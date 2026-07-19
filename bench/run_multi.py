"""run_multi.py — chạy 1 bench case qua HỆ THẬT (API :8000, đội 4 chuyên gia + MAIN điều phối).

Luồng: login (bank RM 'user' mặc định; disclosure-persona case dùng account customer) → POST
/api/conversations (provider=claude-cli, model=sonnet) → POST .../chat → POLL GET
/api/conversations/{id} tới khi ĐỘI THẬT XONG (không chỉ conversation.status=idle 1 lần — main
có thể flip idle→running→idle nhiều đợt khi dispatch tuần tự D-52; điều kiện dừng đúng: status=idle
VÀ không còn task queued/running, ỔN ĐỊNH qua ≥2 lần poll liên tiếp — pattern mượn run_epoch.py LAB
§wait_all, xem docstring _poll_until_done) → thu messages + tasks + cards + tool_calls audit (GET
/api/audit filter conv_id, cần account admin — 'user' KHÔNG đủ quyền audit, xem _fetch_audit) → ghi
bench/responses/multi/<case>.md.

CLI: python3 run_multi.py --case CR-01-floor | --all
Sub-model override: XEM README §Caveat sub_model — server LIVE đọc providers.yaml của CHECKOUT nó
chạy (main checkout /backend, KHÔNG PHẢI worktree này) — script này KHÔNG tự sửa file đó (ranh:
không sửa backend/ngoài phạm vi worktree). Mặc định sub vẫn chạy haiku (giá thật production) trừ
khi vận hành viên đã tự chỉnh providers.yaml của checkout đang chạy TRƯỚC khi gọi --all (Phase 2).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

BASE = "http://localhost:8000"
BENCH_DIR = Path(__file__).resolve().parent
CASES_DIR = BENCH_DIR / "cases"
OUT_DIR = BENCH_DIR / "responses" / "multi"

# account mặc định NGÂN HÀNG (RM) — thấy mọi ca, đủ quyền audit (admin cần cho GET /api/audit).
# case disclosure-khách cần persona KHÁCH riêng — xem CUSTOMER_CASES.
DEFAULT_LOGIN = ("admin", "admin")  # admin: vừa require_admin (audit) vừa require_user (chat) — 1 account đủ cả 2
CUSTOMER_LOGIN = ("c019", "c019")  # persona khách có owner_id thật (C019) cho case cần role=customer
CUSTOMER_CASES = {"TRAP-03-disclosure-khach"}

POLL_INTERVAL_S = 3
POLL_BUDGET_S = 600  # 10 phút/case — đủ cho chuỗi tuần tự D-52 (4 role) + haiku sub chậm nhất


def _req(method: str, path: str, token: str | None = None, body: dict | None = None, timeout: int = 30) -> Any:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw.decode(errors="replace")}
        raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {json.dumps(payload, ensure_ascii=False)}") from e


def login(username: str, password: str) -> str:
    result = _req("POST", "/api/auth/login", body={"username": username, "password": password})
    return result["token"]


def create_conversation(token: str, title: str) -> str:
    conv = _req("POST", "/api/conversations", token=token, body={"title": title, "provider": "claude-cli", "model": "sonnet"})
    return conv["id"]


def send_chat(token: str, conv_id: str, content: str) -> None:
    _req("POST", f"/api/conversations/{conv_id}/chat", token=token, body={"content": content})


def get_conversation(token: str, conv_id: str) -> dict[str, Any]:
    return _req("GET", f"/api/conversations/{conv_id}", token=token)


def _fetch_audit(token: str, conv_id: str) -> list[dict[str, Any]]:
    """GET /api/audit filter conv_id (admin-only, T4-1). Login KHÔNG phải admin → trả [] +
    cảnh báo (bench vẫn ghi response, chỉ thiếu audit chi tiết tool-call — không chặn harness)."""
    try:
        return _req("GET", f"/api/audit?conv_id={conv_id}&limit=500", token=token)
    except RuntimeError as e:
        print(f"  [WARN] audit fetch lỗi (cần admin — tiếp tục không có audit): {e}", file=sys.stderr)
        return []


def _team_settled(conv: dict[str, Any]) -> bool:
    """Đội đã DỪNG THẬT (không chỉ 1 lần idle giữa 2 đợt dispatch tuần tự D-52).
    conversation.status idle/waiting_approval/failed (không phải 'running') VÀ mọi task
    KHÔNG còn queued/running. Nguồn: registry.is_busy + tasks status pattern (conversations.py
    _conv_is_running dùng chính 2 tiêu chí này — bench soi field trần qua REST, không registry
    in-process được vì bench là process ngoài)."""
    status = conv["conversation"].get("status")
    if status == "running":
        return False
    tasks = conv.get("tasks") or []
    if any(t.get("status") in ("queued", "running") for t in tasks):
        return False
    return True


def poll_until_done(token: str, conv_id: str, budget_s: int = POLL_BUDGET_S) -> dict[str, Any]:
    """Poll tới khi đội THẬT xong — ỔN ĐỊNH qua 2 lần đọc liên tiếp (advisor: main flip
    idle→running→idle nhiều đợt cho chuỗi tuần tự D-52; 1 lần idle có thể là khoảng nghỉ giữa
    dispatch Credit xong / trước khi giao Legal). approval_required (brake case) → conversation.
    status='waiting_approval' cũng tính SETTLED (đội đã dừng đúng ở phiếu chờ duyệt — không phải
    lỗi harness).

    GUARD race-khởi-động (advisor): POST /chat trả 202 NGAY rồi mới spawn lượt main nền
    (asyncio.ensure_future — conversations.py) — cửa sổ ngắn (thường <1s nhưng KHÔNG đảm bảo) giữa
    202 và conversation.status thật sự chuyển 'running' + task đầu tiên xuất hiện. 2 lần poll liên
    tiếp RƠI ĐÚNG vào cửa sổ đó (conv vẫn status cũ 'idle' từ trước khi gửi, 0 task) sẽ SETTLE GIẢ
    ngay lập tức — im lặng trả kết quả rỗng cho `--all` không người trông. Chặn: PHẢI thấy ít nhất
    1 lần status='running' HOẶC có task xuất hiện trước khi chấp nhận verdict settled."""
    t0 = time.time()
    stable_count = 0
    seen_started = False
    last: dict[str, Any] | None = None
    while time.time() - t0 < budget_s:
        conv = get_conversation(token, conv_id)
        last = conv
        if conv["conversation"].get("status") == "running" or conv.get("tasks"):
            seen_started = True
        if seen_started and _team_settled(conv):
            stable_count += 1
            if stable_count >= 2:
                return conv
        else:
            stable_count = 0
        time.sleep(POLL_INTERVAL_S)
    print(f"  [WARN] poll budget {budget_s}s hết — trả trạng thái CUỐI CÙNG đọc được (có thể chưa xong)", file=sys.stderr)
    return last or {}


def _load_case(case_id: str) -> dict[str, Any]:
    path = CASES_DIR / f"{case_id}.yaml"
    if not path.exists():
        matches = list(CASES_DIR.glob(f"{case_id}*.yaml"))
        if len(matches) == 1:
            path = matches[0]
        else:
            raise FileNotFoundError(f"case '{case_id}' không tìm thấy trong {CASES_DIR}")
    return yaml.safe_load(path.read_text())


def run_case(case_id: str) -> Path:
    case = _load_case(case_id)
    real_id = case["id"]
    prompt = case["prompt"].strip()
    use_customer = real_id in CUSTOMER_CASES
    username, password = CUSTOMER_LOGIN if use_customer else DEFAULT_LOGIN
    print(f"[{real_id}] login={username} (persona={'khách' if use_customer else 'ngân hàng-admin'})")
    token = login(username, password)
    # audit cần quyền admin (T4-1 require_admin) — persona khách KHÔNG có quyền audit; dùng token
    # admin RIÊNG để fetch audit sau khi case chạy xong (không ảnh hưởng persona lúc chat).
    admin_token = token if not use_customer else login(*DEFAULT_LOGIN)

    conv_id = create_conversation(token, title=f"BENCH {real_id}")
    print(f"[{real_id}] conv={conv_id} — gửi prompt...")
    t_start = time.time()
    send_chat(token, conv_id, prompt)

    conv = poll_until_done(token, conv_id)
    elapsed = round(time.time() - t_start, 1)
    audit = _fetch_audit(admin_token, conv_id)

    out_path = OUT_DIR / f"{real_id}.md"
    _write_response(out_path, case, conv, audit, elapsed, persona=username)
    print(f"[{real_id}] DONE — {elapsed}s — {len(conv.get('tasks', []))} task(s) — ghi {out_path}")
    return out_path


def _final_answer(conv: dict[str, Any]) -> str:
    # store.py Message field = 'sender' (user/assistant/system), KHÔNG 'role' (đó là field Task).
    msgs = [m for m in (conv.get("messages") or []) if m.get("sender") in ("assistant", "system")]
    return msgs[-1]["content"] if msgs else "(không có message assistant/system)"


def _write_response(out_path: Path, case: dict[str, Any], conv: dict[str, Any], audit: list[dict], elapsed_s: float, persona: str) -> None:
    conversation = conv.get("conversation") or {}
    tasks = conv.get("tasks") or []
    cards = conv.get("cards") or []
    lines: list[str] = []
    lines.append(f"# {case['id']} — run_multi (hệ THẬT, đội {len(tasks)} task)")
    lines.append("")
    lines.append(f"- conv_id: `{conversation.get('id')}`")
    lines.append(f"- login persona: `{persona}`")
    lines.append(f"- provider/model: `{conversation.get('provider')}` / `{conversation.get('model')}`")
    lines.append(f"- conversation.status cuối: `{conversation.get('status')}`")
    lines.append(f"- thời gian tới khi settled: {elapsed_s}s")
    lines.append("")
    lines.append("## Prompt")
    lines.append("")
    lines.append(f"> {case['prompt'].strip()}")
    lines.append("")
    lines.append("## Câu trả lời cuối")
    lines.append("")
    lines.append(_final_answer(conv))
    lines.append("")
    lines.append("## Bảng việc (tasks — role/status/cost)")
    lines.append("")
    if tasks:
        lines.append("| role | status | started | ended | cost |")
        lines.append("|---|---|---|---|---|")
        for t in tasks:
            cost = json.dumps(t.get("cost"), ensure_ascii=False) if t.get("cost") else "—"
            lines.append(f"| {t.get('role')} | {t.get('status')} | {t.get('started_at') or '—'} | {t.get('ended_at') or '—'} | {cost} |")
    else:
        lines.append("(không có task nào — MAIN có thể đã trả lời trực tiếp không dispatch)")
    lines.append("")
    lines.append("## Cards (canvas)")
    lines.append("")
    if cards:
        for c in cards:
            # _card_to_dict (store.py) spread data lên TOP-LEVEL (title/items/sources...) — KHÔNG
            # có key 'data' lồng trong response REST (khác raw DB row).
            preview = {k: v for k, v in c.items() if k not in ("id", "conv_id", "task_id", "ts")}
            lines.append(f"- **{c.get('type')}** — {json.dumps(preview, ensure_ascii=False)[:600]}")
    else:
        lines.append("(không có card nào)")
    lines.append("")
    lines.append(f"## Tool-call audit ({len(audit)} dòng — GET /api/audit, cần admin)")
    lines.append("")
    if audit:
        lines.append("| actor | tool | ts |")
        lines.append("|---|---|---|")
        for row in audit[:100]:
            lines.append(f"| {row.get('actor')} | {row.get('tool')} | {row.get('ts')} |")
        if len(audit) > 100:
            lines.append(f"... (+{len(audit)-100} dòng nữa, cắt bớt)")
    else:
        lines.append("(không có audit row — hoặc account không đủ quyền admin)")
    lines.append("")
    lines.append("## Messages đầy đủ (transcript)")
    lines.append("")
    for m in conv.get("messages") or []:
        lines.append(f"**{m.get('sender')}**: {m.get('content')}")
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Chạy bench case qua hệ THẬT (API :8000)")
    ap.add_argument("--case", help="case id (vd CR-01-floor) hoặc filename không .yaml")
    ap.add_argument("--all", action="store_true", help="chạy TẤT CẢ case trong bench/cases/")
    args = ap.parse_args()

    if not args.case and not args.all:
        ap.error("cần --case <id> hoặc --all")

    if args.all:
        case_files = sorted(CASES_DIR.glob("*.yaml"))
        for f in case_files:
            try:
                run_case(f.stem)
            except Exception as e:  # noqa: BLE001 — 1 case lỗi không chặn cả batch
                print(f"[{f.stem}] LỖI: {e}", file=sys.stderr)
    else:
        run_case(args.case)


if __name__ == "__main__":
    main()
