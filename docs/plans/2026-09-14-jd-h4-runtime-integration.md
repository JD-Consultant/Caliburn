# H4：B1／B2／顧問接入新 JD App 的執行計畫

2026-09-14；JD-R002／OI-01、OI-02。依[整體審查](../specs/evidence/jd-b1-adoption/whole-flow-review.md)與[採用映射](../specs/2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)。本稿接替[9/13 交接計畫](2026-09-13-jd-app-continuation-handoff.md) H4 的詳細施工順序；H1–H3 已完成，H5 與產品範圍不變。**本稿是待執行計畫，不是 runtime 完成報告。**

## 1. 接手先確認的現況

| 範圍 | 基準與施工界線 |
|---|---|
| 程式 | `S:/caliburn`；`refactor/current-only-architecture`；**R1 完成於 tag `jd-h4-r1-postgres-batch-20260914`**（原基準 `f160be97` 是 R1 之前）。先核實 HEAD 是否被後續合法提交推進，保留其他 dirty |
| 已完成 | 關聯式 JD 管理／共同保存、前景聊天固定接合、C 即時 Memory 修補與恢復、source port、B1 核心與 OpenAI 固定 adapter。**R1 亦已完成**：固定 target→有界批次、一批 B1 的真 PG 保存與資源重建續作（[批次接點](../specs/evidence/jd-b1-adoption/fixed-target-batch-results.md)、[R1 結果](../specs/evidence/jd-b1-adoption/r1-postgres-batch-results.md)）。不可重做 CA-01／02、window parser、pair proof、B1 prompt 或 R1 |
| 本段待做 | **R2 已完成**（tag `jd-h4-r2-consolidation-20260914`）。**R3 進行中**：純通知辨識、准入表與 dispatch、宿主有限 worker 與排空已完成；[顧問指引、三項分析 Skills、Memory 行動指引與背景可用性](../specs/2026-09-14-jd-consultant-guidance-and-skills-slice.md)已完成（tag `jd-consultant-guidance-skills-20260914`）。**剩下 R3 第 7 項**：真新 Windows 程序＋真 PG 的四個停點續作；以及把 `build_consultant()` 接進日常入口 |
| 此刻禁止宣稱 | 日常自然訪談可用、H4 完成、**B1 已有新 Windows 程序證據**。既有 C／source 的 14 PG 案例不算 B1 PG；R1 的真 PG 證據只涵蓋同程序內的資源重建 |
| 真模型 | 工程全程合成 HTTP、假 key、0 provider；API key 設定接線不等於獲准呼叫。自然驗收及正式採用沿 H5 |

先讀本稿、映射 §3–5、窗口契約 §3／7／8、9/13 C 接合結果與 App README 中環境／PG段落。需改哪個子系統才往相應責任稿讀，不再逐輪閱讀全部舊聊天。

## 2. 必須完成的一條流程

員工說明工作 → A 訪談或更正 JD／C → 原回合安全收尾 → 有有效整理通知時 App 固定未處理範圍 → B1 產生詳記／候選 → B2 整併並發布 → 下一輪 A 讀到目前理解及未涵蓋通知 → 適時撰寫／更正同一份 JD。

- B1 是條件觸發的後台整理階段，不是每句話固定加一次呼叫、不直接寫 JD、不代表更新目前 Memory。
- `failed`／`cancelled` 的安全回合仍保留員工原話；沒有成功答案便如實標示。被門閘阻擋而未安全收尾的回合不能被越過。
- 純通知只表示收到整理意圖；只有 B2 的原 publication 結果能证明已整併範圍。未整理的近期原話仍供 A 使用，不能強迫訪談等待每批整理完。
- 人改 JD 的通知保持 App context，不冒充原話、不自動更改 Memory。撤回 JD 不撤回 Memory／詳記／原話；不另接舊 JD editor。

## 3. 寫入者與檔案範圍

| 責任／範圍 | 可做的有限接合 | 不得代替的權威 |
|---|---|---|
| `jd_relational/conversation_sources.py` | 固定 target 的有界 batch ref；錯誤／purpose／lineage 全交既有 owner | 背景端不得解 token、重算訊息範圍、重設 publication cursor |
| `caliburn_memory/extraction.py` | 原已驗 B1；本段預期無須改 prompt／流程。若有反例才窄修并記 adoption 差異 | 不承擔宿主、原話、排程或 JD |
| `caliburn_memory/consolidation*.py` 等正常套件落點 | 自 `4f94fbfb` 採用 B2、暫存工具與已驗方法；逐檔來源/hash/調整記 adoption | 不 import 研究路徑，不整批搬舊 service／API |
| App 的 `extraction_app.py` 與 B2 adapter | provider／角色組裝、source reader 授予、例外邊界；沿原模型預算 | 不重寫另一套抽取／整併迴圈，不同 provider 的接受條件不混用 |
| App background admission／host owner | 映射 §3.3 的最小准入列、原 B job 對帳、有限 dispatch、資源關閉 | Saver 擁有 B 進度；publication 擁有目前 Memory 和唯一 `processed_source` |
| `consultant_tools.py`／`ai_runtime.py`／顧問組裝 | 純通知的分類、執行／未執行／安全收尾；採用 A 指引與分析 Skills；加入必要 JD 方法差異 | 通知不能借 JD operation 或 C receipt；不以假成功工具結果補未知 |
| 初始化／配置／README | 明示 migration、角色配置、缺設定與背景狀態出口、package 安裝說明 | 平常 open 不 setup；金鑰不進 prompt、DB artifact 或診斷輸出 |

精確模組名可按現有責任調整；每次一位 writer。僅新增內部接點不必改 Web schema；若新增公開狀態投影，依 `docs/contract-strategy.md` 由正式來源生成並跑相應檢查，不手改 generated。

## 4. 三個完整施工單位

### R1｜固定的一批 B1，真 PostgreSQL 保存與原工作恢復

這是**下一個單位**。它不需要先註冊通知，也不需要啟用日常 AI。

1. 依映射 §3.6，在 source owner 補「固定 target＋publication cursor→最多 N 個窗口的 batch ref」。輸入原完整 token，輸出仍在同一 root 的連續未處理前綴 ref 及 `covers_whole_range`；已涵蓋才回明確空結果，整批首尾由 owner 派生。沿原 `_plan`／`plan_saved_windows`，不要把 `windows[:N]` 塞成 B1 新輸入型別，或把相對latest的`unprocessed_source`當原target剩餘範圍。
2. 以實際 App `build_extraction_workflow`、既有 OpenAI adapter、`PostgresSaver`／`PostgresStore` 執行一批。固定 B1 `max_windows=16`、更正 1、輸出 8192／effort high；fixture 可故意降低批量來驗兩批。模型 id 依已驗 profile 的現行組裝配置，不從測試 fixture 的字串猜產品選型。
3. 故障注入在可辨識邊界：模型結果 checkpoint 後、summary 寫入後 candidates 前、兩產物成功但 save checkpoint 未確認。關閉並重建資源，以原 config `resume()`，驗已保存模型結果不再呼叫 HTTP，最後 `files` 可讀、引用固定、未發佈產物不進目前 Memory。
4. 保留允許的未引用 Store 產物證據；不要要求跨 Store／Saver 原子提交或新增一般 GC／outbox。若模擬的是模型回覆後、checkpoint 前的未知位置，不可斷言 0 次重呼叫；按持久位置及原預算明示可能再次呼叫，與保存階段恢復分開。
5. 驗最近相同 input 的查回、pending 時拒換 input、原 source/context pair 重抽及正常 B1 位置不前進。沿既有已通過固定案例，不重新擴張成任意損壞資料修復系統。

**完成：**有界批次與 B1 的真 PG 交接／資源重建證據、實際 source／files／HTTP 次數、首敗和限制；独審後窄複核。這仍不是新 Windows 程序／B2／日常背景完成。

### R2｜B1 的結果交給 B2，發布後下一批才前進

1. B2 從原已完成 B1 checkpoint 的 `files` 取材；保留原 `start`／`resume`／`start_reextraction`、原 request 身分、stale→load、`RECENT_REPAIRS` 與已用預算。prompt、三項分析 Skills 的已驗方法不趁接合改寫。
2. 先列 `4f94fbfb` B2 直接依赖與現有正常套件逐項對應，再只採用缺少部分；不是整批把所有檔案複製過來。provider assembly 按原 OpenAI 已驗路徑與目前 SDK 核 wire，A 的 Anthropic 配置不動；若需變更 provider 或方法，列成獨立差異，不假稱 CT 品質沿用。
3. **同文件只能有一筆未交接完的 B 批次。**B1 完成後先 B2；B2 未發布／受阻，不允許 B1 用新範圍重置最近 `files`。不掃 Store 目錄找「可能尚未處理」的詳記來代替原交接。
   **（2026-09-14 移交 R3）**R2 驗證了正確順序及其耐久性，但**沒有**加入阻擋門閘：獨立審查已重現「B1 在 B2 未發布時用相鄰新範圍重置 `files`，游標隨後永久越過前一批」。`follows()` 只比對 B1 自己的上一個範圍，不看 publication head。**R3 的 admission 必須關掉它**：只讓 `plan_saved_batch(target, after_reference=publication.current().processed_source)` 的輸出進 `b1.start()`，並要求 B1 snapshot 的 `source_reference` 已等於該 `processed_source`（head 為 None 時要求 B1 無 values），並補一條跳號反例。不得因本條寫在 R2 就認為 R2 漏做而重開 R2。
4. B2 原发布 request／receipt 对帳成功後，以 publication `processed_source` 判覆蓋；未覆蓋原 target 的尾端繼續下一批，沒有新通知也不得漏尾端。完成 B1 或更新准入狀態均不可自行推游標。
5. 在 B2 讀基準後插入 C 更正；必須沿既有失效基準重讀與修補來源重做，在剩餘預算內發布。不能單換版本號把舊內容蓋回。B2 發布成功但回覆遺失時原 request 查回，不再次模型整併、不倒退現在 head。

**完成：**固定 SDK＋真 PG 至少一條兩批交接、B1完/B2未開始、B2 pending、發布回覆遺失及 C 介入更正情境；JD／原話完全不被背景直接寫入。可以在測試宿主直接驅動，不代表日常喚醒已接。

### R3｜完整通知、宿主生命週期與顧問方法一起接好

1. 依映射 §3.3 明示初始化最小准入狀態。沿同一宿主既有 lease／資源管理登記 B 工作；不得在 middleware getter、`BackgroundDispatcher.__init__` 或普通 open 偷做 setup。
2. 純通知工具作完整單位：註冊、已保存 call/result 辨識、結果分類、停止前未執行、已執行但回覆未保存、未知位置、復原與 `_settle`。原生證據不足時保留未知；不假造 JD 的 `_not_executed()` 或 C publish 成功。十五個工具是舊基線，不是不可增加；核真 request 工具清單與身份，而非只改 count 斷言。
3. 同時採用 A 基本指引、`work-scope-interview`／`compare-work-patterns`／`outcomes-and-expertise`、SkillAssets 及按需載入、`MEMORY_ACTION_GUIDANCE`／`BackgroundAvailability`。只修原來「不製作 JD」的範圍限制，JD 撰寫規則映射六章研究；保存精確差異。把 `jd_read`／`jd_edit`／`jd_change_read` 接到同一個 JD domain writer：員工手改與 LLM 都走同一組欄位／關聯／版本／operation 規則，App 產生並驗證文件身分、版本、引用與保存結果，LLM 不直接填資料庫欄位或自行拼接定位 token。這是接合既有契約，不新增第二個 JD 寫入者或另一套審核引擎。
4. 完成安全回合與啟動恢復時喚醒同一背景入口；喚醒可重複，持久准入／原工作決定能否執行。新批次必須有有效請求，字數後備預設不啟用；原來已准入的工作按原狀態續作。採既有宿主的有限 worker 接點，沒有則使用標準 executor 執行有界批次；不加入新長駐服務、分散式 queue 或無限 Future loop。
5. 普通關閉：停止前景與背景新准入 → 等已登記的有限工作真的退出 → 關模型 client／Store／Saver／engine。不得持有全 App 鎖等 Future；未開始工作留持久狀態。重啟先沿既有 Windows 前宿主死亡證據取得宿主，找原 B job 續作；不把 `running` 當不存在，不把 timeout 當已停止。
6. 接本機角色配置與狀態出口。缺 OpenAI key 時人工 JD 仍可用；未啟用模型不呼叫 provider，不因已有 Anthropic key 就 fallback B1。整理受阻／未涵蓋通知交 App context，不要求員工判斷模型品質，也不把通知假寫成對話原話。封存停止新B批次，執行中批次可完成；原狀態保留，恢復文件後核原工作續作，按映射§3.3驗收。
7. 用真新 Windows 程序＋真 PG 驗以下原停點後續作：B1 模型已保存、B1完成/B2未開始、B2未發佈、B2已發佈僅回覆遺失。分别断言允许的 HTTP／寫入次數及原工作身份；由新程序取回，不沿用原 Python 物件。

**H4 完成：**新 App 固定完整旅程能訪談、按需要整理、更正 Memory／JD、讀早期來源、續談與重開；當輪真實 JD 差異可查，取消／排空不謊報。0 provider 完成後才進 H5 的自然案例，不把固定模型指令等同顧問自主品質。

## 5. 准入／恢復判斷順序

本表引用映射的六欄准入設計；不是第二份 graph state。

| 觀察到的持久事實 | 唯一允許的下一步 |
|---|---|
| 無未完成 B；無未覆蓋通知；字數後備關閉 | 不啟動 B；保留原話供後續訪談 |
| 有未覆蓋通知且安全連續來源可取 | 固定 target；切固定 batch，先保存准入資料再 invoke B1 |
| B1 有 pending checkpoint | 驗原批次／原 config 後 `resume`；不可以新 source 重新 start |
| B1 已完成且 B2 未開始 | 交原 `files` 給 B2，不覆寫 B1 最近輸入 |
| B2 有 pending checkpoint | 原工作续作；若已有原 receipt，沿原核對路徑收尾 |
| B2 原 receipt 已存在、較晚 C 又更版 | 核原發布結果，不讓原回執把目前 head 拉回；不重新跑 B1／B2 |
| 本批已發布，原 target 還有尾端 | 由唯一 publication cursor 決定下一批；保存新的 batch ref，target 保留 |
| blocked／來源受限／預算耗盡 | 保留原工作與原因，通知受阻；無根因變化不每次喚醒重試、不重啟清額度 |

同一個 SDK 500 重試只是一個模型步的傳輸嘗試；模型 schema 更正另記 B1 額度；宿主恢復次數另依已驗政策保留。新增模型步仍消耗原工作限制，不把 `resume` 當免費無限重試。

## 6. 驗收與審查規範

- 新的可靠性修正先有反例；若測試一寫就通過，標補證據。若變異測試要宣稱有鑑別力，確認變異真的套用，恢復後核 hash；記執行者，不能將作者變異結果寫成獨立審查實跑。
- 最少覆蓋：一批及多批、無通知、重複喚醒、未收尾回合、failed/cancelled原話、B1/B2交接斷點、C較晚更正、原發布結果遺失、關閉／新程序、另一文件與前景不被 B 大鎖拖住。各情境可共用一條旅程，不要求每個小分支都拆成一個交付。
- 保存前／後分層：InMemory 固定證據、真 PG 資源重建、真新程序、瀏覽器、自然模型、真人分開。不要累加重疊測試數；舊 14 PG 不反覆冒稱新 B1 已驗。
- Package 改動更新 adoption 精確 hash、依賴與 wheel；僅 App 接法變動不捏造 prompt 變更。跨接點改動核公開 API／本機已裝版本，不 import 私有框架方法。
- 先跑受影響組；完成 R1／R2／R3 各單位再跑它的必要回歸與獨審。通過後只有新反例才重開，不每次修一行都全跑2800測試並重寫一輪架構報告。
- 審查 finding 必须给可定位的契約／程式與反例、影響層級、最小修法。區分「現存 bug」「下一片未接」「文件過期」「可延後建議」。不能因資料表新增、存在自有業務函式或框架沒有代管所有語意，就判為過度設計。
- v1 context 遇到時明示不支援，fresh fixture使用v2；沒有舊資料轉換子專案。不因假設中的舊資料阻止 R1 施工；也不為通過驗收清掉已有資料。
- 未解問題繼續進 OI-01／02／05 等既有清單。256祖先限制仍是長訪談待解，不在 R1 趁機建通用歷史索引。

執行命令／資料庫範圍沿 [9/13 交接 §7](2026-09-13-jd-app-continuation-handoff.md#7-接手操作與驗收命令)與 App README。真 PG 只用既定專用 fixture；不改正式 DB、不自動 setup、不清 volume，真模型另依已涵蓋授權執行。每個完整單位交：精確程式差異、反例與結果、限制、獨審／窄複核、正常套件／README同步、精確 commit/tag；不 merge／push。
