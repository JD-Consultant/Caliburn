# Q019 只分析應用接線：第八段隔離施工計畫

> **2026-09-06 Owner 同意修訂後接線與失敗處理；准隔離施工。先完成 Task 1–2／Checkpoint A，再接 API。不是 production 切換授權。**
> For agentic workers: REQUIRED SUB-SKILL: use superpowers:executing-plans or superpowers:subagent-driven-development after approval. 每段用 TDD、核对 spec 与獨立 review；不以本計畫補產品政策。

**Goal:** 接成可恢復、有界、不遺失員工輸入的只分析服務，之後才接 UI。

**Architecture:** 文件根 graph 保存完整訪談；每次發言進可恢復 Agent 子圖，官方 limits 使用該次持久 scope。Memory 五產物／B1／B2／C不重新設計。FastAPI＋APScheduler 只處理應用入口與喚醒，持久進度仍用官方 Saver／Store 及既有 publication。

**Tech Stack:** 隔離 package 現有 LC/LG/Deep Agents/OpenAI/SQLAlchemy/PG；接線段新增 FastAPI、ASGI server、APScheduler 穩定版。安裝前查官方穩定版／Python 3.12 相容性並鎖版，不盲升既有已驗證 provider adapter。

**Spec:** [`application-wiring-design.md`](../specs/2026-09-06-analysis-only-agent-application-wiring-design.md)；依其閱讀路由看總覽、Runtime、Memory。以 main 最新稿為準，不讀 worktree 歷史 register 猜目前需求。

**失敗處理前置：**必讀[跨廠商失敗處理核對](../specs/2026-09-06-analysis-only-agent-failure-recovery-review.md)。撤回「人工恢復最多一次」初值；不把 SDK retry、模型修參數、checkpoint resume 混成一套。Owner 同意後啟動隔離段；若公開框架接法出現重大缺口，先回報討論，不自行越過停止線。

## Owner 確認的四步後續路線（2026-09-06）

這是完成 Checkpoint A 與詳記重抽後的產品路線，不重編下方 Task 1–5：

1. 最小 API、單文件送出／恢復／安全停止（本計畫 Task3）。
2. 背景整理的自動喚醒及重啟恢復（Task4，Task5 保存並交接）；依後續裁示，員工手動整理入口改為待討論，非必做。
3. 最小聊天室與小額真實多輪訪談：Luna／medium，記錄回答、實際 Memory 產物、回查結果、token／費用／延遲；先配置明確批次預算，不由本段零付費預算自動放行。
4. **依第三步結果修改、比較及優化 Prompt**，包括主顧問、訪談詳記／候選抽取、工作理解／導覽整併、即時修補與按需回查。檢查哪些資訊應保留、在哪層保留、如何補充／更正／去重與保留未解矛盾；案例共同模式不機械複製，案例特殊細節不能因精簡失去回查線索。用相同代表性訪談比較修改前後的產物、問題及成本，記錄 Prompt 版本、實際差異、理由、官方／既有研究引用與結果；不只憑文字變短或一次輸出好看就判定改善。先維持可用基線，第四步是集中迭代，不代表前三步可以沒有基本 instructions。

第四步不預定額外資料結構、不啟動大型 eval，也不授權立即改 Prompt 或付費測試；改變既有產品效果／資料分工時先討論。依據為本輪 Owner 新要求，分析內容邊界沿用 [Runtime §5](../specs/2026-09-06-analysis-only-agent-runtime-design.md#5-給模型什麼哪些不是模型填的)、[Memory 五產物與抽取／整併](../specs/2026-09-06-analysis-only-agent-memory-design.md)，以及[詳記更正切片結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-06-summary-reextraction-results.md)；具體 Prompt 文字在相應階段研究與驗證，不重做已收斂的 Memory 架構選型。

**觸發狀態核對：**原生 compaction 已有模型參數／request view，`build_model` 的 `compact_threshold` 目前預設 `None`，尚無應用層正式啟用值；測試的32,000僅為參數傳遞用例。接服務時須依所選模型、完整 request／輸出餘裕配置，不能宣稱已有自動壓縮門檻。背景舊4回合／6,000字／idle90秒 OR 規則已退出施工預設；「主顧問段落訊號＋新文字量後備」與通知／結果政策已准隔離施工，通知先走 Task4a，字數門檻未定，其餘排程／worker 待Task4。兩者獨立；B1讀原始問答而非compaction內容。詳見[Runtime §4.2](../specs/2026-09-06-analysis-only-agent-runtime-design.md#42-採原生-compaction非通用文字-summarizer)、[Memory §2.1](../specs/2026-09-06-analysis-only-agent-memory-design.md#21-觸發提案不是-openai-anthropic-共同固定數值)。

## Global Constraints

- 只用 `S:/caliburn/.worktrees/analysis-only-agent` 的 `codex/analysis-only-agent`；base `bd6e4751`／`q019-live-memory-v1`。施工前重新驗證 branch／dirty，保留 owner 變更。
- 所有下列程式檔名相對 `experiments/analysis-agent/`；不 import current API/Web、不改 production、不搬資料、不 merge／push。
- 專用 PG `127.0.0.1:55433/q019_agent_test`；驗 label，只建立／清理測試自己的文件資料。禁止讀出密碼或使用正式 `.env` 做此段測試。
- 原生 reasoning／compaction items 不解碼不改寫；request view 與 canonical storage 分開。
- 模型不填 UUID、版本、時間、回執、成本、Skill ID；不新增 JD 編輯／審核／匯出。
- 技術錯誤不當員工工作事实；員工原話不因 AI 失敗丟失。對話權威仍只有 Checkpointer。
- A 經Task1正常深讀＋修正＋最終回答路徑校準，factory初值為可配置9 model calls／8 tool calls（原6次候選已被實測更新，見Task1結果）；恢復不得暗中重置scope。模型transport優先官方SDK、沿用2次重試預設，不疊model／整圖retry；不設人工恢復一次的任意硬限制。時間、輸出與總工作預算分開，呼叫次數不當金額上限。
- B 觸發依 Q019-MEM-CADENCE-01 後續決策；不用舊4回合／6,000字／idle90秒 OR 初值施工。全 App 背景並行 1 不變，不叫大廠標準。
- **本段付費模型呼叫上限：0。**前七段 120 tests 為 regression baseline，不是新段通過證據。

## Task 1：先證明每次發言的持久額度與原生延續

**Files**

- Create: `src/analysis_agent/conversation.py`
- Modify: `src/analysis_agent/runtime.py`, `src/analysis_agent/live_memory.py`
- Narrow source projection integration when required: `src/analysis_agent/sources.py` (exclude marked runtime notices from C's question/answer view; Task 2 source closing remains separate).
- Create: `tests/test_conversation_lifecycle.py`, `tests/test_postgres_conversation_lifecycle.py`
- Reuse: `tests/test_native_continuity.py`, `tests/test_live_memory.py`, 專用 PG fixture。

**Interfaces:** conversation factory 產生與 `ConversationReader` 相容的根 graph；root `messages` 是完整 canonical history。Agent 是可由公開 `get_state(..., subgraphs=True)` 檢查的直接子節點；本輪 outcome 是 runtime metadata，不是模型 structured output。名稱／精確欄位在測試中以最小需求定義，不新增平行對話 store。

- [x] 先加入失敗測試：第一個工具中斷、同 run 恢復沿用額度、新 HumanMessage 得到新額度但保留歷史。
- [x] 校準正常 Memory 搜尋／逐層深讀／C 修補＋一次必要修正＋最終回答，不把可預期正常路徑擋成 runaway；先離線，不擅自增加真模型預算。
- [x] HTTP 假 transport 分別測暫時錯誤後成功、400 schema／401不盲重試、Retry-After、streaming／incomplete；計實際 attempts，驗沒有 SDK＋middleware＋整圖重試疊乘。
- [x] 已知可修正工具錯誤由 ToolNode／官方 ToolErrorMiddleware 回饋；只把安全可操作資訊交模型。未知配置錯誤／publication uncertain 向外保留，不用 catch-all 掩蓋；必要收尾優先公開 error_handler。
- [x] 加入原生 reasoning／compaction／工具結果在 root↔child 完整往返測試；不得只合回最後一句可見文字。
- [x] 以官方 per-invocation subgraph 與 limit middleware 實作；不寫私有 counter reset 或另寫 Agent while loop。
- [x] 檢查 middleware 的 after hooks 逆序，確保 provider 完成驗證看的是原生模型結果；limit 人工訊息另標技術結果。
- [x] 測 exact limit end／tool pair、未使用額度、失敗模型用量 unknown；不以 completed-call counter 聲稱精確費用。
- [x] C 仍取得真實根圖本輪來源，成功／stale 的 head＋ToolMessage＋reader 切版仍成對。
- [x] 重建 PG clients 後恢復 pending C／A，驗同 operation 不重做；前七段 regression 全跑。

**Stop gate:** 公開 API 無法維持 native items、子圖恢復或來源 locator 時停止此方案，回到 spec 比較，不用 private API 硬接。此段未綠，不往 Task 2–5 堆功能。

## Task 2：安全結束與可抽取來源

**Files**

- Modify: `src/analysis_agent/conversation.py`, `src/analysis_agent/sources.py`
- Owner同意T2-B01局部接線：`src/analysis_agent/live_memory.py`／`repair.py`，必要時窄幅`publication.py`，以及其對應測試；不重設Memory分析／五產物。B1 consumer若需讀來源terminal metadata，可窄幅調整`extraction.py`。
- Modify: `tests/test_conversation_lifecycle.py`, `tests/test_postgres_conversation_lifecycle.py`, `tests/test_extraction.py`

**Interfaces:** runtime 封閉回合範圍／outcome；reader 讀該真實邊界，不以模型自行聲稱已完成作依據。既有 `read(reference, offset)` 及 B1 windows 保留有界、role-aware、可續讀契約。

- [x] 先測 AI 成功、limit、配置失敗、已確認取消四種 terminal 回合；員工文字及之前顧問問題皆可回讀。
- [x] 未決／可恢復回合及 publication uncertain 不前推 B cursor；不是把所有缺 completed status 的訊息直接放行。
- [x] 加入取消前未執行工具／已成功 C／提交結果不明案例；只有已知結果才能補 ToolMessage，不偽造失敗。
- [x] 員工選擇放棄恢復而傳新訊息時，先安全封閉舊回合；不刪原話、不重新接收同 HumanMessage。
- [x] 運用公開 state／middleware APIs 完成關閉；對 provider metadata、raw items 和已發布 Memory 均不偽造／回滾。
- [x] B1 可處理安全封閉的失敗回合，清楚標示沒有成功回覆；不抽技術錯誤作員工工作、不靜默跳過其中段。
- [x] 全部 PG lifecycle＋來源／B1 regression；記錄新增來源邊界與實際恢復路徑。

**Checkpoint A:** 回看 spec §§4–5 與前七段能力矩陣，做獨立 review。只有無重要阻塞才建立本地 commit／tag，再開應用服務；回報遇到的真實取捨。

## Task 3：最小 API、run admission 與重開

**Files**

- Create: `src/analysis_agent/service.py`, `src/analysis_agent/catalog.py`, `src/analysis_agent/api.py`
- Create: `tests/test_service.py`, `tests/test_api.py`, `tests/test_postgres_service.py`
- Modify: `pyproject.toml`, `uv.lock`, `README.md`

**Interfaces:** 文件建立／列表、提交訊息、讀取訊息／run 狀態、請求停止、恢復同一 run。具體 endpoints 用 FastAPI/Pydantic 產生 OpenAPI；不接舊 contract package。catalog 只記 document／run routing、outcome、恢復次數，不存第二份訊息正文。

- [x] 先測雙擊送出／重複 HTTP 請求／同文件第二個 active run；同請求取回既有 run，不生成兩個 HumanMessage。
- [x] 設計並測 crash windows：輸入 checkpoint 成功但 API 回覆遺失、catalog 狀態與 checkpoint 暫不同步；以 runtime identity 對帳，不猜成功／失敗。
- [x] FastAPI lifespan 啟閉所有 clients／workers；同步 graph 不阻塞 API event loop。固定單 process 啟動，不宣稱支援多 worker。
- [x] API回覆 accepted 前確認輸入已耐久保存；關頁不取消 worker，重開只查同 run。未被接收文字不截斷；前端草稿保存屬後續UI驗收，這裡不宣稱已做UI。
- [x] 客戶端只讀 projection，不能更改 checkpoint config／Memory scope；本機綁 loopback，不開任意 origins。
- [x] success／terminal failure 解 busy；startup running→實際 checkpoint 對帳後顯示 interrupted／completed，不自行重啟無限付費工作。
- [x] 停止採協作式安全停止；取消同步 task 不等於殺掉 worker thread。provider timeout 與 thread/client 安全性需測，不用 Future.cancel 冒充已停止。
- [x] A 恢復記錄耐久保存，依原因／保存結果／剩餘預算判斷入口，不以一次恢復硬限制代替錯誤分類；耗尽／未修配置不提供假恢復。記錄 usage unknown，不暴露 secrets／opaque reasoning。

**Task3驗收（2026-09-06）：**[本段結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-06-analysis-only-agent-api-results.md)記錄最終276 passed／0 skipped含PG、compileall／offline lock通過、獨立T3-R01–R07全CLOSED。僅API接線，不把Task4通知等同真正B已跑。下一段先按原Task4接背景worker／恢復／結果Context；字數後備值仍未定，不補舊90秒／6000字。模型付費0。

## Task 4：背景喚醒與重啟重排

> **最新核准（2026-09-06）：**[Q019-MEM-CADENCE-01](../specs/2026-09-06-memory-generation-cadence-and-continuity-review.md)策略及[G4 通知／結果政策](../specs/2026-09-06-memory-consolidation-request-wiring-design.md)均獲 Owner 同意，准隔離施工。先以[Task4a 計畫](../../.worktrees/analysis-only-agent/docs/plans/2026-09-06-memory-consolidation-notification-slice.md)交付純通知、耐久來源投影及安全收尾；它無 API 依賴，先於 Task3 交付不代表其餘 Task4 已完成。後續服務接線須測真正 B worker 不阻塞 A、成功不喚醒主模型、未恢復失敗只在下次正常 run 帶入當前 Context、恢复後不殘留舊錯誤。字數門檻仍未定。不用90秒、不以回合數為主要判準、不依賴手動整理，不自行新增短句過濾、topic table 或額外判斷 LLM。Task3 授權不變。

**Files**

- Create: `src/analysis_agent/scheduling.py`, `tests/test_scheduling.py`, `tests/test_postgres_scheduling.py`
- Modify: `src/analysis_agent/service.py`, `src/analysis_agent/api.py`, `README.md`
- Reuse: `extraction.py`, `consolidation.py`, `publication.py`，非必要不改內部工作流程。

**Interfaces:** scheduler 只觸發 dispatcher；由來源安全邊界＋publication cursor＋現有 B1/B2 checkpoint 判斷 resume／start／no-op。員工手動入口待決；測試可直接使用 dispatcher，不需產品按鈕。

- [x] 先依核准後的觸發策略做假模型／可控輸入測試；不測成舊4回合／90秒即自動整併。無新內容零模型呼叫，重要短句不丟棄；不使用真睡眠／真 API。
- [x] 單 B executor／dispatcher，`coalesce`／`max_instances` 各在正確層；多文件排隊，任何入口不能突破。
- [x] 先恢復舊 B job 再收新來源；B1 已保存不重抽、B2 已發布不再模型整併。
- [x] B 失敗有耐久 blocked/retry metadata，tick 或 restart 不無限重跑；dirty/source 不被清空。
- [x] 長來源分批但不截中段；不越過未決 A 回合，不讓其他文件被一個失敗 job 永久卡住。
- [x] A/C 與 B 可並行，已完成 publication 的 CAS／receipt 測試仍過；scheduler 不能取代它。
- [x] 程序重建測試：尚未開始、B1 已存、B2 pending、publish 回覆遺失；只有真正無需工作才 no-op。

**Checkpoint B:** 專用 PG 全回歸、API smoke、獨立 review；逐項回看 scope／框架責任／自訂接點，新增重要需求先討論。

**Task4驗收（2026-09-06）：**[背景結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-06-background-dispatch-results.md)記錄最終298 passed／0 skipped（56.50s）含PG、compileall／offline lock／staged diff通過。独立T4-R01／P2修復與限定複核CLOSED：B2必須沿部署輸出預算，不被standalone預設覆蓋。APScheduler3.11.3只喚醒，技術admission由小型ORM列保存，實際B進度仍由原Saver／publication持有。字數後備可選、不補預設；wake間隔／程序意外中斷恢復額度要求明訂，不將測試數字當產品最佳值。付費0、未重啟Docker。保存 `f246f43c`／`q019-background-dispatch-v1`，worktree乾淨、未merge/push。

## Task 5：紀錄、保存與 UI handoff

- [x] `README.md` 寫明啟動、單 process、專用 DB、錯誤／重試／停止／背景狀態及能力限制；相關隔離 seam 同 commit 更新。
- [x] 結果另存 `docs/specs/2026-09-06-analysis-only-agent-application-wiring-results.md`，包含實際版本、完整命令結果、未通過項目、付費呼叫 0、來源。該頁以短路由連到各段完整結果，不重複膨脹成長文。
- [x] 依 `docs/current-decisions.md` 更新最新 stage／next gate，不改歷史測試結果，不把草案打勾當驗收。
- [x] `pytest -q -rs --tb=short`、compileall、lock check、diff check；提交前重新核對變更範圍。
- [x] 各 task／完成段保存獨立本地 commit，收尾本地 tag；不 stage main 的其他研究與 owner 變更。
- [ ] API 完整後才寫第九段 UI 與真模型計畫。最小 UI：文件列表／單聊天室、明確狀態、停止／恢復、可選唯讀 Memory；員工手動整理待決，不先加按鈕。不做 JD、dashboard 或大型 eval。

## 目前執行狀態與不可假定

- **最新：**Task4／Checkpoint B已通過上述隔離驗收並本地保存；Task5文檔、驗證與保存完成，唯第九段UI／真模型計畫仍未寫。下一步先完成此計畫，不自行付費測試。下方Task1–2的「Task3未開工」只保留歷史停止點，不作現在指令。

- Task1已保存本地`3118e8a1`；Task2已保存`e1a3cbf0`／tag`q019-safe-turn-closure-v1`，**Checkpoint A通過後先停止回報**。最終209 passed／0 skipped含PG，compileall／offline lock／staged diff check通過，獨立R01複核關閉；隔離worktree乾淨。來源／C對帳／安全收尾的缺口、修復、測試及限制見[Task2結果](../specs/2026-09-06-analysis-only-agent-safe-turn-closure-results.md)，不重複全套Memory研究。Task3–5未開工，不接API／排程／UI；Docker保持運行，自動重啟仍是另列host問題。
- 七段現有測試不代表新 parent／child 接線、取消、API 或排程已驗證。
- API source window 的真正終止與取消收尾需在 Task 1–2 回歸中核實；失敗就停，不帶著未決語意繼續做 UI。
- 真模型／Skill 內容品質、長訪談效果與批次預算在下一段；不得因工具測試通過就宣稱顧問分析完美。
