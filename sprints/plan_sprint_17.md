# Sprint 17 — BENCH: single-agent-full-tool vs hệ action-oriented (deliverable #5 dạng số liệu)

**User chốt (19/7):** tách folder riêng `bench/` · ~12-15 case · **cả 2 bên cùng SONNET**
(fair 1-model; note: prod thật sub=haiku — bench override sub_model=sonnet, report ghi rõ) ·
single-agent PHẢI nhận **TẤT CẢ hướng dẫn (main_skill + 4 SKILL role ghép) + TẤT CẢ tool**
(kể cả disburse/ops_disburse QUA PHANH — đo tuân-thủ-phanh là kịch tính chính của report) ·
response 2 bên file riêng · REPORT tổng + đánh giá architect.

**Đã có để tái dùng:** LAB `reports/SS-SINGLE-VS-MULTI.md` (phương pháp + đề rig-side — đọc,
không trùng) · LAB keys 29 key/4 phòng certified · tab So-sánh S4 (live 1-câu — giữ làm demo,
bench này là bản có-số-liệu) · T16-1 instrument (tokens/cost/duration đo thật).

## Cấu trúc
```
bench/cases/*.yaml        # case: prompt + ground-truth key + rubric + loại (đơn-phòng/liên-phòng/trap/phanh)
bench/run_multi.py        # qua HỆ THẬT (API :8000: tạo conv sonnet → chat → chờ event → thu transcript+tasks)
bench/run_single.py       # 1 SDK session: SKILL ghép + mount TOÀN BỘ tool 4 phòng + common + gated
bench/grade.py            # autograde theo key + scorer opus adversarial (chấm chất lượng + bịa-số)
bench/responses/{multi,single}/case-XX.md
bench/REPORT.md           # bảng: đúng/sai · số-có-nguồn · tool-calls · tokens/cost/duration · phanh
```

## Bộ đề (~14): 8 đơn-phòng (2/role, chưng từ LAB keys) + 3 liên-phòng (vay-trọn-gói, lương-lệch
hoà giải, hồ-sơ-tới-đâu) + 3 trap (trần NHÓM C013 · phả hệ ưu-đãi-Tết-68 · disclosure khách)
+ 1 phanh (yêu cầu giải ngân — kỳ vọng CẢ 2 dừng ở phiếu; single vượt phanh = finding đắt).

## Phase
1. **Harness build** (worktree agent — đang chạy): cases + runners + grader + smoke 1 case.
2. **RUN full** sau T12-5 wave (world đứng yên): 14 case × 2 bên × sonnet.
3. Grade + REPORT + đánh giá architect → trình user.

## Kickoff — 2026-07-19
Không đụng backend/frontend (folder riêng, chạy ngoài như harness). Gate: report có số tự chạy
lại được + response files đầy đủ + scorer verdict không tin text suông.
