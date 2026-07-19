---
id: ma-tran-tham-quyen
role: chung
title: Ma trận thẩm quyền — nguyên tắc phân cấp
topic: authority_matrix
tags: tham-quyen,phan-cap,phe-duyet
legal_basis: QĐ nội bộ 401/QĐ-SHB (gia-thuyet-lab)
effective_from: 2026-01-01
status: active
---

## Nguyên tắc — không chép số ở đây
Trang này mô tả NGUYÊN TẮC phân cấp; con số hạn mức cụ thể (trần tự-duyệt, trần một khách,
trần nhóm liên quan...) sống ở bảng `assumptions`, tra qua tool tương ứng của từng phòng —
xem [[nguyen-tac-nguon-so]]. Lý do tách: số là tham số có thể đổi theo quyết định mới của
ngân hàng, văn bản diễn giải nguyên tắc thì ổn định hơn — hai nguồn số là drift, cấm.

## Ba trục quyết định ai được quyền gì
1. **Hạn mức số tiền** — mỗi cấp thẩm quyền (kể cả hệ agent, coi như MỘT cấp có hạn mức
   riêng) chỉ được tự quyết trong hạn mức của mình. Vượt hạn mức → trình cấp cao hơn, không
   tự ý "linh động" xử lý trong khi chờ.
2. **Mức độ rủi ro hồ sơ** — hồ sơ được phân loại (lane green/yellow/red qua ba trụ xác minh,
   xem [[xac-minh-3-tru]]) quyết định có được tự-duyệt hay không, ĐỘC LẬP với số tiền. Hồ sơ
   nhỏ nhưng rủi ro cao vẫn phải trình người, không chỉ xét theo số tiền.
3. **Loại tài sản/loại vay** — một số loại (điển hình: thế chấp bất động sản) bắt buộc người
   duyệt bất kể hạn mức, vì rủi ro pháp lý tài sản không nằm trong năng lực xét tự động.

Ba trục là ĐIỀU KIỆN CẦN đồng thời — đạt cả ba mới được tự-duyệt; thiếu một trục là phải
trình người.

## Ai xét, ai duyệt, ai thi hành — không lẫn ba vai
- **Credit** thẩm định số liệu (DSCR/LTV) và tính điểm phân loại — KHÔNG tự phê duyệt hồ sơ
  vượt hạn mức của chính mình.
- **Legal** xác minh điều kiện tuân thủ, phân lane — KHÔNG quyết định số tiền được vay.
- **Người có thẩm quyền** (khi hồ sơ vượt hạn mức tự-duyệt) là chủ thể DUY NHẤT được ký phê
  duyệt cho vượt hạn mức — không phòng nghiệp vụ nào, kể cả hệ agent, tự nhận thay vai này.
- **Operations** thi hành khi đã đủ điều kiện (đã duyệt, đã đạt cổng) — KHÔNG xét lại điều
  kiện đã do phòng khác kết luận, KHÔNG tự phê duyệt hộ dưới bất kỳ hình thức nào (kể cả khi
  được yêu cầu "cứ chi trước vì chắc chắn đạt").

## Ghi vết bắt buộc
Mọi quyết định vượt hạn mức phải để lại vết truy được (mã phê duyệt gắn với người ký, thời
điểm, hồ sơ liên quan). Không có vết = không công nhận là đã phê duyệt, kể cả khi có xác
nhận bằng lời — xem án lệ [[al-op-03-vuot-cong-nguoi-ky]].

## Liên kết
[[phan-cap-tham-quyen]] (chi tiết 4 cổng + hạn mức, Credit) · [[xac-minh-3-tru]] (phân lane,
Legal) · [[quy-trinh-vay-7-buoc]] · [[nguyen-tac-nguon-so]].
