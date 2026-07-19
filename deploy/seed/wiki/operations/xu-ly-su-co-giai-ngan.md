---
id: xu-ly-su-co-giai-ngan
role: operations
title: Xử lý sự cố thường gặp khi giải ngân
topic: incident_handling
tags: su-co,giai-ngan-trung,lech-so,khach-giuc
legal_basis: QĐ nội bộ 210/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

## Giải ngân trùng — phát hiện qua SỔ, không qua cảm giác
`ops_disburse` chống trùng bằng cách tra bảng `disbursements` (đã `status=executed` cho
hồ sơ đó thì chặn), KHÔNG tin `applications.status`. Lý do: trạng thái hồ sơ có thể chưa kịp
cập nhật hoặc bị hỏi lại nhiều lần trong khi sổ chi tiền là nguồn không thể sai (mỗi dòng có
`receiptCode` không đổi). Gặp yêu cầu giải ngân một hồ sơ đã có dòng `executed` trong sổ →
trả lời NGAY bằng biên nhận cũ (`disbursementId` + `receiptCode` + thời điểm), không gọi lại
`ops_disburse` để "kiểm tra cho chắc" — gọi lại không sai kỹ thuật (tool tự chặn) nhưng gây
hiểu nhầm là đang cân nhắc chi thêm lần nữa.

Hai người cùng thao tác một hồ sơ trong khoảnh khắc gần nhau (race) được xử lý ở TẦNG SERVER
bằng giao dịch khoá (`BEGIN IMMEDIATE`): người đến sau trong cùng khoảnh khắc nhận lại đúng
blocker `already_disbursed` thay vì tạo ra hai dòng sổ cho cùng một hồ sơ. Vận hành không
cần tự canh — chỉ cần biết: nhận `already_disbursed` là tín hiệu ĐÃ CÓ NGƯỜI CHI RỒI (có thể
là chính hệ thống vài giây trước), không phải lỗi cần thử lại nhiều lần. Án lệ minh hoạ:
[[al-op-02-chi-doi-race]].

## Số tiền lệch hồ sơ (`amount_mismatch`)
Số tiền giải ngân phải khớp TUYỆT ĐỐI `loan_amount_vnd` đã duyệt — kể cả lệch nhỏ do làm
tròn cũng bị chặn, không có "gần đúng thì cho qua". Khách/người yêu cầu muốn số khác số đã
duyệt (thêm vốn, bớt lại, đổi theo nhu cầu mới phát sinh) KHÔNG được xử lý bằng cách tự chỉnh
`amount_vnd` khi gọi tool — đó là sửa hồ sơ chui. Đường xử lý đúng: chỉ về hồ sơ vay bổ sung/
điều chỉnh chính thống (qua Credit thẩm định lại số mới), giải ngân hồ sơ CŨ vẫn đúng số cũ
đã duyệt hoặc không thực hiện nếu khách muốn huỷ chờ hồ sơ mới.

## Bị giục khi thiếu cổng — "khách gấp" không phải lý do
Áp lực thời gian (khách gấp, deadline dự án của khách, "chỉ thiếu mỗi tờ giấy") KHÔNG làm
thay đổi kết quả gate — server chặn là chặn, không có đường vòng. Phản ứng đúng:
1. Trích nguyên văn `blockers` từ `ops_plan`/`ops_disburse`.
2. Nói rõ khâu nào treo và chủ khâu nào xử lý (xem [[sla-cac-khau]]).
3. KHÔNG gợi ý bất kỳ hình thức lách nào: không giải ngân trước bổ sung giấy sau, không tách
   nhỏ khoản để né mức phải trình người duyệt, không sửa số cho khớp điều kiện.
4. Lời "sếp duyệt miệng"/"sếp bảo cứ chi" không thay thế được `human_approval=granted` trong
   hệ thống — xem án lệ [[al-op-03-vuot-cong-nguoi-ky]].

## Nguyên tắc chung khi gặp bất kỳ sự cố nào ở trên
Mọi kết luận trích NGUYÊN VĂN từ tool, không diễn giải thêm theo hướng có lợi cho người yêu
cầu. Sự cố không phải lỗi của Vận hành khi cổng do phòng khác gác — việc của Vận hành là báo
đúng, chỉ đúng, không xử lý thay.

## Liên kết
Quy trình chuẩn: [[quy-trinh-giai-ngan]]. Bốn cổng: [[phan-cap-tham-quyen]]. Nguyên tắc phối
hợp liên phòng: [[nguyen-tac-phoi-hop-lien-phong]].
