# Hybrid Candidate Document Edit Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將現行「模型在 final Structured Output 一次交付完整文件草稿」升級成「單一候選文件編輯 Tool 可實際套用、取得錯誤並在同一 run 修正，final Structured Output 只發布經驗證的候選 revision」，同時維持員工接受／修改接受／拒絕前絕不改變核准 JD。

**Architecture:** 保留既有 LangChain agent loop、Deep Agents 按需 Skill reader、四個員工來源唯讀 Tool，以及 LangGraph/PostgreSQL 的唯一 durable product thread。第五個 `job_document_candidate_edit` Tool 將 strict typed replacement batch 送進同一條 product graph；graph 在 `active_candidate` 隔離 workspace 建立新的 candidate revision、以既有 document authority 實際套用並回傳 semantic diff。內層 agent 不取得自己的 checkpointer／Store，避免複製員工原話或建立第二份權威。final response 只帶候選 revision／digest／action handles；product graph 在同一 semantic commit 內核對後才把該 bundle 放入 review queue，員工 command 才能更新核准文件。

**Tech Stack:** Python 3.13、Pydantic 2.13、LangChain 1.3、LangGraph 1.2、Deep Agents 0.7、`langgraph-checkpoint-postgres` 3.1、PostgreSQL、pytest、OpenRouter／GPT-5.6 Luna Max。

**Spec:** [`docs/adr/0063-hybrid-candidate-edit-tool-and-structured-final-response.md`](../adr/0063-hybrid-candidate-edit-tool-and-structured-final-response.md)、[`docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §3.7.5、§9.17–§9.18，以及 [`docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`](../specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md)。

## Global Constraints

- 每個 Task 開始前確認 `Get-Location` 與 `git branch --show-current`；施工 worktree 必須是 `S:\caliburn\.worktrees\langgraph-consultant-runtime`／`refactor/langgraph-consultant-runtime`。
- `docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md` 現有 working-tree line-ending stat 不屬於本計畫；每次 stage 前用 `git diff --cached --name-only` 證明沒有把它帶入。
- 每個 Task 使用紅燈→最小實作→綠燈→北極星回歸→獨立 commit；同 commit 追加 north-star audit ledger，不能只在最後回想。
- 一位顧問、前景焦點／背景吸收、Task／Duty／OPKS 動態演化、員工原話記憶、必要澄清、Gap、可信進度、自然離開／續談與單一可強制匯出都不得退化。
- 本輪不接 RAG／Reference consumer、不生成能力級別／A、不建立正式 eval 平台、不加入 multi-agent、不加入 Auto-accept。
- `active_candidate` 是 run-scoped framework state，不是第二份文件；它不得出現在核准文件、export、一般 snapshot API 或 review queue，直到 final publication 驗證通過。
- 內層 LangChain agent 繼續沒有 `checkpointer`／`store`；完整 employee source text 只存在既有 LangGraph Store，候選只存在既有 product graph checkpoint。
- 第一版每次 candidate Tool call 都是「完整 replacement batch」，不是在上一批上做任意 JSON Patch。成功才產生 revision N+1；失敗不改 state；同 tool-call ID／同 payload 必須冪等重播。
- Tool 可使用本批 local ref，但不得自填正式 entity UUID、`document_id`、baseline semantic revision、權限或 server budget。local ref 只在同一 replacement batch 內有效。
- final publication 第一版必須引用最新 candidate revision 的完整 action set；不接受 action subset。員工仍可依既有 dependency／atomic subgroup 對獨立項目分開審核。
- paid canary 僅在 deterministic gates 通過後執行，沿用 owner 已核准的 GPT-5.6 Luna Max；紀錄 route、usage、cost、latency、完整訪談輸入／輸出與修正，不把 smoke 假稱完整品質 eval。
- 不 push、不開 PR、不 merge；完成後保留 branch、worktree 與本地 tag 供 owner 審核。

## Framework-first Implementation Gate（2026-08-15 最後複核）

實作者不得因現行類別名稱或既有 code 已存在，就直接延伸自寫機制。每個 Task 動手前先對照下表：成熟 primitive 能完整承接通用機制時直接使用；只有框架不知道的 Caliburn 產品語意才寫薄 adapter／validator／projection。若實作中發現新的成熟 primitive 能更完整承接同一目的，先停下更新本計畫或開 successor ADR，不得一邊保留自寫機制一邊再疊一份 framework state。

| 目的 | 採用的成熟 primitive | Caliburn 只保留的薄政策／理由 |
|---|---|---|
| Model→Tool→result→model loop | LangChain `create_agent`、Tool execution、`ToolMessage` | 不自寫 provider while-loop；只把 JD candidate Tool 接到 current document scope |
| Tool dependency injection與 call identity | LangChain `ToolRuntime`／runtime context | `document_id`、run ID、權限、baseline與 DB runtime由 application 注入，模型不可自填 |
| Tool 對 state 的 durable effect | LangGraph typed state、reducer、`Command`、checkpoint | candidate寫既有 product graph；不替內層 agent再建一套 checkpointer／Store。若 tool不能直接對 parent graph回 `Command`，只允許薄的 `stage_candidate_revision()` adapter呼叫同一 product graph command，不得重寫 state engine |
| Final typed response | LangChain `ProviderStrategy`／`create_agent.response_format`＋Pydantic strict model | 只定義 Caliburn final effect schema與 pure mapper；不解析自由文字、不自寫 schema engine |
| Candidate／resume／fault recovery | LangGraph thread state＋`AsyncPostgresSaver` | `CandidateWorkspace` 只定義 run、revision、digest與 persisted changeset；不建 candidate table、event store或自寫 checkpoint |
| 員工原話與跨 turn記憶 | LangGraph `Store`＋checkpointed thread state | exact source、speaker、更正 lineage、文件 scope與 quote support規則仍屬產品語意；不另建 transcript memory framework |
| 最小充分 Context | LangChain context middleware、dynamic prompt、context editing／summarization primitives | 只寫「此焦點需要哪些 approved／pending／decision／source slice」的 deterministic selection policy，不自寫 agent lifecycle |
| 按需分析方法 | Deep Agents `SkillsMiddleware`＋受限 `FilesystemMiddleware(read_file)` | Task／Duty／O／P／K／S 方法內容由 Caliburn研究稿提供；不自寫 Skill lifecycle或多 Agent |
| Retry、model/tool calls與成本上限 | LangChain `ModelRetryMiddleware`、`ToolRetryMiddleware`、`ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`＋LangGraph recursion limit | 只決定可重試錯誤與產品 budget數值；不得再包另一層隱藏 retry loop |
| 人工澄清與 durable resume | LangGraph `interrupt()`／`Command(resume=...)`＋PostgreSQL checkpointer | 只決定哪個矛盾會阻擋哪個 branch；不得自寫 pause/resume engine |
| 員工文件審核 | LangGraph checkpoint／Command承接 durable command channel；Pydantic承接 typed decision | LangChain `HumanInTheLoopMiddleware` 是「Tool執行前 approve/edit/reject並暫停該 agent run」，不等同本產品「候選可先在隔離區反覆修正，final後以多 action dependency／defer／stale整包審核」。因此不套它來攔 candidate Tool；review dependency、edit-accept、defer、read-set與 employee authority是必要產品政策 |
| Typed JD候選編輯 | LangChain custom client Tool＋Pydantic input/result＋LangGraph state；既有 document-authority apply/validate seam | OpenAI Apply Patch、Anthropic Text Editor與 Deep Agents `StateBackend`／VFS適合檔案／文字／scratchpad，沒有 Duty／Task／OPKS relational invariant、atomic subgroup或員工 authority。第一版用一個 domain-scoped Tool，不展開 `add_task` 等多 Tool，也不使用 host filesystem／shell |
| Evidence transport與驗證 | Pydantic、LangChain content/citation primitives、既有 Store | 框架可攜帶 citation，但不知道員工來源 validity、更正 lineage、quote是否逐字匹配及證據是否支持某個 Task／OPKS；這些 deterministic verifier必須保留 |
| ID、atomic group、dependency、supersession、read-set | Pydantic typed models＋LangGraph durable state | generic framework不知道 JD entity graph與員工審核政策；只寫 deterministic resolver／validator，不自建 workflow runtime |
| Coverage／depth／decision／gap進度 | LangGraph state＋deterministic projection | 進度定義屬職務分析產品語意，不能交給 LLM Structured Output或通用 agent Todo估算 |
| Provider／模型替換 | LangChain model abstraction＋`langchain-openrouter` profile | 不讓 candidate core依賴 OpenAI／Anthropic專有 editor。OpenAI目前建議 Responses API承接 reasoning/tool/multi-turn；若 adapter採用 Responses，也只能是可替換 transport，不得滲入 domain contract |
| Tracing與成本證據 | LangChain callbacks＋OpenTelemetry＋provider usage metadata | 只定義本產品必填 route／usage／cost／latency與 fail-closed條件，不自寫 tracing backend |

兩個「最新但本輪不採」的機制也要明確保留理由：

1. **不採 Programmatic Tool Calling 作 candidate主迴圈。** OpenAI目前將它定位為可由程式一次過濾、聚合、排序的大量 bounded tool work；當每個結果可能改變模型下一步判斷、動作需要人工核准或必須保留 citation/artifact時，官方建議 direct tool calls。本產品需要看實際 candidate error後決定如何修正，因此 direct Tool loop更吻合；未來 Reference大量檢索／去重才重新評估 PTC。
2. **不採 multi-agent。** OpenAI GPT-5.6 multi-agent仍是 beta；Microsoft也建議先用能滿足需求的較簡單 pattern。產品明確是一位顧問，Task／Duty／OPKS是按需 Skills而非多個人格；除非未來有可獨立平行、能量測品質增益的工作流，否則不增加協調成本。

本 gate 的官方依據：

- [OpenAI Model guidance — Responses API、direct／programmatic Tool Calling、精簡 prompts與 approval boundaries](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI GPT-5.6 Luna — Function Calling、Structured Outputs、Tools與成本定位](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [Anthropic — Tool use contract與 user-defined／trained-in tools邊界](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Google Gemini — Function Calling用於中間動作、Structured Outputs用於 final schema](https://ai.google.dev/gemini-api/docs/tools)
- [Microsoft Agent Framework — deterministic workflow、agent reasoning與 HITL的混合](https://learn.microsoft.com/en-us/agent-framework/journey/workflows)
- [LangChain — ToolRuntime、structured Tool result與 Command state update](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — provider-native Structured Output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain — Context engineering與 middleware／state／Store／runtime context](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — prebuilt retry、limits、HITL與 context middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangGraph — checkpoint persistence、memory、HITL與 fault recovery](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Deep Agents — State／Store／filesystem backends及其適用邊界](https://docs.langchain.com/oss/python/deepagents/backends)

---

### Task 1: 拆分 final wire 與候選編輯 wire

**Files:**
- Create: `apps/api/app/consultant/provider_wire.py`
- Create: `apps/api/app/consultant/candidate_wire.py`
- Create: `apps/api/tests/test_consultant_candidate_wire.py`
- Modify: `apps/api/app/consultant/model_output.py`
- Modify: `apps/api/app/consultant/results.py`
- Modify: `apps/api/tests/test_consultant_model_output.py`
- Modify: `apps/api/tests/test_consultant_agent_and_skills.py`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`

**Interfaces:**

```python
# provider_wire.py
class ProviderWireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class OutputQuoteAnchor(ProviderWireModel):
    source_id: UUID
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)

class OutputAnalysisBasis(ProviderWireModel):
    source_ids: tuple[UUID, ...]
    quote_anchors: tuple[OutputQuoteAnchor, ...]
    skill_ids: tuple[SkillId, ...]

class AnalysisBasisTable:
    def resolve(self, ordinal: int, label: str) -> AnalysisBasis: ...
    def reject_unused(self) -> None: ...

# candidate_wire.py
class CandidateEditBatch(ProviderWireModel):
    base_candidate_revision: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=240)
    analysis_bases: tuple[OutputAnalysisBasis, ...] = Field(min_length=1, max_length=32)
    replacement_changes: tuple[OutputDocumentChange, ...] = Field(min_length=1, max_length=32)

def map_candidate_edit_batch(
    batch: CandidateEditBatch,
    *,
    document_id: UUID,
    materialization_run_id: UUID,
) -> tuple[ReviewableDocumentChange, ...]: ...
```

`OutputDocumentChange` 增加 fixed slots：`change_ref`、`depends_on_change_refs`、`depends_on_action_ids`、`supersedes_action_ids`、`atomic_group_ref`；新增 Duty／Task／OPKS payload 增加 `entity_ref`，Task 增加 `duty_ref`，OPKS 增加 `task_refs`／`indicator_refs`。本批 ref 使用短字串 pattern，空字串是 neutral sentinel；既有 action UUID 只能引用 context／Tool result 已提供的 handle。不得加入 `dict[str, Any]`、`anyOf` 或自由 path。

- [ ] **Step 1: 先寫 common wire 與 local-ref 紅燈測試**

  測試必須證明：

  1. `CandidateEditBatch.model_json_schema()` 為 strict、zero optional、zero union/`anyOf`、zero open object；
  2. 同批 `Duty(entity_ref="d1") → Task(duty_ref="d1", entity_ref="t1") → O/P(task_refs=("t1",))` 能映成 application-issued stable UUID；
  3. duplicate／unknown／跨批 local ref、dependency cycle、self dependency、格式錯誤的 non-empty atomic group ref 與模型自填 ADD UUID 都 fail closed；
  4. `change_ref` 相同的 replacement batch 不接受；每個 `depends_on_change_refs` 都只能指向本批 change；
  5. 現行 `ConsultantModelOutput` 的 mapping 行為在本 Task 尚未改變。

- [ ] **Step 2: 執行紅燈**

  Run:

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_wire.py tests/test_consultant_model_output.py -q
  ```

  Expected: collection 因 `provider_wire`／`candidate_wire` 尚不存在而失敗；不得先改 production 讓測試直接綠。

- [ ] **Step 3: 抽出共用 basis wire，不複製 Evidence 規則**

  將 `OutputQuoteAnchor`、`OutputAnalysisBasis`、`OutputModel` 與 `_BasisTable` 從 `model_output.py` 移到 `provider_wire.py`。`model_output.py` 直接 import 使用；保留 pure mapper、quote ordinal 與 unused-basis fail-closed 行為。

- [ ] **Step 4: 建立候選 wire 與 deterministic local-ref resolver**

  `candidate_wire.py` 持有文件 target／field／payload schema及 document-change mapper。local ref 的正式 UUID 以 `uuid5(document_id, f"consultant:{materialization_run_id}:local:{kind}:{ref}")` 產生；同一 batch／同一 revision 重播結果必須 byte-stable。`model_output.py` 在 hard switch 前可 import/re-export這些類別，避免同一契約存在兩份定義。

- [ ] **Step 5: 擴充 application semantic change 的 grouping metadata**

  在 `ReviewableDocumentChange` 加上有 default 的 `change_ref`、`depends_on_change_refs`、`depends_on_action_ids`、`supersedes_action_ids`、`atomic_group_ref`，既有 constructor 不需修改。這些欄位只描述候選內／跨既有 pending action 的依賴、取代關係與審核分組，不給模型 authority。

- [ ] **Step 6: 執行綠燈與 schema measurement**

  Run:

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_wire.py tests/test_consultant_model_output.py tests/test_consultant_agent_and_skills.py -q
  ```

  Expected: PASS；測試輸出記錄 candidate Tool input schema 的 defs、properties、object depth、bytes、optional、union 與 open-object 數。bytes 只作比較訊號，不宣稱 provider 官方上限。

- [ ] **Step 7: 北極星回歸與 commit**

  ledger 記錄本 Task 只拆 provider contract 並加入本批 local ref，沒有 agent Tool、approved write、RAG、A 或 UI 行為變更。

  ```powershell
  git diff --check
  git add apps/api/app/consultant/provider_wire.py apps/api/app/consultant/candidate_wire.py apps/api/app/consultant/model_output.py apps/api/app/consultant/results.py apps/api/tests/test_consultant_candidate_wire.py apps/api/tests/test_consultant_model_output.py apps/api/tests/test_consultant_agent_and_skills.py docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md
  git diff --cached --name-only
  git commit -m "refactor: split consultant candidate wire"
  ```

---

### Task 2: 在唯一 product graph 建立 durable candidate workspace

**Files:**
- Create: `apps/api/app/consultant/candidate_workspace.py`
- Create: `apps/api/tests/test_consultant_candidate_workspace.py`
- Modify: `apps/api/app/consultant/state.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/consultant/document_review.py`
- Modify: `apps/api/app/consultant/verification.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/tests/test_consultant_document_review.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`
- Modify: `apps/api/tests/test_consultant_foundation_boundaries.py`
- Modify: `apps/api/tests/test_consultant_agent_and_skills.py`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`

**Interfaces:**

```python
class CandidateWorkspace(DurableModel):
    run_id: UUID
    baseline_revision: int = Field(ge=0)
    candidate_revision: int = Field(ge=1)
    request_sha256: Digest
    revision_digest: Digest
    used_skill_ids: tuple[SkillId, ...]
    changeset: DocumentChangeSet
    tool_receipts: dict[str, CandidateToolReceipt]

class CandidateStageRequest(DurableModel):
    run_id: UUID
    baseline_revision: int = Field(ge=0)
    tool_call_id: NonEmptyText
    batch: CandidateEditBatch
    selected_skill_ids: tuple[SkillId, ...]
    loaded_skill_ids: tuple[SkillId, ...]

class VerifiedCandidateStage(DurableModel):
    run_id: UUID
    baseline_revision: int = Field(ge=0)
    base_candidate_revision: int = Field(ge=0)
    tool_call_id: NonEmptyText
    request_sha256: Digest
    summary: NonEmptyText
    changes: tuple[ReviewableDocumentChange, ...] = Field(min_length=1)
    used_skill_ids: tuple[SkillId, ...]

async def PostgresConsultantRuntime.stage_candidate_revision(
    *, document_id: UUID, request: CandidateStageRequest
) -> CandidateEditReceipt: ...
```

`ConsultantThreadState` 增加 `active_candidate: dict[str, Any] | None`；`ConsultantCommandContext.action` 增加 `stage_candidate_revision`。此 command 不增加 semantic `revision`、不 touch approved document、不寫 review queue。

- [ ] **Step 1: 先寫 pure reducer 紅燈測試**

  覆蓋 first revision、replacement revision、stale base、同 tool-call ID 同 digest 重播、同 ID 不同 digest 衝突、invalid batch 全不寫入，以及 candidate revision digest 對 canonical changeset 的穩定性。

- [ ] **Step 2: 寫 PostgreSQL durable behavior 紅燈測試**

  驗證 process/runtime reopen 後 candidate 還在；`approved_document`、`review_queue` 與 semantic `revision` 完全不變；一般 snapshot/view 不洩漏 candidate。另驗證同 run 的 failed→restart 保留 workspace，而新 source、direct edit 或任一員工 review decision 會使舊 workspace 清除。

- [ ] **Step 3: 執行紅燈**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_workspace.py tests/test_consultant_durable_authority_postgres.py -q
  ```

  Expected: FAIL，原因是 state／graph/runtime 尚無 candidate channel。

- [ ] **Step 4: 實作 candidate materialization 與審核分組**

  每個成功 revision 使用：

  ```python
  materialization_run_id = uuid5(
      request.run_id,
      f"candidate-revision:{next_candidate_revision}",
  )
  ```

  adapter 在 document lock 內先由目前 workspace算出 next revision，再以此 seed將 raw `CandidateEditBatch` 映成 `VerifiedCandidateStage`，配置 entity／action／changeset IDs，呼叫既有 `create_document_changeset()` 與 `apply_document_actions()` 做真實全批驗證。`depends_on_change_refs` 轉成本 bundle dependency；相同 `atomic_group_ref` 與 explicit merge/split 組成同一 subgroup；dependency cycle 或不完整 group 必須在 state write 前拒絕。

  若 change 明確列出 `depends_on_action_ids`，先從 review queue 建立其 pending/deferred transitive dependency closure，依 dependency order套用到 approved document的 copy，形成明示 `approved=false` 的條件式 baseline，再驗證新 actions。不存在、rejected、stale、跨文件或 cycle 的外部 dependency 一律拒絕；沒有明列 action ID 時絕不自動混入任何 pending candidate。

  `DocumentChangeSet` 增加 `external_dependency_action_ids`，`DocumentPatchAction` 增加 `supersedes_action_ids`；validator允許的跨 changeset dependency必須精確等於已宣告且驗證過的 external closure。員工不得在前置 action尚未 accept/edit-accept時接受 dependent subgroup；前置 action rejected/stale時，下游依既有 revalidation機制變 stale。新 bundle final publication 時，明確被 `supersedes_action_ids` 指向的 pending/deferred舊 action原子標成 stale並保留 audit reason，不改 approved document。

- [ ] **Step 5: 抽出並執行 candidate Evidence verifier**

  將現行 `verify_consultant_result()` 內 document change 的 path／payload／OPKS linkage／Evidence 檢查抽成 `verify_candidate_document_changes()`。adapter 必須依 batch basis從既有 Store載入 current employee sources，核對 document scope、quote anchors、selected／loaded Skills與 operation semantics後，才可建立 `VerifiedCandidateStage`；不得等 final response 才第一次驗 candidate evidence。

- [ ] **Step 6: 實作 product-graph command 與 adapter lock**

  `PostgresConsultantRuntime.stage_candidate_revision()` 必須使用現有 `_lock_for(document_id)`；在 lock 內重新讀 checkpoint、核對 latest run ID／baseline semantic revision／`batch.base_candidate_revision`，計算 next revision、映射 local refs、載入 Evidence並產生 `VerifiedCandidateStage`，然後 `graph.ainvoke`。不得啟動第二個 graph、Saver、Store 或 transaction table。

- [ ] **Step 7: 明定 workspace lifecycle**

  - `mark_consultant_run_failed`：保留同 run candidate，供 retry。
  - `restart_consultant_run`：僅 run ID 與 failed receipt 完全相同時保留。
  - 新 `register_source`／source correction、direct edit、accept／edit-accept／reject／defer：清除 active candidate，防止舊 baseline 被發布。
  - stage failure：保留上一個成功 revision；如果尚無成功 revision則維持 `None`。
  - semantic revision、catalog `updated_at` 與 UI snapshot：candidate staging 不改變。

- [ ] **Step 8: 執行綠燈與 authority guards**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_workspace.py tests/test_consultant_document_review.py tests/test_consultant_durable_authority_postgres.py tests/test_consultant_foundation_boundaries.py tests/test_consultant_agent_and_skills.py -q
  ```

  Expected: PASS；boundary test 證明 candidate module 只依賴 current consultant/document authority，不 import RAG、舊 writer 或 Web contract。

- [ ] **Step 9: 北極星回歸與 commit**

  ledger 明記 durable candidate 是 framework checkpoint 的暫存 channel，不是員工文件或第二 authority。

  ```powershell
  git diff --check
  git add apps/api/app/consultant/candidate_workspace.py apps/api/app/consultant/state.py apps/api/app/consultant/graph.py apps/api/app/consultant/document_review.py apps/api/app/consultant/verification.py apps/api/app/adapters/langgraph/postgres.py apps/api/tests/test_consultant_candidate_workspace.py apps/api/tests/test_consultant_document_review.py apps/api/tests/test_consultant_durable_authority_postgres.py apps/api/tests/test_consultant_foundation_boundaries.py apps/api/tests/test_consultant_agent_and_skills.py docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md
  git diff --cached --name-only
  git commit -m "feat: add durable consultant candidate workspace"
  ```

---

### Task 3: 建立第五個候選編輯 Tool 與真實結果回饋

**Files:**
- Create: `apps/api/app/consultant/candidate_tool.py`
- Create: `apps/api/tests/test_consultant_candidate_tool.py`
- Modify: `apps/api/app/consultant/verification.py`
- Modify: `apps/api/app/consultant/agent.py`
- Modify: `apps/api/app/consultant/model_runtime.py`
- Modify: `apps/api/tests/test_consultant_agent_and_skills.py`
- Modify: `apps/api/tests/test_consultant_model_runtime.py`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`

**Interfaces:**

```python
class CandidateStagePort(Protocol):
    async def stage_candidate_revision(
        self, *, document_id: UUID, request: CandidateStageRequest
    ) -> CandidateEditReceipt: ...

@dataclass(frozen=True)
class CandidateEditToolBinding:
    runtime: CandidateStagePort
    document_id: UUID
    run_id: UUID
    baseline_revision: int
    selected_skill_ids: tuple[SkillId, ...]

def build_job_document_candidate_edit_tool(
    *,
    binding: CandidateEditToolBinding,
    loaded_skill_ids: Callable[[], tuple[SkillId, ...]],
) -> BaseTool: ...
```

Tool 以 LangChain `ToolRuntime` 取得 provider tool-call ID；`document_id`、run ID、baseline、runtime 與 loaded-Skill callback 都是 injected/closure data，不出現在 model schema。

- [ ] **Step 1: 先寫 Tool schema 與 result 紅燈測試**

  斷言正式 Tool 名稱精確為 `job_document_candidate_edit`；model 只看到 `CandidateEditBatch` 四個 top-level 欄位；schema 無 hidden runtime／document／authority 欄位。成功 ToolMessage 需含 `status=applied`、candidate revision、digest、semantic before/after diff、action handles、dependencies、atomic groups與 stale impact；deterministic rejection 需含 `status=rejected`、目前 revision 與可行動問題。

- [ ] **Step 2: 寫「失敗可修正」紅燈測試**

  第一呼叫提交 unknown Task linkage，Tool 正常回 rejected 且 graph state 不變；第二呼叫用相同 base 提交修正版，回 applied。deterministic domain error 不丟給 `ToolRetryMiddleware` 重試；網路／checkpoint infrastructure error 才 raise。

- [ ] **Step 3: 執行紅燈**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_tool.py tests/test_consultant_agent_and_skills.py -q
  ```

  Expected: FAIL，原因是第五個 Tool factory 尚不存在。

- [ ] **Step 4: 在 Tool boundary重驗 current Evidence 與 Skill receipts**

  候選 Tool 將 closure中的 selected Skills與 `PackageSkillBackend.loaded_skill_ids` 放入 `CandidateStageRequest`；adapter 使用 Task 2 的 `verify_candidate_document_changes()` 並從 Store重讀其 basis引用的 current employee sources。Tool不得相信模型自報「已讀 Skill」，也不得使用 run開始時可能已過期的 source snapshot。

- [ ] **Step 5: 實作 Tool 的正常 domain-error 回傳**

  Tool catch 的範圍只包含 `CandidateEditRejected`、stale base、document invariant、Evidence 與 local-ref 錯誤；回傳 compact JSON ToolMessage 讓模型修正。未知 exception 保留給既有 retry／failure classification；不得以廣泛 `except Exception` 把 infrastructure failure包成可忽略文字。

- [ ] **Step 6: 將 Tool 納入 agent assembly，但先由 explicit binding 控制**

  `build_professional_consultant_agent()` 建立 `PackageSkillBackend` 後，才用 callback 建 candidate Tool。lookup-wave middleware 的 names 仍只有 `read_file` 與三個 `employee_source_*`；candidate edit 不計 lookup wave，但仍計總 Tool call 與 model step budget。內層 `create_agent` 繼續不傳 checkpointer/store。

- [ ] **Step 7: 將 model ceiling 放寬到 5，但保留其他 hard budgets**

  `ResolvedExecution.max_model_calls` 仍由 profile 設定，interactive guard 改成 `<=5`；lookup wave 仍 `<=2`，total Tool calls、tokens、cost、elapsed time、timeout與 recursion limit 繼續 fail closed。測試涵蓋第 6 個 model step 被拒絕及 candidate Tool 不繞過 total Tool cap。

- [ ] **Step 8: 執行綠燈與五-Tool surface audit**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_tool.py tests/test_consultant_agent_and_skills.py tests/test_consultant_model_runtime.py -q
  ```

  Expected: PASS；帶 explicit candidate binding 的正式 agent assembly 恰好五個 Tool，沒有 operation-per-tool、accept/reject Tool、Tool Search、MCP catalog 或 RAG Tool。run service 到 Task 4 才一次 hard-switch，不在本 Task 留半接線 production path。

- [ ] **Step 9: 北極星回歸與 commit**

  ```powershell
  git diff --check
  git add apps/api/app/consultant/candidate_tool.py apps/api/app/consultant/verification.py apps/api/app/consultant/agent.py apps/api/app/consultant/model_runtime.py apps/api/tests/test_consultant_candidate_tool.py apps/api/tests/test_consultant_agent_and_skills.py apps/api/tests/test_consultant_model_runtime.py docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md
  git diff --cached --name-only
  git commit -m "feat: add consultant candidate edit tool"
  ```

---

### Task 4: Hard-switch final Structured Output 到 candidate publication

**Files:**
- Modify: `apps/api/app/consultant/model_output.py`
- Modify: `apps/api/app/consultant/results.py`
- Modify: `apps/api/app/consultant/interview.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/agent.py`
- Modify: `apps/api/app/consultant/verification.py`
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/.env.example`
- Modify: `apps/api/tests/test_consultant_model_output.py`
- Modify: `apps/api/tests/test_consultant_interview_flow.py`
- Modify: `apps/api/tests/test_consultant_run_service.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`

**Interfaces:**

```python
class OutputCandidatePublication(OutputModel):
    candidate_revision: int = Field(ge=0)
    revision_digest: str = Field(pattern=r"^(?:|[0-9a-f]{64})$")
    action_ids: tuple[UUID, ...]

class CandidatePublication(ResultModel):
    candidate_revision: int = Field(ge=1)
    revision_digest: Digest
    action_ids: tuple[UUID, ...] = Field(min_length=1)

class ConsultantModelOutput(OutputModel):
    # existing visible reply / understanding / attention / gaps / question / sufficiency
    candidate_publication: OutputCandidatePublication

class ConsultantResult(ResultModel):
    # reviewable_document_changes removed
    candidate_publication: CandidatePublication | None = None
```

`candidate_revision=0`、`revision_digest=""`、`action_ids=()` 是 neutral triplet；其他混合 sentinel 一律 mapper error。這保持 provider schema required-only／union-free。

- [ ] **Step 1: 先寫 final schema hard-cut 紅燈測試**

  斷言 final JSON Schema 不再含 `reviewable_document_changes`、Duty／Task／OPKS payload defs；只含 publication reference。neutral/all-valid mapping、digest pattern、duplicate action ID、revision 0 帶 handles與 revision >0 缺 handles 都有測試。

- [ ] **Step 2: 寫 publication authority 紅燈測試**

  覆蓋：未知 revision、舊 revision、digest mismatch、action subset、action reorder/duplicate、另一 run candidate、baseline semantic revision stale 全部 fail closed；正確最新完整 reference 才把 exact persisted changeset 加入 review queue；approved document仍不變。

- [ ] **Step 3: 寫 unreferenced-candidate 紅燈測試**

  同 run 已有成功 candidate，但 final 用 neutral publication：semantic commit 可完成理解／Gap／問題，candidate 被清除且不進 review queue。模型 run 整體失敗則 candidate 保留供 same-run retry。

- [ ] **Step 4: 執行紅燈**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_model_output.py tests/test_consultant_interview_flow.py tests/test_consultant_run_service.py tests/test_consultant_durable_authority_postgres.py -q
  ```

  Expected: FAIL，現行 final 仍重送完整 document changes。

- [ ] **Step 5: 刪除 final document draft channel**

  `map_consultant_model_output()` 只映射非文件 effects＋publication reference；candidate wire 不再由 final schema import。prompt 刪除「在 final 填完整 Duty／Task／OPKS」規則，改成：有文件候選必須先成功呼叫 candidate Tool，final 只能引用最新 receipt；沒有文件變更就用 neutral publication。

- [ ] **Step 6: 在 graph semantic commit 原子核對並發布**

  `commit_consultant_result` graph command 在同一 checkpoint transition 中：

  1. 讀 `active_candidate`；
  2. 核對 run ID、baseline、latest candidate revision、revision digest與完整 ordered action IDs；
  3. 把 persisted `DocumentChangeSet` 傳給 `apply_verified_consultant_commit(..., published_changeset=...)`；
  4. 加入 review queue、依 `supersedes_action_ids` 將被取代的 pending/deferred舊 actions標 stale、block dependent work、清除 active candidate並只增加一次 semantic revision。

  run service 不可依 final payload重新 materialize第二份 changeset。

- [ ] **Step 7: 維持 Skill／Evidence 一致性**

  final `used_skill_ids` 必須包含 candidate workspace 的 `used_skill_ids`，且全部已 loaded；candidate Evidence 已於 Tool stage 驗一次，publication 時再核對其來源仍 current。來源在 Tool 與 final 之間被更正時 fail closed。

- [ ] **Step 8: 正式設定五次 model ceiling**

  將 `consultant_max_model_calls` 與 example env 預設改為 5。`build_configured_execution()` 的 allowed Tool IDs 恰好五個；run service 將 document/run/baseline binding 注入 agent。不要加入另一個 model router或隱藏 fallback。

- [ ] **Step 9: 量測合併 grammar，不只量 final schema**

  測試同時量測四個 read Tool、candidate Tool input與 final response schema經 LangChain/OpenRouter conversion 後的總 defs/properties/depth/bytes/optional/union/open-object。candidate與 final 各自必須 zero optional／union／open object；總 bytes 只記錄，不設虛構官方閾值。

- [ ] **Step 10: 執行綠燈與 authority regression**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_model_output.py tests/test_consultant_candidate_wire.py tests/test_consultant_candidate_tool.py tests/test_consultant_interview_flow.py tests/test_consultant_run_service.py tests/test_consultant_durable_authority_postgres.py -q
  ```

  Expected: PASS；沒有任何 model path 可呼叫 accept／edit-accept／reject／defer或直接改 approved document。

- [ ] **Step 11: 北極星回歸與 commit**

  ```powershell
  git diff --check
  git add apps/api/app/consultant/model_output.py apps/api/app/consultant/results.py apps/api/app/consultant/interview.py apps/api/app/consultant/graph.py apps/api/app/consultant/run_service.py apps/api/app/consultant/agent.py apps/api/app/consultant/verification.py apps/api/app/config.py apps/api/.env.example apps/api/tests/test_consultant_model_output.py apps/api/tests/test_consultant_interview_flow.py apps/api/tests/test_consultant_run_service.py apps/api/tests/test_consultant_durable_authority_postgres.py docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md
  git diff --cached --name-only
  git commit -m "refactor: publish verified consultant candidates"
  ```

---

### Task 5: 提供明示非核准的 pending overlay 與決策記憶

**Files:**
- Modify: `apps/api/app/consultant/context.py`
- Modify: `apps/api/app/consultant/views.py`
- Modify: `apps/api/tests/test_consultant_context.py`
- Modify: `apps/api/tests/test_consultant_interview_flow.py`
- Modify: `apps/api/tests/test_consultant_document_review.py`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`

**Context sections:**

```text
<active_candidate_workspace authority="none" approved="false">...</active_candidate_workspace>
<pending_document_overlay authority="candidate" approved="false">...</pending_document_overlay>
<document_decision_history authority="employee_decision" approved="false">...</document_decision_history>
```

- [ ] **Step 1: 先寫 semantic context 紅燈測試**

  pending/deferred action 必須帶 operation、path、before、after、source IDs、dependency、atomic subgroup與 status，不再只有 handle。rejected/stale 必須帶 target key、員工拒絕原因／stale reason；不得把其 `after` 合併進 approved slice。edit-accepted 的 approved 文件顯示員工值，decision history標示模型原候選被修改。

- [ ] **Step 2: 寫「9 接受、1 個 O 拒絕」紅燈測試**

  下一輪 context 的 approved slice含九項實際接受內容；被拒絕 O 不在 approved/pending overlay，decision history仍可見其 target與拒絕理由，防止模型把它當已核准或無新證據重提。

- [ ] **Step 3: 寫 failed-run retry context 紅燈測試**

  只有 `request.run_id == active_candidate.run_id` 的 same-run retry看得到 active workspace revision／digest／完整 semantic action摘要；一般新 run 看不到舊 active candidate。內層 agent不需 checkpoint歷史也能在 retry 繼續修正。

- [ ] **Step 4: 執行紅燈**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_context.py tests/test_consultant_interview_flow.py tests/test_consultant_document_review.py -q
  ```

  Expected: FAIL，現行 context 只有 `<pending_review_handles>`。

- [ ] **Step 5: 實作 deterministic relevance與 budget**

  - pending/deferred：先選與 current work／approved focus slice target相交者，再補同 changeset dependency closure，最多 12 actions；
  - decision history：只選 rejected／stale／edit-accepted，按 changeset `created_revision`、changeset ID、action order穩定排序，最多最近 8 actions；
  - 超出時回傳各 status 的 `omitted_count`，不傳所有歷史；
  - active candidate：只在 same-run retry帶入，最多既有 candidate batch hard limit 32 actions；
  - 所有 section 明示 authority與 approved=false，prompt規定 pending只能作條件式假設，引用時必須建立 dependency／supersession。

- [ ] **Step 6: 保持 progress deterministic**

  candidate staging 不增加 coverage／depth／decision／gap progress；publication只增加待審 decision數；accept/edit-accept才改已核准 coverage。新增 regression證明 final Structured Output 的 sufficiency文字不能覆寫 deterministic progress projection。

- [ ] **Step 7: 執行綠燈與 token regression**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_context.py tests/test_consultant_interview_flow.py tests/test_consultant_document_review.py tests/test_consultant_understanding_and_sufficiency.py -q
  ```

  Expected: PASS；context selection receipt 不含 employee source全文，token budget gate仍有效。

- [ ] **Step 8: 北極星回歸與 commit**

  ```powershell
  git diff --check
  git add apps/api/app/consultant/context.py apps/api/app/consultant/views.py apps/api/tests/test_consultant_context.py apps/api/tests/test_consultant_interview_flow.py apps/api/tests/test_consultant_document_review.py docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md
  git diff --cached --name-only
  git commit -m "feat: add semantic candidate context overlays"
  ```

---

### Task 6: 四個產品 canary 與 active design 同步

**Files:**
- Create: `apps/api/tests/test_consultant_candidate_loop.py`
- Modify: `docs/design/consultant-runtime.md`
- Modify: `docs/plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md`
- Modify: `docs/plans/2026-08-14-consultant-tool-surface-upgrade-plan.md`
- Modify: `docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`

- [ ] **Step 1: 建立 scripted-model end-to-end canary**

  使用真 LangChain Tool loop＋真 product graph／PostgreSQL，但用 deterministic scripted chat model，不建 eval harness。四個場景：

  1. 新 Task＋該 Task 的 O／P，以 local refs同批建立，final publication後進 review queue，員工 accept後才進 approved JD；
  2. 跨 Duty／Task split 第一批因 linkage錯誤被 Tool拒絕，模型看見 error後第二批修正，final引用第二個 revision，split actions同 atomic group；
  3. 十個已發布項目中員工接受九個、拒絕一個 O，下一輪能看到核准結果＋拒絕記憶，不會把該 O 偷偷視為事實；
  4. candidate成功後員工 direct edit，舊 baseline不得發布；既有 review queue依 read-set標 stale。

- [ ] **Step 2: 驗證自然離開／續談與 required clarification沒有退化**

  無文件變更回合不呼叫 candidate Tool；員工可在任一回答後關閉頁面再重開；必要澄清仍由 typed final output→LangGraph interrupt/resume，不新增「本輪可停」產品狀態。

- [ ] **Step 3: 執行 canary 紅／綠證據**

  新測試至少先以「candidate Tool 不存在或 final仍含 document draft」呈現紅燈，再執行：

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_loop.py -q
  ```

  Expected: 四個場景 PASS，且 scripted trace證明 rejected Tool result位於修正呼叫之前。

- [ ] **Step 4: 同步 active design與舊計畫 successor**

  `docs/design/consultant-runtime.md` 改成五 Tool、5-step ceiling、hybrid candidate loop、同一 product checkpoint與 final publication reference。兩份舊計畫只追加「已由 ADR 0063／本計畫取代的假設」，不改寫其歷史完成紀錄。

- [ ] **Step 5: 文件與大方向自審**

  檢查 active docs 不再宣稱：文件候選只走 final SO、固定三次 model call、pending只有 handles、agent另有 checkpoint、candidate等於approved、RAG已接入或能力級別／A由模型生成。

- [ ] **Step 6: focused regression**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_loop.py tests/test_consultant_agent_and_skills.py tests/test_consultant_context.py tests/test_consultant_document_review.py tests/test_consultant_clarification.py tests/test_consultant_understanding_and_sufficiency.py -q
  cd ../..
  git diff --check
  ```

  Expected: PASS／clean。

- [ ] **Step 7: 北極星回歸與 commit**

  ledger 逐項對照產品大方向、成熟 framework primitives、Caliburn保留政策與延後範圍；任何偏離先停下與 owner討論，不用測試綠燈掩蓋產品錯誤。

  ```powershell
  git add apps/api/tests/test_consultant_candidate_loop.py docs/design/consultant-runtime.md docs/plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md docs/plans/2026-08-14-consultant-tool-surface-upgrade-plan.md docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md
  git diff --cached --name-only
  git commit -m "test: prove hybrid consultant candidate loop"
  ```

---

### Task 7: GPT-5.6 Luna Max 真 API smoke、完整 gates與交付

**Files:**
- Create: `docs/specs/2026-08-15-hybrid-candidate-loop-live-smoke.md`
- Create: `docs/specs/2026-08-15-hybrid-candidate-loop-completion.md`
- Modify: `docs/specs/2026-08-14-gpt-5-6-luna-live-consultant-smoke.md`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`

- [ ] **Step 1: 在付費呼叫前重跑 deterministic gate**

  ```powershell
  cd apps/api
  uv run pytest -p no:cacheprovider tests/test_consultant_candidate_loop.py tests/test_consultant_model_output.py tests/test_consultant_candidate_wire.py tests/test_consultant_candidate_tool.py tests/test_consultant_run_service.py -q
  ```

  Expected: PASS；若不綠，不消耗真模型費用。

- [ ] **Step 2: 用 disposable文件執行真 API訪談**

  以 `DEBUG=false`、owner核准的 GPT-5.6 Luna Max profile、disposable PostgreSQL文件啟動 `apps/api/run_live.py`。至少完成兩輪：第一輪建立 Task＋O/P candidate並發布待審；員工接受部分、拒絕一項 O後，第二輪證明模型看到實際核准 JD與拒絕記憶。另用受控錯誤 batch證明 Tool result→修正→final publication閉環。OpenAI目前把 Luna定位為成本敏感／高流量 tier，因此本 smoke只驗證真實工具閉環、schema、記憶與成本，不宣稱 Luna是專業顧問品質冠軍；產品完成後的正式 eval再以相同 provider-neutral profile比較 Luna／Terra／Sol或其他供應商模型。

- [ ] **Step 3: 記錄可複核的 live evidence**

  報告必須含：輸入、可公開輸出摘要、Tool call順序、rejected/applied receipt、candidate revision/digest、final handles、員工 decision、第二輪 context效果、requested/actual provider route、usage、cost、latency與所有失敗／修復。不得寫入 API key或完整私密環境變數。

- [ ] **Step 4: 清理 disposable資料並證明正常資料未受影響**

  只刪除報告列出的 disposable document IDs與本輪明確建立的 local log；使用 runtime的 document delete path，不用 broad filesystem/database delete。記錄刪除目標與可恢復性。

- [ ] **Step 5: 完整 monorepo gates**

  ```powershell
  cd apps/api
  uv run pytest -q
  cd ../web
  npm run test
  npx tsc --noEmit
  npm run lint
  cd ../../packages/job-analysis-contract
  npm run test
  cd ../..
  npm run check-codegen -w @caliburn/job-analysis-contract
  npx turbo test --env-mode=loose --output-logs=errors-only --force
  git diff --check
  git status --short
  ```

  Expected: 所有 gate無 unexpected failure；若 PostgreSQL或 Windows temp/cache環境中止，修正環境後重跑，不把中止列為產品通過。

- [ ] **Step 6: 簡單獨立審核**

  使用 `superpowers:requesting-code-review`，只要求 reviewer依 ADR 0063、四個 canary、authority邊界、五 Tool surface、no-RAG／no-A與完整 diff找 P1/P2。確認屬實的 finding使用 `superpowers:receiving-code-review`驗證後修正並重跑受影響 gates；不盲從 reviewer。

- [ ] **Step 7: 完成報告與最後 commit**

  completion report列出 commits、實際變更、live結果、gates、已知延後事項、本機重跑命令，以及「approved JD只有員工 command能改」的證據。

  ```powershell
  git add docs/specs/2026-08-15-hybrid-candidate-loop-live-smoke.md docs/specs/2026-08-15-hybrid-candidate-loop-completion.md docs/specs/2026-08-14-gpt-5-6-luna-live-consultant-smoke.md docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md
  git diff --cached --name-only
  git commit -m "docs: complete hybrid candidate editing loop"
  ```

- [ ] **Step 8: Verification-before-completion與本地 tag**

  使用 `superpowers:verification-before-completion` 重新讀取 fresh gate輸出；確認 worktree只剩進場前的 ADR 0060 line-ending stat，且所有本計畫變更已 commit。建立本地 annotated tag：

  ```powershell
  git tag -a consultant-hybrid-candidate-edit-v1 -m "Hybrid candidate edit tool and structured final response"
  git rev-parse HEAD
  git rev-parse consultant-hybrid-candidate-edit-v1^{}
  git status --short
  ```

  Expected: tag peeled SHA等於 HEAD；不 push、不 merge、不刪 worktree。

---

## Final Spec-Coverage Checklist

- [ ] ADR 0063 決定 1／6：Tool Calling＋final Structured Output，final不重送完整文件候選。
- [ ] 決定 2／3：單一 typed atomic batch Tool，無 operation-per-tool、自由 patch、host path或模型權威 UUID。
- [ ] 決定 4／5：run-scoped candidate revision、真實 Tool result、同 graph durable recovery、無 approved write edge。
- [ ] 決定 7／8：pending／decision context明示非核准；員工 accept/edit/reject/defer仍為唯一 authority command。
- [ ] 決定 9：coverage／depth／decision／gap progress仍為 deterministic projection。
- [ ] 決定 10／11：恰好五 Tool、lookup最多兩波、model ceiling五步且保留 token/tool/time/cost/recursion budgets。
- [ ] 決定 12：四個小型 canary＋GPT-5.6 Luna Max smoke；沒有提前建立完整 eval平台。
- [ ] 產品北極星：一位顧問、動態 Task／Duty／OPKS、原話記憶、必要澄清、Gap、自然續談、單一匯出均未偏移。
- [ ] 延後邊界：RAG／Reference consumer、能力級別／A模型生成、Auto-accept、multi-agent與正式eval仍未進 production。
