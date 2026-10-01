# 跨 App 設計與歷史索引

本目錄同時有獨立保留範圍與已退役設計，不因仍有文件就稱為 active。現行架構從[架構地圖](../target-architecture-map.md)進入；正式產品權責依 [ADR0079（Accepted）](../adr/0079-target-rebuild-production-cutover.md)，[ADR0077](../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)只作舊產品沿革。

## 現行設計

- [`rag-pipeline.md`](rag-pipeline.md) — 保留但與 current API/Web 完全隔離的 PDF／OCS／indexer／embedder／Qdrant bounded context。

## 歷史設計

- [`consultant-runtime.md`](consultant-runtime.md) — 原 ADR0060 設計已退役，保留研究與報告脈絡，不作新施工規格。
- interview engine、editor knowledge pack 的簡短退役通知已移出 checkout；見[Git 恢復對照](../archive/docs-cleanup-2026-10-02.md)。

不要從歷史設計恢復舊 route、hook、store、contract、writer、indexer 或 provider。實際變更維護對應有效責任文件與 App README，不更新退役設計來冒充新權責。
