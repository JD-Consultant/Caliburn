# Caliburn backend（新目標施工中）

本目錄是新架構，不沿用同路徑的舊 venv、DB 或配置。目前提供 health、職務檔案建立／清單／改名／回讀、App 開場正式訪談、JD profile／職責／任務／共用知識／技能及任務關係、協作對象／共通條件的人工讀寫與生成契約；完整 JD 編輯器、AI 訪談和 Memory 產品功能尚未交付。現行正式產品入口不變，進度見[任務表](../../docs/plans/2026-09-29-target-rebuild/tasks.md)。目前僅供隔離開發／合成測試，完整瀏覽器入口安全與正式交付 gate 尚未完成，不對外開放。

## 安裝與執行

從 repo root 執行。使用 Python 3.14、uv 0.12.20；先安裝根 `package.json` 指定的 Node 24／pnpm，前端生成器也需要該環境。精確依賴由 `uv.lock` 保存。

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $PWD 'apps/api/.venv-target'
uv sync --project apps/api --locked
pnpm install --filter @caliburn/frontend --frozen-lockfile --strict-peer-dependencies
uv run --project apps/api --locked uvicorn caliburn.bootstrap:create_app --factory --host 127.0.0.1 --port 8100 --loop asyncio:SelectorEventLoop
```

`GET /api/health` 回傳 `{"status":"ok"}`，只表示程序存活，不表示 DB／模型可用。Ctrl+C 停止前景開發程序。新應用不在 import 時讀取 `.env`，這組命令不需模型金鑰，也不使用現行產品資料。

Windows 的 psycopg async 不支援預設 Proactor loop，因此明確使用 Python／Uvicorn 支援的 Selector factory，而非已棄用的全域 event-loop policy。這尚不代表 PDF 的 Windows 子程序接線已驗證；後續 T13 必須處理其不同 loop 需求，見[介面交付](../../docs/implementation/interface-and-delivery.md#4-pdf-與程序)。

## 驗證

### 目標資料庫初始化

先建立**專用的新空白 PostgreSQL database**，不填舊產品連線。以下從 repo root 執行；密碼由本機秘密管理注入，勿提交。僅使用新的配置名稱，不自動載入 `.env`。

```powershell
$env:CALIBURN_DATABASE_URL = 'postgresql://帳號:密碼@127.0.0.1:5432/caliburn_target'
$env:CALIBURN_DATABASE_SCHEMA = 'caliburn'
uv run --project apps/api --locked alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api --locked alembic -c apps/api/alembic.ini check
```

migration 會在已存在的目標 DB 建立指定 namespace；重跑 `upgrade head` 不重建原資料。應用啟動只檢查 migration head，不默默升級。未配置新 DB 時 health 仍可用、檔案 API 回 503；已配置但結構未初始化／不相符則啟動失敗。初始 schema 包含不可變原文，不提供破壞性 downgrade；需要資料處置應另行核對精確範圍。

目前資料入口（具體 DTO 由 `/openapi.json` 與 `contracts/http/` 生成）：

- `POST /api/job-files`：`command_id`、`display_name`、`employee_name`；新建立回 201，同一命令重送回原結果／200，不同輸入重用命令回 409。
- `GET /api/job-files`、`GET /api/job-files/{job_file_id}`：清單／目前檔案 metadata。
- `POST /api/job-files/{job_file_id}/rename`：`command_id`、`expected_name_revision`、`display_name`；只改檔案標籤。同命令回原結果／200，過期修訂或改 payload 重用命令回 409。GET 的 `name_revision` 作下次改名基準，不能在重送時偷換。成功後再 GET 目前名稱；員工姓名與訪談不變。
- `GET /api/job-files/{job_file_id}/interviews`：只有已正式化的訪談；目前建立後只有來源為 App 的開場第 1 則。未完成原文不在這裡出現。
- `GET /api/job-files/{job_file_id}/jd/profile`：目前正式修訂與四欄基本資料；新檔案為 null，代表尚未提供。
- `POST /api/job-files/{job_file_id}/jd/profile`：`command_id`、`expected_revision_id`、`changes`；明確 set／clear 指定欄位，未指定保留。成功／原命令重送回 200；舊基底、重用命令改 payload、活躍／暫停 A 的新人工修改回 409；非法欄位或重複 change 回 422。重送可返回舊操作當時的固定修訂，需最新內容另 GET；背景 Memory 不阻止人工編輯。保存／恢復界線見 [JD 保存接線](../../docs/implementation/jd-storage.md)。已接人工基本資料 UI，**不是 A 候選寫入入口**。
- `GET /api/job-files/{job_file_id}/jd/areas`：目前正式修訂與依序排列的職責集合，無資料時 `areas: []`。`POST` 同路徑：同一命令／基底規則下，以 `change.action` 建立、修訂、刪除或排序一項職責；完整輸入以 schema 為準。刪職責將任務轉未歸屬，不刪內容；profile、其他職責與任務保留。已接人工 UI；不是模型直接修改正式 JD 的路徑。
- `GET /api/job-files/{job_file_id}/jd/tasks`：目前正式修訂的任務集合，未歸屬在前，再依職責與組內順序；每項含獨立的成果／要求。`POST` 同路徑以 `change.action` 建立、修訂、移動、明細排序或刪除。任務及明細身分保留，兩組不能互換或跨任務移動；同任務多欄與明細調整全成或全拒。沿同一 JD command／base／人工准入規則，原結果可恢復；已接人工 UI，來源尚未交付。完整參數以 `edit-jd-tasks-request.schema.json` 為準，不是模型工具參數。
- `GET /api/job-files/{job_file_id}/jd/capabilities`：同一固定修訂的共用知識／技能定義與有序 `task_links`；正文不在任務內複製。`POST` 同路徑以 `change.action` 增修刪定義、概覽排序、連結／解除任務或排序任務關係。仍被使用的定義刪除回 409 `capability_in_use`；刪任務保留定義。知識與技能不能跨類排序或改類別，命令／基底／准入沿原規則；原結果按原修訂回讀。完整形狀以 `edit-jd-capabilities-request.schema.json` 為準；已接人工 UI，模型工具仍待 T07，不將本端點直接提供給 Agent。
- `GET /api/job-files/{job_file_id}/jd/work`：供人工 UI 組合讀取同一固定修訂的職責、任務及明細、知識／技能與任務關係、協作對象與共通條件；先固定 head，重用既有投影，不另存資料。各集合的獨立 GET 不承諾跨請求相同修訂；需要一個集合編輯畫面基底時使用此入口。
- `GET/POST /api/job-files/{job_file_id}/jd/collaborators`：主要協作對象的固定集合及新增、局部修訂、排序、刪除。名稱／合作範圍至少一欄有內容；未指定保留、null 清空不能清成空項。`GET/POST .../jd/conditions`：全職務共通條件，五類各自排序；明確修訂分類保留身分並放目的類末尾，不自動套到任務。兩者沿同一 JD 命令／基底／准入與歷史規則，完整 shape 依 `contracts/http/`；已接人工 UI 與同版 `/jd/work`，不是模型候選入口。
- `POST /api/job-files/{job_file_id}/inputs`：`command_id`、`text`；原文與 A 准入同次保存回 202，重送原命令回原接受結果／200，改內容重用命令或已有其他 A 回 409。重新提交已取消原文須用新命令，不是重送舊命令。**目前只做持久接受，尚無模型 runner／控制 UI，不會生成答覆**；不提供任意正式化 API。接線及未完邊界見[訪談保存](../../docs/implementation/interview-storage.md#6-輸入接受重送與新提交)。

### 測試與檢查

保持前述 `UV_PROJECT_ENVIRONMENT`；不要意外使用舊 `apps/api/.venv`。

```powershell
uv run --project apps/api --locked pytest apps/api/tests/unit apps/api/tests/contracts -q
uv run --project apps/api --locked ruff check apps/api
uv run --project apps/api --locked ruff format --check apps/api
uv run --project apps/api --locked mypy --config-file apps/api/pyproject.toml apps/api/src/caliburn
uv run --project apps/api --locked python apps/api/scripts/generate_contracts.py --check
```

修改 `contracts/http/*.schema.json` 後，執行相同生成命令但不帶 `--check`。標準生成器產 Python／TS，禁止手改 `generated/`。Python enum 成員使用大寫以避免與 `str.title` 等內建方法撞名；wire 值不改。App schema 與模型原生輸出是不同邊界：前者拒絕額外欄位，後者保留 SDK 原生項目及未知 metadata。

真 PostgreSQL 測試只接受**明確指定、loopback、名稱以 `_test` 結尾的隔離資料庫**；缺環境變數會 skip，不代表通過。測試建立隨機 schema，完成後只清理自己新建的 schema，不刪 DB。

```powershell
# 使用自行建立的空白測試 DB，不填既有產品 DB 或真實員工資料。
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://測試帳號:測試密碼@127.0.0.1:5432/caliburn_test'
uv run --project apps/api --locked pytest apps/api/tests/integration -m postgres -q
```

SDK 測試以 `MockTransport` 攔截所有請求，不連 OpenAI；跨程序 PG probe 只驗框架原生字典及既存 node 接續，不能替代 T06／T12 的業務副作用、取消與故障驗收。真 API 測試必須另外依[有界授權](../../docs/plans/2026-09-29-target-rebuild/README.md#3-狀態與施工順序)執行。
