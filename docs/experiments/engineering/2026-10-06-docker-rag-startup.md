# Docker 公版參考模式：配置與套件驗證

本次新增可選的 Docker 公版參考模式：在原 App＋PostgreSQL 之外，加入獨立的查詢 API、Qdrant 與 GPU 模型服務。修改涵蓋交付配置與操作文件，檢索方法、Agent、工具契約及資料保存方式不變。配置與套件測試已通過；Linux 容器建置與 GPU 搜尋尚未驗證，須待 Docker 引擎可用後補測。

## 問題與選擇

原先 `compose.jd-app.yaml` 只啟動 App／PostgreSQL；根 `docker-compose.yml` 啟動 Qdrant／GPU，查詢 API 還要另外在主機執行。只開啟 `rag` profile 也不會替 App 設定查詢服務的 URL，因此無法以一個命令啟動完整公版參考功能。

採用基本 Compose 加可選延伸檔，重用既有 Qdrant／GPU 服務，不複製其映像與模型設定。查詢 API 另以自己的 lockfile 和契約套件建置。App 透過服務 DNS 查詢，不增加程序控制器、不掛 Docker socket，也不把檢索套件放入 App。

實作順序為：先檢查原權責與官方配置規則，再加入實際 Compose 解析測試，建立 API 映像與延伸配置，最後驗證鎖定安裝、API 回歸與文件一致性。純設定使用配置解析驗證，不將「延伸檔尚不存在」的測試失敗稱為業務 TDD 證據。

參考來源及本案採用的部分：

- [Compose 多檔合併](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)：基本模式與可選延伸檔，共用原 App／資料庫配置。
- [Compose extends](https://docs.docker.com/compose/how-tos/multiple-compose-files/extends/)及[覆寫規則](https://docs.docker.com/reference/compose-file/merge/)：重用獨立 RAG，清除主機埠，明示宣告 volume。
- [服務網路](https://docs.docker.com/compose/how-tos/networking/)及[啟動相依](https://docs.docker.com/compose/how-tos/startup-order/)：內網 DNS、等待依賴 healthcheck；不將啟動順序當業務恢復機制。
- [uv Docker 指南](https://docs.astral.sh/uv/guides/integration/docker/)：鎖定依賴、多階段建置、非 editable 套件及獨立執行環境。

這些是各工具的官方做法；服務選用、資料權責與切換安全點仍依 Caliburn 的 ADR0080 及操作規範。

## 範圍與環境

- 基準：`7a969ee6c`，分支 `docker-rag-startup`；本頁描述該基準上的配置修改，不改原實驗資料。
- Docker CLI 29.8.0、Compose 5.5.1；當輪 Docker Desktop Linux engine pipe 不存在。
- 查詢 API 使用既有 `apps/ocs-indexer/uv.lock`；uv 0.12.20。本機非 editable 安裝以 Python 3.14.0 驗證，Dockerfile 沿 App 的 Python 3.14.8 Linux 基底，兩者不視為同一執行環境。
- 測試使用合成 key／密碼、fake provider 及本機 Qdrant 模式；沒有 OpenAI 請求、真員工資料、正式 DB／volume 操作或新索引建立。
- 暫存環境在 `.research-tmp/docker-rag-validation`，不隨 Git 發布，也不取代現有開發環境。

## 驗證方法與結果

| 層級 | 命令或方法 | 結果與支持範圍 |
|---|---|---|
| Compose 實際解析 | `node --test scripts/docker-compose.test.mjs`／`pnpm test:docker` | 6 項通過；使用 Docker 自身的 `config --format json`，不是比對 YAML 字串 |
| 鎖定依賴安裝 | `uv sync --project apps/ocs-indexer --locked --python 3.14 --extra api --no-dev --no-install-project --no-editable`，再移除 `--no-install-project` | 兩階段皆成功，兩個本地契約與查詢 API 可非 editable 安裝 |
| API／檢索回歸 | 在隔離環境加入鎖定的 `--extra dev`，執行 `python -B -m pytest apps/ocs-indexer/tests -o addopts='' -q -p no:cacheprovider` | 81 項通過；含公版來源固定性、查詢、API 錯誤與既有檢索行為，不等於真 Qdrant／GPU 驗證 |
| App 可選設定 | `uv run --project apps/api --locked pytest apps/api/tests/unit/test_occupation_reference_configuration.py -q -p no:cacheprovider` | 43 項通過；含服務 DNS origin、預設停用與生命週期 |
| 原生入口回歸 | `node --test --test-isolation=none scripts/run-app.test.mjs` | 5 項通過，原生啟動方式未變 |
| 專案離線品質檢查 | `pnpm run check` | exit 0；lint、型別、契約生成檢查與前端建置通過，後端單元／契約 1,407 項、前端 285 項、啟動入口 5 項通過；未包含真 PostgreSQL、瀏覽器旅程或模型品質驗證 |
| CLI 安裝入口 | 隔離環境的 `jd-ocs-indexer --help` | 可執行，包含 `serve` 與 `index-references`；沒有啟動服務或建立索引 |
| 安裝身分／文件 | 套件 `direct_url.json`、修改文件的本機連結與錨點、PowerShell Parser 與格式檢查 | 三套件皆 `editable: false`；338 個本機連結有效，其中 116 個錨點存在；24 段 PowerShell 無語法錯誤；新增腳本與 package.json 通過 Prettier |

Compose 測試核對：基本模式只有原兩服務；完整模式恰有五服務，project、PostgreSQL 配置與原資料 volume 不變；URL 使用容器服務名稱；只有 API 等待檢索依賴，App 仍只依賴 PostgreSQL；RAG 不發布主機埠、不接收 OpenAI key；索引 collection 必須明示；自訂 App 埠仍綁 loopback。

獨立審查另發現，GPU 配置原繼承 `image: caliburn-embedder:local`，即使隔離 project 的 volume 不同，建置仍更新共用 tag。新增兩個 project 的解析反例，先重現 `embedder.image` 仍為共用名稱的失敗，再以 `image: !reset null` 清除延伸檔繼承的名稱，改由 Compose 按 project 命名。修正後六項通過；原獨立開發 Compose 不變。這證明配置不再指定共用 tag，未以此冒充已驗真映像建置。

測試最初受 Windows 沙箱的子程序／uv 快取存取限制阻擋，改為核准的沙箱外驗證，未放寬產品權限。配置建立前是 1 項通過、4 項因缺少延伸檔失敗；加入配置後 5 項通過。API 回歸另出現兩個既有 warning：Starlette TestClient 的 httpx 棄用提示，以及本機 Qdrant 不支援 payload index 的提醒。這些不當成容器或真資料庫的通過證據。

前端建置另有既有的 chunk 大於 500 kB 提示，建置成功；本次未調整前端打包方式。

## 必須留給真環境的檢查

Docker 引擎不可用，因此當輪未建置 Linux API 映像、未驗 GPU passthrough／模型下載、未執行容器 healthcheck，也未驗證「首次建索引 → 啟動完整模式 → App 呼叫公版」或兩模式的真容器切換。這些是交付整合檢查，不是待新增的產品功能。

引擎可用時，依[操作手冊](../../runbook.md#含公版參考的-docker-模式)，使用隔離 project 與新 volume 驗證，不使用正式資料：

1. 建置 App／API／模型；核對 API 非 root、唯讀執行與不帶金鑰、開發來源。
2. 明示初始化測試 PG 與選版索引，實際搜尋一次，核對候選及固定來源。
3. 核對 App consumer 工具可取得資料，以及 RAG 故障不被當空結果。
4. 安全切換兩模式，核對同一份 PG、舊 volume 未刪除，且沒有第二個 App。

`/healthz` 不驗公版 ready manifest；不能因 `up --wait` 成功就略過實際搜尋。失敗索引保留原狀、另選新名稱，啟動不自動覆寫、清除或重建。舊獨立 RAG 的 volume 不自動搬入新 project。
