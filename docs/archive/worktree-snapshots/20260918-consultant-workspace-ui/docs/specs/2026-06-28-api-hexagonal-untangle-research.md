# Phase 3a Research Record — `apps/api` Hexagonal Untangle (core/ports · adapters · kill the graph↔services back-edge)

> Research record (權威資料 + 診斷). Authored 2026-06-28. Sub-project of the Caliburn
> per-project internal-optimization phase (Phase 3). Companion to the implementation
> plan `docs/plans/2026-06-28-phase3a-api-hexagonal-untangle.md`.

## 1. Goal

`apps/api` (FastAPI + LangGraph JD-authoring backend) is already *partly* hexagonal —
it has `Protocol` ports and adapters. But the layering is **inconsistent in placement**
and has an **inverted dependency**. Phase 3a fixes the dependency direction so the
architecture matches its own intent, with the existing test suite as the safety net.

Scope is deliberately a **move-only / import-rewiring refactor** (no behaviour change),
verified green by the test suite at every step — the same discipline that carried
Phase 3b (golden net → Extract Class → thin orchestrator).

## 2. Current state (what the code actually does)

Evidence gathered by reading the modules and grepping cross-layer imports.

### 2.1 Ports & adapters that already exist (good)
- `services/knowledge/base.py` — `KnowledgeClient` **Protocol** (port). ✓ well placed
- `services/knowledge/http_client.py` — `HttpIndexerClient` (HTTP adapter). ✓
- `services/knowledge/models.py` — pydantic DTOs (the port's data contract).
- `services/persistence.py` — `ProfileRepo`, `DocRepo` (Repository-pattern DB adapters) + `compute_completion` (domain logic).
- `graph_v3/deps.py` — `PersistPort`, `LlmPort` **Protocols** + `DbPersist`/`LiveDbPersist` adapters + `Deps` dataclass (the composition struct).
- `graph_v3/llm.py` — `OpenRouterLlm` (network LLM adapter).
- `graph_v3/stubs.py` — `StubKnowledge`, `InMemoryPersist` (test doubles).

### 2.2 The dependency-rule violations (the tangle)

```
            ┌─────────────── graph_v3 (DELIVERY: orchestration) ───────────────┐
            │  deps.py  ──defines──▶  LlmPort, PersistPort   (PORTS live here!) │
            │  llm.py   ──defines──▶  OpenRouterLlm          (ADAPTER lives here)│
            └───────────────────────────▲──────────────────────────────────────┘
                                         │ imports LlmPort   ◀── BACK-EDGE (wrong way)
   ┌──────────── services/ (APPLICATION use-cases) ──────────┐
   │  ai/clarify, ai/draft_op, ai/extract_tasks,             │
   │  ai/recommend_ks, ai/structure_task                     │
   └─────────────────────────────────────────────────────────┘
   routes/ai.py ──imports──▶ graph_v3.deps.LlmPort + graph_v3.llm.OpenRouterLlm
```

Concretely (verified by grep):
1. **Ports live inside `graph_v3`** (a delivery mechanism). `LlmPort`/`PersistPort` are
   in `graph_v3/deps.py`. A port is the *inside* of the hexagon; it must not live in an
   outer ring.
2. **`services` (application) depends on `graph_v3` (delivery).** All five
   `services/ai/*` use-cases do `from app.graph_v3.deps import LlmPort`. The application
   layer importing the delivery layer is the dependency rule reversed.
3. **`routes` reach into `graph_v3` for ports + adapters** (`LlmPort`, `OpenRouterLlm`).
4. **`services/` has no single meaning** — it mixes a port (`knowledge/base`), adapters
   (`knowledge/http_client`, `persistence`), application use-cases (`ai/*`, `ocs_doc`,
   `header_meta`), and domain logic (`compute_completion`).

What is *already clean* and must be **preserved**: nodes consume collaborators via
`config["configurable"]["deps"]` (dependency injection at the graph boundary);
`serving.py` is the composition root; the deep-interview is a deliberate single-layer
loop (see memory `deep-interview-single-layer-loop`, langgraph#6792 — **do not** convert
to subgraphs).

## 3. Authoritative sources & what they prescribe

| Source | Authority | Prescription relevant here |
|---|---|---|
| Alistair Cockburn, *Hexagonal (Ports & Adapters) Architecture* (originator; 2024 book w/ Garrido de Paz) | Primary inventor | "Code pertaining to the **inside** must not leak into the **outside**." The inside (business logic) **defines** the ports; adapters on the outside implement them. A port is an API defined by the *purpose of the conversation*, owned by the inside. |
| Robert C. Martin, *Clean Architecture* — the Dependency Rule | Canonical | Source-code dependencies point **only inward**. Inner circles know nothing of outer circles. Interfaces (ports) belong to the inner circle; frameworks/IO are the outermost ring. |
| Percival & Gregory, *Architecture Patterns with Python* (O'Reilly, 2020) | The standard Python reference | Dependency inversion ⇒ ports & adapters; **service layer** (application) orchestrates use-cases and depends on abstractions; **Repository** pattern for persistence. Idiomatic Python: ports as `Protocol`/ABC, adapters injected. |
| LangChain — *Thinking in LangGraph* (official docs) | Framework owner | Nodes "do one specific thing"; **isolate external services into their own nodes**; "state should store **raw data, not formatted text** — format prompts inside nodes"; smaller nodes are "easier to test in isolation and reuse." Orchestration ≠ business logic. |
| FastAPI — *Dependencies* (official) + layered-architecture guidance | Framework owner | DI container resolves dependencies; structure large apps by **module/functionality** with a layered architecture; wire concretes at the edge (composition root) so business logic stays testable. |
| PEP 544 — Structural subtyping (`Protocol`) | Python language spec | Static-duck-typed interfaces: define the port as a `Protocol`; any class structurally matching it is an adapter — no inheritance/registration coupling. |

**Convergent conclusion:** ports belong to the **inside** (a `core`/domain ring), the
application layer depends only on those ports, adapters implement them at the **edge**,
and the delivery layer (LangGraph graph + FastAPI routes) wires concretes in at a
composition root. The api already uses every one of these tools — Phase 3a is about
**moving the ports inward and flipping the back-edge**, not introducing new machinery.

## 4. Target architecture

```
app/
  core/                     # INSIDE: pure; no imports of adapters / graph_v3 / fastapi
    ports.py                # LlmPort, PersistPort, KnowledgePort  (all Protocols)
    knowledge_dto.py        # pydantic DTOs that the KnowledgePort speaks (from services/knowledge/models)
    domain/                 # (optional, T4) compute_completion + OCS-doc shaping helpers
  services/                 # APPLICATION use-cases; import ONLY from app.core (+ stdlib/pydantic)
    ai/{clarify,draft_op,extract_tasks,recommend_ks,structure_task,tasks}
    knowledge/task_detail.py
    ocs_doc.py, header_meta.py
  adapters/                 # EDGE: concrete tech implementing core ports
    llm_openrouter.py       # OpenRouterLlm        (from graph_v3/llm.py)
    knowledge_http.py       # HttpIndexerClient     (from services/knowledge/http_client.py)
    persistence.py          # ProfileRepo, DocRepo, DbPersist, LiveDbPersist
    stubs.py                # StubKnowledge, InMemoryPersist  (from graph_v3/stubs.py)
  graph_v3/                 # DELIVERY: orchestration only
    nodes, deep_nodes, curate_nodes, build_doc, graph, state, constants, prompts, tracing
    deps.py                 # just the `Deps` dataclass; imports ports from app.core.ports
    serving.py              # composition root: build_live_deps wires app.adapters.*
  api/routes/*              # DELIVERY: HTTP; depend on app.services + app.core.ports; wire adapters at edge
```

Dependency arrows after the change point **inward only**:
`adapters → core.ports` · `services → core.ports` · `graph_v3 → services + core.ports` ·
`routes → services + core.ports`. The `services → graph_v3` back-edge is gone.

### Decisions
- **D-3a-1**: All port Protocols consolidate in `app/core/ports.py` (single inside ring).
  `KnowledgeClient` is renamed-in-place to `KnowledgePort` for naming symmetry (keep a
  back-compat alias `KnowledgeClient = KnowledgePort` to avoid churn in node call sites).
- **D-3a-2**: The KnowledgePort's DTOs move to `app/core/knowledge_dto.py` (a port's data
  contract belongs with the port). `services/knowledge/models.py` becomes a re-export shim
  for back-compat, or is removed if no external importer remains.
- **D-3a-3**: Concrete adapters consolidate under `app/adapters/`. `graph_v3/deps.py`
  keeps **only** the `Deps` dataclass.
- **D-3a-4**: `services/*` import ports from `app.core.ports` — this is what removes the
  inverted dependency.
- **D-3a-5 (scope guard)**: The domain extraction (`core/domain`, T4) is **optional** and
  done last; if it adds risk it is deferred. The deep-interview single-layer loop is **not**
  touched. The package rename `app → caliburn_api` (flagged in `pyproject.toml`) is a
  separate mechanical change, **out of scope** for 3a.

## 5. Safety net & method

- **Net**: the existing pytest suite — **baseline 86 passed, 61 skipped** (skips need
  DB/LLM-key/network). Because this is move-only, green-before == green-after proves
  behaviour preserved (the api analogue of Phase 3b's golden characterization test).
- **Method** (per module move, one commit each): create new home → rewire imports
  (grep-driven) → `uv run --group dev pytest -q` (expect 86 passed) → commit. Keep
  back-compat re-export shims only where they cut cross-file churn; remove them once
  importers are migrated.
- **Risk**: import cycles. Mitigation: `core` imports only stdlib + pydantic; `adapters`
  and `services` import `core` but never each other's internals beyond ports; verify with
  `ruff --select F` (unused/undefined) + a cheap `python -c "import app..."` smoke per step.

## 6. Proposed task breakdown (detailed in the plan)

- **T0** — confirm green baseline (done: 86 passed).
- **T1** — `app/core/ports.py` + `app/core/knowledge_dto.py`: move the 3 ports + DTOs; rewire importers; tests green.
- **T2** — `app/adapters/`: move `OpenRouterLlm`, `HttpIndexerClient`, persistence repos + `DbPersist`/`LiveDbPersist`, stubs; rewire; tests green.
- **T3** — thin `graph_v3/deps.py` to the `Deps` dataclass; fix `serving.py` + `routes/*` to import ports from `core` and adapters from `app.adapters`; confirm the `services → graph_v3` back-edge is gone (grep); tests green.
- **T4 (optional)** — extract domain logic (`compute_completion`, OCS-doc shaping) to `app/core/domain`; tests green.
- **T5** — ADR (`docs/adr/0008-api-hexagonal-layering.md`) + tag `phase3a-api-hexagonal`.

## 7. Out of scope
Behaviour/feature changes; deep-interview loop restructuring; `app → caliburn_api` package
rename; touching `ocs-indexer` (Phase 3c) or `web`.
