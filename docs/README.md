# Caliburn 文件導覽

正式產品位於 `apps/backend` 與 `apps/frontend`。本目錄提供產品、架構、開發規範與操作入口；模組與 Bundle 的詳細契約就近維護，不在本目錄複製第二套 Schema 或執行流程。

## 依工作查閱

| 工作 | 閱讀順序 |
|---|---|
| 了解產品 | [產品介紹](product/README.md) → [產品概念與內容判準](product/concepts.md) |
| 安裝與使用 | [快速開始](operations/getting-started.md) → [操作手冊](operations/README.md) |
| 了解系統 | [架構導覽](architecture/README.md) → [系統責任規格](../apps/backend/architecture.md) |
| 查模組、Bundle 與流程 | [模組與 Bundle](../apps/backend/README.md#檔案位置) → [實作入口](implementation/README.md) |
| 開發與審查 | [貢獻指南](../CONTRIBUTING.md) → [程式規範](standards/README.md) |
| 核對契約與生成 | [契約策略](standards/contract-strategy.md) → [資料與契約接線](implementation/data-and-contracts.md) |
| 選擇驗證 | [驗證範圍](architecture/verification.md) → [驗證責任](implementation/verification-plan.md) |
| 維護公版來源／索引 | [公版操作](operations/rag.md) → [公版模組](../apps/backend/src/caliburn/modules/occupation_reference/README.md) |
| 維護圖面 | [圖庫](diagrams/README.md)及負責該圖的模組文件 |

## 文件責任

產品文件說明使用者目標與內容判準；架構文件說明跨模組責任與限制；模組 README 維護能力、資料及交易，Bundle README 維護 Agent 接入；操作文件及後端／前端 README 維護命令。入口只導航，規則在負責正文修改。

公開文件讓新 checkout 能獨立理解、建置與驗證。研究、內部決策、工作紀錄及完整測試輸出留在本機，不是公開使用的前置。文件維護與檢查見[貢獻指南](../CONTRIBUTING.md#文件維護)。
