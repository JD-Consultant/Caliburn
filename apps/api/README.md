# Caliburn backend

正式後端使用 FastAPI 單程序、PostgreSQL、LangGraph 官方 saver 與 OpenAI 直連 Responses，負責訪談、背景 Memory、JD 編輯、來源回查與 PDF 匯出。日常啟動從專案根目錄的 `pnpm` 命令進入（見[根 README](../../README.md#第一次設定)與 [操作手冊](../../docs/runbook.md)）；本頁說明後端配置、API 與測試。服務只綁定 loopback，不對外開放；正式範圍見 [ADR 0079](../../docs/adr/0079-target-rebuild-production-cutover.md)，實際驗證與限制見[驗證範圍](../../docs/architecture/verification.md)。

產品使用 `gpt-6-luna`／`high`（使用者於 2026-10-01 因成本確認），不採用 Sol 或自動 fallback。程式化 `ModelSettings` 的 Sol 接縫僅保留既有隔離研究，不再推進切換或追加 Sol 外送；沒有環境／UI 模型切換，不能將既有原生歷史交給另一模型。能力與限制以[選型文件](../../docs/implementation/technology-decisions.md#1-首選工具鏈)為準。

## 安裝與執行

從專案根目錄執行，使用 Python 3.14、uv 0.12.20 與根 `package.json` 指定的 Node／pnpm。先提供[資料庫設定](#目標資料庫初始化)，AI 與 PDF 設定見 [操作手冊](../../docs/runbook.md)。依賴由 `apps/api/uv.lock` 與根 `pnpm-lock.yaml` 固定。

```powershell
uv sync --project apps/api --locked
pnpm install --frozen-lockfile
pnpm app:migrate
pnpm build
pnpm start        # 同源提供畫面與 API：http://127.0.0.1:8100/
```

開發前端時以 `pnpm dev` 取代 `pnpm start`，兩者不要同時執行。`pnpm app:status` 只診斷目前環境變數與資料庫；不讀 `apps/api/.env`、不套用啟動器的 Web 目錄、不啟動服務，詳細判讀見 [診斷](../../docs/runbook.md#診斷)。

`pnpm start` 轉交下方的 `scripts/run_backend.py`。只有最低層診斷才直接執行 uvicorn：`uv run --project apps/api --locked uvicorn caliburn.bootstrap:create_app --factory --host 127.0.0.1 --port 8100 --loop asyncio:SelectorEventLoop`。這個入口不載入 `.env`，但已提供的環境變數（包括 key）仍生效。`GET /api/health` 回傳 `{"status":"ok"}` 只表示程序存活，不表示 DB／模型可用。應用不在 import 時讀取 `.env`。

預設精確信任本機 5173／8100 Origin。隔離測試若使用第二個前端埠，可在**該後端啟動前**指定 `CALIBURN_DEV_ORIGIN=http://127.0.0.1:5174`；只接受一個帶明確埠的 HTTP loopback Origin（`127.0.0.1`、`localhost` 或 `[::1]`），非法配置在啟動前拒絕，不放寬其他埠、Host 或 cross-site 防護。前端 proxy 必須保留原始 Origin，具體隔離啟動見[前端 README](../web/README.md#合成資料瀏覽器驗收)。這不是對外部署／認證方案。

Windows 的 psycopg async 不支援預設 Proactor loop，因此明確使用 Python／Uvicorn 支援的 Selector factory，而非已棄用的全域 event-loop policy。PDF renderer 使用獨立的瀏覽器執行環境；Windows 中文短／長版及同機獨立 wheel／新 PDF 資源已有驗證，不能據此推論跨平台結果，見[介面交付](../../docs/implementation/interface-and-delivery.md#4-pdf-與程序)及 [PDF 驗證紀錄](../../docs/history.md#source-25de60a3e4266687fd86)。

### 後端入口（`pnpm start`／`pnpm dev` 所用）

根命令已提供此入口，通常不用單獨執行。若要只開 API，在同一終端提供 `CALIBURN_DATABASE_URL`／schema 與所需 PDF 環境變數，再執行下列命令。`--key-file` 只讀 OpenAI key；根命令在 `apps/api/.env` 存在時自動帶入。換終端後，環境變數須重新提供。

```powershell
uv run --project apps/api --locked python apps/api/scripts/run_backend.py --key-file apps/api/.env
```

只開 API 後，開發畫面可在另一個終端執行 `pnpm --dir apps/web dev`，開啟 `http://127.0.0.1:5173`；不要再執行會同時啟動後端的 `pnpm dev`。後端預設 loopback 8100（`--port` 可改），單程序，不自動遷移／建立範例資料；Ctrl+C 停止前景程序。恢復已接受工作可能繼續使用模型額度；僅要操作人工 JD 時，不提供 key-file 且不設定 `OPENAI_API_KEY`。

### 使用建置後的同源畫面

正式交付形式。先沿上節設定資料庫，使用所定 Node／pnpm 與 Python 環境，從 repo root 執行（`pnpm build`＋`pnpm start` 已包含下列步驟與環境變數）：

```powershell
pnpm --filter @caliburn/frontend build
$env:CALIBURN_WEB_BUILD_DIRECTORY = (Resolve-Path 'apps/web/dist').Path
uv run --project apps/api --locked python apps/api/scripts/run_backend.py --key-file apps/api/.env
```

開啟 `http://127.0.0.1:8100`，不需另外啟動 Vite；職務頁可以直接開啟或重新整理。只使用人工 JD 時省略 `--key-file` 並勿設定 `OPENAI_API_KEY`。PDF 字型／Chromium 仍依下節配置；靜態入口不會代為建庫、遷移或提供模型憑證。

只指定可信的**公開建置目錄**，不要指向 repo、原始碼或秘密目錄；缺目錄／`index.html` 會啟動失敗。未設定此變數時維持 API-only。既有程序不會自動切換；先確認身分再停止自己啟動的程序，勿為此中斷別人的 Demo。更換建置時重新啟動自有服務，不使用 `vite preview` 作交付 server。接線與驗證界線見[交付預備證據](../../docs/history.md#source-25de60a3e4266687fd86)。

## 資料庫設定

### 目標資料庫初始化

首次安裝先建立專用的空白 PostgreSQL database，不填退役產品的連線；更新目前 App 則沿用原資料庫。以下從專案根目錄執行；連線字串僅示意格式，實際帳密由本機秘密管理提供，勿提交。不從 `.env` 載入資料庫設定。

```powershell
$env:CALIBURN_DATABASE_URL = 'postgresql://帳號:密碼@127.0.0.1:5432/caliburn_target'
$env:CALIBURN_DATABASE_SCHEMA = 'caliburn'
uv run --project apps/api --locked alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api --locked alembic -c apps/api/alembic.ini check
```

migration 會在已存在的目標 DB 建立指定 namespace；重跑 `upgrade head` 不重建原資料。應用啟動只檢查 migration head，不默默升級。未配置新 DB 時 health 仍可用、檔案 API 回 503；已配置但結構未初始化／不相符則啟動失敗。初始 schema 包含不可變原文，不提供破壞性 downgrade；需要資料處置應另行核對精確範圍。

日常入口 `pnpm start`／`pnpm dev` 會要求資料庫設定；上述「未配置 DB 時 health 可用」只適用於直接啟動的最低層診斷入口。版本更新流程見[根 README](../../README.md#更新已有安裝)。

**JD 模型短定位（0023）：**升級前讓執行中的工作停在安全點，停止原後端後，沿上述相同 DB／schema 設定執行 `pnpm app:migrate`，再 `pnpm start`。這只新增模型定位映射，不重建 JD 或改寫原模型歷史；新工具結果提供 `task_12`／`citation_18` 等短定位，舊 UUID 定位仍相容。映射由 App 自動發配，不能手動重排／重設序號／清表；前端 HTTP 仍使用原 UUID，無須為此重建前端。設計與驗證見 [JD 保存 §3.2](../../docs/implementation/jd-storage.md#32-模型導覽與既有物件定位)及 [T14 §8](../../docs/history.md#source-098e24f247a9411844be)。

完整 migration 位於 `src/caliburn/migrations` 並隨 Python wheel 交付；CLI 與程式都用 Alembic 的 `caliburn:migrations` 套件資源定位，不依賴 checkout 的相對路徑。非 editable 安裝可使用 `uv sync --project apps/api --locked --no-editable`，後續 `uv run` 也帶 `--no-editable`，避免重新同步成開發模式。2026-10-01 已驗新 venv／實際 wheel、空測試 schema、同源建置、人工 JD 保存與重啟，續驗已補同機 PDF；不是另一台電腦、模型品質或正式切換全部通過，見[證據](../../docs/history.md#source-25de60a3e4266687fd86)。

## API 與執行紀錄

**找回進行中的訪談：**`GET /api/job-files/{job_file_id}/consultant-turns/current` 可依職務檔案找回進行中／暫停的 A，不需瀏覽器先保存 execution／command ID；回傳 `{"turn": <既有公開狀態>}` 或明確 `{"turn": null}`，未知檔案 404。不啟動／恢復模型、不返回 Memory 或終態歷史。狀態也可經 `/consultant-turns/{execution_id}` 或 `/consultant-turns/by-command/{command_id}` 重取；驗證見[原始紀錄](../../docs/history.md#source-c8ea469844e955e1447b)。

**離線回看：**只要原 DB 可用，即使未配置模型，也可透過既有 PostgreSQL checkpointer 讀取已保存的公開中間訊息；不建立模型 client、不啟動執行 supervisor。`POST /inputs` 只在模型與 supervisor 就緒時接受新工作；沒有模型設定時回 `503 model_not_configured`，既有命令仍可查回原結果，不為回看而重跑模型。驗證見 [T17 紀錄](../../docs/history.md#source-98d840caa9eed7fb2840)。

主要資料入口（具體 DTO 由 `/openapi.json` 與 `contracts/http/` 生成）：

- `POST /api/job-files`：`command_id`、`display_name`、`employee_name`；新建立回 201，同一命令重送回原結果／200，不同輸入重用命令回 409。
- `GET /api/job-files`、`GET /api/job-files/{job_file_id}`：清單／目前檔案 metadata。
- `POST /api/job-files/{job_file_id}/rename`：`command_id`、`expected_name_revision`、`display_name`；只改檔案標籤。同命令回原結果／200，過期修訂或改 payload 重用命令回 409。GET 的 `name_revision` 作下次改名基準，不能在重送時偷換。成功後再 GET 目前名稱；員工姓名與訪談不變。
- `GET /api/job-files/{job_file_id}/interviews`：只有已正式化的訪談；目前建立後只有來源為 App 的開場第 1 則。未完成原文不在這裡出現。
- `GET /api/job-files/{job_file_id}/jd/profile`：目前正式修訂與四欄基本資料；新檔案為 null，代表尚未提供。
- `POST /api/job-files/{job_file_id}/jd/profile`：`command_id`、`expected_revision_id`、`changes`；明確 set／clear 指定欄位，未指定保留。成功／原命令重送回 200；舊基底、重用命令改 payload、活躍／暫停 A 的新人工修改回 409；非法欄位或重複 change 回 422。重送可返回舊操作當時的固定修訂，需最新內容另 GET；背景 Memory 不阻止人工編輯。保存／恢復界線見 [JD 保存接線](../../docs/implementation/jd-storage.md)。已接人工基本資料 UI，**不是 A 候選寫入入口**。
- `GET /api/job-files/{job_file_id}/jd/areas`：目前正式修訂與依序排列的職責集合，無資料時 `areas: []`。`POST` 同路徑：同一命令／基底規則下，以 `change.action` 建立、修訂、刪除或排序一項職責；完整輸入以 schema 為準。刪職責將任務轉未歸屬，不刪內容；profile、其他職責與任務保留。已接人工 UI；不是模型直接修改正式 JD 的路徑。
- `GET /api/job-files/{job_file_id}/jd/tasks`：目前正式修訂的任務集合，未歸屬在前，再依職責與組內順序；每項含獨立的成果／要求。`POST` 同路徑以 `change.action` 建立、修訂、移動、明細排序或刪除。任務及明細身分保留，兩組不能互換或跨任務移動；同任務多欄與明細調整全成或全拒。沿同一 JD command／base／人工准入規則，原結果可恢復；人工 UI 可編輯，來源另按需回查。完整參數以 `edit-jd-tasks-request.schema.json` 為準，不是模型工具參數。
- `GET /api/job-files/{job_file_id}/jd/capabilities`：同一固定修訂的共用知識／技能定義與有序 `task_links`；正文不在任務內複製。`POST` 同路徑以 `change.action` 增修刪定義、概覽排序、連結／解除任務或排序任務關係。仍被使用的定義刪除回 409 `capability_in_use`；刪任務保留定義。知識與技能不能跨類排序或改類別，命令／基底／准入沿原規則；原結果按原修訂回讀。完整形狀以 `edit-jd-capabilities-request.schema.json` 為準。模型經 JD 工具編輯候選，不直接使用此人工編輯端點。
- `GET /api/job-files/{job_file_id}/jd/work`：供人工 UI 組合讀取同一固定修訂的職責、任務及明細、知識／技能與任務關係、協作對象與共通條件；先固定 head，重用既有投影，不另存資料。各集合的獨立 GET 不承諾跨請求相同修訂；需要一個集合編輯畫面基底時使用此入口。
- `GET/POST /api/job-files/{job_file_id}/jd/collaborators`：主要協作對象的固定集合及新增、局部修訂、排序、刪除。名稱／合作範圍至少一欄有內容；未指定保留、null 清空不能清成空項。`GET/POST .../jd/conditions`：全職務共通條件，五類各自排序；明確修訂分類保留身分並放目的類末尾，不自動套到任務。兩者沿同一 JD 命令／基底／准入與歷史規則，完整 shape 依 `contracts/http/`；已接人工 UI 與同版 `/jd/work`，不是模型候選入口。
- `POST /api/job-files/{job_file_id}/inputs`：`command_id`、`text`；原文與 A 准入同次保存回 202，原命令重送回原接受結果／200；不同內容重用命令或已有其他 A 回 409。提交後 supervisor 執行既有 runner；未配置模型回 503，不接受無法執行的工作。取消後重新提交須用新命令；不提供任意正式化 API。驗證見 [A 執行紀錄](../../docs/history.md#source-f5df4f496aad7b909036)。

### PDF 執行依賴

Python 套件安裝不包含瀏覽器執行檔或中文字型。依 [Playwright 官方做法](https://playwright.dev/python/docs/browsers)，在後端所用的同一 Python 環境安裝其鎖定版本的 headless Chromium；本 renderer 不需要系統 Chrome、Firefox 或 WebKit：

```powershell
uv run --project apps/api --locked python -m playwright install chromium --only-shell
$env:CALIBURN_PDF_FONT_PATH = 'C:/path/to/licensed/NotoSansTC-VF.ttf'
```

字型路徑須換成實際可讀的檔案；可從 [Noto CJK 官方下載指南](https://github.com/notofonts/noto-cjk/blob/main/Sans/README.md)取得繁體中文臺灣字型，保留其來源、版本及授權，不依賴本機碰巧已安裝的字型。若沿前節使用非 editable 環境，上述 `uv run` 同樣加 `--no-editable`，或直接使用該 venv 的 Python。

可選 `CALIBURN_PDF_CHROMIUM_PATH` 指定與已鎖 Playwright 相容的 Chromium **執行檔**；未指定時使用 Playwright 已安裝的瀏覽器。若安裝時自訂 `PLAYWRIGHT_BROWSERS_PATH`，啟動後端時也保留同一值。下載失敗先依官方文件檢查網路／代理與版本，不改用任意系統瀏覽器冒充已驗環境、不關閉 TLS 檢查。

配置須在啟動後端前提供。`GET /api/job-files/{id}/jd/export.pdf` 固定讀正式 JD，候選不匯出；缺配置明確回 503，不下載空檔。實際驗證與文字抽取限制見 [PDF 紀錄](../../docs/history.md#source-409f20a1c297740aed7d)及[驗證範圍](../../docs/architecture/verification.md)。

## 驗證

產品不以預估美元金額攔截 A／B1／B2；`CALIBURN_TURN_MAX_COST_USD` 已退役。token 容量、壓縮門檻、呼叫／重試及時間限制仍有效。用量估算供診斷，不是 provider 帳單；付費驗證腳本須另以 manifest 設定有限預算，見[執行 §5.8](../../docs/implementation/agent-execution.md#58-產品與付費驗證的金額界線)。

### 測試與檢查

從專案根目錄執行；標準 `uv sync --project apps/api` 使用 `apps/api/.venv`。若自行設定 `UV_PROJECT_ENVIRONMENT`，安裝、啟動與檢查須使用同一個環境。

```powershell
uv run --project apps/api --locked pytest apps/api/tests/unit apps/api/tests/contracts -q
uv run --project apps/api --locked ruff check apps/api
uv run --project apps/api --locked ruff format --check apps/api
uv run --project apps/api --locked mypy --config-file apps/api/pyproject.toml apps/api/src/caliburn
uv run --project apps/api --locked python apps/api/scripts/generate_contracts.py --check
```

修改 `contracts/http/*.schema.json` 或 `contracts/tools/*.schema.json` 後，執行相同生成命令但不帶 `--check`。標準生成器產 Python／TS；tools 另生成包內原 schema 資源，供工具 definitions 讀取。禁止手改 `generated/` 的型別或 JSON。Python enum 成員使用大寫以避免與 `str.title` 等內建方法撞名；wire 值不改。App schema 與模型原生輸出是不同邊界：前者拒絕額外欄位，後者保留 SDK 原生項目及未知 metadata。

真 PostgreSQL 測試只接受**明確指定、loopback、名稱以 `_test` 結尾的隔離資料庫**；缺環境變數會 skip，不代表通過。測試建立隨機 schema，完成後只清理自己新建的 schema，不刪 DB。

```powershell
# 使用自行建立的空白測試 DB，不填既有產品 DB 或真實員工資料。
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://測試帳號:測試密碼@127.0.0.1:5432/caliburn_test'
uv run --project apps/api --locked pytest apps/api/tests/integration -m postgres -q
```

SDK 測試以 `MockTransport` 攔截所有請求，不連 OpenAI；跨程序 PG probe 只驗框架原生字典及既存 node 接續，不能替代 T06／T12 的業務副作用、取消與故障驗收。真 API 測試必須另外依[有界授權](../../docs/history.md#source-ee8cbce8eb3c303d1765)執行。

長訪談評測由 `scripts/simulate_interview.py` 明示啟動，不在測試或 App 啟動時自動執行。已診斷的中斷可保留原輸出路徑及旅程參數，以 `--resume-job-file`、`--resume-execution`、原絕對 `--deadline` 接續；先核對並等待指定原執行，只有已確認終止才依原旅程的重送政策處理，不因查詢失敗自行重送。完整參數見 `--help`，批准範圍、費用／時間與實際結果見 [T17 續跑修訂 A2](../../docs/history.md#source-98d840caa9eed7fb2840)。`.progress.jsonl` 與 `.events.jsonl` 是評測證據，不能代替產品的正式訪談／執行保存。

### 顧問推理摘要

新 A 模型請求啟用可讀推理摘要；`/api/job-files/{job_file_id}/consultant-turns/{execution_id}/activity-stream` 在一條 SSE 提供 `commentary`、`reasoning_summary`，`/reasoning-summaries` 回讀已保存摘要。Web 已接入即時顯示與歷史回看；查詢失敗不當成沒有摘要，也不為回看而重跑模型。摘要不作正式訪談依據，不公開原始推理。完整契約與驗證範圍見[介面 §2.1](../../docs/implementation/interface-and-delivery.md#21-推理摘要串流與歷史回看)。

### 模型失敗診斷

要在 DataGrip 直接 JOIN 查看某份檔案的 AI 輸入、工具與結果，使用按需 `scripts/refresh_execution_diagnostics.py`，再開啟 `diagnostic_execution_history`、`diagnostic_model_steps`、`diagnostic_tool_calls`。它不啟動模型，也不改原 checkpoint；完整命令、擷取新鮮度與敏感資料界線見 [runbook](../../docs/runbook.md#在-datagrip-查某個職務檔案的-ai-執行紀錄)。

後端 logger `caliburn.workflows.model_requests` 以 `Provider request failed` 記錄實際外送失敗：操作、安全分類、HTTP status、白名單 provider code，以及 **App 本地** execution／request／attempt ID。可依這些 ID 核對既有執行紀錄；它們不是可向 OpenAI 取回遺失回應的遠端 ID。`None` 表示未取得 HTTP status 或 code 不在白名單，不能據此推定沒有錯誤。

此警告不代表故障已保存、重試／回滾已完成。不要為診斷開啟原始 HTTP body、訪談、opaque reasoning 或秘密輸出；既有日誌即可，不需新監控服務。接線與驗證範圍見 [T06 §23](../../docs/history.md#source-d76bfd79f21fb146c537)。
