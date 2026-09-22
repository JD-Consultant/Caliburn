# 本機多文件 JD Workspace 最小可見垂直切片實作計畫

- 狀態：Superseded before implementation（2026-07-24；禁止照此計畫實作）
- 日期：2026-07-23
- 決策：[ADR 0039](../adr/0039-local-multi-document-canonical-public-form-workspace.md)
- 研究：
  [本機多文件與公版 UI 研究](../specs/2026-07-23-local-multi-document-jd-workspace-and-public-form-ui-research.md)
- 前置：Authoring Core、`turn.interpret/2.0.0`、`question.select/1.0.0`、production OpenRouter loop 已完成

> **停止執行原因**
>
> Owner 已決定第一個成品不做 revision history。本文 API、autosave、CAS、DTO 與測試大量綁定
> `revision_id/revision_hash/entity_version`，不能機械刪欄位後繼續實作。後續應依
> [current relational storage authority](../specs/2026-07-24-job-authoring-v2-relational-storage-research.md)
> 另寫更小的 localhost 可見切片計畫。本文僅保留作歷史研究，不是 implementation authority。

## 1. 這一步要交付什麼

完成第一個員工可在 localhost 看見並操作的 vNext 產品路徑：

```text
文件庫建立兩份 JD
  -> 開啟其中一份
  -> 看見公版樣式的 job title/task/output canvas
  -> 啟動 AI 顧問並回答一輪
  -> 顧問理解回答後提出下一題
  -> 員工直接新增／修改 task/output
  -> 顯示已儲存
  -> reload／切到另一份再切回，內容與對話仍在
```

這一輪不承諾 AI 已能自動產生 task proposal；那是下一個 `episode.code` 切片。

## 2. 明確不做

- 登入、帳號、密碼、organization、member、ACL、SaaS；
- 新資料表或 migration 0012；
- 刪除／封存／分享／搜尋／folder；
- Electron／Tauri；
- streaming；
- duty、indicator、K/S、公版 metadata、完整 export；
- `episode.code` 或新的 LLM operation；
- proposal decision UI；
- generic command bus、Graph／agent framework；
- 清除全部 legacy API／Web code；
- exhaustive UI/provider/error matrix。

## 3. 契約

### 3.1 `LocalDocumentSummary.v1`

```text
schema_version = local_document_summary.v1
document_id
job_title
last_activity_at
session_status
revision_number
task_count
pending_proposal_count
```

不包含 tenant、user、profile、session_id、revision hash或provider資料。

### 3.2 `LocalWorkspaceView.v1`

```text
schema_version = local_workspace_view.v1
document_id
session:
  status
  can_answer
conversation:
  turn_id
  sequence
  role = employee | consultant
  text
  occurred_at
document:
  schema_version = job_canvas_view.v1
  revision_id
  revision_number
  revision_hash
  job_title
  sections:
    key = ungrouped_tasks
    title = 尚未歸納主要職責
    tasks:
      task_id
      entity_version
      statement
      source_kind
      outputs:
        output_id
        statement
        source_kind
save:
  pending_proposal_count
  stale_proposal_count
```

`revision_hash` 是 UI autosave 的 opaque precondition，不顯示給員工。不要加入 generic metadata map、
`dict[str, Any]` 或 raw domain JSON。

### 3.3 Action／error response

```text
LocalAnswerResult.v1
  outcome: completed | answer_saved_retry_available
  workspace: LocalWorkspaceView.v1
  message: string | null
  retryable: boolean

LocalError.v1
  code:
    local_document_not_found
    local_invalid_session_state
    local_idempotency_conflict
    local_revision_conflict
    local_edit_invalid
    local_persisted_corruption
  message: non-blank employee-safe text
  retryable: boolean
```

`answer_saved_retry_available` 是成功傳輸的產品結果，不是 generic HTTP error；它保證 employee turn 已保存。其他錯誤固定
映射：document not found→404；session／idempotency conflict→409；Authoring revision、task-not-found與task-version conflict
收斂成`local_revision_conflict`→409；output scope／capacity等不合法編輯收斂成`local_edit_invalid`→422；request schema由
FastAPI既有422處理；persisted corruption→500。`no_semantic_change`視為成功，直接回最新workspace，不顯示錯誤。
`message`不得包含provider body、stack、tenant/profile、SQL或internal hash；revision hash只存在workspace的opaque save
precondition。

### 3.4 Requests

```text
CreateLocalDocumentRequest.v1
  request_id: UUID
  job_title: non-blank <= 256

AnswerLocalDocumentRequest.v1
  message_id: UUID
  processing_id: UUID
  text: non-blank bounded employee text

StartLocalDocumentRequest.v1
  request_id: UUID

LocalTaskEditRequest.v1
  command_id: UUID
  expected_revision_id: UUID
  expected_revision_hash: sha256
  action: add | replace
  target_task_id: UUID | null
  expected_target_version: int | null
  statement
  outputs[{output_id|null, statement}]
```

### 3.5 Cross-language guard

依 `docs/contract-strategy.md` 的非Python consumer規則，新增：

```text
packages/local-workspace-contract/
  package.json
  pyproject.toml
  schema/local-workspace.schema.json
  src/local_workspace_contract/models.py
  types/local-workspace.ts
  scripts/check-codegen.*
```

`schema/local-workspace.schema.json` 是單一來源，包含本節所有request／response definitions；Pydantic與TypeScript都由它
生成。沿用 `packages/ocs-contract` 已驗證的 datamodel-code-generator + json-schema-to-typescript 作法、disable timestamp、
regen + diff guard，不手寫第二份 interface。

這個package是小型內部contract，不是新service。API `pyproject.toml`加editable path dependency；Web
`package.json`加workspace dependency。除既有codegen工具外不引入新的runtime dependency。

## 4. Backend modules

### 4.1 新增

```text
apps/api/app/local_workspace/
  __init__.py
  projection.py
  service.py

apps/api/app/api/routes/local_documents.py

packages/local-workspace-contract/
  schema/local-workspace.schema.json
  generated Python/TypeScript contract
```

`local_workspace` 可 import `interview_vnext` 與 `job_authoring` application APIs；反向 import 禁止。
route與projection使用generated contract，domain modules不得import Web type。

### 4.2 修改

```text
apps/api/app/job_authoring/ports.py
apps/api/app/job_authoring/postgres.py
apps/api/app/job_authoring/service.py
apps/api/app/api/router.py
apps/api/tests/test_local_workspace_postgres.py
```

只新增 document list query/use case，不改既有 revision／proposal transition。

## 5. Local scope 與 compatibility anchor

在 `local_workspace/service.py` 定義 server-only constants：

```text
LOCAL_TENANT_ID = 00000000-0000-0000-0000-000000000001
LOCAL_USER_ID   = 00000000-0000-0000-0000-000000000002
LOCAL_PROFILE_ID= 00000000-0000-0000-0000-000000000003
```

建立第一份文件前，以 idempotent insert 確保 legacy `users/job_profiles` anchor存在：

- email：`local@caliburn.invalid`
- name：`Caliburn Local`
- company：null
- profile job title只寫固定 `Local compatibility anchor`，不得隨 document 改變
- 不建立 `DocumentVersion`

所有 local sessions 暫時使用 `LOCAL_PROFILE_ID`；每份真正 title只在 canonical Authoring revision。

硬性規則：

- route不接受scope IDs；
- response不輸出scope IDs；
- list不查 profile title；
- 不呼叫舊 user/profile route或service；
- 不新增登入或「目前使用者」概念。

## 6. Slice W1：文件 list/create/get

### 6.1 Repository

新增：

```python
documents.list_all(tenant_id) -> tuple[AuthoringDocumentRecord, ...]
```

repository 以 `updated_at DESC, document_id` 回傳 deterministic 初始順序。Local Workspace service再 hydrate 每份 head
revision與對應 Interview session，計算
`last_activity_at = max(document.updated_at, session.updated_at)`，最後以
`last_activity_at DESC, document_id` 重排並取得title/task count。本機文件量小，第一版不分頁、不另建read-model table，
也不為這個列表增加跨domain join repository。

### 6.2 Create

`create_local_document(request)`：

1.套用 fixed local scope；
2.以`request_id`作`session_id`；existing session + document時比較canonical job title，相同則exact replay回原document，
  不同則`idempotency_conflict`；
3. ensure compatibility anchor；
4. session不存在時以server UTC建立：
  - `profile_id = LOCAL_PROFILE_ID`
  - `workflow_version = 1.0.0`
  - `reference_snapshot_id = local-reference-unselected`
  - `status = planned`
5. `CreateJobDocumentCommand.command_id = uuid5(request_id, "local/create-job-document")`；
  command `occurred_at`固定使用session `created_at`，讓orphan-session recovery仍產相同command hash；
6. 保存 session；
7. 呼叫既有 `create_job_document()`建立revision 0；
8. 回 `LocalWorkspaceView`。

若 session已建但authoring建立失敗，exact replay必須從session恢復並補建document，不再建第二個session。不要為此新增
distributed transaction或outbox。

### 6.3 Get/list

- `GET /local/documents`回 summaries；
- `GET /local/documents/{id}`只允許fixed scope內document；
- 查無回404；
- persisted closure錯誤回500 typed local corruption，不以空文件掩蓋；
- list不顯示沒有Authoring document的orphan session。

### 6.4 W1 tests

一個real-PG test：

- create A/B；
- list B/A order；
- get A/B title與空canvas；
- scope欄位不在serialized response；
- replay create不新增row。

W1 green才commit：

```text
feat(local): expose saved job document workspaces
```

## 7. Slice W2：start／answer production composition

### 7.1 每次 start／answer action 的 durable run

start與answer都先沿用既有`capture.create_run()`建立run：

```text
start run_id  = uuid5(start.request_id, "local/start/run")
answer run_id = uuid5(answer.processing_id, "local/answer/run")
taxonomy      = INTERVIEW_VNEXT_EXECUTION_V2
workflow      = session.workflow_version
```

- run不存在時`started_at = server UTC now`；
- run已存在時載回persisted started_at，不以新的now重建identity；
- snapshot artifact、started event、terminal event、manifest artifact ID都由run_id +固定literal做UUIDv5；
-成功以`RunStatus.COMPLETED` finalize；
-operation終態失敗以`RunStatus.FAILED` finalize；
-completed roots至少包含每個operation的response artifact；failed roots包含failure artifact／checkpoint authority ref；
-finalize與manifest沿用既有Capture，不新增第二套log。

start的run負責封存version-0 state並承載bootstrap domain commands，沒有model request／result artifact；它不是假
provider call。`processing_id`是一次bounded answer processing run的身分，不是provider attempt。HTTP結果不明時重送
同一ID；只有收到`*_retry_available`後，員工明確重試才產生新的processing ID。

### 7.2 Start

`POST /local/documents/{id}:start(StartLocalDocumentRequest)`不呼叫模型。現行`question.select/1.0.0`要求transcript
tail已有一筆完成interpretation的employee turn，因此不能拿來產生空session的第一題。

固定bootstrap copy：

```text
INITIAL_OPENING_QUESTION_V1 =
  請先用你自己的話，描述你平常最主要負責的工作，以及完成後通常會產生什麼結果。
```

執行順序：

1. 讀取session；terminal拒絕，active且已有consultant turn則直接回最新view，不建立空run；
2. create／resume `run_id = uuid5(request_id, "local/start/run")`；這一步必須在任何state command前完成，讓既有
   `capture.create_run()`封存initial-state snapshot；
3. planned時以run persisted `started_at`執行`TransitionSessionCommand`：
   - `command_id = uuid5(session_id, "local/session/activate/v1")`
   - 成功後session `updated_at`就是唯一的activation timestamp；
4. 重新讀session；若仍沒有consultant turn，以activation timestamp建立：
   - `turn_id = uuid5(session_id, "local/initial-question/turn/v1")`
   - `command_id = uuid5(session_id, "local/initial-question/append/v1")`
   - `client_turn_id = "local/initial-question/v1"`
   - `sequence = 1`、`previous_turn_id = null`
   - `QuestionMode.OPEN_NARRATIVE`、targets空集合；
5. 經既有`apply_durable_command()`保存consultant turn與QuestionFrame；
6. 將本run內新寫入的command／reduction artifacts納入manifest roots並finalize completed；
7. 回最新workspace view。

這兩個domain command本身已有command artifact、reduction artifact、event與CAS，不新增model operation。若transition成功、
append前程序中斷，同一`request_id`先走既有run recovery；已明確terminal failure時用新`request_id`建立新的bootstrap
run，從active session補完固定第一題。若append成功但HTTP response遺失，重送同一request只回現況。已由舊run提交、
本run僅replay的command artifact不得偽裝成本run root。第一題不產生Evidence，也不預先假設task/output/K/S；員工回答
後才進入正式LLM processing。

### 7.3 Answer

`POST :answer`必須按研究§10順序：

1. create／resume`processing_id`對應的durable run；
2. `message_id`就是append employee turn的command id；same id + different text回`idempotency_conflict`；
3. append employee turn先commit；
4. `turn.interpret` operation id固定為`uuid5(processing_id, "local/turn-interpret")`；
5. execute existing `turn.interpret/2.0.0`；
6. control operation id固定為`uuid5(processing_id, "local/loop-control")`；
7. question operation id固定為`uuid5(processing_id, "local/question-select")`；
8.讀同document `JobStateDigest`；
9. `continue_after_interpretation()`；
10. STOP不呼叫question model；
11. finalize run；
12.成功回最新view。

不得把provider call放進DB transaction，不得複製OpenRouter adapter或ContextBuilder。

同一`message_id`已有成功receipt時，即使client帶新`processing_id`也直接回最新view，不重跑interpretation。相同message尚無
receipt且前一processing run失敗時，新`processing_id`可重新處理同一個tail employee turn。

### 7.4 Failure response

定義兩種產品結果：

```text
completed
answer_saved_retry_available
```

第二種必須帶最新workspace view與簡短可顯示訊息，但不洩漏provider body、stack、API key或內部hash。HTTP可維持成功傳輸
回typed outcome，避免UI因通用500看不到已保存的employee turn。

### 7.5 W2 tests

只做兩個高價值整合：

1. start寫入固定第一題與open-narrative frame，重送不新增turn／不呼叫provider；接著以scripted provider回答一輪，
   驗證employee turn、receipt、下一個consultant turn與active frame；
2. provider終態失敗後employee turn仍在；same message + new processing id可重試且不重複append。

production provider既有suite不重跑新matrix。

W2 green才commit：

```text
feat(local): run durable consultant turns for local documents
```

## 8. Slice W3：Web文件庫與雙欄workspace

### 8.1 新增／重寫

```text
apps/web/src/app/page.tsx
apps/web/src/app/documents/[id]/page.tsx
apps/web/src/features/local-documents/api.ts
apps/web/src/features/local-documents/hooks.ts
apps/web/src/features/workspace/ConversationPane.tsx
apps/web/src/features/workspace/JobCanvas.tsx
apps/web/src/features/workspace/SaveIndicator.tsx
```

可按現有目錄風格調整檔名，但不得把新資料流塞回`useProfiles/useInterview/useDocument`。
Web types只可從`@caliburn/local-workspace-contract`匯入。

### 8.2 文件庫

- `/`直接列出saved documents；
- top CTA「新增職務說明書」；
- create表單第一版只問職務名稱；
- click進`/documents/{id}`；
- 空狀態直接說明「建立後由AI顧問逐步訪談」；
- 無user/profile/dashboard文字。

### 8.3 Workspace

- desktop 40% chat／60% canvas；
- mobile兩個tab；
- header有返回文件庫、job title、save indicator；
-沒有profile intake、occupation gate或舊progress ladder；
- session planned時顯示「開始訪談」；
- active時顯示conversation與input；
- request期間input disabled但已送文字立即顯示；
- typed retry outcome顯示「回答已保存，重新整理失敗，可重試」。

### 8.4 Canvas

新`JobCanvas`借用現有表格視覺，不讓`JobDocTable`接新domain後繼續操作OCS deep JSON。第一版欄位：

-職務名稱（建立後唯讀；更名use case尚未存在，不以task edit冒充）；
-工作任務；
-工作產出；
-來源簡短badge；
-新增task；
-修改task／outputs。

區段標題使用「尚未歸納主要職責」，明確是畫面分組，不輸出為canonical duty。

## 9. Slice W4：entity autosave

### 9.1 Hook

新增`useTaskAutosave(documentId)`：

- query key含document id；
- per-task local draft；
- 800ms debounce；
- blur／Ctrl+S／document navigation可flush；
- exact baseline no-op；
-同一flight期間後續輸入保持dirty，不把未送內容誤標saved；
-409保存local draft並顯示conflict；
-非409顯示error與retry；
-成功以server workspace view更新revision baseline。

不得把整個canvas serialize後PATCH。

### 9.2 Conflict

第一版只提供：

-「載入已儲存版本」；
-「保留我的文字並重新套用」。

重新套用要以最新revision重新送同一task bundle，不能force overwrite或關掉CAS。

### 9.3 W3/W4驗證

```text
npm run test -- <focused files>
npx tsc --noEmit
npm run lint
```

新增最多兩個autosave tests，不做component snapshot矩陣。

W3/W4可分兩個commit，但每個commit都需typecheck：

```text
feat(web): open local job document workspaces
feat(web): autosave canonical task bundles
```

## 10. Final product smoke

### 10.1 No-network

- focused local workspace real-PG tests；
- affected Authoring focused；
- affected turn/question loop focused；
- Web typecheck/lint/focused tests；
- schema writer zero diff；
- Alembic仍0011。

不要求為這個UI切片重新跑所有eval trial或新增provider error matrix。

### 10.2 Paid live

owner現有低額key下只跑一條：

1. create document；
2. start；
3. answer一輪；
4.確認direct exact route、local verifier與DB commit；
5.reload Web確認conversation與document仍在。

記錄model、endpoint、tokens、cost與結果，不記key。最高預期花費遠低於US$0.10；若異常重試不得無界循環。

### 10.3 手動UX

-建立兩份；
-切換不串資料；
-直接編task/output；
-看到dirty/saving/saved；
-reload保存；
-關閉再開保存；
-provider失敗時回答不消失；
-Web沒有登入、profile、tenant或設定host/port畫面。

## 11. Docs／status

實作同commit更新：

- `docs/design/local-jd-workspace.md`：click -> request -> state -> response living design；
- `apps/api/README.md`；
- `apps/web/README.md`；
- `apps/api/app/interview_vnext/README.md`；
- `apps/api/app/job_authoring/AGENTS.md`（若邊界改動）；
- 本計畫實際commit／tests／live結果。

## 12. 停線條件

遇到以下任一情況停止，不要猜：

-必須改 Evidence／InterviewState schema 才能顯示Web；
-必須新增通用workspace／ACL／user系統；
-必須讓legacy DocumentVersion或OCS JSON成canonical truth；
-必須由Web傳tenant/profile；
-必須複製provider adapter或ContextBuilder；
-answer失敗會丟掉employee turn；
-direct edit不能保留CAS；
-JobCanvas需要偽造duty/indicator/K/S才能render；
-需要migration 0012；
-API key進response/log/git；
-為通過測試而跳過real-PG product vertical。

## 13. Definition of Done

-本機可保存並重開至少兩份JD；
-每份conversation/Evidence/revision互相隔離；
-一輪production consultant對話可在localhost完成；
-task/output直接編輯會durable save；
-UI使用公版樣式但不儲存OCS deep JSON；
-沒有帳號、登入、SaaS或新migration；
-既有Context Engine、provider、Authoring Core只被compose，未重建；
-Web contract由schema生成；
-focused safety net、real-PG vertical、Web typecheck/lint全綠；
-一條低成本live產品smoke通過後，才進`episode.code` proposal切片。
