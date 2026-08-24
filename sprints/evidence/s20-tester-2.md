# Sprint 20 — Evidence Tester 2 (independent gate)

**Ngày chạy:** 2026-08-24
**Vai trò:** Tester 2 — kiểm thử độc lập implementation và kiểm tra ngược PM
**DB test:** `postgresql://shb:***@localhost:55432/shb_test` (PostgreSQL 15, Alembic head `d4e8a1b7c203`)

## Kết luận

- **Implementation: PASS.** Không phát hiện lỗi chặn Sprint 20. Full suite đạt **613 BE + 336 FE = 949 pass, 17 skip, 0 fail**, cao hơn baseline kế hoạch `807 pass + 17 skip`; ruff, format check, TypeScript, build và diff check sạch.
- **PM process/traceability: FAIL.** Kickoff đã dispatch khi chưa chạy lại baseline tươi; đồng thời dependency `T20-6 -> T20-5` mâu thuẫn với yêu cầu hai tester kiểm tra độc lập/song song. Hai lỗi quy trình này không làm sai implementation nhưng phải được PM sửa/ghi nhận trước khi đóng sprint.
- **Pilot dữ liệu thật: NO-GO.** Evidence này chỉ xác nhận móng kỹ thuật consent và shadow-match. Theo D-80, nó không phải DPIA và không phải tuyên bố tuân thủ; vẫn cần bank/legal/data-protection phê duyệt trước pilot dữ liệu thật.

## 1. Audit PM độc lập

| Hạng mục | Kết quả | Bằng chứng |
|---|---|---|
| PM-01 — baseline trước dispatch | **FAIL** | `plan_sprint_20.md` yêu cầu đối chiếu baseline lúc kickoff, nhưng phần Kickoff ghi rõ chưa chạy fresh full suite trước khi dispatch. |
| PM-02 — tính độc lập của hai tester | **FAIL** | `T20-6` khai dependency vào `T20-5`, trái với mô tả “hai tester gate độc lập” và yêu cầu user cho hai tester kiểm tra chéo PM. Thực tế Tester 2 đã chạy song song theo chỉ đạo của root, nhưng source-of-truth vẫn tự mâu thuẫn. |
| Phạm vi D-80 / non-DPIA | **PASS** | Plan, CURRENT và ROADMAP đều nói rõ đây chỉ là consent foundation; pilot thật vẫn NO-GO cho đến khi có DPIA/đánh giá tác động và bank sign-off. |
| Roster | **PASS, có note** | Thực tế đủ 1 PM, 2 BA, 2 Dev, 2 Tester. Plan dùng role/task ownership nhưng chưa có bảng roster định danh tập trung; nên bổ sung để truy vết dễ hơn. |
| S23 không bị dispatch nhầm | **PASS** | S23 vẫn ở trạng thái draft; Sprint 20 là source-of-truth đang thi hành. |

## 2. Frontend — unit/integration và quality gates

| Lệnh | Kết quả |
|---|---|
| `npm run test -- src/components/stats/ShadowMatchView.test.tsx src/components/ControlTower.test.tsx src/App.deepLink.test.tsx src/components/cards/FormCard.test.tsx src/api/client.test.ts` | **47 pass / 5 files** |
| `npm run test` | **336 pass / 45 files** |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS**, còn 6 warning `react(only-export-components)` ở file có sẵn `controlTowerAudit.tsx` |
| `npm run build` | **PASS**, chỉ có warning chunk Vite >500 KB |

Các assertion máy-kiểm đã xác nhận:

- `2/3` hiển thị `66,7%`, breakdown theo lane/ngày đúng.
- Click mismatch tạo đúng deep-link `?tab=approvals&approval=<id>` và hàng phiếu đích được focus/highlight.
- Vai RM/customer không render tab và **không fetch** cả aggregate lẫn mismatch endpoint.
- API client gửi đúng filter/cursor, không gửi hoặc cho phép override `tenant_id`.
- Checkbox consent mặc định chưa tick, nút submit disabled; request chỉ gửi `consent_granted: true` khi người dùng chủ động tick.
- Snapshot consent legacy/malformed fail-closed; state checkbox được giữ khi component remount.

## 3. Live API, SQL và browser — stack thật

### Shadow-match

Seed độc lập trên DB test đúng 3 ca comparable tenant mặc định:

- green + approved → match;
- red + rejected → match;
- green + rejected → mismatch;
- thêm 1 mismatch ở tenant B để kiểm tra cách ly tenant.

Kết quả HTTP/SQL:

- Aggregate tenant mặc định: `total=3`, `comparable=3`, `matched=2`, `match_rate=0.6666…`; green `1/2`, red `1/1`; breakdown ngày `2/3`.
- Mismatch với `from/to/lane=green`: đúng 1 record, đúng approval đã seed, `next_cursor=null`.
- Thêm query `tenant_id=<tenant-B>` vẫn trả tenant từ JWT (`3/2`), chứng minh query không override tenant scope.
- Anonymous → `401` chuẩn lỗi 4-field; RM → `403` chuẩn lỗi 4-field.
- `from` không có timezone → `400 bad_shadow_filter`, chuẩn lỗi 4-field.

Browser Selenium chạy trên frontend + backend thật:

- login admin, mở Tower → Đối chiếu shadow, thấy `66,7%`;
- click đúng dòng mismatch;
- URL chứa đúng approval và hàng phiếu đích có class focus `ct__appr-wrap--focused`.

Bằng chứng ảnh:

- [Dashboard shadow-match 66,7%](gate-s20-shadow-tester2.png)
- [Deep-link mở và highlight đúng phiếu](gate-s20-deeplink-highlight-tester2.png)

### Consent atomicity

Script ASGI + SQL độc lập chạy form API thật (chỉ mock `_wake_main` để không gọi model ngoài):

```text
MISSING 400 consent_required owner None card pending records 0
GRANTED 200 owner_linked True card submitted records 1 version v1 sha_match True
REPEAT 409 form_already_submitted records 1
```

Điều này xác nhận thiếu consent không tạo hồ sơ/record, có consent thì hồ sơ và record cùng commit với `wording_version=v1` + đúng SHA wording, submit lặp không ghi thêm record.

Test forced failure giữa transaction:

```text
tests/test_consent_s20.py::test_consent_insert_failure_rolls_back_card_customer_and_user PASSED
```

## 4. Backend regression và gate tổng

| Lệnh | Kết quả |
|---|---|
| `TEST_DATABASE_URL=... uv run pytest` | **613 pass, 17 skip, 0 fail** |
| Focused S18/S19: gated receipt/replay + `test_shadow_reviews.py` + `test_notify_channels.py` | **16 pass** |
| `uv run ruff check .` | **All checks passed** |
| `uv run ruff format --check .` | **176 files already formatted** |
| `git diff --check` | **PASS** |

Focused regressions bao phủ receipt/no-double, shadow ledger append path, replay receipt, notification allowlist/post-commit và no-replay.

## 5. Giới hạn và nợ môi trường

- Lần full BE đầu tiên trên môi trường tạo bằng `uv sync` đạt `612 pass + 17 skip` nhưng fail test scale retrieval vì `pyvi` nằm trong optional dependency group `embed`, trong khi test không skip khi dependency vắng. Cài `pyvi==0.1.1` **chỉ vào test venv, không sửa repo**, rồi focused test và full rerun đều PASS (`613 + 17`). Đây là nợ reproducibility có sẵn, không phải regression Sprint 20; nên đánh dấu dependency hoặc skip test đúng điều kiện.
- Gate live dùng seed ledger xác định để kiểm chứng chính xác `2/3` và tenant isolation, thay vì gọi ba luồng model-driven disburse không ổn định. Lifecycle ghi shadow/replay được kiểm riêng bằng test backend thật và full suite.
- Warning lint/chunk nêu trên là non-blocking và không phát sinh từ phạm vi Sprint 20.

## Sign-off Tester 2

- **Implementation Sprint 20:** PASS.
- **PM/process Sprint 20:** FAIL cho đến khi xử lý PM-01 và PM-02 trong source-of-truth/history.
- **Pilot dữ liệu thật:** NO-GO theo D-80.
