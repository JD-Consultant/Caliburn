# Task 邊界、merge/split 與同一性判準研究

- 日期：2026-07-28
- 狀態：Proposed；供 ADR 0042 與 Production Task Analysis v1 契約引用
- 觸發：[R1a 結果](../experiments/2026-07-27-r1-task-discovery/r1a-results.md) §4「不能宣稱」——
  `TI-R1-03`／`TI-R1-04` 顯示 merge/split 仍是核心缺口；owner 2026-07-27 裁定停止付費架構實驗，
  改以權威研究收斂判準
- 相關：[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)（Task rubric 為單一權威判準資產）、
  [ADR 0041](../adr/0041-r1-p0-closure-first-version-context-and-holdout.md)（凍結期望不得為配合模型輸出改寫）、
  [R1 深入研究 §4–5](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)

## 1. 要回答的三個問題

R1a 之後，Task Discovery 剩下的不是「模型夠不夠強」，而是三個判準問題：

1. **粒度**：什麼算一個 Task？何時是步驟、工具或工作活動？
2. **同一性**：新回答裡的敘述，是既有 Task 的換句話說、補充，還是新工作？
3. **merge/split**：什麼條件觸發合併或拆分？輸出要長什麼樣才能機械檢查？

第 2 題是實作 blocker：沒有同一性判準，`revise` 保留哪個 Task、`merge` 合併哪幾個、
`split` 從哪裡拆出來、`withdraw` 撤回哪一項，都無法表達。

## 2. 來源

| 來源 | 性質 |
|---|---|
| [O\*NET Task Writing Guidelines（Appendix B）](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf) | 美國勞工部 O\*NET 中心的 task statement 撰寫規範 |
| [Summary of Procedures for O\*NET Task Updating and New Task Generation（Dierdorff & Norton, 2011）](https://www.onetcenter.org/dl_files/TaskUpdating.pdf) | O\*NET 官方的 task 更新程序，含比對、分群、合併、拆分、刪除 |
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
（`using` / `based on` / `following` 引導），**結構上就不可能自己成為 task statement**。
`TI-R1-01` 的期望因此有官方依據，不是我們的偏好。

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

### 3.5 同一性：官方的三分類

Task Matching 階段把每筆新資訊對既有 task 分成三類：

> a) **Duplicative** of a preexisting O\*NET task; b) **Unique** relative to all of the O-tasks; or
> c) **Overlapping** an O-task but still providing additional content information.

第 (c) 類的處置寫在 Task Revision 階段：**用重疊內容改寫既有 task**，而不是新增一個。
這正是我們缺的 add / revise / no_change 判準。

### 3.6 iCAP：粒度必須對得上工作產出與行為指標

《職能基準發展指引》規定工作內涵的分層與欄位：

> 依據該職業（類）之主要工作進行分析，分層展開主要職責、工作任務、工作活動
> （視工作複雜度決定分層數，**建議以主要職責、工作任務 2 層為主**）。

> **工作產出**：指執行某任務最主要的關鍵工作產出……儘量以書、文件、圖表等有形交付標的為主，
> 若該項任務僅有行動或操作性質之工作成果，則不必列出工作產出，建議將相關成果列於行為指標之描述中。

> **行為指標**：用以評估是否成功完成工作任務之標準。需具體描述在何種任務情境下，有哪些應有的行為或產出。

因為本產品的匯出版型就是 iCAP，這一條是**最硬的粒度尺**：
一個「工作任務」必須能對應到自己的關鍵工作產出或自己的成功判準；對不上的，是工作活動（步驟），不是工作任務。

> 查證註記：外界常引「一份職能基準約 5–10 項工作任務」，**本指引正文查無此數字**，只有「建議 2 層為主」。
> 不得把它寫成官方規定。

## 4. 由證據導出的第一版判準

### 4.1 Task 成立條件（取代含糊的六項檢查敘述）

一個 Task 候選成立，必須同時滿足：

1. 可寫成 `action + object (+ purpose/result)` 的單句，不需要分號；
2. 所有動作**共享同一個 purpose/result**；
3. 有可辨識的關鍵工作產出，或有可描述的成功判準（iCAP 二擇一）；
4. 是本人目前的責任（actor／time 由 Source 判定，不在本研究範圍）。

不滿足 3 時 → `clarify`，不得先建 Task。不滿足 1–2 時 → 觸發 split 檢查。

### 4.2 Enabler 硬規則

工具、程式語言、系統、方法、知識、技能一律進 enabler 欄位。
**任何情況下都不得單獨成為 Task**，包括員工大量描述它的時候。
它們可另作 Knowledge／Skill 候選（支持度依 ADR 0040 決定 29–31）。

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

**平手時偏向合併**：O\*NET 明示 cluster 應寫成盡可能少的敘述、單一為佳。
這與 repo 既有的「持平選較簡單者」一致。

### 4.5 不是 include／exclude，是 Core／Periphery

正式低頻責任、支援性工作不應被排除，應標為 periphery。
排除只留給：他人責任、過去工作、一次性支援、純工具／步驟、員工明確否認、證據不足——
且**排除理由必須分開保留**，不可壓成單一「已排除」狀態。

## 5. 同一性判準與動作對照

| 新內容 vs 既有 Task | O\*NET 分類 | 系統動作 | identity 規則 |
|---|---|---|---|
| 換句話說，無新資訊 | Duplicative | `no_change` + 追加 source support | 既有 ID 不變 |
| 重疊但帶新內容 | Overlapping | `revise` | **保留既有 ID**，敘述改寫 |
| 完全不同的工作 | Unique | `add` | application 配發新候選 ID |
| 兩個既有候選其實是一件事 | Task Joining | `merge` | 明列來源 ID；產生的 Task 取其一為存續 ID，其餘標為被併入 |
| 一個既有 Task 內含兩個獨立結果 | Task Separation | `split` | 明列來源 ID；產生的每個新 Task 都記錄 parent ID |
| 不成立、他人、過去、否認 | Task Deletion | `withdraw` | 既有 ID 不刪除，標為撤回並記錄理由型別 |

## 6. 對契約的直接含意

1. **Task 不能只存一個 `task_statement` 字串。** 至少要分開存 `action`／`object`／`purpose_result`／
   `enabler`／`context`。否則 §4.3–4.4 的判準無法機械檢查——「兩個候選 purpose/result 是否相同」
   是 merge 提示的核心訊號，字串比對做不到。
2. **identity 在候選建立時就配發，不等員工接受。** 否則跨回合無法 `revise`／`merge`，
   每輪只能重複提案。員工接受是把候選送進 Current JD，不是產生 identity。
3. **模型不得自造 ID**，只能引用 Context Packet 提供的既有 Task；引用形式建議用 context-local ordinal
   而非 UUID 字串（沿用 repo 既有 `question.select` 只回 ordinal 的作法）。
4. **一輪可含多個 proposal**，因此需要衝突規則：同一 target 被兩個 proposal 指涉時**兩者都拒絕**
   （沿用既有 verifier 對 duplicate correction target 的裁決，不任選贏家）；
   `merge` 的來源必須兩個以上且都存在；`split` 的來源必須存在且不得同時被 `withdraw`。
5. **verifier 可機械檢查的項目**：分號、多 purpose/result、enabler 欄位混入 action、
   引用 ID 不存在、merge/split 來源數量、產出與行為指標同時為空。
   其餘（是否真的太相似）仍是語意判斷，由 rubric 與人工審查承擔。

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
