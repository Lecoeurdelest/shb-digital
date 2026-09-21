from __future__ import annotations

import logging
from typing import Any

import psycopg2

log = logging.getLogger("mount.read_scope")

_NOT_YOUR_DATA = {
    "code": "not_your_data",
    "message": "This information does not belong to the customer's case",
    "hint": "Customers may only access their own cases.",
    "retryable": False,
}


_SEARCH_TOOLS = {"cust_search"}

_ID_IS_OWNER_TOOLS = {"cust_get"}


def _creator_customer_owner(pg_conn: Any, conv_id: str) -> tuple[bool, str | None]:

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT u.role, u.owner_id FROM conversations c JOIN users u ON c.user_id=u.username WHERE c.id::text=%s",
            (conv_id,),
        )
        row = cur.fetchone()
    if not row or row[0] != "customer":
        return (False, None)
    return (True, row[1])


def _owner_of(pg_conn: Any, table: str, key_col: str, key_val: str) -> str | None:

    with pg_conn.cursor() as cur:
        cur.execute(f"SELECT owner_id FROM {table} WHERE {key_col}=%s", (key_val,))  # noqa: S608
        r = cur.fetchone()
    return r[0] if r else None


def read_scope_refusal(pg_conn: Any, conv_id: str, tool: str, args: dict[str, Any]) -> dict[str, Any] | None:

    try:
        is_customer, owner = _creator_customer_owner(pg_conn, conv_id)
        if not is_customer:
            return None

        if not owner:
            if tool in _SEARCH_TOOLS or any(
                k in args for k in ("owner_id", "id", "loan_id", "collateral_id", "application_id")
            ):
                return dict(_NOT_YOUR_DATA)
            return None

        if tool in _SEARCH_TOOLS:
            return {**_NOT_YOUR_DATA, "hint": f"Customer case: {owner}. Other customers cannot be listed."}

        if args.get("owner_id") is not None and args["owner_id"] != owner:
            return dict(_NOT_YOUR_DATA)
        if tool in _ID_IS_OWNER_TOOLS and args.get("id") is not None and args["id"] != owner:
            return dict(_NOT_YOUR_DATA)
        if args.get("loan_id") is not None and _owner_of(pg_conn, "loans", "loan_id", args["loan_id"]) != owner:
            return dict(_NOT_YOUR_DATA)
        if (
            args.get("collateral_id") is not None
            and _owner_of(pg_conn, "collaterals", "id", args["collateral_id"]) != owner
        ):
            return dict(_NOT_YOUR_DATA)

        if (
            args.get("application_id") is not None
            and _owner_of(pg_conn, "applications", "id", args["application_id"]) != owner
        ):
            return dict(_NOT_YOUR_DATA)
        return None
    except psycopg2.Error as e:
        log.warning("read-scope guard failed conv=%s tool=%s; refusing fail-closed: %s", conv_id, tool, e)
        return dict(_NOT_YOUR_DATA)
