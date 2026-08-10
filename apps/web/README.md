# Caliburn Web

Next.js 本機工作台，只服務現行 Job Analysis API。`/` 導向 `/workspace`；文件庫與單一文件工作頁分別是 `/workspace` 與 `/workspace/[document_id]`。

## 結構

- `src/components/workspace/`：文件庫、JD header、Task／Duty／OPKS 編輯、顧問對話與 Proposal 決策。
- `src/lib/jobAnalysisApi.ts`：唯一 API client。
- `src/lib/jobAnalysis*.ts`：query、form、export 與 contract mapping 純函式。
- `src/components/layout/Providers.tsx`：TanStack Query client。
- `packages/job-analysis-contract/`：生成的 TypeScript DTO 來源。

Web 不保留舊 dashboard、OCS editor、interview component、舊 store 或 OCS contract；新功能只能接 `/api/v1/job-analysis` 與現有 Job Analysis contract。

## 驗證

```bash
npm run test
npx tsc --noEmit
npm run lint
```

Web 不自行重算 readiness、Evidence 或 authority state；讀取 API projection，寫入使用 API 回傳的 idempotency／decision contract。跨 app 流程見 [`docs/design/task-analysis-engine.md`](../../docs/design/task-analysis-engine.md)。
