# Interview AI vNext V3-5A R5-BC Phase 3.5 Corrective——Production Closure 與續作交接規格

- 日期：2026-07-22
- 狀態：**Completed locally；C1–C6、Phase 4與全部final gates已完成，交付於包含本文件的R5-BC atomic commit**
- Review 基線：`9e9dba1` 加上目前尚未提交的 R5-BC working tree
- 上位決策：[`../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md`](../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)
- R5 amendment：[`2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md`](2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md)
- R5-BC 母計畫：[`2026-07-22-interview-vnext-v3-5a-r5-bc-domain-context-hard-cut-plan.md`](2026-07-22-interview-vnext-v3-5a-r5-bc-domain-context-hard-cut-plan.md)
- Scope：**先修 code review 已證實的 Phase 1–3 closure，再續作 Phase 4；不新增產品功能或新架構層**

本文件是 R5-BC 實作中的 corrective addendum。它不重寫 ADR 0037、R5 amendment 或 R5-BC 母計畫，只對目前
未提交 working tree 中已證實的缺口、修正順序與驗收向量作更精確的施工裁決。

若本文件與實作者先前口頭進度回報衝突，以目前 working tree、可重現測試與本文件為準；若與 ADR 0037 衝突，仍以 ADR
0037 為準。R5-BC 仍維持母計畫規定的 **single atomic code commit**：本 corrective 完成前不得提交半套 hard cut。

---

## 1. 白話結論

目前不應丟掉既有工作，也不應直接從 `fixture_builder.py` 繼續 Phase 4。

已完成的 Evidence.v3、State.v3、QuestionFrame、receipt、Context v2 與 executor WIP 方向大致正確，但 code review 發現：

1. 現有 focused tests 尚未搬完，當前工作樹不是 green tree；
2. production `ContextBuilder` 還有 Evidence v2 欄位存取，測試搬完後會 runtime crash；
3. verifier 仍缺 exact marker、false-specificity、duplicate all-drop 與 system insufficiency；
4. stale-context 只在 transaction 外預檢，仍有最後一段 race 會漏成 generic conflict；
5. outcome 與 Capture 尚未形成母計畫要求的 artifact closure；
6. 先前宣稱存在的 implementation record 不在 Git 可見路徑。

因此下一輪先做 **Phase 3.5 corrective**。Phase 3.5 不是新功能，也不是再重構一次；它只把已核准的 R5-BC 設計真正
接通並用測試封口。Phase 3.5 全綠後，才回到母計畫 §15.3 的 interleaved eval replay。

---

## 2. Authority 與本文件只覆寫什麼

### 2.1 Authority 順序

1. ADR 0037 的 employee authority、QuestionFrame、Evidence support 與 receipt invariant；
2. 本文件對目前 review findings 的唯一最小修法與續作順序；
3. R5-BC 母計畫其餘 hard-cut、artifact、eval 與 gate 規格；
4. R5 amendment 未被後續文件 refinement 的欄位與 verifier 規則；
5. 舊 runtime reconstruction plan 只在 R5 amendment 明文沿用處生效。

### 2.2 本文件覆寫的唯一流程裁決

母計畫原順序是 Phase 1 → 2 → 3 → 4。現在改為：

```text
既有 Phase 1–3 WIP
  -> Phase 3.5 production corrective
  -> Phase 1–3 gate 重新全綠
  -> Phase 4 eval/provider mechanical migration
  -> Phase 5 atomic gate + one code commit
```

不允許跳過 Phase 3.5，直接用 eval fixture 或 adapter shim 掩蓋 production 缺口。

---

## 3. Review snapshot 與可重現證據

### 3.1 工作樹狀態

Review 時：

- branch：`research/llm-interview-integration`；
- HEAD：`9e9dba1 docs(interview): resolve prior-turn fixture receipt replay`；
- R5-BC code 尚未 commit；
- tracked modified 與 untracked active schemas/policies 合計 49 個 paths；
- `git diff --check` 無 whitespace error，只有 Windows autocrlf warnings；
- 沒有發現 `r5bc-implementation-record.md`。

`git diff --check` clean 只代表文字格式沒有破損，不代表測試或 runtime 已閉合。

### 3.2 實際 focused test 結果

從 `apps/api` 執行：

```powershell
uv run pytest tests/test_interview_vnext_context_builder.py -q
```

結果：

```text
7 failed / 1 passed
```

第一層失敗是 test fixtures 仍用 Evidence v2 的 `turn_id/quote/span` constructor，尚未建立 v3 `support`。這是已知遷移未完，
但它也遮住 production `ContextBuilder` 仍讀 `item.turn_id` 的下一層錯誤。

再執行：

```powershell
uv run pytest tests/test_interview_vnext_turn_interpret.py -q
```

結果在 collection 階段失敗，因測試仍 import 已移除的 `derive_evidence_id`。因此目前不能引用 Phase 0 的舊 baseline 數字，宣稱
當前 tree 已通過同一套 focused tests。

### 3.3 已證實的 production 欄位錯誤

Evidence.v3 唯一 source accessor 是：

```python
evidence.source_turn_id
```

但 `application/context_builder.py` 的 turn context 與 episode context 排序仍各有一處：

```python
turn_sequences[item.turn_id]
```

Evidence.v3 沒有相容 property `turn_id`，也不應新增。正確修法是把 consumer 搬到 `source_turn_id`，不是把 v2 欄位加回 domain。

---

## 4. 硬邊界：本 corrective 明確不做

為避免過度設計，Phase 3.5 **不得**：

- 新增 SQL table、column、index、FK 或 migration `0011`；
- 新增 dependency、agent framework、graph framework、event-sourcing framework 或 marker/NLP 套件；
- 建立第二套 Context Engine、第二套 verifier、第二套 Capture writer；
- 引入通用 workflow DSL、通用 rule engine 或 provider-independent super-framework；
- 改 OpenRouter/OpenAI HTTP body、retry、route、cache、cost、conformance 或 adapter promotion；
- 新增 Anthropic direct provider；
- 讓 provider 看見 UUID、state hash、frame ID、artifact ref 或 domain ID；
- 恢復 Evidence v2 欄位、dual reader、temporary compatibility shim；
- 自動 repair、trim、NFKC、模糊比對、猜 occurrence、猜 target；
- 修改 TI-09/TI-10 transcript 語意或放寬「每 employee turn 一筆 receipt」invariant；
- 實作 editor、Web、SaaS、company catalog、JD canvas 或共編功能；
- 跑 paid live、OpenRouter catalog 或 12×3 batch；
- 以「之後 R5-D 再處理」為由省略本文件列出的 R5-BC minimum closure。

允許的新增只限於：必要的 typed field／small pure helper／typed internal exception／artifact ref／測試向量與本文件明列的 eval v2
機械遷移。

---

## 5. 修正後仍然是同一個簡單架構

Phase 3.5 不增加新 layer。唯一資料流仍是：

```text
persisted InterviewState.v3
  -> ContextBuilder v2
  -> provider-safe TurnInterpretInput.v2
  -> one governed LLM call
  -> TurnInterpretOutput.v2
  -> deterministic verifier/materializer
  -> TurnInterpretationRecord + Evidence.v3[]
  -> ApplyTurnInterpretationCommand
  -> state-version/hash CAS
  -> typed outcome + Capture roots
```

責任邊界不變：

- LLM 只提出 interpretation proposal；
- application verifier 決定 proposal 是否有 literal/contextual support；
- domain reducer 決定 aggregate 是否可合法提交；
- persistence 負責 CAS 與 durable artifacts/events；
- eval 只重播和評分，不擁有 production semantics；
- provider adapter 只處理 wire protocol，不判 JD／QuestionFrame／Evidence eligibility。

---

## 6. Corrective A：先讓 v3 consumers 與 focused tests 真正執行

### 6.1 Test fixtures 的唯一搬法

所有建立 Evidence 的 test helper 必須改成 v3 `support`：

```text
literal evidence
  -> LiteralEmployeeSpanSupport(employee_turn_id, quote, span, quote_match=exact)

contextual evidence
  -> ContextualAnswerSupport(employee_turn_id, answer_quote/span,
                              question_frame_definition_hash,
                              target ordinal/hash, binding kind/resolution)
```

禁止在 test helper 加 `**legacy_fields`、converter 或 monkeypatch。測試必須和 production contract 使用同一個 Evidence.v3 constructor。

`test_interview_vnext_turn_interpret.py` 必須改 import：

- literal ID：`literal_evidence_id(operation_id, original_index)`；
- contextual ID：`contextual_evidence_id(operation_id, binding_index, materialization_index)`；
- proposal/binding ref 使用 R5 amendment §10.1 的 `p0001`／`b0001` pure derivation；
- 不在測試內重寫另一份 UUIDv5 算法。

### 6.2 Production consumer hard cut

`ContextBuilder` 兩條 Evidence 排序路徑都改成：

```python
turn_sequences[item.source_turn_id]
```

同一輪以 `rg` 檢查 production/eval/tests 中所有 Evidence source consumer：

```powershell
rg -n "evidence\.turn_id|item\.turn_id|\.quote|\.span" app/interview_vnext evals/interview_vnext tests
```

不能機械地把所有 `.quote/.span` 都取代；必須依 `support_kind` 分流：

- literal 顯示 `support.quote/span`；
- contextual 顯示 `support.answer_quote/answer_span`；
- 不得提供會把 contextual claim 偽裝成 employee literal quote 的 convenience property。

### 6.3 Context source content hash 必須真正 seal 來源

R5 amendment §8.1 明訂 QuestionFrame source：

```text
source_type = question_frame
source_id = question_frame_id
state_hash = context.state_hash
content_hash = canonical_hash(question_frame)
```

Evidence source 同理使用 `canonical_hash(Evidence.v3)`。目前 `ContextSourceRef` 只有 container hash，尚未保存 source content hash。

最小修法：

1. 在 active Context v2 的 `ContextSourceRef` 增加 `content_hash: Sha256 | null`；
2. `question_frame` 與 `evidence` source 必須 non-null；
3. `ContextQuestionFrame` validator 驗 `source.content_hash == canonical_hash(frame)`；
4. `ContextEvidenceItem` validator 驗 `source.content_hash == canonical_hash(evidence)`；
5. builder 建 selected/excluded frame/evidence source 時都填同一 authoritative hash；
6. `ContextItemDecision.content_hash` 對 frame/evidence 也必須等於 authoritative object hash，不得因 selected wrapper 不同而改變；
7. frame snapshot artifact content hash必須等於 packet source hash與 manifest decision hash。

`ContextSourceRef.content_hash` 在 Phase 3.5 的 exact matrix：

| source type | content_hash |
|---|---|
| `question_frame` | required；`canonical_hash(QuestionFrame)` |
| `evidence` | required；`canonical_hash(Evidence.v3)` |
| `policy` | null；仍由 policy identity/hash欄位負責 |
| `reference` | null；仍由 `reference_snapshot_hash` 與 snippet自身hash負責 |
| 其他 working-state source | null；`ContextItemDecision.content_hash` 沿用既有authority，不在本 corrective擴張 |

這個 matrix 是刻意收斂：不趁機把所有 Context source 重做成新 lineage system。

不新增第二個 `SourceRefV2` class，不把整份 state hash冒充 source content hash，也不 hash `ContextEvidenceItem` wrapper 取代
Evidence authority。

### 6.4 Corrective A 驗收

至少新增／修正向量：

- literal Evidence.v3 可建 turn context；
- contextual Evidence.v3 可建 turn context；
- 兩種 support 都依 `source_turn_id` 排序；
- collection iteration 反轉後 packet/manifest/budget bytes 相同；
- selected 與 excluded 的同一 Evidence source content hash相同；
- eligible frame source hash = frame snapshot artifact hash；
- 竄改 frame/evidence source content hash，model validation fail closed；
- episode context 不再存取 removed `turn_id`。

完成標準：

```powershell
uv run --locked pytest -q tests/test_interview_vnext_context_builder.py
```

必須 `0 failed / 0 skipped`，而且測試已真的走過 non-empty Evidence collection。

---

## 7. Corrective B：補齊 verifier v2，不建立通用 rule engine

### 7.1 Verification identity 必須先派生、drop 不重編

依 R5 amendment §10.1，active report 必須補齊：

```text
ObservationVerification.v2
  proposal_index
  proposal_ref                    # p0001
  candidate_evidence_id           # literal UUIDv5，accepted/rejected 都保留
  accepted
  reason_codes
  computed_span
  evidence|null

AnswerBindingVerification.v1
  binding_index
  binding_ref                     # b0001
  candidate_evidence_ids          # 依 target/option 預派生
  accepted
  reason_codes
  computed_answer_span
  materialized_evidence
```

流程固定：

1. 先按 model output 原始位置派生 refs/IDs；
2. 再跑 quote、frame、qualifier、duplicate、insufficiency、domain gates；
3. rejected decision 保留 candidate identity；
4. 不因前一筆被 drop 而重編後一筆；
5. choice candidate/materialization 依 option ordinal，不依 set/dict iteration。

不得把 candidate IDs 放進 provider input/output；它們只存在 application report/artifact。

### 7.2 Stable reject codes

Binding path 至少使用 R5 amendment §10.3 的 exact public values：

```text
binding_without_question_frame
binding_target_out_of_range
binding_kind_mismatch
binding_resolution_incoherent
binding_quote_not_found
binding_quote_occurrence_out_of_range
binding_value_not_supported
choice_selection_invalid
duplicate_binding_target
question_frame_not_eligible
question_frame_hash_mismatch
contextual_materialization_failed
```

現有 `question_frame_unavailable`、`unknown_target_ordinal`、`unknown_choice_ordinal`、`duplicate_target_binding`、
`slot_value_not_in_answer` 若只是尚未發布的 WIP 名稱，直接在本 atomic hard cut 收斂，不保留 alias 或 dual values。

Observation path 保留已核准的 quote／qualifier／correction codes，另補母規格要求的 `duplicate_observation` 與
`insufficiency_incoherent`。reason tuple 一律依 policy `reject_order`，不按字母排序。

### 7.3 Marker policy 只有一份 authority

目前 marker tables 寫死在 `application/turn_interpret.py`，但 active verifier policy JSON 沒有保存完整 marker set。修正後：

- `TURN_INTERPRET_VERIFIER_POLICY_V2` typed definition 是 runtime authority；
- `turn-interpret-verifier.2.0.0.json` 是同一物件的 deterministic export；
- application verifier 從該 typed policy 讀 marker maps；
- 不在 prompt、adapter、eval grader 再複製一份 runtime marker authority。

Policy 必須包含 R5 amendment §11 的 exact time/frequency/typicality/polarity/importance/ownership patterns，包含：

```text
只有.*才
我和.*共同
與.*共同
支援.*處理
daily / weekly / monthly / quarterly / annually / yearly / as needed
currently / right now / at present / previously / used to
```

Typed policy只需六個明確 maps，不建立 generic expression AST：

```text
time_scope_markers
frequency_markers
typicality_markers
polarity_markers
importance_markers
ownership_markers
```

JSON key使用各 domain enum的 serialized value，value是 ordered regex string tuple。unknown／not_stated沒有 marker entry；runtime
不得用 dictionary缺 key推導另一個 semantic default。

最小 matcher 即可，禁止引入 rule-engine 套件：

```text
re.search(pattern, original_text,
          IGNORECASE only when pattern is ASCII)
```

- Unicode pattern 不做 case folding；
- ASCII English pattern case-insensitive；
- 不 trim、不 NFKC、不改寫 employee text；
- regex pattern 直接來自 sealed policy；
- policy load 時先 compile 全部 regex，invalid pattern 直接 validation failure；
- 不做 fuzzy matching、stemming、斷詞或同義詞擴充。

### 7.4 Literal qualifier exact-support／false-specificity

每個 literal observation qualifier 必須同時滿足：

1. support 是 observation quote 的 exact substring；
2. specific value 必須由該 support 中對應 dimension 的 marker 支持；
3. unknown/not-stated value 不得帶 specific support；
4. support 若同時命中互斥 canonical values，整筆 observation drop；
5. frequency value/unit/verbatim 必須互相一致；
6. frequency 不得單獨證明 `time_scope=current`。

必要反例：

```text
time_scope=current + support="以前"             -> invalid qualifier
ownership=owner + support="我不負責"            -> invalid qualifier
importance=explicit_core + support="協助性"      -> invalid qualifier
time_scope=unknown + support="目前"              -> invalid qualifier
frequency=per_week + time_scope=unknown + "每週" -> valid
"以前每週" -> time=past, frequency=per_week
```

`polarity=affirmed` 可由 exact affirmative clause support，但 support 不得含 denial/uncertainty marker；`uncertain` 在沒有特定
marker 時可維持 support null，不能因缺 marker 自動改成 affirmed。

### 7.5 Contextual typed slot 必須掃完整 answer quote

typed slot parser 仍是 local small pure functions，不新增 parser service。

對 frequency／ownership／importance／time_scope／typicality：

- `value_text` 必須由 exactly one canonical value支持；
- verifier 同時掃完整 `answer_quote`；
- answer quote 若還有另一個互斥 value，不能讓 model 用較短 `value_text` 隱藏衝突；
- conflict 一律 `binding_value_not_supported`，零 Evidence；
- free-text slot 只允許 exact value replacement，不推定 qualifier。

Frequency v1 exact：

- count 要掃 `value_text` 與完整 `answer_quote`；
- 支援 ASCII decimal + `次|times`，以及一、二／兩、三至十 + `次`；
- count 必須 `> 0`；
- `每月2次` 合法；
- `每月2次或3次`、`2-3次`、`每兩週一次`、多 unit、irregular + count 全部 fail closed；
- 不把 interval 換算成 rate，也不擅自補 1。

### 7.6 Duplicate all-drop

先算完整 output 的 fingerprints，再驗每筆；不得邊走邊保留 first。

Literal fingerprint：

```text
subject, kind, claim, quote, quote_occurrence,
correction target ordinals, target_unknown
```

Binding fingerprint：

```text
target ordinal, kind, resolution, answer quote, occurrence,
value_text, selected choice ordinals
```

規則：

- fingerprint 重複：所有該 fingerprint decisions drop；
- 多個 resolved bindings claim 同一 target：所有該 target bindings drop；
- ambiguous/unknown binding 不和 resolved binding搶 target；
- duplicate drop 後 candidate refs/IDs 不重編；
- 不跨 turn、state 或 prior Evidence 做 semantic dedup；那不是 Turn Interpreter 的責任。

### 7.7 System insufficiency 的最小 deterministic mapping

`model_insufficiency_codes` 原樣保存但必須通過 scope/coherence；`system_insufficiency_codes` 只由 verifier 可證明的失敗產生。

最小 mapping：

| Deterministic fact | system code |
|---|---|
| accepted ambiguous/unknown answer binding | `answer_binding_ambiguous` |
| frequency value conflict/parse failure | `ambiguous_frequency` |
| ownership value conflict/parse failure | `ambiguous_ownership` |
| time-scope value conflict/parse failure | `ambiguous_time_scope` |
| invalid/ambiguous choice selection | `choice_selection_ambiguous` |
| correction target_unknown | `correction_target_unknown` |
| binding attempted but no active frame pointer | `question_frame_missing` |
| frame存在但不是 immediately preceding answer scope | `question_frame_not_immediate` |
| frame status/hash/source/text不再可信 | `question_frame_stale` |

為了區分最後三種，Context v2 packet 可新增一個 application-only、provider projection 不輸出的
`question_frame_limitation` stable field；值只能來自 `ContextBuilder` 現有 eligibility branches。不要再建立 FrameEligibility service。

只有 output 真正提出 answer binding 時才因 frame unavailable 加上述 system code；純 standalone literal observation 不因沒有 frame
被標成 insufficiency。

最終 `TurnInterpretationRecord.insufficiency_codes`：

```text
model codes ∪ system codes
-> unique
-> domain TurnInsufficiencyCode declaration order
```

不得按字母排序，也不得只保存其中一側。

### 7.8 Verifier 不得做的事

- 不因一筆 proposal 錯誤回滾另一筆獨立有效 proposal；
- 不把 invalid binding 降級成 literal observation；
- 不修 model JSON；
- 不替 model 猜 quote occurrence；
- 不用公版／向量檢索補 employee evidence；
- 不因 action 看起來合理就自動產 output/K/S；
- 不做 JD completeness；那屬於後續 agenda/gap/document workflow。

---

## 8. Corrective C：stale-context 必須在最後 transaction boundary typed fail

### 8.1 現況問題

目前 `_commit_report` 先在 transaction 外讀 latest state，比對 `context.state_version/hash`；通過後再呼叫
`commit_verified_operation()`。

如果 state 在兩者之間改變，durable boundary 可能拋：

```text
CheckpointConflict
StateVersionConflict
DomainViolation(state_version_conflict)
```

這雖然不會錯寫 state，卻不符合母計畫 §13.2：正常併發前進必須成為 deterministic terminal
`state_context_stale`，不能漏成 harness/application exception。

### 8.2 核准的最小修法

不新增 saga、lock manager 或 transaction framework。只增加一個 application/persistence internal typed stale signal，例如：

```text
StateContextStale
  expected_state_version/hash
  actual_state_version/hash（可在 rollback 後重新讀取補齊）
```

流程：

```text
_commit_report
  -> command.expected_state_version = context.state_version
  -> commit_verified_operation(transaction)
       -> load state
       -> compare context/checkpoint version + hash
       -> reducer
       -> CAS
       -> any mismatch: rollback / raise StateContextStale
  -> catch StateContextStale
       -> reload only for actual diagnostic values
       -> persist deterministic state_context_stale failure artifact
       -> terminal fail checkpoint
       -> return typed failed outcome
```

重要限制：

- transaction 外可為 diagnostics 讀 state，但不可用它重建／rebase command；
- expected version/hash永遠來自 provider實際看過的 context；
- mismatch 後 domain state/event/receipt/command/reduction都不能寫入；
- provider call count仍為1；
- 不 retry、不換 operation ID、不自動重跑新 context；
- failure artifact ID與 event ID仍由 operation ID deterministic 派生；
- persisted corruption 與 stale context必須是不同 exception/reason。

### 8.3 必測 race windows

real PostgreSQL 至少測：

1. provider call後、進 `_commit_report` 前 state advance；
2. transaction外預檢後、transaction內 state load前 state advance；
3. transaction內 state load後、CAS前競爭 update；
4. stale path重呼叫同 operation，0 network、回同 terminal failure；
5. stale path provider calls=1、receipt=0、domain events=0、command rows=0；
6. tampered state/hash仍是 corruption，不可誤標 stale。

不允許以 sleep 當唯一 race control；使用 barrier/event 或 repository test seam deterministic 排程。

---

## 9. Corrective D：Outcome 與 Capture minimum closure

### 9.1 Outcome v2 保留便利欄位，但補 authoritative refs

為避免為了 `checkpoint_ref` 再創造一個沒有必要的 checkpoint artifact，本 corrective 明確化：

- `OperationCheckpoint.v2` 仍是 durable DB DTO，outcome 可保留嵌入 `checkpoint`；
- 不新增 checkpoint artifact kind/table；
- outcome 必須另外保存目前已存在或本次建立的 authoritative artifact refs。

`TurnInterpretExecutionOutcome.v2` committed path 至少包含：

```text
status = committed
checkpoint: OperationCheckpoint.v2
context_packet_ref
input_ref
provider_result_ref
verification_report_ref
interpretation_record_ref
domain_command_ref
reduction_result_ref
turn_output_ref
interpretation: TurnInterpretationRecord.v1
accepted_evidence: Evidence.v3[]
provider_result / verification_report / reduction_result  # 可保留既有 runtime convenience
noop_result = null
reason_code = null
```

若保留 embedded convenience object，validator 必須驗其 canonical hash等於對應 ref content hash；不能讓 ref 與 embedded payload各說
各話。failed/pending path只要求該 stage 實際存在的 refs，不得合成尚未產生的 artifact。

### 9.2 Exact artifact kinds

Turn Interpreter active v2 路徑使用：

| Payload | kind |
|---|---|
| eligible frame snapshot | `interview.question_frame_snapshot.v1` |
| context packet | `interview.context_packet.v2` |
| context selection manifest | `interview.context_selection_manifest.v2` |
| context budget report | `interview.context_budget_report.v2` |
| provider-safe input | `interview.turn_interpret_input.v2` |
| parsed local output | `interview.turn_interpret_output.v2` |
| semantic report | `interview.turn_interpret_verification_report.v2` |
| durable receipt | `interview.turn_interpretation_record.v1` |
| domain command | `interview.apply_turn_interpretation_command.v1` |
| reduction | `interview.reduction_result.v2` |
| terminal application outcome | `interview.turn_interpret_execution_outcome.v2` |

Prompt、portable schema、provider binding/config/projection、request/result/evidence/conformance 的既有 R3/R4 kind 不在此改名。

不建立 artifact-kind registry framework。可在現有 module 使用 local constants／small mapping；generic durable command path若需要保留舊
kind，僅對 `ApplyTurnInterpretationCommand` 走 exact active kind。

### 9.3 Record 與 domain refs 的最小 durable 作法

`ApplyTurnInterpretationCommand` 已嵌入 receipt，但 Capture 仍需要獨立 receipt artifact。最小修改：

1. `_commit_report` 先建立 deterministic receipt artifact；
2. `commit_verified_operation` 增加 narrow `additional_domain_artifacts` 或等價參數；
3. receipt、command、reduction 與 state transition 在同一 transaction put/commit；
4. commit return 必須把 command/reduction/receipt refs交回 executor；
5. duplicate/recovery path載回相同 deterministic refs，不重建不同 bytes；
6. 不把這個 seam擴大成任意 plugin artifact pipeline。

### 9.4 Outcome artifact 與 run finalization

目前 production route尚未接線，R5-BC 的 terminal orchestrator 是 eval `turn_eval_runner`。因此：

- `execute_turn_interpret()` 回傳 byte-stable outcome closure；
- `turn_eval_runner` 以 deterministic artifact ID保存 outcome，kind使用上表 exact value；
- runner 把 outcome、frame/context/input、provider gate、report、receipt、command、reduction/output refs列為 roots；
- `finalize_run()` terminal event 的 `input_artifacts` 使用同一組已驗證 roots，不再產空 terminal event；
- manifest只列真實已 put 且 scope/hash驗證通過的 refs；
- failed stale path roots至少可達原 context、input、report（若已存在）、failure artifact與outcome；
- receipt-only success roots仍可達 receipt、command、reduction、outcome，即使 Evidence=0。

不在 Phase 3.5 建 production API/Web composition root。未來正式 route使用同一 executor/outcome contracts，不另外複製 runner semantics。

### 9.5 Recovery closure

fresh-process recovery 必須：

- `provider_completed`／`verified`／`committed`：0 network；
- 載入每個 ref時重驗 tenant/run/session/turn/operation scope、kind、schema、content hash；
- committed reduction中找不到該 operation receipt時，拋 `PersistedDataCorruption`，不得讓 Pydantic `ValidationError` 外洩；
- 首次與 recovery outcome 的 authoritative refs及 embedded payload bytes一致；
- crash after domain commit、before outcome artifact時，可由 deterministic refs補存同一 outcome，不重複 receipt/events；
- missing/tampered receipt/report/command/reduction/outcome fail closed。

R5-D 仍負責完整 bundle corruption/re-export matrix；Phase 3.5 只完成上述 R5-BC minimum closure。

---

## 10. 實作順序：不可直接跳到 fixture builder

### C0——建立可見的 implementation record

不要在 repo root或 gitignored output建立孤立 `r5bc-implementation-record.md`。直接在本文件最後的 §17 逐輪追加：

- 起始 HEAD與 `git status --short`；
- 已完成 slice；
- 實際命令與 exact pass/fail/skip；
- 尚未完成項；
- 任何裁決偏差；
- Docker/DB本機狀態；
- commit前 staged secret/migration檢查。

C0 只記錄，不改 production behavior。

### C1——先遷移 Context/Turn focused tests並修 v3 consumers

檔案：

- `tests/test_interview_vnext_context_builder.py`
- `tests/test_interview_vnext_turn_interpret.py`
- test fixture helper（若已有共用 helper，沿用；不得再建第二份）
- `application/context_builder.py`
- `llm/context.py`

完成 §6，全綠才進 C2；仍不 commit。

### C2——Verification report、policy 與 identity

檔案：

- `llm/turn_interpret.py`
- `llm/write_verifier_policies.py`
- `llm/verifier_policies/turn-interpret-verifier.2.0.0.json`
- `domain/turn_identity.py`
- `application/turn_interpret.py`
- active v2 schema fixtures

先補 refs/candidate IDs/reason codes與 sealed marker policy，再寫 pure tests；不要同時碰 executor/PG。

### C3——Verifier behavior vectors

完成 §7.4–§7.7：

- exact support；
- regex/English flags；
- full-answer conflict scan；
- duplicate all-drop；
- system insufficiency；
- literal/contextual/mixed獨立 drop。

所有 verifier tests全綠後才進 transaction code。

### C4——Stale CAS transaction closure

檔案：

- `application/operation_executor.py`
- `application/durable_operations.py`
- `persistence/errors.py`（或既有 application exception owner）
- `tests/test_interview_vnext_recovery_postgres.py`
- turn-executor相關 PostgreSQL tests

只做 §8；不碰 provider adapter。

### C5——Outcome/artifact/Capture closure

檔案：

- `application/operation_executor.py`
- `application/durable_commands.py`
- `application/durable_operations.py`
- `application/schema_exports.py`
- `persistence/capture.py`
- `evals/interview_vnext/turn_eval_runner.py`
- Capture/recovery/runner tests

完成 §9 exact kinds、refs、terminal roots與recovery。

### C6——Phase 1–3 re-baseline

執行 §14 的 focused、schema、no-network、real PostgreSQL gates。任何 failure 都在 Phase 3.5 修正，不得把 failure 推給 Phase 4。

### C7——回到母計畫 Phase 4

只有 C6 全綠後才從母計畫 §15.3.3 開始：

```text
fixture_builder interleaved replay
  -> deterministic prior interpretation seeds
  -> loader/graders
  -> remaining eval modules
  -> 12 fixture JSON + suite hash
  -> OpenRouter/OpenAI reference schema mechanical migration
```

TI-09/TI-10 裁決不變：合成 prior interpretation receipt；不放寬 State v3、不改 transcript。

---

## 11. File responsibility matrix

| File/area | 本 corrective 的唯一責任 |
|---|---|
| `domain/evidence.py` | Evidence.v3 authority；不加回 v2 convenience fields |
| `domain/turn_identity.py` | proposal/binding/evidence deterministic identity pure functions |
| `llm/context.py` | Context v2 source content hash與frame limitation contract |
| `application/context_builder.py` | source_turn排序、eligible frame/evidence exact source hashes |
| `llm/turn_interpret.py` | provider-neutral input/output/report/policy typed contracts |
| `application/turn_interpret.py` | deterministic semantic gates/materialization；不做 provider wire |
| `operation_executor.py` | orchestration、typed stale outcome、artifact refs |
| `durable_operations.py` | transaction boundary、CAS、narrow domain artifact closure |
| `persistence/capture.py` | terminal event + manifest exact roots；不解析 semantics |
| `evals/.../fixture_builder.py` | Phase 4 interleaved replay；不擁有 verifier rules |
| provider adapters | 只換 active output schema/hash；不實作 frame/marker logic |
| graders | 評估結果；不改 production accepted decisions |

若同一規則同時出現在 application verifier與 eval grader，grader只能讀／比較 production report，不可重新成為 eligibility authority。

---

## 12. 必要測試向量

### 12.1 Context

- Evidence v3 literal/contextual source ordering；
- selected/excluded canonical source hash；
- eligible/missing/stale/not-immediate frame；
- frame source hash與snapshot hash；
- provider projection無 UUID/hash/ref；
- reversed collections byte-equal；
- frame超 budget hard fail、不截斷。

### 12.2 Literal verifier

- duplicate quote occurrence exact；
- false-specific time/ownership/importance；
- frequency與time scope獨立；
- Unicode regex與ASCII case-insensitive English；
- duplicate observation all-drop；
- correction ordinal active/inactive/out-of-range/target_unknown；
- 一筆drop不影響相鄰有效 observation。

### 12.3 Binding verifier

- atomic yes/no；
- frequency/ownership/time/importance/typicality slots；
- single/multi choice；
- target out-of-range；
- kind/resolution mismatch；
- value exact substring；
- full answer互斥 marker；
- duplicate fingerprint與duplicate target all-drop；
- ambiguous/unknown accepted但 Evidence=0；
- missing/stale frame binding drop、同 turn literal仍可接受。

### 12.4 Receipt/CAS

- zero-Evidence仍 receipt、state version +1、frame consumed；
- provider/schema/conformance failure無 receipt；
- stale三個 race windows；
- duplicate command idempotent；
- committed fresh-process recovery 0 network；
- missing committed receipt typed corruption。

### 12.5 Capture

- normal Evidence success roots；
- receipt-only success roots；
- stale failure roots；
- terminal event refs = validated manifest roots；
- wrong root hash/missing artifact finalize fail；
- exact artifact kinds/schema IDs；
- secret/reasoning redaction regression不變。

---

## 13. 測試不得只驗「有回傳」

每個 negative vector 至少斷言：

- exact typed exception或stable reason code；
- accepted/rejected decision數；
- candidate IDs沒有重編；
- materialized Evidence exact support kind與source；
- provider call count；
- state version before/after；
- receipt/command/event rows count；
- artifact kind/schema/hash/scope；
- fresh-process network count；
- failure不以 raw `ValidationError`、`KeyError`、`AttributeError` 外洩。

僅斷言 `raises(Exception)`、`outcome.failed` 或 list非空不算完成。

---

## 14. 驗收命令與 gate

全部從 `apps/api`，使用 lock。

### 14.1 Corrective focused

```powershell
uv run --locked pytest -q tests/test_interview_vnext_context_builder.py
uv run --locked pytest -q tests/test_interview_vnext_turn_interpret.py
uv run --locked pytest -q tests/test_interview_vnext_domain.py tests/test_interview_vnext_workflow_reducers.py
uv run --locked pytest -q tests/test_interview_vnext_llm.py tests/test_interview_vnext_capture.py
uv run --locked pytest -q tests/test_interview_vnext_execution_schemas.py tests/test_interview_vnext_schemas.py tests/test_interview_vnext_dependencies.py
```

上述全部要求 `0 failed / 0 skipped`。

### 14.2 Schema determinism

執行 domain/llm/application writers，在兩個 temp dirs各重生一次：

- active v2/v3 files byte-equal；
- committed historical v1 files hash完全不變；
- committed schema目錄無 orphan；
- writer後：

```powershell
git diff --exit-code -- "*.schema.json"
```

若 active untracked schema本來就在此次 atomic commit內，先與 writer output逐 byte比對；不可用上述命令誤把「尚未 staged」當成
historical drift。

### 14.3 Real PostgreSQL focused

依 runbook注入 `TEST_DATABASE_URL`：

```powershell
uv run --locked alembic current
uv run --locked pytest -q tests/test_interview_vnext_persistence.py tests/test_interview_vnext_recovery_postgres.py tests/test_interview_vnext_fixed_replay_postgres.py
```

Phase 4 完成後再加：

```powershell
uv run --locked pytest -q tests/test_interview_vnext_turn_eval_postgres.py tests/test_interview_vnext_turn_eval_openrouter.py
uv run --locked pytest -q tests/test_interview_vnext_*
```

DB gate要求 `0 skipped / 0 failed`。不得因 daemon未啟動自行 skip；依 runbook只啟需要的 PostgreSQL，交付時回報容器狀態。

### 14.4 Full no-network/hygiene

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

成功條件：

- full no-network 0 fail；
- 不把原測試改成新增 skip；
- Alembic current/heads仍只有 `0010 (head)`；
- `app/`不 import `evals.*`；
- 無 `.env`、key、output bundle、DB dump、migration 0011進 staged files；
- 未跑 network/paid live。

---

## 15. Stop conditions：遇到必須回報，不得猜

1. 任何修正被認為必須新增 migration 0011；
2. 必須恢復 Evidence v2欄位或 dual-active schema才可通過；
3. marker語意只能靠第三方 NLP/rule-engine package實作；
4. 必須改 provider route/cache/conformance/HTTP body才會綠；
5. provider input必須加入 UUID/hash/ref；
6. stale context只能自動 rebase或 generic retry；
7. committed recovery必須重打 provider；
8. receipt/command/reduction無法在既有 UoW/transaction seam閉合；
9. outcome closure被迫新增新 table或通用 workflow engine；
10. TI-09/TI-10 無法依已核准 interleaved seed重播且必須改 transcript；
11. historical v1 schema必須改寫；
12. real DB存在不能依 tenant/trial scope處理的非測試資料；
13. 要把 verifier logic放進 provider adapter或 grader；
14. 需要刪除／reset目前 WIP才能續作。

---

## 16. Definition of Done

Phase 3.5 完成必須同時成立：

- Context/Turn focused tests真的使用 Evidence.v3且全綠；
- production/eval/tests沒有 Evidence v2 source欄位殘留；
- frame/evidence Context source content hash exact；
- report refs/candidate IDs/drop identity完整；
- marker policy單一、sealed、deterministic；
- false-specificity、full-answer conflict與duplicate all-drop全有負向測試；
- system insufficiency deterministic且record保存model ∪ system；
- stale所有 race windows回 typed `state_context_stale`；
- normal stale不外洩 generic persistence/domain exception；
- outcome含必要 refs，embedded payload與refs hash一致；
- exact R5-BC artifact kinds落地；
- success/receipt-only/stale manifests closure全綠；
- committed recovery 0 network且不重複 receipt/events；
- focused no-network、schema、real PG gates全綠；
- 無 migration/dependency/provider behavior變更；
- §17 implementation record已回填實際證據。

上述完成只解鎖 Phase 4；不代表 R5-BC atomic commit可以提前建立。Phase 4與母計畫 Phase 5 gates仍必須完成。

---

## 17. 實作紀錄與交付回報模板

實作者每輪直接在本節追加，不建立未追蹤的外部紀錄。

### 2026-07-22 / reviewer handoff baseline

```text
HEAD / branch:
  9e9dba1 / research/llm-interview-integration

working tree before this docs addendum:
  R5-BC code WIP未提交；tracked modified + active untracked contract files共49 paths

review actions:
  read-only code/contract review
  實跑 ContextBuilder與Turn Interpreter focused tests
  未修改production/eval/test code
  新增本corrective文件並更新母計畫/文件索引

focused evidence:
  uv run pytest tests/test_interview_vnext_context_builder.py -q
    -> 7 failed / 1 passed
    -> first failure: tests仍以Evidence.v2 constructor建立資料
  uv run pytest tests/test_interview_vnext_turn_interpret.py -q
    -> collection error
    -> tests仍import已移除derive_evidence_id

production findings:
  ContextBuilder兩條Evidence排序仍讀removed item.turn_id
  ContextSourceRef缺R5要求的frame/evidence content_hash closure
  verifier缺exact marker/false-specificity/full-answer scan/duplicate all-drop/system insufficiency
  stale check仍有transaction race到generic conflict的窗口
  outcome/artifact kinds/manifest roots尚未完成R5-BC minimum closure

schema / DB / network:
  本review未執行schema writer、未改DB、未跑network/paid live

commit status:
  無commit、無push；R5-BC仍須single atomic code commit
```

後續實作者從下一個小節開始追加。

### 2026-07-22 / C0 implementation resume

```text
HEAD / branch:
  9e9dba1 / research/llm-interview-integration
working tree paths:
  52 (49 R5-BC code/contract WIP + 3 corrective docs 本輪 handoff)
completed scope:
  C0 only：接手 corrective plan，確認 review findings 對照現況全部屬實。
review findings 現況確認（皆待 C1+ 修）:
  - context_builder.py:485 與 :779 仍為 turn_sequences[item.turn_id]（v2 欄位存取，
    上一輪 script 只改到 dict-comprehension 與 _evidence_item，漏兩處 sort-key lambda）。
  - ContextSourceRef 無 content_hash 欄位（§6.3 gap 屬實）。
  - binding reject codes 用 WIP 名稱（question_frame_unavailable / unknown_target_ordinal /
    unknown_choice_ordinal / duplicate_target_binding / slot_value_not_in_answer），
    須收斂成 §7.2 canonical values。
  - marker tables 寫死在 application/turn_interpret.py，verifier policy JSON 未 seal（§7.3 gap）。
  - qualifier 只檢查 substring，未做 false-specificity / 互斥 marker drop（§7.4 gap）。
  - verifier 無 duplicate all-drop（§7.6 gap）、system_insufficiency_codes 從不填（§7.7 gap）。
  - _commit_report 在 transaction 外預檢 stale，非 §8 要求的 transaction-boundary typed fail。
  - executor artifact kinds 仍是 context.packet / operation.input / operation.verification 等，
    非 §9.2 的 interview.*（frame snapshot 已用 interview.question_frame_snapshot）。
上一輪已完成且經驗證（沿用，不重做）:
  - Phase 1 domain/persistence v3；Phase 1b domain+reducer 測試（111 passed）。
  - Phase 2 Context v2 / TurnInterpret v2 / verifier+materializer / prompt+policy+operation 2.0.0
    的骨架（本 corrective 補齊其缺口）。
  - Phase 3 receipt commit / outcome v2 / frame snapshot artifact 骨架。
focused commands + exact results:
  本輪 C0 未跑測試（只讀 + grep 確認 findings）。
real PG commands + exact results:
  未跑。
schema determinism:
  未跑。
Alembic current/heads:
  0010 (head)（Phase 0 已記錄，未變）。
provider call/network status:
  無 network、無 paid live。
unresolved findings:
  §6–§9 全部缺口待 C1–C5 修；Phase 4 eval 遷移待 C7。
deviations from this plan:
  無。
Docker/DB local state:
  caliburn-db-1 running；rows 仍為 interview_state.v2（Phase 0 盤點）。
commit status (must remain uncommitted before Phase 5):
  未 commit、未 push。
```

### 2026-07-22 / C1 progress（context side complete）

```text
HEAD / branch:
  9e9dba1 / research/llm-interview-integration（未 commit）
completed scope:
  C1 §6 全部 context-side 修正完成並綠。turn_interpret 測試重寫刻意延到 C2/C3
  （verifier report shape 在那裡才定案，先寫會白工；§6.4 強制 gate 只要求 context_builder）。
changed files (this session, on top of Phase 1-3 WIP):
  app/interview_vnext/application/context_builder.py
    - 兩處 sort-key lambda 由 item.turn_id 改 item.source_turn_id（review §3.3 findings 修完）。
    - _state_source 增 content_hash 參數；evidence / eligible frame / 兩處 excluded 迴圈
      全部填 canonical_hash(object)。
    - _decision 改用 _authoritative_content()：frame/evidence decision 一律 hash 底層 domain
      物件（unwrap selected wrapper），selected==excluded content_hash 一致；與 source.content_hash
      不符則 ContextBuildError。
  app/interview_vnext/llm/context.py
    - ContextSourceRef 新增 content_hash（question_frame / evidence 必填，其餘 null）。
    - ContextEvidenceItem / ContextQuestionFrame validator 驗 content_hash == canonical_hash(object)。
  tests/test_interview_vnext_context_builder.py
    - Evidence 全改 v3 support（literal_support helper）。
    - prior_turn_operation / prior_receipts helper：非-tail employee turn 各建一筆 receipt，
      accepted_evidence_ids 依 state evidence 順序（State.v3 §7.2）。
    - shuffle 測試改「反轉 operation-block 順序、保留 block 內順序」（naive full-reverse 會製造
      production 不可能的 state；invariant 是 per-op 順序固定）。
    - 新增 3 向量：eligible frame projection + sealed source hash；packet/manifest/budget state_version
      == persisted；tampered frame source content_hash fail closed。
  tests/test_interview_vnext_dependencies.py
    - quote-primitive 不變式改成「evidence.py 不得重新宣告 QuoteSpan/QuoteMatch」+
      Evidence.v3 無 top-level quote/span。
focused commands + exact results:
  uv run --locked pytest -q tests/test_interview_vnext_context_builder.py -> 11 passed
  domain+reducers+question_frame+dependencies+context_builder -> 122 passed / 0 skipped
schema determinism / real PG / network:
  本輪未跑（C6 統一 re-baseline）。無 network。
Alembic current/heads: 0010 (head)
commit status: 未 commit、未 push。
```

### C2 精確入口（下一輪從這裡開始，先讀 amendment §10.1/§10.3）

尚未做，本輪停在這。C2 = verifier report/policy/identity，涉及檔案見母 corrective §10 的 C2 清單。
關鍵裁決已由 amendment + corrective §7 寫死，實作時照抄，勿自創：

1. **Reject code 收斂**（corrective §7.2 + amendment §10.3）。目前 `llm/turn_interpret.py`
   的 `TurnInterpretRejectCode` 用 WIP 名稱，須改成兩個 namespace 的 canonical 值：
   - Observation path：`quote_not_found` / `quote_occurrence_out_of_range` / `invalid_qualifier` /
     `qualifier_support_not_in_quote` / `false_specific_qualifier`（§7.4 新增）/
     `foreign_correction_target` / `inactive_correction_target` / `incoherent_correction` /
     `unsupported_quantification` / `reference_leakage` / `non_atomic_claim` /
     `duplicate_observation`（§7.2 新增）/ `insufficiency_incoherent`（§7.2 新增）/
     `domain_invariant_failed`。
   - Binding path（amendment §10.3 exact）：`binding_without_question_frame` /
     `binding_target_out_of_range` / `binding_kind_mismatch` / `binding_resolution_incoherent` /
     `binding_quote_not_found` / `binding_quote_occurrence_out_of_range` /
     `binding_value_not_supported` / `choice_selection_invalid` / `duplicate_binding_target` /
     `question_frame_not_eligible` / `question_frame_hash_mismatch` /
     `contextual_materialization_failed`。
   - WIP→canonical 對照：question_frame_unavailable→binding_without_question_frame；
     unknown_target_ordinal→binding_target_out_of_range；unknown_choice_ordinal→choice_selection_invalid；
     duplicate_target_binding→duplicate_binding_target；slot_value_not_in_answer→binding_value_not_supported。
     不留 alias。verifier policy `reject_order` 須含全部 enum、順序即 enum 宣告序。
2. **Report shape**（amendment §10.1）：`ObservationVerification` 加 `proposal_ref`(p0001) 與
   `candidate_evidence_id`（rejected 也保留）；`AnswerBindingVerification` 加 `binding_ref`(b0001) 與
   `candidate_evidence_ids`（choice 多筆、預派生）。candidate IDs 只在 report/artifact，不進 provider。
   drop 後不重編。`domain/turn_identity.py` 已有 literal/contextual id helper，另加
   `derive_proposal_ref`/`derive_binding_ref`（p/b + 4 位）。
3. **Marker policy sealing**（§7.3）：把 `application/turn_interpret.py` 寫死的六個 marker maps
   （FREQUENCY/OWNERSHIP/IMPORTANCE/TIME_SCOPE/TYPICALITY + polarity）搬進
   `TURN_INTERPRET_VERIFIER_POLICY_V2` typed definition（六個 map，key=enum serialized value，
   value=ordered regex string tuple），由 `turn-interpret-verifier.2.0.0.json` deterministic export；
   application verifier 從 typed policy 讀，不再另存一份；policy load 時 compile 全部 regex。
   必含 §7.3 列的 `只有.*才` / `我和.*共同` / 英文 daily/weekly/... 等 pattern。
4. C3 再做 §7.4 false-specificity、§7.5 full-answer 互斥掃描、§7.6 duplicate all-drop、
   §7.7 system insufficiency mapping、以及重寫 `tests/test_interview_vnext_turn_interpret.py`
   為 v2 + §12.2/§12.3 behavior vectors。

後續實作者從下一個小節開始追加。

### 2026-07-22 / C2 progress（verifier report、policy、identity）

```text
HEAD / branch: 195c6a3 / research/llm-interview-integration
working tree paths: S:/caliburn（單一 worktree）
completed scope: 母 corrective C2（§7.1–§7.3 + amendment §10.1/§10.3/§11）
  - domain/turn_identity.py: 新增 derive_proposal_ref(p0001)/derive_binding_ref(b0001)，1..9999 guard。
  - llm/turn_interpret.py: TurnInterpretRejectCode 收斂為兩個 canonical namespace（14 observation
    + 12 binding = 26），宣告序即 reject_order；WIP 名稱全部移除、無 alias。namespace frozensets
    (_OBSERVATION_REJECT_CODES/_BINDING_REJECT_CODES/_EMERGENT_TOPIC_REJECT_CODES) 逐 decision 強制。
    ObservationVerification +proposal_ref +candidate_evidence_id（accept/reject 都保留；accept 時
    == materialized evidence id）。AnswerBindingVerification +binding_ref +candidate_evidence_ids
    （依 proposal shape 預派生；accept 時 materialized == candidate）。report-level validator 驗
    candidate id 皆由 operation_id 決定性派生。
  - 六個 marker map（time_scope/frequency/typicality/polarity/importance/ownership）搬進
    TURN_INTERPRET_VERIFIER_POLICY_V2 typed definition，§11 exact 內容（含 只有.*才 / 我和.*共同 /
    與.*共同 / 支援.*處理 / English patterns / polarity markers；owner 不含「我／我自己」）。
    policy_is_canonical compile 全部 regex、禁 unknown/not_stated key、禁空 tuple。compile_marker：
    ASCII 才 IGNORECASE、Unicode 不 case-fold。
  - application/turn_interpret.py: 移除寫死 marker maps，改由 _compiled_matchers 從 sealed policy
    編譯（單一 authority）；_sole_marker / _parse_frequency / _slot_qualifiers 改用 policy matcher +
    regex；binding path 改用 canonical binding codes；observation/binding decision 帶 refs +
    candidate ids。移除 multiply_claimed→duplicate_correction_target（duplicate all-drop 是 C3）。
  - 重生：turn-interpret-verifier.2.0.0.json、turn-interpret-verification-report.v2.schema.json、
    turn-interpret-execution-outcome.v2.schema.json（皆 byte-deterministic，重跑一致）。
changed files: domain/turn_identity.py、llm/turn_interpret.py、application/turn_interpret.py、
  verifier_policies/turn-interpret-verifier.2.0.0.json、schemas/turn-interpret-verification-report.v2、
  application/schemas/turn-interpret-execution-outcome.v2、tests/test_interview_vnext_turn_interpret_contracts.py（新）
new/changed contracts: verifier policy hash 由 sha256:7668775b… → sha256:a4902e3dc47e53af5cfde030c0075a7f7092b32721da685d34d9132e5e7fe338；
  reject enum 18 → 26；report items +4 欄位。
focused commands + exact results:
  uv run --locked pytest -q tests/test_interview_vnext_turn_interpret_contracts.py -> 26 passed
  domain+reducers+question_frame+dependencies+context_builder+contracts -> 148 passed / 0 skipped
  end-to-end verifier smoke（scratch，未提交）: literal accept p0001 candidate==derived、
    binding reject binding_target_out_of_range b0001 candidate 預派生、report validator 接受合法 report。
real PG commands + exact results: 本輪未跑（C6 統一 re-baseline）。
schema determinism: 上述三檔重跑 byte 一致。
Alembic current/heads: 0010 (head)（未動）。
provider call/network status: 無 network、無 provider call。
unresolved findings: 無。
deviations from this plan: 無（C2 未觸 executor/PG，符合 §17）。ownership「我／我自己」slot exact 允許（§10.5）
  刻意留給 C3 連 slot vectors 一起實作+測，避免 C2 引入未測行為。
Docker/DB local state: 未動（DB 未啟動）。
commit status: 未 commit、未 push。
```

**C2 → C3 交接與 README reconciliation backlog**

C3 精確入口（先讀 corrective §7.4–§7.7 + amendment §10.4/§10.5）：
1. §7.4 literal false-specificity → 新 `false_specific_qualifier`（specific qualifier 的 support 須有對應
   dimension marker；unknown 不得帶 specific support；互斥 marker 整筆 drop）。用 policy polarity/marker maps。
2. §7.5 full-answer 互斥掃描已在 `_slot_qualifiers` 有雛形（掃 answer_quote）；補 ownership「我／我自己」
   exact 允許（§10.5，含 answer_quote 衝突守衛）與 free-text slot 規則的測試。
3. §7.6 duplicate all-drop：先算 literal/binding fingerprint 全集再逐筆 drop（→ `duplicate_observation` /
   `duplicate_binding_target`）；drop 不重編 candidate refs。C2 已移除舊 multiply_claimed，這裡補回正解。
4. §7.7 system insufficiency deterministic mapping（`answer_binding_ambiguous`/`ambiguous_frequency`/…/
   `question_frame_missing|not_immediate|stale`）；model ∪ system 依 enum order。可能需 Context v2
   `question_frame_limitation` application-only field。
5. `binding_resolution_incoherent`/`question_frame_not_eligible`/`question_frame_hash_mismatch` 目前
   declared 但未 emit，於此補 emitter（§10.2 gate order）。
6. 重寫 `tests/test_interview_vnext_turn_interpret.py` 為 v2 + §12.2/§12.3 behavior vectors；全綠才進 C4。

README reconciliation backlog（`apps/api/app/interview_vnext/README.md`，於 Phase 5 前單次一致性 doc pass
統一修，不在 C 中途 piecemeal 改以免自我矛盾）：
- 第 262–264 行 `proposal_key` UUIDv5 公式 → v2 已改位置式 `proposal_ref`/`candidate_evidence_id`。
- 第 273 行「同批兩個 correction 搶同一 target 兩者都拒絕」→ 改 §7.6 fingerprint duplicate all-drop（C3 後）。
- 第 276、329 行「typed no-op commit / 零 Evidence 走 no-op」→ R5-BC 已改為每個 employee turn 必留 receipt
  （RECEIPT_ONLY vs EVIDENCE_AND_RECEIPT），no-op 概念退役（C5 outcome/Capture 後）。
- 第 279 行 report `v1` / policy `1.0.0` / `proposal_key` / duplicate correction policy 敘述 → v2 / 2.0.0 /
  refs + candidate ids + 兩個 reject namespace + 六個 sealed qualifier marker map。
- 第 281 行 prompt/operation `1.0.0` → `2.0.0`。
- 第 305–322 行 recovery matrix 的 no-op 分支與 VERIFIED conflict → 改 terminal `state_context_stale`（C4 後）。

```text
### YYYY-MM-DD / Cn progress

HEAD / branch:
working tree paths:
completed scope:
changed files:
new/changed contracts:
focused commands + exact results:
real PG commands + exact results:
schema determinism:
Alembic current/heads:
provider call/network status:
unresolved findings:
deviations from this plan:
Docker/DB local state:
commit status (must remain uncommitted before Phase 5):
```

Phase 3.5 最終回報另須逐項列出：

1. Evidence v3 consumer search結果；
2. marker policy hash與active schema hashes；
3. exact reject/insufficiency vectors；
4. stale三個 race測試與provider/domain row counts；
5. normal/receipt-only/stale manifest root kinds；
6. no-network與real PG exact pass/skip/fail；
7. dependency/schema guard；
8. Alembic head；
9. staged secret/migration/output scan；
10. 是否已解鎖 Phase 4。

### 2026-07-22 / C2 corrective + C3 progress（Codex 接手）

```text
HEAD / branch: 9e9dba1 / research/llm-interview-integration
working tree paths: 延續既有 R5-BC single-atomic WIP；未 reset、未覆寫前手成果。
completed scope:
  - C2 corrective：active verifier policy document schema hard-cut 為
    turn_interpret_verifier_policy.v2；1.0.0 只做 raw-byte historical freeze，不恢復
    runtime V1 shim。reason tuple 強制 policy reject_order；六個 marker map 強制 exact
    enum key coverage、非空且 pattern unique。
  - execution schema gate同步辨識 active 2.0.0 + frozen 1.0.0；context policy、operation、
    prompt 的 1.0.0 historical files以 SHA-256 鎖定，active portable output改驗 v2。
  - C3：literal exact marker support/false-specificity；frequency 與 time scope獨立；
    contextual typed slot掃完整 answer quote；bare 我/我自己 owner allowance；frequency
    decimal/count/range/interval fail-closed；literal/binding fingerprint + resolved-target
    duplicate all-drop；frame missing/not-immediate/stale application-only provenance；
    deterministic system insufficiency；mixed literal/binding獨立 drop。
changed files:
  llm/turn_interpret.py、llm/context.py、application/context_builder.py、
  application/turn_interpret.py、active policy/schema fixtures、
  test_interview_vnext_turn_interpret_contracts.py、test_interview_vnext_turn_interpret.py、
  test_interview_vnext_execution_schemas.py。
new/changed contracts:
  verifier policy schema_version=v2；policy hash=
  sha256:baf2180e3e10940c80c602a91b47ff7e9aec37fa9eb85febcc4b24e8b9d4474b；
  TurnInterpretContextPacket + application-only question_frame_limitation enum（不投影 provider）。
focused commands + exact results:
  contracts + execution schemas -> 38 passed / 0 skipped
  turn_interpret + contracts + context_builder -> 71 passed / 0 skipped
  C1-C3 focused（turn/context/domain/reducers/question_frame/dependencies）
    -> 186 passed / 0 skipped
real PG commands + exact results: 未跑（C4-C6 統一執行）。
schema determinism: active policy/LLM/application writers已重生；C6 做雙 temp-dir final gate。
Alembic current/heads: 未變；無 migration file。
provider call/network status: 0 / 無 network。
unresolved findings:
  binding_resolution_incoherent 對通過 TurnInterpretOutput local matrix 的 typed object不可達；
  不製造假的 producer。kind/target/frame failures皆已有可達 exact code與測試。
deviations from this plan: 無架構偏離；上述不可達 code維持 public vocabulary供未來 contract major使用。
Docker/DB local state: 未動。
commit status: 未 commit、未 push；C3 focused green，進 C4。
```

### 2026-07-22 / C4–C6、Phase 4 與 final gate（Codex 完成）

```text
HEAD / branch: 9e9dba1 baseline / research/llm-interview-integration
working tree paths: 延續既有 R5-BC single-atomic WIP；沒有 reset 或重寫 R4/R5-A 歷史。
completed scope:
  - C4：Context state_version/state_hash 成為 transaction CAS authority；prepare 前、provider call 中、
    commit 前 stale 均 typed fail closed 為 state_context_stale，不 rebase、不產 receipt/domain write。
  - C5：成功 interpretation 恆建 receipt；EVIDENCE_AND_RECEIPT / RECEIPT_ONLY 取代 generic no-op；
    frame consume、events、outcome v2、fresh-process recovery與persistence major/corruption分流閉合。
  - C6：Capture terminal event refs與manifest roots閉合 request/result/execution evidence/conformance/
    verification/receipt/state；wrong hash、missing root與corrupt rehydrate皆fail closed。
  - Phase 4：12 case hard cut到 turn-interpret-c1-v2-pilot.v1；TI-09/TI-10 使用interleaved、
    deterministic eval-only prior interpretation seed；loader/runner/graders/review/report/scheduler/
    OpenRouter/OpenAI reference adapters與mocked probes全部搬到active v2 contracts。
  - local schema validation authority corrective：wire succeeded + conformance eligible、但本地完整
    schema invalid時，FAILED checkpoint由result authority重驗並要求 persisted
    output_schema_invalid；不誤判provider conformance，也不重打network。
changed files: 母計畫列出的domain/application/llm/persistence/eval/provider fixtures/tests/schema文件；
  未加入production route、Web/editor、公司/SaaS模型或通用agent framework。
new/changed contracts:
  Evidence.v3 / State.v3 / DomainEvent.v2 / ReductionResult.v2；Context/Input/Output/Report v2；
  turn-interpret-execution-outcome.v2；prompt/context/verifier/operation 2.0.0；eval 11份v2 contract
  schema + 1份prior-seed schema，舊11份v1 raw-byte frozen。
identity hashes:
  operation sha256:efa6523519cae5c4db14a7ddf6141657e073dcc8115b12d395b9e77f74963a4c
  context policy sha256:09468ace1f0564da5a7b1387fc8066a96275590554cc5cafd77274ebaa2b87f3
  verifier policy sha256:baf2180e3e10940c80c602a91b47ff7e9aec37fa9eb85febcc4b24e8b9d4474b
  eval suite sha256:5f60255dd323cd6c458b4ced7e067ca0a6c48cb9b3d2b5765bce8fada7a9bcc5
focused commands + exact results:
  contracts/schema 43；loader 30；fixtures/reference 9；graders/review 29；provider adapters 184；
  mocked probes 18；all interview_vnext no-network 794 passed / 87 skipped / 0 failed。
real PG commands + exact results:
  turn eval 5；runner/Capture 14；mocked OpenRouter batch/CLI 16；
  full API + real PostgreSQL 1269 passed / 0 skipped / 0 failed。
full no-network:
  full API 1071 passed / 198 skipped / 0 failed；skip均為既有DB-required tests，DB gate已全數實跑。
schema determinism: domain/llm/application/eval writers重跑；active deterministic，historical unchanged。
Alembic current/heads: 0010 (head)；無0011、無新dependency。
provider call/network status: 0 paid/live calls；OpenRouter仍first production-target，OpenAI只為mocked reference regression。
unresolved findings: 無R5-BC blocker；真模型品質、JD synthesis、editor共編與production route不屬本切片。
deviations from this plan: 無；只增加上述已由回歸測試證實必要的local validation authority修正。
Docker/DB local state: caliburn-db-1沿用既有running狀態；未啟動qdrant/embedder。
commit status: 全部gate綠後建立包含本文件的single atomic commit；不push。
```

Phase 3.5與Phase 4均完成，不再需要 implementation record續接。母計畫Definition of Done全部成立，R5-D已解鎖；
R6之前仍不得把mocked harness綠燈宣稱為模型品質通過。

---

## 18. Commit 規則

R5-BC 繼續沿用母計畫 single atomic code commit：

```text
feat(interview): ground turn interpretation in persisted question frames
```

只有 Phase 3.5、Phase 4、Phase 5 全部 gate綠後才可建立。不得為了保存進度提交已知 full suite紅的 corrective commit，也不得
amend/rewrite R5-A/R4歷史 commits。

commit前：

- staged diff逐檔核對；
- Author/Committer沿用repo owner identity；
- 不加共同作者；
- 不 stage `.env`、API key、output bundle、cache、DB dump；
- 不 push，除非 owner另行明確指示。
