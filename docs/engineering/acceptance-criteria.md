# Engineering acceptance criteria

This repository treats the acceptance criteria (AC) below as the **default** for
agent-led development work. These criteria target **agent behavior** (primary
agent and subagents) and are **not requirements for human engineers**.
Applicability: **LLM agents only** (primary + subagents).

Prompts should remain a "map" (not a wall of policy). Keep detailed policy here
and reference it from `prompts/build.txt` and `prompts/plan.txt`.

See also (harness engineering):
- [Harness Engineering](harness-engineering.md)

## Ownership / roles

- **Primary agent**: orchestrates (planning, delegation, integration, summary).
- **Subagents**: implement focused changes + gather verification evidence.
- **PRD/TRD/UML + development leadership**: led by **`product-manager`** and
  **`project-manager`** using `docs/templates/*`.

## Review source classification (LLM agents only)

- **Subagent review**: internal quality/verification feedback; advisory.
- **CodeRabbit review**: required automated review for PRs when present.
- **Human review**: disallowed by default unless the user explicitly requests.

## Subagent todo update routing (LLM agents only)

- Subagents **must not** call TodoWrite.
- Subagents request the primary agent to update todos with exact status changes.

## Autonomy default (do not wait for permission)

- Unless the user explicitly says "don't do X", the default is to **continue to
  completion** (execute the todo list, create evidence, commit/push when
  applicable).
- For delivery work, unless explicitly disabled, the default after **commit + push** is to:
  - check PR continuity (existing PR first),
  - create/update a PR (respect PR template),
  - inventory existing PR reviews/comments (avoid duplicate review requests;
    address CHANGES_REQUESTED items first),
  - if no CodeRabbit activity is detected, request `@coderabbitai review` once,
  - if CodeRabbit is **paused**, request `@coderabbitai resume` (avoid duplicate
    `@coderabbitai review` when auto reviews are active),
  - if CodeRabbit posts a **Walkthrough** in comments, sync that section into
    the PR body (idempotent marker replacement),
  - if CodeRabbit review body includes “Prompt for all review comments with AI agents”,
    treat the embedded prompt as **actionable review guidance** for remediation,
  - if the PR updates a git submodule pointer, add verification evidence in the
    PR body: upstream compare URL (old...new) and an explicit list of files
    changed between those submodule commits,
  - if AI review is pending or CHANGES_REQUESTED, **wait and apply** without
    confirmation (repo-local `python3 scripts/review_checks/await_ai_review.py`, or fallback to `python3 "${OPENCODE_HOME:-$HOME/.config/opencode}/scripts/review_checks/await_ai_review.py"` when the repo lacks the script),
    - waits up to **10 minutes**; if no CodeRabbit review appears, treat as
      **absent** and continue; after approval, wait **10 minutes** more to
      catch late reviews,
  - request **only** `@coderabbitai` review (no human reviewers),
  - post evidence to PR **comments** (not the body), and
  - run required checks watcher: `gh pr checks --watch --fail-fast`.
    - If unsupported by the installed `gh`, use: `gh pr checks`.
  - PR 승인 + mergeable + required checks + AI review gate 통과 시 `gh pr merge --auto`로 자동 병합을 활성화한다(merge queue 존중). `--admin`은 명시 요청 없이는 사용 금지.

### GitLab CLI (glab) equivalents

If the repo is hosted on GitLab, use **glab** instead of gh:

- Auth: `glab auth login` (or `GITLAB_TOKEN=... glab auth login --stdin`)
- MR create: `glab mr create`
- MR view: `glab mr view <MR_NUMBER>`
- MR list: `glab mr list`
- MR comments: `glab mr comment <MR_NUMBER> --message "..."`
- Pipeline status: `glab ci status`
- API access: `glab api` for MR/pipeline queries
  - If `glab auth status` fails (missing/unauthenticated `glab`), mark **`BLOCKED`** and provide non-interactive auth steps.
- Avoid language that stops progress (e.g., "원하시면 …").
- Do not request confirmation or opt-in actions (e.g., "원하시면/필요하면/가능하면").
- Prefer **updating the Todo list** as the primary status mechanism.
  - Avoid user-facing progress narration unless needed for **`BLOCKED`**, a required **decision**, or sharing **evidence**.
  - User-facing output must avoid “next steps” narration; limit to evidence, decisions, or **`BLOCKED`**.
- Decompose work into **MECE** tasks and allow background subagent dispatch where safe.
- Only stop when it is genuinely unsafe or impossible to proceed. In that case,
  use **`BLOCKED`** with commands attempted + why + next non-interactive action.

## Mandatory acceptance criteria (default)

1) **100% test coverage** (project-defined scope; no "best effort" by default).
2) **100% docstrings** for new/modified public code.
3) **Non-blocking web** as the default.
    - **Python web**: **ASGI required**.
    - **Prefer Hypercorn** for native ASGI.
    - **If not Hypercorn** (e.g., Uvicorn/Gunicorn/WSGI), treat this as a
      **required change** unless an explicit exception is approved.
    - **Java web**: prefer a reactive/non-blocking stack over Servlet.
      - Examples: Spring WebFlux (Netty), Vert.x, Quarkus reactive.
4) **Lightweight event queue** (bounded + backpressure; no request-path waits)
   **when background/long-running work exists**.
5) **0 warnings** (tests/build/lint must run clean).
6) **0 deprecated APIs** used in touched code.
7) **1-day delivery schedule** is required for software delivery tasks and must
   include explicit security verification, aiming for customer-ready software.
8) **TDD + DDD 동시 적용**: 테스트 우선(TDD)과 도메인 모델/유비쿼터스 언어 정렬(DDD)을 기본값으로 적용한다.
9) **Autocommit/autopush + PR continuity**: repo가 있으면 변경 산출물은 기본적으로 commit+push까지 완료하고, push 후에는 PR continuity를 실행해 canonical PR에 연결한다(기존 PR 우선). canonical PR이 없으면 **새 PR을 생성**한다(예: `python3 scripts/workflow/ensure_pr.py`). 리뷰를 임의로 dismiss 하지 않는다.
10) **Sequential-thinking 사용**: 모든 변경 작업은 순차적 사고 단계를 명시하고, 체크리스트/단계화로 검증한다.
11) **ARCHITECTURE.md 상시 갱신**: 구조/동작 변경이 있으면 해당 문서를 업데이트하고 날짜를 갱신한다.
12) **AGENTS.md 상시 갱신**: 에이전트 지침/규칙 변경 시 AGENTS.md를 업데이트한다(https://agents.md/).
13) **Git init vs clone 구분**: 실제 repo 히스토리가 필요한 작업(예: PR/리뷰/충돌)은 clone을 기본값으로 하고, 산출물만 남기는 작업은 전용 workbench에서 `git init`을 허용한다.
14) **TodoWrite 상시 갱신**: 3단계 이상 작업은 TodoWrite로 계획/상태를 관리한다.
15) **ASSUMPTION 근거 필수**: 가정은 근거(레포/문서/로그/웹 검색)로만 허용하고, 근거가 없으면 `BLOCKED`로 처리한다.
16) **Reformatting 허용**: 포맷터/린터 요구로 발생한 reformatting-only 변경은 유효하다. reformatting을 이유로 변경을 무효 처리하지 않는다.
17) **Memory MCP 사용**: 반복/지속되는 사용자 선호, 정책, 결정, 환경 정보는 memory에 기록하고 재사용한다(기억 소실 방지).
18) **Subagent git 충돌 방지**: subagent는 다른 subagent의 변경을 `git checkout`/`git reset`으로 되돌리거나, 본인 변경이 아니라는 이유로 `git add`를 취소하지 않는다. 변경 충돌은 primary agent가 조정한다.
19) **실행 방식 선택 금지**: 실행 옵션을 사용자에게 묻지 않는다. 기본값은 현재 세션 subagent-driven이며, 긴 실행/리스크 격리가 필요하면 executing-plans 새 세션을 사용한다.
20) **장시간 명령 분할**: 120초 초과가 예상되는 작업은 짧은 단계로 분할하거나 도구 timeout을 명시한다(긴 단일 bash 체인 금지).
21) **진행 선언 금지**: “진행하겠다/바로 처리” 등 실행 선언 문구를 출력하지 않는다. 증적만 기록한다.
22) **GHCR/Trivy는 Actions**: GHCR 배포 및 Trivy 스캔은 GitHub Actions 경로로 수행/증거를 남긴다. 직접 GHCR 로그인/로컬 Trivy 설치는 금지.
23) **Evidence 최소화**: 사용자 출력의 evidence는 명령 + 핵심 결과 1–2줄로 제한한다(대형 덤프 금지).
24) **작업 예정/계획 문구 금지**: “해야 할 작업/다음 작업/예정” 등의 계획성 문구를 출력하지 않는다.

## Functional baseline first (security-by-design)

- **Security by design is required**, and core functionality must still work.
- If security hardening conflicts with critical-path behavior, keep the core
  behavior working first.
- Then apply the **minimum safe controls** that do not break the critical path,
  and record follow-up hardening as explicit tasks/risks.
- Functional-first does not permit removing mandatory security controls
  (authentication/authorization, secret protection, auditability).
- Avoid controls that destroy required query/operator semantics.
  - Example: do not encrypt `pgvector` embedding values in a way that breaks
    similarity operators/index usage for retrieval.
  - Prefer controls that preserve behavior first (access control, audit,
    key/secret hygiene, at-rest encryption).
- Mechanical verification intent:
  - critical-path smoke/tests must pass before claiming completion,
  - otherwise mark the work as **`BLOCKED`** with evidence and follow-up plan.

## Optional guidance

- **Client DB pooler support** when a DB is used (e.g., PgBouncer/PgCat).
- **Target PostgreSQL 17** when PostgreSQL version decisions are needed.

## Mechanical gates (typical)

Prefer repo-provided commands (Makefile / package scripts / CI targets). If
missing, use safe defaults like the examples below, **but attempt evidence first** (repo/docs/env/logs → MCP search/webfetch). If no evidence exists, use `BLOCKED` (avoid unproven `ASSUMPTION`).
- **Python/uv 기본값**:
  - 테스트/실행은 `uv run <cmd>` 형식을 기본값으로 사용한다(예: `uv run pytest`).
  - 의존성 추가는 `uv add`/`uv add --dev`를 우선한다. `uv pip`는 예외 시에만 사용하고 근거를 기록한다.
  - 보안 스캔/린트 도구도 `uv run`을 우선한다(예: `uv run pip-audit`).

### Harness engineering (default behavior)

When you (or a subagent) repeat a manual step, lack reproducible verification,
or drift toward “try harder” prompting, treat it as a harness gap.

Reference: [Harness Engineering](harness-engineering.md).

### Cross-cutting gates

- **Lint (filetype-based)**
  - Preferred:
    ```bash
    PYTHONPATH="${OPENCODE_HOME:-$HOME/.config/opencode}" \
      python3 -m scripts.lint_by_filetype --json
    ```
  - Or via MCP tool:
    `functions.lint_by_filetype(dryRun=false, json=true)`.

- **Typecheck**: run the repo's typecheck script, or language defaults.
- **Warnings = 0**: configure tests/build to fail on warnings where possible.
- **Deprecated APIs = 0**: treat deprecations as failures where possible.

### Default scope definitions (to avoid loopholes)

- **Coverage 100% (default scope)**: all production code under `src/` (or the
  main package/module directory), excluding tests and generated code.
- **Docstrings 100% (default scope)**: all production code under `src/` (or the
  main package/module directory), excluding tests and generated code.

If a repo uses a different layout, record the exact scope paths in the plan.

### Python (example gates)

```bash
# Tests + strict warnings
uv run pytest -q -W error

# Coverage gate
uv run pytest -q -W error \
  --cov=<package_or_src_path> --cov-report=term-missing --cov-fail-under=100

# Docstrings gate (example; pick one tool and enforce it)
uv add --dev interrogate
uv run interrogate -vv --fail-under 100 --exclude "tests" src

# Type checking (pick the repo's tool)
uv run pyright
# or
uv run mypy .
```

### JS/TS (example gates)

```bash
npm test
npm run lint
npm run typecheck   # or: npx -y tsc --noEmit
```

### Web runtime (non-blocking) gate

If a task introduces or modifies a web server, ensure the plan includes:

- request-path non-blocking I/O (no sync DB/HTTP in the event loop),
- bounded concurrency/backpressure,
- an ASGI stack for Python,
- **Hypercorn** as the default server.

For Java, default to a reactive/non-blocking server/runtime rather than a
Servlet container, unless the task explicitly requires Servlet compatibility.

### Deprecations gate (examples)

Pick a stack-appropriate *mechanical* definition of "Deprecated = 0" and fail on
it.

- Python: treat deprecations as errors in the relevant scope.
  - Example (strict, may need filtering to avoid third-party noise):
    ```bash
uv run pytest -q -W error::DeprecationWarning -W error::PendingDeprecationWarning
    ```
- Java: enable deprecation linting and fail builds on warnings (where feasible).
  - Example (javac): `-Xlint:deprecation -Werror`
- Node.js: treat runtime deprecations as failures for server processes.
  - Example: `node --throw-deprecation <entrypoint>`

### Security verification gate (minimum)

- If the work touches an HTTP/GraphQL API surface, apply:
  - `docs/security/api-security-checklist.md` (turn items into tests/checks).
- Run at least one SCA/SAST path appropriate to the stack (prefer existing CI).

## If 100% is impossible: explicit BLOCKED policy

If any mandatory AC cannot be met:

1) Mark the work as **`BLOCKED`** (do not claim "done" or "ready").
2) Provide **mechanical evidence** (commands + outputs or links) for why.
3) Propose **the smallest scope change** that achieves compliance within a day.
4) If an exception is required, record:
   - what is excluded (exact paths/symbols),
   - why it cannot be fixed now,
   - the risk, and
   - the follow-up plan to remove the exception.
