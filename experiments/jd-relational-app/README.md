# 關聯式 JD：隔離編輯核心

此目錄承接[新版施工計畫](../../docs/plans/2026-09-13-jd-relational-app-implementation.md)的 RS-1／2。已驗證八個編輯操作、完整任務建立、相依內容更正、員工／模型共用規則及真實保存；框架選擇可替換，產品效果以既有六章 JD 研究為準。

**目前沒有可開啟的 App 畫面；八操作已透過 Python service 保存到獨立 PostgreSQL 的十三表。**已接六章／歷史／原次改動查詢、單程序人工 writer 及原生 PG Saver 操作紀錄。`build_candidate` 仍只回保存前候選，`JdStorage` 在完整交易確認後才回已保存結果。跨程序 host／AI 回合、寫入 HTTP 及畫面尚未完成。此目錄不啟動模型、不接正式產品或舊實驗模組；manual checkpoint 測試驗合成 native messages 保留，沒有正式訪談／Memory 整合。

## 結構

- `contracts/jd-work.schema.json`：八個編輯工具輸入的唯一 JSON Schema。
- `contracts/jd-result.schema.json`／`jd-http.schema.json`：合法結果組合與 HTTP Problem，和輸入一樣使用標準產生器。
- `contracts/jd-snapshot.schema.json`／`snapshots.py`：v3 完整歷史格式、嚴格轉換及 canonical digest；關聯 rows 仍是 current 權威。
- `contracts/jd-read.schema.json`／`reads.py`／`read_transport.py`：生成式讀取契約、六章完整可續讀投影與兩家模型工具外殼；分頁與實際工具輸出共用 UTF-8 序列化。
- `change_reads.py`／`change_transport.py`：共用 read SSOT，將原 operation 的完整前後差異投影為唯讀、可續讀 records；兩家 SDK 離線驗工具與結果外殼。
- `contracts/jd-query-http.schema.json`／`query_http.py`／`query_api.py`：generated 查詢錯誤與 FastAPI 查詢路由；宿主注入資源，原生 lifespan／threadpool／輸入限制，沒有 mutation 路由或假的 writer owner。
- `src/jd_relational/generated`：標準工具生成 Python DTO／TS 型別，禁止手改。
- `transport.py`：人工與模型轉入同一 command；兩家工具外殼不同。
- `application.py`：同一準備入口，保留候選／原錯誤，發出固定安全診斷；沒有重試或保存。
- `domain.py`：同文件／同 base refs、完整候選、正文／引用／排序／来源規則，沒有 SQL 或 SDK。
- `selection.py`：根據 App 捕捉資料作精確 UTF-16 選區替換；模型不填 offset，不猜相同文字的位置。
- `intents.py`：固定 App 配發的操作身分、可信讀取材料與意圖摘要；`AdmittedIdentity` 保存恢復必要原身分，不含候選／refs／來源內容，不取得 writer 資格。
- `runtime_checkpoints.py`：原生 LangGraph root／直接 child，共用 Saver；只用公開 state API 保存 manual 操作身分，不 invoke 顧問或重寫對話。
- `manual_runtime.py`：實際單程序人工 writer owner；每文件 gate、native Future、保存與收尾確認、原結果恢復。沒有 HTTP waiter 假裝停止，也不把新程序查不到 Future 當死亡證明。
- `result_transport.py`／`http_results.py`：驗證觀察結果並投影；不執行寫入或自動重試，不把候選當保存完成。
- `storage/schema.py`／`migrations`：十三張關聯表與固定 Alembic migration；沒有連線自動初始化或通用 repository。
- `storage/rows.py`：九組 current 資料增量讀寫；由 caller 控制交易。
- `storage/receipts.py`／`storage/service.py`：永久回執、`JdReader` 同版唯讀及 `JdStorage` 共同保存；`reconcile_stopped` 只接受原 `AdmittedIdentity`，沒有候選重建或自動重播。
- `references.py`：ItsDangerous 2.2.0 標準 signer，固定型別、文件／版本／用途與資料集檢查；沒有自建簽章或 token registry。
- `storage/history.py`／`changes.py`：短唯讀交易取得原版或原 operation 的 base/result；穩定 IDs 比較完整欄位／關係，不用目前稿重建過去、不重播事件。
- `observation_projection.py`：只從原保存觀察發配結果 refs；投影故障不把已成功保存改判失敗，也不重跑操作。
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

SDK 測試使用 `httpx2.MockTransport`、固定假 key 與 `offline.invalid`，封鎖 sockets 及環境／本地帳號探索；16 個編輯 wire、4 個讀取 wire 與 4 個差異 wire 測試各兩次 POST 都在程序內攔截。這只證明 SDK 序列化，未證明 provider 接受或模型自然選用。

### 獨立 PostgreSQL 實測

`compose.test.yaml` 僅供合成資料，固定在本機 55436；測試帳密是公開 fixture，不能用於產品。新 PG18 volume 使用 `/var/lib/postgresql`，不接舊 volume。明示建立／驗證：

```powershell
docker compose -f compose.test.yaml up -d --wait --wait-timeout 45
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
uv run --frozen --offline python scripts/init_test_database.py
uv run --frozen --offline python scripts/init_test_runtime.py
$env:JD_RELATIONAL_TEST_DB='1'
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_postgres.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_rows.py tests/test_storage_service.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_history.py tests/test_read_storage_integration.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_query_postgres.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_operation_lookup.py tests/test_manual_runtime_postgres.py
Remove-Item Env:JD_RELATIONAL_TEST_DB
```

initializer 先核固定測試 DB／user／PG18.6 與表集合，再明示 migration；不清資料、不讀產品設定。真 PG tests 預設跳過；明示啟用後無法連線即失敗，不會假 PASS。直接 SQL／mapper 一般案例回滾；service 與新程序回讀案例保留合成已提交文件，不清空 volume。停止測試容器用 `docker compose -f compose.test.yaml stop`，保留 volume。

`init_test_runtime.py` 另於 `jd_runtime_test` 明示執行官方 `PostgresSaver.setup()`，四張原生 checkpoint 表不計入十三 JD 表；public JD/Alembic 不變。普通 runtime 建立及 fixture 都不初始化資料庫，缺 schema 直接失敗。此 schema 名稱與公開測試帳密只供合成驗收。

查詢新程序案例只啟動該測試自己的 loopback server，以 STOP／EOF 關閉，保存 PID／退出紀錄於 repo `.research-tmp/jd-query-http-<uuid>`；不是日常產品啟動器。Windows venv launcher 與 Python server 可能不同 PID，依父子身分核對，不能按端口停止別人程序。Starlette TestClient 目前有一個第三方 AnyIO alias 棄用警告，結果稿保留此限制。

## 待接責任

目前／歷史 item、field、container、section 與觀察 refs 已發配／驗證，`command_context` 用同版讀取材料重核可寫用途、存在性與欄位摘要。來源查核仍是注入 callback，未接實際 source owner；讀取回 `readability=not_checked`。瀏覽器選區發配仍未完成，此接點明示拒絕 selection，不把 field ref 當選區。

`WriterAuthority` 已由單程序 `ManualRuntime` 的實際 writer 提供，且真 PG 驗證；跨 App 程序的互斥／退出證據仍待接，持久 orphan 不能自動宣稱已停止。兩個查詢 HTTP 只使用 `JdReader`／`HistoryReader`，尚未開 mutation。簽章 key／dataset 仍由宿主注入；同 key 新程序不代表持久設定或備份还原世代已完成。寫入 HTTP、畫面、人工變更通知及實際顧問回合尚待接線。

還原／整輪撤回、更名／封存與恢復、autosave 暫存及維護仍未完成。保存 service 能提供真 DB 觀察；外部結果／HTTP mapper 必須由接線層以該觀察投影，不能自行宣稱 COMMIT。正式格式沿十三表、v3 snapshot 與永久回執，沒有另一份文件權威。

原兩工具及來源 digest 見[首切片](../../docs/specs/2026-09-13-jd-relational-command-slice.md)；目前八工具、分層與錯誤／診斷、289 項結果及通過界線見[本次設計與結果](../../docs/specs/2026-09-13-jd-management-operations-slice.md)。

歷史[結果與資料庫基礎](../../docs/specs/2026-09-13-jd-result-and-storage-foundation.md)、[共同保存交易](../../docs/specs/2026-09-13-jd-transaction-service-slice.md)、[同版讀取](../../docs/specs/2026-09-13-jd-read-change-implementation.md)及[查詢 API 與恢復身分](../../docs/specs/2026-09-13-jd-query-api-and-recovery-identity-slice.md)保留當時結果。最新測試、首敗、獨立審查及下一工作見[人工持久執行流程](../../docs/specs/2026-09-13-jd-manual-runtime-slice.md)；各批數字不累加。
