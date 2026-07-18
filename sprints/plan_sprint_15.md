# Sprint 15 — UX wave theo lệnh USER (19/7, kèm MẪU composer kiểu Claude)

User chốt 4 việc (backlog qua chat trực tiếp + screenshot mẫu):

| Task | Việc | Ai |
|---|---|---|
| T15-1 | Markdown chat: khoảng cách line hơi xa → siết line-height/margin | FE |
| T15-2 | Thiết kế lại select model theo MẪU: inline text-button góc phải dưới composer ("provider · model ˅"), dropdown gọn — thay picker hiện tại | FE |
| T15-3 | CRUD conversation: rename + delete (BE endpoints + FE UI sidebar) | BE+FE |
| T15-4 | **BUG prod**: không select được zai↔wrap — root ĐÃ CHỐT: `/api/models` top-level `default="claude-cli"` (provider bị disable, không có trong list) trong khi per-provider `zai.default=true`; FE key theo top-level → kẹt. Fix BE effective_default vào response + FE tolerant | BE+FE |

Root-cause T15-4 (biên lai): curl prod /api/models → `"providers":[zai(default:true), wrap]`,
`"default":"claude-cli"` ← sai, effective_default() đã có từ S10 nhưng response chưa dùng.

## User chốt (19/7, sau vòng bàn-plan-trước)
- T15-2: (a) nút hiện **1 dòng gộp** `model · provider` · (b) **switch per-turn được** ("chỉ là
  switch thôi mà") — PATCH conv {provider, model}, lượt sau đi model mới · (c) KHÔNG làm
  Chat/Cowork/mic từ mẫu.
- T15-3: phương án **(a) hard-delete** + chặn 409 khi phiếu pending/ca đang chạy; approvals đã
  quyết + tool_calls GIỮ (audit). Rename PATCH {title}. Quyền: chủ ca hoặc admin (Fix E scope).
- Kèm 2 việc mới cùng lượt: **check PR** (#5 Ollama — xử riêng) + **explore LAB missions/shb-132**
  (RAG + tools/skills đã hoàn thiện) → CHỈ PLAN task đưa user xem, chưa port.

## Kickoff — 2026-07-19
Backlog từ user trực tiếp (bàn plan trước → chốt → full-auto). Baseline: 514 test (352+162),
prod digital.tinhdev.com HEAD bef8c8f. Gate đóng: 4 task tester verify (T15-4 verify TRÊN PROD
sau deploy — đúng chỗ user gặp bug), test không tụt, CI xanh, deploy + §4b.
