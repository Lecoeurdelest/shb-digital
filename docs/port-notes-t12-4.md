# T12-4 merge-spec (architect diff xong 19/7 — BE áp theo đây, tester verify sau khi retrieval sống)

## 1. `roles/legal/SKILL.md` — APPEND nguyên văn
Diff chốt: LAB = VỎ + đúng 12 dòng cuối (block "## SÁCH TRA CỨU ..." + TRIGGER), KHÔNG dính brand.
→ Append nguyên văn 12 dòng từ `missions/shb-132/skills/legal/SKILL.md` (dòng 50-61) vào cuối
file VỎ. Giữ nguyên comment D-61 + danh xưng BANK Digital hiện có. Ghi 1 dòng deviation dưới
comment D-61: `<!-- T12-4: block SÁCH TRA CỨU append từ LAB (bơm sau certify v3 — user chấp
nhận nguyên trạng, D-65a) -->`.

## 2. `roles/credit/SKILL.md` — APPEND nguyên văn
Cùng dạng: LAB = VỎ + 11 dòng cuối (SÁCH TRA CỨU + TRIGGER notes_search). Append nguyên văn
(dòng 41-51 file LAB) + cùng dòng deviation comment như legal.

## 3. `backend/app/orch/main_skill.py` — CHERRY từ planner v0 (KHÔNG đổi kiến trúc)
Planner LAB là orchestrator-rig đồng bộ; MAIN VỎ là Claude-Code-clone (dispatch nền + event).
KHÔNG bê nguyên — cherry 6 luật đã "trả giá bằng án thật" vào MAIN_SKILL:

(a) **Sửa D-52 bước 2**: "tóm TẮT kết quả tín dụng vào brief" → "chuyển NGUYÊN VĂN verdict +
    số liệu tín dụng vào brief (không tóm, không làm tròn — mọi số truy được về tool phòng gốc)".
(b) **Thêm chuỗi chuẩn ca vay mới có Products** (khi products đã port T12-3): Credit → Legal →
    Products (nếu eligible) → Operations. Câu hỏi thường vẫn fan-out song song (giữ nguyên).
(c) **Thêm mục HOÀ GIẢI CÓ NGHI THỨC**: 2 phòng mâu thuẫn → KHÔNG tự phân xử; nêu cả hai nguyên
    văn + điểm lệch + đường xử (thường: phòng nguồn tính lại với dữ liệu mới). Ca mẫu: Legal
    flag lương-lệch → giao Credit re-assess với income_override (credit_assess có sẵn tham số)
    → verdict mới thay cũ, GHI RÕ vì sao.
(d) **Thêm mục DISCLOSURE VỚI KHÁCH** (role=customer): không trích nguyên văn dữ liệu nội bộ
    (ghi chú RM, chi tiết tiền án, CIC bên thứ ba, số liệu người khác); từ chối thì nói
    điều-kiện-chưa-đạt lịch sự. (Sau T12-1: căn cứ wiki `ung-xu-disclosure-khach-hang`.)
(e) **Thêm 2 câu vào LUẬT**: "Hợp-gói ≠ duyệt-vay ≠ đã-giải-ngân — 3 mốc khác nhau, không gộp
    trong câu trả lời." · "Hồ sơ xanh dưới ngưỡng auto theo thẩm quyền → nói rõ 'tự động theo
    phân cấp thẩm quyền', không xin phép thừa."
(f) **Trùng tên khách** → để phòng tra rồi HỎI người dùng chọn, không chọn hộ (nối vào luật
    thiếu-thông-tin hiện có).

KHÔNG lấy: cấu trúc phong bì đồng bộ của rig (VỎ đã có event/board riêng) · luật "không gọi tool
nghiệp vụ" (MAIN VỎ vốn không mount tool nghiệp vụ — thừa) · route bảng từ khoá (VỎ đã có).

## Verify T12-4 (tester, sau khi T12-1/2 sống)
Legal/credit: 1 vòng live mỗi role — thấy citation page trong câu trả lời khi trích quy định.
Main: ca lương-lệch giả lập (Legal flag) → MAIN giao credit re-assess income_override đúng nghi
thức; 1 câu hỏi khách → không rò nội bộ.
