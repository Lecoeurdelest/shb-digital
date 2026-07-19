---
id: al-pr-01
role: products
title: AL-PR-01 — Tư vấn gói hết hiệu lực vì không soát văn bản (P005)
topic: case_law
tags: an-le,expired,tuan-thu
legal_basis: [[qd-2026-laisuat]]
effective_from: 2026-03-05
status: active
---

## Diễn biến
Khách C008 (Bùi Thị Lan, dược sĩ, thu nhập mức phổ thông, segment mass) tới quầy hỏi vay
tiêu dùng nhỏ, có nhắc "nghe nói dịp Tết có gói lãi 6,8%". RM tư vấn theo trí nhớ từ đợt
truyền thông Tết trước, xác nhận gói còn áp dụng và ghi nhận nhu cầu khách theo mức lãi đó
— trong khi thực tế P005 (Ưu đãi tiêu dùng Tết 6,8%) đã chuyển `status=expired` từ
01/03/2026 theo văn bản kế nhiệm [[qd-2026-laisuat]] thay thế [[qd-2025-tet]]. Khi hồ sơ lên
tới bước xác nhận lãi suất, hệ thống trả lãi thực tế cao hơn nhiều mức RM đã nói miệng —
khách phản ứng vì cảm thấy bị hứa hẹn sai.

## Nguyên nhân gốc
RM không tra `wiki_related_docs`/`wiki_lookup` trước khi xác nhận thông tin ưu đãi với
khách — dùng trí nhớ về một chương trình đã có mốc `effective_to` rõ ràng thay vì kiểm trạng
thái hiện hành. Đây đúng trap thiết kế tại [[uu-dai-tet-68]] và mô tả vòng đời tại
[[chuong-trinh-uu-dai]]: bản cũ và bản mới dễ bị nhầm nếu không đi cạnh thay-thế.

## Cách xử đúng (đã chốt thành luật)
1. Mọi câu hỏi về "gói ưu đãi/khuyến mãi theo tên hoặc mức lãi cụ thể" → tra
   `wiki_lookup`/`wiki_search` TRƯỚC khi xác nhận với khách, không trả lời bằng trí nhớ.
2. Gặp trang `status=expired`/`replaced` → nói rõ ngay với khách, không im lặng chuyển
   hướng khiến khách nghi ngờ bị giấu thông tin.
3. Đề xuất gói active tương đương ngay trong cùng lượt tư vấn (ở ca này: rà nhóm
   [[goi-tieu-dung-chuan]] hoặc [[goi-tieu-dung-linh-hoat]] nếu đủ điều kiện) — không để
   khách ra về tay không.

## Bài học cho agent
Trích dẫn văn bản ưu đãi PHẢI kèm kiểm tra hiệu lực tại thời điểm hỏi, không tại thời điểm
agent "nhớ". Đây là lý do citation của tool luôn kèm `status`/`effective_to` — agent đọc mà
bỏ qua trường này là lỗi tương đương không tra cứu.
