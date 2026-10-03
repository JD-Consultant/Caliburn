# 研究資料

研究文件說明外部做法、論文依據、方案比較與當時的判斷；研究完成不等於採用或驗收。現行規則見[架構與契約](../specs/README.md)，實測結果見[實驗資料](../experiments/README.md)。

## 按主題查閱

| 分類 | 內容 |
|---|---|
| [Agent、Context 與 Memory](agent-systems/) | 原生接續、記憶組織、工具、Prompt、模型評測與不同框架的比較 |
| [工作分析與 JD](work-analysis/) | 訪談方法、職能標準、OPKS、欄位設計、內容品質及合成案例 |
| [工程與介面](engineering/) | 模組與契約、命名、資料保存、編輯互動、文件及報告寫法 |
| [檢索與資料處理](retrieval/) | PDF／OCS、embedding、相似度校準、索引與檢索；屬獨立 RAG 範圍 |

各分類保留原日期與研究脈絡，包含未採用及後來被取代的方案。查閱時須辨認當時研究對象、模型、框架與限制，不把舊建議當成現行產品要求。

## 常用入口

- 如何分析訪談與撰寫 JD：[分析指南](../guides/README.md)。
- 哪些方案已採用：[目前決策](../current-decisions.md)與 [ADR](../adr/README.md)。
- 實際做過哪些比較：[產品驗證資料](../experiments/product-validation/README.md)及[開發沿革](../reports/development-history/README.md)。
- 報告怎麼呈現方法與證據：[專題報告寫作研究](engineering/2026-10-02-cs-project-report-writing-research.md)。
- 舊檔名或施工紀錄去哪裡：[歷史查閱方式](../history.md)。

新增研究沿用 `YYYY-MM-DD-明確主題.md`，記錄問題、來源、查閱日期、事實與推論、比較、限制及決策去向。被採納的規則寫回相應契約，不在研究文件另維護一份現行規格。兼具契約責任的[工具共同規範](../specs/2026-09-27-agent-tool-contract-design-research.md)仍留在規格區，不因檔名含 research 就降為參考資料。
