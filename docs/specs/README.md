# 需求、設計與工具契約

這裡保存具體責任文件及其設計沿革；**不是每個檔案都同時有效**。先讀[目標架構地圖](../target-architecture-map.md)，再沿責任往下讀。[目前決策](../current-decisions.md)與 ADR 判定效力；本索引不改寫狀態、不授權施工。

## 現在設計與開發從哪裡讀

| 主題 | 入口 |
|---|---|
| 全系統責任、交易、運作與驗收 | [目標架構地圖](../target-architecture-map.md) → `architecture/` |
| 工作分析、訪談與 JD 欄位方法 | [指南入口](../guides/README.md)，正文集中於 `guides/` |
| 訪談到 JD、背景整理的整體生命週期 | [核心閉環](2026-09-29-core-value-loop-lifecycle.md) |
| A 的 Context、固定讀取範圍與工具 | [顧問 Context](2026-09-26-consultant-context-and-state-design.md) |
| Memory 三層、候選與快照 | [Memory 子圖](2026-09-24-caliburn-layered-architecture-map.md) → [背景生命週期](2026-09-25-b1-b2-information-gap-lifecycle.md) |
| 模型與工具共用執行、恢復及壓縮 | [共用執行](2026-09-27-shared-agent-execution-and-state-design.md) |
| Tool 命名、說明、輸入、回傳與錯誤 | [工具共同規範](2026-09-27-agent-tool-contract-design-research.md)；名稱含 research，但已承擔有效規範，不搬作純研究 |
| Memory 讀取、來源及編輯 | [讀取契約](2026-09-27-memory-read-and-source-navigation-contract.md)、[更新契約](2026-09-27-memory-object-update-tool-contract.md)、[CRUD 範例](2026-09-28-memory-tools-crud-examples.md) |
| JD 欄位與模型工具 | [JD 工具契約](2026-09-29-jd-model-tool-contract-review.md) |
| 程式如何實現及測試 | [實作規範](../implementation/README.md) → [施工計畫](../plans/README.md) |

表格只提供按主題的入口；完整責任集合仍由目標架構地圖維護。現行正式產品另看 [ADR0077](../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)與[現行設計](../design/README.md)，不把兩代架構拼成一套。

## 不同用途不要混讀

- 外部官方做法、論文與方案比較：已歸位的純研究在 [research/](../research/README.md)。兼有契約的研究沿革仍留原處，依最新決策辨認，不只看檔名。
- 實際測試、事故、修正與原始結果：新目標從[驗收證據](../plans/2026-09-29-target-rebuild/evidence/README.md)進入；原 `specs/evidence/` 已歸位[較早實驗證據](../experiments/legacy-evidence/README.md)，保留原任務脈絡與結果。
- 較早方案、Proposed 或當時的完成報告：仍保留有相依關係的原件，不能只因日期舊就判退役；可用[整理前索引](../archive/2026-10-02-document-index.md)找線索，再用[搬移對照](../archive/document-classification-2026-10-02.csv)定位本次歸位的文件。
- 明確退役／已被取代的本批材料：[退役文件](../archive/retired-documents/README.md)，不作當前施工指令。

新增或修改規格，先找既有責任文件；只有新的獨立責任才分檔。用途、適用範圍、有效狀態與關係按[架構討論規範](../architecture-discussion-standard.md)維護，不繼續把純研究、實測結果與規則堆在同一份檔案。
