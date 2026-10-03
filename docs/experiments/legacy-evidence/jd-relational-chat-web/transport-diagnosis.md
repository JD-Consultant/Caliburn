# 本機聊天 Web：Fetch 傳輸故障的有限診斷

查閱／驗證日期：2026-09-13。狀態：**根因 OPEN；本輪定點診斷停止。**已確認第三組失敗請求並非由 App 的 15 秒 signal timeout 觸發；尚無足夠證據歸因於 CORS、App、Chromium 或 IAB 傳輸層。不得將 server 200／ASGI send 返回改稱瀏覽器已收到，也不得把第一次失敗改記為 PASS。

本稿區分獨立代理直接讀取的本機證據、主代理實際瀏覽器觀察、官方契約及程式推論。只使用合成資料；無付費 provider、配置弱化或永久診斷元件。

## 1. 前兩組已有證據

- [第一組](browser-first.md)：第一輪取得三次完整合成 SDK 回覆及一筆 confirmed JD 修改，後续 `fresh()` 的 fetch 拒絕。員工明示重新查看後，原回合文字、JD 與差異恢復，沒有另送 start；第二輪純訪談及重開另有實際驗證。這證明原結果可查回，不代表首輪傳輸完全正常。
- [第二組](browser-second.md)：建立文件後的 fetch 同樣拒絕。一次點擊正常會先 lookup，再視結果 create；兩次 `POST other` 本身不是重複建立的證據。取消對話框、明示查回／查看後仍有立即拒絕，遂停止重送式排查。
- 第二組獨立代理只做一次帶指定 Origin／dataset header 的本機 GET，完整取得 HTTP 200、309 bytes JSON 與一份文件 ID `76287bb7-3400-4195-8c4c-753533cc4224`。ACAO 恰有一個 `http://127.0.0.1:3002`，`Vary` 恰有一個 `Origin`；沒有重複 ACAO／Vary。這只是 App 至該本機 HTTP client 的證據，不是瀏覽器成功證據。

唯讀核對現行組裝：只有 `query_api.py` 建立一層 CORS middleware，位於安全錯誤 boundary 外；catalog/configured 路由允許 GET／POST／PATCH 及 Content-Type／If-Match／X-JD-Dataset，與 Web 實際請求一致。`credentials: omit` 與服務不啟用 credentials 相符。已安裝 Starlette 1.6.0 對不允許的 private-network preflight 會返回 400；現有 OPTIONS 200 並不支持這項猜測。未發現足以要求放寬 CORS 的反例。

## 2. 第三組：只釐清原始 Fetch 拒絕類型

fixture：`jd-ui-gate-166a47f9ea04424a9548d0c9c473ca35`；真 managed host、DPAPI、專用 PG／Saver，API 8767／UI 3002。以下原生 JSON 已由本稿作者唯讀核對：

- [HTTP／SDK／writer 觀察](browser-third-observations.json)
- [API 關閉結果](browser-third-finished.json)
- [原身分初始化續作結果](browser-third-initialize-resumed.json)

以上三份附件逐位元組複製原始 JSON，未改寫值或格式。複製前已核對只有合成身分及執行觀察欄位，無金鑰、設定內容、原話、URL 或秘密；複製後再次核對原檔與附件完全相同。

主代理暫時在 `api.ts` 的 fetch catch 記錄固定方法、錯誤名稱分類、`performance` 耗時及 signal 是否 aborted；不記 URL、body、header 值或原始例外。重新 build 後，以真 IAB 按一次建立，主代理從 console 取得以下精確資料：

```text
JD_TRANSPORT_PROBE {"method":"POST","category":"TypeError","elapsedMs":13,"aborted":false}
```

這個 console 摘錄來自主代理的實際工具觀察，不是本稿作者另開瀏覽器重現。此時前端保留原建立請求，名稱鎖定，錯誤直接顯示於建立對話框內；沒有再造 request key 或自動送出。

服務端同組紀錄如下：

| ordinal | method／分類 | HTTP status | start 原 send 已返回 | body-end 原 send 已返回 | ACAO 與原 Origin 相等 | server elapsed_ms |
|---|---|---:|---|---|---|---:|
| 1 | GET other | 200 | true | true | true | 16.0 |
| 2 | OPTIONS other | 200 | true | true | true | 0.0 |
| 3 | POST other | 200 | true | true | true | 16.0 |

`model_request_count=0`、`writer_execute_count=0`、`evidence_failed=false`。這組沒有進入 AI 訪談。

**程式推論：**目前 `Workspace.createDocument` 必須先 await `lookupCreation`，收到可用的 not_found 才執行 create。一次點擊只有一筆 POST，且此 Fetch 被拒絕，因此這組停在 lookup，沒有進入後續 create。`other` 的原 trace 未保存具體 route，不能將推論冒充直接路由紀錄；writer 計數也只計 JD 編輯，不能單靠 0 推定 metadata 建立是否發生。

**本次可排除：**該請求為約 13 ms 的 `TypeError`，且同次 signal 的 `aborted=false`，與 15 秒 timeout 觸發不符。此結論只涵蓋第三組被捕捉的請求，不追溯替前兩組未記原始 category 的失敗定因。

**仍未定因：**preflight／server 200 和 ACAO 比對成功，無法證明 browser 最終通過全部 Fetch／安全檢查或取得 Response。獨立 CLI 成功也不能排除瀏覽器／嵌入層差異。IAB 工具 inventory 沒有可用 Network 詳細錯誤介面，未取得底層網路錯誤碼／blocked reason；不據此宣称 IAB 有 bug。

## 3. 時間、狀態及安全語意

### 計時精度

本稿作者於 frozen Python 3.12 唯讀執行 `time.get_clock_info`：`monotonic` 為 `GetTickCount64()`，resolution 0.015625 秒；`perf_counter` 為 `QueryPerformanceCounter()`，resolution 0.0000001 秒。helper 目前採前者，因此 server 的 0／15／16 ms 是合法但粗略的量化值；不能理解為零成本、精確的毫秒耗時或 15 秒逾時。第三組 browser 的 `elapsedMs=13` 是另一個 clock 的觀察，不應直接與 server 的數值相減推算傳输時間。

### Fetch 選項及原結果

`cache: no-store` 控制 HTTP cache；`credentials: omit` 排除憑證；`redirect: error` 在遇到 redirect 時產生 network error。它們不會停用 CORS。Fetch 的 network error 可拒絕為 TypeError，正常 HTTP 4xx／5xx 不會僅因 status 而拒絕 promise；因此服務端 status 和 JavaScript 的 Promise 結果本來就是不同層的觀察。[WHATWG Fetch](https://fetch.spec.whatwg.org/#dom-global-fetch)

`AbortSignal.timeout(15000)` 使用 active time；逾時 abort reason 為 TimeoutError。不能只看統一後的 `response_unknown` 猜測原因，也不能把 MDN 範例某一種 TypeError 解讀成所有 TypeError 都表示瀏覽器不支援 timeout。[MDN AbortSignal.timeout](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static)

現行正式 `api.ts` 在 fetch catch 只回安全錯誤；JSON 解碼與 schema／Problem 有不同出口。前輪查詢拒絕沒有將 `unconfirmed` 改成 `not_saved`，也沒有宣稱 JD rollback。若畫面保留前一次 running，含義是最後成功觀察尚未刷新，不能拿它證明 worker 此刻仍在執行；本輪沒有另改回合狀態契約。

### 有界後續定位條件

Chrome 官方 Network 文件提供 Preserve log、Status 的 CORS error／blocked／failed、Initiator 與 Timing。若後續已有環境能取得這些資料，優先核對同一請求的原錯誤分類及階段；不藉「Replay」重送 mutation。此案只需安全的欄位摘錄，不需新增 logging framework。HAR sanitized 主要排除 Cookie／Authorization 等敏感標頭，不能推定 URL／body 也已清除，因此未匯出或對外傳送整包 HAR。[Chrome Network reference](https://developer.chrome.com/docs/devtools/network/reference)

## 4. 官方依據與適用限制

只核對三個核心來源，未因未知故障另開品牌廣搜：

| 來源 | 查閱與版本／狀態 | 本案限制 |
|---|---|---|
| [WHATWG Fetch](https://fetch.spec.whatwg.org/) | 2026-09-13 查閱；Living Standard 頁面更新 2026-09-02。 | 規範說明可能的 Promise／網路錯誤邊界，不指定本案根因，也不保證特定嵌入實作。 |
| [MDN AbortSignal.timeout](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static) | 2026-09-13 查閱；頁面更新 2026-09-01，Baseline 2024。 | 舊瀏覽器支援須另核；本案捕捉到同次 signal 已建立且未 aborted，不能僅依 TypeError 猜 API 缺失。 |
| [Chrome Network reference](https://developer.chrome.com/docs/devtools/network/reference) | 2026-09-13 查閱現行官方文件；頁面標示更新 2024-07-16。仍有效，未見棄用通知。 | Chrome DevTools 能力不等於目前 IAB 工具提供相同介面；沒有可用介面時如實保留未知。 |

## 5. 初始化續作、清理與停止界線

第三組首次初始化因 sandbox 執行失敗，主代理核對原配置仍為 `initialization_pending`、原 PID 84720 已退出；沿既有 resume 以原身分完成 ready，沒有清 DB 或替換新 dataset 以繞過原 host。`initialize.resumed.json` 與 `serve.ready.json` 同為 dataset `9ae00012-a349-48eb-ba8d-a83438098458`、installation `cc9cb17b-8d5f-43b5-a84a-da9c0e59082a`。本稿未讀取任何 DPAPI 檔。

臨時 Fetch probe 已移除。本稿作者核對 `api.ts` 無 `JD_TRANSPORT_PROBE`／`console.warn`／臨時計時程式，且該檔 `git diff --stat` 為空；沒有留下永久 logging。API PID 72348 的 finished 記錄為 `closed=true`、`saver_connection_closed=true`、reason=requested；主代理另核對 Web PID 91652 身分後停止，並關閉 tab 12。finished 本身不當成程序死亡證明，原生身分核對仍由主代理操作紀錄承接。

主代理另完成[移除臨時診斷後的 clean build](transport-clean-build.txt)：普通 sandbox 中 Next 編譯成功，之後 TypeScript 子程序啟動遭 `EPERM`；使用相同 Node 24.19.0 與相同建置命令，在本機提升執行後完整通過 Next 16.3.5、TypeScript 檢查及 route build，並核對新的 `.next/static` 無 `JD_TRANSPORT_PROBE`。這是主代理實際建置結果，本稿作者未重跑；沒有因此啟動新服務或瀏覽器，也沒有改動 Fetch 安全選項。

本輪只做這一次第三組建立操作以取得分類證據，沒有再 retry、重送、放寬 CORS、延長 timeout 或擴通用診斷。停止目前故障廣搜，保留首敗及根因 OPEN；主線依計畫推進 CV-01。這不是宣布瀏覽器傳輸問題已修，也不等於完整 App／自然模型驗收通過。
