# Caliburn 文件導覽

公開文件維護產品目的、架構、現行契約、實作接線及操作方式。正式產品為 `apps/api`、`apps/web`；各頁維護現行行為及已知限制。詳細規則由對應責任文件維護，索引只負責指路。

## 依讀者任務查閱

| 你現在要做什麼 | 直接入口與閱讀順序 |
|---|---|
| 第一次了解產品與系統 | [產品介紹](product/README.md) → [架構導覽](architecture/README.md) |
| 第一次安裝並使用 | [快速開始](operations/getting-started.md)：Docker 基本模式 |
| 啟停、更新或排查問題 | [操作手冊](operations/README.md)、[原生開發](operations/native-development.md)、[RAG 操作](operations/rag.md) |
| 修改程式、Prompt、Tool 或 Context | [開發規範](standards/development-standard.md) → 受影響的[實作與契約接線](implementation/README.md) |
| 查現行規則及設計取捨 | [架構](architecture/README.md) → 負責該規則的正文；限制見[驗證範圍](architecture/verification.md) |
| 改善訪談與 JD 分析方法 | [工作分析與 JD 指南](standards/work-analysis/README.md) |
| 選擇測試與判讀限制 | [驗證範圍](architecture/verification.md)、[驗證責任](implementation/verification-plan.md)及各 App README |

## 文件維護責任

| 文件層次 | 責任 |
|---|---|
| [產品](product/README.md) | 使用情境、目標、資訊關係與非目標 |
| [規範與方法](standards/README.md) | 開發、模組組織、測試、Log、文件製圖及工作分析方法 |
| [架構](architecture/README.md) | 模組責任、資料流、生命週期、保存與運作邊界 |
| [實作與契約接線](implementation/README.md) | 角色權限、資料資格、工具操作及正式生效條件 |
| [實作](implementation/README.md) | 現行技術選型、程式接線與驗證對照 |
| [操作](operations/README.md) | 啟停、更新、備份與排錯；App README 補元件設定與測試 |
| [現行設計取捨](architecture/design-decisions.md) | 正式取捨及採用理由；[架構與現行責任](architecture/README.md)提供有效狀態 |
| [圖庫](diagrams/README.md) | 架構圖源及衍生圖片 |

維護方式依[文件與圖面規範](standards/documentation-standard.md)，重大取捨依[決策流程](standards/decision-process.md)。ADR、設計稿、決策登記、研究底稿、施工計畫、測試執行原件及報告只在本機保存，不隨公開 repository 或其歷史發布。公開文件直接保留必要契約、官方來源及已知限制；新 checkout 不包含私人佐證，也不依賴那些檔案才能執行產品、建置或測試。

## 程式與本機環境

- `apps/api/`、`apps/web/`：現行產品、測試及元件說明。
- 獨立 RAG：分工見 [RAG 架構](architecture/rag-pipeline.md)，設定見 [RAG 操作](operations/rag.md)。
- `scripts/`、`.github/`、workspace 與 lock：開發、建置及依賴設定。
- `.tmp/`、本機依賴、`.env`、IDE 與代理個人設定不屬於公開交付。
