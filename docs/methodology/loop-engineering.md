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

## §2. Spec là CONTRACT, viết ở thì hoàn thành

**Định kiến:** mô tả ý tưởng rồi để AI "sáng tạo".

**Lựa chọn:** trước khi build, sản phẩm được đặc tả **như thể đã tồn tại** — hành vi, bề
mặt API với envelope nguyên văn từng field, ví dụ vào/ra, hành vi lỗi, và cả danh sách
KHÔNG-LÀM chặn scope-creep. Spec kiểu này chính là **chế tạo ground-truth cho builder**:
mỗi mảnh việc có điều-kiện-xong máy-kiểm-được (test pass, gọi API đúng shape, typecheck
sạch) — agent tự phân rã spec rộng thành mục tiêu con và tự biết lúc nào một mảnh "xanh".
Spec kiểu danh-sách-việc thì không audit được: "đã làm" không suy ra "đã đúng".

Chỗ spec im lặng, luật là: **dừng hỏi, hoặc chọn phương án đảo-ngược-được rồi ghi sổ quyết
định** (*quyết gì — vì sao — cách đổi*) để người đọc lại sau và có quyền lật. Cấm giả định
lặng lẽ — giả định lặng lẽ = bug lặng lẽ.

## §3. Đội hình + vòng lặp: người viết không bao giờ tự chấm

Đội chia vai cố định — người lập kế hoạch/review (đồng thời là **người commit duy nhất**),
các implementer theo mảng, và một **tester độc lập** — cùng một người điều phối. Ba luật
xương sống:

- **Author ≠ checker.** Người viết code tự chấm sẽ pass chính mình. Tester không nhận lời
  khai của implementer làm bằng chứng — tự chạy suite, tự gọi endpoint thật, tự bấm UI;
  fail trả feedback thi-hành-được (expected / actual / cách tái hiện) rồi vòng quay:
  implementer sửa → tester chấm lại → tới 100%. Cái không kiểm được (thiếu env, thiếu
  fixture) khai thẳng **UNVERIFIABLE** — không bao giờ default-xanh; đó chính là chỗ người
  vào spot-check.
- **Verify trước khi tuyên bố.** "Test pass" = chạy lệnh, dán output thật; "đã ghi DB" =
  query lại row; "script chạy" = chạy nó — đọc code không phải chạy code. Áp cho mọi vai,
  kể cả báo cáo của agent con: bên nhận spot-check với nguồn thật trước khi tin.
- **Gate máy-kiểm-được, 100% mới commit.** Mỗi chu kỳ đóng bằng nhiều lớp gate (bề mặt
  API · function/edge-case/typecheck · tổng chu kỳ: số test không được tụt, số liệu chạy
  lại độc lập) — vì tiêu chí không đo được bằng máy là tiêu chí sẽ bị bỏ qua khi mệt. Gate
  fail = chặn commit, không thương lượng. Luật "tử" (cấm xoá, cấm thao tác phá huỷ) cưỡng
  chế bằng **deny cơ khí ở harness**, không phải lời dặn trong prompt — luật prompt là xác
  suất, deny của máy là chắc chắn.

## §4. Người đứng ở đâu trong vòng

**Định kiến:** AI tự trị = người buông tay; hoặc ngược lại, người phải duyệt từng dòng.

**Lựa chọn:** người không kèm code — người giữ đúng phần máy không tự lo được: **định nghĩa
"tốt"** (spec, khẩu vị, ranh giới) và **điểm rẽ không đảo được**. Cơ chế:

- Việc đảo-ngược-được → đội tự quyết + ghi sổ, người đọc lại async và có quyền lật
  (human-wins). Người vắng mặt không làm đội đứng; quyết định treo không làm người bị dí.
- Việc một-chiều (xoá thật, publish, chi tiền) → luôn về người, chặn bằng máy.
- Bất thường dai dẳng nhưng chấp nhận được → **sổ ngoại lệ có ký + điều kiện xét lại**,
  công khai trong sổ chu kỳ — thay vì ép fix. Sổ phình lên nghĩa là spec hoặc gate đang
  sai, không phải thế giới nhiều ngoại lệ.

## §5. Khi kết quả kiểm giở chứng: nghi cái THƯỚC trước khi nghi code

Fail hàng loạt không giải thích được, hai verdict mâu thuẫn, check mới đánh trượt code vốn
tin cậy → thứ tự nghi NGƯỢC bản năng: **(1) môi trường + chính cái check → (2) tool/hạ tầng
→ (3) code sản phẩm — cuối cùng.** Phép thử rẻ: chạy check đó trên code biết-chắc-đúng;
code tốt mà trượt nghĩa là CHECK sai — sửa check kèm ghi chú ngày, cấm nới test lặng lẽ.
Mỗi nghi án kết bằng một hành động kiểm RẺ (một lệnh curl, đọc hai transcript cùng lỗi,
chạy lại một ca bằng tay) trước khi cho sửa bất cứ gì — chẩn đoán không kiểm chứng = đoán.
Và vài lần chạy không phải thống kê: check nhạy phải pass 3 lần liên tiếp mới tính.

## §6. Đối xứng trung tâm — vòng build và sản phẩm agent là MỘT triết lý

Một hệ agent nghiệp vụ đáng tin và một vòng build đáng tin đứng trên cùng bộ nguyên lý:

| Trong sản phẩm agent | Trong vòng build |
|---|---|
| Phanh ở tầng tool — không tin lời agent | Gate máy-kiểm-được — không tin lời implementer |
| Hành động tiền có phiếu + biên nhận, đi đúng một lần | Một người commit + 100% pass — code vào nhánh chính đúng một cửa |
| Audit append-only từng bước | Sổ chu kỳ + sổ quyết định append theo thời gian |
| Đủ điều kiện mới tự quyết, thiếu thì về người | Tự trị trong vùng đảo-ngược-được, điểm rẽ một-chiều về người |
| Dogfood như user thật, sổ lỗi công khai | Tester săn fail + sổ ngoại lệ công khai — không tô hồng |

Ai kiểm được vòng này? Chính các sổ nó đẻ ra: kế hoạch + tổng kết từng chu kỳ với số liệu
chạy lại độc lập, sổ quyết định có ngày + cách đổi, lịch sử commit theo task, CI chạy đủ
các job trên mỗi thay đổi. Vòng không cần được tin bằng lời — nó nộp sổ.

## §7. Trade-off khai thật

- **Chi phí thật đổi chỗ**: build ≈ 0; đường găng là giờ-người chốt spec/quyết định +
  wall-clock của vòng verify. Ước lượng kiểu "N ngày/tính năng" của team người không còn
  áp được — lịch dự án là lịch các buổi chốt spec và các vòng kiểm.
- **Docs đuổi theo code**: tốc độ build cao thì tài liệu là thứ trôi trước nhất. Kỷ luật
  rút ra: claim nào không kèm đường tự-kiểm (lệnh, test, path) sớm muộn cũng lệch; đồng bộ
  docs với code là một loại task có vòng riêng, không phải việc "làm đẹp sau".
- **Gate chỉ chặn được cái nó đo** — phần taste (bố cục đẹp, câu chữ, "đáng làm không")
  vẫn là của người. Giá trị của các gate là làm người RẢNH để chỉ phải nhìn đúng phần đó.
