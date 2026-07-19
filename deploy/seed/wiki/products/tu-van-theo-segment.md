---
id: tu-van-theo-segment
role: products
title: Hướng dẫn tư vấn theo segment (mass/vip/staff)
topic: segment_guidance
tags: segment,tu-van,positioning
legal_basis: QĐ nội bộ 512/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

THAY THẾ: [[phan-khuc-khach-hang-2024]] — bản hướng dẫn cũ dựa trên thu nhập ước lượng đã
hết hiệu lực từ khi `customers.segment` được đưa thẳng vào hồ sơ khách (2026); mọi tư vấn
segment từ nay CĂN CỨ trường `segment` thật trong hồ sơ, không tự suy từ nghề nghiệp/thu
nhập như trước.

## Sự thật quan trọng nhất: catalog CHIA VÙNG theo segment, không phải "vip = mở thêm"
Trường `segment` trên một gói là điều kiện KHOÁ CỨNG trong `product_suggest` — khách phải
đúng segment đó mới hợp gói, không có ngoại lệ theo thu nhập/CIC cao bù lại. Catalog hiện
hành chia ba phần: một nhóm gói MỞ CHO MỌI SEGMENT (P001, P005, P006, P010, P011 — không có
`segment` niêm yết), một nhóm CHỈ MASS (P002, P003, P004, P007, P013), một nhóm CHỈ VIP
(P008, P009, P012). RM cần hiểu đây KHÔNG phải "vip có nhiều lựa chọn hơn mass" đơn thuần —
vip bị LOẠI khỏi đúng nhóm mass-only dù hồ sơ tốt hơn, đổi lại được mở nhóm vip-only.

## Ba segment và cách định vị
- **mass**: đa số khách. Được dùng nhóm mở-cho-mọi-segment VÀ nhóm mass-only
  ([[goi-tieu-dung-linh-hoat]], [[goi-the-chap-an-cu]]) khi đủ điều kiện thu nhập/CIC — đừng
  mặc định chào gói phổ thông nhất khi khách đủ điều kiện gói tốt hơn. Không chào nhóm
  vip-only (P008/P009/P012) — server sẽ trả ineligible vì segment.
- **vip**: được mở nhóm vip-only ([[goi-the-chap-premium]], P012 trong
  [[goi-doanh-nghiep-chi-tiet]]) NHƯNG đồng thời KHÔNG đủ điều kiện nhóm mass-only dù thu
  nhập/CIC vượt xa ngưỡng — đây là điểm RM hay tư vấn nhầm nhất (xem hệ quả thật tại
  [[goi-tieu-dung-linh-hoat]]/[[goi-the-chap-an-cu]]). Positioning đúng: "gói phù hợp quy mô
  tài sản/thu nhập của anh/chị", KHÔNG phải "đặc quyền không cần thẩm định" — vip vẫn qua đủ
  DSCR/LTV/CIC như mọi khách khác, chỉ khác CATALOG được mở, không khác QUY TRÌNH duyệt.
- **staff**: nhân viên nội bộ — segment KHÔNG mở nhóm mass-only lẫn vip-only, nên trên thực
  tế catalog cá nhân khả dụng cho staff hẹp nhất (chủ yếu P001/P006, nhóm mở-cho-mọi-segment).
  Trang này KHÔNG có thẩm quyền nêu ưu đãi riêng cho staff nếu catalog không thể hiện —
  segment=staff không tự động đổi lãi/phí; mọi ưu đãi nhân viên (nếu có) phải đến từ chính
  sách nhân sự riêng, không phải catalog `product_list`, và Products không tự suy diễn khi
  không có nguồn.

## Đánh đổi lãi-vs-phí PHẢI nêu với khách, mọi segment
Đây là luật cứng nhất của trang này: khi có ≥2 gói đủ điều kiện mà một gói lãi thấp hơn
nhưng phí cao hơn (điển hình P013 so với P004 trong [[goi-tieu-dung-linh-hoat]]), RM PHẢI
chủ động nói cả hai chiều — không dừng ở "lãi thấp nhất" vì đó không phải "chi phí thấp
nhất". Khách vip khoản lớn càng cần nêu rõ vì chênh lệch phí tính trên số tiền lớn là số
tuyệt đối đáng kể, dù % nhìn nhỏ.

## Câu khách hay hỏi theo segment
- Khách mass: "Sao anh bạn em vip được lãi tốt hơn mà em thì không?" — trả lời thật: catalog
  phân biệt theo segment/điều kiện khách quan (thu nhập, CIC), không phải quan hệ cá nhân;
  không hứa "linh động" để giữ khách.
- Khách vip: "Em vip chắc được duyệt nhanh/dễ hơn đúng không?" — sửa ngay hiểu lầm: vip đổi
  SANG một nhóm catalog khác (mở gói ngưỡng cao, không dùng được nhóm mass-only nữa), KHÔNG
  mở lane duyệt riêng hay giảm yêu cầu thẩm định.
- Khách staff: "Em là nhân viên ngân hàng, có ưu đãi gì không?" — nếu catalog không thể hiện
  ưu đãi cho segment=staff, nói rõ chưa có chính sách trong hệ thống hiện tại, không tự bịa
  mức ưu đãi để làm hài lòng khách.
