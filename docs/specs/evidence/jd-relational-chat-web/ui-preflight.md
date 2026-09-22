# 同頁聊天與已保存 JD 改動：Web 接合前置

- 查閱日：2026-09-13；Topic：JD-R002／RS-4 局部；狀態：**有界研究與可採設計建議，未實作／未驗收此聊天 Web**。
- 範圍：聊天輸入、原回合查回、執行／收尾／恢復、唯一結構 JD、CV-01 改動可見性、HR-02 接點。只寫本文件，0 provider；不安裝套件、不執行 DB／瀏覽器／模型，不更動欄位及保存責任。
- 有效需求：[CV-01 已選 A](../../2026-09-12-jd-change-visibility-design.md)、[HR-02 整輪 JD 撤回](../../2026-09-12-jd-ai-turn-undo-design.md)、[完整同頁旅程](../../2026-09-13-jd-complete-app-journey-design.md)。現況依[聊天 HTTP 結果](../../2026-09-13-jd-chat-http-slice.md)及實碼；舊研究的當時未完成事項不覆寫目前實作。

## 1. 可採結論與完成界線

在既有 `DocumentWorkspace` 同頁放入真正的訪談區，右側沿用唯一六章 `JdEditor`。聊天回覆、使用者原話是否保存、JD 修改是否保存分別顯示；AI 可直接寫入，不新增逐項接受、專業核准或第二份可編輯稿。原 run 的狀態／歷史可讀，不因新 AI 尚未啟用而一併封鎖。

第一片建議不用新增 Query 庫：由每份文件的一個聊天觀察入口共享 GET 結果，沿用目前的 API／草稿責任，補有界查回即可。這是依目前共享資料需求作的技術取捨，不是指定繼續擴大既有 `JdSession` 類別。§6 明列新增庫的收益與代價。

**CV-01 仍有實質後端接點缺口。**目前 HTTP 可讀每次 operation 的完整差異，尚無完整一輪 S→E 淨差異的 envelope／查詢。只完成 ChatPanel、聊天摘要、歷史入口，不能宣稱 CV-01 完成。既有 App 純比較可重用，最短補法見 §4。HR-02 已選需求保持；撤回服務與資格核查尚未落地，不把「取消」當撤回，也不先掛一個會假成功的撤回按鈕。

## 2. 官方互動行為：可借用的效果與不能推導的事

以下都是官方公開介面資料，不是它們的內部保存、執行或 Memory 架構證明；產品服務也不因參考而成為本案依賴。

| 官方來源，查閱日均為 2026-09-13 | 核實內容 | 本案映射／限制 |
|---|---|---|
| [ChatGPT Release Notes：2026-05-28](https://help.openai.com/en/articles/6825453-chatgpt-release-notes) | GPT-5.5 Instant／Thinking 不再提供 Canvas，寫作與程式內容轉由聊天內 writing／code blocks 承接；舊模型只曾有暫時保留安排 | 不能把 Canvas 說成目前所有 ChatGPT 模型的通用介面，也不能由舊指南斷言現在仍有某一舊模型可用。本案同頁工作稿源於已確認需求，並不依賴 Canvas 的現行供應狀態 |
| [Introducing Canvas，2024 歷史公告](https://openai.com/index/introducing-canvas/) | 曾展示直接編輯、選取局部取得回饋及返回前版的互動 | 只保留為歷史互動參考，不據此新添本案選區能力／還原能力，亦不稱它是當前可用性證據 |
| [Codex Code Review](https://learn.chatgpt.com/docs/code-review) | 工作區變更可在 review pane 查看；提供不同 Git 比較範圍、局部評論及後續聊天 | 支持「完成修改後仍能另行查看確切差異」的效果。其工作區差異可能含人工及其他來源，不能直接當本案某個 AI run 的唯一歸屬；Git stage／revert 也不是 JD 的接受／撤回契約 |
| [Claude Artifacts：Edit and iterate](https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them) | 能要求修改、選取 Markdown 局部使用 Edit with Claude、直接在 artifact 編輯並切換版本 | 支持持續修訂及同處查看。文件關於 Claude 記憶原內容的說明，不能代替本案已批准的 Memory／JD 單一權威設計；不由此假設我方已有選區工具接合 |
| [Claude Code Desktop：diff view／permission modes](https://code.claude.com/docs/en/desktop) | 改後可由差異統計進入內容及局部評論；Accept edits、Manual 等模式分開 | 不能聲稱大廠一律逐次接受，亦不能聲稱所有工具都自動核准。本案 AI 直存沿 Owner 既定選擇，不搬入 Manual 模式的審批流程 |

跨來源只能得出有限共同點：對話可與工作產物連在一起，細節可按需查看，不同產品／模式的接受與保存方式不相同。沒有資料支持它們共用本案的版本、回執、停止證明或資料表設計。Canvas 舊說明頁本次讀取失敗，沒有繼續重試；現行可用性改用上述成功讀到的官方 release notes 核實，不以搜尋摘要或社群貼文代替。

## 3. 本地現況與最小 UI

### 3.1 已有接點

| 本地責任檔 | 已有能力 | 本次仍須接合 |
|---|---|---|
| [DocumentWorkspace.tsx](../../../../experiments/jd-relational-app/web/src/components/DocumentWorkspace.tsx) | 同頁左右欄、文件標題／封存、手動保存狀態、歷史開關、唯一 `JdEditor` | 左欄仍為 AI 接合中的提示；沒有真正聊天、原 run 狀態及重開保護。現有離頁提示只涵蓋手動草稿／提交 |
| [HistoryPanel.tsx](../../../../experiments/jd-relational-app/web/src/components/HistoryPanel.tsx) | 每次原操作完整前後內容、移動／順序／引用／來源的唯讀對照 | 目前由面板內部選 revision，需接受外部選定原 `change_ref`／run 上下文；沒有整輪淨差異或目前稿標記 |
| [JdEditor.tsx](../../../../experiments/jd-relational-app/web/src/components/JdEditor.tsx) | 六章手動 CRUD、各項多行文字、穩定 item／field DOM 定位、IME 接點 | 加純呈現的具名變更標示；不再建第二份編輯 state 或在 Web 重算 domain 規則 |
| [session.ts](../../../../experiments/jd-relational-app/web/src/lib/session.ts)、[api.ts](../../../../experiments/jd-relational-app/web/src/lib/api.ts) | 手動草稿與原 request 的保存／對帳、API 固定錯誤及 schema 驗證、完整分頁 read | 聊天 schema／方法、與手動交接的明確結果、聊天原 request 草稿保護及一個 GET 觀察入口。`flush()` 可能因 IME／review 等條件提前返回，不能僅 `await flush()` 就推定已乾淨可送 |
| [chat_service.py](../../../../experiments/jd-relational-app/src/jd_relational/chat_service.py)、[Chat HTTP SSOT](../../../../experiments/jd-relational-app/contracts/jd-chat-http.schema.json) | `run_status`、`input_state`、`stop_requested`、`write_state` 與 `jd_effects` 分離；GET 原 run、原話歷史、取消／恢復 | Web 應直接消費生成型別及正式 schema。`jd_effects.state` 是 `settled`／`unconfirmed`；每筆結果自己的 durability／effect 另判，不能用「模型完成」推定保存 |

### 3.2 輸入、送出與原請求

聊天輸入採有標籤的純文字多行欄，保留換行與原文。第一片用明確「送出」按鈕；Enter 保持換行，繁中組字時不觸發送出。若後續加快捷鍵，須另核 `isComposing`／composition end 的事件先後，不把鍵盤事件當已保存證據。AI 執行時可保留使用者正在寫的下一段草稿，但不自動排隊送出。

新送出前先完成／明確處理手動未存內容及結構表單，再使用最新可寫引用建立原請求；不能自動把未完成表單當正式內容。原 `run_id`、使用者原文、expected revision、dataset／document scope 在 HTTP 前持久保存。收到不確定結果、重開或重試時沿同一原請求查回，不偷偷換新版次或另生 key。輸入是否已保存只依 `input_state`；不要 POST 一發就清掉唯一草稿。送出期間晚打的下一段不應被前一段 ACK 清除。

舊對話從固定 root/source 歷史頁讀取並依原 cursor 續頁；已載入頁保留其 anchor，不能混入新 root 再假稱完整同一頁。未確認的原輸入可以顯示為「正在確認是否收到」的本機待確認列，不能先冒充已保存 HumanMessage。完整 AI 回覆以真實 `response_message_id`／歷史內容配對，不把系統、工具或執行通知寫成使用者原話。

### 3.3 最小狀態文案與可用動作

下表是呈現建議，不增添 HTTP enum；所有編輯可否進行仍由 `write_state` 決定。

| 已知事實 | 建議顯示／動作 | 不可推論 |
|---|---|---|
| POST 回覆遺失／逾時，原 run 未查定 | 「正在確認這段是否已收到」；以原 ID GET；保留原請求及草稿 | 等待逾時不等於未存、不等於可以新 key 重送 |
| `running` | 「AI 正在整理」；可取消；目前 JD 仍可讀，手改隨 gate 暫停。收到個別 confirmed commit 可更新乾淨的目前稿與提示 | 已有一筆 commit 不等於整輪已結束或效果全集已確定 |
| `running` 且 `stop_requested` | 「已請求停止，等待安全結束」；防重複點擊，繼續查回 | 請求取消不等於 SQL 停止，也不撤回已保存修改 |
| `closing` | 「正在確認保存並收尾」；仍可看已知 JD／差異，依 gate 等待 | 不再標成模型仍在生成；不能直接解除手改鎖 |
| `recovery_required` | 保留原回合，提供「確認原回合並完成收尾」的明確操作，呼叫原 recover 路徑 | GET 本身不恢復／不續跑；recover 不等於再呼叫模型 |
| `completed`／`cancelled`／`failed`，原文已保存 | 原文保留，狀態如實顯示，另列原 JD 結果。例：「回覆未完成，但以下 JD 修改已保存」 | failed 不等於 SQL 全部回滾；cancelled 不等於 JD 沒變 |
| 沒有 committed 操作且效果全集已 settled | 「本輪沒有修改 JD」；保留正常訪談內容 | 不創造空版本或假的變更卡；有 A→B→A 事件時不能使用此話術 |
| `not_found`／輸入未確認 | 「尚未查到原回合，結果仍待確認」；保留原 envelope，提供查回 | 空查詢結果不是已證明未執行，不能自動改用新 run |
| 明確 `input_state=not_saved` | 保留可修正草稿，顯示這次未保存；後續新送出依原請求狀態規則辦理 | 不把 HTTP／網路一般錯誤一律轉成 not_saved |
| `ai_unavailable`（503，`stop`） | 「AI 訪談尚未啟用；輸入已保留，目前仍可手動編輯與查看原有對話」；不自動重試 | 目前是日常組合明確未啟用，不一概說缺金鑰或服務壞掉；不自行增加付費／模型設定流程 |
| dataset 改變或其他查詢失敗 | 保留 scoped 本機資料及上次已知結果並標示未更新，走既有安全錯誤出口 | 不跨 dataset 使用舊引用；不以新 head 改寫原 request |

## 4. CV-01 整輪淨差異：真正缺口與有界補法

CV-01 已選 A 的必要效果是：目前稿欄位／項目有具名標示，同頁按需展開確切差異；刪除、移動及引用有明確持續入口。正常連續一輪預設看 S→E，仍可展開全部已保存事件。改了又改回須顯示「沒有淨變更，但有保存紀錄」。只顯示聊天摘要或一個泛用歷史按鈕不足以承接這些要求。

### 4.1 已有可重用能力

- [changes.py `compare_snapshots`](../../../../experiments/jd-relational-app/src/jd_relational/changes.py) 已接受兩份完整 v3 snapshot，先嚴驗同文件，再以穩定身分比較完整欄位、建立／刪除、搬動／相對順序及關聯，保留受影響任務。它是 App 純比較，不讀 DB／model，不重建 operation 時序，也不產生可執行 patch；用於任意兩份同文件已驗 snapshot 本身不要求版本相鄰。
- [change_reads.py](../../../../experiments/jd-relational-app/src/jd_relational/change_reads.py) 已共用普通 JD 讀取投影，含完整 before／after、位置／相鄰引用、來源及字節分頁。**公開 `ChangeReadService.read` 明確只接受一筆 committed receipt，並核 result 的 parent／producer 屬於該原 operation。**現有 envelope 必填單一 `operation_ref`，不適合假裝成整輪結果。
- [read v2 SSOT](../../../../experiments/jd-relational-app/contracts/jd-read.schema.json) 已有 `ItemRecord.item_id` 與六種 `SectionRecord.section_key`。Web 可在相同 dataset／document 下，以 item ID＋field name／section key 對應 DOM；refs 只作版內關聯與定位，不 decode，也不能用名稱、文字或序號匹配重複項目。
- [原 run SQL 操作查核](../jd-relational-chat-http/operation-results.md) 及 native bindings 已有原操作全集／原順序的接點。SQL 查詢的 UUID 排序不是交易執行順序；terminal exact set 與 active 尚未確定分開，不應在前端另建一份歸屬清單當權威。

### 4.2 推薦最小 App 接合（尚未實作）

1. 新增固定 **run 唯讀淨差異** 的小服務／外部契約，輸入可信原 run identity，沿原生 bindings 與既有 SQL receipt 查核取得原 committed 操作。只在能證明完整範圍時稱完整一輪；active 顯示已確認事件及仍在整理，不能把當前 prefix 標為最終 S→E。
2. App 核每筆 scope／origin／原 base-result／revision parent 鏈，從第一筆 committed base 得 S、最後一筆 result 得 E；no_change／失敗仍可列結果但不進內容鏈。中間插入其他來源或鏈不連續時，明示無單一連續淨範圍，只保留原操作列表；不能把間插的人工作業歸給 AI。
3. 從既有歷史 reader 取不可變 S／E snapshot，直接用 `compare_snapshots`。抽出已存在的差異 record／side 投影供兩個 reader 共用即可；不複製 domain、不增加通用比較任意文件 API，也不讓 Web 比較兩份 JD 自行推導業務事件。
4. 整輪 envelope 有自己的 run 身分、S／E 歷史引用、範圍完整性及原操作事件入口；以正式 SSOT 生成，重用現有可共用 record defs 及分頁機制。**不能虛構單一 operation_ref／change_ref**，也不改 `jd_change_read` 的原操作語意。這個契約需由實作者明確落定，本文不手寫第二份 DTO。
5. Web 以 App 淨差異記錄加具名標籤，點擊開同頁 before／after。刪除項目保留在本輪區，不塞回目前稿；移動／引用／共享 K/S 的影響任務照 App 回傳。即使淨差異為空仍可展開原保存事件。
6. 較晚 head 前進後清除該舊輪目前稿欄位標示，保留「這輪當時的改動；目前稿已有後續修改」及原 S／E／事件入口。舊歷史不可重新解析成目前可寫 refs。判定 head 相等不能只比較文字或 digest。

先接逐次事件列表是一個可驗施工步驟，但不是將 CV-01 降為方案 C。若本單位先停在此，交付需明列整輪淨差異及目前稿標記未完成；不可改寫已選需求來消除缺口。

### 4.3 HR-02 保留邊界

HR-02 是符合資格時整輪撤回 JD，不是每輪必按接受。原話、Memory、案例及原保存紀錄保留。現有每次差異、run receipt 或純比較都不足以授權還原：仍需服務核完整連續鏈、目前 head 正是 E、沒有較晚 JD 修改及待處理手稿等，再用新的明確原子意圖保存。尚無此服務時不提供可操作的撤回承諾；取消／收起差異／查看歷史都不代做撤回。

## 5. 沿目前 MUI／Next 的元件接點

本次不升級。已安裝 Next 16.3.5、React 19.3.0、MUI Core 9.4.0；MUI package 明列 MIT。[前次精確版本研究](../2026-09-13-jd-react-ui-preflight.md)與 [web package.json](../../../../experiments/jd-relational-app/web/package.json)承接其餘 peer／建置依據。下列元件皆為免費 Core；無付費 Grid、AI SDK／聊天套件需求。

| 接點 | 官方／本地依據 | 本案用法 |
|---|---|---|
| 多行輸入、原生 ref／事件 | [TextField](https://mui.com/material-ui/react-text-field/)；本地 `TextField.d.ts` 的 `multiline`、`inputRef`、`slotProps.htmlInput` | controlled string，保留原生 textarea 的 selection／composition 入口；本片不因此宣稱 `jd_replace_selection` 已可用 |
| 送出／取消 | [Button API](https://mui.com/material-ui/api/button/) 的 `loading`／disabled | 明確按钮與可存取名稱；只用已知進行狀態阻止重送，不把 loading 當 SQL 停止證明 |
| 執行／收尾提示 | [Progress](https://mui.com/material-ui/react-progress/) | 具名不定進度；沒有可靠百分比就不捏造數字。依實際 phase 切換整理／確認保存文案 |
| 持續錯誤／改動入口 | [Alert](https://mui.com/material-ui/react-alert/)、既有 Paper／Typography／Button | 重要狀態保留在頁內；一般狀態用 `role=status`／溫和播報，避免每次查回都重播 assertive alert 或搶焦點 |
| 非關鍵短提示 | [Snackbar](https://mui.com/material-ui/react-snackbar/) | 可用於短暫輔助回饋；不能作為唯一保存證據、唯一改動入口或唯一恢復提示 |
| React 互動邊界 | [Next Server／Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)、[use client](https://nextjs.org/docs/app/api-reference/directives/use-client)；本地 bundled 同名文件 | composer／狀態觀察在 Client Component；供應商、owner、DB／回執 authority 留在既有 Python 服務，不搬到 Next 或 browser |

已讀 [web/AGENTS.md](../../../../experiments/jd-relational-app/web/AGENTS.md) 及目前安裝 Next 的 `dist/docs/01-app/01-getting-started/05-server-and-client-components.md`、`03-api-reference/01-directives/use-client.md`、`02-guides/client-side-data-fetching/index.md`。繁中 composition 的細節沿前次官方研究及目前 `JdEditor` 接點，最終仍須真瀏覽器證偽。歷史／狀態更新不得重掛輸入 DOM、重置焦點或移走選區；窄畫面可改上下排，但仍在同頁看 JD 與聊天。

## 6. 只讀查回要不要新 Query 庫

[Next 目前指南](https://nextjs.org/docs/app/guides/client-side-data-fetching) 將 SWR／TanStack Query 的用途說成共享 browser cache、焦點回查、間隔查詢及跨元件 dedupe 等能力，不是所有客戶端請求都必須有新庫。其 browser cache 與 Next server／RSC cache 各有生命週期，身分及更新失效仍要協調。本案已經是 Python API，沒有理由為此新增 Next server cache 或 Server Action 保存權威。

| 本次資料 | 必要共享／生命週期 | 最小責任 |
|---|---|---|
| 一份文件的原 run 狀態 | 同一結果給聊天提示、按鈕、JD gate 及改動入口 | 一個 observer／hook 或 controller；不可每個呈現元件各建輪詢 |
| 原對話歷史頁 | immutable anchor＋cursor；按需補頁，原頁不混版 | API 完整驗 schema，頁序合併沿原 cursor；切 dataset／document 清理視圖 scope |
| 目前 JD＋手動草稿 | 目前 server 版與本機未存內容並存，不能以快取值覆蓋草稿 | 既有 JD session 維持草稿／寫入交接責任；聊天僅請求安全刷新及接收 gate |
| 原聊天 request／輸入草稿 | 跨重開、回覆遺失、晚打草稿，含原 key／expected revision | 明確本機持久記錄及 ACK 規則，不交 Query cache 當原請求 authority |
| POST start／cancel／recover／JD 修改 | 具有原意圖與效果；網路結果可能未知 | 明確命令控制及查原結果；禁止 library 自動 mutation retry |

**推薦首片不加庫，另保留一個窄的只讀 observer。**目前只有一個 `DocumentWorkspace` 需要主動取得該 run，其他都是其 props 消費者，尚無獨立重複 query／多份共享 cache 的實際需求。observer 只管單飛 GET、每次請求 deadline、舊世代回應隔離、進行中有限查回、停止／離頁清理；terminal／明確讀取錯誤停止自動查回並提供明確重查。焦點回來可做一次新 GET，不能自動 start／recover。有限自動觀察的時間／次數預算由實作定型並驗，超出顯示待確認及手動查回，不由 elapsed time 改寫 run 事實。

SWR／TanStack 的收益是現成 focus／poll／dedupe／shared cache；代價是新依賴、QueryClient／provider、完整 dataset＋document＋run＋anchor＋cursor keys、預設 retry／freshness 的審核，以及與 JD 草稿刷新／失效的接合測試。它們不替本案保存原 request、核 SQL receipt 或判安全收尾。若實作發現多個獨立消費者確實共享同一查詢，或需手寫同等通用 cache／dedupe，應在該證據下採一個庫，停止擴充自製 observer；不需現在預先裝兩個比較。未安裝候選本輪不指定版本／不聲稱已驗相容。

## 7. 有界驗收清單（本文件未執行）

| 情境 | 必須觀察的結果 |
|---|---|
| 繁中組字＋多行、送 A 後繼續打 B | IME 不誤送；原文換行不變；A 的保存 ACK 不清掉 B；狀態刷新不丟焦點／選區 |
| 有未存欄位或未完成新增任務表單時送出 | 先明確處理手稿；不冒用 flush 返回當成功；不靜默半存表單或讓 AI 以舊版准入 |
| 純訪談完成 | 原話及完整 AI 回覆可重開；JD 不生空修改／版本；回覆配對不混原 run |
| AI 已 commit，再於最後回覆失敗 | 頁面同時呈現失敗／原文已存／JD 已存修改；目前稿及原差異保留，不標全部回滾 |
| 同輪多次修改、A→B→A、刪除／移動／共享 K/S | 預設真 S→E；可展開所有原事件；改回不丟事件，刪除有入口，重複名稱仍對應正確 item ID |
| 舊輪之後手動修改 | 舊輪目前稿標記清除，原 S／E 差異仍可讀；較晚人工內容不被標成 AI；不提供不合資格撤回 |
| 取消、closing、需要恢復 | 停止請求不假成功；closing 不顯示模型生成；手改依 gate；GET 不執行恢復，明確 recover 不續跑模型 |
| POST 回覆遺失後重開、GET 暫時 not_found | 先用持久原 run 查回，原 body／expected revision 不變；無新 key 重送或 GET 重播；scope 改變不能借舊引用 |
| ai_unavailable 與既有對話 | 新輸入保留、無自動 retry；手動 CRUD 與原對話／原 run 仍可讀，不暗示已啟用真模型 |
| 狹窄畫面、鍵盤、輔助技術及查詢過時回覆 | 同頁入口可達、關鍵提示不只短 toast；無連續 alert／焦點跳走；換文件或 disposed 後舊回應不覆蓋新 view |

測試層次應分開：純 observer／持久 request 狀態及 schema 反例；真瀏覽器以固定 SSE／MockTransport 接原 HTTP／PG 驗 UI；最後才是另獲授權的真模型／真人內容品質。本研究不追加、不合併既有離線／PG／瀏覽器數字，也不宣稱本輪已有自然訪談、Memory、來源／選區完整接合、HR-02 或完整 App 驗收。
