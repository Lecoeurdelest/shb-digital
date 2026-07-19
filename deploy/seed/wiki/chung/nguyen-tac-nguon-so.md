---
id: nguyen-tac-nguon-so
role: chung
title: Nguyên tắc nguồn số — mọi số từ hệ thống, văn bản là căn cứ diễn giải
topic: data_source_principle
tags: nguyen-tac,nguon-so,tool
legal_basis: gia-thuyet-lab — nguyên tắc vận hành hệ agent
effective_from: 2026-01-01
status: active
---

## Nguyên tắc gốc
Con số nghiệp vụ (ngưỡng DSCR/LTV, trần dư nợ, hạn mức tự-duyệt, hạn SLA, nhóm nợ CIC...)
KHÔNG sống trong wiki. Wiki giải thích Ý NGHĨA và CÁCH DÙNG của con số; con số thật sống ở
bảng `assumptions` (và các bảng nghiệp vụ khác: `applications`, `disbursements`,
`procedure_steps`...), lấy ra qua tool. Đây là lý do một khái niệm như "trần cho vay" có
trang wiki (giải thích công thức, ai áp dụng, khi nào phải tra) nhưng KHÔNG có con số phần
trăm cứng trong chính trang đó.

## Vì sao tách — hai nguồn số là drift
Nếu wiki chép số VÀ bảng tham số cũng có số, hai nơi sẽ lệch nhau sau lần đổi tham số đầu
tiên (mà chỉ có một nơi được cập nhật) — hậu quả là agent trích số SAI mà vẫn "có căn cứ
văn bản", nguy hiểm hơn cả không có căn cứ vì trông có vẻ đáng tin. Tách nguồn buộc CHỈ MỘT
nơi có thể sai lệch — sửa tham số ở một chỗ, mọi tool và mọi câu trả lời tự động dùng số mới.

## Áp dụng khi trả lời
- Số liệu định lượng (ngưỡng, tỷ lệ, hạn mức, dư nợ, DSCR/LTV tính toán) → LUÔN qua tool,
  không tự nhẩm, không chép từ trang wiki ra đọc như thể đó là số cuối.
- Văn bản (wiki) dùng để trả lời "tại sao", "áp dụng thế nào", "thứ tự làm gì trước" — những
  câu không có một con số cụ thể làm đáp án.
- Khi một câu hỏi cần CẢ hai (ví dụ "khoản này có vượt trần không") → tra tool lấy số, tra
  wiki lấy định nghĩa/công thức, kết luận ghép cả hai, trích nguồn cho từng phần.

## Dấu hiệu vi phạm cần tự sửa ngay
- Trả lời có con số cụ thể mà không kèm citation tool (`asOf`, tên tool đã gọi).
- Trích một con số từ wiki rồi trình bày như kết quả tính toán cuối cùng.
- Nhớ số từ lần hỏi trước thay vì gọi lại tool cho câu hỏi mới (số có thể đã đổi).

## Với trang bị thay thế/hết hiệu lực
Trang wiki có `status=replaced`/`expired` không được dùng làm căn cứ cho kết luận mới, dù
số liệu cũ trong đó có vẻ vẫn hợp lý — luôn đi cạnh document-graph (`wiki_related_docs`) để
tìm bản hiện hành, xem ví dụ trap tại [[uu-dai-tet-68]].

## Liên kết
[[quy-trinh-vay-7-buoc]] · [[ma-tran-tham-quyen]] · [[sla-cac-khau]].
