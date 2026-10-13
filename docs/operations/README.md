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

以下為 Docker 基本模式；原生開發沿[原生更新](native-development.md#更新已有安裝)，公版模式沿 [RAG 操作](rag.md#更新與保存)。

目前的 `0034_jd_task_sources` 保存格式須在空 namespace 初始化，不搬移較早版本的資料或中斷工作。切換前完成或取消工作並停妥 App，在根 `.env` 將 `CALIBURN_DATABASE_SCHEMA` 設為一個新的空 schema（例如 `caliburn_v2`），再執行下列初始化。相同新版 schema 後續可原地使用；原 schema 與 volume 不會因此刪除。這是明示切換，不能用 Alembic stamp 跳過結構核對。

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

不要因 migration 或 Git 更新失敗就重建資料庫、刪 volume 或強制覆蓋工作。`git pull` 拒絕快轉時先核對本機差異與遠端分支，不自動重設或覆蓋本機工作。

## Docker 設定與保存

根 `.env` 用於 Compose 設定；AI 金鑰的首次設定見[入門步驟](getting-started.md#設定-ai-金鑰可略過)。需要自訂時核對下表：

| 設定 | 用途與限制 |
|---|---|
| `CALIBURN_POSTGRES_PASSWORD` | 新專用 PostgreSQL 的密碼。初始化腳本只在沒有根 `.env` 時產生；既有資料庫須保留原值。手動設定只用英文字母、數字、`-`、`_`，避免 URL 分隔字元 |
| `CALIBURN_APP_PORT` | App 主機埠，預設 `8100`；改埠後使用相應 URL |
| `CALIBURN_POSTGRES_PORT` | PostgreSQL 主機埠，預設 `55440`，供 DataGrip 等本機工具使用 |
| `CALIBURN_DATABASE_SCHEMA` | App namespace，預設 `caliburn`；不相容的保存版本選擇新空 schema |
| `CALIBURN_OPENAI_ENV_FILE` | 本機金鑰檔路徑，預設 `./apps/api/.env`；由 Compose 在執行時注入後端，檔案不建進映像 |

已有根 `.env` 時只補必要設定，不整份覆蓋。根 `.env` 與 key 檔不提交 Git，也不要分享展開後的 `docker compose config` 或完整容器環境。修改 key 後，讓工作停在安全點，再停止 App 並依[日常啟動](#日常啟停與更新)重新啟動，使 Compose 重新載入環境。

App 內部監聽 `0.0.0.0:8100`，主機只發布至 `127.0.0.1`；仍是本機單操作者產品，沒有放寬 Host／Origin 或加入反向代理。不要同時用兩個 App 程序連同一個資料庫。

`jd_postgres_data` named volume 保存完整業務資料與 checkpoint。PostgreSQL 18 掛載於 `/var/lib/postgresql`，不要改掛舊版的 `/var/lib/postgresql/data`。基本模式不讀、不搬、不刪原本的本機資料庫，也不沿用 RAG volume；既有資料遷入容器須先備份並驗證還原，不能把容器啟動當成資料已搬好。

前端建置與後端非 editable 安裝由多階段映像完成；執行容器不帶 Node、uv、原始 repo、金鑰檔或本機依賴。映像名稱依 Compose project 區分，隔離測試不覆蓋正式 project 的映像。App 以非 root、唯讀 root filesystem 執行，PDF 與瀏覽器暫存只寫 `/tmp`。配置與保存接線見[介面與交付](../implementation/interface-and-delivery.md#42-docker-交付)；目標安裝仍須依本頁確認啟動及保存行為。

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
| 一輪訪談很久沒有回應 | 先查後端限流紀錄；等待與取消的判讀見下方 |
| 訪談或背景整理全部立刻失敗 | 核對是否為帳戶額度用完；與限流的差異見下方 |
| 資料庫剛重啟（或被外力中止）後，讀訪談狀態的端點回 500，`/api/health` 仍是 ok | **重啟後端**；連線與工作恢復的限制見下方 |

### 訪談等待與限流

訪談長時間沒有回應，多半是 OpenAI 帳戶的每分鐘 token 上限（TPM）在限流。後端 log 會出現 `event=model.request_failed`、`failure_kind=rate_limited`。

系統按服務建議的時間自動等待；沒有建議時從 10 秒起、60 秒封頂。這段等待不算失敗，單輪最長等到工作期限（預設 30 分鐘），期間可隨時取消。

TPM 200K 的帳戶上，一場 12 輪訪談約 6–25 分鐘；要更快，請改用更高 TPM 的帳戶。

### 帳戶額度用完

後端 log 出現下列欄位時，表示 OpenAI 儲值額度用完：

- `event=model.request_failed`
- `failure_kind=access_blocked`
- `provider_code=credit_balance_exhausted`

它也回 HTTP 429，但不是限流：系統不重試，會保留原輸入並將該次處理標為失敗。補足額度後再送出原輸入。

### 資料庫重啟後

leader 鎖與 checkpoint 各持有一條資料庫連線，不會自動重連，這是現行單一 leader 設計。重啟後端時，系統會查回已保存的進行中工作；能續作則續作，否則安全終止並保留原輸入，之後可重送。

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
| Schema | App 實際的 `CALIBURN_DATABASE_SCHEMA`，預設 `caliburn` |

建議另設唯讀連線。DataGrip 可直接查業務表；包含原生 checkpoint 解碼、當時版本及工具往返的查閱，沿下方 [CLI](#查閱-ai-執行原件)。

### 判讀 `pnpm app:status`

這個命令直接讀取目前終端的環境變數，不經過 `pnpm start` 的啟動器，也不詢問正在執行的後端。它不啟動模型、不遷移資料、不印出密碼或 key。

| 輸出 | 能確認什麼 |
|---|---|
| `database` | 按目前環境設定連線，核對 App migration 是否在 head |
| `model` | 只辨認環境變數中的 key；使用 `apps/api/.env` 時可能顯示未設定，不代表 `pnpm start` 載入失敗。顯示已設定也不證明 key 有效 |
| `pdf` | 核對字型及明示瀏覽器執行檔是否存在；使用 Playwright 預設瀏覽器時，不檢查瀏覽器是否已下載，也不驗證渲染結果 |
| `web` | 只檢查明示的 `CALIBURN_WEB_BUILD_DIRECTORY`；未設定時可能顯示未配置。`pnpm start` 會另外指定 `apps/web/dist` 並核對 `index.html` |

因此，退出碼 0 不是所有產品能力已就緒的證明；AI 與 PDF 的實際功能仍須分別驗證。不要為消除「未設定」提示而把 key 複製到更多地方。

### 查閱 AI 執行原件

原生環境先完成[開發依賴](native-development.md#安裝依賴)，將終端的 `CALIBURN_DATABASE_URL` 與 `CALIBURN_DATABASE_SCHEMA` 設為要查閱的 App 資料庫及 schema。CLI 隨後端套件及執行映像交付，不載入 `.env`，也不需要模型 key。

從職務檔案總覽找到 execution，再查該輪 Step；需要正文時才加 `--full`：

```powershell
uv run --project apps/api --locked python -m caliburn.diagnostics --job-file-id 職務檔案UUID
uv run --project apps/api --locked python -m caliburn.diagnostics --execution-id 執行UUID
uv run --project apps/api --locked python -m caliburn.diagnostics --execution-id 執行UUID --request-id 請求UUID --full
```

Compose 部署使用同一入口與容器的資料庫設定。App 執行中可用 `exec`；App 停止而資料庫仍執行時可用 `run` 單次查閱：

```powershell
docker compose -f compose.jd-app.yaml exec -T app python -m caliburn.diagnostics --execution-id 執行UUID --full
docker compose -f compose.jd-app.yaml run --rm --no-deps -T app python -m caliburn.diagnostics --execution-id 執行UUID --full
```

檔案總覽預設最多 100 輪，可用 `--limit` 調整、`--after 上頁最後的執行UUID` 續查。`--full` 是明示讀取完整原件；檔案範圍加上它會包含所有輪次，不能與 `--after` 合用。大型訪談優先選 execution，再選 request，避免不必要地展開整份檔案。

每次命令在同一唯讀 Repeatable Read 交易組裝業務資料及原生 checkpoint／pending writes，直接輸出 UTF-8 JSON，中文可直接閱讀；不寫診斷副本、不需要 refresh，也不啟動或暫停 Agent。`read` 記錄讀取起訖及模式；再次執行才取得新的讀取視野。

| 輸出 | 如何使用 |
|---|---|
| `execution`、`attempts`、`budget` | 查輪次狀態、故障嘗試及已記錄用量，失敗與取消也可定位 |
| `steps`、`tool_calls` | 查 logical request、已保存 `input_count`、回應、call／operation ID 及工具結果是否保存；完整正文由 `--full` 展開 |
| `context_bindings`、`captured_initial_context`、`captured_analysis_contexts` | 核對 A／B 當時綁定與組裝內容；B 尚無第一個回應的 capture 也可在 `--full` 查閱，不能拿目前的 Memory head 解釋歷史 |
| `compactions` | 查已保存的壓縮請求／結果、局部採用及角色是否引用；尚無下一 request 的壓縮仍可查 |
| `control_history` | 查保存的 `step_pause`、原 interrupt ID、完整 Step 計數及所在 checkpoint；`continuation` 沿同一 thread／namespace 的父子 checkpoint 關係查後續已提交進展 |
| `candidates`、`memory_publications`、`interviews` | 對照正式採用、發布及訪談效果，和模型是否回覆完成分開判讀 |
| `operations`、`versions`（`--full`） | 沿原 operation 與固定版本讀 Memory／JD／Plan 正文；缺少的原件明示為 missing，不改讀 latest |

`--request-id` 選出該 Step 與工具；同輪綁定、操作、控制歷史及壓縮仍提供判讀背景。只有已保存請求不代表已外送；`result_state=not_recorded` 只表示工具輸出尚未保存，不能推定沒有執行。沿 `operation_id` 和 `receipt_state` 核對已提交結果，整輪正式採用仍由業務狀態判斷。壓縮結果的局部採用與角色歷史引用也是不同事件。

Step 的 `input_count` 保留同 thread／request／完整請求快照已保存的 `input_tokens` 與 `attempt_id`，包括父節點尚未返回的子圖原件。`null` 表示本次未觀察到相符 count，不是零，也不能推定可重送；它與回應的 `usage` 分開判讀，不以輪前歷史 count 或目前重新計數補值。

控制歷史的 `continuation.state=observed` 表示保存的後代 checkpoint 已通過該完整 Step 邊界；`checkpoint_path` 提供原件接續位置。`not_observed` 只表示未找到足夠後續證據，不能推定目前仍暫停，須對照 `execution.status`。暫停以 interrupt／checkpoint／`completed_steps` 定位；`continuation.request_id` 屬於後續 checkpoint。`checkpoint_time` 是 checkpoint 保存時間，暫停原件附在其 pending write；它不是 pause 或 resume 受理時間。這份投影不另存控制事件，也不推造未保存的時間。

取消保留執行原件及未發布修訂供查閱，業務讀取已回到取消前。Context 可讀版本、實際送入模型的內容、工具實際讀到的內容各自查證，不把可讀視為已讀，也不推造 opaque 壓縮內容。

輸出遮蔽 `encrypted_content`、已知憑證欄位及可辨識的 key 字串，仍可能含訪談與工作正文，**不代表匿名化**。只在核准範圍另存、分享；一般 Log 不輸出這些正文。查閱使用既有資料庫權限，建議提供唯讀連線；它不是跨使用者授權 API。查閱或匯出失敗不修改正式結果，也不觸發業務重送。

#### 按 request 與 call 查正文

以下 PowerShell 範例先設定 execution／request ID，取得一份完整 JSON 後在本機選欄位；不必為每個欄位重查資料庫。明示 UTF-8 讓 PowerShell 正確解讀原生命令輸出：

```powershell
$executionId = '執行UUID'
$requestId = '請求UUID'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$json = uv run --project apps/api --locked python -m caliburn.diagnostics --execution-id $executionId --request-id $requestId --full
if ($LASTEXITCODE -ne 0) { throw '診斷讀取失敗，請查看 stderr。' }
$document = @($json | ConvertFrom-Json)[0]
$step = $document.steps | Where-Object request_id -EQ $requestId

$step | Select-Object request_id, response_state, input_count
$step.request.instructions                         # 當時組裝的 Prompt
$step.request.input | ConvertTo-Json -Depth 100     # 實際請求 Context／原生歷史
$step.request.tools | ConvertTo-Json -Depth 100     # 當時工具定義
$step.response.output | ConvertTo-Json -Depth 100   # 已保存的模型輸出
```

先列 call ID，再代入要查的那一次；`arguments` 與 `output` 保留原字串，工具輸出不一定是 JSON：

```powershell
$document.tool_calls | Select-Object call_id, name, result_state, receipt_state
$callId = '工具call_id'
$call = $document.tool_calls | Where-Object call_id -EQ $callId
$call.arguments
$call.output
$call.receipts | ConvertTo-Json -Depth 100

# 沿該 call 的 operation ID 取得 owner 已保存的操作／回執正文。
$document.operations.PSObject.Properties | ForEach-Object { $_.Value } |
    Where-Object {
        $call.operation_id -and
        ($_.command_id -eq $call.operation_id -or $_.operation_id -eq $call.operation_id)
    } | ConvertTo-Json -Depth 100
```

沒有對應回執時輸出為空，仍以 `receipt_state` 及正式業務狀態判讀。需要保存本次 JSON 可用 `$json | Set-Content -Encoding utf8 './execution.json'`；再次查閱使用 `Get-Content -Raw -Encoding utf8 './execution.json' | ConvertFrom-Json`。

### 一般 Log 與 HTTP 關聯

正式 `pnpm dev`／`pnpm start` 的後端入口輸出一行一個 JSON 事件。`CALIBURN_LOG_LEVEL` 預設 `INFO`，可選 `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`；提高等級細節也不輸出訪談正文、完整 URL、秘密或 exception 文字。直接呼叫低階 Uvicorn 工廠不會套用這份輸出配置。

先用 `event`、`module`、`failure_kind` 判斷負責環節，再以 `job_file_id`、`execution_id`、`request_id`、`attempt_id` 查原業務／診斷紀錄。HTTP 回應的 `X-Request-ID` 對應 `http_request_id`，由伺服器產生；不採信傳入值，也不把它當業務命令身分。`execution.runner_returned` 只表示 runner 返回，正式完成仍查業務結果。

`supervisor.monitor_failed` 表示背景監督迴圈中止，`supervisor.release_failed` 表示收尾釋放失敗；用 `execution_kind`、`operation`、`failure_kind` 定位。這些事件可能發生在尚未選定工作時，因此不捏造 execution ID，也不輸出原始例外正文。正常取消不記成監督失敗。

`memory.evidence_invalid` 表示某份檔案的 Memory 准入證據損毀；以 `job_file_id`、`execution_id`、`command_id` 及固定 `failure_kind` 查回原操作。execution 識別屬於該筆證據，不一定是 Memory batch，因此事件不推測 `execution_kind`。

該檔案暫不准入 Memory，其他檔案照常處理；同一證據持續異常時，不會每秒重複記錄。重啟不會修好損毀資料，須先依原件與正式關聯定位，再按資料操作授權處理；監督本身不改寫原件。證據修復後，唯讀探索與 claim 會重新核對，這不代表未知模型請求可以重送。完整邊界見[Memory 背景工作](../implementation/agent-supervision.md#5-memory-背景工作)。

#### 日誌容量與保存

輸出使用容量 1024 的非阻塞佇列，滿時捨棄新紀錄；後續可用事件會附累計 `logging_dropped_records`／`logging_output_failures`，不能把沒看到 Log 當作沒發生。

正常關閉最多等待 1 秒排出；程序意外終止可能遺失尾端 Log，可靠結果沿 PostgreSQL／checkpoint 核對。原生終端不自動保存檔案；Docker 沿 Compose 的 local driver 輪替，每檔 10 MB、最多 3 檔。格式規範見[工程文件](../standards/coding-standard.md#72-log-的格式責任與查閱)。

## 資料庫與備份

一個 PostgreSQL cluster 可包含多個 database，每個 database 再包含 schema；Caliburn 的同一 schema 可保存多份職務檔案。不要為每份訪談建立一套 PostgreSQL，也不要只憑容器名稱中的 `test`／`production` 判定資料用途。日常資料與測試資料使用明確分開的 database／連線；驗證用 schema 必須在測試資料庫中。

| 資料用途 | 保存與收尾 |
|---|---|
| 日常訪談、JD 與工作進度 | 操作前核對 App 實際連線、schema 及 volume。不相容版本依本頁明示切換新空 schema；這不代表舊資料已遷移，原資料仍按保存授權處置 |
| 可重建的整合測試 | 保存 fixture、命令與必要結果，完成後只回收本次建立的 schema／容器／volume；中斷留下的資源另核對，不全域 prune |
| 已結案研究實驗 | 保留足以支持結論的設定、輸入、結果、評分及必要 trace；已有 Git／遠端原件的不重複封存。只有還需重播保存狀態時才保留 database／checkpoint |

### 備份範圍

- 使用 `pg_dump -Fc` 保存整個 database，不以 `-n` 只挑部分 schema；業務資料與 checkpoint 必須一起保存。
- 多個 database 分別匯出。角色等 cluster 級資訊另用 `pg_dumpall --globals-only --no-role-passwords` 保存。
- OpenAI key 另行提供，角色密碼與本機設定不放入封存附件；瀏覽器 localStorage／sessionStorage 不作正式資料備份。

相關工具契約見 [PostgreSQL 備份文件](https://www.postgresql.org/docs/18/backup.html)與 [pg_dumpall](https://www.postgresql.org/docs/18/app-pg-dumpall.html)。

### 還原核對與存放

備份與來源資料比較使用同一快照，避免使用中的資料持續更新造成錯判。先在自有隔離環境還原，核對 schema／table、資料筆數與必要內容摘要，保存命令結果；`pg_restore --list` 只能檢查目錄，不能代替實際還原。

移除舊資料前，再確認 App 沒有使用該目標、備份後未新增需保留資料、遠端下載雜湊相同。不能手動刪 WAL，或直接壓縮運作中的資料目錄代替一致性備份。

資料庫備份及未公開材料使用另行授權的受控保存位置，不放公開 repository 或其 Releases。取得備份後先核對清單中的 SHA-256，再在隔離 PostgreSQL 還原；不直接覆蓋日常資料庫。備份須一併保存還原方式與所需版本。

### 測試資料收尾與驗證界線

已確認僅含合成測試資料、且所需研究原件已有保存的舊環境，可以依清理授權直接回收，不必為了清理再建立永久完整備份。清理記錄須指出保留證據的位置，以及不再保留舊 DB 重播能力的取捨。資料用途未明或仍供日常使用時不套用這項規則。

首版驗收曾以中斷後重開查回資料為主；不把該歷史範圍解讀成已完成所有版本的備份還原驗收。未送出的輸入與未保存草稿不保證可恢復；每次維護只回報實際驗證的資料與版本。

## 磁碟空間維護

先盤點目錄容量及目前程序，再區分可重建快取、可還原副本、執行環境與正式資料。被 Git 忽略只代表不提交，不能據此刪除。

- **工具快取**：確認沒有相關工具運作後，可清除有 `CACHEDIR.TAG` 的 mypy 快取。套件快取使用工具本身的維護命令，例如 [uv 的 cache prune](https://docs.astral.sh/uv/concepts/cache/#clearing-the-cache)；先核對快取位置與環境連結方式，避免誤刪執行環境依賴。
- **本機歷史與執行環境**：`.research-tmp` 曾混放 Python、PostgreSQL、Chromium、資料庫與未提交封存材料，不能整包視為可刪快取。清理前查虛擬環境的 `pyvenv.cfg`、設定及程序路徑；即使資料庫已停止，也須沿上節備份與資料處置規則處理。
- **Git 資料**：先用 `git count-objects -vH` 盤點並檢查完整性。保留正式 objects、packs 與復原資料；異常暫存檔須個別確認來源、使用狀態及可恢復性，不以整批刪除 `.git` 或改寫歷史作日常清理。

新工作的暫存沿 `.tmp/` 放置；結束前將必要證據保存至責任文件指定位置，再核對清理範圍。長期執行環境與資料庫應有明確的保存位置，遷移時同步更新設定並驗證啟動，不直接移除目前使用的路徑。

每批暫存使用能辨認用途的目錄，記錄來源、是否仍使用及收尾條件。已結案的研究保存結果與必要原件，依賴保留 lockfile／重建方式；除錯暫留的資料須有明確理由與下次清理條件。維護清單只記尚需處理的本機資源，完成後移除，不再累積第二份永久待辦。
