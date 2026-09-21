# Backend BANK Digital (S10 Docker prep) — Python 3.11 slim + uv + Claude CLI (SDK runtime).
# The SDK (claude-agent-sdk) drives the `claude` binary from npm @anthropic-ai/claude-code, so it must be installed in
# the image even with provider=zai. ZAI changes the base URL, but the CLI remains the SDK runtime. The app user is non-root.

FROM python:3.11-slim

# System dependencies: Node (Claude CLI npm), libpq (psycopg2), curl (health check), and procps (`ps`, from the DevCrew
# reference port, required by SDK process management). bubblewrap/socat (SDK sandbox) are not installed by default because
# setting_sources=[] does not engage the sandbox. Enable them only with evidence; see the sandbox issue in deploy.md.
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
# An empty first-time mount copies ownership from the image directory, so it must match the host. Compose passes UID/GID.
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser \
    && useradd -u ${UID} -g appuser -m -d /home/appuser -s /usr/sbin/nologin appuser
WORKDIR /app

# Install dependencies first for layer caching: copy only manifests, then run uv sync.
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
# T12-5: add the `embed` extra (sentence-transformers, pyvi, and CPU torch pinned through tool.uv.sources) so the vector
# notes_search layer runs in production. CPU torch is about 200 MB with no CUDA. Omitting embed makes notes_search degrade
# to a clean four-field env_missing response while the other three layers remain available, providing a fallback for small VMs.
RUN uv sync --frozen --no-dev --extra embed --extra scale 2>/dev/null || uv sync --no-dev --extra embed --extra scale

# Application code: backend plus roles labpack. mount_role reads roles/ from REPO_ROOT.
WORKDIR /app
COPY backend/ ./backend/
COPY roles/ ./roles/
# FIX D (deploy-blocking): configs/providers.yaml — Providers loader resolve /app/configs/ (parents[3]
# from /app/backend/app/orch). If missing, the loader falls back to the claude-cli-only built-in default, a dead end on VMs.
COPY configs/ ./configs/
# Seed snapshot (D-62): the repository contains its own seed. seed_from_lab falls back to /app/deploy/seed/ when a bare VM
# clone has no LAB sibling.
COPY deploy/seed/ ./deploy/seed/

# Durable volume ownership (the key DevCrew reference-port fix): create directories for named volumes
# (data/conversations and ~/.claude) and chown them before USER. On first mount, an empty named volume copies ownership
# from the image directory, so appuser owns it immediately. This prevents permission errors when creating conversations
# on a fresh deployment without manual chown. See the 18 July VM incident.
RUN mkdir -p /app/backend/data/conversations /home/appuser/.claude /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser
# T12-5 incident on 19 July: hf_cache mounts at /home/appuser/.cache. The directory must exist in the image so the first
# mount copies appuser ownership. Otherwise the volume is root-owned and the uv cache exits with code 2.
USER appuser
ENV PATH="/app/backend/.venv/bin:${PATH}" HOME="/home/appuser"
WORKDIR /app/backend

# Use one worker (D-38 canonical) and no reload in the container. Compose runs migrations in the entrypoint.
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
