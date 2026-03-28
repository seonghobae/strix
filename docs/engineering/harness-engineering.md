# Harness engineering (agents/subagents)

Harness engineering is the practice of improving the **environment around an
agent**—docs, tooling, checks, and observability—so the agent can do reliable
work without relying on “try harder” prompting.
Applicability: **LLM agents only** (primary + subagents).

Non-interactive rule: do not ask for confirmation/permission or offer opt-in
actions (e.g., “원하시면/필요하면/가능하면/필요 시/가능 시”). Proceed under safe
defaults or use **`BLOCKED`** when unsafe.

In this repo, it means turning repeated manual steps and fuzzy policies into
**legible artifacts + mechanical gates**.

> Prompts should remain a **map**, not a wall of policy. Put durable rules here
> in `docs/` and keep prompts short, linking to this doc as needed.

## Triggers (apply harness engineering when…)

Apply harness engineering **by default** when any of these show up:

- You (or a subagent) repeat the same manual step **twice**.
- A failure response is trending toward “try again / be careful / think harder”.
- Critical context exists only in chat and will not be visible to future agents.
- Verification is unclear or not reproducible (no copy/pasteable “done” proof).
- Consistency is enforced by human memory instead of checks (lint/tests/scripts).
- Debugging lacks “eyes” (no logs/metrics/smoke/diff-based evidence).

## The 5 principles → actionable steps

### 1) If it’s not visible to the agent, it doesn’t exist

- Move decisions/constraints from chat into repo artifacts:
  - `docs/…` (searchable, linkable)
  - `ARCHITECTURE.md` (repo map, when applicable)
  - `scripts/…` (repro/verification helpers)
- Prefer copy/pasteable commands + expected outputs.

### 2) Replace “try harder” with “what capability is missing?”

When something fails, treat it as a harness gap:

- Missing repro → add a minimal reproducer command/script.
- Missing verification → add a check that fails fast.
- Missing context → add a doc section with exact steps.

### 3) Turn invariants into mechanical gates

Documentation alone drifts. Prefer checks that fail:

- Linters/typecheckers/tests
- Prompt/pack validation
- Smoke tests (dockerized when available)

### 4) Give the agent “eyes” (observability + feedback loops)

- Prefer evidence from deterministic commands and artifacts (logs/snapshots).
- Keep raw evidence in PR comments; keep PR bodies concise per template.

### 5) Keep prompts short (map, not 1,000 pages)

- Prompts/packs should link to docs for detailed rules.
- Avoid duplicating long policy text across multiple prompts.

## Repo defaults (already available)

- Agent pack checks:
  - `python3 scripts/prompt_checks/validate_agent_packs.py --root .`
  - `python3 scripts/prompt_checks/validate_subagent_policy.py --root .`
- No-question policy gate (non-interactive):
  - `python3 scripts/prompt_checks/validate_no_questions_policy.py --root .`
  - `opencode.jsonc` must keep `permission.question = "deny"`.
- Repo tree recursion gate (large repos):
  - `python3 scripts/analysis/scan_repo_tree.py --root . --output docs/analysis/repo-structure.md --check`
- Filetype-based lint (best-effort):
  - `PYTHONPATH="$(git rev-parse --show-toplevel)" python3 -m scripts.lint_by_filetype --json`

## PR continuity join timing (agent workflow)

To avoid duplicate PRs, join continuity **before** creating a new PR and again
before requesting review:

- After commit + push: run PR continuity to find canonical PRs.
  - `PYTHONPATH="${OPENCODE_HOME:-$HOME/.config/opencode}" python3 -m scripts.pr_continuity --json`
- If an existing PR is found, update that PR instead of creating a new one.
- If **no canonical PR** is found, create one (non-interactive):
  - `python3 scripts/workflow/ensure_pr.py`
- Re-run the continuity check before requesting reviews to confirm the PR is
  still canonical.

## Example: consolidate repeated checks into a single quickcheck

If you find yourself repeating “prompt checks + lint-by-filetype” across tasks,
prefer a single, fail-fast entrypoint.

This repo includes:

```bash
scripts/harness/quickcheck.sh
```

Run it from a repo worktree:

```bash
./scripts/harness/quickcheck.sh
```

Notes:
- Default mode is **non-destructive** (runs `lint_by_filetype` in `--dry-run`).
- To run full lint in quickcheck:
  - `OPENCODE_QUICKCHECK_FULL=1 ./scripts/harness/quickcheck.sh`

## Reference

- Tony Lee, “OpenAI harness engineering 5 principles (Codex)”
  - https://tonylee.im/ko/blog/openai-harness-engineering-five-principles-codex/
- Design: [No-question harness + PR continuity join timing](../plans/2026-02-24-no-questions-harness-design.md)
