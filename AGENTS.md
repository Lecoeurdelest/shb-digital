# AGENTS.md — hướng dẫn cho AI agent làm việc trên repo này

> Bạn là AI coding agent (Claude Code, Cursor, Copilot…) đọc/sửa repo này? File này là điểm vào
> của bạn. Người đọc thì bắt đầu từ [`README.md`](README.md).

## Repo này là gì (1 câu)

Chi nhánh ngân hàng số multi-agent (đề #132 VAIC 2026): MAIN điều phối + 4 SUB chuyên gia dùng
tool thật trên Postgres, hành động nhạy cảm bị **phanh ở tầng tool** chờ người duyệt.

## Thứ tự đọc trước khi sửa code

1. [`SPEC.md`](SPEC.md) — sản phẩm + nguyên lý. **§14 = danh sách KHÔNG-làm** (không Redis,
   không WebSocket, không debounce, không outbox…) — đừng thêm primitive ngoài danh sách cho phép.
2. [`docs/CONTRACT.md`](docs/CONTRACT.md) — shape API/SSE/error. **Đổi shape → sửa file này TRƯỚC**,
   rồi mới sửa code cả 2 phía.
3. [`docs/patterns/00-INDEX.md`](docs/patterns/00-INDEX.md) — đọc đúng pattern theo phần bạn chạm
   (SDK session, dispatch/event, SSE, canvas/present, mount tool LAB).
4. [`DECISIONS.md`](DECISIONS.md) — quyết định còn sống (D-xx). Code có comment `D-xx` = tra ở đây.
5. `sprints/CURRENT.md` + `sprints/ROADMAP.md` — đang ở sprint nào, gate là gì.

## Lệnh chuẩn (đừng tự chế)

```bash
# DB dev
docker compose up -d db                                  # PG15 @ :5432 (shb/shb/shb)

# Backend — làm việc từ backend/
uv sync
uv run alembic upgrade head
uv run python -m app.db.seed_from_lab && uv run python -m app.db.seed_users
uv run uvicorn app.main:app --port 8000 --reload         # DUY NHẤT :8000 — không mọc port mới
uv run pytest                                            # set TEST_DATABASE_URL=...  để tách DB test
uv run ruff check . && uv run ruff format --check .

# Frontend — làm việc từ frontend/
npm install
VITE_USE_MOCK_API=false npm run dev                      # :5173, proxy /api → :8000
npm run test && npm run typecheck
```

## Quy ước code (đo được, review sẽ chặn nếu vi phạm)

- **Error toàn hệ = envelope 4-field** `{code, message, hint, retryable}` (raise `ApiError`,
  xem `backend/app/errors.py`). Success = **resource trần**, không bọc `{success, data}`.
- **File ≤ ~400 dòng** — dài hơn thì tách module. Không copy-paste logic (viết helper).
- Router không chứa business/SQL (service lo); migration Alembic phải **reversible**.
- Trên bề mặt model (prompt/tool result cho agent): dùng **tên role** (`credit`, `legal`…),
  **không** đưa `task_id`/UUID nội bộ — ID là chuyện của code/DB/FE.
- Test: assert hành vi quan sát được (không assert-not-None suông); phủ edge
  rỗng / None / max / malformed / error-path. FE test chạy jsdom — component WebGL phải
  guard no-op (xem `Lobby3D.tsx`).
- Comment tiếng Việt, giải thích **vì sao** (trade-off, D-xx) chứ không tả lại code.
- Secret chỉ ở `.env` (đã gitignore) — **không bao giờ** hardcode/commit key.

## Vùng cẩn trọng (đụng vào phải hiểu invariant)

- `backend/app/orch/gated.py` — phanh disburse: **`status='used' ⟺ có biên nhận`, cùng 1
  transaction**; retry sau thành công phải trả biên nhận cũ, không thực thi lần 2.
- `backend/app/orch/main_session.py` — SDK: connect/disconnect cùng asyncio task
  (cross-task disconnect = treo im lặng); MAIN resume phiên, SUB one-shot.
- `roles/legal/SKILL.md` — bản CERTIFIED (D-55), không sửa tay; tool nghiệp vụ trong
  `roles/*/functions.py` là đất của LAB — vỏ chỉ mount, không sửa logic nghiệp vụ.
- SSE (`backend/app/api/sse.py` + FE hook): emit **sau commit** DB; heartbeat là data-frame
  `{"type":"ping"}` — đừng đổi thành named event.

## Khi xong việc

Chạy đủ: `pytest` + `ruff` (BE) · `test` + `typecheck` (FE) — **100% pass rồi mới coi là xong**;
fail nào không giải thích được thì nghi môi trường/check trước khi nghi code. Mô tả thay đổi
kèm số liệu thật (test count, output), không tuyên bố suông.
