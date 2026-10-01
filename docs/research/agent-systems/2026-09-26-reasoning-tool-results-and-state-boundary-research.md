# 顧問分析延續：Reasoning、工具結果、Compaction 與 State 的邊界

- 狀態：**研究／候選，非施工設計**；不裁決 State 欄位，不宣稱已通過真模型驗收。
- 查閱／最後核對：2026-09-26。
- 維護責任：Agent 架構研究；產品取捨由 Product Owner 確認。
- 範圍：職務顧問 A 如何跨 Step／Turn 接續分析；B1／B2 只核對責任界線，不在此重設背景流程。
- 上位入口：[全產品目標導覽](../../target-architecture-map.md)、[產品概念](../../product-concept.md#reasoning-與-compaction-的接續政策目標未實作)、[討論規範](../../architecture-discussion-standard.md)。
- 研究沿革：PROD-G1-014 → 015 曾允許極端原生自動壓縮 → **018 取消該例外** → **019 確認 A／B1／B2 的交界門檻／Agent 決定兩種主動觸發、完整視窗接續與 LangGraph＋OpenAI direct Responses SDK**。最新政策見[產品概念](../../product-concept.md#reasoning-與-compaction-的接續政策目標未實作)。下文 §6–8 保留各階段審核，提到自動路徑、固定排列未選或 SDK／框架待選時不是最新目標；早期 [09-25 研究](2026-09-25-agent-capabilities-and-lifecycle-patterns-research.md)也不直接作新接線規格。框架已選，State 及背景工作交界仍待研究，見 §9。
- 後續裁決 PROD-G1-016／017：Owner 已選擇不使用 `previous_response_id`、明確設定 `store=false`，由 App 自主管理 context 與原生 items 接續，自己的資料庫負責必要持久資料。下文 §6、§8 中「尚未決定不用／仍可比較 chaining／store 未選」是裁決前的審核紀錄，不再作最新選項；最新責任與官方 stateless reasoning／資料保留界線見[顧問設計稿](../../specs/2026-09-26-consultant-context-and-state-design.md)。019 已另定框架，但不預定 State schema、保存／恢復實現或新增筆記機制。

## 1. 本輪問題與研究結論

**問題不是「State 應該有幾個欄位」，而是「已有原生分析接續與工具觀察後，還有哪些資訊必須明確交付、讓誰使用？」**顧問要能逐步理解員工工作並完成專業 JD，不要求模型每個 Step 重填分析表，也不將每個新疑點都變成永久待辦。

研究建議：先以**原生 reasoning／工具軌跡／Turn 交界 compaction，加上可回查的正式工作資料及 App 執行狀態**作比較基準；額外的模型工作筆記是候選，不預設必需或無用。這不是取消已確認的 State 延續能力，也不是刪除現行 Working State 的授權。上下文 items 本身也屬需承接的狀態；「不另造一份分析表」不等於「App 無狀態」。

下列是能力與責任的比較，不是四個新元件或四張資料表。

| 能力 | 足以承擔的角色 | 不能據此保證／代替 |
|---|---|---|
| 原生 reasoning 接續 | 讓後續請求利用可取得的先前推理，接續規劃、比較、工具選擇及判斷。`all_turns` 可納入相容的先前 Turn reasoning。 | 不保證完全不重算、不遺忘或一定判斷正確；App 無法把 opaque reasoning 當可讀寫的欄位，也不能由此確認資料已提交。 |
| 工具呼叫與結果 | 當呼叫與結果被接入後續 request 時，讓下一 Step 知道實際讀到的 Memory／訪談／JD，以及操作成功、拒絕或未知的結果；提供繼續分析的觀察。 | 不會自行永久留在模型上下文；compaction 只承接部分資訊。精確結果須仍可見或由有權威的保存來源重新取回；過去讀取不是當下最新版，通知背景也不等於發布完成。 |
| 原生 Compaction | 在允許的 Turn 交界縮減上下文，承接後續所需的重要狀態及 reasoning；不是只保留聊天主題的一段文字摘要。 | 不保證每一個細節、疑點或分析分支無損；不能當原話、Memory 版本鏈、JD 或恢復紀錄的唯一權威。 |
| App 管理的狀態與正式資料 | 明確維持職務檔案範圍、當前執行身分、Memory 讀取基準、正式操作／發布結果；依約定處理中斷。 | 不把所有資料都塞進 Prompt；不要求模型填 App 已知值，也不把產品保存責任交給 provider reasoning。 |

## 2. 官方能力、工程經驗與本案推論

| 來源（查閱日期同上） | 公開內容 | 對本題的限制 |
|---|---|---|
| [OpenAI Reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls) | 區分可見對話與 opaque reasoning；`all_turns` 利用可取得且相容的先前 items。工具連續呼叫時，建議保留自最後 user message 以來的 reasoning、calls、outputs。 | `all_turns` 不會創造不存在的歷史；每次仍是新的推論，並非保存可任意存取的模型內部變數。這支持接續能力，不證明 Caliburn 的訪談品質已足夠。 |
| [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction) | 原生 opaque item 承接先前重要狀態與 reasoning；standalone compact 回傳可接續的新視窗，可能包含保留 items。 | 本案的 Turn 內不壓縮是產品限制；不得從原生能力推出無損保留或自動恢復業務副作用。 |
| [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)（2025） | 把 compaction、外部工作筆記、按需取回列為不同技巧；筆記可保存進度及跨長工具軌跡仍要用的資訊。 | 是可採模式，不是所有 Agent 每 Step 必寫固定 schema 的要求；其文字摘要策略不等於 OpenAI 的 opaque compaction。 |
| [Anthropic Long-running Harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)（2025） | 在跨多個 context 的開發工作中，用進度紀錄、正式成果與驗證防止後續工作猜進度或過早宣告完成。 | 這是當時模型與 coding 任務的工程經驗，不直接證明 A 必須保存每個訪談問題。不能把程式開發的 feature list 直接移植為訪談問卷。 |
| [Anthropic Harness Design](https://www.anthropic.com/engineering/harness-design-long-running-apps)（2026-03） | 隨模型進步移除 resets 和部分工作拆段，但保留仍有價值的角色、成果及自動壓縮；逐項檢查輔助流程是否仍有價值。 | 不代表完全不要 state／artifact，也不證明 OpenAI 原生接續已足以處理本案全部需求；不要求本案增加 planner／evaluator。 |
| [Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents)（2026-04） | 持久 session 與模型視窗分離；壓縮後的歷史可從保存的紀錄回查，harness 可替換。 | 支持「可回查原始資料不等於全部放 context」，不要求本機 App 另造事件服務、sandbox 或第二份原話儲存。 |
| [LangGraph Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#step-3-design-your-state)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 依後續步驟需要決定保存資料；可推導者按需計算，Prompt 格式化與原始資料分開；checkpoint 保存執行狀態。 | Graph State 可包含 messages、工具觀察和草稿，不等於一張模型填的 Working State 表；checkpointer 不替代 JD／Memory 的正式提交與來源權威。 |

**跨來源歸納，而非統一規範：**分析接續、可觀察的執行狀態、正式工作事實及當次模型視圖需要分清；沒有共同規定的固定工作筆記 schema。外部可讀筆記在需要可靠交接、人工檢查、程式消費或減少昂貴重查時有價值；不能只因「Agent 應有 State」就新增。

## 3. 什麼仍須明確管理，什麼先不要重複記錄

**App 已知、必須依既有責任管理：**本輪屬於哪份職務檔案、採哪版 Memory、訪談讀取範圍、工具呼叫與結果的對應，以及已確認的 JD／Memory 操作結果。這些是規則所需的資訊，不是這次新定 DB 欄位；能由同一正式資料推得就推得，不另存可互相矛盾的副本。需要重啟後繼續哪部分工作，才決定該部分的持久生命週期。

**普通分析先由已選接續能力承擔：**本輪在比較哪些工作差異、讀取工具後如何調整判斷、下一步先查哪個依據等，不預設每 Step 額外輸出筆記。模型仍可根據新觀察重新評估；「分析延續」不是要求沿用錯誤結論或禁止重新推理。

**額外筆記值得討論的條件：**某個分析成果確實要跨上下文／角色明確交付，接收方不能只靠 opaque reasoning 使用它；或長訪談評估顯示重複查閱／比較影響品質、成本或接續。若採用，保存的是可交付的結論、依據定位與下一步所需資訊，不要求模型揭露完整內部思考，也不複製全部原話、Memory 或 JD。具體分類、欄位、寫入時機和失效規則仍待議。

**不能因筆記而新增的 authority：**「已保存 JD」「Memory 已發布」不得由筆記自行宣告；缺失／衝突不得在筆記中無據變成員工已確認事實。Owner 已允許一般分析問題不永久列為待辦，本稿不恢復舊九欄表、每輪 Memory 對帳或永久問題追蹤的要求。

## 4. 用生命週期檢查是否有缺口

| 情境 | 已有能力的目標承接 | 仍需驗證／討論 |
|---|---|---|
| 同 Turn：讀理解 → 讀相關情境 → 核對訪談 → 決定是否改 JD | 同一 Memory 基準；本輪 user、reasoning、calls、outputs 接續，Step 間不壓縮。 | 工具結果與配對是否完整進下一 request；模型是否真的利用新觀察，而非循環重查。不能僅因工具都成功就稱分析通過。 |
| 下 Turn：員工補充或更正 | 重新 pin 正式 Memory；必要時讀尚未整理的前輪原話；`all_turns` 承接相容舊分析，但不把舊推論當事實。 | 是否保留正確的更正含義；新 Memory 與歷史 tool observation 不可混用。 |
| Turn 交界發生原生 compaction | 使用其合法輸出視窗接續；原話、Memory、JD 保有原責任下的回查能力。 | 能否接續正在訪談的工作主題，必要時找回細節；不能用「API 接受 compaction item」代替品質驗收。 |
| JD 已提交，但 final 失敗／程序中斷 | App 從正式操作結果判斷已提交內容；模型上下文不是唯一恢復依據。 | 不重做已成功副作用；是否續同一 Turn 或終止後開新 Turn，留在執行生命週期決定，不由筆記偷偷裁決。 |
| B1→B2 的跨角色交付 | B1 的工作情境候選、來源與本次工作基準是明確交付資訊；B2 依它分析自己的工作理解。 | 不假定 A 的 `all_turns` 會自動把分析或私有 reasoning 傳給 B1／B2；本稿不新增共用筆記，也不改兩層共同發布。 |

以上是代表性驗收要求，**本輪未執行這些測試**。單一 Turn 超容量的問題仍依上位政策 OPEN，不用額外筆記或假造 Turn 邊界繞過。

## 5. 候選比較與下一個討論點

| 候選 | 優點 | 代價／限制 |
|---|---|---|
| **甲：原生接續＋現有正式資料與必要 App 狀態；不強制另寫分析筆記** | 直接利用已選能力，避免重複抄寫和錯誤筆記；最適合作為比較基準。 | 跨壓縮續談的品質須實測；App 不能解析 opaque reasoning 判斷分析進度。 |
| **乙：甲＋有明確用途的小型工作筆記** | 可檢查、可交接，可能減少重查與重分析；具體需求成立時採用。 | 增加模型輸出與維護成本，需處理舊筆記與新事實衝突、時效及清理；不能成為第二套 Memory。 |
| **丙：每 Step 強制輸出完整結構化分析狀態** | 可供依賴固定中間結果的工作流路由或檢查。 | 本案尚未提出這種消費需求；容易增加工具步驟、重複資訊及過早固化判斷，因此目前不建議。 |

**建議，尚非 Owner 裁決：**先採甲作設計／驗收基準，保留乙處理被明確識別的交接或效率需求，不預先採丙。不因本稿刪除現行 Working State；未來若替換仍須另有施工範圍及回歸。

下一個討論問題是：**除了模型自身接續，是否有分析結果必須讓 App、另一個 Agent 或下一段獨立工作直接讀懂並使用？**先找使用者與用途，再判斷是否需要顯式工作筆記；不是先列欄位再找理由。

若進入驗證，先離線核對 request 內容與狀態來源，再以有界真模型比較訪談接續、跨輪更正與交界壓縮。衡量是否遺漏／誤解事實、是否重複無效查詢、步驟／用量及 JD 品質，不要求讀取隱藏 reasoning 來證明「沒有重新分析」。具體測試腳本、資料範圍、請求／費用上限另定；本次沒有付費呼叫、production 修改或切換。

## 6. 外部審核補核對（2026-09-26，非新增產品裁決）

**歷史狀態：本節記錄 PROD-G1-014 階段的審核。**其後 015 曾允許極端自動路徑，018 又取消該例外；下方保留當時的判斷與理由，不藉改寫研究抹去迭代過程。最新政策只在上位產品概念維護，本研究不另抄第二份政策。

外部參考稿提出四項補正及一份示意 context／state；依官方契約與 PROD-G1-014 核對如下，不整份照採：

- **Reasoning 可取得性：成立。**`all_turns` 不會自動找回已不可取得的舊 reasoning。參考稿的「persisted reasoning」不等於已選 `store=true` 或 `previous_response_id`；官方也提供 stateless replay，保存與接續選型仍待議。參見上方 Reasoning 來源及 [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)。
- **工具結果生命週期：補精確。**工具結果是一次觀察，不是自帶永久記憶的機制。本 Turn 依已定政策接續保留；跨 Turn 壓縮後，承接的重點不等於完整原文。保存了資料也不表示模型已讀取，仍要經 context 注入或工具回查；不因此要求所有工具結果成為新的持久業務物件。
- **產品政策與 API 能力分開：成立；中途自動壓縮兜底不採納。**官方 server-side 模式可在同一 response 推論途中壓縮並繼續，參考稿的「最後兜底」會放寬已定的 Turn 內禁止壓縮，而不只是文案修正。維持既有政策及單一 Turn 超量 OPEN；不把「原生」等同「啟用自動壓縮」。若未來要放寬，必須另行提出取捨並取得 Owner 決定。
- **狀態責任分開：可作討論分類，不定為三個元件。**執行狀態（本輪 Memory 基準、待配對呼叫）由 Runtime 管；業務資料與狀態（JD 版本、正式提交／發布）由相應 Domain 管；模型工作筆記另依明確用途討論。這不是業界規定的唯一分類，也不要求三份儲存。框架 State 可持有正式資料的參照／讀取結果，但不取得其業務權威。`Goal State`、`review failed`、`working_state_version` 尚不是新增需求或欄位。
- **參考架構圖與 JSON 不升格為契約。**Memory 整輪固定指固定讀取基準，不表示每次預載整份 Memory；Goal／Review context、工具名稱、固定排列和持久資料清單均未採用。可推導的近期起點不因 JSON 範例而增加第二個可寫真相。此輪不新增 Goal／Review 子系統、State schema 或固定 context 組裝順序。
- **額外筆記的門檻不限定為「先失敗才可增加」。**若已確認 App／其他 Agent 必須直接讀懂某項分析成果，這本身就是用途證據；若只有模型接續需求，才以品質及效率比較原生能力是否足夠。兩者都不支持無條件每 Step 填完整分析表，也不要求揭露內部思考。

本輪只補研究解釋與衝突標記；沒有更改目標產品決策、production 或原生接法驗收狀態。下一題仍依 §5，先辨認必要分析成果的使用方與生命週期，再決定是否需要額外筆記。

## 7. 外部狀態更新、事件與版本檢查的補核對（2026-09-26）

**狀態：外部參考稿審核／候選比較，非新增產品裁決或現行程式缺陷。**本節採當時 PROD-G1-015 前提，現已由 018 取代壓縮政策，其他研究比較不因此變成產品決定。目的只在分清「模型如何得知外部更新」與「分析如何接續」；不因參考稿新增事件服務、工作筆記 schema 或 Review 子系統。

**成立的方向：**App／Runtime 負責取得正式資料、選定讀取基準及傳遞觀察，不讓模型生成 App 已知的版本或自行猜測保存結果。資料庫更新不會自動出現在模型輸入；但「事件優先、邊界查版本只能是備案」不是所引官方資料支持的通用結論。

| 核對項目 | 官方證據與本案判斷 |
|---|---|
| 事件通知與必要邊界讀取 | [Microsoft 事件架構指南](https://learn.microsoft.com/en-us/azure/architecture/guide/architecture-styles/event-driven#when-to-use-this-architecture)列出適用條件，也明示簡單 request-response、同步已滿足延遲與吞吐時未必值得引入事件架構。由程式在需要的操作邊界讀正式狀態，不等於讓 LLM 反覆呼叫檢查工具，也不等於持續背景輪詢。需比較實際寫入者、更新頻率、讀取時效與恢復要求；不先選每 Step 必查或事件必需。程序內通知亦不等於外部 broker。 |
| 丟失通知與過期寫入是不同問題 | **推演反例：**JD 已更新，通知漏掉，A 只回答而不寫入，便不會觸發任何寫入版本衝突。OCC 能拒絕過期修改，不能單獨保證讀取新鮮度；「沒事件」也不能無條件當作「沒變動」。[PostgreSQL 18 LISTEN](https://www.postgresql.org/docs/18/sql-listen.html)僅通知當時訂閱的 session，session 結束即取消；官方要求先提交訂閱、再讀資料庫初始狀態以處理競爭。若採通知，須說清初始／重連及必要邊界如何與正式來源重新同步；本節不因此決定持久事件 queue。 |
| 持久化與版本檢查不是所有 State 的同一模板 | [Microsoft Foundry State Store](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-state-store#items)是 hosted-agent **preview** 範例；官方區分 mutable item 的 ETag／If-Match 與使用新 key 的 append-only checkpoint，後者不需要同樣前置條件。需要中斷後存活的資訊才依其責任持久化；可推導值不另立可寫 authority。不從這個服務推出本案所有暫存資料都要 version++。 |
| 框架 checkpoint 的責任 | [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers#super-steps)的完整快照邊界是 **super-step**；個別 node 的 pending writes 另支援恢復，不能一律把 node、模型 Step、產品 Turn 畫成同一邊界。這是 graph 執行保存能力，不是自動監看任意外部資料庫、同步 JD 或保證業務副作用只執行一次的證據。 |
| Working State 不取得 JD／審核的業務權威 | 本案既定概念是分析延續，不預定單一元件。參考稿的 `JD version`、`review passed` 等仍應由相應業務來源判定；Graph State 可保存其參照／觀察，但不變成第二個可獨立寫入的真相。`goal_id`、`open_blockers`、固定 State JSON 與 Review 子系統均未裁決，不藉範例採用。 |
| 模型輸入與版本綁定 | [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)以真實 `call_id` 配對工具結果；外部更新不能偽造成模型未要求的工具呼叫結果，`state_refresh` 亦不是本次所核對的官方 Responses item。App 若提供狀態訊息，須區分受控執行 metadata 與員工／模型自由文字，不能因資料存於可信 DB 就提升成高權限指令。寫入的依據版本由 Runtime 綁定實際讀取，不能讓模型猜值；衝突後重新取得相關內容、判斷是否仍要修改，不替舊修改換版本號無條件重送。 |

**API 能力補精確：**目前 [OpenAI Mid-turn steering](https://developers.openai.com/api/docs/guides/steering)也公開 GPT-6 系列透過 Responses WebSocket steering，不能把進行中更新說成只有 Agents API 才有。但接受 steering 不等於已套用，且不撤銷已開始的工具；這不替 App 監看資料庫。本案未選 steering，不因有能力就引入。

**對本案的研究建議：**先逐項辨認誰會修改、誰需要看到、容許看到多舊、何時必須重新核對，再選通知或邊界讀取。自己成功執行工具的觀察可由正常結果接續；Memory 維持上位整輪固定政策；外部人改 JD 的可見時機則另依 JD 編輯契約討論，不套一個「所有 State 下一 Step 一律 latest」的規則。持久化／恢復、通知、模型可見性及保存時的原子檢查是不同責任，不要求各造一個新元件。

**下一個可證偽檢查：**除正常工具回傳外，至少推演「外部更新、通知未到、A 只回答」、「讀取後有人寫入、A 再提交」及「背景發布但 A 本 Turn 仍讀固定 Memory」。三者分別檢查讀取政策、過期寫入保護與已定快照邊界，不能以其中一項 PASS 代替另外兩項。本輪只核對官方契約與研究文件，未測現行實作；未新增正式選型、未改 production、未送模型請求。

## 8. 本輪概念整合與外部參考稿審核（2026-09-26）

**範圍：**Owner 提供的新參考稿（附件識別 `d220211b-931d-40c3-8025-8c14a0565e46`）作研究輸入，不整份採納為產品決策。本節留下審核沿革；可持續維護的責任與生命週期整理移至[顧問上下文與分析延續設計稿](../../specs/2026-09-26-consultant-context-and-state-design.md)，本研究不再兼作架構主入口。其餘產品能力仍由全產品 map 分題深入，不宣稱本次已完成全部架構。

| 參考稿主張／容易誤解的地方 | 核對結果及本輪處置 |
|---|---|
| OpenAI 原生能力負責 tool loop | 須區分 API 與編排。Responses 回傳工具請求；App／框架執行自有工具、回傳配對結果並繼續請求，provider 不替 JD／Memory 工具提交資料。SDK／框架仍待選。依據：[Function calling](https://developers.openai.com/api/docs/guides/function-calling)。 |
| 不用 `previous_response_id`、自行組裝所有 context | **可行候選，不是已定方案。**`all_turns` 的可取得性要求與保存／重播選型是兩件事；不能把可不用寫成已選不用，也不默認 `store=false`。依據：[Reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)、[Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)。 |
| 重新分類壓縮層級，或在安全 Step 邊界主動壓縮 | 不替換 PROD-G1-015。App 主動壓縮仍在 Turn 交界；極端才用原生自動路徑。已超容量另屬失敗處理，不是第三種保證成功的壓縮方式。standalone 回傳整個新視窗，不套 inline 裁切規則。依據：[Compaction](https://developers.openai.com/api/docs/guides/compaction)。 |
| 沒有問題前完全不用額外筆記 | 不把門檻定成「只能先失敗」。有明確跨角色／App 消費需求即可討論；僅模型接續需求則比較原生能力的效果。State 不等於筆記表，仍不強制每 Step 填寫。依據：[LangGraph State 設計](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#step-3-design-your-state)及上方跨廠研究。 |
| Current Memory、原始完整 trace、canonical compacted window | 三者須分清。A 讀本輪固定基準，不是每 Step latest；原始訪談與完整執行 trace 不混存為同一產品事實；provider 的 canonical window 是接續視窗，不是本產品訪談權威。保存不等於模型已看見，也不等於所有中間資料永久保存。 |
| Review 先做 service／工具，之後才考慮 Agent | 可留作未來選項，不在本題定案。Owner 已將審核形態延後；參考 JSON、Goal／Review schema 與固定 context 排列亦未採用。 |

**審核結果：**可沿用「正式資料、執行接續、模型可見視圖各司其職；只保存確有用途的額外成果」的方向，但這是跨來源歸納與本案建議，不是業界唯一切法。Memory 讀取邊界及近期範圍已是 Owner 決策，不降級成待選實驗；SDK、重播、State 欄位、門檻仍不提前決定。本輪也修正記憶子圖殘留的框架定案文字，保留舊研究的歷史位置；沒有改 production、執行產品測試或付費模型。

## 9. LangGraph 與 direct Responses 的契約起點（2026-09-26）

**狀態：019 後的官方契約補核；不是 State schema 或施工完成證據。**框架選擇來自 Owner 本次決定，非從舊研究倒推。以下只處理會影響接續正確性的交界，不重開其他框架比較。

| 核對題目 | 官方公開能力 | 對後續設計的影響／尚未驗證 |
|---|---|---|
| 原生歷史如何接續 | [OpenAI manual conversation state](https://developers.openai.com/api/docs/guides/conversation-state#manually-manage-conversation-state)示範追加 response output 並重送；stateless reasoning 須保留完整原生 items 與適用 metadata。 | 本產品另定未壓縮前不裁改歷史、新導覽追加。這不是聲稱官方禁止任何應用編輯自己的歷史；SDK 型別轉換與保存往返仍需測試。 |
| 主動壓縮回傳什麼 | [Standalone compaction](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint)接收完整現有視窗；回傳新視窗可能含多種 items，不得裁切，其 opaque 項目承接狀態與 reasoning。 | 019 的完整輸出前綴符合該契約；不只留 compaction item，不把舊視窗再附一次，不從 DB 重新展開已壓縮全歷史。API reference 取回僅有入口說明，本次未取得完整參數表，頂層 instructions／tools 映射仍留待核對，不猜可傳欄位。 |
| LangGraph 是否要求用聊天訊息類別 | [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api#working-with-messages-in-graph-state)允許自訂 State；`MessagesState` 的 `add_messages` 會轉成 LangChain Message，並可按相同訊息 ID 更新舊訊息。 | 不能直接推定它可無差異承接 native Responses items，也不能把預設覆寫語意當成產品歷史契約。先核原生型別、序列化與更新規則；不因此設通用轉換框架。 |
| State 要保存什麼 | [Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#step-3-design-your-state)依跨步驟使用需求選資料，能推得的資料按需計算，原始狀態和 prompt 格式分開。 | 是研究資料責任的方法，不是固定筆記 schema。可重建 prompt 不代表可重新改寫已發生的模型輸入歷史。 |
| 持久化是否就是長期工作記憶 | [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)區分 graph checkpoint 與 graph 外的 Store；前者承接執行狀態。 | 名稱相同不代表 Caliburn 三層 Memory 必須遷到框架 Store；業務原話、Memory 發布與 JD 仍有自己的 authority，不另建一份。 |

**此階段提出的研究題（本次結果續於 §10）：**原生歷史如何進入 LangGraph State／checkpoint、正常追加與 compact 後換視窗如何表達、恢復時如何避免重做已完成效果，以及哪些額外分析成果真的有使用方。具體 reducer、欄位、套件版本及儲存形狀未定；正式選型需核所採版本文件／原碼並做離線往返驗證。B1／B2 的 Turn／整理工作交界另依其生命週期提出，不能套 A 的員工回合。

## 10. LangGraph State 保存與恢復的研究結果（2026-09-26）

**狀態：官方文件＋本機鎖定原碼的靜態核對；候選，未施工、未做序列化往返／PostgreSQL／真模型測試。**沿 019 研究框架如何承接已定效果，不重選 provider、不重開三層 Memory、不把現行 implementation 當作新方案的限制。

### 10.1 官方機制與直接影響

| 依據 | 核對結果 | 對 Caliburn 的推論／限制 |
|---|---|---|
| [OpenAI stateless reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-without-stored-responses) | 官方示例將原生 response output 序列化後加入歷史，保留 encrypted reasoning 及相關 metadata，再送後續請求。 | 可以優先用可序列化的原生 items 承接，不必先轉成另一套聊天訊息；不等於只存文字、只存 response ID 或可以自行解密。實際 SDK／Saver 往返仍待驗。 |
| [LangGraph State 設計](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#step-3-design-your-state) | State 存後續步驟需使用的資料，能推得的值按需計算；原始資料與 prompt 呈現分開。 | State 不等於全部 LLM context，也不等於固定分析表。已送出的歷史 observations 自身就是接續資料，不能把「按需格式化」解釋成每輪用新版正文重建舊歷史。 |
| [Graph API：State／reducer／Overwrite／runtime context](https://docs.langchain.com/oss/python/langgraph/graph-api) | 可自訂 State；一般欄位可替換、有 reducer 者依規則合併；`Overwrite` 可明確繞過累加。依賴可由 runtime context 注入，與 State 分開。 | 正常追加、合法 compact 後整窗替換，不必造另一套更新引擎。App 仍須維持確定順序；框架不自動識別產品 Turn 或禁止任意改寫歷史。 |
| [Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers#durability-modes) | 提供 `sync`／`async`／`exit` 保存強度、thread 與 super-step 恢復能力。 | 建議用 `sync` 作恢復驗證基準；不是零遺失保證或外部交易的一部分。框架 thread 不是 OS thread，也不等於產品 Turn。 |
| [Graph API：Re-execution and idempotency](https://docs.langchain.com/oss/python/langgraph/graph-api#re-execution-and-idempotency) | 恢復可能從受影響 node 的函式起點重跑，不是任意程式行接續。 | 已提交效果要經正式 operation／receipt 查回；模型及工具邊界應可獨立恢復。不可把 replay 當作自動防重或自動撤回。 |

### 10.2 同目的接法比較

| 接法 | 效果／代價 | 本次建議 |
|---|---|---|
| 原生 items＋一般 list 累加 reducer；交界用 `Overwrite` | 避免原生→LangChain→原生往返；正常更新只提交新增項目，壓縮明確換窗。需驗工具配對、恢復時不重複追加及保存容量。 | **優先候選**，符合 direct SDK 方向且使用框架原生機制；不是已通過的 production 設計。 |
| 原生 items＋每次回傳整個新 list，使用預設欄位替換 | 也能實現同效果，邊界簡單；每個寫入方須正確承接完整舊視窗，較容易誤漏或覆寫。 | 有效比較基準，不宣稱官方禁止；目前沒有必要讓每個 node 重複處理整窗合併。 |
| `MessagesState`＋原生 items 轉換 | 可用 LangChain Message 生態，但須證明 reasoning、compaction、phase、工具配對及非文字 items 無差異保存。`add_messages` 也允許同 ID 替換。 | **歷史比較，020 後不列目標候選。**Owner 已明確不採 LangChain 應用封裝；這不等於技術上已證不相容。 |

自製外部歷史服務、graph 只存 pointer、再加通用 replay 引擎目前沒有必要性證據，不列施工候選。正式業務保存與原生接續保存仍須分責，不能因 reducer 選擇產生第二個 JD／Memory owner。

### 10.3 鎖定版本、本機核對與儲存取捨

- [正式 App pyproject](../../../experiments/jd-relational-app/pyproject.toml)及 [uv.lock](../../../experiments/jd-relational-app/uv.lock)：LangGraph **1.2.11**、checkpoint **4.2.0**、PostgreSQL Saver **3.1.2**、OpenAI SDK **3.13.0**；本機 `.venv` 套件 metadata 相符。這是本次證據基線，不是替未來目標鎖死版本。
- **020 後的版本及依賴界線：**Owner 允許採新版；後續查當時最新穩定 release、相容矩陣及實際所採原碼，再鎖定版本驗證，不把上述已安裝版本當作目標上限，也不把主分支版號當成最新已發布版。依 [OpenAI SDK 文件](https://developers.openai.com/api/docs/libraries)，此處使用官方 Python `openai` 套件直接呼叫 Responses，不是 Agents SDK。[LangGraph 官方 overview](https://docs.langchain.com/oss/python/langgraph/overview)明示可不使用 LangChain；但[官方套件 manifest](https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/pyproject.toml)與本機 1.2.11 metadata 都包含 `langchain-core` 依賴。因此「不採 LangChain Agent／模型／Message 封裝」成立，不宣稱依賴樹零 `langchain-*`；不為去掉框架內部依賴而自行 fork 或重造框架。本輪未安裝、移除或升級任何套件。
- 已直接讀安裝套件中的 `langgraph/graph/message.py`、`channels/binop.py`、`channels/delta.py`、`types.py` 與 checkpoint 的 `serde/jsonplus.py`：`add_messages` 會轉換訊息且同 ID 可覆寫；一般 reducer channel 支援 `Overwrite`；序列化預設不開 pickle fallback。這支持上述候選，不代替真實 Responses items 的 round-trip 測試，也不為保存 JSON 資料啟用 pickle。
- [官方 DeltaChannel](https://docs.langchain.com/oss/python/langgraph/pregel#deltachannel)及鎖定 source 都標 **Beta**：可保存增量再重建累積值，另有快照與讀取成本。原碼亦處理 `Overwrite`，但本次未驗 Postgres 全鏈。公開 guide 的快照預設敘述與本機建構式的 `snapshot_frequency=1000` 不一致，不能直接抄參數；若採用，需以所採版本的原碼／回歸證據明確定值。
- 模型 compaction 縮小**未來模型視窗**，不自動清理既存 checkpoints。普通累積 channel 的保存量可能隨歷史成長，需量測再比較框架增量能力與保存期限；不現在自製 Git 式差分／事件儲存，不因 context 壓縮刪原話，不先設定無限保留。
- 現行 [runtime_checkpoints.py](../../../experiments/jd-relational-app/src/jd_relational/runtime_checkpoints.py) 的 `DocumentState(MessagesState)` 與 [ai_checkpoints.py](../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) 是 **現況參考**，不是 019 的已完成接線；也不由此再建第二套恢復 owner。現行正式權責循 ADR0077，較舊 ADR0060 的舊產品 State 形狀不是目標約束。

### 10.4 後續驗證邊界與收斂

候選責任與正常／異常生命週期集中寫在[設計稿 §7](../../specs/2026-09-26-consultant-context-and-state-design.md#7-state-責任與生命週期候選先找使用方再決定表示)，不在研究稿另抄一份流程。

採納接線前需要的窄驗證：**原生 items → SDK input → Saver 保存／讀回 → 下一請求**保留內容與順序；一般追加不改舊觀察；compact 全量 output 正確換窗；同 Turn 恢復不刷新 Memory；JD 已提交但 checkpoint 未寫時不重做；provider 回應／compact 已產生卻未保存時不把重送視為零成本。模型品質另驗，不讀 hidden reasoning 判斷是否「真的接著思考」。

本輪研究已足以進入責任核對，停止廣搜。額外顯式分析成果是否需要、由誰讀寫，以及 B1／B2 工作交界仍 OPEN；不將框架的可行性當成這些產品問題已有答案。沒有 production 修改、依賴升級、資料庫操作、付費請求或 commit／push。

## 11. Step 內部恢復與暫停的補核對（2026-09-27）

**狀態：官方公開契約＋現行程式／測試的靜態閱讀；候選，未執行故障注入、PostgreSQL 或模型測試。**問題是利用既有持久執行機制減少中斷重算，而不是從頭製作通用恢復系統。Owner 本輪另確認同一 JD 在 A 執行及暫停期間禁止人工修改（PROD-G1-028）；其餘接法仍需審核。外部附件《我建議 A 的最小可恢復流程採這個結構》只作候選參考；本文重新查官方契約，不依附件中不可解析的引用編號作證。

| 第一手來源 | 官方明文／現況事實 | 對本案的判斷，不冒充官方產品規範 |
|---|---|---|
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#the-tool-calling-flow) | 模型提出工具呼叫，App 執行並提供結果後，才由模型接續。 | provider 不替 App 保存 JD 候選或決定產品 Step 安全點；完整回應保存後才動工具是本案的 022 保證。 |
| [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers#durability-modes) | super-step 有完整快照；成功 node 的 pending writes 可供失敗恢復；`sync` 在下一 graph step 前保存。 | 可承接模型結果與完整 Step 的不同保存邊界；仍需設計何時 context／候選一致，不能宣稱 checkpoint 自動回滾外部 DB。 |
| [Functional API idempotency](https://docs.langchain.com/oss/python/langgraph/functional-api#idempotency) | 恢復重用已保存 task 結果；未完成記錄的 task 可能再執行，副作用須冪等或核對原結果。 | 可比較明確 Graph 節點與必要的 task；不必為每個傳輸階段寫新引擎，也不保證外部模型請求恰好一次。 |
| [Checkpointer replay](https://docs.langchain.com/oss/python/langgraph/checkpointers#replay) | 指定舊 checkpoint 回放，之後節點及 LLM／API 呼叫會重跑。 | **正常 failure resume 不等於 time-travel replay。**不能先用舊 checkpoint 另走一條分支，再聲稱後面的已付費結果必定重用；候選接法須驗原執行身分及結果承接。 |
| [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts#resuming-interrupts) | `interrupt()` 可持久暫停，恢復重新進入所在 node。 | 首選在完整 Step 後的無副作用控制位置處理暫停；不是任意 Python 行或 token 都能原地續跑。 |
| [AWS safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)；[PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html) | AWS 以原請求辨識及一致保存的操作效果／結果處理重送，PostgreSQL 交易提供原子提交。 | 若候選獨立保存，優先由同一候選責任一致保存操作效果與結果；不在 Graph 複製第二份業務真相。若只是 State 內部變換，先評估單一 State 保存，不強加收據表。 |
| [OpenAI Python SDK retries](https://github.com/openai/openai-python#retries) | 部分連線／HTTP 錯誤預設重試兩次，可用 `max_retries` 設定。 | SDK、Graph、使用者重試須分開計數與協調；「呼叫一次 node」不證明只有一次模型 HTTP 請求。費用／次數政策仍未定，本次不修改 SDK 設定。 |

**不是從零缺少所有能力：**現行 [JdStorage](../../../experiments/jd-relational-app/src/jd_relational/storage/service.py) 的 `lookup` 查原操作回執；`_insert_receipt` 與 JD 修訂在原保存交易中成立，`lookup` 明示找不到不證明 writer 已停止。[原操作查回測試](../../../experiments/jd-relational-app/tests/test_operation_lookup.py)已有後續 JD 變更仍查原結果、查詢失敗不當成不存在等案例；[前景准入測試](../../../experiments/jd-relational-app/tests/test_foreground_runtime.py)已有模型等待期間拒絕同文件人工操作的案例。**本輪只讀取，未重跑，不宣稱目標已通過。**尤其現行 `write_candidate` 是一次正式操作交易內的中間值，不能因名稱相似便當成 024 要求的跨 Step 私有 JD 候選；新的暫停／重啟維持禁寫亦尚待驗。

| 比較 | 效果／成本 | 本輪結論 |
|---|---|---|
| 只保存完整 Step，丟棄所有中間 R／工具結果再算 | 表面簡單，卻浪費已取得結果，還可能違反 022 先保存請求再寫入的要求。 | 不建議。 |
| 框架原生保存 R／必要 task 結果＋原業務結果核對；使用者仍停完整 Step | 可以減少重算，責任仍是框架保存與業務冪等；要補私有候選、完整 Step 採用與取消資格接線。 | **優先候選**；不能承諾完全零額外工時，但無理由新建整套恢復引擎。 |
| 每個傳送／接收／token／工具階段都建自訂狀態機及 UI 恢復點 | 更多控制及測試組合，仍不能保證找回未保存的遠端回應。 | 首版不建議；需更細控制的實際需求再重開。 |

**附件審核結論：**保留完整迭代形成 Step、原請求先保存、精確候選採用、短業務完成提交及取消終局核對的候選方向。刪除正常人工中途改稿的設計分支；補正 resume／replay 差異，且不能把「已發送」當成「已執行／未執行」證據。**同日 Owner 接續裁決：**原先因 026 而排除第一步半步恢復的限制已被補正；所有 Step 都可承接已保存、可核對的模型／工具結果。只有確無可用同輪恢復位置或整輪放棄，才回完成 Turn、重新提交新輸入。這是產品政策更新，不是框架新能力；具體保存接法仍未選定、未實作或驗收。詳細流程、暫停位置及可證偽情境只在[設計 §7.4](../../specs/2026-09-26-consultant-context-and-state-design.md#74-step-內部恢復與暫停接法候選未採納)維護。研究足以作取捨，停止廣搜；不選資料表、不升級套件、不施工、不送模型。
