---
id: goi-tieu-dung-linh-hoat
role: products
title: P003/P004/P013 — Nhóm linh hoạt, đọc sâu (có trùng điều kiện + đánh đổi lãi-phí)
topic: consumer_products
tags: goi-vay,tieu-dung,linh-hoat,rate-vs-fee
legal_basis: [[qd-2026-laisuat]]
effective_from: 2026-01-01
status: active
---

## Định vị
Ba gói P003 (Linh hoạt A), P004 (Ưu việt B), P013 (Lãi thấp phí cao) cùng nhắm khách thu
nhập tốt, CIC sạch, dải hạn mức trùng nhau gần như hoàn toàn. Đây là NHÓM DỄ TƯ VẤN SAI
NHẤT trong catalog vì ba gói không loại trừ nhau — khách đủ điều kiện một gói gần như chắc
đủ cả ba, và "gói tốt nhất" phụ thuộc tiêu chí khách quan tâm (lãi thuần hay tổng chi phí).

## Hợp AI
Khách cá nhân thu nhập tốt, CIC nhóm 1, khoản vay tầm trung, VÀ segment = mass (cả ba gói
khoá cứng theo segment này trong catalog — khách vip/staff KHÔNG đủ điều kiện dù thu
nhập/CIC vượt xa ngưỡng, xem [[tu-van-theo-segment]]). Với khách mass đúng điều kiện, đủ một
gói gần như chắc đủ cả P003/P004/P013 cùng lúc. `product_suggest` trả eligibleOptions gồm cả
ba, RM đọc NGUYÊN VĂN, không tự bỏ bớt gói nào.

## Nguyên tắc recommend — và vì sao KHÔNG dừng ở đó
Server đề xuất theo lãi suất thấp nhất trong nhóm đủ điều kiện (`recommend_by=rate_annual_asc`
— xem [[goi-tieu-dung]]). Giữa P003/P004, P004 luôn thắng vì lãi thấp hơn VÀ phí cũng thấp
hơn — không có đánh đổi, chào P004 là xong.

Nhưng P013 khác: lãi P013 THẤP HƠN cả P004 trong catalog, nên server có thể đề xuất P013 —
ĐỒNG THỜI phí của P013 cao hơn hẳn nhóm còn lại. Đây là trap RATE-VS-FEE: nhìn một con số
lãi suất không đủ để nói gói nào lợi hơn cho khách. RM/agent PHẢI tự nêu đánh đổi này với
khách bằng số thật lấy từ `product_list` (lãi thấp hơn bao nhiêu, phí cao hơn bao nhiêu),
không chỉ đọc nguyên văn khuyến nghị của server rồi dừng lại. Tổng chi phí thực tế phụ
thuộc kỳ hạn khách chọn — kỳ hạn ngắn thì phí (thường tính một lần) ảnh hưởng tỷ trọng lớn
hơn so với kỳ hạn dài.

## Câu khách hay hỏi
- "Gói nào lãi thấp nhất?" — trả lời đúng (P013 nếu đúng cấu hình hiện hành theo
  `product_list`), NHƯNG bắt buộc nói thêm phần phí cao hơn ngay trong cùng câu trả lời,
  không tách rời hai thông tin.
- "Vậy chốt gói nào?" — không tự chốt hộ khách; trình bày cả hai chiều (lãi vs phí, ước tổng
  chi phí theo kỳ hạn khách dự kiến) rồi để khách quyết, hoặc khuyến nghị theo mục tiêu
  khách nêu (vay ngắn hạn → phí ảnh hưởng nhiều → cân nhắc P004; vay dài hạn → chênh lãi
  cộng dồn lớn hơn → P013 có thể lợi hơn).
- "P003 với P004 khác gì nhau mà điều kiện y hệt?" — nói thẳng P004 lợi hơn thuần túy trên
  mọi tiêu chí (lãi thấp hơn, phí thấp hơn), không có lý do chọn P003 khi cùng đủ điều kiện
  — đây là gói cũ giữ lại trong catalog, không phải lựa chọn cạnh tranh thật.

## Ranh cần nhắc
Đánh đổi lãi-vs-phí PHẢI nêu chủ động, không đợi khách hỏi — xem thêm hướng dẫn segment tại
[[tu-van-theo-segment]] và án lệ khiếu nại thật liên quan tại [[al-pr-02]].
