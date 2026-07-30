# 0045. `job_analysis` 本機 Web 契約與共用 Current JD commit seam

- 狀態：Proposed
- 日期：2026-07-30
- 補充：[0043](0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)、
  [0044](0044-partial-jd-task-reconciliation-and-human-confirmation.md)
- 研究：
  [`job_analysis` 本機 Web 編輯切片、跨語言契約與共用寫入研究](../specs/2026-07-30-job-analysis-local-web-authoring-contract-and-commit-seam-research.md)

## 脈絡

`job_analysis` 已完成 PostgreSQL durable vertical，但沒有 route 或 Web。現有 Web 綁定匿名 user、job profile、
舊 OCS document，不能作為新產品資料流。員工 direct edit 與 Proposal decision 雖使用同一 UoW／repositories，
卻各自實作 Current JD transaction orchestration，且完整狀態驗證不一致。

新 seam 同時有 Python API 與 TypeScript Web consumer；手寫兩份 DTO 會讓欄位漂移。產品已確認可以保存多份 JD，
但一次只開啟與編輯一份。

## 決定

- 先建立一個小型 application-level Current JD commit seam。員工 direct edit 與 Proposal accepted／edited
  各自完成入口規則後，共用完整 `JobAnalysisState` 驗證、Current JD／Proposal repositories、Journal、
  authority-generation CAS 與單次 UoW commit。Durable AI turn 不修改 JD，不併入此 seam。
- API／Web workspace DTO 依契約規範採 `packages/job-analysis-contract` JSON Schema SSOT，生成 Pydantic
  wire models 與 TypeScript types；domain 不依賴 transport contract，route mapper tests 防止語意欄位漏接。
- 新 FastAPI `APIRouter` 掛在現有唯一 `/api/v1` composition root 下，路徑為 `/job-analysis/documents`；
  不含 user、profile、tenant 或 auth。
- 新 Web 入口為 `/workspace` 與 `/workspace/[document_id]`。可保存多份文件，但任一時間只載入一份；
  不存 current-document pointer、不做 tabs 或並排。
- 第一切片只交付文件建立／列出／開啟及 Current JD Task 新增、完整編輯、刪除、排序與 reload。
  每個 Task 明確按「儲存」提交；不做 keypress autosave。
- 同一個 Task form 供員工 direct edit 與後續 AI Proposal review 使用；但 AI 永遠不能呼叫 direct-edit
  endpoint。AI 對話與 Proposal UI 是第二切片。
- Web 使用 Next.js 16 Server Component shell、小型 Client Components 與既有 TanStack Query v5；mutation
  成功後 invalidate/refetch，不建立第二份 document store，不持久化 JD browser query cache。
- 舊 dashboard／documents routes 暫留但不接新入口；不搬、不整合、不雙寫舊資料。

## 後果

正面：

- 人與 AI 最終修改 Current JD 時共用同一套完整狀態驗證與 PostgreSQL 原子寫入，不會出現兩份核心邏輯。
- Python／TypeScript wire types 有 SSOT 與 codegen guard；UI 可先快速驗證真正的資料形狀。
- 第一個切片小而可用，能及早驗證保存、重開與員工編輯，不被 LLM／Proposal UI 問題拖住。

成本：

- 新增一個小型 contract package、route mapper 與 codegen check。
- 先交付 Task 編輯，AI 對話與 Proposal review 要再接一個薄切片。
- domain 與 wire contract 仍是不同責任；新增公開欄位時必須明確更新 schema 與 mapper，而不是讓 transport
  直接擁有 domain。

風險：

- 舊 Web routes 暫時共存，必須以 root redirect、依賴 guard 與文檔明確標示新產品入口，避免誤接。
- 第一切片沒有 document rename/delete、autosave、OPKS 或 export，不得宣稱完整 JD 產品已完成。

