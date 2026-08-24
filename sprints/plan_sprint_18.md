# Sprint 18 — Plan

<!-- LIVING RULE (read before editing):
     This plan is the single SOURCE OF TRUTH for the sprint. Kickoff does NOT create a new file —
     architect EDITS IN-PLACE (drift <10% = inline note; 10–30% = edit + History appendix; >30% = rewrite),
     then APPENDS a `## Kickoff — YYYY-MM-DD` section at the END. Never dispatch from a stale plan.
     Task = spec: every task must have a MACHINE-VERIFIABLE verification. Task-id: T18-<n>. -->

**Objective:** Transition the system from a demo approval machine to a shadow-ready
pre-assessment engine: make the tier-1 authority threshold configurable down to zero, measure
counterfactual system-versus-human decisions, standardize the credit memo, and align the product
story with the middle-office-copilot positioning in D-73.

**Theme:** POSITIONING — “human signs, machine prepares”: shadow mode + match-rate meter +
credit memo.

**Kickoff baseline (2026-08-24):** BE `461 collected = 444 passed + 17 skipped`; FE `231 passed`
under Node 26 with `NODE_OPTIONS=--no-experimental-webstorage`. Raw `npm run test` under Node 26
fails during Vitest bootstrap because the runtime's experimental Web Storage cannot initialize for
the opaque jsdom origin; that is an environment/toolchain failure, not a product-test regression.

---

## Tasks (5, execute in dependency order)

### T18-1 — Configurable tier-1 threshold (shadow-ready, tighten-only)

- **Assignee:** be
- **Description:** Replace production use of the hardcoded tier-1 threshold with
  `assumptions.auto_approve_threshold_vnd` under D-72. Read the setting through a separate,
  isolated config read (for example, a short-lived read connection) before opening/using the
  money transaction; a failed `SELECT` must not leave the transaction that creates the approval
  in PostgreSQL's aborted state. Semantics are exact: missing key → `500_000_000`; valid value →
  use exactly that value; malformed value or read failure → `0` (fail closed). A resolved value
  `<= 0` takes an explicit shadow branch that routes **every** disbursement to a human before any
  green/tier-2 auto path is considered. Pass the resolved value explicitly into the verdict/gated
  decision. The old constant may remain only as a compatibility/default export; production flow
  must not consult it as route policy. For the counterfactual ledger only, a shadow override
  `<=0` is evaluated against the nominal backward-compatible 500M matrix so the pilot still
  measures what would have happened without the override. Seed/reset does not create the key,
  preserving the 500M demo default.
- **Affected files:** `backend/app/orch/verdict.py`, `backend/app/orch/gated.py`, config/store
  helper as needed, and backend tests.
- **Dependency:** none.
- **Verification:** Add `test_shadow_threshold.py` covering: key `0` + 50M with no assessment;
  key `0` + a green tier-2 assessment; both create a `pending` human approval and never auto-run.
  Missing key preserves 50M auto behavior. A malformed value and a forced DB read error both fail
  closed yet still create a usable pending approval (not `gated_error`). Existing money guards
  (`test_gated.py`, `test_ops_disburse_gated_t123b.py`, `test_verdict_brake_t73.py`) pass unchanged.

### T18-2 — Shadow match-rate ledger (counterfactual system↔human comparison)

- **Assignee:** be
- **Description:** Define the public API in `docs/CONTRACT.md` **before** changing migration,
  service, or router code. Add a reversible Alembic migration for append-only `shadow_reviews`
  and any approval snapshot columns required by the design. When a pending approval is created,
  snapshot the counterfactual system lane and recommendation **before** shadow mode overrides the
  outcome. Resolve both supported owner seams: normal `disburse` rows keyed by `loan_id` and
  `ops_disburse` rows keyed by `application_id`. On human decision, insert the immutable review in
  the **same database transaction** as the approval status/card synchronization; the decision and
  ledger record must commit or roll back together. Enforce one review per `approval_id`.
  Recommended fields: `approval_id`, `conv_id`, nullable `system_lane`,
  `system_recommendation` (`auto-eligible|human-review|reject-recommended`), `human_decision`,
  `human_reason`, `decided_at`, and nullable `match`. `match=true|false` only when the system made
  a directional auto/reject recommendation; a neutral `human-review` recommendation has
  `match=null` and is excluded from the denominator.
- **API:** Admin-only `GET /api/stats/shadow-match` returns `total`, `comparable`, `matched`, and
  `rate = matched / comparable` (`0.0` when `comparable=0`), plus `by_lane` and `by_day` buckets
  with those same counters and rate semantics.
- **Affected files:** `docs/CONTRACT.md` first; Alembic migration; approval/gated store and service
  seams; `backend/app/api/approvals.py`; stats router/service; backend tests.
- **Dependency:** T18-1.
- **Verification:** Tests prove: green snapshot + human rejection → `match=false`; red snapshot +
  human rejection → `match=true`; neutral `human-review` snapshot → `match=null`; aggregate is
  `total=3, comparable=2, matched=1, rate=0.5`. A neutral-only fixture returns
  `total=1, comparable=0, matched=0, rate=0.0`.
  Verify identical counters in lane/day buckets, both owner-key paths, unique retry behavior, and
  rollback atomicity when ledger insertion fails. Existing decide response shape remains intact.
  The 50M/no-assessment shadow fixture must snapshot `auto-eligible` while its real route remains
  human, proving that the stored value is counterfactual rather than a copy of the actual route.

### T18-3 — Standardize the pre-assessment credit memo

- **Assignee:** be (prompt/skill only — no frontend changes).
- **Description:** Make the `document` card “Tờ trình sơ thẩm” the MAIN output only when at least
  two completed expert results are available. Require six sections: (1) request summary;
  (2) repayment capacity — DSCR/LTV/CIC with sources; (3) legal assessment — three pillars, lane,
  assessment ID; (4) proposed terms; (5) recommendation and authority-matrix rationale; and
  (6) tools/sources used. Edit `backend/app/orch/main_prompts.py` and `main_skill.py`; keep the
  existing `document` card contract and require `source` on each business item under SPEC §6.
- **Dependency:** none (may run in parallel with T18-1/T18-2).
- **Verification:** Positive integration check: recorded bench case XD-01 produces a Tờ trình with
  all six sections and sourced business items. Negative check must be a deterministic unit fixture
  whose board contains exactly one completed `operations` task, modeled on OP-01; it must not emit
  the credit memo. Do not use a live CR-01/OP-01 model run as the negative gate because routing can
  dispatch multiple experts and is nondeterministic.

### T18-4 — Docs positioning rewrite

- **Assignee:** architect.
- **Description:** Change the narrative frame, not the features: README opening/Key Features;
  `docs/business-case.md` §1; `docs/demo-script.md` opening scenario; and SPEC metadata. Primary
  persona is the RM/credit-officer underwriting and approvals desk; customer portal is a
  demo/sandbox. State that the product does not compete with TT 06/2023 small-loan automation and
  integrates through bank-controlled adapters. Source: `claude/strategic-report-shb-digital-en.md`
  and D-73.
- **Dependency:** none.
- **Verification:** README includes “sơ thẩm” and “middle office” or “underwriting assistant” in
  its first 30 lines; business case §1 names TT 06/2023; demo script opens from the bank/RM role;
  the former standalone “chi nhánh ngân hàng số” opening is replaced while issue #132 keywords
  remain discoverable.

### T18-5 — S18 Gate (independent tester)

- **Assignee:** tester.
- **Description:** Run a full shadow round-trip on a local stack: set threshold to `0`; submit a
  fresh 50M disbursement payload; observe a human approval in Control Tower; approve; prove exactly
  one receipt; inspect the immutable shadow row and stats response; then remove the key and use a
  second fresh payload to prove default auto behavior. Fresh payloads are mandatory because a
  successful money-tool retry returns its existing receipt by design.
- **Dependency:** T18-1, T18-2, T18-3, **T18-4**.
- **Verification:** Step-by-step curl/SQL/UI evidence; stats counters match the ledger; full suite
  is at least baseline plus new tests with zero failures; backend ruff and frontend typecheck pass.

---

## Kickoff — 2026-08-24

**Drift since plan:** The source package proposed D-69/D-70 for positioning/threshold, but those
IDs are already live S16 decisions. They are D-73/D-72 here, while D-71 remains the doorbell
decision. Audit also found that threshold zero could still enter the green tier-2 path; a caught
config error could poison a shared PostgreSQL transaction; the draft ledger lacked a pending-time
counterfactual snapshot, atomic decision write, neutral denominator, and the `application_id`
owner path; and the draft memo negative relied on nondeterministic live routing. S17 is closed; the
actual kickoff baseline is 444 BE passes + 17 skips from 461 collected and 231 FE passes under the
Node 26 Web Storage compatibility flag.

**Plan revisions:** Added the explicit pre-tier shadow branch and isolated config read; made the
shadow snapshot and decision write transactional with nullable neutral matches and comparable
denominators; made contract-first ordering explicit; replaced the live negative memo case with an
OP-01-modeled deterministic fixture; added fresh-payload guidance; and added the missing T18-4
dependency to the sprint gate.

**Final task list (dispatched):**

- T18-1 — configurable threshold and explicit shadow path.
- T18-2 — snapshotted, atomic shadow ledger and stats contract.
- T18-3 — deterministic six-section credit memo behavior.
- T18-4 — positioning documentation under D-73.
- T18-5 — integrated independent gate after all four implementation tasks.
