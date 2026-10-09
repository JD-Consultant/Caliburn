# Agent 程序監督、控制與背景調度

本頁維護現行單機 runner 的領導資格、啟停、A 控制、最外層失敗收尾及 Memory 持久調度。Supervisor 擁有程序內 task 與鎖；領域 workflow 裁決正式結果；[Graph 執行](agent-execution.md)承接原生進度；[模型外送](model-requests.md)負責准入與 provider 重試。

按問題閱讀：[啟停與 writer 接管](#1-本機-a-supervisor) → [A 暫停／取消／續作](#2-a-pausecancelresume-控制) → [最終失敗怎麼收尾](#3-最外層失敗收尾)。角色能力恢復見[公版工具接線](#4-公版工具的可選角色接線)，已成立的整理要求見 [Memory 背景調度](#5-memory-背景工作)。

產品完成、取消及保留政策沿[共用執行契約](../specs/2026-09-27-shared-agent-execution-and-state-design.md)及[資料交易](../architecture/persistence.md)。本頁不另定終態；實際恢復範圍與未驗情境沿各節證據。

## 1. 本機 A Supervisor

`workflows/consultant_supervisor.py` 借入 `runner.run` 與 session factory，擁有
`adapters/process_lock.py` 及所有 asyncio task：`start()` 先取鎖再掃描、`notify(scope=None)`
只喚醒持久查詢、`close()` 先取消並等待本機 runner 退出，最後關閉鎖。HTTP／lifespan
組裝由 bootstrap 負責，不把 HTTP BackgroundTasks 當隊列；未配置模型不啟動。

- executions 公開 `list_active_consultants()` 只列 active A，不恢復 paused／終態／Memory。
  專用非 pooled PG session advisory lock＋同一主機帳戶/temp 目錄的 OS file lock 是 writer
  替換的准入依據；所有 A runner 必須走此入口。OS lock 補足「PG session 已斷，但舊 task
  還在清理」的實測反例；不能只靠 writer CAS 宣稱 checkpoint 分支沒有並行寫入。
- 強參照保存 monitor／runner／shutdown tasks，預設至多四個不同 Turn 並行，同 scope 一次。
  啟動立即關閉也須收尾；取消等待中的 caller 不讓鎖提前釋放。清理尚未退出則不放鎖。
- DB 監督 I/O 一次失敗即停止准入並收尾，不自動重連接管；scan 有 10 秒界線、鎖 I/O 5 秒。
  runner 例外／含原件的取消 handoff 留在 `failures`；`stopped_reason(scope)` 僅給安全原因碼。
  重複通知不重跑未知外送，不重置 budget，不判定產品 Turn 已取消／失敗／完成。
- 範圍是單機同帳戶部署，不宣稱多主機網路分割接管。明確 interrupt resume 見下節；失敗
  終局及 UI 呈現由上位協調。lock file 不含資料，
  不刪除以避免刪除重建後出現兩份 inode；OS handle 關閉／程序退出釋放實際鎖。

驗證：本機 supervisor 與程序恢復。Windows 使用 SelectorEventLoop；部署範圍限單機同帳戶，不承諾多主機接管或所有 crash 組合均通過。

依據：[Python Task 強參照與取消](https://docs.python.org/3.14/library/asyncio-task.html)、
[PG session advisory lock](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS)、
[Windows 非阻塞 file locking](https://docs.python.org/3.14/library/msvcrt.html#msvcrt.locking)。
官方提供鎖／task 語意；雙鎖生命週期及有界停止策略是本機部署取捨。

## 2. A pause／cancel／resume 控制

`ConsultantControlWorkflow(sessions, checkpointer, supervisor)` 提供 `pause(scope)`、
`cancel(scope)`、`resume(scope)`，回傳執行資格模組的 `ExecutionInfo`。App 綁定 scope；
UI 不傳 writer、checkpoint 或 interrupt ID，Memory kind 不得進入。

- pause 只記持久意圖，未 claim writer 也合法；Graph 沿既有完整 Step interrupt 才確認 PAUSED。
  cancel 先由 `ConsultantCompletionWorkflow.stop` 同交易 fence／discard，確認後才中止本機 task；
  若正式完成已先成立，回原 COMPLETED，不回滾 JD／訪談／歷史。
- resume 和 supervisor claim／launch 序列化，先等舊 paused invocation 退出，再沿公開
  `read_response_pause` 以原 builder／validator 查當前原生 interrupt。無原 interrupt 不放行。
  正式受理由執行資格模組設為 ACTIVE 並清除 pause intent；不新增控制表、State 或模型參數。
- bootstrap 將 `runner.run` 經 `run_consultant_with_controls` 及 [最外層失敗收尾](#3-最外層失敗收尾) 的唯一失敗收尾注入 supervisor。
  wrapper 從原 execution＋原 Graph 重讀已授權的 interrupt，因此 resume COMMIT 後、喚醒前
  中斷仍可接續。只由受控 resume 清除 `_attempted`，普通 notify 不授權重送或復活取消工作。
- final 離開 Graph 後才收到 pause，若完成交易被 A 完成工作流拒絕，wrapper 僅在原 writer 仍有效、
  pending pause、完整 final Graph 已確認時，重入一次既有純控制交界；不重送模型。不攔截
  response-save recovery handoff、不加外送 retry，不重建 pinned context／budget。
- wrapper 可接受 App 仍持有的 typed `recovery`，先交原 runner 核對原 thread／request／
  checkpoint（含 pending writes），不將它轉成新模型請求或 interrupt resume。採用後若有
  pause 要求仍停在完整 Step；之後按原 interrupt 續作，不重傳已消耗的 handoff。取消／
  失效 writer 仍由執行資格模組拒絕。這是內部原件交接，不是新的 HTTP 重試操作，
  也不代表 supervisor 已能自動判定跨程序遺失或啟用再推論。

驗證：A 控制與完成、程序恢復。合成 transport、真 PG 與真模型各自列明層級，不能互相替代。

## 3. 最外層失敗收尾

依 [核心恢復範圍](../specs/2026-09-27-shared-agent-execution-and-state-design.md#64-恢復範圍能續作不能續作則安全退出)，`bootstrap.py` 在 A 的控制 wrapper 與 Memory batch 外共用 `workflows/execution_failures.py::run_with_failure_boundary`。它不是第二個恢復引擎；不增表、重試、模型參數或 UI 控制。

```text
既有角色執行／checkpoint 接續／有界恢復
  ├─ 正常返回 → 保留既有完成或暫停結果
  ├─ task cancellation → 向上傳遞，保留重開進度
  └─ 未處理 Exception → A／Memory 完成工作流核對並收尾
       ├─ 已正式完成 → 保留原完成
       ├─ 尚未完成 → 放棄本次候選，提交 failed
       └─ 收尾未確認 → 向 supervisor 回報，不偽造終態
```

- A 沿 `ConsultantCompletionWorkflow.stop(FAILED)`；Memory 經 `MemoryBatchWorkflow.settle_failure` 保留既有 provider／分析結果／容量等原因分類，再沿 `MemoryConsolidationWorkflow.fail` 收尾；未分類錯誤只用安全代碼 `execution_interrupted`。候選丟棄與終態仍是原有短交易，正式完成競爭由原 job lock／writer fence 決定，不以 Python 例外推翻成功。
- 原生已存資料照常接續；仍握有的原回應先走既有有界補存。最終離開原恢復流程後，本邊界可結束該次工作，不再為同一未明外送增加新的恢復平台或盲目重送。既有低層 typed recovery API 保留，但不宣稱所有原件都要永久救回。
- `except Exception` 不攔 `asyncio.CancelledError`；正常關閉、控制取消及失鎖清理仍走原生命週期。原件補存的 cancellation subclass 同樣傳遞。
- 日誌僅記 execution identity、kind、exception type，不記原錯誤訊息、provider body、原文或 reasoning。收尾自身失敗向上傳遞，不能顯示假 failed；DB 全面故障時仍需恢復服務，不承諾離線提交。
- 通用 supervisor 只擁有 task／領導資格，不新增 JD／Memory 判斷；bootstrap 明確注入各自既有的業務收尾。
- A／Memory 產品執行只在最外層收尾一次；原件接續與故障注入直接呼叫 `run`。收尾自身拋錯直接回 supervisor，不再次分類或第二次提交，也不把原 Memory failure reason 改成通用原因。

## 4. 公版工具的可選角色接線

公版工具的可選接線依 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)：bootstrap 只在明示配置時供 A 注入 RAG client，B1／B2 只增加排除範圍唯讀工具。角色先從自己的原 preparation checkpoint 還原模板，工具權限沿已捕捉 request；同工作重入不換提示或增加工具。A 的公版寫入 command 沿既有 prepare／execute／result 節點，重播不倒帶候選；B 的排除讀取沿原 Memory binding／F。

`ConsultantRunner._tools` 在建立公版候選前，核對原 captured request 的工具組與寫入結果格式。公版工具缺漏、名稱重複或格式混用時拒絕；合法請求由 `occupation_reference_write_result_format` 決定 handler 的回傳模式。

這個判斷使用原工具定義，不讀當前全域設定。已保存的 native output 直接接續，只有尚未完成的命令才沿原模式 execute。固定描述後綴及兩種結果格式只在[公版工具契約](../specs/2026-10-04-public-reference-completion-design.md#工具契約接續改善2026-10-05)完整定義，回歸與獨立審查保存實際證據。

## 5. Memory 背景工作

`request_memory_consolidation` 先沿共用工具機制保存原 intent，再交 `MemoryConsolidationWorkflow` 持久記錄本次要求。**此時尚無正式訪談資格** 。A 正式完成交易保存有效訪談後，調度器從這個既存要求、已完成 execution 與該輪正式員工輸入推得 F；不另設完成交易雙寫的 frontier／通知表。取消／失敗的 A 不具資格。同檔案只一批，後來要求合併待處理上界但不擴大在途 F；重啟可從持久事實重新發現要求，不靠記憶體通知或 broker。

B1 完成 → 保存②及變更概覽 → B2 分析 → 共同發布。B2 不回交 B1；它按需讀目前情境及合法原話，維護工作理解，資料不足則保留未知或矛盾。兩者都只回傳 `{"status":"complete"}` 表示自己的分析完成，發布仍由 Parent 協調原有短交易。沒有固定互審或額外審核角色。

階段結果只接受 `complete`。未完成批次若保留舊 `needs_situation` 結果，沿失敗流程保留已發布快照，不推進整理上界、不改寫原模型輸出，也不重跑 B1。合法的同階段恢復、Step 壓縮與跨批歷史接續仍可用。

最終失敗保留原已發布快照，系統記已知原因與可恢復條件，不自動無限重跑；A 在下一個合法資料交界得簡短必要狀態並繼續訪談／原話回讀。使用者沒有 B 暫停／取消／重試工具。解除阻塞由系統按原資格／未發布有效範圍處理，不跳過未整理資料，也不重新給被取消 A 輸入資格。解除條件只有訪談進度：失敗時 `fail` 把當時的正式訪談前緣存入該失敗紀錄，之後正式序號再前進 6（三輪完成的訪談）才由 `read_block` 視為已解除，一次新批次從已發布涵蓋承接；新要求、重啟或時間不解除，不新增計時器、重設額度或手動入口（`RETRY_AFTER_NEW_MESSAGES`）。這個解除政策仍待確認，且尚未在真長旅程自然觸發；產品語意見[產品概念](../product-concept.md)。
