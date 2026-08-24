"""Tenant-scoped conversation-group persistence (D-79).

Groups organize conversations only. They never become a case identity or orchestration boundary.
All public functions require a server-derived tenant id; non-admin visibility is owner-scoped.
"""

from __future__ import annotations

import asyncio
from typing import Any

import psycopg2
import psycopg2.extras

from app.storage import connect_core


class GroupNameConflict(Exception):
    """The same creator already has a case-insensitive group name in this tenant."""


def _group_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "created_by": row["created_by"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def _list_sync(tenant_id: str, username: str, is_admin: bool) -> list[dict[str, Any]]:
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if is_admin:
                cur.execute(
                    "SELECT id,name,created_by,created_at,updated_at FROM conversation_groups "
                    "WHERE tenant_id=%s ORDER BY lower(name),created_at",
                    (tenant_id,),
                )
            else:
                cur.execute(
                    "SELECT id,name,created_by,created_at,updated_at FROM conversation_groups "
                    "WHERE tenant_id=%s AND created_by=%s ORDER BY lower(name),created_at",
                    (tenant_id, username),
                )
            return [_group_to_dict(dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _create_sync(tenant_id: str, username: str, name: str) -> dict[str, Any]:
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO conversation_groups(tenant_id,name,created_by) VALUES(%s,%s,%s) "
                "RETURNING id,name,created_by,created_at,updated_at",
                (tenant_id, name, username),
            )
            row = cur.fetchone()
        conn.commit()
        return _group_to_dict(dict(row))
    except psycopg2.errors.UniqueViolation as exc:
        conn.rollback()
        raise GroupNameConflict(name) from exc
    finally:
        conn.close()


def _update_sync(
    group_id: str,
    tenant_id: str,
    username: str,
    is_admin: bool,
    name: str,
) -> dict[str, Any] | None:
    conn = connect_core()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            owner_clause = "" if is_admin else " AND created_by=%s"
            params: tuple[Any, ...] = (name, group_id, tenant_id) if is_admin else (name, group_id, tenant_id, username)
            cur.execute(
                "UPDATE conversation_groups SET name=%s,updated_at=now() "
                f"WHERE id=%s AND tenant_id=%s{owner_clause} "
                "RETURNING id,name,created_by,created_at,updated_at",
                params,
            )
            row = cur.fetchone()
        conn.commit()
        return _group_to_dict(dict(row)) if row else None
    except psycopg2.errors.InvalidTextRepresentation:
        conn.rollback()
        return None
    except psycopg2.errors.UniqueViolation as exc:
        conn.rollback()
        raise GroupNameConflict(name) from exc
    finally:
        conn.close()


def _delete_sync(group_id: str, tenant_id: str, username: str, is_admin: bool) -> bool:
    """Delete one group and ungroup its conversations in the same transaction."""
    conn = connect_core()
    try:
        with conn.cursor() as cur:
            owner_clause = "" if is_admin else " AND created_by=%s"
            params: tuple[Any, ...] = (group_id, tenant_id) if is_admin else (group_id, tenant_id, username)
            cur.execute(
                f"SELECT 1 FROM conversation_groups WHERE id=%s AND tenant_id=%s{owner_clause} FOR UPDATE",
                params,
            )
            if cur.fetchone() is None:
                conn.rollback()
                return False
            cur.execute(
                "UPDATE conversations SET group_id=NULL WHERE tenant_id=%s AND group_id=%s",
                (tenant_id, group_id),
            )
            cur.execute("DELETE FROM conversation_groups WHERE id=%s AND tenant_id=%s", (group_id, tenant_id))
        conn.commit()
        return True
    except psycopg2.errors.InvalidTextRepresentation:
        conn.rollback()
        return False
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _assign_sync(
    conv_id: str,
    group_id: str | None,
    tenant_id: str,
    username: str,
    is_admin: bool,
) -> bool:
    """Assign/unassign after the router has authorized the conversation; False hides unusable groups."""
    conn = connect_core()
    try:
        with conn.cursor() as cur:
            if group_id is not None:
                owner_clause = "" if is_admin else " AND created_by=%s"
                params: tuple[Any, ...] = (group_id, tenant_id) if is_admin else (group_id, tenant_id, username)
                cur.execute(
                    f"SELECT 1 FROM conversation_groups WHERE id=%s AND tenant_id=%s{owner_clause}",
                    params,
                )
                if cur.fetchone() is None:
                    conn.rollback()
                    return False
            cur.execute(
                "UPDATE conversations SET group_id=%s WHERE id::text=%s AND tenant_id=%s",
                (group_id, conv_id, tenant_id),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return False
        conn.commit()
        return True
    except psycopg2.errors.InvalidTextRepresentation:
        conn.rollback()
        return False
    finally:
        conn.close()


def _can_use_sync(group_id: str, tenant_id: str, username: str, is_admin: bool) -> bool:
    conn = connect_core()
    try:
        with conn.cursor() as cur:
            owner_clause = "" if is_admin else " AND created_by=%s"
            params: tuple[Any, ...] = (group_id, tenant_id) if is_admin else (group_id, tenant_id, username)
            cur.execute(
                f"SELECT 1 FROM conversation_groups WHERE id=%s AND tenant_id=%s{owner_clause}",
                params,
            )
            return cur.fetchone() is not None
    except psycopg2.errors.InvalidTextRepresentation:
        return False
    finally:
        conn.close()


async def list_groups(tenant_id: str, username: str, is_admin: bool) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_list_sync, tenant_id, username, is_admin)


async def create_group(tenant_id: str, username: str, name: str) -> dict[str, Any]:
    return await asyncio.to_thread(_create_sync, tenant_id, username, name)


async def update_group(
    group_id: str, tenant_id: str, username: str, is_admin: bool, name: str
) -> dict[str, Any] | None:
    return await asyncio.to_thread(_update_sync, group_id, tenant_id, username, is_admin, name)


async def delete_group(group_id: str, tenant_id: str, username: str, is_admin: bool) -> bool:
    return await asyncio.to_thread(_delete_sync, group_id, tenant_id, username, is_admin)


async def assign_conversation_group(
    conv_id: str,
    group_id: str | None,
    tenant_id: str,
    username: str,
    is_admin: bool,
) -> bool:
    return await asyncio.to_thread(_assign_sync, conv_id, group_id, tenant_id, username, is_admin)


async def can_use_group(group_id: str, tenant_id: str, username: str, is_admin: bool) -> bool:
    return await asyncio.to_thread(_can_use_sync, group_id, tenant_id, username, is_admin)
