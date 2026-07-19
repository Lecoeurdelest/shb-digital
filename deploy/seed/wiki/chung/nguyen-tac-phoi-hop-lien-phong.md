---
id: nguyen-tac-phoi-hop-lien-phong
role: chung
title: Nguyên tắc phối hợp liên phòng
topic: cross_department_principle
tags: nguyen-tac,lien-phong,phong-bi
legal_basis: gia-thuyet-lab — nguyên tắc vận hành hệ agent
effective_from: 2026-01-01
status: active
---

## Phong bì bàn giao — đơn vị trao đổi giữa các phòng
Khi một hồ sơ đi qua nhiều phòng (theo [[quy-trinh-vay-7-buoc]]), mỗi phòng nhận một "phong
bì vào" (yêu cầu + kết quả các phòng trước) và trả một "phong bì ra" (kết luận + căn cứ tool
của chính mình). Phong bì ra của phòng trước LÀ phong bì vào của phòng sau — không có bước
trung gian diễn giải lại.

## Dùng-nguyên-kết-quả — không tính lại
Kết quả một phòng khác đã kết luận (ví dụ Credit đã tính `credit_ok=1` với DSCR cụ thể, Legal
đã phân lane) được phòng sau SỬ DỤNG NGUYÊN VĂN, không tính lại bằng công thức của phòng
mình dù có đủ dữ liệu để tính. Lý do:
- Tính lại có thể ra số khác do lệch giả định/thời điểm dữ liệu — hai số cho cùng một việc là
  dấu hiệu lỗi, không phải "chấm chéo cho chắc".
- Mỗi phòng là nguồn thẩm quyền DUY NHẤT cho đúng một loại kết luận (Credit: khả năng trả nợ;
  Legal: tuân thủ; Operations: trạng thái thi hành). Phòng khác tính lại là lấn ranh.
- Nhất quán với [[nguyen-tac-nguon-so]]: một kết luận chỉ có một nguồn, dù nguồn đó là tool
  của phòng mình hay kết quả đã ghi của phòng khác trong cùng hồ sơ.

## Khi nhận phong bì có vẻ sai hoặc thiếu
KHÔNG tự sửa kết quả phòng trước, KHÔNG bỏ qua coi như chưa nhận được. Xử lý đúng: nêu rõ chỗ
nghi ngờ, trả về đúng phòng đã kết luận để họ tra lại bằng tool của họ. Ranh trách nhiệm giữ
nguyên — phòng sau phát hiện nghi vấn, phòng trước xác nhận/sửa.

## Khi trả kết quả cho điều phối/khách
Trích NGUYÊN VĂN kết quả tool của các bước trước (không diễn giải lại số, không đổi từ ngữ
"đạt/không đạt" thành cách nói khác), kèm 1-2 câu diễn giải tiếng Việt của riêng phần mình.
Người nhận phong bì cuối (điều phối, khách hàng qua RM) phải truy ngược được từng phần kết
luận về đúng phòng và đúng tool-call đã sinh ra nó.

## Ranh không chồng lấn
Mỗi phòng GÁC đúng phần việc của mình (xem ranh cụ thể tại vai từng phòng), KHÔNG làm hộ,
KHÔNG phán hộ phần của phòng khác dù có khả năng kỹ thuật để làm — ranh rõ là điều kiện để
dùng-nguyên-kết-quả hoạt động được; ranh mờ thì mỗi phòng lại phải tự kiểm tra chéo, quay về
đúng vấn đề mà nguyên tắc này muốn tránh.

## Liên kết
[[quy-trinh-vay-7-buoc]] · [[ma-tran-tham-quyen]] · [[nguyen-tac-nguon-so]].
