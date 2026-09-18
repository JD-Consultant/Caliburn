# 跨廠 LLM 顧問系統全流程與框架分層（Working Research）

- **日期**：2026-09-04
- **狀態**：Working Research；父層、Capability Catalogue、zero-to-product 流程、P3 responsibility placement 與精簡版方案 A 已獲 Owner G3 核准
- **Topic ID**：`LLM-Q002`
- **Owner**：Product Owner
- **產品成果**：員工透過長期訪談與 AI 共同維護一份高品質、由員工核准的職務說明書（JD）
- **本輪目的**：先完整回答一個現代 LLM 顧問系統需要哪些層、每層由誰負責，再決定模型與框架；不從舊程式或舊元件名稱倒推架構
- **目前決策**：能力 inventory、代表性情境與 P3「有界單一顧問＋deterministic seams」責任配置已形成 G3 Working Baseline；P3 是符合跨廠共同方向的 Caliburn 映射，不是廠商共同發布的標準名稱或完整模板
- **下一個 gate**：進入 G4，定義精簡版 A 的最小 runtime contract、責任邊界與可判定的 bounded characterization；尚不授權精確版本 pin、Tool／Skill／Prompt schema、spike 或 production 施工

## 1. 本輪不是在做什麼

本輪不做以下事情：

- 不保留、整合或逐一對照舊元件；成熟框架能否承接效果，要在產品責任確定後才判斷。
- 不因 production 目前用了某套框架，就預設未來仍使用它。
- 不把某一家 API 的參數、某一個框架 class 或某份舊 schema 當成產品需求。
- 不選正式模型、不跑付費 API、不修改 production、不接 RAG、不設計多 agent。
- 不把「模型可替換」誤解成所有模型能力完全相同。

既有 `LLM-Q001` 只回答 provider capability 與 Tool loop，無法代表本題的完整 LLM 系統。它的 G5 工作應暫停，直到本題父層責任與框架方向收斂。

## 2. 研究方法與共識標籤

### 2.1 來源優先序

1. OpenAI 與 Anthropic 的目前官方 API、agent、Skills、Tools、Memory、context 與 runtime 文件；
2. Google、AWS 與 Microsoft 的目前官方 agent 架構作三角驗證；
3. 候選框架自己的目前官方文件；
4. repo 既有研究只用來確認產品成果與已研究範圍，不用來證明外部框架事實。

### 2.2 標籤

- **跨廠共同**：至少三個一手生態系獨立採用相同責任或機制。
- **強趨勢**：OpenAI、Anthropic 均採用，且至少一個成熟框架提供對應 primitive；但實作細節尚未完全統一。
- **條件式**：只在工具很多、run 很長、存在外部副作用或其他明確條件時需要。
- **廠商／框架選項**：成熟可用，但不能冒充跨廠共同要求。
- **產品決策**：外部框架不能替 Caliburn 決定的產品語意或 authority。
- **Unknown**：公開文件不足，只有 bounded characterization／spike 能回答。

研究停止條件遵守 [`decision-process.md`](../decision-process.md)：新增來源已不再產生新的父層、主要矛盾已列出，剩餘差異可以在最多三個實質方案中比較。

## 3. 跨廠共同的最小整體流程

OpenAI 將 agent 基礎拆成 Model、Tools、Instructions；Anthropic 區分由程式控制路徑的 workflow 與由模型動態選擇行動的 agent；Google ADK、LangChain、PydanticAI 與 Microsoft Agent Framework 都公開同樣的「模型呼叫 ↔ Tool execution」迴圈及外圍 runtime/context 責任。共同形狀可整理為：

```text
員工輸入
  ↓
應用識別目前文件／thread、權限、執行設定
  ↓
Context 組裝
  ├─ 穩定 instructions／policy
  ├─ 近期 conversation 與必要 compaction
  ├─ 按需召回的長期 Memory
  ├─ 目前 JD／工作區的必要視圖
  ├─ 本輪載入的 Skills
  └─ 本輪可用 Tools 與 response format
  ↓
選定並 pin 本次 model/provider/settings
  ↓
有界 agent loop
  ├─ 模型回覆員工
  ├─ 模型要求讀取／操作 Tool
  ├─ Runtime 執行、驗證並回傳 Tool result
  └─ 必要時有限修正；達成停止條件後結束
  ↓
產出自然語言＋typed effects／待審變更
  ↓
Schema、domain、權限與安全驗證
  ↓
員工查看／編輯／接受／拒絕；必要澄清可 interrupt 後 resume
  ↓
保存 conversation、Memory、執行狀態、核准結果與 trace
```

這不是要求每個箭頭都呼叫一次模型，也不是固定 state machine。一次 run 可以包含多個 model step 和 deterministic step；簡單回合也可以只呼叫一次模型。

主要官方依據：

- [OpenAI：Current model guidance](https://developers.openai.com/api/docs/guides/latest-model) 與 [Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)；
- [Anthropic：Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)；
- [Google ADK：Event loop](https://adk.dev/runtime/event-loop/)；
- [LangChain：Context engineering in agents](https://docs.langchain.com/oss/python/langchain/context-engineering)；
- [Microsoft Agent Framework：Agent pipeline architecture](https://learn.microsoft.com/en-us/agent-framework/agents/agent-pipeline)；
- [PydanticAI overview](https://pydantic.dev/docs/ai/overview/)。

### 3.1 產品成果與技術責任之間必須有完整能力層

「顧問要做什麼」只涵蓋 domain／產品能力，不能代表完整 LLM 系統。正式選模型與框架前，必須先建立 **framework-independent Capability Catalogue**，至少從七個面向檢查是否漏項：

| 能力面向 | 代表性問題；不是最終完整清單 |
|---|---|
| 1. 產品／顧問效果 | 能否自然訪談、理解完整工作、發現缺口與衝突、按需分析 JD、完成高品質文件？ |
| 2. Agent 認知與行動 | 能否選模型、使用 Skills、規劃下一步、呼叫 Tools、處理結果、停止或要求人決定？ |
| 3. 資訊／Context／Memory | 能否保存 conversation、修訂與找回長期資訊、組裝正確 context、壓縮但不永久遺失必要資料？ |
| 4. Application control／Human authority | 能否安全操作 JD 工作區、顯示差異、讓員工編輯／接受／拒絕，並阻止未核准內容正式生效？ |
| 5. Runtime／可靠性／成本 | 能否 bounded retry、限制 turns／tokens／時間／費用、避免重複副作用、故障後 resume？ |
| 6. Observability／診斷 | 能否追蹤 run、model、context 組裝、Skill／Tool 的可用與實際使用、輸入輸出、錯誤、延遲、tokens 與成本？ |
| 7. 安全／治理／演進 | 能否保護敏感員工資料、區分可信 instructions 與不可信內容、pin／版本化模型／Prompt／Skill／Tool，並支援日後測試與稽核？ |

這份 catalogue 的目的不是把所有能力第一版都做完，而是**先看見全貌，再用兩條互不取代的軸逐項分類**：

- 業界證據軸：`Cross-vendor common`／`Strong trend`／`Product-specific`／`Vendor/framework option`；
- Caliburn release 軸：`First-version candidate`／`Conditional`／`Deferred`。

`First-version candidate` 也不是寫死的 `Required now`；它必須再通過代表性情境、較簡單等價方案與成本／複雜度審核。完整定義與 G2 證據草案見 §3.4。

每個能力後續都必須記錄：產品效果、跨廠證據、責任層、成熟 primitive、Caliburn 必須補的內容、驗證方式與重開條件。只有這樣才能先找共識機制，再討論 Tool、Skill、Prompt 與資料結構，而不是從框架 API 倒推需求。

#### 3.1.1 「記錄用了什麼」屬於能力，不是事後加普通 log

跨廠共同方向是以 session／trace／span 觀測 agent execution：model requests、Tool calls、結果、錯誤、用量、成本與延遲都應可關聯。AWS AgentCore 還將 request context、Memory operation、Tool input/output 與 skill invocation 納入 trace／evaluation evidence；Anthropic Managed Agents 的 session viewer 可檢查 model、context usage、Tool calls、失敗與成本；LangChain、PydanticAI 與 Microsoft Agent Framework 都提供 model／Tool／workflow 的 OpenTelemetry 或等價 tracing。[AWS AgentCore observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-telemetry.html)、[Anthropic session events](https://platform.claude.com/docs/en/managed-agents/events-and-streaming)、[LangSmith observability](https://docs.langchain.com/oss/python/langchain/observability)、[PydanticAI Harness observability](https://pydantic.dev/docs/ai/harness/)、[Microsoft Agent pipeline](https://learn.microsoft.com/en-us/agent-framework/agents/agent-pipeline)

但「完整原始 Prompt／所有員工內容一律寫進 log」不是跨廠共同要求，也可能造成敏感資料外洩。父層能力應要求：

- 可知道本次使用哪個 model/provider/settings 與版本；
- 可知道 context **由哪些來源類別／版本／IDs 組成**，以及是否發生 compaction／cache；
- 可知道哪些 Skills／Tools 被提供、載入與實際呼叫；
- 可關聯 tool call、result、retry、error、latency、tokens 與 cost；
- 敏感 payload 的全文紀錄必須可關閉或遮罩，預設先記 metadata／reference，而不是無條件複製全部內容。

Skill 使用紀錄由 Runtime／framework instrumentation 產生，不能要求模型自行填「我使用了哪個 Skill」作為真相。各家 trace schema 並未完全統一，因此「可觀測效果」是共同能力；確切欄位要到 framework comparison 才決定。

### 3.2 從 0 開始的設計順序：跨廠公開流程審核

公開資料沒有一套由所有廠商共同命名、逐步完全相同的「標準 agent 開發法」。下列順序是對目前官方流程的**跨來源歸納**，不是宣稱任何一家內部逐字照此執行：

1. **先定使用者問題、成果、成功訊號與不做事項。**Amazon Working Backwards 與 Microsoft Agent Design Framework 都要求從使用者與 outcome 出發，而不是先列工具或選框架。
2. **先判斷問題是否真的需要 agent。**Anthropic 要求從最簡單 prompt／augmented LLM 開始，只有較簡單方案不足時才增加 workflow／agent 複雜度；Google 也先依 task、latency、cost 與 human involvement 判斷非 agent、single-agent 或其他 pattern。
3. **建立 framework-independent requirements／capabilities。**Microsoft 要先盤點 trigger、channel、data、tools、flow、instructions、governance 與 evaluation；Google 先定 workload requirements 再選 pattern；AWS 的 scoping 先定目標、資料、風險、成本、可行性與 success metrics，再進 model selection。
4. **逐段決定 AI 與 deterministic code 的責任。**Microsoft 明確建議把 input／transform／output 各段依容許變異與精確度需求映射到 unstructured AI 或 deterministic implementation；不能因產品含 LLM 就把所有規則交給模型。
5. **再選最簡單能覆蓋需求的 pattern、模型與 framework。**Google 建議早期先以 single agent 精煉核心 prompt／Tools；AWS 建議 PoC 從最簡單方式驗證價值，再依需要加入 RAG、agent 或 fine-tuning；OpenAI 也建議以最小 prompt 保留產品契約，依代表性案例調整 model、reasoning、Tools 與 output format，並用 Agents SDK 等成熟 primitive 避免重建通用 orchestration。
6. **以薄、可觀察的垂直情境驗證核心價值。**AWS 建議 PoC 維持最小平台、以 hypothesis → experiment → measurement → iteration 驗證；Anthropic 說早期可先用 manual testing、dogfooding 與回饋快速前進，規模與變更增加後再建立正式 eval。這支持「第一版不先造完整 eval 平台」，不支持完全不定義代表性情境或 pass／fail。
7. **方向確認後才正式化並小步施工。**Microsoft ADR 要求重大決策保存 context、options、trade-offs、status 與 supersede history；Google review 先審整體合理性與主要設計，再以可獨立審核的小型變更交付。

官方依據：[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6)、[Anthropic Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)、[Anthropic agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)、[AWS Generative AI lifecycle](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lifecycle.html)、[AWS PoC development](https://docs.aws.amazon.com/prescriptive-guidance/latest/gen-ai-lifecycle-operational-excellence/dev-experimenting.html)、[Google agent design patterns](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)、[Microsoft Agent Design Framework](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/agent-design-canvas-framework)、[Microsoft Map agent flows to requirements](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/architecture/map-agent-flows)、[Microsoft ADR](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)、[Google small changes](https://google.github.io/eng-practices/review/developer/small-cls.html)。

#### 3.2.1 對 Caliburn 現行流程的審核

`G0 → G1 → G2 → G3 → G4 → 必要 G5 → G6 → G7 → G8` 的方向符合上述公開做法：先產品目的、再單一決策與官方證據、再可驗證設計，最後才 spike／正式化／垂直施工。`current-decisions.md` 作閱讀入口、Accepted ADR 不改寫而以 successor 取代，也符合 Microsoft 公開的 decision-log 原則。

目前不需要重做整套流程，但要補強兩個 gate：

1. **AI placement／complexity gate**：Capability Catalogue 完成後，先逐項判斷 `deterministic code／單次 model call／固定 workflow／bounded single agent／human interrupt`；只有效果需要時才增加 agentic complexity。這一步必須早於 framework winner。
2. **Representative scenario gate**：framework comparison 前先固定少量「產品成功／重要失敗」情境，至少覆蓋長訪談延續、員工更正、Memory 找回、JD 待審編輯、拒絕回退、衝突需確認與成本／錯誤可見。第一版可人工跑與人工判讀，不要求先建正式 eval 平台。

建議的實際順序因此是：

```text
North Star
  → 代表性產品情境
  → 開放式 Capability Catalogue
  → AI／deterministic／human responsibility placement
  → architecture pattern
  → model／framework capability fit
  → 最薄垂直 slice
  → 依證據擴充
```

19 層地圖與七面向 catalogue 都是**完整性檢查與選型輸入**，不是「第一版要實作 19 個 subsystem」。若把清單直接變成 class、table、service 或每層一個模型呼叫，就會偏離各家「先簡單、只在效果可證明時增加複雜度」的共同方向。

### 3.3 最小代表性產品情境（Working Baseline）

OpenAI、Anthropic、Microsoft 與 Google 的共同方向，是在選 architecture pattern、模型或 framework 前，先以代表性真實工作情境定義「什麼算成功、哪些失敗不可接受」，再用同一批情境比較完整 system／harness，而不是只比較模型單次回答。**下列七組具體情境是 Caliburn 的產品 mapping，不是宣稱任何廠商使用完全相同的七分類。**

本節只固定目前已對齊的**可觀察產品效果與禁止失敗**：

- 「詢問員工」「共同編輯」「工作理解」「待審」均是白話產品概念，不預先指定 UI、資料表、物理文件數、Tool、模型呼叫數或 framework class；
- 所有項目都是可經後續證據與 Product Owner 討論翻案的 Working Baseline，不能因本節出現某個名詞就直接施工；
- 後續 mechanism 若能以更簡單或效果更好的方式達成同一結果，可以提出研究與取捨；不得未討論便改變產品效果；
- 第一輪可人工走查與人工判讀，不表示現在就要建立大型自動 eval 平台。

| ID | 員工情境 | 必須看見的產品效果 | 禁止失敗／本節沒有決定的事 |
|---|---|---|---|
| `S1` 從模糊敘述開始 | 員工以零散、口語、順序不固定的方式描述職位與工作。 | 顧問逐步理解實際工作、保留新線索、選擇有資訊價值的方向追問；員工能知道目前大致訪談方向、已了解與仍待了解之處，但不顯示假精確百分比。 | 資訊不足時不得猜滿 JD、強迫立即歸入 Duty／Task／OPKS，或把訪談做成不可回跳的固定 wizard。進度如何持久化與呈現尚未決定。 |
| `S2` 長訪談、相似案例與續談 | 員工跨很多回合描述多個表面相似但細節可能不同的工作案例，之後關閉並重新開啟同一份文件。 | 顧問仍能取得重要案例差異與目前有效理解，能辨識重複、補充與新主題；不因長對話或整理而永久遺失任何會影響 JD 的工作細節，且只使用這名員工／這份 JD 的資料。 | 不得每個案例固定生成一個 Task 或一筆永久 Memory，也不得以每輪重送全部 transcript／全部 Memory 當唯一解法。本節不指定 Memory 表徵、檢索演算法或 Store。 |
| `S3` 自然更正、衝突與歧義 | 員工像一般聊天一樣說「我剛才說錯了，是處長核准」，或新說法與先前理解衝突。 | 若上下文足夠，顧問修正目前理解；若不知道更正對象、存在多種會影響分析的解釋，或答案只能由員工提供，顧問必須**先詢問員工**，取得回答後才繼續依賴該資訊。 | 不得由 LLM 私下選一個方便答案。詢問可以是一般聊天、選項加自訂回答或其他成熟形式；「需要你的確認」只是可能的產品呈現，不是本節指定的元件或固定 UI。 |
| `S4` 先理解工作，再形成 JD | 訪談逐步累積員工做過的案例、流程、例外、成果與責任邊界。 | 顧問先形成足以理解職務全貌的目前認識，再判斷何時值得產生或局部修訂 JD；JD 萃取穩定、重要、職務層級的工作，並可按需使用 Task／Duty／工作細節／OPKS 等分析方法。 | 不得把每則訊息或每個案例直接變成 JD 項目，也不得預設每回合都必須編輯 JD。何時算資訊足夠、是否保存獨立「工作理解」artifact、使用幾次模型呼叫，仍待後續研究。 |
| `S5` AI 與員工共同編輯最新內容 | AI 與員工持續處理同一份 JD，且 AI 已產生尚待員工查看的變更。 | 員工與 AI 都以最新工作內容為基礎繼續；AI 來源的變更必須可被員工看見並審核，不能偷偷成為核准內容；員工能修改 AI 寫的內容，也能接受或拒絕。 | 本節不固定底層是一個或多個 physical state、不固定逐項或整組審核、不固定按鈕與 diff 版型。任何 mechanism 都必須維持「共同編輯最新內容＋AI 變更需人工審核」的效果。 |
| `S6` 員工直接修改、同時操作與失敗恢復 | 員工可直接修改 JD；另一回合 AI 可能正在分析或遇到 model／Tool／資料錯誤。 | 下一輪顧問能看見員工自上次分析後造成的最新變化；系統避免 AI 與員工同時寫入造成不合理覆蓋；成功、失敗或停止後，聊天與 JD 都回到可繼續使用的狀態，既有訊息與待審工作不遺失。 | 不得讓分析錯誤永久鎖死 UI、無界重試或靜默覆蓋。鎖定、版本、rebase、stale 與 rollback 的具體方式尚未決定。 |
| `S7` 完整 JD 品質盤點 | 訪談已累積大量工作資訊，目前 JD 看似已完成大部分內容。 | 在明確的全面製作／品質檢查時，系統能確實處理這份 JD scope 內全部目前有效、會影響 JD 的工作資訊，找出仍未涵蓋、只部分涵蓋、衝突、重複、邊界重疊或抽象錯誤，再把需要的 JD 修訂交給員工審核。 | 不得用 semantic top-k、最近資料或「模型覺得看夠了」冒充全量處理；也不表示日常每回合都載入全部 Memory。本節不指定一次放入 Context、分頁或分批彙整。 |

七組情境共同套用下列檢查面，而不是再拆出更多產品流程：

1. **品質**：不捏造員工工作；JD 清楚、可維護、完整且不把案例清單當職務結構。
2. **Authority／隔離**：AI 不自行核准；不同員工／JD 不混用資料。
3. **可恢復性**：關閉、恢復、錯誤與有限重試後仍維持一致、可繼續的使用狀態。
4. **成本／Observability**：能由可信 Runtime 看見實際 model、Context 類型、掛載的 Skill／Tool、重試、token、延遲與成本；不要求模型自行填寫 receipt。
5. **可比較性**：後續候選模型、framework 與 architecture pattern 必須接受同一情境集與邊界比較，不能各自換成有利於自己的問題。

方法依據：[OpenAI contextual evals：Specify → Measure → Improve](https://openai.com/index/evals-drive-next-chapter-of-ai/)、[Anthropic agent evals：以真實失敗與多回合 trajectory 建立代表性 tasks](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)、[Google：先定 task／latency／cost／human involvement 再選 pattern](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)、[Microsoft：以代表性 scenarios、expected behavior 與 acceptance criteria 驗證 agent](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/architecture/evaluation-frameworks)。

> **Production authority 差異（不可偷渡施工）**：`S6` 的新版產品方向要求 AI 分析期間避免員工與 AI 同時修改 JD；目前 Accepted ADR 0060 §5 決定 13 則允許 pending AI 回答期間直接編輯與匯出。本文只保存後續架構的 Working 方向，不會自行改變 production；最後採用何種 interaction／serialization mechanism，必須在能力與責任 placement 收斂後由 successor ADR 明確取代相關決定。

### 3.4 候選 Capability Inventory（分類尚待證據審核）

Product Owner 已確認下列能力方向在概念上正確，但特別要求：**不能因清單看起來合理，就直接把它們寫死為 `Required now`。**證據審核後也不能把「大廠有提供」誤寫成「Caliburn 第一版必須施工」。

原本把 `Cross-vendor common`、`Caliburn product requirement`、`Conditional` 放在同一分類軸是錯的：例如 durable conversation 可以同時是跨廠共同能力與 Caliburn 第一版候選必要能力；「每項 AI JD 變更都須員工審核」則是 Caliburn 產品 authority，即使 HITL 是跨廠共同 primitive，也不能把兩者當成同一件事。因此後續一律分成兩軸：

1. **業界證據軸**
   - `Cross-vendor common`：多家最新官方產品／SDK 明確提供或要求的共同責任；
   - `Strong trend`：多家現行方案已採用，但尚不足以宣稱所有系統都必須如此；
   - `Product-specific`：由高品質 JD 與員工 authority 反推的 Caliburn 效果，不冒充廠商共識；
   - `Vendor/framework option`：特定 provider／framework primitive，或只有在門檻出現時才有價值。
2. **Caliburn release 軸**
   - `First-version candidate`：目前看似不可缺少，但仍須證明它是代表性情境的必要條件，且沒有更簡單等價方案；
   - `Conditional`：只有 context、工具數、資料量、風險、併發或執行時間達門檻才啟用；
   - `Deferred`：產品明確延後，或第一版無法證明效果／成本值得。

兩軸互不取代。業界共同能力仍可能因第一版情境用不到而延後；Caliburn 特有能力也可能因直接決定產品是否成立而成為第一版必要。**本節的 release 判斷全是待 Owner 審核的候選，不是施工授權。**

候選能力全貌如下；每一列是待審核的 capability family，不代表一個元件、資料表、模型呼叫或已選實作：

| 面向 | 候選能力家族 |
|---|---|
| 顧問／產品效果 | 自然且可調整的訪談；理解實際工作並區分案例與穩定職務；處理更正、未知與衝突並先詢問員工；質性呈現訪談方向與缺口；專業職務分析與 JD 撰寫；完整涵蓋、去重與一致性盤點。 |
| Agent 認知與行動 | 單一主顧問選擇下一步、是否繼續理解及何時值得編輯 JD；按需取得分析方法與 Tools；read-before-write；理解 Tool 結果與精確錯誤；有限修正、停止或轉為詢問員工。 |
| Conversation／Memory／Context | 長期保存並恢復訪談；可修訂且保留必要細節的工作知識；有界組裝近期對話、相關資訊與最新 JD 工作狀態；按需搜尋／深讀；同一 JD scope 的完整列舉；不同 JD 隔離。 |
| Application control／Human authority | AI 與員工處理最新 JD 工作內容；AI 來源變更清楚可見且必須審核；員工可編輯、接受或拒絕；需要事實時先詢問並可恢復；避免同時修改造成不合理覆蓋，終止後回到可用狀態。 |
| Runtime／可靠性／成本／輸出 | model／provider capability 檢查與單一 run 內穩定選擇；typed input／Tool／effect／error；deterministic validation／authority；durable state、冪等與故障恢復；有限 turns／retries／tokens／time／cost；可理解事件狀態；deterministic JD read／export。 |
| Observability／安全／治理／演進 | 關聯 run、model、settings、Context 組成、Skill／Tool 提供與使用、錯誤、重試、token、延遲與成本；敏感內容遮罩／保留政策；可信 instruction 與不可信資料分離；最小 Tool 權限；model／Prompt／Skill／Tool／contract 版本化；使用同一代表性情境重跑與比較。 |

上一輪口頭列出的 compaction、semantic／hybrid index、deferred Tool／Skill loading、prompt caching、分批盤點、CAS／rebase、durable structured confirmation 與 background continuation，暫時只保留為**可能的條件式機制**；RAG／Reference、附件／多模態、自動核准、多 Agent／投票／自動 routing、remote MCP／computer use、能力級別 A、下游招募／KPI／訓練文件生成、跨 JD Memory／多人／雲端與大型自動 eval 平台，維持第一版排除或延後。這些分類同樣要經官方證據重驗，不能因列在本段就視為定案。

#### 3.4.1 跨廠共同基線：共識的是責任，不是 Caliburn 的欄位或 class

以下結論只採 2026-09-04 可查到的官方產品／SDK 文件；framework 文件只用來確認可承接哪些 mechanism，不拿來替產品定義需求。本輪把 `Cross-vendor common` 採嚴格標準：OpenAI、Anthropic、Google、AWS、Microsoft **五家皆有現行官方能力或明確責任邊界支持同一方向，且沒有查到相反建議**。這仍不表示 API、資料結構或名稱完全相同；若只看到部分廠商採用，一律降為 `Strong trend`。

| 能力責任 | 業界證據判斷 | 證據邊界 |
|---|---|---|
| 明確 instructions、模型呼叫、Tool 介面與有終止條件的 agent loop | `Cross-vendor common`（5/5） | OpenAI 將 agent 基礎整理為 model、tools、instructions，並要求 exit conditions；Anthropic 同樣將 model、tools、environment／feedback loop 分開，且建議從最簡單方案開始；Google ADK、AWS Harness 與 Microsoft Agent Framework 都提供相同父層責任，但組裝 API 不同。[OpenAI practical guide](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/)、[Anthropic Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)、[Google ADK agents](https://adk-labs.github.io/adk-docs/agents/)、[AWS Harness vs Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html)、[Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/) |
| durable session／conversation 與 scope 隔離 | `Cross-vendor common`（5/5） | OpenAI Sessions 會在 runs 間取回及追加對話；Anthropic Managed Agents 的 session history 持久到明確刪除；Google Session 保存單一 conversation 的 events／state；AWS Runtime 以 session 隔離與續接 invocation；Microsoft agents 以 session/context providers 管理延續資料。它們共同要求「對話連續性不能只靠單次 context window」，但 retention 與 storage owner 各家不同。[OpenAI Sessions](https://openai.github.io/openai-agents-python/sessions/)、[Anthropic session events](https://platform.claude.com/docs/en/managed-agents/events-and-streaming)、[Google ADK sessions](https://adk-labs.github.io/adk-docs/sessions/)、[AWS isolated sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html)、[Microsoft agent pipeline](https://learn.microsoft.com/en-us/agent-framework/agents/agent-pipeline) |
| Context 是每次呼叫的有界組裝，不等於完整持久資料 | `Cross-vendor common`（5/5） | Anthropic 明確把 context engineering 定義為每次推理所需資訊的策展；Google 把 session/state/memory 與 invocation context 分開；OpenAI 允許在 model call 前篩選輸入；AWS Harness 明列每次輸入由 system prompt、history、retrieved memory、Skill 與 allowed Tools 組成並提供 truncation limits；Microsoft 把 history provider 與額外 context providers 分開。[Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[Google ADK context](https://adk-labs.github.io/adk-docs/context/)、[OpenAI running agents](https://openai.github.io/openai-agents-python/running_agents/)、[AWS Harness operations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-operations.html)、[Microsoft agent pipeline](https://learn.microsoft.com/en-us/agent-framework/agents/agent-pipeline) |
| 模型提出 typed Tool call；應用／Runtime 執行並回傳結果或精確錯誤 | `Cross-vendor common`（5/5） | OpenAI function calling、Anthropic client tools、Google callbacks/tool context、AWS Harness tools 與 Microsoft middleware 都把模型意圖和實際副作用分開。Structured／strict schema 只保證形狀，不能取代 domain validation。[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)、[Anthropic tool-use contract](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)、[Google ADK callbacks](https://adk-labs.github.io/adk-docs/callbacks/)、[AWS Harness tools](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-tools.html)、[Microsoft middleware](https://learn.microsoft.com/en-us/agent-framework/agents/middleware/) |
| 高影響操作或必要人類輸入可 pause／approve／reject／resume | `Cross-vendor common`（5/5） | OpenAI `RunState`、Anthropic permission policy、Google `RequestInput`、Microsoft Tool approval／durable extension 與 AWS inline client function 均提供中斷後續接；具體哪些 JD 變更必須審核仍是 Caliburn 政策。[OpenAI HITL](https://openai.github.io/openai-agents-python/human_in_the_loop/)、[Anthropic permission policies](https://platform.claude.com/docs/en/managed-agents/permission-policies)、[Google human input](https://adk-labs.github.io/adk-docs/graphs/human-input/)、[Microsoft tool approval](https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval)、[AWS Harness tools](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-tools.html) |
| deterministic validation／policy／permission boundary | `Cross-vendor common`（5/5） | Anthropic、Google、AWS 與 Microsoft 都要求在模型外執行權限、policy、tool guardrail 或 middleware；OpenAI 也把 guardrails 與 tool execution 納入 Runner。共識是「模型輸出不能自行成為 authority」，不是共同的 JD invariant。[Anthropic guardrails](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks)、[Google ADK safety](https://adk-labs.github.io/adk-docs/safety/)、[AWS AgentCore overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)、[Microsoft middleware](https://learn.microsoft.com/en-us/agent-framework/agents/middleware/)、[OpenAI practical guide](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/) |
| bounded errors／retries／turns 與可恢復的失敗 | `Cross-vendor common`（5/5） | OpenAI 提供 `max_turns`、model-visible tool errors 與 paused `RunState`；Anthropic 定義 stop reasons、tool errors 與 `pause_turn`；Google／Microsoft／AWS 也以 session、workflow、callbacks 或 runtime 接住錯誤與續跑。各家的 retry taxonomy 不同，不能直接假設 exactly-once。[OpenAI running agents](https://openai.github.io/openai-agents-python/running_agents/)、[Anthropic tool troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use)、[Google ADK callbacks](https://adk-labs.github.io/adk-docs/callbacks/)、[Microsoft checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)、[AWS isolated sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html) |
| traces／logs／metrics 與敏感資料控制 | `Cross-vendor common`（5/5） | OpenAI tracing 包含 model、Tool、handoff、guardrail；Anthropic session event stream 顯示 model request、thinking、Tool 與成本；Google、AWS 與 Microsoft 均提供或整合 logs／metrics／traces。共同責任是能診斷真實 trajectory 並控制敏感 payload；精確事件 schema 是 framework 選項。[OpenAI tracing](https://openai.github.io/openai-agents-python/tracing/)、[Anthropic session events](https://platform.claude.com/docs/en/managed-agents/events-and-streaming)、[Google ADK observability](https://adk-labs.github.io/adk-docs/observability/)、[AWS observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)、[Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/) |
| 用代表性工作與 trajectory 驗證整體效果 | `Cross-vendor common`（5/5） | OpenAI、Anthropic、Google、AWS 與 Microsoft 都提供以 tasks／scenarios、行動軌跡或 session 結果改善 agent 的能力；這不等於第一版要先造大型自動 eval 平台。[OpenAI contextual evals](https://openai.com/index/evals-drive-next-chapter-of-ai/)、[Anthropic agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)、[Google ADK evaluation](https://adk-labs.github.io/adk-docs/evaluate/)、[AWS AgentCore Harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)、[Microsoft evaluation frameworks](https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/architecture/evaluation-frameworks) |

#### 3.4.2 強趨勢與條件式機制：不能因大廠有功能就第一版全開

| 能力／機制 | 業界證據判斷 | 第一版判斷原則 |
|---|---|---|
| 統一 model interface＋provider capability profile | `Strong trend` | OpenAI Agents SDK、AWS AgentCore、Microsoft Agent Framework、LangChain 與 PydanticAI 均能接多模型，但 OpenAI 官方也明示非 OpenAI provider 對 Responses／structured features 的支援不同。因此第一版候選是「替換模型時先驗能力」，不是假裝所有模型等價或先做自動 router。[OpenAI model providers](https://openai.github.io/openai-agents-python/models/)、[Microsoft model providers](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/model-providers/) |
| transcript/session 與可搜尋、可修訂 long-term memory 分責 | `Strong trend` | Google ADK、AWS AgentCore Memory、Microsoft context providers 與 Anthropic memory tool 都提供此方向；產品是否需要獨立 semantic memory、何時更新及如何表徵，仍須由情境驗證，不能只因 SDK 有 Store 就施工。[Google ADK memory](https://adk-labs.github.io/adk-docs/sessions/memory/)、[AWS Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-get-started.html)、[Microsoft context providers](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/context-providers/)、[Anthropic memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) |
| versioned Skills／按需載入方法與資源 | `Strong trend` | OpenAI、Anthropic 與 Google 均已有 Skills／progressive disclosure，但它仍不是所有 agent 的必要 layer。若 Caliburn 的 Task／Duty／OPKS 方法無法用短 instructions 穩定維持，才成為第一版候選。[OpenAI Skills](https://developers.openai.com/api/docs/guides/tools-skills)、[Anthropic Skills](https://platform.claude.com/docs/en/managed-agents/skills)、[Google ADK Skills](https://adk-labs.github.io/adk-docs/skills/) |
| read-before-write＋小型 editor／patch operation | `Strong trend` | OpenAI apply-patch 與 Anthropic text editor 都採先讀目前內容、再由模型提出結構化編輯、應用執行並回傳結果。這支持 Caliburn 用受控 JD workspace Tool；具體 operation、diff 與核准粒度仍是產品設計。[OpenAI apply patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)、[Anthropic text editor](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool) |
| durable workflow checkpoint／interrupt | `Strong trend`，且是否需要為 `Conditional` | 長工作、跨 process 等待人或 crash resume 時很有價值；單次短呼叫不需要。OpenAI `RunState`、Microsoft checkpoint/durable extension、AWS session 與 LangGraph persistence 都提供 primitive。[OpenAI HITL](https://openai.github.io/openai-agents-python/human_in_the_loop/)、[Microsoft checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)、[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) |
| prompt caching | `Vendor/framework option`／`Conditional` | 只降低穩定重複 prefix 的成本，不減少 context 內容；是否值得取決於 prefix 穩定度與實際命中率。[OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)、[Anthropic tool-context guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context) |
| compaction／context editing | `Vendor/framework option`／`Conditional` | 只在長對話逼近 context／成本／延遲門檻時啟用；不能壓縮 authoritative Memory 後刪掉唯一細節。[OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)、[Anthropic context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)、[Google ADK compaction](https://adk-labs.github.io/adk-docs/context/compaction/) |
| Tool／Skill search 或 deferred loading | `Strong trend`，是否需要為 `Conditional` | 只在可用 Tool／Skill 目錄已造成明顯 context 壓力時啟用。Anthropic 公開建議約 20+ Tools 或 baseline context 已明顯時再加 Tool Search；不是第一天就造 routing subsystem。[OpenAI Tool Search](https://developers.openai.com/api/docs/guides/tools-tool-search)、[Anthropic manage tool context](https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context) |
| semantic／hybrid index | `Vendor/framework option`／`Conditional` | 當 exact／metadata／small-directory routing 已無法可靠找回資料，才以代表性情境證明需要；它不能替代全面盤點時的 exact enumeration。[Google ADK memory](https://adk-labs.github.io/adk-docs/sessions/memory/)、[AWS Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-get-started.html) |
| CAS／rebase、background continuation、分批全面盤點 | `Conditional` | 分別只在允許 concurrent writes、工作超出互動生命週期、或全量資料無法在一次有界處理時需要；目前沒有證據支持把它們一律列為第一版 subsystem。 |

#### 3.4.3 Caliburn 產品能力：大廠 primitive 可承接 mechanism，不能替我們定義語意

下列不是 OpenAI／Anthropic 等廠商會替 Caliburn 決定的通用能力；它們是否為第一版必要，要回到 `S1`～`S7` 與高品質 JD 的目的判斷：

| Caliburn 產品能力 | 可借用的成熟 mechanism | 仍由 Caliburn 定義的內容 |
|---|---|---|
| 自然、可回跳、以實際工作為中心的訪談 | single-agent loop、conversation session、Skills、HITL | 何時追問、何時先理解而不寫 JD、何種資訊足以形成職務層級結論。 |
| 區分工作案例與穩定職務，持續修正對員工工作的理解 | session＋long-term memory＋on-demand retrieval | 工作知識要保存哪些細節、如何辨識案例重複／補充／矛盾，以及哪些內容會影響 JD。 |
| 依工作全貌撰寫 Duty／Task／工作細節／OPKS 並保持適當抽象 | Skills、structured effects、workspace Tools | 職務分析方法、欄位語意、關聯與品質標準。 |
| 完整涵蓋、去重、一致性與邊界盤點 | bounded workflow、exact listing／batching、deterministic checks | 何謂「這名員工的所有有效工作資訊」、何時啟動全面盤點及何謂覆蓋充分。 |
| AI 與員工共同處理最新 JD；AI 變更必須看得見並經員工審核 | editor tools、diff、interrupt／approval、durable state | pending／accepted／rejected 的 authority、審核粒度、員工直接編輯與 AI 後續理解。 |
| 訪談方向、一般待了解與必須先詢問員工的問題 | session state、structured human input | 哪些問題會阻斷分析、如何用白話呈現而不製造假進度。 |
| deterministic JD read／export | typed models、domain commands、export adapter | Caliburn 的 JD 契約與匯出格式。 |

因此「第一版不可缺少」不能只靠廠商票數決定。候選能力必須同時通過：

1. 對 `S1`～`S7` 至少一個不可接受失敗有直接防護；
2. 拿掉後，無法以更簡單 mechanism 達成相同可觀察效果；
3. 官方證據或代表性情境能說明其責任邊界；
4. 成本、延遲與複雜度與第一版價值相稱；
5. 不把未證明需要的 vendor feature 變成新的 subsystem。

#### 3.4.4 第一版候選基線（G3 Working Baseline，不是寫死需求）

目前證據只足以提出下列**能力層候選**，不指定 class、table、Tool 數、模型呼叫數或 framework winner：

- 可恢復且每份 JD 隔離的 conversation/session；
- 清楚且版本可辨識的 instructions、單一 bounded agent loop 與可設定模型；
- 每次 model step 的有界 Context 組裝；
- 小型 typed Tool／effect／error 邊界，由 Runtime 執行及驗證；
- AI JD 操作可見、可由員工審核，遇到只有員工能回答的歧義先詢問；
- 失敗後 UI／run 可恢復，並有限制 turns、retries、time、tokens／cost；
- 能追查 model、settings、Context 類型、Tool／Skill 提供與使用、錯誤、重試、token、延遲與成本的最小 observability；
- 以 `S1`～`S7` 做人工可重跑的整體情境查核；
- Caliburn 的職務訪談、工作理解、JD 分析、完整盤點與 authority 語意。

下列目前**不能**因概念合理就升格為第一版必做：獨立 semantic Memory 表徵、embedding／RAG、compaction、prompt caching、Tool Search、完整 durable workflow、CAS／rebase、background continuation、多模型 routing、全面自動 eval 平台。它們須在相應壓力或代表性失敗出現後重開；其中 RAG／Reference 另受 Product Owner 明確延後約束。

Product Owner 於 2026-09-04 回覆「OK，繼續」，核准以「業界證據」與「Caliburn release」兩軸作為 Working Baseline，並同意第一版能力只能依後續證據調整、不得寫死。這項核准不授權施工，也不表示 §3.4.4 每列已成不可翻案需求。

### 3.5 Responsibility placement（G3 Working Baseline）

#### 3.5.1 先分清「責任」與「誰來寫機械碼」

本節的四欄不是任何單一廠商的現成模板；`P3` 也是本文為方便比較而取的代號。它們是把 §3.4 的跨廠共同責任與強趨勢映射到 Caliburn，不能對外宣稱為某個名叫 P3 的業界標準。它的證據邊界如下：

- OpenAI 目前官方 Model guidance 明列：模型可推理與要求使用 Tool，但 application 仍負責實際執行 Tool 與管理 pending work；也建議先準備可審核結果，再在會改變結果或造成外部影響的邊界取得 approval。Responses API 則把 application 自有程式暴露成 strongly typed custom tools，並由 client 回傳 Tool 結果或 approval 決定。[OpenAI current model guidance](https://developers.openai.com/api/docs/guides/latest-model)、[OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- Anthropic 的 client Tool 契約是模型提出結構化請求、application 執行並回傳結果；Managed Agents 進一步把負責推理的 brain、負責執行的 hands、負責 session／context 的 harness 分開。[Anthropic Tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)、[Anthropic Managed Agents architecture](https://www.anthropic.com/engineering/managed-agents)
- Microsoft 明確要求逐段依可容許變異選擇 generative 或 deterministic implementation；Google 建議先以 single agent 精煉 prompt／Tools，只有工作確實需要時才增加固定 workflow 或多 agent；AWS 則明列 managed harness 只驗 request structure，caller authorization、input／model configuration validation 與 trusted Skill source 仍是 application 責任。[Microsoft map agent flows](https://learn.microsoft.com/en-us/agents/architecture/map-agent-flows)、[Google agent design patterns](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)、[AWS Harness security](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-security.html)

逐條核對後，必須把「共同事實」與「本文推導」分開：

| 底層方向 | 證據判斷 | 不可過度宣稱的部分 |
|---|---|---|
| 模型處理開放式語意、規劃並選擇 Tool；Tool／application 回傳環境結果 | `Cross-vendor common` | 各家 Tool schema、loop API 與自動執行範圍不同。 |
| Runtime／harness 承接 session、context、Tool pairing、failure handling、middleware／trace 等通用 execution machinery | `Cross-vendor common` | 沒有共同 class、checkpoint 格式或 persistence API；應依框架正式能力選擇。 |
| application 在 deterministic 邊界驗證 scope、authorization、輸入與副作用 | `Cross-vendor common` | 廠商不可能替 Caliburn 定義何者是合法 Duty／Task／JD authority。 |
| 高影響、主觀或需要本人事實的地方可停下取得 human input／approval | `Cross-vendor common` | 「所有 AI JD 變更都須員工審核」是 Caliburn 已同意的產品政策，不是所有廠商對所有產品的固定規則。 |
| 先用簡單、可組合的單一 agent／混合式流程，只有證據顯示不足時才增加固定 workflow 或 multi-agent | `Strong trend` | Anthropic 與 Google 最明確；其他廠商提供相容 primitive，但沒有五家共同發布同一句強制規則。 |

所以，本文只能下這個嚴格結論：**P3 的責任邊界符合目前跨廠共同方向，P3 的完整組合則是 Caliburn 根據產品情境做出的 synthesis。**它不是自行發明底層機制，但「如何把共同機制組成 Caliburn」必然仍是產品架構決策。

這裡的「跨廠共同」是**責任方向共同**，不是 native API 完全相同。例如 OpenAI 有 Conversations／Agents SDK state，Anthropic 核心 Messages API 仍是 stateless，另由 Managed Agents session 提供持久生命週期；各家也都有 HITL pattern，但沒有共同的 approval wire protocol。可攜設計因此要依賴 framework／adapter 統一所需效果，不能把任一家欄位名稱假裝成產業標準。[OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state)、[Anthropic Messages](https://platform.claude.com/docs/en/build-with-claude/working-with-messages)、[Anthropic permission policies](https://platform.claude.com/docs/en/managed-agents/permission-policies)

因此「Caliburn 負責一項政策」不等於「Caliburn 自己重寫 framework」。例如，Caliburn 決定所有 AI JD 變更需要員工審核；真正的 pause／resume、Tool call pairing、checkpoint 與 trace 應優先交給成熟 primitive。反過來，framework 能提供 approval middleware，也不代表它能替產品決定哪些內容算正確 JD 或何時正式生效。

四個**主動責任者**是：

1. **模型**：處理無法靠固定規則完成的語意理解、判斷、規劃與文字生成；
2. **成熟 framework／Runtime**：承接跨產品通用的 agent execution machinery；
3. **deterministic Caliburn code**：保證精確 scope、權限、資料關聯、副作用與產品 authority；
4. **員工**：提供只有本人知道的事實，並決定 AI 來源內容是否成為正式 JD。

另有一類**治理內容**而不是第五個執行者：Caliburn 的 product policy、base instructions、職務分析 Skills 與品質 rubric。其內容由產品定義，Runtime 負責版本化與按需載入，模型負責運用；凡是不可容許變異的規則，仍須由 deterministic code 強制。Runtime trace 能證明哪些資源被提供、載入或顯式呼叫，不能證明模型內部「真的照著想過」，更不能要求模型自行回填使用紀錄。

#### 3.5.2 跨廠證據支持的 placement rule

| 問題性質 | 預設責任 | 理由與邊界 |
|---|---|---|
| 自然語言含義、案例是否代表穩定職務、下一個訪談方向、JD 如何以專業語言表達 | 模型 | 需要處理模糊、開放與高變異語意；以 product instructions／Skills 約束，不以大量 `if/else` 假裝可完全確定化。 |
| model↔Tool loop、message pairing、structured parsing、context hooks、streaming、interrupt／resume、checkpoint、通用 call limits 與 tracing | 成熟 framework／Runtime | 這些是跨產品重複的 execution machinery；框架已有 primitive 時優先使用並驗證，不重寫第二套 loop／state。 |
| canonical scope、可信 ID／版本／actor、關聯合法性、權限、冪等、副作用、硬預算、正式 JD authority、deterministic export | deterministic Caliburn code | Schema conforming 不代表內容真實或關聯合法；模型與 generic framework 都不知道 Caliburn 的 domain invariant。可由 framework hook／middleware 執行，但規則本身仍屬產品。 |
| 員工本人事實、歧義的真實答案、AI 變更的接受／修改後接受／拒絕 | 員工 | 模型不能自行補足只有員工知道的資訊，也不能核准自己的輸出；不是每個普通問題都需 workflow interrupt，只有缺少答案會造成錯誤繼續時才要求先回答。 |

這是**預設分配，不是僵硬規則**。若某個輸出只容許唯一答案，就往 deterministic 移；若規則無法窮舉且需理解上下文，就往模型移；若只有人能提供真相或承擔決定，就停給員工。Microsoft 的 dynamic／deterministic guidance、OpenAI 的 rules-based guardrails＋human intervention，以及 Google 的 workload／cost／human-involvement pattern selection 都支持這個判斷方法。

#### 3.5.3 套到 `S1`～`S7` 的責任矩陣

| 能力 | 模型負責 | framework／Runtime 負責 | deterministic Caliburn code 負責 | 員工負責 |
|---|---|---|---|---|
| 輸入與長訪談 | 理解本輪話語與指涉 | session、history、stream、斷線續接 | canonical 順序、文件 scope、只接收允許的輸入 | 自然描述工作、補充與更正 |
| 目前對工作的認識 | 從新資訊辨識新增、補充、重複、衝突與失效內容 | 提供 conversation／Memory primitive、context hook 與持久化 | scope 隔離、可信 metadata、合法讀寫與必要 exact enumeration | 透過對話確認或糾正事實；不直接維護內部 Memory |
| Context 組裝與找回 | 判斷還要讀什麼、需要時使用搜尋／讀取能力 | 有界組裝 history、Memory、Skills、Tools 與目前 JD 視圖 | 保證查詢只落在本文件、返回 canonical 資料並施加 limits | 不需手動挑 context |
| 顧問方法與 Skills | 選擇並運用當下需要的訪談、Task、Duty、工作細節或 OPKS 方法 | catalog、按需載入、版本、提供／載入／顯式呼叫 trace | allowlist、可信來源與不可變硬規則 | 不需知道內部 Skill ID |
| 訪談方向與待了解問題 | 決定下一個重要方向；辨識何時資訊不足或互相衝突 | 維持 loop；必要時 pause／resume | 保存可恢復狀態並阻止不能安全繼續的 transition | 回答只有本人知道的內容；一般問題仍走自然聊天 |
| 是否及如何修改 JD | 依目前工作全貌判斷是否值得修改，產生專業內容及受控操作 | Tool definitions、dispatch、result pairing、structured effects | 注入可信 scope／版本；驗證關聯；把操作套到可見待審工作面 | 不必每輪催促 AI 寫 JD |
| JD 共同編輯與審核 | 看見員工最近修改後的內容；可在尚待審內容上繼續合理編輯 | editor／patch 與 HITL primitive、durable wait | pending／accepted／rejected／stale authority、原子 changeset 與衝突規則 | 直接編輯自己的內容；接受、修改後接受或拒絕 AI 內容 |
| Tool 錯誤與修正 | 依精確、可行動錯誤做有限修正 | bounded loop、validation feedback、通用 retry／stop | 分類錯誤、replay safety、冪等、總 attempts／time／token／cost cap | 只有機器無法解決且答案屬員工時才介入 |
| 最終完整品質盤點 | 評估語意覆蓋、抽象層級、重複、一致性與專業品質 | 提供有界的讀取／分批流程 primitive | 保證全部有效範圍可被列舉、沒有漏批次，並執行硬 invariant | 審核最終 JD；品質判斷不能被冒充為自動保證 |
| 回覆、UI 與匯出 | 產生顧問回覆與 AI 變更理由 | streaming 與 typed event／output parsing | 穩定 UI projection、狀態、錯誤呈現與 deterministic JD export | 閱讀並操作產品，不解讀技術 error code |
| Observability | 不自行聲稱實際使用了什麼 | 記錄真實 model／Tool／Skill／context／retry／usage trajectory | redaction、retention、最小 receipt 與產品事件關聯 | 只看到有助使用的狀態，不暴露私密推理或敏感 trace |
| 模型與 provider | 在已給定能力內推理 | model binding、provider adapter、capability normalization | 選擇政策、required capability preflight、run 內 pin、禁止未知 fallback | 日後可有簡單設定，但不需理解 wire parameters |

矩陣只裁決「誰保證什麼」，不預先裁決一輪呼叫幾次模型、Memory 的實體 schema、待審內容有幾張表、Tool 數量或 framework winner。Memory 的物理責任仍由 `MEM-Q001`～`MEM-Q004` 單獨治理，不能在本節暗中重開。

#### 3.5.4 三個 architecture placement 選項

| 方案 | 形狀 | 優點 | 主要缺點 |
|---|---|---|---|
| **P1．模型／Harness 主導** | 模型在寬 Tool surface 中自行規劃大部分流程；application 只留最終驗證與核准 | 自然、起步快，能充分利用新模型能力 | 容易把過多流程穩定性寄託在 Prompt；Tool 選錯、停止不一致、成本與追查風險較高，且新 harness 預設可能改變產品行為 |
| **P2．固定 Workflow 主導** | application 預先排定理解、缺口、JD 產生、驗證、審核等 stages，再逐步呼叫模型 | 順序與失敗點容易預測，適合真正固定、重複流程 | 長訪談不是固定 wizard；可能每輪執行不需要的 stage、增加 model calls，並把應由模型判斷的語意流程寫成僵硬程式 |
| **P3．有界單一顧問＋deterministic seams** | 一位主顧問模型在本輪內動態決定語意路徑；成熟 Runtime 管 loop／context／Tool／恢復；程式只守精確 seam；只有事實歧義與 authority 交給員工 | 同時保留自然訪談、成熟機制、可驗證 authority 與成本邊界；可以先簡單，只有代表性失敗出現才增加固定 workflow | 必須仔細寫清 Tool／Skill／authority seam；不能只安裝框架就期待產品語意自動成立 |

**G3 Working Baseline 採 P3。**Product Owner 於 2026-09-04 在要求先確認大廠共識後表示同意；核准範圍是上述責任配置，不是把 `P3` 名稱或完整四欄宣稱成廠商標準。它符合 OpenAI／Anthropic「模型負責判斷、Tools／harness 負責行動與回饋」、Microsoft dynamic＋deterministic 混合，以及 Google／Anthropic「從簡單 single-agent 方案開始、效果需要時才增加複雜度」的共同方向。它也不把「單一顧問」誤解成「所有事情都交給模型」：主顧問擁有語意決策，Runtime 與 deterministic seams 仍擁有可靠執行與 authority。

採 P3 **不代表**立刻選 LangChain／LangGraph 或 PydanticAI／Harness，也不代表永遠不用固定 workflow。只有某項代表性情境證明標準 bounded loop 無法穩定表達必要順序、等待或恢復時，才為該窄段加入 workflow；不能先把整個訪談做成 graph wizard。

框架可行性抽查顯示 A、B 都能承接 P3 的多數通用機械責任，因此這個 placement 不會先偷選勝者：

- LangChain／LangGraph 直接提供 bounded agent loop、middleware、typed Tools、context injection、checkpoint／interrupt 與 tracing；interrupt resume 是 checkpoint／replay 語意，副作用仍須冪等。[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)、[LangChain middleware](https://docs.langchain.com/oss/python/langchain/middleware/overview)、[LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- PydanticAI 提供 typed Agent／Tools／outputs、dependencies、hooks、usage limits 與 instrumentation；外部 approval 的 deferred flow 會結束原 run，再由保存的 history 加結果開始後續 run，若要求完整 durable suspended execution，需採其 DBOS／Temporal／Restate 等正式 integration。[PydanticAI Agent](https://pydantic.dev/docs/ai/core-concepts/agent/)、[PydanticAI deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)、[PydanticAI durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)

兩邊都不自動保證 external side effect exactly-once，也不替 Caliburn 定義 semantic authority、審核效果或 JD correctness。下一個 framework gate 比較的是這些 primitive 的效果、完整度、成熟度與整合成本，而不是哪一套名詞看起來比較像現有設計。

## 4. 父層責任地圖

| 層 | 必須解決的問題 | 成熟 primitive／目前趨勢 | 分類 | 最終責任不能交給誰 |
|---|---|---|---|---|
| 1. Product policy | 顧問為誰服務、何時追問、JD 必須經誰核准 | 穩定 developer/system instructions＋domain Skills | 產品決策 | 模型或框架預設 |
| 2. Input | 接受員工文字、未來可能的附件，保留 role 與順序 | typed messages／content blocks | 跨廠共同 | 模型不能決定 canonical input |
| 3. Conversation | 保存長期訪談，關閉後可繼續 | session／thread／conversation history | 跨廠共同 | context window 或 prompt cache |
| 4. Instructions | 穩定角色、權限、禁止事項與成功條件 | system/developer instruction；每個請求或 session 明確提供 | 跨廠共同 | Skill 或員工資料不能升格成 policy |
| 5. Context assembly | 每個 model step 提供正確且有界的消息、Memory、Skills、Tools、JD 視圖 | state/store/runtime context、middleware/hooks、compaction | 跨廠共同 | 模型 context window 不會自動選對資料 |
| 6. Model | 依任務選能力與成本，設定 reasoning／temperature／token limit | model profile、per-run selection、pinned model ID | 跨廠共同責任；細節為選項 | gateway 不可假裝模型等價 |
| 7. Provider/API | 把共同意圖轉成各 provider 真正支援的 wire contract | native SDK 或 model abstraction adapter | 跨廠共同責任；實作可選 | 不能把不支援參數硬送出 |
| 8. Skills | 將訪談、Task、Duty、產出／標準、K／S、JD 品質方法按需載入 | versioned Skills／deferred capabilities／progressive disclosure | 強趨勢 | 模型不應回填「我用了哪個 Skill」作真相 |
| 9. Memory | 跨回合保留、修訂與按需取回員工工作資訊 | conversation 與 long-term/semantic memory 分層 | 跨廠共同；表徵仍為選項 | Memory 不核准 JD、不取代原始 conversation |
| 10. Application workspace／Tools／MCP | 讓模型讀取目前工作區，並以受控操作編輯 JD、搜尋 Memory 或存取外部能力 | client function tools、editor／patch toolsets、MCP、tool search／deferred tools | 跨廠共同；延遲載入與受控工作區為強趨勢 | 模型只提出操作；Runtime 執行並驗證，產品決定 JD 語意與核准規則 |
| 11. Agent loop | 在模型與 Tools 間循環，直到完成、需人或達預算 | Agents SDK Runner、LangChain agent、ADK Runner、PydanticAI Agent | 跨廠共同 | 不等於整個產品 workflow 或資料 authority |
| 12. Workflow runtime | 中斷、恢復、長工作、deterministic steps、故障續跑 | LangGraph、DBOS／Temporal／Restate、ADK workflow | 條件式但 Caliburn 很可能需要 | 模型文字不能當執行游標 |
| 13. Structured effects | 將機器要處理的結果做成 typed output／tool call | native structured output＋typed models | 跨廠共同 | Schema conforming 不代表語意正確 |
| 14. Validation／guardrails | 驗 schema、關聯、版本、權限、安全與內容限制 | typed validation、tool middleware/hooks、domain verifier | 跨廠共同 | provider safety filter 不取代 domain invariant |
| 15. Human control | 高影響行動、JD 變更與必要澄清可暫停等待人 | approval／edit／reject、interrupt／resume | 跨廠共同；產品語意由 Caliburn 定義 | approval 不等於 authentication／authorization |
| 16. Error／retry／budgets | 分辨可重試錯誤，限制模型、工具、時間與成本 | typed errors、bounded retries、max turns/calls/tokens | 跨廠共同 | 不可在多層各自無界重試 |
| 17. Persistence／idempotency | crash 後可續跑，副作用不重複 | checkpoint/durable execution＋idempotent tools | 跨廠共同責任；機制可選 | conversation storage 不保證 exactly-once |
| 18. Observability | 關聯 run、model/settings、context recipe、Skill／Tool 載入與呼叫、結果、錯誤、token、成本、延遲與停點 | OpenTelemetry／traces／usage events；敏感 payload 可遮罩或停用 | 跨廠共同；精確 trace schema 為框架選項 | 日誌不應成為產品 state，也不應無條件複製全部員工內容 |
| 19. Output／UI | 將回覆、進度、待審差異、錯誤與需要確認呈現給員工 | streaming events＋typed UI projection | 產品決策 | Web 不重算 domain invariant |

### 4.1 這張表刻意沒有舊元件名稱

`Focus`、`Work Model`、`Proposal`、`Progress` 等詞若只是舊實作名稱，不會因歷史存在而成為新架構的必要 layer。只有其背後的產品效果仍需要，且沒有成熟 primitive 能承接時，才會在後續設計出現最薄的產品邏輯。

同理，不能因框架也有 `state`、`memory`、`checkpoint` 就說一定「重疊」。若框架 primitive 完整承接相同目的，它可以直接成為正式機制；真正要審核的是資料 authority、產品效果及框架保證是否匹配。

## 5. 模型層：可以換，但不能盲換

### 5.1 已有跨廠與框架支持的能力

OpenAI Agents SDK 可以在 agent 或 run 指定模型／provider；Anthropic Managed Agents 可版本化 agent 並在 session 覆寫 model；LangChain 提供共同 model interface 與 runtime dynamic selection；PydanticAI 的 model string 與 `SelectModel` 可在每個 logical model step 前解析模型。這支持以下結論：

1. **長期產品 state 不屬於模型。** Conversation、Memory、JD、待審內容與核准結果持久化在 runtime/application，換模型不應遺失。
2. **模型可在回合／run 邊界切換。** 每次 run 先解析模型、provider 與設定並記錄；該 run 內預設 pin，避免同一工具迴圈途中無聲換腦。
3. **需要時可以按工作選模型。** 例如日常訪談與全面 JD audit 可用不同能力／成本層級，但第一版不必自動 routing。
4. **模型並不等價。** Tool calling、structured output、context、reasoning controls、streaming、prompt caching、tool search、MCP 與 error shape 都可能不同。

官方依據：[OpenAI Agents SDK models](https://openai.github.io/openai-agents-python/models/)、[Anthropic managed agent configuration](https://platform.claude.com/docs/en/managed-agents/agent-setup)、[LangChain models](https://docs.langchain.com/oss/python/langchain/models)、[PydanticAI SelectModel](https://pydantic.dev/docs/ai/capabilities/select-model/)。

### 5.2 Caliburn 要比較的不是「模型名字」，而是能力 profile

| 等級 | 模型能力 |
|---|---|
| Required | 高品質繁中訪談與職務分析、client tool calling、可驗證 structured output、可用的 context window、streaming 或等價增量事件、usage／finish reason／typed error |
| Preferred | 可調 reasoning effort、prompt caching、provider-native compaction、deferred/tool search、穩定 pinned model ID |
| Deferred | 多模態、web/file search、遠端 MCP、code execution、computer use、超長 autonomous run |
| Product characterization | 真實職務訪談品質、Task／Duty／K／S 分析品質、中文穩定性、延遲與成本；官方規格無法替代 bounded test |

### 5.3 第一版建議的模型策略

目前建議先採：

- 一個明確 default model；
- 允許設定替換模型；
- framework/provider adapter 在執行前做 capability check；
- 不在同一 run 內靜默 fallback 到另一模型；
- 不先做複雜自動 router、多模型投票或多 agent；
- 後續只用少量代表性訪談做 model characterization，再決定 default 與高難度 override。

這是「最簡單可行、需要時才增加 agentic complexity」的產品 mapping，不是任何廠商規定。Anthropic 明確提醒 agentic complexity 會增加成本與延遲；OpenAI 的 model selection guidance 則建議先建立品質基準，再以成本／延遲優化模型。

## 6. Skills、Tools、Memory、Output 不是同一件事

| 元件 | 保存／提供什麼 | 模型何時看到 | 模型輸出什麼 | 不能做什麼 |
|---|---|---|---|---|
| Base instructions | 穩定角色、權限、北極星與禁止事項 | 每次 model request 必要部分 | 不適用 | 不塞完整方法、歷史、Memory、Tool schema |
| Skill | 「怎麼訪談／分析／撰寫」的方法、rubric、資源 | metadata catalog 常駐；完整內容按需載入 | 遵循方法完成思考／行動 | 不保存員工事實，不由模型聲稱載入紀錄 |
| Memory | 「這位員工的工作目前知道什麼」及可回查資訊 | 由 context assembler 或 read/search Tool 按需提供 | Memory 候選更新或查詢 | 不決定是否改 JD，不核准文件 |
| Tool | 讓模型讀／查／操作外部世界或 JD 工作區 | 只暴露本輪可用 definitions；很多時延遲載入 | 名稱＋少量必要參數 | 不把 scope、actor、ID、timestamp 等可信 metadata 交給模型填 |
| Structured output/effect | Runtime 或 UI 要可靠解析的本輪結果 | response format 是當次模型契約 | 小型 typed payload | 不等於 domain validation 或 authority commit |

Progressive disclosure 已不是單一廠商技巧：OpenAI 有 Tool Search 與 Skills；Anthropic 有 Tool Search、Skills 與 context editing；PydanticAI 有 on-demand capability bundle；Deep Agents 有 Skills 與 context management。共同方向是**先給小型目錄，再按需載入完整方法或工具**，不是每輪把全部 prompt/schema 塞給模型。

依據：[OpenAI Tool Search](https://developers.openai.com/api/docs/guides/tools-tool-search)、[OpenAI Skills](https://developers.openai.com/api/docs/guides/tools-skills)、[Anthropic Tool Context](https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context)、[Anthropic Skills](https://platform.claude.com/docs/en/managed-agents/skills)、[PydanticAI on-demand capabilities](https://pydantic.dev/docs/ai/capabilities/on-demand/)、[Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview)。

### 6.1 LLM 控制 App：共識機制與 Caliburn 內容要分開

AI 編輯 JD 的正確父層概念不是「模型直接寫資料庫」，也不只是讓模型輸出一份大 JSON；它是 **LLM 透過受控 Tool 操作一個可檢視的 JD 工作區**。OpenAI function calling、Anthropic client tools、Microsoft Agent Framework Tool approval 與 LangChain HITL 都採相同責任方向：模型提出結構化操作，應用／Runtime 執行，將結果或錯誤回傳模型；需要人決定的操作可以在執行或正式生效前停下。[OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)、[Anthropic Tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)、[Microsoft Tool approval](https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval)、[LangChain HITL](https://docs.langchain.com/oss/javascript/langchain/human-in-the-loop)

```text
模型看到目前 JD 工作視圖＋本輪可用 Tool
  ↓
模型提出小型、typed Tool call
  ↓
Framework／Runtime 解析、驗 schema，注入可信 scope／版本／actor
  ↓
Caliburn domain command 驗關聯與產品規則，操作待審工作視圖
  ↓
將成功結果或精確錯誤回傳模型；必要時有界修正
  ↓
員工在同一份 JD 視圖看見 AI 差異，可編輯、接受或拒絕
  ↓
只有核准結果才由 deterministic authority command 正式生效
```

最後兩步是 Caliburn 已確認的產品語意；外部框架提供 interrupt／approval primitive，但不能替產品決定何謂「同一組變更」、何時正式生效或拒絕後如何還原。

| 跨廠／框架承接的共識機制 | Caliburn 必須討論與定義的內容 |
|---|---|
| Tool schema 產生、註冊、選擇與 dispatch | JD 可以被讀取與操作的產品能力清單 |
| model ↔ tool result 的有界 agent loop | 新增、改寫、移動、解除關聯、刪除等動作的確切語意 |
| typed parsing、middleware、interrupt／resume、trace | 哪些操作組成一個原子待審變更，員工如何接受／修改／拒絕 |
| Tool catalog／deferred loading／MCP transport | 每個 Tool 的最小參數、domain error 與回傳內容 |
| provider structured call wire format | Runtime 必須自行注入的文件 scope、可信 ID、版本與 actor |
| 通用 prompt／Skill 載入 primitive | 顧問角色、JD 品質標準、Task／Duty／工作細節／OPKS 分析方法與 Skill 內容 |

因此後續不能問「Tool 要不要用框架」這種過大的問題，而要分成：

1. **機制是否已有成熟 primitive**：若有，優先採用並驗證，不重寫 agent loop、schema dispatch、interrupt 或 trace；
2. **Caliburn 要讓模型完成什麼工作**：這才決定 Tool 清單、Skill 內容、base instructions 與 domain validation；
3. **最小契約怎麼寫**：最後才討論資料結構、欄位、錯誤碼、載入條件與測試，不從舊 schema 複製。

這也表示「像 Codex／Claude 編輯工作區」是互動與控制概念，不要求照搬檔案系統、shell 或 coding-agent UI。Caliburn 的受控世界只有本產品允許的 JD 與 Memory 能力。

## 7. Framework 不是一個欄位，而是六種角色

| Framework 類別 | 解決什麼 | 目前主要候選／參考 |
|---|---|---|
| Native model/API SDK | 取得最新 provider 原生能力 | OpenAI Responses／Agents SDK、Anthropic Messages／Managed Agents、Gemini Interactions |
| Agent framework | 統一模型、tools、agent loop、structured output、middleware | LangChain、PydanticAI Core、OpenAI Agents SDK、Google ADK、Microsoft Agent Framework |
| Runtime／durability | checkpoint、interrupt/resume、長工作與故障恢復 | LangGraph、DBOS、Temporal、Restate、ADK Workflow |
| Harness | 預先組裝 Skills、workspace、context、memory、planning 等能力 | PydanticAI Harness、Deep Agents、Claude Agent/Managed Agents、AWS AgentCore Harness |
| Gateway／router | 單一 key/endpoint、provider routing、fallback、成本治理 | OpenRouter、Pydantic AI Gateway、雲端 gateway；不是 agent framework |
| Observability | traces、tokens、cost、errors、eval data | OpenTelemetry、LangSmith、Pydantic Logfire、provider traces |

因此「使用 LangGraph」不能回答 model interface、Skills 或 structured output；「使用 PydanticAI」也不能單獨回答跨程序 durable workflow。正式方案必須說清楚每一類是否需要、由哪一項承接，以及哪些不安裝。

LangChain 官方目前也明確區分 framework、runtime、harness：LangChain 是模型／Tools／agent loop framework；LangGraph 是 durable execution、streaming、HITL、persistence runtime；Deep Agents 是帶 planning、subagents、filesystem 與 context management 的高階 harness。[Frameworks, runtimes, and harnesses](https://docs.langchain.com/oss/python/concepts/products)

PydanticAI 官方則把 Core 定位為 typed、multi-provider agent loop，把額外能力做成可組合 `Capability`；Harness 提供 Memory、Skills、context、planning 等能力，且可以只取需要的 blocks。Harness 目前採 0.x versioning，官方稱可用於 production，但 minor version 仍可能改 API，因此不能把「功能多」誤認成「API 已完全穩定」。[PydanticAI overview](https://pydantic.dev/docs/ai/overview/)、[PydanticAI Harness](https://pydantic.dev/docs/ai/harness/)

這個分層也能被其他現行大廠方案交叉驗證。AWS 明分 Strands Agents SDK、AgentCore Harness 與 AgentCore Runtime：Harness 提供受管理的 agent loop；需要自訂 hooks、雙向串流或 graph／workflow 時改由 Runtime 承接。Microsoft Agent Framework 則把 Agent、Session／Context Provider／middleware、Harness 與可 checkpoint 的 Workflow 分開；官方同時明示 model provider 的 structured output、hosted tools 與 MCP 等能力並不完全等價。[AWS：AgentCore Harness 與 Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html)、[Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)、[Microsoft model providers](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/model-providers/)

### 7.1 2026-09-04 成熟度快照

版本只用來判斷目前風險；正式採用仍須 pin 並在施工前重驗，不能把本表當永久版本要求。

| 元件 | 目前官方版本／狀態 | 對選擇的影響 |
|---|---|---|
| LangChain | [1.4.0](https://pypi.org/project/langchain/1.4.0/)，1.x stable，PyPI 標示 Production/Stable | Agent framework 的現行穩定主線；1.x 仍依官方 semantic versioning／LTS 政策評估。 |
| LangGraph | [1.2.11](https://github.com/langchain-ai/langgraph/releases/tag/1.2.11)，package 標示 Production/Stable | 兩案中目前最直接、成熟的 thread checkpoint／interrupt runtime。 |
| Deep Agents | [0.7.13](https://github.com/langchain-ai/deepagents/releases/tag/deepagents%3D%3D0.7.13)，Beta | 可研究 `SkillsMiddleware` 等窄 primitive；不應因功能多就整包採用。 |
| PydanticAI Core | [2.39.0](https://github.com/pydantic/pydantic-ai/releases/tag/v2.39.0)，V2 stable | Typed agent loop、provider abstraction、Tools、output 與 capabilities 是可信正式候選。 |
| PydanticAI Harness | [0.29.0](https://pypi.org/project/pydantic-ai-harness/0.29.0/)，0.x 且 package classifier 仍為 Alpha | 功能可用且官方稱面向 production，但 API 變動風險高於 Core；只能逐項採用並 pin。 |
| DBOS Python | [2.31.0](https://github.com/dbos-inc/dbos-transact-py/releases/tag/2.31.0) | 只在方案 B 需要完整 durable execution owner 時比較；不是 Memory、model 或 agent framework。 |

版本來源校正：初次交叉查詢時，GitHub 搜尋索引只顯示 LangChain `1.4.0a1`，且 Harness 的舊發布頁只到 `0.27.0`；PyPI 套件首頁直接顯示 LangChain `1.4.0` stable 已於 2026-09-03 發布、Harness `0.29.0` 已於 2026-09-04 發布。因此本表以套件發布頁而非可能延遲的搜尋摘要／舊版頁為準。這項校正只改版本事實，不改 A／B 評估方法。

### 7.2 兩個容易做錯的組合規則

1. **不要在同一 agent loop 同時疊 LangChain agent 與 PydanticAI Agent。**兩者都是 agent framework，應二選一；否則模型迴圈、Tool error、retry 與 structured output 會有兩個 owner。
2. **不要同時讓 LangGraph 與 DBOS 擁有同一流程的 durability。**若選 LangGraph，它保存 checkpoint／interrupt/resume；若選 PydanticAI＋DBOS，DBOS 才是 workflow execution owner。兩套 history、resume 與 retry 疊在一起不是「功能更多」，而是責任衝突。

這兩條是由各框架公開責任邊界推得的整合約束，不是跨廠產品規則。PydanticAI Core 本身沒有完整 graph checkpoint owner；Harness 的 step persistence 也不等同完整 graph-state checkpoint，因此方案 B 必須明確決定是否及何時引入 durable engine。

## 8. 目前三個實質方案

### 方案 A：LangChain＋LangGraph，選擇性採用 Deep Agents primitive

**承接**：

- LangChain：provider/model abstraction、Tools、agent loop、structured output、middleware、context engineering；
- LangGraph：thread state、checkpoint、interrupt/resume、durable agent workflow；
- Deep Agents：只在證明需要時採 Skills/context/filesystem 能力，不整包啟用 coding-agent 預設；
- LangSmith 或中立 OpenTelemetry backend：observability。

**優點**：框架／runtime 邊界清楚；LangGraph 的長期 thread、HITL、state inspection 與恢復直接符合長訪談；生態成熟、provider integrations 廣。

**風險**：API 面較多；middleware、state、store 與 domain authority 若沒有清楚 contract，容易被誤用；Deep Agents 的 planning/subagent/shell 對第一版可能過度。

### 方案 B：PydanticAI Core＋選擇性 Harness＋正式 durable integration

**承接**：

- PydanticAI Core：provider/model abstraction、typed Tools、structured output、agent loop、retries、instrumentation；
- on-demand `Capability`：把 Skill instructions、Tools、settings、hooks 一起延遲載入；
- Harness：只取 Memory、Skills、context management 等已需要能力；
- DBOS／Temporal／Restate 等官方 integration：需要跨程序恢復時承接 durability；
- OpenTelemetry／Logfire：observability。

**優點**：typed end-to-end；Capability 很貼近「方法＋工具＋模型設定按需載入」；模型可換；框架功能組合性強，可能減少自行寫 middleware／schema glue。

**風險**：Harness 仍是 0.x；其內建 Memory 目前只含 literal search，semantic ranking 要換 backend；Skills loader 與 bundle resource 完整度要逐項核對；durability 要再選一個 engine，不能只靠 Core。

官方依據：[PydanticAI on-demand capabilities](https://pydantic.dev/docs/ai/capabilities/on-demand/)、[Harness Memory](https://pydantic.dev/docs/ai/harness/memory/)、[PydanticAI durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)。

### 方案 C：直接採各 provider 原生 SDK＋產品自建協調層

**承接**：OpenAI、Anthropic 等各自用原生 adapter，應用自行處理共同 loop、capability negotiation、durability、memory、approval、trace normalization。

**優點**：最早拿到 vendor 原生 features，不被共同抽象限制。

**風險**：需要自行維護最多 provider 差異、loop、錯誤、retry、structured output 與 observability glue；與「優先用成熟框架」的方向最不一致。

### 8.1 目前建議保留 A、B 進決賽

方案 C 應作原生契約的 reference／escape hatch，不宜作第一版主架構。A、B 都覆蓋大部分父層，但各有尚未證明處；在完成 §9 的同表比較前不提前宣布勝者。

Google ADK、Microsoft Agent Framework、AWS AgentCore／Strands 仍是有效的交叉證據與替代候選，但目前不是首輪決賽：Google／AWS 的完整 managed 能力較偏雲端；Microsoft 新框架雖有完整 pipeline、middleware、Skills 與 workflows，部分能力仍快速演進。這是目前產品限制下的候選排序，不是宣稱其技術較差。

## 9. A／B framework 決策矩陣

本輪只比較方案 A 與 B，不能用「少寫程式」作唯一或主要標準。權重順序為：

1. **產品效果**：長訪談、正確 context、職務分析 Skills、JD 編輯與員工審核是否自然；
2. **功能完整性**：L1～L11 與本文 §4 是否有成熟 primitive；
3. **可靠性**：typed contract、HITL、crash resume、idempotency、精確 error feedback；
4. **模型與 provider 可替換性**：能力差異是否能被顯式檢查而非藏起來；
5. **Context 與成本**：deferred Skills/Tools、prompt caching、compaction、usage budgets；
6. **框架成熟度**：GA／stable、version policy、migration risk、官方維護；
7. **可觀測性與測試性**：model/tool/context/usage trace 是否完整；
8. **實作與維護成本**：需要多少 Caliburn glue，升級時有多少 seam；
9. **可逆性**：更換 model/provider、durable engine 或 harness 時，產品資料是否仍可讀。

### 9.1 比較方法與不偏袒現行程式的限制

本節只用已核准的 `S1`～`S7` 產品效果與上述九項標準比較，**不因 production 現在已使用哪套框架而加分**。比較的共同起點是：一位員工／一份 JD 對應一個可長期繼續的訪談；每次 model run 必須有界；員工澄清與待審變更可能跨 HTTP request 或程序重啟；AI 變更不能繞過 server-side authority；職務分析語意仍由 Caliburn 定義。

證據分四層：

1. `Official fact`：框架官方文件明示的 API、保證或限制；
2. `Current package fact`：截至 2026-09-04 的穩定度與版本狀態；
3. `Caliburn inference`：將官方能力套到 `S1`～`S7` 後的工程判斷；
4. `Unknown`：必須在後續 G4／G5 以最小 characterization 才能確認，不拿未知冒充框架保證。

### 9.2 `S1`～`S7` 產品情境覆蓋

| 情境 | A：LangChain＋LangGraph | B：PydanticAI Core＋Harness＋durable integration | 判斷 |
|---|---|---|---|
| `S1` 模糊起點 | `create_agent`、Tools、structured output 與 middleware 可形成一個 bounded agent loop。 | Typed `Agent`、Tool／Output schema、dependencies 與 retry 可形成同等 loop。 | **都完整**；不構成選型差異。 |
| `S2` 長訪談、相似案例、關閉後恢復 | LangGraph 以 thread checkpoint 保存短期 state，Store 保存 namespaced long-term data；官方有 PostgreSQL Saver／Store。 | Core 的 server surface 由呼叫者帶回 `message_history`；Harness Memory 可用 PostgreSQL，但 Step Persistence 官方明示不是完整 graph-state checkpoint，且目前沒有 PostgreSQL backend。要求 process-crash resume 時須另選 DBOS／Temporal／Prefect／Restate。 | **A 較直接**：一套 runtime 即承接 thread、state、Store 與恢復。 |
| `S3` 自然更正、衝突與需要先問員工 | LangGraph interrupt 可持久暫停並以同一 thread resume；LangChain HITL 支援 `respond` 讓員工作為 Tool 回答。 | Deferred Tools 可 inline 等待，或結束 run 後用原 history＋`DeferredToolResults` 開新 run；durable engine 也可承接長等待。 | **兩者都能做**；A 的 server-held pending state 路徑較一體化，B 需把 Core、UI 與 durable owner 接清楚。 |
| `S4` 先理解工作，再按需要形成 JD | LangChain middleware/context hooks 可動態組 context、Tools 與輸出；Deep Agents primitive 可選但非必要。 | `Capability` 可把 instructions、Tools、hooks、model settings 一起 always-on 或按需載入。 | **B 的組合介面略整齊**；真正分析方法仍是 Caliburn Skill，不由框架提供。 |
| `S5` AI／員工共同處理最新內容，AI 變更需審核 | HITL middleware 原生支援 approve／edit／reject 並與 checkpoint 相接。 | Deferred approval 原生支援 approve、override args、deny；但官方明示 UI adapter 不保有 server-side request authority，應用仍須在 Tool 端驗權。 | **功能都完整，A 較少 seam**；兩者都不能取代 Caliburn 的 changeset／document authority。 |
| `S6` 同時操作、失敗與恢復 | Checkpoint、pending writes、fault tolerance、interrupt/replay 與 Functional API 的 deterministic／idempotent 規則在同一 runtime。 | DBOS／Temporal 等是成熟 durable engine，但要另外定義 workflow／step、穩定 ID、serialization、I/O boundary 與 retry owner；Harness Step Persistence 不足以取代它。 | **A 較適合第一版**；B 並非不能做，而是整合面與失誤面較大。 |
| `S7` 完整 JD 品質盤點 | 可呼叫盤點 Tool、產生 typed effects，再由 deterministic verifier 檢查。 | 同樣可用 typed Tool／Output、validator 與 retry。 | **都只提供機械能力**；「何謂完整 JD」仍必須是 Caliburn domain policy。 |

官方依據：LangChain 的 agent／middleware、[HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)、[persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) 與 [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)；PydanticAI 的 [message history](https://pydantic.dev/docs/ai/core-concepts/message-history/)、[Deferred Tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)、[Harness](https://pydantic.dev/docs/ai/harness/)、[Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/) 與 [durable integrations](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)。

### 9.3 九項選型標準的結論

| 標準 | 較佳者 | 理由 |
|---|---|---|
| 1. 產品效果 | **A** | `S2`、`S3`、`S5`、`S6` 可由同一 thread runtime 承接；B 也能達成，但需跨 Core／Harness／durable engine。 |
| 2. 功能完整性 | **A** | A 的 stable baseline 已含 agent loop、context hooks、HITL、persistence、Store、streaming 與 PostgreSQL；B 的完整集合存在，但不在單一 runtime，且部分位於 0.x Harness。 |
| 3. 可靠性 | **平手但強項不同** | A 強在持久流程一體化；B 強在 typed dependencies、Tool／Output validation 與細粒度 retry budgets。兩者都仍需 deterministic domain validation、idempotent side effects 與 server-side authority。 |
| 4. 模型／provider 可替換 | **平手** | LangChain 有共同 model interface、model profiles 與 dedicated OpenRouter integration；PydanticAI 有 providers、model profiles、`SelectModel`／`ResolveModelId`。兩者都不能假裝 provider capabilities 完全相同。 |
| 5. Context 與成本 | **B 小勝** | Harness 有 on-demand Capability、Tool Search、Tool Output Limits、Spend Limits、compaction 與 cache-bust warning；A 也有 summarization、context editing、Tool selector/search、model/tool call limits、usage metadata 與 prompt caching，但美元跨窗口預算較可能要額外 middleware。 |
| 6. 框架成熟度 | **A** | LangChain 1.x 與 LangGraph 1.2 是 stable／Production；B 的 Core V2 與 DBOS 已 stable，但 Harness 官方仍採 0.x、允許 minor-version API 移動。 |
| 7. 可觀測性／測試性 | **平手** | LangChain/LangGraph 可自動追蹤到 LangSmith 並可走 OTel；PydanticAI 原生發 OTel，可接 Logfire 或任意 OTLP backend。最終 backend 仍可延後選。 |
| 8. 實作／維護成本 | **A** | 第一版不必另接 durable engine、重新協調多層 retries 或自建 PostgreSQL StepStore；B 的功能不是少，而是責任分散後需要更多 integration contract。 |
| 9. 可逆性 | **A 小勝** | 只要 domain contract 不塞進 framework message，兩者都可替換；但 B 還要同時隔離 Harness API 與 durable-engine workflow identity，需維護的 seam 較多。 |

這不是「A 功能一定比 B 多」。相反，B 在 typed loop、Capability 與成本治理上更漂亮；**A 勝出的原因是第一版最重要的長期 thread、server-held state、人工停等與 PostgreSQL 恢復由一套較穩定的 runtime 直接承接**，而不是因為少寫幾行程式或因為現行 code 已使用它。

### 9.4 G2 推薦：方案 A，但採精簡組合而非整包 harness

目前證據支持將以下內容送交 Product Owner 作 G3 核准。這是依跨廠共同責任與 Caliburn 情境作出的 **Caliburn inference**，不是宣稱各家大廠共同選用 LangChain／LangGraph：

- 選 **LangChain stable 1.x＋LangGraph stable 1.x** 作第一版 agent framework／durable runtime；
- 一個 `create_agent`／LangGraph runtime 擁有 model↔Tool loop、thread checkpoint、interrupt/resume 與 streaming；
- 使用官方 PostgreSQL Saver／Store，而不是再加 DBOS 或第二套 workflow owner；
- 只採已證明需要的 middleware：Tool error／retry、structured output、HITL、model/tool call limits、context management；確切清單留待後續 G4；
- **不整包採 Deep Agents**，也不先啟用 planning、subagent、shell、filesystem 等第一版無需求能力；Skill progressive disclosure 可在 Skill gate 比較 `SkillsMiddleware` 或更薄的等價 primitive；
- 不同時使用 PydanticAI `Agent`；但 domain types／validation 繼續使用 Pydantic library，兩者不衝突；
- Provider／OpenRouter、default model、reasoning、observability backend、Memory mapping、Tool／Skill／Prompt schema 均仍是後續獨立決策，不隨本案偷渡。

### 9.5 為什麼暫不選 B，以及重開條件

`PydanticAI Core＋Harness＋durable integration` 是有效的第二名，不是被否決為技術不成熟：

- Core V2 的 typed Tool／Output、granular retry、usage limits 與 OTel 很強；
- Harness 的 on-demand Capability、Spend Limits、Tool output spill、Memory／Conversation Search 很接近現代 coding-agent harness；
- DBOS／Temporal／Prefect／Restate 都是官方共同維護的正式 durable 路徑。

但第一版若選 B，必須同時決定並驗證：誰保存 server-trusted history、誰保存 pending approval、誰擁有 workflow resume、哪一層重試、如何確保 stable workflow/toolset IDs，以及如何把 0.x Harness 升級風險隔離。這些不是做不到，而是相較 A 多出尚未證明的 glue。

以下任一情況成立時重開 A／B：

1. Harness 進入 stable，或提供與產品資料庫直接相容的完整 graph-state checkpoint；
2. 後續最小 characterization 證明 PydanticAI 的 typed Capability／retry 在本產品明顯提升成功率或成本，足以抵銷第二 runtime；
3. 必需 provider feature 在 LangChain adapter 無法可靠使用，但 PydanticAI 有正式支援；
4. 產品不再需要跨 request／restart 的 server-held thread state，durable runtime 的權重顯著下降。

### 9.6 仍未知、但不應被藏起來的風險

- `Unknown`：兩案在本產品 prompt、模型與 Tool schema 上的實際成功率、token 成本與延遲；這屬後續 bounded characterization，不靠文件臆測。
- `Unknown`：各 provider 經 OpenRouter 時對 strict structured output、streaming、reasoning、cache 與 Tool Search 的實際 fidelity；須在 provider gate 逐能力驗證。
- `Current issue report, not framework guarantee`：LangGraph 1.2.11 官方 repository 目前有「首個 durable checkpoint 前程序死亡可能沒有 admission record」與特定 `update_state` 用法可能讀到空 state 的未結案回報。若 A 獲核准，G4／G5 必須用實際採用路徑測 crash-before-first-checkpoint、resume、duplicate side effect；不能把 PyPI 的 Production/Stable 標籤當成零風險保證。[Issue #8764](https://github.com/langchain-ai/langgraph/issues/8764)、[Issue #8653](https://github.com/langchain-ai/langgraph/issues/8653)
- `Official limitation`：PydanticAI Harness Step Persistence 不是完整 graph-state checkpoint、目前不含 PostgreSQL backend；外部 UI approval 若只信 client history 也不是 authorization boundary。這是本輪評分 B 較多 seam 的直接依據，不是推測。[Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/)、[Deferred Tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)

因此，文件證據已足以提出 framework 推薦；**不需要為了選 A／B 先做一個寬泛 spike**。A 若獲 Owner 核准，下一 gate 才把上述版本特定風險變成少量、可判定的 G4/G5 contract probes。

## 10. 已確定、尚未確定與禁止偷渡

### 10.1 已有足夠跨廠證據

- 系統需要 instructions、input/conversation、context assembly、model、Tools、bounded agent loop、structured effects、validation、human control、persistence、budgets 與 observability。
- Conversation、長期 Memory、prompt cache 與 compaction 是不同責任。
- client Tool 的執行與權限屬 Runtime/Application，不屬模型。
- structured output 只保證結構，仍需 domain validation。
- Skills／大型 Tool inventory 應 progressive disclosure；不是每輪全載入。
- 模型可替換，但必須用 capability profile 管理差異並 pin 每次 run。
- 第一版維持一位主顧問；多 agent 不是共同必需，也不因框架提供就啟用。

### 10.2 尚未確定

- LangChain／LangGraph 的精確版本 pin、最小 runtime contract 與 upgrade seam；
- default model、reasoning effort 與高難度 override；
- 是否保留 OpenRouter gateway，或改 direct provider adapters／其他 gateway；
- Skills 最終是一個 bundle 或數個 on-demand capability；
- structured effects 要以 final output、Tool calls 或混合方式承載；
- 哪些 run 真正需要 durable engine，哪些只需 persisted conversation；
- observability 使用 LangSmith、Logfire 或純 OpenTelemetry backend；
- Memory 既有 Working Decisions 是否在選定框架後仍是最簡單、效果最好的 mapping。

### 10.3 禁止在後續實作偷偷決定

- 不因框架有某個 class 就建立新產品 entity。
- 不讓 framework state、checkpoint 或 Memory 無審核地成為 JD authority。
- 不為了 provider-neutral 而關閉模型必要能力，或把 unsupported option 硬送給 provider。
- 不把所有模型呼叫都升到最高 reasoning，也不把每項分析拆成多 agent／多次 LLM。
- 不把 RAG、Reference、公司文件、能力級別 A 或額外匯出格式帶入第一版。

## 11. 本輪決策與下一個 gate

Product Owner 於 2026-09-04 同意 §3.1～§3.4 的概念方向，並要求「第一版不可缺少」不能先寫死；其後回覆「OK，繼續」，核准 §3.4.1～§3.4.4 的雙軸證據分類為 G3 Working Baseline：

- 能力層同時盤點產品效果、Agent、Context／Memory、App control、可靠性／成本、Observability 與安全／治理；
- 將「業界證據成熟度」與「Caliburn release 取捨」拆成兩軸，後續發現新的共同能力仍可補入；
- framework 選型前加入 representative scenario gate 與 AI placement／complexity gate；
- 19 層地圖只作完整性檢查與選型輸入，不逐層施工。
- 以 `S1`～`S7` 作最小代表性情境，並把「先詢問員工」「先理解工作再形成 JD」「共同編輯最新內容且 AI 變更需審核」保持為產品效果，不偷渡固定實作。

Product Owner 已核准 §3.5 的 P3「有界單一顧問＋deterministic seams」為 G3 Working Baseline；其嚴格含義是「底層責任符合跨廠證據，完整組合是 Caliburn synthesis」。

Product Owner 已核准 §9 的精簡版方案 A「LangChain stable 1.x＋LangGraph stable 1.x」作第一版 framework／durable-runtime 方向；不整包採 Deep Agents，也不引入第二套 agent loop／durable owner。這是 G3 Working Decision，仍可依本文件列出的重開條件翻案，但不越過現行 production authority。

本次核准不表示全部第一版能力都要施工，也不核准精確版本 pin、Tool／Skill／Prompt schema、產品資料結構、模型、spike 或 production 施工。下一個 gate 是把 G4 最小 runtime contract 建成單一可回答的設計題，再進行正常資料流、責任、錯誤／恢復、成本與 pass／fail 審查。

## 12. 官方來源索引

### OpenAI

- [Current model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Responses API：create a model response](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [Responses API migration](https://developers.openai.com/api/docs/guides/migrate-to-responses)
- [Models and providers — Agents SDK](https://openai.github.io/openai-agents-python/models/)
- [Running agents](https://openai.github.io/openai-agents-python/running_agents/)
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [Agent Skills](https://developers.openai.com/api/docs/guides/tools-skills)
- [Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- [Tracing](https://openai.github.io/openai-agents-python/tracing/)

### Anthropic

- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Scaling Managed Agents：Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents)
- [Tool use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [Working with Messages](https://platform.claude.com/docs/en/build-with-claude/working-with-messages)
- [Manage tool context](https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context)
- [Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview)
- [Agent configuration](https://platform.claude.com/docs/en/managed-agents/agent-setup)
- [Agent Skills](https://platform.claude.com/docs/en/managed-agents/skills)
- [API data retention and state boundaries](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)

### Google／AWS／Microsoft

- [Google agent design patterns](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)
- [Google ADK](https://adk.dev/)
- [Google ADK sessions](https://adk.dev/sessions/session/)
- [Google ADK Memory](https://adk.dev/sessions/memory/)
- [Google ADK human input](https://adk.dev/graphs/human-input/)
- [Amazon Bedrock AgentCore developer guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Amazon Bedrock AgentCore Harness vs. Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html)
- [Amazon Bedrock AgentCore Harness security](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-security.html)
- [Amazon Bedrock AgentCore Harness tools／client-side approval](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-tools.html)
- [Strands model providers](https://strandsagents.com/docs/user-guide/concepts/model-providers/)
- [Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Microsoft Agent Framework pipeline](https://learn.microsoft.com/en-us/agent-framework/agents/agent-pipeline)
- [Microsoft Agent Framework model providers](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/model-providers/)
- [Microsoft workflow checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- [Microsoft map agent flows](https://learn.microsoft.com/en-us/agents/architecture/map-agent-flows)
- [Microsoft Tool approval](https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval)

### Frameworks

- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangChain models](https://docs.langchain.com/oss/python/langchain/models)
- [LangChain OpenRouter integration](https://docs.langchain.com/oss/python/integrations/chat/openrouter)
- [LangChain 1.4.0 package release](https://pypi.org/project/langchain/1.4.0/)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [Frameworks, runtimes, and harnesses](https://docs.langchain.com/oss/python/concepts/products)
- [PydanticAI overview](https://pydantic.dev/docs/ai/overview/)
- [PydanticAI version policy](https://pydantic.dev/docs/ai/project/version-policy/)
- [PydanticAI message history](https://pydantic.dev/docs/ai/core-concepts/message-history/)
- [PydanticAI retries](https://pydantic.dev/docs/ai/core-concepts/retries/)
- [PydanticAI deferred Tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [PydanticAI on-demand capabilities](https://pydantic.dev/docs/ai/capabilities/on-demand/)
- [PydanticAI Harness](https://pydantic.dev/docs/ai/harness/)
- [PydanticAI Harness 0.29.0 package release](https://pypi.org/project/pydantic-ai-harness/0.29.0/)
- [PydanticAI Harness Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/)
- [PydanticAI durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)
- [PydanticAI DBOS integration](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)

## 13. Decision delta

### 2026-09-04：從窄 provider／Tool 題重開為完整 LLM 系統父層

Owner 指出目前研究只涵蓋 provider／Tool loop，尚未完整審核模型、input、output、Skills、Memory、context、框架與整個顧問流程；且不得把舊程式或舊元件當目標架構。故新增 `LLM-Q002`，先完成父層責任與成熟 primitive 地圖；`LLM-Q001` 的 G5 實作暫停，避免在上層框架尚未決定時把窄 contract 固化進產品。

### 2026-09-04：Owner 同意父層，要求補齊 LLM 控制 JD App

Owner 同意 §3～§4 作為父層，但補充 AI 必須像成熟 workspace agent 一樣透過受控能力編輯 JD。本文因此把第 10 層明確化為 Application workspace／Tools，並在 §6.1 分開「跨廠成熟機制」與「Caliburn 必須自行定義的產品內容」。這仍是 G2／G3 設計對齊，不授權 Tool schema 或 production 施工。

### 2026-09-04：Owner 同意 App-control 邊界，要求能力層不可只看產品功能

Owner 同意 §6.1，並指出能力盤點若只從已知 Caliburn 使用情境出發，會漏掉 tracing、context lineage、Skill／Tool usage、成本、安全與演進等共同能力。本文因此新增 §3.1：先建立開放式 capability catalogue，再分類現在必要、條件式、延後與廠商選項；未被使用者事先說出的跨廠共同能力也必須納入研究。

### 2026-09-04：Owner 同意從 0 設計流程與兩個前置 gate

Owner 同意 §3.1～§3.2。Capability Catalogue 必須保持開放；19 層只作完整性檢查。正式比較 framework 前，先以少量代表性產品情境固定真實成功／失敗效果，再逐項決定 deterministic code、單次 model call、固定 workflow、bounded single agent 或 human interrupt。下一輪先整理代表性情境，不開始 framework 選型或 production 施工。

### 2026-09-04：Owner 同意七組代表性產品情境與 mechanism-neutral 邊界

Owner 同意以七組情境覆蓋訪談起始、長訪談與相似案例、自然更正與先詢問員工、先理解工作再形成 JD、AI／員工共同編輯最新內容、同時操作與失敗恢復，以及最終完整品質盤點。Owner 特別校正：JD 不是每個案例的紀錄；「需要你的確認」不是固定 UI，而是 LLM 不得自行裁決、必須先詢問員工的效果；共同編輯也不預先決定物理文件數或審核粒度。所有內容仍是可經研究與討論翻案的 Working Baseline，不授權 framework、schema、UI 或 production 施工。

### 2026-09-04：Owner 同意候選能力概念，要求先完成跨廠證據分類

Owner 認為六面向候選能力概念正確，但不同意直接把它們寫死為第一版 Required。本文因此只保存候選 capability families；下一個 gate 先逐項查證哪些是跨廠共同能力、強趨勢、Caliburn 產品必要效果、條件式能力或廠商選項，完成後再由 Owner 核准正式分類，之後才進 AI／deterministic／human placement。

### 2026-09-04：雙軸分類核准，責任 placement 進入 G2 審核

Owner 回覆「OK，繼續」，核准 §3.4 的雙軸分類為可由新證據翻案的 G3 Working Baseline。本輪依五家官方契約與成熟 framework primitive 整理 §3.5：模型處理語意、Runtime 承接通用 execution machinery、deterministic Caliburn code 保證 scope／invariant／authority、員工提供真實答案並核准 AI 變更；另以 product policy／Skills 作治理內容而非第五個執行者。P1～P3 與推薦 P3 仍是 G2 選項，等待 Owner 裁決，不授權 framework 選型或施工。

### 2026-09-04：P3 經共識邊界複核後核准為 G3 Working Baseline

Owner 要求先確認是否真為目前大廠共識，若成立則同意。複核 OpenAI、Anthropic、Google、AWS 與 Microsoft 現行官方資料後，本文明確區分：模型／Tool／Runtime／deterministic application／human input 的底層責任方向是跨廠共同；從簡單 single-agent 起步是強趨勢；`P3` 名稱、四欄矩陣及「所有 AI JD 變更均須員工審核」的精確產品規則則是 Caliburn synthesis／產品政策，不冒充廠商共同標準。Owner 的條件成立於這個嚴格範圍，因此 P3 升為 G3；框架 A／B、Tool、Skill、Prompt、schema、模型與 production 施工仍未核准。

### 2026-09-04：A／B framework 比較完成，提出 G2 推薦

依相同 `S1`～`S7` 與九項標準逐項核對官方能力後，方案 A「LangChain stable 1.x＋LangGraph stable 1.x」在長期 thread、server-held state、HITL、PostgreSQL persistence 與 crash/restart responsibility 上能由一套 runtime 承接；方案 B 功能完整且在 typed Capability／成本治理上更強，但需把 PydanticAI Core、0.x Harness 與另一個 durable engine 接成一套，留下較多尚未驗證的 integration seam。故本研究提出 A 為第一版 G2 推薦，且只採精簡 primitives、不整包啟用 Deep Agents。這仍等待 Owner G3 核准，不授權 G4 schema、spike 或 production 施工；LangGraph 目前未結案 issue 亦明列為核准後的 bounded characterization 風險。

### 2026-09-04：Owner 核准精簡版方案 A 為 G3 Working Decision

Product Owner 回覆「同意」，核准 LangChain stable 1.x＋LangGraph stable 1.x 作第一版 framework／durable-runtime 方向；不整包採 Deep Agents，不引入 PydanticAI Agent 作第二套 agent loop，也不加入 DBOS 等第二套 durable owner。核准理由是 A 在相同產品情境下以一套 stable runtime 承接長期 thread、HITL、PostgreSQL persistence 與 resume，而不是宣稱各家大廠共同選用此框架。效力只到 framework 方向；精確版本 pin、Tool／Skill／Prompt schema、產品資料結構、模型、spike 與 production 施工仍未核准。下一 gate 進入 G4 最小 runtime contract；若官方能力改變、bounded characterization 證明關鍵假設不成立、必要 provider capability 缺失或產品不再需要 durable server-held state，依 §9.5 重開 A／B。
