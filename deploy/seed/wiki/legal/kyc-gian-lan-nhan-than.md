---
id: kyc-gian-lan-nhan-than
role: legal
title: KYC & nhận diện gian lận nhân thân
topic: identity_fraud
tags: kyc,gian-lan,nhan-than,tien-an
legal_basis: Luật Phòng chống rửa tiền + QĐ nội bộ 305/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

Trụ ① của [[xac-minh-3-tru]] là đối chiếu nhân thân với dữ liệu Bộ Công an
(`police_records`, tool `legal_check_police`). Trang này liệt kê CÁC KIỂU LỆCH thường gặp
để agent nhận diện đúng loại, không gộp chung mọi lệch thành "nghi gian lận".

## Ba kiểu lệch nhân thân hay gặp
`police_records` là bản CANONICAL (đúng, do Bộ Công an xác nhận); `customers`/`businesses`
là bản CRM (khách tự khai, có thể lệch do vô tình hoặc cố ý). Tool so trực tiếp hai bảng —
agent KHÔNG tự so bằng mắt hay suy đoán độ giống tên.

- **Lệch họ tên** (khác dấu/gõ nhầm): hồ sơ ghi một tên, bản Công an ghi tên khác dù đọc
  gần giống — có thể chỉ là lỗi nhập liệu, NHƯNG cũng có thể là cách né đối chiếu (dùng tên
  không dấu/viết tắt để lách tìm kiếm). Xử lý: yêu cầu xác minh lại nhân thân, không tự
  kết luận "chắc gõ nhầm" mà bỏ qua.
- **Lệch địa chỉ** (địa chỉ cũ trong hồ sơ, địa chỉ mới ở bản Công an): thường là khách
  chuyển nơi cư trú nhưng chưa cập nhật CRM — mức độ rủi ro thấp hơn lệch tên/số giấy,
  nhưng vẫn phải yêu cầu cập nhật trước khi xử lý tiếp, vì địa chỉ sai ảnh hưởng cả xác
  minh cư trú lẫn liên hệ khi có tranh chấp sau này.
- **Lệch số giấy tờ** (CCCD lệch một vài chữ số): rủi ro CAO NHẤT trong ba kiểu — số giấy
  gần đúng nhưng không khớp có thể là gõ nhầm, nhưng CŨNG có thể là dùng giấy tờ giả/mượn
  danh có số gần giống số thật để né đối chiếu tự động. Không được coi đây là "lỗi chính tả
  nhỏ" — phải dừng xử lý và yêu cầu xác minh trực tiếp giấy tờ gốc trước khi đi tiếp.

Tool tự động cắm cờ khi phát hiện lệch (field cụ thể + giá trị hai bên) — agent phải TRÍCH
NGUYÊN giá trị lệch làm bằng chứng (không chỉ nói "có lệch nhân thân"), đúng luật cứng #4
của SKILL: dừng ở tên field là chưa đủ căn cứ.

## Tiền án tiền sự và thời hiệu
`police_records.criminal_status` có 3 giá trị cần phân biệt:
- `criminal_record` với loại thuộc `blocked_record_types` (gian lận tài chính, rửa tiền)
  → CHẶN CỨNG, không xét điều kiện, không có ngoại lệ.
- `criminal_record` loại KHÁC, đã kết thúc quá `criminal_record_expiry_years` → chuyển
  `conditional` (xét kèm các trụ khác), KHÔNG còn chặn thẳng — đây là ý nghĩa "thời hiệu":
  án đã đủ lâu không còn là rào cản tuyệt đối, nhưng vẫn phải được NÊU RA và cân nhắc, không
  phải "coi như không có".
- `under_investigation` (đang bị điều tra, chưa có kết luận): KHÔNG chặn cũng KHÔNG cho qua
  — tạm dừng xử lý chờ kết luận từ cơ quan chức năng. Đây không phải "chưa có tiền án" —
  phải nói rõ hồ sơ đang treo vì lý do gì.

## Honest-null
Không phải mọi owner đều có bản ghi Công an trong hệ thống — khi tool trả không có bản ghi,
phải nói "chưa có dữ liệu xác minh Công an cho khách này", KHÔNG được suy diễn ngược thành
"vậy chắc sạch". Honest-null và "sạch đã xác minh" là hai trạng thái khác nhau, gộp lại là
sai luật cứng #2 (không bịa khi thiếu dữ liệu).

## Liên hệ với ứng xử khách hàng
Cách nói với khách khi phát hiện lệch/tiền án — KHÔNG được nêu chi tiết nội bộ (loại tội
danh, năm, nguồn Công an) trực tiếp với khách: xem [[ung-xu-disclosure-khach-hang]].
