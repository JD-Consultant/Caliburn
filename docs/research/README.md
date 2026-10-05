# 研究資料

研究文件記錄外部做法、論文依據、方案比較與當時的判斷，供讀者追查設計理由。
要確認現在採用哪個方案，先看[目前決策](../current-decisions.md)，再讀[架構與契約](../specs/README.md)；
要看實際效果，讀[實驗資料](../experiments/README.md)。研究完成不等於採用或驗收。

## 按主題查閱

| 分類 | 內容 |
|---|---|
| [Agent、Context 與 Memory](agent-systems/) | 原生接續、記憶組織、工具、Prompt、模型評測與不同框架的比較 |
| [工作分析與 JD](work-analysis/) | 訪談方法、職能標準、OPKS、欄位設計、內容品質及合成案例 |
| [工程與介面](engineering/) | 模組與契約、命名、資料保存、編輯互動、文件及報告寫法 |
| [檢索與資料處理](retrieval/) | PDF／OCS、embedding、相似度校準、索引與檢索；屬獨立 RAG 範圍 |

各分類保留原日期與研究脈絡，包含未採用及後來被取代的方案。查閱時須辨認當時研究對象、模型、框架與限制，不把舊建議當成現行產品要求。

## 常用入口

- 動態 JD 子任務與避免重複提問：[任務 state 比較研究](agent-systems/2026-10-05-adaptive-jd-task-state-and-repeated-questions.md)。JD 為總目標，模型依證據新增、拆合及修訂工作；比較可更新計畫、持久筆記與必要 state 主動提供。現行工具已可選接入，主動提供排除範圍及短接續點仍是候選，未改產品。

- 長任務沒有唯一答案時如何收尾：[JD 長任務收斂研究](work-analysis/2026-10-05-jd-long-task-convergence.md)。比較動態分解、反覆修訂、必要條件與提問價值；當輪確認紀錄方案保留沿革，最新公版 state 以[選用公版＋明確否認範圍](../specs/2026-10-04-public-reference-completion-design.md#最新確認只保留明確否認的工作範圍)為準。收尾效果仍需模型比較。
- 分層 Memory 的內容組織與選讀：[大資料方法與目前收斂](agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md#9-收斂採用既有分層改善內容組織與選讀)。保留原話 → 情境 → 理解，借鑑必要脈絡就近組織、增量修訂及按需載入；正式 B1／B2 提示未替換。[表示方案研究](agent-systems/2026-10-05-interview-memory-representation-alternatives.md)保留早期單集合等候選的比較沿革。
- 長任務 Agent 是否需要已完成／未完成進度：[進度保存與公版核對研究](retrieval/2026-10-05-long-running-agent-progress.md)。比較官方接續做法及待辦清單消融，保留各輪方案沿革；最新 state 已獨立保存明確否認並完成[可選角色接線](../plans/2026-10-05-occupation-reference-agent-integration.md)，未驗證重問率或收尾品質。

- 公版檢索如何判斷有效輸出：[相關性標註與評估研究](retrieval/2026-10-04-retrieval-relevance-judgment-methods.md)。研究／候選；比較 TREC／BEIR、官方自動評估與有／無對照方法，提出正文證據、局部／整體價值及已知支持涵蓋的候選判準，尚未建立新評分資料或正式契約。
- 公版參考處理進度與 Memory 更新：[研究比較](retrieval/2026-10-04-public-reference-progress-and-context-selection.md)。研究／候選；比較保存粒度、員工選答、App 投影與顧問局部重核。當時方案保留研究沿革；後續已完成可選 consumer 接線，現行範圍優先整份 JD 收尾，細節用途後續，權責依 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)。
- 如何分析訪談與撰寫 JD：[分析指南](../guides/README.md)。
- B1／B2 如何組織及增量維護內容：[情境與理解的粒度研究](work-analysis/2026-10-05-memory-organization-and-incremental-analysis.md)。比較任務分析、跨情境分析及按需 Context；方法已補入指南，Prompt 與效果待驗，不代表三層已優於單層。
- 哪些方案已採用：[目前決策](../current-decisions.md)與 [ADR](../adr/README.md)。
- 實際做過哪些比較：[產品驗證資料](../experiments/product-validation/README.md)及[開發沿革](../reports/development-history/README.md)。
- 報告怎麼呈現方法與證據：[專題報告寫作研究](engineering/2026-10-02-cs-project-report-writing-research.md)。
- 舊檔名或施工紀錄去哪裡：[歷史查閱方式](../history.md)。

新增研究沿用 `YYYY-MM-DD-明確主題.md`，記錄問題、來源、查閱日期、事實與推論、比較、限制及決策去向。被採納的規則寫回相應契約，不在研究文件另維護一份現行規格。兼具契約責任的[工具共同規範](../specs/2026-09-27-agent-tool-contract-design-research.md)仍留在規格區，不因檔名含 research 就降為參考資料。
