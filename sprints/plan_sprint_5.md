# Sprint 5 — Plan

<!-- DRAFT do architect nháp cuối S4. Kickoff = đọc SPEC §16 B6 + end_sprint_4 + D-50, sửa in-place. -->

**Objective:** Polish + demo-ready (thi Đà Nẵng) + agent-bền D-50 (nếu kịp).
**Theme:** Sẵn sàng đứng trước giám khảo.
**Gate S5 (dự kiến):** demo-script ca "DN X vay 5 tỷ" chạy mượt end-to-end (chat → đội song song →
canvas → phanh → duyệt → giải ngân → trace/Tower/compare) + seed-reset 1 lệnh trước mỗi lần chạy.
**Baseline:** 282 test (208 BE + 74 FE).

## Tasks (draft)

### T5-0 — Demo script + rehearsal
Kịch bản demo 5 deliverable theo thứ tự kể chuyện: (1) chat ca DN X → đội song song (live map/trace F1)
(2) canvas card có nguồn (3) phanh: giải ngân → chặn → Control Tower duyệt → resume → biên nhận
(4) Tower: audit/status/cost (5) compare 1-vs-đội (6) đổi model (zai/GPT) tạo ca. Đo timing từng bước
+ câu thoại. Chạy thử N lần với seed-reset.

### T5-1 — Polish UI theo mock (D-13/D-24)
Rà look-and-feel vs design/mock — lệch thẩm mỹ lớn sửa, 3D lobby CHỈ nếu dư thời gian (D-24).

### T5-2 — Agent-bền per-(conv, role) — D-50 (NẾU KỊP trước demo, không thì sau)
Lật #15 chủ đích (sửa claude-sdk.md + D-entry): sub session lưu (conv, role) → dispatch role lần 2
cùng ca = RESUME (nhớ lượt trước) → nền Hướng-2 (A nhận biên bản) + F2b (chat-sub). Port cơ chế
MAIN-resume. Phạm vi: bền theo CA (đề xuất D-50).

### T5-3 — Nợ kỹ thuật nhỏ (nếu rảnh)
sub_model per-provider (wrap multi-agent) · SSE-live queue Tower · seam-test buffer khi có runner-seam.

### T5-4 — Tester: gate demo-rehearsal
Chạy demo-script như giám khảo: timing + mọi bước PASS + không cần dev can thiệp.

## Nợ từ S4
Xem end_sprint_4 findings: wrap sub-model (a-accepted) · F2b/D-50 (T5-2) · SSE-live queue · exec_failed
re-mint edge (hiếm).

---

## Kickoff — 2026-07-18

**Drift:** none (draft mới viết cùng ngày). **Ưu tiên:** demo-prep trước (T5-0 script + T5-4 rehearsal
+ T5-1 polish); **T5-2 agent-bền CHỜ user chốt lịch demo** (nếu demo sát → dời sau demo; user chưa trả
lời lịch 17-19/7). T5-3 nợ nhỏ chỉ khi rảnh.

**Final:** T5-0 architect viết script → T5-4 tester rehearse · T5-1 FE polish (song song) · T5-2/T5-3 treo chờ lịch.
