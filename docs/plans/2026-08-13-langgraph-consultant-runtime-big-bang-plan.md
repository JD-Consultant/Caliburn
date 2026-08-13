# LangGraph Consultant Runtime Big-bang Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Every task starts with a failing behavior test and ends with its own commit.

**Goal:** 以 LangChain／LangGraph 成熟元件直接取代 current AI／document-state 自寫機制，交付一條可保存、可恢復、可看進度、可按需分析 Task／Duty／OPKS、可審核文件變更並可匯出的專業職務顧問產品流程。

**Prerequisite:** ADR 0060 必須由 owner 明確改為 Accepted；未核准前不得執行 production 變更。

**Architecture:** 新建 `app/consultant` purpose-first runtime。LangGraph PostgreSQL Saver 是訪談與核准 artifact 唯一 semantic-state owner，Store 是員工原話／更正／quote／reference 唯一 source owner；LangChain bounded agent、middleware、OpenRouter binding 與獨立 `SkillsMiddleware` 承接 model loop、context 與 Task／Duty／O／P／K／S 方法。API 以 generated contract＋typed SSE 投影 durable state；Web 不重算 policy。完成 vertical slice 後一次硬切並移除舊 writer，沒有 compatibility adapter 或雙寫期。

**Tech Stack:** Python 3.13、FastAPI 0.141.x candidate、LangChain 1.3.15、LangGraph 1.2.11、`langgraph-checkpoint-postgres` 3.1.0、`langchain-openrouter` 0.2.7、Deep Agents 0.7.5（只取 Skills middleware）、PostgreSQL 16、Pydantic 2、JSON Schema codegen、Next／React、TanStack Query、pytest／Vitest。

**Spec:** [`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §0–§8、§9.12；ADR 0060；Task／Duty／OPKS 分析方法仍以該研究稿列出的 repo 研究為準。

## Global constraints

- 效果與功能完整優先；不以 LOC 或刪碼量縮小產品。
- 不移植 `*_spike.py`；probe 只能作 behavior evidence。
- 不 import、wrap、呼叫或雙寫現行 `core`／`task_analysis`／`opks`／`consultation` AI writer。
- 新舊可在 branch 內暫時共存以保持 commits 可測，但 production composition root 只能在 final cutover 前指向舊系統、final cutover 後只指向新系統。
- LLM 產生且準備進正式文件的內容，一律進 review queue；只有 accept／edit-accept command 能改核准 artifact。
- 必要澄清使用 blocking interrupt；一般 Gap 與文件 review 不阻塞訪談。
- Provider call 不持有 DB transaction；framework node 的外部副作用要 idempotent。
- 本計畫不做正式模型品質 eval、不接 RAG、不做 multi-agent／subagent／shell／Agent Server。
- 一個 task 一個 commit；每次動手前確認 `pwd` 與 branch；不 push／merge。

## Replace／Delete／Retain ledger

| 類別 | 範圍 |
|---|---|
| Replace | provider wire、durable turn、context builders、question target／scheduler、Work Model／Focus／Progress／Proposal／Current JD 的 persistence lifecycle、同步 consultation transport |
| Delete at cutover | `app/core` 舊 state／authority／domain writers、`app/task_analysis`、`app/opks`、`app/consultation`、舊 OpenRouter adapter、舊 document authoring writers、對應 tables／migrations／routes／DTO／Web hooks／tests |
| Retain concept, reimplement thinly | Task／Duty／O／P／K／S 分析方法、source／quote／correction、employee authority、read-set／stale、deterministic verifier、readiness、XLSX export、document catalog、多文件隔離 |
| Retain code if boundary-clean | XLSX renderer、純 readiness／position-code 規則、通用 API problem mapper、database bootstrap；必須改吃新 projection，且不得 import 舊 state |
| Out of scope | `apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 RAG contracts；維持 ADR 0057 隔離 |

---

### Task 1: Pin framework stack and pass the FastAPI/SSE compatibility gate

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/uv.lock`
- Create: `apps/api/tests/test_native_sse_compatibility.py`
- Modify only if required by FastAPI: `apps/api/app/app_factory.py`, existing route tests

- [ ] Write a failing test with a minimal typed SSE endpoint. Assert JSON `data`, `event`, `id`, heartbeat headers, disconnect-safe completion and `Last-Event-ID` parsing; also retain the current `/healthz` and problem-response tests.
- [ ] Add exact dependencies: LangChain 1.3.15, LangGraph 1.2.11, Postgres checkpointer 3.1.0, `langchain-openrouter` 0.2.7 and Deep Agents 0.7.5. Upgrade FastAPI to 0.141.1 candidate and let `uv lock` resolve compatible Starlette／httpx.
- [ ] Run the entire API suite, not only SSE. If FastAPI 0.141.1 fails an existing contract, diagnose once; if the fix would alter product semantics, revert only FastAPI and use current FastAPI＋`StreamingResponse`. Do not add `sse-starlette` or Agent Server.
- [ ] Verify imports and exact versions; commit `build: add consultant runtime framework stack`.

### Task 2: Establish one durable document authority with framework-owned persistence

**Files:**
- Create: `apps/api/app/consultant/__init__.py`
- Create: `apps/api/app/consultant/state.py`
- Create: `apps/api/app/consultant/graph.py`
- Create: `apps/api/app/consultant/policy.py`
- Create: `apps/api/app/consultant/views.py`
- Create: `apps/api/app/adapters/langgraph/__init__.py`
- Create: `apps/api/app/adapters/langgraph/postgres.py`
- Create: `apps/api/tests/test_consultant_authority_postgres.py`
- Add/modify: current-only migration files and DB setup script for a minimal catalog plus framework tables

- [ ] Start with PostgreSQL tests for create/reopen/delete, immutable source＋correction, checkpoint restart, same-thread stale writers, direct edit, export projection, additive state evolution and linear storage growth. Assert there is no second writable artifact table.
- [ ] Define purpose-first typed state: interview units, issue queue, evolving understanding with source refs, review queue, approved artifact, required input and operation status. These are a new production contract, not wrappers around old classes.
- [ ] Use `AsyncPostgresSaver`／`AsyncPostgresStore`; catalog stores only document metadata and thread pointer. Add idempotent setup／cleanup and one-process per-document run admission.
- [ ] Keep provider calls absent in this task. All transitions deterministic; make crash windows explicit and rerunnable.
- [ ] Run focused PostgreSQL tests and migration-from-empty DB; commit `feat: establish durable consultant authority`.

### Task 3: Move professional analysis into bounded agent, Context and Skills

**Files:**
- Create: `apps/api/app/consultant/agent.py`
- Create: `apps/api/app/consultant/context.py`
- Create: `apps/api/app/consultant/models.py`
- Create: `apps/api/app/consultant/verification.py`
- Create: `apps/api/app/consultant/skills/{task,duty,opks-o,opks-p,opks-k,opks-s}/SKILL.md`
- Create: `apps/api/app/adapters/openrouter/langchain.py`
- Create: `apps/api/tests/test_consultant_agent.py`
- Create: `apps/api/tests/test_consultant_context_and_skills.py`

- [ ] With a deterministic tool-capable fake model, prove model profile replacement, structured result, usage/error mapping and hard limits: at most 3 model calls, 1 Skill read per selected Skill and 2 source lookups.
- [ ] Convert the already researched Task／Duty／OPKS methods—not old prompt wrappers—into six independently eligible Skills. Test that Task need not stabilize before OPKS, multiple Skills may compose in one turn, and ineligible Skill content never enters context.
- [ ] Build minimal-sufficient context middleware: current interview unit and reason, relevant understanding／Gap, approved artifact slice, active corrections, recent natural dialogue and source IDs. Older original wording stays in Store until allowlisted lookup.
- [ ] Require a Context Manifest and source dependency in typed output; verifier rejects unauthorized source／Skill IDs, invalid quote anchors and unsupported official-document operations.
- [ ] No paid model call in the gate. Commit `feat: add bounded consultant agent and skills`.

### Task 4: Implement dynamic consultation and the three employee interaction channels

**Files:**
- Modify: `apps/api/app/consultant/graph.py`, `policy.py`, `state.py`, `views.py`
- Create: `apps/api/app/consultant/operations.py`
- Create: `apps/api/app/consultant/review.py`
- Create: `apps/api/app/consultant/clarification.py`
- Create: `apps/api/tests/test_consultant_product_flow.py`
- Create: `apps/api/tests/test_consultant_review_and_clarification.py`

- [ ] Recreate the approved employee scenario as production behavior tests: simple work map, one clear focus, side clue remains visible, defer／return, Task／Duty／OPKS dynamic revision, source correction selectively reopens affected work.
- [ ] Project semantic progress as coverage／depth／decision／concrete Gap and reason; never expose tool-call progress or percentage.
- [ ] Support multiple reviewable grouped operations across Duty／Task／OPKS with stable IDs and path read-set. Test accept, edit-accept, reject, defer, out-of-order decisions, direct-edit conflict and atomic stale rejection.
- [ ] Add typed required-clarification interrupt with reason, current understanding, choices and affected branch. Answer is new employee evidence; it must not accept a document operation. Only dependent branch blocks when another safe interview unit exists.
- [ ] Verify provider execution is outside DB transactions and every semantic update is one checkpoint. Commit `feat: implement adaptive consultant product flow`.

### Task 5: Replace the cross-language contract and API transport

**Files:**
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Regenerate: contract Python／TypeScript outputs
- Create: `apps/api/app/api/routes/consultant.py`
- Create: `apps/api/app/api/consultant_mapper.py`
- Modify: `apps/api/app/api/router.py`, `deps.py`, `app_factory.py`
- Create/modify: API contract and route tests

- [ ] Define new commands/views/events in JSON Schema: catalog, interview focus/reason, visible work units, semantic progress and Gap, messages, review operations, required clarification, approved artifact, readiness and durable operation snapshot. Do not preserve old DTO fields as deprecated aliases.
- [ ] Add endpoints for create/read/delete, submit employee answer (202＋operation ID), read durable snapshot, typed SSE, review decision, clarification answer, direct edit and export.
- [ ] Enforce command idempotency, payload hash, document scope and dirty/stale errors. SSE is a projection only and never owns business state.
- [ ] Run codegen zero-diff check, schema tests and entire API suite; commit `feat: expose consultant runtime contract and stream`.

### Task 6: Deliver the employee-facing consultant workspace

**Files:**
- Rewrite: `apps/web/src/app/workspace/[document_id]/**`
- Create/modify: `apps/web/src/features/consultant/**`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`, query layer and tests
- Retain/adapt: document editor and export components only where they consume the new generated contract cleanly

- [ ] Write UI tests for the employee journey: opening explanation, current focus and reason, work-map／Gap progress, answering while reviews remain pending, multiple review cards, edit-accept／reject／defer, blocking clarification card, reconnect and dirty-editor protection.
- [ ] Use `EventSource` to invalidate/refetch durable snapshots. Missing intermediate events must not lose accepted/waiting/completed/failed state.
- [ ] Keep approved artifact directly editable and clearly separate AI understanding, pending document changes and official content.
- [ ] Run web test／typecheck／lint; commit `feat: deliver adaptive consultant workspace`.

### Task 7: Preserve export, hard-cut old mechanisms and update architecture docs

**Files:**
- Adapt: `apps/api/app/export/**`, `apps/api/app/adapters/xlsx/**`, readiness policy and tests
- Delete: old AI／state modules listed in the ledger, obsolete tests, tables／migrations, routes, DTO and Web plumbing
- Modify: `ARCHITECTURE.md`, `AGENTS.md`, `docs/design/**`, `docs/runbook.md`, dependency guards

- [ ] First add characterization tests proving the new approved artifact preserves required iCAP XLSX semantics and deterministic position codes；另以新 behavior test 固定單一匯出流程：先揭露具體缺口，再允許員工明確強制匯出，且不得接受待審變更、補值或隱藏孤立 Task。
- [ ] Switch composition root to the new runtime; delete old writers in the same task. `rg` and AST guards must prove production cannot import them and no old table is written.
- [ ] Rewrite current-only migrations for a fresh DB: minimal catalog＋framework persistence only. Do not migrate, dual-write or retain old data compatibility.
- [ ] Remove now-unused dependencies and regenerate lockfiles. Update design docs in the same commit as the seam change.
- [ ] Run API／Web／contract／turbo gates; commit `refactor: hard-cut to consultant runtime`.

### Task 8: Final product verification, one smoke and handoff

**Files:**
- Create: `docs/specs/2026-08-13-consultant-runtime-upgrade-completion.md`
- Modify only for verified corrections discovered by final review

- [ ] Run fresh-DB migrate and all deterministic gates: API, Web test／typecheck／lint, contract codegen, turbo, dependency guards and `git diff --check`.
- [ ] Manually simulate one procurement employee session through the real UI with a configured OpenRouter model: establish work map, deepen one focus, discover a side Gap, generate and defer a document patch, answer a required clarification, edit-accept, reopen after correction, export. This is a smoke, not an eval; record model/profile/usage and observed failures without quality claims.
- [ ] Perform one concise external review against ADR 0060 and the product-flow research. Fix confirmed P1/P2 findings; do not start a framework redesign for speculative improvements.
- [ ] Record exact commands, expected known failures and Replace/Delete/Retain closure. Create local tag `consultant-runtime-v1`; keep branch/worktree unmerged and unpushed for owner review.

## Final gate

The upgrade is complete only when the employee can see the present interview purpose and real gaps, the system remembers earlier wording and corrections, Task／Duty／OPKS methods load on demand, all LLM document text is reviewable before becoming official, urgent ambiguity asks first, restart preserves state, direct edit/export remain consistent, and no old writer or compatibility layer remains. Passing framework tests alone is insufficient.
