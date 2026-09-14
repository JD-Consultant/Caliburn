# B1 App 接線 9fdef9eb：審查結果

2026-09-14；審查對象 `9fdef9eb`／`jd-b1-app-wiring-20260914`。本審查對照 `docs/current-decisions.md`、9/13 B1 採用審查、完成窗口 source contract，以及 `app-wiring-results.md`；另以目前固定測試與 OpenAI 現行官方 API 文件核對。結論是：**OpenAI 適配器與 B1 核心接合方向可保留，但本片尚不能標成 B1 已完成接入新 App。**

## 必須修正

### F1：CONTEXT_ONLY 丟失已知回合終局資訊

`ExtractionSourceAdapter.read()` 在讀取 context 後固定覆寫成 `turns=[]`（`extraction_app.py`）。來源 owner 的 `read_context()` 只回 `segments` 與 `omitted_content_types`。這與 9/13 B1 接合審查的界線不符：context 不可作 B1 的新來源或 admission 邊界，但其中若包含已完成或安全結束的 Human 回合，仍須保留同一固定位置能證明的 `turns`；只有前置 AI 問句而沒有 Human 回合時才可以是空集合。

B1 指引明確把 `turns` 當成系統回合終局資料，`answer_succeeded=false` 時不得補寫失敗的顧問回答。現在把它清空，會讓模型看見 assistant 文字卻不知道該回合是否成功，可能把失敗／取消回覆誤當成可用上下文。舊版已驗 source reader 也會從固定 snapshot 投影範圍內的 turns。

**修正界線：**由同一 source owner 在固定 root 上計算並回傳範圍內可證明的 turns；adapter 原樣轉交，仍回 `next_offset=None`。不要在 adapter 另造走鏈或把 context 變成可整併窗口。補至少一個 context 含 completed 與 cancelled／failed turn 的案例，另保留只含前置 AI 問句時為空的案例。

## 必須重新核對，但不是 B1 核心重寫

### F2：依賴沿用舊 pin，未完成「現行版本」核對

本片加入 `langchain-openai==1.6.0`，理由是舊 CT checkout 使用同一 pin；但現行官方 PyPI 頁面已列 `langchain-openai 1.6.2`。9/13 審查已要求「先核當前 OpenAI／LangChain 相容版本與實際 request，再鎖依賴」，不能把舊 pin 當成現行最佳選擇。

**處理：**以目前 lock 的其他版本為基準，先對 1.6.2 做相同的 MockTransport request／structured output／拒絕／截斷探針；相容就更新 lock，不相容才保留 1.6.0 並記錄具體失敗原因。`openai==3.13.0` 與 CT 的 3.8.0 差異仍須保持「線上版本已核、自然品質未延伸」的界線。

### F3：結果名稱與目前完成範圍不一致

報告開頭稱「B1 已接進新 App」，但同一份結果稿 §5 明載 `build_extraction_workflow` 尚未由 App runtime 觸發，宿主啟停、背景准入、排空、新程序續作、模型設定與金鑰尚未接。現況是「B1 核心的 App 端 adapter／provider wiring probe 完成」，不是日常 App 可用的 B1。

**處理：**更新入口與結果用語，明確分成「核心已採用」「adapter 固定接合已驗」「runtime／背景觸發未開始」。在 runtime 接線、設定與真保存驗收前，不把 H4 或完整旅程標為完成。

### F4：測試證據不能外推成正式 App／資料庫完成

13 個新增案例使用 MockTransport、InMemorySaver、InMemoryStore；報告中的 PostgreSQL 14 案例是原話來源、C 接合與 Memory 核心，並非 B1 的 PostgreSQL 執行。這足以證明 adapter 的固定行為，不足以證明 B1 已接入正式宿主、背景排空、PostgreSQL 保存或重開。

下一個 runtime 工作單位須補真 PG 的 B1 保存／續作／冪等與設定接線；在此之前維持零 provider、未啟用日常 AI 的狀態，不把既有 14 案例重複計入 B1。

## 版本與 API 注意事項

`build_extraction_model()` 顯式傳 `truncation="disabled"`。OpenAI 現行 Responses API 參考把 `truncation` 標為 deprecated，並說 `disabled` 本來就是預設值；這不是目前的阻擋性錯誤，但不應在新接線中繼續加入已標示淘汰的參數。下一次依賴／request preflight 應移除它，並以 source budget、實際 400 行為及 `status`／`incomplete_details` 測試保留「不默默縮短」的效果；若現行 SDK 有必要保留，必須記錄原因與替代路徑。

官方依據：[OpenAI Responses API create reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)（`truncation` 為 deprecated、`disabled` 為預設，`status`／`incomplete_details` 為回覆證據）、[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)（refusal／incomplete／schema 三項分開檢查）、[langchain-openai PyPI](https://pypi.org/project/langchain-openai/)（目前 1.6.2）。

## 審查結論

不退回 B1 核心、不新增第二套流程；先修 F1，並完成 F2 版本／request preflight，重寫 F3 的完成宣稱。F4 是下一個 runtime 工作的證據缺口。修正後再做窄複核，才進入 B1 runtime 觸發與 B2；目前不做自然模型呼叫或費用測試。
