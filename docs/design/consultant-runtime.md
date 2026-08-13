# AI 職務顧問 runtime 設計

- 決策：[ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)
- 狀態：Big-bang migration 建構中；目前只完成框架底座與 durable authority foundation，production composition root 尚未切換
- 實作：`apps/api/app/consultant`、`apps/api/app/adapters/langgraph`

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

## 當前邊界

這個 foundation 沒有模型呼叫、RAG／Reference、Skill、prompt、能力級別／A 生成、Web route 或舊 writer bridge。舊 production composition 會維持到垂直切片完成，最終硬切才刪除，不雙寫。
