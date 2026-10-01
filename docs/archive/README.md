# 封存與歷史材料

封存表示不從這裡取得當前施工指令，不表示材料沒有研究價值。本區保留演進、失敗、報告素材與原件；有效規則回到[文件入口](../README.md)及[目前決策](../current-decisions.md)。

| 要找什麼 | 位置 |
|---|---|
| 去除重複快照、證據歸位、僅留 Git 的文件 | [去重紀錄](docs-cleanup-2026-10-02.md)、[逐檔恢復對照](docs-cleanup-2026-10-02.csv) |
| 本次 docs 分類、理由、驗證與原路徑 | [2026-10-02 文件分類紀錄](document-classification-2026-10-02.md)、[路徑／雜湊對照](document-classification-2026-10-02.csv) |
| 已明示退役或被取代的文件 | [retired-documents](retired-documents/README.md) |
| 早期獨立施工計畫 | [implementation-plans](implementation-plans/README.md) |
| 早期 Agent 實作、問題與審查報告 | [agent-task-reports](../experiments/historical/agent-task-reports/README.md)；從根目錄 `.superpowers/sdd/` 歸位 |
| 已結束的 worktree、原分支及可恢復提交 | [工作樹／分支歷史索引](worktree-history-index.md) |
| 工作樹與分支原始材料快照 | [worktree-snapshots](worktree-snapshots/)、[branch-snapshots](branch-snapshots/)；先經上一列查基準 |
| 最早的 PDF 解析與 JobIntel 訪談架構 | [3 月／5 月原件與 Git 出處](early-projects/README.md)；只收錄三份原文，不複製整個前身 repo |
| 舊 JobIntel v3 的原始文件 | [jobintel-v3](jobintel-v3/)；只供歷史追溯 |
| 本次 Repo 整理與實驗原件歸位 | [Repo 整理紀錄](repository-organization-2026-10-02.md) |
| 整理前的大索引 | [原文件索引](2026-10-02-document-index.md)；是凍結入口，不代表所有連結仍是目前路徑 |

## 保留與查閱

要看問題如何反覆被發現、研究、修改與驗證，從[開發演進素材索引](../reports/development-history/README.md)沿主題讀，不必逐個打開所有 snapshot。該索引是導讀，不另造歷史結論。

封存前須有退役、取代或結束的依據；記清楚來源提交、原路徑與接續入口。不按檔名日期或「實驗已結束」直接刪除。研究原料與實驗結果仍有用時，從 [research/](../research/README.md)、[reports/](../reports/README.md)或任務證據索引連入，不再複製正文。

歷史快照已經去重，獨有實測集中於[歷史證據](../experiments/historical/README.md)，本區留獨有設計、研究與恢復索引。遇到舊路徑先查上述對照；精確當時內容仍用對應提交／tag 讀回。搬移只改 Markdown 導航，不改寫舊決策或實驗結果；CSV／log 等原始清單保留當時路徑，不是現在可直接執行的命令。

本機 tag／提交與 ignored 封存不等於遠端備份；這次沒有 push、merge 或刪除資料庫。
