# AI 專業職務分析顧問流程：最終反方審查與品質設計

> **【2026-08-01 現行裁決索引｜先讀這裡】**
> 本文提到的 **「K/S/A 支持度四級」（`behavior_grounded`／`employee_confirmed`／`reference_candidate`／`unsupported`）
> 已由 [ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md) 翻案**，
> 改為 `evidence_origin` × `task_linkage` 兩正交軸 ＋ `source_refs[]` 型別層非空。
> 原文保留供追溯，**不得據以施工**。
> OPKS 現行裁決 = **[0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)（概念）
> ＋ [0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)（實作形狀）
> ＋ [0050](../adr/0050-opks-proposal-minimal-shape.md)（Proposal 形狀）**，三份一起讀。


- 日期：2026-07-25
- 狀態：研究結論，供 owner 審核
- 產品範圍：伺服器部署、瀏覽器存取；員工與 AI 訪談、共同編輯並完成一份客製化職務說明書
- 本文處理：顧問怎麼訪談、分析、修正與判斷完成
- 本文不處理：SaaS、帳號密碼、多人權限、公司級治理、招募／訓練／考核模組、資料表或特定 LLM API
- 相關文件：
  - [專業職務分析與短回答架構研究](2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)
  - [LLM 架構反方審查與工作分析核心修正版](2026-07-24-interview-vnext-llm-architecture-red-team-and-corrected-work-analysis-design.md)
  - [Job Authoring v2 關聯式儲存研究](2026-07-24-job-authoring-v2-relational-storage-research.md)

---

> **【2026-07-26 修訂索引】** 本文件經外部紅隊複審後有兩處修訂：
>
> | 編號 | 位置 | 修訂 |
> |---|---|---|
> | C-01 | §11 第一優先 #6 | 「用便宜模型跑小批多 trial」**已修正**為先用最強可用模型建天花板，再以 ablation 檢查便宜模型 |
> | C-08 | §5.9 Step 7 | 補上 K/S/A 與 Indicator 的四級支持度，以可查核方式落實本文既有的「不評估員工個人熟練度」原則 |
>
> 依據見 [R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.1、§3.7、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)。

---

## 1. 最終結論

### 1.1 能不能保證「不會出差錯」

不能誠實保證任何單一員工訪談、任何 LLM 或任何顧問流程永遠零錯誤。員工可能忘記、概括、混入舊工作或同事工作；
模型可能被先前假設錨定；員工也可能為了快速結束而接受一段不夠精確的文字。

本文可以確認的是：

1. 修正後的流程沒有發現尚未處理的重大概念缺口；
2. 已知的高風險失敗，都有流程防線、可觀察訊號與測試方式；
3. 系統不靠一次抽取或一份公版決定工作，而是逐步形成、挑戰、修正工作模型；
4. 正式 JD 的修改仍由員工接受、修改或拒絕；
5. 在通過職務分析品質評測前，不以資料庫正確或 JSON 合法冒充顧問品質。

因此最終判斷是：

> **方向可採用，但必須使用「固定分析責任、彈性訪談路徑、持續全域理解、跨故事整併、反證檢查」的流程。**
> 不能退回固定問卷、單故事直出 Task、逐欄填表或公版套版。

### 1.2 成品能合理宣稱什麼

第一版可以產出：

> 根據員工目前實際工作、經過多輪訪談、交叉檢查及員工逐項審核形成的角色層級職務說明書。

它不能自動宣稱：

- 已代表整個公司對此職位的正式定義；
- 已由主管、HR 或外部專家核准；
- 已成為產業通用職能標準；
- 已證明該員工具備文件中的全部能力；
- 已完成 KPI、考核制度或法規效度驗證。

這不是降低產品價值，而是避免把「員工確認」誤稱為「外部真實性已驗證」。目前產品仍只做高品質 JD，不擴建上述模組。

---

## 2. 本次審查依據

### 2.1 專業工作分析

- 台灣 iCAP 的職能分析方法將訪談、專家會議、問卷與資料分析視為可組合的方法；BEI 使用具體事件與
  STAR 結構追問情境、任務、行動、結果，分析時再對事件整理、分類與編碼。
- iCAP 的職能基準結構包含主要職責、工作任務、工作產出、行為指標、知識、技能與態度；功能分析要求工作單元具有
  可以辨識的成果與相對完整性。
- 美國 OPM 將 job analysis 定義為系統性整理工作任務、職能及兩者 linkage 的過程，並建議結合現行職務資料與
  熟悉工作的 subject-matter experts。
- O*NET 的 Task 寫作準則把 Task 視為具有 meaningful outcome 的最小工作活動，基本文字為
  action + object，必要時再補 purpose、result、enabler 或 context；不是每個動詞、工具或操作步驟都應成為 Task。
- 工作分析研究已長期指出 self-presentation、社會影響、資訊處理限制與分析者判斷都可能造成偏差，故不能把一輪自述
  當作不需挑戰的真相。

### 2.2 2025–2026 LLM 訪談與評測

- Anthropic Interviewer 採 planning、adaptive interviewing、analysis 三段，訪談計畫兼顧共同研究目標與個別訪談的
  彈性；其公開案例仍保留人類研究者對計畫及分析的檢查。
- Anthropic 對 agent eval 的 2026 指引強調：對話型系統不能只評最終答案，也要評互動過程；需看 transcripts、
  使用多次 trials，並混合 deterministic、model-based 與人工 grader。
- OpenAI 的 eval 指引同樣主張先定義任務、測試資料與評分準則，再持續評測；結構化輸出只能保證輸出形狀，
  不能證明分析內容正確。

這些資料共同支持的不是「使用更多 Agent」，而是：

> 明確方法、受控上下文、結構化中間結果、可恢復狀態、人工決策與以真實失敗案例為中心的 eval。

---

## 3. Make the strongest case that this process was wrong

以下先假設目前流程會失敗，並替反方提出最強論證。若無法回答這些問題，就不應開始實作核心分析。

### 3.1 單一員工自述不足以代表一份職務

反方主張：

- 員工最容易記得最近、最痛苦或最有成就感的事情；
- 例行監控、等待、協調、判斷與預防性工作容易被忽略；
- 員工可能把偶爾幫忙、過去工作、理想工作或同事責任混入；
- 為顯得專業，可能過度強調工具、難度或個人貢獻；
- 不熟悉職務分析語言，因此「我做 Java」不等於他能說出真正的工作成果與責任。

若系統只是「問完就摘要」，最後得到的是個人回憶摘要，不是職務分析。

必要修正：

- 同一名員工也要使用多種 elicitation lens，而不是只問一次「你平常做什麼」；
- 至少涵蓋工作週期、最近故事、例外事件、低頻高影響工作、交接、例行隱性工作與責任邊界；
- 對重要結論做換句話說確認與反例追問；
- 正式內容以目前穩定職責為主，不自動納入一次性、他人、過去或理想內容。

### 3.2 一開始辨識職業，會產生分類錨定

反方主張：

如果系統先猜「這是後端工程師」，後續會傾向只問後端工程師應有的工作，忽略員工實際兼任的資料分析、客戶支援、
設備操作或流程管理。公版檢索若太早出現，模型還可能把訪談引導成公版已有內容。

必要修正：

- 一開始只形成 2–3 個暫定角色假說，不選唯一答案；
- 第一輪工作盤點採 blind-first，不把公版內容先餵給訪談模型；
- 假說必須保存支持、反例與尚未確認處，並可在任何一輪被改寫；
- 職業分類是搜尋與表頭候選，不是限制 Task 的容器。

### 3.3 故事訪談會過度代表「精彩事件」

反方主張：

BEI／STAR 擅長把模糊陳述變成可理解的行為，但使用者最容易講成功、失敗、緊急或特殊事件。若系統一路追故事，
JD 會充滿例外處理，漏掉占大部分時間的例行工作。

必要修正：

- 故事負責深度，工作週期掃描負責廣度；
- 每完成若干故事，回到日／週／月／年與責任區域檢查覆蓋；
- 低頻高影響工作與高頻例行工作分開判斷，頻率不等於重要性；
- 故事不能直接成為正式 Task，只能提供工作單元與證據。

### 3.4 Story、Event、Work Unit、Task 不是一對一

反方主張：

一個「上線新功能」故事可能包含需求釐清、程式開發、測試、部署與跨部門協調；其中有些是同一責任的步驟，有些是
獨立責任。另一個故事又可能重複同一個 Task。若一個故事固定建立一個 Task，會過度合併；若每個動詞建立一個 Task，
會過度切碎。

必要修正：

```text
一段回答
  -> 0..N 個故事／工作片段
  -> 0..N 個工作單元假說
  -> 與既有工作模型、其他故事交叉比較
  -> add / edit / merge / split / no-op / clarify
  -> 穩定後才提出 Task
```

「沒有新 Task」必須是正常且常見的分析結果。

### 3.5 工具、方法與工作會被混為一談

反方主張：

員工說「用 Java、HTML、Python、Excel、SAP」時，LLM 很容易產生五項工作。這會重演舊版最嚴重的品質問題：
技術名詞越多，Task 越多，但真正的責任可能只是「開發與維護系統功能」或「分析營運資料」。

必要修正：

- 工具名稱先視為 method/tool fact；
- 只有工具支援的 action + object + meaningful outcome + responsibility 都清楚時，才考慮形成 Task；
- 「操作設備」也不能一律排除：若操作本身具有獨立結果、責任與查核標準，仍可能是合法 Task；
- 工具可成為 Skill 的線索，但工具名稱本身不是完整 Skill；
- 所有 Task 提案都要通過工具升格檢查。

### 3.6 「從大到小」若變成硬階段，會丟失資訊

反方主張：

若系統規定先完成職位背景，再問 Task，再問 O/P，再問 K/S，員工在第一輪主動說出的產出、標準、技能或新工作可能
被忽略；後面分析 O/P 時又可能發現 Task 邊界錯了，但流程不允許回頭。

必要修正：

- 每輪先全域理解，再決定本輪主要焦點；
- 任何回答提到的 Task/O/P/K/S、工具、責任、否定、更正與不確定都要保留；
- 階段只是 dominant focus，不是資訊進入限制；
- Task、Output、Indicator、K/S 採雙向修正，不是單向 pipeline；
- 新資訊可重新開啟已暫時穩定的工作邊界。

### 3.7 長期保存上下文，也可能長期保存錯誤

反方主張：

「離開一天後繼續」若只保存一份壓縮摘要，摘要中的錯誤假設會成為下一次對話的前提。上下文越長，不代表越正確；
完整 transcript 全塞給模型則會造成注意力稀釋、舊資訊干擾與成本上升。

必要修正：

- 保存原始對話、目前正式 JD、工作模型、暫定假說、反證、未決問題與待審提案；
- 重新進入時由 Context Engine 依當前動作選取相關內容，不只讀一段 summary；
- 摘要是索引，不是事實權威；
- 更正、否定與 supersession 必須能壓過舊說法；
- 不保存或回放模型隱藏 chain-of-thought，只保存可檢查的事實、決定與簡短理由。

### 3.8 公版會讓「可能有」變成「員工真的有」

反方主張：

公版的詞彙通常專業、完整，模型很容易把它當答案。員工也可能因文字聽起來合理而接受，造成一份漂亮但不客製的 JD。

必要修正：

1. 先依員工內容建立工作模型；
2. 再檢索公版做 coverage challenge；
3. 每個候選標記 match、partial、no-match 或 conflict；
4. 沒有員工內容支持時，只能追問或顯示參考候選，不得自動寫入；
5. 公版沒有的實際 Task/K/S 可以建立本文件自訂項目；
6. 公版只保留來源 ID，不提高內容的事實等級。

### 3.9 員工按「接受」不等於內容一定正確

反方主張：

員工可能懶得修改、誤解文字、被專業措辭影響，或只檢查句子好不好看，未檢查它是否真的是穩定職責。

必要修正：

- AI 提案前先完成內部一致性與支持度檢查；
- 對影響大的 Task add/merge/split，使用白話差異與原因，不只顯示完成句；
- 重要 Task 在接受前後仍可被後續反證重新挑戰；
- 最終完成前進行一次 adversarial review，而不是把每次接受累加成不可質疑的真理；
- 員工接受決定「是否寫進他的 JD」，不宣稱完成外部效度驗證。

### 3.10 O/P/K/S 容易被模型補齊成漂亮但虛構的內容

反方主張：

- Output：不是所有服務或操作工作都有實體文件；
- Indicator：模型偏好發明「準確率 95%」「三天內完成」；
- Knowledge：容易寫成空泛的「熟悉相關知識」；
- Skill：容易把軟體名稱或人格特質當技能；
- K/S：容易從職稱或公版推定，而不是由實際 Task 需要導出。

必要修正：

- Output 可缺省，不能為填滿格式而發明；
- Indicator 描述 condition + observable behavior/result；沒有來源就不發明數值門檻；
- Knowledge 寫工作需要的原理、規則、概念或領域知識；
- Skill 寫能被觀察的應用、分析、操作、協調、判斷或解題能力；
- 每個 K/S 都要連回一個以上已確認 Task，並說明為何需要；
- 不從對話語氣推斷態度或人格；
- K/S 是職位要求，不是對員工個人熟練度的評分。

### 3.11 彈性流程可能變成沒有方法的自由聊天

反方主張：

如果只說「讓模型像顧問一樣彈性問」，模型可能被閒聊帶走、重複追問、漏掉例行工作，或每次模型版本更新後呈現完全
不同的訪談品質。

必要修正：

- 分析責任固定；
- 每輪只從有限的顧問動作中選擇下一個最有價值的動作；
- 應用程式維護 coverage、矛盾、未決與已拒絕項目；
- LLM 可選路徑與措辭，但不能自行發明新的流程狀態或跳過完成檢查；
- 以 interaction eval 檢查是否重複、引導、過長或失焦。

### 3.12 「文件有 Task」不是完成條件

反方主張：

只要有一項 Task 就允許結束，可能只記到一個故事；要求所有欄位都填滿，又會把訪談拖成表格盤問並製造虛構內容。

必要修正：

完成要同時看：

- 主要工作週期與責任區域是否已被掃描；
- 高重要性與低頻高影響工作是否有處理；
- 關鍵 Task 邊界是否穩定；
- 關鍵 O/P/K/S 是否已連回 Task；
- 是否還有會改變文件的重大矛盾或未知；
- 最後反方檢查是否通過；
- 員工是否選擇完成。

非關鍵選填欄位可以空白，不以填滿表格取代品質。

### 3.13 完整 Harness 仍可能證明錯的事情

反方主張：

即使 schema、hash、event、retry、provider、資料庫與 Capture 全部正確，也只能證明錯誤答案被可靠地保存。若 eval 沒有
「Java 不是 Task」「一個故事含多項工作」「同一 Task 跨多個故事」等案例，工程會持續優化錯誤目標。

必要修正：

- 把 Task 邊界、過度切分、過度合併、工具升格、其他角色誤收與無支持 O/P/K/S 設為核心品質 gate；
- 同時評最終 JD 與訪談過程；
- 多 trial，不以單次成功代表模型穩定；
- 定期人工閱讀 transcript 與提案差異；
- provider／prompt／context 變更都跑同一組 capability eval。

---

## 4. 反方審查後的保留、修正與否決

| 原設計觀念 | 裁決 | 原因 |
|---|---|---|
| 持久對話，可離開後繼續 | 保留 | 符合產品使用方式，但必須保存假說、反證與未決，不只 summary |
| 全域理解每輪輸入 | 保留並提高為硬規則 | 使用者不會照系統階段說話 |
| Evidence／事實與正式 JD 分開 | 保留概念 | 名稱與現有實作不是本文限制；核心是「談過」不等於「正式採用」 |
| 固定分析責任 | 保留 | 確保 coverage 與品質一致 |
| 固定直線訪談階段 | 否決 | 會漏掉跨焦點資訊，且無法因新資料回頭 |
| 故事式訪談 | 保留但限縮角色 | 故事負責深度，不能代替全職務盤點 |
| 一個故事直接建立一個 Task | 否決 | Story 與 Task 非一對一 |
| Task 後依序產 O/P/K/S | 改為雙向迭代 | O/P/K/S 也會揭露 Task 邊界問題 |
| 公版先決定職業與內容 | 否決 | 高度錨定，抹除客製工作 |
| 公版作後段 coverage challenger | 保留 | 補漏與改善語言，但不當事實來源 |
| AI 直接改正式 JD | 否決 | AI 只能提案，員工接受／修改／拒絕 |
| 員工接受即永久正確 | 否決 | 後續反證可重新提出修正 |
| 有一項 Task 即可完成 | 否決 | 不代表職務覆蓋 |
| 要求所有欄位填滿 | 否決 | 會延長訪談並誘發虛構 |
| 多 Agent／Graph framework 才專業 | 否決 | 專業性來自方法、狀態、context 與 eval，不來自角色數量 |

---

## 5. 修正後的專業顧問流程

### 5.1 流程總覽

```text
開啟／恢復一份 JD
  ↓
恢復正式文件 + 對話 + 工作模型 + 假說/反證 + 未決 + 待審提案
  ↓
Blind-first 角色定位（保留多個暫定假說）
  ↓
廣度盤點（目的、週期、責任區域、例行、例外、交接）
  ↓
┌──────────────────── 持續顧問循環 ────────────────────┐
│ 1. 全域理解本輪回答                                   │
│ 2. 更新事實、工作單元、角色假說、矛盾與 coverage      │
│ 3. 與所有既有 Task 候選／正式 Task 做跨故事比較       │
│ 4. 選擇下一個最高價值顧問動作                         │
│ 5. 追問，或提出 JD 修改                               │
│ 6. 員工接受／修改／拒絕；員工也可直接編輯             │
└───────────────────────────────────────────────────────┘
  ↓
公版 coverage/challenge pass
  ↓
全域整併與反方完整性檢查
  ↓
員工選擇完成
  ↓
高品質客製 JD
```

這不是固定 stage machine。系統可以在分析 Indicator 時發現新 Task，也可以在公版檢查時回頭問一個未確認工作。固定的是
每種資訊應如何判斷，不是問題必須依固定順序出現。

### 5.2 Step 0：開啟或恢復

恢復時至少需要知道：

- 現在正式 JD 的內容；
- 最近對話與必要的相關舊片段；
- 目前暫定角色／職業假說；
- 已確認、候選、合併、拒絕的工作；
- 每項結論的支持與反證；
- 工作週期與責任區域的 coverage；
- 尚未解決的高價值問題；
- 待員工處理的文件提案；
- 上次主要焦點與停止原因。

回來後不應重新開始問職稱，也不應只靠一段 AI 摘要重建真相。若上次停在待審提案，可先讓員工處理；若員工直接提出
新資訊，仍先理解新資訊。

第一版只保存已完成、可再次使用的狀態：

- 已完成的一輪員工訊息與 AI 回覆；
- 已形成的工作模型、coverage、未決問題與目前焦點；
- 已建立的 AI 提案，以及員工接受、修改、拒絕或待處理的結果；
- 目前正式 JD。

不做 token 級回覆續傳、回答到一半的恢復、半完成 LLM operation checkpoint 或為此建立複雜的 crash-recovery
workflow。使用者在一輪正常完成後離開，下次回來必須看到相同對話、提案、JD 與顧問進度；這些資料不能只放在
程序記憶體。

### 5.3 Step 1：Blind-first 角色定位

目標不是立即選定公版職業，而是建立暫定工作輪廓：

- 這份角色存在的主要目的；
- 服務對象／成果接收者；
- 主要責任範圍；
- 工作發生的環境與限制；
- 可能的 2–3 個角色／職業假說；
- 目前無法由職稱解釋的兼任工作。

一開始可以問：

- 「如果要讓一位新同事理解這份工作為什麼存在，你會怎麼說？」
- 「你主要要讓誰得到什麼結果？」
- 「最近一週／一個月，你花時間最多的是哪些責任？」

此階段可以保存員工主動提到的 O/P/K/S，但不急著逐欄追問。

### 5.4 Step 2：廣度工作地圖

不能只問「平常做什麼」。顧問用不同角度掃描：

1. 日常／每週工作；
2. 每月／每季／每年工作；
3. 低頻但出錯影響大的工作；
4. 例行監控、檢查、維護與預防；
5. 對外或跨部門交接；
6. 需要判斷、協調或核准的責任；
7. 緊急、例外與問題處理；
8. 最近新增、已不再做或只偶爾支援的事情。

員工若手邊已有職務說明、SOP、表單、報告範本、工作清單或實際產出，可以選擇拿來幫助回憶與交叉檢查；系統不應
要求一定上傳，也不能因文件看起來正式就把它當成員工目前實際工作的真相。

這一輪只需建立 coverage map 與工作候選，不需要把每一項都立刻寫成正式 Task。

### 5.5 Step 3：持續顧問循環

每一輪都執行五個分析責任。

#### A. 全域理解

辨識本輪是否包含：

- 新工作；
- 已知工作的補充；
- Output 或成果接收者；
- Indicator、條件或標準；
- Knowledge 或 Skill 線索；
- 工具、方法或操作步驟；
- 責任邊界、協作與交接；
- 頻率、重要性、典型性；
- 過去／現在／未來；
- 自己／共同／支援／他人；
- 否定、更正、不知道或不確定。

目前正在談 Output，不代表新 Task 可以被忽略。

#### B. 更新工作模型

系統先更新候選與關係，不急著修改 JD：

- 哪些工作單元可能屬於同一 Task；
- 哪些只是 substep、method 或 tool；
- 哪些與既有 Task 重複；
- 哪些是新責任；
- 哪些只有單一特殊事件支持；
- 哪些與之前說法衝突；
- 哪些已被員工否定或更正。

#### C. 跨故事整併

每次形成 Task 候選前，至少比較：

- 現有正式 Task；
- 尚未決定的 Task 候選；
- 相關故事與工作單元；
- 已合併、拒絕或拆分的歷史；
- 公版候選只在後段作對照。

允許的判斷：

- `add`：確實是新的穩定責任；
- `edit`：既有 Task 文字或邊界需修正；
- `merge`：多個候選共享同一 meaningful outcome；
- `split`：一條 Task 含兩個可獨立指派與查核的結果；
- `no-op`：只是補充、工具、方法、例子或既有 Task 的證據；
- `clarify`：資訊不足，先追問。

#### D. 選下一個最高價值動作

顧問只能從有限動作中選擇：

1. `broaden`：補工作週期或責任區域；
2. `deepen_story`：把模糊工作變成具體事件；
3. `clarify_boundary`：釐清 Task／步驟／工具／他人工作；
4. `validate_or_challenge`：確認理解、矛盾、典型性或反例；
5. `propose_document_change`：已有足夠支持，提出 JD 變更；
6. `review_completion`：coverage 足夠，進行結束檢查。

選擇原則是預期資訊價值，而不是固定欄位順序：

- 會改變 Task 邊界的問題優先；
- 會避免虛構或錯收的問題優先；
- 已可合理推導且風險低的 K/S 不逐項盤問；
- 重複追問的成本要計入；
- 一次只問一個主要問題，避免員工同時處理五個欄位。

#### E. 追問或提案

資訊不足時問自然問題；資訊足夠時提出一個可理解的修改。不要為了保持聊天節奏而每輪都提案。

### 5.6 Step 4：故事深挖

當員工只說「負責資料分析」時，可以追問最近一次具體案例：

- 當時為什麼需要做？
- 誰提出需求或誰會使用結果？
- 你先收到什麼輸入？
- 你實際做了哪些關鍵判斷或行動？
- 最後交付或造成什麼結果？
- 怎麼知道做得符合要求？
- 哪些是你負責，哪些是他人或共同完成？
- 這是常態、週期性、偶發，還是一次性？

應遵守：

- 一次處理一個事件；
- 按時間順序理解；
- 抽象答案要回到具體行為；
- 問題不可預設正確答案；
- 故事結束後仍要回到全職務 coverage。

### 5.7 Step 5：Task 邊界判斷

一個正式 Task 至少應有：

1. 明確 action；
2. 明確 object；
3. 有意義且可辨識的 outcome；
4. 屬於該角色目前的責任；
5. 不是只有工具名稱；
6. 不是單一操作步驟；
7. 不是只出現一次且無持續責任的事件；
8. 與既有 Task 的邊界可說明；
9. 可以被合理指派、說明或查核。

輔助判斷問題：

- 拿掉這個步驟，是否仍是在完成同一個結果？
- 這項工作能否被獨立交辦或檢查？
- 它是否有不同的主要接收者、目的或責任？
- 它在其他故事是否重複出現？
- 員工是否把它視為穩定責任，而非做法之一？

此 rubric 是判斷輔助，不是機械公式；模糊時應追問，不應硬分。

### 5.8 Step 6：主要職責（Duty）整併

主要職責不是先建立幾個大分類，再把後續 Task 硬塞進去。合理順序是：

1. 先形成一批邊界相對穩定的 Task；
2. 依共同 purpose、workflow stage、服務對象、責任領域或成果群組找出 Duty 候選；
3. 檢查每個 Duty 是否能用一句話解釋這組 Task 的共同責任；
4. 檢查是否有只有一項 Task 的空洞 Duty，或把不相干工作放在同一 Duty；
5. 將 Duty 與 Task 分組一起提案，由員工確認或調整。

角色定位初期可以有暫定責任區域，作為 coverage 導航；但正式 Duty 應在 Task 足夠穩定後才定稿。Task 新增、合併或拆分時，
Duty 也可以重新分組。

職務名稱、工作描述與公版分類欄位同樣在主要 Task/Duty 穩定後再提出候選，避免只靠最初職稱反向限制工作內容。

### 5.9 Step 7：O/P/K/S 漸進分析

> **【2026-07-26 修訂 C-08｜補上支持度記錄，強化本節既有原則】**
>
> 本節「不評估員工個人熟練度，只描述職位完成 Task 所需能力」的原則正確，但缺少可查核的記錄方式。
> 職務分析文獻（Morgeson, Delaney-Klinger, Mayfield, Ferrara & Campion, 2004, *JAP* 89(4), 674–686）的田野實驗
> 發現：**在職者對 ability 陳述的評分膨脹顯著高於 task 陳述**；在該研究的 clerical supervisor 與
> trained job analyst 補充樣本中，未重現 job incumbent 的一致 ability inflation 模式。
> 本產品只有一位在職者、沒有主管或分析師對照樣本，因此 K/S/A 是全份資料裡最脆弱的一格。
>
> **補充規定**：K／S／A 與 Indicator 數值門檻一律帶支持度 ——
> `behavior_grounded`（有 Task／故事／行為證據，可入正式 JD）／
> `employee_confirmed`（員工明確確認是**工作要求**而非自己會，可入但保留標記）／
> `reference_candidate`（只來自公版，僅作候選）／`unsupported`（模型推測，不得入正式 JD）。
> Attitude 一併適用。**員工按接受不得被記錄成已有行為證據。**
>
> 依據：[R1 紅隊複審與修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.7、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 29–32。

不是四個互不相干的生成工作，也不是一次整包生成。

```text
Task 初步穩定
  -> 檢查 Output／結果
  -> 檢查 Indicator／可觀察標準
  -> 從 Task + O + P 推導 K/S 候選
  -> 回頭檢查 K/S 或 O/P 是否揭露 Task 邊界錯誤
  -> 修正 Task 或提出 O/P/K/S 提案
```

#### Output

- 實體交付物、資料、紀錄、決策、服務結果或狀態改變皆可能是 Output；
- 不是每個 Task 都要有獨立實體 Output；
- 與 Task 的 meaningful outcome 不一致時，應先重查 Task 邊界。

#### Indicator

- 描述在什麼條件下，應有何可觀察行為或結果；
- 可涵蓋品質、完整性、時效、合規、溝通、風險控制；
- 員工未提供且公版也不能證明的數值，不得自行補上；
- 不把人格形容詞當行為指標。

#### Knowledge

- 完成 Task 所需的原理、規則、概念、程序或領域知識；
- 不寫「熟悉某知識」這種無內容句；
- 可由公版提供候選，但需與本 JD Task 建立理由清楚的 linkage。

#### Skill

- 描述實際應用、操作、分析、判斷、協調、溝通或解題能力；
- 「Python」是工具／技術名稱，「使用 Python 清理、驗證並分析資料以支持決策」才接近可用 Skill；
- 不評估員工個人熟練度，只描述職位完成 Task 所需能力。

### 5.10 Step 8：公版 coverage challenge

在已有員工工作模型後才使用公版：

1. 依角色假說與已確認 Task 檢索候選；
2. 比較是否漏掉常見責任、Output、Indicator 或 K/S；
3. 對候選判定：
   - `match`：與員工工作及 Task 支持一致；
   - `partial`：只有一部分適用；
   - `no-match`：不屬於這份工作；
   - `conflict`：與員工內容或責任邊界矛盾；
4. `partial/no-match/conflict` 不自動寫入；
5. 缺少支持但可能重要時，以非引導問題確認；
6. 公版查無內容時，允許建立本 JD 的自訂 Task/K/S。

### 5.11 Step 9：文件共編

AI 對正式文件只能提出：

- 新增；
- 修改；
- 合併；
- 拆分；
- 刪除。

員工可以：

- 接受；
- 修改後接受；
- 拒絕；
- 暫不處理；
- 直接編輯正式 JD。

提案顯示應包含：

- 會改哪一部分；
- 修改前與修改後；
- 一句白話原因；
- 需要時顯示它依據哪些訪談內容或公版候選；
- 合併／拆分時說明邊界變化。

不需要把複雜 provenance 或技術 ID 暴露給員工。

### 5.12 Step 10：最終反方完整性檢查

AI 在建議完成前，刻意嘗試證明目前 JD 是錯的：

1. 是否被一個精彩故事主導？
2. 是否漏掉高頻例行或低頻高影響工作？
3. 是否把工具、方法或步驟升格成 Task？
4. 是否把同事、過去或一次性工作寫進來？
5. 是否有 Task 過度合併或過度切碎？
6. 是否有重複 Task？
7. 每項關鍵 Output/Indicator/K/S 是否確實連到 Task？
8. 是否發明數字、標準、Output 或能力？
9. 是否因公版而加入員工未做的內容？
10. 是否仍有會顯著改變文件的矛盾或未知？

若發現高影響問題，回到顧問循環；不是強迫員工完成。

### 5.13 Step 11：完成

系統可以建議完成，但員工決定是否完成。合理條件是：

- 角色目的與主要責任可解釋；
- 日／週／月／年或適用工作週期已做廣度掃描；
- 關鍵與高影響工作已有穩定 Task 邊界；
- 關鍵 Task 的 O/P/K/S 已達到可用程度；
- 無未解決的重大矛盾；
- 反方完整性檢查通過；
- 員工審核文件並選擇完成。

允許：

- 非關鍵欄位空白；
- 稍後重新開啟繼續修改；
- 新資訊出現後重新開啟已完成文件。

---

## 6. Context Engineering 在顧問流程中的責任

本文不鎖定資料庫表或現有 Evidence 類別，但 Context Engine 必須提供以下語意。

### 6.1 不同動作拿不同 context

| 顧問動作 | 必要 context | 不應預設加入 |
|---|---|---|
| 理解短回答 | 問題、問題目標、員工回答、最近必要上下文 | 全份公版、全部歷史 |
| 故事深挖 | 該故事 bounded transcript、相關事實、目前工作單元 | 無關故事 |
| Task 邊界 | 相關故事／工作單元、所有相近 Task、拒絕／合併歷史 | 全庫公版 |
| 下一題選擇 | coverage、矛盾、未決、訪談負擔、正式 JD 摘要 | 所有原文 |
| O/P/K/S 分析 | 已確認 Task、相關故事、現有 O/P/K/S、必要公版候選 | 無關職位內容 |
| 最終整併 | 完整 JD 摘要、coverage、重大支持／反證、未決 | 每輪完整 transcript |

### 6.2 Context 的事實層級

Context 應區分：

- 員工明確陳述；
- 問題＋短答共同形成的內容；
- AI 工作假說；
- 員工已接受的正式文件內容；
- 員工拒絕、否定或更正的內容；
- 公版參考；
- 尚未解決的矛盾。

不能把以上內容壓成同一種「已知事實」。

### 6.3 防止遺忘與偏差累積

- 所有輸入先全域分類，再選本輪主要處理項；
- 舊說法被更正後，未來 context 應優先呈現新說法與更正關係；
- 保存多個角色／Task 假說，不只保留目前排名第一者；
- summary 不得覆蓋原始來源；
- context 裁切要保留「還有多少未載入內容」的訊號，避免模型誤以為沒有其他工作；
- 公版 context 與員工內容分區，避免來源混淆。

---

## 7. 顧問問題品質規則

### 7.1 應該

- 一次一個主要問題；
- 先開放敘述，再針對高價值缺口追問；
- 要求具體例子時說明原因；
- 使用員工原本的詞彙，不急著套專業術語；
- 對模糊概括回到最近真實事件；
- 對重大理解使用中性摘要確認；
- 可根據員工回答改變路徑；
- 避免重問已知內容；
- 允許「不知道、不適用、想不起來」。

### 7.2 不應該

- 「你是不是也負責……」式引導問題；
- 一次列五個欄位要求逐項回答；
- 為補滿公版一直追問低價值欄位；
- 員工說工具名稱後立即問「這項工作的產出是什麼」並預設它是 Task；
- 把員工的「偶爾幫忙」重寫成「負責」；
- 因員工接受一段文字，就停止檢查後續矛盾；
- 每輪都強迫產生文件提案；
- 為展示 AI 專業而使用員工看不懂的職務分析術語。

---

## 8. 失敗模式與防線

| 失敗模式 | 流程防線 | 如何測 |
|---|---|---|
| 職稱錨定 | blind-first、多假說、可推翻 | 模糊職稱但混合職責案例 |
| 只記精彩故事 | 週期 coverage + 例行／低頻高影響掃描 | 一個特殊事件掩蓋例行工作的案例 |
| 一故事一 Task | Work Unit + 跨故事 synthesis | 一故事 3 工作、3 故事 1 工作 |
| 工具升格 | Task boundary gate | Java/Python/HTML/Excel negative cases |
| 子步驟膨脹 | meaningful outcome + 獨立責任判斷 | 收集→清理→分析→報告是否拆分 |
| 過度合併 | outcome/recipient/responsibility 比較 | 一段回答含可獨立交辦的兩項責任 |
| 收入他人工作 | ownership/handoff 追問 | 「交給前端」「協助會計」案例 |
| 收入過去工作 | time-scope 檢查 | 「以前負責，現在沒有」案例 |
| 收入一次性工作 | typicality/recurrence 檢查 | 臨時活動、專案救火案例 |
| 公版抄寫 | blind-first + match/partial/no-match/conflict | 公版與員工實際內容不符 |
| 虛構 Output | Output 可空 | 純服務／監控工作 |
| 虛構門檻 | 禁無來源數值 | 無時限回答不得出現 95%/三日 |
| K/S 過度推定 | Task linkage + 白話理由 | 職稱常見但本工作不需要的能力 |
| 接受造成永久偏差 | 後續反證可重開 + final challenge | 先接受、後更正案例 |
| 離開後失憶 | persistent state + action-specific context | 隔多輪／重新載入後續談 |
| summary 保存錯誤 | 原始來源與更正優先 | 舊摘要與新明確否定衝突 |
| 訪談過長 | 資訊價值／負擔排序、可空欄位 | 短答與高 coverage 情境 |
| 太早完成 | coverage + stability + contradiction gate | 只有一項 Task 時不可建議完成 |

---

## 9. 最小但有效的品質驗收

目前不需要建立龐大測試平台，但開始核心流程前至少要有一組能直接證明工作分析品質的案例。

### 9.1 第一批 16 類 capability cases

1. 工具名稱不是 Task；
2. 工具操作有獨立結果時可以是 Task；
3. 一個故事包含多個工作；
4. 多個故事支持同一工作；
5. 多個步驟共享同一 outcome，不應過度切分；
6. 同一回答含兩個獨立 outcome，不能過度合併；
7. 一次性工作；
8. 過去工作；
9. 他人工作與交接；
10. 員工更正先前說法；
11. 純服務／監控 Task 無實體 Output；
12. 沒有數值來源，不得發明 Indicator 門檻；
13. 公版候選不適用；
14. 公版沒有但員工確實在做；
15. 高頻例行工作被精彩故事掩蓋；
16. 離開並恢復後，繼續正確焦點且不重問。

每類應同時有「應建立／應修正」與「不應建立／不應改」的對照，避免只測 trigger cases。

### 9.2 評分層次

#### 層一：確定性檢查

- 是否產生 schema 合法結果；
- 是否出現禁止的無來源數值；
- 是否把明確過去／他人／否定內容寫入；
- 是否保持 AI 提案、員工決定；
- 是否在恢復後重複已回答問題。

#### 層二：職務分析 rubric

- Task boundary precision／recall；
- 過度切分與過度合併；
- duplicate Task；
- tool/substep promotion；
- meaningful outcome 與 responsibility 是否清楚；
- O/P/K/S 是否被 Task 支持；
- JD 是否覆蓋主要責任與工作週期；
- 公版是否只作參考；
- 最終文字是否具體、可理解、可供後續使用。

#### 層三：互動品質

- 問題是否自然、單一且不引導；
- 是否抓到使用者主動提供的跨焦點資訊；
- 是否選擇高資訊價值問題；
- 是否過度追問；
- 是否會承認不確定並尋求澄清；
- 員工是否容易理解提案差異。

### 9.3 執行方式

- 每個關鍵案例跑多次，避免單次運氣；
- 同時保存最終 JD 與完整互動軌跡供審查；
- deterministic grader 負責明確禁令；
- rubric model grader 負責語意品質；
- owner／專業人士定期盲審少量案例，校準 rubric；
- 模型、prompt、context 或流程改動後跑同一組案例；
- 先比較現行流程與修正版流程，再決定是否進 production。

原型不要求全面覆蓋。第一個 gate 應先做到：

- 所有 critical negative cases 不得把工具、他人、過去或一次性內容錯寫為穩定 Task；
- 不得發明數字門檻；
- correction 必須能修正文件與後續 context；
- 一故事多工作與多故事一工作都能得到正確邊界；
- final JD 能覆蓋案例的關鍵責任；
- 人工閱讀未發現系統性引導、重複或失焦。

---

## 10. 架構邊界：現在不要做什麼

為了讓第一個高品質成品更快出現，本流程不要求：

- SaaS、organization、tenant administration、帳號、登入、計費；
- 多人共編、主管核准流程或公司級職能 catalog；
- 招募、訓練、考核、稽核或 KPI 模組；
- Graph database；
- 多 Agent framework；
- 把所有 reasoning、hash 或來源細節顯示給員工；
- 一開始就覆蓋所有職業與所有公版格式；
- 為每個欄位建立複雜 provenance UI；
- 在職務分析核心尚未通過 eval 前擴建非核心 infrastructure。

仍需保留：

- 文件保存與重新開啟；
- 已完成對話與顧問狀態的延續；
- AI 提案、員工接受／修改／拒絕；
- 員工直接編輯；
- 正式 JD 與訪談／工作假說分離；
- 公版最小來源 ID；
- 直接保護文件真實性與決策正確性的必要交易安全。

第一版明確不做回答中途恢復、token checkpoint 或半輪工作續跑；這些能力不直接提升 JD 與訪談品質。

---

## 11. 最終推薦的實作優先順序

### 第一優先：證明 Task 分析方向正確

先完成：

1. 16 類精簡 capability cases；
2. bounded story/work-unit 表示；
3. Task boundary rubric；
4. 跨故事 add/edit/merge/split/no-op/clarify；
5. 持續 coverage 與反證；
6. **先用最強可用模型**跑小批多 trial 建立品質天花板，再以 ablation 檢查便宜模型是否夠用；人工讀 transcript。
   ←【C-01 已修正；原文為「用便宜模型跑小批多 trial」。理由見
   [修訂裁決](2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) §3.1】

這一步比先完成全部 K/S、公版匯出或新基礎設施重要。

### 第二優先：打通員工可見垂直流程

```text
員工輸入
  -> 顧問理解與追問
  -> 工作模型更新
  -> AI 提出 Task/O/P 的文件修改
  -> 員工接受／修改／拒絕
  -> 保存
  -> 離開後重新開啟並繼續
```

先讓一份小型 JD 真正可用，再擴大內容。

### 第三優先：K/S 與公版 challenge

Task/O/P 品質穩定後：

- 由確認 Task + O/P 產 K/S 候選；
- 建立 Task linkage；
- 接公版 retrieval 作 coverage challenge；
- 公版查無時保留 document-local custom item。

### 第四優先：完成檢查與匯出

- adversarial completion review；
- JD 品質檢查；
- 一般 JD 與政府公版格式 projection；
- 小規模員工試用與專業審查。

---

## 12. 最終決策

### 12.1 通過的顧問流程原則

1. **固定分析責任，彈性訪談路徑。**
2. **每輪全域理解，不因目前焦點漏掉其他資訊。**
3. **角色分類保留多假說，公版延後介入。**
4. **故事給深度，工作週期給廣度。**
5. **Story/Work Unit/Task 非一對一，Task 必須跨故事整併。**
6. **工具、方法、步驟預設不升格，但依 meaningful outcome 與責任判斷，不採死規則。**
7. **O/P/K/S 漸進、雙向修正，不是固定流水線。**
8. **AI 只提案，員工決定文件；員工接受不等於免除最後反方檢查。**
9. **公版是 challenger，不是 truth 或 allow-list。**
10. **完成由 coverage、穩定性、矛盾與員工決定共同判定。**
11. **Context 保存來源、假說、反證與未決，不保存單一不可質疑摘要。**
12. **以職務分析品質 eval 為核心 gate，不以工程正確性代替內容品質。**

### 12.2 是否還有必須先解決的概念問題

在本文產品範圍內，沒有發現需要再次推翻整體方向的重大概念問題。剩餘不確定性應用小型 capability eval 和真實員工
試用解決，而不是再擴大抽象架構。

下一步不應再繼續討論資料表、SaaS 或完整平台；應先把上述 16 類案例與最小顧問循環做成可比較的測試品。若結果顯示
Task 邊界仍不穩，再調整 prompt、context、分析 rubric 或 loop policy，而不是先擴建功能。

---

## 13. 權威來源

### 台灣職能基準與訪談方法

- 勞動力發展署 iCAP，
  [職能相關概念](https://icap.wda.gov.tw/ap/knowledge_introduction.php)。
- 勞動力發展署 iCAP，
  [職能基準發展指引](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download)。
- 勞動力發展署 iCAP，
  [行為事例訪談法（BEI）](https://icap.wda.gov.tw/File/Knowledge/Method/2-04.pdf)。
- 勞動力發展署 iCAP，
  [職能基準品質規範](https://icap.wda.gov.tw/Quality/quality_specification.aspx)。

### 工作分析與 Task 寫作

- U.S. Office of Personnel Management，
  [Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)。
- U.S. Office of Personnel Management，
  [Delegated Examining Operations Handbook](https://www.opm.gov/policy-data-oversight/hiring-information/competitive-hiring/deo_handbook/)。
- U.S. Office of Personnel Management，
  [Job Analysis FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/)。
- O*NET Resource Center，
  [Data Collection Program](https://www.onetcenter.org/dataCollection.html)。
- O*NET Resource Center，
  [Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf)。
- O*NET Resource Center，
  [Content Model](https://www.onetcenter.org/content.html)。
- O*NET 30.0 Data Dictionary，
  [Task Statements](https://www.onetcenter.org/dictionary/30.0/text/task_statements.html)。

### 工作分析偏差與 competency modeling

- Morgeson & Campion，
  [Social and cognitive sources of potential inaccuracy in job analysis](https://www.morgeson.com/downloads/morgeson_campion_1997.pdf)。
- Morgeson et al.，
  [Self-presentation processes in job analysis: a field experiment](https://pubmed.ncbi.nlm.nih.gov/15327353/)。
- Campion et al.，
  [Doing competencies well: Best practices in competency modeling](https://onlinelibrary.wiley.com/doi/pdf/10.1111/j.1744-6570.2010.01207.x)。
- Society for Industrial and Organizational Psychology，
  [Competency Modeling Documentation](https://siop.org/wp-content/uploads/2025/01/CompMod.pdf)。

### LLM 訪談、Context 與評測

- Anthropic，2025-12-04，
  [Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)。
- Anthropic，2026，
  [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)。
- OpenAI，
  [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)。
- OpenAI，
  [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。
