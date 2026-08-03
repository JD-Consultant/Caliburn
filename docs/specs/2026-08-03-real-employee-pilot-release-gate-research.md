# 真實員工試用作為第一版 release gate：研究紀錄

日期：2026-08-03
狀態：支援已確認的產品決策——Caliburn 第一版 Web release candidate 在正式稱為「可供員工使用的成品」前，必須通過
小規模真實員工試用。文內員工電腦／本機 Web 的 deployment 字句已由 ADR 0044 取代；pilot 方法與 gate 不變。

## 結論

這個 gate 應驗證的是**完整的人機工作系統**，不是再做一次模型 benchmark：真實員工使用待發布版本，依自己的實際工作完成訪談、確認／修正 AI 提案、保存與重新開啟，最後得到能忠實代表其工作的「員工確認、可交主管／HR 審閱的 JD 草稿」。是否通過，須同時看可觀察的任務結果、互動失敗、內容效度、安全與 provenance，並留下可追溯的 go／rework 決策紀錄。

合成案例、golden、deterministic checks 與 LLM grader 仍是發布前必要工程安全網，但不能取代真人試用。它們能重複檢查已知規則，卻無法單獨證明員工是否理解問題、是否能指出 AI 對其工作理解錯誤、T–T–O–P／KSA 是否符合真實職場，以及瀏覽器端到端操作是否讓人誤以為已成功。

## 第一方來源明說了什麼

| 來源 | 來源明說 | 對本研究的限制 |
|---|---|---|
| [iCAP《職能基準發展指引》頁 50–54](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download) | 驗證方法與對象樣本須依標的性質選擇；驗證應證明職能內涵確為實務所需，並依結果修正。實務工作者可重新評估項目的重要度與正確性，現職人員與管理者可參與驗證；修正後仍須專家審閱。工作任務應反映實際現況，KSA 應完整且符合實務，行為指標應具體且能作為成果評量依據。 | iCAP 驗證的是職能基準，不是軟體 usability；因此只能支持「內容須由實務工作者／專家驗證」，不能取代產品互動測試。 |
| [OPM Assessment Decision Guide，頁 5–6](https://piv.opm.gov/policy-data-oversight/assessment-and-selection/reference-materials/assessmentdecisionguide.pdf) | Job analysis 應建立 task 與 competency 的明確連結；SME 是對職務具有直接、最新經驗且熟悉其任務的人，可為現職者或主管；分析過程及 task–competency linkage 的文件化很重要。 | 主管可作內容 SME，但不等於實際使用 Caliburn 的目標員工。 |
| [O*NET Data Collection Overview](https://www.onetcenter.org/dataCollection.html) 與 [Emerging Tasks revised approach](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf) | O*NET 採多方法、多來源；由 job incumbents 與 occupational experts 評定 task 的 relevance、importance、frequency，並提供遺漏 task，再由分析者整併與判斷。 | O*NET 支持 incumbent／expert evidence 與多來源驗證；它不提供 Caliburn release gate 的通用樣本數或通過門檻。 |
| [GOV.UK moderated usability testing](https://www.gov.uk/service-manual/user-research/using-moderated-usability-testing)、[participant recruitment](https://www.gov.uk/service-manual/user-research/find-user-research-participants) | Usability test 是觀察 actual or likely users 完成具體、可信且不暗示答案的任務；應讓參與者知道受測的是服務，不是本人。能安全處理時，以本人的資料／文件測試通常能發現更多情境問題；參與者須涵蓋不同使用需求。 | 「小規模」的人數與分層取決於研究問題和方法；官方例示不是 Caliburn 可以直接照抄的 release threshold。 |
| [GOV.UK usability benchmarking](https://www.gov.uk/service-manual/measuring-success/usability-benchmarking-a-website-or-whole-service)、[user research introduction](https://www.gov.uk/service-manual/user-research/how-user-research-improves-service-design)、[analysis guidance](https://www.gov.uk/service-manual/user-research/analyse-a-research-session) | 應觀察任務是否完成、耗時、放棄，以及「自認完成但其實未完成」；研究應聚焦正確 outcome，而不只是詢問喜好。原始觀察要記錄實際所見所聞，再與研究者解讀分開。 | 滿意度可作輔助訊號，不是正確性、內容效度或可用性的代理變數。 |
| [GOV.UK informed consent](https://www.gov.uk/service-manual/user-research/getting-users-consent-for-research) 與 [research data/privacy](https://www.gov.uk/service-manual/user-research/managing-user-research-data-participant-privacy) | 應事前告知蒐集、錄製與使用方式，保存同意證據，允許退出；只蒐集必要資料、安全保存、限制存取、設定保存期限並可定位刪除個別參與者資料。 | 具體法遵與保存年限仍須按 Caliburn 實際試用安排與適用法規決定。 |
| [NIST AI RMF Core — Measure](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) | TEVV 應有客觀、可重複或可擴充且已文件化的方法；人類參與評估須代表相關人口，條件須近似部署場景，並納入 domain experts、users 與回饋機制。結果應形成可追溯的風險決策。 | NIST 給治理 outcome，不替特定產品設定數字門檻。 |
| [NIST GenAI Profile](https://doi.org/10.6028/NIST.AI.600-1) | 不應從狹窄、非系統或軼事式評估外推能力；應驗證輸出來源／引用、TEVV 資料 provenance、部署前測試結果與 human override；代表性人類回饋、同意／退出與 privacy 也要被記錄。其附錄並指出直接使用者回饋能提供自動錯誤蒐集所缺少的情境與深度。 | 這支持真人試用與 provenance 檢查並行，不表示每份 JD 都須採數位浮水印等內容鑑別技術。 |
| [OpenAI GDPval](https://openai.com/index/gdpval/) | OpenAI 以產業專家盲評真實工作產出；其 automated grader 尚不如 expert graders 可靠，因此只作粗略估計而不取代專家。該評估也明列 one-shot 無法涵蓋需要建立情境與多輪修改的工作。 | GDPval 不是 job-analysis 產品測試；直接可用的結論只是：LLM grader 不足以證明多輪、領域真實性與專家判斷。 |

## 對 Caliburn 的綜合推論

以下是根據上述來源為本產品形成的設計，不是來源原文規定。

### 1. 工程 eval 與真人 gate 必須分層

| 層次 | 要回答的問題 | 主要證據 | 可否單獨放行 |
|---|---|---|---|
| 工程與模型 eval | 已知規則、golden、schema、交易、恢復與模型品質是否回歸？ | 自動測試、合成案例、人工標註資料、deterministic／LLM grader | 否；它是進入真人試用的前置條件。 |
| 真實員工試用 | 目標員工在接近實際的條件下，能否完成工作並辨認、修正 AI 的錯誤？ | 行為觀察、產品紀錄、JD 成品、員工確認、內容審閱 | 否；若工程安全網未綠，也不能用幾次成功試用抵銷。 |
| Release decision | 已知風險是否落在 owner 預先定義的容忍範圍？ | 上述兩層證據、問題清單、修正與重測紀錄 | 是；須由有放行權限者留下決策。 |

LLM grader 可幫忙找疑似缺漏、比較版本或擴大 regression coverage，但不得同時擔任產生內容者與最終真實性裁判。真實員工掌握的是「這是不是我的工作」，合格 SME 掌握的是「此內容是否有職務分析效度」，研究者掌握的是「他是否真的能用」；三者不能由單一自動分數替代。

### 2. 什麼才算 real employee

本 gate 的核心參與者應同時符合：

- 目前實際從事本輪欲驗證的職務，對工作有直接、近期經驗；
- 是第一版 browser Web 的預期操作者，而非僅旁觀的主管、HR、顧問或開發者；
- 能以自己的實際工作提供敘事、判斷 AI 提案是否正確，並完成確認或修正；
- 招募紀錄能說明其職務情境、使用電腦經驗及本輪欲覆蓋的差異，但研究報告使用去識別代碼。

主管、HR 與職務專家可作第二層內容審閱者，不能取代 incumbent 的端到端操作。產品團隊成員、熟悉腳本的測試者、只扮演虛構職務的人，也不能被計入「真實員工已驗證」；他們的結果只能算 formative 或工程測試。若為保密而使用去識別／改寫資料，核心工作情境仍須來自參與者本人，且應記錄與真實部署的差異。

### 3. 每輪應觀察的五個面向

| 面向 | 應觀察／審查的證據 |
|---|---|
| Outcome | 員工能否從瀏覽器開啟 deployment URL，到完成訪談、檢視與修正提案、保存、關閉／恢復，再產出員工確認的 JD 草稿；是否放棄、誤以為完成、或必須由研究者代操作。 |
| Interaction | 問題與狀態是否被理解；員工是否知道 AI 正在提案而非宣告真相，能否拒絕、修改、回退與修復錯誤；卡住、求助、繞路、等待及失去信心發生在哪裡。 |
| Content quality | Duty／Task／Output／Indicator 是否反映目前工作、粒度合理、無關鍵缺漏或捏造；O/P 是否可觀察且彼此相連；KSA 是否確為工作所需並清楚標示候選／已確認。員工驗證本人工作真實性，必要時由獨立的主管／SME 驗證重要性、完整性與分析品質。 |
| Safety & agency | 系統是否洩露、不當保存或送出敏感工作資料；員工是否能在不受壓力下停止、撤回研究資料、拒絕 AI 建議；錯誤是否可恢復且不靜默覆寫已確認內容。 |
| Provenance & truth | 每項重要主張能否區分員工證據、外部基準與 AI 推論；來源連結是否可回到原始敘事／參考，修改歷程與確認者是否可追溯；虛構、矛盾、錯誤引用與不支援結論是否被偵測並處理。 |

「喜歡」、「看起來專業」或總體滿意度只可描述接受度。Gate 不得以滿意度抵銷任務未完成、內容不實、false-success、provenance 斷裂或隱私問題；也要記錄「使用者很有信心但成品其實錯誤」這種落差。

### 4. Pass／rework／無效試用的界線

Owner 應在招募前固定 rubric、severity 與門檻，避免看到結果後移動球門。研究支持下列**判斷結構**，但不在此替 owner 設定樣本數或數值：

- **Pass**：所有預先指定的必要使用情境均有合格參與者與可追溯證據；端到端 outcome、內容效度、安全、agency 與 provenance 均達預定標準；沒有未處理的 release blocker；所有保留問題都有明確風險接受者與理由。
- **Rework and retest**：核心流程需研究者代做、發生 false-success／資料遺失、員工無法辨認或修正 AI 提案、JD 有重要捏造／缺漏／錯誤邊界、evidence linkage 失真，或隱私／安全／可退出性不符。修正後須重測受影響旅程；不能只由團隊宣稱已修好。
- **Pilot invalid／evidence insufficient**：參與者不是目標職務的實際 incumbent、測的不是 release candidate、腳本暗示答案、測試資料失去工作真實性、觀察／版本／同意紀錄缺漏，或招募覆蓋與宣稱的 release scope 不一致。此時不能判 pass，也不能把沒有看到問題當成成功。
- **Non-blocking improvement**：不影響正確 outcome、內容真實性、安全、可恢復性與核心理解，且落在預定容忍範圍內的摩擦，才能帶風險放行；分類理由仍須記錄。

### 5. 最小可稽核 pilot artifacts

每一輪至少應產生：

1. **Pilot protocol**：研究問題、release scope、待測 build／model／prompt／設定、部署近似條件、rubric、severity 與預先定義的 decision rule。
2. **Recruitment screener 與 coverage matrix**：參與者納入／排除理由、incumbent 證據、欲涵蓋的職務／數位能力／使用需求；對外報告只用代碼。
3. **Information sheet、consent 與 data plan**：錄製／telemetry／OpenRouter 傳送範圍、使用目的、存取權、保存／刪除與退出方式；真實、去識別或 dummy 資料的選擇理由。
4. **Neutral task／discussion guide**：由工作目標描述任務，不洩漏操作步驟；每位參與者的執行方式一致，偏離腳本處有紀錄。
5. **Session evidence bundle**：版本與時間、觀察筆記、經同意的錄影／逐字稿、系統事件與錯誤、JD／revision／evidence-linkage 成品；原始觀察與研究者解讀分開。
6. **Content validation sheet**：由 incumbent 判斷真實性與 ownership，必要時由合格 SME 判斷重要性、完整性、粒度、O/P 可評量性及 KSA linkage；保留不同意見，不用平均分掩蓋關鍵矛盾。
7. **Issue and incident register**：每個 failure／near miss 的證據連結、影響面、severity、責任人、處置、驗證方式與狀態。
8. **Round findings 與 release decision record**：完成／失敗／誤判完成、協助與內容問題的彙整，限制與偏差，pass／rework／invalid 結論、簽核人、殘餘風險與重測範圍。
9. **去識別化 regression candidates**：把真人發現的 failure pattern 轉為後續自動 eval／golden；不得把原始機密工作資料直接搬入 repo。

## 仍須 owner 決策（本研究不代定）

- 第一版宣稱涵蓋哪些職務／產業／員工情境；coverage matrix 要如何代表該範圍。
- 每一類情境需要多少合格參與者與多少獨立證據，何時因新問題停止招募或加開一輪。
- 哪些數位能力、語文、裝置與 accessibility needs 是首發必須涵蓋，哪些明確列為限制。
- Outcome、協助程度、false-success、內容正確／完整、provenance 與可恢復性的通過門檻。
- Release blocker／non-blocker 的 severity 定義，以及哪些安全、資料損毀、錯誤歸屬或未支持內容採零容忍。
- 誰可擔任獨立內容 SME、誰有最終 release authority；兩者是否必須與開發者分離。
- 試用可否使用員工真實資料；若送往 OpenRouter，告知、去識別、保存及刪除的具體規則。
- 修正後是全輪重跑或風險導向重測，以及哪些變更會使先前 pilot evidence 失效。

這些項目一旦決定，應在試用開始前落成 protocol 與 acceptance rubric；完成 gate 後再把確認過的產品邊界、決策與 release plan 分別寫入 ADR／產品文件／執行計畫。
