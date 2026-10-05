# Docker 示範站更新與錄影前檢查

本次將 `caliburn-jd-docker-test` 的 App 更新為目前工作目錄建置的版本。網址維持 `http://127.0.0.1:8105/`；App、資料庫及中文 PDF 已可使用。尚未拍攝產品影片，也未新增真模型訪談。

## 發現與處理

原 App 容器建立於 2026-10-03，沒有掛載原始碼。重新啟動後仍使用舊映像；讀取容器內程式並與工作目錄比對，三份關鍵檔案的 SHA256 不同，且公版參考工具模組不存在。因此需要重建 App 映像並替換容器。

依既有 [runbook](../../runbook.md#docker-操作)及 Docker 官方的 [build](https://docs.docker.com/reference/cli/docker/compose/build/)／[up](https://docs.docker.com/reference/cli/docker/compose/up/)方式，先完成建置，再正常停止 App、以新映像執行 Alembic，最後重新建立 App 容器。這次只升級 `caliburn` namespace；沿用原 PostgreSQL 與 named volume，沒有清空資料。

使用者允許示範資料不保留，但更新本身不需要刪除資料庫。原 volume 另有隔離實驗與測試 database，維持原狀。

## 環境與結果

| 項目 | 本次核對 |
|---|---|
| 工作目錄／分支 | `S:\caliburn`／`jd-app-docker`，含尚未提交的既有功能；不是僅以 HEAD 建置 |
| Compose project | `caliburn-jd-docker-test` |
| App／PostgreSQL | `caliburn-jd-docker-test-app-1`／`caliburn-jd-docker-test-postgres-1` |
| 主機埠 | App `8105`；PostgreSQL `55441`，均綁定 loopback |
| 新 App 映像 | `sha256:51332a7d6c570eb90dd8e0a79163848ad62da2101575772ac8caa42384605047` |
| 替換容器時間 | 2026-10-05 22:04:30，臺灣時間 |
| 建置 | 鎖定依賴安裝、TypeScript 檢查、Vite build、後端 wheel、匹配的 Chromium 安裝均完成；Compose build exit 0 |
| Migration | exit 0；資料庫 head 為 `0024_occupation_reference_state` |
| 啟動 | Compose `up --wait` exit 0；App 為 `healthy` |
| HTTP 與畫面 | `/api/health` 回 `status: ok`；清單及合成 JD 頁面可讀，訪談輸入、就地編輯與收合控制可見 |
| 中文 PDF | 短版正式 JD 匯出回 HTTP 200、`application/pdf`、150,334 bytes，檔案以 `%PDF-` 開始 |
| AI 設定 | 後端已載入既有 OpenAI key；未輸出或複製金鑰至紀錄 |
| 外送與執行 | 替換前及啟動後 `caliburn.executions` 均為零；本次未提交訪談或呼叫模型 |

容器內三份關鍵程式與建置後的工作目錄逐一比對，SHA256 相同：

| 程式 | SHA256 |
|---|---|
| `agents/job_consultant/instructions.py` | `a4865cc5ca115a6d4dd42f95e188a8758e80f3ccb856d5fde385fe4aa001de8b` |
| `agents/job_consultant/tools.py` | `0bcf420d7c6d823973e55a43acb76306450dff57ab39da5338bde3a449762b33` |
| `bootstrap.py` | `2558e2bcb81dfc78d4b94280947df6c3efd028f2370e18e1969f7730d64c9555` |

建置期間的主要等待是 npm 套件來源檢查、Debian 依賴下載及 114.3 MiB 的 Chrome Headless Shell 下載。下載及建置最後完成；沒有因等待修改鎖定版本或略過安裝。

## 錄影準備

目前兩份「Docker 中文 PDF」檔案是原交付測試用的合成 JD，只有 App 開場及人工 JD，不能拿來展示完整 AI 訪談或 Memory 引用。錄影前仍需準備有正式訪談、JD 來源與待核對差異的合成案例，沿[產品影片腳本](../../reports/product-demo.md)拍攝。

新公版參考工具模組已包含於映像，但這組 App 尚未設定 `CALIBURN_OCCUPATION_REFERENCE_URL`。若影片要展示公版搜尋，還需啟動可用的 RAG 服務並配置容器可達的 URL，再驗證實際搜尋。程式已打包不等於該功能已啟用。

本次核對的是部署、畫面讀取與 PDF 匯出。AI 訪談效果、公版選用品質及新功能的完整旅程，沿各功能既有證據判讀；這次沒有新增相關品質結論。操作輔助腳本與 PDF 留在被 Git 忽略的 `.research-tmp/docker-update-2026-10-05/`。
