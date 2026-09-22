# Managed App 背景 callback 與文件範圍組裝設計

- 日期：2026-09-17
- Topic：`JD-R002／MEM-L001`
- Stage：**G7 離線窄切片完成**
- 狀態：managed App 的生命週期、共享顧問 graph、文件範圍注入與背景恢復已完成離線接線與回歸；本稿不代表真模型／付費、完整瀏覽器 App 旅程、layered C、跨 process admission 或 production authority 已完成

## 1. 結果與範圍

本切片已把既有 A 顧問、B1／B2 背景 Memory workflow、dispatcher、正式角色模型及 App 資源接成同一個可管理的本機服務：

```text
一個 managed App process
├─ 一個共用 A 顧問 graph
├─ 一組共用 A／B1／B2 model objects
├─ 一個 App-owned BackgroundCoordinator
│  └─ 按 document_id 延遲組裝既有 dispatcher／B1-B2 workflow
└─ 同一組 PostgreSQL／Saver／Store／publication 資源
```

核心規則是：

1. **App／Runtime 管理生命週期與背景啟動；LLM middleware 不啟動背景工作。**
2. **顧問 graph 共用；文件身分與文件範圍資源在每次 invoke 時由 Runtime 注入。**
3. **資料庫、checkpoint、admission 與 publication 才是可恢復權威；process 內物件只是可重建的執行資源。**
4. **前景回合確實結束後才喚醒背景；重新啟動時先恢復前景，再於 Runtime ready 後恢復背景。**
5. **維持單一 OpenRouter credential 與既有 A／B1／B2 模型、Prompt、Memory、compaction、引用、版本及 publication 規則。**

本稿不新增另一個 Agent、DB table、queue、scheduler、polling loop、Memory registry、provider 或摘要機制，也不處理 layered C、文件封存、artifact GC、自然模型品質、完整 UI 旅程或 production 採用。

## 2. 已確認的現況與真正缺口

### 2.1 可直接沿用

- `open_consultant_runtime()` 已建立 caller-owned sync／async clients、A／B1／B2 三個角色模型及共用 A graph；建構不送 provider request。
- `ManualHost` 已擁有同一 process 的 DB engine、Saver、Store、Memory engine 與前景／背景執行池；背景池固定單一 worker。
- `build_background_memory_workflow()` 已能在 caller 提供的正式資源上，依 `document_id` 組裝隔離的 B1／B2 workflow。
- `BackgroundDispatcher.wake()` 已以既有 durable admission、workflow checkpoint、publication 與窗口狀態決定等待、恢復或提交工作；同一 dispatcher 另有 process-local single-flight 防重。
- `AiRuntime._settle()` 已有「前景安全結束後才喚醒背景」的 callback 位置。
- `BackgroundAvailability` 已將背景狀態縮成一次最小系統提示；它只應通知 A，不應提交背景工作。

### 2.2 本切片已封閉的兩個接線缺口

**缺口一：graph 建立早於 App 文件資源。**施工前 availability middleware 要在 graph 建構時綁入 `BackgroundAdmissions／BackgroundWindows`，但這些 reader 只有 managed App 開啟 DB／host 後才存在。現已由每次 invocation 的 Runtime context 注入可信任 provider；共用 graph 不保存 reader、「目前文件」或 mutable proxy。

**缺口二：重新啟動時背景 wake 發生得太早。**施工前前景恢復 callback 會在 `ManualRuntime.finish_startup()` 尚未把 Runtime 標為 ready 時嘗試 wake；background admission 會以 `startup_pending` 拒絕，而上層又把錯誤隔離掉。現已讓 low-level previous-host recovery 不 wake，待 `finish_startup()` 完成並標記 ready 後，才由 coordinator 掃 catalog、依 durable state 逐文件恢復。

這兩個問題是 managed assembly／生命週期接線問題，不是 Memory、compaction 或 B1／B2 語意問題。

## 3. 官方事實、共同原則與本案取捨

### 3.1 官方事實

- OpenAI Agents SDK 把 local context 定義為 dependency injection：傳入 runner、agent、tools、handoffs 與 lifecycle hooks，但不會自動送給模型；要讓模型看見內容，仍須經 instructions、input 或 tool 等明示投影。
- LangChain runtime context 同樣用於把 user／document scope、DB connection 等 dependency 注入 tools 與 middleware，避免 hard-coded 或 global state；呼叫端在 invoke 時提供 context。
- LangGraph 的 durable execution 依賴 checkpoint；可重放流程中的 side effect 必須保持 deterministic／idempotent，持久 task 結果與 process 內執行物件是不同責任。
- LangGraph Agent Server 在需要 per-run customization 時才動態建立 graph；一般情況可共用 compiled graph。其 durable task／checkpoint 與 ephemeral queue／signal 也分開管理。
- Anthropic 將可恢復的長任務狀態放在 harness 外部的 durable session／event log；harness 可被替換，恢復時由 session identity 明確喚醒。其 context engineering 也建議只投影當下需要的高訊號內容，並以按需回查取代無差別載入。
- AWS 對可重試或並行 side effect 的通用要求是 idempotency 與條件寫入；多 writer 時需由原子條件保護，不能只靠「先查再寫」。

### 3.2 跨來源共同原則

上述來源共同支持的是：

- orchestration、lifecycle 與 side effects 由 App／harness 管；
- request scope 由 per-run context／dependency injection 傳遞，不放 mutable global；
- durable state 是恢復權威，process 物件可重建；
- 模型只接收經 App 明示投影的必要內容；
- 重啟後由已開妥的 Runtime 依 durable state 恢復，而不是靠舊 process 記憶。

它們沒有規定 Caliburn 必須使用某個固定 class、欄位或 scheduler。下節是依本產品現有能力作的映射，不冒稱廠商固定架構。

### 3.3 Caliburn 取捨

採用一個 App-owned `BackgroundCoordinator` 作組裝與生命週期邊界；它沿用既有 dispatcher／workflow，並將文件範圍的 availability provider 注入每次 A invoke。A graph 本身不保存文件、DB reader 或「目前專案」。

不導入 LangGraph Agent Server、Temporal、Redis、外部 queue 或第二套 durable runtime。那些元件在多 process／分散式 worker 才可能有價值；目前單機、單 App process、既有 host lease 與一個背景 worker 的拓撲下會重複既有 Saver／admission／publication 權責。

## 4. 正式組裝

### 4.1 Process-owned 資源

AI-enabled App 開啟時，由同一 process owner 建立並持有：

- OpenRouter sync／async clients；
- A、B1、B2 三個角色模型；
- 一個共用 A graph；
- `ManualHost` 的 DB、Saver、Store、Memory engine 與執行池；
- 一個 `BackgroundCoordinator`。

普通無 key 模式不建立模型與 coordinator；人工 JD 功能保持可用，既有 durable pending background 工作留待下次 AI-enabled 啟動恢復，不做 provider fallback。

### 4.2 BackgroundCoordinator

`BackgroundCoordinator` 只負責三件事：

1. `wake(document_id)`：為該文件延遲取得或建立既有 `BackgroundDispatcher` 與 `BackgroundMemoryWorkflow`，再呼叫既有 wake 流程。
2. `availability(document_id, published_head)`：用既有 admission／window reader 產生背景 availability notice。
3. `resume_pending()`：Runtime ready 後列舉本機 catalog 文件，逐份呼叫 `wake()`；是否真的啟動、恢復或等待仍由 durable state 判斷。

Coordinator 可保有一個加鎖的 `dispatchers_by_document` map，以重用每份文件現有 dispatcher 的 `_wake_lock／_running`，形成 keyed single-flight。這個 map：

- 不是 document registry 或 workflow authority；
- 不保存業務狀態、Memory head 或「目前文件」；
- process 結束即可丟失；
- 重新啟動後完全由 catalog＋durable state 重建；
- 第一版本機產品不另做 map GC，也不因此恢復已取消的文件封存需求。

### 4.3 共用 graph 的 per-invocation context

共用 A graph 永遠包含一個無 document-bound reader 的 availability middleware。每次 `AiRuntime` 呼叫 graph 時，由 App 在 `ConsultantContext` 放入可信任的 local provider；provider 接受 Runtime 已知的 `document_id／published_head`，回傳最小 notice 字串。

```text
App／Runtime 已知 document_id 與本輪 Memory head
    ↓ local runtime context；不直接送模型
BackgroundAvailability 每個 employee input 讀一次 provider
    ↓
只把最小 notice 字串投影到 system context
```

Provider、DB handle、coordinator 與 callable 都不成為模型訊息或 checkpointed 業務狀態。middleware 不可在這裡 wake、重試、等待或修改背景狀態。缺 provider 的測試／人工模式得到空 notice，不偷偷開啟資源。

沿用既有「同一員工輸入只讀一次、後續 model steps 重用 state 中 notice」的效果；不得因工具迴圈重複查 DB 或把背景狀態不斷附加到 context。

## 5. 生命週期與順序

### 5.1 啟動與重啟恢復

```text
開啟 host／DB／Saver／Store／Memory engine／models
    ↓
finish_startup：只恢復或收束前景／人工操作
    ↓
Runtime 標記 ready
    ↓
BackgroundCoordinator.resume_pending()
    ↓
逐文件 wake；durable state 決定 wait／resume／start／no-op
    ↓
開始服務
```

必須把 `_recover_previous()` 內過早的背景 wake 移出 foreground recovery。`finish_startup()` 的前景恢復失敗仍是啟動失敗；Runtime ready 後某份文件的背景 wake 失敗則不得破壞人工 JD 或清除 durable state，也不新增隱藏 polling／無限重試。它可在下一次安全 wake 或下次啟動再次恢復。

### 5.2 一般顧問回合

```text
Runtime 開啟本回合固定 MemoryReadSession／JD 基準
    ↓
把 document-scoped provider 放入 invoke context
    ↓
A 依 guide → 內文 → 引用按需工作
    ↓
前景回合成功／失敗／取消均完成既有 settle
    ↓
settle 確實關閉後，coordinator.wake(document_id)
```

背景 wake 發生在安全終局之後。wake 失敗不能把已成功交付的使用者回合改成失敗；同時也不能假報背景已完成。既有 admission 與 checkpoint 保留下一次恢復依據。

### 5.3 關閉

關閉順序沿用既有 host owner：停止接受新工作，以 `ManualRuntime.close()` 的 bounded drain 契約排空前景／人工／背景執行池，再關 Saver／Store／DB。`ConsultantRuntime` 的共用 model clients 是 caller-owned 資源，只有 managed App／host close 明確回覆成功後才可關閉；若 close 回覆未確認或拋錯，CLI 保留 clients、回既有非零結果與固定診斷，不 force close、不把未排空誤報為完成，也不加入重試 loop。Coordinator 不擁有 thread pool、network client 或 DB connection，因此不建立第二套 shutdown protocol。

## 6. 正確性、並行與失敗界線

### 6.1 目前拓撲的保護

目前採單一 managed App process、host lease、單一 coordinator、每文件 dispatcher lock 與一個背景 worker。process-local single-flight 只防止同一程序重複提交；真正可恢復結果仍由：

- `jd_memory_admission`；
- LangGraph Saver checkpoint；
- publication CAS／receipt；
- canonical source／window authority；

共同判斷。

### 6.2 明確不宣稱的能力

現有 admission `admit` 是 read-then-save，不是跨 process 原子 claim。本稿**不宣稱多 process／多 worker 分散式正確性**。若未來允許兩個 App process 同時服務同一 DB，必須在那次拓撲變更前把 admission claim／lease 提升成 DB 原子條件寫入；不能只擴大 process-local map。

目前不因未發生的分散式需求新增 CAS table、外部 queue 或 lease scheduler。既有 Memory publication CAS 仍照原規則保護正式 Memory head。

### 6.3 失敗語意

- graph context 缺文件身分或 provider 回覆 scope 不一致：fail closed，不改用 global current document。
- availability 讀取失敗：按既有 middleware 契約回最小不可用狀態或隔離該提示；不得因此啟動背景或捏造已完成。
- wake／background job 失敗：保留 durable admission／checkpoint，前景結果不回滾。ordinary turn 的同步 wake 失敗與已提交 Future 的 terminal exception 各寫一筆 `caliburn.jd.background` 固定 event code，只帶必要 `document_id`，不帶 exception 文字、traceback、來源、prompt、員工內容、credential 或模型 payload；未啟動而取消的 Future 不算 workflow failure。
- shutdown 中拒絕新 background admission；已接受工作由既有 drain 規則收束。
- no-key 模式不消費 pending 工作，也不清空它。

## 7. G7 驗收與實際證據

本 G7 切片已固定以下效果：

1. A graph 只建立一次，且可在 App 文件 DB readers 尚未存在時建立；兩份文件交錯 invoke 不會混用 notice 或背景資源。
2. availability provider 每個 employee input 最多讀一次，只產生 system notice，不 wake、不寫 DB、不送模型請求。
3. 無 key／人工模式不建立 B1／B2 models、coordinator 或 provider，人工 JD 可正常使用。
4. 前景 settle 後只 wake 正確 `document_id`；wake 失敗不改寫已完成的前景結果，並留下 allowlisted operator event。
5. 啟動恢復不會在 Runtime ready 前 wake；ready 後可從既有 catalog＋durable state 恢復 pending 文件。
6. 新 process 不依賴舊 coordinator map；從 checkpoint／admission／publication 恢復時不重複發布或重做已成功語意工作。
7. 同 process 同文件並行 wake 只提交一個 job；不同文件可被接受，但仍由既有單一背景 worker 依序執行。
8. shutdown 先排空背景，再關 DB／Saver／Store；只有 App／host 確認 close 後才關 caller-owned model clients，未確認時保留 clients 與診斷現場。
9. assembly 與離線回歸固定使用合成模型；不讀 key、不送 provider request、不付費。
10. 既有 Memory bundle、引用、compaction、Prompt、JD 及 publication 規則不變。

已通過且不受修改影響的 package、dispatcher、角色模型與 compaction 證據直接沿用；不重跑沒有依賴關係的完整研究或相同 provider smoke。

2026-09-17 Task 4 使用 `--offline --frozen --no-sync`、workspace uv cache、停用 pytest cache 且未提供正式 credential，取得以下 fresh 證據：

- Task 3 re-review 已關閉唯一曾阻擋 closure 的 T3-R1：synthetic `ui_chat_server.serve()` fresh-marker 路徑使用同組 caller-owned `MockTransport` sync／async clients 建立 A／B1／B2，並把互異的 `case／understanding` model objects 傳入 `open_managed_app()`；composition 前固定 `model_request_count == 0`、`provider_network is False`。
- 上述 focused 測試刻意停在 `open_managed_app` composition seam，未啟動 DB、lifespan、listener 或瀏覽器；因此它只證明 UI helper 不再因漏傳 B1／B2 models 而固定組裝失敗，不代表真 PostgreSQL、provider、完整瀏覽器 App 旅程或 production authority 已通過。
- 指定受影響集合：**125 passed／2 skipped／1 warning／0 failed**；兩個 skip 是需要明示隔離 PostgreSQL opt-in 的既有案例，未把它們寫成通過。唯一 warning 是既有 Starlette `anyio.abc.BlockingPortal` alias deprecation。
- 第一次完整 App suite：**2,976 passed／320 skipped／5 warnings／37 setup errors**。首個 error 是 `test_missing_read_does_not_initialize` 在建立 `tmp_path` 前掃描既有 `C:\Users\chenb\AppData\Local\Temp\pytest-of-chenb` 時遇到 `WinError 5`；37 個 errors 都是同一 pytest 暫存 ACL，沒有進入產品測試本體。以同一首例在全新、可寫的隔離 basetemp 重跑為 **1 passed**，確認是環境條件而非本計畫回歸。
- 使用另一個全新隔離 basetemp 完整重跑：**3,013 passed／320 skipped／5 warnings／0 failed**。五項 warnings 是一項上述 Starlette deprecation 與四項既有 Pydantic `ConsultantContext` serializer warnings；skipped 保持 skipped，不代稱真 PostgreSQL、provider 或瀏覽器情境已通過。
- `python -m compileall -q src tests`：exit 0。三次驗證前後 `uv.lock` SHA-256 都是 `4D420BC0B9A39A9DB6D9A36B11BA6DF8CEC995D6B9B7EC902EA0E3DE9E24EDBB`，未修改 lock。

以上固定：共用 graph 無建構期 reader 綁定；兩文件的 per-invocation provider 隔離且每個 employee input 只讀一次；coordinator map 僅是 process-local keyed single-flight、可由 catalog＋durable admission／checkpoint／publication 重建；startup ready 後才恢復；一般 turn settle 後 wake 與 shutdown drain 保留；manual／no-key 不建立 coordinator。整個切片為零 provider request、零正式 key read、零付費、零 schema／migration；沒有宣稱未執行的 PG、自然模型、完整瀏覽器或 production authority 通過。

同日 Task 5 final lifecycle closure 先在原實作上取得 **4 failed／1 passed** 的精確 RED：兩種 App drain 未確認路徑都仍關閉 clients，ordinary wake 與 Future terminal exception 都缺 event，而 cancelled Future 保持不誤報。最小修正後，operator／managed shutdown、host bounded drain、wake、dispatcher、coordinator、AI restart 與相鄰 lifecycle focused set為 **105 passed／1 warning／0 failed**；Task 4 指定受影響集合為 **128 passed／2 skipped／1 warning／0 failed**；`python -m compileall -q src tests` exit 0。兩個 skip 與一個 Starlette deprecation 沿用原限制；全程 `--offline --frozen --no-sync`，未讀 key、未呼叫 provider、未新增 retry／polling／queue／authority，`uv.lock` 不變。

Task 5 commit `9dbef03d` 與最終獨立複核完成後，於同一最終 HEAD 使用全新隔離 basetemp 再跑完整 App suite：**3,016 passed／320 skipped／5 warnings／0 failed**，`python -m compileall -q src tests` 再次 exit 0。320 個 opt-in／環境情境與五項既有 warnings 的限制不變；這次最終驗證仍為 offline／frozen／no-sync，沒有 credential 或 provider request，`uv.lock` 未變。

## 8. 不採用方案

| 方案 | 不採用理由 |
|---|---|
| graph 建構時綁 DB readers | 資源生命週期不成立，也使 graph 難以共用與測試。 |
| 共用 mutable proxy／global current document | 並行 invoke 會有跨文件污染，違反 per-run scope。 |
| 每文件建立一個 A graph | 沒有 per-document prompt／schema 差異，只為注入 dependency 重建 graph 屬重複與過度設計。 |
| middleware 直接 wake 背景 | 混合 model context 與 side effect；工具迴圈可能重複提交。 |
| 新建 registry／queue／scheduler／polling loop | 與既有 catalog、admission、Saver、dispatcher 及 host pool 重複。 |
| 現在新增 distributed admission CAS | 未改變單機單 process 拓撲，先加入會擴大 schema 與恢復面；保留為拓撲變更前的必要 gate。 |

## 9. 文件與決策關係

本稿實作既有 ADR0060 的 App／Runtime ownership，並承接已核准的 MEM-L001 workflow、dispatcher、CTX-C001 compaction 與角色模型工廠；沒有改變 framework、provider、資料權威或 production authority，因此不新增競爭 ADR。若施工中發現必須改變上述產品效果、provider／credential、Memory／Prompt／compaction、DB schema 或多 process 拓撲，才停止 G7 並提出新的具體裁決。

## 10. 官方來源

- [OpenAI Agents SDK：Context management](https://openai.github.io/openai-agents-python/context/)，查閱 2026-09-17；local context 作 dependency injection，與 LLM-visible context 分離。
- [OpenAI Agents SDK：Agents](https://openai.github.io/openai-agents-python/agents/)，查閱 2026-09-17；context、dynamic instructions 與 lifecycle 公開邊界。
- [LangChain：Runtime](https://docs.langchain.com/oss/python/langchain/runtime)，查閱 2026-09-17；per-run context／dependency injection，避免 hard-coded context 或 global state。
- [LangChain：Agent Server](https://docs.langchain.com/langsmith/agent-server)，查閱 2026-09-17；compiled graph、per-run customization、durable task 與 ephemeral queue 的區分。
- [LangGraph v1](https://docs.langchain.com/oss/python/releases/langgraph-v1) 與 [Functional API](https://docs.langchain.com/oss/javascript/langgraph/functional-api)，查閱 2026-09-17；durable execution、checkpoint 與可重放 side effect 邊界。
- [Anthropic：Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)，查閱 2026-09-17；高訊號 context、按需回查、compaction 與 structured notes 的分工。
- [Anthropic：Managed agents](https://www.anthropic.com/engineering/managed-agents)，查閱 2026-09-17；外部 durable session、replaceable harness 與明示 wake／resume。
- [AWS：Idempotency in durable executions](https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/) 與 [DynamoDB conditional writes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html)，查閱 2026-09-17；重試 side effect 與條件寫入邊界。

## 11. 下一 gate 與未完成邊界

本 managed callback 的窄 G7 已完成。這裡記錄的「下一 gate 是 layered C」是當時施工順序；layered C 已由後續切片完成。2026-09-20 之後的目前路由依 [`current-decisions.md`](../current-decisions.md) 與[跨顧問、Memory 與 JD 的模型安全證據契約](2026-09-20-cross-agent-evidence-and-jd-context-contract.md)，不由本歷史切片另設競爭中的下一題。

其後仍須分開完成自然模型／付費驗證、完整瀏覽器 App 旅程與 production authority 正式化。現行產品仍是單 process、host lease、單一背景 worker；若未來要改為多 App process／多 worker 共用同一 DB，必須在拓撲變更前新增並驗證 DB 原子 admission claim，不能以目前的 process-local coordinator map 冒充跨 process 保證。
