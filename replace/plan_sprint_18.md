# Sprint 18 — Plan

<!-- LIVING RULE (read before editing):
     This plan is the single SOURCE OF TRUTH for the sprint. Kickoff does NOT create a new file —
     architect EDITS IN-PLACE (drift <10% = inline note; 10–30% = edit + History appendix; >30% = rewrite),
     then APPENDS a `## Kickoff — YYYY-MM-DD` section at the END. Never dispatch from a stale plan.
     Task = spec: every task must have a MACHINE-VERIFIABLE verification. Task-id: T18-<n>. -->

**Objective:** Transition the system from "demo approval machine" to "shadow-ready pre-assessment engine":
tier-1 authority matrix made configurable down to 0 (shadow-mode = config, fulfilling business-case §3
Phase 0 promise — currently `AUTO_APPROVE_THRESHOLD` is a HARDCODED CONSTANT in `verdict.py`, not config),
match-rate meter turned into real API metrics, credit memo standardized as the central product, docs
reframed to the new positioning (middle-office copilot, not competing with small-loan auto-approval —
strategic report 23 Aug, section 3).

**Theme:** POSITIONING — "human signs, machine prepares": shadow-mode + match-rate meter + credit memo.

**Baseline test count:** 679 (448 BE + 231 FE — per README; re-verify at kickoff since S17 is still open).

---

## Tasks (5, execute in dependency order)

### T18-1 — Configurable tier-1 threshold (shadow-ready, tighten-only)
- **Assignee:** be
- **Description:** `backend/app/orch/verdict.py`: replace constant `AUTO_APPROVE_THRESHOLD = 500_000_000`
  with helper `auto_approve_threshold(conn)` that reads `assumptions.auto_approve_threshold_vnd`
  (mirrors the existing `auto_approve_max()` pattern). Fail-closed semantics: key **absent** →
  500_000_000 (backward-compatible, 41 money-tests unchanged); key **present** → use exact value
  (0 ⇒ every disburse goes to human = shadow-mode); **DB read error** → 0 (route to human —
  tighten-only, never loosen). Seed/reset_demo does NOT set the key (demo behaviour unchanged).
  Record DECISIONS entry D-70 (see cover note).
- **Dependency:** none
- **Verification:** new pytest `test_shadow_threshold.py`: (a) key=0 → 50M VND amount creates
  `pending` approval requiring human, NOT auto; (b) key absent → 50M auto-approves as before
  (regression); (c) mock DB read error → routes to human; (d) all existing money-test guards pass
  unmodified (`test_gated.py`, `test_ops_disburse_gated_t123b.py`, `test_verdict_brake_t73.py`).

### T18-2 — Shadow match-rate ledger (system↔human comparison as API)
- **Assignee:** be
- **Description:** When a human phiếu is decided (`backend/app/api/approvals.py::decide`), write a
  comparison record to new append-only table `shadow_reviews` (Alembic migration):
  `approval_id, conv_id, system_lane` (latest assessment lane per owner — reuse
  `verdict.latest_verdict`), `system_recommendation` (derived from authority matrix:
  auto-eligible / human / reject-recommended), `human_decision` (approved/rejected),
  `human_reason, decided_at, match` (bool: system recommendation ≡ human decision).
  New API `GET /api/stats/shadow-match` (admin role): match-rate total + by lane + by day,
  sample count. This is the "audit as match-rate meter" promised in business-case §3 — as real numbers.
- **Dependency:** T18-1 (human branch must cover all cases when threshold=0)
- **Verification:** pytest: 2 simulated cases (green lane human-rejected → match=false; red lane
  human-rejected → match=true) → API returns `{total:2, matched:1, rate:0.5}` + correct lane
  breakdown; existing decide-flow tests unchanged in shape and speed.

### T18-3 — Standardize credit memo (credit memo as central product)
- **Assignee:** be (prompt/skill only — NO frontend changes)
- **Description:** Standardize the `document` card "Tờ trình sơ thẩm" (Pre-assessment Credit Memo)
  as the MAIN output when ≥2 sub-agent results are available. 6 mandatory sections:
  (1) request summary; (2) repayment capacity (DSCR/LTV/CIC + sources); (3) legal assessment —
  3 pillars + lane + assessment #id; (4) proposed terms; (5) **decision recommendation + authority
  matrix rationale** (auto-eligible/human, which threshold applies); (6) tools/sources used.
  Edit `backend/app/orch/main_prompts.py` + `main_skill.py` (present template `document`);
  each item carries a `source` field per SPEC §6. No card type changes, no frontend changes.
- **Dependency:** none (parallel with T18-1/2)
- **Verification:** re-run bench case XD-01 (`bench/run_multi.py --case XD-01-vay-tron-goi`) →
  final `document` card has all 6 sections (script checks `cards.data` fields: title matches
  "Tờ trình", items ≥6, each business item has `source`); case CR-01 (single-department) does
  NOT produce a credit memo (only when ≥2 subs — enforced in skill).

### T18-4 — Docs positioning rewrite (reframe to new positioning)
- **Assignee:** architect
- **Description:** Change the narrative frame, NOT the features: `README.md` (opening paragraph +
  Key Features: primary persona = RM/credit officer underwriting desk; customer portal = demo/sandbox),
  `docs/business-case.md` §1 (add paragraph "not competing with TT06/2023 small-loan auto-approval —
  integration via adapter, system operates at pre-assessment of complex/collateralized cases"),
  `docs/demo-script.md` (opening scenario = RM/underwriting desk, customer interaction is a
  supporting scene), `SPEC.md` §Meta (positioning statement). Source content: strategic report
  23 Aug sections 0–3 (project doc `bao-cao-dinh-huong-shb-digital.md`). Record D-69.
- **Dependency:** none
- **Verification:** machine-checkable grep: README contains "sơ thẩm" + "middle office" (or
  "underwriting assistant") within first 30 lines; business-case §1 contains "TT 06/2023";
  demo-script section 1 opens with bank/RM role; old standalone positioning phrase "chi nhánh ngân
  hàng số" no longer appears alone in the first README description line (replaced with new frame,
  original keywords preserved for judge issue #132).

### T18-5 — S18 Gate (independent tester)
- **Assignee:** tester
- **Description:** Full e2e shadow round-trip on local stack: set
  `auto_approve_threshold_vnd=0` → 50M VND disburse request → human phiếu created + Control Tower
  shows it → decide approve → disbursed exactly once (brake regression) → `shadow_reviews` has
  record + `/api/stats/shadow-match` returns correct numbers → reset key → auto-approve behaviour
  restores. Run full suite.
- **Dependency:** T18-1, T18-2, T18-3
- **Verification:** scenario PASSES step-by-step with evidence (curl/SQL/screenshot); full suite
  ≥ baseline (679) + new tests, 0 failures; ruff + tsc clean.

---

<!-- ↓ Section below appended by ARCHITECT at kickoff. Leave this skeleton blank until then. -->

## Kickoff — {{YYYY-MM-DD}}

**Drift since plan:** {{...}}

**Plan revisions:** {{...}}

**Final task list (dispatched):**
- {{...}}
