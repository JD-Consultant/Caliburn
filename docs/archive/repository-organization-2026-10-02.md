# Repo 分類與封存紀錄（2026-10-02）

Owner 要求整理雜亂檔案、封存不再使用的材料、將實驗成果收進文檔，並清理已結束的 worktree。本次基於 `target-rebuild@f2e1c301`，不改產品程式、驗收條件、模型或正式入口，不啟停服務、不呼叫付費模型、不 push／merge。

本頁按發生順序追加紀錄；以上及下列早期段落的「未切換／仍保留候選」是當時狀態。ADR0079 放行後的最新收尾見[正式切換後收尾](#正式切換後收尾2026-10-02)，不反向改寫先前證據。

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

## 根目錄快取與測試暫存整理

Owner 接著指定整理截圖中的根目錄快取／暫存。本輪基準 `target-rebuild@649d9f93`，只處理已逐項列出的根目錄子資料夾，不清空 `.research-tmp`、不啟停程序、不呼叫模型、不改產品程式。

| 類型 | 處理結果 |
|---|---|
| 舊 pytest 工作區／cache、mypy／Ruff／Turbo cache、npm cache、舊 pnpm store | 32 個根目錄資料夾移入 `.research-tmp/archive/2026-10-02/root-artifacts/`，保留原名；包含權限受限的測試資料，不把列舉失敗誤判為空目錄 |
| `.superpowers/sdd/` 已追蹤報告 | 8 份移入 [agent-task-reports](../experiments/historical/agent-task-reports/README.md)，正文位元組不變 |
| `.superpowers/` 其餘本機工作材料 | 作為第 33 個目錄移入同一本機封存；不公開未審查的 diff／本機日誌 |
| 20 個 `.uv-cache*` | 用 `uv cache clean --cache-dir <逐項確認的絕對路徑> --no-config --offline --no-progress` 清理；112,285 個快取檔案，原邏輯大小 1,745,950,428 bytes（約 1.63 GiB）。不是磁碟實際釋放量保證，因檔案可能有硬連結 |

### 安全界線與查核

- 先解析全部來源與目的地，限制為 repo 根目錄指定子項與本次封存目錄；遞迴檢查沒有 reparse point，不靠未核實的萬用字元刪除。
- 程序清單未查得引用這批根目錄路徑的命令；這不等於完整 open-handle 證明，因此不強制解鎖。uv 使用 `UV_LOCK_TIMEOUT=2`，沒有 `--force`，完成後還原該程序環境設定。uv 清理遵循其[官方 cache safety／clean 契約](https://docs.astral.sh/uv/concepts/cache/#clearing-the-cache)，不用手工刪除內部 bucket。
- `node_modules/.modules.yaml` 指向 `S:\.pnpm-store\v11`，不是這次移走的 `S:\caliburn\.pnpm-store`。現用 `node_modules`、虛擬環境、全域 uv cache 與 repo 外 pnpm store 保留。
- 33 個封存目錄內 2,031 個檔案逐檔核對搬移前後 SHA-256；8 份搬入文件區的報告另外核對。根目錄本次指定的 52 個 cache／pytest 子項及 `.superpowers` 均不再散落原處。
- 原 PostgreSQL、服務程序、`.env`、`.agents`、`.claude`、`.worktrees`、現存實驗證據與其他研究暫存不在清理範圍。沒有為此重跑產品旅程或宣稱產品驗收通過。
- 收尾重新核對 2,031 份封存檔案與 8 份報告的雜湊／檔數、全部指定根目錄路徑已移除；5 份入口文件的相對連結與錨點檢查無失效。歷史報告保留當時連結，不宣稱全部舊連結仍可用。

### 恢復與保存

本機封存內的 `inventory.csv` 記錄原位置、檔數、大小及處理方式；`preserved-files-sha256.csv` 記錄保留檔案雜湊；`tracked-reports.csv` 記錄 8 份報告新舊路徑。還原封存資料時，先核對原位置沒有後續新產物，再逐項搬回，不整批覆蓋。

uv cache 已清除，不是可原樣還原的封存；需要時由 uv 重新下載／建置，專案 lockfile 與已安裝依賴沒有因此移除。其他舊快取與測例只是搬移，沒有刪掉。ignored 封存不等於遠端備份，報告需要的材料仍應經篩選收進版本管理。

### 後續暫存放置方式

- 新的任務特有暫存使用 `.research-tmp/<清楚的任務名稱>/`，不再在根目錄建立 `.pytest-tmp-<task>`、`.uv-cache-<task>` 等散落目錄。
- 依賴快取優先沿用工具目前設定；若確有隔離或同磁碟需求，指定 `.research-tmp` 下的專用 cache，不改動全域設定，也不把現用 cache 目錄直接搬走。
- pytest `--basetemp` 只指向獨占的測試暫存子目錄，不能指向共用 `.research-tmp` 或封存根，因為 pytest 會清理指定目錄。這遵循 [pytest 暫存目錄文件](https://docs.pytest.org/en/stable/how-to/tmp_path.html#temporary-directory-location-and-retention)。
- 有用的研究結論、測試結果與 Agent 報告寫入相應 `docs` 責任文件；未審查的執行狀態留本機。`.gitignore` 補上 `.uv-cache*/`、`.superpowers/` 防止新暫存誤提交，不把 ignore 當成備份或清理。

## 全專案四類處置清單

本輪接續基準為 `target-rebuild@def9c248`，範圍是目錄用途、文件路由與可保全的舊測試暫存。不是重做產品驗收、改變正式權責，或在整理時順帶重構程式。另一個 `target-cutover-candidate` 工作樹仍在使用，本輪沒有讀取、修改或清理它。

### 需要保留

| 範圍 | 理由與入口 |
|---|---|
| `apps/api`、`apps/web` | 新目標實作；任務與未驗範圍以[任務表](../plans/2026-09-29-target-rebuild/tasks.md)為準 |
| `experiments/jd-relational-app`、`packages/consultant-memory` | T18 尚未切換，本分支仍依 ADR0077 使用；不能因舊架構或 `experiments` 名稱而刪除 |
| `apps/pdf-to-json`、`apps/ocs-indexer` 與 RAG 契約套件、908 份 RAG JSON | 獨立 RAG 的解析、索引、校準與契約消費用途仍存在，不接回 JD 也不等於無用 |
| 目標架構、工程／Tool 規範、工作分析與 JD 指南、有效 ADR／任務 | 仍供實作及驗收；由[文件導覽](../README.md)分層，不複製成另一套規則 |
| 獨有研究、失敗紀錄、實驗原件、演進與教授報告 | 用於說明「問題如何發現、研究、修正、驗證與留下限制」；沿[開發演進索引](../reports/development-history/README.md)查找，包括 Memory／context、檢索、JD 與工程驗證 |
| `scripts`、`.github`、workspace／lock、正式契約及生成物 | 根命令、CI、套件資源仍有依賴。生成檔即使沒有直接 App consumer，也須核對 generator／exports 後再退役 |
| DB、`.env`、私人設定、現用依賴與工作樹 | 不是文件雜物；不為目錄整齊改動或公開 |

### 可封存，保留可恢復性

| 範圍 | 本輪處理 |
|---|---|
| 9 族已結束的舊合成整合測試工作目錄 | **743 目錄、16,215 檔案已移至本機封存**，詳下節；不是刪除或釋放磁碟空間 |
| PDF 工具的 `ARCHITECTURE.md`、`SETUP_COMPLETE.md` | 原位保留並明示歷史初始設計／建置紀錄，導向現用 README；避免舊「待實作」與不存在的模組位置誤導施工 |
| 已完成計畫與歷史架構原件 | 先前分類、去重成果沿用；仍有獨有證據的不再刪除、不再複製一份。追溯入口見[封存導覽](README.md) |

### 多餘或可精簡，不一律立刻刪除

| 項目 | 判斷與處置 |
|---|---|
| 整套重複快照、撤回計畫／純退役通知 | 前輪已核對去重 2,396 份、7 份僅留 Git；恢復依[既有去重對照](docs-cleanup-2026-10-02.md)，不是本輪新增刪除 |
| `apps/pdf-to-json/tests/conftest.py` 的 `expected_output_dir`、`tmp_output_dir` | tracked App 程式查核只見定義，屬刪除候選；本輪保留，待該 App 測試維護時移除並驗證收集／受影響測試，不為整理擴大到程式變更 |
| 前端生成工具型別、OCS TypeScript 生成型別 | 暫未找到直接 App consumer，但仍有生成／匯出契約；**用途待核，不是已確認可刪** |
| `.research-tmp` 根層圖檔／JSON／PDF 等疑似副本 | 依檔案大小及 SHA-256 對比 779 份 tracked 圖／資料，未找到完全相同副本；保留。檢查不是涵蓋全部遞迴暫存 |
| `tmp`、`output` 與其他研究暫存 | 仍有未逐項判定的輸出、PDF、瀏覽器／執行資料；先保留，不把「ignored」當成無價值或可公開的證據 |

### 需要更新

| 項目 | 狀態 |
|---|---|
| 根 `AGENTS.md` 將新目標概稱未完成施工 | 已改為實作／驗收中並路由任務表；沒有宣告 T18 完成 |
| `apps/api/docs/README.md` 仍稱整個 API 已移除 | 已替換為新後端文件入口；舊原文可由 `def9c248` 取回，不再要求維護不存在的 `app/core` 等模組 |
| PDF／Indexer README 的契約連結實際指向清理紀錄 | 已直連來源欄位語意與機器 schema，區分 RAG 契約與 JD 著作契約 |
| `current-decisions.md` 的 P3 `App／Saver` 錨點 | 已修正連結，不改歷史實驗內容及結論 |
| `calibrate_match.py` 的 `npm run infra` 提示 | 只更新 docstring 為根 `pnpm rag:up`；未啟動容器、未跑校準、未改執行邏輯 |
| `packages/ocs-contract/scripts/check-codegen.sh` | **待修程式缺陷**：直接生成至 tracked 檔，差異分支又 `git checkout --`，會覆寫未提交修改。本輪只在[套件入口](../../packages/ocs-contract/README.md)加警告，未執行腳本；後續應暫存生成再比較，驗證檢查前後工作檔不變 |
| 正式入口、新舊程式退役、教授報告切換後的現況 | 交給原 T18／報告維護流程，不在清理分支搶先改狀態或改別人的工作樹 |

## 舊合成整合測試目錄封存

本輪將下列「固定前綴＋32 位 hex」目錄移入 `.research-tmp/archive/2026-10-02/closed-integration-fixtures/`：

| 前綴 | 目錄數 |
|---|---:|
| `jd-ai-host-recovery` | 183 |
| `jd-configured-host` | 174 |
| `jd-host-recovery` | 123 |
| `jd-b-recovery` | 98 |
| `jd-ui-gate` | 61 |
| `jd-manual-http` | 31 |
| `jd-query-http` | 30 |
| `jd-catalog-http` | 25 |
| `jd-layered-recovery` | 18 |

### 如何判定與保全

- 沿 `experiments/jd-relational-app/tests/` 的 `test_ai_host_restart_postgres.py`、`test_configured_host_native.py`、`test_host_recovery_postgres.py`、`test_background_new_process_postgres.py`、`test_layered_background_new_process_postgres.py`、`test_catalog_native_http.py`、`test_manual_http_postgres.py`、`test_query_postgres.py` 與 `support/` 建置路徑查回用途；不是按日期猜成垃圾。
- 743 個目錄及其內容全部早於 2026-09-25，最新檔案寫入時間為 2026-09-23 21:31:02（UTC+8）。程序 command line 未見這批路徑；這不等於完整 open-handle 證明，不強制解鎖或終止任何程序。
- 來源、目的地及祖先皆核對絕對路徑與 reparse point；禁止越出本機暫存範圍，拒絕混有 `PG_VERSION`／`.env` 的目錄，不覆蓋既有封存。一般沙盒部分 ACL 不可列舉時，使用核准權限檢查，沒有將讀取失敗當成空目錄。
- 搬移前後逐檔 SHA-256 與檔數一致；16,215 檔、937,334,315 bytes。這是保留內容的邏輯大小，不是釋放空間或磁碟占用的保證。
- 內含合成設定及瀏覽器狀態，**本機保存、不直接提交或當作可公開報告原件**。真 DB、現用服務、付費實驗及其他未核實暫存未動。

### 恢復與驗證界線

本機封存內 `relocations.csv` 保存逐目錄新舊位置、檔數與大小，`sha256.csv` 保存逐檔原路徑、新路徑與雜湊。需恢復時先確認原位置沒有新測試產物，按清單逐項還原，不覆蓋。ignored 封存仍不是遠端備份。

文件查核分別看分類／連結與程式入口／依賴：140 份文件的唯讀掃描只找到一個現用入口錨點需修正；已明示歷史的四處舊路徑不猜接到新版，HTML `id` 造成的錨點誤報人工排除。這是本機導覽檢查，不是外部網站有效性或全量歷史完整性驗證。

收尾另檢查本輪 10 份 Markdown 的相對連結與錨點：檢查器報出的三處錨點均有既存 HTML `id`（兩個不同目標），人工核對有效；其餘無失效。差異空白檢查通過，封存清單重讀確認全部 743 個目的地存在、原目錄已移走。

本輪不重跑產品套件、真 PostgreSQL 或真模型旅程。文件更正與 docstring 提示不改產品行為；可整理的範圍已處理，待修程式、未審查的私有暫存及 T18 不冒稱完成。

## 正式切換後收尾（2026-10-02）

### 範圍與結果

Owner 確認新 App 已依 [ADR0079](../adr/0079-target-rebuild-production-cutover.md)成為唯一正式產品、其他工作已收尾後，從 `target-rebuild@b487e883` 繼續整理。這次不重判 T01–T18、不改產品規則、不新增功能，也不把交接列出的驗收缺口抹成已通過。

| 範圍 | 處置與保留 |
|---|---|
| 候選工作樹及分支 | `S:\caliburn-cutover`／`target-cutover-candidate` 已清除；tip `9438347c` 及祖先仍在主線，見[工作樹收尾與恢復](worktree-history-index.md#切換後候選工作樹收尾2026-10-02) |
| 候選 ignored 產物 | 36 組依賴、快取、建置輸出移入本機封存，不混入 Git 報告 |
| 兩個退役程式區域 | `experiments/jd-relational-app` 與 `packages/consultant-memory` 的 126 組非 tracked 殘留封存；16 份 tracked README、研究筆記、Skill 與指南原文保留，雜湊未變 |
| 本機設定類檔案 | 舊合成測試中的兩份 `host.v1.dpapi` 隨原測試目錄封存、不公開；掃描不搬 `.env` 或 PostgreSQL cluster。現用 DB、volume、秘密不動 |
| 程序 | 核對埠、PID、啟動時間、父程序及入口後停止 8103／8104；保留 PostgreSQL 55439、未列入本次交接清理的 8101／8102；8100／5173 未啟動 |
| 現用文件 | 修正前端 README、design／specs／退役入口、產品概念中仍把 ADR0077 當現況或稱未切換的路由；歷史正文保留。實驗發現、教授報告與原始證據不刪改 |

### 可恢復封存與查核

封存根：`S:\caliburn\.research-tmp\archive\2026-10-02\post-cutover`，只在本機且受 Git ignore 保護。

- `candidate-worktree/`、`retired-local-residue/` 保存上述 162 組原產物；`relocations.csv` 列精確新舊路徑，搬移前核對來源／目的地及祖先，不跨越 reparse point、不覆蓋既有封存。
- `sha256.csv` 覆蓋 **1,838 個非依賴檔、487,294,882 bytes**，搬移後逐檔一致；`.venv`／`node_modules` 以整目錄搬移，不宣稱逐檔雜湊驗證依賴。這些數字不包含依賴，也不表示釋放了磁碟空間。
- `preserved-tracked.csv` 核對 16 份歷史檔搬移前後一致。原始測試輸出可能包含本機設定與瀏覽器狀態，不直接提交或當作公開報告原件。
- 封存可按清單復原到**未被重新使用**的原位置；不可覆蓋新資料。它不是遠端備份。舊程式則仍可用 `git show 6ad33bcb:<路徑>` 回查，不從本機編譯快取恢復程式。

### 切換後本機依賴

交接所指的舊 `apps/api/.venv` 實為 Python 3.13；確認未被 8101／8102 使用後，另移入 `main-dependencies/`，位置記於 `dependency-relocations.csv`。兩個保留服務仍使用 `apps/api/.venv-target`，不改該環境。

用現成的 Node 24.19.0、pnpm 12.5.1、uv 0.12.20、Python 3.14.7，依原 lock **離線同步**新正式環境：後端建立 `apps/api/.venv`，前端移除不再屬於 workspace 的 67 個依賴。第一次 pnpm 在一般沙盒因舊 `.pnpm` ACL 被拒，核准權限後同命令成功；不是套件版本或產品缺陷，沒有改 lock 或全域 PATH。

本機正確工具位置如下，僅作這次操作紀錄，不取代 README 的可攜安裝要求：

- Node：`C:\Users\chenb\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`
- pnpm：`S:\caliburn\.research-tmp\pnpm-12.5.1\package\bin\pnpm.mjs`（以上述 Node 執行）
- uv：`S:\caliburn\.research-tmp\bin\uv.exe`

預設 shell PATH 仍可能選到舊工具，執行根命令前須依 README 核對版本；不自動變更使用者的全域工具設定。沒有啟動 App、資料庫遷移或付費模型。產品剩餘缺口仍由[實驗發現報告](../reports/experiment-findings.md)與各任務證據維護，不另造「已全部驗過」的結論。

### 本輪驗證與限制

- 搬移後重讀清單：162 組目的地存在、原位置已移走；候選工作樹不存在，16 份 tracked 歷史內容不變。
- 七份變更 Markdown 的相對連結／錨點檢查：0 失效；`git diff --check` 通過。
- 新後端環境 `uv pip check`：87 個套件相容。一般沙盒的預設 uv cache ACL 不可讀，明確指定本輪沿用的 `.research-tmp/uv-cache` 後通過。
- 根 `pnpm build`：契約生成一致性、TypeScript 與 Vite 靜態建置 exit 0。第一次因沙盒下 Python 臨時目錄 ACL 被拒，核准權限重跑同一命令後通過；沒有為了通過而修改生成檔或規範。
- 建置仍有單一 JS chunk 超過 500 kB 的效能警告（minified 952.67 kB、gzip 284.91 kB）。它不是建置失敗；是否拆包屬後續效能工作，不在整理任務中擴大改碼。
- 以上不驗真模型品質、DB 恢復或 UI 使用旅程，不取代既有驗收證據。B 壓縮後發布、新入口真模型短旅程、Memory 失敗再准入政策等交接事項仍按原文件狀態保留。
