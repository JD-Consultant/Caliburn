# CLAUDE.md - Coding Behavior Contract

This file defines how Claude Code should behave in this repository.
These are behavioral rules, not preferences. Follow them unless the user explicitly overrides them.

## Core Rules

### 1. Think before coding
Before implementing, state assumptions, uncertainties, and tradeoffs.
Do not silently guess. If the requirement is ambiguous, ask or present the options.
If a simpler solution exists, point it out.

### 2. Simplicity first
Write the minimum code needed to solve the problem.
Do not add speculative features, unnecessary abstraction, or future-proofing that was not requested.
If the solution feels over-engineered, simplify it.

### 3. Surgical changes only
Change only what is necessary for the user's request.
Do not reformat, refactor, rename, or "clean up" unrelated code.
Match the existing style of the file and codebase.
Every changed line should be traceable to the task.

### 4. Goal-driven execution
Convert the task into verifiable success criteria before editing.
For bug fixes, reproduce the bug first when possible.
For features, define what "done" means.
Do not claim completion until the success criteria are verified.

## Agent / Workflow Rules

### 5. Do not use the model for deterministic work
Use normal code for deterministic decisions such as retries, routing, status-code handling, formatting, parsing, and fixed transformations.
Use Claude for language-heavy tasks such as classification, summarization, drafting, extraction, and reasoning.

### 6. Respect work budgets
Avoid endless loops.
If a task becomes too large, stop, summarize the current state, list what has been tried, and ask for the next direction.
Do not continue from a confused or overloaded context.

### 7. Surface conflicts; do not average them
If the codebase contains two conflicting patterns, do not blend them.
Choose the newer, better-tested, or more locally consistent pattern.
Explain the choice and mention the conflicting pattern as a follow-up cleanup item.

### 8. Read before writing
Before adding code to a file, inspect the relevant exports, callers, neighboring code, and shared utilities.
Do not add duplicate logic because you failed to read what already exists.
If the existing structure is unclear, ask before modifying it.

### 9. Tests must verify intent
Tests are required when behavior changes, but passing tests are not the goal.
A useful test should fail if the business logic is wrong.
Do not write shallow tests that only verify that "something returns something."
Test meaningful behavior, edge cases, and failure paths.

### 10. Checkpoint long tasks
For multi-step work, after each meaningful step, summarize:
- what changed
- what was verified
- what remains
- any risks or uncertainties

Do not continue from a state you cannot clearly explain.

### 11. Convention beats novelty
Follow the codebase's existing conventions even if another style seems better.
If the project uses snake_case, use snake_case.
If it uses class components, do not introduce hooks unless asked.
If a convention seems harmful, raise it explicitly instead of silently forking the style.

### 12. Fail visibly
Do not hide skipped work, failed checks, partial migrations, untested paths, or uncertainty.
Do not say "completed" if anything was skipped.
Do not say "tests pass" if tests were skipped or only partially run.
Prefer exposing uncertainty over pretending success.

## Project-Specific Rules

### Tech stack
- **Backend**: Python 3.11+, FastAPI, LangGraph, SQLAlchemy 2 (async), pgvector, Celery + Redis
- **LLM**: Multi-provider (OpenAI / Google Gemini / Anthropic Claude) via `LLM_PROVIDER` env var; embedding always uses OpenAI `text-embedding-3-small`
- **Frontend**: Next.js 16.2 (App Router), React 19, TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query 5, Zustand 5
- **DB**: PostgreSQL 16 + pgvector extension

### Build command
```bash
# Backend (runs via Docker Compose — no manual build needed for dev)
docker compose up --build

# Frontend
cd frontend && npm run dev       # dev server (port 3000)
cd frontend && npm run build     # production build
```

### Test command
```bash
# No formal test suite — manual integration scripts only
cd backend && python scripts/test_full_interview.py
cd backend && python scripts/test_ocs_api.py
cd backend && python scripts/test_ocs_export.py
cd backend && python scripts/test_rag_flow.py
```

### Lint command
```bash
# Frontend
cd frontend && npm run lint      # ESLint (eslint-config-next)
cd frontend && npx tsc --noEmit  # TypeScript type check

# Backend — no linter configured in requirements.txt
# If adding one: pip install ruff && ruff check backend/app/
```

### Important directories
- `backend/app/graph/` — LangGraph state machine (core logic)
- `backend/app/graph/nodes/` — 7 interview nodes (icap_rag, interview, task_extraction, star, five_w2h, indicator, ocs_builder)
- `backend/app/graph/prompts/` — all LLM prompts
- `backend/app/services/` — orchestrator, state service, document service, RAG retriever
- `backend/app/api/routes/` — FastAPI endpoints
- `backend/scripts/` — iCAP ingest scripts + manual test scripts
- `frontend/src/components/interview/` — chat UI + LiveDocPanel
- `docs/` — architecture, RAG pipeline, DB schema, API, testing docs

### Known failure patterns
- **Concurrent graph execution**: No backend lock — two simultaneous requests to the same `profile_id` will race on `graph_state`. Mitigated by frontend `streaming` state disabling the send button.
- **Embedding always requires OpenAI key**: Even when `LLM_PROVIDER=anthropic` or `google`, `get_embeddings()` calls OpenAI. Both API keys are needed when using non-OpenAI providers.
- **iCAP data must be ingested before use**: RAG returns empty if `icap_embeddings` table is not populated. Run `backend/scripts/icap_ingest.py` first.
- **PDF CJK fonts**: PDF export requires a CJK font (e.g., Noto Sans TC). Set `FONT_PATH` in `.env` or leave empty for auto-detect.

### Deployment / migration rules
- DB schema is managed via `backend/migrations/init.sql` (no Alembic migrations yet — schema changes require manual SQL)
- Docker Compose starts: PostgreSQL → Redis → FastAPI (health-check gated)
- Frontend runs separately from Docker (`npm run dev` or Vercel)
- iCAP vector data is seeded once via `icap_ingest.py --resume` (idempotent)
