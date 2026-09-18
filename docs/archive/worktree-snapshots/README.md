# 歷史 worktree 文件快照

這些目錄是從已封存的 worktree commit 複製出的 **docs-only 快照**，讓只透過 GitHub 網頁閱讀專案的人，也能直接看到完整的研究、設計、計畫、ADR、實驗案例與結果。

快照只保存已提交的 `docs/`；不包含程式碼、`node_modules`、pytest cache、scratch 或測試資料庫。內容保留當時的原貌，不代表目前施工權威。

| 快照目錄 | 對應封存 tag | 主要內容 |
|---|---|---|
| [`20260918-analysis-only-agent/`](20260918-analysis-only-agent/docs/) | `archive/worktree-analysis-only-agent-20260918` | 顧問、Memory、背景整理、compaction 與 App 接線研究／結果 |
| [`20260918-consultant-workspace-ui/`](20260918-consultant-workspace-ui/docs/) | `archive/worktree-consultant-workspace-ui-20260918` | 舊 consultant workspace UI 與 JD 編輯演進 |
| [`20260918-langgraph-authority-spike/`](20260918-langgraph-authority-spike/docs/) | `archive/worktree-langgraph-authority-spike-20260918` | LangGraph、runtime authority 與舊架構研究 |
| [`20260918-memory-routing-spike/`](20260918-memory-routing-spike/docs/) | `archive/worktree-memory-routing-spike-20260918` | Memory routing、長對話回查與 Luna 實驗資產 |
| [`20260918-shared-current-jd/`](20260918-shared-current-jd/docs/) | `archive/worktree-shared-current-jd-20260918` | Shared current JD、人工／AI 編輯與 review 演進 |

閱讀目前產品狀態仍先看 [`../../README.md`](../../README.md) 與 [`../../current-decisions.md`](../../current-decisions.md)；要追查「當時遇到什麼問題、如何修正、結果如何」，再依日期閱讀這些快照。
