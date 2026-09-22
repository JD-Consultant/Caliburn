# RS-4：foreign-host AI restart 的有界驗收前置

查閱：2026-09-13。範圍：新 relational App 的 Windows／PostgreSQL 宿主及原生 AI checkpoint。**只讀盤點與測試設計，未改 src、未啟動程序／資料庫／provider。**本稿不把既有人工重啟或本程序 AI PASS 改稱跨宿主 AI 恢復已完成。

後續同日獲授權的有限 owner 實作與非 DB 驗證另記 §7；§1–6 保留前置時點，四個真新程序場景仍未由本作者執行。

有效路由：[目前決策](../../../current-decisions.md)、[AI 回合與工具結果](../../2026-09-13-jd-ai-runtime-and-tools-slice.md)、[人工 Windows 重啟結果](../../2026-09-13-jd-host-restart-recovery-slice.md)。本輪延續現有鎖定版本，不安裝、升級或重開框架比較。

## 1. 結論與先接的差異

沿真正 `open_manual_host → bootstrap_host → HostLease → startup` 接新 AI 恢復，重用 `AiRunCheckpoints`、binding decoder、原 receipt 投影及共同 JdStorage。原生 Future 只能證明本程序工作；新程序必須使用真正 HostLease 的舊組退出證據，不能為了套用現行 `recover_foreground` 而建立假的已 done Future、合成 ForegroundPermit 或 caller `stopped=True`。

現在 `ManualRuntime.finish_startup` 逐頁掃全 catalog、包含封存文件，但只讀 `DocumentCheckpoints` 並以 `_manual` 接回人工 identity。AI／START pending 目前會被原生 busy／格式檢查阻擋。這是現行安全界線，**尚未有 foreign AI startup adapter**；新工作須辨識並對帳原 AI root／child，不能只略過 AI 讓 ready=true。

最多四組真新程序案例即可形成首輪證據：正常退出、活舊 writer／未提交、部分已成功加 COMMIT ACK 遺失、兩種「模型或 SQL 尚未執行」原生 checkpoint。錯 scope、畸形 descriptor、變動 digest、過期本地 attempt context 等保留現有窄單測；除出現新的跨程序反證，不將它們全部重演成昂貴新程序。

## 2. 現行程式與既有證據

| 實際檔案／接點 | 已有能力與此輪限制 |
|---|---|
| [windows_host.py](../../../../experiments/jd-relational-app/src/jd_relational/windows_host.py)：`bootstrap_host`／`HostLease` | 限專用 Windows process 的主執行緒、同安裝 Local namespace；named mutex 排世代，查 exact 舊 Job、必要時一次 TerminateJobObject、等 ActiveProcesses=0，再於同一期限取得 fresh Job 並 assign self。沒有 PID registry／TTL／caller proof。 |
| [host_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/host_runtime.py)：`open_manual_host`／`ManualHost.close` | 真 bootstrap 成功後才建立 engine／Saver；`check_installed` 只讀 prerequisite，沒有 setup。返回的 `ManualRuntime(previous_host=lease)` 尚未 ready；close 等 owner 排空再關連線／engine，OS handles 留到程序退出。仍未組裝 AI startup。 |
| [configured_host.py](../../../../experiments/jd-relational-app/src/jd_relational/configured_host.py)：`open_configured_host` | 從同一 ready 設定讀 installation_id／dataset_id／signing key／DB／checkpoint schema，native 排他後重新比對原設定才開 DB。普通 open 不重新產生身分／setup。它提供穩定配置；不是原 AI run 已恢復的證據。 |
| [manual_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py)：`finish_startup`／`require_stopped` | 全 catalog keyset 掃描，最後才 ready；foreign manual entry 保存真正 previous_host。failure-only SQL 每次核 exact current recovery attempt、其真 Future running／同 thread context，並重核 lease。foreign AI 尚需相同責任的正式接線，不借人工 descriptor。 |
| [storage/service.py](../../../../experiments/jd-relational-app/src/jd_relational/storage/service.py)：`lookup`／`reconcile_stopped`／`_transaction` | 原 identity／digest／origin／run／command kind 核對；未找到 receipt 才鎖 document→head，下一個 READ COMMITTED statement 再查原 receipt。恢復只補原 operation 的 save_failed，從不建 candidate 或重播 command。鎖取得／查回失敗仍 unknown，不能當「原操作沒執行」。 |
| [ai_checkpoints.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py)：`observe`／`_initial_material`／`close` | latest 只定位，固定 root／必要時 child checkpoint；原 START input 以原生 Saver.get_tuple 取得，核完整原 input，而非 pending overlay。close 只保存已核材料、ACK 不明讀回一次；**它不證明原 process 已停或 SQL 已對帳**。 |
| [consultant_tools.py](../../../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py)：binding decoder／`verify_binding_message` | 從已保存 identity-only binding 核原 AIMessage、call ID、共同 parser 與 canonical input digest。完整 BoundEdit cache 只在舊 run 記憶體；新宿主不得重建它來執行寫入。 |
| [test_windows_host.py](../../../../experiments/jd-relational-app/tests/test_windows_host.py)／[windows_host_worker.py](../../../../experiments/jd-relational-app/tests/windows_host_worker.py) | 已有 4 真 OS 情境：正常退出與競爭、mutex thread 已結束但舊 process 仍活、child membership／父退出後 child 終止、舊 Job 額外 handle 阻止 fresh。連同輸入／假 OS 分支的 30 PASS 見既有結果；不能單憑它推定 AI／SQL 已恢復。 |
| [test_host_recovery_postgres.py](../../../../experiments/jd-relational-app/tests/test_host_recovery_postgres.py)／[host_recovery_worker.py](../../../../experiments/jd-relational-app/tests/host_recovery_worker.py) | 真 `open_manual_host`、`jd_host_test` Saver、專用 PG55436；四組人工 before-SQL／COMMIT ACK／活舊 writer 競爭／兩 root 含 archived。父只送 STOP／CRASH 及查證自有 process，沒有提供 `PreviousHost`。原語意、messages／snapshot／receipt 保持的證據可沿用，不能將 manual 七欄 pending 塞入 AI 當作新測試。 |
| [test_configured_host_native.py](../../../../experiments/jd-relational-app/tests/test_configured_host_native.py)／[configured_host_worker.py](../../../../experiments/jd-relational-app/tests/configured_host_worker.py) | 既有真 DPAPI／設定、明示新合成 DB 初始化、ordinary open 與 Uvicorn 人工接合。其 `fresh_database` **會 CREATE DATABASE**；新 AI restart 四案不應直接重用該 fixture。可沿普通 open 的 no-setup assertion；本輪不重做設定初始化。 |
| [test_ai_runtime_postgres.py](../../../../experiments/jd-relational-app/tests/test_ai_runtime_postgres.py) | 真 owner／PG Saver／固定 SDK 的四案已證本程序 AI→manual→AI、ACK 查回、純訪談重開及真 Future 取消；使用 `jd_runtime_test`、每案不同 dataset，沒有 native host bootstrap。不可用該 schema 的跨 dataset 歷史根，冒充單一固定安裝的 startup 測試。 |

上述既有數字按各原結果讀取，本輪沒有重跑或另行加總。新的 foreign-host 證據須由新程序實際輸出產生。

## 3. PreviousHost 能證明與不能證明的事

`PreviousHost.require_previous_stopped()` 是窄 Protocol；真正 production instance 是 bootstrap 私有 constructor 發出的 `HostLease`。bootstrap 在 mutex 排他期間處理 exact 舊 Job，且新宿主加入的是 fresh Job。其後每次 check 核 singleton／本 PID／原主執行緒仍存活／本宿主仍在 exact Job。句意是「本安裝這一世代持有原生排他，先前受管組已處理完」，不是每次重新列 PID 或查新的 stopped 表。

| 已核官方依據（查閱沿 2026-09-13 現有研究） | 對本案的直接限制 |
|---|---|
| [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[Job accounting](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)、[CreateJobObjectW](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw) | Job 是程序組，不是 DB transaction。child 普通繼承 membership；不能 break away。KILL_ON_JOB_CLOSE 受最後 handle 影響；同名既存 Job 不等於 fresh。舊 ActiveProcesses=0 與 fresh 建立的原生順序不可由父測試 bool 代替。 |
| [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)、[CreateMutexW](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw) | WAIT_ABANDONED 只說 mutex owner thread 結束；process／其他 threads 仍可能存活。WAIT_TIMEOUT 不可啟動新 host 或進 DB。 |
| [Python 3.12 Future](https://docs.python.org/3.12/library/concurrent.futures.html) | 等待逾時不停止 callable；只在原程序有其 Future 的實際證据。新程序的「沒有 Future」不能證明舊 writer 已停。 |
| [PostgreSQL 18 explicit locking](https://www.postgresql.org/docs/18/explicit-locking.html)／[READ COMMITTED](https://www.postgresql.org/docs/18/transaction-iso.html#XACT-READ-COMMITTED) | OS client 停止後，PG server 仍須完成原 transaction 的結果與鎖釋放。document→head row lock 屏障後下一 statement 才判原 receipt 是否存在。timeout／連線失敗不是不存在證明。 |
| 同頁 PG advisory lock 官方契約 | Advisory lock 由應用程式自訂使用，session／transaction lifetime 不同；也不能證明原 process group 或 checkpoint 已關閉。**現行 relational JdStorage 的這條恢復路徑沒有 advisory lock**，本輪不替舊維護設計的 advisory 機制新增接線或聲稱已使用。 |
| [AWS safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | 原 key／原意圖／原結果由既有 operation identity／receipt 核對。OS proof 只讓 App 能進 failure-only 對帳，不授權重播原 LLM／mutation。已 committed 保持原 created_at、base/result、status／error 語意，不升到新 head。 |

平台版本沿已驗 Windows 10.0.26200／pywin32 312／PG18.6，以及 App 已鎖的 Python／LangGraph／PG Saver；授權與精確來源見[既有 Windows 結果 §2](../../2026-09-13-jd-host-restart-recovery-slice.md#2-官方契約與本案映射)。這是公開契約與本案接法，不猜測雲端厂商的內部宿主實作。

**Proof 有效期：**foreign entry 必須仍綁本次真 lease，每次恢復交易開始及 row barrier 後照原 `require_stopped` 再核；若 lease 不再有效、checkpoint scope／原 binding 不符、SQL 結果不明，整個 startup 維持未 ready。不能 cache 一個布林結果到下一 host generation；不能以某一份文件恢復成功代證全 catalog 已掃描。

## 4. 最多四組真新程序情境

以下是新驗收設計，尚無 PASS。舊 host、接替 host、競爭 host 都在各自 dedicated helper 中呼叫真正 bootstrap，父 pytest 從未加入 Job。所有模型回覆在舊 host 內由真 SDK＋MockTransport 固定；接替 host 將模型呼叫與 `JdStorage.execute` 設為 test-only 禁入計數，恢復必須走實際 startup／lookup／failure-only port。

### FH-01：正常 AI 結束、正常程序退出後只讀接手

舊 host 正常執行 read→完整新增 task→final，等 owner 的真正收尾與 `host.close=True`，正常 exit=0。保留另一份已封存、無 pending 的文件作 catalog oracle。新 host 使用**同一 installation／dataset／signer／checkpoint schema**，開始前 ready=false，全掃後 ready=true；已 terminal 原 run／HumanMessage／完整 AIMessage／ToolMessage／model-view、原 revision／receipt 完全不變，0 model／0 mutation／0新增失敗 operation。

核新 PID、舊 process handle signaled、實際 bootstrap／startup marker及 no-setup marker。封存文件應被掃描，但不捏造「自然可在封存中啟動 AI」。這一案確立成功退出是可觀察的 idempotent startup，不拿 crash-only 成功推稱普通重開。

### FH-02：活舊 writer 拒絕第二宿主；真舊組退出後才判未提交

舊 host 的 AI 已有持久 binding，真正 SQL callable 進入修改但在 COMMIT 前以合成 barrier 暫停。此時第二 host 用同 installation 啟動，必 `host_already_running`、DB／Saver 建立計數為 0，原 writer 仍活。不能讓 contender terminate 仍持有 mutex 的舊 host。

再令舊專用 helper 自身 `os._exit`；它不執行 Python cleanup、不回傳 proof。接替 host 必經原生舊組／fresh Job 路徑，沿真正 SQL row barrier 查原 receipt；原 transaction 未提交，只有原 operation 的 failure receipt，current／head 保持，原 HumanMessage／已完成 model call 保留並配未成功結果，不 resume／不建立候選。

若本組同時要求覆蓋「新 bootstrap 確實 Terminate 尚活舊 Job 成員」，可沿既有 child helper：舊 host 普通 spawn 一個無 breakaway 的合成 child；父只持有該 test-owned Job 的 query handle，使舊 host 自 crash 後 child 暫時仍活。接替 host 自行 OpenJob／TerminateJob／Query ActiveProcesses=0；父僅在 child 原 process handle 真 signaled 後關掉自己那個 query handle，讓 fresh Job 可於同一期限建立。父不傳任何停止判定給 runtime。此 handle 是故障注入，不是新的 production supervision；已有原生 abandoned-owner／child 測試仍保留各自證據，不能改寫成普通關閉行為。

退出或舊 Job 退休超過原啟動預算時，新 host 固定錯誤、0 DB admission；不得重複 Terminate、重用 old Job、按 port 找 PID 或為了通過斷言提前釋放 host handles。

### FH-03：一項已完成、下一項 COMMIT ACK 遺失，graph 尚未閉合

舊 host 固定流程 read→寫入 A→收到並保存真 ToolMessage→再 read→寫入 B。對 B 只在真正 storage.execute 的 COMMIT 接點注入「先 real do_commit、後失去 ACK」，再於本程序 coordinator 閉合前的 test-only barrier 自 crash。這不是在工具外先造 committed receipt，也不是單純關掉 HTTP response。

父唯讀 oracle 先確認 A、B 都有原 committed receipt，記原 IDs／digest／created_at／base/result 和 current digest；確保 B 的 fault marker 命中、root／child 尚 pending。新 host 0 model／0 execute；先查回兩個原 receipt、保留 A 已保存完整 ToolMessage，只補 B 尚未配對的實際結果，核原 call ID／name／command digest，再持久閉合原 run。沒有原 final AIMessage 就不能合成完成回答或假標自然回合成功；JD 的兩次已提交效果保留。

這案同時覆蓋「工具效果已完成但 graph 未閉合」和部分成功：恢復不因沒有 caller／本地 cache 就丟掉 A、不把 B 改稱未保存、不增加 revision。人工後續修改前，原 transcript 必已完整配對且 startup ready；後續 normal edit 若另做，只用來證明 gate 已解除，不重跑整套 CRUD。

### FH-04：同一舊宿主的未執行 binding 與原 START input

舊 host 準備兩份不同文件，分別停在兩種真 PG Saver 邊界，再自 crash：

- A：真 after_model binding 已被 PostgresSaver 保存，ToolNode／SQL 尚未進入，原 operation 無 receipt；新 host 有真正 prior-group proof 後沿原 identity failure-only 對帳，正文不變，恰一原 failure receipt，對應原 call 的 error ToolMessage。
- B：新 run 的原 native input checkpoint 已保存，而下一 root loop put 尚未發生；`next=(START,)`、metadata source=input，原 HumanMessage／descriptor 在 Saver 原 START payload。模型／工具計數皆 0。新 host 用 `AiRunCheckpoints._initial_material` 的既有公共 Saver.get_tuple 接點驗原 input，保留此前完整對話與這一則新原話，以 failed 閉合，**0假 operation／0 revision**，不 `invoke(None)`／resume START。

新 host 必掃到兩份並完成後才 ready。B 的 root.values 可能尚未包含新 run descriptor，不能看不到 `jd_ai_run` 就跳過；也不能從任意 pending-writes overlay 拼出新的 HumanMessage。這一案例把「未知是否執行」和有原生證據的「尚未進 SQL／模型」分開，不由父 manifest 告知 execution status。

## 5. schema、fixture 與證據隔離

1. 只用明示 opt-in 的現有 **127.0.0.1:55436／caliburn_jd_relational_test／jd_test／PG18.6**，不讀真設定、環境金鑰、production 或另建 DB。沿公共十三表與既有 migration，不新增 run／proof／identity 表，不清任何舊資料。
2. 推薦為這條**固定安裝**測試使用獨立 native Saver namespace `jd_ai_host_test`，包含原生四表且由既有正式初始化程序**另外明示準備**；本輪前置／測試不呼叫 setup。若尚未存在，報 prerequisite 未滿足，不能測試中偷偷建表。不得直接用 `jd_runtime_test` 的每案隨機 dataset AI 根，否則全 catalog startup 會將測試污染誤認為產品跨 scope 問題。
3. 此 namespace 採固定、明示合成的 fixture installation UUID／dataset UUID／signer，跨 old/new/contender、跨本測試重跑均一致；只新增 document／run UUID。這是測試組態，不是 production UUID registry。其目的為讓先前已 closed 的 fixture root 仍能合法再掃，不能每次換 dataset 卻沿用同一 Saver 舊根。
4. host 案例順序執行，協調避免其他組對同固定安裝啟動 host；每案只核本組 document 的 operation／revision／snapshot，仍讓真正 startup 從全 catalog 取得 IDs，不以 manifest 的清單取代 catalog authority。malformed／unknown root 的錯誤出口先沿純測；不要為塞進首輪四案而污染共用 Saver 永久阻斷後續測試。
5. 可沿 `open_manual_host` 的實際入口＋固定合成 codec 做最短 host 驗收；它不聲稱 DPAPI 設定接合再次通過。若採 `open_configured_host`，僅建立本 fixture 的 ready 合成配置檔並保持原 identity，普通 open 的 no-setup assertion仍需保留；不可直接借會 CREATE DATABASE 的 `fresh_database` fixture。
6. helper 用 `CREATE_NO_WINDOW`、自有 Popen／native process handle、固定 stdin 控制、monotonic deadline。timeout cleanup 只終止已確認本測試建立的 process／Job，不依 port、模糊名稱或掃 PID。不能對 pytest／Codex tool process 呼叫 bootstrap；bootstrap 失敗後該 dedicated helper 必須退出，不能同程序改 key 再试。
7. evidence 放新 `.research-tmp/jd-ai-host-recovery-<fixture-run>/`，保留 boot PID／parent PID、場景／fault marker、固定 error code、startup前後ready、舊／新 process exit、model／execute／setup計數、原 run／operation／revision ID及digest。原問答／正文仍以 PG／Saver為權威；一般 stdout／stderr 不寫 provider key、DSN、自由格式例外或正文。全合成固定回覆也不能外送 LangSmith／provider。

## 6. 最小施工與退出條件

先接 server-owned startup 的 AI observation／candidate-free reconciliation，再寫上述新 worker／測試。既有 `PreviousHost` 足以提供平台停止前置；需要新增的是把 foreign AI identity 與這個真 capability 綁在受控恢復 attempt、驗完整原 transcript／receipt、持久閉合及保持 startup gate，**不是另一套 process manager、advisory fencing 表或可注入 bool 權限**。

每案必先能在未接 foreign AI startup 的現況得到安全阻擋或明確反例，再記修後結果。成功條件同時包含：原生 bootstrap 確實執行、讀取 schema 不 setup、完整 catalog 掃描後才 ready、原結果／原話保持、無 LLM／mutation replay、所有自有 helpers 真退出。任何未知結果、舊組未停、native root 不可辨認、binding／scope矛盾，均留 gate，不能把 safe-block 說成已恢復。

本稿未實跑四案；成功 exit／真 forced group／PG rollback／原 receipt／原 START input 的證據须分項報告。自然模型、來源／Memory／選區、聊天 HTTP／Web、跨 Windows 登入 session／不同安裝共享 DB、restore/key rotation 不由這四案證明。

## 7. 後續 owner 接點實作（2026-09-13，限定本程序反例）

主代理另授權本作者只修改 [manual_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py) 並新增 [test_foreground_restart.py](../../../../experiments/jd-relational-app/tests/test_foreground_restart.py)。`claim_foreground_coordinator` 可一次註冊 startup callback；全 catalog 同一 startup lock 內，每份文件先回調並嚴核 0／1，再做原 manual／native idle 檢查，未 closed foreground 也阻擋 ready。

`adopt_previous_foreground(identity, confirm_original)` 只在 runtime 自己的 exact scan token／document／thread／ContextVar 內可用，核真已注入 previous-host capability、原 identity 與回傳 None 的持久確認。外來 entry 沒有 Future，保留 previous_host／settled／foreground_interrupted；只准原結果恢復與持久閉合，execute_foreground 明確拒絕。每個恢復 SQL 仍是實際原生 Future，沿 exact attempt token／thread／running guard，不能拿已 done recovery context 借下一次權限。相同 identity 重用原 foreground handle，尚未結束的 SQL attempt 重試仍拒絕，不另排第二次。

本地 executor submit 已確知失敗的既有 `future=None + foreground_not_started + settled` 只保留 terminal cleanup；它不能取得 SQL recovery 或 foreign adoption 資格。lease 在確認 callback／SQL 等待間失效會阻擋下一界線，close 仍等待 startup I/O 及實際 owner 收尾。

首跑新測試 **17 FAIL／0.57s**，皆為尚無 callback／adopt 介面的預期紅例；實作後新 17＋既有 foreground／manual／catalog／startup 92 共 **109 PASS／1.06s**。再補原 manual recovery 不被取代、confirm 後 lease 失效、SQL 第二檢查點失效、foreign 舊 context 的 done／下一 attempt 重用，共組 **113 PASS／0.89s**（新 21、原 92），沒有加總其他重疊組。差異空白檢查通過。

測試使用真正 ThreadPoolExecutor／Event／Future，OS、checkpoint、SQL 都為明示合成 ports；沒有 Win32 bootstrap、DB、provider、schema setup 或跨程序證據。AI checkpoint discovery／coordinator settlement 由其他作者接合，尚待主代理整合與獨立審查；不能將本段標為四組 foreign-host 驗收通過。
