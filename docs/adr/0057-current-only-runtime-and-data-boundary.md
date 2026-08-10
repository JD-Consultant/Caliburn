# 0057. Current-only runtime 與資料邊界

- **狀態**：Proposed
- **日期**：2026-08-10

## Context

Caliburn 的第一版產品已收斂到本機 Web `job_analysis`：API 的 `/api/v1/job-analysis`、Web 的 `/workspace`、Current State PostgreSQL tables、OpenRouter consultant 與 XLSX export。repo 仍同時保留舊 OCS editor、`app.interview`、隔離中的 `app.interview_vnext`、`app.job_authoring`、舊 Alembic history、OCS/indexer/embedder apps 與 contracts。

owner 已明確決定只需要新系統，並確認本機資料庫可以重建、舊資料可丟棄。繼續保留並存 runtime 會讓已淘汰的 route、table、provider 與依賴持續成為維護邊界，也會讓未來 agent 誤把歷史架構當成可用產品。

## Decision

採用 current-only hard cut：

1. production composition root 只掛 `job_analysis` router；API 只保留 current domain/application/provider/PostgreSQL seam。
2. Web 只保留 `/workspace` 與 current `job-analysis-contract`；移除舊 OCS editor 與其 client、hooks、types。
3. 移除 `interview`、`interview_vnext`、`job_authoring` runtime、測試與舊 migration 0001–0011。
4. 將 current migration 0012 重新接成 root，保留 0012–0017 的 current schema 演進；fresh DB 的 head 只建立 `job_analysis_*` tables。
5. monorepo 移除不再被 current Web/API 消費的 OCS/indexer/pdf/embedder apps 與 contracts；Compose 只啟動 PostgreSQL。
6. 不做資料遷移、dual write、舊 API 相容層或 SaaS／登入／多租戶能力。歷史 ADR/spec 保留為追溯材料，不視為 runtime。

## Consequences

好處是啟動、依賴、資料表與程式邊界都直接對齊第一版產品，current engine 不再被舊路徑污染，DB 可從空白狀態驗證。代價是舊本機資料、舊 URL 與舊 OCS／訪談流程不再可用；需要重建 Postgres volume 或建立新資料庫並重新執行 migration。未來若要恢復任何舊能力，必須開新 ADR 與新 bounded context，不得從 Git 歷史直接復活 deleted runtime。
