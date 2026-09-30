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
