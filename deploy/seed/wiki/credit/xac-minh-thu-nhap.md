---
id: xac-minh-thu-nhap
role: credit
title: Sổ tay xác minh thu nhập trước khi tính khả năng trả nợ
topic: income_verification
tags: xac-minh,thu-nhap,dscr
legal_basis: [[xac-minh-3-tru]]
effective_from: 2026-01-01
status: active
---

**THAY THẾ**: [[xac-minh-thu-nhap-2024]] — quy trình cũ dựa trên xác nhận trực tiếp của
RM, không đối chiếu hệ thống, hết hiệu lực từ 01/01/2026.

## Hai loại thu nhập, không được lẫn
- **Thu nhập KÊ KHAI**: khách/RM ghi nhận ban đầu, coi là SƠ BỘ.
- **Thu nhập XÁC MINH**: kết quả đối chiếu sao kê lương/BHXH/hồ sơ việc làm, do Legal
  chạy tool xác minh và ghi nhận (trụ 3 tại [[xac-minh-3-tru]]).

Nguyên tắc: **DSCR tính bằng thu nhập KÊ KHAI chỉ là kết quả SƠ BỘ** — verdict phải ghi
rõ điều này. Ngay khi có thu nhập XÁC MINH, Credit PHẢI tính lại DSCR bằng số xác minh,
không giữ kết luận sơ bộ cũ.

## Ngưỡng lệch — ai xử lý gì
Lệch giữa kê khai và xác minh vượt ngưỡng cho phép (ngưỡng số cụ thể ở bảng tham số hệ
thống, không chép ở đây) → Legal gắn cờ hồ sơ và điều phối sang Credit để **tính lại
bằng số xác minh**, không dùng số kê khai làm căn cứ quyết định cuối. Lệch trong ngưỡng
→ dùng số kê khai như số xác minh, không cần cảnh báo thêm.

## Khi CHƯA có thu nhập xác minh
Không có nghĩa là "coi như đạt". Ghi verdict `needs_info`/sơ bộ, nêu rõ khoản còn thiếu
xác minh gì, và không đưa ra cam kết duyệt/từ chối chung cuộc dựa trên số kê khai đối
với hồ sơ có dấu hiệu rủi ro (thu nhập cao bất thường so với nghề nghiệp, nguồn thu
nhập không ổn định — hộ kinh doanh, kinh doanh tự do).

## Phối hợp Credit – Legal
- Legal SỞ HỮU quy trình xác minh (chạy tool, ghi nhận kết quả).
- Credit SỬ DỤNG kết quả xác minh làm đầu vào DSCR — không tự chạy xác minh, không tự
  suy đoán số xác minh khi chưa có.
- Hồ sơ nghề nghiệp có thu nhập khó xác minh bằng sao kê thông thường (kinh doanh tự
  do, hộ kinh doanh) → đối chiếu thêm dấu hiệu dòng tiền qua ghi chú tương tác RM, xem
  [[red-flag-tham-dinh]].

## Vì sao đổi từ 2026
Cách làm cũ (xem trang đã thay thế) để lộ khoảng trống: RM tự xác nhận miệng, không có
bản ghi đối chiếu máy-kiểm được, khi có tranh chấp không truy được nguồn. Quy trình mới
bắt buộc đi qua tool, có bản ghi ổn định, kết luận Credit luôn trỏ được về đúng lần xác
minh nào.
