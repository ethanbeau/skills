# PR Operations

## Preconditions

- Run commands from the target repository or worktree.
- Ensure `origin` exists and points at the GitHub repo you intend to operate on.
- Ensure `gh auth status` succeeds before PR, review, or thread-reply operations.
- Invoke helper scripts with `python3`.

## Create

### 1) Gather State

```bash
python3 scripts/gather_repo_state.py
```

Returns JSON:

```json
{
  "owner": "acme", "repo": "widget",
  "branch": "feat/add-auth", "base_branch": "develop",
  "on_base_branch": false, "has_staged": true,
  "staged_stat": "src/auth.py | 45 +++\n2 files changed",
  "commits_ahead": ["abc1234 feat(auth): add JWT validation"],
  "commits_ahead_count": 1
}
```

### 2) Determine Path

| Condition | Action |
| --------- | ------ |
| `on_base_branch=false` + `commits_ahead_count > 0` + `has_staged=false` | Go to step 4 |
| `on_base_branch=false` + `commits_ahead_count > 0` + `has_staged=true` | Ask whether staged changes belong in this PR. If yes, commit them on the current branch before step 4. |
| `on_base_branch=true` + `has_staged=true` | Go to step 3 |
| `on_base_branch=true` + `has_staged=false` | Abort: "No staged changes to create PR from" |
| `on_base_branch=false` + `commits_ahead_count == 0` + `has_staged=true` | Commit the staged changes on the current branch, then continue to step 4. |
| `on_base_branch=false` + `commits_ahead_count == 0` + `has_staged=false` | Abort: "No commits or staged changes to create PR from" |

### 3) Create Branch and/or Commit

1. If currently on the base branch, generate a conventional branch name and create it first.
2. Run `git diff --staged` to analyze changes.
3. Generate a conventional commit message (see [conventions.md](conventions.md)).
4. Execute only the commands needed for the current state:

```bash
git checkout -b <type>/<description>  # only when starting from base branch
git commit -m "<type>[scope]: <description>"
git push -u origin HEAD
```

Run the commit preflight before `git commit`:

```bash
python3 scripts/prepare_commit.py "<message>"
```

For multi-line messages, pass the temp file directly to the preflight:

```bash
python3 scripts/prepare_commit.py --file "$TMPDIR/commit-msg.txt"
```

It returns compact JSON with readiness, blockers, and the recommended push
command. Add `--verbose` when you need the raw repo-state and validation
payloads. Use `validate_commit_msg.py` directly only for message-only
debugging.

### 4) Generate PR Content

**Title**: Conventional commit format, lowercase description after prefix.

- Convert branch to title: `feat/add-user-auth` -> `feat(auth): add user authentication`
- Infer scope from files changed or branch context

**Body**: Find the PR template using this fallback chain:

1. `.github/PULL_REQUEST_TEMPLATE.md` (relative to repo root)
2. First `.md` file in `.github/PULL_REQUEST_TEMPLATE/` directory
3. Skill-bundled `PULL_REQUEST_TEMPLATE.md` (alongside the skill file)

Read the template. Fill sections from diff, commits, and context. Leave placeholders for sections needing manual input. Remove inapplicable sections.

### 5) Create PR

Push the branch if no upstream tracking exists, then create the PR:

```bash
git push -u origin HEAD
gh pr create --title "<title>" --base "<base_branch>" --body "<body>"
```

For draft PRs, add `--draft` to the `gh pr create` command.

### 6) Report

Display the PR URL on success or error details on failure.

---

## Review

### PR Input

- Required: PR URL or `owner/repo#number`
- Optional: focus override after the identifier
  - `owner/repo#123 focus: security, tests`
  - `https://github.com/org/repo/pull/45 focus: error handling`

Focus override replaces the default checklist entirely.

### 1) Parse Input

Extract `owner`, `repo`, `number` from the PR reference (URL like `https://github.com/owner/repo/pull/N` or shorthand `owner/repo#N`). Parse optional focus override from the user's message text.

### 2) Fetch Context

```bash
python3 scripts/fetch_pr_context.py <owner> <repo> <number>
```

Returns JSON with metadata and filtered per-file diffs:

```json
{
  "title": "...", "author": "...", "base": "...", "head": "...",
  "additions": 120, "deletions": 15, "files": [...], "body": "...",
  "diff_files": [
    {
      "path": "src/auth.py",
      "diff": "@@...",
      "line_count": 84,
      "original_line_count": 84,
      "truncated": false,
      "truncated_reason": null,
      "commentable_line_count": 12,
      "hunks": [
        {
          "header": "@@ -10,2 +10,4 @@",
          "old_start": 10,
          "old_count": 2,
          "new_start": 10,
          "new_count": 4,
          "added_line_count": 2,
          "deleted_line_count": 0,
          "added_line_ranges": [{"start": 12, "end": 13}],
          "incomplete": false
        }
      ]
    },
    {
      "path": "src/service.py",
      "diff": "@@...",
      "line_count": 120,
      "original_line_count": 460,
      "truncated": true,
      "truncated_reason": "file_limit+total_limit",
      "commentable_line_count": 18,
      "hunks": [...]
    }
  ],
  "filtered_files": [
    {"path": "package-lock.json", "reason": "lockfile"},
    {"path": "dist/bundle.js", "reason": "path:dist"}
  ],
  "omitted_files": [
    {"path": "src/legacy.py", "reason": "budget_exhausted", "original_line_count": 91}
  ],
  "diff_stats": {
    "total_files": 50, "shown_files": 30,
    "filtered_files": 18, "omitted_files": 1,
    "truncated_files": 2, "budget_exhausted": true
  }
}
```

The script auto-filters lockfiles, generated/minified files, vendored paths, and binary diffs. It allocates an initial slice of the global line budget across reviewable files, then spends the remaining budget by churn (additions + deletions). Defaults: 2000 total lines, 300 per file. Override with `--max-lines N` and `--max-file-lines N`. Use `--no-skip` to include generated/noisy files.

If `diff_stats.budget_exhausted` is true, use `omitted_files` to report which files were not reviewed. Per-file `truncated_reason` shows whether a shown diff was cut by the per-file cap, the total budget, or both.

### 3) Determine Focus

Default (comprehensive):

- Correctness
- Readability
- Bugs / edge cases
- Security
- Performance
- Testing

If focus override provided, use only those areas.

### 4) Analyze Changes

Per file from `diff_files`:

- Review against selected focus areas
- Files are already filtered and coverage-balanced before the remaining budget is spent by churn
- Use `hunks` and `added_line_ranges` to identify commentable new-line ranges
- If any files were `truncated`, note `truncated_reason` in your analysis
- If `budget_exhausted`, state which files from `omitted_files` were not reviewed

### 5) Build Review (do NOT submit)

- **Summary**: 1-3 bullets of key findings, focus areas used, partial scope note if applicable
- **Line comments**: `{path, line, side, body}` entries
  - Prefix body with `[critical]`, `[suggestion]`, or `[nit]`
- **Event**:
  - `REQUEST_CHANGES` if any `[critical]` issues
  - `COMMENT` otherwise
  - Never `APPROVE`

### 6) Present for Confirmation

Display to user before submitting:

- Summary body
- Every line comment (file, line, severity, body)
- Review event

Ask user to confirm. If declined, stop.

### 7) Submit via Script

After confirmation only. Write line comments to a temp JSON file:

```json
[
  {"path": "src/auth.py", "line": 42, "side": "RIGHT", "body": "[critical] SQL injection risk"},
  {"path": "src/utils.py", "line": 10, "side": "RIGHT", "body": "[nit] unused import"}
]
```

Submit:

```bash
python3 scripts/submit_review.py <owner> <repo> <number> <EVENT> "<summary>" /tmp/review-comments.json
```

The script handles both cases (with/without line comments) and enforces the never-APPROVE policy.

### 8) Report

- Total files reviewed
- Comments by severity
- Review event used

---

## Address Comments

### Input

- Required: PR URL or `owner/repo#number`

### 1) Parse Input and Fetch Context

Extract `owner`, `repo`, `number` from the PR reference.

```bash
python3 scripts/fetch_pr_context.py <owner> <repo> <number>
```

Returns metadata with filtered per-file diffs (same shape as Review step 2). Use `diff_files` for understanding change context per thread.

### 2) Fetch and Filter Review Threads

```bash
python3 scripts/fetch_threads.py <owner> <repo> <number>
```

Returns unresolved, non-outdated threads grouped by file path:

```json
[
  {
    "path": "src/auth.py",
    "threads": [
      {
        "thread_id": "...",
        "comments": [{"comment_id": 12345, "author": "reviewer", "body": "...", "line": 42}]
      }
    ]
  }
]
```

### 3) Checkout PR Branch

```bash
gh pr checkout <number> --repo <owner>/<repo>
```

### 4) Process Threads

For each unresolved, non-outdated thread:

1. **Read context**: open file at `path`, read surrounding lines
2. **Decide**: fix needed or no change warranted
3. **If fixing**: implement the minimal change
4. **Draft reply** (do not post yet):
   - Fixed: describe what changed and why (commit hash added after committing)
   - Not fixing: explain rationale clearly

After processing all threads, **group related fixes into logical commits**. Fixes that address the same concern or touch the same code area should be committed together. Validate each message before committing:

```bash
python3 scripts/validate_commit_msg.py "<message>"
git add <files>
git commit -m "<type>: <concise description>" \
  -m "Addresses review feedback on <path(s)>"
```

### 5) Push

```bash
git push
```

### 6) Reply to Threads

After successful push only. For each thread, post a reply using the `databaseId` of the first comment in the thread:

```bash
gh api --method POST "repos/<owner>/<repo>/pulls/<number>/comments/<comment_id>/replies" -f body="<reply>"
```

Examples:

- Fixed: `"Fixed in abc1234: switched to parameterized query"`
- Not fixing: `"Intentional: this import is used by the test harness via dynamic lookup"`

### 7) Report

- Total threads processed
- Threads fixed (with commit hashes)
- Threads declined (with rationale summaries)

### Constraints

- Never mark threads as resolved
- Never dismiss reviews
- Group related fixes into logical commits (by concern or code area, may span files)
- Implement only necessary fixes; no refactors or unrelated cleanup
- Reply to every unresolved thread, fixed or not
- Post replies only after successful push
