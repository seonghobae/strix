# Deploy / release runbook

## Scope

This repository currently automates:

1. CI validation (`.github/workflows/strix.yml`)
2. Release artifact builds (`.github/workflows/build-release.yml`)
3. SARIF workflow validation (`.github/workflows/test-sarif.yml`)

It does **not** include production infrastructure deployment manifests (compose/k8s/terraform) in-repo.

## Preflight

```bash
gh auth status
poetry install --with dev
make check-all
poetry run pytest tests/ -q --no-header --no-cov
docker info
```

## Release procedure (tag-driven)

### 1) Confirm version

```bash
poetry version -s
```

### 2) Create and push release tag

```bash
VERSION="$(poetry version -s)"
git tag "v${VERSION}"
git push origin "v${VERSION}"
```

### 3) Track build/release workflow

```bash
gh run list --workflow "Build & Release" --limit 5
RUN_ID="$(gh run list --workflow "Build & Release" --limit 1 --json databaseId -q '.[0].databaseId')"
gh run watch "$RUN_ID"
```

### 4) Verify release assets

```bash
gh release view "v${VERSION}" --json url,assets
```

## Runtime smoke checks

```bash
poetry run strix --version
poetry run strix --help
```

Optional non-interactive smoke (requires `STRIX_LLM` and `LLM_API_KEY`):

```bash
poetry run strix -n --target ./ --scan-mode quick
```

## Rollback policy

Default rollback is forward-fix:

1. Fix on main
2. Bump patch version
3. Publish new tag

Avoid force-push/tag rewrite unless explicitly approved by maintainers.
