"""Orchestrator spine (T1-2) — build lại cơ chế Claude Code cho ngân hàng.

Main = phiên SDK bền/phòng (resume disk). orch_dispatch = spawn sub nền.
Sub = client tươi xong-trả-về. Event = sub xong báo main (1 lượt/phòng).
VỎ đưa thông tin (kết quả + bảng việc); NÃO quyết đợi/tổng hợp (N1).

Module (tách file ≤400 LOC):
- registry.py    — state in-process (slot/queue/registry sống/sub tasks/main clients)
- dispatch.py    — orch_dispatch fire-and-forget + create_task_guarded idempotent
- sub_runner.py  — _run_sub + _report (invariant 1-điểm-hội-tụ)
- room.py        — try_acquire/release/handle_room_event (wake→work→sleep)
- main_session.py— SDK main lifecycle (resume + close-on-done)
"""
