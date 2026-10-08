# 系統設計與工具介面

本目錄維護 AI 分析、工作記憶、模型上下文與工具的詳細行為。整體關係先看[架構導覽](../architecture/README.md)，再按下方狀態選讀；程式接線見[實作文件](../implementation/README.md)。JSON、差異格式與範例用於解釋，正式格式沿[契約來源](../contract-strategy.md)生成。

## 現行契約

| 文件 | 回答的問題 |
|---|---|
| [分層架構](2026-09-24-caliburn-layered-architecture-map.md) | A、B1、B2、JD 與 Memory 的權限、候選及發布關係 |
| [B1／B2 生命週期](2026-09-25-b1-b2-information-gap-lifecycle.md) | 單向 B1 → B2 → 發布、同一候選、來源範圍及安全點 |
| [顧問 Context](2026-09-26-consultant-context-and-state-design.md) | 固定 Memory、按需 JD／原話、Turn／Step 與恢復 |
| [JD 工作計畫](jd-work-plan.md) | 同一顧問的 Plan 內容、用法、工具、保存及接續契約；正式依據為 ADR0082 |
| [共同工具設計](2026-09-27-agent-tool-contract-design-research.md) | 工具命名、輸入、結果、錯誤及設計理由 |
| [Memory 更新契約](2026-09-27-memory-object-update-tool-contract.md) | 單物件修改、正文 diff、來源集合與操作完整性 |
| [Memory 讀取與來源](2026-09-27-memory-read-and-source-navigation-contract.md) | 導覽、最新候選／固定發布版、訪談訊息與回查 |
| [共用執行與 State](2026-09-27-shared-agent-execution-and-state-design.md) | 原生模型接續、保存交界、控制、恢復及執行限制 |
| [Memory CRUD 範例](2026-09-28-memory-tools-crud-examples.md) | 合成資料的建立、讀取、修改、刪除及錯誤處理示例 |
| [核心價值閉環](2026-09-29-core-value-loop-lifecycle.md) | 訪談、JD、背景整理的跨層時序與正式生效界線 |
| [JD 模型工具](2026-09-29-jd-model-tool-contract-review.md) | 按需讀寫、短定位、直接來源及 Changes 人工／來源比較；逐筆引用確認限 JD |
| [公版參考用途與工具](2026-10-04-public-reference-completion-design.md) | 明示設定啟用後，A 查讀、選用與否認 state；B1／B2 唯讀排除範圍；跨輪資格及原請求相容性 |

Plan 的早期未知筆記方案與比較沿革保留在[原日期文件](2026-10-06-consultant-interview-planning-and-focus-design.md)。查現行規則直接讀上表的 JD 工作計畫，不從舊方案合成契約。

## 已確認方向，尚未完成切換

| 文件 | 尚未實作或仍待驗證的範圍 |
|---|---|
| [輪前摘要與輪中壓縮](2026-10-04-context-summary-and-compaction-design.md) | 輪前改用 App 文字摘要、B1／B2 輪中壓縮後追加目前候選導覽，尚未實作；摘要內容及 Prompt 待討論。現行輪前／輪中原生 compaction 已存在 |
| [JD 與公版按需取用](2026-10-05-jd-and-reference-demand-loading-design.md) | 候選概覽 → 完整任務目錄 → 必要正文的方向已確認，搜尋投影尚未切換；已完成的工具說明、錯誤指引及精簡寫入回傳沿現行公版工具契約 |

## 候選與沿革

候選方案不因研究或隔離測試完成而生效。動態子任務、接續點及收尾方法的候選，從[研究索引](../research/README.md)查閱；待處理問題由[目前決策](../current-decisions.md)指向責任文件。已被取代的設計與決策沿[歷史查閱方式](../history.md)及 [ADR](../adr/README.md)追溯。

## 獨立 RAG 範圍

RAG 自行維護資料處理、檢索與固定來源讀取；App 的可選 HTTP consumer 沿 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)，不使 RAG 成為預設啟動依賴。

| 狀態與文件 | 責任 |
|---|---|
| 已實作：[公版職位參考 API](2026-10-05-occupation-reference-api-design.md) | 搜尋、完整已解析目錄、固定來源任務正文及 HTTP 契約；控制初值不代表通用最佳品質參數 |
| 已授權／核心修正已實作：[公版 PDF → JSON](2026-10-03-public-ocs-pdf-to-json-design.md) | 解析保真、來源檢核、失敗隔離及驗收；批次結果與未支援版型見原件 |
| RAG 契約：[相似度匹配 V1](2026-07-04-similarity-matching-v1-spec.md)、[bounded context 與 retention](2026-08-11-rag-bounded-context-retention-design.md) | 各自標示的 RAG 邊界、資料生命週期及匹配契約；不延伸為 JD App 規則 |
| 研究候選：[職位整體參考搜尋](2026-10-04-occupation-overview-reference-retrieval-design.md) | 主要工作代表性、查詢／資料單位、排序及比較範圍；品質方案與參數未定 |
| 較早候選：[員工工作與公版檢索](2026-10-04-public-reference-retrieval-design.md) | 共同來源、工作內容／職位整體兩種導覽及元件比較；完整度流程未接入 App |
| 研究判準：[代表主要職位評分 v2](2026-10-04-representative-occupation-scoring-protocol.md) | 逐份分級及正文證據；[v1](2026-10-04-public-reference-scoring-protocol.md)保留較早的局部有用判準與校準例 |

各輪檢索比較按變因從[實驗索引](../experiments/README.md#檢索與資料處理)查閱。數字、模型條件、判讀疑義及完整限制由各次原件維護；API 工程驗證另見[工程驗證](../experiments/engineering/README.md#公版參考-api)。

## 方法與實驗

- 產品目的與資訊關係：[產品概念](../product-concept.md)。
- 工作分析、訪談及 JD 欄位方法：[指南入口](../guides/README.md)。
- 外部方法與方案比較：[研究入口](../research/README.md)。
- 已驗與未驗範圍：[驗證章節](../architecture/verification.md)；模型原件：[產品實驗資料](../experiments/product-validation/README.md)。
- 設計演進：[開發沿革](../reports/development-history/README.md)。
