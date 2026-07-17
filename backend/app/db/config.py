"""DB connection config — single source of truth for DATABASE_URL (CLAUDE.md §1)."""

from __future__ import annotations

import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://shb:shb@localhost:5432/shb")
