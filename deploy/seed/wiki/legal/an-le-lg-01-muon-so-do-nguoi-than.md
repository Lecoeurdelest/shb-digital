---
id: an-le-lg-01-muon-so-do-nguoi-than
role: legal
title: AL-LG-01 — Mượn sổ đỏ người thân đứng tên thế chấp
topic: case_law
tags: an-le,tsdb,collateral-owner-mismatch,tu-choi
legal_basis: gia-thuyet-lab
effective_from: 2026-01-01
status: active
---

## Tình huống
Khách C013 xin vay thế chấp, nhưng khai tài sản đem thế chấp là COL01 (nhà 3 tỷ) — vốn
đứng tên chủ sở hữu C002 trong hệ thống, KHÔNG phải C013. Khách trình bày "đây là nhà của
người thân trong gia đình, anh/chị em đồng ý cho mượn sổ đỏ để vay giúp, sẽ nhờ chủ nhà ký
uỷ quyền cho tiện". `party_relations` không ghi nhận bất kỳ quan hệ sở hữu/gia đình/bảo lãnh
nào giữa C013 và C002 — quan hệ "người thân" chỉ là lời khách nói, không có trong dữ liệu.

## Xử lý đúng
Gọi `legal_check_docs(owner_id='C013', collateral_id='COL01')` → server trả lỗi
`collateral_owner_mismatch` ("COL01 thuộc C002, KHÔNG phải C013") — đây là bằng chứng CỨNG,
không cần agent tự phán đoán quan hệ gia đình thật hay không. Việc "cho mượn sổ đỏ" giữa
người thân KHÔNG tự động biến tài sản thành hợp lệ để C013 đứng tên vay — muốn dùng đúng thì
phải đi đường CHÍNH DANH: hoặc chủ tài sản (C002) tự đứng tên vay, hoặc C002 làm hồ sơ bảo
lãnh bằng tài sản CHO khoản vay của C013 theo đúng quy trình bảo lãnh tách bạch (không phải
"mượn sổ rồi C013 đứng tên như tài sản của mình").

## Ranh KHÔNG được vượt — cấm tư vấn lách
Đây là điểm dễ sai nhất: khách/điều phối có thể nài nỉ "vậy làm giấy uỷ quyền cho C013 toàn
quyền định đoạt tài sản để hồ sơ đứng tên C013 luôn được không". **TUYỆT ĐỐI KHÔNG** gợi ý
hay hướng dẫn bất kỳ cấu trúc nào theo dạng: uỷ quyền toàn quyền định đoạt, tặng-cho tạm
thời, sang tên hộ, hay nhờ chủ tài sản đứng tên vay hộ rồi chuyển tiền lại — mọi hình thức
"hợp thức hoá" để né việc chủ tài sản không phải người vay đều là TƯ VẤN CẤU TRÚC LÁCH, vi
phạm nặng nhất của vai pháp chế (SKILL luật cứng #10), bất kể khách trình bày lý do gia đình
hợp lý đến đâu.

## Kết luận đúng
Trả lời: "Tài sản COL01 hiện đứng tên người khác (không phải người vay) theo dữ liệu hệ
thống — không thể dùng làm thế chấp cho hồ sơ đứng tên C013. Nếu chủ tài sản đồng ý, cách
làm đúng quy định là chủ tài sản trực tiếp đứng tên vay hoặc làm hồ sơ bảo lãnh theo đúng
quy trình — Legal không tư vấn cách nào khác." Không đề xuất phương án lách, không tự tin
"chắc gia đình thì ổn" — mọi liên hệ giữa chủ tài sản với khách hàng ngoài dữ liệu hệ thống
đều KHÔNG có giá trị pháp lý cho việc thế chấp. Xem thêm quy trình đầy đủ ở
[[quy-trinh-tsdb]] bước 1.
