---
id: quy-trinh-xu-ly-ho-so
role: credit
title: Quy trình xử lý hồ sơ vay — từ tiếp nhận tới quyết định
topic: workflow
tags: quy-trinh,phe-duyet,green-lane
legal_basis: [[phan-cap-tham-quyen]]
effective_from: 2026-01-01
status: active
---

Trang này mô tả TRÌNH TỰ xử lý một hồ sơ vay; ai có thẩm quyền quyết định ở mỗi mức đã
có tại [[phan-cap-tham-quyen]] — hai trang bổ sung cho nhau, không lặp lại.

## Bước 1 — Tiếp nhận và xác minh (Legal chủ trì)
Đối chiếu ba trụ (nhân thân, CIC, thu nhập xác minh) — xem [[xac-minh-3-tru]] và
[[xac-minh-thu-nhap]]. Kết quả: hồ sơ được phân **lane xanh/vàng/đỏ** bởi tool phân
loại — Credit không tự gán lane.

## Bước 2 — Thẩm định khả năng trả (Credit)
Chỉ thực hiện sau khi có kết quả Bước 1. Tính DSCR/LTV/trần một khách bằng tool thẩm
định (xem [[chinh-sach-dscr-ltv]]), soát thêm red-flag tại [[red-flag-tham-dinh]] nếu
hồ sơ thuộc nhóm cần xét kỹ. Đầu ra: verdict `eligible` / `ineligible` / `needs_info`.

## Bước 3 — Rẽ nhánh theo lane + ngưỡng
- **Lane xanh** VÀ khoản vay dưới ngưỡng tự động (xem bảng tham số hệ thống) VÀ Credit
  kết luận `eligible` → đi thẳng **green-lane**: hệ thống tự phê duyệt, có biên nhận,
  KHÔNG cần người ký thêm.
- **Lane xanh nhưng vượt ngưỡng tự động** (kể cả khi mọi trụ đều sạch) → vẫn phải trình
  người — số tiền lớn tự nó là lý do cần người duyệt, không phải vì hồ sơ có vấn đề.
- **Lane vàng/đỏ, hoặc Credit kết luận `ineligible`/`needs_info`** → luôn trình người,
  không xét green-lane.

## Bước 4 — Trình người (khi không đủ điều kiện green-lane)
Hồ sơ kèm đầy đủ: kết quả 3 trụ, kết quả thẩm định Credit (kèm mọi cảnh báo/red-flag),
checklist giấy tờ (xem [[checklist-giay-to]]) — dùng mẫu tại
[[checklist-to-trinh]]. Người có thẩm quyền quyết định: duyệt / từ chối / yêu cầu bổ
sung. Agent KHÔNG tự đoán quyết định thay người, chỉ chuẩn bị hồ sơ đầy đủ nhất có thể.

## Bước 5 — Sau phê duyệt, trước giải ngân
Khoản thế chấp còn thủ tục công chứng + đăng ký giao dịch bảo đảm phải hoàn tất
(`procedures_done`) trước khi đủ điều kiện giải ngân — đây là cổng riêng, KHÔNG được
xem là đã xong chỉ vì người đã ký duyệt (xem [[phan-cap-tham-quyen]] mục bốn cổng).

## Nguyên tắc xuyên suốt
Mỗi bước chỉ chuyển tiếp khi bước trước có đầu ra RÕ RÀNG từ tool — không suy đoán kết
quả bước trước, không gộp bước để "cho nhanh". Hồ sơ dừng ở bước nào, ghi rõ đang dừng
vì thiếu gì.
