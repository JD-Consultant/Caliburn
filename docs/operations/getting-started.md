# 第一次使用 Caliburn

本頁使用 Docker 啟動單一應用程式、PostgreSQL 與 Qdrant，資料保存於 Compose 管理的 named volumes。只有 Agent 使用模型的能力依配置啟用，公版模組與資料服務屬標準部署。

## 1. 準備環境與設定

安裝可執行 Linux containers 的 Docker 與 Docker Compose，取得本專案後進入 repository 根目錄。以下命令用於首次尚無設定檔的 checkout：

```powershell
Copy-Item .env.compose.example .env
New-Item -ItemType Directory -Force .local
```

編輯根 `.env`，將 `CALIBURN_POSTGRES_PASSWORD` 換成自己的資料庫密碼，使用 URL-safe 字元。此檔供 Compose 插值；不要把密碼提交 Git。完整可調項見 [.env.compose.example](../../.env.compose.example)。

預設只綁本機：應用 `8101`、PostgreSQL `55441`、Qdrant `6335`。Compose 專案名為 `caliburn-rebuild`，啟停與更新須使用同一專案名以存取既有 volumes。

## 2. 建置、初始化與啟動

```powershell
docker compose build app
docker compose up -d --wait postgres qdrant
docker compose run --rm app python -m caliburn.migrate upgrade head
docker compose up -d --wait
docker compose ps
```

依序建置映像、啟動資料服務、明示遷移業務 Schema，再啟動應用。日常啟動不自動遷移。首次 build 會安裝鎖定套件、PDF 用的 Chromium 與字型；不下載公版模型權重或外部語料。

開啟 [Caliburn](http://127.0.0.1:8101)。可先建立檔案、人工編修 JD、查看歷史及匯出 PDF。健康入口是 [/api/health](http://127.0.0.1:8101/api/health)，API 文件位於 [/api/docs](http://127.0.0.1:8101/api/docs)。健康成功不代表公版索引、模型權重或 Agent 已就緒。

## 3. 啟用 AI 訪談

將 [Agent 範例](../../apps/backend/agent.example.json)複製為根 `.local/agent.json`，依需要選擇 Bundle／Plugin。建立 `.local/app.env`，設定：

```dotenv
CALIBURN_REBUILD_AGENT_CONFIG=/opt/caliburn/local/agent.json
CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO=postgresql://caliburn:YOUR_URL_SAFE_PASSWORD@postgres:5432/caliburn?options=-csearch_path%3Dagent_checkpoints
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
```

密碼須與根 `.env` 相同；`app.env` 由容器讀取，不會自動展開另一檔的變數。機密只放程序環境，Agent JSON 只放非秘密的模型與 Plugin 設定。模型請求會將必要工作資料外送至配置的 provider。

首次啟用 Agent 時先建立範例連線指定的專用 schema，再明示初始化官方 Checkpoint，最後重建應用容器以載入設定：

```powershell
docker compose exec postgres psql -U caliburn -d caliburn -c 'CREATE SCHEMA IF NOT EXISTS agent_checkpoints'
docker compose run --rm app python -m caliburn.migrate upgrade head --with-checkpoints
docker compose up -d --force-recreate app
```

Plugin 可分別選取，必要依賴缺漏會拒絕啟動，不自動補開；詳細配置與恢復相容版本見 [Agent](../../apps/backend/src/caliburn/modules/agent/README.md#明示設定)。未啟用 Agent 不會自動呼叫模型。

## 4. 準備公版檢索

公版模組已隨應用組裝，預設配置為 [docker/reference.json](../../docker/reference.json)。搜尋需要既有 Hugging Face cache 放在根 `.local/models`，以及與配置相符、已完成建置的 Qdrant collection。缺少資源會回不可用，不會自動下載權重或建索引。

來源轉換、權重版本、建新索引與配置切換見[公版維護](rag.md)。完成這些準備後，選取 Job Reference Plugin 的顧問即可查找公版；公版線索仍須經員工確認。

日常啟停、更新、備份與排錯見[操作手冊](README.md)，修改程式見[原生開發](native-development.md)。
