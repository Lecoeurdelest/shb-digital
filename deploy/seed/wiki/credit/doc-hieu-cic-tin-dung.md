---
id: doc-hieu-cic-tin-dung
role: credit
title: Đọc nhóm CIC trong thẩm định tín dụng — Credit dùng để làm gì
topic: cic_usage
tags: cic,tham-dinh,dscr
legal_basis: [[phan-loai-no-cic]]
effective_from: 2025-01-01
status: active
---

Bảng phân loại nhóm nợ 1-5 và hệ quả tuân thủ (chặn/không chặn) thuộc thẩm quyền Legal,
xem đầy đủ tại [[phan-loai-no-cic]] — trang này KHÔNG lặp lại bảng đó, chỉ nói Credit
DÙNG nhóm CIC như thế nào trong khâu thẩm định khả năng trả nợ.

## Ai chặn, ai thẩm định
CIC nhóm từ mức chặn cứng trở lên (xem ngưỡng tại [[phan-loai-no-cic]]) là quyết định
CỦA LEGAL — Credit không thẩm định tiếp một hồ sơ đã bị Legal chặn vì CIC. Việc của
Credit là dùng nhóm CIC cho các hồ sơ CHƯA bị chặn để điều chỉnh MỨC ĐỘ THẬN TRỌNG khi
tính DSCR.

## Nhóm 1 (đủ tiêu chuẩn)
Không cần thao tác thêm ngoài quy trình DSCR/LTV chuẩn tại [[chinh-sach-dscr-ltv]].

## Nhóm 2 (cần chú ý)
Chưa bị chặn, nhưng là tín hiệu để soát kỹ hơn: đối chiếu ĐẦY ĐỦ mọi khoản vay hoạt
động của khách (không sót khoản nào khi cộng nghĩa vụ trả nợ hiện có), và tra thêm ghi
chú tương tác nếu hồ sơ thuộc nhóm nghề nghiệp thu nhập biến động — xem
[[red-flag-tham-dinh]]. Nhóm 2 đi kèm nhiều khoản vay hoạt động là tổ hợp cần xét kỹ,
không phải lý do từ chối tự động.

## Nhóm ≥3 (nợ xấu)
Legal đã chặn cho vay mới ở tầng của mình — nếu hồ sơ vẫn tới tay Credit (ví dụ khách
xin xét lại/xin ngoại lệ), Credit KHÔNG có thẩm quyền tự nới ngưỡng chặn cứng của Legal
dù thẩm định riêng DSCR/LTV có đạt bao nhiêu — xem án lệ
[[al-cr-04-no-xau-du-di]]. Muốn xét ngoại lệ, phải đi đúng đường: trình cấp có thẩm
quyền theo [[phan-cap-tham-quyen]], không tự hứa hẹn với khách.

## Khi CIC null (chưa có bản ghi)
Không suy diễn là "sạch" hay "xấu" — xử lý như thiếu dữ liệu, ghi verdict `needs_info`
cho phần này, không mặc định một chiều.

## Vì sao tách trang này khỏi bảng phân loại
Bảng phân loại (Legal) là NGUỒN SỰ THẬT về nhóm nợ và hệ quả tuân thủ; trang này là
HƯỚNG DẪN NGHIỆP VỤ cho riêng Credit — tách để tránh hai nơi cùng mô tả một bảng rồi
lệch nhau khi Legal cập nhật ngưỡng.
