# Reviewed Job Analysis Slices Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在現行 Task Analysis／OPKS v3 主線上，選擇性重作並接通 Header、readiness、Duty、Task 職能級別、OPKS 顯示排序、嚴格公版 XLSX，以及兩個 Web 小修與安全診斷；不合併未審遠端分支，也不帶回已否決的 AI／prompt／server 改動。

**Architecture:** Current JD 仍以 `JobAnalysisState` 為 application 真相，所有 Header／Duty／Task／OPKS 人工編輯都走既有 `commit_authority_change()`、Journal、authority generation 與 PostgreSQL 原子交易。Transport contract 只描述 HTTP DTO；readiness 與 export assembly 是 `app/job_analysis` 純函式。XLSX renderer 只吃 `ExportDocument`，不讀 DB、不呼叫 LLM。遠端 commit 只作 donor diff，不 cherry-pick merge commit；每個 task 以當前主線介面重寫並重新驗證。

**Tech Stack:** Python 3.13、Pydantic 2.13、FastAPI 0.115、SQLAlchemy 2.0 async、PostgreSQL 16、Alembic、openpyxl 3.1、pytest、JSON Schema 2020-12、TypeScript 5、Next.js 16.2.6、React 19、TanStack Query v5、Vitest。

**Authority:** [選擇性移植審查](../specs/2026-08-08-unreviewed-branches-review.md) §16、[ADR 0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md)、[ADR 0053](../adr/0053-jd-header-authority-boundary-and-readiness-scope.md)、[ADR 0054](../adr/0054-opks-progressive-elicitation-and-scheduled-child-operation.md)、[ADR 0056](../adr/0056-strict-public-jd-xlsx-export.md)、[Task Analysis Engine](../design/task-analysis-engine.md)。本計畫與 donor branch 衝突時，以這些現行文件為準。

## Global Constraints

- 執行前用 `superpowers:using-git-worktrees` 從本計畫所在 HEAD 建立隔離 worktree；不得直接在未審遠端分支施工。
- donor commits 只供人工比對：Header `47e2840..26cbe90`、Duty `7e1f9de..ac3d3ea`、OPKS order `c59d15c..b2ba8c6`、export `14feb32..80ed7cb`、混合修正 `42b7118`。**不得整顆 cherry-pick**，尤其不得帶入其舊 OPKS schema／scheduler 或 16K token 預設。
- 保留現行 `task_analysis_result_v3`、ADR 0054 自動 OPKS child、gap／`issue_resolutions[]` 與 `4096` token 預設。
- 唯一獲准的 Task Analysis prompt 新增句是：「`員工填寫的整體描述`是背景不是做過的事；其中提到但訪談沒談過的責任，先追問怎麼做。」不得順手改 Task、P、K/S 判準或 OPKS prompt。現行 prompt byte budget `6000` 不調高。
- `JdHeader` 只進 Task Analysis packet；不得進 OPKS packet，不配 ordinal／`SourceRef`，也不得單靠它產生任何 Task change。
- Header、Duty、Task level 與 OPKS 排序全部是員工 authority；模型 wire schema 不新增這些可寫欄位。
- 不做：reference／taxonomy、AI Duty 按鈕或 operation、per-Task 子對話、server／enterprise、舊 R1 harness、舊資料搬遷、PDF／DOCX、通用匯出 framework、登入／SaaS／多使用者。
- XLSX 只有一張官方 `職能基準表`；無第二張缺漏表、無產品聲明、無自創資料列。Web 可更豐富，匯出只含公版欄位。
- 每個 task 先紅測試、再最小實作、再 focused gate；一個 task 一個 commit，綠了才 commit；不 push。
- 動到端到端行為時，同一 commit 更新 `docs/design/task-analysis-engine.md`；不要最後一次補寫。

## Donor 使用方式

每個 task 可用下列命令查看 donor，但只能手動帶入已列出的行為：

```powershell
git show <commit> -- <path>
git diff <commit>^ <commit> -- <path>
```

禁止以 donor 的 ADR 0058–0061、舊 plan checkbox 或 commit message 取代本計畫的驗收條件。

---

### Task 1: Header domain 與第一版 readiness 純函式

**Files:**
- Create: `apps/api/app/job_analysis/domain/jd_header.py`
- Create: `apps/api/app/job_analysis/application/readiness.py`
- Modify: `apps/api/app/job_analysis/domain/__init__.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`
- Modify: `apps/api/app/job_analysis/application/transition.py:73`
- Test: `apps/api/tests/test_job_analysis_jd_header.py`
- Test: `apps/api/tests/test_job_analysis_readiness.py`
- Docs: `docs/design/task-analysis-engine.md`

**Interfaces:**
- Produces: `JdHeader`, `ReadinessIssueCode`, `ReadinessIssue`, `DocumentReadiness`, `assess_readiness(header: JdHeader) -> DocumentReadiness`.
- `JobAnalysisState.jd_header: JdHeader` **為必填**；不 import `job_analysis_contract`。新文件由建立／載入端明確傳入 `JdHeader()`，不得用 state 預設掩蓋漏傳。

- [ ] **Step 1: Write failing domain and readiness tests**

```python
def test_header_accepts_blank_fields_but_rejects_blank_strings_and_bad_levels():
    assert JdHeader().is_empty
    with pytest.raises(ValidationError):
        JdHeader(competency_name="")
    with pytest.raises(ValidationError):
        JdHeader(competency_level=7)

def test_readiness_only_reports_three_certain_header_gaps():
    result = assess_readiness(JdHeader())
    assert [issue.code for issue in result.issues] == [
        ReadinessIssueCode.COMPETENCY_NAME_MISSING,
        ReadinessIssueCode.WORK_DESCRIPTION_MISSING,
        ReadinessIssueCode.COMPETENCY_LEVEL_MISSING,
    ]
    assert not hasattr(result, "is_complete")

def test_state_requires_every_new_authority_partition_explicitly():
    with pytest.raises(ValidationError):
        JobAnalysisState()
```

另測 `occupation_*`、`industry_*`、`notes` 空白不列 issue，且 domain AST guard 仍禁止 transport import。

- [ ] **Step 2: Run the tests and confirm the missing types fail**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_jd_header.py tests/test_job_analysis_readiness.py -q`

Expected: collection／import failure for the new types.

- [ ] **Step 3: Implement the minimal immutable models and pure function**

```python
class JdHeader(DomainModel):
    competency_name: NonEmptyText | None = None
    occupation_category_name: NonEmptyText | None = None
    occupation_name: NonEmptyText | None = None
    occupation_code: NonEmptyText | None = None
    industry_name: NonEmptyText | None = None
    industry_code: NonEmptyText | None = None
    work_description: NonEmptyText | None = None
    competency_level: int | None = Field(default=None, ge=1, le=6)
    notes: NonEmptyText | None = None
```

Readiness 只檢查名稱、工作描述、基準級別；不建立百分比或 `ready` boolean。同步修改所有 production／test `JobAnalysisState(...)` construction site，明確傳入 `jd_header`；這個刻意的紅燈用來抓漏傳，而不是加回 default。

- [ ] **Step 4: Run focused tests and dependency guard**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_jd_header.py tests/test_job_analysis_readiness.py tests/test_job_analysis_dependencies.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis apps/api/tests/test_job_analysis_jd_header.py apps/api/tests/test_job_analysis_readiness.py docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): add JD header and readiness domain"
```

---

### Task 2: Header PostgreSQL persistence 與 authority state 保真

**Files:**
- Create: `apps/api/alembic/versions/0015_job_analysis_jd_header.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/models.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/repositories.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/serialization.py`
- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Modify: `apps/api/app/job_analysis/application/authority_commit.py`
- Modify: `apps/api/app/job_analysis/application/durable_turn.py`
- Modify: all current authority writers under `apps/api/app/job_analysis/application/`
- Test: `apps/api/tests/test_job_analysis_jd_header_persistence.py`
- Test: `apps/api/tests/test_job_analysis_authority_commit.py`
- Test: `apps/api/tests/test_job_analysis_migration.py`

**Interfaces:**
- Produces: required `DocumentRecord.jd_header: JdHeader`, schema id `job-analysis-jd-header/1`.
- All `JobAnalysisState` loaders and `commit_authority_change()` calls preserve Header even when only Task／Proposal／OPKS changes.

- [ ] **Step 1: Write persistence and migration red tests**

```python
def test_document_record_requires_an_explicit_header(existing_document_record):
    payload = existing_document_record.model_dump(exclude={"jd_header"})
    with pytest.raises(ValidationError):
        DocumentRecord.model_validate(payload)

def test_0015_backfills_existing_documents_with_an_empty_header(migrated_document_row):
    row = migrated_document_row
    assert row.jd_header_schema_id == "job-analysis-jd-header/1"
    assert row.jd_header_json == {}
```

涵蓋 direct edit、proposal decision、durable turn、OPKS authoring／generation 的「沒改 Header 就原樣帶過」。

- [ ] **Step 2: Run focused tests and confirm missing columns／fields fail**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_jd_header_persistence.py tests/test_job_analysis_authority_commit.py tests/test_job_analysis_migration.py -q`

Expected: FAIL before migration/model changes.

- [ ] **Step 3: Add migration 0015 and repository serialization**

Migration adds non-null `jd_header_schema_id` and JSONB `jd_header_json` on `job_analysis_documents`, backfilled to `{}` with schema id `/1`; no second table and no legacy-system migration.

```python
JD_HEADER_SCHEMA_ID = "job-analysis-jd-header/1"

class DocumentRecord(DomainModel):
    jd_header: JdHeader
```

- [ ] **Step 4: Thread Header through the one authority commit seam**

Every state reconstruction must use `record.jd_header`; every authority update serializes `next_state.jd_header`. Do not add a Header-only commit path that bypasses Journal／generation／CAS.

- [ ] **Step 5: Run persistence gates**

Run: `cd apps/api; uv run pytest -k "job_analysis and (migration or persistence or authority_commit or durable_turn or proposal_decisions or opks_generation)" -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/alembic/versions/0015_job_analysis_jd_header.py apps/api/app/adapters/job_analysis_postgres apps/api/app/job_analysis/application apps/api/tests docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): persist JD header with current authority"
```

---

### Task 3: Header authoring API 與共享 Web contract

**Files:**
- Modify: `apps/api/app/job_analysis/application/authoring.py`
- Modify: `apps/api/app/job_analysis/application/errors.py`
- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/serialization.py`
- Modify: `apps/api/app/api/job_analysis_mapper.py`
- Modify: `apps/api/app/api/job_analysis_problems.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Regenerate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Regenerate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Test: `apps/api/tests/test_job_analysis_authoring_postgres.py`
- Test: `apps/api/tests/test_job_analysis_api_postgres.py`
- Test: `packages/job-analysis-contract/tests/test_schema.py`

**Interfaces:**
- Produces: `put_jd_header(uow_factory, *, document_id: UUID, entry_id: str, header: JdHeader) -> JdHeader`.
- Journal: `JdHeaderDirectEditPayload(before, after)` with schema id `job-analysis-jd-header-direct-edit/1`; Header edits are authority history, **not Task Evidence**, so they do not create a `SourceRef`.
- HTTP: `PUT /api/v1/job-analysis/documents/{document_id}/jd-header`, requires `Idempotency-Key`.
- Contract: `JdHeaderWrite`, `JdHeaderView`, `DocumentReadinessView`; `DocumentView` carries `jd_header` and `readiness`.

- [ ] **Step 1: Write red tests for normalization, idempotency and authority effects**

```python
async def test_put_header_trims_and_maps_empty_optional_text_to_none(client):
    response = await client.put(
        f"/api/v1/job-analysis/documents/{document_id}/jd-header",
        headers={"Idempotency-Key": "header-1"},
        json={"competency_name": " 門市營運專員 ", "notes": "   ", "competency_level": 4},
    )
    assert response.status_code == 200
    assert response.json()["competency_name"] == "門市營運專員"
    assert response.json()["notes"] is None
```

另測 Journal 有 typed direct-edit receipt、generation +1、同 key 同 payload replay、同 key 不同 payload typed 409、no-op／值域錯誤 typed 422。

- [ ] **Step 2: Run red tests**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_authoring_postgres.py tests/test_job_analysis_api_postgres.py -k "header" -q`

Expected: FAIL because route and DTOs do not exist.

- [ ] **Step 3: Implement `put_jd_header()` through `commit_authority_change()`**

新增最小 `JdHeaderDirectEditPayload(before, after)` 並接進既有 Journal payload deserializer；`before == after` 以 typed invalid request 拒絕。Header 是整體背景而非 Task Evidence，**不得建立 `SourceRef`**。不呼叫 LLM。The mapper owns `trim -> None`; blank optional text must never enter domain.

- [ ] **Step 4: Extend schema and regenerate both languages**

Run:

```powershell
cd packages/job-analysis-contract
npm run codegen
npm run check-codegen
uv run pytest -q
```

Expected: generated Python／TS match the JSON Schema exactly.

- [ ] **Step 5: Run API and contract tests**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_api.py tests/test_job_analysis_api_postgres.py tests/test_job_analysis_mapper.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api packages/job-analysis-contract docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): expose JD header and readiness"
```

---

### Task 4: Header 作為 Task Analysis 背景、不是 Evidence

**Files:**
- Modify: `apps/api/app/job_analysis/application/context.py:290`
- Modify: `apps/api/app/job_analysis/application/durable_turn.py`
- Modify: `apps/api/app/job_analysis/llm/prompt.py`
- Test: `apps/api/tests/test_job_analysis_context.py`
- Test: `apps/api/tests/test_job_analysis_prompt.py`
- Test: `apps/api/tests/test_job_analysis_opks_context.py`
- Docs: `docs/design/task-analysis-engine.md`

**Interfaces:**
- `build_context_packet` 新增 keyword-only `employee_written_overview: str | None`，並渲染一個獨立背景區。
- Header changes belong to Task Analysis authority read-set; OPKS packet stays byte-for-byte unchanged for the same Task state.

- [ ] **Step 1: Write red boundary tests**

```python
def test_employee_overview_is_background_without_ordinal_or_source_ref(packet_inputs):
    packet = build_context_packet(
        **packet_inputs,
        employee_written_overview="負責門市營運",
    )
    rendered = render_context_packet(packet)
    assert "員工填寫的整體描述" in rendered
    assert "負責門市營運" in rendered
    assert "task-" not in rendered
    assert "source_ref" not in rendered
```

另在既有 OPKS packet fixture 上斷言 rendering 不含「員工填寫的整體描述」；header 在 provider 執行期間改變必須使 authority snapshot stale，不讓舊分析覆蓋新描述。

- [ ] **Step 2: Run red tests**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_context.py tests/test_job_analysis_prompt.py tests/test_job_analysis_opks_context.py -q`

Expected: FAIL before packet field is added.

- [ ] **Step 3: Add exactly one prompt rule and no other prompt edits**

```text
「員工填寫的整體描述」是背景不是做過的事；其中提到但訪談沒談過的責任，先追問怎麼做。
```

Verifier 仍要求 Task change 的 evidence anchor 指向員工回合／direct edit；Header 沒有 `SourceRef`，因此不能單靠 Header 建 Task。保留 `INSTRUCTIONS_BYTES_BUDGET = 6000`。

- [ ] **Step 4: Run prompt/context tests and inspect the exact diff**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_context.py tests/test_job_analysis_prompt.py tests/test_job_analysis_opks_context.py -q`

Then: `git diff -- apps/api/app/job_analysis/llm/prompt.py`

Expected: prompt diff only contains the approved background rule.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis/application/context.py apps/api/app/job_analysis/application/durable_turn.py apps/api/app/job_analysis/llm/prompt.py apps/api/tests docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): show employee header overview to task analysis"
```

---

### Task 5: Header 與 readiness Web 編輯面

**Files:**
- Create: `apps/web/src/components/workspace/JdHeaderForm.tsx`
- Create: `apps/web/src/components/workspace/ReadinessNotice.tsx`
- Create: `apps/web/src/lib/jobAnalysisHeader.ts`
- Test: `apps/web/src/lib/jobAnalysisHeader.test.ts`
- Modify: `apps/web/src/lib/jobAnalysisApi.ts`
- Modify: `apps/web/src/lib/jobAnalysisApi.test.ts`
- Modify: `apps/web/src/components/workspace/ConsultationWorkspace.tsx`

**Interfaces:**
- `JdHeaderForm({ documentId, onDirtyChange })` uses explicit Save／Cancel, no autosave.
- `ReadinessNotice` consumes server-provided issue codes only; Web does not recompute readiness.

- [ ] **Step 1: Write red mapper/API tests**

```ts
it("maps empty optional form fields to null", () => {
  expect(toJdHeaderWrite({ competency_name: " 門市營運專員 ", notes: "  " }))
    .toMatchObject({ competency_name: "門市營運專員", notes: null });
});

it("does not call an LLM endpoint when saving header", async () => {
  await putJdHeader("doc-1", "entry-1", header);
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/jd-header"), expect.anything());
});
```

- [ ] **Step 2: Run Web tests and confirm failure**

Run: `cd apps/web; npm run test -- src/lib/jobAnalysisHeader.test.ts src/lib/jobAnalysisApi.test.ts`

Expected: FAIL because helpers/API are missing.

- [ ] **Step 3: Implement the form and notice**

Display all editable Header fields, nullable level 1–6, explicit unsaved state, Save／Cancel, Ctrl/Cmd+Enter save and existing `UnsavedChangesGuard`. Do not render fields for `職能基準代碼` or `職類別代碼`.

- [ ] **Step 4: Run Web gate**

Run:

```powershell
cd apps/web
npm run test -- src/lib/jobAnalysisHeader.test.ts src/lib/jobAnalysisApi.test.ts
npx tsc --noEmit
npm run lint
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web docs/design/task-analysis-engine.md
git commit -m "feat(web): let employees edit the JD header"
```

---

### Task 6: Duty、Task level 與最終 readiness 規則

**Files:**
- Create: `apps/api/app/job_analysis/domain/duty.py`
- Modify: `apps/api/app/job_analysis/domain/proposal.py:141`
- Modify: `apps/api/app/job_analysis/domain/__init__.py`
- Modify: `apps/api/app/job_analysis/application/transition.py:73`
- Modify: `apps/api/app/job_analysis/application/readiness.py`
- Test: `apps/api/tests/test_job_analysis_duty_domain.py`
- Modify: `apps/api/tests/test_job_analysis_readiness.py`
- Modify: `apps/api/tests/test_job_analysis_transition.py`

**Interfaces:**
- Produces: `Duty { duty_id, statement, display_order }`.
- `JdTaskFields` adds `duty_id: DutyId | None` and `competency_level: int | None` (1–6).
- `JobAnalysisState.current_duties: tuple[Duty, ...]` **為必填**，不設 `()` default；final readiness signature: `assess_readiness(*, header, duties, tasks, current_opks) -> DocumentReadiness`.

- [ ] **Step 1: Write red invariants and readiness tests**

```python
def test_state_rejects_a_task_pointing_to_a_missing_duty():
    with pytest.raises(ValidationError):
        JobAnalysisState(
            jd_header=JdHeader(),
            current_duties=(),
            current_jd=(JdTask(task_id="t1", statement="盤點", display_order=0, duty_id="d9"),),
        )

def test_readiness_reports_employee_fixable_structure_gaps_only():
    duty = Duty(duty_id="d1", statement="門市營運", display_order=0)
    task = JdTask(task_id="t1", statement="盤點庫存", display_order=0)
    result = assess_readiness(
        header=JdHeader(),
        duties=(duty,),
        tasks=(task,),
        current_opks=CurrentJdOpks(),
    )
    codes = {issue.code for issue in result.issues}
    assert ReadinessIssueCode.TASK_DUTY_MISSING in codes
    assert ReadinessIssueCode.TASK_COMPETENCY_LEVEL_MISSING in codes
    assert ReadinessIssueCode.DUTY_WITHOUT_TASK in codes
```

新增 `OPKS_TASK_LINK_MISSING`：只針對沒有連到任何 Current JD Task／Indicator 的 K/S，供 Web 提醒「公版匯出不會包含」；不得把沒有 O、沒有 A 或空 notes 判成缺漏。

- [ ] **Step 2: Run red tests**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_duty_domain.py tests/test_job_analysis_readiness.py tests/test_job_analysis_transition.py -q`

Expected: FAIL before Duty and fields exist.

- [ ] **Step 3: Implement domain invariants and preserve employee authority through AI transitions**

```python
class Duty(DomainModel):
    duty_id: DutyId
    statement: NonEmptyText
    display_order: int = Field(ge=0)
```

`JobAnalysisState` enforces unique Duty order and valid nullable Task→Duty refs. `current_duties` is required, so every production reconstruction must preserve it explicitly. AI add defaults both Task fields to `None`; AI revise／merge／split must not silently overwrite employee-set Duty／level. No Duty or level field enters model output schema.

- [ ] **Step 4: Run domain gate**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_duty_domain.py tests/test_job_analysis_readiness.py tests/test_job_analysis_transition.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis/domain apps/api/app/job_analysis/application/readiness.py apps/api/app/job_analysis/application/transition.py apps/api/tests docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): add Duty and task competency level"
```

---

### Task 7: Duty persistence 與原子 authoring

**Files:**
- Create: `apps/api/alembic/versions/0016_job_analysis_jd_duties.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/models.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/repositories.py`
- Modify: `apps/api/app/adapters/job_analysis_postgres/serialization.py`
- Modify: `apps/api/app/job_analysis/application/persistence.py`
- Create: `apps/api/app/job_analysis/application/duty_authoring.py`
- Modify: `apps/api/app/job_analysis/application/authority_commit.py`
- Modify: all authority state loaders/writers
- Test: `apps/api/tests/test_job_analysis_duty_persistence.py`
- Test: `apps/api/tests/test_job_analysis_duty_authoring_postgres.py`
- Test: `apps/api/tests/test_job_analysis_migration.py`

**Interfaces:**
- Produces: `DutyRepository.list/replace` and `add_duty`／`edit_duty`／`delete_duty`／`reorder_duties`.
- Deleting a Duty leaves Tasks active and sets their `duty_id=None` in the same transaction.

- [ ] **Step 1: Write red persistence and authoring tests**

```python
async def test_delete_duty_unassigns_tasks_without_deleting_them(pg_uow_factory):
    await delete_duty(pg_uow_factory, document_id=doc, entry_id="d-del", duty_id="d1")
    loaded = await load_document(pg_uow_factory, doc)
    assert [task.task_id for task in loaded.state.current_jd] == ["t1"]
    assert loaded.state.current_jd[0].duty_id is None
```

另測 deterministic ID、重送冪等、順序完整集合、invalid order typed error、Journal／generation 原子更新。

- [ ] **Step 2: Run red tests**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_duty_persistence.py tests/test_job_analysis_duty_authoring_postgres.py tests/test_job_analysis_migration.py -q`

Expected: FAIL before table/repository exists.

- [ ] **Step 3: Add migration 0016 with relational integrity**

Create `job_analysis_jd_duties`; add nullable `duty_id` and `competency_level` to `job_analysis_jd_tasks`. Use a composite `(document_id, duty_id)` foreign key to duties with `DEFERRABLE INITIALLY DEFERRED`, so delete-and-reinsert `replace()` remains legal inside one transaction while committed rows cannot dangle. Existing Tasks remain unassigned; do not synthesize Duty.

- [ ] **Step 4: Implement the four authoring use cases through the shared seam**

`add_duty` derives `f"{entry_id}-d0"`; edit preserves identity/order; reorder requires the exact current ID set; delete clears Task refs and removes Duty atomically.

- [ ] **Step 5: Run real PostgreSQL focused gate**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_duty_persistence.py tests/test_job_analysis_duty_authoring_postgres.py tests/test_job_analysis_authority_commit.py tests/test_job_analysis_migration.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/alembic/versions/0016_job_analysis_jd_duties.py apps/api/app/adapters/job_analysis_postgres apps/api/app/job_analysis/application apps/api/tests docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): persist and author Duties"
```

---

### Task 8: Duty／Task level contract、API 與 Web editor

**Files:**
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Regenerate: generated Python／TS contract files
- Modify: `apps/api/app/api/job_analysis_mapper.py`
- Modify: `apps/api/app/api/job_analysis_problems.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Create: `apps/web/src/components/workspace/DutyEditor.tsx`
- Create: `apps/web/src/lib/jobAnalysisDuties.ts`
- Test: `apps/web/src/lib/jobAnalysisDuties.test.ts`
- Modify: `apps/web/src/components/workspace/TaskForm.tsx`
- Modify: `apps/web/src/components/workspace/TaskEditor.tsx`
- Modify: `apps/web/src/components/workspace/ConsultationWorkspace.tsx`
- Test: API, mapper, contract and Web form tests

**Interfaces:**
- Contract: `DutyWrite`, `DutyView`, `DutyOrderWrite`; Task write/view gains nullable `duty_id`／`competency_level`.
- Routes: POST／PUT／DELETE `duties`, PUT `duty-order`; all mutations require `Idempotency-Key`.

- [ ] **Step 1: Write red API and Web tests**

```ts
it("serializes an unassigned task without inventing a Duty", () => {
  expect(toTaskWrite({ ...draft, duty_id: "", competency_level: "" }))
    .toMatchObject({ duty_id: null, competency_level: null });
});
```

API tests assert add/edit/delete/reorder, missing Duty 404／invalid order 422, and deleting Duty returns the surviving unassigned Task on reload.

- [ ] **Step 2: Run red gates**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_api_postgres.py tests/test_job_analysis_mapper.py -k "duty or competency" -q`

Run: `cd apps/web; npm run test -- src/lib/jobAnalysisDuties.test.ts src/lib/jobAnalysisForm.test.ts`

Expected: FAIL before contract/routes/components exist.

- [ ] **Step 3: Extend schema, codegen and routes**

Run `npm run codegen && npm run check-codegen` in `packages/job-analysis-contract`; route remains transport-only and maps existing typed application errors.

- [ ] **Step 4: Implement employee UI**

Duty editor supports explicit add/edit/delete/reorder. Task form offers nullable Duty select and nullable level 1–6. Show an explicit「未分組」section; never add AI Duty suggestion or reference search.

Task 的 Up／Down 以**目前可見 Duty group**為相鄰單位，再把那兩個 ID 在完整文件順序中交換；不得把 group 內 index 直接當全域 index。新增 interleaved fixture（`d1:t1, d2:t2, d1:t3`），在 d1 內把 t3 上移後，畫面與 reload 都得到 `d1:[t3,t1]`，且 t2 不被隱藏改位。

- [ ] **Step 5: Run API／contract／Web gate**

Run:

```powershell
cd packages/job-analysis-contract; npm run check-codegen; uv run pytest -q
cd ../../apps/api; uv run pytest tests/test_job_analysis_api_postgres.py tests/test_job_analysis_mapper.py -q
cd ../web; npm run test; npx tsc --noEmit; npm run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api apps/web packages/job-analysis-contract docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): expose Duty authoring in the workspace"
```

---

### Task 9: OPKS display order domain 與 PostgreSQL backfill

**Files:**
- Create: `apps/api/alembic/versions/0017_job_analysis_opks_display_order.py`
- Modify: `apps/api/app/job_analysis/domain/opks.py:40`
- Modify: OPKS persistence and every creation path
- Test: `apps/api/tests/test_job_analysis_opks_backfill.py`
- Modify: OPKS domain／generation／proposal／authoring tests

**Interfaces:**
- `OpksItem.display_order: int >= 0` unique within `(document, entity_kind)`.
- `CurrentJdOpks.next_display_order(kind) -> int` supplies every add/accept path.

- [ ] **Step 1: Write red invariant and backfill tests**

```python
def test_display_order_is_unique_only_within_kind():
    CurrentJdOpks(items=(output(order=0), knowledge(order=0)))
    with pytest.raises(ValidationError):
        CurrentJdOpks(items=(output("o1", 0), output("o2", 0)))
```

Migration test seeds rows with tied timestamps and asserts backfill order equals prior `(created_at, entity_id)` read order, partitioned by document and kind.

- [ ] **Step 2: Run red tests**

Run: `cd apps/api; uv run pytest -k "opks and (domain or backfill or generation or proposal)" -q`

Expected: FAIL before field/migration.

- [ ] **Step 3: Add migration and preserve all current OPKS v3 behavior**

Do not touch `task_analysis_result_v3`, gap fields, `issue_resolutions[]`, scheduler or child IDs. Direct add and accepted proposals use `next_display_order`; edit/revise preserves order; delete does not renumber.

- [ ] **Step 4: Run OPKS regression gate**

Run: `cd apps/api; uv run pytest -k opks -q`

Expected: PASS, including progressive elicitation tests.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/alembic/versions/0017_job_analysis_opks_display_order.py apps/api/app apps/api/tests docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): persist employee OPKS display order"
```

---

### Task 10: OPKS reorder API 與 Web controls

**Files:**
- Modify: `apps/api/app/job_analysis/application/opks_authoring.py`
- Modify: `apps/api/app/job_analysis/application/errors.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Modify: workspace contract and generated files
- Modify: `apps/web/src/components/workspace/OpksEditor.tsx`
- Modify: `apps/web/src/lib/jobAnalysisOpks.ts`
- Modify: `apps/web/src/lib/jobAnalysisApi.ts`
- Test: `apps/api/tests/test_job_analysis_opks_reorder_postgres.py`
- Modify: `apps/web/src/lib/jobAnalysisOpks.test.ts`

**Interfaces:**
- `reorder_opks_items(uow_factory, *, document_id: UUID, entry_id: str, entity_kind: OpksEntityKind, ordered_entity_ids: tuple[str, ...]) -> tuple[OpksItem, ...]`.
- Contract `OpksOrderWrite { entity_kind, ordered_entity_ids }`; PUT `/{document_id}/opks-order`.

- [ ] **Step 1: Write red reorder tests**

Require exact current IDs for one kind; reject duplicates, omissions, foreign-kind IDs and stale IDs; same key replay is idempotent. O can reorder independently of K even when both currently use order 0.

- [ ] **Step 2: Run red tests**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_opks_reorder_postgres.py -q`

Run: `cd apps/web; npm run test -- src/lib/jobAnalysisOpks.test.ts`

Expected: FAIL before use case and controls.

- [ ] **Step 3: Implement API and Up／Down controls**

Keep simple buttons; no drag-and-drop framework. Disable Up at first item and Down at last item. O／P 在各 Task 卡片依可見相鄰項目重排；K／S 與 A 使用文件層清單，每個 entity 只出現一次，shared 與 unlinked K／S 都必須有唯一排序入口。Task 卡可繼續投影其 linked K/S，但不得放第二套會互相打架的排序按鈕。Dirty state participates in the workspace guard.

- [ ] **Step 4: Run OPKS／contract／Web gate**

Run: `cd apps/api; uv run pytest -k opks -q`

Run: `cd packages/job-analysis-contract; npm run check-codegen; uv run pytest -q`

Run: `cd apps/web; npm run test; npx tsc --noEmit; npm run lint`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api apps/web packages/job-analysis-contract docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): let employees reorder OPKS items"
```

---

### Task 11: Web cache／Proposal null 修正與安全診斷

**Files:**
- Modify: `apps/web/src/components/workspace/ConsultationPanel.tsx`
- Modify: `apps/web/src/components/workspace/ProposalCard.tsx`
- Modify: `apps/web/src/lib/jobAnalysisProposals.ts`
- Modify: `apps/web/src/lib/jobAnalysisProposals.test.ts`
- Modify: `apps/api/app/job_analysis/application/durable_turn.py`
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Test: `apps/api/tests/test_job_analysis_api.py`

**Interfaces:**
- Consultation success sets only the complete consultation cache and invalidates the full document query; it never hand-builds a partial `DocumentView`.
- `UncommittableOperationResult` exposes only typed `outcome` and verifier code values for logging.

- [ ] **Step 1: Write red tests for before/after semantics and safe logging**

```ts
it("hides null jd_before entries but labels null jd_after as removal", () => {
  expect(visibleProposalEntries(entries, "before")).toEqual([]);
  expect(visibleProposalEntries(entries, "after")).toEqual(entries);
});
```

Python `caplog` test makes `operation_result.detail` contain a sentinel employee/provider string and asserts the log contains outcome/verifier codes but **not** the sentinel.

- [ ] **Step 2: Run red tests**

Run: `cd apps/web; npm run test -- src/lib/jobAnalysisProposals.test.ts`

Run: `cd apps/api; uv run pytest tests/test_job_analysis_api.py -k "not_committable" -q`

Expected: at least the new assertions fail.

- [ ] **Step 3: Apply only the approved fixes from donor `42b7118`**

Use `consultationQueryOptions(documentId).queryKey` for the complete consultation result; invalidate `jobAnalysisKeys.document(documentId)` and document list. For Proposal, null on `before` means “not yet in JD” and is hidden; null on `after` means removal. Log only exception class, operation outcome and verifier violation codes—never raw `detail`, refusal text, prompt, transcript or provider response.

- [ ] **Step 4: Verify token config and AI files are untouched**

Run:

```powershell
git diff -- apps/api/app/config.py apps/api/tests/test_app_wiring.py apps/api/app/job_analysis/llm apps/api/app/job_analysis/application/opks_scheduler.py
```

Expected: no diff.

- [ ] **Step 5: Run gates and commit**

Run: `cd apps/web; npm run test; npx tsc --noEmit; npm run lint`

Run: `cd apps/api; uv run pytest tests/test_job_analysis_api.py -q`

```powershell
git add apps/web/src apps/api/app/job_analysis/application/durable_turn.py apps/api/app/api/routes/job_analysis.py apps/api/tests/test_job_analysis_api.py
git commit -m "fix(job-analysis): preserve workspace cache and safe diagnostics"
```

---

### Task 12: Deterministic `ExportDocument` assembly

**Files:**
- Create: `apps/api/app/job_analysis/application/export.py`
- Modify: `apps/api/app/job_analysis/application/__init__.py`
- Test: `apps/api/tests/test_job_analysis_export_assembly.py`

**Interfaces:**
- Produces: `ExportOpksEntry`, `ExportTaskEntry`, `ExportDutySection`, `ExportDocument` and `assemble_export_document(state, *, title) -> ExportDocument`.
- No IO, openpyxl or transport imports.

- [ ] **Step 1: Write red projection tests**

```python
def test_position_codes_are_render_time_only_and_follow_display_order():
    document = assemble_export_document(state, title="門市營運專員")
    assert document.duties[0].position_code == "T1"
    assert document.duties[0].tasks[0].position_code == "T1.1"
    assert document.duties[0].tasks[0].outputs[0].position_code == "O1.1.1"
    assert document.duties[0].tasks[0].indicators[0].position_code == "P1.1.1"
```

另測：K/S 文件層碼固定 `K01`／`S01`，同一 entity 可投影到多個 Task 而 entity ID 只一份；indicator refs 可解析回 Task；unassigned Task 保留、Duty/code 為 `None`；unlinked K/S 不進 `ExportDocument` 且 readiness 已有警示。

- [ ] **Step 2: Run red test**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_export_assembly.py -q`

Expected: import failure before module exists.

- [ ] **Step 3: Implement pure sorted projection**

Sort Duties／Tasks／each OPKS kind explicitly by `display_order`; never depend on tuple or database order. `ExportDocument` contains only fields the official table can render; no readiness list, product disclaimer or unlinked custom section.

- [ ] **Step 4: Run test and dependency guard**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_export_assembly.py tests/test_job_analysis_dependencies.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/job_analysis/application/export.py apps/api/app/job_analysis/application/__init__.py apps/api/tests/test_job_analysis_export_assembly.py
git commit -m "feat(job-analysis): assemble deterministic public export"
```

---

### Task 13: One-sheet strict public XLSX renderer

**Files:**
- Create: `apps/api/app/job_analysis/application/export_xlsx.py`
- Create: `apps/api/tests/test_job_analysis_export_xlsx.py`
- Reference: `docs/specs/2026-08-02-icap-2026-quality-manual-form-authority.md` and official PDF attachment 2-2 page 57

**Interfaces:**
- `render_xlsx(document: ExportDocument) -> bytes`.
- `XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`.

- [ ] **Step 1: Write red workbook structure and safety tests**

```python
def test_workbook_has_only_the_official_form_sheet():
    workbook = load_workbook(io.BytesIO(render_xlsx(document)), data_only=False)
    assert workbook.sheetnames == ["職能基準表"]

def test_formula_shaped_employee_text_stays_literal_text():
    document = ExportDocument(
        title="測試職務",
        header=JdHeader(work_description="=1+1"),
    )
    workbook = load_workbook(io.BytesIO(render_xlsx(document)), data_only=False)
    cell = next(
        cell
        for row in workbook.active.iter_rows()
        for cell in row
        if cell.value == "=1+1"
    )
    assert cell.value == "=1+1"
    assert cell.data_type == "s"
```

另測：沒有「iCAP 版型缺漏」／產品聲明／未分組自創標籤；未分組 Task 仍在官方 Task 欄且 Duty cell 空白；長中文 wrap；K/S 共用同碼；空欄保持空；所有 used cells 有官方邊框；必要 merged ranges、landscape、fit-to-width=1、print area 與 repeated header row 正確。

- [ ] **Step 2: Run red tests**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_export_xlsx.py -q`

Expected: import failure before renderer exists.

- [ ] **Step 3: Implement one local text writer and official layout**

```python
def _put_text(sheet: Worksheet, row: int, column: int, value: str | None) -> Cell:
    cell = sheet.cell(row=row, column=column)
    if value is not None:
        cell.value = str(value)
        cell.data_type = "s"
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return cell
```

Employee／model strings all use `_put_text`; numeric competency levels use a separate numeric writer. Do not prefix apostrophes—the saved value must remain exactly the employee text. Add only official template labels and the official iCAP-provided-code notes shown in attachment 2-2.

- [ ] **Step 4: Implement official visual properties without a theme framework**

Use local constants for thin borders, bold headers, centered code/level cells, top-aligned wrapped content, official seven-column widths, row heights, merges, landscape print setup, A4 paper, fit-to-width 1 and print area. No generic style registry.

- [ ] **Step 5: Run workbook tests and inspect the produced file**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_export_xlsx.py -q`

Then generate one temporary workbook under the OS temp directory, open/render it with the available Excel or LibreOffice tooling, and compare the full sheet against official page 57. If neither viewer is available, stop this task without claiming visual completion.

Expected: automated tests PASS and full-sheet visual inspection shows no extra sheet/row, clipped long CJK text or broken merges.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/job_analysis/application/export_xlsx.py apps/api/tests/test_job_analysis_export_xlsx.py
git commit -m "feat(job-analysis): render the strict public XLSX form"
```

---

### Task 14: XLSX download API 與 dirty-safe Web flow

**Files:**
- Modify: `apps/api/app/api/routes/job_analysis.py`
- Modify: `apps/web/src/lib/download.ts`
- Modify: `apps/web/src/lib/jobAnalysisApi.ts`
- Create: `apps/web/src/lib/jobAnalysisExport.ts`
- Create: `apps/web/src/lib/jobAnalysisExport.test.ts`
- Modify: `apps/web/src/components/workspace/ConsultationWorkspace.tsx`
- Modify: `docs/contract-strategy.md`
- Modify: `docs/design/task-analysis-engine.md`
- Test: `apps/api/tests/test_job_analysis_api_postgres.py`

**Interfaces:**
- GET `/api/v1/job-analysis/documents/{document_id}/export`, no `Idempotency-Key`.
- `exportDocument(documentId) -> Promise<Blob>` and `exportFilename(title) -> string`.

- [ ] **Step 1: Write red route and Web tests**

API test asserts 200, XLSX media type, RFC 5987 UTF-8 filename, one-sheet workbook, 404 problem response and no Journal/generation mutation.

```ts
it("disables export while any editor is dirty", () => {
  expect(canExport({ header: true, duty: false, task: false, opks: false })).toBe(false);
});
```

- [ ] **Step 2: Run red tests**

Run: `cd apps/api; uv run pytest tests/test_job_analysis_api_postgres.py -k export -q`

Run: `cd apps/web; npm run test -- src/lib/jobAnalysisExport.test.ts`

Expected: FAIL before route/helper exists.

- [ ] **Step 3: Add the thin GET route**

Load one validated state, call `assemble_export_document`, then `render_xlsx`. Do not pass readiness into renderer; Web already received readiness in `DocumentView`. No provider dependency and no write transaction.

- [ ] **Step 4: Add download UI with warnings and dirty guard**

When dirty, disable button and show「請先儲存或取消目前編輯，再匯出」。When saved readiness issues or unlinked K/S exist, show them before download but do not block. Do not auto-save and do not put warning text into workbook.

- [ ] **Step 5: Register the seam and run gates**

Update `docs/contract-strategy.md` to record XLSX as a binary HTTP representation owned by `job_analysis`, not a Python⇄TS schema contract and not OCS reuse.

Run:

```powershell
cd apps/api; uv run pytest tests/test_job_analysis_api_postgres.py -k export -q
cd ../web; npm run test; npx tsc --noEmit; npm run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/api/routes/job_analysis.py apps/api/tests/test_job_analysis_api_postgres.py apps/web docs/contract-strategy.md docs/design/task-analysis-engine.md
git commit -m "feat(job-analysis): download strict XLSX from the workspace"
```

---

### Task 15: Real PostgreSQL／browser／workbook vertical and final boundary audit

**Files:**
- Create: `apps/api/tests/test_job_analysis_header_duty_export_vertical.py`
- Modify: `docs/design/task-analysis-engine.md` only if the observed flow differs from its current description
- Modify: `docs/plans/2026-08-09-reviewed-job-analysis-slices-migration-plan.md` checkboxes and execution record

**Interfaces:**
- No new product interface; this task proves the assembled vertical and rejected-branch boundaries.

- [ ] **Step 1: Write the real PostgreSQL vertical test**

The test creates a document, writes Header, creates/reorders/deletes Duty, assigns Task level, reorders OPKS, reloads, exports, reloads workbook and asserts authority generation／Journal receipts／position codes／literal formula text／one official sheet.

- [ ] **Step 2: Run migration from a clean database and the vertical**

Run:

```powershell
npm run db:migrate
cd apps/api
uv run pytest tests/test_job_analysis_header_duty_export_vertical.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full repository gates**

Run:

```powershell
cd packages/job-analysis-contract; npm run check-codegen; uv run pytest -q
cd ../../apps/api; uv run pytest -q
cd ../web; npm run test; npx tsc --noEmit; npm run lint
```

Expected: all new tests PASS; any pre-existing unrelated baseline failure must be recorded with the exact test name and shown unchanged from before Task 1.

- [ ] **Step 4: Run browser smoke**

Start the local app with the repo runbook. Verify one document at a time: Header save/reload, Duty and Task assignment, nullable level, OPKS Up/Down, consultant turn preserving full document cache, add Proposal before-null copy, dirty export disabled, saved export downloads and opens as one-sheet public workbook.

- [ ] **Step 5: Audit rejected scope is absent**

Run:

```powershell
git diff 8bfb444..HEAD -- apps/api/app/config.py apps/api/app/job_analysis/llm/opks_prompt.py apps/api/app/job_analysis/llm/schemas apps/api/app/job_analysis/application/opks_scheduler.py
rg -n "AI.*Duty|reference|enterprise|16384|subconversation" apps/api/app/job_analysis apps/web/src packages/job-analysis-contract
```

Expected: no 16K default, no OPKS schema rollback, no AI Duty/reference/subconversation feature. Any legitimate documentation occurrence must not correspond to runtime code.

- [ ] **Step 6: Commit verification record and tag**

```powershell
git add apps/api/tests/test_job_analysis_header_duty_export_vertical.py docs/design/task-analysis-engine.md docs/plans/2026-08-09-reviewed-job-analysis-slices-migration-plan.md
git commit -m "test(job-analysis): verify reviewed authoring and XLSX vertical"
git tag job-analysis-reviewed-slices-v1
```

Do not push. Hand the branch back for owner review and comparison against `docs/specs/2026-08-08-unreviewed-branches-review.md` §16.
