---
name: database-erd
description: Inspect a live relational database and its migrations, generate a truthful Mermaid ERD, and review integrity, operability, and scale risks. Use for DB audits, schema migrations, ERD refreshes, or datastore architecture reviews.
---

# Database ERD

Build the diagram from evidence, not only ORM declarations.

1. Read the repository's migration rules and current database configuration.
2. Compare the live migration head, migration files, ORM metadata, and live catalog. Report drift.
3. Inventory tables, columns, PK/unique/check/FK constraints, indexes, approximate rows, and sizes.
4. Generate the physical ERD with `scripts/postgres_erd.py` when PostgreSQL is available. Use
   `--tables a,b,c` for bounded-context diagrams; composite FKs are matched by column ordinal.
5. Draw inferred relationships separately and label them `soft`; never render a soft reference as a hard FK.
6. Run orphan, duplicate-idempotency, lifecycle-invariant, timestamp-type, and hot-table/index checks.
7. Separate recommendations into: integrity now, operational scale, and data-volume optimizations. Do not recommend another database without a workload-specific reason.

For migrations, prefer additive/backfill/dual-write/enforce/drop phases. Take a backup and record preflight counts before applying destructive or constraint-tightening changes. Keep every Alembic revision reversible unless the user explicitly accepts otherwise.

The final artifact should include the inspected revision, evidence date, physical ERD, known soft references, data-quality findings, and the exact status of proposed versus applied changes.
