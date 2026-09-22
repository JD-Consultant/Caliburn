# 0048. OPKS：證據兩軸、文件層 K/S/A、與外部指涉的門檻規則

- 狀態：Accepted
- 日期：2026-08-01
- 部分翻案：[0040](0040-professional-consultant-engine-and-r1-validation-contract.md)
  **決定 29–30**（支持度四級）。**決定 31–34 不變且被本 ADR 強化**。
- 研究：[OPKS 設計裁決](../specs/2026-08-01-opks-design-decisions-research.md)與五份原料
  （[效度與法規](../specs/2026-08-01-opks-raw-validity-and-ai-regulation.md)、
  [工作產出](../specs/2026-08-01-opks-raw-work-outputs.md)、
  [行為指標](../specs/2026-08-01-opks-raw-performance-indicators.md)、
  [skills taxonomy](../specs/2026-08-01-opks-raw-skills-taxonomies.md)、
  [LLM 生成](../specs/2026-08-01-opks-raw-llm-generation-grounding.md)）
- 審查：外部審查者兩輪（2026-08-01）；三項事實更正已於 `a464f42` 落地

## 脈絡

`app/job_analysis` 目前只做 Task。下一格是每個 Task 的工作產出(O)／行為指標(P)／
知識(K)／技能(S)與文件層態度(A)——**全份資料裡最容易被模型憑空填滿的一格**。

0040 決定 29–30 為 K/S/A 與指標數值門檻定了**線性四級支持度**
（`behavior_grounded`／`employee_confirmed`／`reference_candidate`／`unsupported`）。
本輪研究與外部審查發現該四級有三個問題：

1. **四級之間沒有可信的全序關係。** `employee_confirmed` 與 `reference_candidate` 是
   兩組不同的優缺點，不可比較：Morgeson et al. (2004, *JAP* 89(4), 674–686) 的田野實驗顯示
   在職者對 ability 陳述系統性超額認領（H1 d≈.52；連研究者編造的 bogus ability 都認領，d=.55），
   同文 p.683 則指非在職者判斷 "less likely to be systematically inflated"。
   在**膨脹**軸上參考來源較乾淨，在**本職特異性**軸上員工來源較好。把兩者排成上下是把
   兩個正交軸壓成一維的後果。
2. **一個欄位同時回答三個不同問題**：證據來源是誰、有沒有連上 Task、員工對自己文件的決定權。
3. **`unsupported` 是一個不該存在的合法狀態。** 它描述的是「模型憑空生成」，
   那不是一種證據等級，是一筆不該被寫入的資料。

另外，本 repo 先前把 iCAP 的「知識、技能、態度**對應行為指標**」讀成單一所有權。
這是誤讀，已於 `a464f42` 更正。

## 決定

### A. 證據標記改為兩個正交軸（翻案 0040 決定 29–30）

```
evidence_origin: employee | reference
task_linkage:    linked | unlinked
source_refs[]:   非空 —— 型別層不變量
```

1. `evidence_origin` 指**證據來源**，不是文字作者。模型從員工描述的 Task／故事推導出的 K/S，
   其 origin 是 `employee`（證據來自員工回合），模型只是候選的作者；作者身分由既有
   `SourceRef.kind`（`employee_turn`／`direct_edit`／`proposal_decision`）承載。
2. **不採 `observed`。** 本產品從未觀察工作現場，只有員工自述。
   29 CFR §1607.14C(4) 要求的是 K/S「operationally defined **in terms of** observable aspects of
   work behavior」——那是對**定義方式**的要求，不是宣稱分析者已直接觀察。用 `observed`
   會宣稱我們沒有的東西。`linked`／`unlinked` 只陳述「有沒有連上本職 Task」，可誠實驗證。
3. `source_refs[]` 非空寫成**型別層不變量**，與 `Task` 既有的
   「active task 至少一條有效 SupportLink」同構。**因此 `unsupported` 不再是合法領域狀態**：
   拿不出來源的 K/S 無法被建構，只能停在暫時的模型輸出或被 verifier 拒絕，不得進 Work Model。
4. **`employee_confirmed` 移出證據軸。** 員工確認由既有產品權威層表達
   （Proposal 決策與 Current JD membership）。這讓 0040 決定 31
   「員工按接受不得被記錄成已有行為證據」從**要記得遵守的規則**變成**結構上無法違反**。

四種合法組合：

| 情境 | `evidence_origin` | `task_linkage` |
|---|---|---|
| 從員工 Task／故事推導 K/S | `employee` | `linked` |
| 員工直接新增、無 Task 依據 | `employee` | `unlinked` |
| 公版候選已對上本職 Task | `reference` | `linked` |
| 尚未對上本職工作的公版候選 | `reference` | `unlinked` |

### B. 掛載形狀依 iCAP 官方編碼，K/S/A 正規化到文件層

```
Task
├─ outputs[]          官方 O1.1.1 —— 任務層階層編號
└─ indicators[]       官方 P1.1.1 —— 任務層階層編號

Document
├─ knowledge_skills[] 官方 K01／S01 —— 文件層平坦編號
│   ├─ task_refs[]
│   └─ indicator_refs[]      optional
└─ attitudes[]        官方 A01 —— 文件層平坦編號
```

5. O/P 掛 Task、K/S/A 掛文件的不對稱**不是實作方便，是官方編號本來就這樣分**：
   《職能基準發展指引》表單 F3-3（p73）的 O/P 採任務層階層編號，而 K/S/A 採**文件層平坦編號**，
   與 iCAP 明文規定為文件層的態度**編號形式相同**。
6. **一條 K/S 不由單一 Indicator 擁有**，與 Task／Indicator 是多對多 references。
   官方規則「對應行為指標」的明文目的是「**為避免相同職能重複出現**」；
   單一所有權會在一項知識支援多條指標時**強迫複製**，恰好製造該規則要避免的重複。
7. 匯出時不必複製 K/S——公版表格本來就是文件層編號。UI 可把 K/S 投影在 Task 或 Indicator 底下。

### C. 生成粒度

8. 員工**選定單一 Task 後按需生成**該 Task 的 O/P/K/S；**不自動對 N 個 Task 發 N 次請求**。
   態度走文件層另處理。
9. 生成時把文件內既有 K/S 帶入 context 以避免跨 Task 重複——這是文件層模型的必然結果。
10. 依 ExtractBench（arXiv 2602.12247v2, 2026），結構化生成的綁定變數是**單次輸出總量**
    （369 欄位下無模型能產出有效結果，整體通過率 4.6%）。product domain 可以豐富，
    **model-facing wire schema 維持輕量**。

### D. 不綁外部 taxonomy

11. 第一版 K/S **不綁** ESCO／O\*NET／Lightcast／SFIA，維持繁中自由文字＋文件內去重。
    官方給的受控詞彙理由只有「跨系統互通」，而本產品本機、單文件、不跨組織，該收益趨近於零；
    四套詞彙表皆無繁體中文；綁定會把員工的真實知識壓成清單裡最接近的通用詞，破壞證據可追溯性。
12. **不預留永遠空著的 external code 欄位。** 內部穩定 ID 已足夠，真要接再升契約。
13. taxonomy 改作**撰寫判準的教材**（例如 ESCO 的「知識寫成名詞、不加動詞」），不作下拉選單。

### E. 訪談：behavior-first，但員工保有完整裁決權

14. **禁止直接問「你需要什麼知識／技能／能力」。** 依 Morgeson，
    「ability to」句式本身就足以造成 d≈.5 量級的膨脹；OPM 亦明文禁止
    "Ability to (perform a task)" 的能力陳述句式。
15. 流程：問 Task／事件／做成與做壞的差異 → 模型產生 K/S 候選 → 綁定具體 Task 與來源 →
    員工可 **confirm / edit / add / reject / unknown**。
16. **不採「只能否決」**。候選清單本身即可能造成認領偏誤，而 Morgeson 未證明否決介面能消除膨脹；
    且員工對自己的 Current JD 有文件權威，必須能新增。員工新增走 `direct_edit` SourceRef、
    `evidence_origin = employee`，有 Task 依據才 `linked`；
    **不得因員工按確認而升級為 `linked`**。
17. 確認時使用對比追問，例如「這是完成該 Task 不可缺少的知識，還是你目前剛好使用的工具／方法？」

### F. 工作產出與指標門檻

18. 無實體交付物時，產出寫成**維持的狀態／避免的後果／遵循的規章**，不寫行為本身。
    依據為香港 QF 官方資料庫全量：1,351 筆 UoC 中 1,337 筆（98.9%）帶
    `integrated outcome requirements`，其中 178 筆用 `so as to`、48 筆用 `in accordance with`、
    53 筆用 `Capable of monitoring`。
19. **連狀態、後果、規章都寫不出來 ⇒ 標記該 Task 邊界可疑，回到 `work.reconcile`，不補 O。**
    此為合成判準（O\*NET 的 task 定義以 meaningful outcome 為成立要件 ＋ OPM 未連結者雙向刪除
    ＋ iCAP 允許省略的是欄位而非成果），**無單一官方條文，ADR 據實標註**。
20. **數值與外部指涉三檔**：
    - 具名法規／SOP／規章／明確約定，或員工逐字說出的數值 → 可寫（附 quote）；
    - 員工逐字只說「依公司程序」→ **忠實保留**，但不宣稱已可查核；重要時才追問具體名稱；
    - 員工未提 → **禁止**模型自行補「依公司規定」「於適當時間內」這類句子。
21. 沒有數值也沒有指涉 → **門檻留空**。**不必為每一格建立 open issue**；
    只有缺口會妨礙主要 Task 的理解或驗證時才追問。
22. 界線是**條件必須指名一個真實存在的外部指涉**，不是「禁止質性條件」——
    澳洲 `according to organisational procedures`、新加坡 `In accordance with: 僱傭法…`（27 次）、
    香港 `in accordance with clearly defined company procedures`（48 筆）都是官方常態寫法。
23. 四個政府體系（香港全量 1,351 筆、新加坡、澳洲單元本體、美國 OPM 能力定義）
    在**職務描述層**的數值門檻皆為 **0**；澳洲的次數門檻住在獨立的 Assessment Requirements 元件，
    OPM 的數字住在評分量表。**數字屬於「怎麼驗證」那一層，不屬於「工作是什麼」那一層。**

### G. verifier 與 rubric 的分界

24. **只有機械可判定且無語意歧義的才進 deterministic verifier**，第一版只有三類：
    引用逐字比對（已實作）、ID／參照合法性、`source_refs[]` 非空。
25. **降為 linter／rubric，不得整筆拒絕**：
    - 程度修飾詞（熟悉／精通／良好的／基本的…）——「基本工資」是真實反例，
      HR 職務的知識項寫「勞基法基本工資規定」完全合理，硬擋會誤殺；
    - `ability to`／「具備…之能力」句式——可偵測並要求改寫，不讓整次輸出失敗；
    - 「知識用名詞、技能用動詞」——繁中無詞性形態標記（「操作」兼具兩者），屬語意判斷；
    - 數字**是否逐字存在**可機械驗證，但**該引文是否真的支持該門檻**仍由 rubric 判斷。

### H. 態度與產品用途

26. **Attitude 第一版預設為空。** 只有具體、與工作有關、能連回行為的傾向才建立；
    不得從聊天語氣推人格。iCAP 官方亦明訂偏特質項目不納入職能基準。
27. 第一版效度承諾鎖成：**本文件適合描述與整理該員工目前職務，不是經多來源職務分析驗證的
    招募、甄選、薪酬、升遷或績效評量標準。** 於 UI 與匯出保留用途聲明與證據標記。
28. **員工文件權威與外部效度是兩件事**：員工決定自己的 Current JD 寫什麼；
    但單一員工確認**不足以**支撐組織級決策。0040 決定 33（匯出標示為客製 JD）由本條強化。
29. 若未來要支援招募或考核，**另開產品切片**，至少補主管／SME／多位 incumbent 來源與該用途的
    效度研究；**不得由這份單一員工 JD 自動升格**。

## 依據

四個政府體系與兩份學術原著的一手證據見研究檔案；每份附原始網址與重現指令。
本 ADR 只記錄與既有設計不同或會被誤解的部分。

**不採外部審查者原提的兩項**（經查證後由審查者自行撤回或修正）：
`behavior_basis: observed|claimed|none` 因 `observed` 過度宣稱而改為 `task_linkage`；
「第一版尚不存在的 reference-linked Task」不作為翻案理由（公版 Challenger 尚未實作，
該案例現階段不可能發生），改以本 ADR〈脈絡〉的三項理由為準。

**已撤回、不得恢復**：在員工可見的候選清單中混入 bogus 參照 K/S 作為品質閘。
bogus item 在 Morgeson 原著中是**測量工具**，從未作為介入被驗證；
在員工自己的文件裡設陷阱與「員工是自己 JD 權威」的產品前提直接衝突；
且無經驗門檻可決定何時降級整場訪談。僅保留為離線 eval fixture。

## 後果

正面：

- 證據欄位不再假裝有自然順序；`unsupported` 與「員工確認＝證據」兩個錯誤狀態變成**不可表示**。
- K/S 正規化消除跨 Task 重複，且匯出天然對齊 iCAP 文件層編號。
- 語意規則降為 rubric 後，模型不會因為中文詞性判斷失誤而整輪作廢。

負面／風險：

- 翻案 0040 決定 29–30，既有文件與 `evals` 若已寫入四級字串需一併更新（目前程式碼尚未實作，
  成本僅限文檔）。
- 兩軸 + refs 比四級字串複雜，UI 需要把兩軸投影成員工看得懂的標示；投影規則未定。
- `task_linkage` 只說有沒有連上，不說連得好不好。連結品質仍需 rubric，第一版無自動判準。
- 第一版不綁 taxonomy，若日後需要跨文件技能盤點，補綁的遷移成本由未來承擔（已知取捨）。
- 判準 19（產出寫不出來就質疑 Task）為合成判準，無官方條文背書，需以真實訪談驗證。
- 「員工通常說不說得出數值或規章名稱」**無任何真人資料**；判準 20–21 的實務效果未知。
