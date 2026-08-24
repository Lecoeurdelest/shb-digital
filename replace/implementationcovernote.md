# Sprint 18 & 19 Implementation — Cover Note

> Companion files: `plan_sprint_18.md` (W1 — Positioning) · `plan_sprint_19.md` (W2 step 1 — Doorbell).
> Both plan files follow the exact `sprints/templates/plan_sprint.template.md` template and drop
> directly into `sprints/` in the repo. Architect edits in-place at kickoff per existing rules.

---

## Sequencing Rationale

**S18 first, S19 second — but independently deployable.** S18 turns the business-case promise
"shadow-mode = config" into technical reality (currently `AUTO_APPROVE_THRESHOLD` is a hardcoded
constant in `verdict.py` — business-case §3 is overclaiming by one step relative to the code) and
builds the match-rate meter — the first thing a bank will ask for when they hear the word "pilot".
S19 proves the doorbell model on the realest event in the system (a pending approval phiếu). The
two sprints connect at the S19 gate: threshold=0 → every disburse goes to human → doorbell fires →
deep-link → human decides → match-rate ledger records. That is the first complete "middle-office
copilot" demo under the new positioning.

**What is deliberately NOT done in these 2 sprints** (anti-bloat, per SPEC §14):
embed SDK for bank channel (W2 step 2) · Control Tower upgrade to credit memo queue (W2 step 3) ·
any two-way Lark integration (bot receiving commands/approvals from chat — PROHIBITED: approval must
happen in Tower where auth + audit live) · Redis/scale-out (roadmap item 5 — not needed at 1-branch
pilot) · consent/PDPL module (required before real-data pilot — schedule as separate sprint once
pilot date is known).

---

## Code Anchors (for fast architect kickoff)

| Item | Location in repo |
|---|---|
| Hardcoded tier-1 threshold | `backend/app/orch/verdict.py` — `AUTO_APPROVE_THRESHOLD = 500_000_000`; config pattern ready: `auto_approve_max()` reads `assumptions.auto_approve_max_vnd` |
| Pending phiếu hook (fire doorbell) | `backend/app/orch/gated.py` — branch 4 creates phiếu, near "SSE AFTER commit: emit card + approval.pending" + call to `notify_conv_owner` |
| Decided hook (fire doorbell) | `backend/app/api/approvals.py::decide` — after commit, next to `notify_conv_owner(decided["conv_id"], ...)` |
| GC-safe fire-and-forget pattern | `backend/app/notify/hooks.py` — `_bg_tasks` holds ref + `add_done_callback(discard)`; `app_url()` for deep-link |
| Queue enrichment (don't repeat PII into webhook) | `store_approvals.py` DF-B-01 enriches at READ time for Tower — webhook does NOT reuse this enrich (data-minimization) |
| Credit memo | `document` card type (already exportable); edit `main_prompts.py`/`main_skill.py`, shell stays untouched |
| Match-rate meter | business-case §3/§6 promises "audit as meter" — S18 T18-2 makes it a real table + real API |

---

## Proposed DECISIONS Entries
*(paste into `DECISIONS.md` at kickoff, newest entry at top)*

---

**D-71 · External chat channels (Lark/Teams/webhook) = DOORBELL, not data pipeline** (locked 23 Aug
per strategic report) — notification payload is minimized: action + 8-char truncated conv_id +
deep-link to Tower; NO customer name / document content / CIC; amount field behind env flag
defaulting OFF. PROHIBIT any flow that pushes credit data through third-party SaaS outside the
bank's infrastructure (Law 91/2025/QH15 Personal Data Protection effective 1 Jan 2026 + industry
security standards; proper integration path = adapter tool + Open API per TT 64/2024/TT-NHNN).
PROHIBIT approval from chat — decisions happen only in Control Tower (auth + audit). — upgrade
path: bank runs Lark on-prem/private and signs data processing agreement → expand payload with 1
env var, shape already reserved.

---

**D-70 · Tier-1 authority matrix threshold: constant → `assumptions.auto_approve_threshold_vnd`** —
missing key = 500M VND (backward-compatible, money-guard unchanged); key present = respected exactly
(0 = shadow-mode); DB read error = 0, fail-closed to human (tighten-only, consistent with
verdict-aware philosophy). — rollback: delete the key from assumptions to restore demo default.

---

**D-69 · Product positioning: pre-assessment machine + middle-office operations; NOT small-loan
unsecured auto-decisioning** (locked 23 Aug) — rationale: internal bench (single wins on speed/cost
for single-department cases; multi wins on cross-department sequential handoffs), market (SHB already
has minute-level auto-approval via SAHA/TT 06/2023), legal framework (LLM-as-credit-decision has no
regulatory basis; NĐ 94/2025 sandbox covers scoring only). Primary persona: RM/credit officer
underwriting desk + approvals desk; customer portal stays as demo/sandbox. — upgrade path: if bank
requires opening auto-approve, do it only via threshold matrix signed off by bank (path already
exists in verdict-aware).

---

## What Comes After S19 (flagged, not yet planned)

**S20 — Control Tower becomes primary interface:** credit memo queue + shadow match-rate dashboard
(T18-2 API already built) + pilot KPIs per business-case §6.

**S21 — Embed SDK:** extract Workspace chat/canvas as embeddable widget (FE↔BE contract already
defined in `docs/CONTRACT.md`).

**Before real-data pilot:** consent module + PDPL impact assessment (Law 91/2025/QH15) — hard
prerequisite, applies even in shadow-mode.

**ROADMAP.md:** add 2 lines for S18/S19 following existing golden-path format.
