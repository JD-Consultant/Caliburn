# Caliburn 文件導覽

文件分成產品與架構、開發與操作、研究與實驗，以及歷史四類。可從產品介紹了解需求，再由架構文件深入設計；研究與實驗保留方案比較、問題發現及測試結果。

## 產品介紹與報告

以下三份文件依序說明產品、專題成果與系統內部設計。

1. [產品介紹](product-introduction.md)：顧問作業的需求、使用流程與產品價值。
2. [專題報告](reports/project-report/report.md)：動機、相關方法、系統設計、實驗、結果及後續研究；正文與附錄可獨立閱讀。
3. [系統架構報告](reports/system-architecture/README.md)：程式內部分工、Context、Memory、引用與恢復，附[架構圖](reports/system-architecture/diagrams/README.md)。

實驗材料與演進脈絡可從[報告材料索引](reports/README.md)深入。

## 開發與維護

| 需要處理的事情 | 閱讀入口 |
|---|---|
| 確認現行狀態與有效決策 | [目前決策](current-decisions.md)、[ADR](adr/README.md) |
| 理解整體架構與各元件契約 | [現行架構地圖](target-architecture-map.md) → [設計與工具契約](specs/README.md) |
| 修改程式、Prompt、Tool 或 Context | [實作規範](implementation/README.md)：模組、命名、寫法、測試及研究方法 |
| 查訪談分析與 JD 寫作方法 | [分析指南](guides/README.md)；不是工程規範或實驗結果 |
| 安裝、啟停、備份及排錯 | [後端](../apps/api/README.md)、[前端](../apps/web/README.md)、[操作手冊](runbook.md) |
| 查來源與可重現證據 | [產品實驗資料](experiments/product-validation/README.md)、[驗證範圍](architecture/verification.md)、[獨立實驗](experiments/README.md) |

架構文件解釋系統行為；開發規範與操作手冊另列，方便依閱讀目的選擇。

## 研究與歷史

| 材料 | 位置與用途 |
|---|---|
| 官方文件、論文及方案比較 | [research/](research/README.md)，依 Agent／Memory、工作分析、工程及檢索分類 |
| 工作分析與職務說明書方法 | [guides/](guides/README.md)，保留分析指南及樣稿，不因日期較早而封存 |
| 從早期原型到現行架構的演進 | [開發沿革](reports/development-history/README.md)，按問題連回當時設計、程式與實驗 |
| 實驗發現、解法與結果 | [實驗材料](experiments/README.md)、[產品實驗資料](experiments/product-validation/README.md)；原始輸出不改寫成成功紀錄 |
| 已結案施工與舊設計 | [歷史查閱方式](history.md)；本機 `docs/archive/` 不隨 Git 發布 |

歷史材料記錄當時的設計與條件；現行系統見架構文件，方案變更的理由見 ADR。

## Repo 的其他目錄

- `apps/api/`、`apps/web/`：現行產品、測試及啟動說明。
- 獨立 RAG 程式：見 [RAG 說明](design/rag-pipeline.md)，不是 JD App 的執行依賴。
- `scripts/`、`.github/`、workspace 與 lock：開發、建置與依賴設定。
- `.research-tmp/`、`tmp/`、`output/`：不隨 Git 發布的本機實驗與輸出。
- `.worktrees/`：本機獨立工作樹。
- `node_modules/`、`.venv*`：本機依賴；`.env`、IDE 與代理設定屬本機配置，不收進報告或證據。

舊程式退役範圍與取回方式見 [ADR0079](adr/0079-target-rebuild-production-cutover.md)。封存不是刪除 Git 歷史；追查舊設計時，依[歷史查閱方式](history.md)找到原路徑與提交。
