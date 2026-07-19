---
id: checklist-to-trinh
role: credit
title: Checklist tờ trình tín dụng
topic: checklist
tags: checklist,to-trinh
legal_basis: QĐ nội bộ 118/QĐ-SHB (gia-thuyet-lab)
effective_from: 2025-06-01
status: active
---

Tờ trình gửi người có thẩm quyền (bước 4 tại [[quy-trinh-xu-ly-ho-so]]) phải đủ các
mục dưới đây — thiếu mục nào, ghi rõ "chưa có" thay vì bỏ trống không giải thích.

## 1. Thông tin hồ sơ
- Định danh khách/doanh nghiệp, mục đích vay, số tiền và loại khoản (tín chấp/thế
  chấp), kỳ hạn đề xuất.
- Mục đích vay đã tra [[muc-dich-vay-han-che]] chưa — banned/conditional/không hạn chế.

## 2. Kết quả ba trụ (Legal)
- Nhân thân: sạch / có tiền án (loại gì, năm nào) / đang điều tra.
- CIC: nhóm mấy, có bị chặn cứng không (xem [[phan-loai-no-cic]]).
- Thu nhập: kê khai vs xác minh, có lệch quá ngưỡng không (xem [[xac-minh-thu-nhap]]).
- Lane phân loại: xanh/vàng/đỏ.

## 3. Kết quả thẩm định Credit
- DSCR, LTV (nếu có tài sản đảm bảo), tổng dư nợ hiện có, đối chiếu trần một khách/trần
  nhóm liên quan — TẤT CẢ lấy từ tool thẩm định, ghi rõ thời điểm tính (`asOf`).
- Verdict: `eligible` / `ineligible` / `needs_info`, kèm lý do (`reasons`) và thiếu sót
  (`missing`) y nguyên như tool trả về — không diễn giải lại làm mất chi tiết.
- Mọi cảnh báo (`warnings`): số bất thường, red-flag đã soát tại
  [[red-flag-tham-dinh]] — liệt kê đủ, không lọc bớt vì "có vẻ không quan trọng".

## 4. Giấy tờ
- Bộ giấy bắt buộc theo loại khoản đã đủ chưa (xem [[checklist-giay-to]]).
- Nếu thế chấp: tình trạng pháp lý tài sản (tranh chấp/quy hoạch) đã soát chưa.

## 5. Đề xuất và căn cứ thẩm quyền
- Đề xuất của Credit (duyệt/từ chối/cần bổ sung) — LÀ ĐỀ XUẤT, không phải quyết định
  cuối nếu hồ sơ thuộc diện phải trình người (xem [[phan-cap-tham-quyen]]).
- Cấp thẩm quyền cần trình (theo hạn mức + lane).

## 6. Chữ ký / xác nhận
- Người lập tờ trình, ngày lập.
- Trường chữ ký người phê duyệt — để trống nếu chưa qua bước duyệt, không tự điền thay.

## Nguyên tắc khi lập
Tờ trình PHẢN ÁNH kết quả tool, không phải nơi Credit tự tính toán lại hay làm tròn số
cho "dễ đọc". Mọi số trong tờ trình phải truy được về đúng một lần gọi tool.
