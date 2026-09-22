# Task 5：人工保存未知結果的有限 transport 設計

- 日期：2026-09-10；狀態：有限G4 Spec／quality PASS，MRD-R01／02 CLOSED；root採用於隔離Task5，實作／實測仍待完成。[原候選／差異／獨立closure](evidence/jd-editor-task5/manual-recovery-transport/review.md)保留；正文為受審34004e1e版本，僅本狀態行更新。
- 範圍：只補 lifecycle 已採用的 cache-lost manual 明示恢復效果；0 模型／DB／Job／程序執行。未讀 Task 5 施工 source。
- 原碼證據：只以接受點 `8eec072d51e97735b22c5f0df598b67101fe570b` 的 `experiments/analysis-agent` 與 `experiments/jd-editor` 指定接點為準。下列 A/W 為這兩個目錄下的 API 與 web。
- 效力：遵守 current register 本輪唯一 transport 問題；不改 production ADR authority、不擴充三個模型工具、不建立新的 operation store。

## 1. 實際缺口與推薦

推薦增加同一路徑的兩個 HTTP 方法：`GET /documents/{document}/jd/manual-recovery` 與 `POST /documents/{document}/jd/manual-recovery`。GET 唯讀發現目前 root manual descriptor／查原 key 的 terminal receipt；POST 只對明示的原 key 做一次有限恢復。既有 `manual-save` 繼續負責完整 candidate 的保存，不能以假的空 candidate 調用它來恢復。

原 journey §6.2「manual 不新增 route／結果枚舉」必須精確豁免這個 App-only 恢復接點。這是已採效果缺少必要介面，無需重選資料 authority 或新增通用 command engine。本文只提此一方案。

接受原碼的依據：

| 接點 | 實際契約與影響 |
|---|---|
| `A/src/analysis_agent/jd_routes.py::manual_save` | 完整 `JdManualSaveClientInput` 才能產生 intent；同 lock 先查原 receipt，再查 archive／run admission。不能以只有 key 的 recovery request 通過此 validator。 |
| `A/src/analysis_agent/jd_contract.py::manual_operation_id` | canonical UUID request key 與 document 經既有 UUID5 對應唯一 operation；可直接重用。不需要另發簽名 ref 或持久 generation token。 |
| 同檔 `request_digest`／`manual_intent` | digest 包含 base／origin／完整 payload；cache 遺失無法重算。恢復必須從可信 root descriptor 取得 digest，不能從 key 猜。 |
| `W/src/jd/useJdSession.ts::load/save` | 現在有 candidate 會在 load 呼叫 `save(true)`；Task 5 必須使未知恢復先走唯讀發現及另次明示操作，不能把此自動 exact POST 當恢復出口。 |
| `W/src/jd/JdWorkspace.tsx` | 恢復提示目前依賴 candidate；cache-lost 需要獨立的 server-pending 提示，不假造候選。 |
| `A/scripts/export_web_contract.py`、contract `scripts/codegen.mjs` | actual API Pydantic TypeAdapter schema 已生成 `web/src/generated/analysis-api.ts`；新 App DTO 必須進入這條現存生成路徑。 |

## 2. 最少 transport shape

本節是待實作的 API Pydantic shape 規格，不是新增模型 wire schema。實際類名可沿 repo 命名，欄位及語意不得各層手寫成不同版本。UUID key 回傳 canonical 字串。

### GET：不附 key 發現目前 pending；附 key 只查該次原操作

可選 query `request_key: UUID`。不附時，從唯一 root `jd_manual_pending` 取得 key；附時，用既有 `manual_operation_id(scope, key)` 找原 operation，絕不退回另一筆目前 pending。讀取 root／receipt／owner 的有限 snapshot；必要的 read lock 只保護一致辨識，不取 PG FOR UPDATE、不輪詢等 SQL 完成。

成功 body 是 discriminated union；所有 GET／POST 成功分支共同必填 `write_blocked: bool` 與 `can_recover: bool`，不是只有 unknown 帶動作能力：

| status | 必要內容 | 精確意義 |
|---|---|---|
| `available` | `request_key`、`result: JdManualSaveResult` | 找到該原 operation 的真 terminal receipt，以既有 mapper 輸出。只包含 terminal confirmed 結果，不把 unconfirmed outcome 放入此分支。成功與終局失敗由原 result 區分。 |
| `unknown` | `request_key` | 有匹配的可信 pending 身分，尚無 terminal receipt。共用 can_recover 表示此原 key 此刻是否可明示恢復，不是停止證明或預先 admission。 |
| `no_pending` | `request_key: UUID or null` | 沒找到所查身分的 pending 或 terminal；null 只用於不附 key 且 root 沒有 pending。不是保存成功、未入工具、未提交或可重播證據。 |

共用欄位精確語意：

- `write_blocked` 由同文件既有完整 admission 判斷來源唯讀投影：包含 archive、所有 native/read/manual/AI owner、未閉合 bindings／turn／manifest 及 root descriptor 等既定阻擋條件。true 表示不能新 admission，false 只表示此 snapshot 的 server gate 開放；不代表特定 payload 合法，也不是原意圖零效果證明。Web 不從 receipt/status/run 自行重算這份 policy。
- `can_recover` 只指 response 的原 request_key 是否有匹配且此刻可取得恢復權的 descriptor／owner 清理或對帳工作。available 且匹配 descriptor 待清也可為 true；terminal 已讀與清理完成是兩件事。no_pending 或 key=null 必為 false；只有別的 owner 阻擋時也不得冒稱此 key 能清別人。它可以與 write_blocked=true 同時成立；恢復是既有意圖閉合，不是新保存 admission。
- 兩欄由同一 owner/admission 在回應前的一致 snapshot 產生；GET 只觀察，POST 完成本次結果／清理後重讀。任何必需狀態不可可靠取得則回 API 錯誤，Web 維持 blocked/read-unavailable，不能猜 false。POST 仍原子重新核權，snapshot 不保證競速後獲准。
- available + write_blocked=true + can_recover=true 顯示原結果與「清理上次保存狀態」入口；available/no_pending + write_blocked=true + can_recover=false 表示此 key 無清理權，保留唯讀並重新讀取狀態，不拿舊 key 清其他 owner。若本 key 待清且另有 owner，清本 key 後 write_blocked 仍可為 true。

不回傳 candidate、完整 descriptor、digest、所有歷史 operations、AI run 或人工原話。descriptor 的 operation／base／digest／origin 留在 server 的既有 root；browser 只需 key 能對帳。`available` 是「結果可讀」，不是「原候選已成功保存」。終局 failure 不冒充 success。

有 descriptor 時先查其原 receipt，即使 root 尚未清除或文件已 archive，也可回 available。receipt 不存在才看 matching pending／owner snapshot。對已知 key，即使 descriptor 已清除，仍直接按同 document＋operation 查回原 terminal result。archive 不能遮蔽這個結果讀取。

DB／checkpoint／owner snapshot 不可用，無法可靠完成辨識時回正常 API 錯誤（例如 503），不得吞成 no_pending。422 為 query 格式錯；404 為文件不存在。可讀到 pending 而沒有停止證明是 unknown，不是 HTTP 失敗。response 與 browser fetch 使用 no-store。

GET 絕不 terminate、set stop、清 root、寫 failure receipt、更新 checkpoint、start native／模型，亦不得呼叫現有會進 Node 的 `read_document()` 當 discovery。即使 terminal 已存在，GET 也只回報，descriptor 清理由既有 owner close／明示 POST 負責。active manual 正在正常處理時回 unknown/can_recover=false，不把查詢當 cancel。

### POST：只有原 request_key，不接收 candidate

body `{request_key: UUID}`，extra forbid；不可省略，不可讓 client 用「現在那筆」作通配。回傳同一個 union，POST 的 no_pending 一定回原 key。無任何模型、重跑 transform 或發布候選的分支。

1. 同文件 admission lock 內 canonicalize key，計算既有 operation，先讀該 operation terminal receipt。若存在，保留原 available 結果；只有仍匹配的 root descriptor 且能取得同 owner 的一次恢復權時才做既有終局 clear，同身分 attempt 已在進行則不重入。clear 失敗不改寫真結果；回應重新投影 write_blocked=true，若匹配待清仍可另次嘗試則 can_recover=true，保留明示出口。若只剩別的 owner，can_recover=false，絕不代清他人。若無法確認完整 gate，回 API 錯誤，不授予新 admission。
2. 無 receipt 時，核 root descriptor 的 request_key、derived operation、scope 與可信 digest／base／origin 一致。不存在或不同 key：回 no_pending（原 key），不碰目前另一筆。descriptor 壞掉／讀取失敗則 API 錯誤並保留 gate，不以 no_pending 抹去未知。
3. 原始 manual 的正常執行／publisher 尚持有效處理權，或同身分已有 recovery attempt：回 409 表示這次恢復未取得 admission；不能並行再清理，也不是原 save 的 `ManualSaveRejection`。UI 保留未知與 candidate。can_recover=true 仍可能因競速收到此 409。
4. 匹配且可進恢復時，沿同 `DocumentRuntime` admission 原子占用一次 recovery attempt，保留原 document generation／binding。只針對同 owner 的原 handle／publisher 做 lifecycle §4.2 一次有界清理；lock 外等待，再 lock 內核同一 generation 與身分。這個內部 generation 是既有 owner race 機制，不新增 durable 欄位或 token 服务。
5. 同程序需原 native／pipe／thread 停止和 Python publish unwind 證據；重啟需真 bootstrap exact old Job 停止證據。只有既定 §6.5 停止後 head-lock、下一 statement 查 receipt 的 PG port 才可判 known-none。若有原 receipt，回它；known-none 才沿原 identity/digest failure port 寫 `save_failed` terminal，絕不虛構 candidate。receipt race 沿既有交易裁決，真 terminal 優先。
6. 停止或 SQL 結果仍不能證明：unknown（原 key）；本次 spinner 結束，不自動再嘗試。可恢復 snapshot 依 owner 當前狀態重算。未知保留 binding；清不掉的 descriptor 不代表保存失败已閉合。

GET/POST 對同 key 原 receipt 的回傳不要求完整 payload：這是原 operation 的結果查詢，不是重新驗證任意 candidate 或授權寫入。Task 4 已有 request key 必須對應不可變 exact submission 的規則不變；新的 body 根本沒有 payload 可以替換它。既有 manual-save 的同 key／不同 payload 仍走原 digest conflict。

## 3. 原身分與 race 不變量

- `document + canonical request_key` 已是 operation identity；新意圖必須新 key。POST A 晚到時，先查 A receipt；若只剩 B descriptor，回 no_pending(A)，絕不恢復 B。禁止 fallback 到 current pending。
- 同 key terminal 重試可在 descriptor 清除後回真結果，解決 POST 成功但 HTTP 回覆遺失。GET 附原 key 也可唯讀取回；不需要第二份 receipt index/history。
- GET snapshot 到 POST 之間可能完成、換頁或開始下一筆。server 每次重新比對；Web 以 document、session generation、查詢/操作 key 檢查回應。舊結果可被忽略，不能覆蓋 B 的 pending、dirty 或 candidate。
- available 證明僅限該 operation 的 terminal。它不證明兄弟 read、其他 writer、AI bindings／ToolMessage／manifest 已閉合；解除寫 gate 仍由 Task 5 同一完整 owner admission 判斷。每個 status 的 write_blocked 均來自此同一判斷；不能因 no_pending 或 available 在 client 單獨解所有鎖。
- 原正常執行仍活躍時，GET 只觀察；POST recovery 不搶跑正常 publisher。正常 attempt 依原有 timeout/cleanup 邊界結束後，才可取得後續一次恢復權。POST 不新增任意 manual cancel 模式。
- archive 阻止新意圖，不阻止對已 admission 原意圖讀 terminal／清理／failure closure。先 terminal、再精確 pending 恢復，不能先用 archived 拒絕，使未知永久卡住。archive 本身也不能解 gate。
- 全域 admission lock 不包住等待；同一 operation 的 POST 競爭只允許一個 attempt，其餘不排成多次自動 cleanup。不同文件可按現有 owner 獨立工作。

## 4. Web 行為與候選保留

掛載／pageshow 先做唯讀 manual discovery，與現有 metadata/run/head 讀取協作；若有本地 exact candidate，用其原 request_key 查詢，並且仍做一次無 key discovery 以辨識是否存在別的 current pending。這是有限兩次 GET，不是輪詢或歷史枚舉。無 candidate 只需無 key discovery。兩個 GET 依序取 snapshot，Web 以 document/session 與本地讀取序列丟棄晚到回應；mutation 開始時使較早讀取失效。掛載、pageshow、明示 refresh 及保存/恢復返回後取新 gate，未取得或讀取失敗先維持 blocked；只依最新有效 server write_blocked 決定 server gate，其他本地 dirty/candidate/忙碌限制仍保留。false 不直接授權寫入，真正 POST 仍核同一 admission。

unknown 必須有不依賴 candidate 的區塊，例如「上次人工保存結果尚未確認」，按鈕「確認上次保存結果」明示 POST 該 key；任何 status 只要 can_recover=true 都保留該原 key 的合法明示恢復／清理入口。available 的按鈕稱「清理上次保存狀態」，仍顯示真原結果；can_recover=false 不送清理 POST，容許唯讀重新整理，不一律將終局結果說成仍在保存。沒有 cache 時說明無法還原未保存候選，但可以確認原保存結果；不能把目前 JD 填成原候選。每次人工點擊只派一次 POST，fetch 不自動 retry。API 錯誤保留狀態；unknown 結束 spinner 保留入口。

- available committed/no_change：展示原 result；只在原 key 與 immutable cache submission 身分匹配時處理該候選確認。新 dirty 永遠保留，saved head 更新沿 Task 4 generation 防護，不盲目替換 editor。
- available terminal failure：展示未保存的真結果；有 candidate 繼續保留供檢視／明示捨棄；沒有 candidate 不能重建。不得把 failure 的 available 清成成功通知。
- no_pending：表示所查身分無 pending/receipt；不能清 candidate、標零寫入或自動重送。若持有完整 immutable exact cache，保留獨立的明示「再次送出同一份」動作，走原完整 manual-save，原 key/base/value 不變，server 重算／核原 digest；這可能是原意圖首次送達，不是 key-only 查詢／清理。無需先取得 not_admitted marker 才顯示此出口。write_blocked=true／gate 未知時禁用此提交，false 才可明示嘗試；本地 manualUnknown 不得單獨封死這個特定原候選出口，但普通新意圖保存仍受本地候選保護。GET absence 本身不是 admission 授權。server 先 receipt/digest，再核同文件 owner／pending 身分；原 POST 遲到、同 key 同時到達仍只能一份效果，不相符 payload 仍衝突。Task 4 明確 not_admitted marker 繼續按原流程處理，不能把 no_pending 當該 marker。無 exact cache 則不能重建提交，保留原診斷限制。
- recovery HTTP 409/422/503 或網路中止：只代表本次操作失敗/未獲准/未知；不使用 `ManualSaveRejection` 的判定邏輯、不丟 cache。即使 HTTP abort，也不取消 server 工作。下次唯讀按原 key 查詢。

load 的自動 `save(true)` 不再用於未知狀態。終局 receipt 可由 GET 查回；exact cache＋no_pending 的未確認情境與既有明確 not_admitted 候選都保留另次明示完整提交，前者不宣告原先未執行，且不要求不存在的 rejection 證據。新 pending／active owner 存在時仍依 server gate 阻擋完整提交，改走匹配身分的有限恢復；不讓 key-only recovery POST 承擔保存，不新增持久候選 store。

## 5. 契約與 implementation 接合範圍

- 在 actual `jd_routes.py` Pydantic 定 request／含兩個共用必填布林的 discriminated response DTO，回 available 的 result 引用既有 generated `JdManualSaveResult` 型別；只在 mapper adapter 中轉換內部結果。domain 不 import 新 transport DTO。
- 將實際 DTO 納入 `scripts/export_web_contract.py` 的 TypeAdapter union，經既有 codegen 生成 `analysis-api.ts`；Web `api.ts`／session 直接引用。不得另手寫 TypeScript response union、建立新 JSON Schema SSOT 或修改 generated 輸出當來源。
- JD core JSON Schema、edit/read/change_read 的 model shape／strict 設定完全不改。這個 App-only route 與接受 Task 4 `ManualSaveRejection` 的生成方式一致，沿 contract-strategy 的單一跨語言來源原則，無第二份 authority。
- service／root／store 只沿 Task 5 已採 owner、descriptor、reconcile_after_writer_stopped／failure closure port；HTTP router 不擁有 subprocess、不直接自行實作 PG proof、不新增表或 Saved History。
- Task 5 Files 還需明列 `scripts/export_web_contract.py`、Web `src/jd/api.ts` 與 generated `analysis-api.ts`；新增 DTO/route/session focused tests。其餘已列 jd_routes/service/root/store/Web 接點足夠。

## 6. 有限驗收（規格，未執行）

| ID | 可觀察條件／反例 | 必须結果 |
|---|---|---|
| MT01 | cache 遺失、root pending、Node 未清 | 無 key GET 回原 key unknown；UI 有独立恢復入口；GET 零 cleanup／checkpoint write／Node／模型。 |
| MT02 | manual 正常 active 或 publisher 尚運作 | GET can_recover=false，POST 409；不把 readback 當 stop 或 known-none。 |
| MT03 | 只剩同程序 retained handle，第一次恢復仍 unreaped | 一次有界 cleanup、unknown、spinner 結束、同 handle 仍在；無自動第二次，無 failure receipt／候選 publish。 |
| MT04 | 另次明示清理成功、原 SQL 結果不明 | 依原停止證據與 PG barrier；原 receipt 返回，或 verified known-none 寫原 failure；無重跑 candidate。沿 NL07/09/10 fixture，不重造 proof。 |
| MT05 | terminal commit 回覆遺失、descriptor 已清 | GET/POST 原 key 回相同 available/result；no_pending 不可替代真結果。 |
| MT06 | terminal receipt 有值但 descriptor clear 失敗或其他 owner outstanding | ①available + matching descriptor clear失敗：write_blocked=true、can_recover=true，結果可讀、保存禁用、另次明示清理可重試。②available/no_pending + 只有其他owner未閉合：write_blocked=true、can_recover=false，舊key不能清他人。③本key清完仍有其他owner則仍blocked；全部閉合後下一有效snapshot才false。 |
| MT07 | A snapshot／POST 晚到，B 已 pending；包含不同 document | A 只回 A receipt 或 no_pending(A)，不能操作 B；UI 不覆新 draft／候選／狀態。 |
| MT08 | 兩個同 key recovery POST 同時到達 | 只有一個 attempt 取得 owner；另一個 409 或已存在 terminal，不重複 cleanup/發配新意圖。 |
| MT09 | archived + 原 terminal；archived + 原 pending | 原結果可讀；已 admission 恢復可走；archive 仍不允許新保存，也不代替停止。 |
| MT10 | GET/POST DB失敗、descriptor壞、receipt absent、HTTP abort | API錯誤和 unknown/no_pending 分清；不丟candidate、不解gate、不稱零寫入；原server工作不因abort當停止。 |
| MT11 | terminal failure／success／no_change + cache有無／新dirty | 原 result 分清；無fake candidate；失敗候選保留；新dirty不被覆蓋。 |
| MT12 | actual Pydantic schema 與 Web build／生成check | 每個status共用write_blocked/can_recover必填且由actual DTO生成；新union可判別、UUID/extra一致，Web無手寫平行response或gate policy；三工具request shape完全不變。 |
| MT13 | exact cache已寫，原POST到server前中斷，重開GET no_pending | 無自動POST、不稱零效果、不要求not_admitted marker；顯示明示完整原候選出口，gate開放才可嘗試，沿原key/base/value成功或真typed拒絕。原POST遲到／兩個同key完整提交仍只有一份效果；gate blocked時不可繞過。 |
| MT14 | GET snapshot晚到／保存或清理後gate刷新失敗 | 舊snapshot不覆新draft／pending或解鎖；失敗維持blocked，不從available/no_pending猜gate；下一有效同server投影才可解除server鎖。 |

只跑這組新增 transport/session 反例及 Task 5 原定整合回歸；Task 1–3 已接受基底不為此重跑。Windows/PG 真證據仍由原 NL 驗收，HTTP mock 不代稱停止或交易證明。本輪未執行任何測試，無 implementation verdict。

## 7. root 採用時需同步的精確文句

1. journey §6.2 原 manual「不新增 route／結果枚舉」改為：manual-save exact submission 與模型工具契約不變；為已採 cache-lost 效果新增 App-only GET/POST manual-recovery，唯讀原 key 發現／原 receipt，以及另次明示一次對帳，不重跑 candidate。§7 加原 pending 恢復與 receipt 都先於 archive 阻擋新意圖；§9/J05–J08 引 MT race。明列 exact cache＋no_pending 可另次明示原 key 完整 manual-save，可能首次送達，不自動、不宣告零效果；每個 recovery status 都回同 admission 的 write_blocked/can_recover，終局待清仍有匹配 key 清理入口。
2. lifecycle §4.2 補明示恢復的 HTTP 接點與 active attempt 不可重入；§6.4–6.5 補 browser 只傳原 request_key、server 取可信 descriptor digest、terminal 後同 key 可查原 receipt及重試匹配descriptor clear；所有status回同完整admission gate／該key恢復能力，不能清其他owner；§7 Task 5 Files 加 actual DTO export、generated Web及api wrapper；不改停止／PG proof。
3. core plan Task 5／brief §5.1、5.4、5.5 加 MT01–14 與上述 Files；Task 4 已接受結果保持歷史原貌，只說 load unknown 行為由 Task 5 接替。
4. Proposed ADR0074 Decision 7 lifecycle/manual identity 段補「App-only 原key唯讀發現及一次明示恢復；key-only恢復不重跑candidate或新增authority；exact cache無pending可另次明示完整原意圖送出」，Consequence 補必要兩方法、同一admission gate／原key清理能力投影與生成 DTO seam；維持 Proposed／隔離採用／production gate不變。
5. current register 將唯一 transport blocking question 記為窄 review 結果與採用路由；本稿尚不能自行當 durable adopted 設計。

## 8. 證據及限制

主要既定來源：`docs/specs/2026-09-10-jd-native-process-lifecycle-design.md` §4.2、§5、§6.4–6.6、§7–8；其 `evidence/2026-09-10-jd-native-lifecycle-review.md` closure；`2026-09-10-jd-employee-journey-design.md` §6.2／7／9；`docs/contract-strategy.md`；接受 Task 4 原碼如 §1。lifecycle §3 已保存 Python subprocess／Microsoft Job Objects 官方依據；journey 已保存 browser abort 不等於 server stop 的 MDN 證據。本文只延續這些停止與 identity 不變量，未重查或更改官方 OS 契約，亦未作新的 HTTP framework 能力假設。

已知限制：無 cache、無 descriptor 且無 receipt 時，沒有資訊能憑空還原原意圖。正常 admitted manual 由 before-Node durable binding 保證可枚舉；若該保證遭破壞，保持診斷與安全 gate，不能用 transport null 偽造修復。本稿閉合的是已保存 identity 的 transport，沒有宣稱任意資料遺失都能自助恢復，也沒有改成外部維運服務。
