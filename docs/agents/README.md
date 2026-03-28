# Subagent Packs Catalog (`agent/*.md`)

This repository ships role-specific **subagent prompt packs** under `agent/*.md`.
Applicability: **LLM agents only** (primary + subagents).

## How to use

Subagent names match filenames (without `.md`). Example:

```text
Task(description="Implement a focused change", subagent_type="python-expert", prompt="<your task>")
```

> Note: AppleDouble files like `agent/._*.md` are ignored (do not use as `subagent_type`).

## Skills / Subagents / MCP 역할

- 역할/우선순위/비대화형 원칙은 `docs/engineering/skills-subagents-mcp.md`를 따른다.

## Requested role mapping (2026-02-19)

| Requested role | subagent_type | Notes |
|---|---|---|
| Python 전문가 | `python-expert` | Python implementation/tooling specialist |
| NodeJS 전문가 | `nodejs-expert` | Node runtime + npm tooling |
| Java 전문가 | `java-expert` | JVM/Gradle/Maven |
| Vite 전문가 | `vite-expert` | Vite config/plugin/build/DX |
| Figma 전문가 | `figma-expert` | Figma handoff/tokens (best-effort MCP) |
| Git 전문가 | `git-expert` | Non-destructive Git workflows |
| UX 전문가 | `ux-ui` | Existing pack already covers UX + UI specs |
| UI 전문가 | `web-design-expert` (or `web-publisher`) | Visual design vs markup/a11y |
| UAT 전문가 | `qa-engineer` | UAT + release readiness go/no-go |
| 웹 디자인 전문가 | `web-design-expert` | Delegates to `ux-ui` / `web-publisher` as needed |
| 보안 전문가 | `security-expert` | Review-first appsec guidance |
| DevSecOps 전문가 | `devsecops-expert` | CI/CD + supply chain gates |
| 프로젝트 일정 관리 전문가 | `project-manager` | Existing PM pack explicitly includes schedule mgmt |
| 프로덕트 품질 관리 전문가 | `qa-engineer` | Product quality mgmt + release readiness |

## Mechanical gates (recommended)

These checks make “agent packs stay consistent” mechanically enforceable:

```bash
python3 scripts/prompt_checks/validate_agent_packs.py --root .
python3 scripts/prompt_checks/validate_subagent_policy.py --root .
```

## Review source classification (LLM agents only)

- **Subagent review**: internal QA/quality feedback; advisory.
- **CodeRabbit review**: required automated review for PRs when present.
- **Human review**: disallowed by default unless explicitly requested.

## Subagent todo update routing (LLM agents only)

- Subagents must **not** call TodoWrite.
- Subagents request the primary agent to update todos with exact status changes.

## Task allocation + background dispatch

- Decompose tasks **MECE** (no overlap, no gaps).
- Background subagent dispatch is allowed; the primary should continue orchestration.

---

## Core execution / review / testing

| subagent_type | When to use (1 line) |
|---|---|
| `general` | Small-to-medium repo changes (config/docs/scripts); minimal diffs + evidence table. |
| `review` | Reviewer-only quality/best-practice feedback; no file edits. |
| `unit-test` | Unit test strategy/fixtures/mocks and coverage-focused improvements. |
| `qa-engineer` | UAT + regression verification, reproducible bug reports, release readiness go/no-go. |
| `system-admin` | OS/network/permissions/CI troubleshooting with secure defaults. |
| `docs-writer` | Write/update documentation with repo conventions. |
| `pr-drafter` | Draft GitHub PR description/body from branch changes/commits. |
| `commit-drafter` | Draft a commit message based on staged changes. |
| `git-conflict-resolver` | Resolve Git conflicts end-to-end (non-interactive). |

## Product / design / publishing

| subagent_type | When to use (1 line) |
|---|---|
| `product-manager` | Requirements, acceptance criteria, scope and release planning. |
| `project-manager` | Delivery plan + **schedule management**, sequencing, risks, coordination. |
| `ux-ui` | IA/flows/usability/UI specs and UX heuristics review. |
| `web-publisher` | Semantic HTML/CSS, responsive layout, accessibility (WCAG). |
| `web-design-expert` | Visual design quality (typography/spacing/colors) + design system tokens. |
| `figma-expert` | Figma handoff, components/variants, tokenization, design-to-code constraints. |

### PM-led artifacts and gates (repo defaults)

- Acceptance criteria (mandatory defaults):
  - `docs/engineering/acceptance-criteria.md`
- One-day delivery plan template:
  - `docs/workflow/one-day-delivery-plan.md`
- Templates (PRD/TRD/UML):
  - `docs/templates/PRD_TEMPLATE.md`
  - `docs/templates/TRD_TEMPLATE.md`
  - `docs/templates/UML_TEMPLATE.puml`

## Language / runtime / tool specialists

| subagent_type | When to use (1 line) |
|---|---|
| `python-expert` | Python code/tooling (typing/async/packaging) with minimal diffs. |
| `nodejs-expert` | Node.js runtime and npm tooling changes; event-loop-safe patterns. |
| `java-expert` | Java/JVM changes (Gradle/Maven, concurrency, correctness-first). |
| `vite-expert` | Vite config/plugin/build/HMR issues and bundling/DX improvements. |
| `git-expert` | Safe Git workflows, troubleshooting, repo hygiene (non-destructive defaults). |

## Data / analytics / databases

| subagent_type | When to use (1 line) |
|---|---|
| `postgresql-expert` | Application-facing Postgres SQL/ORM patterns and correctness. |
| `postgresql-dba` | Postgres schema/perf/ops (indexes, constraints, query plans). |
| `erd-expert` | Data modeling and ERD/DDL design (constraints, indexes). |
| `snowflake-expert` | Snowflake SQL/warehousing roles/performance/cost guidance. |

## Security / compliance / governance

| subagent_type | When to use (1 line) |
|---|---|
| `security-expert` | Secure coding/threat modeling/appsec reviews + actionable remediations. |
| `devsecops-expert` | CI/CD + SAST/SCA + supply chain security and release gates. |
| `cloud-safe-security` | Cloud-safe OS hardening + security response memo. |
| `grc-expert` | Governance, risk, compliance planning and control mapping. |
| `standards-expert` | ISO/IEC/IETF/W3C/NIST mapping and standards alignment. |
| `config-auditor` | Audit OpenCode config for correctness/security. |

### Workflow failure routing

| Workflow signal | Skill route | Subagent route | First command |
|---|---|---|---|
| OSV Scanner fails on PR | `pr-gates-evidence`, `lint-by-filetype` | `devsecops-expert`, `system-admin`, `qa-engineer` | `gh pr checks --watch --fail-fast` (or `gh pr checks`) |

## Research / search / specs

| subagent_type | When to use (1 line) |
|---|---|
| `search-expert` | Query crafting + fast source triage for web/repo research. |
| `researcher` | Desk research with citations for decisions/policies. |
| `prd-expert` | PRD creation/review (requirements framing). |
| `trd-expert` | TRD creation/review (technical requirements). |

## Branding

| subagent_type | When to use (1 line) |
|---|---|
| `branding-expert` | Names/slugs/branch naming + trademark risk scan (required when naming). |

### Git worktrees (clarification)
- Worktrees are optional; use them only when a workflow explicitly requires it.
- No auto-creation is assumed. If a workflow mandates worktrees, follow the relevant skill/workflow; otherwise operate in the current repo/workspace.
- After switching worktrees, re-check the active repo root:
  - `pwd`
  - `git rev-parse --show-toplevel`
- Avoid hardcoded paths for tooling; use `OPENCODE_HOME` (fallback to
  `$HOME/.config/opencode`) for `PYTHONPATH` when needed.
