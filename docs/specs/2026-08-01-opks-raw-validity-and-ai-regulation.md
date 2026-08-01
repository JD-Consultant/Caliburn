---
title: O/P/K/S/A 的效度要求、在職者自評偏誤與 AI 法規現況
date: 2026-08-01
purpose: >
  補齊 2026-07-13 國際標準研究缺的「效度／證據／法規」層。給出可直接當設計判準的條列規則：
  K/S 必須怎麼連回可觀察 work behavior 才算成立、一位員工自評的偏誤有多大、
  本機單人 JD 生成工具在 EU/US/台灣的法規落點、以及「支持度分級」有沒有權威先例。
source_discipline: >
  只收政府／標準機構官方一手文件、學術原著期刊論文、官方資料庫。全部以 WebFetch／直接下載原始檔案
  （PDF/XML/HTML）後逐頁讀取，非二手轉述。每條標文件名 + URL + 版本/年份 + 條號或頁碼。
  未逐字核實者一律標「未核實」並列入末章。
---

> **【現行裁決】** 本檔是**研究原料**，其中對「支持度四級」的分析僅供追溯。
> OPKS 的現行裁決是 **[ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)（概念）
> ＋ [0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)（實作形狀）
> ＋ [0050](../adr/0050-opks-proposal-minimal-shape.md) ＋ [0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)**。
> 四級已被兩正交軸取代。**引用本檔任何段落前請先確認未被三份 ADR 取代**——
> 尤其 §判準 3-B(4) 的 bogus item 建議**已撤回**（見該處更正框）。

> 前置研究：[國際主要職能/職業標準體系的欄位定義與撰寫標準](2026-07-13-ai-redesign-raw-intl-competency-standards.md)
> （O\*NET / ESCO / SFIA / UK NOS / Bloom 的**欄位定義與句式規則**）。本篇**不重寫**那一層。

---

## 第 1 題：SIOP *Principles*（第 5 版）對 job analysis 與 content validity 的要求

**權威文件：** Society for Industrial and Organizational Psychology, *Principles for the Validation and
Use of Personnel Selection Procedures*, **FIFTH EDITION, AUGUST 2018**。
URL: https://www.apa.org/ed/accreditation/personnel-selection-procedures.pdf
（封面第 II 頁原文：「This document is an official policy statement of the Society for Industrial and
Organizational Psychology (Division 14 of the American Psychological Association) and was adopted as
policy of the American Psychological Association (APA) by the APA Council of Representatives in August
2018.」共 60 頁，已逐頁取得全文。）

### 1.1 術語：不是 job analysis，是 **analysis of work**（p. 7，"Analysis of Work"）

> "The term **'analysis of work' is used throughout the Principles and subsumes information that
> traditionally has been collected through work and job analysis methods, and more recently, competency
> modeling efforts** as well as other information about the work, worker, organization, and work
> environment. The focus for conducting an analysis of work may include different dimensions or
> characteristics of work, including **work complexity, environment, context, tasks, behaviors and
> activities performed, and worker requirements (e.g., KSAOs or competencies)**."

> "Competency models are often used by organizations for many different purposes. **When they are
> intended to support the underlying validity or use of a selection procedure, the Principles applies.**"

**判準 1-A：** Caliburn 產的是 competency-shaped 的 JD。只要它**沒有**被拿去支撐選才程序的效度，
*Principles* 在其自身用語下不對它課要求；一旦被拿去做選才，整套 *Principles* 就適用。
這條界線必須寫進產品文案與 JD 成品的警語。

### 1.2 沒有單一正確方法，但**細節程度由用途決定**（p. 7，"LEVEL OF DETAIL"）

> "There is no single approach that is the preferred method for the analysis of work."
> "**The level of detail required of an analysis of work is directly related to its intended use and the
> availability of information about the work.**"
> "Any methods used to obtain information about work or workers should be **understood by the
> participants and should have reasonable psychometric characteristics. Lack of consensus about the
> information contained in the analysis of work should be noted and considered further.**"

**判準 1-B：** 「lack of consensus … should be **noted**」——官方要求把**分歧本身記錄下來**，不是消掉。
這正是四級支持度標記的權威依據形狀：不確定的東西要**留痕**，不是刪掉也不是升級。

### 1.3 單一在職者不夠（p. 8，同節末段）

> "If there is reason to question whether people with similar job titles are in fact doing similar work…
> then **the inclusion of incumbents or other subject matter experts (SMEs) from each of the job titles or
> families will generally be necessary. Even when incumbents are in positions with similar job titles or
> work families, studying multiple incumbents may be necessary** to understand differences in work
> complexity, work context, work environment, job behaviors, or worker KSAOs or competencies as a
> function of shift, location, variations in how work is performed, and other factors…"

**判準 1-C：** *Principles* 明說「多位在職者常有必要」。Caliburn 的第一版是**一位員工**——這是產品的
**已知結構性限制**，必須在 JD 成品上標明「單一在職者來源」，不得假裝是組織級標準。

### 1.4 content-based 效度的核心：**linkage**（p. 15，"Evidence for Validity Based on Content"）

> "Evidence for validity based on content typically consists of a demonstration of **a strong linkage
> between the content of the selection procedure and important work behaviors, activities, worker
> requirements, or outcomes on the job.**"

> （p. 16，"DESIGN AND CONDUCT OF CONTENT-BASED STRATEGIES"）
> "The content-based validation study specifically demonstrates that the content of the selection
> procedure represents **an adequate sample of the important work behaviors, activities, and/or worker
> KSAOs defined by the analysis of work.**"

> （p. 16，"DEFINING THE CONTENT DOMAIN"）
> "The characterization of the work domain should be based on **accurate and thorough information about
> the work, including analysis of work behaviors and activities, responsibilities of the job incumbents,
> and/or the KSAOs prerequisite to effective performance on the job.**"
> "The testing professional should indicate **what important work behaviors, activities, and worker KSAOs
> are included in the domain, describe how the content of the work domain is linked to the selection
> procedure, and explain why certain parts of the domain were or were not included**…"

> （p. 16）
> "The fact that the construct assessed by a selection procedure is labeled an ability or personality
> characteristic **does not per se preclude the reliance on a content-oriented strategy. When selection
> procedure content is linked to job content, content-oriented strategies are useful. When selection
> procedure content is less clearly linked to job content, other sources of validity evidence take
> precedence.**"

> （p. 17，"EVALUATING CONTENT-RELATED EVIDENCE"）
> "Evidence for validity based on content rests on demonstrating that the selection procedure **adequately
> samples and is linked to the important work behaviors, activities, and/or worker KSAOs defined by the
> analysis of work. The documented methods used in developing the selection procedure constitute the
> primary evidence** for the inference…"

**判準 1-D（K/S/A 門檻的第一條）：** *Principles* 的語言是 **KSAO 由 analysis of work「定義」，並與
important work behaviors「連結」**。因此一條 K 或 S 若**沒有**掛回本份 JD 裡的某條 task／behavior，
在 *Principles* 的框架下**根本不構成 content 證據**——它不是「弱證據」，是「不是證據」。
→ 直接對映 Caliburn 的 `unsupported` 必須**擋在正式 JD 之外**（而非降級收錄）。

**判準 1-E：** 「**describe how** … is linked」+「**explain why** certain parts were or were not included」
——官方要求的是**可讀的連結說明與排除理由**，不是一個布林旗標。若 Caliburn 要主張這條線，
支持度欄位應該能帶出「連到哪一條 task／哪一段對話」的指標，而不只是等級字串。

### 1.5 SME 資格是 content 研究成敗的關鍵（p. 15，"FEASIBILITY…"）

> "**The success of a content-based validation study is closely related to the qualifications of the SMEs.**
> SMEs define the work domain; participate in the analysis of work by identifying the important work
> behaviors, activities, and worker KSAOs; and establish the relationship between the selection procedures
> and the work behaviors or worker requirements. **The experts should be competent to perform the task set
> before them.**"

> （p. 15）"Among these issues are **the stability of the work and the worker requirements, interference of
> irrelevant content, availability of qualified and unbiased SMEs, and cost and time constraints.**"

**判準 1-F：** 官方點名「**unbiased** SMEs」是可行性前提之一。Caliburn 的 SME **就是被描述的那個人**，
天然不滿足 unbiased——這直接連到第 3 題。

### 1.6 保密會提高資料正確性（p. 30，"CONFIDENTIALITY"）

> "**Those who provide information, performance ratings, or content validity linkages may be more willing
> to provide accurate information if they are assured of the confidentiality of their individual
> contributions.** Participants in validation research studies should be given confidentiality unless there
> are persuasive reasons to proceed otherwise."

**判準 1-G：** 「本機執行、資料不外流、老闆看不到草稿」不只是隱私賣點，是 *Principles* 認可的
**資料正確性機制**。這是本產品架構（本機、單人、無帳號）少數在效度上**加分**的地方，值得寫進設計理由。

### 1.7 文件化要求（p. 32，"ANALYSIS OF WORK"）

> "The report should contain **a description of the analysis of work, the characteristics of the
> participants in the process, any judgments made by SMEs, instructions that were provided to participants
> in data collection efforts for their specific tasks, and data analyses and results including
> reliability/precision.**"

**判準 1-H：** 若 Caliburn 要能被專業人士接受，JD 成品應可導出一份「來源說明」：誰參與、
被問了什麼、哪些是員工判斷、哪些是模型建議。這與 Consultation Journal 的既有設計同向。

---

## 第 2 題：Uniform Guidelines 29 CFR §1607.14C（content validity）逐字原文

**權威文件：** *Uniform Guidelines on Employee Selection Procedures (1978)*, 29 CFR Part 1607,
§ 1607.14「Technical standards for validity studies」。
一手取得：GPO govinfo **CFR 2024 年版**（`<DATE>2024-07-01</DATE>`）XML granule，
URL: https://www.govinfo.gov/content/pkg/CFR-2024-title29-vol4/xml/CFR-2024-title29-vol4-sec1607-14.xml
（eCFR 對本工具封鎖，改用 GPO 官方 XML；印刷頁碼 pp. 230–232。）

### 2.1 §1607.14A —— 任何效度研究都要有 job analysis

> "A. **Validity studies should be based on review of information about the job.** Any validity study
> should be based upon a review of information about the job for which the selection procedure is to be
> used. **The review should include a job analysis** except as provided in section 14B(3) below with
> respect to criterion-related validity. **Any method of job analysis may be used if it provides the
> information required for the specific validation strategy used.**"

### 2.2 §1607.14C(1) —— content validity 何時**不**適用（產品必讀）

> "A selection procedure can be supported by a content validity strategy **to the extent that it is a
> representative sample of the content of the job.** Selection procedures which purport to measure
> knowledges, skills, or abilities may in certain circumstances be justified by content validity, although
> they may not be representative samples, **if the knowledge, skill, or ability measured by the selection
> procedure can be operationally defined as provided in section 14C(4) below, and if that knowledge,
> skill, or ability is a necessary prerequisite to successful job performance.**"

> "A selection procedure based upon inferences about mental processes cannot be supported solely or
> primarily on the basis of content validity. **Thus, a content strategy is not appropriate for
> demonstrating the validity of selection procedures which purport to measure traits or constructs, such
> as intelligence, aptitude, personality, commonsense, judgment, leadership, and spatial ability.**
> Content validity is also **not an appropriate strategy when the selection procedure involves knowledges,
> skills, or abilities which an employee will be expected to learn on the job.**"

**判準 2-A（對「態度(A)」欄的硬約束）：** 官方明列 **personality / commonsense / judgment / leadership**
為**不能**用 content 策略支撐的 construct。Caliburn 的「態度」欄（O\*NET Work Styles 那一類：
Dependability、Integrity、Initiative…）**正落在這個禁區**。
→ 態度欄不得以「這是 JD 上寫的要求」之姿被當成可用於選才的標準；產品必須把態度欄的地位降級為
**描述性**，並在成品上標註「不作為選才判準」。這是本輪研究對現行設計最強的單一約束。

**判準 2-B：** 「an employee will be expected to learn on the job」——**入職後才學的 K/S 不能寫成入職要求**。
訪談時必須分「進來前就要會」vs「進來後會教」；這兩者在 JD 上是不同欄位語意。

### 2.3 §1607.14C(2) —— **job analysis 本身的要求**（本題核心）

> "**(2) Job analysis for content validity.** There should be a job analysis which includes an analysis of
> **the important work behavior(s) required for successful performance and their relative importance** and,
> **if the behavior results in work product(s), an analysis of the work product(s)**. **Any job analysis
> should focus on the work behavior(s) and the tasks associated with them. If work behavior(s) are not
> observable, the job analysis should identify and analyze those aspects of the behavior(s) that can be
> observed and the observed work products.** The work behavior(s) selected for measurement should be
> **critical work behavior(s) and/or important work behavior(s) constituting most of the job.**"

**判準 2-C：** 這一段是 Caliburn 五欄（Task / Output / Indicator / K / S）的**法規級依據**：
- 「work behavior(s) **and the tasks associated with them**」→ behavior 與 task 是**兩個要一起有**的東西，不是同義詞。
- 「**if the behavior results in work product(s), an analysis of the work product(s)**」→ **工作產出(O) 有明文法規依據**。
  這修正了 2026-07-13 spec 的結論「主流體系無獨立 deliverable 欄位」：O\*NET/ESCO/NOS 確實沒有獨立欄位，
  但 **29 CFR 1607.14C(2) 明文要求分析 work product**。O 欄不是 Caliburn 自創，是 UGESP 要求的。
- 「**If work behavior(s) are not observable … identify and analyze those aspects that can be observed and
  the observed work products**」→ 這正是**行為指標(P) 欄的官方定義來源**：不可觀察的行為，
  必須改寫成「可觀察的面向 + 可觀察的產出」。
- 「critical … and/or important … **constituting most of the job**」→ 涵蓋率門檻，不是全部 task 都要寫。

### 2.4 §1607.14C(4) —— KSA 陳述必須怎麼寫才成立（逐字，最關鍵）

> "**(4) Standards for demonstrating content validity.** To demonstrate the content validity of a selection
> procedure, a user should show that the behavior(s) demonstrated in the selection procedure are a
> representative sample of the behavior(s) of the job in question or that the selection procedure provides
> a representative sample of the work product of the job. **In the case of a selection procedure measuring
> a knowledge, skill, or ability, the knowledge, skill, or ability being measured should be operationally
> defined. In the case of a selection procedure measuring a knowledge, the knowledge being measured should
> be operationally defined as that body of learned information which is used in and is a necessary
> prerequisite for observable aspects of work behavior of the job. In the case of skills or abilities, the
> skill or ability being measured should be operationally defined in terms of observable aspects of work
> behavior of the job.** For any selection procedure measuring a knowledge, skill, or ability the user
> should show that **(a) the selection procedure measures and is a representative sample of that knowledge,
> skill, or ability; and (b) that knowledge, skill, or ability is used in and is a necessary prerequisite
> to performance of critical or important work behavior(s).** In addition, to be content valid, a selection
> procedure measuring a skill or ability should either **closely approximate an observable work behavior,
> or its product should closely approximate an observable work product.**…"

**判準 2-D（K/S 的證據門檻，可直接寫成 verifier 規則）：** 一條 K/S 要成立，法規要求三件事同時成立：
1. **operationally defined** —— 不是名詞標籤，要能操作化。
2. K 必須是「**used in and is a necessary prerequisite for observable aspects of work behavior of the job**」
   ——**用於**某條可觀察工作行為 **且** 是其**必要前提**。
3. S/A 必須「**defined in terms of observable aspects of work behavior of the job**」
   ——技能的定義本身就要用**可觀察工作行為**的語言寫。

→ 轉成 Caliburn 判準：
- **每一條 K 必須帶一個「用在哪條 task/behavior」的指向，且該指向必須是可觀察的。** 沒有指向 = 不成立。
- **每一條 S 的敘述文字本身必須是可觀察行為語言。** 「熟悉 Python」不合格；
  「使用 Python 撰寫並維護 ETL 腳本以產出每日對帳報表」才是 14C(4) 意義下的操作化定義。
- 「**necessary prerequisite**」是比「相關」高的門檻。訪談要問的是「少了這個，這條 task 做不做得成？」
  ——不是「這個有沒有幫助？」

**判準 2-E：** §1607.14C(2) 對比 §1607.14D(2)（construct validity）：construct 路線要求
「**Each construct should be named and defined, so as to distinguish it from other constructs**」
且要有 criterion-related 實證。態度欄若真要留，其法規落點是 construct 路線，
而 construct 路線在本產品**根本不可行**（無樣本、無效標）。這再次支持判準 2-A。

### 2.5 **2026 現況警示：UGESP 的法律地位已被行政部門否定**（必讀，會改變引用方式）

三份一手文件：

**(a) DOJ Office of Legal Counsel, *Constitutionality of Disparate-Impact Liability Under Title VII*,
50 Op. O.L.C. __ (June 9, 2026), 25 頁 slip opinion。**
URL: https://www.justice.gov/olc/media/1444871/dl （已下載全文）
Syllabus 原文：
> "**EEOC's Title VII guidelines are unconstitutional** because they contemplate liability based on
> disparate effects alone, without regard to an employer's likely intent, and pressure employers to engage
> in race-based decisionmaking."
> "**Workplace requirements and selection procedures—such as background checks, aptitude tests, and SAT
> scores—are presumptively job-related. Only irrational or arbitrary practices with no plausible
> job-relatedness can create disparate-impact liability.**"

p. 19–20 直接點名 UGESP 的驗證框架過度：
> "The Guidelines impose detailed requirements for validation studies by providing '[g]eneral standards,'
> 29 C.F.R. § 1607.5, evidentiary documentation standards, id. § 1607.15, and '[t]echnical standards,'
> id. § 1607.14."
> "**The Guidelines impose 34 essential requirements for criterion-related validity, 19 for content
> validity, and 25 for construct validity.**"

**(b) EO 14281, *Restoring Equality of Opportunity and Meritocracy*（2025-04-23 簽署，
90 FR 17537, 2025-04-28 刊登）。** 原文：
> "Sec. 2. Policy. **It is the policy of the United States to eliminate the use of disparate-impact
> liability in all contexts to the maximum degree possible**…"
> "Sec. 4. … **all agencies shall deprioritize enforcement of all statutes and regulations to the extent
> they include disparate-impact liability, including but not limited to 42 U.S.C. 2000e-2**…"

**(c) OPM interim final rule, *Removal of References to the Uniform Guidelines on Employee Selection
Procedures in Federal Personnel Regulations*, 91 FR 48234（2026-07-31 刊登，**即日生效**）。** 原文：
> "OLC concluded that existing EEOC interpretations, **including UGESP, embrace an unconstitutional reading
> of Title VII**…"
> "**OLC also concluded that UGESP's validation study framework is inconsistent with Title VII's
> business-necessity defense**, properly understood, because it imposes detailed and burdensome validation
> requirements beyond what Title VII requires."
> "**The rule is limited. It does not remove the job-analysis requirement in Sec. 300.103(a). It does not
> remove the requirement in Sec. 300.103(b) that there be a rational relationship between performance in
> the position to be filled and the employment practice used. It does not remove the requirement that the
> employment practice be professionally developed.**"

**判準 2-F：** 截至 2026-08-01，**29 CFR Part 1607 仍在 CFR 上**（本文引的就是現行條文），
但行政部門已宣告其不合法並開始移除引用。因此：
- **不要**把 UGESP 當「法律合規要求」寫進產品文案或 ADR 理由（會過期）。
- **要**把 14C(2)/14C(4) 當**專業品質判準**引用——它是被最完整寫下來的「KSA 怎麼連回 behavior」的操作化定義，
  這個技術內容並未被 OLC 否定（OLC 否定的是**課予雇主的舉證負擔**，不是「job analysis 該怎麼做」）。
- 存活下來的美國聯邦要求正是 **5 CFR 300.103(a)-(b)：job analysis + rational relationship +
  professionally developed**——這是比 UGESP 寬鬆得多、但仍存在的底線，且**與 Caliburn 的產品定位一致**。

---

## 第 3 題：在職者自評的偏誤——原著實證與效果量

### 3.1 Morgeson & Campion (1997)：16 個不準確來源的框架

**權威原著：** Frederick P. Morgeson & Michael A. Campion, "Social and Cognitive Sources of Potential
Inaccuracy in Job Analysis," ***Journal of Applied Psychology*, 1997, Vol. 82, No. 5, 627–655**
（29 頁全文，作者自架站提供之出版版 PDF：http://www.morgeson.com/downloads/morgeson_campion_1997.pdf）

摘要原文：
> "Although it appears that many assume job analysis information is accurate, there is considerable
> evidence from other fields to suggest that the types of subjective judgments often involved in job
> analysis may be subject to systematic sources of inaccuracy."

**Table 1（p. 629）的 16 個來源分兩大類：**
- **Social sources** — Social influence processes：Conformity pressures / Extremity shifts / Motivation loss；
  **Self-presentation processes：Impression management / Social desirability / Demand effects**
- **Cognitive sources** — 資訊處理限制：Information overload / Heuristics / Categorization；
  資訊處理偏誤：**Carelessness** / Extraneous information / Inadequate information / Order and contrast
  effects / Halo / Leniency and severity / Methods effects

**Proposition 4（p. 830，直接可當風險清單）：**
> "**Impression management may lead to inaccuracy in the form of inflated job requirements and ratings.
> It is more likely when individuals are accountable for the information, when there is ambiguity, when
> individuals are encouraged to self-monitor, when the audience is high status, when the situation is
> [e]valuative in nature, or when the outcome is personally valued.**"

作者論證這五個條件在 job analysis 裡**全部**成立（p. 829–830）：
> "In job analysis, **by definition, there is some ambiguity**, or there would be no need for the analysis."
> "Job analysis would be expected to **encourage self-monitoring** because incumbents are asked to describe
> what they do for the organization and, ultimately, **their individual contribution**."
> "**in the current climate of downsizing, it may be in the best interest of all incumbents to inflate job
> requirements.** These factors are all present to varying degrees in job analyses, thus providing **an
> ideal setting in which to elicit impression management behaviors.**"

**判準 3-A：** 對 Caliburn 而言五個條件命中率極高——員工要描述**自己的個人貢獻**、內容有模糊性、
成品可能影響薪資或考績。唯一能壓低的是「audience is high status / evaluative」：
**本機、不上傳、老闆看不到草稿**這個架構直接削弱兩個條件。這與判準 1-G 同向，應寫成明確設計理由。

### 3.2 Morgeson et al. (2004)：ability 陳述膨脹的**田野實驗**與效果量

**權威原著：** Frederick P. Morgeson, Kelly Delaney-Klinger, Melinda S. Mayfield, Philip Ferrara &
Michael A. Campion, "Self-Presentation Processes in Job Analysis: A Field Experiment Investigating
Inflation in Abilities, Tasks, and Competencies," ***Journal of Applied Psychology*, 2004, Vol. 89,
No. 4, 674–686**（13 頁全文：http://www.morgeson.com/downloads/morgeson_delaney-klinger_mayfield_ferrara_campion_2004.pdf）

摘要原文：
> "**Results indicated that ability statements were more subject to inflation than were task statements
> across all rating scales. Greater endorsement of nonessential ability statements was responsible for the
> differences.** This produced higher endorsement of ability items but lower mean ratings. Finally,
> frequency and importance ratings of **global competency statements were generally higher than decomposed
> ability and task scales**…"

**逐條效果量（Cohen's d，原文 pp. 679–681）：**

| 假設 | 結果 | 平均效果量 |
|---|---|---|
| H1 認領為「本職一部分」的**陳述數** | ability 比 task 平均多認領 **0.80** 條（12 個 job component 全部顯著） | **d = .52**（中） |
| H2 summed **frequency** | ability 高 2.67（12 中 9 顯著） | **d = .42**（中） |
| H2 summed **importance** | ability 高 2.25（12 中 10 顯著） | **d = .49**（中） |
| H2 summed **required-at-entry** | ability 高（12 中 11 顯著）；平均高 2.32 | **d = .65**（中偏大） |
| H4 **bogus（假造）陳述** summed | bogus ability *M*=2.04 vs bogus task *M*=1.00 | **d = .55**（中） |
| H4 bogus 平均分 | 0.20 vs 0.09 | **d = .65**（中偏大） |
| H5 **competency** frequency vs ability | competency 高 .30 | **d = .53**（中） |
| H5 competency frequency vs task | competency 高 .21 | **d = .37**（小偏中） |

**bogus item 的關鍵結論（p. 682）：**
> "**Thus, on statements no incumbent should endorse, abilities were more frequently identified as part of
> the job. This suggests that the motivation to present oneself favorably may be stronger than the ability
> to differentiate the actual abilities associated with a particular position.**"

**「用平均分會看不見膨脹」（p. 682）：**
> "**When incumbents were asked whether a statement was part of their job or when response scales were
> summed, the expected inflation was observed. When a mean was computed, however, either the effect was
> reversed or no differences were found. Given the typical job analysis practice of calculating means on
> frequency and importance ratings, this suggests that the effect of self-presentation processes may have
> been disguised in prior job analysis practice. This can lead to a false sense of security about the
> accuracy of resultant job analysis data.**"

**低動機情境下仍膨脹（p. 683）：**
> "Because the results of a job analysis done for this purpose minimally impact the respondent…, the
> motivation to self-present is likely to be low. **Yet respondents did self-present by inflating certain
> ratings. In situations in which respondents might be more motivated to self-present, there will likely
> be even greater inflation.** For example, if the job analysis is conducted to determine compensation, job
> classification, or training needs…"

**操縱極弱、效果仍在（p. 683）：**
> "What is remarkable about the present study is that there were **no substantive differences between the
> ability and the task statements (i.e., simply the inclusion of the phrase _ability to_)**. As such, this
> can be viewed as **a very weak manipulation**… **It is likely that there would be much more
> self-presentation if the ability statements were more abstract.**"

**作者給的三個對策（p. 683，直接可實作）：**
> "(1) …**nonincumbent judgments (those of supervisors and job analysts) are less likely to be
> systematically inflated. These can serve as an important check against incumbent judgments of ability
> statements.**"
> "(2) …a key question for future research concerns whether there are ways to structure job-incumbent
> ability statement data collection to avoid problems of inflation. **One possibility might be to give
> incumbents explicit task–ability linkages so that they can have the appropriate frame of reference and
> can anchor their ability judgments in the tasks performed.**"
> "(3) **Our results suggest that competency modeling and other techniques that require such global
> judgments can be subject to inflation in responding.**"

**判準 3-B（K/S/A 的產品級對策，逐條）：**
1. **絕不要求員工對「ability to X」直接評分。** 光是加上 "ability to" 這個詞就足以在 d≈.5 的量級上造成膨脹。
   → 訪談問「你做什麼、做成什麼樣」，由系統從 task 推導 K/S；**不要**問「你需要具備什麼能力」。
2. **強制 task→K/S anchoring。** 這是原著在討論段**建議**的緩解方向。
   > **【2026-08-01 更正｜措辭降一級】** 本條原文寫「本研究確認它有原著背書，不是自創」，
   > 語意介於「作者建議過」與「該研究已驗證有效」之間。**正確表述是前者**：
   > Morgeson et al. (2004) 是一個**測量**研究，它證明了 ability 陳述會膨脹，
   > **並未**設置 task-anchored 組別來驗證 anchoring 能降低膨脹。
   > 因此 Caliburn 的「K/S 必須掛 task linkage」是**依原著建議方向所做的設計選擇**，
   > 其有效性在本 repo 尚無實證。不得寫成「已驗證的介入措施」。
3. **不要用平均分呈現。** 若未來加入重要性評分，要保留 endorsement 計數與加總，
   平均值會**遮蔽**膨脹（p. 682 原文）。
4. **bogus item 只能留在離線 eval，不得進產品。**
   > **【2026-08-01 撤回】** 本條原文寫「可直接當品質閘」，並建議在**員工看得到的候選清單**裡
   > 混入與本職無關的參照 K/S，用員工是否照單全收來降級整場訪談。**此建議已撤回**，四個理由：
   > （a）bogus item 在原著中是**測量工具**，不是經驗證的產品介入；
   > （b）在員工自己的文件裡故意混入假項目會**污染員工決策並破壞顧問信任**——
   >     而本產品的核心前提正是「員工是自己 JD 的權威」；
   > （c）**沒有任何經驗門檻**可決定「照單全收幾條」才該降級整場訪談；
   > （d）若事先告知員工有假項目，就改變了原本的測量條件，偵測力消失；若不告知，就是欺瞞。
   >
   > **保留的用法**：bogus item 可作為**離線 eval fixture**（測模型而非測員工）。
   > 產品內若要達成同樣目的，改用**真實的近鄰反例**與**對比追問**
   > （例：「這是完成該 Task 不可缺少的知識，還是你目前剛好使用的工具／方法？」）。
5. **全域性 competency 陳述比拆解後的 task/ability 更容易膨脹**（H5，d=.53/.37）。
   → 「核心職能」這種粗顆粒欄位風險最高；要寫就必須拆到 task 層再回推。
6. **缺 supervisor / analyst 對照樣本是本產品最大結構缺口。** 原著點名的第一對策我們用不上。
   → 唯一可替代的「非在職者判斷」是**公版參照資料（O\*NET/ESCO/iCAP）**與**模型自身的挑戰角色**；
   兩者都不等價於真人主管，這個差距必須誠實標在成品上。

**判準 3-C（對支持度四級的直接校準）：**
`employee_confirmed`（員工明確確認這是「工作要求」而非「自己會」）在本研究面前**必須被視為弱證據**——
2004 年的實驗中，員工正是在「這是不是我工作的一部分」這個二元題上對 ability 陳述系統性超額認領
（H1, d=.52；bogus H4, d=.55）。**員工點頭本身就是被證實會膨脹的那個動作。**
→ 現行設計「`employee_confirmed` 可入正式 JD 但保留標記」是可辯護的下限；
但**不得**再放寬，且成品呈現上應與 `behavior_grounded` 視覺可區分。

---

## 第 4 題：AI 用於 HR／職務分析的法規

### 4.1 EU AI Act：本產品**不**落入 Annex III 高風險（附條文推理）

**權威文件：** Regulation (EU) 2024/1689（AI Act），OJ L, 2024/1689, 12.7.2024（全文 HTML 已下載逐條讀取）。
URL: https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689

**Annex III point 4（employment）逐字：**
> "**4. Employment, workers' management and access to self-employment:**
> (a) AI systems intended to be used for **the recruitment or selection of natural persons**, in particular
> to place targeted job advertisements, to analyse and filter job applications, and to evaluate candidates;
> (b) AI systems intended to be used **to make decisions affecting terms of work-related relationships, the
> promotion or termination of work-related contractual relationships, to allocate tasks based on individual
> behaviour or personal traits or characteristics or to monitor and evaluate the performance and behaviour
> of persons** in such relationships."

**判斷（逐條對照 Caliburn）：**

| 條文 | 是否命中 | 理由 |
|---|---|---|
| 4(a) recruitment or selection | **否** | Caliburn 產的是**職務說明書本身**，不評估任何候選人、不篩選申請、不投放廣告。JD 是招募的**輸入物**，不是「用於招募的 AI 系統」。 |
| 4(b) 決定僱傭條件 / 升遷 / 終止 | **否** | 系統不做決定，也不輸出對特定人的決策建議。 |
| 4(b) **allocate tasks based on individual behaviour or personal traits** | **需注意** | 這條是「**依個人行為或特質分派任務**」。Caliburn 描述的是**職位**的 task，不是把 task 分派給特定個人。但若未來加入「依這位員工的能力調整他的職務內容」功能，**就會命中**。 |
| 4(b) monitor and evaluate performance | **否**，但**易誤觸** | 目前只描述職位要求。若把「行為指標(P)」拿去**評分該員工**，即命中。 |

**Article 6(3) 的排除條款（即使被列入 Annex III 也可能非高風險）：**
> "3. By derogation from paragraph 2, **an AI system referred to in Annex III shall not be considered to be
> high-risk where it does not pose a significant risk of harm to the health, safety or fundamental rights of
> natural persons, including by not materially influencing the outcome of decision making.**
> The first subparagraph shall apply where any of the following conditions is fulfilled:
> (a) the AI system is intended to **perform a narrow procedural task**;
> (b) the AI system is intended to **improve the result of a previously completed human activity**;
> (c) the AI system is intended to detect decision-making patterns … **without proper human review**; or
> (d) the AI system is intended to **perform a preparatory task to an assessment** relevant for the purposes
> of the use cases listed in Annex III.
> **Notwithstanding the first subparagraph, an AI system referred to in Annex III shall always be considered
> to be high-risk where the AI system performs profiling of natural persons.**"

**判準 4-A：** 即使有人主張 JD 生成是招募的前置，(d)「**preparatory task to an assessment**」正好適用。
**但**——「always high-risk where the AI system performs **profiling of natural persons**」是硬紅線。
Caliburn 必須始終描述**職位**而非**這個人**。「員工能力側寫」「這位員工適不適合」一旦出現，
排除條款全部失效。**這是產品範圍鎖定裡最該寫死的一條。**
（註：Art. 6(3) 未被 2026 年 Omnibus 修改；Omnibus 只在 Art. 6 插入 1a/1b/1c 三款，處理 safety component 定義。）

**Article 2(10) —— 純個人非專業活動的排除：**
> "10. This Regulation **does not apply to obligations of deployers who are natural persons using AI systems
> in the course of a purely personal non-professional activity.**"

**判準 4-B：** 員工在**工作上**用 Caliburn 寫自己的 JD 是 professional activity，**不適用** Art. 2(10)。
不要拿「本機自用」當豁免理由——豁免理由是**功能不落入 Annex III**，不是部署形態。

**Article 2(12) —— 開源排除：**
> "12. This Regulation does not apply to AI systems released under free and open-source licences,
> **unless they are placed on the market or put into service as high-risk AI systems or as an AI system that
> falls under Article 5 or 50.**"

**適用時點（已於 2026 年被修法延後，務必用新日期）：**

原 Art. 113 第三段 (c)：「Article 6(1) and the corresponding obligations … shall apply from 2 August 2027」，
本體「It shall apply from 2 August 2026」。**但已被下列法規修改：**

**Regulation (EU) 2026/1744 of 8 July 2026**, amending Regulations (EU) 2024/1689, (EU) 2018/1139 and
(EU) 2023/1230 as regards the simplification of the implementation of harmonised rules on artificial
intelligence (**Digital Omnibus on AI**), OJ 2026/1744, **24.7.2026**。
URL: https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202601744 （全文已下載）

修正條文原文（第 40 點，修改 Art. 113 第三段 (c)）：
> "'(c) Chapter III, Sections 1, 2, and 3, with the exception of Article 6(5), shall apply from:
> (i) **2 December 2027 as regards AI systems classified as high-risk pursuant to Article 6(2) and Annex III**; and
> (ii) **2 August 2028 as regards AI systems classified as high-risk pursuant to Article 6(1) and Annex I**;'"

Recital 40 說明理由：
> "…the delayed availability of standards, common specifications, and alternative guidance and the delayed
> establishment of national competent authorities lead to challenges that jeopardise the effective entry into
> application of those obligations…"

歐盟執委會官方時間軸（AI Act Service Desk，
https://ai-act-service-desk.ec.europa.eu/en/ai-act/timeline/timeline-implementation-eu-ai-act）與
Shaping Europe's digital future 新聞「AI Omnibus enters into force」（發布 2026-07-27，更新 2026-07-31）
一致確認：Omnibus **2026-07-27 生效**；Annex III 高風險 **2027-12-02**；Annex I **2028-08-02**。

**判準 4-C（現況結論）：** 現在（2026-08-01）Annex III 高風險義務**尚未適用**，最早 2027-12-02。
即便將來產品越界，仍有 16 個月緩衝。**Art. 5 禁止行為與 Art. 50 透明度義務已經或即將適用**——
Art. 50(2) 的生成內容標記義務對「已於 2026-08-02 前上市」的生成式系統有到 2026-12-02 的過渡期
（Omnibus 第 39 點新增 Art. 111(4)）。Caliburn 若只在本機產生文字給使用者自己看、不對外發布，
Art. 50(1)（與人互動須告知）實質上由「這就是個 AI 工具」的產品本質滿足。

### 4.2 NYC Local Law 144（AEDT）：**不適用**

**權威文件：**
- DCWP, *Notice of Adoption of Final Rule*（6 RCNY Subchapter T, §§ 5-300 ff.），2023 年通過，10 頁。
  URL: https://rules.cityofnewyork.us/wp-content/uploads/2023/04/DCWP-NOA-for-Use-of-Automated-Employment-Decisionmaking-Tools-2.pdf
- DCWP, *Automated Employment Decision Tools: Frequently Asked Questions*，**06/29/2023**，6 頁。
  URL: https://www.nyc.gov/assets/dca/downloads/pdf/about/DCWP-AEDT-FAQ.pdf

**規則 §5-300 定義「substantially assist or replace discretionary decision making」逐字：**
> "i. **to rely solely on a simplified output (score, tag, classification, ranking, etc.), with no other
> factors considered**; or
> ii. **to use a simplified output as one of a set of criteria where the simplified output is weighted more
> than any other criterion in the set**; or
> iii. **to use a simplified output to overrule conclusions derived from other factors including human
> decision-making.**"

**FAQ 官方三要件（Q2）：**
> "An AEDT is a computer-based tool that: • Uses machine learning, statistical modeling, data analytics, or
> artificial intelligence. **AND** • **Helps employers and employment agencies make employment decisions.**
> **AND** • Substantially assists or replaces discretionary decision-making."

**FAQ 對範圍的官方澄清（Q5, Q6）：**
> "Q5. Is an 'employment decision' just the final hiring or promotion decision? **No. The Law defines
> employment decision more broadly to include screening.**"
> "Q6. Do the Law's requirements apply if an employer or employment agency uses an AEDT to **scan a resume
> bank, conduct outreach to potential candidates, or invite applications?** **No. The requirements apply to
> AEDT use to assess candidates for hiring or promotion only.** A candidate for employment is a person who
> has applied for a specific position…"
> "**If AEDT use is to assess someone who is not an employee being considered for promotion and who has not
> applied for a specific position for employment, the bias audit and notice requirements do not apply.**"

生效與執行日（FAQ Q1）：
> "The Law was enacted in 2021. **It took effect on January 1, 2023. Enforcement begins on July 5, 2023.**"

**判準 4-D：** LL 144 的三要件必須**同時**成立。Caliburn 不產出對任何**人**的 simplified output
（score/tag/classification/ranking），因此第三要件不成立；也不評估 candidate（Q6 的排除語直接命中）。
**LL 144 不適用。** 但若未來加入「依 JD 對應徵者排序／評分」，三要件立刻同時成立，
就會觸發 bias audit（每年一次、獨立稽核）與 notice 義務。這條界線與 4-A 的紅線是同一條。

### 4.3 EEOC 現況（2024–2026）：**指引已撤、執法方向反轉**

已核實事實：
1. EEOC 2023 年 5 月的 Title VII AI 技術協助文件
   *Select Issues: Assessing Adverse Impact in Software, Algorithms, and Artificial Intelligence Used in
   Employment Selection Procedures Under Title VII*，其官方 URL
   `https://www.eeoc.gov/laws/guidance/select-issues-assessing-adverse-impact-software-algorithms-and-artificial`
   於 2026-08-01 實測回傳 **HTTP 404**（已下架）。
2. EEOC 的 ADA/AI 資源頁
   https://www.eeoc.gov/eeoc-disability-related-resources/artificial-intelligence-and-ada
   **仍在線**，仍連結 2022 年 ADA 技術協助文件與 *Tips for Workers*，頁面**無**撤回聲明。
3. EO 14281（見 2.5(b)）指示全機關**降低 disparate-impact 執法優先度**，並要求 AG 與 EEOC 主委在 45 天內
   檢視所有依 disparate impact 理論進行中的案件。
4. DOJ OLC 2026-06-09 意見（見 2.5(a)）在行政部門內**具拘束力**，直接認定 EEOC 的 Title VII 指引（含 UGESP）違憲。
5. EEOC 於 2026-01 撤回 2024 年職場騷擾執法指引（其新聞稿
   https://www.eeoc.gov/newsroom/eeoc-delivers-administration-priorities-and-president-trumps-executive-orders 有載），
   該頁**未**提及任何 AI 指引之撤回。

**判準 4-E：** 美國聯邦層級目前**沒有**有效的 AI-in-hiring 專門指引可依循，且 disparate impact 這條
過去驅動 job analysis 嚴謹度的執法動力已被行政部門拆除。
→ 對 Caliburn 的意涵：**不要用「合規」當品質論證**。品質論證要回到專業標準（SIOP *Principles*）
與產品自身的北極星（顧問等級 JD），因為法規在這一輪反而變寬鬆且不穩定。

### 4.4 台灣

**(a) 個人資料保護法**（全國法規資料庫 pcode=I0050021，最新修正 **民國 114 年 11 月 11 日**）：
- 第 2 條：「個人資料：指自然人之姓名、出生年月日、國民身分證統一編號、護照號碼、特徵、指紋、婚姻、家庭、
  教育、**職業**、病歷…及其他得以直接或間接方式識別該個人之資料。」
- 第 5 條：「個人資料之蒐集、處理或利用，應尊重當事人之權益，依誠實及信用方法為之，
  **不得逾越特定目的之必要範圍**，並應與蒐集之目的具有正當合理之關聯。」
- 第 19 條（非公務機關蒐集處理）／第 20 條（利用限於特定目的必要範圍內）。
- 第 51 條第 1 項：「自然人為**單純個人或家庭活動**之目的，而蒐集、處理或利用個人資料」不適用本法。

**判準 4-F：** 訪談逐字稿、工作內容敘述與員工姓名／職稱綁在一起時**是個人資料**（第 2 條明列「職業」）。
員工在**工作上**使用不屬於第 51 條的家庭活動豁免（與 EU AI Act Art. 2(10) 同構）。
→ 本機儲存、不外傳、可刪除，是滿足第 5 條「必要範圍」的最直接手段；
**但呼叫 OpenRouter 就是把資料送出本機**，這在個資法下是「利用」的一種形態，
產品必須（i）在送出前讓員工知情，（ii）提供不含可識別資訊的送出模式或明確揭露。這是本輪唯一
對現行架構有實質合規影響的台灣法條。

**(b) 人工智慧基本法**（全國法規資料庫 pcode=H0160093，**民國 115 年 1 月 14 日公布**，共 20 條；
立法院 114 年 12 月 23 日三讀）：
- 第 2 條：中央主管機關為**國家科學及技術委員會**。
- 第 5 條：經中央目的事業主管機關會商數位發展部認定為**高風險應用**者，應明確標示注意事項或警語。
- 第 15 條：政府應積極運用 AI 確保勞動者之勞動權益、弭平技能落差、輔導因 AI 失業者就業。
- 第 16 條：數位發展部應推動風險分類框架，各目的事業主管機關應訂定以風險為基礎之管理規範。

**判準 4-G：** 這是**框架法**，義務主體是政府，**未直接對私人企業課予義務**；
真正的規範會透過第 16 條授權的「各目的事業主管機關風險管理規範」落地——就業／勞動領域的主管機關是勞動部，
**該規範目前尚未發布**。這是需要持續追蹤的唯一台灣變數。

**(c) 勞動部**：查到的是委託研究報告
《112 年度「人工智慧應用下之勞動權益保障—就業歧視及勞工隱私權相關權益之影響與政策建議」》
（GRB PG11212-0059，計畫編號 112-MOL-010301，
https://www.mol.gov.tw/media/syno0vkr/... ）——**研究報告，非函釋、非法規**。
另有《行政院及所屬機關（構）使用生成式 AI 參考指引》（適用對象為**政府機關**，不及於私人企業）。

**判準 4-H：** 台灣目前**沒有**針對 AI 用於職務分析／JD 的具拘束力規範。查不到函釋（見末章）。

### 4.5 第 4 題總結論

**這個產品現在不需要為法規改設計，但需要為法規釘死兩條紅線：**
1. **永不 profiling 自然人**（EU AI Act Art. 6(3) 末段的絕對條款）。
2. **永不對特定人輸出 score / tag / classification / ranking**（NYC 6 RCNY §5-300 的「simplified output」）。

只要這兩條守住，EU 高風險、NYC LL 144 都不適用；而 US 聯邦層級目前無有效 AI 指引。
唯一有實質作用的是台灣個資法第 5 條對「送出本機」的必要範圍限制。

---

## 第 5 題：2024–2026 用 LLM 做 job analysis／competency modeling 的同儕審查實證

**結論：證據稀薄。** 在 *Journal of Applied Psychology*、*Personnel Psychology*、
*Journal of Business and Psychology*、*Industrial and Organizational Psychology*、
*International Journal of Selection and Assessment* 這幾本上，**找不到**一篇直接檢驗
「LLM 生成 task statement／KSAO 的信度與效度」的實證研究。這是**誠實的空白**，不是搜尋不足。

找到的最接近的三筆（全部經 Crossref 核實書目資料）：

**(1) Kowal, J. M., Bryant, K. H., Segall, D., & Kantrowitz, T. (2025). "Harnessing Generative AI for
Assessment Item Development: Comparing AI-Generated and Human-Authored Items."
*International Journal of Selection and Assessment*, 33(3). DOI: 10.1111/ijsa.70021**
（Crossref 摘要原文，逐字）：
> "This study evaluates the efficacy of AI-generated items compared to human-authored counterparts within
> the context of employee selection testing, focusing on data science knowledge areas. Through a paired
> comparison approach, subject matter experts (SMEs) were asked to evaluate items produced by both LLMs and
> human item writers. **Findings revealed a significant preference for LLM-generated items**, particularly in
> specific knowledge domains such as Statistical Foundations and Scientific Data Analysis. **However, despite
> the promise of generative AI in accelerating item development, human review remains critical. Issues such
> as multiple correct answers or ineffective distractors in AI-generated items necessitate thorough SME
> review and revision to ensure quality and validity.**"

**判準 5-A：** 這是目前最接近的同儕審查證據，方向是「**LLM 產出品質可與人類相當甚至更受偏好，
但人類審查不可省**」。注意這是**選才題目**不是 job analysis，遷移推論要謹慎。
它支持 Caliburn 的「模型生成 + 員工決策」形狀，但**不能**被引用為「LLM 做 job analysis 有效」。

**(2) Putka, D. J., Oswald, F. L., Landers, R. N., Beatty, A. S., McCloy, R. A., & Yu, M. C. (2022).
"Evaluating a Natural Language Processing Approach to Estimating KSA and Interest Job Analysis Ratings."
*Journal of Business and Psychology*, 38(2), 385–410. DOI: 10.1007/s10869-022-09824-0**
（書目經 Crossref + Semantic Scholar 核實；**全文與摘要受付費牆保護，未逐字取得**。）
這是**前 LLM 時代**的 NLP 研究：以 job description / task statement 文字預測 KSAO 重要性評分，
以 SME 評分為效標。網路檢索片段稱交叉驗證相關達 .74/.80/.75/.84（K/S/A/Interests）——
**此數字未經一手核實，列入末章**。

**判準 5-B：** 即使是這條最正面的證據，其設計也是「**從 task 文字推導 K/S**」——
與判準 3-B(2)（task→K/S anchoring）同構。這是文獻上唯一被實證支持的 K/S 生成路徑形狀。

**(3) Keeler, J. B., Brock Baskin, M. E., Lambert, A., Clinton, M. S., & Johnson, J. B. (2022).
"Practicality of job analysis in today's world of work." *Industrial and Organizational Psychology*,
15(1), 65–69. DOI: 10.1017/iop.2021.128** —— 已核實**不涉及** generative AI／LLM。

**判準 5-C（給 ADR 用的一句話）：** 「以 LLM 做職務分析」目前**沒有**同儕審查的信效度背書。
因此 Caliburn 的品質論證**不能**建立在「文獻說 LLM 行」上，只能建立在
（a）產出物是否符合 O\*NET/NOS/UGESP 的既有寫作與連結判準，
（b）員工是否對每一條做出了有紀錄的決策。這兩者都是**可在本地驗證**的，不依賴外部實證。

---

## 第 6 題：「支持度分級」的既有權威先例

Caliburn 現行四級（`behavior_grounded` / `employee_confirmed` / `reference_candidate` / `unsupported`，
見 `docs/specs/2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md` C-08）。

**結論：這個四級體系是自創的，職務分析領域沒有等價的官方分級。** 但**每一級都能找到權威對應物**，
分別來自四個不同體系。以下逐條列出，可直接寫進 ADR 的依據欄。

### 6.1 有沒有現成的「證據分級」？——**沒有**

- **O\*NET**：沒有證據等級，但**有 provenance 與精度旗標**。
  *Data Dictionary O\*NET® 30.3 Database*（https://www.onetcenter.org/dl_files/database/db_30_3_dictionary.pdf ，121 頁）
  每一個評分列都帶：
  > "**Recommend Suppress** Character(1) Low precision indicator (Y=yes, N=no)"
  > "**Not Relevant** Character(1) Not relevant for the occupation (Y=yes, N=no)"
  > "**Domain Source** Character Varying(30) Source of the data"
  > "It's assumed that the needs of many users will be met by using O\*NET data along with the O\*NET metadata
  > that provides the recommended '**flags**' for '**Not Relevant**' or '**Recommend Suppress**'."

  `Domain Source` 的值形如 `Analyst`、`Incumbent`、`Analyst - Transition`（原文 p. 3495：
  「data is marked with '**Analyst - Transition**' in the Domain Source column」），
  且 K/S/A 各檔分別指向 *Appendix 1, Item Rating Level Statistics - **Analyst***
  或 *Appendix 2, … - **Incumbent***。

  **對映：這是 `behavior_grounded` vs `reference_candidate` 的權威原型——區分「誰說的」而不是「多可信」，
  再加一個獨立的「精度不足」旗標。** O\*NET 的做法是**兩個正交維度**（來源 × 精度），不是一條線性等級。
  Caliburn 的四級把「來源」與「強度」壓成一維，這是**簡化**，應在 ADR 裡承認。

- **UK NOS**：`essential` 是**收錄門檻**不是等級（Quality Criteria §5.8，2023-08 修訂版，
  已於 2026-07-13 spec 引用）——「只納入對有效表現 essential 者」。

- **ESCO**：官方只有二分。escopedia "Essential" 頁原文：
  > "**'Essential' are those knowledge, skills and competences that are usually required when working in an
  > occupation, independent of the work context or the employer.**"
  （https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/essential）
  對照 optional = 隨情境／雇主而異。**這是「必要性」分級，不是「證據強度」分級。**

- **SIOP *Principles* / AERA-APA-NCME *Standards***：有的是**證據來源類型學**，不是等級。
  *Principles* 5th ed., p. 9 原文：
  > "the *Standards* discusses **five sources of evidence** that can be used in evaluating a proposed
  > interpretation of selection procedure scores for a particular use: **(a) relationships between predictor
  > scores and other variables …, (b) test content, (c) internal structure of the test, (d) response
  > processes, and (e) consequences of testing.**"

  **對映：本領域的權威做法是「標示證據**種類**」而非「排證據**強弱**」。**

### 6.2 醫學 GRADE：唯一真正的四級證據分級，且**確實是四級**

**權威原著：** GRADE Working Group, "Grading quality of evidence and strength of recommendations,"
***BMJ* 2004;328(7454):1490**, DOI: 10.1136/bmj.328.7454.1490
（開放取用全文：https://pmc.ncbi.nlm.nih.gov/articles/PMC428525/ ）

四級定義逐字：
> **High**: "Further research is very unlikely to change our confidence in the estimate of effect."
> **Moderate**: "Further research is likely to have an important impact on our confidence in the estimate of
> effect and may change the estimate."
> **Low**: "Further research is very likely to have an important impact on our confidence in the estimate of
> effect and is likely to change the estimate."
> **Very low**: "Any estimate of effect is very uncertain."

> "**The strength of a recommendation indicates the extent to which one can be confident that adherence to
> the recommendation will do more good than harm.**"

**判準 6-A（GRADE 給 Caliburn 的三個可直接借用的設計原則）：**
1. **等級定義用「未來新證據會不會推翻」寫，不用「來源是誰」寫。** GRADE 的四級全部是
   *confidence in the estimate*，而 Caliburn 的四級全部是*來源*。
   → 可改進處：每一級應**同時**寫出「這一級意味著什麼會推翻它」（例：`employee_confirmed` 的推翻條件
   是「找不到對應 task」），這會讓等級可操作、可被員工理解。
2. **升降級有明文條件**（GRADE 有 −1/−2 的 study limitations、inconsistency、indirectness、imprecision、
   reporting bias，與 +1/+2 的 strong association、dose-response）。
   → Caliburn 的四級目前**沒有降級條件**。
   > **【2026-08-01 更正】** 本條原文提議以「員工照單全收 bogus 參照項」作為明文降級條件，
   > 隨判準 3-B(4) 一併**撤回**（理由見該處）。降級條件仍待設計，但不得以在產品內欺瞞員工的方式取得。
3. **證據等級 ≠ 建議強度。** GRADE 明確把兩者拆開。
   → 對映：「支持度」（證據）與「可否進正式 JD」（行動）應該是兩張表，
   現行設計把它們併在同一張表的第三欄，是可接受的簡化，但擴充時要記得這是兩件事。

**GRADE 有沒有被 HR 借用？** 本輪**未**在 SIOP / O\*NET / ESCO / NOS 的官方文件中找到 GRADE 的採用或引用。
列入末章。

### 6.3 對現行四級的逐條裁決

| Caliburn 級別 | 有無權威先例 | 依據 |
|---|---|---|
| `behavior_grounded` | **有，且是法規要求** | 29 CFR §1607.14C(4)：K 須是「used in and is a necessary prerequisite for **observable aspects of work behavior**」；S/A 須「defined in terms of observable aspects of work behavior」。這一級不是「最高級」，是**法規意義下唯一成立的那一級**。 |
| `employee_confirmed` | **無先例，且被實證點名為高風險** | Morgeson et al. (2004)：員工「認領為本職一部分」正是產生 d≈.52 膨脹的那個動作；bogus ability 認領 d=.55。這一級應理解為**待驗證**，不是「次高證據」。 |
| `reference_candidate` | **有，對映 O\*NET `Domain Source = Analyst`** | 非在職者來源。Morgeson et al. (2004) p. 683 明說 nonincumbent judgments「less likely to be systematically inflated」——所以它在**膨脹**這一軸上其實比 `employee_confirmed` **更乾淨**，只是在**本職特異性**這一軸上更差。**現行把它排在 `employee_confirmed` 之下是把兩個正交軸壓成一維的後果。** |
| `unsupported` | **有，對映 O\*NET `Recommend Suppress` / NOS 非 essential** | 且依 §1607.14C(4)，無 behavior 連結者根本不構成 content 證據 → 現行「不可入正式 JD」正確。 |

**判準 6-B（給 ADR 的一句話）：** 四級支持度**是 Caliburn 自創**，領域內無等價官方體系；
但其**兩端**（`behavior_grounded` / `unsupported`）有 29 CFR §1607.14C(4) 的直接法源，
**中間兩級**的排序是本 repo 的設計選擇，且與 O\*NET 的「來源 × 精度」正交模型不同。
若日後要重構，最有依據的方向是**拆成兩個欄位**：`source`（incumbent / reference / model）
與 `behavior_link`（linked / claimed / none），這正是 O\*NET 的做法。

---

## 來源總表

| # | 主題 | 文件名 | 版本／日期 | URL | 取得方式 |
|---|---|---|---|---|---|
| 1 | 專業標準 | SIOP, *Principles for the Validation and Use of Personnel Selection Procedures* | **5th Edition, August 2018**（APA Council 2018-08 採為 APA 政策） | https://www.apa.org/ed/accreditation/personnel-selection-procedures.pdf | 下載 PDF，60 頁全文逐頁 |
| 2 | 美國法規 | 29 CFR § 1607.14, *Uniform Guidelines on Employee Selection Procedures (1978)* | **CFR 2024 年版（rev. 2024-07-01）**，印刷頁 pp. 227–233 | https://www.govinfo.gov/content/pkg/CFR-2024-title29-vol4/xml/CFR-2024-title29-vol4-sec1607-14.xml | GPO 官方 XML granule，全條逐字 |
| 3 | 美國行政 | DOJ OLC, *Constitutionality of Disparate-Impact Liability Under Title VII*, 50 Op. O.L.C. __ | **2026-06-09** | https://www.justice.gov/olc/media/1444871/dl | 下載 PDF，25 頁 |
| 4 | 美國行政 | EO 14281, *Restoring Equality of Opportunity and Meritocracy* | 簽署 2025-04-23；**90 FR 17537, 2025-04-28** | https://www.federalregister.gov/documents/full_text/text/2025/04/28/2025-07378.txt | Federal Register 官方全文 |
| 5 | 美國行政 | OPM, *Removal of References to the Uniform Guidelines on Employee Selection Procedures in Federal Personnel Regulations*（interim final rule） | **91 FR 48234, 2026-07-31**（即日生效） | https://www.federalregister.gov/documents/full_text/text/2026/07/31/2026-15586.txt | Federal Register 官方全文 |
| 6 | 學術原著 | Morgeson & Campion, "Social and Cognitive Sources of Potential Inaccuracy in Job Analysis" | ***JAP* 1997, 82(5), 627–655** | http://www.morgeson.com/downloads/morgeson_campion_1997.pdf | 作者站出版版 PDF，29 頁全文 |
| 7 | 學術原著 | Morgeson, Delaney-Klinger, Mayfield, Ferrara & Campion, "Self-Presentation Processes in Job Analysis" | ***JAP* 2004, 89(4), 674–686** | http://www.morgeson.com/downloads/morgeson_delaney-klinger_mayfield_ferrara_campion_2004.pdf | 作者站出版版 PDF，13 頁全文 |
| 8 | 歐盟法規 | Regulation (EU) **2024/1689**（AI Act） | OJ L, 2024/1689, **12.7.2024** | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689 | EUR-Lex 官方 HTML 全文 |
| 9 | 歐盟法規 | Regulation (EU) **2026/1744**（Digital Omnibus on AI），amending 2024/1689 | of **8 July 2026**；OJ **24.7.2026**；生效 2026-07-27 | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202601744 | EUR-Lex 官方 HTML 全文 |
| 10 | 歐盟官方 | European Commission, *Timeline for the Implementation of the EU AI Act*（AI Act Service Desk） | 現行（含 Omnibus 修正後日期） | https://ai-act-service-desk.ec.europa.eu/en/ai-act/timeline/timeline-implementation-eu-ai-act | 官方頁 |
| 11 | 歐盟官方 | European Commission, *AI Omnibus enters into force* | 發布 **2026-07-27**，更新 2026-07-31 | https://digital-strategy.ec.europa.eu/en/news/ai-omnibus-enters-force | 官方新聞頁 |
| 12 | 紐約市 | NYC DCWP, *Notice of Adoption of Final Rule*（6 RCNY Subchapter T, §§ 5-300 ff.） | 2023 年通過 | https://rules.cityofnewyork.us/wp-content/uploads/2023/04/DCWP-NOA-for-Use-of-Automated-Employment-Decisionmaking-Tools-2.pdf | 官方 PDF，10 頁 |
| 13 | 紐約市 | NYC DCWP, *Automated Employment Decision Tools: FAQ* | **06/29/2023** | https://www.nyc.gov/assets/dca/downloads/pdf/about/DCWP-AEDT-FAQ.pdf | 官方 PDF，6 頁 |
| 14 | 美國機關 | EEOC, *Artificial Intelligence and the ADA* 資源頁（2022 年文件仍在線） | 現行（2026-08-01 實測） | https://www.eeoc.gov/eeoc-disability-related-resources/artificial-intelligence-and-ada | 官方頁 |
| 15 | 台灣法規 | 個人資料保護法 | **民國 114 年 11 月 11 日**修正 | https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=I0050021 | 全國法規資料庫 |
| 16 | 台灣法規 | 人工智慧基本法（20 條） | **民國 115 年 1 月 14 日公布**（立法院 114-12-23 三讀） | https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=H0160093 | 全國法規資料庫 |
| 17 | 台灣官方 | 勞動部委託研究《112 年度 人工智慧應用下之勞動權益保障—就業歧視及勞工隱私權相關權益之影響與政策建議》（GRB PG11212-0059） | 112 年度 | https://www.mol.gov.tw/media/syno0vkr/ （GRB 檔） | 官方報告（非法規） |
| 18 | 學術（實證） | Kowal, Bryant, Segall & Kantrowitz, "Harnessing Generative AI for Assessment Item Development" | ***IJSA* 2025, 33(3)**, DOI 10.1111/ijsa.70021 | https://doi.org/10.1111/ijsa.70021 | Crossref 官方書目 + 出版摘要逐字 |
| 19 | 學術（實證） | Putka, Oswald, Landers, Beatty, McCloy & Yu, "Evaluating a NLP Approach to Estimating KSA and Interest Job Analysis Ratings" | ***JBP* 2022, 38(2), 385–410**, DOI 10.1007/s10869-022-09824-0 | https://doi.org/10.1007/s10869-022-09824-0 | Crossref + Semantic Scholar 書目（**全文未取得**） |
| 20 | 學術（背景） | Keeler, Brock Baskin, Lambert, Clinton & Johnson, "Practicality of job analysis in today's world of work" | ***IOP* 2022, 15(1), 65–69**, DOI 10.1017/iop.2021.128 | https://doi.org/10.1017/iop.2021.128 | Cambridge Core 頁 |
| 21 | 證據分級 | GRADE Working Group, "Grading quality of evidence and strength of recommendations" | ***BMJ* 2004;328(7454):1490** | https://pmc.ncbi.nlm.nih.gov/articles/PMC428525/ | PMC 開放全文 |
| 22 | 資料標示 | National Center for O\*NET Development, *Data Dictionary O\*NET® 30.3 Database* | **30.3**（現行） | https://www.onetcenter.org/dl_files/database/db_30_3_dictionary.pdf | 官方 PDF，121 頁 |
| 23 | 定義 | ESCO escopedia, "Essential" | 現行 | https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/essential | 官方頁逐字 |

---

## 查不到／需二次確認（誠實清單）

1. **Putka et al. (2022) 的交叉驗證相關係數（.74 / .80 / .75 / .84）**：來自網路檢索片段，
   **未經一手核實**（*JBP* 全文與摘要皆在 Springer 付費牆後，Crossref 與 Semantic Scholar 的 abstract 欄位
   均被出版商遮蔽）。引用前必須取得全文。書目資料（作者／卷期／頁碼／DOI）已經 Crossref 核實。

2. **SIOP *Principles* 對「在職者自評膨脹」有無明文警語**：全文逐字搜尋 `inflat` / `self-report` /
   `distort` / `incumbent` 後，**只找到**（a）p. 8 建議納入多位在職者與 SME、（b）p. 15 要求
   SME「qualified and **unbiased**」、（c）p. 11 對 self-report noncognitive 測驗 faking 的討論
   （那是講**受測者**不是講 job analysis 提供者）、（d）p. 30 保密提升正確性。
   **《Principles》未直接引用 Morgeson & Campion 的膨脹發現。** 若要主張「SIOP 警告過在職者膨脹」，
   證據不足，不要這樣寫。

3. **EEOC 2023 年 5 月 Title VII AI 技術協助文件的正式撤回紀錄**：只確認原 URL 回傳 404，
   **找不到**任何官方公告說明它被撤回、撤回日期或撤回理由。EEOC 的
   「EEOC Delivers on Administration Priorities…」新聞稿列了騷擾指引與平權措施指引的撤回，
   **未提 AI 指引**。因此「已下架」是實測事實，「已正式撤回」則**未經確認**。

4. **29 CFR Part 1607 本身是否已被 EEOC 提案廢止**：查詢 Federal Register API
   （agency = EEOC，2025-01-01 起，term 含 1607）只回傳 2 筆，皆非 Part 1607 的廢止程序。
   截至 2026-08-01，**Part 1607 條文仍在 CFR 上**，但 DOJ OLC 已宣告其違憲、OPM 已移除引用。
   EEOC 自身的後續動作待追蹤。

5. **台灣勞動部對 AI 用於招募／職務分析的函釋**：**查不到**。
   只查到委託研究報告（非拘束力）與適用政府機關的生成式 AI 參考指引。
   人工智慧基本法第 16 條授權各目的事業主管機關訂定風險管理規範，就業／勞動領域的規範**尚未發布**。

6. **人工智慧基本法的公布日與三讀日**：全國法規資料庫顯示公布日為**民國 115 年 1 月 14 日**，
   立法院三讀為 114 年 12 月 23 日；moda 新聞稿的 WebFetch 摘要一度把「114 年 12 月 23 日」誤譯為
   西元 2024 年。以全國法規資料庫為準。**第 5 / 15 / 16 條為 WebFetch 摘要引述，未逐字核對條文原文**，
   引用前建議直接開條文頁核對。

7. **GRADE 是否被 HR／I-O 官方體系採用**：在 SIOP *Principles*、O\*NET、ESCO、UK NOS 的官方文件中
   **未找到** GRADE 的引用或採用。因此本篇只把 GRADE 當**設計參照**（他領域的成熟做法），
   **不主張** HR 領域已借用它。

8. **NYC Admin Code § 20-870 的法條逐字定義**：未取得（amlegal 與 nyc.gov 對本工具回 403）。
   本篇引用的是 DCWP 官方**規則**（6 RCNY § 5-300）與官方 **FAQ** 的逐字內容，兩者均為一手，
   但「automated employment decision tool」「employment decision」的**法律條文原文**未逐字核實。

9. **O\*NET `Domain Source` 欄位的完整取值清單**：Data Dictionary 只把它定義為
   "Source of the data"（Character Varying(30)），實際取值散落在各檔說明與附錄中；
   本篇確認的取值為 `Analyst`、`Incumbent`、`Analyst - Transition`，**不保證窮盡**。
