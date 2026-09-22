# Interview AI vNext：LLM 架構反方審查與工作分析核心修正版

- 日期：2026-07-24
- 狀態：architecture red-team review；尚未授權 production 實作
- 產品範圍：本機 Web、單一員工、單一使用者操作、可保存多份 JD
- 核心目標：透過專業訪談，逐步形成高品質、客製化且由員工審核的職務說明書
- 不包含：SaaS、帳號、密碼、多租戶、多人協作、公司職能庫、Graph DB、multi-agent framework
- 上游文件：
  - [Evidence-first Stateful Interview Architecture](2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md)
  - [專業職務分析與短回答架構研究](2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)
  - [下一題選擇與 Context Loop 研究](2026-07-23-interview-vnext-question-selection-context-loop-research.md)
  - [Job Authoring v2 關聯式儲存研究](2026-07-24-job-authoring-v2-relational-storage-research.md)

## 1. 結論先行

### 1.1 最強反方結論

如果刻意站在反方，現行 vNext 可以被描述成：

> 一套可稽核、可重播、provider-neutral、schema 嚴格的「對話事實處理器」，外面再接一個固定缺口問答器；它尚未真正實作專業工作分析。它可能非常一致、非常可追溯地產出錯誤的 Task。

這個批評成立的原因不是模型不夠強，而是目前 semantic middle 缺了三個必要能力：

1. **工作廣度盤點**：知道這份職位有哪些責任範圍，而不是完成一個 episode 就往下一題；
2. **故事內工作邊界分析**：辨識一個故事中的 Task、子步驟、方法、工具、產出與交接；
3. **跨故事全域整併**：在建立正式 Task 前比較既有 JD 與所有相關故事，做合併、拆分、去重與修正。

若直接依舊規格實作 `episode.code -> add_task proposal`，很可能重演上一版：

- 「用 Java 寫程式」成為 Task；
- 「用 Python 整理資料」再成為另一個 Task；
- 同一個結果的五個操作步驟被拆成五項工作；
- 同一項工作在不同故事被重複加入；
- 一個故事中的五項獨立工作被壓成一條超長 Task。

### 1.2 不是全部推翻

目前基礎架構中，下列方向仍正確，無須重做：

- `QuestionFrame -> turn.interpret -> Evidence` 的短回答 grounding；
- transcript、Evidence 與正式 JD 分開；
- Structured Output 後仍做 application semantic validation；
- LLM 只能提出 proposal，員工接受／修改／拒絕後才寫正式 JD；
- provider adapter、domain reducer、業務狀態與模型 context 分離；
- Context Engine 每個 operation 只選相關資訊；
- 以 deterministic workflow 控制已知流程，不導入 multi-agent 或 graph framework；
- Task、Output、Indicator、Knowledge、Skill 分離；
- 公版只做候選與 coverage check，不替員工事實背書。

所以正確裁決不是「整套砍掉」，而是：

> **保留可靠底座，凍結非核心基礎工程；重做 Evidence 與正式 JD 中間的工作分析層。**

### 1.3 目前不得直接實作的舊假設

在本審查完成 owner 討論前，不應直接照舊設計實作：

- 僅使用 episode 原子 Evidence、完全不讀 bounded story transcript 的 `episode.code`；
- 一個 episode 預設對應一個 Task；
- episode 有任何 Output，就視為其中所有 Action 已有 Output；
- 固定每個 episode 最多兩題後即可 close；
- 只要 JD 已有一個 Task，就允許 offer finish；
- 每個 episode close 直接建立 `add_task` proposal；
- 工具／方法／步驟只靠 prompt 提醒模型不要升格，沒有 Task boundary gate；
- 在沒有 Task boundary quality suite 前先擴建完整 O/P/K/S production flow。

## 2. 本次審查方法

本審查同時檢查三類證據：

1. **現有程式與 contracts**：確認系統實際能做什麼，不只看研究文件；
2. **專業工作分析方法**：iCAP、O*NET、OPM 等官方來源；
3. **2026 LLM 工程方法**：OpenAI、Anthropic 的 workflow、context 與 eval 官方資料。

採用的判斷標準不是「架構看起來先進」，而是：

- 是否提高最終 Task 邊界正確率；
- 是否避免工具、技術和子步驟膨脹成 Task；
- 是否能處理一個故事含多項工作；
- 是否能把多個故事合併為同一項工作；
- 是否能控制訪談長度；
- 是否能被實際員工理解與修正；
- 是否能用小型、具代表性的 eval 證明品質提升。

## 3. 現行架構攤開

### 3.1 已完成的 Conversation Core

目前已實作的主線是：

```text
employee turn
  -> turn.interpret/2.0.0
  -> literal observations / contextual answer bindings
  -> verifier
  -> Evidence + interpretation receipt
  -> deterministic Agenda
  -> bounded question.select Context
  -> question.select/1.0.0
  -> semantic verifier
  -> consultant question + QuestionFrame
```

它擅長處理：

- 「是／不是／每天／給財務」等短回答；
- 明示否定；
- 過去、未來、假設與其他角色；
- 更正舊 Evidence；
- 工具名稱只保存為 `tool` Evidence；
- 不讓 reference、provider 或自由文字直接修改 domain state。

### 3.2 現行 Episode 與 Agenda

目前一次只能有一個 active episode。每筆新 Evidence 直接掛到該 active episode：

- `application/turn_interpret.py` 約第 862 行；
- `episode_id = context.active_episode.episode_id`。

目前 Agenda：

- 找不到 Action，就問工作中做了什麼；
- 找到 Action、沒有任何 Output，就問產出；
- 找到 Action、沒有任何 Purpose，就問目的；
- 每個 episode 固定最多兩個 high-value questions；
- 沒有 active episode 時可 broaden coverage；
- 只要 `job_digest.tasks` 非空，就允許 offer finish。

對應程式：

- `application/agenda.py`；
- `MAX_HIGH_VALUE_QUESTIONS_PER_EPISODE = 2`；
- `allow_offer_finish = bool(job_digest.tasks)`。

### 3.3 已有但尚未形成產品能力的 Episode Context

`ContextBuilder.build_episode_code()` 已有 context packet 骨架，但沒有完整
`episode.code` operation、prompt、output contract、provider execution 與產品 proposal 主線。

目前該 packet 的重要特性：

- 只帶 episode 內原子 Evidence；
- 明確排除 transcript text；
- positive evidence 只接受 `time_scope == current`；
- `time_scope == unknown` 會被放進 excluded/negative；
- 可帶現有 candidate 與 reference snippets；
- 沒有故事段落、事件順序、工作單元或 Task boundary decision。

### 3.4 現行 Authoring Core

已實作 Authoring Core 仍是上一階段的最小垂直切片：

- `JobDocumentDraft.v1`；
- Task + nested Outputs；
- revision snapshot；
- `add_task` proposal；
- employee accept/edit/reject；
- `JobStateDigest.v1` 只投影 Task 與 Output。

2026-07-24 新核准的 current relational T/O/P/K/S/A 設計仍是研究規格，尚未成為 production authority。

因此目前「訪談 -> 正確 Task -> 正式 JD」尚未打通。

### 3.5 現行 eval 實際證明了什麼

目前 12-case `turn.interpret` suite 證明：

- 原話 span、kind 與 qualifiers；
- 短回答 binding；
- 更正、否定、其他角色與注入處理；
- SAP／Excel 不會在 `turn.interpret` 當場升格為 Skill。

它沒有證明：

- 一個故事應拆成幾個 Task；
- 一串步驟是否屬於同一個 Task；
- 工具／方法是否被後續 `episode.code` 升格成 Task；
- 跨故事去重；
- Task 是否覆蓋整份職位；
- 最終 JD 是否對員工有用；
- 訪談是否在合理時間完成。

`question.select` 現有 focused tests 同樣主要證明 ordinal、QuestionFrame、持久化與 action/output/purpose 的窄路徑，
不是專業顧問品質。

## 4. 官方方法對架構的要求

### 4.1 故事是深度工具，不是完整工作清單

iCAP 的 BEI 方法要求受訪者描述真實事件，使用 STAR 追問 Situation、Task、Action、Result，並遵循時間順序、
一次聚焦一個情況。完成後還需要整理所有事件，再做歸納與編碼分析。

同一份方法也明確指出：

- BEI 可以與調查或集會等方法搭配；
- 它需要大量陳述與高強度追問；
- 單靠少量故事建立職位全部內容，成本高且容易不完整。

來源：

- [iCAP 行為事例訪談法](https://icap.wda.gov.tw/File/Knowledge/Method/2-04.pdf)

因此本產品不能把「故事優先」誤寫成「只問故事」。正確方法是：

```text
工作廣度盤點
  -> 挑高價值事件深挖
  -> 跨事件歸納與編碼
  -> 回到完整性檢查
```

### 4.2 Task 是有意義結果的活動單位

O*NET Task Writing Guidelines 將 Task 視為具有 meaningful outcome 的最小活動單位，推薦結構：

```text
Action
  + Object
  + optional Purpose / Result / Enabler / Context
```

其中：

- Java、Python、SAP、Excel 等通常屬於 enabler/tool；
- 方法、資訊來源與設備也屬於 enabler；
- 複雜且包含多組 action/purpose 的句子應考慮拆分；
- 但不是每一個動詞都要拆成 Task，仍需判斷是否共享同一 meaningful outcome。

來源：

- [O*NET Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf)

### 4.3 專業分析不是單一資料來源

O*NET 目前使用 incumbents、occupational experts、analyst ratings、job postings、政府資料、NLP、AI/SME
等多種來源維護職業資料；OPM 也把 job analysis 定義為系統性蒐集、記錄與分析工作內容、情境、要求及
Task–competency linkage。

來源：

- [O*NET Data Collection Overview](https://www.onetcenter.org/dataCollection.html)
- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)

本產品只分析一名員工的客製職位，不需要複製多 SME 統計流程，但至少應模擬其方法分層：

- 員工提供這份職位的事實；
- AI 負責結構化與提出分析假設；
- 公版負責 coverage 與措辭參考；
- 員工負責最後採用；
- 系統明確承認這不是產業代表性驗證。

### 4.4 2026 LLM 工程支持簡單 workflow，但不支持錯誤分解

Anthropic 建議先使用簡單、可組合 workflow，只有需要時才增加 agentic complexity；context engineering
則是在每次 inference 前策展最有用的 token，而不是無條件塞滿 context。

OpenAI 的最新 eval 指引則強調：

- eval 必須 task-specific；
- workflow 中每個非確定節點需要評估；
- model output 變成 agent/tool 選擇後，新增的 nondeterminism 也要測；
- multi-agent 必須由 eval 證明有需要；
- schema adherence 不等於功能正確。

來源：

- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [OpenAI — Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- [OpenAI — Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

所以現行「deterministic workflow + bounded semantic operations」方向正確；錯的是工作分析的分解單位與成功指標
尚未對準產品。

## 5. Make the strongest case that the current design was wrong

本節刻意不替現行架構辯護，提出最強反方論證。

### 5.1 系統優化的是可稽核性，不是職務分析品質

現行程式約略包含：

- application：近萬行；
- domain：五千餘行；
- LLM contracts/context：四千餘行；
- observability：約一千四百行；
- provider：約三千行；
- Authoring Core：約三千行。

這些工程大多保護：

- ID、hash、schema、event、manifest；
- stale state；
- provider route；
- retry authority；
- persistence closure。

它們有價值，但不能回答最重要的問題：

> 「員工說用 Java、Python、HTML 完成一個系統功能，最後應該是幾項 Task？」

如果沒有這項能力，再完整的 Capture 只能幫助我們重播錯誤。

### 5.2 Episode 同時被當故事容器和工作容器

故事、事件、工作單元與 Task 是不同物件：

```text
Story / narrative：員工的一段敘述
Event：一次具體發生的工作事件
Work unit：分析中的候選活動單元
Task：跨事件整理後的穩定責任
```

現行 Episode 只有一個 `target` 和一組 Evidence IDs。當員工一段回答包含五項工作，五項工作的 Evidence
全部掛到同一 episode。

後果：

- episode 裡只要有一筆 Output，Agenda 就不再問其他 Action 的 Output；
- episode 裡只要有一筆 Purpose，Agenda 就視為整個 episode 已有 Purpose；
- 後續 coder 無法知道哪個 Purpose、Output、Tool 屬於哪個 Action；
- 一個 episode close 無法表示「故事已談完，但其中三個工作仍需分別分析」。

這是現行設計最直接的 semantic bug。

### 5.3 原子 Evidence 會把故事變成失去關係的 fact bag

Evidence 原子化是 grounding 的好做法，但不是完整工作分析表示法。

例如：

> 客戶提出需求後，我先確認規格，用 Java 寫 API，再用 Python 整理資料，完成後交給前端串接並抽查結果。

原子 Evidence 可能是：

- 確認規格；
- 使用 Java；
- 寫 API；
- 使用 Python；
- 整理資料；
- 交給前端；
- 抽查結果。

若只保留這些 claims，會遺失：

- 時間順序；
- Java 與 API 的關係；
- Python 是同一工作步驟還是另一個獨立工作；
- 交給前端是 Output recipient、handoff 還是另一個 Task；
- 抽查是同一 Task 的品質步驟還是獨立 QA 責任；
- 所有行動是否共享同一最終結果。

因此 Evidence 是必要輸入，但不足以單獨決定 Task。

### 5.4 Context minimization 被做成 context starvation

目前 `episode.code` ContextBuilder 明確排除 transcript：

```text
turn_text_not_allowed_for_episode_code
```

這能防止整場 transcript 污染分析，卻也移除了判斷故事邊界最需要的資訊：句子順序、指代、因果、轉折與交接。

正確的 context engineering 不是「越少越好」，而是：

> **完成這個 operation 所需的最小充分 context。**

對短回答解讀，QuestionFrame + current turn 足夠；對故事切分，只有原子 Evidence 不足。`work.map` 至少需要：

- bounded story transcript slice；
- 對應 Evidence；
- 目前工作地圖；
- Current Job Canvas 摘要；
- 明確 authority rules。

它仍不需要完整 transcript 或整份公版。

### 5.5 `time_scope == current` gate 會排除正常回答

`turn.interpret` 正確地規定：員工沒有明說「目前／現在」時，不把 literal Evidence 偷改成 current。

但 `build_episode_code()` 又只把 `time_scope == current` 視為 positive Evidence，把 unknown 放到 excluded/negative。

自然訪談中員工通常回答：

- 「我會核對異常資料。」
- 「平常用 Java 寫 API。」
- 「月底會整理報表。」

其中「平常」在現行 policy 只表示 typicality，不表示 current。若沒有 QuestionFrame 的 contextual scope，
大量真實現職內容會以 unknown 進入 Evidence，再被 episode coder 排除。

這是兩個各自合理規則組合後形成的系統錯誤。

修正不應是把所有 unknown 強改 current，而應建立 eligibility 規則：

```text
explicit current
  -> eligible

explicit past / future / hypothetical
  -> excluded

literal unknown + current-role QuestionFrame / interview scope
  -> contextually eligible，保留 literal qualifier 為 unknown

literal unknown + 無上下文
  -> unresolved，不自動 materialize
```

### 5.6 Agenda 是窄欄位檢查，不是真正的採訪計畫

現行 Agenda 只主動合成：

- Action；
- Output；
- Purpose。

而專業工作分析至少還需要在整體層次判斷：

- 典型日／週／月工作範圍；
- 低頻但高重要性的工作；
- ownership；
- 交接與協作；
- 例外與重工；
- 什麼才算完成得好；
- 是否仍有重要責任領域未談。

固定每個 episode 最多兩題可避免訪談過長，但也可能在一個多工作故事剛開始時提前 close。

更嚴重的是：`allow_offer_finish = bool(job_digest.tasks)` 代表只要文件已有一項 Task，就可能提出結束，而不是依
role coverage 判斷完整性。

### 5.7 `add_task` 是危險的第一個文件 operation

現行 Authoring proposal 只有 `add_task`。如果先做 `episode.code -> add_task`，而
`job.consolidate` 延後，就會讓每個新故事傾向新增 Task。

這正是 Task 膨脹的結構性來源。

第一個 production Task operation 必須同時看到：

- 目前 JD 的所有 Task；
- 相關 work units；
- 過去已拒絕／已合併的候選；
- evidence linkage。

輸出至少要能表達：

```text
no_change
add_task
edit_existing_task
merge_into_existing_task
split_candidate
needs_clarification
```

第一版不一定要把每個 action 都立即 materialize，但不能只允許 add。

### 5.8 Prompt 規則不能單獨防止工具升格

`turn.interpret` 已正確規定工具只形成 `tool` Evidence，但後續 Task coder 如果看到：

- tool：Java；
- action：寫程式；
- output：API；

仍可能產生「使用 Java 撰寫程式」。

因此需要 deterministic／rubric-based Task boundary gate：

- 只有工具名稱：不是 Task；
- 只有「使用某工具」：不是 Task；
- 只有操作步驟：不是 Task；
- 必須有 meaningful outcome 或可獨立負責的工作結果；
- 必須是 recurring/current role responsibility；
- 必須與 Current Job Canvas 做 duplicate/overlap 檢查。

### 5.9 局部 commit 會造成全域工作模型錯誤

Task 邊界通常是跨故事比較後才清楚：

- 第一個故事看似兩項工作；
- 第二個故事顯示它們其實是同一責任的不同情境；
- 第三個故事顯示其中一步是另一團隊負責。

若每個 episode close 就立即把 Task proposal 當成接近正式答案，會：

- 提前錨定員工；
- 讓員工為了省事接受過度切碎的 Task；
- 後續需要大量 merge/edit proposal；
- 讓文件在訪談中頻繁跳動。

AI 可以漸進顯示 working hypothesis，但正式 Task proposal 應在 work unit 達到穩定或全域整併後出現。

### 5.10 Harness 很完整，但 quality objective 放錯位置

OpenAI 與 Anthropic 都強調 eval 要反映實際任務與最終 environment outcome。

目前大部分 gate 測：

- 是否成功 commit；
- ID/hash 是否一致；
- schema 是否通過；
- route 是否乾淨；
- bundle 是否可重播。

它們是 regression/safety suite，不是 job-analysis capability suite。

如果沒有 Task boundary gold，開發者可能持續改善「錯誤答案如何穩定寫入」，卻不知道模型是否真的像顧問。

## 6. 反方論證後仍應保留的架構

| 現有設計 | 裁決 | 理由 |
|---|---|---|
| `turn.interpret` literal/contextual 分流 | 保留 | 短回答與來源 grounding 是必要底座 |
| QuestionFrame | 保留 | 「是／每天／財務」不能只靠 transcript 猜 |
| Evidence 原子事實 | 保留 | 適合作為 support，不適合作為完整 Task representation |
| Immutable reducer/state | 保留但凍結擴張 | 已解決可重播與 stale；目前不要再增加非核心 lifecycle |
| Provider-neutral LLM port | 保留 | 已完成，不需重做 |
| OpenRouter-first adapter | 保留 | 開發成本與模型選擇彈性足夠 |
| Capture/conformance | 保留並進維護模式 | 不再為未觀察到的邊界持續加功能 |
| Bounded operation context | 保留並修正 | bounded 不等於禁止必要 story slice |
| Deterministic Agenda | 保留概念、重做輸入 | Agenda 應讀 Role Coverage Map + Work Units |
| `question.select` 只選題與措辭 | 保留 | 權限小、容易 eval |
| 每 episode 固定兩題 | 改成 soft budget | 避免過長，但不能壓過真正的 sufficiency |
| `episode.code` 只讀 Evidence | 不採用 | Task boundary 需要 bounded narrative structure |
| `add_task` first | 不採用 | 必須先全域 compare/consolidate |
| Graph framework/multi-agent | 不採用 | 沒有 eval 證明必要，且增加 latency/除錯面 |
| 公版作 optional reference | 保留 | 可補 coverage，不可變成員工事實 |
| AI proposal + employee decision | 保留 | 員工是這份客製 JD 的採用權威 |

## 7. 修正後的最小工作分析流程

### 7.1 顧問流程不是一路問故事

推薦的產品流程：

```text
Phase 1  Role Scan
  盤點職位目的、典型工作週期、主要責任範圍、低頻高風險工作

Phase 2  Story Deep Dive
  針對代表性、困難、例外或高價值責任要求實際故事

Phase 3  Work Mapping
  把故事拆成 work units，辨識 Task／substep／method／tool／output／handoff

Phase 4  Global Task Synthesis
  跨故事與現有 JD 合併、拆分、去重，形成 Task proposals

Phase 5  O/P Enrichment
  對已穩定 Task 補工作產出與行為指標

Phase 6  K/S Drafting
  從已確認 Task/O/P + optional public reference 提出 K/S 與 linkage

Phase 7  Coverage Review
  檢查典型週期、季節性／年度工作、低頻高重要工作與員工自認缺漏

Phase 8  Employee Final Review / Export
```

這是 application-owned phase policy，不是八個 Agent。

### 7.2 每輪 runtime

```text
employee turn
  -> turn.interpret
  -> commit Evidence / receipt
  -> if short answer:
       update current work-unit gap
     else if substantive narrative:
       work.map
         reads bounded story slice + Evidence + current working map
         produces work-unit hypotheses
  -> deterministic coverage/sufficiency projection
  -> question.select
  -> one natural next question
  -> when a work unit is stable:
       task.synthesize against all current tasks + related work units
       produce add/edit/merge/no-op/clarify proposal
  -> employee accepts / edits / rejects
  -> Current Job Canvas and context refresh
```

第一版不需要 background agents、planner agent 或 Graph DB。

## 8. Story、Episode、Work Unit、Task 的正式邊界

### 8.1 建議語意

| 概念 | 定義 | 是否正式 JD |
|---|---|---|
| Story | 員工敘述的一段真實工作故事 | 否 |
| Episode | 系統管理的一段訪談焦點／故事容器 | 否 |
| WorkUnitHypothesis | AI 對故事內工作單元的分析假設 | 否 |
| Task | 跨故事整併後、具有獨立結果的工作責任 | 是 |
| Substep | 完成 Task 的必要方法或步驟 | 通常否 |
| Tool/Enabler | Java、Python、SAP、Excel、設備、資訊來源 | 否；可支持 S 或 context |
| Output | Task 的主要可查核產出／結果 | 是 |

### 8.2 關係不是一對一

```text
one Story -> zero to many Work Units
one Episode -> zero to many Work Units
one Task <- one to many Work Units / Stories
one Work Unit -> zero or one eventual Task
```

零個 Task 是合法結果，例如員工只提到：

- 使用 Java；
- 收到 Email；
- 偶爾幫忙列印；
- 另一個部門負責部署；
- 過去曾經做過某工作。

### 8.3 WorkUnitHypothesis 最小 contract

這是 operation output／working analysis，不是現在就要建立的新資料庫表：

```text
WorkUnitHypothesis
  ordinal
  label
  evidence_ordinals[]
  narrative_span_refs[]

  role:
    task_candidate
    substep_or_method
    tool_or_enabler
    output_or_result
    trigger_or_context
    collaboration_or_handoff
    unresolved

  boundary_signals:
    meaningful_outcome: yes | no | unknown
    independently_assignable: yes | no | unknown
    separately_reviewable: yes | no | unknown
    recurring_responsibility: yes | no | unknown

  related_work_unit_ordinals[]
  uncertainty_codes[]
```

模型不產 UUID、資料庫 ID 或正式 Task。application 只在需要跨 turn 追蹤時為 accepted hypothesis 配 identity。

### 8.4 何時拆成不同 Task

傾向拆開：

1. 有不同 meaningful outcome；
2. 可以獨立發生；
3. 可由不同人單獨負責；
4. 有不同主要接收者或交接點；
5. 可分別驗收或評估；
6. 有不同 trigger、頻率、重要性或責任邊界。

傾向保留同一 Task：

1. 行動共享同一主要目的與結果；
2. 只是順序步驟；
3. 只是工具／技術變化；
4. 只是檢查、轉檔、登入、下載、上傳等方法；
5. 拆開後無法單獨說明工作價值；
6. 實務上總是一起分派與驗收。

不能把規則寫成單一 if/else。模型做語意判斷，application 用 rubric 與 eval 控制。

## 9. Java／HTML／Python 類型的強制處理

### 9.1 分類規則

員工說：

> 我用 Java 寫 API、用 Python 整理資料，也會用 HTML 調整頁面。

第一步只可建立：

```text
tools/enablers
  Java
  Python
  HTML

actions
  寫 API
  整理資料
  調整頁面
```

不得直接建立三項 Task。

系統要問或從故事判斷：

- 這些行動是否為同一項產品功能服務？
- 是否有不同獨立產出？
- 是否分別被指派與驗收？
- 整理資料是開發流程中的步驟，還是獨立資料處理責任？
- 調整頁面是臨時支援，還是穩定工作責任？

### 9.2 Task boundary gate

一項 Task proposal 必須全部通過：

```text
has_action_and_object
has_meaningful_outcome_or_clear_work_value
is_current_or_contextually_current
is_employee_owned_shared_or_assists
is_recurring_or_role-responsibility
is_not_tool_only
is_not_method_only
is_not_substep_only
is_not_other_role_work
is_not_duplicate_or_narrow_variant_of_existing_task
```

無法通過時：

- 保留為 work-unit hypothesis；
- 連到既有 Task 作 method/context；
- 或提出一個 clarification gap；
- 不建立正式 Task。

### 9.3 Skill 也不能只由工具名稱成立

「使用 Python」只是一筆 tool evidence。

可能形成 Skill 的證據：

- 使用 Python 清理並驗證資料；
- 依錯誤紀錄定位資料轉換問題；
- 設計可重複執行的資料處理流程。

Skill 必須描述可觀察做法，並連到已確認 Task；不能只是軟體名稱。

## 10. Context Engine 修正

### 10.1 `turn.interpret`

保留目前最小 packet：

- current employee turn；
- preceding consultant question；
- eligible QuestionFrame；
- active focus identity；
- correction candidates；
- 少量 recent Evidence。

它不做 Task synthesis。

### 10.2 `work.map`

新增的最小充分 packet：

```text
bounded story transcript slice
  - 從該 story/episode 起點到目前 turn
  - 保留原始順序與 speaker

verified Evidence for that slice
current WorkUnitHypotheses for this story
small Current Job Canvas digest
interview scope: current role
authority and boundary rules
```

第一版不給：

- 完整 session transcript；
- 完整公版；
- K/S reference；
- provider history；
- hidden reasoning；
- 所有 Capture artifacts。

### 10.3 `question.select`

應改讀：

- Role Coverage Map；
- active work unit；
- work-unit gaps；
- unresolved boundary decisions；
- Current Job Canvas digest；
- interview burden/budget。

模型仍只負責：

- 選一個 application-approved gap；
- 寫一句 acknowledgement；
- 問一個自然問題。

### 10.4 `task.synthesize`

最小 packet：

```text
selected stable work units
their supporting Evidence
bounded narrative snippets when boundary depends on sequence
all current JD tasks, not only one nearby task
rejected/merged fingerprints
Task writing and boundary rules
optional public references only after employee work is established
```

輸出：

```text
no_change
add_task
edit_existing_task
merge_into_existing_task
needs_clarification
```

第一版 `split_existing_task` 可以延後到真實案例需要，但模型至少能回報
`needs_clarification: possible_split`，不能硬加。

### 10.5 `job.consolidate`

第一個 MVP 不必另做一個昂貴 operation。

先把最小全域 compare/dedupe 放進 `task.synthesize`。只有下列情況被 eval 證明後才拆出獨立 `job.consolidate`：

- Task 數量增加後 context 過大；
- duty grouping 與 Task synthesis 互相干擾；
- 跨多 episode dedupe 明顯失敗；
- 需要全文件批次重構。

這避免為了架構圖提前增加 operation。

## 11. Role Coverage Map：避免只談一個故事就結束

Role Coverage Map 是 application working projection，不是新公司資料庫：

```text
RoleCoverageMap
  responsibility_areas[]
    label
    support_evidence_ids[]
    related_task_ids[]
    status: mentioned | explored | represented_in_jd | unresolved

  cycle_checks
    typical_day_or_week_checked
    monthly_or_quarterly_checked
    annual_or_seasonal_checked
    low_frequency_high_importance_checked

  unresolved_critical_areas[]
  employee_ready_to_finish
```

第一版不需要所有欄位都寫進 DB；可由 session state + current JD deterministic projection產生。

`offer_finish` 至少應要求：

1. 已有一項以上正式 Task；
2. 沒有 unresolved critical responsibility area；
3. 已做至少一次典型工作週期 coverage check；
4. 已問過低頻／週期性重要工作，或員工明確表示沒有；
5. 員工有機會補充遺漏；
6. 不要求所有 O/P/K/S 欄位非空。

## 12. 訪談長度策略

### 12.1 固定兩題改成 soft default

每個 focus 預設追問 1–2 題仍合理，但它是負擔控制，不是 semantic close condition。

可延長至第 3 題的情況：

- 一個故事含多個可能獨立工作；
- ownership 不清；
- current/past 不清；
- outcome 不清，無法判斷 Task boundary；
- 員工主動提供高價值細節；
- 有重要矛盾。

應停止追問：

- 新資訊邊際價值低；
- 剩餘只是不影響 JD 的工具細節；
- 員工拒答或疲勞；
- 可先形成 working hypothesis 供文件區審閱；
- 問題只是為填滿欄位。

### 12.2 不逐項口頭確認

AI 可回應：

> 我聽到這段包含需求確認、資料準備、程式實作、品質檢查和成果交付。我先釐清它們是否屬於同一項責任；其他內容已保留。

不要求員工逐一回答五次「是」。工作區可以顯示暫存 working map，但正式文件只顯示 proposal。

## 13. 最小 Task capability eval

### 13.1 先寫品質案例，再寫 production Task code

不需要幾百個測試。第一輪建立約 12–20 個人工標註的繁中 cases，覆蓋真正失敗面：

1. 只提 Java／Python／Excel：0 Task；
2. 同一結果的五個步驟：1 Task；
3. 一個故事有三個獨立產出：3 Task；
4. 同一 Task 在兩個故事出現：合併成 1；
5. 員工工作與其他角色工作混合；
6. 過去工作與目前工作混合；
7. 低頻但高重要工作；
8. 高頻但只是支援性工作；
9. 純操作／服務型 Task，沒有硬造 Output；
10. 員工更正責任邊界；
11. 公版候選與員工實際工作不符；
12. 複合 Task 應拆分；
13. 相近步驟不應過度拆分；
14. 一段回答沒有足夠 outcome，需要 clarification；
15. 一個 responsibility area 仍完全未覆蓋；
16. 已有相同 Task 時應 edit/no-op，不再 add。

### 13.2 評估指標

核心：

- Task boundary precision；
- Task boundary recall；
- over-segmentation rate；
- under-segmentation rate；
- tool-to-task false promotion：必須為 0；
- duplicate Task rate；
- other-role/past-work false inclusion；
- Task evidence support；
- Task statement usefulness。

產品：

- 每個 accepted Task 所需 turn 數；
- 中位訪談時間；
- proposal accept/edit/reject；
- 員工「被正確理解」評分；
- 最終 JD usefulness；
- 員工補改 Task 的比例。

工程：

- schema validity；
- state commit；
- provider/conformance；
- stale/capture closure。

工程 gate 不可取代核心與產品指標。

### 13.3 Grader

使用最小組合：

- deterministic：ID、引用、禁止種類、duplicate exact/near-exact 候選；
- rubric model：split/merge 與 task usefulness；
- owner／領域人工：初始 gold 與抽樣校準；
- 每 case 多 trial 只用在模型變異性高的 semantic operation。

不為此另建大型 harness；沿用現有 runner/capture 能力，新增一個較小的 Task capability suite。

## 14. 修正後的 LLM operations

| Operation | 主要責任 | 是否現在需要 |
|---|---|---|
| `turn.interpret/2.x` | grounded Evidence + short-answer binding | 已完成，保留 |
| `work.map/1.x` | bounded story segmentation + work-unit hypotheses | 下一個核心 |
| `question.select/1.x` | 從 approved gaps 選一題並自然措辭 | 已完成，需換 agenda input |
| `task.synthesize/1.x` | 全域比較後 add/edit/merge/no-op/clarify | 緊接 work.map |
| `output_indicator.draft/1.x` | 對 accepted Task 起草 O/P | Task 品質通過後 |
| `requirements.draft/1.x` | K/S + task linkage + optional public coverage | O/P 後 |
| `job.compose/1.x` | 工作摘要、匯出文案 | 最後 |
| `job.consolidate/1.x` | 大型全文件重整 | MVP 不先拆出 |

`work.map` 與 `task.synthesize` 是 operation，不是 Agent。仍由同一 application workflow 呼叫 provider。

## 15. Prompt / Context / Harness / Loop / Graph 再裁決

### Prompt Engineering

正確方向：

- 每個 operation 單一 outcome；
- 提供正反例，尤其 tool/substep/task；
- 明確 unknown/no-op；
- 不要求 hidden chain-of-thought；
- 輸出 id-less ordinals。

需修正：

- Task boundary 不能只靠一句「不要把工具當任務」；
- 必須提供接近真實的 multi-work story few-shot；
- prompt 與 grader 共用同一產品 rubric，但 grader 不能只複製 prompt 判斷。

### Context Engineering

正確方向：

- operation-specific；
- bounded；
- business state 在 application；
- reference 與 employee evidence 分開。

需修正：

- 最小 context 必須是「最小充分」，不是最少 token；
- story analysis 要保留 bounded narrative order；
- question policy 要讀 Role Coverage Map，不只讀 action/output/purpose；
- Task synthesis 要讀全文件 Task 摘要，避免局部重複。

### Harness Engineering

正確方向：

- provider-neutral；
- Capture、trial、multi-trial、deterministic + human/model grader；
- outcome 與 trace 分開。

需修正：

- 暫停擴充低產品價值的 artifact 邊界；
- 新測試投資集中在 Task boundary capability；
- full suite 不必每個小 semantic prompt 改動都擴增大量 contract tests；
- 保留少量安全 regression，增加真正 end-to-end JD outcome。

### Loop Engineering

正確方向：

- application 控制 loop；
- 一次一題；
- STOP/decline 有 deterministic boundary；
- model 不直接 mutation。

需修正：

- 從「episode 欄位缺口 loop」提升為「role coverage + work unit + marginal value loop」；
- episode 問題數是 soft budget；
- Task proposal 必須全域 compare；
- finish 不能由「已有任何 Task」決定。

### Graph Engineering

目前不需要。

工作流程雖然可以畫成 graph，但只有少量已知 phase 與條件分支，用一般 application state machine 即可。
除非 eval 證明：

- 需要大量可動態重排的 tool branches；
- 長時間背景任務；
- 多個真正獨立專家 agent；
- 複雜平行執行與恢復；

否則不引入 LangGraph、Agent Framework graph、multi-agent handoff 或 Graph DB。

## 16. 最小實作順序

### R0：凍結非核心工程

- 不重做 provider adapter；
- 不增加 Capture taxonomy；
- 不增加 SaaS／ACL／tenant 功能；
- 不先做完整 K/S；
- 不先做 Graph；
- 不先把新 relational spec 全部 migration。

### R1：Task boundary gold

- 建 12–20 個人工標註故事；
- 每個 case 標：
  - work units；
  - task/substep/tool/output；
  - 應合併／應拆分；
  - 最終 Task；
  - forbidden Task；
- 先用目前選定模型做 no-code prompt experiment。

### R2：`work.map/1.x`

- 定義最小 output；
- 使用 bounded story slice + Evidence；
- 比較至少兩種 prompt/context：
  - Evidence only；
  - Evidence + bounded story；
- 若 bounded story 沒有明顯提升，不增加 production state。

### R3：Coverage + Agenda 修正

- 建最小 Role Coverage Map；
- Agenda 改讀 work units；
- soft question budget；
- 修正 finish gate；
- 不新增 planner agent。

### R4：`task.synthesize/1.x`

- 全域 current Task compare；
- add/edit/merge/no-op/clarify；
- Task boundary verifier；
- 接 Authoring proposal；
- 員工 accept/edit/reject。

### R5：可見垂直成品

```text
員工說一個包含工具與多項工作的故事
  -> 系統正確拆成 work units
  -> 只追問一個高價值問題
  -> 產生正確粒度 Task proposal
  -> 員工接受／修改／拒絕
  -> JD canvas 更新
  -> reload 後仍存在
```

這條成功後才擴充 Output／Indicator／K／S。

## 17. 最終裁決

### 正確的部分

現行架構不是過時的「大 prompt 一次生成 JD」，也沒有盲目採用 multi-agent。Evidence、Context、typed output、
deterministic workflow、proposal/human decision 都符合目前主流且可維護的方向。

### 錯誤或不足的部分

架構把大量精力放在可靠執行，卻尚未建立最重要的專業分析中間層。尤其：

- Episode 邊界錯用；
- Evidence 關係不足；
- story context 被排除；
- current eligibility 有漏洞；
- Agenda 過窄；
- finish gate 過早；
- add-only proposal 會造成 Task 膨脹；
- eval 尚未測 Task correctness。

### 建議決策

> 不推翻 vNext 底座；停止擴充底座。下一步不是直接做舊版 `episode.code`，也不是先把所有 T/O/P/K/S 表寫完，
> 而是先以小型 Task boundary gold 驗證 `work.map -> task.synthesize`。只有這條能正確處理工具、子步驟、
> 多工作故事與跨故事去重，才接進正式 Authoring Core。

## 18. Sources

### Job analysis / competency

- 勞動部勞動力發展署 iCAP，
  [職能基準發展指引](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download)。
- 勞動部勞動力發展署 iCAP，
  [行為事例訪談法](https://icap.wda.gov.tw/File/Knowledge/Method/2-04.pdf)。
- 勞動部勞動力發展署 iCAP，
  [職能相關概念](https://icap.wda.gov.tw/ap/knowledge_introduction.php)。
- U.S. OPM，
  [Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)。
- U.S. Department of Labor O*NET，
  [Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf)。
- U.S. Department of Labor O*NET，
  [Data Collection Overview](https://www.onetcenter.org/dataCollection.html)。
- U.S. Department of Labor O*NET，
  [Task Statements 30.0](https://www.onetcenter.org/dictionary/30.0/text/task_statements.html)。

### LLM architecture / context / eval

- Anthropic，
  [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)。
- Anthropic，
  [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)。
- Anthropic，
  [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)。
- Anthropic，
  [About Anthropic Interviewer](https://www.anthropic.com/about-anthropic-interviewer)。
- OpenAI，
  [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)。
- OpenAI，
  [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。
- OpenAI，
  [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)。
