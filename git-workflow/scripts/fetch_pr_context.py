#!/usr/bin/env python
"""Fetch PR metadata and diff for review or comment-addressing workflows.

Usage: python3 fetch_pr_context.py <owner> <repo> <pr_number> [options]

Options:
  --max-lines N       Total diff line budget across all files (default: 2000)
  --max-file-lines N  Per-file diff line cap (default: 300)
  --no-skip           Disable auto-skip of generated/noisy files

Output: JSON object to stdout with PR metadata and per-file diffs.
"""

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from typing import Never

BASE_FILE_BUDGET = 80

SKIP_BASENAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Pipfile.lock",
        "poetry.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
    }
)

SKIP_GLOBS = (
    "*.lock",
    "*.min.js",
    "*.min.css",
    "*.generated.*",
    "*_generated.*",
    "*.pb.go",
    "*_pb2.py",
    "*.snap",
)

SKIP_PATH_SEGMENTS = ("/vendor/", "/node_modules/", "/dist/", "/build/")

DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def fail(message: str) -> Never:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def format_command_error(
    label: str,
    details: str,
    repo_ref: str | None = None,
    number: str | None = None,
) -> str:
    lowered = details.lower()

    if (
        "not logged into any github hosts" in lowered
        or "authentication failed" in lowered
        or "gh auth login" in lowered
    ):
        return "gh CLI is not authenticated. Run `gh auth status` or `gh auth login`."

    if repo_ref and (
        "could not resolve to a repository" in lowered
        or ("repository" in lowered and "not found" in lowered)
    ):
        return f"Repository {repo_ref} was not found or is not accessible."

    if (
        repo_ref
        and number
        and (
            "could not resolve to a pullrequest" in lowered
            or "no pull requests found" in lowered
            or ("pull request" in lowered and "not found" in lowered)
        )
    ):
        return f"PR {number} was not found in {repo_ref}."

    if not details:
        return f"{label} failed"

    return f"{label} failed: {details}"


def run(
    cmd: list[str], label: str, repo_ref: str | None = None, number: str | None = None
) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        fail(f"Required CLI is not installed or not on PATH: {cmd[0]}")
    except OSError as exc:
        fail(f"{label} failed: {exc}")

    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        fail(format_command_error(label, details, repo_ref=repo_ref, number=number))

    return result.stdout.strip()


def load_json(raw: str, label: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"{label} returned invalid JSON: {exc}")

    if not isinstance(parsed, dict):
        fail(f"{label} returned unexpected JSON payload")

    return parsed


def skip_reason(path: str) -> str | None:
    basename = path.rsplit("/", 1)[-1] if "/" in path else path
    if basename in SKIP_BASENAMES:
        return "lockfile"
    for glob in SKIP_GLOBS:
        if fnmatch.fnmatch(basename, glob):
            return f"pattern:{glob}"
    for segment in SKIP_PATH_SEGMENTS:
        if segment in f"/{path}/":
            return f"path:{segment.strip('/')}"
    return None


def is_binary_diff(chunk: str) -> bool:
    for line in chunk.split("\n", 10):
        if line.startswith("Binary files") or line.startswith("GIT binary patch"):
            return True
    return False


def parse_diff(raw_diff: str) -> list[dict]:
    """Split a unified diff into per-file chunks."""
    files: list[dict] = []
    current_path: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_path is not None:
            files.append({"path": current_path, "raw": "\n".join(current_lines)})

    for line in raw_diff.split("\n"):
        m = DIFF_HEADER_RE.match(line)
        if m:
            flush()
            current_path = m.group(2)
            current_lines = [line]
        else:
            current_lines.append(line)

    flush()
    return files


def build_churn_index(files_metadata: list[dict]) -> dict[str, int]:
    """Map file path -> additions+deletions from PR metadata."""
    index: dict[str, int] = {}
    for f in files_metadata:
        path = f.get("path")
        if not path:
            continue
        index[path] = f.get("additions", 0) + f.get("deletions", 0)
    return index


def compress_line_ranges(lines: list[int]) -> list[dict]:
    if not lines:
        return []

    ranges: list[dict] = []
    start = lines[0]
    end = lines[0]

    for line in lines[1:]:
        if line == end + 1:
            end = line
            continue
        ranges.append({"start": start, "end": end})
        start = line
        end = line

    ranges.append({"start": start, "end": end})
    return ranges


def finalize_hunk(hunk: dict) -> dict:
    added_lines = hunk.pop("_added_lines")
    hunk["added_line_ranges"] = compress_line_ranges(added_lines)
    return hunk


def is_diff_metadata_line(line: str) -> bool:
    return (
        line.startswith("diff --git")
        or line.startswith("index ")
        or line.startswith("--- ")
        or line.startswith("+++ ")
        or line.startswith("@@")
        or line.startswith("\\ No newline at end of file")
    )


def minimum_useful_lines(lines: list[str], capped_line_count: int) -> int:
    capped_lines = lines[:capped_line_count]

    for index, line in enumerate(capped_lines, start=1):
        if is_diff_metadata_line(line):
            continue
        return index

    return min(capped_line_count, 1)


def build_candidate(entry: dict, churn: dict[str, int], max_file_lines: int) -> dict:
    original_lines = entry["raw"].split("\n")
    capped_line_count = min(len(original_lines), max_file_lines)

    return {
        "path": entry["path"],
        "original_lines": original_lines,
        "original_line_count": len(original_lines),
        "capped_line_count": capped_line_count,
        "minimum_useful_lines": minimum_useful_lines(original_lines, capped_line_count),
        "churn": churn.get(entry["path"], 0),
        "allocated": 0,
    }


def allocate_line_budget(
    candidates: list[dict], max_lines: int, max_file_lines: int
) -> None:
    budget_remaining = max_lines
    base_file_budget = min(BASE_FILE_BUDGET, max_file_lines)

    for index, entry in enumerate(candidates):
        if budget_remaining <= 0:
            continue

        remaining_files = len(candidates) - index
        fair_share = max(1, budget_remaining // remaining_files)
        initial_budget = min(entry["capped_line_count"], base_file_budget, fair_share)

        if initial_budget < entry["minimum_useful_lines"]:
            if budget_remaining < entry["minimum_useful_lines"]:
                continue
            initial_budget = min(
                entry["capped_line_count"],
                max(base_file_budget, entry["minimum_useful_lines"]),
            )

        entry["allocated"] = initial_budget
        budget_remaining -= initial_budget

    for entry in candidates:
        if budget_remaining <= 0:
            break

        remaining = entry["capped_line_count"] - entry["allocated"]
        if remaining <= 0:
            continue

        if entry["allocated"] == 0 and budget_remaining < entry["minimum_useful_lines"]:
            continue

        extra_budget = min(remaining, budget_remaining)
        if entry["allocated"] == 0 and extra_budget < entry["minimum_useful_lines"]:
            continue

        entry["allocated"] += extra_budget
        budget_remaining -= extra_budget


def truncation_reasons_for(entry: dict, max_file_lines: int) -> list[str]:
    reasons: list[str] = []
    if entry["original_line_count"] > max_file_lines:
        reasons.append("file_limit")
    if entry["allocated"] < entry["capped_line_count"]:
        reasons.append("total_limit")
    return reasons


def parse_hunks(lines: list[str], truncated: bool) -> list[dict]:
    hunks: list[dict] = []
    current: dict | None = None
    old_line = 0
    new_line = 0

    for line in lines:
        header = HUNK_HEADER_RE.match(line)
        if header:
            if current is not None:
                hunks.append(finalize_hunk(current))

            old_line = int(header.group("old_start"))
            new_line = int(header.group("new_start"))
            current = {
                "header": line,
                "old_start": old_line,
                "old_count": int(header.group("old_count") or 1),
                "new_start": new_line,
                "new_count": int(header.group("new_count") or 1),
                "added_line_count": 0,
                "deleted_line_count": 0,
                "added_line_ranges": [],
                "incomplete": False,
                "_added_lines": [],
            }
            continue

        if current is None:
            continue

        if line.startswith("+++") or line.startswith("---"):
            continue

        if line.startswith("\\ No newline at end of file"):
            continue

        if line.startswith("+"):
            current["_added_lines"].append(new_line)
            current["added_line_count"] += 1
            new_line += 1
            continue

        if line.startswith("-"):
            current["deleted_line_count"] += 1
            old_line += 1
            continue

        old_line += 1
        new_line += 1

    if current is not None:
        hunks.append(finalize_hunk(current))

    if truncated and hunks:
        hunks[-1]["incomplete"] = True

    return hunks


def process_diffs(
    raw_diff: str,
    files_metadata: list[dict],
    max_lines: int,
    max_file_lines: int,
    skip_enabled: bool,
) -> tuple[list[dict], list[dict], list[dict], dict]:
    parsed = parse_diff(raw_diff)
    churn = build_churn_index(files_metadata)

    filtered_files: list[dict] = []
    candidates: list[dict] = []

    for entry in parsed:
        path = entry["path"]
        if is_binary_diff(entry["raw"]):
            filtered_files.append({"path": path, "reason": "binary_diff"})
            continue

        reason = skip_reason(path) if skip_enabled else None
        if reason is not None:
            filtered_files.append({"path": path, "reason": reason})
            continue

        candidates.append(build_candidate(entry, churn, max_file_lines))

    candidates.sort(key=lambda entry: (-entry["churn"], entry["path"]))
    allocate_line_budget(candidates, max_lines, max_file_lines)

    diff_files: list[dict] = []
    omitted_files: list[dict] = []
    truncated_count = 0

    for entry in candidates:
        if entry["allocated"] == 0:
            omitted_files.append(
                {
                    "path": entry["path"],
                    "reason": "budget_exhausted",
                    "original_line_count": entry["original_line_count"],
                }
            )
            continue

        lines = entry["original_lines"][: entry["allocated"]]
        truncation_reasons = truncation_reasons_for(entry, max_file_lines)

        was_truncated = bool(truncation_reasons)
        if was_truncated:
            truncated_count += 1

        hunks = parse_hunks(lines, truncated=was_truncated)
        commentable_line_count = sum(hunk["added_line_count"] for hunk in hunks)

        diff_files.append(
            {
                "path": entry["path"],
                "diff": "\n".join(lines),
                "line_count": len(lines),
                "original_line_count": entry["original_line_count"],
                "truncated": was_truncated,
                "truncated_reason": "+".join(truncation_reasons)
                if truncation_reasons
                else None,
                "commentable_line_count": commentable_line_count,
                "hunks": hunks,
            }
        )

    budget_exhausted = any(
        entry["allocated"] < entry["capped_line_count"] for entry in candidates
    )

    stats = {
        "total_files": len(parsed),
        "shown_files": len(diff_files),
        "filtered_files": len(filtered_files),
        "omitted_files": len(omitted_files),
        "truncated_files": truncated_count,
        "budget_exhausted": budget_exhausted,
    }

    return diff_files, filtered_files, omitted_files, stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("owner")
    parser.add_argument("repo")
    parser.add_argument("number")
    parser.add_argument("--max-lines", type=positive_int, default=2000)
    parser.add_argument("--max-file-lines", type=positive_int, default=300)
    parser.add_argument("--no-skip", action="store_true")
    args = parser.parse_args()

    repo_ref = f"{args.owner}/{args.repo}"

    metadata_raw = run(
        [
            "gh",
            "pr",
            "view",
            args.number,
            "--repo",
            repo_ref,
            "--json",
            "title,body,author,baseRefName,headRefName,files,additions,deletions",
        ],
        "gh pr view",
        repo_ref=repo_ref,
        number=args.number,
    )
    metadata = load_json(metadata_raw, "gh pr view")

    raw_diff = run(
        ["gh", "pr", "diff", args.number, "--repo", repo_ref],
        "gh pr diff",
        repo_ref=repo_ref,
        number=args.number,
    )

    diff_files, filtered_files, omitted_files, stats = process_diffs(
        raw_diff,
        metadata.get("files", []),
        args.max_lines,
        args.max_file_lines,
        skip_enabled=not args.no_skip,
    )

    author = metadata.get("author") or {}

    result = {
        "title": metadata.get("title", ""),
        "author": author.get("login", "unknown"),
        "base": metadata.get("baseRefName", ""),
        "head": metadata.get("headRefName", ""),
        "additions": metadata.get("additions", 0),
        "deletions": metadata.get("deletions", 0),
        "files": metadata.get("files", []),
        "body": metadata.get("body", ""),
        "diff_files": diff_files,
        "filtered_files": filtered_files,
        "omitted_files": omitted_files,
        "diff_stats": stats,
    }
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
