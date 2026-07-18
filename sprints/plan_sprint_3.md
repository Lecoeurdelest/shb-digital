# Sprint 3 — Plan (DRAFT — chưa kickoff)

<!-- DRAFT do architect nháp cuối S2. Kickoff S3 = đọc lại SPEC §4.4 + patterns + end_sprint_2,
     sửa IN-PLACE, append ## Kickoff. Không dispatch từ draft này. PHẦN KHÓ NHẤT cả hệ (D-29) —
     attention lớn nhất, review sâu nhất. -->

**Objective:** PHANH end-to-end (N2 gate cưỡng chế tầng tool) — `disburse` gated → phiếu
(pending→approved→used) + biên nhận chống-thực-thi-đôi + atomic claim + payload_hash + card
approval (chỉ vỏ sinh) + admin duyệt → event resume. Nối build-order §16 bước 4.
**Theme:** Phanh — két tiền cần chìa giám đốc (luật ở CÁI KÉT, không ở lời dặn).
**Gate S3 (SPEC §4.4):** "giải ngân 5 tỷ khi CHƯA duyệt" → két CHẶN (approval_required + phiếu
pending + card approval) → admin duyệt → Ops gọi lại tool → thực thi ĐÚNG 1 lần (loans.status=
disbursed) → gọi lại sau thành công → biên nhận cũ (KHÔNG thực thi đôi). 4 nhánh wrapper đủ.
**Baseline test count:** 126 (89 BE + 37 FE — end S3 ≥).

## Tasks (draft — chốt ở kickoff)

### T3-0 — Dev skip-auth (D-39, task nhỏ đầu S3)
- **Assignee:** backend + frontend
- **Mô tả:** BE env `DEV_SKIP_AUTH` → deps require_user/require_admin trả admin seed (1 chỗ) + boot cảnh báo; FE boot-check /api/auth/me → skip login vào Workspace admin. Flag OFF = auth cũ (T1-4++ giữ). Test flag ON→admin.
- **Verification:** flag ON → GET /conversations không-cookie → 200 admin; FE vào thẳng Workspace. Flag OFF → 401 + login như cũ. Test cả 2.

### T3-1 — Phanh wrapper gated + phiếu + biên nhận [GATING, TÂM ĐIỂM]
- **Assignee:** backend
- **Mô tả:** wrapper `gated(action, inner)` bọc `disburse` (whitelist) — 4 bước 1 transaction (lab-joint §2.1 + SPEC §4.4): biên nhận? → phiếu approved claim atomic? → pending? → tạo phiếu mới. payload_hash chuẩn hoá (1 hàm dùng chung). Bảng approvals migration. `disburse` = LAB stub (Ops chưa về — D-18) ghi loans.status=disbursed (D-21 write-back). Card approval VỎ tự sinh (§6, ngoài present enum).
- **Verification:** 4 nhánh đinh: (a) chưa phiếu → approval_required + phiếu pending + card, KHÔNG thực thi; (b) gọi lại pending → approval_pending, KHÔNG phiếu/card mới; (c) duyệt → gọi lại → chạy 1 lần + biên nhận + phiếu used; (d) gọi lại sau → biên nhận cũ. atomic claim (2 gọi đồng thời → 1 chạy).

### T3-2 — API approval + admin decide + event resume
- **Assignee:** backend
- **Mô tả:** GET /api/approvals?status=pending (admin) + POST /api/approvals/{id}/decide (atomic UPDATE WHERE pending → 409 nếu đã quyết) → SSE approval.decided + event resume main (multi-agent §8). SSE approval.pending khi phanh tạo phiếu.
- **Verification:** admin duyệt → event đánh thức main → main giao lại Ops → thực thi. decide 2 lần → 409.

### T3-3 — FE approval panel + queue + resume
- **Assignee:** frontend
- **Mô tả:** card approval render (nút Duyệt/Từ chối + lý do) + Control Tower approval queue (admin) + SSE approval.pending/decided → badge + resume. canvas-present §6.
- **Verification:** Chrome: ca disburse → panel approval hiện → admin duyệt → resume → thực thi. browser.

### T3-4 — Tester: gate S3 phanh end-to-end
- **Assignee:** tester
- **Mô tả:** verify 4 nhánh wrapper (đặc biệt atomic claim + biên nhận chống-đôi) + PG đối chiếu (approvals.status, loans.status, receipt) + gate S3 end-to-end. author≠checker.
- **Verification:** GATE S3 (§4.4) + suite ≥126 + browser approval flow.

---

---

## Kickoff — 2026-07-18

**Drift since draft (user nắn altitude phanh):**
- **D-40: phanh = HAPPY-PATH demo** (bấm-duyệt-UI chạy được), atomic/biên nhận = code cơ bản theo
  spec KHÔNG đào sâu, **BỎ crash-injection gate**. User chốt: "atomic là xử lý trường hợp lỗi app
  thật; demo happy-path không gặp". Gate S3 = chặn→duyệt→giải ngân (không dàn cảnh crash).
- **Vai: mọi người vào thẳng ADMIN** (D-39 skip-auth — người cấp cao dùng tool gated). Bỏ phân biệt
  RM/admin ở luồng demo (người chat=người duyệt=admin).
- **Atomicity seam (advisor + backend đồng thuận):** gated write → wrapper 1 conn/tx thread SAME
  conn vào tool → claim+execute+receipt atomic (chống money-doubling MỨC CƠ BẢN). Read tool giữ
  handler per-call. Viết vào T3-1 §C Logic.

**Plan revisions:**
- Gate S3 sửa: happy-path (D-40), không crash-injection. T3-4 verify 4 nhánh + payload_hash + browser, KHÔNG dàn crash.
- T3-0 skip-auth thêm (D-39, độc lập — dispatch trước). T3-1 §C thread-conn atomic.

**Final task list (chốt dispatch):**
- T3-0 → backend+frontend — skip-auth vào thẳng admin (độc lập, làm ngay)
- T3-1 → backend — GATING: wrapper gated 4-bước thread-conn + payload_hash + phiếu + card approval + disburse stub
- T3-2 → backend — API approval + decide + event resume
- T3-3 → frontend — approval panel + queue + boot-check skip-auth
- T3-4 → tester — gate S3 happy-path (chặn→duyệt→giải ngân) + 4 nhánh + authz

## Findings/nợ mang sang từ S2 (xử ở S3)
- D-33 inline-await: nếu T3 thêm CTX_APPROVAL (phiếu context) → PHẢI reset ở run_main_turn (comment site).
- D-34 store.py 409 LOC → tách module (approvals CRUD thêm sẽ phình tiếp).
- §9 main-retry: approval resume qua restart cần main bền — cân nhắc làm.
- Nợ LAB D-35: skill thật dạy present (provisional D-36 mồi).
