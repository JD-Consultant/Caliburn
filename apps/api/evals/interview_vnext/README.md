# Interview vNext — eval-only provider adapters

**Status（2026-07-17）：OpenRouter-first V3-4R mocked complete；OpenRouter live gate pending**

- OpenRouter mocked suite:`test_interview_vnext_openrouter_model_catalog.py`(48)+
  `test_interview_vnext_openrouter_eval_adapter.py`(86)+ `test_interview_vnext_openrouter_live_probe.py`(8)。
- OpenAI direct reference regression 保持全綠:`test_interview_vnext_openai_eval_adapter.py` +
  `test_interview_vnext_openai_live_probe.py`。
- **OpenRouter live gate(§15.5)尚未執行**:沒有 `OPENROUTER_API_KEY`,狀態為
  `mocked complete, OpenRouter live gate pending`;跑通後才進 V3-5。
- OpenAI direct live gate(舊規格§16.5)保留為 optional GPT direct comparison,不阻擋 V3-5(ADR 0035)。
- OpenRouter 上的 Claude／GPT／Gemini 共用這個 gateway adapter;只有官方直連才各自做 OpenAI／Anthropic／
  Google adapter。V3-4R 先不接 production route,後續 promotion 移動同一實作(§16.5),不複製第二份。
- **provider metadata 待核**:`openrouter_metadata.endpoints` 條目巢狀由 live capture bundle 定案
  (見 tests fixtures README);adapter 目前同時容忍 flat / `available` 兩種 shape。

本目錄是 ADR 0034 vNext 的 **eval-only** 邊界:驗證「官方 provider API 真實 shape 能否無損映射到
V2/V3 已發布的 provider-neutral contract(`app.interview_vnext.llm`)」。

- OpenRouter主線權威規格：
  `docs/plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md`。
- OpenAI direct reference規格：
  `docs/plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md`。
- **production `apps/api/app/` 不得 import 本目錄**;dependency guard 測試強制。
- 這裡沒有品質評測:V3-4 只做 adapter conformance;12-case 品質/多 trial 是 V3-5。

## 檔案

| 檔案 | 責任 |
|---|---|
| `schema_catalog.py` | `output_schema_id + hash` → exact published portable schema 的封閉映射(`format_name` 中性,OpenAI/OpenRouter 共用) |
| `openrouter_provider_config.py` | secret-free OpenRouter 主線 profile(exact model/endpoint、route/plugin/reasoning/privacy hard invariants、config hash);唯一建構路徑 `build_openrouter_eval_config()` 由 snapshot 派生 |
| `openrouter_model_catalog.py` | model/endpoints GET client + immutable snapshot + §6.2 preflight(canonical slug、capability、唯一 base-slug endpoint、endpoint-level 能力);無 inference |
| `providers/openrouter_chat.py` | **OpenRouter 主線**:`POST /chat/completions` 的 exact request、single-call/deadline、response/error/routing normalization、raw/routing/visible/error artifacts |
| `openrouter_live_probe.py` | opt-in 單次 OpenRouter live conformance probe + immutable Capture bundle(catalog 與 inference 分離) |
| `provider_config.py` | (reference)secret-free OpenAI Responses profile + config hash |
| `providers/openai_responses.py` | (reference)`AsyncOpenAI.responses.create()` 的 request/response/error normalization |
| `live_probe.py` | (reference)opt-in OpenAI 單次 live probe + bundle |
| `probes/*.json` | synthetic test-only probe 輸入(OpenAI / OpenRouter identity 各自獨立) |

## 不變量(摘錄;完整見規格 §1)

OpenRouter 主線(V3-4R):

- 直接 `httpx` 打 `POST https://openrouter.ai/api/v1/chat/completions`;**不新增 Beta SDK**、不 follow redirect、
  transport/adapter 皆零 retry——一個 durable attempt 恰好一次 inference POST。
- exact canonical model + exact upstream endpoint;`allow_fallbacks=false`、`require_parameters=true`、
  `stream=false`、單一 choice、無 tools;禁 auto/free/latest/nitro/floor/online alias。
- `X-OpenRouter-Metadata: enabled` 為 hard invariant;metadata 缺失、strategy 非 direct、attempt≠1、
  selected provider/model 與 snapshot 不符、或任何 pipeline stage → route contaminated(fail closed)。
- known mutating plugins(context-compression、response-healing、web、file-parser)顯式 disabled;
  不解析 markdown fence、不修 JSON、不降級 JSON mode;reasoning text 一律 redact,不進 Capture。
- 送出的 schema 是 V3-2 published portable schema(hash 驗證);adapter 成功只到 `StructuredPayload`,
  完整 Pydantic/semantic 驗證仍在既有 V3-3 executor。

OpenAI direct(reference):

- `openai==2.46.0`、`max_retries=0`;`store/background/stream=false`、`truncation=disabled`;
  typed traversal 全部 `response.output` items,禁 `output[0]`／`output_text` 串接。

## 驗收命令

```powershell
cd apps/api
# OpenRouter 主線 focused
uv run --locked pytest -q `
  tests/test_interview_vnext_openrouter_model_catalog.py `
  tests/test_interview_vnext_openrouter_eval_adapter.py `
  tests/test_interview_vnext_openrouter_live_probe.py
# OpenAI direct reference regression
uv run --locked pytest -q `
  tests/test_interview_vnext_openai_eval_adapter.py `
  tests/test_interview_vnext_openai_live_probe.py
```

OpenRouter live gate(需 `OPENROUTER_API_KEY`;主線 gate,無 default model/endpoint):

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

無 key:exit 2、不建 run、不打 network。輸出 bundle 已 gitignore(`output/`)。

Optional direct OpenAI probe（需`OPENAI_API_KEY`；不再是主線gate）：

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

無 key:exit 2、不建 run、不打 network。輸出 bundle 已 gitignore(`output/`),不進 Git。
