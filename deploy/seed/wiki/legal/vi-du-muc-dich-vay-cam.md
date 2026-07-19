---
id: vi-du-muc-dich-vay-cam
role: legal
title: Ví dụ thực tế — mục đích vay cấm và có điều kiện
topic: purpose
tags: muc-dich,tuan-thu,vi-du
legal_basis: TT39/2016/TT-NHNN Điều 8 (gia-thuyet-lab)
effective_from: 2025-01-01
status: active
---

Trang [[muc-dich-vay-han-che]] liệt kê danh mục máy đọc (`restricted_purposes`, tool
`legal_check_compliance`). Trang này gắn VÍ DỤ THỰC TẾ cho từng mã, để agent nhận diện được
mục đích cấm khi khách diễn đạt bằng lời thường (không ai nói đúng từ "bds_speculation").

## Cấm tuyệt đối (banned) — không có ngoại lệ, không có "điều kiện gì thì cho"

**`bds_speculation` — đầu cơ bất động sản**
Ví dụ lời khách: "vay để mua lô đất ở khu quy hoạch mới, chờ giá lên bán lại", "ôm thêm vài
mảnh đất vùng ven đợi sốt đất". Phân biệt với mua nhà để Ở hoặc mua nhà cho thuê dài hạn có
phương án trả nợ rõ ràng — đầu cơ là mua để CHỜ TĂNG GIÁ rồi bán, không có mục đích sử dụng/
khai thác. Khi mơ hồ giữa "mua để ở" và "mua để lướt sóng" → hỏi thẳng khách mục đích cụ thể,
không tự suy diễn.

**`gambling` — cờ bạc/cá cược**
Ví dụ: "vay để đặt cược thể thao", "gỡ vốn sòng bài". Cấm tuyệt đối, không cần thẩm định
thêm gì.

**`crypto_trading` — đầu tư tiền mã hoá**
Ví dụ: "vay để mua thêm coin đang lỗ", "đầu tư một dự án tiền số bạn bè giới thiệu". Cấm kể
cả khi khách trình bày có "chiến lược" hay "đã lãi trước đó" — mục đích thuộc danh mục cấm
là cấm, không xét độ khả thi của chiến lược đầu tư.

## Có điều kiện (conditional) — cần cấp phê duyệt xét riêng, KHÔNG phải "cứ đủ giấy là duyệt"

**`securities_investment` — đầu tư chứng khoán**
Ví dụ: "vay để mua thêm cổ phiếu margin", "góp vốn quỹ đầu tư". Không cấm nhưng rủi ro biến
động cao hơn mục đích tiêu dùng thông thường → cần cấp có thẩm quyền xét riêng, agent không
tự kết luận "hợp lệ" và dừng ở đó.

**`debt_refinance` — đảo nợ/tái cấp vốn khoản vay khác**
Ví dụ: "vay để trả khoản vay bên ngân hàng khác đang lãi cao", "gộp nợ nhiều nơi thành một
khoản". Chỉ xét khi đáp ứng điều kiện tái cơ cấu — xem [[co-cau-no]]. Đảo nợ không đơn thuần
là "vay hộ trả nợ cũ", nó phải đi qua đúng quy trình thẩm định lại khả năng trả, không được
xử như một khoản vay mới độc lập.

**`business_expansion` — mở rộng sản xuất kinh doanh**
Ví dụ: "vay mở rộng xưởng cơ khí", "vay mua thêm dây chuyền sản xuất". Cần phương án kinh
doanh cụ thể kèm theo — hồ sơ nêu mục đích này mà không có phương án đi kèm thì chưa đủ điều
kiện xét, không phải đương nhiên "hợp lệ vì không bị cấm".

## Luật làm việc
Agent tra `purpose_code` bằng tool `legal_check_compliance`, KHÔNG tự nhớ danh mục hay tự
suy loại mục đích từ lời khách nói chung chung. `banned` → từ chối thẳng kèm căn cứ;
`conditional` → nêu rõ điều kiện cần đáp ứng, không tự quyết duyệt hay từ chối — đó là việc
của cấp thẩm quyền xét riêng.
