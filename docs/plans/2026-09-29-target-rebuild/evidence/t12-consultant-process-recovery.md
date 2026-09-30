# T12：顧問程序崩潰後承接已保存工作

- 日期：2026-09-30；基底：`09fb3b50`；狀態：**四個真程序／真 PostgreSQL 案例已驗，T12 整體未完成**。
- 契約：[Agent 執行 §4.2](../../../implementation/agent-execution.md#42-已落地的單一模型工具-stept06-第二切片)、[驗證矩陣](../../../implementation/verification-plan.md)的 V07／V09、E03／E04／E12 相關部分。這份是證據，不新增恢復政策。
- 程式：[崩潰 worker](../../../../apps/api/tests/fixtures/consultant_crash_worker.py)、[跨程序整合測試](../../../../apps/api/tests/integration/test_consultant_process_recovery.py)。測試使用既有 `ConsultantRunner`、正式控制 wrapper、候選工具與完成交易；只在外部 SDK 傳輸使用合成回應。

## 1. 先使用既有機制，不新增恢復引擎

Owner 要求優先借鑑成熟框架並減少非必要自訂機制。本輪複核：

| 官方機制 | 本案採用及限制 |
|---|---|
| [LangGraph persistence／checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | 既有 checkpoint 與 pending writes 承接已保存結果；恢復使用同一 thread 的正常接續，不另存模型結果或製作私有 checkpoint 格式。 |
| [LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) | 原生 retry／timeout／error handler／drain 是後續控制接線的優先比較對象，不代表本輪已遷移。Graph superstep 不等於本產品模型 Step；重試整個模型 node 也不等於只補存仍握有的原回應。 |
| [SQLAlchemy transaction](https://docs.sqlalchemy.org/en/21/orm/session_transaction.html)與 [Temporal Activity idempotency](https://docs.temporal.io/activity-definition#idempotency) | 業務效果仍須由原操作身分、交易與既有結果判定。即使另用持久工作流平台，操作成功但回報前崩潰仍需冪等；不能把框架完成通知當跨系統原子提交。 |

**本案取捨：**繼續使用既有 LangGraph＋PostgreSQL，先驗正式角色接線。先前未提交、未部署的 PID／producer provenance 試作及其新 migration／直接依賴已撤下；不把未完成的核對器擴成另一套程序身分服務。本輪無產品程式、依賴或 schema 變更。這不是宣稱框架解決所有未明結果，也不刪除既定有界恢復要求。

## 2. 切斷位置與可觀察效果

每個測例在明確的 loopback `_test` DB 建立獨立 schema；第一個子程序在指定實際 saver 邊界呼叫 `os._exit(19)`，不執行正常 async／finally 清理。父程序確認它已退出後，透過既有 execution owner 取得新 writer；第二個全新子程序使用未修改的官方 `AsyncPostgresSaver` 承接。故障注入只存在測試 fixture。

| 切斷位置 | 恢復要求與已觀察結果 |
|---|---|
| 第一個 input count 已可靠保存 | 不重新計數，繼續原模型請求及工具流程。 |
| 第一個完整模型 R 已可靠保存 | 不重呼第一個模型；依原 call 執行 JD 候選工具。 |
| JD 工具交易已提交、tool result 尚未保存 | 允許再次進入原工具，查回同一操作結果；恢復前後 JD 修訂 ID 集合完全相同，不新增重複效果。 |
| 第二個模型的完整 final R 已保存、產品尚未完成 | 不重呼模型，採用原答覆完成原 Turn。 |

共同斷言：

- 崩潰後、恢復前，正式 JD 尚無候選職稱，正式訪談仍只有開場序號 1。
- 跨兩程序合計只有 `count 1 → model 1 → count 2 → model 2`；每次 count 與相應 model 的實際 input hash 相同，不重新組裝另一份輸入。
- 第二個請求在 SDK 傳輸邊界另外核對原 reasoning、commentary、function call、function result 的順序、身分及內容，不以 input hash 相同代替接續完整性。
- 恢復後正式序號為 1、2、3，原 Turn 為 completed，正式 JD 職稱正確且只有一筆直接來源，仍指向該 Turn 原員工輸入的 source identity。
- 已提交候選的兩案比較全部 JD 修訂 ID，而不只看最後文字或回傳 success。final 正文與原合成答覆相同。

這組證據會捕捉重呼已存結果、遺失工具配對、重複候選修訂、過早正式化、遺失來源或未完成原 Turn；不是只測框架能啟動。

## 3. 實測及測例修正

這是既有實作的故障驗證，**非產品功能的 TDD Red–Green**。最初四案都在最後「預期 JD 修訂數為 2」失敗；核對 `JdProfileWriteWorkflow.execute` 後確認既有工具在同一交易內先建立文字修訂，再建立引用修訂，加上初始版為 3，並非恢復重複寫入。沒有為使測試通過改產品程式，也沒有放寬不重複效果的要求；改用恢復前後固定修訂 ID 集合比較，避免把內部修訂切法當產品不變量，並追加原來源身分斷言。

工作目錄 `apps/api`，使用既有 `.venv-target`，明確設定隔離測試 DB；不載入 `.env`：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/integration/test_consultant_process_recovery.py -q -p no:cacheprovider --tb=short
```

結果：初版 **4 passed in 20.58s**；補強下述審查缺口後 **4 passed in 20.28s**。Ruff check／format 通過這兩個新檔。SDK `MockTransport` 攔截所有模型流量；沒有 OpenAI 遠端、費用或模型品質驗證。測試只回收自己的隨機 schema，沒有停止 Demo 或更動 Demo 資料。

## 4. 邊界與後續

- 這裡的 writer 接管由測試明確呼叫，**不證明 production supervisor 已能自動辨識所有冷啟動狀態**。
- 不涵蓋 R／C／count 未保存且程序已消失的原件遺失判定；當時後續建議為 [T06 §18.1](t06-agent-execution.md#181-未明-attempt-的受控再准入接縫2026-09-30)的可信核對 callback。**本檔 §6 已依 Owner 新指示收斂：首版允許安全結束，不要求完成此自動再准入。**取得鎖／新 writer／查不到結果仍不直接授權重送。
- 本輪不新增 Memory pin 交錯、B1／B2 回交、compaction、取消競爭、正式提交確認遺失或 HTTP／UI 自動重連的驗證。已有相應元件證據不能冒稱這四案已驗全部角色旅程；依原 T12 gate 補齊。
- 語意品質、真 provider 串流／容量、完整訪談到 PDF 與乾淨交付仍在原 T16–T18；本輪不勾選任何完整任務。

## 5. 受影響回歸與審查

主代理執行同一隔離 DB 的七個整合檔：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/integration/test_consultant_process_recovery.py tests/integration/test_consultant_runner_recovery.py tests/integration/test_consultant_completion.py tests/integration/test_consultant_controls.py tests/integration/test_consultant_supervisor.py tests/integration/test_response_recovery_eligibility.py tests/integration/test_unknown_attempt_readmission.py -q -p no:cacheprovider --tb=short
```

結果：初次 **54 passed in 51.18s**；修正審查缺口後重跑 **54 passed in 57.55s**（含上述四案，不與四案加總）。這涵蓋原件控制交接、完成／取消／暫停、既有 supervisor 及未明 attempt 的合成可信判定；未明 attempt 測例的 callback 仍是替身，不因整組通過宣稱正式調度完成。兩個新測試 Ruff check／format 通過；三份異動文件 **118 個本地連結／anchors 零錯**。未修改架構圖及產品流程，不重繪相同圖稿，也不因新增測試重跑不相關前端／模型品質 gate。

獨立審查指出一個 P2 **測試缺口**：原 SDK 替身只要看到 `function_call_output` 就回覆，遺失原 `function_call` 仍可能通過；兩請求 hash 相同不代表內容完整。審查者在恢復子程序記憶體中包裝 `tool_steps.response_input_items`，只濾掉 `function_call`，原測例仍為 **1 passed、3 deselected**，證明原斷言不足，而非正式程式已發生此錯誤。

修正僅在測試 fixture：用獨立的明確期望核對四項原生資料的順序，以及 reasoning 的 encrypted content／未知 metadata、commentary 的 phase／原文、工具 name／arguments／call ID、工具結果。主代理重播相同的程序內變異，得到 **1 failed、3 deselected in 5.52s**，錯誤正是缺失原 model／tool exchange；取消變異後四案通過。沒有改正式 serializer、業務操作或持久資料來配合測試，變異亦未寫入產品檔案。

## 6. 首版恢復減法與最外層失敗收尾（2026-09-30）

Owner 指示「核心有就好，不用太嚴格，避免卡住」。有效政策在[共用執行 §6.4](../../../specs/2026-09-27-shared-agent-execution-and-state-design.md#64-首版恢復範圍能續作不能續作則安全退出)，本節只記實作與證據。

**根因：**原 A／Memory supervisor 會保存 runner 例外，並避免同程序無限派送；但 bootstrap 未接最終業務收尾。無法由既有機制恢復的錯誤可能留下沒有 runner 的 `active` execution。不是缺另一套 durable workflow，而是既有 owner 未接到最後一層。

**最小修正：**新增一個共用 `run_with_failure_boundary`，bootstrap 分別注入 A／Memory 的原收尾交易。有限恢復仍在原層，最後才核對正式完成／丟棄候選；不攔 task cancellation、不新增自動再推論、資料表、依賴、回執或恢復 UI。記錄安全錯誤分類，不記訪談及 provider 原文。業務收尾若不可確認仍拋錯，不能把資料庫離線說成已回滾。

**研究：**2026-09-30 複核 [LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)的有限重試與末端處置，以及 [Python cancellation](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)。未改用 node-level `error_handler`，因本次收尾涵蓋 Graph 外的正式提交及控制 wrapper；放最外層才能核對已提交結果。沒有重寫框架內的 retry／checkpoint。

**TDD 與範圍：**先寫 production bootstrap＋真 PG 的三個反例，得到 **3 failed in 10.87s**（A 一般錯誤／未明舊 attempt 仍為 active，Memory 無持久 failure）；補接線後 **3 passed in 2.31s**。初次從 repo root 執行的 import collection error 不算 Red，改以文件規定 `apps/api` 工作目錄執行。再加完成已提交／正常 shutdown／收尾本身失敗三案，六案 **6 passed in 3.53s**；後三案屬事後回歸，不宣稱全部先測後寫。

這些反例使用合成角色／故障注入，但保留真 HTTP、lifespan、supervisor、PostgreSQL 與原業務 owner，證明接線效果，不冒充模型能力。A 失敗候選不污染正式 JD／訪談，可再接受不同 Turn；Memory 本批 discarded、有持久阻塞、不輪詢重跑，A 仍可准入。原正式完成及輪前基底保持不變，task shutdown 不變成產品取消。收尾 DB 故障仍需恢復服務，未實作自動健康修復或 Memory 條件監測器。

**獨立審查與修正：**審查找出初稿的 P2：A／Memory 的舊 `run_supervised` 內層已會收尾，外層再次捕捉其收尾例外，導致第二次收尾，Memory 還可能以同操作身分換成另一個原因碼。主代理先保留實際內層，在兩角色注入「收尾 COMMIT 後確認遺失」，得到 **2 failed in 2.10s**，兩案均觀察到收尾兩次。修正是移除內層 wrapper，而非增加旗標：bootstrap 只包 raw `run`；Memory 的已知原因分類集中於 `settle_failure`；收尾自身例外直接傳遞。既有原件恢復測試／fixture 改叫 `run`，沒有刪減斷言。複審未發現新的可行動 P1／P2；審查者未另跑 PG，以下結果由主代理執行。

最終回歸（工作目錄 `apps/api`，同前述隔離 `_test` DB）：

```powershell
$recoveryTests = @(
  'tests/integration/test_execution_failure_boundary.py',
  'tests/unit/test_execution_failures.py',
  'tests/integration/test_consultant_process_recovery.py',
  'tests/integration/test_consultant_runner_recovery.py',
  'tests/integration/test_consultant_completion.py',
  'tests/integration/test_consultant_controls.py',
  'tests/integration/test_consultant_supervisor.py',
  'tests/integration/test_memory_supervisor.py',
  'tests/integration/test_consultant_http_execution.py',
  'tests/integration/test_consultant_memory_http_journey.py',
  'tests/integration/test_memory_outcome_failure.py',
  'tests/integration/test_memory_batch_orchestration.py',
  'tests/integration/test_memory_candidates.py',
  'tests/integration/test_result_handoff_routing.py'
)
./.venv-target/Scripts/python.exe -B -m pytest @recoveryTests -q -p no:cacheprovider --tb=short
```

結果 **89 passed in 94.76s**（包含本次 8 案，不與先前 47／22／11 案相加）。11 個異動 Python 檔 Ruff check／format 通過，4 個主要接線檔依專案 mypy 規範通過。本次六份文件的連結檢查另比對 HEAD：935 個本地連結，**零新增錯誤**；決策登記舊條目已有 87 個失效連結／anchor（多為已移除 worktree），不冒稱全文件零錯誤，也不在本切片改寫歷史。

未使用 `.env`、未外送模型、未改 Demo DB／程序，沒有新 migration 或部署。未跑新的瀏覽器／真模型品質驗收，不把本次收尾與故障測試當成 T16–T18 完成。後續回到核心產品旅程與既有 UI 差異檢視缺口；不再為同一罕見原件遺失擴建證明系統。

## 7. 任務完成對照（2026-09-30 恢復後）

沿[任務表 T12 的 Red 與完成條件](../tasks.md#t12-真-postgresql-故障與競爭整合)及 [E01–E15](../../../specs/2026-09-27-shared-agent-execution-and-state-design.md#71-職責異常測試映射全部待執行)逐條對照既有測試，範圍依 Owner 的[首版恢復減法](#6-首版恢復減法與最外層失敗收尾2026-09-30)：能續作的續作，不能續作就安全退出。路徑相對 `apps/api/tests`；除註明外皆為真 PostgreSQL。

| Gate | 對照 |
|---|---|
| E01 R／C 序列化及下一 request | `contracts/test_response_serialization.py`、`contracts/test_openai_native_items.py`、`contracts/test_graph_serialization.py`、`integration/test_graph_postgres.py`；遠端接受性見 [T06 §6、§20](t06-agent-execution.md#20-真-compact-協定預檢2026-09-30-恢復後) |
| E02 R 已存、工具未做 crash | 本頁四個**真子程序 `os._exit`** 案（`integration/test_consultant_process_recovery.py`）；`integration/test_response_step_postgres.py::test_saved_step_reopens_without_repeating_window_items` |
| E03 R 在但保存失敗／確認遺失 | `integration/test_response_step_postgres.py::test_public_step_recovery_saves_held_model_result_after_both_writes_fail`、`integration/test_result_save_retries_postgres.py`、`integration/test_consultant_runner_recovery.py` |
| E04 P1 提交後、Graph 結果前 crash | 本頁「JD 工具交易已提交、tool result 尚未保存」案（比較全部 JD 修訂 ID）；`integration/test_memory_tool_step.py::test_committed_first_write_recovers_original_before_dependent_second_write` |
| E05 原操作查不到／同 ID 不同參數 | `integration/test_input_acceptance.py::test_command_scope_is_per_file_and_conflicting_payload_is_rejected`、`integration/test_jd_candidates.py::test_candidate_command_identity_cannot_be_used_for_a_manual_edit`、`integration/test_jd_candidates.py::test_new_writer_can_recover_but_old_writer_cannot_write` |
| E06 Step 已存但確認遺失；存在更晚候選 | `integration/test_response_recovery_eligibility.py`、`integration/test_consultant_context_binding.py::test_reconnect_restores_exact_request_and_bindings_after_memory_and_candidate_advance` |
| E07 暫停到達各控制點 | `integration/test_execution_control.py`（13 案）、`integration/test_consultant_controls.py`、`unit/test_response_pause.py`；瀏覽器：[T09 旅程](t09-consultant-journeys.md) |
| E08 取消與正式完成同時發生 | `integration/test_consultant_completion.py::test_complete_and_cancel_race_has_one_atomic_outcome`、`integration/test_interview_completion.py::test_cancel_racing_completion_cannot_leave_a_half_formal_exchange`、`integration/test_execution_admission.py::test_cancel_and_complete_compete_for_one_durable_terminal_outcome` |
| E09 取消／失敗後改送 b | `integration/test_role_context_history.py::test_cancelled_work_cannot_replace_prepared_history_for_new_input`、`integration/test_execution_failure_boundary.py::test_escaped_consultant_failure_discards_draft_and_allows_new_input`；瀏覽器：T09 旅程的取消與被拒絕後重新開始 |
| E10 B1／B2 回交後 crash | `integration/test_memory_batch_orchestration.py::test_reentry_after_b1_handoff_skips_b1_and_preserves_work`、`test_memory_analysis_runners.py::test_b1_b2_rework_retains_candidate_private_history_and_original_frontier` |
| E11 C 返回未存／已存未明採用／已採用又取消 | `integration/test_compaction_accounting.py`、`integration/test_context_preparation_postgres.py`、`unit/test_context_compaction.py` |
| E12 A 完成或 Memory ③ COMMIT 後確認遺失 | `integration/test_execution_failure_boundary.py::test_completion_acknowledgement_failure_preserves_original_result`、本頁「final R 已保存、產品尚未完成」案 |
| E13 A 完成後 B 未領取／領取確認遺失／新上界並行 | `integration/test_memory_supervisor.py`、`test_memory_batch_orchestration.py`、`test_memory_candidates.py::test_concurrent_reentry_has_one_effect_and_competing_position_is_rejected` |
| E14 候選預覽、匯出、嘗試改稿 | 後端：`integration/test_consultant_status.py::test_status_preview_reads_fixed_candidate_without_changing_formal_jd`、`integration/test_jd_export.py`；瀏覽器：T09 旅程（候選預覽與正式 PDF、處理中 JD 唯讀）與既有 `jd-profile`／`jd-work` 的「A 已准入拒絕人工修改」 |
| E15 不疊 retry、不重置預算、容量超限、DB 等待 | [T06 §21](t06-agent-execution.md#21-任務完成對照2026-09-30-恢復後)；**本輪另發現並修正串流中的限流被誤判為終止性失敗**（[T06 §22](t06-agent-execution.md#22-串流中的限流被誤判為協定錯誤2026-09-30-恢復後的診斷與修正)） |

Red 清單（R 已存、工具已 commit、Step 已存、final 已 commit、C 採用、B 交接後故障；舊 writer 與新 runner 競爭）：上表逐項有對照；舊 writer 競爭見 `integration/test_execution_admission.py::test_replacement_fences_old_writer_and_cannot_be_silently_replaced_again`、`integration/test_consultant_leader_release.py`。

**結論：**在首版恢復範圍內，T12 的故障與競爭整合成立，勾選。**明確不含（依 Owner 減法，不是遺漏）：**未明 attempt 的 production 再准入與原件遺失證明、任意位置的自動續作；程序被外力硬殺時若尚未保存任何原件，新 Turn 需使用者主動重送。**仍歸其他任務：**大視窗 compact 延遲與容量（T16）、真 provider 故障行為（T16／T17，例如串流限流已由本輪實測暴露並修正）、長時間 soak 與 UI 全跨瀏覽器（T15／T17）。
