# AI 對話式職務分析：由上而下、由下而上或混合式

日期：2026-08-03

狀態：Accepted research；決策見 [ADR 0042](../adr/0042-hybrid-job-discovery-and-ttop-formation.md)

## 研究問題與結論

問題：Caliburn 應以「主要職責 → Task → Output → Indicator」為訪談主線，還是以「具體工作事例 → Task → Duty → Output → Indicator」為主線？

**結論：高可信度原始資料最支持混合式，沒有來源宣稱「純故事式」普遍最佳。** 最接近官方成熟做法的是：先界定職位／工作範圍與蒐集既有資料，透過現職者、主管或 SME 的開放訪談取得真實工作與具體事例，再把資料整理成候選 Task，以結果導向的功能分析形成 Duty–Task 層級；接著確認 Output／Indicator，逐 Task 連結 KSA，最後由 SME 評定重要性、完整性並驗證。故事是發現與佐證工具，不是最終分類法；既有 Duty／taxonomy 是假說與覆蓋檢核，不應成為封閉選單。

## 來源明說了什麼

| 主題 | 原始／第一方來源明說 | 能支持的結論 |
|---|---|---|
| 方法選擇 | iCAP《職能基準發展指引》明說沒有單一方法絕對好壞，應重用實際從業人員為專家、依實況混成方法並以多方法／多來源三角檢核；其操作範例以功能分析為主，混合訪談與專家會議。[iCAP 指引，頁 34、39–48](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download) | 官方最直接支持「混合式」，不是二選一。 |
| 現職者／SME | iCAP 用在職人士訪談讓資料真實反映工作現況，訪談底稿再交專家會議確認；品質要求包含具實務經驗利益關係人群體參與。OPM 先蒐集職務說明、SME、績效標準與職業研究，再列 Tasks／Competencies，由 SME 判斷 criticality 與 linkage。[iCAP 指引，頁 35、40–45](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download)；[OPM Six Steps](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_checklist.pdf) | 員工不是唯一真相來源；候選內容應保留來源，並有後續確認。單人本機版可由同一操作者確認，但不能把 AI 推論冒充 SME 共識。 |
| Task 粒度 | O*NET 把 Task 視為「具有 meaningful outcome 的最小活動單位」，結構為 Action + Object + Purpose／Result（可加 Enabler／Context），並反對複雜 compound statement、時間順序串成一項 Task。OPM 同樣要求「做什麼／對誰或什麼／產生什麼或為何／如何」，避免 double-barreled 與工具過度具體。[O*NET Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf)；[OPM Job Analysis Presentation，頁 18–22](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_presentation.pdf) | Task 不能是 Duty 級空話，也不能把每個按鍵／工具步驟升格；應是有意義結果、可辨識邊界的工作單位。 |
| 具體事例／BEI | iCAP BEI 要受訪者回憶具體成敗事件，以 STAR 追問真實情境、任務、行動、結果；優點是細節豐富。缺點是需大量陳述、時間與成本高、訪談技巧要求高，歸納／編碼亦最困難。[iCAP BEI，頁 26–31](https://icap.wda.gov.tw/File/Knowledge/Method/2-04.pdf) | 適合取證與釐清行為，不足以單獨保證工作範圍完整。 |
| 關鍵事件偏差 | iCAP 2022 比較表明列 CIT 可能漏失例行事件、重要性判斷可能主觀，且可能無法全面分析職務；BEI 也須訪談至資料飽和。[iCAP 指引，頁 31–34](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download) | 不能只問「最成功／最挫折的故事」；還要盤點週期性、例行、交接、例外與低頻高重要工作。 |
| taxonomy／既有清單 | O*NET 會讓 incumbents／occupational experts 評定既有 task list，同時鼓勵提交清單中沒有的 write-ins；分析員再做 task/non-task、重複／重疊、整併、人工覆核與下一輪驗證。O*NET 也採 incumbents、experts、analysts、職缺與研究等多來源。[O*NET Emerging Tasks 2025，頁 1–16](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf)；[O*NET Data Collection](https://www.onetcenter.org/dataCollection.html) | 官方實務不是封閉 taxonomy，也不是把現職者原話直接發布；既有清單與開放新增並存，再經整併和驗證。它**沒有**證明「先自由回憶、後顯示 taxonomy」優於相反順序。 |
| 低頻高重要工作 | OPM 將 Frequency 與 Importance 分開評分；O*NET 也分開蒐集 relevance、importance、frequency，而目前 Core Task 的標準是 relevance ≥ 67% 且 importance ≥ 3.0，並未以高頻為必要條件。[OPM Presentation，頁 29–38](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_presentation.pdf)；[O*NET 30.3 Task Statements](https://www.onetcenter.org/dictionary/30.3/text/task_statements.html)；[Task Ratings](https://www.onetcenter.org/dictionary/30.3/text/task_ratings.html) | Caliburn 不應以頻率單獨決定是否納入；正式、低頻但高影響／高風險的責任要能保留。OPM 的特定甄選用途另有 frequency cutoff，不能直接搬成 JD 的通用刪除規則。 |
| Output → Indicator | iCAP 功能分析是結果導向，從關鍵目的往下拆到個人能完成的功能單元；功能單元確認後，才定義對應的工作產出與行為指標，兩者可合併討論以形成可衡量成果與可觀察行為。行為指標是成功完成任務的標準。[iCAP 指引，頁 39、45–48](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download)；[iCAP 職能相關概念](https://icap.wda.gov.tw/ap/knowledge_introduction.php) | 「以終為始」與官方結果導向一致；但來源說的是 O 與 P 共同對應已確認的 Task，不是只憑 Output 自動推導 P。 |
| KSA linkage | OPM 要 SME 逐一連結 Tasks 與 Competencies，無法連到任何 Task 的 competency 應剔除。iCAP 要由功能單元展開 KSA，並把 KSA 對應行為指標。[OPM Presentation，頁 41](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_presentation.pdf)；[iCAP 指引，頁 48](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download) | KSA 可由既有基準或 AI 提候選，但必須可回連到 Task／Indicator 並經人確認，不能成為獨立形容詞清單。 |

## 三條路線比較（綜合推論）

以下是依上述來源對 Caliburn 的**綜合推論**，不是任何單一來源的原句：

| 路線 | 合理處 | 主要缺口 | 判斷 |
|---|---|---|---|
| 純由上而下 | 符合功能分析的目的→功能→單元分解，易維持完整層級與一致粒度。 | 若 Duty／清單變成封閉答案，會漏掉清單外實際工作；官方成熟流程仍要求現職者輸入、開放新增及驗證。 | 可作分析骨架與後段覆蓋檢核，不宜作封閉訪談。 |
| 純由下而上故事式 | BEI 能取得具體、可追溯的行為與結果，特別適合釐清 actor、例外與品質條件。 | 關鍵故事會漏例行工作；飽和成本高；故事仍需跨事件整併、抽象化和分類，沒有官方來源稱其普遍最佳。 | 可作重要發現模式，不足以單獨完成 JD。 |
| 混合式 | 同時具備真實工作證據、結果導向結構、開放新增、SME 驗證與 KSA linkage；與 iCAP 明示範例及 OPM/O*NET 實務最接近。 | 需防止既有 taxonomy 過早成為答案，也需明確的完成條件。 | **推薦。** |

## 對 Caliburn 的推薦流程

1. **建立暫定框架**：讀取既有 JD／職能基準，只形成職位範圍、候選 Duty 與待驗證清單，明示「可新增／修正／否定」。
2. **先開放發現，再定向補漏**：請員工描述近期典型工作；對高判斷、高風險或例外工作用 STAR 深挖。之後才用既有 Duty、O*NET／iCAP 候選和週期清單檢查例行、月／季／年度、交接、例外及低頻高重要責任。先自由回憶是降低提示影響的產品設計推論，並非來源已證實的唯一最佳順序。
3. **形成 Task 而非照抄故事**：跨故事／陳述整併為 Action–Object–Purpose/Result 的穩定工作單位；保留原話、來源與不確定性。
4. **歸納 Duty 並讓使用者確認**：以結果導向功能分析檢查層級、粒度與覆蓋，允許移動、拆分、合併與補新增 Task。
5. **完成 T–T–O–P**：Task 確認後才討論 Output 與 Indicator；由預期結果反查可觀察行為與品質／條件，但禁止只憑 O 自動生成正式 P。
6. **逐項連結 KSA**：AI／職能基準只提供候選；每個 KSA 必須指出支持的 Task／Indicator 與來源，經人確認後納入。
7. **完成 gate**：每個 Task 分開記錄 relevance／ownership、importance／impact、frequency／cycle、evidence、confidence；以完整性回顧與使用者確認收斂，不以「故事講完」或高頻作為唯一停止／保留條件。

## 邊界

- 這些來源多描述國家職能標準、職務分析與甄選用途，不是 AI 對話產品的 A/B 實驗；它們不能直接證明具體 UI 問句順序的因果效果。
- 「taxonomy 過早顯示會 anchoring」在本次限定的官方資料中沒有直接比較試驗；因此本文件只把「先開放、後提示」列為可驗證的產品假說，不當作既定科學事實。
- iCAP 的「功能單元可由一人獨力完成」是其產業職能基準粒度檢核。套到企業 JD 時，應解讀為一個人可對該責任負責並完成其角色份內成果，不代表跨部門工作必須由一人包辦。
