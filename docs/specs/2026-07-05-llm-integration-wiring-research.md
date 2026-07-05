# LLM 怎麼接進系統 — 接線層研究(進行中)

> **類型**:研究紀錄(滾動式,邊研究邊討論邊補輪次)。**只研究、未改碼**;落實前開 ADR / plan。
> **日期**:2026-07-05 起。**分支**:`research/llm-interview-integration`。
> **上游研究**:[`2026-07-02-llm-interview-authoring-research.md`](2026-07-02-llm-interview-authoring-research.md)
> (五軸 + 勞動部指引精讀 + 載體研究)——那份回答「訪談要**問什麼**、UX 長怎樣」;
> **本份回答「LLM 到底怎麼接(HOW)」**:provider、接線、引擎骨幹、tool 協定。
> **維護者定調**:架構由大慢慢變小、實作從小開始、隨時可調、持續研究;
> **不受既有 authoring graph 約束**(ADR 0020 §4 維護者明示,本輪再次確認)。

---

## 0. 現況盤點(讀碼驗證,2026-07-05)

### 已有的

- **LangGraph 訪談圖**(原 graph_v3,[authoring 深文檔](../../apps/api/docs/authoring.md)):
  pick_profile → 逐任務 STAR/5W2H/indicator loop → curate K/S/A → build_doc;
  interrupt 逐槽問人、checkpointer 可續。**但**:`build_doc` 產舊 doc shape(非 ocs-contract)、
  沒有前端面板驅動、與編輯器是兩條寫入路。→ 定位:**參考材料,不是前提**。
- **`LlmPort`**([ports.py](../../apps/api/app/core/ports.py)):只有 `complete_text` / `complete_json`
  兩方法——**全在「提示層」**(`complete_json` = prompt 要 JSON + `safe_parse_json` + 重試)。
- **`OpenRouterLlm`**([llm_openrouter.py](../../apps/api/app/adapters/llm_openrouter.py)):
  `langchain_openai.ChatOpenAI` 指 OpenRouter OpenAI-相容端點;per-role 分模型
  (deep/indicator/cheap = 成本控制);**沒用到** `response_format` / structured output / tool schema。
- **`extract_tasks`**([extract_tasks.py](../../apps/api/app/services/ai/extract_tasks.py)):
  grounded-id 模式 = LLM 挑 id → **事後 `i in known` 丟棄自創 id**(事後防禦)。
- **相似比對 `items:match`**(ADR 0022):已為未來訪談引擎預留的確定性 tool(灰區對 → 鑑別提問)。

### 缺口(= 「怎麼接」的三條縫)

| # | 縫 | 現況 |
|---|---|---|
| 1 | 既有 graph 對不上現行契約/前端(舊 doc shape、無面板驅動) | 待引擎骨幹定案後處置 |
| 2 | 兩條寫入路(graph `DocRepo.save` vs 編輯器 REST PATCH)| 終局共編 document-of-record;ADR 0015 樂觀鎖為地基 |
| 3 | 缺 adaptive follow-up 判斷器(固定問四槽) | 官方停止準則=資料飽和(上游研究 §7.3) |

## 1. 輪 1 — 骨幹形狀:workflow 優先 + 結構化輸出已 GA(2026-07-04)

### 1.1 Anthropic 立場(2026 重申)

[Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) +
[2026 workflow-vs-agent playbook](https://mer.vin/2026/05/when-not-to-build-ai-agents-anthropics-workflow-vs-agent-playbook/):
「**多數生產系統不需要自主 agent——需要的是明確步驟、緊湊工具、可量測結果的 workflow**」;
agent 只在可證明改善結果時加,收斂三決策:Environment / Tools(poka-yoke)/ System prompt(含 stop rules)。
另:[Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)、
[Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)。

### 1.2 結構化輸出的 2026 分野(關鍵新事實)

([Collin Wilkins 2026](https://collinwilkins.com/articles/structured-output)、
[Pockit 2026 指南](https://pockit.tools/blog/llm-structured-output-complete-guide/)、
[AWS 實務指南](https://builder.aws.com/content/2wzRXcEcE7u3LfukKwiYIf75Rpw/how-to-get-structured-output-from-llms-a-practical-guide))

- **tool/function schema = 「提示」**:結構(欄位/型別)大致對(95–99%),**值仍可自由編**。
- **native structured output = 受限解碼(constrained decoding)= 「約束」**:
  schema/enum 編譯成狀態機,解碼每步只准合法 token → **100% 保證,值也被約束**。
- 2026 現況:OpenAI / Google Gemini / **Anthropic(2026 初 GA)** 皆原生支援;
  自架路線有 Outlines / vLLM guided decoding / XGrammar
  ([AWS + Outlines](https://aws.amazon.com/blogs/machine-learning/generate-structured-output-from-llms-with-dottxt-outlines-in-aws/);
  研究前沿 [draft-conditioned CD, 2026](https://arxiv.org/pdf/2603.03305))。

### 1.3 浮現的架構脊椎(討論定調)

```
骨幹 = workflow(六面向預定義;Anthropic 背書 + 勞動部指引腳本順序)
葉子 = 有界 adaptive loop(僅「深掘」允許 LLM 判斷追問/停;停止準則=官方資料飽和)
中軸 = 信任分軸:目錄類 → 受限解碼(100% 零幻覺)/ 敘述類 → 自由寫 + 溯源 + rubric
工具 = poka-yoke 確定性介面(indexer 檢索 / items:match / extract)
```

不是「workflow vs agent 二選一」——**workflow 骨幹 + 葉子有界 agentic**。
既有圖的「六階段固定 + 深問 loop」形狀方向對;要換血的是兩個機制:
目錄類升受限解碼、深問補 adaptive 判斷器。

**升級意義**:`extract_tasks` 的「事後丟棄自創 id」→「**生成時就編不出池外 id**」
(池 id 當 per-request enum 灌進 schema)。

## 2. 輪 2 — provider / 接線層(2026-07-05,維護者選定的下一鑽)

### 2.1 受限解碼是誰的性質?(核心觀念)

**遮罩發生在跑模型的伺服器(serving stack),不是模型本身。** 三種取得方式:

1. **Provider 原生**:OpenAI / Gemini / Anthropic 各自伺服器已實作,開 `strict` schema 即得 100%。
2. **OpenRouter 透傳**([官方文件](https://openrouter.ai/docs/guides/features/structured-outputs)):
   `response_format: {type: json_schema, strict: true}` 轉給底層 provider →
   **現有 OpenRouter 接線就能用**,前提是底層模型支援(OpenAI/Gemini 系最穩;
   Anthropic 系官方僅列較舊版本)。**不支援 → 直接報錯,不靜默降級**(配錯第一次呼叫就發現)。
   注意:OpenRouter 文件**未承諾**自己的 strict 是受限解碼——保證來自底層 provider,
   所以「挑底層」是關鍵,且對 Anthropic 模型的完整保證
   [官方明說只在第一方 provider 成立](https://openrouter.ai/blog/tutorials/claude-code-openrouter/)。
3. **自架 + Outlines/vLLM**:自己做遮罩,零鎖定(SaaS 暫緩 → 目前 YAGNI)。

**結論:不是非 Anthropic SDK 不可;OpenAI/Gemini 模型可用;現有 OpenRouter API 可用。**

### 2.2 六邊形對策:先定 port 形狀,provider 推遲到 adapter

`LlmPort` 新增第三句話型(方向草案,待 ADR):

```python
async def select_schema(self, prompt: str, schema: dict, *, role: str = "cheap") -> Any: ...
# 語意:「輸出必須符合此 schema(含 enum)」——由 adapter 用 provider 硬保證兌現
```

domain 只表達意圖(「給我池內 id」);打給誰是 adapter/config,隨時可換、domain 零改動。

### 2.3 呼叫路徑選型判準(對齊 contract-strategy 判準式;由上往下取第一列)

| 如果這個呼叫是… | 走 | 為什麼 | 現況 |
|---|---|---|---|
| 敘述類自由文字(STAR 精煉、job_desc、追問句)| `complete_text` → OpenRouter per-role | 值不承重、量大、要成本彈性;有人審(staged)| ✅ 已有 |
| 要 JSON 結構、值不承重(填槽解析、品質分)| `complete_json` → OpenRouter 提示層 | 型別錯 parse 掉重試即可 | ✅ 已有 |
| **值承重 = 目錄類**(挑池內 id、封閉 enum)| **`select_schema` → OpenRouter `json_schema+strict`,底層挑有原生受限解碼的模型** | 值直接成文件身分 → 100% 零幻覺;透傳即得,零新基建 | 🆕 第一刀 |
| 需要 thinking + 多步 tool loop 品質(引擎中樞)| 屆時評估 Anthropic SDK 直連 | 路由器對 tool 協定翻譯非完美;中樞值得最乾淨的路 | ⏳ 立項時 |
| 完全自主 / 資料不出門 | 自架 + Outlines / vLLM guided decoding | 零鎖定 | ❌ YAGNI |

**兩個決定軸**:①值承重嗎(輸出會不會直接成為文件目錄身分)②量 × 成本。

### 2.4 Guard 與 escalation(對齊校準紀律)

- 既有事後 `i in known` **不拆**,降級為 defense-in-depth 保險絲:理論上永不觸發,
  **觸發即 log error** = 所選底層模型沒兌現受限解碼 → 換模型或升直連。
- **模型選用驗收**:選定底層模型後跑**對抗性驗收腳本**(N 次抽取、誘導池外 id,零池外 = 過),
  紀錄留 `docs/specs/`;換模型 = 重跑驗收,不改碼。
- Escalation triggers:①驗收抓到池外 id、連換兩模型仍失敗 → Anthropic 直連;
  ②訪談引擎立項需 thinking+tool loop 中樞 → 只升中樞那一路;③資料主權要求 → 自架(另開研究)。

## 3. 輪 3 — 引擎骨幹岔路:有狀態圖 vs 無狀態回合服務(2026-07-05)

### 3.1 兩個權威

- **12-factor agents**(ADR 0007 既有原則;[Factor 12 原文](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-12-stateless-reducer.md)、
  [2026 生產經驗](https://starlog.is/articles/ai-agents/humanlayer-12-factor-agents/)):
  **own your control flow + agent = 無狀態 reducer**(純函式:進狀態→出狀態,狀態存外面);
  框架藏 retry/暫停/終止是生產卡關主因。
- **LangGraph 2026**([官方 durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)、
  [2026 評測](https://toolbrain.net/blog/langgraph-review-2026/)):interrupt/HITL 同類最強、採用廣;
  公認學習曲線最陡、框架接管控制流。

### 3.2 判別場景(本案特有,權重最大)

ADR 0020 混合主導權=「人隨時直接改文件」。場景:訪談到第 3 任務,員工中途在工作台改名/刪任務,回面板續訪。

| | (A)有狀態圖(LangGraph) | (B)無狀態回合服務 |
|---|---|---|
| 進度存哪 | checkpointer 圖狀態 blob | DB 一列(phase/task_index/slots)+ **文件本身** |
| 人中途改文件 | 圖狀態**過期**=雙真相 ⚠️ | 下回合**現讀文件**,自動生效 ✅ |
| 回合形狀 | resume 圖(AG-UI 協定) | 普通 REST(與編輯器 autosave/proposal-apply 同形)|
| 縫 2 | 仍在 | **自然消失**(走同一條文件 seam)|
| 12-factor | ✗ | ✓ Factor 12 字面實作 |

**洞見:「人隨時可改文件」天然懲罰引擎私有的長壽命狀態。** 訪談軌道本身簡單
(六階段+每任務幾槽),DB 一列裝得下。

## 4. 輪 4 — 三疑慮驗證(維護者要求再研一輪;2026-07-05)

### 4.1 疑慮①:adaptive 多輪追問在無狀態設計下會不會失控?——不會,反而是推薦形

- **LLM 呼叫本來就無狀態**([Atlan 2026](https://atlan.com/know/are-llms-stateless/)):
  連 LangGraph 每次也是把 context 重組進 prompt。差別只在「回合之間狀態存哪」(圖 blob vs DB 列)。
- 2026 記憶體研究([memory 控制](https://arxiv.org/pdf/2601.00821) 等):
  **「結構化、受治理的 context」優於「原始逐字稿重播」**(raw replay 放大 context 崩壞)。
  → 我們的槽位重建(phase + task_index + slots jsonb + 每槽有界追問 Q&A)正是推薦形,不是妥協。
- 追問受**資料飽和停止準則**約束(官方,上游研究 §7.3)→ 狀態成長有界。

### 4.2 疑慮②:與 2a 樂觀鎖並發怎麼接?——(B)直插,(A)要架橋

(B)回合服務走同一條文件 seam:agent 回合帶 revision token 寫入,衝突→409→現讀重試/上浮;
「agent 回合=version+1、人編輯=revision+1」(上游研究 §4 預埋)直接可用。
(A)的圖不知道文件變了,衝突不可見,需另造橋。

### 4.3 疑慮③:LangGraph 退役成本盤點(讀碼實測)——有足跡但有界,且**不必現在退**

| 端 | 足跡 |
|---|---|
| api 依賴 | `langgraph==1.2.5`、`langgraph-checkpoint-postgres`、`ag-ui-langgraph`(3 個套件)|
| api 碼 | `app/authoring/` 14 檔 + `copilotkit_live_app.py` + main/app_factory/router 接線 |
| api 測試 | 8/46 檔(test_graph_* 等)|
| web | `CopilotKitProvider` 全域掛載 + `/api/copilotkit` route + `InterruptHandlers` + 3-4 元件引用 |

- **重要事實**:intake 頁已是純表單、註解明言「不碰 CopilotKit」——產品實際已往表單/REST 回合漂移。
- **處置 = Strangler Fig**(對齊維護者 service-split-framework 原則):(B)引擎旁路蓋起,
  **深問純邏輯(STAR/5W2H 槽定義、prefill、indicator 品質分、prompts)move-only 抬進回合服務**;
  圖/AG-UI/checkpointer 等**編排層**待新引擎覆蓋後再退役(屆時一併清 web 端 provider)。
- **Temporal 反查**(durable execution 何時才需要;[官方](https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications)、
  [2026 指南](https://devstarsj.github.io/2026/03/24/temporal-durable-execution-workflows-microservices-guide-2026/)):
  適用輪廓=長時運算、外呼鏈重、一個邏輯交易跨多脆弱步驟。我們的回合=短請求
  (讀 DB→≤2 次 LLM→寫 DB),等待都是**人速**、狀態靜置 DB → 不需要 durable-execution 引擎。

## 5. 輪 5 — 2026 編排框架版圖(維護者指示:LangGraph 是舊決策,重新選;2026-07-05)

### 5.1 版圖掃描(權威比較文)

([Speakeasy 框架比較](https://www.speakeasy.com/blog/ai-agent-framework-comparison/)、
[AliceLabs 2026 production-tested 排名](https://alicelabs.ai/en/insights/best-ai-agent-frameworks-2026)、
[open-techstack LangGraph vs OpenAI SDK vs PydanticAI](https://open-techstack.com/blog/langgraph-vs-openai-agents-sdk-vs-pydanticai-2026/)、
[AWS Builder 選型指南](https://builder.aws.com/content/3AzsgG6TreTO3uLRqpWNxfEyUhe/picking-an-ai-agent-framework-in-2026))

| 候選 | 2026 定位 | 對本案 |
|---|---|---|
| LangGraph | 「複雜**有狀態** workflow 首選」;persistence/HITL 最成熟;學習曲線最陡 | 強項(私有 durable 圖狀態)被我們的判別場景(人隨時改文件→單一真相)**判定為反特性**(輪 3) |
| Claude Agent SDK | Anthropic-native 自主 agent harness(subagent/hooks/MCP) | 我們是 workflow 不是自主 agent;YAGNI |
| OpenAI Agents SDK | GPT 中心輕量 harness;2026-04 加沙箱/子代理 | provider 傾斜;同上 |
| CrewAI / AutoGen | 多 agent 角色協作 | 用不到 |
| **Pydantic AI** | 「type-safe Python + FastAPI 人體工學首選」;~17k stars;structured output 內建於 run loop | **與 repo 天然契合**(契約全 pydantic、FastAPI);見 5.2 |
| 無框架(own loop) | 2026 趨勢明言:「**less framework, more model**——好框架在變薄不變厚」 | 12-factor + Anthropic 雙背書;骨幹本就簡單 |

### 5.2 Pydantic AI 承重細節驗證(官方文件)

- **三種輸出模式**([官方](https://pydantic.dev/docs/ai/core-concepts/output/)):`ToolOutput`(預設,tool call)/
  **`NativeOutput` = provider 原生 structured output(受限解碼:「model is forced to only output
  text matching the provided JSON schema」)** / `PromptedOutput`(提示層降級)——
  **正好是輪 2 判準表的三層,現成的降級鏈**。
- **OpenRouter 有專屬 provider 類**(`OpenRouterProvider`,[官方](https://pydantic.dev/docs/ai/models/openai/))
  ——現有接線直接用。
- HITL deferred tools / durable 整合([Restate](https://pydantic.dev/articles/restate-durable-execution-pydanticai))
  都有但**我們不買**——只當 **typed client library** 用,不當編排框架用。

### 5.3 關鍵洞見:骨幹選 (B) 之後,「框架題」拆成兩個小題

1. **編排(骨幹)用什麼?** → **自己的碼**(FastAPI route + service + DB 進度列)。
   六階段軌道是顯式 Python,不需要編排框架。(12-factor own control flow;
   2026 趨勢「less framework」;Temporal/LangGraph 都是為我們沒有的問題設計的。)
2. **回合內 LLM 呼叫用什麼庫?** → 框架唯一真正幫得上忙的地方:typed structured output +
   retries + provider 切換。候選:現狀 `langchain_openai`(只當 HTTP client,無 structured
   output 人體工學)vs **Pydantic AI 當 `LlmPort` adapter 內裝**(NativeOutput 兌現
   `select_schema`;六邊形不破——domain 只認 port,adapter 內裝可換)。

**誠實記錄**:LangGraph 在 2026 泛用排名仍是「stateful workflow 安全牌」;我們偏離的理由
**不是它爛,是本案的共編需求使其核心價值變成反特性**(場景特定,非泛用判斷)。

## 6. 輪 6 — 深研:以「本案要解決的問題」為尺重新校準(維護者要求;2026-07-05)

### 6.0 問題定義重申(評判尺;**含維護者 2026-07-05 修正,以此版為準**)

> **「知道工作內容的人(員工)寫不出專業文件;寫得出專業文件的人(顧問)又貴又少。」**

**維護者修正(關鍵)**:**OCS 官方目錄 = 參考鷹架,不是天花板**。產品 = 每家公司/每個員工的
**客製化**職務說明書(同職稱各公司內容不同),且要**比官方公版更細**——頻率(多久一次)、
次數、等待時間、準備材料等細項。LLM 的定位 = **資深職務說明書顧問**:最高品質、最詳細、
會追細節、會抓漏。

三個死結(修正版):
①員工**漏說/說不完整** = 知識引出(elicitation)問題 → 官方目錄的真正用途在此:
**回憶輔助**(反推「你是不是也有做?」),不是對齊目標;
②**細節深度** = 官方公版沒有的細項槽位(頻率/次數/等待/材料)是**我們自己的設計空間**,
也是產品比公版值錢之處;既有 5W2H 架構正是容器,槽位表照「專業顧問會問什麼」擴;
③顧問不可規模化 → **LLM = 把顧問方法論規模化**,不是加聊天功能。

**對架構結論的權重修正**:
- **信任中軸重心翻轉**:目錄類受限解碼只管「引用/溯源」那塊(地基);
  **價值大頭在敘述類客製內容**,其品質機制 = 溯源到員工原話 + rubric + 人審(主菜)。
- **「抓漏」升格一級機制**:公版反推清單 + 資料飽和準則 + **覆蓋率門檻**
  (每任務細項槽位填到門檻才進下一個;確定性把關,LLM 負責問)。
- **新掛起問題**:客製細項要進文件正式欄位(動 ocs-contract)還是先塞敘述文字?影響契約,待裁示。

**評判尺:哪個架構最能保證文件正確性、可稽核性、訪談品質(含細節深度與抓漏)、人的主導權
——我們產的是承重文件,不是聊天紀錄。**

### 6.1 五路權威獨立收斂到同一個分工(核心發現)

| 權威(層級) | 原話/立場 |
|---|---|
| **Rasa CALM**(企業級對話 AI,N26 等受監管銀行在用;[官方](https://rasa.com/docs/learn/concepts/calm/)) | LLM 只做**理解**:「interpret the message in the context of the conversation」→ 產出**Commands**(小指令詞彙表);**確定性 Flows 掌全部業務邏輯**:「LLMs keep the conversation fluent but **don't guess your business logic**」;[2026 預測](https://rasa.com/blog/2026-conversational-ai-predictions):「LLM for understanding + Flows for decisions 將成 de facto 標準」 |
| **Microsoft Azure 架構中心**([官方](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)) | 「**關鍵業務邏輯應強制用確定性 workflow**」;下一步走哪「deterministically defined…**isn't a choice given to agents**」 |
| **Anthropic**(輪 1) | workflow 優先於自主 agent |
| **Harvey**($11B 法律 AI=高風險承重文件的同構先例;[平台](https://www.harvey.ai/platform)) | 針對「幻覺引註」failure mode 打造 grounded reasoning;輸出=**帶精確引註的 memo**(≈我們的溯源);agent 全程 **HITL checkpoints 供律師審**(≈顧問審回合) |
| **TOD 學術文獻**(任務導向對話,數十年積累;[ACM Computing Surveys 2026 綜述](https://dl.acm.org/doi/10.1145/3771090)、[E2E TOD 綜述](https://arxiv.org/pdf/2311.09008)) | 我們的訪談引擎=經典 TOD 管線:**NLU(理解)→ DST(對話狀態追蹤)→ Policy(下一步)→ NLG(措辭)**;LLM 時代=LLM 強化 NLU/DST,但**顯式狀態結構保留**;zero-shot DST 基本填槽可行、多輪易出問題 → 狀態放 LLM 外面 |

**分工收斂**:LLM=理解+措辭;確定性碼=狀態/流程/業務規則;狀態=顯式、可稽核、存外面;
高風險輸出=溯源+人審 checkpoint。**對映三死結**:①elicitation → LLM 正職(理解+追問);
②對映官方 → 確定性把關(受限解碼+溯源=Harvey 引註的對應物);
③方法論規模化 → **勞動部五面向腳本=CALM Flows 的字面對應**(方法論本身就是確定性流程)。

### 6.2 本輪帶來的新設計輸入(不只驗證,還有可偷的)

1. **Command 詞彙表模式**(CALM 實戰驗證):回合內 LLM 的輸出契約不是自由動作,而是
   **小指令集**(如 `SetSlot` / `Correct` / `Clarify` / `SkipTask`)——受限解碼直接可枚舉;
   這給了回合服務「LLM 輸出契約」的具體形狀。
2. **離題/更正是命名過的已解問題**(CALM conversation patterns):員工訪談到一半跳話題、
   改前面的答案——面板設計必須內建這兩個 pattern,不是邊角案例。
3. **TOD 詞彙**:我們的「進度列」=DST 的 dialogue state;「階段機」=Policy;
   直接繼承該文獻的評測方法(joint goal accuracy 等)當未來 eval 素材。

### 6.3 誠實記錄反向證據

Harvey 2026 [推出自主 agent 端到端起草](https://mlq.ai/news/harvey-a-launches-autonomous-agents-for-end-to-end-document-drafting/)——前沿確實在擴大自主性。但:
(a)它建立在多年 grounded 基建**之上**、且保留律師審 checkpoint;(b)法律起草的輸入是文件,
我們的輸入是**人腦裡的隱性知識**——訪談本質上必須互動。結論:不推翻 workflow-first,
但佐證「葉子 agentic 可漸進擴權」是對的升級形狀(骨幹不變,葉子隨信任加深放權)。

## 7. 輪 7 — 需求訪談(維護者;2026-07-05)

| 需求題 | 維護者裁示 | 架構意涵 |
|---|---|---|
| 黃金範本 | **沒有現成 → 研究合成**(工作分析方法論+實務範本→樣板給維護者審) | 樣板反推槽位表+rubric |
| 寫入節奏 | **靈活,無固定回合**——顧問問到一定程度先寫任務;或先列職責→深問→中途發現漏職責回頭補;寫了還會改 | **六階段=軟進度(宏觀),微觀導航=LLM 從有限指令集選**(`DraftSection`/`AskFollowUp`/`AddDuty`/`ReviseSection`/`AdvancePhase`…)=CALM Command 模式;靈活在指令選擇,安全在指令集枚舉+覆蓋率/飽和確定性檢查 |
| 修正權限 | **AI 提議+寫;人編輯/確認/取消**;對話中可彈選單讓人選/改(要研究) | staged proposal-apply(ADR 0015 對齊);+「對話中結構化 widget」研究題 |
| v1 對談者 | **員工**;做完後顧問看文件+訪談內容(審閱者) | 員工語氣/防呆;**溯源到原話=顧問稽核依據**,權重再升 |

**確立的研究議程**:R1 黃金範本合成(最優先,是其他一切的尺)· R2 指令詞彙表+覆蓋率/飽和設計
(mixed-initiative 訪談編排)· R3 提議+寫的 UX(staged 提議+對話中 widget)。

## 8. 輪 8 — R1 黃金範本合成第一稿(2026-07-05)

### 8.1 三路權威(互相印證)

- **O*NET 內容模型**(美國勞動部,取代 DOT 的國際最高權威;[量表](https://www.onetonline.org/help/online/scales)、[資料字典](https://www.onetcenter.org/dl_files/DataDictionary20_0.pdf)):
  任務逐條評 **Importance / Relevance / Frequency**;**core 任務判準 = relevance ≥67% 且
  importance ≥3.0**,其餘為 supplemental;Work Context 問卷=頻率/時間占比量表;
  Tools & Technology 獨立分類。
- **SHRM**(全球最大 HR 專業協會;[JD 指南](https://www.shrm.org/topics-tools/tools/job-descriptions)、[essential functions](https://www.shrm.org/topics-tools/tools/express-requests/job-descriptions-essential-functions)):
  essential functions 要寫**任務頻率、不做的後果、替代做法**;**時間占比加總 100%**;
  reporting relationships、working conditions;先做 job analysis(訪談現任者)。
- **中文圈實務**([104 人資工具包](https://blog.104.com.tw/hr-form-example-statement-of-work/)、公部門 DGPA 範例、MBA智库):
  七部分結構=工作識別/工作摘要/職責與任務/職權/績效標準/工作條件/工作規範;
  **工作比重**、督導與會報、溝通協作向上關係;1–3 頁。

**維護者直覺的細項全部有正式名分**:多久一次=O*NET task frequency;做幾次=volume(task
inventory);等多久=work context;準備什麼材料=inputs+Tools & Technology。

### 8.2 黃金範本骨架草案(章節層;⊕=OCS 之外的客製擴充)

1. 職務識別(職稱/部門/直屬主管/任職者/日期/版本)
2. 工作摘要(2–4 句存在目的;≈OCS job_description)
3. 職責→任務清單(⊕**每任務:工作比重%,加總100** + 頻率)
4. 每任務深描(OCS T/P/O/K/S 既有 + ⊕細項槽位表 8.3)
5. ⊕協作與從屬(向上報告/督導/跨部門協作/會報)
6. ⊕績效標準(每職責怎麼評)
7. ⊕工作條件(環境/工時型態/體力/出差)
8. 任職資格(學經歷/證照/態度;≈OCS A+prerequisites)

### 8.3 每任務細項槽位表草案(= 訪談深問的靶;各槽附值域與出處)

| 槽位 | 值域 | 出處 |
|---|---|---|
| frequency 頻率 | enum:每日/每週/每月/每季/每年/事件驅動(遇X才做) | O*NET |
| time_share 工作比重 | %(全任務加總=100) | SHRM/中文實務 |
| duration 單次耗時 | 時/天 | O*NET work context |
| volume 數量批次 | 一次處理幾件/多少量 | task inventory |
| trigger 觸發 | 排程/指派/事件 | FJA 條件(勞動部 FA 同源) |
| inputs 準備材料 | 材料/文件/資料來源 | 維護者原話+FJA |
| tools 工具系統 | 設備/軟體 | O*NET Tools & Tech |
| collaborators 協作對象 | 誰給輸入/誰收產出/會簽誰 | SHRM+中文實務 |
| wait_points 等待瓶頸 | 等誰/等多久 | 維護者原話+work context |
| exceptions 例外處理 | 常見困難+處置 | 勞動部指引③面向 |
| standards 完成標準 | 怎樣算做完/做好 | SHRM 後果+勞動部④面向 |
| outputs 產出 | (OCS O 既有) | 既有 |

### 8.4 實品樣張

骨架+槽位表已填成完整模擬樣張(軟體測試工程師,公版引用取自 repo 真資料 ISD2519-002v2):
**[`2026-07-05-golden-sample-software-tester.md`](2026-07-05-golden-sample-software-tester.md)**
——同時示範公版/客製兩層分野、抓漏實績、深問預算、覆蓋率自檢四機制。待維護者審。

### 8.5 兩個設計紅利(合成時浮現)

1. **深問預算分配有了原則**:借 O*NET core/supplemental 二分——先問到每任務的
   頻率+比重(便宜、快),**用重要度×比重決定哪些任務值得全套深問**;supplemental
   任務淺掃即可 → 訪談時長可控,員工不會被問到煩。
2. **schema 擴充問題更清晰**:8.2 的 ⊕ 項與 8.3 槽位是 OCS shape 沒有的
   → 契約題(進 ocs-contract 正式欄位 vs 敘述文字)現在有了具體清單可對著裁。

## 9. 輪 9 — R2 指令詞彙表 + 覆蓋率/飽和設計草案(2026-07-05)

> 樣張(§8.4)維護者暫定通過(v0,實作驗證中修)。

### 9.1 依據

- **CALM 實戰指令集只有 ~6 個**([官方參考](https://rasa.com/docs/reference/config/components/llm-command-generators/)):
  `start flow` / `set slot` / `disambiguate` / `search and reply` / `cancel flow` / `repeat`——
  **小詞彙表足以撐住銀行級對話**;詞彙表小=受限解碼 enum 小=可靠。
- **追問停止無標準判準**(2026 現況):[Nature 2026](https://www.nature.com/articles/s41598-026-46517-7)
  每回合判斷「要不要追問」;評準含 **justified skip**(該跳而跳=品質);
  [SparkMe](https://arxiv.org/pdf/2602.21136)、[LLM-as-an-Interviewer](https://arxiv.org/abs/2412.10424)
  無停止規則時得靠 72 回合硬上限(反面教材);evidence-based termination
  ([2604.14170](https://arxiv.org/pdf/2604.14170))=證據足夠即停。
  → **三重保險**:硬上限(cap)+ 覆蓋率門檻(確定性)+ LLM 飽和信號(判斷)。

### 9.2 訪談顧問指令詞彙表草案(每回合 LLM 輸出 1..n 指令;enum+參數 schema=受限解碼)

| 類 | 指令 | 語意 | 信任機制 |
|---|---|---|---|
| 理解 | `set_slot(task, slot, value, quote)` | 填槽;**quote=員工原話必填(溯源內建於指令)** | value 自由文字;quote 必須是逐字稿子串(可程式驗證)|
| 理解 | `correct_slot(…)` | 員工更正先前答案(CALM correction pattern)| 同上 |
| 理解 | `add_duty / add_task(name, quote)` | **抓漏升格**:發現公版外職責/任務 | 同上 |
| 推進 | `ask(question, target_slot)` | 追問(adaptive follow-up)| 受 9.3 三重保險節流 |
| 推進 | `ask_choice(question, options[])` | 彈選單 widget(結構化決策)| options 來自池=目錄類 enum |
| 推進 | `skip(target_slot, reason)` | justified skip(顯式記理由)| reason 落 trace 供稽核 |
| 推進 | `advance(next_focus)` | 換任務/階段(軟階段推進)| **覆蓋率門檻放行才生效**(確定性)|
| 寫入 | `draft_section(ref, content, sources[])` | 草擬文件段(標 AI 草稿)| **提議+寫**(staged;維護者裁示)|
| 寫入 | `revise_section(ref, content, reason, sources[])` | 回頭優化 | 同上;人改過的段 → 只提議 |
| 其他 | `clarify(options)` / `smalltalk_reply(text)` | 消歧 / 離題拉回(CALM patterns)| — |

### 9.3 停止/覆蓋 guard(確定性,掛在指令外——LLM 不能繞過)

1. **硬上限**:每槽追問 ≤2 次;每任務回合預算;全訪談軟預算(前端顯示進度)。
2. **覆蓋率門檻**:core 任務 12 槽、淺掃 4 槽(樣張附錄雛形);`advance` 未達門檻
   → 引擎拒絕並回缺口清單(LLM 只能續問或 justified skip)。
3. **飽和信號**:LLM 每回合帶 `saturation` 判斷(再問無新資訊);三者綜合決定放行。

### 9.4 一回合 trace 示例

```
員工:「上線前那兩天都在跑回歸,大概三百多條吧,自動的佔三分之二。」
LLM 指令輸出(受限解碼):
  set_slot(T2.2, volume, "回歸約300條;自動化200/手動100", quote="大概三百多條…自動的佔三分之二")
  set_slot(T2.2, frequency, "每雙週上線前密集2天", quote="上線前那兩天都在跑回歸")
  ask("自動化那部分的腳本是你自己維護嗎?大概多久要修一次?", target=T2.1.frequency)
引擎(確定性):驗 quote 為逐字稿子串 → 寫進度列 → T2.2 覆蓋 9/12 → 未達門檻,不放行 advance
  → 面板渲染下一題;文件側 T2.2 細項表即時長出兩格(標 AI 草稿)
```

## 10. 輪 10 — 四線並行深研統整(維護者指示 subagent 多路收集;2026-07-05)

> 執行紀錄:4 個研究 agent 並行;C(權限模型)完整回報,A/B/D 撞 session 上限由主線補研。

### 10.1 C 線:「人改過的段落只能提議」重審(維護者點名商榷)——**建議改軸**

**業界 2025–26 獨立收斂**(四家同構):Word Copilot(詞級 Track Changes)、Google Docs
Gemini(suggested edits,與人類協作者同一建議機制)、Cursor(staged diff + checkpoints)、
GitHub Copilot(PR suggestions)——**「AI 可以自由地寫,但寫進待審層,不直接覆蓋定稿」**。

**學術實證**(CHI/CSCW 2024–26):territoriality 真實存在(「你不會去碰別人的邏輯區塊」;
CHI 2026:「我真的很討厭它在我不在場時做事」);**手動整合 AI 建議比自動整合帶來顯著更高的
所有權感**;接受度條件=改動可見可區分、人有輕量 final say、不打斷心流、可逆可稽核。
確認疲勞是設計問題:「每一個不帶認知重量的核准,都在教育使用者核准只是形式」(Anthropic:
逐動作核准製造摩擦不必然帶來安全)。

**建議模型:「雙通道 + 風險分流 + 節點批審」**(取代「人改過=永久降級為提議」):

1. AI 自己寫、人沒碰過的段 → **直改** + 輕量標記 + 一鍵 undo;
2. 人碰過的段 → AI **照樣寫,但寫進建議層**(inline 新舊對照 badge)——不彈窗、不阻塞;
3. 審閱在**自然邊界**批次(小節談完/訪談尾聲總審;Accept all/逐條兩檔);
4. 低風險維度豁免(錯字/格式/術語一致性可直改+標記——實證「不影響我的聲音」);
5. 不可逆動作(刪整節/覆蓋已口頭確認的事實)永遠阻斷確認;
6. 全部落版本歷史;AI 寫入帶樂觀鎖,**衝突自動降級為建議**(「人正在編的段 AI 不直寫」
   不用規則硬編,版本衝突自然湧現)。

**軸的翻轉**:原設計把尊重主導權實作成「**限制 AI 寫入權**」;新模型實作成「**分流 AI
寫入目的地**」——AI 產出力不減、人的字未核准前一字不動、確認批次化。
反方誠實記錄:建議層實作比彈窗貴(緩解:與版本系統同構,v1 粗粒度=段落 badge+新舊對照
即可);雙態文件困惑(緩解:建議量預算化+尾聲清零);信任漸進自動調權(e)判 YAGNI 記縫。

### 10.2 A 線:專業顧問方法(主線補研)

- **BEI 系譜**:McClelland BEI ← Flanagan CIT(1954 原始出處);問法=**調查記者模式**:
  「當時情境?」「**具體是誰做**(probe the 'We')?」「確切做了什麼?」「結果?」「為何有效?」
  ——追問句可直接進 prompt 腳本;「probe the We」= 歸屬與抓漏技巧
  ([CIT 指南](https://www.hr-survey.com/Critical_Incident_Interview_Guide.htm)、
  [JVER CIT 論文](https://scholar.lib.vt.edu/ejournals/JVER/v25n1/stitt.html))。
- **Korn Ferry(Hay)三因子**:know-how / problem solving / accountability;
  input→throughput→output 框架([官方 PDF](https://www.kornferry.com/content/dam/kornferry/docs/pdfs/job-evaluation.pdf))。
  與勞動部 14 法工具箱互證(BEI/CIT 皆在列,上游研究 §7.4)。

### 10.3 B 線:格式獨立驗證(主線補研)

- **CIPD role profile** = purpose / principal accountabilities / K&E&S / context
  ([CIPD 角色設計](https://www.cipd.org/uk/the-people-profession/the-profession-map/how-it-works/role-design/))
  ——**8 章骨架通過獨立驗證,無重大缺漏**。
- 職評用 JD(Hay 系)提示一個候選欄位:**職務量化維度**(管理人數/預算規模)
  → 骨架加為**選填**欄位(職評超集項,v1 不強制)。

### 10.4 D 線:實作細節(主線補研)

- **quote 溯源有 2026 直接先例**:醫療領域 verbatim evidence 要求——
  「**quote 必須是空白正規化後的精確子串**」硬約束 + 自動驗證
  ([medRxiv 2026](https://www.medrxiv.org/content/10.64898/2026.03.03.26346690v1.full)、
  [Deterministic Quoting](https://mattyyeung.github.io/deterministic-quoting))。
  誠實風險:模型「定位 span」弱於「識別相關性」,傾向合成而非逐字
  ([attribution 綜述](https://arxiv.org/html/2508.15396v1))→ **修復策略**:驗證失敗
  retry 一次;仍失敗 → 槽值收下、quote 標「未驗證」降信任級,不阻塞訪談。
- **一回合多指令**:CALM 生產環境本來就每回合輸出指令序列 → 可行;
  結構可靠性由受限解碼保證,語義正確率進評測。
- **模擬受訪者評測**:TOD user simulator 是標準做法
  ([Reliable LLM User Simulator](https://arxiv.org/abs/2402.13374)),
  但有幻覺/跨回合不一致/[Sim2Real gap](https://arxiv.org/pdf/2603.11245) 坑
  → 模擬器要綁「員工 persona 卡+固定事實表」,量測槽位正確率/覆蓋率/追問品質;
  模擬只當回歸網,上線前配真人試訪。

### 10.5 後記:ADR 草案覆審(維護者定調「全新設計、不整合舊碼」;2026-07-05)

ADR 0023/0024/0025 草案對研究結果逐條覆審(尺=最新/最主流/大廠/論文都在用):
0023 除決定 6 外全數通過;**決定 6 改寫**——刪除「move-only 抬舊碼」承諾,新引擎全新實作,
既有圖降為純參考材料,舊資產(圖/AG-UI/checkpointer/CopilotKit provider/3 依賴)於新引擎
可用後一次清除。0024 決定 4 升級:adapter 內裝**首選 Pydantic AI**、spike 確認後汰換
`langchain_openai`(減層)。0025 無修改(四大廠收斂+CHI 實證,即「大廠都在用」的答案)。

## 11. 待決 / 下輪

**決策已凍結(2026-07-05)**:ADR **0023**(引擎骨幹=無狀態回合+軟階段+指令詞彙表,
原待決 1/2/3 皆由其涵蓋——tool=workflow 確定性步驟+回合內小呼叫;adaptive=指令+三重保險)
· **0024**(LLM 接線)· **0025**(共編權限)全數 Accepted。

剩餘(進 spec/plan 階段處理):

1. **立項 spec**:訪談引擎 v1 範圍切片(哪幾個階段先上、槽位表定版、指令參數 schema、
   面板 UI、進度列 DB schema、客製細項欄位 vs 敘述文字的契約裁決)。
2. **最小實作切片**(可先行,0024 第一消費者):`extract_tasks` 升 `select_schema`
   受限解碼版,接現行編輯器,不碰訪談 loop;同時建立對抗性驗收腳本與紀錄。
3. 黃金範本 v0 → 訪談腳本/rubric 的轉譯(spec 內做)。

## 12. 來源

**大廠官方**:[Anthropic Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) ·
[Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) ·
[Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) ·
[OpenRouter structured outputs 官方文件](https://openrouter.ai/docs/guides/features/structured-outputs) ·
[OpenRouter × Claude 官方 blog](https://openrouter.ai/blog/tutorials/claude-code-openrouter/) ·
[AWS 結構化輸出實務](https://builder.aws.com/content/2wzRXcEcE7u3LfukKwiYIf75Rpw/how-to-get-structured-output-from-llms-a-practical-guide) ·
[AWS + Outlines](https://aws.amazon.com/blogs/machine-learning/generate-structured-output-from-llms-with-dottxt-outlines-in-aws/)。
**2026 技術文**:[Collin Wilkins — Structured Outputs](https://collinwilkins.com/articles/structured-output) ·
[Pockit — LLM Structured Output 2026](https://pockit.tools/blog/llm-structured-output-complete-guide/) ·
[Mervin Praison — Anthropic playbook 整理](https://mer.vin/2026/05/when-not-to-build-ai-agents-anthropics-workflow-vs-agent-playbook/)。
**論文**:[Draft-Conditioned Constrained Decoding(2026)](https://arxiv.org/pdf/2603.03305) ·
[Memory 表徵對照(2026)](https://arxiv.org/pdf/2601.00821)。
**輪 3-4 增補**:[12-factor agents(HumanLayer 原文)](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-12-stateless-reducer.md) ·
[Starlog 12-factor 生產經驗](https://starlog.is/articles/ai-agents/humanlayer-12-factor-agents/) ·
[LangGraph durable execution 官方](https://docs.langchain.com/oss/python/langgraph/durable-execution) ·
[LangGraph 2026 評測](https://toolbrain.net/blog/langgraph-review-2026/) ·
[Temporal 官方 — beyond state machines](https://temporal.io/blog/temporal-replaces-state-machines-for-distributed-applications) ·
[Temporal 2026 指南](https://devstarsj.github.io/2026/03/24/temporal-durable-execution-workflows-microservices-guide-2026/) ·
[Atlan — Are LLMs stateless?](https://atlan.com/know/are-llms-stateless/)。
**Repo 內**:上游研究 2026-07-02 · ADR 0007/0008/0015/0020/0022 · `docs/contract-strategy.md`。
