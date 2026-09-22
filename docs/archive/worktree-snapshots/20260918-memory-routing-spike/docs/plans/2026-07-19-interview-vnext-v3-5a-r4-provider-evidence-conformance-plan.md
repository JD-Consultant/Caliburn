# Interview AI vNext V3-5A R4——Provider wire evidence 與 conformance eligibility 分離實作交接規格

- 日期：2026-07-19（實作完成回寫：2026-07-20）
- 狀態：**已完成；R4-1～R4-4 全部落地並通過驗收，執行結果與逐項回報見 §19**
- 上位決策：[`../adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md`](../adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md)
- 母計畫：[`2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`](2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md)
- R3-C baseline：[`2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md`](2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md)
- 範圍：**V3-5A R4 only**；OpenRouter-first，OpenAI 僅為 mocked/reference adapter
- 禁止：paid live、production route/Web、provider promotion、direct Anthropic、migration `0011`

---

## 1. 白話：R4 到底在做什麼

目前 OpenRouter adapter 把兩件不同的事混成同一件事：

1. 供應商是否真的回了一個可解析的 structured response；
2. 這個 response 是否走了我們核准的 model、endpoint、單次 direct route、無 cache、無 pipeline。

舊行為只要看到 route metadata 不符合，就把整個 response 改成
`ModelFailure(openrouter.route_contaminated)`。這雖然會擋住錯誤結果，但也會把真正的 provider output、實際
route 與污染方式壓成一個 generic failure，無法回答「模型本身不好，還是 gateway pipeline 改過內容」。

R4 要改成三層：

```text
Provider HTTP response
        │
        ▼
adapter：忠實記錄 wire result + normalized execution evidence
        │
        ▼
application conformance policy：判斷這次 execution 是否 eligible
        │
        ├─ eligible       → 才可進 local schema / semantic verifier / reducer
        └─ ineligible     → terminal fail closed，但保留 raw payload 與 route evidence
```

最後的安全性沒有放寬：污染結果仍不得進 domain state，也不得進模型品質分母。差別是失敗 authority 從假的
「模型失敗」改成真的 `provider.conformance_failed`，並保留可重播、可稽核的證據。

---

## 2. R4 entry baseline 與不可重做的部分

R3 與 R3-C 已完成下列基礎，R4 必須直接使用，不得另建第二套：

- `ResolvedModelCall.v1` 已包含 request、immutable `ProviderBinding.v1` 與 schema projection；
- adapter 已在 HTTP 前用 `require_runtime_binding()` exact 驗 adapter ID/version、gateway 與 config hash；
- `ModelCallResult.v2`、`ProviderExecutionEvidence.v1`、`ConformanceReport.v1` 已發布；
- executor 已依 wire result → conformance → local validation 的順序 gate；
- result、evidence、conformance 已可在同一 transaction 保存；
- fresh-process recovery 會重新 typed parse 與 deterministic re-evaluate conformance；
- Capture events、manifest roots 與 multi-attempt closure 已完成；
- migration 仍是 `0010 (head)`，R4 不需要 schema migration。

R3-C 最終 baseline：

| Gate | Baseline |
|---|---:|
| 全部 `test_interview_vnext_*.py` + real PostgreSQL | `653 passed, 0 skipped` |
| 完整 API no-network | `844 passed, 197 skipped, 0 failed` |
| dependency guard | `5 passed` |
| Alembic | `0010 (head)` |

R4 不得修改 R3-C 的 artifact identity、event closure、checkpoint transition 或 recovery authority；只有新測試真的
證明既有 generic conformance gate 有 bug，才可停下來回報，不能在 provider adapter 內繞過。

---

## 3. 2026-07-19 官方資料核對結果

### 3.1 OpenRouter Router Metadata

官方 Router Metadata 文件確認：

- request 必須送 `X-OpenRouter-Metadata: enabled` 才會取得 `openrouter_metadata`；
- success 與部分 error response 都可帶 metadata；
- `requested`、`strategy`、`attempt`、`endpoints`、`attempts`、`pipeline` 是不同 execution facts；
- `attempt > 1` 表示先前 provider attempt 失敗後才成功；
- pipeline stage 只有真的執行才出現，no-op 會省略；
- stage type 會持續增加，unknown stage 必須 opaque、forward-compatible 解碼；
- cache hit 會刻意移除 `openrouter_metadata`，避免客戶把 stale route metadata 當成當次 route；
- metadata schema 採 additive evolution，不能因新增欄位就 parse failure。

來源：[OpenRouter Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata)

### 3.2 OpenRouter Provider Routing

官方 routing 文件確認：

- `provider.order` 只表示優先順序；若不要其他 provider，必須同時關閉 fallback；
- `allow_fallbacks=false` 才是禁止改走其他 provider 的明確 request constraint；
- exact endpoint variant 必須使用完整 slug；base slug 可能匹配同 provider 的多個 region/variant；
- `require_parameters=true` 才會排除不支援 request parameters 的 endpoint。

來源：[OpenRouter Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)

因此 R4 保留既有 exact model/endpoint snapshot、`order == only == one endpoint`、
`allow_fallbacks=false`、`require_parameters=true`，不因 response normalization 重寫 outbound request。

### 3.3 OpenRouter pipeline 與 plugins

官方目前列出的 pipeline 類型包含：

- `guardrail`；
- `plugin`；
- `server_tools`；
- `response_healing`；
- `context_compression`。

官方 plugins 文件也明確說明 plugin 可能注入或修改 request/response，例如 PDF parsing、response healing 與
context compression。這些是 execution 事實，不是 provider wire error。

來源：[OpenRouter Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata)、
[OpenRouter Plugins](https://openrouter.ai/docs/guides/features/plugins/overview)

### 3.4 OpenRouter error 與 cache

官方 error 文件要求優先使用 stable `error_type`，不能只看 HTTP status。HTTP `200` 仍可能在 body 中帶 provider
error；`429`/`503` 可能帶 `Retry-After`。R4 保留現行 stable error table 與 executor-owned retry，adapter 仍然
零 retry。

官方 response caching 文件確認 `X-OpenRouter-Cache-Status: HIT|MISS`，且 cache hit 的 billable token counters
會是 0。反過來不成立：token 為 0 不是 cache hit 的充分證據。

來源：[OpenRouter Errors and Debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging)、
[OpenRouter Response Caching](https://openrouter.ai/docs/guides/features/response-caching)

### 3.5 OpenAI Responses reference

OpenAI 官方 Responses API reference 顯示 response 有獨立 `status`、`model`、typed `output[]` 與 usage details；
Structured Outputs 可保證 schema shape，但 refusal 仍是獨立 output 類型，應由 application 明確分流。官方也建議
能用 Structured Outputs 時不要退回舊 JSON mode。

來源：[OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)、
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

R4 不改 OpenAI request shape、SDK lock 或 model lock；只用官方語意核對 reference adapter 的 wire/evidence
分層。

---

## 4. R4 authoritative decisions

### 4.1 Adapter 只描述事實，不決定 eligibility

provider adapter 可以決定：

- HTTP／SDK exception 如何轉成 typed wire failure；
- provider status、finish reason、refusal、incomplete 如何正規化；
- visible structured payload 是否可安全 parse；
- route、pipeline、cache、usage、cost 有哪些可觀察 facts；
- unknown/malformed facts 應填 null、`unknown` 與 limitation。

provider adapter 不可以決定：

- 這個 route 是否可進 benchmark；
- 某個 moderation 是否「安全所以可以接受」；
- model/endpoint mismatch 是否可被 allowlist 例外放行；
- ineligible output 是否可進 local verifier 或 reducer；
- trial disposition 或 promotion eligibility。

上述 policy 全部由 application-owned `attribution-strict/1.0.0` 與 downstream harness gate 決定。

### 4.2 R4 不升 neutral contract version

本切片沿用：

- `model_call_result.v2`；
- `model_call_envelope.v2`；
- `provider_execution_evidence.v1`；
- `provider_conformance_report.v1`；
- `attribution-strict/1.0.0`。

理由是現有 neutral fields 已可表達 gateway model、selected upstream、attempt、pipeline、cache 與 raw source
artifact。R4 只修 provider-specific normalization 與 wire semantics，不修改已發布 schema，也不新增 migration。

如果實作時發現某個必須影響 eligibility 的事實無法以現有 fields、null/unknown 與 raw artifact 誠實表示，必須
停止並提出 contract/ADR 修訂；禁止把 policy verdict 偷塞進 `limitations`、`status` 或假造 pipeline stage。

### 4.3 Binding 仍由 `ResolvedModelCall` 傳入

母計畫舊文字曾寫 adapter constructor 接 `config + binding + schema_catalog + client`；R3 已確立每次 call 的
authoritative binding 在 `ResolvedModelCall.binding`。R4 以現行程式為準：

```python
adapter = OpenRouterChatEvalAdapter(
    api_key=...,
    config=config,
    catalog=catalog,
    http_client=client,
)
envelope = await adapter.generate_structured(resolved_call)
```

不得再把 binding 複製進 constructor，否則 constructor binding 與 recovered call binding 可能 drift。每次 call
仍先執行 `require_runtime_binding()`。

### 4.4 `CacheStatus` 的精確語意

`ProviderExecutionEvidence.cache_status` 在 R4 表示「是否直接重播完整 response、因此沒有當次 upstream model
generation」；它不是 prompt/KV cache telemetry。

- OpenRouter `X-OpenRouter-Cache-Status: HIT` → `CacheStatus.HIT`；
- OpenRouter `...: MISS` → `CacheStatus.MISS`；
- header 缺失但 router metadata 完整 → `CacheStatus.ABSENT`；
- header 缺失且 router metadata 也缺失 → `CacheStatus.UNKNOWN`；
- direct OpenAI Responses → `CacheStatus.ABSENT`；
- `usage.cache_read_tokens > 0` 只保存在 `TokenUsage`，不得改成 response cache hit。

`attribution-strict/1.0.0` 只允許 `ABSENT` 與 `MISS`；`HIT`、`UNKNOWN` 仍 fail closed。

### 4.5 `raw_routing_artifact` 的 provider-neutral 解釋

現行 field 名稱保留。它代表「支撐 normalized route facts 的 immutable provider-specific source artifact」：

- OpenRouter：`provider.openrouter.routing` artifact；
- direct OpenAI reference：可指向已 redacted、immutable 的 raw Responses artifact，因 direct endpoint 沒有另一層
  router metadata。

不得建立假的 OpenAI router metadata。direct adapter 的 endpoint 事實來自 exact adapter endpoint + outbound
call，resolved model 來自 response。

### 4.6 OpenRouter-first 不變

R4 必須先完成 OpenRouter adapter 與 OpenRouter mocked probe。OpenAI 只更新既有 reference adapter，目的只是
證明 neutral contract 不是 OpenRouter 專用；不得執行 OpenAI live，不得新增 Anthropic direct adapter。

---

## 5. Exact wire／evidence／conformance 三層語意

### 5.1 Wire result

`ModelCallResult` 只回答「provider boundary 得到了什麼」：

| Wire condition | `ModelOutcome` | 說明 |
|---|---|---|
| structured object 可安全 parse | `succeeded` | 即使 route/model/pipeline 不合格仍是 wire success |
| provider 明確 refusal/content filter | `refused` | 不把 refusal 當 JSON |
| max token／partial terminal | `incomplete` | 不猜剩餘 JSON |
| transport/HTTP/provider error | `failed` | retryability 仍由 typed failure 決定 |
| invalid JSON/root/cardinality/tool output | `failed` | 仍是 wire/output protocol failure |

下列情況不再產生 `ModelFailure`：

- top-level resolved model 不在 binding allowlist；
- selected upstream provider/model 不符；
- route metadata 缺失；
- `strategy != direct`；
- attempt 不等於 1；
- pipeline 非空；
- cache hit/unknown。

### 5.2 Execution evidence

`ProviderExecutionEvidence` 只回答「這次 execution 發生了什麼」。所有欄位都必須來自：

- immutable binding/request；
- exact outbound projection；
- provider response/header；
- deterministic provider-specific normalizer。

禁止把 binding 的 expected value 複製到 actual 欄位來製造 clean evidence。

### 5.3 Conformance report

executor／probe 以同一純函式建立：

```python
policy = resolve_conformance_policy(call.binding.conformance_policy)
report = evaluate_conformance(
    policy=policy,
    binding=call.binding,
    evidence=envelope.execution_evidence,
    wire_outcome=envelope.result.outcome,
)
```

- wire 非 `succeeded` → `eligible=false + conformance.wire_not_succeeded`；
- wire `succeeded` + facts exact → `eligible=true`；
- wire `succeeded` + 任一 mismatch/unknown → `eligible=false` + deterministic reason codes；
- wire retryability 不得被 conformance 改寫；
- wire succeeded 但 ineligible 固定 non-retryable、failure authority 是 conformance artifact。

---

## 6. OpenRouter pure routing normalizer

### 6.1 新檔與責任

新增：

```text
apps/api/evals/interview_vnext/providers/openrouter_routing.py
apps/api/tests/test_interview_vnext_openrouter_routing.py
```

`openrouter_routing.py` 必須是 pure/provider-specific module：

- 不打 network；
- 不讀 env/API key；
- 不 import executor、scheduler、grader 或 DB；
- 不呼叫 `evaluate_conformance()`；
- 不回 `eligible`、`clean_route`、`failures` 或 conformance reason code；
- 只解析 route facts、pipeline stages、cache status 與 limitations。

### 6.2 建議 data shape

實作者可調整 private class 名稱，但輸出語意不可變：

```python
@dataclass(frozen=True)
class OpenRouterRoutingFacts:
    metadata_present: bool
    metadata_requested_model: str | None
    route_strategy: str | None
    router_attempt: int | None
    selected_provider: str | None
    selected_model: str | None
    selected_count: int | None
    attempts: tuple[object, ...]
    raw_pipeline: tuple[object, ...]
    pipeline_stages: tuple[ProviderPipelineStage, ...]
    transformation_status: TransformationStatus
    cache_status: CacheStatus
    region: object | None
    is_byok: bool | None
    limitations: tuple[str, ...]
```

private dataclass 不需發布 JSON schema；immutable persisted authority 仍是 routing artifact +
`ProviderExecutionEvidence.v1`。

### 6.3 Endpoint shape

官方 2026-07-19 canonical shape 是：

```json
{
  "endpoints": {
    "total": 1,
    "available": [
      {"provider": "Anthropic", "model": "...", "selected": true}
    ]
  }
}
```

既有 synthetic/歷史資料另有 flat array。normalizer 必須：

1. 優先支援官方 nested `endpoints.available[]`；
2. 保留 flat array backward-compatible read；
3. nested `selected` object 與 `available[].selected=true` 若指同一 provider/model，只算一筆；
4. selected count 不等於 1 時 provider/model 都填 null；
5. unknown additive keys 忽略但保存在 raw routing artifact；
6. endpoints 非 object/list 時不丟 exception，填 unknown + limitation。

不得因 official shape 已明確就刪除歷史 flat decoder；官方自己要求 additive、permissive decode。

### 6.4 `upstream_endpoint` 的 provenance

Router metadata 直接回 selected provider/model，不一定回傳請求時使用的完整 endpoint slug。R4 不可無條件把
`binding.upstream_endpoint` 複製成 observed fact。

只有下列條件全成立，才能把 `evidence.upstream_endpoint` 設成 binding/config 中的 exact slug，並視為由
outbound constraint + response facts 共同 attested：

1. runtime binding/config preflight 已通過；
2. outbound `provider.order` 與 `provider.only` 都只有該 exact slug；
3. `allow_fallbacks=false`；
4. metadata `requested` 等於真正送出的 `request.requested_model`；
5. exactly one selected endpoint；
6. selected provider 等於 binding upstream provider；
7. selected model 在 binding accepted upstream models；
8. attempt/attempts metadata 沒有自相矛盾。

任一條件不成立時：

- actual selected provider/model 仍照實填入（若可唯一解析）；
- `upstream_endpoint=None`；
- 加入 stable limitation；
- raw artifact 保留原始 facts；
- conformance 會以 missing/mismatch fail closed。

這不是 adapter 做 policy verdict，而是拒絕把「期望值」偽裝成「已證實的 execution fact」。

### 6.5 Pipeline normalization table

每個 raw stage 依原始順序建立一個 `ProviderPipelineStage`，index 從 1 連續編號：

| Raw `type` / `name` | normalized status | 說明 |
|---|---|---|
| 無 stage 或 metadata 存在但 `pipeline` 缺失/空陣列 | `clean` | 官方說 no-op stage 會省略 |
| `guardrail` | `inspected` | 包含 moderation/content filter；是否 flagged 不影響 strict attribution |
| legacy `moderation` / `content_filter` | `inspected` | 相容已捕獲的舊 metadata |
| `context_compression` | `mutated` | prompt/messages 已改動 |
| `response_healing` | `mutated` | provider output 已修復 |
| `server_tools` | `mutated` | server-side tool execution/injection |
| `plugin` + known `web-search`/`file-parser` | `mutated` | 外部內容注入/解析 |
| known rewrite/redaction/message-transform alias | `mutated` | request/response 被改寫 |
| unknown type/name、非 object stage | `unknown` | 不猜；保留 opaque hash |
| `pipeline` 本身不是 array | overall `unknown` | raw artifact 保存原值 + limitation |

每個 stage：

- `stage_type` 使用可驗證的 raw non-empty string；否則固定 `unknown`；
- `name`、`status` 只讀同名 top-level scalar，不從 free-form `data` 猜；
- `details_hash=canonical_hash(raw_stage)`；
- free-form `data` 不複製進 neutral evidence，只留 raw routing artifact；
- overall transformation 使用既有 `derive_transformation_status()`：`unknown > mutated > inspected`。

即使 `guardrail` 顯示 `flagged=false`，`attribution-strict/1.0.0` 仍因 pipeline 非空與 inspected 而
ineligible。R4 不建立 production-safe allowlist。

### 6.6 Cache normalization

OpenRouter response allowlisted headers新增：

```text
x-openrouter-cache-status
x-openrouter-cache-age       # 可保存，非 eligibility authority
x-openrouter-cache-ttl       # 可保存，非 eligibility authority
```

判定規則：

| Header | Metadata | `CacheStatus` |
|---|---|---|
| `HIT` | 通常缺失 | `hit` |
| `MISS` | 可存在 | `miss` |
| unknown non-empty value | 任意 | `unknown` + limitation |
| 缺失 | metadata present | `absent` |
| 缺失 | metadata missing | `unknown` + limitation |

禁止用下列 heuristic 宣稱 cache hit：

- token counters 全 0；
- latency 很低；
- generation ID 格式；
- cost 為 0；
- metadata 單獨缺失。

---

## 7. OpenRouter adapter exact control flow

### 7.1 保留不動

以下行為與 test 必須 byte/exact 維持：

- URL `https://openrouter.ai/api/v1/chat/completions`；
- `Authorization`、`Content-Type`、`Accept`、`X-OpenRouter-Metadata: enabled`；
- exact provider block、fallback off、require parameters、plugins disabled；
- messages、portable JSON schema 與 reasoning request projection；
- one durable attempt = one HTTP call；
- adapter/transport 零 retry；
- 429/500/timeout call count 各 exact 1；
- stable `error_type` mapping；
- refusal/incomplete/error/cardinality/tool/JSON/root 分流；
- raw/visible/error artifact、reasoning redaction、secret scan；
- usage/cost Decimal、不以 float 重算；
- local semantic validation 仍在 executor。

### 7.2 新 response pipeline

建議流程如下，順序是規格：

```text
1. HTTP/SDK exception → typed wire failure（既有）
2. decode body；建立 redacted raw artifact
3. 若 body 是 object：平行 normalize routing/cache/pipeline facts
4. top-level error / non-2xx → typed wire failure
5. 驗 protocol envelope、generation ID、top-level model
6. 驗 choice cardinality、embedded error、finish reason
7. parse visible JSON object
8. 建 ModelCallResult（不看 eligibility）
9. 用同一組 routing facts 建 ProviderExecutionEvidence
10. 回 ModelCallEnvelope
11. adapter 外的 executor/probe evaluate conformance
```

步驟 3 是 observation，不得搶在 top-level error 前改變 wire outcome。即使 error response 有 metadata，結果仍是
wire failed，但 evidence 應盡量保存已知 route/pipeline facts。

### 7.3 移除的舊邏輯

從 `providers/openrouter_chat.py` 移除：

- `_RoutingCheck.failures` 與 `.clean`；
- `model_match`、`provider_model_match`、`pipeline_clean` 等 policy booleans；
- `routing_conformance()`；
- routing artifact 內的 `conformance` object；
- `openrouter.route_contaminated` failure assembly；
- response resolved model mismatch直接 `RESOLVED_MODEL_MISMATCH`；
- route mismatch時建立 error artifact。

`FailureKind.RESOLVED_MODEL_MISMATCH` enum 與歷史 fixtures/schema 先保留，R4 不做歷史 contract cleanup；只是 active
OpenRouter/OpenAI response path 不再用它表達 eligibility。

### 7.4 Routing artifact v2

OpenRouter routing artifact payload 改成：

```text
schema_version = openrouter_routing.v2
requested_model                         # outbound request
metadata_requested_model                # metadata actual/null
resolved_model                          # top-level body model/null
catalog_canonical_model
configured_endpoint_slug
expected_provider_name
selected_provider_name
selected_model
selected_count
strategy
router_attempt
attempts                                # sanitized raw
pipeline                                # sanitized raw
pipeline_stage_summaries[]              # index/type/name/status/transformation/details_hash
transformation_status
cache_status
cache_header_value
is_byok
region
generation_id
http_request_id
cost
usage_total_mismatch
normalization_limitations[]             # sorted unique
```

不得包含：

- `eligible`；
- `conformance`；
- `pipeline_clean`；
- promotion/trial disposition；
- API key、Authorization、reasoning 原文。

僅 route ineligible 不建立 `provider.openrouter.error` artifact；error artifact 只屬於真正 wire failure。如此
wire-success + conformance-failure 的 authority 才不會再次混淆。

### 7.5 Unified evidence builder

現行 success path 與 failure path 使用不同 evidence helper，導致 error response 內可用 metadata 被丟掉。R4 改成：

- 無 response（preflight/deadline/transport）使用 route-less unknown helper；
- 只要取得 parseable object body，就用同一個 facts → evidence builder；
- result outcome 不決定是否保存 known routing facts；
- evidence `gateway_resolved_model` 使用 top-level actual model；
- evidence `upstream_provider/model` 使用唯一 selected actual 值；
- evidence `upstream_endpoint` 依 §6.4 attestation 規則；
- evidence `route_strategy`、`upstream_attempt_count` 使用 actual metadata；
- evidence pipeline/cache 依 pure normalizer；
- evidence `raw_routing_artifact` 指 routing v2 artifact；
- missing/ambiguous facts 明列 sorted unique limitations。

---

## 8. Exact outcome matrix

下表是 adapter + conformance 的不可自行解讀規格：

| Case | HTTP calls | Wire result | Evidence | Conformance / next action |
|---|---:|---|---|---|
| runtime binding mismatch | 0 | `failed/runtime_binding_mismatch` | runtime adapter facts，其餘 unknown | `wire_not_succeeded` |
| deadline expired before call | 0 | retryable timeout failure | route/cache unknown | `wire_not_succeeded` |
| 429 / timeout / 5xx | 1 | 現行 typed failure | 保存可得 error metadata | retry 只由 executor wire policy決定 |
| top-level/choice embedded error | 1 | 現行 failed/refused | 若有 metadata/pipeline則照實保存 | `wire_not_succeeded` |
| valid structured output + clean direct route | 1 | `succeeded` | clean/absent-or-miss | eligible |
| valid output + metadata missing | 1 | `succeeded` | route unknown + limitation | ineligible `route_metadata_missing` |
| valid output + metadata requested mismatch | 1 | `succeeded` | actual metadata保存；endpoint不可attest | ineligible，至少 `route_metadata_missing` |
| valid output + top-level model mismatch | 1 | `succeeded` | actual gateway model | ineligible `gateway_model_mismatch` |
| valid output + selected provider mismatch | 1 | `succeeded` | actual provider/model；endpoint null | ineligible provider/endpoint reasons |
| valid output + selected model mismatch | 1 | `succeeded` | actual selected model；endpoint null | ineligible upstream model/endpoint reasons |
| valid output + selected count != 1 | 1 | `succeeded` | provider/model/endpoint null | ineligible route metadata missing |
| valid output + `strategy != direct` | 1 | `succeeded` | actual strategy | ineligible route strategy mismatch |
| valid output + attempt > 1 | 1 | `succeeded` | actual attempt | ineligible upstream attempt mismatch |
| valid output + guardrail/moderation | 1 | `succeeded` | inspected pipeline | ineligible pipeline + transformation |
| valid output + compression/healing/tool/plugin | 1 | `succeeded` | mutated pipeline | ineligible pipeline + transformation |
| valid output + unknown stage | 1 | `succeeded` | unknown pipeline + opaque hash | ineligible pipeline + transformation |
| valid output + cache HIT | 1 | `succeeded` | cache hit，route通常unknown | ineligible cache + route reasons |
| invalid JSON + route contamination | 1 | `failed/output_parse_failed` | route facts仍保存 | conformance只回 `wire_not_succeeded` |
| non-object root/cardinality/tool call | 1 | 現行 output failure | route facts仍保存 | `wire_not_succeeded` |
| refusal/incomplete + route contamination | 1 | `refused` / `incomplete` | route facts仍保存 | `wire_not_succeeded`；不進quality output |

重要：wire 非 success 時，現行 conformance evaluator只回 `wire_not_succeeded`，不另外列 pipeline reasons；完整
pipeline facts仍在 evidence/raw artifact。不得為了多列原因改寫 wire retryability。

---

## 9. OpenAI direct reference adapter

### 9.1 不做的事

- 不執行 OpenAI live；
- 不改 `openai==2.46.0` lock；
- 不改 request body、reasoning、store/background/stream/truncation；
- 不加入 OpenAI production composition root；
- 不讓 `app/` import `evals.*`；
- 不把 OpenAI 變成 primary provider。

### 9.2 Exact reference behavior

`OpenAIResponsesEvalAdapter` 改為：

- completed + unique valid structured output → wire `succeeded`；
- response.model 不在 accepted models時不再回 `RESOLVED_MODEL_MISMATCH`；
- evidence `gateway_resolved_model`、`upstream_model` 保存 actual response.model；
- evidence `upstream_provider="OpenAI"`、`upstream_endpoint="responses"`、strategy `direct`、attempt 1；
- evidence `provider_request_id=response._request_id`；
- evidence `generation_id=response.id`；
- evidence `raw_routing_artifact` 指 immutable/redacted raw Responses artifact；
- evidence `cache_status=ABSENT`；OpenAI `cached_tokens` 只映射到 usage；
- clean exact response 可通過同一 `attribution-strict` pure evaluator；
- resolved model mismatch由 conformance產生 gateway/upstream model mismatch reasons；
- refusal/incomplete/failed/cancelled/nonterminal/invalid output維持現行 wire outcome。

### 9.3 為何 direct OpenAI 可以用 raw response作 source artifact

OpenAI direct adapter沒有 gateway router；endpoint由 adapter 本身固定為官方 Responses API，actual model由 response
提供。raw response artifact 加上 immutable binding/config/request足以重新驗證 normalized facts。這不是偽造
OpenRouter metadata，也不需要新增 universal provider framework。

---

## 10. Probe 與 downstream fail-closed 修正

### 10.1 為何 probes 必須同一個 commit 改

目前兩個 probe 以：

```python
result.outcome == SUCCEEDED and local_output_validation_passed
```

當成 conformance passed。R4 後 route-contaminated response 會正確回 wire `succeeded`；若 probe 不同步改，就會把
污染結果誤報成 passed。因此 adapter behavior 與對應 probe 必須在同一個 full-green atomic commit。

### 10.2 OpenRouter probe exact gate

`openrouter_live_probe.py` mocked path必須：

1. recorder taxonomy從 `INTERVIEW_VNEXT_EXECUTION_V1` hard cut到現有
   `INTERVIEW_VNEXT_EXECUTION_V2`；不得往v1 taxonomy偷加event；
2. adapter 回 envelope；
3. 保存 supporting artifacts；
4. 建 `model.result` artifact；
5. 建 `model.provider_execution_evidence` artifact；
6. resolve binding policy並 `evaluate_conformance()`；
7. 建 `model.provider_conformance` artifact；
8. `model.call.completed/failed` event 的input exact等於started inputs，output exact tail為
   `(*supporting_refs, result_ref, evidence_ref)`；
9. append `provider.conformance.completed` event，input exact為 `(binding_ref, evidence_ref)`，output exact為
   `(conformance_ref,)`；
10. conformance event status：eligible=`ok`、wire succeeded但ineligible=`failed`、wire非success=`skipped`；
11. 只有 `report.eligible` 才執行 local output validation；
12. run passed 必須同時為 wire succeeded、conformance eligible、local output valid；
13. manifest roots包含 binding/config/projection/result/evidence/conformance與 supporting closure；
14. 用現有 Capture validator重驗。

artifact IDs沿用既有 deterministic labels：

```text
UUIDv5(attempt_id, "provider-execution-evidence")
UUIDv5(attempt_id, "provider-conformance")
```

probe report升為 `openrouter_live_probe_report.v2`，新增：

- binding ID/hash；
- execution evidence hash；
- conformance policy ID/hash；
- conformance report hash、eligible、reason codes；
- transformation status；
- normalized pipeline stage summaries；
- cache status；
- evidence/conformance artifact IDs；
- manifest hash/last event hash。

移除 v1 `route_conformance.pipeline_clean` verdict；historical v1 bundle不重寫。

### 10.3 OpenAI reference probe

`live_probe.py` mocked path使用相同 gate 與 artifact/event closure，report升為 reference probe v2。不得跑 official
live。clean mocked response可 eligible；resolved-model mismatch mocked response必須 wire success但 probe failed，且
local validation不執行。

### 10.4 Scheduler stop-gap

R6 才會把完整 conformance refs/hash加入 trial contract，但 R4 後 executor terminal reason 已是
`provider.conformance_failed`。為避免有人在 R4–R6 間誤跑 mocked harness並把它分類成 model quality，
`scheduler._HARNESS_FAILURE_MARKERS` 必須加入：

```text
provider.conformance_failed
```

既有 `route_contaminated`、`resolved_model_mismatch` markers保留，用來讀歷史 v1 bundles；不得刪除。

---

## 11. 逐檔實作清單

### 11.1 新增

| File | 必須交付 |
|---|---|
| `evals/interview_vnext/providers/openrouter_routing.py` | pure route/pipeline/cache normalizer；無 policy |
| `tests/test_interview_vnext_openrouter_routing.py` | official nested shape、legacy flat、pipeline、cache、unknown/malformed matrix |

### 11.2 修改 OpenRouter

| File | 必須交付 |
|---|---|
| `providers/openrouter_chat.py` | 移除 adapter eligibility；統一 success/error evidence；routing artifact v2；保持 exact HTTP |
| `openrouter_live_probe.py` | persistent evidence/conformance、gate local validation、report v2 |
| `tests/test_interview_vnext_openrouter_eval_adapter.py` | contamination改驗 wire success + evidence + ineligible report |
| `tests/test_interview_vnext_openrouter_live_probe.py` | contamination仍整體 fail，但 result為 succeeded、failure authority為conformance |
| `tests/fixtures/interview_vnext/openrouter_chat/success.json` | 至少一份改為官方 nested endpoints shape |
| `tests/fixtures/interview_vnext/openrouter_chat/manifest.json` | checked date/source/purpose同步 |
| `tests/fixtures/interview_vnext/openrouter_chat/README.md` | 移除「待 live 決定 shape」；說明 official nested + flat historical compatibility |

### 11.3 修改 OpenAI reference

| File | 必須交付 |
|---|---|
| `providers/openai_responses.py` | response model mismatch移到conformance；補actual request/generation/raw source evidence |
| `live_probe.py` | mocked reference conformance artifact/event/report v2；禁止 live |
| `tests/test_interview_vnext_openai_eval_adapter.py` | clean eligible與model mismatch ineligible matrix |
| `tests/test_interview_vnext_openai_live_probe.py` | probe gate與Capture closure regression |

### 11.4 修改 neutral tests／harness guard

| File | 必須交付 |
|---|---|
| `tests/test_interview_vnext_llm_conformance.py` | exact combined reasons、pipeline precedence、direct source artifact cases |
| `evals/interview_vnext/scheduler.py` | `provider.conformance_failed` → harness invalid stop-gap |
| `tests/test_interview_vnext_turn_eval_openrouter.py` | classifier改驗neutral conformance failure；歷史 marker另保留測試 |
| `tests/test_interview_vnext_dependencies.py` | app/eval import boundary仍綠 |

### 11.5 原則上不修改

除非測試證明 R3-C regression，R4 不應修改：

- `app/interview_vnext/application/operation_executor.py`；
- `durable_operations.py`；
- `provider_gate.py`；
- `llm/port.py`、`result.py`、`execution.py`、`conformance.py` 的 active schemas；
- persistence repositories/UoW/migration；
- turn interpreter/verifier/reducer；
- production app composition root；
- Web。

若需要修改上述檔案，實作者必須先在回報中指出哪一條 R3-C invariant 不成立，不得以「測試比較好寫」為由擴張。

---

## 12. Exact test matrix

### 12.1 Pure routing tests

至少覆蓋：

1. official nested `endpoints.available[]` unique selection；
2. nested `selected` + available duplicate只算一筆；
3. legacy flat array仍可讀；
4. selected 0/2/malformed → null facts + limitation；
5. unknown additive metadata不影響已知 facts；
6. metadata missing；
7. metadata requested mismatch使 endpoint無法attest；
8. attempt 0/1/2與 attempts conflict；
9. guardrail inspected；
10. context compression mutated；
11. response healing mutated；
12. server tools mutated；
13. known plugin mutated；
14. unknown plugin/type/stage shape unknown；
15. multiple stages overall priority `unknown > mutated > inspected`；
16. `details_hash` deterministic；
17. cache HIT/MISS/ABSENT/UNKNOWN；
18. zero usage不推導 cache hit；
19. limitations sorted/unique。

### 12.2 Adapter wire tests

現有 outbound body/header測試必須 unchanged。另要求每個 contamination vector驗三件事：

```python
assert envelope.result.outcome is ModelOutcome.SUCCEEDED
assert envelope.result.parsed_output is not None
assert envelope.result.failure is None

report = evaluate_conformance(...)
assert report.eligible is False
assert report.reason_codes == EXPECTED_SORTED_REASONS
```

vectors：

- metadata missing；
- requested model mismatch；
- strategy auto/latest/fallback/pareto/fusion；
- attempt > 1；
- selected provider/model mismatch；
- multiple selected；
- attempts conflict；
- inspected/mutated/unknown pipeline；
- cache HIT/unknown；
- top-level resolved model mismatch。

另驗：

- conformance-only failure沒有 `ModelFailure`/error artifact；
- raw/visible/routing artifacts仍存在；
- reasoning仍 redacted；
- invalid JSON + contaminated route仍是 output parse failure；
- error response metadata仍進 evidence；
- 429/500/timeout transport call count各 1。

### 12.3 OpenAI reference tests

- clean completed response → wire succeeded + strict eligible；
- response model mismatch → wire succeeded + gateway/upstream model mismatch；
- prompt cached token usage不等於 response cache hit；
- response ID/request ID映射到 evidence；
- raw source artifact ref存在且在 envelope supporting artifacts；
- refusal/incomplete/failed/cancelled/nonterminal維持原 outcome；
- invalid JSON/root/tool/cardinality維持 wire failure；
- SDK `max_retries=0`與單次 transport call不變。

### 12.4 Probe／Capture tests

- clean mocked probe：result/evidence/conformance artifacts與events/manifest全閉合；
- contaminated mocked probe：exit 1、wire result仍 succeeded、conformance ineligible；
- contaminated probe不執行 local output validation；
- failure authority/report reason codes為 conformance，不是 `openrouter.route_contaminated`；
- bundle corruption：移除 evidence/conformance或竄改 ref/hash必須驗證失敗；
- no key仍 exit 2、零目錄、零 DB、零 catalog、零 inference；
- secret/reasoning scan仍綠。

### 12.5 Generic durable regression

不需再寫一份 OpenRouter-specific executor。重跑既有 real PostgreSQL tests證明：

- wire succeeded + conformance false → checkpoint failed；
- failure artifact = conformance artifact；
- result/evidence/conformance同 transaction；
- local verifier/reducer不執行；
- fresh-process recovery重驗；
- Capture roots/events closure不退化。

---

## 13. Commit slicing 與綠度規格

每個 commit 都必須 focused tests + 完整 no-network suite 綠；禁止提交已知整套會紅的中間 commit。

### R4-1——Pure OpenRouter routing normalizer

內容：

- 新增 `openrouter_routing.py`；
- 新增 pure routing tests；
- 不接 adapter、不改 runtime behavior。

建議 commit：

```text
feat(evals): normalize OpenRouter execution facts
```

### R4-2——OpenRouter vertical behavior cut

同一 atomic commit包含：

- adapter wire/evidence separation；
- routing artifact v2/fixtures；
- OpenRouter probe conformance gate；
- scheduler stop-gap；
- 所有受影響 tests。

不能把 adapter先改、probe留到下一個紅 commit。

建議 commit：

```text
refactor(evals): separate OpenRouter wire results from conformance
```

### R4-3——OpenAI mocked reference alignment

內容：

- direct reference evidence；
- response model mismatch移到 conformance；
- mocked OpenAI probe gate；
- reference tests。

不得跑 OpenAI live。

建議 commit：

```text
refactor(evals): align OpenAI reference evidence with conformance
```

### R4-4——Status／handoff close

全部 gates 綠後才回寫母計畫、README、AGENTS/status；不得提前宣告 R4 complete。

建議 commit：

```text
docs(interview): close R4 provider conformance separation
```

所有 commit Author/Committer 必須只顯示 owner：

```text
ArIs0x145 <aris0x145@gmail.com>
```

不 push，除非 owner 另行指示。

---

## 14. 驗收命令

以下皆從 `apps/api` 執行。

### 14.1 Pure/provider focused

```powershell
uv run --locked pytest `
  tests/test_interview_vnext_openrouter_routing.py `
  tests/test_interview_vnext_llm_conformance.py `
  tests/test_interview_vnext_openrouter_eval_adapter.py `
  tests/test_interview_vnext_openrouter_live_probe.py `
  tests/test_interview_vnext_openai_eval_adapter.py `
  tests/test_interview_vnext_openai_live_probe.py `
  tests/test_interview_vnext_turn_eval_openrouter.py -q
```

### 14.2 Dependency/schema guard

```powershell
uv run --locked pytest `
  tests/test_interview_vnext_dependencies.py `
  tests/test_interview_vnext_schemas.py `
  tests/test_interview_vnext_execution_schemas.py -q
```

active generated schemas必須 byte-equal；historical schemas不可改寫。預期仍無 migration `0011`。

### 14.3 完整 no-network API suite

```powershell
uv run --locked pytest -q
```

交付回報必須列 exact passed/skipped/failed；不得只寫「all green」。任何新增 fail都擋 commit。

### 14.4 Real PostgreSQL focused

依 runbook 啟動既有 test DB並 migrate到 `0010 head`，再跑：

```powershell
uv run --locked pytest `
  tests/test_interview_vnext_fixed_replay_postgres.py `
  tests/test_interview_vnext_recovery_postgres.py `
  tests/test_interview_vnext_turn_eval_postgres.py `
  tests/test_interview_vnext_turn_eval_runner.py -q
```

要求 `0 skipped`。測試建立的 eval rows依既有 tenant-scoped cleanup清除；不得刪除其他資料。

### 14.5 Hygiene

```powershell
git diff --check
rg -n "evals\.interview_vnext|openrouter_chat|openrouter_routing" app
rg -n "OPENROUTER_API_KEY|OPENAI_API_KEY|Authorization: Bearer|sk-or-|sk-" `
  app evals tests docs
```

檢查重點：

- `app/` 不 import `evals.*`；
- staged files沒有 `.env`、API key、output bundle；
- 沒有 migration `0011`；
- 沒有 production route/Web改動；
- no-network測試沒有讀真 key或打外網。

---

## 15. 明確禁止事項

- 不得在 adapter 呼叫 `evaluate_conformance()`；
- 不得用 `ModelFailure` 表達 route/pipeline/cache eligibility；
- 不得讓 conformance parser直接理解 OpenRouter raw JSON；
- 不得把 binding expected provider/model/endpoint無條件複製到 actual evidence；
- 不得以 token 0、cost 0、低 latency猜 cache hit；
- 不得把 unknown pipeline當 clean；
- 不得讓 `flagged=false` moderation通過 strict attribution；
- 不得丟棄 ineligible wire payload；
- 不得在 conformance eligible前執行 local verifier/reducer；
- 不得新增 adapter retry、SDK retry或 OpenRouter fallback；
- 不得改 outbound schema/body來配合 fixture；
- 不得新增 universal provider framework、agent framework或第二份 executor；
- 不得新增 direct Anthropic、OpenAI live、paid OpenRouter live；
- 不得修改 v1 historical bundle/schema來讓新測試通過；
- 不得宣告模型品質、production readiness或 provider promotion。

---

## 16. R4 Definition of Done

### Architecture

- [ ] adapter只回 wire result + normalized evidence？
- [ ] application policy才決定 eligibility？
- [ ] contaminated wire output被保存但無法進 verifier/reducer？
- [ ] OpenRouter-specific parser沒有進 neutral `app/llm/conformance.py`？
- [ ] direct OpenAI reference可用同一 neutral policy，不需 universal client？

### Evidence

- [ ] official nested endpoints與legacy flat均可讀？
- [ ] unknown additive fields/stages fail closed且不 crash？
- [ ] pipeline stage details hash deterministic？
- [ ] endpoint只有在 exact outbound + response facts共同attest時才填？
- [ ] cache只依官方 header/可證明 facts分類？
- [ ] error response中的 route metadata沒有被丟掉？

### Wire semantics

- [ ] route/model/pipeline/cache mismatch不再產生 active `ModelFailure`？
- [ ] invalid JSON/root/cardinality/tool仍是 wire failure？
- [ ] refusal/incomplete/transport/retry語意不變？
- [ ] outbound exact body與 single-call tests不變？

### Durable／probe

- [ ] probe保存 result/evidence/conformance與完整 events/manifest roots？
- [ ] probe只在 conformance eligible後做 local validation？
- [ ] scheduler把 `provider.conformance_failed`分類為 harness invalid？
- [ ] real PG generic conformance failure/recovery/Capture tests 0 skipped？

### Boundaries

- [ ] migration仍是 `0010 head`？
- [ ] app不import evals？
- [ ] 沒有 API key/output bundle進 git？
- [ ] 沒跑 paid/live、沒接 production/Web？

上述全部成立，才可把 R4標為 complete並讓 R5 Turn Interpreter C1 v2開始。

---

## 17. 實作者交付回報格式

交付時逐項回報，不要只貼 commit SHA：

1. R4-1～R4-4 commit SHA、subject、Author/Committer；
2. 新增／修改檔案清單；
3. neutral schema/version是否有變（預期：沒有）；
4. routing artifact schema version；
5. official nested/legacy flat endpoint decoder證據；
6. pipeline stage classification matrix與unknown例；
7. cache HIT/MISS/ABSENT/UNKNOWN測試證據；
8. contamination如何同時得到 wire succeeded + ineligible report；
9. exact conformance reason codes；
10. invalid output + contamination如何保持 wire failure authority；
11. OpenAI clean/mismatch reference semantics；
12. probe evidence/conformance artifact IDs、event types與manifest roots；
13. 429/500/timeout各自transport call count；
14. focused測試逐檔數量；
15. 完整 no-network exact passed/skipped/failed；
16. real PostgreSQL exact passed/skipped/failed；
17. dependency/schema guard；
18. Alembic head與 migration files；
19. secret/reasoning scan；
20. DB/container/output cleanup狀態；
21. 明確確認未跑 live、未接 production/Web、未新增 direct provider、未 push；
22. 尚未完成項與是否阻擋 R5。

若有任何超出本規格的 neutral contract、executor、DB或provider行為變更，commit前先停下回報，不自行猜測。

---

## 18. R4 完成後的下一步

R4 完成只代表 provider boundary 能正確區分 wire facts 與 attribution eligibility。下一步才是母計畫 R5：

- `turn.interpret/2.0.0` ID-less output；
- application-owned ordinal `proposal_ref` / Evidence ID；
- qualifier support與 false-specificity verifier；
- prompt/operation/schema/verifier identities hard cut。

仍不得直接跳到 paid 12×3 live batch。R5、R6、R7全部通過後，owner 才在 R8 checklist下核准 true-live。

---

## 19. R4 執行結果與逐項回報（2026-07-20 實作完成）

依 §17 格式逐項回報。

1. **Commits**（Author/Committer 均為 `ArIs0x145 <aris0x145@gmail.com>`）：
   - R4-1 `aee798a` — `feat(evals): normalize OpenRouter execution facts`；
   - R4-2 `a814789` — `refactor(evals): separate OpenRouter wire results from conformance`；
   - R4-3 `067504b` — `refactor(evals): align OpenAI reference evidence with conformance`；
   - R4-4 — 本 status close commit（`docs(interview): close R4 provider conformance separation`）。
2. **檔案**：新增 `evals/interview_vnext/providers/openrouter_routing.py`、
   `tests/test_interview_vnext_openrouter_routing.py`；修改 `providers/openrouter_chat.py`、
   `providers/openai_responses.py`、`openrouter_live_probe.py`、`live_probe.py`、`scheduler.py`、
   openrouter_chat fixtures（`success.json`/`manifest.json`/`README.md`）、
   `test_interview_vnext_openrouter_eval_adapter.py`、`test_interview_vnext_openrouter_live_probe.py`、
   `test_interview_vnext_openai_eval_adapter.py`、`test_interview_vnext_openai_live_probe.py`、
   `test_interview_vnext_llm_conformance.py`、`test_interview_vnext_turn_eval_openrouter.py`；
   §11.5 的「原則上不修改」清單（executor/durable/port schemas/persistence/interpreter/production）
   **零改動**。
3. **Neutral schema/version**：無變更（`model_call_result.v2`、`model_call_envelope.v2`、
   `provider_execution_evidence.v1`、`provider_conformance_report.v1`、`attribution-strict/1.0.0`）；
   schema guard `test_interview_vnext_schemas.py` + `test_interview_vnext_execution_schemas.py` 綠。
4. **Routing artifact schema version**：`openrouter_routing.v2`（無 `eligible`/`conformance`/
   `pipeline_clean`；含 `metadata_requested_model`/`selected_count`/`pipeline_stage_summaries`/
   `transformation_status`/`cache_status`/`cache_header_value`/`normalization_limitations`）。
5. **Endpoint decoder**：official nested `endpoints.available[]`（`success.json` 已改用）與 legacy
   flat array（`resolved-model-mismatch.json` 保留）均可讀；nested `selected` 與 available 重複只算
   一筆；均有 pure tests。
6. **Pipeline classification**：guardrail／legacy moderation/content_filter → `inspected`；
   context_compression／response_healing／server_tools／known plugin（web/web-search/file-parser）
   ／rewrite/redaction/message-transform alias → `mutated`；unknown type/name/非 object stage →
   `unknown` + `details_hash=canonical_hash(raw_stage)` opaque 保留；整體 `unknown > mutated >
   inspected`；`pipeline` 非 array → overall unknown + limitation。
7. **Cache**：`X-OpenRouter-Cache-Status` HIT/MISS 直判；header 缺失＋metadata present → `absent`；
   header 缺失＋metadata missing → `unknown`＋limitation；unknown header 值 → `unknown`＋limitation；
   zero-usage/zero-cost 不推導 cache hit（測試明確覆蓋）。
8. **Contamination = wire success + ineligible**：每個向量三段式驗證
   （`outcome is SUCCEEDED`＋`parsed_output is not None`＋`failure is None`，再
   `evaluate_conformance()` 斷言 `eligible=False` 與 exact sorted reasons）；conformance-only failure
   無 `ModelFailure`/error artifact，raw/routing/visible artifacts 保留。
9. **Exact reason codes**（代表向量）：metadata missing →
   `[cache_ineligible, route_metadata_missing, transformation_ineligible]`；requested mismatch／
   multiple selected／attempts conflict → `[route_metadata_missing]`；strategy 非 direct →
   `[route_strategy_mismatch]`；attempt>1 → `[upstream_attempt_mismatch]`；provider mismatch →
   `[route_metadata_missing, upstream_provider_mismatch]`；unbound selected model →
   `[route_metadata_missing, upstream_model_mismatch]`；pipeline 任一 stage →
   `[pipeline_not_empty, transformation_ineligible]`；cache HIT（metadata present）→
   `[cache_ineligible]`；top-level model mismatch → `[gateway_model_mismatch]`。
10. **Invalid output + contamination**：仍是 wire `output_parse_failed`（authority 是 wire failure、
    retryability 不被 conformance 改寫）；evidence 仍保存 actual route facts；conformance 只回
    `wire_not_succeeded`。error response 的 route metadata 亦進 evidence（429＋metadata 測試）。
11. **OpenAI reference**：clean completed → wire succeeded＋同一 neutral evaluator eligible；
    resolved model mismatch → wire succeeded＋`[gateway_model_mismatch, upstream_model_mismatch]`；
    `cached_tokens` 只進 `TokenUsage`（cache_status 仍 `absent`）；`response.id`/`_request_id` 映射
    到 evidence；raw Responses artifact 為 §4.5 direct route source（在 supporting artifacts 且
    evidence 引用）；refusal/incomplete/failed/cancelled/nonterminal/invalid output wire 語意不變；
    `openai==2.46.0` lock、request body、`max_retries=0` 單次 transport call 不變。
12. **Probes**：兩個 probe 均 hard cut 到 `INTERVIEW_VNEXT_EXECUTION_V2`；artifact IDs
    `UUIDv5(attempt_id, "provider-execution-evidence")`/`UUIDv5(attempt_id, "provider-conformance")`；
    `model.call.completed/failed` output tail `(*supporting, result, evidence)`；
    `provider.conformance.completed` input `(binding, evidence)`、output `(conformance,)`、status
    eligible=ok／wire-success-ineligible=failed／wire-fail=skipped；manifest roots 含
    binding/config/projection/result/evidence/conformance closure，Capture validator 重驗綠；
    report 升 `openrouter_live_probe_report.v2`／`live_probe_report.v2`（含 binding/evidence/
    conformance hash、reason codes、transformation/cache、artifact IDs；v1 `route_conformance`
    verdict 移除）；bundle corruption（移除 evidence/conformance root、竄改 conformance event
    inputs）驗證失敗測試通過；no key 仍 exit 2 零副作用。
13. **Transport counts**：429/500/timeout 各 exact 1 次 HTTP call（既有測試維持綠）。
14. **Focused 測試逐檔**：`openrouter_routing` 65、`llm_conformance` 54、`openrouter_eval_adapter` 102、
    `openrouter_live_probe` 11、`openai_eval_adapter` 66、`openai_live_probe` 7、
    `turn_eval_openrouter` 14 passed／2 skipped（skip 為 real-PG orchestration，於 §14.4 gate 以
    TEST_DATABASE_URL 補跑並綠）。
15. **完整 no-network**：`927 passed, 197 skipped, 0 failed`。
16. **Real PostgreSQL**：focused 四檔 `57 passed, 0 skipped`；全部 `test_interview_vnext_*`＋real PG
    `736 passed, 0 skipped, 0 failed`（R3-C baseline 653＋R4 新增）。
17. **Dependency/schema guard**：`test_interview_vnext_dependencies.py`＋schemas＋execution schemas
    `14 passed`；active generated schemas byte-equal、historical schemas 未改寫。
18. **Alembic**：`0010 (head)`；無 migration `0011`。
19. **Secret/reasoning scan**：adapter/probe secret 掃描測試全綠；reasoning redaction 測試維持；
    repo 內無真實 key（僅 README `<secret>` 佔位與測試假 key）。
20. **Cleanup**：real PG 測試走 per-test transaction rollback＋tenant-scoped cleanup；無 output
    bundle、`.env` 或 key 進 git（`git status` 乾淨、hygiene grep 綠）。
21. **明確確認**：未跑任何 paid/live（OpenRouter live、OpenAI live 均未執行）、未接
    production route/Web、未新增 direct Anthropic/universal framework/第二 executor、未 push。
22. **未完成項**：無；§16 Definition of Done 全項成立，不阻擋 R5（Turn Interpreter C1 v2）。

### 19.1 R4-C corrective（2026-07-20 owner review 三個 blocker 的修正）

Owner review 在初次 close 後發現三個 blocker，均以 regression test 先紅後綠修正
（corrective commit，不重寫 R4-1～R4-4）：

1. **`"pipeline": null` 被誤判 clean** — normalizer 原以 `metadata.get("pipeline") is None`
   同視「key 缺失」與「明確 null」。修正：只有 **key 不存在**（官方 no-op 省略語意）或
   `[]` 才是 clean；明確 null 走 malformed 路徑 → overall `unknown`＋limitation →
   `transformation_ineligible` fail closed。
2. **attempt 與 attempts 筆數矛盾仍 eligible** — `attempt=1` 但 `attempts` 兩筆（同
   provider）原本通過。修正：§6.4 條件 8 補上筆數一致性——`attempt` 與非空 `attempts`
   筆數不一致時，attempt fact 視為無法證立（null＋
   `openrouter attempt count contradicts the recorded attempts` limitation）→
   evidence `upstream_attempt_count=None` → `route_metadata_missing` ineligible。
   一致的 fallback metadata（attempt=2＋兩筆）仍照實記 2 → `upstream_attempt_mismatch`。
3. **blank-only 字串讓 typed evidence 拋 ValidationError 外洩** — `"strategy": " "` 等
   blank 值通過 truthiness 檢查後，在 `define_provider_execution_evidence()`
   （`NonEmptyText`）拋例外，adapter 未回受控 envelope。影響面比回報更廣：
   `ModelCallResult.resolved_model` 也是 `NonEmptyText`，blank body `model` 會炸
   result 建構，OpenAI reference 同類。修正：normalizer `_fact_text()` 把 blank-only
   的 requested/strategy/selected provider/model null 化（非 blank 值原樣保留、不
   strip 改寫）；OpenRouter blank body model → 受控 `openrouter.protocol_invalid`
   wire failure（含 except-handler 兩處 fallback）；OpenAI blank `response.model` →
   result 回退 requested、evidence null＋limitation → `route_metadata_missing`
   ineligible。

Regression tests：pure normalizer ＋ adapter ＋ OpenAI 共 14 個新測試（先紅證實
blocker、修正後綠）。corrective 後 gates：focused 七檔 **333 passed／2 skipped**
（skip＝real-PG orchestration，PG gate 補跑綠）；完整 no-network
**941 passed／197 skipped／0 failed**；interview_vnext＋real PostgreSQL
**750 passed／0 skipped**；dependency/schema guard **14 passed**；Alembic
**`0010 (head)`**。R4 complete 狀態在此 corrective 之後重新確認。

### 19.2 R4-C2 corrective（2026-07-20 follow-up review：usage/cost 數值同類 P1）

Follow-up review 發現與 blocker 3 同類的數值版外洩——usage/cost mapping 未驗證的
異常數值會讓 typed contracts 拋 `ValidationError` 而非回受控 envelope
（OpenRouter `cost=1e-7`／`cost="not-a-decimal"`／`prompt_tokens=-1`、OpenAI
`input_tokens=-1` 均實測重現）。修正（regression tests 先紅後綠）：

1. **`_decimal_str` canonical 化**：合法科學記號 cost（`1e-7`）以
   `Decimal(repr(float))` → `format(value, "f")` 正規化為 `0.0000001`（無 float
   重算）；非數字／負數／非有限（NaN/Infinity）／bool → `None`＋
   `openrouter response cost was not a usable decimal` limitation（與「缺 cost」
   的 limitation 區分）；evidence 與 routing artifact v2 共用同一 canonical 值。
2. **OpenRouter `_map_usage`**：負數 token → `None`＋
   `openrouter usage {field} was negative` limitation（`TokenUsage` 是 ge=0
   typed contract）。
3. **OpenAI `_map_usage`**：負數／非整數／bool token → `None`＋
   `openai usage {field} was not a usable count` limitation。

usage/cost 不是 attribution 判準：null 化後 conformance 仍照 route facts 判
（clean route 仍 eligible），wire outcome 不變。新增 10 個 regression tests
（OpenRouter 9＋OpenAI 1）。R4-C2 後 gates：focused 七檔 **343 passed／2 skipped**；
完整 no-network **951 passed／197 skipped／0 failed**；interview_vnext＋real
PostgreSQL **760 passed／0 skipped**；dependency/schema guard **14 passed**；
Alembic **`0010 (head)`**。
