# Web 工作畫面與 JD 編輯接線

本頁維護現行 Web 工作畫面的組裝、JD 人工編輯、局部草稿與待確認命令接線。正式稿、版本與寫入資格由 [JD 保存](jd-storage.md)負責；HTTP、公開串流、來源回查與本機交付沿[介面與交付](interface-and-delivery.md)。正式產品依 [正式產品與選型](../architecture/design-decisions.md)，既有行為與驗證限制隨原證據保留。

修改欄位或保存恢復先讀[共同編輯規則](#1-基本資料編輯的讀取基底與恢復)，再選對應項目。畫面與導覽看[工作畫面組裝](#5-工作畫面組裝)，鍵盤、就地修改與元件分工看[逐欄編輯](#6-逐欄就地編輯)。視覺數值仍由程式的 theme 與 CSS 維護。

## 1. 基本資料編輯的讀取基底與恢復

[JD feature](../../apps/web/src/features/jd-editor/JdProfileEditor.tsx)讀取正式 profile；四欄文意沿 [JD 指南](../standards/work-analysis/2026-09-09-jd-field-and-writing-guide.md)，不含檔案名稱／員工姓名。後端交易與固定修訂由 [JD 保存](jd-storage.md)負責；此處只描述畫面接線，不另維護 wire schema。

四欄與其他文字一樣點一下就地逐欄修改（[§6](#6-逐欄就地編輯)），每個欄位各自捕捉讀取基底並套用以下保存保護：

- 點欄位開啟就地編輯器時捕捉讀到的修訂及正文；草稿是局部 component state。背景 GET 即使取得新版，也不替換已開啟編輯器的基底或尚未送出的文字。切檔用檔案 ID 作 component key，查詢也帶檔案與 formal 用途。
- dirty 判斷與送出版本共用上述開啟基準。背景改稿不使未動的草稿變成修改，也不因草稿恰好等於新版文字而忽略使用者原本的修改意圖；是否可採用仍由後端核對原 revision。
- 每次儲存只送這一欄的變動；刪空明確 clear（四欄都可以未知），未改不送、直接關閉；只有空白或非法字元拒絕。命令先保留於本分頁、該檔案的 sessionStorage，再 POST。儲存暫存失敗不發請求，連線等待期間禁止重複提交。
- 不明結果保留原命令／原基底／原 changes，編輯器與其他編輯控制項暫停；重開或 reload 後可重新確認同一命令。這不是第二份正式 JD，也不保證關閉分頁或清除瀏覽器資料後仍能取回未確認命令。
- 明確拒絕不自動改基底重送；保留畫面草稿供辨認，要求讀目前 JD 再決定。原命令成功確認後關編輯器，invalidate 並 GET 目前正式稿；舊操作回傳不直接寫入最新 cache。
- 讀取失敗不當空白 JD；取消未送出的編輯只是放棄局部草稿，關閉結果未確認的編輯器也不是撤銷後端效果。未知欄位顯示「尚未提供」，不表示已確認沒有。人工寫入本身不等於員工事實或依據核對完成。

profile、`WorkCommand`、建立及改名共用 [pending-command store](../../apps/web/src/shared/commands/pending-command.ts)與 [useStoredCommand](../../apps/web/src/shared/commands/use-stored-command.ts)，集中保存、條件式 ACK、單次送出與已知／未知結果分類。各命令保留原儲存鍵及 schema；profile 與 work 仍各有自己的待確認 slot，互不覆蓋。

[jd-commands](../../apps/web/src/features/jd-editor/jd-commands.ts)提供 JD 的 validator、完整命令比對、POST、正式拒絕分類及畫面結果投影。共用 hook 不持有草稿或 JD 版本規則；原命令已被替換、ACK 清理不可用或刷新失敗時，保留已知後端結果並顯示相應提示，不再送新命令。持久 ACK 與刷新在卸載後仍完成，只有仍掛載且結果可供目前畫面採用時才執行完成回呼。

刷新由 [workspace-refresh](../../apps/web/src/app/workspace-refresh.ts)組裝：人工 JD 修改讀回 profile、work 及來源；訪談完成另讀回正式訪談；撤回另讀回原 Turn。各 feature 提供自己的 query options／範圍，JD 編輯器與訪談完成元件接收具名刷新 callback，不知道其他 feature 的 query key。來源使用自己的 `jd-sources` key，不依附 profile prefix。[refreshQueries](../../apps/web/src/shared/api/refresh-queries.ts)集中先 cancel、再 invalidate 並傳遞讀取錯誤，避免首次尚無 data 的慢 GET 被沿用為保存後結果；建立、改名、刪除清單、串流重連與終態 Plan 也沿同一機制。Plan 仍依原 execution 合併同時的終態讀取，並明確等待新資料，沒有另造 cache。

JD 的正式拒絕只採已核對原命令後的 `409` 公開碼，以及相應集合的目標不存在／知識技能仍被引用錯誤。前置 schema／`invalid_*_change` 驗證、一般 `404`／`422`、未知碼或非 JSON 都不能否定先前可能已提交的操作，仍保留原命令。回傳成功與畫面刷新成功分開：來源或 JD GET 失敗不能讓已成功 POST 變成未知，也不能自動再送一次。

採用 [React 的 state／key 生命週期](https://react.dev/learn/preserving-and-resetting-state)及 [TanStack Query 的 mutation invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/invalidations-from-mutations)。以上原命令／基底保護是本案契約，不是 React／cache 自動提供交易原子性。沿用既有 HTTP 驗證，不新增全域表單 store 或雙寫保存服務。實測見 T03 evidence §4；職責／任務見 [§2](#2-職責與任務的人工編輯)、知識／技能見 [§3](#3-共用知識技能及任務關係的人工編輯)、協作／條件見 [§4](#4-協作對象與共通條件的人工編輯)、候選與來源見 [§5](#5-工作畫面組裝) 及 [介面 §3](interface-and-delivery.md#3-顯示與來源)。

## 2. 職責與任務的人工編輯

[JdWorkEditor](../../apps/web/src/features/jd-editor/JdWorkEditor.tsx)組裝職責、任務及未歸屬區。[WorkDialog](../../apps/web/src/features/jd-editor/WorkDialog.tsx)負責新增任務、知識／技能、協作對象與條件的表單（[TaskFields](../../apps/web/src/features/jd-editor/TaskFields.tsx)等），以及刪除確認；新增職責使用清單末端的 [AddArea](../../apps/web/src/features/jd-editor/AddArea.tsx)就地列。

既有項目沒有整項編輯表單：文字[逐欄修改](#6-逐欄就地編輯)，搬移用「移到…」選單，成果／要求用「+」新增、× 移除。[workCommand](../../apps/web/src/features/jd-editor/jd-commands.ts)管理本檔案、本分頁的一筆待確認集合命令，恢復規則共用 [§1](#1-基本資料編輯的讀取基底與恢復)。接線沿既有 MUI、Query 與 HTTP guard，不增設 form store 或拖曳框架。

- 畫面使用[同版組合讀取](jd-storage.md#23-組合畫面使用同一修訂)，開表單或就地編輯器時固定當時內容／基底。profile 與集合修改後互相 invalidate，因為兩者共用 JD 修訂；正在重讀時不讓新表單取已失效 cache。已開啟草稿仍不被背景更新覆蓋。
- 職責／任務名稱和內容可局部清空，但至少保留一項有意義內容。成果／要求是獨立的明細，各自一筆命令：新增（清單標籤旁的「+」，在清單末端開空的就地編輯器）、改字（就地，保留身分）、移除（每項的 ×，先確認）。搬到別的職責是任務工具列 ⇄「移到其他職責」選單的單筆 `move_task`：選單列出所有職責與「未歸屬任務」（Primer ActionMenu 單選的做法，Things 的 Move、Jira 的 Move 同類），目前所在處打勾，選了就送、放在目的職責末尾，不附帶文字調整；選目前所在處只關選單。未歸屬明確列為「未歸屬任務」，不用空白選項冒充（`area_id` 是 null）。
- 排序採明確上移／下移；任務及兩組明細各自排序。刪職責先說明任務會保留並轉未歸屬，刪任務另外確認，不把兩種刪除混成同一結果；移除單項成果／要求同樣先確認（沒有 Undo）。
- 所有集合命令先保留原意，再 POST；未知結果不能換命令。待確認入口獨立於原目標是否仍出現在新稿，因此原任務後來已刪除也可取回原結果。成功只觸發 GET 目前稿，不把舊結果塞回 cache。
- 收到合法成功結果但本分頁清理失敗，明說「修改已保存、暫存未清除」，保留原命令供後續確認，不誤報後端保存未知。清除分頁資料的限制仍沿 [§1](#1-基本資料編輯的讀取基底與恢復)。
- 儲存按鈕放 Dialog 固定底部，長表單內容可捲動。轉場完成才設定初始焦點；若使用者已在表單欄位／按鈕操作，不搶焦點。此窄 helper 不取消框架的 focus trap。

沿用 [§1](#1-基本資料編輯的讀取基底與恢復) 的 React／TanStack 官方契約及 MUI 原生表單與 [Dialog](https://mui.com/material-ui/react-dialog/)；保存、新鮮度與原結果辨識由既有業務責任實現，非 UI cache 的保證。相應實測與限制見 T03 §7。

## 3. 共用知識／技能及任務關係的人工編輯

[CapabilitiesSection](../../apps/web/src/features/jd-editor/CapabilitiesSection.tsx)呈現兩類共用定義、概覽排序及反向用途；[CapabilityFields](../../apps/web/src/features/jd-editor/CapabilityFields.tsx)只管新增表單的局部草稿；[TaskCapabilities](../../apps/web/src/features/jd-editor/TaskCapabilities.tsx)在每項任務管理連結、解除及關係排序。沿同一 `JdWorkEditor`、`WorkDialog` 及 `workCommand`，不增加第二套命令暫存、對照表或保存服務。

- 所有定義與關係來自同版 `/jd/work`。畫面可在任務顯示共用說明並連回定義；反向用途連回所屬任務。這是呈現，不把正文或反向列表另存一份。
- 新增定義只填名稱、說明，至少一者有意義；修改在原處逐欄進行（[§6](#6-逐欄就地編輯)），只送變動欄位，空字串轉明確 null，沒改不送。知識／技能類別在建立時確定，不提供會改變所有用途含意的跨類切換。區塊說明列寫明「修改定義，所有使用它的任務都會顯示新版」。
- 任務選單顯示名稱及說明以辨識範圍，使用 stable ID 操作而非標題；同名項仍是獨立物件。清楚標示「選取後即保存關聯」，不冒充尚未提交的表單草稿。解除只移除該任務關係；概覽與每任務的各類排序分開。
- 使用中的共用定義顯示相關任務及刪除限制；先解除所有用途才能刪定義，後端仍為最終約束。刪任務保留共用定義，刪職責不丟失任務關係。
- 定義與關係命令共用 [§2](#2-職責與任務的人工編輯) 的原基底、待確認／重開及 cache 失效邊界；原命令結果再度取得也不覆寫目前新稿。profile／集合互相刷新，沒有獨立 `/capabilities` latest 拼接或樂觀宣告保存。

研究核對 [MUI Select](https://mui.com/material-ui/react-select/) 的標籤／受控選取及 [§1](#1-基本資料編輯的讀取基底與恢復) 的 React／Query 契約；目前用既有元件即可，不為局部選取新增搜尋或表單框架。資料准入、原子性與重送由後端領域模組負責，不由 MUI 判定。桌面／390px、共享修改及實際丟失回應的證據見 T03 §9。

## 4. 協作對象與共通條件的人工編輯

[CollaboratorsSection](../../apps/web/src/features/jd-editor/CollaboratorsSection.tsx)及[ConditionsSection](../../apps/web/src/features/jd-editor/ConditionsSection.tsx)是同一編輯器的集合呈現；新增表單由各自的 Fields 元件管理固定開啟基底的局部草稿，既有文字就地修改（[§6](#6-逐欄就地編輯)）。仍沿 [§2](#2-職責與任務的人工編輯) 的單一待確認命令、Dialog、schema guards 及重讀，不新增保存機制或另一套操作引擎。

- 協作對象填已知名稱與合作範圍，至少一項有內容；未知名稱可空，不因合作推定主管。只改有變動欄位；清空已知名稱但保留範圍是明確 null，不是刪除物件。
- 共通條件以五種既定分類及正文呈現，新增時須明確選分類，不代猜預設。分類內上移／下移；更正分類是條件工具列 ⇄「移到其他分類」選單的一個動作（單筆 `revise_condition` 的 `kind`），列出五種分類並勾出目前的，保留原身分、追加於新類末尾。共通條件不自動變成任務要求，未知不等於沒有或不需要。
- 刪除需確認，只移除目前選用，歷史仍保留。新集合從同版 `/jd/work` 取得；未知結果重開後沿原請求確認，確認成功再 GET 目前稿，不將舊結果寫回 cache。
- 回傳 schema 及 TypeScript 由同一份來源生成；顯示分組／文案是 UI 投影，不另存第二份 server state。既有草稿不因背景查詢改基底。

採用 [React state 原則](https://react.dev/learn/choosing-the-state-structure)、[TanStack invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/invalidations-from-mutations)、[MUI Select](https://mui.com/material-ui/react-select/)；目前元件足以承接，無需新表單／分類框架。這些來源支持 state／呈現機制，交易、固定歷史與原命令保證仍由 JD 領域模組及編輯工作流承接。驗證與限制見 T03 第九切片。

## 5. 工作畫面組裝

JD 章節導覽及知識／技能的雙向任務連結共用 `jd-navigation`：原 reveal 事件冒泡展開目標的章節、職責／未歸屬及任務祖先，以 React `flushSync` 在瀏覽器捲動／聚焦前提交 DOM。僅在使用者導覽事件使用同步提交，保留 fragment URL 與修飾鍵開頁；收合仍只改呈現，草稿保持掛載。依據：[React flushSync](https://react.dev/reference/react-dom/flushSync)。

工作區在 `max-width: 899.95px` 與既有 CSS 同步採 tab／tabpanel 關聯；非活動面板隱藏但不卸載。寬版改為兩個具名稱的 region，不讓隱藏的 tab 為區域命名。依據：[APG Tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)、[MUI useMediaQuery](https://mui.com/material-ui/react-use-media-query/)。

本節維護畫面行為；視覺數值由 [`theme.ts`](../../apps/web/src/app/theme.ts)與 [`styles.css`](../../apps/web/src/app/styles.css)維護。

### 版面、狀態與資料呈現

畫面使用下列資料，各自保留原本的保存與更新責任：

| 資料 | 持有位置 | 更新者 | 用途限制 |
|---|---|---|---|
| 服務端 Turn 狀態 | 後端業務保存 | 後端執行、控制及完成工作流 | HTTP 讀已保存狀態；SSE 呈現過程，不裁定正式完成 |
| 工作發現提示（hint） | 按檔案隔離的 `localStorage` | `useInterviewInput` 與 Composer 的恢復查詢經 turn API 寫入／清除 | 只帶命令與執行識別，不是執行狀態或訪談正文。檔案身分只有小寫 UUID 一種拼法：路由是唯一接受外來拼法（含大寫）的入口，正規化後才成為 query key、Web Lock、hint、暫存與刪除廣播的 scope（`shared/api/uuid.ts`） |
| Turn 的查詢結果 | 本分頁 TanStack Query cache | `InterviewComposer` 查詢／輪詢；頁面只觀察 | 不用 Effect 複製進 component state；沒有資料不等於已確認閒置 |
| JD 局部草稿與開啟基底 | 編輯器的 component state | 開啟時捕捉修訂，使用者修改草稿 | 背景 GET 不換草稿或基底；保存條件沿 [§1](#1-基本資料編輯的讀取基底與恢復) |
| JD 待確認命令 | 本分頁、該檔案的 `sessionStorage` | `useStoredCommand` | 保留原命令供確認，不是正式 JD；重送條件沿 [§1](#1-基本資料編輯的讀取基底與恢復) |

[hint 訂閱](../../apps/web/src/features/interview/interview-turn-api.ts)使用 `useSyncExternalStore`，接收同分頁事件及跨分頁 `storage`；沒有 hint 時，由 `/current` 發現工作。處理區與頁面觀察同一識別；頁面以 `useCurrentTurn` 的停用 query 觀察者讀同一份 cache，供檔案列徽章與 JD 唯讀判定，不另發 GET／輪詢。啟動、恢復與輪詢只由 `InterviewComposer` 負責；回傳區分已核狀態與未知，HTTP／SSE 邊界見[介面 §2](interface-and-delivery.md#2-串流不是保存權威)。

- **版面**：職務檔案頁為左訪談、右 JD 並排（`WorkspaceLayout`），各自捲動、整頁不捲動；窄螢幕（<900px）以分頁切換。切換只用 CSS，**兩區保持掛載** ，輪詢、SSE 與未送出草稿不因切換而丟失。訪談輸入與 Turn 控制固定在訪談欄底部；訊息記錄只在使用者接近底部時跟到最新，回看舊訊息不被打斷；離開底部時，輸入區上方浮出一顆「回到最新」圓鈕（AI Elements 的 scroll-to-bottom 做法），點了回到最新並恢復跟隨。[useStickToBottom](../../apps/web/src/shared/ui/use-stick-to-bottom.ts)只回報「是否離開」與「回去」兩件事，頁面把按鈕經 `aboveDock` 插槽交給輸入區，輸入區不認得捲動、按鈕不認得聊天。
- **JD 唯讀鎖**：Turn 為 active 或 paused，或處理狀態尚未確認時，JD 顯示原因並停用人工編輯入口；已開啟的表單也保留草稿但禁止新修改，仍可核對既有待確認命令。正式內容仍可閱讀。已核終態或已確認沒有進行中工作才解除。這只改善體驗，寫入仍由後端拒絕（[介面 §1](interface-and-delivery.md#1-api-與-ui-的責任)），不把一次 GET 當長期寫入資格。
- **候選與正式稿**：候選預覽在 JD 欄，用獨立「候選」樣式（「AI 層」）並註明尚未正式保存，可一鍵切到正式稿；兩個檢視都保持掛載，切換不重新載入正式稿。PDF 入口在 JD 欄，仍只匯出正式版本。取消後候選消失、回到正式稿。
- **來源**：來源回查是 JD 欄右側滑出面板（列表與單筆來源切換）；JD 各項目旁的「來源 n 筆／待核對」徽章只用 `Reference.target` 身分連結（見 [JD 保存 §3.7](jd-storage.md#37-人的正式來源回查)），沒有 `target` 就不顯示徽章，絕不按標籤猜。徽章點擊只把面板篩到該項目的引用；查看不解除待核對。App 組裝實際開啟控制與面板，關閉時回到仍有效的來源徽章或 disclosure，控制失效則回到固定 disclosure；DOM 焦點狀態不進正式資料或 query cache。面板維持非 modal，不新增焦點陷阱。

### 長 JD 導覽與操作

- **收合範圍與顯示**：職責與任務使用相同的收合箭頭；內容保持掛載。職責收合時顯示任務數，任務收合時保留標題與來源標籤，兩者皆隱藏編輯動作。「JD 職責與任務」整區收合時，所有職責、所屬任務、「新增職責」與「未歸屬任務」一起隱藏，留下標題及「N 項職責・M 項任務」；未歸屬區也能[單獨收合](../../apps/web/src/features/jd-editor/UnassignedSection.tsx)，行為與職責相同。載入、讀取失敗與待確認命令橫幅在收合區外，持續可見。
- **輔助區塊的收合**：所需知識、所需技能、主要協作對象、工作條件與責任邊界四個區塊，各用 [FoldableSection](../../apps/web/src/features/jd-editor/FoldableSection.tsx)在標題旁顯示箭頭及項數；不受職責與任務整區收合影響。這些是正式 JD 的必讀內容，預設展開，因此不採 GOV.UK 手風琴的預設收合建議。展開狀態僅留於本次畫面，不寫入儲存。
- **章節導覽與共用狀態**：sticky 導覽列標示目前章節；選到已收合區塊時，先展開再捲動。職責、任務、輔助區塊、未歸屬區及整段職責與任務共用 [FoldToggle](../../apps/web/src/features/jd-editor/FoldToggle.tsx)的箭頭／無障礙屬性，以及 [useFold](../../apps/web/src/features/jd-editor/use-fold.ts)的展開狀態。導覽透過區塊元素的 `jd-reveal-section` DOM 事件要求展開，兩方不互相 import。
- **編輯操作的可見性**：圖示按鈕保留無障礙名稱。滑鼠 hover／聚焦時，只顯示最內層項目的工具列；指著任務不連帶顯示所屬職責工具列。搬移選單開啟時，所屬工具列保持顯示。刪除一律用 ×：平時中性色、hover 轉紅，仍經確認對話框，確認鈕才是紅色；任務下的解除關聯也用相同記號。清單「+」只在指著該清單時顯示，不增加行高；空清單與觸控環境則常駐。
- **觸控提示**：觸控環境的編輯操作常駐。對 `hover: none`／`pointer: coarse` 指標，「JD 職責與任務」標題下顯示「點任何文字即可直接修改」；滑鼠環境不顯示。這沿用 Atlassian 就地編輯需有可見提示的原則。

### 訪談、樣式與多分頁

- **視覺系統與聊天室**：職務檔案頁由檔案頂欄（`FileBar`）兼任頁首；清單頁用全域頁首（`AppHeader`）。訪談欄採 Cloudscape 的窄版聊天模式，員工與顧問同側排列，以頭像及名稱辨識。訪談採與右側 JD 一致的白底閱讀欄：員工原話旁加細線，不用大面積色塊；顧問正文直接排在頁面上，頭像淡化；App 開場同側排列並降低強調。頭像字樣由 [SpeakerAvatar](../../apps/web/src/features/interview/SpeakerAvatar.tsx)統一。標頭不顯示正式訪談序號；來源回查仍保留後端提供的序號與說話者標籤。
- **這一輪與歷史回覆**：[TurnLog](../../apps/web/src/features/interview/TurnLog.tsx)呈現尚未正式的員工原輸入（虛線框、「尚非正式訪談」）與顧問處理內容（推理摘要、過程及輸入中的圓點）。暫停、取消、失敗仍歸在顧問名下；`InterviewComposer` 負責提交與恢復，不接管串流排版。確認完成後，底部不再保留摘要或過程入口，統一從正式顧問回覆的「處理紀錄」按需展開。歷史尚未載入或讀取失敗時，由歷史區顯示載入狀態或提供重讀，不另造底部備用紀錄；Composer 不觀察歷史快取來決定是否顯示完成紀錄。
- **閱讀與樣式邊界**：「匯出目前已正式保存的版本，不包含本輪候選預覽。」常駐可見。MUI 樣式放入 CSS Layer，一般 CSS 不以加大優先權覆蓋 MUI。中文行寬以 `em` 限制，字型自架（Inter＋Noto Sans TC），不對外連線。聊天室繼續沿用既有色彩、字級、焦點與高對比規則，不建立另一套主題。
- **不變**：所有命令識別／原命令恢復、版本衝突、待確認命令、跨職務檔案 query key 隔離、公開訊息非正式來源等規則不因版面改變；重排時以既有測試的「角色＋名稱」為護欄，標題、按鈕名稱與 region 名稱視同契約。

**多分頁的最小支援：** 保留一般多分頁開啟，各頁向原 API 讀取，hint 訂閱沿上表接線；不新增全 App 單分頁鎖、即時協作、草稿同步或跨頁 Query cache 廣播。畫面可能短暫落後，最終仍由後端同檔 A 排他、人工寫入資格及 JD 修訂條件拒絕過期寫入，不能靜默以新版基底重送。這不是跨瀏覽器單一視窗承諾。

## 6. 逐欄就地編輯

既有文字點一下就地改一欄；新增任務、知識／技能、協作對象及條件用表單，新增職責使用就地列；搬移用選單，成果／要求用「+」與 ×。每次儲存或操作都是單筆命令：集合使用 [§2](#2-職責與任務的人工編輯) 的 `WorkCommand`，基本資料使用 [§1](#1-基本資料編輯的讀取基底與恢復) 的 profile 命令。

### 編輯範圍與操作

可逐欄編輯的文字包括 JD 基本資料四欄（職務名稱、所屬單位／工作範圍、匯報關係、職務目的；送 profile 命令，四欄都可清空）、職責名稱／範圍、任務名稱／工作內容、每項成果／要求、知識與技能名稱／說明、協作對象名稱／範圍，以及共通條件內容。

**新增職責**：職責清單末端的「新增職責」就地變成名稱欄位，只送名稱，範圍之後在原處補，沒有對話框。

新增任務、知識／技能、協作對象與條件仍使用表單，以填寫多欄或選擇分類、所屬職責。條件分類與任務歸屬由「移到…」選單處理；成果／要求的新增與移除則使用「+」與 ×。

互動依據為 Atlassian inline edit、Primer saving 與 Cloudscape inline edit。點文字，或用鍵盤找到「修改〇〇」按鈕（視覺隱藏，聚焦時整段文字出現外框；它是鍵盤與螢幕報讀的路徑，點文字只是捷徑）。

文字就地變成輸入框，儲存（✓，品牌色實心）與取消（✕）兩顆圖示鈕在欄位末端，先儲存後取消（Atlassian inline edit、PatternFly、Cloudscape 都用圖示鈕；提示文字標出對應的鍵，觸控裝置放大到 40px）；單行 Enter 儲存、多行 Ctrl／⌘＋Enter 儲存（Enter 換行）、Esc 取消。

單行的 Enter 用 `<form>` 的原生送出而不是自己聽按鍵，所以注音選字的 Enter 不會誤送（e2e 以 CDP 的輸入法組字驗證，限 Chromium）。

拖曳選取文字（複製）不會開啟編輯。關閉後焦點回到該按鈕。

搬任務與更正條件分類共用 [MoveMenu](../../apps/web/src/features/jd-editor/MoveMenu.tsx)：圖示鈕開啟單選選單，目前位置打勾，選取後送出單筆命令；先例見 [§2](#2-職責與任務的人工編輯)。

成果／要求的新增與移除在 [TaskDetails](../../apps/web/src/features/jd-editor/TaskDetails.tsx)（標籤旁「+」開空的就地編輯器，同一個 `InlineEditor`，空白儲存只關閉；每項的 × 先確認再送 `remove_detail`）。

任務所屬職責的選項由 [area-choice](../../apps/web/src/features/jd-editor/area-choice.ts)給新增表單與搬移選單共用。

### 編輯互斥與命令恢復

同一頁只開啟一個編輯器，沿用 Primer 的做法。編輯開啟期間其他編輯控制項（項目工具列、新增）暫停，因為編輯器固定了開啟時的修訂，期間任何其他寫入都會讓它的儲存衝突。

基本資料與集合是兩條命令卻寫同一個修訂，所以這個排他跨兩邊：[EditSlots](../../apps/web/src/features/jd-editor/EditSlots.tsx)提供一個共享的「誰佔著 JD」集合，每個編輯器（[JdProfileEditor](../../apps/web/src/features/jd-editor/JdProfileEditor.tsx)、`JdWorkEditor`）經 [useEditSlot](../../apps/web/src/features/jd-editor/edit-slots-context.ts)回報自己是否佔用（編輯器開著，或命令在途、未確認、被拒絕），並得知別人是否佔用；兩邊互不認得對方。

沒有 `EditSlots` 時（單獨渲染）編輯器獨立運作。

「新增」類控制項用 `aria-disabled` 而非 `disabled`，儲存後頁面短暫忙碌時焦點仍能落在它上面。

儲存送出「開啟時固定的修訂＋單筆變更」；基底、草稿保護及恢復沿 [§1](#1-基本資料編輯的讀取基底與恢復)及 [§2](#2-職責與任務的人工編輯)。

只有空白（含必填文字清空）拒絕並說明、清空選填欄位送 `null`、沒有改動就關閉不送。

命令先保留原命令再送出；在途時欄位與按鈕停用；結果不明時草稿留在原處，並在欄位旁提供「重新確認修改結果」（同一原命令，不能換新命令）；明確拒絕保留草稿並要求讀目前稿；Turn 佔用時草稿保留但不能儲存。

離開編輯器時，頁面橫幅接手重新確認；欄位若在新稿中消失，原結果仍可取回（編輯器自己回報掛載與卸載，頁面不會卡在已不存在的編輯器上）。

### 編輯元件的分工

| 元件 | 責任 |
|---|---|
| [inline-fields](../../apps/web/src/features/jd-editor/inline-fields.ts) | 定義可編輯文字及每欄的單筆變更 |
| [InlineText](../../apps/web/src/features/jd-editor/InlineText.tsx) | 閱讀檢視、點擊／鍵盤入口及焦點返回 |
| [InlineEditor](../../apps/web/src/features/jd-editor/InlineEditor.tsx) | 局部草稿、鍵盤與儲存／取消 |
| [WorkStatus](../../apps/web/src/features/jd-editor/WorkStatus.tsx) | 顯示命令狀態，供頁面橫幅與編輯器共用 |
| [use-focus-return](../../apps/web/src/features/jd-editor/use-focus-return.ts) | 關閉後把焦點還給開啟控制項，供閱讀入口與「+」共用 |
| [JdWorkEditor](../../apps/web/src/features/jd-editor/JdWorkEditor.tsx)、[JdProfileEditor](../../apps/web/src/features/jd-editor/JdProfileEditor.tsx) | 各自管理開啟欄位及命令 hook，透過 [inline-edit-context](../../apps/web/src/features/jd-editor/inline-edit-context.ts)提供窄介面 |
| [AddArea](../../apps/web/src/features/jd-editor/AddArea.tsx) | 新增職責的就地列，使用同一個 InlineEditor |

共用介面為 `save(revisionId, intent)`、`status`、`canOpen`／`canEdit`。`intent` 以 `collection` 區分 `WorkIntent` 與 `ProfileIntent`；inline-fields 描述意圖，各 hook 轉成命令，編輯元件只傳遞而不解讀。編輯元件不 import 命令 hook，也不依賴任務或職責的資料形狀。沒有 provider 時（例如候選預覽），同一元件僅呈現文字。

### 已知取捨與驗證限制

- 每段可編輯文字增加一個 Tab 停點，與工具列圖示並存；觸控靠標題下的說明提示點字編輯。
- 同時只開一個編輯器。修改三欄會送出三筆命令，各自推進修訂；新增職責先填名稱，範圍須另行補入；搬移完成後才可修改文字。
- 移除成果／要求須先確認，沒有 Undo。搬移後項目離開原處，目前沒有「已移到…」提示。
- 輸入法僅以 Chromium CDP 模擬驗證，未以真實注音輸入法逐瀏覽器測試。

驗證：逐欄就地編輯、基本資料與畫面。
