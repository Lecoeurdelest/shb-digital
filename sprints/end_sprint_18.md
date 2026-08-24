# Sprint 18 — End (Positioning + shadow readiness)

**Status (2026-08-24): CLOSED.** Implementation, deterministic/integrated verification, and the
corrected live-model memo gate all passed.

## Results

- **T18-1 — Configurable threshold:** production routing now reads
  `assumptions.auto_approve_threshold_vnd`; missing means 500M, malformed/read failure means `0`,
  and a resolved value `<=0` sends every case to a human before the tier-2 green path. The
  counterfactual snapshot still evaluates the nominal 500M matrix.
- **T18-2 — Shadow ledger:** pending approvals snapshot lane/recommendation; the human decision and
  immutable `shadow_reviews` row commit atomically with one row per approval. Neutral
  `human-review` rows keep `match=null` and stay out of the comparable denominator. The admin
  stats endpoint exposes consistent total/comparable/matched/rate lane/day buckets.
- **T18-3 — Pre-assessment memo:** the deterministic MAIN gate requires at least two completed,
  distinct specialist roles. The `document` card keeps its existing type and uses the exact title
  `Tờ trình sơ thẩm`; the six locked sections cover request summary, DSCR/LTV/CIC repayment
  capacity, three-pillar legal assessment/lane/assessment ID, proposed terms, recommendation with
  authority-matrix rationale, and tools/sources. Business items require non-empty sources. The
  one-role Operations fixture proves the negative path without relying on live routing.
- **T18-4 — Positioning:** README, SPEC, business case, and demo opening now frame the product as a
  pre-assessment/middle-office copilot under D-73: the machine prepares and a human signs. The
  customer surface remains a demo/sandbox, not a small-loan auto-decisioning proposition.

## Integrated lifecycle evidence (`shb_test`)

- With the threshold set to `0`, a fresh 50M case with no assessment became `pending`. Its
  counterfactual snapshot was `system_lane=null` and `system_recommendation=auto-eligible`.
  Approval created an immutable review with `match=true`.
- A separate green case also stayed pending in shadow mode; approval produced `match=true`, and
  `/api/stats/shadow-match` increased `total`, `comparable`, and `matched` by exactly one.
- Resume executed the real disbursement once: approval became `used`, the loan became
  `disbursed`, and an immediate replay returned the identical receipt while the actual handler
  invocation count remained `1 → 1`.
- After removing the threshold assumption, a fresh 50M case followed the backward-compatible
  auto-approval path. Gate rows were removed afterwards and the threshold was restored to absent.

## Verification

- Historical S18 checkpoint: backend **477 collected = 460 passed + 17 skipped**; frontend
  **231 passed**. Total: **691 passed + 17 skipped**.
- The 17 backend skips remain explicit opt-in live-SDK/embed coverage, not failures.
- Deterministic memo tests cover the positive two-role gate, the one-role negative gate, all six
  section names, and item-level sources.

## T18-3 live-model memo evidence

The first live run completed in **286.966s** (`ed981ed4-a35e-4755-969b-a617caf3b53b`) with four
specialist roles done, the exact title, all six exact sections, and a non-empty source on every
business item. It exposed a real integration defect: the prompt required top-level `sources`, but
the MCP `present` schema did not advertise that optional field, so all three memo revisions omitted
it and the strict validator returned `pass=false`.

The fix exposes optional `sources: string[]` in the tool schema while preserving the generic card
contract and legacy required fields. Focused schema/prompt verification passed **13/13**. A fresh
SDK-session recheck using the recorded XD-01 facts then passed on conversation
`bce3c011-caac-4539-8a83-4c73e15b1db4`: four done roles, one document, exact title, six exact
sections, non-empty item sources, and top-level sources
`[credit_assess, legal_classify_profile, product_suggest, operations, wiki_lookup]`. The audit log
also proves MAIN actually called `wiki_search` and `wiki_lookup(phan-cap-tham-quyen)` before
presenting the memo; the provenance entry was not invented.

## Gate verdict

- [x] Contract/config/ledger behavior and fail-closed edge cases.
- [x] Real shadow lifecycle, atomic review, stats delta, exactly-once receipt, and default restore.
- [x] Positioning rewrite and deterministic memo gate.
- [x] Live-model memo validator PASS after the tool-schema integration fix.

**Verdict:** all Sprint 18 gates passed; Sprint 18 is **closed**.
