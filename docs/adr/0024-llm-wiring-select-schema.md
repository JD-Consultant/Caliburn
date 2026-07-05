# ADR 0024 — LLM 接線:LlmPort 增 select_schema + 受限解碼路徑判準

- **狀態**:Accepted(2026-07-05)。
- **研究依據**:[`../specs/2026-07-05-llm-integration-wiring-research.md`](../specs/2026-07-05-llm-integration-wiring-research.md)
  (輪 1–2:受限解碼機制、OpenRouter 透傳查證、判準表;輪 5:Pydantic AI 承重驗證)。
- **關聯**:六邊形分層=ADR 0008;訪談引擎(指令輸出的消費者)=ADR 0023。

## 脈絡

現行 `LlmPort` 只有 `complete_text` / `complete_json`,全在「提示層」——`complete_json`
是 prompt 要 JSON + 事後 parse;`extract_tasks` 靠事後 `i in known` 丟棄幻覺 id(事後防禦)。

2026 新事實:**native structured output(受限解碼)已 GA**——schema/enum 編成狀態機,
解碼每步只准合法 token,100% 保證、值也被約束;OpenAI/Gemini/Anthropic 皆原生支援,
**OpenRouter 透傳可得**(底層不支援即報錯、不靜默降級)。信任中軸:目錄類(池內 id、
指令 enum)值承重 → 需要硬保證;敘述類(客製內容)品質靠溯源+rubric+人審,不靠解碼。

## 決定

1. **`LlmPort` 新增第三句話型**(既有兩方法不動):
   `async def select_schema(self, prompt: str, schema: dict, *, role: str = "cheap") -> Any`
   ——語意「輸出必須符合此 schema(含 enum)」;domain 只表達意圖,provider 由 adapter 兌現。
2. **路徑判準**(由上往下取第一列;完整表見研究 §2.3):
   值承重(目錄類 id/指令 enum)→ `select_schema` → OpenRouter `json_schema+strict`、
   底層挑**有原生受限解碼**的模型;敘述/結構不承重 → 現狀 per-role 提示層。
   Escalation 槽(不預建):Anthropic SDK 直連(驗收連續失敗或引擎中樞需 thinking+tool
   loop 品質時)、自架+Outlines(資料主權要求時)。
3. **Guard(對齊校準紀律)**:既有事後 `i in known` **不拆**,降級為 defense-in-depth
   保險絲——理論上永不觸發,**觸發即 log error**(= 底層模型未兌現受限解碼)並觸發
   escalation 評估。選定底層模型須跑**對抗性驗收腳本**(誘導池外 id,零池外=過),
   紀錄留 `docs/specs/`;換模型 = 重跑驗收,不改碼。
4. **adapter 內裝:首選 Pydantic AI**(2026 type-safe Python 主流,與 repo pydantic
   契約同血統;`NativeOutput/ToolOutput/PromptedOutput` 現成降級鏈 + `OpenRouterProvider`;
   **只當 typed client library,不當編排框架**),實作 spike 確認後**順勢汰換
   `langchain_openai` 舊依賴**(全新設計、減層);備選=直用 openai SDK 指 OpenRouter。
   六邊形保證此選擇不外漏:domain 只認 port。

## 後果

- ✅ 目錄類從「事後丟棄」升級為「**生成時就編不出池外 id**」;ADR 0023 的指令詞彙表
  直接受同一機制保護;provider 鎖定被推遲到 config,隨時可換。
- ⚠️ 新增驗收紀律(選模型=跑腳本留紀錄);OpenRouter strict 對部分模型可能非真受限
  解碼——由驗收腳本與保險絲攔截,連換兩模型失敗才升直連。
- 📌 per-role 成本分層(deep/indicator/cheap)照舊;本 ADR 不動現有任何呼叫點,
  第一個消費者(如 extract_tasks 升級)在 plan 裡定。
