# 實際雇主職位文件與 Caliburn 樣稿比較

公開的公司職位文件可以提供具體寫作參考，但「雇主真的發布過」不等於「完整反映某位員工目前的全部工作」。本比較區分機構職位描述、公司職族文件，以及含職責的招聘頁，再對照客製化 JD 的用途；不以文件名稱或公司知名度代替內容判斷。

## 1. 範圍、基準與結論

研究基準日：2026-09-09；議題 **JD-R001/C06**。先前示例深度獲 Owner「應該可以」的可修訂同意；本輪跨國比較為 **G2 補證完成／建議供審閱**，不是新增欄位、prompt 或施工核准。

**後續狀態：**Owner 在比較後對完整閱讀版r2「大致上同意」；[樣稿版本及核心文檔複核](2026-09-09-jd-sample-basis-and-review.md#10-完整閱讀版-r2-與核心文檔一致性審核)為最新交接紀錄。本文保留補查當時的證據與措辭；下文「本次未改樣稿」指該次比較，不否定後來同步閱讀版。r2未改15筆情境、工作範圍或任務數，§5比較仍適用，不宣稱所有外部結論逐項獲Owner核准。

比較基準為[完整前端工程師樣稿](2026-09-09-frontend-engineer-jd-sample.md)及其[15筆明示虛構情境](2026-09-09-jd-sample-basis-and-review.md#2-完整情境材料)。它描述受雇於網站服務公司的前端工程師，不是所有軟體工程師，也不是自營接案者。方法原則仍由[欄位指南](2026-09-09-jd-field-and-writing-guide.md)及[客製化校準](2026-09-09-customized-jd-depth-and-interview-calibration.md)負責；本文件只存實例、比較及新增發現。

**研究判斷：目前內容骨架不需要因本批例子推翻。更值得校準的是內容辨識度，而非增加固定欄位。** 應保留真正的服務／產品範圍、本人責任層次、交付及求援界線、發生條件和必要專業。實例沒有證明「Duty／Task／OPKS」是統一格式，也沒有證明某種頁數能保證完整。

共選十份官方雇主文件／頁面，涵蓋八國的機構或職位所在地：美國、英國、澳洲、紐西蘭、加拿大、日本、丹麥及荷蘭。GitLab 為美國公司、全球職族，不冒稱美國單一職位。這是目的性比較，不是隨機抽樣、各國代表性調查或全部產業驗收；技術類較多，另用人資行政與道路工程檢查差異。

## 2. 先辨識文件是哪一種

| 文件性質 | 本批實例 | 能學什麼／不能證明什麼 |
|---|---|---|
| 機構自己的完整職位文件 | HDR UK、West Arnhem、NZTA、CFEC；Central Saanich 在招聘頁內另列完整 JD；CSAC 為空缺職位的 Proposed Duty Statement | 可看特定單位如何寫職責、分工與條件；仍不能證明現任者已核實全部內容，亦可能是招募預期職位 |
| 公司職族／多職級文件 | GitLab Frontend Engineer Roles | 可看共通責任與職級／團隊差異；不能把所有級別、所有團隊工作加到同一員工 |
| 招聘頁中的職位描述 | LEGO、JASM／TSMC、Adyen | 可學具體工作對象、交付範圍及條件；福利、候選人門檻、招聘宣傳與工作本身須分開，不能冒稱完整內部 JD |

「私版」在本研究指機構特定職位，而不是機密文件，也不限私人企業。所有來源均為公開可取得資料；未存取內部員工資料。公部門的特定職位文件與 iCAP 等職業層級標準也不是同一種東西。

## 3. 十份原始文件：具體內容及限制

以下均為精簡意譯。「未載」只表示本次公開頁未說，不表示雇主沒有管理該事項。日期只採文件／頁面明示值；沒有以搜尋引擎的爬取日推定發布日。原文連結與精確位置見§7。

### 3.1 英國 HDR UK：Junior Frontend Software Engineer

六頁 **Job description and person specification**；PDF 未署日期，所附招聘頁日期為2026-03-09。內容包含產品目的、職責、協作與必要／加分條件。不是只寫開發網站：點名健康資料服務，並將功能拆解、程式審查、文件及問題升級連在一起；需要時向 Technical Programme Director 升級。[^1]

**可學／限制：**產品對象與求援接口有辨識力；但「需要時」沒有具體門檻。兩年經驗可含個人／學術專案，學位列加分，不能抄成一律兩年正式年資或必備學位。六頁還含大量組織介紹與招聘資訊，不能用總頁數判斷職責更完整。

### 3.2 美國 GitLab：Frontend Engineer Roles

公司公開職族，分共通責任、職級及團隊專長；頁尾最後修改2026-03-12，修改說明涉及職等用語及薪酬頁，不代表所有責任當日重寫。它具體寫依嚴重度／優先序處理缺陷、以程式審查維持標準，也另外列職族績效指標。[^2]

**可學／限制：**共通工作與特定責任可以分開閱讀；不能把 Staff 的輪值或全部團隊領域套給所有前端人員。本頁確實包含績效指標，故不能說「大廠都不放 KPI」；Caliburn 分離下游目標是自己的用途選擇，不能冒充全球共識。

### 3.3 美國 CSAC：Web Developer & Graphic Designer

四頁 **Position Duty Statement**，2025-06-10；首頁勾 Proposed、任職者 Vacant，另載2025-06-04修訂。除網站開發外，明列平面／影音素材、無障礙及行政訊息發布；正式分類名稱與實際工作稱呼不同。這是機構職位配置，不是已在職員工的完成紀錄。[^3]

**可學／限制：**同一職位可能兼具不同工作，不應因前端職稱就刪掉設計或發布職責。文件同時使用協助、獨立分析等不同層次，仍須按事項讀；不照搬時間比例、職位分類表、通用態度條目或簽核流程。

### 3.4 美國 CFEC：Information Technology Technician

兩頁 **Job Description**，頁尾修訂2025年1月。除系統支援外，寫出減少作業中斷、診斷問題、相關行政／網路工作，以及在合作社服務區域內移動、尖峰或緊急時段的工作條件。[^4]

**可學／限制：**即使是 IT 職位，也不能預設純辦公室工作。部分責任用「可能」描述而沒有明確觸發條件；本產品遇到類似敘述應釐清，不直接寫成固定責任。身體要求、雇用查核及法律措辭屬該職位／制度，不能通用複製。

### 3.5 澳洲 West Arnhem：Human Resources Administration Assistant

兩頁 **Position Description**，核准日期2026-03-30。列出試用期提醒、資格更新、人事資料、聘用文件與報表；薪資工作包含協助處理，另明示受訓以便在人員缺席時代理。匯報 HR Coordinator、沒有下屬，並交代必要差旅。[^5]

**可學／限制：**例行、協助與缺員代理不是同一種責任；不能把準備聘用文件寫成有核准權，也不能把全部薪資工作改成只在缺員時才做。當地證照、查核、職等及「其他交辦」條件不自動成為本產品要求。

### 3.6 紐西蘭 NZTA：Principal Engineer Surfacing

五頁 **Position description**，署2025年7月。對瀝青／鋪面標準是主導，對道路標線標準是協助；另有專項研究及按需技術審查。正文列技術關係及預算範圍為 None，專業對應紐西蘭運輸系統。[^6]

**可學／限制：**動詞與對象一起界定責任，同一職位不必對所有事項都是「主導」。不能由 Principal 推定有人事、預算或最後簽核權；公開文件也未把每項審查頻率／核准權寫全。組織價值及發展制度不是本產品必填欄。

### 3.7 加拿大 Central Saanich：Network & Client Support Technician

官方招聘頁另列 **Job Description**；職缺編號2025-06、截止日2025-02-10，JD 修訂日未載。工作明確支援市政及警察單位，涉及實際業務軟體、設備／網路維護、使用者指導及文件；另列安全查核、待命輪值與必要的現場操作。[^7]

**可學／限制：**「維護系統」需要知道維護誰的哪些系統。服務警察的24小時運作，不等於個人全天工作；個人輪值須另外看條件。頁首一般工作時段與末段可變時段應合讀，不能只截一行；不採其薪資、資格或體力數值為通則。

### 3.8 日本 JASM／TSMC：IT_iCC Engineer

熊本職位招聘頁，署2026-09-02。責任指向警報／事件、基礎設施操作，以及與供應商和台灣總部工程師協作；工作條件另載日夜班及輪班安排。[^8]

**可學／限制：**跨地協作、語言與輪班可能真的界定工作。但工作清單未明列事件完成／升級標準，不能因為是大公司頁面就判完整。招聘流程、福利及公司可調動範圍，不等於現任員工已承擔所有可能工作。

### 3.9 丹麥 LEGO：Associate Software Engineer – API Gateway Platform

Billund 招聘頁，署2026-08-26。不是泛稱開發軟體，而是 API gateway、自助工具及平台功能，含事故處理和輪值；另指出製造環境需求及實際技術範圍。[^9]

**可學／限制：**相同工程職稱在不同平台有不同工作對象及營運責任；不能由 Associate 猜測沒有輪值。公開頁未說輪值頻率、事故升級門檻或量化品質尺度；這些是否需要寫，仍依真正職位確認，不是照抄工具清單就完成客製化。

### 3.10 荷蘭 Adyen：Software Engineer (Java) – Unified Platform

Amsterdam 招聘頁，發布／修訂日未載；同時招募多團隊及兩種職級，明說面試再確認團隊。工作涵蓋需求至上線及 API／工具品質，但列出的五大平台領域不是每位錄用者全部負責。[^10]

**可學／限制：**交付終點值得說清；整個平台願景與個人範圍不能混為一談。本例主要作反例：公開頁再詳細，也可能尚未決定個人分工；不能靠它補出 Caliburn 員工未說過的工作或硬性年資。

## 4. 橫向比較：共同可學與不可硬湊的差異

| 比較面向 | 原文呈現的差異 | 對 Caliburn 的研究判斷 |
|---|---|---|
| 文件骨架 | 有的分目的／責任／專業，有的另分協作、條件、職級或招聘資訊 | 反覆出現的內容目的可學；不能稱所有雇主共有相同欄位，更不能直接推出資料結構 |
| 責任粒度 | HDR UK按軟體開發／技術問題分組；CSAC包含混合職務；NZTA以專業責任列項 | 依實際工作區分，不套固定Duty數／Task數；分類名稱不是員工範圍的上限 |
| 工作對象 | HDR UK具體到服務，LEGO具體到平台，Central Saanich具體到業務系統 | **不把每個案例列成永久任務，不等於不能寫產品／系統名稱**。固定承擔的系統與一次性案件須分辨 |
| 責任程度 | NZTA分主導／協助／審查；West Arnhem分協助／代理；HDR UK指出升級對象 | 不只用「負責」一個詞。實際權限未確認就問，不能由職稱補猜 |
| 成果與品質 | 有些融在責任句，有些集中列；GitLab還連結績效指標 | 保留必要完成要求，不要求每條都另產O/P，也不能說所有公司排除績效資料 |
| 專業內容 | 有的合稱KSA，有的分experience／qualifications；必要與偏好常分開 | 名稱不同不表示缺少能力概念；但經驗、知識、技能、資格不是可無條件互換 |
| 工作條件 | 技術職可含輪值、現場移動、體力；行政職也可能有偏遠差旅 | 不因office／IT／行政標籤略過條件，也不能把別家條件帶進本職位 |
| 完整性 | 部分有模糊「需要時」「可能」「及時」或廣泛品質形容 | 外部文件只能提供查漏問題，不是已驗證真實或滿分的答案 |

這些是十份具體樣本的比較結論，不是「大家都這樣做，因此一定效果最好」的因果證明。組織、用途及責任範圍不同，本來就可能有不同合理呈現。

## 5. 與我們的樣稿逐項對照

| 樣稿面向 | 目前已做到 | 實例帶來的校準／是否改稿 |
|---|---|---|
| 組織定位與目的 | 已分直屬主管、專案經理及協作對象，交代客戶專案性質 | 基本方向相容；不能抄HDR UK產品或Adyen平台作員工事實 |
| 需求至維護的完整範圍 | 八項任務涵蓋已宣告範圍，非只寫開發 | 外部工程職另有審查、帶教、平台營運等；本例沒提供就不能判漏，也不能偷偷追加。真實訪談時可用作追問方向 |
| 前後端、客戶、商務權限 | 已寫本人技術責任及不自行承諾／核准事項 | 保留此深度；可把同一位置附近的重述精簡，但不能抹掉各自適用條件 |
| 事件／周期／有條件工作 | 已分上線問題與有月檢約定才執行的檢查 | 與實例的條件式責任可比較；將來真有代理工作再寫，不能為表格完整硬補 |
| 必要的異常判斷 | 已分查詢逾時與訂單結果不明，避免不同情境混用 | 不為模仿簡短招聘頁刪掉。它們目前用來界定異常處理責任，不是逐案工作日誌；無需把所有操作步驟放進來 |
| 交付品質 | 已有檢查、版本、已知限制與交接內容 | 不能自造測試覆蓋率、效能門檻或時限。若訪談確認具體標準，應補到適用內容，而非只留「高品質」 |
| K／S的具體性 | 已交代專業與用途，但未定技術棧 | 可比實例更具體之處是辨識實際技術／業務範圍；只有取得事實才補，React、GitHub等不是看別家公司就填入 |
| 特殊條件與資格 | 已明示本例無固定輪班／例行出差，必要資格資訊未提供 | 不把未知改成不需要；CFEC／Central Saanich等提醒我們要問，但不代表本前端職位也有相同要求 |
| 閱讀篇幅 | 任務句＋必要產出／完成要求，末段總覽 | 本樣稿部分界線比招聘頁寫得細，並不證明品質更高；可以短總覽＋必要細節，不以他家頁數作上限 |

**建議維持現有樣稿及六個閱讀區塊，先不新增固定欄位。** 本次沒有新增真實工作資訊，因此未修改樣稿或虛構情境。真正需要加強的，是日後取得資訊後把「主要操作、必要說明、相關技術」填成適用於該員工的內容，而不是把所有人的 JD 都寫得像同一份前端模板。

## 6. 推薦與下一步

採用**簡明概述＋能辨識實際責任的必要細節**，維持已同意方向。三種選擇中，照抄職族／招聘頁容易混入未承擔工作；把所有案例逐項塞入JD會失去持續責任；按實際範圍客製較符合本產品目的。這是用途導向的研究推薦，不是宣稱唯一國際標準。

本輪沒有發現必須重開 Memory、新增A／級別、iCAP格式、強制KPI或固定關係表的證據。外部文件含這些內容，不代表我們漏做；反過來，外部文件沒寫完成條件，也不構成刪除既有必要細節的理由。

下一步只需審閱上述比較是否揭露仍未表達的內容需求；若沒有，沿既定 **JD-R002/C02** 續談員工與AI如何編輯／審核，不重做同類跨國原則研究。只有真實樣稿無法表達必要工作、新用途或新證據推翻既有判斷，才重開內容選擇。沒有修改prompt、Memory、模型設定、程式、DB或UI，也沒有產品測試。

## 7. 來源、日期及查核位置

下列來源均於2026-09-09核讀；PDF頁碼按檔案第一頁起算。PDF正文有分頁文字可核對；頁面影像取得部分失敗，未完成逐頁視覺驗讀，故**本研究比較內容，不宣稱比較過全部實際版面美觀**。CFEC本地下載亦被網路連線限制阻擋；不以未取得的檔案作視覺證據。未重讀已排除的2026-08-12產品流程長稿。

[^1]: Health Data Research UK，[*Junior Frontend Software Engineer — Job description and person specification*](https://www.hdruk.ac.uk/wp-content/uploads/2026/03/Junior-Frontend-Software-Engineer-Job-description.pdf)，6頁；PDF無日期，全文核讀，重點pp.1、3–5。對照[官方招聘頁](https://www.hdruk.ac.uk/jobs/junior-frontend-software-engineer/)所署2026-03-09及其PDF下載，不把網址月份當修訂日。
[^2]: GitLab，[*Frontend Engineer Roles*](https://handbook.gitlab.com/job-description-library/engineering/development/frontend/)，Requirements／Responsibilities／Performance Indicators／Job Levels／Team Specialties及頁尾；最後修改2026-03-12，不明首次發布日。這是全球職族頁，並非個別任職者JD。
[^3]: California Student Aid Commission，[*Web Developer & Graphic Designer — Position Duty Statement*](https://calcareers.ca.gov/CalHrPublic/FileDownload.aspx?aid=28118190&name=701-1400-002DutyStatementFinal.pdf)，4頁；首頁日期2025-06-10、修訂欄2025-06-04，Proposed／Vacant；全文核讀，重點pp.1–3。頁尾表單版次01.25不是本職位修訂日期，p.4有人資批准日期，不因此把首頁Proposed改稱Current。
[^4]: Caney Fork Electric Cooperative，[*Information Technology Technician — Job Description*](https://caneyforkec.com/wp-content/uploads/2025/01/Information-Technology-Technician.pdf)，2頁，頁尾Revised January 2025；全文，尤其p.1職責與p.2條件。文件寫CFEC Use Only但由官方公開提供且附申請連結；不據此宣稱已取得私密員工檔案。
[^5]: West Arnhem Regional Council，[*Human Resources Administration Assistant — Position Description*](https://westarnhem.nt.gov.au/sites/default/files/2026-04/Human%20Resources%20Administration%20Assistant%20-%20Position%20Description%20-%202026.03.pdf)，2頁，Approval Date 2026-03-30；全文，p.1職責3、8及p.2關係／條件。核准日不同於發布日；未由網址2026-04推定另一個版本。
[^6]: NZ Transport Agency Waka Kotahi，[*Principal Engineer Surfacing — Position description*](https://nzta.govt.nz/assets/careers/position-descriptions/Transport-Services/2025/Principal-Engineer-Surfacing-PD-final.pdf)，5頁，July 2025；全文，重點p.2工作／關係／Dimensions、p.3專業。未確認原招聘公告日期，不稱2026新修訂。
[^7]: District of Central Saanich，[*Network and Client Support Technician*](https://www.centralsaanich.ca/node/3371)，招聘頁及內嵌Job Description全文；General Accountability／Nature and Scope／Knowledge, Skills and Abilities／Requirements／Other。Competition 2025-06，截止2025-02-10，未載JD修訂日；不宣稱職缺目前仍在招募。
[^8]: JASM，TSMC官方招聘站，[*IT_iCC (Infrastructure Command Center) Engineer*](https://ro.careers.tsmc.com/job/Kumamoto-IT_iCC%28Infrastructure-Command-Center%29-Engineer-43/1363882266/)，Japan／Kumamoto，Date 2026-09-02；Job Responsibilities／Minimum Qualifications／Working Conditions。是日本職位，不因母公司而算台灣職位。
[^9]: LEGO Group，[*Associate Software Engineer – API Gateway Platform*](https://www.lego.com/en-us/careers/job/associate-software-engineer-api-gateway-platform-9c90647b5c311001725ffe27d90b0000)，Billund／Denmark，2026-08-26，職缺0000036197；Team／Core Responsibilities／能力／Additional details及工作條件。網址en-us是網站語系，不是職位在美國。
[^10]: Adyen，[*Software Engineer (Java) – Unified Platform*](https://careers.adyen.com/vacancies/7342887-software-engineer-java-unified-platform)，Amsterdam；未載發布／修訂日，核讀Unified Platform／What you’ll do／Who you are／Minimum qualifications。只作目前公開文本實例，不宣稱2026新方法或最新內部版本。

## 8. 研究審核與記錄責任

兩路唯讀研究分別查英澳紐機構文件及美歐公司頁；主研究另查美加日實例，並回到十份原始內容逐一核對。來源中「Proposed、職族、多團隊、必要／加分、文件日期／頁面日期」均保留，未將研究者推論冒充雇主自述。共同出現的內容與不同用途未混成同一官方規範。

有效狀態寫回[decision register](../current-decisions.md)，父入口只放路由；實際文件證據及比較由本文單一維護，既有[國際方法證據](2026-09-09-job-analysis-international-evidence.md)不再複製十份內容。原樣稿、情境與既有產品保持不變。

獨立唯讀整合審查未發現影響結論的待修問題；範圍為文件分類、十份／八國計數、案例與長期產品範圍的區別、決策狀態及跨文件一致性，並非第二次重驗全部外部原文。另完成六份本輪文檔的編碼、引用及本地連結檢查；產品目錄沒有本輪改動。這些檢查不等於樣稿已由真實員工核實，也不是模型生成效果測試。
