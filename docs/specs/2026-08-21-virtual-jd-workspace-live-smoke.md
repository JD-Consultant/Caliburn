# Virtual JD workspace live smoke evidence

- 日期：2026-08-22
- 狀態：**partial；exact profile 仍有未解 blocker，不是 live pass**
- 範圍：current Deep Agents virtual JD workspace、deterministic candidate check／repair、pending-only publication；不接 RAG／Reference、不做能力級別／A、不啟用 auto mode 或正式 eval。

## 1. Provider schema 修正

第一次 exact provider smoke 到達 OpenAI 後，strict response schema 因 `OutputEvidenceReference.occurrence` 是 optional 而被 `invalid_json_schema` 拒絕。這是 provider wire 與 OpenAI strict required-field 規則的契約錯位，不是模型品質結果。

最小修正如下：

- provider-facing `occurrence` 改為 required strict integer；唯一 quote 填 `0`，重複 quote 填 1-based occurrence；
- `AnalysisBasisTable` 將 provider sentinel `0` 映射回 workspace `WorkspaceEvidenceReference.occurrence=None`，正整數原樣保留；
- agent prompt 明示 sentinel 規則；
- fixtures、schema contract、mapper 與 runtime regression 一併更新。

這保留模型不知道 source UUID／offset 的邊界，也沒有新增 provider-specific abstraction。focused API regression 已驗證 schema requiredness、sentinel mapping 與既有 evidence resolver；Web integration coverage 也維持綠燈。

## 2. Exact profile live result

runner 直接以 `apps/api/.env` 的 dotenv values 載入 owner key/base URL，並在 runner 內固定 disposable PostgreSQL：

```text
postgresql+asyncpg://postgres:password@localhost:5432/caliburn_reviewed
postgresql://postgres:password@localhost:5432/caliburn_reviewed
```

Profile 固定為：

- requested model：`openai/gpt-5.6-luna`
- provider：`OpenAI`
- fallback：disabled
- reasoning：`max`
- existing model-call policy：8 calls、2 lookup waves
- model-facing Tools：`ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`、`check_candidate_document`

schema 修正後，smoke 已實際走到 GPT-5.6 Luna，並確認 exact seven-Tool surface 已 bound/exposed；實際 Tool calls 只觀察到 `ls` 與 `read_file`。Luna 反覆讀取這兩個 lookup，跨過既定兩波 lookup limit，production middleware 回傳 `LookupWaveLimitExceeded` 並 fail closed。這是 exact profile 的 unresolved live blocker；不得用提高 budget、換 model/provider、fallback 或放寬 lookup policy 把它改寫成 pass。

runner 的安全摘要不輸出 key、headers、prompt、員工完整 payload 或 Tool payload。每次失敗都在 `finally` 只刪本輪 document；controller evidence 顯示 disposable document 已刪除，相關 persistence counts 回到零。

## 3. Reproduction commands

在同一 worktree、API dependency 已就緒且 local PostgreSQL `caliburn_reviewed` 可用時：

```powershell
cd S:\caliburn\.worktrees\langgraph-consultant-runtime\apps\api
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
$env:PYTHONPATH='S:\caliburn\.worktrees\langgraph-consultant-runtime\apps\api'
uv run python ..\..\.superpowers\sdd\2026-08-21-deep-agents-virtual-jd-workspace-plan\task-8-live-smoke.py
```

runner 直接讀取 `S:\caliburn\apps\api\.env`，不把 ignored env 複製到 worktree；DB/profile 的固定值由 runner 控制。live output 只接受 `passed` 或安全 provider/runtime failure；本次結果應解讀為上節的 lookup-wave blocker。

## 4. Deterministic browser authority review

browser QA 是另一個 local fixture evidence，不是上述 stochastic provider smoke 的替代品。controller 使用 plan-local ignored `task-8-browser-fixture.py` 建立一份 pending review document，驗證下列 employee-visible semantic decisions：

- accept job title；
- edit-and-accept work description；
- reject Duty with a reason；
- defer Task；
- leave one O pending。

reload 後各 decision status 保留；API snapshot 顯示 approved 只含員工接受的 job title／work description，單一 O 仍 pending，Duty／Task 仍為原核准內容，沒有其他 O/P/K/S 被暗中寫入。畫面沒有 `/candidate/`、`write_file`、`edit_file` 或 `check_candidate_document`。fixture document 已精確刪除，local servers 已停止。

這證明的是 deterministic employee authority／semantic review surface；它不證明 exact provider live run 已通過。

## 5. Relevant gates

```text
cd apps/api
uv run pytest tests/test_consultant_model_output.py tests/test_consultant_run_service.py tests/test_consultant_workspace_resources.py tests/test_consultant_candidate_loop.py -q

cd apps/web
npm run test
npx tsc --noEmit
npm run lint
```

所有 PostgreSQL gate 都必須明確設定 disposable `TEST_DATABASE_URL`，且 cleanup 後查核 `consultant_documents`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`store`；未設定 DB 的 skipped tests 不可被報成 PostgreSQL pass。
