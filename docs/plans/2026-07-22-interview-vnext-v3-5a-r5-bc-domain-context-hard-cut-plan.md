# Interview AI vNext V3-5A R5-BC——Domain、Context 與 Turn Interpreter 原子 Hard Cut 實作交接規格

- 狀態：**Approved / planned；實作尚未開始**
- 日期：2026-07-22
- 前置完成：R5-A `bf35137`、R5-A corrective `09f406a`、corrective status `195c6a3`
- 分支 baseline：`research/llm-interview-integration`，文件建立時 HEAD `195c6a3`
- 實作 authority：本文件負責 R5-B 與 R5-C 的原子交付；未重述處仍以 R5 amendment 與 ADR 0037 為準
- 不執行：paid live、production route、Web/editor 整合、SaaS、多租戶、Job synthesis、Alembic 0011、provider promotion

關聯 authority：

- [`2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md`](2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md)
- [`../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md`](../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)
- [`2026-07-21-interview-vnext-v3-5a-r5-a-corrective-contract-closure-plan.md`](2026-07-21-interview-vnext-v3-5a-r5-a-corrective-contract-closure-plan.md)
- [`2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`](2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md)

---

## 1. 白話：這一步到底在做什麼

目前系統已經有「問題是什麼、短答應該綁到哪個問題」的 inactive domain contracts，但正式 runtime 仍使用舊的
`Evidence.v2`、`InterviewState.v2`、generic append-turn command 與只會抽完整句子的 Turn Interpreter v1。

R5-BC 會一次把正式執行路徑切到新架構：

1. 顧問問問題時，除了 transcript，還會持久保存一個 `QuestionFrame`，明確描述這題要確認的命題、欄位或選項；
2. 員工回答「是／不是／每週／兩個都有」時，模型只回傳 ordinal 與語意，不得產生 domain UUID；
3. application 用當時的 frame、context snapshot 與 deterministic verifier 決定答案是否可採用；
4. literal 完整句與 contextual 短答都 materialize 成 `Evidence.v3`，但 support type 永遠可區分；
5. 即使這輪沒有 Evidence，例如「不知道／不想回答」，仍保存 durable interpretation receipt，表示這輪已處理；
6. state、receipt、Evidence、frame consume、events 與 Capture artifacts 要在同一條可重播、可稽核的鏈上閉合；
7. provider adapter、OpenRouter route/cache/conformance 規則不變，語意判斷仍在 neutral application layer。

本步不是做完整產品 UI，也不是把整份 JD 丟給模型。它交付的是後續「對話式專業顧問」可依賴的正確核心。

---

## 2. 為什麼 R5-B 與 R5-C 必須合併

母計畫允許在中間版本無法全綠時合併相鄰 slice。這裡已透過 code audit 確認不能誠實地只提交 R5-B：

- `ContextEvidenceItem` 目前直接巢狀 `Evidence`；Evidence v2 → v3 會改變 frozen `context-packet.v1` 的 schema；
- `ContextBuilder`、Turn Interpreter、reducers、state validators 與 eval fixtures 直接讀 `evidence.turn_id/quote/span`；
- executor 直接建立 `ApplyEvidenceCommand.v2`；command hard cut 後必須同步改成 `ApplyTurnInterpretationCommand.v1`；
- zero-Evidence 的舊路徑建立 generic no-op；State v3 要求成功 interpretation 建 receipt，兩者不能同時 active；
- input/output/report v1 直接嵌舊 Evidence/qualifier/user-signal 語意；只改 domain 會讓 schema 與 runtime 不一致；
- 不允許 temporary dual-active reader、`request | call` shim、提交已知 full suite 會紅的 commit。

因此本文件把 R5-B 與 R5-C 合併為一個 **atomic R5-BC code commit**。實作期間可在工作樹內分 phase 驗證，但在 active
registry、全部 consumer、schema fixtures、no-network suite 與 real PostgreSQL gate 同時全綠前不得 commit。

這不是擴張需求；是避免同一概念存在兩套 active authority。

---

## 3. Authority、優先序與本文件唯一 refinement

若文件文字衝突，依下列優先序：

1. ADR 0037 的 authority/invariant；
2. 本 R5-BC 文件對實作切片、欄位與 gate 的明確化；
3. R5 amendment；
4. runtime reconstruction mother plan；
5. 現行 v1 code 只代表 migration source，不是目標設計。

### 3.1 Provider-facing evidence projection 必須含 `support_kind`

R5 amendment §8.5 原先把 recent/correction evidence 寫成只有 `quote` 的扁平物件；ADR 0037 §4 又要求每個 consumer 先查看
`support_kind`，不得把 contextual answer 的「是」呈現成完整 claim 的逐字引文。為消除歧義，本切片採以下 exact refinement：

```text
TurnInputEvidence
  ordinal field                        # candidate_ordinal 或 recent_ordinal
  subject
  kind
  claim
  support_kind                         # literal_employee_span | contextual_answer
  quote                                # literal: support.quote；contextual: support.answer_quote
  qualifiers
```

規則：

- input 保持扁平 portable object，不把 domain support union 原樣送 provider；
- contextual 的 `quote` 只是「本輪短答」，不是 claim 的逐字支持；prompt 必須明文告知模型；
- domain `Evidence` 只提供 non-serialized `source_turn_id` property，不新增通用 `quote` property；
- UI、grader、Capture viewer 或未來 editor 若顯示來源，一律先 branch `support_kind`；
- 本 refinement 只修 projection authority，不改 provider output schema、binding identity或 R4 conformance。

---

## 4. Scope 與非目標

### 4.1 必須交付

- Evidence.v3、InterviewState.v3 active hard cut；
- consultant/employee append、frame invalidation、apply interpretation commands；
- DomainEvent.v2、ReductionResult.v2 與 reducer transaction/event order；
- persisted state major-version fail-closed；
- Context packet/manifest/budget v2，state version/hash與 eligible QuestionFrame；
- TurnInterpret input/output/report v2；prompt/context/verifier/operation 2.0.0；
- literal observation + contextual answer binding materialization；
- durable interpretation receipt，包含 zero-Evidence success；
- executor stale-context CAS、fresh-process recovery與 minimum Capture closure；
- provider adapters/probes/scripted fixtures 對新 output schema 的機械遷移；
- eval harness 的 active v2 schema/import/fixture hard cut，舊 v1 files frozen；
- full no-network、real PostgreSQL、schema/dependency/secret/Alembic gates。

### 4.2 本切片不做

- 不做下一題選擇 agent、完整 JD synthesis 或 K/S 推論；
- 不讀現有 editor 或向量資料庫，不新增 `JobStateDigest`；
- 不做員工接受／修改／拒絕 AI 文件 patch 的 UI；
- 不改 OpenRouter provider routing、cache、retry、conformance eligibility；
- 不新增 OpenAI production route；OpenAI 仍是 mocked reference adapter；
- 不做 live model quality promotion，不因 reference/mock 全綠宣稱模型品質已達標；
- 不新增 SQL table/column/index，不做 dual reader 或正式資料 migration；
- 不藉機重構與 R5 無關的 persistence、Capture framework 或整個 eval harness。

---

## 5. R5-BC 完成後唯一 active version set

| Area | Historical/frozen | R5-BC active |
|---|---|---|
| Evidence | `evidence.v2` | `evidence.v3` |
| State | `interview-state.v2` | `interview-state.v3` |
| append turn | `append-transcript-turn-command.v1` | consultant/employee command v1 |
| apply evidence | `apply-evidence-command.v2` | `apply-turn-interpretation-command.v1` |
| DomainEvent | `domain-event.v1` | `domain-event.v2` |
| ReductionResult | `reduction-result.v1` | `reduction-result.v2` |
| Context packet/manifest/budget | v1 | v2 |
| Turn input/output/report | v1 | v2 |
| Context/verifier/operation/prompt | `1.0.0` | `2.0.0` |
| application outcome | generic/no-op or v1 | `turn-interpret-execution-outcome.v2` |
| eval suite | `turn-interpret-pilot.v1` | `turn-interpret-c1-v2-pilot.v1` |
| provider binding/call/result/evidence/conformance | R4 active | **不變** |
| execution taxonomy/checkpoint | `2.0.0` / v2 | **不變** |
| DB schema | Alembic 0010 | **仍為 0010** |

### 5.1 Historical schema policy

每個 schema writer 分成：

- `SCHEMA_EXPORTS`：只含 active schemas，可由 model 重生；
- `HISTORICAL_SCHEMAS`：只含已 committed frozen files；writer 不重生；test 以 byte/hash 鎖住；
- active 與 historical filename 不得重疊；目錄不得有未註冊 schema。

Domain 至少凍結：

```text
evidence.v2.schema.json
interview-state.v2.schema.json
append-transcript-turn-command.v1.schema.json
apply-evidence-command.v2.schema.json
domain-event.v1.schema.json
reduction-result.v1.schema.json
```

LLM 至少凍結：

```text
context-packet.v1.schema.json
context-selection-manifest.v1.schema.json
context-budget-report.v1.schema.json
turn-interpret-input.v1.schema.json
turn-interpret-output.v1.schema.json
turn-interpret-verification-report.v1.schema.json
```

Eval 現有 11 個 `turn-eval-*.v1.schema.json` 全部保留為 historical；active models/files 使用 v2，避免 outer v1 schema 因巢狀
production type 改變而 silent drift。`case_id`、12 個 case 的語意與 dev/challenge split 不變，但 suite/file hashes全部重算。

---

## 6. Dependency direction 與模組責任

允許的 production-neutral 方向：

```text
domain.base / identifiers / hashing
                 ↓
domain.support / question_frame / interpretation
                 ↓
domain.evidence
                 ↓
domain.state / commands / events / reducers
                 ↓
application.context_builder / turn_interpret / executor
                 ↓
llm provider-neutral contracts and port
```

實際 Python import 不要求完全照圖單向穿越所有 layer；必須維持的硬限制是：

- domain 不 import application、llm、evals；
- app/production 不 import `evals.*`；
- provider adapters 不持有 domain/reducer authority；
- `support.py` 不回頭 import `evidence.py`；
- 不用 `TYPE_CHECKING`/late import 掩蓋 cycle；
- deterministic ID/hash helpers 只有一份實作。

建議新增 `domain/turn_identity.py`，只放四個 pure UUIDv5 functions；若實作者選擇放在既有 `identifiers.py`，必須維持相同
公共 authority，不可在 verifier、reducer、eval fixture 各複製一份。

---

## 7. Domain hard cut exact contract

### 7.1 Evidence.v3

直接依 R5 amendment §6.5 實作；active model 不保留 v2 top-level `turn_id/quote/span/quote_match/normalization_version`。

```text
Evidence.v3
  schema_version = evidence.v3
  evidence_id / session_id / episode_id
  subject / kind / claim
  support: LiteralEmployeeSpanSupport | ContextualAnswerSupport
  qualifiers
  status / supersedes / superseded_by
  withdrawn_reason / withdrawn_by_turn_id
  correction_target_unknown
  extractor_operation_id
```

`source_turn_id` 是唯一允許的 non-serialized source convenience property，值永遠為 `support.employee_turn_id`。所有 lineage、排序、
candidate、context、eval consumer 改讀它。不得留下 fallback `getattr(evidence, "turn_id", ...)`。

### 7.2 State.v3 closure

保留 v2 collections/invariants，Evidence tuple升 v3，新增：

```text
question_frames: tuple[QuestionFrame, ...] = ()
active_question_frame_id: UUID | null = null
turn_interpretations: tuple[TurnInterpretationRecord, ...] = ()
```

aggregate validator 除母規格條件外，必須保證：

- 最多一個尚未有 interpretation receipt 的 employee turn；若存在必須是 transcript tail；
- 有 active+answer-bound frame 時，其 answer turn就是該 pending employee tail；
- receipt、operation、employee turn、frame、Evidence IDs各自 unique且 same session；
- `accepted_evidence_ids` 順序等於該 operation產生並保存的 Evidence順序；
- contextual support只可連回同一 receipt 的 frame、employee turn與 operation；
- literal support的 quote/span仍對應 source employee turn；
- active pointer與唯一 active frame完全一致；closed frame不可 reopen；
- frame source evidence只在 active frame建立/使用時要求 active；closed歷史 frame保存原 hash，不因後續 supersede/withdraw變成不可讀。

若既有 ReasonCode 不足以表達「employee turn 已 append、尚待 interpretation」，在 enum尾端新增
`turn_interpretation_pending`。不要錯用 provider failure或 generic invalid state。

### 7.3 Commands

Active command union移除 generic append/apply-evidence，新增並註冊：

```text
AppendConsultantQuestionCommand.v1
  CommandBase
  turn: consultant TranscriptTurn
  frame_definition: QuestionFrameDefinition

AppendEmployeeTurnCommand.v1
  CommandBase
  turn: employee TranscriptTurn

InvalidateQuestionFrameCommand.v1
  CommandBase
  question_frame_id
  reason

ApplyTurnInterpretationCommand.v1
  CommandBase
  record: TurnInterpretationRecord
  observations: tuple[Evidence.v3, ...] = ()
```

`record.accepted_evidence_ids` 必須逐項等於 observations IDs；set equality不合格。Command可有零 observations。

### 7.4 Deterministic identities

```python
uuid5(consultant_turn_id, "question-frame")
uuid5(operation_id, "turn-interpretation")
uuid5(operation_id, f"literal/{observation_index:04d}")
uuid5(operation_id, f"binding/{binding_index:04d}/materialization/{materialization_index:04d}")
```

- indices 1..9999；
- 先按 provider 原始位置派生，再做 drop；drop 後不重編；
- choice materialization按 option ordinal排序後編號；
- tests 必須使用固定 UUID exact vectors，不只測 repeatable。

### 7.5 Reducer transaction與 event order

四條 command path 依 R5 amendment §7.3–§7.6；不得拆成多次 state write。

額外澄清：

- `AppendConsultantQuestionCommand` 在任何 pending employee interpretation存在時必須 reject；bound active frame回
  `question_frame_answer_pending`，無 eligible frame但仍有 pending turn回 `turn_interpretation_pending`；
- `AppendEmployeeTurnCommand` 不接受 caller/frame ID，只由 active state綁 immediate frame；
- withdrawal若影響 active frame source，同 transaction stale並在 `evidence.withdrawn` 後 emit `question_frame.staled`；
- `ApplyTurnInterpretationCommand` 一次完成 evidence lineage、frame consume、receipt append、state version increment；
- zero-Evidence 仍 emit `question_frame.consumed`（有 frame時）與最後的 `turn.interpretation_applied`；
- duplicate command走既有 idempotent result，不重建 clock/event/receipt。

Apply event exact order：

```text
每個 observation：
  evidence.observed
  該 observation 的每個 superseded target：evidence.superseded
若有 frame：question_frame.consumed
turn.interpretation_applied       # 永遠最後
```

所有 event升入 `DomainEvent.v2`；`ReductionResult.v2`只引用 v2 union。v1 JSON files frozen，不在新 model union中 active。

---

## 8. Persistence hard cut

### 8.1 Raw version check

在 `persistence/serialization.py` 先解析 JSON object與 raw `schema_version`，再交 Pydantic：

```text
interview_state.v3  -> strict InterviewState.model_validate
missing / v2 / unknown -> UnsupportedPersistedSchemaVersion
v3 內容、hash、cross-link壞 -> PersistedDataCorruption
```

新增：

```text
UnsupportedPersistedSchemaVersion(PersistenceError)
  expected: interview_state.v3
  actual: string | null
```

不得：

- 把合法 v2 資料報成 corruption；
- 寫 dual reader、自動 upgrade、v2→v3 fallback；
- 全表刪資料。若 test/eval rows 阻擋，只能用現有 tenant-scoped cleanup 並記錄 exact count；
- 新增 0011。repository/table/state_json欄位不改。

### 8.2 Durable command mapping

`application/durable_commands.py` 同步切 active command bindings、schema IDs與 reducer dispatch：

```text
INTERVIEW_STATE_SCHEMA_ID -> interview-state.v3
REDUCTION_RESULT_SCHEMA_ID -> reduction-result.v2
```

command artifact、result artifact、state write與 domain events 保持同一 transaction。所有 artifact refs仍先驗 scope/hash。

---

## 9. Context Engine v2

### 9.1 Identity與版本

`ContextIdentity` 新增 `state_version >= 0`；packet、selection manifest、budget report三者的 operation/session/turn/state hash/version/
policy identity 必須 byte-equal。

以下所有序列化 contract升 v2，不得讓 v1 filename內容漂移：

```text
ContextBuildResult.v2              # internal serialized result亦升版
TurnInterpretContextPacket.v2
EpisodeCodeContextPacket.v2        # 因共同 identity/Evidence shape改變，僅機械升版
ContextSelectionManifest.v2
ContextBudgetReport.v2
```

Episode-code policy/operation語意不在 R5 改寫；只遷移共同 context contract，避免 v1 schema silent mutation。

### 9.2 Section order與 QuestionFrame

Turn Interpret policy `2.0.0` exact order：

```text
injection_boundary
preceding_consultant_turn
current_employee_turn
question_frame
active_episode
contradictions
correction_candidates
recent_active_evidence
```

eligible frame時是 mandatory item，cap=1，不因 budget被 drop或截斷。若完整 frame超 budget，ContextBuilder typed fail；不得只截
target/options。frame source type/content hash依母規格。

### 9.3 Eligible frame

只有 pointer、active status、answer turn、immediate previous consultant、text/definition/target hashes、source Evidence closure全部成立才
投影。stale/missing/non-immediate frame不提供 targets，manifest/budget保存 stable limitation；current employee turn仍可 literal extraction。
ContextBuilder只觀察，不修 state。

### 9.4 ContextEvidenceItem

Context packet可巢狀完整 `Evidence.v3`，但 source/content hash要以 canonical Evidence v3計算。排序與 candidate identity改讀
`source_turn_id`。provider projection依 §3.1 轉成帶 `support_kind` 的扁平物件。

---

## 10. TurnInterpret input/output/report v2

### 10.1 Input

exact top-level沿 R5 amendment §8.5，並套用本文件 §3.1 refinement。禁止所有 UUID/domain ID/state/frame/artifact hash/ref。

ordinal規則：

- correction candidates依 canonical source turn sequence + Evidence ID排序後編 1..n；
- recent evidence同理獨立編號；
- frame targets/options使用 definition既有 ordinal；
- iteration order改變不得改 provider JSON bytes；
- projection map只留 application memory/artifact內，provider看不到 domain identity。

### 10.2 Output

實作 R5 amendment §9 exact shape：

- `dialogue_act`、`episode_signal` 使用 domain-owned enums；
- `literal_observations` 無 proposal key/UUID，只用原始位置；
- correction只輸出 candidate ordinals；
- `answer_bindings` 是 flat portable schema；
- 移除 `user_signal`；
- insufficiency unique且依 domain enum順序，不按字母排序；
- model order保留，不 sort。

portable schema projection、OpenRouter outbound `response_format`、OpenAI reference schema與 schema catalog 必須使用同一 active
`turn-interpret-output.v2` canonical hash。

### 10.3 Report

`TurnInterpretVerificationReport.v2` 必須同時保存 observation/binding decisions、candidate/materialized IDs、computed spans、drop reasons、
accepted IDs與 model/system insufficiency。accepted ID順序固定為：

1. accepted literal observations依 output位置；
2. accepted bindings依 output位置；
3. 同一 choice binding materializations依 option ordinal。

任何 drop 後不得重編 proposal/binding/evidence identity。

---

## 11. Verifier與 materialization

### 11.1 Gate順序不可調換

依母規格 §10.2 的 13 steps。特別禁止：

- trim/NFKC/修 JSON/猜 occurrence；
- 找不到 quote時選 first duplicate；
- invalid binding降級為 literal；
- model輸出 target/domain UUID；
- adapter做 frame/qualifier/evidence eligibility；
- 因一筆 observation失敗回滾另一筆獨立有效 observation。

### 11.2 Literal materialization

每筆 accepted literal observation：

- quote/span只來自 current employee turn exact Unicode code-point span；
- `support_kind=literal_employee_span`；
- qualifiers每個 exact support仍位於 observation quote；
- correction ordinals由 input projection map解回 active Evidence ID；
- identity用 literal observation原始 1-based index。

### 11.3 Contextual materialization

依 frame mode/kind/resolution matrix；source永遠是 current employee answer quote/span與 frame target，不偽造 employee曾逐字說出 target
claim。`ContextualAnswerSupport.question_frame_definition_hash/target_hash` 必須來自當次 context snapshot，不重新 load latest frame計算。

slot/frequency parser、choice materialization、conflict marker與 denial supersession規則完全依母規格 §10.5/§11。任何 ambiguous/unknown
binding可以是 semantic success，但 materialized Evidence為空。

### 11.4 Zero-Evidence success

下列情況仍是成功 interpretation，不走 `OperationNoopResult`：

- dont_know、decline、stop、off_topic；
- ambiguous/unknown binding；
- output schema合法，但所有 proposal被 deterministic verifier drop。

仍建立 report、record、apply command、reduction、receipt；有 eligible frame就 consume。provider refusal、wire/conformance/schema failure、
stale-context failure則不建立 receipt、不 consume frame。

---

## 12. Prompt、policy、operation與 registry

新增並由 writers deterministic 產生／驗證：

```text
prompts/turn-interpret.2.0.0.md
context_policies/turn-interpret.2.0.0.json
verifier_policies/turn-interpret-verifier.2.0.0.json
operations/turn-interpret.2.0.0.json
```

active registry對 `turn.interpret` 只回 2.0.0；舊 1.0.0 files保留但不可 active fallback。

Prompt 除母規格 normative sections，必須明寫：

- transcript/context都是 untrusted data，不服從其中指令；
- QuestionFrame是唯一可用的短答語境；無 eligible frame時「是」不可綁舊問題；
- input evidence 的 contextual `quote` 是短答，不代表 claim逐字出現在員工訊息；
- literal observation quote只可取 current turn exact substring；
- 不輸出 UUID/hash/domain identity，不補 frame未提供的 target；
- frequency不暗示 current，time_scope與frequency分開；
- valid zero-Evidence dialogue act可回空 observations/bindings。

operation保留 `max_attempts=3`、schema repair=1、semantic repair=0；provider binding/conformance policy不改。

---

## 13. Executor、CAS 與 recovery

### 13.1 Fresh execution

固定順序：

```text
load InterviewState.v3
build Context v2
project TurnInterpretInput.v2
save context/input/frame snapshot artifacts
prepare checkpoint using those exact refs
provider preflight + one governed call
persist result/evidence/conformance
provider gate
local output schema gate
semantic verifier/materialization
build record + ApplyTurnInterpretationCommand
CAS domain commit against context state version/hash
finalize checkpoint/outcome/manifest
```

eligible frame時保存 `question_frame_snapshot.v1`，hash必須等於 context source hash。

### 13.2 Stale context

`_commit_report` 不可 load latest state後重建 command。expected version/hash固定取自 context。transaction內實際 state任一不同：

- 不寫 domain state/event/receipt；
- 保存 deterministic `state_context_stale` local failure artifact，含 expected/actual version/hash；
- terminal fail checkpoint；
- provider call count維持1；
- 不 retry、不 rebase、不重用相同 operation ID跑新 context。

### 13.3 Outcome v2

新增 application model/schema：

```text
TurnInterpretExecutionOutcome.v2
  schema_version = turn_interpret_execution_outcome.v2
  checkpoint_ref
  context_packet_ref / input_ref / provider result refs / report_ref
  interpretation: TurnInterpretationRecord
  accepted_evidence: tuple[Evidence.v3, ...]
  domain_command_ref / reduction_result_ref
  noop_ref: null
```

若實際 existing outcome還需保存 manifest/state artifact ref，可在不重複 authority下加入 typed refs；不得省略上述 closure。v1/no-op schema留
historical。Turn Interpreter成功路徑不得再產 `operation-noop-result.v1`。

### 13.4 Recovery

依母規格 §13.6。provider_completed/verified/committed fresh-process recovery一律0 network；所有 artifact先驗 scope/hash/schema。domain command
成功、checkpoint未完成時用 deterministic command ID重送，reducer回 idempotent result，receipt/events不重複。

missing/tampered artifact是 persisted corruption；正常 concurrent state前進是 `state_context_stale`。兩者不得合併成同一 error。

---

## 14. Capture minimum closure

R5-BC 必須正確產生 v2 artifact/event refs，R5-D 再補完整 bundle corruption/re-export矩陣。

新增/升版 artifact kinds：

```text
interview.question_frame_snapshot.v1
interview.context_packet.v2
interview.context_selection_manifest.v2
interview.context_budget_report.v2
interview.turn_interpret_input.v2
interview.turn_interpret_output.v2
interview.turn_interpret_verification_report.v2
interview.turn_interpretation_record.v1
interview.apply_turn_interpretation_command.v1
interview.reduction_result.v2
interview.turn_interpret_execution_outcome.v2
```

R5-BC minimum gate：

- started/context/model/local/domain/terminal events引用實際 input/output refs；
- success manifest roots可達 frame→context/input→provider→output/report→record/command/reduction/outcome；
- zero-Evidence success仍可達 record/command/reduction；
- stale failure root可達原 context/report與 failure artifact；
- secret/reasoning redaction規則完全沿用 R4；
- 不在 manifest填不存在或只憑預期值合成的 artifact。

---

## 15. Eval/provider mechanical migration

### 15.1 Provider adapters

OpenRouter/OpenAI adapter只做以下機械改動：

- expected output schema ID/hash改 v2；
- mocked success fixtures改 v2 JSON shape；
- probe request/input builder改 context/input v2；
- exact outbound schema、single-call、wire result、execution evidence、conformance tests維持原語意；
- 不執行 live；不改 route/cache/retry/routing normalizer。

若 adapter需要理解 `QuestionFrame`、Evidence或 verifier reasons，表示 boundary跑歪，必須停下。

### 15.2 Eval suite active v2

為避免現有 v1 schema被巢狀 production type改寫，eval 11 個 contracts一次升 v2，v1 files全部 historical。新 suite：

```text
turn-interpret-c1-v2-pilot.v1
```

12 個 case ID、case內容與 split不變；case/fixture/reference/gold/batch identities與 suite hash全部重算，不得沿用
`sha256:ed51167d64a9887f7a119568ad501ea71e1edd63eace6e44ccba222b5d763d5a`。

必要 mechanical semantic migration：

- initial prior Evidence改 domain `EvidenceQualifiers` + literal support fixture；
- transcript replay改 consultant/employee commands；每個 consultant turn提供 deterministic frame definition；
- reference output改 literal observations/bindings v2，correction用 observation index + logical evidence keys；
- gold `allowed_user_signals` 改 `allowed_dialogue_acts`；
- insufficiency type改 domain `TurnInsufficiencyCode`；
- `ExpectedCommit` 改成 `evidence_and_receipt | receipt_only`；不再有 no-op success；
- gold observation新增/保留足以要求 `allowed_support_kinds` 的欄位；舊12 case預期為 literal，不藉機新增 contextual quality標籤；
- `state_hash_changed=true` 對兩種成功 commit都成立，receipt-only可沒有 required Evidence observation；
- grader先 branch support_kind，再取 literal quote或 contextual answer_quote；不得使用通用 Evidence.quote；
- reference gate必須走 production ContextBuilder/verifier/reducer，不可在 eval複製 materializer。

這是契約硬切與 harness可執行性，不是 R6 模型品質改標。R6才新增真正 short-answer/mixed/frequency quality cases與 live multi-trial。

---

## 16. 逐檔施工責任

### 16.1 Domain/persistence

修改：

```text
app/interview_vnext/domain/evidence.py
app/interview_vnext/domain/state.py
app/interview_vnext/domain/commands.py
app/interview_vnext/domain/events.py
app/interview_vnext/domain/reducers.py
app/interview_vnext/domain/reason_codes.py
app/interview_vnext/domain/invariants.py
app/interview_vnext/domain/schema_exports.py
app/interview_vnext/domain/write_schemas.py
app/interview_vnext/domain/__init__.py
app/interview_vnext/persistence/serialization.py
app/interview_vnext/persistence/errors.py
```

可新增一個 deterministic identity helper module；不得新增第二個 Evidence/frame aggregate。

### 16.2 Context/LLM/application

```text
app/interview_vnext/llm/context.py
app/interview_vnext/llm/turn_interpret.py
app/interview_vnext/llm/operation.py
app/interview_vnext/llm/registry.py
app/interview_vnext/llm/schema_exports.py
app/interview_vnext/llm/write_*.py
app/interview_vnext/llm/prompts/turn-interpret.2.0.0.md
app/interview_vnext/llm/context_policies/turn-interpret.2.0.0.json
app/interview_vnext/llm/verifier_policies/turn-interpret-verifier.2.0.0.json
app/interview_vnext/llm/operations/turn-interpret.2.0.0.json
app/interview_vnext/application/context_builder.py
app/interview_vnext/application/turn_interpret.py
app/interview_vnext/application/operation_executor.py
app/interview_vnext/application/durable_commands.py
app/interview_vnext/application/durable_operations.py
app/interview_vnext/application/recovery.py
app/interview_vnext/application/schema_exports.py
app/interview_vnext/application/write_schemas.py
```

### 16.3 Eval/providers/tests

修改全部會 import active turn/domain contracts的 eval modules，至少：contracts、loader、fixture_builder、schema writer/catalog、runner、
graders、report、scheduler、batch orchestrator、live wiring、兩個 probe與兩個 provider adapter fixtures/tests。

production tests至少覆蓋：domain、workflow reducers、schemas、context builder、turn interpret、llm、persistence serialization、durable PG、
recovery PG、Capture、provider adapters、eval contracts/loader/fixtures/runner/graders/OpenRouter PG。

禁止為了讓舊 test綠而在 production保留 v1 active aliases。測試應搬到新 authority。

---

## 17. 實作順序：工作樹 phases，不是 commits

### Phase 0——Baseline與資料盤點

1. 記錄 HEAD/worktree/config author；
2. 跑 focused baseline與 schema writer no-diff；
3. 查 test/eval DB state schema versions與 tenant counts；
4. 記錄 Alembic current/heads = 0010；
5. 不清資料，先把 counts寫入實作紀錄。

### Phase 1——Domain/state/persistence

先改 models/schema/reducers與 pure tests，再改 persistence/durable command mapping。此時可跑 focused，但不得 commit。

### Phase 2——Context/input/output/verifier

切 context v2、portable input/output/report、prompt/policies/registry與 pure semantic tests。不得用 temporary v1 adapter。

### Phase 3——Executor/recovery/Capture

切 receipt commit、zero-Evidence、state CAS/outcome/artifacts；跑 scripted/real PG recovery。

### Phase 4——Eval/provider migration

切 11 個 eval schemas、12 case fixtures/hash、provider mocked fixtures/probes。provider wire logic不改。

### Phase 5——Atomic gate與 commit

所有下列 gate全綠後，才建立一個 code commit：

```text
feat(interview): ground turn interpretation in persisted question frames
```

不得先提交「domain已好但 full suite紅」或「暫時兼容 v1」的中間 commit。commit後再開 docs-only status commit，不 amend/rewrite
R5-A/R4歷史 commits。

---

## 18. Required test matrix

### 18.1 Domain/reducer

- R5 amendment §16.1 全矩陣；
- fixed UUIDv5 vectors；drop不重編；choice materialization排序；
- pending employee tail invariant；consultant/employee command role與 immediate rules；
- zero Evidence仍 receipt/event/state version；
- duplicate command idempotent，duplicate receipt/operation拒絕；
- source withdrawal stales active frame，同 transaction/event order；
- all prior Episode/Gap/Inference/Candidate lineage在 Evidence.v3仍通過。

### 18.2 Context/projection

- packet/manifest/budget exact state version/hash；
- eligible frame mandatory，ineligible limitation；
- provider input找不到 UUID/hash/ref；
- literal/contextual `support_kind`與 quote投影 exact；
- contextual「是」不被 grader/prompt當 claim literal quote；
- collection iteration打亂後 bytes相同；frame budget不可截斷。

### 18.3 Output/verifier

- portable schema forbidden extras/UUID；
- binding coherence、ordinal、quote occurrence、duplicate all-drop；
- literal/contextual/mixed各自成功與單邊 drop；
- frequency/time independence exact vectors；
- ambiguous/dont_know/decline/stop/off_topic receipt-only；
- provider/schema/conformance failure無 receipt；
- frame missing/stale時短答不綁，但 literal clause仍可採用。

### 18.4 Persistence/recovery/Capture

- v2 state → UnsupportedPersistedSchemaVersion；v3 malformed → corruption；
- stale state provider calls=1、domain writes=0；
- provider_completed/verified/committed fresh process calls=0；
- crash after command不重複 receipt/events；
- manifest success、receipt-only、stale failure roots；
- missing/tampered frame/report/record fail closed。

### 18.5 Eval/provider

- all 11 v1 schemas byte frozen、11 v2 active deterministic；
- 12/12 v2 reference outputs走 production gate；
- suite hash固定且非舊 v1 hash；
- gold不再有 `UserSignal`/`NO_OP`；
- OpenRouter/OpenAI outbound schema hash精確等於 v2 catalog；
- 429/500/timeout single-call、route/cache/conformance R4 regression全綠；
- no key path不建 run、不打 network、不碰 DB。

---

## 19. 驗收命令與 gate

全部從 `apps/api`，使用 lock。可增加檔案，不可刪同類 gate。

### 19.1 Focused no-network

```powershell
uv run --locked pytest -q tests/test_interview_vnext_question_frame.py tests/test_interview_vnext_domain.py tests/test_interview_vnext_workflow_reducers.py
uv run --locked pytest -q tests/test_interview_vnext_schemas.py tests/test_interview_vnext_execution_schemas.py tests/test_interview_vnext_dependencies.py
uv run --locked pytest -q tests/test_interview_vnext_context_builder.py tests/test_interview_vnext_turn_interpret.py tests/test_interview_vnext_llm.py
uv run --locked pytest -q tests/test_interview_vnext_openrouter_eval_adapter.py tests/test_interview_vnext_openai_eval_adapter.py
uv run --locked pytest -q tests/test_interview_vnext_capture.py tests/test_interview_vnext_persistence_serialization.py
uv run --locked pytest -q tests/test_interview_vnext_turn_eval_contracts.py tests/test_interview_vnext_turn_eval_loader.py tests/test_interview_vnext_turn_eval_fixtures.py tests/test_interview_vnext_turn_eval_graders.py tests/test_interview_vnext_turn_eval_runner.py
```

### 19.2 Schema determinism/historical freeze

執行 domain/llm/application/eval writers後：

```powershell
git diff --exit-code -- "*.schema.json"
```

測試另須在 temp dirs重生兩次，active files byte-equal，historical files hash未變，目錄無 orphan。

### 19.3 Real PostgreSQL

依 runbook注入 `TEST_DATABASE_URL`：

```powershell
uv run --locked alembic current
uv run --locked pytest -q tests/test_interview_vnext_persistence.py tests/test_interview_vnext_outbox_postgres.py tests/test_interview_vnext_fixed_replay_postgres.py tests/test_interview_vnext_recovery_postgres.py tests/test_interview_vnext_turn_eval_postgres.py tests/test_interview_vnext_turn_eval_openrouter.py
uv run --locked pytest -q tests/test_interview_vnext_*
```

第二條要求 **0 skipped / 0 failed**。不能因 DB daemon沒跑自行 skip；依 runbook啟動只需服務，交付時回報容器狀態。

### 19.4 Full/no-network/hygiene

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
uv run --locked pytest -q
uv run --locked pytest -q tests/test_interview_vnext_dependencies.py
uv run --locked alembic heads
git diff --check
rg -n "evals\.interview_vnext" app
rg -n "OPENROUTER_API_KEY|Authorization:|Bearer |sk-or-" app evals tests
git status --short
```

成功條件：full no-network 0 fail、沒有把原測試改成新增 skip、Alembic只有 `0010 (head)`、app無 eval import、無 secret/output
bundle/migration 0011進 staged files。

---

## 20. Stop conditions：遇到就回報，不得猜

1. 任何必要 authority無法存在 state_json，實作者認為要 0011；
2. portable schema無法表達 flat answer binding；
3. 必須改 provider route/cache/conformance才會綠；
4. 必須讓 model看/產 UUID、hash或 domain ID；
5. 只能靠 dual reader、temporary shim或提交已知紅 suite完成；
6. State v3 validator無法在不讀外部資料下閉合 frame/receipt/Evidence；
7. concurrent state只能自動 rebase，無法 typed fail；
8. provider_completed recovery必須重打 network；
9. eval 12 cases不能在不改語意標籤下機械遷移；
10. test/eval DB含不可依 tenant scope清除的資料；
11. provider adapter開始需要 domain frame/verifier邏輯；
12. committed v1 historical schema必須被改寫才能繼續。

---

## 21. Definition of Done

- [ ] Evidence.v3/State.v3/commands/events/reduction唯一 active，v1/v2 historical frozen；
- [ ] QuestionFrame從 consultant append到employee bind/consume/stale/supersede完整閉合；
- [ ] literal/contextual support全 consumer可區分，contextual「是」不偽裝 literal claim；
- [ ] input/output/report v2無 domain identity且 deterministic；
- [ ] zero-Evidence success有 receipt/state/event，不走 no-op；
- [ ] provider/operation failure無 receipt；
- [ ] context state version/hash參與 CAS，stale fail closed不 rebase；
- [ ] recovery不重打已完成 provider call、不重複 domain writes；
- [ ] persistence正確區分 unsupported major與 corruption；
- [ ] eval v2 suite/11 schemas/hash完成機械 hard cut，舊 v1 frozen；
- [ ] R4 OpenRouter/OpenAI reference regression不漂；
- [ ] minimum Capture roots閉合；
- [ ] focused、full no-network、全部 vNext real PG gates全綠；
- [ ] Alembic仍0010，無新 dependency、secret、paid live、production/Web/editor改動；
- [ ] code只在全部 gate綠後以一個 atomic commit提交，作者/提交者只顯示專案 owner；
- [ ] 未 push。

全部成立才解鎖 R5-D correctness closure。R5-D 完成後才可做 R5-E status handoff；R6才做真模型多 trial品質判斷。

---

## 22. 實作者交付回報格式

1. baseline HEAD、worktree、DB rows/version盤點；
2. atomic commit SHA/subject/author/committer；
3. active/historical domain/LLM/application/eval schema清單與 hashes；
4. Evidence.v3 direct consumer遷移數與確認無 v2 fallback；
5. State v3 closure、commands/events/reducer exact tests；
6. context/input/output/report/prompt/policy/operation versions與 hashes；
7. `support_kind` literal/contextual投影與防偽引文測試；
8. short answer/literal/mixed/frequency/time/zero-Evidence focused數字；
9. receipt/frame consume與 domain event順序證據；
10. state stale時HTTP call/domain write數；
11. fresh-process各 checkpoint network call數；
12. unsupported persisted major/corruption分類測試；
13. Capture roots與 minimum corruption測試；
14. eval suite ID/new hash、12 case IDs/split/reference gate；
15. OpenRouter/OpenAI adapter focused回歸數字；
16.完整 no-network exact passed/skipped/failed與 baseline delta；
17.全部 vNext real PostgreSQL exact passed/skipped/failed；
18. schema/dependency/secret/diff/Alembic gates；
19. DB/container/output cleanup狀態；
20. 未完成項、是否解鎖 R5-D；
21. 明確確認未跑 paid live、未接 production/Web/editor、未 push。
