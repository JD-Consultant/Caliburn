# 公版參考與 RAG 操作

本頁供已啟動基本 App、需要增加公版查找的操作者使用。基本訪談、人工 JD 與 PDF 不依賴 RAG；本頁另列[獨立 RAG 開發](#獨立-rag-開發)入口。

查詢 API 的四條模型檢索路由在派工前共用單一准入，最多等五秒；逾時或關閉中回 503，health 及純讀取仍沿獨立路徑。這是准入期限，不是模型執行或關閉的硬期限。取消已派工請求會等實體 worker 結束再關共用 clients，沒有放大全域 thread pool。

## 含公版參考的 Docker 模式

需要顧問查找公版時，在基本配置上加上 `compose.jd-app.rag.yaml`。兩種模式共用 `caliburn-jd-app` project、App 與 PostgreSQL，不另外開第二套產品。公版模式多了查詢 API `ocs-indexer`、Qdrant 與 GPU 模型服務 `embedder`；它們啟動後持續運行，顧問需要資料時才查詢，不必等到第一次提問才啟動容器。

此模式沿用現有 NVIDIA CUDA 模型服務，需要 Docker Compose `2.30.0` 以上（支援 `gpus` 設定），以及 Docker Desktop／WSL2 可使用的 NVIDIA GPU，詳見 [Compose GPU 設定](https://docs.docker.com/reference/compose-file/services/#gpus)與 [Windows GPU 支援](https://docs.docker.com/desktop/features/gpu/)。首次下載、載入模型可能較久；啟動最多等待 900 秒，失敗時先檢查紀錄，不反覆重送。這份配置不保證 CPU 模式或各 GPU 型號都能使用。

### 首次準備

先沿[第一次使用](getting-started.md)完成基本模式的資料庫初始化，再依序準備 RAG。整個過程不需要 OpenAI 請求。

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

### 日常啟動與查詢檢查

首次由基本模式切換時，先讓原 App 的工作停在安全點並停止 App，再執行下列命令。之後若要關閉或更換公版工具，已綁定工具的 A／Memory 工作須先完成；不要在工作暫停或執行中換設定。

```powershell
docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag up -d --wait --wait-timeout 900
```

已安裝 pnpm 時，可用 `pnpm docker:rag:up`／`pnpm docker:rag:stop` 作為相同 Compose 命令的捷徑。

`--wait` 等待服務通過健康檢查，但 `/healthz` 不檢查公版 collection 是否已建好。使用前再執行一次實際公版搜尋，確認索引與嵌入、重排序模型相容。下例只使用本機 GPU，不呼叫 OpenAI：

```powershell
docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag exec -T ocs-indexer python -c "import json, urllib.request; request = urllib.request.Request('http://127.0.0.1:8000/occupation-references:search', data=json.dumps({'query':'負責收貨、庫存盤點及帳實差異追蹤','limit':1}).encode('utf-8'), headers={'Content-Type':'application/json'}); result=json.load(urllib.request.urlopen(request, timeout=120)); print('公版搜尋成功，候選數：', len(result['references']))"
```

這只確認搜尋可用，不能以一次成功判定相關性或 JD 品質。索引未 ready／不相容回 409，連線故障回 503，不當成查無資料。查詢 API 的設定與來源契約見 [RAG README](../../apps/ocs-indexer/README.md#職位整體參考-api)。

| 操作 | 命令 |
|---|---|
| 看完整模式的容器狀態 | `docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag ps` |
| 看 RAG 服務紀錄 | `docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag logs --tail 100 ocs-indexer embedder qdrant` |
| 停止完整模式 | `docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag stop` |

App 經 `http://ocs-indexer:8000` 查詢；RAG 三個服務不發布主機連接埠，也不接收 OpenAI key。App 的啟動相依仍只有 PostgreSQL；RAG 故障不終止基本訪談／人工 JD 功能，相關工具會回報錯誤。

Indexer 自建的 embedding、rerank 與 Qdrant HTTP client 使用明示目的地，不採用 shell 的 `HTTP_PROXY`／`HTTPS_PROXY`／`ALL_PROXY` 或環境憑證設定（HTTPX `trust_env=False`）。明示 URL、反向代理路徑與 Qdrant API key 仍由既有配置傳入；注入的外部 client 則由 caller 負責其路由與生命週期。Qdrant client 1.18.0 的選用背景版本探針另建 HTTP client，未沿用上述設定，因此關閉該探針；部署更新仍須核對 lock 中的 client 與 Compose server 版本並執行實際搜尋，不以背景警告替代相容性驗收。依據：[HTTPX 環境設定](https://www.python-httpx.org/environment_variables/)、[Qdrant 版本探針原碼](https://github.com/qdrant/qdrant-client/blob/v1.18.0/qdrant_client/common/version_check.py)。

由完整模式改回基本模式時，先依上表停止完整模式，再依[基本模式](README.md#日常啟停與更新)啟動。Compose 會依基本配置重建同一個 App，保留原資料。若 App 的外部 key 檔另有 `CALIBURN_OCCUPATION_REFERENCE_URL`，還須移除該設定才能關閉工具。反向切換時也先在安全點停下原 App，再使用完整模式，不同時運行兩個 App。

### 更新與保存

兩種模式共用 `caliburn-jd-app_jd_postgres_data`。完整模式另有 `caliburn-jd-app_qdrant_storage` 與 `caliburn-jd-app_hf_cache`；不自動沿用獨立 RAG project 的舊 volume，也不移除它們。舊索引若需遷移，另行備份與驗證還原；不可讓兩個 Qdrant 同時掛同一份儲存。基本模式的停止命令不會停止額外的 RAG 容器，請使用對應模式的停止命令。兩種模式都不使用 `down -v`。

更新完整模式時，在安全點停止 App／RAG，備份 PostgreSQL 與 Qdrant，再明示建置 `app ocs-indexer embedder`。若先前已停止整套服務，先用 `docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag up -d --wait postgres` 啟動並等候資料庫就緒；失敗就停止更新。接著用 `docker compose -f compose.jd-app.yaml -f compose.jd-app.rag.yaml --profile rag run --rm app alembic -c /opt/caliburn/alembic.ini upgrade head` 升級資料庫，成功後才啟動完整模式。

這裡不使用基本模式的初始化腳本，以免提前啟動未帶公版設定的 App。更新程式不覆寫索引；來源或模型身分變動時，另建新 collection 並重新做搜尋檢查。

設定解析、鎖定安裝與 API 回歸結果見 [公版 Docker 驗證](../experiments/engineering/2026-10-06-docker-rag-startup.md)。真容器與 GPU 的已驗／未驗範圍在該頁分開記錄。

## 獨立 RAG 開發

獨立 `docker-compose.yml` 只含 Qdrant 與模型服務 `embedder`：Qdrant `6333`（REST）／`6334`（gRPC），以及 `embedder` `8082`（`/embed`、`/rerank`、`/health`，不是查詢 API），明確只發布至 `127.0.0.1`，供本機開發存取。公版查詢 API 由 `pnpm rag:dev` 在本機 `127.0.0.1:8000` 啟動；正式 App overlay 的 `ocs-indexer`、Qdrant 與 `embedder` 都只使用 Compose 內部網路，App 經 `http://ocs-indexer:8000` 查詢。設定驗收檢查兩種模式解析後的 ports，不啟動 GPU 或重建索引。依據：[Docker port publishing](https://docs.docker.com/engine/network/port-publishing/)。

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 及共用契約套件不在 JD App 的套件依賴內。獨立開發時依用途執行：

| 操作 | 命令 |
|---|---|
| 啟動 Qdrant 與 embedder 容器 | `pnpm rag:up` |
| 啟動本機查詢 API 開發程序 | `pnpm rag:dev` |
| 停止 Qdrant 與 embedder 容器 | `pnpm rag:down`；本機開發程序在原終端按 Ctrl+C |

依 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)，App 可透過明示 URL 使用公版參考 HTTP 工具；未配置時不建立 client，不自動啟動上述服務。上列命令供獨立開發；若要 App 與 RAG 一起啟動，使用[公版 Docker 模式](#含公版參考的-docker-模式)，不用另執行 `rag:dev`。啟用及執行中請求的設定邊界見 [API README](../../apps/api/README.md#公版參考工具的可選啟用)。有人正在測試時，不為啟用工具重啟共用程序、改既有 `.env`、更新正式 schema 或清索引。

解析與索引的本機命令、設定及測試分別由 [pdf-to-json README](../../apps/pdf-to-json/README.md)、[indexer README](../../apps/ocs-indexer/README.md)維護，模型服務見 [embedder README](../../apps/embedder/README.md)。服務分工與資料保存邊界見 [RAG 架構](../architecture/rag-pipeline.md)。
