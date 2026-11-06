# Caliburn 架構

Caliburn 採模組化單體：單一 FastAPI 應用程序提供 HTTP、SSE 與建置後的 Web，PostgreSQL 保存業務資料及官方 Checkpoint，Qdrant 保存公版檢索索引。正式程式位於 `apps/backend` 與 `apps/frontend`。

能力模組管理規則與資料，Bundle／Plugin 決定模型如何使用能力，Agent Core 管通用執行。公版 PDF 解析、Embedding、rerank、索引與查讀由 `occupation_reference` 內聚管理，不另部署解析器或 GPU HTTP 服務。停用 Agent Plugin 不會移除模組的查讀、維護與必要清理能力。

## 閱讀入口

| 問題 | 責任文件 |
|---|---|
| 系統邊界、模組歸屬及部署 | [系統架構與責任規格](apps/backend/architecture.md) |
| 程式放哪裡、依賴方向 | [程式組織](docs/standards/code-organization.md) |
| 正式資料、版本、取消及恢復 | [保存與恢復](docs/architecture/persistence.md) |
| 啟停、設定與備份 | [操作手冊](docs/operations/README.md) |
| 實作與測試定位 | [實作導覽](docs/implementation/README.md)、[驗證範圍](docs/architecture/verification.md) |

後端按本機單 worker 設計；沒有登入、ACL、多租戶或多主機鎖。OpenAI 模型透過外部 API 執行，本機保存不代表工作資料不外送。來源、權限與正式保存由能力模組判定，模型短碼及工具參數不授予權限。
