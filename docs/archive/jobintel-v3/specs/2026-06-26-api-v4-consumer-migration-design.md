# v3 Consumer Migration to Indexer API v4 (Resource-Oriented + Provenance)

**Date:** 2026-06-26
**Repo:** `s:\jobintel-ai` (v3 backend + frontend)
**Companion:** `S:\jd-ocs-indexer\docs\plans\2026-06-26-api-v4-resource-oriented.md` (indexer side — DONE, branch `dev`, 9/9 green)

## Goal

Switch the v3 consumer (backend `services/knowledge` + graph/REST call sites, and the
Next.js frontend) from the **old indexer query API** to the new **resource-oriented v4
surface**, propagating v4 naming end-to-end and surfacing K/S/O **provenance** in the UI.

This is the cross-repo item the indexer plan explicitly deferred ("v3 backend consumers
must switch to the new endpoints + `CitableItem`/URN shapes"). Re-ingest and dedup
merge/clustering remain out of scope (separate later increments).

## Authoritative v4 contract (consumed, not changed here)

From the implemented indexer (`src/jd_ocs_indexer/api/{schemas,routes}.py`):

| Method | Endpoint | Response |
|---|---|---|
| GET | `/occupations/{ocs_code}` | `OccupationDetail{ocs_code, urn, ocs_name{job_category_name,occupation_name}, job_categories/occupations/industries:[CodeName], job_description, ocs_level, attitudes:[CodeName], prerequisites:[str], supplements:[str]}` |
| GET | `/occupations/{ocs_code}/competencies` | `CompetencyPool{ocs_code, knowledge/skills/outputs/indicators/attitudes:[CitableItem]}` |
| GET | `/occupations/{ocs_code}/tasks` | `OccupationTasks{ocs_code, ocs_name, units:[UnitTasks{ocu_code,ocu_name,urn,tasks:[TaskRef{task_code,task_name,urn}]}]}` |
| POST | `/occupations/search` | `OccupationSearchResponse{hits:[OccupationHit{ocs_code,urn,ocs_name,job_description,ocs_level,score}]}` (body `{query, top_k}`) |
| POST | `/tasks/search` | `TaskSearchResponse{hits:[TaskHit{ocs_code,ocs_name,ocu_code,ocu_name,task_code,task_name,urn,score}]}` |
| POST | `/tasks/batchGet` | `TasksResponse{tasks:[TaskDetail{id,urn,...,competency_blocks:[dict]}]}` — **not used** (no endpoint surfaces point ids to feed it) |
| POST | `/tasks/findSimilar` | dedup pairs — **out of scope** |
| GET | `/healthz` | unchanged |

`CitableItem{id(URN), type(K|S|O|P|A), code, name?, text?, ocs_code, ocs_name,
sources:[SourceRef{ocu_code,ocu_name,task_code,task_name,competency_level}]}`.

URN scheme: occupation `ocs:{ocs_code}`, unit `ocs:{ocs_code}:U:{ocu_code}`,
task `ocs:{ocs_code}:T:{task_code}`, item `ocs:{ocs_code}:{K|S|O|P|A}:{code}`.

## Core forced change: task identity & per-task detail

The v4 surface returns a **Qdrant point id only from `batchGet`**; `OccupationTasks`,
`TaskHit`, and `CompetencyPool` carry no point id. Therefore:

1. **Task identity** shifts from point id → `(ocs_code, task_code)` / URN everywhere.
2. **Per-task K/S/O/indicators** are derived from the occupation's `/competencies`
   pool by **filtering CitableItems whose `sources[].task_code == task_code`** — there
   is no per-task detail endpoint the consumer can call (no point ids to feed `batchGet`).
   This replaces every `tasks_by_id` use.
3. `provenance.id` (catalog UUID/point id) in the OCS document is **dropped**. The
   document already stores `provenance.{ocs_code, task_id}`, which becomes the
   `(ocs_code, task_code)` key. `validate()`/export do not read `provenance`, so the
   exported OCS JSON contract is unaffected.

## Design decisions (approved)

- **Migration strategy:** full re-model to v4 shapes (not an adapter layer).
- **Frontend contract:** propagate v4 naming to the frontend (rename fields stack-wide).
- **Provenance depth:** rename + carry URN **and** surface provenance — render each
  K/S/O candidate's source `task_code`s in the UI (reusing the existing HeaderMetaPanel
  "共 N／來自：…" badge pattern).
- **`activity_examples`:** v4 task listings don't include it. Drop the activity-examples
  hint from the task-pool / `edit_tasks` curator. Indicators (P) remain available where
  they matter (draft-op, which fetches per task anyway).
- **findSimilar / dedup:** not wired; no client method added. Entirely deferred.
- **Execution:** single plan, **backend tasks first then frontend tasks** (natural
  dependency order), via superpowers:subagent-driven-development, strict TDD.

---

## Section 1 — Backend knowledge layer (`backend/app/services/knowledge/`)

### `models.py` — replace all models with v4 shapes
`extra="ignore"` retained (tolerate API evolution). New models mirror the indexer:
- `CodeName{code,name}`, `OcsName{job_category_name,occupation_name}`
- `SourceRef{ocu_code,ocu_name,task_code,task_name,competency_level}` (all optional)
- `CitableItem{id,type,code,name?,text?,ocs_code,ocs_name,sources:[SourceRef]}`
- `OccupationDetail`, `CompetencyPool`, `OccupationTasks`/`UnitTasks`/`TaskRef`,
  `OccupationHit`/`OccupationSearchResponse`, `TaskHit`/`TaskSearchResponse`.
- **Removed:** `Hit`, `SearchResult`, `Pair`, `Pairs`, `PoolTask/Unit/Group/TaskPool`,
  `ProfileMeta`, `TaskDetail`, `TasksByIdResult`.

### `base.py` (Protocol) + `http_client.py` — new methods
```
search_occupations(query, *, top_k=10) -> OccupationSearchResponse   POST /occupations/search
search_tasks(query, *, top_k=10)       -> TaskSearchResponse         POST /tasks/search
occupation(ocs_code)                   -> OccupationDetail            GET  /occupations/{code}
competencies(ocs_code)                 -> CompetencyPool             GET  /occupations/{code}/competencies
occupation_tasks(ocs_code)             -> OccupationTasks            GET  /occupations/{code}/tasks
healthz() -> bool                                                    GET  /healthz (unchanged)
```
Removed: `search`, `task_pool`, `pairs`, `profile`, `tasks_by_id`.

### New helper module `task_detail.py` (or function in `knowledge/`)
Pure function over a `CompetencyPool`:
```
task_competencies(pool: CompetencyPool, task_code: str) -> {
  "knowledge":[CodeName], "skills":[CodeName], "outputs":[CodeName], "indicators":[Indicator]
}
```
Filters `pool.{knowledge,skills,outputs,indicators}` to CitableItems whose
`sources[].task_code == task_code`; flattens to the consumer's existing `{code,name}` /
`{code,text}` shapes. Used by `ai.py` and `deep_nodes` to replace `tasks_by_id`.

---

## Section 2 — Backend graph + REST call sites

- **`graph_v3/nodes.py`**
  - `pick_profile`: `search_occupations(query)`. Candidate dicts now carry
    `ocs_name` (was `job_title`); resume-to-codes unchanged.
  - `build_task_pool`: call `occupation_tasks(code)` per selected code, merge into the
    proposed-task list. `_pool_to_tasks` reads `ocu_code/ocu_name/task_code/task_name`;
    `indexer_ref` becomes `{ocs_code, task_code}`. **Drop `activity_examples`.**
- **`graph_v3/curate_nodes.py`** `fetch_ksa_pool`: `competencies(ocs)`; map
  `knowledge/skills/attitudes` CitableItems via `_pairs_to_items` (reads `.name/.code`)
  and attach `sources` (task_codes) for provenance.
- **`graph_v3/deep_nodes.py`** `_prefill_from_catalog`: fetch `competencies(ocs_code)`
  for the task's `indexer_ref.ocs_code`, then `task_competencies(pool, task_code)` →
  outputs. No `tasks_by_id`, no `output_pairs`.
- **`api/routes/ai.py`**
  - `_catalog_ks` / `_catalog_op`: take `(ocs_code, task_code)` from the task's
    provenance, fetch `competencies`, derive K/S and outputs+indicators via
    `task_competencies`. (`_tasks.catalog_id` → new `_tasks.catalog_ref(task)` returning
    `{ocs_code, task_code}` from `provenance`.)
  - `_task_candidates` (extract-tasks grounding): from `occupation_tasks` per code,
    candidate id = `task_code` (was point id). `extract_tasks` service + result
    `suggested_task_ids` now hold task_codes.
- **`api/routes/documents.py`**
  - `task_candidates`: per-code `occupation_tasks` merged into groups; emit v4 field
    names `{ocs_code, ocs_name, units:[{ocu_code,ocu_name,tasks:[{task_code,task_name,urn}]}]}`.
  - `ocs_search`: `search_occupations`; emit `{ocs_code, ocs_name}`.
  - `header_meta` route: `occupation(code)` per code.
  - `ksa_pool`: `competencies(code)`; bucket items now include `sources`.
- **`services/header_meta.py`** `aggregate`: input is now `OccupationDetail` list;
  read `m.ocs_name.occupation_name` / `m.ocs_name.job_category_name` (were
  `m.job_title` / `m.job_category_name`). **Output shape unchanged** — it already emits
  `occupation_name`/`job_category_name` keys the frontend `HeaderMeta` type expects;
  only the attribute access on the input model changes.
- **`services/ocs_doc.py`**: `provenance` becomes `{ocs_code, task_code, urn}` (drop
  `id`, rename `task_id`→`task_code`); merge-on-recurate dedup keys on
  `(ocs_code, task_code)`. `build_from_picked` reads `task_code` from picked rows.

---

## Section 3 — Outward REST contract (v4 naming to the frontend)

Renamed response fields (frontend updated in lockstep, Section 4):
- task-candidates: `occupation_name`→`ocs_name`, `unit_id`→`ocu_code`,
  `unit_title`→`ocu_name`, `task_id`→`task_code`, drop `id`, add `urn`.
- ocs-search hits: `job_title`→`ocs_name`.
- ksa-pool & curate candidates: each item gains `sources: [task_code…]`.
- header-meta: `occupation_name` stays (already), sourced from `ocs_name`.
- build-tasks request (`PickedTask`): `task_id`→`task_code`, drop `id`.
- OCS document `provenance`: `{ocs_code, task_code, urn}`.

## Section 4 — Frontend (`frontend/src`)

- **`types/index.ts`**: update `OcsSearchHit{ocs_code,ocs_name}`, `CandidateTask{task_code,task_name,urn}`,
  `CandidateUnit{ocu_code,ocu_name,tasks}`, `CandidateGroup{ocs_code,ocs_name,units}`,
  `PickedTask{...,task_code}` (drop `id`), `OcsTask.provenance{ocs_code,task_code,urn}`.
  Provenance `sources?: string[]` go on a **display-only pool/candidate item type**
  (e.g. `KsaPoolItem extends CodeName`), NOT on the document-of-record `CodeName` written
  into `OcsDocument` — the of-record K/S/O items stay `{code,name}` only.
- **`lib/api.ts`** / **`lib/ocsDoc.ts`**: follow renamed fields.
- **`components/interview/v3/TaskCuratePanel.tsx`**: `g.ocs_name`, `u.ocu_code/ocu_name`,
  `t.task_code/task_title→task_name`; `alreadyIn`/`tkey` key on `(ocs_code, task_code)`;
  extract-tasks `byId` maps by `task_code`; remove `t.id` usage.
- **`components/interview/v3/InterruptHandlers.tsx`**: `ProfileCandidate.ocs_name`;
  `PoolTask.indexer_ref{ocs_code,task_code}`, drop `activity_examples` rendering in
  `TaskCurator`; `CurateList` renders source task_codes badge.
- **`components/interview/v3/CellFillerPanel.tsx`**: `Picker` candidates carry `sources`;
  render "共 N／來自：…" badge per K/S/O candidate.
- **`components/interview/v3/HeaderMetaPanel.tsx`**: already source-aware; adjust only if
  field names shift (`occupation_name` preserved).
- **Provenance UI:** reuse HeaderMetaPanel's badge (`共 {n}` + `title="來自：{task_codes}"`)
  on K/S/O candidate rows in `CellFillerPanel` and `CurateList`.

## Section 5 — Testing & out of scope

**Backend tests to rewrite/extend:**
`test_http_indexer_client.py` (new endpoints + parsing), `test_knowledge_models.py`,
new `task_competencies` helper test, `test_node_task_pool.py`, `test_curate_nodes.py`,
`test_deep_*` (prefill), `test_ai_*` (catalog K/S/O via competencies, extract-tasks
task_code ids), `test_documents_api.py` (task-candidates/ocs-search/header-meta/ksa-pool),
`test_ocs_doc.py` (provenance task_code), `header_meta` test. Suite must stay green.

**Frontend:** update any component/type tests touching the renamed fields; typecheck +
lint clean per `frontend/AGENTS.md` (read `node_modules/next/dist/docs/` before code).

**Out of scope (later, separate increments):**
- `/tasks/findSimilar` wiring + cross-repo dedup clustering/merge (`MergedTask`).
- Re-ingest of live Qdrant (destructive; requires explicit authorization; after consumer).
- Reranker for occupation search relevance.

## Risks / notes

- `task_competencies` fetches the whole occupation competency pool per task; fine for
  the interview's small selected-OCS set. Cache per `(profile, ocs_code)` if a call site
  loops many tasks (curate already caches the pool in state — reuse that).
- A task's `task_code` is unique within an occupation but could repeat across occupations;
  always pair with `ocs_code` (from `provenance`/`indexer_ref`).
- Custom/cherry-picked tasks have no catalog provenance → `task_competencies` yields
  empty, callers already degrade gracefully.
