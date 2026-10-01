# Caliburn 文件與 Repo 導覽

這裡只維護分類與閱讀路徑，不複製產品規則、任務進度或驗收結論。**新目標正在 `apps/api`／`apps/web` 重建；現行正式入口仍依 ADR0077，尚未完成 T18 切換。**「已有程式」「已有個別證據」與「整體驗收完成」須分開。

## 先讀

| 你現在要做什麼 | 從這裡開始 |
|---|---|
| 認識產品、準備介紹或報告 | [產品專題介紹](product-introduction.md)、[報告與研究材料入口](reports/README.md) |
| 接手開發，知道接下來做什麼 | [Goal／計畫](plans/2026-09-29-target-rebuild/README.md) → [收尾分類與下一步](plans/2026-09-29-target-rebuild/tasks.md#收尾分類與下一步) |
| 理解新架構、找元件／工具契約 | [目標架構地圖](target-architecture-map.md) → 該主題的責任文件 |
| 寫程式、改 Prompt／Tool、安排驗收 | [實作規範入口](implementation/README.md) → [程式組織](implementation/code-organization.md)／[寫法規範](implementation/coding-standard.md)／[開發與實驗規範](implementation/development-standard.md) |
| 找問題、實驗、修正與驗證紀錄 | [驗收證據分類](plans/2026-09-29-target-rebuild/evidence/README.md) |
| 查官方做法、論文、方案比較 | [研究資料](research/README.md)：Agent／Memory、工作分析、工程、檢索四類 |
| 查分析方法、訪談與 JD 撰寫要求 | [分析指南](guides/README.md)；不是工程規範或測試結果 |
| 確認哪個決定有效、哪些仍未定 | [目前決策](current-decisions.md) → 該題責任文件／ADR |
| 啟動新目標開發環境 | [後端 README](../apps/api/README.md)、[前端 README](../apps/web/README.md) |
| 操作現行正式產品 | [正式 App README](../experiments/jd-relational-app/README.md)、[runbook](runbook.md)；不要套用新目標的啟動方式 |

接手只讀本次任務需要的責任文件與最新證據，不從全部歷史重新開始。[AGENTS.md](../AGENTS.md) 管工作方式；本頁不另建規則。

### 教授版架構報告

直接閱讀[教授版架構報告](reports/system-architecture/README.md)與[圖稿](reports/system-architecture/diagrams/README.md)。2026-10-02 從 `docs/professor-architecture@c5650c15` 收錄既有報告與圖檔，不合併該分支的其他程式，也沒有更新它的程式基準。

報告是面向讀者的解說，與開發契約分開。閱讀時先看其基準與限制，不把圖稿當成此分支已實作或已驗收的證據；原分支及工作樹處理見[封存紀錄](archive/repository-organization-2026-10-02.md)。

## JD 核心知識與成品研究

分析方法、Prompt 與工具品質先讀這一組；它們不是因日期較早就失效的舊資料。

- [指南分工與研究入口](specs/2026-09-09-job-analysis-and-jd-content-research.md#2-文檔各負責什麼)。
- [完整工作分析指南](specs/2026-09-09-complete-work-analysis-guide.md)：理解工作事實、細節、缺口與分析依據。
- [個別化 JD 深度與訪談校準](specs/2026-09-09-customized-jd-depth-and-interview-calibration.md)。
- [JD 欄位與寫作指南](specs/2026-09-09-jd-field-and-writing-guide.md)。

## 現行設計與決策

| 範圍 | 權責與閱讀入口 |
|---|---|
| 新目標設計 | [目標架構地圖](target-architecture-map.md)選用的責任文件；實作／驗收狀態查[任務表](plans/2026-09-29-target-rebuild/tasks.md)，不從設計稿推導已完成 |
| 現行正式產品 | [ADR0077](adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)、[現行鳥瞰](../ARCHITECTURE.md)、[產品筆記](product-notes.md)；舊接線不是新目標的選型要求 |
| 決策與變更方法 | [決策流程](decision-process.md)、[架構討論與文件規範](architecture-discussion-standard.md)、[契約策略](contract-strategy.md) |
| 獨立 RAG 範圍 | [RAG pipeline](design/rag-pipeline.md)，不是目前 JD App 的依賴 |
| 查較早文件及演進 | [封存入口](archive/README.md) → 原索引、舊計畫、工作樹與搬移對照；先核最新決策再採用 |

## Repo 目錄分類

| 路徑 | 用途與處理方式 |
|---|---|
| `apps/api/`、`apps/web/` | 新目標程式、測試與各自啟動說明；程式內部分工沿[程式組織](implementation/code-organization.md) |
| `experiments/jd-relational-app/`、`packages/consultant-memory/` | 仍屬 ADR0077 的正式產品；不是可直接刪除的實驗或暫存 |
| `apps/`、`packages/` 的其他子目錄 | 各有範圍，包含獨立 RAG 與歷史入口；看子目錄 README，不以目錄名推定可刪 |
| `docs/` | 產品、設計、工程規範、任務、證據與沿革，分層見下表 |
| `scripts/`、`.github/`、根 workspace／lock／設定檔 | 開發、建置與自動檢查入口；不能當雜物搬走 |
| `.worktrees/`、repo 外的其他 worktree | 獨立分支的工作目錄；先以 `git worktree list` 核對，不在本分支代為整理或刪除 |
| `.research-tmp/`、`tmp/`、`output/` | 本機研究與輸出區，**可能含測試資料庫、原始實驗或 PDF**；不是全部可丟。本次已移轉的實驗與舊測試暫存見[封存紀錄](archive/repository-organization-2026-10-02.md)；未審查部分仍保留 |
| `node_modules/`、`.venv*` | 現用本機依賴，保留；不當作測試暫存清理 |
| 工具 cache／`.pytest-*` | 散落根目錄的舊資料已[集中封存或用官方工具清理](archive/repository-organization-2026-10-02.md#根目錄快取與測試暫存整理)；新任務暫存集中在 `.research-tmp/`，不再於根目錄建立每任務一份的 cache |
| `.env`、本機 agent／IDE 設定 | 私有配置或憑證；不搬入文件、實驗資料包或提交 |

## 文檔分層

分類看**用途**，有效性看**狀態**；兩者不能混在一起。研究、規格與計畫都可能包含歷史內容；日期較新不代表已採用，較舊也不代表沒用。

| 類別 | 放哪裡／怎麼找 | 不放什麼 |
|---|---|---|
| 產品介紹與目的 | [產品介紹](product-introduction.md)、[產品概念](product-concept.md) | 每次測試結果、實作進度副本 |
| 研究資料 | [research/](research/README.md)，按 Agent、工作分析、工程、檢索分主題 | 把官方能力、研究建議當成產品已採用／已驗收 |
| 工作分析與 JD 方法 | [guides/](guides/README.md) 統一導讀，既有指南正文留原路徑 | 外部樣稿冒充員工事實，或複製第二份指南 |
| 開發架構與元件契約 | [目標地圖](target-architecture-map.md) → `architecture/`、[specs/](specs/README.md)；現行另由 [design/](design/README.md) 導讀 | 所有歷史方案混成一份有效規格 |
| 程式設計與工程規範 | `implementation/`，從其 [README](implementation/README.md) 深入 | 每輪新增另一份命名或工具規則 |
| 任務、依賴與完成狀態 | [plans/](plans/README.md) → 重建計畫的 [tasks.md](plans/2026-09-29-target-rebuild/tasks.md) | 用報告或單次測試代替任務驗收 |
| 實驗、事故、修正、驗收證據 | 該計畫的 [evidence/](plans/2026-09-29-target-rebuild/evidence/README.md)，原件留 `data/`；獨立實驗在 [experiments/](experiments/README.md) | API key、私人資料、未經篩選的 checkpoint；不把失敗資料丟掉 |
| 面向教授／讀者的報告 | [reports/](reports/README.md)，引用規格與證據解說 | 另定產品規則或重抄全部實驗原件 |
| 決策與工作規則 | [current-decisions.md](current-decisions.md)、[ADR](adr/README.md)、既有討論／契約／開發規範 | 因搬資料夾而改變決策效力 |
| 操作與排錯 | 各 App README、[runbook](runbook.md)、[交付與操作設計](architecture/delivery-and-operations.md) | 混用正式產品與重建版命令 |
| 退役與歷史快照 | [archive/](archive/README.md)，保留原件與恢復路徑 | 把所有舊文件或已完成實驗都當成可刪暫存 |

## 後續文件放哪裡

1. 先找上述用途對應的既有責任文件。說明外部做法寫研究，決定產品行為改契約，說明測試經過寫證據；不要每次討論另造一份「最新版」。
2. 純研究以主題歸檔並保留日期；有效規格、指南與任務仍由原入口判讀。含研究與有效契約的混合文件暫留穩定路徑，不靠 `research` 字樣機械搬家。
3. 封存須有退役／取代／結束依據，記下接續入口與來源。搬動前檢查程式、規格、報告和證據的引用；搬動後檢查連結及內容保全。
4. 原始結果與 Git／worktree 快照不為美化目錄重寫；報告只引用，不建立另一份可分別修改的原件。

研究來源、這次 55 份研究歸位與 8 份封存的理由、驗證及限制，見[分類整理紀錄](archive/document-classification-2026-10-02.md)。這是既有[架構文件規範](architecture-discussion-standard.md)的目錄整理，不新增產品或開發授權。

## 歷史材料使用規則

1. 先區分「目標契約、現行實作、候選、歷史」；較早的「未實作／未驗」是當時狀態，進度以同任務最新證據為準。
2. 規則改在原責任文件；任務狀態改在任務表；實測經過補進對應證據。入口只更新路由，避免多份互相矛盾的規格。
3. 原索引與快照保留當時路徑；本次移動有[新舊路徑對照](archive/document-classification-2026-10-02.csv)，不是把原件刪除。仍無法證明已被取代的文件先保留，不宣告整個歷史目錄全部退役。
