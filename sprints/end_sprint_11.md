# Sprint 11 — End

**Theme:** Cleanup + docs + nâng-điểm-chấm (từ review ngoài user đưa — phản biện có biên lai,
nhận phần đúng) + các lệnh user giữa sprint (google live, form/flaky, dark/light, logout,
kịch bản test nghiệp vụ).
**Commit:** f7e9332 (kickoff) · 2b1ec4d (METHODOLOGY+README-60s) · cb6dd2d/15e03f5 (CI + vá
secret-test) · a690ec9 (badge) · bd9350d (T11-4a) · ff3ad42 (T11-4b google/flaky) · 943f310
(T11-2 refactor + T11-5) · 7351b10 (T11-6 theme) · 276ce03+54e755c (logout) · 32d88af
(scenarios 7/7 + script v9) · đóng = commit này.

## Kết quả

### Nâng điểm chấm (review ngoài)
- **T11-1 CI GitHub Actions** ✅ — PG service + pytest/ruff/format + vitest/tsc, badge README.
  Run#1 BE đỏ = CI bắt đúng false-green local (test phụ thuộc secret .env) → vá gốc dummy-
  monkeypatch + LUẬT conftest "local-mirror phải mirror SỰ VẮNG MẶT secret". 6+ run xanh liên tiếp.
- **T11-2 refactor gated 0-đổi-hành-vi** ✅ — tách 5 nhánh giữ-1-tx, `_save_receipt` khử lặp
  (giữ khác biệt set_used_at claim/auto — trap chính), log.exception cửa-cuối, Protocol/TypedDict
  ranh giới tiền. 41 money-test + suite pass KHÔNG SỬA TEST, SQL runtime byte-identical.
- **T11-3 docs** ✅ — `docs/METHODOLOGY.md` (khuôn khai-thật + §6 mới "người duyệt ở tầng TOOL");
  README "⚡ Chạy thử 60 giây" compose-1-lệnh + badge. Hygiene: dọn worktree/branch.
- **T11-4a/5 English docstring surface** ✅ (thân tiếng Việt giữ — giám khảo VAIC/SHB người Việt).
- Phản biện KHÔNG làm: lockfile (đã có sẵn — reviewer chấm bản backup thiếu git), dịch toàn bộ
  comment (sai đối tượng).

### Lệnh user giữa sprint
- **Google auth LIVE trên prod** ✅ — env cắm + redirect/FRONTEND_URL/COOKIE_SECURE prod;
  /start 307 accounts.google.com; nút env-gated + template chuẩn (logo G inline SVG).
- **T11-4b fix flaky mở modal** ✅ — root: Login self-fetch providers sau paint → layout-shift;
  fix prefetch-từ-page-load + reserve-chỗ; prod đo thật gap=0ms noShift=true.
- **T11-6 dark/light default LIGHT** ✅ — tokens theo data-theme, inline blocking script no-FOUC,
  persist, 2 mode × 3 mặt verify prod.
- **Logout thật** ✅ — bug FE phát hiện (đăng xuất không xoá cookie httponly → reload re-auth,
  máy demo dùng chung): POST /api/auth/logout delete_cookie khớp attributes; prod verify me
  200→401→Landing, reload không auto-vào-lại.
- **Kịch bản test nghiệp vụ** ✅ — `docs/business-test-scenarios.md`: tester viết + CHẠY THẬT
  7/7 luồng PASS trên prod (kiêm regression gate S11). Luồng 3 đủ 3 tầng ma trận với
  **assessment #5 thật** (594tr>500tr auto vì green). Finding vàng: script sai số seed
  (L006/L007) + Fix-A ownership → script v9.

## 3 Quality Gates
- [x] **Gate 1 — API**: logout mới (idempotent, deletion-header khớp attributes) + /api/stats
  chưa có (S13) · 4-field giữ · test cũ pass · không primitive (CI/theme/logout đều tooling/UI/
  endpoint thường).
- [x] **Gate 2 — Function**: unit mới (+2 logout, +5 useTheme, +2 google-gate, +1 best-effort,
  +5 effective-default...) · edge đủ (secret-vắng, cookie-attributes, FOUC, private-mode
  localStorage) · refactor money-path 0-đổi có guard 41 test · ruff+format+tsc sạch · author≠
  checker giữ · FE verify prod thật cả 3 cụm · LOC ≤400 (gated 385 + gated_types).
- [x] **Gate 3 — Sprint**: số liệu TỰ CHẠY LẠI: **477 test (357 BE + 120 FE) ≥ 465** + CI xanh
  khách quan mọi commit · architect đọc trọn từng diff trước 11 commit · tester 7/7 luồng
  nghiệp vụ trên prod + FE 3/3 verify gộp · findings ghi (script-v9 seed, cookie-share-đa-tab,
  502-tunnel) · commit format · invariant §15 giữ (refactor gated verify SQL byte-identical) ·
  UNVERIFIABLE: 0 mục mới ngoài 2 waiver dưới.

## Sổ ngoại lệ (§6b — 2 mục mới, tester đề + architect duyệt)
- **502 Cloudflare tunnel thoáng qua** (1 lần, tự phục hồi <20s, không lặp) — hạ tầng ngoài,
  xét lại nếu gặp lần 2 trong phiên demo.
- **Cookie-share đa tab MCP** (2 lần gây nhiễu thao tác test, tự chẩn đúng cả 2) — giới hạn
  công cụ, bài học vận hành đã ghi vào scenarios doc: không chạy nhiều persona song song đa tab.

## Trạng thái prod sau sprint
digital.tinhdev.com: đủ google-auth + theme + logout + mọi fix; L001/L007/L108 đã restore
active + approvals sạch (sẵn demo); account test t9prod1/t9go1 còn (vô hại). Image durable
UID/GID đã live (volume chown 1000 lần cuối).

## Bài học sprint
- **CI trả công ngay run đầu** — bắt false-green-secret mà local không bao giờ thấy; lớp bài
  học thứ 3 "môi trường sạch mới lộ phụ thuộc ngầm" (seed→configs→secret).
- **Vướng-verify đôi khi là BUG SẢN PHẨM** — FE bí đường anon-flow vì logout không thoát thật;
  vá bug mở luôn đường verify (chọn (d) thay vì lách (a/b/c)).
- **Script demo phải đối chiếu seed BẰNG SQL mỗi lần seed/guard đổi** — lớp lỗi thứ 3 (tên →
  purpose → amounts+ownership); checklist script giờ có mục "query lại số trước giờ G".
