# Caliburn 文檔索引

本目錄是 repo 的文檔權威。現行產品是本機 Web Job Analysis；current-only 硬切後，只有現行 code、ADR 0057、current design 與 runbook 可指導 current 產品的新施工。repo 另外保留一組與 current 完全隔離的 RAG bounded context（`pdf-to-json`／`ocs-indexer`／`embedder`／`ocs-contract`／`indexer-contract`），設計見 [`design/rag-pipeline.md`](design/rag-pipeline.md)；它們有自己可獨立驗證的 runtime 與 schema，只是不屬於 current API/Web。已刪除的舊訪談／`job_authoring` 內容則保留在歷史研究與 ADR 中供追溯，不代表仍有 runtime 或 schema。

## 先讀

- [`../AGENTS.md`](../AGENTS.md) — agent 工作紀律與 current-only 邊界。
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — 現行 monorepo 與 API／Web 邊界。
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — 安裝、開發、測試與提交。
- [`runbook.md`](runbook.md) — PostgreSQL、API、Web 起停與 fresh DB。
- [`product-notes.md`](product-notes.md) — 產品範圍與 UX 優先級。

## 現行設計與決策

- [`design/task-analysis-engine.md`](design/task-analysis-engine.md) — Job Analysis packet → OpenRouter → verifier → transition → PostgreSQL／Proposal → Web 的端到端真相。
- [`specs/2026-08-10-current-only-hard-cut-design.md`](specs/2026-08-10-current-only-hard-cut-design.md) — 本次淘汰範圍、fresh DB 與驗證證據。
- [`plans/2026-08-10-current-only-hard-cut-plan.md`](plans/2026-08-10-current-only-hard-cut-plan.md) — 執行切片與 hard gates。
- [`specs/2026-08-10-job-analysis-module-boundaries-research.md`](specs/2026-08-10-job-analysis-module-boundaries-research.md) — current system 完成隔離後的功能模組、shared kernel、port ownership 與 Web 邊界研究。
- [`adr/0058-current-api-functional-modules-and-dependency-rules.md`](adr/0058-current-api-functional-modules-and-dependency-rules.md) — **Accepted** current API／Web 模組與可執行依賴規範；後續 move-only 重構的權威邊界。
- [`plans/2026-08-10-current-application-modularization-plan.md`](plans/2026-08-10-current-application-modularization-plan.md) — 可交付實作者逐 task 搬移、驗證與 commit 的 current application 模組化計畫。
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

`docs/adr/0001`–`0056`、舊 OCS schema、舊 interview／vNext research、舊 monorepo plans 與 archive 都是決策歷史。閱讀它們是為了理解取捨或避免誤判，不是恢復實作的授權。若要改變 current-only 邊界，必須另開研究與 ADR，不能直接從歷史文件抽 code。
