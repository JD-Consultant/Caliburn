# JD 編輯核心：Task6 接合與固定驗收

更新：2026-09-12。JD-R002／隔離 G7；BASE `444416722190fd48c14f4423d101f36b25831de1`（Task5 已接受）。**Task6 工程驗收與獨立審查已通過，root已接受；準備精確本地保存，未正式採用。** Task1–5 原接受結果不改判，整體跨切片審查在 Task6 接受後完成。

## 完成效果與責任

同一顧問可以按需使用 JD 方法，從空白訪談到產生結構化稿、修正條件、保留員工手改並續編。App 發配身分／來源／定位，Plate 執行原生操作，PG 保存真版本與操作結果。已保存的完整改動、歷史與原問答在同頁可查；只有一份可編 JD。

本切片只改主顧問能力宣告與只讀方法邊界，新增一份按需 Skill／兩份引用，不改 Memory B/C 文字、策略、模型、預算或三工具 schema。`ADVISOR_INSTRUCTIONS` 在同一 `api.py` 定義供实际 factory 及離線 factory 共用。CT25 golden 原件不變；新增明示三筆 JD capability／metadata／asset-boundary delta，每筆須命中一次。

方法涵蓋何時足以寫稿、案例不直接變永久任務、未知／更正／低頻／責任邊界、平行成果與要求、同版共享 K/S，以及工作→JD、JD→依據核對。其存在與按需供給已測；**自然模型會否正確使用仍待 P3／P6**。

## 實際結果（群組可能重疊，不累加）

| 驗收 | 實際結果與界線 | Raw 證據 |
|---|---|---|
| 全部隔離 Python、無 PG opt-in | **620 passed、151 skipped**，72.54s；skip 不代表 PG 通過 | `task6-final-all.log`／json |
| 真 JD PG／native／managed 程序 | **156 passed**，280.81s，23 個 test_jd 檔，包含新增端到端及來源反例 | `task6-final-jd.log`／json |
| 真 Memory PG／實際 factory | **45 passed**，38.55s；11 個 test_postgres 檔及4組 extraction-role 真 PG factory，保留預算／client／Memory 斷言 | `task6-final-memory.log`／json |
| 原生 Plate | **68 passed**，9檔 | `task6-web-tests.log` |
| 最終 Web | **41 passed**，9檔；含 key-order、終態讀取及延遲差異期間手改保護 | `task6-review-dirty-green.log` |
| SSOT／生成 DTO | **PASS**，same schema and DTOs；無手改生成檔 | `task6-web-codegen.log` |
| 建置／型別／lint | **全部 PASS**；先保留測試fixture型別首敗，再改為完整生成型別 | `task6-web-fix-*.log`／checks.json |
| 真 Chrome 完整旅程 | **PASS**；空白→不足只問→六章初稿＋K/S→月檢條件更正→DOM手改保存→AI續編→純聊天→同頁歷史／來源 | `task6-browser-initial.json`／png／`task6-browser-fixed5.log` |
| 真 API 中斷＋新程序／新瀏覽器 | **PASS**；current、5筆歷史、全部來源／原問答與5次原run結果全相等 | `task6-before-api-crash.json`、`task6-restarted-servers.json`、`task6-browser-reopened.json`／log／png |
| 提交後回覆遺失、純訪談取消 | **PASS**；一版／一份原 ToolMessage／零模型重試；純訪談取消不改 JD | `task6-e2e-result.json`、端到端測試及上列真 JD PG log |
| OS 真人 IME、自然品質、真人使用 | **NOT RUN** | P3／P6 原門檻保留 |

Raw 檔案在 [jd-editor-task6](jd-editor-task6/)。真 Chrome 由 Playwright 1.61.0 的 headed channel 驅動，1500×1050；實際 Chrome 版本在 JSON，不能以套件版本代稱瀏覽器版本。初次完整旅程的 Web 版本包含前兩項同步修正；其後 Claude F5 的最後 guard 另有精確反例及41項 Web 回歸。最終built Web重開再次PASS；修正前的第一次重開JSON／log／png以 `*-before-review.*` 保留，不把較早旅程說成最後guard的實機反例。

隔離 Node 22.23.2；Plate 53.3.11、Slate 0.126.2、宣告 React／DOM 19.2.4、Next 16.3.3；Python3.12.13、既有 uv.lock。DeepAgents0.7.13 保持 Beta 分類，不冒稱穩定；未為追新升級。沿同一 PostgreSQL16兩個專用測試庫；Memory fixture 明示 additive metadata／JD setup，只清理該 test 建立的 UUID，沒有 reset/drop/truncate。

## 首敗與有限修正

### T6-R01：讀本輪原問答後遺失已發配有效性

真端到端原始2項失敗：`read_conversation` 後覆寫 `jd_sources[reference]`，把 App 已發配的 `current_input` 消掉；本輪尚未關閉的來源隨後被錯當一般歷史拒絕。修正只保留同一 reference 已有 metadata 再附實際 tool-call。沒有替未發配、跨文件或被改 payload 的來源補權。

原 BASE overlay 的 focused regression **1 fail／2 pass**；修正後 **3 pass**。兩個陰性守衛仍拒絕未發配較大範圍与偽造 payload。原端到端第二次剩1 fail 為測試誤把來源第一段顧問問句當員工答案，改為精確核對全部 user 段；canonical reader 未改。來源靜態 Claude 審查限定通過，但其 test 檔名猜錯，未完整讀兩個 test；獨立 Codex 反例及主代理真 PG 執行才是測試證據。

### T6-R02：JSONB key 順序造成假的未保存內容

第一輪真瀏覽器首稿2次原生寫入後，已保存正文被 `JSON.stringify` 當成 dirty，下一輪誤先保存旧版並收到 stale base。用正式歷史 `POST /jd/read` 核對，正文結構相等，僅 key 順序不同。修正 `JdEditor`／`JdSession` 的正文 equality，使用已安裝 `fast-deep-equal@3.1.3`；direct dependency及lock僅各1行，MIT，無新 engine。陣列次序／文字／marks／ID／metadata 不被忽略。

保留2項 RED、測試 storage／lookup stub 首敗，最後3檔27PASS。最初診斷誤用 GET query 實際讀到 current，不能作本因證據；更正的 POST 歷史診斷另存 `task6-browser-dirty-diagnostic-corrected.json`。Claude 限定靜態審查通過；它稱 root 套件不處理 Date 的附帶說法與已安裝 source 相反，未採用。

### T6-R03：終態讀取與較早的正文回覆組成舊畫面

真瀏覽器第四次嘗試發現 run 已 completed，但早啟動的 parallel head/messages 讀到舊內容，前端不再輪詢。依終態先於其後讀取建立順序：先讀 metadata/runs，再讀 head/messages，保留 generation checks。延遲 mock 在實際呼叫時取 snapshot，舊碼 **1 fail／2 pass**；修正後3檔27PASS。不聲稱多 HTTP 請求為同一 DB snapshot。

中間另外兩次瀏覽器失敗是測試 locator 同時匹配正文／隱藏高亮及 nested details；改為原 changes region 的直接 before/after details。第五次 `waitForResponse` promise 先 reject、`click` 尚未結束導致證據 finally 未執行，保留原 raw log，**沒有新的截圖可供該次作根因證據**。改用 Playwright 官方常見 Promise.all 等待點擊與回應後，完整旅程通過；不把這些測試故障當額外產品修正。

### T6-R04：差異讀取期間手改可能被晚到正文蓋掉

Claude F5 提供具體反例，root建立延遲 change-read 後手改的測試。**RED 1 fail／3 pass**，畫面 buffer 變成「AI 新稿」，確認資料遺失可能。最小修正：await changes 後、套用 head 前再核 dirty；若已手改，保留原 buffer／saved baseline並顯示既有通知。沒有新增保存、重試、rebase或全域鎖。RED保留同情境原inline fixture，最後 **41 Web PASS**；新增 fixture 以完整生成型別提供資料，首個 build 的 TS2352失敗保留。

### 既有回歸 fixture 與環境故障

全Python首跑 **15 fail／609 pass／147 skip**：5個舊建立文件測試沒帶 Task4已要求的request key；4個 real factory SQLite替身不符現已要求真JD PG；2個CT25 AST只接受literal；4個未知寫入stop仍期待拋錯、而Task5已回uncertain。只修測試接點，保留錯誤封鎖、原 golden／Memory政策、真模型預算／角色／client生命週期。4組factory轉真PG實際執行，不能以新增skip省略。

Memory首跑 **16 fail／25 pass**，既有測試库缺metadata欄位；明示additive test setup後45PASS。另保留sandbox Docker拒絕及舊basetemp權限故障；改用新擁有的測試暫存目錄和允許的managed執行，沒有繞過資料庫守衛或刪舊現場。部分Windows managed測試外層exit0仍可含pytest FAIL，所有結果以raw pytest summary核實。

## 官方依據與本案映射

| 資料／查閱 | 官方事實、版本／授權與限制 | 本案使用 |
|---|---|---|
| [OpenAI Skills](https://learn.chatgpt.com/docs/build-skills)、[Anthropic Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)，2026-09-11 | 先metadata、再按需正文／材料。託管產品能力各有條件，不採它們的付費code execution；詳[前置證據](../2026-09-11-jd-skill-current-official-preflight.md) | 一份既有顧問的按需方法，檔案數／JD專業內容是本案取捨，不稱供應商統一方案 |
| [PostgreSQL16 JSON](https://www.postgresql.org/docs/16/datatype-json.html)，2026-09-12 | jsonb不保留object key順序；PG16 supported、PostgreSQL License | 不用JSON序列字串判斷正文語意相等 |
| [PostgreSQL16 Read Committed](https://www.postgresql.org/docs/16/transaction-iso.html)，2026-09-12 | statement依起始時的已提交資料讀取；不同讀取可看到不同提交 | 終態先讀、其後才取得內容是App因果順序；不是大廠指定的前端架構／原子快照 |
| [Plate controlled value](https://platejs.org/docs/controlled)，2026-09-12 | Plate管理editor狀態；原生操作／外部value更新有既定接點。實裝53.3.11 MIT，無付費擴充 | 保留既有native batch及必要重建分支，修正baseline比較，不另造編輯器 |
| [React useEffect](https://react.dev/reference/react/useEffect)，2026-09-12 | 非同步回覆可亂序，cleanup／忽略舊結果有官方示例；React19 MIT | 沿既有generation與dispose guard，額外在真正套用時重核人工buffer |
| [fast-deep-equal](https://github.com/epoberezkin/fast-deep-equal#readme)，2026-09-12本機source核對 | 實裝3.1.3、MIT；比較object內容及有序array，已在lock | 宣告直接使用的既有依賴；不把單一套件稱跨廠共識 |

只將有跨來源支持的按需方法、依真工具結果、明確資料責任稱共同原則。資料表、具體refs、UI順序及恢復接法仍是已有設計的本案映射。沒有推測OpenAI／Anthropic未公開的JD資料庫內部實作。

## 審查及剩餘 gate

Claude Opus5經用戶明確授權，只讀相關隔離程式／測試／technical synthetic材料，排除秘密、帳號及真實訪談。保留實際CLI model、Read工具、無MCP與使用結果；CLI估價不是訂閱實際帳單。前三次限定review加本次 correction review 不代稱整體Task6／core approval。F5已由root重現修正；F4所指JD工具覆蓋在 `test_jd_end_to_end.py` 的最終SDK payload逐schema／description比對，無須新增平行golden。其餘低風險建議未構成觀察到的產品缺口，保留範圍說明。

[獨立審查與root closure](jd-editor-task6/review.md)已通過，I1文件計數更正、F5 CLOSED。下一gate：精確本地commit→整體跨切片審查／tag。之後按成品計畫進P3自然模型費用防護與案例授權、P4 successor ADR/G6、P5啟停／備份還原／更新、P6長訪談及三名員工、P7本機交付。現有正式ADR0060權責不變，未merge／push／正式部署。原先AGENTS更新、README11行與其他Memory研究不混入本切片。

## 2026-09-12：核心整體交接

Task6已保存於`3d0445ae2d4b3bb2ef3493f703ea18f0108b0eef`。其後[整體review與有限修正](jd-editor-core-review/review.md)完成，F1–3及R1–2 CLOSED；最後47 Web／86受影響Python／19真PG、build/types/lint與真Chrome短恢復流程通過。R3/R4呈現Minor列P5，原Task6未驗界線不變。六切片隔離核心已接受；自然品質與正式產品未交付。
