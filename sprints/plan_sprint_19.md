# Sprint 19 — Plan

<!-- LIVING RULE (read before editing): task-id: T19-<n>. Plan is the single source of truth;
     kickoff EDITS IN-PLACE + APPENDS Kickoff section at bottom. -->

**Objective:** Deliver step 1 of the headless/thin-client model: data-minimized
approval-pending and approval-decided notifications to a bank chat channel, each deep-linking to
the exact approval in Control Tower. External chat is a doorbell only under D-71—never a credit
data pipeline and never an approval surface. Embed SDK and the broader Tower upgrade remain later
work.

**Theme:** DOORBELL — outbound notification adapter + exact-ticket deep-link.

**Baseline test count:** at least the count locked in `end_sprint_18.md`.

---

## Tasks (4, execute in dependency order)

### T19-1 — Outbound webhook adapter (bank-side, best effort)

- **Assignee:** be.
- **Contract-first:** Before implementation, add the generic and Lark outbound payload shapes,
  retry/timeout behavior, defaults, and data-minimization rules to `docs/CONTRACT.md` as the single
  source of truth.
- **Description:** Add `backend/app/notify/channels.py`, mirroring the GC-safe background-task
  lifetime pattern in `notify/hooks.py`. Configuration: `SHB_NOTIFY_WEBHOOK_URL` (empty/absent =
  disabled), `SHB_NOTIFY_CHANNEL=generic|lark` (default `generic`), and
  `SHB_NOTIFY_INCLUDE_AMOUNT=0|1` (default `0`). Expose pending and decided notifications. The
  normalized content is only `action`, the first eight characters of `conv_id`, `status`, and a
  Tower `deep_link`; include `amount` only when explicitly enabled. Never include customer name,
  document text, CIC, collateral, reasons, credentials, or webhook URL in logs. Generic format is
  flat JSON; Lark format is an interactive card with an “Open Control Tower” button. Use a 5-second
  request timeout and at most three total attempts (initial, then backoffs of 1s and 3s); any 2xx
  is success, exhaustion logs and drops without changing the business response.
- **Hook points:** After the database commit and after the existing SSE emission: (a) only when
  `gated.py` actually creates a human `pending` approval; and (b) after
  `api/approvals.py::decide` commits. Use `{APP_URL}/?tab=approvals&approval={id}` via the existing
  URL helper. No outbound call may run inside the money/decision transaction.
- **Dependency:** none.
- **Verification:** HTTP-mock tests cover both exact payload shapes, one request per event,
  decided status, amount absent by default, explicit amount opt-in, no forbidden fields, disabled
  mode, retry count/backoffs, timeout/500/non-2xx, and business success despite delivery failure.
  A below-threshold auto path must emit no pending doorbell.

### T19-2 — Exact-ticket API and Control Tower deep-link

- **Assignee:** be + fe.
- **Contract-first:** Define admin-only `GET /api/approvals/{id}` in `docs/CONTRACT.md` before
  backend or frontend changes. The current queue lists pending approvals only and cannot satisfy a
  deep-link to an already-decided ticket. The endpoint returns the existing approval resource for
  any status, using the same authorization and read-time enrichment rules; nonexistent or hidden
  resources follow the repository's 4-field error envelope and non-disclosure policy.
- **Description:** Implement the exact-ticket store/service/router path. In the SPA, validate and
  parse `?tab=approvals&approval=<id>` without adding a router library. An authenticated bank user
  opens Tower's approval tab and the exact ticket is fetched, scrolled into view, and highlighted,
  including a decided ticket not present in the pending list. An unauthenticated user keeps the
  validated **relative** return path through password and Google login, then resumes it. Reject
  absolute/protocol-relative return targets. A customer role neither renders Tower nor performs
  the exact-ticket fetch, so ticket existence is not disclosed.
- **Affected files:** `docs/CONTRACT.md` first; approval store/service/router; `App.tsx`,
  `ControlTower.tsx`, login/auth continuation seam; tests.
- **Dependency:** none (parallel with T19-1; integration in T19-4).
- **Verification:** Backend tests cover pending, approved, rejected, 404/non-disclosure, and role
  authorization. FE tests cover authenticated bank focus/highlight, decided ticket fetch, absent
  params, password and Google round-trips, unsafe redirect rejection, and customer zero-fetch.
  Existing app tests and typecheck remain green.

### T19-3 — Deployment config and doorbell runbook

- **Assignee:** be.
- **Description:** Add the three T19-1 variables to `.env.example` and
  `docker-compose.prod.yml`, with a clear warning not to enable amount on channels outside the
  bank DC. Add “Lark / Webhook Doorbell” to `docs/deploy.md`: custom-bot setup, secret handling,
  data boundary, rate-limit/best-effort behavior, retry/timeout behavior, exact event shapes, and
  disabling/rollback. Keep `docs/CONTRACT.md` as the authoritative payload source and link to it.
  D-71 already records that this narrowly supersedes D-15 only for outbound doorbell notifications.
- **Dependency:** T19-1; the public shapes must already be fixed in the contract.
- **Verification:** `docker compose -f docker-compose.prod.yml config` passes with sample env;
  `.env.example` contains all keys/defaults; deploy docs contain the safety warning and link to
  both contract shapes; no secret or real webhook URL is committed.

### T19-4 — S19 Gate (independent tester)

- **Assignee:** tester.
- **Description:** On a local stack with a controlled receiver, submit a fresh over-threshold
  disbursement; observe the pending doorbell in under five seconds; follow the deep-link while
  logged out; authenticate as bank staff; see the exact highlighted ticket; approve; observe the
  decided doorbell; and prove exactly one disbursement receipt. Inspect the received payloads for
  data minimization. Then set the S18 threshold to zero and prove a fresh otherwise-auto case also
  creates a human ticket and doorbell. No approval may be performed from chat.
- **Dependency:** T19-1, T19-2, T19-3 and the **S18 gate passed**.
- **Verification:** Receiver log with timestamps, login/deep-link screenshot, SQL approval and
  receipt evidence, zero forbidden payload fields, duplicate-call guard, full suite at or above
  baseline with zero failures, and real event-to-webhook latency recorded in `end_sprint_19.md`.

---

## Kickoff — 2026-08-24

**Drift since plan:** D-71 is available because existing D-69/D-70 belong to S16. D-71 narrowly
supersedes D-15 for outbound doorbells only. Audit found that the pending-only list endpoint cannot
open a decided deep-link, hook order was not explicit enough, auth continuation omitted Google and
open-redirect validation, and retry/timeout semantics needed one authoritative definition.

**Plan revisions:** Added contract-first ordering to T19-1 and T19-2; made an admin exact-ticket
endpoint a backend dependency; fixed post-commit/post-SSE hook ordering; defined three total
attempts and a five-second timeout; covered both login paths with safe relative redirects; and made
passing the S18 gate an explicit prerequisite for T19-4.

**Final task list (dispatched):**

- T19-1 — contract and best-effort data-minimized channel adapter.
- T19-2 — exact-ticket API plus authenticated deep-link UX.
- T19-3 — production configuration and operational runbook.
- T19-4 — integrated independent gate after S18.
