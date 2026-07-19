---
id: chinh-sach-dscr-ltv
role: credit
title: Ngưỡng thẩm định DSCR và LTV
topic: dscr_ltv
tags: dscr,ltv,tham-dinh
legal_basis: QĐ nội bộ 118/QĐ-SHB (gia-thuyet-lab)
effective_from: 2025-06-01
status: active
---

## DSCR — hệ số trả nợ
DSCR = thu nhập tháng / tổng nghĩa vụ trả tháng (nợ hiện có + khoản xin vay, tính annuity).
Ngưỡng đạt: **DSCR ≥ 1.2** (assumptions `dscr_min`). DSCR PHẢI tính bằng tool
`credit_assess` — cấm nhẩm tay.

## LTV — tỷ lệ cho vay trên tài sản
LTV = khoản vay / giá trị định giá tài sản thế chấp. Trần: **LTV ≤ 0.70**
(assumptions `ltv_max`). Vượt trần → giảm số tiền vay hoặc bổ sung tài sản.

## Thu nhập dùng để tính
Ưu tiên thu nhập XÁC MINH (trụ 3 tại [[xac-minh-3-tru]]); nếu mới có kê khai thì kết quả
là SƠ BỘ — ghi rõ trong verdict. Lệch kê khai vs xác minh >10% → bắt buộc tính lại.

## Lãi suất tham chiếu khi tính nghĩa vụ
Tín chấp 15%/năm kỳ hạn chuẩn 60 tháng · thế chấp 8%/năm 180 tháng (assumptions
`rate_consumer_annual`/`rate_secured_annual`) — cấu hình theo [[qd-2026-laisuat]].
