# Repo 分類與封存紀錄（2026-10-02）

Owner 要求整理雜亂檔案、封存不再使用的材料、將實驗成果收進文檔，並清理已結束的 worktree。本次基於 `target-rebuild@f2e1c301`，不改產品程式、驗收條件、模型或正式入口，不啟停服務、不呼叫付費模型、不 push／merge。

## 分類結果

| 類別 | 保存位置與實際動作 |
|---|---|
| 日常閱讀入口 | [文件／Repo 導覽](../README.md)按用途分類；[任務表](../plans/2026-09-29-target-rebuild/tasks.md#收尾分類與下一步)區分先核對、待診斷、可延後與最後交付；不另造進度系統 |
| 原文件索引 | [整理前快照](2026-10-02-document-index.md)保留舊入口全部內容，僅調相對連結與搬移路由；新入口不再混列所有歷史方案 |
| 8 份早期施工計畫 | `docs/superpowers/plans/` → [archive/implementation-plans/](implementation-plans/README.md)；原文位元組不變，更新指向它們的 Markdown 連結；過去命令中的舊路徑不改寫 |
| 教授報告與圖稿 | 從 `docs/professor-architecture@c5650c152527bc3cf7d309eddc1e4962e3e0a5e4` 收錄 [system-architecture/](../reports/system-architecture/README.md) 全部 34 檔；搬入時逐檔雜湊相同，只另在入口加收錄說明，不改圖稿、結論與基準 |
| 合成實驗原件 | `.research-tmp/eval/` 的 84 個 JSON／JSONL／PDF／PNG 歸位：56 個移到[執行／品質探測資料包](../plans/2026-09-29-target-rebuild/evidence/data/runtime-probes-2026-10-01/README.md)，28 個與[既有資料包](../plans/2026-09-29-target-rebuild/evidence/data/instruction-experiments-2026-10-01/README.md)完全相同，核對後移除暫存副本；每個原位置、保存位置、大小與雜湊見資料包 `relocations.csv` |
| 5,659 個舊單元測試目錄 | `.research-tmp/jd-gate-unit-*`（3,614）與 `jd-chat-helper-unit-*`（2,045）移到 `.research-tmp/archive/2026-10-02/unit-fixtures/`；15,470 個檔案搬移前後 SHA-256 一致。是既有合成測例的隨機暫存，不是新研究結論，不整批加入 Git |

本機封存根為 `S:\caliburn\.research-tmp\archive\2026-10-02`，仍受 Git ignore 保護。`unit-fixtures-relocations.csv`、`unit-fixtures-sha256.csv` 記原／新位置與檔案雜湊；`legacy-plan-relocations.csv` 記舊計畫原路徑與雜湊。這些本機暫存封存**不等於遠端備份**；報告需要的合成實驗原件已另收進受版本管理的 `evidence/data/`。

## 工作樹與恢復

| 原工作樹／分支 | 結果與理由 |
|---|---|
| `S:\caliburn\.worktrees\professor-architecture`／`docs/professor-architecture` | 已移除 checkout；後續分支整理將原提交保存在 `archive/professor-architecture-20261002` tag。移除前確認乾淨、沒有未追蹤／ignored 遺留、沒有查得使用此路徑的程序，且報告 34 檔完整收錄。10 個 ignored 圖片／渲染腳本保留於本機封存根的 `professor-architecture-c5650c15/.research-tmp/`；舊腳本含當時工具路徑，只作歷史，不直接當目前可攜指令 |
| `S:\caliburn-cutover`／`target-cutover-candidate@5bccf4fb` | 保留；這是尚待驗收與正式切換的候選，不是已結束工作 |
| `S:\caliburn`／`target-rebuild` | 保留主開發工作樹；本次不重置或切換分支 |

若需重新開啟原教授報告分支，確認分支名及目的地均不存在後可在 repo 根目錄執行（不須合併主分支）：

```powershell
git worktree add -b docs/professor-architecture .worktrees/professor-architecture refs/tags/archive/professor-architecture-20261002
```

分支恢復的是原已提交報告；本次收錄說明與之後編修仍在主工作分支的 `docs/reports/`。單元測試暫存可依本機 CSV 逐項搬回；還原前須核對目的地沒有新檔，不覆蓋後續測試產物。

## 未動的範圍與理由

- 現行正式產品、新目標程式、依賴、有效規格與指南不因名稱或日期被判成無用；正式退役仍走 T18。
- PostgreSQL 目錄、`.env`、私人設定、依賴與其他未逐項確認的研究暫存保留；沒有把整個 `.research-tmp` 打包當成可公開資料。
- `.research-tmp/eval/` 腳本、日誌及子目錄保留。兩個 `long-procurement-1-resume-0004` 日誌讀取時仍被占用，未強制搬動；沒有關閉持有它們的程序。
- 舊單元測試前綴經測試程式核對，使用 UUID 每次另建；本批最近修改在 2026-09-24，程序清單未查得 pytest 或這兩個前綴使用者。僅此兩族做本機集中封存，沒有改測試程式。
- 原始實驗資料只做搬移、去除已核對的相同副本與分類，不重算成績、不補造結果；JSON／JSONL 已解析，敏感模式掃描未命中。這不保證其他未盤點暫存都可公開。

本次清理成果是「能找到、可回查、保留歷史、減少散落目錄」，不是宣告整個 repo 所有檔案都已審完或產品已驗收。

## 驗證與已知限制

- 新入口、封存說明、計畫路由、教授報告與 8 份搬移計畫共 29 份 Markdown：相對檔案連結及錨點檢查通過。證據索引覆蓋本目錄全部 38 份既有紀錄。
- 84 份實驗移轉對照逐項驗 SHA-256，保存位置可讀、原暫存副本已移除；56 個新原件另有 `SHA256SUMS.txt`。15,470 個舊單元測試檔案及教授報告搬移前後亦核對雜湊。
- 8 張既有 SVG 可解析為 XML，對應 PNG 檔頭有效；圖稿未重畫，本次不宣稱重新做過每張視覺驗收。
- 6 份受路由調整影響的長歷史文件原檢查出 101 個失效連結：84 個指向舊 `analysis-only-agent` worktree，已改連**確實存在且錨點可解析**的歷史 snapshot。剩餘 17 處逐項比對 `f2e1c301`，確認整理前已存在：`current-decisions.md` 11 個失效錨點、`current-job-analysis-analysis-flow.md` 1 個舊設計路徑、2026-08-11 provider 研究 3 個舊程式／ADR 路徑、2026-08-12 產品流程研究 2 個舊程式路徑。本次沒有猜測替代來源；不是這次移轉造成的新斷鏈。
- Git 將 8 份計畫辨識為 100% 相同的搬移；56 個新原件的 staged blob 與工作目錄原始位元組相同，沒有被換行轉換。T01–T18 勾選逐項比對原提交，未變更。
- 本次沒有產品程式變更，不重跑產品測試、重啟服務或新增付費實驗。後續產品驗收沿原 T16–T18，不因整理而增減要求。

## 後續本機分支整理

Owner 接著核准整理本機分支，基準為上述整理提交 `916862ee`。18 個本機分支保留 4 個使用中的／交付入口分支，移除 14 個歷史分支名稱；5 個新增 tag、5 個既有 tag 與 4 個已納入保留分支的歷史保護全部原 tip。逐項清單與恢復方法見[歷史索引](worktree-history-index.md)，沒有推送、合併或刪除遠端分支。

補收的早期 JD 研究共 23 筆來源、20 份不同原文，透過 manifest 對回原 Git blob；新增[報告材料入口](../reports/README.md)串起既有介紹、圖稿、實驗、失敗與修正紀錄，不再複製當前驗收狀態。

保存核對曾發現匯出檔雜湊不同：`core.autocrlf=true` 使 Git archive 轉換換行；以 Git text normalization 驗證是同一內容，再用單次 `git -c core.autocrlf=false archive` 匯出，20 份原件均與原 blob 相同。未修改全域／repo Git 設定，只為這批原件加精確的 `-text` 保存規則。敏感模式初掃把 `task-...` 誤認為 `sk-...`，加入前綴邊界後 20 份文件無匹配；這是模式檢查，不宣稱完整私人資料稽核。

原件保留歷史路徑與連結；選錄未含完整舊 checkout，入口已說明如何從 tag 查完整語境。本次只驗證新整理入口的本地連結與來源完整性，不聲稱全部歷史連結可用。未改動產品程式或重跑產品測試。

收尾核對：6 份整理入口的相對連結檢查通過；原 18 個分支 tip 都可取回，14 個已移除分支的 tag／祖先關係逐項成立，剩餘 4 個分支符合清單。20 份收錄原件在 index 中的 blob 亦逐檔等於原來源。全量 `git diff --cached --check` 指出 3 份歷史計畫原本就有檔尾空白行；為保留原件不修改它們，排除歷史原件後，本次撰寫的索引與保存規則差異檢查通過。
