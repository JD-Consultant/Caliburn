# Q019：只分析應用接線——執行額度、恢復與背景排程

> 2026-09-06 · **Owner 已同意修訂後接線／失敗處理，進入隔離開發；不是 production 切換或已完成的功能。**
> 先完成每次發言的額度／恢復與安全來源邊界，通過 Checkpoint A 再接 API／排程。發現重大設計缺口先討論。
> 已完成的七段保持不變：[第七切片結果](2026-09-06-analysis-only-agent-live-memory-results.md)。
> **同日失敗處理複核已獲同意：**已撤回「人工恢復最多一次」初值；6／8 額度須校準。依[跨廠商失敗處理核對](2026-09-06-analysis-only-agent-failure-recovery-review.md)及[隔離計畫](../plans/2026-09-06-analysis-only-agent-application-wiring.md)執行；不呼叫付費模型。

## 1. 本輪唯一決策與閱讀路由

**Q019-APP-01：是否採用「單一文件根流程＋每次發言的可恢復 Agent 子流程」，再接本機 API 與背景排程？**

目標是讓既有隔離能力成為可操作的分析應用：送訊息、等待回答、關頁再回來、中斷後恢復、背景整理 Memory。不是新增顧問、重新選 Memory 架構或做 JD 編輯。

- 範圍與三條路徑：[總覽](2026-09-06-analysis-only-agent-design.md)。
- 原生 reasoning／compaction、模型與 Context：[Runtime](2026-09-06-analysis-only-agent-runtime-design.md)。
- 五產物、B1／B2、C、來源與發布：[Memory](2026-09-06-analysis-only-agent-memory-design.md)。
- 本稿只持有應用接線差異；[施工計畫草案](../plans/2026-09-06-analysis-only-agent-application-wiring.md)依本稿分段。不得用草案自行越過設計 gate。

## 2. 核對結果：三個接線缺口，不是重開 Memory 設計

| 已核對事實 | 若直接接 UI 會發生什麼 | 本稿的處理 |
|---|---|---|
| 官方呼叫上限有 invocation 與 thread 兩種範圍；run counter 不持久化 | 重新 invoke 可能重置額度；把整份文件 thread 限成 6 次又會阻止長訪談 | 每次發言是一個可恢復子流程，沿用子流程的官方持久計數；文件歷史由根流程保留 |
| limit 的 `end` 模式會產生系統代填的 AI／Tool 訊息 | 不能把技術停止當成模型成功完成；也不能剪掉未配對工具訊息 | 明確記錄技術結束原因，UI 顯示未完成，保留工具配對 |
| 現行 B1 reader 要求來源以 provider `status=completed` 的 AI 回覆結尾 | 失敗後的新員工內容雖已保存，卻可能一直進不了抽取範圍 | 區分「該回合已結束」與「AI 回答成功」；失敗／取消回合的員工資料仍可抽取 |

前兩项依官方 [middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) 與隔離環境 `langchain==1.4.0` 原始碼核對：`model_call_limit.py` 的 state／before_model／after_model，以及 `tool_call_limit.py` 的 after_model。第三項來自 [sources.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/sources.py) 的 `extraction_windows`；這是未接應用生命週期前的限制，**不是已觀察到使用者原話被刪除**。

## 3. 三個選項與推薦

| 選項 | 好處 | 成本／限制 | 判斷 |
|---|---|---|---|
| 完整 Agent Server | 原生 runs、queue、double-texting 策略 | standalone 路線還涉及 Redis、server 部署與授權／金鑰設定，不能當成 OSS `create_agent` 的一個參數 | 保留；目前不為單一本機应用引入這套部署 |
| **OSS LangGraph＋官方 middleware／subgraph＋薄應用接線** | 維持已核准的本機單程序＋PG；重用現有持久能力 | 要寫文件 catalog、API、一次只跑一個前台工作的接線，以及排程條件 | **推薦**；自訂責任在 §7 明列 |
| 根 Agent 直接套 run_limit | 最少改動 | invocation 額度與跨恢復總額度不同；不足以直接宣稱同一輪不會越用越多 | 不作為完整解法 |

Agent Server 的 double-texting 並不在 OSS LangGraph 內；官方提供 reject／enqueue／interrupt／rollback。[官方分界](https://docs.langchain.com/langsmith/double-texting)

Standalone 文件列出 PostgreSQL、Redis 及相關金鑰／license／egress 前提。這是該部署路線的實際額外條件，**不是宣稱所有本機開發方式都需付費**。[部署前提](https://docs.langchain.com/langsmith/deploy-standalone-server)

這個選擇是本案的複雜度取捨，不是「OpenAI／Anthropic 公認最佳部署」。若未來需要多程序、多機、正式 queue／streaming service，重開此選項，不擴寫自製平台。

## 4. A：一份文件、一份完整訪談，每次發言有自己的執行範圍

```text
文件根流程（同一 thread，官方 Checkpointer）
  保存員工新訊息與本次 run identity
    ↓
  本次主顧問子流程（同一個模型，不是第二位 Agent）
    帶入完整 canonical items，由既有 request view 控制 Context
    原生 reasoning／compaction 延續
    官方模型／工具上限＋Memory read／C repair
    失敗時保留子流程 checkpoint，恢復同一次工作
    ↓
  合回完整新增 items＋本次技術結果
    ↓
  UI 顯示回答或未完成原因；背景可發現新來源
```

### 4.1 官方能力與本案映射

官方 per-invocation subgraph 每次新呼叫有新的內部狀態，但同一次可繼承父 Checkpointer 恢復；父圖須配置 Checkpointer。將 `create_agent` 作為可見的子節點，可用公開 state API 檢查它。[官方 subgraph persistence](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#subgraph-persistence)

**本案映射：**讓 Agent 的 `thread_limit` 用於這次子流程，而不是整份文件的一生。根流程每次仍把 canonical 對話傳入；「子流程新狀態」不等於忘記前幾輪，也不把 reasoning 改成自製摘要。原生項目、工具配對和 C 的 Command 更新仍要完整保留。

執行中的新 AI／Tool items 暫在該子 checkpoint；根圖已有本次員工輸入。讀狀態不能只看根圖就誤報「AI沒有動作」。成功或安全關閉時，完整新增 items 以原 identity 合回根圖一次；正在恢復的子流程不可提前當成已完成來源。這是同一 Saver 的執行層次，不是另建一份可各自修改的訪談資料庫；代價是多一層 checkpoint I/O，不能說成本為零。

不要為了重置額度去改框架 private counter，也不自行重寫模型／工具 while loop。原有 6 model steps／8 tool calls 僅是待校準工程初值，不是已證明能完成正常深入讀取的產品上限。先驗證完整讀取、必要修正與最後回答的路徑；見[失敗複核 §5](2026-09-06-analysis-only-agent-failure-recovery-review.md)。恢復同一次子流程不暗中重新取得額度。

### 4.2 2026-09-06 極小官方契約檢查

僅在程序記憶體內建立 `MessagesState` 根圖＋`create_agent` 子節點＋`InMemorySaver`；使用本地假模型／假工具，**沒有網路、付費模型、檔案或資料庫寫入**。上限縮成 2 個 model steps，方便看結果。

| 情境 | 實際結果 |
|---|---|
| 第一次工具刻意丟錯 | 模型已呼叫 1 次；根圖已保存 human-1；子流程仍 pending |
| `invoke(None)` 恢復 | 模型累計 2 次即停止，不是再取得 2 次；完整訊息回到根圖 |
| 傳 human-2 | 模型累計增至 4；根圖同時保留 human-1／human-2 |
| 檢查上限結尾訊息 | 是人工 limit 訊息，沒有 provider completed status |

**只證明框架 scope／恢復形狀可行**，不代替與 MemorySession、C、原生 compaction、PG 和取消的整合測試。實作第一段須把這個檢查轉成正式回歸測試。

### 4.3 額度不是精確金額保證

官方 model counter 在模型回傳後累加；SDK transport retries、回覆遺失後重跑仍可能另外計費。因此「6 steps」不能寫成「最多 6 個 HTTP requests」或硬美元上限。

- 每 request 限輸出並保留輸入檢查；暫時模型傳輸錯誤優先由官方 SDK 重試，候選沿用 2 次預設。尊重 Retry-After 及整體時間界線；不再外套會疊乘的 model／整圖 retry。2 次不是跨廠商硬標準。
- 分開「SDK 重送」「模型收到工具錯誤後改參數」「恢復同一 checkpoint」。後兩者不能統一算成 transport retry；未修的配置／schema 問題不能原樣重送。
- 同一失敗工作的恢復不能自動無限排程。**撤回人工恢復最多一次的初值**；是否恢復依錯誤類型、真實執行／保存狀態及剩餘預算，不增設一套任意恢復配額。原工作 identity 與已用量在重啟後保持。
- 額度耗盡不能靠原額度原樣恢復解決；如實結束為未完成。是否明確增加額度另由配置／操作決定，不由重試暗中補額度，也不宣稱廠商一律禁止提高預算後延續。
- 記錄已取得的 provider usage；未知用量標 unknown，不填 0。真正付費驗收另設批次預算與停止條件，本稿不授權呼叫真模型。

依 [OpenAI retry 指引](https://developers.openai.com/api/docs/guides/rate-limits#retrying-with-exponential-backoff)、[Claude errors](https://platform.claude.com/docs/en/api/errors) 與[框架 fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) 分層使用既有能力。數值、parent／child 映射與 UI 入口是本案取捨，不冒稱共同底層。

## 5. 失敗、取消與來源：不能鎖死，也不能假装成功

| 情境 | 前台／執行處理 | 原文與 Memory |
|---|---|---|
| 正常完成 | 顯示顧問回答；解除忙碌 | 回合可交 B |
| 上限結束／不可重試配置錯誤 | 顯示本次未完成；不自動重跑 | 保留員工已送出文字；技術錯誤不提煉成員工工作事實 |
| 可恢復的中斷 | 顯示中斷原因與可用恢復入口；不顯示永遠分析中 | 繼續同一 checkpoint／同一 operation，不重送 HumanMessage |
| 員工選擇不恢復、改傳新訊息 | 先安全結束前工作，再啟動新工作 | 保留前一輪原話；不能因重新開始而刪除整個回合 |
| 要求停止 | 停止排下一個模型／工具；已開始的工作到安全邊界才結束 | 已發布 C 不回滾；未確定發布結果先對帳 |
| C 提交結果仍不明 | 如實顯示正在確認保存結果；不啟第二個寫入者 | 對帳原 operation；不可編一個失敗 ToolMessage 然後重寫 |
| 關頁／重開 | 關頁不取消後端；重開只讀目前狀態 | 不新建重複 run |

### 5.1 技術結果不是模型語意

新增最少的本輪技術 metadata：run identity、輸入 message identity、執行／結束原因、恢復次數、可定位 checkpoint。由系統填，**不進模型 structured-output schema，不建工作理解狀態機**。

先用框架已存在的 ToolNode／ToolErrorMiddleware 處理模型可修正的工具錯誤；真實配置錯誤、程式問題及未知發布結果不得一律轉成模型可重試。官方 `error_handler` 可做技術收尾，但不把仍待恢復的子流程直接吃掉當成功；此接法列第一段 gate。詳細來源與版本核對只存[失敗複核](2026-09-06-analysis-only-agent-failure-recovery-review.md)，不另複製長文。

官方 limit hooks 的 `end` 保留工具結果配對，但其人工 AI 結尾不能冒充 provider 成功。使用公開 middleware hook 對技術停止加上機器標示；不靠比對英文錯誤字串判斷、不改掉 provider status。[公開 middleware hooks 與順序](https://docs.langchain.com/oss/python/langchain/middleware/custom)

取消／失敗後若有未完成工具，必須先判定實際執行結果。只有確定未執行／已失敗才給對應 ToolMessage；已成功用真正回執，結果不明先查。不能把整段 raw items 刪掉來「修好格式」。精確關閉／恢復接法列為第一段整合 gate，未通過不接 UI。

### 5.2 B1 來源規則的窄幅調整提案

Memory 舊稿的「完成回合」在應用層需要拆清楚：

1. 模型回答成功：照既有完整問答抽取。
2. 工作已明確結束但回答失敗／取消：保留當時顧問問題、員工回答，以及真實已完成可見內容；明示沒有成功答覆，不補寫假回答。
3. 還在執行、仍可能恢復或 C 結果未明：來源不前推越過這一段；待安全結束後再處理。

員工資料不因 AI 失敗而失效。需由 runtime 的真實終止 metadata 決定可封閉範圍，**不能把所有缺 `completed` 的輸出都放行**，也不要求 LLM 判斷 checkpoint 是否已結束。原始資料仍只有 Checkpointer 一份權威，不建立 employee-source-events 文字副本。

這是依「完整訪談不遺失」需求補的本案來源契約，不宣稱 OpenAI 也用相同 enum。它不放寬 Memory 發布驗證、不把部分工具結果當成功、不讓 B 跨越未決來源游標。

## 6. B 排程與最小本機服務

推薦維持單一 API process＋專用 PG；以 FastAPI `lifespan` 管理 clients、worker 與 scheduler 的建立／關閉，不用已棄用的 startup/shutdown 事件混接。[FastAPI 官方生命週期](https://fastapi.tiangolo.com/advanced/events/)

排程選用 APScheduler 穩定 3.x 路線，施工前核對最新 patch 並鎖版。它負責喚醒、合併漏跑時點及限制工作實例；**不承擔 B1／B2 的 durable state**。後者維持 LangGraph，成功位置維持 publication cursor。[APScheduler 官方 user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)

- **2026-09-06 最新同意：**主顧問段落整理訊號＋新文字量後備為 WORKING 策略；[G4 通知／結果政策](2026-09-06-memory-consolidation-request-wiring-design.md)已准隔離施工，字數門檻未定。Task4a 先做通知、安全收尾與耐久來源投影，其餘 worker／結果 Context 仍待接線驗收。不用90秒、不以回合數為主，不沿舊 OR 初值施工；沒有 dirty 不呼叫模型。[策略依據](2026-09-06-memory-generation-cadence-and-continuity-review.md)不重開。
- 喚醒後檢查目前可處理來源；每份文件同時一個 B，全 App 一個 B worker。基礎設施的檢查 tick 不等於訪談 idle 觸發。員工手動整理是否開放待決；若日後開放也走同一 admission，不能繞過限制。
- APScheduler `max_instances=1` 是單 job 限制，不是所有 job 的全域限制；需配單一背景 executor／dispatcher。不因每份文件各設一次上限就宣稱全 App 只有一個 B。
- 排程表可在程序內重建；不另存第二份 B workflow／對話。啟動先查已存在的 B checkpoint／receipt，再判斷新來源。已抽取 B1 不重抽；已發布不再整併。
- 中斷只做有界恢復。配置錯誤、額度耗尽或重複失敗標成需處理，不讓每次 tick／每次重啟都再花一次模型費；記錄技術阻擋狀態而不是清空 dirty。
- A 與 B 用不同 worker，避免背景長工作卡住顧問；C／B 的寫入競爭仍由既有 publication 協調，不靠 scheduler 鎖。

文件 catalog／工作狀態只是應用 metadata；對話依舊讀根／子 checkpoint，Memory 依舊讀 Store＋publication。API 不應保存另一份對話正文。

同文件正在分析時拒絕第二次送出；UI 鎖輸入只是呈現，服務也需防重入。這是採用已知 reject 策略的本機接線，**不是聲稱 OSS 有 Agent Server 的原生 run queue**。單 process 約束須由啟動設定與測試固定；不宣稱程序內 mutex 可保護多程序。

## 7. 哪些直接用框架，哪些需要自己寫

| 能力 | 直接使用 | 本案接線／不能冒稱原生 |
|---|---|---|
| Agent loop／工具往返 | `create_agent` | 主顧問 instructions／Skill 內容 |
| 同輪恢復與消息持久化 | LangGraph root／subgraph＋官方 Saver | 一次員工輸入的邊界、結束狀態與 API 對應 |
| 模型／工具次數上限與錯誤 | 官方 limit／tool error middleware、SDK retry、graph fault tolerance | 選擇持久 scope、錯誤類型與預算；不疊重試、不冒充成功 |
| Memory 儲存／發布 | 已完成的 Store／backend／ORM publication | 不新增一套引擎 |
| 定時執行 | APScheduler | 何時 dirty、選哪段來源、B 失敗不無限重跑 |
| API 生命週期 | FastAPI lifespan | 文件／run endpoints、single-process admission、狀態投影 |
| UI | 之後用 React／Vite 的最小分析畫面 | 訊息、狀態、停止／恢復；手動整理入口待決，不是 JD 編輯器 |

自訂部分均為已核准產品需求的 mapping，不宣稱其名稱／資料欄位是大廠共識。若第一段需要 private framework API、自製 agent loop 或第二份原話權威，停止並回報，不靜默加補丁。

## 8. 退出條件與下一段

原接線三段如下；Owner 在 Checkpoint A／詳記切片完成後，確認後續路線另加「真模型測試後的 Prompt 優化」，見[四步後續路線](../plans/2026-09-06-analysis-only-agent-application-wiring.md#owner-確認的四步後續路線2026-09-06)。它不是重新設計 Memory，也不把計畫 Task 編號改成產品路線編號：

1. **第八段 A：執行與來源生命週期。**官方額度跨恢復、canonical／reasoning 完整、C receipt 恢復、失敗原話仍能供 B1。先離線假模型＋專用 PG。
2. **第八段 B：API＋背景排程。**單文件 admission、關頁／重啟、有界 B 恢復、無新內容零模型呼叫。
3. **第九段：只分析 UI＋小額真實模型驗收。**先瀏覽器測前兩段；再依獨立預算配置測 luna／medium，不使用 Opus。沒有真模型效果證據前不宣稱分析品質已達標。
4. **接續 Prompt 優化：**依真實訪談結果改善顧問及 Memory 的抽取／整併／修補／回查指引，特別檢查資訊留存與去重、更正、案例細節及導覽的效果；記錄版本、來源、前後結果與成本。沿既有範圍小步改善，不先加資料層或大型 eval；完整規則只由上方連結的路線持有。

**本輪狀態：**研究與設計草案已經失敗處理複核，仍待 Owner 審核；§4.2 是先前程序內行為檢查，同日新增原始 SDK exception 的離線 retry predicate 檢查，非整合測試。未改隔離程式、未新增依賴、未跑新的 PG 回歸、未呼叫付費模型、未 merge／push。前七段 120 passed 是前段保存點，不冒充本段驗收。

本輪審核重點只有修訂後接線方案：維持既有分析／Memory目標，先按類型處理失敗、校準額度，核准後證明恢復與來源收尾，再接 API／排程。不重開整套 Memory 研究。
