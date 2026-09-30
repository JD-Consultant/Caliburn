# 同源 Web 交付入口的接線與驗證

2026-10-01，基準 `4f67929a`。本片補[介面交付 §4](../../../implementation/interface-and-delivery.md#4-pdf-與程序)已決定、程式尚未接通的「一個 API process 提供靜態 Web」能力。**只是交付預備，T18 及其前置品質 gate 未完成**；沒有改正式 authority、根 scripts、舊碼／資料、Demo 程序或模型／Prompt。

## 研究與最小取捨

- [FastAPI Frontend](https://fastapi.tiangolo.com/tutorial/frontend/)已提供建置目錄、路由優先及 HTML 導覽 fallback；本機鎖定 `fastapi==0.141.1` 原碼確認有同一契約。使用公开 `frontend()`，不依賴私有 class。
- [Vite 靜態交付](https://vite.dev/guide/static-deploy.html)以 build 產物部署，`preview` 不是 production server。本片不新增 nginx、SSR、Docker 或第二個 Web process。
- Caliburn 取捨：明確絕對目錄、預設關閉；`/` 只服務真檔案，`/job-files` 才允許 SPA fallback，避免全域 fallback 把未知 API／缺失根資源變成 HTML 200。原安全 middleware 不變，build 只包含可信公開資源。

程式只改 `settings.py` 讀配置及 `bootstrap.py` 組裝；没有新 HTTP schema、依賴、靜態路由框架或資料 owner。設定、工具鏈與操作責任由原 README／介面文件維護，本頁只保存證據。

## 驗證

先新增 `tests/unit/test_web_delivery.py`。前兩次受 Windows 沙箱 tmp ACL 阻擋，屬環境錯誤，**不是 Red**；依工具權限流程在全新 repo 暫存目錄執行後：**6 failed、3 passed**。失敗為首頁／深連結／資源尚無入口，以及缺失建置／相對路徑未被拒絕。

加入最小接線，Ruff 格式化後執行（工作目錄 `apps/api`，`$testScratch` 是 repo `.research-tmp` 下本次全新 GUID 目錄）：

```powershell
.\.venv-target\Scripts\python.exe -X utf8 -B -m pytest tests/unit/test_web_delivery.py tests/unit/test_local_http_security.py tests/unit/test_dev_origin_settings.py tests/unit/test_settings.py -q -p no:cacheprovider --tb=short --basetemp $testScratch
.\.venv-target\Scripts\python.exe -m ruff check src/caliburn/settings.py src/caliburn/bootstrap.py tests/unit/test_web_delivery.py
.\.venv-target\Scripts\python.exe -m ruff format --check src/caliburn/settings.py src/caliburn/bootstrap.py tests/unit/test_web_delivery.py
.\.venv-target\Scripts\python.exe -m mypy --cache-dir ../../.research-tmp/mypy-web-delivery --config-file pyproject.toml src/caliburn
```

局部與原安全測例 **83 passed，2.14s**；mypy **253 source files 無問題**。測例使用真 FastAPI／靜態檔／ASGI，不替換路由器，驗 GET／HEAD 深連結、資源正文、API 優先／404／503、非 HTML／POST 拒絕 fallback、Host／Origin、越界檔案拒絕、無配置純 API 及缺建置早期失敗。只驗本切片，沒重跑無關 DB／模型／PDF 全套。

真 Web：初次 PATH 的 Node／pnpm 試圖觸發重裝、因無 TTY 中止；不批准清理 modules。改用 [T01 已記錄工具鏈](t01-foundation.md#2-可接續的環境與命令)，經沙箱子程序權限後 `tsc --noEmit && vite build` 成功，1,363 modules，JS 952.67 kB／gzip 284.91 kB。保留既有 >500 kB chunk 警告，不為本片加入拆包或調高警告門檻。

再將**真 `apps/web/dist`** 注入 `create_app(Settings(web_build_directory=...))`，以 TestClient 檢查：首頁 200、HTML 實際引用的 JS／CSS 200、`/job-files/<id>` 回同一入口，`/api/missing` 在接受 HTML 時仍 404，health 保持 JSON。無 DB／provider 設定、無付費請求、沒有啟動長駐服務。

獨立唯讀程式審查核對三檔與鎖定框架原碼，未發現須先修的正確性、安全或範圍問題；沒有把該審讀算成另一輪執行測試。

## 未驗與接續

這不等於瀏覽器完整旅程、乾淨 clone 安裝、打包容器或正式切換；沿 T17／T18 原 gate 完成，不用本片替代分析品質。T14 的長歷史拆分漏引、Memory 語意精確化與 T16 容量 provider 限制仍保留原證據。不為同一未證實假說繼續增加 Prompt，亦不以可開畫面宣稱整個 Goal 完成。

## 乾淨安裝與套件化 migration（2026-10-01）

承接 `cae4f960`，補上一節未驗的同機乾淨安裝；不是正式入口切換。從 HEAD 用 `git archive` 匯出 tracked 檔案至 ignored `.research-tmp/delivery-clean-cae4f960-7b3e/source`，不帶工作樹、`.env` 或舊 venv。這是固定 Git 匯出，**不是另機網路 clone**；系統工具鏈、下載快取與本機 PostgreSQL 程序仍共用。

### 實際反例與採用機制

新 `venv` 以 Python 3.14.7／uv 0.12.20、`--locked --no-editable` 安裝 87 套件；Web 以 Node 24.19／pnpm 12.5.1、frozen lock 安裝 392 套件後建置成功（1,363 modules，既有 chunk 警告不變）。offline 嘗試缺 RapidFuzz／前端 tarball 後，明確在線下載缺項，沒有升級版本或改 lock。

在 loopback 55439 的 `caliburn_t01_test` 確認 namespace 不存在，才建立本次 `delivery_clean_20261001_7b3e`，以原 CLI 升至 head、`alembic check` 無差異。隨後以實際非 editable 套件啟動後端，失敗於 `Database.verify_schema()`：`No 'script_location' key found in configuration`。原因是 `API_ROOT = Path(__file__).parents[3]` 假設存在 checkout 的 `alembic.ini`；wheel 的 `site-packages` 不符合此路徑。

依 [Alembic ScriptDirectory 官方文件](https://alembic.sqlalchemy.org/en/latest/api/script.html)的 `Config()`＋`script_location="myapp:migrations"` 套件資源做法，採以下最小修正：

- 唯一 migration 移入 `src/caliburn/migrations`，隨既有 Hatch wheel 交付，不複製第二份或猜候選路徑。
- 程式 `migration_config()` 與 CLI `.ini` 均指 `caliburn:migrations`；CLI 移除只服務 checkout 的 `prepend_sys_path`。先安装套件仍為使用前提。
- 19 份 revision、修訂 ID、DDL 及模板全部保留；`env.py` 新納入 strict mypy 後，將 table metadata assertion 改為同表身分核對，不忽略型別錯誤、不改 migration 行為。
- 不新增 schema revision、資料表、通用資源框架或自動升級；啟動仍只核版本，遷移仍由明確命令執行。

[uv sync](https://docs.astral.sh/uv/concepts/projects/sync/)說明預設 editable 與 `--no-editable`；本例證明只用 editable 開發環境不足以驗交付，並非框架未提供機制。[pnpm install](https://pnpm.io/cli/install)的 frozen lock 用來保留已驗依賴，不把「最新」當浮動安裝。

### 回歸及實際套件證據

先補 `test_packaged_migrations.py`，把真 package 移出 checkout，使用獨立子程序讀其 migration history。首次執行遭 sandbox tmp ACL 拒絕，**不算 Red**；依權限流程使用全新目錄後，1 項因上述缺 `script_location` 失敗。修正後套件測例＋5 項真 PG migration 測例 **6 passed**；加入依賴邊界及同源入口回歸，最終 **30 passed，7.24s**。命令從 `apps/api` 執行：

```powershell
# CALIBURN_TEST_DATABASE_URL 為本機專用 _test DB；$testScratch 是全新 GUID 路徑
.\.venv-target\Scripts\python.exe -X utf8 -B -m pytest tests/unit/test_packaged_migrations.py tests/unit/test_import_boundaries.py tests/unit/test_web_delivery.py tests/integration/test_database_migrations.py -q -p no:cacheprovider --basetemp $testScratch
.\.venv-target\Scripts\python.exe -m ruff check src/caliburn/adapters/database.py src/caliburn/migrations tests/unit/test_packaged_migrations.py tests/integration/test_database_migrations.py
.\.venv-target\Scripts\python.exe -m ruff format --check src/caliburn/adapters/database.py src/caliburn/migrations tests/unit/test_packaged_migrations.py tests/integration/test_database_migrations.py
.\.venv-target\Scripts\python.exe -m mypy --cache-dir ../../.research-tmp/mypy-packaged-migrations --config-file pyproject.toml src/caliburn
```

Ruff 檢查／格式通過，mypy **274 source files 無問題**。未重跑與搬檔無關的全部模型／UI／故障測試。

另外真正 `uv build --wheel`，在上述新 venv 以 `uv pip install --no-deps --reinstall` 換入修正 wheel；其餘依賴與匯出的前端不變。確認 package 來自 `venv/Lib/site-packages/caliburn`，在非 checkout 目錄可取得全部 19 revisions、模板與 head `0019_optional_cost_limit`，連續兩次升級及 `check` 成功。最後僅格式化後的 wheel 重建曾受網路代理阻擋；使用既有完整快取 `--offline` 重建／重裝成功，沒有因此放寬版本或連線保護。

以真 Uvicorn loopback **58141**、上述專屬 namespace、新 Web build 啟动，不提供模型金鑰或 PDF 配置：

- health 200；首頁、HTML 引用的兩份 JS／CSS、職務頁深連結 200。
- HTTP 建立全合成職務 `fee3a9f6-cb35-4e66-9f68-6d5ec7d7e9b6`，人工保存「課程行政專員」及合成目的，得到正式 JD `976830b9-3d36-42f0-b940-bb45d8a1ad49`；原命令重送返回原結果。
- 正常停止自有程序、重新啟動後，GET 仍返回同一修訂及原文。不是只看 health，也沒有直接 DB 填入成稿代替 HTTP 寫入。
- 兩次自有 server 均已停止；保留 ignored 安裝目錄及該測試 namespace 供回查，不動 Demo、既有旅程或私人資料。本片 **零 provider 呼叫**。

獨立唯讀審查確認 19 份 revision 與模板的 Git 正規化雜湊不變，CLI／程式解析同一資源，未發現需先修問題。單元測試只證明搬離 checkout 仍能讀資源；真正 wheel 包含內容與啟動的證據來自以上額外實測，兩者不混稱。

### 仍未完成

本片沒有另機／容器、乾淨 PDF 字型與 Chromium 安裝、真模型整體旅程或正式入口切換。T14 的拆分漏依據／Memory 表述問題、T16 的高容量 provider gate、T17 品質與 T18 最後切換仍依原 evidence，不以本次安裝成功勾選。工程代理已提出「先試用並明列品質限制」或「修好品質再交付」的取捨，**尚未收到裁決，不改原完成標準**。
