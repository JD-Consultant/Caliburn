# 0045. `job_analysis` 本機 Web 契約與共用 authority commit seam

- 狀態：Accepted
- 日期：2026-07-30
- 補充：[0043](0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)、
  [0044](0044-partial-jd-task-reconciliation-and-human-confirmation.md)
- 研究：
  [`job_analysis` 本機 Web 編輯切片、跨語言契約與共用寫入研究](../specs/2026-07-30-job-analysis-local-web-contract-and-authority-commit-seam-research.md)

## 脈絡

`job_analysis` 已完成 PostgreSQL durable vertical，但沒有 route 或 Web。現有 Web 綁定匿名 user、job profile、
舊 OCS document，不能作為新產品資料流。員工 direct edit 與 Proposal decision 雖使用同一 UoW／repositories，
卻各自實作 Current JD transaction orchestration，且完整狀態驗證不一致。

新 seam 同時有 Python API 與 TypeScript Web consumer；手寫兩份 DTO 會讓欄位漂移。產品已確認可以保存多份 JD，
但一次只開啟與編輯一份。現有 Proposal persistence helper 也會保存只改 Proposal／stale 狀態、不改 JD 的
authority change，因此 seam 不得用 `Current JD` 命名誤導責任。

## 決定

- 先建立小型 application-level `commit_authority_change` seam。員工 direct edit 與 Proposal decision 各自完成
  入口規則後，共用完整 `JobAnalysisState` 驗證、Current JD／Proposal repositories、Journal、
  authority-generation CAS 與單次 UoW commit。Durable AI turn 不併入：它的新狀態已由
  `apply_task_analysis_result` 驗證，且另有 provider-outside-transaction／snapshot revalidation 語意。
- API／Web workspace DTO 是契約 #4，採 `packages/job-analysis-contract` JSON Schema SSOT，生成 Pydantic
  wire models與 TypeScript types；domain 不依賴 transport contract，AST guard 禁止 `app.job_analysis`
  import `job_analysis_contract`，只有 route mapper 可同時認識兩者。
- 新 FastAPI `APIRouter` 掛在現有唯一 `/api/v1` composition root 下，路徑為 `/job-analysis/documents`；
  不含 user、profile、tenant 或 auth。
- `PUT /job-analysis/documents/{document_id}` 以 Web 產生的 UUID 建立文件或完整取代該文件的可寫 metadata
  （第一版只有 `title`），因此同一端點也負責改名；Tasks 是獨立 subresource，PUT metadata 不得改動 Tasks、
  Work Model、Proposals 或 Journal。Title 不屬於模型 authority read-set；改名不 bump `authority_generation`、
  不寫 Journal，也不經 `commit_authority_change`。建立回 201，取代回 200；不另開 PATCH，也不要求
  `Idempotency-Key`。
- Application layer 為 metadata write 在 `DocumentRepository` 增加只更新 `title`／`updated_at` 的
  `update_title` port 與 PostgreSQL adapter；
  現有 document create-or-replay 流程遇到同 ID、不同 title 時改為取代 title，不再回
  `IdempotencyConflict`。這條 port 不得順帶承接 Task 或其他 authority 寫入。
- Task mutation 使用 `Idempotency-Key` 對應既有 `entry_id`；它是業界慣例，不宣稱為已發布標準。不得新增
  全站 middleware、fallback 或隱藏 retry。
- 新 route 的錯誤採 RFC 9457 `application/problem+json`。`type` 是 JSON Schema enum 與 Web 唯一判斷依據：
  `https://caliburn.dev/problems/job-analysis/document-not-found`、
  `https://caliburn.dev/problems/job-analysis/task-not-found`、
  `https://caliburn.dev/problems/job-analysis/idempotency-conflict`、
  `https://caliburn.dev/problems/job-analysis/authority-conflict`、
  `https://caliburn.dev/problems/job-analysis/invalid-task-order`、
  `https://caliburn.dev/problems/job-analysis/invalid-request`。
  不加重複的 `error_code`，Web 不解析 `detail`；`errors?` 是本產品擴充，固定為
  `[{field: string, message: string}]`，consumer 忽略不認得的擴充。生成的 TypeScript union 必須以
  exhaustive switch／`never` 守住六種型別。
- Application error 由新 route 映射為 Problem Details。FastAPI body validation handler 是 app-scoped，故唯一
  handler 只對 `/api/v1/job-analysis/*` 轉換格式；其他路徑交回既有 FastAPI handler，並以 regression test
  保證 legacy 422／409 body 不變。
- Wire mapper 對 optional text 先 trim，空字串轉 `null`；`statement` trim 後為空則回 `invalid-request`。
- 新 Web 入口為 `/workspace` 與 `/workspace/[document_id]`。可保存多份文件，但任一時間只載入一份；
  不存 current-document pointer、不做 tabs 或並排。
- 第一切片只交付文件建立／列出／開啟及 Current JD Task 新增、完整編輯、刪除、排序與 reload。
  每個 Task 明確按「儲存」提交；不做 keypress autosave。寫入只有 Client mutation → FastAPI，不另用
  Server Actions／`useActionState` 寫同一份 server state。以 Next `<Link onNavigate>`、`beforeunload`、
  Ctrl／Cmd+Enter 與 Esc 保護未存草稿。
- 同一個 Task form 供員工 direct edit 與後續 AI Proposal review 使用；但 AI 永遠不能呼叫 direct-edit
  endpoint。AI 對話與 Proposal UI 是第二切片。
- Web 使用 Next.js 16 Server Component shell、小型 Client Components 與既有 TanStack Query v5；mutation
  成功後 invalidate/refetch，不建立第二份 document store，不持久化 JD browser query cache。
- 舊 dashboard／documents routes 暫留但不接新入口；不搬、不整合、不雙寫舊資料。
- 第一切片明確接受 stale browser page 的 last-write-wins；現有 transaction 內
  `authority_generation` CAS 只保護伺服器端 authority change，不是瀏覽器送舊資料的防線。若實際使用出現
  lost update，再另案加 per-task ETag／`If-Match` → 412；不得把 legacy ADR 0015 autosave／版本契約默認接回。
- 生成工具先沿用 repo 現有 `json-schema-to-typescript`。若 schema 需要它無法可靠生成的 2020-12 特性，
  才停線評估 FastAPI OpenAPI 3.1 + `openapi-typescript`；本切片不升 repo 的 FastAPI 0.115.0，最新版
  0.141.1 的升級另案處理。

## 後果

正面：

- 人與 AI 的 authority change 共用同一套完整狀態驗證與 PostgreSQL 原子寫入，不會出現兩份核心邏輯。
- Python／TypeScript wire types 有 SSOT 與 codegen guard；UI 可先快速驗證真正的資料形狀。
- 第一個切片小而可用，能及早驗證保存、重開與員工編輯，不被 LLM／Proposal UI 問題拖住。

成本：

- 新增一個小型 contract package、route mapper、六種 Problem type 與 codegen check。
- 先交付 Task 編輯，AI 對話與 Proposal review 要再接一個薄切片。
- domain 與 wire contract 仍是不同責任；新增公開欄位時必須明確更新 schema 與 mapper，而不是讓 transport
  直接擁有 domain。

風險：

- 舊 Web routes 暫時共存，必須以 root redirect、依賴 guard 與文檔明確標示新產品入口，避免誤接。
- 第一切片沒有 document delete、autosave、瀏覽器 stale-write 防護、OPKS 或 export，不得宣稱完整 JD 產品已完成。
