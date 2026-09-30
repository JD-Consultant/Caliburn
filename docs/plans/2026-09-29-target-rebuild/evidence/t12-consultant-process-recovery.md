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
- 不涵蓋 R／C／count 未保存且程序已消失的原件遺失判定；可信核對 callback 與受控再准入仍沿 [T06 §18.1](t06-agent-execution.md#181-未明-attempt-的受控再准入接縫2026-09-30)完成，不能以取得鎖／新的 writer／查不到結果直接授權重送。
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
