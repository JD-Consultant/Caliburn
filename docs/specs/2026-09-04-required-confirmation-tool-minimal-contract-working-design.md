# 必要確認 Tool 的最小契約（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q009`
- 階段：PAUSED；父前提由 `LLM-Q011` 重驗中
- 父決策：`LLM-Q006`～`LLM-Q008`
- 效力：只比較模型可見輸入與 Runtime 回傳責任；不授權 schema code、UI、provider pin、測試或 production

> 本文保留為方案歷史；選項與自由文字 UI 不等於 durable pending run。Current 生命週期問題見 [`2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md`](2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md)。

## 1. 本輪唯一問題

專用 confirmation Tool 最少應讓模型填哪些內容，又應把哪些既有資訊交給 Runtime／framework 自動注入，才能可靠表達必要確認並避免大型 schema、虛構 ID 與無效欄位？

## 2. 已固定的產品邊界

1. 此 Tool 只處理符合 `LLM-Q006` 四項條件、沒有員工決定便無法安全繼續的真正 blocking 問題。
2. 普通訪談問題仍是自然語言 final response，不使用此 Tool。
3. Tool 只取得回答，不直接修改 Memory、JD 或待審 changeset。
4. 員工必須能不受預設選項限制，以自己的文字回答。
5. 第一版優先正確、清楚與低錯誤率，不為了複製任何廠商完整 UI 而增加未使用欄位。

## 3. 官方事實

### F1．OpenAI 建議不要讓模型填系統已知資料

OpenAI Function calling 的現行 best practices 明確要求：Tool 名稱、參數與使用時機要清楚；應由程式提供的既知參數不要交給模型填；可用 enum／object structure 排除無效狀態；初始可見 Tool 數量應保持精簡。`strict: true` 可要求 Tool input 符合 schema，但 strict schema 的所有 properties 都必須列為 required，optional 要以 nullable 表達。

### F2．Anthropic 的成熟 clarification 形狀是問題＋選項＋自由文字逃生口

Claude Agent SDK 的 `AskUserQuestion` 讓模型提供問題、短標籤、2～4 個選項的 label／description 與 multi-select 設定；應用程式另外顯示 `Other`，並把員工真正輸入的自由文字送回 Claude。這證明「模型提出清楚候選、應用程式永遠保留自訂回答」是已公開使用的成熟互動形狀。

### F3．LangChain 可把 Runtime 資訊從模型 schema 隱藏

LangChain `ToolRuntime` 可把 state、context、Store、execution info、thread／run／Tool call identity 注入 Tool；`runtime` 參數不會出現在送給模型的 Tool schema。Tool 回傳 plain string 時，framework 會轉成模型可讀的 `ToolMessage`。因此 thread ID、interrupt ID、document scope、時間、重試次數與目前 graph state 都不應由模型提供。

### F4．LangGraph 不提供 Caliburn 專用澄清 schema

LangGraph 提供 `interrupt(payload)`／`Command(resume=...)` 與 Tool 內 interrupt，但 payload 的產品內容由應用程式定義。LangChain HITL middleware 主要審核即將執行的 Tool call，不能取代「顧問需要員工釐清職務事實」的問題內容。

## 4. 三個方案

| 方案 | 模型可見輸入 | 優點 | 主要問題 |
|---|---|---|---|
| **A．Anthropic 形狀的最小子集（建議）** | 一次一題：`question`＋2～4 個 `{label, description}` 選項 | 一個 Tool、無 union／nullable mode；選項可清楚說明不同解讀；Runtime 永遠加自由文字回答；最符合 `LLM-Q006` 已要求「至少兩個實質分歧」 | 第一版不支援一呼叫多題或 multi-select；真正需要時須重開 |
| B．完整複製 `AskUserQuestion` | `questions[]`、`header`、options、`multiSelect`，可一次 1～4 題 | 已有 Anthropic 成熟先例，彈性最高、可批次降低人機往返 | schema 與模型責任較大；Caliburn 尚未證明需要批次、多選、preview 或模型填 header，容易重演過度複雜 |
| C．拆成自由文字 Tool＋選項 Tool | 一個 Tool 只有 `question`；另一個再接受 options | 每個 schema 個別簡單 | 增加 Tool surface 與選擇錯誤；open-text Tool 容易被拿來阻塞普通訪談問題，而真正 blocker 依既有判準本來就有至少兩個分歧 |

## 5. 建議 A 的概念契約

暫用描述性名稱 `request_employee_confirmation`；名稱尚待 G3 一併裁決。

### 5.1 模型只負責

- `question`：一個清楚、自成一體、員工可以直接回答的必要問題；
- `options`：2～4 個真實可行的解讀；每個只有：
  - `label`：短而互斥的答案標籤；
  - `description`：選擇代表的實際意思或影響。

模型不填 `header`、`multiSelect`、`Other`、reason code、Memory／Task／Duty／JD ID、branch、Skill ID、quote、thread／run／interrupt ID、時間、狀態、scope、retry 或顯示樣式。

### 5.2 Runtime／framework 自動負責

- 透過 `ToolRuntime` 取得目前 thread、document scope、graph state 與 Tool call identity；
- 驗證只有一題、選項數量有界、label 不重複、內容非空；
- 提供固定產品標題「需要你的確認」；
- 永遠允許員工輸入自訂文字，不要求模型產生 `Other` 選項；
- 以 `interrupt(payload)` 保存並等待；
- 員工回答後，以 `Command(resume=...)` 恢復；
- 將員工的實際答案轉成簡短 Tool result 交回模型，不要求模型解析 UI index，也不直接改其他 authority。

### 5.3 回傳給模型

概念上只回傳員工實際回答的文字。例如員工選擇某個 label，就回傳該 label 所代表的答案；員工自訂輸入，就回傳原文字。UI event、selection index 與 interrupt identity 留在 Runtime，不塞進模型 context。

canonical conversation 是否另外保存這次回答、如何投影到員工可見歷史，是後續 conversation／projection 題；本題不偷決定。

## 6. 為何目前不採完整 Anthropic schema

這不是否定 Anthropic 的設計，而是採其已證明有效的核心形狀，再依 Caliburn 目前產品約束縮小：

- `LLM-Q006` 已要求真正 blocker 至少有兩個實質解讀，因此無需另做 open-text-only blocking Tool；
- 第一版每次只有一個當前 blocking decision，不需 `questions[]` batching；
- 固定產品標題可由 UI／Runtime 產生，不需模型填 `header`；
- 自由文字由應用程式永遠提供，不需把 `Other` 交給模型；
- 尚無代表性情境證明 multi-select 是必要的；「兩者皆是」仍可作一個明確選項或由員工自訂回答。

以上縮減是 **Caliburn mapping**，不是跨廠固定 schema。若真實情境證明多題 batching 或 multi-select 可明顯改善效果／成本，依重開條件補回，而不是預先加入。

## 7. 建議裁決

建議暫時採方案 A：一個 `request_employee_confirmation` Tool；模型只填一個問題與 2～4 個 label／description 選項。Runtime 透過 LangChain `ToolRuntime` 注入其餘資訊、加入自由文字回答入口、執行 LangGraph interrupt／resume，最後只把員工實際答案回給模型。

下一個 gate 不應直接寫 production schema；應先決定 Tool description／system instruction 如何精確重述 `LLM-Q006` 的「何時用、何時不用」，因為官方資料明確指出 Tool 描述與使用說明會直接影響模型是否正確呼叫。

### 7.1 G3 裁決

Product Owner 於 2026-09-04 暫時核准方案 A，包括：一個 Tool、一次一題、模型只提供 `question` 與 2～4 個 `{label, description}`，其餘 identity／scope／自由文字入口／interrupt／resume／Tool result 均由 Runtime／framework 負責。

本裁決只把最小責任邊界升為 Working Decision；仍不授權 production schema、UI 或實作。下一個 topic 為 `LLM-Q010`：如何以官方建議撰寫 Tool description 與 system instruction，讓模型只在真正 blocker 時呼叫。

## 8. 重開條件

- 代表性情境需要同時回答多個互相依賴的 blockers；
- 沒有 multi-select 導致員工頻繁只能用自訂文字修正選項；
- 兩個 Tool 經 characterization 顯著降低誤呼叫或 schema error；
- provider 的 strict Tool schema 不支援此最小結構；
- UI／產品決策改變「自由文字永遠可用」或一題一 interrupt 的要求。

## 9. 官方來源

### OpenAI

- [Function calling：Tool schema、strict mode 與 function design best practices](https://developers.openai.com/api/docs/guides/function-calling)

### Anthropic

- [Claude Agent SDK：`AskUserQuestion` 的 question／option／free-text 契約](https://code.claude.com/docs/en/agent-sdk/user-input)
- [Claude Agent SDK TypeScript reference：`AskUserQuestionInput`](https://code.claude.com/docs/en/agent-sdk/typescript)

### LangChain／LangGraph

- [LangChain Tools：`ToolRuntime` 注入、隱藏模型參數與 Tool return](https://docs.langchain.com/oss/python/langchain/tools)
- [LangGraph Interrupts：Tool 內 interrupt 與 resume](https://docs.langchain.com/oss/python/langgraph/interrupts)
