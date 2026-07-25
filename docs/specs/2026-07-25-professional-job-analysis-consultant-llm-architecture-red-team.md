# AI 專業職務分析顧問：LLM 程式架構紅隊審查與修正版

> 日期：2026-07-25
> 狀態：Proposed，供產品與實作決策使用
> Revision：3，補齊顧問流程追蹤所需的來源／工作／文件三層、恢復、短回答、故事焦點與直接編輯語意
> 範圍：從零設計一套能實現既定「專業職務分析顧問流程」的 LLM 程式架構
> 需求權威：[`2026-07-25-professional-job-analysis-consultant-process-final-red-team.md`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)
> 明確排除：既有 vNext、舊 AI 流程、既有 API／資料表相容、SaaS、帳號密碼、多租戶與多人協作

---

## 1. 文件目的

前一份文件已回答「專業顧問應該如何訪談、分析與完成職務說明書」。本文件只回答下一層問題：

> 要用什麼 LLM 程式架構，才能忠實實現該顧問流程，而且不把它做成固定問卷、自由聊天或一堆難以驗證的 Agent？

本文件不是資料庫 migration、API endpoint 或 class-by-class 實作規格，也不要求整合現有程式。它先固定：

1. 系統必須保存哪些語意；
2. LLM 與程式各自負責什麼；
3. 一輪訪談如何運作；
4. Context 如何選取；
5. Task、O/P/K/S 與文件提案如何產生；
6. 什麼由 deterministic code 保證，什麼必須靠 LLM、評測與員工判斷；
7. 第一版哪些能力不能提前做。

本文件同時刻意執行一次：

> **Make the strongest case that this architecture was wrong.**

目的不是讓架構顯得複雜，而是在寫程式前先找出最可能重演上一版失敗的地方。

---

## 2. 最終結論

### 2.1 推薦架構

推薦採用：

> **受約束的自適應顧問核心（Bounded Adaptive Consultation Kernel）**

它不是單一大 Agent，也不是固定階段狀態機，更不是 Planner + 多 Agent 工廠。核心分工是：

- **程式擁有**
  - 已完成對話；
  - 工作模型；
  - 更正與矛盾；
  - Context 選取規則；
  - 允許的顧問動作；
  - AI 提案與員工決策；
  - 正式 JD；
  - 儲存、恢復與基本不變量。
- **LLM 擁有**
  - 理解自然語言；
  - 找出一句話裡的多個工作訊號；
  - 跨故事比較；
  - 判斷 Task 邊界；
  - 選擇當下最高價值的追問；
  - 產生 O/P/K/S 候選；
  - 提出員工看得懂的文件修改建議；
  - 在完成前反向挑錯。
- **員工擁有**
  - 接受、修改、拒絕或延後 AI 提案；
  - 直接編輯自己的 JD；
  - 說明 AI 的理解是否錯誤；
  - 決定何時先完成目前版本。

### 2.2 一句話架構

```text
員工回答
  → 高召回理解所有訊號
  → 更新開放世界工作模型
  → 跨故事校正 Task 邊界
  → 選擇一個最高價值顧問動作
  → 追問或提出 JD 修改
  → 員工接受／修改／拒絕
  → 保存完整回合與目前 JD
```

### 2.3 為什麼這是目前最合理的主流方向

此方向與目前權威實務的共同原則一致：

- Anthropic 建議先使用簡單、可組合、可觀察的 workflow，只有在任務確實需要動態路徑時才增加 agentic autonomy；本產品需要彈性，但不需要讓模型自由建立無限工具鏈。[Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Anthropic 的訪談研究把共同研究目標、訪談規劃、自適應追問、分析與人工檢查分開，而不是把一切藏在一個超長 prompt。[Anthropic — Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)
- OpenAI 與 Anthropic 都把 Context 視為需要主動選擇與管理的有限資源，不建議把所有歷史內容無差別塞回每一次模型呼叫。[OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)、[Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Structured Outputs 能保證資料形狀，不能保證工作分析語意正確，因此仍需要 semantic verification、評測與員工決策。[OpenAI — Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- OPM 與 O*NET 都強調 Task、能力及其 linkage，也強調 Task 必須描述有意義的工作結果，而非任意動作或工具名稱。[OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)、[O*NET — Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf)

### 2.4 不能誠實宣稱的事

第一版只能合理宣稱產出：

> 一份由員工參與審核、具工作證據、可繼續修訂的高品質職務說明書草案。

不能只靠單一員工訪談就宣稱：

- 已代表組織內所有同職位人員；
- 已經主管、HR、法遵或職務分析 SME 驗證；
- 可直接作為薪酬、解僱或高風險人事決策的唯一依據；
- 所有內容都是真實世界的客觀真相。

這是產品誠實邊界，不是架構缺陷。第一版目標仍然可以是「比一般人工自行撰寫更完整、更有方法、更少漏項」。

---

## 3. 從顧問流程導出的硬需求

程式架構不得自行發明另一套流程。以下是顧問流程對軟體的直接要求。

### 3.1 固定分析責任，彈性訪談路徑

系統必須完成的分析責任固定：

1. blind-first 角色定位；
2. 工作週期廣度盤點；
3. 故事與事件深挖；
4. Work Unit 與 Task 邊界分析；
5. 跨故事合併、拆分與修正；
6. Duty 整併；
7. O/P/K/S 漸進分析；
8. 公版 coverage challenge；
9. 文件共編；
10. 最終反方檢查。

但這些不是只能依序走一次的頁面精靈。員工在任何階段都可能：

- 補充新的工作；
- 更正舊說法；
- 談到另一個故事；
- 提出 Output、Indicator、Knowledge 或 Skill；
- 說明某項工作其實是別人的；
- 直接編輯 JD；
- 暫時跳過某個問題。

因此「固定」的是分析責任，不是問題順序。

### 3.2 每輪必須先理解整段話，再決定焦點

如果目前正在問 Output，而員工回答：

> 我通常會整理異常報告給主管，但最近也開始負責跟供應商確認修復時程。

系統不能只擷取「異常報告」而丟掉新的「供應商協調」工作訊號。

每一輪都必須：

1. 掃描整個新回答；
2. 找出所有可能相關訊號；
3. 先保存，不要求當輪全部解決；
4. 再選擇一個最值得追問或提案的焦點。

這裡的「全域理解」不是每輪重讀全部 transcript，而是：

- 新回答必須高召回掃描；
- 歷史資訊先進入可查詢的工作模型；
- 各操作只取回與當前判斷相關的來源；
- 未能映射的內容必須保留，不能因 schema 沒欄位就消失。

### 3.3 Story、Work Unit 與 Task 必須多對多

系統不得預設：

```text
一段回答 = 一個故事 = 一個 Task
```

實際可能是：

- 一個故事包含三種穩定工作；
- 三個故事共同證明同一個 Task；
- 一個故事只是例外，不應形成 Task；
- 一段回答只描述工具或步驟，沒有新的 Task；
- 原本看似兩個 Task，後來發現應合併；
- 原本看似一個 Task，後來因 Output 或責任邊界而拆分。

### 3.4 O/P/K/S 不是填空，且可以反向修正 Task

架構必須支援雙向關係：

```text
Task → Output / Indicator / Knowledge / Skill
```

也必須支援：

```text
Output / Indicator / Knowledge / Skill
  → 發現 Task 邊界不對
  → 重新合併、拆分、改寫或追問
```

例如兩項工作看似相似，但產出與判斷責任完全不同，可能應拆成兩個 Task。反之，多個操作使用不同工具，但共同產生同一穩定結果，可能只是一個 Task。

### 3.5 公版是後段挑戰者，不是早期答案

公版資料可以用來：

- 發現員工可能漏講的工作；
- 提供 Task、K、S 候選；
- 比較常見職業內容；
- 支援公版格式匯出。

但公版不能：

- 在角色尚未理解前定義員工；
- 自動寫入正式 JD；
- 把「該職業常見」當成「這位員工真的負責」；
- 阻止建立公版沒有的客製內容。

### 3.6 AI 不得直接改正式文件

AI 可以提出的文件變更只有：

- add；
- edit；
- merge；
- split；
- delete；

`no-op` 與 `clarify` 是工作分析／reconciliation 判斷；`defer` 是員工對 proposal 的決定。三者都不是正式文件變更類型。

只有員工接受或修改後，內容才進入正式 JD。員工直接手動編輯則可直接成為文件內容。

### 3.7 正常完成的回合必須可恢復

員工可在一輪 AI 回答完成後離開，隔天回來繼續。

恢復時至少要回到：

- 相同對話歷史；
- 相同目前 JD；
- 相同工作模型；
- 相同未決問題與矛盾；
- 相同 AI 提案及員工決策；
- 相同訪談焦點與 coverage 狀態。

第一版不需要保存 token 生成到一半的狀態，也不需要恢復 AI 回答一半的 workflow。

### 3.8 來源、工作模型與正式文件必須是三層不同真相

為了防止「員工提過」被誤寫成「正式 JD 已採用」，程式語意必須分成三層：

1. **Source Layer**：員工訊息、問題與短回答、員工提供的 SOP／表單／工作清單／報告範本／舊 JD／實際產出；
2. **Work Model**：AI 對來源形成的 claim、Story、Work Unit、Task candidate、coverage、conflict 與 hypothesis；
3. **Document Layer**：員工已接受提案或直接編輯後的 Current JD。

三層可以互相連結，但權限不同：

- Source Layer 是輸入，不因文件看起來正式就成為現況真相；
- Work Model 是可被更正、重開與推翻的分析；
- Document Layer 是目前文件真相，但仍不自動成為工作事實；
- 員工直接編輯 Document Layer 時，相關 Work Model 要標記為待重整，不可反向偽造訪談來源。

這是語意分層，不要求三個服務、三套資料庫或複雜 provenance 平台。

---

## 4. 三種可行架構比較

### 4.1 方案 A：單一大 Agent

```text
所有對話 + JD + 公版
  → 一個大型 system prompt
  → Agent 自行理解、規劃、追問、改文件
```

#### 優點

- 原型最快；
- 對話表面自然；
- 不需要先定義太多內部物件；
- 模型可自由處理未預期情況。

#### 最強反方

它把以下責任全部藏在 prompt 與模型臨場行為中：

- 哪些是事實；
- 哪些已被更正；
- 哪些只是候選；
- 下一步為何；
- 何時可修改文件；
- 員工拒絕過什麼；
- 何時算完成。

結果是：

- 同一份對話多跑幾次，Task 邊界可能不同；
- 長上下文中的更正容易失效；
- 模型可能把工具、過去工作或他人工作寫入 JD；
- 難以知道問題來自 prompt、context、模型、檢索或流程；
- 只要 prompt 變長，就容易誤以為能力變強。

若替方案 A 加上 application-owned state、typed action、proposal gate 與恢復能力，它就已經逐漸變成本文件的推薦方案。

#### 裁決

可用作最早期 demo，不適合作為正式產品核心。

---

### 4.2 方案 B：固定階段與欄位流水線

```text
角色定位 → Task → Output → Indicator → K → S → 完成
```

#### 優點

- 可預測；
- 容易測試；
- 容易知道目前在哪一階段；
- 容易產出完整格式。

#### 最強反方

它假設員工會照系統順序說話，但真實訪談不會。

可能造成：

- 談 K/S 時出現新 Task，系統不接；
- 為了完成欄位而虛構 O/P/K/S；
- 每個故事硬形成一個 Task；
- 公版欄位完整但工作分析錯誤；
- 員工被迫經歷很長的問卷；
- 過早固定職業與 Task 邊界。

#### 裁決

不能採用硬階段狀態機。可以保留 coverage 與顧問責任，但不能把它們當成單向流程。

---

### 4.3 方案 C：Planner／Executor／多 Agent

```text
Planner Agent
  → 建訪談計畫
  → Interview Agent
  → Task Agent
  → OPKS Agent
  → Reviewer Agent
```

#### 優點

- 責任看似清楚；
- 每個 Agent 可有專門 prompt；
- 適合事前無法預測的大型工作分解；
- 有機會提高複雜任務的上限。

#### 最強反方

訪談計畫會在員工下一句話後立即過期。Planner 一旦誤判，其他 Agent 會忠實放大錯誤。

還會增加：

- 呼叫成本與延遲；
- 跨 Agent context 損失；
- 狀態同步問題；
- 責任歸因困難；
- 多個模型互相確認錯誤的假安全感；
- 不必要的框架與部署複雜度。

Anthropic 把 orchestrator-workers 放在「子任務數量與性質事前無法預測、而且可獨立處理」的場景；一般互動式訪談不自然符合這個條件。[Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

#### 裁決

第一版不採用。只有日後評測證明單一受約束流程無法處理某些可分解任務，才針對那個 operation 局部引入。

---

### 4.4 推薦方案：受約束的自適應顧問核心

```text
                 ┌──────────────────────┐
                 │ Consultation State   │
                 │ + Open Work Model    │
                 └──────────┬───────────┘
                            │
員工訊息 ─→ Context Policy ─→ LLM Operations
   ↑                        │
   │                 Consultation Controller
   │                        │
   └─ 提問／提案 ← Guardrails + Proposal Boundary
                            │
                      Current Job Document
```

它保留：

- 模型對自然語言與專業判斷的彈性；
- 程式對文件真相、狀態與合法動作的控制；
- 員工對正式文件的最終決定權；
- 可被評測與逐步替換的 operation 邊界。

它刻意不建立：

- 可自由產生任意子 Agent 的 planner；
- 固定欄位順序；
- 無限工具 loop；
- Graph DB；
- 全功能 workflow 平台；
- 以 provider abstraction 為產品核心的框架。

---

## 5. Make the strongest case that the recommended architecture was wrong

即使採用推薦方案，仍有以下致命風險。

### 5.1 Typed Work Model 可能把錯誤本體固化

如果內部只允許 `Task / Output / Indicator / Knowledge / Skill`，模型會把所有資訊硬塞進這些格子。

例如：

> 我每天看監控，異常時判斷要不要停線；重要的是知道什麼情況不能繼續跑。

真正的價值可能是：

- 風險判斷；
- 停線權限；
- 例外處理；
- 責任邊界；
- 隱性知識。

若只產生「監控設備」與「通知異常」，JD 形式正確但核心工作錯誤。

#### 修正

工作模型必須是 open-world：

- 允許尚未分類的 `UnmappedSignal`；
- 允許 `unknown`，且 unknown 不等於不存在；
- 允許矛盾、否定、過去、他人責任與一次性事件；
- 保留原始訊息；
- 類型用來支援判斷，不得刪除無法映射的內容。

### 5.2 「每輪全域理解」可能只是口號

模型有有限注意力。長對話全部塞回去，並不保證更正、否定與跨故事關係會被正確使用；還可能因 context rot 變差。[Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

#### 修正

- 每個新回答做高召回掃描；
- 歷史資訊轉成可查詢工作模型；
- 需要時回取原始片段；
- 每個 operation 使用不同 context packet；
- 更正與拒絕在 context 排序上高於舊摘要；
- 定期檢查 unmapped residue，而不是只看已結構化內容。

### 5.3 Coverage 會讓系統為了通過指標而填滿欄位

若完成條件只是：

- 每個 Task 有 Output；
- 每個 Output 有 Indicator；
- 每個 Task 有 K/S；
- 所有 coverage 都是綠色；

模型會傾向補出漂亮但沒有根據的內容。

#### 修正

- coverage 是顧問導航，不是真相分數；
- 欄位可明確標為 unknown／not applicable；
- 沒有自然 Output 或數字門檻時不得虛構；
- 最終檢查要特別尋找漏項、過度合併、過度拆分與 unsupported claims；
- 員工可以帶著非關鍵 unknown 完成。

### 5.4 員工接受可能成為橡皮圖章

員工不是職務說明書專家，可能因 AI 寫得流暢就接受。

#### 修正

提案畫面與文字必須：

- 用白話說明改了什麼；
- 明示增加、刪除、合併或拆分；
- 說明為何這是 Task，而非工具或步驟；
- 提醒尚未確定之處；
- 避免一次顯示太多變更；
- 允許員工直接修改後接受；
- 後續新證據仍可重新挑戰已接受內容。

員工接受代表「目前文件決策」，不代表外部專家驗證。

### 5.5 Evidence linkage 可能變成引用洗白

有一段引用，不代表它支持該 Task。原句可能是：

- 「以前做過」；
- 「不是我負責」；
- 「偶爾幫忙」；
- 「我不會使用」；
- 「只是方法」。

#### 修正

來源不是只存 message ID，還要保留最少必要語意：

- 誰的工作；
- 現在／過去／未來；
- 肯定／否定；
- 常態／例外／一次性；
- 頻率或典型性；
- 不確定程度；
- 支持、反對或更正哪個結論。

正式內容仍只需要簡單 source pointer，不需要第一版就建立複雜 provenance 平台。

### 5.6 Structured Output 可能產生「合法即正確」錯覺

符合 JSON Schema 只代表可以解析，不代表 Task 邊界、O/P/K/S 或來源判斷正確。[OpenAI — Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

#### 修正

分成三層：

1. **格式驗證**：欄位、型別、ID、enum；
2. **領域不變量**：不得直接改正式 JD、連結對象存在、更正優先；
3. **語意品質**：Task 邊界、支持程度、完整性，由 rubric、模型評測與人工閱讀判斷。

不得把第三層偽裝成 deterministic guarantee。

### 5.7 Provider-neutral 可能退化成最低共同能力

如果所有模型都被壓成一套最小共同參數，較強模型的能力會被隱藏，評測也只剩 adapter 相容性。

#### 修正

- 第一版固定一個經評測的模型；
- Provider Adapter 保持薄；
- domain operation 契約中性，但允許 capability profile；
- 不承諾不同模型完全等價；
- 換模型必須重新跑品質案例；
- provider auto-routing 不能替代品質評測。

### 5.8 多次 LLM 呼叫可能讓錯誤累積

如果每輪都依序呼叫五到十個模型，前一步錯誤會污染後一步，也會造成高延遲與高成本。

#### 修正

採用「兩條路徑」：

- **一般回合**：理解 + 回應，通常 2 次模型呼叫；
- **深度回合**：只有遇到跨故事重整、文件提案或完成檢查時才追加專門 operation。

每個 operation 都可單獨評測，不建立固定五段流水線。

### 5.9 單一員工仍可能漏掉職務真相

再好的架構也無法從未被提供的資訊推導真相。

#### 修正

- 使用工作週期、例外、交接與低頻高影響問題主動降低遺漏；
- 公版只用來 challenge coverage；
- 完成前明示仍未確認的項目；
- 文件標示為員工共編結果；
- 未來若產品需要組織級驗證，再加入主管、同儕、文件或觀察來源；第一版不提前做多人流程。

### 5.10 Graph Engineering 可能把流程複雜度誤認成品質

2026 年 7 月開始流行的「Graph Engineering」，常以：

```text
Planner
  → Worker
  → Reviewer 1..N
  → Synthesize
  → Pass?
  → 失敗回 Worker
```

描述多個 Agent、驗證器與回饋 loop 的連接方式。

這個視角有價值，但若直接套在本產品每一輪訪談，可能造成：

- 每次員工回答都啟動 Planner、Worker 與多個 Reviewer；
- 不同 Agent 各自保存不同版本的工作真相；
- Reviewer 一起確認同一個錯誤；
- 多階段摘要產生「傳話遊戲」；
- latency、token 與 failure surface 大幅增加；
- 顧問問題還沒有證明更好，架構先變成多 Agent 平台。

Anthropic 的多 Agent Research 顯示，此模式特別適合可大量平行探索、資訊超出單一 context、且工具很多的高價值研究任務；同一篇官方紀錄也指出，多 Agent 約消耗一般聊天 15 倍 token，而且高度共享 context、相依性高的工作並不適合。[Anthropic — Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)

職務訪談的每一輪高度依賴同一份工作模型、更正、員工決策與歷史語境，因此不能因為「Graph Engineering」是新名詞，就預設多 Agent 一定更強。

#### 修正

- 採用 Graph Engineering 的顯式節點、edge、route、authority、failure path 與 stop condition；
- 不採用「每個節點都是 Agent」的假設；
- 長期存在的是 application-owned state，不是多個 Agent 的私有記憶；
- 模型操作預設為 ephemeral，由 Context Policy 每次供應明確 context；
- 多 Reviewer 只在高風險、可獨立檢查且 eval 證明有效的節點啟用；
- 第一版先用普通程式碼表示 Execution Graph，不導入 Graph runtime。

---

## 6. 修正後的整體架構

架構不是十五個獨立服務，而是六個核心責任、兩個邊界與兩個橫切能力。

```text
┌──────────────────────────────── Local Web App ────────────────────────────────┐
│                                                                               │
│  Employee UI                                                                  │
│     │                                                                         │
│     ▼                                                                         │
│  ① Consultation Controller ────────────────┐                                  │
│     │                                      │                                  │
│     ├─ ② Context Policy                    │                                  │
│     │      │                               │                                  │
│     │      ▼                               │                                  │
│     ├─ ③ LLM Operations ── ⑦ Model Gateway│                                  │
│     │      │                               │                                  │
│     │      ▼                               │                                  │
│     ├─ ④ Open Work Model / State           │                                  │
│     │      │                               │                                  │
│     ├─ ⑤ Proposal & Document Boundary ◄────┘                                  │
│     │                                                                         │
│     └─ ⑥ Public Reference Challenger                                         │
│                                                                               │
│  Cross-cutting: ⑧ Guardrails / ⑨ Observability                               │
└───────────────────────────────────────────────────────────────────────────────┘

Offline, separate from runtime:
⑩ Quality Harness
```

### 6.1 ① Consultation Controller

它是應用流程的唯一控制者，但不是專業判斷的唯一來源。

負責：

- 接收 employee message、proposal decision、direct document edit 與 resume session 四種入口事件；
- 接收新員工訊息；
- 建立本輪需要的 context；
- 呼叫正確 LLM operation；
- 驗證模型輸出；
- 更新工作模型；
- 判斷是否需要 reconciliation；
- 選擇「追問、挑戰、提案或回顧」；
- 確保 AI 不直接寫入正式 JD；
- 在員工直接編輯後標記受影響的分析、coverage 與提案為待重整，必要時安排中性澄清；
- 在完整回合成功後保存；
- 恢復先前狀態。

不負責：

- 用大量 if/else 寫死專業顧問的每個語意判斷；
- 自動把每個訊號升格為 Task；
- 自行編造 Output、Indicator、K 或 S；
- 執行無限 agent loop。

### 6.2 ② Context Policy

Context Policy 合併了傳統所說的 Prompt Engineering、Context Engineering 與 Retrieval Policy。

它負責：

- 這次 operation 的 system/developer instructions；
- 短回答的 `QuestionContext`：原問題、問題目標、預期回答範圍與允許的「不知道／不適用」；
- 應該給模型哪些現況；
- 應回取哪些原始訊息；
- 哪些資料禁止進入；
- 哪些更正、拒絕與矛盾要優先；
- context 太長時如何取捨；
- 明確告知模型哪些相關來源因預算未載入，避免把「未載入」誤判為「不存在」；
- public reference 何時才可使用；
- 把員工提供的工作文件與公版 reference 分區，兩者都不得覆蓋系統規則或自動升格為事實；
- prompt 與 context policy 的版本。

Prompt 不是獨立大腦；它只是 Context Policy 的一部分。

### 6.3 ③ LLM Operations

LLM Operations 是少數可評測的專業能力，不是多個人格化 Agent。

建議操作如下：

| Operation | 核心責任 | 是否每輪都跑 |
|---|---|---:|
| `turn.understand` | 高召回理解新回答的所有訊號、claim、更正、未知與未映射內容 | 是 |
| `work.reconcile` | 跨故事比較 Work Unit、Task candidate 與既有 Task，提出 add/edit/merge/split/no-op/clarify | 條件式 |
| `consultation.decide` | 根據 coverage、矛盾、重複負擔與目前焦點，選一個最高價值顧問動作 | 是，可與回應生成合併 |
| `job.analyze` | 依穩定 Task 漸進分析 Duty、Output、Indicator、Knowledge、Skill；在有明確工作行為支持時才處理 Attitude，並可要求 reopen Task | 條件式 |
| `document.propose` | 把已分析結果轉成員工看得懂的文件差異與理由 | 條件式 |
| `public.challenge` | 比較 deterministic retrieval 提供的少量公版候選與 Work Model，形成 match/partial/no-match/conflict 及追問／提案建議 | 條件式 |
| `quality.challenge` | 完成前主動找漏項、虛構、錯誤責任、過度拆分／合併與 unsupported claims | 完成前 |

這些是語意責任，不代表一定各有一個 class、microservice 或模型呼叫。

第一版可以把：

- `consultation.decide` 與自然語言回應生成合併；
- `job.analyze` 與 `document.propose` 在簡單情況合併；
- 複雜 reconciliation 才獨立呼叫。

`public.challenge` 不擁有 retrieval、Current JD 或員工決策。Retrieval node 負責取得候選；此 operation 只作語意比較，
輸出只能導向 `validate_or_challenge` 或 `propose_document_change`，不得自行把公版內容寫入正式文件。

### 6.4 ④ Open Work Model / Consultation State

這是產品可以恢復、比較與修正的核心，不是完整 transcript 的摘要。

最小語意物件：

#### A. Conversation

- 已完成的 employee / AI turns；
- 每則訊息穩定 ID；
- 目前 active question 或 focus；
- 上次停止原因與建議下一個動作；
- 文件是否已完成、是否因新資訊或員工選擇而重新開啟；
- 不需要 token-level checkpoint。

#### A2. Employee Supporting Artifact

員工可選擇提供：

- SOP；
- 表單；
- 工作清單；
- 報告或產出範本；
- 舊 JD；
- 其他能幫助回憶或交叉檢查的工作材料。

第一版只需保存來源 ID、名稱、類型與可供分析的內容；不要求一定上傳。這些資料屬於 Source Layer，必須視為不可信輸入，
不能因其格式正式就覆蓋員工現況、系統指令或文件權限。

#### B. Source Claim

從員工原話辨識出的最小可判斷陳述，例如：

- 「我每週彙整異常資料」；
- 「停線不是我決定」；
- 「以前負責供應商，現在只審核」。

至少保留：

- statement；
- source message；
- subject／ownership；
- current / past / future；
- positive / negative；
- routine / exception / one-off；
- frequency／typicality（若有）；
- certainty；
- supports / contradicts / supersedes 關係；
- mapped 或 unmapped。

#### C. Role Hypothesis

- 角色存在的暫定 purpose；
- 成果接收者／服務對象；
- 主要責任範圍；
- 工作環境與限制；
- 2–3 個暫時角色假說；
- 職稱無法解釋的混合或兼任工作；
- 支持訊號；
- 反例；
- 未決問題；
- 狀態：active / weakened / rejected / accepted-for-now。

角色假說不能直接決定 JD。

#### D. Story 與 Work Unit

- Story：員工描述的一段具體事件；
- Story Focus：目前正在深挖哪個故事，以及 chronology、input、action、judgment、outcome、recipient、ownership、typicality
  哪些位置已知或仍缺；
- Work Unit：故事中可比較的工作片段；
- 一個 Story 可連多個 Work Unit；
- 多個 Story 可支持同一 Work Unit 或 Task；
- Work Unit 可標為 current、past、other-person、one-off、uncertain。

#### E. Task Candidate 與 Task

Task Candidate 是待判斷工作，不是正式 Task。

Task 邊界至少檢查：

- 有動作；
- 有作用對象；
- 有 meaningful outcome；
- 屬於員工目前責任；
- 是穩定／典型責任，或低頻但屬正式高影響責任；
- 可獨立交辦或檢查；
- 不是只有工具、方法、技術名稱或子步驟。

Task 必須能：

- merge；
- split；
- edit；
- reopen；
- supersede；
- link 多個來源。

#### F. Duty、O/P/K/S 與 Attitude

- Duty 由較穩定 Task 動態整併；
- Output、Indicator、Knowledge、Skill 分別保存；
- 每項連回一個或多個 Task；
- 欄位可 unknown 或 not applicable；
- O/P/K/S 可以觸發 Task reopen。
- Attitude 必須獨立於 Knowledge 與 Skill；不得從聊天語氣或人格印象推斷，只能從明確工作行為、公版候選與員工確認形成提案。

#### G. Coverage / Conflict / Open Issue

- 工作週期是否已觸及；
- 日／週／月／季／年工作；
- 低頻高影響；
- 監控、預防、例外、交接、判斷與授權；
- 哪些 Task 支持不足；
- 哪些說法互相衝突；
- 哪些內容尚未映射；
- 哪些問題被員工暫時跳過。

#### H. Proposal / Decision / Current JD

- AI proposal；
- proposal 類型與目標；
- before / after；
- 白話理由；
- source pointers；
- employee accept / edit / reject / defer；
- 目前正式 JD。

員工直接編輯 Current JD 時：

- 文件內容立即成為 Document Layer 的目前真相；
- 不自動建立 Source Claim，也不把編輯內容偽裝成員工曾在訪談中陳述；
- 受影響的 Task／Duty／O/P/K/S 分析、coverage 與未決 proposal 標記為待重整；
- 若直接編輯與既有工作來源矛盾，建立 open issue，後續以中性問題確認；
- 不要求員工先經 proposal 才能修改自己的文件。

Current JD 的最小產品語意可包含：

- Header／Profile：職務名稱、工作描述、基準級別，以及選填的公版代碼、職類／職業／行業分類；
- Duty；
- Task；
- Output；
- Indicator；
- Knowledge；
- Skill；
- Attitude；
- 說明與補充事項。

公版代碼與分類是外部 reference，不是本 JD 的內部 identity；未完成公版比對時可以留空。

這些是語意模型，不等於每個都要獨立資料庫表。第一版可用最容易維護且能正確恢復的儲存方式實作。

#### I. 三層權威摘要

| 層級 | 內容 | 可以直接改 Current JD 嗎 |
|---|---|---:|
| Source Layer | 員工訊息、問題脈絡、員工提供的工作材料 | 否 |
| Work Model | AI claim、Story、Work Unit、Task candidate、coverage、conflict | 否 |
| Document Layer | 員工已接受／修改後接受的提案，以及員工直接編輯 | 是，只有員工決策可成立 |

### 6.5 ⑤ Proposal & Document Boundary

正式文件與 AI 分析必須分離：

```text
Work Model / Analysis
        │
        ▼
AI Proposal
        │
        ├─ accept ─→ Current JD
        ├─ edit ───→ Employee-edited content → Current JD
        ├─ reject ─→ Rejection / correction context
        └─ defer ──→ Pending
```

必要不變量：

- LLM 不能直接 mutate Current JD；
- 一個 proposal 必須指向明確目標；
- proposal 只能使用已存在或同案建立的關係；
- employee edit 後保存的是員工修改結果；
- reject 不刪除原始對話，但後續 context 不得把被拒內容當現況；
- accepted 內容仍可被新證據重新 challenge；
- UI 顯示人類可理解差異，不顯示內部技術結構。

### 6.6 ⑥ Public Reference Challenger

公版檢索是條件式 operation，不是每輪都跑。

啟動條件：

- 已形成初步角色與工作地圖；
- 至少有一批員工自己的 Task candidate；
- 需要做 coverage challenge、K/S 候選或公版匯出比對。

流程：

```text
員工工作模型
  → 形成檢索查詢
  → lexical + dense hybrid retrieval
  → 取少量候選
  → match / partial / no-match / conflict
  → 只形成問題或 proposal
  → 員工確認
```

混合檢索可同時利用職稱、代碼、專業名詞的 lexical match 與語意相近的 vector match；但 retrieval score 不代表內容適用。[Microsoft — Hybrid search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview)

第一版不要：

- 自動把最高分候選寫入 JD；
- 每輪都檢索；
- 因公版沒有就拒絕建立客製 Task／K／S；
- 建立通用企業知識圖譜。

### 6.7 ⑦ Thin Model Gateway

Model Gateway 只處理：

- operation request；
- model/provider configuration；
- structured response；
- timeout、rate limit 與 provider error；
- usage、latency 與最少必要 diagnostics。

它不處理：

- Task 邊界；
- coverage；
- proposal decision；
- employee authority；
- document mutation；
- 顧問流程。

第一版策略：

- 固定一個經評測的模型與明確版本／slug；
- 每次只傳該 operation 所需 context，不把整個本機資料庫無差別送給 provider；
- 不做自動模型路由；
- 不假設所有 provider 品質等價；
- 同一 operation 的 prompt/context/schema 可版本化；
- 換模型前必須重跑 capability cases。

### 6.8 ⑧ Guardrails

Guardrails 是橫切防線，不是另一個 Agent。

#### 可 deterministic 保證

- AI 不直接修改 Current JD；
- proposal 目標存在；
- employee decision 合法；
- link 指向存在物件；
- source message 存在；
- correction／supersession 規則不被逆轉；
- 未提供數字時不能把模型生成數值標成已確認；
- public reference 不會自動升格成員工事實；
- employee message 與 retrieval content 都視為不可信資料，不得覆蓋 system instructions、合法 action 或文件權限；
- operation output 符合 schema；
- 回合失敗不留下半套正式文件變更。

#### 不可假裝 deterministic 保證

- Task 邊界一定正確；
- 所有工作都已被找出；
- K/S 一定完整；
- 員工自述一定客觀；
- 一段引用一定足以支持結論；
- 最終 JD 可代表全公司同職位。

後者必須交給評測、反方檢查與人類判斷。

### 6.9 ⑨ Observability

第一版只記能幫助找出品質問題的最小資訊：

- operation；
- model/provider；
- prompt/context policy version；
- latency；
- token/cost；
- parse/validation result；
- retry/error；
- proposal 是否被 accept/edit/reject；
- 評測 case 與 trial。

不需要：

- 全面分散式 tracing 平台；
- 複雜 hash chain；
- SaaS telemetry；
- 把 observability 當成內容正確性證明。

OpenTelemetry 可作為未來統一 telemetry 的標準，但它是 instrumentation 規範，不是顧問品質引擎。[OpenTelemetry — What is OpenTelemetry?](https://opentelemetry.io/docs/what-is-opentelemetry/)

### 6.10 ⑩ Quality Harness

Harness 在 runtime 外面，重播相同案例比較架構、prompt、context 與模型。

第一版不需要完整評測平台，只需要：

- 小型 JSON／fixture case；
- 可固定輸入與初始狀態；
- 可保存每輪輸出與最終 JD；
- deterministic checks；
- 少量 rubric grader；
- 重要案例人工閱讀 transcript；
- 同案例 2–3 次 trial 看穩定性。

OpenAI 建議先定義 objective、dataset、metrics，再以持續評測比較迭代；Anthropic 也強調 agent eval 應結合多次 trial、不同 grader，並實際閱讀 transcript。[OpenAI — Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)、[Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

---

## 7. Prompt、Context、Harness、Loop、Graph 的正確位置

### 7.1 Prompt Engineering

Prompt Engineering 負責：

- operation 的角色與目標；
- 欄位與判斷定義；
- 正例、反例與邊界案例；
- 不可做事項；
- 輸出 schema 說明；
- 任務判準與公版使用規則。

Prompt 不負責：

- 保存長期狀態；
- 記住員工拒絕；
- 控制正式文件寫入；
- 決定所有流程路徑；
- 取代評測。

Prompt 應在程式碼或受版本控制的檔案中管理，與 operation 及評測結果一起版本化。OpenAI 目前也建議在 API 整合中以程式化、版本化方式管理 prompt，而非把遠端 prompt object 當成永久架構核心。[OpenAI — Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering#version-prompts-in-code)

### 7.2 Context Engineering

Context Engineering 的問題不是「可以塞多少」，而是：

> 這個 operation 現在最需要看什麼，哪些內容若出現反而會造成錨定或混淆？

不同 operation 的 context：

| Operation | 必須提供 | 預設不提供 |
|---|---|---|
| `turn.understand` | `QuestionContext`、完整新回答、近期必要對話、目前 focus、精簡工作模型、相關內容未載入提示 | 大量公版候選、完整歷史 transcript |
| `work.reconcile` | 相關原始片段、claims、Stories、Work Units、相似 Task、merge/split/reject 歷史、unmapped signals | 無關職責的全文、公版答案 |
| `consultation.decide` | coverage、conflicts、open issues、目前焦點、近期已問問題、JD digest、員工負擔 | 每個原始訊息全文 |
| `job.analyze` | 穩定 Task、支持與反證、目前 O/P/K/S、相關故事 | 不相關 Task、未授權公版內容 |
| `document.propose` | 目標內容、目前 JD、已通過的分析、source pointers | 任意未驗證候選 |
| `quality.challenge` | 完整結構化工作模型、JD、coverage、conflicts、低支持內容、公版比較摘要 | 無差別完整 transcript |

Context 事實優先級：

```text
員工最新明確更正／否定
  > 員工已確認內容
  > 具來源的現行工作 claim
  > AI hypothesis / candidate
  > 公版 reference
  > 舊摘要
```

摘要只能當索引，不能取代原始來源。

### 7.3 Harness Engineering

Harness 回答：

- Task 判斷是否真的比較準；
- 是否漏掉回答中的次要工作訊號；
- 是否把工具升格成 Task；
- 是否能正確合併跨故事工作；
- 是否虛構 O/P/K/S；
- correction 與 resume 是否可靠；
- proposal 是否守住員工決定權；
- 改 prompt／context／模型後是否退化。

它不應為了追求 100% 測試覆蓋而拖延成品，也不需要一開始建立通用 eval 平台。

### 7.4 Loop Engineering

Loop 是每輪「理解 → 更新 → 選擇 → 回應 → 保存」的控制策略。

對外的顧問動作以顧問流程文件為唯一詞彙：

- `broaden`：補工作地圖；
- `deepen_story`：深挖具體故事；
- `clarify_boundary`：釐清責任、時間、頻率、結果或 Task 邊界；
- `validate_or_challenge`：確認理解、處理矛盾、反例或公版候選；
- `propose_document_change`：提出文件修改；
- `review_completion`：回顧目前 JD、coverage、缺口與完成條件。

每輪只選一個主要動作，避免一次問五個問題。

`work.reconcile`、`job.analyze`、`document.propose`、`public.challenge`、`quality.challenge` 是內部
`ExecutionRoute`／operation，不是另一套顧問動作。一次 `ConsultantAction` 可以經過一個或數個 bounded route，
但 UI 與評測只需理解本輪主要顧問意圖；不得讓兩套 enum 互相漂移。

第一版凍結以下互不混用的詞彙：

| 詞彙集合 | 唯一合法值 | 用途 |
|---|---|---|
| `ConsultantAction` | `broaden`、`deepen_story`、`clarify_boundary`、`validate_or_challenge`、`propose_document_change`、`review_completion` | 本輪對員工的主要顧問意圖 |
| `ReconciliationDecision` | `add`、`edit`、`merge`、`split`、`no-op`、`clarify` | Work Unit／Task 邊界分析結果 |
| `ReferenceMatch` | `match`、`partial`、`no-match`、`conflict` | 已完成判斷的公版候選比較結果 |
| `DocumentChange` | `add`、`edit`、`merge`、`split`、`delete` | AI 可以提出的 JD 變更 |
| `ProposalDecision` | `accept`、`edit`、`reject`、`defer` | 員工對 proposal 的決定 |

公版候選若資訊不足，保持未決並選 `validate_or_challenge`；不得為了 enum 完整而新增 `uncertain` 判定。

Loop 不採用：

- 無限自我反思；
- 模型自行建立任意 action；
- 固定跑完所有 operation；
- 以「模型說完成」作唯一停止條件。

### 7.5 Graph Engineering

#### 7.5.1 名詞查證

截至 2026-07-25，「Graph Engineering」仍不是主要 AI 實驗室共同制定的正式標準名稱。OpenAI 使用 agent orchestration，Anthropic 區分 workflow 與 agent，Microsoft Agent Framework 及 LangGraph 則直接提供 graph-based workflow／execution。

本文件據此把 Graph Engineering 定義為：

> 把 LLM 操作、deterministic code、retrieval、validator、human decision 與 loop，設計成具有明確節點、typed edge、共享狀態、路由、權限、失敗與停止條件的執行圖。

這是對既有 workflow orchestration、state machine、DAG 與 agent patterns 的整理，不是新模型能力，也不會取代 Prompt、Context、Harness 或 Loop Engineering。

- OpenAI 說明 orchestration 可以由 LLM 或程式控制；程式控制在速度、成本與行為上更 deterministic、predictable，兩者可混用。[OpenAI Agents SDK — Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/)
- Microsoft Agent Framework 把 workflow 定義為 executor 與 edge 構成的 directed graph。[Microsoft Agent Framework — Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows)
- LangGraph 的官方 workflow patterns 已包含 parallelization、orchestrator-worker、synthesizer、conditional edge 與 evaluator-optimizer loop。[LangGraph — Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- Anthropic 仍建議從最簡單、可組合的方案開始，只有評測證明需要時才增加 agentic complexity。[Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

#### 7.5.2 必須區分兩種 Graph

本產品同時有兩種不同的 Graph，不能混為一談。

##### A. Work Graph：系統知道什麼

它描述工作分析語意：

```text
QuestionContext + Message → Claim → Story / Work Unit → Task
Employee Supporting Artifact → informs / challenges → Claim / Task
Task → Duty / Output / Indicator / Knowledge / Skill / Attitude
Claim → supports / contradicts / supersedes → Claim or Task
Public Reference → challenges → Task / K / S
Proposal → changes → Current JD
Direct Edit → changes → Current JD
Direct Edit → reopens / challenges → Work Model
```

Work Graph 的目的：

- 保存 Story、Work Unit 與 Task 的多對多關係；
- 讓更正、反證與 supersession 不會遺失；
- 讓 Context Engine 可以找到相關原始內容；
- 支援 Task 與 O/P/K/S 的雙向修正。

這不代表需要 Graph DB。第一版使用穩定 ID 與 typed relations 即可。

##### B. Execution Graph：系統接下來做什麼

它描述顧問流程的執行路由：

Execution Graph 有四種第一版入口事件：

| 入口事件 | 第一個 deterministic 責任 |
|---|---|
| Employee Message | 建立 `QuestionContext`，再執行 `turn.understand` |
| Proposal Decision | accept／edit 時更新 Document Layer；reject／defer 時更新 decision context；最後重新計算待處理項 |
| Direct Document Edit | 更新 Current JD，標記相關 Work Model 待重整，必要時建立 open issue |
| Resume Session | 恢復最後完整回合、停止原因、建議下一動作、pending proposal 與 completion/reopen 狀態 |

```text
Employee Turn
      │
      ▼
turn.understand
      │
      ▼
Validate + Update Work Model
      │
      ▼
Route by current state
      ├─ conflict / correction ─────────→ consultation.decide: validate_or_challenge
      ├─ new or changed work boundary ─→ work.reconcile
      ├─ stable Task ──────────────────→ job.analyze
      ├─ document-ready change ────────→ document.propose
      ├─ reference phase ──────────────→ public challenge
      └─ completion candidate ─────────→ quality.challenge
                                               │
                                               ▼
                                      Guardrails / Proposal Gate
                                               │
                                               ▼
                                      Employee-facing response
                                               │
                                               ▼
                                      Persist completed turn
                                               │
                                               └── next employee turn
```

這張圖不是固定 stage machine：

- 一輪只走與目前狀態相關的分支；
- 新資訊可以讓流程回到 work reconciliation；
- O/P/K/S 可以 reopen Task；
- employee rejection／correction 可以改變下一輪路由；
- loop 存在於 Graph 裡，沒有被 Graph 取代。

#### 7.5.3 Node 不等於 Agent

Execution Graph 的 node 可以是：

| Node 類型 | 例子 |
|---|---|
| LLM operation | `turn.understand`、`work.reconcile`、`quality.challenge` |
| Deterministic code | schema validation、state update、coverage 計算、proposal authority |
| Retrieval | 公版候選檢索 |
| Human checkpoint | accept / edit / reject / defer |
| Persistence | 保存完整回合與目前 JD |
| Formatter | 產生 UI diff 或公版匯出格式 |

不得因為畫成一個方框，就自動替它建立一個 Agent。

#### 7.5.4 Resident state，ephemeral LLM operations

附圖區分 resident agent 與 ephemeral worker。對本產品更安全的對應不是建立多個 resident agents，而是：

> **Resident state + ephemeral model operations**

長期存在並可恢復的是：

- Conversation；
- Source Claims；
- Work Graph；
- Coverage／Conflict／Open Issues；
- Proposal／Employee Decision；
- Current JD；
- Current Focus。

每次 LLM operation：

1. 由 Context Policy 讀取同一份 application-owned state；
2. 組成 operation-specific context；
3. 執行一次 bounded model call；
4. 回傳 typed candidate；
5. 經程式驗證後才更新 state；
6. operation 自身不擁有私有長期真相。

這可避免 Worker、Reviewer 與 Planner 各自記住不同版本的員工工作。

LangGraph 的官方 persistence 能為 graph step 建 checkpoint，但第一版只承諾正常完整回合後恢復，不需要為每個內部 node 建 checkpoint、time travel 或 token-level durable execution。[LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

#### 7.5.5 Reviewer 與平行分支的使用邊界

附圖中的 Worker → Reviewer 1..N → Synthesize → Pass? 是 evaluator-optimizer 加 fan-out／fan-in。

它只在以下條件下可能值得採用：

- 子檢查可以真正獨立；
- 每個 Reviewer 有不同、明確、可評測的責任；
- synthesis 不會丟失關鍵反對意見；
- 有外部 evidence 或 deterministic checks，不是模型互相認同；
- 多 Reviewer 相對單 Reviewer 有事前定義的品質提升；
- latency 與成本仍可接受。

第一版可研究的候選位置：

1. 高風險 Task merge／split；
2. 最終 JD 完整性檢查；
3. 公版與員工現況發生明確 conflict。

不適合每輪啟用，因為：

- 每輪 Context 高度共享；
- 訪談動作互相依賴；
- 員工等待時間敏感；
- 多 Reviewer 不等於多個獨立真相來源。

Anthropic 在其多 Agent Research 的評測中，曾比較多個 judge 與單一 judge；該場景最後是單一 rubric judge 更一致且更接近人工判斷。這不能直接證明本產品永遠只該用一個 Reviewer，但足以否決「Reviewer 越多越可靠」的預設。[Anthropic — Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)

#### 7.5.6 第一版的實作裁決

採用：

- 明確畫出 Work Graph 與 Execution Graph；
- 以普通 application code 實作 Controller、typed action 與 route；
- deterministic node 優先；
- LLM 只放在需要語意判斷的 node；
- 每個 node 有明確 input、output、authority、error 與 stop condition；
- 正常回合完成後保存；
- Harness 記錄實際走過的 path，評估 outcome 而非要求每次走固定路徑。

不採用：

- LangGraph、Microsoft Agent Framework 等 runtime 作第一版必要 dependency；
- Graph DB；
- resident multi-agent memory；
- 每輪 Planner + Worker + N Reviewers；
- 模型動態建立無上限的新 node；
- 因為流程可以畫成 Graph，就預設需要 Graph framework。

只有當普通 Controller 已出現大量難以維護的 branch／join、長時間中斷恢復、真正可平行子流程，且 eval 證明 Graph runtime 有價值時才重新評估。

---

## 8. 一輪完整內部流程

### 8.1 正常快速路徑

```text
1. 員工送出一段話
2. Controller 依 active question 建 `QuestionContext` 與 turn-understanding context
3. turn.understand 掃描所有訊號
4. 程式驗證並更新 claims / corrections / unmapped signals
5. 更新 coverage、conflicts 與目前 focus
6. consultation.decide 選一個最高價值動作
7. 生成一個自然問題，或一個小型文件 proposal
8. Guardrails 驗證
9. 保存完整 user turn、AI turn、工作模型與 proposal
10. UI 顯示回答與 JD 目前狀態
```

一般回合目標是 2 次 LLM 呼叫：

1. 理解；
2. 決策與自然回應。

如果同一次可靠完成，可經評測後合併；不能只為少一次呼叫犧牲漏訊號率。

### 8.2 深度 reconciliation 路徑

以下訊號出現時才額外呼叫 `work.reconcile`：

- 新工作可能與既有 Task 重複；
- 一個故事包含多個結果；
- 多個故事可能屬於同一 Task；
- 員工更正責任或時間範圍；
- O/P/K/S 暗示 Task 邊界不對；
- 員工指出 AI 切太細或合太粗；
- 目前 Task 無法自然連接 Output 或 Skill。

輸出只能是：

- add candidate；
- edit；
- merge；
- split；
- no-op；
- clarify。

它不能直接更新 Current JD。

### 8.3 文件提案路徑

```text
已驗證的工作模型變化
  → document.propose
  → 產生一個可理解的 before/after
  → 說明理由與未確定處
  → 員工 accept / edit / reject / defer
  → 才更新 Current JD
```

若一次分析產生很多改動，應拆成少量可理解 proposal，而不是讓員工一次批准整份文件。

### 8.4 失敗路徑

#### Provider／網路失敗

- 不更新正式 JD；
- 不提交半套分析；
- 保留上一個完整回合；
- UI 允許重試。

#### Structured output 無法解析

- 最多執行有限的一次 repair／retry；
- 仍失敗就回報本輪未完成；
- 不進無限修復 loop。

#### 語意不確定

- 不以 retry 強迫模型猜答案；
- 保存 unknown／conflict；
- 下一步向員工澄清。

#### 員工中途離開

- 只承諾上一個完整 AI 回合可恢復；
- 不做 token-level 或回答到一半的 durable workflow。

---

## 9. Task 分析的程式化流程

### 9.1 先辨識訊號，不立即建立 Task

`turn.understand` 對每段新回答辨識：

- action；
- object；
- intended / actual outcome；
- output 或服務結果；
- indicator／品質條件；
- knowledge；
- skill；
- tool／technology；
- method／step；
- responsibility／ownership；
- handoff；
- frequency／cycle；
- current／past；
- routine／exception／one-off；
- negative／correction；
- ambiguity；
- unmapped content。

這是高召回 capture，不代表全部都會進 JD。

### 9.2 形成 Work Unit

把一個故事拆成可比較的工作片段，但不因每個動詞都建立 Work Unit。

例如：

> 我用 Python 讀取資料、清理格式，再產生每週異常報告給主管，必要時跟現場確認原因。

可能得到：

- 工具：Python；
- 方法／步驟：讀取資料、清理格式；
- 主要 Work Unit：整理與分析異常資料；
- Output：每週異常報告；
- 交接／協作：向現場確認原因；
- 接收方：主管；
- 頻率：每週。

不能得到三個獨立 Task：

- 使用 Python；
- 讀取資料；
- 清理格式。

### 9.3 跨故事比較後才穩定 Task

對候選工作比較：

- 是否相同 outcome；
- 是否相同責任；
- 是否可獨立交辦；
- 是否只是同一 Task 的不同工具／情境；
- 是否有不同決策權或風險；
- 是否在不同週期重複出現；
- 是否只是一次性協助；
- 是否有多個來源支持。

### 9.4 Task 狀態

只需要簡單狀態：

- `candidate`；
- `needs_clarification`；
- `stable_for_now`；
- `reopened`；
- `superseded`；
- `rejected`。

`stable_for_now` 不是永遠正確，O/P/K/S 或新故事仍可 reopen。

### 9.5 Duty 合成

Duty 在 Task 相對穩定後依：

- 共同目的；
- 共同責任；
- 共同 outcome；
- 工作流程位置；
- 決策與風險性質；

動態分組。

Duty 不是用公版類別先建立盒子，再把 Task 塞進去。

---

## 10. O/P/K/S 分析流程

### 10.1 分析順序

O/P/K/S 分別分析，但在同一 Task context 中互相校正：

```text
Task
  ├─ Output：完成後留下什麼產品、服務、狀態改變或決策結果？
  ├─ Indicator：如何觀察是否做得符合要求？
  ├─ Knowledge：要知道什麼，才理解並判斷這項工作？
  └─ Skill：要能做什麼，才可穩定完成這項工作？
```

不是一次 prompt 要模型把四格全部補滿。

### 10.2 Output

可包含：

- 文件或資料；
- 服務結果；
- 決策；
- 狀態改變；
- 監控、預防或維持結果；
- 經確認無須行動的判斷結果。

沒有實體產物不代表沒有 Output。若確實不適用，可以空白或 not applicable，不能硬造文件名稱。

### 10.3 Indicator

優先找可觀察的：

- 正確性；
- 完整性；
- 時效；
- 合規；
- 可追溯；
- 風險控制；
- 服務回應；
- 交接品質；
- 例外處理結果。

沒有來源時不得生成百分比、時間、數量等數字門檻。AI 可以提問「是否有明確時限」，不能自行填「24 小時內」。

### 10.4 Knowledge

Knowledge 是理解、判斷與解釋工作所需的知識，例如：

- 規範；
- 流程；
- 產品或業務知識；
- 風險原理；
- 資料定義；
- 專業概念。

工具名稱不自動等於 Knowledge。

### 10.5 Skill

Skill 是可執行的能力，例如：

- 分析異常原因；
- 驗證資料品質；
- 協調跨部門處理；
- 撰寫可供決策的報告；
- 操作特定工具完成工作。

「Python」本身不是 Skill；「使用 Python 清理與驗證大量資料」才可能是 Skill，而且仍須連回 Task。

### 10.6 反向修正

若分析 O/P/K/S 時發現：

- 一個 Task 有兩個完全不同 outcome；
- 所需 Skill 對應不同責任；
- Indicator 無法共同描述；
- Knowledge 只支持其中一部分；

系統要提出 reopen / split / merge / clarify，而不是硬把欄位填完。

### 10.7 Attitude 邊界

公版職能基準可能需要態度（A），但它不能由模型根據員工的文字風格或聊天禮貌程度推斷。

第一版規則：

- Attitude 與 K/S 分開保存；
- 優先描述與工作有關、可被行為觀察的傾向；
- 必須有明確工作故事、反覆行為，或經員工確認的公版候選；
- 「個性很好」「很有責任感」等空泛人格標籤不得直接寫入；
- 無足夠支持時保留 unknown，不為公版欄位完整而補寫；
- Attitude 可連到相關 Duty／Task，但不強迫每個 Task 都有一項。

---

## 11. 顧問動作選擇策略

`consultation.decide` 不需要建立一份長期固定 plan。它每輪根據最新狀態選一個局部動作。

### 11.1 輸入

- coverage 缺口；
- unresolved conflicts；
- unmapped signals；
- Task candidate 支持程度；
- 最近問過的問題；
- 員工是否反覆修改同一內容；
- 目前 JD 缺口；
- 當前 focus；
- 員工負擔與對話節奏。

### 11.2 優先順序

一般建議：

1. 修正明確矛盾或責任錯誤；
2. 接住新出現但尚未理解的工作；
3. 釐清可能造成 Task merge/split 的邊界；
4. 補高影響 coverage 缺口；
5. 深挖代表性故事；
6. 補 O/P/K/S；
7. 提出小型文件修改；
8. 進行公版 challenge；
9. 進行完成檢查。

這不是硬編碼順序。模型可以選擇不同動作，但必須說得出與目前狀態一致的理由。

### 11.3 問題規則

每輪原則上只問一個主要問題：

- 短；
- 自然；
- 可直接回答；
- 不預設答案；
- 不把公版內容包裝成事實；
- 優先取得具體例子；
- 需要時接受短答；
- 不重問已回答或已拒絕問題；
- 不為了 coverage 分數追問低價值細節。

---

## 12. 公版資料的使用流程

### 12.1 Blind-first 階段

禁止把公版 Task、K、S 當作使用者 context。可以用一般顧問方法提問，但不能讓職業模板主導理解。

### 12.2 初步工作模型形成後

依目前：

- role hypothesis；
- Task；
- outcome；
- tool／domain terms；
- industry clues；

檢索少量相關公版項目。

### 12.3 比對結果

每個候選只能標為：

- `match`；
- `partial`；
- `no-match`；
- `conflict`。

### 12.4 對話動作

- match：詢問是否確實適用，或用來補細節；
- partial：指出差異，建立客製內容；
- no-match：保留員工自有內容；
- conflict：優先相信員工現況，但請他確認。

資訊不足以分類時，候選保持未決並追問，不建立第五種 match 狀態。

### 12.5 文件來源

第一版只需在採用公版候選時保存一個簡單 reference ID。無須建立複雜 provenance UI 或企業級 lineage 系統。

---

## 13. 完成與最終反方檢查

### 13.1 完成不是欄位全滿

系統可建議完成，但不只看：

- Task 數量；
- O/P/K/S 是否每格都有值；
- 公版是否完全匹配。

建議完成前必須同時成立：

- 角色 purpose 與主要責任可以解釋；
- 適用的日／週／月／季／年工作週期、例外與低頻高影響責任已做合理盤點；
- 關鍵 Task 邊界已達 `stable_for_now`；
- 關鍵 Task 的適用 O/P/K/S 已達到可供 JD 使用的程度；
- 無會顯著改變文件的重大矛盾；
- `quality.challenge` 沒有 blocker；
- 員工審閱並選擇完成。

「關鍵 O/P/K/S 可用」不代表每項 Task 四格全滿。自然不適用的 Output 可以省略，非關鍵欄位可以 unknown；
只有會使主要工作無法理解、查核或使用的缺口才阻擋完成。

### 13.2 `quality.challenge` 檢查

至少主動尋找：

- 被遺漏的日常工作；
- 被精彩故事掩蓋的例行工作；
- 低頻高影響責任；
- 過去、他人或一次性工作誤收；
- 工具或步驟誤升格；
- Task 過度拆分；
- 不同 outcome 過度合併；
- Duty 分組不合理；
- 無來源的 Output、Indicator、K、S；
- 從對話語氣推斷的 Attitude；
- 虛構數字門檻；
- correction 未生效；
- 公版錨定；
- accepted proposal 與後續證據衝突；
- 尚未處理的 unmapped signals。

### 13.3 Blocker 與 warning

#### Blocker

- 重大責任歸屬矛盾；
- 主要 Task 邊界仍不清楚；
- 正式 JD 含已知錯誤或被否定內容；
- 未經員工決定的 AI 內容進入正式文件；
- unsupported numerical standard；
- 關鍵工作週期完全未盤點；
- 關鍵 Task 的適用 O/P/K/S 尚不足以形成可用 JD。

#### Warning

- 某些 Task 支持較少；
- 非關鍵 K/S 或選填內容尚未完整；
- 公版比對未做；
- 非關鍵欄位 unknown；
- 員工選擇暫時跳過。

員工可以在沒有 blocker、仍有 warning 的情況完成目前版本。

---

## 14. 最小品質 Harness

### 14.1 第一批能力案例

沿用顧問流程文件定義的 16 類案例：

1. 工具不是 Task；
2. 工具操作本身確實是 Task；
3. 一個故事包含多個工作；
4. 多個故事共同支持一個 Task；
5. 共享 outcome 不應過度拆分；
6. 不同 outcome 不應過度合併；
7. 一次性工作；
8. 過去工作；
9. 他人工作／交接；
10. 使用者更正舊說法；
11. 服務或監控工作無實體產出；
12. 沒有來源的數字門檻；
13. 公版候選不適用；
14. 公版沒有但員工確實負責；
15. 精彩故事掩蓋例行工作；
16. 離開後恢復不遺失狀態。

### 14.2 必測指標

- false Task promotion；
- missed Task；
- over-split / over-merge；
- responsibility attribution；
- correction retention；
- unsupported O/P/K/S；
- unsupported numeric threshold；
- source support correctness；
- proposal integrity；
- resume fidelity；
- 重複問題率；
- 員工修改負擔；
- latency / cost；
- 同案例多 trial 的變異。

### 14.3 Gate

第一版進入 UI 垂直整合前，至少必須：

- 工具、過去、他人、一次性四類不得出現嚴重誤收；
- correction 不得復活舊內容；
- AI 不得直接改 Current JD；
- 一故事多 Task與多故事一 Task皆有可接受表現；
- 無來源數字不得進正式 Indicator；
- resume 不得重問或忘記 accepted/rejected proposal；
- 人工閱讀 transcript 後，問題路徑仍像顧問而非問卷。

不要求一開始達成 100% coverage，也不為每個小欄位建立大量單元測試。

---

## 15. 第一版建置順序

### Phase 1：Task 分析實驗核心

先做：

- Source Claim；
- Unmapped Signal；
- Story / Work Unit；
- Task Candidate / Task；
- `turn.understand`；
- `work.reconcile`；
- `consultation.decide`；
- 6–8 個最關鍵 capability cases。

輸入先用固定 transcript 或簡單 CLI，不接正式 Web。

成功條件：

- 不把 Java、Python、HTML 等工具直接變 Task；
- 能從一段故事找出多個工作；
- 能把跨故事相同工作合併；
- 能處理 current／past／other／one-off；
- 能提出自然的下一問。

### Phase 2：最小可對話與恢復

加入：

- completed turns；
- consultation state；
- coverage / conflict；
- 本機保存與重開；
- 一輪快速路徑；
- 簡單本機 UI 或開發介面。

### Phase 3：O/P/K/S 與 Proposal

加入：

- `job.analyze`；
- Task linkage；
- Task reopen；
- 有明確行為支持時的 Attitude 候選；
- `document.propose`；
- accept / edit / reject / defer；
- Current JD。

### Phase 4：公版 challenger

加入：

- hybrid retrieval；
- match / partial / no-match / conflict；
- 簡單 reference ID；
- 公版格式輸出映射。

### Phase 5：完成檢查與成品 UI

加入：

- `quality.challenge`；
- blocker / warning；
- 完整本機 Web 訪談與 JD 共編；
- 保存多份本機 JD；
- 匯出。

此順序刻意先證明「工作分析是否正確」，再投入完整 Web 與資料設計，避免重演先做完 App 才發現 LLM 分析方向錯誤。

---

## 16. 明確不做

第一版不做：

- SaaS；
- 帳號、密碼、登入；
- organization / tenant / member / ACL；
- 計費；
- 遠端雲端部署；
- 多人共編；
- 主管與 HR workflow；
- Graph DB；
- 通用 multi-agent framework；
- planner/executor 平台；
- 任意動態 agent spawning；
- Event Sourcing；
- token-level workflow recovery；
- 複雜 provenance UI；
- 全面 hash / audit platform；
- 自動 provider routing；
- semantic cache 自動重用顧問結論；
- fine-tuning；
- 企業級資料治理平台。

### 16.1 Cache 邊界

可使用：

- provider prompt cache；
- deterministic reference retrieval cache；
- 不影響語意的靜態資料 cache。

第一版不要使用：

- 以語意相似問題直接重用上一個員工的分析結果；
- 把舊模型結論當記憶；
- 跳過 correction／context 重建的結果 cache。

Cache 是成本優化，不是顧問記憶。

---

## 17. 未來升級觸發條件

只有出現可觀察需求時才升級。

### 17.1 引入更複雜 workflow／graph

必須同時看到：

- 真實流程有多個長時間等待節點；
- 有可平行且獨立驗證的子任務；
- 線性 controller 已難以維護；
- 評測證明 graph orchestration 改善品質或可靠性。

### 17.2 引入多 Agent

必須證明：

- 某 operation 可被明確分解；
- 子任務具獨立 context 與驗收；
- 相對單一 operation 有顯著品質提升；
- 沒有增加 critical error、成本與延遲到不可接受。

### 17.3 引入 fine-tuning

先累積：

- 穩定 task 定義；
- 足夠高品質標註案例；
- 可重現 eval；
- prompt/context 優化已到平台期。

OpenAI 的模型優化指南也把 eval、prompt 與 fine-tuning 視為迭代流程，而不是一開始就訓練模型。[OpenAI — Model optimization](https://developers.openai.com/api/docs/guides/model-optimization)

### 17.4 引入多來源組織級驗證

只有當產品目標從「員工共編 JD」變為「組織正式職務標準」時，才加入：

- 主管；
- 同職位 SME；
- HR；
- 文件；
- 觀察；
- 多人裁決。

這是產品範圍改變，不是第一版預先埋好 SaaS 欄位。

---

## 18. 顧問流程到架構的追蹤矩陣

| 顧問流程責任 | 主要架構責任 | 核心防錯 |
|---|---|---|
| 開啟、恢復與重新開啟 | Conversation + Consultation State + Resume entry | 保存停止原因、建議下一動作與完成狀態 |
| Blind-first 角色定位 | Role Hypothesis + Context Policy | 早期禁止公版錨定 |
| 工作週期廣度盤點 | Coverage + consultation.decide | 不讓精彩故事代表全部工作 |
| 每輪全域理解 | turn.understand + Unmapped Signal | 新訊號不因目前焦點而消失 |
| 問題與短回答共同理解 | QuestionContext + turn.understand | 短答不脫離提問目的，也不補出未說內容 |
| 員工提供的工作材料 | Source Layer + Context Policy | 文件只協助回憶與交叉檢查，不自動成為現況真相 |
| 故事深挖 | Story / Work Unit | 故事不直接等於 Task |
| Task 邊界 | work.reconcile + Task rubric | 工具、步驟、他人、過去、一次性不誤收 |
| 跨故事整併 | many-to-many relations | 避免重複與錯誤 merge/split |
| Duty 整併 | Task grouping | 不用公版盒子預先固定 |
| O/P/K/S | job.analyze + Task linkage | 不填空、不虛構、可 reopen Task |
| Attitude | explicit behavior + employee confirmation | 不從語氣或人格印象推斷 |
| 公版 challenge | Reference Challenger | reference 不自動升格為事實 |
| 文件共編 | Proposal Boundary | AI 不直接改正式 JD |
| 員工直接編輯 | Document Layer + reconciliation route | 文件立即更新，但不偽造來源並重整受影響分析 |
| 更正與否定 | Claim supersession + Context Policy | 舊錯誤不復活 |
| 恢復 | Consultation State | 回到相同對話、焦點、提案與 JD |
| 最終反方檢查 | quality.challenge | 找漏項、錯誤責任與 unsupported claims |
| 完成 | blocker/warning + employee decision | 欄位全滿不等於正確 |
| 品質改進 | Quality Harness | 以能力案例而非感覺選 prompt／模型 |

---

## 19. 架構驗證與否決條件

### 19.1 推薦架構仍應被否決的情況

如果實驗顯示以下任一項長期無法修正，應重新審視架構：

- Work Model 讓新型態工作大量掉入 unknown 且無法恢復；
- `turn.understand` 漏掉跨焦點訊號；
- reconciliation 比單一 prompt 更常錯誤 merge/split；
- context packet 使 correction 復活；
- 兩次以上 LLM 呼叫造成明顯錯誤累積；
- proposal gate 讓員工操作負擔過高；
- 固定 action set 使對話變成問卷；
- Task quality 沒有優於簡單單 Agent baseline；
- 成本或 latency 讓本機 Web 互動不可接受。

### 19.2 比較基準

Task 實驗時保留一個簡單單 Agent baseline，在相同：

- 模型；
- transcript；
- token 預算；
- capability cases；
- trial 數；

下比較。

推薦架構只有在以下至少一項實質改善、且沒有 critical regression 時才值得保留：

- Task precision／recall；
- correction reliability；
- merge/split correctness；
- proposal integrity；
- resume fidelity；
- 可診斷性；
- 員工修改負擔。

不能因為架構看起來專業就假設它比較好。

---

## 20. 最終決策

### 20.1 通過

- 採受約束的自適應顧問核心；
- 程式擁有狀態、合法動作、文件與保存；
- LLM 擁有自然語言理解、專業比較、追問與提案；
- 員工擁有正式文件決定權；
- 使用 open-world、claim-centric work model；
- 明確區分 Source Layer、Work Model 與 Document Layer；
- 每輪高召回理解新回答，再選一個焦點；
- 短回答使用 `QuestionContext`，故事深挖使用 bounded `StoryFocus`；
- Story / Work Unit / Task 多對多；
- O/P/K/S 可反向修正 Task；
- 公版後段 challenge；
- Context 依 operation 組裝；
- Structured Output 只保證形狀；
- Harness 與 runtime 分離；
- 第一版單模型、薄 adapter、有限呼叫；
- 明確區分 Work Graph（知道什麼）與 Execution Graph（接下來做什麼）；
- Execution Graph 先用普通 application code 實作；
- resident state、ephemeral LLM operations；
- 顧問動作使用單一 canonical vocabulary，內部 operation 只作 ExecutionRoute；
- 多 Reviewer 只在高風險節點經 eval 證明有效後採用；
- 先測 Task 分析，再做完整 Web。

### 20.2 否決

- 單一大 Agent 直接改 JD；
- 固定 Task→O→P→K→S 單向流水線；
- Planner／多 Agent 作第一版預設；
- 每輪塞完整 transcript 與公版；
- 欄位填滿即完成；
- evidence 有引用即視為真；
- employee accept 即視為外部驗證；
- provider-neutral 即假設品質等價；
- 先做 Graph DB、Graph runtime、每輪多 Agent、SaaS 或完整平台。

### 20.3 下一個實際工作

下一步不是建完整 Web，也不是先決定所有資料表，而是寫一份小型「Task 分析實驗規格」：

1. 固定 `turn.understand`、`work.reconcile`、`consultation.decide` 的最小輸入輸出；
2. 準備 6–8 個高風險案例；
3. 用一個固定便宜模型跑 2–3 trials；
4. 與簡單單 Agent baseline 比較；
5. 人工閱讀 transcript；
6. 先證明工具、故事、責任與 Task 邊界分析方向正確。

若這一步失敗，應修改 work model、context 或 operation 分工；不要先重構 App。

---

## 21. 權威來源

### 專業工作分析

- [U.S. Office of Personnel Management — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)
- [O*NET — Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf)
- [O*NET — Content Model](https://www.onetcenter.org/content.html)
- [勞動力發展署 iCAP — 行為事例訪談法](https://icap.wda.gov.tw/File/Knowledge/Method/2-04.pdf)
- [ESCO — Structure and downloadable datasets](https://esco.ec.europa.eu/en/structure-esco-downloadable-datasets)

### LLM 架構、Context 與 Agent

- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)
- [OpenAI — Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering)
- [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI — Compaction](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI — Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

### Graph orchestration 與 multi-agent

- [OpenAI Agents SDK — Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/)
- [Microsoft Agent Framework — Workflow Builder & Execution](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows)
- [LangGraph — Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)

### 檢索、評測與可觀測性

- [Microsoft — Hybrid search in Azure AI Search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview)
- [Anthropic — Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [OpenAI — Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- [Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [NIST — AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
- [Microsoft — Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/)
- [Google PAIR — Feedback and controls](https://pair.withgoogle.com/guidebook-v2/chapter/feedback-controls/)
- [OpenTelemetry — What is OpenTelemetry?](https://opentelemetry.io/docs/what-is-opentelemetry/)

---

## 22. 文件維護規則

本文件是「顧問流程如何落成 LLM 程式架構」的研究決策基線。

後續若要改變以下任一項，應先回到本文件重新做反方審查：

- AI 是否能直接修改正式 JD；
- 是否改成固定階段；
- 是否提前使用公版；
- 是否取消 raw source／unmapped signals；
- 是否改成多 Agent；
- 是否把 Task 與 Story 設計成一對一；
- 是否取消 O/P/K/S 對 Task 的反向修正；
- 是否用欄位完整率取代完成反方檢查；
- 是否加入 SaaS、多人或組織級驗證。

細部資料庫表、API 與 UI 可以在後續實作計畫中決定，但不得破壞本文件的顧問流程不變量。
