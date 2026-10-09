# 原生開發與本機 PostgreSQL

本頁供修改程式或自行管理 PostgreSQL 的開發者使用。只想使用產品，從[第一次使用](getting-started.md)採 Docker 路線即可，不必安裝本頁列出的開發工具。

首次設定依序完成：

1. 核對[工具版本](#服務與版本)，並[安裝依賴](#安裝依賴)。
2. 設定[資料庫](#資料庫設定)，按需準備 [AI 金鑰](#ai-金鑰)與 [PDF](#pdf-匯出)。
3. 完成[初始化](#第一次初始化)，再[啟動 App](#日常啟動與停止)。

更新與測試另見[更新已有安裝](#更新已有安裝)、[驗證](#驗證)。所有命令都在專案根目錄執行。

## 服務與版本

| 項目 | 要求 |
|---|---|
| Node.js | `>=24.19.0 <25` |
| package manager | pnpm `12.5.1`，根目錄單一 lockfile |
| Python | `3.14`，由 uv `0.12.20` 管理（`apps/api/uv.lock`） |
| PostgreSQL | 本機 **18.6**，獨立程序；容器或本機安裝皆可 |
| API | `127.0.0.1:8100`，單程序、無 reload、無 proxy headers |
| Web | 正式：由 API 同源提供 `http://127.0.0.1:8100/`；開發：Vite `http://127.0.0.1:5173/` |
| 模型 | OpenAI Responses 直連，`gpt-6-luna`／high；key 只在後端使用 |
| PDF | 啟動前設定字型與 Playwright Chromium，見[PDF 匯出](#pdf-匯出) |
| RAG | 隔離且非預設依賴 |

不要按端口終止身分不明的程序；程式變更後在原前景終端正常停止再重啟。

`pnpm start`／`pnpm dev` 收到正常停止通知後，最多等待九十秒，讓原生 checkpoint 與其他資源收尾。Windows Ctrl+C 已送到同一 console，啟動器會先等待；啟動失敗等未能送出正常通知的情況，則明示為強制清理。

超過期限後，只強制停止本次持有的程序樹，再等最多五秒確認退出。強制停止時會提示結果可能尚未確認；重新開啟後，沿原 execution ID 查詢。未收到結果不代表未執行，也不會自動重送模型請求。

## 安裝依賴

```powershell
& {
    pnpm install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw 'Node 依賴安裝失敗，停止初始化。' }
    uv sync --project apps/api --locked
    if ($LASTEXITCODE -ne 0) { throw 'Python 依賴安裝失敗，停止初始化。' }
}
```

Node／TypeScript 只使用 `pnpm-lock.yaml`；Python 只使用 `apps/api/uv.lock`。不要產生 npm lockfile，也不要用 RAG Compose 建立 JD App 的資料庫。

## 資料庫設定

1. 建立一個空的專用 PostgreSQL database。首次安裝不搬移其他產品的資料；更新目前 App 時則沿用原資料庫。
2. 以環境變數明示連線，密碼由本機秘密管理注入，不貼在命令列歷史、文件或 Git：

```powershell
$env:CALIBURN_DATABASE_URL = 'postgresql://帳號:密碼@127.0.0.1:5432/caliburn'
$env:CALIBURN_DATABASE_SCHEMA = 'caliburn'      # 預設值；可省略
```

PowerShell 的 `$env:…` 只對目前視窗及其啟動的程序有效。換新視窗後，須重新提供相同的資料庫／schema 與所需 PDF 設定；不會從 `apps/api/.env` 載入這些設定。

## AI 金鑰

二擇一，後端只讀 `OPENAI_API_KEY` 這一項：

- 環境變數 `OPENAI_API_KEY`；
- 或 `apps/api/.env`（已被 Git 忽略）內**唯一一行** `OPENAI_API_KEY=...`，`pnpm start`／`pnpm dev` 會自動以 `--key-file` 載入。

key 不進 prompt、模型工具、Web bundle、URL、資料庫、checkpoint、一般 log 或 Git。檔案存在時，根啟動器以 `--key-file` 載入的 key 為準；不要同時保留兩份不同金鑰。更換 key 後須重啟後端。

`pnpm app:status` 不讀取此檔案，判讀方式見[診斷](README.md#判讀-pnpm-appstatus)。沒有 key 時人工 JD 仍可使用，AI 訪談明示停用，且不會自動 fallback。

注意：後端啟動時會續跑已接受但未完成的訪談與背景整理，這可能消耗模型額度；只想操作人工 JD 時不要提供 key。

## PDF 匯出

要匯出正式 JD 的中文 PDF，先準備下列兩項。暫不使用 PDF 可略過；缺少設定時，`GET /api/job-files/{id}/jd/export.pdf` 回 503，不下載空檔：

```powershell
$env:CALIBURN_PDF_FONT_PATH = 'D:\fonts\NotoSansTC-VF.ttf'              # 已授權的中文字型
uv run --project apps/api --locked python -m playwright install chromium --only-shell   # 鎖定版本的瀏覽器
if ($LASTEXITCODE -ne 0) { throw '瀏覽器安裝失敗，請查明原因後再啟動需要 PDF 的 App。' }
# 或指定與已鎖 Playwright 相容的 Chromium：$env:CALIBURN_PDF_CHROMIUM_PATH = '...\chrome.exe'
```

PDF 只匯出正式 JD、不含候選與員工姓名；畫面中文正確，部分字型的文字複製／搜尋會出現部首字元（已知限制，見 T13）。

字型必須使用實際可讀的檔案，下載方式見 [Noto CJK 官方指南](https://github.com/notofonts/noto-cjk/blob/main/Sans/README.md)。如果安裝瀏覽器時自訂了 `PLAYWRIGHT_BROWSERS_PATH`，後端啟動時也要提供相同值。換新終端後，在啟動前重新提供字型與自訂瀏覽器路徑；已啟動時須重啟才生效。

## 第一次初始化

資料庫與所需的可選功能設定就緒後，從同一個 PowerShell 視窗執行：

```powershell
& {
    pnpm app:migrate
    if ($LASTEXITCODE -ne 0) { throw '資料庫升級失敗，停止初始化。' }
    pnpm app:status
    if ($LASTEXITCODE -ne 0) { throw '設定檢查失敗，請依輸出查明原因。' }
    pnpm build
    if ($LASTEXITCODE -ne 0) { throw 'Web 建置失敗，停止初始化。' }
}
```

`app:migrate` 建立 App 業務 schema 並升級到目前版本，可重跑。App 啟動時只核對 migration head，不自動升級業務 schema、清資料或重建 volume；LangGraph 的 checkpoint 表則由官方 saver 在啟動時建立。

`app:status` 退出碼 0 不代表 AI 與 PDF 已經實際通過驗證，各項輸出的意義見[操作手冊](README.md#判讀-pnpm-appstatus)。

## 日常啟動與停止

先啟動已初始化的 PostgreSQL，再於根目錄選一種方式：

| 用途 | 命令與畫面 |
|---|---|
| 使用已建置的 App | `pnpm start`；後端同源提供 Web，開啟 `http://127.0.0.1:8100/` |
| 修改前端與後端 | `pnpm dev`；後端 `:8100` 與 Vite `:5173` 同時前景啟動，開啟 `http://127.0.0.1:5173/` |

`pnpm start` 需要先 `pnpm build`；沒有建置會明確報錯，不自動建置或猜目錄。在原終端按 Ctrl+C 正常停止：後端先停止新准入、保存已取得的結果並停在可恢復邊界，再釋放資源；強制關閉仍依最後可靠位置恢復。重開後，進行中或暫停的訪談可由介面找回並續作；背景整理由系統依持久狀態自動承接。

啟動器先執行一次 `uv run --locked`，同步既有專案環境並取得 Python 路徑，再直接啟動後端；自訂 `UV_PROJECT_ENVIRONMENT` 仍由 uv 處理。任一服務啟動失敗或退出時，只收尾啟動器持有的其他服務，不依程序名稱或埠號清理。Windows 的等待及強制停止依前述[服務與版本](#服務與版本)說明；強制停止不代表在途工作已全部保存。

隔離驗證時若前端使用第二個埠，可在**後端啟動前**設定 `CALIBURN_DEV_ORIGIN=http://127.0.0.1:5174`（只接受一個帶明確埠的 loopback HTTP origin），見[後端 README](../../apps/api/README.md)。

## 更新已有安裝

先讓工作停在安全點，正常停止自己啟動的 App，依[備份操作](README.md#資料庫與備份)備份原資料庫。沒有未提交修改且分支沒有分歧時，從專案根目錄執行：

```powershell
& {
    git pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw 'Git 更新失敗，請先核對本機差異。' }
    pnpm install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw 'Node 依賴安裝失敗，停止更新。' }
    uv sync --project apps/api --locked
    if ($LASTEXITCODE -ne 0) { throw 'Python 依賴安裝失敗，停止更新。' }
    # 本終端須已提供原 CALIBURN_DATABASE_URL／schema 與所需 PDF 設定。
    pnpm app:migrate
    if ($LASTEXITCODE -ne 0) { throw '資料庫升級失敗，停止更新。' }
    pnpm build
    if ($LASTEXITCODE -ne 0) { throw 'Web 建置失敗，停止更新。' }
}
```

不要因為 migration 或分支更新失敗就重建資料庫、刪 volume 或強制覆蓋工作。`git pull` 拒絕快轉時先核對本機差異；歷史修正的提交對照見歷史查閱。更新 Playwright 套件後，還需按[PDF 匯出](#pdf-匯出)重新安裝對應瀏覽器，然後依[日常啟動](#日常啟動與停止)啟動。

## 驗證

```powershell
pnpm check
```

也可使用窄命令：`pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build`。`pnpm test` 不需資料庫；真 PostgreSQL 整合測試需明確指定隔離的 loopback `_test` 資料庫並直接執行 pytest：

```powershell
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://測試帳號:密碼@127.0.0.1:5432/caliburn_test'
uv run --project apps/api --locked pytest apps/api/tests -m postgres -q
```

測試各自建立並回收隨機 schema，不碰既有資料。真 PostgreSQL、真瀏覽器與真模型結果分開記錄；離線測試不能代替 provider 或 UI 證據。付費驗證腳本須依 manifest 明示的有限預算執行。Windows 受限 token 可能讓暫存目錄權限出現 `WinError 5`，不得為測試變綠而放寬安全限制。
