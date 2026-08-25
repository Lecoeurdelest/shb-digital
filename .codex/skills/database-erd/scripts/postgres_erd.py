#!/usr/bin/env python3
"""Print a Mermaid ERD from PostgreSQL's live catalog without modifying the DB."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

import psycopg2


def _ident(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value).upper()


def _type_name(data_type: str, udt_name: str) -> str:
    aliases = {
        "timestamp with time zone": "timestamptz",
        "timestamp without time zone": "timestamp",
        "character varying": "varchar",
        "double precision": "float8",
    }
    if data_type == "USER-DEFINED":
        return udt_name
    return aliases.get(data_type, data_type.replace(" ", "_"))


def render(dsn: str, schema: str, tables: set[str] | None = None) -> str:
    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.table_name, c.column_name, c.data_type, c.udt_name,
                       c.is_nullable = 'YES' AS nullable,
                       EXISTS (
                         SELECT 1
                         FROM information_schema.table_constraints tc
                         JOIN information_schema.key_column_usage kcu
                           ON tc.constraint_name=kcu.constraint_name
                          AND tc.constraint_schema=kcu.constraint_schema
                         WHERE tc.table_schema=c.table_schema
                           AND tc.table_name=c.table_name
                           AND tc.constraint_type='PRIMARY KEY'
                           AND kcu.column_name=c.column_name
                       ) AS is_pk
                FROM information_schema.columns c
                WHERE c.table_schema=%s
                ORDER BY c.table_name, c.ordinal_position
                """,
                (schema,),
            )
            columns = cur.fetchall()
            cur.execute(
                """
                SELECT tc.table_name, child.column_name,
                       parent.table_name, parent.column_name, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage child
                  ON tc.constraint_name=child.constraint_name
                 AND tc.constraint_schema=child.constraint_schema
                JOIN information_schema.referential_constraints rc
                  ON rc.constraint_name=tc.constraint_name
                 AND rc.constraint_schema=tc.constraint_schema
                JOIN information_schema.key_column_usage parent
                  ON parent.constraint_name=rc.unique_constraint_name
                 AND parent.constraint_schema=rc.unique_constraint_schema
                 AND parent.ordinal_position=child.position_in_unique_constraint
                WHERE tc.table_schema=%s AND tc.constraint_type='FOREIGN KEY'
                ORDER BY tc.table_name, tc.constraint_name, child.ordinal_position
                """,
                (schema,),
            )
            foreign_keys = cur.fetchall()
    finally:
        conn.close()

    if tables:
        columns = [row for row in columns if row[0] in tables]
        foreign_keys = [row for row in foreign_keys if row[0] in tables and row[2] in tables]

    by_table: dict[str, list[tuple]] = defaultdict(list)
    for row in columns:
        by_table[row[0]].append(row)

    lines = ["erDiagram"]
    for table, table_columns in by_table.items():
        lines.append(f"  {_ident(table)} {{")
        for _, column, data_type, udt_name, nullable, is_pk in table_columns:
            # Mermaid chỉ nhận PK/FK/UK ở vị trí key. NOT_NULL là token tự do nên làm
            # parser mới lỗi; giữ thông tin nullability trong comment hợp lệ của attribute.
            key = " PK" if is_pk else ""
            comment = ' "NOT NULL"' if not nullable else ""
            lines.append(f"    {_type_name(data_type, udt_name)} {column}{key}{comment}")
        lines.append("  }")

    grouped_foreign_keys: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for child, child_col, parent, parent_col, constraint in foreign_keys:
        grouped_foreign_keys[(child, parent, constraint)].append((child_col, parent_col))
    for (child, parent, constraint), column_pairs in grouped_foreign_keys.items():
        child_cols = ",".join(pair[0] for pair in column_pairs)
        parent_cols = ",".join(pair[1] for pair in column_pairs)
        label = f"{constraint}:{child_cols}->{parent_cols}"
        lines.append(f'  {_ident(parent)} ||--o{{ {_ident(child)} : "{label}"')
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn-env", default="DATABASE_URL")
    parser.add_argument("--schema", default="public")
    parser.add_argument(
        "--tables",
        help="comma-separated table allowlist; foreign keys are shown when both tables are included",
    )
    args = parser.parse_args()
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        print(f"missing environment variable: {args.dsn_env}", file=sys.stderr)
        return 2
    tables = {item.strip() for item in (args.tables or "").split(",") if item.strip()} or None
    print(render(dsn, args.schema, tables))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
