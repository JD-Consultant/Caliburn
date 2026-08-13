# AI 職務顧問 runtime 設計

- 決策：[ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)
- 狀態：Big-bang migration 建構中；目前完成框架底座、durable authority、模型執行與最小充分 Context foundation，production composition root 尚未切換
- 實作：`apps/api/app/consultant`、`apps/api/app/adapters/langgraph`、`apps/api/app/adapters/openrouter/langchain.py`

## 儲存權威

每項持久事實只有一個 writer：

| 事實 | Owner |
|---|---|
| 文件 ID、library title、thread pointer、tombstone | Alembic 管理的 `consultant_documents` 最小 catalog |
| 員工逐字輸入、direct-edit 改寫文字、修正 lineage、position anchor | LangGraph `AsyncPostgresStore` 的文件 UUID namespace |
| 可演進顧問狀態、source references、review queue、核准文件與 run status | LangGraph `AsyncPostgresSaver` checkpoint |

checkpoint 不複製員工逐字來源；Store 不保存第二份核准文件。API／Web 日後只讀 checkpoint projection，不再建立 relational／JSONB semantic mirror。

## 一筆員工來源的 durable 順序

1. 驗證 application-issued document UUID、stable source ID 與 payload hash。
2. 先把 immutable source 以 `pending` 寫入文件專屬 Store namespace；修正與被取代來源用同一 Store batch 更新。
3. 以 LangGraph command 在一個 checkpoint 加入 source reference／lineage 與 semantic revision。provider 不在本 Task，也不會持有 DB transaction。
4. 將 Store source 標為 `committed`。若在兩個 crash window 任一處失敗，同一 source ID 重播只補缺少的步驟；其他新訪談輸入先被擋住。

只有 employee turn 與真的 authority direct edit 可鑄成 evidence source。模型文字、accept／reject／defer 與未啟用的 Reference 都不是來源種類。employee turn 的前後空白與換行按原樣保存並以原始 bytes 計 hash；quote range 也不做 trim。direct edit 只走明確允許的員工文字欄位，保存員工實際改寫的文字及其 JSON-pointer-like path，不把系統 UUID、enum、整份文件或未改文字複製成來源。核准 OPKS 引用的 evidence ID 必須能在同一文件 Store namespace 找到，或正是該次 direct edit 即將建立的來源。

## 安全與生命週期

- Saver 使用 `JsonPlusSerializer(allowed_msgpack_modules=None, pickle_fallback=False)`；等價於官方 strict msgpack allowlist。
- 官方 connection factory 提供 `autocommit=True`、`prepare_threshold=0`、`dict_row`；整合測試直接驗證。
- Windows 的 psycopg async connection 要求 Selector event loop；`run_live.py` 與獨立 storage setup entrypoint 都必須在建立 loop 前設定，不能只靠 pytest fixture。
- Saver／Store `.setup()` 可重跑；Caliburn catalog schema 只由 Alembic 管理。
- Catalog migration 使用 Alembic schema primitives 與具名 constraint／index，不以 `IF NOT EXISTS` 掩蓋 schema drift；每次成功寫入 semantic revision 後更新 catalog `updated_at`。
- 同一 process 以 document UUID admission lock 序列化 semantic writer；revision 再阻止 stale command。
- 刪除先 tombstone catalog，再清 checkpoint thread 與完整 Store namespace；重跑仍安全。
- Store namespace 不接受自由字串，只能由 application-issued UUID 組成。

## 模型執行

- Versioned model profile 只決定 requested model、唯一 provider、有效參數與 timeout；versioned run policy 只決定 eligible Skills／tools、context／call／token／time／cost budget 與 retry。兩者在每次 run 前解析成 immutable `ResolvedExecution`，Skill 不能選模型。
- `ChatOpenRouter` 承接 provider wire，`create_agent`／`response_format` 承接 bounded loop 與 structured output；model／tool call limit、retry、非權威摘要與唯讀工具結果清理由 LangChain built-in middleware 承接。OpenRouter SDK 自己的通用 retry 關閉；LangChain 1.3.15 `SummarizationMiddleware` 內建的獨立三次 retry 也由窄 subclass 關閉，所有主推論與摘要共用同一個 run attempt budget，避免框架內部出現無紀錄重試。
- 第一版固定單一 route 且禁止 fallback。adapter 保留 OpenRouter 回傳的實際 provider、model 與 cost；LangChain callback 對每個真實 attempt 各寫一張含 primary／summarization kind 的 payload-free receipt與 OpenTelemetry span。成功 attempt 若缺 route、usage，或在啟用 cost budget 時缺 cost，deterministic verifier 會在 semantic commit 前 fail closed。provider error 只保留安全分類／HTTP status，不把原始例外訊息或可能回顯的員工內容寫入 receipt／telemetry。
- `SummarizationMiddleware` 與 `ContextEditingMiddleware` 只處理非權威對話副本／舊唯讀 tool result；不能成為員工原話、核准文件或顧問理解的 owner。

## 最小充分 Context

每次實際模型推論都由 middleware 依目前 checkpoint snapshot 與 Store 重建 Context，不持久化第二份 Context packet：

1. bounded global orientation 讓模型知道整份文件有哪些 Duty／Task、目前工作、Gap 與待審數量；
2. 載入目前焦點的核准文件 slice、可修訂理解、具體 Gap、待審 handles 與必要澄清；
3. checkpoint message 只留帶 stable source ID 的 placeholder；本輪員工原話每次從 Store 逐字重載到明標「不可信 evidence」的 authority Context，明確 required evidence 必帶，相關近期來源在 token budget 內加入；
4. 只有本輪、required 與近期相關來源的 stable lookup handle 進 prompt；更早來源不列出全部 ID，模型可透過同文件 lexical search 再以 ID／correction lineage 按需讀取。現階段沒有設定 semantic index，也沒有連接 Reference／RAG bounded context；
5. Context selection receipt 只存 ID、hash、原因、revision、Skills、token 與降級資訊，不複製員工文字。

明確降級順序是：先捨棄非權威 dialogue summary，再壓縮 global orientation，再略過超出預算的近期候選來源。本輪原話、required evidence、必要澄清、blocking Gap 與焦點核准 slice 不會被摘要取代；這些 mandatory 內容本身超出 budget 時直接回 typed error。即使 LangChain 已把舊 message history 摘要化，middleware 仍會從 Store 重建 authority Context；tool loop 後續推論不會把員工回答重複追加到 ToolMessage 後面。

## 當前邊界

這個 foundation 已有可替換模型 profile、LangChain agent harness、attempt receipt 與 Context middleware，但尚未接 production route、真實顧問 Skill／結果 schema、訪談 routing、員工 review command 或 Web。它沒有 RAG／Reference、能力級別／A 生成、品質 eval 或舊 writer bridge。舊 production composition 會維持到垂直切片完成，最終硬切才刪除，不雙寫。
