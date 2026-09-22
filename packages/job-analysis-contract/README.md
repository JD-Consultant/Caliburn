# job-analysis-contract

> **歷史文件（2026-09-22 退役）：**本套契約的 schema、生成器與生成碼已隨舊 API／Web 移除；本頁只保留契約演進記錄。現行新 App 契約由 [`experiments/jd-relational-app/contracts`](../../experiments/jd-relational-app/contracts) 產生並驗證，詳見 [ADR 0077](../../docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)。

以下描述退役前 `/api/v1/job-analysis/consultant-documents` 與 `/workspace` 共用的 typed seam。`schema/job-analysis-workspace.schema.json`
是唯一 source of truth；`src/job_analysis_contract/models.py` 與 `types/job-analysis-workspace.ts`
都是生成物，不可手改。

主要消費者：`apps/api` 的 consultant route／mapper／problem responses，以及 `apps/web` 的
consultant workspace 與 API client。此套件只發布 durable consultant／approved document／problem 契約與生成物，不放 application service、
資料庫模型或 UI 邏輯。

```bash
npm run codegen -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/job-analysis-contract
```

schema 變更後先執行 `codegen` 並檢查生成 diff；不要直接編輯 Python／TypeScript 生成檔。
