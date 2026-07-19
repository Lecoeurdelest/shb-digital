"""[BACKEND] Test T12-3 port Products + Operations CERTIFIED v1 (AGENT-products-DONE.md +
AGENT-ops-DONE.md) từ LAB shb-digital-experts thay STUB — pattern giống test_legal_port_t72.py.

4 nhóm:
1. Byte-identical vs LAB (chuỗi source — verify port KHÔNG hunk logic, kể cả seam docstring
   không đè lên function body).
2. mount_role('products'/'operations') derive đúng tool set (không hardcode) + SKILL v1 + brand D-61.
3. ops_disburse × PHANH (SỐNG CÒN) — trong GATED_WHITELIST, KHÔNG chạy qua run_labpack_fn thường,
   không bypass (nhánh human tạo phiếu pending TRƯỚC khi inner chạy — kể cả bảng applications
   chưa tồn tại T12-2, phiếu vẫn tạo/không ghi gì nếu inner lỗi sau đó).
2b. products (product_list/product_suggest) read-only — mount qua run_labpack_fn thường (không gated).
5. **30 money-test cũ (test_gated.py + test_gate_s3_gated_disburse_tester.py + test_verdict_brake_t73.py)
   PHẢI XANH NGUYÊN VẸN** — verify KHÔNG trong file này (chạy full suite riêng, dán output trong
   báo cáo) nhưng assert Ở ĐÂY rằng "disburse" (action cũ) vẫn còn trong GATED_WHITELIST/GATED_TOOLS/
   GATED_ROLE nguyên (đổi = phá 30 test).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .conftest import requires_db

REPO_ROOT = Path(__file__).resolve().parents[2]
LAB_FUNCS = REPO_ROOT.parent / "shb-digital-experts" / "missions" / "shb-132" / "tools" / "functions"


def _strip_module_docstring(src: str) -> str:
    """Bỏ module docstring (dòng đầu) — port có docstring RIÊNG (seam note), LAB thì không.
    So sánh AST function bodies, KHÔNG so text đầu file (đã biết khác — đó là phần vỏ được viết)."""
    tree = ast.parse(src)
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        tree.body = tree.body[1:]
    return ast.dump(tree)


def _functions_ast_equal(port_path: Path, lab_path: Path) -> bool:
    """[CHECK SỬA 19/7 — architect §6b] Bản cũ so text/AST CẢ MODULE → FALSE-FAIL: port có khối
    REGISTRY/SCHEMAS append HỢP LỆ (pattern legal T7-2) mà LAB không có → module lệch dù logic 0 đổi
    (test này chưa từng chạy thật trên worktree vì LAB ngoài tầm — skip). Bản mới: so AST TỪNG HÀM
    (bỏ docstring hàm) — mọi hàm LAB phải tồn tại trong port với body Y HỆT; port THÊM gì ở
    module-level là việc của test mount riêng, không phải việc check này."""
    import ast

    def defs(path: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        for n in ast.parse(path.read_text()).body:
            if isinstance(n, ast.FunctionDef):
                body = (
                    n.body[1:]
                    if (n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant))
                    else n.body
                )
                out[n.name] = ast.dump(ast.Module(body=body, type_ignores=[]))
        return out

    lab, port = defs(lab_path), defs(port_path)
    return all(name in port and port[name] == lab[name] for name in lab)


# ── 1. Byte/AST-identical vs LAB (0 hunk logic) ──────────────────────────────


@pytest.mark.skipif(not LAB_FUNCS.exists(), reason="LAB sibling repo không có trên máy này")
def test_products_functions_ast_identical_to_lab():
    """roles/products/functions.py AST-equal LAB products.py (docstring khác, logic 0 đổi)."""
    port = REPO_ROOT / "roles" / "products" / "functions.py"
    lab = LAB_FUNCS / "products.py"
    assert _functions_ast_equal(port, lab), "roles/products/functions.py lệch AST so với LAB — có hunk logic"


@pytest.mark.skipif(not LAB_FUNCS.exists(), reason="LAB sibling repo không có trên máy này")
def test_operations_functions_ast_identical_to_lab():
    """roles/operations/functions.py AST-equal LAB operations.py (docstring khác, logic 0 đổi)."""
    port = REPO_ROOT / "roles" / "operations" / "functions.py"
    lab = LAB_FUNCS / "operations.py"
    assert _functions_ast_equal(port, lab), "roles/operations/functions.py lệch AST so với LAB — có hunk logic"


def test_products_functions_no_janitor_or_lab_only_artifacts():
    """Janitor (scripts/janitor_app01.py) KHÔNG mang sang (DONE-report ghi rõ đồ lab-train)."""
    assert not (REPO_ROOT / "roles" / "operations" / "janitor_app01.py").exists()
    assert not list(REPO_ROOT.glob("roles/**/janitor*"))


def _assert_no_shb_outside_d61_comment(skill: str) -> None:
    """D-61: 'SHB' được PHÉP xuất hiện DUY NHẤT trong dòng comment HTML giải thích brand sweep
    (pattern y hệt roles/legal/SKILL.md — dòng '<!-- D-61 ... danh xưng "SHB" → ... -->').
    User-facing text (mọi dòng khác) KHÔNG được còn 'SHB'."""
    offending = [line for line in skill.splitlines() if "SHB" in line and "D-61" not in line]
    assert not offending, f"D-61 brand sweep: 'SHB' còn sót ngoài comment: {offending}"


# ── 2. mount_role derive đúng tool set + SKILL brand ─────────────────────────


def test_mount_products_exposes_two_tools_v1_skill_branded():
    from app.mount.mount_role import mount_role

    skill, _server, allowed = mount_role("products")
    tool_names = {a.rsplit("__", 1)[-1] for a in allowed}
    assert tool_names == {"product_list", "product_suggest"}, f"phải đủ 2 tool CERTIFIED: {tool_names}"
    assert "v1" in skill[:200], "SKILL phải là bản v1 (LAB certify version)"
    _assert_no_shb_outside_d61_comment(skill)
    assert "BANK Digital" in skill, "D-61: danh xưng phải là 'BANK Digital'"


def test_mount_operations_exposes_three_tools_v1_skill_branded():
    from app.mount.mount_role import mount_role

    skill, _server, allowed = mount_role("operations")
    tool_names = {a.rsplit("__", 1)[-1] for a in allowed}
    assert tool_names == {"ops_app_get", "ops_plan", "ops_disburse"}, f"phải đủ 3 tool CERTIFIED: {tool_names}"
    assert "v1" in skill[:200], "SKILL phải là bản v1 (LAB certify version)"
    _assert_no_shb_outside_d61_comment(skill)
    assert "BANK Digital" in skill, "D-61: danh xưng phải là 'BANK Digital'"
    # cũ: SKILL vỏ dạy tool tên "disburse" — LAB skill certified dạy "ops_disburse" (tên khác,
    # xem gated.py seam note: routing main_skill.py "Gọi tool disburse" là seam T12-4, KHÔNG sửa ở đây).
    assert "ops_disburse" in skill


# ── 3. ops_disburse × PHANH (SỐNG CÒN) — không bypass ────────────────────────


def test_ops_disburse_in_gated_whitelist_not_plain_mount():
    """ops_disburse PHẢI trong GATED_WHITELIST — nếu KHÔNG, mount_role sẽ gán read_handler thường
    (run_labpack_fn) → LAB write chạy TRỰC TIẾP, KHÔNG qua phanh (bypass — vi phạm SỐNG CÒN)."""
    from app.orch.gated import GATED_ROLE, GATED_TOOLS, GATED_WHITELIST

    assert "ops_disburse" in GATED_WHITELIST, "ops_disburse PHẢI gated — thiếu = bypass phanh"
    assert "ops_disburse" in GATED_TOOLS
    assert GATED_ROLE.get("ops_disburse") == "operations"


def test_disburse_action_untouched_by_ops_disburse_addition():
    """Đường 'disburse' cũ (30 money-test neo vào) PHẢI nguyên vẹn sau khi thêm ops_disburse —
    additive-only, KHÔNG sửa/xoá entry cũ."""
    from app.orch.gated import GATED_ROLE, GATED_TOOLS, GATED_WHITELIST

    assert "disburse" in GATED_WHITELIST
    assert "disburse" in GATED_TOOLS
    assert GATED_ROLE.get("disburse") == "operations"


def test_mount_operations_ops_disburse_gets_gated_handler_not_read_handler():
    """mount_role('operations') áp gated() wrapper cho ops_disburse (khớp GATED_WHITELIST theo
    TÊN — mount_role.py dòng 'handler = gated(name, read_handler) if name in GATED_WHITELIST')."""
    import roles.operations.functions as ops_mod

    from app.orch.gated import GATED_WHITELIST

    assert "ops_disburse" in ops_mod.REGISTRY
    assert "ops_disburse" in GATED_WHITELIST  # đủ điều kiện áp gated() trong mount_role loop


@requires_db
@pytest.mark.asyncio
async def test_ops_disburse_first_call_creates_pending_no_write_even_without_applications_table():
    """LIVE qua gated() thật: gọi ops_disburse LẦN ĐẦU → verdict matrix (đọc args['amount'],
    ops_disburse mang 'amount_vnd' — key khác) → KeyError-safe .get() → TypeError parse →
    ('human', None) → LUÔN qua _branch_human. Nhánh human tạo phiếu pending + card TRƯỚC KHI
    inner (LAB ops_disburse, cần bảng applications) từng được gọi — KHÔNG BYPASS dù bảng thiếu.
    Verify bằng cách gọi qua chính gated() (đường thật SDK dùng), KHÔNG gọi tắt nội bộ."""
    import json
    from uuid import uuid4

    from app.orch import registry
    from app.orch.gated import gated

    conv = f"ops-disburse-port-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("ops_disburse", None)
    args = {"application_id": "APP-PORT-TEST", "amount_vnd": 100_000_000}
    env = await h(args)
    body = env["content"][0]["text"] if "content" in env else env
    payload = json.loads(body) if isinstance(body, str) else body
    # human path: approval_required (phiếu tạo, chờ người) — KHÔNG phải kết quả đã-thực-thi.
    assert payload.get("code") == "approval_required", f"phải approval_required (human path): {payload}"
    assert payload.get("retryable") is False

    import psycopg2

    from app.db.config import DATABASE_URL

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM approvals WHERE conv_id=%s AND action='ops_disburse'",
            (conv,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1, f"phải đúng 1 phiếu pending: {rows}"
        assert rows[0][0] == "pending"
    finally:
        conn.close()


@requires_db
@pytest.mark.asyncio
async def test_ops_disburse_claim_fails_clean_4field_when_applications_table_missing():
    """[CẬP NHẬT T12-3b] Tiền đề CŨ (bảng applications chưa tồn tại T12-2) ĐÃ HẾT: T12-3b tạo bảng
    + bridge OpsConnProxy. Giờ app KHÔNG TỒN TẠI (APP-PORT-CLAIM không seed) → LAB ops_disburse trả
    found:False → bridge RAISE OpsDisburseBlocked → wrapper trả `disburse_blocked` 4-field SẠCH
    (KHÔNG traceback, KHÔNG crash, KHÔNG ghi lỡ — vẫn đúng guarantee gốc, chỉ đổi code từ gated_error
    → disburse_blocked vì nay bridge phân loại được). Đổi-hành-vi CÓ CHỦ ĐÍCH T12-3b, ghi rõ."""
    import json
    from uuid import uuid4

    import psycopg2

    from app.db.config import DATABASE_URL
    from app.orch import registry
    from app.orch.gated import gated, payload_hash

    conv = f"ops-disburse-claim-{uuid4()}"
    registry.CTX_CONV.set(conv)
    registry.CTX_TASK.set("")
    h = gated("ops_disburse", None)
    args = {"application_id": "APP-PORT-CLAIM", "amount_vnd": 100_000_000}
    ph = payload_hash("ops_disburse", args)

    await h(args)  # tạo pending

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approvals SET status='approved' WHERE conv_id=%s AND action='ops_disburse' AND payload_hash=%s",
            (conv, ph),
        )
        conn.commit()
        assert cur.rowcount == 1
        cur.close()
    finally:
        conn.close()

    env = await h(args)  # claim → inner (app không tồn tại) → found:False → bridge raise → rollback
    body = env["content"][0]["text"] if "content" in env else env
    payload = json.loads(body) if isinstance(body, str) else body
    # T12-3b: app-not-found → disburse_blocked 4-field SẠCH (KHÔNG gated_error nữa — bridge phân loại)
    assert payload.get("code") == "disburse_blocked", f"app không tồn tại phải ra disburse_blocked sạch: {payload}"
    assert set(payload.keys()) >= {"code", "message", "hint", "retryable"}, f"phải đủ 4-field: {payload}"

    # "không ghi lỡ": phiếu rollback về 'approved' (KHÔNG 'used'), 0 disbursement (app còn không có)
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status FROM approvals WHERE conv_id=%s AND payload_hash=%s", (conv, ph))
        assert cur.fetchone()[0] == "approved", "block → phiếu KHÔNG 'used' (money-invariant)"
        cur.close()
    finally:
        conn.close()
