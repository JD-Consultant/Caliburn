# Runbook：Caliburn 日常操作與維護

本頁供已安裝 Caliburn 的操作者查啟停、更新、備份與問題。第一次使用請先完成[Docker 入門](getting-started.md)。所有命令都從專案根目錄執行；操作前確認目前使用的資料庫與 Compose project。

| 要處理的事情 | 入口 |
|---|---|
| 開始或結束今天的使用 | [Docker 日常啟停](#日常啟停與更新) |
| 更新程式與資料庫版本 | [更新已有安裝](#更新已有安裝) |
| 啟動失敗、AI 沒回應、查看執行內容 | [診斷](#診斷) |
| 保存訪談與 JD、整理空間 | [資料庫與備份](#資料庫與備份)、[磁碟空間維護](#磁碟空間維護) |
| 修改程式或自行管理 PostgreSQL | [原生開發](native-development.md) |
| 啟用公版查找或維護索引 | [公版參考與 RAG](rag.md) |

## Docker 操作

基本模式使用根目錄的 `compose.jd-app.yaml`。下方直接使用 Docker Compose，不需要安裝 Node、pnpm、Python、uv 或本機 PostgreSQL。已安裝 pnpm 的開發者可用 `pnpm docker:up`／`pnpm docker:stop`，它們只是相同 Compose 命令的捷徑。

### 日常啟停與更新

首次安裝完成後，依需要執行其中一項。再次啟動沿用原設定及資料，不需重做初始化。瀏覽器預設開啟 `http://127.0.0.1:8100/`。

| 操作 | 命令 |
|---|---|
| 啟動／再次啟動 | `docker compose -f compose.jd-app.yaml up -d --wait` |
| 查看容器狀態 | `docker compose -f compose.jd-app.yaml ps` |
| 查看最近的 App 紀錄 | `docker compose -f compose.jd-app.yaml logs --tail 100 app` |
| 停止 App 與資料庫 | `docker compose -f compose.jd-app.yaml stop` |

`stop` 保留容器與 volume；`down` 移除容器與網路，仍保留 named volume。**不要用 `down -v` 或 volume prune 清資料。** 不要任意改 Compose project name（`-p`），否則會使用另一份 volume。

帶 key 重開 App 時會承接已接受但未完成的工作，可能使用模型額度。停止時 Docker 的 `init` 與 90 秒期限供程序正常收尾；逾時強制結束仍沿最後可靠位置恢復，不保證保存所有在途結果。不要按埠號終止身分不明的程序。

資料庫被外力中止或重啟後，再執行 `docker compose -f compose.jd-app.yaml restart app`。Compose 的相依重啟只處理明確的 Compose 操作，不保證 Docker 自動重啟 PostgreSQL 時也重啟 App。healthcheck 只確認程序存活，不代表 AI、資料庫或 PDF 全部可用。

## 更新已有安裝

以下為 Docker 基本模式；原生開發沿[原生更新](native-development.md#更新已有安裝)，公版模式沿 [RAG 操作](rag.md#更新與保存)。三種方式均沿用原資料庫，不以新空庫代替更新。

1. 讓訪談與背景工作停在安全點，確認是自己的 App 後停止它：

   ```powershell
   docker compose -f compose.jd-app.yaml stop app
   ```

   停止失敗時先查明原因，不繼續升級。

2. 按[備份規則](#資料庫與備份)備份整個原資料庫。保留根 `.env` 與原密碼；修改 `.env` 不會替已存在的 PostgreSQL 帳號改密碼。
3. 依取得專案的方式更新程式，保留原設定：

   | 原先取得方式 | 更新方法 |
   |---|---|
   | Git clone | 確認沒有未提交修改、分支沒有分歧後執行 `git pull --ff-only`。失敗時停止，不繼續初始化 |
   | Download ZIP | 將新版解壓到新目錄，先複製原根 `.env`，原 `apps/api/.env` 存在時也一併複製；若自訂 key 檔路徑，確認新目錄仍能找到同一份檔案。保留原目錄直到更新確認完成 |

4. 在更新後的專案根目錄執行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-docker.ps1
   ```

ZIP 更新沿用 Compose 中的 `caliburn-jd-app` project 及原 Docker volume，不因換目錄而另建資料庫。操作前仍須核對使用的是原 Docker 引擎與 project；不要改 project name 或先在沒有原 `.env` 的新目錄執行初始化。

初始化腳本沿用既有設定，依序建置映像、等待 PostgreSQL、執行 migration，再啟動 App；任一步驟失敗就停止。資料庫升級是這次明確執行的操作，日常 `up` 不自動 migration、建立示範資料或清空 volume。腳本拒絕在 App 運行時遷移；不能把停止失敗當作已停妥。

不要因 migration 或 Git 更新失敗就重建資料庫、刪 volume 或強制覆蓋工作。`git pull` 拒絕快轉時先核對本機差異；歷史提交對照沿[歷史查閱](../history.md)查找。

## Docker 設定與保存

根 `.env` 用於 Compose 設定；AI 金鑰的首次設定見[入門步驟](getting-started.md#設定-ai-金鑰可略過)。需要自訂時核對下表：

| 設定 | 用途與限制 |
|---|---|
| `CALIBURN_POSTGRES_PASSWORD` | 新專用 PostgreSQL 的密碼。初始化腳本只在沒有根 `.env` 時產生；既有資料庫須保留原值。手動設定只用英文字母、數字、`-`、`_`，避免 URL 分隔字元 |
| `CALIBURN_APP_PORT` | App 主機埠，預設 `8100`；改埠後使用相應 URL |
| `CALIBURN_POSTGRES_PORT` | PostgreSQL 主機埠，預設 `55440`，供 DataGrip 等本機工具使用 |
| `CALIBURN_OPENAI_ENV_FILE` | 本機金鑰檔路徑，預設 `./apps/api/.env`；由 Compose 在執行時注入後端，檔案不建進映像 |

已有根 `.env` 時只補必要設定，不整份覆蓋。根 `.env` 與 key 檔不提交 Git，也不要分享展開後的 `docker compose config` 或完整容器環境。修改 key 後，讓工作停在安全點，再停止 App 並依[日常啟動](#日常啟停與更新)重新啟動，使 Compose 重新載入環境。

App 內部監聽 `0.0.0.0:8100`，主機只發布至 `127.0.0.1`；仍是本機單操作者產品，沒有放寬 Host／Origin 或加入反向代理。不要同時用兩個 App 程序連同一個資料庫。

`jd_postgres_data` named volume 保存完整業務資料與 checkpoint。PostgreSQL 18 掛載於 `/var/lib/postgresql`，不要改掛舊版的 `/var/lib/postgresql/data`。基本模式不讀、不搬、不刪原本的本機資料庫，也不沿用 RAG volume；既有資料遷入容器須先備份並驗證還原，不能把容器啟動當成資料已搬好。

前端建置與後端非 editable 安裝由多階段映像完成；執行容器不帶 Node、uv、原始 repo、金鑰檔或本機依賴。映像名稱依 Compose project 區分，隔離測試不覆蓋正式 project 的映像。App 以非 root、唯讀 root filesystem 執行，PDF 與瀏覽器暫存只寫 `/tmp`。配置、PDF、資料保存及已驗範圍見 [Docker 交付驗證](../experiments/product-validation/2026-10-03-docker-delivery.md)。

## 診斷

初始化失敗先查下方[失敗階段](#初始化失敗)。日常使用依現象查閱：

| 現象 | 查什麼 |
|---|---|
| 初始化無法連到 Docker | 先開啟 Docker Desktop，確認 Linux containers 可用；依腳本輸出的階段查明原因，不另外安裝原生開發工具 |
| 初始化指出資料庫 volume 已存在，但根 `.env` 遺失 | 找回原 `.env` 與資料庫密碼；不要重新產生密碼或刪 volume |
| Docker 原始錯誤指出主機連接埠已占用 | 核對是否已有 Caliburn 在運行。確有其他服務使用時，依 [Docker 設定](#docker-設定與保存)更換 App 或 PostgreSQL 埠；不要終止身分不明的程序 |
| 原生開發：檢查目前終端的設定 | `pnpm app:status`：核對環境變數及資料庫連線／migration；不代表正在執行的後端狀態，見下方判讀說明 |
| 後端啟動失敗並提到 migration | 沿對應的[更新流程](#更新已有安裝)核對資料庫版本；不要在仍有 App 使用時遷移 |
| `POST /inputs` 回 503 `model_not_configured` | 沒有 OpenAI key（或後端啟動前未設定）；人工 JD 不受影響 |
| 瀏覽器或 CLI 收到 403 | 精確 Host／Origin 檢查：只接受 `127.0.0.1`／`localhost`／`[::1]` 的 5173／8100（及明示的一個 dev origin） |
| `GET /api/health` | 只表示程序存活，不表示資料庫或模型可用 |
| 訪談失敗或結果不明 | 介面顯示安全的失敗原因，原輸入保留；技術診斷在後端 log（只含穩定 ID、階段、錯誤類別，不含原話或 payload） |
| 一輪訪談很久沒有回應 | 多半是 OpenAI 帳戶的每分鐘 token 上限（TPM）在限流，後端 log 會出現 `event=model.request_failed`、`failure_kind=rate_limited`。系統會照服務建議的時間自動多等（沒有建議時 10 秒起、60 秒封頂），**不算失敗**，單輪最長等到工作期限（預設 30 分鐘）；可隨時取消該輪。TPM 200K 的帳戶上，一場 12 輪訪談約 6–25 分鐘；要更快請改用更高 TPM 的帳戶 |
| 訪談或背景整理全部立刻失敗，後端 log 為 `event=model.request_failed`、`failure_kind=access_blocked`、`provider_code=credit_balance_exhausted` | OpenAI 帳戶儲值額度用完（HTTP 429，但不是限流）。系統不重試、原輸入保留、該次處理標為失敗；補額度後重新送出原輸入 |
| 資料庫剛重啟（或被外力中止）後，讀訪談狀態的端點回 500，`/api/health` 仍是 ok | **重啟後端**。leader 鎖與 checkpoint 連線各只持一條資料庫連線、不會自動重連，這是刻意的單一 leader 設計；重啟時系統會恢復已保存的進行中工作（能續作則續作，否則安全終止、原輸入保留，之後可重送） |

### 初始化失敗

初始化腳本只顯示失敗階段與退出碼，不轉印 Docker 原始輸出，避免設定或秘密混入一般輸出。在同一份專案設定下，只重跑失敗的那一步以取得原始錯誤：

| 腳本停在哪裡 | 按需查錯 |
|---|---|
| `[1/4]` 建置 App | `docker compose -f compose.jd-app.yaml build app`；核對下載、網路或建置錯誤 |
| `[2/4]` 等待 PostgreSQL | `docker compose -f compose.jd-app.yaml up -d --wait postgres`；主機埠衝突會在此顯示，程序內部錯誤再查 `docker compose -f compose.jd-app.yaml logs --tail 100 postgres` |
| `[3/4]` 升級資料庫 | 確認 App 已停止後，執行 `docker compose -f compose.jd-app.yaml run --rm app alembic -c /opt/caliburn/alembic.ini upgrade head`，查明連線或 migration 錯誤 |
| `[4/4]` 等待 App | `docker compose -f compose.jd-app.yaml up -d --wait app`；再查 `docker compose -f compose.jd-app.yaml logs --tail 100 app` |

這些命令會重新執行對應步驟，不需把整張表依序跑一遍。查明原因後修正；需要重跑初始化腳本時，先停妥已部分啟動的 App。不要以刪 volume 或重產密碼處理失敗，也不要分享包含秘密的原始錯誤、展開後的 Compose 設定或完整環境。

### DataGrip 與診斷

| 欄位 | 預設值 |
|---|---|
| Host／Port | `127.0.0.1`／`55440`（改埠後依根 `.env`） |
| Database／User | `caliburn`／`caliburn` |
| Password | 根 `.env` 的 `CALIBURN_POSTGRES_PASSWORD` |
| Schema | 勾選 `caliburn`，不是 `public` |

建議另設唯讀連線。既有 AI 執行紀錄的查閱方式不變：先完成[原生開發依賴](native-development.md#安裝依賴)，再在該環境將 `CALIBURN_DATABASE_URL` 設為上述主機連線，沿下方[執行紀錄](#在-datagrip-查某個職務檔案的-ai-執行紀錄)執行 `apps/api/scripts/refresh_execution_diagnostics.py`，再從 DataGrip 查 VIEW。此開發診斷腳本不在執行映像中；不另造一份診斷來源。

### 判讀 `pnpm app:status`

這個命令直接讀取目前終端的環境變數，不經過 `pnpm start` 的啟動器，也不詢問正在執行的後端。它不啟動模型、不遷移資料、不印出密碼或 key。

| 輸出 | 能確認什麼 |
|---|---|
| `database` | 按目前環境設定連線，核對 App migration 是否在 head |
| `model` | 只辨認環境變數中的 key；使用 `apps/api/.env` 時可能顯示未設定，不代表 `pnpm start` 載入失敗。顯示已設定也不證明 key 有效 |
| `pdf` | 核對字型及明示瀏覽器執行檔是否存在；使用 Playwright 預設瀏覽器時，不檢查瀏覽器是否已下載，也不驗證渲染結果 |
| `web` | 只檢查明示的 `CALIBURN_WEB_BUILD_DIRECTORY`；未設定時可能顯示未配置。`pnpm start` 會另外指定 `apps/web/dist` 並核對 `index.html` |

因此，退出碼 0 不是所有產品能力已就緒的證明；AI 與 PDF 的實際功能仍須分別驗證。不要為消除「未設定」提示而把 key 複製到更多地方。

### 在 DataGrip 查某個職務檔案的 AI 執行紀錄

先連到**正式 App 使用的 PostgreSQL database**，勾選 `caliburn` schema；不是 `public`。5180／8180 的記憶體示範站沒有這份資料。DataGrip 的 schema 選擇、Synchronize 及重新查詢是三件事：看不到 VIEW 先同步 schema，資料更新後再重新執行 SELECT。

這是按需診斷功能：原生 checkpoint 有二進位內容，先解碼成一份可重建的本機副本，再用 VIEW 查閱。只讀原始執行／業務表，寫入的只有 `diagnostic_execution_snapshots`；不執行模型、不續跑 Turn、不修改 JD 或 Memory。

在 repository 根目錄、與正式 App 相同的資料庫環境設定下執行：

```powershell
uv run --project apps/api --locked python apps/api/scripts/refresh_execution_diagnostics.py --job-file-id 職務檔案UUID
# 只更新某一輪，改用：
uv run --project apps/api --locked python apps/api/scripts/refresh_execution_diagnostics.py --execution-id 執行UUID
# 不重新擷取，直接在終端查看該輪已有的診斷副本：
uv run --project apps/api --locked python apps/api/scripts/refresh_execution_diagnostics.py --execution-id 執行UUID --show
```

兩個範圍參數擇一；不用 API key。資料庫須已升級到目前 migration；若尚未升級，先沿[更新流程](#更新已有安裝)停妥 App 並升級資料庫，不是每次查詢都遷移。沒有 execution 的既存空檔案回報 0 筆，找不到的 UUID 則報錯。若權限、migration、原生紀錄解碼或並行更新出錯，整次匯入回滾，原診斷副本仍保留。終端只印成功筆數或錯誤類別，避免洩露私人 payload。

DataGrip 展開 `caliburn → views`，可直接雙擊下列 VIEW，再用 `job_file_id` 或 `execution_id` 篩選：

| VIEW | 每列代表什麼 | 主要欄位 |
|---|---|---|
| `diagnostic_execution_history` | 一輪 A 或一批 Memory（包含失敗／取消） | 檔案名稱、原輸入、正式答覆、正式序號、狀態、失敗嘗試、JD 候選、`captured_initial_context`、目前 Memory head 及本批發布的快照 |
| `diagnostic_model_steps` | 一份已保存的邏輯請求；可能尚無回應，不等於已外送或業務 Step 已完成 | role、request_id、response_state、response_order、request（instructions、input、tools）、response（輸出與 usage）、原請求及回應的 checkpoint／source、snapshot_at |
| `diagnostic_tool_calls` | 上述回應的一次 function call | 工具名稱、原 arguments、call_id、可空的 operation_id、對應 output、結果是否已保存 |

例如整個檔案的操作：

`0029_diagnostic_tool_operations` 增加操作識別；需先沿既有更新流程套用 forward migration，再 refresh 診斷副本。投影只安全讀取原 response 的 UUID／null `operation_seed`，以既有 `uuid5(seed, call_id)` 規則計算，沒有 seed 的舊副本為 null，不按相同正文猜命令。`result_state=not_recorded` 只表示工具輸出未保存，仍可用 operation ID 查已提交的業務結果。複合 JD 命令以根 command ID 對應 `jd_operations.result_payload`；舊衍生操作依其既有修訂因果查閱。此 view 及 JSON metadata 是可重建診斷副本，不參與正式恢復或重送。

```sql
SELECT * FROM caliburn.diagnostic_execution_history
WHERE job_file_id = '換成職務檔案UUID'::uuid
ORDER BY created_at, execution_id;

SELECT * FROM caliburn.diagnostic_tool_calls
WHERE execution_id = '換成執行UUID'::uuid
ORDER BY response_order, output_index;

SELECT role, response_order, request, response, snapshot_at
FROM caliburn.diagnostic_model_steps
WHERE execution_id = '換成執行UUID'::uuid
ORDER BY response_order;
```

`request` 是保存的當時請求（敏感欄位已遮蔽），可展開 JSON 看 Context、指引與工具說明。`response_state=request_only` 表示尚未找到已保存回應，不能推定未外送；`recorded` 才有原回應。`response_order` 為相容保留的欄位名，表示邏輯請求的觀察順序，不是重試次數或跨程序精確時鐘。原請求與後續回應的 checkpoint／source 分列，避免用後來的回應時間冒充請求捕捉時間。

`captured_initial_context` 保存原始 binding、request 及來源，可核當輪固定的 Memory／Plan 版本；`current_published_snapshot_id` 是查詢當下的 Memory head，`published_snapshot_ids` 是這次 execution 發布的快照，三者不能互換。Context 中有導覽或工具可用，不表示模型已讀過正文；實際讀取依工具呼叫及回傳查證。CLI `--show` 輸出同一份受控副本，包含工作正文，不能導入一般 Log 或提交 Git。

要看本輪資料庫實際寫了什麼，再 JOIN 既有操作表；讀工具不一定有業務操作，一次工具也可能產生多筆操作：

```sql
SELECT h.display_name, h.execution_id, o.kind, o.expected_revision_id,
       o.result_revision_id, o.request_payload, o.created_at
FROM caliburn.diagnostic_execution_history h
JOIN caliburn.jd_operations o
  ON o.job_file_id = h.job_file_id AND o.candidate_execution_id = h.execution_id
WHERE h.execution_id = '換成執行UUID'::uuid
ORDER BY o.created_at, o.command_id;
```

這個排列用於查閱，不宣稱同時間戳的 command_id 順序就是操作發生順序；修訂因果查 `expected_revision_id → result_revision_id`。`jd_candidate_status = adopted` 才表示本輪候選已採用；工具成功訊息本身不表示整輪已提交。

**判讀界線：**

- 總覽的業務狀態、正式訪談序號與嘗試統計是即時 JOIN；模型／工具正文是 `snapshot_at` 那次擷取。`snapshot_at IS NULL` 表示尚未匯入，兩種計數也為 null；`saved_response_count` 只計已有回應，`request_only_count` 另計只有請求。新進展須再次執行匯入命令，DataGrip Refresh 本身不會解碼新增 checkpoint。
- `recorded` 只表示取得工具回傳，內容仍可能是錯誤；`not_recorded` 表示未找到保存結果，不能推定未執行或失敗。正式效果仍由 JD／Memory 原結果判定。
- 包含本 execution 各階段留下的原模型回應及 pending writes，可能含後來放棄的工作。不能把診斷項目當成正式訪談來源，或把模型回應 `completed` 當整輪成功。
- 副本遮蔽 `encrypted_content`、已知憑證欄位及可辨識的 key 字串，**不是完整匿名化**。仍含原訪談與工作內容；不自動匯出、不提交 Git。DataGrip 可將核准的合成結果另存 JSON／CSV 供錄影或報告使用。一般 log 仍不含這些正文。
- VIEW 沿用查詢者的資料庫權限；建議在 DataGrip 開啟唯讀連線。它不是跨使用者授權或資料隔離 API。

設計取捨、測試及版本見 [T06 診斷查閱證據](../history.md#source-6ac54c64f9ded4edcb9e)。

### 一般 Log 與 HTTP 關聯

正式 `pnpm dev`／`pnpm start` 的後端入口輸出一行一個 JSON 事件。`CALIBURN_LOG_LEVEL` 預設 `INFO`，可選 `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`；提高等級細節也不輸出訪談正文、完整 URL、秘密或 exception 文字。直接呼叫低階 Uvicorn 工廠不會套用這份輸出配置。

先用 `event`、`module`、`failure_kind` 判斷負責環節，再以 `job_file_id`、`execution_id`、`request_id`、`attempt_id` 查原業務／診斷紀錄。HTTP 回應的 `X-Request-ID` 對應 `http_request_id`，由伺服器產生；不採信傳入值，也不把它當業務命令身分。`execution.runner_returned` 只表示 runner 返回，正式完成仍查業務結果。

`supervisor.monitor_failed` 表示背景監督迴圈中止，`supervisor.release_failed` 表示收尾釋放失敗；用 `execution_kind`、`operation`、`failure_kind` 定位。這些事件可能發生在尚未選定工作時，因此不捏造 execution ID，也不輸出原始例外正文。正常取消不記成監督失敗。

`memory.evidence_invalid` 表示某份檔案的 Memory 准入證據損毀；以 `job_file_id`、`execution_id`、`command_id` 及固定 `failure_kind` 查回原操作。execution 識別屬於該筆證據，不一律是 Memory batch，所以此事件不推測 `execution_kind`。該檔案暫不准入 Memory，其他檔案照常處理；相同證據持續異常不每秒重複記錄。重啟不會修好損毀資料。先依原件與正式關聯定位，再按資料操作授權處理；監督本身不改寫原件。證據修復後，既有唯讀探索與 claim 會重新核對，不能把這個恢復誤認為未知模型請求可以重送。完整邊界見[Memory 背景工作](../implementation/agent-supervision.md#5-memory-背景工作)。

輸出使用容量 1024 的非阻塞佇列，滿時捨棄新紀錄；後續可用事件會附累計 `logging_dropped_records`／`logging_output_failures`，不能把沒看到 Log 當作沒發生。正常關閉最多等待 1 秒排出；程序意外終止可能遺失尾端 Log，可靠結果沿 PostgreSQL／checkpoint 核對。原生終端不自動保存檔案；Docker 沿 Compose 的 local driver 輪替，每檔 10 MB、最多 3 檔。格式規範見[工程文件](../standards/coding-standard.md#72-log-的格式責任與查閱)，本輪驗證見[重構證據](../plans/evidence/full-system-review-2026-10-08.md)。

## 資料庫與備份

一個 PostgreSQL cluster 可包含多個 database，每個 database 再包含 schema；Caliburn 的同一 schema 可保存多份職務檔案。不要為每份訪談建立一套 PostgreSQL，也不要只憑容器名稱中的 `test`／`production` 判定資料用途。日常資料與測試資料使用明確分開的 database／連線；驗證用 schema 必須在測試資料庫中。

| 資料用途 | 保存與收尾 |
|---|---|
| 日常訪談、JD 與工作進度 | 保留既有資料來源；操作前核對 App 實際連線、schema 及 volume。更新 App 不另建一份空庫當作遷移完成 |
| 可重建的整合測試 | 保存 fixture、命令與必要結果，完成後只回收本次建立的 schema／容器／volume；中斷留下的資源另核對，不全域 prune |
| 已結案研究實驗 | 保留足以支持結論的設定、輸入、結果、評分及必要 trace；已有 Git／遠端原件的不重複封存。只有還需重播保存狀態時才保留 database／checkpoint |

需要保留資料庫時，使用 `pg_dump -Fc` 保存整個 database，不以 `-n` 只挑部分 schema；業務資料與 checkpoint 必須一起保存。多個 database 分別匯出，角色等 cluster 級資訊另用 `pg_dumpall --globals-only --no-role-passwords` 保存。OpenAI key 另行提供，角色密碼與本機設定不放入封存附件；瀏覽器 localStorage／sessionStorage 不作正式資料備份。相關工具契約見 [PostgreSQL 備份文件](https://www.postgresql.org/docs/18/backup.html)與 [pg_dumpall](https://www.postgresql.org/docs/18/app-pg-dumpall.html)。

備份與來源資料比較使用同一快照，避免使用中的資料持續更新造成錯判。先在自有隔離環境還原，核對 schema／table、資料筆數與必要內容摘要，保存命令結果；`pg_restore --list` 只能檢查目錄，不能代替實際還原。移除舊資料前，再確認 App 沒有使用該目標、備份後未新增需保留資料、遠端下載雜湊相同。不能手動刪 WAL，或直接壓縮運作中的資料目錄代替一致性備份。

資料庫備份及未公開材料放[私人封存庫](https://github.com/JD-Consultant/Caliburn-archives)，不放公開 repository 或其 Releases。取得備份後先核對清單中的 SHA-256，再在隔離 PostgreSQL 還原；不直接覆蓋日常資料庫。封存格式與取回方式見[原件保存規範](../experiments/artifact-storage.md#私人歷史材料與資料庫封存)。

已確認僅含合成測試資料、且所需研究原件已有保存的舊環境，可以依清理授權直接回收，不必為了清理再建立永久完整備份。清理記錄須指出保留證據的位置，以及不再保留舊 DB 重播能力的取捨。資料用途未明或仍供日常使用時不套用這項規則。

首版驗收曾以中斷後重開查回資料為主；不把該歷史範圍解讀成已完成所有版本的備份還原驗收。未送出的輸入與未保存草稿不保證可恢復；每次維護只回報實際驗證的資料與版本。

## 磁碟空間維護

先盤點目錄容量及目前程序，再區分可重建快取、可還原副本、執行環境與正式資料。被 Git 忽略只代表不提交，不能據此刪除。

- **實驗解壓副本**：沿[原件保存規範](../experiments/artifact-storage.md#分析完成後釋放空間)核對後清理；gzip 與雜湊清單保留，分析前按需還原。
- **工具快取**：確認沒有相關工具運作後，可清除有 `CACHEDIR.TAG` 的 mypy 快取。套件快取使用工具本身的維護命令，例如 [uv 的 cache prune](https://docs.astral.sh/uv/concepts/cache/#clearing-the-cache)；先核對快取位置與環境連結方式，避免誤刪執行環境依賴。
- **本機歷史與執行環境**：`.research-tmp` 曾混放 Python、PostgreSQL、Chromium、資料庫與未提交封存材料，不能整包視為可刪快取。清理前查虛擬環境的 `pyvenv.cfg`、設定及程序路徑；即使資料庫已停止，也須沿上節備份與資料處置規則處理。
- **Git 資料**：先用 `git count-objects -vH` 盤點並檢查完整性。保留正式 objects、packs 與復原資料；異常暫存檔須個別確認來源、使用狀態及可恢復性，不以整批刪除 `.git` 或改寫歷史作日常清理。

新工作的暫存沿 `.tmp/` 放置；結束前將必要證據保存至責任文件指定位置，再核對清理範圍。長期執行環境與資料庫應有明確的保存位置，遷移時同步更新設定並驗證啟動，不直接移除目前使用的路徑。

每批暫存使用能辨認用途的目錄，記錄來源、是否仍使用及收尾條件。已結案的研究保存結果與必要原件，依賴保留 lockfile／重建方式；除錯暫留的資料須有明確理由與下次清理條件。維護清單只記尚需處理的本機資源，完成後移除，不再累積第二份永久待辦。

## 其他操作入口

<a id="快速開始"></a>
<a id="首次啟動"></a>

首次安裝與啟動已集中至[第一次使用](getting-started.md)。

<a id="服務與版本"></a>
<a id="安裝依賴"></a>
<a id="第一次初始化"></a>
<a id="ai-credential"></a>
<a id="日常啟動與停止"></a>
<a id="pdf-匯出"></a>
<a id="驗證"></a>

工具版本、安裝依賴、原生資料庫／AI／PDF 設定、開發啟停及測試見[原生開發](native-development.md)。

<a id="含公版參考的-docker-模式"></a>
<a id="rag獨立服務非-jd-app-預設依賴"></a>

公版模式與獨立管線的操作見[公版參考與 RAG](rag.md)。本節保留舊連結的閱讀去向，完整步驟只在對應頁維護。
