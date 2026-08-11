# 0057. Current-only runtime 與資料邊界

- **狀態**：Proposed
- **日期**：2026-08-10（2026-08-11 修正 Decision 5 與 Consequences：RAG 供應鏈改為保留＋隔離，非刪除；詳見 [`docs/specs/2026-08-11-rag-bounded-context-retention-design.md`](../specs/2026-08-11-rag-bounded-context-retention-design.md)）

## Context

Caliburn 的第一版產品已收斂到本機 Web `job_analysis`：API 的 `/api/v1/job-analysis`、Web 的 `/workspace`、Current State PostgreSQL tables、OpenRouter consultant 與 XLSX export。repo 同時保留舊 OCS editor、`app.interview`、隔離中的 `app.interview_vnext`、`app.job_authoring`、舊 Alembic history，以及尚未接上 current API/Web、但未來 RAG 檢索仍需要的供應鏈——`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract`、`packages/indexer-contract`（PDF → OCS contract → OCS JSON → indexer → embedder/Qdrant）。

owner 已明確決定 current 產品只需要新系統，並確認本機資料庫可以重建、舊資料可丟棄；繼續保留並存的已淘汰 `app.interview`／`app.interview_vnext`／`app.job_authoring`／舊 OCS editor route／舊 migration 會持續成為維護邊界，也會讓未來 agent 誤把歷史架構當成可用產品。2026-08-11 owner 進一步澄清：RAG 供應鏈不是已淘汰架構，而是尚未接線、但未來檢索功能仍要用的來源與管線；把它與 `interview`／`job_authoring` 等已淘汰路徑混為一談會誤刪未來要用的程式碼與 908 份 PDF／OCS JSON 來源資料。

## Decision

採用 current-only hard cut，並以隔離取代刪除處理 RAG 供應鏈：

1. production composition root 只掛 `job_analysis` router；API 只保留 current domain/application/provider/PostgreSQL seam。
2. Web 只保留 `/workspace` 與 current `job-analysis-contract`；移除舊 OCS editor 與其 client、hooks、types。
3. 移除 `interview`、`interview_vnext`、`job_authoring` runtime、測試與舊 migration 0001–0011。
4. 將 current migration 0012 重新接成 root，保留 0012–0017 的 current schema 演進；fresh DB 的 head 只建立 `job_analysis_*` tables。
5. RAG 供應鏈——`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract`、`packages/indexer-contract`——維持 monorepo 成員，作為與 current API/Web 隔離的獨立 bounded context：各自安裝、測試、執行。Qdrant／embedder 是選用（opt-in）的 RAG 基礎設施，Compose 以 `rag` profile 標記，不在 `docker compose up`／`npm run up`／`npm run dev` 的預設啟動範圍內。這個決定不為 current API/Web 新增任何 import、route、資料庫寫入或 dual-write；正式讓 current API/Web 消費 RAG 檢索結果須另開 ADR。
6. 不做資料遷移、dual write、舊 API 相容層或 SaaS／登入／多租戶能力。歷史 ADR/spec 保留為追溯材料，不視為 runtime。

## Consequences

好處是啟動、依賴、資料表與程式邊界都直接對齊第一版 current 產品，current engine 不再被舊路徑污染，DB 可從空白狀態驗證；同時 RAG 供應鏈與其 908 份 PDF／OCS JSON 來源資料被保留而非誤刪，未來檢索功能有可重建的基礎。代價是舊本機資料、舊 URL 與舊 OCS editor／訪談流程不再可用，需要重建 Postgres volume 或建立新資料庫並重新執行 migration；monorepo 也重新包含兩個獨立 Python data app 與一個 GPU container，即使 current API/Web 完全不消費它們，仍是 repo 的維護與磁碟成本（以 `rag` Compose profile 與各自 uv project 隔離，預設指令不啟動它們）。未來若要恢復 `app.interview`／`app.interview_vnext`／`app.job_authoring` 等已淘汰能力，仍必須開新 ADR 與新 bounded context，不得直接從 Git 歷史復活 deleted runtime；若要讓 current API/Web 開始消費 RAG 檢索結果，也必須另開 ADR，明確定義 query contract、index freshness、embedding identity、failure fallback、API transaction 外的 provider 呼叫，以及 current JD provenance／evidence linkage——本 ADR 不授權任何 current API/Web wiring。
