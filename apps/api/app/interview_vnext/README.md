# Interview AI vNext（隔離開發中）

本 package 是 ADR 0034 的 greenfield 實作區。目前已完成 **V0 + V1 domain foundation + V2-A provider/Capture contracts + V2-B durable persistence + V3-0 readiness + V3-1 Context Engine**。V3-0固定官方OpenAI SDK 2.46.0並補上verified zero-Evidence operation的typed no-op result與atomic commit；V3-1加入deterministic ContextBuilder、hash-addressed policies、selection manifest、budget report與reference snapshot。migration仍為0010八張 `interview_vnext_*` 表。仍然**沒有 route、live provider call**，也沒有被 production composition root import。現行使用者流量仍走 `app/interview/` v3。

權威文件：

- 目標架構：[`../../../../docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`](../../../../docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md)
- V2 研究：[`../../../../docs/specs/2026-07-16-interview-vnext-v2-provider-capture-research.md`](../../../../docs/specs/2026-07-16-interview-vnext-v2-provider-capture-research.md)
- V2-B persistence reference：[`../../../../docs/specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md`](../../../../docs/specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md)
- V2-B 實作交接：[`../../../../docs/plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md`](../../../../docs/plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md)
- V3 fixed replay reference：[`../../../../docs/specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md`](../../../../docs/specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md)
- V3 實作計畫：[`../../../../docs/plans/2026-07-17-interview-vnext-v3-fixed-replay-plan.md`](../../../../docs/plans/2026-07-17-interview-vnext-v3-fixed-replay-plan.md)
- 實作順序：[`../../../../docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md`](../../../../docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md)
- 決策：[`../../../../docs/adr/0034-interview-ai-vnext-greenfield-evidence-workflow.md`](../../../../docs/adr/0034-interview-ai-vnext-greenfield-evidence-workflow.md)
- package 禁令：[`AGENTS.md`](AGENTS.md)

## 目前的程式邊界

```text
domain/                 已實作：純 Pydantic contracts、validators、reducers、domain events、schemas
application/            已實作(V2-B/V3-0/V3-1)：async persistence ports、apply_durable_command、
                        durable operations(prepare/attempt/verify/commit/fail/no-op)、
                        typed no-op result/application schema、crash recovery、pure ContextBuilder
llm/                    已實作：neutral operation/request/result/failure、registry、scripted fake、
                        V3-1 context contracts/hash-addressed policies、schemas
providers/              空殼：尚未接 OpenAI/Anthropic SDK、模型或正式 prompt
knowledge/              空殼：尚未接 reference snapshot
persistence/            已實作(V2-B)：ORM rows、migration 0010、serialization、repositories、
                        UoW、durable capture(run/event/outbox)、Postgres outbox lease adapter
projection/             空殼：尚未投影到現有 OCS/Web contract
observability/          已實作：artifact/event/hash-chain/outbox/checkpoint contracts 與 in-memory fake
```

`domain/` 只能依賴 Python 標準庫、Pydantic 和同一 domain package。AST dependency test 會阻止 vNext import v3 internals，也會阻止 domain 偷接 FastAPI、ORM 或 provider SDK。

`llm/` 與 `observability/` 也有 provider dependency guard，不得 import OpenAI、Anthropic、LangChain、LangGraph 或 Pydantic AI。未來 SDK object 只能存在 `providers/` adapter，轉成 neutral result 後就停止向內傳遞。

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

## V2-A Provider-neutral LLM contract

### Operation registry

`OperationSpec` 由 input/output contract、prompt template、context policy、quality profile、deadline/attempt/output budget、allowed tools、repair 與 safety policy 的 canonical content 產生 `definition_hash`。registry 以 stable operation name 查找，拒絕同名不同 definition。provider/model 不在 operation 內；部署與 V6 bake-off 才把 operation definition 綁到 resolved provider/model profile。

`ModelCallRequest` 表示單一 attempt：

- `operation_id` 跨 retry 不變；`attempt_id` 每次唯一、`attempt` 從 1 開始；
- `idempotency_key` 是 workflow identity，不是假裝 provider exactly-once；
- prompt、output schema、context packet、selection manifest 都用 artifact ref + canonical hash；
- instructions/messages 是 portable text contract；messages固定從 user開始、user/assistant交替並以 user結尾，使 Responses與 stateless Messages adapter都能明確投影；provider beta header、cache breakpoint、reasoning/sampling knob不進此模型；
- request 明列 `output_schema_id`，result 的 parsed payload 必須與它一致。

`ModelCallResult.outcome` 不用含糊的 boolean：

| Outcome | 必要內容 | 不可當成 |
|---|---|---|
| `succeeded` | parsed structured payload + visible response artifact + `finish_reason=completed` | domain 已接受；仍需 semantic verifier/reducer |
| `refused` | normalized refusal + visible response artifact | transport error或可 parser fallback 的 JSON |
| `incomplete` | non-complete finish reason + visible partial artifact | 可 commit 的 proposal |
| `failed` | normalized typed failure；output-related failure另需 visible artifact | 一律可 retry；是否 retry 看 `retryable` 與 deadline |

token usage 的每一欄可為 null；有 null 時必須附 limitation，不能把 provider 未回報誤記成 0。visible response只包含 provider 可見輸出，不要求也不保存 hidden chain-of-thought。

`ScriptedLlmPort` 依 operation 消耗明確 script，會檢查 attempt順序、unexpected operation與 script exhaustion。application tests可重現 valid、refusal、incomplete、typed failure與 first-fail-second-success，不必打 live API。

## V2-A Capture contract

### Artifact、execution event與 manifest

`ArtifactRecord` 是 immutable payload：ID、kind、media/schema、canonical content hash、byte size、run/session/turn/operation/attempt與 retention/redaction/test metadata。相同 ID + 相同完整 record可重送；相同 ID + 不同內容是 conflict。

`ExecutionEvent` 與 V1 `DomainEvent` 分開。它記錄 workflow/model/verification 執行，不宣稱自己是員工事實。`event_type` 和 `stage` 是 open `StableName`，由 version-addressed `ExecutionTaxonomy` allowlist驗證；目前 registry與完整名稱在 `observability/taxonomy.py`，committed document在 `observability/taxonomies/interview-vnext-execution.1.0.0.json`。新增 stage不改 event envelope schema，但要新增 taxonomy semver/document，舊版本不可覆寫。每個 run依 `sequence`、`previous_event_hash`、`event_hash` 形成 canonical hash chain；`RunManifest` 保存 event count、首尾 hash與 root artifact refs。

hash chain能偵測缺漏／改寫，但目前不是外部數位簽章或 WORM storage。in-memory `CaptureRecorder` 會先驗 artifact ref、enqueue outbox再加入 run chain；同 event ID重送相同內容為 idempotent，不同內容為 conflict。

### Outbox

`InMemoryOutbox` 的 contract狀態是：

```text
pending -> leased -> delivered
             └----> retry_wait -> leased
             └----> dead_letter
expired lease -----------------> leased by another worker
```

lease有 owner/expiry，每次 delivery attempt 可見；retry需明確 next-attempt time與 error code。這只驗證 state machine，尚未代表 PostgreSQL row lock、跨 process lease或外部 exporter 已完成。

### Operation checkpoint與 recovery

```text
prepared -> calling -> provider_completed -> verified -> committed
                 └------------- failure/policy reject ------------> failed
```

- `prepared` 已有 request artifact與 state-before hash；
- `calling` 已有唯一 active attempt；每次 retry前先把前一個 attempt result artifact append到 checkpoint，再以新 attempt ID與遞增序號啟動下一次；crash後可 reconcile provider job或依 deadline policy續行；
- `provider_completed` 已有 normalized result artifact，recovery不得重打 provider；
- `verified` 已有 verification artifact，accepted才執行 idempotent reducer command；
- `committed` 已有 domain result、response artifact與 state-after hash，可直接重用；
- `failed` 保存 terminal failure artifact/reason；不做無上限 retry。

transition會拒絕跳步、時間倒退或 terminal改寫；重送相同 artifact的同一 transition為 idempotent。

## V3-1 Context Engine（已完成，2026-07-17）

`application/context_builder.py`是provider-neutral pure service：輸入已hydrate、已驗證的`InterviewState`、versioned context policy、operation identity與選定的immutable `ReferenceSnapshot`；不查DB、不讀環境變數、不呼叫provider，也不使用provider conversation memory。相同輸入得到相同packet、manifest、budget與hash。

每次成功build同時產生：

- `ContextPacket`：實際可送模型的typed projection；
- `ContextSelectionManifest`：state/reference中每個候選source的selected/excluded、stable reason、section、canonical ordinal、內容hash與大小；
- `ContextBudgetReport`：完整packet bytes/code points、各section item count/cap、reserved output與versioned estimator限制；
- `ContextBuildResult`：綁定三份內容hash與共同operation/policy/state/reference identity，identity不一致即拒絕。

`turn.interpret`只看current employee turn、最近的preceding consultant turn、active episode identity、最多4個unresolved contradiction、8/4個correction candidates與最多6個去重後recent active evidence。它的型別根本沒有reference/candidate欄位，所有candidate/inference/review都只會在manifest顯示為禁止選入。current/preceding文字保留exact Unicode與CRLF，不做normalization或截斷。

`episode.code`不帶raw transcript/current turn；只帶target episode的active evidence，並把current employee/team且非denied、非`NOT_RESPONSIBLE`分到positive，其餘past/future/hypothetical/other-role/denied/not-responsible分到excluded-or-negative。reference使用canonical URN與整份snapshot hash，和working-state hash分開；固定authority rules禁止reference替員工事實背書，也禁止單一工具名稱直接升為skill/ability。

固定policy `1.0.0`：

- turn：65,536 UTF-8 bytes、保留8,192 output tokens；item caps為4 contradictions、8/4 correction candidates、6 recent evidence；
- episode：262,144 UTF-8 bytes、保留12,288 output tokens；hard caps為256 episode evidence、64 contradictions、128 candidates、8 references；
- estimator：`utf8-codepoint-heuristic/1.0.0 = max(code_points, ceil(utf8_bytes/4))`，只作deterministic preflight，不冒充provider tokenizer。

超過hard byte/item cap時不做first-N、摘要或文字截斷；`ContextBudgetExceeded`帶回完整未截斷packet/manifest與failing budget，且不得呼叫模型。修改policy必須建立新semver文件並以eval/ablation證明，不能原地覆寫`1.0.0`。

## JSON Schema

committed schema 目前共 38 份：`domain/schemas/` 24 份、`application/schemas/` 1 份、`llm/schemas/` 7 份、`observability/schemas/` 6 份。檔名與 `$id` 都有 major version。修改 Pydantic contract 後執行：

```powershell
cd apps/api
.venv\Scripts\python.exe -m app.interview_vnext.domain.write_schemas
.venv\Scripts\python.exe -m app.interview_vnext.application.write_schemas
.venv\Scripts\python.exe -m app.interview_vnext.llm.write_schemas
.venv\Scripts\python.exe -m app.interview_vnext.llm.write_context_policies
.venv\Scripts\python.exe -m app.interview_vnext.observability.write_schemas
.venv\Scripts\python.exe -m app.interview_vnext.observability.write_taxonomies
.venv\Scripts\python.exe -m pytest tests/test_interview_vnext_schemas.py tests/test_interview_vnext_execution_schemas.py -q
```

Schema golden test 會比較 committed JSON 與當前 Pydantic codegen；未知欄位採 strict reject。runtime validator 的跨物件不變量（例如 quote 對 transcript、lineage cycle）無法只靠 JSON Schema 表達，consumer 仍必須走 domain verifier。

V1-B 沒有靜默覆寫破壞性契約：`Evidence`（withdraw authority）、`Inference`（operation hash + lineage）、`Gap`（resolution evidence）、`InterviewState` 與 `ApplyEvidenceCommand` 已升到 `v2`；純新增 command/event 或向後相容欄位維持 `v1`。這些 v1 prototype 從未接 route 或寫入 DB，因此目前不實作 runtime backward reader；V2 一旦開始 durable persistence，任何 major 升級都必須同時提供 migration／dual reader 或明確拒絕策略，不可再直接移除 persisted version。

## V2-B durable persistence(已完成,2026-07-17)

八張全新 `interview_vnext_*` 表(sessions/runs/artifacts/commands/
execution_events/outbox/operation_checkpoints/operation_attempts;migration
`0010`,不共用、不刪改 v3 rows;downgrade 只移除 vNext objects):

- canonical aggregate/event/checkpoint 存 exact TEXT + hash,read 重跑 strict
  validation,任何 text/hash/normalized identity 不符 → `PersistedDataCorruption`;
- 一次 command commit = state CAS + command/reduction immutable artifacts +
  hash-chained event + pending outbox **同一 transaction**(reference §7.3;
  先鎖 run row 建立一致鎖序,防 FK KEY SHARE 死鎖);
- transactional outbox:§8.1 lease CTE(`FOR UPDATE SKIP LOCKED` 只用在 queue、
  同 run 只放最早 non-terminal message)、lease commit 後才呼叫 exporter、
  at-least-once(consumer 以 event_id 冪等)、delivered/dead_letter terminal 留稽核;
- checkpoint crash recovery:prepared→calling→provider_completed→verified→
  committed|failed,revision CAS;`application/recovery.py` 的 `decide_recovery`
  純函式照 §9 決策表;`provider_completed` 之後 recovery 的 provider generate
  次數=0,committed 重呼叫回同一 response/domain result artifact;
- provider/exporter network call 一律在 DB transaction 外;LLM outcome 分類
  (retryable 與否)由 caller/adapter 提供,typed `ModelCallResult` 正規化屬 V3/V6。

Postgres integration tests(需 `TEST_DATABASE_URL`;CI 由 `api-tests.yml` 以
postgres:16 service 必跑,`require_postgres` 讓 skip 不可能被當通過):

```powershell
cd apps/api
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn'
uv run alembic upgrade head
uv run pytest tests/test_interview_vnext_persistence_serialization.py `
  tests/test_interview_vnext_migration.py `
  tests/test_interview_vnext_persistence.py `
  tests/test_interview_vnext_outbox_postgres.py `
  tests/test_interview_vnext_recovery_postgres.py `
  tests/test_interview_vnext_pg_fixtures.py -q     # 50 passed, 0 skipped
```

## 測試與下一個切片

目前測試（V2-A contracts,無 DB）：

```powershell
cd apps/api
.venv\Scripts\python.exe -m pytest tests/test_interview_vnext_domain.py tests/test_interview_vnext_workflow_reducers.py tests/test_interview_vnext_llm.py tests/test_interview_vnext_capture.py tests/test_interview_vnext_dependencies.py tests/test_interview_vnext_schemas.py tests/test_interview_vnext_execution_schemas.py -q
```

V2-B完成點的歷史基線是focused Postgres `50 passed, 0 skipped`、完整API
`499 passed, 0 skipped`。V3-0完成後（2026-07-17）durable focused suite為
`54 passed, 0 skipped`，完整API suite以本機PostgreSQL 16實跑為
`506 passed, 0 skipped`。no-op cases涵蓋exact replay、不同response/verification
conflict、stale state、event failure全transaction rollback與兩個concurrent
committer只產生一個completion；沒有新增migration或command row。V3-1聚焦
Context/schema/dependency suite為`15 passed`，完整API + PostgreSQL regression為
`515 passed, 0 skipped`。

下一步是 **V3-2 `turn_interpret` contracts、prompt、proposal mapper與verifier**。
Context輸入只能來自已持久化state/artifact/reference snapshot；typed
`ModelCallResult`在後續V3 executor接上`record_attempt_result`。先做
Capture/persistence與Context Engine的原因是：
沒有可重播 execution record,就無法判斷未來品質差是模型、context selection、
verifier 還是 reducer 所造成。V5 前必須完成 authenticated principal → tenant
→ profile ownership 驗證(reference §2.3),否則 production gate 不得通過。

本階段明確未做 route、外部 Capture exporter、live OpenAI/Anthropic adapter、
Web seam、模型 bake-off或正式 Prompt；production 行為仍為
零變化(composition root 不 import vNext)。durable outbox/checkpoint 已由
V2-B DB tests 證明;只有 V3 fixed replay與 V6 bake-off通過後才能談模型品質或上線。
