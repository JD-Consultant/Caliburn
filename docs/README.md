# Caliburn 文檔索引

本目錄是 repo 的文檔權威。現行產品是本機 Web Job Analysis；current-only 硬切後，只有現行 code、ADR 0057、current design 與 runbook 可指導 current 產品的新施工。repo 另外保留一組與 current 完全隔離的 RAG bounded context（`pdf-to-json`／`ocs-indexer`／`embedder`／`ocs-contract`／`indexer-contract`），設計見 [`design/rag-pipeline.md`](design/rag-pipeline.md)；它們有自己可獨立驗證的 runtime 與 schema，只是不屬於 current API/Web。已刪除的舊訪談／`job_authoring` 內容則保留在歷史研究與 ADR 中供追溯，不代表仍有 runtime 或 schema。

## 先讀

- [`../AGENTS.md`](../AGENTS.md) — agent 工作紀律與 current-only 邊界。
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — 現行 monorepo 與 API／Web 邊界。
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — 安裝、開發、測試與提交。
- [`runbook.md`](runbook.md) — PostgreSQL、API、Web 起停與 fresh DB。
- [`product-notes.md`](product-notes.md) — 產品範圍與 UX 優先級。

## 現行設計與決策

- [`design/consultant-runtime.md`](design/consultant-runtime.md) — LangChain／LangGraph durable consultant、context、Skills、文件審核／authority、API、Web 與 export 的端到端真相。
- [`adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`](adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) — **Accepted** framework replacement、單一 durable authority、Big-bang 與延後 RAG 的決策。
- [`adr/0064-deep-agents-virtual-jd-workspace-and-deterministic-evidence-anchor.md`](adr/0064-deep-agents-virtual-jd-workspace-and-deterministic-evidence-anchor.md) — **Proposed** Deep Agents 受限虛擬 JD editor、薄 domain check、typed publication gate 與 application-derived Evidence anchor。
- [`specs/2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md`](specs/2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md) — Codex／Claude／Deep Agents 官方做法、現行 mega-form／quote-offset 診斷、方案與施工邊界。
- [`plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md`](plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md) — 逐 task 驗證與 hard-cut 計畫。
- [`specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`](specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md) — 每個功能切片回看產品大方向與 framework 覆蓋的證據。
- [`contract-strategy.md`](contract-strategy.md) — 現行 `job-analysis-contract` 的契約規範。
- [`adr/README.md`](adr/README.md) — ADR 索引；0057 記錄 current-only hard cut。
- [`design/rag-pipeline.md`](design/rag-pipeline.md) — PDF → OCS contract → indexer → embedder/Qdrant 的 RAG 供應鏈；保留但與 current API/Web 完全隔離的獨立 bounded context，非 current 產品 runtime。

## 文檔分層

| 問題 | 位置 |
|---|---|
| 現行跨 app 流程、請求與不變量 | `docs/design/` |
| 單一 app 的 codemap／內部規則 | `apps/*/README.md`、`AGENTS.md` |
| 為什麼採這個決策 | `docs/adr/` |
| 研究、診斷、來源與選項 | `docs/specs/` |
| 可重現操作與故障排除 | `docs/runbook.md`、`CONTRIBUTING.md` |
| 實驗與 live evidence | `docs/experiments/` |
| 已淘汰的歷史材料 | `docs/archive/`、被標成 superseded／retired 的 ADR、spec、plan |

跨 app 文檔要把 UI 動作對到真實 endpoint 或純函式，寫出欄位真名、不變量與「已退役、不要呼叫」的路徑。動到該 seam 的 code，就在同一 commit 更新文檔。

## 歷史材料使用規則

被 ADR 0060 取代的 0058–0059 模組切割、`docs/design/task-analysis-engine.md` 的 Git 歷史、`docs/adr/0001`–`0056`、舊 interview／vNext research、舊 plans 與 archive 都是決策歷史。閱讀它們是為了理解取捨，不是恢復實作的授權。若要改變 current／RAG 邊界或 authority，必須另開研究與 successor ADR。
