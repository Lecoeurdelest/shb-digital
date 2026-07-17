# docs/patterns/ — Thư viện pattern build SYSTEM #132

> Bộ tài liệu TỰ CHỨA đi kèm `SPEC.md`: spec nói **cái gì + vì sao**,
> patterns nói **cách build**. Đọc spec trước, mở pattern đúng chủ đề khi build tới phần đó.
> Mọi snippet là ví dụ viết cho dự án này — không port từ đâu, không cần mở repo ngoài.

## Vòng đời 1 ca — sơ đồ neo (tên event/bảng/tool thật)

```
USER chat ──POST /chat──▶ hàng đợi phòng ──wake──▶ MAIN (SDK resume, 1 lượt/phòng)
                                                    │ orch_dispatch(role,…) ⟳ idempotent
                                                    ▼
                                          SUB <role> chạy nền (client tươi)
                                          │ gọi tool banking_* (audit → tool_calls)
                                          │ present(card) → bảng cards + SSE `card`
                                          │ tool GATED → phanh 4 bước (§4.4):
                                          │   biên nhận? → trả cũ · approved? → claim atomic
                                          │   → chạy thật · pending? → báo chờ · chưa có?
                                          │   → phiếu pending + card + `approval.pending`
                                          ▼
                    MỌI kết cục (done/failed/timeout/hủy) → đúng 1 event task_done
                                                    │
USER ◀──SSE chat.delta── MAIN thức, đọc bảng việc, tự quyết: đợi / giao tiếp / tổng hợp
ADMIN ──decide phiếu──▶ event approval_decided ──wake──▶ MAIN giao lại → sub gọi lại tool
                                                          → wrapper khớp phiếu → biên nhận
```

## Bản đồ file

| File | Chủ đề (kiêm CHỦ NHÀ của) | Build phần nào của spec |
|---|---|---|
| `claude-sdk.md` | thuần SDK: lifecycle close-on-done, options, resume disk, MCP in-process, ranh interrupt/cancel, cost, đa provider | §3 (main bền/sub tươi), §8 (session), §12 (stack) |
| `multi-agent.md` | **chủ nhà CƠ CHẾ**: event wake/sleep, slot + hàng đợi (không nuốt lệnh người), dispatch idempotent, invariant không-chết-im-lặng, đường hủy per-agent, approval resume | §4 (4 cơ chế lõi), §5 (tool điều phối) |
| `streaming-sse.md` | SSE 1-worker in-process: contract event (payload `phieu`), seq/dedup chat.delta, FE hook, refetch-on-reconnect, mapping emit theo 4 nhánh wrapper | §9 (SSE), §8 (DB = kho render) |
| `canvas-present.md` | **chủ nhà MẶT CARD**: present 6 loại hiển thị, card approval chỉ-vỏ-sinh, id vỏ-inject, citation theo tên tool, persist reload | §6 (canvas), N5 |
| `lab-joint.md` | **chủ nhà CONTRACT + CODE MOUNT**: 4 interface, mount_role + schema builder (bản duy nhất), wrapper gated 4 bước + payload_hash, stub, seed DB, audit ContextVar | §7 (contract lab), §4.4 (code phanh), N3 |

## Tra nhanh: khái niệm → chủ nhà

| Khái niệm | Định nghĩa đầy đủ ở |
|---|---|
| Phanh 4 bước · payload_hash · biên nhận · vòng đời phiếu | SPEC §4.4 (cơ chế) · `lab-joint.md` §2.1 (code) |
| Slot + hàng đợi phòng · dedup không-nuốt-lệnh-người | `multi-agent.md` §2 |
| Dispatch fire-and-forget + idempotent (conv, role) | `multi-agent.md` §3–§4 |
| Invariant "mọi kết cục sub → đúng 1 event" · `_report` | `multi-agent.md` §5–§6 |
| Hủy per-agent · boot dọn cờ mồ côi | `multi-agent.md` §7 |
| Approval resume (phiếu decided → wake main) | `multi-agent.md` §8 |
| mount_role · schema_to_input · bad_param · stub role | `lab-joint.md` §2–§4 |
| calc + present (server `common`) · audit ContextVar | `lab-joint.md` §5, §7 |
| present · 2 loại card · 7 card types · citation source | `canvas-present.md` |
| SDK lifecycle · resume disk · interrupt/cancel · cost · providers | `claude-sdk.md` |
| SSE bus · envelope event · seq per-turn · emit mapping | `streaming-sse.md` |
| Envelope error 4-field · success = resource trần | SPEC §5 + §11 |
| Bảng anti-pattern (danh mục săn lỗi) | SPEC §15 |

Chuẩn chất lượng tool (envelope, schema, idempotent, honest, affordance, gate): SPEC §5 + §15
+ `lab-joint.md` — tự chứa trong repo. Design/mock: `design/` — chỉ tham khảo (D-13/D-14).
