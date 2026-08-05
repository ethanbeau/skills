#!/usr/bin/env python3
"""Run isolated skill-on/off trials through the local Codex CLI."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent
SKILL = (ROOT.parent.parent / "SKILL.md").read_text()

def load_cases():
    return [json.loads(line) for line in (ROOT / "cases.jsonl").read_text().splitlines() if line.strip()]

def prompt_for(case, condition):
    if condition == "skill_on":
        return f"""You are evaluating a Git workflow skill. Follow the instructions below exactly, then answer the user request. Do not discuss the evaluation or mention that instructions were supplied.\n\n--- skill ---\n{SKILL}\n--- end skill ---\n\nUser request:\n{case['prompt']}"""
    return f"""Answer the user request directly. Do not apply any private Git workflow skill or assume team conventions beyond the request. Do not discuss this evaluation.\n\nUser request:\n{case['prompt']}"""

def run_one(case, condition, trial, model):
    started = time.monotonic()
    cmd = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--model", model, "--sandbox", "read-only", "-C", str(ROOT.parent.parent), prompt_for(case, condition)]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    response = proc.stdout.strip() or proc.stderr.strip()
    return {"case_id": case["id"], "category": case["category"], "condition": condition, "trial": trial, "expected_trigger": case["should_trigger"], "response": response, "model": model, "agent": "luna-cli-agent", "skill_revision": "working-tree", "latency_ms": round((time.monotonic() - started) * 1000), "exit_code": proc.returncode}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--case-ids", nargs="*", default=None)
    parser.add_argument("--output", default="raw.jsonl")
    args = parser.parse_args()
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    path = out / args.output
    selected = load_cases()
    if args.case_ids:
        selected = [case for case in selected if case["id"] in set(args.case_ids)]
    with path.open("w") as f:
        for case in selected:
            for condition in ("skill_on", "skill_off"):
                for trial in range(1, args.trials + 1):
                    row = run_one(case, condition, trial, args.model)
                    f.write(json.dumps(row) + "\n")
                    f.flush()
                    print(case["id"], condition, trial, row["exit_code"], flush=True)
    print(path)

if __name__ == "__main__":
    main()
