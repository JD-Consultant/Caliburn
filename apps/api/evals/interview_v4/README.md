# Interview eval portable foundation（legacy path：`interview_v4`）

這個目錄名稱因歷史原因仍是 `interview_v4`，但內容是 provider/architecture-neutral 的 case、gold、
run、grader 與 immutable artifact 基礎，不是 v4 runtime contract。2026-07-16 起，新 runtime 改採
greenfield vNext；C0 runner 與現有 opt-in capture 只供 v3 黑箱 baseline/failure audit，不再作為新
架構的 stage 或 state 模板。Runner 與 case tools 不介入 production 對話，現有 capture 預設關閉。

設計與 gate 來源：
[`docs/specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md`](../../../../docs/specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md)。
新版架構與 Capture 契約：
[`docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`](../../../../docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md)。

## 目錄

```text
interview_v4/
├─ contracts.py       Pydantic 執行時契約
├─ write_schemas.py   發布 vendor-neutral JSON Schema
├─ loader.py          完整 case cross-file integrity
├─ exporter.py        只讀 session 匯出＋直接識別資訊遮罩
├─ export_candidate.py read-only DB candidate export（Git 外）
├─ inventory_sessions.py 無內容 session inventory
├─ privacy_scan.py    只回報類型／位置的隱私預篩
├─ candidate_metrics.py 不回傳原文的 call/guard/latency 摘要
├─ graders.py         quote／speaker／projection deterministic graders
├─ runner.py          isolated C0 replay 與現行 scribe/harvest adapter
├─ schemas/           case/run 與 runtime capture 的 committed JSON Schema
├─ cases/             development／validation／held_out
└─ reports/           不含敏感原文的結果與稽核報告
```

## 重新產生 schemas

從 `apps/api` 執行：

```powershell
.\.venv\Scripts\python.exe -m evals.interview_v4.write_schemas
```

CI／單元測試會比對 committed schema 與 Pydantic 輸出，防止 drift。

## 載入 case

```python
from evals.interview_v4.loader import load_case

bundle = load_case("evals/interview_v4/cases/development/JD-golden-001")
```

loader 同時檢查：manifest/gold schema、相對路徑、case id、turn 順序、employee quote、
evidence requirement bucket 與 episode boundary。只有 JSON 格式合法但 cross-file 不一致仍會失敗。

## 匯出真實 session

先只讀盤點非敏感中繼資料：

```powershell
$env:DEBUG='false'
.\.venv\Scripts\python.exe -m evals.interview_v4.inventory_sessions --limit 100
```

inventory 不輸出逐字稿、職稱、文件內容、Email 或 profile id；只輸出 session id、數量、
review／guard／document aggregate signals。`initial_snapshot_available=false` 是現行資料模型的
已知限制：document draft 會原列更新，歷史 session 通常沒有訪談開始前的完整文件 snapshot。

`export_session_case` 只呼叫 repo 的 `get/list_*`，不呼叫 create/update/upsert。呼叫者需提供：

- 指定 session id。
- 該 trial 的初始文件與 immutable reference snapshot。
- 不寫入 artifact 的隨機 salt。
- 已知姓名／組織／客戶的 explicit replacements。

一般資料輸出固定為 `privacy.status=redaction_pending_review`、`replay.ready=false`。Regex 只能處理
Email、UUID、URL 與常見台灣電話格式；姓名、罕見事件、商業機密必須人工檢查。禁止把未審
export 直接 commit。

歷史 session 若缺少 turn-zero document/state 或當時的 immutable reference snapshot，必須傳
`None`。exporter 會寫入 `unavailable_fixture.v0.1`，並把匯出當下的資料分開放在
`observed_document.json`／`observed_session_state.json`；禁止把 observed artifact 冒充 replay
起點。可用下列命令以 PostgreSQL read-only transaction 匯出候選，且輸出目錄必須在 Git repo
外：

```powershell
$env:DEBUG='false'
$env:CALIBURN_EVAL_EXPORT_SALT=[guid]::NewGuid().ToString()
.\.venv\Scripts\python.exe -m evals.interview_v4.export_candidate `
  --session-id '<approved-session-uuid>' `
  --case-id 'REAL-INCIDENT-001' `
  --output-root "$env:TEMP\caliburn-interview-eval-staging"
Remove-Item Env:CALIBURN_EVAL_EXPORT_SALT
```

CLI 會從 profile/user rows 建立已知姓名、Email、公司、部門與職稱的 exact replacements，
不把這些原值印到 console。這仍不等於人工去識別審查，也不會把 case 改成
`privacy.status=deidentified`。

### Owner-confirmed test data

只有資料擁有者已確認是測試／合成資料時，才可加入 `--test-data`。CLI 會要求 `TEST-` case id，
允許輸出到 repository，並標記 `privacy.status=synthetic`；它不會自動讓歷史 session 變成
replay-ready：缺 turn-zero fixtures 時仍是 `replay.ready=false`。

```powershell
$env:DEBUG='false'
$env:CALIBURN_EVAL_EXPORT_SALT=[guid]::NewGuid().ToString()
.\.venv\Scripts\python.exe -m evals.interview_v4.export_candidate `
  --session-id '<test-session-uuid>' `
  --case-id 'TEST-SYNTHETIC-SESSION-001' `
  --output-root 'evals/interview_v4/cases/development' `
  --test-data
Remove-Item Env:CALIBURN_EVAL_EXPORT_SALT
```

`TEST-SYNTHETIC-SESSION-001` 已完成 22 個 required evidence labels、三種 inference
bucket、三段 episode boundary 與時間矛盾標註。它可測 quote grounding、否定證據與 gap state；
因缺 turn-zero document/state/reference，禁止拿它跑歷史 C0 replay。

對 Git 外候選執行不顯示命中文字的預篩與品質摘要：

```powershell
.\.venv\Scripts\python.exe -m evals.interview_v4.privacy_scan '<case-dir>'
.\.venv\Scripts\python.exe -m evals.interview_v4.candidate_metrics '<case-dir>'
```

`candidate_metrics` 把 NULL token telemetry 保留為 `recorded_calls=0,total=null`，並依 stage role／
turn 聚合 latency、guard check/reason；不以 0 冒充未記錄。第一份無內容報告在
[`reports/real-candidate-audit-2026-07-15.md`](reports/real-candidate-audit-2026-07-15.md)。

## Opt-in immutable runtime capture

### 1. Migration 與預設狀態

Migration `0009_interview_eval_capture`：

- 擴充 `interview_llm_calls` 的 `stage/provider/requested_model/resolved_model/attempt_count/outcome/
  prompt_hash/tool_schema_hash`；
- 歷史 rows 回填 `stage=role`、`requested_model=model`、`outcome=legacy_unknown`，不把未知結果冒充
  success；
- 新增一個 session 對一個 `interview_eval_captures`；
- 新增 `(capture_id, kind, sequence)` 唯一的 `interview_eval_artifacts`；
- PostgreSQL trigger 拒絕 artifact `UPDATE`；為 retention/privacy deletion 保留 `DELETE` 與 cascade。

```powershell
cd apps/api
.\.venv\Scripts\alembic.exe upgrade head
```

Capture 預設關閉。一般 `interview:start` request 不會建立任何重播 artifact，既有產品流程不需
改 request body。

### 2. 啟用一次 synthetic/eval pilot

啟動 API 前明確設定：

```powershell
$env:INTERVIEW_EVAL_CAPTURE_ENABLED='true'
$env:INTERVIEW_EVAL_CAPTURE_GIT_SHA='<exact git commit sha>'
$env:INTERVIEW_EVAL_CAPTURE_DIRTY_WORKTREE='false' # 必須如實填寫
```

第一個 turn 之前呼叫：

```http
POST /api/job-profiles/{profile_id}/interview:start
Content-Type: application/json

{
  "eval_capture": {
    "enabled": true,
    "consent_policy_version": "synthetic-pilot.v1",
    "locale": "zh-TW"
  }
}
```

Fail-closed 規則：

- server flag 未開：`409 eval_capture_disabled`；
- 未提供 consent policy：`422 eval_capture_consent_policy_required`；
- server 未固定 git SHA：`503 eval_capture_git_sha_unconfigured`；
- session 已有 turns 才要求開 capture：`409 eval_capture_not_turn_zero`；
- turn-zero reference 無法完整取得：`502 eval_reference_snapshot_failed`；
- 同一 capture 重複 start 只回既有 capture，不重寫 initial artifact。

### 3. 實際保存的 artifact

| 時點 | Artifact kind | Sequence | 用途 |
|---|---|---:|---|
| Start | `initial_document` | 0 | 真正的 replay 起點，而非 export-time final draft。 |
| Start | `initial_state` | 0 | session status/phase/focus/counters/human_touched/ledger。 |
| Start | `reference_snapshot` | 0 | 當時選定職類的 tasks/competencies 與 self hash。 |
| Employee turn | `turn_state_before` / `turn_document_before` | employee seq | 模型處理前狀態。 |
| Employee turn | `turn_tool_results` | employee seq | consultant 動態工具名稱、args 與完整 result。 |
| Employee turn | `turn_stage_outputs` | employee seq | curation/consultant/scribe/harvest parsed output 與 guard log。 |
| Employee turn | `turn_state_after` / `turn_document_after` | employee seq | transaction 成功後狀態；state 另含 `derived_phase`。 |
| Employee turn | `turn_trajectory` | employee seq | before/after hashes、按真實語意排序的 call ids、transition reason。 |
| Finish | `session_final_document` / `session_final_state` | 0 | 收尾後快照。 |
| Finish | `session_finish` | 0 | summary、blocker、guard、finish call ids、stop reason。 |

每筆 artifact 寫入時以 canonical JSON 計算 `sha256:`；trajectory 的 before/after hash 必須等於對應
artifact 的 `content_hash`。模型 call 順序明確使用
`curation → consultant → scribe → harvest`，不能拿 DB row 寫入先後猜執行順序。
成功寫完 finish artifacts 後，capture metadata 由 `capturing` 單向轉成 `completed`；重送 finish
直接回傳既有 `session_finish`，不再呼叫模型或覆寫 artifact。

### 4. 目前仍不可宣稱 replay-ready 的缺口

此 slice 解決 turn-zero 與 state/document trajectory，但 LLM port 尚未暴露：

- provider 實際 resolved model；
- provider 內部 retry 與逐 attempt prompt/outcome；
- raw provider response；
- token usage；
- provider exception 發生時的獨立 failure trace。

目前 `attempt_count` 是應用 pass 層重試數，`prompt_hash` 對應 pass 記錄的 prompt；不能解讀為
provider 的每次嘗試。整個 turn 使用同一 DB transaction，若 provider exception 使 request 失敗，
該 transaction 內的 capture 也會 rollback。2026-07-16 決定不再為 v3 補這個 provider-level
instrumentation slice；`resolved_model/tokens/raw artifact/attempt traces`、failure outbox 與 open-string
stage taxonomy 直接在 vNext Capture 實作。現有 v3 capture 仍固定 `replay_ready=false`，除非未來有
一個獨立、經核准且不改 v3 runtime 語意的 baseline capture 工作包。

## 執行 C0 replay

```python
from evals.interview_v4.runner import CurrentC0Processor, SnapshotKnowledge, run_c0_case

knowledge = SnapshotKnowledge(snapshot)
processor = CurrentC0Processor(
    llm=llm,
    knowledge=knowledge,
    header_codes=set(snapshot["header_codes"]),
    ref_ocs_codes=tuple(snapshot["selected_ocs_codes"]),
    reference_snapshot_id=knowledge.snapshot_id,
)
artifact_dir = await run_c0_case(
    case_dir,
    processor=processor,
    output_root=temporary_artifact_root,
    git_sha=current_commit,
    dirty_worktree=is_dirty,
    trial_index=1,
)
```

runner 規則：

- `replay.ready=false` 預設拒跑。
- 不使用 profile/session DB；每次從 fixtures deep copy。
- 每次產生新 `run_id`，拒絕覆寫既有 artifact。
- timeout／parse failure／limitations 不得從 artifact 消失。
- v0.1 的現行 C0 adapter尚無 raw provider response/token 回傳，因此 run 必須明列 limitation，
  不能假裝 trace 已完整。

## Provisional legacy case

`JD-golden-001` 只是舊 golden 的格式遷移樣本。它刻意：

- `annotation.status=draft`。
- `replay.ready=false`。
- 同時標記「100% 完成」與「趕工抽樣」並保留 unresolved gap。
- 不提供唯一 indicator/JD projection gold。

補齊原始 initial fixture、reference snapshot、episode boundary 與 domain adjudication 前，不能拿它
決定 C1 晉級。
