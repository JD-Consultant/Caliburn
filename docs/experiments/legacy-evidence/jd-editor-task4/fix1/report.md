# Task4 review fix1 — 凍結交接

2026-09-10；`codex/analysis-only-agent`；root 的初輪69檔 snapshot／review 為本次對照。R01–R04 已各做有限修正與受影響驗證，交 root 窄複核，尚未自行宣告 review PASS／commit。source 精確15檔列 `task-4-fix1-source-files.json`，hash 列 `task-4-fix1-source-manifest.json`；完整自身交付列 `task-4-fix1-files.json`。沒有改 production、paid model、key、DB guard，沒有清資料、commit 或 spawn。

## R01：明確拒絕與 unknown 分流

新增 actual Pydantic API `ManualSaveRejection`，由原官方 codegen 生成 Web 型別，包含 `admission: not_admitted`、原 request_key 與 message。沒有改 active JD SSOT／grammar／JdWriteResult，也沒有新建另一份 schema validator。

manual input 的 Pydantic validation 失敗、scoped envelope、source、archived／foreground gate 拒絕，只有在同一 service lock 內查明該 identity 無 receipt 時才回明確未 admission。UUID 依有效 DTO 相同規則 canonicalize；`manual_operation_id` 從既有 manual_intent 原算式抽出共用，沒有改 identity 演算法。Pydantic validation 失敗的查詢經官方 run_in_threadpool，不阻塞 async route handler。已有 receipt 的非法重放／不同格式 UUID、receipt unavailable、一般 HTTP 409／422 不帶此肯定；正常同鍵 receipt 仍優先於 archived／busy。

Web 只在明確回覆 request_key 與目前候選相同時解除 manualUnknown，保留 exact candidate 與原 chat，提供明示捨棄出口；未分類409／422／503、不同 key 的明確回覆和網路未知均保留鎖。與 R02 一起作用：拒絕後仍不能用一般 current save 靜默覆寫原候選，須員工明示處理。

RED：真 API 的 invalid element 回422但沒有 admission；Web matched-key 明確拒絕後仍 unknown。GREEN：API 2 tests（原完整 manual route 與新增 rejection）涵蓋 body拒絕、既有receipt非法重放、UUID正規化、receipt unavailable、正常receipt優先。Web matched-key409/422、無分類409/422/503、不同key均驗。真 headed Chrome 由 actual API archived409 回覆送入 Web，candidate/key/value與原問句保留、head未改，員工按確認後才清候選；獨立文件 route.abort 模擬真正網路未知，candidate保留、捨棄 disabled、actual contenteditable=false。

## R02：舊候選不被一般 current save 消耗

在任何新 payload/key/cache.write 之前，已有 unresolved candidate 時一般 save 明確返回 false 並提示先處理。保留原單一 document cache；沒有多版本 cache、merge 或新 authority。員工可明示捨棄後保存 current；未新增自動轉用或偷偷覆蓋工作稿。

RED：重開 stale 候選後編另一段 current，再 save 竟第二次呼叫 API並覆 cache。GREEN：一般 save 不 POST；再次建新 session/load 仍得到原 exact `ONLY RECOVERABLE OLD TEXT` 候選；員工 discard 後 cache 才清，新提交可成功。本輪此項為 session 持久 storage/port 窄測試，不冒稱重跑所有真 browser recovery。

## R03：撤回初輪 clipboard 保真綠燈，補真內容驗證

初輪 `web-app/task4-input-browser.json` 與 screenshot／report 原 bytes 完全保留。當時 pasted 是無關技術文字，只驗段數與ID，**不能證明複製保真**；初輪 report 的相關通過表述由本補充撤回其保真含義。

新 `task4-fix1-clipboard.mjs` 使用受控 clipboard sentinel、實際鍵盤選取「複製保真內容」（兩 leaf，第一 leaf bold），先觀察 DOM range，再 Ctrl-C。首敗 raw 顯示 copy event已發生但 data types=[]，clipboard仍sentinel；這次沒有讓錯內容貼入後被弱斷言放過。最小 harness 修正是等待產品既有「已選取正文」訊號，再核 navigator.clipboard.readText 等於實際range原文；沒有新增產品 copy handler、定位器或文字重找。

固定套件原碼支持時序界線：slate-react0.126.4 `dist/index.js:3170–3228` 經 throttled DOM selection 更新 editor；`:4007–4012` copy 走官方 setFragmentData。可見訊號來自既有 Plate onSelectionChange，並非測試自設 editor 狀態。不能把這個受控首敗推定成初輪所有焦點因素已逐一隔離。

GREEN raw 同時記 copy/paste event 的 text/plain、text/html、application/x-slate-fragment，clipboard read 原文/HTML；貼上後兩 paragraph children（含 bold）全等、type相同、ID唯一且copy不同於source；保存→重開 exact fragment全等、DOM全文兩份相同。headed installed Chrome153.0.8010.37，Playwright1.61.0；**OS IME NOT RUN** 不變。只驗這個有限 paragraph/marks 案例，不宣稱跨應用所有 refs/table clipboard。

原 `task4-input.mjs` 也补上 DOM range／app selection ready／clipboard原文／children/type/ID 斷言，防止未來再產同類假綠。未重跑整組 input；獨立 fix1 script 已驗同接點，原script最後只做單檔 lint。

## R04：create cache 獨立初始化

create recovery 在發出列表 GET 前獨立讀取並有 ready/error 狀態；未檢／讀失敗／有未解記錄都不能產新 key。create handler 再读 cache 守住條件，原 recovery 也必須匹配讀到的記錄；不只依賴 disabled button。列表 GET 失敗不清本機 cache 錯誤，不把它當空列表。

RED：existing cache＋slow/failed GET 無法顯示原記錄；cache unreadable 後強制 submit handler 仍發新create。GREEN：三個情境皆不發新key，既有記錄立即顯示且只能原key確認。沒有重跑 PG create 原子性。

## 受影響驗證與首敗分類

`task4-fix1-verification-api-web-codegen.json` 記 API2、Web19、check-codegen exit0；同檔保留 types初敗。修正僅測試註記後，`task4-fix1-verification.json` 記 type/lint/build exit0。原 clipboard script 最後單檔lint亦exit0。API原有 Starlette anyio BlockingPortal alias deprecation仍在。沒有重跑完整154、native suite、r2性能、selection/history或已過browser群；active SSOT hash仍 `893fdb43fe2696846e74f15f2b5e12ed97a00f5ff1a5bc667c11ce734d7430fc`。

其他首敗按原因保留：第一次 vitest 工作目錄錯而找不到 tests（不是RED），改目錄才得R02/R04四個真RED；API第一輪fix把生成UUID物件當字串導致原busy409變422，轉字串後綠；typecheck發現 Testing Library 不支援 Playwright 的 exact option、fixture未標 tuple型別，僅修測試；rejection browser先用 textbox role查readOnly element失敗，改核既有 aria-label 的 contenteditable=false。舊log不刪、不改判。

## 自有程序／證據

最終 API scoped launcher **5248** → Python30616 → uv20400 → venv Python20652 → worker **29272**，console18736；8091。Next launcher **24248** → server **25744**，console12956；3001。實際 commandline／parent 留 `task4-fix1-owned-processes.json`。新 JdEngine self.node 仍 isolated22.23.2，完整 manifest複本 `task4-fix1-browser-server.json`。舊 API580與fix中19368已按核過的自有commandline停止；目前程序均hidden啟動。日後先核PID未被重用，不按port猜kill。

durable 新目錄 `docs/specs/evidence/jd-editor-task4/fix1/`；原 `web-app/`36 raw／report／manifest及 root-owned Node/schema-performance證據不變。精確清單／hash／copy核對與初輪證據未改核對在新manifest。README原11行保留。原 Task5/P5/Task6／production gate限制完全不變，這次只交四個 finding 的 closure證據。
