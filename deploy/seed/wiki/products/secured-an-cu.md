---
id: goi-the-chap-an-cu
role: products
title: P007 — An cư ưu đãi, đọc sâu
topic: secured_products
tags: goi-vay,the-chap,an-cu
legal_basis: [[qd-2026-laisuat]]
effective_from: 2026-01-01
status: active
---

## Định vị
P007 có điều kiện chặt hơn P006: ngưỡng thu nhập tối thiểu và đòi CIC nhóm 1 (không chấp
nhận nhóm 2 như P006). LƯU Ý QUAN TRỌNG: điều kiện chặt hơn ở đây KHÔNG đồng nghĩa lãi thấp
hơn — theo catalog hiện hành P007 không phải gói lãi tốt nhất nhóm secured (hai gói lãi tốt
nhất là P008/P009, xem [[goi-the-chap-premium]]). RM không được mặc định quy luật "điều kiện
chặt hơn thì lãi tốt hơn" cho P006 vs P007 — phải tra `product_list` mỗi lần để so đúng số.

## Hợp AI
Khách cá nhân thế chấp mua/sửa nhà, thu nhập đạt ngưỡng tối thiểu của gói (xem số qua
`product_list`), CIC nhóm 1, VÀ segment = mass — P007 khoá cứng theo segment này trong
catalog. Khách **vip** dù thu nhập rất cao vẫn KHÔNG đủ điều kiện P007 (server trả
ineligible vì segment, không phải vì thu nhập/CIC) — hướng khách vip sang P006 (mở mọi
segment) hoặc xét [[goi-the-chap-premium]] nếu đạt ngưỡng thu nhập cao hơn hẳn của nhóm đó.
Khách **staff** cũng không đủ điều kiện P007 cùng lý do — P006 là lựa chọn thế chấp thực tế
duy nhất cho staff, xem [[tu-van-theo-segment]].

## Hồ sơ cần
Giống P006 — CCCD, chứng minh thu nhập, giấy sở hữu tài sản, chứng thư định giá, kết hôn
nếu tài sản chung — theo [[checklist-giay-to]]. Vì P007 đòi thu nhập tối thiểu, ưu tiên thu
nhập XÁC MINH hơn kê khai khi tính điều kiện, đúng nguyên tắc tại [[chinh-sach-dscr-ltv]].

## Câu khách hay hỏi
- "Thu nhập em hơi thấp so với ngưỡng, chị linh động cho em vào P007 được không?" — không;
  ngưỡng thu nhập là điều kiện gói, không phải điều kiện có thể xin giảm — nếu chưa đạt, tư
  vấn P006 (không đòi thu nhập tối thiểu) thay vì tìm cách lách ngưỡng P007.
- "CIC em nhóm 2 do một lần chậm nhỏ, có ngoại lệ không?" — không, CIC nhóm là dữ liệu khách
  quan từ tool, Products không có thẩm quyền miễn trừ; gợi ý khách chờ CIC cải thiện hoặc
  chuyển hướng P006.
- "P007 đòi nhiều điều kiện hơn P006 vậy chắc lãi tốt hơn nhiều đúng không?" — không nên
  khẳng định trước khi tra `product_list`; catalog hai gói này KHÔNG theo quy luật đơn giản
  "chặt điều kiện hơn = lãi tốt hơn", nêu đúng số thật cho khách, tránh hứa hộ mức chênh
  lệch mình chưa kiểm tra.

## Ranh cần nhắc
Đủ điều kiện thu nhập/CIC của P007 chỉ là "hợp gói" — DSCR thật (thu nhập XÁC MINH đối chiếu
nghĩa vụ trả) và LTV tài sản vẫn do Credit tính bằng tool; xem thêm ranh giới đầy đủ tại
[[faq-ban-hang-goi-vay]].
