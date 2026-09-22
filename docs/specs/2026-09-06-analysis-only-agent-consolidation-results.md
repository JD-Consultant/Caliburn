# Q019 第六切片：B2 按需整併與發布結果

> 2026-09-06 · 隔離實作；修復後全套 **96 passed／0 skipped**。獨立 review 的 R01／P01 限定複核 Closed，無新增 blocking findings，詳見 §3；本地保存點由[決策入口](S:/caliburn/docs/current-decisions.md)記錄。
> [本段計畫](../plans/2026-09-06-analysis-only-agent-consolidation-slice.md) · [有效 Memory 設計 §2.3／§6](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md)

## 1. 本段完成的效果

完成 B1 詳記／候選 → B2 按需補讀 → 暫存正文與導覽 → 完整檢查 → 不可變保存 → 原子發布。

- B2 只接已完成 B1 checkpoint 的真實地址與 source reference，不接模型自編 manifest。
- 候選有界給全文；詳記提供地址，模型需要才搜尋／讀取。既有正文在暫存區，不強制每次放入 prompt；導覽給模型作路由。
- 正文按主題整理、保留條件／未知／案例差異／關鍵詞與詳記引用；導覽不另生第六份資料。這是 instructions，測試**未證明自然模型一定正確去重與保留所有細節**。
- 模型只能改兩個暫存檔案；不能寫詳記、其他文件或實際電腦檔案。沒有 JD、shell、網路查詢或任意 raw 調查工具。
- 可先呼叫無參數 validate_memory；格式／引用錯誤回工具結果，模型在剩餘額度內修正。最終重新檢查兩個檔案，才保存和發布。
- B2 收到的原文只有 stale 恢復時由 Runtime 取出的指定修補問答，包含角色；不解碼／轉存 A 的 opaque reasoning。

## 2. 實現與直接來源

| 責任 | 成熟元件 | 本案接線 |
|---|---|---|
| LLM／工具回圈 | LangChain create_agent、原生 ChatOpenAI Responses | B2 instructions、允許的工具集合；没有另一個手寫 model/tool loop |
| 暫存內容 | DeepAgents StateBackend、FilesystemState | 兩檔 editable staging；原 published version 不原地修改 |
| 按需搜尋讀取 | 官方 filesystem tools＋CompositeBackend／StoreBackend | 固定同文件 namespace、詳記唯讀、既有輸出限額 |
| 格式錯誤 | 公開 tool／ToolException | 無欄位 validate_memory；只查可讀性、大小與實際詳記地址 |
| 執行恢復 | LangGraph StateGraph＋per-invocation subgraph＋PostgresSaver | load→consolidate→save→prepare→publish；metadata 是 runtime 欄位 |
| 發布與競爭 | 第四切片 SQLAlchemy version_id_col／receipt | stale 保留 B1、讀新 head／修補問答後重新執行 B2 |
| 成本邊界 | 官方 ModelCallLimitMiddleware／ToolCallLimitMiddleware | 失敗安全停止、stale 扣除前次成功步數；不宣稱 HTTP 計費硬上限 |

本輪只補框架接線缺口，沒有重新研究 OpenAI 五產物。OpenAI 角色／引用分層沿用 [Q019 Memory §1／§3](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md) 與其原研究路由。下列是本輪核對的官方能力，**組合及路徑政策仍是本案 mapping，不冒称 OpenAI 内部用相同類別或 schema**：

1. [DeepAgents Backends](https://docs.langchain.com/oss/python/deepagents/backends)：StateBackend／StoreBackend／CompositeBackend 及 backend policy extension。另讀鎖定 0.7.13 的公開 StateBackend.read/write/edit/upload_files/download_files、FilesystemState；應用沒有 import framework private helper。
2. [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)：per-invocation 子圖可繼承 parent checkpointer，本次工具步驟可恢復，不等於跨 attempt 保留舊分析；實際 PG 重建測試驗證。
3. [LangChain 官方限額](https://docs.langchain.com/oss/python/langchain/middleware/built-in)：thread limit 與 run limit 有別；選 error，不把 framework 合成的停止訊息當成功結果。子圖恢復保留計數，stale 新 attempt 只取得剩餘額度。
4. [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)：正常工具與錯誤回傳；本段用 ToolException 回格式錯誤。未自行生成假 tool call 或加入逐字驗證 schema。
5. [LangChain AIMessage 官方 source](https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/messages/ai.py) 與 [ChatOpenAI 官方 source](https://github.com/langchain-ai/langchain/blob/master/libs/partners/openai/langchain_openai/chat_models/base.py)：成功解析的 tool_calls 與解析失敗的 invalid_tool_calls 分開。實際依 lock 的 core1.6.2／openai1.6.0 檢查並以真 adapter 測試，不因 master 更新而重解釋測試證據。
6. [SQLAlchemy versioning](https://docs.sqlalchemy.org/en/20/orm/versioning.html)：沿用已驗證的 publication seam，模型等待期間不持有 DB transaction。Store 與 Saver 不是假裝同一個跨元件交易。

## 3. 測試與審核

**付費 API 0；不讀產品 .env、不接 production、不改資料架構、不新增依賴。**
測試是真框架／adapter／Store／Saver／SQLAlchemy，只有 provider HTTP 合成；PG 錯誤由測試注入。

- 第一組9項確認缺 B2 module 的 RED，接線後9 passed；逐步增加 stale、故障、限額、來源／文件邊界。
- 最新 B2 in-memory **22 passed**，真 PG 新增 **3 passed**。
- 修復前完整93 passed；R01回歸及延伸反例後完整 **96 passed in14.07s／0 skipped**；提交前再跑 **96 passed in12.59s／0 skipped**，包含前五段測試。
- compileall、uv lock --check --offline（73 packages）、git diff --check 通過；無套件變更。
- 真 PG：在暫存寫入完成後令詳記工具失敗、模型完成後令 Store 保存失敗、提交成功後丟失回覆。關閉／重建 HTTP client、graph、Saver、Store、metadata connection，再恢復。前者重用已保存工具進度；後兩者不再呼叫模型；提交回執與 operation ID 不變。
- 僅清理 q019_agent_test／localhost55433 的本次隨機 document、B1/B2 technical threads、artifacts及receipt；沒有刪既有訪談或重建庫。

| ID／問題 | 重現、處理與狀態 |
|---|---|
| Q019-B2-R01／P1（獨立 review） | 壞 JSON function arguments 被 adapter 放入 invalid_tool_calls，正常 tool_calls 為空；原檢查誤當 no-op，發布空檔並前進 source cursor。已先重現 RED，再檢查**整個 attempt 的所有 AIMessage**：invalid calls、incomplete／failed、refusal 不可發布。補3個反例：單獨 invalid、valid＋invalid 混合後有正常 final、前段 incomplete tool 後有正常 final。修復後通過；獨立限定複核 Closed。 |
| Q019-B2-P01／局部 preflight 修正 | 超界候選原先先建立 durable job 才拒絕；擴充測試重現後改在 start 作 read-only admission，拒絕時不預占 job，調整有界配置可再啟動。durable load 仍重新讀 head，不能假定 preflight 後沒有競爭。獨立限定複核 Closed。 |
| 測試 fixture 邊界 | stale 測試初稿把 callback 立即呼叫，實際不是「整理途中修補」；已改正觸發位置並驗 actual attempt／HTTP。PG 初稿故障點放在 HTTP，會被 SDK 網路重試混淆；改在真正詳記 read tool 注入失敗，驗工具恢復。沒有修改 runtime 來迎合錯誤 fixture。 |

Reviewer 初審限定離線81 passed 並另行重現 R01；修復後獨立限定複核 **22 passed**，R01／P01 Closed，無新增 blocking findings。Reviewer 沒有重跑 PG；全套96 passed／0 skipped是主實作者執行，不把它算成獨立執行。

## 4. 明確限制與下一個 gate

1. **這不是整個產品完成。** 沒有 C 對話內修補工具、A 在同 run 刷新 Memory reader、背景排程、streaming／UI／JD；分析語意品質亦未用真模型驗證。
2. validate_memory 工具錯誤可在回圈內修；但模型直接以不合法檔案／壞 tool call／incomplete 回覆結束，最終檢查會停住，**resume 只重驗，不會自動改寫壞內容**。沒有自動取消／重排／重做失敗 attempt 的產品入口；不能把安全停止寫成全部錯誤自動恢復。
3. 8 model steps／12 tool calls 為每個 B2 job 的初始配置；已有完整 attempt 的耗用扣入 stale 重做。每步輸出4,096 tokens、新候選24,000字、修補原文12,000字可配置；**20 repair receipts 是目前固定安全上限，不是可調參數**。超界不截短冒充完整，沒有自動縮批。啟動前超界不建立 job；執行中修補文字超界會保留 pending 及較新 head，可明確調整文字上限後恢復；超過20 receipts則仍安全停止，本段不提供繞過或重排入口。
4. Model step 預算不等於 HTTP requests 或計費上限。SDK 可有網路重試；模型結果丟失在 checkpoint 前也可能重呼。這段未自訂另一層 API retry。
5. 類似案例是否真的整理得好、用哪個模型成本較好、正文是否保留所有工作細節，需要之後小額自然訪談驗證；本段不能用合成答案自證。
6. 本輪没有產品方向翻案。下一段依 Q019 §5–6 接 **C 局部修補與 A 受控刷新**；整體 retry/cancel/replan 與背景 admission 於應用接線階段處理，不能帶著此限制直接宣称可上線。
