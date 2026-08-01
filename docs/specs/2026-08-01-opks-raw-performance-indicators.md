---
title: 行為指標（P）的撰寫紀律與數值門檻 —— Flanagan CIT 原著與 OPM 官方禁令（研究原料）
date: 2026-08-01
purpose: 補 OPKS 研究缺口 D；回答「指標怎麼寫才算可觀察」與「數字門檻該全禁還是有條件允許」
source_discipline: 只收官方一手與學術原著；取得失敗與未核實項目列入 §6
---

# 行為指標（P）的撰寫紀律與數值門檻（研究原料）

> **【現行裁決】** 本檔是**研究原料**，其中對「支持度四級」的歷史分析僅供追溯。
> OPKS 的現行裁決是 **[ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)
> ＋ [0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)
> ＋ [0050](../adr/0050-opks-proposal-minimal-shape.md) ＋ [0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)**。**引用本檔任何段落前請先確認未被三份 ADR 取代。**


## 0. 取得狀態

| 來源 | 狀態 |
|---|---|
| Flanagan (1954) *The Critical Incident Technique*, *Psychological Bulletin* 51(4) | ✅ **APA 官方 PDF 全文取得並抽字**；以下引文逐字 |
| OPM *Delegated Examining Operations Handbook*（Appendix D）+ *Job Analysis Template* | ✅ **PDF 全文取得**；逐字 |
| 香港 SCS 物流業 | ✅ 全文（見 [工作產出原料](2026-08-01-opks-raw-work-outputs.md)） |
| Smith & Kendall (1963) BARS 原著 | ❌ 未取得（付費牆）；本檔不引用 |
| **澳洲** training.gov.au：`TAEASS412`、`BSBOPS401` 的單元＋Assessment Requirements | ✅ **四份官方 PDF 全文取得**；逐字（改走 `TrainingComponentFiles` 靜態路徑） |
| **新加坡** SkillsFuture *Skills Framework for HR* | ✅ **全文取得**（9.4 MB／7,639 行）；官方網域只回 SPA 殼，改由 Wayback 對同一官方 URL 的 2025-08-05 快照取得 |
| 澳洲 AQF 的指標升階判準語言 | ❌ 未取得 |

### 0.2 複核方法（審核者可完整重現）

```bash
# Flanagan 1954（APA 官方）
curl -sSL -A "Mozilla/5.0" -o flanagan.pdf \
  "https://www.apa.org/pubs/databases/psycinfo/cit-article.pdf"
pdftotext flanagan.pdf flanagan.txt

# 美國 OPM（兩份，指令見工作產出原料 §0.2）

# 澳洲 —— 單元本體與 Assessment Requirements 是兩個獨立官方元件
B=https://training.gov.au/TrainingComponentFiles
curl -sSL -o au-taeass412.pdf     "$B/TAE/TAEASS412_R1.pdf"
curl -sSL -o au-taeass412-ar.pdf  "$B/TAE/TAEASS412_AssessmentRequirements_R1.pdf"
curl -sSL -o au-bsbops401.pdf     "$B/BSB/BSBOPS401_R1.pdf"
curl -sSL -o au-bsbops401-ar.pdf  "$B/BSB/BSBOPS401_AssessmentRequirements_R1.pdf"

# 新加坡 —— 官方網域只回 SPA 殼，改用 Wayback 對同一官方 URL 的快照；
# 首次下載會在剛好 5 MiB 截斷，必須用 -C - 續傳
curl -sSL -C - --max-time 180 -A "Mozilla/5.0" -o sg-sfw-hr.pdf \
  "http://web.archive.org/web/20250805003944id_/https://www.skillsfuture.gov.sg/docs/default-source/skills-framework/skills-framework-for-hr.pdf"
# 完整檔 9,393,552 bytes → pdftotext -layout → 7,639 行
```

**§3b 的數值計數可用以下指令重現：**

```bash
grep -icE "at least|minimum of|no fewer|[0-9]+ (times|occasions)" \
  au-taeass412.txt au-bsbops401.txt        # → 0 與 0（單元本體）
grep -icE "at least|minimum of|no fewer|[0-9]+ (times|occasions)" \
  au-taeass412-ar.txt au-bsbops401-ar.txt  # → 5 與 1（Assessment Requirements）
grep -icE "at least [0-9]|minimum of [0-9]|[0-9]+%|within [0-9]+ (days|hours|weeks)" \
  sg-sfw-hr.txt                            # → 5，逐一檢視後全為訓練補助／CPD
```

### 0.3 引用定位的限制（審核時務必注意）

**Flanagan 那份 PDF 的頁面結構是壞的。** `pdftotext` 可整檔抽字，但
`pdftotext -f N -l N` 逐頁抽取回傳空白，`pdfinfo` 亦無法讀出頁數。
**因此本檔對 Flanagan 一律不標頁碼**，改用文章章節標題定位（可 Ctrl-F）：

```
THE CRITICAL INCIDENT TECHNIQUE（開篇）
BACKGROUND AND EARLY DEVELOPMENTS
DEVELOPMENTAL STUDIES AT THE AMERICAN INSTITUTE FOR RESEARCH
STUDIES CARRIED OUT AT THE UNIVERSITY OF PITTSBURGH
USES OF THE CRITICAL INCIDENT TECHNIQUE
SUMMARY AND CONCLUSIONS
```

期刊頁範圍 51(4), 327–358 取自書目資料，**非本檔自行核實的頁碼**。
OPM（自印 `Page D-1`）與澳洲（自印 `Page 2 of 4`）的頁碼則為文件自帶，可核實。

---

## 1. Flanagan (1954)：可觀察性的原始定義

### 1a. incident 與 critical 的定義（逐字）

**定位**：開篇第三段，緊接 "The critical incident technique consists of a set of procedures…" 之後。
可 Ctrl-F `"By an incident is meant"`。（頁碼不標，理由見 §0.3。）

> "By an incident is meant **any observable human activity that is sufficiently complete in itself to
> permit inferences and predictions to be made about the person performing the act**. To be critical, an
> incident must occur in a situation where **the purpose or intent of the act seems fairly clear to the
> observer** and where **its consequences are sufficiently definite to leave little doubt concerning its
> effects**."

→ **判準 D-1：一條合格的行為證據要同時滿足三件事**——可觀察、意圖對觀察者清楚、後果明確到不容懷疑。
這正好是我們 `behavior_grounded` 該有的定義，且比「有 quote」嚴格得多。

### 1b. 1954 年就已經描述了我們今天在防的那個失敗（逐字）

Flanagan 檢視 1,000 名被淘汰飛行學員的淘汰理由時發現：

> "many of the reasons given were **clichés and stereotypes** such as 'lack of inherent flying ability'
> and 'inadequate sense of sustentation,' or **generalizations** such as 'unsuitable temperament,'
> 'poor judgment,' or 'insufficient progress.'"

以及他對 job analysis 的直接批評（逐字，引自 Aviation Psychology Program 總結卷 pp. 273–274）：

> "**Too often, statements regarding job requirements are merely lists of all the desirable traits of
> human beings. These are practically no help** in selecting, classifying, or training individuals for
> specific jobs."

→ **這是 LLM 生成 K/S/A 時最典型的失敗模式的 1954 年版本。**
「主動積極」「良好的溝通能力」「抗壓性強」與 "unsuitable temperament"、"poor judgment" 是同一類東西。
判準：**指標／能力若可以原封不動搬到任何一份職務說明書，它就是 Flanagan 說的那種 list of desirable traits。**

### 1c. 方法論核心：只要求觀察者做簡單判斷（逐字）

> "The essence of the technique is that **only simple types of judgments are required of the observer**,
> reports from only qualified observers are included, and all observations are evaluated by the observer
> **in terms of an agreed upon statement of the purpose of the activity**."

> "The accuracy and therefore the objectivity of the judgments depend on **the precision with which the
> characteristic has been defined** and the competence of the observer in interpreting this definition
> with relation to the incident observed."

> "…gathering facts in a rather objective fashion **with only a minimum of inferences and interpretations
> of a more subjective nature**."

> "**No planning and no evaluation of specific behaviors are possible without a general statement of
> objectives.**"

> "In its simplest form, the functional description of an activity **specifies precisely what it is
> necessary to do and not to do if participation in the activity is to be judged successful or effective**."

→ **判準 D-2：指標必須對照一個先講明的目的來評，而不是憑空評「好不好」。**
對映到本 repo：`Task.purpose_result` 就是那個 "agreed upon statement of the purpose"，
**指標必須掛在它下面**才有判準可言。這給 §Q2 的掛載形狀（`Task→P`）一個方法論理由，而不只是版型理由。

### 1d. 回憶衰退與選擇性回憶的實測數據（逐字＋數字）

Delco-Remy 研究中，三組領班分別以每日／每週／每兩週回報：

> "The foremen reporting daily reported **315** critical incidents; the foremen reporting weekly, **155**
> incidents; and the foremen reporting only once at the end of two weeks reported **63** incidents. Thus,
> foremen who reported only at the end of the week had **forgotten approximately one half** of the
> incidents… The foremen who reported only at the end of the two-week period appeared to have
> **forgotten 80 per cent** of the incidents observed."

以及（航管員研究）：

> "The study also demonstrated **the selective recall of dramatic or other special types of incidents.
> This bias was especially noticeable in the incidents reported several months after their occurrence.**"

→ **判準 D-3：兩條直接對映本產品的既有風險。**
（a）員工在訪談中回憶「上個月」「去年」的工作，遺失率是有實測量級的（一週約 50%、兩週約 80%）——
所以「想不起來」是正常結果，不是訪談失敗，**更不該由模型補齊**。
（b）**戲劇性事件會系統性擠掉例行工作**——這正是路線圖 §9.5 列的
「精彩事件掩蓋高頻例行工作」案例，**現在有 1954 年的實測背書**，不再只是直覺。

---

## 2. OPM：兩條可直接寫成 verifier 規則的官方禁令

**權威文件：** U.S. OPM, *Delegated Examining Operations Handbook*, Appendix D,
"How Competencies Should be Written"（p. D-1，PDF 全文取得）。

### 2a. 禁止「Ability to（做某任務）」句式（逐字）

> "You should define competencies simply and clearly and make sure that they embody **a single, readily
> identifiable characteristic**. **Avoid stating a competency in way that would confuse it with a task —
> as frequently happens when competency statements begin with a statement such as 'Ability to (perform a
> task).'**"

**這一條與 Morgeson et al. (2004) 的實證從兩個完全不同的方向指向同一個禁令**：
- OPM 的理由是**語意**——會把能力寫成任務；
- Morgeson 的理由是**實證**——光是加上 "ability to" 就造成 d≈.5 的膨脹
  （見 [效度與法規原料](2026-08-01-opks-raw-validity-and-ai-regulation.md) §3.2）。

→ **判準 D-4：`ability to` / 「能夠…」/「具備…之能力」句式在 K/S 欄位一律拒收。**
兩個獨立權威支持，可以放心寫成 deterministic 規則。

### 2b. 禁止程度修飾詞（逐字）

> "**Qualifiers such as 'thorough' knowledge, 'considerable' skill, or 'basic' understanding, are
> unnecessary. These qualifiers should not be part of the competency definition — they do not provide
> meaningful information to distinguish examples of performance clearly.**"

→ **判準 D-5：K/S 不得帶程度修飾詞。** 繁中對應的黑名單：
**熟悉／精通／良好的／深厚的／扎實的／基本的／豐富的／優秀的／一定程度的**。
這是**可直接實作的字串層規則**，成本極低、依據明確。

### 2c. 知識用名詞、技能用動詞（逐字）

> "It is also good practice to make the competency definitions **behaviorally based** to the extent that
> an individual possessing that competency **can be assessed through measurable behaviors**. One way to do
> this is to **incorporate action verbs into the competency definitions (except for definitions of
> knowledge areas)**."

→ 與 ESCO 官方規則完全一致（ESCO：knowledge 概念 "do not make use of action verbs"，
用 "fermentation process" 而非 "Know fermentation process"）。**兩個獨立體系同意，可寫成硬規則。**

---

## 3. 數值門檻：全禁還是有條件允許？

### 3a. 兩條官方要求是相反方向的

| 方向 | 來源 | 逐字 |
|---|---|---|
| **要求量化** | iCAP 指引 p48 | 「行為指標與工作產出可合併討論，以利討論出**可衡量工作成效之量化指標**及可觀察之行為指標」 |
| **要求可佐證** | 29 CFR §1607.14C(4) | K/S/A 須以 "**observable aspects of work behavior**" 定義（見效度原料 §2） |

### 3b. 四個政府體系的實測：**職務描述層沒有一個放自訂數值目標**

四份官方文件全文抽字後逐一計數（方法與檔案見 §6）：

| 體系 | 承載「標準」的欄位 | 該欄位的數值門檻 | 數字實際住在哪 |
|---|---|---|---|
| **澳洲**（training.gov.au 兩個單元） | Performance Criteria（單元本體） | **0** | **獨立的 Assessment Requirements 元件**（見 §3c） |
| **香港** QF 官方資料庫，物流業**全 1,351 筆 UoC** | Performance Requirements ＋ `integrated outcome requirements`（官方 `uocItemDescEng_Criteria` 欄） | **0**（全量計數，非抽樣） | 不存在 |
| **新加坡** Skills Framework (HR) | Performance Expectations | **0** | 不存在（見 §3d） |
| **美國 OPM** | competency 定義 | **0**（另禁模糊修飾詞，§2b） | **評分量表**（importance 1–5、frequency 0–5、need-at-entry 1–4） |

> 新加坡那份 7,639 行全文中符合數值門檻樣式的只有 5 處，逐一檢視後**全部是訓練補助與 CPD 規定**
> （"70-90% course fee subsidy"、"at least 90 Continuing Professional Development"），
> 與職務績效無關。

**這是本檔最強的一條結論，因為它是四個獨立體系的一致行為，不是單一條文的解讀。**

### 3c. 澳洲：數字存在，但被關在另一個元件裡

澳洲是唯一**確實使用次數門檻**的體系——但門檻不在描述工作的單元裡，而在
`AssessmentRequirements` 這個**分離的官方元件**（逐字，`TAEASS412`）：

> "conduct a total of **at least 6** assessments, **at least 1** of which must use recognition of prior
> learning (RPL). The above assessments must be for **3 different candidates** against all requirements
> specified in **at least 2 different units** of competency…"
> "identify and apply **at least 3 changes** to improve own assessment practice…"

**`BSBOPS401` 的 Performance Evidence 全文（逐字，供對照）：**

> "The candidate must demonstrate the ability to complete the tasks outlined in the elements,
> performance criteria and foundation skills of this unit, including evidence of the ability to:
> · **coordinate at least three business resources.**
> In the course of the above, the candidate must:
> · calculate and assess costs in relation to use and maintenance of business resources
> · develop and present resource requirement recommendations
> · consult and communicate with individuals and teams about acquiring and using resources
> · monitor and assess resource acquisition, allocation, use and procedures
> · follow organisational policies and procedures in relation to business resource acquisition and
>   monitoring and maintaining records."

**對照組——同一個體系的 Performance Criteria 長什麼樣（逐字，`TAEASS412` Element 1–2）：**

> "1.3 Access and analyse unit/s of competency and assessment tool, and check that tool maps to unit/s
> and assessment requirements and complies with the principles of assessment and rules of evidence
> 1.4 Identify actions required to be undertaken by candidate and assessor in preparation for assessment
> 1.5 Identify and obtain resources required to meet assessment conditions **according to organisational
> procedures**
> 2.1 Identify where recognition of prior learning (RPL) and/or reasonable adjustment is required and can
> be appropriately applied to the assessment process **without compromising the assessment's integrity**"

→ 注意兩件事：（a）**一個數字都沒有**；（b）品質條件是用
"according to organisational procedures"、"without compromising the assessment's integrity"
這種**可查核的限定語**表達的——與香港例 #2、新加坡的做法同源。

**計數證據**（指令見 §0.2）：同兩個單元的 Elements 與 Performance Criteria，
`at least`／`minimum of`／次數門檻出現次數為 **0 與 0**；Assessment Requirements 側為 **5 與 1**。

→ **判準 D-7a：數字屬於「怎麼驗證」那一層，不屬於「工作是什麼」那一層。**
澳洲用文件邊界把這件事做成了結構性強制。OPM 用「量表 vs 定義」做同一件事。

### 3d. 新加坡：把「標準」定義成外部權威的遵循

**欄位結構（逐字，表頭）**：新加坡把三件事並列成一張表——

> "**CRITICAL WORK FUNCTIONS** | **KEY TASKS** | **PERFORMANCE EXPECTATIONS**"

**定位**：`grep -n "CRITICAL WORK FUNCTIONS"`，職務 *Chief Human Resource Officer (CHRO)*。
`Critical Work Function` 全文出現 69 次、`Key Task` 138 次。

**一個完整列（逐字）：**

> **Critical Work Function** — "Apply business and financial acumen, MP：Using knowledge of key business
> drivers and important company data to make informed decisions with a keen appreciation of their impact
> on business outcomes"
>
> **Key Tasks** —
> · "Formulate and shape the organisation's business strategy and enterprise risk management with senior
>   business leaders and stakeholders by giving inputs related to business and people agenda"
> · "Deliver credible and persuasive presentations to senior business leaders and stakeholders and
>   display deep understanding of the business and industry"
> · "Display professional maturity and executive presence in dealing with contentious or sensitive topics
>   during discussion with senior business leaders and stakeholders"
> · "Advise senior business leaders and stakeholders on the design of the organisation structure to
>   enable business strategy and support the business objectives aligning to the organisation's vision,
>   mission and goals"
> · "Identify and assess an organisation's current and future core capabilities required to deliver
>   against business strategy in a competitive operating environment and changing business landscape and
>   economic conditions"
>
> **Performance Expectations** — 見下。

→ **Key Tasks 是動詞開頭的行為陳述，而 Performance Expectations 完全不是它們的量化版本。**
兩者不是「做什麼」與「做到多少」的關係。

新加坡的 `Performance Expectations` 欄不是目標值，而是**具名法規與框架的清單**（逐字）：

> "**In accordance with:** Central Provident Fund Act · Employment Act · Employment of Foreign Manpower
> Act · Employment of Foreign Manpower (Work Passes) Regulations · Fair Consideration Framework ·
> Industrial Relations Act · Retirement and Re-employment Act · Workman Injury Compensation Act"

全文出現 27 次同樣的 "In accordance with" 句式。

→ **判準 D-7b：這是第三種合法的「標準」寫法，而且對本產品特別好用。**
員工通常講得出治理自己工作的**法規、SOP、公司規章或客戶 SLA 的名稱**——
那是**可查核、不可虛構**的，遠優於憑空生成的百分比。
當員工說「有標準但講不出數值」時，**先問「依據什麼」而不是「是多少」**。

### 3e. 裁決建議

**不全禁，但預設不生成。** 四檔（原三檔 + 新加坡模式）：

| 情況 | 處置 | 支持度 |
|---|---|---|
| 員工說出具體數字且可逐字回溯（「我們的 SLA 是 4 小時」） | 允許寫入，附 quote | `behavior_grounded` |
| 員工講得出**依據的法規／SOP／規章名稱** | 寫成「依 X 辦理」——新加坡模式 | `behavior_grounded` |
| 員工確認有標準但講不出數值也講不出依據 | 寫成質性條件（「在約定時限內」），**不得補數字** | `employee_confirmed` |
| 員工未提及 | **不得生成任何數值** | 不寫 |

依據：iCAP 要的是「可衡量」不是「有數字」——質性但可觀察的指標同樣滿足審核指標 3.4.2；
無來源的數字則同時違反 §1607.14C(4) 與 ADR 0040 決定 29–30。
**香港與新加坡的全質性寫法證明「沒有任何數字也能通過政府級品質審查」**，
澳洲則證明**要用數字就該把它放到驗證層**。

---

## 4. 指標與級別的對齊

iCAP 審核指標 3.4.3 要求「『行為指標』所描述的能力程度，應可對應符合該工作任務之職能級別」。

**本輪未取得 AQF／新加坡的等價條文**（站點失敗）。可用的替代品是既有原料裡已逐字核實的
**SFIA 四軸升階措辭**（autonomy／influence／complexity／knowledge，見
[2026-07-13 國際體系原料](2026-07-13-ai-redesign-raw-intl-competency-standards.md) §5a）
與 **EQF 三維**。

→ **判準 D-6：第一版不做自動判級。** 理由：判級需要跨任務比較與級別定義的一致套用，
而我們連 Task 的 O/P/K/S 都還沒有真實資料。級別留給後續切片，
現在只確保指標**寫得夠具體到日後可以判級**（即 D-1 的三要件）。

---

## 5. 判準彙整（可直接進 verifier 或 prompt）

| 編號 | 判準 | 實作層 | 依據 |
|---|---|---|---|
| D-1 | 行為證據須：可觀察 + 意圖清楚 + 後果明確 | prompt／rubric | Flanagan 1954 開篇逐字（定位見 §1a；不標頁碼，理由見 §0.3） |
| D-2 | 指標必須對照已聲明的任務目的來寫 | schema（P 掛 Task） | Flanagan 1954 逐字 |
| D-3 | 「想不起來」是正常結果；戲劇性事件會擠掉例行工作 | 顧問行為 | Flanagan 1954 實測（50%／80%／selective recall） |
| D-4 | K/S 禁 `ability to`／「具備…能力」句式 | **deterministic** | OPM 逐字 + Morgeson 2004 實證 |
| D-5 | K/S 禁程度修飾詞（熟悉／精通／良好的…） | **deterministic** | OPM 逐字 |
| D-6 | 知識用名詞、技能用動詞 | **deterministic**（可近似） | OPM + ESCO 逐字 |
| D-7 | 數值門檻只在可逐字回溯時允許 | **deterministic** | 合成：iCAP p48 + §1607.14C(4) + 香港實例 |
| D-8 | 第一版不自動判級 | 範圍決定 | 缺 AQF／SG 條文 + 無真實資料 |

---

## 6. 來源總表

| # | 機關／體系 | 文件名 | 版本／年份 | URL | 取得方式 |
|---|---|---|---|---|---|
| 1 | **APA**（American Psychological Association 官方） | Flanagan, J. C., *The Critical Incident Technique*, *Psychological Bulletin* 51(4), 327–358 | **1954 年 7 月號** | https://www.apa.org/pubs/databases/psycinfo/cit-article.pdf | curl + `pdftotext`，全文 |
| 2 | **美國 OPM** | *Delegated Examining Operations Handbook*, Appendix D "How Competencies Should be Written"／"Task and Competency Linkages" | 現行線上版 | https://www.opm.gov/policy-data-oversight/hiring-information/competitive-hiring/deo_handbook.pdf | curl + `pdftotext -layout`，2.3 MB 全文 |
| 3 | **美國 OPM** | *Job Analysis Template*（Step 6c／6d 逐字） | 現行 | https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_handout.pdf | curl + `pdftotext -layout`，全文 |
| 4 | **香港教育局 QF（官方網域）** | 物流業 SCS 全量資料 | 每筆帶 `uoc_version`／`uoc_rev`；取得日 2026-08-01 | https://www.hkqf.gov.hk/api/content/en/record/logistics-scs | JSON 1,351 筆全量計數；PDF 副本已逐字比對一致。見[工作產出原料](2026-08-01-opks-raw-work-outputs.md) §1.4 |
| 5 | 美國聯邦法規 | 29 CFR §1607.14C(4)（Uniform Guidelines） | CFR 2024 年版 | 見[效度與法規原料](2026-08-01-opks-raw-validity-and-ai-regulation.md) §2 | 該檔已取 GPO 官方 XML 逐字 |
| 8 | **澳洲 DEWR**（training.gov.au 官方元件檔） | *TAEASS412 Assess competence*（單元）＋ *Assessment Requirements for TAEASS412* | Release 1；文件生成日 **2024-07-12**；TAE Training Package v5.0 | https://training.gov.au/TrainingComponentFiles/TAE/TAEASS412_R1.pdf ／ …/TAEASS412_AssessmentRequirements_R1.pdf | curl + `pdftotext -layout`，全文 |
| 9 | **澳洲 DEWR** | *BSBOPS401 Coordinate business resources*（單元＋Assessment Requirements） | Release 1 | https://training.gov.au/TrainingComponentFiles/BSB/BSBOPS401_R1.pdf ／ …/BSBOPS401_AssessmentRequirements_R1.pdf | curl + `pdftotext -layout`，全文 |
| 10 | **新加坡 SkillsFuture SG** | *Skills Framework for Human Resource*（含 Critical Work Functions／Key Tasks／Performance Expectations 全表） | 官方站現行檔；**經 Wayback Machine 2025-08-05 快照取得** | https://web.archive.org/web/20250805003944id_/https://www.skillsfuture.gov.sg/docs/default-source/skills-framework/skills-framework-for-hr.pdf | curl（分段續傳）+ `pdftotext -layout`，9.4 MB／7,639 行 |

> 第 10 項：官方網域直連只回傳 Next.js SPA 殼，無法取得 PDF；改用 Wayback 對**同一官方 URL** 的
> 存檔快照。內容為 SkillsFuture SG 官方文件，但**版次以快照日期為準**，正式引用前宜回官方站核對。
| 6 | **台灣勞動部勞動力發展署** | 《職能基準發展指引》p48（量化指標要求） | 111 年 10 月修正 | 見 [2026-07-13 iCAP 原料](2026-07-13-ai-redesign-raw-icap-field-standards.md) §5 | 前輪已逐字核實 |
| 7 | 學術原著 | Morgeson et al., *JAP* 89(4), 674–686（"ability to" 膨脹實證） | 2004 | 見[效度與法規原料](2026-08-01-opks-raw-validity-and-ai-regulation.md) §3.2 | 該檔已取作者站出版版 PDF |

---

## 7. 查不到／需二次確認（誠實清單）

1. **Smith & Kendall (1963) BARS 原著**——付費牆，未取得。本檔完全未引用 BARS 的建構步驟。
2. ~~澳洲 Performance Evidence 的次數門檻~~ —— **已解決，見 §3c。**
   澳洲確實使用次數門檻，但關在獨立的 Assessment Requirements 元件；單元本體為 0。
   結論由「可能的反例」轉為**強化**。**仍待確認**：只取樣兩個單元（TAE／BSB 各一）。
3. ~~新加坡 Performance Expectations 欄位定義~~ —— **已解決，見 §3d。**
   結論意外：該欄不是目標值，而是具名法規清單（"In accordance with…"）。
   **仍待確認**：只讀了 HR 一個框架，38 個 sector 是否全採同一寫法未驗證。
4. **AQF 的指標升階判準語言**——未取得；D-6 因此保守處理。
5. **Flanagan 全文的後半段**（分類系統建構程序）——已抽出但本檔僅用到方法論原則章節；
   若日後要做 rubric，該段仍值得再讀。
6. **香港 SCS 的版本與官方出處**——同工作產出原料 §6.5，須回 hkqf.gov.hk 確認。
