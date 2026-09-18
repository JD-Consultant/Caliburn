# LLM Tool Loop 與 Runtime 責任：跨家官方證據附錄

- 日期：2026-09-04
- Topic ID：`LLM-Q001`
- 狀態：`EVIDENCE`；不是產品決策、ADR、施工計畫或 production 授權
- 父文件：[`2026-09-04-llm-invocation-lifecycle-and-provider-capability-contract-research.md`](2026-09-04-llm-invocation-lifecycle-and-provider-capability-contract-research.md)

## 0. 審核結論

本附錄依同一個 blocking question 做五輪交叉審核：

1. OpenAI 與 Anthropic 的原生 API／SDK／Runner；
2. Google Gemini／ADK 作外部三角驗證；
3. LangChain／LangGraph／OpenRouter 的實際能力邊界；
4. Caliburn 現行 code、Accepted ADR 0060 與先前研究的矛盾稽核；
5. 官方頁面時效性抽查與本地 pinned dependency 對照。

結果沒有推翻已核准的「provider-neutral capability contract＋第一版 OpenRouter adapter」方向，
但修正了五個過度推論：

1. 大廠共同支持的是**有界 Tool loop 與明確執行邊界**，不是強制所有應用都用某一個 Runner；
2. 大廠共同支持的是**有界、分類、可安全重播的 retry**，不是共同規定只能有哪一層叫做 retry owner；
3. 已知的 required capability mismatch 應在付費呼叫前失敗，但 endpoint metadata 可能不完整，不能宣稱呼叫前一定知道全部能力；
4. `require_parameters: true` 是 OpenRouter 路由工具，不是所有 optional／preferred 參數都應一律升格成 endpoint 硬條件；
5. LangChain／LangGraph／Pydantic／OpenRouter 的精確分工是 Caliburn mapping，不是跨家標準。

本輪送 Owner 審核、並於五輪查證完成後獲核准的配置是：

> 以 LangChain `create_agent` 承接一次 bounded model↔Tool loop；以薄 capability compiler 把產品需求轉成
> exact OpenRouter request；沿用現有 LangGraph durable product workflow，但不為 LLM 呼叫再建立第二個
> 外層 Tool loop。Caliburn 只定義產品必要效果、domain Tool／invariant、員工 authority、總 budget 與
> normalized outcome。決策效力記錄在 `docs/current-decisions.md`；本附錄本身仍只是證據。

## 1. 研究方法與證據標籤

### 1.1 來源優先序

1. OpenAI、Anthropic 原生 API／SDK／agent runtime 官方文件；
2. Google Gemini／ADK 官方文件，只作跨家三角驗證；
3. LangChain／LangGraph／OpenRouter 官方文件；
4. Caliburn frozen payload、receipt、現行 code 與測試；
5. 先前研究只作線索，與新官方資料衝突時不保留舊推論。

不以部落格轉述、搜尋摘要或廠商未公開的內部架構作證。OpenAI／Anthropic 是主要標竿；Google
只用來確認某原則不是單一廠商特例。

### 1.2 標籤

- **Official fact**：來源直接承諾的能力或限制；
- **Cross-vendor inference**：至少兩家官方事實共同支持的高階原則；
- **Framework fact**：某框架公開提供的 primitive，不外推成產業標準；
- **Caliburn mapping**：為本產品選擇的責任配置，必須由 Owner 裁決；
- **Unknown**：公開資料不足，需離線 contract test 或最小 live characterization。

### 1.3 Stop rule

本輪在以下條件成立時停止廣搜：

- 所有會改變 G4 責任配置的主張都有官方來源或明列 Unknown；
- OpenAI、Anthropic、Google、LangChain／LangGraph 與 OpenRouter 未再產生新的架構分支；
- 新來源只增加例子，不再改變候選；
- 剩餘問題可由無付費 contract test 或一個有界 characterization 回答。

## 2. 第一輪：OpenAI 與 Anthropic

### 2.1 OpenAI 官方事實

- `Runner` 的標準循環是 model call → Tool／handoff／final 判斷 → 執行 Tool → 把結果加入輸入 →
  再呼叫模型；`max_turns` 可硬性限制循環。[Running agents](https://openai.github.io/openai-agents-python/running_agents/)
- Function／local tools 是模型提出結構化請求、Runtime／application 真正執行；模型不會自行執行
  application code。[Tools](https://openai.github.io/openai-agents-python/tools/)
- 需要人類核准的 Tool 可中斷 Runner，序列化 `RunState`，核准／拒絕後恢復；這是通用機制，
  哪些動作要核准仍由 application 決定。[Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- Runner-managed model retry 是 opt-in，而且要服從 response-started／stateful request／local side-effect
  的 replay-safety 邊界。[Models and providers](https://openai.github.io/openai-agents-python/models/)
- tracing 可記 model generation、Tool、handoff、guardrail 與自訂 span；是否記敏感 input／output
  由 application 控制。[Tracing](https://openai.github.io/openai-agents-python/tracing/)

這些事實證明成熟 Runner 能承接一般 loop、上限、approval 與 tracing；同一官方文件仍允許直接使用
Responses API 或自訂 provider，因此不能推導「所有應用必須用 OpenAI Runner」。

### 2.2 Anthropic 官方事實

- client Tool 的正式契約是 Claude 回傳 `tool_use`，application 執行，再以相同 `tool_use_id` 回傳
  `tool_result`；Claude 本身不執行 application Tool。[How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- SDK Tool Runner 可自動管理 Tool 執行、message history、錯誤包裝與循環，並以 `max_iterations`
  限制；需要自訂 retry、HITL 或 batching 時，application 可接管 history。
  [Tool Runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- Claude 現在同時支援原生 JSON output `output_config.format` 與 strict Tool；兩者可同 request 使用。
  SDK 會轉換不支援的 schema constraint，之後仍以原始型別作 local validation。
  [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- Tool 執行錯誤以原 call ID 與 `is_error: true` 回給模型，讓模型在同一 loop 中修正。
  [Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- SDK 對部分 connection／429／5xx 預設有 bounded retry；錯誤回應帶 request ID。
  [API errors](https://platform.claude.com/docs/en/api/errors)

這些事實證明 managed Tool Runner 是 Anthropic 的推薦便利層，但手寫 canonical loop 仍是正式支援路徑。
因此「優先使用成熟 Runner」是合理工程建議，不是 API 合規的唯一方式。

## 3. 第二輪：Google 三角驗證

- Gemini custom function calling 同樣是模型回傳 function name／arguments／ID，application 執行後再把
  matching function response 送回模型。[Using tools with Gemini](https://ai.google.dev/gemini-api/docs/tools)
- Structured Output 與 Function Calling 是不同目的：前者約束 final response，後者要求中間執行外部
  動作；即使 schema 正確，application 仍須驗證語意值。[Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- ADK Runtime 的 Runner 接收輸入、驅動 agent、處理事件並透過 service 提交 state；agent／Tool／callback
  才負責實際計算與決策。[Runtime event loop](https://adk.dev/runtime/event-loop/)
- ADK Session 是一條 conversation thread，保存事件與暫時 state；confirmation 可在動作前暫停並等待
  使用者輸入。[Sessions](https://adk.dev/sessions/session/) · [Action confirmations](https://adk.dev/tools-custom/confirmation/)

Google 的元件名稱與 OpenAI／Anthropic 不同，但同樣把「模型請求動作、Runtime 驅動循環、application
執行 Tool、session 保存事件、必要時等待確認」分層。這支持高階原則，不支持直接把 ADK 元件名搬進
Caliburn。

## 4. 第三輪：Framework 與 Gateway 能力

### 4.1 LangChain／LangGraph

- LangChain `create_agent` 已在 LangGraph runtime 上執行，不是另一套與 LangGraph 無關的 loop。
  [Runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- `create_agent` 可直接管理 Tool loop；middleware 可插入 call limit、retry、logging、context、guardrail
  與 HITL 等機制。Middleware 在 `create_agent` 編譯出的 LangGraph 內執行，不是第三個 runtime。
  [Agents](https://docs.langchain.com/oss/python/langchain/agents) · [Middleware](https://docs.langchain.com/oss/python/langchain/middleware/overview)
- structured output 可選 provider-native `ProviderStrategy` 或 Tool-based `ToolStrategy`；直接傳 schema
  時可依 profile 自動選，但官方允許在 profile 缺漏時覆寫。若同時有 Tool 與 final structured output，
  exact model/provider 必須支援該組合。[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- LangGraph Checkpointer 保存 thread-scoped graph state，提供 fault tolerance、interrupt／resume 與 HITL；
  Store 是另外的長期資料 primitive。這些是 framework mechanism，不會定義 Caliburn domain truth。
  [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

### 4.2 OpenRouter

- `require_parameters: true` 只路由到宣告支援 request 中全部參數的 endpoint；預設為 `false`，預設路由
  可能忽略 unknown parameters。[Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- 即使 `require_parameters: false`，OpenRouter 目前仍把 `tools`、`response_format` 與 `verbosity` 當作
  同模型 endpoints 間的 soft preference；若沒有 endpoint 宣告支援，仍可能路由並忽略該參數。因此
  soft preference 不能代替 required-outcome preflight。[Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- model catalog 有 `supported_parameters`，但 exact endpoint 是否支援某組合仍可能需要 endpoint metadata
  或 characterization。[Models](https://openrouter.ai/docs/guides/overview/models)
- opt-in router metadata 可回 requested／selected route、候選 endpoint、attempts 與 pipeline，適合診斷
  與成本歸因。[Router metadata](https://openrouter.ai/docs/guides/features/router-metadata)

OpenRouter 是可替換 gateway，不是 Agent Runtime、domain validator 或 durable workflow owner。它能提供
capability evidence 與 route evidence，但不能保證所有下游 provider 具有同一原生 wire contract。

### 4.3 第五輪：時效性與 pinned-version 邊界

2026-09-04 再次直接抽查 OpenAI Runner、Anthropic Tool Runner、LangChain Runtime 與 OpenRouter routing
官方頁面，仍支持前四輪結論；同時新增了 OpenRouter soft preference 這項容易被忽略的細節。

本 repo preflight 前 pin `langchain==1.3.15`、`langgraph==1.2.11`、
`langgraph-checkpoint-postgres==3.1.2`、`langchain-openrouter==0.2.7` 與 `deepagents==0.7.5`。2026-09-04
再次核對時，LangChain 已於 09-03 發布 stable `1.4.0`，DeepAgents 已於 09-02 發布 `0.7.13`，
`langchain-openrouter` 最新 stable 是 `0.2.8`。Owner 核准的 isolated preflight 已把最終 baseline 解析為
LangChain `1.4.0`、LangGraph `1.2.11`、PostgreSQL checkpointer `3.1.2`、OpenRouter integration
`0.2.8`、DeepAgents `0.7.13`、`langchain-core 1.6.1` 與 OpenRouter SDK `0.10.8`；完整 API suite
`258 passed, 29 skipped`。OpenRouter integration 仍限制 SDK `<1.0.0`，所以不能直接混入 SDK 1.x。

目前官方文件能證明 architecture primitive，不能單獨證明任何一組 pinned integration 對某個 exact
endpoint 的 wire serialization。因此 G4 可裁決責任；G5 仍須先凍結一組相容 dependency baseline，
再以無付費 serialization／Runtime contract test 驗證。兩種證據不得互相冒充。

直接來源：[LangChain 1.4.0](https://pypi.org/project/langchain/1.4.0/)、
[langchain-openrouter 0.2.8 metadata](https://pypi.org/pypi/langchain-openrouter/0.2.8/json)、
[DeepAgents 0.7.13](https://pypi.org/project/deepagents/0.7.13/)。

## 5. 跨家共同原則

以下均為 **Cross-vendor inference**，不是某一家官方原句：

1. **模型提出動作，Runtime／application 執行。** Client Tool 的 shape 與 call ID 來自 provider；路徑、
   權限、副作用、資料庫操作與 business invariant 由執行環境負責。
2. **一次使用者輸入可形成有界的多 step loop。**OpenAI Runner、Anthropic Tool Runner、Google ADK 與
   LangChain 都提供 iteration／turn limit 或可在 application 施加硬上限。
3. **成熟 Runner 應優先於重寫通用 plumbing，但不是唯一合法方法。**當它能表達所需錯誤、順序、
   approval 與 observability 時直接使用；只有有實證缺口才接管 loop。
4. **原生 schema 約束與 application validation 分層。**strict／structured output 解決 shape；引用是否
   存在、JD relation 是否合法、員工是否核准仍由 application 驗證。
5. **平行化依 Tool 語意決定。**獨立唯讀 Tool 可平行；共享 working state、有副作用或有順序依賴的
   Tool 必須由 Runtime 循序或互斥執行，不能假設一個跨 provider boolean 完整表達政策。
6. **恢復策略必須有界且 replay-safe。**transient transport／429／5xx、model validation repair、
   user-required input 與程式錯誤應分流；已開始輸出或已造成 side effect 時不能盲目重播。
7. **每個實際 attempt 必須可觀察。**至少要能關聯 request／call ID、requested／actual route、usage、
   latency、finish／error class；不保存 secret 或 private reasoning。

## 6. 不是跨家共識的項目

下列項目不能再寫成「大廠都這樣做」：

| 項目 | 真實性質 |
|---|---|
| 一定透過 OpenRouter | Caliburn 第一版 gateway 選擇；原生 provider SDK 不要求它 |
| LangChain 一定管 loop、LangGraph 一定管外層流程 | LangChain stack 的合理產品分工；不是 OpenAI／Anthropic／Google 標準 |
| Pydantic 是唯一 schema owner | Python 技術選擇；其他 SDK 使用 Zod、dataclass、Java class 等 |
| 只能有一個叫做 retry owner 的元件 | Caliburn 可採的簡化政策；共識只是 effective attempts 必須有界、可追蹤且安全 |
| 所有 request 一律 `require_parameters: true` | OpenRouter 路由策略；只能套在確實 required 且 metadata 可支持的已送參數 |
| 所有 provider 共用 `parallel_tool_calls: false` | OpenAI wire field；Anthropic 表徵不同，Runtime 亦可自行循序執行 |
| 永遠固定 `ProviderStrategy` | LangChain strategy 選擇；exact endpoint 不支援時應 fail 或採已驗證的 `ToolStrategy` |
| 統一 receipt 欄位集合 | Caliburn observability mapping；各 provider 提供的原生 metadata 不同 |

## 7. Policy 與 Mechanism 的正確分法

「Caliburn 保留責任」不等於「Caliburn 手寫機械碼」。應先定義產品政策，再盡量交給 framework primitive
執行：

| 產品政策／效果 | 可直接採用的成熟 mechanism |
|---|---|
| 一輪最多多少 model／Tool calls | LangChain call-limit middleware／Runner limit |
| 哪些錯誤可重試、總共幾次 | SDK 或 middleware retry；Caliburn 只保留一個有效總預算與分類政策 |
| Tool input 必須符合 shape | provider strict Tool＋LangChain／Pydantic validation |
| Tool 實際執行與結果 pairing | LangChain Tool loop／provider call ID |
| 需要員工確認時可暫停恢復 | LangGraph checkpoint／interrupt；觸發條件仍是 Caliburn domain policy |
| 哪些 Tool 可寫什麼、JD 是否有效 | Caliburn domain Tool／verifier；框架不知道職務分析語意 |
| AI 內容何時進核准 JD | Caliburn employee-authority command；不能交給 provider 或 generic HITL 自動決定 |
| 實際 route、usage、latency、error 可追查 | provider／OpenRouter metadata＋LangChain callback；Caliburn 定義最小 receipt projection |

## 8. Runtime 形狀比較

此處不重開已核准的方案 B，只比較它內部的 G4 runtime mapping。

| 候選 | 做法 | 優勢 | 主要風險 | 本輪判斷 |
|---|---|---|---|---|
| **R1．一個標準 agent loop** | capability compiler → LangChain `create_agent`；現有 LangGraph 只承接 durable product workflow／interrupt | 最直接重用成熟 loop、structured output、middleware 與 Tool result；不增加第二 loop | 必須明確阻止 SDK／middleware 疊加未知 retry，並驗 exact OpenRouter wire | **G4 已核准** |
| **R2．每次呼叫再包一個顯式外層 StateGraph** | 每個 model／Tool step 都由自訂 graph nodes 包住 `create_agent` 或 model | 每個 stage 可獨立 checkpoint／stream | `create_agent` 本身已是 LangGraph；若沒有非標準 durable topology，容易形成雙 loop／雙 state | 只有 R1 無法表達具體需求才採 |
| **R3．每家 native Runner** | OpenAI Runner／Anthropic Tool Runner 各有 adapter | 原生能力、錯誤與新功能最直接 | 兩套 runner lifecycle、retry、tracing、測試與 provider switching；偏離已核准的 OpenRouter-first | 保留為重開條件，不作第一版 |

R1 不表示刪除 LangGraph，也不翻案 ADR 0060。它只表示 `LLM-Q001` 不另寫一套 generic Tool loop；
durable semantic state、必要澄清與 authority command 仍由現行 production owner 管理，除非未來 successor ADR
另行裁決。

## 9. G4 已核准責任表

| 層 | G4 核准責任 | 明確不承擔 |
|---|---|---|
| model／native provider | 生成、native Tool／structured-output protocol、原生 usage／request ID | JD authority、domain correctness、員工核准政策 |
| OpenRouter adapter | model／endpoint routing policy compile、provider wire compile、已知 capability evidence、實際 route evidence、gateway error normalization | agent loop、durable state、假裝呼叫前已知道最終 endpoint 或所有 provider wire 相同 |
| LangChain `create_agent` | 單一 bounded model↔Tool loop、Tool result pairing、structured-output strategy、middleware hooks | 決定產品哪些效果可降級、職務分析規則與員工 authority |
| LangGraph product runtime | 現有 durable product transition、checkpoint、interrupt／resume、crash recovery | 再建立第二個 model↔Tool loop、替 provider 猜能力 |
| Pydantic／shared contract | local request／Tool／effect／result 型別與 deterministic shape validation | 證明職務內容真實或替員工核准 |
| Caliburn policy | Invocation Intent、required／preferred／runtime-enforced 分類、domain Tool／invariant、員工 authority、總 budget、normalized outcome 與最小 receipt | 重寫 provider SDK、LangChain loop 或 LangGraph persistence |

### 9.1 Required／preferred／runtime-enforced

- **required outcome**：缺少就不能達成產品效果，例如至少一種經驗證的 typed effect path、資料政策、
  員工 authority；已知不成立時在付費呼叫前失敗。
- **preferred native capability**：原生 strict／structured output／provider-side concurrency control；沒有時，
  只有存在已驗證且等價的 Runtime mechanism 才可替代，並記 receipt。
- **runtime-enforced policy**：call／Tool／time／cost cap、stateful Tool 序列化、domain validation；不要求
  provider 必須宣告同名 wire field。
- **unknown capability**：metadata 不足時不得假裝 supported 或 unsupported；先做不付費的 serialization／
  schema contract test，仍無法回答且會改變選擇時才做一次 bounded characterization。

## 10. 本地研究與現行實作矛盾稽核

### 10.1 已被新證據取代的舊主張

1. [`2026-08-23-luna-structured-tools-and-context-official-audit.md`](2026-08-23-luna-structured-tools-and-context-official-audit.md)
   §4.4 與 [`2026-08-28-llm-authored-field-contract-audit.md`](2026-08-28-llm-authored-field-contract-audit.md)
   §11.4 曾要求所有相關 request 保留 `require_parameters: true`。Revision 3 已證明把 optional
   `parallel_tool_calls` 一起升格為硬篩選會讓 request 在模型前 404；這兩段不能再指導新的 adapter。
2. Anthropic 現已正式提供 `output_config.format` 原生 JSON output，且可與 strict Tool 同 request 使用。
   任何「Claude final structured output 只能透過 Tool」的舊推論均已過時。
3. 「呼叫前必定知道 exact endpoint 全部能力」過強。OpenRouter metadata 與 LangChain profile 是 evidence，
   不是永不過時的型別系統。

### 10.2 仍是 production authority，但不是產業共識

- [ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) 對 LangChain、
  LangGraph、Store／Saver 與 Caliburn 的分工仍是 Accepted production authority。
- 本附錄只指出那些分工是 Caliburn 已接受的架構，不應倒推成 OpenAI／Anthropic／Google 共同標準。
- 若 G4 Working Decision 日後要改變 Accepted boundary，必須開 successor ADR；research 文件不能直接改 production。

### 10.3 現行 code 的直接診斷

- `build_consultant_agent()` 已使用 LangChain `create_agent` 與 middleware，沒有理由再手寫 generic Tool loop。
- `build_openrouter_chat_model()` 目前關閉 SDK retry、由 LangChain middleware施加 retry，形成一套可理解的
  effective budget；這是合理 Caliburn mapping，但不是跨家唯一做法。
- adapter 固定 `require_parameters: true`，agent 固定 `ProviderStrategy(strict=True)`；兩者都需要 capability
  compiler，而不是再加特例或盲目 retry。
- product `StateGraph` 與 per-run `create_agent` 目前各有不同目的；`LLM-Q001` 應只修 capability／invocation
  seam，不藉機重寫 Memory、JD authority 或產品 graph。

## 11. 剩餘 Unknown 與下一個 Gate

仍需在 G5 用低成本方式回答：

1. G5 最終凍結的 `langchain-openrouter` 對 exact Luna endpoint 的 `ProviderStrategy`、`ToolStrategy`、strict Tool 與
   reasoning wire 實際怎麼序列化；
2. OpenRouter endpoint metadata 是否足以判斷「Tools＋native structured output」組合，或需 adapter-owned
   verified capability matrix；
3. 拿掉 provider-side parallel control、改由 Runtime 序列化 mutation Tool 後，LangChain 是否仍會完整
   回送所有 call result；
4. SDK／OpenRouter／LangChain 各層 retry 設定能否由 contract test 證明只有同一個 effective attempt
   budget；
5. normalized failure 與 receipt 的最小欄位，不得把 private prompt／reasoning 或整份 provider payload
   寫入 durable state。

Dependency preflight 已 PASS 並凍結 final baseline。下一個 gate 不是 live Memory revision 4，而是依已完成的
capability-by-capability matrix 實作零付費 G5 contract tests。G4 已核准；只有新官方證據、contract failure
或產品要求改變時才重開責任 mapping，不重做已完成的官方研究。
