# API Security Checklist (repo-local)

This is a **practical checklist** for designing, implementing, reviewing, and
releasing APIs.

## When to apply

Apply this document **only when the task touches an API surface**, e.g.

- HTTP endpoints (REST/JSON/XML)
- GraphQL schemas/resolvers
- OAuth/OIDC flows, SSO callbacks, token/session issuance
- public webhooks, inbound/outbound integrations
- API gateways, rate limiting, WAF rules, request routing

If the task does not touch an API surface (pure docs/config unrelated to APIs),
do not force this checklist.

## How to use

1. Start from the sections below and mark relevant items.
2. Convert the most critical items into **mechanically verifiable gates**:
   - tests (unit/integration)
   - lint/typecheck
   - config assertions (headers, TLS settings)
   - smoke checks (curl, Playwright, etc.)
3. In PR artifacts, record what you changed and why (file-by-file).

## Checklist

### Authentication

- [ ] Do not use `Basic Auth` for new APIs; use standard authentication.
- [ ] Do not reinvent token generation or password storage; use established
      standards/libraries.
      - Password hashing MUST use a slow password hash (KDF; key derivation
        function — intentionally expensive for password hashing) such as **Argon2id**
        (preferred), **bcrypt**, or **scrypt**.
      - Do NOT use fast hashes like **SHA-256** (even with a salt) for password
        storage.
      - See: `docs/security/password-hashing.md`.
- [ ] Use max retry / account lock / jail mechanisms for login flows.
- [ ] Encrypt sensitive data at rest and in transit.

### Access (transport, exposure, perimeter)

- [ ] Apply request throttling to reduce DDoS / brute-force impact.
- [ ] Use HTTPS with TLS 1.2+ and secure ciphers; prevent MITM.
- [ ] Ensure `Host` header matches SNI expectations (where applicable).
- [ ] Use `HSTS` to prevent SSL strip.
- [ ] Disable directory listings.
- [ ] For private APIs, restrict access to safelisted IPs/hosts.

### Authorization

#### OAuth/OIDC (when applicable)

- [ ] Validate `redirect_uri` server-side against an allowlist.
- [ ] Prefer authorization code flow; avoid implicit (`response_type=token`).
- [ ] Use a random `state` parameter to prevent CSRF.
- [ ] Define default scopes and validate requested scopes per client.

### Input (requests)

- [ ] Enforce correct HTTP methods for each resource; return `405` when invalid.
- [ ] Validate content negotiation (`Accept`) and return `406` when unsupported.
- [ ] Validate request `Content-Type` for posted data.
- [ ] Validate all user input to prevent common vulns (XSS, SQLi, RCE, etc.).
- [ ] Never put secrets in URLs (credentials/passwords/tokens/API keys). Use
      Authorization headers.
- [ ] Prefer server-side encryption (avoid client-side encryption assumptions).
- [ ] Consider an API gateway for caching + rate limit policies (quota/spike
      arrest/concurrency caps) + dynamic routing.

### Processing (server-side behavior)

- [ ] Ensure all endpoints requiring auth are actually protected.
- [ ] Avoid exposing user-owned resource IDs when possible: prefer `/me/...`
      patterns over `/user/654321/...`.
- [ ] Avoid auto-increment IDs in externally visible contexts; prefer UUIDs.
- [ ] If parsing XML, disable external entity parsing (XXE defense).
- [ ] If parsing XML/YAML or anchor-heavy formats, prevent entity expansion
      bombs ("Billion Laughs").
- [ ] Use a CDN for file uploads.
- [ ] Offload heavy work to workers/queues and return fast responses (avoid
      request-thread/event-loop blocking).
- [ ] Ensure debug mode is OFF in production.
- [ ] Use non-executable stacks where available.

### Output (responses)

- [ ] Send `X-Content-Type-Options: nosniff`.
- [ ] Send `X-Frame-Options: deny`.
- [ ] Send `Content-Security-Policy: default-src 'none'` (or a tailored CSP).
- [ ] Remove fingerprinting headers (`X-Powered-By`, `Server`, etc.).
- [ ] Force correct response `Content-Type`.
- [ ] Do not return overly specific errors that reveal implementation details;
      log details server-side.
- [ ] Do not return sensitive data (credentials/passwords/security tokens).
- [ ] Return correct status codes for each operation.

### CI & CD

- [ ] Audit design + implementation with unit/integration tests and coverage.
- [ ] Use code review (no self-approval).
- [ ] Run static/dynamic security tests continuously.
- [ ] Check dependencies (app + OS) for known vulnerabilities.
- [ ] Have a rollback plan for deployments.

### Monitoring

- [ ] Centralize logins for services/components (where applicable).
- [ ] Monitor traffic/errors/requests/responses.
- [ ] Alert via appropriate channels (Slack/Email/SMS/etc.).
- [ ] Ensure logs do not contain sensitive data (cards/passwords/PINs/etc.).
- [ ] Consider IDS/IPS for monitoring API traffic and instances.

## Advanced (apply only if relevant)

### Rate limiting & abuse prevention

- [ ] Sliding window rate limiting per API key and IP.
- [ ] Exponential backoff for repeated failed auth.
- [ ] Challenge suspicious activity (CAPTCHA / proof-of-work) when acceptable.
- [ ] Alert on unusual usage patterns (time/volume/endpoints).

### GraphQL-specific security

- [ ] Disable introspection in production when possible.
- [ ] Enforce query depth limits.
- [ ] Enforce query cost limits.
- [ ] Consider allowlisting persisted queries.

### Secrets management

- [ ] Rotate API keys/secrets regularly.
- [ ] Use secret scanning in CI/CD.
- [ ] Never commit secrets; use env vars or a secret manager.

### Zero trust architecture

- [ ] Consider mTLS for service-to-service.
- [ ] Validate internal requests like external requests.
- [ ] Prefer short-lived tokens + refresh.
- [ ] Consider request signing for sensitive operations.

## Notes: how this repo maps to the checklist

This OpenCode config repo already enforces (or strongly prefers) several items
via prompts/agents, such as:

- Avoid secrets in git; treat secret scanning/push protection as stop-the-line.
- Prefer non-blocking web stacks and avoid request-path blocking.
- Prefer UUIDs over auto-increment IDs.

This doc exists so the checklist is **visible** and can be referenced from
prompts, plans, and reviews without inflating the prompt text.

## Attribution

Based on **Shieldfy API Security Checklist** (MIT License):

- Source: https://github.com/shieldfy/API-Security-Checklist
- Original checklist: https://github.com/shieldfy/API-Security-Checklist/blob/master/README.md
- License: https://raw.githubusercontent.com/shieldfy/API-Security-Checklist/master/LICENSE
