# 研究資料

研究文件記錄外部做法、論文依據、方案比較與當時的判斷。確認現在採用什麼，讀[目前決策](../current-decisions.md)與責任契約；查實際效果，讀[實驗資料](../experiments/README.md)。研究完成不等於採用或驗收，本索引不維護最新施工狀態。

## 按主題查閱

| 分類 | 內容 |
|---|---|
| [Agent、Context 與 Memory](agent-systems/) | 原生接續、記憶組織、工具、Prompt、模型評測及框架比較 |
| [工作分析與 JD](work-analysis/) | 訪談方法、職能標準、OPKS、欄位設計、內容品質及合成案例 |
| [工程與介面](engineering/) | 模組與契約、命名、資料保存、編輯互動、文件及報告寫法 |
| [檢索與資料處理](retrieval/) | PDF／OCS、embedding、相似度校準、索引及檢索；屬獨立 RAG 範圍 |

各分類保留日期、研究對象、模型、框架及限制，包含未採用與後來被取代的方案。日期是研究時點，不足以判斷文件是否有效。

## 常用入口

| 想追查的問題 | 研究與接續文件 |
|---|---|
| 文件如何分類、避免多處維護 | [文件資訊架構研究](engineering/2026-10-08-documentation-information-architecture.md)保存本機盤點、方案與整理建議；維護規則沿[文件與圖面規範](../implementation/documentation-standard.md) |
| 架構與流程圖如何選符號 | [圖面與技術文件研究](engineering/2026-10-08-architecture-diagram-notation-and-documentation.md)區分官方規範、工具表示與本案慣例 |
| 全系統工程做法與組裝取捨 | [18 面向工程研究](engineering/2026-10-08-full-stack-engineering-practices.md)比較架構、契約、資料、長任務、並行、網路、安全、前端、測試、觀測、效能及交付；§6 比較公開插件與 harness 做法。施工結果由[計畫](../plans/README.md)維護 |
| 正式 Agent 如何便於比較及診斷 | [可對照與可觀測性研究](engineering/2026-10-08-agent-experimentability-and-observability.md)從實際參數、工具往返與保存結果提出工程判準；已採用規則沿[實作規範](../implementation/README.md) |
| 長訪談如何保留焦點與剩餘工作 | [規劃研究](work-analysis/2026-10-06-long-interview-planning-and-focus-research.md)保存公開方法與方案演進；現行內容及保存見[JD 工作計畫](../specs/jd-work-plan.md)，早期未知筆記見[設計沿革](../specs/2026-10-06-consultant-interview-planning-and-focus-design.md) |
| 筆記如何保留語意並重新定焦 | [語意忠實與重新定焦](work-analysis/2026-10-07-interview-note-fidelity-and-refocus-followup.md)對照內容指南、設計及反例，討論局部候選與既有回看／更新要求 |
| JD 子任務如何修訂、避免重問 | [任務 state 比較](agent-systems/2026-10-05-adaptive-jd-task-state-and-repeated-questions.md)比較可更新計畫、持久筆記、排除範圍主動提供及短接續點 |
| 沒有唯一答案的 JD 長任務如何收尾 | [收斂研究](work-analysis/2026-10-05-jd-long-task-convergence.md)比較動態分解、反覆修訂、必要條件與提問價值；現行公版 state 沿[工具契約](../specs/2026-10-04-public-reference-completion-design.md) |
| 分層 Memory 如何組織及選讀 | [大資料方法與收斂](agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md)及[粒度與增量分析](work-analysis/2026-10-05-memory-organization-and-incremental-analysis.md)；較早單集合等方案見[表示研究](agent-systems/2026-10-05-interview-memory-representation-alternatives.md)，持續使用的方法見[分析指南](../guides/README.md) |
| 長任務是否需要已完成／未完成進度 | [進度保存與公版核對](retrieval/2026-10-05-long-running-agent-progress.md)比較公開接續做法與待辦消融，保存否認 state 各輪設計沿革 |
| 公版檢索如何評估有效輸出 | [相關性標註與評估](retrieval/2026-10-04-retrieval-relevance-judgment-methods.md)比較 TREC／BEIR、官方自動評估及有／無對照方法；提出正文證據、局部／整體價值與已知支持涵蓋的候選判準 |
| 參考處理進度如何銜接 Memory 更新 | [進度與提供資料研究](retrieval/2026-10-04-public-reference-progress-and-context-selection.md)比較保存粒度、員工選答、App 投影與局部重核；現行權責沿 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)及[公版工具契約](../specs/2026-10-04-public-reference-completion-design.md) |
| 報告如何呈現方法與證據 | [專題報告寫作研究](engineering/2026-10-02-cs-project-report-writing-research.md) |

研究效果與採用判斷不要從上表推定。方案採用沿[目前決策](../current-decisions.md)與 [ADR](../adr/README.md)，比較結果沿[產品驗證](../experiments/product-validation/README.md)及[檢索實驗](../experiments/README.md#檢索與資料處理)，舊路徑依[歷史查閱方式](../history.md)定位。

## 新增與維護研究

新增研究沿用 `YYYY-MM-DD-明確主題.md`，記錄問題、來源、查閱日期、事實與推論、比較、限制及決策去向。被採納的規則寫回責任契約，研究保留當時推論。兼具契約責任的[工具共同規範](../specs/2026-09-27-agent-tool-contract-design-research.md)仍留在規格區，不因檔名含 research 就降為參考資料。
