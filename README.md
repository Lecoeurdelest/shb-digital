# Digital Expert Guild — SYSTEM #132

Hệ thống **chi nhánh ngân hàng số vận hành bằng đội multi-agent AI**: khách hàng chat một câu
tiếng Việt, đội chuyên gia số (Tín dụng · Pháp chế · Sản phẩm · Vận hành) tự lập kế hoạch, dùng
tool truy vấn dữ liệu thật, phối hợp với nhau và **thực thi hành động có kiểm soát** — khoản nhỏ
tự duyệt theo ma trận thẩm quyền, khoản lớn dừng lại chờ người của ngân hàng duyệt. Mọi bước có
vết, mọi con số có nguồn.

Sản phẩm dự thi đề **#132 — Digital Expert Agents** (Vietnam AI Innovation Challenge 2026 /
Hack CX Together 2026 · SHB). Đề bài: [`docs/problem-statement.md`](docs/problem-statement.md) ·
PDF gốc: [`docs/132-SHB-agents.pdf`](docs/132-SHB-agents.pdf).

**Demo trực tuyến:** https://digital.tinhdev.com

![Landing page](docs/assets/landing.png)

> 🤖 **AI agent đọc/sửa repo này** → bắt đầu từ [`AGENTS.md`](AGENTS.md) (lệnh chuẩn, quy ước
> code, vùng cẩn trọng). Người đọc tiếp tục bên dưới.

---

## Mục lục

- [Tính năng chính](#tính-năng-chính)
- [Đáp ứng đề bài (5 deliverables)](#đáp-ứng-đề-bài-5-deliverables)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Cài đặt & chạy local](#cài-đặt--chạy-local)
- [Kiểm thử](#kiểm-thử)
- [API chính](#api-chính)
- [Tài liệu](#tài-liệu)
- [Quy trình phát triển](#quy-trình-phát-triển)

---

## Tính năng chính

Hệ thống có **hai persona trên cùng một nền** (quyết định D-56):

**Cửa khách hàng** — như đến chi nhánh thật, nhưng là chi nhánh số:

- Đăng nhập bằng username/password, **đăng ký tài khoản mới**, hoặc **Sign in with Google**
  (tài khoản khách tạo tự động).
- Chat tiếng Việt tự nhiên với đội chuyên gia; hệ tự biết khách là ai (inject danh tính),
  khách mới thì có **form tiếp nhận hồ sơ** ngay trong hội thoại.
- Xem đội làm việc trực quan: **lobby 3D** (chi nhánh ngân hàng — từng chuyên gia sáng đèn khi
  đang chạy), khối "diễn tiến đội" hiện suy nghĩ + tool-call theo thời gian thực (SSE).
- Nhận kết quả dạng **card có nguồn**: DSCR/LTV/CIC, kết luận pháp lý 3 trụ, gói vay đề xuất —
  mỗi con số có chip nguồn truy ngược được về tool đã tính ra nó.
- Yêu cầu giải ngân: **≤ 500 triệu** — agent tự duyệt theo ma trận thẩm quyền (phiếu vẫn ghi
  `decided_by=auto-rule` + lý do, audit đầy đủ); **> 500 triệu** — tạo phiếu chờ ngân hàng duyệt,
  khách thấy trạng thái "chờ ngân hàng".

**Bàn ngân hàng (admin)** — giám sát và cầm quyền quyết:

- Thấy mọi ca của mọi khách + **Control Tower**: hàng đợi phiếu duyệt (badge real-time),
  audit log append-only từng LLM call/tool call kèm chi phí, trace timeline.
- Duyệt / từ chối phiếu giải ngân — hệ đánh thức đúng ca, đội thực thi tiếp **đúng một lần**
  (biên nhận chống thực-thi-đôi; bấm lại trả biên nhận cũ).
- Click từng chuyên gia xem brief/trace/kết quả; hủy một sub đang chạy không ảnh hưởng sub khác.
- Thông báo: chuông in-app + email Gmail thật khi có phiếu chờ duyệt / ca xong (tùy chọn env).

![Lobby 3D — chi nhánh ngân hàng số](docs/assets/lobby-3d.png)

## Đáp ứng đề bài (5 deliverables)

| # | Đề #132 yêu cầu | Sản phẩm trả bằng |
|---|---|---|
| 1 | Demo ≥ 2–3 chuyên gia số cộng tác trên một request phức tạp | Ca "DN vay 5 tỷ": Tín dụng + Pháp chế + Sản phẩm + Vận hành chạy song song, card đổ về canvas |
| 2 | Cơ chế orchestration: planner phân rã → executor | MAIN (planner, phiên bền — resume qua restart) + `orch_dispatch` giao việc nền + event đánh thức khi sub xong |
| 3 | Tool use thật — hành động cụ thể, không chỉ text | Tool đọc/ghi Postgres thật (DSCR, CIC, pháp lý…); `disburse` bị **chặn ở tầng tool** bằng phiếu phê duyệt |
| 4 | Dashboard traces, task status, decisions, collaboration flows | Control Tower + SSE trace (thinking/toolcall) + audit append-only + lobby/task map |
| 5 | So sánh single-agent chatbot vs hệ action-oriented agents | `POST /api/compare` — chạy cùng câu hỏi 2 chế độ, render đối chiếu 2 cột |

## Kiến trúc hệ thống

```mermaid
flowchart LR
  KH[Khách hàng / RM] -->|chat tiếng Việt| FE[React SPA<br/>chat · canvas · lobby 3D]
  FE -->|REST + SSE, cookie JWT| API[FastAPI · 1 worker]
  API --> MAIN[MAIN — điều phối viên<br/>phiên bền, resume từ disk]
  MAIN -->|orch_dispatch<br/>fire-and-forget · idempotent| SUB[4 SUB chuyên gia<br/>Tín dụng · Pháp chế · Sản phẩm · Vận hành]
  SUB -->|tool nghiệp vụ| PG[(Postgres 15<br/>nghiệp vụ + render + audit)]
  SUB -->|present card| FE
  SUB -->|disburse| GATE{{PHANH tầng tool<br/>phiếu payload-hash · single-use}}
  GATE -->|"≤ 500tr (ma trận)"| AUTO[Tự duyệt auto-rule<br/>+ biên nhận]
  GATE -->|"> 500tr"| BANK[Bàn duyệt ngân hàng<br/>Control Tower]
  BANK -->|approved / rejected| MAIN
```

Các thành phần chính:

| Thành phần | Vai trò | Code |
|---|---|---|
| **MAIN** | Điều phối viên: phân rã yêu cầu, giao việc, hòa giải mâu thuẫn, tổng hợp trả lời. Phiên bền — server restart vẫn resume đúng hội thoại | `backend/app/orch/main_session.py` |
| **SUB** (×4) | Chuyên gia domain, client tươi mỗi lượt: nhận brief → dùng tool → `present` card → trả kết quả | `backend/app/orch/sub_runner.py` |
| **Orchestrator (vỏ)** | Dispatch nền idempotent, hàng đợi event, đánh thức MAIN khi sub xong — vỏ **không** ép logic "đợi đủ N sub" (điều phối là suy nghĩ của model) | `backend/app/orch/` |
| **Phanh (approval gate)** | Wrapper tầng tool cho hành động nhạy cảm: phiếu `(conversation, action, payload_hash)` single-use, claim atomic, biên nhận trong cùng transaction — retry không thực thi đôi | `backend/app/orch/gated.py` |
| **Mount tool LAB** | Nạp tool nghiệp vụ + SKILL per chuyên gia từ `roles/` (labpack) — vỏ cấp connection, không sửa logic nghiệp vụ | `backend/app/mount/` |
| **Canvas / present** | Card có cấu trúc (metric, bảng, document, approval, form…) do agent trình bày, stream về FE qua SSE | `backend/app/orch/common_tools.py` + `frontend/src/components/cards/` |
| **Control Tower** | Màn admin: approval queue, audit, trace, cost | `frontend/src/components/ControlTower.tsx` |

Nguyên tắc thiết kế (đầy đủ trong [`SPEC.md`](SPEC.md)):

- **Phanh nằm ở tầng tool, không phải lời dặn trong prompt** — model không thể "lách" bằng văn.
- **Không nhẩm** — mọi chỉ số tính bằng tool; card nào cũng truy ngược được nguồn.
- **Hợp đồng một nguồn sự thật** ([`docs/CONTRACT.md`](docs/CONTRACT.md)): success trả resource
  trần; error toàn hệ một shape `{code, message, hint, retryable}`.
- **Tối giản có chủ đích** (SPEC §14): không Redis, không WebSocket (SSE đủ), không replay-cursor —
  reconnect thì tải lại full-state.

## Công nghệ sử dụng

| Lớp | Công nghệ |
|---|---|
| Backend | Python 3.11 · FastAPI + uvicorn (1 worker) · SQLAlchemy + Alembic · psycopg2 |
| Agent runtime | **claude-agent-sdk** — multi-provider qua registry (Anthropic subscription hoặc provider keyed như `zai` cho container/headless) |
| Database | PostgreSQL 15 (data nghiệp vụ + render + audit cùng một DB) |
| Frontend | React 19 + Vite + TypeScript · three.js (lobby 3D) · SSE (EventSource) |
| Auth | JWT cookie httponly · bcrypt · Google OAuth 2.0 (authorization-code, server-side) |
| Kiểm thử | pytest (BE) · vitest + Testing Library (FE) · ruff · tsc |
| Deploy | Docker Compose · nginx (FE + proxy /api) · cloudflared tunnel |

## Cấu trúc thư mục

```
shb-digital/
├── README.md · AGENTS.md · SPEC.md · DECISIONS.md
├── docker-compose.yml            # DB dev; bản prod: docker-compose.prod.yml
├── backend/
│   ├── app/
│   │   ├── api/                  # REST + SSE: conversations, approvals, audit, compare, …
│   │   ├── auth/                 # login/register/me · JWT cookie · Google OAuth
│   │   ├── orch/                 # MAIN/SUB, dispatch, event, phanh (gated.py), store
│   │   ├── mount/                # mount tool LAB per role (schema + PG adapter)
│   │   └── db/                   # models, migrations (Alembic), seeds
│   └── tests/                    # pytest — chạy được với TEST_DATABASE_URL riêng
├── frontend/
│   └── src/
│       ├── components/           # Workspace, Canvas, Lobby3D, ControlTower, Landing, cards/
│       ├── api/                  # cổng duy nhất gọi backend (client thật + mock theo cờ env)
│       └── types.ts              # shape khớp docs/CONTRACT.md
├── roles/                        # labpack per chuyên gia: SKILL.md + functions.py (tool nghiệp vụ)
├── docs/                         # đề bài · CONTRACT · patterns/ · demo-script · deploy (+ mục lục docs/README.md)
├── sprints/                      # ROADMAP + plan/end từng sprint (số liệu thật, gate, waiver)
├── design/                       # mock look-and-feel (Claude Design) — tham khảo, scope theo SPEC
└── deploy/seed/                  # snapshot seed để deploy tự chứa (D-62)
```

## Cài đặt & chạy local

### ⚡ Chạy thử 60 giây (chỉ cần Docker)

```bash
git clone https://github.com/tinhnguyen0110/shb-digital.git && cd shb-digital
cp .env.example .env                       # điền key provider (zai/wrap) nếu muốn chat thật
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
# → mở http://localhost:3011  (DB + migration + seed nghiệp vụ TỰ ĐỘNG — seed-if-empty)
#   account demo: admin/admin (ngân hàng) · c019/c019, b001/b001 (khách) — hoặc Đăng ký mới
```

1 lệnh dựng trọn stack (Postgres + backend + frontend, project `shb132-prod` cô lập). Không có
API key thì UI/DB/audit vẫn xem đủ; chat cần 1 key provider trong `.env`.

### Chạy dev (hot-reload)

Yêu cầu: **Docker** · **[uv](https://docs.astral.sh/uv/)** (Python package manager) · **Node.js 20+**.

```bash
git clone https://github.com/tinhnguyen0110/shb-digital.git
cd shb-digital

# 1) Database — Postgres 15 tại localhost:5432 (db/user/pass: shb/shb/shb)
docker compose up -d db

# 2) Backend — http://localhost:8000
cd backend
uv sync                                    # cài dependencies
uv run alembic upgrade head                # tạo schema
uv run python -m app.db.seed_from_lab      # seed data nghiệp vụ (fallback snapshot deploy/seed/)
uv run python -m app.db.seed_users         # seed tài khoản demo
uv run uvicorn app.main:app --port 8000 --reload

# 3) Frontend — http://localhost:5173 (proxy /api → :8000)
cd ../frontend
npm install
VITE_USE_MOCK_API=false npm run dev
```

Mở http://localhost:5173 và đăng nhập bằng tài khoản đã seed.

Ghi chú:

- Muốn agent chạy thật cần credential LLM: hoặc đăng nhập Claude CLI trên máy (subscription),
  hoặc đặt `SHB_PROVIDER=<tên>` + key tương ứng trong `.env` (gitignored).
- `DEV_SKIP_AUTH=1` bỏ qua màn login (mọi request là admin) — chỉ dùng khi dev.
- Reset dữ liệu demo về ban đầu: `uv run python -m app.db.reset_demo` (không xoá tài khoản).

## Kiểm thử

```bash
# Backend — ~300 test (pytest); nên tách DB test
cd backend
TEST_DATABASE_URL=postgresql://shb:shb@localhost:5432/shb_test uv run pytest
uv run ruff check . && uv run ruff format --check .

# Frontend — ~90 test (vitest) + typecheck
cd frontend
npm run test
npm run typecheck
```

Quy ước kiểm thử: suite phải **100% pass** trước khi đóng task; test assert hành vi quan sát
được, phủ edge case (rỗng/None/max/malformed/error-path); component WebGL guard no-op trong
jsdom. Chi tiết per-sprint: `sprints/end_sprint_*.md`.

## API chính

Đầy đủ shape (request/response/SSE/error) tại [`docs/CONTRACT.md`](docs/CONTRACT.md). Quy ước:
success = resource trần; error = `{code, message, hint, retryable}`; auth qua cookie JWT.

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/auth/login` · `/api/auth/register` | Đăng nhập / đăng ký (auto-login, set cookie) |
| GET | `/api/me` | Boot-check phiên: `{username, role, owner_id}` |
| GET/POST | `/api/conversations` | Danh sách / tạo ca tư vấn |
| GET | `/api/conversations/{id}` | Full-state một ca (messages, tasks, cards) — nguồn sự thật khi reconnect |
| POST | `/api/conversations/{id}/chat` | Gửi tin nhắn (202 — kết quả stream qua SSE) |
| GET | `/api/conversations/{id}/sse` | Stream SSE: message/status/card/task/thinking/toolcall/approval |
| POST | `/api/conversations/{id}/form-submit` | Khách nộp form hồ sơ (card `form`) |
| POST | `/api/conversations/{id}/interrupt` | Hủy một sub đang chạy |
| GET | `/api/approvals?status=pending` | Hàng đợi phiếu duyệt (admin) |
| POST | `/api/approvals/{id}/decide` | Duyệt/từ chối phiếu — đánh thức đúng ca (idempotent, 409 nếu đã quyết) |
| GET | `/api/audit` | Audit log tool-call (filter theo ca/task) |
| GET | `/api/models` | Provider + model khả dụng |
| POST | `/api/compare` | Chạy so sánh single-agent vs multi-agent |

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [`SPEC.md`](SPEC.md) | Đặc tả sản phẩm: nguyên lý → kiến trúc → cơ chế → rule (kể cả mục KHÔNG-làm) |
| [`docs/CONTRACT.md`](docs/CONTRACT.md) | Hợp đồng API + SSE + error — một nguồn sự thật FE↔BE |
| [`docs/patterns/`](docs/patterns/00-INDEX.md) | 5 pattern build: SDK session · multi-agent · SSE · canvas/present · mount tool LAB |
| [`docs/demo-script.md`](docs/demo-script.md) | Kịch bản demo ~10-13 phút, 2 cửa sổ khách ‖ ngân hàng |
| [`docs/deploy.md`](docs/deploy.md) | Deploy + vận hành + rollback |
| [`DECISIONS.md`](DECISIONS.md) | Sổ quyết định — mỗi entry ghi *quyết gì / vì sao / cách đổi* (human-wins) |
| [`sprints/ROADMAP.md`](sprints/ROADMAP.md) | Lộ trình + trạng thái từng sprint |
| [`AGENTS.md`](AGENTS.md) | Hướng dẫn cho AI coding agent làm việc trên repo |

## Quy trình phát triển

Repo này được xây bởi **đội AI agent** (điều phối bởi con người) theo vòng lặp
*BUILD → SAI → UPDATE → LOOP*:

- **Tester độc lập** (author ≠ checker) verify từng task trên kết quả thật: suite → tool → API →
  browser; fail trả feedback 5 mục (expected/actual/repro/nghi vấn/mức độ) để implementer sửa.
- **Commit theo task** sau khi tester pass + review; mỗi sprint đóng bằng **3 quality gates**
  (API / function / sprint) — số liệu chạy lại độc lập ghi ở `sprints/end_sprint_*.md`,
  kể cả waiver và lỗi đã gặp (không tô hồng).
- Quyết định ngoài dự tính ghi `DECISIONS.md` để con người đọc lại async và có quyền lật.

**Trạng thái hiện tại:** Sprint 1–8 đã đóng (spine → canvas + 4 chuyên gia → phanh → Control
Tower + trace → demo-safety → pháp lý 3 trụ → 2 persona) · Sprint 9 (khách mới + form intake +
mail/bell) đang chạy · Sprint 10 deploy. Chi tiết: [`sprints/ROADMAP.md`](sprints/ROADMAP.md).
