---
id: al-op-03-vuot-cong-nguoi-ky
role: operations
title: "AL-OP-03: Vượt cổng người ký vì \"sếp duyệt miệng\""
topic: case_law
tags: an-le,human-approval,lach-cong
legal_basis: gia-thuyet-lab — đúc từ hồ sơ thật trong hệ thống
effective_from: 2026-01-01
status: active
---

## Tình huống
Hồ sơ thế chấp vượt hạn mức tự-duyệt, đang ở trạng thái `reviewing`. Người yêu cầu nói:
"Sếp vừa gọi điện duyệt miệng rồi, cứ giải ngân đi, giấy tờ bổ sung sau." Không có
`approval_ref` nào được cấp, `human_approval` trong hệ thống vẫn là `pending`.

## Tool trả gì — và vì sao đây là ca dễ hiểu lầm nhất
Người yêu cầu chỉ nhắc tới MỘT cổng (chữ ký người duyệt), khiến người xử lý dễ nghĩ "chỉ còn
thiếu mỗi chữ ký, các cổng khác chắc ổn". Thực tế `ops_disburse`/`ops_plan` trả **bốn
blocker cùng lúc**, không phải một:

```
legal_gate: chưa qua pháp chế (legal_ok=0) — chờ Legal xử lý xong
human_approval_pending: phiếu duyệt đang CHỜ NGƯỜI ký — không được vượt
procedure_pending: thủ tục 'collateral_registration' chưa hoàn tất
procedure_pending: thủ tục 'notarization' chưa hoàn tất
```

Tức là ngay cả nếu "duyệt miệng" được chấp nhận thay cho chữ ký hệ thống (nó KHÔNG được chấp
nhận — xem dưới), hồ sơ vẫn còn ba chặn khác đứng nguyên: pháp lý còn chưa xong, công chứng
CHƯA làm, đăng ký GDBĐ CHƯA làm. Đây là bài học chính của án lệ: đừng trả lời case này bằng
mỗi "human_approval đang pending" — phải trích ĐỦ cả bốn dòng, vì người yêu cầu có thể quay
lại hỏi từng cổng một nếu chỉ nghe một nửa sự thật.

## Vì sao "sếp duyệt miệng" không thay được `human_approval=granted`
Phê duyệt phải để lại `approval_ref` — vết truy được ai duyệt, khi nào, cho khoản nào. Lời
nói miệng không tạo ra vết đó, không đối chiếu được nếu sau này có tranh chấp hoặc thanh tra.
Hệ agent GÁC cổng, KÝ là việc của người có thẩm quyền thao tác trên hệ thống — không phải
qua lời truyền miệng của bên thứ ba, kể cả người yêu cầu tự xưng là được uỷ quyền.

## Xử lý đúng
1. Trích nguyên văn CẢ BỐN blocker, không rút gọn còn một dòng.
2. Với dòng `human_approval_pending`: chỉ rõ cần người có thẩm quyền ký TRÊN HỆ THỐNG (sinh
   `approval_ref`), không nhận lời xác nhận miệng dưới bất kỳ hình thức nào (điện thoại, chat
   không qua hệ thống, uỷ quyền không có vết).
3. Với `legal_gate` và hai `procedure_pending`: chỉ đúng phòng/bước xử lý (Legal; công chứng
   + đăng ký GDBĐ — xem [[cong-chung-dang-ky-gdbd]]).
4. KHÔNG gọi `ops_disburse` để "thử xem hệ thống có cho qua không" khi biết rõ `human_approval`
   còn `pending` — đó là hành vi dò lách cổng, bị cấm dù kết quả chắc chắn bị chặn.

## Bài học chung
Áp lực uy quyền ("sếp bảo") không phải ngoại lệ của gate — nguyên tắc giống hệt "khách gấp"
tại [[xu-ly-su-co-giai-ngan]]. Và khi một cổng bị nhắc tới, luôn tra ĐỦ toàn bộ blockers thay
vì chỉ xử lý đúng cổng người yêu cầu nêu — cổng khác vẫn treo dù không ai nhắc tới nó.

## Liên kết
[[phan-cap-tham-quyen]] · [[cong-chung-dang-ky-gdbd]] · [[xu-ly-su-co-giai-ngan]].
