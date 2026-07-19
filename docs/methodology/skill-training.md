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
cùng cấu trúc tối ưu với train một model ML (weights × optimizer × nguồn tín hiệu), chỉ
khác chất liệu: trọng số ở đây là CHỮ. Cùng cấu trúc nên cùng bệnh di truyền (overfit,
reward-hacking, label-noise…) — và cùng thuốc, đổi tên biến (§8).

## §2. EPOCH-0 — khởi tạo từ phiên làm thật, KHÔNG dựng mù

**Định kiến:** đọc đề xong là ngồi viết SKILL v0 + danh sách tool.

**Cơ chế thật:** skill và toolpack đoán từ đề luôn thiếu đúng chỗ đau nhất — tool-gap chỉ lộ
khi có người thật sự LÀM việc đó. Vòng khởi tạo đúng là một **walkthrough trong phiên**:

1. Người hỏi agent từng câu nghiệp vụ thật (dễ → khó); agent BẮT BUỘC trả lời bằng gọi tool
   thật — cấm trả lời chay từ trí nhớ.
2. Agent bí vì thiếu tool/field → dựng/sửa tool ngay → hỏi lại câu đó. Tool-gap chết ở
   scaffold thay vì ở epoch thứ 3.
3. Tốt nghiệp scaffold khi agent trả lời đúng trọn bộ câu cơ bản, người verify tận mắt với
   ground-truth — chạy tay trọn một vòng trước khi đốt epoch nào.
4. **Chưng cất chính phiên đó thành SKILL v0** (luật + flow + chữ ký tool vừa dùng thật);
   bộ câu walkthrough thành các đề train đầu tiên — ground-truth đã verify sẵn.

## §3. Vòng epoch — gate, hội tụ, sổ ngoại lệ

```
đề (giọng người dùng thật: cụt, mơ hồ, có bẫy) → thí sinh FRESH × N (mỗi con một đề,
không con nào thấy bài nhau) → chấm nhiều tầng (§4) → phỏng vấn ngược đúng con vừa thi
(§7) → gom defect thành LÔ → sửa SKILL/tool, mỗi thay đổi trỏ về defect thật → GATE →
đạt thì thành version mới, không thì giữ bản cũ → lặp tới hội tụ
```

- **Gate strict: bản mới phải HƠN bản cũ** trên cùng bộ đề, và không thụt lùi trên đề từng
  pass (chống quên-thảm-hoạ: sửa luật mới đè gãy luật cũ). Tỷ lệ đáng kể bản sửa bị gate
  từ chối là gate đang làm việc, không phải vòng hỏng. Lệch nhỏ trên mẫu nhỏ = nhiễu →
  giữ bản cũ, đừng nhận bản mới vì hơn 0.01.
- **Sửa theo LÔ defect cỡ vừa** — đây là learning-rate của vòng: sửa cả file một lần thì
  không biết thay đổi nào có tác dụng; vá từng câu fail thì học vẹt, skill thành mì rối.
  Mỗi luật trong SKILL trỏ về defect thật kèm ngày — luật không có gốc là luật sẽ mâu thuẫn
  luật khác mà không ai dám xoá.
- **Bộ đề chia ba**: train (được săn điểm yếu có chủ đích) / selection / **test-khoá** —
  không bao giờ lộ cho bên sửa skill. Pass-rate chỉ đọc trên bộ giữ đúng phân bố người dùng
  thật: đọc điểm trên bộ săn-pain là tự dọa mình, trên bộ đề-dễ là tự ru mình.
- **Hội tụ đếm theo VERSION, không theo chuỗi lịch chạy**: đạt khi ≥2 lượt đề fresh pass
  với CÙNG version skill + 0 trap fail + không regress; mọi ca fail còn lại đã nằm trong
  sổ ngoại lệ. Đếm theo "chuỗi liên tiếp" là phạt oan skill vì lịch chạy.
- **Không ép 100%.** Ca dị thật (đề hai nghĩa, hành vi đúng còn tranh cãi) vào **sổ ngoại
  lệ có người ký + điều kiện xét lại** — ép fit ca dị là phá các ca lành (overfit kinh
  điển). Sổ phình lên nghĩa là đề hoặc thước đang sai, không phải thế giới nhiều ca dị.

## §4. Chấm — thang nhiều tầng, và ÁN ĐIỂM khi thước cãi nhau

**Thang chấm, vắt kiệt máy trước khi đến người:** tầng 1 = code deterministic (đối chiếu
số với tool-log, regex có đích, format — không bịa được, rẻ vô hạn) · tầng 2 = LLM chấm
rubric có ranh rõ, bắt buộc verify bằng gọi tool thật · tầng 3 = người, cho phần taste
thật (giọng, độ khéo) — nhận nó là cặn, đừng giả vờ nén được ("chấm độ chân thành 1-10"
là Goodhart sớm). **Điểm = min các tầng.**

**Án điểm — quy trình khi hai tầng cãi nhau to (hoặc thí sinh "làm đúng mà fail"):**
1. **Đóng băng cả dây chuyền** — điểm nghi oan không được chảy vào vòng sửa: gradient
   nhiễm độc thì mọi epoch sau xây trên nền sai.
2. **Niêm phong hiện trường**: transcript nguyên văn + tool-log + trạng thái data. KHÔNG
   "chạy lại cho chắc" trước khi đọc hiện vật — chạy lại là xoá hiện trường.
3. **Mọi bên là nghi phạm** — thí sinh, cả hai giám khảo, và chính cái thước. Điều tra
   viên là NGƯỜI với công cụ duy nhất không biết nói dối: truy vấn thẳng ground-truth.
   Không nhờ LLM thứ ba phân xử — thêm LLM là thêm một nghi phạm.
4. **Kết án → sửa đúng tầng → CHẤM LẠI mọi rollout dính án** + thêm regression test.

**Cây chẩn đoán tầng** (kẹt/điểm lạ → sửa TẦNG NÀO — thứ tự nghi NGƯỢC bản năng, vì bản
năng luôn đổ cho skill là thứ dễ sửa nhất):
- (0) Việc này có nên bắt AGENT làm không? Việc deterministic-ở-quy-mô (lặp, đếm, gửi
  hàng loạt) bắt agent loop là đặt sai chỗ → đẩy về tool/server, cày skill vô ích.
- (1) Hai tầng chấm cãi nhau → án điểm; một giám khảo đang sai, không phải thí sinh.
- (2) Cả batch cùng vấp một chỗ (param mò, gọi sai tên) → tầng TOOL — sửa 1 phát diệt cả
  lớp; sửa skill từng con là vá triệu chứng.
- (3) Thí sinh làm đúng nghiệp vụ mà bị chấm fail → tầng LOSS/thước — người hiệu chỉnh CÓ
  GHI CHÚ ngày + ca gây sửa; bên sửa-skill không được đụng thước.
- (4) Điểm giảm dần dù bản sửa được nhận đều → HARNESS — tín hiệu không chảy (bản mới
  không đến được thí sinh, state dính giữa các lượt).
- (5) Fail tụ vào một loại đề, hành vi sai thật, ≥2 nhân chứng cùng kiểu → đúng đất của
  SKILL — cho vòng chạy bình thường.
Mỗi nghi án kết bằng MỘT hành động kiểm rẻ (curl ground-truth, đọc 2 transcript cùng lỗi)
trước khi cho sửa — chẩn đoán không kiểm chứng = đoán.

## §5. Loss không có sẵn — KHAI QUẬT rồi ĐÀM PHÁN

**Định kiến:** cứ cho "AI chấm điểm 1-10" là có loss để train.

**Cơ chế thật:** "thế nào là ĐÚNG" của một nghiệp vụ không nằm trong training data của
model nào. Nó nằm ở bốn mỏ đều không tự phát biểu — mỗi mỏ một kỹ thuật đào:
- **Data thật hôm nay** → MỞ ra xem tận mắt (field nào null, phân bố lệch gì, entity trùng
  tên) — đừng tin mô tả.
- **Tool nào gọi được thật** → GỌI THỬ từng cái, đọc error thật — đừng tin docs.
- **Luật riêng của business** → hỏi CASE, không hỏi lý thuyết; rình chữ "thường thì… trừ
  khi" — NGOẠI LỆ là quặng đắt nhất. (Người cũng nịnh như model: hỏi mớm sẽ được gật —
  đưa hai bản cho họ CHÊ một, thay vì hỏi "bản này tốt không".)
- **Điều tuyệt đối không được làm** → mỏ duy nhất hỏi thẳng được.

Khai quật xong phải **nén thành check máy chạy được** — ground-truth không được tìm thấy,
nó được *chế tạo*: một phán xét của người trả giá một lần rồi đông cứng thành check chạy
vô hạn. Hai loại check đáng giá nhất: **số nào cũng truy về tool-log** (không truy được là
bịa, phạt thẳng) và **trap = làm-ẩu-thì-fail** (ca vi phạm điều kiện cứng phải bị TỪ CHỐI,
hành động thiếu phê duyệt phải BỊ CHẶN — chỉ đường làm đúng mới pass, đường tắt rớt; câu
mà làm ẩu cũng pass là câu chết, không phân loại được gì).

**Loss là hợp đồng hai bên đàm phán, không phải văn bản một người viết:** người giữ NỘI
DUNG (tốt là gì, vì sao — verdict phải kèm lý do, verdict suông là máy học vẹt) · máy giữ
HÌNH THỨC KIỂM (phát biểu này nén xuống tầng nào, check viết sao) và có nghĩa vụ PHẢN BIỆN
("luật này như phát biểu là không kiểm được", "mâu thuẫn ca hôm qua — cho tôi ca phân
biệt"). Máy chỉ gật đầu chép là thư ký — loss sẽ đầy lỗ. Và máy tự sửa thước của chính nó
= Goodhart: hội tụ nhanh về đúng cái sai.

**Ngưỡng điểm có ba nghĩa khác nhau — tách, đừng trộn thành một số:**
1. Ranh an toàn tuyệt đối (trap/compliance/số-từ-tool): nhị phân, sai một là fail, không
   thương lượng.
2. Ngưỡng chất lượng mềm: mốc do người-giữ-nghiệp-vụ định. Trước khi chấm thí sinh, **chấm
   giám khảo**: chạy thước trên 5-10 đáp án thật của người giỏi — người giỏi mà fail thước
   thì THƯỚC sai, không phải người sai.
3. Ngưỡng dừng kinh tế: điểm lab thứ 91 không có giá trị tự thân — ship ở mốc chấp nhận
   được rồi cải thiện bằng dữ liệu thật.

## §6. SEED — làm giàu quanh cốt thật, sinh theo loss

**Định kiến:** bảo AI "tạo 500 hồ sơ giống thật" là có data train.

**Cơ chế thật:** sinh tự do thì data mượt — không null, không trùng tên, không mâu thuẫn —
tức là không có gì để train honesty; và trap không có ca kích hoạt thì luật tương ứng không
bao giờ được train. Luật sinh:
- **Seed = làm giàu quanh cốt data thật, không phải nguồn** — gen phủ đúng vùng data thật
  THIẾU cho việc train (trap chưa có ca kích hoạt, pathology hiếm). Chưa có data thật nào
  (bootstrap từ 0) → lấy số nghề ghi trong đề/brief + hỏi chuyên gia bằng CASE, chấp nhận
  sai-có-chủ-đích, và có NGHĨA VỤ CÓ LỊCH neo về thật khi data thật xuất hiện.
- **Ba lớp sinh**: (1) SEED-SPEC trước khi sinh — marginals + tương quan chéo bảng + quota
  pathology + danh sách trap-coverage, viết dạng validator compile được; (2) agent sinh
  THAM SỐ + code generator đẻ row (chống mode-collapse, tái lập được) — agent chỉ viết tay
  phần văn bản tự do; (3) nghiệm thu hai tầng: validator code chấm phân bố/FK/thời gian →
  một con đọc 10 hồ sơ ngẫu nhiên smell-test "có mùi thật không".
- **Quota pathology tường minh** (x% null, y% trùng tên, z ca mâu thuẫn — người duyệt) ·
  đuôi dài + rác thật (viết tắt, không dấu) · mỗi trap ≥k ca kích hoạt · mọi record sinh
  tag được là synthetic — trộn được lúc train, tách được lúc đo, rút được khi có thật.
- **Sổ đo thiên ca thật** — pass-rate đọc trên data gen là hết giá trị dự báo.

## §7. PHỎNG VẤN NGƯỢC — và 7 cơ chế LLM phải thuộc khi hỏi

Thẩm quyền của "người dùng tool" đến từ VIỆC DÙNG: đừng hỏi agent trước khi nó làm đề
(khai chay = pattern-match + gật theo người hỏi); mọi câu hỏi đặt SAU khi thi xong, hỏi
**đúng con vừa thi** — nhân chứng có trải nghiệm, hơn hẳn con mới đọc transcript (suy diễn
≠ trải nghiệm). Rollout đo phải SẠCH: không hint, không nói bị test, không chọc giữa chừng
— chọc rồi thì thành rollout thăm dò, không tính điểm, cửa một chiều.

**Ngưỡng tin lời khai:** ≥2 con độc lập không-ai-mớm cùng khai + transcript có vết loay
hoay thật → TIN, build fix · 1 con khai có vết → NGHI, probe hành vi một phát (thả con
fresh vào đề thiết-kế-đâm-đúng-chỗ-nghi rồi XEM NÓ LÀM — không nghe nó nói) · khai chay
không vết → ghi sổ giả thuyết · khai khi bị mớm → loại.

**7 cơ chế LLM chi phối mọi thiết kế prompt/skill/câu hỏi:**
| Cơ chế | Hệ quả thiết kế |
|---|---|
| Attention chia tỷ lệ, không cộng dồn | 1 con = 1 đề = 1 mẫu; N việc nhét 1 context là N việc nông |
| Vị trí quyết định trọng lượng | luật sống còn đặt ĐẦU skill; skill dài thì nhắc lại điểm chết người ở cuối; đừng chôn luật mới vào giữa |
| Nịnh người hỏi (sycophancy) | hỏi trải nghiệm, đừng hỏi kết luận hộ; độ tin = hội tụ giữa N con không ai mớm |
| Dồn N câu / 1 message = chia attention | dồn chỉ để quét thô; câu quan trọng hỏi TỪNG câu, đọc trả lời rồi mới hỏi tiếp |
| Ví dụ là KHUÔN, không phải minh hoạ | model copy HÌNH DẠNG ví dụ mạnh hơn mọi mô tả — ví dụ phải đúng nguyên văn dạng muốn nhận |
| Giá trị cụ thể bị echo như data | luật/learning không chứa số thật, tên thật — dùng placeholder |
| Role hội tụ attention | mở mọi prompt bằng vai rõ; scorer phải ADVERSARIAL, không "hãy kiểm tra" trung tính |

## §8. Bệnh học — mọi bệnh ML có bản dịch agent

Gặp hiện tượng lạ trong vòng train, hỏi *"trong ML nó tên gì?"* — tra từ điển luôn rẻ hơn
phát minh giải thích mới. Thuốc ưu tiên 3 nấc: **cấu trúc** (làm bệnh không thể phát —
không có field `success` để bịa "đã gửi") → **hook máy** (bệnh có vết cơ học — check tự
động đối chiếu tool-log) → **người** (bệnh chỉ còn vết ngữ nghĩa).

| Bệnh ML | Dạng agent | Thuốc |
|---|---|---|
| Overfit | skill học tủ — đổi vỏ đề là gãy | held-out thiêng liêng · đề same-concept-khác-vỏ |
| 100%-pass-ngay | đề dễ hoặc lộ đề | NGỜ EVAL TRƯỚC KHI MỪNG — thêm distinguishing-case |
| Label noise | giám khảo chấm oan → gradient nhiễm độc | án điểm + chấm lại rollout dính án |
| Reward hacking | né việc cho an toàn, khai "đã làm" không khớp log | scorer verify bằng tool thật · deflection-khi-trả-lời-được = fail |
| Sim2real | pass trên seed, fail hiện trường | hai sổ train/đo · re-certify trên data thật |
| Catastrophic forgetting | luật mới đè gãy luật cũ | gate chấm không-regress · sửa có anchor |
| Noisy gradient | kết luận từ 1 rollout / 1 lời khai | N con + ngưỡng tin hội tụ |
| Prompt spaghetti (bệnh riêng chất liệu chữ) | vá nhanh nhiều vòng, skill dài ra mà điểm không lên | mỗi luật có gốc defect + ngày · tỉa định kỳ |

Hai chỗ KHÔNG dịch nguyên văn từ ML: (1) **plateau đảo thứ tự xử lý** — ML kẹt thì
early-stop; agent kẹt thì tra cây chẩn đoán TRƯỚC (đa số ca kẹt là bug thước/harness, không
phải hết khả năng học), early-stop là phương án cuối; (2) **early-stop có vai ML không
có** — skill đạt target mà cứ ép sửa là tự phá weights bằng chính optimizer (sửa thừa đè
luật cũ + phình skill loãng attention).

## §9. DISTILL + CERTIFY — trí khôn phải nằm trong CHỮ

- **Skill trained = reasoning đã nén**: suy luận trả giá đắt trong vòng train đông cứng
  thành luật + ví dụ khuôn + chữ ký tool — model rẻ thừa kế qua chữ thay vì tự suy lại.
  Trả giá một lần (train), áp vô hạn (production). Vì thế **thí sinh khi train = model
  ĐÍCH của production** — train bằng model xịn rồi ship model rẻ mà không đo lại là trí
  khôn còn nằm trong model, chưa vào chữ.
- **Distill không phải viết ngắn** — là viết ĐỦ để model đích không phải đoán. Skill phình
  vô ích là thuế context; skill thiếu là bắt model đoán — cả hai đều trả giá bằng lỗi.
- **Runtime tách đôi**: TRAIN chạy ở môi trường có mắt người nhìn live (nửa số bug harness
  chỉ lộ khi nhìn) + spawn rẻ + phỏng vấn được; CERTIFY chạy headless CỐ TÌNH MÙ giống
  production — bắt lớp lỗi trình-bày-context mà phiên tương tác che mất.
- **Kết quả certify = bộ HỒ SƠ**: pass-rate trên bộ đề đúng phân bố + sổ ngoại lệ có ký +
  version skill + định danh bộ đề. Thiếu mảnh nào là báo cáo thiếu. Bộ test-khoá đã dùng
  để ra quyết định = CHÁY — đúc bộ mới cùng độ phủ, khác vỏ.
- **Bản certified không được vá tay.** Sửa một chữ ngoài vòng train là mất hiệu lực nghiệm
  thu — hệ tiêu thụ kiểm bằng so sánh máy (diff/AST với bản gốc), không bằng lời hứa.
  Thẩm quyền của skill/tool càng cao, yêu cầu nguồn-sự-thật của nó càng khắt khe.

## §10. PRODUCTION — vòng train không kết thúc, nó đổi nguồn gradient

Lab lấy tín hiệu từ đề tự viết; production lấy từ **thất bại thật + outcome thật**. Thiết
kế bắt buộc: **instrument từ ngày MỘT** (câu hỏi nguyên văn — chính là phân bố thật cho sổ
đo · tool-call + kết quả · tỷ lệ output bị người sửa trước khi dùng · version skill đang
chạy) — audit log của compliance và instrument của training là MỘT hạ tầng hai vai. Mỗi ca
người dùng chê/sửa nặng = ứng viên đề mới, người duyệt rồi vào sổ train; đủ lô → epoch mới
→ re-certify → release version mới. Outcome là tín hiệu CÂM — không tự phân biệt "phục vụ
thật" với "chiêu trò" — phải người diễn dịch. Bỏ ống dẫn này = skill đông cứng trong thế
giới đang trôi.

## §11. Trade-off khai thật

- **Đắt hơn viết prompt một lần** — nhiều epoch × nhiều rollout mỗi skill. Đổi lại: biết
  skill đứng ở đâu bằng số, và bản kém không bao giờ đè bản tốt.
- **Certify trên data sinh = tạm ứng** (sim2real) — lời giải là shadow-mode khi triển khai:
  chạy song song người thật, đo độ khớp trên phân bố thật trước khi cấp thẩm quyền.
- **Nghiệm thu có hạn dùng** — nghiệp vụ đổi, phân bố trôi, model đổi thế hệ → chu kỳ
  re-certify như chính LLM có release.
- **Máy chạy vòng rẻ đi không làm rẻ việc BIẾT-ĐO-GÌ** — loss định sai thì vòng hội tụ
  nhanh về đúng cái sai. Phần khó nhất và ít khấu hao nhất của nghề nằm ở đó.

---

## Repo này đã ứng dụng thế nào (overview — mỗi dòng tự kiểm được)

Vòng train chạy tại LAB (môi trường huấn luyện riêng); repo này là **hệ tiêu thụ bản
certified** và giữ trọn các kỷ luật ở trên:

| Nguyên lý (§) | Trong repo này |
|---|---|
| Skill = trọng số đã distill (§1, §9) | `roles/<role>/SKILL.md` per chuyên gia — luật hành nghề + khối "SÁCH TRA CỨU" append nguyên văn từ bản certify (D-65a) |
| Bản certified cấm vá tay, kiểm bằng máy (§9) | `backend/tests/test_legal_port_t72.py` (đối chiếu bản port ↔ certify) + check AST-identical per-function cho đợt port Products/Ops; sổ D-55/D-58 trong `DECISIONS.md` |
| Trap làm-ẩu-thì-fail chạy được bằng pytest (§5) | `backend/tests/test_retrieval_seed_t122.py` — bẫy văn-bản-hết-hiệu-lực bắt bằng cạnh đồ thị, trần dư nợ NHÓM khách liên quan |
| Seed pathology có chủ đích (§6) | `deploy/seed/` — hồ sơ null/trùng tên/nợ xấu/ca vượt trần + wiki 82 trang chính sách làm nguồn retrieval |
| Không port bản trôi (§9) | D-63: hoãn port retrieval tới khi LAB khoá bản certified — vết quyết định có ngày trong `DECISIONS.md` |
| Shadow-mode = re-certify trên phân bố thật (§11) | Lộ trình pilot Pha 0 tại [`../business-case.md`](../business-case.md) §3 |
