# Sprint 12 — End (Port LAB drop: retrieval 4 tầng + Products/Ops CERTIFIED + planner)

**Commit chuỗi:** 754e66f (plan+D-65/66) · 52ea649 (T12-1+2, 97 file) · e075f37 (T12-3 porter merge)
· 13ce2d2 (fix check AST) · 4b44524+54dd040 (T12-4+addendum) · 1d66bb6+96c2389 (T12-3b+mài sắc) ·
d009e2d (FAIL B+C) · 2f38ab0 (HOTFIX F3+F2) · f0ac1ee/4d6cc29/096fedf (wrap sub_model+picker+guard)
· a0f918c (amount required) · c6b6fa5 (Dockerfile .cache) · đóng = commit này.

## Kết quả
- **Retrieval 4 tầng SỐNG trên prod**: wiki 82 trang (citation bắt buộc) · doc-graph phả hệ (trap
  `uu-dai-tet-68` cảnh báo thay-thế ĐÚNG trên prod) · vector notes 2.215 (bkai local-CPU, semantic
  PASS "xuất sắc" prod — C002/C008/C019 + note_id; D-68b khách bị refuse `internal_only`) ·
  entity-graph trần NHÓM (C013→B002/B004, 8.000 tỷ, ground-truth khớp LAB TỪNG SỐ qua PG).
- **4/4 chuyên gia ruột thật**: Products (13 gói, suggest theo segment thật) + Operations
  (app/plan/disburse pipeline — `ops_disburse` GATED độc lập thứ 2, e2e prod DSB03 + receipt) port
  CERTIFIED v1, vỏ 0 sửa. `ops_disburse` chạy THẬT dưới phanh qua OpsConnProxy (tx-strip + raise-on-
  blocked — money-invariant 'used'⟺tiền-chạy giữ; blocked rơi loop-bound T4-0; 2 lớp idempotency).
- **SKILL merges (D-65a)**: legal/credit + SÁCH TRA CỨU verbatim; main_skill cherry 6 luật planner
  v0 (bàn-giao-nguyên-văn, chuỗi +Products, hoà-giải income_override, disclosure, 3-mốc, trùng-tên).
- **World-swap prod 8bf6b4** GIỮ users/convs/tool_calls (D-65b — biên lai 7/20/183) + MAIN_MODEL
  env-driven, prod default wrap/gpt-5.4 (lệnh user) + image +embed extra CPU-torch + hf_cache volume.

## Vòng lặp build→sai→update (đúng vai — 5 FAIL thật đều bị bắt TRƯỚC demo)
- Wave T12-5: A2 stale-roles (env — `--reload` KHÔNG watch roles/ → luật restart mới) · B thiếu
  products/segment trong world-swap · C display enrich hard-code key cũ.
- Bench-builder S17 (giá trị chéo): **F3 disburse MẤT MOUNT** (port-replace file xoá registry stub —
  demo money-path gãy, wave từng PASS vì stale-module che) + **F2 credit thiếu income_override_vnd**
  (VỎ giữ bản LAB cũ). Bài học: port-replace cần test GIỮ-TOOL-VỎ, không chỉ test đúng-LAB.
- Prod round: **wrap-haiku 502** (giả thuyết architect ghi sổ TRƯỚC 15' — confirmed nguyên văn;
  fix sub_model + GUARD test chống nguyên class) · picker models[0] lệch MAIN_MODEL · amount=0 lọt
  disburse (schema REQUIRED).

## Quality Gates
- [x] **Gate 1 — API**: display/cost/stats mở rộng có integration test; 4-field giữ (found:False
  chuẩn hoá); không primitive ngoài SPEC (vector CHỈ interaction_notes — D-65 lật hẹp có sổ).
- [x] **Gate 2 — Function**: BE 352→410 test · edge đủ (payload rác/memoryview/blocked-3-nhánh/
  cross-conv-dup/stale-module) · fail-open/closed nói rõ từng chỗ · ruff/format sạch · author≠checker
  (tester độc lập + bench-builder làm finder chéo) · money-path 43 test neo, 0 đụng đường disburse cũ.
- [x] **Gate 3 — Sprint**: tester wave local 5/5 + prod round (A3 semantic + smoke 5-deliverable +
  S16 số thật + ops e2e) — 2 điểm wrap re-verified PASS (picker gpt-5.4 UI thật + sub gpt-5.4-mini hết 502, by_model xác nhận) + income_override PROD PASS (DSCR 70.058, tool_calls receipt) · số TỰ CHẠY LẠI: **637 test (410 BE + 227 FE) ≥ 605** ·
  invariant §15 giữ · deviation LAB có sổ (MIN-via D-68c — LAB re-sync upstream đã relay user).

## Sổ ngoại lệ / nợ ghi nhận
- Phiếu `exec_failed` chưa mang reason (chốt (a) — nâng (b) nếu demo lòi nhu cầu đọc-phiếu).
- products/ops chưa có `SKILL.present.md` provisional (D-36) — card canvas 2 role do MAIN trình thay.
- sqlite IntegrityError map trong OpsConnProxy: defensive-unexercised (khai thật).
- LAB upstream cần re-sync: retrieval.py MIN(via) + credit.py đã có sẵn income_override (VỎ sync lại rồi).

## Bài học
- **Finder chéo bắt lỗi finder chính bỏ sót**: bench-builder (mục tiêu khác) lộ 2 regression mà
  wave chuyên verify không thấy — vì wave chạy trên server stale-module. Môi trường verify là một
  phần của phép đo.
- **Ghi giả thuyết trước = chẩn đoán nằm sẵn**: wrap-haiku từ FAIL đến fix-committed <20'.
- **Port-replace file = thay registry**: cần test giữ-tool-vỏ + restart server (roles/ ngoài
  watch-scope reload).
