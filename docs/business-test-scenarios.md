# Kịch bản test theo luồng nghiệp vụ — SYSTEM #132 "BANK Digital"

> Tác giả: tester (author ≠ checker — mọi kết quả CHẠY THẬT do tester tự gọi tool/API/UI, không
> nhận lời khai implementer). Kiêm gate S11 (dispatch 19/7). Chạy trên **PROD
> `https://digital.tinhdev.com`** trừ khi ghi rõ khác. Một số luồng TÁI DẪN evidence từ vòng
> 6/6 hôm qua (18/7) — ghi rõ timestamp cũ, không lý thuyết suông (SPEC §5 D-... / CLAUDE.md §5).
>
> **Seed THẬT đã verify trực tiếp bằng SQL (2026-07-19, local DB tham chiếu schema — giá trị
> loan lấy từ LAB nên PROD có thể lệch, đã đối chiếu riêng khi chạy) — bài học script v3/v7:
> đừng tin câu mẫu trong demo-script.md có số tiền khớp seed, luôn query lại.**
> Account login-able (customer role; mật khẩu demo đã gửi riêng BTC, không đăng repo): **[KHÁCH-CN c001]** (C001 — Nguyễn
> Văn An, cá nhân, thu nhập khai 30tr/tháng) · **[KHÁCH-DN b001]** (B001 — Công ty TNHH Cơ khí Xưởng
> X, DN) · **[KHÁCH-CN c019]** (C019 — Huỳnh Văn Phong, cá nhân, lane-green tổ hợp DUY NHẤT theo
> comment `seed_users.py` dòng 24-26).
> Loan sở hữu bởi 3 account trên: **L001** (C001, 340.000.000, active) · **L007** (B001,
> 3.000.000.000, active) · **L108** (C019, 594.000.000, active). Loan khác (L002-L006, L101-...)
> thuộc owner KHÔNG có account login → không dùng được cho kịch bản chat thật.
> **Lệch với demo-script.md v8**: script ghi "L006 300 triệu" và "L007 1 tỷ" — SAI, seed thật
> L006=600tr/C003 (không login được), L007=3.000.000.000/B001. Đã báo finding — dùng số liệu
> SQL thật trong toàn bộ tài liệu này, KHÔNG dùng câu mẫu script cho số tiền.

## Bảng tổng PASS/FAIL — 8/8 luồng PASS (2026-07-19, gate S13/T13-4)

| # | Luồng | Happy | Từ chối | Biên | Authz | Trạng thái |
|---|---|---|---|---|---|---|
| 1 | Khách vay → 3 trụ → verdict có nguồn | ✅ | ✅ (giấy tờ thiếu) | — | — | PASS |
| 2 | Giải ngân GATED (phanh→phiếu→duyệt→đúng-1-lần) | ✅ tái dẫn | ✅ tái dẫn | ✅ tái dẫn | ✅ tái dẫn | PASS (tái dẫn) |
| 3 | Ma trận 3 tầng D-59 | ✅ 3a/3b/3d đủ 3 tầng | — | ✅ (case biên ca-ăn-tiền có assessment #id thật) | — | **PASS ĐỦ 3 TẦNG** |
| 4 | Khách MỚI vòng đời (register→form→C9xx→yellow→duyệt→mail+bell) | ✅ tái dẫn | — | ✅ tái dẫn (honest-null) | — | PASS (tái dẫn, ghép 2 nguồn) |
| 5 | 2 persona (khách 404-hide vs bank Tower) | ✅ tái dẫn | — | ✅ tái dẫn | ✅ tái dẫn | PASS (tái dẫn) |
| 6 | Read-scope 2 chiều (A không đọc B · tự tra mình OK) | ✅ tái dẫn | — | — | ✅ tái dẫn | PASS (tái dẫn) |
| 7 | Compare single vs multi (tab So sánh) | ✅ | — | ✅ (403 authz — lỗi thao tác, đã tự sửa) | ✅ (admin-only xác nhận) | PASS |
| 8 | Dashboard Tổng quan + Hồ sơ/lý do AI (T13-4) | ✅ | — | ✅ tab Hồ sơ đối chiếu chéo đúng | ✅ | PASS |

---

## Luồng 1 — Khách vay: chat → MAIN dispatch → 3 trụ credit/legal/products → verdict có nguồn

**Mục tiêu**: xác nhận MAIN fan-out đúng 3+ chuyên gia, mỗi card trên canvas có `source` trỏ về
tool-call gốc (SPEC §6 — "mọi con số nên kèm source"), không phải model tự bịa số.

**Actor**: khách (b001 — DN, để test fan-out đủ 3 trụ theo kịch bản script "vay lớn thế chấp"
đã proven; KHÔNG cần khoản vay lớn thật để trigger — chỉ cần câu hỏi đủ tín hiệu "khảo sát...
chưa chính thức").

**Tiền điều kiện**: DB PROD hiện tại (không cần reset) — account b001 (khách B001) đã tồn tại từ seed gốc.

**Các bước**:
1. Login `[KHÁCH-DN b001]` trên `https://digital.tinhdev.com`.
2. Mở ca mới, gõ nguyên văn (câu đã proven trong demo-script.md CẢNH 1, không đổi vì đây không
   liên quan số tiền loan-seed):
   `"Công ty tôi muốn vay 5 tỷ mở rộng sản xuất, thế chấp nhà xưởng — khảo sát nhanh giúp tôi:
   sức khoẻ tín dụng, pháp lý hồ sơ thế chấp, gói vay phù hợp. Chưa phải hồ sơ chính thức."`
3. Quan sát khối "Diễn tiến đội" — đếm số sub-agent được dispatch (kỳ vọng ≥3: credit/legal/
   products), xem tool call 🔧 thật (không chỉ 🧠 suy nghĩ).
4. Đợi canvas render card — đọc từng card, xác nhận có trường `source`/`sources` trỏ đúng tên
   tool (không phải id bịa — SPEC §6 "mọi id do VỎ inject").
5. Case con — **biên**: hỏi 1 câu KHÔNG đủ thông tin (không nêu mục đích/tài sản) → kỳ vọng
   Pháp chế dừng hỏi lại (luật SKILL legal #3/#6), không tự đoán.
6. Case con — **từ chối/honest-null**: dựa vào finding sẵn có — khách C001 tra công an CHƯA có
   bản ghi → hệ phải nói "chưa xác minh được", KHÔNG đoán sạch/bẩn (đã quan sát trong rehearsal
   18/7, ghi trong demo-script.md CẢNH 2 Nhịp C — tái xác nhận bằng câu hỏi trực tiếp legal
   khía cạnh cho C001 nếu cần).

**Kết quả kỳ vọng**: ≥3 sub dispatch song song hoặc tuần tự (D-52 — cả 2 cách đều đạt), mọi card
có source, case thiếu info → hỏi lại, case honest-null → "chưa xác minh được" không bịa.

**Kết quả CHẠY THẬT — PASS.** Chạy 19/7, [KHÁCH-DN b001] trên PROD, câu chat NGUYÊN VĂN đúng bước 2.
- **1 finding hạ tầng thoáng qua (không FAIL luồng)**: lần gõ đầu tiên (~00:xx) gặp `HTTP 502`
  từ `/api/health` VÀ khi gửi câu hỏi — trang lỗi Cloudflare gateway, không phải app. Retry
  `/api/health` 10s sau → 200 sạch. Login lại + gõ lại câu → chạy trọn vẹn không lỗi. Đây là
  tunnel/upstream blip thoáng qua (1 lần, tự phục hồi trong <20s, không lặp lại) — ghi vào sổ
  ngoại lệ §6b, không chặn.
- Fan-out đúng 3 chuyên gia song song (Tín dụng/Pháp chế/Sản phẩm) — "Diễn tiến đội 31 bước ·
  🔧14 · 🧠17", MAIN báo tiến độ từng chuyên gia xong (✅) trước khi tổng hợp cuối.
- Canvas 5 card đều có `source` chip trỏ tool thật: `credit_assess`, `credit_cic_get`,
  `mcp__banking_legal_...` — đúng SPEC §6.
- Case biên thiếu-info: card "Giấy tờ pháp lý — Vay thế chấp nhà xưởng" đánh dấu ✗ đúng 2 mục
  thiếu (Giấy CN quyền sở hữu tài sản, Chứng thư định giá) — không tự bịa "coi như đủ".
  Mục đích vay "Mở rộng sản xuất" → card Metric đánh `Conditional (Có điều kiện)` ✗ Không đạt —
  đúng seed `business_expansion=conditional`, không tự đoán pass.
- Verdict document cuối liệt kê đủ 3 mảnh (Tín dụng/Pháp lý/Gói vay khuyến nghị), mỗi dòng có
  `(source: tool_name)` cụ thể.

---

## Luồng 2 — Giải ngân GATED: phanh → phiếu → bank duyệt → đúng-1-lần → biên nhận

**Mục tiêu**: xác nhận wrapper gated (SPEC §4.4) chặn ở TẦNG TOOL (không cược prompt), phiếu
approval chỉ vỏ tự sinh, resume đúng 1 lần, decide-twice → 409, cross-owner → `not_your_loan`.

**Actor**: khách (b001) + bank (admin).

**Tiền điều kiện**: L007 (B001, 3.000.000.000) đủ điều kiện test nhánh "vượt ngưỡng" (>2 tỷ →
luôn human theo tầng 3, xem Luồng 3). Dùng cho luồng 2 vì đã có evidence sẵn từ S3 gate + hôm
qua điểm 2.

**Case con + evidence TÁI DẪN** (không chạy lại — dữ liệu cũ đã đủ điều kiện, chạy lại sẽ chỉ
tốn 1 lần thao tác giống hệt, đúng chỉ đạo "đừng đốt vòng lặp vô ích"):

| Case | Evidence cũ | Kết quả |
|---|---|---|
| Happy (phiếu → duyệt → resume đúng 1 lần) | S3 gate 4/4 browser+PG (happy/reject/decide-twice/authz 12/12), commit `87d9e18→2ab26a4`. Tái xác nhận hôm qua (19/7... thực ra 18/7) điểm 2: c019 disburse L108 594tr → phiếu `35559d5b-7...` → admin duyệt qua Control Tower 23:05:26-23:06:50 → resume "Đã giải ngân thành công" 16:30:49 UTC | PASS |
| Từ chối (admin bấm ✗ Từ chối) | S3 gate reject case, `end_sprint_3.md` | PASS |
| Biên — decide-twice (duyệt/từ chối phiếu ĐÃ quyết lần 2) | S3 gate decide-twice→409 | PASS |
| Authz — khác chủ (`not_your_loan`) | Hôm qua (18/7) điểm 2 re-verify sau Fix E: 23:05:26-23:06:50, format đúng `not_your_loan`, không lộ số liệu. Nguồn: SendMessage verdict tổng gửi architect cùng ngày | PASS |

**Kết quả CHẠY THẬT**: PASS (tái dẫn 100% — 4/4 case con có evidence timestamp cụ thể, không
lý thuyết suông). Không cần chạy mới trừ khi architect/user muốn timestamp hôm nay.

---

## Luồng 3 — Ma trận 3 tầng D-59: <500tr auto · 500tr-2 tỷ (xanh tự duyệt, dẫn assessment #id) ·
## >2 tỷ luôn người

**Mục tiêu**: xác nhận `AUTO_APPROVE_THRESHOLD=500_000_000` và `auto_approve_max_vnd` (2 tỷ)
hoạt động đúng 3 nhánh, nhánh xanh phải dẫn `assessment #id` cụ thể trên phiếu.

**Actor**: khách c001 (tầng 1) · c019 (tầng 2) · b001 (tầng 3).

**Tiền điều kiện — ĐÃ VERIFY SQL THẬT (không tin script)**:
- Tầng 1: **c001/L001, 340.000.000** (individual, <500tr, không red theo assessment mặc định
  → auto).
- Tầng 2 xanh: **c019/L108, 594.000.000** — nhưng CẦN legal_classify_profile ra lane=green
  TRƯỚC (mục đích "mua nhà ở"/`residential_purchase` not_restricted, KHÔNG nói "mở rộng kinh
  doanh" — business_expansion là `conditional`→yellow, bài học T7-4). Nếu KHÔNG chạy assessment
  trước hoặc lane≠green → rơi vào nhánh "500tr-2tỷ nhưng chưa xanh" = human (đã có evidence hôm
  qua, xem bảng dưới).
- Tầng 3: **b001/L007, 3.000.000.000** (>2 tỷ) — luôn human BẤT KỂ lane, kể cả nếu DN đạt xanh
  tuyệt đối (thực tế DN KHÔNG BAO GIỜ xanh — `legal/functions.py` ÁN-L-F2: business luôn
  `employment=yellow` cứng, "chưa có cơ chế xác minh BCTC DN" — nên tier-3 business luôn double-
  chặn: vừa do >2 tỷ vừa do never-green).

**Các bước (chạy MỚI — luồng này dispatch yêu cầu cover trọn cả 3 tầng)**:

### 3a — Tầng 1 (<500tr, auto)
1. Login `[KHÁCH-CN c001]`.
2. Gõ: `"Giải ngân khoản vay L001 số tiền 340 triệu đồng."`
3. Kỳ vọng: card tự động duyệt trong ~15s, KHÔNG cần admin, phiếu `decided_by='auto-rule'` +
   lý do "dưới ngưỡng 500 triệu".
4. Case biên: nếu C001 có lane=red (kiểm tra trước — nếu C001 chưa có assessment thì lane mặc
   định không phải red, auto vẫn chạy theo tầng 1 "auto trừ khi lane=red" — chỉ có RED mới chặn
   tầng 1, không cần xanh).

### 3b — Tầng 2 xanh (500tr-2 tỷ, auto SAU KHI xanh, dẫn assessment #id)
1. Login `[KHÁCH-CN c019]`.
2. Gõ: `"Tôi muốn vay 594 triệu mua nhà ở, vay tín chấp không thế chấp — thẩm định hồ sơ giúp
   tôi theo quy trình."` (đúng nguyên văn demo-script CẢNH 2 Nhịp C — mục đích + loại vay rõ để
   Legal không dừng hỏi thêm).
3. Đợi Pháp chế chạy 3 trụ thật (police/CIC/employment) → `legal_classify_profile` ghi sổ →
   kỳ vọng lane=**green**.
4. Gõ tiếp: `"Giải ngân khoản vay L108 số tiền 594 triệu."`
5. Kỳ vọng: **✅ TỰ ĐỘNG DUYỆT** dù 594tr > 500tr, phiếu `auto-rule`, lý do trích **"Hồ sơ XANH —
   assessment #N"** (N là id thật ghi trong DB — soát bằng SQL sau khi chạy, không chỉ tin text
   UI).
6. **⚠️ Lưu ý vận hành**: L108 là loan single-use trong ngữ cảnh demo — nếu đã disburse rồi (như
   hôm qua) cần architect restore trạng thái `active` + xoá approval cũ TRƯỚC khi chạy bước
   này (đã làm 1 lần hôm qua, biên lai `[GO]` từ architect). Xác nhận trạng thái trước khi gõ
   bước 4-5, tránh lặp lỗi "tool trả biên nhận cũ không mail mới".

### 3c — Tầng 2 CHƯA xanh (500tr-2 tỷ, chưa/không xanh → human) — TÁI DẪN
Evidence hôm qua (18/7) trước khi chạy legal: c019/L108 594tr, C019 CHƯA có assessment trên DB
fresh → phiếu CHỜ NGƯỜI đúng ma trận (không auto dù cùng khoảng tiền tầng 2) — id phiếu
`95ab555e-6...`, đúng nguyên tắc "auto CHỈ khi lane=green" (tầng 2 không có nhánh yellow-auto).
**Kết quả**: PASS (tái dẫn).

### 3d — Tầng 3 (>2 tỷ, luôn người bất kể lane)
1. Login `[KHÁCH-DN b001]`.
2. Gõ: `"Giải ngân khoản vay L007 số tiền 3 tỷ đồng."`
3. Kỳ vọng: phiếu CHỜ NGƯỜI ngay cả khi (giả định) DN đạt lane xanh — thực tế DN luôn yellow
   (ÁN-L-F2) nên đây là double-guard; ghi rõ trong evidence nhánh nào chặn (ngưỡng hay lane).
4. Admin duyệt → resume → biên nhận.
5. **Sau khi xong: KHÔNG cần restore L007** (không phải case tái dùng bắt buộc cho luồng khác —
   nhưng nếu B001 cần dùng lại cho Luồng 1 fan-out demo sau, ghi chú trạng thái cuối).

**Kết quả CHẠY THẬT**:
- **3a PASS** (chạy 19/7, [KHÁCH-CN c001] trên PROD): gõ "Giải ngân khoản vay L001 số tiền 340 triệu
  đồng." → auto duyệt trong ~10s, biên nhận DOCUMENT card xác nhận `Tự động (auto-rule)` +
  "Tự động duyệt theo rule: số tiền dưới ngưỡng 500,000,000 VND", timestamp
  `18/07/2026 17:36:44 (UTC)`. Không cần admin can thiệp.
- **3d PASS** (chạy 19/7, [KHÁCH-DN b001] trên PROD): gõ "Giải ngân khoản vay L007 số tiền 3 tỷ đồng."
  → ngay lập tức "Đã gửi chờ duyệt" (KHÔNG auto dù bất kỳ lane nào — đúng tầng 3 luôn human) →
  phiếu Tower `af299c95-2...` `{"amount":3000000000,"loan_id":"L007"}` → admin duyệt → resume
  tự động → "GIẢI NGÂN THÀNH CÔNG" 18/07/2026 17:43:19 (UTC), mỗi dòng kết quả đều có
  `source: disburse` trên UI (không chỉ trong log nội bộ — hiển thị ngay cho khách).
- **Bằng chứng phụ (ngoài kế hoạch, giữ vì có giá trị xác nhận ÁN-L-F2)**: do thao tác lệch tab,
  vô tình chạy câu legal "594 triệu mua nhà ở, tín chấp" trên chính b001 (DN) thay vì c019 (cá
  nhân) — kết quả: Tín dụng ĐẠT (DSCR 48.68) nhưng Pháp lý ra **YELLOW cứng** với lý do nguyên
  văn "Hệ thống chưa có cơ chế xác minh báo cáo tài chính doanh nghiệp (BCTC) — đây là hạn chế
  hệ thống, không phải lỗi khách. Khoản vay DN theo chính sách luôn cần người duyệt." — xác
  nhận trực tiếp ÁN-L-F2 (business luôn yellow cứng, không bao giờ đạt green) bằng lời của chính
  MAIN, không phải suy diễn từ code.
- **3b (tier-2 green) — PASS, ĐÂY LÀ CA ĂN TIỀN CỦA CẢ MA TRẬN**: sau khi architect restore
  L108 (active + xoá approval cũ, biên lai 1/1), chạy TRỌN 2 bước liền mạch trên 1 tab duy nhất
  c019 (rút kinh nghiệm cookie-flip đã gặp 2 lần trước đó — không mở tab persona khác song
  song):
  1. **Legal classify** — gõ "Tôi muốn vay 594 triệu mua nhà ở, vay tín chấp không thế chấp —
     thẩm định hồ sơ giúp tôi theo quy trình." → 3 trụ chạy tuần tự thật (Tín dụng trước, Pháp
     lý sau dùng ngữ cảnh tín dụng) → **Tín dụng ELIGIBLE** (DSCR 1.464 ≥ 1.2, CIC Nhóm 1) →
     **Pháp lý: 🟢 AUTO_APPROVE_ELIGIBLE**, cả 7 trụ PASS/CLEAR/ELIGIBLE (nhân thân, tiền án,
     CIC, việc làm&lương lệch 7.4% trong ngưỡng, giấy tờ, mục đích "Mua nhà" not_restricted,
     tín dụng) — xác nhận RÕ RÀNG bằng text trước khi qua bước 2, không giả định.
  2. **Disburse L108 594tr** — MAIN hỏi làm rõ 1 câu (nhầm giữa "khoản mới vừa thẩm định" và
     "khoản L108 cũ" — vì restore đưa L108 về active với dư nợ hiển thị 549.559.085đ, khác số
     594tr đang bàn) → trả lời rõ "Chính khoản vay mã L108 594 triệu" → MAIN tiếp tục đúng.
     Kết quả: **TỰ ĐỘNG duyệt dù 594tr > 500tr ngưỡng**, KHÔNG cần admin. Biên nhận canvas
     "Biên nhận giải ngân — L108" ghi rõ: `Phê duyệt: Tự động (AUTO-APPROVED)` ·
     **`assessment #5 — lane green, auto_approve_eligible`** · `Ghi chú: Hồ sơ XANH — đủ điều
     kiện giải ngân tự động` · timestamp mới `18/07/2026 18:00:39 (UTC)` (khác hẳn timestamp cũ
     16:30:49 hôm qua — xác nhận chạy mới, không phải cache). Tờ trình DOCUMENT card đầy đủ
     citation `[source: credit_assess]`, `[source: legal_classify_profile]`,
     `[source: credit_cic_get]`, `[source: cust_get]`, `[source: calc]` cho từng dòng số liệu.
  **assessment #5 chính là số N thật** phân biệt tier-2-green (auto dù vượt ngưỡng) với tier-1
  (auto vì dưới ngưỡng, không cần assessment) — đúng điểm ăn tiền dispatch yêu cầu chứng minh.

---

## Luồng 4 — Khách MỚI vòng đời: register → form → C9xx → yellow honest-null → duyệt → mail (From
## "BANK Digital") + bell

**Mục tiêu**: xác nhận khách hoàn toàn mới (0 hồ sơ) tự đăng ký, nộp form, ra hồ sơ vàng
honest-null (thiếu giấy tờ xác minh — KHÔNG đoán sạch/bẩn), và khi có mail thật thì brand đúng
"BANK Digital" đồng nhất From/subject/body.

**Actor**: khách mới (đăng ký live) cho phần 1-3; khách c019 (đã có email gán sẵn) cho phần
mail-brand — vì fresh customer KHÔNG SỞ HỮU LOAN nào (chỉ có assessment), không thể tự đi hết
tới bước duyệt→mail trong 1 account (đã thử và dừng đúng lúc hôm qua — xem NGHI VẤN dưới).

**Ghép 2 nguồn evidence** (không chạy lại vì đã đủ + tránh đốt thêm account/DB rác):

| Đoạn | Evidence | Nguồn |
|---|---|---|
| Register → form 6-field → C9xx | T9-4 (18/7) 6 bước PASS local: "register khách mới, form intake present_form, thẩm định khách mới → yellow honest-null" | `end_sprint_9.md` T9-4 |
| Yellow honest-null (thiếu CCCD/thu nhập/cư trú, KHÔNG đoán) | T9-4 local + tái xác nhận trên PROD hôm qua với t9go1: MAIN trả lời rõ "chưa có mã khoản vay... thiếu CCCD, chứng minh thu nhập, xác nhận cư trú, CIC chưa có bản ghi" — không tự nhận giấy tờ qua lời khai chat (đúng luật SKILL legal cấm bịa) | phiên tester 18-19/7, trực tiếp |
| Mail thật "BANK Digital" đồng nhất From/subject/body | Hôm qua 19/7 00:30 (giờ hệ 16:30 UTC): c019 (đã gán email SMTP_USER) disburse L108 594tr → duyệt → 2 mail mới From="BANK Digital", so sánh trực tiếp với 2 mail cũ From="SHB Digital" còn nằm nguyên cùng inbox làm chứng | verdict tổng gửi architect, msg 19/7 |
| Bell badge/dropdown | T9-4 bước 5 — verify bằng `get_page_text` (screenshot không chụp được layer dropdown, giới hạn công cụ đã ghi) | `end_sprint_9.md` T9-4 |

**NGHI VẤN đã xác nhận KHÔNG PHẢI bug (structural, đúng thiết kế Fix E)**: một khách vừa mới
đăng ký (có email) không sở hữu loan nào trên DB fresh — chỉ có sau khi admin/seed gán riêng.
Đường "register→...→mail" liền mạch 1 account chỉ chạy được khi DB ở trạng thái demo cũ (trước
Fix E siết read/write-scope) — sau Fix E, phải ghép 2 account (1 để chứng minh lifecycle-tới-
yellow, 1 đã có email+loan sẵn để chứng minh mail-brand) mới đủ, đây là lý do bảng trên tách
2 dòng nguồn.

**Kết quả CHẠY THẬT**: PASS (ghép 2 nguồn, cả 2 đều có timestamp + evidence cụ thể).

---

## Luồng 5 — 2 persona: khách 404-hide + không nút duyệt vs bank mọi ca + Tower

**Mục tiêu**: xác nhận customer role KHÔNG thấy Control Tower, KHÔNG có nút duyệt trên phiếu của
mình; admin thấy MỌI ca + Tower + nút duyệt.

**Case con + evidence TÁI DẪN**:

| Case | Evidence | Kết quả |
|---|---|---|
| Khách không thấy Tower/nút duyệt (404-hide) | S8 gate: matrix 7/7 + e2e 2-phía, "cửa KHÁCH (customer khoanh, 404-hide, MAIN inject danh tính, card 'chờ ngân hàng')", `end_sprint_8.md` | PASS |
| Bank thấy mọi ca + Tower + duyệt | S8 gate cùng nguồn: "NGÂN HÀNG (admin mọi ca + Tower + duyệt + badge phiếu-bay poll)" | PASS |
| Screenshot trực tiếp hôm qua — admin login thấy nút "🗼 Control Tower" trên header, khách (c019) KHÔNG có nút này | Ảnh chụp phiên 18/7 22:xx (điểm 1 picker) + xác nhận lại lúc duyệt L108 (23:05-23:06, admin thấy Tower, c019 UI không có) | PASS |
| Badge phiếu-bay poll ≤5s | S8 rehearsal delta C1 2'10" | PASS |

**Kết quả CHẠY THẬT**: PASS (tái dẫn — cả S8 gate lẫn quan sát trực tiếp hôm qua đều nhất quán).

---

## Luồng 6 — Read-scope 2 chiều: khách A không đọc data khách B · tự tra mình OK

**Mục tiêu**: xác nhận Fix E (choke point tầng mount) chặn đúng CẢ 2 hướng — tool ghi
(`disburse`) VÀ tool đọc (`credit_assess`, `cust_search`) không rò dữ liệu chéo khách; đồng thời
KHÔNG false-positive khi khách tự hỏi hồ sơ chính mình.

**Case con + evidence TÁI DẪN** (điểm 2/3 hôm qua, sau Fix E — đây CHÍNH LÀ finding nghiêm
trọng nhất dự án nên evidence rất kỹ, không cần chạy lại):

| Case | Evidence | Kết quả |
|---|---|---|
| Chặn cross-owner qua tool GHI (`disburse`) | 18/7 23:05:26-23:06:50: t9prod1 gõ giải ngân loan của C001 → `not_your_loan`, đúng format, không lộ số liệu | PASS |
| Chặn cross-owner qua tool ĐỌC trực tiếp (`credit_assess`) | 18/7 23:07:14-23:13:39: hỏi thẳng DSCR/thu nhập của khách khác → `not_your_data`, không lộ số liệu | PASS |
| Chặn cross-owner qua tool ĐỌC gián tiếp (`cust_search`) | Cùng phiên 23:07:14-23:13:39 — tìm khách khác qua search cũng bị chặn `not_your_data` | PASS |
| Tự tra hồ sơ CHÍNH MÌNH vẫn chạy bình thường (không false-positive) | Cùng phiên — hỏi hồ sơ chính t9prod1/c019 → chạy bình thường, không bị chặn nhầm | PASS |
| **Trước Fix E — bằng chứng lỗ hổng THẬT (không phải config)**: đăng ký khách mới, gõ giải ngân loan người khác → MAIN không từ chối mà HIỂN THỊ THẲNG DSCR=3.709, thu nhập, nợ của khách không liên quan | 18/7 vòng GO đầu — finding quan trọng nhất dự án, architect xác nhận là lỗ hổng thật, không phải bug config | Đã VÁ (Fix E), tái xác nhận PASS sau vá |

**Kết quả CHẠY THẬT**: PASS (tái dẫn, evidence đầy đủ nhất trong 7 luồng — đây là luồng tester
tự phát hiện lỗ hổng nên có track record kỹ nhất).

---

## Luồng 7 — Compare single-LLM vs multi-agent (tab So sánh)

**Mục tiêu**: xác nhận tab So sánh chạy song song 1 LLM trần (0 tool) vs cả đội (multi-tool, có
nguồn), kết quả hiển thị đối lập rõ (silent hallucination vs sourced answer).

**Actor**: bất kỳ account nào có quyền vào tab So sánh (theo script — cửa PHẢI/bank, hoặc kiểm
tra lại quyền thật khi chạy vì đây là điểm CHƯA verify).

**Tiền điều kiện**: PROD hiện tại, không cần state đặc biệt.

**Các bước (chạy MỚI)**:
1. Login (xác nhận role nào thấy tab "So sánh" — ghi finding nếu khác kỳ vọng demo-script).
2. Gõ câu demo-script đã proven: `"Khách C001 vay 500 triệu được không?"`
3. Chạy, đợi cả 2 cột hoàn tất (~70s theo script).
4. Case biên — đối chiếu: cột 1-LLM-trần kỳ vọng KHÔNG gọi tool, trả lời chung chung/không tra
   được hồ sơ thật (hoặc bịa số — ghi rõ hành vi thật quan sát được, không suy đoán). Cột multi-
   agent kỳ vọng có DSCR thật + nguồn tool.
5. Case biên — nếu 1-LLM-trần vô tình bịa số cụ thể (hallucination) → đây CHÍNH LÀ điểm giá trị
   của demo, ghi lại nguyên văn làm bằng chứng đối lập.

**Kết quả CHẠY THẬT — PASS** (chạy 19/7, [ADMIN] trên PROD, tab Control Tower → "So sánh 1
vs đội"):
- **Authz xác nhận đúng chuẩn ngay từ lần thử đầu**: tab So sánh CHỈ nằm trong Control Tower
  (admin/bank), KHÔNG có ở workspace khách — đúng script.
- **Case biên phát hiện thêm (không cố ý)**: 2 lần gọi đầu `POST /api/compare` trả
  **403 `{"code":"forbidden","message":"Chỉ quản lý (admin) được thao tác này.","hint":"Đăng
  nhập bằng account admin.","retryable":false}`** — envelope 4-field đúng chuẩn SPEC §5. NGHI
  VẤN VÀ TỰ SỬA: root cause là lỗi thao tác của tester (nhiều tab MCP dùng chung cookie theo
  domain — tab admin bị 1 tab khác login `b001` ghi đè cookie giữa chừng do chạy song song
  Luồng 3d). Xác nhận qua `GET /api/me` trên đúng tab lúc lỗi → trả về `{"username":"b001",
  "role":"customer"}` dù trước đó đã login admin — đúng là session bị ghi đè, KHÔNG phải bug
  compare/authz. Login lại admin TRÊN ĐÚNG TAB (không chạy song song tab khác) → chạy sạch.
  Đây là bài học vận hành cho các luồng test sau: KHÔNG chạy 2 persona trên 2 tab MCP song song
  nếu cả 2 cần giữ session lâu — cookie domain dùng chung sẽ ghi đè nhau.
- **Kết quả chạy thật đối lập rõ** (câu demo-script: "Khách C001 vay 500 triệu được không?"):
  - **1 LLM trần**: 6.67s, **0 tool**, 💰0.0053 — trả lời chung chung, tự nhận "không có công cụ
    tra cứu dữ liệu khách hàng", liệt kê điều kiện CHUNG CHUNG (không phải số liệu C001 thật).
    Không bịa số cụ thể (an toàn) nhưng vô dụng cho quyết định thật.
  - **Cả đội (multi-agent)**: 75.27s, **🔧9 tool, ▦3 card**, verdict có nguồn cụ thể: Tín dụng
    ✅ ĐẠT (DSCR 2.522, CIC nhóm 1, trả/tháng 11.894.965 VND), Pháp lý ⚠️ CHƯA ĐẠT — phát hiện
    case biên honest-null: "thiếu dữ liệu công an (chưa tra được nhân thân/tiền án)" →
    **"KHÔNG ĐỀ XUẤT GIẢI NGÂN tại thời điểm này"**, đề xuất hành động cụ thể "xác minh tay với
    cơ quan công an". Đây là bằng chứng mạnh nhất cho deliverable #5: multi-agent không chỉ
    nhanh/nhiều tool hơn mà còn TỪ CHỐI kết luận khi thiếu bằng chứng — đúng tinh thần "tin
    được" hơn "trả lời được".
  - Có `conv_id` thật `e6051d79-7...` truy vết được ở Workspace.

---

## Luồng 8 — Dashboard Tổng quan + Hồ sơ/lý do AI (T13-4, Control Tower 6 tab)

**Mục tiêu**: xác nhận tab "Tổng quan" (7 KPI) và "Hồ sơ + lý do AI" (list assessment + panel
criteria 3 trụ) ăn ĐÚNG dữ liệu thật từ 7 luồng đã chạy — đối chiếu chéo với nguồn độc lập
(Nhật ký tool-call, `/api/approvals?status=pending`), không tin số hiển thị suông (SPEC §5).

**Actor**: bank (admin) cho tab dashboard; customer (c001) cho case authz.

**Tiền điều kiện**: PROD sau khi 7 luồng trước đã chạy (assessments/approvals đã có data thật,
KHÔNG cần seed thêm — đúng như dispatch mô tả).

**Case con + kết quả CHẠY THẬT:**

### 8a — Tab Tổng quan, đối chiếu chéo — ✅ PASS (sau khi làm rõ false alarm)
**Vòng 1 (nghi FAIL)**: `GET /api/stats?window=today` và `window=7d` đều trả
`{"approvals":{"approved":0,...,"auto":0},"assessments":{"green":1,"yellow":4,"red":0},...}`
trong khi Nhật ký tool-call (111 dòng) xác nhận ≥6 lệnh `operations disburse` thành công trong
ngày — badge "PHIẾU ĐÃ DUYỆT"/"trong đó AUTO" = 0 trông như sai. Đã đọc kỹ `stats.py` +
`store_approvals.py` + `gated.py` để khoanh vùng (logic trên giấy đúng cả 2 nhánh auto/admin),
báo [FAIL] đầy đủ 5 mục kèm 3 giả thuyết cụ thể.

**Root cause thật (architect xác nhận)**: KHÔNG phải bug — sau khi tester chạy xong 7 luồng đầu
(hôm 18/7), architect đã dọn prod cho vòng T13-4: restore 3 loan (L001/L007/L108) về `active` +
**`DELETE FROM approvals`** cho cả 3 (đúng như biên lai "approvals 0 — khỏi dọn thêm" gửi trước
đó). Bảng `approvals` RỖNG THẬT trên prod tại thời điểm tester đọc → `stats` trả 0 là **đọc
đúng ground-truth**, không phải bug đếm. `assessments` đếm đúng vì bảng đó KHÔNG bị dọn.
`tool_calls` (Nhật ký tool) là log append-only riêng, không chung vòng đời với `approvals` —
đối chiếu chéo bằng 2 nguồn khác bảng là đúng phương pháp, chỉ là ground-truth đã đổi giữa lúc
chạy 7 luồng và lúc đọc dashboard.

**Vòng 2 (re-verify bằng data tươi, PASS)**: login c001 → "Giải ngân khoản vay L001 số tiền 340
triệu đồng." → auto-rule duyệt, timestamp **MỚI** `18/07/2026 lúc 18:50` (khác 17:36:44 cũ —
xác nhận sự kiện tươi) →
- `GET /api/stats?window=today` (no-store): `{"approved":1,"rejected":0,"pending":0,"auto":1}`
  — nhảy đúng approved=1, auto=1 ngay sau khi có sự kiện thật.
- UI tab "Tổng quan": **"PHIẾU ĐÃ DUYỆT: 1 ↑1"**, **"trong đó AUTO: 1"**, "CA TƯ VẤN: 13" (tăng
  từ 12) — khớp UI lẫn API, không lệch.

**Note vận hành (architect yêu cầu ghi cho người sau)**: reset/dọn bảng `approvals` (vd trước
demo thật) → KPI "PHIẾU ĐÃ DUYỆT"/"trong đó AUTO" về 0 và sẽ NHẢY LIVE theo từng sự kiện duyệt
mới trong lúc demo — đây là HÀNH VI ĐÚNG THIẾT KẾ (approvals = trạng thái hiện tại của bảng,
`tool_calls` = lịch sử append-only không bao giờ bị dọn — 2 bảng khác vòng đời). Sau
`reset_demo` trước giờ G, KPI sẽ 0 và tăng dần theo đúng nhịp demo — đây là điểm KỂ CHUYỆN tốt
cho giám khảo ("số liệu sống, không phải fixture tĩnh"), KHÔNG phải bug cần lo.

### 8b — Tab Hồ sơ + lý do AI, đối chiếu chéo — ✅ PASS
List "Hồ sơ thẩm định + lý do AI (5)" hiện đúng 5 bản ghi khớp 100% với dữ liệu 7 luồng tự tạo:
1 GREEN (C019 · 594 triệu · 17:58) + 4 YELLOW (C001 500tr, B001 594tr, C901 200tr ×2).
- Click bản **GREEN (C019)**: panel hiện đủ 7 tiêu chí ✓ (identity/criminal/cic/employment/
  docs/purpose/credit) + "🤖 Lý do AI" — khớp chính xác kết quả Luồng 3b vừa chạy trước đó
  (assessment #5, lane green, "mua nhà ở"→not_restricted).
- Click bản **YELLOW (C001, 500tr)**: panel tương phản rõ — **⚠ identity "chưa tra được bản ghi
  công an — cần xác minh tay"**, **⚠ criminal "chưa tra được tiền án"** — khớp CHÍNH XÁC finding
  honest-null đã ghi trong Luồng 1 hôm trước (tester C001 tra công an CHƯA có bản ghi → hệ nói
  "chưa xác minh được", KHÔNG đoán sạch/bẩn). Đây là đối chiếu chéo mạnh nhất trong Luồng 8 —
  dữ liệu UI khớp 1-1 với hành vi hệ thống đã quan sát trực tiếp trước đó, không phải suy diễn.

### 8c — Authz customer → 403 — ✅ PASS
`c001` (customer) gọi trực tiếp:
- `GET /api/stats?window=today` → **403** `{"code":"forbidden","message":"Chỉ quản lý (admin)
  được thao tác này.","hint":"Đăng nhập bằng account admin.","retryable":false}`
- `GET /api/assessments` → **403** cùng envelope.
UI: reload với session c001 → header KHÔNG có nút "🗼 Control Tower" (regression giữ nguyên từ
D-56/S8, khách không bao giờ thấy Tower).

### 8d — Theme dark/light — ✅ PASS
Toggle 🌙/☀️ trên Control Tower: cả tab "Tổng quan" (7 card KPI, border màu green/yellow/red
giữ đúng) và "Hồ sơ + lý do AI" (list + panel 7 tiêu chí + card "Lý do AI" nền tím) đều
render sạch ở dark theme — không mất chữ/mất contrast, không cần fix.

### 8e — Regression 5 tab cũ — ✅ PASS
Click qua lần lượt "Hàng chờ duyệt" (0, khớp API) · "Nhật ký tool" (111 dòng, nguyên vẹn) ·
"Trạng thái đội" (12 ca, khớp `conversations.total`) · "So sánh 1 vs đội" (còn nguyên nút "▶
Chạy so sánh", không lỗi) — không tab nào vỡ do thêm 2 tab mới.

### Poll không error-loop — ✅ PASS
Đứng ở tab Tổng quan hơn 40s (>30s dispatch yêu cầu): `read_network_requests` xác nhận
`GET /api/stats?window=today` tự gọi lại ≥2 lần, cả 2 đều status 200; `read_console_messages`
(onlyErrors) = rỗng — không error-loop, không exception JS.

**Kết luận Luồng 8**: 6/6 case con PASS. 8a trải qua 2 vòng — vòng 1 nghi FAIL (điều tra kỹ,
báo đúng người, KHÔNG đoán), vòng 2 re-verify bằng data tươi xác nhận đây là false alarm do
ground-truth (bảng `approvals`) bị dọn giữa 2 lần tester chạy, không phải bug logic. Quy trình
điều tra vẫn có giá trị: chứng minh code đúng trên giấy + chốt đúng root cause thật bằng 1 vòng
re-verify rẻ (login → disburse → so API/UI trước-sau), đúng tinh thần CLAUDE.md §6b "nghi môi
trường/ground-truth trước khi nghi code, mỗi nghi án kết bằng 1 hành động kiểm rẻ".

---

## Trạng thái DB prod sau khi chạy hết 8 luồng (19/7) — cho người sau đọc trước khi tự chạy lại

**Lưu ý quan trọng cho người sau**: giữa lúc tester chạy 7 luồng đầu và lúc chạy Luồng 8
(T13-4), architect ĐÃ dọn 1 lần: restore 3 loan (L001/L007/L108) về `active` + `DELETE FROM
approvals` cho cả 3 — đây chính là lý do 8a từng nghi FAIL rồi xác nhận false alarm (xem chi
tiết ở mục Luồng 8 phía trên). Bảng dưới phản ánh trạng thái SAU CÙNG (sau cả dọn lẫn re-verify
Luồng 8), không phải chồng lịch sử tất cả lần chạy.

| Loan | Trạng thái cuối cùng | Do luồng nào | Cần dọn trước khi tái sử dụng? |
|---|---|---|---|
| L001 (C001, 340tr) | Đã restore active bởi architect SAU đóng S13 (disburse lần 2 của re-verify 8a đã được dọn — biên lai: 3/3 loans active, 1 approval auto giữ làm mồi dashboard) | 3a + re-verify 8a (đã restore) | Không — đang active sẵn, sạch để dùng |
| L007 (B001, 3 tỷ) | Đã restore active bởi architect (approvals đã xoá), CHƯA disburse lại từ đó | 3d (đã restore) | Không — đang active sẵn, sạch để dùng |
| L108 (C019, 594tr) | Đã restore active bởi architect (approvals đã xoá), CHƯA disburse lại từ đó | 3b (đã restore) | Không — đang active sẵn, sạch để dùng |
| B001 assessment (594tr, DN, YELLOW) | 1 assessment "lệch" tồn tại do lỗi cookie-flip (Luồng 3b nháp đầu) — vô hại, chỉ là 1 row assessment thừa. Bảng `assessments` KHÔNG bị dọn nên vẫn còn | Sự cố thao tác, không phải luồng chính thức | Không bắt buộc dọn — không ảnh hưởng logic, nhưng có thể gây nhiễu nếu ai đó query "assessment mới nhất của B001" mong đợi thấy đúng 1 cái |

**Account test tạo mới trong các phiên trước (18-19/7), CHƯA được architect xác nhận dọn:**
t9prod1, t9go1 (từ phiên 18/7) — không tự ý xoá, chờ quyết định.

**Đề xuất dọn 1 lần cuối (không tự làm — cần architect duyệt vì đụng DB prod):**
`reset_demo` KHÔNG dùng được ở đây (sẽ xoá luôn account/loan seed cần cho demo thi thật 17-19/7
theo CLAUDE.md) — nên dọn thủ công: restore 3 loan trên về `active` + xoá approval liên quan,
giữ nguyên account test (không xoá, chỉ đánh dấu nếu cần).

## Ghi chú vận hành chung

- Toàn bộ chat live dùng provider `zai` (glm-4.6) — picker đã verify sạch, tránh `claude-cli`
  (400 theo thiết kế trên standalone không CLI-auth).
- Sau mỗi luồng đụng loan single-use (L108 đặc biệt), kiểm tra + báo architect nếu cần restore
  trước khi luồng sau dùng lại — tránh lặp lỗi "tool trả biên nhận cũ, không tạo phiếu/mail
  mới" đã gặp 2 lần trong phiên trước.
- Account t9prod1/t9go1 tạo trong các phiên test trước — chưa được architect xác nhận có cần
  dọn hay không; không tự ý xoá (§2 luật an toàn — không đụng data ngoài quyền, hỏi trước).
- **Bài học vận hành mới (19/7)**: cookie session dùng chung theo domain giữa các tab MCP —
  KHÔNG chạy 2 persona (vd admin + customer) trên 2 tab song song nếu cả 2 cần giữ session
  sống lâu; tab sau login sẽ ghi đè cookie tab trước, gây lỗi 403/redirect giả (không phải bug
  authz thật — đã gặp + tự chẩn đoán đúng ở Luồng 7). Cách an toàn: login → thao tác xong hẳn
  → mới chuyển sang persona khác trên cùng tab, hoặc xác nhận lại `GET /api/me` trước mỗi thao
  tác nhạy cảm nếu bắt buộc phải xen kẽ nhiều tab.
- **1 finding hạ tầng đã ghi vào sổ ngoại lệ §6b**: `HTTP 502` thoáng qua từ Cloudflare tunnel
  lúc bắt đầu Luồng 1 (19/7) — tự phục hồi <20s, không lặp lại xuyên suốt phần còn lại của
  phiên test (mọi luồng sau đều chạy sạch không gặp lại 502). Lý do chấp nhận: hạ tầng ngoài
  phạm vi test nghiệp vụ, tự phục hồi, không ảnh hưởng kết quả cuối của bất kỳ luồng nào —
  architect duyệt khi review, điều kiện xét lại: nếu lặp lại ≥2 lần/phiên trong tương lai thì
  nâng thành finding hạ tầng cần điều tra riêng (không còn coi là ngoại lệ).
