# One-day delivery plan (template)

> Intended owner: **`project-manager`** (schedule/risk) + **`product-manager`**
> (scope/PRD/acceptance).
Applicability: **LLM agents only** (primary + subagents).

## 0) Context

- **Customer / user**:
- **Goal (one sentence)**:
- **Non-goals**:
- **Assumptions**:

## 1) Required artifacts (PM-led)

- PRD: `docs/templates/PRD_TEMPLATE.md`
- TRD: `docs/templates/TRD_TEMPLATE.md`
- UML: `docs/templates/UML_TEMPLATE.puml`

**Artifact location (choose one and be consistent):**

- [ ] Store artifacts in-repo under `docs/` (recommended for agent legibility)
  - Paths:
    - PRD:
    - TRD:
    - UML:
- [ ] Store artifacts in PR attachments/external docs
  - Links:

## 2) Acceptance criteria to enforce

Follow: `docs/engineering/acceptance-criteria.md`.

## 3) Timeline (timeboxed)

Adjust times to your timezone; keep the total within one workday.

### Phase A — Align (60–90 min)

- [ ] Finalize PRD (scope, AC, success metrics)
- [ ] Confirm risks + out-of-scope items

### Phase B — Design (60–90 min)

- [ ] TRD (architecture, interfaces, data contracts)
- [ ] UML sketch (at least one diagram)

### Phase C — Implementation (3–4 hours)

- [ ] Subagent tasks (small diffs)
- [ ] Integration by primary agent

### Phase D — Verification + hardening (2–3 hours)

- [ ] Run all mechanical gates (below)
- [ ] Fix failures until **0 warnings / 0 deprecated / 100% gates**
- [ ] Security verification (below)

### Phase E — Release readiness (30–60 min)

- [ ] Customer-ready checklist (docs, migration notes, rollback)
- [ ] PR workflow (default): ensure PR exists (existing PR first; create if missing unless explicitly disabled), request only CodeRabbit review, post evidence in PR comments, run required checks watcher, enable auto-merge after approval + mergeable + required checks + AI review gate
  - If PR continuity finds no canonical PR: `python3 scripts/workflow/ensure_pr.py`
- [ ] Final summary + evidence links

## 4) Mechanical gates (must be explicit)

Copy/paste the exact commands that will be executed for this repo.

### Quality gates

- [ ] Tests
  - Command:
  - Expected: PASS

- [ ] Coverage 100%
  - Command:
  - Expected: `--fail-under=100` (or equivalent)

- [ ] Docstrings 100%
  - Command/tool:
  - Expected: 100%

- [ ] Warning count = 0
  - Command/settings:
  - Expected: no warnings

- [ ] Deprecated API usage = 0
  - Command/settings:
  - Expected: no deprecations

- [ ] Typecheck
  - Command:
  - Expected: PASS

- [ ] Lint-by-filetype
  - Command/tool:
  - Expected: PASS

- [ ] Non-blocking verification (if web request path exists)
  - Evidence: request returns promptly; no request-path waits on queue/IO

- [ ] Queue + backpressure verification (if background work exists)
  - Evidence: bounded queue behavior when full (fast fail / 429 / 503)

### Security gates

- [ ] If API surface changed: apply `docs/security/api-security-checklist.md`
  - Evidence (tests/checks):

- [ ] SCA/SAST path appropriate to stack (prefer existing CI)
  - Commands:
  - Expected: clean / within policy

### PR merge-gate evidence (when PR exists)

> Keep raw output in PR comments as evidence.

- If `gh` is missing or `gh auth status` fails, treat PR evidence collection as **BLOCKED** and record the exact commands needed to authenticate.

- [ ] Auth check (precondition)
  - `gh auth status`

- [ ] Set PR context vars (needed for `gh api` calls below)
  - `PR_NUMBER="$(gh pr view --json number -q .number)"`
  - `OWNER_REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"`
  - `OWNER="${OWNER_REPO%%/*}"; REPO="${OWNER_REPO#*/}"`
  - `echo "$OWNER/$REPO#$PR_NUMBER"`

- [ ] Required checks
  - `gh pr checks --watch --fail-fast`
  - If unsupported by the installed `gh`, use: `gh pr checks`
- [ ] Merge state
  - `gh pr view --json mergeStateStatus,mergeable`

- [ ] OSV scanner run + code-scanning evidence
  - `gh run list --workflow "OSV Scanner" --event pull_request --limit 5`
  - `gh api "/repos/$OWNER/$REPO/actions/workflows/osv-scanner.yml/runs?event=pull_request&status=completed&per_page=5"`
  - `gh api "/repos/$OWNER/$REPO/code-scanning/analyses?pr=$PR_NUMBER&tool_name=osv-scanner"`
  - `gh api "/repos/$OWNER/$REPO/code-scanning/alerts?pr=$PR_NUMBER&state=open&tool_name=osv-scanner"`
  - If `vars.OSV_UPLOAD_SARIF` is not set to `true`, SARIF upload is intentionally disabled; a `403` on the two code-scanning API calls is expected and OSV workflow logs/results are the primary evidence.

- [ ] GHCR publish + Trivy scan (GitHub Actions only)
  - GHCR/Trivy 워크플로가 활성화된 경우에만 아래 명령을 사용하고, 비활성 상태면 "not enabled"으로 기록한다.
  - `gh run list --workflow "GHCR" --event pull_request --limit 5`
  - `gh run list --workflow "Trivy" --event pull_request --limit 5`
  - Do **not** `docker login ghcr.io` or install Trivy locally; use workflow evidence.

- [ ] Review inventory (before requesting a new review)
  - `gh pr view --json reviewDecision,comments,reviews --jq '{reviewDecision,comments:(.comments|length),reviews:(.reviews|length)}'`
  - `gh api --paginate "/repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews"`
  - `gh api --paginate "/repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments"`
  - `gh api --paginate "/repos/$OWNER/$REPO/issues/$PR_NUMBER/comments"`
  - Expected: existing `CHANGES_REQUESTED` items are either fixed or explicitly
    resolved with evidence before re-requesting `@coderabbitai review`.

- [ ] If no CodeRabbit activity detected, request review once
  - `gh pr comment "$PR_NUMBER" --body "@coderabbitai review"`

- [ ] Walkthrough sync (if present)
  - Detect `<!-- walkthrough_start -->`...`<!-- walkthrough_end -->` in CodeRabbit
    issue comments, then update PR body with a `coderabbit_walkthrough` section.
  - If CodeRabbit review body includes “Prompt for all review comments with AI agents”,
    treat it as actionable review guidance (apply after verification).

- [ ] If CodeRabbit review is paused, resume
  - `gh pr comment "$PR_NUMBER" --body "@coderabbitai resume"`

- [ ] AI review wait/apply gate (no confirmation)
  - `python3 scripts/review_checks/await_ai_review.py` (repo-local) or `python3 "${OPENCODE_HOME:-$HOME/.config/opencode}/scripts/review_checks/await_ai_review.py"` when the repo lacks the script
  - Expected: waits up to **10 minutes**; if CodeRabbit appears and is pending,
    it waits; if none appears after 10 minutes, treat as absent and continue;
    after approval, recheck for 10 minutes to catch late AI comments; exits
    non-zero on CHANGES_REQUESTED/failed.

- [ ] Auto-merge on approval (GitHub)
  - `gh pr merge --auto`
  - Expected: auto-merge enabled only after approval + mergeable + required checks + AI review gate; merge queue 존중; do not use `--admin` unless explicitly instructed.

### GitLab CLI (glab) equivalents (if repo is on GitLab)

- Auth: `glab auth login` (or `GITLAB_TOKEN=... glab auth login --stdin`)
- MR context:
  - `MR_NUMBER="$(glab mr view -F json | jq -r .iid)"`
- Required checks / pipelines:
  - `glab ci status`
- Merge state:
  - `glab mr view "$MR_NUMBER" -F json | jq '{state: .state, detailed_merge_status: .detailed_merge_status}'`
- Review inventory:
  - `glab mr approvals "$MR_NUMBER"`
  - `glab mr view "$MR_NUMBER" -F json | jq .discussions`

### Trigger matrix (workflow signal -> route)

| Workflow signal | Skill route | Subagent route |
|---|---|---|
| OSV Scanner fails on PR | `pr-gates-evidence`, `lint-by-filetype` | `devsecops-expert`, `system-admin`, `qa-engineer` |
| Required checks fail/pending | `pr-gates-evidence` | `qa-engineer`, `devsecops-expert` |
| Code-scanning evidence missing/incomplete | `pr-gates-evidence` | `devsecops-expert` |

## 5) Delivery outputs

- [ ] PR body is concise; evidence is in PR comments (commands + raw outputs)
- [ ] No human reviewers are requested; only CodeRabbit review is requested
- [ ] Change log / release notes (if applicable)
- [ ] Operational notes (timeouts, backpressure, queue semantics)

### Customer-ready (minimum definition)

- [ ] Install/run instructions are present (README or runbook)
- [ ] Rollback plan is documented (explicit steps)
- [ ] Security verification evidence is recorded

## 6) BLOCKED / exceptions

If any mandatory gate cannot be met, record it here and stop:

- **What is blocked**:
- **Evidence** (commands/output):
- **Proposed scope change**:
- **Exception request** (exact paths + risk + follow-up):
