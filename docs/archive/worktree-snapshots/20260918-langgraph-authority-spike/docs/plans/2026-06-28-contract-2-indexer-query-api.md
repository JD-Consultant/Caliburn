# Contract #2 — Indexer Query API SSOT (shared pydantic package) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the two hand-maintained pydantic model sets for the indexer query API into
one shared package `packages/indexer-contract`, imported by both the producer (`ocs-indexer`)
and the consumer (`api`) — making drift structurally impossible (same classes, no codegen).

**Architecture:** Option B from the research record
(`docs/specs/2026-06-28-contract-2-indexer-query-api-research.md`): a pure-pydantic contract
package distributed as a per-app editable **path dependency**, exactly like `packages/ocs-contract`
(ADR 0005). Producer uses the models as FastAPI request/`response_model`; consumer's
`KnowledgePort` returns them and `HttpIndexerClient` parses them.

**Tech Stack:** Python ≥3.11, pydantic v2, uv (per-app path deps), pytest, hatchling.

## Global Constraints

- **Move-only consolidation.** No wire-shape change. Field set = union of the current producer
  (`ocs-indexer/.../api/schemas.py`) + consumer (`api/.../core/knowledge_dto.py`) models, with
  **permissive defaults** (`extra="ignore"`, `populate_by_name=True`, optional-with-defaults) to
  preserve the consumer's tolerant parsing and the producer's serialization.
- **Safety nets:** `ocs-indexer` suite **41 passed** and `api` suite **86 passed, 61 skipped**
  must hold. Producer cmds: `uv run --all-extras pytest`; consumer: `uv run --group dev pytest`
  (both `PYTHONUTF8=1`, run from each app dir).
- **Back-compat re-export shims are allowed here** (cross-package), following the Phase-2
  `ocs-contract` precedent (re-export + aliases) — definitions live only in the package, so SSOT
  holds; shims just preserve existing import paths to avoid churning ~16 test files.
- **No codegen / no schema-diff CI** — drift is impossible because both ends import the same
  module (the whole point of Option B).
- Commit per task; suites green first. Package dir `/s/caliburn/packages/indexer-contract`;
  commit from `/s/caliburn`.

---

## Task 1: create `packages/indexer-contract`

**Files:**
- Create: `packages/indexer-contract/pyproject.toml`
- Create: `packages/indexer-contract/src/indexer_contract/__init__.py`
- Create: `packages/indexer-contract/src/indexer_contract/models.py`
- Create: `packages/indexer-contract/README.md` (1 paragraph: what/why, link research record)

**Interfaces:**
- Produces module `indexer_contract.models` exporting the full query-API contract:
  requests `SearchRequest, TaskBatchGetRequest, FindSimilarRequest`; leaves
  `CodeName, OcsName, SourceRef, CitableItem`; responses `OccupationDetail, CompetencyPool,
  TaskRef, UnitTasks, OccupationTasks, OccupationHit, OccupationSearchResponse, TaskHit,
  TaskSearchResponse, TaskDetail, TasksResponse, SimilarTaskRef, SimilarPair,
  FindSimilarResponse, HealthResponse, StatsResponse`.

- [ ] **Step 1: `pyproject.toml`** (mirror `ocs-contract`):

```toml
[project]
name = "indexer-contract"
version = "0.1.0"
description = "Caliburn indexer query-API contract — shared pydantic wire models (ocs-indexer ⇄ api)"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.9,<3"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/indexer_contract"]
```

- [ ] **Step 2: `src/indexer_contract/__init__.py`** — empty (or a docstring).

- [ ] **Step 3: `src/indexer_contract/models.py`** — the canonical union (verbatim merge; requests
  keep their validation, everything else permissive):

```python
"""Indexer query-API wire contract — single source of truth (ocs-indexer ⇄ api).

Both the producer (FastAPI request/response_model) and the consumer (KnowledgePort
return types + HttpIndexerClient parsing) import THESE classes. extra="ignore"
tolerates additive producer evolution on the consumer side.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ── requests ──────────────────────────────────────────────────────────────────
class SearchRequest(_Base):
    query: str = Field(min_length=1)
    top_k: int = Field(10, ge=1, le=50)


class TaskBatchGetRequest(_Base):
    ids: list[str] = Field(min_length=1)


class FindSimilarRequest(_Base):
    ocs_codes: list[str] = Field(min_length=1)
    score_threshold: float = Field(0.85, ge=0.0, le=1.0)


# ── leaves ────────────────────────────────────────────────────────────────────
class CodeName(_Base):
    code: str = ""
    name: str = ""


class OcsName(_Base):
    job_category_name: Optional[str] = None
    occupation_name: Optional[str] = None


class SourceRef(_Base):
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    competency_level: Optional[int] = None


class CitableItem(_Base):
    id: str = ""
    type: str = ""
    code: str = ""
    name: Optional[str] = None
    text: Optional[str] = None
    ocs_code: str = ""
    ocs_name: str = ""
    sources: list[SourceRef] = Field(default_factory=list)


# ── occupation detail / competencies ──────────────────────────────────────────
class OccupationDetail(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: OcsName = Field(default_factory=OcsName)
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: Optional[int] = None
    attitudes: list[CodeName] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class CompetencyPool(_Base):
    ocs_code: str = ""
    knowledge: list[CitableItem] = Field(default_factory=list)
    skills: list[CitableItem] = Field(default_factory=list)
    outputs: list[CitableItem] = Field(default_factory=list)
    indicators: list[CitableItem] = Field(default_factory=list)
    attitudes: list[CitableItem] = Field(default_factory=list)


# ── occupation tasks ──────────────────────────────────────────────────────────
class TaskRef(_Base):
    task_code: str = ""
    task_name: str = ""
    urn: str = ""


class UnitTasks(_Base):
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    urn: str = ""
    tasks: list[TaskRef] = Field(default_factory=list)


class OccupationTasks(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    units: list[UnitTasks] = Field(default_factory=list)


# ── search ────────────────────────────────────────────────────────────────────
class OccupationHit(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: str = ""
    job_description: str = ""
    ocs_level: Optional[int] = None
    score: Optional[float] = None


class OccupationSearchResponse(_Base):
    hits: list[OccupationHit] = Field(default_factory=list)


class TaskHit(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    urn: str = ""
    score: Optional[float] = None


class TaskSearchResponse(_Base):
    hits: list[TaskHit] = Field(default_factory=list)


# ── batch get / find similar / ops ────────────────────────────────────────────
class TaskDetail(_Base):
    id: str = ""
    urn: str = ""
    ocs_code: str = ""
    ocs_name: str = ""
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    competency_blocks: list[dict] = Field(default_factory=list)


class TasksResponse(_Base):
    tasks: list[TaskDetail] = Field(default_factory=list)


class SimilarTaskRef(_Base):
    urn: str = ""
    ocs_code: str = ""
    task_code: str = ""
    task_name: str = ""


class SimilarPair(_Base):
    a: SimilarTaskRef
    b: SimilarTaskRef
    score: float


class FindSimilarResponse(_Base):
    candidates: list[SimilarPair] = Field(default_factory=list)


class HealthResponse(_Base):
    status: str = ""
    model_loaded: bool = False
    qdrant: str = ""
    collection: str = ""
    index_model: Optional[str] = None


class StatsResponse(_Base):
    collection: str = ""
    total_points: int = 0
    by_level: dict[str, int] = Field(default_factory=dict)
```

- [ ] **Step 4: standalone import check.**

```bash
cd /s/caliburn/packages/indexer-contract && uv run --with pydantic python -c "import indexer_contract.models as m; print(len([n for n in dir(m) if n[0].isupper()]), 'models')"
```

- [ ] **Step 5: Commit.**

```bash
cd /s/caliburn && git add packages/indexer-contract && git commit -m "feat(indexer-contract): shared pydantic package for the indexer query API (Contract #2 T1)

Single source of truth for the ocs-indexer⇄api wire shapes (requests + responses).
Pure pydantic, path-dep distributed like ocs-contract. No codegen."
```

---

## Task 2: producer (`ocs-indexer`) imports the contract

**Files:**
- Modify: `apps/ocs-indexer/pyproject.toml` (add dep + `[tool.uv.sources]` path)
- Modify: `apps/ocs-indexer/src/jd_ocs_indexer/api/schemas.py` → re-export from `indexer_contract.models`

**Interfaces:**
- Consumes: `indexer_contract.models`. `api/schemas.py` keeps the same public names (re-export),
  so `api/routes.py` is unchanged.

- [ ] **Step 1: add the path dep** to `apps/ocs-indexer/pyproject.toml` — mirror the
  `ocs-contract` lines: add `"indexer-contract"` to `[project].dependencies` and under
  `[tool.uv.sources]` add `indexer-contract = { path = "../../packages/indexer-contract", editable = true }`.

- [ ] **Step 2: `uv sync`** to wire the editable dep: `cd /s/caliburn/apps/ocs-indexer && uv sync --all-extras`.

- [ ] **Step 3: replace `api/schemas.py` with a re-export** (definitions now live in the package):

```python
"""Query-API pydantic models — re-exported from the shared contract package.

Single source of truth = packages/indexer-contract. Kept as this module path so
api/routes.py imports are unchanged.
"""
from indexer_contract.models import (  # noqa: F401
    CitableItem, CodeName, CompetencyPool, FindSimilarRequest, FindSimilarResponse,
    HealthResponse, OccupationDetail, OccupationHit, OccupationSearchResponse,
    OccupationTasks, OcsName, SearchRequest, SimilarPair, SimilarTaskRef, SourceRef,
    StatsResponse, TaskBatchGetRequest, TaskDetail, TaskHit, TaskRef, TaskSearchResponse,
    TasksResponse, UnitTasks,
)
```

- [ ] **Step 4: run the producer suite.** `cd /s/caliburn/apps/ocs-indexer && PYTHONUTF8=1 uv run --all-extras pytest -q` → **41 passed**.

- [ ] **Step 5: OpenAPI smoke** (response_model still resolves): `PYTHONUTF8=1 uv run python -c "from jd_ocs_indexer.api.app import create_app; create_app().openapi(); print('openapi OK')"`.

- [ ] **Step 6: Commit.**

```bash
cd /s/caliburn && git add -A && git commit -m "refactor(ocs-indexer): query-API schemas re-export indexer-contract (Contract #2 T2)

api/schemas.py now re-exports the shared package; routes.py unchanged. 41 passed."
```

---

## Task 3: consumer (`api`) imports the contract

**Files:**
- Modify: `apps/api/pyproject.toml` (add dep + `[tool.uv.sources]` path)
- Modify: `apps/api/app/core/knowledge_dto.py` → re-export from `indexer_contract.models`

**Interfaces:**
- Consumes: `indexer_contract.models`. `core/knowledge_dto.py` keeps the same public names, so
  `core/ports.py`, `adapters/*`, `services/*`, and the ~16 test imports of
  `app.core.knowledge_dto` are unchanged.

- [ ] **Step 1: add the path dep** to `apps/api/pyproject.toml` (same two-line pattern as Task 2,
  relative `../../packages/indexer-contract`).

- [ ] **Step 2: `uv sync`**: `cd /s/caliburn/apps/api && uv sync`.

- [ ] **Step 3: replace `app/core/knowledge_dto.py` with a re-export** (the api consumes a subset,
  but re-export the names the codebase already imports from this module):

```python
"""Indexer query-API DTOs — re-exported from the shared contract package.

Single source of truth = packages/indexer-contract. Kept as this module path so
existing `from app.core.knowledge_dto import ...` sites (ports, adapters, services,
tests) are unchanged.
"""
from indexer_contract.models import (  # noqa: F401
    CitableItem, CodeName, CompetencyPool, OccupationDetail, OccupationHit,
    OccupationSearchResponse, OccupationTasks, OcsName, SourceRef, TaskHit, TaskRef,
    TaskSearchResponse, UnitTasks,
)
```

- [ ] **Step 4: verify the seam-critical types are identical objects** (producer == consumer):
  `cd /s/caliburn && PYTHONUTF8=1 uv run --project apps/api python -c "from app.core.knowledge_dto import CompetencyPool as A; from indexer_contract.models import CompetencyPool as B; assert A is B; print('same class OK')"`.

- [ ] **Step 5: run the consumer suite.** `cd /s/caliburn/apps/api && PYTHONUTF8=1 uv run --group dev pytest -q` → **86 passed, 61 skipped**.

- [ ] **Step 6: import smoke.** `PYTHONUTF8=1 uv run python -c "import app.main, app.graph_v3.serving; print('import OK')"`.

- [ ] **Step 7: Commit.**

```bash
cd /s/caliburn && git add -A && git commit -m "refactor(api): knowledge DTOs re-export indexer-contract (Contract #2 T3)

core/knowledge_dto.py now re-exports the shared package — producer & consumer share
one class per wire shape (drift impossible). 86 passed."
```

---

## Task 4: ADR + tag

**Files:** Create `docs/adr/0010-indexer-contract-shared-package.md`; modify `docs/adr/README.md`.

- [ ] **Step 1: Write ADR 0010** (Chinese, Nygard-style): context (two hand-written model sets,
  `extra="ignore"` hides additive drift); decision (Option B shared pydantic package, path dep,
  re-export shims; why NOT JSON-Schema/codegen like #1 — no non-Python consumer; why NOT Pact —
  internal single-consumer); consequences (drift structurally impossible; both ends one pydantic
  major; escalate to OpenAPI/JSON-Schema only when a non-Python consumer appears); status
  Accepted 2026-06-28; link research record. Add the index row to `docs/adr/README.md`.

- [ ] **Step 2: Commit + tag.**

```bash
cd /s/caliburn
git add docs/adr/0010-indexer-contract-shared-package.md docs/adr/README.md
git commit -m "docs(adr): 0010 indexer-contract shared package (Contract #2)"
git tag -a contract2-indexer-api -m "Contract #2: indexer query API SSOT via shared pydantic package packages/indexer-contract. Both suites green (ocs-indexer 41, api 86)."
```

---

## Self-Review notes
- **Spec coverage:** research §5 method T1–T4 ↔ plan Tasks 1–4. Option B as chosen.
- **Type consistency:** the package exports every name `ocs-indexer/api/schemas.py` and
  `api/core/knowledge_dto.py` currently define; both shims re-export from it (no second
  definition anywhere). Producer-only names (requests, TaskDetail/TasksResponse, FindSimilar*,
  Health/Stats) live in the package and are re-exported by `api/schemas.py`.
- **Risk:** pydantic skew — both apps already run pydantic v2 and already share `ocs-contract`
  under the same constraint; both suites importing the package prove compatibility. `uv sync`
  per app wires the editable dep before its suite runs.
- **Net:** ocs-indexer 41 + api 86 must hold after Tasks 2 and 3 respectively.
