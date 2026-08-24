# Sprint 21 — End (Headless Core + Embed SDK)

**Status (2026-08-24): CLOSED.** The application/runtime boundary and embeddable package gates
passed. The existing SPA remains a reference host and Control Tower, not a runtime dependency of
bank channels.

## Delivered product boundary

- **Headless core:** FastAPI REST/SSE, orchestrator, tool-layer brake and audit stay in
  `backend/app/`. `GET /api/ready` directly checks PostgreSQL, Alembic head, effective provider
  configuration and every role MCP mount. Exact-origin CORS is off by default.
- **Bank-DC guard:** `SHB_RUNTIME_MODE=bank_dc` rejects demo secrets/database credentials,
  insecure cookies, dev auth bypass, subscription providers and provider hosts outside the exact
  allowlist before startup or seed DB access. Provider policy is rechecked when a conversation is
  resolved. This is an application guard, not a network firewall claim.
- **Embed SDK:** `@bank-digital/embed-sdk` publishes a DOM-free headless client, React compound
  components, Shadow DOM mount/custom-element entries and a standalone IIFE. It injects cookie or
  per-request Bearer auth, uses fetch-SSE with reconnect/full-state recovery, and exposes no
  approval API/control.
- **Reference surface:** `frontend/src/` is retained for demonstration and bank operations. SDK
  entries do not import it, its mock API, Three.js, Recharts or SPA CSS/assets.

## Runtime and consumer evidence

- Live local readiness on port 8000 returned
  `{"ready":true,"profile":"demo","checks":{"database":true,"migrations":true,"provider":true,"mcp_mounts":true}}`.
- The built headless SDK authenticated with Bearer against the real backend: admin identity and
  conversation/full-state reads passed; a non-owner read was hidden as canonical `404`; the real
  fetch-SSE stream received the `ping` heartbeat.
- The standalone reference page mounted `<bank-digital-rm-copilot>` in Shadow DOM against a real
  conversation. Connection state reached `open`; no approval control or stale configuration text
  existed; browser console warnings/errors were empty.
- A fresh consumer installed the packed tarball and passed headless import without React peers,
  ESM, CommonJS/NodeNext, declarations (including the side-effect standalone entry), Vite build
  and IIFE execution in a browser global without Node `process`.
- Release artifact: **35 files / 86,298 bytes**; standalone IIFE **210.94 kB raw / 66.86 kB
  gzip**. Source, tests and SPA assets are excluded by allowlist/size gates.
- The frontend Docker image built successfully, installs with **0 npm vulnerabilities**, and
  serves the SDK under `/embed-sdk/dist/` plus its example under `/embed-sdk/examples/`.

## Verification

- Backend: **548 collected = 531 passed + 17 skipped**; Ruff passed; **138 files** format-clean.
- Frontend: **36 files / 276 passed**; typecheck, SDK typecheck, lint and production builds passed.
- SDK-focused: **7 files / 25 passed** plus packed-consumer smoke.
- Combined project tests: **807 passed + 17 skipped**, zero failures.
- Dependency scans: `pip-audit` reported **no known vulnerabilities** after locking
  `cryptography 50.0.0`; `npm audit --audit-level=moderate` reported **0 vulnerabilities**.
- `git diff --check` passed.

## Explicit non-claims / remaining integration work

- MCP is currently mounted in-process by role/common tool surface. A separate out-of-process MCP
  server per CIC/core/eKYC source has **not** been implemented.
- CIC/core use seeded/adapted repository tools; no live bank credential, source-system network
  contract or target-environment acceptance evidence is present.
- Core-banking exactly-once behavior cannot be claimed until the external adapter accepts the
  payload hash as an idempotency key, replays the same receipt and passes crash-window tests.
- `bank_dc` application fail-fast is implemented; bank infrastructure firewall/egress, SSO,
  secrets, deployment topology and data-residency evidence remain deployment acceptance gates.
- Approval/receipt ledgers are transactional, but ordinary tool-call tracing remains best-effort;
  WORM retention and a 100% audit guarantee are not delivered.

## Gate verdict

- [x] Headless runtime, brake, audit and REST/SSE boundary operate independently of the SPA.
- [x] Real SDK artifact supports headless, React, Web Component and standalone consumers.
- [x] Auth/ownership, no-approve SDK boundary, reconnect/state and malformed-input cases are tested.
- [x] Full backend/frontend suites, security scans, packed consumer, Docker and browser gates pass.
- [x] Undelivered source-system/infrastructure claims are recorded explicitly.

**Verdict:** the requested **headless core + embeddable SDK** product boundary is delivered and
Sprint 21 is closed. Live CIC/core adapters and per-source MCP processes are the next integration
package, not part of this verdict.
