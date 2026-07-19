---
id: cong-chung-dang-ky-gdbd
role: operations
title: Công chứng và đăng ký giao dịch bảo đảm (GDBĐ) — khoản thế chấp
topic: procedures_secured
tags: gdbd,cong-chung,the-chap,thu-tuc
legal_basis: QĐ nội bộ 214/QĐ-SHB + Nghị định đăng ký biện pháp bảo đảm (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

## Vì sao chỉ khoản thế chấp (secured) mới có bước này
Khoản tín chấp (`consumer`) không có tài sản bảo đảm nên không có thủ tục GDBĐ — hồ sơ
`loan_type=secured` mới sinh dòng trong bảng `procedure_steps`. Tra thủ tục còn lại của một
hồ sơ bằng `ops_app_get`/`ops_plan`, KHÔNG giả định thủ tục xong chỉ vì hồ sơ đã có
`human_approval=granted` — phê duyệt và thủ tục là hai việc khác nhau.

## Thứ tự bắt buộc — không đảo được
1. **Công chứng hợp đồng thế chấp** (`notarization`) — hai bên (ngân hàng, bên thế chấp) ký
   hợp đồng thế chấp trước phòng công chứng. Đây là điều kiện TIÊN QUYẾT của bước 2.
2. **Đăng ký giao dịch bảo đảm** (`collateral_registration`) — đăng ký hợp đồng thế chấp ĐÃ
   CÔNG CHỨNG với cơ quan đăng ký (đất đai/động sản tuỳ loại tài sản). Đây là bước xác lập
   hiệu lực đối kháng bên thứ ba — chưa đăng ký thì quyền ưu tiên xử lý tài sản của ngân
   hàng CHƯA được bảo vệ nếu phát sinh tranh chấp với bên thứ ba khác.

Hai bước này PHẢI xong theo đúng thứ tự trên, và cả hai phải `status=done` thì cổng
`procedures_done` mới đạt (định nghĩa tại [[phan-cap-tham-quyen]]). Đăng ký GDBĐ trước khi
công chứng xong là vô nghĩa về pháp lý — hệ thống không cho trạng thái này xảy ra hợp lệ,
gặp thì đó là dấu hiệu nhập liệu sai, báo Legal kiểm tra lại, không tự sửa.

## Lỗi hay gặp
- **Coi phê duyệt = xong thủ tục.** `human_approval=granted` chỉ nghĩa là người có thẩm
  quyền đã ký phiếu duyệt khoản vay — KHÔNG đồng nghĩa hợp đồng thế chấp đã công chứng/đăng
  ký. Hai việc chạy song song sau khi duyệt, không phải tuần tự nhân quả.
- **Giải ngân khi mới công chứng, chưa đăng ký.** Đây là án lệ chuẩn — xem
  [[al-op-01-giai-ngan-truoc-gdbd]].
- **Nhầm tài sản đăng ký với tài sản kê khai.** `collateral_id` trên hồ sơ phải khớp đúng
  tài sản đã công chứng; đổi tài sản giữa chừng phải làm lại thủ tục từ bước 1, không tiếp
  nối thủ tục cũ.
- **"Đăng ký tạm/hẹn lịch" tính là done.** Chỉ trạng thái `done` với `done_at` ghi nhận trong
  hệ thống mới được tính; lịch hẹn, biên nhận nộp hồ sơ đăng ký chưa phải là hoàn tất.

## Vai của Vận hành trong hai bước này
Vận hành KHÔNG thực hiện công chứng/đăng ký (việc của bộ phận pháp lý/khách hàng phối hợp
phòng công chứng, cơ quan đăng ký) — Vận hành chỉ TRA trạng thái qua `ops_app_get` và BÁO
đúng thủ tục nào đang treo, dùng đúng câu chữ server trả (`procedure_pending: thủ tục
'<tên bước>' chưa hoàn tất`). Không ước lượng "chắc sắp xong", không tự đánh dấu xong hộ.

## Liên kết
Bốn cổng tổng thể: [[phan-cap-tham-quyen]]. Checklist giấy tờ tài sản: [[checklist-giay-to]].
Quy trình giải ngân đầy đủ: [[quy-trinh-giai-ngan]]. Án lệ liên quan:
[[al-op-01-giai-ngan-truoc-gdbd]].
