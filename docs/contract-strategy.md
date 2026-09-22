# Caliburn Contract Strategy

## 現行規則

Current 產品（`experiments/jd-relational-app` 及其 `web`）的跨語言 contract 位於 App 自己的 `contracts/`。JSON Schema 是 SSOT，`scripts/generate_contract.py` 以鎖定的標準生成器產生 `src/jd_relational/generated` 下的 Python DTO 與 TypeScript 型別；API 與 Web 共用這批生成物。改 schema 必須先研究、更新 ADR／plan，再執行 codegen、schema diff 與兩端測試。舊 `packages/job-analysis-contract` 已退役，只留歷史 README，不得再作正式依賴。

保留、隔離的 RAG bounded context 另有自己的跨語言 contract `packages/ocs-contract`（同一種 JSON Schema SSOT 機制，生成 Pydantic model 與 TypeScript type，`pnpm --filter @caliburn/ocs-contract run check-codegen` 驗證無 diff），但不屬於 current JD 產品的 contract surface：正式 App／Web 不 import、不消費它。

API 內部的 domain／application model 不直接 import transport contract；mapper 是 HTTP DTO 與 domain 之間唯一的轉換邊界。Web 不手寫重複的 Current State、Evidence、Proposal 或 readiness shape。

## 選擇判準

| seam | 機制 |
|---|---|
| 跨語言或對外的 JSON shape | JSON Schema SSOT + generated models；在 CI 驗證生成物無 diff |
| 純 Python、同 repo、少數消費者的內部 port | shared typed module 或明確 Protocol；不另建泛用契約 package |
| 未來出現外部／隱藏消費者 | 另開研究與 ADR，評估 OpenAPI-first 或 consumer-driven contract |

不要僅因保留、隔離的 RAG bounded context（OCS、indexer、PDF ETL）本身有 contract（`packages/ocs-contract`；ADR 0004／0010／0011 為歷史依據），就新增 contract 把它們接進 current 產品；ADR 0057 的隔離邊界不因 contract 存在而鬆動。已移除的舊 Web seam（interview／job-authoring）同樣不要新增 contract。

## 交付流程

1. 研究 seam 的 drift surface 與 authoritative source，寫入 `docs/specs/`。
2. 在 `docs/adr/` 記錄選擇、拒絕選項與升級條件，並更新索引。
3. 在 `docs/plans/` 拆出可驗證切片。
4. 先跑現有測試，再改 codegen／consumer；一個 task 一個 commit。
5. 跑根目錄 `pnpm build`（包含正式 App `codegen:check`）、API／Web 測試與 `git diff --check`；RAG contract 改動另跑其 filter 命令。
