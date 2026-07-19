---
id: chuong-trinh-uu-dai
role: products
title: Chương trình ưu đãi & vòng đời hiệu lực
topic: promo_lifecycle
tags: uu-dai,hieu-luc,tuan-thu
legal_basis: [[qd-2026-laisuat]]
effective_from: 2026-01-01
status: active
---

## Vì sao chương trình ưu đãi khác gói catalog thường
Gói trong [[goi-tieu-dung]]/[[goi-the-chap]]/[[goi-doanh-nghiep]] sống lâu dài theo văn bản
biểu lãi suất hiện hành. CHƯƠNG TRÌNH ƯU ĐÃI (khuyến mãi theo mùa, theo sự kiện) có VÒNG ĐỜI
NGẮN gắn với một văn bản ban hành riêng, luôn có `effective_from`/`effective_to` rõ ràng —
và khi hết hiệu lực, RM/agent vẫn có thể vô tình nhớ nhầm mức ưu đãi cũ nếu không soát lại
văn bản trước khi chào.

## Vòng đời một chương trình ưu đãi
1. Văn bản ban hành chương trình (vd [[qd-2025-tet]]) → gói ưu đãi xuất hiện trong catalog
   với `status=active` và mốc `effective_to`.
2. Tới mốc hết hạn, gói chuyển `status=expired` trong catalog VÀ trang wiki mô tả cũng đổi
   `status=expired` (xem ví dụ thật: [[uu-dai-tet-68]]).
3. Văn bản kế nhiệm (vd [[qd-2026-laisuat]]) đánh dấu rõ mình THAY THẾ văn bản cũ; văn bản
   cũ đổi `status=replaced` (xem [[qd-2025-tet]]) — cả hai trang GIỮ LẠI, không xoá, vì lịch
   sử hiệu lực là căn cứ audit khi có khiếu nại về mốc thời gian.

## Luật ứng xử bắt buộc
- Trước khi chào bất kỳ chương trình có tên "ưu đãi/khuyến mãi", agent PHẢI tra
  `wiki_related_docs` xem văn bản căn cứ còn `status=active` hay đã `expired`/`replaced` —
  không chào theo trí nhớ hoặc theo tài liệu in giấy cũ.
- Gói `status=expired` không được chào dù khách hỏi trực tiếp bằng tên/mức ưu đãi cũ — trả
  lời rõ đã hết hiệu lực, chuyển hướng gói active tương đương (xem case thật đã xảy ra tại
  [[al-pr-01]]).
- Không có "gia hạn miệng" — chương trình chỉ còn hiệu lực khi có văn bản mới ban hành, thể
  hiện bằng trang wiki `status=active` tương ứng; RM không tự quyết định kéo dài ưu đãi.

## Câu khách hay hỏi
- "Tháng trước em nghe nói có ưu đãi X%, giờ sao không thấy?" — tra đúng văn bản, nếu đã hết
  hạn thì nói rõ mốc hết hạn, không đổ lỗi "hệ thống lỗi" hay hứa khôi phục.
- "Sắp có ưu đãi mới không?" — chỉ trả lời khi có văn bản/thông báo chính thức đã nạp vào
  wiki; không suy đoán hay hứa trước lịch ban hành.

## Ranh cần nhắc
Chương trình ưu đãi vẫn là MỘT GÓI trong catalog — mọi ranh "hợp gói ≠ duyệt vay" tại
[[faq-ban-hang-goi-vay]] áp dụng y hệt, kể cả khi gói đang active.
