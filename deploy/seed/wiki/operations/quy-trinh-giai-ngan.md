---
id: quy-trinh-giai-ngan
role: operations
title: Quy trình giải ngân từng bước
topic: disbursement_process
tags: giai-ngan,quy-trinh,4-cong
legal_basis: QĐ nội bộ 210/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

## Bốn cổng — nhắc lại, không định nghĩa lại
Điều kiện giải ngân là **credit_ok · legal_ok · human_approval_resolved · procedures_done**,
định nghĩa gốc và ngưỡng tự-duyệt tại [[phan-cap-tham-quyen]]. Vận hành KHÔNG tự phán cổng
nào đạt — tool `ops_disburse` verify trọn bộ ở tầng server, thiếu một cổng là chặn, trả
`blockers` nguyên văn. Vai của Vận hành là THI HÀNH khi đủ, không phải xét lại.

## Trình tự một lệnh giải ngân
1. **Tra trạng thái** — `ops_app_get(application_id)`: xem status, 4 cổng, thủ tục còn lại,
   đã có biên nhận chưa. Đây là bước bắt buộc trước khi thi hành, kể cả khi người yêu cầu
   khẳng định "chắc xong rồi".
2. **Tra lộ trình** — `ops_plan(application_id)` nếu chưa rõ việc kế tiếp là gì; trả
   `nextAction` do server tính, trích thẳng.
3. **Thi hành** — chỉ khi được YÊU CẦU giải ngân, gọi `ops_disburse(application_id,
   amount_vnd, beneficiary?)`. Số tiền phải khớp TUYỆT ĐỐI `loan_amount_vnd` của hồ sơ đã
   duyệt — không làm tròn, không nhận số do người yêu cầu tự đọc miệng.
4. **Server ghi sổ** — đủ điều kiện thì tool ghi bảng `disbursements`, cập nhật
   `applications.status='disbursed'`, trả `disbursementId` + `receiptCode`.
5. **Trả biên nhận** — trích NGUYÊN VĂN `disbursementId` và `receiptCode` cho người yêu cầu;
   đây là chứng từ duy nhất xác nhận đã chi.

## Chứng từ đi kèm
Chứng từ giấy tờ hồ sơ (CCCD, chứng minh thu nhập, với khoản thế chấp thêm giấy tờ tài sản)
đã được Legal xác nhận đủ trước khi hồ sơ vào trạng thái chờ giải ngân — xem
[[checklist-giay-to]]. Vận hành không thu lại, không kiểm lại giấy tờ đã qua cổng Legal;
việc của Vận hành là chứng từ GIẢI NGÂN: lệnh chi + biên nhận, không phải hồ sơ vay gốc.

## Bên thụ hưởng theo mục đích vay
Tiền giải ngân chuyển cho bên thụ hưởng ĐÚNG mục đích vay đã khai trong hồ sơ (bên bán nhà,
nhà cung cấp, đơn vị thi công...), hạn chế chi tiền mặt trực tiếp cho người vay — nguyên tắc
tại [[phan-cap-tham-quyen]]. Nếu người yêu cầu không nêu bên thụ hưởng, tool tự điền tên chủ
hồ sơ làm mặc định; muốn chi cho bên khác phải nêu rõ và khớp mục đích vay đã duyệt, không
tự suy diễn bên thụ hưởng lạ.

## Biên nhận
Biên nhận gồm `disbursementId` (mã sổ) + `receiptCode` (mã biên lai, định dạng
`RC-2026-xxxxxx`) + thời điểm chấp hành. Đây là NGUỒN SỰ THẬT duy nhất về việc đã chi hay
chưa — không suy từ `status` của hồ sơ (một hồ sơ có thể ở `ready_to_disburse` do dữ liệu
chưa đồng bộ dù thực tế đã có biên nhận, xem [[xu-ly-su-co-giai-ngan]]). Mọi câu trả lời về
"đã chi chưa" phải tra sổ `disbursements`, không tra `applications.status`.

## Liên kết
Thủ tục phải xong trước khi tới bước 3: [[cong-chung-dang-ky-gdbd]]. Sau khi chi xong còn
việc theo dõi: [[checklist-sau-giai-ngan]]. Sự cố thường gặp: [[xu-ly-su-co-giai-ngan]].
