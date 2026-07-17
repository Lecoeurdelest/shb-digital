# Pattern: Mối ghép LAB → SYSTEM + mount tool MCP in-process

> ⚠️ **D-21 (18/7) ĐÈ doc này**: data nghiệp vụ nay ở **Postgres** (1 kho với render+audit),
> KHÔNG SQLite. `conn` do vỏ cấp = **PG conn từ pool** (không `sqlite3.connect(mode=ro)`);
> tool LAB viết **SQL portable**; disburse GHI được (không read-only cứng). Mọi snippet
> `sqlite3.*` / `mode=ro` / `row_factory=Row` bên dưới là bản CŨ — architect adapt sang PG
> pool ở B1 (cách A2: vỏ chỉ đổi lớp cấp-conn, KHÔNG đụng logic tool). Xem DECISIONS D-21.
>
> Bản "cách build" cho `SPEC.md` §7 (contract 4 interface + `mount_role`),
> phủ luôn §5 (tool chung) và nguyên lý N3 (vỏ mù). Đọc doc này + spec là viết được
> `mount_role` và stub 3 role — không cần đọc thêm gì.
>
> LAB = repo nuôi tool/skill nghiệp vụ qua vòng train (`shb-digital-experts`, mission
> `missions/shb-132/`). SYSTEM = vỏ (repo này): orchestrator, FE, MCP mount, phanh, sổ sách.

---

## 0. Bức tranh 30 giây

```
LAB (nuôi trí khôn)                 SYSTEM (vỏ — mù nội dung)
roles/<role>/                       mount_role(role)  ← điểm ghép DUY NHẤT
├── SKILL.md      ──text thô──▶     system_prompt của sub
└── functions.py  ──import────▶     REGISTRY + SCHEMAS (+ANNOTATIONS)
    fn(conn,**kw)->dict             → wrap conn RO + envelope lỗi + gate
                                    → @tool → create_sdk_mcp_server("banking_<role>")
                                    → allowed_tools cho sub role đó
```

Vỏ khoá đúng **4 interface** (§1). Mọi thứ khác — bao nhiêu tool, skill dạy gì, công thức
nào, verdict shape ra sao — vỏ **không đọc, không biết, không cần biết** (N3). LAB đổi ruột
thoải mái; chỉ cần không chạm 4 cửa thì vỏ không build lại.

---

## 1. Bốn interface khoá cứng

### Nguyên lý

Contract càng mỏng càng khó vỡ. Ta khoá đúng 4 thứ — dưới mức đó là chuyện của LAB,
trên mức đó là chuyện của vỏ:

1. **Tool** = hàm thuần `fn(conn, **kwargs) -> dict`.
2. **Schema** = entry trong dict `SCHEMAS` theo grammar cố định (§1.2) + `ANNOTATIONS`.
3. **Skill** = `SKILL.md` text Markdown thô → nhét thẳng vào `system_prompt`. Không parse.
4. **Output** = `dict` tự do — vỏ `json.dumps` rồi chuyển nguyên xuống agent. Không đọc trong.

### 1.1 Interface (1) — tool = hàm thuần `fn(conn, **kwargs) -> dict`

```python
def credit_assess(conn: sqlite3.Connection, owner_id: str, loan_amount_vnd: float = 0,
                  collateral_id: str | None = None, loan_type: str | None = None,
                  term_months: int | None = None) -> dict[str, Any]:
    ...
```

- Tham số đầu **luôn** là `conn` — một `sqlite3.Connection` read-only do **vỏ mở và truyền vào**.
  LAB không tự mở conn, không biết DB nằm đâu.
- Tham số nghiệp vụ còn lại là keyword, param optional có default.
- Trả `dict`. **Lỗi nghiệp vụ cũng là dict** (`{code, message, hint, retryable}`), không raise —
  raise chỉ dành cho lỗi bất ngờ, và vỏ sẽ chặn ở envelope (§2).
- File functions **không import SDK/MCP** — thuần `sqlite3` + stdlib, dict-in/dict-out.
  Nhờ vậy LAB test hàm trần bằng pytest, còn vỏ wrap kiểu gì tuỳ vỏ.

### 1.2 Interface (2) — SCHEMAS entry: grammar CHÍNH XÁC

Đây là docs duy nhất agent thấy về tool. Shape gốc tại tool-server LAB (nguồn copy chính thức: DECISIONS D-08) — đây là contract,
sai 1 khoá là converter vỡ:

```python
SCHEMAS: dict[str, Any] = {
    "credit_assess": {
        "mô tả": "THẨM ĐỊNH TRỌN GÓI + là tool DUY NHẤT trả DSCR: ...",
        "params": {
            "owner_id":        {"type": "str",   "required": True, "desc": "id khách/DN, vd 'C007'/'B003'"},
            "loan_amount_vnd": {"type": "float", "default": 0,     "desc": "số tiền muốn vay (VND)"},
            "collateral_id":   {"type": "str",   "default": None,  "desc": "id tài sản thế chấp (nếu có)"},
            "loan_type":       {"type": "str",   "values": ["consumer", "secured"], "default": None,
                                "desc": "loại vay — bỏ trống server tự suy"},
            "term_months":     {"type": "int",   "default": None,  "desc": "kỳ hạn tháng — bỏ trống dùng chuẩn"},
        }},
    "cust_search": {
        "mô tả": "Tìm khách theo TÊN ... Read-only.",
        "params": {
            "q":     {"type": "str", "required": True, "desc": "tên khách/DN"},
            "limit": {"type": "int", "default": 5, "max": 20},
        }},
}

ANNOTATIONS = {                       # annotation chuẩn MCP — harness đặt policy máy-đọc
    "credit_assess": {"readOnlyHint": True},
    "cust_search":   {"readOnlyHint": True},
}

REGISTRY = {"credit_assess": credit_assess, "cust_search": cust_search}   # {tên: fn}
```

Grammar của 1 entry:

| Khoá | Bắt buộc? | Ý nghĩa |
|---|---|---|
| `mô tả` | có | Description tool cho model (thành description của `@tool`). |
| `params` | có | dict `{tên_param: meta}` — meta theo bảng dưới. |

Meta của 1 param:

| Khoá | Bắt buộc? | Ý nghĩa |
|---|---|---|
| `type` | có | `"str"` \| `"int"` \| `"float"` \| `"bool"` \| `"enum"` \| `"list[str]"`. |
| `required` | không | `True` → bắt buộc. Vắng/`False` → optional. |
| `default` | không | Giá trị mặc định — vào khoá `default` của JSON Schema (máy-đọc) **và** ghép vào description; không làm param thành required. |
| `values` | không | Enum các giá trị hợp lệ. Với `list[str]` = enum của phần tử. |
| `max` | không | Trần số — thành `maximum` trong JSON Schema **và** server vẫn tự `min()` enforce (trần là của server, không tin caller). |
| `desc` | không | Mô tả param → `description` trong JSON Schema. |

### 1.3 Interface (3) — SKILL.md = text thô → system_prompt

`SKILL.md` là Markdown thuần (vai + ranh giới + luật cứng + cách trình kết quả). Vỏ đọc
raw text, gán thẳng làm `system_prompt` của sub role đó. **Không parse, không cấu trúc hoá.**
Skill là data, không phải code: LAB sửa luật trong SKILL → vỏ chỉ copy file mới, 0 dòng code đổi.

### 1.4 Interface (4) — output dict tự do, vỏ chuyển nguyên

Tool trả dict shape gì cũng được. LAB hiện dùng 2 phong bì chính (agent + skill là bên đọc):

```python
# phong bì đơn:  {"found": True|False, "item": {...}, "asOf": "...", "hint": "..."}
# phong bì lỗi:  {"code": "...", "message": "...", "hint": "...", "retryable": True|False}
```

Vỏ chỉ làm đúng 1 việc: `dict → json.dumps(..., ensure_ascii=False) →
{"content":[{"type":"text","text": ...}]}`. LAB thêm field `warnings`, đổi shape verdict →
vỏ không biết, không sửa.

### Lưu ý (bẫy → rule)

| Bẫy | Rule |
|---|---|
| Vỏ "tiện tay" đọc `item.verdict` để render/quyết định | CẤM — vỏ mù nội dung (N3). Card có cấu trúc đi đường `present` (spec §6), không đi đường parse output. |
| Functions import SDK để "tự làm @tool luôn" | CẤM — hàm thuần, vỏ mới là bên wrap. Import SDK trong functions = LAB bị khoá vào cách mount của vỏ. |
| Ép mọi tool về 1 schema output cứng | Không — output là dict TỰ DO (interface 4). Envelope `{found,item,asOf,hint}` là **thói quen tốt của LAB**, không phải luật vỏ enforce. |
| Đổi tên khoá `"mô tả"` thành `"description"` cho "Tây" | Không — grammar là contract, LAB đã ship `"mô tả"`. Đổi = vỡ mọi module role hiện có. |

---

## 2. `mount_role(role)` — điểm ghép DUY NHẤT

### Nguyên lý

Toàn bộ chỗ vỏ "chạm" LAB gói trong **1 hàm generic, viết 1 lần, không đổi khi swap tool**.
Hàm này làm 4 việc: đọc module role → wrap từng fn (conn + envelope lỗi + gate) → build
`input_schema` full JSON Schema → dựng MCP server in-process + derive `allowed_tools`.

Vì sao in-process (không HTTP): vỏ chỉ **đọc** seed DB — không có tranh chấp ghi, không cần
world-isolation, nên `create_sdk_mcp_server` in-process là đủ và ít moving part nhất (N4).
Hệ quả phải nhớ: envelope try/except vốn nằm ở HTTP handler của tool-server LAB — bỏ HTTP thì
**vỏ phải tự re-own envelope đó** trong wrapper, thiếu là tool crash = lượt agent vỡ thay vì
dict lỗi sạch.

### Pattern — `schema_to_input`: SCHEMAS params → full JSON Schema

```python
_JSON = {"str": "string", "int": "integer", "float": "number",
         "bool": "boolean", "enum": "string", "list[str]": "array"}

def schema_to_input(params: dict) -> dict:
    """FULL JSON Schema — required/enum/default nằm TRONG schema.
    KHÔNG dùng shorthand {tên: kiểu} của SDK: dạng đó ép MỌI param thành required.
    BẢN DUY NHẤT của converter này — claude-sdk.md §4 trỏ về đây, không copy."""
    props, required = {}, []
    for pname, meta in params.items():
        t = meta.get("type", "str")
        p = {"type": _JSON.get(t, "string")}
        if t == "list[str]":
            p["items"] = {"type": "string"}
            if meta.get("values"):
                p["items"]["enum"] = meta["values"]        # enum của PHẦN TỬ
        elif meta.get("values"):
            p["enum"] = meta["values"]
            # type PHẢI khớp kiểu phần tử — enum [1,2,3] mà type "string" là SDK reject mọi tool_use
            if all(isinstance(v, bool) for v in meta["values"]):   p["type"] = "boolean"
            elif all(isinstance(v, int) for v in meta["values"]):  p["type"] = "integer"
            elif all(isinstance(v, (int, float)) for v in meta["values"]): p["type"] = "number"
            else:                                                   p["type"] = "string"
        if meta.get("default") is not None:
            p["default"] = meta["default"]                 # máy-đọc, không chỉ description
        if meta.get("max") is not None:
            p["maximum"] = meta["max"]                     # JSON Schema key là "maximum";
                                                           # server VẪN tự min() — trần của server
        desc = meta.get("desc", "")
        if meta.get("default") is not None:
            desc = f"{desc} (default {meta['default']})".strip()
        if not meta.get("required"):
            desc = f"{desc} — optional, bỏ trống được".strip(" —")
        if desc:
            p["description"] = desc
        props[pname] = p
        if meta.get("required"):
            required.append(pname)
    return {"type": "object", "properties": props, "required": required}
```

### Pattern — `mount_role`

```python
# vo/mount.py — cách mở conn: read-only + Row, 1 conn TƯƠI mỗi call
def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)   # read-only — vỏ KHÔNG ghi (§6)
    c.row_factory = sqlite3.Row                            # BẮT BUỘC — functions gọi dict(row)
    return c
```

```python
# vo/mount.py — viết MỘT lần; swap tool/thêm tool KHÔNG đổi hàm này
def mount_role(role: str):
    mod = importlib.import_module(f"roles.{role}.functions")   # REGISTRY + SCHEMAS ở đây (§3)
    skill = (ROLES / role / "SKILL.md").read_text()            # interface (3): text thô
    sdk_tools = []
    for name, fn in mod.REGISTRY.items():
        def make(fn=fn, name=name):
            known = set(inspect.signature(fn).parameters) - {"conn"}
            sig_hint = ", ".join(                              # hint người-đọc-được, không dump dict
                f"{p}({m.get('type','str')}{', bắt buộc' if m.get('required') else ''})"
                for p, m in mod.SCHEMAS[name].get("params", {}).items())
            async def handler(args: dict) -> dict:
                # PARAM LẠ → chặn ở cửa, KHÔNG lọc im (§15 param-nuốt: gõ `loan_amount`
                # thay `loan_amount_vnd` mà lọc im là fn chạy default → verdict sai đầy tự tin)
                unknown = set(args) - known
                if unknown:
                    err = {"code": "bad_param",
                           "message": f"param không tồn tại: {sorted(unknown)}",
                           "hint": f"Params hợp lệ: {sig_hint}. Sửa tên rồi gọi lại.",
                           "retryable": True}
                    return {"content": [{"type": "text",
                            "text": json.dumps(err, ensure_ascii=False)}]}
                conn = _conn()                                 # 1 conn MỚI mỗi call
                try:
                    result = fn(conn, **args)                  # interface (1)
                except sqlite3.Error as e:
                    result = {"code": "db_error", "message": str(e),
                              "hint": "Thử lại 1 lần — vẫn lỗi thì báo main dừng nhánh này.",
                              "retryable": True}               # chi tiết seed/path vào LOG VỎ
                except (TypeError, ValueError) as e:
                    result = {"code": "bad_type", "message": f"tham số sai/thiếu: {e}",
                              "hint": f"Params hợp lệ: {sig_hint}.", "retryable": False}
                except Exception as e:   # cửa cuối — agent KHÔNG BAO GIỜ thấy traceback
                    result = {"code": "tool_error", "message": str(e)[:200],
                              "hint": "Lỗi nội bộ tool — thử lại 1 lần; lặp thì báo main.",
                              "retryable": True}
                finally:
                    conn.close()
                return {"content": [{"type": "text",
                        "text": json.dumps(result, ensure_ascii=False)}]}   # interface (4)
            return handler
        h = make()
        if name in GATED_WHITELIST:            # phanh §4.4 spec — bọc NGOÀI envelope (§2.1 dưới)
            h = gated(name, h)
        sdk_tools.append(tool(name=name, description=mod.SCHEMAS[name]["mô tả"],
                              input_schema=schema_to_input(mod.SCHEMAS[name].get("params", {})))(h))
        # ANNOTATIONS không mồ côi: policy máy-đọc sinh từ CHÍNH vòng mount này
        # (readOnlyHint → auto-log nhẹ; destructiveHint → phải nằm trong GATED_WHITELIST)
        TOOL_POLICY[name] = getattr(mod, "ANNOTATIONS", {}).get(name, {})
    server = create_sdk_mcp_server(f"banking_{role}", version="1.0.0", tools=sdk_tools)
    allowed = [f"mcp__banking_{role}__{n}" for n in mod.REGISTRY]
    return skill, server, allowed
```

Dùng khi spawn sub:

```python
skill, server, allowed = mount_role("credit")
options = ClaudeAgentOptions(
    system_prompt=skill,
    mcp_servers={f"banking_credit": server, "common": COMMON_SERVER},   # §5
    allowed_tools=allowed + COMMON_ALLOWED,
)
```

### 2.1 Wrapper gated — phanh bọc ngoài (BẢN ĐẦY ĐỦ — chủ nhà code; cơ chế: spec §4.4)

Hai mảnh: **hàm hash chuẩn hoá** (1 hàm dùng chung cả tạo phiếu lẫn verify — 2 hàm lệch nhau
là phiếu không bao giờ khớp, phanh chết demo) và **wrapper 4 bước trong 1 transaction**.

```python
def payload_hash(action: str, args: dict) -> str:
    """CHUẨN HOÁ rồi mới hash — cùng 1 hàm ở MỌI chỗ (tạo phiếu + verify).
    Chuẩn hoá: bỏ None/field phi-nghiệp-vụ · số về 1 dạng (5e9 ≡ 5000000000) · sort key."""
    biz = {k: (float(v) if isinstance(v, (int, float)) else v)
           for k, v in sorted(args.items()) if v is not None and k not in NON_BIZ_FIELDS}
    canon = json.dumps({"action": action, **biz}, ensure_ascii=False,
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]

def gated(action: str, inner):
    async def wrapper(args: dict) -> dict:
        conv = CTX_CONV.get()                                # §7 — key luôn có conversation
        ph = payload_hash(action, args)
        async with db.tx() as tx:                            # 4 BƯỚC, THEO THỨ TỰ (spec §4.4)
            # 1. Đã thực thi trước? → trả biên nhận cũ, KHÔNG chạy lại (chống thực-thi-đôi)
            r = await tx.get_receipt(conv, action, ph)
            if r:
                return _text({**r, "hint": "Hành động này ĐÃ thực thi trước đó — đây là biên nhận."})
            # 2. Có phiếu APPROVED? → CLAIM ATOMIC rồi mới chạy (1 phiếu = đúng 1 lần chạy)
            claimed = await tx.exec(
                "UPDATE approvals SET status='used', used_at=now() "
                "WHERE conv_id=%s AND action=%s AND payload_hash=%s AND status='approved'",
                conv, action, ph)                            # rowcount 0 = không có/đã bị claim
            if claimed:
                out = await inner(args)                      # chạy thật
                await tx.save_receipt(conv, action, ph, out) # biên nhận cho bước 1 lần sau
                return out
            # 3. Đang PENDING? → báo chờ, KHÔNG đẻ phiếu/card mới (idempotent đường pending)
            if await tx.has_pending(conv, action, ph):
                return _text({"code": "approval_pending",
                              "message": f"'{action}' với đúng tham số này ĐANG chờ duyệt",
                              "hint": "Báo main và kết thúc lượt — có kết quả duyệt sẽ được gọi lại.",
                              "retryable": False})
            # 4. Chưa có gì → tạo phiếu + VỎ tự sinh card approval + SSE (spec §6)
            await tx.create_pending(conv, action, args, ph)  # + card + approval.pending
                                                             # + conversation.status=waiting_approval
        return _text({"code": "approval_required",
                      "message": f"'{action}' ({_tóm_tắt(args)}) cần người duyệt",
                      "hint": "Đã gửi chờ duyệt — báo main và kết thúc lượt.",
                      "retryable": False})
    return wrapper
```

- **Không phiếu-id trên mặt model**: message/hint nói theo HÀNH ĐỘNG + tham số. Khớp phiếu là
  việc của wrapper qua key `(conv, action, payload_hash)` — admin duyệt xong, main giao lại,
  sub gọi lại tool y nguyên là wrapper tự khớp (bước 2).
- Tool nào gated = **whitelist config** (khởi điểm: `disburse`). Ranh gate: chỉ irreversible
  + ảnh-hưởng-ngoài (§4.4 spec); write reversible thì write-through.

| Bẫy phanh | Rule |
|---|---|
| 2 hàm hash (tạo ≠ verify) | 1 hàm `payload_hash` duy nhất — import chung, cấm viết lại |
| check→chạy→mark có `await` xen | claim bằng atomic UPDATE…WHERE TRƯỚC khi chạy (bước 2) |
| Retry sau thành công đẻ phiếu mới | bước 1 — biên nhận trả lại, không chạy, không phiếu (§15) |
| Gọi lại lúc pending đẻ phiếu/card trùng | bước 3 — báo chờ, idempotent (§15 "chỉ cho đường đẹp") |
| Lookup không lọc `conv_id` | phiếu ca A mở khoá ca B — key LUÔN có conversation |
| Phiếu-id trong hint/message | model không cần id (§15 ID-cho-code) — nói theo hành động |

### Lưu ý (bẫy → rule)

| Bẫy | Rule |
|---|---|
| Quên `row_factory = sqlite3.Row` | NỔ ngay call đầu — functions gọi `dict(row)`, default row là tuple. Đặt `Row` trong `_conn()`, không chỗ nào khác. |
| Dùng shorthand `@tool(name, desc, {"arg": str})` | CẤM — shorthand ép **mọi** param thành required; tool có 4 param optional (như `credit_assess`) sẽ làm model kẹt retry rồi bỏ tool. Luôn `schema_to_input` full JSON Schema (enum-số/`maximum`/`default` đã xử trong đó). |
| Lọc im param lạ rồi chạy tiếp | CẤM — param-nuốt (§15): agent gõ sai tên param → fn chạy default → kết quả sai đầy tự tin. Arg ngoài signature → `bad_param` 4-field, fn KHÔNG chạy. |
| Bỏ try/except vì "HTTP server lo rồi" | In-process KHÔNG còn HTTP handler — vỏ phải tự re-own envelope. Thiếu nó: 1 exception = vỡ lượt agent thay vì dict lỗi 4-field agent tự sửa được. |
| Trả traceback cho agent "để dễ debug" | CẤM — agent chỉ thấy error 4-field (`db_error`/`bad_type`/`tool_error`), message cắt 200 ký tự. Traceback vào log vỏ. |
| Mở 1 conn dùng chung cho cả session sub | Không — 1 conn TƯƠI mỗi call, `finally: conn.close()`. Rẻ (SQLite local) và không rò state giữa các call. |
| Thiếu param required → lọt xuống fn nổ TypeError khó hiểu | Chấp nhận được: `TypeError` bị bắt thành `bad_type` kèm schema trong `hint` → agent tự sửa. Muốn đẹp hơn thì check required trước khi gọi fn và trả `missing_param` (retryable: True) — cùng envelope 4-field. |
| Gõ tay `allowed_tools` | Không — derive `f"mcp__banking_{role}__{n}"` từ REGISTRY. Whitelist khớp theo string tuyệt đối, sai 1 ký tự là tool biến mất khỏi model. |
| Đặt gate trong SKILL ("đừng disburse khi chưa duyệt") | Skill là hành-vi-mong-muốn, không phải cơ chế an toàn (N2). Phanh = wrapper `gated` ở tầng tool — chỗ duy nhất kiểm được 100%. |

---

## 3. Swap tool thật = 3 thao tác

### Nguyên lý

LAB ship 1 role thành **1 cụm không tách rời**: các hàm functions + block
`SCHEMAS`/`REGISTRY`/`ANNOTATIONS`. Vỏ gom cụm đó vào **1 module role**
(`roles/<role>/functions.py`) — module tự khai đủ `REGISTRY` + `SCHEMAS`, `mount_role`
chỉ import.

Vì sao SCHEMAS phải đi cùng functions trong 1 module (không manifest nuôi tay riêng):
`@tool` **bắt buộc** có `input_schema` — nghĩa là schema không phải "tài liệu kèm theo" mà là
điều kiện sống của tool. Nếu schema nằm ở file manifest riêng do người khác nuôi tay → 2 nguồn
sự thật → drift (fn thêm param, manifest quên) → model gọi theo schema cũ, fn nổ. Rule: **1 nguồn
sự thật — SCHEMAS sống cạnh REGISTRY trong chính module role** (anti-pattern "2 nguồn sự thật
contract tool", spec §15).

### Pattern — swap `legal` từ stub → thật

1. **Thả file functions**: copy các hàm `legal_*` thật của LAB vào `roles/legal/functions.py`.
2. **Dán cụm SCHEMAS/REGISTRY/ANNOTATIONS** của legal (LAB ship cùng mạch trong tool-server
   của mission) vào cùng file đó.
3. **Xoá stub** cũ.

`mount_role` không đổi 1 ký tự. Orchestrator, dispatch, FE, SSE không đổi. Đó là nghĩa đen
của "vỏ không đổi".

### Lưu ý (bẫy → rule)

| Bẫy | Rule |
|---|---|
| Kỳ vọng swap = "1 dòng registry" | Sai kỳ vọng — swap = **thả module role** (functions + cụm SCHEMAS/REGISTRY). "1 dòng" che mất SCHEMAS, mà `@tool` bắt buộc có `input_schema`. |
| Sửa `mount_role` "nhân tiện" lúc swap | Nếu swap đòi sửa `mount_role` → LAB đã vi phạm 1 trong 4 interface. Sửa phía LAB, không sửa mount. |
| Giữ stub song song tool thật "để so sánh" | Xoá stub — 2 tool cùng tên/gần tên trong 1 server làm model chọn nhầm. |
| LAB thêm tool mới vào role | Không phải swap, chỉ là thêm entry REGISTRY + SCHEMAS trong module role — mount tự thấy ở lần `mount_role` kế. |

---

## 4. Stub role chưa nuôi

### Nguyên lý

LAB mới có `credit` thật; `legal`/`products`/`operations` chưa nuôi. Vỏ vẫn build đủ 4 role
ngay từ ngày 1 (test đường ghép sớm + demo phối hợp nhiều chuyên gia). Stub = tool giả
**đúng contract** (signature + envelope shape thật, data giả) → agent tiêu thụ stub và tool
thật **y hệt** → swap vô hình. Giảm rủi ro "agent quen envelope stub lệch envelope thật" bằng
cách bám đúng phong bì chuẩn của LAB: `{found, item, asOf, hint}` + lỗi 4-field.

### Pattern — `roles/legal/functions.py` (stub, xoá khi LAB đẻ thật)

```python
import sqlite3
from datetime import datetime, timezone
from typing import Any

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def legal_check_documents(conn: sqlite3.Connection, owner_id: str) -> dict[str, Any]:
    """STUB — envelope {found,item,asOf,hint} y tool thật; số fake, shape thật."""
    row = conn.execute(
        "SELECT id, docs_status FROM collaterals WHERE owner_id=? LIMIT 1", (owner_id,)
    ).fetchone()
    if not row:
        return {"found": False, "isMock": True, "asOf": _now(),
                "hint": f"[STUB] Không thấy tài sản của '{owner_id}' — lấy id qua cust_search."}
    return {"found": True, "isMock": True, "asOf": _now(),   # isMock MỌI return — máy đọc được,
            "item": {"ownerId": owner_id, "docsStatus": row["docs_status"],   # loại khỏi tổng hợp
                     "legalVerdict": "đủ" if row["docs_status"] == "complete" else "cần bổ sung",
                     "computedBy": "STUB"},
            "hint": "[STUB] Pháp chế thật chưa nuôi — shape đúng, số fake, KHÔNG dùng để quyết."}

REGISTRY = {"legal_check_documents": legal_check_documents}
SCHEMAS = {
    "legal_check_documents": {
        "mô tả": "[STUB] Kiểm tra pháp lý giấy tờ tài sản của owner. Read-only.",
        "params": {"owner_id": {"type": "str", "required": True, "desc": "id khách/DN, vd 'C007'"}},
    }}
ANNOTATIONS = {"legal_check_documents": {"readOnlyHint": True}}
```

### Lưu ý (bẫy → rule)

| Bẫy | Rule |
|---|---|
| Stub trả string thô / shape tuỳ hứng | Stub PHẢI đúng phong bì chuẩn (`found/item/asOf/hint`, lỗi 4-field) — nếu không, skill viết cho stub sẽ vỡ khi swap tool thật. |
| Stub hardcode data không đụng DB | Cho stub query seed DB thật khi có bảng liên quan (như `collaterals` ở trên) — test được cả đường conn ngay từ stub. |
| Giấu chuyện đang là stub | `[STUB]` trong `mô tả`/`hint` cho người + **`isMock: true` MỌI return** cho máy (Trụ 5 — audit/scorer loại số mock khỏi tổng hợp; chữ [STUB] trong text máy không lọc được). |
| Stub "cho đẹp" thêm 5-6 tool | 1-2 tool/role là đủ chạy demo phối hợp. Stub là chỗ giữ chỗ, không phải chỗ thiết kế thay LAB. |

---

## 5. Tool chung mọi role: `calc` + `present`

### Nguyên lý

Hai tool KHÔNG thuộc role nào mà mọi sub đều cần:

- **`calc`** — tầng-0: agent **cấm nhẩm** (cấm tính tay mọi phép tính, kể cả cộng trừ lẻ).
  Số nghiệp vụ (DSCR/LTV) tool nghiệp vụ đã tính sẵn, nhưng `calc` là lưới an toàn cho mọi
  phép còn lại. Không hedge — cấp mặc định cho mọi role. Contract (chốt 1 chỗ, TẠI ĐÂY):
  `calc(expression: str)` → `{value, expression, asOf}` · lỗi → `{code:"bad_expression",
  message, hint, retryable:true}` — biểu thức số học thuần, không eval code.
- **`present(card)`** — cửa DUY NHẤT sinh card có cấu trúc ra canvas (N5 — vỏ không bao giờ
  parse text agent ra card). Chi tiết card types + hành vi STOP của approval-card: spec §6.

Mount vào **1 server chung** `common`, `allowed_tools` của mọi sub = tool role + tool chung.

### Pattern

```python
# vo/common_tools.py — dựng 1 lần lúc boot, share cho mọi sub
COMMON_SERVER = create_sdk_mcp_server("common", version="1.0.0",
                                      tools=[calc_tool, present_tool])
COMMON_ALLOWED = ["mcp__common__calc", "mcp__common__present"]

# lúc spawn sub bất kỳ:
options = ClaudeAgentOptions(
    system_prompt=skill,
    mcp_servers={f"banking_{role}": server, "common": COMMON_SERVER},
    allowed_tools=allowed + COMMON_ALLOWED,
)
```

`calc` và `present` là tool vỏ tự viết → phải qua đủ checklist chất lượng + auditor đối kháng
như mọi tool điều phối (spec §5). `calc` cùng contract handler (`args dict` → content-block,
lỗi 4-field); `present` khác ở chỗ có side-effect (lưu card + SSE) và chuỗi trả về điều khiển
agent dừng/chạy tiếp (spec §6).

### Lưu ý (bẫy → rule)

| Bẫy | Rule |
|---|---|
| Nhét `calc` vào từng server `banking_<role>` | Không — 1 server `common` duy nhất; nhét theo role là N bản copy 1 tool, audit lẫn namespace. |
| Namespace lẫn: tool chung mang prefix role | Convention spec §5: `orch_*` (điều phối, chỉ MAIN) · `banking_<role>_*` (nghiệp vụ) · tool chung không prefix role (`mcp__common__calc`). Audit log đọc ra ngay tool nào của ai. |
| Cấp `orch_dispatch` cho sub "cho tiện" | CẤM — sub không được giao việc. `orch_*` chỉ nằm trong `allowed_tools` của MAIN. Ranh giới quyền = whitelist, không phải lời dặn. |
| Dặn agent "hãy dùng calc" rồi thôi | Dặn trong SKILL **và** cấp tool. Nhưng nhớ N2: muốn chặn cứng số-không-nguồn thì kiểm ở scorer/audit (số trên card phải có `source`), không cược mình prompt. |

---

## 6. Seed DB — vỏ mở read-only

### Nguyên lý

LAB giữ nguồn seed (data + ground-truth). Vỏ chỉ cần biết: **file DB nằm đâu** và **mở
read-only**. Nội dung từng bảng là chuyện giữa functions và DB — vỏ không query nghiệp vụ.
Bảng `assumptions` là tầng tham số nghiệp vụ (ngưỡng DSCR, trần LTV, rate, term, trần
1-khách...) — tool đọc từ đây, **không hardcode số** → LAB đổi chính sách = update 1 dòng DB,
không đổi code.

### Pattern — 6 bảng (cột theo mission `shb-132` thật)

| Bảng | Cột chính | Vai |
|---|---|---|
| `customers` | `id, full_name, age, occupation, monthly_income, region` | khách cá nhân |
| `businesses` | `id, name, sector, annual_revenue, equity, years_operating` | khách doanh nghiệp |
| `loans` | `loan_id, owner_id, principal, outstanding, monthly_payment, status` | dư nợ hiện hữu |
| `collaterals` | `id, owner_id, type, appraised_value, docs_status` | tài sản thế chấp |
| `cic_records` | `owner_id, cic_group, history_note` | lịch sử tín dụng (nhóm 1-5) |
| `assumptions` | `key, value, source, note` | **tham số nghiệp vụ swap được** |

Cách vỏ mở (đã nằm trong `_conn()` ở §2):

```python
sqlite3.connect(f"file:{DB}?mode=ro", uri=True)   # mode=ro qua URI — mở ghi là bug
```

### Lưu ý (bẫy → rule)

| Bẫy | Rule |
|---|---|
| `sqlite3.connect(DB)` trần (mặc định read-write) | Luôn `file:...?mode=ro&uri=True` — vỏ KHÔNG ghi seed DB, kể cả "chỉ update 1 cờ". Ghi audit đi Postgres (§7), không đi SQLite seed. |
| Hardcode ngưỡng (dscr_min=1.2) trong tool | Số nghiệp vụ đọc từ `assumptions` — hardcode là 2 nguồn sự thật, LAB đổi chính sách mà tool báo số cũ. |
| Vỏ tự viết migration/seed script cho 6 bảng | Không — LAB giữ nguồn seed + ground-truth. Vỏ chỉ nhận file `.db` đã seed và trỏ `DB_PATH` vào. |
| Nhầm seed DB (SQLite) với DB vỏ (Postgres) | 2 DB khác vai: SQLite seed = thế giới nghiệp vụ, read-only với vỏ · Postgres = kho render + audit của vỏ (spec §10), read-write. |

---

## 7. Attribution + audit mỗi tool-call

### Nguyên lý

Mọi tool-call phải truy được: **ca nào, ai gọi** (actor = role sub hay main). Nhưng 2 id này
KHÔNG được nằm trong `input_schema` — model thấy là model bịa được (fabricate id trông-hợp-lệ),
và id bịa = ghi audit nhầm ca. Giải pháp: `ContextVar` — vỏ set trước khi chạy lượt agent,
wrapper đọc lúc tool chạy; model không hề thấy. Dùng `ContextVar` (không phải biến global)
vì mỗi async task có bản sao riêng → 2 conversation chạy đồng thời không giẫm id của nhau.

Audit ghi bảng `tool_calls` (Postgres, spec §10) — **append-only, fire-and-forget**: audit là
sổ phụ, lỗi ghi sổ không được phép làm hỏng cú tool-call chính.

### Pattern

```python
from contextvars import ContextVar

CTX_CONV:  ContextVar[str] = ContextVar("conversation_id", default="")
CTX_ACTOR: ContextVar[str] = ContextVar("actor", default="")

# Set BÊN TRONG coroutine chạy lượt đó — KHÔNG set từ handler của main trước khi spawn
# (spawn nhiều sub liên tiếp từ 1 handler → set ở cha là các con giẫm actor của nhau):
async def _run_main_turn(conversation_id, ...):
    CTX_CONV.set(conversation_id); CTX_ACTOR.set("main")
    ...
async def _run_sub(task):                        # dòng ĐẦU TIÊN của coroutine sub
    CTX_CONV.set(task.conv_id); CTX_ACTOR.set(task.role)
    ...

# trong handler của mount_role (§2), quanh cú gọi fn:
t0 = time.monotonic()
result = fn(conn, **args)
spawn_bg(audit_write(                    # NỀN, fire-and-forget — audit lỗi KHÔNG fail call chính,
    conv=CTX_CONV.get(), actor=CTX_ACTOR.get(), tool=name,     # không block đường trả kết quả
    input=args, output=result, ms=int((time.monotonic() - t0) * 1000)))   # lỗi ghi → log vỏ
```

`audit_write` = INSERT vào `tool_calls(id, task_id, ts, actor, tool, input, output, cost)` —
chỉ INSERT, không UPDATE/DELETE (append-only). SSE `toolcall` (spec §9) bắn từ cùng chỗ này
cho trace timeline + cost meter.

### Lưu ý (bẫy → rule)

| Bẫy | Rule |
|---|---|
| Cho `conversation_id` vào `input_schema` "để model điền" | CẤM — model bịa id. Id đi đường ContextVar, model không thấy → không bịa được. |
| Dùng biến global thay ContextVar | Race giữa 2 conversation đồng thời → audit trộn ca. ContextVar cho mỗi async task bản sao riêng. |
| `await audit_write(...)` chờ xong mới trả kết quả tool | Fire-and-forget — audit nằm trong try/except nuốt lỗi (hoặc đẩy task nền). Audit sập ≠ nghiệp vụ sập. |
| UPDATE bản ghi tool_calls "cho gọn" | Append-only tuyệt đối — audit sửa được thì không còn là audit. |
| Set ContextVar 1 lần lúc boot | Set **trước MỖI lượt/mỗi lần spawn** — actor đổi theo sub đang chạy, set 1 lần là mọi call mang tên con đầu tiên. |

---

## 8. Đường mở (thiết kế sẵn chỗ cắm — KHÔNG build trước khi cần, N4)

### Nguyên lý

Hai hướng phình đã biết trước, đều đã có chỗ cắm sẵn trong pattern trên — nên khi cần thì
cắm, không phải đập:

**(a) Role mới** — thêm phòng ban = thêm thư mục `roles/<role>/{SKILL.md, functions.py}`.
Vỏ quét `roles/` lúc boot → `mount_role` từng thư mục → phòng tự có role mới. Không sửa
code vỏ, không sửa orchestrator (dispatch nhận `role` là string, FE render role động).

**(b) Tri thức phình** — hiện tri thức domain nằm trọn trong SKILL (data ít, cô đọng — đủ).
Khi phình quá SKILL: **wiki markdown trên disk** — mục lục inject vào `system_prompt` + 1 tool
đọc-trang (`wiki_get(page)`). Tool đó là **1 tool retrieval do LAB đẻ** theo đúng contract §1
(`fn(conn_hoặc_path, page) -> dict`), mount qua `mount_role` như mọi tool khác — **vỏ không
dựng hạ tầng RAG/vector**. Chọn cách lấy dữ liệu theo bài (time/accuracy/cost): có id rõ →
query DB thẳng · tri thức cô đọng → skill/wiki · triệu bản ghi phi cấu trúc → lúc đó mới bàn
vector (spec §7).

### Lưu ý (bẫy → rule)

| Bẫy | Rule |
|---|---|
| Build sẵn wiki/vector "cho tương lai" | N4: đường mở là đường ĐÃ VẼ, không phải đường ĐÃ XÂY. SKILL còn đủ thì thôi. Dựng vector khi skill đủ là anti-pattern có tên trong spec §15. |
| Hardcode danh sách 4 role trong orchestrator/FE | Role là dữ liệu quét từ `roles/` — hardcode là role thứ 5 phải sửa 3 chỗ. |
| Vỏ tự viết tool wiki retrieval | Tool retrieval thuộc trí khôn role → LAB đẻ theo contract §1, vỏ chỉ mount. Vỏ viết = vỏ bắt đầu biết nội dung = vỡ N3. |

---

## Phụ lục: checklist ghép 1 role (chạy tay 5 phút)

1. `roles/<role>/functions.py` có `REGISTRY` + `SCHEMAS` (+`ANNOTATIONS`), functions không
   import SDK. `roles/<role>/SKILL.md` tồn tại.
2. `mount_role(role)` trả `(skill, server, allowed)` — `allowed` đúng dạng
   `mcp__banking_<role>__<tool>`.
3. Gọi 1 tool với param thiếu kiểu → `bad_type` 4-field, KHÔNG traceback. Gọi với TÊN param
   sai → `bad_param` (fn không chạy — không lọc im).
4. Gọi 1 tool khi DB chưa seed → `db_error`, `retryable: True`.
5. Tool có param optional → model gọi được mà KHÔNG điền param đó (chứng minh không dính
   shorthand-ép-required).
6. Tool trong `GATED_WHITELIST` — đủ 4 nhánh: (a) chưa phiếu → `approval_required` + phiếu
   pending + card, KHÔNG thực thi · (b) gọi lại lúc pending → `approval_pending`, KHÔNG phiếu/
   card mới · (c) duyệt xong gọi lại → chạy thật đúng 1 lần, phiếu thành `used` + biên nhận ·
   (d) gọi lại sau thành công → trả biên nhận cũ, KHÔNG chạy lại.
7. `tool_calls` có bản ghi mới với đúng `actor` = role vừa chạy (2 ca song song không trộn actor).
