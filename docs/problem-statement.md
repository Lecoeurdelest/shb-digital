# Đề bài 132 — Digital Expert Agents

> **Vietnam AI Innovation Challenge 2026 — Hack CX Together 2026**
> **A Team of AI Specialists for Banking Operations**
> Nguồn: `battle/de-archive/attachments/132-SHB-agents.pdf`

---

## Tóm tắt

Một hệ **multi-agent AI** trong đó mỗi agent đóng vai một chuyên gia số (digital expert) cho một domain nghiệp vụ ngân hàng cụ thể — như tín dụng (credit), pháp lý & tuân thủ (legal/compliance), sản phẩm (products), hoặc vận hành (operations).

Các agent phải **tự động lập kế hoạch** (plan) tác vụ, **dùng tool**, truy xuất tri thức nội bộ qua **RAG**, **cộng tác** với nhau, và **thực thi hành động** trong hệ thống vận hành của SHB — thay vì chỉ sinh text trả lời.

---

## Thông tin đề (bảng gốc)

| Trường | Nội dung |
|---|---|
| **Topic** | Digital Expert Agents – A Team of AI Specialists for Banking Operations |
| **Brief Description** | Hệ multi-agent AI, mỗi agent là chuyên gia của một domain ngân hàng (credit, legal/compliance, products, operations). Agent tự plan tác vụ, dùng tool, retrieve tri thức nội bộ qua RAG, cộng tác với nhau, và thực thi hành động trong hệ thống vận hành của SHB — không chỉ sinh text. |
| **Suggested Technologies** | GenAI / LLM reasoning engine (GPT-4 hoặc Claude); agentic framework (LangGraph, CrewAI, hoặc AutoGen); tool use & function calling; domain-specific RAG cho từng agent; planner–executor orchestration & routing; memory & state management; multi-agent communication protocols (bao gồm **MCP** khi phù hợp); **FastAPI** backend; **React-based** orchestration interface. |
| **Key Deliverables** | Xem mục dưới. |
| **Benefits to the Bank** | Xem mục dưới. |
| **Why This Problem Matters** | Xem mục dưới. |

---

## Key Deliverables (bắt buộc nộp)

1. **Working demo** với ít nhất **2–3 chuyên gia số** (ví dụ: Credit, Legal/Compliance, Operations) **cộng tác trên một request phức tạp**.
2. **Cơ chế orchestration**: một **planner agent** phân rã công việc và giao task cho các **executor agent** chuyên biệt.
3. **Tool use thực tế**: agent gọi API, query data, hoặc thực hiện **hành động cụ thể** — không chỉ trả về text.
4. **Dashboard** hiển thị **agent traces**, **task status**, **decisions**, và **collaboration flows**.
5. **So sánh hiệu năng** giữa **single-agent chatbot** và hệ **action-oriented AI agents**.

---

## Benefits to the Bank

- Mở rộng GenAI từ trả lời câu hỏi → **thực thi công việc**, tăng giá trị vận hành.
- Một hệ agent phối hợp **đại diện cho nhiều phòng ban chuyên môn**, tăng tốc các request liên phòng ban (cross-functional).
- Giảm phụ thuộc vào từng chuyên gia cá nhân trong khi vẫn **giữ workflow & control theo domain**.
- Đặt nền kỹ thuật cho **tự động hóa quy trình ngân hàng end-to-end** trong tương lai.
- Tạo lợi thế cạnh tranh khi ngành ngân hàng dịch chuyển từ chatbot đơn giản → AI agent hành động.

---

## Why This Problem Matters

Các use case AI hiện tại như RAG và anomaly detection thường vẫn chỉ tập trung vào **hỏi–đáp** hoặc phân tích. Đến 2026, xu hướng công nghệ ngày càng nghiêng về **hệ agentic** có thể plan, phối hợp, dùng tool, và hành động.

Hack CX Together 2026 vì vậy cần một thử thách **kết hợp năng lực foundation-model với kiến trúc multi-agent rõ ràng**, khám phá ứng dụng SHB thực tế **vượt ra ngoài RAG và chatbot truyền thống**.

---

## Suggested Technologies (chi tiết)

- **Reasoning engine**: GPT-4 hoặc Claude.
- **Agentic framework**: LangGraph / CrewAI / AutoGen.
- **Tool use & function calling**.
- **Domain-specific RAG** cho từng agent.
- **Planner–executor orchestration & routing**.
- **Memory & state management**.
- **Multi-agent communication protocols**, bao gồm **MCP** khi phù hợp.
- **Backend**: FastAPI.
- **Frontend**: React-based orchestration interface.
