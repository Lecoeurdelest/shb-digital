# Backend BANK Digital (S10 Docker prep) — Python 3.11 slim + uv + Claude CLI (SDK runtime).
# SDK (claude-agent-sdk) DRIVE binary `claude` (npm @anthropic-ai/claude-code) — phải cài trong image
# dù provider=zai (zai đổi base-url, nhưng CLI vẫn là runtime SDK gọi). user app non-root.

FROM python:3.11-slim

# ── deps hệ thống: node (Claude CLI npm) + libpq (psycopg2) + curl (healthcheck) + procps (`ps`,
# port DevCrew ref — SDK/process-mgmt cần). bubblewrap/socat (SDK sandbox) KHÔNG cài mặc định —
# setting_sources=[] của mình không engage sandbox; bật theo bằng chứng (deploy.md "lỗi sandbox").
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg libpq5 procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# ── uv (package manager D-26) ──
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ── user non-root — UID/GID BUILD-ARG (port DevCrew ref, durable volume ownership): named volume
# RỖNG lần đầu mount copy ownership từ image dir → phải khớp host. Compose truyền DOCKER_UID/GID.
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser \
    && useradd -u ${UID} -g appuser -m -d /home/appuser -s /usr/sbin/nologin appuser
WORKDIR /app

# ── deps trước (cache layer) — chỉ copy manifest, uv sync ──
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
# T12-5: +extra `embed` (sentence-transformers + pyvi + CPU-torch pin qua tool.uv.sources) — tầng
# vector notes_search chạy THẬT trên prod. CPU-torch ~200MB (KHÔNG CUDA). Bỏ embed → notes_search
# degrade env_missing 4-field sạch (3 tầng kia sống) — đường lùi nếu VM không kham.
RUN uv sync --frozen --no-dev --extra embed 2>/dev/null || uv sync --no-dev --extra embed

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

# DURABLE VOLUME OWNERSHIP (port DevCrew ref — miếng chính): TẠO SẴN dir sẽ mount named volume
# (data/conversations + ~/.claude) + chown TRƯỚC USER. Named volume RỖNG lần đầu mount copy ownership
# từ image dir → appuser sở hữu từ lúc sinh (hết Permission denied mkdir conversations trên fresh
# deploy — không cần chown tay). Sự cố VM 18/7.
RUN mkdir -p /app/backend/data/conversations /home/appuser/.claude \
    && chown -R appuser:appuser /app /home/appuser
USER appuser
ENV PATH="/app/backend/.venv/bin:${PATH}" HOME="/home/appuser"
WORKDIR /app/backend

# 1 worker (D-38 canonical), no-reload trong container. Migration chạy ở entrypoint compose.
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
