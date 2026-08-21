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
