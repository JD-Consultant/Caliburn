# Task 邊界、merge/split 與同一性判準研究

> **【2026-08-01 更新】** 本文提到的 `Task.deliverable_hint` 與 `Task.success_criterion_hint`
> **將由 [ADR 0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md) 決定 15
> 在 OPKS 上線時退役**（與正式 O/P 語意重疊，留著必成兩份真相）。目前 production 無寫入路徑。


- 日期：2026-07-28
- 狀態：Proposed；供 ADR 0042 與 Production Task Analysis v1 契約引用
- 觸發：[R1a 結果](../experiments/2026-07-27-r1-task-discovery/r1a-results.md) §4「不能宣稱」——
  `TI-R1-03`／`TI-R1-04` 顯示 merge/split 仍是核心缺口；owner 2026-07-27 裁定停止付費架構實驗，
  改以權威研究收斂判準
- 相關：[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)（Task rubric 為單一權威判準資產）、
  [ADR 0041](../adr/0041-r1-p0-closure-first-version-context-and-holdout.md)（凍結期望不得為配合模型輸出改寫）、
  [R1 深入研究 §4–5](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)

## 1. 要回答的三個問題

R1a 之後，**能靠研究推進的**是三個判準問題。R1a 用的已是最強模型且 `TI-R1-03`／`04` 仍失敗，
因此**不得推論「模型能力不是原因」**；判準寫清楚之後模型是否遵守，第一版沒有實驗可回答（ADR 0042 決定 8）。

1. **粒度**：什麼算一個 Task？何時是步驟、工具或工作活動？
2. **同一性**：新回答裡的敘述，是既有 Task 的換句話說、補充，還是新工作？
3. **merge/split**：什麼條件觸發合併或拆分？輸出要長什麼樣才能可診斷（不是可自動判定）？

第 2 題是實作 blocker：沒有同一性判準，`revise` 保留哪個 Task、`merge` 合併哪幾個、
`split` 從哪裡拆出來、`withdraw` 撤回哪一項，都無法表達。

## 2. 來源

| 來源 | 性質 |
|---|---|
| [O\*NET Task Writing Guidelines（Appendix B）](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf) | 美國勞工部 O\*NET 中心的 task statement 撰寫規範 |
| [Identification of Emerging Tasks in the O\*NET System: A Revised Approach（2025 No. 021，2025-02-25）](https://www.onetcenter.org/reports/EmergingTasks_RevisedApproach.html) | **現行**官方程序；duplicate／overlap 判準的第一來源（§3.5） |
| [Adding Drone-Specific Tasks to the O\*NET Database: Initial Identification of Emerging Tasks using ChatGPT](https://www.onetcenter.org/dl_files/Drone_Tasks.pdf) | 官方以 LLM 產生候選、再由分析師審查的實作紀錄 |
| [Summary of Procedures for O\*NET Task Updating and New Task Generation（Dierdorff & Norton, 2011）](https://www.onetcenter.org/dl_files/TaskUpdating.pdf) | **歷史機制補充**；Task Joining／Separation 等編輯階段程序（§3.4），2025 文件未涵蓋同一階段 |
| 同上 Appendix：A Primer on Preparing O\*NET Occupational Task Statements（Cunningham） | task statement 結構的原始教材；引用 Fine & Getkate (1995) 與 DOL《Revised Handbook for Analyzing Jobs》(1991) |
| [職能基準發展指引（勞動部勞動力發展署／工研院）](https://icap.wda.gov.tw/ap/knowledge_introduction.php) | 本產品匯出版型的官方定義（主要職責／工作任務／工作產出／行為指標） |
| [DACUM Occupational Analysis（Eastern Kentucky University）](https://www.eku.edu/in/guides/dacum-occupational-analysis/) | duty／task 兩層與 task 的操作型定義 |

## 3. 權威證據

### 3.1 Task 的單位定義

O\*NET Appendix B 開宗明義：

> Tasks are typically conceptualized as **the smallest unit of activity with a meaningful outcome**.

同頁引 Cunningham (2000)：

> Task writing requires considerable individual judgment. It is an art, and no two writers will
> produce exactly the same results. It is essential, however, that writers follow common guidelines
> in order to maintain some uniformity of task-statement structure.

**這句話限定了本研究能交付什麼**：可交付一致的判準與寫法，不能交付唯一正解。

DACUM 的操作型定義補上可觀察性：task 是「有明確起訖、可觀察、包含兩個以上步驟、
產生產品／服務／決策的工作活動」；duty 是「持續性的能力領域，內含兩個以上 task」。

### 3.2 結構：工具屬於 Enabler，不是 Task

O\*NET 的 task statement 固定結構為：

```text
Action (Behavior) → Object of the Action → Purpose/Result
                                            + Enabler、Context
```

其中 **Enabler** 明確涵蓋：machines、tools、equipment、work aids、sources of information、
methods used、**knowledge and skill drawn upon**、nature of the instructions followed。

也就是說「Java／Python／HTML」在權威規範裡有指定的欄位——它們是 enabler 片語
（`using` / `based on` / `following` 引導），**工具名稱本身不構成 task statement**。
`TI-R1-01` 的期望因此有官方依據，不是我們的偏好。

反面同樣重要：**含有工具的工作可以是 Task**。`TI-R1-02` 是八案中唯一的正向案例——
「開發與維護訂單處理服務，以支援門市交易資料正確傳送至 ERP」成立，Java／Python 落在 enabler。
判準管的是「工具名稱不能當 action+object+purpose」，不是「提到工具就不建 Task」。
ADR 0041 決定 14 已明文警告後者會把 prompt 推向單邊最佳化。

### 3.3 何時拆：多個 action + 多個 purpose

Appendix B：

> Generally, it is best **not to write complex, compound task statements involving multiple action
> and purpose components**. When task statements are too complex, consider writing multiple task
> statements, rather than a single comprehensive statement.

風格規則給了一個機械訊號：

> Do not use semicolons. **A semicolon implies that there are two distinct tasks in one statement.**

另一條反向規則值得注意——O\*NET 偏好 `or` 甚於 `and`：

> When "and" is used, job incumbents may believe they need to do every aspect of the task to
> endorse it. "Or" is more inclusive.

注意條件是「multiple action **and** purpose components」，**不是「多個動詞」**。
多個動作共享同一 purpose/result 時，是一個 task。

### 3.4 何時併：Task Joining 與 TEWA roll-up

O\*NET Task Updating 的 Type I 編輯分四層，直接對應我們要的四個動作：

| O\*NET 階段 | 定義 | 對應我們的動作 |
|---|---|---|
| Task Deletion | 消除 incomplete、redundant、useless、irrelevant、contradictory 的 task | `withdraw` / `no_change` |
| Task Separation | 拆開「含太多資訊、內容太變異以致無法寫成一句簡潔可解釋的通則敘述」的 task | `split` |
| Task Joining | 合併「彼此太相似而無法各自獨立成立」的 task，**並把 support task 與 TEWA（tools, equipment, work aids）task roll-up 成單一敘述** | `merge` |
| Final Review | 分類 **Core Tasks**（多數在職者都會做）與 **Periphery Tasks**（含 support task） | 不是 include／exclude，而是分層 |

Task Sorting 階段定義了「什麼算同一群」：

> A cluster represents a grouping of task information that **shares a meaningful interrelationship,
> such as a common action or purpose**.

而 Task Writing 階段明示**偏向合併**：

> Emphasis is placed on writing **as few summary tasks as possible** for a given cluster – a single
> task is preferable, but up to five summary tasks are allowed.

### 3.5 同一性：現行（2025-02-25）官方判準

**第一來源是 2025 年的 Revised Approach**，其 Step 3 把每筆新陳述對既有 task 分成兩類：

> A **duplicate** is defined as a write-in statement that is **conceptually redundant with or fully
> encompassed by** one of the published tasks. Write-in statements deemed to be duplicates are not
> considered for further review and are discarded from the evaluation process.

> **Overlap** in this context refers to situations where a write-in statement shares significant
> conceptual similarity with a task in the published list, but **provides additional details or nuance
> not captured** in the original task description. In such cases, the overlapping write-in statement is
> retained for further review, **with the aim of potentially revising the corresponding published task**.

同一份文件明說它與舊術語的關係：

> These judgment criteria differ slightly from those used in prior evaluation cycles. Previously,
> analysts used categories such as "completely redundant," "partially redundant," and "unique"…
> Although the terminology has changed, **the underlying concepts and intent remain the same**.

因此 2011 版的 duplicative／unique／overlapping 三分類仍然可引，但**只作歷史補充**，
現行判準以 2025 版為準。

流程上，NLP 先產生 pre-populated 判斷與 cosine similarity，**分析師再審查與調整**——
機器提候選、人做裁決，與本產品的 verifier ＋ rubric ＋ 員工決定同構。

> **本產品刻意的分歧**：O\*NET 對 `duplicate` 的處置是 **discard**；本產品是
> `support_only`（追加 SupportLink）。原因是 O\*NET 在建職業層級的 task 清單，
> 我們必須能回答「這個 Task 憑什麼有這些依據」。這是有理由的分歧，不是引用錯誤。

> **不可移植的部分**：2025 版 Step 4 規定「兩位以上專家或在職者的重疊陳述才建立或修訂 task」。
> 那是跨受訪者的**共識門檻**，本產品是單一員工的客製 JD，沒有這個分布，不得移植。

### 3.6 iCAP：粒度必須對得上工作產出與行為指標

《職能基準發展指引》規定工作內涵的分層與欄位：

> 依據該職業（類）之主要工作進行分析，分層展開主要職責、工作任務、工作活動
> （視工作複雜度決定分層數，**建議以主要職責、工作任務 2 層為主**）。

> **工作產出**：指執行某任務最主要的關鍵工作產出……儘量以書、文件、圖表等有形交付標的為主，
> 若該項任務僅有行動或操作性質之工作成果，則不必列出工作產出，建議將相關成果列於行為指標之描述中。

> **行為指標**：用以評估是否成功完成工作任務之標準。需具體描述在何種任務情境下，有哪些應有的行為或產出。

因為本產品的匯出版型就是 iCAP，這一條是**最硬的粒度尺**：
一個「工作任務」必須能對應到自己的關鍵工作產出或自己的成功判準；對不上的，是工作活動（步驟），不是工作任務。

> 查證註記：外界常引「一份職能基準約 5–10 項工作任務」。**本指引（2022 版）正文查無此數字**，
> 只有「建議 2 層為主」。這只代表本文件未見，不代表其他官方文件沒有；要引用須指出實際出處，
> 不得逕稱為官方規定。

## 4. 由證據導出的第一版判準

### 4.1 Task 成立條件（取代含糊的六項檢查敘述）

一個 Task 候選成立，必須同時滿足：

1. 可寫成 `action + object (+ purpose/result)` 的單句，不需要分號；
2. 所有動作**共享同一個 purpose/result**；
3. 有**可理解的 meaningful outcome**——可以明寫在 purpose/result、關鍵工作產出或成功判準，
   也可以合理隱含於 action＋object（O\*NET 的 "Mops, sweeps, and dusts halls and corridors"）；
4. 是本人目前的責任（actor／time 由 Source 判定，不在本研究範圍）。

`purpose/result` **欄位可以為空**——O\*NET 明示它常常是隱含的（"Mops, sweeps, and dusts halls
and corridors" 的 result 隱含在 action＋object）。成立條件要求的是「目的說得出來」，
**不是欄位非空**；前者是語意判斷，後者才是 verifier 能查的。

**不得用「三個欄位皆空」作結構性否決**——是否具備可理解的 outcome 由 rubric 判斷。
確實判不出 outcome 時 → `clarify`，不先建 Task。不滿足 1–2 時 → 觸發 split 檢查。

### 4.2 Enabler 硬規則

工具、程式語言、系統、方法、知識、技能一律進 enabler 欄位；**工具名稱本身不成為 Task**，
包括員工大量描述它的時候。它們可另作 Knowledge／Skill 候選（支持度依 ADR 0040 決定 29–31）。

但**不得反向過度套用**：使用該工具完成的工作，若自己有 action＋object＋purpose/result，仍然成立
（`TI-R1-02`）。判準檢查的是「這句話的 action 與 object 是不是工具本身」。

### 4.3 Split 觸發條件（任一成立即檢查）

- 候選內含多組 action，且對應**不同**的 purpose/result；
- 內容太變異，無法寫成一句簡潔可解釋的敘述（O\*NET Task Separation）；
- 敘述需要分號才寫得下；
- 兩組活動各自都能對應到**不同**的工作產出或行為指標（iCAP）。

### 4.4 Merge 觸發條件（任一成立即檢查）

- 兩個候選共享 common action or purpose（O\*NET cluster 判準）；
- 其中一方是另一方的 support 活動或 TEWA（工具／設備／輔助）活動；
- 兩者對應**同一個**工作產出且無法各自寫出獨立的行為指標；
- 兩者太相似，無法各自 stand alone。

**語意平手時不預設合併，也不預設拆分，而是 `clarify`。** §3.4 引的「as few summary tasks as
possible」是 O\*NET **撰寫階段**把一群網路蒐集資料寫成精簡敘述的規則，不是單一員工工作邊界的
裁決規則，不得當 tie-break 直接套用。邊界不明時員工才是權威（ADR 0037／0040 的 employee authority），
應追問，不是替他決定。

### 4.5 第一版不採 Core／Periphery，也不加 frequency／importance 欄位

O\*NET 的 Core／Periphery 是**職業群體**構念（core＝多數在職者都會做），本產品是單一員工的客製 JD，
沒有 incumbent 分布可依據，因此**不引入 centrality 欄位**。

第一版**也不加 frequency／importance 欄位**：「正式低頻責任可成立」已經在 Task policies 的判準文字裡，
不需要欄位承載。真的需要區分時再加，並受 ADR 0042 決定 7 約束。

正式低頻責任、支援性工作不因低頻而被排除。真正的排除只留給：他人責任、過去工作、一次性支援、
純工具／步驟、員工明確否認、證據不足——且**排除理由必須分開保留**，不可壓成單一「已排除」狀態。

## 5. 同一性判準與動作對照

| 新內容 vs 既有 Task | O\*NET 分類 | 系統動作 | identity 規則 |
|---|---|---|---|
| 換句話說，無新資訊 | Duplicative | `no_change` + 追加 source support | 既有 ID 不變 |
| 重疊但帶新內容 | Overlapping | `revise` | **保留既有 ID**，敘述改寫 |
| 完全不同的工作 | Unique | `add` | application 配發新候選 ID |
| 新內容被某個既有 Task 吸收 | Task Revision | `revise` | **沿用該 Task ID**；不產生新 ID |
| 兩個既有 Task 合成一個較廣的工作 | Task Joining | `merge` | **建立新 Task ID**，兩個舊 Task 都記 `merged_into`；舊記錄不刪除 |
| 一個既有 Task 內含兩個獨立結果 | Task Separation | `split` | 明列來源 ID；產生的每個新 Task 都記錄 parent ID |
| **既有** Task 被新證據推翻 | Task Deletion | `withdraw` | 既有 ID 不刪除，標為撤回並記錄理由型別 |

**吸收與合成的區分判準**用已經拆開的 `purpose_result` 欄位就能表達，不需要新機制：
合成後的目的若等於其中一個舊 Task 的目的 → 那是吸收（`revise`，沿用該 ID）；
若需要一個涵蓋兩者、比原本更廣的新目的 → 那是合成（新 ID）。
模型提出判斷，但因為它會改變 JD，最終仍由員工在提案決定時確認。
**建立時間不作為存續依據**——它不代表語意主體。

新 Task ID 必須**冪等**——這是不變量：同一份已保存的模型結果重送時，不得建立第二個 Task ID。
**實際做法留給 production contract／plan**，本研究不鎖死機制，避免把舊路徑的複雜 identity 推導搬回來。

**一開始就不成立的訊號不建立 Task**。工具、步驟、他人責任、過去工作、一次性支援、證據不足
一律不先建 Task 再撤回——那會污染 Work Model，也給模型一條「先建再退」的避險路徑。
它們依判定結果留在 Source Layer、`open_issues[]` 或 `excluded_signals[]`。
`withdraw` 只適用於**已經存在**的 Task 被後來的證據推翻
（`TI-R1-08`），這條路徑必須保留。

不成立的訊號分成兩個最小集合存在 Work Model，**判準是「agenda 還會不會主動追問它」**：

| 集合 | 內容 | agenda 行為 |
|---|---|---|
| `open_issues[]` | 責任邊界不明、**證據不足**、矛盾未解 | 會被選中追問；一輪只問一題，未選中的留著 |
| `excluded_signals[]` | 他人工作、過去工作、一次性支援、純工具／步驟、員工明確否認 | **不主動再問** |

`insufficient_evidence` 屬 `open_issues`，不是排除——它是「還沒問到」，不是「已判定不是」。

`excluded_signals` **不是永久 terminal**：員工日後自己更正（「其實那個我也要做」）仍可讓它重新成為候選。
差別只在系統不主動騷擾。此區分與舊路徑 `deferred`／`declined` 的**產品語意一致**，可作先例參考；
但依 ADR 0040 決定 3，production v1 仍重新定義，**不繼承舊資料模型或程式碼**，
也不得以舊實作曾經運作來主張新模型正確。

不分開的話，模型下一輪會把同一件事再提一次 Task，員工得重複說「那是別人做的」——
`TI-R1-06` 正是這種訊號。兩者都是最小 Work Model 資料，不是新的 Evidence／Claim layer。

## 6. 對契約的直接含意

1. **Task 不能只存一個 `task_statement` 字串。** 至少要分開存 `action`／`object`／`purpose_result`／
   `enabler`／`context`。理由是**可診斷性**：「兩個候選是不是同一個 purpose/result」是 merge 的核心訊號，
   拆開欄位讓模型與 reviewer 有明確的比較對象、讓錯誤有明確的位置。
   **這不代表 purpose、merge、split 可以由程式自動判定**，字串比對做不到這件事。
2. **identity 在候選建立時就配發，不等員工接受。** 否則跨回合無法 `revise`／`merge`，
   每輪只能重複提案。員工接受是把候選送進 Current JD，不是產生 identity。
3. **模型不得自造 ID**，只能引用 Context Packet 提供的既有 Task；引用形式建議用 context-local ordinal
   而非 UUID 字串（沿用 repo 既有 `question.select` 只回 ordinal 的作法）。
4. **一輪可含多個 proposal**，因此需要衝突規則：同一 target 被兩個 proposal 指涉時**兩者都拒絕**
   （沿用既有 verifier 對 duplicate correction target 的裁決，不任選贏家）；
   `merge` 的來源必須兩個以上且都存在；`split` 的來源必須存在且不得同時被 `withdraw`。
5. **verifier 與 rubric 的分界要寫死**，否則會出現「用 schema required 逼模型硬填一句話」，
   那正是 ADR 0040 決定 25 禁止的「Task 不得因 schema 必填被迫產生」：

   | verifier（確定性） | rubric／模型（語意） |
   |---|---|
   | 欄位型別與存在、分號、引用的 Task ordinal 是否在範圍內、source anchor 是否存在且 quote 可回原文核對、merge/split 來源數量、lineage 是否成環 | 目的是否合理、工作結果是否足夠、兩個候選是不是同一個 purpose、該不該 merge／split |

   §4.3–4.4 的判準**大部分不是機械檢查**——「是否共享同一 purpose/result」是語意判斷。
   欄位拆開的價值是讓語意判斷**有明確的比較對象與可診斷的位置**，不是讓它變成可自動驗證。

## 7. 依新判準重新檢視 TI-R1-03／04

依 ADR 0041 決定 15，**不改動 case revision 1**（R1a 結果引用它）。以下只是依 §4 判準的推導記錄：

- **`TI-R1-04`（資料匯入 vs 驗證規則調整拆成兩個 Task）**：兩者對應同一個關鍵工作產出
  （正確、可對帳的 ERP 資料），驗證規則調整無法寫出獨立的行為指標，屬 support 活動。
  依 §4.4 判準應 merge。**凍結期望站得住**，A6 的輸出確實違反判準。
- **`TI-R1-03`（過早把「主持每月改善追蹤」建成 Task）**：該活動可能有自己的產出（追蹤結論／改善紀錄），
  因此**不是**結構上不可成立；不成立的原因是 §4.1 條件 3–4 的證據不足。
  依判準應先 `clarify`。**凍結期望站得住，但理由要改寫**：是證據不足，不是邊界錯誤。

這是依判準推導，不是 SME 驗證。ADR 0040 決定 14 的 Job Analysis Quality Rubric 應據此更新，
更新後 grader rubric 必須能抓到 R1a §2 列的三個漏判。

## 8. 限制

- O\*NET 自承 task writing「requires considerable individual judgment…no two writers will produce
  exactly the same results」。本研究交付的是可複核判準，**不是唯一答案**，不得宣稱 03／04 已有定論。
- O\*NET 程序的操作者是 I-O 心理學研究生並受過專門訓練，其判斷品質不能直接轉移到 LLM。
- iCAP 指引規範的是**公版職能基準**的發展，客製 JD 沿用其欄位語意，但不受其審核程序約束。
- DACUM 來源為大學課程頁面，僅用於佐證 duty／task 兩層與 task 的操作型定義，不作為主要依據。
- 本研究**沒有**新的模型實驗證據；owner 已裁定第一版不再跑架構矩陣。判準是否被模型遵守，
  只有實作後的少量案例檢查能看出來。

## 9. Task v1 凍結形狀（2026-07-28）

本節是 production contract 的**研究基礎，不是最終資料庫 schema**。欄位到此凍結；
要再增加必須先指出它避免的具體使用者失敗。

**本節只凍結 Current Work Model 的 Task Analysis slice，不是完整 Current Work Model。**
角色假說（Role Hypothesis）、coverage、current focus、active question、conversation 與
Product Proposal 由後續垂直切片定義（見 [roadmap §9.2](2026-07-25-professional-consultant-architecture-realization-roadmap.md)）；
它們沒有被刪除，只是不在這一輪的範圍內。

### 9.1 形狀

```text
SourceRef { kind: employee_turn | direct_edit | proposal_decision, id }

SourceAnchor { source_ref, quote?, question_turn_id? }

Task
├─ task_id                       application 產生，冪等
├─ statement                     給人看的 AI 敘述；Current JD 另有自己的文字，兩者可不同
├─ action / object               必填
├─ purpose_result? / context?
├─ deliverable_hint? / success_criterion_hint?
├─ enablers[]        { kind: tool_system|method|knowledge|skill|other, name }
├─ support_links[]   { source_ref, quote?, question_turn_id?, superseded_by?: SourceRef }
├─ retirement?       { kind: withdrawn|merged|split, reason?, source_ref }
│                      reason: other_person|past_work|one_off|enabler_or_step|employee_denied
│                      （只有 kind == withdrawn 才有 reason）
├─ merged_into? / split_from?
└─ pending_reconciliation?: SourceRef   合法來源見 §9.5（direct_edit｜employee_turn｜
                                        proposal_decision 且 decision 為 edited 或 rejected）；
                                        多筆未對齊時指向最新一筆

Current Work Model
├─ tasks[]
├─ open_issues[]      { id, kind, summary, source_anchors[], last_asked_turn_id? }
│    kind: 責任邊界不明 | 證據不足 | 矛盾未解 | task_boundary_uncertain
└─ excluded_signals[] { id, reason, summary, source_anchors[] }
     reason: 他人工作 | 過去工作 | 一次性支援 | 工具或步驟 | 員工否認
```

`task_boundary_uncertain` 涵蓋 duplicate／overlap 不確定、merge／split 邊界不明、
是否共用 meaningful outcome 不明。它是暫時性 `identity_assessment.relation = uncertain`
的**持久落點**——本輪若選擇先問別的問題，這個缺口不會消失。

### 9.2 推導狀態（不存 status 欄位）

| 狀態 | 條件 | 可否作為穩定現況產生新文件提案 |
|---|---|---|
| `active` | `retirement == null` 且 `pending_reconciliation == null` | 可 |
| `pending reconciliation` | `retirement == null` 且 `pending_reconciliation != null` | **不可**；優先進 reconciliation／clarify |
| `retired` | `retirement != null` | 不可 |

reconciliation 必須讀 **Current JD 的目前文字**，不是只讀該筆 edit；成功對齊後清空
`pending_reconciliation`。不建立 revision、checkpoint 或 reconciliation history。

### 9.3 持久與暫時

全部持久，**除了**單次模型輸出的 `identity_assessments[]`、`task_change_proposals[]`、
原始 `next_question`，以及 ordinal↔ID mapping（存在該輪呼叫紀錄側）。

模型送出的 `next_question` 一旦實際發問，**必須**轉成持久的顧問回合與 active question——
`support_links[].question_turn_id` 依賴它；少了它，reload 後員工的短答無從連回問題。

### 9.4 寫入權威

```text
模型      → 提出候選結果（依據）
員工      → 接受／修改／拒絕，或直接編輯 Current JD（依據與文件權威）
application → 驗證後唯一負責寫入 Current Work Model 與 Current JD
```

員工直接編輯**不覆寫** Work Model 欄位：JD 立即保存員工文字 → 該編輯成為 `direct_edit` Source
→ Task 標記 `pending_reconciliation` → application 驗證新的分析結果後才更新 Work Model。

Proposal **只 gate Current JD**。分析結果對 Work Model 的更新在通過 verifier 後即可套用，
唯一例外是會碰到 JD 既有 identity 的 topology 變更（§9.6）。被 `reject` 時**不回滾** Work Model——
拒絕成為新來源，由下一輪向前重新分析，不做補償交易。

### 9.5 確定性 verifier 規則

- 欄位型別與 enum 值域；ordinal 在 Context Packet 範圍內；
- `source_ref.kind == employee_turn` → `quote` 必填且為該回合原文的逐字子字串；
  只有 `direct_edit`／`proposal_decision` 的 `quote` 可空；
- `question_turn_id` 指向**已存在且較早**的顧問回合，不得指向員工回合或未來回合；
- `open_issue` 至少一個 anchor；`矛盾未解` 至少兩個；
- `retirement.kind == withdrawn` → `reason` 必填；`== merged` → `merged_into` 必填；
- `merged_into`／`split_from` 目標必須存在且不得成 cycle；
- Current JD 與 Proposal ID 不得重複，Current JD 投影必須使用 canonical Task ID 順序；
- staged delta 內的 lineage／new Task ID 不得重複，且 withdraw／merge／split 不得夾帶
  不屬於該 action 的 lineage 欄位；
- `pending_reconciliation` 必須指向下列其中一種來源：`direct_edit`、`employee_turn`（訪談中的更正
  或否認）、`proposal_decision` 且該決定為 `edited`（對齊員工文字）或 `rejected`（重新判斷方向）；
  `deferred` 不觸發。它是**觸發器與最近原因指標，不是待辦清單**——reconcile 一律讀 Current JD 現況
  與該 Task 的最近相關決策，不能只讀那一筆 `SourceRef`。判定 reconcile 目標需要
  `source_ref` **加上** 該 Proposal 的 decision，只看 `kind` 分不出 `edited` 與 `rejected`；
- **`active` Task 至少一條 `superseded_by == null` 的 SupportLink**；
- **原子性**：同一次寫入若使某 `active` Task 的最後一條有效 SupportLink 變成 `superseded_by != null`，
  該次寫入必須**同時滿足下列其中一項**，否則整筆拒絕：

  | 出口 | 適用情境 | 對 Current JD 的效果 |
  |---|---|---|
  | 新增有效 SupportLink | 新說法只修正細節，仍支持同一 Task（`revise`） | 由 Proposal 決定是否改文字 |
  | 設定 `pending_reconciliation` | 員工直接編輯與舊分析不一致 | **JD 不動**，等待重新對齊 |
  | 設定 `retirement` | 員工在訪談中明確否認原 Task（`TI-R1-08`） | Work Model 可立即 retire；**JD 中已核准的內容不因此消失**，移除須另提 Proposal |

  三個出口對應三種不同的真實情境，缺一就會出現「active 但零有效支持」或
  「員工編輯被當成否認」的錯誤處置。

retirement 的 `source_ref` 必須取自該 `work_signal` 實際引用的 employee-turn anchor；
不得因為某個回合恰好是 current turn，就把未被模型引用的回合寫成撤回依據。
application 配發的 Task／Proposal ID 採 insert-only：相同 ID 已存在且內容不同時整筆拒絕，
不得用 dict overwrite 靜默改寫既有真相。這仍不等於 exactly-once；完整 replay 留給 persistence
階段的 operation ledger。

其餘（purpose 是否相同、該不該 merge／split、outcome 是否可理解、enabler 分類是否正確）
一律歸 rubric 與員工審核，**不得寫進 verifier**，也不得用 schema required 逼模型硬填
（ADR 0040 決定 25）。

### 9.6 Identity gate：什麼時候可以直接改 Work Model

閘門條件不是動作類型，也不是「有沒有建立新 ID」，而是**這次 topology 變更是否碰到 Current JD
已有的 identity**：

```text
topology_affected_existing_ids ∩ current_jd_task_ids
```

| 交集 | 處置 |
|---|---|
| 空 | 純 Work Model 整理，**立即更新**，不建立 Proposal、不打擾員工 |
| 非空 | 建立 Proposal，同時保存 `staged_work_model_delta` 與 JD before／after |

逐情境：

| 情境 | Work Model | Proposal |
|---|---|---|
| JD 外候選 `withdraw` | 立即 retire | 不建立 |
| JD 內 Task `withdraw` | 暫不 retire，設 `pending_reconciliation` | 建立 |
| `merge` 來源全不在 JD | 立即 merge | 不建立 |
| `merge` 任一來源在 JD | 暫不套用 topology | 建立 |
| `split` 母 Task 不在 JD | 立即 split | 不建立 |
| `split` 母 Task 在 JD | 暫不套用 topology | 建立 |
| `add` 候選 | 立即建立候選 ID | 只有要加入 JD 時才建立 |
| 同 ID `revise` | 立即更新（topology delta 為空） | JD 文字也要改時才建立 |

`accept`／`edit` 時 `staged_work_model_delta` 與 JD 變更**原子套用**；`reject`／`stale` 兩層都不套用；
`defer` 兩層都不動，delta 留在 Proposal，Context 標為待決假說。
`add`／`revise` 已先進 Work Model，被 `reject` 後需要 reconciliation；`merge`／`split` 尚未套用，
被 `reject` 不需要 reconciliation，只需記錄拒絕；JD 內 `withdraw` 等待期間本來就在 reconciliation。

**待決 Proposal 不得當成已成立事實**，但可用於避免重複，也可被新證據修訂或取代。

#### Authority snapshot：不得用過期分析套用新現況

LLM 分析所依據的 Work Model 與 Current JD 是一份 **authority snapshot**。寫入時：

1. 若該分析**實際讀取或指涉**的 Task 與其 JD membership 在模型執行期間改變 → **整份分析結果失效，
   不得套用**，必須重新分析。不得只在最後重算交集然後換一種分類方式硬套——那會把基於舊上下文的
   判斷用到新現況上，兩個方向都可能套錯語意。
2. snapshot 仍有效時，才在同一原子操作中重算上面的交集。

read-set 的範圍以**該輪 Context Packet 投影出的 Task 集合及其 JD membership** 為準：模型只能引用
packet 給的 ordinal，所以它碰得到的東西必然在 packet 裡。與本次分析無關的 Task 被編輯，不需要
作廢整輪——單機單人但員工可在 AI 回應期間編輯文件，全域作廢會讓員工每次順手改字都白等一輪。

這只需要最小的 stale-input／optimistic concurrency 保護，**不需要 Event Sourcing、hash chain 或
版本歷史**；用 generation、before-value 或其他機制留給 contract／persistence 決定。
（舊路徑的 `state_context_stale` 是同一個教訓的產品語意先例；依 ADR 0040 決定 3，
v1 重新定義，不繼承其資料模型或程式碼。）

#### 舊 Proposal 因純 Work Model 變更而失效時

同一交易必須給出明確 disposition，不得讓它無聲消失：

- **replacement**：仍有對應的 JD 修改建議 → 建立新 Proposal，舊的 stale；
- **closed_without_replacement**：分析後已不再建議修改 JD → 舊的 stale，並保留**員工看得到**的失效理由。

不得強制一定要有 replacement——那會把已被否決的內容換個形式再推給員工一次。
理由只存在資料庫而 UI 從不呈現，等同無聲消失。

#### 已知例外：direct edit 讓被拒絕的 topology 再次出現

一般接受流程下，Task 離開 JD 時必然同時在 Work Model retire，因此被拒絕的跨層 topology
不會退化成「純 Work Model 整理」。**員工直接編輯 JD 刪除某條目是已知例外**：該 Task 離開了
`current_jd_task_ids`，卻只被設為 `pending_reconciliation` 而未 retire，於是同一個 topology
判斷下一輪的交集會變成空集合。

後果有界——AI 仍不能靜默改 JD，只能再提一次讓員工再拒一次；但 duplicate-rejection 規則攔不住它
（新提案的 action＋target＋after 與被拒的那份不同）。因此**被拒絕的 topology 判斷必須持久保存，
並在 Context Builder 再次分析相關 Task 時帶入**。這不是永久禁令：有新資訊時 AI 仍可重新提出，
但不得當作舊拒絕不存在。

### 9.7 不在 Task v1 內

Product Proposal 的 target 形狀與生命週期、員工決策如何分別更新 Work Model 與 Current JD，
見 **§10**（在 Task v1 凍結之後另外定案）。Context Packet 在其後。

## 10. Product Proposal v1 凍結形狀（2026-07-28）

與 §9 同性質：production contract 的研究基礎，不是資料庫 schema。Proposal **只 gate Current JD**；
Work Model 的更新規則見 §9.6。

### 10.1 狀態與轉移

```text
pending  → deferred | accepted | edited | rejected | revision_requested | stale
deferred → accepted | edited | rejected | revision_requested | stale

terminal: accepted | edited | rejected | revision_requested | stale
```

| 狀態 | 誰決定 | payload |
|---|---|---|
| `pending` | application 建立 | — |
| `deferred` | 員工 | — |
| `accepted` | 員工 | — |
| `edited` | 員工 | `edited_jd_after`（見 §10.5） |
| `rejected` | 員工 | `reason?` 自由文字 |
| `revision_requested` | 員工 | `excluded_member_task_ids[]`（merge）或 `excluded_child_refs[]`（split），至少一項 |
| `stale` | **application 判定，非員工決策** | `stale_reason`（員工可見） |

**`stale` 只套用於仍為 `pending`／`deferred` 的 Proposal；terminal Proposal 不會被改成 `stale`。**

命名注意：`source` 一詞已專指 provenance／`SourceRef`，因此排除清單用 `member`／`child`，
不得叫 `source_ids`。

### 10.2 action 與 target

| action | target | `affected_task_ids` | 何時需要 Proposal |
|---|---|---|---|
| `add` | `task_id`（Work Model 候選） | `[task_id]` | 要進 JD 時 |
| `revise` | `task_id` | `[task_id]` | JD 文字也要改時 |
| `withdraw` | `task_id` | `[task_id]` | 該 Task **在 JD 中**時（JD 外直接 retire，§9.6） |
| `merge` | staged `new_task_id` ＋ `member_task_ids[]`（≥2） | 新 ID ＋ 全部成員 | 任一成員在 JD 時 |
| `split` | `parent_task_id` ＋ staged `child_ids[]`（≥2） | 母 ＋ 全部子 | 母 Task 在 JD 時 |

staged 的新 ID 與子 ID 由 application 在提案建立時配發、冪等；提案未被接受即成為未使用的孤兒 ID。
`excluded_child_refs` 指的就是這些 staged child id，**不另立第二套 ordinal 指涉**。

第一版把「Task Analysis 建立候選」與「候選送進 Current JD 審核」維持為兩個顯式動作：
`add` 只建立 Work Model 候選；agenda／產品流程判定現在值得送審時，才呼叫
`propose_task_for_jd()` 建立 `add` Proposal。不得因每輪發現新候選就自動堆一張提案卡，也不得
跳過 Proposal 直接寫 JD。

### 10.3 JD before／after 與 precondition

```text
jd_before: { task_id -> JD 目前內容 | null }    null = 尚未在 JD（add 的常態）
jd_after:  { task_id -> 提議內容   | null }     null = 從 JD 移除（withdraw、merge 成員）
```

precondition：每個 `affected_task_ids` 的 **JD 現況等於 `jd_before` 對應值**；不等即 `stale`，不套用。

### 10.4 staged Work Model delta

```text
staged_work_model_delta?    只有跨層 topology 變更（merge／split／JD 內 withdraw）才有
├─ retirement / merged_into / split_from
└─ staged 新 Task 的語意欄位
```

`accepted`／`edited` 時與 JD 變更**原子套用兩層**；`rejected`／`stale`／`revision_requested` 兩層都不套用；
`deferred` 留在提案內，Context 標為待決假說。

### 10.5 `edited` 的硬規則

`edited` 是**文字修改**，不是結構修改。payload 是完整 map：

```text
edited_jd_after: { task_id -> edited content | null }
```

- key 集合必須與原 `jd_after` **完全相同**；
- `null`／非 `null` 的位置必須**完全相同**；
- 只能修改非 `null` 的內容；
- **不得**修改 `action`、`target`、成員集合或任何 topology。

不符合即拒絕整筆決定。這幾條讓「edited 真的只是改字」成為可機械檢查的事實，而不是靠實作者自律。

### 10.6 決策對兩層的效果

| 決策 | Current JD | Current Work Model |
|---|---|---|
| `accepted` | 套用 `jd_after` | 套用 staged delta（若有）；產生 `proposal_decision` Source |
| `edited` | 套用 `edited_jd_after` | 套用 staged delta（若有）＋ 受影響 Task 設 `pending_reconciliation` |
| `rejected` | 不變 | `add`／`revise` 已先進 Work Model → 設 `pending_reconciliation`；`merge`／`split`／`withdraw` 未套用 → 不需要 |
| `deferred` | 不變 | 不變 |
| `revision_requested` | 不變 | 不變；原 Proposal **永不執行** |
| `stale` | 不變 | 不變 |

結構性提案被 `edited` 時，staged delta 照原樣套用、只有文字換成員工的；因此新產生的 Task
一落地就帶 `pending_reconciliation`，由下一輪對齊。

### 10.7 `revision_requested` → replacement

```text
交易 1   Proposal → revision_requested、保存排除清單與員工決策、兩層都不套用、commit
交易外   依最新 authority snapshot 呼叫 LLM 重建
交易 2   snapshot 仍有效 → 建立 replacement Proposal（caused_by_decision_id 指回該決策）
         snapshot 已失效 → 丟棄結果，重組 context 重來
```

重建以**語意正確優先**，減少不必要的改寫；**不得為追求小 diff 而保留受排除成員影響的內容**。

解析結果有持久落點，兩者互斥：

```text
RevisionRequestResolution
├─ replacement Proposal（由 caused_by_decision_id 關聯）
└─ closed_without_replacement_reason?
```

狀態由此推導：兩者皆無 → 等待重建，reload 後可重試；有 replacement → 新的提案待確認；
有 closure reason → 已結束並顯示原因。

**唯一性：同一筆 `revision_requested` 決策最多產生一份 replacement**（不是「最多一份非 stale」）。
該 replacement 日後若 stale，後續提案依最新現況重新產生，**不得復活舊的 revision request**。

重建結論是不需要改 JD 時走 `closed_without_replacement`；**不為「不做某件事」要一次核准**。

### 10.8 stale 觸發與 disposition

| 觸發 | disposition |
|---|---|
| 新提案的 `affected_task_ids` 與它有交集，且它仍 `pending`／`deferred` | 新提案即 replacement |
| affected Task 的 JD 現況 ≠ `jd_before` | replacement 或 visible closure |
| affected Task 進入 `pending_reconciliation` 或 `retirement != null` | replacement 或 visible closure |
| 純 Work Model topology 變更使它失效 | **同一交易**內 replacement 或 visible closure（§9.6） |
| 本輪已實質重新分析 affected Task、但沒有 replacement | visible closure |

`closed_without_replacement` 的理由必須**員工看得到**；只存資料庫等同無聲消失。

### 10.9 Authority snapshot 的 read-set

read-set 是該輪 Context Packet 中**所有會影響分析且可能變動的 authority input**：

- 投影出的 Task 語意欄位；
- JD membership 與 `jd_before` 內容；
- 相關的 Proposal 決策；
- `open_issues[]` 與 `excluded_signals[]`。

其中任何一項在模型執行期間改變 → **該次分析結果失效，不得套用**，必須重新分析；不得只重算
§9.6 的交集然後換一種分類硬套。與本次分析無關的資料被改動不作廢整輪——只保護模型真正讀過的部分。

### 10.10 提案卡最低顯示

變更 diff、JD before／after、相關員工原話、被排除成員目前如何處理。
取消勾選時不再問一次；員工審查 replacement 後按一次接受即可。

**引用邊界**：OpenAI 的 HITL 指引直接支持的是「新生成內容投入使用前應由人審查」與「審查者應能方便
取回原始資料」——因此**顯示員工原話有官方依據**。diff、before／after 與排除成員狀態是本產品的
設計選擇，不得標成 OpenAI 的要求。

### 10.11 不在 Product Proposal v1 內

資料庫表、job／workflow framework、版本歷史、通用 topology editor、批次核准、
Proposal 之外的通知機制。

## 11. TaskAnalysisContext.v1（2026-07-28）

分區依據是**資料的權威來源**，不是模型的思考步驟。identity 比對、Task 邊界、變更提案與下一題
共用同一批資料，按思考步驟拆會重複資料並逼模型照死流程推理；完全扁平則容易讓「員工已確認的事」、
「AI 暫時的理解」與「尚未核准的提案」混在一起。OpenAI 與 Anthropic 的 prompt／context 指引都主張
用清楚區段表達邏輯邊界，且只放足以完成任務的最小高訊號內容。

### 11.1 請求結構

```text
Task Analysis Model Request
├─ Static Instructions          （固定 prompt，不隨產品現況變動）
│  ├─ 顧問角色
│  ├─ Task policies（§4 判準）
│  ├─ 行為與禁止事項
│  └─ 輸出規則
│
├─ Dynamic Context Packet
│  ├─ conversation_context
│  │  ├─ transcript            第一版送完整
│  │  └─ active_question       產生 question_turn_id 的來源
│  │
│  ├─ current_authorities
│  │  ├─ tasks[]               ＋ context-local ordinal
│  │  │   └─ support_links[]   ＋ task-local ordinal（模型指認被更正的依據時用）
│  │  ├─ jd_presence           該 Task 是否在 Current JD 及目前文字
│  │  ├─ retired_tasks[]       精簡形式：ordinal、statement、retirement.kind/reason
│  │  ├─ open_issues[]
│  │  └─ excluded_signals[]
│  │
│  └─ proposal_context
│     ├─ pending / deferred proposals   明標「尚未成立」
│     ├─ 尚未完成的 revision requests
│     └─ 會約束後續判斷的 rejection
│
└─ Output Schema
   ├─ identity_assessments
   ├─ task changes
   └─ next_question
```

### 11.2 固定限制

- `next_question` 是**輸出**，不是輸入區段；
- Task policies 屬 Static Instructions，**不混進動態產品現況**；
- pending／deferred Proposal 必須明標**尚未成立**，模型不得當現況事實（§9.6）；
- 第一版直接送**完整 transcript 與全部 Work Model Tasks**，不做 embedding、retrieval、compaction
  或通用 Context framework；長對話出現退化再啟用 ADR 0041 決定 8 已定案的 recent-window；
- Proposal 只引用 Task **ordinal**，不重複整份 Task 內容；
- ordinal 每輪重新編號、在 packet 中明示、超出範圍即 invalid；ordinal↔ID mapping 存在該輪呼叫
  紀錄側，不進產品 domain（§9.3）。

### 11.3 read-set 的保守定義

分區只能讓權威邊界清楚，**不能證明模型實際注意了哪些資料**。因此：

> read-set ＝ 本輪 packet 中送出的**所有可變 authority 資料**（保守計入）。
> application 保存當輪的實際投影，寫入前只檢查這批 authority 是否已變（§10.9）。

不另建 read-set framework，也不試圖從模型輸出反推它「真正讀了什麼」。

### 11.4 與 A6 的關係（ADR 0042 決定 7 的逐項理由）

本結構仍是 A6 已 live 驗證過的 `sources ＋ current_work_model ＋ task_policies`，只是把後續定案時
確實存在的資料放到正確位置。每一項新增都對應一個已定案的機制：

| 新增項 | 為什麼必要 | 出處 |
|---|---|---|
| `jd_presence`（是否在 JD ＋ 目前文字） | identity gate 的交集判斷與 `jd_before` precondition 都需要它 | §9.6、§10.3 |
| `open_issues[]` | 未被選中追問的缺口否則會消失；`uncertain` 需要落點 | §9.1 |
| `excluded_signals[]` | 否則同一訊號會被重複提成 Task，員工得重複拒絕 | §9.1 |
| pending／deferred proposals | 避免重複提案，並允許以新證據修訂或取代待決提案 | §9.6 |
| 受約束的 rejection 記錄 | direct-edit 已知例外的唯一承擔者 | §9.6 |
| `active_question` | `support_links.question_turn_id` 的來源；缺它短答無法解讀 | §9.3、§9.5 |
| support link 的 task-local ordinal | 否則模型無法指認「哪一句依據被更正」，`superseded_by` 永遠設不了（§12.1） | §9.1、§9.5 |
| `retired_tasks[]`（精簡） | 否則已撤回的工作會被重新提出，員工得重複拒絕 | §9.6 |

`retired_tasks[]` 是 **read-only 的防重提資訊**：

- **不進 active Task 的 ordinal namespace**（另一組編號）；
- **不得出現在任何 `target_task_ordinals` 或 supersession reference**；
- 新證據若與該 `retirement` 衝突，第一版**輸出 `open_issue`**，不得自動復活。

沒有其他新增。欄位到此停止擴充。

## 12. TaskAnalysisResult.v1（2026-07-28）

模型的 production output shape 與其 application mapping。**模型永遠不產生 ID**，只用 packet 給的
ordinal 與本次輸出內的位置索引；所有 ID 由 application 配發（§9.6、§11.2）。

### 12.1 形狀

```text
TaskAnalysisResult.v1
├─ work_signals[]                     一段回答可產生 0..N 條
│  ├─ anchors[]  { turn_ordinal, quote }        ≥1；`矛盾未解` 需 ≥2
│  ├─ identity   { relation, target_task_ordinals[] }
│  │                relation: no_match | duplicate | overlap | uncertain
│  ├─ supersedes_support_ordinals[]            預設空；指認被本次更正取代的既有依據
│  │                每項 { task_ordinal, support_ordinal }
│  ├─ disposition: task_change | support_only | exclude | open_issue
│  └─ payload（依 disposition 擇一）
│     ├─ task_change  { change, target_task_ordinals[], task_fields?, split_children[]? }
│     │                  change: add | revise | withdraw | merge | split
│     │                  split child: { task_fields, inherited_support_ordinals[] }
│     ├─ support_only { }                       只追加來源，不改 Task
│     ├─ exclude      { reason, summary }
│     └─ open_issue   { kind, summary }
│
├─ next_question { text, purpose, target? }
│                   target: { kind: existing_open_issue, ordinal }
│                         | { kind: new_signal, index }
│                         | null
└─ limitations[]
```

`task_fields`＝§9.1 的語意欄位子集：`statement`、`action`、`object`、`purpose_result?`、`context?`、
`deliverable_hint?`、`success_criterion_hint?`、`enablers[]`。**不含** `task_id`、`support_links`、
`retirement`、`merged_into`、`split_from`——那些全部由 application 依 anchors 與 gate 產生。
`split_children[].inherited_support_ordinals` 是 task-local ordinal，只用來讓 application
把母 Task 的既有有效 SupportLink 分配給真正受其支持的 child；不得把全部來源無差別複製。
Merge 則由 application 合併所有 member 的有效 SupportLink，再加入本輪 anchors。
跨 JD 的 staged merge／split 必須保存 application 已解析完成的同一組 SupportLink，
確保接受後的新 active Task 不需猜測來源。

**不設整體 `analysis_decision` 欄位**：本輪是提案、澄清還是不變更，由 `work_signals` 推導
（無 `task_change` 即澄清或不變更）。多存一個可能與陣列內容矛盾的欄位沒有價值（§9.2 同一原則）。

### 12.2 relation × disposition → application mapping

| relation | disposition | application 效果 |
|---|---|---|
| `duplicate` | `support_only` | 既有 Task 追加 SupportLink，不改語意欄位 |
| `overlap`（1 target） | `task_change: revise` | 沿用該 `task_id` 改寫語意欄位 ＋ 追加 SupportLink |
| `overlap`（≥2 targets） | `task_change: merge` | merge 候選；存續 ID 依 §5／§9.6 |
| `no_match` | `task_change: add` | 建立新候選 Task（application 配發 ID） |
| 任一 | `task_change: withdraw` | 依 §9.6：JD 外立即 retire；JD 內走 Proposal |
| 任一 | `task_change: split` | 母 Task ＋ ≥2 個 `split_children` |
| 任一 | `exclude` | 寫入 `excluded_signals[]`（他人工作／過去工作／一次性支援／工具或步驟／員工否認） |
| `uncertain` | `open_issue` | 寫入 `open_issues[]`（`task_boundary_uncertain`） |
| 任一 | `open_issue` | 責任邊界不明／證據不足／矛盾未解 |

每一筆 `task_change` 由 application 各自計算
`topology_affected_existing_ids ∩ current_jd_task_ids`，決定立即套用或建立 Proposal（§9.6）。
同一輪可同時包含立即套用與 Proposal 兩類結果。

模型只給 `anchors`；application 把 `turn_ordinal` 解析成 `SourceRef`，再建立 SupportLink
與 `source_anchors[]`（§9.1）。

### 12.3 這個形狀專屬的 verifier 規則

在 §9.5／§10.5 之外另加：

- `anchors` ≥1；`open_issue.kind == 矛盾未解` 時 ≥2；
- `quote` 必須是該 `turn_ordinal` 原文的逐字子字串，且該回合必須是**員工回合**；
- `target_task_ordinals` 必須在 packet 範圍內；`no_match` 時必須為空、`duplicate`／`overlap` 時 ≥1、
  `merge` 時 ≥2；
- `change == merge` → `task_fields` 必填；`change == split` → 1 個母 target ＋ `split_children` ≥2；
  `change == withdraw` → **不得**帶 `task_fields`；
- split child 的 `inherited_support_ordinals` 不得重複，且只能指向母 Task 目前有效的 support link；
- 同一個 target Task 被兩筆 `task_change` 指涉 → **兩筆都拒絕**，不任選贏家；
- `next_question.target` 必須指向存在的 packet ordinal 或本次輸出的合法 index；
- `supersedes_support_ordinals[]` 的每一項必須指向 packet 中存在、且**目前 `superseded_by == null`**
  的 support link；其 `task_ordinal` 必須出現在同一筆 signal 的 `target_task_ordinals` 中；
  `retired_tasks[]` 不在此 namespace，不得被指涉。
- 兩筆 `work_signals[]` 若逐欄完全相同，兩筆都拒絕；只做 exact duplicate 檢查，
  不以文字相似度、embedding 或語意模型猜測是否重複。

**`superseded_by` 要寫哪個新來源**：第一版一律指向**本次 operation 正在處理的 employee turn**，
且該 turn 必須存在於同一筆 signal 的 `anchors` 中。不加欄位讓模型指定。日後若 direct edit 或
proposal decision 的 reconciliation 共用這個 operation，再另升契約。

輸出契約本身沒有任何可讓模型填 ID 的欄位，因此**不做「掃描全文是否含 UUID 形狀字串」的檢查**——
員工原話可能合法含有 request／correlation UUID，掃描會誤殺。只驗 ordinal 與結構欄位。

**為什麼需要 `supersedes_support_ordinals`**：§9.1 的 `SupportLink.superseded_by` 與 §9.5 的原子性
三出口，都以「某條依據被後續來源取代」為前提。若模型無法指認是哪一條，application 只能自行猜測，
而那是語意判斷，依 §9.5 末段不得放進 verifier。`TI-R1-08`（員工更正責任範圍）在缺這個欄位時
**無法實作**：舊的錯誤引述會繼續掛在 Task 上當有效依據。這是本欄位存在的唯一理由，
不作其他用途。

分類是否正確、該不該 merge、outcome 是否可理解，一律仍歸 rubric（§9.5 末段）。

### 12.4 provider schema 範圍

**只有 `TaskAnalysisResult.v1` 需要提交 provider-facing JSON Schema**（portable subset，
ADR 0040 決定 24）。Task、Proposal、Context 等同 package 內部契約用 Pydantic ＋ 少量 unit test 即可，
不為內部 DTO 產生大量 JSON Schema 與 golden。
