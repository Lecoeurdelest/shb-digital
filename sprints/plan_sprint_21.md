# Sprint 21 — Headless Core + Embed SDK

**Status:** closed · **Kickoff/close:** 2026-08-24 · **Decision:** D-74 ·
**End record:** [`end_sprint_21.md`](end_sprint_21.md).

**Objective:** Make the agent runtime/brake/audit the product core and publish a real embeddable
SDK for SAHA, bank websites, RM portals and LOS. The existing SPA remains a reference host and
Control Tower; it is not an SDK dependency.

## Tasks

### T21-1 — Freeze boundary and harden the headless core

- Define readiness, SDK API, auth/CORS and data boundaries in `docs/CONTRACT.md` first.
- Add exact-origin CORS (off by default), `/api/ready`, `SHB_RUNTIME_MODE=bank_dc` fail-fast and
  MCP tool annotations without changing `orch/`/gate transaction invariants.
- Gate: readiness checks DB, migration, provider config and all role MCP mounts; insecure bank-DC
  config fails before startup/seed DB access; error remains the canonical four-field envelope.

### T21-2 — Publish `@bank-digital/embed-sdk`

- Headless entry: REST + authenticated fetch-SSE; no React/DOM/SPA import.
- React entry: injected `{state, actions, meta}` provider, compound components and explicit
  `CustomerAssistant` / `RmCopilot` variants.
- Element entry: mount API + Shadow DOM custom elements; no approval action or token attribute.
- Gate: reconnect/refetch, cancellation, out-of-order stream, conversation switch and malformed
  identity behavior have distinguishing tests.

### T21-3 — Release artifact and integration surface

- Build ESM + CommonJS + declarations and a browser IIFE; exclude SPA public assets/source/tests.
- Add a minimal standalone reference host, nginx artifact path, integration guide and bank-DC
  deployment checklist.
- Gate: pack and install the tarball into a fresh consumer; typecheck/build ESM/CJS/React; execute
  the packed IIFE in a browser global with no Node `process`; enforce file and size allowlists.

### T21-4 — Independent acceptance gate

- Run full backend pytest/ruff and frontend vitest/typecheck/lint/build/consumer smoke.
- Exercise `/api/ready`, authenticated SDK REST and SSE ownership against the real local backend;
  visually inspect the standalone Shadow DOM host without relying on the reference SPA.
- Record exact counts and limitations. Separate source-system MCP processes, live CIC/core
  credentials, infrastructure firewall and WORM audit remain explicit non-claims until delivered.
