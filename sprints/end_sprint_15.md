# Sprint 15 — End (UX wave theo lệnh user, kèm mẫu composer Claude)

**Commit:** 2df84e9 (plan) · af8782b (BE 3 task) · 1068300 (FE tail; thân FE lên master qua
snapshot 8c3a3ce→d8de335 do sự cố tree-chung — khai trong end này) · 4e59331 (compose D-66) ·
đóng = commit này.

## Kết quả (4 task user chốt)
- **T15-4** 🔴 bug prod "không switch được zai↔wrap": root = `/api/models` top-level default
  trỏ provider ĐÃ DISABLE (default_name thay vì effective_default — sót từ S10). Fix 1 dòng +
  FE resolveSelection tolerant (không bao giờ trỏ provider ma). Tester PASS cả case mạnh
  (SHB_PROVIDERS_DISABLED → default=zai) + PROD live. Kèm phát hiện lúc deploy: compose
  hardcode `environment:` ĐÈ .env → sửa đúng chỗ (D-66 local ẩn khỏi picker prod).
- **T15-2** composer kiểu mẫu Claude: ModelSelect text-button 1 dòng "model · provider ˅",
  dropdown portal group theo provider, has_key=false disable; **switch PER-TURN** (PATCH conv
  {provider,model}, validate theo provider-kết-quả, 409 khi running; lượt sau đi model mới —
  main đọc conv fresh mỗi lượt). ModelPicker cũ archive (local-only, gitignore .archive).
- **T15-3** CRUD conversation (3a): PATCH rename + DELETE hard 1-tx (chặn 409 pending-phiếu/
  đang-chạy; xoá conv+messages+cards+tasks; GIỮ tool_calls + phiếu đã-quyết — **D-67** phân loại
  nội-dung-ca vs dấu-audit). Sidebar rename inline + delete 2 bước (pattern B-07), khách chỉ
  thấy ca mình (scope cookie + can_access_conv 404-hide).
- **T15-1** markdown spacing siết (line-height 1.45) — user chê "hơi xa", giờ đặc, không dính.

## Verify
Tester local: BE 3/3 (18 case + invariant số-row audit-giữ) + FE 4/4 (trap label-theo-ca,
409-hint UI, per-turn qua UI). **PROD 4/4** (bundle C4Pe1jXH): picker chỉ zai+wrap, switch
zai↔wrap THẬT mượt (đúng chỗ user gặp bug), rename/delete tự dọn, markdown thoáng.
Baseline sau vòng: 3/3 loans active + 1 phiếu auto — nguyên văn (soát số).
Giới hạn khai thật: "bằng chứng model-thật-đổi tầng SDK" không chứng minh được từ ngoài →
thành yêu cầu chính thức T16-1 (per-turn log provider/model/base_url).

## 3 Quality Gates
- [x] **Gate 1**: PATCH/DELETE/models — 4-field đủ (400 bad_provider/bad_model/empty_patch,
  404-hide, 409 ×2 loại), integration test mới +17, test cũ pass, không primitive mới.
- [x] **Gate 2**: unit BE 352→369 + FE 162→180 · edge (provider ma, model lệch, race xoá-giữa-
  đọc, running-guard 2 nguồn) · ruff/format/tsc 0 (architect tự chạy) · author≠checker ·
  browser 2 theme + PROD.
- [x] **Gate 3**: số tự chạy lại **549 test (369 BE + 180 FE) ≥ 514** · CI xanh mọi commit ·
  đọc trọn diff từng cụm · tester local→prod trọn · commit format · invariant §15 giữ (money-
  path không đụng; DELETE giữ audit) · UNVERIFIABLE: chỉ mục model-thật-đổi → chuyển T16-1
  (không waiver — thành backlog có chủ).

## Sự cố quy trình (khai thật + luật mới)
- **Commit-tree-chung nuốt WIP FE** (2 nhịp): index + `git commit -- path` đều bẫy — master
  gãy 2 run CI rồi lành (`d8de335`). Luật mới trong memory architect: soát `--cached` trước
  MỌI commit, cấm pathspec-commit khi teammate đang code.
- **:8000 treo ×3**: root A reload-wedge (WatchFiles chờ SSE vô hạn — ×2) + root B worker mồ
  côi giữ port. Diệt gốc: D-38 thêm `--timeout-graceful-shutdown 5` (CLAUDE.md §1 đã sửa) +
  luật kill-cả-cây. Dev-infra thuần, prod không dùng --reload.

## Trạng thái sau sprint
Prod: đủ S15 + D-66; models `default: zai | [zai, wrap]`. Song song đang bay: T12-2 (BE) ·
T12-3 (porter worktree) · T16-3 (FE contract-first). DB local: 162 phiếu rác pytest — kệ,
world-swap T12-2 thay sạch.
