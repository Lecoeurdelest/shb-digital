# Sprint 8 — 2 PERSONA: cửa khách hàng + bàn duyệt ngân hàng (D-56, làm TRƯỚC S7)

> User chốt 18/7: app là CỬA KHÁCH — khách tự chat, đội chuyên gia số xử lý, khoản vừa/nhỏ agent
> tự duyệt theo ma trận, khoản lớn bắn về NGÂN HÀNG duyệt. Đảo D-54. Engine giữ 100% — sprint này
> là lớp persona + authz + UX. S7 (LAB legal port) hoãn nguyên dispatch, nối ngay sau.
> Seam đã có sẵn (soát kickoff): `conversations.user_id` (S1) · `_list_conversations_sync(user_id)`
> · `require_admin` (deps, compare đang dùng) · `users.role`.

## Theme
Role `customer` (khoanh: ca của mình, không nút duyệt, MAIN biết danh tính) vs role bank
(`admin` hiện hành: mọi ca + Tower + duyệt). Demo 2 cửa sổ cạnh nhau — phiếu bay real-time.

## Task

### T8-1 — Backend: role model + scoping + đảo authz (GATING — một mình trước)
- users: thêm cột `owner_id` (nullable — map account khách → customers/businesses seed). Seed
  ≥2 account khách: 1 cá nhân (map C0xx có employment_records sau này) + 1 DN (map B001).
- Conversations: bank thấy TẤT CẢ, customer chỉ ca mình (list + get + SSE + interrupt).
- Đảo D-54: decide/approvals + audit + Tower endpoints → bank-only (`require_admin` sẵn).
  Customer gọi decide → 403 4-field.
- MAIN identity inject: ca do customer tạo → context "khách hàng hiện tại = {owner_id} ({tên})"
  vào MAIN prompt; mặc định mọi tra cứu về khách này. Ca do bank tạo → như cũ.
- `/api/me` (hoặc mở rộng login response): trả `{username, role, owner_id}` cho FE gate.

### T8-2 — Frontend: view theo role + badge queue live (sau T8-1)
- Đọc role từ /api/me: customer → ẩn Tower + ẩn nút duyệt (card approval hiển thị
  "⏳ Đang chờ ngân hàng phê duyệt"); bank → như hiện tại + nút duyệt tại card + Tower.
- Badge live trên nút/queue Tower: SSE approval-card mới → badge đỏ (cảnh phiếu-bay 2 cửa sổ).
- Login form: đăng nhập account khách hoạt động trơn (demo mở 2 cửa sổ 2 account).

### T8-3 — Script demo v6 hai-cửa-sổ + MAIN skill tone khách (architect + frontend hỗ trợ)
- Cảnh chính mới: màn trái khách vay lớn → badge nổ màn phải → bank duyệt → màn trái tiền về.
- MAIN skill: xưng hô với KHÁCH (không phải nhân viên), không lộ thuật ngữ nội bộ khi chat khách.
- Fallback ghi rõ: 1 tab account bank (thấy hết, duyệt tại chỗ) = flow cũ.

### T8-4 — Tester: authz matrix + e2e 2-phía (xuyên suốt)
- Matrix: customer decide→403 · customer thấy ca người khác→404/rỗng · bank thấy hết · SSE ca
  người khác không leak · suite cũ 100%.
- E2e 2-browser-context (Chrome): khách tạo phiếu → bank context thấy badge/queue → duyệt →
  khách thấy receipt.

## Ngoài scope
Tool-level scoping chặt (khách A hỏi hồ sơ khách B qua CHAT — MAIN skill dặn nhưng không cưỡng
chế tầng tool) → ghi known-limitation, S sau nếu cần. Ma trận thẩm quyền nâng cao = S7 (lane LAB).

## Gate S8
Live 2 cửa sổ: khách login → chat vay ≥500tr → phiếu bay real-time sang cửa sổ bank (badge) →
bank duyệt → cửa sổ khách nhận receipt; khách gọi decide API → 403; khách không thấy ca người
khác. Suite ≥ 302 + matrix authz mới. Script v6 rehearsal 1 vòng 2-cửa-sổ.
