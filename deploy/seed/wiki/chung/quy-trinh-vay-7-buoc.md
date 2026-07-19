---
id: quy-trinh-vay-7-buoc
role: chung
title: Quy trình vay 7 bước toàn hàng
topic: process_overview
tags: quy-trinh,lien-phong,tong-quan
legal_basis: gia-thuyet-lab — tổng hợp từ quy trình từng phòng
effective_from: 2026-01-01
status: active
---

Một khoản vay đi qua đúng 7 bước, mỗi bước một phòng chủ trì, bàn giao cho bước sau bằng
KẾT QUẢ đã có trong hệ thống (không phải mô tả lại bằng lời). Nguyên tắc dùng-nguyên-kết-quả
xem [[nguyen-tac-phoi-hop-lien-phong]].

## 1. Chọn sản phẩm — Products
Tư vấn/RM đối chiếu nhu cầu khách với danh mục gói vay đang hiệu lực (tín chấp/thế chấp/
doanh nghiệp), loại ngay gói đã hết hiệu lực hoặc bị thay thế bởi văn bản mới. Bàn giao:
`product_id` phù hợp + hạn mức/kỳ hạn khung của gói.

## 2. Mở hồ sơ vận hành — Operations
Hồ sơ (`application`) được tạo với `owner_id`, `product_id`, `loan_amount_vnd`, `loan_type`,
`collateral_id` (nếu thế chấp). Đây là bản ghi DUY NHẤT theo dõi xuyên suốt các bước sau —
mọi phòng sau đều tra/ghi vào đúng hồ sơ này, không tạo bản ghi song song riêng.

## 3. Thẩm định tín dụng — Credit
Tính DSCR/LTV bằng tool, đối chiếu ngưỡng ([[chinh-sach-dscr-ltv]]). Đạt → `credit_ok=1`.
Không đạt → hồ sơ dừng ở đây, không chuyển bước tiếp cho tới khi có phương án đạt (giảm số
tiền vay, bổ sung tài sản, hoặc từ chối).

## 4. Thẩm tra pháp lý — Legal
Ba trụ xác minh (nhân thân, CIC, thu nhập — [[xac-minh-3-tru]]) + checklist giấy tờ
([[checklist-giay-to]]) + kiểm mục đích vay hạn chế + trần dư nợ (đơn và nhóm liên quan).
Đạt hết → `legal_ok=1` và hồ sơ được phân lane green/yellow/red.

## 5. Xét thẩm quyền phê duyệt — Credit (quy tắc) / cấp có thẩm quyền (quyết định)
Lane green + trong hạn mức tự-duyệt → hệ agent tự phê duyệt, không cần bước 6. Vượt hạn mức
hoặc lane yellow/red hoặc thế chấp bất động sản → bắt buộc trình người (nguyên tắc phân cấp
tại [[ma-tran-tham-quyen]]).

## 6. Ký phê duyệt — Cấp có thẩm quyền (khi hồ sơ thuộc diện bước 5 bắt buộc)
Người có thẩm quyền ký trên hệ thống, sinh `approval_ref` — vết duy nhất được công nhận là
đã duyệt. Không có bước này với hồ sơ đã tự-duyệt ở bước 5.

## 7. Thủ tục sau duyệt + Giải ngân — Operations
Khoản thế chấp: công chứng + đăng ký GDBĐ theo đúng thứ tự
([[cong-chung-dang-ky-gdbd]]). Đủ 4 cổng (`credit_ok`, `legal_ok`,
`human_approval_resolved`, `procedures_done`) → thi hành giải ngân
([[quy-trinh-giai-ngan]]), trả biên nhận. Sau đó chuyển giai đoạn theo dõi
([[checklist-sau-giai-ngan]]).

## Điều chỉnh giữa chừng
Khách đổi ý (đổi số tiền, đổi tài sản, đổi mục đích) ở bất kỳ bước nào sau bước 2 → không
sửa hồ sơ hiện tại chắp vá, quay lại bước tương ứng với dữ liệu mới (thường là mở lại từ
bước 3 nếu đổi số tiền/tài sản, vì DSCR/LTV phải tính lại).

## Liên kết
[[ma-tran-tham-quyen]] · [[nguyen-tac-phoi-hop-lien-phong]] · [[nguyen-tac-nguon-so]] ·
[[glossary]].
