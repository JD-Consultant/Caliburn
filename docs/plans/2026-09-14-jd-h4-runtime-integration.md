# H4：B1／B2／顧問接入新 JD App 的執行計畫

> 2026-09-16 閱讀校正：產品目標為 [一個由人與 LLM 共編 current JD 的 App](../product-notes.md)。下方 Anthropic、直連 OpenAI、模型未選與完整 JD 歷史／還原等敘述有施工時間差；目前模型路徑以 [目前決策](../current-decisions.md) 的 framework＋OpenRouter＋OpenAI Luna 為準。首版只需當輪 LLM 的 JD 差異與整輪撤回，原始對話／Memory 不撤回。R3 新程序結果見 [R3 證據](../specs/evidence/jd-b1-adoption/r3-notification-and-background-results.md)。正式組裝已把既有顧問 graph、單一 OpenRouter credential 與 `enable_chat=True` 接進日常 `serve`；B1 也已走同一 OpenRouter 邊界，背景提示的文件與本回合目前 Memory 讀取基準改由每次 runtime 執行提供。一般讀取不追逐背景最新 head；C 準備修改時才明確刷新，保存仍使用既有 CAS，成功後本回合固定在 C 實際產生的版本。B2 若依舊版完成候選，必須 stale→讀新版→重新整理，不能換版號重送；B2 後續發布也不自動推進前景本回合。缺 key 時仍只開人工 JD。2026-09-15 的 OpenRouter native compaction smoke 保留為 `SERVER-UNVERIFIED` 證據，但 Owner 已於 2026-09-16 結束 transport 三選一：A／B2 改採 [OpenRouter／Luna App-side continuity compaction](../specs/2026-09-16-openrouter-continuation-compaction-design.md)，不切 direct OpenAI、不等待原生 item、不改主顧問 Prompt 或 Memory 語意。背景 dispatcher、真 PG／新程序完整 App 旅程與之後的完整自然 smoke仍待後續。C 是前景即時 Memory 修補，B1/B2 是背景抽取／整併，不得把舊狀態當成新需求。

2026-09-15 接縫進度：既有 Responses request-only view 已抽為 A／B2 可共用、未綁 provider 的 Responses middleware；B2 保持原組裝，A factory 已可注入，但正式 A runtime 刻意不注入任何未驗候選。這只先閉合 graph 接點，不是 transport 選擇、正式改線或長對話通過。同步邊界已沿實際呼叫鏈核對：A 的 admission 背景工作最終使用 `graph.invoke(..., durability="sync")`，B2 的 start／resume／attempt 也使用同步 `invoke()`；沒有真實 A／B2 async 模型入口，因此不加 `awrap_model_call`。B2 的 context 是單次有界整併嘗試，不是全員工訪談；Memory、B1、C 與原話範圍不變。本次沒有引入或核准全歷史替代方案；transport 未決只限此 context 切片，dispatcher 與完整 App 驗收仍按本計畫另行閉合。

2026-09-14；JD-R002／OI-01、OI-02。依[整體審查](../specs/evidence/jd-b1-adoption/whole-flow-review.md)與[採用映射](../specs/2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)。本稿接替[9/13 交接計畫](2026-09-13-jd-app-continuation-handoff.md) H4 的詳細施工順序；H1–H3 已完成，H5 與產品範圍不變。**本稿是待執行計畫，不是 runtime 完成報告。**

## 1. 接手先確認的現況

| 範圍 | 基準與施工界線 |
|---|---|
| 程式 | `S:/caliburn`；`refactor/current-only-architecture`；**R1 完成於 tag `jd-h4-r1-postgres-batch-20260914`**（原基準 `f160be97` 是 R1 之前）。先核實 HEAD 是否被後續合法提交推進，保留其他 dirty |
| 已完成 | 關聯式 JD 管理／共同保存、前景聊天固定接合、C 即時 Memory 修補與恢復、source port、B1 核心與 OpenRouter／OpenAI-only Luna adapter。**R1 亦已完成**：固定 target→有界批次、一批 B1 的真 PG 保存與資源重建續作（[批次接點](../specs/evidence/jd-b1-adoption/fixed-target-batch-results.md)、[R1 結果](../specs/evidence/jd-b1-adoption/r1-postgres-batch-results.md)）。不可重做 CA-01／02、window parser、pair proof、B1 prompt 或 R1 |
| 本段待做 | **R2 已完成**（tag `jd-h4-r2-consolidation-20260914`）。純通知辨識、准入表與 dispatch、宿主有限 worker／排空、顧問指引／Skills／Memory 行動指引都有既有成果；`build_consultant()` 的正式前景入口、B1 OpenRouter route 與 runtime 動態文件 scope 已於 2026-09-15 閉合。A／B2 長對話已由 Owner 裁決採 App-side continuity compaction，下一先做下方 R2C 單一切片；正式 background callback／dispatcher 與真 PG／新程序完整旅程仍未閉合，不重做顧問方法 |
| 此刻禁止宣稱 | 日常自然訪談已由本切片重新驗收、H4 完成、背景已接入正式入口。既有分段 PG／新程序證據不能取代新的完整 App 組合證據 |
| 真模型 | 本計畫原工程切片使用合成 HTTP／假 key；其後另經 Owner 授權完成 1 次有界 OpenRouter compaction smoke（US$0.00556460，結果 `UNVERIFIED`）。這不等於自然顧問、完整 App 或正式採用驗收；其餘仍沿 H5 |

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
| `consultant_tools.py`／`ai_runtime.py`／顧問組裝 | 純通知的分類、執行／未執行／安全收尾；沿已校準 A 指引與分析 Skills；只加入 JD tools、App context 與必要的「可編輯 JD」範圍差異 | 不重寫訪談 prompt、Skills、Memory 判斷或通知的模型可見描述／時機／語意；通知不能借 JD operation 或 C receipt；不以假成功工具結果補未知 |
| 初始化／配置／README | 明示 migration、角色配置、缺設定與背景狀態出口、package 安裝說明 | 平常 open 不 setup；金鑰不進 prompt、DB artifact 或診斷輸出 |

精確模組名可按現有責任調整；每次一位 writer。僅新增內部接點不必改 Web schema；若新增公開狀態投影，依 `docs/contract-strategy.md` 由正式來源生成並跑相應檢查，不手改 generated。

## 4. 三個完整施工單位

### R1｜固定的一批 B1，真 PostgreSQL 保存與原工作恢復

這是**下一個單位**。它不需要先註冊通知，也不需要啟用日常 AI。

1. 依映射 §3.6，在 source owner 補「固定 target＋publication cursor→最多 N 個窗口的 batch ref」。輸入原完整 token，輸出仍在同一 root 的連續未處理前綴 ref 及 `covers_whole_range`；已涵蓋才回明確空結果，整批首尾由 owner 派生。沿原 `_plan`／`plan_saved_windows`，不要把 `windows[:N]` 塞成 B1 新輸入型別，或把相對latest的`unprocessed_source`當原target剩餘範圍。
2. 以實際 App `build_extraction_workflow`、provider adapter、`PostgresSaver`／`PostgresStore` 執行一批。9/14 當時用直連 OpenAI adapter 完成的結果只證明 workflow 接縫；正式組裝須改走 LangChain／LangGraph 的 OpenRouter adapter，固定 OpenAI provider、禁止 fallback。B1 `max_windows=16`、更正 1、輸出 8192／effort high；fixture 可故意降低批量來驗兩批。模型 id 依已驗 profile 的現行組裝配置，不從測試 fixture 的字串猜產品選型。
3. 故障注入在可辨識邊界：模型結果 checkpoint 後、summary 寫入後 candidates 前、兩產物成功但 save checkpoint 未確認。關閉並重建資源，以原 config `resume()`，驗已保存模型結果不再呼叫 HTTP，最後 `files` 可讀、引用固定、未發佈產物不進目前 Memory。
4. 保留允許的未引用 Store 產物證據；不要要求跨 Store／Saver 原子提交或新增一般 GC／outbox。若模擬的是模型回覆後、checkpoint 前的未知位置，不可斷言 0 次重呼叫；按持久位置及原預算明示可能再次呼叫，與保存階段恢復分開。
5. 驗最近相同 input 的查回、pending 時拒換 input、原 source/context pair 重抽及正常 B1 位置不前進。沿既有已通過固定案例，不重新擴張成任意損壞資料修復系統。

**完成：**有界批次與 B1 的真 PG 交接／資源重建證據、實際 source／files／HTTP 次數、首敗和限制；独審後窄複核。這仍不是新 Windows 程序／B2／日常背景完成。

### R2｜B1 的結果交給 B2，發布後下一批才前進

1. B2 從原已完成 B1 checkpoint 的 `files` 取材；保留原 `start`／`resume`／`start_reextraction`、原 request 身分、stale→load、`RECENT_REPAIRS` 與已用預算。prompt、三項分析 Skills 的已驗方法不趁接合改寫。
2. 先列 `4f94fbfb` B2 直接依赖與現有正常套件逐項對應，再只採用缺少部分；不是整批把所有檔案複製過來。workflow／prompt 沿已驗結果，provider assembly 統一走 OpenRouter profile；A、B1、B2 都固定 OpenAI provider 並禁止 fallback，但可保留各自模型參數。9/14 的「A Anthropic 配置不動」已失效，不得照做。
   **2026-09-16 接線註記：**A 與 B1 已完成 OpenRouter 基本組裝；完成版 A／B2 的舊接縫使用 Responses inline `context_management`／compaction 12000。官方契約與真 smoke 仍只證明 OpenRouter 此路徑沒有產生必要 item，不能再以 synthetic wire 或 HTTP 200 猜測未知 pass-through。Owner 已裁決不等待該能力、也不切 direct OpenAI；下一以 R2C 的 App-side continuity compaction 閉合 A／B2，既有 `native_context_view` 與 adapter gate 留作歷史／characterization 證據，不再是正式路徑。
3. **同文件只能有一筆未交接完的 B 批次。**B1 完成後先 B2；B2 未發布／受阻，不允許 B1 用新範圍重置最近 `files`。不掃 Store 目錄找「可能尚未處理」的詳記來代替原交接。
   **（2026-09-14 移交 R3）**R2 驗證了正確順序及其耐久性，但**沒有**加入阻擋門閘：獨立審查已重現「B1 在 B2 未發布時用相鄰新範圍重置 `files`，游標隨後永久越過前一批」。`follows()` 只比對 B1 自己的上一個範圍，不看 publication head。**R3 的 admission 必須關掉它**：只讓 `plan_saved_batch(target, after_reference=publication.current().processed_source)` 的輸出進 `b1.start()`，並要求 B1 snapshot 的 `source_reference` 已等於該 `processed_source`（head 為 None 時要求 B1 無 values），並補一條跳號反例。不得因本條寫在 R2 就認為 R2 漏做而重開 R2。
4. B2 原发布 request／receipt 对帳成功後，以 publication `processed_source` 判覆蓋；未覆蓋原 target 的尾端繼續下一批，沒有新通知也不得漏尾端。完成 B1 或更新准入狀態均不可自行推游標。
5. 在 B2 讀基準後插入 C 更正；必須沿既有失效基準重讀與修補來源重做，在剩餘預算內發布。不能單換版本號把舊內容蓋回。B2 發布成功但回覆遺失時原 request 查回，不再次模型整併、不倒退現在 head。

**完成：**固定 SDK＋真 PG 至少一條兩批交接、B1完/B2未開始、B2 pending、發布回覆遺失及 C 介入更正情境；JD／原話完全不被背景直接寫入。可以在測試宿主直接驅動，不代表日常喚醒已接。

### R2C｜A／B2 的 OpenRouter／Luna App-side continuity compaction

本切片只依[正式設計](../specs/2026-09-16-openrouter-continuation-compaction-design.md)施工，不再重開 transport 或 Memory 原理：

1. 以公開 LangChain／LangGraph middleware 接點新增 typed `continuation_compaction`，只保存 summary＋安全邊界＋canonical prefix digest；canonical `messages`、B1 source、Memory／JD authority 不變，不新增 table、migration、dependency 或歷史 UI。
2. 沿既有 OpenRouter model factory 進行摘要，固定 OpenAI-only／no-fallback／hidden retry 0，納入 route／usage／token／cost receipt。起始 profile 為 16k trigger、至少 8 messages、2048 summary output；完整 request 計算包含 instructions、JD／Memory context、tools 與輸出預留。
3. 修正 `JdNoticeMiddleware` 接受並保留內層 `ExtendedModelResponse` command，使 `jd_model_view` 與 `continuation_compaction` 同時保存；不改主顧問 Prompt。正式 A 注入 middleware。
4. B2 改走同一 OpenRouter boundary；同 attempt 可恢復，stale 新 attempt summary 為空。移除其正式 direct Responses／native compaction 依賴，但保留原 adapter contract／smoke 文件作歷史證據。
5. 跑設計 §9 的受影響離線反例與既有 A／B2／C／JD 鄰接回歸。通過後先回報；付費自然 smoke 另依既有授權，不由本切片自動執行。

**完成：**A／B2 都能在 canonical 原文未變、工具配對完整、文件隔離與 stale attempt 清空成立時，從保存的 continuity summary 接續；失敗不前移 boundary、不隱藏成本。這只關閉長對話接線，不代表 dispatcher 或完整 App 旅程已完成。

### R3｜完整通知、宿主生命週期與顧問方法一起接好

1. 依映射 §3.3 明示初始化最小准入狀態。沿同一宿主既有 lease／資源管理登記 B 工作；不得在 middleware getter、`BackgroundDispatcher.__init__` 或普通 open 偷做 setup。
2. 純通知工具作完整單位：註冊、已保存 call/result 辨識、結果分類、停止前未執行、已執行但回覆未保存、未知位置、復原與 `_settle`。直接採用原顧問已校準的 `request_memory_consolidation` 模型可見描述、判斷時機與觸發語意，不因接線重寫；只有可重現的框架相容性或正確性問題才作最小修正並保存差異／回歸證據。原生證據不足時保留未知；不假造 JD 的 `_not_executed()` 或 C publish 成功。十五個工具是舊基線，不是不可增加；核真 request 工具清單與身份，而非只改 count 斷言。
3. 同時採用 A 基本指引、`work-scope-interview`／`compare-work-patterns`／`outcomes-and-expertise`、SkillAssets 及按需載入、`MEMORY_ACTION_GUIDANCE`／`BackgroundAvailability`。只修原來「不製作 JD」的範圍限制，JD 撰寫規則映射六章研究；保存精確差異。把 `jd_read`／`jd_edit`／`jd_change_read` 接到同一個 JD domain writer：員工手改與 LLM 都走同一組欄位／關聯／版本／operation 規則，App 產生並驗證文件身分、版本、引用與保存結果，LLM 不直接填資料庫欄位或自行拼接定位 token。這是接合既有契約，不新增第二個 JD 寫入者或另一套審核引擎。
4. 完成安全回合與啟動恢復時喚醒同一背景入口；喚醒可重複，持久准入／原工作決定能否執行。新批次必須有有效請求，字數後備預設不啟用；原來已准入的工作按原狀態續作。採既有宿主的有限 worker 接點，沒有則使用標準 executor 執行有界批次；不加入新長駐服務、分散式 queue 或無限 Future loop。
5. 普通關閉：停止前景與背景新准入 → 等已登記的有限工作真的退出 → 關模型 client／Store／Saver／engine。不得持有全 App 鎖等 Future；未開始工作留持久狀態。重啟先沿既有 Windows 前宿主死亡證據取得宿主，找原 B job 續作；不把 `running` 當不存在，不把 timeout 當已停止。
6. 接本機角色配置與狀態出口。缺 OpenRouter credential 時人工 JD 仍可用；未啟用模型不呼叫 provider，也不得 fallback 到 Anthropic 或其他 provider。整理受阻／未涵蓋通知交 App context，不要求員工判斷模型品質，也不把通知假寫成對話原話。封存停止新 B 批次，執行中批次可完成；原狀態保留，恢復文件後核原工作續作，按映射 §3.3 驗收。
7. 用真新 Windows 程序＋真 PG 驗以下原停點後續作：B1 模型已保存、B1完成/B2未開始、B2未發佈、B2已發佈僅回覆遺失。分别断言允许的 HTTP／寫入次數及原工作身份；由新程序取回，不沿用原 Python 物件。

**H4 完成：**新 App 固定完整旅程能訪談、按需要整理、更正 Memory／JD、讀早期來源、續談與重開；當輪真實 JD 差異可查，取消／排空不謊報。固定／synthetic 驗收不呼叫 provider；正式接線後只補一條有界自然 smoke 核對 OpenRouter 真 route 與完整 App 結果，不重做已完成的顧問 prompt／品質研究。

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
