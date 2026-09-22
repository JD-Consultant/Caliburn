# Contract #2 Research Record — Indexer Query API (ocs-indexer ⇄ api)

> Research record (權威資料 + 診斷). Authored 2026-06-28. Second of the three planned
> contracts (ADR 0004 / system-architecture spec §contracts). Companion to a plan written
> only after the design decision below is approved.

## 1. Goal

Make the **indexer query API** (the HTTP seam between `apps/ocs-indexer`, the producer, and
`apps/api`, the consumer) a **single source of truth** so the request/response shapes cannot
drift — the same class of bug contract #1 (`packages/ocs-contract`) fixed for the OCS document.

## 2. Current state (the drift surface)

The same wire shapes are **hand-maintained twice**:

- **Producer** — `apps/ocs-indexer/src/jd_ocs_indexer/api/schemas.py`: pydantic models used as
  FastAPI `response_model=` (so FastAPI already emits an OpenAPI 3.1 spec for them):
  `SearchRequest, OccupationSearchResponse/OccupationHit, TaskSearchResponse/TaskHit,
  OccupationDetail/OcsName/CodeName, OccupationTasks/UnitTasks/TaskRef,
  CompetencyPool/CitableItem/SourceRef, TasksResponse/TaskDetail, FindSimilarResponse,
  HealthResponse, StatsResponse`.
- **Consumer** — `apps/api/app/core/knowledge_dto.py` (post-Phase-3a): a **near-duplicate**
  pydantic set (`OccupationDetail, OccupationTasks, CompetencyPool, OccupationSearchResponse,
  TaskSearchResponse, CodeName, OcsName, CitableItem, SourceRef, …`) returned by
  `KnowledgePort` (`core/ports.py`) and parsed by `HttpIndexerClient`
  (`adapters/knowledge_http.py`).

**Drift evidence / risk:**
- Two independently authored model sets for one wire contract — exactly the "code-first
  synchronisation" problem the sources call out.
- The consumer's `_Base` sets `extra="ignore"`, so a **new producer field is silently dropped**
  on the consumer side; a **renamed field** silently becomes its default. No build-time signal.
- Already slightly out of step (e.g. `hits` is required on the producer, `default_factory=list`
  on the consumer). Harmless today, but it shows the two drift independently.

**Scope of the seam** the api actually consumes (`HttpIndexerClient` methods): `POST
/occupations/search`, `POST /tasks/search`, `GET /occupations/{code}`, `GET
/occupations/{code}/competencies`, `GET /occupations/{code}/tasks`, `GET /healthz`. The indexer
also exposes `tasks/batchGet`, `tasks/findSimilar`, `stats` (not currently called by api).

**Decisive distinguishing fact:** this seam is **Python → Python, one producer, one consumer**.
The web frontend never calls the indexer (it calls `api`, which calls the indexer). So — unlike
contract #1 — there is **no non-Python consumer** forcing a language-neutral schema.

## 3. Authoritative sources & what they prescribe

| Source | Authority | Prescription relevant here |
|---|---|---|
| FastAPI — *Generating Clients / SDKs* (official) | Framework owner | FastAPI is OpenAPI-native; generate clients from the spec so a backend change is reflected (or errors out) in the client — single source of truth, drift caught on regenerate. |
| Malt Engineering — *Contract-First API with FastAPI & OpenAPI* | Practitioner case study | "Code-first" (hand-written models on both ends) causes synchronisation issues; a committed contract + generation removes them. |
| Speakeasy — *Pact vs OpenAPI*; TotalShiftLeft — *API Contract Testing (2026)* | Contract-testing references | **Internal services → schema-first OpenAPI** (lean, low setup, spec already exists). **Consumer-driven Pact → partner-facing/external** APIs where hidden consumer deps must be made visible. Strongest setups combine schema validation + a lean integration test. |
| ADR 0004 (this repo) — contract-first `ocs-contract` | Local precedent | #1 chose **JSON-Schema + codegen** *because* of the TS/web consumer + language neutrality + the OCS document being a real-world standard. Those forces are **absent** for #2. |

**Convergent conclusion.** For an internal, single-consumer, Python↔Python RPC seam, full
consumer-driven contract testing (Pact) is overkill, and JSON-Schema+dual-codegen (the #1
recipe) buys language-neutrality we don't need. The leanest drift-proof options are a **shared
typed package** or **OpenAPI-first client generation**.

## 4. Design options

### Option B — Shared pydantic contract package `packages/indexer-contract` (recommended)
One pydantic module of the wire models, imported by **both** ends: the indexer uses them as
FastAPI `response_model`/request bodies; the api's `KnowledgePort` returns them and
`HttpIndexerClient` parses them. **Zero codegen, zero drift — literally the same classes.**
Distributed as a per-app editable **path dependency**, exactly like `ocs-contract` already is
(ADR 0005). `api/schemas.py` and `core/knowledge_dto.py` collapse into this package
(`core/knowledge_dto.py` → thin re-export or removed; `core/ports.py` imports from the package).
- ➕ Simplest; impossible to drift; no regen/CI machinery; matches the existing path-dep pattern.
- ➖ Couples both services to one pydantic major version (already true via `ocs-contract`); only
  works while both ends are Python (true now and for the foreseeable future).

### Option A — OpenAPI-first codegen (alternative)
Commit the indexer's generated `openapi.json`; generate the api's consumer DTOs/client from it
(`datamodel-code-generator` OpenAPI input, or `openapi-python-client`). CI regenerates + `git
diff` guards (like `ocs-contract/scripts/check-codegen.sh`).
- ➕ Producer's models stay authoritative; consumer can be any language later; decoupled evolution.
- ➖ Adds codegen tooling + a regen step + spec-export step, for language-neutrality we don't
  currently need. More moving parts than B.

### Option C — JSON-Schema-first, mirroring contract #1 (for consistency)
Author standalone JSON schemas for the query API; codegen pydantic for both ends.
- ➕ Symmetric with `ocs-contract`; language-neutral.
- ➖ Heaviest authoring (schemas separate from FastAPI models); no non-Python consumer justifies
  it. Over-engineered for this seam.

**Recommendation: Option B.** It is the YAGNI-correct, truly-zero-drift choice for an internal
Python↔Python seam with a single consumer, and it reuses the established `ocs-contract`
path-dependency pattern. Option A is the right escalation **if/when** a non-Python consumer of
the indexer appears (then promote the shared models' shapes to an OpenAPI/JSON-Schema artifact).

## 5. Safety net & method (if Option B approved)
- **Net:** both test suites — `api` (86 passed) and `ocs-indexer` (41 passed). Move-only model
  consolidation → green-before == green-after.
- **Method:** (1) create `packages/indexer-contract` with the wire models (verbatim);
  (2) ocs-indexer `api/schemas.py` imports them (keep request-only models there if preferred);
  (3) api `core/knowledge_dto.py` → re-export shim then rewire importers to the package;
  `core/ports.py` imports the package; (4) both suites green; (5) ADR 0010 + tag. One commit per
  side.
- **Risk:** pydantic version skew between the two app locks — mitigated by pinning the package's
  pydantic floor compatibly (both already run pydantic v2); verified by both suites importing it.

## 6. Out of scope
Contract #3 (api/web authored-document) — separate record/plan next; live runtime cutover;
adding new indexer endpoints; Pact/CDC test infrastructure (revisit only for an external
consumer).
