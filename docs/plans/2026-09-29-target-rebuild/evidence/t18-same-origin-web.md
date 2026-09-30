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
