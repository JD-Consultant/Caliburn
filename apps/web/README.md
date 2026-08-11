# Caliburn Web

Next.js 本機工作台，只服務現行 Job Analysis API。`/` 導向 `/workspace`；文件庫與單一文件工作頁分別是 `/workspace` 與 `/workspace/[document_id]`。

## 結構

Web 依 UI responsibility 採 feature-first；`shared` 只放 HTTP／query／通用 UI，不放 domain policy；跨 feature 組裝只在 Next.js app workspace composition（`app/workspace/[document_id]/_components/`）。

- `src/features/documents/`：文件庫、JD header、Duty／Task 員工直接編輯與 readiness 提示。
- `src/features/consultation/`：Task Proposal 卡片與決策 helper。
- `src/features/opks/`：OPKS 編輯、Proposal 卡片與 helper。
- `src/features/export/`：匯出 dirty-state／檔名純函式（無獨立 UI）。
- `src/shared/api/jobAnalysisApi.ts`：唯一 API client。
- `src/shared/query/jobAnalysisQueries.ts`：TanStack Query options／keys。
- `src/shared/ui/`：shadcn-style 通用元件。
- `src/shared/providers/Providers.tsx`：TanStack Query client。
- `src/app/workspace/[document_id]/_components/`：`ConsultationPanel`／`ConsultationWorkspace`，因同時協調 Task／OPKS proposal，留在 app 層組裝而非任一 feature 內。
- `src/architecture.test.ts`：AST 掃 import，擋 `shared → feature`、`feature ↔ feature`、`app` 繞過 feature `index.ts` 的深路徑 import。
- `packages/job-analysis-contract/`：生成的 TypeScript DTO 來源。

Web 不保留舊 dashboard、OCS editor、interview component、舊 store 或 OCS contract；新功能只能接 `/api/v1/job-analysis` 與現有 Job Analysis contract。

## 驗證

```bash
npm run test
npx tsc --noEmit
npm run lint
```

Web 不自行重算 readiness、Evidence 或 authority state；讀取 API projection，寫入使用 API 回傳的 idempotency／decision contract。跨 app 流程見 [`docs/design/task-analysis-engine.md`](../../docs/design/task-analysis-engine.md)。
