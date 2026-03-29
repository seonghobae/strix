# PR continuity

## Purpose

Keep one canonical PR per branch/work item and avoid duplicate PR queues.

## Preconditions

```bash
gh auth status
git rev-parse --abbrev-ref HEAD
```

If `gh` auth fails, treat continuity as blocked until auth is restored.

## Canonical process

### 1) Resolve branch identity

```bash
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
ME="$(gh api user -q .login)"
echo "$ME:$BRANCH"
```

### 2) Search open PRs for current branch

```bash
gh pr list --state open --head "$ME:$BRANCH" \
  --json number,title,url,headRefName,baseRefName,updatedAt
```

### 3) Decide canonical PR

- If an open PR exists for the current branch, **continue that PR**.
- If none exists, create a new PR from the current branch.
- If multiple PRs represent the same intent, keep the most up-to-date canonical PR and close superseded duplicates with a reason comment.

### 4) Post-push default actions

After each push on an active PR:

```bash
gh pr checks --watch --fail-fast || gh pr checks
gh pr view --json mergeStateStatus,mergeable,reviewDecision,statusCheckRollup
```

Then:

- If no CodeRabbit activity exists, request once: `@coderabbitai review`
- If CodeRabbit is paused, request resume: `@coderabbitai resume`
- Run AI-gate wait helper (repo-local first, fallback to global):

```bash
python3 scripts/review_checks/await_ai_review.py || \
python3 "${OPENCODE_HOME:-$HOME/.config/opencode}/scripts/review_checks/await_ai_review.py"
```

When PR is mergeable and required checks/reviews are satisfied, enable auto-merge:

```bash
gh pr merge --auto
```

Do not use `--admin` unless explicitly instructed.
