---
id: red-flag-tham-dinh
role: credit
title: Sổ tay red-flag khi thẩm định — dấu hiệu cần xét kỹ hơn số trên giấy
topic: red_flags
tags: red-flag,tham-dinh,rui-ro-mem
legal_basis: QĐ nội bộ 118/QĐ-SHB (gia-thuyet-lab)
effective_from: 2025-06-01
status: active
---

DSCR/LTV đạt ngưỡng trên tool KHÔNG có nghĩa hồ sơ an toàn tuyệt đối. Danh sách dưới
đây là các dấu hiệu buộc Credit XÉT KỸ HƠN trước khi kết luận — không phải lý do từ
chối tự động, mà là lý do tra thêm dữ liệu trước khi ký kết luận.

## 1. Thu nhập đẹp nhưng dư nợ nhiều nơi
Khách thu nhập cao/rất cao trên hồ sơ nhưng ĐANG gánh nhiều khoản vay hoạt động — kể cả
tại chính SHB — khiến phần thu nhập THỰC SỰ còn trống cho nghĩa vụ mới rất mỏng. Đây là
dạng "số đẹp, khả năng trả mỏng": DSCR tính đủ có thể vẫn KHÔNG đạt dù thu nhập thuộc
nhóm cao nhất hồ sơ. Không vì thu nhập cao mà bỏ qua bước cộng đủ nghĩa vụ trả nợ hiện
có — xem án lệ [[al-cr-01-vip-no-nang]].

## 2. Ghi chú tương tác cảnh báo dòng tiền
Trước khi kết luận hồ sơ khách có hoạt động kinh doanh (kinh doanh tự do, chủ hộ/DN
nhỏ), tra `notes_search(owner_id)` để soi dấu hiệu mềm: than phiền dòng tiền yếu, chậm
thanh toán nhà cung cấp, hỏi hệ quả nếu chậm trả một kỳ, xin giãn kỳ hạn. Các dấu hiệu
này KHÔNG nằm trong bảng số DSCR/LTV nhưng là tín hiệu sớm hơn CIC — CIC phản ánh nợ xấu
ĐÃ XẢY RA, ghi chú RM có thể phản ánh nguy cơ TRƯỚC khi lên CIC. Trích dẫn kèm `note_id`.

## 3. CIC nhóm cần chú ý (nhóm 2) đi kèm nhiều khoản
Nhóm 2 chưa bị chặn cứng (khác nhóm ≥3, xem [[phan-loai-no-cic]]) nhưng nếu đi cùng
nhiều khoản vay hoạt động, đây là tổ hợp cần xét kèm — không tự động từ chối, cũng
không tự động bỏ qua. Xem cách Credit dùng nhóm CIC tại [[doc-hieu-cic-tin-dung]].

## 4. Hồ sơ xin hạn mức lệch mạnh so với lịch sử giao dịch
Khách trước giờ chỉ giao dịch nhỏ (tiết kiệm, thẻ) bỗng xin khoản vay lớn bất thường —
không phải lý do từ chối, nhưng là lý do xác minh kỹ mục đích vay ([[muc-dich-vay-han-che]])
và nguồn trả nợ trước khi đưa vào tính DSCR.

## 5. Tài sản thế chấp giá trị cao nhưng chủ sở hữu đang neo nợ nhiều nơi
LTV tính trên giá trị định giá có thể đạt ngưỡng, nhưng nếu chủ tài sản đồng thời có
nhiều nghĩa vụ trả nợ khác, rủi ro thực nằm ở DSCR chứ không nằm ở LTV — hai chỉ số phải
đọc CÙNG NHAU, không đọc rời.

## Nguyên tắc chung
Red-flag là tín hiệu ĐI TÌM THÊM DỮ LIỆU (notes, CIC, xác minh thu nhập), không phải
căn cứ để tự kết luận. Mọi kết luận cuối vẫn phải bằng số ra từ tool thẩm định.
