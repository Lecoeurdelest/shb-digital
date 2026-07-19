---
id: sla-cac-khau
role: operations
title: SLA từng khâu và tiêu chí "quá hạn"
topic: sla
tags: sla,quy-trinh,quá-hạn
legal_basis: QĐ nội bộ 210/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

## Nguyên tắc — khung, không phải con số
Thời hạn cụ thể của từng khâu (bao nhiêu ngày làm việc) là THAM SỐ nghiệp vụ, sống ở bảng
`assumptions` (tag giả-thuyết, có thể đổi theo lô sếp chốt) — trang này KHÔNG chép số, chỉ
mô tả khâu nào có đồng hồ chạy và khi nào tính là quá hạn. Muốn biết con số hiện hành, tra
`assumptions` qua tool tương ứng, không nhớ từ văn bản này.

## Các khâu có đồng hồ SLA
1. **Thẩm định tín dụng** (credit_ok) — từ khi hồ sơ đủ hồ sơ tới khi Credit trả kết quả
   đạt/không đạt. Chủ khâu: Credit.
2. **Thẩm tra pháp lý** (legal_ok) — ba trụ xác minh, xem [[xac-minh-3-tru]]. Chủ khâu: Legal.
3. **Trình và ký phê duyệt** (`human_approval`) — với hồ sơ vượt hạn mức tự-duyệt
   ([[phan-cap-tham-quyen]]). Chủ khâu: cấp thẩm quyền, Vận hành chỉ theo dõi trạng thái
   `pending` chuyển sang `granted`/`denied`.
4. **Công chứng + đăng ký GDBĐ** (`procedures_done`, khoản thế chấp) — xem
   [[cong-chung-dang-ky-gdbd]]. Chủ khâu: khách hàng phối hợp Vận hành/Legal, phụ thuộc lịch
   cơ quan bên ngoài (phòng công chứng, cơ quan đăng ký) nên độ trễ có thể ngoài kiểm soát
   nội bộ — vẫn phải theo dõi và báo cáo, không mặc nhiên coi là "được miễn trừ SLA".
5. **Thi hành giải ngân** (`ops_disburse`) — từ lúc đủ 4 cổng tới lúc có biên nhận; khâu này
   ngắn nhất vì là bước máy-thực-thi, không phải bước xét duyệt.

## Khi nào tính là quá hạn
Một khâu quá hạn khi thời gian ở trạng thái `pending`/chưa xong VƯỢT ngưỡng tham số của
đúng khâu đó (không phải tính từ ngày mở hồ sơ). Vận hành phát hiện quá hạn qua chênh lệch
giữa `created_at`/`done_at` (nếu có) trong `ops_app_get` với ngưỡng tham số — không tự ước
lượng bằng cảm giác "để lâu rồi".

## Xử lý khi phát hiện quá hạn
Quá hạn KHÔNG phải lý do để lách cổng hay tự chi trước — xem [[xu-ly-su-co-giai-ngan]] mục
"khách gấp". Việc của Vận hành khi phát hiện quá hạn: báo đúng khâu đang treo + chủ khâu
tương ứng (theo bảng trên) để phòng chuyên môn xử lý, không tự làm hộ, không giục bằng
cách gọi thử `ops_disburse` (gọi thử vẫn tính là một lần yêu cầu, có thể gây hiểu nhầm là đã
xin giải ngân).

## Liên kết
Bốn cổng: [[phan-cap-tham-quyen]]. Quy trình đầy đủ: [[quy-trinh-giai-ngan]]. Nguyên tắc số
liệu toàn hàng: [[nguyen-tac-nguon-so]].
