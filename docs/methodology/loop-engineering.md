# LOOP ENGINEERING — để đội AI build phần mềm mà vẫn tin được

> Phương pháp luận tổng quát — cách tổ chức một đội AI agent build hệ thống production,
> với con người giữ đúng vai không máy nào thay được. Khuôn mỗi mục: *định kiến → cơ chế
> thật → lựa chọn → trade-off khai thật.*

## §1. Vì sao dám để AI build — và vì sao vẫn tin được

**Định kiến:** code AI viết = vibe coding, chạy được hôm nay gãy ngày mai, không ai dám
đem vận hành thật.

**Cơ chế thật:** chi phí MỘT LẦN THỬ phần mềm đã sụp — từ hàng-tuần-công xuống vài phút.
Khi thử ba lần rẻ hơn ngồi nghĩ cho đúng một lần, câu hỏi đổi hẳn: không phải "AI viết code
đúng không?" mà là **"vòng nào ÉP code phải đúng trước khi được nhận?"**. Sai không phải sự
cố — sai là một bước của vòng `BUILD → SAI → UPDATE → LOOP`; giấu sai / tự chấm pass mới là
sự cố. Toàn bộ phương pháp dưới đây chỉ làm một việc: biến "tin AI" thành **"tin cái PHANH
đứng sau AI"**.

Nguyên lý gốc đằng sau mọi mảnh của quy trình: **agent build gần như miễn phí và nhanh hơn
người; đường găng duy nhất là những chỗ phải CHỜ NGƯỜI hoặc phải ĐOÁN.** Mọi thiết kế dưới
đây đều là một trong hai việc: dồn hết chờ-người về một điểm, hoặc triệt tiêu một chỗ đoán.

## §2. KICKOFF hai bước — máy scaffold, người chốt, rồi mới nổ máy

**Định kiến:** cứ mô tả ý tưởng rồi để AI vừa build vừa hỏi dần.

**Lựa chọn:** tách làm hai bước có ranh cứng:

- **Bước 1 — SCAFFOLD (máy, một lèo):** từ input người cấp (spec/mock/data mẫu), agent dựng
  trọn bộ khung: spec chuẩn hoá, luật chung của đội, playbook từng vai, backlog, sổ quyết
  định — rồi BÁO CÁO và DỪNG. Vắng người thì dừng vô hạn ở báo cáo. Ba luật khi điền chỗ
  trống: có default → lấy + ghi sổ; suy được từ spec → chọn phương án đảo-ngược-được + ghi
  sổ; phải người quyết (lệnh chạy, port, tài khoản) → đánh dấu BLOCKER tại chỗ rồi đi tiếp
  — **cấm điền giá trị tạm**, vì giá trị tạm sẽ bị vòng lặp dùng thầm như sự thật.
- **Bước 2 — DISCUSS-CHỐT (người):** người đọc kit + danh sách blocker, trả lời, chỉnh —
  và đi hết **resource checklist diệt human-block**: mock đã duyệt? design token trỏ đâu?
  data mẫu cho mọi màn? lệnh run/test? credential (env, không vào repo/chat)? deploy
  target? chính sách việc-không-đảo-được? nhịp người trả lời quyết định treo? — mỗi dòng
  chưa giải quyết là một lần vòng lặp ĐỨNG CHỜ trong tương lai, trả trước rẻ hơn trả giữa
  sprint. Người nói "chạy đi" thì vòng build mới bắt đầu — scaffold xong tự chạy là vi phạm.

Vì sao tách: máy làm phần rẻ (dựng file), người chỉ vào đúng chỗ cần người (quyết định).
Mọi khác biệt giữa các dự án nằm ở một nhúm quyết định (stack, auth, mức tự trị, build mới
hay port); phần còn lại của quy trình bất biến — nên scaffold được, và nên scaffold bằng máy.

## §3. SPEC là CONTRACT, viết ở thì hoàn thành

**Định kiến:** spec là danh sách việc cần làm.

**Cơ chế thật:** spec danh-sách-việc không audit được — "đã làm" không suy ra "đã đúng".
Spec đúng nghĩa mô tả hệ **như thể đã tồn tại**: hành vi, bề mặt API với envelope nguyên
văn từng field, ví dụ vào/ra, hành vi lỗi, và cả danh sách **KHÔNG-LÀM** chặn scope-creep
(agent thấy "cần cho scale/security" là muốn build thêm — danh sách cấm là phanh rẻ nhất).
Spec kiểu này chính là **chế tạo ground-truth cho builder**: mỗi mảnh việc có
điều-kiện-xong máy-kiểm-được (test pass, gọi API đúng shape, typecheck sạch) — agent tự
phân rã spec rộng thành mục tiêu con và tự biết lúc nào một mảnh "xanh". An toàn của
tự-phân-rã có điều kiện: từng mảnh checkable là CẦN nhưng chưa đủ — tập check phải phủ cả
KHỚP NỐI giữa các mảnh (integration test), và độ-phủ-của-check là thứ người duyệt.

**MỘT nguồn sự thật:** mỗi thông tin sống đúng một chỗ (spec ở spec, luật đội ở luật đội,
chi tiết task ở dispatch) — hai nguồn thì cãi nhau, mơ hồ thì agent bịa. Chỗ spec im lặng:
**dừng hỏi, hoặc chọn phương án đảo-ngược-được rồi ghi sổ quyết định** (*quyết gì — vì sao
— cách đổi*) để người đọc lại sau và có quyền lật. Cấm giả định lặng lẽ — giả định lặng lẽ
= bug lặng lẽ.

## §4. ĐỘI HÌNH — vai theo chức năng, dispatch là contract

Đội chia vai cố định: **architect** (chủ vòng sprint: kickoff, dispatch, review, gate —
và là NGƯỜI COMMIT DUY NHẤT) · các **implementer** theo mảng (server / UI — không ai đụng
mảng của người khác) · một **tester độc lập** · một **điều phối** (proxy của người: route
việc, không code, không đụng git). Vai định nghĩa theo CHỨC NĂNG, không theo con model —
cùng model đóng nhiều vai được, miễn mỗi phiên chỉ mang một vai.

- **Task LÀ spec — dispatch là hợp đồng thi hành**, không phải tin nhắn tóm tắt. Mỗi task
  đi kèm đủ mục: bối cảnh · scope IN/OUT · **Logic/Algorithm cho việc phi-CRUD** (architect
  thiết kế CÁCH LÀM — inputs → biến đổi từng bước → output → edge case → công thức/ngưỡng
  chính xác; implementer không tự chế logic, vì data trông-hợp-lý-nhưng-sai tốn cả sprint
  mới bắt) · defensive case BẮT BUỘC xử · exports (chữ ký cho tester dựng test trước) ·
  baseline số test (mỏ neo chống thụt lùi) · tiêu chí pass tường minh.
- **Plan là nháp 70-80% đúng** — trước mỗi sprint, architect đối chiếu plan với hiện trạng
  thật (spec đổi? code đã mọc gì?) và sửa plan TẠI CHỖ rồi mới dispatch. Không bao giờ
  dispatch từ plan ôi.
- **Review 4 bước, không pass trên diff:** xem diff → **mở file đọc TRỌN function đã đổi**,
  lần theo đường chạy vào→ra → đối chiếu mục tiêu sprint ("vấn đề được giải" chứ không phải
  "code có đổi") → săn lỗ hổng lân cận (endpoint anh em cùng bệnh?).
- **Báo cáo hoàn thành TRƯỚC khi nghỉ là luật không thương lượng** — format cố định: file
  đổi · test pass/fail so baseline · đã verify bằng gì · lệch gì so dispatch · blocker.
  Lỗi giữa chừng gửi STATUS, không im lặng — teammate im lặng là lead phải đi đọc
  transcript đoán, đắt hơn mọi báo cáo.
- **Gặp mơ hồ / tradeoff không hiển nhiên / nghi thiếu defensive case → BLOCKER đẩy lên**,
  một dòng + câu hỏi cụ thể. Không tự đoán.

## §5. VÒNG LẶP + GATE — người viết không bao giờ tự chấm

- **Author ≠ checker.** Người viết code tự chấm sẽ pass chính mình. Tester không nhận lời
  khai của implementer làm bằng chứng — tự chạy suite, tự gọi endpoint thật (payload thật,
  không mock), tự bấm UI bằng browser; fail trả feedback thi-hành-được (expected / actual /
  cách tái hiện) rồi vòng quay: implementer sửa → tester chấm lại → tới 100%. Cái không
  kiểm được (thiếu env, thiếu fixture) khai thẳng **UNVERIFIABLE** — không bao giờ
  default-xanh; đó chính là chỗ người vào spot-check.
- **Verify trước khi tuyên bố.** "Test pass" = chạy lệnh, dán output thật; "đã ghi DB" =
  query lại row; "script chạy" = chạy nó — đọc code không phải chạy code. Áp cho mọi vai,
  kể cả báo cáo của agent con: bên nhận spot-check với nguồn thật trước khi tin.
- **Gate máy-kiểm-được, 100% mới commit.** Nhiều lớp gate mỗi chu kỳ (bề mặt API: schema
  constraint, integration test cũ-mới, format response nhất quán · function: unit test hành
  vi quan sát được, edge case rỗng/None/max/malformed, error path fail-open-hay-closed nói
  rõ, không test tự-xác-nhận · chu kỳ: số test ≥ baseline, số liệu chạy lại độc lập, UI
  verify bằng mắt browser) — vì tiêu chí không đo được bằng máy là tiêu chí sẽ bị bỏ qua
  khi mệt. Gate fail = chặn commit, không thương lượng.
- **Test cũng bị soi**: suite cần distinguishing-case (case mà chỉ bản làm-đúng pass, đường
  tắt hợp-lý fail); 100% pass ngay từ lần đầu = nghi suite yếu trước khi mừng; check nhạy
  phải pass 3 lần liên tiếp mới tính.
- **Luật "tử" cưỡng chế bằng máy**: cấm xoá, cấm thao tác git phá huỷ — đặt ở deny cơ khí
  của harness, không phải chữ trong prompt. Luật prompt là xác suất; deny của máy là chắc
  chắn. Muốn bỏ file thì chuyển vào chỗ lưu trữ — chỉ người xoá thật.

## §6. NGƯỜI đứng ở đâu — và ước lượng phải đổi hệ quy chiếu

**Định kiến:** AI tự trị = người buông tay; hoặc ngược lại, người phải duyệt từng dòng.

**Lựa chọn:** người giữ đúng phần máy không tự lo được: **định nghĩa "tốt"** (spec, khẩu
vị, ranh giới) và **điểm rẽ không đảo được**. Cơ chế:
- Việc đảo-ngược-được → đội tự quyết + ghi sổ (**decide-and-log**), người đọc lại async và
  có quyền lật (human-wins). Người vắng mặt không làm đội đứng; quyết định treo gom một
  chỗ chờ người theo nhịp, không rải câu hỏi suốt sprint.
- Việc một-chiều (xoá thật, publish, chi tiền, đổi hạ tầng) → luôn về người, chặn bằng máy.
- Bất thường dai dẳng nhưng chấp nhận được → **sổ ngoại lệ có ký + điều kiện xét lại**,
  công khai trong sổ chu kỳ — thay vì ép fix. Sổ phình lên nghĩa là spec hoặc gate đang
  sai, không phải thế giới nhiều ngoại lệ.

**Ước lượng đổi hệ quy chiếu:** chi phí thật = **SPEC (giờ-người thảo luận) + VERIFY
(wall-clock vòng kiểm) + BUILD (≈ 0)**. Ước lượng "N ngày/tính năng" kiểu team người là
echo từ quá khứ — tốc độ cũ bị tái dùng như sự thật hiện hành. Lịch dự án thời agent-build
là: lịch các buổi người chốt spec/quyết định + wall-clock vòng verify + phụ thuộc ngoài.
Code biến mất khỏi phương trình.

## §7. Khi kết quả kiểm giở chứng: nghi cái THƯỚC trước khi nghi code

Fail hàng loạt không giải thích được, hai verdict mâu thuẫn, check mới đánh trượt code vốn
tin cậy → thứ tự nghi NGƯỢC bản năng: **(1) môi trường + chính cái check → (2) tool/hạ tầng
→ (3) code sản phẩm — cuối cùng.** Phép thử rẻ: chạy check đó trên code biết-chắc-đúng;
code tốt mà trượt nghĩa là CHECK sai — sửa check kèm ghi chú ngày, cấm nới test lặng lẽ.
Mỗi nghi án kết bằng một hành động kiểm RẺ (một lệnh curl, đọc hai transcript cùng lỗi,
chạy lại một ca bằng tay) trước khi cho sửa bất cứ gì — chẩn đoán không kiểm chứng = đoán.
Và vài lần chạy không phải thống kê: lệch nhỏ giữa vài run là nhiễu, không phải tín hiệu.

## §8. HOOK — điều hướng cơ khí quanh việc dùng tool

Hook (can thiệp của harness trước/sau mỗi tool-call) là rào chắn cơ khí — mạnh, nhưng mỗi
hook là một tầng phải nuôi và một nghi phạm mới khi có án lạ. CHỈ đặt hook khi có ≥1 trong
ba: (1) có check máy chạy được SAU hành động mà agent khó tự thấy (lint/typecheck sau mỗi
lần sửa file → bơm lỗi ngược vào context); (2) trạng thái CROSS-CALL mà một call đơn không
thấy ("đã xử 3, còn 11") — nhưng nếu tool tự chở được trạng thái thì làm ở tool, đừng hook;
(3) hành động một-chiều cần chặn cứng trước khi xảy ra. Ưu tiên **đèn báo (inject nhắc)
hơn khoá (deny cứng)** — block cứng lúc ghi hay bẫy agent vào vòng false-positive không
hiểu vì sao; deny cứng chỉ dành cho một-chiều thật. Hook có sổ: mục đích + môi trường +
chủ — hook chạy ngầm, không sổ thì lúc có án lạ mù thêm một tầng.

## §9. Đối xứng trung tâm — vòng build và sản phẩm agent là MỘT triết lý

Một hệ agent nghiệp vụ đáng tin và một vòng build đáng tin đứng trên cùng bộ nguyên lý:

| Trong sản phẩm agent | Trong vòng build |
|---|---|
| Phanh ở tầng tool — không tin lời agent | Gate máy-kiểm-được — không tin lời implementer |
| Hành động tiền có phiếu + biên nhận, đi đúng một lần | Một người commit + 100% pass — code vào nhánh chính đúng một cửa |
| Audit append-only từng bước | Sổ chu kỳ + sổ quyết định append theo thời gian |
| Đủ điều kiện mới tự quyết, thiếu thì về người | Tự trị trong vùng đảo-ngược-được, điểm rẽ một-chiều về người |
| Tool honest: không có data thì nói không có | Tester honest: không kiểm được thì khai UNVERIFIABLE |
| Dogfood như user thật, sổ lỗi công khai | Tester săn fail + sổ ngoại lệ công khai — không tô hồng |

Ai kiểm được vòng này? Chính các sổ nó đẻ ra: kế hoạch + tổng kết từng chu kỳ với số liệu
chạy lại độc lập, sổ quyết định có ngày + cách đổi, lịch sử commit theo task, CI chạy đủ
các job trên mỗi thay đổi. Vòng không cần được tin bằng lời — nó nộp sổ.

## §10. Trade-off khai thật

- **Chi phí thật đổi chỗ**: build ≈ 0; đường găng là giờ-người chốt spec/quyết định +
  wall-clock của vòng verify (xem §6). Ai lên lịch dự án theo "ngày-công code" sẽ ước sai
  cả hai chiều.
- **Docs đuổi theo code**: tốc độ build cao thì tài liệu là thứ trôi trước nhất. Kỷ luật
  rút ra: claim nào không kèm đường tự-kiểm (lệnh, test, path) sớm muộn cũng lệch; đồng bộ
  docs với code là một loại task có vòng riêng, không phải việc "làm đẹp sau".
- **Gate chỉ chặn được cái nó đo** — phần taste (bố cục đẹp, câu chữ, "đáng làm không")
  vẫn là của người. Giá trị của các gate là làm người RẢNH để chỉ phải nhìn đúng phần đó.
- **Quy trình này mua ĐỘ TIN bằng ĐỘ TRỄ**: mỗi lớp gate/tester/report là wall-clock cộng
  thêm. Với prototype vứt-được thì nó thừa; nó sinh ra cho hệ mà cái giá của "sai mà không
  biết" lớn hơn cái giá của chậm vài vòng kiểm.

---

## Repo này đã ứng dụng thế nào (overview — mỗi dòng tự kiểm được)

Chính repo này được build bằng vòng ở trên — một đội AI 4 vai + một người điều phối:

| Nguyên lý (§) | Trong repo này |
|---|---|
| Spec là contract thì-hoàn-thành (§3) | `SPEC.md` (kể cả mục KHÔNG-LÀM) + `docs/CONTRACT.md` — envelope API/SSE/error nguyên văn từng field, FE↔BE một nguồn sự thật |
| Đội hình + author ≠ checker (§4, §5) | 4 vai cố định (architect/backend/frontend/tester độc lập); mỗi sprint có `sprints/plan_*.md` + `end_*.md` với số liệu chạy lại độc lập |
| Gate máy-kiểm-được, 100% mới commit (§5) | 3 lớp quality-gate/sprint; lịch sử commit theo task; CI 4 job (pytest · ruff · vitest · tsc) mỗi push — badge đầu README |
| Người giữ điểm rẽ, decide-and-log (§6) | `DECISIONS.md` 60+ entry *quyết gì — vì sao — cách đổi* (human-wins); sổ ngoại lệ có ký trong `sprints/end_sprint_*.md` |
| Nghi thước trước khi nghi code (§7) | Biên lai sống: check AST-identical đợt port từng so cả-module đánh trượt bản port hợp lệ → sửa CHECK, không "sửa" code đang đúng (commit `13ce2d2`) |
| Dogfood + sổ lỗi công khai (§9) | `docs/dogfood-findings.md` — 16 finding trên prod, gồm 1 lỗ credential tự phát hiện & vá (D-64) |
| Đối xứng sản phẩm ↔ vòng build (§9) | Phanh tiền ở `backend/app/orch/gated.py` và gate build của đội: cùng một triết lý "không tin lời — tin transaction/test" |
