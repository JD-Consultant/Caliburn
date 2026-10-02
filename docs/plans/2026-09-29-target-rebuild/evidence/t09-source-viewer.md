# T09 正式 JD 來源唯讀：整合證據

2026-09-30；本切片已接線並作有限整合驗證，T09 整體仍未完成。任務狀態以[任務表](../tasks.md)為準；產品責任見[JD 保存 §3.7](../../../implementation/jd-storage.md#37-人的正式來源回查t09-增量)及[介面 §3.1](../../../implementation/interface-and-delivery.md#31-正式-jd-來源的唯讀下鑽t09)。

## 接線與責任

- `workflows/jd_evidence.py` 只讀目前正式 JD 引用，與模型的候選工作分開；HTTP `transport/http/jd_evidence.py` 提供列表、原固定來源及舊新差異三個 GET。
- Memory 正文沿原引用快照下鑽；差異以讀取當時最新已發布 Memory 為新端點。A 的工具仍固定本 Turn 基準，不新增任意舊 Memory 全文入口。
- 原有模型及人工 caller 共用 `jd_source_queries.py` 和 `jd_source_markdown.py`，無新表、遷移、副本或第二套 diff 計算。canonical JSON schema 生成兩端型別。
- 正式稿已變則 409 重讀；跨檔、候選、引用鏈外的物件／訊息拒絕；保存缺失不是空結果。所有 GET 都不改引用或解除待核對。
- UI 預設收合、按需載入、切檔／重讀清除舊選取。Markdown 禁 raw HTML、主動連結與外部圖片；原始訪談用帶序號、角色的純文字。前端研究／測例見[UI 子切片](t09-source-viewer-ui.md)，後端等價抽取見[共享查詢](t09-shared-source-queries.md)。

## 驗證

主線於暫停交接前實測（API cwd 為 `apps/api`、Python 為 `.venv-target/Scripts/python.exe`）：

```powershell
python -m pytest tests/unit tests/contracts -q -p no:cacheprovider
# 946 passed，10.31 秒；離線，無真模型。
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
python -m pytest tests/integration/test_jd_source_http.py tests/integration/test_jd_changes.py tests/integration/test_jd_reads.py tests/integration/test_jd_shared_source_queries.py -q -p no:cacheprovider
# 13 passed，9.45 秒；隔離真 PG，無 skip。
python -m ruff check src tests
python -m mypy src
python scripts/generate_contracts.py --check
# Ruff、246 source files mypy、生成一致性均 exit 0。
```

前端主線重新執行 `vitest run src/features/source-viewer`：**2 files／20 passed**，20.11 秒；`tsc --noEmit` 通過。worker 的同版完整前端 115 tests、lint、build 與 frozen install 證據另在子切片，不與上述重複加總。主線未重跑全部 PG suite；此前 725 項結果只代表此前版本。

HTTP 測例包含候選不可見、正式完成後可見、原固定鏈、改名／差異不確認、越界原話、跨檔及舊 JD 修訂 409。獨立唯讀 reviewer 跑受影響 37 項（與以上有重疊），未找到阻擋缺陷；另以臨時反例確認列表讀後再發布新版，差異會選新發布端點。這個臨時反例尚未納入永久測試，列為後續低優先補強，不宣稱已持續回歸。

瀏覽器接現有全合成 Demo：重開仍有正式訪談 1–9、完成狀態、三項 JD 任務；來源列表可展開，選「支援每季財務庫存差異抽查」的訪談序號 8，實際讀回員工原話。此 Demo 的 JD 直接來源目前都是訪談，因此沒有冒稱已在瀏覽器驗理解→情境→原話 UI；該路徑目前有 component／HTTP／真 PG 證據。沒有新增訪談或改 Demo DB。

12:30 的「匯出目前 JD（PDF）」實際下載 `C:/Users/chenb/Downloads/job-description (1).pdf`，615,045 bytes；這次確認下載，不冒稱重新逐頁視檢。中文長短版的既有渲染證據見[T13](t13-pdf-export.md)。

介面文件三張 Mermaid 圖均以既有 renderer 成功渲染；主線視檢新增来源 sequence 圖（`.research-tmp/t09-source-diagram-2.png`），角色、固定鏈與 409 分支可讀。暫態 render 產物不提交。

## 問題與未完

- 開發 Vite 曾回舊模組，報 `SourceViewer` 無 export，而磁碟來源與 production build 正常；核對自有程序後重啟 Vite、重新載入恢復。未改業務碼處理，尚不能斷言更深的 cache 根因。一次滑鼠自動化未展開，改用原生按鈕 Enter 可展開與下鑽；未據此宣稱所有滑鼠／鍵盤／窄屏交互已驗。
- 瀏覽器尚未實測 Memory 鏈及舊新 diff、完成前真串流／重連、並行人工更新導致 409、跨 tab 全旅程；大型來源集合與 JS chunk 量測仍屬 T09／T12／T15。
- 本切片不改模型分析、Compaction、恢復或發布政策；不以唯讀 UI 完成代整體 Goal 完成。

## 2026-10-03：區分 JD 與來源變更，補上雙向比較

### 問題與採用方式

使用者指出「待核對」的位置不清楚，並追問 JD 自身也改動時如何查看。原列表逐筆引用重複同一目標標題，只有合併後的 `needs_recheck`，畫面無法區分 JD 修改或 Memory 更新；原差異入口只顯示來源鏈，訪談引用也不能查看 JD 改動。

本次改用同一結構化 JD 目標分組、各筆引用獨立呈現原因。只新增兩個讀取投影欄位；比較重用既有正式 JD 修訂與引用的 `reviewed_revision_id`，沒有新增表、diff 保存、核對命令或模型請求。JD 差異從**該筆引用最後核對**算到所選正式稿，不用上一輪切斷更早未核對的修改；来源仍以固定舊鏈對最新已發布 Memory。訪談原話不可變，只回 JD 差異。功能責任已同步至 [JD 保存 §3.7](../../../implementation/jd-storage.md#37-人的正式來源回查t09-增量) 與[介面 §3.1](../../../implementation/interface-and-delivery.md#31-正式-jd-來源的唯讀下鑽t09)。

前端分成列表分組、固定正文、差異呈現與選取協調四個元件，不在畫面推算版本，也不複製 Query cache。按需展開沿既有原生 disclosure、安全 Markdown 與視覺 token；本次查閱 [MUI Accordion](https://mui.com/material-ui/react-accordion/) 及 [TanStack lazy queries](https://tanstack.com/query/latest/docs/framework/react/guides/disabling-queries)，最後沿現有機制接線，沒有新增 UI 套件。

### 前端 RED／GREEN 與靜態檢查

新增 `SourceViewer.diff.test.tsx` 四項：同項目標題只出現一次、同名不同身分不得合併、一次動作按需讀兩類差異且不確認、訪談引用只有 JD 差異。初次執行先被舊 schema 拒絕；生成新契約後再跑，**3 failed／1 passed**：重複標題、沒有差異入口、沒有「JD 已修改」原因。此後才實作元件。

```powershell
# cwd: apps/web；使用既有 Node runtime，無安裝套件
node node_modules/vitest/vitest.mjs run src/features/source-viewer --reporter=dot
# 4 files / 31 passed
node node_modules/vitest/vitest.mjs run --reporter=dot
# 36 files / 223 passed，25.61 秒
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js src/features/source-viewer
node node_modules/vite/bin/vite.js build
```

以上命令 exit 0。變更檔案經 Prettier 格式化；build 仍提醒主 bundle 大於 500 kB（本次約 978 kB 未 gzip），沒有為本次唯讀功能增開拆包工程。Vite 首次於沙箱內啟動遇 `spawn EPERM`，升權後才執行測試；環境啟動失敗不當行為 RED。

### 合成示範與瀏覽器

本機 ignored 示範 adapter／fixture 同步兩種變更旗標及分開的 Markdown，補訪談引用的 JD 差異範例。示範來源路由測試 **14／14 passed**；這些比較文字是**固定合成範例**，不是正式版本儲存的替代實作，不能據此宣稱任意示範人工改稿的差異正確。

使用者再次授權重啟 8180 後，確認該埠舊 PID 44832 的完整指令為本 repo `demo-server.mjs`，才停止並重啟（新 PID 536）。記憶體示範編輯依授權重設；正式 PostgreSQL 與其他服務未動。

以 Codex 內建瀏覽器實際驗證 5180：同一任務的訪談及情境來源列於同一標題下；按情境的「查看差異」可獨立展開 JD 與來源；重新讀取後回到來源列表且待核對仍保留。390 × 844 窄版切 JD 分頁後，Enter 開差異、Enter／Space 展開兩區塊皆有效。頁面寬與 viewport 同為 390 px；長 diff 在區塊內水平捲動，不撐破整頁。驗完重設 viewport。

- [桌面來源分組與原因](ui-refresh/source-review-grouped.jpg)
- [窄版雙差異與鍵盤焦點](ui-refresh/source-review-narrow.jpg)

這是合成示範 UI 與元件驗證，不是真模型品質重驗；正式 API 的版本比較另由 PostgreSQL 整合測試驗證。本次未更改 A／Memory 分析或核對政策，未 commit／push。

### 正式後端與減少多餘讀取

後端切片以真 PostgreSQL 隨機隔離 schema，驗證核對基準缺失／不匹配回 503、同名他項及兄弟明細不混入、舊核對後多次修改仍保留完整淨差異、改回原文不自動核對、顯式核對才前進基準、來源刪除或同名重建不替代原物件。沒有操作正式資料或發送付費請求。

```powershell
# cwd: repo root；沿用既有 Python 與隔離測試 PostgreSQL
$py = 'apps/api/.venv-target/Scripts/python.exe'
& $py -m pytest apps/api/tests/unit/test_jd_source_rules.py apps/api/tests/unit/test_jd_source_markdown.py apps/api/tests/unit/test_import_boundaries.py apps/api/tests/contracts -q -p no:cacheprovider --tb=short
# 359 passed
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
& $py -m pytest apps/api/tests/integration/test_jd_source_http.py apps/api/tests/integration/test_jd_shared_source_queries.py apps/api/tests/integration/test_jd_source_edits.py apps/api/tests/integration/test_jd_source_persistence.py apps/api/tests/integration/test_jd_changes.py apps/api/tests/integration/test_memory_candidates.py::test_candidate_binding_tracks_new_situation_but_old_snapshot_never_changes -q -p no:cacheprovider --tb=short
# 29 passed
```

以上由後端平行切片執行；Ruff、格式及三個修改模組的 mypy 亦通過。測試集合互有覆蓋，不與下述主流程重跑加總。

審核曾發現初版列表為判斷來源變更而提前展開整條來源鏈。實作與既有發布測試確認：正式 Memory 子情境修訂變動時，發布會讓包含該引用的理解取得新修訂，即使理解正文不變。因此保留原本的 root 身分／修訂比較即足夠，已移除這段額外展開。單一理解＋一個變動情境的合成 PG 反例由 **35 SQL／4 次 Memory 正文讀取，減至 24 SQL／2 次正文讀取**；不是整體效能 benchmark。回歸護欄限制列表不得展開子正文或訪談原文，詳細鏈仍由差異入口按需讀。

主流程隨後獨立重跑 `test_jd_source_http.py`、`test_jd_source_markdown.py` 與 `test_jd_sources_target_contract.py`，**20 passed／13.29 秒**；正式生成器 `generate_contracts.py --check --schema jd-sources-view.schema.json --schema jd-source-changes-view.schema.json` 亦 exit 0。生成器新增可重複的 `--schema` 以限定同一權威流程的生成範圍，未傳時仍檢查全部；不是另一套手寫生成方式。生成比對首次遇 Windows 暫存目錄 PermissionError，沙箱外重跑通過；不為環境權限修改產品邏輯。

獨立唯讀審核未發現 Critical／Important，指出一項錯誤文案：核對基準損壞不是暫時斷線，不能只建議重試。主流程先新增測試重現，沿共用 HTTP 的既有公開錯誤碼白名單保留 `jd_review_baseline_not_available`，再由來源 feature 顯示「無法取得此引用的核對基準，尚不能比較 JD 變更。」；其他診斷內容仍丟棄，不新增錯誤框架。修正後完整前端 **36 files／224 passed，22.71 秒**。此數字取代本節前一次 223 項結果，不重複加總；後端資料比較沒有因此改動。

正式 API 程式與契約已更新並經上述隔離 PG 驗證，但本次**只重啟合成示範後端**；其他既有 Python 服務仍需在其工作安全點重啟才能載入新契約。沒有將示範站成功等同正式服務已重啟。

### 前端接手入口（2026-10-03）

提交前再次驗證：來源 HTTP／Markdown／契約三份測試 **20 passed，23.32 秒**；兩個來源 schema 的正式生成比對通過。前端預設並行全套為 223 passed／1 timeout，逾時在既有 `JdWorkCreate.test.tsx` 的長表單測例；單獨重跑兩項均通過（該測例 1.48 秒），不改測試或 5 秒上限，再以 `vitest run --maxWorkers=4 --reporter=dot` 執行完整 **36 檔／224 passed，32.27 秒**。此觀察與並行負載有關，但沒有據此確定機器資源或測試排程的根因。`tsc --noEmit`、來源 feature 與共用 HTTP 的 ESLint／Prettier、Vite build 均 exit 0。本次沒有重跑瀏覽器、模型或全套後端，沿用上節已列明的有限證據。

本次交接整理的是「來源待核對原因與 JD／來源雙差異」切片，不重新設計 UI、不啟停服務。提交留在 `target-rebuild`，不 push；提交前工作目錄仍有其他前端、推理摘要與報告改動，沒有以整批 stage、reset 或刪檔清掉它們。接手時先核對 `git status --short`，不要把本機完整畫面誤認為單一提交的成果。

1. **先讀規範**：根 `AGENTS.md`、[前端 README](../../../../apps/web/README.md)、[介面 §1.6／§3.1](../../../implementation/interface-and-delivery.md)、[程式組織](../../../implementation/code-organization.md)與[程式撰寫規範](../../../implementation/coding-standard.md)。本機尚未提交的視覺研究與證據見 `docs/research/engineering/2026-10-02-web-ui-benchmark-and-direction.md`、`t09-ui-visual-refresh.md`；新 checkout 不保證有這些檔案。
2. **從功能入口找檔案**：來源相關在 `apps/web/src/features/source-viewer`；列表、固定正文及雙差異分別由 `SourceReferenceList`、`SourceDetails`、`SourceChanges` 處理。畫面與共用樣式在 `apps/web/src/app`，不要為美化再建一份資料快取或差異計算。
3. **保持契約**：同一 JD 目標按結構身分分組；引用各自顯示原因；訪談沒有來源版本差異，但能看 JD 差異。讀取不完成核對。API schema 是唯一權威，型別由生成器產生；前後端須一起載入新契約，不接受舊 `markdown` 形狀來掩蓋錯版。
4. **分清環境**：正式開發命令由前端與後端 README 取得。`5180 → 8180` 是本機合成示範，fixture 在 ignored 的 `.research-tmp/ui-review`，重啟會重設其記憶體編輯；不能當成可搬到另一台機器的正式交付。正式 Python 服務何時重啟，先核對其用途與安全點，不為 UI 驗收停止他人的程序。
5. **保留其他工作**：`features/interview` 與 reasoning-summary 後端屬摘要接線；`app`、`features/jd-editor`、字型依賴及多數樣式屬視覺／就地編輯；`docs/reports` 與相關研究屬報告工作。這些未提交內容需各自確認範圍與證據後再提交，不混入本次來源切片。
6. **驗收按風險**：純樣式改動先驗受影響元件、鍵盤／窄螢幕、型別及 build；動到來源契約或比較基準，再跑本節列出的真 PostgreSQL 測例。合成示範成功不取代正式來源鏈測試，也不需要為 UI 改版重新付費跑模型。
