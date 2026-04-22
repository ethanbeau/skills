#!/usr/bin/env python
"""Check whether the current repo state is ready for commit and push.

Usage: python3 scripts/prepare_commit.py <message>
    python3 scripts/prepare_commit.py --verbose <message>
    python3 scripts/prepare_commit.py --file <path>
    echo "feat: add thing" | python3 scripts/prepare_commit.py --stdin

Output: JSON object to stdout with commit readiness, blockers, and the
recommended push command. Use --verbose to include raw repo state and
commit-message validation details.

Exit code 0 if ready to commit, 1 if blocked, 2 if usage is invalid.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any, NoReturn

from gather_repo_state import get_repo_state
from validate_commit_msg import read_message, validation_result


def fail(message: str, code: int = 1) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def parse_args(argv: list[str]) -> tuple[bool, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(argv)

    if not parsed.args:
        fail("prepare_commit.py requires a commit message or --file/--stdin", code=2)

    return parsed.verbose, parsed.args


def current_upstream() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    upstream = result.stdout.strip()
    return upstream or None


def push_plan(repo_state: dict[str, Any], upstream: str | None) -> dict[str, Any]:
    if repo_state["on_base_branch"]:
        return {
            "has_upstream": upstream is not None,
            "upstream": upstream,
            "command": "git push -u origin HEAD",
            "reason": "Current branch is the base branch; after creating a feature branch, push it with a new upstream.",
        }

    if upstream:
        return {
            "has_upstream": True,
            "upstream": upstream,
            "command": "git push",
            "reason": "Current branch already tracks a remote branch.",
        }

    return {
        "has_upstream": False,
        "upstream": None,
        "command": "git push -u origin HEAD",
        "reason": "Current branch has no upstream yet.",
    }


def build_blockers(
    repo_state: dict[str, Any], message_result: dict[str, Any]
) -> list[str]:
    blockers: list[str] = []

    if not repo_state["has_staged"]:
        blockers.append("No staged changes to commit.")

    if repo_state["on_base_branch"]:
        blockers.append(
            f"Current branch '{repo_state['branch']}' is the base branch; create a feature branch before committing."
        )

    if not message_result["valid"]:
        blockers.append("Commit message validation failed.")

    return blockers


def build_next_steps(
    repo_state: dict[str, Any], message_result: dict[str, Any], blockers: list[str], push: dict[str, Any]
) -> list[str]:
    if blockers:
        steps: list[str] = []
        if repo_state["on_base_branch"]:
            steps.append("Create a feature branch before committing.")
        if not repo_state["has_staged"]:
            steps.append("Stage the intended files with git add.")
        if not message_result["valid"]:
            steps.append("Fix the commit message validation errors and re-run this helper.")
        return steps

    return ["Run git commit with the validated message.", f"Run {push['command']}."]


def build_result(
    repo_state: dict[str, Any],
    message_result: dict[str, Any],
    blockers: list[str],
    push: dict[str, Any],
    verbose: bool,
) -> dict[str, Any]:
    result = {
        "ready": not blockers,
        "message_valid": message_result["valid"],
        "has_staged": repo_state["has_staged"],
        "branch_required": repo_state["on_base_branch"],
        "push_command": push["command"],
        "blockers": blockers,
        "next_steps": build_next_steps(repo_state, message_result, blockers, push),
    }

    if verbose:
        result["repo_state"] = repo_state
        result["commit_message"] = message_result
        result["push"] = push

    return result


def main() -> None:
    verbose, message_args = parse_args(sys.argv[1:])
    repo_state = get_repo_state()
    message = read_message(["prepare_commit.py", *message_args])
    message_result = validation_result(message)

    upstream = current_upstream()
    push = push_plan(repo_state, upstream)
    blockers = build_blockers(repo_state, message_result)
    ready = not blockers and message_result["valid"]

    result = build_result(repo_state, message_result, blockers, push, verbose)
    json.dump(result, sys.stdout, indent=2)
    print()
    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()