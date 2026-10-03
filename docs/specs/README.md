
# 系統設計與工具介面

本目錄詳細說明 AI 分析、工作記憶、模型上下文與工具的行為。整體關係可先看[架構導覽](../target-architecture-map.md)，再依問題閱讀下面各章；JSON、差異格式與操作範例用來說明模型和 App 如何交換資料。


## 核心系統設計

| 文件 | 主要內容 |
|---|---|
| [分層架構](2026-09-24-caliburn-layered-architecture-map.md) | A、B1、B2、JD 與 Memory 的權限、候選及發布關係 |
| [B1／B2 生命週期](2026-09-25-b1-b2-information-gap-lifecycle.md) | 單向 B1 → B2 → 發布、同一候選、來源範圍及安全點 |
| [顧問 Context](2026-09-26-consultant-context-and-state-design.md) | A 固定 Memory、按需 JD／原話、Turn／Step 與壓縮恢復 |
| [共同工具設計](2026-09-27-agent-tool-contract-design-research.md) | 工具命名、輸入、結果、錯誤與設計理由 |
| [Memory 更新契約](2026-09-27-memory-object-update-tool-contract.md) | 單物件修改、正文 diff、來源集合與操作完整性 |
| [Memory 讀取與來源](2026-09-27-memory-read-and-source-navigation-contract.md) | 導覽、最新候選／固定發布版、訪談訊息與回查 |
| [共用執行與 State](2026-09-27-shared-agent-execution-and-state-design.md) | 原生模型接續、保存交界、控制、恢復與執行限制 |
| [Memory CRUD 範例](2026-09-28-memory-tools-crud-examples.md) | 以合成資料示範建立、讀取、修改、刪除及錯誤處理 |
| [核心價值閉環](2026-09-29-core-value-loop-lifecycle.md) | 訪談、JD、背景整理的跨層時序與正式生效界線 |
| [JD 模型工具](2026-09-29-jd-model-tool-contract-review.md) | 按需讀寫、短定位、直接來源與兩類差異；逐筆引用確認限 JD |

## 獨立 RAG 範圍

- [相似度匹配 V1](2026-07-04-similarity-matching-v1-spec.md)
- [RAG bounded context 與 retention](2026-08-11-rag-bounded-context-retention-design.md)

這兩份說明獨立的檢索研究，不是現行 JD App 的執行依賴。


## 方法與實驗

- 產品目的與資訊關係：[產品概念](../product-concept.md)。
- 工作分析、訪談及 JD 欄位方法：[指南入口](../guides/README.md)。
- 外部方法與方案比較：[研究入口](../research/README.md)。
- 測試方法、結果與限制：[驗證章節](../architecture/verification.md)、[產品實驗資料](../experiments/product-validation/README.md)。
- 設計如何隨問題演進：[開發沿革](../reports/development-history/README.md)。
