# SKILL TRAINING — huấn luyện chuyên gia AI như train một model

> Phương pháp luận tổng quát — áp cho mọi agent nghiệp vụ, không riêng hệ nào.
> Khuôn mỗi mục: *định kiến → cơ chế thật → lựa chọn → trade-off khai thật.*

## §1. Vì sao phải TRAIN — không phải "viết prompt hay là xong"

**Định kiến:** chuyên gia AI = một system prompt viết khéo; chưa tốt thì dặn thêm vài câu.

**Cơ chế thật:** model đông cứng — không học gì giữa các lượt. Mỗi lượt agent chạy là một
"thí sinh mới tinh" bước vào phòng thi **đề mở**: được mang theo đúng hai thứ — cuốn sách
(SKILL) và đồ nghề (tool). Hệ quả bất di dịch: **cải thiện agent = sửa sách + sửa đồ nghề,
không phải kèm cặp từng lượt chat.** Dặn thêm vào lượt chat là mẫu nhiễm — không tái lập
được ở lượt sau.

Sửa theo cảm giác thì không biết sửa đỡ hay phá. Nên SKILL và tool được đối xử như **trọng
số của một vòng huấn luyện**: có version, có bộ đề, có điểm, có gate chặn bản kém hơn —
cùng cấu trúc với train một model ML, chỉ khác chất liệu: trọng số ở đây là CHỮ.

## §2. Vòng huấn luyện

```
đề (giọng người dùng thật: cụt, mơ hồ, có bẫy) → thí sinh FRESH × N (mỗi con một đề,
không con nào thấy bài nhau) → chấm 2 tầng → phỏng vấn ngược đúng con vừa thi → gom
defect thành LÔ → sửa SKILL/tool, mỗi thay đổi trỏ về defect thật → GATE → đạt thì
thành version mới, không thì giữ bản cũ → lặp tới hội tụ
```

Các luật giữ cho vòng không tự lừa mình:

- **Chấm 2 tầng, điểm = min.** Tầng 1 là code deterministic (đối chiếu số với tool-log —
  không bịa được, rẻ vô hạn); tầng 2 là LLM chấm rubric, bắt buộc verify bằng gọi tool
  thật. Hai tầng cãi nhau to → **án điểm**: đóng băng dây chuyền, NGƯỜI truy thẳng
  ground-truth rồi mới xử — thí sinh, giám khảo và cả thước đo đều là nghi phạm; chỉ
  tool-log là thật. Điểm nghi oan không được chảy vào vòng sửa — gradient nhiễm độc thì
  mọi epoch sau xây trên nền sai.
- **Gate strict: bản mới phải HƠN bản cũ** trên cùng bộ đề, và không thụt lùi trên đề từng
  pass. Tỷ lệ đáng kể bản sửa bị gate từ chối là gate đang làm việc, không phải vòng hỏng.
  Lệch nhỏ trên mẫu nhỏ = nhiễu → giữ bản cũ, đừng nhận bản mới vì hơn 0.01.
- **Bộ đề chia ba**: train (được săn điểm yếu có chủ đích) / selection / **test-khoá** —
  không bao giờ lộ cho bên sửa skill. Pass-rate chỉ đọc trên bộ giữ đúng phân bố người
  dùng thật; đọc điểm trên bộ săn-pain là tự dọa mình, trên bộ đề-dễ là tự ru mình.
- **Sửa theo LÔ defect, không vá từng câu fail** — vá từng câu là học vẹt; skill thành mì
  rối, luật mâu thuẫn nhau không ai biết vì sao tồn tại. Mỗi luật trong SKILL phải trỏ về
  defect thật kèm ngày.
- **Không ép 100%.** Ca dị thật (đề hai nghĩa, hành vi đúng còn tranh cãi) vào **sổ ngoại
  lệ có người ký + điều kiện xét lại** — ép fit ca dị là phá các ca lành (overfit kinh
  điển). Sổ phình lên nghĩa là đề hoặc thước đang sai, không phải thế giới nhiều ca dị.

## §3. Loss không có sẵn — phải KHAI QUẬT

**Định kiến:** cứ cho "AI chấm điểm 1-10" là có loss để train.

**Cơ chế thật:** "thế nào là ĐÚNG" của một nghiệp vụ không nằm trong training data của
model nào. Nó nằm ở bốn chỗ đều không tự phát biểu: **dữ liệu thật hôm nay** (field nào
null, bản ghi trống nghĩa là gì) · **tool nào gọi được thật** · **luật riêng của business**
(ngoại lệ "thường thì… trừ khi" — ngoại lệ là quặng đắt nhất) · **điều tuyệt đối không
được làm**. Khai quật xong phải **nén thành check máy chạy được** — ground-truth không được
tìm thấy, nó được *chế tạo*: một phán xét của người trả giá một lần rồi đông cứng thành
check chạy vô hạn.

Hai loại check đáng giá nhất:
- **Số nào cũng truy về tool-log** — không truy được là bịa, phạt thẳng.
- **Trap = làm-ẩu-thì-fail**: ca vi phạm điều kiện cứng phải bị TỪ CHỐI, hành động thiếu
  phê duyệt phải BỊ CHẶN, dữ liệu mâu thuẫn phải được TÍNH LẠI — chỉ đường làm đúng mới
  pass, đường tắt rớt. Câu mà làm ẩu cũng pass là câu chết, không phân loại được gì.

Phân vai không đổi: **người giữ nội dung** ("tốt" là gì, vì sao — verdict phải kèm lý do,
verdict suông là máy học vẹt) · **máy giữ hình thức kiểm** (nén phát biểu thành check).
Máy tự sửa thước của chính nó = Goodhart — hội tụ nhanh về đúng cái sai.

Data huấn luyện cũng theo loss: seed sinh bằng generator có chủ đích **bơm pathology**
(null, trùng tên, hồ sơ mâu thuẫn, ca sát ngưỡng) — mỗi trap phải có ca kích hoạt trong
data; luật không có ca kích hoạt là luật không bao giờ được train.

## §4. Certify — nghiệm thu là phép đo, không phải nghi lễ

Skill hội tụ chưa phải là xong. Nó phải qua nghiệm thu:

- **Chạy test-khoá ở môi trường mù** (headless, giống production) — bắt lớp lỗi chỉ lộ khi
  cách trình bày context đổi; pass trong phiên tương tác không suy ra pass ở backend.
- **Kết quả là bộ HỒ SƠ, không phải một con số**: pass-rate trên bộ đề đúng phân bố + sổ
  ngoại lệ có ký + version skill + định danh bộ đề. Thiếu mảnh nào là báo cáo thiếu.
- **Bộ test-khoá đã dùng để ra quyết định = CHÁY** — lần sau phải đúc bộ mới cùng độ phủ,
  khác vỏ. Đề lộ rồi thì điểm trên nó là đo ảo.
- **Bản certified không được vá tay.** Sửa một chữ ngoài vòng train là mất hiệu lực nghiệm
  thu — hệ tiêu thụ kiểm điều này bằng so sánh máy (diff/AST với bản gốc), không bằng lời
  hứa. Thẩm quyền của skill/tool càng cao, yêu cầu về nguồn-sự-thật của nó càng khắt khe.

## §5. Trade-off khai thật

- **Đắt hơn viết prompt một lần** — mỗi skill tốn nhiều epoch × nhiều rollout. Đổi lại:
  biết skill đứng ở đâu bằng số, và bản kém không bao giờ đè bản tốt.
- **Certify trên data sinh = tạm ứng**, chưa phải năng lực chứng minh trên người dùng thật
  — khoảng cách phân bố seed ↔ thật là có thật (sim2real). Lời giải: giai đoạn shadow-mode
  khi triển khai — hệ chạy song song người thật, đo độ khớp trên phân bố thật trước khi
  được cấp thẩm quyền; certify trên seed chỉ là điểm khởi tạo.
- **Nghiệm thu có hạn dùng** — nghiệp vụ đổi, phân bố trôi, model đổi thế hệ → chu kỳ
  re-certify như chính LLM có release. Không có "certify một lần dùng mãi".
