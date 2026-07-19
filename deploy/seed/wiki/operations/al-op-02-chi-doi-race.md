---
id: al-op-02-chi-doi-race
role: operations
title: "AL-OP-02: Chi đôi do hai người cùng thao tác (race)"
topic: case_law
tags: an-le,chi-doi,race,double-disburse
legal_basis: gia-thuyet-lab — đúc từ hồ sơ thật trong hệ thống
effective_from: 2026-01-01
status: active
---

## Tình huống 1 — hỏi lại một hồ sơ đã chi
Hồ sơ tín chấp đủ 4 cổng từ trước, đã được giải ngân, sổ `disbursements` có dòng
`status=executed` kèm biên nhận. `applications.status` của hồ sơ này vẫn hiển thị
`ready_to_disburse` — KHÔNG tự cập nhật hồi tố khi tra nhanh bằng mắt. Một người yêu cầu
khác (không biết đã chi, hoặc chi nhánh khác hỏi lại) đề nghị giải ngân hồ sơ này lần nữa.

## Tool trả gì
`ops_disburse` không tin `applications.status` — luôn tra bảng `disbursements` trước. Với
hồ sơ đã có dòng `executed`, tool trả blocker:

```
already_disbursed: ĐÃ giải ngân (DSB<id>, biên nhận RC-2026-xxxxxx, <thời điểm>)
— cấm giải ngân đôi
```

Đây là blocker DUY NHẤT trong ca này — ba cổng kia không còn ý nghĩa kiểm tra lại vì tiền đã
ra khỏi ngân hàng. Xử lý đúng: trích nguyên văn biên nhận CŨ, khẳng định đã chi, không gọi
lại tool thêm lần nào để "thử xem có chặn thật không" — gọi thử không sai kỹ thuật nhưng
không cần thiết và có thể gây hiểu nhầm với người yêu cầu là đang cân nhắc chi thêm.

## Tình huống 2 — race: hai lệnh gần như đồng thời
Khác tình huống 1 (đã có sổ từ trước, tra được ngay), race là khi HAI lệnh `ops_disburse`
cho CÙNG một hồ sơ tới gần như cùng lúc — ví dụ hai đầu mối cùng xử lý một hồ sơ mà không
biết người kia cũng đang thao tác. Nếu hệ thống chỉ tính số dòng sổ hiện có để sinh mã dòng
mới mà không khoá, cả hai lệnh có thể cùng đọc "chưa có dòng nào", cùng định sinh một mã, và
một trong hai sẽ ghi đè hoặc gây lỗi dữ liệu (hai biên nhận cho một khoản chi, hoặc mã trùng).

Server chặn bằng giao dịch có khoá: lệnh tới trước mở giao dịch, kiểm tra sổ TRONG giao dịch
đó, ghi và đóng giao dịch; lệnh tới sau — dù đọc gần như cùng thời điểm — buộc phải chờ giao
dịch trước đóng lại rồi mới đọc, lúc đó đã thấy dòng `executed` và tự nhận blocker
`already_disbursed` giống Tình huống 1. Trường hợp cực hiếm hai giao dịch cùng mở được cùng
lúc ở tầng hệ quản trị dữ liệu, hệ thống trả lỗi ghi đồng thời (`concurrent_write`/
`ledger_busy`) thay vì âm thầm tạo hai dòng sổ — đây là kết quả AN TOÀN (từ chối rõ ràng),
không phải lỗi cần khắc phục bằng cách thử lại ngay lập tức.

## Xử lý đúng khi gặp `concurrent_write`/`ledger_busy`
KHÔNG lặp lại `ops_disburse` liên tiếp. Gọi `ops_app_get` để xem sổ đã có dòng `executed`
chưa — có thì dùng biên nhận đó, chưa có thì mới thử lại một lần.

## Bài học chung
Nguồn sự thật của "đã chi hay chưa" luôn là bảng `disbursements`, không phải
`applications.status` và không phải trí nhớ của người yêu cầu ("chắc chưa ai chi đâu"). Mọi
câu trả lời về việc đã giải ngân phải tra sổ, dù người hỏi khẳng định chắc chắn thế nào.

## Liên kết
[[quy-trinh-giai-ngan]] · [[xu-ly-su-co-giai-ngan]].
