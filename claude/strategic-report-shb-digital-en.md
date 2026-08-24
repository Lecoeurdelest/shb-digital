# Strategic Direction Report — SHB Digital Multi-Agent System
*Research report · 23 August 2026*

---

## 0. Executive Summary

The multi-agent system `shb-digital` is positioned in a space that SHB's incumbent lending engine (SAHA / TT 06/2023 sub-100M unsecured) has already claimed. Competing head-on would lose. The correct move is a **hard pivot in one sprint**: reframe from "approval machine" to **"pre-assessment + middle-office copilot"** — serving complex collateralized and SME loans where underwriters spend days, not minutes, and where no incumbent machine exists.

Lark as a data conduit is technically and legally the wrong choice. Used correctly — as a **doorbell** (notification + deep-link back to Control Tower) — Lark works fine and avoids both the compliance risk (Law 91/2025/QH15 effective 1 Jan 2026) and rate-limit fragility.

Throughput architecture for the bank is fundamentally different from web-app TPS thinking. The unit is cases/minute, not requests/second. The current architecture is correct for demo scale; the upgrade path is clear and can be deferred to the first paid pilot.

---

## 1. SHB's Existing Strengths — What Must Not Be Touched

| System | Capability | Regulatory basis |
|---|---|---|
| SAHA app (launched 18 Jun 2025) | 24/7 online overdraft, disbursement in minutes | TT 06/2023 |
| SHBFinance | 5-minute auto-approval, unsecured personal loans | TT 06/2023 |
| Credit scoring engine | Rules-based + statistical, proven in production | Internal |

**Key finding:** TT 06/2023 (electronic consumer lending ≤ 100M VND) already makes fast small-loan auto-approval a commodity in Vietnam. Any system that tries to replicate this loses on cost, speed, and regulatory simplicity. The multi-agent system cannot win here and should not try.

**Counter-argument addressed:** Could the system add value by improving the incumbent's accuracy? No — the incumbent's approval matrix is already tuned to the bank's risk appetite and regulatory ceiling. Adding an LLM layer on top introduces latency and hallucination risk with no upside.

---

## 2. Where the Incumbent Fails — The Real Market Gap

Complex loan cases are structurally different from small unsecured ones:

| Dimension | Small unsecured (SAHA) | Complex / collateralized |
|---|---|---|
| Typical loan size | < 100M VND | 500M – 50B+ VND |
| Processing time | Minutes | 1–5 working days |
| Departments involved | 1 (credit scoring) | 3–5 (credit, legal, appraisal, operations, compliance) |
| Document volume | 3–5 standard forms | 15–80+ documents (title deeds, CIC, financial statements, legal opinions) |
| Key bottleneck | System latency | Human coordination overhead |
| TT 06/2023 scope | In scope | Out of scope |

The multi-agent architecture wins specifically on **cross-department sequential handoffs** — this is confirmed by the bench results: multi-agent outperforms single-agent only on cross-department cases (XD-01 "package loan"). For single-department cases (CR-01), single-agent is faster and cheaper.

**McKinsey reference (2024):** Agentic AI in corporate credit = +40–80% productivity per use case, 50% reduction in financial risk assessment time. Mandatory human oversight throughout. This is exactly the complex-loan use case.

---

## 3. Positioning Pivot — "Human Signs, Machine Prepares"

### New positioning
> **Pre-assessment copilot + middle-office operations tool** for RM/credit officers handling complex collateralized and SME loans. The system prepares, sources, and structures; the human decides.

### What this means in code
- `verdict.py` tier-1 threshold must become **configurable** (currently hardcoded `AUTO_APPROVE_THRESHOLD = 500_000_000` — critical gap). Setting to 0 = **shadow-mode**: every case goes to human. This is what business-case §3 Phase 0 promises but the code doesn't yet deliver.
- The credit memo card (`document` type) becomes the **central product** — the structured pre-assessment report the loan officer signs off on.
- "Customer portal" stays as demo/sandbox only; primary persona shifts to RM/credit officer desk.

### What to drop from the pitch
- ❌ "Automated approval of small loans" — that's SAHA's job
- ❌ "Replace the credit officer" — legally and reputationally toxic; NĐ 94/2025 sandbox only covers credit *scoring*, not credit *decisions*
- ✅ "Draft the credit memo, source the documents, flag the risks, propose the decision — officer reviews and signs"

### Regulatory alignment
- NĐ 94/2025 (fintech sandbox, effective 1 Jul 2025): covers AI-assisted credit scoring. LLM-as-decision-maker for credit has **no legal framework** yet.
- TT 64/2024 (Open API, effective 1 Mar 2025): the proper integration path for bank data — adapter tools calling bank's own Open API, not Lark pushing loan data through SaaS.

---

## 4. Lark — Doorbell, Not Data Pipe

### The case against Lark as data conduit

**Legal risk (Law 91/2025/QH15, effective 1 Jan 2026):**
Sensitive financial data (loan amounts, CIC data, collateral details, customer identity) flowing through a third-party SaaS (Lark) is a personal data transfer to a third party under the new law. This requires explicit consent per processing purpose, a Data Protection Impact Assessment, and potentially a cross-border transfer agreement (if Lark servers are offshore). For a bank undergoing regulatory review, this is a blocker.

**Operational risk:**
Lark's incoming webhook endpoints have documented rate limits. A loan pipeline processing dozens of cases simultaneously could hit throttling. The bank cannot accept "best-effort" SLA on approval workflows.

**Governance risk:**
If approval decisions can be triggered from Lark, the audit trail leaves the bank's controlled environment. Auth + audit must happen in Control Tower, not chat.

### The correct role: doorbell
- Lark receives: `{action, 8-char conv_id, deep-link to Control Tower}` — nothing more
- Amount behind an env flag defaulting OFF
- No customer name, no CIC, no document content
- Button in the Lark card: "Open Control Tower" → officer authenticates → sees full phiếu → decides
- Decision recorded in Control Tower with full audit trail

**Upgrade path if the bank wants more:** Run Lark on-prem/private cloud, sign a data processing agreement → open the payload with a single env var (the shape is already reserved in the design).

---

## 5. Throughput Architecture for Bank-Grade Requirements

### Reframe the problem
"Bank performance" ≠ thousands of TPS. The unit of work is a **case/conversation**, not an HTTP request.

| Metric | Value |
|---|---|
| Large Vietnamese bank's complex loan volume | ~500–2,000 complex cases/day |
| Equivalent throughput | 0.006–0.023 cases/second |
| Even at 10,000 cases/day | 0.12 cases/second |
| Each case duration | 5–20 minutes of agent work |

The bottleneck is **LLM provider concurrency budget**, not HTTP infrastructure.

### Current architecture assessment (correct for demo)
Per SPEC §14, single worker + no Redis is intentional. The gate (`gated.py`) is atomic via `UPDATE…WHERE status='approved' RETURNING` — the brake is invariant regardless of architecture. This is correct.

### Scale-up path (for paid pilot, not demo)
```
Phase 0 (demo):       [FastAPI single worker] → [SQLite/Postgres]
Phase 1 (1 branch):   [FastAPI] → [Postgres] + agent worker separated to background process
Phase 2 (multi-branch): [API tier] → [Task queue (Celery/ARQ)] → [Agent worker pool]
                         Sticky routing by conv_id (same conversation → same worker)
Phase 3 (bank-wide):  [API tier] → [Redis Streams or Kafka] → [Agent worker pool]
                         External LLM rate-limit budget pooled across workers
```

**Do not build Phase 2+ for the demo.** The judge evaluates the decision intelligence, not the queue infrastructure. Redis/scale-out is explicitly deferred in SPEC §14.

---

## 6. Strategic Roadmap — Recommended Sequence

| Sprint | Theme | Key deliverable |
|---|---|---|
| **S18** | Positioning | Threshold configurable (shadow-mode works), match-rate meter, credit memo standardized, docs reframed |
| **S19** | Doorbell | Outbound webhook adapter (data-minimized) + deep-link to Control Tower |
| **S20** | Tower upgrade | Queue view for credit memos + shadow-match dashboard (S18 API already built) |
| **S21** | Embed SDK | Workspace chat/canvas as embeddable widget (CONTRACT.md already defines the interface) |
| Pre-pilot | Compliance | Consent module + PDPL impact assessment (Law 91/2025) — hard prerequisite before real data |

**Why this order:**
S18 makes the business-case promise true in code. S19 proves the doorbell model on the most real event in the system (a pending approval). S18+S19 together produce the first complete "middle-office copilot" demo. S20/S21 are the commercial path. Pre-pilot compliance is a legal prerequisite, not optional.

---

## 7. Identified Gaps (Code vs. Business Case)

| Gap | Location | Risk | Sprint fix |
|---|---|---|---|
| `AUTO_APPROVE_THRESHOLD` hardcoded | `verdict.py` line ~40 | Business-case §3 "shadow = config" is false | T18-1 |
| No system↔human match tracking | Missing table/API | Cannot demonstrate pilot metrics (§6) | T18-2 |
| Credit memo not standardized | `main_prompts.py` / `main_skill.py` | Primary product is inconsistent | T18-3 |
| Docs still pitch "approval machine" | `README.md`, `docs/business-case.md` | Misalignment with new positioning | T18-4 |
| No outbound notification | `notify/` | Bank staff don't know a case needs attention | T19-1 |
| No deep-link into Control Tower | `App.tsx` | Notification useless without navigation | T19-2 |

---

## 8. Sources

- SHB SAHA app launch: [vnexpress.net, 18 Jun 2025](https://vnexpress.net) (confirmed via web search)
- SHBFinance 5-minute approval: confirmed product page (web search Aug 2026)
- TT 06/2023/TT-NHNN: electronic consumer lending regulation
- TT 64/2024/TT-NHNN: Open API framework for credit institutions, effective 1 Mar 2025
- Law 91/2025/QH15: Personal Data Protection Law, effective 1 Jan 2026
- NĐ 94/2025/NĐ-CP: Fintech sandbox, effective 1 Jul 2025
- McKinsey Global Institute (2024): "The economic potential of generative AI" — agentic AI in financial services
- Bench results: `bench/REPORT.md` in repo (S17 benchmark, 15 cases)
- Code audit: `verdict.py`, `gated.py`, `notify/hooks.py`, `SPEC.md §14` (from repomix export)
