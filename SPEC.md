# Digital Expert Guild — Core Spec v2.0
> Đề #132 SHB (VAIC 2026): đội chuyên gia số ngân hàng — multi-agent có giám sát, có phanh, có bằng chứng.
> Spec TỰ CHỨA: nguyên lý → kiến trúc → cơ chế → contract → rule. Thay thế toàn bộ v1.
> Cách build từng phần: `docs/patterns/` (5 pattern doc tự chứa — xem `00-INDEX.md`).
> Spec + patterns TỰ CHỨA — không phụ thuộc tài liệu ngoài repo. Design/mock: `design/`
> (tham khảo look-and-feel — D-13/D-14); nguồn tài sản LAB để copy: DECISIONS D-08.

---

## 1. Vision

**Một chi nhánh ngân hàng số thu nhỏ.** RM gõ một yêu cầu phức tạp tiếng Việt → đội chuyên gia số
(1 MAIN điều phối + các SUB chuyên gia: Credit / Legal / Products / Operations) tự chia việc, tra cứu,
TÍNH bằng tool (không nhẩm), phối hợp, THỰC THI hành động có phanh — việc nhạy cảm dừng chờ người
duyệt. Mọi bước có vết, mọi con số có nguồn.

**Không phải chatbot trả lời — là đội-làm-việc có giám sát, có phanh, có bằng chứng.**

## 2. Nguyên lý nền (tiên đề — mọi quyết định thiết kế suy từ đây)

**N1 — Ba tầng trách nhiệm: VỎ – NÃO – TRÍ KHÔN.**
- **VỎ (SYSTEM, repo này)** = cơ khí phòng làm việc: bàn giao, hàng đợi, đánh thức, phanh, sổ sách,
  tool điều phối, UI. Vỏ KHÔNG chứa luật nghiệp vụ, KHÔNG ép luật điều phối ("đợi đủ N con").
- **NÃO (model)** = mọi quyết định trong lượt: giao ai, đợi hay tổng hợp, hòa giải mâu thuẫn,
  cư xử khi user chen lời. Vỏ đưa thông tin đúng lúc (kết quả sub + bảng việc), não quyết.
- **TRÍ KHÔN (lab)** = tool + skill nghiệp vụ của TỪNG SUB — nuôi ở repo lab riêng, ghép qua
  contract §7. MAIN không cần lab train: skill mỏng (vỏ tự viết) + tool điều phối là đủ.

**N2 — Không tin agent qua lời dặn.** Skill là hành-vi-mong-muốn, không phải cơ chế an toàn.
Gate / scope / audit đặt ở TẦNG TOOL — chỗ duy nhất kiểm được 100%. Prompt "đừng làm X" không
phải phanh; phanh là cú gọi tool tự nó không nổ được khi chưa đủ điều kiện (§4.4).

**N3 — Vỏ mù nội dung.** Vỏ chỉ khoá INTERFACE (§7): tool signature, schema shape, skill = text,
output = dict tự do chuyển thẳng cho agent. Bao nhiêu tool, skill dạy gì, số nào đúng — vỏ không
biết và không cần biết. Lab đẩy vào lúc nào cũng chạy, vỏ không đổi.

**N4 — Đơn giản trước, mở rộng là đường đã vẽ.** 1 worker, in-process, ít moving part. Các đường
mở (thêm role, wiki tri thức, vector search, đa worker) được thiết kế SẴN CHỖ CẮM nhưng KHÔNG build
trước khi cần.

**N5 — Card có cấu trúc là OPT-IN qua tool-call, không phải schema ép.** Agent trả TEXT tự do cho
chat. Muốn hiện "sản phẩm công việc" có cấu trúc bên canvas → agent GỌI tool `present`. Vỏ không
bao giờ parse text của agent ra card.

## 3. Kiến trúc: phòng làm việc

```
┌──────────────── 1 CONVERSATION = 1 CA = 1 PHÒNG ────────────────┐
│                                                                  │
│  USER ──chat──▶ ┌────────┐  orch_dispatch  ┌──────────────┐     │
│  (RM/admin)     │  MAIN   │────────────────▶│ SUB Credit   │     │
│        ◀────────│ (điều   │◀───event────────│ SUB Legal    │     │
│        trả lời  │  phối)  │  (báo xong)     │ SUB Products │     │
│                 └────────┘                  │ SUB Ops      │     │
│                     │                       └──────────────┘     │
│                     └── mỗi sub: SKILL + toolpack riêng (lab)    │
└──────────────────────────────────────────────────────────────────┘
```

- **User chỉ nói chuyện với MAIN.** Sub không lộ mặt ra chat (nhưng hiện trên canvas/tower).
- **MAIN** = 1 SDK session BỀN per conversation — resume từ disk (SDK tự lưu transcript), nhớ
  nguyên ngữ cảnh ca qua các lượt và qua cả restart.
- **SUB** = SDK client TƯƠI mỗi lần được giao việc (disposable): system_prompt = SKILL role,
  tool = toolpack role + tool chung (calc, present), nhận ngữ cảnh qua input của task. Xong là hết đời.
- **Sub không nói chuyện với nhau, không nói với user** — mọi bàn giao qua MAIN.
- **Role động**: vỏ quét thư mục roles/, lab đẻ role nào thì phòng có role đó. Thêm phòng ban =
  thêm {SKILL + toolpack}, không sửa code vỏ.

## 4. Bốn cơ chế lõi (toàn bộ phần "cơ khí" của vỏ)

### 4.1 Giao việc — main gọi tool, sub chạy nền, main free
```
MAIN gọi orch_dispatch(role, title, input)
  → vỏ ghi task (DB) + spawn sub chạy NỀN
  → tool trả NGAY {role, status:"running", hint} → MAIN FREE, tiếp tục lượt hoặc kết thúc lượt
```
- **ID cho CODE, TÊN cho MODEL**: trong 1 phòng không bao giờ có 2 con cùng role chạy (luật
  idempotent dưới) → `role` CHÍNH LÀ định danh trên mặt-tool-agent. `task_id` chỉ sống trong
  code (DB/SSE/FE/audit) — không bao giờ lên input/output tool hay prompt đánh thức (model chép
  id = cơ hội hallucinate; role là enum đóng, không sai được).
- **Idempotent bắt buộc**: main retry/quên gọi trùng (cùng conversation + role đang running) →
  KHÔNG spawn con thứ hai — trả `{created:false, role, status:"running", hint:"đang chạy —
  xem orch_status"}`. Không có luật này: compaction + retry = 2 con Credit chạy đè nhau.
- Task không phụ thuộc nhau: main cứ dispatch liên tiếp → các sub chạy song song tự nhiên.
- Sub bị giới hạn: max_turns + budget + timeout (mặc định idle 120s).

### 4.2 Báo xong — event đánh thức, một lượt một lúc
```
SUB kết thúc (xong | lỗi | timeout | bị hủy)
  → vỏ ghi task.result (DB) + đẩy EVENT vào hàng đợi của phòng
  → phòng rảnh?  → đánh thức MAIN: prompt = "sự kiện: SUB <role> [kết cục], kết quả: ..., bảng việc: ..."
     phòng bận?  → event xếp hàng, xử ngay khi lượt hiện tại xong
```
- **1 lượt/phòng**: tại 1 thời điểm chỉ 1 lượt main chạy. Mọi việc tới (user chat, sub báo,
  phiếu được quyết) đều vào MỘT hàng đợi, xử tuần tự. Không có 2 bản main đâm nhau.
- **Hàng đợi không nuốt lệnh người**: dedup (nếu có) chỉ áp cho event máy có khoá tự nhiên
  (`task_done` khoá theo role); `user_message` và `approval_decided` KHÔNG BAO GIỜ bị dedup/gộp —
  mỗi tin user, mỗi phiếu được quyết phải tới tay main đủ từng cái. Nuốt 1 phiếu = phòng kẹt
  vĩnh viễn (phiếu không nằm trong bảng việc — không có lưới đỡ thứ hai).
- **INVARIANT SỐNG CÒN — không có đường chết im lặng**: MỌI kết cục của sub (done / failed /
  timeout / user hủy) đều sinh ĐÚNG MỘT event báo main. Sub chết mà không event = phòng treo
  vĩnh viễn = cấm tuyệt đối. Timeout cũng là một kết cục, cũng phải báo.
- Main thức dậy làm gì (đợi thêm, tổng hợp, giao tiếp, dừng sớm) = quyết định của NÃO. Vỏ chỉ
  đưa: kết quả task vừa xong + bảng việc (task nào done/running/failed).

### 4.3 Tương tác user — chat, chen lời, hủy, chuyển ca
- Main rảnh → user gửi là chạy lượt mới ngay. Main đang trong lượt → tin nhắn xếp hàng
  (FE hiện trạng thái đang bận + nút hủy).
- **User chen lời khi sub đang chạy**: main (rảnh) nhận được ngay. Main muốn biết tình hình đội
  → gọi `orch_status`. Cư xử (trả lời tạm "em ghi nhận, chờ Credit xong sẽ gộp ý này" / chờ)
  là việc của não — vỏ không quy định.
- **Hủy per-agent**: user hủy được TỪNG con — hủy lượt main (interrupt) hoặc hủy 1 sub cụ thể.
  Hủy sub đi QUA CHÍNH vòng đời của sub: cancel đúng task đang chạy nó, mọi dọn dẹp + báo cáo
  nằm trong `finally` được shield khỏi cancel → kết cục `failed("user hủy")` vẫn sinh đúng 1
  event (invariant 4.2). CẤM cơ chế hủy ngoài băng (disconnect từ task khác = treo im lặng;
  đường báo cáo thứ hai = double-event).
- **Chuyển ca / xem sub đang làm gì**: sidebar nhiều conversation; click 1 sub thấy trace sống của nó.
- Hỏi-lại (clarify) và what-if KHÔNG phải cơ chế riêng: main thiếu thông tin thì hỏi trong chat;
  "thử lại với 4 tỷ" là một câu chat mới — main tự re-dispatch. UI what-if chỉ là nút/slider bắn câu chat.

### 4.4 Phanh — gate cưỡng chế ở tầng tool
Ẩn dụ: két tiền cần chìa giám đốc — dù nhân viên muốn mở, tin nên mở, hay bị dụ mở, tay vặn
cũng không ra tiền. Luật nằm ở CÁI KÉT, không nằm ở lời dặn.
```
SUB gọi tool gated (vd ops_disburse(loan_id, amount))
  → wrapper tính key = (conversation, action, payload_hash)     # hash trên payload CHUẨN HOÁ
  → tra theo key, trong 1 transaction, theo THỨ TỰ:
     1. có BIÊN NHẬN (đã thực thi trước)?  → trả lại biên nhận cũ — KHÔNG thực thi lại
     2. có phiếu APPROVED chưa dùng?       → claim atomic (UPDATE … WHERE status='approved')
                                            → thực thi → lưu biên nhận → phiếu thành used
     3. có phiếu PENDING?                  → trả "hành động này ĐANG chờ duyệt" — KHÔNG tạo mới
     4. chưa có gì?                        → tạo phiếu pending + vỏ TỰ sinh card approval + SSE
                                            → trả error 4-field:
            {code:"approval_required", message:"Giải ngân 5 tỷ cho DN X cần người duyệt",
             hint:"Đã gửi chờ duyệt — báo main và kết thúc lượt", retryable:false}
```
- **payload_hash chuẩn hoá** (định nghĩa 1 lần, dùng chung — lệch là phanh chết): JSON canonical
  của {action + các param nghiệp vụ}: sort key · số về dạng chuẩn (không `5e9` vs `5000000000`) ·
  bỏ field phi-nghiệp-vụ (ts, ghi chú). CÙNG MỘT HÀM ở cả lúc tạo phiếu lẫn lúc verify.
- **Vòng đời phiếu**: `pending → approved | rejected → used`. Chuyển approved→used bằng **atomic
  UPDATE…WHERE** — 1 phiếu duyệt thực thi được đúng 1 lần, kể cả 2 cú gọi trùng đồng thời.
- **Biên nhận chống-thực-thi-đôi**: kết quả thực thi lưu theo key; retry SAU thành công (sub mất
  kết quả rồi gọi lại) → trả biên nhận cũ, không chạy lại, không đẻ phiếu mới. Đây là
  idempotency-key của hành động irreversible — thiếu nó, phanh tự thành máy nhân đôi.
- **Phiếu khoá theo PHÒNG + payload**: lookup luôn lọc conversation — phiếu duyệt ca A không mở
  khoá ca B. Duyệt 1 tỷ mà gọi 5 tỷ → hash khác → phiếu mới. Không lách "xin duyệt A làm B".
- **Mặt model không có phiếu-id** (§15 ID-cho-code): error/hint/prompt nói theo HÀNH ĐỘNG
  ("giải ngân 5 tỷ cho DN X đã được DUYỆT — gọi lại tool để thực hiện"); khớp phiếu là việc của
  wrapper qua key. Admin quyết (`POST /approvals/{id}/decide` — id chỉ FE cầm) → event đánh thức
  main theo action → main giao lại Ops → Ops gọi lại tool → wrapper tự khớp.
- Tool nào gated = **whitelist config** (khởi điểm: `disburse`). Ranh gate theo Trụ 8: chỉ gate
  irreversible + ảnh-hưởng-ngoài; write reversible (ghi chú, tạo đơn nháp) → write-through,
  người sửa sau — gate thừa là friction giết tự trị.

## 5. Tool điều phối (vỏ tự viết)

| Tool | Làm gì | Tính chất then chốt |
|---|---|---|
| `orch_dispatch(role, title, input)` | giao việc, spawn sub nền, trả `{role, status}` ngay | **idempotent**: gọi trùng → trả existing theo role, không spawn đôi |
| `orch_status()` | bảng việc + trạng thái SỐNG các sub | **honest**: đọc registry sống, không tin cờ DB cũ; kèm `asOf` |
| `present(card)` | đẩy card có cấu trúc ra canvas (§6) | **affordance**: happy-path cũng hint bước kế |
| `calc(...)` | tính toán chung (tầng-0: agent cấm nhẩm) | cấp cho MỌI role |
| wrapper gated | phanh §4.4 bọc tool trong whitelist | **gate cưỡng chế ở tầng tool** — không cược prompt |

- Namespace: server `orch` (tool điều phối `orch_*`) · server `banking_<role>` (nghiệp vụ, từ lab)
  · server `common` cho tool chung mọi role (`calc`, `present`). Tên server chốt 1 lần Ở ĐÂY —
  `allowed_tools` khớp string tuyệt đối, lệch tên server là tool biến mất im lặng.
- **1 envelope + 1 error-shape cả hệ**: error luôn `{code, message, hint, retryable}` — hint là
  ACTION KẾ cụ thể. Annotations chuẩn MCP (`readOnlyHint`, `destructiveHint` cho disburse) để
  harness đặt policy máy-đọc.
- Audit: attribution qua ContextVar (conversation_id, actor role) set trước mỗi call; ghi
  append-only, fire-and-forget — audit lỗi không fail request chính.
- Quy trình ship tool điều phối: viết → checklist (bảng trên + checklist mount ở
  `docs/patterns/lab-joint.md` phụ lục) → 1 auditor đối kháng per-tool (FAIL kèm evidence GỌI
  THẬT) → fix → ≥1 ca thử then chốt (chỉ hiện thực đúng mới pass, đường tắt fail) → ship.
  Ca thử then chốt: *gọi dispatch 2 lần phải trả existing* · *gọi disburse chưa phiếu phải ra
  phiếu chứ không nổ*.

## 6. Canvas & card (present-tool)

- **Nguyên lý N5**: card sinh ra CHỈ từ cú gọi `present(card)` của agent (sub trình verdict,
  main trình tờ trình). Skill dạy agent gọi lúc nào; vỏ cấp tool + render.
- **Hai loại card — khác nhau DUY NHẤT ở chuỗi tool trả về cho agent:**
  - *Hiển thị* (verdict, case-file, tờ trình): vỏ lưu + bắn SSE, tool trả "card đã render,
    tiếp tục" → agent chạy tiếp.
  - *Cần người bấm* (approval panel): card `approval` do VỎ TỰ SINH khi wrapper phanh tạo phiếu
    (§4.4) — agent KHÔNG gọi present cho phanh; người bấm → event đánh thức (cùng đường §4.4).
- **Card types** (generic, mọi role dùng chung — FE render theo `type`):
  `case_file` · `metric` (bảng chỉ số kèm ngưỡng + nguồn) · `checklist` · `options` (so gói) ·
  `timeline` · `document` (tờ trình, export được) · `approval` (chỉ vỏ sinh). Nội dung agent bơm,
  vỏ chỉ validate shape tối thiểu (`type` + `title` + `items`).
- **Mọi id trên card do VỎ inject** (card id, phiếu id cho FE) — model không bao giờ phải bơm id
  nó không có (model chỉ có thể bịa — §15). Tham chiếu chéo trên card (`source`, `sources`) dùng
  TÊN tool/role, không dùng id.
- Mọi con số trên card nên kèm `source` (tool nào trả) — citation chip trên UI trỏ về tool-call gốc.

## 7. Contract ghép LAB → SYSTEM

**Bốn interface khoá cứng — vỏ mù mọi thứ phía sau:**
1. **Tool** = hàm thuần `fn(conn, **kwargs) -> dict` — conn = **Postgres từ pool** do VỎ cấp (D-21,
   cách A2). Data nghiệp vụ nằm CÙNG Postgres với render+audit (không SQLite). Tool viết **SQL
   PORTABLE** (param bind, không cú pháp SQLite-riêng); tool+skill là việc LAB, vỏ không đụng logic.
2. **Schema** = entry `{tên: {"mô tả": str, "params": {tên: {type, required?, default?, values?, desc}}}}`
   (+ annotations). Đây là docs duy nhất agent thấy.
3. **Skill** = `SKILL.md` text thô → system_prompt của sub. Không parse.
4. **Output** = dict tự do — vỏ chuyển nguyên xuống agent, không đọc bên trong.

**Điểm ghép duy nhất — `mount_role(role)`:**
```
đọc roles/<role>/  →  {SKILL.md, functions.py, SCHEMAS, ANNOTATIONS}
  → wrap từng fn:  lấy conn PG từ pool mỗi call (D-21 A2; đọc mặc định,
                   ghi cho tool gated như disburse)
                   + try/except → error 4-field (db_error/bad_type/tool_error)
                   + wrapper gated nếu tên trong whitelist phanh
  → build MCP server in-process "banking_<role>"  →  allowed_tools cho sub role đó
```
- **Swap tool thật = 3 thao tác**: thả file functions (SQL portable — D-21) + dán cụm
  SCHEMAS/REGISTRY + xoá stub. `mount_role` và toàn bộ orchestrator/FE KHÔNG đổi.
- Schema build bằng full JSON Schema (required/enum/default nằm TRONG schema) — không dùng
  shorthand ép mọi param thành required (vỡ tool có param optional).
- **Hiện trạng theo thời điểm — kiểm nguồn D-08 lúc kickoff**: role nào lab ĐÃ đẻ thật
  (functions + SKILL) → mount thật ngay (test đường ghép sớm); role còn lại = stub cùng
  contract, trả dữ liệu giả đúng shape, swap sau. Không hardcode danh sách role thật vào spec.
- **Tri thức domain**: hiện nằm trọn trong SKILL (data ít, cô đọng — đủ). Đường mở khi phình:
  wiki markdown trên disk (mục lục inject vào prompt + tool đọc-trang) — là 1 tool retrieval
  lab đẻ, vỏ không dựng hạ tầng RAG. Chọn cách lấy dữ liệu theo bài (time/accuracy/cost):
  có id rõ → query DB thẳng · cô đọng → skill/wiki · triệu bản ghi không cấu trúc → mới tính vector.
- Data nghiệp vụ (D-21 — trong Postgres, cùng kho render+audit): `customers · businesses · loans ·
  collaterals · cic_records · assumptions` (+ legal tables). Con số nghiệp vụ = bảng `assumptions`,
  swap được — không hardcode. Schema + seed-values dựng lại từ nguồn LAB (D-08), KHÔNG mount `.db`.

## 8. Session & sự cố

- **Continuity = SDK session trên disk.** Main resume từ transcript (cwd ổn định per conversation).
  DB KHÔNG phải nguồn resume.
- **DB (Postgres) = kho render cho FE**: hội thoại, bảng việc, card, phiếu, audit — để vẽ UI
  và load lại khi mở ca.
- **Server sập = tạm ngưng, không phải quên.** Việc đang chạy đứt → error cho user. Sống lại:
  conversation + session id giữ nguyên → user chat tiếp là resume bình thường, chỉ việc bị đứt
  phải làm lại. KHÔNG build máy cứu-ca-đang-chạy.
- **Không cờ giả sau restart**: trạng thái `running` chỉ tin registry sống trong process; lúc
  boot, task nào DB còn `running` → đánh `failed ("server restart")` để UI không treo.

## 9. SSE (FE ↔ BE realtime)

| event | payload | UI dùng |
|---|---|---|
| `conversation.status` | {status: running/waiting_approval/done/failed} | badge sidebar/chat |
| `task.created` / `task.status` | {task} | bảng việc, live map, node sub |
| `chat.delta` | {chunk} | stream chữ main trong chat |
| `card` | {card} (từ present) | canvas render |
| `toolcall` | {id, task_id, tool, summary, cost} | trace timeline + cost meter + (3D view sau) |
| `thinking` | {task_id, text} | trace: suy nghĩ model (live-only, KHÔNG persist — F1/T4-2) |
| `approval.pending` / `approval.decided` | {phiếu} | badge chờ duyệt, approval queue, resume |

- Reconnect: FE gọi `GET /conversations/{id}` load full state từ DB rồi nghe SSE tiếp.
  KHÔNG có replay-cursor/outbox.
- Header SSE production: `X-Accel-Buffering: no` (thiếu là chết im sau nginx) + heartbeat.

## 10. Data model (Postgres — 1 kho: NGHIỆP VỤ + render + audit — D-21)

```sql
-- ── VẬN HÀNH / render / audit (BE ghi lúc chạy) ──
users(id, username, pass_hash, role)                    -- 2 account: user(RM) / admin
conversations(id, user_id, title, status, sdk_session_id, created_at)
messages(id, conv_id, ts, sender, content, meta jsonb)
tasks(id, conv_id, role, title, status, input jsonb, result jsonb,
      queued_at, started_at, ended_at, cost jsonb)
cards(id, conv_id, task_id, type, data jsonb, ts)       -- canvas reload
tool_calls(id, task_id, ts, actor, tool, input jsonb, output jsonb, cost jsonb)  -- APPEND-ONLY
approvals(id, conv_id, task_id, action, payload jsonb, payload_hash,
          status,                 -- pending | approved | rejected | used (§4.4)
          decided_by, decided_at, reason,
          used_at, receipt jsonb) -- biên nhận thực thi — chống thực-thi-đôi (§4.4)

-- ── NGHIỆP VỤ (tool LAB đọc; disburse ghi loans.status — D-21; schema+seed dựng từ nguồn LAB) ──
customers(id, full_name, occupation, monthly_income, region, ...)
businesses(id, name, sector, annual_revenue, ...)
loans(id, owner_id, amount, monthly_payment, outstanding, status, ...)   -- status: active|disbursed…
collaterals(id, owner_id, type, appraised_value, docs_status, ...)
cic_records(owner_id, cic_group, history_note, ...)
assumptions(key, value)                                 -- con số nghiệp vụ, swap được
-- + legal tables (legal_requirements, owner_documents, restricted_purposes, …) khi mount legal
```

## 11. API

| Method | Path | Vai | Ghi chú |
|---|---|---|---|
| POST | `/api/auth/login` | all | JWT, 2 account seed |
| GET/POST | `/api/conversations` | user | list / tạo ca |
| POST | `/api/conversations/{id}/chat` | user | lượt user → main (bận thì xếp hàng) |
| GET | `/api/conversations/{id}` | user | full state (messages+tasks+cards+approvals) |
| GET | `/api/conversations/{id}/sse` | all | stream §9 |
| POST | `/api/conversations/{id}/interrupt` | user | hủy main hoặc 1 task (body: target) |
| GET | `/api/approvals?status=pending` | admin | hàng chờ duyệt |
| POST | `/api/approvals/{id}/decide` | admin | duyệt/từ chối → event resume |
| GET | `/api/audit?filters` | admin | tool_calls search |
| POST | `/api/compare/{id}` | admin | (XỬ SAU §13) trigger 2 bản chạy cùng câu |

- **Success-envelope REST**: trả RESOURCE TRẦN (row/list đúng shape DB serialize — cùng
  serializer với SSE §9, một codepath render FE); CHỈ error mới có envelope, và là 4-field
  `{code, message, hint, retryable}` thống nhất toàn hệ (§5). Không bọc `{success, data}`.

## 12. Tech stack

- **Backend**: Python 3.11 + FastAPI + uvicorn (1 worker) · claude-agent-sdk (ClaudeSDKClient) ·
  Postgres 15 (SQLAlchemy + Alembic). **Không Redis** — hàng đợi phòng + SSE fanout in-process
  (N4: 1 worker demo, bớt moving part).
- **Đa provider / model routing**: `providers.yaml` — main = model mạnh (sonnet), sub = model rẻ
  (haiku), fallback nhiều provider qua env per-session (base-url + key). Không hardcode model.
- **Frontend**: React + Vite + TS. Token màu: nền `#1a1917`, cam `#d97757`, bộ pass/fail/warn/run.
  2 màn: **Workspace** (sidebar | chat | canvas) + **Control Tower** (live map · traces ·
  approval queue · audit · compare-certify) — chi tiết element từng màn: theo design/mock
  người cấp (D-13); chưa có → build theo tính năng §6/§9/§13 + tokens dưới.
- **Deploy**: docker compose (api, web, postgres) — on-premise 1 lệnh.

## 13. Ánh xạ deliverable đề

| Đề đòi | Đáp bằng |
|---|---|
| 1. demo ≥2-3 chuyên gia phối hợp 1 request phức tạp | ca "DN X vay 5 tỷ mở xưởng, thế chấp nhà xưởng 8 tỷ" |
| 2. planner phân rã → executor | main + orch_dispatch + event (§4) |
| 3. tool-use thật, hành động cụ thể | toolpack lab + `disburse` gated (§4.4) |
| 4. dashboard traces/status/decisions/flows | Control Tower + SSE toolcall (3D view dự kiến) |
| 5. so sánh single-agent vs multi-agent | **XỬ SAU** khi hệ chính xong: endpoint trigger 2 bản chạy cùng câu (1 LLM trần vs cả đội), render 2 cột, người đánh giá. Không chặn kiến trúc. |

## 14. KHÔNG LÀM (chống phình)

Marketplace · billing · multi-team · mobile · i18n ngoài VI · WebSocket · phân quyền >2 role ·
**debounce cửa chat** · **outbox/replay-cursor** · **Redis** · **máy clone what-if** ·
**máy cứu-ca-qua-restart** · **train MAIN ở lab** · **hạ tầng vector/RAG khi skill còn đủ** ·
gate cho write reversible.

## 15. RULE CẦN TRÁNH (anti-pattern riêng của hệ này)

| Anti-pattern | Vì sao chết | Luật thay thế |
|---|---|---|
| Parse text agent ra card | đoán mò, vỡ theo format | card CHỈ từ present-tool (N5) |
| Tin lời dặn thay phanh | model quên/bị dụ/injection | gate cưỡng chế tầng tool (N2, §4.4) |
| Dispatch không idempotent | retry → 2 sub chạy đè | trùng → trả existing (§4.1) |
| Sub kết thúc không event | phòng treo vĩnh viễn | MỌI kết cục sinh đúng 1 event (§4.2) |
| Cờ `running` giả sau restart | UI treo, main tưởng còn con chạy | tin registry sống; boot đánh failed task mồ côi (§8) |
| Vỏ ép luật "đợi đủ N con" | cướp quyết định của não | vỏ đưa bảng việc, não quyết (N1) |
| Envelope cứng ép mọi câu trả lời | gò model, vỡ khi lệch schema | text tự do + card opt-in (N5) |
| Dựng vector/wiki khi skill đủ | hạ tầng thừa, thêm điểm hỏng | chọn cách lấy dữ liệu theo bài (§7) |
| 2 nguồn sự thật contract tool | function tay + manifest tay → drift | 1 nguồn: SCHEMAS đi cùng functions (§7) |
| Số không nguồn trong card/trả lời | "bịa" — chết điểm bank | mọi số kèm `source` tool-call (§6) |
| ID kỹ thuật lên mặt-tool-agent | model chép id = hallucinate/gõ sai; id là dead weight khi role đã là khoá | TÊN cho model (role/enum đóng), ID cho code — DB/SSE/FE giữ id (§4.1) |
| Đòi model bơm ID nó chưa từng được phát | model chỉ có thể BỊA id từ hư không — tệ hơn cả chép nhầm | vỏ inject mọi id; tham chiếu bằng tên tool/role (§6) |
| Retry-thành-xin-duyệt-lại | phiếu đã used + sub gọi lại = phiếu mới = admin duyệt lần 2 = thực thi ĐÔI | biên nhận theo (conv, action, payload_hash) — trả kết quả cũ (§4.4) |
| Single-use không atomic | check→chạy→mark có `await` xen giữa = 1 phiếu chạy 2 lần | claim bằng atomic UPDATE…WHERE rồi mới thực thi (§4.4) |
| Param lạ bị nuốt im lặng | gõ `loan_amount` thay `loan_amount_vnd` → default 0 → verdict sai đầy tự tin | arg ngoài schema → error 4-field `bad_param`, không lọc im (§7) |
| Idempotent chỉ cho đường "đẹp" | dispatch có chống-đôi mà tạo phiếu/card thì không → retry = spam phiếu, card trùng | MỌI đường ghi gọi-lặp-được đều idempotent (§4.1, §4.4, §6) |
| Hủy ngoài băng | disconnect cross-task treo im lặng; report bị cancel = mất event = phòng treo | hủy qua chính vòng đời sub; report trong `finally` có shield (§4.3) |

## 16. Build order (gate mỗi bước = chạy ca "DN X vay 5 tỷ" end-to-end tới mức của bước)

1. **Skeleton**: compose + FastAPI + Postgres + auth + `mount_role` (credit+legal THẬT · products+ops stub — D-17/D-18) +
   tool điều phối (dispatch/status/present/calc + wrapper gated) qua checklist+auditor §5.
2. **Vòng lõi**: chat → main → dispatch credit → sub chạy → event → main tổng hợp → SSE →
   FE chat thô. *(Gate: hỏi "lương 30tr, đang trả nợ 8tr/tháng — DSCR?" → DSCR tính bằng tool, có nguồn.)*
3. **Canvas + đội đủ**: present-tool + 7 card types + 4 sub song song + bảng việc + live map.
4. **Phanh end-to-end**: disburse gated → phiếu → admin duyệt → resume + approval queue + audit view.
   *(Gate: "giải ngân luôn nhé" khi chưa duyệt phải bị két chặn.)*
5. **Điều khiển**: interrupt per-agent + switch ca + trace/cost meter + trạng thái đầy đủ
   (empty/streaming/waiting/error/abstain).
6. **Polish + demo**: UI theo mock + demo-script + seed-reset (+ compare endpoint nếu kịp).

<!-- ═══════════ setup thêm (scaffold Bước 1 — bù section template thiếu, thân trên giữ nguyên) ═══════════ -->

## Meta (bổ sung theo SPEC template)

- **App:** Digital Expert Guild — đội chuyên gia số ngân hàng SHB (đề #132 VAIC 2026).
- **Cho ai:** multi-user 2 role — `user` (RM) / `admin` (quản lý·compliance). Giám khảo dùng 1 trong 2.
- **Chốt:** 2026-07-17 (spec v2.0 sau audit đối kháng 3 vòng).
- **Design baseline:** mock tại `design/` (D-14) — THAM KHẢO look-and-feel (D-13). Tokens
  ĐẦY ĐỦ ở `design/workspace/shared.jsx` (object `T`: nền/panel/border/chữ + accent
  `#d97757` + bộ run/pass/fail/warn/main + font Be Vietnam Pro/mono) → FE port thành
  `frontend/src/tokens.css` ở dispatch đầu.
- **Screens:** 2 màn (§12): Workspace (sidebar ca | chat | canvas card) + Control Tower
  (live map · traces · approval queue · audit · compare-certify). Element từng màn: build theo
  TÍNH NĂNG các § của spec (§6 card, §9 SSE, §13 deliverable) — không tự chế thêm màn ngoài 2
  màn này; look-and-feel theo `design/` (Workspace mock + lobby 3D + Login/Tower/Approval
  trong `design/Digital Expert Guild.dc.html`).
