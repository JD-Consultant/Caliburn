# Web 資料層

現行 Web 使用 TanStack Query 讀取 Job Analysis projection；Query cache 是讀取快取，不是另一份文件真相。真相在 API 的 PostgreSQL Current State。

## Query keys

`src/lib/jobAnalysisQueries.ts` 定義三組 key：

- `job-analysis/documents`：文件庫。
- `job-analysis/documents/{id}`：單一文件與 Current JD。
- `job-analysis/documents/{id}/consultation`：顧問與 Proposal projection。

## 寫入規則

`jobAnalysisApi.ts` 的 mutation 成功後，依 `jobAnalysisInvalidationKeys(documentId)` invalidate 文件、文件庫與 consultation query；畫面以 API 回傳值更新，不另建 local document store。`Idempotency-Key` 與決策欄位由各 operation helper 負責，Web 不重算 domain invariant。

`Providers.tsx` 只建立 QueryClientProvider；不持久化舊 OCS／knowledge cache，也不保存第二份文件真相。
