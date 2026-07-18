# Dogfood findings — #132 BANK Digital (Sprint 14)

Loop dogfood 19/7: dùng app như user thật trên prod → finding → fix theo lô → re-verify.
Luật finding: **verdict + LÝ DO + tầng + repro + mức** — verdict suông = vô giá trị.

- **Tầng:** UX · nghiệp-vụ · kỹ-thuật
- **Mức:** 🔴 demo-killer · 🟡 khó-chịu · ⚪ cosmetic
- **Trạng thái:** open → fixing → fixed (re-verified) / deferred / waiver / đề-xuất-ngoài-SPEC

## Bảng tổng

| ID | Persona | Tầng | Mức | Tóm tắt | Trạng thái |
|---|---|---|---|---|---|
| DF-A-01 | A | UX | 🔴 | Modal login/register lộ credential thật (`user/user`, `admin/admin`, `c001/c001`) ngay trên landing page công khai | fixed (re-verified :8000; PROD chưa deploy) |
| DF-A-02 | A | UX | ⚪ | Header/brand landing chỉ ghi "Digital Expert Guild", không thấy "BANK"/"BANK Digital" cho tới khi mở modal login | fixed (re-verified :8000) |
| DF-A-03 | A | UX | 🟡 | Thông báo lỗi đăng ký sai ngữ cảnh: điền đủ username/password nhưng email sai định dạng → app báo "Nhập đủ tên đăng nhập và mật khẩu" (không nói về email) | fixed (re-verified :8000) |
| DF-A-04 | A | UX | 🔴 | Form intake MẤT SẠCH dữ liệu đã điền khi chuyển tab "Đội làm việc" ↔ "Công việc" — không cần reload/logout, chỉ đổi tab. Tái hiện 2/2 lần | fixed (re-verified :8000, 6/6 field giữ đúng vị trí sau chuyển tab) |
| DF-A-05 | A | kỹ-thuật (đính chính từ nghiệp-vụ) | 🟡 | Card canvas TIMELINE "CÁC BƯỚC CẦN HOÀN THIỆN" chỉ hiện "Bước 1/2/3..." trống trơn — root cause CHỐT: data đủ 7 bước nằm ở key `detail`, FE `TimelineBody` không đọc field đó nên vứt hết (không phải card rỗng) | fixing — PROD chưa deploy (card cũ vẫn trống) |
| DF-A-06 | A | nghiệp-vụ | 🟡 | Card canvas "KẾT QUẢ TỪNG TRỤ TÍN HIỆU" dùng thuật ngữ Anh không dịch (Identity/Criminal) + cấu trúc 2 cột dễ đọc ngược (cột trạng-thái-thật vs cột-ngưỡng-kỳ-vọng dính sát nhau, không phân biệt rõ) | fixing — PROD chưa deploy (card cũ vẫn y hệt) |
| DF-A-07 | A | kỹ-thuật | 🔴 | "+ Ca mới" KHÔNG hoạt động khi account đã có ≥1 ca cũ — panel hiện label "Ca mới" (nút active) nhưng nội dung vẫn là ca CŨ nhất, gõ+gửi tin nhắn không tạo request nào (0 POST, 0 console error, silent failure). Tái hiện trên CẢ c001 (sau logout/login) VÀ b001 (session login-đè, không qua logout) — không phải riêng luồng logout | fixed (re-verified :8000, cả 2 case gốc PASS; PROD chờ deploy) |
| DF-B-01 | B | UX+nghiệp-vụ | 🔴 | Đọc code xác nhận (không cần chờ phiếu thật): "Hàng chờ duyệt" render `shortId(conv_id)` (10 ký tự đầu UUID, VÔ NGHĨA) + `summarize(payload)` (JSON thô cắt 90 ký tự, không có TÊN KHÁCH) làm định danh phiếu — cán bộ không thể biết phiếu của ai chỉ nhìn UUID + JSON thô. Sidebar chat "CA CỦA BẠN" cũng cùng vấn đề (nhãn "Ca mới/Mới" đồng loạt) | fixing — BE enrich PASS trên :8000 (field-cũ-nguyên, fail-soft, lane-null-đúng khi thiếu assessment), FE chưa test UI; PROD chưa deploy |
| DF-B-02 | B | UX | 🟡 | Khung "🤖 LÝ DO AI" hiện JSON policy TĨNH giống nhau mọi hồ sơ — root cause CHỐT: by-design (audit chính sách áp dụng), bug chỉ ở NHÃN FE gây hiểu nhầm là lý do riêng | fixing |
| DF-B-03 | B | UX | 🟡 | Tab "Trạng thái đội" hiện đếm "1 Lỗi" nhưng card không thể click/drill-down (`cursor:auto`, không có handler) — cán bộ thấy có ca lỗi nhưng không biết ca nào, lỗi gì, phải tự mò qua Workspace (mà sidebar cũng không phân biệt được ca — xem DF-B-01) | open |
| DF-B-04 | B | UX | ⚪ | Control Tower / Trạng thái đội lộ thuật ngữ kỹ thuật nội bộ ra màn hình nghiệp vụ: "Cost meter... cost per-tool chưa có (SDK không tách, D-48)" — "SDK", "D-48" là mã quyết định nội bộ đội dev, cán bộ ngân hàng đọc không hiểu | open |
| DF-B-05 | B | nghiệp-vụ | ⚪ | Tab "So sánh 1 vs đội" chỉ có nút "Chạy so sánh", chưa có kết quả nào — đây là deliverable demo (so 1 LLM vs đội), không phục vụ tác vụ duyệt hồ sơ hàng ngày của cán bộ. Không phải lỗi, nhưng lạc lõng giữa 5 tab tác nghiệp thật | open |
| DF-B-06 | B | kỹ-thuật | UNVERIFIED | Badge phiếu-bay không hiện dù có 2 phiếu pending thật — NHƯNG prod xác nhận đang chạy bundle CŨ (2 bằng chứng riêng: hint 403 + modal credential đều pre-wave-1) nên chưa chốt được là bug hay chỉ do chưa deploy. Re-test sau deploy wave 1 | unverified |
| DF-B-07 | B | nghiệp-vụ | 🔴 | Nút "✗ Từ chối" quyết ngay lập tức, KHÔNG có ô nhập lý do — code `decideApproval(row.id, decision, '')` truyền `reason` rỗng cứng cho CẢ 2 nút. Khách nhận thông báo qua chat "không được duyệt... kiểm tra lại lý do" nhưng hệ thống chưa từng lưu lý do gì để kiểm tra — khách hoang mang, cán bộ không để lại dấu vết quyết định (thiếu audit) | open |

## Chi tiết finding

### DF-A-01 — Credential demo lộ công khai trên landing prod
- **Persona:** A khách vay
- **Tầng · Mức:** UX · 🔴 demo-killer
- **Repro:** Vào `https://digital.tinhdev.com` (chưa login) → click "Bắt đầu miễn phí" hoặc "Đăng nhập" → modal hiện dòng cuối: "Demo: user/user (RM) · admin/admin (quản lý) · c001/c001 (khách)".
- **Expected (tâm thế user):** Trang public không nên tự hiện thông tin đăng nhập của tài khoản quản trị/nội bộ — khách lạ ghé qua không cần biết account nào tồn tại.
- **Actual:** Toàn bộ 3 bộ credential (kể cả admin) hiện ngay trên UI công khai, ai cũng đọc được mà không cần đăng nhập.
- **Verdict + lý do:** Đây có thể là chủ đích cho DEMO (giám khảo cần gõ nhanh) — nhưng nếu để nguyên lúc thi thật, bất kỳ ai truy cập link public đều login được admin (xem toàn bộ Tower, dữ liệu khách, duyệt/từ chối phiếu). Rủi ro cao nếu link bị lộ ra ngoài trước giờ G. Đề xuất: ẩn dòng "Demo:" trên bản public hoặc đổi cách hiển thị (chỉ hiện cho `user`/`c001`, giấu `admin`), hoặc gate bằng flag môi trường.
- **Bằng chứng bổ sung**: không chỉ UI landing — `POST /api/auth/login` với credential sai trả lỗi 401 kèm `"hint":"Kiểm lại credential. 2 account demo: user / admin."` — API backend cũng tự lộ gợi ý account demo trong error message, không chỉ riêng modal FE. Rủi ro rộng hơn ban đầu tưởng (áp dụng cả cho ai gọi thẳng API, không cần thấy UI).
- **Trạng thái:** fixing — architect chốt D-64 (DECISIONS): FE modal chỉ giữ gợi ý `c001/c001`, BE đổi hint 401 sang generic (giấu admin/user-RM khỏi bề mặt public, không dùng env-flag). (Có 1 đoạn ngắn D-64 tạm ⏸ hold chờ user chốt hướng, sau đó user chốt lại đúng phương án 2 (che admin/RM) → về `fixing`, không đổi kết quả cuối.)
  **Re-verify :8000 (2026-07-18, TESTER xác nhận PASS 4/4 case)**: 401 login sai → hint="Kiểm lại thông tin đăng nhập.", không lộ admin/user/c001; 403 admin-only bằng cookie khách → hint="Cần quyền quản lý.", không nêu "admin"; 409 register trùng → message generic; `uv run pytest` = 343 passed, 37 skipped (khớp báo cáo BE). **BE phần A-01 ĐÃ COMMIT (`58d3774`).**
  **Re-verify FE trên :8000 (2026-07-18)**: modal "Đăng nhập" chỉ còn dòng "Demo: c001/c001 (khách)" — KHÔNG còn admin/admin, user/user. PASS.
- **Trạng thái:** fixed (re-verified :8000, cả BE lẫn FE đều PASS). **PROD CHƯA deploy** — kiểm chứng qua 403 hint dogfood-a1 gọi `/api/stats` trên prod vẫn ghi "Đăng nhập bằng account admin" (pre-D-64) — cần deploy rồi re-confirm 1 lượt trên PROD.

### DF-A-02 — Brand landing không nhất quán tên ngân hàng
- **Persona:** A khách vay
- **Tầng · Mức:** UX · ⚪ cosmetic
- **Repro:** Vào landing `https://digital.tinhdev.com`, đọc header (logo + tagline) trước khi mở modal.
- **Expected:** Khách lạ đọc 5 giây phải thấy rõ đây là dịch vụ ngân hàng gì.
- **Actual:** Header chỉ ghi "Digital Expert Guild — Hội đồng Chuyên gia Số", không có chữ "BANK"/"BANK Digital" nào cho tới khi mở modal login (mới thấy "Đội chuyên gia số ngân hàng — BANK Digital"). Nội dung trang (canvas 3D) có chữ "BANK" nhưng nằm giữa trang, không ở vị trí đọc đầu tiên.
- **Verdict + lý do:** Không chặn chức năng, chỉ là điểm nhận diện thương hiệu — khách có thể thấy hơi mơ hồ "đây là app gì" trong 1-2 giây đầu. Mức cosmetic vì không ảnh hưởng luồng dùng thật.
- **Trạng thái:** fixed (re-verified :8000) — landing header giờ có badge "BANK Digital" cạnh "Digital Expert Guild", đọc rõ ngay lần đầu.

### DF-A-03 — Thông báo lỗi đăng ký sai ngữ cảnh khi email invalid
- **Persona:** A khách vay
- **Tầng · Mức:** UX · 🟡 khó chịu
- **Repro:** Modal "Đăng ký khách mới" → điền đủ username ("dogfood-a1") + password ("dogfood123") → điền email SAI định dạng ("khong-phai-email", không có @) → bấm "Đăng ký & vào".
- **Expected:** Thông báo lỗi phải nói đúng nguyên nhân (email không hợp lệ), giúp khách sửa đúng chỗ.
- **Actual:** Hiện "Nhập đủ tên đăng nhập và mật khẩu." — sai hoàn toàn, vì 2 field đó đã điền đủ. Request không hề gửi lên server (client-side HTML5 `type=email` chặn), nhưng message app hiển thị lại là message cũ dành cho case khác. Lặp lại y hệt ở 2 lần bấm liên tiếp.
- **Verdict + lý do:** Khách gõ nhầm email (dễ xảy ra, email là optional) sẽ bối rối không hiểu sai ở đâu vì thông báo chỉ về username/password — có thể xoá nhầm rồi gõ lại username/password dù chúng đã đúng, gây khó chịu nhẹ. Không chặn được (khách vẫn có thể tự nhận ra là do email và sửa) nên xếp 🟡 không phải 🔴.
- **Trạng thái:** fixed (re-verified :8000) — email sai định dạng → "Email không hợp lệ (hoặc bỏ trống — email là tuỳ chọn)." (đúng ngữ cảnh); email rỗng → đăng ký thành công (đúng "tuỳ chọn"). Input đổi `type="email"`→`type="text"` nên không còn bị HTML5 chặn submit im lặng.

### DF-A-04 — Form intake mất dữ liệu khi chuyển tab canvas
- **Persona:** A khách vay
- **Tầng · Mức:** UX · 🔴 demo-killer
- **Repro:** Login/đăng ký khách mới → chat kích hoạt form "Hồ sơ vay" (present_form) → điền 2-3 field (vd "Họ và tên" + "Số CMND/CCCD") → click tab "Đội làm việc" (bên phải, cạnh tab "Công việc") → click lại tab "Công việc" để quay về form.
- **Expected:** Dữ liệu đã gõ trong form phải còn nguyên khi quay lại — đây là hành vi UI thông thường (chuyển tab không phải submit/reset).
- **Actual:** Toàn bộ field đã điền bị XOÁ SẠCH VỀ RỖNG, kể cả chỉ gõ 1 field duy nhất. Tái hiện ổn định 2/2 lần thử (lần 1: 3 field, lần 2: 1 field) — không phải flaky.
- **Verdict + lý do:** Đây là finding nghiêm trọng nhất của Persona A — form intake là bước bắt buộc cho MỌI khách mới. Nếu khách (nhất là trên điện thoại, dễ vô tình chạm tab khác, hoặc bị thông báo/cuộc gọi làm xao nhãng) lỡ rời form 1 giây rồi quay lại, phải gõ lại từ đầu — rất dễ khiến khách bỏ cuộc giữa chừng, đặc biệt tệ nếu xảy ra trong lúc DEMO trước giám khảo. Nghi ngờ: component Form không lưu state cục bộ ngoài React state của canvas-panel, bị unmount khi đổi tab thay vì chỉ ẩn/hiện (CSS display) — cần frontend xác nhận lại kiến trúc canvas panel.
- **Trạng thái:** fixing — FE báo fixed (root cause: FormCard unmount khi đổi tab do Canvas conditional render → local state chết; fix: lift form values lên Workspace để sống qua tab).
  **Re-verify :8000 (2026-07-18)**: đăng ký khách mới → chat "toi muon vay mua nha" → form intake hiện đủ 6 field → điền đủ 6/6 field (Họ tên/CMND/Địa chỉ/Nghề nghiệp/Thu nhập/Mục đích), chụp baseline TRƯỚC khi chuyển tab → chuyển "Đội làm việc" → quay lại "Công việc" → đọc lại 6 field: **GIỮ ĐÚNG 100% giá trị + ĐÚNG vị trí**, khớp chính xác baseline. (Lưu ý nội bộ: lần thử đầu tiên tưởng phát hiện bug "data xô lệch field" nhưng hoá ra do tester tự set sai index — DOM có 7 input vì index 0 là ô chat, không phải field form đầu tiên; xác nhận qua `aria-label` rồi làm lại đúng cách, kết quả PASS sạch.)
- **Trạng thái:** fixed (re-verified :8000, đủ 6/6 field giữ nguyên qua chuyển tab). Chưa re-test PROD.

### DF-A-05 — Card canvas TIMELINE thiếu nội dung (root cause CHỐT: FE vứt field, không phải card rỗng)
- **Persona:** A khách vay
- **Tầng · Mức:** ~~nghiệp-vụ~~ → **kỹ-thuật** (FE render quá hẹp — đính chính theo root cause architect, xem dưới) · 🟡 khó chịu
- **Repro:** Đăng ký khách mới → điền form → nộp → chat "300tr, tín chấp, mua nhà" → đợi Pháp lý chạy xong (lane YELLOW) → xem card "CÁC BƯỚC CẦN HOÀN THIỆN - C902" (type TIMELINE) trên canvas.
- **Expected:** Mỗi bước trong timeline phải có tên/mô tả (theo SPEC §6 card generic `timeline` — item cần `name`/`step` mô tả).
- **Actual:** Card chỉ hiện "Bước 1", "Bước 2", "Bước 3"... trống hoàn toàn không có nội dung mô tả trên UI. Nội dung THẬT (bổ sung CCCD, sao kê lương, xác nhận cư trú → ngân hàng tra CIC+công an → chuyển cấp phê duyệt) chỉ thấy trong đoạn chat text bên trái.
- **Root cause CHỐT (architect đối chiếu code + query prod, card id `2afff539`):** Card KHÔNG rỗng — data đủ 7 bước nội dung tiếng Việt thật, nhưng nằm ở key `detail`/`assignee` trong item. FE component `TimelineBody` chỉ đọc `step ?? name` + `owner`/`eta`, KHÔNG đọc `detail` → vứt hết nội dung thật khi render, để lại "Bước 1/2/3" trống. **Đính chính nhận định ban đầu**: KHÔNG phải "nội dung không đồng bộ ra card" (ý là backend/data thiếu) — mà là "card CÓ đủ nội dung, FE đọc sai field nên không hiện". Đổi tầng từ nghiệp-vụ → kỹ-thuật cho khớp root cause thật (lỗi code render, không phải thiếu logic nghiệp vụ).
- **Verdict + lý do:** Không đổi mức 🟡 (kênh chính chat vẫn diễn giải đủ, không chặn hoàn toàn) nhưng đổi tầng vì nguyên nhân thật là bug code cụ thể, dễ fix (đọc thêm field `detail`), không phải thiết kế thiếu.
- **Trạng thái:** fixing — FE báo fixed 2 lần (wave 2 tolerant-render + bản cải theo shape thật `{name,detail,status,assignee}`).
  **Re-verify PROD (2026-07-18)**: card CŨ "CÁC BƯỚC CẦN HOÀN THIỆN - C902" (assessment #6, tạo 20:23) **VẪN hiện "Bước 1..7" TRỐNG** — CHƯA fix trên PROD. Đối chiếu: card MỚI hơn cùng ca "Lộ trình xử lý hồ sơ" (tạo 20:49, TIMELINE khác) hiện ĐÚNG đủ nội dung ("Tiếp nhận hồ sơ · RM · 1 ngày"...) — cho thấy code review/local đúng, nhưng PROD chưa deploy bundle FE mới (khớp pattern đã thấy ở A-01-FE/B-01-BE/A-07 — nhiều phần PROD vẫn chạy bundle cũ). KHÔNG kết luận fix sai — chỉ là CHƯA DEPLOY. Cần re-test lại đúng card CŨ này (không phải card mới) sau khi PROD deploy xong.

### DF-A-06 — Card kỹ thuật khó đọc, thuật ngữ không dịch
- **Persona:** A khách vay
- **Tầng · Mức:** nghiệp-vụ · 🟡 khó chịu
- **Repro:** Cùng ca DF-A-05, xem card "KẾT QUẢ TỪNG TRỤ TÍN HIỆU" (type METRIC) trên canvas.
- **Expected:** Khách đọc phải hiểu vì sao mình YELLOW mà không cần biết tiếng Anh/thuật ngữ ngân hàng.
- **Actual:** Tên trụ để nguyên tiếng Anh trong ngoặc ("Nhân thân (Identity)", "Tiền án (Criminal)"). Mỗi dòng nhồi 2 cụm sát nhau dễ đọc nhầm: cột 1 là giá trị THẬT của khách (vd "YELLOW - Chưa xác minh được"), cột 2 là NGƯỠNG kỳ vọng hệ thống cần (vd "PASS - Có bản ghi công an") — 2 chữ "YELLOW" và "PASS" xuất hiện cạnh nhau trên cùng dòng dễ khiến người đọc nhanh hiểu lầm là 2 kết quả khác nhau thay vì giá-trị-vs-ngưỡng.
- **Verdict + lý do:** Không sai dữ liệu (đã verify khớp đúng honest-null ở Luồng 1 business-test-scenarios), chỉ là cách trình bày gây khó đọc cho non-technical user — đúng khung chấm dispatch "khách thật có lạc không". Card này + DF-A-05 cùng 1 vùng UI (canvas panel) đáng xem xét sửa cùng lúc.
- **Trạng thái:** fixing — FE báo fixed (header cột + dịch thuật ngữ Identity→Định danh...).
  **Re-verify PROD (2026-07-18)**: card CŨ cùng assessment #6 **VẪN hiện "Nhân thân (Identity)"** tiếng Anh trong ngoặc + cấu trúc 2 cột dính y hệt trước — CHƯA fix trên PROD, cùng nguyên nhân chưa deploy như DF-A-05 (xem ghi chú ở đó). Cần re-test lại khi PROD deploy xong.

### DF-A-07 — "+ Ca mới" không hoạt động khi account có sẵn ca cũ (🔴 nghiêm trọng nhất phiên)
- **Persona:** A khách vay
- **Tầng · Mức:** kỹ-thuật · 🔴 demo-killer
- **Repro (case 1 — qua logout, tái hiện trên c001):**
  1. Login `c001/c001` trên `https://digital.tinhdev.com` (account đã có lịch sử ca cũ — "Giải ngân L001 340tr").
  2. Click "Đăng xuất" (góc trên phải) → modal login hiện lại → đăng nhập lại `c001/c001`.
  3. Vào Workspace → click "+ Ca mới" (nút cam góc trên trái sidebar).
  4. Click vào ô input cuối panel, gõ 1 câu bất kỳ (vd "Tôi muốn hỏi về khoản vay mua xe"), bấm nút gửi (hoặc Enter).
  5. Quan sát: không có gì xảy ra — không "Đang chạy", không tin nhắn mới xuất hiện trong panel chat.
- **Repro (case 2 — KHÔNG qua logout, tái hiện trên b001, loại trừ nguyên nhân là do logout):**
  1. Từ 1 tab đã login sẵn (bất kỳ), gọi thẳng `POST /api/auth/login` đổi sang `b001/b001` (login-đè, không qua nút Đăng xuất) → `navigate()` reload trang.
  2. b001 đã có sẵn 3 ca cũ (1 ca thẩm định 594tr DN từ trước). Click "+ Ca mới" → nút chuyển trạng thái active (highlight cam) đúng, nhưng **nội dung panel bên dưới vẫn hiện nguyên ca cũ nhất** (bảng "KẾT QUẢ 3 PHÒNG" của thẩm định 594tr) — không phải panel nháp trống.
  3. Bấm lại "+ Ca mới" thêm 1-2 lần nữa: không đổi gì, luôn quay về đúng ca cũ đó.
- **Expected (tâm thế user):** Bấm "+ Ca mới" phải mở 1 cuộc trò chuyện HOÀN TOÀN MỚI, trống — gõ câu hỏi vào phải gửi được và MAIN phải trả lời.
- **Actual:** Panel header ghi "Ca mới" / nút ở trạng thái active đúng, NHƯNG nội dung chat bên dưới vẫn hiển thị đúng y hệt lịch sử ca CŨ NHẤT của account. Gõ câu mới vào input + bấm gửi (case 1): **hoàn toàn không có network request nào được gửi** (xác nhận qua `read_network_requests` — chỉ toàn GET `/api/conversations`, `/api/models`, `/api/conversations/{id}/sse`, không có bất kỳ POST nào), **không có console error/exception nào** (silent failure hoàn toàn — user không được báo lỗi gì). Tái hiện ổn định qua 3 lần thử độc lập trên c001, kể cả sau khi `navigate()` reload sạch trang, VÀ tái hiện độc lập trên b001 (không qua logout) — loại trừ khả năng đây chỉ là lỗi liên quan riêng tới flow logout, hoặc chỉ là cache tạm thời của 1 session.
- **Bằng chứng bổ sung (quyết định)**: `GET /api/conversations` trước/sau nhiều lần bấm "+ Ca mới" trả về SỐ LƯỢNG CA KHÔNG ĐỔI (3 ca, tất cả `created_at` từ hôm qua 18/7 17:xx — không có ca nào mới). Kiểm tra trực tiếp DOM input cuối panel: `placeholder="Hỏi Main về ca này…"` — đây LÀ placeholder dành cho hỏi-thêm-về-ca-đang-xem (so sánh với placeholder đúng của ca nháp thật đã thấy ở các phiên trước: "Gõ một yêu cầu tư vấn... Main sẽ điều phối..."/"Gõ câu hỏi đầu tiên — ca sẽ tạo với model đã chọn..."). Vậy: nút "+ Ca mới" thực chất **KHÔNG chuyển UI sang trạng thái nháp mới** — panel vẫn đang ở nguyên ngữ cảnh ca cũ nhất, chỉ có nút bấm đổi màu (active) nhưng không có hiệu ứng thật nào khác.
- **Verdict + lý do:** Đây là finding nghiêm trọng nhất toàn phiên dogfood — bug không giới hạn ở logout/login mà là **bất kỳ khách nào đã có ≥1 ca chat cũ đều không mở được ca chat MỚI qua nút "+ Ca mới"**, chỉ luôn quay về xem lại ca cũ nhất, dù nút bấm trông như đã kích hoạt. Đây gần như chắc chắn sẽ xảy ra khi demo thật — mất khả năng bắt đầu hội thoại mới là thảm hoạ trực tiếp trên sân khấu. Nghi vấn kỹ thuật đã thu hẹp nhờ bằng chứng DOM: (a) khả năng cao nhất — handler `onClick` của nút "+ Ca mới" chỉ set 1 cờ UI (class active) nhưng KHÔNG thực sự gọi hàm chuyển `selectedConvId` về `null`/nháp, nên component panel chat vẫn render theo `selectedConvId` cũ trỏ tới ca cũ nhất; (b) có thể có race giữa state cục bộ (local click handler) và state đến từ 1 nguồn khác (context/store) ghi đè lại ngay sau click. **Đây là bug FE thuần (không cần backend log) — frontend có thể tái hiện + fix nhanh bằng cách kiểm tra trực tiếp component xử lý nút "+ Ca mới" (tìm theo text "Ca mới" hoặc placeholder "Gõ một yêu cầu tư vấn") xem có gọi đúng action reset ca-đang-chọn hay không.**
- **Trạng thái:** fixing — FE báo fixed (root cause THẬT khác nghi vấn ban đầu của tester: KHÔNG phải "onClick chỉ set cờ UI", mà là RACE — mount auto-select ca resolve MUỘN sau khi user bấm "+ Ca mới", đè `activeId` về ca cũ nhất; giải thích luôn vì sao local khó tái hiện (window <20ms) còn prod mạng chậm nên trúng race. Fix: guard `draftingRef`).
  **Re-verify :8000 HOÀN TẤT (2026-07-18, sau server hồi phục) — PASS CẢ 2 CASE:**
  - **Case 1 (c019, 1 ca cũ, reload thường)**: "+ Ca mới" → panel đúng "Ca mới (nháp)" + placeholder draft → gõ "Xác nhận A-07 fix..." + gửi → MAIN trả lời ĐÚNG nội dung tin nhắn mới (hỏi lại rõ ràng vì không hiểu, đúng persona điều phối viên vay) — HOÀN TOÀN KHÁC ca cũ (hỏi vay mua xe). Sidebar hiện 2 dòng "Ca mới" riêng biệt. PASS.
  - **Case 2 (login-đè b001 qua `fetch('/api/auth/login')` trực tiếp, KHÔNG qua nút Đăng xuất, có 1 ca cũ)**: reload → "+ Ca mới" → panel đúng "Ca mới (nháp)" + placeholder "Gõ một yêu cầu tư vấn..." (draft thật, không phải ca cũ). PASS.
  - Cả 2 case đều xác nhận bằng UI thật (không chỉ network log) — bug KHÔNG còn tái hiện.
- **Trạng thái:** fixed (re-verified :8000 — cả 2 case gốc PASS). Chưa re-test PROD (PROD hiện đang bận với data Lô 2, sẽ re-test khi deploy wave 1 lên PROD).

### DF-B-01 — Phiếu chờ duyệt định danh bằng UUID + JSON thô, không tên khách (xác nhận qua code, không chỉ UI)
- **Persona:** B cán bộ duyệt (login `admin/admin`)
- **Tầng · Mức:** UX + nghiệp-vụ · 🔴 demo-killer
- **Repro (UI — sidebar chat, đã thấy trực tiếp):**
  1. Login `admin/admin` trên `https://digital.tinhdev.com` → Workspace (mặc định) → sidebar trái "CA CỦA BẠN" (14 dòng).
  2. Đối chiếu `GET /api/conversations` (fetch qua console, credentials include) → 14 conversation thuộc NHIỀU `user_id` khác nhau (`dogfood-a1`, `c001`, `c019`, `compare`, `b001`...).
  3. 13/14 dòng sidebar hiện y hệt "Ca mới" (tên) + "Mới" (trạng thái) — không tên/mã khách/số tiền/ngày.
- **Repro (code — đọc trực tiếp, xác nhận "Hàng chờ duyệt" CŨNG bị, không cần chờ seed):**
  4. Đọc `frontend/src/components/ControlTower.tsx` dòng 106-110 (component `ApprovalQueue`, render mỗi phiếu):
     `<span>{shortId(row.conv_id)}</span><span>{summarize(row.payload)}</span>`.
  5. `shortId()` (dòng 284-286): `id.slice(0,10) + '…'` — cắt 10 KÝ TỰ ĐẦU CỦA UUID conv_id (vd `1add1eff-6…`), không phải tên/mã khách.
  6. `summarize()` (dòng 287-290): `JSON.stringify(payload).slice(0,90)` — dump payload thô cắt 90 ký tự. Đối chiếu payload thật đã thấy trong Nhật ký tool: `{"amount":300000000,"loan_id":"C902"}` — CÓ số tiền + loan_id, nhưng KHÔNG có tên khách (payload `disburse` không mang customer name).
- **Expected (tâm thế cán bộ, đúng khung dispatch bước 1):** Phiếu trong hàng chờ phải "tự đứng được" — thấy ngay khách nào, bao nhiêu tiền, vì sao — không phải đọc lại cả chat hay đoán qua UUID.
- **Actual:** Phiếu hiện dạng `🔒 disburse | 1add1eff-6… | {"amount":300000000,"loan_id":"C902"}` — cán bộ đọc được SỐ TIỀN + LOAN_ID (nhờ payload) nhưng KHÔNG thấy tên khách trực tiếp trên dòng phiếu, phải tự tra loan_id/conv_id sang tab khác. conv_id hiển thị dạng UUID cắt ngắn hoàn toàn vô nghĩa với người đọc.
- **Verdict + lý do:** Đây là bằng chứng CODE, không phụ thuộc việc có phiếu thật hay không — component render đúng vậy với BẤT KỲ phiếu nào. Xếp 🔴 vì đây là màn hình QUYẾT ĐỊNH TRỰC TIẾP (duyệt/từ chối tiền thật), đúng tâm điểm câu hỏi dispatch "cán bộ có DÁM KÝ dựa trên màn hình này không" — 1 dòng UUID+JSON thô không đủ tự tin để bấm Duyệt mà không mở thêm tab tra cứu. Vẫn có amount/loan_id nên không phải mù hoàn toàn (hạ 1 bậc so với "không biết gì") nhưng thiếu tên khách là thiếu sót nghiệp vụ rõ ràng cho 1 thao tác ký duyệt. Nghi vấn: `ApprovalRow` (type ở `frontend/src/types`) có thể đã có sẵn field liên quan tới khách trong payload gốc từ BE (cần FE kiểm lại `store_approvals.py`/`gated.py` xem `payload` có mang được `owner_id`/tên khách không, nếu có thì chỉ là FE chưa render, sửa nhanh; nếu BE cũng không có thì cần bổ sung field).
- **Trạng thái:** open — vẫn nên re-test bằng mắt với phiếu thật khi có seed (để xác nhận UI thật khớp đúng đọc code, và đo thời gian/số click thực tế theo đúng bước 1 dispatch)

### DF-B-02 — "Lý do AI" trong tab Hồ sơ đọc như lý do riêng nhưng là snapshot policy chung
- **Persona:** B cán bộ duyệt
- **Tầng · Mức:** UX · 🟡 khó chịu (KHÔNG phải 🔴 — 3 trụ phía trên vẫn đủ để ký, xem ghi chú)
- **Repro:**
  1. Login `admin/admin` → Control Tower → tab "Hồ sơ + lý do AI".
  2. Click hồ sơ `C902 · consumer · 300 triệu` (YELLOW) → đọc khung tím "🤖 LÝ DO AI" ở cuối panel phải.
  3. Click hồ sơ `C019 · consumer · 594 triệu` (GREEN) → đọc lại khung "🤖 LÝ DO AI".
  4. So sánh 2 nội dung.
- **Expected:** Không rõ SPEC có yêu cầu "lý do AI" phải riêng theo từng hồ sơ hay không (chưa đối chiếu SPEC §nào định nghĩa field này) — expected ở đây là kỳ vọng ĐỌC của cán bộ khi thấy 1 khung tên "LÝ DO AI" đặt ngay dưới hồ sơ cụ thể.
- **Actual:** Cả 2 hồ sơ (1 YELLOW, 1 GREEN, khác khách, khác số tiền, khác kết quả thẩm định) đều hiện **NGUYÊN VĂN 1 JSON giống hệt nhau**: `{"lane_policy_version": "v1", "auto_approve_max_vnd": 2000000000.0, "cic_block_min_group": 3, "blocked_record_types": "financial_fraud,money_laundering", "source": "assumptions table (mentor-1807-hypothesis)"}`. Đây đọc như config NGƯỠNG CHUNG của hệ thống (snapshot chính sách áp dụng lúc chấm lane), không phải lý do tính riêng cho hồ sơ đang xem.
- **Verdict + lý do (đã tự sửa sau lần ghi đầu — hạ từ 🔴 xuống 🟡):** Phần "TIÊU CHÍ THẨM ĐỊNH (3 TRỤ)" phía trên (identity/criminal/cic/employment/docs/purpose/credit) VẪN đúng và riêng theo từng hồ sơ — cán bộ ĐÃ có đủ thông tin để ký nếu đọc đúng phần đó, nên đây KHÔNG chặn được việc ký (không phải 🔴 theo đúng định nghĩa demo-killer). Vấn đề thuần là NHÃN/KỲ VỌNG: đặt tên "LÝ DO AI" cho 1 khung hiện policy tĩnh dễ khiến cán bộ hiểu lầm đây là suy luận riêng cho ca này, trong khi có thể đây là snapshot chính sách áp dụng — hoàn toàn có thể là THIẾT KẾ CHỦ Ý (ghi lại "chính sách nào đã áp dụng lúc quyết" là thông tin audit hợp lệ). **Không khẳng định đây là bug backend** — chưa đối chiếu SPEC xem field `basis`/`lý do AI` có bắt buộc per-profile hay không; nếu KHÔNG bắt buộc, đây chỉ là góp ý đổi tên/label (vd "Chính sách áp dụng" thay vì "Lý do AI") để tránh hiểu lầm, không phải fix logic.
- **Root cause CHỐT (architect đối chiếu code):** `basis` do LAB legal ghi (`roles/legal/functions.py` dòng 346) = policy snapshot lúc chấm, GIỐNG NHAU giữa mọi hồ sơ LÀ BY-DESIGN (audit "chính sách nào áp dụng lúc quyết", LAB certified không đổi) — xác nhận đúng phỏng đoán "có thể là thiết kế chủ ý" ở trên, KHÔNG phải bug backend/DB. Bug thật chỉ là NHÃN FE "🤖 Lý do AI" (`AssessmentsView.tsx:128`) gây đọc nhầm thành lý do riêng — lý do per-profile thật nằm ở criteria 3 trụ ngay phía trên (đã đúng).
- **Trạng thái:** fixing — gom cùng wave B (với DF-B-01, DF-B-04) sau khi tester chốt mức DF-B-01 với phiếu thật. Fix dự kiến: đổi nhãn/chú thích FE, không đổi logic.

### DF-B-03 — "Trạng thái đội" đếm lỗi nhưng không drill-down được
- **Persona:** B cán bộ duyệt
- **Tầng · Mức:** UX · 🟡 khó chịu
- **Repro:**
  1. Control Tower → tab "Trạng thái đội".
  2. Quan sát 5 card: Đang chạy=0, Chờ duyệt=0, Hoàn tất=0, **Lỗi=1**, Sẵn sàng=13.
  3. Thử click vào card "Lỗi" — kiểm tra qua JS: `getComputedStyle(card).cursor` = `"auto"`, không có `onclick` handler trên card.
- **Expected:** Cán bộ thấy "1 Lỗi" phải bấm được để xem NGAY ca nào lỗi, lỗi gì, để xử lý hoặc báo kỹ thuật.
- **Actual:** Card chỉ hiển thị con số, không phải nút — không có cách nào từ tab này biết ca lỗi là của khách nào. Sidebar Workspace cũng không giúp được (xem DF-B-01 — mọi dòng đều "Ca mới", có 1 dòng ghi "Lỗi" thay vì "Mới" khi quan sát kỹ nhưng vẫn không có tên khách).
- **Verdict + lý do:** Không chặn hoàn toàn (cán bộ vẫn có thể tự dò qua từng ca trong Workspace để tìm dòng ghi "Lỗi" thay vì "Mới"/"Sẵn sàng"), nhưng mất thời gian và dễ bỏ sót — 1 ca lỗi lẫn giữa 13 ca khác không tên. Xếp 🟡 vì có đường vòng, không phải bế tắc hoàn toàn.
- **Trạng thái:** open

### DF-B-04 — Thuật ngữ kỹ thuật nội bộ lộ ra màn hình nghiệp vụ
- **Persona:** B cán bộ duyệt
- **Tầng · Mức:** UX · ⚪ cosmetic
- **Repro:** Control Tower → tab "Trạng thái đội" → đọc dòng ghi chú dưới 5 card.
- **Expected:** Màn hình cán bộ nghiệp vụ chỉ nên chứa ngôn ngữ nghiệp vụ, không lộ mã nội bộ đội dev.
- **Actual:** Dòng chú thích: *"💰 Cost meter: chi phí tính theo LƯỢT (tasks.cost per-turn) — cost per-tool chưa có (SDK không tách, D-48). Mở 1 ca ở Workspace để xem cost per-turn của lượt đó."* — cụm "SDK không tách", "D-48" (mã quyết định trong `DECISIONS.md` nội bộ) là ngôn ngữ dev thuần, cán bộ ngân hàng đọc sẽ không hiểu và có thể đặt câu hỏi không cần thiết lúc demo.
- **Verdict + lý do:** Không ảnh hưởng chức năng, chỉ là điểm lộ "hậu trường" ra sản phẩm — nên xếp cosmetic. Nhưng dễ sửa (chỉ là văn bản tĩnh) nên đáng dọn trước khi thi.
- **Trạng thái:** open

### DF-B-05 — Tab "So sánh 1 vs đội" lạc lõng giữa các tab tác nghiệp
- **Persona:** B cán bộ duyệt
- **Tầng · Mức:** nghiệp-vụ · ⚪ cosmetic
- **Repro:** Control Tower → tab "So sánh 1 vs đội".
- **Expected/Actual:** Tab chỉ có tiêu đề "So sánh: 1 LLM trần vs cả ĐỘI (deliverable #5)" + nút "▶ Chạy so sánh", chưa từng chạy (không có dữ liệu sẵn). Đây là 1 "deliverable" chứng minh giá trị kiến trúc đội-agent (marketing/thuyết phục giám khảo), không phải công cụ cán bộ dùng để duyệt hồ sơ hàng ngày.
- **Verdict + lý do:** Không phải bug — đúng ý đồ thiết kế (SPEC có nhắc "deliverable #5"). Nhưng đứng cùng hàng với 5 tab tác nghiệp thật (Tổng quan/Hàng chờ/Hồ sơ/Nhật ký/Trạng thái đội) khiến 1 cán bộ mới lần đầu vào Tower có thể bấm nhầm, tốn 1 lượt LLM call không cần thiết chỉ để "xem thử". Đề xuất (không tự build): cân nhắc tách riêng khu vực "demo/deliverable" khỏi khu vực "tác nghiệp hàng ngày", hoặc thêm mô tả ngắn giải thích mục đích tab này khác biệt.
- **Trạng thái:** open

### DF-B-06 — Badge phiếu-bay trên Control Tower KHÔNG hiện (NGHI ngờ do PROD chạy bundle CŨ, chưa deploy wave — chưa chốt là bug thật)
- **Persona:** B cán bộ duyệt
- **Tầng · Mức:** kỹ-thuật · **UNVERIFIED — tự hạ từ 🔴 xuống nghi vấn treo, xem lý do dưới**
- **Repro:**
  1. Đã seed 2 phiếu pending thật trên PROD (architect seed L950/L951 cho C902 → dogfood-a1 chat xin giải ngân từng khoản → 2 phiếu vào hàng chờ, xác nhận qua chat MAIN: "Yêu cầu đang chờ duyệt rồi ạ").
  2. Login `admin/admin` → Workspace load xong (đợi ≥3s cho chắc hook đã kịp poll lần đầu theo code — hook có "poll ngay lần đầu, không đợi 5s").
  3. Zoom vào góc phải header, vùng nút "🗼 Control Tower".
  4. Kiểm DOM: `document.querySelector('[data-testid="tower-badge"]')` → `null` (element hoàn toàn không tồn tại, không phải bị ẩn CSS).
  5. Kiểm network qua `read_network_requests` (urlPattern `/api/`) NGAY SAU reload sạch + đợi 3s: chỉ thấy `GET /api/conversations`, `/api/models`, `/api/conversations/{id}/sse`, `/api/conversations/{id}` — **KHÔNG có `GET /api/approvals` nào**.
  6. Đối chiếu: `fetch('/api/approvals?status=pending', {credentials:'include'})` gọi TRỰC TIẾP từ console → 200, trả đúng 2 phiếu thật (`L951` 1.2 tỷ + `L950` 800tr, cả 2 `status:"pending"`).
- **Expected:** Theo code `frontend/src/hooks/useApprovalBadge.ts` — hook `useApprovalBadge(isAdmin)` phải tự poll `GET /api/approvals?status=pending` ngay khi mount (dòng 54: "poll ngay lần đầu, không đợi 5s") và set badge số trên nút Control Tower (`frontend/src/Workspace.tsx` dòng 399-407, điều kiện `pendingApprovals > 0`). Cán bộ mở app phải THẤY NGAY có phiếu chờ mà không cần chủ động click vào Tower để "đi tìm".
- **Actual:** Badge KHÔNG bao giờ xuất hiện — hook dường như không được gọi/không chạy đúng trên PROD, dù API backend hoạt động hoàn toàn bình thường khi gọi trực tiếp.
- **Verdict + lý do (TỰ SỬA sau advisor review — ban đầu ghi 🔴, hạ xuống UNVERIFIED):** Cùng phiên này đã xác nhận 2 lần PROD đang chạy bundle CŨ, chưa deploy wave 1: (a) 403 hint khi dogfood-a1 gọi `/api/stats` vẫn ghi "Đăng nhập bằng account admin" — trong khi fix D-64 (đã PASS trên :8000) đổi hint sang generic; (b) modal login PROD vẫn hiện đủ 3 credential kể cả admin/admin — trong khi A-01-FE đã báo fixed. Vậy PROD ≠ code tôi vừa đọc để viết Expected — so sánh code MỚI (repo) với hành vi PROD CŨ là so sai 2 bundle khác nhau, không phải bằng chứng bug. Có khả năng cao badge code (`useApprovalBadge`) cũng chưa nằm trong bundle PROD hiện tại, giống hệt tình trạng A-07/A-04/A-01 đang chờ deploy. KHÔNG loại trừ đây là bug thật (có thể badge code đã có nhưng lỗi race như A-07) — nhưng chưa đủ căn cứ để chốt 🔴 lúc PROD chưa update.
- **Trạng thái:** UNVERIFIED — gộp re-test vào đợt xác nhận PROD sau khi wave 1 (A-07+A-04+A-01) deploy xong. Nếu badge VẪN không hiện sau deploy dù có phiếu pending thật → nâng lại 🔴 ngay. Nếu hiện đúng → đóng finding, ghi "false alarm do đọc nhầm bundle".

### DF-B-07 — "Từ chối" không có ô nhập lý do, khách nhận thông báo mơ hồ
- **Persona:** B cán bộ duyệt (thực hiện bước 1-2 dispatch với seed L950/L951 architect cấp)
- **Tầng · Mức:** nghiệp-vụ · 🔴 demo-killer
- **Repro:**
  1. Login `dogfood-a1` (owner C902) → tạo 2 ca mới → xin giải ngân L950 (800tr) rồi L951 (1.2 tỷ) → cả 2 vào hàng chờ, xác nhận qua chat MAIN.
  2. Login `admin/admin` → Control Tower → Hàng chờ duyệt (2 phiếu, đúng UUID+JSON thô như DF-B-01) → bấm "✓ Duyệt" trên phiếu L950 → bấm "✗ Từ chối" trên phiếu L951.
  3. Quan sát: bấm "✗ Từ chối" ra quyết định NGAY LẬP TỨC — không có dialog/ô nhập lý do nào hiện ra trước khi quyết.
  4. Đọc code xác nhận: `frontend/src/components/ControlTower.tsx` dòng 86, hàm `decide()` gọi `conversationApi.decideApproval(row.id, decision, '')` — tham số `reason` LUÔN LÀ CHUỖI RỖNG CỨNG, dùng chung cho CẢ nút Duyệt lẫn Từ chối (dòng 121-122 cả 2 đều gọi `decide(row, ...)` không truyền reason riêng).
  5. Đăng xuất admin → login lại `dogfood-a1` → ca L951 tự động resume, MAIN báo: *"Nguyễn Văn Test ơi, em phải báo tin buồn ạ. Yêu cầu giải ngân khoản vay L951 (1.2 tỷ VND) của anh **không được duyệt**. Anh cần em kiểm tra lại lý do không được duyệt hoặc hỗ trợ thêm gì không ạ?"*
- **Expected:** Từ chối 1 khoản vay 1.2 tỷ là quyết định nghiệp vụ NGHIÊM TRỌNG — cán bộ cần được YÊU CẦU nhập lý do (bắt buộc hoặc ít nhất khuyến khích) trước khi xác nhận, để (a) khách biết chính xác cần sửa gì, (b) có dấu vết audit "vì sao từ chối" thay vì chỉ có "ai từ chối, lúc nào".
- **Actual:** Reason luôn rỗng. Khách nhận thông báo "không được duyệt" nhưng KHÔNG BIẾT VÌ SAO — MAIN tự đề nghị "kiểm tra lại lý do" nhưng thực chất hệ thống không hề lưu lý do gì để kiểm. Khách chỉ còn cách đoán hoặc liên hệ trực tiếp ngân hàng hỏi lại — đúng kịch bản gây bực/nghi ngờ theo khung chấm dogfood ("khách thật có bực không").
- **Verdict + lý do:** Xếp 🔴 vì đây là 1 trong 2 hành động cốt lõi nhất của toàn hệ thống (duyệt/từ chối tiền thật) và thiếu 1 field cơ bản mọi ngân hàng thật đều bắt buộc (lý do từ chối). Không chỉ là UX-thiếu-tiện — đây là THIẾU DẤU VẾT NGHIỆP VỤ (audit trail rỗng cho quyết định quan trọng nhất). Backend đã CÓ SẴN field `reason` trong bảng `approvals` (xác nhận qua `frontend/src/components/ControlTower.tsx` type `ApprovalRow` và API `POST /api/approvals/{id}/decide` body có `reason?: string`, theo `backend/app/api/approvals.py` `DecideBody.reason: str | None`) — chỉ FE chưa có UI nhập, sửa không khó (thêm 1 ô input/textarea + prompt trước khi gọi decide, tối thiểu cho nhánh "Từ chối").
- **Trạng thái:** open

## Đề xuất ngoài SPEC (ghi, KHÔNG build — chờ lead/user)

_(chưa có)_

## Biên lai dọn prod cuối loop (Lô 1 — Persona A, chưa đóng loop, còn chờ Lô 2/3)

**Trạng thái stats trước Lô 1** (`/api/stats?window=7d`, đầu phiên): `approvals{approved:1,auto:1}`,
`assessments{green:1,yellow:4}` (total 5), `conversations{total:13}`.

**Trạng thái stats sau Lô 1** (cùng query): `approvals{approved:1,auto:1}` (KHÔNG đổi — xác nhận
L001/L007/L108 không bị đụng, đúng chỉ đạo "seed demo phải còn active nguyên trạng"),
`assessments{green:1,yellow:5}` (total 6, +1 = assessment #6 của C902) `conversations{total:14}`
(+1 = ca dogfood-a1 "cho vay k? lãi bn ạ").

**Rác tạo trong Lô 1 — khoanh vùng C9xx, cần dọn cuối loop (không tự dọn ngay, chờ lệnh)**:
- Account `dogfood-a1` (email `dogfood-a1@example.com`) — khách mới đăng ký.
- Khách hàng `C902` (Nguyễn Văn Test, CMND 079099001234) — hồ sơ vay 300tr tín chấp, lane YELLOW,
  assessment #6, chưa có loan/disburse nào (chỉ dừng ở bước thẩm định honest-null).
- 1 conversation của `dogfood-a1` (ca "cho vay k? lãi bn ạ").

**Xác nhận seed KHÔNG bị đổi**: L001 (C001, 340tr), L007 (B001, 3 tỷ), L108 (C019, 594tr) — cả 3
vẫn `active`, không có disburse/approval mới nào trong toàn bộ Lô 1 (đúng biên lai stats trên).

## Biên lai dọn prod cuối loop (Lô 2 — Persona B, bước 1-2)

**Seed do architect cấp (KHÔNG do tester tạo)**: `L950` (C902, 800tr, active), `L951` (C902, 1.2
tỷ, active) — insert trực tiếp DB, ngoài range L1xx, không đụng B004/L901 (đã tồn tại từ LAB seed).

**Trạng thái stats trước bước 1-2** (đầu Lô 2, khớp cuối Lô 1): `approvals{approved:1,rejected:0,
pending:0,auto:1}`, `assessments{green:1,yellow:5,red:0}`, `conversations{total:14}`.

**Hành động tester thực hiện**: login `dogfood-a1` (owner C902) → tạo 2 ca mới → xin giải ngân
L950 rồi L951 (tuần tự, đúng ma trận D-59 — cả 2 nằm band 500tr-2tỷ + lane YELLOW nên bay thẳng
về người duyệt, không auto) → 2 phiếu pending → login `admin/admin` → Control Tower → Hàng chờ
duyệt → **Duyệt L950**, **Từ chối L951** (reason rỗng — xem DF-B-07).

**Trạng thái stats sau bước 1-2** (`/api/stats?window=7d`): `approvals{approved:2,rejected:1,
pending:0,auto:1}` (auto KHÔNG đổi — xác nhận L001/L007/L108 vẫn nguyên, +1 approved từ L950,
+1 rejected từ L951), `conversations{total:16}` (+2 ca dogfood-a1 mới cho L950/L951).

**Rác tạo trong bước 1-2 — khoanh vùng C9xx + L9xx, cần dọn cuối loop (không tự dọn, chờ lệnh)**:
- Loan `L950` (C902, 800tr) — đã DUYỆT + disburse (status `used`), là tiền giả lập, không dùng thật.
- Loan `L951` (C902, 1.2 tỷ) — đã TỪ CHỐI (status `rejected`).
- 2 approval record tương ứng (`approved` cho L950, `rejected` cho L951).
- 2 conversation mới của `dogfood-a1` (ca xin giải ngân L950, ca xin giải ngân L951).

**Xác nhận seed gốc KHÔNG bị đổi**: L001/L007/L108 vẫn active, `auto:1` không đổi qua toàn bộ
Lô 2 tính tới bước 1-2 — đúng cam kết không động seed khoanh vùng.
