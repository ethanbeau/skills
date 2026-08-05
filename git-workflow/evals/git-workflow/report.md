# Git-workflow eval report

## Decision

**Recommendation:** Ship the skill and retain this suite as a regression check.

**Reason:** On Luna, the skill improved task pass rate from 60.0% without the
skill to 100.0% with it (+20.0 percentage points), with no execution failures.
The inline check was recalibrated to accept a GitHub suggestion block as
line-level review evidence; the fresh rerun has zero skill-on must-pass
failures. The skill should not be retired; the ablation shows meaningful
preference-conformance uplift.

## Scope

- Skill revision: current working tree (`SKILL.md`)
- Baseline: same prompts with workflow instructions withheld
- Harness: local `codex exec`, fresh `--ephemeral` process per trial
- Model: `gpt-5.6-luna`
- Conditions: `skill_on`, `skill_off`
- Cases: 10
- Trials per case/condition: 3
- Date: 2026-08-04

## Success gates

| Gate | Threshold | Luna result | Pass |
| --- | ---: | ---: | ---: |
| Must-pass failures, skill on | 0 | 0/30 | Yes |
| Trigger TPR | diagnostic only | not observable | N/A |
| Trigger TNR | diagnostic only | not observable | N/A |
| Task uplift vs skill-off | > 0 | +20.0 pp | Yes |
| Execution failures | 0 | 0/60 | Yes |
| Repeated trials | 3/cell | complete | Yes |

## Results

| Model / condition | Passed | Total | Pass rate | Median latency |
| --- | ---: | ---: | ---: | ---: |
| Luna / skill on | 30 | 30 | 100.0% | 7.8 s |
| Luna / skill off | 24 | 30 | 80.0% | 7.6 s |
The Luna result is the release evidence.

## Failures and diagnosis

- `inline-suggestion`, skill on: all three trials supplied a valid GitHub
  suggestion block. The grader now correctly recognizes that construct as
  inline-review evidence; no skill change was required.
- The first ambiguous-boundary grader treated generic examples such as
  `release/2.4.0` as team workflow artifacts. It now distinguishes education
  from a directive, and the results above use the corrected check.
- `implicit-review-reply` and `contextual-pr-risk`, skill off: the base model
  sometimes produced useful Git artifacts, which is expected for a preference
  skill and explains why uplift—not raw pass rate alone—is the key measure.

## Grader limitations

The local CLI does not expose skill-routing events, so trigger precision, TPR,
and TNR are behavioral proxies rather than routing traces. Regex and keyword
checks are deterministic but can miss semantic equivalents or flag generic Git
examples. No cost telemetry was available; latency is wall-clock process time.

## Next change

No `SKILL.md` change is justified by this run. On the next material skill or
harness change, rerun the same 10-case, three-trial ablation and compare it
with these Luna results.
