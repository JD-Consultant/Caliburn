# Caliburn Web

> **歷史文件（2026-09-22 退役）：**本目錄的可執行 Web 已移除；以下內容只保留舊 UI 的設計沿革，不是目前啟動方式。現行 Web 位於 [`experiments/jd-relational-app/web`](../../experiments/jd-relational-app/web/README.md)，正式入口見 [ADR 0077](../../docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)。

以下記錄退役前的 Next.js 本機員工顧問工作區。`/` 導向 `/workspace`；文件庫與單一文件頁分別是 `/workspace` 與 `/workspace/[document_id]`。

## 結構

- `src/features/consultant/`：文件庫、訪談對話、AI 目前理解／焦點／Gap／語意進度、必要澄清、待審文件變更與核准文件 editor。
- `src/shared/api/jobAnalysisApi.ts`：唯一 consultant API client。
- `src/shared/query/jobAnalysisQueries.ts`：TanStack Query keys、revision-monotonic cache 與 invalidation。
- `src/shared/ui/`：通用 UI；不放 domain policy。
- `src/app/workspace/`：App Router composition；只從 feature barrel 掛載。
- `src/architecture.test.ts`：feature-first import boundary。

Web 只讀 purpose-first durable snapshot，不解析 LangGraph checkpoint／interrupt／receipt，也不重算 authority、evidence、readiness 或完成度。正式文件草稿只存在 document-scoped localStorage，不能成為第二份 server document store。所有 AI 文件內容都先讓員工 accept／edit-accept／reject／defer；員工直接編輯另走 authority command。

目前沒有 RAG／Reference UI、consumer 或 contract。能力級別與 A 只有員工可直接編輯，LLM 不產生。

## 驗證

```bash
npm run test
npx tsc --noEmit
npm run lint
```

跨 app 真相見 [`docs/design/consultant-runtime.md`](../../docs/design/consultant-runtime.md)。
