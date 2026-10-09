# 獨立 RAG 設計與歷史入口

本目錄保留獨立 RAG 的設計說明及舊設計路由。現行 JD App 的整體責任直接讀[架構導覽](../architecture/README.md)，正式切換依 [ADR0079](../adr/0079-target-rebuild-production-cutover.md)。

## 獨立 RAG

- [RAG pipeline](rag-pipeline.md)：PDF／OCS／indexer／embedder／Qdrant 的資料流、資源與操作邊界。App 可依 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)明示啟用 HTTP consumer，RAG 不成為預設啟動依賴。
- 詳細介面、研究候選與證據路由見[規格索引](../specs/README.md#獨立-rag-範圍)。

## 歷史設計

- 原 consultant runtime：ADR0060 時期設計已退役，供研究與報告追溯。
- interview engine、editor knowledge pack 的退役通知已移出 checkout，見Git 恢復對照。
- [ADR0077](../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)只作舊產品沿革。

歷史內容不作新施工規格，不據此恢復舊 route、hook、store、contract、writer、indexer 或 provider。變更維護對應有效責任文件及 App README。
