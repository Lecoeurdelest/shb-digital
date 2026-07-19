---
id: al-op-01-giai-ngan-truoc-gdbd
role: operations
title: "AL-OP-01: Giải ngân khi chưa xong đăng ký GDBĐ"
topic: case_law
tags: an-le,gdbd,thu-tuc-chua-xong
legal_basis: gia-thuyet-lab — đúc từ hồ sơ thật trong hệ thống
effective_from: 2026-01-01
status: active
---

## Tình huống
Hồ sơ thế chấp đã qua thẩm định tín dụng đạt, pháp lý sạch, người có thẩm quyền đã ký phê
duyệt (`human_approval=granted`, có `approval_ref`) — mọi dấu hiệu "nhìn như xong". Thủ tục
sau phê duyệt gồm hai bước: công chứng hợp đồng thế chấp ĐÃ xong, nhưng đăng ký giao dịch
bảo đảm (GDBĐ) VẪN đang `pending`. Người yêu cầu (điều phối hoặc nhân viên) đề nghị giải
ngân vì "hồ sơ duyệt rồi, công chứng cũng xong rồi, chờ đăng ký làm gì cho chậm khách".

## Tool trả gì
`ops_disburse` verify đủ 4 cổng theo đúng thứ tự tại [[phan-cap-tham-quyen]] — thủ tục
`procedures_done` đòi CẢ HAI bước `done`, không phải một trong hai. Với hồ sơ đang ở tình
trạng "công chứng xong, đăng ký GDBĐ chưa", tool trả **đúng một blocker**:

```
procedure_pending: thủ tục 'collateral_registration' chưa hoàn tất
(công chứng/đăng ký GDBĐ xong mới giải ngân)
```

Ba cổng còn lại (credit_ok, legal_ok, human_approval) đều đạt — CHỈ thiếu đúng bước đăng ký.
Đây là ca "gần xong nhất có thể mà vẫn chặn" — dễ khiến người yêu cầu nghĩ "chỉ còn thủ tục
giấy tờ, chi trước cũng được".

## Vì sao KHÔNG được chi trước dù chỉ thiếu một bước
Đăng ký GDBĐ là bước xác lập hiệu lực đối kháng bên thứ ba của quyền nhận thế chấp — xem
[[cong-chung-dang-ky-gdbd]]. Giải ngân trước khi đăng ký xong nghĩa là ngân hàng đã chuyển
tiền trong khi quyền xử lý tài sản bảo đảm CHƯA được bảo vệ đầy đủ trước bên thứ ba (ví dụ
tài sản bị thế chấp trùng ở nơi khác, hoặc phát sinh giao dịch khác trên tài sản trong lúc
chờ đăng ký). Rủi ro này không đo được bằng "chậm bao lâu" mà là rủi ro mất quyền ưu tiên —
không có mức độ nào của "gấp" bù đắp được.

## Xử lý đúng
1. Trích nguyên văn blocker `procedure_pending` cho người yêu cầu.
2. Chỉ đúng bước đang treo (`collateral_registration`) và việc cần làm (hoàn tất đăng ký với
   cơ quan đăng ký) — không tự nhận việc thúc đẩy bên ngoài.
3. Nhắc: một khi bước đăng ký chuyển `done`, gọi lại `ops_app_get` để xác nhận cổng
   `procedures_done` đã đạt rồi mới thi hành `ops_disburse` — không đoán thời điểm xong.
4. Nếu bị giục "chỉ thiếu thủ tục hành chính" → xem thêm cách trả lời chuẩn tại
   [[xu-ly-su-co-giai-ngan]].

## Hậu quả nếu (giả định) đã lỡ chi trước
Nếu một hồ sơ tương tự đã bị chi trước khi đăng ký xong (ngoài luồng hệ thống này), đây là
sự kiện rủi ro pháp lý phải báo cáo Legal ngay, không phải lỗi vận hành có thể tự khắc phục
bằng cách hoàn tất đăng ký sau — thứ tự đã đảo thì không "sửa lại thứ tự" được, chỉ có thể
xử lý hậu quả.

## Liên kết
[[cong-chung-dang-ky-gdbd]] · [[phan-cap-tham-quyen]] · [[quy-trinh-giai-ngan]].
