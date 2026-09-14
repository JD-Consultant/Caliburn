# JD App：收尾與未解事項

**完成窗口最新狀態（2026-09-13）：**[3cbd3ca5 窄複核](evidence/jd-interview-window-source/cursor-lineage-review.md)確認 R-01／R-02 CLOSED，獨立來源／歷史及原探針 59 passed；F-03 source 層已閉合。下列各片數字保留歷史；下一採用 B1，W-13、原 pair 與 reader grant 隨 B1／B2 接線驗收。未新增配對引擎需求，H4 整體仍未完成。

**最新複核狀態（2026-09-13）：**H2–H3已完成；H4映射`2e243d15`的[提交後審查](evidence/2026-09-13-jd-b1-b2-adoption-review.md)及完成窗口 `ab483f6c` 的[9/12–9/13 文件審查](evidence/2026-09-13-jd-window-source-contract-review.md)已修正已驗方法／通知漏接、背景恢復誤套、source／publication 接縫、窗口觸發與分頁語意。這些是文件缺口，沒有本輪產品bug或測試通過宣稱。下一按[接續計畫H4](../plans/2026-09-13-jd-app-continuation-handoff.md)依修正版有限實作；OI-01／02整體退出條件仍未完成。

**最新整體審查（2026-09-14）：**B1／source固定接合已到 `f160be97`；W-13、F-04、P3 的早期 OPEN 為下方歷史，不重做。[整體審查](evidence/jd-b1-adoption/whole-flow-review.md)補上同 ID 內容替換的 source owner 窄修、批次→B1接縫與背景狀態責任，獨立 B1／來源＋Memory 套件212項通過；未跑B1真PG或新程序。**下一依[H4 runtime計畫 R1](../plans/2026-09-14-jd-h4-runtime-integration.md)**做一批 B1 真PG保存／恢復與固定有界批次，再接B2／通知／宿主。v1 context明示不支援、fresh fixture用v2；沒有舊資料轉換工作，也不因假設中的v1資料阻施工。

更新：2026-09-14；JD-R002。依[最新決策](../current-decisions.md)、[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)及最近結果整理；9/13 詳細切片仍保留作沿革，當前施工以頁首最新狀態及 H4 計畫為準；只集中追蹤，不改需求、保存權責或既有授權。

**目前可看／可驗：**隔離 App 的六章手動管理、真 DB 保存、重開、同頁聊天接點與已保存差異已有實證。既有非JD顧問的CT49／50真模型成果已完成，不能說成只有固定測試。**新App尚不能稱可交付：**完整顧問／Memory採用及新JD自然品質仍未完，日常AI未啟用；新工具的固定SDK回覆不代替新旅程真模型驗收。

完整度分三層：內部展示可標明限制；受控自然試用須先閉合核心接線及該旅程可靠性；完整第一版仍履行原計畫的還原、撤回、維護與驗收。下列「可稍後」不是默默刪除承諾。技術細節由工程端處理，不要求 Owner 重選欄位或框架。Owner 本輪明確收斂為只看當輪 LLM 改動；從舊對話選看該輪整體改動不列缺口，既有保存歷史仍保留。

## 核心阻擋與已承諾接點

### OI-01｜日常 AI 與專業顧問指引：核心阻擋
- 現象／影響：日常入口回 `ai_unavailable`；目前合成接線不能讓員工自然訪談製作專屬 JD，也未證明顧問能掌握適當寫稿時機及雙向收尾。
- 證據：[聊天結果](2026-09-13-jd-chat-web-slice.md)、[已研究的顧問品質與寫作規則](2026-09-10-jd-product-quality-acceptance.md)。
- 下一最小動作：把既定專業方法接入實際顧問與現有工具，補日常模型設定／明確啟用接點；先驗固定流程，付費驗證依 OI-09，不能用改一個啟用旗標代替接合。
- 退出條件：從日常入口可自行開始訪談，資料不足能問、局部足夠能寫、純訪談可以不改 JD；實際保存與回覆一致，至少完成首份自然案例。

### OI-02｜Memory、工作理解與來源原文：核心阻擋
- 現象／影響：已接當輪原話 source owner、真 request 引用通知及人工／AI 共用保存驗證，真 PG 更正與重新開啟資源可讀原來源。完整 Memory／案例能力、較早來源檢索及來源 UI 尚未接；頁面 metadata／`not_checked` 仍不代表使用者已能回查原話。這直接影響反覆更正、忠實度與客製化，不能當美化缺口。
- 證據：[Agent 接合界線](2026-09-13-jd-ai-runtime-and-tools-slice.md)、[人工通知與 context 界線](2026-09-13-jd-consultant-context-slice.md)、[工具責任](2026-09-12-jd-relational-agent-tool-contract.md)。
- **2026-09-14 來源 UI 局部：**讀取視圖一直都回傳每個欄位／項目依據哪些訪談、以及那份依據是否仍吻合目前內容，但畫面驗證完就丟掉。現在每個欄位與項目下方會說「依據你說過的 N 段訪談」，內容在那之後被改過時改說「原始依據可能不再吻合」。不顯示不透明的 source token，也**不顯示 readability**——伺服器明說那項未核對，畫面不得暗示原話點得開。伺服器端整條鏈（`source_ref`→`basis_refs`→`jd_source_link`→讀取視圖的 `source` 記錄、以及改稿後 `basis_status` 翻成 `needs_recheck`、刷新後翻回 `current`）早已有真 PG 測試；本次新增的是投影與畫面兩層，各有固定測試。由來源[點回原話](2026-09-14-jd-source-readback-slice.md)也已完成並在真瀏覽器驗過：標記旁的「看第 N 段原話」開出員工原話，顧問當時的回覆另標且註明不是員工確認過的事實。**仍未接：**較早來源的檢索（主動找某段訪談，而不是由標記點進去）。
- 已驗局部：[當輪原話接合](2026-09-13-jd-consultant-source-integration-slice.md)。沒有新增原話表或模型工具；來源故障停止回合、人工來源讀取可排空，兩項獨審缺口已修；當輪固定來源不是所有早期工作已納入的證明。
- 已驗核心：[獨立 Memory 套件與新來源接合](2026-09-13-jd-memory-core-adoption-slice.md)完成既有保存／發布、固定讀取、來源埠及 proper wheel；核心44、來源71、受影響113、真 PG1及獨審98通過（範圍重疊不相加）。真 Store／發布可修正、阻擋舊整理覆蓋及重開讀原話；模型 Memory 工具、B1/B2/C 與日常宿主尚未接，不等於完整 Memory 通過。
- 已驗宿主：[Memory 資源／初始化／重開](2026-09-13-jd-memory-host-integration-slice.md)接同設定與原生 Store。受影響154、初始化33真PG、新Windows／PG1與原旅程回歸3通過；只有已登記讀取／既有前景的排空範圍，模型Memory／背景工作尚未接。普通open不setup，JD／原話不雙寫。
- 已驗讀取：[固定 Memory／詳記／原話工具](2026-09-13-jd-memory-read-integration-slice.md)已接真正模型 request、原生四個只讀工具及 native 中斷／收尾。真 SDK／PG 三輪與新 Windows 宿主回歸通過；模型回覆及發布仍是合成測試，不是自然理解或 C／B1B2 已完成。沒有為本功能新增資料表或一般儲存引擎。
- 已驗修補核心：[C 子圖／官方 patch／原結果查回](2026-09-13-jd-memory-repair-core-slice.md)已在正常套件；真 PG 更正及回覆遺失後原 request 查回、JD／原話保留通過。三個錯誤／結果核對缺口已修且獨審閉合；不等於 App 已有 C 工具／取消收尾或 B1B2。
- 已驗App接合：[停止收尾、跨程序查回與封裝](2026-09-13-jd-memory-repair-app-integration-slice.md)已修CA-01／02；缺證據仍保持門閘。FH05真新程序＋真PG只憑原receipt對帳，publish／patch為0；乾淨venv完整依賴wheel隔離已通過。實作者最終全組數字與本次獨立窄跑分別見結果稿／複核稿，本清單不再保存另一份易過時的數字。這是C接合可驗收，不是完整顧問或自然品質通過。
> **以下 source port 與 B1 adapter 條目是 9/13–9/14 沿革，不是目前待辦；目前接續以本頁最新段落及 H4 runtime 計畫為準。**
- 採用映射已交並修正：[採用映射](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)保留`4f94fbfb`已驗來源與13模組hash結論；補回A指引／三项分析Skills／整理通知，分清C查回與B有界續作、來源介面及各角色限制。只有文件，不是H4實作通過。
- 契約已交並完成文件審查：[完成窗口source port契約](2026-09-13-jd-interview-window-source-contract.md)定新增`purpose="window"`簽章引用（`last`不綁run_id）、分頁讀取、逐輪終局改用run record＋`observed.closed`、整理請求辨識、觸發與連續範圍分開、B2 `processed_source` 的用途感知驗證、source/context pair、Unicode offset 及 purpose salt 隔離，並列W-01–W-14固定情境。其後五個隔離切片已完成固定測試，但最新[實作審查](evidence/2026-09-13-jd-window-source-implementation-review.md)指出W-08／W-13／W-14及cursor lineage／boundary仍不完整；不能宣稱H4或B1／B2已接通。
- 實作第一片已完成：[用途隔離與B2發布驗證](evidence/jd-interview-window-source/purpose-isolation-results.md)閉合審查F2的整合斷點——未用途感知前，B2的完成結果在`PublicationStore._validate`就會被拒，永遠無法發布。離線2748／套件130／真PG14通過。窗口內容讀取、planner與公開發配路徑**刻意未做**（安全終局只有planner能確立），見該稿界線。
- 實作第二片已完成：[逐輪安全終局、發配與分頁讀取](evidence/jd-interview-window-source/window-read-results.md)。全部放在同一source owner，沿既有`AiRunHistory`逐輪在該輪自己的終局checkpoint核對，lineage以訊息序列精確前綴證明（不靠ID相同）；分頁只切可見文字、`turns`每頁完整、offset為Unicode code point；省略種類具名。已涵蓋W-03／05／07／08與W-04的停在未收尾之前。離線2753／套件130／真PG16通過（另1個既有OI-05分頁缺陷不變）。
- 實作第三片已完成：[整理通知採用、觸發清單與連續安全範圍](evidence/jd-interview-window-source/trigger-and-coverage-results.md)。整理通知自`4f94fbfb`逐位元採用進`caliburn_memory/requests.py`（工具描述一字未改，已登記adoption）；`pending_windows`只回觸發回合，`unprocessed_source`另回連續安全範圍且納入沒通知的安全回合，範圍止於第一個未收尾回合；游標只接受publication head自己的window引用，離線lineage即停止admission不重設。離線2762／套件130／真PG18通過。已涵蓋W-01–W-05／07／08／11／12。**工具尚未註冊給顧問，顧問目前發不出通知。**
- 實作第四片已完成：[切分規劃、消歧pair與admission](evidence/jd-interview-window-source/planner-and-admission-results.md)。切分／批次／重抽驗證／admission沿`4f94fbfb`逐條移接：超大回合與放不下的消歧一律失敗不截斷；新增第三個purpose `context`（獨立salt，不得當成待整併來源），用途授予拆成`window_references`／`context_references`兩旗標，因為套件對source與context走同一個`validate_source`；規劃結果固定同一root，有界批次以`covers_whole_range`防止取前綴宣稱完成，尾端由publication游標接續不需額外狀態。離線2770／套件130／真PG14通過。
- **契約固定情境 W-01–W-14 都已有測試入口，但最新審查不把它們全部標成完整通過。** W-08尚無同ID分支 lineage／合法 mid-turn cursor；W-13尚無B1 `reextract`及正常輸入位置不前進證據；W-14尚無`>256` ancestor fixture。W-14既有缺鏈案例沿`test_ai_history.py`技法通過並明示`original_run_lookup_required`，屬補證據不是改產品；詳見[source port實作審查](evidence/2026-09-13-jd-window-source-implementation-review.md)。
- 審查F-01／F-03已修：[游標lineage／完整邊界與查找上限](evidence/jd-interview-window-source/cursor-lineage-results.md)。原本的`_after_cursor`／`follows`**從未打開游標自己的固定root**，只比對訊息ID；新增`AiRunHistory.ancestor_of`（沿`find`同一組parent連結與同一上限）與共用的`_cursor_boundary`，要求在游標自身位置讀回、訊息為精確前綴、root為真祖先、`last`正好是安全回合邊界。三個反例：合法簽章但停在回合中間（原本會跳過該輪其後原話）、游標root讀不到、**同內容兄弟鏈**。另補`>MAX_PARENT_LOOKUPS`固定鏈案例。離線2774／套件130／真PG18通過。**W-13（F-02）與pair交叉配對（F-04）仍開著，依審查留給B1 adapter。**
**目前下一最小動作：**依[H4 runtime 計畫](../plans/2026-09-14-jd-h4-runtime-integration.md)完成 R1→R2→R3；固定批次／真PG保存、B2發布／C競爭、完整通知與背景生命週期。詳細步驟與六欄准入責任不在此重抄。上方各切片的「未接」依本段最新狀態閱讀，不重新安排已完成 source／adapter 測試。

**目前退出條件：**跨輪／重開後能取回早期有效工作，晚期更正不被舊 Memory 蓋回；JD→原話與工作→JD 均可核對，手改通知不冒充原話，也不自動寫入 Memory。

### OI-03｜瀏覽器 Fetch 拒絕：OPEN，可靠試用阻擋
- 現象／影響：建立文件與聊天後刷新曾發生 `response_unknown`；服務端 200 不等於瀏覽器取得結果，不能保證員工能順暢自行完成。
- 證據：[有限診斷與三組紀錄](evidence/jd-relational-chat-web/transport-diagnosis.md)：第三組 TypeError／13 ms／未 aborted 只排除該次 15 秒逾時；原 run 明示查回成功，根因仍未明。
- 下一最小動作：本輪先停止無證據重現。取得既有環境可用的 Network 原錯誤階段後再定點處理；其間保留原請求與清楚查回出口，不弱化 CORS 或加入自動重送。
- 退出條件：原因有可核證據並修正，或明確受支持的日常環境通過同條完整旅程；受影響舊環境仍如實列限制，不改寫首次失敗。

### OI-04｜CV-01 當輪改動：API／畫面已接，真瀏覽器未驗
- 現象／影響：當輪淨結果、目前欄位提示、完整前後與直接可見刪除原文／完整所屬已接，分層測試及獨審通過；尚無新畫面的真瀏覽器點擊／捲動／晚回競爭驗收。
- **2026-09-14 局部：**[整輪撤回的真瀏覽器旅程](evidence/2026-09-14-jd-restore-and-undo-browser-results.md)順帶在真 Chrome 上看過「本輪 JD 改動」面板，逐項顯示這輪的新增（任務／要求／成果）與變動欄位。**只涵蓋新增**；修改／刪除／移動／引用的辨認、捲動與晚回競爭仍未在真瀏覽器驗，本項不因此關閉。
- 證據：[當輪接合與分層結果](2026-09-13-jd-run-change-view-slice.md)、[依Owner收斂的呈現需求](2026-09-12-jd-change-visibility-design.md)。舊對話選輪入口不需要，不列未修缺口。
- 下一最小動作：配合核心顧問旅程與可用的日常瀏覽器環境，集中核對一條當輪查看／更正流程；有新反例才修，不重開架構或追加歷史選輪。
- 退出條件：真瀏覽器可辨認當輪新增／修改／刪除／移動／引用，改後改回仍可查事件，人工或別輪介入不混算；沒有接受按鈕，開始下一輪後不把舊輪內容冒充當輪。

### OI-05｜深歷史與長訪談連續性：長訪談／完整首版阻擋
- 現象／影響：歷史查找有 256 祖先上限及缺鏈出口，底層讀完整 messages；長上下文、壓縮與晚期更正尚未在新 App 完整驗證，不能把上限或缺鏈當「沒有原回合」。
- 證據：[原回合查回结果](2026-09-13-jd-chat-admission-and-original-run-slice.md)、[聊天歷史界線](2026-09-13-jd-chat-http-slice.md)、[品質 Q09／Q13](2026-09-10-jd-product-quality-acceptance.md)。
- **2026-09-14 已定案並修好：**分頁方向由四個各自獨立的來源一致指向同一個語意——契約 `ChatHistoryPage` 明寫「初始頁是**最新**的至多五十則，`next_cursor` 取**更舊**的一頁，每頁內部維持時序」；`chat_history.py` 的註解寫同一句；Web 的 `chat-session.ts` 把續頁**前插**到已顯示訊息之前（`[...page.messages, ...this.messages]`）；離線測試更有一條專門命名的 `test_initial_page_is_latest_window_and_continuations_prepend_older_chronological_pages`。唯一相反的是那條真 PG 斷言，它假設 `limit=1` 會拿到最舊一則——**它才是錯的**，而且因為只在明示啟用 PG 時才跑，長期沒被看見。已改成依契約斷言：`limit=1` 取最新一則、用 `next_cursor` 往回取到較舊那則、anchor 不變。這不是為綠燈改測試：實作與契約沒有動，變異驗證（把取窗改成最舊）會讓包含那條專門測試在內的多項失敗，改動後以 `git hash-object` 確認 `chat_history.py` 還原。**OI-05 其餘部分仍開著**：256 祖先上限、缺鏈出口、長上下文與壓縮、晚期更正在新 App 的完整驗證都還沒做。
- 下一最小動作：完成既定深歷史可操作查回及 context／Memory 交接，保留原話與原 request 身分；以一個超過現有查找窗口的合成流程核對，再接已規劃長訪談。
- 退出條件：早期回合與來源仍可定位；超限／缺鏈可處理且不重播，壓縮／重開後早期工作與最新更正不遺失。

### OI-06｜整份還原與整輪 JD 撤回：伺服器端還原已接，其餘未接線
- **2026-09-14 進度（一）：**`restore_revision` 的伺服器端操作已實作並在真 PG 驗收（[結果](evidence/2026-09-14-jd-restore-revision-results.md)）：新修訂、歷史保留、`no_change`／`stale_view`／`target_missing`、同 operation 查回、來源沿用、身分保留；模型永遠沒有這個工具。
- **2026-09-14 進度（二）：**預覽流程、HTTP／Web 入口與整輪 AI 撤回都已接線，並完成[真瀏覽器驗收](evidence/2026-09-14-jd-restore-and-undo-browser-results.md)：真 Chrome 上建立→打字→自動保存→開歷史→「還原到第 2 版」→看逐項比較→「確認還原」，以及一次真訪談讓 AI 寫入後按「撤回這輪 JD 改動」→「確認撤回」；兩條都由獨立唯讀連線核對 PostgreSQL——還原／撤回各新增一版、被取代的版本仍讀得到、conversation checkpoint 未減少。
- **2026-09-14 進度（三）：**設計 §4.2 的暫停已實作——比較開著時 JD 欄位與訪談送出都停用，畫面說明「正在確認一次還原，暫停送出。你的輸入會保留。」，取消即恢復；真瀏覽器已驗還原這一側。收據也改為記錄實際被放回的版本，undo 另記被撤回的回合，並由本輪通知轉給下一輪 AI（`took_back_ai_run`），明說對話與工作理解沒有被取回。**本項仍未關閉**：撤回那一側的暫停共用同一接點但未單獨在真瀏覽器驗；`no_change` 與失敗路徑的暫停解除、以及多分頁情境未驗。
- 現象／影響：可以直接更正及看歷史，但尚未完整提供整份還原的員工入口／符合條件的整輪撤回；不能把 AI 取消當作撤回。
- 證據：[歷史與恢復](2026-09-12-jd-history-and-recovery-design.md)、[HR-02](2026-09-12-jd-ai-turn-undo-design.md)、[目前施工界線](../plans/2026-09-13-jd-relational-app-implementation.md)。
- 下一最小動作：沿既有業務／保存接點實作已定效果與 UI，使用 OI-04 的真實比較材料；不新增通用 undo stack 或任意早期局部拒絕引擎。
- 退出條件：還原／撤回形成新 JD 版本，原對話、Memory、案例與歷史保留；有較晚修改時不覆蓋，結果遺失查回原操作不重複套用。

### OI-07｜輸入、選區與異常旅程：已承諾接點／未驗範圍
- 現象／影響：選區改寫尚未完整接發配；實體 IME、原生候選升版競爭及其餘取消／故障旅程未全驗。既有純測與部分真瀏覽器證據不能代替这些操作。
- 證據：[完整旅程](2026-09-13-jd-complete-app-journey-design.md)、[手動畫面結果](2026-09-13-jd-manual-ui-and-browser-drafts-slice.md)、[聊天未驗範圍](2026-09-13-jd-chat-web-slice.md)。
- 下一最小動作：按既定旅程集中補實際選區、繁中組字及「保存／取消／重開」代表性場景，觀察到缺口才擴測；不要重新測遍已通過的無關元件。
- 退出條件：未送出文字和表單可保留，晚回不蓋晚輸入，選區不改錯同文位置；取消後已保存 JD 可查，狀態、手改門閘與實際程序一致。

### OI-08｜日常交付、備份還原與正式採用：完整首版必補
- 現象／影響：明示初始化／一般啟動核心已驗，日常易用入口、完整備份還原／更新程序及正式採用尚未完成；隔離試驗入口不能直接稱正式產品。
- 證據：[配置結果](2026-09-13-jd-managed-configuration-slice.md)、[RS-5／RS-7](../plans/2026-09-13-jd-relational-app-implementation.md)、[ADR0075 Proposed](../adr/0075-relational-jd-authority-and-structured-editor.md)。
- 下一最小動作：完成一條啟停與設定異常旅程，再實際備份／還原含 JD、原話、Memory 與歷史的整體資料；正式包須含出站驗證使用的同一 contracts 資源。最後沿既有 ADR／G6 辦正式接合，不要求整合退役舊碼。
- 退出條件：員工不靠研究者代操作可開始／停止／續談；還原後 scope 與歷史一致，更新不清資料；正式入口與文件只指向已採用的一套保存流程。

## 需要 Owner 配合的驗收

### OI-09｜自然模型與專業品質：需實際付費批次授權
- 現象／影響：新 App 尚無完整自然訪談 JD 的品質證據，合成 SDK／真 DB 通過無法證明顧問會正確提問、寫稿與更正。
- 證據：[RS-6／RS-7](../plans/2026-09-13-jd-relational-app-implementation.md)、[既定品質門檻與合成校準材料](2026-09-10-jd-product-quality-acceptance.md)。
- 下一最小動作：OI-01／02 及相依可靠性齊備後，提出首份案例的資料範圍、模型、呼叫數與費用上限；已有有效授權不重問，未涵蓋者確認後才執行。
- 退出條件：先完成一份自然案例，再按既定 3 職位各 2 次及長訪談驗收；記實際內容、失敗、耗時與用量，重大錯置／捏造／遺漏不能由平均分抵銷。

### OI-10｜目標員工自行操作：需 Owner 安排真人
- 現象／影響：目前研究者的操作不能证明不懂 JD 撰寫的員工能自行完成；真人顧問核准流程仍不在產品範圍。
- 證據：[RS-7 三名員工安排](../plans/2026-09-13-jd-relational-app-implementation.md)、[品質與可用性材料](2026-09-10-jd-product-quality-acceptance.md)。
- 下一最小動作：可試用旅程通過後請 Owner 安排 3 名目標員工，使用既定觀察材料核「開始、訪談、看懂改動、更正、保存、續談」；不新增權限／核准功能。
- 退出條件：實際完成觀察並處理阻斷核心旅程的問題；未安排前如實標「未完成員工試用」，不能由工程代理代填通過。

## 可延後與推進順序

可延後美化：拖曳捷徑、逐字高亮、非阻斷的排版／動畫；保留既有鍵盤移動、完整欄位前後對照及必要錯誤提示。已明示延後：Excel／原始訪談下載、其他電腦安裝、真人顧問交付流程。它們不阻擋本輪 App 收尾，也不改 JD 的關聯結構。

OI-04 工程接合已完成，接著集中 OI-01／02 的顧問、Memory 與來源流程；OI-04 未驗操作隨該完整旅程集中驗收。OI-03 只按新增證據定點處理，OI-05–08 依相依收尾。OI-09／10 的材料可以先備好，費用／真人安排不阻止獨立工程工作；全部尚未達到的退出條件繼續標未完，不以「大致完成」改成成品 PASS。
