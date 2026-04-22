#!/usr/bin/env python
"""Create a git worktree using $GIT_WORKTREE_DIR.

Usage: python3 create_worktree.py <branch_name> [base_ref]

Directory naming: <repo>-<branch-slug> where the branch slug replaces / with -.
    e.g. repo "widget" + branch "feat/add-auth" -> "widget-feat-add-auth"

Requires $GIT_WORKTREE_DIR to be set.
Output: path to created worktree.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Never
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


def remote_head_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", branch],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def repo_name() -> str:
    url = run(["git", "remote", "get-url", "origin"])
    url = url.removesuffix(".git")
    if url.startswith("git@"):
        path = url.split(":", 1)[1]
    else:
        path = urlparse(url).path.lstrip("/")
    return path.split("/")[-1]


def main() -> None:
    if len(sys.argv) < 2:
        fail("Usage: create_worktree.py <branch_name> [base_ref]")

    branch = sys.argv[1]
    base_ref = sys.argv[2] if len(sys.argv) > 2 else None

    worktree_dir = os.environ.get("GIT_WORKTREE_DIR")
    if not worktree_dir:
        fail("$GIT_WORKTREE_DIR is not set")
    worktree_root = Path(worktree_dir)

    name = repo_name()
    slug = branch.replace("/", "-")
    worktree_path = worktree_root / f"{name}-{slug}"

    if worktree_path.exists():
        fail(f"Worktree directory already exists: {worktree_path}")

    if command_succeeded(["git", "rev-parse", "--verify", f"refs/heads/{branch}"]):
        fail(f"Branch '{branch}' already exists locally")

    if remote_head_exists(branch):
        fail(f"Branch '{branch}' already exists on remote")

    worktree_root.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "worktree", "add", str(worktree_path), "-b", branch]
    if base_ref:
        cmd.append(base_ref)

    subprocess.run(cmd, check=True)
    print(worktree_path)


if __name__ == "__main__":
    main()
