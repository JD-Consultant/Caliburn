# 實作級技術假設驗證(四項)

> 研究員紀錄。原則:只收官方一手文件(OpenRouter / promptfoo / OpenTelemetry / 模型廠官方)。
> 存取日期一律 **2026-07-13**(所列 URL 皆於此日經 WebFetch/WebSearch 取得)。
> 「不支援 / 查不到」也如實標明。

---

## 假設 1 — OpenRouter 對 prompt caching 的透傳

**結論:成立(部分,依 provider 而異)。** OpenRouter 官方明文支援跨 provider 的 prompt caching 透傳,
usage 會回報 cached tokens,計價按各 provider 的 cache read/write 倍率。但**不是所有 provider 都自動**,
Anthropic / Alibaba(以及 Gemini explicit)需要在 content block 上明確帶 `cache_control`。

### 官方證據

來源:`https://openrouter.ai/docs/guides/best-practices/prompt-caching`(存取 2026-07-13)

- **支援的 provider**:OpenAI、Anthropic、DeepSeek、Google Gemini、Grok(xAI)、Moonshot、Groq、Alibaba Qwen。
- **自動 vs 手動**:官方原文「Most providers automatically enable prompt caching, but note that some
  (see Alibaba and Anthropic below) require you to enable it on a per-message basis.」
  - 自動(免設定):OpenAI、DeepSeek、Grok、Moonshot、Groq。
  - 手動(要 `cache_control` breakpoint):**Anthropic、Alibaba**。
  - Gemini 2.5:同時支援 implicit(自動)與 explicit `cache_control` breakpoint。
- **usage 回報**:cache 指標在回應的 `usage.prompt_tokens_details` 底下:
  - `cached_tokens` = 從 cache 讀到的 tokens(cache hit)。
  - `cache_write_tokens` = 寫入 cache 的 tokens。
  - `cache_discount` = 此次 cache read 省下的金額(顯示折扣)。
- **計價(相對於原始 input 單價的倍率)**:
  - Cache read 折扣:DeepSeek 0.1x、Anthropic 0.1x、Gemini 0.25x、Moonshot 0.25x、Grok 0.25x、Groq 0.5x。
  - Cache write 加價:Anthropic 5-min TTL 1.25x、Anthropic 1-hour TTL 2x、Alibaba 1.25x;
    OpenAI 與 Grok 的 cache write「no cost」。
- **TTL**:Anthropic 預設 5 分鐘、可設 1 小時(`cache_control` 帶 `"ttl": "1h"`);
  Gemini 5 分鐘(不 refresh);Alibaba 5 分鐘;OpenAI explicit 最低 30 分鐘。
- **路由**:為提高 hit 率,OpenRouter 用 **provider sticky routing**,把後續請求黏到同一 provider endpoint
  (來源:`https://openrouter.ai/docs/guides/best-practices/prompt-caching`)。

### 對實作的具體指示

- **Anthropic(我們最可能的著作模型)走 OpenRouter 時**:必須沿用 Anthropic 原生語法,在訊息 content block 上
  自己放 `cache_control`,例如把大段固定 system / 範本標成:
  ```json
  {"type": "text", "text": "<長 system/黃金範本>",
   "cache_control": {"type": "ephemeral", "ttl": "1h"}}
  ```
  OpenRouter 會透傳給 Anthropic。**不放就完全不快取**(這是頭號踩雷)。
- 讀回省了多少:解析 `usage.prompt_tokens_details.cached_tokens` 與 `usage.cache_discount`。
- **替代方案**:若要更精細掌控 breakpoints / beta header,或省掉 OpenRouter 的一層,可直連 Anthropic;
  但就快取「有沒有生效」而言,經 OpenRouter 是官方支援的,不必為此直連。sticky routing 需注意:
  同一 conversation 要維持同 provider 才有 hit,避免用會打散路由的參數。

---

## 假設 2 — OpenRouter 對 tool calling / structured outputs / parallel tool calls 的支援面

**結論:成立。** `tools`、`tool_choice`、`parallel_tool_calls` 皆透傳;`response_format` json_schema `strict`
官方支援;provider 差異用 models 頁的 `supported_parameters` 過濾;路由層用 **`require_parameters: true`**
強制只路由到支援該參數的 provider。

### 官方證據

來源:`https://openrouter.ai/docs/guides/features/tool-calling`(存取 2026-07-13)

- 透傳參數:
  - `tools` — 工具定義陣列(OpenAI 相容格式)。
  - `tool_choice` — `auto`(預設)/ `none` / 指定某工具。
  - `parallel_tool_calls` — 布林,「Control whether multiple tools can be called simultaneously」,
    多數模型預設 true;設 false 則一次只請求一個工具。
- 查 provider 是否支援 tools:官方原文「You can find models that support tool calling by filtering on
  `openrouter.ai/models?supported_parameters=tools`」。

來源:`https://openrouter.ai/docs/guides/features/structured-outputs`(存取 2026-07-13)

- 官方原文:結構化輸出用 `response_format` 帶 `type: "json_schema"`,並「Always set `"strict": true`
  to ensure models follow the schema exactly」。
- 支援的 provider/模型:OpenAI(GPT-4o 起)、Google Gemini、Anthropic(Sonnet 4.5、Opus 4.1+)、
  多數 open-source 模型、Fireworks 全部模型。
- **保證路由到支援的 provider(三步)**:
  1. 在 models 頁確認該模型的 `supported_parameters`。
  2. 在 provider preferences 設 **`require_parameters: true`**(官方原文:「set `require_parameters: true`
     in your provider preferences」)。
  3. 請求帶上 `response_format` + `type: json_schema`。
- 不支援時:「the request will fail with an error indicating lack of support.」

### 對實作的具體指示

- 多輪訪談引擎若用 function-calling 收結構化答案,請求範例:
  ```json
  {
    "model": "anthropic/claude-...",
    "tools": [ /* OpenAI 格式 */ ],
    "tool_choice": "auto",
    "parallel_tool_calls": false,
    "provider": { "require_parameters": true }
  }
  ```
- 若要嚴格 JSON schema(而非 tool),用 `response_format`:
  ```json
  {
    "response_format": {
      "type": "json_schema",
      "json_schema": {
        "name": "interview_turn",
        "strict": true,
        "schema": { "type": "object", "properties": { /* ... */ },
                    "required": [ /* ... */ ], "additionalProperties": false }
      }
    },
    "provider": { "require_parameters": true }
  }
  ```
- **`require_parameters` 是 provider routing 旗標(放在 `provider` 物件),不是 tool 內的 `required`**
  (後者是 JSON schema 內指定必填欄位;兩者不同,別混)。搭配 `strict: true` + `additionalProperties: false`
  才有嚴格結構保證。
- provider 能力差異:一律以 `openrouter.ai/models?supported_parameters=tools`(或 `=structured_outputs` /
  `=response_format`)實查為準,別憑記憶假設某模型支援。

---

## 假設 3 — promptfoo 接自建 Python/FastAPI 引擎(考多輪訪談引擎)

**結論:成立。** promptfoo 官方同時支援 Python custom provider、HTTP provider(打 FastAPI)、
以及 **Simulated User provider** 專門評測多輪對話 agent;assertion 有 deterministic + model-graded(含 llm-rubric)
+ 自訂 python/javascript 斷言;GitHub Actions 有官方 action。

### 官方證據

**(a) Python custom provider** — `https://www.promptfoo.dev/docs/providers/python/`(存取 2026-07-13)

- 必要函式簽名:`def call_api(prompt: str, options: dict, context: dict) -> dict`。
- 回傳至少 `{"output": ...}`;可選 `tokenUsage`、`cost`、`error`。
- config 引用:`id: 'file://my_provider.py'`,底下 `config:` 傳自訂設定,腳本內 `options.get('config', {})` 讀。
- **多輪/stateful**:官方原文 Python provider 用「persistent worker processes」,腳本只在 worker 啟動時載入一次;
  多輪要保狀態時設 `workers: 1` 讓請求都進同一 worker。

**(b) HTTP provider(打 FastAPI)** — `https://www.promptfoo.dev/docs/providers/http/`(存取 2026-07-13)

- config:`url` / `method` / `headers` / `body`(body 用 `{{prompt}}` 等模板變數)。
- 解析回應:`transformResponse`(JS 表達式/函式/檔案,如 `json.output`);不給就預設當 JSON。
- **session/多輪**:官方提供「server-side session management」;用 `sessionParser` 從 header/body 抽 session id,
  後續以 `{{sessionId}}` 帶回;client 端可用 `transformVars` 注入 conversation id。
- 範例:
  ```yaml
  providers:
    - id: https
      config:
        url: 'http://localhost:8000/interview'
        method: 'POST'
        headers: { 'Content-Type': 'application/json' }
        body: { text: '{{prompt}}', session: '{{sessionId}}' }
        transformResponse: 'json.output'
  ```

**(c) Simulated User provider(評多輪訪談引擎的最佳姿勢)** —
`https://www.promptfoo.dev/docs/providers/simulated-user/`(存取 2026-07-13)

- 官方定位:測試「多輪對話 between an AI agent and a simulated user」,適合 chatbot / 虛擬助理。
- 機制原文:每一 turn「The simulated user's message is sent to the agent. The agent's response is sent back
  to the simulated user. The simulated user generates the next message based on their instructions.」
- 關鍵設定:`maxTurns`(初始訊息之後要模擬的**新** turn 數)、`instructions`(模擬使用者的 persona/行為模板)。
- 停止條件:達 `maxTurns`、或 agent 回應含 `###STOP###`、或出錯。
- 範例:
  ```yaml
  defaultTest:
    provider:
      id: 'promptfoo:simulated-user'
      config:
        maxTurns: 5
  tests:
    - vars:
        instructions: |
          你是一位資深 HR,正在被訪談以產出某職務說明書。
          你會逐步提供職責細節,但一開始講得含糊,要被追問才展開。
  ```
  搭配 `originalProvider` 指向你的引擎(前述 Python/HTTP provider),Simulated User 會逐輪驅動它。

**(d) Assertions** — `https://www.promptfoo.dev/docs/configuration/expected-outputs/`(存取 2026-07-13)

- Deterministic:`equals` `contains` `icontains` `regex` `starts-with` `contains-any` `contains-all`
  `is-json` `contains-json` `is-html` `is-sql` `javascript` `python` `webhook` `latency` `cost`
  `rouge-n` `bleu` `levenshtein` 等。
- Model-graded:`llm-rubric`、`g-eval`、`answer-relevance`、`context-faithfulness`、`factuality`、
  `model-graded-closedqa`、`select-best` 等。`llm-rubric` 用 LLM 依你給的 criteria 打分。
- 自訂 python assertion:回傳 `bool` / `float` / GradingResult(`{'pass':bool,'score':float,'reason':str}`)。
- 自訂 javascript assertion:`(output, {vars}) => ({pass, score, reason})`。

**(e) GitHub Actions** — `https://www.promptfoo.dev/docs/integrations/github-action/`(存取 2026-07-13)

- 官方 action:`promptfoo/promptfoo-action@v1`。PR 改動 prompts 時自動跑 before-vs-after 評測,
  把比對連結貼成 PR comment。
- 主要 inputs:`github-token`、`prompts`、`config`、`openai-api-key`(用別的 provider 時可選)、`cache-path`。

### 對實作的具體指示

- **推薦架構**:FastAPI 引擎起在 localhost →(1) 用 **HTTP provider** 當 target,搭 session 保多輪狀態;
  (2) 用 **Simulated User provider** 當「考官」逐輪驅動,`instructions` 放不同受訪者 persona;
  (3) 每個 test case 用 `llm-rubric`(對照黃金範本尺度)+ 少量 deterministic(`is-json`、必答欄位 `contains`)
  + 自訂 python assertion 做結構化評分。
- 若引擎邏輯重、要直接 in-process 呼叫,改用 Python provider + `workers: 1` 保狀態;否則 HTTP provider 較乾淨
  (引擎照常獨立跑,符合本 repo hexagonal 邊界)。
- CI:`promptfoo/promptfoo-action@v1`,PR 改動 prompt/引擎時自動評測並貼 PR comment。

---

## 假設 4 — OpenTelemetry GenAI 的 Python 落地現況

**結論:部分成立(標準仍 Development/experimental,套件仍 beta)。** GenAI semconv 屬性已定義且穩定命名,
但整個 `gen_ai.*` namespace 仍標為 **Development**(前稱 experimental),未 stable;Python 的 auto-instrument
套件(openai-v2、google-genai、vertexai、openai-agents-v2)全在 opentelemetry-python-contrib 的
`instrumentation-genai`,狀態皆 development / beta。手動埋 `gen_ai.*` span 是目前對「自建 LLM 呼叫」最穩的姿勢。

### 官方證據

**(a) semconv 屬性(client 層)** —
`https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/`(存取 2026-07-13)
(註:舊頁 `.../gen-ai/gen-ai-spans/` 已標「moved / no longer maintained」,內容遷至 GenAI semconv 專屬 repo。)

- 現行 `gen_ai.*` 屬性(皆標 **Development** stability):
  - `gen_ai.operation.name`(如 `chat` / `embeddings` / `text_completion`)
  - `gen_ai.provider.name`(識別 provider;**取代已 deprecated 的 `gen_ai.system`**)
  - `gen_ai.request.model`、`gen_ai.request.temperature`、`gen_ai.request.max_tokens`
  - `gen_ai.response.id`、`gen_ai.response.model`、`gen_ai.response.finish_reasons`
  - `gen_ai.usage.input_tokens`、`gen_ai.usage.output_tokens`
  - `gen_ai.conversation.id`(session/thread 識別)
  - `gen_ai.output.type`(`text` / `json` / `image` / `speech`)
  - `gen_ai.input.messages`、`gen_ai.output.messages`(內容擷取,含敏感資料,預設不記)
- **重要 deprecation**:官方原文「`gen_ai.system` has been superseded by `gen_ai.provider.name`」——
  新碼一律用 `gen_ai.provider.name`。
- span 命名慣例:`{gen_ai.operation.name} {gen_ai.request.model}`(如 `chat claude-...`)。
- 內容擷取:預設**不**記 prompt/tool 內容(可能含敏感資料),要靠環境變數開啟。

**(b) Python 落地套件** — opentelemetry-python-contrib `instrumentation-genai`
(`https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai`,
PyPI 對應頁,存取 2026-07-13):

- `opentelemetry-instrumentation-openai-v2`(openai>=1.26,狀態 development;PyPI 最新為 2.x beta)
- `opentelemetry-instrumentation-google-genai`(google-genai>=1.0,development;官方自陳「still experimental
  … may not be complete or correct」,附 TODOS.md)
- `opentelemetry-instrumentation-vertexai`(development)
- `opentelemetry-instrumentation-openai-agents-v2`(openai-agents>=0.3.3,development;正被遷至
  `opentelemetry-python-genai` 新 repo)
- **沒有** Anthropic 官方 Python auto-instrumentation 套件(semconv 有 Anthropic 專節,但 contrib 未提供
  對應 `opentelemetry-instrumentation-anthropic`)。

**(c) FastAPI zero-code** — `https://opentelemetry.io/docs/zero-code/python/`(存取 2026-07-13):
講 `opentelemetry-distro` + `opentelemetry-bootstrap -a install` 的 monkey-patch auto-instrument;
**該頁不涵蓋 GenAI**,FastAPI 有獨立的 web 框架 instrumentation(`opentelemetry-instrumentation-fastapi`)。

### 對實作的具體指示

- **姿勢建議(FastAPI + 自建 LLM 呼叫,且我們主走 Anthropic/OpenRouter)**:
  - Web 層:用 `opentelemetry-instrumentation-fastapi`(auto)拿 HTTP server span,穩定可用。
  - LLM 呼叫層:因為我們是自建呼叫 + 走 OpenRouter(非直用 openai SDK 的原生路徑),
    **手動埋 `gen_ai.*` span 最可靠**——不要指望 auto-instrument 能認得經 OpenRouter 的呼叫。
- 手動 span 最小屬性集(依現行 semconv):
  ```python
  with tracer.start_as_current_span(f"chat {model}") as span:
      span.set_attribute("gen_ai.operation.name", "chat")
      span.set_attribute("gen_ai.provider.name", "openrouter")  # 或實際上游 provider
      span.set_attribute("gen_ai.request.model", model)
      span.set_attribute("gen_ai.request.temperature", temperature)
      span.set_attribute("gen_ai.conversation.id", session_id)   # 多輪訪談串起來
      # ... 呼叫 ...
      span.set_attribute("gen_ai.response.model", resp_model)
      span.set_attribute("gen_ai.response.finish_reasons", [finish_reason])
      span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
      span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
  ```
- 內容(input/output messages)預設不記;要記需自行決定並注意多租戶資料隔離(本 repo 是 B2B 隔離,格外小心)。
- 標準仍 Development:命名可依現行 semconv,但**預期未來會變**,把屬性設定收斂到一個 helper,別散落各處。
- **不要為了 GenAI observability 而把 openai/torch 之類重依賴放進 app 進程**(呼應 ADR 0012 的環境禁令);
  手動埋 span 只需 `opentelemetry-api/sdk`,無此風險。

---

## 來源總表(全部存取日 2026-07-13)

| # | 主題 | URL |
|---|------|-----|
| 1 | OpenRouter Prompt Caching(provider 支援/usage/計價/TTL) | https://openrouter.ai/docs/guides/best-practices/prompt-caching |
| 2 | OpenRouter Tool & Function Calling(tools/tool_choice/parallel_tool_calls) | https://openrouter.ai/docs/guides/features/tool-calling |
| 2 | OpenRouter Structured Outputs(response_format json_schema strict / require_parameters) | https://openrouter.ai/docs/guides/features/structured-outputs |
| 2 | OpenRouter models 能力過濾 | https://openrouter.ai/models?supported_parameters=tools |
| 3 | promptfoo Python provider | https://www.promptfoo.dev/docs/providers/python/ |
| 3 | promptfoo HTTP provider | https://www.promptfoo.dev/docs/providers/http/ |
| 3 | promptfoo Simulated User provider(多輪) | https://www.promptfoo.dev/docs/providers/simulated-user/ |
| 3 | promptfoo Assertions & Metrics | https://www.promptfoo.dev/docs/configuration/expected-outputs/ |
| 3 | promptfoo llm-rubric | https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/ |
| 3 | promptfoo GitHub Action | https://www.promptfoo.dev/docs/integrations/github-action/ |
| 4 | OTel GenAI 屬性 registry | https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/ |
| 4 | OTel GenAI spans(已遷移通知頁) | https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/ |
| 4 | OTel Python contrib instrumentation-genai | https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai |
| 4 | OTel Python zero-code(FastAPI auto-instrument) | https://opentelemetry.io/docs/zero-code/python/ |
