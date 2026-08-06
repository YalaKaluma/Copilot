# SKAI Growth Copilot (Simon-Kucher)

SKAI Growth Copilot is a Simon-Kucher-aligned analytics copilot for revenue growth management (RGM) work.

It combines a prompt-driven LLM orchestrator with SKAI analytics APIs to answer commercial questions end-to-end, using a structured loop:

`SCOPE -> PLAN -> EXECUTE -> ANSWER`

The app is built as a monorepo with:
- A React frontend for chat, workflow visibility, and SKAI connection state
- A FastAPI backend for orchestration, auth, tool execution, and streaming
- PostgreSQL + Redis + worker services for persistence and async execution
- Optional GPU worker for accelerated workloads

## Executive Summary

SKAI Growth Copilot is designed to support the way Simon-Kucher teams solve commercial questions in real projects: clearly define the decision context, scope the analysis correctly, run a structured fact base, and provide a recommendation that can be defended in front of client leadership.

The core objective of this system is not to generate generic AI text. The objective is to produce reliable, transparent, and decision-ready analytical outputs for pricing, promotions, category performance, channel dynamics, and margin management. The orchestrator logic enforces this through explicit scoping rules, bounded planning, tool-based execution, and evidence-first answer formatting.

From an operating-model perspective, this repository provides a complete implementation path from user question to analytical output:
- frontend interface for user interaction and workflow transparency
- backend orchestration for structured reasoning and tool calls
- integrations to SKAI data services for analytical retrieval
- infrastructure and service patterns to run locally and deploy in production

In short, this project operationalizes a consulting-style analytical process in software form.

## Architecture

### Frontend (`services/frontend/app`)
- React 19 + TypeScript + Vite
- Clerk auth integration
- Streaming orchestrator chat UI
- Execution plan panel with tool-call log

### Backend (`services/backend/app`)
- FastAPI API server
- Orchestrator session service with SSE streaming
- OpenAI Responses API client with tool calling + structured outputs
- SKAI API client + Cognito-based per-user SKAI auth routes
- Routers for orchestrator, agent chat, realtime, jobs, files, storage, auth

### Supporting Services
- PostgreSQL (app data)
- Redis (queue/cache/pub-sub)
- Worker service (background tasks)
- Fake GCS for local storage emulation
- Optional GPU worker (native or Docker profile)

Local service wiring lives in `docker-compose.yml`.

## Orchestrator Flow

The orchestrator is implemented as staged workflow state with session memory:

1. **Scoping**
- Confirm required inputs (for example category for market-share questions)
- Ask for missing required info with constrained options
- Apply explicit defaults for optional inputs

2. **Planning**
- Create a bounded plan sized to query complexity
- Start with data retrieval and dependency-ordered steps

3. **Execution**
- Call handoff tools (currently category-focused handoff is primary)
- Track plan progress with `plan_update`
- Finish as soon as enough evidence exists using `move_to_done`

4. **Answer**
- Structured response with findings, assumptions, and confidence

This flow is intentionally aligned with how Simon-Kucher teams run analytical workstreams: clarify the business question, define the analysis plan, execute focused analyses, and return a recommendation that can be presented to client stakeholders.

### Practical Interpretation of the Four Stages

1. **Scoping stage**
- Purpose: ensure the question is analytically well-defined.
- Result: the system either has enough mandatory information or asks focused follow-up questions.
- Benefit: avoids rework and prevents invalid analysis runs.

2. **Planning stage**
- Purpose: create a right-sized set of analytical steps.
- Result: transparent plan with step-by-step logic visible to the user.
- Benefit: makes reasoning traceable and avoids unnecessary analysis overhead.

3. **Execution stage**
- Purpose: retrieve and process relevant data via specialized tools/agents.
- Result: completed plan steps, logged tool interactions, and concrete evidence.
- Benefit: clear visibility into what was done and why.

4. **Answer stage**
- Purpose: synthesize evidence into a business-usable response.
- Result: concise conclusion with assumptions, risks, and confidence.
- Benefit: immediate usability for consultant discussion and stakeholder communication.

## Local Development

### Prerequisites
- Docker + Docker Compose
- Node.js 18+
- `pnpm`
- Python 3.12 (for native scripts/tools)
- `uv` (Python package manager)

### 1) Configure environment files

Copy and fill the example files:

```bash
cp environment/.env.backend.example environment/.env.backend
cp environment/.env.frontend.example environment/.env.frontend
```

Minimum useful backend config for orchestrator flows:
- `OPENAI_API_KEY`
- `DATABASE_URL`
- `CLERK_SECRET_KEY`
- `CLERK_WEBHOOK_SECRET`
- SKAI config (`SKAI_API_URL` + token/cognito fields)

### 2) Install JS deps

```bash
pnpm install
```

### 3) Start the stack

```bash
pnpm dev
```

Default local endpoints:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8080`
- Backend OpenAPI docs: `http://localhost:8080/docs`
- Fake GCS: `http://localhost:4443`
- Redis Insight: `http://localhost:5540`

## Useful Commands

```bash
# start/stop
pnpm dev
pnpm down
pnpm dev:build
pnpm dev:debug
pnpm logs

# database
pnpm db:migrate
pnpm db:create "migration_name"
pnpm db:rollback
pnpm db:reset

# tests
pnpm test:backend
pnpm test:backend:unit
pnpm test:frontend

# pre-commit (lint + type-check before commit)
pnpm pre-commit:install   # install git hooks (run once)
pnpm pre-commit:run       # run all hooks on the repo

```

See all root scripts in `package.json`.

### Pre-commit hooks

The repo uses [pre-commit](https://pre-commit.com/) to run checks on backend and shared Python before each commit. Hooks run only on files that match their patterns (e.g. backend/packages `.py`).

**Setup (once per clone):**

```bash
pnpm pre-commit:install
```

**What runs:**

| Hook | Scope | Purpose |
|------|--------|---------|
| Trim trailing whitespace | backend, packages | Remove trailing spaces; markdown-aware |
| end-of-file-fixer | backend, packages, worker | Ensure newline at EOF |
| black | backend, packages | Format Python |
| ruff | backend, packages | Lint (with `--fix`) |
| mypy (backend) | `services/backend/app/` | Type-check backend when any backend `.py` changes |

**Run manually (e.g. before pushing):**

```bash
pnpm pre-commit:run
```

To run a single hook: `uv run pre-commit run <hook-id> --all-files` (e.g. `ruff`, `mypy-backend`). Config: `.pre-commit-config.yaml`.

## Key API Routes

All backend routes are mounted under `/api`.

High-value routes:
- `POST /api/orchestrator/chat` (SSE or non-stream)
- `POST /api/orchestrator/reply`
- `DELETE /api/orchestrator/session/{session_id}`
- `GET /api/skai/auth/status`
- `POST /api/skai/auth/login`
- `POST /api/skai/auth/refresh`
- `POST /api/skai/auth/disconnect`

## Example API Description (Model-Oriented)

`Category Landscape API (GET /api/v1/category/landscape)`

This API contains category-performance landscape data across brands, retailers, categories, subcategories, channels, and optionally specific SKUs. You can use it to retrieve the fact base for market structure questions such as "who is winning/losing share", "where growth is coming from", and "how price levels differ by segment."

You can use the parameters in the API to vary:
- Time window: `start_date`, `end_date`
- Scope of analysis: `categories`, `subcategories`, `brands`, `retailers`, `channels`, `sku_ids`
- Price lens: `price_metric` (`price_per_unit` or `price_per_scaled_volume`)

Recommended model usage pattern:
- First call with broad filters (for example category + date range) to establish baseline landscape.
- Then narrow with `brands`, `retailers`, or `channels` to isolate where the change is concentrated.
- Use `price_metric` to switch between unit-price and scaled-volume views when testing premiumization vs mix-shift hypotheses.

## Deployment / Infra

Terraform is organized by reusable modules and per-service stacks:

- Modules: `terraform/modules/`
  - `cloud-run`
  - `artifact-registry`
  - `gcs`
- Service stacks: `terraform/services/`
  - `backend`
  - `frontend`

Railway + Neon deployment is also supported through per-service Railway config files:

- Backend: `services/backend/railway.toml`
- Frontend: `services/frontend/railway.toml`

See `docs/deployment-railway-neon.md` for setup steps and required variables.

## Repository Layout

```text
services/
  backend/       FastAPI app + orchestrator + tools + SKAI integration
  frontend/      React UI + streaming chat experience
packages/
  db/            Shared DB/alembic package
  langfuse/      Observability helpers
terraform/
  modules/       Reusable infra modules
  services/      Service-specific deployments
environment/
  .env.*         Local environment files
```

## Debugging

### Backend (FastAPI) with VS Code

1. Start the full stack with backend debug enabled:

```bash
pnpm dev:debug
```

2. In VS Code, run **Attach Backend (debugpy)** from the Run panel.
