# Sprint 18 & 19 Implementation — Cover Note

*Kickoff package · 24 August 2026*

> Canonical companions: `sprints/plan_sprint_18.md` (positioning and shadow readiness),
> `sprints/plan_sprint_19.md` (doorbell), and
> `claude/strategic-report-shb-digital-en.md` (strategic direction). The sprint plans are living
> sources of truth and already contain the 24 August kickoff reconciliation.

---

## Sequencing rationale

S18 comes first and S19 follows its gate, although their deliverables remain independently
deployable. S18 turns “shadow mode = config” from a business-case promise into an enforceable
technical path and adds the match-rate meter a bank will require for a pilot. S19 proves the
doorbell model on a real pending approval. Their integrated gate is the first complete demo of the
new middle-office-copilot position: threshold zero sends a case to a human; a minimized doorbell
deep-links to the exact ticket; the officer decides inside Control Tower; and the shadow ledger
records the counterfactual comparison.

The package deliberately does not include an embedded SDK, a credit-memo queue redesign, two-way
Lark commands or approval-from-chat, Redis/scale-out infrastructure, or the consent/PDPL module.
Those are later commercial or pre-pilot work. Approval remains inside the bank-controlled Tower,
where authentication and audit already live.

---

## Kickoff governance corrections

The downloadable draft proposed D-69 for positioning and D-70 for the threshold. Those IDs are
already live S16 decisions and are preserved. The canonical numbering is:

- **D-71 — External chat is a doorbell only.** It narrowly supersedes D-15 only for minimized
  outbound notifications. D-15 continues to exclude two-way chat and external data pipelines.
  There is no approval from chat and no credit data outside the bank DC; amount is opt-in and off
  by default.
- **D-72 — Configurable tier-1 threshold.** Read
  `assumptions.auto_approve_threshold_vnd`; missing means 500M VND, malformed/read failure means
  zero, and zero takes an explicit fail-closed shadow branch before every auto path.
- **D-73 — Product positioning.** The product is a pre-assessment and middle-office operations
  copilot for complex loans, not a small-loan auto-decision engine. The human signs; the machine
  prepares, sources, structures, and flags risk.

Contract changes precede implementation. In particular, the shadow stats resource, outbound
payloads, and exact-ticket approval resource must be written into `docs/CONTRACT.md` before backend
or frontend work changes those shapes.

---

## Code anchors for implementation

| Item | Location in repository |
|---|---|
| Hardcoded tier-1 threshold | `backend/app/orch/verdict.py` — current compatibility constant and verdict branches |
| Money gate and pending ticket | `backend/app/orch/gated.py` — config must be isolated from its transaction; doorbell runs only after commit and SSE |
| Human decision | `backend/app/api/approvals.py::decide` — decision and shadow-ledger write are atomic; decided doorbell runs after commit and SSE |
| Fire-and-forget lifetime pattern | `backend/app/notify/hooks.py` — retained task references and URL helper |
| Approval read model | approval store/service/router — add admin exact-ticket lookup because the current list is pending-only |
| Credit memo | `backend/app/orch/main_prompts.py` and `main_skill.py`; existing `document` card type stays unchanged |
| Shadow metrics | new migration, approval snapshot seam, and admin stats endpoint defined contract-first |

---

## Implementation invariants highlighted by the audit

- A setting of zero must route even a green tier-2 assessment to a human. Checking only the amount
  branch does not implement shadow mode.
- Config lookup failure must not be caught inside the transaction used to create the money ticket;
  PostgreSQL would leave that transaction aborted. Use a separate read seam and pass the resolved
  value into the money flow.
- Snapshot the counterfactual system recommendation when the pending ticket is created, before the
  shadow override. Under threshold `<=0`, evaluate that snapshot with the nominal compatible 500M
  matrix while the real route remains human. The human decision and immutable ledger insertion
  commit together.
- A neutral system recommendation (`human-review`) has `match=null`. Report `total`, `comparable`,
  and `matched` separately; calculate rate over comparable rows and return `0.0` when none exist,
  matching the locked contract.
- Cover both ownership paths (`loan_id` and `application_id`).
- A decided notification needs `GET /api/approvals/{id}`; a pending-only queue cannot resolve it.
- Memo gating uses a deterministic one-completed-task unit fixture modeled on OP-01. A live bench
  route is evidence for the positive XD-01 path, not a stable negative test.
- The S18 independent gate follows T18-4 as well as T18-1 through T18-3. S19's integrated gate
  begins only after S18 passes.

---

## What comes after S19

S20 can make Control Tower the primary commercial interface with a credit-memo queue and the
shadow-match dashboard. S21 can extract Workspace chat/canvas as an embeddable client. Before any
real-data pilot, the bank still needs the consent module and PDPL impact assessment identified in
the strategic report.
