# Caliburn 訪談與 JD 前端

React／TypeScript 前端，接 `apps/backend`。使用 MUI 元件與本機字型，提供 Workspace、訪談與完整問答、處理紀錄及 token、Plan、已發布 Memory、JD 編修／來源／歷史比較與 PDF。

桌面維持左訪談、右 JD 與獨立捲動；窄版用頁籤切換，兩區保留掛載。歷史查閱往返保留同工作區的未送訪談草稿與頁籤。單一淺色主題支援鍵盤焦點、高對比及減少動態效果；字型由本機提供，不向外部字型服務請求。

## 啟動與檢查

使用 Node 24、pnpm 12。依賴由專案根目錄的唯一 lock 安裝：

```sh
pnpm install --frozen-lockfile
pnpm --dir apps/frontend dev
pnpm --dir apps/frontend check
```

開啟 `http://127.0.0.1:5174`。Vite 將 `/api` 轉送至 `http://127.0.0.1:8101`，可用 `CALIBURN_API_URL` 明示另一個開發 Host；後端配置及資料庫初始化見[後端說明](../backend/README.md)。根目錄 `pnpm build` 產生前端靜態檔，`pnpm start` 由正式 Host 同源提供 `/api`、靜態資源及前端路由回退。部署設定見[操作手冊](../../docs/operations/README.md)。

在本目錄執行 `pnpm codegen`，從後端離線匯出 OpenAPI，生成 TypeScript、Ajv runtime guards及原生 SSE 具名事件清單；不啟動資料庫。陣列驗證器沿正式 HTTP response schema 生成。`pnpm codegen:check` 只在暫存目錄生成比對，不改產品檔。

## 可重跑的離線瀏覽器驗收

`scripts/e2e_host.py` 使用正式 Host／SDK 邊界與固定離線模型場景，沿真 PostgreSQL、工具及 Checkpoint 保存。先用 `uv sync --project ../backend --locked` 安裝後端及測試 helpers，準備 loopback、名稱以 `_test` 結尾且帳號可建立 schema 的專用合成資料庫。URL 不接受 query；`PGHOSTADDR`／`PGSERVICE` 須未設定。此入口不讀 `.env`，不使用真模型或正式員工資料。

從本目錄以獨立終端啟動 Host，明示既有 PDF 字型與匹配鎖定 Playwright revision 的 Chromium。以下參數須替換為自己的合成環境；不會自動下載瀏覽器。

```powershell
$env:CALIBURN_E2E_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/caliburn_e2e_test'
& ../backend/.venv/Scripts/python.exe -X utf8 scripts/e2e_host.py --port 8103 --pdf-font 'C:/path/to/NotoSansTC-VF.ttf' --chromium 'C:/path/to/chrome-headless-shell.exe' --output output/e2e-host.json
```

非 Windows 使用 `../backend/.venv/bin/python`。等 Uvicorn 顯示 `Application startup complete`；output 只記本次 PID／schema，不代表已啟動完成。每次建立新 UUID 業務與 Checkpoint schema，沿正式 migration／saver 初始化；Ctrl+C 只關閉這個 Host。合成 schema 保留供檢查，後續只按 output 識別清理自己的 schema。

另一個終端啟動 Vite：

```powershell
$env:CALIBURN_API_URL = 'http://127.0.0.1:8103'
pnpm dev
```

再執行瀏覽器測試：

```powershell
$env:CALIBURN_E2E_BASE_URL = 'http://127.0.0.1:5174'
$env:CALIBURN_E2E_API_URL = 'http://127.0.0.1:8103'
$env:CALIBURN_E2E_CHROMIUM_PATH = 'C:/path/to/chrome-headless-shell.exe'
pnpm test:e2e
```

每例建立獨立 Workspace。訪談固定場景涵蓋問答、正式 JD／Plan、Memory 發布、取消與 JD-only 撤銷；故障攔截測例另外標示。離線 SDK 串流只有 created／completed，這條旅程不證明逐字串流、native compaction 或真模型品質；事件、resync 與用量缺值另由契約及行為測例驗證。

## 責任與資料生命週期

```text
src/
  app/                      路由、QueryClient、主題、雙欄與跨功能刷新
  features/
    workspace/              清單、姓名、建立與刪除
    interview/              訪談、問答、同輪接續／取消、SSE、Plan與token
    memory/                 已發布map、固定發布版項目及來源
    job-description/        目前JD、expected_version保存、來源與PDF
      editing/              單一編輯槽、保存佇列與未確認草稿
      editor/               各內容區塊的編修操作
      history/              固定歷史、兩版比較及版本恢復
  shared/
    api/                    HTTP、原生EventSource與生成契約
    ui/                     安全Markdown、icons、焦點與捲動機制
```

依賴只由 `app → features → shared`；feature 不互相匯入。Query cache 是伺服器資料的前端來源，局部輸入與展開狀態留在負責元件。完成、取消與 JD 撤銷後由 app 刷新各正式投影，不按工具名稱猜保存效果。已確認 Workspace 刪除會取消查詢再清除同 scope 快取，遲到回覆不能復活資料。

後端在同一筆交易建立 Workspace、空 JD 與開場引導。前端在建立成功後讀取已保存的資料，不再建立 JD，也不因查不到資料而自動補建。訪談受理不明沿原 turn_id 查回；SSE 的暫時片段不冒充正式訪談，斷線先讀保存結果，恢復模型需要明確操作。只有正式取消完成才清除本輪內容。Token 顯示已保存 R／C 用量，缺值明示未知，不當成全部費用。

JD 的既有文字點選後進入單一編輯槽；單行 Enter、多行 Ctrl／⌘＋Enter 保存，Esc 取消。保存使用 expected_version；衝突與未知結果保留草稿，重新讀取核對後才由使用者明確套用。未確認文字與新增表單存於同分頁 sessionStorage，重開不自動重播，且不承諾跨分頁／裝置恢復。未完成或狀態未知的訪談輪讓目前 JD 維持唯讀，後端版本契約仍負責其他入口的交錯修改。

完成輪比較使用後端保存的固定前後版；「撤銷此輪 JD 改動」只回退 JD，由後端拒絕不安全的後續／交錯修改，保留訪談、Plan、Memory 與 Agent。一般版本恢復則恢復整份所選版並建立新版本。主 JD 只呈現目前保存內容；沒有候選／採用流程。引用查讀保留固定來源座標，未知不代表已核對。PDF 只匯出目前保存 JD，失敗不建立假下載。
