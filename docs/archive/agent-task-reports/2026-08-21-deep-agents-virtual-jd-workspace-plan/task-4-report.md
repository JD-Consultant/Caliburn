# Task 4 report — safe virtual JD edit and check tools

日期：2026-08-21
分支：`refactor/langgraph-consultant-runtime`
基準：`6c8532c`

## 範圍

本 Task 新增：

- `apps/api/app/consultant/workspace_tools.py`
- `apps/api/tests/test_consultant_workspace_tools.py`

本 Task 修改：

- `apps/api/app/consultant/agent.py`

`agent.py` 新增可選的 `ConsultantWorkspaceBackendBinding` 組裝 seam：workspace mode 共用 Task 3 的 `CompositeBackend` 給 `SkillsMiddleware` 與 `FilesystemMiddleware`，固定 allowlist 六個 framework editor verbs，加入 payload-free `check_candidate_document` 與 `WorkspaceToolWaveMiddleware`。原有 direct Skill／legacy candidate 組裝仍保留，留給 Task 6 hard-cut；本 Task 沒有修改 run service、publication、authority、model output 或 policy default。

## RED / GREEN 證據

### RED

在 `workspace_tools.py` 尚不存在時執行：

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task4'; uv run pytest tests/test_consultant_workspace_tools.py -p no:cacheprovider -q
```

結果（exit code 1）：

```text
ModuleNotFoundError: No module named 'app.consultant.workspace_tools'
!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!
1 error
```

這是預期的 feature-missing import RED。

### GREEN

brief 指定的 focused gate 原命令：

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task4'; uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_agent_and_skills.py -q
```

結果（exit code 0）：

```text
40 passed, 2 warnings in 6.11s
```

兩個 warning 都是 worktree `.pytest_cache` 因 Windows `WinError 5` 無法建立 cache directory；不是測試或 production warning。相同 focused gate 關閉 pytest cache provider 後：

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task4'; uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_agent_and_skills.py -p no:cacheprovider -q
```

```text
40 passed in 6.52s
```

相關回歸：

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task4'; uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_agent_and_skills.py tests/test_consultant_workspace_backend.py tests/test_consultant_workspace_resources.py tests/test_consultant_evidence_anchor.py tests/test_consultant_model_output.py tests/test_consultant_model_runtime.py -p no:cacheprovider -q
```

```text
117 passed in 8.90s
```

另以 `python -m compileall -q app/consultant/agent.py app/consultant/workspace_tools.py` 通過；`git diff --check`（tracked Task 4 modification）無輸出錯誤。

## Pinned framework characterization

實際 installed versions：`deepagents==0.7.5`、`langchain==1.3.15`、`langgraph==1.2.11`。

- `FilesystemMiddleware` 的真實簽名提供 `tools=` allowlist，候選使用 `['ls', 'read_file', 'grep', 'write_file', 'edit_file', 'delete']`，並明設 `tool_token_limit_before_evict=None`、`human_message_token_limit_before_evict=None`。
- `AgentMiddleware.awrap_tool_call()` 真實收到 `ToolCallRequest(tool_call, tool, state, runtime)`，因此 middleware 讀取完整 `request.state['messages']` 的最後一個 `AIMessage.tool_calls`，而不是依賴某一個已完成的 handler。
- `ToolRuntime` 是 `langchain.tools`／`langgraph.prebuilt` 的同一個直接注入 marker；check function 只宣告 `runtime: ToolRuntime`，不把 runtime 放進 model schema。
- `ToolMessage` 的 pinned API 支援 `status: Literal['success', 'error']`；conflicting wave 對每個 call 都回 `status='error'`、原 `tool_call_id` 與同一 actionable content，完全跳過 handler。
- `create_agent` 的真實 async tool loop 驗證了平行 read、不同 entity edit、重疊 mutation 與 mutation＋check 行為；沒有新增 State／Store，candidate 仍由 Task 3 的 LangGraph `files` channel／`StateBackend` 擁有。

workspace mode 的 filesystem descriptions 也以 framework `custom_tool_descriptions` 覆蓋預設 host-oriented wording，避免將 `execute`、host filesystem 或 `/large_tool_results` 暗示送入模型；legacy Skill mode 的 read-only description 未改。

## Model-facing schema metrics

以下數值直接來自 `convert_to_openai_tool(tool)['function']['parameters']`。`properties`／`optional` 是 top-level 數量；`unions` 是遞迴計算 `anyOf`、`oneOf` 或 list-valued `type`；`open_objects` 是遞迴計算 `type=object` 且 `additionalProperties` 不是 `False`；`depth` 是 schema tree 最大深度；`bytes` 是 `ensure_ascii=False`、compact separators 後的 UTF-8 bytes。

| tool | properties | optional | unions | open_objects | depth | bytes |
|---|---:|---:|---:|---:|---:|---:|
| `ls` | 1 | 0 | 0 | 1 | 3 | 165 |
| `read_file` | 3 | 2 | 0 | 1 | 3 | 433 |
| `write_file` | 2 | 0 | 0 | 1 | 3 | 304 |
| `edit_file` | 4 | 1 | 0 | 1 | 3 | 613 |
| `delete` | 1 | 0 | 0 | 1 | 3 | 172 |
| `grep` | 5 | 4 | 3 | 1 | 4 | 1598 |
| `check_candidate_document` | 0 | 0 | 0 | 0 | 2 | 62 |

實際 tool name set：

```text
{'ls', 'read_file', 'grep', 'write_file', 'edit_file', 'delete', 'check_candidate_document'}
```

沒有 `glob`、`execute`、`employee_source_get`、`employee_source_lineage`、`employee_source_search`、`job_document_candidate_edit` 或任何 host／legacy business Tool。check 的 internal args schema 只有 hidden `ToolRuntime`，`tool_call_schema` 與 OpenAI conversion 都是空 object。

## Wave safety evidence

`WorkspaceToolWaveMiddleware` 對完整最後一個 AI message 做 deterministic preflight：

- 平行 `read_file` calls：兩個 `success`。
- 不同 candidate entity 的兩個 `edit_file` calls：兩個 `success`，兩份 resource 都更新。
- 同一路徑 mutation：兩個 `error`，相同 actionable message，candidate content 完全不變。
- ancestor／descendant mutation path：兩個 `error`，invalid ancestor handler 也沒有執行，candidate 沒有新增 resource。
- mutation＋`check_candidate_document`：兩個 `error`，check port 呼叫次數為零，candidate content 完全不變。

衝突診斷先按 tool-call ID 排序再形成訊息，且每個 call 都重新檢查同一完整 wave；不依 completion order，不會先完成一個 mutation 才拒絕另一個。

## 邊界與後續

- `CandidateCheckPort` 目前是 Task 4 的 raw current-files application seam；它將 `document_id`、`run_id`、排序後的目前 candidate file contents 與 `tool_call_id` 傳給下一個 Task。Task 5 才實作 parser→Evidence→semantic changeset／checked receipt，故 Task 4 沒有偷做 publication 或第二份 domain state。
- Task 6 仍需把 production run service 接到 workspace binding、改八步 policy／path-aware lookup，並移除 legacy source／candidate Tool compatibility seam；本 Task 沒有提前做這些 hard-cut。
- `docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md` 在開始時已是 persistent dirty，未修改、未 stage、未 restore；沒有建立 tag、merge、push 或對外動作。

## Fix round 1/5（2026-08-22）

本輪只修正 Task 4 review 已驗證的六項安全／介面缺口，沒有開始 Task 5 publication 或 Task 6 hard-cut。除原有三個 Task 4 檔案外，為重用既有 candidate resource policy，新增一個最小的 `CandidatePolicyBackend.validate_candidate_file_path()` 入口；沒有新增 state、Store、transaction layer、sync DB port 或另一套 path normalizer。

### RED 證據

先只加入 `apps/api/tests/test_consultant_workspace_tools.py` 與 `apps/api/tests/test_consultant_agent_and_skills.py` 的回歸測試，再執行 brief focused gate：

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task4'; $env:VIRTUAL_ENV=(Join-Path (Get-Location) '.venv'); uv run --active pytest tests/test_consultant_workspace_tools.py tests/test_consultant_agent_and_skills.py -p no:cacheprovider -q
```

結果為 exit code 1：`41 passed, 21 failed`。失敗集中在：未驗證 mutation path 未阻擋 sibling、canonical alias 未整波拒絕、check raw files key 未 fail closed、workspace continuation constructor／receipt policy 尚未存在、workspace sync `invoke` 未拒絕。provider test 首次顯示的差異是測試內 depth helper 未採報告既有 schema-tree 定義；改正測試 helper 後，該 test 成為 provider-binding characterization（現有 builder 已能通過真實 bind），沒有藉此擴張 production scope。

另外補測空字串 mutation path 後，先獨立執行該 parametrized case 得到 `1 failed, 2 passed`；同一 framework validation 結果納入最小 fail-closed guard。

### Framework evidence and minimal fixes

- 實際 pinned versions：`deepagents==0.7.5`、`langchain==1.3.15`、`langgraph==1.2.11`。
- `deepagents.backends.utils.validate_path(path, *, allowed_prefixes=None) -> str` 是唯一 path canonicalization primitive；實測 `/./`、重複 slash、backslash aliases 都回傳同一 canonical path，`..`／traversal raise `ValueError`。wave 現在保存每個 mutation call 的 validation 結果，任何 missing／invalid path 都先拒絕整個 wave，再以 canonical string 做 same／ancestor-descendant 比較。
- check 讀同一 LangGraph `files` channel；每個 key 先經 `CandidatePolicyBackend.validate_candidate_file_path()`（內部重用 `validate_path` 與既有 resource grammar），並要求 raw key 已是 canonical current-run resource。cross-run、dot、重複 slash、backslash alias、traversal 與非法 resource key 都在 CandidateCheckPort 前 fail closed。
- `RunScopedSkillsMiddleware` 保留 legacy direct mode 的 blanket stale-read rejection。workspace mode 才以 preceding `AIMessage` 的 matching `tool_call_id` 找 `read_file.file_path`、經 framework validation，只有 `/skills` receipt 視為 stale；正常 `/candidate`、`/sources`、`/approved`、`/pending` receipt 放行，orphan／ambiguous receipt 拒絕。
- workspace `ProfessionalConsultantAgent.invoke()` 現在立即 raise 明確的 `WorkspaceAgentAsyncOnlyError`；legacy direct agent 仍可 sync invoke。check `StructuredTool` 維持只有 `coroutine`、無 sync `func`，其 async-only contract 已寫入 docstring。

### GREEN evidence

brief 原始 focused gate（保留 Windows pytest cache warning，以證明原命令本身）：

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task4'; $env:VIRTUAL_ENV=(Join-Path (Get-Location) '.venv'); uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_agent_and_skills.py -q
```

結果：`63 passed, 2 warnings in 10.66s`。warnings 只是在 worktree 建立 `.pytest_cache` 的 `WinError 5`，不是測試／production warning；同一 focused gate 關閉 cache provider 為 `63 passed`。

相關 regression gate：

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-task4'; $env:VIRTUAL_ENV=(Join-Path (Get-Location) '.venv'); uv run --active pytest tests/test_consultant_workspace_tools.py tests/test_consultant_agent_and_skills.py tests/test_consultant_workspace_backend.py tests/test_consultant_workspace_resources.py tests/test_consultant_evidence_anchor.py tests/test_consultant_model_output.py tests/test_consultant_model_runtime.py -p no:cacheprovider -q
```

結果：`140 passed in 13.44s`。

真實 provider binding regression 以實際 `build_professional_consultant_agent()` 建 graph，讓 model 的真實 `bind_tools()` 收集 `convert_to_openai_tool()` 結果；沒有 monkeypatch builder，也沒有使用會丟棄 tools 的 model。exact names 仍為七個 workspace tools，provider-converted metrics（`properties/optional/unions/open_objects/depth/bytes`）如下：

| tool | properties | optional | unions | open_objects | depth | bytes |
|---|---:|---:|---:|---:|---:|---:|
| `ls` | 1 | 0 | 0 | 1 | 3 | 165 |
| `read_file` | 3 | 2 | 0 | 1 | 3 | 433 |
| `write_file` | 2 | 0 | 0 | 1 | 3 | 304 |
| `edit_file` | 4 | 1 | 0 | 1 | 3 | 613 |
| `delete` | 1 | 0 | 0 | 1 | 3 | 172 |
| `grep` | 5 | 4 | 3 | 1 | 4 | 1598 |
| `check_candidate_document` | 0 | 0 | 0 | 0 | 2 | 62 |

check 的 provider parameters 仍是 empty object（`properties={}`、無 required／document payload），internal schema 只有 hidden `ToolRuntime`。

### Fix round self-review

- 平行 reads、disjoint edits、same／ancestor overlap、mutation＋check 的既有成功／拒絕行為保留；conflicting wave 仍由完整最後 AI message preflight，未依 completion order 部分套用。
- 仍只有一個 Task 3 `StateBackend`／`CompositeBackend`；沒有把 candidate files 複製成第二份 durable state，也沒有 publication／authority edge。
- 未修改 `run_service.py`、publication、authority、model output、policy default 或 ADR 0060；Task 5／6 留待後續 task。
- `git diff --check` 通過。persistent false-dirty `docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md` 持續未修改、未 stage、未 restore。

## Fix round 2/5（2026-08-22）

本輪只修正 scoped re-review 剩餘的 wave candidate-policy seam 與 provider capture assertion，沒有開始 Task 5 publication 或 Task 6 hard-cut。`WorkspaceToolWaveMiddleware` 現在直接接收同一個 `workspace_binding.candidate_backend`；每個 mutation path 先經 pinned Deep Agents `validate_path` canonicalize，再呼叫既有 `CandidatePolicyBackend.validate_candidate_file_path()`。沒有新增 policy framework、path grammar、state/store 或 transaction layer。

### RED 證據

先把兩個 real `create_agent` + `FilesystemMiddleware` cases 改為 canonical cross-run 與 canonical invalid-resource path，並保留合法 sibling edit：

```text
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_workspace_tools.py::test_cross_run_or_invalid_resource_mutation_rejects_sibling_before_zero_mutation -q -p no:cacheprovider
```

在 production 接線前結果為 `2 failed in 6.05s`；兩個 case 都觀察到 `['error', 'success']`，證明 invalid mutation 被拒絕但 sibling handler 仍已執行，且 state safety assertion 不能成立。provider regression 同步在 captured schemas 轉 dict 前固定 `len == 7` 與 names 不重複。

### GREEN／framework evidence

- 新增 real framework wave cases 接線後：`2 passed in 4.27s`。
- brief focused gate：

  ```text
  $env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_agent_and_skills.py -q
  ```

  結果：`63 passed, 2 warnings in 8.52s`。兩個 warning 是 worktree `.pytest_cache` 的 Windows `WinError 5`，不是測試或 production warning。
- 同一 focused gate 關閉 pytest cache 的 final evidence：`63 passed in 8.47s`。
- 相關 regression gate（關閉 pytest cache）的 final evidence：`140 passed in 11.79s`。
- `convert_to_openai_tool()` 的真實 provider capture 仍是恰好七個且無 duplicate names；exact metrics 沒有改變：`ls 1/0/0/1/3/165`、`read_file 3/2/0/1/3/433`、`write_file 2/0/0/1/3/304`、`edit_file 4/1/0/1/3/613`、`delete 1/0/0/1/3/172`、`grep 5/4/3/1/4/1598`、`check_candidate_document 0/0/0/0/2/62`（欄位順序同前表：properties/optional/unions/open_objects/depth/bytes）。check provider schema 仍為空 properties、無 required，沒有 document payload。

### Fix round self-review

- cross-run、canonical invalid resource、missing/invalid path 都在任何 handler 前使整個 wave 的每個 call 回 error；canonical aliases 仍在 framework validation 後比較，並保留同 path／重疊 safety 行為。
- preflight 與 `FilesystemMiddleware` 共用同一 `CandidatePolicyBackend` policy seam；沒有複製 resource grammar，也沒有第二份 candidate state。
- production 只改 `agent.py` 的 middleware binding 與 `workspace_tools.py` 的直接 backend plumbing；沒有修改 run service、publication、authority、model output 或 policy defaults。
- `docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md` 仍是既有 false-dirty，未修改、未 stage、未 restore；沒有 tag、merge 或 push。`git diff --check` 通過。

## Docs-only clarification（2026-08-22）

Task 4 Step 3 的非可執行 `analyze_workspace_wave` 範例已補上 `candidate_backend=workspace_binding.candidate_backend`，與 production signature 及目前 workspace policy binding 一致；本次未修改 production/tests，亦未重跑 broad gates。
