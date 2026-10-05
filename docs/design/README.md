# 跨 App 設計與歷史索引

本目錄保留跨 App 的設計說明，並分開列出現行範圍與歷史設計。現行架構從[架構地圖](../target-architecture-map.md)進入；正式產品權責依 [ADR0079（Accepted）](../adr/0079-target-rebuild-production-cutover.md)，[ADR0077](../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)只作舊產品沿革。

## 現行設計

- [`rag-pipeline.md`](rag-pipeline.md) — 獨立的 PDF／OCS／indexer／embedder／Qdrant bounded context，說明資料流、資源與操作邊界。依 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)，JD App 可明示啟用 HTTP consumer；RAG 不成為預設啟動依賴。

## 歷史設計

- [`consultant-runtime.md`](../history.md#source-ac37cc49c94c6b310f5e) — 原 ADR0060 設計已退役，保留研究與報告脈絡，不作新施工規格。
- interview engine、editor knowledge pack 的簡短退役通知已移出 checkout；見[Git 恢復對照](../history.md#source-342210e06cceeff43952)。

不要從歷史設計恢復舊 route、hook、store、contract、writer、indexer 或 provider。實際變更維護對應有效責任文件與 App README，不更新退役設計來冒充新權責。
