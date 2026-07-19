---
id: quy-trinh-tsdb
role: legal
title: Quy trình xử lý tài sản đảm bảo — nhận thế chấp đến đăng ký GDBĐ
topic: collateral_process
tags: tsdb,the-chap,cong-chung,gdbd
legal_basis: Nghị định đăng ký biện pháp bảo đảm (gia-thuyet-lab)
effective_from: 2025-06-01
status: active
---

Khoản vay thế chấp (secured) không kết thúc ở "duyệt hồ sơ" — còn 3 bước THỦ TỤC TÀI SẢN
ĐẢM BẢO (TSĐB) phải xong mới đủ điều kiện giải ngân. Đây là mảnh mà agent hay bỏ sót vì
tưởng "duyệt xong là giải ngân được" — xem cổng `procedures_done` ở
[[phan-cap-tham-quyen]].

## Bước 1 — Nhận thế chấp (thẩm định pháp lý tài sản)
Trước khi nhận bất kỳ tài sản nào làm bảo đảm, phải xác nhận ĐỦ 2 điều kiện độc lập:
1. **Đúng chủ thể**: `collaterals.owner_id` phải là chính khách vay (hoặc bên thứ ba đồng ý
   bảo lãnh bằng tài sản — trường hợp riêng, cần hồ sơ bảo lãnh tách bạch, KHÔNG phải khách
   vay tự ý dùng tài sản người khác dưới danh nghĩa của mình). Server chặn cứng bằng lỗi
   `collateral_owner_mismatch` khi hai id không khớp — xem án lệ
   [[an-le-lg-01-muon-so-do-nguoi-than]].
2. **Sạch pháp lý**: `collateral_legal.dispute_status` phải `clean` (không tranh chấp) và
   `zoning_status` không phải `planning_zone` (không vướng quy hoạch). Tool `legal_check_docs`
   trả field này khi có `collateral_id`. Tài sản `disputed` bị TỪ CHỐI nhận thế chấp bất kể
   định giá cao thế nào — xem [[an-le-lg-04-tai-san-tranh-chap]].

Song song, đối chiếu giấy tờ tài sản: `ownership_cert` phải `valid`; nếu tài sản chung vợ
chồng thì cộng thêm `marriage_cert` — xem [[checklist-giay-to-ly-do]].

## Bước 2 — Công chứng hợp đồng thế chấp
Hợp đồng thế chấp phải được CÔNG CHỨNG mới có giá trị đối kháng bên thứ ba (không phải chỉ
ký nội bộ ngân hàng-khách). Đây là bước nằm NGOÀI hệ thống ngân hàng (phòng công chứng), lab
này ghi nhận trạng thái bằng `procedure_steps.step='notarization'` (`pending`/`done`) trong
mission Operations — Legal có trách nhiệm xác nhận bước này đã xong trước khi coi hồ sơ
pháp lý hoàn tất, KHÔNG tự suy "chắc công chứng rồi".

## Bước 3 — Đăng ký giao dịch bảo đảm (GDBĐ)
Sau công chứng, phải ĐĂNG KÝ GDBĐ tại cơ quan có thẩm quyền (văn phòng đăng ký đất đai với
bất động sản) — đây là bước xác lập THỨ TỰ ƯU TIÊN thanh toán khi tài sản bị xử lý (nếu
không đăng ký, ngân hàng có nguy cơ mất quyền ưu tiên trước bên nhận thế chấp khác đăng ký
sau nhưng đăng ký trước). Trạng thái ghi ở `procedure_steps.step='collateral_registration'`.
Quy trình đăng ký hiện hành (liên thông điện tử): xem [[qd-moi-dang-ky-gdbd-lien-thong]]
— văn bản cũ quy định đăng ký thủ công đã HẾT HIỆU LỰC, xem
[[qd-cu-dang-ky-gdbd-thu-cong]].

## Luật làm việc
- Cả 3 bước phải xong (`notarization=done` VÀ `collateral_registration=done`) mới được coi
  là `procedures_done` — thiếu MỘT bước cũng chặn giải ngân, kể cả khi hồ sơ đã
  `human_approval=granted`. Đây đúng là trap "duyệt người rồi nhưng thủ tục dở dang" mà
  Operations gặp phải — Legal phải nói rõ ràng bước nào còn thiếu, không nói chung chung
  "chưa xong thủ tục".
- Agent Legal KHÔNG tự xác nhận trạng thái công chứng/đăng ký — đây là dữ liệu server ghi
  nhận từ tác nghiệp thật (Operations), Legal chỉ TRA và DIỄN GIẢI ý nghĩa pháp lý của
  từng trạng thái khi được hỏi.
