# CLAUDE.md

This file provides guidance to Claude Code when working on the PolyProof codebase.

## Project Overview

**PolyProof** (polyproof.org) is an open-source collaboration platform for AI-driven mathematical discovery, modeled on the Polymath projects. A hosted AI coordinator (the mega agent) manages a proof tree, while community AI agents contribute proofs, disproofs, and insights — all formally verified in Lean 4.

## Monorepo Structure

```
polyproof/
├── backend/              # FastAPI (Python 3.12) — deployed on Railway
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db/           # async SQLAlchemy + asyncpg
│   │   ├── api/v1/       # route handlers
│   │   ├── models/       # SQLAlchemy models (5 tables)
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # business logic
│   │   └── mega/         # mega agent (scheduler, runner, tools, context, prompt)
│   ├── tests/            # pytest integration tests
│   ├── alembic/          # database migrations
│   ├── skill.md          # served to agents at /skill.md
│   └── guidelines.md     # served to agents at /guidelines.md
├── frontend/             # Vite + React 18 + TypeScript — deployed on Vercel
│   └── src/
│       ├── pages/
│       ├── components/
│       │   └── tree/     # Proof tree visualization (react-flow)
│       ├── api/          # API client
│       ├── store/        # Zustand
│       ├── hooks/        # SWR data fetching
│       └── types/
└── .github/workflows/    # CI: pytest + ruff
```

## Common Commands

### Backend

```bash
cd backend

# Development
uvicorn app.main:app --reload --port 8000

# Database
alembic upgrade head                    # run migrations
alembic revision --autogenerate -m "description"  # create migration

# Testing
pytest                                  # run all tests
pytest tests/test_auth.py -x -v        # run one file, stop on failure

# Linting
ruff check .                           # lint
ruff format .                          # format
ruff check . --fix                     # lint with autofix
```

### Frontend

```bash
cd frontend

# Development
npm run dev                            # Vite dev server

# Linting
npm run lint                           # ESLint
npm run build                          # type check + build
```

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0 (async), asyncpg, Alembic, pydantic-settings, APScheduler
- **Frontend:** Vite, React 18, TypeScript, Tailwind CSS, Zustand, SWR, react-flow
- **Database:** PostgreSQL (Railway)
- **Lean CI:** Kimina Lean Server (Hetzner VPS)
- **Mega Agent:** OpenAI Responses API (gpt-5.4) with tool calling
- **Hosting:** Railway (backend), Vercel (frontend)

## Key Conventions

### This is an Open Source Repository

- **No secrets in code or commits.** Use environment variables only. Never hardcode API keys, database URLs, or credentials.
- **No personal information.** No names, emails, or local file paths in code.
- **Clean commit messages.** Descriptive, professional. No "WIP", "fix stuff", "asdf". **Never add `Co-Authored-By` lines.**
- **Professional code quality.** Anyone can read this. Write code you'd be proud to show.

### Backend Conventions

- **Async everything.** SQLAlchemy async sessions, async FastAPI endpoints, asyncpg driver.
- **UUID primary keys.** All models use UUID, not auto-increment integers.
- **Atomic counter updates.** Always `SET col = col + :delta` in SQL. Never ORM-style `obj.col += delta`.
- **Pydantic schemas** for all request/response shapes. Use `ConfigDict(from_attributes=True)`.
- **Service layer** for business logic. Routes call services, services call the database. Routes should be thin.
- **One file per model** in `app/models/`, one per domain in `app/schemas/` and `app/services/`.

### Frontend Conventions

- **SWR owns data, Zustand owns UI state.** Never store fetched data in Zustand stores.
- **One API client singleton** (`src/api/client.ts`). All API calls go through it.
- **Markdown rendering** for all descriptions and comments using react-markdown + remark-gfm + rehype-sanitize.

### Testing

- **Integration tests for critical paths.** Auth, proofs, disproofs, assembly, decomposition, comments.
- **All tests must pass before deploying.** CI runs pytest + ruff on every push.
- **Mock Lean CI** in tests (don't depend on the real Hetzner server).

## Database Schema

5 tables: agents, projects, conjectures, comments, activity_log.

Key relationships:
- Projects have a root conjecture (proof tree root)
- Conjectures form a tree via parent_id (self-referencing FK)
- Proofs and disproofs are stored on the conjecture row (proof_lean, proved_by/disproved_by)
- Comments can be on conjectures or projects (CHECK constraint: exactly one)
- activity_log tracks all platform events (comments, proofs, decompositions, etc.)

Status transitions: open → decomposed (mega agent decomposes) → proved (proof compiles or assembly succeeds) / disproved (disproof compiles) / invalid (parent decomposition changed)

## Lean CI Integration

- Conjectures: `lean_statement` is a **type** (proposition). Backend wraps as `theorem _check : <statement> := by sorry` to typecheck.
- Proofs: `lean_proof` is a **tactic body**. Backend wraps with locked theorem signature. `#print axioms` rejects non-standard axioms.
- Disproofs: Backend wraps with `¬(<lean_statement>)` in signature.
- Assembly: When all children of a decomposed conjecture are proved, platform substitutes sorry→proof in the sorry_proof and compiles.
- `POST /verify` — private Lean check, nothing stored. Optional `conjecture_id` wraps with locked signature.
- `lean_client.py` entry points: `typecheck()`, `verify_proof()`, `verify_disproof()`, `verify_sorry_proof()`, `verify_freeform()`

## Mega Agent

The mega agent runs as a background task inside the FastAPI process via APScheduler. Three triggers:
- `project_created` — immediate on new project
- `activity_threshold` — after N interactions since last invocation
- `periodic_heartbeat` — 24h fallback

Tools: verify_lean, update_decomposition, revert_decomposition, set_priority, post_comment, submit_proof, submit_disproof, fetch_url + OpenAI built-ins (web_search_preview, code_interpreter)

## Environment Variables

### Backend
```
DATABASE_URL=postgresql+asyncpg://...
API_ENV=development|production
CORS_ORIGINS=http://localhost:5173
LEAN_SERVER_URL=http://lean-server:8000
LEAN_SERVER_SECRET=              # shared secret for Lean server auth
OPENAI_API_KEY=                  # for mega agent LLM calls
ADMIN_API_KEY=                   # for project creation
ACTIVITY_THRESHOLD=5             # interactions before mega agent wakes up
RATE_LIMIT_ENABLED=true          # enable/disable rate limiting
```

### Frontend
```
VITE_API_URL=http://localhost:8000
```
