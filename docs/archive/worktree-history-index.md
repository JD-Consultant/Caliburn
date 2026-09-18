# Worktree 與歷史研究封存索引

本頁是歷史研究、設計、實驗與階段性結果的尋找入口。它不改寫任何研究內容，也不取代 [`../current-decisions.md`](../current-decisions.md)；目前施工仍只依 current decisions、Accepted ADR 與現行 code。

## 保留原則

- 已提交的研究文件、設計文件、實驗案例、模型輸入／輸出與結果都保留在 Git 歷史中。
- 舊 worktree 的提交以 archive tag 保存；刪除本機 checkout 或 GitHub 舊分支不等於刪除文件。
- 下列 tag 是歷史參考，不是目前產品的施工授權，也不能單獨推翻現行決策。
- 未提交的 `node_modules`、pytest cache、資料庫暫存檔等本機產物不屬於研究證據，未納入封存。

## Archive tag 對照

| 封存 tag | 原 worktree／主題 | 報告用途 | 使用時注意 |
|---|---|---|---|
| `archive/worktree-analysis-only-agent-20260918` | analysis-only agent | 顧問、Memory、背景整理、compaction 與 App 接線的階段研究與驗證結果 | 保留演進脈絡；不能直接當成現行 production authority |
| `archive/worktree-memory-routing-spike-20260918` | Memory routing canonical-read spike | Memory routing、長對話回查、LangMem／Luna 試驗案例與結果 | 實驗結論需配合後續 current decisions 閱讀 |
| `archive/worktree-langgraph-authority-spike-20260918` | LangGraph／consultant runtime authority spike | 舊 runtime、framework、durable authority 與資料責任的研究過程 | 部分內容已被後續決策取代，適合寫問題與取捨，不直接施工 |
| `archive/worktree-consultant-workspace-ui-20260918` | 舊 consultant workspace UI | 舊 API／Web 工作區、JD 編輯與審查流程的迭代材料 | 舊架構保留作比較，不接回現行產品 |
| `archive/worktree-shared-current-jd-20260918` | 舊 shared-current-JD implementation | 共同 JD 工作稿、人工／AI 編輯與 review 的演進材料 | 舊實作保留作歷史，不與目前 relational JD authority 混用 |

## 建議查找順序

1. 先看 [`../current-decisions.md`](../current-decisions.md)，確認目前有效決策與文件入口。
2. 再看 [`../README.md`](../README.md) 的現行設計、計畫與研究地圖。
3. 要寫「遇到什麼問題、怎麼修正、如何驗證」時，再依上表到對應 archive tag 查看完整提交與實驗結果。
4. 實驗資料的格式、限制與保存規則以 [`../experiments/README.md`](../experiments/README.md) 為準。

## 目前分支與封存的界線

目前產品工作區是 `tmp/save-all-20260914`。現行 `docs/` 已包含目前可直接查閱的 ADR、design、plans、specs 與 experiments；封存 tag 補足尚未整理進現行入口的歷史研究與實驗資產。未來整理報告時，應新增報告或索引連結，不要把互相衝突的歷史決策直接覆蓋或混回 current 文件。
