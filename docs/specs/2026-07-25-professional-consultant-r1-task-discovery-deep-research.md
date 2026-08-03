# AI 專業職務分析顧問 R1：Task Discovery 深入研究與候選設計

> 日期：2026-07-25  
> 狀態：Task 粒度與混合式職務發現已確認；R1 逐檔案實作計畫尚未建立
> 研究層級：R1 垂直切片的專業方法與程式責任，不是逐檔案施工計畫  
> 產品範圍：本機 Web 職務分析產品；本階段只做 fixture／CLI 品質測試，不接 Web  
> 顧問流程權威：
> [`2026-07-25-professional-job-analysis-consultant-process-final-red-team.md`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)  
> 程式架構權威：
> [`2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md`](2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md)  
> 實現順序權威：
> [`2026-07-25-professional-consultant-architecture-realization-roadmap.md`](2026-07-25-professional-consultant-architecture-realization-roadmap.md)

---

> **【2026-07-26 修訂索引｜先讀這裡】**
>
> 本文件經外部紅隊複審後有五項修訂，分佈於六個章節。**原文一律保留並就地標記，不得據被否決的原文實作。**
> 完整依據見 [R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md)
> 與 [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)。
>
> | 編號 | 位置 | 修訂 |
> |---|---|---|
> | C-01 | §10.8、§13.2 | 便宜模型優先**已否決**；改為先用最強模型建天花板 + 2×2 model × schema ablation；兩階段拆分降級為待實驗假說 |
> | C-02 | §12.5 | exit gate 的「或可診斷性」**已否決**；Task 邊界不得退步為硬條件，判準須跑實驗前寫定 |
> | C-03 | §11、§12 | 8 案例只作快速篩選；鎖架構前擴至 20–30；critical 跑 pass³；案例須帶 `case_family_id` 與 `source_type` |
> | C-04 | §12.4 | 評審者拆三層：Rubric 資產／R1 blind grader／R7 product challenger |
> | C-07 | §13.3 | Structured Output 契約：provider 保證不可攜；portable subset + deterministic verifier；endpoint pinning |

> **【2026-08-03 owner 確認】** §16 決策一的 Task 粒度已接受；職務發現採「暫定職務框架＋開放工作敘事＋
> 定向補漏」，跨敘事形成 Task 後才歸納 Duty，Task 穩定後共同定義 O/P 並連結 KSA。完整取捨見
> [ADR 0042](../adr/0042-hybrid-job-discovery-and-ttop-formation.md)。先自由敘事、後顯示 taxonomy 的精確順序仍是
> 待 R1 驗證的產品假說，不得寫成官方已證明事實；本確認不授權 runtime 實作。

---

## 1. 研究問題

本文件只深入回答第一個、也是最容易讓整份 JD 失敗的問題：

> 員工說出一句話或一段工作故事後，系統應如何辨識其中的工作訊號、保留原話與不確定性、跨故事整併，
> 最後形成合理的 Task 候選與下一個顧問問題？

這個問題不能簡化成「從文字抽取 Task」。員工的話可能同時包含：

- 工作本身；
- 工具、程式語言、方法或步驟；
- 工作產出、品質條件、頻率與對象；
- 他人的工作或交接邊界；
- 過去工作、一次性支援或例外事件；
- 對先前說法的更正；
- 尚不足以分類，但不能遺失的重要內容。

上一版會把 Java、HTML、Python、Excel 或操作步驟各自升格為 Task，並不是單純 Prompt 寫得不好，而是缺少
「原話 → 主張 → 故事／工作單元 → 跨故事邊界判斷 → Task 候選」這層專業分析。

### 1.1 本階段要決定

1. Task 的專業判準；
2. Message、Source Claim、Story、Work Unit、Task Candidate 之間的語意；
3. `turn.understand` 應理解什麼、不得決定什麼；
4. `work.reconcile` 如何處理一故事多工作、多故事一工作、merge／split／no-op；
5. `consultation.decide` 如何選一個自然、有效且不引導的下一問；
6. Prompt、Context、LLM、deterministic code 與人工評測的責任邊界；
7. 用最少案例，如何先證明方向優於簡單 baseline。←【C-01 已修正；原文為「用最少案例**與低成本模型**」。
   低成本模型是 ablation 的一個 arm，不是驗證方向的前提】

### 1.2 明確不做

- 不設計最終資料庫表；
- 不接現有 vNext、Authoring Core、API 或 Web；
- 不做 Duty、Output、Indicator、K、S、A 的完整產生；
- 不做公版檢索與向量資料庫；
- 不做長期恢復；
- 不做 Graph runtime、Planner Agent、Reviewer 群或多 Agent；
- 不做 fine-tuning；
- 不做 SaaS、帳號、權限、多人協作、雲端部署；
- 不以 schema、hash、log 數量冒充職務分析品質。

---

## 2. 執行摘要

### 2.1 ~~最終推薦~~ 待實驗的主要候選【C-01】

R1 推薦採用：

> **兩次受約束的語意判斷，加一個普通 application controller。**

> **【C-01 修正｜此推薦降級為待實驗假說】** 「兩次」不再是已定案架構。R1 必須實際比較
> 「一次呼叫」與「兩階段」，**持平時選較簡單者（一次呼叫）**。快篩矩陣**同時**包含 A2–A5 的
> model × schema 2×2，以及固定「最強 + 輕 schema」下 **A2 vs A6** 的兩階段／一次呼叫比較 ——
> **不是「ablation 之後才在較佳配置比較」**；勝出配置下的 matched comparison 延後到
> shortlist 或 shipping model gate。
> 實驗矩陣固定為 **6 個 arm**，其中 A1 =**最強模型 + 輕 schema + 一次呼叫 + minimal harness**
> （baseline，算在六個之內，不另計），與 A6（同配置但 full harness）對照以檢驗 **harness bundle**
> 是否承重；定義見 §12.2 與 ADR 0040 決定 6。
> 見 [修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.1、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 5–8。

概念上有三個責任，但第一版只需要兩次模型呼叫：【C-01：此句為**待實驗假說**，見上方修訂框】

```text
員工原話 + 當輪 QuestionContext
  │
  ▼
LLM Call 1：turn.understand
  ├─ Source Claims
  ├─ corrections / negations / unknowns
  └─ Unmapped Signals
  │
  ▼
普通程式：驗證引用、套用更正、組合最小相關 context
  │
  ▼
LLM Call 2：work.reconcile + consultation.decide
  ├─ Story / Work Unit 判斷
  ├─ add / edit / merge / split / no-op / clarify
  ├─ Task Candidates
  └─ 一個下一步顧問動作與自然問題
```

`work.reconcile` 與 `consultation.decide` 在語意上分開，但 R1 可放在同一次模型呼叫，避免為架構純度多一次延遲與
錯誤傳播。未來只有在評測證明分開較好時才拆成第三次呼叫。

### 2.2 最關鍵判斷

1. **Task 不是句子中的名詞或動詞片段。**
2. **故事是訪談素材，不是 Task。**
3. **Work Unit 是分析中的工作假說，不是正式 JD 項目。**
4. **Task 是跨一句或多段故事後，對角色層級穩定責任的暫定結論。**
5. **工具、方法、知識、步驟、輸入、產出與品質條件都可能重要，但不能因此各自成為 Task。**
6. **一個故事可支持 0..N 個 Work Unit；多個故事也可能支持同一個 Task。**
7. **頻率是重要證據，但不是唯一門檻。低頻、高影響且正式負責的工作仍可能是 Task。**
8. **`no-op` 是正常且必要的結果。每輪都生 Task 代表架構有錯。**
9. **結構化輸出只保證形狀，不保證職務分析正確。**
10. **第一版不需要 Graph framework；關係語意可以先用普通型別與 application code 表達。**

### 2.3 研究裁決

目前沒有發現任何大廠公開一套可直接照抄的「員工訪談 → 臺灣 iCAP 格式客製 JD」完整產品架構。
可辯護的做法是組合兩條權威證據鏈：

1. **專業工作分析方法**：iCAP、O*NET、OPM；
2. **現代 LLM 工程方法**：OpenAI、Anthropic。

前者決定「什麼是好的工作分析」，後者決定「如何把這種判斷做成可控、可評估的模型流程」。
不能反過來用 Agent 框架的能力定義顧問方法。

---

## 3. 權威資料讀後結論

### 3.1 專業工作分析資料

| 權威來源 | 讀到的核心方法 | 對 R1 的直接影響 |
|---|---|---|
| [O*NET Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf) | Task 是具有 meaningful outcome 的最小活動單位；可由 Action、Object、Purpose／Result、Enabler、Context 組成；工具與方法屬 Enabler | Java、Excel、方法與設備通常是 Task 的手段，不是 Task 本身；Task 必須能說清楚做什麼及其結果 |
| [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) | 工作分析是系統性檢視 Tasks、Competencies 及兩者連結 | 不能從一句話同時隨意產生 Task 與 K/S；先建立工作，再檢查能力連結 |
| [OPM Job Analysis Presentation](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_presentation.pdf) | Task 描述可用「做什麼、對誰／什麼、產生什麼／為什麼／怎麼做」；避免 double-barreled、過度具體工具與模糊形容詞；Task 要評估頻率與重要性 | Task 邊界要檢查過度拆分、過度合併、工具升格、頻率與重要性，而不是只檢查文字流暢 |
| [OPM Six Steps to Conducting a Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_checklist.pdf) | 先蒐集職位資料，再列 Tasks／Competencies，由 SME 評分 criticality，最後建立 task–competency linkage | 員工自述是重要來源，但不是一句話直接成為文件真相；候選仍需後續確認與跨資料檢查 |
| [O*NET Content Model](https://www.onetcenter.org/content.html) | Tasks、Work Activities、Knowledge、Skills 位於不同內容層級 | T、活動、K、S 必須分層；不能因一句話出現 Python 就同時把 Python 變成 Task 與 Skill |
| [O*NET 30.3 Task Statements](https://www.onetcenter.org/dictionary/30.3/json/task_statements.html) | 現行資料仍區分 occupation-specific Tasks，並保留 task ID、core／supplemental 等資訊 | 公版可在後續做 challenger／候選參考，但 R1 不能先拿公版替員工決定實際工作 |
| [O*NET Data Collection](https://www.onetcenter.org/dataCollection.html) | 使用 incumbents、occupational experts、analysts、job postings、研究與 ML／NLP 等多種來源 | 專業資料不是單一模型一次抽取；第一版只有員工來源時，必須誠實保留不確定與限制 |
| [iCAP 職能基準介紹](https://icap.wda.gov.tw/ap/knowledge_introduction.php) | 職能基準區分主要職責／工作任務、工作產出、行為指標、K/S/A；工作產出是關鍵過程或最終產出，行為指標是成功完成標準 | R1 應先把 Task 邊界做對；O/P/K/S 是後續不同分析責任，不能在 Task 發現時混成一包 |
| [iCAP 行為事例訪談法（BEI）](https://icap.wda.gov.tw/File/Knowledge/Method/2-04.pdf) | 以具體過去事例、STAR 與追問取得行為資料；一次聚焦一個情境、按時間順序追問；後續編碼與主題分析是困難且具判斷性的工作 | 故事適合取得具體行為證據，但故事不等於 Task；系統仍需跨故事整理、比較與抽象化 |
| [iCAP 品質管理](https://icap.wda.gov.tw/ap/quality_manage.php) | 強調系統化方法、步驟紀錄與結果檢核 | 必須能看出候選 Task 根據哪些原話與判斷形成，而不是只留漂亮的最終句子 |

本次研究採用現行 O*NET 30.3 data dictionary。iCAP／OPM 部分方法文件較早，但仍由現行官方入口提供，且其工作
分析概念與現行 O*NET 分層一致。本文件採用的是穩定的專業判準，不把舊 API 或舊 LLM 框架當成現行技術。

### 3.2 現代 LLM 工程資料

| 權威來源 | 讀到的核心方法 | 對 R1 的直接影響 |
|---|---|---|
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | Structured Outputs 可提高 schema adherence，但內容仍可能犯錯；輸入與 schema 不相容時，模型可能為了填滿 schema 而虛構 | schema 必須允許 `no-op`、unknown、unmapped、clarify；不能要求每輪必有 Task |
| [OpenAI Evaluation Best Practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | 評測要 task-specific、早做、涵蓋正常／邊界／對抗案例，並以人工校準；分類、pairwise、pass/fail 往往比開放式打分可靠 | 先做 8 個 Task 邊界案例與 baseline 對照，不先建大型通用 Harness |
| [OpenAI Reasoning Best Practices](https://developers.openai.com/api/docs/guides/reasoning-best-practices) | 指示應簡單、直接、成功條件具體；不需要要求模型輸出 chain-of-thought | Prompt 要求結論、來源引用與短理由，不保存或評分私有思考鏈 |
| [Anthropic Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) | 先用最簡單可組合 workflow；固定、可定義的任務適合 workflow；框架可能遮蔽 prompt 與 response；多 Agent 會增加成本與複雜度 | R1 使用兩次 bounded operation 與普通 controller，不建 Planner／Worker／Reviewer graph |
| [Anthropic Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Context 是有限資源；應提供最小、高訊號且與操作相關的內容；過長 context 會產生 context rot | 不把完整 transcript 塞進每次呼叫；`turn.understand` 與 `work.reconcile` 使用不同 context packet |
| [Anthropic Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | 區分 transcript 與 outcome；可混用 code、model、human grader；對話系統要同時看最終狀態與互動品質；不需要一開始塞滿 evaluator | R1 同時評 Task 結果、來源忠實度與下一問，不用大量 evaluator |
| [Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer) | 採 planning、adaptive interviewing、analysis 分工；訪談依 rubric 保持研究目標但允許岔題；承認 self-report、selection 與 interpretation 限制 | 支持「固定分析責任、彈性問題路徑、訪談與分析分責」；員工自述仍不能自動等同客觀完整事實 |
| [About Anthropic Interviewer](https://www.anthropic.com/about-anthropic-interviewer) | 現行說明持續採規劃、動態訪談與分析三段責任 | 可參考其 adaptive interview 原則，但它不是職務分析產品，不能直接取代 Task 專業判準 |

OpenAI 舊 Evals 平台已進入退場時程，因此本研究只沿用官方評測原則，不把 prototype 綁在將退役的平台。
第一版應使用本地、provider-neutral 的小型案例執行與輸出比較。

---

## 4. 專業語意：不要把五個不同層級混成一個「抽取結果」

### 4.1 Employee Message

員工一次送出的原始內容。它是來源，不是分析結論。

例：

> 我每天用 Python 把門市資料整理後匯入 ERP；月底資料比較多，還要先找出重複資料，不然財務會對不上。

這段話至少可能包含：

- 方法／工具：Python、ERP；
- 工作動作：整理、匯入、找出重複資料；
- 對象：門市資料；
- 頻率：每天、月底；
- 條件：月底資料較多；
- 結果／風險：避免財務對帳錯誤；
- 潛在 Task：維護門市資料匯入與品質。

若直接用動詞切 Task，會產生「使用 Python」「整理資料」「匯入 ERP」「找重複資料」四個工作，這正是錯誤架構。

### 4.2 QuestionContext

當輪問題對短回答的有限語意範圍。它只允許把回答連回已明確詢問的命題，不允許補出未說內容。

例：

```text
AI：這項資料匯入通常多久做一次？
員工：每週。
```

合理理解：

- 「每週」修飾已知的資料匯入活動。

不合理理解：

- 員工每週執行所有資料相關工作；
- 此工作必然很重要；
- 員工是唯一負責人；
- 因為每週，所以已足以成為正式 Task。

「不知道」「不適用」「想不起來」也必須保留成不同狀態，不能都轉成否定或空字串。

### 4.3 Source Claim

從原話中辨識出的、仍可回到來源片段的最小主張。它的目的是保留員工實際說了什麼，不是提早寫 JD。

R1 至少要能表示下列語意：

- actor／ownership：本人、共同、支援、他人、未知；
- time scope：現行、過去、未來構想、未知；
- recurrence／typicality：例行、週期性、低頻正式、一次性、例外、未知；
- action／object／recipient／outcome；
- tool／method／condition；
- polarity：肯定、否定；
- certainty：明確、模糊、不知道；
- correction：更正或取代哪一個舊主張；
- source span：根據原話哪一段。

`Source Claim` 不需要現在就成為資料庫 schema。本階段只固定語意與可評測輸出。

### 4.4 Unmapped Signal

模型看見可能重要，但目前無法安全映射的內容。

例：

> 有時候那個夜間批次很麻煩，出問題會被追得很急。

若目前不知道「夜間批次」是本人負責的 Task、工作條件、事件背景還是他人流程，應保留：

- 原始片段；
- 為何可能重要；
- 為何目前不能升格；
- 可能需要追問的缺口。

它不是垃圾桶，也不能被安靜丟棄。後續問題或新故事可能使它成為新的 Claim／Work Unit。

### 4.5 Story

一個具體工作事件的訪談容器，通常包含：

- 情境／觸發；
- 輸入；
- 本人的動作與判斷；
- 他人與交接；
- 結果、接收者與影響；
- 例行性／頻率；
- 異常與限制。

故事的價值是讓抽象敘述變具體。它本身不是 Task，原因包括：

- 一個故事可能只有步驟，沒有獨立工作；
- 一個故事可能含多個可分責的工作；
- 多個故事可能只是同一 Task 在不同情境的實例；
- 精彩故事可能是罕見例外，不能代表主要職務。

### 4.6 Work Unit

顧問從一個或多個 Source Claims／Story 中形成的「工作邊界假說」。

它至少回答：

- 做了什麼；
- 對什麼／誰；
- 產生什麼有意義結果；
- 是誰負責；
- 是否現行；
- 是否穩定或屬正式低頻責任；
- 是否可被獨立指派、檢核或討論；
- 目前有哪些支持與反證；
- 邊界仍缺什麼。

Work Unit 是分析工具，不應直接顯示成正式 JD，也不應要求員工理解這個術語。

### 4.7 Task Candidate

跨故事與既有工作模型比較後，形成的角色層級穩定工作候選。

Task Candidate 與 Work Unit 不是一對一：

```text
一個 Story ──→ 0..N Work Units
多個 Stories ──→ 同一 Work Unit／Task Candidate
一個 Work Unit ──→ Task、既有 Task 的證據、步驟、工具或 no-op
多個 Work Units ──→ merge 成一個 Task，或 split 成不同 Tasks
```

這是「Graph semantics」：多對多關係與可回溯來源。R1 不需要因此安裝 Graph database 或 workflow framework。

---

## 5. Task 的專業判準

### 5.1 建議的 Task 定義

第一版採用：

> **Task 是角色目前負責、具有有意義工作結果、在組織上可被獨立指派或檢核，並屬穩定例行或正式低頻責任的工作單位。**

文字形式通常接近：

> 動作 + 對象 + 目的／結果，必要時補充關鍵條件；工具與方法只有在區分責任時才寫入。

### 5.2 六個必要檢查

| 檢查 | 要問的問題 | 不通過時通常是 |
|---|---|---|
| Meaningful outcome | 完成後產生了什麼有意義改變、交付或責任結果？ | 細步驟、按鍵、工具使用 |
| Role responsibility | 這是員工本人目前負責，還是他人、過去、旁觀或偶爾幫忙？ | actor／time leakage |
| Assignability | 能否合理交辦成一項工作，而不是一句手段描述？ | 方法、知識、技能 |
| Checkability | 能否判斷是否完成或是否達到工作目的？ | 過度抽象、無 outcome |
| Stability | 是穩定例行／週期性，或明確的正式低頻責任嗎？ | 單次事件、臨時支援 |
| Boundary coherence | 內含活動是否共享主要目的與責任，還是應 merge／split？ | over-split／over-merge |

這六項不是硬算分數。LLM 必須給出候選判斷與來源，評測再檢查是否合理。

### 5.3 頻率不是唯一門檻

「規律執行」不等於「每天／每週」。下列工作即使一年一次，仍可能是 Task：

- 年度災難復原演練的正式負責人；
- 法定稽核資料準備；
- 年度預算編製；
- 特定重大事故的 on-call 應變責任。

相反地，某件事即使發生過一次、花很多時間，也不一定是穩定 Task：

- 某次幫同事安裝 Java；
- 臨時替別部門整理一份表格；
- 一次性的搬遷支援。

因此需要同時看：

- 頻率／典型性；
- 是否為正式角色責任；
- 重要性／風險；
- 可預期是否再次承擔。

### 5.4 工具何時不是 Task，何時可能成為 Task

#### 不是 Task

> 我用 Java、Python 和 HTML 寫系統。

這些是技能／技術／方法訊號。真正 Task 仍要追問系統目的、本人責任與產出。

可能形成：

> 開發與維護訂單處理服務，以支援門市交易資料正確傳送至 ERP。

Java／Python 可留作 Skill／Knowledge 候選或技術條件，不能各寫一個 Task。

#### 可能是 Task

> 我每季主責 Java 執行環境升級，先驗證相容性、安排停機窗口，並確保服務升級後可正常運行。

此處重點不是「使用 Java」，而是：

- 有獨立 outcome：受控完成執行環境升級；
- 有本人責任；
- 可指派與檢核；
- 有穩定週期。

合理 Task 可能是：

> 規劃並執行 Java 執行環境升級，以維持應用服務的相容性與可用性。

---

## 6. `turn.understand`：高召回理解，但不搶先定義 Task

### 6.1 責任

`turn.understand` 要做到：

1. 掃描完整新回答，不只看目前 StoryFocus；
2. 依 QuestionContext 理解短回答；
3. 提取可回到來源的 Source Claims；
4. 標出 actor、time、typicality、frequency、polarity、certainty 與 correction；
5. 保留工具、方法、步驟、O/P/K/S 等線索，但不升格；
6. 把無法安全映射的內容留在 Unmapped Signals；
7. 明確允許「此輪沒有新工作主張」。

它不得：

- 直接寫正式 Task；
- 直接修改 Current JD；
- 因 schema 必填而補 outcome／ownership；
- 把問題中的假設當成員工已確認；
- 把未知當否定；
- 因員工用了專業術語就推定熟練程度；
- 因一句話有多個動詞就建立多個工作。

### 6.2 最小 Context Packet

建議只提供：

- 當輪 AI 問題；
- `QuestionContext`：這題正在確認什麼、指向哪些既有候選；
- 員工完整原始回答；
- 立即必要的前一輪對話；
- 目前 StoryFocus 的精簡摘要；
- 與回答中明確指涉對象相關的少量既有 claims／task candidates；
- 若有內容未載入，明示 omission，而不是假裝不存在。

不提供：

- 整份長 transcript；
- 大量公版候選；
- 所有 Task／OPKS 全文；
- 無關故事；
- 先前模型的自由敘事分析；
- 隱藏 chain-of-thought。

### 6.3 Prompt 原則

依現行 OpenAI 與 Anthropic 指引：

- 指示短、直接、責任單一；
- 先定義「只能根據哪些來源」；
- 明列不能推論的高風險項目；
- 使用少量、多樣且代表錯誤邊界的 examples；
- 要求輸出 source span／claim type／qualifier；
- 允許 `unknown`、`unmapped`、`no new claim`；
- 不要求模型「一步一步展示思考」；
- 不在一個 Prompt 同時要求寫 Task、OPKS、下一問與 JD 文案。

### 6.4 Deterministic code 可驗證什麼

- schema 合法；
- source span 的文字確實存在於允許來源；
- correction target 存在；
- enum 與引用合法；
- 不同 claim ID 不重複；
- 明確否定／過去／他人標記沒有被序列化丟失；
- 模型沒有輸出正式 JD mutation。

Deterministic code 不能可靠判斷：

- 這個 outcome 是否「有意義」；
- 兩段故事是否其實是同一工作；
- 某步驟是否值得獨立成 Task；
- 某項正式低頻責任是否屬角色核心。

這些仍需語意模型與人工 rubric。

---

## 7. `work.reconcile`：Task 是比較與整併的結果

### 7.1 責任

`work.reconcile` 取得：

- 新增或更正後的有效 Source Claims；
- 必要的原始片段；
- 相關 Stories／Work Units；
- 最相近的既有 Task Candidates；
- 支持、反證與 unresolved boundary；
- 相關 merge／split／reject 歷史摘要；
- 明確的 context omission。

然後判斷：

```text
add      新的穩定工作候選
edit     新資料修正既有候選的敘述或邊界
merge    原本分開的候選其實共享責任與 outcome
split    原候選混入可獨立指派、結果不同的工作
no-op    只是工具、步驟、補充證據、重複資訊或無文件影響
clarify  缺少決定邊界的關鍵資訊，不能安全判斷
```

### 7.2 一故事多工作

不是看到多個動詞就 split。只有當活動具備不同的：

- 主要 outcome；
- 責任承諾；
- 接收者／服務對象；
- 可獨立指派性；
- 完成判準；

才傾向拆開。

例：

> 客戶回報錯誤後，我先查 log、重現問題、修程式、部署，確認恢復後通知客戶。

多數情況這是一個「處理應用系統故障」Task 的步驟，不應拆成查 log、重現、寫程式、部署、通知五個 Task。

但若員工同時：

> 事故後還要獨立完成根因分析報告，並主持跨部門改善追蹤，這是另外一項固定責任。

「恢復服務」與「治理後續改善」可能有不同 outcome、接收者與責任，可形成不同 Work Units／Tasks。

### 7.3 多故事一工作

不同情境不代表不同 Task。

例：

- 每天匯入門市交易資料；
- 月底匯入量增加，要先排除重複資料；
- 遇到欄位格式改版，要調整驗證規則。

這可能都是「維護門市交易資料匯入與品質」的不同情境，不宜建立三個高度重疊的 Task。

### 7.4 更正的權威

若員工說：

> 剛才說錯了，不是我負責部署；我只負責測試，部署是維運做。

新說法必須：

- 取代舊 actor／ownership 主張；
- 舊內容可保留作對話歷史與 trace；
- 舊主張不得繼續支持有效 Task；
- 若既有候選含部署責任，必須 edit、split 或撤回；
- 下一問只在仍有必要時澄清交接，不可讓舊錯誤復活。

### 7.5 輸出原則

每個決策至少要可看見：

- 決策類型；
- 受影響 Task Candidate；
- 候選 Task statement；
- 支持的 claim／work-unit refs；
- 反證或限制；
- Task 六項判準中尚未成立的部分；
- 為何不是工具／步驟／他人／過去／一次性；
- 若 `clarify`，缺少的唯一關鍵資訊。

不需要輸出模型完整推理。短而可檢查的 decision rationale 即可。

---

## 8. `consultation.decide`：不是 Planner，而是每輪選一個最高價值動作

### 8.1 R1 只保留三種動作

| 動作 | 適用情況 | 問題目標 |
|---|---|---|
| `broaden` | 目前沒有足夠工作廣度、只得到單一工具或單一事件 | 發現另一個責任區或例行工作 |
| `deepen_story` | 已知可能的工作，但描述抽象、缺少本人動作／判斷／outcome | 取得一個具體實例或關鍵結果 |
| `clarify_boundary` | actor、time、typicality、獨立 outcome、merge／split 或 correction 有高風險不確定 | 只問能改變 Task 邊界的關鍵問題 |

R1 不需要完整長期 plan，也不需要 LLM 先列十個問題。

### 8.2 選擇優先順序

建議使用有限決策規則，不做虛假的精密分數：

1. 有 correction、actor／time 衝突或高風險 Task 誤收時，先 `clarify_boundary`；
2. 已有合理工作方向，但缺 outcome／ownership／實際行動時，`deepen_story`；
3. 目前只看到工具、單一事件或工作覆蓋太窄時，`broaden`；
4. 問過且已回答的內容不得重問；
5. 每輪只選一個主要問題；
6. 先自然承接員工內容，再提問，不呈現內部術語或審訊式清單。

### 8.3 好問題與壞問題

員工：

> 我主要用 Python 整理資料。

較差：

> 請說明 Python 的工作產出、行為指標、知識、技能、頻率、重要性與利害關係人。

問題：

- 一次問太多；
- 帶出系統欄位；
- 暗示「Python」已是 Task；
- 員工負擔高。

較好：

> 你最近一次整理這些資料，是要交給誰使用，最後要完成什麼結果？

它同時有機會取得 recipient 與 outcome，但仍是一個自然問題。

---

## 9. 候選架構比較

### 9.1 選項 A：單次 end-to-end 大 Prompt

```text
transcript → 一次模型 → Tasks + 下一問
```

優點：

- 最快；
- 呼叫少；
- 可作 baseline。

主要問題：

- 原話理解、工作邊界與下一問互相污染；
- 很難判斷錯在理解、整併還是提問；
- schema 容易迫使模型每輪產生 Task；
- correction、merge／split 與 no-op 不透明；
- 後續難以加入長期 Context。

裁決：**保留為比較 baseline，不作推薦架構。**

### 9.2 選項 B：兩次 bounded semantic operations

```text
Call 1：理解原話
普通 code：驗證與組 context
Call 2：reconcile Task + 選下一問
```

優點：

- 保留原話與分析結論邊界；
- 可單獨評測理解與 Task 邊界；
- correction／unknown／unmapped 不易被最後文案吃掉；
- 相較三到五 Agent 仍然簡單；
- 未來可自然接到多輪 resident work model。

風險：

- 第一次錯誤可能傳給第二次；
- schema 與 context 若過度設計，仍會僵化；
- 比 baseline 多延遲與成本。

裁決：**推薦，但必須用 baseline 實證它有改善。**

### 9.3 選項 C：規則／傳統 NLP 直接分類

優點：

- 快、便宜、可預測；
- 適合 deterministic validation。

主要問題：

- meaningful outcome、ownership、merge／split 是語意判斷；
- 中文省略主詞、短答、故事跨句關係不適合只靠 regex；
- 規則容易重演「見動詞就建 Task」。

裁決：**只作 verifier 與明確約束，不作核心分析器。**

### 9.4 選項 D：Planner + Worker + 多 Reviewer／Graph runtime

優點：

- 看似可分工；
- 可針對不同面向平行審查。

主要問題：

- R1 問題尚未證明需要多 Agent；
- 增加成本、延遲、錯誤傳播與除錯困難；
- Reviewer 可能只是重複同一模型偏差；
- Graph framework 不能替代 Task 專業判準；
- 容易投入基礎設施，仍不知道 Task 是否切對。

裁決：**不採用。只有未來評測證明單一 reconcile operation 無法可靠處理特定獨立審查時，才新增一個有明確
rubric 的 reviewer。**

---

## 10. Make the strongest case that the 推薦架構仍然是錯的

### 10.1 反方一：兩階段會把錯誤固化

`turn.understand` 一旦把原話錯拆，第二階段看到的是被整理過的錯誤，可能比直接看原文更有自信。

防線：

- 第二階段必須同時看到必要原始片段，不只看 claims；
- claims 必須保留 uncertainty 與 unmapped；
- baseline 與候選架構比較時，要特別看是否發生「第一次誤解 → 第二次合理化」；
- 若兩階段邊界品質沒有改善，回到單次模型或重新劃分責任。

### 10.2 反方二：Work Unit 本身會誘發過度拆分

只要建立一個名為 Work Unit 的中間物件，模型可能傾向找出很多單元，以證明自己有分析。

防線：

- schema 允許 0 個 Work Unit；
- 明訂工作步驟、工具與補充條件可只附著既有工作；
- 以 over-split 作 critical failure；
- 不以候選數量或欄位完整率計分。

### 10.3 反方三：高召回會淹沒真正工作

`turn.understand` 要接住所有訊號，可能製造大量低價值 claims／unmapped signals，後續 context 反而變差。

防線：

- 高召回不等於每個名詞都建立物件；
- source claim 只保存可陳述的主張；
- 工具清單可聚合為同一 method signal，不需每個詞一筆；
- Context Policy 只帶與當次 operation 有關的高訊號內容；
- R1 評估噪音是否導致 Task 誤收與問題漂移。

### 10.4 反方四：專業 Task 邊界沒有唯一答案

同一工作可依職位層級、管理用途與組織分工寫成不同粒度。模型可能產生「合理但不同」的答案。

防線：

- gold 不應只允許一個精確字串；
- 以禁止錯誤、必要語意與可接受邊界做 rubric；
- 比較 over-split／over-merge、actor、time、outcome，而不是字面完全相同；
- 讓 Task 保持 candidate，後續由員工確認與多輪證據修正。

### 10.5 反方五：員工自述可能不完整或不準確

再好的模型也不能從未被說出的內容還原完整職務。員工可能美化、遺忘例行工作、只講精彩事件或混入他人工作。

防線：

- R1 不宣稱完整 JD；
- 下一問需逐步擴大 coverage；
- 後續才加入週期盤點、材料、公版 challenger 與反證；
- 所有結論標記為根據當前訪談形成，而非組織正式真相。

### 10.6 反方六：八個案例很容易被 Prompt 過度擬合

防線：

- 8 類只固定能力，不在 Prompt 原封不動放全部測試句；
- examples 與 eval fixtures 分離；
- 通過後再用少量 unseen paraphrases／真實匿名片段抽查；
- 不因測試全綠就直接接 Web。

### 10.7 反方七：精彩故事偏差

BEI／STAR 擅長取得具體資料，但罕見事故可能比例行工作更容易被記住，導致職務模型失衡。

防線：

- R1 把 Story 當證據，不把 Story 自動升格 Task；
- R2 必須加入日／週／月／年與低頻高影響 coverage；
- `typicality` 與 `importance` 分開；
- 下一問不只追最精彩的故事。

### 10.8 反方八：便宜模型可能根本做不好複雜邊界

> **【2026-07-26 修訂 C-01｜本節防線已被否決】**
>
> 原防線的順序與 2026 年權威指引相反。OpenAI 明確建議：先用**最強模型**建立品質 baseline，
> 再換小模型 ——「**this way, you don't prematurely limit the agent's abilities, and you can diagnose
> where smaller models succeed or fail**」。理由不是成本，是**歸因能力**。
> Anthropic 亦指出「every component in a harness encodes an assumption about what the model can't do
> on its own, and those assumptions are worth stress testing」：用弱模型校準 harness，
> 會把 scaffolding 永久 over-fit 到該模型。
>
> **現行規定為：**
>
> 1. R1 的快篩矩陣是 6 個 arm，**同時**包含 A2–A5 的 model × schema 2×2
>    （｛最強, 便宜｝×｛輕, 重 schema｝，架構固定兩階段），以及固定「最強 + 輕 schema」下
>    **A2 vs A6** 的兩階段／一次呼叫比較，另含 A1（同配置、minimal harness）作 harness 承重對照；
> 2. **勝出配置下的 matched comparison 延後到 shortlist 或 shipping model gate** ——
>    不是「ablation 之後才在較佳配置比較」；
> 3. **兩階段拆分降級為待實驗假說**，不再視為已確定架構，持平時選一次呼叫；
> 4. shipping 模型定案時必須重跑一次該對照，並重審 harness、拆掉不再承重的 scaffolding。
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.1、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 5–8。
> 以下原文保留供追溯，**不得據原文執行**。

防線：

- ~~固定便宜模型先驗證架構，不先花錢比較多模型；~~ ←【C-01 已否決】
- ~~若錯誤集中在模型能力而不是 context／schema／責任分工，再用一個較強模型做小型 spot check；~~
  ←【C-01 已否決：順序反轉】
- 不因換強模型暫時變好，就忽略可診斷性與 critical failure。

### 10.9 最終反方裁決

推薦架構不是因為「兩階段看起來先進」，而是它提供可診斷邊界：

- 原話是否理解正確；
- Work Unit 是否過度拆分；
- Task 是否跨故事合理整併；
- 下一問是否針對真正不確定性。

但若小型實驗顯示它沒有比單次 baseline 更準，或只增加成本與錯誤傳播，就應停線重劃，而不是繼續加 Reviewer、
Graph、資料庫與 Web。

---

## 11. 最小 capability cases

> **【2026-07-26 修訂 C-03｜八類案例的定位與擴充規則】**
>
> 八類案例本身保留，但**定位改變**：它們是**快速篩選**用的，只能淘汰明確錯誤設計，
> **不得用於宣稱候選架構勝出**（8 個高度相關的樣本撐不起比較結論）。
>
> - 鎖定架構前擴至 **20–30 個**，優先取真實失敗語料，不足才補構造案例；
> - critical case 跑 **3 trials 看 pass³**（面向員工、要求一致性的系統用 pass^k 而非 pass@k）；
> - 每個案例必帶 `case_family_id`（統計聚類單位）與
>   `source_type`（`constructed_edge`／`human_manual_test`／`real_employee_interview`）——
>   **不設預設值，依實際來源分類**：人工構造或由舊 session 改寫合成＝`constructed_edge`
>   （可另留 `source_session_ref`）；原樣使用人類操作逐字稿＝`human_manual_test`；
>   **一律不得升級為 `real_employee_interview`**；
> - 同一 session 衍生的多個案例共用一個 family，整組算一個單位；
> - R1 **不做正式 power analysis**。
>
> 可重用的既有語料與不可沿用的舊 gold 契約，見
> [修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §5。
> 依據：同文件 §3.3、[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 11–13。

案例不以數量取勝。第一批固定八類，每類一個主要能力與明確禁止錯誤。

### TI-R1-01：工具不是 Task

輸入核心：

> 我平常用 Java、HTML 和 Python 開發。

預期：

- 三者保留為工具／方法／K/S 線索；
- 不建立三個 Task；
- 因缺少目的、對象與 outcome，傾向 `deepen_story`；
- 自然詢問最近一次開發的系統要解決什麼問題或交付給誰。

Critical failure：

- Task = 使用 Java；
- Task = 撰寫 HTML；
- Task = 使用 Python。

### TI-R1-02：工具相關工作有獨立 outcome，因此可成 Task

輸入核心：

> 我每季主責 Java 執行環境升級，要先做相容性驗證、排停機時間，最後確認服務都恢復。

預期：

- Java 是對象／技術條件，不是因名稱本身成 Task；
- 能形成「規劃並執行執行環境升級，以維持服務相容性與可用性」候選；
- 驗證、排程、恢復確認通常是同一 Task 的步驟；
- 下一問可確認責任範圍或成功標準，不必再問已知頻率。

### TI-R1-03：一個故事包含多個工作，但不能見動詞就拆

輸入核心：

> 系統故障時我會查 log、重現、修復和部署；事故後我還要獨立完成根因報告，主持每月改善追蹤。

預期：

- 查 log、重現、修復、部署通常整併為故障處理；
- 根因報告與改善追蹤若有獨立責任／outcome，形成另一 Work Unit；
- 不建立六個 Task；
- 若「每月改善追蹤」責任仍模糊，`clarify_boundary`。

### TI-R1-04：多個故事支持同一 Task

輸入核心：

- 故事 A：每天匯入門市交易資料；
- 故事 B：月底先排除大量重複資料；
- 故事 C：欄位格式改版時調整驗證規則。

預期：

- 傾向整併為資料匯入與品質維護的同一 Task；
- 不因日常／月底／改版建立三個重疊 Task；
- 保留不同情境作條件與證據。

### TI-R1-05：過去工作不得成為現行 Task

輸入核心：

> 我前一份工作會管理伺服器，但現在這份工作只負責應用測試。

預期：

- 管理伺服器標記為過去；
- 不支持現行 Task；
- 應用測試仍需 outcome／範圍才決定候選；
- 不因技術經驗把過去責任帶入現在 JD。

### TI-R1-06：他人工作與交接

輸入核心：

> 我把測試報告交給維運，正式部署是他們做；我只在部署後確認核心功能。

預期：

- 正式部署不是本人 Task；
- 測試報告與部署後驗證是本人的可能工作訊號；
- 若兩者同屬同一測試責任可 merge，不能把維運責任誤收；
- 下一問聚焦本人完成標準，而非詢問部署細節。

### TI-R1-07：一次性支援

輸入核心：

> 上個月同事請假，我幫他做過一次供應商請款，平常不是我負責。

預期：

- 標記一次性、替代支援、非穩定責任；
- `no-op`，不建立穩定 Task；
- 除非其他內容顯示這是正式備援責任，否則不繼續深挖。

### TI-R1-08：更正先前說法

先前：

> 我負責把版本部署到正式環境。

更正：

> 剛才說錯，我只做上線前測試；正式部署是維運負責。

預期：

- 新說法 supersede 舊 ownership；
- 舊「本人部署」不得繼續支持 Task；
- 既有候選需 edit／split／撤回；
- 不得在後續 context 讓錯誤責任復活。

---

## 12. 小型品質 Harness：不是平台，只是防止我們再次自我感覺良好

### 12.1 比較對象

#### Baseline

一次模型呼叫：

```text
員工內容 → Task candidates + 下一問
```

#### Candidate

兩次 bounded operations：

```text
turn.understand
→ deterministic validation/context projection
→ work.reconcile + consultation.decide
```

固定：

- 同一模型；
- 同一 provider／endpoint；
- 相近輸入資訊；
- 同一組 8 cases；
- 同一輸出目的；
- 不在比較時同時更換模型、Prompt 與案例。

### 12.2 第一輪執行量

> **【C-03 已修正｜分三階段，避免測試爆量也避免以 8 案冒充結論】**
>
> | 階段 | 規模 | 用途 |
> |---|---|---|
> | 1. 快速篩選 | 8 cases × 6 configurations × **1 trial** | **只淘汰明顯錯誤設計**，不得宣稱任何架構勝出 |
> | 2. 候選縮小 | shortlist 後才擴至 **20–30 cases** | 形成可討論的品質判斷 |
> | 3. Gate | 僅 shortlisted 架構的 **critical subset 跑 pass³** | 決定是否進 R2 |
>
> 六個 arm 的定義見
> [ADR 0040 決定 6](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)：
> **A1 = 最強模型 + 輕 schema + 一次呼叫 + minimal harness**（baseline，算在六個之內，不另計）；
> A2–A5 = 兩階段 + full harness 下的｛最強, 便宜｝×｛輕, 重 schema｝2×2；
> **A6 = 最強模型 + 輕 schema + 一次呼叫 + full harness**（**固定配置，不是 A2–A5 勝出配置**，
> 否則 A1 vs A6 會同時改動模型、schema 與 harness）。
>
> 每個比較只打開一個變因：**A1 vs A6** = harness bundle（minimal ↔ full）；**A2–A5 內部** = 模型 × schema；
> **A2 vs A6** = 架構（兩階段 ↔ 一次呼叫）。勝出配置下的一次／兩階段複驗移到 shortlist 或 shipping gate。
>
> 規模＝**48 個 case-arm trial observations**；生成器模型呼叫 **80 次**
> （單階段 2 × 8 = 16、兩階段 4 × 8 × 2 = 64），grader 呼叫另計。**不是每個 arm 都跑 pass³。**
>
> 原文保留於下，**不得據原文執行**。依據見
> [修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.3、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 11–12。

為避免測試拖慢成品：

1. ~~8 cases × baseline 1 次；~~ ←【C-03 已修正】
2. ~~8 cases × candidate 1 次；~~ ←【C-03 已修正】
3. ~~只對結果不穩或 critical 的案例補 1–2 次；~~ ←【C-03 已修正：改為 shortlisted 架構的 critical subset 跑 pass³】
4. 不一開始做大規模 Monte Carlo；
5. 不做跨十個模型排行榜。

這足以發現方向性錯誤，但不代表統計上證明產品品質。

### 12.3 評測欄位

#### 硬性 critical checks

- tool-as-task；
- step-as-task；
- past-work leakage；
- other-person leakage；
- one-off leakage；
- correction resurrection；
- unsupported Task；
- schema 逼迫產生 Task。

上述任一重大錯誤，不可用總分平均掩蓋。

#### 語意 rubric

- meaningful outcome 是否成立；
- Task 粒度是否過度拆分／合併；
- actor／time／typicality 是否忠實；
- 一故事多工作判斷；
- 多故事一工作判斷；
- evidence／source grounding；
- 不確定性是否誠實；
- `no-op／clarify` 是否在適當時使用；
- 下一問是否只問一件事；
- 下一問是否自然、不重複、不引導且能改變分析。

#### 診斷欄位

- 錯在 `turn.understand`；
- 錯在 `work.reconcile`；
- 錯在 context 缺失／污染；
- 錯在 schema 強迫；
- 錯在下一問；
- baseline 與 candidate pairwise preference。

### 12.4 Grader 策略

> **【2026-07-26 修訂 C-04｜評審者拆成三層】**
>
> 原文第 3 點「不讓同一模型自己判自己就是通過」方向正確但不夠。Anthropic 2026-03 的實測是
> 「agents tend to respond by confidently praising the work—**even when, to a human observer,
> the quality is obviously mediocre**」，其解法是**分離產生器與評審者、把評審者調成 skeptical、
> 每條標準給硬門檻**，且校準需數輪。**現行規定為三層，共用判準但不共用 prompt 與輸出目的：**
>
> 1. **Job Analysis Quality Rubric** —— 單一權威判準資產（Task 邊界、支持度、禁止錯誤、完成條件）。
> 2. **R1 Eval Grader** —— 開發期、盲測、可回 `Unknown`、**不讀產生器的 rationale**、按維度分開評分
>    （不要一個 judge 打全部）。
> 3. **R7 Product Challenger** —— 執行期產品元件，讀 Evidence／Current Work Model／JD，
>    **不讀產生器自我辯護**，只輸出 blocker／疑點／追問；不得宣布完成，不得修改正式文件。
>
> 注意：Anthropic 觀察到的是**執行期**行為，所以 R7 也必須繼承同樣的懷疑工程（乾淨 context、明確 rubric、
> 硬門檻），否則它在生產環境就是一台自誇機器。
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.4、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 14–17。

第一版使用：

1. deterministic checks：明確 actor／time／forbidden promotion；
2. owner／人工 rubric：Task 邊界與問題品質；
3. 必要時才用 model grader 作輔助，不讓同一模型自己判自己就是通過。

不需要：

- 複雜總分權重；
- 多個 reviewer agents；
- 自動 promotion gate；
- 大型 dashboard；
- 雲端 eval 平台。

### 12.5 通過標準

候選架構至少要：

- 8 個案例無 critical false promotion；【C-03：此為快速篩選門檻，非架構通過門檻】
- correction 不復活；
- 一故事多工作與多故事一工作沒有明顯過拆／過併；
- `no-op` 可正常成立；
- 每題只問一個主要問題；
- ~~相較 baseline，在 Task 邊界或錯誤可診斷性至少一項實質更好；~~
  ←【C-02 已修正：**Task 邊界品質不得退步為必要條件**，可診斷性只加分；且判準須在跑實驗前寫定。
  8 案例的結果只能淘汰明確錯誤設計，不能宣稱架構勝出 —— 見
  [修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.2、
  [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 9–11】
- 不出現足以抵銷改善的新 critical regression。

這不是正式產品 promotion，只是允許進入 R1 prototype 與 R2 多輪研究。

---

## 13. 固定模型與成本策略

### 13.1 R1 測試模型

依 owner 指示，第一輪固定使用 OpenRouter 的具名模型：

```text
openai/gpt-5.4-mini
```

[OpenRouter 官方模型頁](https://openrouter.ai/openai/gpt-5.4-mini/api)在本次研究時提供該 exact slug。
模型價格、端點與上游供應狀態可能變動，因此實驗前再取得一次官方 catalog snapshot；研究文件不把價格寫成永久規格。

### 13.2 ~~為什麼先固定一個便宜模型~~【已否決，見 C-01】

> **【2026-07-26 修訂 C-01｜本節整節已被否決】**
>
> 「同時比較多模型會讓錯誤難以歸因」的顧慮成立，但解法不是**先固定弱模型**，而是**先固定強模型**：
> 天花板未知時，任何架構結論都無法排除「模型能力不足」這個混淆因子。
> §13.1 的 exact slug 仍然要固定，但「固定哪一個」由 2×2 ablation 決定。
> 8 個案例 × 4 種配置的成本仍在個位數美元量級，成本不構成採用弱模型優先的理由。
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.1、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 5–8。
> 以下原文保留供追溯，**不得據原文執行**。

- 現在要驗證的是責任分工、Task rubric 與 context，而不是選模型冠軍；
- 同時比較多模型會讓錯誤難以歸因；
- 小 context、結構化輸出與少量 cases 可控制成本；
- 若 mini 模型在特定語意邊界持續失敗，再以一個較強模型做少量對照，判斷是架構問題還是能力上限。

### 13.3 可重現性

> **【2026-07-26 修訂 C-07｜Structured Output 契約，屬 R1 前提，不是附註】**
>
> OpenRouter 官方文件（ADR 0035 的 provider 主線）明載：
>
> > "Support is determined **per endpoint, not just per model**."
> > "**Enforcement varies by provider**: some guarantee schema-conforming output, while others
> > **translate your schema into their own structured-output format or treat it as a strong hint,
> > so exact compliance is not guaranteed on every endpoint.**"
> > "Strict modes may also **restrict which JSON Schema features you can use**."
>
> 因此**沒有任何 provider 端的 schema 保證是可攜的，包括 key ordering**。責任分工必須寫死：
>
> | Schema 負責 | Deterministic verifier 負責 |
> |---|---|
> | object／array／基本型別、required、nullable union（模擬 optional）、enum、`additionalProperties: false`、基本巢狀 | quote 非空與最小有效長度、至少一個 source anchor、陣列語意去重、數值範圍、source span 真實存在、ID／跨欄位引用合法、correction target 存在、Task 不得因 schema 必填被迫產生、actor／time／ownership 語意規則 |
>
> **執行要求**：固定 exact model slug **與 endpoint**、`require_parameters: true`、**禁 fallback**、
> R1 live preflight 實際送 portable schema、local verifier 永遠存在。
>
> **JSON Schema 容量上限不是架構常數**（OpenAI direct 與 Azure OpenAI 當期數字不同），由 resolved endpoint
> 決定；核心規格不寫死全域 property／nesting 上限，**以 live preflight 實測為準，文件只是預期值**。
> 帶日期的 provider 數字見[修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §7。
>
> 「先推理後格式化」**不靠 schema 欄位順序**（可見 rationale ≠ 內部推理、可能先合理化錯誤結論、
> 增加 token 與 schema 負擔）。依序採用：具原生 reasoning 能力的模型 → 減輕 schema →
> 避免 forced function calling → 最後才拆兩次呼叫。
>
> 依據：[修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.6、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 23–28。

- 使用 exact model slug，不用 `auto`、`free`、`latest` 等可變 alias；
- 記錄執行時 resolved model 與 provider endpoint；
- Prompt／schema／case 各有版本；
- 同一比較批次固定設定；
- 不使用 provider conversation state 當產品真相；
- 模型輸出只作 operation result，不直接成為正式 JD。

---

## 14. R1 的 Prompt、Context、Harness、Loop、Graph 對應

| 工程層 | R1 實際用途 | 現在不做 |
|---|---|---|
| Prompt Engineering | 為 `turn.understand` 與 `work.reconcile + decide` 寫單一責任、來源約束、Task rubric、少量 examples 與 structured output | mega-prompt、CoT 要求、一次產完整 JD |
| Context Engineering | 依 operation 提供最小高訊號 packet；保留原始片段、更正與 omission | 全 transcript、全公版、全 Work Model 每次重送 |
| Harness Engineering | 8 cases 快速篩選 → 20–30 cases → critical subset pass³；強模型 + 最小 harness baseline 對照、critical checks、盲測 grader、人工 rubric【C-03 修正；原文為「8 cases、baseline 對照、critical checks、人工 rubric、少量重跑」】 | 通用 eval 平台、大量測試排列、dashboard、正式 power analysis |
| Loop Engineering | 每輪只選 broaden／deepen／clarify 之一，問一個自然問題 | 長期 Planner、固定問卷、十題清單 |
| Graph Engineering | 保存 Message→Claim→Story／Work Unit→Task Candidate 的多對多來源關係；route 由普通 code 表達 | Graph database、LangGraph 類 runtime、N-agent graph |
| Structured Output | 讓 operation result 可驗證、允許 no-op／unknown／unmapped | 把 schema adherence 當語意正確 |
| Guardrails | 驗來源引用、actor/time/correction 狀態與禁止直接寫 JD | 用大量規則取代語意判斷 |
| Observability | 保存 prompt/version、必要 context、operation result、latency/cost 與案例判斷 | 全面 tracing 平台或產品級 audit |

---

## 15. 從顧問流程到 R1 的覆蓋

| 顧問流程責任 | R1 是否涵蓋 | R1 的實現 |
|---|---|---|
| 每輪完整理解，不漏跨焦點訊號 | 是 | `turn.understand` 掃描完整新回答，保留 unmapped |
| 短回答依當輪問題理解 | 是 | `QuestionContext` 的有限 grounding |
| 故事深挖 | 部分 | Story 語意與 `deepen_story`，完整 StoryFocus 留 R2 |
| 一故事多工作 | 是 | Story→0..N Work Units + split rubric |
| 多故事一工作 | 是 | `work.reconcile` 的 merge／edit |
| 工具、步驟不誤成工作 | 是 | Task 六項判準與 critical cases |
| 過去、他人、一次性不誤收 | 是 | claim qualifiers + critical cases |
| 更正舊說法 | 是 | supersede + effective facts |
| 彈性選下一問 | 最小涵蓋 | broaden／deepen／clarify |
| 完整職務廣度 | 否，R2 | R1 只有 minimal coverage gap |
| 角色假說 | 否，R2 | 不在 Task 邊界尚未證明前加入 |
| Duty、O/P/K/S/A | 否，R4 | 只保留線索，不產生正式內容 |
| Proposal／員工接受修改拒絕 | 否，R5 | R1 不改 Current JD |
| 公版 challenger | 否，R6 | 防止公版錨定 R1 |
| 完成反證 | 否，R7 | R1 不是完整 JD |
| 保存、退出、重開 | 否，R3 | R1 先驗證單輪核心品質 |

因此 R1 沒有假裝涵蓋整套顧問流程；它只完成最危險、且後續全部依賴的 Task boundary。

---

## 16. 實作前仍需 owner 討論的決策

### 決策一：Task 粒度

推薦：

> 以「角色層級、可指派／檢核、有 meaningful outcome 的穩定責任」為 Task；不以每個動作、工具、故事或操作步驟
> 建 Task。

**已確認（2026-08-03）**：採用此粒度作第一版權威；canonical 定義見 `apps/api/CONTEXT.md`。

### 決策二：~~兩次模型呼叫~~【C-01：降級為待實驗假說，由 ablation 裁決；持平時選一次呼叫】

推薦：

- Call 1：`turn.understand`；
- Call 2：`work.reconcile + consultation.decide`；
- 單次 end-to-end 作 baseline；
- 不做第三個 reviewer。

需要確認是否接受用少量額外成本換可診斷性。

### 決策三：低頻正式責任

推薦：

- 低頻不等於排除；
- 正式、現行、高影響且可預期再次承擔，可成 Task；
- 一次性幫忙預設不成 Task，除非證明是正式備援責任。

需要確認此產品語意。

### 決策四：第一批測試素材

推薦先使用本文 8 類小型合成案例；通過後，再加 2–3 個**未曝光於 Prompt 的片段**作 unseen check。
←【C-03 已修正；原文為「真實／匿名片段」。**owner 已裁定沒有真人員工訪談資料**，
unseen check 只能取自未用於調 prompt 的 constructed 或 human_manual_test 片段】

需要確認是否有現成失敗案例希望優先加入。總案例數在快速篩選階段保持少量（8），
鎖定架構前才擴至 20–30。

### 決策五：R1 到哪裡算完成

推薦：

> 輸出 Task Candidates、判斷依據與一個下一問即可；不建立正式 JD、不接公版、不做 O/P/K/S。

這能讓錯誤在最便宜階段被發現。

---

## 17. 研究後建議的下一步

### 17.1 先討論，不立即施工

Task 粒度與混合式職務發現已由 owner 確認；兩次模型呼叫不再是待確認的決策，而是待實驗的假說（C-01）：
由 R1 的 ablation 裁決，持平時選一次呼叫。開始施工前仍須用獨立 plan 寫定案例清單、實質改善門檻、成本上限與
停止條件；未有該 plan 前不實作 runtime。

### 17.2 確認後才寫 R1 實作計畫

實作計畫只需包含：

1. **兩種候選架構的最小輸入／輸出**：一次呼叫（單一 operation）與兩階段
   （`turn.understand` → `work.reconcile + decide`），兩者共用同一份 Task rubric；
   ←【C-01 已修正；原文為「兩個 operation 的最小輸入／輸出」，預設了兩階段】
2. 8 個快速篩選 fixture，**以及擴充到 20–30 cases 的路徑**（含 `case_family_id`／`source_type` 欄位）；
   ←【C-03 已修正；原文只有「8 個 fixture」】
3. **強模型 + 最小 harness 的單次 baseline**；←【W2／C-01 已修正；原文為「單次 baseline」，未指定模型與 harness】
4. 一個 CLI runner，**能跑 6 個 arm 的 ablation 矩陣並輸出 Trial Manifest**；
5. 簡單結果輸出、**盲測 grader** 與人工 rubric；←【C-04】
6. OpenRouter exact-model **與 exact endpoint** adapter 的最薄接線，含 `require_parameters: true`、
   禁 fallback 與 live preflight；←【C-07】
7. 成本上限與停止條件。

### 17.3 不可提早展開

- Web；
- 資料庫；
- 完整 Context Engine 平台；
- OPKS；
- 公版 retrieval；
- Graph runtime；
- 多 Agent；
- 產品級 Capture／observability；
- SaaS。

### 17.4 Stop／Rework

若兩階段方案：

- critical false promotion 不少於 baseline；
- correction 更容易復活；
- over-split／over-merge 更嚴重；
- 問題變得制式或不自然；
- 無法指出錯在理解還是 reconcile；
- 成本／延遲上升但品質無實質改善；

則停止進入 R2，先重畫 `turn.understand`／`work.reconcile` 邊界。不得用更完整 UI 或更多 Agent 掩蓋。

---

## 18. 最終研究裁決

R1 不應實作成：

```text
員工文字 → 抽取動詞／名詞 → 寫 Tasks
```

也不應實作成：

```text
Planner → 多個 Worker／Reviewer → Graph runtime → 看起來很專業
```

應實作成：

```text
原話與問題脈絡
  → 忠實理解 claims、qualifiers、corrections、unknowns
  → 保留原始證據與未映射內容
  → 從故事提出工作邊界假說
  → 跨故事 merge／split／edit／no-op／clarify
  → 形成可辯護但仍可修正的 Task Candidate
  → 問一個最能降低邊界不確定性的自然問題
```

這符合專業工作分析的核心，也符合 2026 現行大廠 LLM 工程的主流原則：

- 專業 rubric 先於 Agent 框架；
- structured output 保證形狀，不保證真相；
- operation-specific context；
- 簡單、可組合、可評測的 workflow；
- 每次模型判斷都有清楚責任；
- 以 task-specific eval 與人工校準否決錯誤方向；
- Graph 先表達關係與 route，不先引入 framework；
- 只在評測證明需要時增加模型呼叫、reviewer，或**為個別 operation 回補比 shipping 模型更強的模型**。
  ←【C-01 補充：品質天花板在 R1 第一步就用最強可用模型量過；此處指降本之後的回補，不是初次升級】

本文件目前仍是研究提案。第 16 節決策經 owner 確認後，才可進入 R1 implementation plan。
