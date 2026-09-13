# 同頁聊天草稿與原請求交接前置

日期：2026-09-13。JD-R002／RS-4；責任是本輪 Web 交接的有界研究，並非實作結果。依[目前決策](../../../current-decisions.md)、[施工計畫](../../../plans/2026-09-13-jd-relational-app-implementation.md)及[已完成聊天 HTTP 契約](../../2026-09-13-jd-chat-http-slice.md)。本輪只讀源碼、既有證據及相關官方文件；沒有改程式、開 DB、啟動服務或呼叫模型。

## 1. 推薦與範圍

**同一文件沿用一個 `JdSession`／原 Web Lock owner，在原 IndexedDB 草稿列增設聊天候選及原請求。** 聊天框可在 AI 執行時繼續輸入；送出新回合、JD 手改及原回合恢復仍由共用 controller 按 App 真實狀態決定。聊天草稿不是原始訪談權威，只有 App 原生保存確認的 HumanMessage 才是已提交原話。

本案接點是已有能力的延伸：idb 管短交易，Web Locks 管同 origin 的文件 owner，生成契約管 HTTP，現有 App 管原回合、SQL、准入和停止證據。以下 row 欄位、序號、介面及門檻是本案取捨，不稱為 OpenAI、Anthropic 或所有大廠共同 schema；兩家 LLM 工具與完整原話責任沿[已核契約](../jd-relational-ai-restart/chat-contract-preflight.md)，本輪不重新廣搜。

不採另外建立 `ChatSession` 再取得同名鎖：原 controller 已在整個文件使用期間持鎖，第二個 owner 會互相阻擋；換另一個 lock name 又失去人工／AI 共用文件交接。也不把聊天放進 `forms.chat`：現有 `resume(discard)` 會處理全部 forms，`dirty`／`review` 也包含全部 forms，可能把未送原話當成可捨棄的 JD 表單。

## 2. 本輪核對的官方能力

查閱日期均為 2026-09-13。未安裝或升級依賴；版本以本 app lock／已安裝套件為準。

| 依據 | 適用版本／穩定與授權 | 官方事實與本案界線 |
|---|---|---|
| Next bundled `use-client`、`server-and-client-boundary`、`use-router` | Next 16.3.5，現有穩定鎖版，MIT | Client Component 仍可能先在 server render；browser API 的取得／草稿打開應在 client lifecycle 或事件，不能只加 directive 就在 render 直接開 IndexedDB。`router.refresh()` 保留未受影響 React state 不等於關頁重開的持久保存。[官方入口](https://nextjs.org/docs/app/api-reference/directives/use-client)；本輪精確版本讀下列 bundled 路徑。 |
| [React `useEffect`](https://react.dev/reference/react/useEffect) | React 19.3.0，現有穩定鎖版，MIT；官方現行文件 | cleanup 在卸載／依賴變更時執行；開發 Strict Mode 額外驗 setup／cleanup。建立及釋放 owner 可用 lifecycle；送出原話是明確事件，不因 mount／重播 effect 自動 POST。舊 controller 的延遲通知不能更新新文件。 |
| [idb 官方 README](https://github.com/jakearchibald/idb/tree/v8.0.3#readme) | idb 8.0.3，穩定、ISC；亦讀本機同版 README | `tx.done` 成功代表該 IndexedDB transaction 完成；不可在 transaction 中等待 fetch。`upgrade` 提供 oldVersion；`blocking`／`blocked`／`terminated` 是原生生命週期的薄介面。不是一般網路重試或資料同步引擎。 |
| [Web Locks `request`](https://developer.mozilla.org/en-US/docs/Web/API/LockManager/request) | 瀏覽器原生穩定 API，非 npm 授權套件；實際環境須支援 | exclusive callback 的 Promise 結束才釋鎖；`ifAvailable` 失敗回 null，`steal` 不會停止舊程式。沿原同文件鎖、不可 steal；缺此能力停寫。鎖不跨 origin，也不證明後端 Future／模型停止。 |
| [IndexedDB 升級事件](https://developer.mozilla.org/en-US/docs/Web/API/IDBOpenDBRequest/upgradeneeded_event)、[既有草稿官方核對](../2026-09-13-jd-browser-draft-preflight.md) | 原生穩定 API；套件授權不適用 | 更高 DB version 觸發升級；版本變更及舊 connection 協調須明示處理。`durability: strict` 沿既有設定，但不宣稱瀏覽器儲存永不被使用者清除／配額驅逐或可承受任意斷電。 |
| [KeyboardEvent `isComposing`](https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/isComposing)、既有 InputEvent／beforeunload 證據 | 原生 UI Events；MDN 對 KeyboardEvent 相容性有保留，不能用合成測試聲稱所有輸入法相容 | 判斷組字階段；聊天與 JD 各自保留 composition state，結束事件先接住最終 value。`beforeunload` 只提示可能未完成，不能等關頁時才第一次保存。實體繁中 IME 另驗。 |

本機文件為 `experiments/jd-relational-app/web/node_modules/next/dist/docs/01-app/03-api-reference/01-directives/use-client.md`、`01-app/02-guides/server-and-client-boundary.md`、`01-app/03-api-reference/04-functions/use-router.md`；已先讀同 Web 的 `AGENTS.md`。未導入 query library 或另一套同步框架：此單位尚無 cache／重試功能缺口足以支持新增依賴；原權威仍為 App 的只讀狀態及原請求 API。

## 3. 現況中不能直接沿用的部分

| 現有接點 | 已讀到的限制 | 本輪應補的行為 |
|---|---|---|
| `drafts.ts` 的 format 1 row | 只接受 manual request；exact keys 不容任意加欄位 | 明示 format 2，保留原 manual 結構與原 request。 |
| `JdSession.flush(): Promise<void>` | composing、review、write blocked 等情況會直接返回；也不提交 `forms.editor` | 不能把 `await flush()` 成功返回當作聊天准入。送出前另核實完整條件。 |
| `SessionSnapshot.readOnly` | 同時包含 server write blocked／manual review | 只用來管 JD 及需要寫 App 的操作；聊天草稿是否可輸入改看本地 owner／storage，AI 執行不禁止記下一段。 |
| `reconcile(retry=true)` | manual not_found 時可重送原 manual request | 不直接複用為聊天恢復；聊天重新打開先 GET 原 run，不自動 POST 或換 run。 |
| `refreshStatus`／`resume(discard)`／dirty | 全 forms 都算人工候選、可被人工捨棄 | JD 人工候選與聊天候選分別處理；人工捨棄不可清除 chat draft／chat submission。 |
| `dispose` 的 Web Lock callback | 目前只排空原 manual flight 和 local queue | 納入新的本地聊天寫入及有限 HTTP 等待。取消 UI 等待不代表停止後端；不為等待 AI 全輪終止而永久占用瀏覽器退出。 |

這些是源碼核對，尚未在此文件執行紅／綠測試。實作者應保留具體反例，而不是只調整型別使程式可編譯。

## 4. 最少持久欄位與 native 版本演進

推薦仍以 `[apiOrigin, datasetId, documentId]` 作原 `drafts` store key；同一 row 共用 `draftId`、`ownerEpoch`、`generation`、`inputSeq`。不新增另一個 owner、run status 表或聊天訊息副本。

| 新增內容（名稱可由實作者定） | 必要資料 | 保證／不是什麼 |
|---|---|---|
| `chatDraft` | `text`、單調 `seq` | 保存尚未交付的原文，允許空白及換行；送出前才驗非空／契約 byte 上限。不是 Memory，也不標成 server 已保存。 |
| `chatSubmission` 或 null | 原生成 `ChatStartInput` 完整物件；`submissionGeneration`；所涵蓋 `chatSeq` | 原 run_id、text、expected_jd_revision_ref 固定不變。候選後續輸入不得覆寫它；回覆來時核 owner、run、generation、涵蓋序號。 |
| 可選 `lastRunId` 或 null | 同範圍 canonical UUID | 只做已結束回合的 UI 定位提示；重新讀 App 才知狀態，不能據此認定 running／terminal／可寫。不是必要的第二份結果快取。 |

原 scope 在 row；request 不重複增加 dataset、document 或 body digest，原 HTTP header／path 仍由可信 client 組合。request 由生成驗證器檢查；不 decode opaque ref，不由 Web 重算 backend digest 或工具身分。候選上限、原 request byte 上限與現有整 row 4 MiB 界線要各別檢查，不靜默截字或 trim 原文。字數檢查可用 trim 判空，保存的 text 必須仍是原字串。

**推薦 IndexedDB version 1 → 2，但不搬 store、不清舊列。** 理由是協調舊頁，不是 JSON 欄位必然需要 object-store schema 變更：

1. `upgrade` 改成只有 `oldVersion < 1` 才建立原 `drafts`／index／`creations`。單純把 open version 改成 2 而仍無條件 create 會碰既有 store。
2. 原 v1 列先完整保留在既有 store。新程式的兼容 reader 可嚴格辨識 v1／v2；只有取得原文件鎖後的 claim，在同一短 readwrite transaction 將合法 v1 補空 chat 欄位為 v2，並更新原 owner。保留全部 fields、forms、inputSeq、draftId、manual submission 及其原 operation／coverage／generation。
3. 未使用的文件、其他 dataset 草稿和 `creations` 不批次重寫；單列不合法或未知較新 format 則保留並停該列寫入。不能解讀失敗就造空 row，也不能清 DB 重新開始。
4. 已開的舊連線收到 versionchange，沿現有 `blocking` 關閉 DB 並停用編輯／提示重開。未關舊頁而仍占原 Web Lock 時，新頁應明確等待或只讀；不能偷鎖。v2 成功後舊 bundle 再 open version 1 應失敗，不得降級開庫。
5. 升級 blocked／交易失敗維持原資料；不新增清除或 auto-reset 出口。開庫及 claim 若分段故障，下次仍以原 record 驗證恢復，不用局部記憶猜已遷移。

不採新增 chat store，是因為會增加跨 store owner／claim／ACK 交易的必要範圍，對本案單文件候選沒有較小的效果。這不是否定 IndexedDB 多 store，而是此單位已有可靠的一列 owner 與合併規則可使用。

## 5. 原話送出、後續輸入與查回

送出由使用者事件啟動，同一 owner 內按以下順序：

1. 先阻擋新的 JD 編輯進入交接窗；若 JD 或聊天仍組字，拒送並保留內容，不自動排程組字結束後送。聊天 final value 先交給 controller；不以 blur、固定 sleep 或鍵碼推定 IME 已完成。
2. 等本地 queue 排空，flush 已編輯 JD，核其真結果。確認沒有 RAM JD 候選、持久 fields、manual submission、manual review 或未完成 editor form；文件尚未封存且 App 可寫。不符合就保留聊天，說明需先處理哪件事。`flight`／交接實作不能互相等待自己。
3. 取得保存後的 JD projection／revision ref，再核未有本地變更插入。client 無法把 GET 與 POST 變成一個 server transaction；起始 JD 版次的最終判斷仍交現有 App 原子准入。stale 時不能偷偷替換已固定 request 的 ref。
4. 固定一次 `run_id`、原 text 及 ref。在短 IndexedDB transaction 以原 owner 和 seq 建立 chat submission，等 put 與 `tx.done` 成功後，才 POST 該完整原 request。先寫持久記錄、再送 network；中間不持 IDB transaction。
5. 可在這個提交交易內把已涵蓋的聊天輸入移到原 request，將 composer 留空供下一段 B；A 的完整原文仍持久保留在 submission，畫面顯示為送出待確認。若實作選擇留 A 在輸入框到 ACK，則 ACK 也只能清仍相同 seq 的 A，不能清之後的 B。兩者都不得在原 request 尚未持久時清原文。
6. A 執行期間 B 的 onChange 繼續進同 local queue；B 只本地保存，不能自動成為第二回合。原 A GET／cancel／recover 回應只能更新 A，不能覆蓋 B。手改 JD 暫停；是否放行由 App write state 決定，不用動畫是否停止推定。

回覆處理分清原話與執行：

| 真實回應 | 本地應做什麼 |
|---|---|
| `input_state=saved`，run 仍 running／closing／recovery_required | 可以把 A 顯示為已記錄的原話；原 request／run 仍保留供續查，不解除活動回合限制。 |
| terminal、effects settled | 可依 exact owner／run／generation 收掉 A 的 active submission，保留 B；重新讀 JD／狀態及歷史。terminal 不等於目前 document 必定可寫，也不等於 JD 已專業完整。 |
| `input_state=not_saved` | 這是 App 已證原話未保存的特定原 attempt；保留 A 可供明確處理，不覆蓋 B，不自動換 key 重送。 |
| transport 失敗、202、not_found／unconfirmed、lookup gap 或 malformed response | 保留 exact A；以原 run GET／原控制介面核實。不偽造 failed／completed，不把查無當作允許新 run。 |

關頁／重開後，claim 原 row，優先 GET 原 chat submission 的 run_id；不從 composer 重新產生請求，也不因 effect 再 POST。POST 回覆成功但 browser ACK 失敗同樣查原 run。原資料的 ACK 在短交易重新讀最新 row，只處理 exact A，不能把發送前整列覆寫回來。

有一個必須誠實呈現的空窗：已保存 A、尚未實際送出 POST 就關頁，與已送出但查回暫時無證據，瀏覽器不能只憑旗標區分。第一版可提供明示「查回」及「繼續原請求」；後者若採用，只能 POST 同 A、由既有後端判重／版次准入，不可自動觸發或造新 run。原輪已 terminal 的再次訪談，是使用者另一次明確送出，不是恢復程式暗中重新執行。

## 6. 沒有本地 pending 時定位原回合

目前 history 初頁最多 50 則，從固定快照的最早公開訊息開始。新瀏覽器沒有原 run_id 時，若只依最後一則可見訊息，會漏掉 50 則以後的活動回合，或沒有公開 assistant 文字的進行中回合。現有 manual state 也不提供 AI run_id。

推薦在同一生成 `ChatHistoryPage` 加 **`anchor_run_id`**：取該次已驗證 `observed.record.run_id`；空 history 為 null。它是既有 native record 的最小投影，不新建 endpoint／表，也不由 Web 從 anchor token decode。續頁須保留同一固定 root／source、anchor、anchor_run_id；不能續到一半取 latest 的 run。

初頁可直接以這個 ID 呼叫原 run GET；它表示該固定快照所屬回合，**不保證查詢後世界不再前進**。查原 A 得知目前 document 被其他工作阻擋時，不把 A 改標為那份工作的執行。local pending A 的查回責任不因頁面已有較新的 B 就消失；先保存／完成對 A 的原結果處理。需要重新發現目前原生位置時，重新讀初頁即可，無需每次掃到聊天最後一頁。

這不能解決舊 run locator 的 256 祖先界線或缺鏈；遇原結果查回限制仍應保留候選並明確提示，不借公開訊息分頁猜原回執。anchor_run_id 的欄位與生成改動由主代理另行裁決／實作，本文件沒有改 schema。

## 7. UI 與生命週期的有限規則

- 分開顯示「JD 已保存」「訊息暫存於此瀏覽器」「原話已記錄／回合處理中」。不能因聊天有未送文字把 JD 說成未保存，也不能把 idb 成功說成對話已入 App。
- 同 controller 釋放 Web Lock 前，排空本地 queue 和已開始的有限 HTTP 等待；卸載停止 polling timer、抑制舊通知。不能把 client abort 或 tab 關閉當成 AI 停止證據；若等待逾時，保留原請求，後來 owner 只查回。
- storage/versionchange 故障立即停新的保存／送出，保留畫面 RAM 及既有 record；不因顯示讀取成功就忽略寫入失敗。已持久的候選可在同 origin 重開恢復，但瀏覽器清除資料／驅逐及 API/UI origin 改變不在這個承諾內。
- React mount／Strict Mode、文件切換、重開只做讀取／owner 接合，不執行新 run。IDB、原文和 bearer 類 refs 不經 Server Component props 或診斷日志另送；App 支援的 Origin／dataset 邊界繼續由原 API 驗證。
- 暫不做聊天自動排隊、多個並行 run、跨分頁搶鎖或通用重試引擎。輸入框在 AI 執行時能寫，與能立即送出第二輪是不同能力。

## 8. 必要反例與真正產品取捨

下一實作至少應驗下列有限反例；本輪文件沒有把它們標成已通過：

| 情境 | 必須成立 |
|---|---|
| v1 有人工 fields、未完成 form、unknown manual submission，升 v2 並重開 | 原值、原 request／operation／coverage 完整；chat 初值空，不清原人工草稿。 |
| 舊頁占 connection／同文件 Web Lock，新頁升級；未知 format／corrupt row | 舊頁停寫，新頁不偷鎖；拒絕並保留資料，不造空白副本。 |
| JD 組字中／chat 組字確認 Enter／flush 無事返回 | 不送半句或以舊 ref 開 AI；最終文字仍保存。需另實體 IME 證據。 |
| JD 慢保存成功／unknown／保存途中又有本地輸入 | 只在本地候選排空和真成功後交接；unknown 不送 chat。 |
| A 持久後、POST 前關頁；POST 成功回覆遺失；browser ACK 失敗 | 重開先 GET 同 run；原文、ref、ID 不變，沒有自動新 POST／新 run。 |
| A 執行，員工輸入 B；A 晚 ACK；owner 換頁後舊 callback 回來 | B 保留，過期 owner／generation 拒寫，原 A 不覆蓋新 row。 |
| 另一文件／dataset 的候選與回覆、封存、模型未啟用 | 不跨範圍套用、不偷偷送 provider；文字仍可保留供處理。 |
| 超過 50 則、末輪尚無公開回覆、child 繼續前進 | 初頁 anchor_run_id 可直接查原 run；續頁快照一致，不靠掃頁／token decode。 |
| terminal A 後 JD 已被其他工作更新；AI failed 但有 committed JD | 原結果呈現精確；fresh JD 另讀，不把 AI 回答摘要當修改證據。 |

已確認的「AI 執行時 JD 手改暫停、下一段聊天可打、不自動新回合」不需再問。真正剩餘 UX 選項僅：未完成結構表單是否允许交給 AI 後再重接，以及查無原 run 時是否在首版提供明示同請求重送。推薦首版前者先阻擋送出、保留聊天並請先完成或明確取消該表單；後者若提供就清楚標成原請求繼續，不能和新訊息送出混用。這些可由主代理依已授權的最小完整旅程定案；若改成自动提交／清除表單或自動送下一輪，才是新的產品語意，不能偷偷加入。

此單位研究已足以開始有界實作；剩餘由上述反例回答，不再廣搜框架或重做資料庫設計。
