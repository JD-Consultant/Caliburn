# Docker 交付驗證

本次將正式 JD App 打包為 Linux 容器，驗證建置、資料庫初始化、同源畫面、中文 PDF 與重建後的資料保存。結果支持本機 Docker 交付；未重新評測真模型的訪談品質，也沒有搬移既有資料庫。

操作方式由 [runbook](../../runbook.md#docker-操作)維護，交付邊界見[介面與交付 §4.2](../../implementation/interface-and-delivery.md#42-docker-交付)。本頁保存驗證方法、發現與結果，不另訂產品規格。

## 環境與隔離

| 項目 | 本次使用 |
|---|---|
| 程式基準 | `main` 的 `13c0663a7d42e2e73b5c2ef45d20faa9e1b1fa11`，加本次 Docker 配置及明確監聽位址修改 |
| 日期與主機 | 2026-10-03；Windows 主機上的 Docker Desktop Linux containers |
| Docker Engine／Compose | `29.8.0`／`5.5.1` |
| 容器平台 | `linux/amd64` |
| 建置依賴 | Node `24.19.0`、pnpm `12.5.1`、Python `3.14.8`、uv `0.12.20`；沿用專案 lockfile |
| PDF | Python Playwright `1.63.0` 的匹配 Chromium；Noto Sans CJK TC `Sans2.004` 靜態 OTF 與授權檔 |
| 資料庫 | 官方 PostgreSQL `18.6-bookworm`；版本與 digest 見 Compose |
| 測試 project | `caliburn-jd-docker-test`，不同於預設正式 project |
| 測試入口 | App `127.0.0.1:8105`；PostgreSQL `127.0.0.1:55441` |
| 測試 volume | `caliburn-jd-docker-test_jd_postgres_data` |
| 整合測試 database | `caliburn_docker_test`；各測試使用隔離 namespace |
| 模型請求 | 未提供 OpenAI key；沒有付費模型請求 |

原有 PostgreSQL 容器 `caliburn-jd-postgres-18-6`（`55437`）持續執行，未停止、遷移或清除。測試只使用合成 JD，沒有取用員工私人資料。Docker Desktop 啟動時會恢復它原本管理的容器；此行為不等於本次重建了原資料庫。

## 設計依據與取捨

採一個 App 容器、一個 PostgreSQL 容器，以 Compose 統一啟停。App 同源提供 Web 成品、API、背景整理及 PDF，沒有增加 nginx、Redis 或額外 worker；資料庫獨立保存 named volume。這符合 Docker 的[單一職責與多階段建置建議](https://docs.docker.com/build/building/best-practices/)，不將「一個容器」誤解成只能有一個作業系統程序。

Python 依 [uv 官方 Docker 指南](https://docs.astral.sh/uv/guides/integration/docker/)以 lockfile 安裝，再將非 editable 環境複製到執行階段；Node、pnpm、uv 與原始 repo 不進執行映像。PDF 使用[與 Playwright 套件匹配的瀏覽器](https://playwright.dev/python/docs/docker)，字型及授權檔檢查 checksum。映像基底固定 digest，更新時需明確更新並驗證，不靠浮動 `latest` 自動換版。

資料庫掛載採 [PostgreSQL 18 官方映像](https://hub.docker.com/_/postgres)要求的 `/var/lib/postgresql`。App 只在資料庫健康後啟動；schema 升級仍是明確的一次性 Alembic 命令，不藏在日常啟動中。相依啟動與重啟的界線依 [Compose 官方說明](https://docs.docker.com/compose/how-tos/startup-order/)。

## 驗證方法與結果

| 驗證層級 | 方法 | 結果與能支持的結論 |
|---|---|---|
| 啟動器 TDD | 先驗原生預設、容器明確監聽與 proxy headers；未實作時 2 項失敗、1 項通過 | 修改後 3 項通過；原生仍綁 `127.0.0.1`，容器必須明確指定 `0.0.0.0`，任意位址被拒絕 |
| 專案離線檢查 | `pnpm check` | exit 0；Python 單元／契約 1,175 項、前端 43 檔／270 項、根啟動器 5 項通過；Ruff、ESLint、型別、契約生成核對及 production build 通過 |
| Linux 映像建置 | 真正執行 Compose build，不使用主機 `node_modules` 或 Python venv | 建置成功；前端、非 editable 後端、migration、瀏覽器及字型均可從映像使用 |
| 空資料庫啟動反例 | 新測試 volume 初始化後，不執行 migration，直接啟動 App | 啟動失敗並要求 migrations；沒有偷偷建示範資料或自動升級 |
| 明確 migration | 使用映像內的 Alembic 升級，之後啟動 App；再次執行升級 | 命令 exit 0，App 健康；重跑不清資料 |
| 容器執行邊界 | 只讀取指定的 inspect 欄位及安全的 runtime 探針 | UID `10001`、非 root、read-only、`init=true`；主機埠只綁 loopback；無 Node／uv、`.env` 或 `.git` |
| 同源 HTTP | 讀首頁、未知 API／asset；以不受信任 Origin 寫入 | 首頁 200；未知 API 與 asset 404；不受信任寫入 403；不是全域首頁 fallback |
| 無 key 行為 | 對隔離 App 送出合成訪談請求 | 503 `model_not_configured`，人工編輯與 PDF 仍可用；沒有產生模型費用 |
| 真 Chromium 畫面 | 在 App 容器內以 Playwright 開啟已保存合成 JD，等待職務名稱出現 | HTTP 200、名稱可見、`pageerror` 為空；確認 Web 成品與 API 接線，不代表完整 UI 品質測試 |
| 中文 PDF | 經真正 HTTP 匯出端點取得短版及長版 PDF，逐頁轉圖檢查 | A4 短版 1 頁、長版 3 頁；中文、80 行內容、分頁及頁碼可見；未見明顯缺字或裁切 |
| 資料持久性 | 保存 JD 後 `down`（不加 `-v`）、重新 `up`；審查修正後再重建容器 | volume 保留，兩份 JD 的修訂 ID 與文字長度完全一致；再次匯出長版 PDF 成功 |
| 真 PostgreSQL 整合 | 下列 4 份既有測試，連測試容器的 PG18；模型為腳本化回應 | 20 項通過；涵蓋 A 完成、B1／B2 發布、下一輪讀 Memory、來源差異及程序中斷接續，不是容器內真模型驗收 |
| PowerShell 操作說明 | 解析 README／runbook 的命令區塊；以退出碼 7 的無檔案副作用命令檢查停止行為 | 語法有效；失敗後不執行下一個步驟 |
| 文件連結 | 核對本次相關 8 份 Markdown 的本機連結目標 | 218 個路徑存在，未發現失效檔案連結；不將此檢查當成外部網站或 PDF 排版驗證 |
| 正常關閉 | 只停止本次測試 project，讀取 App 關閉訊息並核對 volume | Uvicorn 記錄 `Application shutdown complete`；測試容器停止，volume 保留，原資料庫仍健康 |

Python 型別檢查覆蓋 295 份來源檔；Ruff 格式檢查覆蓋 455 份檔案。Web build 仍有既有大型 chunk 提醒，本次未為容器交付改變前端分包設計。

真 PostgreSQL 測試命令在隔離開發環境執行，`CALIBURN_TEST_DATABASE_URL` 指向上述 `_test` database，不將帳密寫進紀錄：

```powershell
uv run --project apps/api --locked pytest apps/api/tests/integration/test_consultant_memory_http_journey.py apps/api/tests/integration/test_consultant_process_recovery.py apps/api/tests/integration/test_jd_source_http.py apps/api/tests/integration/test_memory_stage_changes.py -q -p no:cacheprovider
```

結果：`20 passed in 37.16s`。程序中斷測試覆蓋請求計數已保存、模型回應已保存、工具已提交與正式答覆已保存四個位置；驗證既有恢復規則，不新增第二套 Docker 恢復機制。

## 中文 PDF 與持久性觀察值

兩份合成 JD 均為「庫存管理專員」，各有一項「核對進貨及追蹤帳物差異」。短版任務描述 45 字元；長版為 80 行、3,750 字元。員工姓名設為「不應匯出姓名」，PDF 文字擷取確認沒有該姓名；長版末項「最終驗證報告」可取回。

| 合成檔案 | job file ID | 重建前後相同的正式修訂 ID |
|---|---|---|
| 短版 | `74c35d7d-7a68-4d5e-ab0f-6fdd0139718f` | `64424d98-e867-42b8-9388-dfc14abdc1b7` |
| 長版 | `01fad820-1ad9-43d7-8739-432e66929eee` | `d9e73947-4989-4621-a67d-636e143a99c2` |

首次匯出檔案的觀察值：

| 檔案 | 頁數 | bytes | SHA256 |
|---|---:|---:|---|
| `jd-short.pdf` | 1 | 150334 | `7bdf6c6eef208e986282cf7b40e928b592985f5db5f3502d0eb85f1fb3048337` |
| `jd-long.pdf` | 3 | 156763 | `5de0a8ba4efd7ddbd5a32bfa8898d30db60534bd97d39c8bdd77b7077ba68c72` |

檔案與逐頁檢查圖留在本機被 Git 忽略的 `.research-tmp/docker-delivery/`；合成資料留在測試 volume。雜湊辨認當次匯出原件，不要求重新匯出的 PDF 位元完全相同；持久性比較的是正式修訂及內容。

最終測試映像為 `caliburn-jd-docker-test-app`，image ID：`sha256:4df4ce3ee6619412589920d27fe8ceb352d79583515bcb40eab3e60bd30e6f2f`。它只用於本機驗證，未推送 registry。

## 建置與審查發現

| 發現方式 | 問題 | 修正與驗證 |
|---|---|---|
| 第一次 Linux build 的 TypeScript 錯誤 | Web 原始碼匯入正式 HTTP JSON schema，但最初 COPY 沒納入該目錄 | 加入既有契約來源，不另生成一套；重新 build 成功 |
| 比較 build context | 初版過寬的 Web 排除範圍仍帶入舊建置快取 | 改為 Dockerfile 專用 allowlist，只收必要來源；完整 context 傳輸由 136.97 MB 降至 21.82 MB，後續增量傳輸更小；兩版均排除 `.env` |
| 審查 project 隔離 | 固定 App image tag 會讓測試與正式 project 共用建置結果 | 移除固定 `image:`，使用 Compose project／service 命名；實際核對測試映像名稱與容器來源 |
| 查 PG 官方 entrypoint | 空庫初始化的暫時 server 只開 socket，原 socket healthcheck 可能太早通過 | 改檢查 `127.0.0.1:5432` TCP；更新配置後健康並可執行 migration。此競態由[官方原碼](https://github.com/docker-library/postgres/blob/e00e1bd34ec5c8a8e7ad89b273b3d42efaf6d5bc/docker-entrypoint.sh#L264)推導，本次沒有實際觸發 |
| PowerShell 失敗探針 | 外部命令非零退出後，貼上的後續命令仍可能繼續執行 | 啟動／更新放在同一區塊，每一步檢查 `$LASTEXITCODE`；無檔案副作用探針確認停止 |
| 核對 Compose 契約 | 可選 key 檔的 `env_file.required` 有最低版本 | 文件明示 [Compose 2.24.0 以上](https://docs.docker.com/reference/compose-file/services/#required)，不假設所有舊版本皆支援 |

## 驗證範圍

本次支持這個平台上的建置、初始化、人工 JD 保存、中文 PDF 與容器重建資料保存。Memory 及程序恢復另以真 PostgreSQL、腳本化模型整合測試核對；未在容器內送出真 Luna 訪談，也未重新評測長訪談分析品質。既有產品品質與字型文字層限制仍以[整體驗證說明](../../architecture/verification.md)為準。

未驗證其他作業系統／CPU 平台、乾淨的另一台電腦或對外網路部署。既有資料遷入與備份還原不是本次工作，named volume 也不等於備份。測試結束後停止本次隔離 project，保留合成資料與本機 PDF；不清除其他容器、映像或 volume。
