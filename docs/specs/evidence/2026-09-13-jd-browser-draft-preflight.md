# JD 瀏覽器候選與原請求恢復：DA03 有界查核

查閱：2026-09-13。狀態：採用方向；本文件不代表真瀏覽器、斷電或真人驗收已通過。

責任路由：[自動保存](../2026-09-12-jd-autosave-and-handoff-design.md)、[歷史與恢復](../2026-09-12-jd-history-and-recovery-design.md)、[受管理設定](../2026-09-13-jd-managed-configuration-slice.md)。原請求／結果沿 [Manual HTTP schema](../../../experiments/jd-relational-app/contracts/jd-manual-http.schema.json) 與 [結果 schema](../../../experiments/jd-relational-app/contracts/jd-result.schema.json)，瀏覽器不得另定一份業務命令格式。

## 1. 決定及適用界線

採 **IndexedDB + idb 8.0.3** 保存每份文件的一筆本機候選，原生 **Web Locks** 限制同一瀏覽器來源內同文件只有一頁可手動寫入。PostgreSQL 仍是已保存 JD 的唯一權威。IndexedDB 保存未完成輸入、原保存請求及其涵蓋範圍，不是離線可獨立寫入的第二套 JD。

不另造資料庫 wrapper、背景同步佇列、TTL 鎖或通用合併引擎。`drafts.ts` 只做本案有限候選的短交易更新。每次保存仍走既有具名業務命令；沒有任意 JSON patch 或通用 batch。

### 官方事實與候選比較

| 依據 | 已確認能力與限制 | 本案採用 |
|---|---|---|
| [MDN IndexedDB 使用](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Using_IndexedDB)、[交易](https://developer.mozilla.org/en-US/docs/Web/API/IDBTransaction) | 原生非同步交易；單一 request 成功不等於 transaction 完成；交易在沒有待辦 request 時會自動結束。瀏覽器关闭不可靠地保證最後工作完成。 | `get → 身分核對 → 局部 merge → put → tx.done`；沒有網路等待跨交易。 |
| [idb 官方](https://github.com/jakearchibald/idb)、[8.0.3 原碼](https://raw.githubusercontent.com/jakearchibald/idb/v8.0.3/src/entry.ts)、[套件宣告](https://raw.githubusercontent.com/jakearchibald/idb/main/package.json) | 8.0.3 tag 可讀，ISC；薄 promise/TypeScript 封裝，提供 `tx.done`、`blocked`／`blocking`／`terminated`。官方直接提醒不要在 IndexedDB transaction 內 await fetch。此次不以 GitHub main 推稱 npm 最新發布日。 | 採固定 8.0.3，安裝結果及 lock 由 Web 切片核實。 |
| [Dexie transaction](https://dexie.org/docs/Dexie/Dexie.transaction())、[套件宣告](https://raw.githubusercontent.com/dexie/Dexie.js/master/package.json) | 免費開源核心 Apache-2.0；repo 宣告 4.4.6，未在本次驗其 npm 穩定發布。提供更高階表操作，但不能免除原生 transaction lifetime 限制。 | 第二候選；一筆候選不需要額外查詢／反應式資料層，未採、未安裝；未混入 Cloud 能力。 |
| [Web Locks](https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API)、[request](https://developer.mozilla.org/en-US/docs/Web/API/LockManager/request) | 同來源 context 間排他，鎖持有至 callback promise 結束。`ifAvailable` 可立即得知未取得；不能與 `signal` 併用。`steal` 不會讓原程式自動停止。 | `{mode:'exclusive', ifAvailable:true}`，無 steal；第二頁只看，待第一頁釋放才可再取得。 |
| [Storage 配額與清除](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)、[transaction durability](https://developer.mozilla.org/en-US/docs/Web/API/IDBDatabase/transaction) | 配額、瀏覽器清除、best-effort eviction 會影響本機資料；標準 `durability` 是提示，不能把普通 transaction complete 當每個字元已物理落盤的證明。 | 原請求／ACK 交易採原生 strict durability 提示，實際目標瀏覽器再驗；不採非標準 `readwriteflush`。不宣稱替代資料庫備份。 |
| [InputEvent.isComposing](https://developer.mozilla.org/en-US/docs/Web/API/InputEvent/isComposing)、[beforeunload](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event) | IME 組字期間有標誌；beforeunload 不是可靠保存機制。 | 組字期間不發出文字保存或 Enter 送出；compositionend 後才啟用保存排程。離頁提示只保護已有候選，不代替先行持久化。 |

共同原則是以原生交易保護一筆更新、以持有鎖的生命週期限制寫入、區分網路結果未知與確定保存。以下 record、大小、命名及 UI 提示是依本案 HTTP 契約做的映射，不能稱作上述廠商通用標準。

## 2. 單筆格式與擁有者

`format: 1` 的 row 以 `[apiOrigin,datasetId,documentId]` 為 key；不以標題、目前頁面或時間推斷文件。

| 欄位 | 意義 |
|---|---|
| scope | 精確 API origin、資料集 UUID、文件 UUID；資料集由列表 GET 取得，不由草稿猜。 |
| draftId、ownerEpoch | 候選建立身分與這次成功取得 Web Lock 的擁有者身分。接管保留原候選與原請求，只更新 ownerEpoch。 |
| generation、inputSeq | row 每次成功更新的版本；UI 每次輸入的單調序號。不同欄位分開比對 seq，不能以全域最大 seq 丟掉另一欄較早的輸入。 |
| fields | key 是 `JSON.stringify([itemId|null, fieldName])`；值含原 fieldRef、baseValue、目前 text、seq。App 使用讀取投影給的身分與欄位名，不解析 ref。 |
| forms | 新增任務等尚未符合提交契約的完整 plain JSON 表單值與 seq；保存所有輸入，不只保存某個文字框。 |
| submission | 完整原 `ManualSaveInput`、固定 submissionGeneration、`coveredFields`／`coveredForms` 的逐 key seq。base revision 已在原請求中；原命令內容、operation_id 及 base 不可改寫。 |

原保存請求沿 HTTP 1 MiB 上限；候選整筆以 4 MiB 有界檢查作本案初始防護，不自動淘汰舊候選。大小超過或 IDB 寫入失敗時保留記憶體輸入、停止發出新寫入並清楚顯示仍未保存。表單本機格式只准有限深度 plain JSON；正式 domain 限制由共用服務檢查。

呼叫 draft store 前，UI 已持有對應 Web Lock。store 並不以一個 boolean 宣稱持有原生鎖；每次更新仍核對原 `draftId + ownerEpoch`，使舊頁未完成的 callback 在新頁接管後不能改寫新 row。generation 分開核 submission 身分，避免晚輸入 B 合法增加 row generation 後，A 的 ACK 全被錯誤拒絕。

Web Lock 的同來源限制不跨其他瀏覽器、profile 或另一前端 origin。後端 base revision、operation 和 writer gate 仍須處理這些情形。loopback 的 [secure context 適用條件](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts) 與實際瀏覽器能力須在啟用編輯前核實；缺少 Web Locks／IndexedDB 時不偷偷改用 localStorage 租約。

## 3. 保存順序與晚回覆

1. UI 先更新畫面及 seq，完整 IME 輸入才排保存；`persistField`／`persistForm` 以短交易局部更新，只修改該 key，不清 submission。
2. 選定一次具名命令後，`prepareSubmission` 核候選涵蓋 seq，持久保存原 `ManualSaveInput` 與逐 key 涵蓋表；等 transaction 完成才 fetch。最多一筆未確認 submission。
3. 網路中斷、取消 fetch、HTTP Problem 或未確認結果不改寫原請求、不清候選。HTTP 失敗不是原業務已回滾的證據。
4. 原 operation 有 confirmed receipt 後，ACK 在交易內重新讀取最新 row。只清這次 `coveredFields`／`coveredForms` 中 seq 沒超過涵蓋值的候選。A 只送一欄，不能清掉別欄更早的尚未送資料。
5. 同欄 A 送出後又輸入 B，保留 B；原 A 確認後可把 A.text 作該欄新的 baseValue，但不能猜新 fieldRef。UI 讀取目前版，確認其 revision 與結果、目前欄位身分後，才換成新 ref。若目前已是其他 C，保留 B 並呈現 C，不將整頁退回 A。
6. confirmed 拒絕仍保留輸入，停止原排程、依既有 next_action 更正；unconfirmed 不解除原 submission。原結果是唯讀查回得到，也遵守相同步驟。

ACK 使用 `operationId + submissionGeneration` 及 owner handle 核原送出，不拿 prepare 當下的 row generation 要求現在仍一樣。沒有任意重播所有歷史輸入或通用 rebase。

## 4. 重開及環境變更

重開先取得 Web Lock、從 server 列表得知 dataset，再 claim 同 scope 的 row。原 `ManualSaveInput` 必須通過與 HTTP 相同的生成 schema 驗證。不能以同名文件套用舊候選；不同 dataset 的候選只保留查看，不自動送往還原後資料集。

| 查回情形 | 行為 |
|---|---|
| observed／confirmed | 核同 operation；按上述 ACK 保留晚輸入；重讀目前完整內容及 write state，再決定是否可送下一筆。 |
| pending／unconfirmed | 保留原請求，使用既有 recovery 接點作有界查回；不以 AbortController 當後端取消證明。 |
| not_found | **不證明原 request 未送出／延遲 request 不會到達**。保留原 key/body，不自動產生新 key；重讀／人工明示同原請求再確認的 UI 出口由本切片核實，不自動背景重播。 |
| dataset_changed、格式不支援、owner 已被接管 | 保留候選，停止舊頁寫入；不清 DB、不無條件覆寫、不借新身分繞過檢查。 |

GET state 只是觀察，不能作離開 server gate 的寫入許可。unsafe HTTP `X-JD-Dataset` 由 App 填入原 scope，不能讓 LLM 或候選表單自填。

schema upgrade 以 IDB 原生 versionchange；`blocking` 關閉舊連線、UI 停止寫入並提示重開。`blocked` 不刪資料庫解卡。頁面離開／bfcache 回來須重新確認 lock/controller/dataset；不可繼續執行上一生命週期的排程。這部分及 quota／私密模式須用真瀏覽器驗，不以 Node 模擬當證明。

## 5. 有限驗收與停止研究條件

單元驗證：原請求先持久；A 回覆時 B 保留；A 一欄不清另欄；完整新增任務表單保留；舊 owner／舊 operation／舊 submission generation 被拒；無 confirmed receipt 不清；同 operation 不可換 payload；不合法 local format、HTTP body、非 JSON、超限拒絕且原 row 保留。

真瀏覽器：兩頁同文件排他／不同文件可寫；IndexedDB tx 完成後重開可讀；A 已保存但回覆遺失；重開原請求不自動重播；IME 繁中 composition、晚回覆、bfcache、schema blocking／異常終止及儲存失敗。真後端另核 dataset 還原、busy／cancel／server restart。未操作不能標通過。

本次官方能力已足以施工，停止廣搜。尚未證明的是具體瀏覽器事件順序、重開及配額失敗體驗，交有限實測；不是新增泛用 queue 或另一套業務狀態機的理由。

## 6. 有界實作交接與實際證據

已落 [drafts.ts](../../../experiments/jd-relational-app/web/src/lib/drafts.ts) 與 [純 transition 測試](../../../experiments/jd-relational-app/web/tests/drafts.test.ts)。`openDraftStore` 回傳 `DraftStore`；`claim → draftHandle → persistField/persistForm → prepareSubmission → acknowledgeSubmission`。明確 reread 後用 `rebindField` 換 ref；直接丟棄候選要有原 key/seq，且不得有未知 submission。空 row 保留 owner fence；不保留已確認原命令作另一套歷史。

同 IDB version 1 另有 `creations` store，key 為 `JSON.stringify([origin,datasetId])`；只保存生成契約 `CatalogCreateInput`。`readCreation/storeCreation/clearCreation` 三個有限操作，在 UI 持有原生 catalog lock 下使用；已有原請求時只允許同 key、同 title、同 dataset，清除必須仍是原 key。這是建立文件的原請求恢復，不是另一種保存引擎或 localStorage 副本。

首個測試入口遇 sandbox 子程序 `EPERM`，改 Node 原生 `--test-isolation=none` 後確實首敗 `ERR_MODULE_NOT_FOUND`。初版完成 16 項正反例；再加「C 晚輸入不得把 A 確認後的基準改回」與「重開 coverage 不可指向別欄或不存在候選」兩例，確實先 **2 FAIL**，修正後 **18 PASS**（2026-09-13，約 0.26 秒）。手改只更新當前 text/seq；fieldRef/baseValue 的前進限 ACK／明確 reread 接點。

這些是純函式與真生成 schema 驗證，未使用 fake IndexedDB，**不證明原生 IDB/Web Locks/瀏覽器重開**。全 Web TypeScript 檢查此時尚有其他代理施工中檔案的接線錯誤，不能標成整體通過；本檔／測試當時沒有殘留型別錯誤。原生瀏覽器證據交主切片續做。
