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

## 非 editable 安裝的中文 PDF（2026-10-01 續驗）

承接 `166dd960`，沿用上述獨立 venv、實際 wheel 與 `delivery_clean_20261001_7b3e`，本片只補 PDF 交付接縫。沒有修改 renderer／模型／工具／Prompt，也沒有付費外送、另造容器或更換 Demo 程序。

### 執行依賴與研究

[Playwright 官方瀏覽器文件](https://playwright.dev/python/docs/browsers)說明每版套件對應特定瀏覽器、headless-only 安裝及自訂下載路徑。鎖定 Python Playwright 1.63.0 的本機 `browsers.json` 指定 headless shell **153.0.8010.12、revision 1243**。不以系統 Chrome 冒充這個組合。

- 在全新 `PLAYWRIGHT_BROWSERS_PATH` 執行 `python -m playwright install chromium --only-shell --no-remove --no-progress`；CLI 內建的 5 次下載均於 30 秒逾時，命令失敗，沒有宣稱原生 installer 成功。
- 同一官方 CDN URL 的 PowerShell HEAD 為 200；遂以 `Invoke-WebRequest` **一次**下載該相同 ZIP，再 `Expand-Archive` 至獨立目錄。沿產品原有 `CALIBURN_PDF_CHROMIUM_PATH` 明確指定其中的執行檔，沒有改 Playwright、關閉 TLS 或新增產品 fallback。未查明 Node CLI 與 PowerShell 的網路行為差異，不斷言是代理原因。
- 字型從 [Noto CJK 官方下載指南](https://github.com/notofonts/noto-cjk/blob/main/Sans/README.md)選繁體中文臺灣 subset variable TTF；固定 repo commit `f8d157532fbfaeda587e826d4cd5b21a49186f7c`，下載 `Sans/Variable/TTF/Subset/NotoSansTC-VF.ttf` 及同版 `Sans/LICENSE` 至隔離目錄，不依賴 Windows 已安裝字型。首次誤取根目錄 LICENSE 得 404，查官方位置後補正；不是字型下載／產品故障。

| 本機依賴原件 | Bytes | SHA-256 |
|---|---:|---|
| 官方 headless shell ZIP | 120,200,717 | `7aec872f3090e639c4237467624ea863c20fe2878914c93a6556bdbb52aa6c4c` |
| NotoSansTC-VF.ttf | 11,942,800 | `ac091cc8cd19e848202afc8fe6d3809b4526c8fdbdb4be82da20c4f785949591` |
| Sans/LICENSE | — | `6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2` |

以上是下載後的辨識雜湊，不宣稱為廠商簽章驗證。原件、字型授權及 PDF 保留於 ignored `.research-tmp/delivery-clean-cae4f960-7b3e`，不提交二進位或更動系統字型。

### 真 HTTP、保存與頁面檢查

確認 `caliburn.__file__` 來自獨立 venv 的 `site-packages`，使用 Selector loop、同源靜態 build、loopback 58141 啟動真 Uvicorn，**不提供 API key**。PDF 字型與瀏覽器指向上述新下載原件。

1. 讀回上片人工保存的職務 `fee3a9f6-cb35-4e66-9f68-6d5ec7d7e9b6`，確認仍是修訂 `976830b9-3d36-42f0-b940-bb45d8a1ad49`，經正式 `GET .../jd/export.pdf` 匯出短稿。
2. 透過正式 HTTP 建立長稿用合成職務 `75edfe61-49e0-4d69-826f-fcf8482fc4d2`；保存 profile 及一個含 80 段文字的未歸屬任務，再由正式端點匯出。內容沿既有 `test_pdf_rendering.py` 的分頁素材，不是把人工編稿算成真模型品質。
3. 首次驗證命令誤用 `job_purpose`，HTTP 422 拒絕，未寫入 profile；讀 canonical `revise-jd-profile-request.schema.json` 後改用正確 `purpose`，保存成功。這是探針輸入錯誤，沒有為了讓測試通過修改契約。最終正式長稿修訂 `d7ea6ad5-922a-497d-bf86-50f904d86596`。
4. 兩次匯出均 HTTP 200、`application/pdf`、`Cache-Control: no-store`。Poppler 確認 tagged A4、無 JavaScript；短稿 **1 頁／83,093 bytes**，長稿 **3 頁／268,380 bytes**。
5. Poppler 將全部四頁轉 PNG 並逐頁目視：中文可讀，無遮疊、缺字或截斷；長稿步驟在 20→21、65→66 正常跨頁，末尾成果仍在第 3 頁。另用 pypdf 驗步驟 0–79 依序完整、末尾成果存在、合成員工姓名／檔案名未輸出。既有字型 cmap 的文字複製／搜尋限制仍依 [T13](t13-pdf-export.md#任務完成對照與-pdf-文字層診斷2026-09-30-恢復後)，不以視覺成功消除該限制。

| 產物（ignored `pdf/`） | SHA-256 |
|---|---|
| `jd-short.pdf` | `6e5181c07ec637dc54334b25509434e124089d5e1d5000f8dfaa9bbcfd9fb661` |
| `jd-long.pdf` | `a1f3bf7a31d65a31b0aa34a64dd5b21d389767149341a9caa02b95a792e7ce0a` |

自有 server PID 36024 已 Ctrl+C 完成 lifespan 關閉；58141 不再監聽。測試資料保留，未刪舊資料或停止其他程序。只補 README 的 PDF 安裝／配置步驟及本證據，沒有新產品程式行為，因此不重跑無關全套測試。

**結論：**已證實同機獨立 wheel 環境＋新下載指定版本瀏覽器／字型可以由正式後端匯出短／長中文 PDF。原生 Playwright CLI 下載仍未成功，另機／Linux 未驗；不以此勾 T18 或宣告 T14／T16／T17 的品質／容量問題已解決。

## 切換範圍盤點與舊依賴防線（2026-10-01）

以 `4a71e0b1` 的 tracked 樹作唯讀盤點，**不是批准立即刪除或切換**。T14／T16／T17 未通過，現行 ADR0077、根命令、CI、Demo 與資料均保持原狀。產品 Luna／high 決策不變。

### 精確範圍與保留項

| 範圍 | 基準數量 | T18 通過前置 gate 後的處置 |
|---|---:|---|
| `experiments/jd-relational-app` 下的 tracked 非 Markdown 檔 | 336 | 舊 App／Web 程式、契約、測試、遷移、設定與 lock 的退役候選 |
| `packages/consultant-memory` 下的 tracked 非 Markdown 檔，排除 `adoption.json` | 41 | 舊 Memory 程式、測試及套件設定的退役候選 |
| `scripts/run-jd-app.mjs`、`scripts/run-jd-app.test.mjs` | 2 | 舊啟動器及其測試；新根入口須先驗證再移除 |
| 上述兩個目錄的 Markdown 及 `packages/consultant-memory/adoption.json` | 16 | 保留研究、方法、結果與採用沿革；原 README／局部指引於切換時標示歷史，不再作執行入口 |

候選共 **379 檔**。可用 `git ls-tree -r --name-only 4a71e0b1 -- experiments/jd-relational-app packages/consultant-memory` 重建：排除 `.md` 與前述 `adoption.json`，再加兩個明列的啟動器檔案。此為固定 Git 樹的選取條件，不是對工作目錄遞迴刪除的命令；執行當天須重新核對 dirty、使用中的程序與逐檔 diff，保留新增／未追蹤／ignored 檔案。`.env`、venv、資料庫、volume、測試產物及其他 experiments／RAG 不在清單。

### 必須共同切換的入口

1. 根 `package.json` 的 JD 開發／建置／測試／啟動及舊 `app:*` 命令、`pnpm-workspace.yaml` 的兩個舊 workspace、相應 `pnpm-lock.yaml` importer。新根命令應轉交既有新 App 入口，不將舊 OpenRouter／Windows 憑證管理移植成相容層。RAG scripts 與獨立套件保留；lock 由 pnpm 更新，不手刪共用傳遞依賴。
2. `.github/workflows/api-tests.yml` 目前仍安裝舊 Python 專案、執行舊 codegen／測試與 Web typecheck，必須與根命令一起改到新目標，否則綠色 CI 仍只在驗舊產品。切換前不先讓它冒充新產品 gate。
3. `README.md`、`ARCHITECTURE.md`、`CONTRIBUTING.md`、`AGENTS.md`、runbook、current-decisions、ADR 索引與 successor，以及相關 App README。歷史 ADR0077 不改寫；舊文檔失效入口改連歷史索引或固定 Git 版本，不能保留成看似可執行的現行指令。

本次以 `git grep` 搜 tracked 非 Markdown／非 lock 的反向依賴：除舊產品本身，執行接線命中上述根命令、workspace、CI 及啟動器；新後端只在邊界測試中提及舊套件。這是靜態盤點，不能代替切換後的 frozen install、codegen、建置與完整旅程。套件化 migration、同源交付及 PDF 已有本頁前節證據，不為盤點重跑或重建另一套交付方式。

### 發現並修正的檢查缺口

既有 `tests/unit/test_import_boundaries.py` 禁止 `consultant_memory`，但舊套件 `pyproject.toml` 的 wheel 路徑是 `src/caliburn_memory`，因此原檢查漏攔真正的舊 import。目前新產品沒有該依賴，不是已發生的執行故障。

先在原參數化測例加入 `import caliburn_memory` 與 `from caliburn_memory import publication`：**2 failed、15 passed**，失敗原因是未報違規。僅補正既有 denylist 的套件名後，同檔 **17 passed（0.24s）**，包含實際掃描新後端 source；Ruff check／format check 通過。沒有新增 AST 框架、產品依賴、runtime 行為或付費請求。

重現命令（`apps/api`）：

```powershell
.\.venv-target\Scripts\python.exe -X utf8 -B -m pytest tests/unit/test_import_boundaries.py -q -p no:cacheprovider --tb=short
.\.venv-target\Scripts\python.exe -m ruff check tests/unit/test_import_boundaries.py
.\.venv-target\Scripts\python.exe -m ruff format --check tests/unit/test_import_boundaries.py
```

依開發規範 §3.1，本片只改測試防線及盤點文件，不重跑未受影響的 DB／模型／UI 全套。**下一步仍先處理前置 gate；本節不勾 T18、不執行清單、不啟動或停止任何產品程序。**

## 乾淨 worktree 的根命令（切換候選，2026-10-01）

基準 `2fdc6cad`。本片把 T18 的入口切換備成一組可審提交，**放在獨立分支 `target-cutover-candidate`（git worktree `S:\caliburn-cutover`）**，原分支 `target-rebuild` 的根入口、舊程式與 ADR0077 效力不變；沒有 merge、push、刪資料，也沒有啟停 Demo。T14／T16／T17 前置 gate 仍是放行條件，本片只證明「切換本身可行且可驗」。

### 內容（候選分支三個提交）

| 提交 | 內容 |
|---|---|
| `d08a3b09` | 根 `package.json`（`dev`／`start`／`build`／`lint`／`typecheck`／`test`／`check`／`app:migrate`／`app:status`）、`pnpm-workspace.yaml` 移除舊 workspace、pnpm 重新生成的 lock（importer 只剩 `.` 與 `apps/web`，其餘為 RAG 套件）、`scripts/run-app.mjs`（啟動後端、dev 時加 Vite；`start` 沒有建置就明確失敗；額外參數如 `--port` 轉給後端）及其 5 項 node 測試、`python -m caliburn.status` 與其 6 項測試、CI 改跑同一個根 `check` |
| `be14f8ba` | 退役固定盤點的 **379 個 tracked 檔**（336＋41＋2 個啟動器檔），兩個 README 加歷史標記與基準提交 |
| `7f2e0085` | README、ARCHITECTURE、CONTRIBUTING、AGENTS、runbook 改寫；ADR0079 補切換內容、預先驗證及「退役範圍與取回」（仍為 Proposed） |

`app:status` 只讀：列出資料庫（可連線、migration 是否在 head）、模型是否設定（不印 key）、PDF 字型／瀏覽器、Web 建置；`app:migrate` 是唯一改 schema 的命令。沒有移植舊的初始化精靈、OpenRouter 或 Windows 認證管理員接線（ADR0079 明定不做相容層）。

### 實際驗證（工作目錄皆為該 worktree；工具鏈沿 [T01 §2](t01-foundation.md#2-可接續的環境與命令)）

- **鎖定安裝**：`uv sync --project apps/api --locked`（uv 0.12.20）與 `pnpm install --frozen-lockfile`（pnpm 12.5.1、Node 24.19，393 套件）；快取命中，沒有改 lock。
- **根 `pnpm run check` 通過**（lint → typecheck → test → build）：Ruff check／format（429 檔）、ESLint；mypy strict（279 source files）、`tsc`；node 測試 4 項（當時；後加轉發參數測例為 5 項）、**1,113 項單元／契約測試（16 秒）**、**162 項前端測試**；契約生成核對；production build（952.67 kB JS，沿既有 chunk 警告）。
- **發現並修正的反例（Red → Green）**：第一次根 `check` 在 Python 測試階段 **17 個單元測試模組收集失敗**（`ModuleNotFoundError: No module named 'tests'`），原因是測試以 `tests.fixtures…` 匯入共用夾具，只有從 `apps/api` 啟動才解析得到；文件原本就寫從 repo root 執行同一命令，所以是文件與設定不一致的潛在缺陷。在 `apps/api/pyproject.toml` 加 `pythonpath = ["."]`（原分支提交 `313acc54`），根命令全數通過；原分支上以 console script 從 repo root 跑單檔也由失敗變為 7 passed。
- **操作旅程（真 PostgreSQL，新 schema `cutover_verify`，隔離 `_test` DB）**：`app:status` 無設定時回報四項「未設定」且 exit 0；`app:migrate` 建立 namespace 並升到 head（exit 0）；有設定時 `app:status` 顯示「資料庫可連線、migration 在 head／key 已設定（隱藏）／字型與瀏覽器 ok／Web 建置已找到」；`pnpm start --port 8104` 啟動單一程序：首頁 200 `text/html`、`/job-files/<id>` 深連結在瀏覽器式 `Accept: text/html` 下 200、建置資源 200、缺失 API 在接受 HTML 時仍 404、`/api/health` ok；經 HTTP 建立合成職務檔後**硬停止**後端三個程序、以同一根命令重啟，職務檔仍在清單中。
- **探針誤判（非產品問題）**：PowerShell `Invoke-WebRequest` 預設 `Accept: */*`，深連結得 404，這是 FastAPI frontend 只對 HTML 導覽套用 SPA fallback 的設計；以瀏覽器式 `Accept` 即 200。

### 未驗與限制

- 這是**同機乾淨 worktree**，不是另機網路 clone、容器或 Linux；依賴取自本機快取。
- 候選分支上的真模型旅程與 PDF 另記於 T17／下節（若已執行）；這裡的啟動驗證沒有發送模型請求。
- 根 `check` 不含真 PostgreSQL 整合測試、瀏覽器旅程與真模型；它們仍依各任務證據分開執行。
- 尚未更新 `current-decisions.md`、各 App README 的狀態標頭與 ADR 採用狀態——那是放行時的同步動作，不在候選預先改寫。

## 切換候選重基與重驗（2026-10-02）

**重基：**候選分支 `target-cutover-candidate`（原 `5bccf4fb`，基準 `57db0b5f`）重基到目前主線 `target-rebuild`（`2c70f0ef`，主線在候選建立後多了 13 個提交，含 `docs/` 的大規模整理）；新 head 當時是 `f11f23b6`，8 個提交（原 6 個＋2 個同步），與主線無分歧（`target-rebuild` 的每個提交都在候選裡）；其後主線又增加只動文件的提交，候選已再重基（無衝突，現為 `280a9474`，基於主線 `f51280aa`）。放行前仍須再核對一次是否落後。**沒有 merge、push，原分支未動，ADR0079 仍是 Proposed。**

| 衝突 | 解法與理由 |
|---|---|
| `experiments/jd-relational-app/tests/support/p3_trial_server.py`（候選刪除、主線改了一個證據路徑） | 刪除：該檔本來就在 379 檔退役清單，主線的修改只是路徑改名 |
| `experiments/jd-relational-app/README.md` | 保留退役標記，並採主線更新過的連結行 |
| `ARCHITECTURE.md`、`README.md` | 採候選的「新產品是正式產品」敘述，只併入主線新增的兩條導覽（找檔案／接手工作、教授與技術評閱者）；移除自動併入的「本頁仍描述 ADR0077 的正式產品」句 |
| `docs/README.md`（主線整份重寫） | 採主線的新結構，把候選的意圖重新套上：導言、啟動入口列、權責表、目錄分類表；另修兩處殘留（目錄分類表與 `docs/specs/README.md` 仍稱舊 App 是現行正式產品） |

另補兩個同步（`f11f23b6`）：ADR0079「採用前條件」改成 2026-10-02 的真實狀態（T14／T16／T17 已結案、T18 待放行、仍須查回的限制），runbook 診斷表新增兩列——額度用完（`credit_balance_exhausted`，不重試、補額度後重送）與資料庫伺服器重啟後須重啟後端。

**實際驗證（候選 worktree，工具鏈沿 [T01 §2](t01-foundation.md#2-可接續的環境與命令)；沒有送任何模型請求）：**

- 根 `pnpm run check` **exit 0**：Ruff 433 檔、mypy strict 280 個來源檔、`tsc`、node 測試 5 項、**1,152 項單元／契約測試（21.5 秒）**、**162 項前端測試（28 檔）**、契約生成核對、production build（952.67 kB JS）。後端測試比先前的 1,141 多 11 項，是主線新增的 harness 續跑測試。
- 入口文件連結：README、ARCHITECTURE、CONTRIBUTING、docs/README、specs/README、目標架構地圖、實作入口、runbook、current-decisions、兩個 App README、兩個退役 README、ADR0079 共 14 份，只剩 `current-decisions.md` 既有的 11 個歷史壞錨點，與主線同一份的基準數字相同。
- **`app:status` 先正確地擋下舊 schema：**候選驗證用的 `cutover_verify` 還在重基前的 migration 版本，診斷回報「schema NOT usable，先 `pnpm app:migrate`」；依指示 `app:migrate` 後回報「reachable, migrations at head」（0021）、模型 key 已設定（隱藏）、字型與瀏覽器 ok、Web 建置已找到。
- 以根 `pnpm start --port 8104` 從重基後的樹重啟（只停止以命令列與埠確認身分的候選後端 3 個程序）：首頁 200 `text/html`、`/job-files/<id>` 深連結在瀏覽器式 `Accept` 下 200、缺失 API 404、`/api/health` ok、先前驗證資料仍在（1 份職務檔案）。探針腳本兩處本機小錯（用了 PowerShell 唯讀的 `$home`、深連結沒帶 `Accept`）已修正，不是產品問題。

**仍未驗：**候選分支上的真模型短旅程與 PDF——**OpenAI 帳戶額度已用完**（2026-10-02 05:16 起，見 [T16 §12](t16-compaction-continuity.md#12-b1b2-輪前壓縮的真模型觀察2026-10-02執行前-manifest)），補額度前不執行；它不在 T18 要求的「先驗」清單內，產品程式碼與原分支相同（重基只帶入文件與 harness 腳本／測試），因此不是放行阻擋條件，但放行前若有額度建議補一次（約 US$0.1）。同機驗證的限制（非另機／容器）不變。**T18 不勾**：放行與否由 Owner 決定。

## 放行與切換（2026-10-02）

**決定：**T14／T16／T17 結案、候選分支重基並通過最終驗證後，Owner 在「放行／先補額度再放行／先不放行」中選擇**放行**。

| 項目 | 結果 |
|---|---|
| 合併 | `git merge --ff-only target-cutover-candidate`：`target-rebuild` 由 `6ad33bcb` 快轉到 `9438347c`（9 個提交）；只在本機，沒有 push、沒有對外部署 |
| 最終檢查 | `9438347c` 的根 `pnpm run check` exit 0：Ruff 433 檔、mypy strict 280 檔、node 測試 5、後端單元／契約 1,152、前端 162（28 檔）、契約生成核對、production build；快轉後的樹與該提交相同，所以不需另跑 |
| 退役清單 | 與主線 diff：刪除正好 **379** 檔（`experiments/jd-relational-app` 336、`packages/consultant-memory` 41、`scripts` 2），範圍外 0；保留 16 個 Markdown／`adoption.json` 沿革檔；另 5 個新增、19 個修改 |
| 可取回 | `git show 6ad33bcb:<路徑>`；ADR0079 的清單重建命令實測得 377 個非 Markdown 檔（336＋41）加 2 個啟動器。重基後先前引用的 `d08a3b09` 不在歷史內，已全部改引 `6ad33bcb`（本檔上方表格的舊雜湊是重基前的歷史紀錄） |
| 沒動的 | DB、volume、秘密、ignored 與未追蹤檔（舊目錄裡的 `node_modules`、cache 等本機殘留檔仍在）、Demo、RAG；沒有遷移舊資料 |
| 文件同步 | ADR0079 → Accepted、ADR 索引標 0077 為 Superseded by 0079；README／ARCHITECTURE／AGENTS／docs 導覽、目標架構地圖與六份架構文件的狀態、任務表、current-decisions 同步 |

**仍保留：**候選 worktree `S:\caliburn-cutover` 與分支 `target-cutover-candidate`（現與主線同一提交）、候選 app 8104（schema `cutover_verify`）仍在；是否清理由 Owner 決定，本次不刪除。**限制不因放行消失**：候選上的真模型短旅程與 PDF 因 OpenAI 帳戶額度用完未跑（不是放行條件）；同機驗證非另機／容器；其餘見[實驗發現的問題彙整](../../../reports/experiment-findings.md)。
