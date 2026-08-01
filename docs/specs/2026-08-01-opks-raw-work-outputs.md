---
title: 工作產出（O）的權威處理 —— 無形產出、outcome 陳述與「產出缺失」的訊號價值（研究原料）
date: 2026-08-01
purpose: 補 OPKS 研究缺口 C；iCAP 有獨立「工作產出」欄位而國際體系都沒有，本檔找出可替代的權威做法
source_discipline: 只收官方一手；每條引文附可複核定位；取得失敗與未核實項目一律列入 §8
review_note: 本檔供第三方人工審核。§0.2 提供完整重現步驟，所有引文可用 Ctrl-F 在重現的檔案中定位
---

# 工作產出（O）的權威處理（研究原料）

## 0. 取得狀態與複核方法

### 0.1 取得狀態

| 來源 | 狀態 |
|---|---|
| **香港 QF 官方資料庫**（`hkqf.gov.hk` API，物流業全量） | ✅ **官方一手**，JSON 7.9 MB，**1,351 筆 UoC**、5 個 branch；每筆帶 `uoc_code`／`old_uoc_code`／`uoc_version`／`uoc_rev`／`uoc_level`／`uoc_credit` 與逐欄 HTML 內容 |
| 香港 QF《SCS for the Logistics Industry》PDF（HKU SPACE 轉載） | ✅ PDF 全文 13,202 行。**現降為佐證副本**——其內容已與官方資料庫逐字比對一致（見 §1.3） |
| 美國 OPM *Delegated Examining Operations Handbook*（Appendix D／G） | ✅ PDF 全文，抽出 **12,794 行**；文件自帶 `Page D-1` 式頁碼標記，可核實 |
| 美國 OPM *Job Analysis Template* | ✅ PDF 全文，10 頁 |
| O\*NET *Task Writing Guidelines*、台灣 iCAP《職能基準發展指引》 | ✅ 前輪已逐字核實，見 §7 |
| Gilbert《Human Competence》accomplishment 原文 | ❌ **未取得**，詳見 §5 |

### 0.2 複核方法（審核者可完整重現）

```bash
# 香港 QF 官方資料庫（主來源）
#   官方站是 Nuxt SPA，頁面本身沒有內容；資料在 /api/content/{lang}/record/{industry}-scs
curl -sSL -A "Mozilla/5.0" -o hk-api-scs.json \
  "https://www.hkqf.gov.hk/api/content/en/record/logistics-scs"   # → 7,907,596 bytes

# 香港 SCS PDF（佐證副本）
curl -sSL -A "Mozilla/5.0" -o hk-scs.pdf \
  "https://hkuspace.hku.hk/f/rpl/103620/e_lo_tw.pdf"
pdftotext -layout hk-scs.pdf hk-scs.txt      # → 13,202 行

# 美國 OPM
curl -sSL -A "Mozilla/5.0" -o opm-deoh.pdf \
  "https://www.opm.gov/policy-data-oversight/hiring-information/competitive-hiring/deo_handbook.pdf"
pdftotext -layout opm-deoh.pdf opm-deoh.txt  # → 12,794 行

curl -sSL -A "Mozilla/5.0" -o opm-ja.pdf \
  "https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_handout.pdf"
pdftotext -layout opm-ja.pdf opm-ja.txt      # → 10 頁
```

本檔每條引文都標「**定位**」，可直接 `grep`／Ctrl-F 於上述輸出檔中驗證。
**行號會因 poppler 版本而異，故定位一律用可搜尋字串或文件自印的頁碼，不用行號。**

### 0.3 抽字警告（審核時務必注意）

香港 SCS 的 UoC 是**雙欄表格**。`pdftotext -layout` 會把左欄的欄位標籤與右欄的值**錯開一行**
（因為 `Range` 的值折了兩行）。原始抽出文字長這樣：

```
3. Range       This unit of competency is applicable to logistics service providers. Practitioners should be
4. Level       capable of using basic warehousing terms, codes and abbreviations.   ← 這其實是 Range 的第二行
5. Credit      1                                                                    ← 這其實是 Level
6. Competency  3 (for reference only)                                               ← 這其實是 Credit
7. Assessment  Performance Requirements: …                                          ← 這其實是 Competency
```

**正確對應見 §1.3 的還原表。** 不註明這一點，審核者會誤判本檔讀錯欄位。

---

## 1. 香港 SCS：`integrated outcome requirements`

### 1.1 官方對 UoC 內容的定義（逐字）

**定位**：Chapter 2 "Hong Kong Qualifications Framework"，編號第 22 段；文件自印頁碼 **8**。

> "22. The Logistics ITAC is responsible for the development of a **task-based SCS** for the core
> functional areas of the industry. The SCS, being comprised of Units of Competencies (UoCs), provides
> not only **quantitative and qualitative specifications on the competencies required for specific
> tasks**, but also **the integrated outcome requirements** as well as information on the QF level and
> credits."

**定位**：同章 "QF Levels"，第 25 段末；文件自印頁碼 **9**。

> "A QF level is assigned to every UoC (Chapter 4) with reference to the GLDs… Therefore,
> **QF level assignment is essentially a holistic judgment on the unit's integrated outcome
> requirements.**"

→ 這兩段確立兩件事：（a）`integrated outcome requirements` 是**與能力規格並列的獨立成分**，
不是摘要；（b）它是**判級的依據**——級別判在成果上，不判在行為清單上。

### 1.2 QF 的四個級別維度（逐字，第 25 段）

> "a. Knowledge and intellectual skills; b. Processes; c. Application, autonomy and accountability;
> d. Communication, IT and numeracy."

（供日後與 SFIA 四軸、EQF 三維對照用；本輪不做判級設計，見
[行為指標原料](2026-08-01-opks-raw-performance-indicators.md) 判準 D-8。）

### 1.3 一個完整 UoC（逐字全文還原）

**定位**：`grep -n "LOWHOM101A"`；文件自印頁碼 **34**，屬 "Competency Level 1" 區塊。

| 欄位 | 值（已依 §0.3 還原欄位對齊） |
|---|---|
| 1. Title | Understand logistics and warehousing terminologies |
| 2. Code | LOWHOM101A |
| 3. Range | "This unit of competency is applicable to logistics service providers. Practitioners should be capable of using basic warehousing terms, codes and abbreviations." |
| 4. Level | 1 |
| 5. Credit | 3 (for reference only) |
| 6. Competency | 見下方 Performance Requirements 全文（官方欄位 `uocItemDescEng_Competency_1`／`_2`） |
| 7. **Assessment Criteria** | **`integrated outcome requirements` 就住在這一欄**（官方欄位 `uocItemDescEng_Criteria`）。見下方 |
| 8. Remarks | 空 |

**官方識別碼（取自 API，PDF 上沒有）**：現行 `uoc_code` = **104734**；`old_uoc_code` = `LOWHOM101A`；
`uoc_version` = **A**；`uoc_rev` = **01**；分類路徑 = Logistics → Terminals, Warehouse & Logistics Centre
→ Operation Management。

> **修正一處先前的判讀錯誤。** 本檔前一版把第 7／8 欄記成「未印內容」——那是 PDF 雙欄排版
> （§0.3）造成的誤讀。官方資料證明**成果陳述正是 Assessment Criteria 欄的內容**。
> 這一點不是細節：它表示香港把「成果」放在**評量準則**的位置，與 §1.1 第 25 段
> 「QF level assignment is essentially a holistic judgment on the unit's integrated outcome
> requirements」完全一致——**成果是判級與評量的依據，不是描述的裝飾。**

**Competency 欄全文（逐字）：**

> "**Performance Requirements:**
> **6.1 Understand logistics and warehousing terminology**
> · Understand the logistics workflow and relevant terms
> · Understand warehousing terms
> · Understand trade related terms
> · Understand the loading/unloading operations of container and terminal, and relevant terms
> · Understand abbreviations and terms used in freight documents
> · Understand abbreviations and terms used in the calculation of freight charges
> · Understand names of the countries, areas and ports
> · Understand the abbreviations commonly used in warehousing and logistics
>    ○ Understand the meaning of the abbreviations
>    ○ Understand the conversion of the abbreviations in English or Chinese
>    ○ Understand ways to inquire or consult about warehousing abbreviations commonly used
> · Understand names and abbreviations of different weights and measurements
> · Understand names and abbreviations of different currencies
> · Understand the expression of international time
> · Understand ways to inquire or consult about the meanings of the aforesaid codes and terms
> **6.2 Apply basic warehousing terms, codes and abbreviations**
> · Apply appropriate warehousing terms to communicate with counterparts, customers and colleagues
>   effectively, e.g. receiving and conveying information
> · Use logistics and warehousing terms to complete logistics and trading documents
>
> **The integrated outcome requirements of this unit of competency is:**
> · **Capable of using warehousing terms, codes and abbreviations correctly in general communication
>   and document handling so as to avoid delays, mistakes or losses caused by wrong use of terms**"

**這一則是本檔最重要的單一證據**：一個**完全沒有實體交付物**的知識型單元，
它的「成果」寫成 **能力 + 對象 + 正確性條件 + 所避免的損害**。

### 1.4 全體系統計：這不是特例，是體系性欄位

**以官方資料庫全量計數**（指令見 §0.2；`uocItemDescEng_Criteria` 欄）：

| 指標 | 數字 |
|---|---|
| 物流業官方 UoC 總數（5 個 branch） | **1,351** |
| Criteria 欄含 `integrated outcome requirements` | **1,337（98.9%）** |
| Criteria 欄含 `Capable of` 句式 | **554** |
| Criteria 欄含 `so as to`（目的／後果子句） | **178** |
| Criteria 欄含 `in accordance with`（遵循規章） | **48** |
| Criteria 欄含 `Capable of monitoring`（狀態維持） | **53** |
| **Criteria 欄含數值門檻樣式**（`\d+%`／`at least \d`／`within \d+ days` 等） | **0** |

**最後一列是本檔最強的單一數字：1,351 筆政府官方能力單元，零個數值門檻。**
（跨體系比對見[行為指標原料](2026-08-01-opks-raw-performance-indicators.md) §3b。）

### 1.5 官方實例（逐字，附官方代碼可核對）

以下取自官方資料庫，證明 §1.7 的句式歸納非單一特例：

| 官方代碼／舊碼 | 逐字（已去 HTML 標籤） |
|---|---|
| `109710` / `LOCUOM505B` | "Capable to formulate a comprehensive project management plan **in accordance with** special technical or professional requirements for an individual logistics project and requirements specified by the customer **so as to** ensure successf…" |
| `109708` / `LOCUOM503B` | "Capable to formulate recruitment strategies **in accordance with** the requirements on the company's development and operation, **the legal requirements** and special technical requirements on daily logistics operation" |
| `109821` / `LOCUCT504B` | "Capable of analysing freight transit requirements; Capable of planning the procedures and systems for freight transit; **Capable of monitoring freight transit and ensure the compliance of designed quality standard** and international…" |
| `109846` / `LOCUSS601B` | "Capable of applying knowledge of security procedures; Capable of assessing security risks; Capable of specifying security requirements and establishing implementation strategies" |

### 1.6 PDF 版的其他實例（逐字，與官方一致）

以下 7 則取自 PDF 副本，用以呈現較短、較易讀的句式；其代碼可於官方資料庫以 `old_uoc_code` 反查：

| # | 定位（可 grep） | 逐字 |
|---|---|---|
| 1 | 同頁 33 之貨物交付 UoC | "Capable of inspecting and sorting cargoes for delivery" / "Capable of using appropriate equipment to sort and shift cargoes" / "Capable of completing required records or notices" |
| 2 | 回收物料 UoC | "Capable of preparing work" / "Capable of using appropriate methods to remove reclaimed materials and clean up materials **in accordance with clearly defined company procedures and instructions**" |
| 3 | 危險品文件 UoC（註明 "adapted from the Logistics UoC LOCUIE203A"） | "Capable of describing the processes of handling documents for dangerous goods, prohibited articles and dutiable commodities" / "Capable of **handling errors and omissions in the processes, taking remedial actions, and advising relevant persons**" |
| 4 | 工作文件 UoC，頁 41 | "Capable of preparing, producing and completing workplace documents" |
| 5 | 工作場所整理 UoC，頁 43 | "Capable of identifying workplace housekeeping procedures" / "Capable of **monitoring the tidiness and cleanliness of workplace**" / "Capable of carrying out work housekeeping activities" |
| 6 | 危險品知識 UoC（"adapted from … LOCUSS202A"） | "Capable of understanding dangerous goods and their characteristics" / "Capable of applying basic knowledge of dangerous goods" |

### 1.7 句式歸納

| 成分 | 有形交付物（例 #1、#4） | 無形／狀態維持（§1.3、§1.6 例 #2、#5） |
|---|---|---|
| 能力 | Capable of completing | Capable of using … correctly／Capable of monitoring |
| 對象 | required records or notices ／ workplace documents | warehousing terms ／ the tidiness and cleanliness of workplace |
| 結果 | 交付物本身即結果 | **so as to avoid delays, mistakes or losses**（§1.3）／**in accordance with clearly defined company procedures**（例 #2） |

→ **判準 C-1：無實體交付物時，「產出」寫成「維持的狀態」或「避免的後果」或「所遵循的規章」，
永遠不寫行為本身。** 三種收尾方式都有逐字實例。

> 例 #2 的 "in accordance with clearly defined company procedures and instructions" 與新加坡的
> `Performance Expectations` 寫法同源，見[行為指標原料](2026-08-01-opks-raw-performance-indicators.md) §3d。

### 1.8 誠實記錄一個權威衝突

§1.3 的 6.1 底下連續 **15 條**以 "Understand" 起首。這**直接違反** Bloom 修訂版的可觀察動詞規則
——Airasian & Miranda 明言 "Ambiguous verbs such as 'state,' 'list,' 'demonstrate,'… should be used
with great care"；Krathwohl 更點名 "understand" 可涵蓋從記憶到綜合的任何層次
（逐字見 [2026-07-13 國際體系原料](2026-07-13-ai-redesign-raw-intl-competency-standards.md) §3a）。

**不要假裝各權威一致。** 本 repo 應採 Bloom／O\*NET／OPM 這一系的可觀察動詞要求
（理由見 §2.1 的 OPM 規則），並把香港的**成果句式**（§1.7）與其**動詞用法**分開採用。
——這是本檔唯一一處明知而不採用來源做法的地方，理由已寫明。

### 1.9 數值門檻

抽出全文中，Performance Requirements 與 integrated outcome requirements
**未出現任何數值門檻**（無百分比、無時限、無次數）。
跨體系比對與計數方法見[行為指標原料](2026-08-01-opks-raw-performance-indicators.md) §3b。

---

## 2. 美國 OPM：能力必須連回任務，否則刪除（雙向）

### 2.1 能力撰寫規則（逐字）

**定位**：Appendix D "OPM's Job Analysis Methodology" → "How Competencies Should be Written"；
文件自印頁碼 **Page D-1**。

> "You should define competencies simply and clearly and make sure that they embody **a single, readily
> identifiable characteristic**. **Avoid stating a competency in way that would confuse it with a task —
> as frequently happens when competency statements begin with a statement such as 'Ability to (perform a
> task).'** It is also good practice to make the competency definitions **behaviorally based** to the
> extent that an individual possessing that competency **can be assessed through measurable behaviors**.
> One way to do this is to **incorporate action verbs into the competency definitions (except for
> definitions of knowledge areas)**."

> "**Qualifiers such as 'thorough' knowledge, 'considerable' skill, or 'basic' understanding, are
> unnecessary. These qualifiers should not be part of the competency definition — they do not provide
> meaningful information to distinguish examples of performance clearly.**"

（此兩條的判準化見[行為指標原料](2026-08-01-opks-raw-performance-indicators.md) §2。）

### 2.2 Uniform Guidelines 要求 task↔competency linkage（逐字）

**定位**：Appendix D → "Task and Competency Linkages"；Page D-1。

> "The Uniform Guidelines also require that **the tasks and competencies be linked to demonstrate the
> respective job-relatedness of competencies**. The linkage also ensures that there is **a clear
> relationship between the tasks performed on the job and the competencies required to perform those
> tasks**."

### 2.3 未連結者一律刪除——**而且是雙向的**（逐字）

**定位**：*Job Analysis Template*，"Steps 6 – 8: Task and Competency Linkages"，Step 6。

> "c) Next, have each SME work independently to rate the extent to which each competency is important
> for effective task performance… It is recommended that a cutoff of 3.0 be used for this scale to
> determine which competencies are linked to each task. **(Note: If any tasks/competencies are not
> linked, you should reconsider whether all critical tasks and competencies have been considered)**; and
>
> d) You and SMEs should then **eliminate any tasks not linked to one or more competencies** and only
> competencies that are not linked to at least one task."

### 2.4 OPM 把數字放在哪裡（逐字，供 §4 與 D 檔交叉引用）

**定位**：*Job Analysis Template*，"Job Analysis Worksheet for Tasks"／"…for Competencies"。

> **Importance Scale** — "0 = Not Performed / 1 = Not Important / 2 = Somewhat Important /
> 3 = Important / 4 = Very Important / 5 = Extremely Important"
> **Frequency** — "0 = Not Performed / 1 = Every few months to yearly / 2 = Every few weeks to monthly /
> 3 = Every few days to weekly / 4 = Every few hours to daily / 5 = Hourly to many times each hour"
> **Need At Entry Scale** — "1 = Needed the first day / 2 = Must be acquired within the first 3 months /
> 3 = … 4-6 months / 4 = Must be acquired after the first 6 months"

→ 數字全部在**評分程序**裡，**沒有一個進入能力或任務的敘述文字**。

> **附帶發現（本產品目前沒有的區分）**：`Need At Entry` 把「入職即需」與「到職後習得」分開。
> 本 repo 的 K/S 目前無此維度。**不建議現在加**（無真實資料），但記錄為已知缺口。

---

## 3. 「產出寫不出來」是否該回頭質疑 Task？

**沒有任何體系明文寫「產出缺失 ⇒ Task 邊界有問題」**——這是誠實結論。但有三條可組合的官方依據：

1. **O\*NET 的 task 定義本身**（逐字見 [2026-07-13 原料](2026-07-13-ai-redesign-raw-intl-competency-standards.md) §1a）：
   > "Tasks are typically conceptualized as **the smallest unit of activity with a meaningful outcome**."

   → outcome 是 task **成立的定義要件**，不是可選欄位。寫不出 outcome 的東西不符合 task 的定義
   ——它可能是步驟、工具或動作。
2. **OPM 的雙向刪除規則**（§2.3）：官方在 linkage 缺失時要求**重審兩邊**，不是單向補齊。
3. **iCAP 的合法例外有明確邊界**（逐字，指引 p37；見 [iCAP 原料](2026-07-13-ai-redesign-raw-icap-field-standards.md) §4）：
   > 「若該項任務**僅有行動或操作性質之工作成果**，則不必列出工作產出，
   > 建議將相關成果**列於行為指標之描述中**」

   → iCAP 允許省略的是**欄位**，不是**成果**。成果必須改寫進行為指標，仍然要存在。

**判準 C-3（三條合成）：**

| 情況 | 處置 |
|---|---|
| 有有形交付物 | 寫進 O（名詞化、可查核） |
| 無交付物但講得出「維持的狀態／避免的後果／遵循的規章」 | O 留空，成果寫進 P（iCAP 合法路徑 + 香港句式） |
| 連狀態、後果、規章都講不出來 | **不是補 O，是把該 Task 標為邊界可疑**，回到 `work.reconcile` |

> **第三列是本 repo 自行合成的判準，無單一官方條文可引。** 它由 O\*NET 的定義要件 + OPM 的雙向規則
> 推導而來，**必須在 ADR 中如實標註為合成判準**，不得寫成「依據 O\*NET 規定」。

---

## 4. 產出欄位的國際地位（再確認）

| 體系 | 有無獨立 output／deliverable 欄位 | 產出住在哪 |
|---|---|---|
| 台灣 iCAP | ✅ **有**（工作產出 O，編碼 O1.1.1） | 獨立欄位，可合法省略 |
| 香港 QF SCS | ❌ 無 | `integrated outcome requirements`（成果陳述，非交付物清單） |
| O\*NET | ❌ 無 | task 句的 Purpose/Result（"to…"） |
| UK NOS | ❌ 無 | function／key purpose |
| ESCO／SFIA | ❌ 無 | — |

→ **判準 C-4：iCAP 的獨立 O 欄位是國際例外。** 內部模型不必以它為結構主軸；
它是**匯出時的投影欄位**。這與 [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)
決定 33–34（匯出只採 iCAP 版型、不自產基準代碼）方向一致。

---

## 5. Gilbert 的 accomplishment（**未取得一手，僅供背景，不得引用**）

Thomas F. Gilbert《Human Competence: Engineering Worthy Performance》（McGraw-Hill, 1978；
HRD Press／ISPI Tribute edition, 1996）提出 behavior 與 accomplishment 的區分，
以及 First Leisurely Theorem（worthy performance = valuable accomplishments ÷ costly behavior）。

**本輪取得失敗的紀錄：**

| 嘗試 | 結果 |
|---|---|
| *JOBM* 40(1) (2019) "Human Competence Revisited: 40 Years of Impact"（tandfonline） | **HTTP 403** |
| 專書全文 | 無公開來源 |
| 其餘搜尋結果 | 課程 wiki、廠商部落格、Goodreads 等，**不符來源紀律，全部剔除** |

→ **不得在 ADR 或 prompt 教材中引用 Gilbert 的逐字定義。**
「產出是行為的產物」這個論點改引 §1.3（香港逐字）與 §3.1（O\*NET 定義逐字），兩者皆已一手核實。

---

## 6. 判準彙整

| 編號 | 判準 | 依據強度 |
|---|---|---|
| C-1 | 無形產出寫成「維持的狀態／避免的後果／遵循的規章」，不寫行為本身 | **強**：香港 8 則逐字實例（§1.3、§1.4） |
| C-2 | linkage 缺失 ⇒ 重審兩邊，不單向補齊 | **強**：OPM 逐字（§2.3） |
| C-3 | 連成果都寫不出 ⇒ 標記 Task 邊界可疑，不補 O | **中：合成判準**，須標註（§3） |
| C-4 | O 欄位可空；獨立 O 欄位是 iCAP 特有，屬匯出投影 | **強**：五體系對照（§4） |
| C-5 | 採香港的成果句式，不採其動詞用法 | **中**：權威衝突下的取捨，理由見 §1.6 |

---

## 7. 來源總表

| # | 機關／體系 | 文件名 | 版本／日期 | URL | 取得與定位方式 |
|---|---|---|---|---|---|
| 1 | **香港教育局 QF（官方網域）** | 物流業 SCS 全量資料（`/api/content/en/record/logistics-scs`） | 每筆 UoC 自帶 `uoc_version`（A／B）與 `uoc_rev`（01）；取得日 **2026-08-01** | https://www.hkqf.gov.hk/api/content/en/record/logistics-scs | curl → JSON 7.9 MB／1,351 筆；定位用 `uoc_code`／`old_uoc_code` |
| 1b | 同上（**HKU SPACE 轉載副本**，佐證用） | *Specification of Competency Standards for the Logistics Industry (Terminals, Warehouse, & Logistics Centre)* | 版次未印 | https://hkuspace.hku.hk/f/rpl/103620/e_lo_tw.pdf | curl + `pdftotext -layout`；**內容已與第 1 項逐字比對一致**（§1.3） |
| 2 | **美國 OPM** | *Delegated Examining Operations Handbook*, Appendix D／G | 現行線上版 | https://www.opm.gov/policy-data-oversight/hiring-information/competitive-hiring/deo_handbook.pdf | curl + `pdftotext -layout`；定位用文件自印 `Page D-1` |
| 3 | **美國 OPM** | *Job Analysis Template*（DEOH Appendix G 工作表） | 現行 | https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_handout.pdf | curl + `pdftotext -layout`；定位用步驟編號 |
| 4 | O\*NET（美國勞工部 ETA 資助） | *Appendix B: Task Writing Guidelines* | 引 Cunningham 2000 | https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf | 前輪逐字核實，見 [2026-07-13 原料](2026-07-13-ai-redesign-raw-intl-competency-standards.md) §1a |
| 5 | **台灣勞動部勞動力發展署** | 《職能基準發展指引》 | 102 年 3 月出版、**111 年 10 月修正**，80 頁 | https://icap.wda.gov.tw/ap/get_file.php?t=download&c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf | 前輪逐字核實，定位用頁碼 |

> **第 1 項的網域不是政府網域。** 內容為香港 QF 體系的官方 SCS，但取自香港大學專業進修學院轉載頁。

---

## 8. 查不到／需二次確認（誠實清單）

1. ~~香港 SCS 的版本與官方出處~~ —— **已解決（2026-08-01）**。已取得 `hkqf.gov.hk` 官方 API
   全量資料並逐字比對：§1.3 引用的單元現行官方碼為 **104734**（舊碼 `LOWHOM101A`），
   版本 A／rev 01，內容與 PDF **完全一致**（連原文的 `consul t` 空格錯字都相同）。
   比對過程另**修正了本檔一處欄位判讀錯誤**，見 §1.3 的修正框。
2. ~~香港 SCS 的跨產業一致性~~ —— **部分解決**。已驗證**物流業全 5 個 branch、1,351 筆 UoC**
   中有 1,337 筆（98.9%）帶 `integrated outcome requirements`，確認是體系性欄位而非特例。
   **仍未驗證**：其他產業（零售、保安、汽車、ICT…）是否同樣採用此欄位。
   官方 API 路徑為 `/api/content/en/record/{industry}-scs`，可用同法查證。
3. **Gilbert 一手文本** —— 未取得（§5）。ISPI 官方對 accomplishment 的定義亦未取得。
4. **香港 UoC 的 `Assessment Criteria` 與 `Remarks` 欄** —— §1.3 的 UoC 未印內容；
   是否為該產業排版特例、或該兩欄本就常留空，未確認。
5. **O\*NET 的 task 定義是否有更新版** —— 引用的 *Task Writing Guidelines* 為綠色職業專案附錄，
   引 Cunningham 2000。O\*NET 資料庫現行為 30.3，該撰寫指引是否另有新版未查。
