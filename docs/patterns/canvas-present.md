# Pattern: Canvas & Present-tool — card có cấu trúc từ agent

> Tài liệu "cách build" cho `SPEC.md` §6 (canvas & card), giao với §4.4 (phanh)
> và nguyên lý N5. Tự chứa: đọc doc này + spec là build được tool `present` + FE render canvas.
> Thuật ngữ hệ: **present** (tool đẩy card) · **card** (sản phẩm công việc có cấu trúc trên canvas) ·
> **phiếu** (bản ghi bảng `approvals` chờ người duyệt) · **main/sub** (agent điều phối / chuyên gia).

---

## 0. Nguyên lý N5 — đọc trước mọi thứ

> **Agent trả TEXT tự do cho chat. Card trên canvas CHỈ sinh ra từ cú gọi tool `present(card)`
> của agent. Vỏ KHÔNG BAO GIỜ parse text của agent để đoán ra card.**

Card là **opt-in qua tool-call**, không phải schema ép lên mọi câu trả lời. Agent nói chuyện
bình thường bằng text; khi (và chỉ khi) có "sản phẩm công việc" đáng trình lên canvas — sub
trình verdict thẩm định, main trình tờ trình — agent chủ động gọi `present`.

### Vì sao parse-text SAI, present-tool ĐÚNG

Parse-text chết vì: ép JSON mỗi câu = cuộc chiến prompt vô tận, lệch 1 dấu ngoặc là card vỡ;
heuristic tách text = đoán mò vỡ dây chuyền; và structured bị serialize-rồi-parse-ngược là
mất mát 2 chiều (anti-pattern "envelope cứng" §15 spec). Present-tool đúng vì **structured đi
thẳng tại nguồn**: agent vừa tính xong DSCR thì đưa nguyên dict vào tool-arg → DB → SSE → FE,
không qua khâu đoán nào; agent chủ động lúc nào cần card; skill dạy hành vi, vỏ chỉ cấp tool
+ render (N1/N3).

---

## 1. Anatomy của `present` — vòng đầy đủ

### Nguyên lý
`present` là tool chung (cấp cho MỌI role, main lẫn sub). Nó làm đúng 4 việc: **validate shape
tối thiểu → persist bảng `cards` → bắn SSE `card` → trả text cho agent**. Vỏ không đọc nội dung
bên trong `items` (N3) — chỉ khóa shape `{type, title, items}` đủ để FE không vỡ khi render.

```
AGENT (main/sub, vừa xong một khối việc)
  │  gọi tool với DATA STRUCTURED (không phải text)
  │  present({type:"metric", title:"Thẩm định DN X", items:[...]})
  ▼
PRESENT-TOOL (vỏ)
  1. validate shape tối thiểu: type ∈ 6 loại HIỂN THỊ, title: str, items: list
       fail → error 4-field {code:"bad_card", ..., retryable:false}
  2. INSERT bảng cards (conv_id, task_id, type, data)   ◄─ để canvas reload (§4)
       id do VỎ sinh lúc insert — agent không cầm, không bơm id nào (§15)
  3. sse_emit(conv_id, "card", {card})                  ◄─ FE đang mở thấy ngay
  4. return {rendered:true, hint:"tiếp tục việc"}       ◄─ happy-path cũng hint (Trụ 6)
  ▼                                    ▼
FE render card theo type          AGENT chạy tiếp
(canvas cột phải Workspace)

Card `approval` KHÔNG đi đường này — nó do VỎ tự sinh từ wrapper phanh (§6).
```

### Pattern

```python
# 6 loại HIỂN THỊ — enum này nằm TRONG input_schema của tool present (SDK chặn từ cửa).
# "approval" KHÔNG có trong enum: sub/main gọi present type=approval là bị schema reject —
# rào bằng cơ chế, không bằng lời dặn (N2). Card approval chỉ có MỘT cửa sinh: wrapper phanh (§6).
PRESENT_TYPES = ["case_file", "metric", "checklist", "options", "timeline", "document"]

async def present(card: dict) -> dict:
    # 1. Shape tối thiểu — vỏ mù nội dung items (N3)
    if card.get("type") not in PRESENT_TYPES \
       or not isinstance(card.get("title"), str) \
       or not isinstance(card.get("items"), list):
        return {"code": "bad_card",
                "message": "card cần {type, title, items}; type ∈ " + str(PRESENT_TYPES),
                "hint": "sửa shape rồi gọi lại present",
                "retryable": False}          # retry Y NGUYÊN vô ích — phải sửa shape

    ctx = current_ctx()  # ContextVar: conversation_id, task_id, actor (set trước mỗi call)

    # 2. Persist — card không ghi DB là card ma, mất khi reload (§4).
    #    MỌI id (card_id) do VỎ sinh tại đây — model không bao giờ phải bơm id (§15).
    card_id = await db.cards.insert(conv_id=ctx.conversation_id,
                                    task_id=ctx.task_id,
                                    type=card["type"], data=card)

    # 3. Realtime — id vỏ vừa sinh inject vào payload cho FE
    sse_emit(ctx.conversation_id, "card", {"card": {**card, "id": card_id,
                                                    "task_id": ctx.task_id}})

    # 4. Happy-path cũng chỉ đường (Trụ 6)
    return {"rendered": True,
            "hint": f"card {card['type']} đã lên canvas — tiếp tục việc, "
                    "xong hết thì trả lời text."}
```

### Lưu ý

| Bẫy | Rule |
|---|---|
| Vỏ validate sâu nội dung card (đúng số cột, đúng tên metric…) | Chỉ khóa shape tối thiểu `type + title + items` — nội dung là việc của lab/skill (N3); khóa sâu = lab đổi card là phải sửa vỏ |
| Bắn SSE trước khi commit DB | Persist TRƯỚC, SSE SAU — nếu ngược, FE nhận card mà reload lại mất (card ma) |
| Validate fail thì raise exception → agent thấy stack trace | Trả error 4-field `{code, message, hint, retryable}` cùng envelope toàn hệ (§5 spec) — hint là action kế cụ thể |
| Quên set ContextVar attribution → card không biết của task nào | Set (conversation_id, task_id, actor) trước MỌI tool-call — card phải trỏ được về sub sinh ra nó |
| Dùng text agent trả cho chat làm nguồn render card "cho tiện" | Cấm — mọi pixel structured trên canvas đều đi từ tool-arg, không từ chat text (N5) |
| Schema card đòi agent bơm id (`card_id`, `approval_id`…) | Model chưa từng được phát id nào — chỉ có thể BỊA (§15 "Đòi-ID-chưa-phát"). Mọi id do VỎ sinh lúc persist/emit; tham chiếu agent-side dùng TÊN tool/role |

---

## 2. HAI LOẠI CARD — khác nhau ở CỬA SINH

### Nguyên lý

Cả 7 card type dùng **cùng MỘT hạ tầng ra màn hình**: cùng bảng `cards`, cùng SSE event
`card`, cùng FE canvas. Khác nhau ở **cửa sinh** — và chỉ có ĐÚNG HAI cửa:

| | (a) Card HIỂN THỊ | (b) Card CẦN NGƯỜI BẤM |
|---|---|---|
| Type | `case_file` · `metric` · `checklist` · `options` · `timeline` · `document` | `approval` |
| Cửa sinh | **AGENT gọi `present`** (§1) — opt-in, skill dạy lúc nào | **VỎ tự sinh từ wrapper phanh** (§6) — agent không gọi, không cần biết |
| Mục đích | Verdict, hồ sơ, tờ trình — người xem | Dừng chờ người quyết (đường phanh §4.4 spec) |
| Persist + SSE | bảng `cards` + event `card` | như (a) + **phiếu** bảng `approvals` + `approval.pending` + `conversation.status → waiting_approval` |
| Agent thấy gì | `{rendered:true, hint:"tiếp tục"}` từ present | error `approval_required` từ chính TOOL GATED nó vừa gọi — hint "báo main, kết thúc lượt" |
| Đường sống lại | Không cần | Người bấm → `POST /api/approvals/{id}/decide` → event đánh thức main (resume §4.4 spec) |

Vì sao tách cửa: card approval là **một nửa của cơ chế phanh** — mà phanh là cưỡng chế (N2),
không được phụ thuộc agent tự giác gọi present. Sub gọi tool gated là wrapper TỰ đẻ phiếu +
card, agent lì hay ngoan không đổi được điều đó. `approval` không nằm trong enum của present
(§1) nên cũng không có đường "agent tự chế card phanh giả".

### Lưu ý

| Bẫy | Rule |
|---|---|
| Build 2 hạ tầng render riêng cho 2 loại card | MỘT hạ tầng ra màn hình (cards + SSE + canvas); chỉ CỬA SINH khác. Thêm hạ tầng = thêm điểm hỏng (N4) |
| Cho agent gọi `present type=approval` "khi muốn xin ý kiến" | KHÔNG — 1 cửa sinh duy nhất là wrapper phanh. Agent muốn hỏi user thì HỎI TRONG CHAT (clarify §4.3 spec), không chế card phanh |
| Trông cậy hint "kết thúc lượt" làm phanh | Hint là hành vi (N2). Phanh thật: tool gated không nổ khi chưa có phiếu APPROVED — agent lì chạy tiếp cũng không rút được tiền |
| Sinh card approval nhưng quên đổi status phòng | FE không biết đang chờ ai — wrapper sinh phiếu phải kèm `conversation.status → waiting_approval` + SSE (§6) |

---

## 3. Bảy card types

### Nguyên lý
Card type là **generic theo hình dạng dữ liệu, không theo role** — mọi role dùng chung 7 type,
FE chỉ cần 7 component render theo `type`. Sub Legal muốn trình checklist thì dùng `checklist`;
mai lab đẻ role mới (vd Risk) cũng trình bằng đúng 7 type này — **thêm role KHÔNG thêm card
type, không sửa FE**. Nội dung trong `items` do agent bơm, vỏ và FE không áp đặt nghĩa.

### Pattern — bảng chuẩn

| type | Ai gọi (điển hình) | Data schema tối thiểu (trong `items` + field kèm) | Loại | FE render |
|---|---|---|---|---|
| `case_file` | main (mở ca, chốt hồ sơ khách) | `items: [{label, value}]` + `flags: [str]` | hiển thị | Khối hồ sơ: khách/DN, nhu cầu vay, docs đã có, cờ đỏ nổi bật |
| `metric` | sub credit (bảng chỉ số thẩm định) | `items: [{name, value, threshold, pass, source}]` | hiển thị | Bảng chỉ số: DSCR/LTV/nhóm CIC, badge pass/fail theo ngưỡng, chip source |
| `checklist` | sub legal (điều kiện pháp lý) | `items: [{item, status: ok\|missing\|risk, note?}]` | hiển thị | Danh sách tick; `missing`/`risk` highlight màu warn/fail |
| `options` | sub products (so gói vay) | `items: [{name, rate, tenor, fee, fit}]` + `recommended: str` | hiển thị | Bảng so sánh cột các gói, gói khuyến nghị đóng khung |
| `timeline` | sub operations (lộ trình xử lý) | `items: [{step, owner, eta}]` + `total_days` | hiển thị | Dòng thời gian bậc thang, tổng ngày ở cuối |
| `document` | main (tờ trình tổng hợp cuối ca) | `items: [{section, content}]` + `sources: [tên tool/role]` | hiển thị | Trang tờ trình cuộn dọc, nút export |
| `approval` | **CHỈ vỏ tự sinh** từ wrapper phanh (§6) — không agent nào gọi được (§1: ngoài enum present) | data vỏ tự dựng từ phiếu: `items: [{label, value}]` + `action`, `options` — mọi id vỏ inject cho FE | **cần bấm** | Panel phanh: tóm tắt hành động + nút Duyệt / Từ chối + ô lý do |

### Mọi con số kèm `source` — citation chip

Rule cứng của hệ (anti-pattern "số không nguồn" §15 spec): **mỗi item mang số trên card kèm
field `source` = TÊN tool đã trả ra số đó** (vd `"banking_credit_tinh_dscr"`) — KHÔNG kèm
id tool-call (agent không được phát id nào, §15 Đòi-ID-chưa-phát). FE render `source` thành
**citation chip** — bấm chip, FE tự khớp về tool-call gốc trong trace theo `(task_id của card,
tên tool)` — bảng `tool_calls` append-only có đủ 2 khoá đó. Số không nguồn = số bịa — skill
dạy agent: không lấy từ tool thì không đưa lên card.

```tsx
// FE — 1 switch theo type, 7 component; chip source dùng chung
function Card({ card }: { card: CardPayload }) {
  switch (card.type) {
    case "metric":    return <MetricTable rows={card.items} />;
    case "checklist": return <CheckList rows={card.items} />;
    case "options":   return <OptionCompare rows={card.items} rec={card.recommended} />;
    case "timeline":  return <StepTimeline rows={card.items} total={card.total_days} />;
    case "case_file": return <CaseFile rows={card.items} flags={card.flags} />;
    case "document":  return <DocumentView sections={card.items} sources={card.sources} />;
    case "approval":  return <ApprovalPanel card={card} />;   // §6
    default:          return <RawCard data={card} />;          // type lạ: render thô, không vỡ
  }
}

const SourceChip = ({ source, taskId }: { source: string; taskId: string }) => (
  // FE khớp tool-call gốc theo (taskId, tên tool) — agent chỉ phát TÊN, không phát id
  <button className="chip" onClick={() => openTrace(taskId, source)}>{source}</button>
);
```

### Lưu ý

| Bẫy | Rule |
|---|---|
| Đẻ card type theo role (`verdict_credit`, `verdict_legal`…) | Type theo HÌNH DẠNG dữ liệu, không theo role — credit dùng `metric`, legal dùng `checklist`; thêm role không thêm type |
| Đẻ tool present riêng cho từng type (7 tool) | MỘT tool `present(card)`, type là field — giảm bề mặt tool, skill chỉ cần dạy chọn type + bơm items đúng |
| FE gặp type lạ thì crash/trắng canvas | Default branch render thô (title + JSON items) — vỏ mù nội dung thì FE cũng phải chịu được nội dung lạ |
| Số trên card không có `source` | Skill dạy: số từ tool mới lên card, kèm source; scorer/audit soi card thiếu source là lỗi |
| Chip source chỉ là text chết | Chip phải BẤM ĐƯỢC về tool-call gốc — đó là giá trị demo "mọi con số có nguồn" trước giám khảo bank |

---

## 4. Persist để reload — card không persist là card ma

### Nguyên lý
Canvas KHÔNG có state riêng. **Mở lại ca = đọc bảng `cards` theo `conv_id` dựng lại canvas
nguyên trạng.** SSE chỉ là đường nhanh cho phiên đang mở; nguồn sự thật để render là DB
(§8 spec: DB = kho render cho FE). Card chỉ bắn SSE mà không ghi DB là **card ma** — user
refresh trang là biến mất, demo đang đẹp thành trắng canvas.

### Pattern

```python
# GET /api/conversations/{id} — full state, canvas dựng từ đây
async def get_conversation(conv_id):
    return {
        "messages":  await db.messages.list(conv_id),
        "tasks":     await db.tasks.list(conv_id),
        "cards":     await db.cards.list(conv_id, order="ts"),   # canvas reload
        "approvals": await db.approvals.list(conv_id),
    }
```

```tsx
// FE: reload = GET full state → dựng canvas → nghe SSE tiếp (không replay-cursor)
// REPLACE rule: card mới cùng (task_id, type) thay card cũ — giữ bản ts mới nhất.
// What-if chạy lại ("thử với 4 tỷ") → sub mới present metric mới → card cập nhật tại chỗ.
function buildCanvas(cards: CardPayload[]) {
  const latest = new Map<string, CardPayload>();
  for (const c of cards.sort((a, b) => a.ts - b.ts)) {
    const key = c.type === "approval" ? `ap:${c.id}`      // approval KHÔNG replace nhau
                                      : `${c.task_id}:${c.type}`;
    latest.set(key, c);
  }
  return [...latest.values()];
}
```

- **Replace là chuyện của FE-render, không phải DB**: bảng `cards` giữ đủ lịch sử (audit soi
  được card cũ), FE chỉ HIỂN THỊ bản mới nhất per `(task_id, type)`. Không DELETE/UPDATE đè.
- **Approval không replace nhau**: mỗi phiếu là một sự kiện riêng, panel đã quyết hiển thị
  trạng thái decided chứ không biến mất (§6).
- Reconnect SSE giữa chừng → gọi lại GET full state rồi nghe tiếp — hệ không build
  replay-cursor/outbox (§14 spec KHÔNG LÀM).

### Lưu ý

| Bẫy | Rule |
|---|---|
| Chỉ bắn SSE, tính sau chuyện lưu DB | Persist là bước 2 TRONG present, trước SSE — không phải việc "tính sau" |
| FE giữ canvas trong memory làm nguồn sự thật | Nguồn sự thật = bảng `cards`; memory chỉ là cache của phiên đang mở |
| Replace bằng UPDATE/DELETE bản ghi cũ | Append giữ lịch sử, FE lọc bản mới nhất — audit và compare cần card cũ |
| What-if đẻ card trùng chồng chất kín canvas | Key render `(task_id, type)` giữ bản mới nhất; task mới (re-dispatch) = task_id mới → card mới đứng cạnh nếu cần so |
| Approval decided thì xóa card cho gọn | Không xóa — panel chuyển trạng thái decided (ai bấm, lúc nào, lý do): đó là bằng chứng, không phải rác |

---

## 5. Skill dạy gọi present — vỏ cấp tool, lab dạy hành vi

### Nguyên lý
Đúng ranh N1/N3: **vỏ cấp tool `present` (cơ khí câm — không biết lúc nào nên gọi)**, còn
**lúc nào gọi + bơm gì vào items = hành vi, nuôi bằng SKILL ở lab**. Skill không dạy agent
"viết JSON đúng khuôn cho vỏ parse" — skill dạy agent **gọi tool với data**. Đây là
tool-discipline chuẩn: học *dùng tool đúng lúc*, không học *format text cho máy đoán*.

### Pattern — đoạn skill mẫu cho sub credit (nằm trong `roles/credit/SKILL.md`)

```markdown
## Trình kết quả lên canvas (bắt buộc, trước khi trả lời text)
Thẩm định xong (đã có đủ DSCR, LTV, nhóm CIC từ tool):
1. Gọi `present` với:
   type: "metric"
   title: "Thẩm định tín dụng — <tên khách/DN>"
   items:
     - {name: "DSCR",     value: <số>, threshold: ">= 1.2",  pass: <bool>,
        source: "banking_credit_tinh_dscr"}
     - {name: "LTV",      value: <số>, threshold: "<= 70%",  pass: <bool>,
        source: "banking_credit_tinh_ltv"}
     - {name: "Nhóm CIC", value: <nhóm>, threshold: "nhóm 1-2", pass: <bool>,
        source: "banking_credit_tra_cic"}
2. Mọi số trên card PHẢI từ tool và kèm `source` đúng tên tool đã trả số đó.
   Số không lấy từ tool → không đưa lên card, không đưa vào câu trả lời.
3. Tool trả "card đã render — tiếp tục" → LÚC ĐÓ mới viết text kết luận trả về main
   (verdict + điều kiện kèm theo, ngắn gọn).
```

Tương tự, skill mỏng của main (vỏ tự viết — main không cần lab train) dạy: mở ca chốt xong
hồ sơ → `present type=case_file`; tổng hợp xong các verdict → `present type=document` (tờ trình,
`sources` = tên các tool/role nguồn); và **khi sub báo về lỗi `approval_required` thì báo user
"đang chờ duyệt" rồi kết thúc lượt** — chờ event phiếu được quyết đánh thức.

### Lưu ý

| Bẫy | Rule |
|---|---|
| Nhét luật "khi nào present" vào code vỏ (vd "task done thì vỏ tự đẻ card từ result") | Vỏ tự đẻ card từ result = parse/đoán nội dung = vỡ N5. Card là quyết định của agent, dạy qua skill |
| Skill dạy format text đầu ra để "vỏ dễ đọc" | Cấm — structured đi qua tool-arg. Text của agent là cho NGƯỜI đọc |
| Skill quên dặn thứ tự (present TRƯỚC, text SAU) | Dặn rõ thứ tự — không thì agent trả text xong quên card, hoặc card ra sau khi main đã tổng hợp |
| Trông cậy skill để agent LUÔN gọi present | Skill là hành-vi-mong-muốn (N2) — thiếu card thì mất điểm demo chứ không mất an toàn; thứ cần cưỡng chế (phanh) đã nằm ở wrapper tool (§6) |
| Sửa vỏ mỗi lần lab đổi cách trình card | Không phải sửa — lab đổi skill/items tùy ý, vỏ chỉ khóa shape `{type, title, items}` |

---

## 6. Approval panel chi tiết — phiếu + card là 2 mặt của 1 sự kiện

### Nguyên lý
**Phiếu** (bản ghi bảng `approvals` — dữ liệu quyết định: action, payload_hash, status) và
**card approval** (bản ghi bảng `cards` type=approval — mặt hiển thị trên canvas) là **hai mặt
của cùng MỘT sự kiện "cần người quyết"**, sinh cùng lúc từ **MỘT cửa duy nhất: bước 4 của
wrapper phanh** (không có "cửa chủ động" nào khác — §2).

**Chủ nhà từng mảnh** (doc này KHÔNG lặp code): cơ chế phanh 4 bước + payload_hash + biên nhận
= spec §4.4 · code wrapper `gated` đầy đủ = `lab-joint.md` §2.1 · event `approval_decided`
đánh thức main = `multi-agent.md` §8. Doc này chỉ giữ **mặt CARD** — 4 luật dưới.

### Pattern — 4 luật mặt card

1. **Sinh**: wrapper tạo phiếu pending (bước 4) → vỏ dựng card approval TỪ PHIẾU (title theo
   action, items từ payload, options Duyệt/Từ chối — mọi id vỏ inject cho FE) → 3 tín hiệu ra
   FE: SSE `card` + `approval.pending` + `conversation.status → waiting_approval`.
2. **Idempotent**: tool gated bị gọi lại khi phiếu còn pending (bước 3 wrapper) → KHÔNG phiếu
   mới, KHÔNG card mới, không SSE lặp — chỉ trả "đang chờ duyệt" cho agent (§15 "Idempotent
   chỉ cho đường đẹp").
3. **Quyết — 1 cửa**: bấm trên canvas (ApprovalPanel) hay Control Tower (queue) đều về
   `POST /api/approvals/{id}/decide` (id do FE cầm — chưa bao giờ qua tay model). Decide phải
   **atomic một chiều**: `UPDATE approvals SET status=<choice> WHERE id=%s AND
   status='pending'` — rowcount 0 (đã quyết rồi / double-click / 2 admin) → HTTP 409 body
   error 4-field `{code:"already_decided", ...}`, KHÔNG raise trần. Thành công → SSE
   `approval.decided` + event `approval_decided` vào hàng đợi phòng (prompt cho main nói theo
   HÀNH ĐỘNG + tham số, không phiếu-id — spec §4.4).
4. **Mặt card đổi theo phiếu, không sửa data card**: bảng `cards` là append-only (§4) — FE
   ghép card approval với phiếu (SSE `approval.decided` mang trạng thái mới) để render panel
   thành "ĐÃ DUYỆT bởi X lúc Y, lý do Z". Không UPDATE đè data card.

Vòng khép: main thức dậy ("giải ngân 5 tỷ cho DN X ĐÃ DUYỆT") → giao lại sub Ops → sub gọi
lại tool y nguyên payload → wrapper bước 2: claim atomic → chạy thật → biên nhận, phiếu `used`.

### Lưu ý

| Bẫy | Rule |
|---|---|
| Bắt agent gọi present để hiện panel phanh | KHÔNG — phanh là cưỡng chế (N2); wrapper tự sinh cả phiếu lẫn card. Agent chỉ cần đọc hint `approval_required` và kết thúc lượt |
| Phiếu và card lưu 1 chỗ | 2 bảng, 2 vai: `approvals` = dữ liệu quyết (query theo key, atomic, biên nhận), `cards` = mặt render. Vỏ trỏ nhau bằng id nội bộ — FE thấy, model không |
| Mỗi nơi một endpoint duyệt | MỘT endpoint decide — một chỗ validate, một chỗ bắn event |
| Duyệt xong không đánh thức main | Decide PHẢI đẩy event `approval_decided` vào hàng đợi phòng — và event này KHÔNG BAO GIỜ bị dedup/nuốt (spec §4.2) |
| Decide bằng get-rồi-update (2 bước) | Race 2 admin = quyết 2 lần — dùng atomic UPDATE…WHERE status='pending', rowcount 0 → `already_decided` |
| Gọi lại tool gated lúc pending → spam phiếu/card | Bước 3 wrapper: báo chờ, không sinh gì mới — canvas chỉ có đúng 1 panel/1 sự kiện |
