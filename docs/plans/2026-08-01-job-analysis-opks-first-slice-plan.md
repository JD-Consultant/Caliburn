# Job Analysis OPKS First Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Keep one task per commit and stop at every stated gate.

**Goal:** 在現行本機 Job Analysis vertical 上加入可持久、可由員工編輯、可由 AI 提案的工作產出（O）、行為指標（P）、知識（K）、技能（S）與態度（A），並維持來源可追溯與 Current JD 員工權威。

**Architecture:** 以一個固定形狀的 `OpksItem` 表達五種項目，以 `entity_kind` 與 refs 不變量區分 O/P/K/S/A；Current JD OPKS 與獨立的 `OpksProposal` 各用一張 PostgreSQL 表，不擴充 Task Proposal、不抽通用 Proposal framework。員工 direct edit 與 OPKS Proposal 決策共用既有 authority transaction；AI 使用獨立、輕量、strict 的單 Task O/P/K/S operation，模型只看 ordinal，application 才解析或配發穩定 ID。Attitude 第一版預設空且只做手動編輯，不進 per-Task model operation。

**Tech Stack:** Python 3.12、Pydantic v2、FastAPI 0.115.0、SQLAlchemy 2.0.51 async、PostgreSQL 16、Alembic、pytest、JSON Schema 2020-12、Next.js 16.2.6、React 19、TanStack Query v5、TypeScript、Vitest、ESLint。

**Authority:** [ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)、[ADR 0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)、[ADR 0050](../adr/0050-opks-proposal-minimal-shape.md)、[ADR 0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)、[OPKS 研究紀錄](../specs/2026-08-01-opks-design-decisions-research.md)、[Task Analysis Engine](../design/task-analysis-engine.md)。四份 ADR 缺一不可；研究原料與 ADR 衝突時以 ADR 為準。

## Global Constraints

- 本切片只做 Current JD 的 O/P/K/S/A、員工手動編輯、OPKS Proposal、單 Task O/P/K/S 生成與本機 Web；不做匯出、taxonomy、Reference Challenger、自動判級、proficiency、批次核准、跨文件分析或 Attitude AI 生成。
- 不建立空白 OPKS placeholder。Task 可以完全沒有 OPKS；真正建立一筆 `OpksItem` 時 `text` 必須非空。這保留「員工只先寫 Task 名稱，其餘稍後補」的既有能力。
- `OpksItem` 只持久化 `entity_id`、`entity_kind`、`text`、refs 與 `evidence_links`；`task_linkage`／`evidence_origins` 一律推導，不存第二份真相。
- 第一版 Evidence 只接受 `employee_turn`／`direct_edit`。`proposal_decision` 不得成為 Evidence；單純 accept 不得鑄 direct-edit Source。
- O/P 恰連一個 Task且不得帶 `indicator_refs`；K/S 可連 0..N 個 Task 與 0..N 個 Indicator；A 不連 Task／Indicator。語意正確性歸 rubric／員工，application 只驗 ID、值域與 cardinality。
- 模型永遠只看 context-local ordinal，不看、不輸出 `entity_id`。既有項目由 application 解析 ordinal；add ID 由 `operation_id + entity_kind + item position` 決定性產生，不用 `uuid4()`、不回收。
- AI 只建立 Proposal，不直接改 Current JD。員工 direct edit 與 accepted／edited Proposal 都經同一個 `commit_authority_change` transaction、完整狀態驗證、Journal 與 authority generation。
- OPKS wire schema 必須與 Task wire 分離，維持 strict portable subset、一次 HTTP、零 hidden retry；不改現有 OpenRouter adapter 或 provider routing。
- 不 import／搬移／雙寫舊 `app.interview`、`app.interview_vnext`、`app.job_authoring`、`evals` 或 OCS 資料；既有 AST guard 保持綠。
- 每個 Task 先紅測試，再做最小實作；focused gate 綠後才跑擴大 gate；一個 Task 一個 commit，不 push。
- 動到可觀察行為時，同 commit 更新 `docs/design/task-analysis-engine.md`；不得等全部做完才補回 fossilized 文檔。

## First-version domain shape

```python
class OpksEntityKind(StrEnum):
    OUTPUT = "output"
    INDICATOR = "indicator"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    ATTITUDE = "attitude"


class OpksEvidenceLink(SourceAnchor):
    # model validator: source_ref.kind 只可 EMPLOYEE_TURN / DIRECT_EDIT
    pass


class OpksItem(DomainModel):
    entity_id: Identifier
    entity_kind: OpksEntityKind
    text: NonEmptyText
    task_refs: tuple[TaskId, ...] = ()
    indicator_refs: tuple[Identifier, ...] = ()
    evidence_links: tuple[OpksEvidenceLink, ...]

    # derived only; do not serialize as fields
    @property
    def task_linkage(self) -> Literal["linked", "unlinked"]: ...

    @property
    def evidence_origins(self) -> frozenset[Literal["employee"]]: ...


class CurrentJdOpks(DomainModel):
    items: tuple[OpksItem, ...] = ()
```

`OpksProposal.before`／`after`／`edited_after` 使用完整 `OpksItem | None` snapshot，而非只存文字。這讓 refs／Evidence 的併發變更也能被判 stale；`edited_after` 必須保持 `entity_id`、kind、refs、Evidence 不變，只允許員工改 `text`。它是 0050 所列 before/after、refs、Evidence 的單一正規表示，不另抄 top-level 第二份 refs。

## Baseline

- [ ] 在 repo 根確認 `git branch --show-current` 是 `docs/task-analysis-v1-foundations`，`git status --short` 只含本 plan commit 之後的預期變更。
- [ ] 在 `apps/api` 執行 `uv run pytest -q`，保存既有 failure fingerprint；若 `test_interview_vnext_execution_schemas.py` 仍因 CRLF hash 失敗，只能在 fingerprint 相同時列為既有失敗。
- [ ] 在 `apps/web` 執行 `npm run test`、`npx tsc --noEmit`、`npm run lint`，三項必須先綠。
- [ ] 在 `packages/job-analysis-contract` 執行 `npm run check-codegen` 與 `uv run pytest -q`，確認契約 SSOT 起點乾淨。

---

### Task 1: 凍結 OPKS domain contracts

**Files:**

- Create: `apps/api/app/job_analysis/domain/opks.py`
- Create: `apps/api/app/job_analysis/domain/opks_proposal.py`
- Modify: `apps/api/app/job_analysis/domain/__init__.py`
- Modify: `apps/api/tests/test_job_analysis_domain.py`
- Create: `apps/api/tests/test_job_analysis_opks_domain.py`
- Modify: `apps/api/tests/test_job_analysis_dependencies.py`
- Modify: `docs/design/task-analysis-engine.md`

**Interfaces:**

- Produces: `OpksEntityKind`, `OpksEvidenceLink`, `OpksItem`, `CurrentJdOpks`, `OpksProposalAction`, `OpksProposalStatus`, `OpksProposal`。
- `OpksProposalStatus` 固定六態：`pending|deferred|accepted|edited|rejected|stale`；`revision_requested` 不可表示。
- `OpksProposal` 固定欄位：`proposal_id`、`operation_id`、`entity_id`、`entity_kind`、`action`、`before`、`after`、`edited_after`、`status`、`rejection_reason`、`stale_reason`、`base_authority_generation`、`created_at`、`resolved_at`。

- [ ] **Step 1: 寫 domain 紅測試**

  覆蓋：Evidence 空陣列拒絕；`proposal_decision` Evidence 拒絕；O/P 非恰一 Task或帶 Indicator ref 拒絕；K/S refs 可多筆但重複值要拒絕、不靜默去重；A 帶 refs 拒絕；Indicator ref 必須指向同 aggregate 的 Indicator；推導軸不出現在 `model_dump()`；三種 action 的 before/after 組合；六態轉移；`edited_after` 只可改文字；stale/rejected payload 歸屬；`unknown` 不在 enum。

- [ ] **Step 2: 跑 focused red gate**（working directory: `apps/api`）

  ```powershell
  uv run pytest tests/test_job_analysis_opks_domain.py tests/test_job_analysis_domain.py -q
  ```

  Expected: FAIL，因 OPKS types 尚不存在；不可用修改測試期望來變綠。

- [ ] **Step 3: 實作最小 immutable contracts**

  所有 collection 使用 tuple、`extra="forbid"`／frozen 沿用 `DomainModel`。`CurrentJdOpks` 驗 entity ID 唯一與 indicator refs；另提供：

  ```python
  def validate_against_tasks(self, current_jd_task_ids: frozenset[TaskId]) -> None: ...
  def item_by_id(self, entity_id: str) -> OpksItem | None: ...
  ```

  `validate_against_tasks()` 只驗 refs 存在，不判斷「這個 K 是否真的支援該 Task」。

- [ ] **Step 4: 跑 focused 與 dependency gate**

  ```powershell
  uv run pytest tests/test_job_analysis_opks_domain.py tests/test_job_analysis_domain.py tests/test_job_analysis_dependencies.py -q
  ```

- [ ] **Step 5: Commit**

  ```powershell
  git add apps/api/app/job_analysis/domain apps/api/tests/test_job_analysis_opks_domain.py apps/api/tests/test_job_analysis_domain.py apps/api/tests/test_job_analysis_dependencies.py docs/design/task-analysis-engine.md
  git commit -m "feat(job-analysis): define OPKS domain contracts"
  ```

---

### Task 2: PostgreSQL Current JD OPKS 與 Proposal persistence

**Files:**

- Create: `apps/api/alembic/versions/0014_job_analysis_opks.py`
- Modify: `apps/api/app/job_analysis/application/transition.py`
- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Modify: `apps/api/app/job_analysis/application/authority_commit.py`
- Modify: `apps/api/app/job_analysis/application/durable_turn.py`
- Modify: `apps/api/app/job_analysis/application/authoring.py`
- Modify: `apps/api/app/job_analysis/application/proposal_decisions.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/models.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/serialization.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/repositories.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/__init__.py`
- Modify: `apps/api/tests/test_job_analysis_persistence_contracts.py`
- Modify: `apps/api/tests/test_job_analysis_postgres.py`
- Modify: `apps/api/tests/test_job_analysis_migration.py`
- Modify: `apps/api/tests/test_job_analysis_authority_commit.py`
- Modify: `apps/api/tests/test_job_analysis_durable_turn_postgres.py`
- Modify: `docs/design/task-analysis-engine.md`

**Persistence shape:**

```text
job_analysis_opks_items
  document_id + entity_id PK
  entity_kind
  item_schema_id
  item_payload JSONB
  created_at / updated_at

job_analysis_opks_proposals
  document_id + proposal_id PK
  operation_id / entity_id / entity_kind / action / status
  base_authority_generation
  proposal_schema_id
  proposal_payload JSONB
  created_at / resolved_at
```

不建五張 item table、不建 task/indicator join tables、不加 revision/history/hash。refs 與 Evidence 留在 typed JSON payload；application 在每次 hydrate 與 commit 重驗完整 `CurrentJdOpks`。

**Ports:**

```python
class OpksRepository(Protocol):
    async def list(self, document_id: UUID) -> tuple[OpksItem, ...]: ...
    async def replace(self, document_id: UUID, items: tuple[OpksItem, ...]) -> None: ...

class OpksProposalRepository(Protocol):
    async def list(
        self,
        document_id: UUID,
        *,
        statuses: frozenset[OpksProposalStatus] | None = None,
    ) -> tuple[OpksProposal, ...]: ...
    async def replace(
        self, document_id: UUID, proposals: tuple[OpksProposal, ...]
    ) -> None: ...
```

- [ ] **Step 1: 寫 serialization／port／migration 紅測試**

  測完整 round-trip、未知 schema ID fail closed、損毀 payload fail closed、六態 DB check、active/terminal `resolved_at` check、文件刪除 cascade、兩個文件可使用相同 entity ID 而互不污染；Journal kind check 必須在保留既有 `consultant_opening|employee_turn|direct_edit|proposal_decision` 的前提下加入 `opks_generation`。

- [ ] **Step 2: 跑 focused red gate**

  ```powershell
  uv run pytest tests/test_job_analysis_persistence_contracts.py tests/test_job_analysis_postgres.py tests/test_job_analysis_migration.py -q
  ```

- [ ] **Step 3: 實作 migration、rows、serialization 與 repositories**

  新 schema IDs 固定為：

  ```python
  OPKS_ITEM_SCHEMA_ID = "job-analysis-opks-item/1"
  OPKS_PROPOSAL_SCHEMA_ID = "job-analysis-opks-proposal/1"
  ```

  Repository 回傳順序固定 `(created_at, entity_id)`／`(created_at, proposal_id)`；第一版不增加可編輯排序欄位。

- [ ] **Step 4: 把完整 OPKS authority 納入現有 state 與 commit seam**

  `JobAnalysisState` 新增：

  ```python
  current_opks: CurrentJdOpks = CurrentJdOpks()
  opks_proposals: tuple[OpksProposal, ...] = ()
  ```

  `JobAnalysisState` validator 必須以 `current_jd_task_ids` 呼叫 `current_opks.validate_against_tasks()`；`_load_state()` 一律載入兩個新 repository。`commit_authority_change()` 在完整 `JobAnalysisState.model_validate()` 後，與 Tasks／Task Proposals 同交易 replace OPKS／OPKS Proposals，再寫 Journal、CAS generation、commit。舊 caller 傳入的空 OPKS 必須保持 no-op 語意，現有 Task transition 必須逐字保留未碰到的 OPKS state。

- [ ] **Step 5: 跑 PostgreSQL focused gate**

  ```powershell
  uv run pytest tests/test_job_analysis_postgres.py tests/test_job_analysis_migration.py tests/test_job_analysis_authority_commit.py tests/test_job_analysis_durable_turn_postgres.py -q
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/api/alembic/versions/0014_job_analysis_opks.py apps/api/app/job_analysis apps/api/app/adapters/job_analysis_postgres apps/api/tests docs/design/task-analysis-engine.md
  git commit -m "feat(job-analysis): persist Current JD OPKS state"
  ```

---

### Task 3: 員工 OPKS 手動編輯與 workspace contract

**Files:**

- Create: `apps/api/app/job_analysis/application/opks_authoring.py`
- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`
- Modify: `apps/api/app/job_analysis/application/authoring.py`
- Modify: `apps/api/app/job_analysis/application/proposal_decisions.py`
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Generate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Generate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `packages/job-analysis-contract/tests/test_schema.py`
- Modify: `apps/api/app/api/job_analysis_mapper.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Modify: `apps/api/app/api/job_analysis_problems.py`
- Create: `apps/api/tests/test_job_analysis_opks_authoring_postgres.py`
- Modify: `apps/api/tests/test_job_analysis_mapper.py`
- Modify: `apps/api/tests/test_job_analysis_api.py`
- Modify: `docs/design/task-analysis-engine.md`

**HTTP contract:**

```text
POST   /api/v1/job-analysis/documents/{document_id}/opks
PUT    /api/v1/job-analysis/documents/{document_id}/opks/{entity_id}
DELETE /api/v1/job-analysis/documents/{document_id}/opks/{entity_id}
```

`OpksItemWrite` 只帶 `entity_kind`、`text`、`task_refs[]`、`indicator_refs[]`；不接受 client 傳 Evidence 或 ID。add 的 `entity_id` 由 `Idempotency-Key` 決定性產生，edit/delete 使用 path ID。`DocumentView` 與 `ConsultationView` 增加 `opks_items[]`；wire view 可顯示 evidence quotes，但不可洩漏 Journal payload 或 authority generation。

- [ ] **Step 1: 寫 application 紅測試**

  測 add/edit/delete、相同 key replay、不同 payload 同 key conflict、非空 text、refs cardinality、edit 後 Evidence 只指向新 direct-edit entry、application 配發 ID、全程零 LLM call。

- [ ] **Step 2: 寫 Task topology 變更的 OPKS 一致性紅測試**

  員工直接刪 Task，或接受既有 Task Proposal 的 withdraw／merge／split 時，必須在同一 authority transaction：刪除已離開 Current JD 的 Task 所擁有的 O/P；從 K/S 移除舊 Task refs 與已刪 Indicator refs；K/S 無 refs 時合法保留為 unlinked；A 不變。不得留下 O/P 指向不存在 Task，也不得靠 DB cascade 靜默猜語意；merge／split 不得把舊 refs 自動猜成新 Task。此步要在員工可建立 OPKS 的同一 commit 完成，不能把中間工作樹留成「OPKS 一存在，既有 Task 決策就驗證失敗」。

- [ ] **Step 3: 實作 Journal payload 與 authoring service**

  新 `OpksDirectEditPayload` 映射既有 Journal kind `direct_edit`，使用獨立 schema ID `job-analysis-opks-direct-edit/1`；payload 保存 action、before、after。SourceRef 仍是 `{kind: direct_edit, id: entry_id}`，不增加 SourceKind。

- [ ] **Step 4: 擴充 JSON Schema SSOT 並 codegen**

  ```powershell
  npm run codegen --workspace=@caliburn/job-analysis-contract
  npm run check-codegen --workspace=@caliburn/job-analysis-contract
  ```

  生成檔禁止手改。`OpksItemWrite.text` 空白由 mapper trim 後回 `invalid-request`；不存在的項目回 `opks-item-not-found` problem type，加入既有 Problem URI enum 與 Web exhaustive switch 的後續契約。

- [ ] **Step 5: 實作薄 mapper／routes 並跑 gate**

  ```powershell
  uv run pytest tests/test_job_analysis_opks_authoring_postgres.py tests/test_job_analysis_mapper.py tests/test_job_analysis_api.py -q
  uv run pytest tests/test_job_analysis_authoring_postgres.py tests/test_job_analysis_authority_commit.py -q
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/api packages/job-analysis-contract docs/design/task-analysis-engine.md
  git commit -m "feat(job-analysis): add employee OPKS editing"
  ```

---

### Task 4: OPKS Proposal 決策與拒絕記憶

**Files:**

- Create: `apps/api/app/job_analysis/application/opks_proposals.py`
- Modify: `apps/api/app/job_analysis/application/authority_commit.py`
- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Modify: `apps/api/app/job_analysis/application/opks_authoring.py`
- Modify: `apps/api/app/job_analysis/application/authoring.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Generate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Generate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `packages/job-analysis-contract/tests/test_schema.py`
- Modify: `apps/api/app/api/job_analysis_mapper.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Create: `apps/api/tests/test_job_analysis_opks_proposals_postgres.py`
- Modify: `apps/api/tests/test_job_analysis_authority_commit.py`
- Modify: `apps/api/tests/test_job_analysis_api.py`
- Modify: `docs/design/task-analysis-engine.md`

**Decision contract:**

```text
pending  → deferred | accepted | edited | rejected | stale
deferred → accepted | edited | rejected | stale
accepted | edited | rejected | stale = terminal（無後續轉移）
```

`unknown` 的 Web decision 送 `deferred`。`edited_after` 是完整 snapshot，但 validator 強制除 `text` 外等於原始 `after`。`accepted` 套用 `after`；`edited` 套用 `edited_after` 並另鑄 direct-edit Source；`rejected`／`deferred` 不改 Current JD；`stale` 只有 application 可寫。

- [ ] **Step 1: 寫決策與 replay 紅測試**

  覆蓋六態轉移、terminal 不可再決定、accept 不鑄 Evidence、edited 必須真的改字才可決定、edited 同交易寫 proposal-decision Journal 與 direct-edit Journal、rejected reason 持久、deferred reload、相同 decision ID replay、不同 payload conflict。

- [ ] **Step 2: 寫 stale 紅測試**

  三條規則逐條測：target 消失；refs Task 不存在／退休；同 entity 的另一 Proposal 先 accepted。再測 direct edit 與 Task delete 會讓相關 pending/deferred OPKS Proposal stale，並保留員工可見 `stale_reason`；terminal proposal 不改成 stale。

  同一組 regression 必須涵蓋既有 Task Proposal 決策：Task 3 已完成的 O/P 移除與 K/S refs prune 語意保持不變，並在同一交易把相關 pending/deferred OPKS Proposal 標 stale；terminal OPKS Proposal 不變。

- [ ] **Step 3: 把 authority seam 的 Journal 參數收斂成 tuple**

  ```python
  async def commit_authority_change(
      ...,
      journal_entries: tuple[JournalEntry, ...] = (),
      ...,
  ) -> None: ...
  ```

  更新既有 Task direct edit／Task Proposal caller，只做簽章與迴圈的 move-first 修改；不得改其語意。這讓 edited OPKS decision 可在同交易寫兩筆 Journal，而不繞過共同 seam。

- [ ] **Step 4: 實作 OPKS decision service 與 transport contract**

  新 route：

  ```text
  POST /api/v1/job-analysis/documents/{document_id}/opks-proposals/{proposal_id}/decisions
  ```

  `OpksProposalDecisionWrite` 只允許 `accepted|edited|rejected|deferred`；`edited_after` 只是一段員工文字，mapper 以原 Proposal 組出完整 snapshot。`ConsultationView` 增加 `opks_proposals[]`，UI 所需 operation grouping 欄位保留。

- [ ] **Step 5: Gate**

  ```powershell
  npm run codegen --workspace=@caliburn/job-analysis-contract
  npm run check-codegen --workspace=@caliburn/job-analysis-contract
  uv run pytest tests/test_job_analysis_opks_proposals_postgres.py tests/test_job_analysis_authority_commit.py tests/test_job_analysis_api.py -q
  uv run pytest tests/test_job_analysis_proposal_decisions_postgres.py tests/test_job_analysis_authoring_postgres.py -q
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/api packages/job-analysis-contract docs/design/task-analysis-engine.md
  git commit -m "feat(job-analysis): add OPKS proposal decisions"
  ```

---

### Task 5: OPKS Context、wire schema 與 deterministic verifier

**Files:**

- Create: `apps/api/app/job_analysis/application/opks_context.py`
- Create: `apps/api/app/job_analysis/application/opks_verifier.py`
- Create: `apps/api/app/job_analysis/llm/opks_result.py`
- Create: `apps/api/app/job_analysis/llm/opks_wire.py`
- Create: `apps/api/app/job_analysis/llm/opks_prompt.py`
- Create: `apps/api/app/job_analysis/llm/schemas/opks_result_v1.json`
- Modify: `apps/api/app/job_analysis/llm/__init__.py`
- Modify: `apps/api/app/job_analysis/domain/task.py`
- Modify: `apps/api/app/job_analysis/application/context.py`
- Modify: `apps/api/tests/test_job_analysis_domain.py`
- Modify: `apps/api/tests/test_job_analysis_context.py`
- Create: `apps/api/tests/test_job_analysis_opks_context.py`
- Create: `apps/api/tests/test_job_analysis_opks_wire.py`
- Create: `apps/api/tests/test_job_analysis_opks_verifier.py`
- Create: `apps/api/tests/test_job_analysis_opks_prompt.py`
- Modify: `docs/design/task-analysis-engine.md`

**Packet scope:** 僅選定 Task 的完整語意與有效員工來源（`employee_turn`／`direct_edit`）、該 Task 的現有 O/P、全文件既有 K/S ordinal、相關 pending/deferred/rejected OPKS Proposal。不得送內部 ID、整份 transcript、不相關 Task、A、taxonomy 或公版資料。若 selected Task 沒有任何有效員工 Evidence，application 在 provider 前回 typed `OpksGroundingUnavailable`，不得用職稱先驗生成。員工手動建立的 Task 即使只有 `direct_edit` 來源也可進 operation；內容不足時由模型 `uncertain`／abstain，不在 application 假裝它沒有來源。

**Wire shape:**

```json
{
  "items": [
    {
      "entity_kind": "output|indicator|knowledge|skill",
      "decision": "add_new|reuse_existing|revise_existing|remove_existing|uncertain",
      "target_ordinal": 0,
      "text": ""
    }
  ]
}
```

所有欄位 required，不用 nullable union：`0`／`""` 是 wire-only sentinel，mapping 後不得進 domain。`add_new` 要 `target_ordinal=0,text!=blank`；`reuse_existing` 只允許 K/S、target>0、text 空；`revise_existing` target>0 且 text 非空；`remove_existing` target>0 且 text 空；`uncertain` target=0 且 text 空。A 不在 enum。

- [ ] **Step 1: 寫 Context 紅測試**

  測 ordinal 決定性、不同 namespace 不混用、rendering 零內部 ID、只帶有效員工 Evidence、既有 K/S 跨 Task可見、拒絕記憶只取相關項目、pending proposal 明標「待決而非事實」。

- [ ] **Step 2: 寫 wire／portable schema 紅測試**

  測 committed golden、`additionalProperties:false`、零 nullable union、provider schema lint、schema name 無點、`$ref` 無 sibling keyword、欄位／enum budget 固定。不得重開 Task schema 或把 OPKS 塞入 `task_analysis_result_v2`。

- [ ] **Step 3: 寫 verifier 紅測試**

  測五種 decision mapping、ordinal 範圍、kind 相符、同 target 不重複、O/P target 必屬選定 Task、K/S reuse 可追加 selected Task ref、`uncertain` 不建立 Proposal。單 Task operation 的 K/S `remove_existing` 只解除 selected Task 與該 Task Indicator 的 refs，永遠映射為 revise；即使因此成為 unlinked 也保留文件層 entity，不得刪掉其他 Task 仍使用或目前未連結的 K/S。目標原本與 selected Task 無關時拒絕該 model item。模型新建 K/S 第一版只連 selected Task，`indicator_refs` 留空，不增加同批 item 間的臨時 reference 語法。Verifier 不判「K/S 是否真的必要」「Indicator 是否可觀察」「數字是否合理」。

- [ ] **Step 4: 實作 pure packet／mapping／verifier／prompt**

  Prompt 只放 ADR 0048 的核心規則：behavior-first、O/P/K/S 定義、不得補官樣句或數字、Evidence 不足就 abstain、K/S 優先 reuse。Attitude、taxonomy、proficiency、匯出編碼不得出現在 prompt。

- [ ] **Step 5: OPKS operation 就緒後才退役舊 hint，並 Gate**

  從 `TaskFields` 移除 `deliverable_hint`／`success_criterion_hint`，同步刪除 Context rendering 與只依賴這兩欄的 fixture。此步不得新增 replacement 欄位；正式 O/P 已由 `CurrentJdOpks` 承擔。不得提前到 Task 1，避免在 O/P 尚未接上前製造暫時功能缺口。

  ```powershell
  rg -n "deliverable_hint|success_criterion_hint" apps/api/app/job_analysis apps/api/tests
  uv run pytest tests/test_job_analysis_opks_context.py tests/test_job_analysis_opks_wire.py tests/test_job_analysis_opks_verifier.py tests/test_job_analysis_opks_prompt.py tests/test_job_analysis_context.py tests/test_job_analysis_wire_schema.py -q
  ```

  Expected: `rg` 零 production hit；歷史 migration／文檔不在此 gate。

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/api/app/job_analysis apps/api/tests docs/design/task-analysis-engine.md
  git commit -m "feat(job-analysis): define grounded OPKS model operation"
  ```

---

### Task 6: One-stage OPKS operation 與 durable proposal generation

**Files:**

- Create: `apps/api/app/job_analysis/application/opks_operation.py`
- Create: `apps/api/app/job_analysis/application/opks_generation.py`
- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Modify: `apps/api/app/api/job_analysis_mapper.py`
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Generate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Generate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `packages/job-analysis-contract/tests/test_schema.py`
- Create: `apps/api/tests/test_job_analysis_opks_operation.py`
- Create: `apps/api/tests/test_job_analysis_opks_generation_postgres.py`
- Modify: `apps/api/tests/test_job_analysis_api.py`
- Modify: `docs/design/task-analysis-engine.md`

**Flow:**

```text
committed replay check
→ load immutable authority snapshot
→ build selected-Task OPKS packet
→ transaction 外一次 OpenRouter HTTP
→ parse + local verifier
→ re-lock document and compare authority generation/read-set
→ application resolves ordinals / derives stable IDs
→ create one OpksProposal per item
→ Journal generation receipt + authority CAS + atomic commit
```

新 endpoint：

```text
POST /api/v1/job-analysis/documents/{document_id}/tasks/{task_id}/opks-proposals
```

使用 `Idempotency-Key`；同 key replay 不打第二次 provider。回 `OpksGenerationView { outcome: proposed|no_grounded_candidates, proposal_ids[] }`。Provider failure/refusal/invalid/rejected 都不寫 Current JD 或 Proposal；route 沿用顧問 unavailable problem，不暴露 provider 細節。

- [ ] **Step 1: 寫 operation outcome 紅測試**

  覆蓋 verified/rejected/invalid_output/refused/failed；斷言 adapter 一次、schema/instructions 是 OPKS 專用、packet 字串無內部 ID、Task operation 完全不變。

- [ ] **Step 2: 寫 durable generation 紅測試**

  覆蓋 provider-before-commit、同 key replay 零 call、不同 Task 同 key conflict、authority 改變即丟棄、零候選也有 receipt、add ID 由 operation+kind+position 決定、reuse 解析成既有 `entity_id` 的 revise Proposal。

- [ ] **Step 3: 實作 generation Journal receipt**

  `OpksGenerationPayload` 使用 Journal kind `opks_generation`、schema ID `job-analysis-opks-generation/1`，保存 operation ID、selected Task ID、outcome、proposal IDs；migration 0014 已預先允許該 kind。它只做 replay/audit，不是 Evidence Source。

- [ ] **Step 4: 實作 durable service 與 route**

  模型 item index 從 0 起，ID 格式固定：

  ```python
  entity_id = f"{operation_id}-{kind_prefix}{item_index}"
  proposal_id = f"{operation_id}-op{item_index}"
  ```

  `kind_prefix` 固定 `o|p|k|s`。不得把 ordinal 寫入持久化資料。

  `reuse_existing` 若沒有新增 Task ref、Evidence 或文字變更，視為 no-op，不建立一張內容完全相同的 Proposal；該 operation 仍由 generation receipt 完成冪等記錄。

- [ ] **Step 5: Gate**

  ```powershell
  npm run codegen --workspace=@caliburn/job-analysis-contract
  npm run check-codegen --workspace=@caliburn/job-analysis-contract
  uv run pytest tests/test_job_analysis_opks_operation.py tests/test_job_analysis_opks_generation_postgres.py tests/test_job_analysis_api.py -q
  uv run pytest tests/test_job_analysis_operation.py tests/test_job_analysis_durable_turn_postgres.py -q
  ```

- [ ] **Step 6: Commit**

  ```powershell
  git add apps/api packages/job-analysis-contract docs/design/task-analysis-engine.md
  git commit -m "feat(job-analysis): generate durable OPKS proposals"
  ```

---

### Task 7: Local Web OPKS editor 與 Proposal review

**Files:**

- Create: `apps/web/src/components/workspace/OpksEditor.tsx`
- Create: `apps/web/src/components/workspace/OpksItemForm.tsx`
- Create: `apps/web/src/components/workspace/OpksProposalCard.tsx`
- Modify: `apps/web/src/components/workspace/ConsultationWorkspace.tsx`
- Modify: `apps/web/src/components/workspace/TaskEditor.tsx`
- Modify: `apps/web/src/components/workspace/ConsultationPanel.tsx`
- Modify: `apps/web/src/lib/jobAnalysisApi.ts`
- Modify: `apps/web/src/lib/jobAnalysisQueries.ts`
- Create: `apps/web/src/lib/jobAnalysisOpks.ts`
- Create: `apps/web/src/lib/jobAnalysisOpks.test.ts`
- Modify: `apps/web/src/lib/jobAnalysisApi.test.ts`
- Modify: `apps/web/src/lib/jobAnalysisQueries.test.ts`
- Modify: `apps/web/README.md`
- Modify: `docs/design/task-analysis-engine.md`

**UX scope:**

- 每個 Task 下顯示 O/P/K/S；空集合顯示「尚未填寫」，不建立 placeholder row。
- 「產生 O/P/K/S 建議」一次建立多張 proposal card；UI 依 `operation_id` 分組，但每項仍獨立 accept/edit/reject/defer。
- K/S 可在多個 Task 下投影同一 `entity_id`，不得複製成多筆；A 在文件層獨立區塊，第一版只有員工新增／編輯／刪除。
- edited 只開文字欄，不提供 refs/topology editor；需要改連結時先 reject，再由員工手動建立或重新生成。
- 所有人工編輯按「儲存」才寫入，沿用 dirty guard、`beforeunload`、`onNavigate` 與 Ctrl/Cmd+Enter；不加 autosave、第二份 client store 或 Server Action。

- [ ] **Step 1: 寫 pure Web helpers 紅測試**

  測按 Task 分組、不複製 K/S identity、A 只出現在文件層、空集合文字、Proposal operation grouping、`unknown` 轉 `deferred`、edited payload 只帶文字、known problem type exhaustive mapping。

- [ ] **Step 2: 擴充 API client 與 query invalidation**

  新 mutation 都重用失敗時的同一 Idempotency-Key；成功後 invalidate document + consultation，不手動 patch 第二份 cache。generation pending 時禁重複按鈕。

- [ ] **Step 3: 實作最小 editor 與 proposal cards**

  使用既有 Button/Card/Form primitive，不引入新表單 library、drag-and-drop、toast framework 或 component test framework。錯誤以現有 inline `aria-live` 呈現。

- [ ] **Step 4: Gate**（working directory: `apps/web`）

  ```powershell
  npm run test -- src/lib/jobAnalysisOpks.test.ts src/lib/jobAnalysisApi.test.ts src/lib/jobAnalysisQueries.test.ts
  npx tsc --noEmit
  npm run lint
  ```

- [ ] **Step 5: Commit**

  ```powershell
  git add apps/web docs/design/task-analysis-engine.md
  git commit -m "feat(web): edit and review OPKS items"
  ```

---

### Task 8: Scripted vertical、全量 gate 與交付文檔

**Files:**

- Create: `apps/api/tests/test_job_analysis_opks_vertical_postgres.py`
- Create: `apps/api/scripts/job_analysis_opks_smoke.py`
- Modify: `docs/design/task-analysis-engine.md`
- Modify: `docs/README.md`
- Modify: `docs/plans/2026-08-01-job-analysis-opks-first-slice-plan.md`

**Scripted scenarios:**

1. 有 employee-turn Evidence 的 Task → fake provider 產生 O/P/K/S Proposal，A 為空。
2. 同 operation replay → generation HTTP 呼叫仍為 1，ID 與 Proposal 不重複。
3. 員工分別 accept、edit、reject、defer 四筆 → reload 後狀態、Evidence 與拒絕理由正確。
4. 員工手動新增、修改、刪除 A → Current JD 與 Journal 同交易、零 LLM call。
5. 同一 K/S reuse 到第二個 Task → 保留同一 entity ID、追加 Task ref，不用文字相似度。
6. 刪除 Task → O/P cascade、K/S refs prune、相關 pending Proposal stale；另一文件完全不受影響。
7. 無有效員工 Evidence 的 Task → provider call 0、Current JD／Proposal／Journal 不變。

- [ ] **Step 1: 寫 PostgreSQL vertical 紅測試與人讀摘要斷言**

  Smoke 必須經真 UoW／repositories／serialization／authority seam，provider 使用 scripted transport；禁止 monkeypatch repository 直接塞最終狀態。

- [ ] **Step 2: 實作最小 smoke driver**

  Driver 僅供本機開發，不加 production route、CLI framework 或 output artifact framework。輸出每個 scenario 的 proposal count、Current JD OPKS count、Journal count 與 provider call count。

- [ ] **Step 3: 跑 focused、contract、Web 與全量 gate**

  Working directory `apps/api`：

  ```powershell
  uv run pytest tests/test_job_analysis_opks_vertical_postgres.py -q
  $tests = Get-ChildItem -LiteralPath tests -Filter 'test_job_analysis_*.py' | Sort-Object Name | ForEach-Object FullName
  uv run pytest @tests -q
  uv run pytest -q
  ```

  Working directory `packages/job-analysis-contract`：

  ```powershell
  npm run check-codegen
  uv run pytest -q
  ```

  Working directory `apps/web`：

  ```powershell
  npm run test
  npx tsc --noEmit
  npm run lint
  ```

  Repo root：

  ```powershell
  git diff --check
  git status --short
  ```

- [ ] **Step 4: 更新 living design 與 plan execution record**

  `task-analysis-engine.md` 必須寫清楚 OPKS 的 domain/persistence/HTTP/model 真實函式名、Employee 與 AI 的共同 commit seam、ordinal→ID 邊界、目前未做項目。Plan 末尾記錄 exact test counts、既有 failure fingerprint、migration head 與 no-network 事實；不得把 scripted smoke 寫成模型品質驗證。

- [ ] **Step 5: Commit**

  ```powershell
  git add apps/api/tests/test_job_analysis_opks_vertical_postgres.py apps/api/scripts/job_analysis_opks_smoke.py docs/design/task-analysis-engine.md docs/README.md docs/plans/2026-08-01-job-analysis-opks-first-slice-plan.md
  git commit -m "test(job-analysis): close the OPKS first slice"
  ```

## Stop conditions

- 任何需求要求建立空白 OPKS row、從 Proposal acceptance 鑄 Evidence、讓模型輸出內部 ID、或把 A 塞進單 Task生成：停線，回讀 0048–0051，不得在程式裡妥協。
- 若 strict OPKS schema 被 provider 拒絕，先記錄展開後 grammar 指標並縮小 wire；不得改成 non-strict 或放寬 local verifier，除非另開 ADR。
- 若 Current JD OPKS 與 Proposal 無法在同一 PostgreSQL transaction／authority CAS 內提交，停線；不得以補償交易或雙寫繞過。
- 若 implementer 想抽通用 Proposal／generic entity／workflow framework，先證明第三個實際 consumer；目前一律拒絕。
- 若任一新增欄位無法指出避免的員工失敗，刪掉，不以「未來可能需要」保留。

## Explicitly deferred

- iCAP 公版匯出與 O/P/K/S/A 編碼。
- Reference Challenger、reference Evidence Source 與 taxonomy linking。
- Attitude AI 生成、自動支持度／效度評分、招募／績效用途。
- proficiency、frequency/importance、批次核准、跨文件 K/S 去重。
- 付費 live model eval；本計畫只做到 deterministic/scripted vertical，真模型另開 bounded smoke。
