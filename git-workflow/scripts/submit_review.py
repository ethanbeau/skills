#!/usr/bin/env python
"""Submit a PR review with optional line comments.

Usage: python3 submit_review.py <owner> <repo> <pr_number> <event> <summary> [comments_json_file]

event: COMMENT | REQUEST_CHANGES (never APPROVE)
comments_json_file: optional path to JSON array of {path, line, side, body}

Output: API response JSON to stdout.
"""

import json
import subprocess
import sys
from typing import Never


def fail(message: str) -> Never:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def run_gh(cmd: list[str], payload: str | None = None) -> str:
    try:
        result = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        fail("gh CLI is not installed or not on PATH")
    except OSError as exc:
        fail(str(exc))

    if result.returncode != 0:
        fail(result.stderr.strip() or result.stdout.strip() or "gh command failed")

    return result.stdout


def parse_comments(comments_file: str | None) -> list[dict]:
    if not comments_file:
        return []

    with open(comments_file, encoding="utf-8") as handle:
        return json.load(handle)


def submit_with_comments(
    owner: str, repo: str, number: int, event: str, summary: str, comments: list[dict]
) -> None:
    payload = json.dumps({"event": event, "body": summary, "comments": comments})
    print(
        run_gh(
            [
                "gh",
                "api",
                f"repos/{owner}/{repo}/pulls/{number}/reviews",
                "--method",
                "POST",
                "--input",
                "-",
            ],
            payload=payload,
        )
    )


def submit_simple(owner: str, repo: str, number: int, event: str, summary: str) -> None:
    flag = "--request-changes" if event == "REQUEST_CHANGES" else "--comment"
    print(
        run_gh(
            [
                "gh",
                "pr",
                "review",
                str(number),
                "--repo",
                f"{owner}/{repo}",
                flag,
                "--body",
                summary,
            ]
        )
    )


def validate_event(event: str) -> None:
    if event == "APPROVE":
        fail("APPROVE is not permitted by review policy")

    if event not in ("COMMENT", "REQUEST_CHANGES"):
        fail(f"Invalid event '{event}'. Use COMMENT or REQUEST_CHANGES")


def main() -> None:
    if len(sys.argv) < 6:
        print(
            "Usage: submit_review.py <owner> <repo> <pr_number> <event> <summary> [comments.json]",
            file=sys.stderr,
        )
        sys.exit(1)

    owner, repo = sys.argv[1], sys.argv[2]
    number = int(sys.argv[3])
    event = sys.argv[4].upper()
    summary = sys.argv[5]
    comments_file = sys.argv[6] if len(sys.argv) > 6 else None

    validate_event(event)

    comments = parse_comments(comments_file)

    if comments:
        submit_with_comments(owner, repo, number, event, summary, comments)
    else:
        submit_simple(owner, repo, number, event, summary)


if __name__ == "__main__":
    main()
