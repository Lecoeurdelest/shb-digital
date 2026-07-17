# shb-digital

**Đề 132 — Digital Expert Guild**: hệ multi-agent AI cho vận hành ngân hàng SHB.
Vietnam AI Innovation Challenge 2026 / Hack CX Together 2026.

## Đề bài

Xem [`docs/problem-statement.md`](docs/problem-statement.md) (PDF gốc: [`docs/132-SHB-agents.pdf`](docs/132-SHB-agents.pdf)).

Tóm tắt: một team các "chuyên gia số" (Credit · Legal · Products · Operations), 1 MAIN điều
phối + các SUB chuyên gia — tự chia việc, dùng tool (tính bằng tool, không nhẩm), phối hợp,
**thực thi hành động có phanh** (việc nhạy cảm dừng chờ người duyệt). Mọi bước có vết, mọi con
số có nguồn. Không chatbot trả lời — là đội-làm-việc có giám sát, có phanh, có bằng chứng.

## Tài liệu

- **`SPEC.md`** — sản phẩm là gì (nguyên lý → kiến trúc → cơ chế → contract → rule).
- **`docs/patterns/`** — cách build từng phần (5 pattern doc + `00-INDEX.md`).
- **`DECISIONS.md`** — sổ quyết định ngoài-dự-tính (human-wins, đảo được).
- **`CLAUDE.md`** — luật vận hành đội build (§0 kim chỉ nam: Thử · Sai · Sửa).
- **`design/`** — mock look-and-feel (tham khảo, không phải nguồn scope — D-13/D-14).

## Trạng thái

Đã chốt spec v2.0 + patterns + design. Chuẩn bị vào loop build (build-order 6 bước — SPEC §16).
