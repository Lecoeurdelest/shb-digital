---
id: phan-khuc-khach-hang-2024
role: products
title: Hướng dẫn phân khúc khách hàng 2024 (bản cũ)
topic: segment_guidance
tags: segment,tu-van,het-hieu-luc
legal_basis: QĐ nội bộ 340/QĐ-SHB (gia-thuyet-lab)
effective_from: 2024-06-01
effective_to: 2025-12-31
status: replaced
---

**ĐÃ BỊ THAY THẾ** bởi [[tu-van-theo-segment]] kể từ 01/01/2026 — giữ trang này để tra
lịch sử, KHÔNG dùng làm căn cứ tư vấn.

## Nội dung bản cũ (chỉ để đối chiếu lịch sử)
Trước khi hệ thống có trường `segment` gắn thẳng vào hồ sơ khách, RM tự ước lượng "hạng
khách" dựa trên quan sát định tính: nghề nghiệp, tài sản thể hiện qua trò chuyện, lịch sử
giao dịch tại quầy. Cách làm này không có nguồn dữ liệu chuẩn hoá, dẫn tới hai vấn đề đã ghi
nhận: (1) RM khác nhau đánh giá khác nhau cho cùng một khách, (2) không có căn cứ máy-kiểm
khi khách khiếu nại bị phân loại sai.

## Vì sao thay thế
Từ khi `customers.segment` (mass/vip/staff) được nạp trực tiếp vào hồ sơ và các gói VIP-only
(P009 và tương tự) tra thẳng trường này qua `product_suggest`, việc RM tự ước lượng segment
bằng quan sát không còn cần thiết và có thể gây SAI LỆCH so với hệ thống — ví dụ RM "cảm
thấy" khách sang trọng nên chào P009 dù hồ sơ segment=mass, dẫn tới tư vấn sai rồi bị hệ
thống từ chối ở bước sau, mất thời gian cả hai phía.

## Luật ứng xử khi gặp trang này
Agent/RM tra cứu wiki gặp trang `topic=segment_guidance` PHẢI kiểm `status` trước khi dùng —
trang `status=replaced` không được dùng làm căn cứ kết luận; đi cạnh [[tu-van-theo-segment]]
để lấy bản hiện hành. Đây là ví dụ thực hành đúng nguyên tắc đồ thị văn bản mô tả tại
`RETRIEVAL-README.md` §2: bản cũ và bản mới có thể gần giống nhau về nội dung bề mặt, chỉ
field hiệu lực + cạnh thay-thế mới phân biệt được đâu là căn cứ đúng.
