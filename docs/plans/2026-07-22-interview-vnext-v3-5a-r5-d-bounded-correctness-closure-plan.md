# Interview AI vNext V3-5A R5-D——Bounded Correctness Closure 實作交接規格

- 狀態：**Completed（2026-07-22）；實作證據見 §17**
- 日期：2026-07-22
- Code baseline：`7b2cec5aae3ba9e7c81cc336de2a85f83127cb95`
- Code commit：`2432e9895e7be2d6d1a7a86ec1dfdf77ed0a0b90`（`fix(interview): close R5 turn artifacts into capture bundles`；未 push）
- 前置完成：R5-BC（Evidence／State／Context／Turn Interpreter v2 hard cut）
- 本步定位：**短小的 Capture 完整性封口，不是新產品功能或第二次架構重構**
- 下一產品切片：最小 Authoring Core；R5-D 完成後立即往可操作成品前進
- 禁止：paid live、production route、provider promotion、Web/editor 整合、新 domain/schema、Alembic `0011`

關聯 authority：

- [`../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md`](../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)
- [`2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md`](2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md)
- [`2026-07-22-interview-vnext-v3-5a-r5-bc-domain-context-hard-cut-plan.md`](2026-07-22-interview-vnext-v3-5a-r5-bc-domain-context-hard-cut-plan.md)
- [`2026-07-22-interview-vnext-v3-5a-r5-bc-phase-3-5-corrective-plan.md`](2026-07-22-interview-vnext-v3-5a-r5-bc-phase-3-5-corrective-plan.md)
- [`2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md`](2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md)

---

## 1. 白話：這一步到底在做什麼

R5-BC 已能把員工回答轉成 Evidence、verification report、interpretation receipt、domain command 與 reduction result，並能處理
短答、修正、零 Evidence、CAS 與 crash recovery。R5-D 不再改這些語意。

R5-D 只確認一件事：**一個完成或失敗的 trial 匯出後，是否真的帶齊「這次判斷用過的所有權威資料」，而且任何缺漏或竄改都會被發現。**

完成後必須能回答：

1. 這次模型看的是哪份 prompt、output schema、context、QuestionFrame 與 turn input？
2. 實際使用哪個 binding/config/projection，provider 每一次 attempt 回了什麼？
3. application 驗證出什麼 report，成功時寫了哪筆 receipt、command、reduction 與 turn output？
4. 若是 stale/CAS 失敗，為何失敗、哪些資料沒有被寫入？
5. bundle 少一個必要 root、少一筆 artifact、內容被改、event chain 被改時，是否一定 fail closed？
6. 相同 durable rows 匯出兩次，檔案是否逐 byte 相同，offline regrade 是否完全不改 bundle？

這不是單純「多存幾筆 log」。Capture 是可驗證的執行證據包；R5-D 封住的是日後 debug、模型評估與責任追溯的可信度。

---

## 2. 已鎖定的成果與時間邊界

### 2.1 必須交付

- Turn Interpreter trial manifest 補齊 request、context、frame、input、provider、report 與 domain outcome 的直接 root closure；
- in-memory bundle 重新驗證每一筆 `ArtifactRecord`，不能信任 `model_copy()` 後未重跑 validator 的物件；
- bundle 內的 manifest artifact 必須唯一且與 `CaptureBundle.manifest` byte authority 一致；
- Turn Interpreter outcome 內每個非空 authority ref 必須存在、ref exact match、scope 正確且是 terminal root；
- committed Evidence、receipt-only、`state_context_stale`、schema-invalid 四條代表路徑的 closure 證據；
- 刪除、unroot、hash/content、event、manifest 與 scope corruption matrix；
- 真正寫出兩份 trial bundle，逐 relative path、逐 raw bytes 比對相等；
- 現有 12-case suite 的 case、split、gold 與 frozen suite hash完全不變，reference gate續綠；
- full no-network、全部 vNext real PostgreSQL、Alembic、dependency、secret與git hygiene gates全綠。

### 2.2 明確不做

- 不新增 Evidence、State、QuestionFrame、receipt、command、event taxonomy 或 LLM contract版本；
- 不改 Turn Interpreter prompt、verifier policy、ContextBuilder budget或短答判斷；
- 不新增題目選擇、Agenda、Sufficiency、episode coding、JD synthesis或文件 patch；
- 不改 OpenRouter/OpenAI adapter、HTTP body、routing、cache、retry、usage或conformance；
- 不擴增 12-case suite，不重算 suite hash，不調 gold 讓測試過；
- 不建立通用 Capture framework、graph database、event-sourcing平台或新 service；
- 不補 production Web route；`app/` 仍不得 import `evals.*`；
- 不跑 paid live，不宣稱模型品質通過；
- 不新增 dependency，不做 migration。

### 2.3 預期改動預算

正常情況只應修改下列檔案：

```text
apps/api/evals/interview_vnext/turn_eval_runner.py
apps/api/evals/interview_vnext/capture_export.py
apps/api/tests/test_interview_vnext_turn_eval_runner.py
apps/api/tests/test_interview_vnext_turn_eval_postgres.py   # 只補 root 斷言時
apps/api/evals/interview_vnext/README.md                    # 完成後回寫
apps/api/app/interview_vnext/README.md                      # 完成後回寫
docs/README.md                                              # 完成後回寫
本計畫文件                                                # §17 實際證據
```

`app/interview_vnext/domain/`、`application/operation_executor.py`、`durable_operations.py`、`llm/port.py`、provider adapter、migration與
case fixture原則上都不應改。若實作者發現必須改這些檔案才可通過，先依 §15 停線回報，不要自行擴張。

---

## 3. 現況 code audit：哪些已有、哪些才是 R5-D 缺口

### 3.1 已完成，不得重做

| 能力 | 現行證據 | R5-D處理 |
|---|---|---|
| concurrent state move | `test_state_change_during_provider_call_rejects_stale_verified_commit` 已驗 `state_context_stale`、domain unchanged、首次1 call、replay 0 call | 保留；只補 stale trial 的 Capture closure |
| fresh-process recovery | prepared/calling/provider_completed/verified/failed recovery 已有 real PG matrix | 原測試列入 final gate，不重寫 recovery |
| provider authority closure | `validate_model_call_capture_closure()` 已驗 started/result/conformance event 與 result/evidence/conformance terminal roots | 直接沿用，不建第二套 provider validator |
| DB artifact immutability | PostgreSQL trigger 已阻擋 persisted artifact update | 不關 trigger，不以非法 DB update 當主要測試手段 |
| terminal event chain | `validate_event_chain()` 已重驗 sequence、previous hash、taxonomy、event refs與manifest hash/count | 直接沿用 |
| success/receipt-only/schema-invalid grading | online/offline byte-equal golden paths 已有 | 擴充為實體bundle雙寫byte identity，不重寫grader |
| 12 cases | `turn-interpret-c1-v2-pilot.v1` 12 cases real PG reference gate已綠 | case內容、split、gold與hash完全凍結 |
| bundle file integrity | `write_trial_bundle()` 已寫 `integrity-manifest.json`，offline tamper test已存在 | 沿用writer；補「兩個獨立目錄真的byte-equal」 |

### 3.2 已確認的實際缺口

#### 缺口 A：request 的四個內容 dependency 不是 terminal roots

`ModelCallRequest.v2` 已直接引用：

- `prompt_artifact`；
- `output_schema_artifact`；
- `context_artifact`；
- `selection_manifest_artifact`。

但 `turn_eval_runner.run_trial()` 現在的 `request_roots` 只取
`model.request + binding + provider config + schema projection`。因此 prompt/schema/context/selection 雖然存在資料庫，卻不能只靠
terminal manifest證明它們是本次執行 authority。

#### 缺口 B：in-memory bundle validator 沒有重新建構 `ArtifactRecord`

PostgreSQL export會經 `ser.load_artifact()` 重驗 hash/byte size；但測試或offline consumer可使用
`record.model_copy(update={...})` 建出沒有重跑 Pydantic validator 的物件。現行 `validate_capture_bundle()` 直接信任該 instance，部分未被
特定 typed parser讀取的 artifact可能帶著錯誤 inline bytes通過。

#### 缺口 C：只有 provider closure，沒有 Turn Interpreter outcome closure

現行 validator會檢查 provider request/binding/result/evidence/conformance，但不會逐一要求
`TurnInterpretExecutionOutcome.v2` 內的 context/input/report/receipt/command/reduction/output/failure refs都是 terminal roots。

#### 缺口 D：re-export測試只比 object/hash，沒有比實際檔案 bytes

現行測試證明兩次 export object相同、offline regrade不改單一目錄；尚未證明相同內容寫到兩個不同bundle目錄後，包含
`integrity-manifest.json` 在內的所有檔案逐 byte相同。

### 3.3 不是缺口的項目

- `capture.run_manifest` 不需要把自己列為 `root_artifacts`；run row 的 `manifest_artifact_id` 是 pointer authority；
- retry request會由每次 `model.call.started` event直接引用，provider各attempt result/evidence/conformance已由現行closure收齊；
- audit event不是完整event-sourcing payload。本步不藉機重寫全部 event input/output；terminal manifest + event chain + typed artifacts共同形成closure；
- setup command/reduction已由setup events引用；eval-only prior seed 的額外artifact仍維持既有direct roots；
- `state_context_stale`行為本身已完成，R5-D只驗它的失敗bundle沒有假receipt或domain mutation。

---

## 4. 架構裁決：最小改動，不新增框架

### 4.1 保留三層 validator

```text
validate_event_chain
  └─ 通用 Capture：event/hash/taxonomy/ref/manifest

validate_model_call_capture_closure
  └─ provider-neutral：request/binding/config/projection + 每attempt result/evidence/conformance

validate_capture_bundle 內的 private Turn Interpreter closure
  └─ eval operation-specific：prompt/schema/context/frame/input/report/receipt/command/reduction/outcome
```

R5-D **不新增** `CaptureService`、`GraphValidator`、registry或plugin system。Turn Interpreter-specific規則暫時留在
`evals/interview_vnext/capture_export.py` 的private pure helpers，因為目前只有eval exporter需要離線重驗；production route尚未存在。

未來 production composition root需要同一套 exporter時，再以實際第二個consumer證明值得上移到application層。現在先不預建抽象。

### 4.2 不修改 provider event input order

`model.call.started` 的既有 exact input order維持：

```text
model.request
model.provider_binding
provider.config
model.schema_projection
```

這四個是 provider execution authority，OpenRouter/OpenAI mocked probes與既有conformance測試依賴此順序。R5-D只把
prompt/schema/context/selection加入**terminal manifest roots**，不改provider wire或event contract。

### 4.3 fail-closed，但不要將正常結果誤判 corruption

- missing、ref mismatch、inline hash mismatch、wrong run/session scope、unrooted required authority → `CaptureExportError`；
- model quality差、verifier全部drop、receipt-only、provider/schema正常typed failure → 是可匯出的合法terminal bundle；
- `state_context_stale` → 合法typed operation failure，bundle應通過完整性驗證；
- DB row不存在或typed payload壞掉 → persisted corruption，不能改寫成一般模型失敗；
- secret/reasoning scan規則維持，命中仍是harness invalid。

---

## 5. Exact terminal root contract

### 5.1 Root順序

`run_trial()` 建 roots時維持現有 deterministic append + first-occurrence dedupe。新順序固定為：

1. provider event authority前四項（現行順序不變）；
2. request內容dependencies：prompt、output schema、context packet、context selection manifest；
3. eval setup額外roots（現行順序）；
4. 所有attempt的provider result/evidence/conformance（event sequence順序）；
5. context budget；
6. QuestionFrame snapshot（存在才加入）；
7. checkpoint/outcome refs（依下表固定欄位順序，`None`略過）；
8. execution outcome artifact本身。

重複ref保留第一次出現的位置。既有測試要求前四項不變，R5-D不得為了美觀重排。

### 5.2 Request closure

對每個 rooted `model.request`，以下refs都必須是exact terminal roots：

| Ref | Artifact kind | 說明 |
|---|---|---|
| request artifact本身 | `model.request` | request envelope |
| `binding_artifact` | `model.provider_binding` | immutable provider binding |
| `provider_config_artifact` | `provider.config` | outbound provider config authority |
| `schema_projection_artifact` | `model.schema_projection` | portable schema projection report |
| `prompt_artifact` | `prompt.template` | 本次真正送出的versioned prompt bytes |
| `output_schema_artifact` | `schema.output` | 本次structured output schema |
| `context_artifact` | `interview.context_packet.v2` | immutable context snapshot |
| `selection_manifest_artifact` | `interview.context_selection_manifest.v2` | context選取／省略決策 |

前三個provider refs仍由現行`validate_model_call_capture_closure()`驗；R5-D private closure只補後四個content refs，避免複製
provider規則。

此外要驗真正送出的request與artifact bytes一致：

- prompt artifact的inline text必須逐字等於`request.instructions`；
- output schema ref的`schema_id`必須等於`request.output_schema_id`；
- context artifact必須typed parse為`TurnInterpretContextPacket`，其operation identity要與request的session/turn/operation一致；
- attempt 1的第一個user message必須逐字等於持久化`TurnInterpretInput`的canonical JSON；
- 不重新render prompt、不重新build context，只比已persisted authority。

### 5.3 Context closure

每個 `turn.interpret` operation還必須包含：

| Authority | Exact規則 |
|---|---|
| context packet | 等於request的`context_artifact`，並可parse為`TurnInterpretContextPacket` |
| context selection manifest | 等於request的`selection_manifest_artifact` |
| context budget report | ID=`uuid5(operation_id, "context-budget")`，kind=`interview.context_budget_report.v2`，direct root |
| turn input | 等於outcome的`input_ref`，kind=`interview.turn_interpret_input.v2`，direct root |
| QuestionFrame snapshot | packet含eligible frame時，ID=`uuid5(operation_id, "question-frame-snapshot")`、kind=`interview.question_frame_snapshot.v1`、content hash等於packet內frame canonical hash、direct root |
| 無eligible frame | 不要求snapshot；不得為了湊root偽造空frame artifact |

context packet、selection manifest與budget report都要typed parse，且下列`ContextIdentity`欄位逐欄相等：

```text
operation_name
operation_definition_hash
context_policy_name
context_policy_version
context_policy_hash
session_id
turn_id
operation_id
state_hash
state_version
reference_snapshot_hash
section_order
```

`TurnInterpretInput`使用既有pure `turn_interpret_input_from_context(packet)`重建一次，重建值必須與input artifact typed value相等。
這不是從current state重新推導；它只驗同一個immutable packet到provider input的既有deterministic projection。

### 5.4 Provider attempt closure

完全沿用 `validate_model_call_capture_closure()`：

- 每個started attempt必須有同identity的result event；
- execution evidence存在時必須有conformance event；
- started/result input refs一致；
- result/evidence/conformance tail order不變；
- 所有attempt的result/evidence/conformance都是terminal roots；
- schema repair的兩次attempt都保留，不只root最後一次。

R5-D不重寫這段邏輯，只在corruption matrix中保留既有向量，證明沒有回歸。

### 5.5 Outcome closure

每個turn-eval finalized run必須恰有一個rooted
`interview.turn_interpret_execution_outcome.v2`。先typed parse為`TurnInterpretExecutionOutcome`，再要求以下所有**非空**ref是exact root：

```text
checkpoint.request_artifact
checkpoint.attempt_result_artifacts[*]
checkpoint.provider_result_artifact
checkpoint.provider_execution_evidence_artifact
checkpoint.provider_conformance_artifact
checkpoint.verification_artifact
checkpoint.domain_result_artifact
checkpoint.response_artifact
checkpoint.failure_artifact

outcome.context_packet_ref
outcome.input_ref
outcome.provider_result_ref
outcome.verification_report_ref
outcome.interpretation_record_ref
outcome.domain_command_ref
outcome.reduction_result_ref
outcome.turn_output_ref
outcome.failure_ref
outcome.response_artifact
outcome artifact本身
```

`TurnInterpretExecutionOutcome`本身已驗committed/failed shape與checkpoint一致性；R5-D不要再寫第二份status state machine，只做
ref存在、root、scope與typed content檢查。

### 5.6 四條代表路徑

| 路徑 | 必須有 | 必須沒有 |
|---|---|---|
| committed evidence（TI-01） | context/frame/input/provider/report/receipt/command/reduction/output/outcome | failure |
| receipt-only（TI-11） | 與committed相同，report accepted count為0，仍有receipt/command/reduction/output | fake Evidence、generic no-op |
| `state_context_stale` | context/frame/input/provider/report/failure/outcome | receipt、domain command、reduction、turn output、Evidence mutation |
| schema-invalid | request/context/input、每attempt provider authority、failure/outcome | report/receipt/domain command/reduction/output（依實際checkpoint非空欄位為準） |

不要用同一份硬編碼kind list套所有status；authority以typed request、checkpoint與outcome的非空refs為準。

---

## 6. `capture_export.py` exact實作

### 6.1 先重新驗每一筆 artifact

`validate_capture_bundle()` 建records map前，必須對每筆artifact執行等價於：

```python
validated = ArtifactRecord.model_validate(record.model_dump(mode="python"))
```

後續store、scan與closure只能使用`validated`，不能再使用caller傳入的未驗instance。驗證順序：

1. 重建`ArtifactRecord`，重驗inline content hash與UTF-8 byte size；
2. `record.run_id == bundle.run_id == bundle.manifest.run_id`；
3. `record.session_id == bundle.manifest.session_id`；
4. artifact ID不得重複；
5. 本eval bundle若遇`storage=external`直接fail closed：現行bundle沒有攜帶external bytes，不能假裝已驗內容；
6. secret/reasoning scan；
7. 才放入memory store。

Pydantic `ValidationError`、JSON parse錯誤與scope mismatch一律包成`CaptureExportError`，不要讓raw exception從exporter外洩。

### 6.2 Manifest artifact自我一致性

bundle artifacts中必須恰有一筆kind=`capture.run_manifest`：

- 必須inline；
- parse結果必須等於`bundle.manifest`；
- `bundle.run`仍必須等於`bundle.manifest`；
- artifact ref content hash/byte size由ArtifactRecord revalidation保證；
- manifest artifact本身不加入`root_artifacts`，不得造成自我引用。

多一筆、少一筆、external、內容不同或parse失敗都回`CaptureExportError`。

### 6.3 Private helper責任

可在同檔新增下列小型private helpers，名稱可等價但責任不可混：

```text
_require_exact_root(ref, roots_by_id, label)
_load_inline_ref(ref, records, expected_kind, run/session/operation scope)
_validate_turn_interpret_capture_closure(bundle, records)
```

限制：

- pure、同步、無DB、無network；
- 不建立class hierarchy或registry；
- 不修改artifact內容、不補缺值、不做best-effort repair；
- error message至少含authority label或artifact ID，讓測試與debug可定位；
- generic event/provider validator先跑或後跑皆可，但整個bundle只有全部通過才算valid；建議順序為artifact → manifest artifact → event chain → provider closure → turn closure → secret metadata。

Turn closure直接使用現有typed authority：`ModelCallRequest`、`TurnInterpretContextPacket`、`ContextSelectionManifest`、
`ContextBudgetReport`、`TurnInterpretInput`、`TurnInterpretExecutionOutcome`與`turn_interpret_input_from_context()`。不要另建平行dict
schema或用手寫JSON path代替Pydantic contracts。

### 6.4 Scope檢查

對request/outcome closure載入的operation artifact：

- `run_id`、`session_id`必須與manifest一致；
- `operation_id`必須與request/outcome checkpoint一致；
- 有`turn_id`的artifact必須與request/outcome turn一致；
- attempt-specific artifact若ref來源是特定attempt，`attempt_id`必須一致；
- setup／run-level artifact不套operation規則，避免把合法initial snapshot誤判corruption。

不要只比kind；exact authority是完整`ArtifactRef`（ID、kind、media type、schema ID、hash、byte size）相等。

---

## 7. `turn_eval_runner.py` exact實作

### 7.1 只補roots，不改執行流程

在現行：

```python
request = ModelCallRequest.model_validate_json(...)
request_roots = model_call_input_artifacts(request_record.ref, request)
```

之後建立一個固定tuple，保留前四項並追加：

```text
request.prompt_artifact
request.output_schema_artifact
request.context_artifact
request.selection_manifest_artifact
```

把這個完整tuple放入現行`root_artifacts`組裝；其餘provider/setup/budget/frame/checkpoint/outcome順序維持 §5.1。

### 7.2 不准順便改的內容

- 不改`execute_turn_interpret()`signature；
- 不在runner重建context或re-run verifier；
- 不從current state推導frame；只能使用已persisted snapshot；
- 不把manifest artifact列入自身roots；
- 不用kind搜尋替代exact request/outcome refs；
- 不改`model_call_input_artifacts()`，以免連動probe event順序；
- 不改dedupe為set；現行first-occurrence list才能保存deterministic order。

---

## 8. Exact corruption matrix

所有corruption測試都從一份已通過`export_run_bundle()`的合法bundle複製，**只改一個維度**，再呼叫
`validate_capture_bundle()`。不得修改production DB、停用trigger或重新簽一整條偽造chain來讓壞資料看似合法。

### 8.1 Artifact record層

| 向量 | 變異 | 預期 |
|---|---|---|
| duplicate ID | artifacts tuple重複同一record | `CaptureExportError` |
| missing record | 逐一刪除每個manifest root對應record | fail |
| inline content changed | 對每個inline record以`model_copy`在內容尾端加一個無害空白，ref不改 | ArtifactRecord revalidation fail |
| byte size changed | ref byte_size ±1，內容不改 | fail |
| content hash changed | ref hash改為另一合法sha256字串，內容不改 | fail |
| wrong run | record.run_id換成foreign UUID | fail |
| wrong session | record.session_id換成foreign UUID或`None` | fail |
| external authority | 將一個required root改成external record但bundle無bytes | fail |

若「對所有inline records」造成測試量太大，仍只是一個已export bundle上的in-memory parametrize，不應重新跑DB trial；不得縮成只測provider config。

### 8.2 Manifest root層

逐一把下列required ref從`manifest.root_artifacts`移除，但artifact record保持存在：

- prompt；
- output schema；
- context packet；
- context selection manifest；
- context budget；
- eligible QuestionFrame snapshot；
- turn input；
- verification report；
- interpretation receipt（committed/receipt-only）；
- domain command（committed/receipt-only）；
- reduction result（committed/receipt-only）；
- turn output（committed/receipt-only）；
- failure artifact（failed）；
- execution outcome；
- 既有 provider config/result/evidence/conformance representative vectors。

每一項都必須fail。不要只驗「record缺失」；本矩陣特別證明nested JSON內仍有ref時，少了direct terminal root也不能通過。

### 8.3 Event與manifest層

| 向量 | 預期 |
|---|---|
| event body改動但保留舊event hash | `validate_event_chain` fail |
| event sequence缺號、重複event ID或previous hash不符 | fail；可沿用既有event tests，不必全在runner重複 |
| `bundle.run != bundle.manifest` | fail |
| manifest root ref hash與stored record不符 | fail |
| manifest event_count/first/last hash不符 | fail |
| manifest artifact缺失 | fail |
| manifest artifact重複 | fail |
| manifest artifact內容與bundle.manifest不同 | fail |

### 8.4 Semantic closure層

- packet有eligible frame但snapshot root缺失 → fail；
- frame snapshot內容被改、hash ref未改 → fail；
- context/outcome指向foreign operation artifact → fail；
- committed outcome少receipt/command/reduction/output任一root → fail；
- stale outcome少report或failure root → fail；
- schema-invalid兩attempt少任一provider authority root → fail；
- receipt-only accepted Evidence仍為0是合法，不得因「沒有Evidence」判corruption。

---

## 9. `state_context_stale` Capture測試

### 9.1 不新增production hook

在`test_interview_vnext_turn_eval_runner.py`建立test-only `LlmPort` decorator：

```text
inner.generate_structured(call)
  → 取得原本合法envelope
  → 執行一次before_return async callback
  → 回傳原envelope
```

callback使用現有production UoW與`apply_durable_command()`提交一個deterministic
`TransitionSessionCommand(... target_status=PAUSED)`，expected version從callback當下讀到的persisted state取得。禁止：

- 在production `ScriptedLlmPort`加測試hook；
- 直接SQL update state；
- monkeypatch reducer/CAS；
- sleep製造race。

測試identity與時間固定，不留給實作者自行命名：

```text
command_id           = uuid5(trial_id, "command/r5-d-concurrent-pause")
event_id             = uuid5(trial_id, "event/r5-d-concurrent-pause")
command_artifact_id  = uuid5(trial_id, "artifact/command/r5-d-concurrent-pause")
reduction_artifact_id= uuid5(trial_id, "artifact/reduction/r5-d-concurrent-pause")
occurred_at          = call.request.created_at + 500 milliseconds
stage                = turn.receive
idempotency_key      = turn-eval:<trial_id>:r5-d-concurrent-pause
```

`expected_state_version`必須來自callback內重新load的當下state；其他tenant/run/session ID直接取`call.request`，不得另造scope。

這與既有fixed-replay stale test採相同原理，但讓完整`run_trial()`能finalize並匯出failed bundle。

### 9.2 必須斷言

- provider call恰1次；
- terminal outcome/run皆failed；
- reason code exact=`state_context_stale`；
- persisted state只有測試callback的pause transition；
- target employee turn沒有新增Evidence或interpretation receipt；
- outcome有context/input/provider/report/failure refs；
- outcome沒有receipt/domain command/reduction/turn output refs；
- manifest roots符合 §5.6；
- `export_run_bundle()`與`validate_capture_bundle()`通過；
- 既有fixed-replay test繼續證明相同operation重播0 provider call，不在此再複製一套recovery實作。

---

## 10. 真正的 re-export byte identity

### 10.1 測試方式

對同一個durable trial：

1. 呼叫`export_run_bundle()`取得`capture_a`；
2. 由相同execution建立同一份trial/grading資料；
3. `write_trial_bundle(tmp_path / "export-a", ...)`；
4. 再次呼叫`export_run_bundle()`取得`capture_b`；
5. `write_trial_bundle(tmp_path / "export-b", ...)`；
6. 對兩個trial directory建立`relative POSIX path -> raw bytes` map；
7. 斷言path集合與每個raw bytes完全相等，包含：
   - `trial.json`；
   - `capture/run.json`；
   - `capture/events.jsonl`；
   - `capture/artifacts.jsonl`；
   - `capture/manifest.json`；
   - final state/candidate/report/grader/review files；
   - `integrity-manifest.json`；
8. 對A、B各跑至少一次offline `_score_trial()`；
9. 斷言兩個目錄在regrade前後byte map都不變。

### 10.2 不可接受的捷徑

- 只比較Pydantic object equality；
- 只比較manifest root hashes；
- 只比較檔案SHA但忽略path集合；
- export第二次時直接copy第一個目錄；
- 遇到nondeterministic欄位就刪欄位或排序語意上有序的資料；
- 修改canonical serializer格式只為讓測試過。

若測試發現真實nondeterminism，先定位是哪個欄位與authority，再依 §15停線；不要在R5-D引入新的timestamp normalization規格。

---

## 11. 12-case reference gate

### 11.1 Frozen identity

以下必須原封不動：

```text
suite_version = turn-interpret-c1-v2-pilot.v1
case_count = 12
development = TI-01 ... TI-08
challenge = TI-09 ... TI-12
suite_hash = sha256:5f60255dd323cd6c458b4ced7e067ca0a6c48cb9b3d2b5765bce8fada7a9bcc5
```

### 11.2 R5-D只跑，不改

- `test_interview_vnext_turn_eval_fixtures.py`：suite hash與fixture identity；
- `test_all_reference_cases_commit_on_real_postgres`：12/12 production reducer gate；
- committed Evidence與receipt-only的Capture assertions；
- 不重新生成fixtures，不改gold/split/reference output；
- 若新增roots改變suite hash，代表suite identity算法錯把execution packaging當case semantics；先停線，不更新expected hash。

Reference全綠只代表harness與deterministic contract正確，不代表true model品質通過。

---

## 12. 實作順序與commit slicing

### D0——Baseline audit（不commit）

1. 確認HEAD=`7b2cec5...`或明確記錄新的owner-approved baseline；
2. `git status --short`，保留既有未提交文檔，不得reset／checkout；
3. 以R5-BC在exact code baseline留下的`1071/198/0` no-network與`1269/0/0` real-PG證據作full baseline，不在D0重跑兩套完整suite；
4. D0只跑§13.1 focused no-network、§13.2 focused real PostgreSQL與Alembic current/heads，確認環境與目標路徑可工作；
5. 記錄focused pass/skip/fail、Docker/db初始狀態與Alembic `0010 (head)`；
6. D2 code完成後仍必須跑§13.3～§13.6全部final gates，不得以D0 focused取代最終完整驗收。

這是owner於2026-07-22核准的時間優化：exact HEAD已有完整基線且目前只有文檔變更，因此避免在改碼前重複約兩千個測試。
若HEAD不同、已有production code變更、focused紅或Alembic不符，這項優化立即失效，先回報並補跑完整baseline，不把既有失敗混進R5-D。

### D1——Test-first closure（未全綠前不commit）

先新增／擴充下列測試並確認它們能重現 §3.2 缺口：

- request content root缺失；
- arbitrary inline artifact經`model_copy`竄改仍可能通過；
- outcome nested ref存在但direct root被移除；
- 兩個獨立bundle目錄尚未做raw byte equality；
- stale trial尚無完整Capture golden path。

測試可以先紅，但這個紅狀態不commit。

### D2——最小code修正

1. `run_trial()`追加四個request content roots；
2. `validate_capture_bundle()`重建所有ArtifactRecord並驗run/session/storage；
3. 驗exact單一manifest artifact；
4. 加private Turn Interpreter request/context/outcome closure；
5. 保留現有event/provider/secret validators與exception boundary；
6. 跑focused與全部相關regression；
7. 跑full no-network＋全部vNext real PG，全部綠才可commit。

建議implementation commit：

```text
fix(interview): close R5 turn artifacts into capture bundles
```

commit必須包含code與對應tests，不能先提交一個已知整套會紅的半成品。

### D3——Final evidence與文檔

1. 回寫本文件 §17 exact結果；
2. 更新`apps/api/evals/interview_vnext/README.md`；
3. 更新`apps/api/app/interview_vnext/README.md`：R5-D complete，下一工程切片改為最小Authoring Core；
4. 更新`docs/README.md`索引狀態；
5. 再跑doc/hygiene gates；
6. 建立docs/status commit。

建議commit：

```text
docs(interview): close R5-D correctness handoff
```

Author與Committer都使用repo owner既有identity：

```text
ArIs0x145 <aris0x145@gmail.com>
```

不得加入`Co-authored-by`；不amend/rebase既有R5-BC commit；不push，除非owner另行指示。

---

## 13. 驗收命令

以下命令在`apps/api`執行；Windows PowerShell依repo runbook設定環境。

### 13.1 Focused no-network／pure guards

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
uv run --locked pytest -q tests/test_interview_vnext_capture.py tests/test_interview_vnext_dependencies.py
uv run --locked pytest -q tests/test_interview_vnext_turn_eval_fixtures.py
```

若R5-D沒有修改`test_interview_vnext_capture.py`，仍需跑它確認通用Capture沒有回歸。

### 13.2 Focused real PostgreSQL

依[`../runbook.md`](../runbook.md)只啟動標準db，測試庫需已upgrade至head：

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test'
uv run --locked pytest -q tests/test_interview_vnext_turn_eval_runner.py tests/test_interview_vnext_turn_eval_postgres.py
uv run --locked pytest -q tests/test_interview_vnext_fixed_replay_postgres.py tests/test_interview_vnext_recovery_postgres.py
```

不得把需要DB的測試改成skip，也不得只報`runner.py`結果而省略既有CAS/recovery regression。

Docker操作裁決：

1. 開始前先記錄Docker Desktop與`caliburn-db-1`是否原本就在運行；
2. 若未運行，允許啟動Docker Desktop，且只啟動標準`db` service；不得順帶啟動Qdrant、GPU embedder或其他service；
3. 只使用既有`caliburn_test`測試庫，依runbook upgrade到`0010 (head)`；不得碰dev/production資料；
4. D0～D3期間保持db運行，避免每個gate反覆起停；
5. 交付時：若db原本已在運行就保持原狀；若是本次才啟動，只停止`db` service、不執行`down`或刪volume；
6. 最終回報初始狀態、實際啟動／停止命令與交付時狀態。

### 13.3 全部 vNext real PostgreSQL

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test'
uv run --locked pytest -q tests/test_interview_vnext_*
```

成功條件：`0 skipped / 0 failed`。

### 13.4 Full API no-network

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
uv run --locked pytest -q
```

Baseline為`1071 passed / 198 skipped / 0 failed`。R5-D不得把任何既有passed test改成skip；新增PG-only測試的skip規則如下。

2026-07-22 owner refinement：R5-D新增的real-PostgreSQL test node使用repo既有`require_postgres` fixture，因此在未設定
`TEST_DATABASE_URL`的full no-network run中可以新增對應skip；這不算靠skip逃避驗收。必要條件是：

- baseline既有198個skip的identity保持不變，沒有任何既有passed test退化為skip；
- 新增skip數必須exact等於新增的PG-only test node數，並以`pytest -rs`或等價collection證據逐項對上；
- 同一批新增tests在§13.2／§13.3 real PostgreSQL gate必須全部實跑、`0 skipped / 0 failed`；
- 不得新增手寫`pytest.skip`／`skipif`來繞過失敗。

### 13.5 Full API＋real PostgreSQL

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test'
uv run --locked pytest -q
```

Baseline為`1269 passed / 0 skipped / 0 failed`。最終仍須`0 skipped / 0 failed`。

### 13.6 Schema、Alembic、dependency與hygiene

```powershell
uv run --locked pytest -q tests/test_interview_vnext_schemas.py tests/test_interview_vnext_execution_schemas.py tests/test_interview_vnext_dependencies.py
uv run --locked alembic current
uv run --locked alembic heads
git diff --check
git status --short
```

另人工確認：

- Alembic current/heads都是`0010 (head)`，沒有`0011`；
- `app/`沒有import `evals.*`；
- staged檔沒有`.env`、API key、Authorization header、`output/` bundle或DB dump；
- 沒有新dependency/lockfile變更；
- 沒有paid live或外部network call；
- test/eval rows依既有tenant-scoped cleanup清除；
- 若實作者啟動Docker Desktop或`caliburn-db-1`，交付時明確回報容器仍在或已收掉。

---

## 14. Definition of Done

- [ ] request prompt/schema/context/selection都是terminal roots；
- [ ] provider started event exact前四input順序未變；
- [ ] every bundled ArtifactRecord重新typed validation；
- [ ] wrong run/session、external authority、duplicate artifact fail closed；
- [ ] bundle中恰一個manifest artifact且與bundle manifest一致；
- [ ] committed Evidence closure通過；
- [ ] receipt-only closure通過且沒有fake Evidence/no-op；
- [ ] stale/CAS failure closure通過且沒有receipt/domain mutation；
- [ ] schema-invalid多attempt closure通過；
- [ ] 每個required root被unroot時都fail；
- [ ] 每個inline artifact content被單點竄改時都fail；
- [ ] event與manifest corruption vectors fail；
- [ ] 兩個獨立bundle directory path集合與raw bytes完全一致；
- [ ] offline regrade不改任一bundle byte；
- [ ] 12 cases、split、gold與suite hash完全未改；
- [ ] existing stale/CAS與fresh recovery regression全綠；
- [ ] full no-network 0 fail；既有passed test無退化skip，新增skip只來自可逐項對上的PG-only新test nodes；
- [ ] 全部vNext＋real PostgreSQL 0 skipped/0 failed；
- [ ] full API＋real PostgreSQL 0 skipped/0 failed；
- [ ] Alembic仍0010、無dependency/provider/domain/schema改動；
- [ ] secret/reasoning/dependency/git hygiene全綠；
- [ ] 本文件與README回寫exact執行證據；
- [ ] 未push，commit contributor只顯示owner。

全部成立才把R5-D標記Completed，並解鎖最小Authoring Core。mock/reference全綠仍不解鎖true model quality promotion。

---

## 15. 停線條件：遇到就回報，不要猜

1. 必須改Evidence/State/QuestionFrame/TurnInterpret contract或schema major才能完成；
2. 必須新增migration、table、column、dependency或service；
3. 必須改provider adapter、outbound request、route/cache/retry/conformance才能過；
4. 必須改12-case fixture、gold、split或suite hash；
5. 必須改event taxonomy或全面重寫event inputs/outputs；
6. 合法receipt-only、typed failure或external-free bundle被新validator誤判corruption；
7. production `app/`需要import `evals.*`；
8. re-export不一致來自已發布canonical contract，且修正會改persisted bytes；
9. real PG gate只能靠skip、停trigger或直接SQL偽造state才能通過；
10. 範圍超過 §2.3 檔案預算且不是單純測試/README回寫。

停線回報格式：實際證據、最小重現、受影響authority、兩到三個選項、推薦選項與blast radius。不要先做相容shim。

---

## 16. Code review checklist

### Correctness

- required root來自persisted typed request/outcome，不是靠kind猜一筆；
- `ArtifactRecord.model_validate()`使用caller資料重建，確實會重跑after validator；
- closure比較完整`ArtifactRef`，不是只比ID或kind；
- context frame snapshot hash與packet內frame canonical hash一致；
- failed path只要求實際存在的refs，沒有偽造success closure；
- receipt-only成功仍要求receipt/command/reduction；
- provider multi-attempt authority仍由event sequence完整root；
- dedupe保留first occurrence與deterministic order；
- manifest artifact沒有自我root。

### Architecture

- 通用event/provider validator未複製；
- Turn Interpreter-specific規則沒有污染provider adapter；
- 沒有為一個consumer建立framework/registry/plugin；
- 沒有把eval exporter反向import進production app；
- 沒有把Capture當成current state authority；
- 沒有以try/except吞corruption後繼續grading。

### Tests

- corruption每次只改一個維度；
- in-memory mutation確實繞過constructor，能證明revalidation有價值；
- byte identity比raw bytes與path集合；
- stale用production command/reducer製造，不用sleep/SQL；
- 12-case frozen hash仍exact；
- no-network與PG結果分開回報，0 skipped不含「沒收集到測試」。

---

## 17. 實作完成回報（實際結果）

- 狀態：**Completed（2026-07-22）**。

1. **Commits**
   - Code：`2432e9895e7be2d6d1a7a86ec1dfdf77ed0a0b90` — `fix(interview): close R5 turn artifacts into capture bundles`；Author 與 Committer 皆 `ArIs0x145 <aris0x145@gmail.com>`；未 push。
   - Docs/status：本次 handoff 收尾 commit（README 與本文件回寫）。
2. **Files changed（皆在 §2.3 預算內）**
   - `evals/interview_vnext/turn_eval_runner.py`：`run_trial()` 追加 prompt/output-schema/context-packet/selection-manifest 四個 request content roots（§5.1 order，provider authority 前四項不變）。
   - `evals/interview_vnext/capture_export.py`：`validate_capture_bundle()` 加 ArtifactRecord revalidation、單一 manifest artifact 自我一致性、Turn Interpreter request/context/outcome closure；private pure helpers，無 DB/network、無 class hierarchy/registry。
   - `tests/test_interview_vnext_turn_eval_runner.py`：D1 A/B/C red proofs + D/E golden + §8 corruption matrix；未超出預算。
   - README×2、`docs/README.md`、本文件於 docs commit 回寫。無 domain/schema/provider/migration/fixture 改動。
3. **Root order**：成功 committed trial 的 terminal roots 依 §5.1：provider authority(`model.request`,`model.provider_binding`,`provider.config`,`model.schema_projection`) → request content(`prompt.template`,`schema.output`,`interview.context_packet.v2`,`interview.context_selection_manifest.v2`) → provider result/evidence/conformance → `interview.context_budget_report.v2` → `interview.question_frame_snapshot.v1` → checkpoint/outcome authorities(verification/domain_result/response/interpretation/command/reduction/output) → `interview.turn_interpret_execution_outcome.v2`。schema-invalid 兩 attempt 的 `model.result` 都 root（`test_schema_invalid_requires_every_attempt_provider_authority` 斷言 2 個）。
4. **Artifact validation**：每筆 record 以 `ArtifactRecord.model_validate(model_dump())` 重建重驗 inline hash/byte size；驗 `run_id==bundle.run==manifest.run`、`session_id==manifest.session`、artifact ID 唯一、`storage=external` fail-closed；恰一個 inline `capture.run_manifest` 且 parse 等於 `bundle.manifest`、不自我 root。
5. **Corruption matrix（全部 fail-closed，實測通過）**：
   - Artifact 層（§8.1，代表 8 種 kind × 6 維：inline-content/byte-size/content-hash/wrong-run/wrong-session/external）+ duplicate ID + missing record。
   - Manifest root 層（§8.2）：`test_unrooting_any_required_root_fails_closed` 逐一移除每個 root（record 保留、manifest artifact 同步一致）皆 fail。
   - Event/manifest 層（§8.3）：run≠manifest、event body 改動保留舊 hash、manifest artifact 缺失/重複/內容不符。
   - Semantic 層（§8.4）：foreign operation scope（context/input/frame/prompt/request/verification/outcome）、stale 少 report/failure root、schema-invalid 少任一 attempt provider result、receipt-only accepted 0 為合法。
   - **Frame 覆蓋**：12/12 cases 皆為 frame-eligible，正向 packet↔snapshot equality 路徑已執行。公開 corruption matrix 中的 frame 內容竄改會先由 ArtifactRecord／event-chain 完整性層攔截；若不重簽 terminal event 與 manifest，無法單獨觸發後段 semantic mismatch exception。因此不建立 re-sign 偽造 chain 測試，保留 semantic check 作 cross-artifact defense-in-depth（它防 producer 一開始就產生兩份各自合法但語意不一致的 artifact，非重複 hash 檢查）。
6. **Committed Evidence path（TI-01）**：context/frame/input/provider/report/receipt/command/reduction/output/outcome 全 rooted 且 closure 通過；無 failure。
7. **Receipt-only path（TI-11）**：`accepted_evidence==()` 合法；仍有 interpretation/command/reduction refs；bundle 通過驗證。
8. **Stale path**：`_PauseOncePort` 併發提交 `TransitionSessionCommand(PAUSED)`；provider call 恰 1 次；outcome/run failed、reason `state_context_stale`；state 只有 pause transition（PAUSED、Evidence/interpretations 不變）；outcome 有 context/input/provider/report/failure、無 receipt/command/reduction/output；export+validate 通過。
9. **Schema-invalid path**：`invalid_output_llm` 兩 attempt → `output_schema_invalid`；兩 attempt 的 provider result 都 root，少任一即 fail。
10. **Re-export**：同一 trial 兩次 export+write 到獨立目錄，relative path 集合與每個 raw bytes 完全相等（含 `integrity-manifest.json`、`capture/manifest.json`）；A、B 各 regrade 後 byte map 不變。
11. **Suite identity**：`turn-interpret-c1-v2-pilot.v1`、12 cases（TI-01…08 development、TI-09…12 challenge）、frozen hash `sha256:5f60255dd323cd6c458b4ced7e067ca0a6c48cb9b3d2b5765bce8fada7a9bcc5` 未變。
12. **Focused no-network**：`test_interview_vnext_capture.py`+`_dependencies.py`+`_turn_eval_fixtures.py` → 28 passed / 0 skipped / 0 failed。
13. **Focused real PG**：`test_interview_vnext_turn_eval_runner.py` 27 passed；`_turn_eval_postgres.py`/`_fixed_replay_postgres.py`/`_recovery_postgres.py` 續綠。
14. **全部 vNext real PG**：`tests/test_interview_vnext_*` → 894 passed / 0 skipped / 0 failed。
15. **Full API no-network**：1071 passed / 211 skipped / 0 failed（baseline 198 skipped；+13 為新增 real-PG test nodes 在 no-network 由既有 `require_postgres` fixture 跳過，原 198 identity 不變、無 passed→skip 退化、無新增手寫 `pytest.skip/skipif`）。
16. **Full API＋real PG**：1282 passed / 0 skipped / 0 failed（baseline 1269；+13 新測試實跑 0 skipped）。
17. **Guards**：schema/execution-schema 測試綠；Alembic current/heads `0010 (head)` 無 `0011`；`git diff --check` 僅 autocrlf 警告；secret/reasoning scan 保留；`app/` 未 import `evals.*`（grep 命中為註解）；無 dependency/lockfile 變更。
18. **Local state**：工作樹只餘 docs（本次 docs commit）；test/eval rows 以 tenant-scoped `cleanup_trial_rows` 清除；無 `output/` bundle 殘留；`caliburn-db-1` 本次前已 Up（非本次啟動）→ 交付保持原狀、不停 db、不 down、不刪 volume。
19. **未完成項**：無。（paid live/V3-6/production promotion 非 R5-D 缺口。）
20. **Unblock**：最小 Authoring Core 解鎖（§18）。mock/reference 全綠**不**代表 true model quality 或 production promotion。

---

## 18. R5-D之後立即做什麼

R5-D完成後不再增加Turn Interpreter correctness工作包，除非code review找到真 blocker。下一步依ADR 0038直接做最小Authoring Core：

```text
Evidence（員工事實）
  → deterministic JobStateDigest
  → task-centered DocumentPatch proposal
  → 員工接受／修改／拒絕
  → canonical JobDocument revision
```

第一個可操作vertical slice的exact施工規格已落在
[2026-07-23 minimal Authoring Core plan](2026-07-23-interview-vnext-minimal-authoring-core-plan.md)：只做一個task proposal、
可選outputs、employee direct edit、accept/edit/reject、stale、accepted revision、deterministic JobStateDigest與scripted端到端
golden。**本切片不做indicator**；它依ADR 0038 §10延後到task/output產品loop成立之後。
上述最小 Authoring Core 已於 2026-07-23 完成；後續依該計畫 §20 進入 Context Engine、episode工作分析與最小單機workspace，
不再把時間投入 Authoring generic framework 或 SaaS 化。
 Agenda/Sufficiency、question.select、OpenRouter production composition、episode coding與K/S推論依ADR順序後接；不要再用R5-D當理由延後產品核心。
