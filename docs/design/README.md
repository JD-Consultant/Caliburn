# docs/design — 現行跨 app 設計

這裡只放能指導現行 code 的跨 app／seam 說明。每個 UI 動作要對到真實 request 或純函式，欄位用真名，不變量與退役禁令要明寫。

## 現行設計

- [`consultant-runtime.md`](consultant-runtime.md) — ADR 0060 的 LangChain／LangGraph durable consultant、context、Skills、文件審核／authority、API、Web 與 export；唯一 active current-product design。
- [`rag-pipeline.md`](rag-pipeline.md) — 保留但與 current API/Web 完全隔離的 PDF／OCS／indexer／embedder／Qdrant bounded context。

## 歷史設計

- [`interview-engine.md`](interview-engine.md) — 已刪訪談 engine，只供決策追溯。
- [`editor-knowledge-pack.md`](editor-knowledge-pack.md) — 已刪 OCS editor／knowledge seam，只供決策追溯。

不要從歷史設計恢復舊 route、hook、store、contract、writer、indexer 或 provider。現行 consultant seam 改變時，同 commit 更新 `consultant-runtime.md` 與對應 app README。
