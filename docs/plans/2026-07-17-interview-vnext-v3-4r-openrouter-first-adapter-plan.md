# Interview AI vNext V3-4R——OpenRouter-first adapter、routing conformance與 live gate交接規格

- 日期：2026-07-17
- 狀態：**研究定稿、已核准實作；尚未寫 code、尚未執行 OpenRouter live gate**
- 決策：[`../adr/0035-interview-vnext-openrouter-first-provider-boundary.md`](../adr/0035-interview-vnext-openrouter-first-provider-boundary.md)
- 上游 contract：[`../specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md`](../specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md)
- direct OpenAI reference：[`2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md`](2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md)
- 適用切片：**V3-4R only**；完成後才開始 V3-5正式 OpenRouter live trials
- 裁決權：本文件取代 V3 research／plan中「官方 OpenAI live gate先行」的順序。若本文件與舊
  V3-4 OpenAI規格衝突，OpenAI adapter自身行為仍由舊規格管理；OpenRouter主線與 release gate由
  本文件管理。

---

## 1. 交接結論

V3-4R不是「把 `base_url`換成 OpenRouter」；它要證明真正 production gateway的 request、routing、
response、錯誤與 Capture可以無損映射到既有 `LlmPort`，而且品質實驗不會被暗中的 alias、provider
load balancing、fallback、plugin、response healing、context compression或 cache污染。

完成後應能以證據回答：

1. Caliburn送出的 exact portable schema是否就是 persisted artifact hash描述的schema？
2. 一個 durable attempt是否只由本程式送出一個 inference HTTP request？
3. 實際使用的 model與 upstream endpoint是否等於 run config？
4. OpenRouter是否在 request內做 fallback或在 pipeline修改 prompt／response？
5. normalized/native finish reason、embedded error、usage、cost與 generation ID是否完整保存？
6. adapter失敗時是否回 typed `ModelCallResult`，不把 provider message或半截JSON當 domain事實？
7. live run能否從 Capture bundle重建 config、request、route、response、verification與 manifest？

本切片的 hard decisions：

1. gateway provider stable name固定為 `openrouter`；model author與hosting endpoint另存，不冒充provider。
2. 第一條可 promotion介面固定 `POST https://openrouter.ai/api/v1/chat/completions`。
3. 使用專案既有 `httpx.AsyncClient`直接 HTTP；不新增目前仍為 Beta 的 OpenRouter Python SDK。
4. 不共用／泛化現有 `OpenAIResponsesEvalAdapter`，也不接受任意 base URL。
5. benchmark只接受 exact canonical model slug與 exact upstream endpoint slug。
6. `allow_fallbacks=false`、`require_parameters=true`、`stream=false`、單一 choice、無 tools。
7. strict structured output使用已發布 portable schema；adapter不得重生或修改schema。
8. `X-OpenRouter-Metadata: enabled`是 hard invariant；metadata缺失即 conformance failure。
9. known mutating plugins顯式 disabled；metadata顯示任何 mutating／unknown pipeline stage即 contaminated。
10. reasoning若啟用只能使用 model snapshot明列支援的值，且 `exclude=true`；不得保存 hidden CoT。
11. 任何 retry由 durable executor建立新attempt；adapter與 HTTP transport都不重試。
12. 原 OpenAI mocked adapter保留且測試持續全綠，但官方 OpenAI live gate不再阻擋 V3-5。

V3-4R完成只代表 gateway conformance成立，**不代表模型分析品質成立**。`turn_interpret` 12-case、
multi-trial與 semantic failure review仍是 V3-5。

---

## 2. 2026-07-17官方資料核對與直接影響

以下只採 OpenRouter官方文件／API reference；HTTP transport版本另採 HTTPX官方 release資料。

| 官方來源 | 已核對事實 | 本案直接影響 |
|---|---|---|
| [API overview](https://openrouter.ai/docs/api/reference/overview) | Chat Completions是統一OpenAI-compatible schema；response含generation `id`、resolved `model`、normalized/native finish reason、usage與cost；non-streaming usage會回傳 | 主線採Chat；不可只抓content；generation/model/finish/usage/cost全部Capture |
| [OpenAPI](https://openrouter.ai/openapi.json) | OpenRouter公開完整OpenAPI，欄位可能持續增加 | fixtures按核對日最小化；parser對未知一般欄位forward-compatible，但對未知會改內容的pipeline fail closed |
| [Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) | `response_format.type=json_schema`、`strict=true`；只在相容model/provider支援；建議`require_parameters=true` | exact portable schema + local full validation；provider不支援時fail，不降級JSON mode |
| [Models](https://openrouter.ai/docs/guides/overview/models) | Models API回`id`、permanent `canonical_slug`、context、expiration、supported parameters、reasoning capability等；alias會resolve | 每個run先建model snapshot；requested必須等於canonical slug；禁latest/auto/free shortcut |
| [List model endpoints](https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints) | 可查某model可用endpoints | live probe保存endpoint snapshot並建立exact slug到官方provider identity的對照；metadata只承諾selected provider/model，不假設它回完整slug |
| [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection) | 預設load balance且`allow_fallbacks=true`；可用`only/order`、full endpoint suffix、`require_parameters`、`data_collection`、`zdr`控制；base slug會匹配同provider的多個variants | benchmark只接受snapshot中唯一匹配的slug，固定`only/order`且fallback false；privacy controls進config hash |
| [Router metadata](https://openrouter.ai/docs/guides/features/router-metadata) | header opt-in後回requested、strategy、attempt、selected endpoints、attempts與pipeline；shape可additive；cache hit不回metadata | hard requirement；一般未知欄位忽略，未知pipeline不忽略；metadata缺失也可偵測cache／帳戶設定污染 |
| [Errors and debugging](https://openrouter.ai/docs/api/reference/errors-and-debugging) | error可能是HTTP非2xx，也可能在non-streaming 200 body／choice內；`error_type`是跨skin stable分類；429/503可能有Retry-After | 先查error再查choice；完整error matrix；Retry-After只Capture，不在adapter暗中sleep/retry |
| [Reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) | unified `reasoning`會跨供應商映射；Models API可列supported efforts；某些值會被映射到最近值；`exclude=true`不回reasoning text | preflight拒絕未明列effort；不用「最近值」；exclude true；reasoning usage仍保存 |
| [Plugins](https://openrouter.ai/docs/guides/features/plugins/overview) | plugin可由request或帳戶預設啟用，且會修改request/response；帳戶可Prevent overrides | dedicated eval key/workspace不得強制plugin；request顯式disable；metadata pipeline作最後證據 |
| [Message transforms](https://openrouter.ai/docs/guides/features/message-transforms) | context compression會middle-out刪／截message；8K以下endpoint可能預設啟用 | 顯式disable context-compression；model context preflight；任何compression stage使trial contaminated |
| [Response healing](https://openrouter.ai/docs/guides/features/plugins/response-healing) | opt-in plugin可修JSON syntax但不保證schema adherence | baseline關閉，避免掩蓋model/schema failure；日後只能另做具名ablation |
| [Response caching](https://openrouter.ai/docs/guides/features/response-caching) | cache需啟用；cache hit有新generation ID、usage可為0，且不回router metadata | benchmark不送cache headers；metadata缺失fail；不可把cache hit當獨立model trial |
| [Generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-generation) | generation ID可查provider、upstream ID、native tokens、cost、latency與request ID | 不在adapter inference path多打一個GET；live report可在run後做optional audit enrichment，不能改outcome |
| [Data collection](https://openrouter.ai/docs/guides/privacy/data-collection) | prompt/output logging與OpenRouter使用內容預設關閉；request metadata仍保存；upstream有各自政策 | eval config明示data policy；secret與內容仍由Caliburn Capture管理；promotion需使用production同等privacy profile |
| [ZDR](https://openrouter.ai/docs/guides/features/zdr) | `provider.zdr=true`只路由ZDR endpoints，可能排除某些first-party endpoint | config必須明示是否要求；synthetic smoke可false，production promotion需另行核准並重跑相同route profile |
| [Responses API Beta](https://openrouter.ai/docs/api/reference/responses/overview) | 官方標Beta、stateless、可能breaking changes | 只列為parallel candidate，不作V3-4R唯一production path |
| [Python SDK API reference](https://openrouter.ai/docs/client-sdks/python/api-reference/endpoints) | 官方SDK type-safe/OpenAPI-generated，但API reference仍明寫Python SDK與docs為Beta | 本切片不新增SDK；解除Beta後用parity tests重新裁決 |
| [HTTPX releases](https://github.com/encode/httpx/releases) | 最新stable為0.28.1；專案目前lock 0.27.2，直接HTTP所需API在兩版皆存在 | V3-4R不混入全repo dependency升級；沿用lock並測exact wire。HTTPX升級另開dependency PR/full regression |

### 2.1 為何不是「越新的Responses一定越好」

Responses API的 typed items、reasoning與工具模型長期有價值，但本 operation只需要：完整context輸入、
一個strict JSON output、無tools、無provider state。使用Beta Responses不會自動提高工作分析品質，卻會
增加一個breaking wire變因。先以stable Chat做可重播品質基準，再用相同case比較Responses；只有
quality、reliability或cost有可重複收益才切換。

### 2.2 為何直接HTTP，不用 OpenAI SDK指向OpenRouter

OpenRouter官方允許用OpenAI SDK，但OpenRouter-specific的`provider`、plugins、router metadata、
native finish reason、embedded error、cost與generation audit不是OpenAI direct contract。既有OpenAI
adapter若可任意換base URL，會混淆兩個provider的錯誤與artifact語意。

`httpx.AsyncClient`已有專案lock，預設不做應用層retry，並可用`MockTransport`精確斷言headers、body、
HTTP call count與raw JSON。V3-4R只需一個endpoint，直接HTTP是較小且可稽核的surface。

### 2.3 不是永遠拒絕SDK

SDK解除Beta後，建立同一fixture matrix的SDK candidate adapter；只有 request canonical body、single-call、
error/usage/routing artifacts與live probe全部parity，才可替換transport。替換SDK不得改 neutral contract、
operation hash或品質gold。

---

## 3. Scope與明確不做

### 3.1 必須交付

1. OpenRouter secret-free eval config與canonical config hash；
2. model/endpoints snapshot acquisition與preflight validation；
3. 實作Caliburn `LlmPort`的OpenRouter Chat eval-only adapter；
4. request projection、single-call deadline、response/error/usage normalization；
5. raw/sanitized response、visible response、error與routing supporting artifacts；
6. `httpx.MockTransport` provider-shape fixture matrix；
7. opt-in `OPENROUTER_API_KEY` live conformance probe與immutable Capture bundle；
8. dependency/import guard：production `app/`不得import eval adapter；
9. README/status更新與一次真live gate結果；
10. 原OpenAI adapter regression保持全綠。

### 3.2 本切片不做

- production route、FastAPI wiring或feature flag；
- V3-5 dataset、grader與multi-trial report；
- model quality ranking或宣稱某Claude/GPT/Gemini最佳；
- OpenRouter `auto` router、models array或multi-model fallback；
- provider fallback／load balancing的production profile；
- response healing、response cache、prompt cache optimization；
- server tools、web/file plugin、agent SDK、presets；
- streaming；
- OpenRouter Responses Beta adapter；
- provider conversation/session memory；
- HTTPX或其他全repo dependency升級；
- migration 0011或修改domain Evidence/reducer；
- 把upstream provider/cost加進neutral result v1；
- 修改或刪除既有OpenAI eval adapter。

### 3.3 邊界圖

```text
ModelCallRequest + published schema artifact
             |
             v
Caliburn LlmPort
             |
             v
OpenRouterChatEvalAdapter (eval-only implementation)
  - local config/schema/model snapshot gates
  - exact Chat request + metadata header
  - one POST, no retry
  - routing/error/usage normalization
             |
             v
ModelCallEnvelope
  - neutral ModelCallResult
  - provider.openrouter.response.raw
  - provider.openrouter.routing
  - provider.response.visible
  - provider.openrouter.error (failure only)
             |
             v
existing V3-3 executor -> local Pydantic -> verifier -> reducer
```

OpenRouter adapter不能import repository/UoW、ContextBuilder、TurnInterpretOutput或reducer。完整Pydantic與
semantic verifier仍由executor負責。

---

## 4. 目錄與逐檔責任

預期新增／修改：

```text
apps/api/evals/interview_vnext/
  README.md                                  # 同時列OpenAI reference與OpenRouter active gate
  schema_catalog.py                          # format_name中性化（機械rename）
  openrouter_provider_config.py              # secret-free config + route/reasoning/profile invariants
  openrouter_model_catalog.py                # model/endpoints snapshot + preflight，無inference
  openrouter_live_probe.py                    # key-gated live probe + bundle
  providers/
    openrouter_chat.py                        # 唯一Chat adapter
  probes/
    turn-interpret-openrouter-smoke.v1.json   # synthetic input，可沿用內容但identity獨立

apps/api/tests/
  test_interview_vnext_openrouter_eval_adapter.py
  test_interview_vnext_openrouter_model_catalog.py
  test_interview_vnext_openrouter_live_probe.py
  fixtures/interview_vnext/openrouter_chat/
    manifest.json
    success.json
    length.json
    content-filter.json
    refusal-error.json
    embedded-provider-error.json
    ...
```

責任：

| 檔案 | 負責 | 不負責 |
|---|---|---|
| `openrouter_provider_config.py` | exact model/endpoint、routing/privacy/reasoning/plugin hard invariants與hash | API key、schema、env讀取 |
| `openrouter_model_catalog.py` | GET model/endpoints、保存raw snapshot、檢查canonical slug/capabilities | 每次generate查network、替使用者選最佳模型 |
| `schema_catalog.py` | published schema ID/hash到exact schema與format name | OpenRouter model/routing |
| `providers/openrouter_chat.py` | exact POST、deadline、normalize、supporting artifacts | DB、reducer、quality grader、retry scheduling |
| `openrouter_live_probe.py` | CLI、catalog snapshot、single synthetic call、Capture/manifest/report | production service、V3-5多case |

### 4.1 `schema_catalog.py`中性化

現有`CatalogEntry.openai_format_name`與`SchemaBinding.openai_format_name`只是JSON Schema format name，
OpenRouter Chat也使用同一OpenAI-style `json_schema.name`。實作先機械rename為`format_name`，同步更新
OpenAI adapter/tests；schema內容、hash、format name值與operation hash全部不得變。

若rename導致任何published schema hash變化，立即停止；這個rename只能改Python欄位名稱，不能改artifact。

### 4.2 已有自己的抽象`LlmPort`；不再建立第二套萬用provider framework

`app.interview_vnext.llm.LlmPort`、`ModelCallRequest`與`ModelCallResult`就是Caliburn-owned abstraction；
OpenRouter、OpenAI、Anthropic、未來Google adapter都實作這個port。V3-4R不是讓application直接依賴
OpenRouter，也不是用OpenRouter SDK type取代neutral contract。

現在有兩個真實且差異很大的adapter，仍不在`LlmPort`上再疊ABC、動態plugin registry或萬用normalizer。
可共用的只有：

- published schema catalog；
- neutral `LlmPort`／result/artifact types；
- 測試中的canonical fixture helper（若沒有provider語意）。

error表、request mapping、raw artifacts與response traversal保持各adapter私有。

### 4.3 Adapter按wire boundary拆，不按OpenRouter上的模型拆

`OpenRouterChatAdapter`代表Caliburn到OpenRouter Chat這條外部協定。經OpenRouter呼叫Claude、GPT、
Gemini時，只建立不同且不可變的model／endpoint config，不建立`OpenRouterClaudeAdapter`、
`OpenRouterGptAdapter`或`OpenRouterGeminiAdapter`；三者的wire、routing metadata與error skin相同，複製
adapter只會製造漂移。

官方直連是不同wire boundary，所以保留／新增各自adapter：現有`OpenAIResponsesAdapter`是GPT direct
reference；若V3-5入選Claude，才新增`AnthropicMessagesAdapter`；若入選Gemini，才評估Google direct
adapter。每個direct adapter有自己的request/error/artifact conformance，不透過OpenRouter adapter假裝。
這是「架構支援多provider adapter」的意思，不是要求一人團隊在知道入選模型前先維護所有供應商。

---

## 5. Config contract

### 5.1 型別

`OpenRouterChatEvalConfig`是immutable、secret-free Pydantic model。欄位至少如下；名稱可依既有style微調，
語意不可改：

```text
schema_version = "openrouter_chat_eval_config.v1"
provider = "openrouter"
api_format = "chat_completions"
base_url = "https://openrouter.ai/api/v1"
requested_model: NonEmptyText                 # required，無default
accepted_resolved_models: tuple[NonEmptyText] # builder由requested_model派生，固定只能一個
upstream_endpoint_slug: NonEmptyText          # required，依snapshot matching恰好命中一個endpoint
expected_upstream_provider_name: NonEmptyText # 從endpoint snapshot取得，不由slug字串猜
model_catalog_hash: Sha256                    # required
endpoint_catalog_hash: Sha256                 # required
provider_order = (upstream_endpoint_slug,)
provider_only = (upstream_endpoint_slug,)
allow_fallbacks = false
require_parameters = true
data_collection: "deny" | "allow"            # required，run不能靠帳戶隱含值
zdr_required: bool                             # required；false=省略zdr，不能反向覆蓋account policy
reasoning_effort: enum | null
reasoning_max_tokens: int | null
reasoning_exclude = true
connect_timeout_seconds: 10.0                 # 0 < x <= 60
stream = false
choice_count = 1
response_format = "json_schema"
strict_schema = true
router_metadata = true
disabled_plugins = ("context-compression", "response-healing", "web", "file-parser")
transport_retries = 0                         # direct HTTP transport／adapter不重試
response_cache = false
session_sticky_routing = false
contains_test_data = true
```

Config structural validator：

1. model與endpoint不得含前後空白；
2. model必須為`author/slug`，禁止`~`開頭、`openrouter/auto`、`openrouter/free`、`:free`、`:nitro`、
   `:floor`、`:online`與`latest` alias；
3. benchmark v1的accepted resolved models由builder派生，必須**恰好**等於`(requested_model,)`；不得讓CLI
   或一般caller傳入；也不得預先放入alias、
   fallback model或「可能回傳的近似名稱」來放寬resolved-model gate；
4. provider order/only只能恰好包含同一個exact endpoint；
5. disabled plugins必須與上列固定tuple完全相等，不可少一個或由caller增加；
6. catalog hashes必須是有效SHA-256；
7. reasoning effort與max_tokens互斥；兩者皆null代表不送reasoning；
8. reasoning max_tokens若有必須`>=1`，且由live request檢查`request.max_output_tokens`大於budget；
   Claude endpoint另依官方映射要求至少1024，不把此下限錯套所有模型；
9. `data_collection=allow`的run可做synthetic研究，但report固定`production_promotable=false`；
10. API key、Authorization、workspace secret不得出現在model dump/hash/repr。

另提供唯一公開construction path `build_openrouter_eval_config(probe_inputs, model_snapshot,
endpoint_snapshot)`；它驗證expected provider name確實來自snapshot、兩個hash等於artifact content hash，
再建立config。CLI/runner不得直接以未驗snapshot的任意字串呼叫Pydantic constructor；tests可直接constructor
建立invalid cases。

### 5.2 沒有預設模型

本文件不把研究日的Claude/GPT/Gemini slug寫成default。OpenRouter模型與endpoint會更新；隱含default會讓
未來命令在沒注意時換模型。CLI必須顯式給`--model`與`--upstream-endpoint`，並把model catalog snapshot
與config一起hash。

### 5.3 Config hash與run identity

Config canonical hash涵蓋所有上列欄位（其中已含model/endpoint snapshot hashes）。另建立run profile hash：
`canonical_hash(config_hash, published_schema_hash, probe_id, operation_definition_hash)`。API key不進任何hash。
任一route/reasoning/privacy/plugin profile不同就是不同experiment config，不可合併報表。

---

## 6. Model／endpoint snapshot與preflight

### 6.1 何時查

Live probe與V3-5 runner在建立每批run前查一次，不在每個`generate_structured()`內查：

```text
GET /api/v1/model/{author}/{slug}
GET /api/v1/models/{author}/{slug}/endpoints
```

兩個response以取得時間、URL path、HTTP request ID（若有）與raw JSON建立immutable
`provider.openrouter.model_catalog_snapshot` artifact。Authorization header不得保存。

### 6.2 Preflight hard gates

呼叫inference前必須：

1. model lookup `data.id == requested_model`；
2. `data.canonical_slug == requested_model`；若API把alias resolve到別值，拒絕；
3. `expiration_date`為null或晚於run時間；
4. input/output modalities包含text；
5. `supported_parameters`至少含`structured_outputs`、`response_format`與`max_tokens`；
6. 若config送reasoning，model capability必須明列reasoning；送effort時requested effort必須在
   `reasoning.supported_efforts`（null依官方語意代表接受全部，欄位缺失代表不支援effort selection）；
   送max_tokens時`reasoning.supports_max_tokens`必須明確為true；不得接受OpenRouter自動nearest mapping；
7. `context_length`與top provider max completion可容納probe/request budget；
8. endpoints response屬同一model且非空；
9. endpoint snapshot可把configured slug對應到官方`tag`／routing slug與provider identity；不得用display
   name或substring自行猜；
10. 依官方base-slug matching語意計算configured slug會匹配的endpoint集合，必須恰好一個。若
    `google-vertex`同時匹配default與region variants，即使snapshot內有同名default endpoint也拒絕；改選
    唯一full variant slug，或換成在該snapshot中只匹配一個endpoint的provider；
11. 唯一matched endpoint自己的`supported_parameters`至少含本request實際送出的`response_format`、
    `structured_outputs`與`max_tokens`；有reasoning時也必須支援對應欄位。model-level union不能代替
    endpoint-level能力證明；
12. route成功的證明是三者合併：outbound `only/order`為exact且唯一匹配的slug、fallback false、metadata selected
    provider/model符合snapshot、metadata attempt為1。官方metadata未承諾回完整endpoint slug，不得要求
    不存在的欄位；
13. snapshot/config/schema任一hash不符時在inference前fail。

Endpoint OpenAPI允許未來增加欄位；catalog parser保存完整raw JSON，但只把已文件化、測試fixture覆蓋的欄位
升為hard rule。不得用display name猜slug，也不得把model-level `supported_parameters`誤當每個endpoint都支援。

### 6.3 Catalog failure

Catalog 401/402/429/5xx是`catalog_probe_failed`，live run可建立failed Capture bundle，但**不得呼叫inference**。
Catalog call不算durable model attempt；其event/artifact必須與inference call分開，report列出
`catalog_http_calls`與`inference_http_calls`。

---

## 7. Exact outbound request

### 7.1 Local binding checks

`generate_structured()`在任何HTTP前依序確認：

1. `request.provider == "openrouter"`；
2. `request.requested_model == config.requested_model`；
3. request requested model等於config唯一accepted canonical model；
4. request operation name/definition hash/output contract hash符合closed catalog；
5. output schema ID/hash解析為published schema且portable lint通過；
6. prompt/context/schema/selection artifacts的scope與hash已由neutral request validator成立；
7. `deadline_at > now`且remaining time為正；
8. request.max_output_tokens足以容納reasoning budget與可見JSON；
9. operation沒有tools；本adapter只接受current `turn.interpret/1.0.0` binding；
10. config snapshot hashes已由probe/runner綁定。

Binding failure回typed `INVALID_REQUEST/openrouter.binding_invalid`，建立error artifact，HTTP call count為0。

### 7.2 Message projection

Chat request messages固定：

1. 第一個`system` message內容等於`request.instructions`；
2. 後續逐一映射neutral messages的`user`/`assistant` role與exact text；
3. 不合併相鄰message、不trim、不插入OpenRouter指令、不增加assistant prefill；
4. gold、verifier error、model name與provider name不得注入prompt；只有schema repair attempt依既有executor
   明確產生的新request可帶machine-readable validation errors。

Mock test將outbound messages與request artifact逐字比較，包括中文、換行與Unicode。

### 7.3 唯一允許的body

概念shape如下；實際JSON key使用OpenRouter REST snake_case：

```json
{
  "model": "<exact canonical slug>",
  "messages": [
    {"role": "system", "content": "<request.instructions>"},
    {"role": "user", "content": "<exact text>"}
  ],
  "max_tokens": 4096,
  "stream": false,
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "turn_interpret_output_v1",
      "strict": true,
      "schema": {"<exact published portable schema>": "..."}
    }
  },
  "provider": {
    "order": ["<exact endpoint slug>"],
    "only": ["<exact endpoint slug>"],
    "allow_fallbacks": false,
    "require_parameters": true,
    "data_collection": "deny"
  },
  "plugins": [
    {"id": "context-compression", "enabled": false},
    {"id": "response-healing", "enabled": false},
    {"id": "web", "enabled": false},
    {"id": "file-parser", "enabled": false}
  ]
}
```

若`zdr_required=true`，`provider.zdr=true`；false時省略，不送false假裝覆蓋account policy。

若reasoning啟用，額外加入且只加入：

```json
{"reasoning": {"effort": "medium", "exclude": true}}
```

或：

```json
{"reasoning": {"max_tokens": 4096, "exclude": true}}
```

兩者不得同時。

### 7.4 必須省略的欄位

以下不得出現在benchmark body：

```text
models, route, preset, session_id, user, trace,
tools, tool_choice, parallel_tool_calls,
response-healing enabled, context-compression enabled,
transforms, web_search_options,
temperature, top_p, top_k, seed,
n, stop, logprobs,
stream_options,
metadata,
assistant prefill
```

缺省sampling參數代表使用該model/endpoint當下default；model snapshot保存default parameters。V3-5若要比較
sampling設定，必須建立新generation profile/config hash，不得臨時塞欄位。

### 7.5 Headers

只允許：

```text
Authorization: Bearer <OPENROUTER_API_KEY>
Content-Type: application/json
Accept: application/json
X-OpenRouter-Metadata: enabled
```

`HTTP-Referer`與`X-OpenRouter-Title`是官方optional attribution headers，不影響功能；V3-4R不送，避免
測試／本機值漂移。若production要送，另納入deployment config，不進domain operation。

不得送`X-OpenRouter-Cache`、debug、experimental metadata舊header或自創idempotency header。

### 7.6 Endpoint與redirect

URL hardcode `https://openrouter.ai/api/v1/chat/completions`。不接受CLI base URL，不跟redirect，避免
Authorization被送往其他host。測試注入`httpx.MockTransport`，不是換production URL。

---

## 8. Deadline、timeout、retry與取消

### 8.1 一個durable attempt的定義

```text
Caliburn durable attempt
  -> 0或1個catalog外的inference POST
  -> OpenRouter internal upstream attempt(s)
```

本adapter保證本地只送一次POST；無法宣稱gateway內只做一次推論。benchmark要求
`allow_fallbacks=false`且成功metadata `attempt==1`，若仍顯示多attempt，trial contaminated。

### 8.2 HTTP client

Owned client：

- `httpx.AsyncClient(follow_redirects=False)`；
- TLS verification使用HTTPX預設true；
- 不安裝retry transport；
- adapter context manager／`aclose()`負責關閉；
- 測試注入external client時由caller關閉。

HTTPX沒有本案所需的應用層自動retry；mocked 429、500、timeout tests仍必須斷言transport恰收到1 call。

### 8.3 Wall-clock deadline

`request.deadline_at`是authority：

1. 用injected UTC clock算remaining；
2. connect timeout=`min(config.connect_timeout_seconds, remaining)`；
3. HTTPX read/write/pool timeout不得超過remaining；
4. 外層使用`asyncio.timeout(remaining)`涵蓋serialization、network與decode；
5. latency用monotonic clock；
6. `asyncio.CancelledError`原樣重拋，不偽裝provider failure。

Deadline到期回`TRANSPORT_TIMEOUT/openrouter.timeout/retryable=true`；SDK／adapter本身不sleep、不retry。

### 8.4 Retry-After

OpenRouter 429/503可能回`Retry-After`。error artifact只保存已parse且上限合理的秒數與原始allowlisted header；
V3-4R不修改neutral result v1，也不在adapter sleep。現有executor的retry scheduling缺口列為V7 production
blocker。V3-5遇429/503的trial標`infrastructure_invalid`並在外層batch scheduler稍後重跑，不計入品質失敗。

---

## 9. Response處理演算法

### 9.1 先保存sanitized raw，再判斷

只要收到HTTP response（含非2xx），先建立raw artifact，內容至少：

```text
schema_version=openrouter_chat_raw.v1
http.status_code
http.headers.x-request-id
http.headers.x-generation-id
gateway=openrouter
api_format=chat_completions
body=<JSON or bounded text fallback>
redactions=[]
```

只保存allowlisted headers；不得保存Authorization、cookies或整份request headers。

若body包含`message.reasoning`、`reasoning_details`或其他reasoning text，即使已要求exclude，raw artifact將
該值替換為`{present:true, byte_length, sha256, redacted:true}`，`redaction_status=redacted`。hidden CoT不進
Capture、log、error或grader。

### 9.2 判斷優先序

1. JSON decode失敗：HTTP 2xx→`OUTPUT_PARSE_FAILED`；非2xx→typed HTTP failure，raw text只進error artifact。
2. body有top-level `error`：依`error.metadata.error_type`分類，不看HTTP 200與否。
3. HTTP非2xx且無error object：依status fallback分類為typed failure。
4. 驗證top-level object、`object=chat.completion`、generation `id`、resolved `model`。
5. 驗證router metadata存在且route未污染。
6. 驗證`choices`恰好一個、index=0。
7. 若choice內有`error`或`finish_reason=error`，依embedded error分類。
8. 驗證message role、tool calls與finish reason。
9. 建visible artifact。
10. 依finish reason分流；只有`stop`進JSON parse。
11. JSON必須是單一object root，建立`StructuredPayload`；完整TurnInterpretOutput仍由executor驗證。

不得使用正規表示式從混合文字抽JSON、不得剝markdown fence、不得修逗號、不得呼叫response healing。

### 9.3 Router metadata gate

成功、準備進入content parse的`openrouter_metadata`必須滿足（edge/auth/500 error依官方規格可能沒有
metadata，先由§10 error table分流，不誤判route contamination）：

- `requested == config.requested_model`；
- strategy為direct等不含alias/auto/fallback的已核准值；初版allowlist只接受`direct`；
- `attempt == 1`；
- selected endpoint candidate恰好一個，`provider`與`model`等於endpoint snapshot導出的
  `expected_upstream_provider_name`與resolved model；metadata不提供完整slug時不做字串臆測；
- `attempts`缺省或只含一次成功的同provider/model；
- `pipeline`缺省或空。

下列任何一項使result為`FAILED`，reason `openrouter.route_contaminated`或更精確code：

- metadata缺失；
- strategy是auto/latest/alias/fallback/pareto/fusion/bodybuilder；
- attempt不是1；
- selected provider/model與pinned endpoint snapshot不符；
- pipeline出現context compression、response healing、plugin、server tools；
- 未知pipeline stage（初版fail closed）。

一般metadata新增欄位可忽略並保留raw；pipeline是可能改內容的執行證據，未知時不能忽略。

### 9.4 Choice與visible內容

成功／部分內容visible artifact固定：

```json
{
  "schema_version": "provider_visible_response.v1",
  "items": [
    {
      "type": "output_text",
      "choice_index": 0,
      "text": "<provider visible content>"
    }
  ]
}
```

若有refusal欄／content policy error，item type=`refusal`；provider原文只進artifact，不成為safe message。
Reasoning不屬visible item。tool call不得執行，保存其sanitized shape後回failure。

### 9.5 Finish reason mapping

| Chat結果 | Neutral outcome | FinishReason | 行為 |
|---|---|---|---|
| `stop` +唯一object JSON | `SUCCEEDED` | `COMPLETED` | 建StructuredPayload |
| `length` | `INCOMPLETE` | `MAX_OUTPUT_TOKENS` | 保存partial visible，不猜JSON |
| `content_filter` | `REFUSED` | `SAFETY_REFUSAL` | fixed safe refusal；原文只進visible |
| `tool_calls` | `FAILED` | `TOOL_USE` | `OUTPUT_PARSE_FAILED`，因request無tools |
| `error` + typed error | `FAILED`或`REFUSED` | 依§10 | 不parse partial content |
| `stop`但content空 | `FAILED` | `PROVIDER_ERROR` | `openrouter.empty_content`，retryable=true |
| `stop`但invalid JSON | `FAILED` | `PROVIDER_ERROR` | `OUTPUT_PARSE_FAILED`，retryable=false |
| `stop`但root非object | `FAILED` | `PROVIDER_ERROR` | `OUTPUT_SCHEMA_INVALID`，retryable=false |
| unknown/null | `FAILED` | `UNKNOWN` | protocol failure |

`provider_finish_reason`保存可逆值：

```text
chat:<normalized>|native:<native-or-none>
embedded_error:<error_type-or-unmapped>
http_error:<status>:<error_type-or-unmapped>
route_contaminated:<code>
```

### 9.6 Refusal

下列映射`REFUSED/SAFETY_REFUSAL`：

- finish reason `content_filter`；
- stable error_type `content_policy_violation`或`refusal`；
- 403且router metadata pipeline明確顯示guardrail block。

Safe message固定`The model declined this request.`，provider category保存stable error type／guardrail code。
一般403 permission denied沒有guardrail證據時是authentication/permission failure，不猜成refusal。

---

## 10. Error classification matrix

分類優先使用stable `error_type`，HTTP status只作fallback。原message永不進safe message。

| error_type／status | FailureKind / outcome | reason_code | retryable | finish |
|---|---|---|---:|---|
| `context_length_exceeded` | INVALID_REQUEST | `openrouter.context_window_exceeded` | false | CONTEXT_WINDOW_EXCEEDED |
| `max_tokens_exceeded` | INVALID_REQUEST | `openrouter.max_tokens_exceeded` | false | MAX_OUTPUT_TOKENS |
| `token_limit_exceeded` | INVALID_REQUEST | `openrouter.token_limit_exceeded` | false | MAX_OUTPUT_TOKENS |
| `string_too_long` | INVALID_REQUEST | `openrouter.string_too_long` | false | CONTEXT_WINDOW_EXCEEDED |
| `authentication` / 401 | AUTHENTICATION_FAILED | `openrouter.authentication_failed` | false | PROVIDER_ERROR |
| `permission_denied` / plain 403 | AUTHENTICATION_FAILED | `openrouter.permission_denied` | false | PROVIDER_ERROR |
| `payment_required` / 402 | RATE_LIMITED | `openrouter.credits_unavailable` | false | PROVIDER_ERROR |
| `rate_limit_exceeded` / 429 | RATE_LIMITED | `openrouter.rate_limited` | true | PROVIDER_ERROR |
| `provider_overloaded` / 503/529 | PROVIDER_UNAVAILABLE | `openrouter.provider_overloaded` | true | PROVIDER_ERROR |
| `provider_unavailable` / 502 | PROVIDER_UNAVAILABLE | `openrouter.provider_unavailable` | true | PROVIDER_ERROR |
| `timeout` / 408/504/524 | TRANSPORT_TIMEOUT | `openrouter.provider_timeout` | true | PROVIDER_ERROR |
| `server` / 500 | PROVIDER_UNAVAILABLE | `openrouter.server_error` | true | PROVIDER_ERROR |
| `unmapped` / other 5xx | UNKNOWN_PROVIDER_FAILURE | `openrouter.unmapped_provider_error` | true | PROVIDER_ERROR |
| `invalid_request` | INVALID_REQUEST | `openrouter.invalid_request` | false | PROVIDER_ERROR |
| `invalid_prompt` | INVALID_REQUEST | `openrouter.invalid_prompt` | false | PROVIDER_ERROR |
| `not_found` / 404 | INVALID_REQUEST | `openrouter.not_found` | false | PROVIDER_ERROR |
| `precondition_failed` / 412 | INVALID_REQUEST | `openrouter.precondition_failed` | false | PROVIDER_ERROR |
| `payload_too_large` / 413 | INVALID_REQUEST | `openrouter.payload_too_large` | false | PROVIDER_ERROR |
| `unprocessable` / 422 | INVALID_REQUEST | `openrouter.unprocessable` | false | PROVIDER_ERROR |
| `content_policy_violation` | REFUSED | `openrouter.content_policy_violation` | n/a | SAFETY_REFUSAL |
| `refusal` | REFUSED | `openrouter.refusal` | n/a | SAFETY_REFUSAL |
| local `httpx.TimeoutException` | TRANSPORT_TIMEOUT | `openrouter.timeout` | true | PROVIDER_ERROR |
| local `httpx.TransportError` | TRANSPORT_ERROR | `openrouter.transport_error` | true | PROVIDER_ERROR |
| resolved model mismatch | RESOLVED_MODEL_MISMATCH | `openrouter.resolved_model_mismatch` | false | PROVIDER_ERROR |
| route metadata mismatch | UNKNOWN_PROVIDER_FAILURE | `openrouter.route_contaminated` | false | PROVIDER_ERROR |

如果body的error code與HTTP status矛盾，stable error type主導classification，raw/error artifact同時保存兩者與
`status_mismatch=true`供調查。完全未知4xx為`UNKNOWN_PROVIDER_FAILURE/retryable=false`；完全未知5xx為true。

Safe messages固定本地字典，例如：

```text
timeout: OpenRouter did not complete the request before the attempt deadline.
connection: The adapter could not connect to OpenRouter.
authentication: OpenRouter rejected the configured credentials.
permission: The configured OpenRouter credentials do not permit this request.
credits: OpenRouter credits are unavailable for this request.
invalid: OpenRouter rejected the model request.
rate: OpenRouter rate limiting prevented this request.
unavailable: OpenRouter or the selected model endpoint was temporarily unavailable.
bad_output: OpenRouter returned an unusable structured response.
route: OpenRouter did not use the approved model routing profile.
```

---

## 11. Usage、cost與identity mapping

### 11.1 TokenUsage

| OpenRouter Chat欄位 | Neutral欄位 |
|---|---|
| `usage.prompt_tokens` | `input_tokens` |
| `usage.completion_tokens` | `output_tokens` |
| `usage.prompt_tokens_details.cached_tokens` | `cache_read_tokens` |
| `usage.prompt_tokens_details.cache_write_tokens` | `cache_write_tokens` |
| `usage.completion_tokens_details.reasoning_tokens` | `reasoning_tokens` |

明確0保存0；缺失保存null並加入sorted unique limitation。`usage.total_tokens`作diagnostic一致性檢查，
不另映射。若`prompt+completion != total`，不改值，routing/raw artifact加`usage_total_mismatch=true`。

### 11.2 Cost

`usage.cost`與cost details沒有neutral TokenUsage欄，保存於routing/raw artifact，以decimal字串canonical化，
不得用binary float重算。V3-5報告從artifact讀；本切片不改neutral schema。

### 11.3 IDs

- `ModelCallResult.provider_request_id`：HTTP `x-request-id`；沒有就null，不拿generation ID冒充；
- response `id`／`X-Generation-Id`：OpenRouter generation ID，保存在raw/routing artifact；
- upstream provider request ID：若generation/router metadata有，保存artifact；
- `provider_conversation_id=None`；
- `resolved_model=response.model`，必須exact等於requested canonical model；prefix/substring不放行。

Generation API的optional audit GET不在adapter內執行，也不回填／改寫已terminal result。若執行，新增
`provider.openrouter.generation_audit` artifact與event，失敗只標enrichment failure。

---

## 12. Artifact contract

Call-scoped artifacts以`uuid5(request.attempt_id, stable-label)`產生，scope必須與result完全一致。
Catalog snapshots在request/attempt建立前取得時，以`uuid5(run_id, stable catalog label + model)`產生，
scope到run/session且`attempt_id=None`；若batch共用snapshot，每個run仍保存content-addressed ref。全部
`contains_test_data=true`、retention class=`eval`。

### 12.1 Kinds

| kind | 必要時機 | 內容 |
|---|---|---|
| `provider.openrouter.response.raw` | 收到任何HTTP response | sanitized HTTP/body/generation/model/usage/error |
| `provider.openrouter.routing` | 有router metadata或route檢查結果 | requested/resolved model、configured endpoint slug、selected provider/model、attempts、pipeline、cost |
| `provider.response.visible` | success/refusal/incomplete/output failure有可見內容 | 順序化visible items，不含reasoning |
| `provider.openrouter.error` | typed failure | classification、status、error_type/provider_code、Retry-After、safe diagnostics |
| `provider.openrouter.model_catalog_snapshot` | 每live run/batch | model/endpoints raw snapshot與capability decisions |
| `provider.openrouter.generation_audit` | optional post-run | generation GET raw metadata，不改result |

### 12.2 Routing artifact最小shape

```json
{
  "schema_version": "openrouter_routing.v1",
  "requested_model": "...",
  "resolved_model": "...",
  "configured_endpoint_slug": "...",
  "expected_provider_name": "...",
  "selected_provider_name": "...",
  "selected_model": "...",
  "strategy": "direct",
  "router_attempt": 1,
  "attempts": [],
  "pipeline": [],
  "is_byok": false,
  "region": null,
  "generation_id": "gen-...",
  "http_request_id": "req-...",
  "cost_usd": "0.00123",
  "conformance": {
    "model_match": true,
    "provider_model_match": true,
    "single_upstream_attempt": true,
    "pipeline_clean": true,
    "metadata_present": true
  }
}
```

未知metadata欄位保留於raw子物件；artifact的conformance欄只由本地deterministic checker產生。

### 12.3 Error artifact

不得保存API key或整份exception repr。至少：

```text
classification.failure_kind/reason_code/retryable/provider_error_code
http_status
error_type
provider_code
request_id
generation_id
retry_after_seconds
route_conformance
body (sanitized test-only)
exception_type (local transport only)
```

### 12.4 Raw不是hidden reasoning archive

「raw」代表provider wire facts可稽核，不代表可以永久保存供應商hidden CoT。reasoning text一律redact；
visible output與usage保留。測試必須放一個故意回reasoning的fixture，斷言artifact沒有原文且secret scan通過。

---

## 13. `ModelCallResult`逐欄規則

下列一律從request複製：

```text
run_id, session_id, turn_id, operation_id, attempt_id, attempt,
operation_name, operation_definition_hash,
provider, requested_model,
prompt_hash, output_schema_id, output_schema_hash, context_hash
```

其餘：

| 欄位 | authority |
|---|---|
| `resolved_model` | response.model；無response時requested model |
| `provider_request_id` | x-request-id；缺失null |
| `provider_conversation_id` | 永遠null |
| `outcome/finish_reason` | §9/§10 deterministic table |
| `provider_finish_reason` | normalized + native／error可逆字串 |
| `parsed_output` | 只在唯一object JSON success建立 |
| `visible_response_artifact` | success/refusal/incomplete與output-related failure |
| `refusal` | only refusal outcome，safe local text |
| `failure` | only failed outcome，typed classification |
| `usage` | §11；無response全部null + limitation |
| `latency_ms` | local monotonic elapsed，四捨五入規則固定與OpenAI adapter一致 |
| `started_at/completed_at` | injected UTC clock；provider timestamp只進raw |

Adapter成功只表示JSON object可建立`StructuredPayload`；不得在此import或執行
`TurnInterpretOutput.model_validate()`。V3-3 executor的完整local validation與deterministic verifier不可移走。

---

## 14. Mocked HTTP fixture與test matrix

### 14.1 Fixture原則

- 依2026-07-17官方OpenAPI／docs shape人工最小化；
- body不放測試註解，來源URL、核對日、用途、hash放`manifest.json`；
- 經真`httpx.Response`與adapter JSON decoder，不mock內部normalize函式；
- request assertion看exact parsed body與headers；
- unknown additive欄位fixture證明forward compatibility；
- 不含真key、真員工資料或hidden reasoning原文。

### 14.2 Config/catalog tests

1. config dump/hash無secret；
2. alias/auto/free/latest/variant shortcuts拒絕；
3. accepted models恰好只有requested canonical model，provider lists exact；
4. reasoning effort/max tokens互斥；
5. data_collection/zdr明示進hash；
6. model id/canonical slug exact；
7. alias resolution拒絕；
8. expired model拒絕；
9. model-level structured outputs／response format/max tokens capability缺一拒絕；
10. configured base slug同時匹配default/region/turbo時拒絕，full variant唯一匹配時通過；
11. model-level支援但唯一endpoint缺structured output／max tokens／requested reasoning時拒絕；
12. reasoning effort不在supported_efforts，或送max_tokens但supports_max_tokens非true時拒絕；
13. catalog 401/429/500不打inference；
14. catalog raw artifact不含Authorization。

### 14.3 Request tests

1. exact URL、method、headers；
2. system/user/assistant messages逐字映射；
3. exact schema canonical hash等於request artifact與published schema；
4. provider only/order exact、fallback false、require parameters true；
5. plugins顯式disabled；
6. optional zdr true only when required；
7. reasoning exact且exclude true；
8. forbidden body keys全部不在；
9. expired deadline/binding/schema mismatch HTTP count=0；
10. 429/500/timeout各HTTP count=1；
11. cancellation重拋；
12. owned/external HTTP client lifecycle。

### 14.4 Success/output tests

1. success strict object；
2. unknown top-level/metadata additive欄位仍成功且raw保留；
3. choices空／多個／index錯；
4. message role錯、content null/list、tool_calls；
5. finish length + partial／empty；
6. content_filter/refusal；
7. invalid JSON、markdown fenced JSON、mixed prose+JSON、non-object root；
8. empty content（retryable typed failure）；
9. resolved model exact mismatch（不得prefix放行）；
10. native finish reason保存；
11. reasoning text被redact且不進visible；
12. full local-only Pydantic constraint仍由executor test證明。

### 14.5 Routing contamination tests

1. metadata missing；
2. requested mismatch；
3. strategy auto/latest/alias/fallback；
4. router attempt >1；
5. selected provider/model與endpoint snapshot不符／多選；
6. attempts顯示早先失敗；
7. context compression stage；
8. response healing stage；
9. server tool/plugin stage；
10. unknown pipeline stage fail closed；
11. metadata一般unknown field pass；
12. cache-like response（metadata missing + zero usage）不得算success。

### 14.6 Error tests

每個§10 stable error type至少一個table-driven case；另測：

- HTTP error envelope；
- HTTP 200 top-level error；
- HTTP 200 choice embedded error + partial content；
- error_type/status矛盾；
- 500 masked message；
- Retry-After valid/invalid/過大；
- unknown 4xx/5xx；
- non-JSON error body；
- raw/error artifact deterministic UUID與scope；
- safe message不含provider原文／prompt／key。

### 14.7 Usage tests

- all fields含cache write/reasoning/cost；
- explicit zeros；
- usage整個缺失；
- nested details缺失；
- total mismatch；
- decimal cost不以float重算；
- limitations sorted/unique。

---

## 15. Opt-in live conformance probe

### 15.1 CLI

模組固定：

```powershell
cd apps/api
$env:OPENROUTER_API_KEY='<secret>'
uv run --locked python -m evals.interview_vnext.openrouter_live_probe `
  --probe turn-interpret-openrouter-smoke.v1 `
  --model '<exact-canonical-model-slug>' `
  --upstream-endpoint '<exact-provider-endpoint-slug>' `
  --data-collection deny `
  --zdr-required false `
  --reasoning-effort medium `
  --output-dir ../../output/interview_vnext/openrouter-live-probes
```

`--reasoning-effort none`表示不送reasoning；CLI轉成null，不送字串`none`，除非model明列支援且實驗明確
要測disable semantics。model與endpoint不得有default。

### 15.2 Key與exit codes

- 無`OPENROUTER_API_KEY`：exit 2、stderr明確說明、run/artifact/output directory皆不建立；
- catalog/preflight失敗：exit 1、建立failed bundle但inference call=0；
- inference或route/local validation失敗：exit 1、建立完整failed bundle；
- conformance全部通過：exit 0。

CLI永不印key、Authorization或完整prompt/output；只印run ID、pass/fail、bundle path、requested/resolved
model、configured endpoint slug與selected provider/model。

Live gate使用dedicated eval key/workspace。執行前由人工checklist確認：未套preset、沒有account-wide
provider allowlist改寫本run、沒有Prevent Overrides的default plugin／guardrail、response cache未由preset
啟用。API目前沒有單一端點可完整證明所有dashboard設定，因此這些條件不能偽裝成自動preflight；最終仍由
request明示disable、exact-route metadata與pipeline/cache gates驗證實際結果。checklist與確認時間進bundle，
不保存管理者身分或secret。

### 15.3 Probe流程

```text
check key/CLI
 -> create run IDs + secret-free provisional probe inputs
 -> GET model + endpoints snapshots
 -> construct final config with snapshot hashes/provider identity
 -> preflight
 -> build same published prompt/schema/context/request artifacts
 -> run.started + catalog events
 -> call.started
 -> adapter POST exactly once
 -> persist supporting artifacts + model.result
 -> local TurnInterpretOutput validation
 -> call.completed/failed
 -> run.completed/failed
 -> RunManifest + hash chain
 -> atomic bundle write (temp directory -> rename)
```

Probe用synthetic test-only employee content，不接DB production profile、不寫現有JD。

### 15.4 Bundle

```text
<run-id>/
  probe-inputs.json
  config.json
  model-catalog.json
  endpoint-catalog.json
  request.json
  result.json
  artifacts.jsonl
  events.jsonl
  manifest.json
  probe-report.json
```

Catalog完全失敗時可能沒有final `config.json`；此時`probe-inputs.json`保存CLI的secret-free model、endpoint、
privacy/reasoning選擇，report明列`final_config_created=false`。成功或進入inference的run必須有final config。

`probe-report.json`至少：

```text
run/probe/config/schema/model/endpoints hashes
catalog HTTP counts/status
inference HTTP count
requested/resolved model
configured endpoint slug、expected/selected provider name與selected model
router strategy/attempt/pipeline
generation ID/request ID
outcome/finish/native finish/error type
usage/cache/reasoning tokens/cost
route conformance booleans
local output validation
manifest/hash-chain validation
production_promotable
limitations
```

Bundle在`output/`且gitignored。寫入temp directory，所有檔案與manifest驗證完成後rename；crash不留下看似
完整的final directory。

### 15.5 Live gate

V3-4R完成必須同時：

1. mocked matrix全綠；
2. neutral/fixed replay/dependency/full API+PostgreSQL regression全綠；
3. 使用真`OPENROUTER_API_KEY`至少一次；
4. model與endpoint catalog snapshot成功且canonical；configured slug依官方matching語意只匹配一個endpoint，
   該endpoint支援本request全部必要參數；
5. inference POST恰好1次；
6. route metadata存在、strategy direct、attempt 1；outbound exact endpoint限制成立，selected
   provider/model符合endpoint snapshot；
7. pipeline clean、無cache跡象；
8. resolved model恰好等於requested canonical model；
9. strict schema被接受；
10. local full output validation通過；
11. usage與cost合理，缺值有limitation；
12. artifacts/events/manifest/hash chain重新驗證通過；
13. bundle secret scan通過；
14. 人工檢查outbound config與bundle後在交付報告記run ID/hash。

只有mocked tests不算完成；沒有key時狀態寫`mocked complete, OpenRouter live gate pending`。原官方
OpenAI live gate可以pending，不影響本slice完成。

---

## 16. V3-5的接法

### 16.1 順序

```text
V3-4R mocked conformance
 -> V3-4R one live probe
 -> V3-5 deterministic harness
 -> V3-5 12 cases x >=3 trials, exact route
 -> failure attribution/re-run
 -> only then model/endpoint comparison
```

### 16.2 Benchmark profile

每個V3-5 config固定：

- one exact canonical model；
- one exact endpoint；
- one reasoning profile；
- fallback off；
- plugins/cache off；
- same prompt/schema/context policy hashes；
- 每case至少3獨立inference，不用response cache；
- contaminated/infrastructure-invalid trials不算quality denominator，必須補跑且保留原failure。

### 16.3 模型比較

先以相同12 cases分別跑每個候選model/endpoint，不在一個request放`models`。報告盲化provider/model名稱
給human reviewer。若選Claude再做Anthropic direct對照；選GPT再用現有OpenAI direct adapter對照。

OpenRouter gateway與direct vendor比較必須使用相同：

- model snapshot（能對齊時）；
- prompt/schema/context artifacts；
- output budget/reasoning profile；
- cases/trials/graders；
- privacy/routing限制的書面差異。

### 16.4 Resilience profile晚於quality gate

只有各endpoint個別通過後，才建立新config：

1. 同model provider fallback；
2. 再評估多model fallback；
3. 每個fallback resolved model都在allowlist且獨立通過quality floor；
4. Capture router attempts/pipeline；
5. availability收益與品質退化分開報告。

不得把fallback成功掩蓋第一endpoint失敗，也不得把混合模型結果當單一模型分數。

### 16.5 從eval adapter升為production adapter：移動，不複製

V3-4R的`eval-only`指「尚未接production composition／route」，不是throwaway prototype。V3-5/V6選型
通過、進V7 pilot以前，另開一個promotion slice：

1. 將已通過同一fixture/live/quality gates的`openrouter_chat.py`實作移到
   `app/interview_vnext/providers/openrouter_chat.py`；不得copy後留下兩份normalize/error邏輯；
2. 將真正屬transport的immutable profile／types一併移到production provider package；catalog runner、
   probe CLI、gold與report仍留`evals/`；
3. eval harness改為import production adapter，原V3-4R全部tests不改期待值並持續通過；
4. production adapter不得反向import`evals`，dependency test強制；
5. exact benchmark profile永久保留可重播；production fallback/cache/privacy profile另以versioned config
   新增，不改寫已通過的profile；
6. promotion slice仍不自動接Web。只有V7 pilot gate核准後，composition root才注入這個adapter。

V3-4R檔案位置依§4固定留在`evals/interview_vnext/providers/`，不得由實作者自行改放production package；
這可在quality gate前防止composition誤接。上述promotion slice是唯一允許的搬移時點，且搬移commit必須
同時刪除eval舊實作、改由eval harness import production adapter，確保任何時間都只有一份provider實作。

---

## 17. 實作順序與commit切片

### 17.1 R0——文件與status（本文件）

- ADR 0035；
- 本交接規格；
- 更新V3 research/plan、implementation plan、eval/app README與docs index；
- 無code、無dependency。

### 17.2 R1——Schema catalog中性rename

- `openai_format_name -> format_name`；
- 更新OpenAI adapter/tests；
- schema/hash/artifact完全不變；
- 跑原66 focused + neutral/dependency tests；
- 獨立commit。

### 17.3 R2——Config與model catalog

- config validators/hash；
- model/endpoints GET client；
- snapshot artifacts與fixtures；
- no-key/secret tests；
- 尚不打inference；
- 獨立commit。

### 17.4 R3——Request/single-call/error path

- exact HTTP body/headers/deadline；
- no retry；
- raw/error artifacts；
- HTTP與embedded error table；
- single-call assertions；
- 獨立commit。

### 17.5 R4——Success/routing/usage path

- choices/content/finish traversal；
- route contamination gates；
- visible/routing artifacts；
- usage/cost/reasoning redaction；
- full fixture matrix；
- 獨立commit。

### 17.6 R5——Live probe/bundle

- CLI/key gates；
- catalog + inference events；
- manifest/hash chain；
- mocked bundle tests；
- production import guard；
- 獨立commit。

### 17.7 R6——真live gate與status

- 執行一次真probe；
- 人工檢查、不commit bundle；
- 回寫run ID、config hash、manifest hash與限制；
- full regression；
- 狀態改complete；
- 獨立commit。

不得把R1–R6壓成一個巨大commit；每一步失敗時保留前一步可審查狀態。

---

## 18. 驗收命令

實作者完成後至少：

```powershell
cd apps/api

# OpenRouter focused
uv run --locked pytest -q -p no:cacheprovider `
  tests/test_interview_vnext_openrouter_model_catalog.py `
  tests/test_interview_vnext_openrouter_eval_adapter.py `
  tests/test_interview_vnext_openrouter_live_probe.py

# Existing direct OpenAI regression
uv run --locked pytest -q -p no:cacheprovider `
  tests/test_interview_vnext_openai_eval_adapter.py `
  tests/test_interview_vnext_openai_live_probe.py

# Neutral workflow/import boundary
uv run --locked pytest -q -p no:cacheprovider `
  tests/test_interview_vnext_llm.py `
  tests/test_interview_vnext_fixed_replay_postgres.py `
  tests/test_interview_vnext_dependencies.py

# Full API + real PostgreSQL per runbook
uv run --locked pytest -q -p no:cacheprovider

# Hygiene
git diff --check
rg -n "evals\.interview_vnext|openrouter_chat" app
```

最後一個`rg`在production `app/`應無eval adapter import；文件文字或provider-neutral stable name不算import，
dependency AST test才是authority。

Live命令見§15.1。不得把無key exit 2記成passed或skip。

---

## 19. Definition of Done checklist

### Contract/request

- [ ] `provider=openrouter`，沒有把model author當provider？
- [ ] stable Chat endpoint hardcoded且不follow redirect？
- [ ] exact canonical model與endpoint snapshot/preflight？
- [ ] exact published schema/hash、strict true、require parameters true？
- [ ] body/headers forbidden fields tests完整？
- [ ] system/messages逐字、不加prefill/gold？

### Routing

- [ ] fallback false、single model、exact only/order？
- [ ] metadata enabled且缺失fail？
- [ ] strategy/attempt與selected provider/model對endpoint snapshot的hard gates？
- [ ] mutating與unknown pipeline fail closed？
- [ ] alias/auto/free/latest shortcuts拒絕？

### Retry/deadline

- [ ] adapter一次attempt最多一個inference POST？
- [ ] 429/500/timeout mock call count各為1？
- [ ] deadline涵蓋完整call且cancel重拋？
- [ ] Retry-After只Capture，沒有adapter sleep/hidden retry？

### Response/errors

- [ ] top-level與choice embedded error都先於content處理？
- [ ] choices cardinality、finish/native finish、tool/refusal/length完整？
- [ ] invalid/mixed/fenced JSON不repair？
- [ ] stable error_type完整矩陣？
- [ ] safe message不含provider原文？

### Capture/privacy

- [ ] raw/routing/visible/error/catalog artifacts deterministic且scope正確？
- [ ] generation/request/upstream IDs、usage、cost無損？
- [ ] hidden reasoning text redacted？
- [ ] API key不進config/artifact/log/bundle？
- [ ] events/hash chain/manifest可重新驗證？

### Scope/gates

- [ ] production `app/`無eval import？
- [ ] 無migration、route、agent SDK、Responses Beta、fallback production logic？
- [ ] 原OpenAI adapter tests全綠？
- [ ] 真OpenRouter live run ID/hash已回報？
- [ ] 沒把conformance宣稱為品質通過？

任一項不滿足不得把V3-4R標complete。

---

## 20. 常見錯誤與立即停線條件

發現下列任一項立即停止、回文件裁決：

- 只改OpenAI adapter base URL；
- 用OpenRouter auto/latest/free alias跑gold；
- 未送metadata或看到metadata缺失仍算pass；
- fallback/attempt>1卻歸到同一model trial；
- account default plugin修改內容但bundle沒記；
- context compression刪掉中間對話仍做Evidence；
- response healing修過JSON卻宣稱model strict output成功；
- response cache hit當獨立trial；
- provider不支援schema時降級JSON mode／free text；
- 解析markdown fence或從混合文字擷取JSON；
- 把reasoning text存進Capture；
- 把generation ID塞進HTTP request ID欄；
- adapter依provider error message字串作主要分類，忽略error_type；
- SDK／transport暗中retry；
- 在DB transaction內做catalog或inference network call；
- live key缺失卻把slice標complete；
- 未過12-case就接Web或宣布AI顧問可上線。

---

## 21. 明確留到後續

### 21.1 OpenRouter Responses candidate

解除Beta或需求出現後，以同一request/schema/cases建立`OpenRouterResponsesCandidateAdapter`；比較：

- status/error資訊是否比Chat更完整；
- reasoning與structured output reliability；
- route metadata parity；
- latency/cost；
- breaking-change維護成本。

沒有可量收益不切換。

### 21.2 Official SDK candidate

SDK解除Beta後做transport parity，不動domain。必須能顯式零retry、注入mock transport、取得raw
headers/metadata、完整unknown fields並有async lifecycle；缺一不換。

### 21.3 Retry scheduling v2

正式production前設計：

- neutral `retry_after`提示如何version；
- outbox/scheduler何時重啟attempt；
- total operation deadline；
- jitter/backoff與max attempts；
- crash recovery；
- 429/503不在worker內長sleep。

### 21.4 Production routing

V6/V7依eval決定exact endpoint、same-model fallback、multi-model fallback、ZDR/data policy、cache與healing。
每次變更皆新config hash與canary，不由OpenRouter dashboard無聲改default。

### 21.5 Neutral query fields

若實務需要按upstream provider、generation ID、cost或router attempts查詢，提出
`ModelCallResult.v2`／attempt metadata與migration；V3-4R supporting artifacts先證明需求，不先加欄。

---

## 22. 實作者交付回報格式

交付必須逐項回報：

1. commit SHA與實際修改檔案；
2. HTTPX lock版本與是否新增dependency（預期沒有）；
3. exact live model canonical slug與upstream endpoint slug；
4. data collection/ZDR/reasoning profile與config hash；
5. model/endpoints snapshot hash；
6. mocked focused、OpenAI regression、neutral/PostgreSQL/full suite數量；
7. 429/500/timeout各transport call count證據；
8. exact outbound body/schema hash與forbidden key檢查；
9. success/refusal/length/embedded error/routing contamination/usage矩陣；
10. live run ID、manifest hash、generation ID、HTTP request ID；
11. requested/resolved model、configured endpoint slug、expected/selected provider name、strategy、
    attempt、pipeline；
12. token usage、cost與limitations；
13. local TurnInterpretOutput validation、artifact/event/hash-chain驗證；
14. secret/reasoning redaction檢查；
15. 尚未完成項與是否阻擋V3-5。

不得只回「OpenRouter接通」「JSON正常」或「測試通過」。本切片的價值是取得可歸因、可重播的
gateway證據，讓V3-5真正測AI專業顧問的分析能力，而不是再一次測到與上線不同的路徑。
