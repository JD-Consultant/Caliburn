---
title: 行為指標（P）的撰寫紀律與數值門檻 —— Flanagan CIT 原著與 OPM 官方禁令（研究原料）
date: 2026-08-01
purpose: 補 OPKS 研究缺口 D；回答「指標怎麼寫才算可觀察」與「數字門檻該全禁還是有條件允許」
source_discipline: 只收官方一手與學術原著；取得失敗與未核實項目列入 §6
---

# 行為指標（P）的撰寫紀律與數值門檻（研究原料）

## 0. 取得狀態

| 來源 | 狀態 |
|---|---|
| Flanagan (1954) *The Critical Incident Technique*, *Psychological Bulletin* 51(4) | ✅ **APA 官方 PDF 全文取得並抽字**；以下引文逐字 |
| OPM *Delegated Examining Operations Handbook*（Appendix D）+ *Job Analysis Template* | ✅ **PDF 全文取得**；逐字 |
| 香港 SCS 物流業 | ✅ 全文（見 [工作產出原料](2026-08-01-opks-raw-work-outputs.md)） |
| Smith & Kendall (1963) BARS 原著 | ❌ 未取得（付費牆）；本檔不引用 |
| 澳洲 Performance Evidence／AQF、新加坡 Performance Expectations | ❌ 官方站 timeout／SPA 殼；未取得 |

---

## 1. Flanagan (1954)：可觀察性的原始定義

### 1a. incident 與 critical 的定義（逐字，p. 327）

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

### 3b. 實際觀測到的做法

- **香港 SCS**（唯一取得全文的政府體系）：Performance Requirements 與 outcome requirements
  **未出現任何數值門檻**，一律質性。
- **OPM**：對 competency 的要求是禁模糊修飾詞（§2b），**未要求也未禁止數字**；
  數字出現在**評分量表**（importance 1–5、frequency 0–5、need-at-entry 1–4）而不是在**能力陳述**裡。
  → **這是關鍵區分：OPM 把數字放在「分析程序」，不放在「文件內容」。**

### 3c. 裁決建議（合成，非單一條文）

**不全禁，但預設不生成。** 三檔：

| 情況 | 處置 | 支持度 |
|---|---|---|
| 員工說出具體數字，且可逐字回溯（「我們的 SLA 是 4 小時」） | 允許寫入，附 quote | `behavior_grounded` |
| 員工確認有標準但講不出數值 | 寫成質性條件（「在約定時限內」），**不得補數字** | `employee_confirmed` |
| 員工未提及 | **不得生成任何數值** | 不寫 |

依據：iCAP 要的是「可衡量」不是「有數字」——質性但可觀察的指標同樣滿足
審核指標 3.4.2「具體清楚描述行為表現」；而**無來源的數字同時違反** §1607.14C(4) 的可觀察要求
與 ADR 0040 決定 29–30。**香港 SCS 的全質性寫法證明「沒有數字也能通過政府級品質審查」**。

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
| D-1 | 行為證據須：可觀察 + 意圖清楚 + 後果明確 | prompt／rubric | Flanagan 1954 p.327 逐字 |
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
| 4 | 香港 QF（經 HKU SPACE 轉載） | *Specification of Competency Standards for the Logistics Industry* | 版次未標 | https://hkuspace.hku.hk/f/rpl/103620/e_lo_tw.pdf | 見[工作產出原料](2026-08-01-opks-raw-work-outputs.md) §6 |
| 5 | 美國聯邦法規 | 29 CFR §1607.14C(4)（Uniform Guidelines） | CFR 2024 年版 | 見[效度與法規原料](2026-08-01-opks-raw-validity-and-ai-regulation.md) §2 | 該檔已取 GPO 官方 XML 逐字 |
| 6 | **台灣勞動部勞動力發展署** | 《職能基準發展指引》p48（量化指標要求） | 111 年 10 月修正 | 見 [2026-07-13 iCAP 原料](2026-07-13-ai-redesign-raw-icap-field-standards.md) §5 | 前輪已逐字核實 |
| 7 | 學術原著 | Morgeson et al., *JAP* 89(4), 674–686（"ability to" 膨脹實證） | 2004 | 見[效度與法規原料](2026-08-01-opks-raw-validity-and-ai-regulation.md) §3.2 | 該檔已取作者站出版版 PDF |

---

## 7. 查不到／需二次確認（誠實清單）

1. **Smith & Kendall (1963) BARS 原著**——付費牆，未取得。本檔完全未引用 BARS 的建構步驟。
2. **澳洲 Performance Evidence 的次數門檻**（如 "on at least 3 occasions"）——未取得。
   若該體系確實使用次數門檻，§3c 的三檔規則需要重審（那會是「官方允許數字」的反例）。
3. **新加坡 Performance Expectations 欄位定義**——未取得。
4. **AQF 的指標升階判準語言**——未取得；D-6 因此保守處理。
5. **Flanagan 全文的後半段**（分類系統建構程序）——已抽出但本檔僅用到方法論原則章節；
   若日後要做 rubric，該段仍值得再讀。
6. **香港 SCS 的版本與官方出處**——同工作產出原料 §6.5，須回 hkqf.gov.hk 確認。
