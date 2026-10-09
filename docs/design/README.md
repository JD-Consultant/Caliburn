# 獨立 RAG 設計入口

本目錄維護獨立 RAG 的設計說明。現行 JD App 的整體責任直接讀[架構導覽](../architecture/README.md)，正式切換依 [正式產品與選型](../architecture/design-decisions.md)。

## 獨立 RAG

- [RAG pipeline](rag-pipeline.md)：PDF／OCS／indexer／embedder／Qdrant 的資料流、資源與操作邊界。App 可依 [公版接線](rag-pipeline.md)明示啟用 HTTP consumer，RAG 不成為預設啟動依賴。
- App 介面與保存接線見[實作與契約接線](../implementation/README.md)。
