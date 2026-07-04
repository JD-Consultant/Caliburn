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

## 3. 待決 / 下輪

1. **引擎骨幹**:workflow 骨幹的載體——沿用/修對齊既有 LangGraph 圖 vs 重寫輕量編排?
   (ADR 0007 保留 LangGraph;ADR 0020 §4 又解綁;需權衡 checkpointer/interrupt 資產 vs 舊 shape 債)
2. **tool 協定**:indexer 工具(檢索 / items:match)進引擎是「LLM function-calling tools」
   還是「workflow 確定性步驟」?(Anthropic workflow-first 傾向後者,LLM 只填槽)
3. **兩條寫入路收斂**(縫 2)+ adaptive 判斷器具體設計(縫 3)。
4. **最小實作切片**收斂:候選 = `extract_tasks` 升 `select_schema`(受限解碼版,接現行編輯器,
   不碰訪談 loop)——待引擎骨幹討論後定。

## 4. 來源

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
**論文**:[Draft-Conditioned Constrained Decoding(2026)](https://arxiv.org/pdf/2603.03305)。
**Repo 內**:上游研究 2026-07-02 · ADR 0007/0008/0015/0020/0022 · `docs/contract-strategy.md`。
