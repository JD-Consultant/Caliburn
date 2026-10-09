# Caliburn 文件導覽

依手上的問題選入口。現行產品為 `apps/api`、`apps/web`；各頁維護現行行為及已知限制。詳細規則由對應責任文件維護，索引只負責指路。

## 依讀者任務查閱

| 你現在要做什麼 | 直接入口與閱讀順序 |
|---|---|
| 第一次了解產品與系統 | [產品介紹](product-introduction.md) → [架構導覽](architecture/README.md) |
| 啟動、操作或排查問題 | [操作手冊](runbook.md)；元件設定、開發及測試另查[後端 README](../apps/api/README.md)與[前端 README](../apps/web/README.md) |
| 修改程式、Prompt、Tool 或 Context | [貢獻指南](../CONTRIBUTING.md) → [程式規範](standards/README.md)及受影響的責任正文 |
| 查現行規則與設計取捨 | [架構與現行責任](architecture/README.md) → 責任正文；現行理由查 [現行設計取捨](architecture/design-decisions.md) |
| 查訪談、工作分析及 JD 的已採用內容要求 | [產品內容判準](product-concept.md#內容判準)與正式角色提示 |

## 文件由誰維護

| 文件層次 | 責任 |
|---|---|
| [產品概念](product-concept.md) | 產品目標、資訊關係與非目標 |
| [架構](architecture/README.md) | 模組責任、資料流、生命週期、保存與運作邊界 |
| [程式規範](standards/README.md) | 模組組織、程式寫法、資源、測試、Log 及契約策略 |
| [實作](implementation/README.md) | 具體程式接線、工程機制與測試責任 |
| [操作](runbook.md) | 安裝、啟停、備份與排錯；App README 補元件設定與測試 |

修改、驗證及文件維護見[貢獻指南](../CONTRIBUTING.md)。公開文件直接保留必要契約、官方來源與已知限制；研究、內部流程、決策及工作原件只留本機，新 checkout 不依賴私人檔案。

## Repo 的其他目錄

- `apps/api/`、`apps/web/`：現行產品、測試及元件說明。
- 獨立 RAG 程式：見 [RAG 說明](design/rag-pipeline.md)；JD App 可明示設定公版查讀，不以 RAG 為預設啟動依賴。
- `scripts/`、`.github/`、workspace 與 lock：開發、建置及依賴設定。
- `.tmp/`、`.research-tmp/`、`tmp/`、`output/`、`.worktrees/`：本機工作、實驗、輸出及獨立工作樹，不作正式文件入口。
- `node_modules/`、`.venv*`：本機依賴；`.env`、IDE 與代理設定屬本機配置，不收進報告或證據。

舊程式退役依 [正式產品與選型](architecture/design-decisions.md)。新 checkout 不包含私人工作紀錄；產品、建置與測試使用公開交付中的必要資料。
