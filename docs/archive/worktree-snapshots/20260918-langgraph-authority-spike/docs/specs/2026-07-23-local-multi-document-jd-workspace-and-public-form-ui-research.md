# 本機多職務說明書、Canonical 文件與公版樣式 UI 架構研究

- 日期：2026-07-23
- 狀態：Historical research；revision persistence 已被 2026-07-24 owner 裁決取代
- 範圍：本機文件庫、儲存／續作、公版樣式 JD canvas、API／Web seam、既有前端取捨
- 不包含：SaaS、登入、帳號密碼、多人共編、完整 K/S／指標／匯出實作
- 上游 authority：
  - [ADR 0038](../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)
  - [專業職務分析與共編研究](2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)
  - [最小 Authoring Core 計畫](../plans/2026-07-23-interview-vnext-minimal-authoring-core-plan.md)
  - [production 顧問 loop 計畫](../plans/2026-07-23-interview-vnext-production-openrouter-consultant-loop-plan.md)

> **2026-07-24 scope correction**
>
> 本文對本機多文件、雙欄共編、公版樣式 UI、內部 canonical model 與保留前端資產的研究仍有效；所有 immutable
> revision、head hash、entity version、restore 與 revision CAS 描述不再是第一個成品要求。MVP 只保存每份 JD 的目前
> relational state，AI proposal 仍須由員工接受、修改後採用或拒絕。active persistence authority 見
> [Job Authoring v2 本機單一現況儲存設計](2026-07-24-job-authoring-v2-relational-storage-research.md)。

## 1. 結論先行

目前架構沒有跑掉，不需要重做 LLM runtime、Context Engine、Evidence 或 Authoring Core。下一步應增加一層薄的
`Local Workspace` composition，將既有能力組成可見產品：

```text
本機文件庫
  -> 開啟一份 JD workspace
  -> 左側 AI 顧問對話
  -> 右側公版欄位排列的可編輯 JD canvas
  -> Employee answer -> Evidence -> next question
  -> Employee direct edit -> canonical revision
  -> AI proposal -> employee accept/edit/reject -> canonical revision
  -> deterministic public-form/export projection
```

核心裁決如下：

1. 一台電腦可保存多份職務說明書；一次只開啟一份，不做帳號、workspace membership 或多人狀態。
2. 每份保存項目是一個獨立 workspace，固定為一個 Interview session 對一個 canonical Job Document。
3. `app/job_authoring` 的 immutable revision 是文件真相；Interview vNext 是對話／Evidence 真相。
4. UI 可以採政府公版的欄位名稱與表格排列，但不能把 OCS 深 JSON 或 `_pending` 恢復成產品真相。
5. 儲存是 server-side canonical commit；browser state 只是尚未送出的短暫編輯緩衝。
6. 沿用現有 Web 技術、設計元件與部分互動外觀；重寫舊 profile、whole-document PATCH 與舊 interview 資料流。
7. 第一個可見切片只呈現已完成的 `job_title + task + output`。Duty、indicator、K/S、職能基準 metadata 隨各自
   canonical operation／contract 完成後加入，不先在 UI 偽造資料。
8. 第一個切片不新增資料表；使用現有 `interview_vnext_sessions` 與
   `job_authoring_documents/revisions/proposals`。

這不是把 vNext 塞回舊 editor，而是「保留前端產品資產，替換資料與權威邊界」。

## 2. 已確認的產品需求

### 2.1 使用者與執行環境

- 使用者是員工，不是職務分析專家。
- 應用程式在員工電腦本機運行，以 browser／localhost 操作。
- 不註冊、不登入、沒有帳號或密碼。
- 不做 company、organization、member、role、ACL、tenant administration、billing 或 cloud deployment。
- OpenRouter API key 是 owner／開發環境設定，不是員工輸入流程。

### 2.2 多文件的正確語意

先前「第一版一名員工當下的一份 JD」應收斂為：

> 一次訪談與編輯一份 JD，但本機可以建立、保存、關閉、重新開啟多份彼此隔離的 JD。

這不是多人或多租戶。它只是一個本機文件庫：

```text
我的職務說明書
├─ AIoT 應用工程師
├─ 生產管理專員
└─ 軟體工程師
```

文件之間不得共享員工 Evidence、conversation、active episode、pending proposal 或 accepted document state。只有公版
reference corpus 可以共用，且仍是唯讀參考。

### 2.3 最終使用畫面

桌面版採固定雙欄：

```text
┌───────────────────────┬────────────────────────────────────┐
│ AI 專業顧問           │ 職務說明書                         │
│                       │                                    │
│ 對話歷史              │ 公版欄位排列                       │
│ 下一個問題            │ 主要職責／任務／產出／指標／K／S  │
│ 回答輸入框            │ 可直接編輯                         │
│                       │ AI 提案可接受／修改／拒絕           │
└───────────────────────┴────────────────────────────────────┘
```

行動版可以切成「訪談／文件」兩個頁籤，但兩者必須讀同一個 workspace snapshot；第一版先把桌面體驗做好。

## 3. 與既有研究／決策的比對

| 既有決策 | 本次結論 | 是否衝突 |
|---|---|---|
| ADR 0020：文件常駐 + 訪談面板 | 保留互動模式，改成 vNext 資料流 | 否 |
| ADR 0015：樂觀並發、不上 CRDT | 保留 CAS／conflict 原則，改用 entity command，不用 whole-document PATCH | 否 |
| ADR 0029：公版欄位全展開、選單是工具 | 保留 UI／參考工具概念，不讓選單成為 canonical truth | 否 |
| ADR 0030：AI 變更要可審 | 保留可審原則；`_pending` 實作已由 ADR 0038 proposal store 取代 | 部分取代舊實作 |
| ADR 0037：員工是文件 authority | direct edit 立即成 draft truth；AI 只能 proposal | 否 |
| ADR 0038：Canonical Authoring Core + JobStateDigest | Local Workspace 只負責組裝，不另建文件真相 | 否 |
| Minimal Authoring Core：一個 session 一份 document | 每個 workspace 仍是一對一；只是本機可有多個 workspace | 否 |
| product-notes：第一版一份 JD | 改為一次只開一份，但可保存多份 | 需要文字校正 |

最重要的解讀是：ADR 0038 的「單一 active draft」是 **每一份 document 只有一個 active head revision**，不是整台電腦
永遠只能存在一筆 document。

## 4. 現有程式盤點

### 4.1 可以直接沿用的後端能力

`app/interview_vnext` 已完成：

- immutable `InterviewState.v3`；
- transcript、QuestionFrame、Evidence、receipt、episode／gap；
- `turn.interpret/2.0.0`；
- `question.select/1.0.0`；
- operation-specific Context Engine；
- durable executor、CAS、recovery、Capture；
- production OpenRouter exact routing；
- GPT-5.4 mini 真 live smoke。

`app/job_authoring` 已完成：

- `JobDocumentDraft.v1`：job title、tasks、outputs；
- immutable `JobDocumentRevision.v1`；
- employee direct add／replace；
- AI add-task proposal；
- employee accept／edit／reject；
- proposal stale；
- deterministic `JobStateDigest`；
- PostgreSQL documents／revisions／proposals。

所以新的 Web route 不得複製 LLM adapter、ContextBuilder、reducer、revision 或 proposal lifecycle。

### 4.2 現有資料庫已能保存多份文件

`job_authoring_documents` 已有：

- `document_id`
- `session_id`
- head revision id／number／hash
- `created_at`
- `updated_at`
- `(tenant_id, session_id)` 唯一鍵
- 依 `updated_at DESC` 排序的 index

只要每份 JD 建立不同 session，就能保存多份 document。第一個切片只缺：

- list documents query；
- local workspace create composition；
- Web/API DTO；
- UI。

不需要為「多份文件」新增第四張 Authoring table。

### 4.3 歷史 `profile_id` 相容債

`interview_vnext_sessions.profile_id` 仍是 required FK，指向早期 `job_profiles`。它已不是 vNext 的產品 authority，但若只為
移除這個欄位就改 `InterviewSession`、`InterviewState`、persistence schema、historical artifacts 與大批測試，會把產品時間
花在非核心 migration。

第一個 Local Workspace 切片採以下收斂：

- server 內部維護一個固定 local compatibility profile anchor；
- 所有本機 vNext sessions 暫時共用這個 anchor；
- Web request／response 永遠不出現 user、tenant 或 profile；
- 文件列表只查 canonical Authoring documents，不查 `job_profiles`；
- job title 來自 canonical `JobDocumentDraft`，不來自 legacy profile；
- legacy `DocumentVersion` 不建立、不讀取、不同步；
- 日後只有在 vNext session schema 因核心需求升版，或正式刪除 legacy profile tables 時，才一起移除此 FK。

這個 anchor 是 storage compatibility，不是隱藏帳號功能：沒有登入、密碼、使用者選擇、權限或 profile API。

## 5. 2026 官方產品模式核對

本次重新核對現行官方資料後，雙欄共編與 revision／human control 方向仍是主流，不是過時做法：

- OpenAI Apps SDK UI guidelines 將 rich editing canvas／multi-step workflow 列為 fullscreen 適用情境，並要求 conversation
  composer 保留在同一 context；inline direct edits 也應持久化。
- ChatGPT Canvas 允許直接編輯、對選取區域要求 AI 修改、檢視差異、版本切換與還原。
- Claude Artifacts 把可持續修改的內容放在主對話右側 dedicated window，支援 in-place edit、版本選擇與多 artifact 管理。
- Microsoft Copilot in Word 採 document canvas + chat；rewrite suggestion 可修改後 replace，AI 內容仍需使用者 review。

這些產品並不證明 Caliburn 應複製其 UI；它們共同支持以下邊界：

1. conversation 與可編輯 artifact 同時可見；
2. 人可以直接改；
3. AI 建議要可定位、可審查；
4. 持久化內容與版本不是 provider chat memory；
5. 一個產品可以管理多個可重開的 artifact／document。

## 6. Target architecture

### 6.1 五個責任層

```text
Local Web UI
  │  renders public-form-shaped view; keeps only unsaved field draft
  ▼
Local Workspace API / composition
  │  hides local scope/profile compatibility; coordinates use cases
  ├───────────────┬─────────────────┬─────────────────────┐
  ▼               ▼                 ▼                     ▼
Interview vNext   Job Authoring     Public Reference      LLM Runtime
conversation /    canonical JD /    official snapshots /  provider /
Evidence / loop   revision/proposal retrieval              conformance
  └───────────────┴─────────────────┴─────────────────────┘
                          │
                          ▼
                  deterministic projectors
                  canvas view / OCS / PDF / XLSX
```

`Local Workspace` 不是新的 domain truth，也不是 agent framework。它只負責：

- 套用固定 local scope；
- 建立／列出／載入 workspace；
- 從 Interview + Authoring 組成 Web view；
- 依序呼叫既有 use cases；
- 把 typed failure 轉成員工可理解的 API result。

### 6.2 每份 workspace 的不變量

1. 一個 `document_id` 對一個 `session_id`。
2. 一個 session 最多一個 Authoring document。
3. document head revision 是目前文件真相。
4. session state 是目前 conversation／Evidence 真相。
5. proposal 必須指向同一 document、base revision 與同一 session Evidence。
6. Context Engine 只能讀正在開啟之 document 的 `JobStateDigest`。
7. 切換文件時不得把 React Query cache、dirty edit、turn request 或 proposal decision 帶到另一份 document。
8. public reference corpus 可共享；retrieval result 不可跨 workspace 持久化成 employee fact。

### 6.3 不採用通用 Graph／Agent workspace

多文件不等於 multi-agent 或 graph orchestration。每份 workspace 仍執行 ADR 0038 的固定流程：

```text
start
  -> planned -> active
  -> append deterministic opening question + open-narrative QuestionFrame

answer
  -> append
  -> turn.interpret
  -> verify + Evidence commit
  -> Agenda/Sufficiency
  -> question.select
  -> consultant turn + QuestionFrame
```

文件切換只改變被載入的 committed state，不改 operation graph。

第一題不能呼叫現行 `question.select/1.0.0`：其 ContextBuilder 明確要求 transcript tail 已有一筆完成 interpretation 的
employee turn。bootstrap 問題固定為 versioned product copy：

> 請先用你自己的話，描述你平常最主要負責的工作，以及完成後通常會產生什麼結果。

它建立 `OPEN_NARRATIVE` QuestionFrame，不預先假設 task、output、K/S 或公版職業分類。員工第一次回答後才進入正式
Context／Interpret／Loop／Question Select。這也避免為沒有 context 的第一句多花一次模型費用。

## 7. Canonical 內部格式與公版 UI

### 7.1 三種 shape 必須分開

| Shape | 用途 | 是否持久化為 truth |
|---|---|---:|
| Canonical Job Model／revision | 產品內部完整職務分析、identity、linkage、provenance | 是 |
| Job Canvas View | 給 Web 顯示的 read projection，欄位排列接近公版 | 否，可重建 |
| OCS／PDF／XLSX export | 特定交付格式 | 否，可重建 |

「公版 UI」代表員工熟悉的欄位與版面，不代表資料庫要儲存一份 OCS JSON。

### 7.2 為何不能讓 OCS 深 JSON 繼續當 live truth

現有 OCS contract 適合交換與匯出，但不適合作新核心：

- 顯示用位置碼和 entity identity 混合；
- K/S 與 task linkage 不完整；
- `_pending` 把 UI review state 放進輸出文件；
- whole-document PATCH 會繞過 entity revision／proposal stale；
- 公版沒有的 custom task／K/S 容易被迫塞進官方 code 欄。

因此新 UI 不直接 `PATCH OcsDocument`。

### 7.3 Job Canvas View 第一版

第一版只投影已存在的 canonical 欄位：

```text
JobCanvasView.v1
  document_id
  revision_id / revision_number / revision_hash
  job_title
  presentation_sections
    - key = ungrouped_tasks
      title = 尚未歸納主要職責
      tasks
        task_id / entity_version / statement / source
        outputs
          output_id / statement / source
```

`ungrouped_tasks` 是 presentation bucket，不可寫回 canonical duty，也不可出現在最終匯出。等 `job.consolidate` 與 Duty
contract 完成後，`JobCanvasView.v2` 才投影真 duty groups。

同理：

- indicator 未完成前不從 output 猜 indicator；
- K/S 未完成前不從工具名稱或模型常識填入；
- 公版 metadata 未選定前不發明職能基準代碼；
- UI 可以顯示尚未形成的欄位區，但必須明確是「待後續分析」，不能偽裝成已保存內容。

### 7.4 UI 編輯如何回到 canonical model

```text
員工修改 task row
  -> UI local draft
  -> EmployeeTaskBundleCommand(action=replace)
  -> CAS against revision + entity_version
  -> new immutable revision
  -> rebuild JobStateDigest
  -> re-project JobCanvasView
```

UI 不送 JSON Patch path，也不送位置碼。它送 stable entity ID 與具體 use-case command。

### 7.5 公版 metadata 的後續位置

職能基準代碼、名稱、所屬類別、職業、行業、級別等應成為 canonical header／reference selection contract，再投影到公版
表頭。第一個 Web slice 不把它們塞進 task/output draft，也不繼續依賴 legacy `selected_ocs_codes` 作 document identity。

## 8. 儲存與續作語意

### 8.1 什麼叫「已儲存」

只有後端成功 commit canonical revision，UI 才能顯示「已儲存」。下列內容分開保存：

| 使用者動作 | 寫入位置 | 是否立即改文件 |
|---|---|---:|
| 員工回答 | Interview transcript，之後形成 Evidence／receipt | 否 |
| 員工直接編輯 | Authoring revision | 是 |
| AI 文件建議 | Authoring proposal | 否 |
| 接受／修改後接受 | proposal decision + Authoring revision | 是 |
| 拒絕 | proposal decision | 否 |

### 8.2 Autosave

第一版沿用現有好用的 autosave UX，但不沿用 whole-document PATCH：

1. onChange 只更新當前欄位／task bundle 的 local draft；
2. 停止輸入約 800ms、blur、Ctrl+S 或切換文件前觸發 flush；
3. 同一個未完成 task edit 合併成一筆 command；
4. 相同內容不送 request；
5. request pending 顯示「儲存中」；
6. commit 成功後以 server 回傳 revision 更新 baseline；
7. 409/conflict 時保留員工尚未儲存的文字，不自動覆蓋；
8. 切換文件前若 flush 失敗，留在原 workspace 並顯示錯誤；
9. browser 關閉且仍 dirty 時使用原生離開警告，不假設 `beforeunload` network 一定成功。

### 8.3 Idempotency

每次 create、answer、direct edit 使用一個由 Web application 產生並在 retry 時重用的 UUID：

- `request_id`：建立 workspace；
- `message_id`：員工回答身分，同一回答永遠重用；
- `processing_id`：這一次 LLM 整理嘗試；HTTP結果不明時重用，已確定終態失敗後由使用者重試產生新值；
- `command_id`：文件直接編輯。

模型不產生這些 ID。重送 exact request 必須回相同結果，不新增 turn 或 revision。

### 8.4 多份文件的列表排序

Local document summary 以最近活動排序：

```text
last_activity_at = max(authoring_document.updated_at, interview_session.updated_at)
```

列表最小顯示：

- job title；
- last activity；
- session status；
- task count；
- pending proposal count；
- document id（只作 route，不顯示給員工）。

第一版不做 tag、folder、search、sharing、archive、trash、quota 或 pagination。文件數量真的形成 UX 問題後再加搜尋。

## 9. 最小 API seam

### 9.1 Client 永遠不傳 scope

下列欄位不可出現在 Web request：

- tenant id；
- user id；
- profile id；
- organization id；
- role／permission。

server 的 Local Workspace composition 套用固定 local scope。

### 9.2 第一個切片端點

```text
GET  /api/v1/local/documents
POST /api/v1/local/documents
GET  /api/v1/local/documents/{document_id}
POST /api/v1/local/documents/{document_id}:start
POST /api/v1/local/documents/{document_id}:answer
POST /api/v1/local/documents/{document_id}/task-edits
```

用途：

- list：列出所有 canonical local documents；
- create：建立 planned Interview session + revision 0；
- get：組合 conversation、save token 與 `JobCanvasView.v1`；
- start：帶一個 `request_id` 建立／續接 bootstrap workflow run，以 deterministic domain command 啟動 session並寫入
  固定第一題與 open-narrative QuestionFrame；不呼叫模型；
- answer：append employee turn，執行 `turn.interpret`，再執行既有 consultant loop；
- task-edits：employee direct add／replace，建立 revision。

不建立 generic `/commands`、generic `/patches` 或任意 operation endpoint。

### 9.3 第二階段才加入

當 `episode.code` 能建立真 task/output proposal 後再加入：

```text
GET  /api/v1/local/documents/{document_id}/proposals
POST /api/v1/local/documents/{document_id}/proposals/{proposal_id}:decide
```

不在沒有 proposal producer 時先做完整 proposal UI。

### 9.4 API response contract

API⇄Web 是 Python⇄TypeScript seam，依 `docs/contract-strategy.md` 應使用 JSON Schema SSOT + codegen。新增一個小型
`packages/local-workspace-contract`，由同一份 schema 產生 API 使用的 Pydantic models與Web使用的TypeScript types。
第一版只建立四個 response contract與四個 request contract：

- `LocalDocumentSummary.v1`
- `LocalWorkspaceView.v1`（內含 `JobCanvasView.v1`）
- `LocalAnswerResult.v1`（`completed | answer_saved_retry_available` + 最新 workspace）
- `LocalError.v1`（小型穩定code、員工可顯示message、retryable；不含內部exception）
- `CreateLocalDocumentRequest.v1`
- `StartLocalDocumentRequest.v1`
- `AnswerLocalDocumentRequest.v1`
- `LocalTaskEditRequest.v1`

不把 ORM row、完整 `InterviewState`、raw Artifact、provider response、tenant/profile 或 OCS deep document 傳到 Web。
這個 contract package 是跨語言資料 seam，不是新service或generic framework。

## 10. 一個 answer request 的完整內部流程

```text
POST :answer(message_id, processing_id, text)
  1. resolve document -> session inside fixed local scope
  2. exact replay? return existing workspace view
  3. append employee turn first
  4. commit transcript
  5. load current InterviewState
  6. execute turn.interpret/2.0.0
  7. verify + commit Evidence/receipt
  8. load canonical JobStateDigest for this document
  9. continue_after_interpretation()
 10. STOP? no question model
 11. otherwise execute question.select/1.0.0
 12. commit consultant turn + QuestionFrame
 13. finalize Capture run
 14. re-read workspace and return LocalWorkspaceView
```

若 provider 在步驟 6 或 11 失敗：

- employee turn 仍已保存；
- response 回 typed `answer_saved_retry_available`；
- UI 顯示回答，不製造假的 consultant reply；
- HTTP結果不明時重送相同 `message_id + processing_id`；
- 已明確終態失敗後，使用者按重試會保留`message_id/text`並產生新的`processing_id`，因此不重複append，但會建立
  一個新的bounded durable processing run。

第一版不 streaming；顯示明確「顧問正在整理」狀態。取得真 latency 後再決定 SSE，不先增加雙通道狀態同步。

## 11. 現有前端的保留／替換

### 11.1 直接保留

- Next.js／React／Tailwind／shadcn 技術基礎；
- `components/ui/*`；
- React Query；
- DnD、popover、tooltip、scroll area 等基礎元件；
- 現有色彩、間距與表格視覺語言。

### 11.2 借用互動／視覺，但重寫 data binding

- `InterviewPanel`：保留 chat bubble、composer、loading presentation；
- `JobDocTable`：保留公版表格與 task/output 編輯手感；
- `PendingMark`：保留「AI 建議有出處且可決定」的視覺概念；
- `ConflictDialog`：保留員工文字優先、不可靜默覆蓋的 UX；
- occupation／task／knowledge pickers：後續作 public-reference tools。

### 11.3 不沿用

- `useProfiles`／anonymous user store；
- `/dashboard` 的使用者／profile 流程；
- `useInterview` 與舊 `/job-profiles/{id}/interview:*`；
- `useDocument` 的整份 OCS PATCH；
- legacy `DocumentVersion`；
- `_pending` 作 proposal store；
- 舊 `InterviewProgress`／phase ladder；
- profile `selected_ocs_codes` 作新文件 identity。

### 11.4 新的 Web route

產品主路徑：

```text
/                       本機文件庫
/documents/{documentId} 對話 + JD canvas
```

`/dashboard` 可暫時 redirect `/`；舊 route／hook 在新 vertical 穩定前先不急著刪，避免同一切片混入 cleanup。

## 12. 不過度設計的明確界線

第一個可見 vertical 不做：

- auth、account、password、organization、ACL；
- Electron／Tauri；
- CRDT、OT、presence、cursor、comment thread；
- cloud sync、share link；
- filesystem watcher 或讓員工挑資料庫路徑；
- generic workflow／graph／agent framework；
- generic command bus；
- 新 Authoring table；
-完整 revision browser／restore；
- archive／trash／hard delete；
- full OCS export；
- duty、indicator、K/S 的假資料或 placeholder persistence；
- streaming；
- background proposal reconciliation；
-所有 UI 狀態排列的測試矩陣。

這些不影響「建立、保存、重開多份 JD；完成一輪真對話；直接編輯 task/output」的成品路徑。

## 13. 最小驗證

### 13.1 後端

只新增高價值案例：

1. 建立兩份 local documents，list 依活動時間回傳且 title 正確；
2. 編輯 document A 後關閉／重讀，revision 與內容保存，document B 不受影響；
3. 同一 create／answer／edit id 重送不新增 document／turn／revision；
4. scripted provider 跑一輪 answer，員工 turn、Evidence receipt、consultant question與QuestionFrame都存在；
5. provider failure 後 employee turn仍存在且可 retry；
6. route response 不含 tenant/user/profile/provider secret。

其中成功案例必須從空 session 呼叫 start，證明固定第一題與 open-narrative frame 可建立、重送不重複，接著才回答；
不得用預先塞好的 employee turn 掩蓋 bootstrap 邊界。

不新增多租戶、ACL、pagination 或 exhaustive provider matrix。

### 13.2 Web

- TypeScript compile；
- lint；
- 一個 autosave state test：dirty -> saving -> saved；
- 一個 conflict test：失敗時不丟 local text；
- 手動走通 create -> start -> answer -> edit -> reload -> reopen。

現有全域測試只跑受影響 safety net，不因 UI slice擴大成新 exhaustive suite。

## 14. 交付順序

```text
Stage 1  Local document list/create/get + minimal canvas projection
Stage 2  Production start/answer route + chat UI
Stage 3  Employee task/output direct edit autosave
Stage 4  episode.code -> task/output AI proposal -> accept/edit/reject UI
Stage 5  duty/indicator operations and canvas fields
Stage 6  public-reference retrieval + document-local K/S
Stage 7  completion assessment + OCS/PDF/XLSX export
```

Stage 1–3 先形成可見的本機測試品。Stage 4–7 才逐步提高 JD 完整度與專業品質。

## 15. 來源

### 15.1 本 repo authority

- [ADR 0015 — optimistic concurrency](../adr/0015-document-save-optimistic-concurrency.md)
- [ADR 0020 — document + interview hybrid UI](../adr/0020-interview-authoring-interaction-model.md)
- [ADR 0029 — editor tools and public-form layout](../adr/0029-editor-menus-three-types-decoupling.md)
- [ADR 0037 — employee authority](../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)
- [ADR 0038 — Context Engine and canonical authoring](../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)
- [Product scope](../product-notes.md)

### 15.2 2026 官方產品資料

- OpenAI, [Apps SDK UI guidelines](https://developers.openai.com/apps-sdk/concepts/ui-guidelines) — persisted direct edits、
  rich editing canvas 與 conversation context。
- OpenAI Help, [ChatGPT Canvas](https://help.openai.com/en/articles/9930697-using-canvas-in-chatgpt) — direct edit、
  targeted suggestion、show changes、version history 與 export。
- Anthropic Help, [Claude Artifacts](https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them) —
  conversation 旁 dedicated artifact、in-place edit、version selector、multiple artifacts。
- Microsoft Support, [Welcome to Copilot in Word](https://support.microsoft.com/en-us/word/welcome-to-copilot-in-word) —
  document canvas + chat、preview/review before applying changes。
- Microsoft Support, [Rewrite text with Copilot in Word](https://support.microsoft.com/en-us/word/copilot-rewrite-text-with-copilot-in-word) —
  edit suggestion then replace／insert／regenerate。

## 16. 建議裁決

採用：

```text
single local operator
+ multiple saved document workspaces
+ one active workspace at a time
+ canonical Authoring Core as truth
+ public-form-shaped Web projection
+ entity command autosave
+ existing frontend visual assets
+ new vNext API/data flow
```

不採用「繼續用 job profile + DocumentVersion + OCS PATCH 當新產品核心」，也不為清除一個歷史 `profile_id` 先重做整套
Interview schema。先完成可見產品，再以真正的職務分析品質資料推動後續 operation。
