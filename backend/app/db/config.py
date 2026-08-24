"""DB connection config — single source of truth for DATABASE_URL (CLAUDE.md §1)."""

from __future__ import annotations

import os

DEFAULT_DATABASE_URL = "postgresql://shb:shb@localhost:5432/shb"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
