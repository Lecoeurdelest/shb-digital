# Digital Expert Guild

An AI-assisted pre-assessment and middle-office workflow for complex bank lending cases. A coordinating agent delegates to credit, legal, product, and operations specialists; their tools query PostgreSQL and produce source-backed work products. Bank staff make the final decision. Sensitive actions, including disbursement, are gated server-side and require an approval ticket.

Built for problem #132 of the Vietnam AI Innovation Challenge 2026. The headless FastAPI core and [embed SDK](docs/EMBED_SDK.md) are the primary integration surfaces; the React app is a reference workspace and administrator Control Tower. The customer-facing flow is a demo/sandbox, not an automated lending decision service.

[![CI](https://github.com/Lecoeurdelest/shb-digital/actions/workflows/ci.yml/badge.svg)](https://github.com/Lecoeurdelest/shb-digital/actions/workflows/ci.yml)

## What it does

- Coordinates four specialist roles and streams messages, task state, cards, and audit events over SSE.
- Builds a source-backed credit memo and provides case intake, approval queues, shadow-review metrics, and exact-case links.
- Enforces authorization and disbursement approval at the tool boundary. A successful execution and its receipt are recorded atomically; retries return the existing receipt.
- Supports per-conversation providers and an optional local retrieval/model setup. Redis and Qdrant are opt-in scale integrations, not default dependencies.

Live demo: [digital.tinhdev.com](https://digital.tinhdev.com). Demo credentials are distributed separately; no credentials are stored in this repository. The demo deployment does not by itself establish bank-DC data residency or readiness for a real-data pilot.

## Run locally

Requirements: Docker, Python 3.11+ with [uv](https://docs.astral.sh/uv/), and Node.js 20+.

```bash
docker compose up -d db
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.prompting.sync
uv run python -m app.db.seed_from_lab
uv run python -m app.db.seed_users
uv run uvicorn app.main:app --port 8000 --reload
```

In another terminal:

```bash
cd frontend
npm install
VITE_USE_MOCK_API=false npm run dev
```

Open [localhost:5173](http://localhost:5173). The frontend proxies `/api` to `localhost:8000`. For real agent turns, configure a provider credential in a local `.env` copied from [`.env.example`](.env.example); never commit secrets.

For a containerized demo stack instead, copy `.env.example` to `.env` and run `docker compose -f docker-compose.prod.yml --env-file .env up -d --build`. The reference UI is then at [localhost:3011](http://localhost:3011). See [deployment notes](docs/deploy.md) for configuration and limitations.

## Verify

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .

cd ../frontend
npm run test
npm run typecheck
```

Use `TEST_DATABASE_URL` for an isolated test database; do not run database-mutating tests against demo data. See [AGENTS.md](AGENTS.md) for the repository's full development commands and safety invariants.

## Architecture and documentation

`backend/app/orch/` contains the coordinator, event queue, approval gate, and audit stores; `roles/` contains specialist tools and skills; `frontend/sdk/` is the embeddable client; `frontend/src/` is the reference UI.

- [Specification](SPEC.md) and [decisions](DECISIONS.md)
- [API, error, and SSE contract](docs/CONTRACT.md)
- [Embed SDK integration](docs/EMBED_SDK.md)
- [Implementation patterns](docs/patterns/00-INDEX.md)
- [Benchmark results](bench/REPORT.md) and [sprint status](sprints/CURRENT.md)
