# Sprint 11 — Cleanup + Docs + Nâng điểm chấm (kickoff 2026-07-18)

> Theme gốc ROADMAP (cleanup + METHODOLOGY) + backlog bổ sung từ BẢN REVIEW NGOÀI user đưa
> (phản biện đã chốt: một nửa A là artifact bản-backup — lockfile ĐÃ commit, venv/node_modules
> gitignored; phần NHẬN: CI, README-60s, 4 refactor gated, English docstring). Không primitive
> mới — CI/refactor là tooling + dọn, không phình app.

## Task

### T11-1 — CI GitHub Actions (backend, gating cho badge)
`.github/workflows/ci.yml`: job BE (PG 15 service → uv sync --frozen → alembic upgrade →
seed → `TEST_DATABASE_URL` pytest → ruff check + format --check) + job FE (npm ci → vitest →
tsc). Live-SDK test tự skip (không key trong CI — đúng thiết kế RUN_LIVE_SDK). Badge vào README.
= "bằng chứng khách quan suite xanh" — điểm đúng nhất của review.

### T11-2 — Refactor gated.py (backend, sau T11-1) — HÀNH VI 0 ĐỔI
(a) tách `_gated_txn` 5 nhánh → helper per-nhánh, GIỮ NGUYÊN 1 transaction + thứ tự khoá
(tách tx = phá auditability — cấm); (b) trích `_run_and_receipt(conn, cur, approval_id,
action, args)` khử lặp claim/auto (nợ "step-2 pattern" tự ghi từ S5); (c) except cửa-cuối GIỮ
pattern trả-4-field nhưng `log.exception` full traceback; (d) Protocol type cho conn-quack +
TypedDict biên nhận ở GATED_TOOLS. Guard: 33 money-test + suite pass KHÔNG SỬA TEST.

### T11-3 — Docs (architect): METHODOLOGY + README-60s + hygiene
Review draft `.archive/drafts/METHODOLOGY.draft-s11.md` (206 dòng, subagent viết, khai-thật)
→ spot-check claims với repo → `docs/METHODOLOGY.md`. README: mục "Chạy thử 60 giây" nổi bật
`docker compose -f docker-compose.prod.yml up` (full stack + seed tự động) + badge CI. Cleanup:
dọn worktree/branch chết, archive nháp, DECISIONS soát entry đã tiêu hoá.

### T11-4 — FE polish nhẹ (frontend)
Tooltip "Đăng nhập với Google" sót khi nút ẩn (finding tester) + English docstring ngắn cho
public API surface FE (api/client.ts exported fns). Vitest giữ.

### T11-5 — English docstring public API BE (backend, gộp T11-2 batch)
Router endpoints + tool registry signatures: 1 dòng English mỗi cái (thân comment tiếng Việt
GIỮ — giám khảo VAIC/SHB là người Việt, phản biện đã chốt; English chỉ ở surface).

## Treo chờ user (không block)
- GOOGLE_CLIENT_ID/SECRET → bật đăng nhập Google thật (code sẵn, disabled sạch).
- Rehearsal restart-giữa-ca trên VM: QUYẾT để TRƯỚC GIỜ G ghép vòng rehearsal tay (cần ca live
  + mắt người) — ghi ROADMAP, không thành task S11.

## Gate S11
CI xanh trên GitHub (badge thật) · suite ≥ 465 sau refactor KHÔNG sửa test · METHODOLOGY merged
khai-thật · README 60s chạy được từ clone trần (verify 1 lần bằng compose local) · tester
regression 1 vòng nhanh trên prod sau redeploy cuối (nhặt durable-fix 6ec86bc còn chờ).
