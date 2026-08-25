# docs/ — mục lục

> Mỗi tài liệu một việc, không trùng nhau. Cột "đọc khi" giúp chọn đúng file — người và AI
> đều dùng bảng này làm điểm vào (AI: bắt đầu từ [`../AGENTS.md`](../AGENTS.md)).

| File | Là gì | Đọc khi |
|---|---|---|
| [`problem-statement.md`](problem-statement.md) | Đề bài #132 (text) — 5 deliverable bắt buộc | Muốn biết đề đòi gì; chấm xem sản phẩm trả đủ chưa |
| [`132-SHB-agents.pdf`](132-SHB-agents.pdf) | Đề bài PDF gốc từ BTC | Cần nguyên văn |
| [`CONTRACT.md`](CONTRACT.md) | Hợp đồng API + SSE + error envelope FE↔BE — **1 nguồn sự thật về shape** | Trước khi viết/sửa endpoint, SSE event, hoặc FE client |
| [`EMBED_SDK.md`](EMBED_SDK.md) | Tích hợp headless core + SDK vào SAHA/website/portal RM/LOS; auth, CORS, Web Component và non-claims | Khi nhúng sản phẩm vào kênh ngân hàng hoặc phát hành SDK |
| [`patterns/00-INDEX.md`](patterns/00-INDEX.md) | Mục lục 5 pattern build: `claude-sdk` · `multi-agent` · `streaming-sse` · `canvas-present` · `lab-joint` | Trước khi build/sửa phần tương ứng — đọc đúng file theo task |
| [`demo-script.md`](demo-script.md) | Kịch bản demo thi ~10-13 phút, 2 cửa sổ (khách ‖ ngân hàng), kèm đường thoát hiểm | Chuẩn bị demo / muốn hiểu happy-path end-to-end |
| [`deploy.md`](deploy.md) | Deploy production: Docker compose + cloudflared → `digital.tinhdev.com`, seed snapshot, reset demo, rollback | Deploy / vận hành server |
| [`db-erd-live.md`](db-erd-live.md) | DDL snapshot + ảnh ERD overview/full sinh từ live catalog tại `e6f9b2c4d105` | Cần schema SQL hoặc sơ đồ DB chính xác để review/tra cứu |
| [`db-architecture-v2.md`](db-architecture-v2.md) | Kiến trúc datastore + ERD as-built tại Alembic head mới, issue legacy và lộ trình scale | Đánh giá DB, thêm loại DB, migrate hoặc chuẩn bị scale ngang |
| [`db-erd-review.md`](db-erd-review.md) | Baseline ERD trước migration D-76 | Cần đối chiếu schema cũ với as-built |
| [`db-erd-operational-target.md`](db-erd-operational-target.md) | ERD đích dài hạn còn lại ngoài phần đã migrate | Lập backlog policy/history/typed data và retention |
| [`business-case.md`](business-case.md) | Khả thi kinh doanh + pilot 3 pha + trách nhiệm pháp lý | Hỏi về triển khai thực tế / giá trị nghiệp vụ |
| [`methodology/`](methodology/README.md) | **Bộ phương pháp luận** — [`README.md`](methodology/README.md) vì sao chọn từng công nghệ (8 mục) · [`skill-training.md`](methodology/skill-training.md) huấn luyện chuyên gia AI như train model · [`loop-engineering.md`](methodology/loop-engineering.md) đội AI build có phanh · [`ux-design.md`](methodology/ux-design.md) tư duy thiết kế UX AI-native | Hỏi "vì sao làm thế này" — kiến trúc, công nghệ, quy trình build, UX |
| [`../bench/`](../bench/README.md) | Bench single-agent vs hệ: 15 case (đơn-phòng · liên-phòng · bẫy · phanh) + 2 runner + grader | Muốn số liệu deliverable #5 / chạy lại bench |
| `assets/` | Ảnh chụp sản phẩm dùng cho README | — |

Tài liệu cấp repo (ngoài `docs/`):

- [`../README.md`](../README.md) — mặt tiền: sản phẩm, kiến trúc, quickstart, bản đồ repo.
- [`../AGENTS.md`](../AGENTS.md) — điểm vào cho AI agent: lệnh chuẩn, quy ước, vùng cẩn trọng.
- [`../SPEC.md`](../SPEC.md) — đặc tả sản phẩm (nguyên lý → cơ chế → rule, §14 KHÔNG-làm).
- [`../DECISIONS.md`](../DECISIONS.md) — sổ quyết định sống (human-wins).
- [`../sprints/`](../sprints/ROADMAP.md) — ROADMAP + nhật ký sprint (plan/end, số liệu thật).
- [`../bench/REPORT.md`](../bench/REPORT.md) — benchmark single vs đội (15 case, số liệu + đánh giá)
