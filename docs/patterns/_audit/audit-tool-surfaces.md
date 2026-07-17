# AUDIT ĐỐI KHÁNG — mặt-tool-agent hệ #132 (per-tool × per-trụ)

> Auditor: đối kháng, thước đo `craft/01-tool.md` (10 trụ). Ngày 2026-07-17.
> Phạm vi: `spec/CORE-SPEC-132.md` + `docs/patterns/{claude-sdk, lab-joint, canvas-present}.md`
> **+ `multi-agent.md`** (bổ sung bắt buộc — orch_dispatch/orch_status/wake-prompt viết kỹ nhất ở đó,
> `result_summary 3000` nằm ở đó, không audit là hổng nửa mặt tool điều phối).
> Luật đối chiếu chính: **TÊN cho MODEL (enum đóng), ID cho CODE (DB/SSE/FE)** — spec §15 dòng 298.
> Chỉ ghi FAIL có evidence file:dòng. Không sửa, không khen.

---

## 1. BẢNG TỔNG — tool × trụ

Surface = mọi thứ model nhìn thấy: name/description/input_schema/return/hint/error/wake-prompt.

| Surface | T1 gộp | T2 ngữ pháp | T3 schema | T4 lean/bounded | T5 honest | T6 affordance | T7 idempotent | T8 harness |
|---|---|---|---|---|---|---|---|---|
| `orch_dispatch` | PASS | **FAIL** (V4,V10) | **FAIL** (V9,L1,L2) | PASS | PASS | PASS | **FAIL** (V4) | **FAIL** (V3) |
| `orch_status` | PASS | **FAIL** (V5) | N-A (0 param) | **FAIL** (V5) | PASS (spec text) | N-A (chưa định nghĩa) | PASS | **FAIL** (V3) |
| `present` | PASS | **FAIL** (V1,V2) | **FAIL** (V8) | **FAIL** (N1) | PASS | **FAIL nhẹ** (V1) | **FAIL** (N4) | PASS |
| `calc` | N-A | N-A | **FAIL** (V7) | N-A | N-A | N-A | N-A | **FAIL** (N6) |
| wrapper gated / `ops_disburse` | PASS | **FAIL** (V1) | N-A | **FAIL** (N5) | PASS | PASS | **FAIL** (N3,N4) | **FAIL** (V14,V3) |
| mount_role error-envelope (mặt chung mọi tool lab) | N-A | PASS | N-A | PASS | **FAIL** (N2) | **FAIL** (L4, db_error) | PASS (conn tươi) | **FAIL** (V3) |
| schema builder (×2 bản) | N-A | N-A | **FAIL** (V13) | N-A | N-A | N-A | N-A | **FAIL** (V12) |
| `credit_assess` | PASS | PASS | PASS (L6 nhẹ) | N-A (fn lab) | N-A | N-A | N-A | PASS |
| `cust_search` | PASS | **FAIL** (V11) | PASS | **FAIL** (V11) | N-A | N-A | N-A | PASS |
| `legal_check_documents` (stub) | PASS | PASS | PASS | PASS | **FAIL nhẹ** (L5) | PASS | PASS | PASS |
| wake-prompt (`build_event_prompt`) | N-A | PASS | N-A | **FAIL** (V6) | **FAIL** (V6) | PASS | N-A | N-A |

Đếm: **NẶNG 6 · VỪA 14 · NHẸ 7**.

---

## 2. FAIL NẶNG (6)

### N1 — Đòi ID chưa phát: schema card bắt model điền id mà chỉ vỏ sinh ra và KHÔNG BAO GIỜ trả cho model
- **Evidence 1**: `canvas-present.md:164` — bảng schema card `approval`:
  > `items: [{label, value}]` + `approval_id`, `action`, `options: [{id, label}]` … "main cũng gọi được khi chủ động xin người quyết"
- **Evidence 2**: `canvas-present.md:89` — `approval_id` chỉ sinh BÊN TRONG present, SAU khi card đã được agent bơm:
  > `phieu_id = await _tao_phieu_tu_card(ctx, card)          # §6`
- **Evidence 3**: `canvas-present.md:163` — card `document`:
  > `items: [{section, content}]` + `sources: [card_id/tool]`
  trong khi return của present (`canvas-present.md:90-94`) **không có id nào**: `{"status": "ok", "message": "card ... đã render ..."}` — main chưa từng thấy `card_id` của bất kỳ card nào.
- **Vì sao fail (Trụ 4 + tiên đề gốc)**: model chỉ biết cái trong context. `approval_id` chưa tồn tại lúc main gọi present type=approval; `card_id` chưa bao giờ được phát cho main. Schema đòi → model **chỉ có thể bịa**. Đây là bản NẶNG HƠN của lỗi `task_id`: task_id ít nhất tồn tại thật; ở đây id còn chưa/không hề đến tay model.
- **Sửa 1 câu**: vỏ tự inject `approval_id` sau khi tạo phiếu (agent không bơm field này), `sources` của document đổi thành tên-tool/tên-role (TÊN cho model), bỏ `card_id` khỏi mọi shape agent bơm.

### N2 — Param-nuốt im lặng: mount_role lọc arg lạ theo signature rồi chạy tiếp như không
- **Evidence**: `lab-joint.md:213`
  > `ok = {k: v for k, v in args.items() if k in inspect.signature(fn).parameters}`
- **Vì sao fail (Trụ 5)**: model gõ sai tên param (vd `loan_amount` thay `loan_amount_vnd`) → arg bị lọc **im lặng** → fn chạy với `default 0` (`lab-joint.md:71`) → thẩm định 0 đồng, verdict sai đầy tự tin — đúng bệnh "sai trơn, không crash". Chính `craft/01-tool.md:294` đã đặt tên bệnh: "schema validate mọi call (**chống param-nuốt**)" — snippet này tái nhiễm.
- **Sửa 1 câu**: arg không thuộc signature → trả `bad_param` 4-field liệt kê param lạ + param hợp lệ, KHÔNG chạy fn.

### N3 — Retry-sau-thành-công của `disburse` = vòng xin-duyệt-mới → nguy cơ GIẢI NGÂN ĐÔI
- **Evidence**: `canvas-present.md:353-354`
  > `receipt = await tool_fn(**kwargs)             # có phiếu khớp → chạy thật`
  > `await db.approvals.mark_used(phieu.id)        # single-use`
  và toàn bộ wrapper (`lab-joint.md:255-269`, `canvas-present.md:330-356`) **không nhận `idempotency_key`, không lưu/trả lại biên nhận cũ theo payload_hash đã thực thi**.
- **Vì sao fail (Trụ 7)**: sub thực thi xong nhưng mất kết quả (compaction/timeout giữa lượt) → gọi lại y nguyên → phiếu đã `used` → wrapper coi như "chưa duyệt" → tạo phiếu pending MỚI → main xin admin duyệt lần 2 → admin (thấy yêu cầu giống hệt) duyệt → **tiền đi 2 lần**. Craft Trụ 7 dòng 159: "Write nguy hiểm lặp … cùng key → trả kết quả cũ, không thực thi lại" — chính xác ca này, chưa có.
- **Sửa 1 câu**: wrapper tra `payload_hash` đã-executed trước khi tra phiếu — trùng → trả lại biên nhận cũ kèm `alreadyExecuted: true`, không tạo phiếu mới.

### N4 — Sinh phiếu pending KHÔNG idempotent: retry → phiếu + card trùng chồng chất
- **Evidence**: `canvas-present.md:335-340` — chỉ tra phiếu APPROVED, không tra pending:
  > `phieu = await db.approvals.find(action=action, payload_hash=h, status="approved", used=False)`
  > `if phieu is None:` → `insert(... status="pending")` vô điều kiện.
  Tương tự `lab-joint.md:257-259` (`has_approved` → `create_pending`). `present type=approval` (`canvas-present.md:89`) cũng tạo phiếu mỗi lần gọi, không dedupe.
- **Vì sao fail (Trụ 7)**: sub retry cú gọi gated (bệnh mà spec §4.1 đã thừa nhận cho dispatch: "compaction + retry") → N phiếu pending + N card approval cho CÙNG một việc; admin duyệt 1, N-1 phiếu treo, main bị đánh thức lệch. Spec §15 dòng 290 đúc luật "Dispatch không idempotent → trùng trả existing" nhưng **quên áp cho cửa sinh phiếu** — cùng hạng lỗi, khác cửa.
- **Sửa 1 câu**: tra `(action, payload_hash, status="pending")` trước khi insert — có rồi thì trả lại đúng error `approval_required` trỏ phiếu đang chờ, không sinh phiếu/card thứ hai.

### N5 — `phiếu #17` (id kỹ thuật) lên mặt model — vi phạm CHÍNH luật §15 spec vừa đúc
- **Evidence 1**: `spec/CORE-SPEC-132.md:122-123` (error surface của tool gated):
  > `hint:"Đã tạo phiếu #17 — báo main kết thúc lượt, chờ duyệt"`
- **Evidence 2**: `spec/CORE-SPEC-132.md:126` + `multi-agent.md:114` (wake-prompt):
  > `return (f"Phiếu #{data['phieu_id']} ({data['action']}) đã được ...`
  và `multi-agent.md:597-598`: *"Phiếu #17 (disburse, 5 tỷ, loan L-042) đã được DUYỆT"*; `canvas-present.md:92,351`.
- **Vì sao fail (Trụ 4 + spec §15:298)**: model không cần phiếu-id để làm BẤT KỲ việc gì — đường resume khớp bằng `payload_hash`, model không bao giờ nhập phiếu-id vào tool nào. Id là dead weight trên mặt model: chép vào chat cho user là cơ hội hallucinate/gõ sai y hệt `task_id` đã bị bắt và sửa. `action` (+ tóm tắt payload) mới là TÊN; trong wake-prompt đã có sẵn cả hai. Spec tự vi phạm luật mình đúc ở §15 dòng 298 ngay tại §4.4.
- **Sửa 1 câu**: mặt model chỉ nói `action` + tóm tắt payload ("phiếu giải ngân 5 tỷ cho L-042 ĐÃ DUYỆT"); `phieu_id` ở lại DB/SSE/FE như task_id.

### N6 — Một tool hai hộ khẩu: `present`/`calc` khai 2 server khác nhau ở 2 doc (đã bị audit-bloat #5 bắt — CHƯA SỬA, ghi lại vì còn nguyên trong file + thêm 1 góc mới)
- **Evidence**: `claude-sdk.md:318-319` (`ORCH_SERVER ... tools=[orch_dispatch, orch_status, present, calc]`) + `claude-sdk.md:165-167,172` (`"mcp__orch__present", "mcp__orch__calc"`) ĐỐI ĐẦU `lab-joint.md:399-401` (`COMMON_SERVER`, `"mcp__common__calc", "mcp__common__present"`) + `lab-joint.md:421`.
- **Góc MỚI chưa ai ghi**: `claude-sdk.md:171` — sub được mount nguyên `ORCH_SERVER`:
  > `mcp_servers={"banking_credit": role.server, "orch": ORCH_SERVER}`
  tức server chứa `orch_dispatch`/`orch_status` nằm trong process của SUB, chỉ chặn bằng allowed_tools — trong khi `lab-joint.md:422` tuyên "CẤM — sub không được giao việc". Mount thừa = thuế + ranh quyền mỏng hơn tuyên bố.
- **Vì sao fail (Trụ 2/8)**: tên đầy đủ `mcp__<server>__<tool>` là PHẦN của contract, whitelist khớp string tuyệt đối — 2 doc tự chứa khai 2 tên → build theo doc nào cũng vỡ doc kia, tool "biến mất im lặng" (đúng bẫy claude-sdk.md:391 tự cảnh báo).
- **Sửa 1 câu**: chốt `common` (theo lab-joint), sửa claude-sdk §2/§4; sub chỉ mount `banking_<role>` + `common`, không mount `orch`.

---

## 3. FAIL VỪA (14)

### V1 — `present` happy-path phá ngữ pháp chung: `{status, message}` không có `hint`, và 2 cửa phanh trả 2 shape
- **Evidence**: `canvas-present.md:90-94`
  > `return {"status": "waiting", "message": f"STOP — phiếu #{phieu_id} ...\"}` / `return {"status": "ok", "message": "card ... — tiếp tục việc."}`
  Trong khi error của chính nó (dòng 72-74) là 4-field `{code,message,hint,retryable}`, dispatch trả `{role,status,hint}`, và spec §5:139 hứa "happy-path cũng hint bước kế".
- **Vì sao fail (Trụ 2/6)**: cùng sự kiện "chờ duyệt" mà cửa present trả `{status:"waiting",message}` còn cửa wrapper gated trả `{code:"approval_required",...,hint}` — model phải học 2 grammar cho 1 nghĩa; field `status` ở đây (ok/waiting) lại đồng âm khác nghĩa với `status` của dispatch (running) — bẫy parse-nhầm.
- **Sửa 1 câu**: present trả cùng grammar: happy `{rendered:true, hint:"<bước kế>"}`, approval trả đúng error 4-field `approval_required` như wrapper.

### V2 — `retryable` mâu thuẫn định nghĩa: cùng loại lỗi tham-số-sai, chỗ True chỗ False
- **Evidence**: `canvas-present.md:74` — `"hint": "sửa shape rồi gọi lại present", "retryable": True` ĐỐI ĐẦU `lab-joint.md:221` — bad_type: `"retryable": False`.
- **Vì sao fail (Trụ 2/6)**: craft:144 định nghĩa retryable = "retry Y NGUYÊN có ích không" — bad shape retry y nguyên chắc chắn fail → phải False; hai tool dạy model 2 nghĩa khác nhau của cùng 1 field.
- **Sửa 1 câu**: chốt định nghĩa craft, `bad_card.retryable=false` (sửa-rồi-gọi-lại ≠ retry).

### V3 — ANNOTATIONS mồ côi: contract khai, điểm mount vứt
- **Evidence**: `lab-joint.md:85-89` khai `ANNOTATIONS = {...readOnlyHint...}`; spec §5:145-146 đòi "Annotations chuẩn MCP (readOnlyHint, destructiveHint cho disburse)"; NHƯNG cả hai điểm mount đều không truyền: `lab-joint.md:234-235` và `claude-sdk.md:371-372` — `tool(name=..., description=..., input_schema=...)` không có annotations; `@tool` của orch (`claude-sdk.md:296-311`) cũng không.
- **Vì sao fail (Trụ 8)**: harness không còn gì máy-đọc để auto-approve read-only / gate destructive — quay lại đúng anti-pattern "đoán từ description" mà craft:176 cấm; ANNOTATIONS thành trang trí = 2 nguồn sự thật (khai một đằng, chạy một nẻo).
- **Sửa 1 câu**: mount và annotations sinh từ CÙNG vòng lặp (như luật allowed_tools ở claude-sdk.md:391); nếu SDK `@tool` không nhận annotations thì phải ghi rõ đường thay thế (policy map từ ANNOTATIONS trong vỏ), không để rơi im.

### V4 — Envelope `orch_dispatch` 3 chỗ 3 shape; case-đinh đòi `existing` mà pattern không trả
- **Evidence**: happy `{role, status:"running", hint}` không có `created` (`multi-agent.md:263-265`, spec:75); trùng `{created:false, role, status, hint}` (`multi-agent.md:255-256`, spec:83); spec §5:137 lại ghi gọn "trả `{role, status}`"; và `multi-agent.md:341-342` tuyên case đinh: *"lần 2 PHẢI trả `created:false` + `existing`"* — nhưng pattern dòng 255-256 **không có field `existing`**.
- **Vì sao fail (Trụ 2/7)**: field xuất hiện-rồi-biến-mất giữa 2 kết cục của cùng tool = model không học được pattern; craft:155-157 mẫu chuẩn là trả `existing` object để agent tiếp tục được — case đinh của chính doc sẽ FAIL khi auditor gọi thật.
- **Sửa 1 câu**: khoá 1 envelope: happy `{created:true, role, status, hint}` / trùng `{created:false, role, status, hint}` (+ `title` việc đang chạy làm "existing" mức TÊN), sửa cả 3 chỗ.

### V5 — `orch_status` không có contract return và không có trần
- **Evidence**: spec §5:138 chỉ 1 dòng "bảng việc + trạng thái SỐNG các sub"; `multi-agent.md:468-470` chỉ nói cách đọc (registry + asOf); **không file nào định nghĩa shape output, trần count/bytes, truncated** (audit-bloat #4 đã ghi thiếu-pattern; đây bổ thêm góc Trụ 4).
- **Vì sao fail (Trụ 2/4)**: tool trả "bảng" mà không envelope list chuẩn `{items,count,truncated}` + không trần → builder tự chế, ca what-if re-dispatch nhiều task là dump không giới hạn vào context main.
- **Sửa 1 câu**: khoá shape `{tasks:[{role,status,title,ago}], count, asOf, truncated:false}` — mức TÊN (role), không task_id, trần server theo count.

### V6 — `result_summary` cắt 3000 chars IM LẶNG, main không có đường lấy bản đầy đủ
- **Evidence**: `multi-agent.md:454`
  > `"result_summary": summarize(result, max_chars=3000),  # bản đầy đủ ở DB + card`
  Wake-prompt (`multi-agent.md:110-112`) đưa thẳng summary, không cờ cắt; main không có tool nào đọc lại result đầy đủ (orch_status cũng không trả result).
- **Vì sao fail (Trụ 4/5)**: cắt-im-lặng đúng anti-pattern craft:90 — main tưởng đã thấy hết verdict, tổng hợp trên bản cụt đầy tự tin; "bản đầy đủ ở DB" là chỗ CODE thấy, model không thấy.
- **Sửa 1 câu**: summary kèm cờ tường minh khi cắt ("[đã tóm tắt — chi tiết trên card <type> của <role>]") và skill sub bắt buộc present card TRƯỚC khi kết thúc để bản đầy đủ có mặt trên đường model-đọc-được.

### V7 — `calc` không có surface contract ở bất kỳ đâu
- **Evidence**: spec §5:140 nguyên văn signature là "`calc(...)`"; `lab-joint.md:385-391` chỉ nói nguyên lý "cấm nhẩm"; không file nào có description/input_schema/return của calc.
- **Vì sao fail (Trụ 3/8)**: tool "tầng-0 cấp cho MỌI role" mà contract 1-nguồn không có nguồn nào — builder tự chế mỗi người một kiểu (expression string? operands?), khác nhau giữa main/sub là vỡ ngữ pháp chung.
- **Sửa 1 câu**: viết contract calc 1 chỗ (đề xuất: `calc(expression: str)` → `{value, expression, asOf}` + error 4-field `bad_expression`), qua đủ checklist 10 trụ như spec §5 tự yêu cầu.

### V8 — `present` không có input_schema; 7 card types không hiện trong schema/description
- **Evidence**: `canvas-present.md:64-74` — 7 type chỉ tồn tại trong hằng `CARD_TYPES` server-side và trong error message sau-khi-fail; không đâu có input_schema của present (enum `type`, shape `items` per-type).
- **Vì sao fail (Trụ 3)**: "mọi quy ước phải HIỆN trong schema/output" (craft:20) — model chỉ học 7 type từ skill (lời dặn) hoặc từ lỗi `bad_card` (học bằng vấp); enum đóng có sẵn mà không đưa vào schema là bỏ không lợi thế chống-gọi-sai rẻ nhất.
- **Sửa 1 câu**: input_schema full JSON Schema với `type: {enum: [7 loại]}`, `title: string`, `items: array`, mô tả per-type 1 dòng trong description.

### V9 — enum `role` hardcode trong schema dispatch ĐỐI ĐẦU "role động quét thư mục"
- **Evidence**: `claude-sdk.md:304-305` — `"enum": ["credit", "legal", "products", "operations"]` (literal) ĐỐI ĐẦU spec §3:66-68 ("vỏ quét thư mục roles/ … không sửa code vỏ") + `multi-agent.md:249` (validate runtime bằng `discovered_roles()`) + `lab-joint.md:540` (bẫy "Hardcode danh sách 4 role").
- **Vì sao fail (Trụ 3/8 + mâu thuẫn nội bộ)**: enum đóng là ĐÚNG cho model, nhưng nguồn enum phải là `discovered_roles()` lúc build server — literal trong code là role thứ 5 phải sửa vỏ, và 2 doc mô tả 2 cơ chế validate khác nhau (schema-reject vs handler-error) cho cùng tool.
- **Sửa 1 câu**: enum sinh động từ quét `roles/` lúc mount, ghi chú rõ trong claude-sdk snippet.

### V10 — param `input` của dispatch: `dict` ở doc này, `string` ở doc kia
- **Evidence**: `multi-agent.md:247` — `async def orch_dispatch(role: str, title: str, input: dict)` ĐỐI ĐẦU `claude-sdk.md:307` — `"input": {"type": "string", ...}`.
- **Vì sao fail (Trụ 2/8)**: 2 nguồn khai 2 kiểu cho cùng param — build lệch là SDK reject hoặc sub nhận ngữ cảnh nát; thêm nữa "input" là tên mơ hồ (xem L1).
- **Sửa 1 câu**: chốt 1 kiểu (đề xuất `string` — brief tự do cho sub), sửa doc còn lại, đổi tên `task_brief`.

### V11 — `cust_search` là SEARCH nhưng hệ chỉ đúc 2 phong bì đơn+lỗi; `max: 20` không enforce cũng không hiển thị
- **Evidence**: `lab-joint.md:77-82` — cust_search có `limit {"default": 5, "max": 20}`; `lab-joint.md:121-124` — "LAB hiện dùng 2 phong bì chính": `{found,item,asOf,hint}` + lỗi 4-field — **không có phong bì list** `{items,count,total,truncated}`; `lab-joint.md:110` tuyên `max` "chỉ hiển thị, không enforce" nhưng `schema_to_input` (dòng 161-189) **không hề đọc khoá `max`** — không enforce mà cũng không hiển thị.
- **Vì sao fail (Trụ 2/4)**: search trả nhiều bản ghi mà không truncated/total = cắt-im-lặng ("agent tưởng thấy hết", craft:90); trần limit biến mất khỏi cả schema lẫn server = trần không của ai.
- **Sửa 1 câu**: thêm phong bì list chuẩn cho mọi tool search của LAB, `max` phải thành `maximum` trong JSON Schema + min() server-side.

### V12 — Hai bản converter schema drift: bản claude-sdk thiếu `enum`/`list[str]`
- **Evidence**: `claude-sdk.md:326` — `_JSON_TYPES = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}` ĐỐI ĐẦU grammar contract `lab-joint.md:104` (type gồm cả `"enum"`, `"list[str]"`) và bản converter đủ `lab-joint.md:157-171`.
- **Vì sao fail (Trụ 8)**: 2 nguồn sự thật cho cùng 1 converter — builder đọc claude-sdk (tự nhận "tự chứa", dòng 2-3) ship bản thiếu: tool LAB có param `list[str]` → schema ra `"string"` → model gửi string, fn nổ TypeError, kẹt vòng bad_type. Đúng anti-pattern spec §15:296 "2 nguồn sự thật contract tool".
- **Sửa 1 câu**: xoá bản builder trong claude-sdk.md, trỏ sang `schema_to_input` của lab-joint làm bản duy nhất.

### V13 — `default` chỉ ghép vào description, không vào JSON Schema — snippet tự vi phạm bẫy-table của CHÍNH file mình
- **Evidence**: `claude-sdk.md:345-347` / `lab-joint.md:180-181` — `desc = f"{desc} (default {meta['default']})"`, không set `p["default"]`; trong khi `claude-sdk.md:388` (bẫy-table cùng file) phán: *"`required`/`enum`/`default` chỉ ghi trong description | model đọc được nhưng validator không — hai nguồn sự thật lệch nhau. Tất cả nằm TRONG schema"*.
- **Vì sao fail (Trụ 3)**: đúng nguyên văn cái bẫy đã tự đặt tên — luật một đằng, snippet một nẻo trong cùng một file.
- **Sửa 1 câu**: `if meta.get("default") is not None: p["default"] = meta["default"]` (giữ cả dòng desc cũng được).

### V14 — Wrapper gated có 2 phiên bản mâu thuẫn: bản sinh card, bản không
- **Evidence**: `lab-joint.md:255-269` — `gated()` tạo phiếu + (comment) SSE approval.pending, **không tạo card** ĐỐI ĐẦU `canvas-present.md:341-348` — wrapper "2 mặt của 1 sự kiện: phiếu + card approval, sinh cùng lúc" + insert cards + 2 SSE.
- **Vì sao fail (Trụ 8 + mâu thuẫn nội bộ)**: build theo lab-joint là mất nguyên panel phanh trên canvas (admin không thấy gì để bấm ngoài Control Tower); 2 doc cùng tự nhận "tự chứa" mô tả 2 hành vi khác nhau cho cùng 1 wrapper.
- **Sửa 1 câu**: lab-joint §2.1 ghi rõ "bản rút gọn — bản đầy đủ (kèm sinh card) là canvas-present §6, code chung 1 hàm".

---

## 4. FAIL NHẸ (7)

| # | Evidence | Lỗi + trụ | Sửa 1 câu |
|---|---|---|---|
| L1 | `claude-sdk.md:307` `"input": {...}` ; spec:73 `orch_dispatch(role, title, input)` | Trụ 3 — tên param `input` mơ hồ (input của ai, chứa gì?); craft:66 "tên param nói rõ nhận gì" | đổi `task_brief` (ngữ cảnh + yêu cầu cho sub) |
| L2 | `claude-sdk.md:299-301` (desc dispatch), spec:137-140 | Trụ 3 — không tool vỏ nào có "khi nào KHÔNG dùng" (vd dispatch: không dùng để hỏi tình hình → orch_status) trong khi craft:70 + checklist bắt buộc | thêm 1 mệnh đề "KHÔNG dùng để…" mỗi description |
| L3 | `multi-agent.md:250-251` `err("bad_role", ..., retryable=True)` | Trụ 6 — retry Y NGUYÊN vô ích (phải đổi param mới có ích) → theo định nghĩa craft:144 là `false`; True dạy model lặp lại call hỏng | `retryable=False` (hint đã bảo đổi role) |
| L4 | `lab-joint.md:221` `"hint": f"schema: {mod.SCHEMAS[name]['params']}"` | Trụ 6 — hint dump raw grammar nội bộ (`{"type":"str","required":True...}`) KHÁC JSON Schema model đã thấy → 2 cách biểu diễn 1 schema, nhiễu | hint nêu đúng param sai + kiểu đúng, không dump dict |
| L5 | `lab-joint.md:355-359` stub đánh dấu bằng text `[STUB]` + `computedBy:"STUB"` | Trụ 5 — craft:114-115 đòi mock có "1 signal thống nhất mọi tool" máy-đọc (`isMock:true`) để loại khỏi tổng hợp; text marker không lọc máy được, nhánh `found:False` không có marker field | thêm `"isMock": true` mọi return của mọi stub |
| L6 | `lab-joint.md:71` `"loan_amount_vnd": {"type": "float", "default": 0, ...}` | Trụ 5 — `0` làm sentinel "không cung cấp" là họ hàng anti-pattern `{"price": 0}` phía input: 0 đồng là giá trị nghiệp vụ hợp lệ-trông-thật | `default: None` + desc "bỏ trống nếu chưa rõ số tiền" |
| L7 | `claude-sdk.md:361-362` `mount_role(role) -> (mcp_server, allowed_tools, skill_text)` ĐỐI ĐẦU `lab-joint.md:238` `return skill, server, allowed` | Mâu thuẫn nội bộ (builder-surface) — 2 doc 2 thứ tự tuple, unpack chéo là gán skill vào server | chốt 1 thứ tự, sửa doc kia |

---

## 5. LỖI CHƯA CÓ TÊN — pattern đáng đúc thành rule §15

1. **"Đòi ID chưa phát"** (từ N1): schema/bảng-card bắt model điền một id mà chỉ vỏ sinh ra SAU cú gọi (hoặc không bao giờ trả về đường model-đọc-được). Nặng hơn "ID lên mặt model": ở đây model không chép sai id — model **bịa id từ hư không** vì không còn lựa chọn nào khác. **Luật đề xuất**: *field model phải điền thì hoặc là TÊN/enum model sẵn có, hoặc phải do một tool-return TRƯỚC ĐÓ phát ra; id vỏ sinh → vỏ tự inject, cấm nằm trong shape agent bơm.*

2. **"Idempotent chỉ cho con cưng"** (từ N4): luật idempotent được đúc thành rule cho `orch_dispatch` (§15:290) nhưng các cửa khác cùng sinh-bản-ghi-chờ (phiếu pending, card approval) không được quét cùng luật. **Luật đề xuất**: *MỌI tool-call sinh bản-ghi-chờ-người (task, phiếu, card cần bấm) phải dedupe theo khoá tự nhiên của nó (role / action+payload_hash) — retry trả bản đang chờ, không sinh bản thứ hai.*

3. **"Retry-thành-xin-duyệt-lại"** (từ N3): phiếu single-use + không cache biên nhận biến retry-sau-thành-công thành một vòng approval MỚI trông hợp lệ với cả admin — phanh an toàn tự trở thành máy nhân đôi hành động irreversible. **Luật đề xuất**: *write irreversible phải nhớ payload_hash đã-executed và trả lại biên nhận cũ; "đã làm rồi" là một kết quả, không phải lý do mở vòng duyệt mới.*

4. **"Một tool hai hộ khẩu"** (từ N6/V12/V14/V10/L7): tên đầy đủ `mcp__<server>__<tool>`, kiểu param, hành vi wrapper, converter — mỗi thứ đang sống ở ≥2 doc "tự chứa" và đã drift. **Luật đề xuất**: *mọi mảnh contract của 1 tool (server nó ở, schema, envelope, wrapper) chỉ được VIẾT ĐẦY ĐỦ ở đúng 1 doc; doc khác chỉ được trỏ, không được chép.*

5. **"Annotations mồ côi"** (từ V3): capability khai ở contract nhưng điểm mount không truyền — policy máy-đọc chết im mà mọi audit đọc-doc vẫn thấy "có khai". **Luật đề xuất**: *annotations sinh ra từ cùng vòng lặp với mount + allowed_tools; audit gate = round-trip `list_tools()` phải thấy annotations.*

6. **"Hint cho builder"** (từ L4 + db_error `lab-joint.md:218` "kiểm file seed rồi thử lại"): hint nêu hành động mà chỉ NGƯỜI BUILD làm được — agent không có tool nào "kiểm file seed". **Luật đề xuất**: *hint chỉ được nêu action agent thi hành được bằng tool đang cầm (hoặc "báo main/user"); action vận hành đi vào log vỏ.*

7. **"Cắt-tóm-tắt im lặng ở mặt prompt"** (từ V6): trụ 4 lâu nay soi tool-output, nhưng wake-prompt cũng là mặt model — summary có trần mà không cờ + không đường re-fetch là cắt-im-lặng ở cửa khác. **Luật đề xuất**: *mọi bản tóm tắt vỏ đưa vào prompt phải khai "đã tóm tắt" + chỉ chỗ bản đầy đủ nằm trên đường model-đọc-được (card/tool), y như truncated-envelope của tool.*
