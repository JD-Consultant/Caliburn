# LangGraph Consultant Runtime Big-bang Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 LangChain／LangGraph 成熟元件直接取代 current AI／document-state 自寫機制，交付一位可自然續談、記得員工原話、動態選擇訪談重點、按需分析 Task／Duty／O／P／K／S、呈現可信缺口、讓員工審核所有 LLM 文件內容並可靠匯出的專業職務顧問。

**Prerequisite（已滿足）:** Owner 於 2026-08-14 完成產品方向／成熟元件覆蓋審核後授權施工，ADR 0060 已改為 Accepted。

**Architecture:** 新建 `app/consultant` purpose-first runtime。LangGraph PostgreSQL Saver 是可修訂理解、動態訪談工作、缺口、待審文件變更與核准文件的唯一 semantic-state owner；Store 是員工原話／更正／quote 的唯一 source owner。LangChain bounded agent、middleware、OpenRouter binding，以及 Deep Agents `SkillsMiddleware`＋read-file-only middleware 承接 model loop、最小充分 context 與專業方法。API 以 generated contract＋typed SSE 投影 durable state；完成垂直切片後一次硬切並刪除舊 writer，不做 compatibility adapter 或雙寫。

**Tech Stack:** Python 3.13、FastAPI 0.141.1、HTTPX 0.28.1、LangChain 1.3.15、LangGraph 1.2.11、`langgraph-checkpoint-postgres` 3.1.2、`langchain-openrouter` 0.2.7、Deep Agents 0.7.5（只取 Skills＋read-only file middleware）、PostgreSQL 16、Pydantic 2、JSON Schema codegen、Next／React、TanStack Query、OpenTelemetry、pytest／Vitest。版本已於 2026-08-14 以官方 PyPI 指定版本端點確認存在且未被 yank；兩個 Beta integration 必須有窄介面 canary。

**Spec:** [`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §0–§8、§9.12–§9.13；[ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)；Task／Duty／OPKS 方法依研究稿 §10 所列 repo 研究。

## Global constraints

- 效果、功能完整與員工體驗優先；不以 LOC 或刪碼量縮小產品。
- 不移植任何 `*_spike.py`；probe 只作 behavior evidence。
- 不 import、wrap、呼叫或雙寫現行 `core`／`task_analysis`／`opks`／`consultation` AI／document writer。
- 新 target code／schema 不得出現 `WorkModel`、`Focus`、`Progress`、`Agenda`、`Proposal`、`CurrentJd` 等舊元件名稱；它們只可出現在 migration／delete guard／歷史文件。
- 凡 LLM 產生且準備進職務文件的內容，一律進 framework-backed review queue；只有 accept／edit-accept command 能改核准文件。員工 direct edit 直接依員工 authority 提交。
- 第一版 LLM 可處理職務名稱、工作描述、Duty、Task、分組、排序及 O／P／K／S；不得輸出能力級別、A 或任何官方代碼。能力級別與 A 的既有欄位、direct edit 與 export 必須保留。`職業別`／`行業別` 名稱與分類代碼可由員工直接填寫；iCAP 配發的 `職能基準代碼`／`職類別代碼` 對員工與模型都不可編輯並維持空白。
- 理解校準、文件 changeset review、必要澄清與一般 Gap 是不同互動；只有依賴未決結構／重大歧義的分析分支會 blocked。
- 員工可隨時停止傳訊息或關頁；不得新增 pause／finish interview command。重新開啟時恢復 durable view。
- Provider call 不持有 DB transaction；framework node 的外部副作用必須 idempotent。
- 本計畫不做正式模型品質 eval、不接 RAG／Reference、不做 multi-agent／subagent／shell／Agent Server。RAG 維持 ADR 0057 隔離，日後另案。
- 同文件員工原話／更正的 stable-ID、lineage、lexical／semantic Store lookup 是必要記憶能力，不算公版 RAG；只能查 employee-source namespace，不能接 ADR 0057 bounded context、外部 corpus 或預建 Reference source type。
- 一個 task 一個 commit；每次動手前確認 `pwd` 與 branch；不 push／merge。

## 每個 Task 都必做的北極星回歸 gate

Big-bang 只代表最後一次硬切，不允許累積十個 Task 後才發現方向跑掉。每個 Task／可獨立功能在 commit 前都要更新 [`2026-08-14-consultant-runtime-north-star-audit-ledger.md`](../specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md)，逐項回答：

1. 員工實際多了什麼可觀察效果；是否仍是一位自然續談、AI 帶路但員工可改道的專業顧問？
2. 哪個成熟 framework primitive 承接了通用機制；有沒有無證據地重寫 framework 已提供的 persistence、routing、memory、context、retry、structured output、HITL 或 streaming？
3. 剩下的自寫部分是否真的是職務分析方法、員工 authority、來源／quote、文件 invariant、reason code 或 UX policy；若不是，先找成熟 primitive 再繼續。
4. LLM 是否仍無法直接改核准文件；文件審核、理解校準、required clarification 與一般 Gap 是否仍分流？
5. 是否仍保留完整員工回答、最新更正與全域旁支，同時只傳最小充分 context；是否出現摘要取代來源或 Skill 固定流水線？
6. 是否誤加 pause／finish、假百分比、能力級別／A 生成、RAG consumer、multi-agent、第二 authority、舊名稱 compatibility 或 silent fallback？
7. 本 Task 新增什麼測試／命令證明以上結論；若有更好的產品方法，是否已先與 owner 討論並更新研究／ADR？

任何一題不通過就停止下一個 Task。帳本與功能在同一 commit 更新，讓 `git log` 能回查每次方向審核。

## Replace／Delete／Retain ledger

| 類別 | 範圍 |
|---|---|
| Replace | provider wire、durable turn、context builders、question target／scheduler、舊 Work Model／Focus／Progress／Proposal／Current JD persistence lifecycle、同步 consultation transport |
| Delete at cutover | `app/task_analysis/**`、`app/opks/**`、`app/consultation/**`、`app/core/**` 舊 state／domain writers、舊 OpenRouter adapter、舊 authoring writers、對應 PostgreSQL models／repositories、routes／mappers、DTO、Web hooks／components 與拓撲 tests |
| Retain semantics, implement through framework | Task／Duty／O／P／K／S 方法、員工來源／更正／quote、employee authority、read-set／stale、deterministic verifier、可解釋 sufficiency、文件欄位 invariant |
| Retain code only after dependency audit | XLSX renderer、純 readiness／position-code 規則、通用 API problem mapper、database bootstrap；必須只讀新 projection，且不得 import 舊 state |
| Out of scope | `apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、RAG contracts／consumer；能力級別與 A 的 LLM 分析／Skill；正式模型品質 eval |

---

### Task 1: Pin framework stack and prove transport compatibility

**Files:**

- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/uv.lock`
- Create: `apps/api/tests/test_native_sse_compatibility.py`
- Modify only if required: `apps/api/app/app_factory.py`, `apps/api/tests/test_app_wiring.py`

**Produces:** A locked framework stack and a verified typed-SSE path without changing product behavior.

- [x] Write a failing SSE compatibility test that creates a minimal endpoint and asserts `event`, JSON `data`, stable `id`, heartbeat, disconnect-safe completion, `Last-Event-ID` parsing, `/healthz`, and existing RFC 9457 responses.
- [x] Run `uv run pytest tests/test_native_sse_compatibility.py -q`; expect failure because the target FastAPI/framework versions are not installed.
- [x] Pin LangChain 1.3.15, LangGraph 1.2.11, `langgraph-checkpoint-postgres` 3.1.2, `langchain-openrouter` 0.2.7 and Deep Agents 0.7.5. Upgrade FastAPI to stable 0.141.1 and HTTPX to stable 0.28.1, resolve Starlette with `uv lock`; assert the lock contains these exact, non-yanked distributions.
- [x] Run the SSE test and entire API suite. If FastAPI 0.141.1 breaks an existing product contract, capture the exact failure, revert only FastAPI, and implement SSE with current FastAPI＋`StreamingResponse`; do not add `sse-starlette` or Agent Server.
- [x] Add narrow import／behavior canaries for the Beta `langchain-openrouter` and `SkillsMiddleware`＋`FilesystemMiddleware(tools=["read_file"])`; prove only `read_file` is exposed and no host filesystem／write／delete／shell／subagent／todo tool enters the agent.
- [x] Verify exact imported versions, run the common north-star gate, append the Task 1 ledger entry and commit `build: add consultant runtime framework stack`.

### Task 2: Establish framework-owned durable source and document state

**Files:**

- Create: `apps/api/app/consultant/__init__.py`
- Create: `apps/api/app/consultant/state.py`
- Create: `apps/api/app/consultant/graph.py`
- Create: `apps/api/app/consultant/views.py`
- Create: `apps/api/app/adapters/langgraph/__init__.py`
- Create: `apps/api/app/adapters/langgraph/postgres.py`
- Create: `apps/api/scripts/setup_consultant_storage.py`
- Create: `apps/api/tests/test_consultant_durable_authority_postgres.py`
- Create during branch construction: `apps/api/alembic/versions/0018_consultant_runtime_catalog.py` (`down_revision = "0017"`)
- Rewrite the same 0018 revision at cutover as the fresh `down_revision = None` root after removing 0012–0017

**Interfaces:**

- Produces `ConsultantThreadState`, `EmployeeSource`, `InterviewWorkItem`, `UnderstandingItem`, `DocumentChangeSet`, `ApprovedJobDocument`, `RequiredClarification`, `RunReceipt` and `ConsultantSnapshot`.
- `AsyncPostgresStore` owns complete `EmployeeSource` payloads; `ConsultantThreadState` stores only source IDs／lineage.
- 第一版只有已保存的 employee turn 與 employee direct edit 能成為工作事實來源；每筆來源保存 stable ID、原文、speaker＝employee、quote／position anchor、建立時間、修訂／取代 lineage 與 validity。模型輸出、accept／reject／defer 等審核事件不是新事實來源。

- [x] Write PostgreSQL tests for create／reopen／delete, immutable input＋correction, same-ID hash conflict, pending-source reconciliation, checkpoint restart, stale same-thread writers, direct edit, quote-anchor lookup, superseded-source validity, export projection, additive schema evolution and linear storage growth. Assert no second writable artifact table exists.
- [x] Add source-authority tests proving model text and accept／reject／defer decisions cannot mint evidence; an employee edit creates a direct-edit source only for the text the employee actually changed. Reject unknown source kinds so a future Reference source cannot be enabled accidentally.
- [x] Run the focused tests and confirm they fail because the framework-owned state does not exist.
- [x] Define purpose-first typed state. Do not create fields or classes named after the old Work Model／Focus／Progress／Proposal／Current JD components.
- [x] Implement `AsyncPostgresSaver`／`AsyncPostgresStore`, minimal document catalog, idempotent framework storage setup and one-process per-document admission. Set `LANGGRAPH_STRICT_MSGPACK=true` or an explicit module allowlist; use application-issued UUID namespaces; if connections are manual, enforce `autocommit=True`＋`row_factory=dict_row`. Provider calls remain absent.
- [x] Add security／setup tests for strict deserialization, `.setup()` rerun, connection options and cross-document namespace isolation.
- [x] During branch construction, add 0018 incrementally above 0017 so every task stays runnable. Replace migrations 0012–0017 only at the final hard cut and rewrite 0018 as the fresh root (`down_revision = None`). The new root creates catalog only; the setup script initializes framework tables idempotently.
- [x] Run focused PostgreSQL tests plus fresh-DB Alembic／framework setup, run the common north-star gate, append the Task 2 ledger entry and commit `feat: establish durable consultant state`.

### Task 3: Implement model profile, receipts and minimal-sufficient context

**Files:**

- Create: `apps/api/app/consultant/model_runtime.py`
- Create: `apps/api/app/consultant/context.py`
- Create: `apps/api/app/consultant/verification.py`
- Create: `apps/api/app/adapters/openrouter/langchain.py`
- Modify: `apps/api/app/config.py`
- Create: `apps/api/tests/test_consultant_model_runtime.py`
- Create: `apps/api/tests/test_consultant_context.py`

**Interfaces:**

- `ConsultantModelProfile` and `RunPolicy` resolve to immutable `ResolvedExecution`.
- Every provider attempt returns `AttemptReceipt` with requested／actual model, provider, effective parameters, usage, cost, latency, route and stop/error reason.
- LangChain context middleware augments the framework `ModelRequest` and emits a `ContextSelectionReceipt` plus bounded `GlobalOrientationIndex`; do not create a second durable context object.

- [x] Write fake-model tests for profile replacement, no per-Skill model switching, no silent fallback, actual route／usage receipt, parameter round-trip, budget enforcement and typed errors.
- [x] Write context tests proving every main inference contains a bounded global orientation index, current interview details, latest valid corrections, approved-document slice, concrete gaps, recent dialogue and source lookup handles. Assert old／superseded statements are never presented as current facts.
- [x] Add lookup tests for direct stable-ID／lineage access first, then lexical／configured semantic Store search for older employee wording. Do not add iCAP／Reference retrieval.
- [x] Implement OpenRouter binding with LangChain `create_agent`／`response_format`; use built-in `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、`ModelRetryMiddleware` and `ToolRetryMiddleware` for generic loop controls. Application policy still owns retry eligibility, total budget, idempotency and an attempt receipt for every actual call. `ModelFallbackMiddleware` stays off unless an explicit versioned allowlist policy records every attempted route.
- [x] Use `SummarizationMiddleware`／`ContextEditingMiddleware` only for non-authoritative recent dialogue copies and large read-only tool results. Tests must prove employee verbatim sources, latest correction, blocking contradiction, source lineage and approved-document slice are reloaded from Store／state and can never be replaced by a summary.
- [x] Emit LangChain callback／run metadata into the existing OpenTelemetry pipeline and local receipts; do not require LangSmith or remote prompt logging.
- [x] Require `ContextSelectionReceipt` to record loaded／omitted sources, reasons, revisions, Skills, token counts, profile and degraded sections. Run focused tests, run the common north-star gate, append the Task 3 ledger entry and commit `feat: add consultant model and context runtime`.

### Task 4: Convert professional methods into independently eligible Skills

**Files:**

- Create: `apps/api/app/consultant/agent.py`
- Create: `apps/api/app/consultant/results.py`
- Create: `apps/api/app/consultant/skill_backend.py`
- Create: `apps/api/app/consultant/skills/work-discovery/SKILL.md`
- Create: `apps/api/app/consultant/skills/story-interview/SKILL.md`
- Create: `apps/api/app/consultant/skills/task-boundary/SKILL.md`
- Create: `apps/api/app/consultant/skills/duty-grouping/SKILL.md`
- Create: `apps/api/app/consultant/skills/output/SKILL.md`
- Create: `apps/api/app/consultant/skills/performance-indicator/SKILL.md`
- Create: `apps/api/app/consultant/skills/knowledge/SKILL.md`
- Create: `apps/api/app/consultant/skills/skill/SKILL.md`
- Create: `apps/api/app/consultant/skills/completion-red-team/SKILL.md`
- Create: `apps/api/tests/test_consultant_agent_and_skills.py`

**Produces:** A typed `ConsultantResult` containing visible reply, understanding／interview-work deltas, concrete gaps, document changes, next question and sufficiency recommendation.

- [x] Write deterministic fake-model tests proving Task need not stabilize before OPKS, multiple Skills may compose in one turn, ineligible Skill content never enters context, and work discovery／story／completion methods are not hidden inside one giant Task prompt.
- [x] Add negative tests: no Reference Skill, no competency-level or A generation, no model-authored classification／iCAP codes, and no direct write to `ApprovedJobDocument`.
- [x] Add OPKS semantic tests: O／P remain Task-level, K／S remain document-level many-to-many; every active K／S has at least one valid employee source; O may remain empty when the employee gave no meaningful outcome／state／consequence／regulation, in which case the consultant challenges the Task boundary instead of fabricating an O.
- [x] Add anti-fabrication tests: without an anchored employee quote the model cannot introduce quantities, named laws／SOPs／rules, external-reference claims or vague pseudo-citations such as “依公司規定”; model authorship itself never satisfies an evidence requirement.
- [x] Add method-conformance tests from the accepted research: Story／Work Unit／Task are not one-to-one; Task requires action／object／meaningful outcome／current responsibility and is not merely a tool、step or one-off; Duty stays revisable and cannot become an early fixed box; K/S are inferred from concrete Task／story／O/P evidence rather than a leading “你需要什麼能力” question; K is noun-like, S is applied action, neither uses `ability to`／「具備…之能力」、empty degree adjectives or per-skill proficiency; P is observable and not a personality label.
- [x] Add completion-red-team tests covering routine-work omission, dramatic-story bias, other-person／past／one-off work, over-merge／over-split／duplicate Task, unsupported O/P/K/S and unresolved high-impact contradiction. One employee-facing turn still asks only one main question.
- [x] Convert the researched methods—not old prompt wrappers—into the nine Skills above. Each Skill states eligibility, required evidence, outputs, gaps, anti-hallucination rules and when to reopen another analysis direction.
- [x] Bind Skills through `SkillsMiddleware` and a shared `FilesystemMiddleware(tools=["read_file"])`. Implement only a traversal-safe, read-only `BackendProtocol` adapter over versioned `/skills` package resources; do not use host `FilesystemBackend` in the API. Load each selected Skill at most once and enforce at most three model calls and two lookup waves per interactive run.
- [x] Require source dependencies and allowed Skill IDs in typed output; verifier rejects unauthorized source／Skill IDs, invalid quote anchors and unsupported document change paths. Run focused tests, run the common north-star gate, append the Task 4 ledger entry and commit `feat: add professional consultant skills`.

### Task 5: Deliver adaptive interview, visible understanding and truthful sufficiency

**Files:**

- Modify: `apps/api/app/consultant/graph.py`, `state.py`, `views.py`
- Create: `apps/api/app/consultant/interview.py`
- Create: `apps/api/app/consultant/understanding.py`
- Create: `apps/api/tests/test_consultant_interview_flow.py`
- Create: `apps/api/tests/test_consultant_understanding_and_sufficiency.py`

**Produces:** Graph transitions and projections for dynamic interview work, persistent “AI 目前理解”, concrete gaps and advisory sufficiency.

- [x] Recreate the approved procurement scenario as behavior tests: initial navigation, broad work map, one clear interview focus, side clue remains visible, employee changes topic, Task／Duty／OPKS revise dynamically, and a correction selectively reopens affected work.
- [x] Test `UnderstandingProjection` and calibration triggers: always-available collapsible view; soft card after meaningful shift／long return; branch-blocking card only for contradiction, high-risk responsibility or structural premise. Actions are confirm, direct correction and later; confirmation never accepts document text.
- [x] Test semantic progress as coverage／depth／employee-decision／concrete gap with reason codes. Assert no percentage, tool-call progress, “本輪可停”, pause command, finish-interview state or required completion click exists.
- [x] Test sufficiency recommendation: deterministic evidence＋LLM explanation states why enough, remaining gaps and likely benefit of continuing; employee may keep chatting or leave, and new evidence recalculates it without requiring any session close／reopen lifecycle.
- [x] Implement graph routing／reducers／projections and natural close／reopen behavior. Run focused tests, run the common north-star gate, append the Task 5 ledger entry and commit `feat: implement adaptive consultant interview`.

### Task 6: Implement document review, structural dependency blocking and required clarification

**Files:**

- Create: `apps/api/app/consultant/document_review.py`
- Create: `apps/api/app/consultant/document_authority.py`
- Create: `apps/api/app/consultant/clarification.py`
- Modify: `apps/api/app/consultant/graph.py`, `state.py`, `views.py`
- Create: `apps/api/tests/test_consultant_document_review.py`
- Create: `apps/api/tests/test_consultant_clarification.py`

**Interfaces:**

- `DocumentChangeSet` contains stable patch actions, evidence, before／after, path read-set, dependencies and atomic subgroup IDs.
- Commands: `accept_changes`, `edit_and_accept_changes`, `reject_changes`, `defer_changes`, `direct_edit_document`, `answer_clarification`.

- [x] Write tests for multiple simultaneous review bundles, partial accept, edit-accept, reject, defer, out-of-order decisions, dependency-based atomic subgroups, direct-edit conflict, stale rejection and revalidation of remaining changes. Review state must distinguish pending／deferred／accepted／edit-accepted／rejected／stale, including employee edits／rejection reason and a presentable stale reason.
- [x] Assign every patch-action ID in application code when the changeset is created. Test deterministic replay keeps the same ID, stale／rejection matching uses stable ID＋path read-set rather than text similarity, and a rejected change is not silently proposed again without relevant new employee evidence.
- [x] Test that a review bundle is only a presentation unit: unrelated patch actions remain independently decidable, while a declared atomic subgroup is all-or-nothing because partial application would violate document invariants.
- [x] Test evidence effects separately from authority effects: accept／reject／defer changes review state but creates no work-fact source; edit-accept mints a direct-edit source only for the employee-authored delta; direct edit follows the same rule.
- [x] Test LLM changes across job name／work description／Duty／Task／order／reassignment／O／P／K／S. Assert competency level／A paths and every official-code path are rejected from model-authored patch actions. Employee direct edits may set competency level／A and `職業別`／`行業別` classification only; iCAP-assigned `職能基準代碼`／`職類別代碼` remain non-editable and blank.
- [x] Test structural review behavior: unresolved Duty create／merge／split or Task reassignment blocks only dependent branches; safe interview work continues; if none exists, projection explains which decision is needed. After decision, downstream changes／gaps／linkages are revalidated.
- [x] Add typed required-clarification interrupt with reason, current understanding, choices and affected branch. Its answer is new employee evidence and cannot accept a document changeset.
- [x] Implement deterministic authority commands and one semantic checkpoint per accepted decision. Verify provider calls stay outside DB transactions; run the common north-star gate, append the Task 6 ledger entry and commit `feat: add employee document authority`.

### Task 7: Replace cross-language contract and API transport

**Files:**

- Rewrite: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Regenerate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Regenerate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Create: `apps/api/app/api/routes/consultant.py`
- Create: `apps/api/app/api/consultant_mapper.py`
- Modify: `apps/api/app/api/router.py`, `deps.py`, `app_factory.py`, `problems.py`
- Create/modify: API contract and route tests

**Produces:** Framework-neutral commands, durable snapshots and typed SSE events; no legacy DTO aliases.

- [x] Define JSON Schema for catalog, current interview reason, understanding projection／calibration, visible work units, coverage／depth／decision／gap, advisory sufficiency, messages, document changesets／review decisions, required clarification, approved document, readiness and durable run snapshot.
- [x] Add endpoints for create／read／delete, submit employee answer (202＋run ID), read snapshot, typed SSE, review command, calibration／clarification answer, direct edit and export. Do not add pause／finish endpoints.
- [x] Test source-first admission: while an answer is pending／failed, a second AI interview answer is rejected with a typed recoverable problem; read, review, direct edit, export and delete remain available.
- [x] Enforce idempotency, payload hash, document scope, stale errors and untrusted client payloads. SSE only triggers refetch and never owns state.
- [x] Run contract schema tests, deterministic codegen check and entire API suite; run the common north-star gate, append the Task 7 ledger entry and commit `feat: expose consultant runtime contract`.

### Task 8: Deliver the employee-facing consultant workspace

**Files:**

- Rewrite: `apps/web/src/app/workspace/[document_id]/**`
- Create: `apps/web/src/features/consultant/**`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/shared/query/jobAnalysisQueries.ts`
- Retain/adapt: document editor and export components only when they consume the new generated contract cleanly

**Produces:** One persistent consultant workspace with natural continuation, visible understanding, truthful progress and separate employee interaction channels.

- [x] Write UI tests for first-use external-AI disclosure, opening navigation, current interview reason, collapsible “AI 目前理解”, soft／blocking calibration, concrete gaps, sufficiency advice, multiple editable review bundles, required clarification, reconnect and dirty-editor protection.
- [x] Test natural leave／return: after a completed reply, closing and reopening needs no pause／resume action; during processing, reopening shows completed or recoverable status without losing the employee input.
- [x] Keep understanding, pending LLM document changes and approved content visually distinct. Structural review may block dependent analysis but must not modal-lock unrelated work.
- [x] Use `EventSource` only to invalidate/refetch durable snapshots. Missing intermediate events must not lose accepted／waiting／completed／failed state.
- [x] Run Web tests, `npx tsc --noEmit` and lint; run the common north-star gate, append the Task 8 ledger entry and commit `feat: deliver consultant workspace`.

### Task 9: Preserve export, hard-cut old mechanisms and update architecture docs

**Files:**

- Adapt: `apps/api/app/export/**`, `apps/api/app/adapters/xlsx/**`, readiness policy and tests
- Delete: old AI／state modules listed in the ledger, obsolete tests, tables／migrations, routes／DTO and Web plumbing
- Create: `apps/api/alembic/versions/0018_consultant_runtime_root.py`
- Modify: `ARCHITECTURE.md`, `AGENTS.md`, `docs/design/**`, `docs/runbook.md`, dependency guards

- [ ] Add characterization tests proving the new approved document preserves all required XLSX fields and deterministic position codes, including manually editable competency level／A and employee-entered occupation／industry classification; iCAP-assigned code cells remain blank. Preserve O as optional, O／P as Task-level and K／S as document-level many-to-many rather than flattening them into per-Task duplicates.
- [ ] Add one-export behavior tests: reveal concrete gaps, allow explicit force export, and never accept pending changes, fabricate values, hide orphan Tasks or alter approved content.
- [ ] Switch composition root to the new runtime and delete old writers in the same task. AST／`rg` guards must prove production cannot import them, no old table remains writable, and new target modules／schema do not reintroduce banned legacy component names.
- [ ] Delete migrations 0012–0017 and install fresh root 0018; run migration on an empty database and assert only catalog＋framework persistence exist. No migration, dual-write or compatibility converter for old local data.
- [ ] Verify ADR 0057 still holds: no RAG package import、HTTP consumer、route、tool、compose default or contract dependency was introduced.
- [ ] Update architecture／runbook docs in the same commit; run API／Web／contract／turbo gates, run the common north-star gate, append the Task 9 ledger entry and commit `refactor: hard-cut to consultant runtime`.

### Task 10: Final product verification, one smoke and handoff

**Files:**

- Create: `docs/specs/2026-08-14-consultant-runtime-upgrade-completion.md`
- Modify only for confirmed P1／P2 corrections discovered by final review

- [ ] Run fresh-DB migration and every deterministic gate: API, Web test／typecheck／lint, contract codegen, turbo, dependency guards and `git diff --check`.
- [ ] Manually simulate one procurement session through the real UI with one configured OpenRouter model: establish work map, deepen one focus, capture side clue, inspect／correct AI understanding, generate and defer a changeset, resolve structural dependency, answer required clarification, edit-accept, reopen after correction, observe sufficiency advice, close／reopen naturally and force export with a visible gap.
- [ ] Record the versioned profile, resolved execution snapshot, actual attempt receipt／usage and observed failures. This is a smoke, not an eval; make no model-quality claim.
- [ ] Perform one concise external review against ADR 0060 and product-flow §9.13. Fix confirmed P1/P2 findings; do not redesign the framework for speculative improvements.
- [ ] Record exact commands, known failures and Replace／Delete／Retain closure. Run the common north-star gate, append the final Task 10 ledger entry, create local tag `consultant-runtime-v1`; keep branch/worktree unmerged and unpushed for owner review.

## Final gate

The upgrade is complete only when:

- the employee can see the present interview purpose, AI’s current understanding, real gaps and advisory sufficiency;
- closing the page never requires a pause／finish workflow and reopening restores the durable state;
- earlier employee wording and latest corrections remain retrievable without resending the entire history;
- work-discovery／story／Task／Duty／O／P／K／S／completion Skills load only when eligible;
- every LLM-authored document change is reviewable before becoming official, while competency level／A remain employee-editable but absent from LLM output;
- urgent ambiguity asks the employee first, structural uncertainty blocks only dependent branches, and ordinary gaps remain visible without becoming modals;
- restart、failure、direct edit、review、export and dirty-editor behavior remain consistent;
- no RAG consumer, old writer, legacy target component, compatibility layer or second authority remains.

Passing framework tests alone is insufficient.
