# 分層 Memory 完整背景 Workflow 施工計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將既有 B1 案例維護、B2 工作理解維護、完整 bundle 與 publication CAS 串成一個可 checkpoint／resume、最多返工一次且 stale 時會基於新 head 重做的 deterministic 背景工作。

**Architecture:** 新增 package 內 `BackgroundMemoryWorkflow` 作純 Runtime 狀態機，不新增 LLM orchestrator；B1、B2 繼續使用各自已驗 Agent graph，但由外層配發 durable attempt ID，確保 transport resume 沿用同一 attempt，而 rework／stale 一定建立新 attempt。正式副作用只有既有 `PublicationStore.publish()`；完整 `PublishRequest` 先以同步 checkpoint 保存，publication 以 exact-base CAS 與 receipt 保證 stale 拒絕及遺失回覆後的冪等查回。

**Tech Stack:** Python 3.12、LangChain 1.4.0、LangGraph 1.2.11、Deep Agents StoreBackend、SQLAlchemy 2、既有 `CaseMaintenanceWorkflow`／`UnderstandingMaintenanceWorkflow`／`MemoryArtifacts`／`PublicationStore`。

**Spec:** `docs/specs/2026-09-17-layered-memory-background-workflow-design.md`

## Global Constraints

- 產品資料鏈固定為 `canonical 訪談 ↔ B1 完整案例 ↔ B2 穩定工作理解 → JD`；B1、B2 不合併成同一 Agent。
- 不重寫 B1／B2 Prompt 或語意工具；只加入 Runtime review 所需的最小 B1 邊界與 attempt 接點。
- 模型不產生 document、版本、attempt／operation ID、signed reference、offset、cursor、完成 outcome 或 publication 參數。
- B2 `case_rework_required` 最多觸發一次新 B1；第二次即 `blocked / case_rework_limit_reached`，不發布。
- `max_stale_retries` 是組裝時必填正整數；stale 不重設 rework 次數，也不能只替舊候選換版本。
- `processed_source` 只有 publication 成功才推進。相同／已涵蓋來源可查回正式 head；較舊、部分重疊、跳號或不同 lineage 一律拒絕。
- `PublishRequest` 必須先進父 graph 的同步 checkpoint，再進 publish node；回覆不明只能重送同一 request／operation。
- 不接 dispatcher、C、compaction、provider、JD writer、UI、文件封存、artifact GC、舊資料 migration 或 production authority。
- 離線固定模型只證明控制流與資料邊界，不冒稱自然模型品質；不呼叫 provider、不讀正式 key。
- 官方依據只採共同工程原則：LangGraph persistence／durable execution 要求 thread identity、JSON-safe state、可重執行副作用冪等；AWS optimistic locking 要求版本條件寫入、衝突後 fresh read 與有界重試；Anthropic 建議固定可分解工作使用 deterministic workflow，複雜度只增到必要程度。

---

### Task 1：由 canonical source owner 判定游標關係

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/sources.py`
- Modify: `packages/consultant-memory/tests/conftest.py`
- Modify: `experiments/jd-relational-app/src/jd_relational/conversation_sources.py`
- Modify: `experiments/jd-relational-app/src/jd_relational/extraction_app.py`
- Modify: `experiments/jd-relational-app/tests/test_interview_window_source.py`

**Interfaces:**
- Produces: `ExtractionSourceReader.source_progress(reference: str, previous: str) -> Literal["covered", "next"]`。
- `covered` 只表示 `previous` 在同一 canonical lineage 已完整涵蓋 `reference`；`next` 只表示 `reference` 從 `previous` 後第一個尚未處理的安全回合開始。
- 任何部分重疊、較舊但未被完整涵蓋、跳過中間安全回合、兄弟 lineage、錯文件／purpose 或不可讀位置都沿既有 source error fail closed。
- Existing `require_new_source_after()` remains compatible and delegates to／agrees with `source_progress(...)=next`；不保留兩套不同判定。

- [ ] **Step 1: 寫 App source owner 反例**

在 `test_interview_window_source.py` 建立固定 canonical turns，覆蓋：同一 window → `covered`；較晚 publication window 完整包住較早 job → `covered`；真正緊接 → `next`；部分重疊、倒退、跳號、兄弟 root 與跨文件全部明示失敗。測試必須以 conversation message order／lineage 證明，不能比較 token 字串或時間。

- [ ] **Step 2: 跑 RED**

Run:

```powershell
cd experiments/jd-relational-app
.\.venv\Scripts\python.exe -m pytest -q tests/test_interview_window_source.py -k "source_progress"
```

Expected: `ConversationSourceService.source_progress`／adapter port 尚不存在而失敗。

- [ ] **Step 3: 實作單一 owner 判定**

在 `ConversationSourceService` 解析兩個既有 signed window，於可證明包含兩者的固定 lineage 上比較完整 settled-turn 邊界；只回：

```python
Literal["covered", "next"]
```

`ExtractionSourceAdapter.source_progress()` 只轉譯 owner 結果與既有錯誤，不自行重排／解 token。`require_new_source_after()` 改由同一判定要求結果必須是 `next`。

- [ ] **Step 4: 跑 GREEN 與相鄰來源回歸**

Run:

```powershell
cd experiments/jd-relational-app
.\.venv\Scripts\python.exe -m pytest -q tests/test_interview_window_source.py tests/test_extraction_app.py
```

Expected: 全綠；既有 window admission、context pair、history/exact-source 仍通過。

- [ ] **Step 5: 提交 Task 1**

```powershell
git add packages/consultant-memory/src/caliburn_memory/sources.py packages/consultant-memory/tests/conftest.py experiments/jd-relational-app/src/jd_relational/conversation_sources.py experiments/jd-relational-app/src/jd_relational/extraction_app.py experiments/jd-relational-app/tests/test_interview_window_source.py
git commit -m "feat(memory): classify source publication progress"
```

---

### Task 2：B1 durable attempt 與來源約束的 Runtime review

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/case_maintenance.py`
- Modify: `packages/consultant-memory/src/caliburn_memory/__init__.py`
- Modify: `packages/consultant-memory/tests/test_case_maintenance_workflow.py`

**Interfaces:**
- Produces Runtime-only immutable `CaseRuntimeReview(case_id, source_reference, reason, candidate_content, case_origin)`；`case_origin` 僅為 `base` 或 `candidate`。
- Produces `CaseMaintenanceWorkflow.run_attempt(source_reference, *, base_publication_revision, base_version, case_attempt_id, runtime_review=())`；同 attempt pending 時 resume、完成時查回，輸入不符則拒絕。
- Existing `start()`／`resume()` 保持相容，仍使用原 document-scoped default attempt。
- `case_attempt_id` 必須為 Runtime UUID，只參與 thread／checkpoint identity，不進模型 schema。
- `RUNTIME_REVIEW` 只把 locator、origin、rejected candidate prose、B2 reason 與 Runtime evidence key 送模；signed reference 不送模，review 不是員工原話或正式案例。

- [ ] **Step 1: 寫 attempt／review RED 測試**

新增案例證明：

```text
同 case_attempt_id transport failure → resume 同 checkpoint，不重播已成功語意工具
不同 case_attempt_id＋相同 source/base → 新 B1 attempt，不查回前一完成結果
review source 位於較早批次 → 只先登記 metadata/key，不預載原文
未完整讀完每個 review evidence → finish 被拒絕
讀完 review evidence → 才能 finish
candidate-only case_id 不成為新 stage current case；保留需 create_case 配新 ID
```

- [ ] **Step 2: 跑 RED**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_case_maintenance_workflow.py','-k','attempt or runtime_review or rework']))"
```

Expected: 新型別／`run_attempt`／review 完成 gate 不存在而失敗。

- [ ] **Step 3: 實作最小 B1 attempt 接點**

由 `case_attempt_id` 衍生獨立 thread ID；graph 結構與工具不複製。`run_attempt()` 依該 config 的 snapshot 做 start／resume／completed lookup，並驗證 source、base 與 review digest 完全相同。所有 state 保持 JSON-safe。

- [ ] **Step 4: 實作 Runtime review 投影與完成 gate**

在第一個 request 前由 owner history 找到 review references 並註冊 attempt keys，必要時與本次 `NEW_SOURCE` 的相同 source 共用同一 key。Payload 形狀固定為：

```python
{
    "RUNTIME_REVIEW": [{
        "case_locator": review.case_id,
        "case_origin": review.case_origin,
        "candidate_content": review.candidate_content,
        "reason": review.reason,
        "evidence_key": key,
        "authority": "runtime_review_not_employee_evidence",
    }]
}
```

finish 檢查對應 `CaseEvidence.next_offset is None`；若 review source 已包含在 `NEW_SOURCE` 且完整讀入，可視為已讀，否則模型必須用既有 `read_more_evidence(key)` 讀完。Prompt 只補 review 邊界，不改案例分析方法。

- [ ] **Step 5: 跑 GREEN 與完整 B1 回歸**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_case_maintenance.py','tests/test_case_maintenance_workflow.py']))"
```

- [ ] **Step 6: 提交 Task 2**

```powershell
git add packages/consultant-memory/src/caliburn_memory/case_maintenance.py packages/consultant-memory/src/caliburn_memory/__init__.py packages/consultant-memory/tests/test_case_maintenance_workflow.py
git commit -m "feat(memory): add durable B1 review attempts"
```

---

### Task 3：B2 以 B1 attempt identity 隔離 durable 工作

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/understanding_workflow.py`
- Modify: `packages/consultant-memory/tests/test_understanding_workflow.py`

**Interfaces:**
- Produces `UnderstandingMaintenanceWorkflow.run_attempt(case_stage, *, case_attempt_id)`；同 ID pending resume、完成查回，另一 ID 即使 B1 stage bytes 相同也建立新 B2 thread。
- Existing `start()`／`resume()` 保持原 default thread 行為。
- B2 stage／Prompt 不增加 attempt ID；它只屬 Runtime checkpoint identity。

- [ ] **Step 1: 寫相同 B1 bytes、不同 attempt ID 的 RED 測試**

測試先讓 attempt A 產生 `case_rework_required`，再以完全相同 `CaseMaintenanceStage` 但 attempt B 執行；B 不得查回 A 的終局。另測 B transport failure 後同 ID resume 不重播 read/tool。

- [ ] **Step 2: 跑 RED**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_understanding_workflow.py','-k','attempt']))"
```

- [ ] **Step 3: 實作 attempt-specific config 與 start/resume/lookup**

共用同一 compiled graph；只把 config 的 deterministic thread ID 改由 document＋Runtime UUID 衍生。驗證 UUID、固定 case stage，拒絕同 ID 換輸入。

- [ ] **Step 4: 跑 GREEN 與完整 B2 回歸**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_understanding_maintenance.py','tests/test_understanding_workflow.py']))"
```

- [ ] **Step 5: 提交 Task 3**

```powershell
git add packages/consultant-memory/src/caliburn_memory/understanding_workflow.py packages/consultant-memory/tests/test_understanding_workflow.py
git commit -m "feat(memory): isolate B2 by B1 attempt"
```

---

### Task 4：正常 B1→B2→bundle→publication durable chain

**Files:**
- Create: `packages/consultant-memory/src/caliburn_memory/background_workflow.py`
- Create: `packages/consultant-memory/tests/test_background_workflow.py`
- Modify: `packages/consultant-memory/src/caliburn_memory/__init__.py`

**Interfaces:**
- Produces `BackgroundMemoryWorkflow(case_workflow, understanding_workflow, publication, checkpointer, *, max_stale_retries)`。
- Produces `BackgroundMemoryWorkflow.start(source_reference)`／`resume()`；pending 拒換 source，同 source completed 查回。
- Produces JSON-safe `BackgroundMemoryWorkflowState`，至少保存 source、base revision/version、case attempt ID、兩層 stage、rework/stale counters、candidate version、完整 request、status/error/result。
- 不新增 LLM-facing tool 或第三個 Agent。

- [ ] **Step 1: 寫正常 changed／no-op RED 測試**

使用 real `CaseMaintenanceWorkflow`、`UnderstandingMaintenanceWorkflow`、`MemoryArtifacts`、SQLite `PublicationStore` 與 `InMemorySaver`，模型只使用固定合成 tool calls。驗證：

```text
B1 changed → B2 changed → 一個完整 bundle → revision 1
B1/B2 no-op → 仍建立以固定 base 驗證的完整 bundle並發布
publication 成功前 current head/processed_source 不變
bundle 含正確 cases、understandings、bindings、兩層 supersessions
同 source completed 再 start 不呼叫模型、不建立 revision 2
pending job start 新 source 被拒絕
```

- [ ] **Step 2: 跑 RED**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_background_workflow.py']))"
```

Expected: module/class 不存在。

- [ ] **Step 3: 實作 JSON-safe state 與 graph 節點**

建立固定節點：

```text
load_base → run_b1 → run_b2 → route_b2
route_b2(publishable) → assemble_bundle → prepare_publication → publish
```

所有 graph `invoke` 使用 `durability="sync"`。`run_b1`／`run_b2` 只呼叫 Task 2/3 的 idempotent attempt API。`assemble_bundle` 從 completed sessions 取得完整 current sets、guides 與兩層 supersessions，呼叫：

```python
artifacts.save_bundle(
    base_publication_revision=base_revision,
    base_version=base_version,
    evidence_through_reference=source_reference,
    case_guide=case_stage.case_guide,
    cases=case_session.current_cases(case_stage),
    understanding_guide=understanding_stage.understanding_guide,
    understandings=understanding_session.current_understandings(understanding_stage),
    supersessions=(*case_stage.supersessions, *understanding_stage.supersessions),
)
```

prepare 使用 `kind="consolidation"` 與 `processed_source=source_reference`；完整 `PublishRequest` 以 primitive dict 存入 state，publish node 才重建型別。

- [ ] **Step 4: 跑 GREEN 與 publication 回歸**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_background_workflow.py','tests/test_bundle.py','tests/test_publication.py']))"
```

- [ ] **Step 5: 提交 Task 4**

```powershell
git add packages/consultant-memory/src/caliburn_memory/background_workflow.py packages/consultant-memory/src/caliburn_memory/__init__.py packages/consultant-memory/tests/test_background_workflow.py
git commit -m "feat(memory): publish layered background bundles"
```

---

### Task 5：一次有界 B2→B1 semantic rework

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/background_workflow.py`
- Modify: `packages/consultant-memory/tests/test_background_workflow.py`

**Interfaces:**
- `case_rework_required` 由 outer Runtime 轉成 Task 2 的 `CaseRuntimeReview`；candidate content 從被拒 B1 stage 精確讀出，`case_origin` 由 `base_case_ids` 判斷。
- 第一次 rework 配新 `case_attempt_id`、清除兩層 stage／candidate／request，固定同一 base/source，保留 `case_rework_count=1`。
- 第二次 rework 結束為 `status="blocked"`、`error_code="case_rework_limit_reached"`。

- [ ] **Step 1: 寫 base case／candidate-only／第二次退回 RED 測試**

驗證正式 base case 可用既有 ID revise；candidate-only locator 在新 B1 不存在，保留時必須 create 並取得新 ID。兩者都必須讀完 review exact source。第二次 B2 rework 不發布、不推進 source、模型呼叫有限。

- [ ] **Step 2: 跑 RED**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_background_workflow.py','-k','rework']))"
```

- [ ] **Step 3: 實作 review 轉換與有界 route**

外層不修改案例內容，只建立 `CaseRuntimeReview`。被拒 B1／B2 stage 保留在舊 checkpoint 作診斷，但不搬入新 stage；新 B1 從相同 formal base 重新開始。

- [ ] **Step 4: 跑 GREEN**

Run Task 5 focused tests，再跑完整 `test_background_workflow.py`。

- [ ] **Step 5: 提交 Task 5**

```powershell
git add packages/consultant-memory/src/caliburn_memory/background_workflow.py packages/consultant-memory/tests/test_background_workflow.py
git commit -m "feat(memory): bound B2 case rework"
```

---

### Task 6：stale 重做、來源涵蓋查回與 publication 不明結果恢復

**Files:**
- Modify: `packages/consultant-memory/src/caliburn_memory/background_workflow.py`
- Modify: `packages/consultant-memory/tests/test_background_workflow.py`

**Interfaces:**
- `StalePublication` 清除舊 base、attempt stages、candidate、request；增加 stale counter，保留 source 與 rework count，再回 `load_base`。
- 新 head 的 source 關係為 `covered` 時直接回目前正式 head；`next` 才配置新 B1/B2 attempt。其他關係由 source owner 拒絕。
- stale 次數耗盡為 `blocked / stale_retry_limit_reached`。
- `PublicationUncertain` 不改 state；resume 重入 publish node，使用 checkpoint 中同一 `PublishRequest.operation_id`。

- [ ] **Step 1: 寫 stale／covered／uncertain RED 測試**

以 real publication 加有界 fault wrapper 驗證：

```text
另一 writer 先發布 → 舊 candidate CAS 失敗 → B1/B2 讀新 base 重做
另一 writer 已完整涵蓋 job source → 直接完成，不重跑模型
較舊／部分重疊／跳號／兄弟 lineage → 零 publication
stale 超過 max → blocked，不再呼叫模型
publish commit 成功但 wrapper 丟失回覆 → resume 同 operation receipt，只有一個 revision
rework_count 經 stale 不重設
```

- [ ] **Step 2: 跑 RED**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_background_workflow.py','-k','stale or covered or uncertain or receipt']))"
```

- [ ] **Step 3: 實作有界 stale route 與同 request 恢復**

publish node 只捕捉 `StalePublication`；`PublicationUncertain` 與非 transient 錯誤原樣拋出，讓 checkpoint 保持在 publish 前。不得自動建立新 operation 或在 package 偷加 sleep/backoff。

- [ ] **Step 4: 跑 GREEN 與完整 package 回歸**

Run:

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -m compileall -q src
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests']))"
```

- [ ] **Step 5: 提交 Task 6**

```powershell
git add packages/consultant-memory/src/caliburn_memory/background_workflow.py packages/consultant-memory/tests/test_background_workflow.py
git commit -m "feat(memory): recover layered background publication"
```

---

### Task 7：文件對齊、App 相鄰回歸與本地交付

**Files:**
- Modify: `docs/specs/2026-09-17-layered-memory-background-workflow-design.md`
- Modify: `docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md`
- Modify: `docs/current-decisions.md`
- Modify: `packages/consultant-memory/README.md`
- Modify: `docs/README.md` only if routing text is stale

**Interfaces:**
- Records exact implementation status, tests, limits and next gate；不把 package workflow 稱為 dispatcher／production 已接好。

- [ ] **Step 1: 更新 responsibility docs**

只記實際完成：source progress owner port、attempt identity、B1 review boundary、outer graph、CAS／receipt／stale 行為。明確保留未完成：App dispatcher 組裝、真 PostgreSQL／新程序旅程、C、compaction、provider、自然模型與完整 App 驗收。

- [ ] **Step 2: 跑 final verification**

```powershell
cd packages/consultant-memory
.\.venv\Scripts\python.exe -m compileall -q src
.\.venv\Scripts\python.exe -c "import sys; sys.path.append(r'S:\caliburn\apps\api\.venv\Lib\site-packages'); import pytest; raise SystemExit(pytest.main(['-q','tests']))"

cd ..\..\experiments\jd-relational-app
.\.venv\Scripts\python.exe -m compileall -q src
.\.venv\Scripts\python.exe -m pytest -q tests/test_memory_sources.py tests/test_interview_window_source.py tests/test_extraction_app.py

cd ..\..
git diff --check
```

- [ ] **Step 3: 自我審查**

逐項核對 spec §8 的 17 項驗收；未由本 package 切片涵蓋的真 PG／新程序項目必須標示留待 App 接線，不得寫成 pass。搜尋舊接口、重複 authority、模型可填 Runtime 欄位、provider 呼叫與意外 production import。

- [ ] **Step 4: 提交與 tag**

```powershell
git add docs/current-decisions.md docs/README.md docs/specs/2026-09-17-layered-memory-background-workflow-design.md docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md packages/consultant-memory/README.md
git commit -m "docs(memory): close layered background workflow slice"
git tag mem-layered-background-workflow-v1-20260917
```

不 push。提交作者必須仍為 `ArIs0x145 <aris0x145@gmail.com>`。

