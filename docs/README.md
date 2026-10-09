# Caliburn 文件導覽

依手上的問題選入口。現行產品為 `apps/api`、`apps/web`；各頁會標明現行、目標／未實作、候選或歷史。詳細規則由對應責任文件維護，索引只負責指路。

## 依讀者任務查閱

| 你現在要做什麼 | 直接入口與閱讀順序 |
|---|---|
| 第一次了解產品與系統 | [產品介紹](product-introduction.md) → [架構導覽](architecture/README.md) |
| 啟動、操作或排查問題 | [操作手冊](runbook.md)；元件設定、開發及測試另查[後端 README](../apps/api/README.md)與[前端 README](../apps/web/README.md) |
| 修改程式、Prompt、Tool 或 Context | [實作規範](implementation/README.md) → 受影響的[詳細契約](specs/README.md) |
| 查當前規則與未決問題 | [目前決策](current-decisions.md) → 責任正文；正式取捨與接續關係查 [ADR](adr/README.md) |
| 改善訪談與 JD 分析方法 | [工作分析與 JD 指南](guides/README.md) |

## 文件由誰維護

| 文件層次 | 責任 |
|---|---|
| [產品概念](product-concept.md) | 產品目標、資訊關係與非目標 |
| [架構](architecture/README.md) | 模組責任、資料流、生命週期、保存與運作邊界 |
| [規格](specs/README.md) | 角色權限、資料資格、工具操作及正式生效條件 |
| [實作](implementation/README.md) | 模組接線、命名、寫法、工程機制與測試方法 |
| [操作](runbook.md) | 安裝、啟停、備份與排錯；App README 補元件設定與測試 |

維護方式依[文件與圖面規範](implementation/documentation-standard.md)，正式取捨依[決策流程](decision-process.md)。研究底稿、施工計畫、實驗原件及報告只留本機，不隨公開 repository 或其歷史發布。公開文件直接維護必要契約、官方來源與限制。

## Repo 的其他目錄

- `apps/api/`、`apps/web/`：現行產品、測試及元件說明。
- 獨立 RAG 程式：見 [RAG 說明](design/rag-pipeline.md)；JD App 可明示設定公版查讀，不以 RAG 為預設啟動依賴。
- `scripts/`、`.github/`、workspace 與 lock：開發、建置及依賴設定。
- `.tmp/`、`.research-tmp/`、`tmp/`、`output/`、`.worktrees/`：本機工作、實驗、輸出及獨立工作樹，不作正式文件入口。
- `node_modules/`、`.venv*`：本機依賴；`.env`、IDE 與代理設定屬本機配置，不收進報告或證據。

舊程式退役依 [ADR0079](adr/0079-target-rebuild-production-cutover.md)。新 checkout 不包含私人工作紀錄；產品、建置與測試使用公開交付中的必要資料。
