# Phase 3a — `apps/api` Hexagonal Untangle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the port Protocols into a pure `app/core` ring and the concrete adapters into
`app/adapters`, so source dependencies point inward only and the `services → graph_v3`
back-edge is eliminated — without any behaviour change.

**Architecture:** Hexagonal / Ports & Adapters (Cockburn; Clean Architecture dependency rule;
Percival & Gregory *Architecture Patterns with Python*). Ports = `Protocol`s in `app/core`;
adapters implement them at the edge in `app/adapters`; `app/services` (application use-cases)
depend only on `app/core`; `app/graph_v3` (LangGraph orchestration) + `app/api` (HTTP) are the
delivery ring and wire concretes at the composition root (`serving.py` / route deps). See the
research record: `docs/specs/2026-06-28-api-hexagonal-untangle-research.md`.

**Tech Stack:** Python 3.13, FastAPI, LangGraph, pydantic v2, SQLAlchemy async, pytest.

## Global Constraints

- **Move-only refactor.** No behaviour/logic/signature changes. Function bodies move verbatim.
- **Safety net = the test suite.** Baseline: **`uv run --group dev pytest -q` → 86 passed, 61 skipped.**
  After every task the count must remain **86 passed** (skips may vary only if env changes — they
  should not here). Run from `apps/api`. Prefix `PYTHONUTF8=1` (CJK).
- **No back-compat shims** at old (wrong-layer) locations — rewire all importers (production +
  tests) so the end state is clean. Test imports are bulk-rewired with `sed`.
- **Do not touch**: the deep-interview single-layer loop (intentional, langgraph#6792); the
  `app → caliburn_api` package rename; `ocs-indexer` / `web`. Domain extraction to `core/domain`
  is **deferred** (not in this plan).
- **Commit per task** (one logical move each), only after the suite is green.
- Working dir for all commands: `s:/caliburn/apps/api` (bash: `/s/caliburn/apps/api`).
  Commit from repo root `/s/caliburn`.

---

## Task 1: `app/core/` — move the 3 ports + knowledge DTOs inward (kills the back-edge)

**Files:**
- Create: `app/core/__init__.py` (empty)
- Create: `app/core/knowledge_dto.py` (verbatim body of `app/services/knowledge/models.py`)
- Create: `app/core/ports.py` (`KnowledgePort`, `LlmPort`, `PersistPort` + `KnowledgeClient` alias)
- Delete: `app/services/knowledge/models.py`, `app/services/knowledge/base.py`
- Modify (production importers): `app/graph_v3/deps.py`, `app/graph_v3/llm.py`(none — llm doesn't import these), `app/graph_v3/stubs.py`, `app/services/knowledge/http_client.py`, `app/services/knowledge/task_detail.py`, `app/services/header_meta.py`, `app/services/ai/{clarify,draft_op,extract_tasks,recommend_ks,structure_task}.py`, `app/api/routes/ai.py`, `app/api/routes/documents.py`
- Modify (tests): all under `tests/` importing `app.services.knowledge.models` / `app.services.knowledge.base` / `app.graph_v3.deps import LlmPort` (bulk sed)

**Interfaces:**
- Produces: `app.core.knowledge_dto` (all DTO classes: `CodeName, OcsName, SourceRef, CitableItem, OccupationDetail, CompetencyPool, TaskRef, UnitTasks, OccupationTasks, OccupationHit, OccupationSearchResponse, TaskHit, TaskSearchResponse`); `app.core.ports.{KnowledgePort, LlmPort, PersistPort}` (+ `KnowledgeClient = KnowledgePort`).
- Consumes: nothing outside stdlib + pydantic + `app.core` internally.

- [ ] **Step 1: Move DTOs to core.** `git mv app/services/knowledge/models.py app/core/knowledge_dto.py` (create `app/core/__init__.py` first with `New-Item`/`touch`). Update its module docstring's first line to note it is the KnowledgePort data contract. No code changes to the classes.

- [ ] **Step 2: Create `app/core/ports.py`.** Move the `KnowledgeClient` Protocol body from the old `app/services/knowledge/base.py` (rename type to `KnowledgePort`, keep method signatures verbatim), import its DTOs from `app.core.knowledge_dto`. Append the `LlmPort` and `PersistPort` Protocol definitions moved verbatim from `app/graph_v3/deps.py`. Add at the end: `KnowledgeClient = KnowledgePort  # back-compat alias`. Then `rm app/services/knowledge/base.py`.

```python
"""Ports (hexagonal inside ring): Protocols the application/graph depend on.

Adapters in app/adapters/ implement these; nothing here imports adapters,
graph_v3, or fastapi. See docs/specs/2026-06-28-api-hexagonal-untangle-research.md.
"""
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from app.core.knowledge_dto import (
    CompetencyPool, OccupationDetail, OccupationSearchResponse,
    OccupationTasks, TaskSearchResponse,
)


class KnowledgePort(Protocol):
    async def search_occupations(self, query: str, *, top_k: int = 10) -> OccupationSearchResponse: ...
    async def search_tasks(self, query: str, *, top_k: int = 10) -> TaskSearchResponse: ...
    async def occupation(self, ocs_code: str) -> OccupationDetail: ...
    async def competencies(self, ocs_code: str) -> CompetencyPool: ...
    async def occupation_tasks(self, ocs_code: str) -> OccupationTasks: ...
    async def healthz(self) -> bool: ...


@runtime_checkable
class PersistPort(Protocol):
    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None: ...
    async def save_document(self, job_profile_id: UUID, content: dict) -> dict: ...


@runtime_checkable
class LlmPort(Protocol):
    """per-role LLM 介面（D10）。role ∈ {"deep","indicator","cheap"}。"""
    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str: ...
    async def complete_json(self, prompt: str, *, role: str = "cheap", default: Any = None) -> Any: ...


KnowledgeClient = KnowledgePort  # back-compat alias (node call sites unchanged)
```

- [ ] **Step 3: Trim `app/graph_v3/deps.py`.** Remove the `PersistPort` and `LlmPort` Protocol
  definitions and the `runtime_checkable`/`Protocol`/`Any` imports they needed. Replace the
  `from app.services.knowledge.base import KnowledgeClient` line with
  `from app.core.ports import KnowledgeClient, LlmPort, PersistPort`. Keep `DbPersist`,
  `LiveDbPersist`, and `Deps` exactly as-is for now (they move in Task 2/3).

- [ ] **Step 4: Rewire production DTO/port importers (sed).**

```bash
cd /s/caliburn/apps/api
# DTO module moved → core.knowledge_dto
grep -rl 'app\.services\.knowledge\.models' app | xargs sed -i 's/app\.services\.knowledge\.models/app.core.knowledge_dto/g'
# base port module moved → core.ports
grep -rl 'app\.services\.knowledge\.base' app | xargs sed -i 's/app\.services\.knowledge\.base/app.core.ports/g'
# kill the back-edge: services/ai + routes import LlmPort from core, not graph_v3
grep -rl 'from app\.graph_v3\.deps import LlmPort' app | xargs sed -i 's/from app\.graph_v3\.deps import LlmPort/from app.core.ports import LlmPort/g'
```

- [ ] **Step 5: Rewire test importers (sed).**

```bash
cd /s/caliburn/apps/api
grep -rl 'app\.services\.knowledge\.models' tests | xargs sed -i 's/app\.services\.knowledge\.models/app.core.knowledge_dto/g'
grep -rl 'app\.services\.knowledge\.base'   tests | xargs sed -i 's/app\.services\.knowledge\.base/app.core.ports/g'
grep -rl 'from app\.graph_v3\.deps import LlmPort' tests | xargs sed -i 's/from app\.graph_v3\.deps import LlmPort/from app.core.ports import LlmPort/g'
```

- [ ] **Step 6: Verify back-edge is gone + no stale refs.**

```bash
cd /s/caliburn/apps/api
echo "services → graph_v3 (expect NONE):"; grep -rnE 'from app\.graph_v3' app/services && echo FAIL || echo OK
echo "stale models/base refs (expect NONE):"; grep -rnE 'services\.knowledge\.(models|base)' app tests && echo FAIL || echo OK
```

- [ ] **Step 7: Run the suite.** `PYTHONUTF8=1 uv run --group dev pytest -q` → expect **86 passed, 61 skipped**.

- [ ] **Step 8: Commit.**

```bash
cd /s/caliburn && git add -A && git commit -m "refactor(api): move ports + knowledge DTOs to app/core (Phase 3a T1)

LlmPort/PersistPort/KnowledgePort + DTOs now live in app/core (the inside
ring); services/ai/* import LlmPort from core, killing the services→graph_v3
back-edge. Move-only; 86 passed."
```

---

## Task 2: `app/adapters/` — move concrete adapters to the edge

**Files:**
- Create: `app/adapters/__init__.py` (empty)
- Create: `app/adapters/llm_openrouter.py` (from `app/graph_v3/llm.py`)
- Create: `app/adapters/knowledge_http.py` (from `app/services/knowledge/http_client.py`)
- Create: `app/adapters/persistence.py` (from `app/services/persistence.py` — `ProfileRepo`, `DocRepo`, `compute_completion`; plus `DbPersist`, `LiveDbPersist` from `app/graph_v3/deps.py`)
- Create: `app/adapters/stubs.py` (from `app/graph_v3/stubs.py`)
- Delete: `app/graph_v3/llm.py`, `app/services/knowledge/http_client.py`, `app/services/persistence.py`, `app/graph_v3/stubs.py`
- Modify: `app/graph_v3/deps.py` (remove `DbPersist`/`LiveDbPersist`; keep only `Deps`), `app/graph_v3/serving.py`, `app/api/routes/{ai,documents,job_profiles}.py`
- Modify (tests): `test_llm_gateway.py`, `test_llm_tracing.py`, `test_ai_recommend_ks.py`, `test_serving_live.py`, `test_http_indexer_client.py`, `test_persistence_doc.py`

**Interfaces:**
- Produces: `app.adapters.llm_openrouter.{OpenRouterLlm, get_chat_llm, model_for_role}`;
  `app.adapters.knowledge_http.HttpIndexerClient`;
  `app.adapters.persistence.{ProfileRepo, DocRepo, DbPersist, LiveDbPersist, compute_completion}`;
  `app.adapters.stubs.{StubKnowledge, InMemoryPersist}`.
- Consumes: `app.core.ports`, `app.core.knowledge_dto`, `app.models`, sqlalchemy, httpx, langchain.

- [ ] **Step 1: LLM adapter.** `git mv app/graph_v3/llm.py app/adapters/llm_openrouter.py`. Its
  imports (`app.config`, `app.graph_v3.tracing`, `app.utils`) stay valid (delivery-internal tracing
  import is acceptable from an adapter; leave verbatim). No body changes.

- [ ] **Step 2: Knowledge HTTP adapter.** `git mv app/services/knowledge/http_client.py app/adapters/knowledge_http.py`. Its `from app.core.knowledge_dto import (...)` (rewired in T1) stays valid.

- [ ] **Step 3: Persistence adapter.** `git mv app/services/persistence.py app/adapters/persistence.py`.
  Then move `DbPersist` and `LiveDbPersist` (verbatim class bodies) **out of** `app/graph_v3/deps.py`
  **into** `app/adapters/persistence.py`; update their imports there to
  `from app.adapters.persistence import ProfileRepo, DocRepo` → not needed (same module now); they
  reference `ProfileRepo`/`DocRepo` which are local. Add `from app.core.ports import PersistPort` only
  if used for typing (optional). `compute_completion` stays in this module (used by `DocRepo.status_of`).

- [ ] **Step 4: Stubs adapter.** `git mv app/graph_v3/stubs.py app/adapters/stubs.py`. Its
  `from app.core.knowledge_dto import (...)` (rewired in T1) stays valid.

- [ ] **Step 5: Trim `app/graph_v3/deps.py` to just `Deps`.** After Step 3 removed the adapters, the
  file should contain only the imports it still needs and the `Deps` dataclass:

```python
from dataclasses import dataclass

from app.core.ports import KnowledgePort, LlmPort, PersistPort


@dataclass
class Deps:
    knowledge: KnowledgePort
    persist: PersistPort
    llm: LlmPort | None = None
```

- [ ] **Step 6: Rewire production importers (sed).**

```bash
cd /s/caliburn/apps/api
grep -rl 'app\.graph_v3\.llm' app | xargs sed -i 's/app\.graph_v3\.llm/app.adapters.llm_openrouter/g'
grep -rl 'app\.services\.knowledge\.http_client' app | xargs sed -i 's/app\.services\.knowledge\.http_client/app.adapters.knowledge_http/g'
grep -rl 'app\.graph_v3\.stubs' app | xargs sed -i 's/app\.graph_v3\.stubs/app.adapters.stubs/g'
# persistence symbols (ProfileRepo/DocRepo/compute_completion) module path
grep -rl 'from app\.services\.persistence import' app | xargs sed -i 's/from app\.services\.persistence import/from app.adapters.persistence import/g'
# DbPersist/LiveDbPersist now come from adapters, not graph_v3.deps (serving.py)
sed -i 's/from app\.graph_v3\.deps import Deps, LiveDbPersist/from app.graph_v3.deps import Deps\nfrom app.adapters.persistence import LiveDbPersist/' app/graph_v3/serving.py
```

- [ ] **Step 7: Rewire test importers (sed).**

```bash
cd /s/caliburn/apps/api
grep -rl 'app\.graph_v3\.llm' tests | xargs sed -i 's/app\.graph_v3\.llm/app.adapters.llm_openrouter/g'
grep -rl 'app\.services\.knowledge\.http_client' tests | xargs sed -i 's/app\.services\.knowledge\.http_client/app.adapters.knowledge_http/g'
grep -rl 'from app\.services\.persistence import' tests | xargs sed -i 's/from app\.services\.persistence import/from app.adapters.persistence import/g'
sed -i 's/from app\.graph_v3\.deps import LiveDbPersist/from app.adapters.persistence import LiveDbPersist/' tests/test_serving_live.py
```

- [ ] **Step 8: Verify no stale refs + layering.**

```bash
cd /s/caliburn/apps/api
echo "stale graph_v3.llm/stubs, services.http_client/persistence (expect NONE):"
grep -rnE 'graph_v3\.(llm|stubs)|services\.knowledge\.http_client|services\.persistence' app tests && echo FAIL || echo OK
echo "graph_v3.deps still exporting adapters (expect NONE):"
grep -nE 'DbPersist|LiveDbPersist|class .*Persist' app/graph_v3/deps.py && echo FAIL || echo OK
```

- [ ] **Step 9: Run the suite.** `PYTHONUTF8=1 uv run --group dev pytest -q` → expect **86 passed**.

- [ ] **Step 10: Commit.**

```bash
cd /s/caliburn && git add -A && git commit -m "refactor(api): move concrete adapters to app/adapters (Phase 3a T2)

OpenRouterLlm, HttpIndexerClient, persistence repos + DbPersist/LiveDbPersist,
stubs now live in app/adapters (the edge). graph_v3/deps.py is now just the
Deps dataclass importing ports from core. Move-only; 86 passed."
```

---

## Task 3: verify the hexagon + final wiring sanity

**Files:** Modify only if a check fails. Read-only otherwise.

**Interfaces:** none (verification task).

- [ ] **Step 1: Dependency-direction audit.** All must print `OK`:

```bash
cd /s/caliburn/apps/api
echo "core imports nothing outward (expect NONE):"; grep -rnE 'from app\.(adapters|graph_v3|api|services)' app/core && echo FAIL || echo OK
echo "services imports nothing outward (expect NONE):"; grep -rnE 'from app\.(adapters|graph_v3|api)' app/services && echo FAIL || echo OK
echo "adapters do not import graph_v3/api (tracing import allowed) :"; grep -rnE 'from app\.(graph_v3|api)' app/adapters | grep -v 'graph_v3.tracing' && echo REVIEW || echo OK
```

  Note: `app/adapters/llm_openrouter.py` importing `app.graph_v3.tracing` is the one tolerated
  edge→delivery reference (OTel span helper). If undesired, a follow-up can move `tracing` to
  `app/core/`; **out of scope here** — record it in the ADR's "known follow-ups".

- [ ] **Step 2: Import smoke.** `PYTHONUTF8=1 uv run python -c "import app.main, app.graph_v3.serving, app.api.routes.ai, app.api.routes.documents; print('import OK')"`.

- [ ] **Step 3: Pyflakes.** `uv run --group dev ruff check --select F app/` → expect `All checks passed!` (no unused imports / undefined names introduced by the moves).

- [ ] **Step 4: Full suite re-confirm.** `PYTHONUTF8=1 uv run --group dev pytest -q` → **86 passed, 61 skipped**.

- [ ] **Step 5: Commit (only if Step 1–3 required edits; otherwise skip).**

```bash
cd /s/caliburn && git add -A && git commit -m "chore(api): hexagon dependency-direction audit fixes (Phase 3a T3)"
```

---

## Task 4: ADR + tag

**Files:**
- Create: `docs/adr/0008-api-hexagonal-layering.md`

- [ ] **Step 1: Write the ADR.** Record: context (the inverted dependency + scattered ports/
  adapters), decision (core/ports + adapters/ + services depend only on core; graph_v3/api are
  delivery), consequences (clean inward dependency; back-edge removed), status `Accepted`, date
  2026-06-28, and "known follow-ups" (domain extraction to `core/domain`; `tracing` placement;
  `app → caliburn_api` rename). Link the research record.

- [ ] **Step 2: Commit + tag.**

```bash
cd /s/caliburn
git add docs/adr/0008-api-hexagonal-layering.md
git commit -m "docs(adr): 0008 api hexagonal layering (Phase 3a)"
git tag -a phase3a-api-hexagonal -m "Phase 3a: api ports→core, adapters→edge, services→graph_v3 back-edge removed. Move-only; 86 passed throughout."
```

---

## Self-Review notes
- **Spec coverage:** research §6 tasks T1–T3 map to plan Tasks 1–3; research T5 → plan Task 4.
  Research T4 (domain) intentionally excluded per scope decision.
- **Type consistency:** `KnowledgePort`(+`KnowledgeClient` alias), `LlmPort`, `PersistPort`,
  `Deps`, `OpenRouterLlm`, `HttpIndexerClient`, `ProfileRepo`, `DocRepo`, `DbPersist`,
  `LiveDbPersist`, `StubKnowledge`, `InMemoryPersist`, `compute_completion` — names preserved
  exactly (no renames except `KnowledgeClient`→`KnowledgePort` with alias).
- **Risk:** import cycles — mitigated by core importing only stdlib/pydantic and the Task 3 audit.
- **Net:** 86 passed must hold after each task; any drop = stop and investigate (executing-plans rule).
