# AGENTS.md

## Project overview
- Repository: **Strix CLI/agent runtime** (`strix-agent`)
- Primary package: `strix/`
- CLI entrypoint: `strix.interface.main:main`
- CI/release workflows: `.github/workflows/*.yml`

## Setup commands
```bash
poetry install --with dev
make setup-dev
```

## Build / test commands
```bash
# Fast quality gates
make check-all

# CI-parity test command (Strix workflow)
poetry run pytest tests/ -q --no-header --no-cov

# SARIF-specific tests
poetry run pytest tests/test_sarif.py -v --no-cov
```

## Code style
- Keep diffs minimal and scoped to the task.
- Use repo tooling first:
  - `make format`
  - `make lint`
  - `make type-check`

## Testing instructions
- Run targeted tests first, then full suite.
- For runtime-sensitive changes, include Docker readiness evidence:
```bash
docker info
poetry run strix --version
poetry run strix --help
```

## Security considerations
- Never commit secrets/API keys.
- Only test targets you are explicitly authorized to test.
- Runtime backend default is Docker sandbox (`STRIX_RUNTIME_BACKEND=docker`).

## PR / Commit instructions
- Existing PR first (PR continuity): reuse an open PR for the same branch before creating a new one.
- Keep PR body concise; post raw gate evidence in PR comments.
- Do not dismiss existing reviews unless explicitly requested.
- If runtime/workflow/structure changes, update `ARCHITECTURE.md` in the same change.

### PR continuity quick check
```bash
gh auth status
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
ME="$(gh api user -q .login)"
gh pr list --state open --head "$ME:$BRANCH" --json number,title,url,updatedAt
```
