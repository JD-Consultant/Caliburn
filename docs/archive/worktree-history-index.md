# Worktree 與歷史研究封存索引

本頁是歷史研究、設計、實驗與階段性結果的尋找入口。它不改寫任何研究內容，也不取代 [`../current-decisions.md`](../current-decisions.md)；目前施工仍只依 current decisions、Accepted ADR 與現行 code。

為了讓不使用 Git 指令、只透過 GitHub 網頁審查專案的人也能找到資料，5 個封存 tag 的已提交 `docs/` 已同步放在 [`worktree-snapshots/`](worktree-snapshots/)。另有只存在於舊本機分支的研究與實驗差異放在 [`branch-snapshots/`](branch-snapshots/)。snapshot 是可直接瀏覽的歷史副本，不是新的決策來源。

## 保留原則

**2026-10-02 整理：**教授報告已收錄於 [`docs/reports/system-architecture`](../reports/system-architecture/README.md)，完成的 checkout 已移除；接著依 Owner 授權將歷史分支收斂為封存 tag，詳見本頁下方「本機分支收斂」。新目標實驗原件、舊施工計畫與本機測試暫存的移轉見[整理紀錄](repository-organization-2026-10-02.md)。`target-cutover-candidate` 尚待 gate，工作樹仍保留；下列 2026-09 歷史紀錄不改寫。

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

## 本機分支 snapshot

| Snapshot | 原分支／主題 | 報告用途 | 使用時注意 |
|---|---|---|---|
| [`20260922-local-main-r1`](branch-snapshots/20260922-local-main-r1/) | 舊本機 `main` 的 R0／R1 professional consultant 與 task-discovery 離線切片 | 研究、ADR、提示詞、合成案例、ablation、blind grader、rubric 與測試工具 | 只作歷史與實驗證據；其中 `apps/api` 副本不屬 production |
| [`20261002-legacy-jd-research`](branch-snapshots/20261002-legacy-jd-research/README.md) | 早期 origin-main 審查／整合分支 | JD header、分析引擎、職責建議、iCAP 深度與確定性匯出研究 | 20 份不同原文的選錄，完整歷史仍在 tag；不是現行規格 |

## 建議查找順序

1. 先看 [`../current-decisions.md`](../current-decisions.md)，確認目前有效決策與文件入口。
2. 再看 [`../README.md`](../README.md) 的現行設計、計畫與研究地圖。
3. 要寫「遇到什麼問題、怎麼修正、如何驗證」時，再依上表到對應 archive tag 查看完整提交與實驗結果。
4. 實驗資料的格式、限制與保存規則以 [`../experiments/README.md`](../experiments/README.md) 為準。

## 目前分支與封存的界線

目前產品正式分支是 `main`。現行 `docs/` 已包含目前可直接查閱的 ADR、design、plans、specs 與 experiments；worktree tag 與 branch snapshot 補足尚未整理進現行入口的歷史研究與實驗資產。未來整理報告時，應新增報告或索引連結，不要把互相衝突的歷史決策直接覆蓋或混回 current 文件。

## 2026-10-02 本機分支收斂

Owner 核准在保留有用報告與完整歷史後整理本機分支。清理前基準為 `target-rebuild@916862ee`，18 個本機分支收斂為以下 4 個；沒有合併程式、推送、刪除遠端分支或改動兩個仍在使用的工作樹。

| 保留分支 | 用途 |
|---|---|
| `main` | 保留既有正式分支，這次不切換產品權責 |
| `target-rebuild` | 目前重建與交接工作 |
| `target-cutover-candidate` | `S:\caliburn-cutover` 的未完成切換候選 |
| `docs/target-rebuild-architecture-2026-09-30` | 保留已推送的架構文件分支，本次不更新遠端 |

### 已移除的本機分支名稱

先驗證每個分支 tip，再確認精確 tag 或保留分支的祖先關係，才移除分支名稱。下表的提交與全部祖先仍可回查，並非刪除研究歷史。4 個已納入的分支不另外建立多餘 tag。

| 原分支 | 原 tip | 保存位置 |
|---|---|---|
| `archive/integrate-local-opks-review-20260915` | `06ac2235` | `archive/integrate-local-opks-review-20261002` |
| `archive/integrate-reviewed-origin-main-20260915` | `26cbe906` | `archive/integrate-reviewed-origin-main-20261002` |
| `archive/review-origin-main-20260915` | `db98bfec` | `archive/review-origin-main-20261002` |
| `codex/analysis-only-agent` | `2b16d11d` | `archive/worktree-analysis-only-agent-20260918` |
| `codex/consultant-workspace-ui` | `f4acb5a4` | `archive/worktree-consultant-workspace-ui-20260918` |
| `codex/gpt6-luna-responses` | `7e47c133` | 已在 `target-rebuild` 提交歷史內 |
| `codex/memory-routing-canonical-read-spike` | `a370af94` | `archive/worktree-memory-routing-spike-20260918` |
| `codex/shared-current-jd` | `56db1249` | `archive/worktree-shared-current-jd-20260918` |
| `docs/professor-architecture` | `c5650c15` | `archive/professor-architecture-20261002` |
| `docs/r1-p0-context-representation-corrections` | `bf52f713` | 已在 `target-rebuild` 提交歷史內 |
| `feat/reviewed-job-analysis-slices` | `b37387e0` | 已在 `target-rebuild` 提交歷史內 |
| `refactor/current-only-architecture` | `9e95cdb4` | 已在 `target-rebuild` 提交歷史內 |
| `spike/langgraph-document-authority` | `b6eaa15f` | `archive/worktree-langgraph-authority-spike-20260918` |
| `tmp/save-all-aris-20260914` | `c173c602` | `archive/save-all-aris-20261002` |

[分支清單 CSV](branch-cleanup-2026-10-02.csv) 保存清理前 18 個分支的完整 SHA、當時本機記錄的 upstream 與處置；upstream 欄不代表已重新向遠端驗證分支存在。這次新增 5 個 annotated tag，重用 5 個原有 tag，其餘 4 個已由保留分支歷史涵蓋。**新 tag 與本次提交目前只在本機，不等於遠端備份。**

### 報告與實驗資料

- [報告與研究材料入口](../reports/README.md)集中介紹、圖稿、品質實驗、長訪談事故／恢復與原始資料包。
- 從兩個早期分支補收[20 份不同的 JD 研究原文](branch-snapshots/20261002-legacy-jd-research/README.md)，manifest 記錄全部 23 筆來源；相同 blob 只存一次，不改寫不同版本的結論。
- 5 個既有工作樹 snapshot 不重複複製。對 analysis-only 分支掃出的 130 個不同 blob，其對應檔案均已在原 snapshot 中存在；不覆寫整理過的歷史副本，精確位元組仍以原 tag 為準。
- 教授報告 34 檔已在前次整理收錄；原提交改以本次 tag 保護，正文不重新合併。舊整合／暫存分支中已存在路徑的歷史修訂也只保留於 tag，不覆蓋現行文件。

### 需要恢復時

先確認欲恢復的分支名尚不存在。由 CSV 的 `commit` 欄可恢復任一原分支的精確 tip：

```powershell
git branch <原分支名> <CSV中的完整commit>
```

例如教授報告：

```powershell
git branch docs/professor-architecture refs/tags/archive/professor-architecture-20261002
```

這只還原本機分支；若要恢復原 upstream，另外依 CSV 核對目前遠端後設定，不把舊記錄視為仍有效。需要 checkout 時才另建 worktree，不能覆蓋既有工作目錄。沒有執行遠端 prune 或 Git GC；原 tip 及其祖先由上述 refs 保留，恢復不依賴已刪分支的 reflog。
