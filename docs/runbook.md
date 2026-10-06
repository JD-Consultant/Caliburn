# Runbook — Caliburn JD App 本機操作

正式 App 是 `apps/api` 與 `apps/web`，日常操作統一從 repository 根目錄進入；正式邊界見
[ADR 0079](adr/0079-target-rebuild-production-cutover.md)。舊 `experiments/jd-relational-app`
（含舊 `app:init`／`app:set-key`、OpenRouter、Windows 認證管理員）已退役，不再有對應命令。

本頁負責安裝、設定、啟停、更新與診斷。首次使用從下方[快速開始](#快速開始)選擇 Docker 或原生方式；產品用途與功能見[主 README](../README.md)。

## 快速開始

選一種啟動方式，所有命令都從專案根目錄執行。首次使用先完成對應的安裝、設定與初始化；之後使用日常啟動命令即可。

| 方式 | 首次安裝與啟動 | 日常啟動 | 停止 |
|---|---|---|---|
| Docker 基本模式：App、資料庫與 PDF | [Docker 操作](#docker-操作) | `pnpm docker:up` | `pnpm docker:stop` |
| Docker 公版參考模式：基本模式加 RAG | [公版參考設定](#含公版參考的-docker-模式) | `pnpm docker:rag:up` | `pnpm docker:rag:stop` |
| 原生：本機開發或自行管理 PostgreSQL | [服務與版本](#服務與版本) → [安裝依賴](#安裝依賴) → [第一次初始化](#第一次初始化) → [AI credential](#ai-credential) | 啟動 PostgreSQL、提供環境設定後執行 `pnpm start` | 在啟動的終端按 Ctrl+C |

預設畫面是 `http://127.0.0.1:8100/`。原生開發使用 `pnpm dev`，畫面改為 `http://127.0.0.1:5173/`，操作細節見[日常啟動與停止](#日常啟動與停止)。原生 PDF 資源須另行設定，見[PDF 匯出](#pdf-匯出)。

## 服務與版本

| 項目 | 要求 |
|---|---|
| Node.js | `>=24.19.0 <25` |
| package manager | pnpm `12.5.1`，根目錄單一 lockfile |
| Python | `3.14`，由 uv `0.12.20` 管理（`apps/api/uv.lock`） |
| PostgreSQL | 本機 **18.6**，獨立程序；容器或本機安裝皆可 |
| API | `127.0.0.1:8100`，單程序、無 reload、無 proxy headers |
| Web | 正式：由 API 同源提供 `http://127.0.0.1:8100/`；開發：Vite `http://127.0.0.1:5173/` |
| 模型 | OpenAI Responses 直連，`gpt-6-luna`／high；key 只在後端使用 |
| PDF | Docker 已包字型與 Playwright Chromium；原生啟動須另行設定，缺少時匯出回 503 |
| RAG | 隔離且非預設依賴 |

不要按端口終止身分不明的程序；程式變更後在原前景終端正常停止再重啟。

## Docker 操作

使用根目錄的 `compose.jd-app.yaml`，不是 RAG 的 `docker-compose.yml`。Docker Desktop 須切到 Linux containers，Docker Compose 須為 `2.24.0` 以上（`docker compose version`）；首次建置需下載映像、鎖定依賴、Chromium 與 Noto CJK 字型。前端建置和後端非 editable 安裝由多階段映像完成；執行容器不帶 Node、uv、原始 repo、金鑰或本機依賴。

`pnpm docker:*` 只是下方 Compose 命令的捷徑，不建立另一套啟動器。未安裝 pnpm 時可直接執行對應的 `docker compose` 命令。

### 首次啟動

1. 根目錄尚無 `.env` 時，複製 `.env.jd-app.example` 為 `.env`；已有檔案時只補上範例中的設定，不覆蓋原內容：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.jd-app.example .env }
```

2. 在根 `.env` 設定 `CALIBURN_POSTGRES_PASSWORD`。使用足夠長、只含英文字母、數字、`-`、`_` 的密碼，避免 URL 分隔字元；妥善保管，後續沿用，不每次重產。這是新專用 PostgreSQL 的密碼，不是既有資料庫的密碼。
3. AI key 仍放 `apps/api/.env` 的唯一一行 `OPENAI_API_KEY=...`，或以 `CALIBURN_OPENAI_ENV_FILE` 指向本機 key 檔。缺檔時只停用 AI，不影響人工 JD／PDF。Compose 在執行時注入後端環境；它不將檔案建進映像。根 `.env` 與 key 檔均不提交 Git；也不要分享展開後的 `docker compose config` 或完整容器環境。
4. 從 repo 根目錄依序執行：

```powershell
& {
    docker compose -f compose.jd-app.yaml build app
    if ($LASTEXITCODE -ne 0) { throw 'App 建置失敗，停止啟動。' }
    docker compose -f compose.jd-app.yaml up -d --wait postgres
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL 未就緒，停止啟動。' }
    docker compose -f compose.jd-app.yaml run --rm app alembic -c /opt/caliburn/alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) { throw '資料庫升級失敗，停止啟動。' }
    docker compose -f compose.jd-app.yaml up -d --wait app
    if ($LASTEXITCODE -ne 0) { throw 'App 未就緒，請檢查 log。' }
}
```

畫面預設在 `http://127.0.0.1:8100/`。App 內部監聽 `0.0.0.0:8100`，但主機只發布至 `127.0.0.1`；仍是本機單操作者產品，沒有放寬 Host／Origin 或加入反向代理。根 `.env` 可改 `CALIBURN_APP_PORT`（App）與 `CALIBURN_POSTGRES_PORT`（DataGrip）；改埠後使用相應 URL。不要同時用兩個 App 程序連同一個資料庫。

新 PostgreSQL 的 `jd_postgres_data` named volume 保存完整資料庫，包含業務與 checkpoint。PostgreSQL 18 使用 `/var/lib/postgresql` 掛載；不要改掛到舊版的 `/var/lib/postgresql/data`。這套配置不讀、不搬、不刪原本的本機資料庫，也不沿用 RAG volume。既有資料遷入容器須另外先備份、驗證還原，不能將「容器可以啟動」當成資料已搬好。

### 日常啟停與更新

首次安裝完成後，依需要執行其中一項；再次啟動沿用原設定及資料，不需重做初始化。

| 操作 | 命令 |
|---|---|
| 啟動／再次啟動 | `docker compose -f compose.jd-app.yaml up -d --wait` |
| 查看容器狀態 | `docker compose -f compose.jd-app.yaml ps` |
| 查看最近的 App 紀錄 | `docker compose -f compose.jd-app.yaml logs --tail 100 app` |
| 停止 App 與資料庫 | `docker compose -f compose.jd-app.yaml stop` |

`stop` 保留容器與 volume；`down` 移除容器與網路，仍保留 named volume。**不要用 `down -v` 或 volume prune 清資料。**不要任意改 Compose project name（`-p`），否則會使用另一份 volume。密碼只在空 volume 初始化時生效；修改 `.env` 不會替已存在的 PostgreSQL 帳號改密碼。

更新前先停在安全點、停止自有 App 並備份整個原資料庫，再更新程式：

```powershell
& {
    docker compose -f compose.jd-app.yaml stop app
    if ($LASTEXITCODE -ne 0) { throw 'App 停止失敗，停止更新。' }
    git pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw 'Git 更新失敗，請先核對本機差異。' }
    docker compose -f compose.jd-app.yaml build app
    if ($LASTEXITCODE -ne 0) { throw 'App 建置失敗，停止更新。' }
    docker compose -f compose.jd-app.yaml up -d --wait postgres
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL 未就緒，停止更新。' }
    docker compose -f compose.jd-app.yaml run --rm app alembic -c /opt/caliburn/alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) { throw '資料庫升級失敗，停止更新。' }
    docker compose -f compose.jd-app.yaml up -d --wait app
    if ($LASTEXITCODE -ne 0) { throw 'App 未就緒，請檢查 log。' }
}
```

資料庫升級仍是明確操作；啟動不自動 migration、建示範資料或清空 volume。上述 PowerShell 區塊在任一步驟失敗時停止，不繼續啟動未升級的 App。映像名稱由 Compose project 區分，隔離測試建置不覆蓋正式 project 的映像。App 以非 root、唯讀 root filesystem 執行，暫存 PDF／瀏覽器工作只寫 `/tmp`。Docker 的 `init` 與 90 秒停止期限供正常收尾；逾時強制結束仍依既有可靠位置恢復，不保證保存所有在途結果。重開且帶 key 時會承接已接受工作，可能使用模型額度。

資料庫被外力中止或重啟後，依既有連線限制再執行 `docker compose -f compose.jd-app.yaml restart app`。Compose 的相依重啟只處理明確的 Compose 操作，不保證 Docker 自動重啟 PostgreSQL 時也重啟 App。healthcheck 只確認程序存活，不代表 AI、資料庫或 PDF 全部可用。

### 含公版參考的 Docker 模式

需要顧問查找公版時，在基本配置上加上 `compose.jd-app.rag.yaml`。兩種模式共用 `caliburn-jd-app` project、App 與 PostgreSQL，不另外開第二套產品。公版模式多了查詢 API `ocs-indexer`、Qdrant 與 GPU 模型服務 `embedder`；它們啟動後持續運行，顧問需要資料時才查詢，不必等到第一次提問才啟動容器。

此模式沿用現有 NVIDIA CUDA 模型服務，需要 Docker Compose `2.30.0` 以上（支援 `gpus` 設定），以及 Docker Desktop／WSL2 可使用的 NVIDIA GPU，詳見 [Compose GPU 設定](https://docs.docker.com/reference/compose-file/services/#gpus)與 [Windows GPU 支援](https://docs.docker.com/desktop/features/gpu/)。首次下載、載入模型可能較久；啟動最多等待 900 秒，失敗時先檢查紀錄，不反覆重送。這份配置不保證 CPU 模式或各 GPU 型號都能使用。

**首次準備：** 先完成上方基本模式的資料庫初始化，再依序準備 RAG。整個過程不需要 OpenAI 請求。

1. 在根 `.env` 設定 `CALIBURN_REFERENCE_COLLECTION`，例如 `ocs_references_20261006`，指定本次使用的公版索引。`CALIBURN_REFERENCE_CANDIDATE_LIMIT` 預設 20，是檢索服務的候選數量上限，不是模型參數。
2. 準備 `./data/selected-ocs`，只放本次選用的 OCS JSON，每個 OCS code 一份。這個目錄由操作者準備，啟動不自動選版、解析 PDF 或建立示範資料。
3. 建置查詢 API／模型映像，啟動 Qdrant 與模型，再一次性建新索引。下例的 collection 名稱須與根 `.env` 一致：

```powershell
& {
    $sourceDirectory = (Resolve-Path './data/selected-ocs' -ErrorAction Stop).Path
    if (!(Test-Path -LiteralPath $sourceDirectory -PathType Container)) { throw '來源必須是已存在的目錄。' }
    docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag build ocs-indexer embedder
    if ($LASTEXITCODE -ne 0) { throw 'RAG 建置失敗。' }
    docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag up -d --wait --wait-timeout 900 qdrant embedder
    if ($LASTEXITCODE -ne 0) { throw 'RAG 基礎服務未就緒，請檢查紀錄。' }
    docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag run --rm --volume "${sourceDirectory}:/sources:ro" ocs-indexer jd-ocs-indexer index-references /sources --collection ocs_references_20261006
    if ($LASTEXITCODE -ne 0) { throw '索引未完成，請勿將此 collection 視為可用。' }
}
```

來源目錄只在建索引時唯讀掛載，之後 API 從 Qdrant 讀取已固定的來源，不需掛載原 JSON。`index-references` 不覆寫既有 collection，完整寫入後才發布就緒標記（ready manifest）。已有相容、完整的 collection 時，可略過建索引，不必每次啟動重建。失敗索引保留原狀；修正後另選新名稱，不自動刪除。

**日常啟動與查詢檢查：**

```powershell
pnpm docker:rag:up
# 等同下列命令；沒有 pnpm 也可直接使用：
# docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag up -d --wait --wait-timeout 900
```

`--wait` 等待服務通過健康檢查，但 `/healthz` 不檢查公版 collection 是否已建好。使用前再執行一次實際公版搜尋，確認索引與嵌入、重排序模型相容。下例只使用本機 GPU，不呼叫 OpenAI：

```powershell
docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag exec -T ocs-indexer python -c "import json, urllib.request; request = urllib.request.Request('http://127.0.0.1:8000/occupation-references:search', data=json.dumps({'query':'負責收貨、庫存盤點及帳實差異追蹤','limit':1}).encode('utf-8'), headers={'Content-Type':'application/json'}); result=json.load(urllib.request.urlopen(request, timeout=120)); print('公版搜尋成功，候選數：', len(result['references']))"
```

這只確認搜尋可用，不能以一次成功判定相關性或 JD 品質。索引未 ready／不相容回 409，連線故障回 503，不當成查無資料。查詢 API 的設定與來源契約見 [RAG README](../apps/ocs-indexer/README.md#職位整體參考-api)。

| 操作 | 命令 |
|---|---|
| 看完整模式的容器狀態 | `docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag ps` |
| 看 RAG 服務紀錄 | `docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag logs --tail 100 ocs-indexer embedder qdrant` |
| 停止完整模式 | `pnpm docker:rag:stop` |

App 經 `http://ocs-indexer:8000` 查詢；RAG 三個服務不發布主機連接埠，也不接收 OpenAI key。App 的啟動相依仍只有 PostgreSQL；RAG 故障不終止基本訪談／人工 JD 功能，相關工具會回報錯誤。切換模式仍須讓已綁定公版工具的 A／Memory 工作結束，再在安全點停止原 App；不要在暫停或執行中的工作換掉工具設定。

由完整模式改回基本模式時，先執行 `pnpm docker:rag:stop`，再執行 `pnpm docker:up`。Compose 會依基本配置重建同一個 App，保留原資料。若 App 的外部 key 檔另有 `CALIBURN_OCCUPATION_REFERENCE_URL`，還須移除該設定才能關閉工具。反向切換時也先在安全點停下原 App，再使用完整模式，不同時運行兩個 App。

兩種模式共用 `caliburn-jd-app_jd_postgres_data`。完整模式另有 `caliburn-jd-app_qdrant_storage` 與 `caliburn-jd-app_hf_cache`；不自動沿用獨立 RAG project 的舊 volume，也不移除它們。舊索引若需遷移，另行備份與驗證還原；不可讓兩個 Qdrant 同時掛同一份儲存。基本模式的 `docker:stop` 不會停止額外的 RAG 容器，請使用對應模式的停止命令。兩種模式都不使用 `down -v`。

更新完整模式時，在安全點停止 App／RAG，備份 PostgreSQL 與 Qdrant，再明示建置 `app ocs-indexer embedder`；如需 migration，沿基本模式的一次性命令完成，最後啟動完整模式。更新程式不覆寫索引；來源或模型身分變動時，另建新 collection 並重新做搜尋檢查。

設定解析、鎖定安裝與 API 回歸結果見 [公版 Docker 驗證](experiments/engineering/2026-10-06-docker-rag-startup.md)。真容器與 GPU 的已驗／未驗範圍在該頁分開記錄。

### DataGrip 與診斷

| 欄位 | 預設值 |
|---|---|
| Host／Port | `127.0.0.1`／`55440`（改埠後依根 `.env`） |
| Database／User | `caliburn`／`caliburn` |
| Password | 根 `.env` 的 `CALIBURN_POSTGRES_PASSWORD` |
| Schema | 勾選 `caliburn`，不是 `public` |

建議另設唯讀連線。既有 AI 執行紀錄的查閱方式不變：在原生開發環境將 `CALIBURN_DATABASE_URL` 設為上述主機連線，沿下方[執行紀錄](#在-datagrip-查某個職務檔案的-ai-執行紀錄)執行 `apps/api/scripts/refresh_execution_diagnostics.py`，再從 DataGrip 查 VIEW。此開發診斷腳本不在執行映像中；不另造一份診斷來源。

配置、PDF、資料保存及已驗範圍見 [Docker 交付驗證](experiments/product-validation/2026-10-03-docker-delivery.md)。

## 安裝依賴

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

以下為原生開發方式。Node／TypeScript 只使用 `pnpm-lock.yaml`；Python 只使用 `apps/api/uv.lock`。不要產生 npm lockfile，也不要用 RAG Compose 建立 JD App 的資料庫。

## 第一次初始化

1. 建立一個**空的**專用 PostgreSQL database（不要沿用舊產品的資料庫；本版不搬移舊資料）。
2. 以環境變數明示連線，密碼由本機秘密管理注入，不貼在命令列歷史、文件或 Git：

```powershell
$env:CALIBURN_DATABASE_URL = 'postgresql://帳號:密碼@127.0.0.1:5432/caliburn'
$env:CALIBURN_DATABASE_SCHEMA = 'caliburn'      # 預設值；可省略
pnpm app:migrate                                 # 建立 namespace 並升級到最新 schema，可重跑
pnpm app:status                                  # 診斷；不印出密碼或 key
pnpm build                                       # 建置 Web，供 `pnpm start` 同源提供
```

`app:migrate` 負責 App 業務 schema 的建立與升級。啟動只核對 migration head：未初始化或版本不符會啟動失敗，並提示執行 `pnpm app:migrate`；它不自動升級業務 schema、清資料或重建 volume。LangGraph 的 checkpoint 表則由官方 saver 在啟動時建立。

PowerShell 的 `$env:…` 只對目前視窗及其啟動的程序有效。換新視窗後，須重新提供相同的資料庫／schema 與所需 PDF 設定；不會從 `apps/api/.env` 載入這些設定。這裡的空白資料庫要求只適用於首次安裝，更新目前 App 時沿用原資料庫。

## AI credential

二擇一，後端只讀 `OPENAI_API_KEY` 這一項：

- 環境變數 `OPENAI_API_KEY`；
- 或 `apps/api/.env`（已被 Git 忽略）內**唯一一行** `OPENAI_API_KEY=...`，`pnpm start`／`pnpm dev` 會自動以 `--key-file` 載入。

key 不進 prompt、模型工具、Web bundle、URL、資料庫、checkpoint、一般 log 或 Git。檔案存在時，根啟動器以 `--key-file` 載入的 key 為準；不要同時保留兩份不同金鑰。`pnpm app:status` 不讀取此檔案，判讀方式見[診斷](#診斷)。沒有 key 時人工 JD 仍可使用，AI 訪談明示停用，且不會自動 fallback。更換 key 後須重啟後端。

注意：後端啟動時會續跑已接受但未完成的訪談與背景整理，這可能消耗模型額度；只想操作人工 JD 時不要提供 key。

## 日常啟動與停止

先啟動已初始化的 PostgreSQL，再於根目錄執行：

```powershell
pnpm start    # 單一後端程序同源提供建置後的 Web：http://127.0.0.1:8100/
pnpm dev      # 開發：後端 :8100 與 Vite :5173 同時前景啟動：http://127.0.0.1:5173/
```

`pnpm start` 需要先 `pnpm build`；沒有建置會明確報錯，不自動建置或猜目錄。在原終端按 Ctrl+C 正常停止：後端先停止新准入、保存已取得的結果並停在可恢復邊界，再釋放資源；強制關閉仍依最後可靠位置恢復。重開後，進行中或暫停的訪談可由介面找回並續作；背景整理由系統依持久狀態自動承接。

隔離驗證時若前端使用第二個埠，可在**後端啟動前**設定 `CALIBURN_DEV_ORIGIN=http://127.0.0.1:5174`（只接受一個帶明確埠的 loopback HTTP origin），見[後端 README](../apps/api/README.md)。

## 更新已有安裝

先讓工作停在安全點，正常停止自己啟動的 App，備份原資料庫。沒有未提交修改且分支沒有分歧時，從專案根目錄執行：

```powershell
git pull --ff-only
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
# 在此終端提供原 CALIBURN_DATABASE_URL／schema 與所需 PDF 設定。
pnpm app:migrate
pnpm build
pnpm start
```

不要因為 migration 或分支更新失敗就重建資料庫、刪 volume 或強制覆蓋工作。`git pull` 拒絕快轉時先核對本機差異；歷史修正的提交對照見[歷史查閱](history.md)。更新 Playwright 套件後，還需按下節重新安裝對應瀏覽器。

## PDF 匯出

匯出正式 JD 的中文 PDF 需要兩項，缺少時 `GET /api/job-files/{id}/jd/export.pdf` 回 503，不下載空檔：

```powershell
$env:CALIBURN_PDF_FONT_PATH = 'D:\fonts\NotoSansTC-VF.ttf'              # 已授權的中文字型
uv run --project apps/api --locked python -m playwright install chromium --only-shell   # 鎖定版本的瀏覽器
# 或指定與已鎖 Playwright 相容的 Chromium：$env:CALIBURN_PDF_CHROMIUM_PATH = '...\chrome.exe'
```

PDF 只匯出正式 JD、不含候選與員工姓名；畫面中文正確，部分字型的文字複製／搜尋會出現部首字元（已知限制，見 [T13](history.md#source-409f20a1c297740aed7d)）。

字型必須使用實際可讀的檔案，下載方式見 [Noto CJK 官方指南](https://github.com/notofonts/noto-cjk/blob/main/Sans/README.md)。如果安裝瀏覽器時自訂了 `PLAYWRIGHT_BROWSERS_PATH`，後端啟動時也要提供相同值。新的終端需重新提供字型與自訂瀏覽器路徑；設定完成後重啟後端才生效。

## 診斷

| 現象 | 查什麼 |
|---|---|
| 檢查目前終端的設定 | `pnpm app:status`：核對環境變數及資料庫連線／migration；不代表正在執行的後端狀態，見下方判讀說明 |
| 後端啟動失敗並提到 migration | 資料庫尚未初始化或版本不符：`pnpm app:migrate` |
| `POST /inputs` 回 503 `model_not_configured` | 沒有 OpenAI key（或後端啟動前未設定）；人工 JD 不受影響 |
| 瀏覽器或 CLI 收到 403 | 精確 Host／Origin 檢查：只接受 `127.0.0.1`／`localhost`／`[::1]` 的 5173／8100（及明示的一個 dev origin） |
| `GET /api/health` | 只表示程序存活，不表示資料庫或模型可用 |
| 訪談失敗或結果不明 | 介面顯示安全的失敗原因，原輸入保留；技術診斷在後端 log（只含穩定 ID、階段、錯誤類別，不含原話或 payload） |
| 一輪訪談很久沒有回應 | 多半是 OpenAI 帳戶的每分鐘 token 上限（TPM）在限流，後端 log 會出現 `Provider request failed: … failure=rate_limited`。系統會照服務建議的時間自動多等（沒有建議時 10 秒起、60 秒封頂），**不算失敗**，單輪最長等到工作期限（預設 30 分鐘）；可隨時取消該輪。TPM 200K 的帳戶上，一場 12 輪訪談約 6–25 分鐘；要更快請改用更高 TPM 的帳戶 |
| 訪談或背景整理全部立刻失敗，後端 log 為 `failure=access_blocked … provider_code=credit_balance_exhausted` | OpenAI 帳戶儲值額度用完（HTTP 429，但不是限流）。系統不重試、原輸入保留、該次處理標為失敗；補額度後重新送出原輸入 |
| 資料庫剛重啟（或被外力中止）後，讀訪談狀態的端點回 500，`/api/health` 仍是 ok | **重啟後端**。leader 鎖與 checkpoint 連線各只持一條資料庫連線、不會自動重連，這是刻意的單一 leader 設計；重啟時系統會恢復已保存的進行中工作（能續作則續作，否則安全終止、原輸入保留，之後可重送） |

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
```

兩個範圍參數擇一；不用 API key。資料庫須已升級到目前 migration；若尚未升級，先沿[更新流程](#更新已有安裝)停止 App，再執行 `pnpm app:migrate`，不是每次查詢都遷移。沒有 execution 的既存空檔案回報 0 筆，找不到的 UUID 則報錯。若權限、migration、原生紀錄解碼或並行更新出錯，整次匯入回滾，原診斷副本仍保留。終端只印成功筆數或錯誤類別，避免洩露私人 payload。

DataGrip 展開 `caliburn → views`，可直接雙擊下列 VIEW，再用 `job_file_id` 或 `execution_id` 篩選：

| VIEW | 每列代表什麼 | 主要欄位 |
|---|---|---|
| `diagnostic_execution_history` | 一輪 A 或一批 Memory（包含失敗／取消） | 檔案名稱、原輸入、正式答覆、正式序號、狀態、失敗嘗試、JD 候選狀態／修訂、已發布 Memory 快照 |
| `diagnostic_model_steps` | 一份已保存的原模型回應，不等於業務 Step 已完成 | A／B1／B2 role、response_order、request（含 instructions、input、tools）、response（含輸出與 usage）、thread／checkpoint、snapshot_at |
| `diagnostic_tool_calls` | 上述回應的一次 function call | 工具名稱、原 arguments、call_id、對應 output、結果是否已保存 |

例如整個檔案的操作：

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

`request` 就是保存的當時請求（敏感欄位已遮蔽），可在 DataGrip 展開 JSON 看 context、指引與工具說明。`response` 可看公開訊息、可讀推理摘要與原工具要求；舊模型沒有回傳摘要時不會補造。`response_order` 是本次擷取中已保存回應的觀察順序，不是重試次數，也不是跨程序精確時鐘。

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

- 總覽的業務狀態、正式訪談序號與嘗試統計是即時 JOIN；訪談文字、模型／工具正文均經遮蔽，是 `snapshot_at` 那次擷取。`snapshot_at IS NULL` 表示尚未匯入；有時間且回應數 0 表示該次未找到已保存回應。新進展須再次執行匯入命令，DataGrip Refresh 本身不會解碼新增 checkpoint。
- `recorded` 只表示取得工具回傳，內容仍可能是錯誤；`not_recorded` 表示未找到保存結果，不能推定未執行或失敗。正式效果仍由 JD／Memory 原結果判定。
- 包含本 execution 各階段留下的原模型回應及 pending writes，可能含後來放棄的工作。不能把診斷項目當成正式訪談來源，或把模型回應 `completed` 當整輪成功。
- 副本遮蔽 `encrypted_content`、已知憑證欄位及可辨識的 key 字串，**不是完整匿名化**。仍含原訪談與工作內容；不自動匯出、不提交 Git。DataGrip 可將核准的合成結果另存 JSON／CSV 供錄影或報告使用。一般 log 仍不含這些正文。
- VIEW 沿用查詢者的資料庫權限；建議在 DataGrip 開啟唯讀連線。它不是跨使用者授權或資料隔離 API。

設計取捨、測試及版本見 [T06 診斷查閱證據](history.md#source-6ac54c64f9ded4edcb9e)。

## 資料庫與備份

**首版成品驗收不以備份／空庫還原為前置。**目前優先驗證既有 PostgreSQL／checkpoint 在一般中斷與重開後能查回已確認保存的訪談、JD 與進度；未送出的輸入或未保存草稿不保證意外關閉後找回。備份資訊供後續維護參考，不表示已完成完整還原端到端驗收：

- 備份整個資料庫（`pg_dump` 不要用 `-n` 只挑單一 schema）；關聯式資料與 checkpoint 表在同一 namespace，兩者屬同一資料範圍。
- OpenAI key 不在備份內；在另一台電腦還原後須重新提供 key。瀏覽器 localStorage／sessionStorage 不是正式資料備份。
- 不自動清資料、刪 volume 或重建資料庫；資料處置需先核對精確目標。

## 驗證

```powershell
pnpm check
```

也可使用窄命令：`pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build`。`pnpm test` 不需資料庫；真 PostgreSQL 整合測試需明確指定隔離的 loopback `_test` 資料庫並直接執行 pytest：

```powershell
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://測試帳號:密碼@127.0.0.1:5432/caliburn_test'
uv run --project apps/api --locked pytest apps/api/tests -m postgres -q
```

測試各自建立並回收隨機 schema，不碰既有資料。真 PostgreSQL、真瀏覽器與真模型結果分開記錄；離線測試不能代替 provider 或 UI 證據。付費驗證腳本須依 manifest 明示的有限預算執行（見各任務證據）。Windows 受限 token 可能讓暫存目錄權限出現 `WinError 5`，不得為測試變綠而放寬安全限制。

## RAG（獨立服務、非 JD App 預設依賴）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract` 不在 JD App dependency graph。只有明確執行下列命令才啟動：

```powershell
pnpm rag:up
pnpm rag:dev
pnpm rag:down
```

依 [ADR0080](adr/0080-opt-in-public-reference-agent-tools.md)，App 可透過明示 URL 使用公版參考 HTTP 工具；未配置時不建立 client，不自動啟動上述服務。上列命令供獨立開發；若要 App 與 RAG 一起啟動，使用[公版 Docker 模式](#含公版參考的-docker-模式)，不用另執行 `rag:dev`。啟用及執行中請求的設定邊界見 [API README](../apps/api/README.md#公版參考工具的可選啟用)。獨立管線沿 [`design/rag-pipeline.md`](design/rag-pipeline.md)。有人正在測試時，不為啟用工具重啟共用程序、改既有 `.env`、更新正式 schema 或清索引。
