# Interview AI vNext V3-5A R3-C——Runtime binding、durable conformance 與 Capture 完整性修正交接規格

- 日期：2026-07-19
- 狀態：**可直接實作；R3-C code 尚未開始，R4 blocked**
- 被審查的 baseline commit：`6ea5ed5412617cbae893e0baeab1abde6aa0d075`
- baseline subject：`feat(interview): execute resolved model calls with conformance gates`
- 上位決策：[`../adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md`](../adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md)
- 母計畫：[`2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`](2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md)
- 架構研究：[`../specs/2026-07-18-interview-vnext-llm-runtime-architecture-review.md`](../specs/2026-07-18-interview-vnext-llm-runtime-architecture-review.md)
- Scope：**只補正 R3 已發布契約的完整性，不提前實作 R4 route eligibility 分離**
- Release gate：R3-C 全部驗收完成前，**R4、paid live、V3-6、production route/Web、adapter promotion 皆 blocked**

本文件是 V3-5A 母計畫的 R3 corrective addendum。若本文件與 baseline commit 的註解、測試假設或交付摘要
衝突，R3 修正範圍以本文件為準；若與 ADR 0036 衝突，以 ADR 為準。本文件不改 R4 的責任：OpenRouter
route contamination 目前仍可維持 adapter 內 `ModelFailure` fail-closed，直到 R4 才把 wire outcome、evidence
normalization 與 eligibility policy 正式分離。

---

## 1. 白話：為什麼測試全綠還要補修

R3 已經把系統改成：先建立不可變的 provider binding，再把 request、binding、schema projection 交給 adapter，
provider 回來後保存 result、execution evidence 與 conformance report。方向正確，但 code review 發現有幾個
「資料看起來都有，實際上 gate 沒有鎖死」的缺口：

1. binding 說要使用 config A，adapter 實際拿 config B，只要 provider/model 相同仍會放行；
2. projection report 只要 policy name 相同，version/hash 改掉仍會放行；
3. durable write 接受多個互相獨立的布林與 outcome，可能保存矛盾的成功 checkpoint；
4. fresh-process recovery 只讀 result，沒有重新驗證 evidence/conformance；
5. Capture 雖然存了 binding/config/projection，event graph 與 manifest roots 不一定真正引用它們；
6. provider config artifact 宣告了一個不存在的 schema ID。

這些問題不一定會讓 happy-path 測試失敗，但會破壞本架構最重要的承諾：**任何 provider call、成功提交與
離線重播，都必須能證明自己使用的 exact binding/config/projection，以及當時通過的 exact conformance gate。**

R3-C 不是增加新功能，也不是重寫 provider adapter。它是把既有設計的 fail-closed 邊界補完整。

---

## 2. Code review 的可重現證據

### 2.1 Adapter config drift 目前會被接受

以 OpenAI reference adapter 做 no-network 最小重現：

```text
binding config: reasoning_effort=medium
runtime adapter config: reasoning_effort=high
binding.provider_config_hash != adapter.config_hash
_validate_binding(): ACCEPTED
```

OpenRouter 與 OpenAI 的 `_validate_binding()` 現在都只驗 gateway provider、requested model 與部分 schema/message
條件，沒有 exact 驗 `adapter_id`、`adapter_version`、`provider_config_hash`。這會讓 fresh-process recovery 或
composition wiring 在真正 HTTP 前失去 immutable binding 保證。

### 2.2 Projection policy identity 目前可被替換

已用 no-network 最小重現：

```text
binding schema projection policy: portable-strict-output/2.0.0/<approved hash>
report policy: portable-strict-output/9.9.9/sha256:000...000
report_hash: 依竄改後 definition 正確重算
artifact content hash: 依竄改後完整 report 正確重算
ResolvedModelCall(): ACCEPTED
```

目前 validator 的 `and` 條件實際只有效檢查 `policy_name`，沒有 exact 比對 policy version/hash，也沒有把
`target_profile` 對回已解析的 policy document。

### 2.3 Durable gate 目前信任彼此獨立的參數

`record_attempt_result()` 接收：

```text
outcome
wire_succeeded
conformance_eligible
result_artifact
execution_evidence_artifact
conformance_artifact
```

它只驗 artifact scope，沒有把三個 typed payload 解析後交叉核對。因此呼叫者若傳：

```text
outcome=SUCCEEDED
wire_succeeded=false
conformance_eligible=false
```

現行分支仍會把 checkpoint 推進 `provider_completed`，但 conformance event 會是 `skipped`。目前 executor 的
正常 caller 恰好傳一致值，不代表 durable boundary 本身有守住 invariant。

### 2.4 Recovery 目前不重新驗證 persisted gate

`PROVIDER_COMPLETED` recovery 只載入 `provider_result_artifact`，接著就跑 local verifier；`VERIFIED`、
`COMMITTED` 與 provider-attempt `FAILED` 的 early return 也沒有共用的 persisted provider gate validation。
checkpoint model 只保證 evidence/conformance refs 成對且非空，不能證明 refs 指向正確內容或 report 仍 eligible。

### 2.5 Capture 目前沒有完整 closure

`model.call.started` 沒有 input artifacts；model result event 沒有 request/binding/config/projection inputs；
conformance event input 只有 evidence，沒有 binding。eval runner 的 manifest roots 有 result/evidence/conformance，
但沒有 binding/config/projection。

Capture validator 只驗 event 與 manifest 明確列出的 refs，不會遞迴解析 request JSON 裡面的 `ArtifactRef`。
所以「request 內容裡有 ref」不能替代「event graph / manifest root 直接引用 artifact」。

---

## 3. Scope 與硬邊界

### 3.1 R3-C 必須完成

1. 建立一個 provider-neutral runtime adapter/binding preflight authority；
2. exact 驗證 projection policy name/version/hash/target profile；
3. 讓 durable write 從 typed result/evidence/conformance 派生 wire/conformance facts；
4. 所有 fresh-process terminal/recovery path 重驗 persisted provider gate；
5. 補齊 model/conformance event artifacts 與 manifest roots；
6. 移除不存在的 generic provider-config schema ID；
7. 補足 no-network 與 real PostgreSQL 負向測試；
8. 保持 no-network full suite、real PG focused suite 與 dependency guard 全綠；
9. migration head 保持 `0010`，不得新增 `0011`；
10. 一步一 commit，任何 commit 都不得留下已知 no-network suite failure。

### 3.2 R3-C 明確不做

- 不把 OpenRouter route contamination 從 `ModelFailure` 改成 wire success；該行為屬 R4；
- 不改 OpenRouter outbound URL/body/header、endpoint selection、retry 或 cost mapping；
- 不新增 Anthropic direct、OpenAI production route或另一個 provider；
- 不引入 agent framework、graph framework、provider SDK abstraction framework；
- 不改 `turn.interpret` prompt/output/verifier/domain semantics；
- 不跑 paid live probe、catalog或 12×3 batch；
- 不新增 SQL column/table/FK/migration；
- 不修改 frozen v1 schema 檔或歷史 Capture bundle；
- 不把 eval adapter import 到 production `app/` composition root；
- 不用 compatibility shim 同時接受 v1/v2 port。

### 3.3 R3-C 完成後仍然不代表什麼

完成 R3-C 只代表 R3 的 runtime contract、durability 與 Capture authority 可信；不代表 R4 adapter semantics、
C1 v2、完整 turn eval 或 production readiness 已完成。

---

## 4. 修正後唯一允許的資料流

```text
composition/eval wiring
  -> runtime provider config
  -> canonical config hash
  -> immutable ProviderBinding(adapter/model/config/policies)
  -> persisted binding/config/projection artifacts
  -> ModelCallRequest exact refs
  -> ResolvedModelCall exact policy validation
  -> adapter pre-HTTP runtime identity/config validation
  -> exactly one provider call
  -> ModelCallResult + ProviderExecutionEvidence
  -> deterministic ConformanceReport
  -> one atomic durable write
  -> checkpoint provider_completed only when gate is internally consistent
  -> every recovery reloads and revalidates persisted gate
  -> verifier/reducer
  -> Capture events + manifest close over all authoritative artifacts
```

禁止任何分支用 caller 傳入的布林、目前 deployment config、重新 catalog resolve 或 request 內未解參照的 JSON
來代替上述 authority。

---

## 5. 必須固定的 invariants

### 5.1 Runtime adapter/binding preflight

任何 adapter 在送出 HTTP 前必須 exact 滿足：

```text
runtime adapter ID       == binding.adapter_id
runtime adapter version  == binding.adapter_version
runtime gateway provider == binding.gateway_provider
runtime config hash      == binding.provider_config_hash
request binding ID/hash  == binding.binding_id/hash
request requested model  == binding.requested_model
request operation name   == binding.operation_name
```

任一不符：

- 回既有 provider-specific `binding_invalid` 類型的 local `ModelFailure`；
- `retryable=false`；
- transport/mock call count 必須是 `0`；
- result保留「被嘗試的」request/binding identity；execution evidence的adapter ID/version/gateway必須描述實際
  runtime adapter，不得從不相符的binding複製成假事實；
- 不建立假的 routing metadata，route/cache/transformation依既有unknown failure規則保存；
- evidence limitation/error artifact明確記錄runtime binding preflight失敗，但不保存完整config或secret；
- 不洩漏 config 值或 secret 到 safe message。

這是 binding safety，不是 R4 的 route eligibility policy，因此必須在 R3-C 完成。

### 5.2 Provider config artifact

R3-C 不發布假的 generic provider config schema。`provider_config` 是 composition-owned、provider-specific、
secret-free snapshot；目前 authority 是：

```text
canonical serialized config bytes
  -> ArtifactRef.content_hash
  -> ProviderBinding.provider_config_hash
  -> runtime adapter self._config.config_hash
```

三者必須 exact 相等。`provider-config.v1.schema.json` 目前不存在，因此：

- 刪除 production executor 與兩個 probe 內的 `PROVIDER_CONFIG_SCHEMA_ID` 常數；
- 新建立的 `provider.config` artifact 使用 `schema_id=None`；
- config 內容仍保留自身 `schema_version`；
- 不修改既有歷史 artifacts；
- 未來若要發布 provider-specific config schemas，另開 versioned design，不在 R3-C 猜一個 union schema。

### 5.3 Projection exact identity

`ResolvedModelCall` 與 recovery 必須先解析已知 policy，再 exact 驗證：

```text
report.policy_name       == policy.name
report.policy_version    == policy.version
report.policy_hash       == policy.policy_hash
report.target_profile    == policy.target_profile
report.projected hash    == request.output_schema_artifact.content_hash
report artifact hash     == canonical_hash(report full document)
binding policy identity  == policy name/version/hash
```

未知 policy name/version/hash 一律 fail closed，不得只因 name 相同而接受。不得在 adapter 內維護第二份 projection
policy registry。

### 5.4 Provider gate typed closure

一個 persisted provider gate 由下列資料組成：

```text
request
binding
result artifact -> ModelCallResult.v2
evidence artifact -> ProviderExecutionEvidence.v1
conformance artifact -> ConformanceReport.v1
```

必須驗證：

- 三個 artifact 都是 inline JSON、kind/schema/scope/attempt exact；
- generic ArtifactRecord content hash/byte size 正確；
- typed model 內部 `binding_hash`、`evidence_hash`、`report_hash` 正確；
- result/evidence 的 run/session/turn/operation/attempt/binding/provider/model exact；
- conformance binding ID/hash等於 binding；
- conformance `execution_evidence_hash` 等於 evidence；
- conformance `wire_outcome` 等於 result outcome；
- 依 binding conformance policy重新執行 `evaluate_conformance()`，完整 report 必須與 persisted report相等；
- success checkpoint 的 report 必須 `eligible=true`；
- wire failure 的 report 必須 `eligible=false` 且包含 `conformance.wire_not_succeeded`。

「完整 report 相等」是指 Pydantic model/canonical document equality，不只比較 `eligible`。

### 5.5 Durable classification truth table

`record_attempt_result()` 不再接受可獨立漂移的 `wire_succeeded` 與 `conformance_eligible` 參數；兩者從 validated
result/report 派生。`AttemptOutcome` 仍表示 executor 已考慮 local schema/repair budget 後的 durable classification，
但必須符合下表：

| Wire result | Conformance | 允許的 AttemptOutcome | Checkpoint |
|---|---|---|---|
| succeeded | eligible | succeeded | provider_completed |
| succeeded | eligible | retryable failure | calling；僅 local schema repair 尚有額度 |
| succeeded | eligible | non-retryable failure | failed；僅 local schema invalid且無repair額度 |
| succeeded | ineligible | non-retryable failure | failed；failure authority=conformance report |
| refused/incomplete/failed | ineligible + wire_not_succeeded | retryable或non-retryable failure | 依既有wire policy/budget |

下列組合必須在任何 artifact/event/checkpoint write 前 raise `CheckpointConflict` 或更精確的 integrity exception：

- `AttemptOutcome.SUCCEEDED` 但 wire不是 succeeded；
- `AttemptOutcome.SUCCEEDED` 但 conformance不eligible；
- wire succeeded且conformance ineligible，卻要求 retryable；
- wire failure的 persisted conformance 缺少 `wire_not_succeeded`；
- failure authority與分類不一致。

### 5.6 Recovery invariant

所有 fresh-process path 在回傳或進入下一階段前都必須重驗 persisted gate：

| Checkpoint/attempt state | Recovery要求 |
|---|---|
| calling + attempt calling | 不重打未知provider call；維持現行pending/deadline規則 |
| calling + result_recorded | 載入result/evidence/conformance，重驗後才建next attempt |
| provider_completed | 載入exact三件artifact，重驗eligible後才跑local verifier |
| verified | 重驗provider gate，再載入verification report，才可commit |
| committed | 重驗provider gate與committed artifacts，再回idempotent outcome |
| failed + provider refs | 重驗provider gate與failure authority，再回failed |
| failed + 無provider refs | 只允許明確的pre-provider/coordinator failure shape |

不得以 deterministic UUID 存在就視為正確；若 checkpoint 有 ref，必須載入該 exact ref並比較完整
`ArtifactRef`。retry prior evidence/conformance雖不留在checkpoint final pointers，仍必須依 deterministic attempt ID
載入並驗證對應 event/artifacts。

### 5.7 Capture closure

event graph 必須如下：

```text
model.call.started
  inputs: request, binding, provider-config, schema-projection

model.call.completed|failed
  inputs: request, binding, provider-config, schema-projection
  outputs: visible/raw/error/routing supporting artifacts, result, execution-evidence

provider.conformance.completed
  inputs: binding, execution-evidence
  outputs: conformance report
```

terminal run manifest roots至少包含：

```text
request
binding
provider-config
schema-projection
provider result
execution evidence
conformance report
verification/domain/response/failure artifacts（若存在）
```

順序必須 deterministic，artifact IDs 唯一。request JSON 內嵌的 refs 不算 event/root closure。

---

## 6. 指定的 code 結構

以下是 normative responsibility；函式名稱若因現有 style 微調，交付報告必須列出對應名稱，但不得把同一驗證
複製到多處形成不同 authority。

### 6.1 `llm/binding.py`

新增 neutral pure preflight：

```python
class RuntimeBindingMismatch(ValueError): ...

def require_runtime_binding(
    binding: ProviderBinding,
    *,
    adapter_id: str,
    adapter_version: str,
    gateway_provider: str,
    provider_config_hash: str,
) -> None: ...
```

它只做 exact identity/hash 驗證，不import SDK、eval config或application executor。OpenRouter/OpenAI adapter 都呼叫
這一個 function，再把 exception 翻成各自既有的 local binding failure。

### 6.1.1 LLM contract schema IDs

result/evidence/conformance artifact metadata不能從`operation_executor.py`與probe各自複製字串。將R3-C會共用的
active IDs收斂到provider-neutral LLM module（建議`llm/schema_ids.py`）：

```text
model-call-request.v2
model-call-result.v2
provider-binding.v1
schema-projection-report.v1
provider-execution-evidence.v1
provider-conformance-report.v1
```

executor、provider gate validator與eval probes只import這一份常數。`provider.config`刻意沒有generic schema ID，
不得加入上述清單。此module只含字串常數，不importapplication/evals，也不建立第二份schema catalog。

### 6.2 `llm/portable_schema.py`

把目前 executor 私有的 active policy identity 判斷收斂成 neutral resolver/validator：

```python
class SchemaProjectionMismatch(ValueError): ...

def resolve_schema_projection_policy(identity: ContractIdentity) -> SchemaProjectionPolicy:
    ...

def require_projection_report(
    *,
    policy: SchemaProjectionPolicy,
    report: SchemaProjectionReport,
    projected_schema_hash: str,
) -> None:
    ...
```

目前 registry 只有 `PORTABLE_STRICT_OUTPUT_POLICY_V2`；unknown identity fail closed。`ResolvedModelCall` 與 executor
共用，不再維持目前只檢查 name 的條件或第二份 `_resolve_projection_policy()` 邏輯。

### 6.3 `llm/conformance.py`

同樣提供 exact policy resolver與 persisted report validator：

```python
def resolve_conformance_policy(identity: ContractIdentity) -> ConformancePolicy:
    ...

def require_conformance_report(
    *,
    policy: ConformancePolicy,
    binding: ProviderBinding,
    evidence: ProviderExecutionEvidence,
    wire_outcome: ModelOutcome,
    report: ConformanceReport,
) -> None:
    ...
```

validator內部重新 `evaluate_conformance()` 並要求完整 report equality。executor、durable write、recovery共用。

### 6.4 `application/provider_gate.py`（新增）

建立一個不做I/O的 application-owned validation authority：

```python
@dataclass(frozen=True)
class ValidatedProviderGate:
    result: ModelCallResult
    evidence: ProviderExecutionEvidence
    conformance: ConformanceReport

def validate_provider_gate_artifacts(
    *,
    request: ModelCallRequest,
    binding: ProviderBinding,
    result_artifact: ArtifactRecord,
    evidence_artifact: ArtifactRecord,
    conformance_artifact: ArtifactRecord,
    require_eligible: bool | None,
) -> ValidatedProviderGate:
    ...
```

責任只有 §5.4 的 typed/cross-artifact validation；不開UoW、不打provider、不決定retry budget、不import evals。
這讓 durable write 與 recovery 使用同一套檢查。

### 6.5 `application/durable_operations.py`

修改 `record_attempt_result()`：

- 移除 `wire_succeeded`、`conformance_eligible` 參數；
- 從 attempt request artifact 載入 `ModelCallRequest`；
- 依 request exact refs載入並驗證 binding、provider config與schema projection；provider config full ref/content hash
  必須等於binding，projection必須通過exact policy validator；
- 在 `put`/event/checkpoint transition前呼叫 `validate_provider_gate_artifacts()`；
- 依 validated result/report派生 event status與failure authority；
- 依 §5.5 驗 `AttemptOutcome`；
- model result event補齊四個 inputs；
- conformance event input補 binding；
- 三件provider gate artifacts與兩個events仍維持同一transaction；
- 任一驗證失敗，整個UoW rollback，不留下partial artifacts/event/attempt transition。

不要把驗證放在 `operation_executor` 呼叫前後各做一次卻讓 `record_attempt_result()` 仍可被其他caller繞過。

### 6.6 `application/operation_executor.py`

新增單一 recovery loader，例如：

```python
async def _load_and_validate_provider_gate(...) -> ValidatedProviderGate:
    ...
```

它負責：

1. exact載入 request與binding/config/projection refs；
2. 確認 provider config artifact存在、完整ref/content hash等於binding；
3. 依 checkpoint或attempt載入result/evidence/conformance exact refs；
4. 呼叫共用 provider gate validator；
5. 根據 checkpoint status決定 `require_eligible=True/False/None`。

必須接到 §5.6 的每個分支，包括目前函式開頭的 `COMMITTED`、`FAILED` early return。不得只修
`PROVIDER_COMPLETED` 分支。

`_resolved_call_for_request()` 也必須載入 provider config artifact並比對完整ref，不能只驗 request ref hash與
binding hash；它不需要把 provider-specific config payload塞入 `ResolvedModelCall`，因為 adapter會用自己的
config hash做第二道preflight。

### 6.7 Provider adapters

修改：

- `evals/interview_vnext/providers/openrouter_chat.py`
- `evals/interview_vnext/providers/openai_responses.py`

兩者在既有 schema/body validation前先呼叫 neutral runtime binding preflight。各 mismatch test 必須斷言 transport
call count=`0`。不要在兩個adapter各自手寫不同的hash規則。

R3-C 不改它們對 contaminated route 的現行 wire outcome；該 fixture matrix留給 R4。

### 6.8 Eval runner與probes

- `turn_eval_runner.py` finalize前從 persisted request取出 binding/config/projection refs，加入 manifest roots；
- root排序與去重 deterministic；
- OpenRouter/OpenAI probe的 request/model event與manifest roots也補 binding/config/projection；
- probe新建的 provider config artifact使用 `schema_id=None`；
- R3-C 不執行live probe；
- 若 probe仍把 `conformance_passed` 當「wire success + local schema valid」，不得在R3-C宣稱它是完整R4 gate；
  R4必須改成真正 persisted evidence/report與taxonomy v2後才可重新開live gate。

### 6.9 Persistence/schema files

- 不新增migration；
- `OperationCheckpoint.v2` schema identity不變；
- 不修改 frozen v1 JSON schema；
- 若 pure function/exception不改Pydantic fields，不需重生schema；
- 刪除假的 provider config schema ID時，model request schema不用改，因`ArtifactRef.schema_id`本來可null；
- schema drift test必須證 active schemas可重生、歷史schemas byte-identical。

---

## 7. Test-first 修正矩陣

實作者必須先新增會在 baseline commit失敗的測試，再改production/eval code。不得只改既有assert讓它變綠。

### 7.1 Runtime binding preflight

OpenRouter與OpenAI各自覆蓋：

1. exact binding/config通過；
2. adapter ID mismatch → local binding failure，HTTP calls=0；
3. adapter version mismatch → HTTP calls=0；
4. gateway provider mismatch → HTTP calls=0；
5. config只有reasoning field不同、hash不同 → HTTP calls=0；
6. config只有storage/cache/plugin/routing field不同、hash不同 → HTTP calls=0（依provider現有欄位）；
7. requested model相同但config hash不同仍拒絕；
8. safe error artifact不含完整config、hash以外的敏感資料或API key。

### 7.2 Projection

每個case獨立：

1. policy name mismatch；
2. version mismatch但name相同；
3. policy hash mismatch但name/version相同；
4. target profile mismatch但identity相同；
5. report hash正確重算後仍因binding policy不符而拒絕；
6. artifact content hash正確重算後仍拒絕；
7. unknown policy identity fail closed；
8. active policy exact case通過；
9. fresh-process載回projection後走同一validator。

至少保留一個與code review相同的回歸向量：`2.0.0 -> 9.9.9`且完整重算report/artifact hashes。

### 7.3 Durable write truth table

real PostgreSQL測試至少覆蓋：

1. clean succeeded+eligible+local valid → provider_completed；
2. succeeded+ineligible → failed、failure artifact=conformance；
3. retryable wire failure → prior result/evidence/conformance落盤，checkpoint可進next attempt；
4. `AttemptOutcome.SUCCEEDED` + wire failure → rollback；
5. `AttemptOutcome.SUCCEEDED` + ineligible report → rollback；
6. succeeded+ineligible + retryable classification → rollback；
7. evidence binding hash與result不同 → rollback；
8. report evidence hash與evidence不同 → rollback；
9. report wire outcome與result不同 → rollback；
10. report為合法自我hash但不等於deterministic re-evaluation → rollback；
11. wrong kind/schema/scope/attempt → rollback；
12. rollback後沒有新增result/evidence/conformance artifacts、events或attempt transition。

### 7.4 Fresh-process recovery corruption matrix

對 `provider_completed`、`verified`、`committed` 至少參數化：

- result missing；
- evidence missing；
- conformance missing；
- checkpoint ref指向另一個同scope但不同content的artifact；
- evidence/report inline content或row hash tampered；
- evidence binding/model/provider mismatch；
- conformance report ineligible；
- conformance report self-hash合法但不是重新evaluate的結果；
- provider config artifact missing/mismatched；
- projection version/hash/target mismatch；
- persisted binding missing/mismatched。

預期一律：

```text
no provider HTTP call
no verifier/reducer/domain write
no checkpoint advancement
PersistedDataCorruption / CheckpointConflict（依現有exception boundary）
```

另覆蓋：

- committed clean recovery不打network且回byte-equivalent outcome；
- failed provider attempt recovery會重驗failure authority；
- pre-provider failed checkpoint沒有provider refs時仍可idempotent回failed；
- calling + recorded retry會重驗prior evidence/conformance後才claim next attempt。

### 7.5 Capture closure

1. `model.call.started` input refs exact且順序固定；
2. result event inputs/outputs exact；
3. conformance event input包含binding+evidence；
4. success、conformance failure、wire failure、retry各自event status正確；
5. manifest roots包含binding/config/projection/evidence/conformance；
6. root IDs唯一、順序deterministic；
7. 從export bundle刪除任一root artifact → integrity fail；
8. 替換任一root ref/hash → integrity fail；
9. 同一run重export/regrade不改manifest/event hashes；
10. request內有nested ref但manifest缺root的fixture必須被判 invalid，避免回歸成現況。

### 7.6 Provider config schema metadata

- 新artifact `provider.config.ref.schema_id is None`；
- artifact content hash仍等於config hash；
- binding仍exact引用config hash；
- schema writer不產生空殼`provider-config.v1.schema.json`；
- frozen historical schemas不變。

---

## 8. 建議 commit 切片

每個commit前都跑受影響focused tests + 完整no-network suite；C2/C3另跑real PostgreSQL focused。若實作時發現
無法在不留紅窗下切開，可合併相鄰slice，但不得用compatibility shim或提交已知紅測試。

### R3-C0——本文件與status lock

只改docs/AGENTS/status，不改code。

建議commit：

```text
docs(interview): specify R3 runtime integrity corrections
```

### R3-C1——Exact binding/config/projection preflight

修改neutral binding/projection helpers、ResolvedModelCall、兩個adapters與focused tests；同時移除假的provider config
schema ID。

建議commit：

```text
fix(interview): enforce exact resolved provider bindings
```

R3-C1不可改route contamination response semantics。

### R3-C2——Typed durable provider gate與recovery

新增`application/provider_gate.py`，修改durable write、executor所有recovery分支、scripted/test helpers與real PG tests。

建議commit：

```text
fix(interview): revalidate durable provider gates on recovery
```

### R3-C3——Capture closure

補model/conformance event refs、runner/probe manifest roots與bundle corruption tests。

建議commit：

```text
fix(interview): close provider artifacts into capture manifests
```

### R3-C4——Final status evidence

只在C1-C3全綠後回寫母計畫、README與測試數；R4才可改成unblocked。

建議commit：

```text
docs(interview): close R3 runtime integrity corrections
```

---

## 9. 驗收命令

全部從`apps/api`執行，使用locked environment。實作者可加入新test檔，但不得少跑同類。

### 9.1 Pure contracts與adapters

```powershell
uv run --locked pytest -q `
  tests/test_interview_vnext_llm_binding.py `
  tests/test_interview_vnext_schema_projection.py `
  tests/test_interview_vnext_llm_conformance.py `
  tests/test_interview_vnext_llm.py `
  tests/test_interview_vnext_openrouter_eval_adapter.py `
  tests/test_interview_vnext_openai_eval_adapter.py `
  tests/test_interview_vnext_openrouter_live_probe.py `
  tests/test_interview_vnext_openai_live_probe.py
```

### 9.2 Persistence/Capture focused（real PostgreSQL，0 skipped）

依`docs/runbook.md`使用本機`caliburn_test`，不可指向production或真使用者資料：

```powershell
$env:DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test'
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test'
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked pytest -q `
  tests/test_interview_vnext_capture.py `
  tests/test_interview_vnext_fixed_replay_postgres.py `
  tests/test_interview_vnext_recovery_postgres.py `
  tests/test_interview_vnext_turn_eval_postgres.py
```

`alembic current`必須仍是`0010 (head)`；任何skip或0011都不算完成。

### 9.3 Full no-network API suite

清除會啟用live/network的env，只保留測試需要的本機設定：

```powershell
uv run --locked pytest -q
```

允許既有「明確需要DB/network」項目在沒有對應env時skip，但不得新增fail或把R3-C focused tests變成skip。交付
報告需同時列no-network full suite與real PG focused的passed/skipped數，不能只報其中一個。

### 9.4 Dependency、schema與hygiene

```powershell
uv run --locked pytest -q tests/test_interview_vnext_dependencies.py
uv run --locked pytest -q tests/test_interview_vnext_execution_schemas.py
git diff --check
git status --short
```

再人工確認：

```powershell
rg -n "evals\.interview_vnext|openrouter_chat|openai_responses" app
rg -n "provider-config\.v1\.schema\.json" app evals tests
Get-ChildItem alembic\versions | Sort-Object Name | Select-Object -Last 3 Name
```

預期：production `app/`無`evals.*` import；假provider config schema ID無active使用；沒有0011。

---

## 10. 禁止用以下方式讓測試變綠

- 只在test helper保證config相同，不補adapter preflight；
- 只比較provider/model，不比較adapter version/config hash；
- projection只比較name或只比較report self-hash；
- 在recovery重新resolve目前deployment binding/config，取代persisted refs；
- recovery重新算一份conformance但不比較persisted report；
- 看到persisted report ineligible仍繼續local verifier；
- 捕捉integrity exception後改成普通provider failure或自動repair；
- 用request JSON nested refs宣稱Capture closure已完成；
- 建一個內容為`additionalProperties: true`的假provider config schema；
- 刪除／skip tamper tests；
- 放寬Capture validator以容忍missing artifact；
- 在R3-C順手修改OpenRouter route contamination outcome；
- 打live API驗證本修正。

---

## 11. 完成定義

只有同時滿足下列條件才能把R3-C標成complete、開始R4：

- [ ] 兩個adapter都exact驗adapter ID/version/provider/config hash且pre-HTTP fail closed；
- [ ] code review的medium/high config drift向量已轉成回歸測試；
- [ ] projection name/version/hash/target profile exact；
- [ ] `2.0.0 -> 9.9.9` forged report向量已轉成回歸測試；
- [ ] `record_attempt_result()`不再接受獨立wire/conformance布林；
- [ ] durable write解析並交叉驗證三個typed artifacts；
- [ ] provider_completed/verified/committed/failed/retry recovery共用同一gate validator；
- [ ] tampered/missing binding/config/projection/evidence/conformance全部fail closed且0 HTTP；
- [ ] model/conformance events與manifest roots形成完整closure；
- [ ]不存在的provider config schema ID已移除，未偽造替代schema；
- [ ] no-network full suite 0 fail；
- [ ] real PostgreSQL focused 0 skipped、0 fail；
- [ ] dependency/schema drift/hygiene全綠；
- [ ] Alembic仍0010、無migration；
- [ ] 未執行network/paid live；
- [ ] 每個code commit author/committer仍只有owner指定identity；
- [ ] 工作樹無未解釋變更；
- [ ] 母計畫與README回寫exact commit/test evidence。

---

## 12. 實作者交付回報模板

```text
R3-C status:
baseline SHA:
R3-C commit SHAs / subjects:
files added/modified:

Runtime binding:
- OpenRouter adapter ID/version/config hash checks:
- OpenAI reference adapter ID/version/config hash checks:
- zero-HTTP mismatch matrix:

Projection:
- exact policy identity helper:
- forged 2.0.0 -> 9.9.9 regression result:

Durable gate:
- removed parameters:
- typed cross-validation authority:
- impossible classification tests:
- transaction rollback evidence:

Recovery:
- calling/result_recorded:
- provider_completed:
- verified:
- committed:
- failed:
- missing/tampered matrix and exception types:

Capture:
- model event exact inputs/outputs:
- conformance event exact inputs/outputs:
- manifest root set:
- delete/tamper bundle tests:

Schema/migration:
- provider config schema_id decision:
- schema drift:
- Alembic head / migration files:

Tests:
- pure/focused:
- OpenRouter adapter:
- OpenAI reference adapter:
- full no-network:
- real PostgreSQL focused (0 skipped required):
- dependency guard:
- git diff --check:

Network/paid calls: none
R4 route eligibility behavior changed: no
Known limitations/unresolved items:
R4 unblocked: yes/no with reason
```

交付摘要不能只寫「全部通過」。必須列出exact mismatch/tamper cases、HTTP call count、PG skipped數、migration
head，以及R4行為確實未提前改動。
