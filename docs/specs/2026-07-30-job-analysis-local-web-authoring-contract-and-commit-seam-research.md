# `job_analysis` 本機 Web 編輯切片、跨語言契約與共用寫入研究

- 日期：2026-07-30
- 產品：本機 Web、單一操作者；可保存多份 JD，但任一時間只開啟一份
- 目標：把已完成的 PostgreSQL durable vertical 接成第一個員工可操作的文件庫與 Task 編輯器
- 不包含：AI 對話 UI、Proposal review UI、O/P/K/S/A、正式公版匯出、舊資料搬遷、登入、SaaS、多人協作

## 1. 結論

第一個 Web 切片只做「文件庫 + 單文件 Task 編輯」；AI 訪談與 Proposal review 是緊接的第二切片，
不和第一切片混成一次大交付。

在接 route 前，先收斂一個現有重複：員工 direct edit 與 Proposal decision 最終都會改 Current JD，
兩者必須先各自完成權限／precondition 檢查，再把完整的新狀態交給同一個 application-level
Current JD commit seam。該 seam 統一做完整狀態驗證、repositories 寫入、Journal、authority-generation
CAS 與 commit／rollback。它不是通用 workflow framework，也不吸收不修改 Current JD 的 AI turn transaction。

API 與 Web 是 Python／TypeScript 跨語言 seam，依 [`docs/contract-strategy.md`](../contract-strategy.md)
採小型 JSON Schema SSOT，生成 Pydantic wire models 與 TypeScript types。Domain model 不由 wire schema
生成；route 使用明確 mapper，契約測試負責抓出 domain／wire 漂移。

## 2. 已確認的產品效果

- 同一台電腦可建立、保存、關閉與重開多份 JD；文件庫只負責選擇。
- 一次只載入、顯示與編輯一份 JD；不做 tabs、並排、多文件背景編輯或 persisted current-document pointer。
- 員工直接編輯 Current JD，按「儲存」後立即寫 PostgreSQL，不呼叫 LLM，也不顯示內部
  `pending_reconciliation`。
- AI 不能呼叫 direct-edit 路徑。第二切片中 AI 只能建立 Proposal；員工接受／修改後接受才會寫 Current JD。
- 員工直接編輯與 AI Proposal review 共用同一個 Task form、同一份 `JdTaskFields` 語意與最終 commit seam；
  入口規則仍分開。
- Task 只要求非空 `statement`；`purpose_result`、`context`、`frequency_text`、
  `responsibility_role` 與 `enablers` 都可留白。
- 內部 UI 不必長得和公版一模一樣；正式匯出才另案投影成公版。第一切片不預建 O/P/K/S/A 空欄位。

## 3. 現況診斷

### 3.1 Current JD 寫入已有兩份 transaction orchestration

`application/authoring.py::_commit_direct_edit` 與
`application/proposal_decisions.py::_persist` 都會：

1. replace Current JD Tasks；
2. replace Proposals；
3. 選擇性寫 Journal；
4. 以 `authority_generation` CAS 更新 Work Model／active question；
5. commit UoW。

但只有 Proposal helper 在發出 repository 寫入前建構完整 `JobAnalysisState` 驗證兩層狀態。這使核心
安全網不是單一來源：日後新增欄位或不變量時，存在只改一條路徑的真實風險。

裁決：建立一個只服務「會改 Current JD 的 authority change」的共用函式。Direct edit 與 Proposal
decision 保留自己的命令驗證、stale 判斷與狀態推導；完成後才呼叫共用函式。Durable AI turn 不改
Current JD，且另有 provider-outside-transaction／snapshot revalidation 語意，不為追求表面統一而塞入。

### 3.2 舊 Web 不是新產品資料流

目前 `/dashboard` 與 `/documents/[id]` 綁定 `users`、`job_profiles`、舊 OCS document 與匿名 user store。
沿用它會把已否決的帳號／profile identity 與舊文件權威帶回來。

裁決：新產品入口是 `/workspace` 與 `/workspace/[document_id]`；首頁改導向 `/workspace`。可重用現有
Button／Card／樣式與 TanStack Query provider，但不得 import 舊 user/profile hooks 或舊 OCS document flow。
舊 route 暫時留著，不在這一切片順手刪除。

### 3.3 API／Web 型別不能手抄兩份

FastAPI 會產生 OpenAPI 3.1，也能據此生成 TypeScript client；但 repo 現行契約規範對「內部、已有
非 Python consumer」要求 JSON Schema SSOT + codegen。兩者並不衝突：本切片用 JSON Schema 擁有
workspace DTO，FastAPI 仍提供 OpenAPI 文件；第一版只生成 types，不再引入一整套 SDK runtime。

選擇 `packages/job-analysis-contract`：

- `schema/job-analysis-workspace.schema.json` 是 wire DTO 的唯一來源；
- 生成 `job_analysis_contract` Pydantic models 給 FastAPI route；
- 生成 `@caliburn/job-analysis-contract` TypeScript types 給 Web；
- codegen check 以既有 `ocs-contract` 做法為模板；
- domain `JdTaskFields` 維持純核心模型，route mapper test 確認所有公開欄位完整映射。

這避免 Python route DTO 與 TypeScript type 漂移，但不把 transport concerns 倒灌到 domain。

## 4. 最新官方資料與設計含意

### 4.1 SQLAlchemy 2.0.51：transaction scope 必須明確且只有一個 owner

SQLAlchemy 2.0.51（repo 固定版本，2026-06-15 current release）說明 transaction context 在成功時
commit、例外時 rollback；`async_sessionmaker.begin()` 同時提供新 AsyncSession 與 transaction。

含意：共用 seam 接收既有 UoW，不自行開第二個 session／nested transaction；UoW 仍是 transaction owner。
先驗完整 `JobAnalysisState`，再發出任何 repository write，最後只 commit 一次。

來源：

- SQLAlchemy 2.0.51，[Transactions and Connection Management](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
- SQLAlchemy 2.0.51，[Asynchronous I/O](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

### 4.2 FastAPI：獨立 router、明確 response model、更新語意要對得上 HTTP

FastAPI 官方目前仍以 `APIRouter` 組織大型應用；response model 會驗證、文件化並過濾輸出。局部更新可
用 `PATCH` + `exclude_unset`；完整取代則使用 `PUT` 更誠實。

本切片：

- 新增單一 `job_analysis` router，掛入現有唯一 composition root；
- 文件標題若日後開放局部修改才用 `PATCH`；本切片只在建立時設定標題；
- Task form 每次送完整可編輯欄位，使用 `PUT`，不把完整取代偽裝成 partial patch；
- route 只做 transport mapping 與 application error → HTTP status，domain／transaction 規則不寫進 route。

來源：

- FastAPI，[Bigger Applications - Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- FastAPI，[Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)
- FastAPI，[Body Updates](https://fastapi.tiangolo.com/tutorial/body-updates/)
- FastAPI，[Generating SDKs](https://fastapi.tiangolo.com/advanced/generate-clients/)

### 4.3 Next.js 16.2.6／TanStack Query v5：互動邊界要小，server state 不另抄一份

repo 內隨 Next.js 16.2.6 安裝的官方文件說 pages/layouts 預設是 Server Components；需要 state、event
handlers 或 browser API 時才使用 Client Components，並應把 `use client` 限在較小的互動元件。它也明列
React Query 可用於 Client Component 資料取得。

TanStack Query v5 官方建議 mutation 成功後 invalidate 相關 query；若 `onSuccess` 回傳 Promise，mutation
會維持 pending，直到資料更新完成。

含意：頁面 shell 保持 Server Component；`DocumentLibrary` 與 `TaskEditor` 是小型 Client Components。
PostgreSQL／API response 是 server-state 真相；mutation 成功後 invalidate/refetch，不建立第二份 Zustand
document store，也不把 JD query 寫入 browser persistent cache。

來源：

- Next.js 16，[Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)
- TanStack Query v5，[Invalidations from Mutations](https://tanstack.com/query/v5/docs/framework/react/guides/invalidations-from-mutations)

### 4.4 人工權威：只在真正改文件時要求決定

OpenAI 目前 approval lifecycle 把待審動作存成 interruption，由 application 持有 approve／reject 與可恢復
state。Anthropic 2026 的實際自治研究指出，有效 oversight 不等於逐步核准；模型在不確定時主動追問也是
重要控制。

含意：員工自己的 direct edit 不繞 Proposal；AI 的內部 Work Model 整理也不逐步彈核准。只有 AI 要把內容
寫入 Current JD 時才建立可恢復 Proposal。這是第二切片，第一切片只先確保共用寫入 seam 能承接它。

來源：

- OpenAI，[Guardrails and human review — Approval lifecycle](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals#approval-lifecycle)
- Anthropic，2026-02，[Measuring AI agent autonomy in practice](https://www.anthropic.com/research/measuring-agent-autonomy)

### 4.5 表單：標籤、錯誤與保存狀態必須可讀

W3C WAI 要求表單控制項有可辨識標籤。第一版每個輸入都有 visible label；保存中／成功／失敗使用可讀文字
與 `aria-live`，不只靠顏色或 icon。

來源：W3C WAI，[Labeling Controls](https://www.w3.org/WAI/tutorials/forms/labels/)

## 5. 方案比較

### A. 改造舊 dashboard／OCS editor

優點是畫面已有雛形；缺點是匿名 user、profile、OCS envelope、舊 hooks 與舊文件權威彼此糾纏。
拒絕：表面省檔案，實際會把錯誤邊界帶回新產品。

### B. 一次接文件庫、Task 編輯、AI 對話與 Proposal review

優點是更早看到完整畫面；缺點是 route、cross-language contract、LLM error、Proposal UX 與持久化問題同時出現，
失敗難歸因。拒絕：不是不能做，而是不符合目前「先得到可操作成品、減少重構」的順序。

### C. 兩個薄切片（採用）

第一切片驗證文件庫、單文件編輯、共用 commit seam、API contract、PostgreSQL reload 與基本 UX；第二切片在
同一個 Task form 上加對話與 Proposal 卡。若第一切片的 DTO／表單欄位不合理，修正成本仍很低。

## 6. 第一切片具體邊界

### 6.1 API

```text
GET    /api/v1/job-analysis/documents
POST   /api/v1/job-analysis/documents
GET    /api/v1/job-analysis/documents/{document_id}
POST   /api/v1/job-analysis/documents/{document_id}/tasks
PUT    /api/v1/job-analysis/documents/{document_id}/tasks/{task_id}
DELETE /api/v1/job-analysis/documents/{document_id}/tasks/{task_id}
PUT    /api/v1/job-analysis/documents/{document_id}/task-order
```

- `POST document` 由 Web 先生成 UUID，重送同一 request 不建立第二份文件。
- Task mutation 使用 Web 每次操作生成、同一次重送保持不變的 `X-Operation-Id` header，映射既有
  `entry_id` idempotency；這是本 route 的明確參數，不新增全站 middleware，也不宣稱它是外部標準。
- `GET document` 第一版只回文件資訊與 Current JD Tasks；不外洩 Work Model、generation、lineage、Journal 或
  內部 reconciliation。
- application errors 明確映射：404 not found、409 idempotency／authority conflict、422 invalid order／payload。
- 第一切片不做 rename、delete document、duplicate、search、pagination 或 export。

### 6.2 Web

```text
/
└─ redirect /workspace

/workspace
├─ 列出本機已保存 JD
└─ 建立 JD（職務名稱）

/workspace/[document_id]
├─ 返回文件庫
├─ 顯示目前唯一開啟的 JD
├─ 新增 Task
├─ 同一 TaskForm 編輯完整 JdTaskFields
├─ 刪除 Task（確認）
└─ 上移／下移排序
```

- 每個 Task 以明確「編輯 → 儲存／取消」提交；不做每個 keypress autosave，也不呼叫 LLM。
- `statement` 必填，其餘欄位留白合法；空值顯示「尚未填寫」，不補 placeholder 內容。
- 排序先用可鍵盤操作的上移／下移，不在第一版加入 drag-only interaction。
- mutation 期間鎖定該操作，成功後 invalidate 文件／文件庫 query；失敗保留表單內容並顯示錯誤。
- 不 import 舊 `useUserStore`、profile hooks、OCS editor types 或 interview components。

## 7. 測試與停線條件

最小但足夠的安全網：

1. 共用 commit seam characterization：direct edit 與 accepted/edited Proposal 都經同一函式；完整狀態不合法時
   repository 零寫入，CAS 失敗 rollback。
2. Contract codegen guard：JSON Schema、Pydantic、TypeScript 任一漂移即 fail。
3. API route tests：create/list/open/add/edit/delete/reorder、404/409/422 與 no-user/no-tenant contract。
4. 一條 real PostgreSQL HTTP vertical：建立文件 → 新增只有 statement 的 Task → 補欄位 → 排序 → reload。
5. Web pure tests：DTO↔form mapping、空 optional fields、query keys、mutation error 保留 draft。
6. Web gates：Vitest、`tsc --noEmit`、ESLint；必要時以本機 browser 做一次手動 smoke，但不先引入 E2E framework。

停線：若需要 import 舊 user/profile/OCS 資料流、修改 `job_analysis` domain 只為配合 UI、建立通用 API framework、
加入 auth/tenant、或為第一切片增加 OPKS／export，先回到本研究重新裁決。

## 8. 下一步

1. ADR 接受本研究的 commit seam、contract mechanism 與兩個薄切片。
2. 使用者確認書面設計，尤其是「按儲存」而非 keypress autosave，以及第一切片暫不做 AI UI。
3. 另寫 bite-size plan；TDD 依序做 commit seam → contract → API → Web → real-PG/browser smoke。
