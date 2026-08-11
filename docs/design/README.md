# docs/design — 現行跨 app 設計

這裡放能讓 agent 不看所有 code 也能改對的跨 app／seam 說明。每個 UI 動作要配真實請求或純函式；欄位用真名；不變量與退役禁令要明寫。為什麼這樣寫見 [`../README.md`](../README.md)。

## 現行設計

- [`task-analysis-engine.md`](task-analysis-engine.md) — API `app/core`、`app/documents`、`app/task_analysis`、`app/opks`、`app/consultation`、`app/export`、adapters(`app/adapters/{postgres,openrouter,xlsx}`)、`/api/v1/job-analysis` 與 Web `/workspace` 的 durable vertical；它是唯一 active design。

## 歷史設計

- [`interview-engine.md`](interview-engine.md) — 舊訪談 engine，已不在 repo runtime；只供決策追溯。
- [`editor-knowledge-pack.md`](editor-knowledge-pack.md) — 舊 OCS editor／knowledge seam，已不在 repo runtime；只供決策追溯。

不要從歷史設計恢復舊 route、hook、store、contract、indexer 或 provider。若現行流程改變，更新 `task-analysis-engine.md` 並同 commit 更新 API／Web 文檔。
