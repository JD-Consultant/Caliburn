# 真瀏覽器 CDP driver

日期：2026-09-14。只存在於 tests；production 不 import。用來讓代理實際操作已經跑起來的 App，不是自動化測試框架，也不取代任何單元或真 PG 測試。

## 依據與版本

- 協定：[Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)，本檔只用 `Page`、`Runtime`、`DOM`、`Input` 四個 domain。查閱 2026-09-14。
- 瀏覽器：本機 `C:\Program Files\Google\Chrome\Application\chrome.exe`，`--headless=new`，獨立 `--user-data-dir`（放在該次 fixture 目錄下），`--no-proxy-server`，關掉背景網路與同步。
- 傳輸：工作區既有的 `websockets` 16.1.1（相依樹內既有套件）。**沒有新增相依**，沒有 Playwright／Puppeteer／Selenium。

`Input.dispatchMouseEvent`／`dispatchKeyEvent` 產生的事件在頁面端 `isTrusted` 為 true，走瀏覽器自己的輸入路徑；座標是主框架 viewport 的 CSS 像素，與 `getBoundingClientRect`／`elementFromPoint` 同一個座標系。

## 界線

- `reachable()` 在按下前要求元素存在、有版面尺寸、未 `disabled`，且 `elementFromPoint` 在該點命中它自己或其後代。**按不到就是失敗**，不改用 JS `.click()` 或直接呼叫 API 繞過畫面。
- `click()` 先等版面在兩次量測間穩定（位移 < 1px），按下後由頁面自己回報這次點擊的 `event.target` 是不是原本瞄準的元素；不是就重新量測再試，三次都不是才失敗。這個監聽器只記錄，不取消、不改寫、不重放事件。
- `FETCH_TRACE` 必須用 `Page.addScriptToEvaluateOnNewDocument` 安裝：App 在首次 render 就把 `fetch` 抓進 `JdApi`，載入後才包裝會錄不到任何東西。它只觀察，不延遲、不重送、不代答。
- 沒有網路故障注入、沒有 HTTP 閘門、沒有並行分頁控制；需要那些請用 `ui_response_gate_server.py`。
- headless，不是實體視窗；沒有實體 IME、觸控或多螢幕。

## 用法

App 要先由既有 helper 跑起來（`ui_response_gate_server.py` 或 `ui_chat_server.py` 的 `prepare`／`initialize`／`serve`），Web 用 `JD_API_ORIGIN=<該次 API origin> npm run start` 服務於 127.0.0.1:3002。旅程腳本見 [還原與撤回實證](../../../../docs/specs/evidence/jd-relational-ui-restore/)。
