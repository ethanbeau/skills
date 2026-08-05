# Git-workflow evals

These evals measure whether the skill is selected for Git collaboration work and
whether it improves branch, commit, PR, and review-comment outputs without
polluting adjacent requests.

## Conditions and command

Each case runs in an isolated `codex exec` subprocess under `skill_on` and
`skill_off`, with three trials per condition. The on condition supplies the
current `SKILL.md` as context; the off condition supplies no workflow guidance.

```sh
python3 evals/git-workflow/run_eval.py --trials 3
python3 evals/git-workflow/grade_results.py
```

The local Codex CLI runs `gpt-5.6-luna`; the current release evidence is a
fresh 60-trial Luna run.
The inline-review grader accepts a GitHub `suggestion` block as line-level
review evidence because GitHub renders that syntax only for an inline comment.

## Release gates

- Zero must-pass failures on explicit, implicit, contextual, and harm cases.
- No regression in negative-control true-negative rate.
- Positive task-pass uplift over `skill_off` on intended cases.
- Three independent trials per case and condition.

The trigger field is behavioral rather than an internal skill-selection trace,
because the local CLI does not expose skill-routing events. Treat trigger
metrics as diagnostic until a trace-capable harness is available.
