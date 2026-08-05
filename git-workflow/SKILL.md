---
name: git-workflow
description: Apply team conventions for Git branch names, conventional commit messages, pull-request titles and descriptions, and code-review comments or replies. Use when creating or naming a branch, drafting or validating a commit, preparing a PR, writing review feedback, or responding to review discussion.
---

# Git Workflow

Before drafting a branch, commit, or PR for an existing repository, check its
contribution guidance and PR template when present. Repository-specific
conventions take precedence over this skill.

## Response Format

- For a branch request, offer one to three names and put the best choice first.
- For a commit request, give the ready-to-use message first. Add a body only
  when it preserves useful context about why, risk, or compatibility.
- For a PR request, provide a title and a completed template.
- For a review comment or reply request, provide the ready-to-post text unless
  the user asks for implementation or more context.

## Branches

Name branches `<type>/<short-kebab-description>`. Use lowercase letters,
numbers, and hyphens. Describe the outcome, not the implementation.

| Work | Prefix | Example |
| --- | --- | --- |
| Feature | `feat/` | `feat/team-invitations` |
| Bug fix | `fix/` | `fix/token-refresh-loop` |
| Documentation | `docs/` | `docs/api-authentication` |
| Refactor | `refactor/` | `refactor/session-store` |
| Tests | `test/` | `test/invitation-expiry` |
| CI/build | `ci/` or `build/` | `ci/cache-dependencies` |
| Maintenance | `chore/` | `chore/update-dependencies` |
| Performance | `perf/` | `perf/reduce-query-count` |
| Formatting | `style/` | `style/format-api-client` |
| Urgent fix | `hotfix/` | `hotfix/revoke-compromised-key` |
| Release preparation | `release/` | `release/v2.4.0` |

## Commits

Use Conventional Commits:

```text
<type>[optional scope]: <imperative description>

[optional body]

[optional footer(s)]
```

- Use `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`,
  `ci`, or `chore`.
- Make the subject imperative, specific, lowercase after the prefix, and end
  it without a period: `fix(auth): prevent refresh token reuse`.
- Keep the subject at 50 characters or fewer, including its prefix.
- Keep each body line at 72 characters or fewer. Separate the body and any
  footer with blank lines. Explain what changed and why; omit implementation
  detail unless it is important context.
- Use a scope only when it makes the change easier to understand. Mark a
  breaking change with `!` or a `BREAKING CHANGE:` footer.
- Group one logical change per commit. Inspect the staged diff before writing
  the message; do not commit unrelated work together.

## Pull Requests

- Use the same format as commits for the title.
- Use the repository's PR template. If none exists, use the bundled
  [PULL_REQUEST_TEMPLATE.md](PULL_REQUEST_TEMPLATE.md).
- State the user impact or motivation, what changed, how it was tested, and
  material risks (including security, privacy, and migrations).
- Make PR descriptions about the change, not a pasted commit message.

## Review Comments and Replies

Make comments specific, actionable, and tied to observable behavior. State the
issue, impact, and requested change; suggest a direction when useful. Mark as
**blocking** only issues that should prevent merging. Otherwise use a
suggestion, nit, or question.

Leave feedback on changed code as an inline comment on the smallest relevant
line or contiguous range. Use a general PR comment only when feedback applies
across files, concerns the overall design, or has no suitable changed line. On
GitHub, add comments to a pending review and submit the complete review rather
than publishing comments individually.

Use a GitHub suggestion for an edit that is small, self-contained, and safe to
evaluate in isolation:

````markdown
```suggestion
replacement code
```
````

Do not use suggestions for multi-file changes, unseen context, or broad design
decisions.

For every review thread, choose one outcome: fixed, partially fixed, deferred,
or declined. Reply with the outcome first, then the rationale and evidence.

- **Fixed:** `Fixed in abc1234: validate the token before reading its claims.`
- **Partially fixed:** `Updated the retry path in abc1234; the shared timeout
  policy is out of scope because it affects all clients.`
- **Deferred:** `Agreed. Tracked the broader cleanup in #123 so this PR can
  remain focused.`
- **Declined:** `Keeping this as-is: the framework invokes this method by name,
  and renaming it would break discovery.`

Avoid vague acknowledgements such as `done` or `updated`. When a reply refers
to a code change, post it only after the change is committed and pushed.
