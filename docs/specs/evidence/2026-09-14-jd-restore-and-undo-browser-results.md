# JD 還原與整輪撤回：真瀏覽器驗收結果

日期：2026-09-14；Topic：JD-R002。承接[還原單位結果](2026-09-14-jd-restore-revision-results.md)與[施工計畫](../../plans/2026-09-13-jd-relational-app-implementation.md)。隔離 App，ADR0075 Proposed／production ADR0060 不變。零付費模型呼叫。

## 1. 完成效果

**員工真的按得到，也真的按得動。**在真 Chrome 上，從空白建立文件、打字、自動保存、開歷史、按「還原到第 2 版」、看過逐項比較再按「確認還原」，畫面與資料庫都回到第 2 版的內容；另一份文件經一次真訪談由 AI 寫入任務／成果／要求後，按「撤回這輪 JD 改動」再「確認撤回」，AI 這輪寫的內容一次收回，而這輪的對話、回覆與改動紀錄都還在。

兩條旅程都不是靠單元測試或型別檢查推斷，而是**實際的滑鼠事件落在員工看得到的按鈕上**，並由獨立唯讀連線另外核對 PostgreSQL。

產品程式只改了一處，就是設計 §4.2 的暫停：比較開著時停用 JD 欄位與訪談送出（[ChatPanel](../../../experiments/jd-relational-app/web/src/components/ChatPanel.tsx)、[HistoryPanel](../../../experiments/jd-relational-app/web/src/components/HistoryPanel.tsx)、[RunChangesPanel](../../../experiments/jd-relational-app/web/src/components/RunChangesPanel.tsx)、[DocumentWorkspace](../../../experiments/jd-relational-app/web/src/components/DocumentWorkspace.tsx)）。其餘新增的是測試 helper [browser_cdp.py](../../../experiments/jd-relational-app/tests/support/browser_cdp.py) 與本目錄的旅程／探針腳本；沒有改 domain、資料表、HTTP 契約或保存流程。

## 2. 官方依據與本案映射

| 依據（查閱 2026-09-14） | 官方事實與本次使用範圍 |
|---|---|
| [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) | 本次只用 Page、Runtime、DOM、Input 四個 domain。`Input.dispatchMouseEvent`／`dispatchKeyEvent` 產生的事件在頁面端 `isTrusted` 為 true，與真實輸入同一條路徑；座標是主框架 viewport 的 CSS 像素。CDP 未規定本案任何 UI 文案或驗收判準。 |
| [W3C `elementFromPoint`](https://drafts.csswg.org/cssom-view/#dom-document-elementfrompoint) | 給定 viewport 座標回傳最上層命中元素，超出 viewport 回傳 null。本案用它在按下前確認「這個點真的會打到這顆按鈕」，不是用來代替點擊。 |

driver 直接用工作區既有的 `websockets` 16.1.1（已是相依樹內套件），**沒有新增相依，也沒有引入 Playwright／Puppeteer／Selenium**。沒有宣稱業界一致採用此種驗收方式。

## 3. 環境與範圍

Windows 11 原生 DPAPI 設定檔與 host；PostgreSQL 18.6 專用 55436，每條旅程各自一個新建資料庫；Web 為 Next 16.3.5 production build（`JD_API_ORIGIN` 指向該次 API port）以 `next start` 服務於 127.0.0.1:3002；瀏覽器為本機 Chrome `--headless=new`，viewport 1264×1505。

| 旅程 | fixture／資料庫 | 模型 |
|---|---|---|
| 還原 | `jd-ui-gate-23c344cbab3f4412943c90091cb7cb08` | 完全未啟用聊天，**零模型請求** |
| 整輪撤回 | `jd-ui-gate-cdf2665358474c909700b8039e9f44d4` | 真 Agent／Saver／SQL，只有 Anthropic HTTP 傳輸換成既有 helper 的固定離線腳本；[3 次請求全部離線](jd-relational-ui-restore/undo-chat.observations.json)，`provider_network: false` |

## 4. 還原旅程的實際步驟與觀察

[逐步紀錄](jd-relational-ui-restore/browser-restore-journey.json)、[截圖](jd-relational-ui-restore/shots/)。

| 實際操作 | 觀察 |
|---|---|
| 按「建立文件」，輸入「還原與撤回驗收」，按「建立」 | 進入六章編輯畫面，狀態「已保存」。 |
| 在「職稱」打字後離開欄位 | 自動保存到第 2 版。 |
| 在「職務目的」打字後離開欄位 | 自動保存到第 3 版。 |
| 按「改動與歷史」 | 出現「還原到第 3／2／1 版」。 |
| 按「還原到第 2 版」 | 顯示「會有 1 處變動；以下逐項列出將回復與移除的內容」，並列出修改前後。此時 **JD 欄位仍是第 3 版內容**，預覽沒有寫入任何東西（頁面送出的 `/jd/edits` 仍只有 2 次，都是前面的自動保存）。 |
| 比較開著時，試著繼續編輯或送出訪談 | **做不到，而且說得出為什麼。**「職稱」「職務目的」欄位都被停用，訪談送出鍵停用，畫面寫「正在確認一次還原，暫停送出。你的輸入會保留。」——正在比較的那一版不會在腳下移動。 |
| 按「取消」 | 欄位立刻回到可編輯，暫停說明消失。（送出鍵此時仍停用，原因是訪談框是空的，與還原無關，已另記。） |
| 再按一次「還原到第 2 版」，然後按「確認還原」 | POST `/jd/edits` 回 `committed`／`changed`；畫面上「職務目的」清空、「職稱」保留，狀態回到「已保存」。 |
| 再看歷史 | 變成「還原到第 4／3／2／1 版」——還原是**新增一版**，先前版本一版都沒有消失。 |

[獨立唯讀核對](jd-relational-ui-restore/db-restore.json)（REPEATABLE READ／READ ONLY、另一條連線）：4 版、3 筆 operation 全部 committed，最後一筆 `command_kind` 為 `restore_revision`；第 4 版的 `content_digest` 與第 2 版相同但 `revision_id` 不同、parent 是第 3 版；第 3 版的 snapshot 仍保有被取代的職務目的。[writer 觀察](jd-relational-ui-restore/restore-writer.observations.json)同樣是 3 次執行。

## 5. 整輪撤回旅程的實際步驟與觀察

[逐步紀錄](jd-relational-ui-restore/browser-undo-journey.json)、[截圖](jd-relational-ui-restore/undo-shots/)。

| 實際操作 | 觀察 |
|---|---|
| 建立「整輪撤回驗收」，在訪談框輸入一段自己的工作敘述，按「送出」 | 一次真回合：AI 自己呼叫 `jd_read`、`jd_create_task` 寫入，並**引用這一輪 App 發給它的來源**，畫面出現「已保存 1 次 JD 修改」與 1 個任務、2 項成果、1 項要求。 |
| 看 JD 上的來源標記 | 「依據你說過的 1 段訪談。」，四個項目各有一顆「看第 1 段原話」。 |
| 按「看第 1 段原話」 | 對話框逐則標示角色：**員工原話一字不差**、顧問當時的回覆另標為「顧問當時的回覆」，底下明說那不是員工確認過的事實。 |
| 看「本輪 JD 改動」 | 逐項列出這輪的新增（任務／要求／成果）**與四筆「加入引用 · 「…」的依據」**，並說明「查看不會更動 JD」。 |
| 按「撤回這輪 JD 改動」 | 先出現說明：「一次取回這輪對 JD 的全部改動，不是只取消最後一項。這只會改 JD：這輪的對話、工作理解與案例都會保留，歷史也保留這輪的紀錄。」此時 JD 內容仍在。 |
| 按「確認撤回」 | POST `/jd/edits` 回 `committed`／`changed`；AI 這輪寫的項目一次消失。 |
| 回頭看訪談欄 | AI 回覆、員工原話、「已保存 1 次 JD 修改」的紀錄都還在。 |

[獨立唯讀核對](jd-relational-ui-restore/db-undo.json)：3 版（`initial`／`ai`／`manual`），2 筆 operation 為 `jd_create_task`（origin `ai`）與 `undo_ai_turn`（origin `manual`），都 committed；第 3 版重現該回合開始前的 `content_digest`，但是**新的一版**；任務數回到 0。同一個資料庫裡 conversation checkpoint 19 筆、checkpoint write 51 筆**未因撤回而減少**——只有 JD 動，對話沒有動。

## 6. 首敗、真正原因與限制

**首敗保留（同一條旅程連續失敗四次）：**按下「確認還原」後什麼都沒發生——沒有 POST、沒有錯誤訊息、預覽面板原封不動。加上點擊接收紀錄後才看清原因：事件確實以 `isTrusted` 送達頁面，但 `event.target` 是預覽上方的說明 Alert，不是按鈕。量到的按鈕座標在按下前仍有效，版面卻在量測與按下之間位移，按鍵落到位移後占住該點的元素。這是 **driver 的時序問題，不是產品缺陷**：失敗截圖裡「確認還原」清楚可見、未被遮擋，同一顆按鈕在沒有中間步驟的重現腳本裡一次就按得動。

修法在 driver：按下前等版面在兩次量測間穩定（位移 < 1px），按下後由頁面自己回報「這次點擊的目標是不是原本瞄準的元素」，不是就重新量測再試，三次都不是才失敗。這讓「員工按得到」成為被觀察到的事實，而不是假設。

來源這一段也留了兩個首敗：訪談輸入框在文件剛建立、session 還沒載完時是停用的，driver 直接打字就失敗——改成先等它可用；「看第 1 段原話」在長頁面上落在可視範圍之外，`elementFromPoint` 命不中，driver 判為被遮擋——改成按下前需要時先捲到該元素（員工也是這樣做的），只在真的不在畫面內時捲動。

其他首敗：狀態字串一開始取到聊天面板的 Chip 而不是保存狀態的 `aria-live` Chip；fetch 追蹤第一版在頁面載入後才安裝，而 `JdApi` 在首次 render 就抓走 `fetch`，因此什麼都沒錄到，改用 `Page.addScriptToEvaluateOnNewDocument` 才有紀錄；`還原到第 2 版` 之前的文件下拉選單 backdrop 仍在，會擋住下一個按鈕。

**通過範圍的限制，說清楚：**

- 只驗了這兩條旅程各一次成功路徑。**沒有**驗斷電、瀏覽器崩潰、還原確認中途的網路中斷、並行分頁、實體 IME、觸控或鍵盤操作。
- 撤回旅程的模型回覆是固定離線腳本，**不是**模型品質或判斷能力的驗收；`memory_store_rows` 為 0，本次沒有觸發 B1／B2，**不能**當作 Memory 流程的證據。
- 撤回後 `jd_source_link` 回到 0 筆，因為那一輪寫的項目連同它們的來源一起被取回；來源標記與按鈕存在的證據是旅程中段的截圖與紀錄，不是結束時的資料庫。
- 還原確認期間的暫停（設計 §4.2）已實作並在真瀏覽器驗過**還原**這一側；**撤回**那一側的暫停由同一個 `onHold` 接點提供，但沒有在真瀏覽器單獨驗過。保存時的 `stale_view` 拒絕仍是最後一道。
- 「取消後送出鍵恢復」無法由這條旅程證明：該鍵此時被空輸入這個獨立原因停用。這裡只證明欄位恢復可編輯、暫停說明消失。
- headless Chrome，不是實體視窗操作。旅程結束後[五個 helper 程序都確認退出](jd-relational-ui-restore/process-exit-check.json)，Saver 連線關閉；沒有刪資料庫或清 volume。

## 7. 下一步

真瀏覽器這一項已閉合。本稿列為後續的兩項也已完成並各自另有結果：[顧問指引與分析 Skills](../2026-09-14-jd-consultant-guidance-and-skills-slice.md)、[新 Windows 程序續作](jd-b1-adoption/r3-notification-and-background-results.md)、以及收據記錄被撤回回合（tag `jd-undo-provenance-20260914`）。其餘仍照[收尾清單](../2026-09-13-jd-app-open-issues.md)推進。
