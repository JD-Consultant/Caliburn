# T06：保存取消的原件交接與 A／B 路由

日期：2026-09-30。此為有界原件修復，**不是 T06／Goal 完成證據**。

## 範圍與責任

沿共用執行規格的原件優先、execution 資格與既有有限補存政策：
[共用執行規格](../../../specs/2026-09-27-shared-agent-execution-and-state-design.md)、
[執行實作 §4.4／§5.3／§5.5／§5.6](../../../implementation/agent-execution.md)。
主線依既有 Goal 分派本切片，先只新增測試；主線通知既有整合 commit 完成後，才修改 production。

- `agent_execution/tool_steps.py`、`context_compaction.py`：原生查存／補存／invoke 期間取消，若仍握有完整原件，沿既有 `ResultSaveCancelledError.save_error.recovery` 交出；仍是 `CancelledError`，不重試取消、不 `uncancel`。普通取消或下游已釋放 Held 的取消不捏造 handoff。保留原取消為 cause，包括框架可能附帶的清理工作參照；**不以外層 Task.done 推論清理已結束**。
- `result_save_retries.py`：只調整既有取消型別說明／安全固定訊息，沒有第二套 retry。
- A `agents/job_consultant/runner.py`：`run`／`run_supervised(..., recovery=...)` 接受既有四類 Held；依原 scope／準備或中途 C thread 分流，不把 C 傳成 response-Step recovery，不拿 Held 當 pause-resume 授權。
- B `agents/memory_analysis/dispatch.py`、`workflows/memory_batch.py`：新增同型別 optional recovery，傳入當前 B1／B2 原角色入口；該角色成功返回後清除本次 handoff，不傳給下一 stage。
- 沿原 writer 檢查、固定 budget、原 attempt／reservation 與 Graph pending writes；不修改 executions owner、model_requests、未知 attempt 再准入、bootstrap 或 supervisor。

## Red 與驗證

新增測試：

- `apps/api/tests/unit/test_result_save_cancellation.py`：先觀察 **5 failed**，均在 saver 阻塞後真正 `Task.cancel()`，原本只有普通 `CancelledError`、沒有 typed Held；不是 import／連線錯誤。修正後另補補存再次取消及父 loop 內 C 取消案例，共 10 cases；原 R／count／C 不再外送，取消本身不執行後續工作。
- `apps/api/tests/integration/test_result_handoff_routing.py`：初次 fixture 缺 JD head，不計為產品 Red；修正 fixture 後 **6 failed, 2 passed**。A 的 preparation count／C 未分流而碰到原 unknown-attempt 防重送；B parent 不接受 recovery。修正後覆蓋 A／B1／B2 的四類 Held，另含中途 C；核 foreign scope、錯誤 writer 無新外送、固定 budget 不變、原外送不重複。
- 合成 C fixture 另補其已存在正式計量契約要求的 `cache_write_tokens=0`，沒有放寬 usage 驗證。

本輪所有 provider 回應均為 `httpx2.MockTransport` 合成資料，沒有 API 外送。PG 使用既有 loopback `_test` DB、各測例獨立隨機 schema；沒有改 Demo 資料或新增 migration。

命令（工作目錄 `apps/api`，使用既有 `.venv-target/Scripts/python.exe -B`）：

```text
-m pytest tests/unit/test_result_save_cancellation.py tests/unit/test_result_save_retries.py tests/unit/test_context_compaction.py tests/unit/test_response_recovery.py -q -p no:cacheprovider --tb=short
-m pytest tests/integration/test_result_handoff_routing.py tests/integration/test_consultant_runner_recovery.py tests/integration/test_memory_batch_orchestration.py tests/integration/test_memory_analysis_runners.py -q -p no:cacheprovider --tb=short
```

離線最終一輪：**59 passed（1.69s）**；真 PG 最終一輪：**26 passed（23.32s）**。修改的六個 production 檔 mypy（`--follow-imports=silent --no-incremental --no-sqlite-cache --cache-dir=nul`）通過；Ruff 僅檢查／格式化本切片檔案。A runner 交還主線新增串流欄位後，本代理未再修改或格式化該檔；六檔 mypy 證據屬交還前版本。未跑全套回歸。

## 官方機制與未涵蓋

2026-09-30 重新核對 [Python Task cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)：`CancelledError` 是 `BaseException`，捕捉後仍應傳遞取消。因此原本 `except Exception` 不會交出 Held。此修復不以一般錯誤吞掉取消。

[LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) 提供 checkpoint／pending writes 恢復；沿現有原生入口，不新增結果表／registry／replay cursor。實測鎖定 LangGraph 1.2.12、checkpoint 4.2.0；不能將框架保存保證擴大成跨 provider／DB 原子交易。

限制：

- 只修「完整原件已進入共用保存邊界」與角色手動明確回交。Supervisor 既有 failures mapping 會保留取消例外，但**沒有新增自動排程／自動 reentry**；呼叫方須在清除 failure／銷毀 supervisor 前保留需要的原件。User cancel 不授權恢復。
- 不證明真正新 process、舊 producer 已退出或全域 Held 不存在；不做 PID／OS stamp、Saver 共 session 或遺失原件的新 attempt 准入。
- 原切片交付時尚未涵蓋串流 terminal 後 close 取消；主線依既有 Goal 隨後分派的共同接縫及新驗證見下一節。仍無真 provider 驗收。
- 本輪為作者自審與窄測試，未派子代理；未 commit，未改其他 evidence／責任文件。

## 主線後續分派：terminal carrier → 共用原件保存（同日）

主線依既有 Goal 分派串流 terminal 後 close error／cancel 接縫，不表示使用者親自指定此技術作法。沿主線已新增的 adapter carrier，不改 adapter、runner 三個串流 composition 區塊或 Demo 程序。

- 將 `ReceivedModelResponseError`／`ReceivedModelResponseCancelledError` 從 `workflows/model_requests.py` 移到 `agent_execution/tool_steps.py` 的既有 `ReceivedModelResponse` 旁。Executor 只 import 共用型別，沒有 Graph 反向 import workflow。這兩個型別仍可從 workflow 的既有 import 位置取得同一 class，沒有第二份身分。
- model node 只捕捉帶完整 `ReceivedModelResponse` 的兩種 carrier；使用原 request、attempt 及一次產生的 operation seed 建立正常 update／Held，先走原 sync 保存交界。下一個 account node 在任何結算／工具／交付前傳回原 interruption。
- 取消不可因 LangGraph 包成 `NodeCancelledError`，或同時遇上暫時性 saver 失敗，而轉成普通錯誤後自動重試。既有 invocation 的短暫 holder 保留取消分類，交回 `ResultSaveCancelledError.save_error.recovery`；無新增持久 flag／狀態／owner。
- 若實際 task cancellation 同時打斷原生清理，仍交出完整 Held 和原取消 cause；**不宣稱已確認保存或 native cleanup 全部結束**。若保存已確認，補存入口優先重用既有 R；未確認則按原資格核對補存。取消本身不授權業務重入。

新增 `apps/api/tests/unit/test_terminal_response_handoff.py`：先 **4 failed**（normal/cancel × saver 成功/失敗）。前者直接漏出 carrier；後者被 native `NodeCancelledError` 包裝，沒有既有 typed Held。補正後四例 Green，再補真正 `Task.cancel()` 與 cancellation＋暫時性保存故障不可自動 resume，共六例。

Fresh 驗證：

```text
-m pytest tests/unit/test_terminal_response_handoff.py tests/unit/test_result_save_cancellation.py tests/unit/test_result_save_retries.py tests/unit/test_context_compaction.py tests/unit/test_response_recovery.py tests/unit/test_response_streaming.py -q -p no:cacheprovider --tb=short
83 passed in 2.31s

-m pytest tests/integration/test_result_handoff_routing.py tests/integration/test_consultant_runner_recovery.py -q -p no:cacheprovider --tb=short
18 passed in 15.12s
```

本輪僅額外修改 `tool_steps.py`、`model_requests.py` 的 carrier 定義／import 與本節；新增 terminal 測試。Ruff 通過；shared／workflow 兩檔 mypy 通過（`Success: no issues found in 2 source files`）。無外送、migration、commit 或 restart，未知 attempt 准入契約未改。
