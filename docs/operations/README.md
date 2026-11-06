# Caliburn 操作手冊

標準部署包含一個 FastAPI 應用程序、PostgreSQL 與 Qdrant。首次部署沿[快速開始](getting-started.md)，原生開發沿[開發初始化](native-development.md)，來源與索引維護沿[公版操作](rag.md)。

## 啟停與狀態

在 repository 根目錄操作同一份 Compose：

```powershell
docker compose up -d --wait
docker compose ps
docker compose logs --tail 100 app
docker compose stop
```

已有根 pnpm 依賴時，可用 `pnpm docker:up`、`pnpm docker:status`、`pnpm docker:stop`。停止容器不刪 volumes；不要以刪 volume 作一般故障修復。原生開發使用 `pnpm dev`，正式同源模式使用 `pnpm build` 後 `pnpm start`，詳見[原生開發](native-development.md)。

`pnpm app:status` 對原生後端設定作唯讀診斷，不啟動模型或遷移；Docker 狀態則以 Compose 及應用 health 核對。容器健康不保證公版來源、索引、權重與模型憑證可用。

## 設定與載入

| 檔案／環境 | 責任 |
|---|---|
| 根 `.env` | Compose 的資料庫密碼、host ports、掛載位置；由 `.env.compose.example` 建立。 |
| 根 `.local/app.env` | Docker 應用的 Agent、Checkpoint 與 provider 秘密設定；可用 `CALIBURN_APP_ENV_FILE` 改位置。 |
| 根 `.local/` | 唯讀掛入容器 `/opt/caliburn/local`，放 Agent JSON 與既有模型 cache；可用 `CALIBURN_LOCAL_DIRECTORY` 改位置。 |
| `docker/reference.json` | 容器公版設定；可用 `CALIBURN_REFERENCE_CONFIG_FILE` 指向另一份。容器 Qdrant 位址是 `http://qdrant:6333`。 |
| `apps/backend/.env` | 原生後端環境，由根 launcher 透過 uv 載入，與根 Compose `.env` 分開。 |

配置在啟動時載入，沒有熱更新。停用 Agent 後仍保留其 Checkpoint 連線，讓整份 Workspace 刪除能清理原保存點；停用不等於刪資料。Plugin 選取與相容版本見 [Agent 設定](../../apps/backend/src/caliburn/modules/agent/README.md#明示設定)。

## 更新與備份

更新前先停止寫入並備份同一時點的 PostgreSQL 業務／Checkpoint 資料、Qdrant snapshot、來源 JSON／PDF、模型版本及必要設定。秘密備份須受控；Git 忽略不是備份。不同 collection 的舊來源永久回讀不在目前契約內，換索引前先確認引用保存需求。

取得新程式後重新 build，明示遷移，再啟動：

```powershell
docker compose stop app
docker compose build app
docker compose run --rm app python -m caliburn.migrate upgrade head
docker compose up -d --wait
```

官方 Saver 需要初始化或升級時，才在遷移命令加 `--with-checkpoints`。破壞性 Node／Tool／State 契約變更須同步 `resume_version`，不相容的未完成輪不會猜測恢復。遷移只適用本專案維護的資料格式；未提供相容遷移的資料庫不得直接套用升級命令。

## 查閱 AI 執行原件

從 Web 的處理紀錄定位 Workspace 與 Turn，再查看保存的模型步驟、公開訊息、工具參數／結果及用量。API 位於 `/api/workspaces/{workspace_id}/agent`；具體查讀端點見 [Agent HTTP](../../apps/backend/src/caliburn/modules/agent/README.md#http-與部署)。這些查讀不啟動模型。

公開查讀投影不等於完整 provider 帳單或所有外送原件；缺用量及未保存結果維持未知。比較實際 Context、完整原生保存或資料庫內容時須沿官方公開接口及各 owner 的固定版本查詢，不用目前最新內容冒充當輪輸入，也不傾倒秘密、不透明推理或員工正文到一般日誌。

## 常見問題

| 現象 | 核對順序 |
|---|---|
| 應用未啟動 | `docker compose ps`、app logs、PG／Qdrant health、是否已明示遷移；核對所用 Compose project 與設定檔。 |
| Agent 不可用 | Agent JSON 路徑、Plugin 必要依賴、Checkpoint 初始化及 provider 環境；不要只看金鑰是否存在。 |
| 公版搜尋不可用 | collection／manifest、既有模型 cache、固定權重版本、容器掛載及公版配置；不以健康端點成功推定已建索引。 |
| PDF 不可用 | 原生模式的字型與 Chromium；Docker build 是否完整；失敗不視為空 PDF。 |
| 訪談中斷 | 先查同一 Turn 的保存狀態，再明確恢復或取消；HTTP／SSE 斷線不等於取消。 |
| JD 寫入衝突／結果未知 | 保留草稿，重讀版本及內容後核對；不偷偷換版、自動重套 patch 或宣稱未保存。 |
| Workspace 刪除失敗 | 可能已刪業務資料但仍有待清 Checkpoint；以同一 Workspace ID 重試清理。 |

服務僅供本機使用，沒有登入或多租戶權限；信任與外送限制見[交付邊界](../architecture/delivery-and-operations.md#4-信任與權限邊界)。
