---
id: xac-minh-3-tru
role: legal
title: Ba trụ xác minh hồ sơ trước phê duyệt
topic: verification
tags: xac-minh,nhan-than,cic,thu-nhap
legal_basis: QĐ nội bộ 305/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

Khâu pháp lý-tuân thủ duyệt hồ sơ dựa trên BA TRỤ, mọi trụ lấy từ tool — cấm tự nhớ:

## Trụ 1 — Nhân thân (mapping dữ liệu Bộ Công an)
Đối chiếu hồ sơ với dữ liệu dân cư + tiền án tiền sự (tool `legal_check_police`).
Loại tiền án CHẶN CỨNG: gian lận tài chính, rửa tiền (assumptions `blocked_record_types`).
Án khác đã kết thúc > 7 năm (`criminal_record_expiry_years`) → conditional, không chặn thẳng.

## Trụ 2 — Lịch sử tín dụng CIC
CIC nhóm ≥ 3 (`cic_block_min_group`) → CHẶN theo tuân thủ. Nhóm 2 → cảnh báo, xét kèm
các trụ khác. Chi tiết phân nhóm: [[phan-loai-no-cic]].

## Trụ 3 — Việc làm và thu nhập xác minh
Tool `legal_verify_employment` trả thu nhập XÁC MINH (sao kê/BHXH). Lệch so với kê khai
≤ 10% (`income_mismatch_max_pct`) → chấp nhận; LỆCH > 10% → gắn cờ, đề nghị điều phối
cho Credit TÍNH LẠI khả năng trả bằng thu nhập xác minh — không dùng số kê khai.

## Tổng hợp
Ba trụ + checklist [[checklist-giay-to]] + mục đích [[muc-dich-vay-han-che]] + trần
[[tran-cho-vay]] → tool `legal_classify_profile` phân lane green/yellow/red (máy tính,
ghi bảng `assessments`) — agent không tự phán lane.
