# Current Application 功能模組化實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改 HTTP／JSON Schema／PostgreSQL／產品行為的前提下，移除歷史隔離容器 `app/job_analysis`，將現行 API 與 Web 整理成 ADR 0058 規定的功能模組。

**Architecture:** API 維持單一 FastAPI process、單一 PostgreSQL 與 authority transaction；第一層採 `core`、`documents`、`task_analysis`、`opks`、`consultation`、`export`，具體 IO 留在 `adapters`，HTTP 留在 `api`。Web 以 feature-first 整理，只有 Next.js page/workspace composition 可以協調多個 feature。

**Tech Stack:** Python 3.13、FastAPI、Pydantic、SQLAlchemy、HTTPX、OpenPyXL、pytest、Next.js 16、React 19、TypeScript、Vitest、Turborepo。

## Global Constraints

- 權威決策：[`ADR 0058`](../adr/0058-current-api-functional-modules-and-dependency-rules.md)；研究依據：[`module boundaries research`](../specs/2026-08-10-job-analysis-module-boundaries-research.md)。
- 施工時先用 `superpowers:using-git-worktrees` 建立隔離 worktree；不得直接覆蓋使用者工作樹的未追蹤或未提交內容。
- 只做 source-level refactor；不得改 `/api/v1/job-analysis`、`job-analysis-contract`、`job_analysis_*` tables、migration history、journal schema、Current State 或 authority semantics。
- 不建立 `app/job_analysis` compatibility shim、wildcard facade、第二套 runtime、雙寫或第二份 document store。
- provider call 保持在 transaction 外；repository 不自行 commit；generation／read-set stale protection 不變。
- 每個 task 都要先跑列出的 focused tests，再跑 `git diff --check`，綠燈後一個 task 一個 commit；不得把邏輯修改混入搬移 commit。
- 現行設計文件提到的 import path 必須與對應程式搬移在同一 commit 更新；不 push。
- 搬移後若單檔仍超過 500 行、單一 facade 超過 25 個 public names，或混合兩種 IO／use-case responsibility，記錄並在同一 task 拆分；不得為湊行數機械切檔。

## Target Source Map

```text
apps/api/app/
  core/domain/**
  core/{state,authority,persistence,journal,errors,model_outcome,portable_schema,opks_integrity}.py
  documents/{__init__,authoring,duty_authoring,readiness,errors}.py
  task_analysis/{__init__,context,operation,ports,proposal_decisions,transition,verifier}.py
  task_analysis/llm/{prompt,result,wire}.py
  opks/{__init__,authoring,context,digest,generation,operation,ports,proposals,scheduler,verifier}.py
  opks/llm/{prompt,result,wire}.py
  consultation/{__init__,turn,durable_turn}.py
  export/{__init__,assembly}.py
  adapters/{postgres,openrouter,xlsx}/
  api/routes/{documents,consultation,opks,export}.py
  api/mappers/{documents,consultation,opks}.py

apps/web/src/
  features/{documents,consultation,opks,export}/
  shared/{api,query,providers,ui}/
  app/workspace/[document_id]/_components/
```

Allowed graph：`documents/task_analysis/opks/export → core`；`consultation → task_analysis/opks/core`；`adapters → owning ports/core`；`api → feature public APIs/adapters`。除此之外的跨模組 edge 一律禁止。

---

### Task 1: 建立 shared core domain 與 Current State

**Files:** move `apps/api/app/job_analysis/domain/**` → `apps/api/app/core/domain/**`; create `apps/api/app/core/__init__.py`, `state.py`; modify `apps/api/app/job_analysis/application/transition.py`, all Python imports, domain/state tests, `apps/api/tests/test_job_analysis_dependencies.py`.

**Produces:** `app.core.domain` 與 `app.core.JobAnalysisState`；`core` 不 import 任何 feature、adapter、FastAPI、SQLAlchemy、HTTPX 或 OpenPyXL。

- [x] 跑搬移前基線：`cd apps/api; uv run pytest -q`，記錄 pass／skip／fail 數。
- [x] 將既有 `domain` 整目錄用 `git mv` 搬入 `app/core/domain`，不改 model fields、validator 或序列化結果。
- [x] 只把 `JobAnalysisState` 從 `transition.py` 抽到 `core/state.py`；transition functions 仍留在原處等 Task 4 搬移。
- [x] 全 repo 更新 imports；擴充 AST test，先守住 `core` 的 forbidden imports。
- [x] 跑 `uv run pytest tests/test_job_analysis_domain.py tests/test_job_analysis_duty_domain.py tests/test_job_analysis_jd_header.py tests/test_job_analysis_transition.py -q` 與完整 API suite。
- [x] Commit：`refactor: extract current authority domain core`。

### Task 2: 搬 authority／persistence seam 並消除跨功能共用實作

**Files:** move `application/authority_commit.py`, `persistence.py`; create `core/journal.py`, `errors.py`, `model_outcome.py`, `portable_schema.py`, `opks_integrity.py`; modify `context.py`, `verifier.py`, `opks_digest.py`, `opks_authoring.py`, `opks_proposals.py`, `providers/openrouter.py` and related tests/adapters.

**Produces:** `app.core.authority.commit_authority_change`、`JobAnalysisUnitOfWork`／factory、journal payloads、provider-neutral outcomes；core-owned aggregate referential integrity.

- [x] Move `ConversationTurn`、`ActiveQuestion`、`TurnSpeaker`、`ScheduledOpks` 到 `core/journal.py`，保持 field／enum value 完全相同。
- [x] Move `JobAnalysisApplicationError`、`DocumentNotFound`、`JdTaskNotFound`、`InvalidProposalDecision`、`IdempotencyConflict`、`ConcurrentAuthorityChange` 到 `core/errors.py`；`JdTaskNotFound` 被 documents／opks 共同消費，`InvalidProposalDecision` 被 task_analysis／opks 共同消費。
- [x] Move `OperationOutcome`、`ProviderFailureKind`、`ProviderText`、`ProviderRefusal`、`ProviderFailure`、`ProviderOutcome` 到 `core/model_outcome.py`；OpenRouter adapter 只 import 這些 boundary types。
- [x] Move `portable_schema.py` 到 core；move `prune_opks_for_current_jd`、`prune_opks_gaps_for_current_jd`、`ACTIVE_OPKS_PROPOSAL_STATUSES`、`stale_invalid_opks_proposals` 及該函式使用的 `_utcnow` helper 到 `core/opks_integrity.py`。
- [x] 更新 Postgres adapter 與所有 use cases imports，不改 schema IDs、UOW protocol methods 或 commit 順序。
- [x] 跑 `uv run pytest tests/test_job_analysis_authority_commit.py tests/test_job_analysis_persistence_contracts.py tests/test_job_analysis_postgres.py tests/test_job_analysis_openrouter_evidence.py -q` 與完整 API suite。
- [x] Commit：`refactor: extract authority and persistence seams`。

### Task 3: 建立 documents 功能模組

**Files:** move `application/authoring.py`, `duty_authoring.py`, `readiness.py` → `app/documents/`; create `documents/__init__.py`, `errors.py`; modify API imports, mapper imports and corresponding tests.

**Produces:** documents public API 僅暴露 document/header/Duty/Task direct-edit use cases、readiness DTO/function；不暴露 helper 或 repository implementation。

- [x] Move document-only errors：`DutyNotFound`、`InvalidDutyOrder`、`InvalidJdTaskOrder`、`JdHeaderNotChanged`；`JdTaskNotFound` 使用 core 的共用型別。
- [x] 將 direct edit 對 OPKS 的清理改為 import `core.opks_integrity`，documents 不 import `app.opks` internals。
- [x] `documents/__init__.py` 只 re-export routes/mappers 真正消費的 use cases 與 result DTOs；刪除舊 global application facade 中相同 exports。
- [x] 跑 `uv run pytest tests/test_job_analysis_authoring_postgres.py tests/test_job_analysis_duty_authoring_postgres.py tests/test_job_analysis_readiness.py tests/test_job_analysis_header_duty_export_vertical.py -q`。
- [x] 跑完整 API suite與 `git diff --check`。
- [x] Commit：`refactor: extract documents module`。

### Task 4: 建立 task_analysis 功能模組與 model port

**Files:** move `application/context.py`, `operation.py`, `proposal_decisions.py`, `transition.py`, `verifier.py`; move `llm/prompt.py`, `result.py`, `wire.py`, task schema JSON → `app/task_analysis/`; create `task_analysis/__init__.py`, `ports.py`, `llm/__init__.py`, `errors.py`; modify imports/tests.

**Produces:** `TaskAnalysisModelPort.complete(...) -> ProviderOutcome`、packet／operation／verifier／transition／Task Proposal public APIs；不 import concrete OpenRouter 或 OPKS internals。

- [x] 在 `ports.py` 定義現有 `OpenRouterAdapter.complete` 所需的 structural Protocol；`run_task_analysis_operation` 參數改吃該 port，呼叫參數與 outcome handling 不變。
- [x] Port signature 固定如下；OPKS 在 Task 5 建立同形、但由 `app.opks` 擁有的 Protocol：

```python
class TaskAnalysisModelPort(Protocol):
    async def complete(
        self,
        *,
        instructions: str,
        packet_text: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> ProviderOutcome: ...
```

- [x] Move 原檔內 `ProposalNotFound`／`ProposalNotDecidable` 到 task-analysis error surface；`InvalidProposalDecision` 使用 core 的共用型別。
- [x] Task Proposal 對 OPKS 的 stale/prune 行為只呼叫 `core.opks_integrity`，不得 import `app.opks`。
- [x] `task_analysis/__init__.py` 只公開 consultation/API 需要的 application API、port 與 DTO；LLM wire、prompt、verifier helper 保持 internal。
- [x] 跑 `uv run pytest tests/test_job_analysis_context.py tests/test_job_analysis_operation.py tests/test_job_analysis_prompt.py tests/test_job_analysis_wire_schema.py tests/test_job_analysis_verifier.py tests/test_job_analysis_transition.py tests/test_job_analysis_proposal_decisions_postgres.py -q`。
- [x] 跑完整 API suite與 `git diff --check`。
- [x] Commit：`refactor: extract task analysis module`。

### Task 5: 建立 opks 功能模組與 model port

**Files:** move all `application/opks_*.py`; move `llm/opks_prompt.py`, `opks_result.py`, `opks_wire.py`, OPKS schema JSON → `app/opks/`; create `opks/__init__.py`, `ports.py`, `llm/__init__.py`, `errors.py`; modify imports/tests.

**Produces:** `OpksModelPort.complete(...) -> ProviderOutcome` 與 OPKS authoring／generation／proposal／scheduler public APIs；只依賴自身與 core。

- [x] Move `OpksItemNotFound`、`InvalidOpksOrder`、`OpksProposalNotFound`、`OpksProposalNotDecidable` 到 `opks/errors.py`。
- [x] 在 `ports.py` 定義 OPKS model Protocol；`run_opks_operation`／generation 改吃 port，不 import concrete OpenRouter。
- [x] `opks/__init__.py` 公開 consultation/API 需要的 use cases、scheduler 與 port；不得 re-export prompt、wire mapper 或 verifier helpers。
- [x] 跑 `uv run pytest -k opks -q`，再跑 `tests/test_job_analysis_consultation.py` 確認尚未破壞 orchestration。
- [x] 跑完整 API suite與 `git diff --check`。
- [x] Commit：`refactor: extract opks module`。

### Task 6: 建立 consultation orchestration

**Files:** move `application/consultation.py` → `consultation/turn.py`, `application/durable_turn.py` → `consultation/durable_turn.py`; create `consultation/__init__.py`; modify API dependency injection and consultation tests.

**Produces:** `submit_employee_turn` 是唯一同時協調 task_analysis 與 opks 的功能 API。

- [x] `submit_employee_turn` 明確接收 `TaskAnalysisModelPort` 與 `OpksModelPort`；composition root 可把同一 OpenRouter instance 傳給兩個 port，但 consultation 不 import adapter class。
- [x] consultation 只 import `app.task_analysis`／`app.opks` root public APIs 與 core；不得 import sibling implementation files。
- [x] 保持一個主顧問＋至多一個 OPKS child、replay payload、idempotency key 與 provider-before-transaction 順序不變。
- [x] 跑 `uv run pytest tests/test_job_analysis_consultation.py tests/test_job_analysis_durable_turn_postgres.py tests/test_job_analysis_durable_smoke.py -q`。
- [x] 跑完整 API suite與 `git diff --check`。
- [x] Commit：`refactor: extract consultation orchestration`。

### Task 7: 搬 export／adapters 並拆薄 HTTP delivery

**Files:** move `application/export.py` → `export/assembly.py`, `application/export_xlsx.py` → `adapters/xlsx/`; move `providers/**` → `adapters/openrouter/`; rename `adapters/job_analysis_postgres` → `adapters/postgres`; split `api/routes/job_analysis.py`, `job_analysis_mapper.py`; rename deps/problems modules; update router, tests and architecture docs.

**Produces:** 四個 route modules 共用原 prefix；API 只 import feature root public APIs；OpenPyXL 只存在 xlsx adapter。

- [x] Routes 依 endpoint 固定拆分：documents = document/header/Duty/Task CRUD＋order；consultation = GET consultation／POST turns／Task Proposal decision；opks = OPKS CRUD／order／Proposal decision；export = XLSX download。
- [x] Mappers 拆成 documents／consultation／opks；保留所有 wire DTO、problem type、status code、filename 與 header 行為。
- [x] `api/router.py` include 四個 routers；路由集合必須與搬移前完全相同。
- [x] 移除已空的 `app/job_analysis`、舊 global facade 與所有內部 `app.job_analysis` imports；不得留下 shim。
- [x] 更新 `AGENTS.md`、`ARCHITECTURE.md`、`docs/design/task-analysis-engine.md` 的 source map／依賴規則；把 `apps/api/app/job_analysis/AGENTS.md` 仍有效的規則移入上述權威文件後刪除舊檔。
- [x] 跑 `uv run pytest tests/test_app_wiring.py tests/test_job_analysis_api.py tests/test_job_analysis_api_postgres.py tests/test_job_analysis_mapper.py tests/test_job_analysis_export_assembly.py tests/test_job_analysis_export_xlsx.py tests/test_job_analysis_migration.py -q`，再跑完整 API suite。
- [x] Commit：`refactor: compose current functional modules`。

### Task 8: 將 Web 整理為 feature-first

**Files:** move workspace components/helpers/tests into `features/documents`, `features/consultation`, `features/opks`, `features/export`; move generic API/query/providers/UI into `shared`; move `ConsultationWorkspace.tsx` 與 `ConsultationPanel.tsx` into `app/workspace/[document_id]/_components`; create each feature `index.ts` and `src/architecture.test.ts`.

**Produces:** feature public entrypoints；feature 不 import sibling feature；跨 feature 組裝只在 Next.js app workspace。

- [x] documents 收 `DocumentLibrary`、header/Duty/Task editors/forms、readiness、unsaved guard 與 `jobAnalysisDuties/Form/Header` helpers/tests。
- [x] consultation 收 `ProposalCard` 與 proposal helper/tests；`ConsultationPanel` 因同時協調 Task／OPKS proposal，與 `ConsultationWorkspace` 一起留在 app workspace composition。opks 收三個 OPKS components 與 helper/tests；export 收 export helper/tests。
- [x] `jobAnalysisApi.ts` 移到 `shared/api`、`jobAnalysisQueries.ts` 移到 `shared/query`；`components/ui`、Providers、download/utils 移到相應 shared folder，不放 domain policy。
- [x] 用 TypeScript compiler API 的 Vitest architecture test 掃 import declarations：`shared -> feature` 與 `feature A -> feature B` 一律失敗；app 只經 feature root `index.ts` import。
- [x] 跑 `npm run test`、`npx tsc --noEmit`、`npm run lint`（cwd `apps/web`）。
- [x] Commit：`refactor: organize workspace by feature`。

## Final Gate

- [x] `rg -n "app[./]job_analysis|components/workspace|@/lib/jobAnalysis|src/lib/" apps docs AGENTS.md ARCHITECTURE.md` 不得找到現行 source／orientation 的舊路徑；歷史 specs/ADR 可保留歷史名稱。
- [x] Backend AST contracts驗證 allowed dependency graph、API-only access、no cycle、core/framework prohibition、adapter-only SQLAlchemy/HTTPX/OpenPyXL。
- [x] `npm run check-codegen -w @caliburn/job-analysis-contract` 通過，證明 contract 無變更。
- [x] `npx turbo test --force --env-mode=loose`、Web typecheck／lint、`git diff --check` 全綠；route snapshot 與 fresh PostgreSQL migration test 全綠。
- [x] 工作樹只容許使用者原有未追蹤檔；建立本地 tag：`git tag current-application-modules-v1`。除非 owner 另行要求，不 push。
