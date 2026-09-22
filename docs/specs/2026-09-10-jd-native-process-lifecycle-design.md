# JD 原生程序生命週期：Task 3／5 有限接線設計

日期／查閱日：2026-09-10。Topic：JD-R002/C03，ER03。狀態：**有限 G4 PASS，主工作單位採用 B 作隔離 Task 5 依據**；[獨立審查](evidence/2026-09-10-jd-native-lifecycle-review.md) NL-R01／NL-R02 CLOSED。不是新 production authority、付費模型授權或實作驗收；Windows／PG 故障證據留 Task 5。相應正式採用範圍記於 Proposed ADR0074，尚未切換 production。

## 1. Preflight 與結論

- Current stage：隔離核心 Task 2 已接受，Task 3 三工具接線施工中；完整 lifecycle 屬 Task 5。本次依有限 review 的 NL-R01／NL-R02 修稿，不阻塞 Task 3。
- Binding decisions：持續工作稿、同 PG 的唯一 JD head／revision／terminal receipt；checkpointed binding；ER03 一次 attempt、零自動重播；必須 writer quiescent＋全部已發配 operation 閉合＋turn closure 才解人工 gate；Memory authority 不變。
- 本輪唯一問題：工具已返回但 Node 未 reap 時，既有 service 如何保留停止證據，並避免 close／restart 把「沒有 Future／沒有 receipt」誤當已停止？
- 已讀：[current register](../current-decisions.md)、[decision process](../decision-process.md)、[核心 Task 3／5](../plans/2026-09-10-jd-editor-core-implementation.md)、[ER03](evidence/2026-09-10-jd-error-recovery-contract-closure.md#4-er03執行停止及逾時由-app-負責)、隔離 scratch `task-2-review.md` 的 quiescence handoff；Task 3.4 與既有 `MemorySession.after_model/reconcile` 為 binding 基線。[通知設計](2026-09-10-jd-model-view-change-notice-design.md)只增 manifest 的 child→root 傳遞，不提供原生程序證據。
- 不做：通用 job／replay／sync engine、Memory 重做、模型新欄位、DB running 表、全面 framework 升級。

**採用：Task 5 採每文件有限 Popen owner，加上 API 啟動前的 App 專用 Windows Job Object／單程序互斥。**前者負責同程序清理，後者以整組程序退出證據覆蓋 API crash 後無法重建的 Popen，包含沒有 AI binding 的 read／manual／create。再按同文件 DB lock、原 receipt 與 checkpoint 關閉操作和 turn。這是已採用於隔離施工的有限工程設計，沒有把 Windows API 成功呼叫當成故障驗收。一般 API 在 transform 中或 publish 前 crash 都可能沒有 receipt；A 的保守維運方案不足以交付一般恢復旅程，不能稱為僅極端 unreap。

這不表示 Node 可在背景自行提交。固定 Node 只讀 stdin、計算候選、寫 stdout，沒有 DB／模型設定，也沒有呼叫 Python 的 IPC；真正 JD DB writer 是 Python `JdStore.publish`。停止 Node 的義務包含 ER03 的資源清理與不早解 gate，不能藉「Node 無 DB」刪掉該義務；同時不能把 Node 尚活著誤寫成「還可能自行 COMMIT」。

## 2. 已核對的 code 事實

以下 `A` 為 `S:/caliburn/.worktrees/analysis-only-agent/experiments/analysis-agent`，`J` 為同 checkout 的 `experiments/jd-editor`；只讀當下工作樹，沒有把尚未施工的接點當成事實。

| 位置 | 目前事實與缺口 |
|---|---|
| `A/src/analysis_agent/service.py` `CooperativeStop` | 在 before／after model、model entry 與 tool entry 檢查同一 Event；已进入 handler 後不會自動中斷 Node／SQL。entry 未執行的 ToolMessage 只能證明該次 handler 未開始。 |
| 同檔 `_execute`、`join`、`close`、`_reconcile(startup=True)` | `_execute` 同步 graph unwind 後多處直接傳 `quiescent=True`；`join` 只等外層 Future；executor shutdown 只等 Python 工作。startup 的空 futures 沒有跨程序停止證明。這些 boolean 接點在 Task 5 必須補核。 |
| `A/src/analysis_agent/conversation.py` `close_turn` | 不會取消 thread；呼叫者須先停止並序列化文件。以公開 get_state／update_state 先 child 後 root；只補缺失 call，未知 write fail closed。JD 不可借既有 Memory read 例外跳過對帳。 |
| `A/src/analysis_agent/jd_engine.py` `_call`／`_reap` | Popen 與三個 daemon I/O threads 是 local；timeout／cancel 後 terminate→wait→kill→wait。未 reap 僅傳 `JdEngineFailure(quiescent=False)`。`BaseException` 分支丟掉 `_reap` 回值；正常退出後 I/O thread 未 join 完的錯誤預設 quiescent=True。這兩路也須交給同一 owner，不能只修一般 timeout。 |
| `A/src/analysis_agent/jd_service.py` `_write` | receipt-first；Node 在 DB transaction 外；未 reap 時回 unchanged／unconfirmed／reconcile，不發布候選。`edit/manual_save` 尚未傳 Event；selection 也尚無 cancel port。 |
| `A/src/analysis_agent/jd_types.py` `JdWriteOutcome` | 是效果／回執資料，無 lifecycle 證據；不宜把一次性 quiescent 布林塞進 durable receipt。 |
| `A/src/analysis_agent/jd_store.py` `publish` | Python 持 head lock，revision／receipt／head 同交易；COMMIT 送出後例外屬不明。terminal failure 另做有限閉合，不重跑 Node。receipt 無 row 不能证明原 transaction 未提交／未完成。 |
| `J/native/src/bridge.ts`、Python 的 env allowlist | 固定三入口、stdin request／stdout result；沒有 DB／模型接線。環境過濾是本固定程式的能力界線，不宣稱 OS sandbox。 |

## 3. 官方事實與適用版本

隔離 `pyproject.toml` 固定 Python `>=3.12,<3.13`、LangChain 1.4.0、LangGraph 1.2.11；已讀安裝套件目錄為 langchain-core 1.6.2、langgraph-prebuilt 1.1.0。沒有安裝／升級。以下是官方契約，§4 以後才是 Caliburn mapping。

| 來源（均 2026-09-10 查閱） | Official fact／不能推出的主張 |
|---|---|
| [Python 3.12.14 subprocess](https://docs.python.org/3.12/library/subprocess.html#subprocess.Popen.wait) | wait／poll 可確認子程序終止；communicate timeout 不自動殺程序，PIPE 需處理讀取以免死鎖。Windows terminate 使用 TerminateProcess，kill 是其別名；啟動未必能即時中斷。呼叫停止不等於已退出，30／5／5 秒是本案控制預算。 |
| [Python 3.12.14 concurrent.futures](https://docs.python.org/3.12/library/concurrent.futures.html#concurrent.futures.Future.cancel) | 已執行的 Future 無法由 cancel 取消；done 只涵蓋該 callable 完成／取消。沒有替任意外部 process 提供回收證明。 |
| [LangGraph ToolNode 原碼，1.2.11 repo tag](https://github.com/langchain-ai/langgraph/blob/1.2.11/libs/prebuilt/langgraph/prebuilt/tool_node.py)；另核已安裝 prebuilt 1.1.0 `tool_node.py:793–824,1020–1055` | 同步 ToolNode 在 executor context 中 map 工具，wrapper 收 request／handler。框架等工具 callable 的結果，沒有追蹤工具自行啟動的 Popen。不能由 ToolMessage 或 ToolNode 結束推論 Node 已終止。 |
| LangChain 1.4.0 已安裝官方原碼 `langchain/agents/factory.py` 的 middleware wrapper composition／after_model 節點；LangGraph 1.2.11 `langgraph/pregel/main.py` `invoke` durability 與 `update_state` | 公開 middleware 可在 ToolNode 前產生 state；sync durability 在下一 step 前保存。這是先存 binding 的接點，並非把 checkpoint 與 JD SQL 包成同一交易。遠端固定 LC tag 頁讀取失敗，主張以已安裝官方原碼核對，不冒稱遠端取碼成功。 |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)，滾動文件 | Checkpointer 保存 thread graph state；不保存作業系統 process handle。本文不採其一般 Store 建議改寫本案 Memory 或 JD authority。 |
| [Microsoft Process Handles and Identifiers](https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers)，現行 Win32 文件 | process ID 有生命週期；持有對象 handle 與只記數字 PID 是不同能力。PID／同名 executable 不能當跨重啟的可靠 owner identity。 |
| [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject)，現行 Win32；nested job 自 Windows 8 | Job 可管理程序群、設定最後 handle 關閉時終止程序；需建立並確實指派，不能替未加入的程序提供保證。一般 completion-port 訊息不保證送達。這不等於 Popen 已有安全的跨重啟 supervisor，也不能把送出 termination 當完成等待。 |

只核對會改變 owner 選擇的公開接點。既有 code／官方契約已足以識別缺口，不開新 spike；實際取消、process 故障與 restart 效果由 §8 有界測試驗證。

## 4. 最小 owner 與內部 port

### 4.1 四種資料各有一個責任

1. **文件 runtime／admission owner**：沿 `DocumentRuntime`／`AnalysisService`，持 stop Event、外層 Future 及有限 `JdNativeCalls` owner。所有該文件的原生呼叫（AI edit、manual validate、selection）在開始前登記；讀取不配置 write operation，但仍有 ephemeral call token 供 cleanup。另文件不受影響。
2. **原生 adapter owner**：`jd_engine.py` 的有限 helper 持當前 call 的實際 Popen、三個 I/O thread／pipe、spawn-in-progress、cleanup 結果。token 只在本程序內使用，不是模型 ref／DB ID；不序列化 Popen。登記先於 spawn；spawn 返回立即交 handle；在此期間的 stop 仍可見。只在 process exit 已確認、I/O workers 全部結束並釋放 pipe 後移除 entry。spawn 返回前卡住仍有 outstanding entry，不能因尚無 handle 就當沒開始。
3. **checkpointed binding owner**：沿 Task 3 `JdToolSession` 保存 saved input→AI message→tool call→operation／digest／exact request／base；既有 after_model 返回 state 的 saved node 在 Node 前持久化。`Command`／ToolMessage 更新結果；不從 wrapper handler 返回的最後一刻才保存「已發配」。這不是 native handle store。
4. **JD 保存 owner**：`JdStore` 獨占文件效果及 terminal receipt；原生候選已完整驗證、native cleanup confirmed、取消 gate 再查一次後，才可进入普通發布。取消與 commit 競速若已进入 SQL，仍依真實 commit／abort 結果收尾，不能承諾 stop 必然零寫入。

Task 5 新增 `jd_engine.py` 內有限 `JdNativeCalls`／call record，配 §6 的 App 啟動 helper；不另起 scheduler、daemon manager 或通用 registry 服務。文件 owner 被 `DocumentRuntime` 引用，create 則使用 App create-entry owner，JdService 方法以 keyword-only `cancel`、`native_calls` 接收。Task 3 只先接實際 cancel、binding 和可接受 owner 的 port，不注入空 stub、不聲稱已追蹤 Popen；Task 5 完成後 production composition 才要求缺 owner fail closed。

`JdWriteOutcome`／wire schema 保持效果 DTO，不加模型欄位。必要的 `pending_native_cleanup` 是 App owner 診斷狀態，不保存成 terminal receipt；wire 仍用既有 unconfirmed/reconcile，UI 用 run uncertain 狀態呈現。`quiescent=False` 不靠 exception 存活才成立：所有 exception（含 BaseException、I/O thread 未退出）都留下 outstanding owner entry，因此 read 的 typed failure 也不會掩蓋清理義務。

### 4.2 不從 observer 執行 cleanup

2026-09-10已採[人工恢復HTTP接點](2026-09-10-jd-manual-recovery-transport-design.md)：GET只投影原key／真receipt及完整admission gate；POST以原key明示一次，active attempt不可重入。server從既有descriptor取digest，terminal後仍可同key查原結果；不新增身份token／candidate重播。所有分支的write_blocked/can_recover來自同一owner，結果可讀不等於全文件可寫；exact cache/no_pending保留原完整提交的明示出口。§6.4–6.5停止／PG proof不變，§7 Task5加actual DTO export、generated Web/API wrapper及MT01–14有限驗收。

普通 run GET／投影可看 owner snapshot，不能偷偷 terminate、replay 或輪詢 DB。原 attempt 有 ER03 一組 cleanup 預算；後來員工顯式 stop／恢復可對**同一 handle**再做一次有界清理與一次結果 lookup，這是資源清理／對帳，不是重跑 Node。任何未證明狀態仍停在 uncertain，下一次動作必須另有明示觸發。

清理等待不得持全域 admission lock；先設 stopping／保留文件 gate，lock 外等待 Future／handle，再 lock 內重核同一文件 generation、沒有新 admission、全部 owner entries 與 binding；避免舊 close 解鎖新 run。禁止因 Python Future.done、receipt 存在或某一 Node 已退出就略過其他 outstanding entry。

## 5. 正常與異常接法

正常：admission→saved binding（AI）／既有人工 request identity→register native call→一次 Node→exit＋I/O 收尾→核取消→一次 publish→真 receipt→原 call ToolMessage→完成 turn。新發布不變量是 **任何該 operation 的 terminal receipt 均只能在該 operation 的 native 工作已停止後产生**；failure receipt 同樣適用。不得先寫 terminal 再异步清 Node。

取消／timeout：Event 傳進 engine；候選丟棄→一次清理；若 native 未退出，回已知 unchanged／unconfirmed，Python 不再跑該候選的 publish，並阻止模型再呼叫或另一人工寫入。外層 graph unwind 只解除 Python callable 活躍，不解除 native outstanding。待顯式恢復確認 native stopped，原 binding exact request 仍可用、這次未进入 SQL 的證據仍在時，可做原 operation 的 terminal failure 閉合交易；不需重跑原 transform。

SQL／回執不明：等待 Python publish 已返回／unwind（含其連線清理），再查同 operation。receipt 有值則使用 immutable 原結果；無值仍不得猜 abort。必要的 DB 未提交證明沿 ER03／既有 storage recovery，不以 Node 停止代替。若無法取得證明，維持 uncertain。

close：`close_turn(...,jd_session=...)` 之前先核全部 quiescence，JD reconcile 限原 factory identity／binding／digest，僅補缺失 ToolMessage，再走原 child→root closure，連同通知 manifest 傳遞。**不能只對缺失 ToolMessage 做恢復**：若 provisional unconfirmed 結果已成 ToolMessage，該 operation 仍 pending；即使 messages 配對完整或 child 已 terminal，所有 pending bindings 也須核實閉合。原訊息不改寫，durable binding 的閉合資料在既有 checkpoint 更新；不以新增重複 ToolMessage 修正。

`_execute` 的 stop／configuration-error、`_reconcile` child-terminal shortcut、startup stopping、submit(abandon_pending)、`stop` idle branch、`send_input(abandon_pending)` 全部使用同一判斷；不能漏一條硬寫 True 的捷徑。worker 自己在 graph unwind 後收尾時，不 join 自己的 Future；由它證明 graph/tool stack 已退出，且查 native owner／SQL 狀態，再做 serialized close。外部 stop／shutdown 則 wait/join 後查相同證據。

## 6. restart proof 與可用恢復出口（NL-R01／NL-R02 修正）

### 6.1 有限選項與推薦

| 選項 | 正常與 crash 能力／取捨 |
|---|---|
| A：僅每文件 Popen owner | 正常同程序清理可做；但 API 在 transform 中、transform 正常完成後 receipt 前、SQL 結果未明時 crash，都會失去完整 owner。不是只在極端 kill 失敗才發生。A 無一般可用恢復出口，只能當施工中間狀態。 |
| B：A＋API 自身先加入 App 專用 Windows Job、同安裝單程序 mutex | 無外部 supervisor；API 與其固定 Node 由同一 kernel job 覆蓋。重啟先證明舊組全退，再以 DB lock 確認原結果；可閉合一般 crash 旅程。代價是 Windows 專用依賴／啟動約束、整 API crash 會停止該 App 的其他文件工作，需沿原 Memory 恢復接點收尾。**推薦 B，待採用與實測。** |

這不是 DB／Memory authority 轉移，kernel job 只證明執行已停止；文件及 receipt 仍由原 PG owner 決定。新增 Windows 啟停不變量跨 API composition seam，正式採用須在既有採用 ADR 中明列，或新增一份 Proposed 的有限程序生命週期 ADR，經 G6 再成 production；本稿不自行授權。現有 `api.py` 的 workers=1／reload=False 與 App RLock 不等於已實作 OS mutex，Task 5 要補實體接點。Task 3 不做空 owner stub。

### 6.2 精確官方接點與 wrapper

下列均於 2026-09-10 定點查閱；Win32 是目前 Windows desktop API，目標為目前本機 Windows，nested job 需 Windows 8+。不廣搜通用程序管理器。

- [CreateJobObjectW](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw)／[OpenJobObjectW](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-openjobobjectw)：可由名字取得同一 kernel object 的 handle；新建／既存可區分。NULL security attributes 的 handle 不繼承。job 的最後 handle 關閉且成員退出後才銷毀；kill-on-close 可終止成員。**本案以名稱找 exact object，不用 PID 重找程序。**
- [AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)：API 可指派自身；其後 CreateProcess 子程序預設沿 job chain。既在其他 job 的程序有 nested／UI-limit／權限相容限制；正在 terminating 的 job 不可加入。故新 API 在清理舊 job 時保持未加入，舊 job 不重用。
- [Job accounting](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)：`ActiveProcesses` 表示仍關聯程序數；持同一 job handle 查到 0 才通過本案整組退出 gate。不是用非保證送達的 completion-port 訊息或「TerminateJobObject 返回成功」代替。外部仍持 process reference 可能延後數字下降，逾時不謊報退出。
- [CreateMutexW](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw)／[WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)：mutex 給單啟動者所有權；abandoned 只證明擁有 thread 結束，不保證整個 API 已死。因此取得 mutex 後仍清查舊 job。等待 handle 期間不可把它關掉。
- 成熟 wrapper 推薦 [pywin32 b312](https://github.com/mhammond/pywin32/releases/tag/b312)，已讀 [win32job 原碼](https://raw.githubusercontent.com/mhammond/pywin32/b312/win32/src/win32job.i)：直接提供 Create/Open/Assign/Terminate/Query/Set job API 與 PyHANDLE，不自寫 ctypes 結構／FFI。選用固定 312、Windows-only marker，接線時確認 Python 3.12 wheel；未安裝。這不是泛用 job scheduler。其 [README licenses](https://raw.githubusercontent.com/mhammond/pywin32/b312/README.md)明示混合授權；[win32/License.txt](https://raw.githubusercontent.com/mhammond/pywin32/b312/win32/License.txt)允许免費使用／修改／散布並要求保留通知，不能籠統稱整包 MIT。正式依賴落鎖時核同版 License-File metadata，保留 notice。
- [PG16 row locks](https://www.postgresql.org/docs/16/explicit-locking.html)：FOR UPDATE 與衝突 row lock 等交易結束；Read Committed 下一 statement 可見已提交結果。本案對 `publish` 的語句序列推論見 §6.5，不把 OS 停止等同 PG rollback。

### 6.3 API 自持 Job 的最小啟動順序

新增有限 `windows_lifecycle.py` helper，由真正 App 啟動入口在 `create_app/open_service`、executor、DB／模型 client、scheduler 或任何 Node 前呼叫；保持單 worker、無 reload。不是在 FastAPI 已接請求後才加入 job。helper 只管理此 App API／固定 Node，不把開發 terminal、Codex、PostgreSQL Docker 或其他使用者程序加入。

1. 用同一本機安裝／PG runtime 的固定、非 DSN 明文識別形成 App 專用 named mutex/job；所有啟動入口必須使用同一 key，禁止每次随机名稱讓舊組失聯。限定同 Windows 登入 session；換 session／另一套安裝共用同 PG 不列支持，不能忽略衝突。用 `Local\Caliburn.<installation>.ApiMutex`／`ApiJob` 兩個不同名稱。這是安裝配置常數，非 process store。私有 ACL 限目前使用者與必要系統存取；命名衝突／拒絕存取不假當不存在。
2. bootstrap/main thread 取得 mutex，持到整 API 結束，handle 不繼承。超時表示既有 API 仍擁有入口，本次退出／顯示已開啟，不殺正常 API。正常持 mutex 與 abandoned 都必須進下一步核舊 job，不能把 abandoned 當整組停止。
3. 新 API **尚未加入 job**，`OpenJobObject` 取舊 job 的 query／terminate handle。只在確定不存在時走新建；其他錯誤 fail closed。存在時對此 exact object 做一次 TerminateJobObject，再在一個有限 monotonic cleanup budget（本案起始 10 秒，可配置）中核 `ActiveProcesses==0`。這是有界 OS 停止觀測，不是 receipt polling／工具 replay。未達成就不開 DB/client/admission；顯示啟動恢復失敗，明示重試啟動可再做一次。沒有無限 spinner。
4. 確認 0 後關舊 handle；舊 terminating job **不得重用／加入**。建立新同名 job，若仍回既存則不繼續指派（另次明示啟動可再核）；新 job 設 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`，不設任何 BREAKAWAY／SILENT_BREAKAWAY 或 UI limits，核設定成功。
5. 用目前 process 的精確 handle `AssignProcessToJobObject`，再 `IsProcessInJob` 核本 App job；任何 nested-job／ACL／指派失敗均在 admission 前退出。不能 fallback 到無 containment 模式，也不採 CREATE_BREAKAWAY_FROM_JOB。API 在此之前 crash 尚未做任何 App work；此後 crash 已受 job 管理，**故沒有每顆 Node spawn→assign 的 gap**。
6. API 終身保留新 job handle，絕不傳給 Node；Node 以現有 shell=False／close_fds=True／CREATE_NO_WINDOW 啟動，無 breakaway，membership 自動繼承。handle 繼承與 membership 是兩回事。這時才開 DB、恢復 catalog/checkpoint、最後開 admission。startup generation 的 `prior_group_stopped` 是本程序 proof，不能由 HTTP／模型自填。
7. 正常退出先關 admission、stop/join、全 native cleanup、必要原 binding/turn closure、關 DB/client。Job handle 留到最終 process exit；API 自己也是成員，提前 CloseHandle 會終止自己，不能在一般 context manager finally 中當普通資源提早關閉。無法 orderly close 而 process 最終死亡時，kill-on-last-handle-close 收整組；下一 bootstrap 再核舊 job。bootstrap 自身若在持舊 handle 清理時死亡，也沒有新 App work；若 crash 發生在自身已加入後，已是受管組的一員。

官方支援這套先收舊組、後加入新組的因果條件；**Inference**：在所有 App 工作均晚於成功入 job、無 breakaway／handle 泄漏及互斥不繞過的前提下，舊 job 已不存在或 exact handle 的 active=0 可覆蓋舊 API 與全部 Node，而不必持久列每一次 read。不存在只適用這套機制已覆蓋的 prior execution，不能回套舊版／直接繞過 bootstrap 的程序。首次切換先受控停止舊入口並驗沒有未受管 App，再開新機制；測試使用獨立安裝 key，不能套當前 API。

### 6.4 所有 native-capable 入口的覆蓋与可枚舉责任

| 入口 | 同程序 owner／重開停止全集 | 邏輯 request／結果 owner |
|---|---|---|
| AI edit | 每文件 `JdNativeCalls`，跨程序由整 App job 覆蓋 | Task 3 保存的所有 pending JD bindings（不限缺失 ToolMessage）；原 call identity／operation／digest／exact request，逐一對帳。 |
| AI read／selection、HTTP selection | 同一每文件 native owner；沒有 operation 也登記。重開由 job 全組退出證明，**不靠 edit receipt 列舉 read** | AI read 用 saved call 配對丟失結果；HTTP read 可另次明示重讀，不建 write receipt。不得假報資料不存在。 |
| manual save | 每文件 admission＋native owner；重開全組 proof | Task 5 在既有文件 root checkpoint 增一個有界 `jd_manual_pending` admission descriptor，before-Node 保存 `{operation,base,digest,request_key,origin}`，最多一筆；exact candidate 仍沿既有 browser submission cache。descriptor 不存第二份 JD，不造 HumanMessage／AI run。terminal 回執确认後清除；恢復時可僅閉合已知未提交 failure，不需重跑候選。這是現有 checkpoint 的有限 binding 增補，需隨 Task 5 review，不另設 DB running 表。只有 client cache 不足以讓 server 完整枚舉 admitted manual，故不能省略這一筆。 |
| create（尚無 document ID） | App lifecycle 內的 create-entry owner，以 request_key 作 ephemeral key；全部同 App job。不能假放到不存在的文件 runtime | 沿已採[旅程 §6](2026-09-10-jd-employee-journey-design.md#6-最小-apiwire-增補與回覆遺失)同 key／原 title catalog 唯一性，catalog＋initial revision＋head 同交易。browser create cache 保存 request key；不生假 AI binding。沒有成功 row 就沒有可解鎖的半文件，應先確認上次建立；見 §6.5。 |

manual descriptor 是**本輪新增的具體 Caliburn mapping**，不是既有 code 事實／公開 wire 欄位。它使「全部已發配 operation 閉合」可由 server 核對；沿同一 Saver root state 與文件 admission序列化，跟 AI run 互斥，不引入其他文檔／Memory authority。若只留 client cache，必须承認 cache 消失時 server 無法枚舉，不得聲稱滿足全閉合 gate。Task 5 應採前者並在正式採用 ADR 明列其有限 binding 性質。

正常 orderly close 必須停下**全部入口**：AI Future、HTTP manual／selection 及 create owner 都 drain；讀取也不能在「已全清理」之後又 spawn。重開一律使用 bootstrap 整組 proof 作完整覆蓋，再用 descriptor/bindings 作邏輯閉合。單有 edit A 的 receipt 不涵蓋 selection B；A receipt＋B pending crash 與沒有 B 的正常 restart 都有明确判斷，不再从空 registry 猜全集。

### 6.5 Python 已停止後的 PG 對帳與 known-none

四項證據順序固定：**舊 App 組已退出 → 原寫入 DB 交易邊界已越過 → 每個 admitted operation 終局 → turn closure**。Node 永遠不能自行 COMMIT；但舊 Python 死亡後，其已送 PG 的 statement／COMMIT 仍可能由 server 完成，故第一項不代替第二項。

`JdStore.publish` 現行順序是同交易 scope 查詢→`jd_head FOR UPDATE`→receipt lookup→base查詢→revision insert（若有）→receipt insert→head update（若有）→COMMIT；同步 `_execute` 回來才送下一句，沒有 SQL pipeline。**本案推論**：在旧 Python 已確證停止、沒有其他 bypass writer 下，新對帳交易取得同一文件 head row lock 後，再用下一 statement 查原 scoped operation/digest，先前已進入任何 mutation 的交易必已 commit／abort；它若尚在等 head lock，當時只可能有前置讀／lock statement，死亡 Python 不能再送後續 mutation。因此此時 absence 可證原 operation 未發布，不是一般 receipt 無 row 都可作 known-none。

新增同 store 的限定 `reconcile_after_writer_stopped` port：要求 App 提供可信停止 proof，在同一 SQL attempt／Read Committed 交易鎖 head，**锁後一次 receipt lookup**；不存在則回內部 known-none 證據，有 receipt 則回原結果。不能以既有裸 `receipt()` 實作此 port，不能用 last/current head 內容相似代替。head missing／lock timeout／DB unavailable 均不建立 proof；維持可明示恢復的 uncertain，下一次最多另一個有界 lookup。此 port 不重跑 Node／LLM；row lock 是 recovery barrier，不是新增文檔 authority。

若確定 known-none：以原 operation／digest 閉合一次 `save_failed`（已知未发布、failure receipt），不是配置新 identity 或自動重播候選；failure closure 沿原 `publish(error=...)` 原子回執，禁止發布內容。已存 terminal 先回原結果；現行 publish 會重檢 receipt 保留 race 安全。原人工候選仍在 browser cache，終局閉合後員工可明示新提交；AI 不自行再跑整輪。如此即使一般 crash 在 transform 與 publish 之間，也有可用「確認結果→本次未保存→繼續編輯」出口。

manual cache 遺失時，descriptor 只授權上段**不發布內容的 failure closure**，不授權重建或重跑原 candidate。Task 5 用限定內部 identity／failure port 共用既有 receipt 寫入交易，不偽造一份空 candidate 來通過 intent validator；digest 直接核對可信 before-Node descriptor 與 scoped receipt。若要重執行原 exact request，仍須取得 cache payload 並重新核 digest，且沿 ER03 另次明示恢復 gate；本文推薦先終局閉合，不默認 replay。如此無須把完整候選複製到 checkpoint，又能核全體 admitted manual。

create 沒有既存 head 可鎖，不套此 known-none port。沿已採同-key POST：catalog 的唯一 `create_request_key` 與 initial 同交易；同 key reentry 在唯一索引衝突處等待舊交易結束，再讀 winner／同 digest 返回，或舊交易 abort 才建立一次。這是旅程既有顯式同意圖防重，不新增 create 自動重播；普通 GET 查無仍不能聲稱未曾執行。Node 初始空值驗證不持 DB，已由 job proof 收尾。current Task 2 尚未有 request-key catalog 接線；Task 4／5 的既定旅程實作必須先具備該唯一約束才驗 create restart，不能以 current 每次新 UUID 的方法直接重送。

### 6.6 restart 判斷／可觀察 crash 窗口

| 狀態 | 結果與有限出口 |
|---|---|
| 瀏覽器重開、API 還在 | 取原 run／manual descriptor/cache；同程序 native owner清理，按原 receipt。HTTP abort 不當 stop。 |
| 正常 orderly exit／terminal receipt 重開 | bootstrap 核舊 job 全退；枚舉 pending write bindings／manual descriptor，原 receipt 閉合，正常可解 gate；不把所有歷史 operation 標 uncertain。 |
| API 在 Node transform 中 crash | kill-on-close／新 bootstrap 收舊 job，覆盖 Node 与其 read/manual兄弟；PG head lock後無 receipt→known-none→原 failure receipt→close。不重跑 Node。 |
| API 在 Node 正常退出後、publish前 crash | 同上，沒有「Node還活」也同樣需要跨程序proof；一般可恢復，不是永久維運。 |
| SQL／COMMIT期間 crash | job proof後取head lock跨過舊交易，再查原receipt；存在就成功／原failure，不在才known-none。保存值不倒退。 |
| saved next仍在已知 after_model節點 | 只對同一latest child、同AI response、sync durability、無副作用且已知在tools前的節點，舊Python已停止時可作not-started；不靠任意`endswith`白名單。saved next=tools、binding已存、無task.error皆不夠。其他入口／早前calls仍靠全組與枚舉proof。 |
| job query/指派/cleanup失敗、未受管舊版、DB不可用 | 清楚啟動／對帳錯誤，保留資料與可重試入口；不開新寫入，不聲稱取消成功。這是真依賴失敗，不是所有一般API crash的預設結局。無OS重開按鈕／沒有人工「我確認」代替proof。 |

## 7. Task 3／5 精確 Files 增補

### Task 3（只預留可接 port，不冒稱 lifecycle 已完成）

- Modify `A/src/analysis_agent/service.py`：`_context` 將同文件 stop Event 注入 JD factory；`CooperativeStop` 與 JD wrapper 同一 signal。不要求現在建立／注入未實作的 native owner。
- Create／Modify `A/src/analysis_agent/jd_tools.py`：after_model 保存 exact binding，工具 entry 核同一原 factory instance；將 cancel 傳到 `JdService`。`reconcile_operation` 結果阻止新 JD intent／模型迴圈，未閉合不是 read-only 例外。
- Modify `A/src/analysis_agent/jd_service.py`、`jd_engine.py`：實際 keyword-only cancel 傳遞，包含所需 selection 窄 seam；僅預留可接受 owner 的內部 port／型別，不注入空物件、不以 forwarding 測試宣稱停止。manual/create admission、完整 owner、publish gate 都留 Task 5；內部 DTO／模型 wire 不增加 lifecycle 欄位。
- Modify `A/tests/test_jd_tools.py`、`test_jd_provider_binding.py`：固定 Event 傳遞、saved binding 早於 engine invocation、ToolMessage 原 ID、non-strict 三 schema 完全不變。更新 `A/README.md` 的 seam／Task 5 限制。

### Task 5（在原 Files 清單增加以下範圍）

- Create `A/src/analysis_agent/windows_lifecycle.py`、`A/tests/test_windows_lifecycle.py` 與有限 subprocess harness；Modify `A/src/analysis_agent/api.py` 真正啟動入口，於所有 App work 前 bootstrap，禁止未受管替代入口；依採用結果在 `A/pyproject.toml`／隔離 lock 加固定 Windows-only pywin32，不改 root lock、不安裝到 production。
- Modify `A/src/analysis_agent/jd_store.py`：新增 §6.5 限定停止後 head-lock／receipt port；不拿裸 receipt absence 当 proof。Modify `conversation.py` root state 與 `jd_routes.py` manual admission：§6.4 有界 `jd_manual_pending` descriptor，before-Node durable、terminal後清除；create 沿 Task 4 已定 catalog unique key，不新建 running表。
- Modify `A/src/analysis_agent/jd_engine.py`：有限 owner helper 與所有退出分支、spawn／Popen／pipe／thread retention；同文件多 call 不覆蓋。
- Modify `A/src/analysis_agent/jd_service.py`：核原生停止才 publish；取消後候選不发布；failure closure 與 unconfirmed 分離。
- Modify `A/src/analysis_agent/service.py`：§5 所有 close/admission/startup/shutdown 路徑，兩階段等待，run 投影保留 uncertain；manual／selection 的 owner 同樣可觀察。
- Modify `A/src/analysis_agent/conversation.py`、`jd_tools.py`；Create `jd_reconcile.py`：有界 reconciliation port，先核全體未閉合 binding，不只 missing ToolMessage；保留原 Memory reconciliation、unknown write、manifest 傳遞。
- Modify `A/src/analysis_agent/jd_routes.py`、`W/src/jd/useJdSession.ts`／`JdWorkspace.tsx`（W 依原計畫 alias）：明示一次恢復、停止 spinner、讀取可用、pending gate 不因 receipt 無 row 解開。
- Modify `A/tests/test_jd_engine.py`；Create／Modify 原 Task 5 的 `test_jd_admission.py`、`test_jd_close_reconcile.py`、`test_jd_postgres_recovery.py`、`tests/jd_process_worker.py`；更新 `A/README.md` 恢復與啟停限制。不在此稿建立新測試檔。

## 8. 有限 acceptance 增補

事件 barrier 控制時序；不靠 sleep 判斷安全，不新增付費／自然模型案例。沿既有測試 fixture，不為 lifecycle 重跑所有保存測試。

| ID | Task／反例 | 必須結果 |
|---|---|---|
| NL01 | 3：before-model／tool-entry stop 與已進 engine | 未開始不 spawn；已開始收到同一 Event；before-Node durable binding 查得到。Task 5 再驗同 latest child／已知無副作用 after_model／sync 邊界才作 not-started，next=tools不能。 |
| NL02 | 5：terminate／kill 等待皆失敗、工具返回 | Popen 仍在 owner，Future.done／ToolMessage／receipt lookup 無 row 都不解 gate；Node／SQL／模型 attempt 不增加。 |
| NL03 | 5：後續同 handle 已退出 | 顯式恢復一次 cleanup／lookup；保留原 operation／digest，符合未發布證據才寫 failure receipt、close，gate 可解除。 |
| NL04 | 5：BaseException、stdout overflow、I/O thread 尚活、spawn 尚未返回 | 每路保留 outstanding；process 已退但 thread 未退仍不假報 cleanup complete；spawn 超預算後返回立即清理，無第二 spawn。 |
| NL05 | 5：commit 後 ToolMessage 遺失 | 原 terminal receipt 唯一回填，head 不倒退；cancel 不回滾既有提交；後續重開正常可解 gate。 |
| NL06 | 5：unconfirmed ToolMessage 已存在／child 已 terminal | 仍找出 pending operation，先對帳再 closure；原訊息不改寫、不補第二個同 ID 結果；manifest child→root 正確。 |
| NL07 | 5：正常 shutdown／新 API | 全入口停止admission、AI/manual/selection/create均drain；新bootstrap具整組proof、全部binding／manual descriptor閉合；正常解gate，不把歷史operation一律標uncertain。 |
| NL08 | 5：一般API crash三個barrier | 分別在transform中、transform後publish前、COMMIT前後終止受管API；新bootstrap查exact Job active=0（或依既定機制不存在），head-lock後查原receipt；known-none閉合原failure，已commit回原成功。native invocation不增加、不配置新operation；無永久uncertain或OS重開依賴。 |
| NL09 | 5：receipt 查詢失敗／查無且 DB abort 未證 | 不假造結果，不重播；已知 native stopped 仍不能冒稱 SQL 未提交。 |
| NL10 | 5：edit A receipt＋selection B pending→crash | 不以A receipt／空registry證B；全App job退出才涵蓋B。另驗無B正常重開可解gate；manual descriptor缺client cache仍可按原identity閉合failure，create沒有假文件owner／AIrun。兩文件正常owner不混用；整API crash確實停止兩文件但各自獨立對帳。 |
| NL11 | 5：真bootstrap而非測試父程序代勞 | 用產品bootstrap＋獨立test job key；父harness只觀測，不替產品cleanup提供proof。驗mutex競爭／abandoned-owning-thread但API其他thread仍活、API入job前後crash、新bootstrap清舊job時crash、child不繼承jobhandle／不能breakaway、nested指派失敗不開DB／admission。 |
| NL12 | 5：DB boundary精確反例 | 舊publish持head lock，new recovery必等待；COMMIT後返回原receipt，abort後absence才known-none。另阻住舊SELECT FOR UPDATE前置語句，確證其無pipeline後續mutation；lock timeout／head missing／DB失聯均不造proof。每明示恢復一個有界查詢attempt，failure closure另計，不跑模型／Node。 |
| NL13 | 5：未受管／名衝突／wrapper／create | job名稱ACL錯誤／外部handle拖延active數／terminating-job重用拒絕，均有限報錯；首次legacy切換有受控停止證據。create舊txn提交／rollback與同request-key重入各一次，唯一catalog＋initial＋head，不造重複文件。 |

## 9. Closure

- Finding：Task 2 的 conservative unconfirmed 回覆沒有提早解 gate，但 lifecycle 證據目前未跨 service 返回；Task 5 不能只加 `outcome.quiescent` 或讀 receipt 解決。
- Status：NL-R01／NL-R02 已依有限review修訂，待窄複核。推薦B已給一般crash可執行出口、manual／read／create覆蓋与head-lock known-none條件；沒有跑faulttest，不把設計閉合當實作完成。
- Why：官方 framework 管 callable／checkpoint；Popen 與 SQL 結果各需實際 owner 證據。
- Affected artifacts：本文提供 Task 3／5 精確增補；register／plan 由主工作單位採用後同步，本稿不自行更動。
- Reopen trigger：引擎開始衍生未受管程序／DB能力、跨session／多API共用PG、bootstrap可繞過、新code改publish鎖序／使用pipeline、nested job不相容，或NL反例失败。
- Next gate：窄複核NL-R01／NL-R02，主工作單位採用B並同步有限ADR／plan；Task3繼續。Task5實作NL01–13及正式gate後才宣稱完整取消／restart驗收，不需先廣搜或另建外部supervisor。
