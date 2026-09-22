# Web request deadline 相容性施工與驗收紀錄

日期：2026-09-21

## 範圍

本次只處理新 JD Web 的 HTTP client request deadline 相容性。產品目標為目前支援的新版 Chrome／Edge，採用標準 `AbortSignal.timeout()`，不保留舊瀏覽器 fallback。既有的 request identity、未知結果、原操作查回、不自動重送、API contract、JD／Memory／顧問流程均未改動。

## 實作

- 使用標準 `AbortSignal.timeout(15_000)`；deadline 覆蓋 fetch、完整 response body 讀取及 JSON 解析。
- 完整 body 可讀但 JSON 語法錯誤時回報 `invalid_response`。
- body 讀取中斷、abort 或其他 transport 讀取錯誤時回報 `response_unknown`。
- 沒有加入 retry、`Promise.race`、新的 service、state manager 或依賴。

## 離線證據

使用專案指定的 Node 24.19 runtime：

- `tests/api.test.ts`：**47 PASS／0 FAIL**。
- 完整 Web 測試：**308 PASS／0 FAIL**。
- `npm run typecheck`：通過。
- `npm run build`：Next production compile 通過；後續建置程序在目前 Windows 環境以 `spawn EPERM` 結束，獨立 `npm run typecheck` 已通過。

回歸涵蓋：標準 `AbortSignal.timeout()` 確實接收 15 秒 deadline、body 中斷保持 `response_unknown`、完整但壞 JSON 保持 `invalid_response`，以及既有的 unknown 不重送規則。

2026-09-21 決策：只支援目前目標的新版 Chrome／Edge，不為沒有 `AbortSignal.timeout()` 的舊瀏覽器增加 fallback；這是支援範圍收斂，不是 IAB response-read 問題的修正。

## 真瀏覽器邊界

前一輪在全新 Windows DPAPI／PostgreSQL 隔離 fixture、真 Next production build、Codex IAB 中重跑建立文件時：

- API 觀察到請求抵達，HTTP 200、response start／body end 都已由 ASGI send 完成，CORS origin 也符合；資料庫實際留下建立的文件。
- 瀏覽器仍把同一個 POST 的讀取結果呈現為 `response_unknown`，保留原 request，沒有重送；使用原 request key 查回仍未在 IAB 中完成。
- 因此這不是「資料未保存」證據，也不是「完整真瀏覽器流程通過」。目前只能把問題縮小為 IAB 端 response 讀取／傳輸相容性仍待定位。

結論：本次 client deadline 與錯誤分類的離線施工完成；Stable Chrome 控制組通過，Codex IAB 相容性仍 **OPEN**，Edge 控制組本輪未取得可用的瀏覽器證據。這些 gate 分開記錄；不因 server 端已送完 body 就宣稱 IAB 已讀取，也不在沒有新證據下調寬 CORS、加入 retry 或改動資料保存語意。

## 2026-09-21 IAB response-read / transport fault isolation

本輪以全新隔離資料庫、同一 production Web build、同一 API，先維持產品程式不變，再做 IAB 與 Stable Chrome 控制組。模型 transport 為固定離線合成，沒有 provider request。

### Codex IAB

- 初始文件列表 GET 成功，表示一般 GET body 可以讀取。
- 建立文件沿現有 UI 流程先呼叫 `POST /api/document-creations/lookup`；伺服器觀察到 HTTP 200、CORS origin 符合、ASGI response start 與 body end 均正常返回。
- IAB 在這個 lookup response 的讀取階段即顯示 `response_unknown`，所以尚未進入真正的 `POST /api/documents` 建立；按「查回並繼續原建立」後，同一 request key 的 lookup 仍重現相同結果。
- 本輪隔離資料庫只留下控制組建立的文件；IAB 的真正 create 沒有被送出。這與前一輪「server 已 commit 但回覆遺失」的場景不同，不能把兩輪證據混寫。

本次重新執行同一 IAB 流程仍可重現 UI 錯誤；隔離 API 收到的觀察皆為 HTTP 200、CORS origin 符合，且 response start／body end 均已轉送。這次 fixture 的收尾也確認 `model_request_count=0`、`writer_execute_count=0`、Saver connection 已關閉，因此重跑沒有產生模型或正式資料副作用。這是 IAB 失敗的可重現性證據，不是 browser-side root cause 證據。

目前可用的 Codex IAB 操作介面只能取得畫面／可存取性狀態，沒有提供上述 Network event 與 console 原始欄位；未以腳本注入、raw CDP 或其他繞過方式補造這些訊號，所以仍不能宣稱已完成 IAB exact root-cause isolation。

IAB 的 `javascript:` 只讀 probe 被 Codex 瀏覽器 URL 安全政策拒絕；沒有用 raw CDP、腳本注入或其他方式繞過，因此本輪沒有捏造 IAB 內部的 `responseReceived`／`loadingFinished` 訊號。

### Stable Chrome 控制組

同一 production Web／API 由隔離 Stable Chrome 執行相同的 lookup→body read→create：

- lookup：HTTP 200、`application/json`、完整 JSON body 可由 `response.text()` 讀取。
- create：HTTP 200、`application/json`、完整 JSON body 可由 `response.text()` 讀取。
- CDP Network 同時觀察到兩條路徑的 `responseReceived` 與 `loadingFinished`；沒有 `errorText`、`blockedReason` 或 `corsErrorStatus`。
- 同一 API 的 POST response framing 為 `Content-Type: application/json`、固定 `Content-Length`，沒有 `Transfer-Encoding` 或 `Content-Encoding`；CORS 為單一正確 origin 並帶 `Vary: Origin`。

### Stable Edge 控制組

本輪也準備了同一隔離資料庫、同一 production Web／API 與相同 lookup→body read→create 腳本，使用本機 Edge 153.0.4234.48。Edge 的 headless DevTools endpoint 曾短暫可取得，但在建立可用頁面 Network session 前即關閉連線，沒有取得任何可核對的 lookup／create request、response body 或 Network event。

因此本輪 Edge 結論是 **UNVERIFIED**，不是 PASS，也不是產品失敗。隔離 API 的收尾報告確認沒有因此產生模型 request 或 writer mutation；服務與 Web 之後均已停止，3002／8767 沒有留下 listener。未把這個控制失敗當成產品 HTTP 證據，也沒有因此修改產品程式。

三個驗收環境獨立判定：Edge 的 UNVERIFIED 不降低 Stable Chrome 已取得的 PASS；Codex IAB 的 OPEN 也不回溯否定 API／DB 或 client deadline 的 PASS。

### 2026-09-21 目前標準後的 IAB 基本流程重跑

為核對採用標準 `AbortSignal.timeout()` 後的真瀏覽器基本路徑，另建立全新的新 JD App 合成 fixture `jd-ui-gate-a1b2c3d4e5f6478899aabbccddeeff00`，使用 API `8769`、新版 Next production Web、Codex IAB，provider 關閉且沒有模型呼叫。

- IAB 初始文件列表 GET 成功，完整畫面載入。
- 透過畫面建立「新標準驗收文件」成功；lookup 與建立回覆均能被 App 讀取，接著載入完整六章 JD 編輯區。
- API 唯讀查回確認同一隔離 dataset 已保存該文件；`serve.finished.json` 確認 `closed=true`、Saver 已關閉、沒有 writer operation 或模型 request。
- 本輪沒有取得 Network／console 原始事件，因此不宣稱已解出先前 IAB failure 的內部根因；但先前的 `response_unknown` 在這個新 fixture／目前標準實作中沒有重現。
- API、Web、PostgreSQL 與 IAB 驗收服務均已正常收尾，沒有留下 listener；測試 volume 保留，沒有清除資料。

### 2026-09-21 新 App 顧問旅程的 IAB 重現

接著使用另一個全新 fixture `jd-ui-gate-b1c2d3e4f5a6478899aabbccddeeff11`，由新 JD App 的 `ui_chat_server` 提供真 managed host／LangGraph／JD tool／Saver／SQL 接線，模型 transport 維持固定離線合成，沒有 OpenRouter request。

- IAB 初始 GET 成功；建立文件時，畫面收到 `response_unknown`，保留原名稱與原操作，顯示「查回並繼續原建立」，沒有自動重送。
- 明確按一次查回後仍呈現同一結果；未進入顧問回合或 JD writer。
- server evidence：`GET=1`、`OPTIONS=2`、`POST=2`，每筆都是 HTTP 200、CORS origin 相符、`response_start_forwarded=true`、`response_body_end_forwarded=true`；`model_request_count=0`、`writer_execute_count=0`。
- 這次再次確認：IAB 的 response body read failure 可以發生在 server 已完成送出、且沒有任何顧問／資料寫入副作用的情況；仍沒有 Network／console 原始事件可把它細分到 IAB 內部層。
- 顧問服務、Web 與測試資料庫已停止，Saver connection closed；沒有留下產品服務。

### 下一次 IAB 診斷的最小證據

下一輪只有在取得真正 browser-side Network／console 原始訊號後，才進一步區分 IAB policy／CORS、response body delivery／Chromium network layer，或 IAB bridge／renderer 問題。至少需要保留：

```text
requestWillBeSent
  ↓
responseReceived
  ↓
dataReceived
  ↓
loadingFinished 或 loadingFailed
```

若為 `loadingFailed`，再記錄 `errorText`、`blockedReason`、`corsErrorStatus`；兩種結果都要搭配 HTTP `status`、response headers、`encodedDataLength` 與 timing／duration。沒有這組證據時，不修改 CORS、retry、request identity 或 `response_unknown` 保存語意。

### 階段結論

目前最符合證據的分類是：**Codex IAB 對跨來源 POST response body 的讀取／傳輸相容性問題，或 IAB acceptance harness 特有問題**。尚不能在沒有 IAB Network／console 原始訊號時，細分成 Chromium body delivery、IAB bridge 或其他內部層。

已排除或未支持的方向：

- 不是 15 秒 deadline；IAB 錯誤在短時間內出現，伺服器處理約 0–16 ms。
- 沒有證據支持 CORS mismatch；IAB lookup 的伺服器 origin 比對成功，Stable Chrome 亦通過同一 preflight／POST。
- 不是完整 JSON 本身格式錯誤；Stable Chrome 與原始 HTTP framing 都能讀到合法 JSON。
- 不能因此修改 `api.ts`、放寬 CORS、加入 retry、改 request identity 或改保存語意。

目前 gate 狀態為：**Stable Chrome：PASS；Stable Edge：UNVERIFIED；Codex IAB 基本 GET／lookup／create：本輪 PASS；Codex IAB 先前 failure 的 exact root cause／完整 App 旅程：OPEN；API／DB correctness：PASS；client deadline／error semantics：PASS。** 產品層沒有新增修正依據；若要關閉 IAB OPEN，仍需取得真正 Codex IAB 的 Network／console response-read 訊號，並完成完整需要的旅程；在此之前維持現有 `response_unknown` 與原 request 查回邊界。
