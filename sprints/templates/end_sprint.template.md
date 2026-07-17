# Sprint {{X}} — End

<!-- LUẬT SỐNG CÒN (đọc trước khi viết):
     Đây là RECEIPT, không phải bản kể công. Mỗi task done phải kèm BẰNG CHỨNG verify
     chạy độc lập được — lệnh ĐÃ CHẠY + output count, không phải "đã làm xong". "Đã làm"
     ≠ "đã đúng". 3 gate tick-box PHẢI tick trước khi commit; ô nào chưa tick = commit bị chặn.
     Findings ngoài scope → flag cho sprint sau, KHÔNG tự làm trong sprint này. -->

**Theme:** {{khớp plan}} · **Commit:** {{<hash> — điền sau khi commit}}

## Kết quả từng task

### {{<task-id>}} — {{done / fail}}
- **Bằng chứng:** {{lệnh đã chạy + output count — vd: "`<test-cmd>` → N passed, 0 failed" / "`curl GET /<resource>` → 200, M field non-null"}}
- **Deviation:** {{lệch gì so với dispatch, hoặc none}}

### {{<task-id>}} — {{done / fail}}
- **Bằng chứng:** {{...}}
- **Deviation:** {{...}}

## 3 Quality Gates

<!-- Danh sách ô ĐẦY ĐỦ và chuẩn = CLAUDE.md §6a (load-bearing: bất kỳ ô nào unchecked = commit
     blocked). Dưới đây chỉ là chỗ tick receipt tóm tắt — lệch ô nào, lấy §6a làm chuẩn. -->

- [ ] **Gate 1 — API** {{n/a nếu không chạm API}}: schema · integration test endpoint mới · test cũ pass · response format · REST status
- [ ] **Gate 2 — Function**: unit test assert observable behavior · test cũ pass · edge (empty/None/max/malformed) · error path · typecheck clean · FE Chrome self-verify nếu chạm UI
- [ ] **Gate 3 — Sprint**: end_sprint có count re-run độc lập · architect đọc full function (không chỉ diff) · tester 100% · test count ≥ baseline · findings ngoài scope đã ghi

## Test counts

- **Baseline (đầu sprint):** {{<count>}}
- **Sau sprint:** {{<count> — phải ≥ baseline}}

## Findings ngoài scope (flag cho sprint sau)

- {{phát hiện lúc build nhưng KHÔNG thuộc sprint này — mô tả + gợi ý task. "none" nếu không.}}

## Ngoại lệ đã ký (nếu có)

<!-- Chỉ điền khi có anomaly hợp lệ không fix được trong sprint (flaky-by-infra, case mơ hồ thật). -->
- {{item · lý do · <YYYY-MM-DD> · signer · điều kiện re-review}} {{— hoặc "none"}}
