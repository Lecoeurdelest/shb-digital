# Sprint 20 — evidence tester-1

**Ngày:** 2026-08-24
**Phạm vi:** T20-5 API/DB/migration + kiểm tra ngược PM.
**Nguyên tắc:** độc lập với test của dev; không sửa production để làm gate xanh.

## Audit PM / traceability

| Claim / invariant | Gate máy kiểm trong plan | Kết luận |
|---|---|---|
| Dashboard cho thấy tổng, lane/day và drill-down đúng phiếu | T20-1, T20-2, T20-6: ba ca comparable cố định, `2/3 = 66,7%`, exact S19 href/highlight | Có trace |
| Mismatch API admin-only, tenant-scoped, read-only | T20-1, T20-5: auth roles, cross-tenant, static write-path check | Có trace |
| Consent versioned và chứng minh đúng nội dung đã hiện | T20-3, T20-4, T20-5/T20-6: server snapshot, SHA-256, client chỉ gửi `true`, SQL proof | Có trace |
| Hồ sơ và consent cùng transaction | T20-4, T20-5: forced failure + SQL before/after + retry/double-submit | Có trace |
| D-80 không phải DPIA/compliance | Objective, D-80, wording, T20-3 và kết luận T20-6 đều ghi PILOT NO-GO trước bank sign-off/impact assessment | Có trace; không thấy compliance claim |
| Baseline `807 pass + 17 skip` | Plan dẫn `end_sprint_21.md` và yêu cầu fresh suite tại kickoff | **FAIL PM-01:** Kickoff tự ghi fresh suite chưa chạy nhưng vẫn dispatch. Con số chỉ được coi là historical baseline, chưa phải current baseline. |
| Hai tester độc lập kiểm tra PM | T20-5 và T20-6 đều có review PM | **FAIL PM-02:** T20-6 khai dependency T20-5, mâu thuẫn chữ “hai tester độc lập” và làm gate bị serial. Hai gate phải chạy song song sau dev; PM review sau cả hai. |

## Gate kỹ thuật

### API/DB đối kháng độc lập

Lệnh (PG15 tmpfs riêng, không chạm DB demo):

```bash
cd backend
TEST_DATABASE_URL=postgresql://shb:shb@localhost:55432/shb_test \
  .venv/bin/pytest -q \
  tests/test_s20_tester1_shadow.py tests/test_s20_tester1_consent.py
```

Kết quả: `6 passed, 1 warning in 1.73s`. Warning duy nhất là deprecation của
`fastapi.testclient`/`httpx`, không phải failure nghiệp vụ.

Coverage quan sát được:

- seed đúng `green+approved`, `red+rejected`, `green+rejected` → aggregate
  `total=3, comparable=3, matched=2, rate=2/3`; list đúng một mismatch và đúng 7 field;
- `from` inclusive, `to` exclusive, lane, empty page; timestamp/lane/limit/cursor malformed đều
  `400` 4-field; anonymous `401`; role `user|customer` `403`; tenant B nhận zero row;
- hai row cùng `decided_at` phân trang `limit=1` không trùng/sót, đúng UUID tie-break; đổi lane hoặc
  tenant khi dùng cursor trả `400 invalid_cursor`;
- consent thiếu/false, legacy card, snapshot tamper và client bơm version/tenant/actor đều fail-closed
  và SQL xác nhận zero partial write;
- ép `consent.insert_record` nổ sau card/customer path → card vẫn pending, user/customer/consent
  đều zero; retry thành công tạo đúng một customer + một consent; submit lần hai `409`, không nhân;
- proof row lấy tenant/subject/actor từ claims, version/checksum từ canonical snapshot; DB reject
  enum/hash/tenant sai, unique trùng; direct UPDATE và DELETE đều bị trigger chặn SQLSTATE `55000`;
- static source: mỗi ledger chỉ có một insert seam được cho phép, không có app update/delete và
  `reset_demo.py` không nhắc `consent_records`.

Lần chạy đầu có hai lỗi trong chính harness tester (ký tự `+` chưa URL-encode; `null` bị hiểu là
malformed thay vì field missing). Tester sửa harness sang `params=` và omission thực, rồi rerun xanh;
không ghi hai lỗi harness thành defect production.

### Migration hai chiều trên DB sạch

Database tạm độc lập `shb_s20_tester1_migration` được tạo riêng, sau đó chạy:

```bash
DATABASE_URL=postgresql://shb:shb@localhost:55432/shb_s20_tester1_migration \
  .venv/bin/alembic upgrade head
DATABASE_URL=postgresql://shb:shb@localhost:55432/shb_s20_tester1_migration \
  .venv/bin/alembic downgrade 9f3a2b7c4d10
DATABASE_URL=postgresql://shb:shb@localhost:55432/shb_s20_tester1_migration \
  .venv/bin/alembic upgrade head
```

Kết quả cuối: revision `d4e8a1b7c203`, table `consent_records` và trigger
`trg_consent_records_append_only` cùng tồn tại. Database tạm đã được drop đúng tên sau khi lấy
evidence.

## Kết luận tạm thời

- **Dev BE: PASS targeted gate** tại snapshot này; cần rerun sau handoff/full regression mới ký cuối.
- **PM: FAIL / needs correction** vì PM-01 và PM-02; không được dùng con số historical như fresh
  baseline, và không được serial hóa hai tester độc lập.
