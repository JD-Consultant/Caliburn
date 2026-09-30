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
