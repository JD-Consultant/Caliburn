# LLM provider interface 與 framework 選型研究

> **歷史選型研究，已被取代（2026-08-28）**：本文「不採 LangChain／LangGraph、保留薄自有 port」的結論已由 [Accepted ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) 與後續 0061–0068 取代。下一版產品語意與施工以 [Proposed ADR 0071](../adr/0071-revisable-work-understanding-context-and-review-provenance.md) 及 [2026-08-28 實作計畫](../superpowers/plans/2026-08-28-consultant-work-understanding-and-workspace-implementation.md) 為準。本文只保留 provider capability／routing 研究脈絡，不得用來恢復舊 adapter-first 架構。

- 日期：2026-08-11
- 狀態：研究結論，尚未形成 ADR
- 範圍：模型替換、generation 參數、結構化輸出、provider 差異、retry/fallback、可觀測性
- 目標：保留目前 Task Analysis 的證據、驗證與一次請求邊界，同時讓日後能換模型或 provider

## 1. 現況與問題

目前 `apps/api` 的 LLM seam 是一個直接使用 `httpx` 的 `OpenRouterAdapter`：

- `app/api/deps.py` 直接建構 `OpenRouterAdapter`；設定可改 `job_analysis_model`、`job_analysis_provider`、輸出上限與 timeout。
- adapter 固定使用 Chat Completions、JSON Schema response format、`require_parameters=true`、單一 provider order、`allow_fallbacks=false`。
- adapter 不自動 retry；結果會區分 timeout、連線、HTTP/provider error、拒絕、截斷、格式錯誤與 model mismatch。
- 應用層仍負責 proposal、identity gate、semantic verifier 與 employee decision；LLM 輸出不是 Current State 的真相。

因此要解的是「可替換 provider/model 的受控 seam」，不是把整個 application 改成 agent framework。若框架隱藏 retry、fallback、schema strategy 或實際 model，會削弱目前的品質歸因與證據鏈。

## 2. 權威資料的共同結論

主流 provider 都有一組可共用的基本參數，但能力並不完全相同：

- OpenAI 將模型選擇、reasoning effort、verbosity、context、token/cost、latency 與 task success 放進模型評估，而不是只看「能否呼叫」。官方目前建議 reasoning/tool/multi-turn 場景使用 Responses API。
- Anthropic 的 structured outputs 使用 provider 自己的 `output_config.format`，schema 仍有複雜度限制；拒絕或 `max_tokens` 截斷可能以正常 HTTP 200 回來，不能只依賴 JSON parse。
- Gemini 把 `temperature`、`topP`、`seed`、`thinkingLevel`、`maxOutputTokens` 放在 generation config，但明確說不是每個模型都支援每個參數；JSON Schema 也是支援子集。
- AWS Bedrock Converse 提供跨模型的共同 message/inference API，模型特有欄位放在 `additionalModelRequestFields`，即「共同子集 + provider/model escape hatch」。
- OpenRouter 的 Models API 提供 `supported_parameters`、context、pricing 與 endpoint metadata；provider routing 另有 `require_parameters`、fallback 與 provider order。這證明 capability/profile 和 routing policy 應分開，而不能盲送參數。

結論：通用介面應採「小而明確的 common subset + 可驗證的 capability profile + 受控 provider-specific options」，不應追求一個假設所有模型都相同的 `dict[str, Any]`。

## 3. Framework 比較

| 選項 | 強項 | 與目前 Caliburn 的衝突 | 判斷 |
|---|---|---|---|
| 薄型自有 port + provider adapters | 完全掌控 wire request、retry、fallback、raw evidence、verifier；最容易維持一次請求 | 需要自己維護 adapters、capability checks、conformance tests | **目前採用** |
| PydanticAI | Python/Pydantic 原生；有 provider/model profile、structured output、model fallback；可用 `direct.model_request` 做單次呼叫 | 仍可能帶入 provider SDK retry、profile/structured-output strategy 差異；必須明確關閉或驗證 hidden retry | **日後若要框架，首選；先包在 adapter 後面** |
| LiteLLM | 大量 provider 統一格式、Router、fallback、budget/spend、Proxy gateway | Router 的 retry/fallback 和正規化可能隱藏實際執行 provider；與目前「無隱藏 fallback、可歸因」要求衝突 | 只有多 provider gateway、集中預算/路由成為主要需求時再考慮 |
| LangChain / LangGraph | provider 統一介面、runtime model/configurable fields、tools、structured output、agent orchestration | 範圍過大；官方 model 呼叫預設可 retry（目前文件列出 `max_retries=6`）；LangGraph 與本 repo 已退場的舊路徑有架構慣性風險 | **目前不採用** |
| Vercel AI SDK | TypeScript provider abstraction、registry、fallback、model settings；很適合 Web/TS AI 產品 | 現行 LLM seam 在 Python API；引入它會把 domain LLM 移到 Web 或增加第二套 runtime | **目前不採用** |
| OpenAI Agents SDK | 適合 agent/tool loop、handoff、tracing | 現行 Task Analysis 是一次受控 structured operation，不是 agent loop；會擴大問題範圍 | **目前不需要** |

## 4. 建議的目標 seam（研究提案，非已核准 API）

### 4.1 分離 selection、capability 與 execution

1. `ModelSelection`：部署設定選擇 provider、精確 model、endpoint/region；可有 `quality`、`latency`、`cheap` 這種應用 profile，但 resolver 必須最後落到 pinned exact model。
2. `ModelProfile`：記錄精確 model/provider、context/output limit、structured output、reasoning、tools、multimodal 及支援的參數；來源與 snapshot time 一起保留。
3. `LlmRequest`：由 application 產生 operation、messages/context、generation policy、output schema 與 correlation metadata；Web 使用者不能任意改 provider options。
4. `LlmPort.complete()`：回傳 typed response/failure；provider adapter 只負責 transport、provider translation、結果解析與執行證據。

### 4.2 Common settings 與 escape hatch

共用欄位只保留跨 provider 有清楚語義的項目，例如：

- `max_output_tokens`
- 明確允許時才傳的 `temperature`、`top_p`、`stop_sequences`
- `reasoning`/thinking level（由 profile 先確認支援）
- `timeout` 與 output mode（text / JSON Schema）

provider-specific 欄位只能進 adapter-owned `provider_options`，並遵守：

- capability 明確支援才送；
- 必要能力不存在就 fail closed；
- 非必要欄位不能靜默丟棄，至少要產生 warning 並進 execution evidence；
- structured output 由各 adapter 翻譯，回來仍用原始 schema 做 deterministic validation 與 domain verifier。

### 4.3 Response、錯誤與 policy

Response 至少應保留 requested model、resolved model/provider/endpoint、request id、finish reason、input/output/reasoning/cache tokens、latency、warnings 與 provider cost（若有）。raw provider metadata 放在 evidence/capture，不直接成為 domain truth。

錯誤應有跨 provider 的 typed taxonomy：`timeout`、`connection`、`rate_limited`、`auth`、`invalid_request`、`unsupported_capability`、`model_not_found`、`provider_error`、`malformed_response`、`refusal`、`truncated`、`model_mismatch`。

retry/fallback 不應由低層 adapter 偷做，而由 application policy 明確決定。對目前高品質 Task Analysis operation，預設仍是一次請求、無 fallback；拒絕、截斷、schema/semantic verifier 失敗也不應無條件重試。若日後加入 retry，必須有 idempotency、attempt evidence、上限與 eval 證明。

可觀測性可對齊 OpenTelemetry GenAI semantic conventions：`gen_ai.request.model`、`gen_ai.response.model`、`gen_ai.provider.name`、token usage、output type、latency、finish reason、error 與 cost；預設不記 prompt/content。

## 5. 建議採用順序

### 現在

不引入大型 framework。先把目前 OpenRouter adapter 的 provider-neutral types 從 OpenRouter 命名中抽出，保留現有行為與測試：一次 HTTP、無 hidden retry/fallback、JSON schema、結果分類、execution evidence。這是 seam refactor，不是重寫 LLM 流程。

### 下一階段

1. 加入 validated `ModelSelection`、`ModelProfile` 與 capability check。
2. 把 OpenRouter-specific request/response translation 留在 `adapters/openrouter`。
3. 增加 adapter conformance tests：同一份 application request、unsupported parameter、structured output、refusal、truncation、resolved model 與 evidence。
4. 只有在第二個 provider 有真實需求與測試 fixture 後，才新增第二個 adapter；不要先做空泛 registry。
5. 若確實需要 Python framework，再以 PydanticAI 做 adapter 內部實驗，使用單次 `direct.model_request`，明確設定 zero hidden retries，並和現有 direct-http adapter 做 wire/evidence/eval 對照。
6. LiteLLM 只有在需要集中 gateway、預算、跨應用 routing 或營運 fallback 時才引入；那會是部署架構決策，應另開 ADR。

## 6. 最終建議

**目前不要用框架取代 LLM 核心 seam；採用薄型自有 port + provider adapters。**

**若一定要選一個 Python 框架，選 PydanticAI，但只放在 adapter 邊界內，不能讓它接管 application policy、evidence、verifier 或 retry/fallback。** 它的 model profile 與 Pydantic 結構化輸出最貼近現況；但它不是現在就值得承擔的必要依賴。

這個結論尚未授權實作。要開始改造時，應先把本研究轉成 Proposed ADR 與 bite-size plan；模型替換也要用代表性職務資料重跑品質、完整性、evidence linkage、token/cost 與 latency eval，而不是只確認 API 回 200。

## 7. 來源

官方 provider / gateway：

- [OpenAI — Latest model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Anthropic — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Google — Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Google — Generate Content API reference](https://ai.google.dev/api/generate-content)
- [AWS — Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [OpenRouter — Models API](https://openrouter.ai/docs/guides/overview/models)
- [OpenRouter — Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)

框架 / runtime：

- [PydanticAI — Models](https://pydantic.dev/docs/ai/models/overview/)
- [PydanticAI — Model profiles](https://pydantic.dev/docs/ai/api/pydantic-ai/profiles/)
- [Vercel AI SDK — Provider management](https://ai-sdk.dev/docs/ai-sdk-core/provider-management)
- [LiteLLM — Getting started](https://docs.litellm.ai/)
- [LangChain — Models](https://docs.langchain.com/oss/python/langchain/models)
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [OpenTelemetry — GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)

本 repo 相關現況與既有決策：

- [`apps/api/app/adapters/openrouter/openrouter.py`](../../apps/api/app/adapters/openrouter/openrouter.py)
- [`apps/api/app/api/deps.py`](../../apps/api/app/api/deps.py)
- [`docs/adr/0040-task-analysis-llm-architecture.md`](../adr/0040-task-analysis-llm-architecture.md)
- [`docs/specs/2026-07-31-job-analysis-openrouter-attribution-and-live-smoke-research.md`](2026-07-31-job-analysis-openrouter-attribution-and-live-smoke-research.md)
- [`docs/contract-strategy.md`](../contract-strategy.md)
