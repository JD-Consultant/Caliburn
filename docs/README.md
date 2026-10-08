# Caliburn 文件導覽

依手上的問題選入口。現行產品為 `apps/api`、`apps/web`；各頁會標明現行、目標／未實作、候選或歷史。詳細規則由對應責任文件維護，索引只負責指路。

## 依讀者任務查閱

| 你現在要做什麼 | 直接入口與閱讀順序 |
|---|---|
| 第一次了解產品與系統 | [產品介紹](product/README.md) → [架構導覽](architecture/README.md)。需要完整敘事再讀[專題報告](reports/project-report/report.md)或[系統架構報告](reports/system-architecture/README.md) |
| 第一次安裝並使用 | [快速開始](operations/getting-started.md)：Docker 基本模式，使用預設設定完成首次啟動 |
| 啟停、更新或排查問題 | [操作手冊](operations/README.md)；開發環境見[原生開發](operations/native-development.md)，公版查找見 [RAG 操作](operations/rag.md) |
| 修改程式、Prompt、Tool 或 Context | [規範與方法](standards/README.md) → 受影響的[詳細契約](specs/README.md)與[實作接線](implementation/README.md)；多步驟施工由[計畫入口](plans/README.md)查閱 |
| 查當前規則與未決問題 | [目前決策](current-decisions.md) → 責任正文；正式取捨與接續關係查 [ADR](adr/README.md) |
| 改善訪談與 JD 分析方法 | [工作分析與 JD 指南](standards/work-analysis/README.md) → 對應研究與效果證據 |
| 查測試結果、研究或歷史 | [驗證範圍](architecture/verification.md)、[實驗原件](experiments/README.md)、[研究分類](research/README.md)；演進解說見[開發沿革](reports/development-history/README.md)，舊檔取回見[歷史查閱方式](history.md) |

## 文件由誰維護

| 文件層次 | 責任 |
|---|---|
| [產品](product/README.md) | 介紹使用情境與價值；[產品概念](product/concepts.md)維護目標、資訊關係與非目標 |
| [規範與方法](standards/README.md) | 從研究整理、持續修訂的開發、架構設計、測試、Log、文件製圖及工作分析方法 |
| [架構](architecture/README.md) | 模組責任、資料流、生命週期、保存與運作邊界 |
| [規格](specs/README.md) | 角色權限、資料資格、工具操作及正式生效條件 |
| [實作](implementation/README.md) | 現行技術選型、程式接線與驗證對照 |
| [入門](operations/getting-started.md)、[操作](operations/README.md) | 入門只維護首次使用路線；runbook 維護啟停、更新、備份與排錯，原生開發及 RAG 按讀者任務分頁。App README 補元件設定與測試 |
| [決策](adr/README.md) | 正式取捨及採用理由；[目前決策](current-decisions.md)提供有效狀態與路由 |
| [研究](research/README.md) | 原始依據、方案比較、研究過程與當時判斷；整理後的規範引用其來源 |
| [實驗](experiments/README.md) | 受測條件、結果、限制及必要原件 |
| [計畫](plans/README.md) | 施工範圍、進度與驗收；已移出的舊計畫由歷史索引取回 |
| [報告](reports/README.md) | 面向指定讀者與日期範圍解釋設計及成果，引用契約與原件 |
| [圖庫](diagrams/README.md) | 集中維護設計圖源、生成圖片與產品截圖，供正文及報告共用；實驗圖片直接引用原件 |
| [歷史索引](history.md)、[提交對照](history-commit-map.csv) | 查回舊文件及退役程式，將歷史提交身分對應至修正後版本；保留固定路徑供既有引用使用 |

維護方式依[文件與圖面規範](standards/documentation-standard.md)，正式取捨依[決策流程](standards/decision-process.md)。報告、計畫及索引不另抄完整契約。

## Repo 的其他目錄

- `apps/api/`、`apps/web/`：現行產品、測試及元件說明。
- 獨立 RAG 程式：分工見 [RAG 架構](architecture/rag-pipeline.md)，啟停與設定見 [RAG 操作](operations/rag.md)。
- `scripts/`、`.github/`、workspace 與 lock：開發、建置及依賴設定。
- `.tmp/`：按需建立的工作暫存；`.research-tmp/`：本機執行環境與字型；`.worktrees/`：獨立工作樹。皆不作正式文件入口。
- `node_modules/`、`.venv*`：本機依賴；`.env`、IDE 與代理設定屬本機配置，不收進報告或證據。

舊程式退役依 [ADR0079](adr/0079-target-rebuild-production-cutover.md)。本機 `docs/archive/` 不隨 Git 發布；已提交原件從[歷史索引](history.md)取回，僅本機保存與私人封存材料查[保存索引](experiments/artifact-storage.md)。與固定 Git 原件相同的本機副本不重複保留。
