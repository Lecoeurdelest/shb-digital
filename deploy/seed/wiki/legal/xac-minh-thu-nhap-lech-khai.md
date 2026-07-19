---
id: xac-minh-thu-nhap-lech-khai
role: legal
title: Xác minh thu nhập và xử lý lệch kê khai
topic: income_verification
tags: thu-nhap,xac-minh,lech-khai,dscr
legal_basis: QĐ nội bộ 305/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

Trụ ③ của [[xac-minh-3-tru]] tóm tắt luật lệch-lương trong một câu — trang này diễn giải
CHI TIẾT cơ chế, vì đây là điểm hay bị agent làm sai: tính lệch nhầm chiều, hoặc quên báo
điều phối.

## Hai nguồn thu nhập, không trộn lẫn
- `customers.monthly_income` (và tương đương phía Credit) = số KHÁCH TỰ KÊ KHAI khi làm hồ
  sơ. Đây là lời khai, chưa được xác minh độc lập.
- `employment_records.verified_income_vnd` = số XÁC MINH — do tool `legal_verify_employment`
  đối chiếu sao kê lương/BHXH, là bản CANONICAL cho mục đích thẩm định pháp lý.

Hai số này KHÔNG được coi ngang nhau. Khi có lệch, số verified LUÔN thắng — kê khai chỉ là
tham chiếu ban đầu.

## Công thức lệch và ngưỡng
Tool tính `gap = (declared − verified) / verified`, so với `income_mismatch_max_pct` (10%):
- **Lệch ≤ 10%**: nằm trong ngưỡng, coi như khớp — KHÔNG cắm cờ, không cần hành động thêm,
  DSCR Credit đã tính vẫn giữ nguyên.
- **Lệch > 10%**: cắm cờ `income_mismatch` — bắt buộc BÁO điều phối viên đề nghị Credit TÍNH
  LẠI khả năng trả (DSCR) bằng `verified_income`, không phải bằng số kê khai đã dùng trước
  đó. Legal KHÔNG tự tính lại DSCR (đó là việc Credit) — chỉ phát hiện lệch, định lượng %
  lệch, và CHUYỂN YÊU CẦU tính lại đúng chỗ.

## Khi nào đề nghị tính lại — quy tắc quyết định
1. Có `employment_records` cho owner này? Nếu KHÔNG (honest-null, ví dụ doanh nghiệp dùng
   BCTC/CIC thay cho "quá trình làm việc" cá nhân) → không áp cơ chế lệch-lương này, nói rõ
   "không áp dụng xác minh việc làm cá nhân cho pháp nhân".
2. Bản ghi có `status='expired'`? → không tính được gap đáng tin (số xác minh đã cũ) — yêu
   cầu cập nhật hồ sơ việc làm mới, KHÔNG dùng số cũ để kết luận đạt/trượt.
3. Bản ghi `status='active'` và có gap > 10% → cắm cờ + báo điều phối như trên.
4. Gap ≤ 10% → không hành động gì thêm, tiếp tục quy trình bình thường.

## Vì sao ngưỡng 10% chứ không phải "bất kỳ lệch nào"
Kê khai và xác minh gần như không bao giờ khớp tuyệt đối 100% (làm tròn, thời điểm chốt
lương khác kỳ kê khai...) — chặn ở MỌI lệch dù nhỏ sẽ chặn oan phần lớn hồ sơ hợp lệ.
Ngưỡng 10% (`income_mismatch_max_pct`) là ranh phân biệt "sai số tự nhiên" với "khai khống
đáng kể" — số này nằm ở `assumptions`, agent không tự đặt ngưỡng khác.

## Không tự tính tay
Luật cứng #1 của SKILL: MỌI đối chiếu lệch phải qua tool `legal_verify_employment`, cấm agent
tự cộng trừ % lệch bằng nhẩm tay rồi kết luận. Số liệu sai một ly ở bước này kéo theo DSCR
Credit tính lại cũng sai — trách nhiệm định lượng luôn ở tool, agent chỉ đọc kết quả và
chuyển đúng hành động kế tiếp.
