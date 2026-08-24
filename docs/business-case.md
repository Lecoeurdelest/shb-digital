# BUSINESS CASE — Khả thi kinh doanh & Lộ trình pilot

> BANK Digital — Digital Expert Guild · đề #132 · VAIC 2026.
> Nguyên tắc số liệu: **số đo được từ hệ** ghi kèm nguồn; **số nghiệp vụ ngành** là giả định
> khai rõ, tham số hoá — pilot Pha 0 (shadow-mode) chính là cỗ máy đo lại các giả định này
> bằng dữ liệu thật của ngân hàng, trước khi cam kết bất kỳ con số nào với kinh doanh.

## §1. Bài toán kinh tế — tiền nằm ở đâu

Quy trình tư vấn + sơ thẩm một khoản vay hiện đi qua nhiều phòng ban (tiếp nhận → tín dụng →
pháp chế → vận hành), mỗi bước chờ nhau theo giờ hành chính:

Đây **không** phải bài toán cạnh tranh với luồng tự động khoản vay nhỏ theo **TT 06/2023**.
Theo định vị D-73, khoảng trống cần giải là hồ sơ SME/phức tạp/có tài sản bảo đảm: nhiều nguồn,
nhiều phòng và nhiều lần bàn giao. Hệ đóng vai **copilot sơ thẩm + vận hành middle office** cho
bàn RM/cán bộ tín dụng; hệ chuẩn bị tờ trình, căn cứ và cảnh báo, còn con người quyết định và ký.
Cửa khách hàng là bề mặt demo/sandbox để chứng minh vòng đời, không phải persona thương mại chính.
Nguồn định hướng: [`claude/strategic-report-shb-digital-en.md`](../claude/strategic-report-shb-digital-en.md).

| Đại lượng | Hiện trạng (giả định khai rõ) | Với hệ này (đo từ demo) |
|---|---|---|
| Thời gian bàn RM có bản sơ thẩm đủ 3 mặt (năng lực trả nợ · pháp lý · gói phù hợp) | 1–3 ngày làm việc (chuyển tay liên phòng ban) | **3–5 phút/ca demo** — các chuyên gia phối hợp, đo trực tiếp trên môi trường demo |
| Công RM cho một hồ sơ sơ thẩm | 2–4 giờ tra cứu + tổng hợp thủ công | RM rà soát tờ trình thay vì tự tra từ đầu: mọi con số có nguồn tool, audit sẵn; quyền quyết định không chuyển cho model |
| Chi phí biến đổi một ca tư vấn | giờ-công nhiều phòng ban | chi phí LLM/ca — hệ có sẵn chỗ đo (`/api/compare` trả `cost` mỗi run; tab thống kê cost đang mở rộng S16) |
| Nhất quán chất lượng | phụ thuộc kinh nghiệm từng RM | mọi ca cùng một bộ SKILL + wiki chính sách + ma trận thẩm quyền |

Giá trị không nằm ở “thay người quyết” hay tự động hoá khoản vay nhỏ — nằm ở **nén thời gian chờ
liên phòng ban** và **chuẩn hoá chất lượng sơ thẩm**, hai thứ đo được ngay trong pilot.

## §2. Hệ hiện phủ đoạn nào của vòng đời khoản vay — và mở rộng bằng gì

Vòng đời khoản vay đầy đủ: tiếp nhận/eKYC → thẩm định & rủi ro → quyết định & phê duyệt →
hợp đồng & giải ngân → giám sát sau vay. Trạng thái phủ của hệ:

| Giai đoạn | Trạng thái trong hệ |
|---|---|
| Tư vấn sản phẩm + tiếp nhận nhu cầu | ✅ chạy (MAIN + form intake trong hội thoại) |
| Thẩm định năng lực trả nợ (DSCR/LTV/CIC) | ✅ chạy — chuyên gia Tín dụng, tool SQL thật |
| Soát pháp lý 3 trụ + trần nhóm liên quan | ✅ chạy — chuyên gia Pháp chế + entity-graph |
| Đề xuất quyết định + phê duyệt có người | ✅ chạy — ma trận đưa khuyến nghị, phanh tầng tool + bàn duyệt; pilot đặt ngưỡng auto bằng 0 |
| Gói sản phẩm & lộ trình giải ngân | 🔧 code CERTIFIED đã port S12 — migration + seed bảng `products`/`applications` đã vào, role query bảng thật + MAIN dispatch được; **e2e prod VERIFIED** (phiếu→duyệt→DSB03+receipt, T12-5) |
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
trên tập hồ sơ SME/phức tạp của pilot), 0 sự cố an toàn dữ liệu, audit đủ 100% ca. Đây là
**điều kiện trước pilot**, chưa phải claim của profile demo: ledger approval/receipt là transaction
mạnh, còn trace `tool_calls` thường hiện best-effort và chưa phải WORM.

**Pha 1 — Một bàn RM/chi nhánh, người ký (8–12 tuần):**
giữ ngưỡng auto ở **0**; đưa copilot vào ca SME/phức tạp có kiểm soát. Hệ tự động hoá việc chuẩn
bị (intake, tra cứu, đối chiếu, tờ trình, cảnh báo và bàn giao), không tự ra quyết định tín dụng.
RM/cấp phê duyệt rà soát, sửa nếu cần và ký trong Control Tower.
*Đo thêm:* thời gian xử lý đầu-cuối · tỷ lệ tờ trình cần sửa · độ khớp khuyến nghị ↔ quyết định
người · NPS RM/bàn phê duyệt. **Go khi:** không có sự cố dữ liệu/phanh, audit đủ và chỉ số vận hành
ổn định qua hai chu kỳ.

**Pha 2 — Mở rộng:** thêm bàn/chi nhánh và lớp hồ sơ phức tạp; mở labpack theo thứ tự **giá trị
nhanh/rủi ro thấp trước** (intake/eKYC/chứng từ — việc lặp lại tốn nhân lực, không trực tiếp ra
quyết định), rồi tới agent hỗ trợ chấm điểm. Con người tiếp tục kiểm soát, giải trình và ký.

Ba cơ chế làm pilot rẻ: ngưỡng thẩm quyền là **cấu hình** (đặt 0 = shadow fail-closed) · ledger
shadow là **máy đo độ khớp** system↔human · so sánh single-vs-multi là khung đo chi phí/chất lượng.
Mở lại bất kỳ nhánh auto nào là một quyết định quản trị riêng, cần ma trận được ngân hàng ký duyệt;
đó không phải định vị của lộ trình này.

## §4. Tích hợp thực tế — chỗ cắm đã chừa sẵn

Kiến trúc thương mại không lấy SPA làm sản phẩm chính:

| Lớp | Nội dung | Từ repo hiện tại |
|---|---|---|
| **Lõi headless** | Runtime agent + phanh + audit; REST/SSE; role/common tool mount qua MCP in-process | `backend/app/orch/`, `backend/app/mount/`, `gated.py` — sản phẩm thật |
| **Mặt tiền bank** | SAHA/website/portal RM/LOS gọi API hoặc nhúng widget | package `frontend/sdk/`; contract tại `docs/CONTRACT.md` §9 |
| **Control Tower** | Hàng đợi duyệt, audit, vận hành, analytics | SPA `frontend/src/` được giữ làm reference host + mặt bàn admin |
| **Chat ngoài** | Chỉ doorbell + deep-link | adapter S19; không credit data, không approve-from-chat (D-71) |

Đừng gộp “MCP đã có” với “adapter nguồn đã tích hợp”: repo hiện tạo MCP server **theo role** và
common retrieval trong cùng process. MCP server tách process **theo từng hệ nguồn** CIC/core/eKYC,
credential thật và network contract của ngân hàng chưa có; đó là hạng mục integration tiếp theo,
không phải bằng chứng của S21.

Demo chạy trên Postgres seed giả lập **có chủ đích**: mọi nguồn ngoài đi qua tool có contract
cố định, nên tích hợp thật = **đổi adapter dưới tool, không đổi agent**:

| Nguồn thật | Tool hiện tại (contract giữ nguyên) | Việc tích hợp |
|---|---|---|
| CIC | `credit_cic_get` đọc bảng seed | adapter gọi API CIC, giữ nguyên input/output schema của tool |
| Core banking (T24/tương đương) | `disburse` ghi `loans.status` | adapter thật phải nhận `payload_hash` làm idempotency key và core phải replay cùng receipt; chưa được gọi là exactly-once live trước crash-window test |
| eKYC/OCR | (labpack lộ trình) | agent intake mới, không đụng các agent đang chạy |
| Chính sách nội bộ | wiki 4 tầng đã port (82 trang, citation bắt buộc) | thay nội dung wiki bằng văn bản nội bộ ngân hàng — cập nhật chính sách = sửa tài liệu, không sửa code |

Hạ tầng: một Postgres + FastAPI chạy được on-prem. Compose hiện tại là **profile demo** và có thể
chọn provider ngoài; không dùng nó làm bằng chứng data-residency. Triển khai yêu cầu dữ liệu không
rời DC phải dùng profile `bank_dc`, readiness pass và egress policy độc lập của ngân hàng. Ollama
đã chứng minh cơ chế provider on-prem; chất lượng/model sizing vẫn phải benchmark trên hạ tầng đích.

## §5. Trách nhiệm khi AI hỗ trợ quyết định — trả lời thẳng

Câu hỏi đúng: *ai quyết và ai chịu trách nhiệm?* Trả lời của thiết kế theo D-73:

1. **Agent không phải chủ thể thẩm quyền.** Nó chuẩn bị tờ trình, căn cứ, cảnh báo và khuyến nghị;
   RM/cấp phê duyệt của ngân hàng rà soát và ký. Trách nhiệm không được chuyển cho model.
2. **Mọi khuyến nghị có đường giải trình:** căn cứ (`assessment #id` từ phân loại pháp lý ghi DB),
   nguồn tool và trace từng call được ghi. Approval/receipt là ledger transaction; muốn cam kết
   audit 100% cho pilot phải nâng trace thường khỏi best-effort và bổ sung retention/WORM theo bank.
3. **Thiết kế chỉ-siết:** thiếu dữ liệu/hồ sơ chưa qua pháp lý → rơi về người, không bao giờ tự
   nới (verdict-aware — `docs/methodology/README.md` §6). Lỗi ở bất kỳ tầng nào đều fail-closed về
   phía “chờ người”.
4. **Pilot giữ auto = 0:** hệ đo độ khớp bằng ledger shadow nhưng không quyết thật. Nhánh
   `auto-rule` hiện hữu là seam kỹ thuật/tương thích demo; chỉ được mở lại bằng một quyết định quản
   trị riêng với ma trận thẩm quyền do ngân hàng ký, không phải thay đổi tuỳ ý của đội kỹ thuật.

## §6. KPI theo dõi pilot (dashboard có sẵn khung)

| KPI | Nguồn đo trong hệ |
|---|---|
| Thời gian đầu-cuối/ca | timestamps conversation + tasks |
| Độ khớp hệ ↔ người (shadow) | `shadow_reviews` + `/api/stats/shadow-match` |
| % khuyến nghị `auto-eligible` / `human-review` / `reject-recommended` | `shadow_reviews` + `/api/stats/shadow-match` |
| Chi phí LLM/ca, theo model | compare `cost` + tab thống kê (S16 đang mở rộng) |
| Tool-error rate | bảng tool_calls (audit append-only) |
| Phủ audit | Điều kiện go-live = 100%; hiện approval/receipt mạnh, `tool_calls` best-effort nên pre-pilot chưa đạt |
