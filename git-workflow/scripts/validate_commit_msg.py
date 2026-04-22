#!/usr/bin/env python
"""Validate a commit message against conventional commit and 50/72 rules.

Usage: python3 validate_commit_msg.py <message>
    python3 validate_commit_msg.py --file <path>
    echo "feat: add thing" | python3 validate_commit_msg.py --stdin

Validates:
  - Conventional commit type prefix (required)
  - Subject line max 50 characters
  - Blank line between subject and body
  - Body lines wrap at 72 characters
  - No trailing period on subject
  - Lowercase first letter after prefix
  - Footer formatting (Closes #N, BREAKING CHANGE:, etc.)

Output: JSON object to stdout with "valid" (bool) and "errors" (list of strings).
Exit code 0 if valid, 1 if invalid, 2 if usage error.
"""

import json
import re
import sys
from typing import Never

TYPES = frozenset(
    {
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
    }
)

SUBJECT_MAX = 50
BODY_WRAP = 72
USAGE = (
    "Usage: validate_commit_msg.py <message>\n"
    "       validate_commit_msg.py --file <path>\n"
    "       validate_commit_msg.py --stdin"
)

PREFIX_RE = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\([a-z0-9._-]+\))?"
    r"!?"
    r": "
    r"(?P<desc>.+)$"
)

FOOTER_RE = re.compile(
    r"^(?:"
    r"BREAKING CHANGE: .+"
    r"|[A-Za-z-]+: .+"
    r"|[A-Za-z-]+ #\d+"
    r")$"
)


def fail_usage() -> Never:
    print(USAGE, file=sys.stderr)
    sys.exit(2)


def validate(message: str) -> list[str]:
    errors: list[str] = []
    lines = message.rstrip("\n").split("\n")

    if not lines or not lines[0].strip():
        errors.append("Empty commit message")
        return errors

    subject = lines[0]

    m = PREFIX_RE.match(subject)
    if not m:
        errors.append(
            "Subject does not match conventional commit format: "
            "<type>[scope]: <description>"
        )
        return errors

    if m.group("type") not in TYPES:
        errors.append(
            f"Unknown type '{m.group('type')}'; "
            f"expected one of: {', '.join(sorted(TYPES))}"
        )

    desc = m.group("desc")
    if desc and desc[0].isupper():
        errors.append("Description after prefix should be lowercase")

    if subject.endswith("."):
        errors.append("Subject line should not end with a period")

    if len(subject) > SUBJECT_MAX:
        errors.append(f"Subject is {len(subject)} chars (max {SUBJECT_MAX})")

    if len(lines) == 1:
        return errors

    if len(lines) >= 2 and lines[1].strip():
        errors.append("Missing blank line between subject and body")

    body_start = 2 if len(lines) >= 2 and not lines[1].strip() else 1

    in_footer = False
    for line_number, line in enumerate(lines[body_start:], start=body_start + 1):
        if not in_footer and FOOTER_RE.match(line):
            if line_number >= 3 and lines[line_number - 2].strip():
                errors.append(
                    f"Line {line_number}: footer should be preceded by a blank line"
                )
            in_footer = True

        if in_footer:
            continue

        if len(line) > BODY_WRAP:
            errors.append(
                f"Line {line_number}: {len(line)} chars (wrap at {BODY_WRAP})"
            )

    return errors


def read_message(argv: list[str]) -> str:
    if len(argv) >= 3 and argv[1] == "--file":
        with open(argv[2], encoding="utf-8") as handle:
            return handle.read()

    if len(argv) >= 2 and argv[1] == "--stdin":
        return sys.stdin.read()

    if len(argv) >= 2 and argv[1] not in ("--file", "--stdin"):
        return argv[1]

    fail_usage()


def main() -> None:
    message = read_message(sys.argv)
    errors = validate(message)
    result = {"valid": len(errors) == 0, "errors": errors}
    json.dump(result, sys.stdout, indent=2)
    print()
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
