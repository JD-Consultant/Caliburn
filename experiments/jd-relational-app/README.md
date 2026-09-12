# 關聯式 JD：隔離編輯核心

此目錄承接[新版施工計畫](../../docs/plans/2026-09-13-jd-relational-app-implementation.md)的 RS-1／2。已驗證八個編輯操作、完整任務建立、相依內容更正、員工／模型共用規則及真實保存；框架選擇可替換，產品效果以既有六章 JD 研究為準。

**目前沒有可開啟的 App 畫面；八操作已透過 Python service 保存到獨立 PostgreSQL 的十三表。**已接同版六章讀取、可驗證定位、歷史材料及確切差異；`build_candidate` 仍只回保存前候選，`JdStorage` 在完整交易確認後才回已保存結果。HTTP、實際 writer 資格／停止證明及顧問接線尚未完成。此目錄不讀寫 Memory／訪談、不呼叫模型、不接正式產品或舊實驗模組。

## 結構

- `contracts/jd-work.schema.json`：八個編輯工具輸入的唯一 JSON Schema。
- `contracts/jd-result.schema.json`／`jd-http.schema.json`：合法結果組合與 HTTP Problem，和輸入一樣使用標準產生器。
- `contracts/jd-snapshot.schema.json`／`snapshots.py`：v3 完整歷史格式、嚴格轉換及 canonical digest；關聯 rows 仍是 current 權威。
- `contracts/jd-read.schema.json`／`reads.py`／`read_transport.py`：生成式讀取契約、六章完整可續讀投影與兩家模型工具外殼；分頁與實際工具輸出共用 UTF-8 序列化。
- `src/jd_relational/generated`：標準工具生成 Python DTO／TS 型別，禁止手改。
- `transport.py`：人工與模型轉入同一 command；兩家工具外殼不同。
- `application.py`：同一準備入口，保留候選／原錯誤，發出固定安全診斷；沒有重試或保存。
- `domain.py`：同文件／同 base refs、完整候選、正文／引用／排序／来源規則，沒有 SQL 或 SDK。
- `selection.py`：根據 App 捕捉資料作精確 UTF-16 選區替換；模型不填 offset，不猜相同文字的位置。
- `intents.py`：固定 App 配發的操作身分、可信讀取材料與意圖摘要；不取得 writer 資格或驗外部 token。
- `result_transport.py`／`http_results.py`：驗證觀察結果並投影；不執行寫入或自動重試，不把候選當保存完成。
- `storage/schema.py`／`migrations`：十三張關聯表與固定 Alembic migration；沒有連線自動初始化或通用 repository。
- `storage/rows.py`：九組 current 資料增量讀寫；由 caller 控制交易。
- `storage/receipts.py`／`storage/service.py`：永久回執型別、建立查回、同版讀取、共同保存交易及停止後只記失敗的收尾接點；沒有自動重播。
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

SDK 測試使用 `httpx2.MockTransport`、固定假 key 與 `offline.invalid`，封鎖 sockets 及環境／本地帳號探索；既有 16 個編輯 wire 測試的 32 個 POST，以及 4 個讀取 wire 測試的 8 個 POST 都在程序內攔截。這只證明 SDK 序列化，未證明 provider 接受或模型自然選用。

### 獨立 PostgreSQL 實測

`compose.test.yaml` 僅供合成資料，固定在本機 55436；測試帳密是公開 fixture，不能用於產品。新 PG18 volume 使用 `/var/lib/postgresql`，不接舊 volume。明示建立／驗證：

```powershell
docker compose -f compose.test.yaml up -d --wait --wait-timeout 45
$env:PYTHONUTF8='1'
$env:PYTHONPATH='src'
uv run --frozen --offline python scripts/init_test_database.py
$env:JD_RELATIONAL_TEST_DB='1'
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_postgres.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_rows.py tests/test_storage_service.py
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_storage_history.py tests/test_read_storage_integration.py
Remove-Item Env:JD_RELATIONAL_TEST_DB
```

initializer 先核固定測試 DB／user／PG18.6 與表集合，再明示 migration；不清資料、不讀產品設定。真 PG tests 預設跳過；明示啟用後無法連線即失敗，不會假 PASS。直接 SQL／mapper 一般案例回滾；service 與新程序回讀案例保留合成已提交文件，不清空 volume。停止測試容器用 `docker compose -f compose.test.yaml stop`，保留 volume。

## 待接責任

目前／歷史 item、field、container、section 與觀察 refs 已發配／驗證，`command_context` 用同版讀取材料重核可寫用途、存在性與欄位摘要。來源查核仍是注入 callback，未接實際 source owner；讀取回 `readability=not_checked`。瀏覽器選區發配仍未完成，此接點明示拒絕 selection，不把 field ref 當選區。

`WriterAuthority` 只有明示測試替身，不能让 HTTP caller 自稱有寫入資格或程序已停止。簽章 key／dataset 由宿主注入；同 key 新程序測試不代表已完成宿主持久設定或備份還原世代。`jd_read` 契約／外殼已驗；`jd_change_read` 尚缺對外 DTO、分頁與工具外殼，不能將目前的純差異與 SQL 材料說成完整 UI。HTTP endpoint、畫面、人工變更通知基準及顧問 runtime 仍待接線。

還原／整輪撤回、更名／封存與恢復、autosave 暫存及維護仍未完成。保存 service 能提供真 DB 觀察；外部結果／HTTP mapper 必須由接線層以該觀察投影，不能自行宣稱 COMMIT。正式格式沿十三表、v3 snapshot 與永久回執，沒有另一份文件權威。

原兩工具及來源 digest 見[首切片](../../docs/specs/2026-09-13-jd-relational-command-slice.md)；目前八工具、分層與錯誤／診斷、289 項結果及通過界線見[本次設計與結果](../../docs/specs/2026-09-13-jd-management-operations-slice.md)。

歷史[結果與資料庫基礎](../../docs/specs/2026-09-13-jd-result-and-storage-foundation.md)與[共同保存交易切片](../../docs/specs/2026-09-13-jd-transaction-service-slice.md)保留當時結果。最新測試、首敗、獨立審查及未完成範圍見[同版讀取與確切差異](../../docs/specs/2026-09-13-jd-read-change-implementation.md)；各批數字不累加。
