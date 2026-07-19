# docs/ — mục lục

> Mỗi tài liệu một việc, không trùng nhau. Cột "đọc khi" giúp chọn đúng file — người và AI
> đều dùng bảng này làm điểm vào (AI: bắt đầu từ [`../AGENTS.md`](../AGENTS.md)).

| File | Là gì | Đọc khi |
|---|---|---|
| [`problem-statement.md`](problem-statement.md) | Đề bài #132 (text) — 5 deliverable bắt buộc | Muốn biết đề đòi gì; chấm xem sản phẩm trả đủ chưa |
| [`132-SHB-agents.pdf`](132-SHB-agents.pdf) | Đề bài PDF gốc từ BTC | Cần nguyên văn |
| [`CONTRACT.md`](CONTRACT.md) | Hợp đồng API + SSE + error envelope FE↔BE — **1 nguồn sự thật về shape** | Trước khi viết/sửa endpoint, SSE event, hoặc FE client |
| [`patterns/00-INDEX.md`](patterns/00-INDEX.md) | Mục lục 5 pattern build: `claude-sdk` · `multi-agent` · `streaming-sse` · `canvas-present` · `lab-joint` | Trước khi build/sửa phần tương ứng — đọc đúng file theo task |
| [`demo-script.md`](demo-script.md) | Kịch bản demo thi ~10-13 phút, 2 cửa sổ (khách ‖ ngân hàng), kèm đường thoát hiểm | Chuẩn bị demo / muốn hiểu happy-path end-to-end |
| [`deploy.md`](deploy.md) | Deploy production: Docker compose + cloudflared → `digital.tinhdev.com`, seed snapshot, reset demo, rollback | Deploy / vận hành server |
| [`business-case.md`](business-case.md) | Khả thi kinh doanh + pilot 3 pha + trách nhiệm pháp lý | Hỏi về triển khai thực tế / giá trị nghiệp vụ |
| [`ux-design.md`](ux-design.md) | Tư duy thiết kế UX AI-native — lập luận đằng sau từng lựa chọn UI | Muốn hiểu vì sao UI bố cục như hiện tại |
| `assets/` | Ảnh chụp sản phẩm dùng cho README | — |

Tài liệu cấp repo (ngoài `docs/`):

- [`../README.md`](../README.md) — mặt tiền: sản phẩm, kiến trúc, quickstart, bản đồ repo.
- [`../AGENTS.md`](../AGENTS.md) — điểm vào cho AI agent: lệnh chuẩn, quy ước, vùng cẩn trọng.
- [`../SPEC.md`](../SPEC.md) — đặc tả sản phẩm (nguyên lý → cơ chế → rule, §14 KHÔNG-làm).
- [`../DECISIONS.md`](../DECISIONS.md) — sổ quyết định sống (human-wins).
- [`../sprints/`](../sprints/ROADMAP.md) — ROADMAP + nhật ký sprint (plan/end, số liệu thật).
