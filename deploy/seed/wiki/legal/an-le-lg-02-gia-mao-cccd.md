---
id: an-le-lg-02-gia-mao-cccd
role: legal
title: AL-LG-02 — Lệch số CCCD một chữ số, nghi giả mạo nhân thân
topic: case_law
tags: an-le,kyc,gian-lan,cccd
legal_basis: gia-thuyet-lab
effective_from: 2026-01-01
status: active
---

## Tình huống
Khách C020 nộp hồ sơ với CCCD số kết thúc `...741`. Gọi `legal_check_police('C020')`, tool
đối chiếu `police_records` (bản Bộ Công an) trả số đúng kết thúc `...740` — LỆCH ĐÚNG MỘT
CHỮ SỐ CUỐI so với hồ sơ khách nộp. Tất cả các trường khác (họ tên, địa chỉ) khớp hoàn toàn.

## Vì sao đây là ca khó — không được xử nhẹ tay
Trực giác thường thấy "lệch một số, chắc gõ nhầm khi nhập liệu" — CHÍNH XÁC vì lệch nhỏ và
dễ tin là lỗi vô tình nên đây là dạng rủi ro cao: một chữ số lệch có thể là (a) lỗi đánh máy
thật, hoặc (b) cố ý dùng số CCCD gần giống số thật (của người khác, hoặc số bị chỉnh sửa)
để né các hệ thống đối chiếu tự động chỉ so khớp tuyệt đối. KYC không được phép coi "gần
đúng" tương đương "đúng" — xem nguyên tắc phân loại rủi ro theo kiểu lệch ở
[[kyc-gian-lan-nhan-than]] (lệch số giấy tờ = rủi ro cao nhất trong ba kiểu lệch thường gặp).

## Xử lý đúng
1. KHÔNG tự kết luận "chắc gõ nhầm, cho qua" — kể cả khi mọi trường khác khớp hoàn hảo và hồ
   sơ trông rất sạch.
2. KHÔNG tự kết luận "chắc gian lận" — tool chỉ cắm cờ lệch, không kết luận động cơ. Phải
   nói đúng những gì tool xác nhận: có lệch, lệch ở đâu, lệch giá trị nào.
3. Trích NGUYÊN giá trị lệch làm bằng chứng: "hồ sơ ghi CCCD kết thúc 741, dữ liệu Bộ Công
   an ghi kết thúc 740 — lệch đúng 1 chữ số" — không dừng ở "có cờ lệch nhân thân" chung
   chung (luật cứng #4 của SKILL: dừng ở tên field là chưa đủ căn cứ).
4. Yêu cầu xác minh trực tiếp bằng giấy tờ gốc trước khi xử lý tiếp hồ sơ — hồ sơ TẠM DỪNG
   ở bước này, không tiến tới các trụ khác (CIC, thu nhập) như thể nhân thân đã xác nhận
   xong.

## Kết luận đúng
"Hồ sơ có lệch số CCCD (741 so với 740 theo dữ liệu Bộ Công an) — cần khách xuất trình giấy
tờ gốc để xác minh trước khi xử lý tiếp, chưa thể kết luận đạt/trượt ở bước nhân thân." Khi
báo với khách, KHÔNG nói "hệ thống nghi anh/chị gian lận" — chỉ nói cần xác minh lại thông
tin giấy tờ, theo đúng cách ứng xử ở [[ung-xu-disclosure-khach-hang]].
