# Digital Expert Guild — SYSTEM #132

> **Chi nhánh ngân hàng số vận hành bằng một đội chuyên gia AI** — khách hàng chat một câu tiếng Việt,
> đội agent (Tín dụng · Pháp chế · Sản phẩm · Vận hành) tự chia việc, dùng tool, phối hợp và **thực thi
> hành động có phanh**: khoản nhỏ tự duyệt theo ma trận thẩm quyền, khoản lớn dừng chờ người duyệt.
> Mọi bước có vết, mọi con số có nguồn.

Đề **#132 — Digital Expert Agents**, Vietnam AI Innovation Challenge 2026 / Hack CX Together 2026
([đề bài](docs/problem-statement.md) · [PDF gốc](docs/132-SHB-agents.pdf)). Demo: **https://digital.tinhdev.com**

![Landing](docs/assets/landing.png)

> 🤖 **Bạn là AI agent đọc repo này?** Bắt đầu từ [`AGENTS.md`](AGENTS.md) — lệnh chạy/test,
> quy ước code, và thứ tự đọc tài liệu dành riêng cho bạn.

---

## Sản phẩm trong 60 giây

Hai persona, một hệ thống (D-56):

- **Cửa khách hàng** — khách đăng nhập (username/password, đăng ký mới, hoặc Google), chat với đội
  chuyên gia số như đến chi nhánh thật. Hệ tự biết khách là ai, hỏi đủ mục đích/tài sản, trả kết quả
  thẩm định bằng **card có nguồn** (DSCR, pháp lý, gói vay) trên canvas + **lobby 3D** nhìn thấy
  từng phòng ban đang làm việc.
- **Bàn ngân hàng** — admin thấy mọi ca + **Control Tower**: hàng đợi phiếu duyệt, trace từng
  tool-call, audit log, cost. Phiếu giải ngân lớn "bay" sang bàn này real-time chờ người bấm nút.

![Lobby 3D](docs/assets/lobby-3d.png)

**5 deliverable đề bài → chỗ trả trong sản phẩm:**

| # | Đề #132 yêu cầu | Trả bằng |
|---|---|---|
| 1 | ≥2–3 chuyên gia cộng tác trên 1 request phức tạp | Ca "vay 5 tỷ": credit + legal + products + ops chạy song song, card đổ về canvas |
| 2 | Planner phân rã → executor | MAIN (phiên bền, resume qua restart) + `orch_dispatch` fire-and-forget + event đánh thức |
| 3 | Tool use thật, hành động cụ thể | Tool đọc Postgres thật (DSCR/CIC/pháp lý); `disburse` **gated tầng tool**: phiếu payload-hash single-use, ma trận ≤500tr tự duyệt (`decided_by=auto-rule`), >500tr chờ người |
| 4 | Dashboard traces / status / decisions | Control Tower: approval queue + thinking/tool trace live (SSE) + audit append-only + cost |
| 5 | So sánh single-agent vs multi-agent | `POST /api/compare` — 2 bản chạy cùng câu hỏi, render 2 cột |

---

## Kiến trúc

```mermaid
flowchart LR
  KH[Khách hàng / RM] -->|chat tiếng Việt| FE[React SPA<br/>canvas · lobby 3D · SSE]
  FE -->|REST + SSE cookie JWT| API[FastAPI · 1 worker]
  API --> MAIN[MAIN — điều phối<br/>phiên bền, resume]
  MAIN -->|orch_dispatch<br/>fire-and-forget| SUB[SUB: Tín dụng · Pháp chế<br/>Sản phẩm · Vận hành]
  SUB -->|tool đọc/ghi| PG[(Postgres 15<br/>nghiệp vụ + render + audit)]
  SUB -->|present card| FE
  SUB -->|disburse| GATE{{PHANH tầng tool<br/>phiếu payload-hash}}
  GATE -->|≤500tr| AUTO[tự duyệt auto-rule<br/>+ biên nhận]
  GATE -->|>500tr| BANK[Bàn duyệt ngân hàng<br/>Control Tower]
  BANK -->|approved/rejected| MAIN
```

Nguyên tắc lõi (đầy đủ trong [`SPEC.md`](SPEC.md)):

- **MAIN là não, vỏ là cơ chế** — vỏ (orchestrator) không ép "đợi đủ N sub"; điều phối là suy nghĩ
  của model. MAIN = phiên bền (resume từ disk); SUB = client tươi, xong việc là bỏ.
- **Phanh nằm ở TẦNG TOOL, không phải lời dặn trong prompt** — `disburse` bị wrapper chặn bằng
  phiếu `(conversation, action, payload_hash)` single-use, claim atomic, biên nhận chống thực-thi-đôi.
- **Không nhẩm** — mọi chỉ số (DSCR, LTV…) tính bằng tool, card nào cũng mang chip nguồn truy ngược được.
- **Hợp đồng 1 nguồn sự thật** — API/SSE/error shape chốt tại [`docs/CONTRACT.md`](docs/CONTRACT.md):
  success = resource trần, error = 4-field `{code, message, hint, retryable}` toàn hệ.

**Stack:** Python 3.11 · FastAPI + uvicorn (1 worker) · claude-agent-sdk (multi-provider, D-45) ·
Postgres 15 (SQLAlchemy + Alembic) · React + Vite + TypeScript · three.js (lobby 3D) · SSE (không WebSocket).

---

## Chạy local

Yêu cầu: Docker, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
# 1. Database
docker compose up -d db                    # Postgres 15 @ localhost:5432 (shb/shb/shb)

# 2. Backend  (http://localhost:8000)
cd backend
uv sync
uv run alembic upgrade head                # schema
uv run python -m app.db.seed_from_lab      # data nghiệp vụ (fallback snapshot deploy/seed/)
uv run python -m app.db.seed_users         # account demo
uv run uvicorn app.main:app --port 8000 --reload

# 3. Frontend  (http://localhost:5173)
cd frontend
npm install
VITE_USE_MOCK_API=false npm run dev
```

Test & lint:

```bash
cd backend  && uv run pytest && uv run ruff check .        # TEST_DATABASE_URL=... để tách DB test
cd frontend && npm run test  && npm run typecheck
```

### Tài khoản demo

| Account | Vai | Thấy gì |
|---|---|---|
| `b001 / b001` | Khách doanh nghiệp (B001) | Cửa khách — chỉ ca của mình |
| `c001 / c001` | Khách cá nhân (C001) | Cửa khách |
| `admin / admin` | Ngân hàng | Mọi ca + Control Tower + duyệt phiếu |
| `user / user` | RM | Workspace nhân viên |

Khách mới: nút **Đăng ký** hoặc **Đăng nhập với Google** (tự tạo tài khoản khách).

### Cấu hình (env)

Không commit secret — `.env` đã gitignore. Các biến chính:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | `postgresql://shb:shb@localhost:5432/shb` | Postgres |
| `SHB_PROVIDER` (+ key) | CLI subscription | Provider LLM cho MAIN/SUB (vd `zai` — keyed, chạy headless/container) |
| `DEV_SKIP_AUTH` | `0` | `1` = bỏ login, mọi request là admin (chỉ dev) |
| `JWT_SECRET` | dev-only | Đặt secret thật khi deploy |
| `AUTH_GOOGLE_ENABLED` + `GOOGLE_OAUTH_CLIENT_ID/SECRET` | off | Đăng nhập Google |
| `COOKIE_SECURE` | `0` | `1` trên HTTPS |
| `SMTP_USER/SMTP_APP_PASSWORD` | off | Mail thông báo Gmail (S9) — thiếu env thì no-op sạch |

Deploy production (Docker + cloudflared → `digital.tinhdev.com`): xem [`docs/deploy.md`](docs/deploy.md).

---

## Bản đồ repo

| Đường dẫn | Là gì |
|---|---|
| [`SPEC.md`](SPEC.md) | Sản phẩm là gì — nguyên lý → cơ chế → contract → rule (kể cả §14 KHÔNG-làm) |
| [`docs/CONTRACT.md`](docs/CONTRACT.md) | Hợp đồng API + SSE + error envelope — 1 nguồn sự thật FE↔BE |
| [`docs/patterns/`](docs/patterns/00-INDEX.md) | Cách build từng phần (SDK, multi-agent, SSE, canvas, lab-joint) |
| [`docs/demo-script.md`](docs/demo-script.md) | Kịch bản demo 2 cửa sổ ~10-13 phút (5 deliverable trong 1 mạch chuyện) |
| [`docs/deploy.md`](docs/deploy.md) | Deploy Docker + cloudflared, seed snapshot, rollback |
| [`DECISIONS.md`](DECISIONS.md) | Sổ quyết định ngoài-dự-tính — human-wins, mỗi entry có "cách đổi" |
| [`sprints/`](sprints/ROADMAP.md) | ROADMAP + plan/end từng sprint — số liệu thật, gate thật, waiver thật |
| `backend/` | FastAPI: `app/orch` (MAIN/SUB/dispatch/phanh) · `app/mount` (tool LAB) · `app/api` · `app/auth` · `app/db` |
| `frontend/` | React SPA: Workspace (chat + canvas + lobby 3D) · Control Tower · Landing |
| `roles/` | Labpack per chuyên gia: `SKILL.md` + `functions.py` (tool nghiệp vụ) |
| `design/` | Mock look-and-feel từ Claude Design (tham khảo — scope theo SPEC, D-13) |

## Quy trình build (điểm khác biệt)

Repo này do **đội AI agent tự build** theo vòng lặp *BUILD → SAI → UPDATE → LOOP*: tester độc lập
verify từng task trên kết quả thật (suite → tool → API → browser), architect review + commit theo
task, mỗi sprint đóng bằng 3 quality gates; hơn **380 test tự động** (BE + FE) tại S9. Quyết định
ngoài dự tính ghi `DECISIONS.md` để con người đọc lại và có quyền lật (human-wins). Lịch sử đầy đủ,
kể cả sai lầm và waiver, nằm trong `sprints/end_sprint_*.md` — không tô hồng.

**Trạng thái:** Sprint 1–8 đã đóng (spine → canvas → phanh → Control Tower → demo-safety → pháp lý
3 trụ → 2 persona) · S9 (khách mới + mail + bell) đang chạy · S10 deploy · xem [ROADMAP](sprints/ROADMAP.md).
