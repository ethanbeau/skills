#!/usr/bin/env python3
"""Grade JSONL responses from run_eval.py with deterministic checks."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
CASES = {json.loads(line)["id"]: json.loads(line) for line in (ROOT / "cases.jsonl").read_text().splitlines() if line.strip()}

def lower(text: str) -> str:
    return text.lower()

def grade(case, text):
    t = lower(text)
    checks = {}
    for check in case["checks"]:
        cid, typ = check["id"], check["type"]
        passed = True
        evidence = ""
        if typ == "git_branch":
            passed = bool(re.search(r"\b(?:feat|fix|docs|refactor|test|ci|build|chore|perf|style|hotfix|release)/[a-z0-9]+(?:-[a-z0-9]+)*\b", t))
            evidence = "branch prefix and kebab-case name"
        elif typ == "conventional_commit":
            passed = bool(re.search(r"\b(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore)(?:\([^\n)]+\))?!?: [a-z][^\n.]*", t))
            evidence = "Conventional Commit subject"
        elif typ == "commit_subject_limit":
            subjects = re.findall(r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore)(?:\([^\n)]+\))?!?: ([^\n]+)", t)
            passed = bool(subjects) and all(len(s.strip()) + len(re.search(r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore)(?:\([^\n)]+\))?!?: ", t).group(0)) <= 50 for s in subjects)
            evidence = "subject length <= 50"
        elif typ in {"pr_title", "pr_title_match"}:
            passed = bool(re.search(r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore)(?:\([^\n)]+\))?!?:", t))
            evidence = "Conventional PR title"
        elif typ == "review_outcome":
            passed = bool(re.search(r"\b(fixed|partially fixed|deferred|declined)\b", t))
            evidence = "explicit review outcome"
        elif typ == "not_contains_only_ack":
            passed = not bool(re.fullmatch(r"\s*(done|updated|ack|thanks)[!. ]*", t))
            evidence = "reply contains more than a vague acknowledgement"
        elif typ == "pr_template_sections":
            passed = sum(token in t for token in ("motivation", "what changed", "testing", "risk")) >= 3
            evidence = "template sections"
        elif typ == "suggestion_block":
            passed = "```suggestion" in t
            evidence = "GitHub suggestion fence"
        elif typ == "inline_review":
            passed = "```suggestion" in t or any(term in t for term in ("inline", "changed line", "anchor", "range"))
            evidence = "GitHub suggestion block or explicit inline anchor"
        elif typ in {"no_git_artifacts", "no_git_workflow_artifacts"}:
            passed = not bool(re.search(r"\b(feat|fix|docs|refactor|chore|perf|hotfix|release)/[a-z0-9-]+\b|conventional commit|pull request|pr title|```suggestion|review comment", t))
            evidence = "no workflow artifact"
        elif typ == "no_team_directive":
            passed = not bool(re.search(r"\b(our team|the team|for my team|follow (?:this|our)|use this)\b.{0,60}\b(branch|workflow|convention|prefix)\b", t))
            evidence = "no directive applying team conventions"
        elif typ == "ignore-pattern":
            passed = True
        elif typ == "contains_any":
            passed = any(v.lower() in t for v in check["values"])
            evidence = ", ".join(check["values"])
        else:
            passed = False
            evidence = f"unsupported check type: {typ}"
        checks[cid] = {"passed": passed, "evidence": evidence}
    must_failures = [cid for cid, result in checks.items() if not result["passed"] and next(c for c in case["checks"] if c["id"] == cid)["severity"] == "must_pass"]
    return checks, must_failures

def main():
    in_path = ROOT / "results" / "raw.jsonl"
    out_path = ROOT / "results" / "graded.jsonl"
    rows = []
    for line in in_path.read_text().splitlines():
        row = json.loads(line)
        checks, failures = grade(CASES[row["case_id"]], row["response"])
        row["check_results"] = checks
        row["must_pass_failures"] = failures
        row["task_pass"] = not failures
        rows.append(row)
    out_path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
    print(f"graded {len(rows)} rows -> {out_path}")

if __name__ == "__main__":
    main()
