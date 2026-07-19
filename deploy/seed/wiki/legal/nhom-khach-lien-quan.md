---
id: nhom-khach-lien-quan
role: legal
title: Nhóm khách hàng liên quan — định nghĩa và cách tính
topic: related_party
tags: exposure,quan-he,tuan-thu
legal_basis: Luật TCTD Điều 4 (gia-thuyet-lab)
effective_from: 2025-01-01
status: active
---

## Quan hệ tính là "liên quan"
- **Sở hữu**: cá nhân/pháp nhân sở hữu ≥ 20% vốn điều lệ của pháp nhân khác (`owns_pct`).
- **Điều hành**: chủ tịch / người đại diện pháp luật của pháp nhân.
- **Bảo lãnh**: người bảo lãnh cho nghĩa vụ trả nợ của khách vay.
- **Gia đình**: vợ/chồng, cha mẹ, con của cá nhân vay.

## Cách tính dư nợ nhóm
Dư nợ nhóm = tổng `outstanding` mọi khoản vay ACTIVE của TẤT CẢ thành viên nhóm
(đi quan hệ tới 2 bậc — ví dụ cá nhân → công ty A → công ty B mà A sở hữu ≥20%).

Tool `legal_related_exposure(owner_id)` trả: danh sách thành viên nhóm, đường quan hệ
từng người, tổng dư nợ nhóm, đối chiếu trần tại [[tran-cho-vay]].

## Ví dụ điển hình phải bắt
Doanh nghiệp xin vay sạch hồ sơ, NHƯNG chủ tịch đồng thời sở hữu doanh nghiệp khác
đang dư nợ lớn → cộng nhóm vượt trần → từ chối/trình cấp cao, dù từng khoản riêng lẻ đều đạt.
