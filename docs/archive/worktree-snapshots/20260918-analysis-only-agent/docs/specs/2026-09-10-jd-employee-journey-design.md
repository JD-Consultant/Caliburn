# JD 員工完整旅程與結構可讀設計

2026-09-10；Topic `JD-R002/C03`，對應[成品總計畫 R2／R3](../plans/2026-09-10-jd-product-delivery.md)。本稿是有限 G4 設計及 Task 4／5 增補交接，尚未實作或通過 DOM／API 驗收；由主線 review 並寫回 register 後成為施工路由。production 仍依 ADR 0060；本稿不使 ADR 0073 自動 Accepted。

## 1. Preflight、既有決策與唯一問題

- Current stage：完整成品已獲 Owner 實作授權；隔離核心 Task 1 起跑，R2／R3 並行閉合。
- Binding decisions：目前這台電腦、單一操作者、App 內多文件；建立／暫定命名／更名／列表／封存／恢復；保留 JD、訪談、Memory、歷史。Plate OSS、format 2／`jd-plate-clean-v2`、同畫面唯一工作稿、唯讀確切歷史與差異；沒有逐筆接受／拒絕。前景 AI 含純訪談均暫停手改，非每輪改稿。
- 唯一問題：員工遇到未保存、回覆遺失、取消、切文件、重開或封存時，是否都有真實且可操作的出口，並能讀懂完整 v2 的關係與改動？
- 已讀：[register](../current-decisions.md)、[decision process](../decision-process.md)、[主接線設計 §5–7](2026-09-09-jd-editor-app-integration-design.md)、[六切片 Task 4–5](../plans/2026-09-10-jd-editor-core-implementation.md)、[profile](2026-09-10-jd-plate-document-profile.md)、[語意 v2](evidence/2026-09-10-jd-semantic-contract-closure.md)、[contract strategy](../contract-strategy.md)，及隔離 `analysis_agent/api.py`／`service.py`／`catalog.py` 現行接點。
- PARKED：永久刪除、匯出、真人交付、其他電腦安裝、雲端／多人、離線同步、通用草稿合併／rebase／歷史還原引擎、Memory 重設計、自然模型付費驗收。

以下 **F** 是直接官方事實、**E** 是既有 code／probe 證據、**D** 是 Caliburn 有限映射、**V** 是待實作驗收。未列新的 Owner 產品選擇；名稱微調沿「工作執行要求」暫用。

## 2. 定點證據與採用界線

| 證據 | 結論與界線 |
|---|---|
| F：[WHATWG Web Storage](https://html.spec.whatwg.org/multipage/webstorage.html)、[Mozilla localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)；查閱 2026-09-10，Living Standard／瀏覽器內建 API | localStorage 依 origin 保存、可跨一般 browser session；可能被禁用、超額或清除，不能當 DB、跨分頁鎖或已保存 JD。D：只保留送出請求的 exact recovery record；寫入失敗不發送。開發 3001 的 localhost／127.0.0.1 不是同一 cache，日常入口固定一個 origin。 |
| F：[WHATWG BeforeUnloadEvent](https://html.spec.whatwg.org/multipage/nav-history-apis.html#the-beforeunloadevent-interface)、[Mozilla beforeunload](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event)；查閱 2026-09-10，HTML 頁標示更新 2026-09-08 | 有使用者互動時可請 browser 提示離開；字句由 browser 決定、事件不保證所有關閉情境執行。D：未保存時才裝 listener；不能承諾強制關閉／斷電後找回普通 dirty，也不在 unload 偷做保存。 |
| F：[Chrome Page Lifecycle](https://developer.chrome.com/docs/web-platform/page-lifecycle-api)、[Mozilla AbortController.abort](https://developer.mozilla.org/en-US/docs/Web/API/AbortController/abort)；查閱 2026-09-10，內建 Web API | 頁面可被 freeze／discard；abort 中止 browser 請求或讀取，不證明服務端工作停止或交易回滾。D：重開及恢復頁面先查 authoritative state；「停止顧問」必須走現有 stop／join／receipt 流程。 |
| F：[AWS safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)；查閱 2026-09-10，公開設計文章 | caller request identity、相同身分／不同參數的衝突、原子記錄是防重原則；不規定本案 schema 或永久保存策略。D：create identity 留在既有 catalog row；因本版不刪文件，生命週期隨該 row 保留，不另造通用 receipt 系統。 |
| E：[固定 Plate profile／來源與授權](2026-09-10-jd-plate-document-profile.md#1-固定引擎與官方插件)、[F03](evidence/jd-semantic-native-probe/README.md) | 沿 Plate 53.3.11、diff 53.0.0、list-classic 53.0.0、table 53.0.9、React 19.2.4 與 exact lock。核心等 MIT；diff 原衍生碼 Apache-2.0、修改部分 Apache-2.0／MIT。既有盤點已核授權，不升版、不採付費 kit。F03 不是 DOM 或正式 copy adapter 已過。 |
| E：隔離 API／catalog，2026-09-10 唯讀核對 | create 只有 title、每次新 UUID，尚無防重；run 有 `(document_id, request_key)` 唯一性，但 digest 只含 text。DocumentOutput 只有 id/title/created_at；無封存、更名、單文件 metadata 查詢。這些是新增接點的具體原因。 |

本輪不引入新的 LLM 機制。顧問、人工變更通知與來源依[OpenAI／Anthropic 既有官方接點研究](2026-09-10-jd-context-change-and-source-research.md)及 Task 3.3a；本稿只閉合 Web／App 入口。Web API 無需新增套件或商業授權；上述是查閱日的規格，不宣稱所有 browser 版本均已測過。

## 3. 員工看見的入口與同頁工作

```text
我的職務說明書                         [建立文件] [已封存]
客服專員                [開啟] [更名] [封存]
設備維護工程師          [開啟] [更名] [封存]

文件：設備維護工程師                  [回文件列表] [更名] [封存]
顧問訪談                         職務說明書        已保存
「我們先從你平常負責的工作談起。」  唯一可編工作稿   [保存]
                                 [這次改動] [歷史] [依據]
輸入你想補充或更正的內容            在原畫面展開唯讀前後內容
[送出]／[停止顧問]
```

D：列表只列文件名称、建立時間及需要注意的恢復狀態，不造完成率、核准徽章或品質分數。預設未封存，建立時間由新到舊、同時以 ID 固定順序；「已封存」可切回，空列表與查詢失敗有不同文案。名稱允許相同，不能以標題作 identity。

建立對話框只需暫定名稱，預填「未命名職務說明書」，沿現有 1–200 字元且非全空白檢查；由 App 產生 request key。建立成功後才進入該 document ID；不以 AI 猜職位，不預造工作事實。首屏說明「先談你的實際工作，資料足夠時顧問會開始整理。你可以隨時補充或更正。」空白 JD 顯示「尚未開始寫稿」，只在 current read 成功且確為空白時顯示。

命名是列表管理資料，不改 JD 正文的職稱、來源、Memory 或 revision；若員工要改工作事實，仍在正文或訪談處更正。唯讀歷史標明保存時間、人工／顧問修改及版本；保存不等於專業核准。歷史沒有「設為最新版」按鈕，員工可回到工作稿自行修改或說明要更正什麼。

## 4. 三種內容與普通未保存保護

| 種類 | 持有者／保存意義 | 離開與重開 |
|---|---|---|
| 已保存 JD、訪談及 run 結果 | 各既有 server owner；成功 receipt 或 canonical input 是事實 | 重開先讀 server，保持 document scope；不靠畫面快取判成功 |
| 普通未保存 JD dirty／尚未送出聊天 | 目前頁面記憶體；明示「未保存」／「尚未送出」 | App 的離開／切文件／封存動作先處理；browser reload／關頁用原生離開提醒。未提交內容不保證 crash recovery，不新建每字自動保存庫 |
| 已送出人工候選／尚未確認的 create 或 chat request | localStorage exact submission record，非權威 | 送出前寫入；重開按原身分對帳。不能把 cache 顯示為已保存、因讀入畫面便刪除，或用新 key 重送未知請求 |

D：App 控制的「回列表／切其他文件」在 dirty 時提供「保存後離開」「繼續編輯」「捨棄未保存修改後離開」。保存後離開需 receipt confirmed；失敗／未知留在同頁。若另有未送出聊天，單獨指出「這段話還沒送出」，選擇留下或捨棄；不能因保存 JD 順便送聊天或啟動模型。確認文案要列出實際會捨棄的兩種內容，不混稱全文件刪除。

有限 navigation 接法：跨文件／返回列表使用完整頁面 navigation（原生 anchor／location），App 按鈕在 navigation 前處理上述選擇；不另建 Next router blocking／popstate 回滾引擎。Browser 上一頁／下一頁／輸入網址／關頁沿原生 beforeunload，不能保證顯示自訂文案。單頁內展開歷史／依據不離開、不清 dirty。頁面 `pageshow`／恢復可见時重新查 metadata、run、head；刷新期間先唯讀，有 dirty 就保留原 buffer，不以晚到 GET 覆蓋。這些行為須在實際使用的桌面 browser 驗收。

送出保存時暫停輸入到回執閉合；不把「保存中的新一波打字」引入本版。confirmed failure 的 candidate 保留於原 submission record。若 head 未變，可在唯一 editor 修改原候選後，以新 key 建新持久提交；先持久寫好新記錄才清舊記錄。若 head 已變，保留 current 唯一 editor，將失敗候選以同頁唯讀材料提供；員工可複製需要的內容到 current 再保存，或明示捨棄該候選。不提供整份覆蓋新版或自動 merge／rebase；重新開第二次仍可回看未處理候選。

## 5. 狀態／動作矩陣

下表是 Web 投影；busy、封存、保存結果及是否可寫仍由 App 裁決。不能將多個真實失敗折成一個「空白」。

| 狀態 | 畫面與可操作出口 | 禁止／轉移條件 |
|---|---|---|
| 初次載入／讀取失敗 | 「讀取中」；失敗顯示「暫時無法讀取，請重試」。有上次成功內容則唯讀並註明尚未更新 | 未成功 GET 不顯示無文件／空稿；不啟動 writer |
| 找不到該文件／格式不支持 | 明示錯誤、回列表；格式錯誤保留服務端資料供診斷 | 不自動新建、清空、轉換或降版 |
| active、乾淨、無未閉合工作 | 編輯、保存、送出、歷史、切文件、更名／封存 | run admission 前重新核 current scope |
| active、dirty／未送出聊天 | 顯示未保存；可繼續輸入、保存或明示捨棄 | 送聊天先保存 JD；普通 dirty 不能自動替換成 server 新 head |
| 人工保存送出中 | 「正在保存」；可閱讀 | 暫停手改／新聊天／封存；timeout 轉對帳而非判失敗 |
| confirmed stale／保存失敗 | 「這次修改尚未保存」＋原因，候選仍在；可依 §4 處理 | 已終局 failure 不以同 key 變成功；新意圖先核最新 base |
| 人工結果／回執未確認 | 「保存結果尚待確認」＋「再次確認」；可閱讀、在可靠 record 已存在時離開 | 不另發新 writer／新 key；離開不是取消或捨棄 |
| 聊天送出、尚未知是否收到 | 原文保留並標示「正在確認是否收到」；read-only lookup | 不自動 POST 重播或清空輸入；確認收到再接原 run |
| 前景 AI running（含純訪談） | 「顧問處理中，暫停編輯」；可看稿／歷史／依據／停止，乾淨頁可切文件 | server 同樣拒絕手改；離開不隱含停止；其他文件維持隔離 |
| stopping／uncertain | 「正在停止並確認已保存的內容」或「結果尚待確認」；再次查詢、閱讀 | worker 停止且必要 receipt 閉合才解鎖；不以 timeout／abort 解鎖 |
| interrupted、可恢復 | 依既有 run 的 can_resume 提供明示繼續或停止／閉合；先查已保存結果 | 重開不自動續跑模型；沒有能力旗標不顯示虛假恢復按鈕 |
| run 已閉合 | 讀最新 head；如有新 revision 可開「這次改動」，無寫入則說明本輪只有訪談 | 不把顧問回答文字當保存成功證據；不每輪造版 |
| archived | 「已封存，可查看；恢復後即可繼續」；可讀 JD／聊天／歷史／來源、恢復、回列表 | JD／聊天新寫入與新 run 禁止；不刪資料、不改 scope |

讀取失敗的重試只做讀取；寫入恢復按同一 identity 與既有 ER03，零自動新意圖重播。恢復不成功時停止轉圈，顯示可再次確認及本機服務錯誤，不假造已完成。不同 document 的晚到 response、selection、source handle、cache、run ID 不能裝入目前頁面；以 request 綁定 document 與頁面 generation 判斷是否仍可顯示。

## 6. 最小 API／wire 增補與回覆遺失

依 [contract strategy](../contract-strategy.md)，以下是待納入**同一 active schema** 的有限 defs／欄位，不在 Web 手寫鏡像。隔離 Task 4 使用 `docs/specs/contracts/jd-editor-v2.schema.json` 及原 `C/` codegen；既有 analysis API 匯出接線引用生成 defs。正式採用歸回 `packages/job-analysis-contract`；mapper 隔開內部 catalog／service 型別。本文不是第二份可執行 schema，實作時 exact defs 與 codegen diff 必須一起 review。

### 6.1 建立與 catalog metadata

| 既有或新增入口 | 有限輸入／輸出 | 保存與重試規則 |
|---|---|---|
| `POST /documents` | 現有 title 加 `request_key`（App UUID）；回 Document metadata | 首次新 key 沿核心 Task 2.4，在同一短交易建立 catalog row（含唯一 `create_request_key`、原始 create payload digest）、唯一初始空稿 revision 與 head；失敗整批回滾，不能留下半文件。相同 key／相同原 title 僅回同一 document ID，不額外造 revision，即使後來更名／封存；不同 title 衝突。不呼叫模型；更名／封存也不造 JD revision |
| `GET /documents?archived=false\|true` | 預設 false；Document metadata list | 返回實際空陣列才顯示空列表；保留既有 created_at，明示排序 |
| `GET /documents/{document}` | metadata：現有 id/title/created_at，加 `archived:boolean`、`metadata_version:integer` | version 是 catalog 條件式更新 token，不是 JD revision、Memory 版號或 workflow state |
| `PATCH /documents/{document}` | discriminated command：`rename`＋title 或 `set_archived`＋boolean；都帶 `expected_metadata_version` | 短交易鎖定 catalog row、核 version，實際有變才 version+1；相同目標可 no-change。版本不合 409，回讀 metadata；不偷偷用最新版 token 重發 |

Create cache namespace 為 `caliburn:jd-plate-clean-v2:create:{request_key}`，保存 exact title/key，成功得到 document ID 後清理。存在 unresolved create 就先提示「確認上次建立結果」，不因超時配新 key；員工主動再次確認可同鍵 POST，這是相同建立意圖。DB 原子唯一性處理雙擊／並發；不能只用按鈕 disabled 或以同名搜尋當去重。cache 清除失敗無害，重開查得同 ID。建立 endpoint 不初始化模型或收費工作。

Metadata 不需另建通用 operation receipt。送出前保存 exact `{document_id, expected_metadata_version, command}` 至 `caliburn:jd-plate-clean-v2:catalog:{document_id}`；回覆遺失先 GET metadata。若讀得目標狀態，顯示「目前名稱／封存狀態已更新」，不聲稱證明是哪次請求執行；若仍是原 version，可由員工重試同一 conditional command；若版本已變且不同目標，提示目前值讓員工重新決定，不自動覆蓋。DELETE endpoint 不新增。metadata payload、key 與 cache 從未交模型。

### 6.2 聊天收到與模型執行分開確認

沿用 `POST /documents/{document}/runs` 的 request_key 與 run 身分；送出前記錄 exact text、abandon_pending 及 optional `jd_selection`，namespace `caliburn:jd-plate-clean-v2:run-submission:{document_id}`。同文件 unresolved input 不並存第二筆新送出。新欄位的有效輸入 fingerprint 應涵蓋所有影響此次 admission 的參數（含 selection、abandon_pending），不能只沿目前 text digest：相同 key 但不同 selection 必須 conflict，不能悄悄套另一位置。

新增唯讀 `GET /documents/{document}/runs/by-request?request_key=...`，route 排在任意 run ID route 前；key 用 query parameter 編碼，沿既有長度檢查，不假定所有歷史 key 都是 UUID。有限結果為 `found:false` 或 `found:true, run:RunOutput, input_received:boolean`；`input_received` 由 server 核 canonical input，不憑 catalog row 存在猜收到。若查詢本身失敗，HTTP 錯誤而非 found:false。這是 App 恢復接點，不新增模型工具或第二聊天 store。

- 重開先 GET，確認 input_received 後才清已送出 recovery record，保留 run ID 以讀現有狀態；目前狀態／可恢復行為仍沿既有 RunOutput，不能單靠「收到」稱模型成功。
- found:false／input_received:false 表示當下尚無已確認輸入，不能證明原 request 永不完成。提供「再次送出同一則」明示動作，仍用原 key／exact payload；server lock／唯一性／canonical input 去重是最後防線。重開不自動 POST，因既有 submit 在 not_received 時可能真的啟動模型。
- 查到 running／interrupted／uncertain 就接原 run；不要新建訊息或用 `abandon_pending:true` 偷關前次工作。只有員工明示選擇才走既有停止／繼續接點。
- 選取失效、base 變動或 admission 已確定拒絕：保留原聊天文字、要求重選；新意圖才配新 key。單純 response-loss 不重新捕捉 selection。

JD manual-save 的 exact submission、receipt及模型工具契約不變。2026-09-10為已採cache-lost效果，依[有限恢復設計](2026-09-10-jd-manual-recovery-transport-design.md)補App-only GET/POST `/documents/{document}/jd/manual-recovery`：GET唯讀發現原key／結果，POST只對明示原key作一次清理／對帳，不重跑candidate。全部status均投影同一server `write_blocked`／`can_recover`，Web不猜owner；available待clear仍有明示出口。exact cache＋no_pending保留原key完整manual-save的另次明示提交，可能首次送達，不以absence宣稱零效果。此明確取代原「manual不新增route」限制；沒有新模型工具、store或泛用command engine，catalog/chat cache仍不得取代人工候選。

## 7. 封存與恢復的 admission

D：封存只是 catalog 中的可逆收起。`document_id`、Saver thread、Store namespace、JD head／revisions／receipts、sources lineage、run history 不變；恢復只改 archived=false。不做 delete cascade、重建 context、複製文件或啟動模型。封存後讀取與終局結果查詢維持可用。

App 封存前先處理本頁 dirty／未送出聊天／失敗候選；已提交但尚未確認的工作先對帳，不能以封存隱藏它。保存中、running、stopping、uncertain 或未閉合 interrupted run 回 busy，提供查看／停止並確認的原流程；closed 且必要結果已知才封存。不把「封存」包成暗中 stop／join。純訪談同樣須閉合；已收到來源衍生的背景 B1／B2／C 沿原政策處理，包括尚未首次排程、部分批次及受控恢復，不因封存額外啟動工作，也不等待背景歸零。

隔離 `scheduling.py` 的 `tick()` 實際呼叫 `service.list_documents()` 枚舉工作。此**內部完整 catalog 枚舉必須包含 archived**，保留已收到來源的既有排程／恢復政策；§6.1 的 active-only 預設只屬 UI HTTP 列表，不得把其過濾套到內部 `list_documents()`。不新增另一套 scheduler 或因封存清理既有 admission／recovery 記錄。

server 在**同一文件 admission** 內檢查 archived、尚未閉合的 foreground／人工 writer，再改 catalog；新的 manual-save／run admission 在同一邊界檢查 archived，避免查完 busy 後又啟動新 writer。單 API worker 限制不變，SQL 短交易不包住模型。重啟先既有 reconcile，不憑 process lock 消失便准封存。更名也在該有限 admission 內執行，忙碌時留到閉合後，避免本版增加額外並發政策。

查原終局 manual receipt、查原 run／request 或同 key create 去重應先於「封存拒絕新寫入」；封存不能遮蔽已保存的真結果。恢復 endpoint 可在 archived 狀態使用，不需要先建立第二份 active 文件。

另一分頁尚未提交的 buffer 不是 server 能知道的狀態。封存後該分頁恢復焦點會保留 buffer 並顯示唯讀「文件已封存，恢復後才能保存」；延遲 POST 在 API 被拒，資料留在候選／buffer，不自動丟棄。這不是跨分頁 draft 鎖或同步保證。

## 8. v2 結構、共享關係與實際差異

D：同一 renderer 用於 current、確切 before／after 與唯讀 diff；完整 K／S 只存一次，引用用該版定義解析。Web 只呈現 server 已驗資料，不決定有效性、來源真偽或工作適用性。

| 內容 | 同頁呈現與有限人工動作 | 不可接受的省略 |
|---|---|---|
| Task | 名稱／完整敘述及條件；其下「工作成果／產出」「工作執行要求」兩組並列閱讀、多項清單各自編輯；空組維持空 p | 不把要求掛在某成果、不自動合併、不把未知填成「無」 |
| Task 的 K／S | 「相關知識」「相關技能」列該版 item 可讀名稱；點擊在同頁展開全文／定位該項，無名稱顯示「未命名知識／技能」 | 不直接展示裸 ID，不因名稱相同合併，不回退 current 解析歷史 |
| K／S 完整項目 | knowledge／skills 章節有可編全文，旁列「此項目供哪些工作使用」；反向清單由同版 outgoing links 推導、按 Task 順序 | 不存第二組可編反向關係；未被引用項目仍顯示、仍可保存 |
| 建立／解除人工引用 | 在 Task 有限控制選擇同文件現版既有 K／S；只 set／unset 對應欄位，沿同一完整性 validator | 不要求員工配 ID；移除被引用項目先列使用者，需明示解除／改接後才可刪，不自動清線 |
| 共享項目改字 | 編輯旁持續显示「共用於 N 項工作」及可展開工作名稱；實际保存後显示 item 前後全文與 affected Tasks | 文案不稱所有引用者都已重新核實；純名稱變更也要可見 |
| 來源 | 依原來源 owner 顯示「依據」，可同頁看確切原問答；失效、讀取失敗各顯示實況 | 不以 Memory path 冒充原文，不造 footnote 內容，不把手改當重新核實 |
| 格式與 metadata | profile 支持 marks、section 用途、表格尺寸／span／背景／border、source_refs、K／S links 均可讀到實際前後值 | 不用 JSON 面板代替員工可讀說明，不以紅綠正文代稱全部改動 |

原生 `computeDiff` 繼續負責可用的文字／結構高亮；不修改原生 diff、不另建通用匹配。對一次有 operations 的保存，沿既有實際 operation 材料列有限屬性「修改前／修改後」；同 ID 刪／增比較節點都必須顯示，React key 不能按業務 ID 去重。對任意兩份快照缺少 operations 的比較，顯示確切兩版與「部分格式或關係差異未高亮，可查看兩版完整內容」，不得聲稱沒有變更或補造 operation。

K／S 的連線變更有可讀 before／after 清單；共享 item 變更的相關工作列出比較兩版的引用者聯集，分明「原本使用／目前使用」，不把已解除者漏掉。這只遍歷已驗有限 Task link 欄位，不猜語意相似度或發明新 diff engine；兩版各用其自己的標題及定義。同頁可看全文，不能只給「改了 3 處」摘要。

歷史／來源展開為唯讀，不改 editor selection、dirty 或 session undo stack。回到 current 才能編輯；確切歷史不套 normalization、不更新 ID。原生 undo／redo 的跨 AI batch 邊界沿 Task 4.5；重開 stack 重置、既有 revisions 仍保留，沒有歷史倒帶 API。

## 9. Task 4／5 精確增補清單

本節交主線納回既有計畫，**不另開平行 runtime 計畫、不由本稿修改 plan／register**。A/J/W/C 路徑沿六切片。更名／封存／恢復完整日常 UI 屬 P5；Task 4／5 先做共同 metadata／admission seam 及固定驗證，避免 P5 再推翻核心。

| 原位置 | 必須增補的工作與輸出 |
|---|---|
| Task 4 Files／4.1 | 增 `W/src/documents/DocumentList.tsx`、`DocumentActions.tsx`、`W/src/jd/navigationGuard.ts`、`requestRecoveryCache.ts` 及對應測試；修改 A 的 api/service/catalog 與 API 測試，產生 §6 defs；不手寫 `analysis-api.ts` 第二 shape。完整管理 UI 可 P5 完成，create／list／reopen 是本切片出口 |
| 4.2／4.3 API 表 | 加 §6 metadata／create identity 及唯讀 run-by-request lookup；首次 create 的 identity／catalog／初始空稿 revision／head 沿 Task 2.4 同交易，同鍵重試不多造版；同鍵不同 selection 負例。UI active-only 列表與包含 archived 的內部 catalog 枚舉分開。catalog setup 採既有隔離 DB 政策，不讓 `create_all` 被誤稱可替已存在表加欄；需要 schema 更新時明列 migration／setup，保留既存資料 |
| 4.3a | 保留原人工 submission 規則；增加普通 dirty vs sent cache 區別、localStorage failure、origin／document namespace、confirmed stale 的唯讀候選與第二次重開；create／chat recovery 依 §6，不用共通自動重播 |
| 4.3b | dirty 保存→真 selection capture 原順序不變；丟失 admission response 只保留原 exact range，不重抓 selection；服務端 digest 納 admission 有效欄位 |
| 4.4 | 加 §8 Task 成果／要求空組、K／S 同版全文／引用與 incoming 清單、共享影響、有限 link 控制、可讀錯誤；貼上／copy 仍走原生＋同一 validator |
| 4.5 | 明定相同 renderer、精確 before／after、有限 metadata 說明、無 operation 的高亮限制；展開歷史不改 dirty；加完整頁面 navigation 與 pageshow revalidate |
| 4.6 驗收 | 加下表 J01–J12 的 Web／API／DB 證據；維持原 DOM／IME、1 張基本資料表＋8 Task 兩組＋5 K／5 S 驗收，不回到 v1 三表 |
| Task 5 Files／5.1 | 在 admission／close tests 加 archive↔run/manual race、讀原 receipt 優先、chat admission 丟回覆與 reopen 不自動啟動模型、不同文件晚到 response |
| 5.2 | 同文件 gate 納 archived 與 catalog metadata 更新；重啟先 reconcile，再允許新寫入／封存；未知結果不因 UI 離開而解鎖。背景 B1／B2／C 對已收到來源沿原政策，不因封存額外啟動或要求背景歸零；`scheduling.tick()` 所用 `service.list_documents()` 保持含 archived，驗尚未首次排程／部分批次／受控恢復不被 UI 過濾遺漏 |
| 5.3／5.4 | browser abort／關頁不當 stop；維持 worker join→原 receipt→補缺 ToolMessage→閉合。K／S 先建→read→link 中間取消保留已保存未連結稿。新程序再查 run request identity，不新建原文 |
| 5.5／README | 記普通 dirty crash 限制、已提交恢復 record、唯一日常 origin、封存保留範圍／writer gate、查詢與繼續的差別；自然模型、P5完整管理UI及production G6各自未驗，不合併宣稱完成 |

## 10. 有限驗收、停止條件與 closure

| 情境 | 可觀察 pass／fail |
|---|---|
| J01 首次／列表／讀取錯誤 | 真成功空列表才出建立引導；DB／API 失敗不顯示「沒有文件」；同名两份仍不同 ID，建立不產生模型呼叫 |
| J02 create 丟回覆 | 首建恰一 catalog row（含 key／digest）、一初始空稿 revision 與一 head；注入交易失敗回滾後無半文件。commit 後斷連、重開／雙擊同鍵仍同 document ID，不多造初版；更名／封存後再重放仍同 ID；不同 payload conflict |
| J03 普通 dirty | JD 与未送 chat 分別驗 App 保存／留下／捨棄；失敗不離開；browser 返回／重載原生提示。無已提交 record 時不宣稱 crash 可恢復 |
| J04 保存 cache | cache 失敗不發 POST；POST 後關頁、confirmed failure 後再次關頁仍 exact candidate；unknown 不換 key；late head 不覆 buffer |
| J05 聊天回覆遺失 | canonical 原文只一次、run 只一次；唯讀 lookup 不啟動模型，not_received 需明示同鍵 retry；同鍵不同 selection 拒絕；已接收後重開不自動 resume |
| J06 取消／未知 | 純訪談取消不等 JD receipt；commit 後取消不撤銷已保存稿；worker 未停／lookup unavailable 不解鎖；停止與實際結果據實顯示 |
| J07 切文件／頁面恢復 | A running 時開 B，A 晚到 response 不入 B；不同 cache／refs／原文互不污染；bfcache 恢復先 revalidate，不因舊畫面顯示 active 就可寫 |
| J08 封存／恢復 | busy、dirty、unknown 有操作出口；archive/run/manual barrier race 只有合法一方取得 admission；封存後 delayed 新寫入拒絕、原 receipt 可讀；恢復後相同 ID／JD／問答／Memory／歷史可續用。另以固定背景案例驗 B1／B2／C：已收到來源的未首次排程／部分批次／受控恢復仍依原政策被 tick 枚舉，含 archived 的內部列表不受 UI active-only 過濾；封存本身不額外啟動背景、不等待背景歸零 |
| J09 完整 v2 DOM | 6章、1表、子清單、8 Task 各自兩組、5 K／5 S全文与 links；空組不造字、Task4／8條件不丟；真 IME／選取／貼上／copy／undo 同原驗收 |
| J10 共享／歷史 | 兩 Task 共用 K；改 K 後兩者可讀名稱皆更新、before 使用舊定義；連線增刪／引用順序可讀；解除者在 before 仍可回看，無 orphan 被悄悄修掉 |
| J11 真實差異 | 刪增同 ID 兩段均在；只改空 leaf mark／source／span／links 也有前後可讀材料。只有快照時限制提示可見，computeDiff 空不宣稱無改動 |
| J12 正常完整旅程 | create→純訪談無 JD 版→足夠才寫→手改保存→下輪人工通知→查改動／依據→停止／重開→更名→封存查看→恢復續談；全程無第二可編稿、accept/reject 或下載入口 |

全部採既有離線 provider／固定 transport、明確測試 DB、零付費呼叫；DOM／IME 必須真 browser，PG／新程序必須實際執行。這份設計未執行上述驗收。J08/J12 的完整日常管理UI在 P5 才可標通過；核心不能提早代稱日常成品。

**停止線：**（1）需要通用 draft sync／rebase／history restore 才能保內容；（2）只能靠 client disabled 阻止已封存寫入；（3）cache failure 或讀取 error 被當成功／空白；（4）恢復必須自動重播模型、新 key 或改 Memory owner；（5）官方 renderer 無法保留必要資料而想靜默攤平。遇到這些具體反證，保留候選／既有保存資料並回報，不能用新引擎或降低驗收繞過。

**Decision / finding：**R2／R3 可用原生 browser、既有 catalog／run identity、同一保存 gate 及有限 JD renderer 閉合；新增 create 防重、metadata conditional command、唯讀 chat request lookup，沒有新增 AI 機制或第二 authority。

**Status：**有限 G4 設計已通過主線獨立review，PDR-01／03閉合，§9已納回六切片；[審查證據](evidence/2026-09-10-jd-product-baseline-review.md)。實作、DOM、資料恢復、自然模型及員工試用未驗。

**Why / sources：**新缺口由現行 API／catalog 與已核准旅程逐項對照，官方只核 browser lifecycle／storage／idempotency；正文 §2 與既有 profile／context 責任文件提供證據，無新廣搜議題。

**Affected artifacts：**本檔；主線後续依 §9 更新六切片／register；schema、catalog setup、API/Web README 在各實作切片同步，正式 authority 由 R5／G6 負責。

**Reopen trigger / next gate：**Owner 改變普通未提交資料的 crash 保證、要離線同步／多人、實測原生 navigation／renderer 不能達驗收，或與 R5 owner／setup 衝突時才重開。其餘直接進 Task 4／5 指定接線與 P5管理UI，不重問已批准產品方向。

2026-09-10 Task5 transport閉合：原terminal與已admission pending恢復先於archive的新寫入阻擋；按同一owner／原key比對，晚到A不碰B。§9的Task5 Files加actual DTO export、generated Web及API wrapper；J04/J06–08的可觀測接合依上述設計MT01–14，未宣稱已實測。
