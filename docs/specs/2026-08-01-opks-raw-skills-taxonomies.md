---
title: O/P/K/S 原料研究 —— 技能 taxonomy 現況、業界綁定做法與繁中可行性
date: 2026-08-01
purpose: >
  為 Caliburn Task Analysis 引擎的 K/S（知識/技能）欄位裁決提供權威依據：
  各國際 taxonomy 的 2025–2026 現行版本／授權／中文支援／機器可讀性，
  大廠 HR 產品實際怎麼把 JD／職務分析綁上受控 taxonomy，
  以及對「繁體中文、單一職務、本機」這個產品形態的利弊。
source_discipline: >
  只收標準機構／政府官方一手文件與大廠官方技術／開發者文件。
  每條主張標文件名 + URL + 版本／年份。全部經 WebFetch 實際開啟原始頁面後撰寫；
  無法開啟（JS 渲染、PDF 二進位）者一律標「未核實」並列入文末清單，不憑記憶補寫。
---

# O/P/K/S 原料研究 —— taxonomy 現況、業界綁定做法與繁中可行性

> **【現行裁決】** 本檔是**研究原料**。OPKS 的現行裁決是 **[ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md) ＋ [0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md) ＋ [0050](../adr/0050-opks-proposal-minimal-shape.md) ＋ [0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)**（四份一起讀）。
> 本檔的建議凡與四份 ADR 不符者，**一律以 ADR 為準**。


## 0. 這份補什麼（與 2026-07-13 那份的分工）

`docs/specs/2026-07-13-ai-redesign-raw-intl-competency-standards.md` 已研究過 ESCO/O\*NET/SFIA 的
**定義與句式**（task 三段式、knowledge 名詞化、SFIA 四軸判級等），本檔**不重複**。

本檔補三件 2026-07-13 沒查的事：
1. 這些 taxonomy **現在的版本、授權、機器可讀性、中文支援**（能不能真的拿來用）。
2. **大廠實際怎麼做**：自由生成技能 vs 對映受控 taxonomy；skill inference；證據與熟練度。
3. 對**繁中／單一職務／本機**這個形態的**裁決建議**。

---

## 1. 各 taxonomy 現況（逐一查官方）

### 1.1 O\*NET（美國勞工部）—— 版本最新、授權最寬、階層最完整；但**只有英文**

| 項目 | 事實 | 來源 |
|---|---|---|
| 最新版本 | **O\*NET 30.3**，**2026 年 5 月**發布 | O\*NET Resource Center, *O\*NET Database*（onetcenter.org/database.html）；*Database Releases Archive*（onetcenter.org/db_releases.html） |
| 發布節奏 | 一年 3–4 版：30.2（2026-02）、30.1（2025-12）、30.0（2025-08）、29.3（2025-05）、29.2（2025-02）、29.1（2024-11）、29.0（2024-08） | 同上 db_releases.html |
| 授權 | **Creative Commons Attribution 4.0 International**。官方要求：標註「O\*NET 30.3 Database」與「U.S. Department of Labor, Employment and Training Administration」、連結授權條款、標示是否修改；若修改須註明「USDOL/ETA has not approved, endorsed, or tested these modifications」。O\*NET 為註冊商標，須當**形容詞**用（"O\*NET data"），不可當名詞／動詞／所有格／複數 | onetcenter.org/license_db.html（O\*NET 30.3） |
| 格式 | Excel / CSV / JSON / SQL / RDF，可整包 ZIP 下載 | onetcenter.org/db_releases.html、/dictionary/30.3/excel/ |

**Task → DWA → IWA → GWA 階層（官方）**

- 官方階層陳述（*GWAs to IWAs to DWAs* 檔頁）：
  > "Each Detailed Work Activity…is linked to exactly one Intermediate Work Activity, which in turn is linked to exactly one Work Activity from the O\*NET Content Model."
  → **DWA →(1:1)→ IWA →(1:1)→ GWA**，GWA 就是 Content Model 4.A 的 Work Activities。
- Task ↔ DWA 是**多對多**（*Tasks to DWAs* 檔頁官方說明）：
  > "Each DWA is mapped to multiple task statements, and each referenced task statement is mapped to one or more DWAs."
- 規模（O\*NET 30.3 資料字典逐檔頁）：
  - **Task Statements**：18,796 列，8 欄（O\*NET-SOC Code / Title / **Task ID** / Task / **Task Type**（Core 或 Supplemental）/ Incumbents Responding / Date / Domain Source）。Task 欄長度上限 1000 字元。
  - **Tasks to DWAs**：23,850 列，8 欄（含 DWA Element ID / DWA Element Name）。
  - **GWAs to IWAs to DWAs**：2,087 列，6 欄（GWA/IWA/DWA 各一組 ID+Name）。
  - **Work Activities**（職業層級評分）：73,308 列。
- O\*NET Online 官方說明：DWA 是「over 2,000 detailed work activities performed across a small to moderate number of occupations」；IWA 是「over 300 of these more general activities」。GWA 為 Content Model 4.A 四大類（Information Input / Mental Processes / Work Output / Interacting With Others），官方定義：
  > "Work activities are general types of job behaviors occurring on multiple jobs."

**對本產品的意義**：Task→DWA 對映檔**公開可下載、CC BY 4.0**，是四個 taxonomy 中授權最乾淨的。
但**沒有任何中文版**，且 DWA 的粒度是「跨職業共用的活動」，不是「這位員工的具體任務」。

---

### 1.2 ESCO（歐盟執委會）—— **沒有 v2**；28 語系但**沒有任何中文**

| 項目 | 事實 | 來源 |
|---|---|---|
| 最新版本 | **v1.2.1（minor）**，官方公告發布日 **2025-12-22**；分類頁另顯示 "last updated on December 10, 2025" | esco.ec.europa.eu/en/news/esco-v121-live；/en/classification/skill_main |
| 版本史 | v1（2017 中）→ v1.1 major（2022-01）→ v1.1.1 minor（2022-09）→ v1.1.2 minor（2024-02）→ **v1.2 major（2024-05）** → v1.2.1 minor（2025-12） | escopedia《ESCO versions》 |
| **v2 狀態** | **官方未公告 v2，也沒有時程**。官方版本政策：major = "creation of new content, semantic revisions and adjustments to the data model"；minor = "focus only on quality improvements without introducing new content" | escopedia《ESCO versions》 |
| 概念數 | **3,039 occupations / 13,939 skills**（skills 含 knowledge、language skills、transversal） | esco.ec.europa.eu/en/about-esco/what-esco；/en/classification/skill_main |
| v1.2 增量 | 新增 "35 occupations, 42 new skills and 196 new knowledge concepts"、677 alternative labels，12,000+ 概念受品質改善影響 | escopedia《ESCO v1.2》 |
| v1.2.1 改了什麼 | 只有翻譯更新、去除 preferred/alternate label 重複、occupation 品質複查、green skill 關係修訂、新增替代標籤；**沒有新增或移除內容** | esco.ec.europa.eu/en/news/esco-v121-live |
| 語系 | **28 語系**：24 個 EU 官方語 + Arabic、Icelandic、Norwegian Bokmål、Ukrainian。**沒有中文（簡體或繁體都沒有）** | escopedia《ESCO languages》；ESCO FAQ |
| 授權 | 依 **Commission Decision 2011/833/EU（2011-12-12）**，可免費下載、使用、重製、再利用於任何目的。官方要求標註：`"This service uses the ESCO classification of the European Commission."`；修改版須明確標示為修改版 | ESCO FAQ（esco.ec.europa.eu/en/about-esco/faq） |
| Bulk download | CSV / JSON-LD / ODS / RDF / TTL / XML，全 28 語系；另有 **Delta File**（列出與前版差異的概念） | esco.ec.europa.eu/en/use-esco/download；v1.2.1 公告 |
| API | 兩種：**Web-Service API**（machine-to-machine）與**可下載的 Local API**（本機／自有伺服器安裝，"increased performance and independence from the availability of the service"）。API 軟體本身授權 **EUPL 1.2**（底層元件 SOLR/Fuseki/Tomcat/Spring 為 Apache 2.0）。官方註記目前 local API 版本 "provided for reference only and will be replaced shortly" | esco.ec.europa.eu/en/use-esco/use-esco-services-api；escopedia《ESCO API》 |

**skills pillar 結構（escopedia 官方頁摘述，非逐字）**：2019 建立階層，四個 sub-classification —— Knowledge、
Language skills and knowledge、Skills、Transversal skills。**階層第二層是把美國 O\*NET 的 332 個
Intermediate Work Activities 對映進來建的**（歐盟官方直接複用 O\*NET IWA 當骨架，這點對我們判斷
「要不要自建骨架」很關鍵）。每個概念的 metadata：preferred term / non-preferred terms / hidden terms /
description / definition / scope note / skill type / **reusability level** / 與職業的 essential 或 optional 關係。
官方明說 **skills 與 competences 在 pillar 內不做區分**。

**reusability level 四層（官方定義）**：
> "The skills reusability level in ESCO indicates, how widely a knowledge, skill or competence concept can be applied."
transversal → cross-sectoral → sector-specific → occupation-specific。

**ESCO 沒有 proficiency（熟練度）**：skills pillar 頁的 metadata 清單只有 reusability level，
**沒有任何 proficiency / mastery level 欄位**。ESCO 的「級別」概念在 **EQF**（8 級，學習成果導向）那一側，
不掛在單一 skill 上。（EQF 三維描述子見 2026-07-13 spec 第 5b 節。）

---

### 1.3 Lightcast Open Skills —— 更新最快，但**只給 API、授權要談、無中文**

| 項目 | 事實 | 來源 |
|---|---|---|
| 規模 | 官方頁：`"Our collection of 34,000+ skills comes from real-world use cases, honed by in-house experts"`；同頁另處與官方 KB 寫 "over 33,000 skills" | lightcast.io/open-skills；kb.lightcast.io《Lightcast Skills Taxonomy》 |
| 結構 | `"a 3-tier hierarchy, with many skills grouped into Categories and Subcategories"` | kb.lightcast.io 同上 |
| 技能型別 | **Specialized Skills**（如 Java、financial analysis）／**Common Skills**（如 communication）／**Certifications and Licenses**；另可辨識口語語言與軟體技能 | lightcast.io/open-skills/faqs；kb.lightcast.io |
| 更新頻率 | KB：`"Lightcast Skills are refreshed every 4 weeks…"`；FAQ：`"We release a new version of the library monthly."`（兩處說法一致等價：約每月一版） | 同上兩處 |
| 取用方式 | **只給 API，不給下載清單**。官方 FAQ 原文：`"We offer an API, rather than a downloadable list, because skills are constantly changing."` 另有免費瀏覽用的 Skills Library 網頁 | lightcast.io/open-skills/faqs |
| 授權 | 官方頁：非營利／公益用途註冊後 `"we'll set you up with full access, free of charge"`；FAQ：`"Your use of the taxonomy is determined by the type of license you request."` **完整條款在 legal.lightcast.io，本輪未開啟 → 見文末需二次確認** | lightcast.io/open-skills；/open-skills/faqs |
| 抽取方法 | 官方 KB：先對 job posting 做 segmentation/tokenization，再掃描指示技能的字序列；用上下文消歧（例：AWS = American Welding Society vs Amazon Web Services）；`"A confidence score is assigned, and accuracy thresholds ensure quality predictions are displayed."` | kb.lightcast.io |
| 中文 | 官方 FAQ 只提到地理覆蓋（US/Canada、UK、Europe、Asia Pacific），**未提任何語系翻譯**。視為無中文 | lightcast.io/open-skills/faqs |

**對本產品的意義**：本機、離線友善的產品**不適合**依賴一個「不給下載、只給雲端 API、條款要個案談」的 taxonomy。

---

### 1.4 SFIA 9 —— 授權對「做成工具」明確收費；**只有簡體中文，沒有正體中文**

| 項目 | 事實 | 來源 |
|---|---|---|
| 版本 | `"SFIA 9 is the new version of the global skills and competency framework for the digital world - published in October 2024."` | sfia-online.org/en/sfia-9 |
| 變更 | 相對 SFIA 8：新增 26 skills、10 skills 更名、5 skills 重構／拆分、60 levels added、7 levels moved/replaced；generic attributes 每級加上 "Essence" 陳述 | sfia-online.org/en/sfia-9 |
| 結構 | 7 級責任層級 + generic attributes / behavioural factors；`"Each skill is defined at relevant levels of responsibility, reflecting real-world practices. Not all skills are defined at all seven levels…"` | sfia-online.org/en/about-sfia/how-sfia-works |
| **授權（關鍵）** | 免費：`"For personal career development and for the majority of internal use for staff management and workforce development, SFIA is available free of charge."`<br>**需付費授權**（官方逐條）：`"using SFIA to support the sale or marketing of any product or service"`、`"using SFIA for external certification or credentials"`、`"using SFIA for recruitment as a service offering"`、`"using SFIA to promote a company or organisation, including in rate cards"`、`"using SFIA across a large organisation"`、**`"redistributing SFIA material in electronic or printed form to any other organisation"`**、**`"translating SFIA into another language or language variant and distributing that version"`**。不可 sub-licence | sfia-online.org/en/about-sfia/licensing-sfia/using-and-licensing-sfia |
| 語系 | 網站 13 個語系：English、Deutsch、Español、Français、Italiano、Nederlands、Polski、Português、Français (Canada)、العربية、**中文（簡體）**、日本語、Русский。**清單中沒有繁體／正體中文**；實際開啟 `sfia-online.org/zh/sfia-9` 確認為簡體中文頁（`sfia-online.org/zh-hans/...` 為 404，語言路徑是 `/zh/`） | sfia-online.org/en/sfia-9/documentation；sfia-online.org/zh/sfia-9 |
| 官方翻譯政策 | 翻譯須由 SFIA Foundation 的翻譯管理系統完成才算官方、才受支援；自行翻譯並散布屬需授權行為（見上） | SFIA 授權頁 + 搜尋摘要（翻譯政策細節頁未逐字開啟 → 需二次確認） |

**對本產品的意義**：把 SFIA 的技能名稱／級別描述**內建進 Caliburn 這個產品**，即使本機執行、
即使免費，也落在 `"building SFIA into a support tool of any kind"` 的商用開發範圍；
若再自譯成繁中散布，直接踩到「translating…and distributing」那條。**SFIA 不宜當內建詞彙表**，
只宜當**判級的內部教材／設計參考**（現況即 2026-07-13 spec 的用法，維持即可）。

---

### 1.5 台灣 iCAP 職能基準 —— **唯一原生繁中**；但**開放資料只有清單，沒有內容**

| 項目 | 事實 | 來源 |
|---|---|---|
| 收錄量 | 平台查詢結果頁顯示 **2,986 項**：各部會職業別職能基準 2,665 項、勞動部技能檢定規範 255 項、教育部專業職能 66 項 | icap.wda.gov.tw/ap/resources_datum_list.php（2026-08-01 讀取） |
| 取得方式 | 逐份下載 **PDF 或 ODT**；ODT 需登入個人／單位會員；**下載時須填「下載認同調查表」**。平台採 ODF 開放文件格式 | 同上；icap.wda.gov.tw/ap/knowledge_downLoad.php |
| 著作權 | 網站頁尾：**「版權所有：勞動部勞動力發展署」** | icap.wda.gov.tw/ap/index.php |
| **政府開放資料** | data.gov.tw 資料集 **21198「職能基準資料檔」**：提供機關 勞動部勞動力發展署；格式 CSV / JSON / XML / WEBSERVICES；**更新頻率 每 1 年**；**授權方式「政府資料開放授權條款-第 1 版」**；2015-09-07 上架 | data.gov.tw/dataset/21198；data.gov.tw/api/v2/rest/dataset/21198 |
| **開放資料的真實內容（實測）** | 直接下載 1150102 版 CSV，**表頭只有 5 欄**：<br>`序號,職能基準名稱,發展單位,有效期限,備註`<br>首列如 `1,RF研發工程師,經濟部,1171231,`<br>→ **這是「有哪些職能基準」的清單 metadata，完全不含 T/O/K/S/A 內容**。三個年度版分別 801／830／870 筆 | apiservice.mol.gov.tw/OdService/download/A17020000J-000019-JbU（CSV，1150102 版） |

**對本產品的關鍵結論**：repo 既有的 OCS JSON 資料（`apps/pdf-to-json` 解析 PDF 而來）之所以要自己解析 PDF，
原因在此 —— **官方沒有把職能基準內容做成機器可讀開放資料**，開放的只是名稱清單。
所以：
- **不存在**可自動同步的「iCAP 職能基準內容 API」；更新機制是人工重新抓 PDF。
- 「政府資料開放授權條款-第 1 版」**只覆蓋那份 5 欄清單**，不等於覆蓋各部會職能基準 PDF 全文；
  PDF 全文的權利狀態是「版權所有：勞動部勞動力發展署」+ 下載認同調查表，**與開放資料授權不是同一件事**。
  → 若未來要對外散布內建的 OCS 語料，須另行確認（見文末清單）。

---

## 2. 業界主流做法（只引大廠官方文件）

**先講結論**：**沒有一家大廠讓 AI 自由生成技能字串當最終資料**。
一致模式是 **「LLM/ML 從自由文字抽取 → 對映到受控 taxonomy 的 canonical concept → 人類確認」**。

### 2.1 Microsoft People Skills（Microsoft Learn，官方文件，2026-05／07 更新）

- 定位（官方原文）：
  > "People Skills is an AI-driven service that uses state-of-the-art AI to generate personalized skill profiles for your users **mapped to a customizable, built-in taxonomy**."
- **內建 taxonomy 的來源**：官方功能表逐字列 **"People Skills taxonomy (powered by LinkedIn)"**。
  另一份官方文件在資料來源清單直接指向 LinkedIn Skills Graph（"Provides a base skills taxonomy and semantic descriptions for skills"）。
- **規模與管理**：out-of-the-box library 官方建議 `"use all 16,000 skills, with a minimum of 500 skills"`；
  管理員可加自訂技能、可刪、可匯入匯出、可把敏感技能標為 **AI-restricted**（AI 不得推論出來，但使用者仍可手動選）。
- **推論方式（官方原文）**：
  > "People Skills uses large language models to assign skills. The skills assigned to users are **skills most closely matched in the taxonomy** for the user profile and activity."
  訊號來自 Microsoft Graph（profile、job title、協作訊號、郵件／會議／文件的 key phrase）；
  **不採用 90 天以前的活動**；初次計算 48 小時～5 天，之後**每 30 天** refresh。
- **證據／可信度處理**：官方區分 **"Skill confirmed by user"** 與 **"Skill inferred by AI"**；
  UI 上 AI 生成技能顯示灰色、使用者確認的顯示藍色打勾（Viva Insights Skills landscape report 可只篩 confirmed）。
- 官方自陳限制：`"They aren't intended to be a comprehensive reflection of a person's capabilities."`；
  且 `"Inferences are impacted by the skill name and description uploaded by customer administrators."`
  → **詞彙表的命名與描述品質直接決定推論品質**。
- **proficiency**：官方文件**沒有**熟練度分級欄位（只有 confirmed / inferred 二分）。
- 語系：官方文件未說明多語支援 → 未核實。

### 2.2 Workday Skills Cloud

- **API 層的硬證據（community.workday.com production API，Talent v46.2 / v40.2）**：
  - Talent 服務有 `Get_Skills`（"This operation retrieves skill items."）、`Put_Skill`、`Manage_Skills`
    （"allows adding and removing the Skills for a worker"）、`Get_Skill_Item_Categories`、`Get_Skill_Category_Groups` 等。
  - **`Import_External_Skill_Mapping`**："This high-volume web service configures external skill mapping data."
    欄位包含 `External_Skill_ID`、`External_Skill_Source_Vendor`、`External_Skill_Name`、**`Match_Type`**、
    **`Workday_Skill_Reference`**（Skills Cloud 的技能 ID）、`Workday_Skill_Name`、**`Map_To_Skill`**。
    每筆外部技能三種處置：map 到既有 Workday skill／建立新的 maintained skill／略過。
    文件亦載有防呆訊息 "change [the] mapping for this skill because it's an exact match of a Skills Cloud skill"。
  → **這就是「外部自由詞彙 → 內部受控 taxonomy」的正規化管線本身**，寫進 API 契約。
  - `Manage_Skills` 的 request 只有 `Skill_Item_Reference` / `Skill_Name` / `Remove_Skill`，
    **沒有 proficiency 欄位**；服務目錄另有「Proficiency Rating Scales」但本輪未取得細節（見文末）。
- **產品層陳述（Workday 官方部落格，2022）**：Skills Cloud 使用 graph technology 維護技能並描述技能間關聯；
  功能包含 "skill suggestions and inference"、**"Skills level to measure a worker's skill proficiency"**、
  "Skills data interoperability"；並經 Skill Software Alliance 夥伴（Aon、Degreed、SkyHive）提供
  "delivered pre-mapped skills ontologies"。
  （註：此為廠商官方部落格，非技術文件；引用時標明來源層級。）

### 2.3 LinkedIn Skills Graph（LinkedIn Engineering 官方部落格）

- 規模：**39,000+ skills**、**26 languages**、**374,000+ aliases**（"different ways to refer to the same skill -
  e.g., 'data analysis' and 'data analytics'"）、**200,000+ 技能間連結**；圖上連結 875M people、59M companies。
- 做法：稱為 **"Structured Skills"**，重點是 "mapping the relationships it has to other skills around it"；
  以 NLP 從 job descriptions／summaries 抽取，人工標註者 "connect text found across jobs, profiles, and
  learning courses, **to specific skills in our taxonomy**"，模型學會辨識同一技能的不同說法。
- → **canonical concept + 多語 alias**，語言只是 label，概念 ID 才是主體。

### 2.4 SAP SuccessFactors Talent Intelligence Hub —— **本輪無法核實**

help.sap.com 為 JS 渲染，WebFetch 只取得站台標題，**四次不同 URL 形式（docs/、viewer/、release-information .html、加 locale 參數）皆無法取得正文**。
可確認的只有官方存在下列標題的文件頁（來自官方站內搜尋結果，非正文）：
《Using Talent Intelligence Hub》《Adding Attributes to the Growth Portfolio》
《Overview of the Redesigned Growth Portfolio》**《Configuring the Proficiency Level Scale》**
**《Skill Inferencing in Talent Intelligence Hub》**《Migrating from Job Profile Builder to Talent Intelligence Hub》。
→ 可推論 SAP 具備「集中 Attribute Library + 可設定的 proficiency level scale + skill inferencing」，
但**細節（層級數、名稱、推論來源）一律未核實**，見文末清單。

### 2.5 Salesforce / ServiceNow —— 對照組

- **Salesforce**：`Skill` DMO 官方定義 `"The proficiency, competence, or expertise an employee has, which is
  valuable to the organization's mission."`，欄位只有 Id/Name/DataSourceId 等，
  **官方文件未指定任何 taxonomy 來源或階層**。Chatter/WDC 的 Skills 是**使用者自建的自由文字 + 同事 endorse**，
  官方文件**沒有 proficiency scale、沒有受控詞彙**；且 `"Starting in Spring '22, WDC isn't available to new
  Salesforce customers."`
  → Salesforce 沒有做 skills taxonomy 這件事；**這正是「自由文字 + 背書」路線的下場：功能停售**。
- **ServiceNow**：官方 docs 站在本輪全面 302/301 到新網域且為 JS 渲染，**正文未取得**。
  僅能確認官方存在《Update skill proficiency level》《Define the skill taxonomy》《Skills Intelligence》等文件頁 → 未核實，見文末清單。

### 2.6 大廠模式對照表（只列已核實者）

| 廠商 | 詞彙來源 | 自由生成？ | 推論方式 | 證據／確認 | proficiency |
|---|---|---|---|---|---|
| Microsoft People Skills | 內建 taxonomy（powered by LinkedIn，建議啟用全部 16,000 項）+ 管理員自訂 | ❌ LLM 只能挑 taxonomy 內最接近的 | LLM + Microsoft Graph 活動訊號，忽略 90 天前活動，每 30 天 refresh | confirmed（藍勾）vs inferred（灰） | **無** |
| Workday Skills Cloud | Skills Cloud 內部 ontology（graph） | ❌ 外部技能須經 `Import_External_Skill_Mapping` 正規化 | ML + graph；suggestions/inference | Match_Type / Map_To_Skill 逐筆決策 | 有「skills level」（部落格層級陳述；API 細節未核實） |
| LinkedIn Skills Graph | 39K canonical skills + 374K aliases（26 語） | ❌ NLP 抽取後對映到 taxonomy 內特定 skill | NLP + 人工標註訓練 | —（本輪未查） | —（本輪未查） |
| Salesforce | 無（客戶自建記錄） | ✅ 自由文字 | 無 | 同事 endorsement | 無 |

---

## 3. 關鍵設計問題：受控詞彙 vs 自由文字，對本產品的利弊

### 3.1 官方講的「為什麼要受控詞彙」

ESCO 官方（*What is ESCO*）：
> "ESCO…is the European multilingual classification of Skills, Competences and Occupations."
> 它是 "a dictionary, describing, identifying and classifying professional occupations and skills"，
> 且 "those concepts and the relationships between them **can be understood by electronic systems**"，
> 目的是 "offering a **'common language'** on occupations and skills"。

→ 官方給的受控詞彙理由只有一個：**跨系統、跨組織、跨語言的互通（interoperability）**。
不是「品質」，不是「寫得好不好」。

### 3.2 官方講的「為什麼 task 仍是自由文字」

O\*NET 是同時做兩件事的最好證據：
- **Task Statements 是自由文字、綁死單一職業**：18,796 列，每列一個 `O*NET-SOC Code` + 1000 字元的
  自由文字 task，加上 Core/Supplemental 標記。撰寫靠**風格規則**約束（2026-07-13 spec 第 1a 節的三段式與禁令清單），
  不是靠選項清單。
- **DWA 才是受控層**：2,000+ 條 DWA，跨職業共用，1:1 上掛 IWA、再 1:1 上掛 GWA；
  task 與 DWA 是多對多（一條 task 可掛多條 DWA）。

→ **官方架構本身就是「自由文字的事實層 + 受控詞彙的檢索／互通層」雙層**，而不是二選一。
Task 之所以留自由文字，是因為它要承載**這個職業特有的**行為、受詞、目的、工具；
一旦壓進受控清單就失去那些資訊。DWA 之所以受控，是因為它的用途是**跨職業比對**（O\*NET Online 的
DWA 搜尋就是「用我現在職業的活動找其他職業」）。

### 3.3 對「繁中／單一職務／本機」的利弊

| | 綁受控 taxonomy | 純自由文字 |
|---|---|---|
| **利** | 跨文件可比對、可去重、可做 skill gap；LLM 輸出可被 identity gate 收斂到有限集合，減少同義漂移；可對接外部資料 | 保留職務特殊性與證據原文；沒有授權風險；沒有詞彙表維護成本；繁中不需翻譯 |
| **弊** | **本產品沒有跨文件比對需求**（一次一份、本機、單一操作者）→ 互通性收益趨近 0；四個候選詞彙表**全部沒有繁中**（見 §4）→ 必得自譯，SFIA 明文禁止未授權翻譯散布、ESCO/O\*NET 可譯但你得自己維護翻譯品質；受控清單會把「這位員工真正的知識」壓成最接近的通用詞，**破壞 evidence linkage**（K/S 不再是訪談原話的可追溯結論） | 同義詞漂移（「Excel 樞紐分析」vs「樞紐分析表操作」）；無法自動去重；未來若要做跨文件分析要回頭補 |

**本產品的非對稱**：受控詞彙的**全部官方理由（互通）在單機、單文件、單使用者的情境下不成立**；
而它的成本（無繁中→自譯→授權風險 + 詞彙表維護 + 破壞證據可追溯）**全額發生**。

---

## 4. 繁體中文的現實

| taxonomy | 繁體中文 | 簡體中文 | 官方跨語系做法 |
|---|---|---|---|
| O\*NET | ❌ 無 | ❌ 無 | 無（僅英文） |
| ESCO | ❌ 無 | ❌ 無（28 語系清單無任何中文） | **概念 ID 為主體、各語言只是 label**：`"ESCO is bridging language barriers by providing terms for each concept in all languages covered by the classification."` |
| Lightcast | ❌ 未提供／未提及 | ❌ 未提及 | 官方文件未述 |
| SFIA 9 | ❌ **無正體中文** | ✅ 有簡體中文（`sfia-online.org/zh/`） | 官方翻譯須經 SFIA Foundation 翻譯管理系統；自行翻譯並散布需付費授權 |
| iCAP 職能基準 | ✅ **原生繁中** | — | — |

**業界處理跨語系的官方做法（唯一被核實的兩例，模式相同）**：
1. **ESCO**：一個概念一個 URI，28 語系各有 preferred term / non-preferred terms / hidden terms；
   跨語言比對比的是概念不是字串。
2. **LinkedIn**：39K canonical skills，配 374K aliases，覆蓋 26 語系；
   NLP 把任何語言的自由文字對映到同一個 canonical skill。

→ **業界的答案不是「翻譯詞彙表」，是「canonical concept + 多語 alias」**。
對 Caliburn 的直接啟示：若哪天真要做受控詞彙，**該做的是「繁中 preferred term + alias 清單」的本地概念表**，
而不是把 ESCO/O\*NET 整包翻成繁中。而且這件事**與 K/S 欄位要不要綁外部 taxonomy 是兩回事**。

---

## 5. proficiency／熟練度分級的官方現況

| 體系／產品 | 有沒有 proficiency | 官方內容 |
|---|---|---|
| **ESCO** | **沒有** | skills pillar 的概念 metadata 只有 description / scope note / **reusability level** / 與職業的 essential-optional 關係；**沒有任何 mastery 或 proficiency 欄位**。ESCO 的「級」在 EQF 那側（8 級，三維：knowledge / skills / responsibility and autonomy），掛在**資格**上不掛在單一 skill 上 |
| **SFIA 9** | 有，但**不是技能熟練度，是責任層級** | 7 級 responsibility；`"Each skill is defined at relevant levels of responsibility…Not all skills are defined at all seven levels."` 判級沿 autonomy / influence / complexity / knowledge 四軸（見 2026-07-13 spec §5a） |
| **O\*NET** | 有，但是**職業層級的量表評分**，不是個人熟練度 | Content Model 的 K/S/A 是對職業評 Importance/Level（`Level Scale Anchors`、`Scales Reference` 檔），不是「這個人會到什麼程度」 |
| **台灣 iCAP** | 有 | 職能基準的**職能級別 1–6 級**（平台查詢條件可依 Level 1–6 篩選）；掛在職能基準／職能單元上 |
| **Microsoft People Skills** | **沒有** | 只有 confirmed vs inferred 二分 |
| **Workday** | 有 | 部落格層級陳述 "Skills level to measure a worker's skill proficiency"；API 目錄有「Proficiency Rating Scales」但 `Manage_Skills` request 無 proficiency 欄位（細節未核實） |
| **SAP SuccessFactors** | 官方有《Configuring the Proficiency Level Scale》文件頁 | 正文未核實 |
| **Salesforce** | 沒有 | Chatter Skills 只有 endorsement |

**可直接支持裁決的觀察**：
- **標準機構那一側（ESCO/O\*NET/SFIA/iCAP）沒有人在「單一技能」上掛個人熟練度**。
  級別一律掛在**更大的單位**上：資格（EQF）、責任層級（SFIA）、職業（O\*NET 評分）、職能基準（iCAP 1–6 級）。
- **HR 產品那一側**才有 per-skill proficiency，而且是**組織自訂的評等量表**（Workday、SAP 皆為可設定 scale），
  不是標準。Microsoft 這種以 AI 推論為主的產品乾脆**不做 proficiency**，只做 confirmed/inferred。
- → Caliburn 的 OCS 已經有 `ocs_profile.ocs_level` 與 `CompetencyBlock.competency_level`（掛在職能區塊，
  不掛在單一 K/S 上），**與國際慣例一致**。**不需要**為單一 K/S 加 proficiency 欄位。

---

## 6. 對 Caliburn 的裁決建議

現況（`packages/ocs-contract/schema/ocs-document.schema.json`）：`CompetencyBlock` 的
`knowledge` / `skills` 是 `CodeText`（`code` + `text` + `_pending`），也就是
**「每份文件自帶的本地代碼（K01/S01…）+ 繁中自由文字」**。這正是 iCAP 職能基準本身的做法。

**建議：K/S 不綁外部受控 taxonomy；維持本地代碼 + 繁中自由文字。** 理由（全部有官方依據）：

1. **受控詞彙的官方理由是互通（ESCO 明文），本產品沒有互通對象**——本機、一次一份、不跨組織、不跨語言。
2. **四個候選全部沒有繁體中文**；自譯 ESCO/O\*NET 是可行但要自己扛翻譯品質，
   自譯 SFIA 並散布**明文需付費授權**。
3. **O\*NET 自己就是雙層設計**：事實層（task statements）留自由文字並靠**撰寫規則**管品質；
   受控層（DWA）另建、另有用途。Caliburn 現在缺的是**撰寫規則的執行**（2026-07-13 spec 已備齊教材），
   不是缺一張詞彙表。
4. **綁詞彙表會破壞 evidence linkage**：K/S 一旦被壓成清單裡最接近的通用詞，就不再是訪談原話的可追溯結論，
   與本 repo 的 provenance 方向相反。
5. Salesforce 的反例（自由文字 + endorsement，功能停售）**不適用**於我們：
   它失敗在「沒有任何品質機制」，我們有 verifier + identity gate + 撰寫判準。

**同時建議做（低成本、保留未來縫）**：

- **文件內同義收斂**，不是跨文件受控：對單一 JD 內的 K/S 做 identity gate，避免同一概念出現兩種寫法。
  這是大廠 normalization 的**最小版本**（Workday `Match_Type`／`Map_To_Skill` 的精神），
  但範圍只到一份文件，沒有詞彙表維護成本。
- **保留 `code` 欄不動**：未來若要接概念表，`code` 就是掛 external concept ID 的縫；現在不要填外部 ID。
- **不加 per-skill proficiency**：級別維持掛在 `competency_level` / `ocs_level`，與 ESCO/O\*NET/SFIA/iCAP 一致。
- **借 taxonomy 當「判準與檢核」而非「值域」**：ESCO 的 knowledge 名詞化規則、reusability 四層（可當
  「這條 K/S 是通用還是職務特有」的自查提示）、O\*NET 的 task 撰寫禁令——都當 LLM skill 教材用，
  不當下拉選單用。這條在授權上完全乾淨（ESCO CC-equivalent、O\*NET CC BY 4.0；SFIA 僅內部參考不內建不散布）。
- **如果哪天真要受控**：照 ESCO/LinkedIn 的官方模式做 **繁中 canonical concept + alias**（本地自建），
  而不是翻譯外部 taxonomy。

**授權上唯一要注意的既有風險**：repo 內的 OCS JSON 語料來自 iCAP 職能基準 PDF。
data.gov.tw 的「政府資料開放授權條款-第 1 版」**只覆蓋名稱清單那 5 欄**，
不覆蓋 PDF 全文（iCAP 站標示「版權所有：勞動部勞動力發展署」且下載須填認同調查表）。
本機自用與對外散布是兩件事，散布前須另行確認。

---

## 7. 來源總表

| # | 體系／廠商 | 文件名 | URL | 版本／日期 | 取得狀態 |
|---|---|---|---|---|---|
| 1 | O\*NET | O\*NET Database（下載頁） | https://www.onetcenter.org/database.html | 30.3 | ✅ 開啟 |
| 2 | O\*NET | Database Releases Archive | https://www.onetcenter.org/db_releases.html | 30.3 = 2026-05 | ✅ 開啟 |
| 3 | O\*NET | O\*NET Database Licence | https://www.onetcenter.org/license_db.html | CC BY 4.0 | ✅ 開啟 |
| 4 | O\*NET | Data Dictionary 30.3 — Task Statements | https://www.onetcenter.org/dictionary/30.3/excel/task_statements.html | 30.3，18,796 列 | ✅ 開啟 |
| 5 | O\*NET | Data Dictionary 30.3 — Tasks to DWAs | https://www.onetcenter.org/dictionary/30.3/excel/tasks_to_dwas.html | 30.3，23,850 列 | ✅ 開啟 |
| 6 | O\*NET | Data Dictionary 30.3 — GWAs to IWAs to DWAs | https://www.onetcenter.org/dictionary/30.3/excel/gwas_to_iwas_to_dwas.html | 30.3，2,087 列 | ✅ 開啟 |
| 7 | O\*NET | O\*NET Online Help — Detailed Work Activities | https://www.onetonline.org/help/online/dwa | 現行 | ✅ 開啟 |
| 8 | O\*NET | Content Model 4.A Work Activities | https://www.onetonline.org/find/descriptor/browse/4.A | 現行 | ✅ 開啟 |
| 9 | O\*NET | Work Activities Project Technical Report（DWA 2014） | https://www.onetcenter.org/reports/DWA_2014.html | 2014-02 | ⚠️ 只取到摘要頁；PDF 正文未解析 |
| 10 | ESCO | What is ESCO | https://esco.ec.europa.eu/en/about-esco/what-esco | 3,039 職業／13,939 skills | ✅ 開啟 |
| 11 | ESCO | ESCO versions（escopedia） | https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/esco-versions | v0–v1.2.1 | ✅ 開啟 |
| 12 | ESCO | ESCO v1.2.1 is live!（新聞） | https://esco.ec.europa.eu/en/news/esco-v121-live | 2025-12-22 | ✅ 開啟 |
| 13 | ESCO | ESCO v1.2（escopedia） | https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/esco-v12 | 2024-05 | ✅ 開啟 |
| 14 | ESCO | Skills pillar（escopedia） | https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/skills-pillar | 現行 | ✅ 開啟 |
| 15 | ESCO | Skill reusability level（escopedia） | https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/skill-reusability-level | 現行 | ✅ 開啟 |
| 16 | ESCO | ESCO languages（escopedia） | https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/esco-languages | 28 語系 | ✅ 開啟 |
| 17 | ESCO | FAQ（授權、語言、概念數） | https://esco.ec.europa.eu/en/about-esco/faq | 現行 | ✅ 開啟 |
| 18 | ESCO | Download ESCO | https://esco.ec.europa.eu/en/use-esco/download | v1.0.3–v1.2.1 | ✅ 開啟 |
| 19 | ESCO | Use ESCO services (API) | https://esco.ec.europa.eu/en/use-esco/use-esco-services-api | EUPL 1.2 | ✅ 開啟 |
| 20 | ESCO | ESCO API（escopedia） | https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/esco-api | 現行 | ✅ 開啟 |
| 21 | ESCO | Skills & competences 分類瀏覽 | https://esco.ec.europa.eu/en/classification/skill_main | v1.2.1 | ✅ 開啟 |
| 22 | Lightcast | Lightcast Skills Taxonomy（open-skills 產品頁） | https://lightcast.io/open-skills | 34,000+ skills | ✅ 開啟 |
| 23 | Lightcast | Open Skills FAQs | https://lightcast.io/open-skills/faqs | 月更 | ✅ 開啟 |
| 24 | Lightcast | Knowledge Base — Lightcast Skills Taxonomy | https://kb.lightcast.io/en/articles/7216059-lightcast-skills-taxonomy | 4 週更新 | ✅ 開啟 |
| 25 | SFIA | SFIA 9 Home | https://sfia-online.org/en/sfia-9 | 2024-10 發布 | ✅ 開啟 |
| 26 | SFIA | Using and licensing SFIA | https://sfia-online.org/en/about-sfia/licensing-sfia/using-and-licensing-sfia | 現行 | ✅ 開啟 |
| 27 | SFIA | SFIA 9 documents（語系清單） | https://sfia-online.org/en/sfia-9/documentation | SFIA 9 | ✅ 開啟 |
| 28 | SFIA | How SFIA works | https://sfia-online.org/en/about-sfia/how-sfia-works | SFIA 9 | ✅ 開啟 |
| 29 | SFIA | SFIA 9 中文（簡體）首頁 | https://sfia-online.org/zh/sfia-9 | SFIA 9 | ✅ 開啟（確認為簡體） |
| 30 | iCAP | iCAP 職能發展應用平台首頁 | https://icap.wda.gov.tw/ap/index.php | 現行 | ✅ 開啟 |
| 31 | iCAP | 職能基準查詢結果列表 | https://icap.wda.gov.tw/ap/resources_datum_list.php | 2,986 項（2026-08-01） | ✅ 開啟 |
| 32 | iCAP | 資料下載 | https://icap.wda.gov.tw/ap/knowledge_downLoad.php | 現行 | ✅ 開啟 |
| 33 | 政府資料開放平臺 | 職能基準資料檔（dataset 21198） | https://data.gov.tw/dataset/21198 | 政府資料開放授權條款-第 1 版，年更 | ✅ 開啟 |
| 34 | 政府資料開放平臺 | dataset 21198 metadata API | https://data.gov.tw/api/v2/rest/dataset/21198 | 1130115／1140107／1150102 三版 | ✅ 開啟 |
| 35 | 勞動部 | 職能基準資料檔 CSV（1150102 版，870 筆） | https://apiservice.mol.gov.tw/OdService/download/A17020000J-000019-JbU | 1150102 | ✅ 實際下載並讀表頭 |
| 36 | Microsoft | Overview of People Skills | https://learn.microsoft.com/en-us/microsoft-365/copilot/people-skills-overview | ms.date 2025-10-21，updated 2026-05-06 | ✅ 開啟（全文） |
| 37 | Microsoft | Manage your skills library in People Skills | https://learn.microsoft.com/en-us/microsoft-365/copilot/people-skills-manage-skills-library | updated 2026-07-09 | ✅ 開啟（全文） |
| 38 | Microsoft | People Skills AI Inference engine | https://learn.microsoft.com/en-us/microsoft-365/copilot/people-skills-ai-inferencing | updated 2026-05-06 | ✅ 開啟（全文） |
| 39 | Microsoft | Skills landscape report（Viva Insights） | https://learn.microsoft.com/en-us/viva/insights/advanced/analyst/templates/skills-landscape | 現行 | ⚠️ 僅經官方搜尋摘要，未逐字開啟 |
| 40 | Workday | Talent Service Details（production API v46.2） | https://community.workday.com/sites/default/files/file-hosting/productionapi/Talent/v46.2/Talent.html | v46.2 | ✅ 開啟 |
| 41 | Workday | Import_External_Skill_Mapping Operation Details | https://community.workday.com/sites/default/files/file-hosting/productionapi/Talent/v40.2/Import_External_Skill_Mapping.html | v40.2 | ✅ 開啟 |
| 42 | Workday | Manage_Skills Operation Details | https://community.workday.com/sites/default/files/file-hosting/productionapi/Talent/v46.2/Manage_Skills.html | v46.2 | ✅ 開啟 |
| 43 | Workday | How Workday Is Delivering Next-Generation Skills Technology at Scale（官方部落格） | https://blog.workday.com/en-us/2022/how-workday-delivering-next-generation-skills-technology-scale.html | 2022 | ✅ 開啟（層級：廠商官方部落格） |
| 44 | LinkedIn | Building LinkedIn's Skills Graph to Power a Skills-First World（LinkedIn Engineering） | https://www.linkedin.com/blog/engineering/skills-graph/building-linkedin-s-skills-graph-to-power-a-skills-first-world | 2022 | ✅ 開啟 |
| 45 | Salesforce | Skills Overview（Salesforce Help） | https://help.salesforce.com/s/articleView?id=sf.collab_skills.htm | 現行 | ✅ 開啟 |
| 46 | Salesforce | Skill DMO（Data 360 DMO Guide） | https://developer.salesforce.com/docs/data/data-cloud-dmo-mapping/guide/c360dm-skill-dmo.html | 現行 | ✅ 開啟 |

---

## 8. 查不到／需二次確認（誠實清單）

1. **SAP SuccessFactors Talent Intelligence Hub 全部細節** —— help.sap.com 為 JS 渲染，
   本輪四種 URL 形式（`/docs/successfactors-platform/...`、`/docs/SAP_SUCCESSFACTORS_*/…​.html`、
   `/viewer/…`、加 `?locale=en-US`）**皆只回站台標題**。
   已知官方存在的文件標題：《Configuring the Proficiency Level Scale》《Skill Inferencing in Talent
   Intelligence Hub》《Adding Attributes to the Growth Portfolio》《Overview of the Redesigned Growth Portfolio》。
   **未核實**：proficiency 有幾級／名稱／預設值；Attribute Library 是否為 SAP 交付內容或客戶自建；
   skill inferencing 的輸入訊號與是否對映到 Attribute Library。
2. **ServiceNow Skills Intelligence / Talent Development** —— docs.servicenow.com 全面 301/302 到
   www.servicenow.com/docs 且為 JS 渲染，正文未取得。已知存在《Update skill proficiency level》
   《Define the skill taxonomy》等頁；**proficiency 級別名稱與 skill ontology 細節未核實**。
3. **Lightcast Open Skills 的正式授權條款全文** —— 條款在 legal.lightcast.io，本輪未開啟。
   已核實的只有產品頁與 FAQ 的敘述（非營利註冊後免費、商用依申請的 licence 類型而定）。
   **若未來考慮採用，必須先讀完整 Terms of Use。**
4. **O\*NET Work Activities Project 技術報告（DWA_2014.pdf）正文** —— PDF 已下載但本環境無 pdftoppm，
   無法逐頁讀取；GWA/IWA/DWA 的**逐字官方定義**與**建構方法論**未取得。
   本檔的階層陳述來自資料字典檔頁與 O\*NET Online 說明頁（已核實），
   但「DWA 為何存在／與 task 的設計分工」的官方原句未取得。
5. **GWA 的確切條數** —— 只核實 Content Model 4.A 為四大類；41 條 GWA 的說法**未核實**。
6. **ESCO Handbook 正文** —— PDF 為二進位，未解析。ESCO 的互通性論述本檔改引 escopedia／官方頁
   （已核實），但 handbook 中關於 skill 用語規則的逐字段落未取得。
7. **ESCO v1.2.1 的日期不一致** —— 官方新聞頁寫 "22 December 2025"，分類瀏覽頁顯示
   "last updated on December 10, 2025"。以新聞頁為準，差異原因未確認。
8. **SFIA 官方翻譯政策細節頁** —— `sfia-online.org/en/about-sfia/translations` 只回傳一個
   `@translations` endpoint，未取得正文。「翻譯須經 SFIA 翻譯管理系統」一句來自官方站內搜尋摘要，
   **需二次確認**。授權頁關於「translating…and distributing」需付費授權那條**已逐字核實**。
9. **iCAP 職能基準 PDF 全文的權利狀態／可否再散布** —— 平台頁尾僅「版權所有：勞動部勞動力發展署」，
   下載須填「下載認同調查表」，**沒有找到明確的再利用授權條款頁**。
   data.gov.tw 的「政府資料開放授權條款-第 1 版」經實測只覆蓋 5 欄清單資料。
   **repo 內 OCS 語料若要對外散布，須向勞動力發展署確認。**
10. **Lightcast / Microsoft People Skills 的語系支援** —— 兩者官方文件皆未說明多語（含中文）支援程度。
11. **Workday Proficiency Rating Scales 的資料模型** —— Talent 服務目錄提到此名詞，
    但本輪未開啟該 operation 的細節頁；`Manage_Skills` 確認無 proficiency 欄位。
12. **LinkedIn Skills Graph 的授權** —— 未查。LinkedIn taxonomy 透過 Microsoft People Skills
    以產品形式提供（"powered by LinkedIn"），**是否可獨立取得／授權條件不明**。
