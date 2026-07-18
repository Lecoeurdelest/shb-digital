# Sprint 7 — DRAFT (LAB legal 3-nguồn port + verdict-xanh wire)

> Nháp lúc đóng S6 — kickoff S7 sẽ chỉnh tại chỗ. Nguồn sự thật phong bì bàn giao:
> `../shb-digital-experts/reports/AGENT-legal-DONE.md` (CERTIFIED 18/7, skill v3 · tool a354fd ·
> keys 8a4d43) + D-52 (pain người ra đề: pháp lý 3 nguồn Bộ CA / CIC / lương, hồ sơ xanh agent
> tự duyệt). Demo Đà Nẵng 17-19/7 — port này là NỘI DUNG pain-point, ưu tiên trước polish.

## Theme
Thay legal v0 prod bằng legal CERTIFIED của LAB: 5 tool thật (3 nguồn + classify_profile WRITE)
+ wire verdict-xanh vào phanh phân tầng (`_auto_approve_ok(args, verdict)`) + demo script cập nhật.

## Task dự kiến

### T7-1 — Migration + seed 3 nguồn (backend, gating — đi trước một mình)
- Alembic: bảng `police_records` / `employment_records` / `assessments` (schema theo LAB
  `missions/shb-132/seed/` — đối chiếu khi kickoff) + 6 dòng `assumptions` tag
  `mentor-1807-hypothesis` (auto_approve_max_vnd=2e9, income_mismatch_max_pct=10,
  blocked_record_types, cic_block_min_group=3, criminal_record_expiry_years=7, lane_policy v1).
- Seed port từ LAB (canonical md5 e0a009e2) vào seed_from_lab + reset_demo giữ nghiệp vụ mới.
- Chú ý: `assessments` là bảng GHI runtime (như approvals) — reset_demo phải wipe.

### T7-2 — Port tool + SKILL (backend, sau T7-1)
- `roles/legal/functions.py` ← LAB `missions/shb-132/tools/functions/legal.py` (5 tool:
  check_docs / check_compliance / check_police / verify_employment / classify_profile).
  classify_profile WRITE qua PGConnAdapter (quyền ghi assessments). Contract adapter đối chiếu
  pattern D-08 (copy labpack, PG conn inject).
- `roles/legal/SKILL.md` ← LAB skill v3 (thay v0). KHÔNG sửa nội dung skill đã certify —
  lệch prod cần gì → blocker về LAB, không tự vá (thước LAB là nguồn sự thật đã trả $35 train).

### T7-3 — Wire verdict-xanh vào phanh (backend, sau T7-2 — architect viết Logic/Algorithm
kickoff)
- `gated.py _auto_approve_ok(args, verdict)`: verdict = bản ghi `assessments` MỚI NHẤT theo
  loan/khách (wrapper disburse đọc — phong bì chỉ định). Xanh + trong ngưỡng lane_policy →
  auto-approve (decided_by='auto-rule' + reason dẫn assessment id); không xanh/không bản ghi
  → đường người duyệt như cũ (fail-closed).
- Ngưỡng 500tr hiện tại vs auto_approve_max_vnd=2e9 của LAB assumptions: architect quyết ở
  kickoff + DECISIONS (nghi 2 tầng: rule-tiền + verdict-hồ-sơ).

### T7-4 — Demo script + FE nhẹ (frontend/architect, song song sau T7-2)
- Script v5: cảnh pháp lý 3-nguồn (check_police/verify_employment thật) + cảnh xanh-tự-duyệt.
  MỌI TÊN/MÃ KHỚP SEED MỚI. FE: card assessment nếu cần (nghi đã có card type đủ — kiểm trước).

### T7-5 — Tester: regression + smoke mở rộng
- Suite cũ 100% (legal đổi tool → gate S2/S3 legal case soát lại) + smoke thêm nhánh
  xanh-tự-duyệt nếu rẻ + labels LAB (tự-phán-lane / tự-duyệt-vượt-quyền / cầu-cứu-thừa) làm
  checklist chấm tay 1 vòng live.

## Nợ mang theo (không chặn theme)
- `_wait_for_settled` → helper chung conftest (bịt thoáng-idle toàn suite).
- Xác nhận live 2-process ở lần restart kế (sổ ngoại lệ S6).
- Agent-bền D-50 — SAU demo (user chốt).

## Gate S7 (dự kiến)
Ca hồ sơ vay live: legal chạy 3 nguồn THẬT (police/CIC/lương có audit rows) → classify ghi
assessments → hồ sơ xanh dưới ngưỡng TỰ DUYỆT dẫn assessment id, hồ sơ đỏ/thiếu → phiếu người
duyệt. Suite ≥ 302. Script v5 rehearsal 1 vòng.

---

## Kickoff — 2026-07-18 (architect)

**Drift so plan gốc: <10%** — plan viết cùng ngày từ phong bì, đọc code LAB thật xác nhận +
3 điểm cụ thể hoá (D-55 log DECISIONS):

1. **LAB code viết trên sqlite3** (`?` placeholder, `conn.execute`, `lastrowid`, `commit`) —
   prod đã có PGConnAdapter (D-27) nhưng **read-only** (`gated.py` note "adapter chỉ cho LAB
   read tool"). → T7-2 thêm việc: mở WRITE khoanh vùng bảng `assessments` (INSERT + commit +
   lastrowid emulate qua RETURNING id). LAB code byte-identical.
2. **`legal.py` import `from .credit import _assumptions, credit_assess`** — LAB để chung 1
   package, prod tách `roles/<role>/`. → đổi ĐÚNG 1 dòng import sang labpack credit prod
   (share-tool server-side, user đã chốt 18/7). Kèm điều kiện: **đối chiếu credit prod (312
   LOC) vs credit LAB hiện tại** — classify gọi credit_assess, nếu LAB credit đã tiến hoá so
   bản prod cầm (S1 port) thì đồng bộ credit TRƯỚC trong T7-2 (cùng nguyên tắc copy nguyên).
3. **Bảng cần soát ở T7-1**: mới chắc chắn = `police_records` / `employment_records` /
   `assessments`; nghi ĐÃ CÓ từ port trước = `cic_records`, `legal_requirements`,
   `owner_documents`, `collateral_legal`, `restricted_purposes` — backend grep migration cũ
   trước khi viết migration mới, chỉ tạo cái thiếu.

**Task list final:** T7-1 (gating, một mình) → T7-2 (sau T7-1) → T7-3 ∥ T7-4 (sau T7-2) →
T7-5 xuyên suốt. Thứ tự giữ nguyên plan. Verdict-hook `_auto_approve_ok(args, verdict)` đã
chừa sẵn từ S5 — T7-3 chỉ wire, không đổi cấu trúc phanh.
