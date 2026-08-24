# Sprint 19 — Plan

<!-- LIVING RULE (read before editing): task-id: T19-<n>. Plan is the single source of truth;
     kickoff EDITS IN-PLACE + APPENDS Kickoff section at bottom. -->

**Objective:** Step 1 of the "headless + 3 thin frontends" model (strategic report 23 Aug, section 4):
**doorbell** — approval-pending / approval-decided events fire to the bank's chat channel (Lark custom
bot webhook / generic webhook) as DATA-MINIMIZED notifications + a deep-link that opens the exact
phiếu in Control Tower. Lark's role is doorbell only, NOT a credit data pipeline (D-71). Embed SDK
and Control Tower upgrade are the NEXT sprint — this sprint does NOT touch them.

**Theme:** DOORBELL — notify channel adapter + deep-link to Tower.

**Baseline test count:** ≥ count locked at end_sprint_18.

---

## Tasks (4, execute in dependency order)

### T19-1 — `notify/channels.py`: outbound webhook adapter (bank-side, best-effort)
- **Assignee:** be
- **Description:** New module `backend/app/notify/channels.py` — mirrors the GC-safe fire-and-forget
  pattern from `notify/hooks.py` (hold task ref, try/except-log, NEVER block main flow). Env config:
  `SHB_NOTIFY_WEBHOOK_URL` (empty = disabled, default), `SHB_NOTIFY_CHANNEL=lark|generic`,
  `SHB_NOTIFY_INCLUDE_AMOUNT=0|1` (default 0). Two event functions:
  `notify_channel_approval_pending(approval_row)` and `notify_channel_approval_decided(approval_row)`.
  Payload is DATA-MINIMIZED — NO customer name, NO document content, NO CIC:
  `{action, conv_id truncated to 8 chars, amount (only when env enabled), status, deep_link}`.
  Lark format = interactive card (title + 1 line + button "Open Control Tower"),
  generic format = flat JSON. Light retry: max 2 retries, backoff 1s/3s, then log warning and drop
  (best-effort, same as email §12). Hook points (AFTER commit + SSE, alongside existing
  `notify_conv_owner` calls): (a) `gated.py` pending-phiếu branch (where `approval.pending` is
  emitted); (b) `api/approvals.py::decide` (alongside existing mail notify).
  Deep-link: `{APP_URL}/?tab=approvals&approval={id}` (reuse `hooks.app_url()`).
- **Dependency:** none
- **Verification:** pytest `test_notify_channels.py` with HTTP server mock: (a) pending phiếu created →
  mock receives exactly 1 request, payload matches lark/generic shape per env, does NOT contain
  full_name/PII (assert absence); (b) decide → second request with status=approved; (c) webhook
  returns 500/timeout → decide still returns 200, main flow unchanged (regression `test_gated.py`
  passes); (d) empty env → 0 requests; (e) `SHB_NOTIFY_INCLUDE_AMOUNT=0` → payload has no amount field.

### T19-2 — Control Tower deep-link: open exact phiếu from URL
- **Assignee:** fe
- **Description:** FE reads query param `?tab=approvals&approval=<id>` at boot: (a) already logged in
  as bank role → open Control Tower, approvals queue tab, scroll + highlight phiếu `<id>` (decided
  phiếu → still open, show final status); (b) not logged in → show login screen, after successful
  login redirect back to the EXACT deep-link (preserve params through auth flow); (c) customer role →
  403-hide as current behaviour (do not reveal phiếu existence). Touch:
  `App.tsx` (boot/routing), `ControlTower.tsx` (focus/highlight), `Login.tsx` (preserve redirect
  param). No router library added — manual param parsing consistent with current SPA approach.
- **Dependency:** none (parallel with T19-1; integration tested in T19-4)
- **Verification:** vitest: (a) render App with URL containing param + bank session mock →
  ControlTower active, phiếu element has highlight class; (b) no param → existing behaviour
  unchanged (existing App.test passes); (c) customer session + param → Tower not rendered, approval
  not fetched (assert mock API not called). tsc typecheck: 0 errors.

### T19-3 — Deployment config + doorbell runbook
- **Assignee:** be
- **Description:** (a) `.env.example` + `docker-compose.prod.yml`: add 3 env vars from T19-1
  (comment clearly: "approvals desk webhook — DO NOT enable include_amount on channels outside
  bank's DC"); (b) `docs/deploy.md` new section "Lark / Webhook Doorbell": instructions for
  creating a Lark custom bot (incoming webhook) in the approvals group chat, note on Lark-side
  rate limits and adapter's best-effort/drop behaviour, table of 2 event payload shapes; (c)
  `docs/CONTRACT.md` appendix — outbound webhook (2 payload shapes as single source of truth).
  Record D-71 in DECISIONS.
- **Dependency:** T19-1 (payload shape must be finalized)
- **Verification:** `docker compose -f docker-compose.prod.yml config` validates with sample env;
  grep deploy.md has doorbell section + CONTRACT.md has outbound shape appendix;
  `.env.example` contains all 3 new keys.

### T19-4 — S19 Gate (independent tester)
- **Assignee:** tester
- **Description:** Full e2e round-trip on local stack + real webhook receiver (or real Lark bot if
  test group available): disburse case over threshold → pending phiếu → webhook receives card in
  <5s (measure timestamp emit→receive) → click deep-link → (not logged in) log in as bank →
  correct phiếu highlighted → approve → webhook receives decided event → disbursal resumes
  EXACTLY ONCE (brake regression, duplicate-call guard). Verify data-minimization on real payload
  (no PII). Full suite + S18 shadow-mode still functional (threshold=0 → human phiếu → doorbell
  fires — both sprints integrated correctly).
- **Dependency:** T19-1, T19-2, T19-3
- **Verification:** scenario PASSES step-by-step with evidence (receiver log, highlight screenshot,
  SQL approvals/receipt); full suite ≥ baseline, 0 failures; event→webhook latency recorded as
  real number in end_sprint_19.

---

<!-- ↓ ARCHITECT appends at kickoff. -->

## Kickoff — {{YYYY-MM-DD}}

**Drift since plan:** {{...}}

**Plan revisions:** {{...}}

**Final task list (dispatched):**
- {{...}}
