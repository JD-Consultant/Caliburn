# Caliburn Contract Strategy

## 現行規則

Current-only monorepo 目前只有一個跨語言 contract：`packages/job-analysis-contract`。其 JSON Schema 是 SSOT，生成 Python／TypeScript DTO，消費者是 `apps/api` 與 `apps/web`。改 schema 必須先研究、更新 ADR／plan，再執行 codegen、schema diff 與兩端測試。

API 內部的 domain／application model 不直接 import transport contract；mapper 是 HTTP DTO 與 domain 之間唯一的轉換邊界。Web 不手寫重複的 Current State、Evidence、Proposal 或 readiness shape。

## 選擇判準

| seam | 機制 |
|---|---|
| 跨語言或對外的 JSON shape | JSON Schema SSOT + generated models；在 CI 驗證生成物無 diff |
| 純 Python、同 repo、少數消費者的內部 port | shared typed module 或明確 Protocol；不另建泛用契約 package |
| 未來出現外部／隱藏消費者 | 另開研究與 ADR，評估 OpenAPI-first 或 consumer-driven contract |

不要為已移除的 OCS、indexer、PDF ETL 或舊 Web seam 新增 contract。歷史 ADR 0004／0010／0011 的機制只作背景，不代表那些 package 仍存在。

## 交付流程

1. 研究 seam 的 drift surface 與 authoritative source，寫入 `docs/specs/`。
2. 在 `docs/adr/` 記錄選擇、拒絕選項與升級條件，並更新索引。
3. 在 `docs/plans/` 拆出可驗證切片。
4. 先跑現有測試，再改 codegen／consumer；一個 task 一個 commit。
5. 跑 `npm run check-codegen -w @caliburn/job-analysis-contract`、API／Web 測試與 `git diff --check`。
