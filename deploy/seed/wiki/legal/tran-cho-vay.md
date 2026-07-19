---
id: tran-cho-vay
role: legal
title: Trần cho vay một khách hàng và nhóm liên quan
topic: tran_cho_vay
tags: limit,exposure,tuan-thu
legal_basis: Luật TCTD Điều 127 (gia-thuyet-lab)
effective_from: 2025-01-01
status: active
---

## Trần dư nợ một khách hàng
Tổng dư nợ cấp cho MỘT khách hàng không vượt **15% vốn tự có** của ngân hàng
(assumptions: `single_customer_cap_pct=0.15`, `bank_equity_bil_vnd=50000` tỷ → trần một
khách = **7.500 tỷ VND**).

## Trần dư nợ nhóm khách hàng liên quan
Tổng dư nợ của một khách hàng VÀ NGƯỜI CÓ LIÊN QUAN không vượt **25% vốn tự có**
(assumptions: `related_group_cap_pct=0.25` → trần nhóm = **12.500 tỷ VND**).

Định nghĩa "người có liên quan" và cách tính dư nợ nhóm: xem [[nhom-khach-lien-quan]].

## Luật áp dụng khi thẩm định
1. Khoản vay xin cấp + dư nợ hiện tại của khách ≤ trần một khách.
2. Khoản vay xin cấp + tổng dư nợ CẢ NHÓM liên quan ≤ trần nhóm.
3. Một khoản có thể QUA trần đơn nhưng VỠ trần nhóm — bắt buộc tra quan hệ liên đới
   (tool `legal_related_exposure`) trước khi kết luận, không được tra phẳng từng khách.
