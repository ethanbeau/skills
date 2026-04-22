#!/usr/bin/env python
"""Gather repository state for PR creation workflow.

Usage: python3 scripts/gather_repo_state.py
Output: JSON object to stdout with all fields needed to determine the PR creation path.

Example output:
{
  "owner": "acme",
  "repo": "widget",
  "branch": "feature/add-auth",
  "base_branch": "develop",
  "on_base_branch": false,
  "has_staged": true,
  "staged_stat": "src/auth.py | 45 +++\n2 files changed",
  "commits_ahead": ["abc1234 feat(auth): add JWT validation"],
  "commits_ahead_count": 1
}
"""

import json
import subprocess
import sys
from typing import Any, Never
from urllib.parse import urlparse


def fail(message: str) -> Never:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], check: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    return result.stdout.strip()


def command_succeeded(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def detect_remote_head() -> str | None:
    result = subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip().removeprefix("refs/remotes/origin/")


def detect_origin_show_head() -> str | None:
    result = subprocess.run(
        ["git", "remote", "show", "origin"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    prefix = "  HEAD branch: "
    for line in result.stdout.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()

    return None


def branch_exists(branch: str) -> bool:
    return command_succeeded(["git", "rev-parse", "--verify", f"refs/heads/{branch}"])


def remote_branch_exists(branch: str) -> bool:
    return command_succeeded(
        ["git", "rev-parse", "--verify", f"refs/remotes/origin/{branch}"]
    )


def parse_remote_url(url: str) -> tuple[str, str]:
    url = url.removesuffix(".git")
    if url.startswith("git@"):
        # git@github.com:owner/repo
        path = url.split(":", 1)[1]
    else:
        path = urlparse(url).path.lstrip("/")
    parts = path.split("/")
    return parts[0], parts[1]


def detect_base_branch() -> str:
    """Detect base branch: prefer remote default, else develop, else main/master."""
    for detector in (detect_remote_head, detect_origin_show_head):
        branch = detector()
        if branch:
            return branch

    if branch_exists("develop") or remote_branch_exists("develop"):
        return "develop"

    for branch in ("main", "master"):
        if remote_branch_exists(branch) or branch_exists(branch):
            return branch

    return "main"


def get_repo_state() -> dict[str, Any]:
    repo_check = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if repo_check.returncode != 0:
        fail("Not inside a git repository")

    remote_result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    )
    if remote_result.returncode != 0:
        fail("Repository has no 'origin' remote")

    remote_url = remote_result.stdout.strip()
    owner, repo = parse_remote_url(remote_url)
    branch = run(["git", "branch", "--show-current"])
    if not branch:
        fail("HEAD is detached (not on a branch)")

    base_branch = detect_base_branch()
    on_base_branch = branch == base_branch

    run(["git", "fetch", "origin", base_branch, "--quiet"], check=False)

    staged_stat = run(["git", "diff", "--staged", "--stat"], check=False)
    has_staged = bool(staged_stat)

    commits_ahead_raw = run(
        ["git", "log", f"origin/{base_branch}..HEAD", "--oneline"],
        check=False,
    )
    commits_ahead = [line for line in commits_ahead_raw.splitlines() if line]

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "base_branch": base_branch,
        "on_base_branch": on_base_branch,
        "has_staged": has_staged,
        "staged_stat": staged_stat,
        "commits_ahead": commits_ahead,
        "commits_ahead_count": len(commits_ahead),
    }


def main() -> None:
    state = get_repo_state()
    json.dump(state, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
