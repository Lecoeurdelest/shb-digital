# BUSINESS CASE — Khả thi kinh doanh & Lộ trình pilot

> BANK Digital — Digital Expert Guild · đề #132 · VAIC 2026.
> Nguyên tắc số liệu: **số đo được từ hệ** ghi kèm nguồn; **số nghiệp vụ ngành** là giả định
> khai rõ, tham số hoá — pilot Pha 0 (shadow-mode) chính là cỗ máy đo lại các giả định này
> bằng dữ liệu thật của ngân hàng, trước khi cam kết bất kỳ con số nào với kinh doanh.

## §1. Bài toán kinh tế — tiền nằm ở đâu

Quy trình tư vấn + sơ thẩm một khoản vay hiện đi qua nhiều phòng ban (tiếp nhận → tín dụng →
pháp chế → vận hành), mỗi bước chờ nhau theo giờ hành chính:

| Đại lượng | Hiện trạng (giả định khai rõ) | Với hệ này (đo từ demo) |
|---|---|---|
| Thời gian khách nhận kết quả sơ thẩm đủ 3 mặt (năng lực trả nợ · pháp lý · gói phù hợp) | 1–3 ngày làm việc (chuyển tay liên phòng ban) | **3–5 phút/ca** — các chuyên gia chạy song song, đo trực tiếp trên demo |
| Công RM cho một hồ sơ sơ thẩm | 2–4 giờ tra cứu + tổng hợp thủ công | RM duyệt KẾT QUẢ thay vì tự tra: mọi con số có nguồn tool, audit sẵn |
| Chi phí biến đổi một ca tư vấn | giờ-công nhiều phòng ban | chi phí LLM/ca — hệ có sẵn chỗ đo (`/api/compare` trả `cost` mỗi run; tab thống kê cost đang mở rộng S16) |
| Nhất quán chất lượng | phụ thuộc kinh nghiệm từng RM | mọi ca cùng một bộ SKILL + wiki chính sách + ma trận thẩm quyền |

Giá trị không nằm ở "thay người quyết" — nằm ở **nén thời gian chờ liên phòng ban** và **chuẩn
hoá chất lượng sơ thẩm**, hai thứ đo được ngay trong pilot.

## §2. Hệ hiện phủ đoạn nào của vòng đời khoản vay — và mở rộng bằng gì

Vòng đời khoản vay đầy đủ: tiếp nhận/eKYC → thẩm định & rủi ro → quyết định & phê duyệt →
hợp đồng & giải ngân → giám sát sau vay. Trạng thái phủ của hệ:

| Giai đoạn | Trạng thái trong hệ |
|---|---|
| Tư vấn sản phẩm + tiếp nhận nhu cầu | ✅ chạy (MAIN + form intake trong hội thoại) |
| Thẩm định năng lực trả nợ (DSCR/LTV/CIC) | ✅ chạy — chuyên gia Tín dụng, tool SQL thật |
| Soát pháp lý 3 trụ + trần nhóm liên quan | ✅ chạy — chuyên gia Pháp chế + entity-graph |
| Quyết định & phê duyệt phân cấp | ✅ chạy — ma trận thẩm quyền 3 tầng + phanh tầng tool + bàn duyệt |
| Gói sản phẩm & lộ trình giải ngân | 🔧 code CERTIFIED đã port, chờ migration schema (T12-2) |
| eKYC/OCR chứng từ · fraud · giám sát sau vay · thu hồi nợ | 🗺 lộ trình — mỗi mảng = **một thư mục `roles/<role>/` mới** (SKILL + functions), vỏ mount tự động, không sửa core |

Điểm kiến trúc ăn tiền cho lộ trình: **thêm một nghiệp vụ = thêm một labpack**, đã tự chứng
minh 2 lần (legal port S7, retrieval + products/ops port S12). Chi phí mở agent mới là chi phí
Ở TẦNG NGHIỆP VỤ (định nghĩa luật + tool), không phải chi phí đập core.

## §3. Lộ trình pilot 3 pha — mỗi pha có tiêu chí go/no-go

**Pha 0 — Shadow-mode (4–6 tuần, không rủi ro nghiệp vụ):**
hệ chạy SONG SONG quy trình thật tại 1 phòng giao dịch: RM vẫn quyết như cũ, hệ xử lý cùng
hồ sơ và ghi kết luận vào audit — không quyết gì thật. Tầng auto của ma trận đặt **0 đồng**
(mọi phiếu đều chờ người — cơ chế có sẵn, chỉ là cấu hình ngưỡng).
*Đo:* độ khớp kết luận hệ ↔ quyết định người (per hồ sơ, per trụ pháp lý) · thời gian/ca ·
chi phí LLM/ca · tỷ lệ tool-error. **Go khi:** độ khớp ≥ ngưỡng ngân hàng chốt (đề xuất ≥90%
trên khoản nhỏ), 0 sự cố an toàn dữ liệu, audit đủ 100% ca.

**Pha 1 — Một chi nhánh, thẩm quyền thắt (8–12 tuần):**
bật tầng auto cho đúng **khoản nhỏ tín chấp** (ví dụ ≤50 triệu — thấp hơn nhiều ngưỡng
500 triệu của demo; ngưỡng là config trong ma trận, ngân hàng chốt). Khoản còn lại: hệ làm
sơ thẩm, người ký. Mọi phiếu auto có lý do + biên nhận, đối soát cuối ngày.
*Đo thêm:* % ca auto đúng (đối soát hậu kiểm) · thời gian xử lý đầu-cuối · NPS khách + RM.
**Go khi:** 0 phiếu auto sai qua hậu kiểm 2 chu kỳ, chỉ số vận hành ổn định.

**Pha 2 — Mở rộng:** thêm chi nhánh, nới ngưỡng auto theo dữ liệu Pha 1, mở labpack mới theo
thứ tự **giá trị nhanh/rủi ro thấp trước** (intake/eKYC/chứng từ — việc lặp lại tốn nhân lực,
không trực tiếp ra quyết định) rồi mới tới các agent chấm điểm/quyết định (luôn giữ người
kiểm soát + giải trình đầy đủ).

Ba cơ chế demo đã có sẵn làm pilot RẺ: ma trận thẩm quyền là **cấu hình** (siết về 0 = shadow
mode tức thì) · audit append-only là **máy đo độ khớp** dựng sẵn · so sánh single-vs-multi là
khung đo chi phí/chất lượng.

## §4. Tích hợp thực tế — chỗ cắm đã chừa sẵn

Demo chạy trên Postgres seed giả lập **có chủ đích**: mọi nguồn ngoài đi qua tool có contract
cố định, nên tích hợp thật = **đổi adapter dưới tool, không đổi agent**:

| Nguồn thật | Tool hiện tại (contract giữ nguyên) | Việc tích hợp |
|---|---|---|
| CIC | `cic_lookup` đọc bảng seed | adapter gọi API CIC, giữ envelope `{found, item, asOf, hint}` |
| Core banking (T24/tương đương) | `disburse` ghi `loans.status` | adapter gọi core; **phanh phiếu + biên nhận giữ nguyên ở tầng tool** — chính là chỗ ngân hàng cần nhất khi nối core thật |
| eKYC/OCR | (labpack lộ trình) | agent intake mới, không đụng các agent đang chạy |
| Chính sách nội bộ | wiki 4 tầng đã port (82 trang, citation bắt buộc) | thay nội dung wiki bằng văn bản nội bộ ngân hàng — cập nhật chính sách = sửa tài liệu, không sửa code |

Hạ tầng: **một Postgres, deploy on-premise một lệnh** (compose) — chạy được trong DC của ngân
hàng; **on-prem LLM đã kiểm chứng cơ chế** (Ollama giọng Anthropic) cho kịch bản dữ liệu không
rời hạ tầng (NĐ13/bảo mật); multi-provider = đàm phán giá/không khoá vendor.

## §5. Trách nhiệm pháp lý khi agent tự duyệt — trả lời thẳng

Câu hỏi đúng: *ai chịu trách nhiệm khi tầng auto duyệt sai?* Trả lời của thiết kế:

1. **Agent không phải chủ thể thẩm quyền — nó là CÔNG CỤ thực thi một uỷ quyền có văn bản.**
   Ma trận thẩm quyền (ngưỡng tiền, điều kiện hồ sơ, lane pháp lý) do NGÂN HÀNG cấu hình và
   phê duyệt — giống văn bản uỷ quyền hạn mức cho một cấp nhân viên. Trách nhiệm pháp lý nằm
   ở ngân hàng vận hành, như mọi hệ tự động hoá quyết định — vì vậy ma trận phải là thứ
   ban lãnh đạo ký, không phải tham số kỹ thuật.
2. **Mọi quyết định auto giải trình được:** phiếu ghi `decided_by=auto-rule` + lý do nguyên
   văn + căn cứ (`assessment #id` từ phân loại pháp lý ghi DB) + audit từng tool call —
   phục vụ khách hàng, kiểm toán nội bộ và cơ quan quản lý (khớp yêu cầu giải trình của
   nghiệp vụ tín dụng).
3. **Thiết kế chỉ-siết:** thiếu dữ liệu/hồ sơ chưa qua pháp lý → rơi về người, không bao giờ
   tự nới (verdict-aware — `docs/methodology/README.md` §6). Lỗi hệ thống ở bất kỳ tầng nào đều
   fail-closed về phía "chờ người".
4. **Pilot bắt đầu với auto = 0** (Pha 0): hệ chứng minh độ khớp bằng số liệu trước, ngân
   hàng mới uỷ quyền dần — trách nhiệm được chuyển giao theo dữ liệu, không theo niềm tin.

## §6. KPI theo dõi pilot (dashboard có sẵn khung)

| KPI | Nguồn đo trong hệ |
|---|---|
| Thời gian đầu-cuối/ca | timestamps conversation + tasks |
| Độ khớp hệ ↔ người (shadow) | audit + assessments đối chiếu quyết định RM |
| % ca trong hạn mức auto / % rơi về người | bảng approvals (`decided_by`) |
| Chi phí LLM/ca, theo model | compare `cost` + tab thống kê (S16 đang mở rộng) |
| Tool-error rate | bảng tool_calls (audit append-only) |
| Phủ audit | 100% ca phải có vết — điều kiện cứng, không phải KPI mềm |
