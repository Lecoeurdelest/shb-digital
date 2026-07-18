# METHODOLOGY — Vì sao chọn từng công nghệ

> BANK Digital — Digital Expert Guild · đề #132 · VAIC 2026.
> Khuôn mỗi mục: *định kiến → cơ chế thật → lựa chọn → trade-off khai thật.* Khai TRẠNG THÁI
> THẬT tại thời điểm viết (S11) — dẫn tên cơ chế + entry DECISIONS cụ thể, không nói vống.

## §0. Nguyên tắc gốc

Công nghệ chọn theo bài toán, không theo résumé. Mỗi thành phần trả lời được: giải cơ chế gì ·
vì sao không chọn phương án quen · từ bỏ gì khi chọn nó.

## §1. Vì sao MULTI-AGENT

**Định kiến:** model đủ thông minh thì một agent gánh hết.

**Cơ chế thật — ba giới hạn của agent đơn:** attention hữu hạn (5 vai = 5 bộ luật nhiễu nhau
trong một context; một vai — một bộ luật — attention dồn một chỗ) · bùng nổ tool (nghiệp vụ đủ
lớn chạm 30–50 tools, chọn sai tăng theo số lựa chọn — chia phòng ban: mỗi agent 5–8 tools đúng
nghề) · tràn context (một ca end-to-end nhồi một context = dài, đắt, trượt bước — MAIN giữ ngữ
cảnh ca mỏng, SUB giữ ngữ cảnh việc ngắn, xong là hết đời).

Cộng: mỗi role **train + certify độc lập** (nâng Legal không hỏng Credit — thật: LAB legal port
CERTIFIED v3 ở S7, D-55, không đụng credit đang chạy production). Quy trình tín dụng thật VỐN
đa phòng ban (NHNN: tách 3 tuyến, maker–checker, phân cấp thẩm quyền) — multi-agent là bản số
hoá trung thực cách ngân hàng buộc phải tổ chức, không phải kiến trúc áp lên bài toán.

**Trạng thái SYSTEM:** 4 chuyên gia mount thật — Credit + Legal (tool LAB byte-identical, D-55/
D-58) · Products + Operations (stub vỏ-viết PROVISIONAL, D-36, chờ LAB). Ca "DN X vay 5 tỷ"
dispatch ≥2 sub song song, canvas render real-sub card (gate S2, browser evidence conv
17fe336a).

**Trade-off:** điều phối phức tạp hơn, bàn giao có thể rơi thông tin — chỉ đáng trả khi bài đủ
phức tạp. Bằng chứng định lượng: endpoint compare single vs multi (deliverable #5, S4) — chênh
lệch nhỏ ở ca đơn giản, bùng nổ ở ca liên-phòng-ban và ca có hành động nhạy cảm.

## §2. Vì sao CLAUDE AGENT SDK — không LangGraph

**Định kiến:** làm multi-agent phải dùng framework đồ thị.

**Luận điểm chính: chọn HIGH-LEVEL SDK vì phần KHÓ thì SDK đã làm sẵn — phần LangGraph làm
sẵn thì tự viết được.**

- Phần khó — **không đội nào tự đắp nổi**, SDK handle trọn: agentic tool-loop được train khớp
  model · **context compaction** tự động · **MCP** native · **subagent** + session
  resume/fork. LangGraph không có tầng này — tự lo trimming, tự dựng tool-loop.
- Phần LangGraph có — checkpoint, interrupt, barrier, typed state — đều là tổ hợp của ba
  nguyên tử SDK đã cấp: **tool-call · vòng đời session (spawn/đóng/resume/fork) ·
  transcript-là-state**. Đã BUILD THẬT trong `backend/app/orch/gated.py`: human-in-the-loop =
  tool `disburse` trả `approval_required` (điều-kiện-chưa-đủ) → sub kết thúc lượt → người bấm
  Duyệt trên UI → API `decide` đánh thức main qua `handle_room_event` (cùng đường event
  `task_done`, KHÔNG chế cơ chế mới) → main giao lại Ops → gọi lại tool → wrapper claim bước 2
  → chạy thật. Vài trăm dòng (`gated.py` + `store_approvals.py`), sở hữu trọn, **đúng nghiệp
  vụ** thay vì generic: phiếu duyệt có vòng đời (pending→approved→used) + biên nhận
  chống-thực-thi-đôi (claim atomic + advisory lock per-key, INVARIANT `status='used' ⟺ receipt
  present`) + phân cấp hạn mức (ma trận 3 tầng, §6 dưới) — thứ `interrupt()` generic không có.
- Đồ thị tĩnh còn ép luật điều phối vào code (conditional edge vẽ trước). MAIN_SKILL (vỏ tự
  viết, `app/orch/main_skill.py`) dạy luồng nghiệp vụ TUẦN TỰ (Tín dụng → Pháp lý kèm bàn giao
  → Vận hành tổng hợp cuối — D-52) bằng PROMPT: đổi thứ tự nghiệp vụ = sửa prompt, không sửa
  code điều phối.

**Khi nào chọn ngược lại:** quy trình cứng nhiều khâu chồng chéo mà tổ chức MUỐN hardcode
(đồ thị = tài liệu chứng nhận quy trình), hoặc ràng buộc multi-vendor. Không phải bài này.

**Trade-off:** gắn hệ sinh thái Anthropic — xử bằng multi-provider qua `ClaudeAgentOptions.env`
per-session (D-45, port từ `battle/core/runtime/providers.py`, KHÔNG chế bánh xe): đổi model là
config (`providers.yaml` — subscription/zai/wrap, UI dropdown 3 nhà D-45b), không đụng process
env nên session song song không đụng nhau. Ca đứt giữa chừng thì re-dispatch task ngắn thay vì
máy cứu-ca — ít moving part (guard A/B race-fix D-47 xử đúng lớp này).

## §3. RAG — phá định kiến "RAG = vector"

**Cơ chế thật:** RAG = mọi cơ chế lấy tri thức ngoài-model bơm vào context; vector chỉ là MỘT
dạng, đúng cho duy nhất dữ liệu đông + phi cấu trúc + không khoá + hỏi mờ nghĩa. Retrieval của
hệ agent là **agentic retrieval**: tool-call trong vòng suy luận (tra mục lục → đọc → thiếu thì
tra tiếp), không phải pipeline top-k tĩnh.

**Bốn tầng dữ liệu — bốn cách truy vấn:**

| Tầng | Cách truy vấn | Vì sao |
|---|---|---|
| Hồ sơ, khoản vay, CIC, lương | SQL | số đúng từng đồng; bank thật cũng query core banking |
| Văn bản quy định | wiki + **document graph** (`[[link]]` = cạnh căn-cứ/thay-thế/hiệu-lực) | compliance đòi nguyên văn + audit từng cạnh; trap "tựa văn-bản-hết-hiệu-lực" bắt bằng cạnh |
| Quan hệ khách ↔ DN ↔ bảo lãnh | **entity graph** (bảng quan hệ + recursive CTE) | trần cho vay NHÓM liên quan (Luật TCTD) — tra phẳng không thấy |
| Sổ tay RM, nghìn ghi chú tự do | **vector local** (BLOB float32 + numpy cosine trong tool, KHÔNG pgvector) | tầng duy nhất semantic thắng: "khách từng có dấu hiệu rủi ro mềm gì?" |

**Trạng thái thật — khai đúng, không vống:** cả 4 tầng đã THIẾT KẾ + BUILD và **CERTIFIED tại
LAB** (`shb-digital-experts/missions/shb-132/RETRIEVAL-README.md`, 18/7): DOER-test 5/5 câu
đúng ground-truth (gói Tết chết theo cạnh thay-thế · C005 ghép CIC+notes+dư nợ · B002 vỡ trần
nhóm đúng số · trần 1 khách có citation · bộ 3 khách quan tâm mua nhà) + QA đối kháng 7 hướng
(39 tool-call có biên lai, PASS toán-tay/đồ-thị/vector/an-toàn-ghi/schema-drift, 4 bug vá +
re-verify). **Tầng SQL** đã nằm TRONG SYSTEM từ S1 (Postgres, D-21/D-22). **Wiki +
document-graph, entity-graph, vector notes** CHƯA port vào SYSTEM — kế hoạch port ở **Sprint
12** (sau S10 deploy, S11 cleanup — thứ tự người chốt 18/7): 3 thao tác quen thuộc (thả
`functions/retrieval.py` vào common/legal, dán SCHEMAS, migration 4 bảng + seed wiki), không
phải xây mới.

**Bản gốc từng nhắm pgvector; bản BUILD THẬT tại LAB là BLOB+numpy local**
(`bkai-foundation-models/vietnamese-bi-encoder` 768-dim + pyvi word-segmentation, CPU, không
mạng — benchmark 18/7 chọn bằng số: precision@5 11/15, phổ điểm rộng 0.45 đỉnh/0.15 đáy so với
3 model đối chứng 8-9/15 dính chùm). Lý do đổi: z.ai + wrapper nội bộ KHÔNG có embedding
endpoint (API là phụ thuộc không sẵn có); 544 notes brute-force cosine <1ms nên pgvector là hạ
tầng thừa ở quy mô này; quan trọng hơn — giữ tool SQL PORTABLE tuyệt đối (SQLite lab ↔ Postgres
system không đổi một dòng). pgvector ghi nhận là đường mở khi notes lên quy mô triệu dòng,
không build trước.

Mọi tri thức được dùng có vết 2 tầng: citation → dòng/trang → file nguồn git.

**Câu chốt:** *RAG không phải một công nghệ — là quyết định tổ chức dữ liệu. Người chọn cách
truy vấn đúng bản chất từng tầng; agent chỉ việc gọi.*

**Trade-off:** vector CHỈ ở tầng ghi-chú-mềm — đặt lên hồ sơ/quy định là rước retrieval-sai-
âm-thầm vào chỗ cần chính xác tuyệt đối. Local-CPU đổi lấy độ trễ thấp hơn API nhưng ăn RAM/CPU
server lúc encode — chấp nhận ở quy mô demo; S12 phải rebuild image cài sentence-transformers +
pyvi, cache model vào volume (venue không cần mạng).

## §4. PHANH ở tầng TOOL — không phải prompt

Prompt là hành-vi-mong-muốn, không phải cơ chế an toàn (model quên / bị dụ / injection).
Tầng kiểm được 100% là tool: cú gọi **tự nó không nổ được** khi chưa đủ điều kiện — luật nằm
ở cái két, không ở lời dặn.

**Cơ chế thật đã build (`backend/app/orch/gated.py`, T3-1/T3-2, SPEC §4.4):** wrapper gated
chạy 1 conn psycopg2 riêng, 1 transaction đồng bộ **4 bước tuần tự** trong `asyncio.to_thread`
(không block event loop 1-worker):
1. Biên nhận cũ (status='used') → trả biên nhận, không chạy lại.
2. Phiếu approved → **claim atomic** (`UPDATE … WHERE status='approved' RETURNING id`) rồi mới
   chạy — 1 phiếu = đúng 1 lần thực thi.
3. Phiếu pending → báo chờ, không đẻ phiếu/card mới (idempotent).
4. Chưa có gì → ma trận 3 tầng quyết `auto` hay `human` (§7 dưới); `human` → tạo phiếu pending
   + card approval, kết thúc lượt.

Đầu transaction có `pg_advisory_xact_lock(hash(conv_id, action, payload_hash))` — serialize
per-key, chặn race 2-gọi-đồng-thời đẻ phiếu rác (tester tìm 18/7, fix bằng advisory lock, verify
10× không rác). INVARIANT tiền: receipt-save nằm TRONG CÙNG tx với claim + write nghiệp vụ
(`status='used' ⟺ receipt present`) — lỗi giữa chừng thì rollback về `approved`, retry sạch,
không có cửa sổ tiền-đôi. Chuỗi tin cậy **tool-ghi-DB → wrapper-đọc-DB**: model bịa "hồ sơ
xanh" trong lời cũng không mở được két, vì điều kiện auto đọc thẳng bảng `assessments`, không
đọc lời agent.

Phanh = **phân cấp thẩm quyền** đúng nghiệp vụ, không phải nhị phân chặn/không-chặn (§6). Đây
là câu trả lời cho chữ đề nhấn ba lần: *execute actions* — thực thi thật trong thẩm quyền, dừng
thật đúng chỗ người phải ký.

## §5. Hạ tầng TỐI GIẢN — một Postgres

Mỗi moving part thêm = một điểm hỏng thêm. SYSTEM chọn D-21 (đảo SPEC gốc): **1 Postgres 15**
gánh trọn — data nghiệp vụ (customers/loans/collaterals/cic/assumptions) + render (cards/
conversations) + audit append-only (tool_calls) + phanh (approvals) — 1 pool, 1 migration
(Alembic), deploy on-premise một lệnh. Wiki + hai đồ thị (CTE) + vector notes (BLOB, §3) khi
port ở S12 cũng nằm CHUNG Postgres này — không thêm hạ tầng mới. Đường mở vẽ sẵn chưa build:
đa worker → tách queue; đồ thị triệu cạnh → graph engine; kho vạn trang → nâng retrieval. Chừa
chỗ cắm, không chừa code chết.

## §6. Vì sao NGƯỜI DUYỆT ở tầng TOOL, không phải agent-approver

**Định kiến hay gặp trong đề multi-agent:** an toàn = thêm một agent "kiểm duyệt" đọc lại kết
quả agent kia rồi gật/lắc.

**Vì sao SYSTEM không làm vậy:** một agent-approver vẫn là LLM đọc-và-tin lời LLM — chỉ dịch
chuyển bề mặt tấn công, không xoá nó, vì cả hai nhận input là TEXT. N2 (SPEC §2) đã nói rõ:
*"Skill là hành-vi-mong-muốn, không phải cơ chế an toàn. Prompt 'đừng làm X' không chặn được
X."* Agent-approver bị dụ y hệt agent-thực-thi bị dụ. Cửa duyệt thật phải nằm ở nơi model
**không thể nói dối được** — không nằm trong lời, nằm trong dữ liệu server tự ghi.

**Cơ chế thật khiến "duyệt ở tool" hoạt động — ba mảnh khớp nhau:**
- **N2 + phanh 4-bước (§4):** điều kiện mở két đọc thẳng `approvals`/`assessments` trong DB,
  không đọc câu chuyện agent kể. Agent thuyết phục thế nào, tay vặn vẫn không ra tiền nếu bảng
  chưa có phiếu `approved`.
- **Ma trận thẩm quyền 3 tầng verdict-aware (D-59, `app/orch/verdict.py`):** agent là MỘT CẤP
  THẨM QUYỀN có hạn mức, giống nhân viên ngân hàng thật — không phải "luôn hỏi người" hay "luôn
  tự quyết". Tầng 1 (`<500tr`): auto trừ khi verdict xấu (`lane=red`) thì thắt về người. Tầng 2
  (`500tr–2 tỷ`): auto CHỈ khi hồ sơ đã qua 3 trụ pháp lý và lane=green (dẫn `assessment #id`
  làm căn cứ, trích thẳng bản ghi LAB certify — không tự xưng). Tầng 3 (`>2 tỷ`): luôn người.
  `assessments` rỗng (chưa qua Legal) → hành vi y hệt bản trước D-59 — verdict-aware KHÔNG nới
  lỏng, chỉ SIẾT thêm.
- **D-56 hai persona:** app tách CỬA KHÁCH (role `customer`, khoanh chỉ-thấy-ca-mình, MAIN
  inject danh tính, KHÔNG có quyền `decide`) và BÀN DUYỆT NGÂN HÀNG (role admin, thấy mọi ca +
  Control Tower + quyền duyệt). Thẩm quyền nằm ở role-check tại API (`require_admin` cho
  `decide`), không ở việc agent "tự nhận mình là ai" — khách prompt-inject cỡ nào cũng không
  đổi được role JWT của chính họ, vì phanh đọc cookie/claims đã ký, không đọc lời khách.

**Kết quả đo được:** tester verify 12/12 nhánh (happy/reject/decide-twice→409/authz) bằng
browser + query PG trực tiếp — biên nhận, không phải lời khai. Card "tự động duyệt" ở tầng auto
vẫn hiện NGUYÊN VĂN lý do (`reason` từ `disburse_decision`) trên canvas — người xem thấy phanh
vẫn tồn tại, chỉ là thẩm quyền được cấp có kiểm soát, không phải phanh bị tắt.

**Trade-off khai thật:** thẩm quyền tự động dựa trên `lane` verdict là con dao 2 lưỡi có chủ
đích — nhanh hơn chờ người ở ca rõ ràng, nhưng một lỗi trong tool `legal_classify` (LAB certify,
ngoài quyền sửa của SYSTEM — N1) lan thẳng thành auto-approve sai. Vì vậy Legal phải
byte-identical với bản certify (D-55/D-58, không vá tay) — thẩm quyền tool càng cao, yêu cầu về
nguồn-sự-thật của thứ nó tin càng khắt khe.

## §7. Đo được mới tin

- Bộ ca certify 3 tầng (floor/trap/combo) chấm máy trên ground-truth seed; trap = làm-ẩu-thì-
  fail (nợ xấu phải từ chối, chưa phê duyệt phải bị chặn, lương lệch phải tính lại) — LAB DOER-
  test 5/5, QA đối kháng 7 hướng có biên lai (§3).
- Tester nội bộ SYSTEM giữ nguyên tắc **author ≠ checker**: mọi gate (S1→S10) verify bằng
  browser evidence + query DB thật, không nhận lời khai implementer — 465 test tại S9/S10 (355
  backend + 110 FE), tăng dần qua từng sprint, không lùi; vòng chấm cuối 6/6 chạy TRÊN
  production công khai (digital.tinhdev.com), không phải máy dev.
- **Span-grounding**: mọi trích dẫn đối chiếu ngược về trang/dòng được cite — không có thật
  = rejected (nguyên tắc LAB retrieval §5, port cùng S12).
- Single vs multi chạy CÙNG bộ ca qua endpoint compare (Control Tower, S4) — khoảng cách hai
  cột là con số duy nhất xin giám khảo nhớ.

*Hệ này không xin được tin — nó nộp bảng điểm.*
