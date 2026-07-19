---
id: al-pr-02
role: products
title: AL-PR-02 — Khoe lãi thấp giấu phí cao dẫn tới khiếu nại (P013)
topic: case_law
tags: an-le,rate-vs-fee,khieu-nai
legal_basis: [[qd-2026-laisuat]]
effective_from: 2026-04-10
status: active
---

## Diễn biến
Khách C011 (Đỗ Minh Phúc, lập trình viên, thu nhập tốt, CIC nhóm 1, segment mass) đủ điều
kiện cả nhóm [[goi-tieu-dung-linh-hoat]] (P003/P004/P013). RM chào P013 với lý do "lãi thấp
nhất trong các gói anh đủ điều kiện" — đúng theo `recommend_by=rate_annual_asc` — nhưng
KHÔNG nhắc tới phí của P013 cao hơn hẳn nhóm còn lại. Khách ký hồ sơ theo ấn tượng "lãi thấp
nhất = tiết kiệm nhất". Khi nhận bảng tính tổng chi phí thực tế ở bước giải ngân, khách phát
hiện chi phí cả kỳ hạn cao hơn phương án P004 mà không hề được so sánh — khiếu nại RM tư vấn
không đầy đủ, có dấu hiệu che giấu thông tin bất lợi.

## Nguyên nhân gốc
RM đọc đúng khuyến nghị mặc định của server (rate thấp nhất) nhưng DỪNG LẠI ở đó, không tự
đối chiếu thêm trường phí trong cùng kết quả `product_suggest` — vi phạm đúng luật cứng đã
ghi tại [[goi-tieu-dung]] và mô tả chi tiết tại [[goi-tieu-dung-linh-hoat]]: "recommend theo
rate thấp nhất" là quy tắc MÁY, không miễn trừ nghĩa vụ CON NGƯỜI phải nêu đánh đổi tổng chi
phí.

## Cách xử đúng (đã chốt thành luật)
1. Khi khuyến nghị một gói vì lãi thấp, PHẢI đọc và nêu luôn phí của chính gói đó trong CÙNG
   câu trả lời — không tách hai thông tin ra hai lượt hội thoại khác nhau.
2. Với khách hỏi "gói nào lợi nhất", ước tổng chi phí theo kỳ hạn khách dự kiến (không chỉ
   nêu % rời rạc) để khách hình dung được số tuyệt đối, đặc biệt khoản vay lớn.
3. Không có lỗi khi khuyến nghị đúng gói lãi thấp nhất — lỗi nằm ở CHE GIẤU đặc điểm còn lại
   của chính gói đó, dù không cố ý.

## Bài học cho agent
"Trích nguyên văn kết quả tool" không đồng nghĩa "chỉ đọc trường mà server nhấn mạnh". Mọi
trường liên quan tới chi phí thực tế của khách (rate VÀ fee) đều phải xuất hiện cùng lúc
trong kết luận — đây là ranh giữa "đúng nhưng gây hiểu lầm" và "đúng và đủ".
