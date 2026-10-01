# Agent 能力與生命週期：跨廠做法研究（候選，非施工設計）

- 查閱日期：2026-09-25
- 狀態：研究／候選；**LangGraph 已由 Owner 指定為 Agent 執行框架**，本稿未裁決執行拓撲、資料表或 production 修改
- 範圍：回答「Caliburn 應如何討論 A／B1／B2 的共同能力與生命週期」，不重做已確認的產品效果
- 依據：[架構討論規範](../../architecture-discussion-standard.md)、[產品概念](../../product-concept.md)、[目前決策](../../current-decisions.md)、[分層架構導覽](../../specs/2026-09-24-caliburn-layered-architecture-map.md)
- 關聯歷史：[2026-09-05 harness 審核](../../specs/2026-09-05-agent-harness-framework-gap-review.md)回答當時的框架接線問題；不以其歷史 G3 狀態取代較新的目標決策。

> **2026-09-25 後續澄清／Owner 已確認責任原則：**正常路徑是 B1 維護案例、B2 依案例維護工作理解、兩層候選一致後共同發布。B2 不是 B1 的案例審核者，也不負責判定案例對錯。B2 若在自己的理解分析中發現**理解所需資訊未寫在案例裡**，向 B1 交流缺口及受影響的理解；B1 核對原話並在案例層補充已有依據，仍無法釐清時把已知和未知寫進相關案例。B2 後續只調整自己的工作理解；需員工回答則由 A 訪談。下文「B2 指出案例錯誤、退回 B1、返工草稿」的反例與方案描述現行程式和先前研究，**不是新目標的交流語意**或必經審批。交流的具體資料契約、草稿、重試與恢復語意尚未裁決。

## 這輪可回答的問題

在「一份職務檔案內的長訪談、條件式 JD 改稿、B1／B2 背景共同發布」的已確認目標下，哪些 Agent 執行能力必需，哪些只是可選框架特性？正常工作、重開與失敗時，哪些生命週期不應混為一談？本輪不選類別、API、資料表、provider 或新元件。

代表性正常情境：員工多輪訪談，A 按需查原話／案例／理解，資料足夠才寫 JD；背景整理完成後 A 只讀正式 Memory。反例：A 的 JD 工具已提交但模型 final 失敗；B2 分析理解時發現案例未寫出必需的條件，向 B1 交流，B1 查原話後仍可能只能記錄未知；背景已保存通知後程序中斷；舊背景固定輸入後員工才提出更正。這些場景的產品規則來自本案決策，不是任何供應商自動保證。

### 研究時先按問題找做法，再對照名稱

以下是**搜尋入口與責任核對表，不是宣稱同列名詞完全等價，也不是新元件清單**。先由[架構導覽](../../specs/2026-09-24-caliburn-layered-architecture-map.md)確認能力要解決的問題，再用效果、失敗情境與常見名稱交叉查官方文件；查到的機制仍要核對適用版本、保存邊界及 Caliburn 的產品規則。這能避免只搜本案自訂名稱，卻漏掉成熟方案。

| 要解決的問題（本案用語） | 可交叉搜尋的業界用語／機制 | 不能因此混同 |
|---|---|---|
| 多個模型／工具步驟、員工回合之間接續未完成分析（訪談工作狀態） | graph state、checkpoint、session state、scratchpad、task state | 原始訪談、正式工作理解或模型隱藏 reasoning；能保存 state 不等於能正確接續所有業務副作用 |
| 長訪談時控制模型實見內容（對話延續摘要） | context engineering、conversation compaction／summarization、history projection、request view | 保存的完整原話與正式 Memory；摘要不是不可回查資訊的唯一副本 |
| 找回早期工作細節與依據（原話／案例／理解的分層回查） | retrieval、progressive disclosure、source grounding、provenance、durable conversation items | 「每次把全部歷史放進 prompt」或「任何模型摘要都已是正式事實」 |
| B1／B2 有界整理、候選不外露、一起發布 | durable workflow、staged work、checkpoint、transactional publication、versioned snapshot | 有 checkpoint 或工具回傳成功就等於 Memory 已正式發布；框架不會自動實作本案的引用鏈 |
| JD 編輯已保存、final 可能失敗 | side-effecting tool、idempotency、operation receipt、reconciliation | Agent final、ToolMessage 或 checkpoint 本身就是 SQL 已提交證據 |
| 同一份職務檔案的多輪工作，及本次模型請求 | session／thread、turn／run、model request／step | 同一個時間尺度；供應商 session 不是本案產品資料庫 |

搜尋時可先問「什麼資料不能遺失、什麼事件才算完成、失敗後要從哪個已確認邊界繼續」，再查各家的名稱。上表對 LangGraph 的 state／checkpoint 採[官方 Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)與[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)用語；對 session／turn／saved item 採 [OpenAI 官方文件](https://developers.openai.com/api/docs/guides/agents-api/sessions)；持久 session 與 context window 的區分參考 [Anthropic 工程紀錄](https://www.anthropic.com/engineering/managed-agents)。Codex Field Guide 只作**非官方、固定快照的名詞與公開原碼導讀**，不當成當前 OpenAI 保證。

## 公開來源能確定什麼

| 來源與適用邊界 | 官方公開事實 | 本案不應推出的結論 |
|---|---|---|
| [OpenAI Agents SDK：running agents](https://developers.openai.com/api/docs/guides/agents/running-agents)、[orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration)（查閱 2026-09-25） | 一個 run 是一次應用層 turn，模型／工具／handoff 迴圈到 final 才結束；跨輪可由 app history、SDK session、Conversation ID 或 previous response ID 承接，須選清楚策略。Handoff 會轉移下一段對使用者的回答責任；agent-as-tool 讓主代理保有回答權。 | B1／B2 是背景整理，不等於必須 handoff、必須用 OpenAI SDK，或把供應商 conversation 當產品原話資料庫。 |
| [OpenAI Agents API：events](https://developers.openai.com/api/docs/guides/agents-api/sessions/events)（查閱 2026-09-25） | 管理式 session 有事件與明確工作終局；session 空閒和某個工作的成功是不同層級。 | 可直接把 OpenAI 的事件／狀態名稱照搬成 Caliburn 的 Memory 發布狀態。 |
| [Anthropic：effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)（2025 文章，查閱 2026-09-25） | 區分即時取回、對話 compaction、外部持久筆記與多代理；compaction 要以實際長軌跡調校資訊保留，而非單靠更大的 context window。 | Compaction 就是業務 Memory、B1／B2，或必須再造一個摘要 Agent。 |
| [Google ADK：Session／State／Memory](https://adk.dev/sessions/)（查閱 2026-09-25） | 對話事件、會話內 state、可搜尋的長期資料分責；記憶體版服務重啟會失去資料。 | ADK 的通用 MemoryService 等於本案有版本／引用鏈的工作理解 Memory。 |
| [Microsoft Agent Framework：Harness](https://learn.microsoft.com/en-us/agent-framework/concepts/harness)（2026-09-21 更新，查閱 2026-09-25） | Harness 將模型客戶端、工具、context provider、compaction、中介處理與觀測組合；背景 Agent、檔案存取及 looping 標示為 experimental。 | 「最新」就代表這些 experimental 能力適合立即作為 Caliburn 正式核心。 |
| [LangGraph：Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)（查閱 2026-09-25） | Checkpointer 保存 thread 的 graph state 以支援延續與故障恢復；Store 保存 app-defined data；記憶體 Saver 不支援重啟恢復。 | Graph checkpoint 自動提供本案 JD 收據、原話、Memory 原子 publication 或來源版本規則。 |
| [Anthropic：Agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)（2026 文章，查閱 2026-09-25） | 分開 trace／trajectory 與最後環境 outcome；Agent 說「已完成」不代表 DB 中真有相應結果。 | 只靠 final 文本就能驗收 JD 寫入、引用或背景發布。 |

跨來源共同原則（**研究推論**）：模型決定下一步、執行器承接工具迴圈與暫時上下文、App／Domain 承擔產品資料真相與有副作用操作；長任務需要明確停止與可查的結果。各家在「由誰託管 session、要不要多代理、如何保存細節」沒有唯一主流架構。

### 先比較責任切法，不先固定 Caliburn 元件圖（2026-09-25 補核）

Owner 補充的關鍵方法界線：**研究不應排在「責任、資料真相、正常與異常生命週期都已畫定」之後。**成熟方案可能連這些邊界都切得不同；應先固定產品效果與工作事實要求，再以不同切法形成候選，沿正常、並行、失敗與恢復情境比較。以下是截至查閱日的**公開契約／工程紀錄**，不是相同功能的一對一映射，也不是 Caliburn 的已核准元件清單。

| 來源及適用對象 | 公開的主要切法 | 對本案可借鑑的問題；不可直接照搬 |
|---|---|---|
| [OpenAI Agents API 架構](https://developers.openai.com/api/docs/guides/agents-api/architecture)、[sessions／turns](https://developers.openai.com/api/docs/guides/agents-api/sessions)；託管式 Codex harness | Harness 執行模型／工具迴圈並維持 session；可選的 environment 提供執行位置；application server 連接產品、處理 function tools。Session 可跨 turn；idle 不等於本 turn 成功。 | 問「Agent 執行、工具副作用、正式 JD／Memory 提交分別由誰證明」。其託管邊界不是要求本案改用 Agents API、另建 environment，或把 session 當 JD 資料庫。 |
| [Anthropic Managed Agents 工程紀錄](https://www.anthropic.com/engineering/managed-agents)；託管長任務 | 可持久回查的 session event log、可替換的 harness、執行工具／程式的環境分開；session 不是模型當次 context，harness 可從 log 選取並轉換視圖。 | 問「中斷後從哪個已保存事實恢復，哪些摘要可替換」。這是其產品的演進，不等於本機 App 應另建 event log 服務或沙箱。 |
| [Google ADK Session](https://adk.dev/sessions/session/)、[State](https://adk.dev/sessions/state/)、[Memory](https://adk.dev/sessions/memory/)；SDK 抽象 | 一次對話的 events 與可變 session state 分述；長期 Memory 另由 MemoryService 提供讀寫及搜尋，是否持久依 service 實現。 | 問「跨步驟分析」與「可回查原話」是否各有正確保存邊界。ADK 的通用 MemoryService 不提供本案案例→理解→JD 的來源、版本與共同發布契約。 |
| [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)；已選的本案 Agent 框架 | Checkpointer 保存一條 thread 的 graph 快照，Store 保存 app-defined 資料；graph state 是節點共享狀態，不等於每個產品物件或成功發布。 | 在此框架內可以比較 state／checkpoint／Store／既有業務 DB 的責任；「可跨 thread」不代表員工資料要跨職務檔案共享，也不自動給 JD 收據或 Memory 引用版本。 |
| [Microsoft Agent Framework orchestration](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/)、[handoff](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff)、[checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)；workflow 框架 | Sequential、concurrent、handoff、group chat 等是不同協作型態；handoff 參與者不共用同一 AgentSession，工具呼叫／結果不會隨一般訊息廣播；checkpoint 保存 workflow 執行狀態以恢復，executor 的內部資料需按契約保存。 | 問「B1／B2 是固定接力、動態 handoff，還是別的責任切法」，不能因有多個 Agent 就直接採 handoff，更不能假定 B2 自動看見 B1 的來源查閱與工具結果；checkpoint 不等於正式產品發布。 |

**跨來源可歸納，但非統一拓撲：**可恢復紀錄、當次模型視圖、執行進度與正式業務結果必須能被區分及驗證；具體是幾個服務、State 或 Agent，沒有由上述來源給出一種對所有產品最佳的答案。OpenAI、Anthropic 的託管架構、Google ADK 的 Session／Memory、LangGraph 的 checkpoint／Store 甚至使用不同軸線分類，不能把同名詞強行對映。本案仍以已確認的產品效果——完整長訪談、可追溯原話與案例／理解、專業 JD 及安全恢復——比較：既有劃分達成效果就可保留；更成熟的不同劃分若更適合，應說清適用條件、產品效果、轉換代價與驗收方式，**不要求先重現現行故障才准採用**。LangGraph 是已確認執行框架，**不是**其餘責任切法已定。

### A 與背景整理如何協作：拓撲候選，尚非設計裁決（2026-09-25）

**本輪問題／效果：**A 在一份職務檔案內持續訪談與條件式編輯 JD；它可通知背景整理，但不等 B1／B2 同輪完成，也不把未發布候選當正式 Memory。B1 根據原話維護案例及其來源涵蓋；B2 根據案例維護工作理解，**不負責驗收 B1 案例**。正常路徑由兩層候選一致後共同發布；若 B2 分析理解時發現所需資訊未寫在案例裡，就向 B1 說明缺口與影響，由 B1 在案例層處理，不能自行認定 B1 做錯。具體接續仍待設計，不由框架預設回答。本輪不決定新版物件版本格式、C 退役施工、全稿審核 Agent 或新排程服務。

**外部公開契約，不混稱同一產品的內部實作：**[OpenAI Agents SDK orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration)區分 handoff（專員接管下一段對話）與 agent-as-tool（主 Agent 保有回覆權），並提醒僅在指令、工具或政策確實不同時拆角色；[OpenAI Responses Multi-agent](https://developers.openai.com/api/docs/guides/responses-multi-agent)把獨立、可並行的任務列為適用情境，對有固定先後依賴或共用可變狀態的工作則提醒成本與適用性問題。前者是 Agents SDK 契約，後者是 Responses beta 能力，均不是本案要遷移的執行框架。[Anthropic 的 workflow／agent 分類](https://www.anthropic.com/engineering/building-effective-agents)與[LangGraph workflows guide](https://docs.langchain.com/oss/python/langgraph/workflows-agents)都區分「程式固定流程」與「模型動態選工具」；固定可分解步驟可串接，中間可有檢查及有界回饋，但 Anthropic 該文是 2024 年模式指南，頁面也明言部分工具面已演進，不能視作 2026 年 SDK 規格。[LangChain multi-agent guide](https://docs.langchain.com/oss/python/langchain/multi-agent)明列單 Agent、subagents、handoff、skills、router 與 LangGraph custom workflow，並把每個角色**實際收到哪段 context**列為核心設計問題。[Microsoft Agent Framework sequential](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/sequential)提供固定流水線，但其預設將前一位 Agent 的完整對話傳給下一位；這是該 API 的預設，不適合直接當本案 B1→B2 的最小輸入契約，也不能推論 LangGraph 會如此傳遞。以上均於 2026-09-25 查閱；實際採用仍需核對鎖定的 LangGraph／LangChain 版本。

| 候選控制方式 | 對本案的可能收益 | 需要防的問題與適用界線 |
|---|---|---|
| **單一模型角色處理訪談及兩層整理**，靠提示或工具切換工作 | 少一次角色交接；小範圍單步任務或許更省模型請求。 | A 與背景的時間尺度、來源範圍、工具權限和正式發布責任不同；如果讓同一互動迴圈直接讀寫兩層候選，須另外證明員工回覆權、隔離與共同發布仍清楚。不能只因「Agent 少」就認定較簡單。 |
| **App 接受背景通知；正常 B1→B2，兩層候選完成後由業務權威共同發布** | 與「先整理案例、再分析工作理解」的資料依賴一致；B1/B2 可各自按需讀取，App 能明示 checkpoint 與發布邊界。LangGraph 能把固定順序與模型內部動態工具選擇結合。 | B2 不因此成為案例審核者；只有理解分析需要而案例未寫出資訊時才交流缺口，B1 在案例層處理。具體接續與恢復待設計；兩個分析責任不自動等於兩份服務或資料庫。 |
| **A 動態 handoff／manager 調度 B1、B2** | 當下一個處理者或任務拆分不可預期、需專員接管對話或獨立平行探索時有價值。 | 本案已知 B1→B2 依賴；B1/B2 不直接與員工對話，也不能獨自發布。自由交接不會自動保證來源、版本、候選隔離與原子提交，可能增加往返和重複 context。若未出現此類動態需求，不先新增總控 LLM。 |

**目前較合適的研究候選，不是核准施工：**A 保留對員工的回覆責任；通知是交給 App 的持久工作要求，非把同一訪談 handoff 給 B1。背景外層採**有固定依賴與發布邊界的正常流程**，B1／B2 在各自的分析工作內仍能動態選擇按需讀取與修訂。B2→B1 僅作理解分析缺少案例資訊時的例外交流；不能把它當作固定審核關卡，也不是兩個角色在群聊裡自由輪流。這是從本案資料依賴映射上述公開模式的**推論**；不能寫成「OpenAI、Anthropic、Microsoft 都指定 Caliburn 用此拓撲」。

**交接資料比角色數更關鍵。**[LangGraph 官方 subgraph 指南](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)明示：父子流程若有不同 state schema 或需轉換資料，應在節點入口／出口映射；只有共享 state key 時，才直接讓子圖讀寫同一通道。[LangChain 多 Agent 指南](https://docs.langchain.com/oss/python/langchain/multi-agent)也把 context engineering 視為中心問題。因此本案應核對 B1 交給 B2 的是**已完成的候選案例、變更、來源定位及正式 base 身分**，而非無差別重播 B1 私有推理、工具全文或整段訪談；B2 仍能從受控來源 owner 按需查相關案例及其原話。例外交流時，B2 說明理解需要什麼、案例缺少什麼，附上已取得的依據即可；不代替 B1 決定案例內容。這是本案的候選資料契約與現況核對題，非 LangGraph 預設幫我們保證引用有效或正式發布。

**與現行底稿的關係：**`packages/consultant-memory/src/caliburn_memory/background_workflow.py` 已有 `load_base → run_b1 → run_b2 → route_b2 → assemble／prepare／publish` 的 LangGraph 控制流；`case_rework_required` 可回 B1，stale publication 會重新載入 base。這與候選形狀相近，**不等於**新目標已驗收：目前新 B1 attempt 是否保住同批其他正確案例，A 的更正是否跨回合保留到後續背景涵蓋、以及逐物件版本／固定引用鏈與 C 退役，都仍按下方 OPEN 逐一證明。現行圖只能作基準，不是限制方案比較的 authority。

**下一個可證偽 gate（先研究與隔離驗證，不預設新元件）：**① 正常 B1→B2→共同發布，核對兩層各守自己的內容與來源；② 背景固定第 16 輪時第 17 輪更正，確認舊背景不假稱已涵蓋、A 後續仍看得到更正，新背景才根據它修訂；③ 中斷落在 B1 完成／B2 未完成及「發布提交後回覆遺失」兩處，核對不重複已成功副作用。例外交流的目標反例應是「B2 發現理解所需條件未記在案例；B1 查原話後補充，或記錄仍未知」，同時不讓其他案例消失。下方舊多案例返工反例仍保留為現行風險證據，**不能**原樣當新需求；具體生命週期未裁決，production 不變。

## 成熟做法與演進：先借鑑，再處理本案差異

研究順序是先找適用於本案目標的成熟公開做法、契約與實作，作為設計和施工的優先基準；**不要求 Caliburn 先重現相同故障，才准採用**。廠商公開的演進與失敗案例用來理解做法的適用條件與取捨，避免照搬已過時的補救措施。只有成熟方案無法滿足本案需求、與現有限制衝突，或實測證明不適用時，才補本案特有設計。下表區分「廠商公開記錄了前後演進」和「現行契約只說明如何使用」；單一廠商做法不自稱跨廠共識。查閱日期同上。

| 可核對的演進／契約 | 當時遇到的問題與修正 | 對本案的研究價值與限制 |
|---|---|---|
| [Anthropic Managed Agents 工程紀錄](https://www.anthropic.com/engineering/managed-agents)：模型改變後的 harness 假設 | Anthropic 記錄 Sonnet 4.5 接近 context 限制時會過早收尾，曾在 harness 加 context reset；換 Opus 4.5 後該行為不再出現，reset 反成負擔。 | Compaction／截斷閾值須以目前模型與長訪談實測驗證，不能把舊模型 workaround 寫成永久生命週期。**不能推出** Caliburn 應取消既有摘要或直接換模型。 |
| [同篇 Anthropic 工程紀錄](https://www.anthropic.com/engineering/managed-agents)：執行器與持久狀態耦合 | 最初把 session、harness、sandbox 放在同一容器；容器故障使 session 遺失，故障來源難以分辨。後來把持久 session 事件與可替換 harness、執行環境分開，harness 故障可依既有事件恢復。 | 問清楚「模型／工具迴圈中斷後，哪些是產品已確認事實，哪些只是候選工作」。這是**權責分離原則**，不是要求本機 Caliburn 增加容器、事件日誌服務或新 DB。 |
| [Microsoft Agent Framework checkpoint 文件](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)：Python 1.13.0 的邊界補強 | 原 checkpoint 在每個 superstep 後；1.13.0 另外在第一個 superstep 前、外部 response 交付後保存，讓完整 workflow 可 replay。文件明示 iteration count、來源 ID、checkpoint 順序的相容影響。 | 討論背景工作恢復時須畫出**輸入已接受、模型／工具已執行、外部結果已提交**各邊界，不能只寫「有 checkpoint 就可恢復」。更不能把框架 checkpoint 當成 JD／Memory 業務提交收據。 |
| [OpenAI Agents API events 契約](https://developers.openai.com/api/docs/guides/agents-api/sessions/events)：**現行契約，非公開歷史故事** | `session.idle`／串流關閉不等於 turn 成功；應看明確的 terminal event 或查回保存狀態；turn completed 亦不保證其中每個 tool 都成功。 | 本案須分清 A 的 final、JD effect、背景通知與 Memory publication；但**不能聲稱** OpenAI 曾因 Caliburn 這類故障才改成此契約。 |

研究每條生命週期時先填「可直接借鑑的成熟做法與適用條件 → 是否滿足 Caliburn 目標 → 若不滿足，缺口在哪裡及所需最小產品設計」。若有公開演進紀錄，再補「原做法 → 實際問題 → 後續改動與代價」，協助選擇版本與避免過時方案；**演進故事不是採用前置條件**。若沒有公開演進資料，就標「現行契約／推論」，不替廠商編造試錯史。以 [Codex Field Guide](https://tt-a1i.github.io/codex-field-guide/docs/source-basis/) 理解公開原碼分析與名詞，但它是非官方、固定在 2026-07-26 的原碼快照；現行 OpenAI 產品契約仍以官方文件為準。

## 以 Codex 公開做法複核既有架構：首輪定位，不是採用裁決

本輪問題：既有 Caliburn 是否把成熟 Agent 執行能力重造一份，或把短期執行狀態、產品資料真相與工具副作用混為一談？已定邊界是[產品概念](../../product-concept.md)的使用者效果；目前程式是底稿而非目標權威。本輪只查可觀察的責任分界，**不選新框架、不修改 production、不宣稱完成完整程式審核**。正常情境是一輪訪談跨多次工具操作後得到回答；反例是 JD 寫入已提交但最後回答失敗，或背景 checkpoint 已保存但 Memory 尚未發布。

以非官方、固定快照的 [Agent Loop](https://tt-a1i.github.io/codex-field-guide/docs/agent-loop/)、[Context 引擎](https://tt-a1i.github.io/codex-field-guide/docs/context-engine/)、[工具執行](https://tt-a1i.github.io/codex-field-guide/docs/tools-shell-patch/)與 [Runtime／Session](https://tt-a1i.github.io/codex-field-guide/docs/runtime-session-events/)作檢查問題來源；Codex 官方現行[Agents 架構](https://developers.openai.com/api/docs/guides/agents-api/architecture)區分 harness、可選 execution environment 與 application server。這些是比較基準，不能把 Codex 的 shell／sandbox／事件名稱直接變成本案需求。查閱 2026-09-25。

| 檢查面向 | 本案目前找到的證據 | 初步判斷／尚缺的證據 |
|---|---|---|
| 模型—工具迴圈 | 正式 A 組裝使用 LangChain `create_agent`（`experiments/jd-relational-app/src/jd_relational/consultant_context.py`）；B1／B2 同樣使用 `create_agent`；外層背景用 LangGraph `StateGraph`（`packages/consultant-memory/src/caliburn_memory/background_workflow.py`）。 | **非自行重寫一般 Agent loop。** 外層圖是在編排 B1／B2 與 publication，是否忠實承接新目標須按跨角色場景驗收，不能只因「自訂 graph」就判錯。 |
| 完整紀錄與本次請求視圖 | `ContinuationCompactionMiddleware` 由 canonical 訊息導出 request-only view，摘要與邊界存入既有 Agent state；[既有框架比較](../../specs/2026-09-05-conversation-compaction-framework-gap-review.md)已研究 LangChain／Deep Agents／LangMem 的限制，[現行設計](../../specs/2026-09-16-openrouter-continuation-compaction-design.md)記錄選材與失敗語意。 | **確實有本案自訂 compaction 接線，但不是自行重寫 loop。** 它是為保留原話權威而選的實作；是否仍為現行最佳選擇，應先核對既有比較的鎖定版本與產品要求，再看新框架能力，不能僅因有 prebuilt summarizer 就換掉。 |
| 工具結果與業務提交 | [現行背景流程](../../specs/2026-09-17-layered-memory-background-workflow-design.md)把 B1／B2 完成、prepare、publish 分階段；JD effect／final 不同的目標語意見[架構導覽](../../specs/2026-09-24-caliburn-layered-architecture-map.md)。 | **需做實際路徑審核**：工具結果怎樣回到模型、哪些已提交效果有可信收據、final 失敗時如何查回；本輪只查到架構和部分組裝，未據此宣稱所有工具都正確。 |
| Session、turn、背景 job、Memory publication | 正式 App 已用 PostgreSQL Saver，外層背景圖有 checkpoint 與 publication node；[架構討論規範](../../architecture-discussion-standard.md)要求正常、異常與並行生命週期分圖。 | **這些時間尺度不得共用一個「成功」判斷。** 目標版本／引用和退役 C 尚未施工；下一輪先畫責任與資料真相，再把已確認的正常及異常流程落成可驗收時序，不預設新 queue、registry 或事件服務。 |

此首輪找到了「已有框架能力」和「本案特有接線」的分界，**尚未找到能證明某項自訂接線用錯的反例**。若後續實測或鎖定版官方能力顯示有可直接取代的成熟方案，就以實際效果、權威資料保留、恢復語意與成本比較，必要時替換；不把既有程式當成必須保護的架構，也不為了像 Codex 而引入其不適用的 shell、sandbox 或整套服務。

## State／資料權威：2026-09-25 的討論底稿（候選）

**本輪問題：**長訪談與背景整理中，「哪些內容要跨步驟延續」不能等同「哪些內容已成正式工作事實」。正常例子：A 保存原話、跨步驟保留待問線索，B1／B2 後來發布 Memory；反例：JD 工具已提交但 A 的 final 失敗，或背景 graph 有 checkpoint 但整版 Memory 尚未發布。本輪只盤點責任與時間尺度，不裁決新的欄位、服務或資料表。

公開框架並沒有通用的單一 `State` schema。[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) 的 state 是 graph 節點共享的快照；其 [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 把 thread checkpoint 與 app-defined Store 分開，[runtime context](https://docs.langchain.com/oss/python/langgraph/graph-api#runtime-context) 又可傳遞不屬於 graph state 的依賴。[Google ADK Session](https://adk.dev/sessions/session/) 區分對話 events 與會話內 scratchpad state。[OpenAI Docs 的 Sessions／Turns](https://developers.openai.com/api/docs/guides/agents-api/sessions)區分持續 session、一次 turn 與明確終局；[Events／Items](https://developers.openai.com/api/docs/guides/agents-api/sessions/events)區分即時事件與已保存項目。[Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents)明確區分持久 session 與模型當前 context window。這些是各產品的**官方契約**；下表是 Caliburn 為檢查責任而作的**研究歸納**，不是各家共同規定的元件清單。

| 應分辨的責任 | 現行程式可核對的例子 | 不可誤認為 | 目標狀態／待核實 |
|---|---|---|---|
| 完整互動紀錄與原話 | A 的 Saver `messages`、原話來源 owner | 本次模型 request 必須重送的全部文字；摘要 | 目標仍要求可回查完整問答；目前各入口保存與讀取一致性按旅程驗收 |
| Agent／workflow 執行快照 | `ConsultantState`、B1／B2 agent state、`BackgroundMemoryWorkflowState` 與 PostgreSQL Saver | JD 操作已提交，或 Memory 已正式發布 | 現行有 checkpoint；重啟與副作用邊界須按具體時序核實 |
| 跨步驟分析延續 | `interview_working_state` 是目前 A 的一種實作 | 員工原話、已發布案例／理解或模型隱藏推理 | 產品只已確認「分析需延續」的效果；未鎖定未來元件／欄位 |
| 對話壓縮與模型請求視圖 | `continuation_compaction` 保存摘要與切點；middleware 組裝 request-only view | 完整歷史、正式 Memory 或業務提交收據 | 摘要與切點可持久；完整 request view 是按需投影；長訪談保真與效率另驗 |
| 正式業務資料 | PublicationStore 的正式 head／artifact 與 JD SQL 工作稿 | B1／B2 staging、graph state、working item | 原話→案例→理解→JD 新版本／引用鏈是目標，尚未施工 |
| 已確認副作用與工作進度 | JD run／operation 收據、背景 admission／publish 進度 | Agent final 文字、工具意圖或 `session idle` | 已提交、未知、失敗、已發布須各有可查依據；現行 Q12 缺口獨立 OPEN |
| 本次執行依賴 | `ConsultantContext` 的文件身分、run、來源／Memory session 與取消控制 | 模型應生成的欄位，或所有依賴都應複製到 checkpoint | 由 App 注入並驗證 scope；哪些內容需恢復時重建，以實際入口核實 |

**初步收斂，不是產品裁決：**圖上應區分「事實權威」「執行快照」「衍生分析／摘要」「當次請求視圖」及「提交／發布結果」。一種責任可由現有框架或 App 元件承擔，**七行不是七個新服務／資料表**；一個現有 class 同時承載多種欄位也不自動構成錯誤。先以具體時序核對其所有者、保存邊界與恢復語意；若反例證明混用造成資料遺失或權威衝突，再比較成熟框架能力、薄接線與替換。不得因 LangGraph Store 可跨 thread 而推論本案應跨職務檔案共享員工資料。

**後續研究與核對：**把此分類當作畫圖時的檢查欄，不當成 Owner 必須決定的元件清單。先沿 A 的一則員工輸入，從原話保存、分析延續、模型 request、可選 JD effect 到回合終局／下一回合，核對正常及「JD 已提交但 final 失敗」兩個時序；再用相同方法處理 B1／B2 的候選、checkpoint 與 publication。技術實現先查 LangGraph 能力與現碼；只有會改變產品效果或資料權威的真分歧才交 Owner 裁決。

### 已定執行前提與跨廠對照（2026-09-25 補核）

**已定前提：LangGraph。**不再把 OpenAI Agents API、Anthropic Managed Agents 或直接模型 API 列成待選的 Caliburn 執行框架。研究它們是為了檢查工作分層、狀態延續、上下文、工具結果與恢復等成熟做法；並不等於要遷移供應商或複製託管服務。現行新 App lock 為 LangGraph `1.2.11`、LangChain `1.4.0`、`langgraph-checkpoint-postgres` `3.1.2`（`experiments/jd-relational-app/uv.lock`）；以下官方網頁是查閱日公開契約，凡涉及具體新 API 是否可用，仍須核對這組鎖定版本。這是 Owner 的框架決定；下表各欄只說可核對的公開依據與本案適用邊界。

| 來源與性質 | 可借鑑的具體做法 | 在 LangGraph／Caliburn 的核對問題，不直接推出新元件 |
|---|---|---|
| [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)；**框架官方契約** | State 是節點共享的執行快照；checkpointer 按 thread 保存，Store 保存 App 定義的資料；runtime context 可注入本次依賴。節點可能重執行，因此有副作用的操作須檢查冪等與已提交結果。 | 目前 A／B1／B2 及外層背景各有哪些 state、checkpoint、業務提交？哪些只需由已知資料現場投影，不必再保存一份？Store 可跨 thread 不意味跨職務檔案共享。 |
| [OpenAI Agents 架構](https://developers.openai.com/api/docs/guides/agents-api/architecture)、[Sessions／Turns](https://developers.openai.com/api/docs/guides/agents-api/sessions)、[Events／Items](https://developers.openai.com/api/docs/guides/agents-api/sessions/events)；**官方託管服務契約** | 將 harness、可選執行環境和產品 application server 分責；session 可跨 turn 延續；即時事件、保存項目與 turn 的完成／失敗／取消不同。函式工具仍須由產品程式執行並回傳結果。 | A 的模型迴圈、原話與 JD／Memory 寫入是否各有清楚 owner？「收到事件」「工具已執行」「業務已提交」「回合 final」不可合併成一個成功標記。這些契約不是要求改用 OpenAI 託管 Agent。 |
| [Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents)、[Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)；**廠商工程紀錄** | 持久 session 紀錄與可替換的 harness、工具執行環境分離；session 不是模型 context window，先前內容可從持久紀錄選取再組裝；compaction 是有損的上下文管理。 | A 的 canonical 問答與本次 request view 是否真的分開？壓縮後仍能否回查原話？中斷後哪些事實從 DB／Saver 取回，哪些需要重新組裝？不照搬 Anthropic 的託管事件服務。 |
| [Codex Field Guide：Runtime／Session](https://tt-a1i.github.io/codex-field-guide/docs/runtime-session-events/)、[Context 引擎](https://tt-a1i.github.io/codex-field-guide/docs/context-engine/)；**非官方、固定 2026-07 源碼快照的導讀** | 把外部控制、長期 session、一次 turn、模型／工具 step、輸出事件分層；記錄路徑與面向模型的歷史視圖分開，倉庫資料按需讀取，壓縮後關鍵事實應能重讀。導讀亦明言「有事件流」不等於整套 Event Sourcing。 | 借它檢查「一輪訪談內多次工具操作」和「跨輪可恢復原話」的分界；不把 Codex 的 Op／Event 名稱、shell、sandbox 或快照細節當成 Caliburn 必需元件，也不稱它為 OpenAI 現行官方保證。 |

**本案研究歸納，不是供應商共同 schema：**持久真相應可回查；執行快照要能延續未完工作；模型每次只見為當前任務組裝的有效視圖；有副作用結果以 App 的正式提交／收據判定，而不由模型 final、checkpoint 或摘要代替。這是可驗收的責任區分，不要求七個資料表、第二份 event log 或另一個 runtime。

### 先按 A 的一輪畫時間軸（核對提綱，非現況 PASS）

| 時點 | 應核對的持久事實或當次視圖 | 現有位置／驗證邊界 |
|---|---|---|
| 員工送出一則原話 | 哪個入口保存可回查的完整問答、如何綁到正確職務檔案；保存成功不等於 A 已完成回答 | A 的 `AgentState.messages`／Saver、App 輸入 run 紀錄與來源 owner；須核對實際寫入順序 |
| A 在同一回合多次推理與用工具 | 跨步驟分析線索與工具往返可延續；文件身分、run、取消等依賴由 App 注入，不交模型填 | `ConsultantState` 有 `interview_working_state` 等欄位；`ConsultantContext` 持有本次依賴；需檢查跨 checkpoint 與重開的有效範圍 |
| 每次模型請求 | 從持久紀錄、正式 JD／Memory 和當下工具結果組裝；摘要與近期訊息是 request view，不回寫覆蓋 canonical 原話 | `ContinuationCompactionState` 只記摘要、涵蓋邊界與 digest；模型實見內容須由 outbound capture 驗證 |
| 若 JD 工具成功提交 | 正式 JD 與操作收據成為可查事實；模型 final 尚未產生也不會撤銷該提交 | JD SQL／run-operation receipt；需以 DB 查回和失敗時序驗證，不以 ToolMessage 或最終話術代替 |
| A 結束／失敗／下一回合 | final 狀態、已提交 JD effect、背景工作進度分別查回；下一回合從仍有效的資料重建必要視圖 | 現行 Q12 仍有已提交效果未穩定供模型看見的缺口；本表不宣稱恢復和長訪談全程已 PASS |

**現碼已核對到的 A 時序邊界（靜態審核，不是端到端 PASS）：**`AiRuntime.start` 先由既有 owner 依職務檔案身分、run 身分與 JD revision 准入；只在同一文件內序列化 handle 建立，不能據此說全 App 只能同時處理一份文件。`_run` 把原始員工輸入與 run 資料交給 LangGraph `graph.invoke(..., durability="sync")`，`thread_id` 是該文件身分；本次依賴透過 `ConsultantContext` 注入。這確認執行入口與保存機制，但**尚未以實測釘死員工輸入相對於首次模型外送的落盤順序**。依據：`experiments/jd-relational-app/src/jd_relational/ai_runtime.py` 的 `start`、`_start`、`_run`。

**副作用與失敗分開看：**`_settle` 依保存的工具呼叫綁定核對 SQL 操作收據，處理 pending tool result，再關閉本回合；`inspect_run` 分別回傳 `run_status`、`input_state`、`response_message_id` 與已確認 JD 收據。已提交 JD 不由最終回答文字推定，也不因缺 final 自動重做。重開時 `_recover_previous_run` 明確只核對原始狀態與收據、完成 closure，**不續跑模型或再執行工具**；這是現行 Caliburn 的恢復契約，不應誤稱 LangGraph 自動提供完整業務恢復。依據：同檔 `_settle`、`inspect_run`、`_recover_previous_run`。尚需以既有測試／trace 核對跨回合實見 context、下一回合對已提交 JD 的可見性，以及目標架構退役 C 後的責任；此靜態審核不改變 Q12 或產品驗收狀態。

上述 A 時間軸後續仍須以既有測試／trace 補齊逐點證據；B1／B2 的首輪「通知持久接受→固定來源→候選／checkpoint→共同正式發布→失敗恢復」核對見下節。若發現不相符，先判定是框架狀態、App 業務 authority 或模型 request view 的問題，不先新增通用 State 引擎。

### B1／B2 背景生命週期首輪核對：現行與目標分開

**本輪問題：**A 通知後，何時算背景工作被持久接受、何時算案例／工作理解真的正式生效？B2 發現理解所需資訊未在案例中、程序中斷或發布時版本已變時，哪些工作可以安全接續？本輪只核對既有 owner、程式與既有測試，**不**裁決新的逐物件版本格式、C 退役施工、模型 prompt 或新排程服務。目標效果依[目前決策](../../current-decisions.md)與[分層架構導覽](../../specs/2026-09-24-caliburn-layered-architecture-map.md)；以下「現行」不得當成新目標已驗收。

| 時點與產品效果 | 現行可核對的 owner／證據 | 尚未由此證明的目標 |
|---|---|---|
| A 通知，不等待 B1／B2 同輪做完 | `background_dispatch.py` 只由已保存的整理請求決定新 target；`background_admission.py` 的 document row 分辨 `idle／queued／running／blocked`，准入 row 只證明接受，不能證明模型執行或 Memory 發布。重複 wake 在同一 dispatcher 只作 single-flight。 | 「通知工具收據已持久保存」到背景准入之間的完整交錯時序、目標 C 退役後的交互，不能只靠背景 worker 的狀態推論。 |
| 固定本次來源與讀取基準 | App 的 dispatcher 固定 target，先 `dispatch` 當前 batch 再呼叫 workflow；外層 `BackgroundMemoryWorkflow._load_base` 固定 publication revision、Memory version 與 source reference。B1 可按需查同文件較早原話，B2 可按需查候選案例及沿案例引用回查原話；batch 不是讀取權限邊界。 | 第 17 輪才提出的更正不會憑空進入此前固定的來源；須另驗 A 如何維持新更正到後續涵蓋它的背景工作。 |
| B1 案例 → B2 工作理解 | 兩個 Agent 各有 durable attempt；外層 graph 先等 B1 completed stage，再讓 B2 讀該 stage。現行 B2 `case_rework_required` 會帶案例、已讀來源及理由，外層以新 B1 attempt 傳回 review、要求重讀精確來源，之後重跑 B2；返工有界。 | 這只證明現行流程和資料交接；**目標已改為 B2 交流理解所需而案例未記的資訊**，由 B1 在案例層處理已知與未知，不把 B2 當案例錯誤審核者。現有回路是否可承接仍待驗。 |
| 候選、正式發布 | B1／B2 stage 與 bundle 在正式發布前留在 Saver／Store，不能當成 A 可用的正式 Memory。外層先 checkpoint 完整 `PublishRequest`，`PublicationStore.publish` 再以同一 expected revision 做條件提交；成功時一併保存 head 與 operation receipt，`processed_source` 才推進。 | 既有 bundle／digest 不能直接宣稱滿足新目標的逐案例／理解物件版本、固定跨層引用鏈與 JD 待核對規則；這些仍是後續設計／施工。 |
| 中斷、版本衝突、未知提交 | pending graph 用原 checkpoint `resume()`；B1 完成而 B2 失敗時不重做 B1。發布回覆遺失沿同一 request／receipt 查回；CAS stale 拒絕舊候選，重新載入 head、重新建立 B1／B2 語意 attempts，有次數界線，耗盡轉 blocked。 | 「有 checkpoint」不等於任意中斷都自動復原；自然模型與真實使用者旅程未由固定回覆測試證明。stale 後重新分析是否忠實保留較新更正，仍需語意驗收。 |
| 最終未解失敗，A 下一回合如何知道 | `background_coordinator.py` 在 App ready 後掃文件並 wake；`background_availability.py` 對仍欠來源的 blocked row 只給 A 一次每員工回合的「尚未整理」系統提示，已自動修好的暫時錯誤不提示。 | Owner 已確認最終未解失敗要有安全的原因與下一步；現行提示未使用持久 `error_code` 表達這兩項。具體可見性與恢復責任待設計，不新增第二份進度權威。 |

**已存在的分層證據，不重做同一考卷：**`packages/consultant-memory/tests/test_background_workflow.py` 覆蓋一次 bundle 發布、B2→B1 來源型返工、有界 blocked、stale 重整、來源已涵蓋短路與不明發布結果的同 request receipt；`experiments/jd-relational-app/tests/test_layered_background_dispatch_postgres.py` 以真 PostgreSQL 驗證一通知一發布、B2 失敗後重開不重跑 B1、commit 回覆遺失後不重複發布。這是控制流與持久化證據；[真模型試跑紀錄](../../specs/evidence/2026-09-23-gpt6-cw-natural-trial.md)另有部分 B1／B2 真請求及已發布來源的查回，但不等於目標版本／引用、完整長訪談與 JD 品質通過。框架提供的 checkpoint 不替 App 保證業務提交；[LangGraph 官方 Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[OpenAI 官方 Events／Items](https://developers.openai.com/api/docs/guides/agents-api/sessions/events)與 [Anthropic 工程紀錄](https://www.anthropic.com/engineering/managed-agents)都支持分清執行紀錄與當前可用視圖，具體 publication／receipt 仍是本案契約。CAS 衝突後刷新並有界處理的原則也見 [AWS 官方 optimistic locking](https://docs.aws.amazon.com/us_en/amazondynamodb/latest/developerguide/BestPractices_OptimisticLocking.html)；這是並行控制參照，**不是建議改用 DynamoDB**。

**本輪交錯核對題：**以兩條時序審核新目標而不先施工：① B2 在分析工作理解時指出具體案例錯誤與原話，B1 修正案例與其候選集合，B2 再評估受影響的工作理解，確保候選不外露；② 背景已固定第 16 輪來源，第 17 輪員工更正並被 A 保存，舊背景不冒稱已處理第 17 輪，後續工作確實涵蓋更正，若最終 blocked 則 A 得到可理解的安全提示。先沿現有 source owner、admission、Saver、publication 與 A 工作狀態找 owner；只有反例證明缺能力，才比較薄接線或替換，不先新增 Agent、queue、registry 或資料表。靜態核對結果如下；模型語意與跨回合效果尚未驗收。

### 兩條交錯時序的現碼核對（2026-09-25；靜態審核，非目標驗收）

| 時序 | 現行程式與既有測試可支持的範圍 | 尚不能宣稱通過的新目標 |
|---|---|---|
| B2 分析理解時發現具體 B1 案例錯誤 | `understanding_maintenance.py` 要求 B2 先讀該案例及其精確原話，`request_case_rework` 保存來源與理由；`background_workflow.py` 組成含案例定位、候選正文、來源與理由的 `CaseRuntimeReview`，不發布該候選。`case_maintenance.py` 把來源轉成 Runtime 提供的 evidence key，要求 B1 讀完，再開新 B1 attempt；其後 B2 重跑，只有完整 bundle 經 publication 才對外可見。`test_background_workflow.py` 有既有案例修正、未發布候選重建及第二次返工阻擋的離線反例。 | 這證明**不是只有籠統「重做」命令**，也不等於已驗證新目標所有品質：目前新 B1 attempt 從同一正式 base 與固定來源重開，上一份未發布候選的其餘改動不直接成為新 attempt 的狀態；尚須用含多個無關案例的情境核對 B1 返工是否保住該批應有資訊，並以實際模型／正式版本確認 B2 後續的工作理解分析沒有帶回已指出的錯誤。不能由單案例 fixture 推斷整體效果。 |
| 背景固定至第 16 輪後，第 17 輪提出更正 | `conversation_sources.py` 將 target 與 batch 釘在已保存的完整訪談回合；`test_interview_window_source.py::test_a_fixed_target_is_never_widened_by_later_speech` 驗證較晚原話不會擴張舊 target。`background_dispatch.py` 只有讀到另一次**已保存的整理請求**才准入新 target，`PublicationStore` 的 `processed_source` 記錄舊工作實際涵蓋的固定來源；因此舊背景可以合法發布「至第 16 輪」的成果，但不能聲稱它處理了第 17 輪。原話由 Saver／source owner 保留；A 的 Working State 可保留含更正來源的暫時 item。 | 「原話可回查」不等於「A 必然建立／持續看見該更正 item」，也不等於第 17 輪會**自動**進入 B1／B2。下一次有效整理通知須以已發布 cursor 之後的連續完整來源納入更正；目前仍需驗證跨摘要／重開時 A 不被較舊正式理解蓋回，以及 B1／B2 最終按原話重審。新目標不要求每次更正立即觸發背景，但不能把舊批次的成功當成更正已承接。 |

**失敗可見性的獨立缺口：**現行 `background_admission.py` 持久保存 terminal `blocked` 的 `error_code`；`background_availability.py` 只在未涵蓋來源仍 blocked 時提供「最近一段尚未成功整理」與範圍，尚未將安全原因與下一步提供給 A。暫時錯誤若被既有恢復解決不需通知；真正 blocked 的目標效果仍 **OPEN**。這是現有 owner 的呈現／驗證缺口，**不是**要求新通知服務或資料表。

**下一驗收邊界：**先以同一文件、兩個來源範圍的隔離反例查正式 cursor、B1／B2 候選與 A 下一回合實見資訊；另以多案例返工反例核對未受影響資訊。若反例成立，再依責任 owner 提出修正；此處不預先修改 prompt、背景排程、Memory 架構或 C 退役施工。

### 多案例返工的隔離反例：現行流程容許靜默漏案（2026-09-25）

**本次實際執行的零付費反例，不是自然模型品質測試。**以現有 `test_background_workflow.py` 的固定回覆 harness、記憶體 Store／Saver／SQLite 和單一固定來源，首輪 B1 建立兩個互不相同的新案例 A（告警確認）與 B（結果記錄）；B2 讀 A 及其原話，只指出 A 錯誤並要求返工。次輪 B1 讀該精確原話、建正確的 A′，但沒有重建 B；次輪 B2 依 A′ 建工作理解並結束。實測得到 `status=completed`、`case_rework_count=1`、正式案例數為 1、原 B 不在正式 manifest，且 `processed_source` 已推進到整批固定來源。未修改 production 或正式資料。

**責任定位：**`background_workflow.py::_prepare_case_rework` 清空兩層候選、換新 B1 attempt，只帶回被指出的 `CaseRuntimeReview`；`case_maintenance.py::run_attempt` 從同一正式 base 和完整固定來源新建 stage，並不把首輪其他正確候選當作新 stage 的保留義務；`finish` 檢查 review 原話已讀及「當前案例各有 guide route」，但沒有核對首輪未受影響候選或這批來源的案例涵蓋。`_assemble_bundle` 只發布次輪 stage 的當前集合。因此這不是 B2 無權查所有案例，也不是 SQL CAS／原子提交失效；是**語意返工的候選保留／涵蓋判準**缺口。原始訪談仍在 source owner，故不是原話被刪除；風險是正式案例漏掉 B、下游 B2／A 導覽不到它，同時來源 cursor 已顯示整批處理完成。

此反例證明「**允許**漏案且完成」，不證明真模型必然漏案、所有來源都必須一對一轉成案例，亦不裁決哪種修正最佳。既有單案例返工、B1/B2 checkpoint、發布收據與 CAS 測試仍有效，只是未覆蓋此多案例交錯。下一步候選須以**正確來源、案例差異可回查、不把錯誤 A 留下、B 不靜默消失**為共同驗收，不以「省一次模型呼叫」凌駕完整性：

**與舊設計的明確張力：**[背景 Workflow 設計 §5.2](../../specs/2026-09-17-layered-memory-background-workflow-design.md)要求被拒且尚未發布的 candidate 不直接匯入新 attempt；如仍成立，新 B1 需依原話重新建立，舊 candidate ID 不可冒充正式身分。該文件 §2.4 的「不新增 coverage manifest／第二個 verifier」針對當時 C repair→B2 impact 接點，不是本次漏案已被證明安全；但也不能藉此直接提議新表或通用驗證服務。下列候選若改變「新 attempt 從乾淨 base 開始」的契約，必須先明講這個差異再裁決。

| 候選語意（尚未裁決） | 可以沿用的 owner／機制 | 需要驗證的代價與風險 |
|---|---|---|
| 全批重新分析，但把首輪完整候選作為待核對輸入，發布前逐案說明保留／改寫／不採用 | 現有固定來源、新 attempt、B1 stage 與 B2 review；不另建 Agent 或資料表 | 候選非正式權威，不能直接複製錯案；若只是靠 prompt 提醒，是否仍可漏 B；需處理新候選 ID 與引用分配 |
| 由 B1 修指出的案例並處理其餘候選；B2 只重評受影響的工作理解 | 現有 stage、已讀原話、B2 可按需讀全案例以完成自己的分析 | B1 必須知道候選何者可保留、何者受 A 更正牽動；不能假定 B 永遠不受 A 變更影響，亦不能繞過同批來源涵蓋檢查；不可把 B2 改成全批案例審核者 |
| 重新分析固定來源，完成前以首輪候選與來源作差異／涵蓋對帳 | 現有正式 base、候選 stage、原話及來源引用；可在既有完成／發布邊界判斷 | 必須允許有理由地拆分、合併或撤銷錯誤候選，不能機械要求 ID 不變；若判準需要新的模型判斷，須有界，不能無限循環 |

[LangGraph 官方 subgraph 文件](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)把不同 state schema 的父子交接列為明確映射責任；[官方 Persistence 文件](https://docs.langchain.com/oss/python/langgraph/persistence)只保證執行狀態可保存／恢復，並不替產品檢查案例涵蓋。故「返工時傳什麼、可丟什麼、正式發布前怎麼判定涵蓋」仍是 Caliburn 業務契約，不能稱作框架預設。**建議的下一個設計 gate** 是先選定多案例返工的保留語意，再以同一隔離反例補回歸；若要裁掉首輪 B，須有可核對的來源與理由，而非因重開 attempt 自然消失。這一節只記證據與候選，未改 production、未接受任一方案。

**2026-09-25 追加核對（Owner 對「不可無理由消失」表示大致同意，尚非施工裁決）：**成熟公開模式支持「產出候選→給具體回饋→有界修訂→重新檢查」，但不替本案規定要保留哪個案例：[Anthropic evaluator-optimizer](https://www.anthropic.com/engineering/building-effective-agents)描述可有界的評估／改進迴圈；[OpenAI 官方 multi-agent 指南](https://developers.openai.com/api/docs/guides/responses-multi-agent)提醒固定依賴鏈與共享可變狀態未必適合自由平行子代理；[LangGraph time-travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)提供 checkpoint fork，但 fork 後的節點可能重執行，並不自動形成安全的業務草稿修訂。這些是不同產品／框架的公開能力，**不是**三家共同指定一種 Caliburn API。

現碼還有兩個會影響選擇的具體限制：① `CaseMaintenanceStage` 把 evidence keys、已讀狀態、upserts 與 change log 存在一次 attempt，`run_attempt` 從正式 base 新建 stage；直接複製 completed stage 或舊 evidence keys 並非已驗證的續作。② `revise_case` 可修本 attempt 新建案例，但 `retire_case`／`split_case`／`merge_cases` 對未發布 candidate-only ID 明確拒絕；若採「保留整份草稿再修」，必須先解決被證明完全錯誤的草稿如何明確撤銷，不能只把 A、B 全部原封不動帶入。另一方面，B2 的最低必讀案例是由最後 B1 stage 的變更推導；若 B 仍列於候選變更，B2 至少會讀 B 以分析工作理解；若 B 已在新 stage 靜默消失，它連最低必讀集合都進不了。**B2 能讀 B 不等於它負責驗證 B1 的案例涵蓋。**這些是**現況限制／可利用的既有 gate**，不是新目標已裁決。

**後續語意已修正：**Owner 保留的是 B2 在理解分析缺資料時對 B1 的例外交流，**不是**「B2 判案例錯→B1 全批返工」。B1 應先在自己案例層核對既有原話，補充可證實資訊；若無法釐清，就在相關案例保留已知與未知。下方「保留舊草稿／全批重建」的比較是針對先前*案例錯誤返工*假設的歷史研究，不能直接變成新的必要施工；但舊流程可靜默漏掉其他案例的反例仍是現行風險。新目標的接續、共同發布與恢復方式要再按這個更窄的例子討論，stale 正式 base 的重整也不能混稱。

### 正常分工與例外交流（2026-09-25；已選交流，舊替代方案保留沿革）

兩案都以 **B1 維護案例 → B2 依案例維護工作理解 → 共同發布** 為正常路徑；B2 不主動對案例做完整性或正確性驗收。

| 例外選項 | 可簡化之處 | 必須回答的邊界 |
|---|---|---|
| **不設 B2→B1 專用交流回路（歷史備選）** | 少一次跨角色往返。 | B2 發現理解所需資訊未寫在案例時，若無法告知 B1，缺口可能一直留在案例層。這是當時的取捨，Owner 後續已選擇保留窄範圍交流。 |
| **保留窄範圍「資訊缺口交流」（已確認的目標）** | B2 只說明理解需要哪項資訊、案例目前缺什麼；B1 核對原話，在案例寫入有根據的已知或未知；B2 再做自己的理解分析。 | 不得變成 B2 審核案例對錯或指揮 B1 怎麼寫；同背景工作如何接續、何時共同發布和有界失敗仍待設計。 |

Owner 已選擇窄範圍例外交流；上表的「不設交流」保留為決策前替代方案，並非現行目標。這是本案產品取捨，並非 OpenAI／Anthropic／LangGraph 指定要有「B2 案例審核」或「B2 退回工具」。下文返工草稿方案是**先前錯誤假設下的歷史研究**，保留可追溯性，不自動作為新目標的下一步。

### 先前案例錯誤返工方案比較（2026-09-25；歷史候選，非新目標施工計畫）

**當時的決策題（已由上方後續澄清取代）：**同一背景工作中，B2 指出案例 A 的具體錯誤，B1 如何修 A 而不讓另一個案例 B 無理由消失？這反映現行 `case_rework_required` 的多案例風險，**不是**目前確認的「B2 因理解缺資訊向 B1 交流，B1 把已知與未知寫進案例」的正常例外場景。以下甲／乙保留當時候選，不據此預設新目標必須重建整批 B1 草稿。

| 方案 | 正常／返工語意 | 優點與代價 |
|---|---|---|
| **甲：保留同一背景工作的 B1 未發布案例草稿，另開語意返工步驟（建議）** | B1 看見原候選、B2 指出的具體錯誤與原話，修訂 A；B 仍在草稿中，除非 B1 明確修訂、合併、拆分或撤銷並留下可核對的原因與來源。B2 只在修正後案例上重新分析受影響工作理解。 | 最直接保住已做過的案例工作與引用；但現碼的新 `run_attempt` 從正式 base 開始、candidate-only 的撤銷／拆合受限，不能只改 prompt 或原樣複製舊 checkpoint。需設計同工作草稿與新語意步驟的身分、合法操作及恢復邊界。 |
| **乙：從正式 base 重建 B1 案例草稿，但交付上一輪全部候選供逐項對帳** | B1 重新核對固定原話；每個舊候選都要明確對應新案例、修訂／合併／撤銷或說明不採用，不能只傳被指出的 A。B2 再分析工作理解。 | 較貼近現行「新 attempt、舊候選不直接匯入」規則；但會重做已正確的案例、增加模型步驟與 ID／引用重配，僅靠提示不能證明對帳完整。 |

**研究依據與界線（2026-09-25 核對）：**[LangGraph 官方 Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)建議把跨步驟仍需使用的草稿放在 state，而可從其他資料推導者不重複保存；[Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)要求不同子圖狀態在交接邊界明確映射。這些支持清楚保存／交接候選，**不**自動替本案處理案例取捨。[OpenAI 官方 Orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration)強調專家分工要窄，不表示 B2 應變成 B1 的總審核者。[Anthropic Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)區分固定步驟與 evaluator-optimizer，後者需要明確評估標準；本案的 B2 首要任務是工作理解，不能只因它偶爾回報案例錯誤，就改稱案例 evaluator。上述是公開模式的適用性推論，不是大廠對 Caliburn 返工 API 的共同規定。

**後續停止線：**甲／乙只是針對舊「案例錯誤返工」假設的研究比較，先前偏向甲的建議不再是新目標的預設方向。下一輪先以「B2 需要某條件但案例未寫；B1 查原話後可補充／仍只能記未知」及「另一個案例不可靜默消失」釐清交接和發布；有需要才借用舊研究的草稿保留技巧。未獲具體生命週期與施工裁決前不改 production。

### B2 資訊缺口交流：同一背景工作的接續比較（2026-09-25；目標語意已確認）

**本輪只問一件事：**B2 分析工作理解時，需要的條件尚未寫在某個 B1 案例裡，應如何在不讓 B2 越權寫案例、也不讓本批其他案例消失的前提下繼續？這不是上節歷史上的「B2 審判 B1 錯案」。已確認的效果是：B1 對案例及來源涵蓋負責，B2 對理解負責；已有原話就核對後補入案例，原話不足就如實保留未知；候選在完整共同發布前不給 A 或 JD 當正式依據。此處不決定新工具、資料表、草稿 ID 或模型請求次數。

| 接續方式 | 正常與例外時會發生什麼 | 在本產品的主要取捨 |
|---|---|---|
| **固定工作內的有界交流（Owner 已選目標語意；工程待審）** | 同一份固定來源與正式 base 下，B1 保留本次尚未發布的案例候選及來源涵蓋；B2 只指出自己分析所缺的資訊及受影響理解；B1 查原話後補充有據內容或明列未知，再交 B2 重評相關理解。兩層候選一致才一次發布。 | 最直接保留本批已做的工作；仍須設計「哪些未受影響候選必須保留或明確處置」及有界往返，不能以現碼新 attempt 默默清空草稿。 |
| **終止本次工作、另開一次重新整理** | 不發布有缺口的候選；新工作重新讀固定來源與最新正式 base，再做 B1／B2。 | 恢復邊界簡單，但可能重做大量正確案例；若只重建被指出的案例，已有多案例漏案反例。不能把程序重開誤當語意缺口已解。 |
| **由 B2 直接補案例，或等員工答完才發布** | 跳過 B1 交流，或把未知留在工作中等待日後訪談。 | 前者破壞已確認分責；後者會讓可如實標記未知的有效成果無限期不可用，與 `PROD-G2-004` 衝突，因此不建議。 |

首選候選的**可畫時序**：通知持久接受 → 固定本次新增原話範圍及正式 Memory 讀取基準 → B1 建立完整候選集合與來源涵蓋 → B2 依候選案例分析；若發現資訊缺口，將「缺什麼／影響哪項理解」交 B1 → B1 在同一未發布工作內查原話並補已知或未知，**其他候選不得無理由消失** → B2 依更新後案例重評 → 驗證整版來源、引用與兩層一致 → 原子發布並推進該批來源進度。若交流超過有界恢復能力，停在可診斷的未發布狀態，不把未處理來源標成完成；員工須回答的缺口由 A 後續訪談處理，**不**在背景工作中等待員工回覆。此時「同一工作」是業務來源與候選保留的語意，不先假定必須復用同一個 graph checkpoint 或 Python 物件。

**外部依據與限制：**[LangGraph Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)建議先拆清步驟、跨步驟要用的資料才放 state、可推導資料不重複保存，並依錯誤類型決定回路；[LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)要求不同 state 範圍的交接明確映射。這支持明確保留／傳遞候選，不保證 Caliburn 的案例涵蓋或 publication。[Anthropic Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)把固定工作流與有評估準則的 evaluator-optimizer 分開；B2 的職責是形成理解，不應因它能報缺口就改成案例總審。[Microsoft handoff](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff)說明角色間可有明確交接，但不要求本案採動態 handoff。**「同工作、有界交流、共同發布」是本案依既定效果提出的候選組合，不是宣稱四家都有相同內部架構。**上述公開頁面查閱於 2026-09-25；具體 API 若進施工，仍需核對本案鎖定版本。

**後續與驗收門檻：**Owner 已同意「同工作、有界交流、其他候選不得無理由消失、兩層一致才發布」的目標語意；[唯一生命週期設計稿](../../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)承接具體時序與工程未決，此研究比較不作 production 授權。用「本批兩個案例 A／B，B2 只缺 A 的條件」驗證：B1 可從原話補 A 或記未知，B 仍存在或有可核對的不採用理由，B2 不寫案例，發布前 A／JD 看不到候選，成功後兩層版本與引用鏈一致；中斷、stale 與重開不得將缺口候選標成已發布。舊多案例反例只證明現碼允許漏案，不等於這個新目標方案已失敗或已通過。

## Caliburn 候選分層：先說效果，不先命名元件

1. **A 職務顧問**：唯一對員工訪談／回答的角色；按需回查已確認資訊，必要時追問；有足夠依據時才透過 App 業務入口編輯 JD。這是本案產品決策，不是「一個模型 turn 就必須使用 JD 工具」。
2. **B1 案例整理、B2 工作理解整理**：B1 維護案例與來源涵蓋，B2 依案例分析並維護工作理解；B2 不是 B1 的案例驗收者。兩者不直接問員工；未能判定的員工問題由 A 後續訪談承接。兩層候選一致才共同發布。B2 若因理解分析發現案例未記所需資訊，向 B1 交流缺口；B1 在案例層寫明有依據的已知與仍未知，B2 只處理自己的理解。具體接續待設計。固定來源與引用版本是本案特殊領域契約，通用 agent framework 不會自動實現。
3. **上下文延續能力**：按需資料讀取、跨步驟／跨回合分析延續、compaction 各解不同問題。工作事實的長期真相仍是原話／案例／理解；摘要不能成為第二份權威。是否由獨立模型呼叫、middleware 或模型原生機制實現，留到實現層比較。
4. **決定性保存與可查結果**：模型提出工具意圖；App／Domain 判斷身分、版本、來源、合法性與提交；其他讀者只有在正式提交／發布後才能當真。恢復時根據已持久的事實判斷，不由 final 文本反推副作用。

生命週期至少區分五種範圍（**概念，不等於五個類別／資料表**）：

```text
職務檔案：員工／JD／隔離的長期產品資料範圍
訪談會話：多回合原話與分析延續
一次顧問執行：模型與工具的多步迴圈，可完成、失敗或中斷
背景整理工作：已通知 ≠ 已持久接受 ≠ 已整理 ≠ 已正式發布
Memory publication／JD effect：已通過業務檢查的正式結果及其版本／收據
```

這種分層是為避免狀態混用的**本案候選表述**。例如一次 run 已失敗，JD effect 仍可能已提交；背景工具已回「接受」，尚未代表新 Memory 已發布。不能從框架的 session idle 或 checkpoint 存在推論任何一項業務完成。

## 歷史實現路徑比較（不再是本案待選框架）

下表保留先前研究時的比較脈絡。Owner 後續已指定 **LangGraph** 為 Agent 執行框架；託管式 Agent 及自建 loop 只作外部做法／風險的參照，不能再當成下一輪需要 Owner 三選一的提案。若將來有可重現的 LangGraph 能力缺口，應先核對官方既有機制與薄接線，再另行提出具體替代案。

| 路徑 | 可能收益 | 對本案的風險／驗證門檻 |
|---|---|---|
| 託管式 Agent／Session 服務 | 由供應商承接較多 loop、session、compaction、觀測。 | 本地 PostgreSQL、OpenRouter 路由、原話主權、工具副作用、背景共同發布是否仍能忠實遵守；不能因功能表齊全就判定適用。 |
| App 保有產品權威，使用成熟框架處理 loop／checkpoint／context | 可重用執行能力，JD／Memory 真相仍由本案 Domain 管理；目前已定用 LangGraph。 | 必須核實重啟、工具 result、模型 request view、B1／B2 共同發布的實際行為，避免 checkpoint 與產品狀態各自成為 authority。 |
| 直接模型 API、自建執行迴圈 | 最大控制權，可能避開特定 adapter 限制。 | 必須自行負責工具迴圈、限額、取消、恢復、context 與 trace；只有目前框架出現可重現且難以薄接線修正的缺口，才值得比較其總代價。 |

不採「A、B1、B2 所以一定要自由 handoff／全套 multi-agent runtime」作預設；角色分工是產品需要，不等於 runtime 技術型態。也不把所有 Agent 共享同一長 session，或把 B1／B2 的候選推理誤當成已發布 Memory。

## 下一個有限研究／驗收 gate

先以現有程式和已保存證據對照三個場景，不先改 production：

1. A 連續兩回合訪談後條件式改 JD：核對下一次模型看到的有效資訊、正式 JD 收據與使用者畫面是否一致。
2. B2 在分析工作理解時指出具體案例錯誤：核對現行能否傳達錯誤與原話、由 B1 修正並處理其他候選、由 B2 重評受影響理解；候選不外露，兩層一致才正式發布。目標規則未施工處標 OPEN；不把 B2 當成案例涵蓋審核者。
3. JD effect 已提交但 final 失敗，或背景已持久接受後程序中斷：核對重啟後哪些結果可查、哪些仍待工作、是否避免重送已成功的有副作用操作。

以 trace、DB／正式版本結果、重啟後查回和必要的真使用者旅程分層驗收；模型自然語句不替代保存證據。若現有框架已能滿足，就寫「不新增元件」；若有反例，先指出失效層，再比較薄接線與替換。此研究不代表上述場景已通過，也不授權施工、付費模型或 provider 切換。
