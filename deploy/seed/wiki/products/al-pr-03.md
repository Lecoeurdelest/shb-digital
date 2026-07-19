---
id: al-pr-03
role: products
title: AL-PR-03 — Hứa "chắc chắn duyệt" khi hồ sơ mới hợp gói (APP03)
topic: case_law
tags: an-le,duyet-vay,tuan-thu
legal_basis: [[qd-2026-laisuat]]
effective_from: 2026-05-02
status: active
---

## Diễn biến
Khách C017 nộp hồ sơ vay P001 (đơn APP03, hồ sơ đang ở trạng thái `reviewing`). Ngay sau
bước `product_suggest` xác nhận C017 hợp điều kiện P001, RM nói với khách "hồ sơ anh hợp
gói rồi, coi như chắc chắn được duyệt, cứ yên tâm chuẩn bị nhận tiền". Vài ngày sau, khoản
vay vẫn ở `reviewing` chờ Credit tính DSCR và Legal xác minh hồ sơ — khách gọi lại thắc mắc
"sao đã nói chắc chắn mà giờ vẫn chưa xong", RM không có câu trả lời vì đã hứa vượt thẩm
quyền phòng ban của mình.

## Nguyên nhân gốc
RM nhầm "hợp gói" (Products xác nhận) với "được duyệt vay" (kết quả tổng hợp của Credit +
Legal + người có thẩm quyền, xem [[phan-cap-tham-quyen]]). Đây đúng lỗi mà luật cứng #2 của
SKILL Products đã cảnh báo: "hợp gói ⇏ được duyệt vay — nói rõ khi kết luận" — ca này là
bằng chứng cụ thể khi RM bỏ qua câu nhắc đó.

## Cách xử đúng (đã chốt thành luật)
1. Kết luận "hợp gói" LUÔN đi kèm câu nói rõ các bước còn lại (DSCR, pháp lý, thẩm quyền phê
   duyệt) — không dùng từ tuyệt đối như "chắc chắn", "coi như xong", "yên tâm nhận tiền" khi
   hồ sơ còn ở trạng thái `reviewing`.
2. Nếu khách hỏi thẳng "vậy có được duyệt không", trả lời đúng phạm vi: "Products xác nhận
   anh/chị hợp điều kiện gói; kết quả duyệt cuối do Credit/Legal/người có thẩm quyền quyết
   định, em sẽ báo ngay khi có kết quả" — không đoán hộ kết quả thẩm định của phòng khác.
3. Với hồ sơ đã ở bước `approved_pending_procedures` trở lên mới có thể nói "đã được duyệt,
   đang hoàn tất thủ tục" — vẫn không phải "chắc chắn nhận tiền" vì còn cổng
   `procedures_done`/`human_approval_resolved` tại [[phan-cap-tham-quyen]].

## Bài học cho agent
"Hợp gói" là câu trả lời của MỘT phòng ban trong chuỗi bốn cổng giải ngân. Agent Products
không được (và không có dữ liệu để) đại diện phát ngôn kết quả của Credit/Legal/người duyệt
— mọi cam kết về khả năng được vay phải chờ đủ nguồn từ đúng phòng ban, xem ranh đầy đủ tại
[[faq-ban-hang-goi-vay]].
