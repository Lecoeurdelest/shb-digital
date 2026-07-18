# Backend BANK Digital (S10 Docker prep) — Python 3.11 slim + uv + Claude CLI (SDK runtime).
# SDK (claude-agent-sdk) DRIVE binary `claude` (npm @anthropic-ai/claude-code) — phải cài trong image
# dù provider=zai (zai đổi base-url, nhưng CLI vẫn là runtime SDK gọi). user app non-root.

FROM python:3.11-slim

# ── deps hệ thống: node (cho Claude CLI npm) + libpq (psycopg2) + curl (healthcheck) ──
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg libpq5 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# ── uv (package manager D-26) ──
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ── user non-root (app chạy quyền thấp; ~/.claude + data volume map ở compose) ──
RUN useradd -m -u 10001 appuser
WORKDIR /app

# ── deps trước (cache layer) — chỉ copy manifest, uv sync ──
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# ── code (backend + roles labpack — mount_role đọc roles/ ở REPO_ROOT) ──
WORKDIR /app
COPY backend/ ./backend/
COPY roles/ ./roles/
# FIX D (deploy-blocking): configs/providers.yaml — Providers loader resolve /app/configs/ (parents[3]
# từ /app/backend/app/orch). THIẾU → loader rơi built-in default CHỈ claude-cli (nút chết trên VM).
COPY configs/ ./configs/
# SEED snapshot (D-62): repo tự chứa seed — seed_from_lab fallback rơi vào /app/deploy/seed/
# khi không có LAB sibling (VM clone-trần).
COPY deploy/seed/ ./deploy/seed/

RUN chown -R appuser:appuser /app
USER appuser
ENV PATH="/app/backend/.venv/bin:${PATH}"
WORKDIR /app/backend

# 1 worker (D-38 canonical), no-reload trong container. Migration chạy ở entrypoint compose.
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
