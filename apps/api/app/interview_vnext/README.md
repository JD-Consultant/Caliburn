# Interview AI vNext（隔離開發中）

本 package 是 ADR 0034 的 greenfield 實作區。目前已完成 **V0 + V1 domain foundation**，沒有 route、DB migration、provider call，也沒有被 production composition root import。現行使用者流量仍走 `app/interview/` v3。

權威文件：

- 目標架構：[`../../../../docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`](../../../../docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md)
- 實作順序：[`../../../../docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md`](../../../../docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md)
- 決策：[`../../../../docs/adr/0034-interview-ai-vnext-greenfield-evidence-workflow.md`](../../../../docs/adr/0034-interview-ai-vnext-greenfield-evidence-workflow.md)
- package 禁令：[`AGENTS.md`](AGENTS.md)

## 目前的程式邊界

```text
domain/                 已實作：純 Pydantic contracts、validators、reducers、events、schemas
application/            空殼：尚未實作 workflow/use case
llm/ providers/         空殼：尚未選模型、SDK 或 prompt
knowledge/ persistence/ 空殼：尚未接 reference snapshot 或資料庫
projection/             空殼：尚未投影到現有 OCS/Web contract
observability/          空殼：Capture vNext 留到 V2
```

`domain/` 只能依賴 Python 標準庫、Pydantic 和同一 domain package。AST dependency test 會阻止 vNext import v3 internals，也會阻止 domain 偷接 FastAPI、ORM 或 provider SDK。

## V1 已落實的契約

### Aggregate 與 authority boundary

- `InterviewState` 是 immutable materialized aggregate；nested collection 使用 tuple。
- `InterviewSession.state_version` 是 optimistic concurrency token。
- `processed_command_ids` 是本階段的 deterministic idempotency guard；持久化後會由 repository transaction／idempotency record 承接。
- LLM 未來只能產生 proposal。只有 reducer 可以接受 proposal、驗證並產生新 state。
- employee evidence、inference、reference URN、human review 是不同 authority channel，不混成一段摘要。
- `accepted`／`rejected` candidate 必須有 human `ReviewDecision`；模型不得覆寫人工裁決。

### 時間與文字定位

- 所有 domain timestamp 必須是 aware UTC（offset `+00:00`）；不接受只帶任意時區的時間。
- command 時間不得早於 materialized state 的 `updated_at`，避免 replay 後時間倒退。
- `TranscriptTurn` 保留逐字內容；`received_at >= occurred_at`。
- `QuoteSpan.start/end` 是 Python／Unicode **code point**、左閉右開 `[start, end)`，欄位 `unit` 固定為 `unicode_code_point`。JavaScript UI 若顯示 span，必須轉換 UTF-16 index，不可直接當 JS string offset。
- exact quote 必須逐字等於 span；normalized quote 只允許已版本化的 `quote_nfkc_ws.v1`（NFKC + whitespace collapse）。normalized quote 仍保留原 transcript span，不改寫來源。

### Evidence 與 projection gate

- 新 evidence 必須引用既有 employee turn；consultant 問句不能成為員工事實。
- correction 建立新 evidence，舊 evidence 改 `superseded`，歷史不刪除。
- supersede link 必須雙向、target 必須 active、同一批不得重複取代、整體 lineage 不得成環。
- episode↔evidence、episode↔gap、candidate↔review 都必須雙向閉合；只存單邊 ID 會被 aggregate validator 拒絕。
- projected candidate 至少要有 active、current、affirmed、employee/team evidence，ownership 必須是 `owner|shared|assists`。
- ability／attitude 在 `verified|projected` 前至少需要兩個 episode 的 evidence。
- behavior indicator 的顯式數字門檻必須有 employee evidence、approved policy 或 human source；employee threshold evidence 必須同時存在於 candidate lineage。

### Episode lifecycle

| Current | 可到達 | Hard gate |
|---|---|---|
| `open` | `closing` | 一個 session 同時只能有一個 non-closed episode；opening turn 必須是 transcript tail |
| `closing` | `closed` | 不得殘留 `open|asked` gap；`closed_turn_id` 必須存在且不早於 opening turn |
| `closed` | 無 | 不再接受該 episode 的 evidence 或 gap mutation |

Evidence 只能掛到當前 active、未關閉且 source turn 不早於 opening turn 的 episode。這個限制避免 delayed extractor 把新回合內容誤寫回舊 episode。

### Gap lifecycle 與「有回答」的定義

| Current | 可到達 | 必要來源 |
|---|---|---|
| `open` | `asked` | consultant turn；`sensitivity=prohibited` 永遠不可問 |
| `open` | `not_applicable` | employee turn + active resolution evidence + reason |
| `open` | `deferred` | unresolved reason |
| `asked` | `answered` | employee turn + 至少一個同回合 active resolution evidence |
| `asked` | `declined` | employee turn + reason；之後不可重問 |
| `asked` | `not_applicable|deferred` | 對應 evidence/reason |
| `deferred` | `asked` | 只有 deferred 可在 episode 仍 open 時重新追問 |
| `answered|declined|not_applicable` | 無 | terminal |

`answered` 不是「使用者有傳訊息」；必須是該 employee turn 已產生並通過 quote verifier 的 Evidence。若 resolution evidence 後續被撤回，reducer 會把 gap 降為 `deferred`，清除 resolution evidence closure，留下原 resolution turn 與 deterministic reason。

### Evidence correction 與 withdrawal

- replacement evidence 必須來自比 target 更新的 employee turn；`supersedes`／`superseded_by` 雙向保存且不可成環。
- withdrawal 必須引用比原陳述更新的 employee turn及非空 reason；原 evidence 保留但改為 `withdrawn`。
- withdrawal 會在同一 atomic reducer 中做 deterministic invalidation：
  - 使用它回答的 gap → `deferred`；
  - 已無 active supporting evidence 或 decision evidence 被撤回的 inference → `insufficient`；
  - 引用它的 model-owned `draft|verified|projected` candidate → `insufficient`；
  - human `accepted|rejected` candidate 不被模型 reducer 改寫，但 projector 仍必須重新檢查 evidence closure。

### Inference lifecycle 與員工決策

- `ApplyInferenceProposalsCommand` 只接受 `llm|rule` 的 `candidate|insufficient` proposal；引用 evidence 必須存在且 active。
- 同一 inference ID 可在 employee decision 前 revision；revision 必須保留既有 lineage。
- 語意被新推論取代時使用 `SupersedeInferenceCommand`：舊 inference 轉 `superseded`、新 inference 使用新 ID，雙向 lineage 不可成環。
- `confirmed_by_employee|rejected` 只能由 `DecideInferenceCommand` 建立，且 `decision_evidence_id` 必須是 active employee evidence。之後模型 proposal 不得覆寫。
- prompt 檔名不是版本；Inference 保存 `operation_definition_hash=sha256:<64 hex>`，V2 operation registry 必須以 canonical content 產生此值。

### Candidate 與 human review lifecycle

```text
draft -> verified -> projected -> accepted|rejected   (最後一步只能 human review)
  │         │          │
  └─────────┴──────────┴-> insufficient|conflicted -> draft（補 evidence 後重驗）
```

- proposal 只可建立／revision `draft|insufficient|conflicted`；不能直接聲稱 verified/projected/accepted。
- `verified|projected` 只能由 deterministic verifier transition，並重跑 current/polarity/ownership、ability cross-episode 與 quantitative source gate。
- rejected/superseded inference 會阻止 verify/project；若已 projected，reducer 會先降成 `conflicted`。
- review 只接受 `finishing|completed` session 中尚未 review 的 projected candidate。
- `accept|edit` → candidate `accepted`；`reject` → `rejected`。Edit 後 statement 必須等於 `ReviewDecision.edited_statement`。
- human edit 若新增數字門檻，必須帶 `edited_thresholds`；`source_type=human` 可直接引用 review authority，employee threshold 則仍須 evidence closure。
- completed session 可以繼續累積 human review state/version，但不能再接受 transcript、evidence 或模型 proposal。

### Reducer 結果與事件的正確解讀

Reducer 形式固定為：

```text
old immutable state + typed command
  -> validated new immutable state + typed domain events + stable state hash
```

相同初始 state 與 command stream 會得到相同 event IDs 和 state hash；重送同一 `command_id` 不重複 mutation。事件目前是 artifact index／audit notification，只帶被改變物件的 ID，不含完整 transcript/evidence payload。因此：

- 本階段驗證的是 **command replay + materialized state determinism**；
- 不可聲稱只靠目前 event JSON 就能重建完整 state；
- V2 persistence/Capture 必須原子保存 command/result artifact 或完整可重建 payload，再定義 checkpoint + replay protocol；
- provider SDK response 絕不可塞進 domain event。

這個區分是刻意的：audit event 和完整 event-sourcing payload 是兩種契約，不能因為都叫 event 就混用。

## JSON Schema

committed schema 位於 `domain/schemas/`，目前共 24 份，涵蓋 9 個 materialized object、1 個 event union 與 14 個 command seam；檔名與 `$id` 都有 major version。修改 Pydantic contract 後執行：

```powershell
cd apps/api
.venv\Scripts\python.exe -m app.interview_vnext.domain.write_schemas
.venv\Scripts\python.exe -m pytest tests/test_interview_vnext_schemas.py -q
```

Schema golden test 會比較 committed JSON 與當前 Pydantic codegen；未知欄位採 strict reject。runtime validator 的跨物件不變量（例如 quote 對 transcript、lineage cycle）無法只靠 JSON Schema 表達，consumer 仍必須走 domain verifier。

V1-B 沒有靜默覆寫破壞性契約：`Evidence`（withdraw authority）、`Inference`（operation hash + lineage）、`Gap`（resolution evidence）、`InterviewState` 與 `ApplyEvidenceCommand` 已升到 `v2`；純新增 command/event 或向後相容欄位維持 `v1`。這些 v1 prototype 從未接 route 或寫入 DB，因此目前不實作 runtime backward reader；V2 一旦開始 durable persistence，任何 major 升級都必須同時提供 migration／dual reader 或明確拒絕策略，不可再直接移除 persisted version。

## 測試與下一個切片

目前測試：

```powershell
cd apps/api
.venv\Scripts\python.exe -m pytest tests/test_interview_vnext_domain.py tests/test_interview_vnext_workflow_reducers.py tests/test_interview_vnext_dependencies.py tests/test_interview_vnext_schemas.py -q
```

下一步是 **V2 provider-neutral LLM port + Capture vNext**。先定義 operation registry、typed result/error、fake provider、execution artifact/event、outbox 與 crash-recovery contract；仍不接 production route，也不先寫正式訪談 Prompt。OpenAI／Anthropic adapter 只能依賴 neutral port，不能讓 SDK object 進入 domain。

ContextBuilder 在 V3 fixed replay operation 開始時實作，輸入只能來自已持久化 state/artifact/reference snapshot。現在先做 Capture 的原因是：沒有可重播 execution record，就無法判斷未來品質差是模型、context selection、verifier 還是 reducer 所造成。

本階段明確未做 route、migration、Web seam、模型 bake-off、ContextBuilder 或正式 Prompt；production 行為仍為零變化。
