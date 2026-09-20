# A／B2 框架步數驗收與最小修正

- 日期：2026-09-20；Topic：JD-R002／A-R001／MEM-L001。
- 狀態：步數修正、指定離線回歸與隔離真 PG／HTTP 收尾回歸通過；尚不代表自然模型、完整 App 或 production authority 完成。
- 範圍：新 App `experiments/jd-relational-app`、新分層 `UnderstandingMaintenanceWorkflow`。不改舊兩檔 Memory，不改 Prompt、來源、版本、provider、模型／工具額度或 production authority。

## 依據與診斷

已對齊 A 執行額度規格及施工計畫、B2 Agent 計畫、分層背景 workflow 設計、角色 profile 與 package README。OpenAI／Anthropic 的有界 Agent／工具原則沿用 A 規格既有研究；此次新增缺口屬 LangGraph 排程，而非 Memory 或模型設計。

[LangGraph 官方 Graph API](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/graph-api.mdx)說明 `recursion_limit` 計算 supersteps，不是模型呼叫；[官方錯誤參考](https://reference.langchain.com/python/langgraph/errors/GraphRecursionError)提供透過公開 config 調整的方式。查閱 2026-09-20，並核對本機鎖定 LangChain 1.4.0／LangGraph 1.2.11。倍率與保留步數是本案組裝推導，不是大廠規定值或通用公式；不 fork 框架、不新增計數權威。

- A：兩個 before-model hooks＋model＋三個 after-model hooks＋tools，再加 document graph 的 parent routing step，每個完整工具 wave 八步。另保留 16 步供入口／收尾，`max(100, 64*8+16)=528`。實際 `build_consultant()` 節點集合另有測試核對。原生 checkpoint 中的 model／tool thread counters 仍負責 64／63 上限。
- B2：一個 before-model hook＋model＋三個 after-model hooks＋tools，每 wave 六步；`max(100, max_model_steps*6+16)`，正式 128 時為 784。保留原 start／resume／attempt 與完成修正流程，不新增 Agent。
- B1 正式配置與程式未修改。本輪不將先前以變更工具額度探測模型上限的結果冒稱正式 256／240 profile 已完整驗收。

## 測試與限制

首敗：A 生命周期測試補上 App 真正使用的 config 後，出現 `GraphRecursionError: 198`；B2 使用正式 128／120 與合法案例讀取、revalidate、finish，出現 `GraphRecursionError: 390`。舊 A 測試沒有傳該 config，不能證明正式步數足夠。

修正後：

- `test_consultant_context.py`＋`test_understanding_workflow.py`：42 passed，含 A 63 tools→第64次回答→下輪新額度，以及 B2 120 個成功工具→第121次正常完成。
- App 組裝、execution、background compaction、role models 相鄰測試：30 passed。
- B2 第121個工具仍由 `ToolCallLimitExceededError` 拒絕：修正測試需讀原生 child checkpoint 而非尚未完成的 parent 後，精確重跑 1 passed；120個工具結果已保存。
- 真 PostgreSQL／HTTP `test_http_failed_final_model_keeps_saved_input_and_confirmed_committed_jd`：1 failed，已確認 JD revision／receipt 保存不變，但捕捉請求數63，不是64。此長迴圈測試的觀察期限由15秒改為120秒，僅測試等待，不改產品 timeout。

上述首敗已由後續最小修正閉合：最後 request 清除工具專用 `strict`，明確傳 `tools=[]`／`tool_choice=none`。同一隔離 PostgreSQL／HTTP 測試後續結果為 **1 passed／1 warning**；warning 是既有 Starlette 相容性棄用提示，不影響本契約。

## 新發現與修正：最後無工具請求的 wire 契約

鎖定框架 `factory._get_bound_model()` 在 `final_tools` 為空時改用 `model.bind(**request.model_settings)`，不傳 `request.tool_choice`。A middleware 雖在 ModelRequest 設定 `tools=[]／tool_choice='none'`，但設定物件的成功不等於 wire 成功。另因前一個有工具 request 的 App context 會帶 `strict=True`，收尾若不移除它，OpenRouter SDK 會在送出前回 `Chat.send() got an unexpected keyword argument 'strict'`。

另以真 create_agent＋既有 OpenRouter SDK＋MockTransport、預置已使用63次的 thread counter 做零外送探針：原接法的 `tools`／`tool_choice` 沒有完整落到 wire；PG fixture 隨後進一步證明 `strict=True` 也會在第64次前阻止送出，故原 failed 狀態不能算作「刻意注入的最後 transport failure 已驗證」。

最小修正：在最後一次 request 的公開 `model_settings` 移除只適用於工具的 `strict`，並明確傳遞 `tools=[]` 與 `tool_choice='none'`，保留其他設定；不 fork 框架、不放寬驗收、不更動收尾語意。修正後仍須驗真 adapter wire／PG 最後失敗和成功路徑。

本輪零 provider、零正式 key、零付費、零 migration；隔離 PG 容器已停止，volume／合成證據保留。不表示完整 App、自然模型或瀏覽器旅程通過。
