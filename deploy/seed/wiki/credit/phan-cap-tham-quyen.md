---
id: phan-cap-tham-quyen
role: credit
title: Phân cấp thẩm quyền phê duyệt và giải ngân
topic: approval_authority
tags: phe-duyet,phan-cap,giai-ngan
legal_basis: QĐ nội bộ 401/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

## Nguyên tắc
Hệ agent là MỘT CẤP THẨM QUYỀN có hạn mức — như giám đốc chi nhánh có hạn mức của mình.
Trong hạn mức + hồ sơ đạt chuẩn → tự phê duyệt, có biên nhận. Vượt → trình người.

## Hạn mức tự động (green-lane)
- Hồ sơ lane **green** (phân loại bởi tool `legal_classify_profile`, tiêu chí tại
  [[xac-minh-3-tru]]) VÀ khoản vay ≤ **2 tỷ VND** (assumptions `auto_approve_max_vnd`)
  → được tự phê duyệt.
- Vượt 2 tỷ, hoặc lane yellow/red, hoặc vay thế chấp bất động sản → BẮT BUỘC người duyệt.

## Bốn cổng trước giải ngân (assumptions `disburse_requires`)
`credit_ok` (thẩm định đạt) · `legal_ok` (pháp lý sạch) · `human_approval_resolved`
(người đã duyệt nếu thuộc diện) · `procedures_done` (thủ tục sau phê duyệt xong — công
chứng, đăng ký GDBĐ với khoản thế chấp, xem [[checklist-giay-to]]).
Thiếu BẤT KỲ cổng nào, lệnh giải ngân không thực thi được — chặn ở tầng tool.

## Giải ngân đúng đối tượng
Chuyển khoản cho BÊN THỤ HƯỞNG theo mục đích vay (bên bán nhà, nhà cung cấp...),
hạn chế giải ngân tiền mặt trực tiếp cho người vay (TT39 — gia-thuyet-lab).
