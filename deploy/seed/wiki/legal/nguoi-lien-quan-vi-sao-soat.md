---
id: nguoi-lien-quan-vi-sao-soat
role: legal
title: Người có liên quan và trần nhóm — hai bậc định nghĩa, vì sao phải soát
topic: related_party
tags: quan-he,tuan-thu,trần-nhom
legal_basis: Luật TCTD Điều 4 (gia-thuyet-lab)
effective_from: 2025-01-01
status: active
---

Trang [[nhom-khach-lien-quan]] nêu cách TÍNH dư nợ nhóm. Trang này diễn giải HAI BẬC quan
hệ và LÝ DO bắt buộc phải soát, không phải thủ tục hình thức.

## Hai bậc — vì sao dừng ở bậc 2, không đi xa hơn
- **Bậc 1 (trực tiếp)**: sở hữu ≥20% vốn điều lệ, điều hành (chủ tịch/người đại diện pháp
  luật), bảo lãnh, quan hệ gia đình trực hệ (vợ/chồng, cha mẹ, con).
- **Bậc 2 (gián tiếp qua bậc 1)**: ví dụ cá nhân → sở hữu công ty A (bậc 1) → công ty A sở
  hữu ≥20% công ty B (bậc 1 của A, tức bậc 2 của cá nhân ban đầu). Dư nợ nhóm CỘNG DỒN đến
  hết bậc 2.

Vì sao không đi bậc 3 trở đi: định nghĩa "người có liên quan" theo Luật TCTD dừng ở phạm vi
kiểm soát/ảnh hưởng thực chất — bậc 3 trở đi mối liên hệ sở hữu/kiểm soát đã quá loãng để
coi là RỦI RO TẬP TRUNG thực sự (sở hữu 20% của 20% của 20% không còn là kiểm soát đáng kể).
Đây là ranh có chủ đích, không phải giới hạn kỹ thuật của tool — thay đổi độ sâu phải sửa
CẢ code lẫn định nghĩa ở [[nhom-khach-lien-quan]] đồng thời, không lệch giữa hai nơi.

## Vì sao PHẢI soát — rủi ro tập trung ẩn
Bài toán không phải "khách này có trả được khoản NÀY không" (đó là DSCR/LTV từng khoản, việc
Credit) mà là "NGÂN HÀNG có đang gánh quá nhiều rủi ro vào MỘT nhóm lợi ích thực chất không,
dù mỗi khoản đứng tên khác nhau". Một tập đoàn có thể chia nhỏ nhu cầu vốn thành nhiều pháp
nhân/nhiều khoản vay đứng tên khác nhau, mỗi khoản riêng lẻ đều dưới trần — nhưng nếu tất cả
đều bị kiểm soát bởi cùng một cá nhân/nhóm, rủi ro vỡ nợ của cả nhóm là LIÊN ĐỚI (một mắt xích
sụp thì cả nhóm khó trả). Trần đơn (15%) không nhìn thấy rủi ro này — CHỈ trần nhóm (25%,
qua đi cạnh quan hệ) mới bắt được.

## Vì sao không được tra phẳng từng khách
Nếu chỉ kiểm tra "khoản này, khách này có vượt trần đơn không" mà bỏ qua bước đi quan hệ, một
khoản có thể ĐẠT trần đơn nhưng khiến CẢ NHÓM vượt trần 25% — về bản chất đây chính là tình
huống ngân hàng đang vi phạm giới hạn cấp tín dụng dù trên giấy tờ không khoản nào "quá to".
Đây là lý do luật cứng #3 ở [[tran-cho-vay]] bắt buộc gọi `legal_related_exposure` trước khi
kết luận với bất kỳ khoản vay lớn nào, không được coi kiểm tra trần đơn là đã đủ.

## Thực hành
Bất kỳ khoản vay lớn nào (đặc biệt doanh nghiệp) → gọi `legal_related_exposure(owner_id)`
TRƯỚC khi kết luận, dù hồ sơ trông "sạch" ở mọi mặt khác. Kết luận phải nêu rõ ĐÃ SOÁT
trần nhóm, không chỉ trần đơn — thiếu câu này coi như thẩm định chưa đầy đủ theo luật cứng
của SKILL.
