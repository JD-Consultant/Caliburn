# JD 跨輪人工修改感知：OpenAI 官方文件與公開 Codex 實作

- 日期：2026-09-10；決策題：JD-R002／C03；G2 定向補證，不是新設計／施工核准。
- 本輪問題：應用程式在員工手改後、下一輪回應前，主動把外部狀態送入模型，是否有 OpenAI 直接證據？具體送什麼、角色、長度、差異與回讀規則，能證明到哪裡？
- 已讀 current decision register／decision process；沿用單一持續 JD、手改感知與既有 authority 邊界。只保存來源與判讀，不更新產品設計、計畫或 register。
- 查證順序：OpenAI Docs 直接 search／fetch → 既有 `.research-tmp` 定向搜尋 → GitHub 官方固定原始碼。未安裝依賴、未執行模型／測試、未改 production／DB／Memory。

## 1. 可說與不可說的結論

**Official fact：OpenAI 公開 Codex 提供 App 在跨輪間注入模型可見訊息、每輪帶入最新 IDE context 的具體機制，且有檢查實際 `/responses` 請求內容的測試原始碼。這不是僅供 UI 顯示的通知。**

**Unknown：這些證據不足以宣稱 Codex／ChatGPT 的所有封閉產品畫面，會自動偵測每一次人工編輯，並在下一輪送完整 before／after 或完整 diff。**現行官方 prompting 文件甚至提醒，使用者手動撤回或修改後應告知 Codex，避免下一輪覆寫。這是自動感知保證的限制，不能省略。

**Caliburn mapping：**「App 在模型開始下一輪工作前供給人工變更 context」可借用公開成熟的 context 注入概念；由 JD App 自動產生可靠版本／範圍通知、提供實際差異回讀，仍是本案的整合責任，不能冒稱 OpenAI 現成 JD 功能。OpenAI 此處沒有替 JD 決定通知字數、短差異全部內嵌／長差異按需讀取、基準恢復或每輪強制回讀規則。

## 2. 文件證據

下列官方文件均在 2026-09-10 由 OpenAI Docs 直接 fetch；頁面未提供本段精確發布日期。

| 來源 | 直接證明 | 限制與對 JD 的映射 |
|---|---|---|
| [Prompting：Iterate on UI with live updates](https://learn.chatgpt.com/docs/prompting#iterate-on-ui-with-live-updates) | Verification 提醒手動 revert／change edit 後告知 Codex，以免下一 prompt 覆寫。 | 不能用「大廠都會自動感知」作依據。本案主動通知是在 App 層自動化此必要供給。 |
| [Codex IDE extension](https://learn.chatgpt.com/docs/codex/ide) | 開啟檔案、選取內容可帶入 prompt；同畫面可審閱差異。 | 審閱 UI 與 context 供給是分別描述的能力；沒有宣告跨輪全檔案修改偵測／完整 before-after。 |
| [Codex App Server](https://learn.chatgpt.com/docs/app-server) | `thread/inject_items` 把原始 Responses items 加入 model-visible history，不啟動 user turn；`turn/start` 開始下一輪。文件另外定義 `turn/diff/updated` 聚合差異事件與 `fs/changed` 檔案事件。 | 後兩項是 app-server 通知；單憑事件存在不能推定差異已進模型輸入。 |
| [Use ChatGPT：What ChatGPT Work can do](https://learn.chatgpt.com/docs/use-chatgpt#what-chatgpt-work-can-do) | 可讀檔、建立與修訂文件並供使用者審閱。 | 沒有公開人工修改通知的內部角色、完整內容、token 上限與每輪差異規則；此處維持 unknown。 |

## 3. 固定公開原始碼與測試

版本：[openai/codex `c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68`](https://github.com/openai/codex/commit/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68)，本輪 GitHub API 查到的 `main` HEAD，committer time `2026-09-09T19:22:22Z`。這是來源快照，不宣稱已安裝 app／CLI 與這個 commit 相同。

| 問題 | 固定來源與行號 | 原始碼直接呈現 | 不能外推 |
|---|---|---|---|
| 跨輪注入真的會給模型？ | [thread_inject_items.rs L512–641](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/app-server/tests/suite/v2/thread_inject_items.rs#L512-L641) | 第一輪完成後，建立 `role: developer` 的訊息，呼叫 `thread/inject_items`，開始第二輪；L622–638 斷言第一個模型 request 沒有該 item、第二個有。 | 測試內容是一般 injected text，不是文件變更。此輪只讀測試原始碼，未重跑。 |
| 直接每輪帶 App context？ | [turn.rs L177–180](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/app-server-protocol/src/protocol/v2/turn.rs#L177-L180)、[turn_start.rs L564–626](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/app-server/tests/suite/v2/turn_start.rs#L564-L626) | `turn/start.additionalContext` 是 **experimental** client-provided fragments；測試送 custom source，讀取實際 `/responses` request body，確認標記包裹的 context 在內。 | 不能當穩定通用 API 或封閉 App 特定用途的證明。 |
| role／內容怎麼分？ | [additional_context.rs L15–33](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/core/src/state/additional_context.rs#L15-L33)、[fragments L22–101](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/context-fragments/src/additional_context.rs#L22-L101) | `Application` 變成 developer role、`<key>value</key>`；`Untrusted` 變成 user role、`<external_key>value</external_key>`。相同 key/value/kind 不重送；變動才形成 fragment。 | user role 不代表真人逐字輸入；這裡有明確來源分類／包裝。不是說 JD 必須採此字串格式或把員工原話提升成 developer 指令。 |
| 大小限制？ | [fragments L6](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/context-fragments/src/additional_context.rs#L6)、[L94–101](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/context-fragments/src/additional_context.rs#L94-L101)、[truncate.rs L4–28](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/utils/string/src/truncate.rs#L4-L28) | 此 additional-context value 使用 1,000 **估算** token 預算，4 bytes/token 近似值，保留頭尾、截中段。 | 不是模型 tokenizer 的 1,000 精確 token，也不是所有 Codex context／手改通知上限；截斷不等於自動摘要或可完整恢復 diff。 |
| 最新 IDE 內容何時取得？ | [chatwidget/ide_context.rs L66–94](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/tui/src/chatwidget/ide_context.rs#L66-L94) | 啟用 `/ide` 後，outgoing user turn 取得 fresh IDE context，並折入 prompt；失敗會提示本訊息略過 IDE context。 | 這是 TUI 接 IDE 的公開程式，不是全產品自動手改通知；不含上輪基準與變更前內容。 |
| IDE prompt 送多少、什麼？ | [prompt.rs L8–58](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/tui/src/ide_context/prompt.rs#L8-L58)、[L95–188](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/tui/src/ide_context/prompt.rs#L95-L188)、[tests L249–305、L361–402](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/tui/src/ide_context/prompt.rs#L249-L402) | 在 user text 前加 IDE context，用 `## My request for Codex:` 分隔真人 request。包含 active path、selection content／ranges、open-tab paths。selection 最多 40,000 字元；tab 最多 100 筆且該清單以 `.len()` 限 20,000 UTF-8 bytes，略過／截斷有標記。 | open tabs 是路徑清單，不是每個檔案全文；不計算人工 diff 或 before-after。原始碼常數名稱雖用 CHARS，tab 實際 `.len()` 是 bytes。 |
| 檔案變更事件就是模型通知？ | [fs_watch.rs L82–144](https://github.com/openai/codex/blob/c1840dc55e3cbb7ef27ccc1fb20b38cdd0e9ef68/codex-rs/app-server/src/fs_watch.rs#L82-L144) | watcher 收集並排序 changed paths，以 `send_server_notification_to_connection_and_wait` 傳 `FsChanged` 給 client；payload 為 watch ID／changed paths。 | 此函式沒有內容 diff、before-after，也沒有把事件加入模型 history；不能把 client event 當模型已知的證據。 |

## 4. 尚未由這些證據決定的事項

1. OpenAI 封閉 ChatGPT／Codex UI 是否針對特定人工編輯動作，自動組裝何種變更通知；本輪不可推知。
2. 任意文件自上次模型讀取以來的完整人工 diff、短長分流、revision 配對與強制回讀；以上公開片段沒有共同保證。
3. 注入內容存在於模型 request，只證明「提供了模型可見資訊」，不保證模型理解正確，也不能取代 App 寫入時的版本驗證。

本輪已足以停止 OpenAI 廣泛搜尋：成熟接點存在與全產品自動感知保證缺失已分清。JD 所需的自動生成通知、版本基準與可回讀差異，應由本案既有接線設計／有限驗收完成，不再把 UI 事件或一般文件編輯能力當成證據替代。

## 5. 來源留存與執行界線

GitHub HEAD／tree metadata、官方原始碼 archive 與定向解出檔案位於 `.research-tmp/jd-context-openai/`。archive 解包曾因另指定的舊路徑不存在返回非零；本表引用的每個現有檔案都已另行直接讀取，未把該解包結果稱成測試通過。

本輪沒有執行 Codex 測試或模型；測試結論一律指「官方測試原始碼斷言什麼」。沒有以 grep 未找到來宣稱全 repository／封閉產品不存在該能力。
