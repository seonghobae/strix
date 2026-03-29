# ARCHITECTURE.md

Last updated: 2026-03-29

## 1) Scope

This repository contains the **Strix CLI and agent runtime** implementation.

- Python package: `strix`
- CLI/TUI entrypoint: `strix.interface.main:main`
- Tooling/runtime abstractions for sandboxed execution
- CI workflows for tests, SARIF upload, and release artifact builds

## 2) High-level flow

```text
User or CI
  -> strix CLI / TUI (strix.interface.*)
    -> agent orchestration (strix.agents.*)
      -> tool registry and tool actions (strix.tools.*)
        -> runtime selection (strix.runtime.*)
          -> Docker sandbox runtime
```

## 3) Main subsystems

- `strix/interface/`:
  CLI/TUI UX, renderers, argument handling, and interaction orchestration.
- `strix/agents/`:
  Agent graph/state orchestration.
- `strix/tools/`:
  Tool registration, action handlers, and runtime adapters.
- `strix/runtime/`:
  Runtime abstraction and Docker runtime implementation.
- `strix/config/`:
  Runtime and provider configuration loading/validation.
- `strix/sarif.py`:
  SARIF generation and GitHub code-scanning upload support.

## 4) Runtime model

- Default runtime backend is Docker (`STRIX_RUNTIME_BACKEND=docker`).
- Sandbox tool server is ASGI-based (`FastAPI` + `uvicorn`) in sandbox mode.
- There is no repository-local production deployment stack (no compose/k8s/terraform manifests in this repo).

## 5) CI/release model

- `.github/workflows/strix.yml`
  - Runs unit tests on `push` and `pull_request` to `main`
  - Uploads SARIF on non-PR events
- `.github/workflows/test-sarif.yml`
  - Branch-specific/manual SARIF export+upload validation flow
- `.github/workflows/build-release.yml`
  - Multi-OS binary build and GitHub Release publishing on `v*` tags

## 6) Change-management rule

When runtime behavior, workflow behavior, or repository structure changes,
update this document in the same PR.
