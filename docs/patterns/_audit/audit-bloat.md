# Audit ĐỘ GỌN — docs/patterns (2.652 dòng) vs spec/CORE-SPEC-132.md (311 dòng)

> Auditor đối kháng, ngày 2026-07-17. Nhiệm vụ: chỉ chỗ PHÌNH/TRÙNG/RƯỜM để cắt — không sửa.
> Đơn vị dòng: theo `wc -l` — claude-sdk 592 · multi-agent 683 · lab-joint 557 · canvas-present 402 · streaming-sse 401 · 00-INDEX 17.

## 0. Kết luận nhanh

- **Cắt an toàn ~300 dòng (11%)** mà KHÔNG mất "đọc-là-build-được": 2.652 → **~2.350**.
- Ép thêm ~120 dòng nữa (nén văn "Nguyên lý" các section) → **~2.230**, đổi lại phần "vì sao" cụt hơn — chấp nhận được vì spec đã là chủ nhà của "vì sao".
- Bệnh chính KHÔNG phải văn kể lể — là **3 loại trùng**: (a) 2 file cùng chép 1 đoạn code (có chỗ đã DRIFT thành 2 bản lệch nhau — nguy hiểm hơn cả phình); (b) bảng "Lưu ý/bẫy" cuối section chép lại nguyên văn đoạn "Nguyên lý" đầu section; (c) bảng tổng/TL;DR cuối file chép lại thân bài.

## 1. Bảng cắt theo file

### 1.1 `claude-sdk.md` (592 dòng) — file phình nặng nhất, cắt ≈ 126

| Section | Loại | Dòng | Cắt ~ | Thay bằng |
|---|---|---|---|---|
| §4 `build_input_schema` | **trùng-chéo** (chủ nhà: lab-joint §2 `schema_to_input`) | claude-sdk.md:323-356 | **29** | 2 dòng: "Schema builder full JSON Schema: xem lab-joint §2 — cấm shorthand, enum suy type từ phần tử." **Lưu ý: 2 bản đã DRIFT** — bản lab-joint xử `list[str]`+`enum` items, bản claude-sdk không → giữ 2 bản là sẽ có người copy nhầm bản thiếu. |
| §4 khung `mount_role` | **trùng-chéo** (chủ nhà: lab-joint §2 bản đầy đủ) | claude-sdk.md:358-377 | **18** | 2 dòng trỏ lab-joint §2. claude-sdk chỉ giữ phần thuần-SDK của §4: `@tool`/envelope/`mcp__<server>__<tool>`/allowed_tools (dòng 263-321 — giữ). |
| §5 khoá lượt + interrupt | **trùng-chéo + MÂU THUẪN** (chủ nhà: multi-agent §1-§2, §7) | claude-sdk.md:397-459 | **45** | Đây là chỗ tệ nhất bộ docs: claude-sdk §5 hiện thực "1 lượt/phòng" bằng `asyncio.Lock` + `_live_main`, multi-agent §2/§7 bằng `_busy_rooms` set + queue/drain + `main_registry`/`sub_registry` — **2 cơ chế KHÁC NHAU cho cùng 1 invariant, tên registry khác nhau**. Người build đọc 2 file sẽ code 2 kiểu. Cắt claude-sdk §5 còn ~18 dòng thuần fact SDK: `interrupt()` gọi cross-task ĐƯỢC / `disconnect()` thì KHÔNG; registry đăng ký sau connect, gỡ trong finally — cơ chế slot/queue/drain trỏ multi-agent §2. |
| §8 "Bảng tổng — BẪY CHẾT NGƯỜI" | **rườm** — 17 hàng chép lại đúng các bảng Lưu ý §1-§7 của CHÍNH file này (mỗi hàng đều tự trỏ §) | claude-sdk.md:572-592 | **20** | Xoá. Mỗi section đã có bảng bẫy tại chỗ; bảng gom không thêm thông tin, chỉ thêm 1 chỗ phải sync khi sửa. |
| Bảng Lưu ý §1/§2/§3 chép lại Nguyên lý cùng section | **rườm** | claude-sdk.md:100-108 (hàng 1,2,4 = dòng 30-39 nói rồi) · 177-186 (hàng 1,2,3 = "ba quyết định" 121-131) · 250-259 (hàng 1,2,5,6 = 194-215 nói rồi) | **14** | Mỗi bảng Lưu ý chỉ giữ bẫy CHƯA nói ở Nguyên lý (vd §1 giữ "break khỏi receive_response", "duck-type ThinkingBlock"). |

### 1.2 `multi-agent.md` (683 dòng) — chủ nhà điều phối, giữ phần lớn; cắt ≈ 42

| Section | Loại | Dòng | Cắt ~ | Thay bằng |
|---|---|---|---|---|
| Bảng thuật ngữ đầu file | **trùng-spec** (spec §3 + §4.4 đã định nghĩa phòng/MAIN/SUB/phiếu) | multi-agent.md:8-18 | **4** | Giữ 2 hàng riêng của doc (`event`, `bảng việc`), 4 hàng còn lại trỏ spec §3. |
| §3 `build_sub_client` | **trùng-chéo** (chủ nhà options: claude-sdk §2 `build_options` + phân vai 159-175) | multi-agent.md:268-279 | **10** | 1 dòng: "Options sub (skill/toolpack/model rẻ/trần): claude-sdk §2." |
| §4 đoạn Nguyên lý idempotent | **trùng-spec** (spec §4.1 đã có nguyên luật + lý do, spec §15 có anti-pattern) | multi-agent.md:303-312 | **5** | Giữ phần MỚI: khoá là `(conv_id, role)` không phải nội dung task + check-then-create không `await` xen giữa. Phần "retry/compaction → 2 con đè nhau" trỏ spec §4.1. |
| §6 đoạn Nguyên lý bảng việc | **trùng-spec** (N1 + spec §4.2 "não quyết" đã nói 2 lần) | multi-agent.md:433-440 | **5** | Nén còn 3 dòng: payload 4 thứ + trỏ N1. |
| §8 narrative chuỗi phanh | **trùng-spec** (spec §4.4:117-131 tả nguyên chuỗi) | multi-agent.md:560-572 | **8** | Giữ ý MỚI duy nhất: pause-point sống nhờ phiếu-DB + event (không nhờ process đứng chờ) + "vỏ không tự replay". Chuỗi wrapper/hash/single-use trỏ spec §4.4. |
| Hàng Lưu ý chép lại Nguyên lý cùng section | **rườm** | multi-agent.md:122-127 (hàng 1,2,5) · 208-215 (hàng 4,5 = 145-152) · 415-421 (hàng 1 = 367-370) | **10** | Như quy tắc ở 1.1: Lưu ý chỉ giữ bẫy chưa nói. |

Giữ nguyên (đáng tiền): sequence diagram §1:44-72 · slot/queue/drain §2 · `_report()` §5 · `handle_main_failure` §9 · Phụ lục checklist 672-683 (đây là ship-gate, khác vai với TL;DR — giữ).

### 1.3 `lab-joint.md` (557 dòng) — chủ nhà contract/mount/ContextVar, gọn sẵn; cắt ≈ 23

| Section | Loại | Dòng | Cắt ~ | Thay bằng |
|---|---|---|---|---|
| §2.1 wrapper `gated` | **trùng-chéo** (canvas-present §6 `gated_call` là bản đầy đủ hơn: kèm sinh card + phiếu 2 mặt) | lab-joint.md:252-269 | **13** | Giữ đúng 1 dòng vị-trí-mount (`if name in GATED_WHITELIST: h = gated(name, h)` — đã có ở dòng 232-233) + trỏ canvas-present §6. |
| §5 đoạn cuối về quy trình 10 trụ + present | **trùng-spec** (spec §5 quy trình ship + spec §6 hành vi present) | lab-joint.md:411-414 | **4** | 1 dòng trỏ spec §5/§6. |
| Hàng bẫy shorthand/enum lặp trong chính file | **rườm** — bẫy shorthand nói ở 162-163, 279, enum ở 174, 280 | lab-joint.md:279-280 | **6** | Bảng Lưu ý §2 bỏ 2 hàng đã nói trong docstring/comment của snippet ngay trên. |

### 1.4 `canvas-present.md` (402 dòng) — cắt ≈ 52

| Section | Loại | Dòng | Cắt ~ | Thay bằng |
|---|---|---|---|---|
| §0 hai bảng "parse-text SAI / present ĐÚNG" | **trùng-spec** (N5 + spec §15 hàng "Parse text agent ra card" + "Envelope cứng" đã chốt cả luật lẫn vì-sao) | canvas-present.md:10-33 | **18** | 5 dòng: câu N5 + 1 ý mới duy nhất đáng giữ ("structured giữ tại nguồn: tool-arg → DB → SSE → FE, không qua serialize-parse") + trỏ spec §15. |
| §2 bảng so sánh 2 loại card | **trùng-spec** (spec §6 đã có đúng phân biệt này) | canvas-present.md:118-126 | **6** | Giữ 2 hàng build-detail (chuỗi return + đường sống lại), các hàng còn lại trỏ spec §6. |
| §6 narrative 2 cửa sinh phiếu | **trùng-spec/chéo** (spec §4.4 + multi-agent §8 tả cùng chuỗi) | canvas-present.md:314-326 | **6** | Giữ ý riêng: "2 cửa sinh — wrapper tự bắn card, agent KHÔNG gọi present cho phanh"; đường resume trỏ multi-agent §8. |
| §6 endpoint `decide` | **trùng-chéo** (multi-agent §8:576-595 là chủ nhà đường event/resume; 2 bản còn lệch nhau: một bản trả error 4-field, một bản raise 409) | canvas-present.md:358-373 | **12** | Giữ 2 dòng riêng của canvas (update mặt card theo phiếu — dòng 366-367) + trỏ multi-agent §8. Chốt luôn 1 hành vi (khuyên: theo multi-agent — atomic UPDATE điều kiện). |
| TL;DR cuối file | **rườm** — 5 ý chép lại đúng §0-§6 | canvas-present.md:392-402 | **10** | Xoá. File 400 dòng có mục lục ngầm bằng heading, không cần tóm tắt lặp. |

### 1.5 `streaming-sse.md` (401 dòng) — file gọn nhất bộ, cắt ≈ 7

| Section | Loại | Dòng | Cắt ~ | Thay bằng |
|---|---|---|---|---|
| §0 hệ quả không-replay | **trùng-spec** (spec §9 "KHÔNG replay-cursor/outbox" + §14) | streaming-sse.md:19-23 | **4** | Giữ tiên đề in đậm (13-16) + 1 dòng trỏ spec §14. |
| §2 câu dẫn bảng event | **trùng-spec** (spec §9 có bảng event) | streaming-sse.md:125-126 | **3** | Bảng CHI TIẾT ở đây đáng giữ (thêm shape full-row + quy tắc "bắn nguyên row") — chỉ thêm chú "mở rộng bảng spec §9, spec là chuẩn tên event". |

### 1.6 Trùng lặp XUYÊN FILE mức hàng-bẫy (dedup giữ chủ nhà) — cắt ≈ 25-30

Cùng 1 rule xuất hiện dạng hàng bảng ở 4-5 file. Giữ ở chủ nhà, các nơi khác xoá hàng (đã có trỏ §):

| Rule | Xuất hiện | Chủ nhà giữ |
|---|---|---|
| "Timeout cũng là kết cục → đúng 1 event" | claude-sdk.md:96-98,107,588 · multi-agent.md:367-370,417 · streaming-sse.md:258,388 | multi-agent §5 |
| "Boot đánh failed task `running` mồ côi" | claude-sdk.md:459 · multi-agent.md:500-506,548 · streaming-sse.md:389 · spec §8 | multi-agent §7 |
| "disconnect trong finally / close-on-done" | claude-sdk.md:32-39,104-105 · multi-agent.md:124,683 | claude-sdk §1 |
| "DB không phải nguồn resume" | claude-sdk.md:196,259 · multi-agent.md:126 · streaming-sse §0 (vai render) | claude-sdk §3 |
| "Persist trước, emit sau" | streaming-sse.md:357-361 · canvas-present.md:102 · multi-agent.md:478 | streaming-sse §5 |

## 2. Tổng kết cắt

| File | Hiện | Cắt an toàn | Còn |
|---|---|---|---|
| claude-sdk.md | 592 | ~126 | ~466 |
| multi-agent.md | 683 | ~42 | ~641 |
| lab-joint.md | 557 | ~23 | ~534 |
| canvas-present.md | 402 | ~52 | ~350 |
| streaming-sse.md | 401 | ~7 | ~394 |
| dedup hàng xuyên file (1.6) | — | ~28 | — |
| **Tổng** | **2.652** | **~278 (≈300 kèm dòng trống/heading kéo theo)** | **~2.350** |

Nấc 2 (tuỳ sếp): nén các đoạn "Nguyên lý" mỗi section từ 8-15 dòng văn xuống 4-6 dòng gạch đầu dòng (nhất là multi-agent §1/§2/§3, canvas-present §1/§4) → thêm ~120 dòng, còn **~2.230**. Không khuyên ép quá mức này: phần code/bảng còn lại là vật liệu build thật, cắt nữa là mất "đọc-là-build-được".

Trả lời câu "tại sao 2650 dòng": ~1.500 dòng là code/bảng contract build thật (đáng); ~300 dòng là trùng (cắt); ~400 dòng là văn nguyên-lý mà một nửa spec đã nói (nén được ~120); phần còn lại là bẫy hiện trường có giá (giữ).

## 3. Chỗ THIẾU / LỆCH (ngắn quá hoặc mâu thuẫn — không build được nếu không bổ)

1. **`payload_hash` chưa định nghĩa chuẩn hoá** — được gọi ở canvas-present.md:333, lab-joint.md:257, spec:127 nhưng không đâu nói chuẩn hoá thế nào (thứ tự key? `5e9` vs `5000000000` vs `"5 tỷ"`? bỏ param None/default?). Hash lệch 1 bit = phiếu đã duyệt KHÔNG BAO GIỜ khớp = disburse không bao giờ chạy — bug chết demo phanh. Cần ~8 dòng ở canvas-present §6 (chủ nhà): sort key + JSON canonical + ép kiểu số + drop None.
2. **`run_with_idle_watchdog` chỉ có tên** — multi-agent.md:398 gọi nhưng không có pattern: idle-timeout (reset mỗi message nhận được) khác trần-tổng thế nào, đo "idle" trên stream SDK ra sao. Cần ~10 dòng ở multi-agent §5 hoặc claude-sdk §1.
3. **Tool `calc` không có spec hành vi** — lab-joint.md:387-389 nói "tầng-0, cấm nhẩm" nhưng không nói input là gì (expression string? {op, args}?), output shape gì. Sub nào cũng cầm nó — cần ~8 dòng schema mẫu ở lab-joint §5.
4. **`orch_status` không có pattern** — spec §5 đòi honest/asOf, multi-agent.md:468-471 nhắc 3 dòng, nhưng không đâu có shape output (bảng việc trả gì, đối chiếu registry-vs-DB thế nào khi lệch). Cần ~8 dòng ở multi-agent §6.
5. **LỆCH: `present`/`calc` nằm server nào** — claude-sdk.md:318-319 đặt `present`+`calc` vào `ORCH_SERVER` (tên `mcp__orch__present`), lab-joint.md:399-401 đặt vào `COMMON_SERVER` (tên `mcp__common__present`) và tuyên bố "1 server common duy nhất". allowed_tools khớp string tuyệt đối → build theo 2 file là tool biến mất với 1 trong 2 agent. Phải chốt 1 (khuyên: `common` theo lab-joint, sửa claude-sdk §4 ví dụ).
6. **`turn_id` ai sinh, lúc nào** — streaming-sse.md:159,191 dùng làm khoá seq nhưng không nói sinh ở đâu (mỗi lượt main? uuid? map với message nào trong DB). 2-3 dòng ở streaming-sse §3.

## 4. Ba chỗ trùng NẶNG nhất (đọc trước khi cắt gì khác)

1. **Khoá lượt/interrupt/registry**: claude-sdk.md:397-459 vs multi-agent.md §1-§2+§7 — không chỉ trùng mà là **2 hiện thực khác nhau** (Lock vs slot+queue+drain; `_live_main` vs `main_registry`) cho cùng invariant "1 lượt/phòng". ~45-60 dòng + rủi ro build lệch. Chủ nhà: multi-agent.
2. **Schema builder + mount_role**: claude-sdk.md:323-377 vs lab-joint.md:161-239 — 2 bản copy **đã drift** (lab-joint xử `list[str]`, claude-sdk không). ~50 dòng. Chủ nhà: lab-joint.
3. **Phanh/approval**: 4 nơi (spec §4.4 · multi-agent §8 · lab-joint §2.1 · canvas-present §6) — wrapper gated ×2 bản code, endpoint decide ×2 bản code (hành vi 409 còn lệch nhau), narrative chuỗi ×3. ~45 dòng. Chia chủ nhà: spec = luật, canvas-present §6 = wrapper+card 2 mặt, multi-agent §8 = đường event/resume + decide.
