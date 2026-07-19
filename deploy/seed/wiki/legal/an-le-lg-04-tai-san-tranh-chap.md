---
id: an-le-lg-04-tai-san-tranh-chap
role: legal
title: AL-LG-04 — Tài sản thế chấp đang tranh chấp thừa kế
topic: case_law
tags: an-le,tsdb,tranh-chap,tu-choi
legal_basis: gia-thuyet-lab
effective_from: 2026-01-01
status: active
---

## Tình huống
Khách C002 (chính chủ, đúng người đứng tên trong hệ thống — khác AL-LG-01 là ca sai chủ
thể) xin vay thế chấp bằng COL01 (nhà 3 tỷ). Khoản xin vay 2,4 tỷ → LTV = 0.80, đã VƯỢT
trần `ltv_max` (0.70) — đây là trap đã biết ở tầng Credit. Nhưng ngay cả khi giả định số
tiền vay thấp hơn để LTV đạt, hồ sơ vẫn phải TỪ CHỐI vì một lý do HOÀN TOÀN ĐỘC LẬP:
`collateral_legal` ghi nhận COL01 có `dispute_status='disputed'` — nhà đang tranh chấp thừa
kế giữa các đồng sở hữu.

## Vì sao đây là ca "2 lý do từ chối" — không được chỉ nêu 1
Đây là bẫy hay gặp: nếu chỉ nhìn số (LTV vượt trần), agent dễ kết luận "chỉ cần giảm số tiền
vay xuống dưới 70% định giá là ổn". Kết luận đó SAI — vì kể cả khi số tiền vay giảm để LTV
đạt, tài sản vẫn KHÔNG ĐỦ ĐIỀU KIỆN nhận thế chấp do đang tranh chấp. Hai lý do từ chối này
ĐỘC LẬP với nhau: một lý do là bài toán TÀI CHÍNH (LTV, việc Credit/số liệu), một lý do là
bài toán PHÁP LÝ TÀI SẢN (tranh chấp, việc Legal). Sửa lý do này không tự động giải quyết
lý do kia — agent phải nêu ĐỦ CẢ HAI khi cả hai đều đúng, không dừng ở lý do dễ thấy trước.

## Vì sao tranh chấp là CẤM TUYỆT ĐỐI, không phải "cần thêm giấy"
Tài sản đang tranh chấp thừa kế nghĩa là quyền sở hữu CHƯA XÁC ĐỊNH RÕ RÀNG giữa các đồng
thừa kế — nhận thế chấp một tài sản như vậy tạo rủi ro pháp lý cực lớn: nếu tranh chấp ngã
theo hướng bất lợi, hợp đồng thế chấp có thể bị vô hiệu hoặc ngân hàng mất quyền xử lý tài
sản khi cần. Đây KHÔNG phải trường hợp "thiếu giấy, bổ sung là xong" (như `missing_ownership_
cert`) — nó là tình trạng pháp lý TỰ THÂN của tài sản, không thể khắc phục bằng cách nộp
thêm giấy tờ. Xem điều kiện nhận thế chấp đầy đủ ở [[quy-trinh-tsdb]] bước 1.

## Xử lý đúng
1. Gọi `legal_check_docs(owner_id='C002', collateral_id='COL01')` → nhận cờ
   `collateral_disputed`, verdict `blocked`.
2. Nêu RÕ cả hai lý do nếu cả hai cùng đúng trong ca cụ thể: định giá/LTV (nếu được hỏi) VÀ
   tình trạng tranh chấp — không chọn một để trả lời cho gọn.
3. Không gợi ý "chờ tranh chấp giải quyết xong rồi quay lại vay" như một cam kết — chỉ nêu
   đây là điều kiện cần có để tài sản đủ điều kiện, không hứa trước kết quả tương lai.

## Kết luận đúng
"Nhà tại COL01 hiện đang trong tình trạng tranh chấp thừa kế giữa các đồng sở hữu theo dữ
liệu pháp lý tài sản — không đủ điều kiện nhận thế chấp dù định giá đạt yêu cầu. Đây là vấn
đề pháp lý tài sản, độc lập với việc tính toán số tiền vay." Không nêu chi tiết nội bộ về
các bên tranh chấp — chỉ nêu tình trạng chung, theo [[ung-xu-disclosure-khach-hang]].
