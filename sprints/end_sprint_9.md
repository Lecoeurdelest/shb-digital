# Sprint 9 — End (kèm S10-deploy đóng sớm theo lệnh user)

**Theme (D-57 mentor):** khách MỚI + vòng đời hồ sơ (register → form intake → hồ sơ C9xx →
honest-null yellow → người duyệt → MAIL thật + bell). **Giữa sprint user lệnh trực tiếp:**
deploy công khai `digital.tinhdev.com` (S10 kéo lên sớm) + brand D-61 + merge PR#1/#2/#3.
**Commit:** 5059e1a (T9-1+siết) · 4f0f49d (T9-3 FE) · 2dd07c3 (T9-2 mail HTML) · 184a116 (FixA+B)
· 0c76e26 (FixC) · c9190a6 (FixD) · adc83ab (FixE+F+name) · f53a244 (UV_NO_SYNC) · e267339
(effective-default) · 6ec86bc (durable volume ownership) · merges 8eb1b92/59b1122 (sweep D-61) ·
1d37027 (PR#1 lobby 3D) · landing+google (5d06692→master) · 1de8768 (D-60 markdown) · đóng = commit này.

## Kết quả build (4 task gốc)
- **T9-1** register + present_form (fields server-side) + form-submit (card-flip-first idempotent
  + mint C9xx advisory-lock + commit-trước-wake) + inject 3 trạng thái + reset_demo C9xx.
- **T9-2** mail Gmail HTML brand (multipart, no-op sạch thiếu env, hook decide/receipt
  fresh_disburse — replay không mail lại, fail không chặn resume) + GET /notifications derive.
  LIVE-TEST 3 kind về Gmail thật.
- **T9-3** FE Register tab + FormCard (render theo fields server, reload-safe) + bell poll.
- **T9-4** tester e2e vòng đời trọn 6 bước PASS (form không hỏi vặt · yellow honest-null ·
  mail + bell sống · khách cũ không bị form).

## DEPLOY công khai (user lệnh "ko chờ deploy lẹ") — S10 core đóng sớm
- dev-vm GCP: compose 3 service (project `shb132-prod`, port 8011/3011 cô lập, volumes SDK/conv/
  PG) + cloudflared `digital.tinhdev.com` (backup config; web mẫu :3010 vốn đã chết trước swap).
  digipad.tinhdev.com: thêm rồi gỡ theo 2 lệnh user (backup-restore sạch, digital không rớt).
- **6 fix sinh ra từ prod thật (vòng chấm tester là máy phát hiện):**
  A cross-owner disburse guard (money) · B restart-script · C SHB_PROVIDERS_DISABLED ·
  D image thiếu COPY configs/ · **E READ-scope choke point tầng mount (leak hồ sơ chéo khách —
  nghiêm trọng nhất dự án, known-limitation S8 chết khi lên public)** · F VITE mock-off.
  + effective-default (picker không preselect provider ẩn) · UV_NO_SYNC (runtime không được cần
  mạng) · durable volume ownership UID/GID (port DevCrew ref user đưa) · chown 2 volume tay ·
  NOTIFY_FROM_NAME env override (lỗi architect — sweep code không quét .env).
- **Merge PR:** #1 lobby 3D (dep-union) · #3 landing + #2 google-auth (landing chồng google —
  resolve router/Login giữ đủ register+google+brand; re-parent migration hết 2-head fork;
  google default-OFF: no env → 503 4-field, nút ẨN).

## Gate cuối — tester 6/6 PASS trên https://digital.tinhdev.com (bản e267339 + env fix)
| # | Mục | Kết quả |
|---|---|---|
| 1 | Picker zai+wrap, claude-cli→400 | PASS |
| 2 | Cross-owner refuse (A/E) not_your_loan | PASS |
| 3 | Read-scope 2 chiều (chặn người khác · cho chính mình) | PASS |
| 4 | Mail brand đồng nhất From/subject/body (so sánh trực tiếp mail cũ SHB cùng inbox) | PASS (vòng 2 sau env fix) |
| 5 | Tower + SSE-qua-tunnel + banner MOCK biến mất | PASS incidental |
| 6 | Landing anon → 3D → modal login (Google ẩn) | PASS |

## 3 Quality Gates
- [x] **Gate 1 — API**: register/form-submit/notifications/google mới — 4-field đủ (409/400/404/
  503), status phân biệt chủ đích; test cũ pass; không primitive ngoài SPEC (bell=poll, mail=
  smtplib stdlib).
- [x] **Gate 2 — Function**: unit mới ~60 (t91 13 + notify 12 + guard 8 + fixc 12 + read-scope 12
  + seed_if_empty 5 + google 10...) · edge/fail-mode nói rõ từng guard (fail-closed money/leak;
  fail-open có chủ đích ghi note) · ruff+format+tsc sạch · author≠checker giữ · FE Chrome + prod
  browser · LOC ≤400 (tách disburse_guard/read_scope/verdict) · không copy-paste.
- [x] **Gate 3 — Sprint**: số liệu TỰ CHẠY LẠI: **355 BE + 110 FE = 465 ≥ baseline 378** ·
  architect đọc trọn mọi diff trước từng commit (13 commit) · tester e2e local + 6/6 PROD ·
  findings ghi (dưới) · commit format · invariant SPEC §15 giữ (phanh nguyên cấu trúc, thêm 2
  guard TRƯỚC phanh) · UNVERIFIABLE đóng hết (mail thật ×2 vòng, restart-persistence, fresh-volume).

## Sổ ngoại lệ: đóng cũ, không mở mới
- **S6 "2-process" ĐÓNG**: tester đếm trên restart thật = uv-wrapper + child = thiết kế.
- **S8 "2-cửa-sổ-cùng-lúc"** vẫn treo (giới hạn tool — người verify tay trước giờ G).
- Sprint này: KHÔNG mục mới.

## Findings mở (không chặn — mang sang polish/S11)
- Tooltip text "Đăng nhập với Google" sót khi nút ẩn (FE polish 1 dòng).
- Google auth chưa bật (chờ user cấp GOOGLE_CLIENT_ID/SECRET nếu muốn dùng thật).
- DNS CNAME digipad còn trên Cloudflare (trả 404, vô hại — xoá dashboard nếu muốn sạch).
- PR#2/#3 GitHub chưa auto-close (merge qua branch resolve — đóng tay khi push).

## Bài học sprint (đắt nhất từ đầu dự án)
- **Known-limitation chết khi đổi ngữ cảnh**: read-scope "làm sau demo" ổn khi app nội bộ —
  thành lỗ hổng thật NGAY khi URL public. Mỗi lần đổi ngữ cảnh triển khai phải re-review sổ
  known-limitation, không mang theo như định mệnh.
- **Prod là máy phát hiện lỗi tốt nhất**: 6 fix trong 1 buổi đều do chấm-trên-prod-thật lộ ra
  (image thiếu file, env override, volume ownership, DNS runtime) — những lớp local/unit không
  bao giờ thấy. Deploy sớm theo lệnh user hoá ra là quyết định chất lượng.
- **Sweep hằng số phải quét CẢ env đang override** (NOTIFY_FROM_NAME) — code đúng, env cũ đè.
- **Runtime container không được cần mạng** (UV_NO_SYNC) + **volume ownership phải sinh đúng
  từ image** (UID/GID) — 2 nguyên tắc port từ pattern DevCrew của chính user, "đừng tự chế bánh xe".
