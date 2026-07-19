---
id: al-cr-03-sanity-so-to
role: credit
title: AL-CR-03 — Thừa một chữ số 0, khoản vay phóng to gấp bội
topic: case_law
tags: an-le,sanity-check,nhap-lieu
legal_basis: Nội bộ — biên bản rút kinh nghiệm (gia-thuyet-lab)
effective_from: 2026-03-01
status: active
---

## Bối cảnh
Trong một vòng thao tác nhập số tiền xin vay, người nhập gõ thừa MỘT chữ số 0 khi điền
số tiền — biến một khoản vay ở quy mô hợp lý thành một con số lớn gấp nhiều lần trần
cho vay một khách. Vì hệ thống vẫn CHẤP NHẬN số đó về mặt kiểu dữ liệu (một số dương hợp
lệ), tool thẩm định vẫn chạy và trả kết quả — nhưng kết quả đó là thẩm định cho một con
số SAI, không phải ý định thật của người nhập.

## Vì sao đây không chỉ là "lỗi gõ phím"
Nếu tool chỉ báo "vượt trần một khách" như một khoản vay lớn thông thường, người đọc dễ
hiểu nhầm đây là một khoản vay lớn CÓ THẬT cần trình cấp rất cao, thay vì một lỗi nhập
liệu cần SỬA LẠI SỐ rồi thẩm định lại. Hai tình huống cần hai hành động khác nhau hoàn
toàn: trình duyệt cấp cao vs. sửa lại số và chạy lại.

## Cơ chế đã có để bắt lỗi này
Tool thẩm định có một mức cảnh báo RIÊNG cho số tiền lớn bất thường (vượt trần một
khách một số lần đáng kể) — đây là CẢNH BÁO MỀM (`warnings`), không phải chặn cứng: tool
không tự ý cho rằng số là sai (có thể đúng là khách hàng doanh nghiệp lớn thật), nhưng
buộc người đọc phải TỰ XÁC NHẬN LẠI đơn vị và số chữ số trước khi xử lý tiếp.

## Bài học
1. **Nghi THƯỚC trước khi nghi hồ sơ.** Số ra bất thường lớn/nhỏ so với hồ sơ tương tự
   → việc đầu tiên là xác nhận lại số đã nhập đúng đơn vị (VND, không phải nghìn/triệu/tỷ
   nhầm lẫn) và đúng số chữ số — KHÔNG phải lập tức trình hồ sơ lên cấp rất cao hoặc kết
   luận khách hàng có nhu cầu bất thường.
2. Cảnh báo số bất thường trong tool là gợi ý HÀNH ĐỘNG KẾ TIẾP ("xác nhận lại đơn vị"),
   không phải bản án — đọc `warnings` không có nghĩa hồ sơ tự động sai, nhưng CŨNG không
   được bỏ qua cảnh báo đó.
3. Sau khi xác nhận số đúng đơn vị/đúng ý định khách hàng, luôn CHẠY LẠI thẩm định với
   số đã sửa — không dùng kết quả của lần chạy sai số làm căn cứ cho bất kỳ bước nào
   sau đó, kể cả khi phần còn lại của hồ sơ (CIC, giấy tờ) không đổi.

## Liên quan
[[khau-vi-rui-ro]] · [[chinh-sach-dscr-ltv]]
