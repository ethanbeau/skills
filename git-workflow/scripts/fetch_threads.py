#!/usr/bin/env python
"""Fetch unresolved, non-outdated PR review threads with automatic pagination.

Usage: python3 fetch_threads.py <owner> <repo> <pr_number>
Output: JSON array of threads grouped by file path, to stdout.
"""

import json
import subprocess
import sys
from itertools import groupby
from typing import Never

QUERY = """
query($owner:String!, $repo:String!, $number:Int!, $after:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$after) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first:100) {
            nodes {
              databaseId
              author { login }
              body
              path
              line
              startLine
              originalLine
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


def fail(message: str) -> Never:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def load_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"gh api graphql returned invalid JSON: {exc}")


def gh_graphql(owner: str, repo: str, number: int, after: str | None = None) -> dict:
    cmd = [
        "gh",
        "api",
        "graphql",
        "-F",
        f"owner={owner}",
        "-F",
        f"repo={repo}",
        "-F",
        f"number={number}",
        "-f",
        f"query={QUERY}",
    ]
    if after:
        cmd.extend(["-F", f"after={after}"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        fail("gh CLI is not installed or not on PATH")
    except OSError as exc:
        fail(f"gh api graphql failed: {exc}")

    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "unknown error"
        fail(f"gh api graphql failed: {details}")

    return load_json(result.stdout)


def fetch_all_threads(owner: str, repo: str, number: int) -> list[dict]:
    threads: list[dict] = []
    cursor = None

    while True:
        data = gh_graphql(owner, repo, number, cursor)
        review_threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]

        for node in review_threads["nodes"]:
            if not node["isResolved"] and not node["isOutdated"]:
                threads.append(node)

        page_info = review_threads["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    return threads


def build_thread_comments(thread: dict) -> list[dict]:
    return [
        {
            "comment_id": comment["databaseId"],
            "author": comment["author"]["login"],
            "body": comment["body"],
            "path": comment["path"],
            "line": comment["line"],
            "start_line": comment["startLine"],
            "original_line": comment["originalLine"],
        }
        for comment in thread["comments"]["nodes"]
    ]


def thread_path(thread: dict) -> str:
    return thread["comments"][0]["path"] or ""


def transform(threads: list[dict]) -> list[dict]:
    flat = []
    for thread in threads:
        comments = build_thread_comments(thread)
        if not comments:
            continue
        flat.append({"thread_id": thread["id"], "comments": comments})

    sorted_threads = sorted(flat, key=thread_path)
    return [
        {"path": path, "threads": list(group)}
        for path, group in groupby(sorted_threads, key=thread_path)
    ]


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: fetch_threads.py <owner> <repo> <pr_number>", file=sys.stderr)
        sys.exit(1)

    owner, repo, number = sys.argv[1], sys.argv[2], int(sys.argv[3])
    threads = fetch_all_threads(owner, repo, number)
    result = transform(threads)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
