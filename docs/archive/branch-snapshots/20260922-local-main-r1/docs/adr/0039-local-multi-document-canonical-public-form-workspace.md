# 0039. 本機多文件 Workspace、Canonical 文件權威與公版樣式 UI

- 狀態：Superseded by [0043](0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)（勿據以施工）
- 日期：2026-07-23
- 範圍：Local Web 文件庫、儲存／續作、API／Web 文件 shape、既有 editor 取捨
- 前置決策：[0015](0015-document-save-optimistic-concurrency.md)、
  [0020](0020-interview-authoring-interaction-model.md)、
  [0037](0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)、
  [0038](0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)
- 研究：
  [本機多文件與公版 UI 研究](../specs/2026-07-23-local-multi-document-jd-workspace-and-public-form-ui-research.md)

> **2026-07-24 owner amendment（優先於本文其餘段落）**
>
> 第一個成品不做 JD 版本歷史、restore、revision diff、head revision、entity version 或 immutable revision snapshot。
> 每份 document 只有一份 current relational state；員工直接編輯或接受 AI proposal 時更新目前 rows。AI 仍只能先建立
> proposal，由員工 accept／edit／reject。本文關於本機多文件、內部 canonical model、公版樣式 UI 與保留前端資產的
> 決策繼續有效；所有「建立 revision」「revision CAS／hash」文字降為後續優化。active storage authority 見
> [Job Authoring v2 本機單一現況儲存設計](../specs/2026-07-24-job-authoring-v2-relational-storage-research.md)。

> **2026-07-29 supersession**
>
> 本 ADR 從未升為 Accepted，現由 [ADR 0043](0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)
> 完整取代。現行設計採 greenfield `app/job_analysis`、不搬遷／不整合／不雙寫舊資料；本文保留供追溯，
> 不得據以施工。

## 脈絡

現行產品已確定是員工電腦上的本機 Web app，不做登入、帳號、SaaS 或多人共編。先前文字把第一版描述為「一名員工
當下的一份職務說明書」，但 owner 已進一步確認：同一台電腦需要建立、保存、關閉與重新開啟多份職務說明書。

同時，產品 UI 希望延續政府職能基準／公版表格的欄位與閱讀方式；內部資料則需要保存 stable identity、task linkage、
Evidence、proposal、revision 與 custom K/S。若直接沿用舊 `DocumentVersion.content`／OCS 深 JSON／`_pending` 作真相，
會破壞 ADR 0037／0038 已完成的員工 authority 與 canonical Authoring Core。

必須決定：

1. 多份 JD 是否等同帳號／workspace platform；
2. 儲存的真相是舊 OCS JSON 還是 canonical revision；
3. 現有 Web 要保留、重做或局部改造；
4. 第一個可見產品切片應完成多少。

## 決定

### 1. 單機可保存多份，一次只開一份

產品採本機文件庫。沒有登入者、tenant chooser、organization 或 member。一份保存項目稱為 document workspace；每個
workspace 固定是一個 Interview session 對一個 canonical Job Document。

「單一 active draft」的語意是每份 document 只有一個 active head revision，不是整台電腦只能存在一份 document。

### 2. 兩個真相來源、一個組裝層

- Interview vNext 是 conversation、QuestionFrame、Evidence、episode／gap 的真相。
- Job Authoring 是 JD entity、revision、proposal、decision 與 JobStateDigest 的真相。
- Local Workspace 是薄 application composition，只做 list/create/load、scope 隱藏與 use-case 組裝。

Local Workspace 不新增 agent、domain state、generic workflow、event table 或 document storage。

### 3. 內部 canonical，UI 公版樣式，export 另投影

Web 顯示 `JobCanvasView`，欄位命名與排列可以接近政府公版，但 view 是 deterministic projection，不是 persistence
contract。UI 編輯 stable entity 後送 employee command，成功才建立新 canonical revision。

OCS JSON、PDF、XLSX 與簡化招募 JD 都是後續 export profile，不得反向決定 internal Job Model。

第一版 canvas 只顯示已存在的 job title、task、output。未完成的 duty、indicator、K/S 與職能基準 metadata 不得由 UI
或 projector 猜出。

### 4. Autosave 使用 entity command 與 CAS

保留 autosave、dirty／saving／saved／conflict UX；停用新產品路徑的 whole-document OCS PATCH。員工 direct edit 以
revision/head與entity version為 precondition，成功產生 immutable revision。AI output只建立 proposal，接受／修改後採用
才產生 revision。

不採 CRDT／OT；單一操作者、回合制 AI proposal 不需要多人即時同步演算法。

### 5. 保留前端產品資產，替換舊資料流

保留 Next.js、React Query、Tailwind、shadcn、表格視覺、chat composer、task/output 編輯手感與 conflict UX。重寫
`useProfiles`、anonymous user、legacy `useInterview`、whole-document `useDocument`、`_pending` 與舊 profile API binding。

既有 `JobDocTable`／`InterviewPanel` 是互動與視覺參考，不是必須相容的資料元件。

### 6. 第一個切片不新增 migration

多份文件使用既有 Authoring documents 與每份獨立 session。`interview_vnext_sessions.profile_id` 暫由 server-only fixed
local compatibility anchor滿足；它不進 Web DTO，也不是文件列表或權限來源。只有在 vNext session schema因核心需求升版
或 legacy profile tables 正式移除時，才清除此相容債。

## 被否決的選項

### 繼續以舊 dashboard／profile／DocumentVersion 作產品核心

可最快看到舊畫面，但會讓 canonical truth 分裂，且 whole-document PATCH／`_pending` 無法正確表示 Evidence、
entity linkage與proposal stale。

### UI 與資料庫都直接使用政府公版 OCS shape

交換容易，但會讓版面位置碼取代 stable identity，也無法自然表示 custom K/S、task linkage與多來源 provenance。

### 為移除歷史 profile FK 先升整套 Interview schema

長期較乾淨，但會觸及 State、artifact、migration與大量安全網，對第一個可見產品沒有直接品質收益。

### 現在建立 SaaS workspace／account 系統

與本機單使用者需求無關，且會排擠訪談與 JD 品質工作。

### 重做全套前端

會浪費既有公版表格、編輯器與互動資產；目前需要重做的是 authority/data seam，不是每個 button。

## 後果

- 本機可以保存與重開多份 JD，而不引入帳號或 SaaS。
- Web 與 export 都可替換，不會反向污染 canonical Job Model。
- 第一個 UI 可較快出現，但只會誠實顯示已完成的 task/output，不假裝完整 JD 已完成。
- API⇄Web 需要小型 versioned JSON Schema 與 generated TypeScript contract。
- local compatibility profile 是明確的暫時債；不得擴張為產品 profile。
- proposal UI 要等 `episode.code` 真正產生文件提案後再完成，不先建空功能。
- 後續 duty、indicator、K/S 與公版 metadata 都需各自從 canonical contract／operation 加入。
