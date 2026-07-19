---
id: checklist-giay-to-ly-do
role: legal
title: Vì sao cần từng loại giấy tờ — diễn giải checklist theo loại vay
topic: documents
tags: giay-to,ho-so,ly-do
legal_basis: QĐ nội bộ 214/QĐ-SHB (gia-thuyet-lab)
effective_from: 2025-06-01
status: active
---

Trang [[checklist-giay-to]] liệt kê DANH MỤC máy đọc (bảng `legal_requirements`, tool
`legal_check_docs`). Trang này diễn giải VÌ SAO từng giấy bắt buộc — để agent trả lời
được câu "sao lại cần giấy này" thay vì chỉ dán nhãn "thiếu/đủ".

## `cccd` — Căn cước công dân
Xác nhận nhân thân là ĐIỀU KIỆN TIÊN QUYẾT của mọi hợp đồng tín dụng — không có CCCD hợp lệ
thì hợp đồng vô hiệu về chủ thể. Đây cũng là mỏ neo để đối chiếu với dữ liệu Bộ Công an
(`legal_check_police`) — xem [[kyc-gian-lan-nhan-than]]. CCCD hết hạn coi như KHÔNG có giấy
hợp lệ (trạng thái `expired` trong `owner_documents`) chứ không phải "gần đủ".

## `proof_income` — Chứng minh thu nhập
Là đầu vào của thẩm định khả năng trả (Credit dùng để tính DSCR) — thiếu giấy này thì con số
income Credit dùng KHÔNG có căn cứ xác minh, chỉ là lời khai. Đây là lý do tại sao
`proof_income` bắt buộc ở CẢ HAI loại vay (tiêu dùng lẫn thế chấp), không có ngoại lệ theo
quy mô khoản vay. Liên quan trực tiếp lệch kê khai — xem [[xac-minh-thu-nhap-lech-khai]].

## `ownership_cert` — Giấy chứng nhận quyền sở hữu tài sản (sổ đỏ/hồng)
Chỉ áp dụng vay thế chấp. Đây là bằng chứng DUY NHẤT xác lập ai có quyền đem tài sản ra bảo
đảm — thiếu giấy này, ngân hàng không có cơ sở pháp lý để nhận thế chấp dù tài sản có tồn
tại thật. Server đối chiếu `collaterals.owner_id` với `owner_id` hồ sơ vay: lệch chủ →
lỗi `collateral_owner_mismatch`, không phải "thiếu giấy" mà là SAI CHỦ THỂ — xem
[[quy-trinh-tsdb]] bước 1.

## `appraisal_report` — Chứng thư định giá
Là input của LTV — không có định giá độc lập thì loan/appraised không tính được, hoặc tệ
hơn là dùng số khách tự khai (dễ bị thổi phồng giá trị tài sản để vay nhiều hơn). Chứng
thư phải do đơn vị định giá được công nhận lập, không nhận số khách tự nêu.

## `marriage_cert` — Đăng ký kết hôn (có điều kiện)
CHỈ bắt buộc khi tài sản thế chấp là TÀI SẢN CHUNG VỢ CHỒNG — vì theo luật hôn nhân gia
đình, định đoạt tài sản chung cần sự đồng ý của cả hai vợ chồng; thiếu giấy này thì hợp
đồng thế chấp có nguy cơ bị một bên khởi kiện vô hiệu sau này. Đây KHÔNG phải giấy "cho có"
— nó là điều kiện hiệu lực pháp lý của chính hợp đồng thế chấp khi tài sản là sở hữu chung.

## `residence` — Xác nhận cư trú
Giấy phụ (không chặn cứng) — hỗ trợ đối chiếu địa chỉ với dữ liệu Công an khi có dấu hiệu
lệch (xem [[kyc-gian-lan-nhan-than]]), không phải điều kiện bắt buộc để duyệt.

## Luật làm việc chung
Thiếu giấy `mandatory=1` → verdict `needs_docs`, KHÔNG duyệt tiếp bất kể khách quen hay hồ
sơ đẹp ở các mặt khác — xem án lệ [[an-le-lg-03-khach-quen-chau-chuoc]]. Diễn giải ở trang
này KHÔNG thay thế danh mục máy đọc — luôn tra `legal_check_docs` để lấy verdict thật.
