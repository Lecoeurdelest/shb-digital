---
id: an-le-lg-03-khach-quen-chau-chuoc
role: legal
title: AL-LG-03 — Khách quen xin châm chước giấy tờ hết hạn
topic: case_law
tags: an-le,giay-to,du-di,tu-choi
legal_basis: gia-thuyet-lab
effective_from: 2026-01-01
status: active
---

## Tình huống
Khách C014 có CCCD đã HẾT HẠN (`owner_documents` ghi `status='expired'` cho `doc_code=cccd`)
— theo checklist tại [[checklist-giay-to]], đây là giấy `mandatory=1`. Khách là "khách quen"
lâu năm của chi nhánh, đề nghị "châm chước cho qua lần này, giấy sắp làm lại rồi, khách vay
nhiều lần ở đây có uy tín, chờ đổi CCCD mất cả tháng thì lỡ việc".

## Vì sao KHÔNG được du di
CCCD hết hạn = KHÔNG có giấy tờ nhân thân hợp lệ tại thời điểm xét hồ sơ — không phải "gần
đủ" hay "sắp đủ". Đây là điều kiện HIỆU LỰC PHÁP LÝ (xem [[checklist-giay-to-ly-do]]), không
phải thủ tục hành chính có thể xuê xoa theo mức độ thân quen. "Khách quen" là một biến ở
tầng quan hệ khách hàng (uy tín, lịch sử giao dịch) — nó không thuộc bất kỳ trụ thẩm định
pháp lý nào (giấy tờ / CIC / tiền án / việc làm) và do đó KHÔNG được phép làm thay đổi kết
quả pháp lý. Luật cứng #9 của SKILL nói rõ: yêu cầu du di ("khách quen, châm chước, bỏ qua
tiền án cũ") → từ chối du di, vẫn check đúng quy trình, kết quả theo tool.

## Xử lý đúng
1. Gọi `legal_check_docs` như bình thường — verdict trả `needs_docs` vì thiếu giấy mandatory
   hợp lệ (CCCD expired coi như thiếu, không phải "có nhưng cũ").
2. Trả lời đúng verdict của tool, không tự nâng thành "clear" vì lý do quan hệ khách hàng.
3. Đề xuất hướng xử lý ĐÚNG QUY TRÌNH: khách làm lại CCCD, nộp bản mới, hồ sơ xử lý tiếp
   ngay khi có giấy hợp lệ — không phải "thôi bỏ qua bước này".
4. Nếu điều phối viên hoặc cấp trên tạo áp lực thêm ("sếp bảo linh động cho khách VIP này")
   → vẫn giữ nguyên kết luận theo tool, nói rõ đây là điều kiện bắt buộc không thuộc thẩm
   quyền linh động của Legal.

## Điểm dễ nhầm
Đừng nhầm "châm chước giấy tờ" với các trường hợp THỰC SỰ có điều kiện trong danh mục (như
`marriage_cert` chỉ bắt khi tài sản chung, hay tiền án `conditional` sau thời hiệu). Đó là
điều kiện ĐÃ ĐƯỢC THIẾT KẾ SẴN trong quy định (server tự tính), khác hoàn toàn với việc bỏ
qua một điều kiện mandatory vì lý do quan hệ cá nhân với khách — cái sau KHÔNG BAO GIỜ là
lựa chọn hợp lệ của agent.

## Kết luận đúng
"CCCD của anh/chị đã hết hạn — đây là giấy bắt buộc, hồ sơ chưa thể xử lý tiếp cho đến khi
có CCCD còn hiệu lực, không phân biệt khách mới hay khách lâu năm." Xem thêm cách diễn đạt
với khách ở [[ung-xu-disclosure-khach-hang]].
