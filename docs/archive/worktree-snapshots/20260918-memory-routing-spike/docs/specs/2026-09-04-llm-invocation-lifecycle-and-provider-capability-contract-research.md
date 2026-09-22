# LLM 呼叫生命週期與 Provider 能力契約研究

- 日期：2026-09-04
- Topic ID：`LLM-Q001`
- 狀態：`WORKING`；Product Owner 已核准方案 B、G4 與 dependency 方案 A；isolated dependency preflight PASS，G5 capability contract tests 尚未施工
- 性質：架構研究；不是 ADR、施工計畫或 production 授權
- 上游事件：`MEM-Q004` live trial revision 3 在第一個 Luna model response 前被 provider routing 拒絕
- 跨家證據：[`LLM Tool Loop 與 Runtime 責任：跨家官方證據附錄`](2026-09-04-llm-tool-loop-and-runtime-responsibility-cross-vendor-evidence.md)

## 1. 本輪 preflight

```text
Topic ID: LLM-Q001
Current stage: G5 dependency preflight PASS；final baseline frozen
Binding decisions:
  - Production 仍受現行 code、AGENTS.md 與 Accepted ADR 0060 約束。
  - 產品仍是一位專業顧問；框架與 provider 不得改變產品語意。
  - MEM-Q004 維持 FAIL_UNPROVEN；不授權 revision 4。
This turn's only blocking question:
  是否授權依 §9.4～§9.6 實作零付費 G5 capability contract tests？
Already reviewed evidence:
  OpenAI Responses／Agents SDK、Anthropic Messages／Tool Runner／native structured output、
  Google Gemini／ADK、OpenRouter routing／metadata、LangChain／LangGraph、PyPI metadata、
  uv resolver、dependency baseline regression，以及 MEM-Q004 revision 3 的真實 404 receipt 與 frozen payload。
Out of scope / parking lot:
  Memory 資料結構與 revision 4、JD 編輯器、RAG、UI、模型品質比較、
  production 施工、framework 翻案、merge、push。
```

## 2. 要解決的產品問題

員工送出一輪訪談後，系統應可靠地啟動**同一位顧問的一次有界 run**：

1. 只把所選 model／provider 真正支援且本輪需要的 request 送出去；
2. Tool 與結構化輸出可被模型正確使用，也由 Runtime 驗證；
3. 暫時性錯誤可在明確上限內恢復，設定或能力錯誤不浪費重試與費用；
4. 成功、失敗、實際 model／provider、tokens、費用與路由原因可追查；
5. provider 失敗不偽裝成 Memory、顧問分析或員工輸入錯誤。

本題不先決定 Memory 或 JD 如何運作。它只建立所有 model-bearing 功能都能共用的可靠呼叫入口。

## 3. 觸發本題的真實證據

`MEM-Q004` revision 3 的 Store 與三次 embedding 均成功；第一個 Luna chat invocation 在任何
model response／tool call 前收到 OpenRouter 404。凍結的 payload 同時送出：

- `parallel_tool_calls: false`；
- `provider.require_parameters: true`；
- exact Luna model、strict tools、reasoning 與 output-token cap。

OpenRouter 公開資料當時列出的七個 Luna endpoint 都沒有宣告 `parallel_tool_calls`；而官方明定
`require_parameters: true` 會在 routing 前排除不支援 request 中任一參數的 endpoint。因此這次
失敗反證的是**目前 request compilation／capability routing 契約**，不是 Memory 語意、Luna
品質或 Tool schema。

完整 receipt 與診斷見[實驗報告 §10](../experiments/2026-09-03-memory-routing-canonical-read/report.md#10-trial-revision-3-實際結果)。

## 4. 官方事實

以下只記會改變本題方案的直接官方事實；沒有把廠商未公開的內部架構當成事實。

### 4.1 OpenAI

- **Official fact：**OpenAI 對 GPT-5.6 的目前建議是使用 Responses API 處理 reasoning、Tool calling
  與 multi-turn；reasoning effort 應依代表性工作量比較品質、延遲與成本，而不是一律選最高。
- **Official fact：**Function calling 以 `call_id` 關聯 tool call 與 tool output；`strict: true` 可保證
  參數符合受支援的 JSON Schema 子集。OpenAI 建議 strict mode，但其 schema 有明確限制。
- **Official fact：**OpenAI 的 `parallel_tool_calls: false` 是 Responses／Chat Completions wire
  control，可限制一個 model turn 最多零或一次 function call。
- **Official fact：**OpenAI Agents SDK 將 provider 選擇放在 model／run boundary，支援自訂
  `ModelProvider` 與第三方 adapter；官方明確提醒非 OpenAI provider 的 Responses 支援與功能差異
  必須實際驗證，並提供 `strict_feature_validation` 讓不支援的能力 fail fast，而不是靜默忽略。
- **Official fact：**Agents SDK 的 runner-managed model retry 是 opt-in，且只有在尚未收到 response
  event、符合 replay-safety 時才重送。

直接來源：

- [OpenAI — GPT-5.6 Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Agents SDK — Models and providers](https://openai.github.io/openai-agents-python/models/)

### 4.2 Anthropic

- **Official fact：**Claude 可能在同一 response 產生多個 `tool_use`；Runtime 應依 Tool 語意決定
  concurrent 或 sequential。獨立 read 通常可平行；共享狀態、有副作用或具順序依賴的 Tool 應循序。
- **Official fact：**Anthropic 關閉平行 Tool 的 wire control 不是 OpenAI 的頂層欄位，而是
  `tool_choice.disable_parallel_tool_use`。每個結果以 `tool_use_id` 對應原 call；未執行的 call 也要
  回傳 `is_error: true`，讓模型知道並可在下一輪修正。
- **Official fact：**Anthropic 建議多數應用使用 SDK Tool Runner 處理 Tool loop、message history、結果
  格式與錯誤包裝，並以 `max_iterations` 限制；只有需要自訂 batching、retry、HITL 或錯誤行為時才接管。
- **Official fact：**`strict: true` 使用 grammar-constrained sampling 保證 Tool input 符合其支援的
  JSON Schema；複雜工具可附 schema-valid input examples，但 examples 會增加 prompt tokens。
- **Official fact：**Claude 現在另有原生 JSON output `output_config.format`，可與 strict Tool 在同一
  request 使用；舊 beta `output_format` wire 只在過渡期相容。SDK 可先把 provider 不支援的 schema
  constraint 簡化，再以原始 Pydantic／Zod 類型作 local validation。
- **Official fact：**API 錯誤有 typed exception、HTTP 類別與 request ID。404 是資源／設定錯誤；
  500 應 exponential backoff；SDK 對暫時性錯誤預設重試，因此若外層 Runtime 也重試，必須避免
  疊成兩套未知 attempt budget。

直接來源：

- [Anthropic — Parallel tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)
- [Anthropic — Tool Runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [Anthropic — Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
- [Anthropic — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic — API errors](https://platform.claude.com/docs/en/api/errors)

### 4.3 OpenRouter

- **Official fact：**OpenRouter 的 `provider.only`／`order`／`allow_fallbacks` 控制路由；
  `require_parameters: true` 只保留支援 request 中**所有已提供參數**的 endpoint。若沒有候選，request
  可在到達模型前失敗。
- **Official fact：**model catalog 可列 model-level `supported_parameters`，endpoint API 可列出實際
  provider endpoints；因此 model 名稱存在不等於特定 request 一定可路由。
- **Official fact：**opt-in `X-OpenRouter-Metadata: enabled` 可在成功與多數錯誤回傳 routing snapshot。
  `attempt: 0` 代表 request 未到 provider，常見原因正是所有候選被 routing filters 排除。metadata
  是 additive，client 應忽略未知欄位。
- **Official fact：**OpenRouter 是相容層，不會讓不同原生 API 的每項能力自動變成完全相同的 wire
  contract；其 routing 與 supported-parameter 資料本身也是呼叫前 capability evidence 的一部分。
- **Official fact：**即使 `require_parameters: false`，OpenRouter 目前仍把 `tools`、`response_format` 與
  `verbosity` 當作同模型 endpoints 間的 soft preference；若沒有 endpoint 宣告支援，仍可能路由並忽略
  該參數。因此 soft preference 不能代替 required-outcome preflight。

直接來源：

- [OpenRouter — Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter — Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
- [OpenRouter — Router metadata](https://openrouter.ai/docs/guides/features/router-metadata)
- [OpenRouter — Models and supported parameters](https://openrouter.ai/docs/guides/overview/models)
- [OpenRouter — List endpoints for a model](https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints)

### 4.4 LangChain／LangGraph runtime

- **Official fact：**LangChain 提供跨 provider 的標準 model／message／Tool interface；provider integration
  仍負責 provider-specific 能力與參數。官方對 OpenRouter 建議使用專用 `ChatOpenRouter` integration。
- **Official fact：**`create_agent` 可由 agent loop 執行 Tool call／result 循環；middleware 可處理 call
  limit、retry、fallback、logging、summarization 與 HITL，不必重新手寫整個 harness。
- **Official fact：**原生結構化輸出可用 `ProviderStrategy`，不支援時可用 `ToolStrategy`；同時使用 Tool
  與 structured output 時，所選 model/provider 必須支援兩者。LangChain 可依 model profile 選策略，
  但 profile 是 beta，官方允許資料缺漏、過時或錯誤時 override，因此不能把它當唯一真相。
- **Official fact：**Model／Tool retry middleware 支援 typed predicate、有界 backoff 與明確失敗行為；
  Tool validation error 可轉成受控 `ToolMessage` 讓模型修正，而不是把 raw exception 全部洩露給模型。

直接來源：

- [LangChain — Models and model profiles](https://docs.langchain.com/oss/python/langchain/models)
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain — Middleware overview](https://docs.langchain.com/oss/python/langchain/middleware/overview)
- [LangChain — Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain — ChatOpenRouter integration](https://docs.langchain.com/oss/python/integrations/chat/openrouter)

### 4.5 Google Gemini／ADK（三角驗證）

- **Official fact：**Gemini custom function calling 同樣由模型回傳 function name／arguments／ID，
  application 執行後再送回 matching function response；模型不直接執行 application code。
- **Official fact：**Gemini 把 Function Calling 與 Structured Output 視為不同用途；前者做中間動作，
  後者約束 final response，application 仍應驗證語意值。
- **Official fact：**ADK Runtime Runner 負責驅動 event loop、提交 session state 與向上游送事件；
  agent／Tool／callback 負責實際計算與決策。Session 保存一條 conversation thread 的事件與狀態。
- **Official fact：**ADK 可在 action 前要求 confirmation 並暫停／恢復；觸發政策仍由 application 定義。

直接來源：

- [Google Gemini — Using tools](https://ai.google.dev/gemini-api/docs/tools)
- [Google Gemini — Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Google ADK — Runtime event loop](https://adk.dev/runtime/event-loop/)
- [Google ADK — Session](https://adk.dev/sessions/session/)
- [Google ADK — Action confirmations](https://adk.dev/tools-custom/confirmation/)

## 5. 跨家共同做法與不可假裝相同的部分

### 5.1 共同做法

以下是由多份官方 API／SDK 契約共同支持的 **Inference**，不是任何一家官方原句：

1. **產品要求與 provider payload 分層。**應先描述本輪要達成的結果與政策，再由 adapter 轉成所選
   provider 的 wire fields；不能把某一家欄位假裝成所有家的通用語意。
2. **呼叫前做能力解析。**對已知的 model、provider endpoint、API surface、Tool、structured output
   與必要參數不相容，應在 paid inference 前 fail。官方 metadata 仍可能缺漏；未知必須明列，再以
   不付費 contract test 或最小 bounded characterization 回答，不能假裝呼叫前能知道全部能力。
3. **原生約束優先，Runtime 仍驗證。**可用 strict Tool／native structured output 時使用；Runtime
   仍負責 business invariant、Tool result 與最終 effects 驗證。
4. **優先使用成熟 runtime 的 Tool loop。**模型提出 call、Runtime 執行、以 call ID 回傳結果；平行或
   循序由 Tool 副作用與依賴決定，不由一個跨 provider raw boolean 代表全部語意。只有成熟 Runner
   無法表達已證明必要的控制時才接管 loop；手寫 canonical loop 仍是各家正式支援路徑。
5. **Retry 必須形成一個可證明的有效總預算。**只重試 typed transient 且 replay-safe 的 failures；
   設定、schema、authentication、capability mismatch 與一般 4xx 不應盲目重試。哪一層執行 retry 是
   Caliburn mapping，不是跨家共同指定；不能讓 SDK、gateway 與 middleware 疊成未知 attempt chain。
6. **每個實際 attempt 都可觀察。**至少保留 requested／actual model/provider、API surface、request ID、
   usage、cost、latency、finish／error class 與 routing metadata；不得保存 secret 或 private reasoning。

### 5.2 不同 provider 不相同的部分

| 語意 | OpenAI | Anthropic | Google Gemini | OpenRouter／相容層 |
|---|---|---|---|---|
| 關閉／限制平行 Tool | `parallel_tool_calls: false` | `tool_choice.disable_parallel_tool_use: true` | function-calling config 與 SDK 行為依 API surface | 是否接受／轉譯取決於 model endpoint 與 metadata |
| Agent API／Runner | Responses API＋Agents SDK Runner | Messages API＋Tool Runner | Gemini API＋ADK Runner | 提供多種相容 API route，但不是 application Runner |
| 嚴格 Tool | OpenAI strict schema 子集 | Anthropic strict schema 子集 | Gemini function declaration schema | 取決於下游 model/provider 與正規化能力 |
| 結構化最終輸出 | provider-native structured output | `output_config.format` | `response_json_schema` | 不可只由 model 名稱推定 exact endpoint 同時支援 Tools＋output |
| 錯誤／路由資訊 | typed SDK error、request ID | typed SDK error、request ID | SDK／API error 與 function ID | 另有 router metadata、generation ID、endpoint attempts |

因此「provider-neutral」應指**穩定的產品能力契約與正規化結果**，不是強迫所有 provider 收到相同 JSON。

## 6. 現行接線診斷

這是依 production code 與 revision 3 的 **Caliburn mapping**：

1. [`model_runtime.py`](../../apps/api/app/consultant/model_runtime.py) 已有 model profile、run policy、call／
   token／cost budget、receipt，並關閉 provider SDK retry、改由 LangChain middleware 形成目前可追蹤的
   effective retry budget。這是合理的現行 Caliburn mapping，不是跨家唯一做法；G5 要驗證實際 attempt
   chain，不因名義上只有一個 middleware 就假設沒有隱藏重試。
2. [`langchain.py`](../../apps/api/app/adapters/openrouter/langchain.py) 目前把所有非 `None` 的 effective
   parameters 直接交給 OpenRouter，並固定 `require_parameters: true`。這把「可選的 provider control」
   升格成「每個 endpoint 都必須宣告支援的硬條件」。
3. `parallel_tool_calls: false` 表達的是 Runtime 想避免不安全並行的意圖；但它在 OpenAI、Anthropic
   與 OpenRouter 的 wire 表徵不同，而且 Runtime 本來就能依 Tool 語意循序執行。這次 404 證明現行
   接線沒有把**產品語意、原生能力與 Runtime fallback**分開。
4. `ProviderStrategy(..., strict=True)` 目前固定套用；官方契約要求先確認 exact path 是否同時支援
   Tools 與原生 structured output，否則應選受支援策略或在呼叫前拒絕。
5. 現有 failure receipt 對 OpenRouter typed 404 只留下 exception class，遺失安全的 HTTP status、
   provider error code／message、request／generation ID 與 router metadata，造成事後只能以旁證診斷。

以上不表示現行全部要重寫；它指出缺的是一個明確、可測的 capability-resolution seam。

## 7. 三個方案

| 方案 | 產品效果／功能 | 錯誤風險 | 成本／複雜度 | 可逆性 |
|---|---|---|---|---|
| **A. 只修 OpenRouter 特例**：移除本次不支援欄位，再加 Luna endpoint preflight | 最快恢復單一路徑；沒有建立其他模型／API surface 的一致規則 | 高；下一個欄位、模型或 structured-output 組合仍可能重演 | 最低短期成本，長期反覆修補 | 高 |
| **B. Provider-neutral capability contract＋先實作一個 OpenRouter adapter** | 保留換模型／參數能力；呼叫前判斷必需、偏好與 Runtime 可執行語意；同時保留 LangChain agent loop | 低至中；metadata 仍可能不完整，但可 fail fast、記錄 evidence 並以 bounded characterization 補未知 | 中；只建一個薄 contract/compiler，不同時實作所有 provider | 高 |
| **C. 直接接 OpenAI Responses＋Anthropic Messages 兩套一方 adapter** | 原生功能最完整、錯誤與能力最清楚；可繞過 aggregator translation | 中；兩套 lifecycle、credentials、billing、observability 與回歸矩陣 | 最高，且目前會擴大範圍 | 中 |

## 8. 建議：方案 B

**Working direction／已核准：**採方案 B，但第一版只做 OpenRouter adapter，不同時建立 OpenAI 與
Anthropic direct adapters。這既不是修一個 boolean，也不是 Big Bang 換掉現有 framework。以下
capability 分類與責任細節已由 G4 核准；它仍不是施工授權，須先通過 G5 contract verification。

建議的 provider-neutral lifecycle：

```text
一輪產品需求
  ↓
Invocation Intent
  - required outcomes：本輪需要的 Tool／typed result／隱私與確定路由語意
  - preferred native capabilities：strict、native structured output、provider-side parallel control
  - runtime policies：call/tool/token/time/cost limits、Tool 執行順序、retry budget
  ↓
Capability Resolution（呼叫前）
  - exact model + API surface + endpoint 候選／routing policy
  - required 不成立：不發付費 call，回 configuration/capability failure
  - preferred 不成立：只有 Runtime 有等價、安全實現時才降級，並寫入 receipt
  ↓
Provider Adapter Compile
  - 對已知候選只送支援且本輪需要的 wire fields；unknown 依明示政策處理
  - 選 ProviderStrategy 或 ToolStrategy
  - 產生可稽核的 request manifest（不含 prompt、secret、private reasoning）
  ↓
LangChain Agent Runtime
  - bounded model ↔ tool loop
  - read-only independent tools 才可平行；side-effect／相依 tools 循序
  - Tool validation error 回受控錯誤給模型做有界修正
  ↓
Normalized Result
  - success / needs-input / capability-config-failure /
    transient-exhausted / budget-exceeded / validation-failure
  - 每個 attempt receipt 記 requested/actual route、usage、cost、IDs 與安全錯誤細節
```

### 8.1 這個契約刻意不暴露的東西

模型不填 provider、model、版本、API surface、timeout、retry、limit、parallel policy 或 receipt 欄位；
這些都由可信 Runtime／設定解析。LLM 只看到本輪允許的 Tool 及其最小 schema。

### 8.2 「required／preferred／runtime policy」為何要分開

- **required outcome** 是產品不能失去的效果；無法達成就不應花錢呼叫。
- **preferred native capability** 是有原生支援時更可靠或更省，但 Runtime 有等價機制時可明確降級。
- **runtime policy** 本來就應由應用程式執行，例如 call cap、循序執行有副作用的 Tool、receipt 與
  retry 上限；不應因 provider 沒有同名參數而宣告整個 model 不可用。

本次的 `parallel_tool_calls: false` 最可能屬於後兩者，而不是 Luna 必須原生宣告支援的產品硬能力；
它的正式分類與 Tool concurrency 行為仍要在 G5 逐項驗證，不能只依研究文字直接改 code。

### 8.3 G4 已核准：責任邊界

五輪完整證據與矛盾稽核見[跨家官方證據附錄](2026-09-04-llm-tool-loop-and-runtime-responsibility-cross-vendor-evidence.md)。
這張表不是 OpenAI、Anthropic、Google 與 LangChain 共同發布的標準。它包含三種不同 authority，
後續審核不可混在一起：

1. **官方事實：**各 provider／framework 公開承諾自己提供的 primitive 與限制；
2. **跨家共同原則（研究 inference）：**成熟 runtime 承擔通用 loop／Tool plumbing，應用仍定義自己的
   domain schema、權限、side effect 與驗收政策；
3. **Caliburn 已核准 mapping：**在既定技術選擇下，把某項責任放到 LangChain、LangGraph、adapter 或
   Caliburn 薄政策層。它是目前 Working Decision，仍可依重開條件討論、替換或翻案。

| 層 | G4 核准責任 | 不應負責 |
|---|---|---|
| 模型／原生 provider | 生成、原生 Tool／structured-output protocol、原生 usage 與 request ID | Caliburn 文件權威、domain correctness、員工核准政策 |
| OpenRouter adapter | model／endpoint routing policy compile、provider wire compile、已知 capability evidence、實際 route evidence、gateway error normalization | agent loop、durable state、假裝呼叫前已知道最終 endpoint 或所有 provider wire 相同 |
| LangChain `create_agent` | **唯一 generic bounded model↔Tool loop**、Tool result pairing、structured-output strategy、middleware hooks | 決定產品哪些效果可降級、職務分析規則與員工 authority |
| LangGraph product runtime | 現有 durable product transition、checkpoint、interrupt／resume 與 crash recovery | 再建立第二個 model↔Tool loop、替 provider 猜能力 |
| Pydantic／共享 contract | local request、Tool、effects 與 normalized result 的型別／shape validation | 證明職務內容真實或替員工核准 |
| Caliburn 薄政策層 | Invocation Intent、required／preferred／runtime-enforced 分類、domain Tool／invariant、員工 authority、總 budget、normalized outcome 與最小 receipt | 重寫 provider SDK、LangChain loop 或 LangGraph persistence |

這裡的「原生能力缺少時降級」更精確應稱為**可驗證的等價機制替代**：例如 endpoint 沒有原生
structured output，但可靠支援 Tool calling 時，可由 LangChain `ToolStrategy` 產生同一 typed result，
再由 Pydantic 與 Caliburn verifier 驗證。若連等價機制都沒有，或缺少的是隱私、授權、成本上限等
硬要求，就必須 fail fast，不能靜默降低產品效果。每次替代都應在 receipt 留下 requested、selected、
reason 與 validation outcome；不保存 prompt、secret 或 private reasoning。

推薦 runtime 形狀是：capability compiler → LangChain `create_agent`；現有 LangGraph 只承接 product-level
durability／interrupt，不因本題再包一層 generic Tool loop。OpenAI Runner、Anthropic Tool Runner 與
Google ADK 證明 managed loop 是成熟做法；它們也證明 manual takeover 仍是例外時可用的正式路徑，
因此本配置不是把 LangChain 誤稱成唯一產業標準。

Product Owner 先於 2026-09-04 澄清本節精確分工不可由方案 B 自動推導；五輪官方資料與本地反向
審查完成後，再明確核准本責任配置。它仍可由新證據重開，也不得被倒推成跨家產業標準。

## 9. G5 verification design

### 9.1 Preflight、範圍與停止條件

```text
Topic ID: LLM-Q001 / G5
Current stage: dependency preflight passed；final baseline frozen；G5 contract tests 尚未施工
Binding decisions:
  - G3 方案 B 與 G4 精確責任邊界已核准；本輪不重開。
  - Production 仍受現行 code、AGENTS.md 與 Accepted ADR 0060 約束。
  - MEM-Q004 維持 FAIL_UNPROVEN；不授權 revision 4。
This turn's only blocking question:
  Owner 是否授權依 §9.4～§9.6 實作零付費 G5 contract tests。
Out of scope:
  live API、模型品質 eval、Memory／JD／UI／RAG、direct-provider adapter、ADR、施工與 push。
Cost / side-effect cap:
  0 個 model／provider request、0 模型費用、0 外部產品寫入；dependency preflight 只允許 PyPI
  metadata／distribution resolution，後續 G5 只允許本地 synthetic tests。
Stop rule:
  矩陣每列都有證據層級、零付費測試、明確 PASS／FAIL 與剩餘 unknown 後即停止；
  不因「順便可以測」擴張到 live characterization。
```

### 9.2 Dependency baseline 決策與 preflight 結果

Preflight 前，本 repo 固定 `langchain==1.3.15`、`langchain-openrouter==0.2.7`、
`langgraph==1.2.11`、`deepagents==0.7.5`，lock 解析到 `langchain-core==1.5.4`、OpenRouter SDK
`0.10.8`。2026-09-04 再查 PyPI 時，LangChain 已於 09-03 發布 stable `1.4.0`，DeepAgents 已於
09-02 發布 `0.7.13`，`langchain-openrouter` 最新 stable 仍是 `0.2.8`；LangGraph `1.2.11` 與
PostgreSQL checkpointer `3.1.2` 已是最新 stable。

套件 metadata 顯示：LangChain `1.4.0` 要求 `langchain-core>=1.6.0,<2.0.0` 與
`langgraph>=1.2.11,<1.3.0`；DeepAgents `0.7.13` 要求 `langchain>=1.3.18,<2.0.0` 與
`langchain-core>=1.6.1,<2.0.0`；OpenRouter integration `0.2.8` 仍要求
`langchain-core>=1.5.5,<2.0.0`、OpenRouter SDK `>=0.9.2,<1.0.0`。因此必須整組解析，不能只改一個
版本字串，也不能把 OpenRouter SDK 1.x 直接塞進目前 integration。

直接來源：

- [PyPI — LangChain 1.4.0](https://pypi.org/project/langchain/1.4.0/)
- [PyPI — langchain-openrouter 0.2.8 metadata](https://pypi.org/pypi/langchain-openrouter/0.2.8/json)
- [PyPI — DeepAgents 0.7.13](https://pypi.org/project/deepagents/0.7.13/)
- [PyPI — LangGraph 1.2.11](https://pypi.org/project/langgraph/1.2.11/)
- [PyPI — PostgreSQL checkpointer 3.1.2](https://pypi.org/project/langgraph-checkpoint-postgres/3.1.2/)
- [LangChain — ChatOpenRouter integration](https://docs.langchain.com/oss/python/integrations/chat/openrouter)

| 選項 | 作法 | 優勢 | 風險／成本 | 建議 |
|---|---|---|---|---|
| **A．先做 isolated dependency preflight，再只驗最終 baseline** | 在隔離分支讓 resolver 嘗試最新相容 stable set；跑既有 API contract suite。成功才凍結版本並寫 G5 tests；失敗則不保留 lock diff，帶相容性證據回來裁決 | 符合「以最新 stable 實作」；不替即將淘汰的 wire 寫整套新測試 | 多一個有界 dependency gate；可能揭露 DeepAgents／core 相容性 | **Owner 已選；preflight PASS** |
| **B．只驗目前 pins** | 對 1.3.15／0.2.7／0.10.8 寫 G5 tests，升級另案 | 最快、變數最少 | 很可能之後升級又要重驗 integration wire；會把時間花在舊 baseline | 僅在近期不能改依賴時採 |

Owner 已選 A。Isolated preflight 最終解析並精確固定：

- direct：LangChain `1.4.0`、LangGraph `1.2.11`、PostgreSQL checkpointer `3.1.2`、
  `langchain-openrouter 0.2.8`、DeepAgents `0.7.13`；
- relevant transitive：`langchain-core 1.6.1`、OpenRouter SDK `0.10.8`；
- resolver：`uv lock --dry-run` 與正式 lock 均成功，98 packages 可解；
- regression：升級前 targeted suite `26 passed`；升級後第一次只有 exact-version assertion 如預期失敗，
  更新版本收據／canary 後 targeted suite `26 passed`；完整 API suite `258 passed, 29 skipped`；
- cost／side effect：測試在無外網 sandbox 執行，沒有 live model request、模型費用或外部產品寫入；
  唯一外部存取是 PyPI metadata／distribution resolution。

因此 final dependency baseline 已凍結並保留 lock diff。這只完成 G5 gate 1 與既有 deterministic regression；
沒有改 runtime 產品語意，也沒有開始 §9.4 的新 capability contract tests、live call、merge 或 push。

### 9.3 四層證據，不再互相冒充

下列名稱是 **Caliburn 的 verification taxonomy**，不是廠商共同標準；用途只是阻止「文件說支援」被誤寫成
「這條實際接線已驗證」：

| 層級 | 能證明什麼 | 不能證明什麼 |
|---|---|---|
| `DOC_DECLARED` | 官方 model／endpoint catalog、framework profile 或文件宣告候選能力 | pinned adapter 實際送出的 JSON、能力組合、exact endpoint 行為 |
| `SERIALIZATION_VERIFIED` | 以 pinned integration 捕捉到實際 outbound request，證明 wire field／schema／route compile | provider 真會接受或嚴格執行 |
| `RUNTIME_CONTRACT_VERIFIED` | 以 synthetic provider response／error 驗證 Tool loop、pairing、retry、budget、normalization、receipt | 真 endpoint 的路由與生成品質 |
| `LIVE_ENDPOINT_CHARACTERIZED` | 一次有界 live call 對 exact route 的當下行為 | 永久能力保證或跨 endpoint 結論 |

前三層都不能回答、而且 unknown 會改變 adapter 選擇時，才可另提第四層授權。OpenRouter 官方明示
structured-output 支援是 endpoint-level 且可能變動；`require_parameters=true` 只做路由篩選，不能取代
第二、三層驗證。[Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)、
[Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)

### 9.4 逐能力矩陣

| 能力／產品結果 | 分類 | G5 零付費驗證 | PASS 條件 | G5 後仍未知 |
|---|---|---|---|---|
| exact model、單一 provider、禁止 fallback | `required` | 捕捉實際 request manifest 與 outbound JSON；餵 synthetic router metadata | exact slug；`only/order` 只有 allowlist provider；`allow_fallbacks=false`；actual route 不符時 fail closed | base provider 仍可能有多個實體 endpoint；真 selected endpoint 要 live metadata 才知道 |
| 本輪允許的 Tool schema | `required` | 從**實際 `create_agent`＋動態 middleware** 的 outbound JSON 取 tools，不只讀 Python object 屬性 | 只出現 allowlist Tool；schema strict／provider-safe；模型不填 scope、limit、retry、authority 欄位 | exact endpoint 的 Tool 品質 |
| Tool call／result pairing 與多 call wave | `required` | synthetic response 產生多個 call ID；Runtime 回傳每個 matching result；測獨立 read 與重疊 mutation | 每個 call 恰有一個 result；獨立操作可完成；重疊 mutation 在執行前受控拒絕；無靜默遺漏 | provider 是否傾向平行呼叫 |
| typed final result | `required outcome`；provider-native 是 `preferred` | 分別捕捉 `ProviderStrategy`／已驗證 fallback 的 wire，並用原始 Pydantic type local validate | strategy 有明確 capability evidence；schema 正規化；不合格輸出 fail／有界修正，不進 domain transition | Luna exact endpoint 是否同 request 可靠執行 Tools＋native structured output |
| native strict | `preferred` | 驗 request 中 strict schema；以 malformed synthetic output 證明 local validation 不被繞過 | native strict 不可用時仍有同一 local domain gate；receipt 記 strategy／reason | gateway translation 的實際約束強度 |
| reasoning effort | `preferred` | catalog/profile 對照＋捕捉實際 `reasoning` wire | 只送 model 宣告支援的 effort；模型不填；不支援時依明示政策 fail／omit | 品質、成本與延遲；屬未來 eval |
| temperature／top-p 等 sampling controls | `preferred` | 用 Luna 現行 catalog/profile 編譯並捕捉 JSON | 未宣告支援或值為 `None` 的參數完全不送；不再被 blanket `require_parameters` 升格 | 其他模型的最佳預設 |
| provider-side parallel control | `preferred`；安全順序是 `runtime-enforced` | 證明 Luna request 不因產品排序政策硬送未支援的 provider field；測 workspace wave guard | 沒原生 control 仍能安全序列化相依／有副作用操作；不把 optional field 變 required filter | provider 內部 scheduling |
| effective retry／replay safety | `runtime-enforced` | synthetic timeout、429、5xx、4xx、validation error、已發生 side effect；計算真實 model invocation 與 receipt | SDK model retry=0；model 與 Tool 各只有一個明示 retry owner；每次真 model invocation 一張 receipt；4xx config 不重試；只有明示 replay-safe 的 Tool 可重試，mutation 不盲重播；總 attempts 有硬上限 | OpenRouter 內部 endpoint attempts；只有 metadata/live 可觀察 |
| failure taxonomy／恢復狀態 | `required` | 注入 SDK typed error、HTTP error、embedded gateway error、Tool validation error | 保留安全的 status／provider code／request ID；不洩露 prompt、員工內容或 raw payload；映射到穩定 normalized status | 未見過的新 provider error shape |
| budget／receipt | `runtime-enforced` | synthetic usage、cache、cost、latency、finish、route metadata；超限案例 | model／Tool／token／elapsed／cost 均 fail closed；receipt 只留 manifest、實際 route、attempt、usage/cost/latency、finish 或安全 error | 真 provider 計費與 router attempt metadata 完整度 |

OpenRouter 的當日 model catalog 只足以給 Luna `DOC_DECLARED`：它宣告 `tools`、`tool_choice`、
`response_format`、`structured_outputs`、`reasoning`／`reasoning_effort`，但未宣告 `temperature`、`top_p`
或 `parallel_tool_calls`；這不能自行升格為「Tools＋structured output 組合已驗證」。
[OpenRouter models API](https://openrouter.ai/api/v1/models)

### 9.5 測試形狀與反假綠規則

1. **Compiler unit tests：**同一 `InvocationIntent` 對 known-supported、known-unsupported、unknown 三種
   capability evidence，驗 required fail-fast、preferred 等價替代與 unsupported field omission。
2. **Transport serialization tests：**使用本地 HTTP mock 捕捉 `langchain-openrouter` 真正送出的 body／headers；
   不接受只 assert `ChatOpenRouter` instance attributes，因那不能證明 SDK 最終 wire。
3. **Agent-loop contract tests：**走真 `create_agent`／middleware，provider response 與錯誤用 synthetic fixture；
   驗 Tool pairing、structured result、重試、call cap 與每 attempt receipt。
4. **Privacy tests：**receipt／normalized error 不得含 prompt、Tool raw payload、員工逐字內容、secret 或 private
   reasoning；安全 provider error code、HTTP status、request／generation ID 可保留。
5. **Regression tests：**重現 revision 3 的 `parallel_tool_calls:false + require_parameters:true` 組合，必須在
   付費呼叫前被 compiler 修正為 runtime policy／unsupported omission，而不是再次送出或用 retry 掩蓋。

每個測試必須寫明自己只證明 §9.3 哪一層。Mock response 不能被報告成 Luna live capability；catalog
也不能被報告成 integration wire 已正確。

### 9.6 G5 通過門檻與輸出

G5 只有同時符合以下條件才可標為 PASS：

1. §9.2 選定的 dependency set 已固定，lock 與 runtime-reported versions 一致；**已於 dependency
   preflight 通過**；
2. §9.4 每一列都有 `DOC_DECLARED` 狀態，適用者另有 `SERIALIZATION_VERIFIED`／
   `RUNTIME_CONTRACT_VERIFIED`；
3. 所有 required outcome 在已知不支援時都於外部 request 前 fail fast；
4. optional／preferred capability 不會再被 blanket compile 成 endpoint 硬條件；
5. hidden retry、漏配 Tool result、錯誤資訊遺失、receipt 洩露與 post-hoc budget 假保護均有反例測試；
6. 現有 API deterministic suite 維持綠燈，且測試全程不需要 API key。

G5 產出只是一份 capability matrix、零付費 contract-test 證據與剩餘 unknown。它不自動授權 ADR、
production 修改、live API 或 `MEM-Q004` revision 4。若前三層已足以選 strategy，就直接停止；不得為了
「更完整」自行花費 live call。

## 10. 未知與重開條件

- **Unknown：**OpenRouter catalog 是否會始終完整反映每個 endpoint 的所有相容參數；官方 metadata
  可作 evidence，但不能當永不過時的型別系統。
- **Unknown：**G5 最終凍結的 `langchain-openrouter` 對每種 provider-native structured output／strict
  組合的真實 wire translation；應以無付費 serialization test 優先確認。
- **Parking lot：**是否改用 OpenAI Responses direct、Anthropic Messages direct、模型 fallback、跨模型
  品質／成本比較、streaming transport 與 prompt caching。
- **重開方案選擇的條件：**OpenRouter adapter 無法提供 required outcome、官方取消必要能力、代表性
  contract test 證明 metadata／translation 無法可靠 fail fast，或 Owner 改變 provider／fallback 政策。

## 11. 本輪 closure

```text
Decision / finding:
  跨家共同點是 provider boundary、已知 mismatch 的 capability preflight、native schema＋local validation、
  可接管的 framework-managed bounded loop、replay-safe bounded retry 與 per-attempt observability；
  各家 wire field、Runner 與責任元件並不相同。revision 3 是 blanket request compilation 的反例。
Status:
  LLM-Q001 WORKING；G3 方案 B 與 G4 精確責任邊界均已核准；Owner 已選 dependency 方案 A，
  isolated preflight PASS，final baseline 已凍結；G5 capability contract tests 尚未施工。
Why:
  三個實質方案已可比較；G5 已把文件宣告、wire、Runtime 與 live 四層證據分開，並為每項能力定義
  零付費測試、PASS 條件與剩餘 unknown。
Sources:
  §4 的 OpenAI、Anthropic、Google、OpenRouter、LangChain／LangGraph 官方資料；PyPI package metadata；
  跨家證據附錄；§3 的 revision 3 receipt；現行 model runtime／adapter／tests 反向稽核。
Affected artifacts:
  本研究、docs/current-decisions.md、API dependency pins／lock、adapter 版本收據與 exact-version canary；
  沒有 runtime 語意變更、ADR、live API、Memory revision 4、merge 或 push。
Reopen trigger:
  §10。
Next gate:
  Owner 審核 preflight 結果；若授權，才依 §9.4～§9.6 實作零付費 G5 contract tests。目前仍不授權
  live call、Memory revision 4、merge 或 push。
```
