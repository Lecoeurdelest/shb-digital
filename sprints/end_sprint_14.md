# Sprint 14 — End (LOOP DOGFOOD)

**Theme (user chốt 19/7, full-auto):** dùng app như USER THẬT trên prod → finding → fix theo lô
→ re-verify → lặp tới sạch. 2 persona (A khách vay · B cán bộ duyệt), khung chấm "phục vụ được
chưa / dám ký chưa" — không phải "chạy được chưa".
**Commit:** 7896b29 (kickoff) · 58d3774 (A-01-BE) · 8c3a3ce (Persona A ×7 FE) · cdeb2a9 (B-01+
B-07 BE) · 985ffbb (B-01/07-FE + B-06) · 67350cd (nginx cache) · dc29769 (B-08) · 2940295
(wave nhẹ B-02/03/04) + docs (ba86853/564f2d7/6813997/7e94be9/7cda2b0/eeffa22) · đóng = commit này.

## Kết quả: 16 finding — 14 fixed+CHỐT PROD · 1 deferred · 1 test-artifact-hoá-fix

| Mức | Finding | Kết cục |
|---|---|---|
| 🔴 ×7 | A-01 credential lộ (D-64) · A-04 form mất data đổi tab · A-07 "+Ca mới" race · B-01 phiếu vô danh · B-06 badge (→fix first-tick) · B-07 từ chối không lý do (đứt mạch cả BE) · B-08 bell dropdown bị clip 87% | fixed, re-verified PROD |
| 🟡 ×5 | A-03 lỗi sai ngữ cảnh · A-05 timeline card "trống" (root: FE vứt field `detail`) · A-06 metric khó đọc · B-02 nhãn "Lý do AI" gắn nhầm policy-snapshot · B-03 ca lỗi không drill-down | fixed, re-verified PROD |
| ⚪ ×3 | A-02 brand landing · B-04 jargon dev | fixed · B-05 bố cục tab demo | B-05 **deferred** (gu — chờ lead/user) |
| hạ tầng | cache-stale index.html (FE bắt lúc verify prod) | fixed (nginx no-cache/immutable) + runbook §4b |

**Double-evidence:** B-01/B-07 chốt bằng 2 kịch bản độc lập (c001/L001 + dogfood-a1/L952 khớp
script từng ký tự). **A-07 race THẬT** kích hoạt trên latency prod và guard chặn — không phải
"pass vì chưa ép được".

## Bài học điều tra đắt giá (root cause ≠ nghi vấn ban đầu, 5 ca)
- A-07: không phải "onClick thiếu reset" — là RACE mount-effect resolve muộn ĐÈ user-intent.
- A-05: không phải "card rỗng"/"LAB drift" — items ĐỦ nội dung ở key `detail`, FE render hẹp
  (1 query prod 30s chốt, sau khi cả tester lẫn BE đoán sai; BE dừng đúng tripwire không sửa mù).
- B-06: án lật 2 lần (bundle cũ → automation visibilityState luôn hidden) → hoá FIX BỀN
  first-tick vô điều kiện (badge + bell), automation verify được từ nay.
- B-07: không chỉ thiếu ô nhập — mạch reason đứt ở BE (wake payload không mang, prompt hứa suông).
- B-08: bell "không mở được" từ Lô 2 tưởng lỗi thao tác — là bug thật (overflow clip 87%,
  elementFromPoint làm bằng chứng + làm luôn tiêu chí pass).

## Quyết định
- **D-64** áp phương án 2 (che admin/RM khỏi bề mặt public — 1 nhịp treo đúng quy trình:
  architect đề → lead giữ chờ gu user → lead decide-and-log §7, user override được).
- Deviation implementer được CHẤP 2 lần vì GIỮ SỰ THẬT: B-04 per-turn (phrase architect sai
  D-48) · B-03 conv-level (đúng nguồn con số).

## 3 Quality Gates
- [x] **Gate 1 — API**: field mới `display` + reason-mạch có integration test (+9 BE) · 4-field
  giữ (401/403 wording đổi CHỦ ĐÍCH D-64, test đổi có khai báo) · status code giữ · không
  primitive ngoài SPEC (JOIN read-time, portal, nginx header — không Redis/WS/outbox).
- [x] **Gate 2 — Function**: unit +41 (BE 343→352, FE 130→162) · edge đủ (payload rác, reason
  None/HTML-escape, visibility hidden, draft cross-user, item card rỗng/lạ) · fail-open/closed
  nói rõ (display fail-soft — "hàng chờ sống quan trọng hơn enrich") · ruff+format+tsc 0 (architect
  tự chạy) · author≠checker (tester độc lập, có 2 lần tự lật án của chính nó) · FE browser 2
  theme × mock/:8000/prod · money-path 0-đụng (30 test guard xanh mọi nhịp).
- [x] **Gate 3 — Sprint**: số TỰ CHẠY LẠI: **514 test (352 BE + 162 FE) ≥ 497** · CI xanh mọi
  commit · architect đọc trọn từng diff (11 lượt review, 1 blocker xử bằng query-prod) · tester
  13/14 finding re-verified PROD + browser · findings doc = sổ trạng thái đầy đủ · commit format
  đúng · invariant §15 giữ · UNVERIFIABLE → sổ ngoại lệ dưới, không mục nào treo.

## Sổ ngoại lệ (§6b — architect duyệt 19/7)
- **Mail inbox dogfood** — dogfood-a1@example.com không phải inbox thật, không kiểm được mail
  nhận; render đã có unit + template verify S9 bằng inbox thật — chấp nhận — xét lại nếu đổi SMTP.
- **Poll cadence 5s khi tab visible** — automation không giả lập được visibility thật (CDP luôn
  hidden); first-tick đã verify máy được, cadence để NGƯỜI liếc badge 10s trong rehearsal giờ G
  (đã ghi checklist) — chấp nhận — xét lại nếu có display thật cho automation.

## Dọn prod sau loop (biên lai theo số — bài học S13)
DELETE: 5 approvals (giữ 1 auto-rule mồi dashboard) · 3 loans L950/951/952 · 2 assessments (#6
C902, #7 C001-rác) · 5 conversations dogfood-a1 · 1 customer C902 · 1 user dogfood-a1. UPDATE:
L001 → active (đã bị disbursed trong e2e). **Verify sau dọn:** 3/3 loans active · stats
`approvals{approved:1,rejected:0,pending:0,auto:1}` NGUYÊN VĂN baseline · 5 assessments (#5
green giữ) · dogfood-a1 = 0 row. Còn lại chờ quyết: t9go1 (watch-item cũ, vô hại) · vài conv
test của c001 (reset theo script v9 trước giờ G).

## Nợ kỹ thuật ghi nhận (không chặn — refactor riêng sprint bảo trì)
- LOC >400 có sẵn trước sprint: `Workspace.tsx` 561 (+20 sprint này) · `api/mock.ts` 618 (+11).
- `tests/test_approvals.py` 500 (phình sprint này) → đề nghị tách `test_approvals_display.py`.
- Đề xuất bác trong sprint: BE list-tasks-failed API (không cần cho demo — conv-level đủ).

## Trạng thái sau sprint
Prod `digital.tinhdev.com` = bundle `index-DMAHaUjP.js`, đủ 14 fix + cache-fix, data baseline
demo sạch. Checklist giờ G bổ sung: hard-refresh máy demo đầu phiên (§4b) + người liếc badge 10s.
Hàng đợi ngoài sprint: S12 retrieval (⏸ D-63) · rehearsal 2-cửa-sổ tay · B-05 chờ gu user.

## Bài học sprint
- **Dogfood ĐEO PERSONA lòi đúng lớp bug test-kỹ-thuật mù**: 8/8 luồng nghiệp vụ từng PASS mà
  vẫn còn 7 demo-killer — vì test cũ hỏi "chạy được chưa", dogfood hỏi "phục vụ được chưa".
- **1 hành động kiểm rẻ trên MÔI TRƯỜNG THẬT thắng N vòng suy luận**: query card prod (A-05),
  grep bundle prod (B-06), elementFromPoint (B-08) — mỗi cú chốt án trong 1 lệnh.
- **Verify-được-bằng-máy là thuộc tính thiết kế**: B-06 bế tắc phân xử → fix first-tick biến
  badge/bell thành verify-được vĩnh viễn; phép đo của tester thành tiêu chí pass của FE.
- **Môi trường verify prod là một lớp test riêng**: cache-stale + 2 lần án-lật-vì-bundle-cũ —
  từ nay §4b bắt buộc sau mỗi redeploy.
