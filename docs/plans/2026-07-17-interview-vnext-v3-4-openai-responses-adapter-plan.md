# Interview AI vNext V3-4——OpenAI Responses eval-only adapter 實作交接規格

- 日期：2026-07-17
- 狀態：**研究與實作規格定稿；尚未實作**
- 適用切片：V3-4 only
- 上游架構：[`../specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md`](../specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md)
- 總實作計畫：[`2026-07-17-interview-vnext-v3-fixed-replay-plan.md`](2026-07-17-interview-vnext-v3-fixed-replay-plan.md)
- 現有中立合約：`app.interview_vnext.llm.port.LlmPort`、`ModelCallRequest`、`ModelCallEnvelope`、`ModelCallResult`
- 裁決權：本文件優先於總計畫 §7 的摘要。若實作時需要改 request/result schema、retry ownership、artifact 語意或 production import boundary，必須先修訂本文件，不可自行猜測。

---

## 1. 交接結論

V3-4 要做的不是「把 OpenAI SDK 接上就好」，而是建立一個**只供 vNext 實驗使用、可稽核、無隱藏重試、無 provider 記憶、輸出語意完整正規化**的 Responses adapter。完成後應能回答：目前 OpenAI Responses 真實 API shape 是否能無損映射到 V2/V3 已發布的 provider-neutral contract。

實作者必須遵守下列結論：

1. 直接使用官方 `openai==2.46.0` 的 `AsyncOpenAI.responses.create()`，不經 LangChain、OpenRouter、Agents SDK、Chat Completions 或 Assistants。
2. adapter 只存在 `apps/api/evals/interview_vnext/`；`apps/api/app/`、production composition root、route 與 Web 都不得 import。
3. 使用 Responses strict Structured Outputs 的 `text.format`，但送出的 schema 必須是 V3-2 已發布、已 hash 的 portable schema；不可在 adapter 內另從 `TurnInterpretOutput` 重生另一份 schema。
4. 因此**不用** `responses.parse(text_format=TurnInterpretOutput)`。官方 helper 適合 Pydantic model 就是 provider schema authority 的情境；Caliburn 的 authority 是 persisted `output_schema_artifact` 的 portable schema/hash，兩者不能混用。
5. OpenAI client 必須 `max_retries=0`。SDK 2.46.0 預設是 2 次 retry，若保留，單一 durable attempt 可能產生三次 HTTP call，破壞 V3-3 的 attempt/Capture 語意。
6. application 的 `request.deadline_at` 是總 wall-clock deadline；adapter 同時用 `asyncio.timeout()` 與 per-request HTTP timeout，不能改用 SDK 預設 10 分鐘。
7. `store=false`、`background=false`、`stream=false`、`truncation=disabled`；不送 conversation、`previous_response_id`、tools、reasoning round-trip、compaction 或 prompt cache control。
8. 遍歷所有 typed `response.output` items；只允許 reasoning item 加上唯一一個完整 message/output_text。禁止 `response.output[0]` 假設，也禁止用會串接多段內容的 `response.output_text` convenience property。
9. `completed`、`incomplete`、`failed`、`cancelled` 與 refusal 必須分流。incomplete/refusal/error 不可送入 JSON repair parser。
10. provider strict schema只保證輸出形狀，不保證員工事實正確。adapter 成功只建立 `StructuredPayload`；完整 `TurnInterpretOutput` Pydantic 驗證與 deterministic verifier 仍由既有 executor 負責。
11. HTTP request ID 寫入 `ModelCallResult.provider_request_id`；OpenAI response resource ID 保留在 raw provider artifact。`provider_conversation_id` 固定為 `None`。
12. V3-4 不新增 migration、不改已發布 neutral schema、不做品質 gate。V3-5 才建立 12 個 turn tasks、多 trial 與 semantic report。

---

## 2. 官方資料核對與直接影響

以下資料皆為 OpenAI 官方文件、官方 OpenAPI 或官方 SDK；核對日期為 2026-07-17。

| 官方來源 | 已核對事實 | 本切片裁決 |
|---|---|---|
| [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | Responses 的 structured response 使用 `text.format`；refusal 是獨立 content item；schema adherence 不代表內容正確；無關輸入仍可能產生符合 schema 的幻覺內容 | 用 strict JSON Schema；遍歷 message content；保留本地 schema/domain verifier；prompt允許 empty/unknown |
| [Migrate to Responses：Structured Outputs](https://developers.openai.com/api/docs/guides/migrate-to-responses#6-update-structured-outputs-definitions) | raw request shape 是 `text.format={type,json_schema name,strict,schema}`；Python `parse` helper 則接受 Pydantic `text_format` | 本案需送出既有 portable schema，使用 `responses.create(text=...)`，不用 `parse` 重生 schema |
| [Create a model response](https://developers.openai.com/api/reference/resources/responses/methods/create) | `store`、`background`、`previous_response_id`、`reasoning`、`service_tier`、`truncation`、`max_output_tokens` 等為 provider transport/profile controls；`max_output_tokens`同時涵蓋可見與 reasoning tokens；`truncation=disabled`超 context 時以 400 失敗 | provider controls 留在 eval config/adapter；禁止 provider state；不讓 API 靜默丟掉最前面的 context |
| [Responses OpenAPI](https://api.openai.com/v1/responses) | Response 有 `status`、`error`、`incomplete_details`、resolved `model`、多型 `output[]` 與 usage；output 可同時有 reasoning與message等不同 item | typed traversal與完整 raw artifact是必要條件，不可只讀第一個 item |
| [Reasoning guide](https://developers.openai.com/api/docs/guides/reasoning#allocating-space-for-reasoning) | 達到 `max_output_tokens` 時 response 可為 incomplete，且可能沒有任何可見文字；已使用的 reasoning token仍計費 | incomplete 即使可見 items 為空也必須有 typed result、空 visible artifact與 usage，不能當 parser bug |
| [Latest model guide](https://developers.openai.com/api/docs/guides/latest-model) | 目前 quality-first 通用起點是 `gpt-5.6`；alias 指向 `gpt-5.6-sol`；官方建議先以代表性 eval 比較 effort，不假設最高 effort 最佳 | V3-4 smoke 預設 `gpt-5.6`、`standard`、`medium`；這是可版本化 eval config，不進 domain/operation hash |
| [Error codes](https://developers.openai.com/api/docs/guides/error-codes) | 官方 Python SDK區分 timeout、connection、auth、permission、bad request、conflict、rate limit、unprocessable與server errors | 建立封閉、可測的 exception → `FailureKind/retryable` 表，不以 message substring猜整體類別 |
| [openai-python 2.46.0 retries/timeouts/request IDs](https://github.com/openai/openai-python/tree/v2.46.0#retries) | SDK預設會 retry特定錯誤兩次；可用 `max_retries=0`停用；成功 response與 status error可取得 request ID | 關閉SDK retry；HTTP request ID進neutral result/error artifact；timeout由durable request控制 |
| [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | task-specific、持續 eval、完整紀錄、code-first grader與人工校準 | V3-4只做adapter conformance；V3-5才做模型品質，兩者不得混為「架構有效」 |

### 2.1 專案鎖定版本的實際 SDK surface

已在專案 `.venv` 以只讀 introspection 核對 `openai==2.46.0`：

- `AsyncOpenAI(..., max_retries=2)` 是建構預設值；
- `responses.create()` 接受 `background`、`input`、`instructions`、`max_output_tokens`、`model`、`reasoning`、`service_tier`、`store`、`stream`、`text`、`tools`、`truncation`、per-request `timeout`；
- `Response.status` 目前型別為 `completed | failed | in_progress | cancelled | queued | incomplete | None`；
- `IncompleteDetails.reason` 目前是 `max_output_tokens | content_filter | None`；
- message content 是 `ResponseOutputText | ResponseOutputRefusal`；
- usage 有 `input_tokens_details.cached_tokens`、`input_tokens_details.cache_write_tokens` 與 `output_tokens_details.reasoning_tokens`。

另以`httpx.MockTransport`做過不連網serialization probe：本文件§7.3的`reasoning={mode,effort}`、`text.format={type,name,schema,strict}`、`service_tier`、`store/background/stream`與`truncation`會被SDK 2.46.0原樣序列化到`POST /v1/responses`；pseudo-code不是依記憶猜參數。

這些 SDK 型別只能存在 eval adapter/tests。不得將 `openai.types.*` 放進 `app.interview_vnext.llm`、domain、application、persistence、artifact schema或公開函式簽名。

### 2.2 未找到 Responses create 的官方 idempotency 承諾

目前 Responses create reference與 SDK typed parameters沒有公開、專用的 idempotency parameter。本切片不得自行透過 `extra_headers`送一個未在此 endpoint文件化的 `Idempotency-Key`，也不得宣稱 provider exactly-once。

`ModelCallRequest.idempotency_key`仍是 Caliburn workflow identity與Capture metadata；真正防止重複 domain mutation的是 V3-3 durable attempt claim、checkpoint與 reducer command idempotency。provider call在 crash邊界仍可能出現「遠端已執行、本地未收到response」的不確定性，這是既有架構已明列的限制。

---

## 3. Scope 與明確不做

### 3.1 V3-4 交付物

1. OpenAI Responses eval adapter與config；
2. exact published schema catalog/hash gate；
3. mocked HTTP provider-shape fixture matrix；
4. opt-in單次live conformance probe；
5. probe 的 immutable Capture bundle；
6. README、來源、限制與驗收命令。

### 3.2 V3-4 不做

- production provider adapter或DI wiring；
- FastAPI route、Web、現行 `app/interview/` v3整合；
- Anthropic adapter、model routing、fallback或bake-off；
- 12/20 case模型品質評測；
- episode coding、JD投影或下一題生成；
- streaming、background polling、conversation state、server compaction；
- tools、Agents SDK、MCP、web/file search；
- prompt caching調優；
- output text修補、markdown fence剝除、regex JSON擷取；
- migration或修改 `model_call_request.v1`／`model_call_result.v1`。

Live probe成功只代表「目前官方 API shape能正確映射」，不代表工作分析品質通過，也不代表可上 production。

---

## 4. 目錄與逐檔責任

實作後應有以下最小結構：

```text
apps/api/evals/interview_vnext/
  __init__.py
  README.md
  provider_config.py
  schema_catalog.py
  live_probe.py
  probes/
    turn-interpret-smoke.v1.json
  providers/
    __init__.py
    openai_responses.py

apps/api/tests/
  test_interview_vnext_openai_eval_adapter.py
  test_interview_vnext_openai_live_probe.py
  fixtures/interview_vnext/openai_responses/
    README.md
    manifest.json
    success_reasoning_then_message.json
    refusal.json
    incomplete_max_output_no_visible.json
    incomplete_content_filter_partial.json
    failed_server_error.json
    completed_no_message.json
    completed_multiple_output_text.json
    completed_commentary_then_final.json
    completed_invalid_json.json
    unexpected_tool_call.json
    resolved_model_mismatch.json
    usage_unavailable.json
    invalid_schema_400.json
    authentication_401.json
    rate_limit_429.json
    quota_429.json
    server_500.json
```

逐檔責任：

| 檔案 | 只負責 | 不可負責 |
|---|---|---|
| `provider_config.py` | secret-free eval profile、model allowlist、reasoning/service tier/connect timeout驗證與canonical config hash | API key、prompt/schema/domain規則 |
| `schema_catalog.py` | `output_schema_id + hash`到exact published schema與OpenAI format name的封閉映射 | 從任意path/network載入schema、修改schema |
| `providers/openai_responses.py` | request projection、SDK call、response/error normalization、supporting artifacts | DB/UoW、domain reducer、semantic verifier、CLI |
| `live_probe.py` | env preflight、建立一個synthetic request、呼叫adapter、建立Capture bundle、exit code | 多case runner、品質grader、production wiring |
| `probes/*.json` | 明確標示test-only的最小synthetic input與期望contract | gold答案、真員工內容、API key |
| adapter tests | mocked HTTP、SDK deserialization、mapping與network-call count | live API |
| live probe tests | no-key fail-fast、bundle hash/manifest、mocked smoke | 以skip冒充live成功 |

不要建立通用「provider framework」、abstract base class或plugin registry。現在只有一個eval adapter；待Anthropic實作後出現真實共同點再抽象化。

---

## 5. Config contract

### 5.1 建議型別

`OpenAIResponsesEvalConfig`是secret-free immutable Pydantic model，至少包含：

```text
schema_version = "openai_responses_eval_config.v1"
provider = "openai"
requested_model = "gpt-5.6"
accepted_resolved_models = ("gpt-5.6", "gpt-5.6-sol")
reasoning_mode = "standard"
reasoning_effort = "medium"
service_tier = "default"
connect_timeout_seconds = 10.0
store = false
background = false
stream = false
truncation = "disabled"
sdk_max_retries = 0
contains_test_data = true
```

固定值也要進config dump/hash，讓報告能證明實際使用的hard invariants；但對外constructor不可允許把它們改成其他值。可實作為 `Literal`/validator，而不是自由bool。

規則：

- `accepted_resolved_models`非空、去重、排序；
- `requested_model`不必出現在allowlist，因alias可解析為另一model；
- current default allowlist同時接受`gpt-5.6`與官方說明的`gpt-5.6-sol`；其他model必須由CLI顯式提供相應allowlist，不能自動接受任意`gpt-5.6-*`；
- reasoning effort型別按SDK 2.46.0可接受值，但V3-4 default只測`medium`；
- `reasoning_mode` V3-4只允許`standard`，不把`pro`混入第一個基準；
- `service_tier`固定`default`，避免project設定讓run在`auto`下漂移；
- API key、organization/project secret與完整environment永不進config model/artifact/hash；
- config hash使用既有`canonical_hash(config)`，live bundle保存config artifact。

### 5.2 Model drift規則

requested model與resolved model都必須保存。allowlist是eval reproducibility gate，不是domain規則：

- response.model在allowlist：繼續status/content normalization；
- response.model不在allowlist：`FAILED + RESOLVED_MODEL_MISMATCH`、`retryable=false`；
- mismatch結果仍保存raw與visible artifacts；
- 不用prefix、regex或「看起來同family」自動放行；
- 官方alias改向時，先更新config/report並review，再重新跑probe，不改operation definition。

---

## 6. Schema authority：不得讓 persisted hash 與實際 request 漂移

### 6.1 現有缺口

`ModelCallRequest`只有：

```text
output_schema_id
output_schema_artifact: ArtifactRef
output_schema_hash  # property，實際取 artifact content_hash
```

它沒有schema JSON本體，也沒有tenant ID可讓provider adapter直接讀DB。若實作者直接呼叫 `TurnInterpretOutput.model_json_schema()`，會得到包含本地constraints的完整schema，不是V3-2送provider的portable schema，造成：

- provider實際request無法由artifact重建；
- `output_schema_hash`不再描述實際constrained decoding grammar；
- future Anthropic/OpenAI比較不再使用同一schema；
- local schema repair與Capture分析會誤判。

### 6.2 V3-4裁決：封閉的 content-addressed schema catalog

新增 `PublishedOutputSchemaCatalog`，只支援已知schema：

```text
schema_id:
  https://caliburn.local/schemas/turn-interpret-output.v1.schema.json
filename:
  turn-interpret-output.v1.schema.json
openai_format_name:
  turn_interpret_output_v1
operation:
  turn.interpret + current turn_interpret_operation().definition_hash
factory:
  app.interview_vnext.llm.schema_exports.published_schema
```

`resolve(request)`必須依序：

1. 以exact `request.output_schema_id`查封閉mapping；未知ID立刻local failure，不打API；
2. 呼叫 `published_schema(filename)`取得fresh dict；
3. 驗證root `$id == request.output_schema_id`；
4. 驗證`canonical_hash(schema) == request.output_schema_hash`；
5. 呼叫 `assert_portable_strict_output_schema(schema)`；
6. 驗證root `type=object`；
7. 以`turn_interpret_operation()`驗證request的operation name、definition hash與output contract hash都屬於同一份current operation；
8. 回傳deep copy、固定OpenAI format name與hash。

注意：目前 artifact byte hash與 `canonical_hash(schema)`使用相同canonical JSON bytes，因此可做content-addressed equivalence。catalog不是用schema ID盲目信任current code；hash不合就拒絕。

### 6.3 為何不用 `responses.parse`

官方Structured Outputs指南建議在一般應用使用Pydantic/Zod helper，避免model與schema漂移。Caliburn已經以另一種方式避免漂移：Pydantic source經 `portable_strict_output_schema()`投影、committed schema golden test、artifact hash與本地完整Pydantic validation。

若改用：

```python
client.responses.parse(text_format=TurnInterpretOutput, ...)
```

SDK會從完整Pydantic model生成provider schema，繞過portable artifact。因此V3-4必須使用：

```python
client.responses.create(
    text={
        "format": {
            "type": "json_schema",
            "name": binding.openai_format_name,
            "strict": True,
            "schema": binding.schema,
        }
    },
    ...,
)
```

此裁決不是否定官方helper，而是確保本專案實際送出的grammar與Capture宣稱的hash相同。

### 6.4 禁止provider-specific臨時改schema

不得在adapter內：

- 刪`$id`、`title`或`$defs`；
- inline `$ref`；
- 改required順序；
- 加/刪description；
- 放寬`additionalProperties`；
- 遇400就retry一份不同schema。

若live API拒絕exact schema，V3-4應失敗並保存400 error artifact。接著回V3-2更新portable projection、發布新contract/version/hash與兩家provider研究；不能讓adapter送出未被artifact描述的shadow schema。

---

## 7. Exact request mapping

### 7.1 前置驗證

`generate_structured(request)`在任何network I/O前必須驗證：

1. `request.provider == "openai"`；
2. `request.requested_model == config.requested_model`；
3. schema catalog解析與hash/lint全部通過；
4. `request.deadline_at > clock.now()`；
5. messages仍符合中立contract的user開始、交替、user結尾；雖Pydantic已驗，adapter boundary再以assert/failure防錯誤mock；
6. operation沒有tools；`ModelCallRequest`不含allowed_tools，所以V3-4以catalog中已知的current `turn.interpret` operation name/definition hash/output contract hash與schema binding封閉，不做任意operation adapter。

本地config/schema/request mismatch不應丟出未分類exception給executor。回傳 `FAILED + INVALID_REQUEST` 或 `RESOLVED_MODEL_MISMATCH` 的typed envelope；只有程式取消 `asyncio.CancelledError`必須向外重拋。

### 7.2 Message projection

top-level instructions與對話items分開：

```python
instructions=request.instructions
input=[
    {"role": message.role.value, "content": message.text}
    for message in request.messages
]
```

不要把instructions複製成system message；不要把artifact IDs、timestamp、hash、validation error以外的Capture metadata塞進prompt。schema repair attempt若已有machine-readable validation errors，它已由V3-3放進request messages，adapter只忠實投影。

### 7.3 唯一允許的 Responses call shape

語意等價的pseudo-code如下；實際型別要通過SDK 2.46.0與mypy/pytest：

```python
response = await client.responses.create(
    model=request.requested_model,
    instructions=request.instructions,
    input=[
        {"role": item.role.value, "content": item.text}
        for item in request.messages
    ],
    max_output_tokens=request.max_output_tokens,
    reasoning={
        "mode": config.reasoning_mode,
        "effort": config.reasoning_effort,
    },
    text={
        "format": {
            "type": "json_schema",
            "name": binding.openai_format_name,
            "strict": True,
            "schema": binding.schema,
        }
    },
    service_tier="default",
    store=False,
    background=False,
    stream=False,
    truncation="disabled",
    timeout=http_timeout_for_remaining_deadline,
)
```

必須omit，不是送`None`或由env/profile默認：

- `conversation`、`previous_response_id`；
- `tools`、`tool_choice`、`parallel_tool_calls`；
- `context_management`、`include`、reasoning encrypted content；
- `prompt` hosted template；
- `prompt_cache_key/options/retention`；
- `temperature`、`top_p`、`verbosity`；
- `metadata`；
- `moderation`；
- `safety_identifier`（V3-4只有synthetic eval，沒有authenticated end-user principal；production前另補）；
- `extra_headers`中的自製idempotency header。

`tools`省略即沒有可呼叫工具；不需要同時送空list與`tool_choice=none`。若mocked response仍出現tool call，視為provider protocol/output failure，不執行工具。

### 7.4 Client建構

adapter自己建立client，不接受外部任意 `AsyncOpenAI` instance，避免caller偷偷帶入retry/base URL設定：

```text
AsyncOpenAI(
  api_key=<constructor secret>,
  base_url="https://api.openai.com/v1",
  max_retries=0,
  timeout=<explicit default; each call仍覆寫remaining deadline>,
  http_client=<optional injected AsyncClient for mocked tests>,
)
```

- live API key從`OPENAI_API_KEY`讀取後以constructor參數傳入；不寫log/artifact/repr；
- base URL固定官方endpoint。V3-4不是OpenAI-compatible provider測試；
- 若注入`http_client`，ownership要明確：由adapter建立就由`aclose()`關閉，外部注入就不關；
- adapter提供async context manager或明確`aclose()`，live CLI一定在`finally`關閉；
- mocked tests使用`httpx.MockTransport`或respx攔截官方URL，仍經過官方SDK deserialization，不直接new SDK response objects。

---

## 8. Deadline、timeout、retry與取消

### 8.1 一個durable attempt只能有一個HTTP call

下列三層責任不可混淆：

```text
V3-3 executor: 是否建立下一個 durable attempt
V3-4 adapter: 一個 attempt 做一次 Responses HTTP call
OpenAI SDK: transport與deserialization；retry被關閉
```

每個429/500/timeout mocked test都要斷言transport invocation count恰為1。下一次呼叫只能由executor依`ModelFailure.retryable`建立新的attempt ID、request artifact與idempotency suffix。

### 8.2 Wall-clock deadline

adapter開始時：

```text
started_at = utc_clock.now()
remaining_seconds = (request.deadline_at - started_at).total_seconds()
```

- `remaining_seconds <= 0`：不打API，回typed timeout；
- connect timeout = `min(config.connect_timeout_seconds, remaining_seconds)`；
- read/write/pool timeout不得大於remaining；
- 整個await另包 `asyncio.timeout(remaining_seconds)`，因HTTP各階段timeout不等於總wall-clock deadline；
- latency使用monotonic clock計算，不以provider timestamp或UTC相減；
- completed_at用UTC clock；若test fake clock未前進，仍不得早於started_at；
- `asyncio.TimeoutError`與SDK `APITimeoutError`都正規化為`TRANSPORT_TIMEOUT`；
- 外部task cancellation的`asyncio.CancelledError`重拋，不偽裝provider失敗。V3-3會讓未取得durable result的CALLING attempt按deadline recovery。

### 8.3 Timeout結果

```text
outcome = failed
finish_reason = provider_error
failure.kind = transport_timeout
failure.reason_code = openai.timeout
failure.retryable = true
resolved_model = requested_model  # 尚無provider response
usage = all null + sorted limitation
supporting artifacts = normalized error artifact
```

不要建立假的usage=0，也不要宣稱遠端一定沒有執行。

---

## 9. Response traversal演算法

### 9.1 先保存raw，再判斷語意

只要SDK成功回傳`Response`物件，先建立raw與visible artifacts，再做model/status/content分類。如此即使normalization失敗，原始shape仍可稽核。

不要依賴：

```python
response.output[0]
response.output_text
```

`output_text` convenience property可能串接多個message片段，會掩蓋「本應恰好一個structured payload」的不變量。

### 9.2 Typed traversal

遍歷順序必須保留provider array order：

```text
for output_index, output_item in enumerate(response.output):
  if ResponseReasoningItem:
    記錄其存在於raw；不保存/回送hidden reasoning；繼續
  elif ResponseOutputMessage:
    驗證message status與phase（只接受None或final_answer；commentary視為unexpected）
    for content_index, content in enumerate(output_item.content):
      ResponseOutputText -> visible item(type=output_text,text=...)
      ResponseOutputRefusal -> visible item(type=refusal,text=...)
      其他 -> protocol failure
  else:
    unexpected output item（tool/program/MCP/...）
```

reasoning item可以位於message前後；不能因它不是message就失敗。所有非reasoning、非message output item在V3-4都不允許，因request沒有tools。

SDK 2.46.0的message另有optional `phase=commentary | final_answer`。Structured output authority只能來自`phase=None`（provider未標示）或`phase=final_answer`；任何visible commentary都不能與final JSON拼接，也不能單獨當structured payload。

### 9.3 狀態優先序

正規化順序固定：

1. resolved model allowlist；
2. top-level `response.status`；
3. completed response的message/content cardinality；
4. JSON parse；
5. 建立canonical `StructuredPayload`。

`failed`/`cancelled`/`incomplete`不能因恰好帶了一段看似JSON的partial text就升格success。只有top-level `completed`才進refusal/output parse。

### 9.4 Completed response的cardinality

對`status=completed`：

| 可見內容 | 結果 |
|---|---|
| refusal >=1，output_text=0，無unexpected item | `REFUSED/SAFETY_REFUSAL`；safe message用固定本地文字，provider refusal原文只在visible artifact |
| refusal >=1且output_text >=1 | `FAILED/OUTPUT_PARSE_FAILED`，reason=`openai.ambiguous_refusal_and_output` |
| refusal=0且output_text恰好1，無unexpected item | 進strict JSON parse |
| output_text=0 | `FAILED/OUTPUT_PARSE_FAILED`，reason=`openai.missing_structured_output` |
| output_text>1 | `FAILED/OUTPUT_PARSE_FAILED`，reason=`openai.multiple_structured_outputs` |
| 任一unexpected item | `FAILED/OUTPUT_PARSE_FAILED`，reason=`openai.unexpected_output_item` |

message本身若在top-level completed時仍標`in_progress`或`incomplete`，視為provider protocol failure，不能拼partial output。

### 9.5 JSON parse

唯一output text直接 `json.loads(text)`：

- 禁止trim markdown fence再試；
- 禁止搜尋第一個`{...}`；
- 禁止JSON5、trailing comma、repair model或第二次隱藏call；
- parse失敗 → `OUTPUT_PARSE_FAILED`；
- root不是JSON object → `OUTPUT_SCHEMA_INVALID`；
- parse成功 → `build_structured_payload(schema_id=request.output_schema_id, value=value)`；
- adapter此時回`SUCCEEDED`，既有executor接著以完整`TurnInterpretOutput.model_validate()`驗證local-only constraints；失敗時由V3-3明確schema repair attempt處理。

不得在adapter直接執行semantic quote/span/domain verifier。provider adapter只負責provider syntax/outcome boundary。

---

## 10. Top-level status mapping

| OpenAI response | Neutral outcome | finish reason | failure/refusal | retryable |
|---|---|---|---|---:|
| `completed` + 唯一valid JSON | `SUCCEEDED` | `COMPLETED` | parsed payload | n/a |
| `completed` + only refusal | `REFUSED` | `SAFETY_REFUSAL` | `reason_code=openai.refusal` | n/a |
| `incomplete`, reason=`max_output_tokens` | `INCOMPLETE` | `MAX_OUTPUT_TOKENS` | 無failure、無parsed | n/a |
| `incomplete`, reason=`content_filter` | `INCOMPLETE` | `UNKNOWN` | 無failure、無parsed；provider_finish_reason保留完整值 | n/a |
| `incomplete`, reason缺失/未知 | `INCOMPLETE` | `UNKNOWN` | 無failure、無parsed | n/a |
| `failed`, error=`server_error` | `FAILED` | `PROVIDER_ERROR` | `PROVIDER_UNAVAILABLE` | true |
| `failed`, error=`rate_limit_exceeded` | `FAILED` | `PROVIDER_ERROR` | `RATE_LIMITED` | true |
| `failed`,其他known request/content error | `FAILED` | `PROVIDER_ERROR` | `INVALID_REQUEST` | false |
| `failed`,無error/unknown error | `FAILED` | `PROVIDER_ERROR` | `UNKNOWN_PROVIDER_FAILURE` | false |
| `cancelled` | `FAILED` | `CANCELLED` | `CANCELLED` | false |
| `queued`/`in_progress`/`None`（background=false同步call） | `FAILED` | `UNKNOWN` | `UNKNOWN_PROVIDER_FAILURE`, reason=`openai.unexpected_nonterminal_status` | false |

`provider_finish_reason`不要偽造Chat Completions的`stop`。固定保存可逆字串：

```text
completed
incomplete:max_output_tokens
incomplete:content_filter
incomplete:unknown
failed:<provider_error_code-or-unknown>
cancelled
unexpected:<status-or-none>
```

Incomplete visible content可能是空集合。仍建立visible artifact `{items: []}`，因`ModelCallResult` contract要求incomplete有visible partial response artifact；空集合精確表示「provider沒有可見partial」，不是缺artifact。

Refusal物件固定為：

```text
reason_code = openai.refusal
safe_message = The model declined this request.
provider_category = refusal
```

provider refusal原文可能含不受信任內容，只進visible artifact，不直接成為safe message。

---

## 11. HTTP/SDK exception mapping

先讀官方exception type與structured error code；只有最後fallback才看status code。禁止用自然語言message判斷「可能retry」。

| SDK/HTTP | FailureKind | reason_code | retryable | finish reason |
|---|---|---|---:|---|
| `APITimeoutError`、adapter wall timeout、HTTP 408 | `TRANSPORT_TIMEOUT` | `openai.timeout` | true | `PROVIDER_ERROR` |
| `APIConnectionError` | `TRANSPORT_ERROR` | `openai.connection_error` | true | `PROVIDER_ERROR` |
| `AuthenticationError` 401 | `AUTHENTICATION_FAILED` | `openai.authentication_failed` | false | `PROVIDER_ERROR` |
| `PermissionDeniedError` 403 | `AUTHENTICATION_FAILED` | `openai.permission_denied` | false | `PROVIDER_ERROR` |
| `BadRequestError` 400且code=`context_length_exceeded` | `INVALID_REQUEST` | `openai.context_window_exceeded` | false | `CONTEXT_WINDOW_EXCEEDED` |
| 400其他、404、422 | `INVALID_REQUEST` | `openai.invalid_request`等穩定code | false | `PROVIDER_ERROR` |
| `ConflictError` 409 | `PROVIDER_UNAVAILABLE` | `openai.conflict` | true | `PROVIDER_ERROR` |
| `RateLimitError` 429且code=`insufficient_quota` | `RATE_LIMITED` | `openai.quota_exhausted` | false | `PROVIDER_ERROR` |
| 429其他 | `RATE_LIMITED` | `openai.rate_limited` | true | `PROVIDER_ERROR` |
| `InternalServerError`或status >=500 | `PROVIDER_UNAVAILABLE` | `openai.server_error` | true | `PROVIDER_ERROR` |
| 其他`APIStatusError` | `UNKNOWN_PROVIDER_FAILURE` | `openai.api_status_error` | false | `PROVIDER_ERROR` |
| 其他unexpected exception | `UNKNOWN_PROVIDER_FAILURE` | `openai.adapter_unexpected_error` | false | `PROVIDER_ERROR` |

上表的`等穩定code`不得由實作者自由命名；完整reason registry固定如下：

| 情境 | reason_code |
|---|---|
| attempt deadline/SDK timeout/HTTP 408 | `openai.timeout` |
| connection error | `openai.connection_error` |
| 401 | `openai.authentication_failed` |
| 403 | `openai.permission_denied` |
| context length 400 | `openai.context_window_exceeded` |
| 400其他 | `openai.invalid_request` |
| 404 | `openai.not_found` |
| 409 | `openai.conflict` |
| 422 | `openai.unprocessable_entity` |
| retryable 429 | `openai.rate_limited` |
| quota 429 | `openai.quota_exhausted` |
| HTTP 5xx | `openai.server_error` |
| top-level failed/server_error | `openai.response_server_error` |
| top-level failed/rate_limit_exceeded | `openai.response_rate_limited` |
| top-level failed/其他known code | `openai.response_invalid` |
| top-level failed/無code | `openai.response_failed_unknown` |
| cancelled | `openai.cancelled` |
| queued/in_progress/None | `openai.unexpected_nonterminal_status` |
| refusal與output混合 | `openai.ambiguous_refusal_and_output` |
| completed無output | `openai.missing_structured_output` |
| 多個output text | `openai.multiple_structured_outputs` |
| commentary或tool等unexpected item | `openai.unexpected_output_item` |
| JSON parse失敗 | `openai.output_parse_failed` |
| JSON root非object | `openai.output_schema_invalid` |
| resolved model不在allowlist | `openai.resolved_model_mismatch` |
| schema/operation/request local binding錯誤 | `openai.request_binding_invalid` |
| 未分類SDK status error | `openai.api_status_error` |
| 未分類adapter exception | `openai.adapter_unexpected_error` |

safe message固定如下，不可帶provider原message或exception `str(exc)`：

| 分類 | safe_message |
|---|---|
| request/config/schema binding | `The model request does not match the approved eval configuration.` |
| timeout | `OpenAI did not complete the request before the attempt deadline.` |
| connection | `The adapter could not connect to OpenAI.` |
| authentication | `OpenAI rejected the configured credentials.` |
| permission | `The configured OpenAI credentials do not permit this request.` |
| invalid request/context/not found/422 | `OpenAI rejected the model request.` |
| retryable rate limit | `OpenAI rate limiting prevented this request.` |
| quota | `OpenAI quota is unavailable for this request.` |
| provider unavailable/conflict/5xx | `OpenAI was temporarily unavailable.` |
| cancelled | `OpenAI cancelled the response.` |
| invalid/ambiguous provider output | `OpenAI returned an unusable structured response.` |
| resolved model mismatch | `OpenAI resolved an unapproved model.` |
| unexpected status/adapter exception | `The adapter could not normalize the OpenAI response.` |

safe message是給caller安全顯示，不是診斷主鍵；測試以`FailureKind + reason_code + retryable + provider_error_code`為主要斷言。原始provider message只進error artifact。

規則：

- exception的`request_id`若有，寫`provider_request_id`；
- `provider_error_code`保存SDK error body的machine code，沒有則`None`；
- safe message使用本地固定文字，不把API原message直接當user-facing文字；
- error artifact可保存`exception_type/status_code/request_id/code/param/type/body`供test診斷；
- 不保存request/response headers全集，不保存Authorization/API key，不保存traceback；
- error body若不是JSON-safe，轉成安全字串；
- limitation字串要唯一排序。

所有retryable值只表示executor「可以依operation policy建立新attempt」，不代表adapter自己retry。

---

## 12. Usage mapping

OpenAI `Response.usage`映射：

```text
input_tokens       <- usage.input_tokens
output_tokens      <- usage.output_tokens
cache_read_tokens  <- usage.input_tokens_details.cached_tokens
cache_write_tokens <- usage.input_tokens_details.cache_write_tokens
reasoning_tokens   <- usage.output_tokens_details.reasoning_tokens
```

規則：

- provider明確回0就保存0；只有欄位不存在/usage為None才保存null；
- usage整體None：五欄全null，limitation加入`openai response did not include usage`；
- nested details缺欄：只把對應欄設null，加入精確limitation；
- limitations必須排序、去重，符合`TokenUsage` validator；
- 不以`total_tokens - input - output`反推reasoning/cache；
- 不把reasoning token加入visible output；
- failure exception沒有Response usage時不能估0。

V3-5報告才做cost/latency統計；V3-4只確保資料不丟失、不偽造。

---

## 13. Artifact contract

### 13.1 Deterministic IDs

supporting artifact ID固定以attempt ID為UUIDv5 namespace：

```text
uuid5(request.attempt_id, "artifact/openai-responses/raw/v1")
uuid5(request.attempt_id, "artifact/openai-responses/visible/v1")
uuid5(request.attempt_id, "artifact/openai-responses/error/v1")
```

同attempt正常只能call一次。若錯誤程式重打同attempt得到不同response，相同deterministic ID會在immutable persistence產生conflict，幫助暴露exactly-once違規，而不是靜默覆寫。

### 13.2 Raw provider response

每個成功取得SDK `Response`的call建立：

```text
kind = provider.openai.response.raw
media_type = application/json
schema_id = null
retention_class = eval
redaction_status = not_required
contains_test_data = true
```

payload固定：

```json
{
  "http_request_id": "req_... or null",
  "sdk": "openai-python",
  "sdk_version": "2.46.0",
  "response": "response.model_dump(mode='json', exclude_none=False)的JSON值"
}
```

`response.id`（OpenAI response resource ID）在`response`內。raw artifact不能存SDK object repr。

### 13.3 Visible response

所有取得Response的call都建立visible artifact，即使items為空：

```text
kind = provider.response.visible
media_type = application/json
schema_id = null
```

payload固定：

```json
{
  "schema_version": "provider_visible_response.v1",
  "items": [
    {
      "output_index": 1,
      "message_id": "msg_...",
      "message_status": "completed",
      "content_index": 0,
      "type": "output_text",
      "text": "原始可見字串"
    }
  ]
}
```

refusal item的`type=refusal`，text保留provider原文。這份artifact不含reasoning summary/hidden chain-of-thought。順序與index不可重排。

### 13.4 Error artifact

所有`ModelOutcome.FAILED`建立normalized error artifact並由`failure.error_artifact`引用：

```text
kind = provider.openai.error
media_type = application/json
schema_id = null
```

HTTP exception與top-level `status=failed`都要有；output parse/model mismatch也要有，並在artifact中指出classification reason。若有Response，同一envelope同時包含raw、visible、error三份。

### 13.5 Parsed payload存放位置

`StructuredPayload`嵌在`ModelCallResult.parsed_output`；V3-3 executor會把整份result另存為`model.result` artifact。因此V3-4**不再建立一份沒有ref可連結的重複parsed supporting artifact**。

實際持久化分層是：

```text
raw provider shape       -> provider.openai.response.raw artifact
visible provider content -> provider.response.visible artifact
canonical parsed payload -> model.result artifact內的 parsed_output
normalized error         -> provider.openai.error artifact
```

這修正總研究文件「parsed canonical payload分開存artifact」可能造成的歧義；它確實與raw/visible分開，但由既有model result artifact承載。

### 13.6 Scope

每個supporting artifact必須完全複製request/result的：

```text
run_id, session_id, turn_id, operation_id, attempt_id
```

`created_at=result.completed_at`；`contains_test_data=true`。`ModelCallEnvelope`會再次驗ref存在與scope。

---

## 14. ModelCallResult逐欄映射

以下欄位一律從request複製，不可從config或provider重建：

```text
run_id, session_id, turn_id, operation_id, attempt_id, attempt,
operation_name, operation_definition_hash,
provider, requested_model,
prompt_hash, output_schema_id, output_schema_hash, context_hash
```

其他欄位：

| Result欄位 | 來源 |
|---|---|
| `resolved_model` | 有Response用`response.model`；network前失敗用`request.requested_model` |
| `provider_request_id` | 成功Response的`response._request_id`或SDK exception request ID |
| `provider_conversation_id` | 永遠`None` |
| `provider_finish_reason` | §10固定可逆字串 |
| `parsed_output` | completed唯一JSON經canonical build；其他None |
| `visible_response_artifact` | 有Response時通常設visible ref；network前失敗None |
| `refusal` | completed-only-refusal時固定本地safe message + provider category |
| `failure` | §10/§11分類與error ref |
| `usage` | §12 |
| `latency_ms` | monotonic elapsed，向下取整且>=0 |
| `started_at/completed_at` | injected UTC clock；不得使用provider `created_at/completed_at`取代local call timing |

`provider_request_id`在本版本明確定義為HTTP `x-request-id`，不是`response.id`。原因是欄位名稱與官方故障排查用途一致；response resource ID仍完整存在raw artifact。V3-4不為此修改neutral schema。

---

## 15. Mocked HTTP fixture與test matrix

### 15.1 Fixture原則

- response bodies由2026-07-17官方Responses OpenAPI/SDK shape人工最小化，不錄真API key；
- fixture README/manifest記錄來源URL、OpenAPI/SDK版本、建立日期、用途與是否synthetic；
- body保持provider shape，不能加`_fixture_note`等非API欄位；metadata放sidecar manifest；
- 測試一定經HTTP mock與官方SDK deserialization；不要直接mock `responses.create()`回MagicMock，否則無法抓SDK shape drift；
- 每個HTTP error提供status、JSON body與`x-request-id` header；
- 成功fixture至少有一個reasoning item排在message前，證明adapter不假設index 0。

### 15.2 必要tests

至少包含下列具名行為：

1. `test_request_body_uses_exact_schema_and_stateless_hard_invariants`
   - outbound schema canonical hash等於request output schema hash；
   - strict=true、store/background/stream false、truncation disabled；
   -沒有previous response/conversation/tools/cache/sampling；
   - instructions與alternating messages不被合併；
   - reasoning standard/medium與max output tokens正確。
2. `test_success_ignores_reasoning_item_and_parses_unique_message`
   - reasoning在index 0、message在後仍success；
   - raw/visible/result identity/request ID/usage完整。
3. `test_adapter_never_uses_output_text_concatenation`
   - multiple output text必須fail，不可拼接。
4. `test_refusal_is_not_parsed_as_json_or_retried`
5. `test_incomplete_max_tokens_without_visible_text_is_preserved`
6. `test_incomplete_content_filter_with_partial_text_is_not_success`
7. `test_failed_response_error_is_normalized_and_raw_is_kept`
8. `test_completed_without_output_is_parse_failure`
9. `test_invalid_json_has_visible_and_error_artifacts`
10. `test_unexpected_tool_call_is_not_executed`
11. `test_commentary_message_is_not_concatenated_with_final_answer`
12. `test_resolved_model_mismatch_fails_closed`
13. `test_usage_none_uses_nulls_and_sorted_limitations`
14. `test_schema_hash_mismatch_fails_before_http`
15. `test_unknown_schema_id_fails_before_http`
16. `test_operation_definition_mismatch_fails_before_http`
17. `test_expired_deadline_fails_before_http`
18. `test_400_invalid_schema_is_nonretryable_invalid_request`
19. `test_401_and_403_are_nonretryable`
20. `test_429_rate_limit_is_retryable_but_quota_is_not`
21. `test_500_503_connection_and_timeout_are_retryable`
22. `test_sdk_internal_retry_is_disabled`
   - 對429、500、timeout各自斷言mock transport只收到1次call。
23. `test_cancelled_error_propagates`
24. `test_envelope_artifact_ids_are_deterministic_and_scoped`
25. `test_api_key_and_authorization_never_enter_artifacts`
26. `test_production_app_does_not_import_eval_adapter`

### 15.3 Schema-local validation分界test

另做一個fixture，其JSON符合portable structure但違反local-only Pydantic constraint。adapter應回`SUCCEEDED`的canonical payload；把結果交給既有executor/local validator後才判定invalid並走schema repair。這個test防止adapter偷偷複製application責任。

### 15.4 不可接受的mock方式

以下測法不能算V3-4通過：

- `AsyncMock(return_value=MagicMock(output_text='...'))`；
- 只測happy path；
- 只assert JSON parse，沒有assert outcome/retry/artifact/hash；
- 429/500時沒有assert HTTP invocation count；
- no-key live test標skip後仍將整體稱為probe passed；
- fixture由adapter自己產生，讓producer/consumer一起錯。

---

## 16. Opt-in live conformance probe

### 16.1 目的

Live probe只驗：

- official endpoint可接受exact portable schema；
- SDK 2.46.0實際response shape可被normalizer處理；
- resolved model、request ID、usage與artifacts有保存；
- output可通過完整`TurnInterpretOutput`本地驗證；
- Capture bundle hash chain/manifest完整。

不以單一輸出計算模型品質，也不承諾semantic precision/recall。

### 16.2 CLI

建議命令：

```powershell
cd apps/api
$env:OPENAI_API_KEY='<secret>'
uv run python -m evals.interview_vnext.live_probe `
  --probe turn-interpret-smoke.v1 `
  --model gpt-5.6 `
  --accepted-resolved-model gpt-5.6 `
  --accepted-resolved-model gpt-5.6-sol `
  --reasoning-mode standard `
  --reasoning-effort medium `
  --output-dir ../../output/interview_vnext/live-probes
```

無`OPENAI_API_KEY`：在建立run/network前印一行安全錯誤，exit code 2；不能pytest skip，也不能產生「passed」manifest。

### 16.3 Synthetic probe

`turn-interpret-smoke.v1.json`只放虛構測試資料，至少包含：

- 一個明確員工action/output句；
- 固定turn/context payload；
- expected schema ID；
- `contains_test_data=true`；
- 不包含gold structured output，以免probe變成品質grader。

CLI由現有committed prompt、published schema與fixture建立`ModelCallRequest`。所有ID除run ID外可由`uuid5(run_id, stable label)`產生；run ID每次`uuid4()`，避免覆蓋舊bundle。

### 16.4 Capture bundle

使用現有`InMemoryArtifactStore`、`CaptureRecorder`、execution taxonomy與outbox建立真實typed events，不自行發明另一套log：

```text
workflow.run.started
model.call.started
model.call.completed | model.call.failed
workflow.run.completed | workflow.run.failed
```

stage分別使用`workflow.run`與`turn.interpret`。先put config/request/prompt/schema/context artifacts；adapter回來後put supporting與model result artifacts；最後build `RunManifest`並驗hash chain。

現有`ExecutionStatus`只有`ok | partial | failed | skipped`，不可寫`started/succeeded`等不存在值。probe固定映射：

| Event | status |
|---|---|
| `workflow.run.started` | `ok` |
| `model.call.started` | `ok` |
| `model.call.completed` + succeeded | `ok` |
| `model.call.completed` + refused/incomplete | `partial` |
| `model.call.failed` | `failed` |
| `workflow.run.completed`（adapter succeeded且完整local schema通過） | `ok` |
| `workflow.run.failed` | `failed` |

refusal/incomplete雖然是有效neutral outcome，但本次conformance probe未取得可驗證structured payload，所以probe run仍以failed結束；不能把它們當adapter crash，也不能把run標completed。

輸出到已gitignore的：

```text
output/interview_vnext/live-probes/<run_id>/
  config.json
  request.json
  result.json
  artifacts.jsonl
  events.jsonl
  manifest.json
  probe-report.json
```

所有檔案使用canonical JSON/UTF-8；先寫temp directory，全部完成與validate後atomic rename到`<run_id>`。若call失敗，也要產生failed event、failed manifest與report後exit 1；不要因失敗刪除診斷資料。

probe report至少含：

```text
run_id, probe_id, started_at, completed_at,
config_hash, request/result artifact refs,
outcome, failure/refusal/finish reason,
requested_model, resolved_model, provider_request_id,
usage, local_output_validation_passed,
manifest_hash/last_event_hash,
limitations, source_versions
```

不得寫API key、Authorization header或完整process environment。

### 16.5 Live gate

V3-4可標完成必須同時：

- probe process exit 0；
- exactly oneHTTP call；
- neutral outcome succeeded；
- exact schema被官方endpoint接受；
- full local `TurnInterpretOutput` validation通過；
- resolved model在allowlist；
- raw、visible與model result artifacts存在；
- HTTP request ID非空；
- usage有input/output；cache/reasoning若缺則有limitation；
- manifest/event chain validation通過；
- output bundle不進Git。

若API key當下不可用，mocked suite可以完成code review，但切片狀態必須寫「mocked complete, live gate pending」，不能宣稱V3-4完成。

---

## 17. Implementation順序

實作者按以下順序commit，不要一開始先寫live CLI：

1. 建立eval package/README與`OpenAIResponsesEvalConfig`；測config hash、hard invariants、secret exclusion。
2. 實作schema catalog；測unknown ID、hash mismatch、portable lint與exact outbound schema。
3. 實作client factory與single-call timeout/retry guard；先測429/500/timeout call count=1。
4. 實作raw/visible/error artifact builders與deterministic IDs；測scope/hash/no secret。
5. 實作typed output traversal與completed/refusal/incomplete/status matrix。
6. 實作HTTP/SDK exception與usage mapping。
7. 跑完整mocked matrix與既有LLM/fixed replay tests。
8. 實作minimal live probe與Capture bundle；先以mock transport測bundle。
9. 有key時跑一次official live probe，人工檢查outbound config與bundle。
10. 更新README/status/實際測試數；不要把`output/`或key commit。

若第2步發現官方endpoint不接受exact schema，停止後續步驟，按§6.4回報contract問題；不可用adapter workaround把問題藏起來。

---

## 18. 驗收命令

實作者完成後至少執行：

```powershell
cd apps/api

# V3-4 mocked adapter/live-bundle tests
uv run --locked pytest -q `
  tests/test_interview_vnext_openai_eval_adapter.py `
  tests/test_interview_vnext_openai_live_probe.py

# neutral contract與fixed replay regression
uv run --locked pytest -q `
  tests/test_interview_vnext_llm.py `
  tests/test_interview_vnext_fixed_replay_postgres.py

# vNext dependency/import boundary
uv run --locked pytest -q tests/test_interview_vnext_dependencies.py

# full API suite；PostgreSQL依現有runbook提供TEST_DATABASE_URL
uv run --locked pytest -q

# schema/doc hygiene
git diff --check
git status --short
```

PostgreSQL integration suite不能以skip當通過；按既有runbook啟動DB。live probe命令另見§16，不應放在一般CI secretless tests。

CI gate：

- mocked suite每次必跑；
- live probe預設不在PR CI自動花費或讀secret；
- 可另設manual workflow，且沒有secret時明確failed/precondition，不回報passed；
- dependency guard要證明`apps/api/app`沒有import `evals.interview_vnext`或`openai` adapter。

---

## 19. Definition of Done

### Contract與request

- [ ] 使用官方`AsyncOpenAI.responses.create`與lock的2.46.0？
- [ ] outbound schema exact hash等於request artifact hash？
- [ ] 未使用`responses.parse`重生schema？
- [ ] stateless/store/background/stream/truncation hard invariants全部可測？
- [ ] model/reasoning/service tier只在eval config，不改operation hash？
- [ ] API key沒有進config/hash/artifact/log？

### Retry/recovery

- [ ] SDK `max_retries=0`？
- [ ] 429、500、timeout各只有一次HTTP call？
- [ ] deadline同時約束wall clock與HTTP？
- [ ] `CancelledError`向外傳播？
- [ ] retryable只由typed result告知executor，adapter不自重試？

### Response semantics

- [ ] 遍歷全部typed output items且reasoning item不造成index錯誤？
- [ ] 不使用`response.output_text`拼接？
- [ ] refusal/incomplete/failed/cancelled/queued分流完整？
- [ ] incomplete無visible text仍有空visible artifact？
- [ ] multiple output、unexpected tool與invalid JSON fail closed？
- [ ] local-only Pydantic/domain validation仍在executor？

### Capture

- [ ] raw/visible/error/result分層明確？
- [ ] supporting artifact IDs deterministic且scope一致？
- [ ] response resource ID與HTTP request ID都可找回？
- [ ] usage null與limitation沒有偽造0？
- [ ] live probe產生合法events/hash chain/manifest與report？

### Scope

- [ ] 無migration、route、Web、v3改動？
- [ ] production composition root沒有import？
- [ ] 無LangChain/OpenRouter/Agents SDK/Chat Completions？
- [ ] 無Anthropic、routing、fallback、tools、stateful provider功能？
- [ ] 未把單次probe宣稱為模型品質或production gate？

任一項未滿足，V3-4不得標完成；在handoff/PR寫明具體pending項。

---

## 20. 常見錯誤與立即停線條件

看到以下任一實作，review應立即要求修正：

- `responses.parse(text_format=TurnInterpretOutput)`；
- `response.output[0].content[0]`或只讀`response.output_text`；
- adapter catch所有exception後一律retry；
- OpenAI client保留default retries；
- 以provider response/conversation ID作下回合唯一context；
- `truncation=auto`讓最早內容被靜默丟棄；
- refusal/incomplete嘗試JSON repair；
- schema 400後刪keyword再打一次；
- usage缺值填0；
- 把SDK model/error object穿過`LlmPort`；
- raw artifact只存parsed object、沒有provider status/error/output items；
- output fixture由MagicMock構造，不經SDK HTTP deserialization；
- live probe只印console、沒有Capture bundle；
- no-key被pytest skip後仍標passed；
- `app/` import `evals/`；
- 為一個adapter建立agent/provider framework。

---

## 21. 留到後續、但不是V3-4 blocker

1. `provider_response_id`目前只在raw artifact，neutral result沒有獨立欄位；先不升schema。若V6跨provider觀測真的需要，再以新schema版本提案。
2. production `safety_identifier`需要authenticated principal的不可逆hash；V5 auth/ownership完成後設計，eval-only synthetic probe不假造user ID。
3. prompt cache write/read已可Capture，但V3 fixed replay不調cache policy；V6用相同case驗證成本/品質後才決定。
4. background mode可能適合較長的episode/global operation，但需要provider job reconcile與checkpoint新規格；不偷塞進turn adapter。
5. Anthropic Messages adapter與OpenAI/Anthropic bake-off仍是V6；不得為預想共同點提前抽象化。
6. 12-case turn品質與多trial report是V3-5；V3-4 fixture不是gold dataset。

---

## 22. 交接時實作者應回報的結果

PR/交付訊息至少列出：

- 實際OpenAI SDK lock版本；
- mocked test數與完整suite數；
- 429/500/timeout transport call count證據；
- outbound schema ID/hash與exact-match test；
- live probe是否執行、run ID、resolved model、HTTP request ID是否存在；
- live bundle路徑（不要貼secret/raw員工內容）；
- usage欄位與limitations；
- production import/dependency guard結果；
- 未完成項與是否阻擋V3-5。

回報不得只寫「API接通」或「測試通過」。本切片的價值是證明provider mapping與既有durable/Capture contract一致，而不是多一個能回JSON的函式。
