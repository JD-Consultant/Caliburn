# 關聯式 JD：隔離編輯核心

此目錄承接[新版施工計畫](../../docs/plans/2026-09-13-jd-relational-app-implementation.md)的 RS-1。已驗證八個編輯操作、完整任務建立、相依內容更正與員工／模型共用規則；框架選擇可替換，產品效果以既有六章 JD 研究為準。

**目前沒有可開啟的 App 畫面；十三表已在獨立 PostgreSQL 實際初始化及測試，完整保存 service 尚未接上。**`build_candidate` 回傳保存前的關聯資料候選，保留原 revision；不得把它當已保存結果或可反覆提交的 operation。它不讀寫 Memory／訪談、不呼叫模型、不接正式產品或舊實驗模組。

## 結構

- `contracts/jd-work.schema.json`：八個編輯工具輸入的唯一 JSON Schema。
- `contracts/jd-result.schema.json`／`jd-http.schema.json`：合法結果組合與 HTTP Problem，和輸入一樣使用標準產生器。
- `src/jd_relational/generated`：標準工具生成 Python DTO／TS 型別，禁止手改。
- `transport.py`：人工與模型轉入同一 command；兩家工具外殼不同。
- `application.py`：同一準備入口，保留候選／原錯誤，發出固定安全診斷；沒有重試或保存。
- `domain.py`：同文件／同 base refs、完整候選、正文／引用／排序／来源規則，沒有 SQL 或 SDK。
- `selection.py`：根據 App 捕捉資料作精確 UTF-16 選區替換；模型不填 offset，不猜相同文字的位置。
- `result_transport.py`／`http_results.py`：驗證觀察結果並投影；不執行寫入或自動重試，不把候選當保存完成。
- `storage/schema.py`／`migrations`：十三張關聯表與固定 Alembic migration；沒有連線自動初始化或通用 repository。
- `tests`：合成工作、格式正反例、共同操作流程、真 SDK 的離線請求捕捉。未完整任務不強迫補欄；多成果和多要求不配對。

## 重現

本單位驗證 Python 3.12.13、Node 24.19.0。使用此目錄的 lock；不修改正式 App 依賴。安裝公開套件後，測試可以全程離線且不需要模型金鑰：

```powershell
uv sync --frozen
npm ci --ignore-scripts --no-audit --no-fund
uv run --frozen --offline python scripts/generate_contract.py --check
uv run --frozen --offline pytest -q -p no:cacheprovider
node node_modules/typescript/bin/tsc -p tsconfig.json
```

若工具預設暫存目錄不可寫，將 uv 的 `--cache-dir` 指到可寫位置。`NODE_BINARY` 可指到正確的 Node 執行檔；在本機不要依賴全機舊版 npm wrapper 選中的 Node。產生器只用標準 CLI stdout，`--check` 不寫生成物。

SDK 測試使用 `httpx2.MockTransport`、固定假 key 與 `offline.invalid`，封鎖 sockets 及環境／本地帳號探索；16 個 wire 測試的 32 個 POST 都在程序內攔截。這只證明 SDK 序列化，未證明 provider 接受或模型自然選用。

### 獨立 PostgreSQL 實測

`compose.test.yaml` 僅供合成資料，固定在本機 55436；測試帳密是公開 fixture，不能用於產品。新 PG18 volume 使用 `/var/lib/postgresql`，不接舊 volume。明示建立／驗證：

```powershell
docker compose -f compose.test.yaml up -d --wait --wait-timeout 45
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
uv run --frozen --offline python scripts/init_test_database.py
$env:JD_RELATIONAL_TEST_DB='1'
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_postgres.py
Remove-Item Env:JD_RELATIONAL_TEST_DB
```

initializer 先核固定測試 DB／user／PG18.6 與表集合，再明示 migration；不清資料、不讀產品設定。真 PG tests 預設跳過；明示啟用後無法連線即失敗，不會假 PASS。一般案例回滾，新程序回讀案例留下合成已提交文件。停止測試容器用 `docker compose -f compose.test.yaml stop`，保留 volume。

## 待接責任

`Ref`／`Source`／`Selection` 為 App 注入的合成已驗讀取材料；正式 refs 發配、讀取 DTO、永久 snapshot／receipt schema、完整交易／未知結果恢復、HTTP endpoint、實際選區捕捉、畫面及顧問 runtime 在後續切片。外部結果驗證與 HTTP 純投影已完成，但不能自行證明 DB COMMIT。正式保存格式仍以十三表與 immutable revision 設計為準；此 probe 的 dict 不是另一份文件 authority。

原兩工具及來源 digest 見[首切片](../../docs/specs/2026-09-13-jd-relational-command-slice.md)；目前八工具、分層與錯誤／診斷、289 項結果及通過界線見[本次設計與結果](../../docs/specs/2026-09-13-jd-management-operations-slice.md)。

後續[結果與資料庫基礎](../../docs/specs/2026-09-13-jd-result-and-storage-foundation.md)記錄 404 離線／22 真 PG tests、首敗、獨立審查及仍未通過的保存流程；歷史測試數不累加。
