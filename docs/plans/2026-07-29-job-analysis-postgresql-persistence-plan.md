# Job Analysis PostgreSQL Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 greenfield `app/job_analysis` 可在 PostgreSQL 建立、保存、關閉與重開多份本機 JD，支援員工直接編輯、AI transition 與 Proposal 決策的原子寫入。

**Architecture:** `app/job_analysis` 保持純 domain/application；persistence ports 住 application，新 SQLAlchemy adapter 住 `app/adapters/job_analysis_postgres`。Current JD Task 用 relational rows，Current Work Model 與 Proposal 用 versioned JSONB，完成回合／直接編輯／決策用 append-only Journal；reload 直接讀 Current State，不 replay Journal。

**Tech Stack:** Python 3.12、Pydantic v2、SQLAlchemy 2.0.51 async、asyncpg 0.31.0、Alembic 1.18.5、PostgreSQL 16、pytest。

## Global Constraints

- Greenfield：不得 import、wrap、dual-write、轉換或回填 `app.job_authoring`／`app.interview_vnext`。
- 不刪舊 tables；migration 0012 只新增 `job_analysis_*`，downgrade 回 0011。
- 不新增 tenant、user、profile、login、ACL、SaaS、revision history、hash chain、outbox、Event Sourcing 或 Graph runtime。
- 不先建 O/P/K/S/A／完整公版 header tables；本計畫只做 Task durable vertical。
- LLM/provider call 不得位於 DB transaction；每個 asyncio task 使用自己的 `AsyncSession`。
- application 是唯一 writer；模型與員工只提供候選、文字與決策。
- 測試採最小風險網：純契約／transition 測關鍵不變量，real PostgreSQL 只測 migration、hydrate、原子性、stale、idempotency、reload。
- 每個 Task 各一個 commit；green-before == green-after；不 push。

---

## 檔案配置

```text
apps/api/app/job_analysis/
├─ domain/
│  └─ proposal.py                  Current JD `JdTask` 與 Proposal before/after
└─ application/
   ├─ persistence.py               純 records、ports、journal payload contracts
   ├─ authoring.py                 文件與員工 direct-edit use cases
   ├─ durable_turn.py              snapshot → provider外呼 → stale-safe commit
   └─ proposal_decisions.py        accept/edit/reject/defer/revision-request

apps/api/app/adapters/job_analysis_postgres/
├─ __init__.py
├─ models.py                       SQLAlchemy rows
├─ serialization.py                versioned JSONB encode/hydrate
└─ repositories.py                 repositories + UoW

apps/api/alembic/versions/
└─ 0012_job_analysis_current_state.py
```

`app/job_analysis` 不 import adapter；composition/root 與 Web 不在本計畫。

---

### Task 1: Current JD 可編輯契約

**Files:**

- Modify: `apps/api/app/job_analysis/domain/proposal.py`
- Modify: `apps/api/app/job_analysis/domain/__init__.py`
- Modify: `apps/api/app/job_analysis/application/context.py`
- Modify: `apps/api/app/job_analysis/application/transition.py`
- Modify: `apps/api/tests/test_job_analysis_domain.py`
- Modify: `apps/api/tests/test_job_analysis_context.py`
- Modify: `apps/api/tests/test_job_analysis_transition.py`
- Modify: `apps/api/tests/test_job_analysis_smoke.py`

**Interfaces:**

- Produces:

```python
class ResponsibilityRole(StrEnum):
    PRIMARY = "primary"
    SHARED = "shared"
    ASSIST = "assist"

class JdTaskFields(DomainModel):
    statement: NonEmptyText
    purpose_result: NonEmptyText | None = None
    context: NonEmptyText | None = None
    frequency_text: NonEmptyText | None = None
    responsibility_role: ResponsibilityRole | None = None
    enablers: tuple[Enabler, ...] = ()

class JdTask(JdTaskFields):
    task_id: TaskId
    display_order: int

class JdEntry(DomainModel):
    task_id: TaskId
    value: JdTask | None = None
```

- `JobAnalysisState.current_jd` 只保存目前存在於 JD 的 `JdTask`，依 `display_order, task_id` 排序；
  `current_jd_task_ids` 直接由這組 Task 推導。
- Proposal `edited_jd_after` 可改非 null `JdTask` 的可見內容，但不得改 key、null 位置、`task_id` 或
  `display_order`。

- [x] **Step 1: 寫失敗測試**

加入四個 focused cases：完整 `JdTask` round-trip、非法 responsibility role、edited 改 `display_order` 被拒、
context rendering 顯示員工可編輯的完整 JD 欄位而不顯示內部 Task ID。

- [x] **Step 2: 確認測試先紅**

Run:

```powershell
cd apps/api
uv run pytest tests/test_job_analysis_domain.py tests/test_job_analysis_context.py tests/test_job_analysis_transition.py tests/test_job_analysis_smoke.py -q
```

Expected: `JdTask`／`ResponsibilityRole` 尚不存在。

- [x] **Step 3: 實作最小契約並做機械替換**

把舊 `content` string 映射改成 `entry.value.statement`；transition 新建 JD after 時由 Work Model
`TaskFields` 投影 `JdTaskFields`，新順序使用目前最大 `display_order + 1`。不要把 Work Model
`action/object/support/lineage` 複製進 Current JD。

- [x] **Step 4: 跑 focused 與全部 job_analysis tests**

```powershell
$tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
uv run pytest @tests -q
```

Expected: 全綠，既有五個 smoke 語意不變。

- [x] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis apps/api/tests/test_job_analysis_*.py
git commit -m "feat(job-analysis): expand current JD task contract"
```

---

### Task 2: 純 persistence contracts 與 versioned serialization

**Files:**

- Create: `apps/api/app/job_analysis/application/persistence.py`
- Create: `apps/api/tests/test_job_analysis_persistence_contracts.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`
- Modify: `apps/api/tests/test_job_analysis_dependencies.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class DocumentRecord:
    document_id: UUID
    title: str
    work_model: CurrentWorkModel
    active_question: ActiveQuestion | None
    authority_generation: int
    created_at: datetime
    updated_at: datetime

@dataclass(frozen=True)
class LoadedDocument:
    document: DocumentRecord
    state: JobAnalysisState
    recent_turns: tuple[CompletedTurnPayload, ...]

@dataclass(frozen=True)
class DocumentSummary:
    document_id: UUID
    title: str
    task_count: int
    updated_at: datetime

class JournalEntry(DomainModel):
    document_id: UUID
    entry_id: str
    kind: Literal["employee_turn", "direct_edit", "proposal_decision"]
    payload_schema_id: str
    payload: CompletedTurnPayload | DirectEditPayload | ProposalDecisionPayload
    created_at: datetime

class JobAnalysisUnitOfWork(Protocol):
    documents: DocumentRepository
    tasks: JdTaskRepository
    proposals: ProposalRepository
    journal: JournalRepository
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    async def commit(self) -> None: ...
```

`CompletedTurnPayload` 保存 employee turn、實際送出的 consultant next-question turn、operation ID；
`DirectEditPayload` 保存 edit kind 與完成後 `JdTask | None`；`ProposalDecisionPayload` 保存 proposal ID、
decision 與員工文字／理由。三者都是 frozen Pydantic contract，不讓 raw ORM/JSON 越過 port。

- [x] **Step 1: 寫失敗測試**

測 frozen records、負 generation 被拒、三種 journal payload 與 kind 必須相符、UoW Protocol 不含
SQLAlchemy 型別、dependency guard 仍禁止 `sqlalchemy` 進 `app/job_analysis`。

- [x] **Step 2: 確認測試先紅**

```powershell
cd apps/api
uv run pytest tests/test_job_analysis_persistence_contracts.py tests/test_job_analysis_dependencies.py -q
```

- [x] **Step 3: 實作 records／ports**

Repository methods 固定為：

```python
DocumentRepository.create(record) -> None
DocumentRepository.get(document_id, *, for_update=False) -> DocumentRecord | None
DocumentRepository.list() -> tuple[DocumentSummary, ...]
DocumentRepository.update_authority(document_id, *, expected_generation, work_model, active_question, updated_at) -> bool

JdTaskRepository.list(document_id) -> tuple[JdTask, ...]
JdTaskRepository.replace(document_id, tasks) -> None

ProposalRepository.list(document_id, *, statuses=None) -> tuple[Proposal, ...]
ProposalRepository.replace(document_id, proposals) -> None

JournalRepository.get(document_id, entry_id) -> JournalEntry | None
JournalRepository.add(entry) -> None
JournalRepository.list_recent_turns(document_id, *, limit) -> tuple[CompletedTurnPayload, ...]
```

`replace` 是 document lock 下的 aggregate persistence seam，不是 generic repository framework。

- [x] **Step 4: 跑 focused tests**

```powershell
uv run pytest tests/test_job_analysis_persistence_contracts.py tests/test_job_analysis_dependencies.py -q
```

- [x] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis/application apps/api/tests/test_job_analysis_persistence_contracts.py apps/api/tests/test_job_analysis_dependencies.py
git commit -m "feat(job-analysis): define persistence ports"
```

---

### Task 3: Migration 0012 與 PostgreSQL rows

**Files:**

- Create: `apps/api/alembic/versions/0012_job_analysis_current_state.py`
- Create: `apps/api/app/adapters/job_analysis_postgres/__init__.py`
- Create: `apps/api/app/adapters/job_analysis_postgres/models.py`
- Create: `apps/api/tests/test_job_analysis_migration.py`
- Modify: `apps/api/alembic/env.py`
- Modify: `apps/api/tests/conftest.py`
- Modify: `apps/api/tests/test_interview_vnext_migration.py`

**Interfaces / schema:**

- `job_analysis_documents(document_id UUID PK, title, work_model_schema_id, work_model_json JSONB,
  active_question_json JSONB NULL, authority_generation BIGINT, created_at, updated_at)`
- `job_analysis_jd_tasks(document_id, task_id TEXT, statement, purpose_result, context, frequency_text,
  responsibility_role, enablers_json JSONB, display_order, created_at, updated_at)`
- `job_analysis_proposals(document_id, proposal_id TEXT, status, base_authority_generation,
  proposal_schema_id, proposal_payload JSONB, caused_by_decision_id, created_at, resolved_at)`
- `job_analysis_journal(journal_sequence BIGINT IDENTITY PK, document_id, entry_id TEXT, kind,
  payload_schema_id, payload JSONB, created_at)`

所有 constraint/index 名稱以 `ja2_` 開頭，避免與 0011 舊表混淆。`ON DELETE CASCADE` 只用於同一新 document
內的三張 child tables。

- [x] **Step 1: 寫 migration introspection 失敗測試**

測 upgrade `0011 → 0012`、四表 columns/PK/FK/UNIQUE/CHECK/index、downgrade 回 0011 後舊
`job_authoring_*` 仍存在、新表消失、Alembic single head 為 0012。

- [x] **Step 2: 確認 migration test 先紅**

```powershell
cd apps/api
uv run pytest tests/test_job_analysis_migration.py -q
```

Expected: revision `0012` 不存在。

- [x] **Step 3: 建 migration 與 models**

只使用 PostgreSQL 16 已有 JSONB、identity、FK、UNIQUE、CHECK、index。不得建 trigger、RLS、tenant 欄位、
revision table 或舊資料 INSERT/SELECT。

- [x] **Step 4: 增加 document-scoped cleanup**

在 `tests/conftest.py` 新增獨立 `job_analysis_document_id` 與 cleanup fixture，依
Journal → Proposal → JD Task → Document 反向刪除；不得把它塞進舊 tenant-scoped vNext cleanup。

- [x] **Step 5: 跑 migration tests**

```powershell
uv run pytest tests/test_job_analysis_migration.py tests/test_interview_vnext_migration.py -q
```

- [x] **Step 6: Commit**

```powershell
git add apps/api/alembic apps/api/app/adapters/job_analysis_postgres apps/api/tests/conftest.py apps/api/tests/test_job_analysis_migration.py apps/api/tests/test_interview_vnext_migration.py
git commit -m "feat(job-analysis): add current-state migration"
```

---

### Task 4: PostgreSQL repositories、UoW 與 fail-closed hydrate

**Files:**

- Create: `apps/api/app/adapters/job_analysis_postgres/serialization.py`
- Create: `apps/api/app/adapters/job_analysis_postgres/repositories.py`
- Create: `apps/api/tests/test_job_analysis_postgres.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/__init__.py`

**Interfaces:**

```python
class PersistedJobAnalysisCorruption(RuntimeError): ...

class SqlAlchemyJobAnalysisUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]): ...
```

Serialization IDs：

```text
job-analysis-work-model/1
job-analysis-proposal/1
job-analysis-active-question/1
job-analysis-completed-turn/1
job-analysis-direct-edit/1
job-analysis-proposal-decision/1
```

Proposal JSONB 不重複 relational `proposal_id/status/caused_by_decision_id`；hydrate 時由 row 欄位注入再跑完整
`Proposal.model_validate`。任何 schema ID、enum、JSON shape、JD/Work Model identity 不一致都 raise
`PersistedJobAnalysisCorruption`。

- [x] **Step 1: 寫 real-PostgreSQL 失敗測試**

只測：create/list/get、ordered Task round-trip、open Proposal round-trip、recent completed turn、`FOR UPDATE`
鎖 document、corrupt Work Model/Proposal/enablers fail closed。

- [x] **Step 2: 確認測試先紅**

```powershell
cd apps/api
uv run pytest tests/test_job_analysis_postgres.py -q
```

- [x] **Step 3: 實作 serialization 與 repositories**

UoW `__aenter__` 開一個 `AsyncSession`/transaction；未呼叫 `commit()` 時 `__aexit__` rollback。不得在 repository
內 commit，不得 hidden retry。

- [x] **Step 4: 跑 focused PostgreSQL tests**

```powershell
uv run pytest tests/test_job_analysis_postgres.py -q
```

- [x] **Step 5: Commit**

```powershell
git add apps/api/app/adapters/job_analysis_postgres apps/api/tests/test_job_analysis_postgres.py
git commit -m "feat(job-analysis): persist and hydrate current state"
```

---

### Task 5: 文件庫與員工 direct edit

**Files:**

- Create: `apps/api/app/job_analysis/application/authoring.py`
- Create: `apps/api/tests/test_job_analysis_authoring_postgres.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`

**Interfaces:**

```python
async def create_document(uow_factory, *, document_id: UUID, title: str, entry_id: str) -> DocumentRecord
async def list_documents(uow_factory) -> tuple[DocumentSummary, ...]
async def load_document(uow_factory, document_id: UUID) -> LoadedDocument | None
async def add_jd_task(uow_factory, *, document_id: UUID, entry_id: str, fields: JdTaskFields) -> JdTask
async def edit_jd_task(uow_factory, *, document_id: UUID, entry_id: str, task_id: TaskId, fields: JdTaskFields) -> JdTask
async def delete_jd_task(uow_factory, *, document_id: UUID, entry_id: str, task_id: TaskId) -> None
async def reorder_jd_tasks(uow_factory, *, document_id: UUID, entry_id: str, ordered_task_ids: tuple[TaskId, ...]) -> tuple[JdTask, ...]
```

新增 Task ID 由 application 以 `(document_id, entry_id)` 決定性配發；同 entry replay 回相同結果。

- [ ] **Step 1: 寫失敗測試**

測 create/list/load、add/edit/delete/reorder、完整 reload、同 entry replay 不重做、不同 payload 共用 entry ID
回 idempotency conflict、direct edit 產生 Journal、generation 恰加一、相關 Proposal stale、Work Model
`pending_reconciliation` 更新但 UI DTO 不需要暴露。

- [ ] **Step 2: 確認測試先紅**

```powershell
cd apps/api
uv run pytest tests/test_job_analysis_authoring_postgres.py -q
```

- [ ] **Step 3: 實作短 transaction**

固定順序：lock document → idempotency lookup → 讀 Task/Proposal → 套用 pure change → replace rows →
insert direct-edit Journal → generation + 1 → commit。找不到 document/task 回 typed application error，
不把 SQLAlchemy exception 洩漏給 caller。

- [ ] **Step 4: 跑 focused tests**

```powershell
uv run pytest tests/test_job_analysis_authoring_postgres.py tests/test_job_analysis_postgres.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis/application apps/api/tests/test_job_analysis_authoring_postgres.py
git commit -m "feat(job-analysis): add durable direct editing"
```

---

### Task 6: Durable AI turn 與 authority snapshot

**Files:**

- Create: `apps/api/app/job_analysis/application/durable_turn.py`
- Create: `apps/api/tests/test_job_analysis_durable_turn_postgres.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class TurnSnapshot:
    document_id: UUID
    authority_generation: int
    state: JobAnalysisState
    packet: TaskAnalysisPacket

async def prepare_turn(...) -> TurnSnapshot
async def commit_verified_turn(..., snapshot: TurnSnapshot, operation_id: str,
                               employee_turn: ConversationTurn,
                               operation_result: TaskAnalysisOperationResult) -> TransitionResult
```

composition 呼叫順序固定為 `prepare_turn()` → transaction 外
`run_task_analysis_operation()` → `commit_verified_turn()`；application API 不提供把 adapter 傳入 transaction 的簽章。

- [ ] **Step 1: 寫失敗測試**

測 fake provider 期間另一個 session direct edit 使舊 snapshot 被拒、未變更時 transition/Proposal/next question/
completed-turn Journal 同交易保存、同 operation replay 不長第二份 Task/Proposal、provider failure 不寫 current state。

- [ ] **Step 2: 確認測試先紅**

```powershell
cd apps/api
uv run pytest tests/test_job_analysis_durable_turn_postgres.py -q
```

- [ ] **Step 3: 實作兩段式 commit**

prepare transaction 結束後才外呼；commit transaction 先 lock document，再比較 generation 與 packet read-set。
不符回 `stale_authority_snapshot`，不得只重算交集後套用舊 result。

- [ ] **Step 4: 跑 focused tests**

```powershell
uv run pytest tests/test_job_analysis_durable_turn_postgres.py tests/test_job_analysis_operation.py tests/test_job_analysis_transition.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis/application apps/api/tests/test_job_analysis_durable_turn_postgres.py
git commit -m "feat(job-analysis): commit AI turns durably"
```

---

### Task 7: Proposal 決策與兩層原子更新

**Files:**

- Create: `apps/api/app/job_analysis/application/proposal_decisions.py`
- Create: `apps/api/tests/test_job_analysis_proposal_decisions_postgres.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`

**Interfaces:**

```python
async def decide_proposal(
    uow_factory,
    *,
    document_id: UUID,
    proposal_id: str,
    decision_id: str,
    decision: Literal["accepted", "edited", "rejected", "deferred", "revision_requested"],
    edited_jd_after: tuple[JdEntry, ...] | None = None,
    reason: str | None = None,
    excluded_member_task_ids: tuple[TaskId, ...] = (),
    excluded_child_refs: tuple[TaskId, ...] = (),
) -> Proposal
```

- [ ] **Step 1: 寫失敗測試**

測 accept 原子套用 JD + staged Work Model delta、edited 套員工文字並標 reconcile、reject 不動 JD、defer reload
仍可決定、revision-request 保存 payload 但不呼叫 provider、`jd_before` 不符即 stale、terminal 不可再決定、
同 decision replay、同 decision ID 不同內容 conflict。

- [ ] **Step 2: 確認測試先紅**

```powershell
cd apps/api
uv run pytest tests/test_job_analysis_proposal_decisions_postgres.py -q
```

- [ ] **Step 3: 實作固定 lock 與原子 mutation**

lock document → proposal → task IDs sorted；以完整 `JdTask` 比較 `jd_before`。accepted/edited 才改 JD；
staged delta 與 JD 必須同 transaction；寫 proposal-decision Journal 後 generation + 1。
replacement LLM rebuild 不在本計畫，revision request 只需 durable、可 reload。

- [ ] **Step 4: 跑 focused tests**

```powershell
uv run pytest tests/test_job_analysis_proposal_decisions_postgres.py tests/test_job_analysis_authoring_postgres.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis/application apps/api/tests/test_job_analysis_proposal_decisions_postgres.py
git commit -m "feat(job-analysis): persist proposal decisions"
```

---

### Task 8: Durable scripted vertical 與 design writeback

**Files:**

- Create: `apps/api/tests/test_job_analysis_durable_smoke.py`
- Modify: `docs/design/task-analysis-engine.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md`
- Modify: `docs/plans/2026-07-29-job-analysis-postgresql-persistence-plan.md`

- [ ] **Step 1: 寫 real-PostgreSQL durable smoke**

一條測試完成：

```text
create document
→ direct add/edit/reorder
→ 關閉 UoW
→ 新 session reload
→ fake verified AI turn 建 Proposal
→ 關閉 UoW
→ 新 session accept Proposal
→ 再 reload 並核對 Current JD／Work Model／Journal／generation
```

不打網路，不接 route，不使用舊 tables。

- [ ] **Step 2: 跑 durable smoke 與全部 job_analysis tests**

```powershell
cd apps/api
uv run pytest tests/test_job_analysis_durable_smoke.py -q
$tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
uv run pytest @tests -q
```

- [ ] **Step 3: 更新端到端文件**

`docs/design/task-analysis-engine.md` 必須寫真實 module/function 名、四表 authority、direct edit 與 AI turn
transaction 時序、reload、idempotency、greenfield 禁令，以及仍未提供 Web/O/P/K/S/A/export。

- [ ] **Step 4: 跑完整 API suite**

```powershell
cd apps/api
uv run pytest -q
```

Expected: green-before == green-after；若既有 vNext raw-bytes hash failure 仍存在，需以同一 test node
在動工前後均失敗證明不是本分支造成。

- [ ] **Step 5: 文件檢查與 commit**

```powershell
git diff --check
git add apps/api/tests/test_job_analysis_durable_smoke.py docs/design/task-analysis-engine.md docs/README.md AGENTS.md docs/plans/2026-07-29-job-analysis-postgresql-persistence-plan.md
git commit -m "docs(job-analysis): record durable vertical"
```

---

## 停線條件

- 任一實作需要讀／寫舊 `job_authoring`／vNext tables：停線；不得加 compatibility adapter。
- 必須新增第五張 table 才能完成 Task durable vertical：先指出缺少它會造成的具體使用者失敗，再回 ADR 審議。
- 為 JSONB hydrate 必須跳過 Pydantic 驗證或接受未知 schema ID：停線。
- 必須把 provider call 放進 transaction 才能維持一致：設計錯誤，停線。
- Current JD 與 Work Model 需要共用同一 row/model 才寫得下去：停線，這違反兩層 authority。
- migration／adapter 開始吸收 tenant、revision、hash、outbox 或全面 audit：刪除該設計，不以「以後可能用」保留。

## 明確延後

- Web route／generated TypeScript／UI；
- O/P/K/S/A、完整公版 header、retrieval 與 export；
- revision history、restore、diff；
- long-context compaction、embedding retrieval；
- revision-request replacement 的 LLM rebuild；
- 正式模型品質調校與付費 eval。
