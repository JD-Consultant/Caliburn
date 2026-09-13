# RS-4 前景協調器獨立審查

日期：2026-09-13。本次唯讀審查 `ai_runtime.py`／`test_ai_runtime.py`，以及 OR-R01 的 `manual_runtime.py` 修正與四個反例。未修改程式；原生 graph、Future 使用合成資料，零 provider／SQL／宿主啟動。

**最後窄複核：PASS，審查範圍內沒有未解 P1／P2。**初審兩項 P2、後續 callback 註冊競爭及同步查回的關閉接點均已修正，原始反例保留於下。獨立執行受影響四檔 **126 PASS／1.54s**；最後再加兩個閉合反例後，重跑 coordinator **25 PASS／1.01s**。另核對初始 START 分支與真 PG 四案的實際證據；不宣稱跨程序 AI 恢復、自然模型或完整 App 已完成。

## OR-R01 窄複核

`_run` 現在將 entry token、每個 attempt 的 token、document、mode、實際 thread ID 一起放入 ContextVar。`require_bound` 額外確認 entry 的目前 attempt 是 write、同一 native Future 且 running；`require_stopped` 核目前 recover attempt 的同一 native Future 正在執行，及原 write 已停止。這使同一 worker thread 的舊 copy_context 不能借用後一次 recovery 的執行資格。

實際執行 manual／AI × after_done／during_next_attempt 四個反例：**4 PASS**。測試有核同一 native worker thread，並非僅用不同 thread ID 碰巧拒絕；舊 context 在原 Future 結束後及下一 attempt 執行期間均拒絕。

## CR-R01｜P2：start 的前置 checkpoint 失敗直接外吐 driver exception

位置：[AiRuntime._start](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py)，首次 `graph.get_state(...)`。這段在既有固定錯誤轉換外，先於 foreground dispatch 發生。

獨立合成探針把該 read 換成拋出 `OSError("SYNTHETIC_PRIVATE_DRIVER_DETAIL")`。實際 `start()` 結果：

```text
exception_type=OSError
fixed_code=None
marker_exposed=True
```

這不是「graph 已 invoke 後 input 保存失敗」；本反例尚未呼叫 owner.start_foreground、未執行模型或工具。public coordinator 的開始與等待應同樣回固定安全錯誤，不能要求後續 HTTP 作者另猜哪些前置 read 會直接吐原例外。

修正判準：未知 read／scope 結構失敗轉成固定 `AiRuntimeError`，不在 message／可見 cause 留原 marker；沒有派發新的 run 或 SQL。可辨識的同 key 衝突與原 run 查回狀態仍保留原錯誤語意。

## CR-R02｜P2：成功回合的必要收尾依賴 observer 呼叫 wait

位置：[AiRunHandle.wait／AiRuntime._settle](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py)。現行只有 `AiRunHandle.wait()` 呼叫 `_settle`；run Future 及原生 graph 成功结束後，若請求／頁面已離開而不再 wait，foreground reservation 仍未閉合，下一次人工／AI 工作被阻擋。

合成原生 graph 已產生正常完整回覆；先只等待底層 foreground Future，刻意不呼叫 AiRunHandle.wait。實際結果：

```text
actual_run_done=True
owner.close(0.05)=False
```

之後補 `AiRunHandle.wait()`，才完成持久閉合，`owner.close(2)=True`。舊 close 對已完成 foreground 仍 set stop Event，使這個原已正常完成的案例被標為 cancelled；保存的回覆沒有遺失，但終態受晚到 shutdown 影響。

主代理採用的有界方向：在 owner 自身已結束的 callback 後，追加原生 Future done callback，由 App 自動嘗試一次收尾；不新增 Agent／恢復工作佇列。自動收尾與手動查回共用同一 attempt 的 settling 排他；失敗保留原 handle／未解狀態，不重播模型。close 只要求仍未結束的 foreground 停止。

修正判準：

1. 完整回合結束後，即使沒有 observer，也自動保存 terminal root 並解除 reservation。
2. 原生 callback 不持有 doc slot 鎖執行外部 Saver 收尾；立即完成的 Future、callback 與 public wait 競爭不造成雙次閉合或死鎖。
3. 自動收尾故障只保留 recovery_required，沒有 raw error／重跑模型；同一原 handle 可顯式查回。
4. 正常完成後才收到 shutdown，不把成功回合改標 cancelled；仍在執行的真正取消繼續保留實際保存結果。
5. close 在 callback／Saver 尚未完成時不關資源；不以 run Future.done 取代完整收尾證據。

## 關閉前置讀取的接合條件

另一個有限探針卡住 `_start` 的首次 `graph.get_state`，此時還未登記 foreground。`owner.close(0.05)` 回 True，但 start Future 仍未結束；釋放 read 後 start 才因 runtime_closed 停下。沒有模型／SQL 重播，然而這段同步 Saver read 不在 owner 的 drain 範圍。

後續宿主接線必須確保 start 請求先 drain，或把這段前置 read 納入既有 owner 的有界生命週期。不能由 owner.close 成功推定所有 coordinator 前置讀取都已結束後直接關 Saver。若由 ASGI request drain 提供證據，须在實際組合測試中驗證；不另加全域 I/O 鎖。此條先記接合條件，不重複算成第三項獨立錯誤。

## 其餘核對與本次結果

- `_pending_calls` 核原始 call／ToolMessage 順序、ID 與 name，不讓未答工具後直接接新 AI／HumanMessage；閉合補回原 call 的實際 receipt 或明確未執行結果，沒有重呼叫模型。
- `_verify_saved_results` 把已保存工具結果與該 binding 的原 SQL observation 再比對，內容／name／success-error 不符拒絕，不能只信既有 ToolMessage 自稱成功。
- active 本地 operation 即使原 receipt 已可讀，仍加入原 attempt 的 recovery，避免讀到 receipt 就略過本地未解 owner；先处理 active，再处理其餘未解 binding。
- 使用相同 document、run、原 request digest 核對。很早以前的原 HumanMessage ID 不會因記憶體 latest handle 已換而重派模型；無法查完整原 run 時明確要求原結果查回。
- 純訪談不造 JD operation，取消保留原話與實際完整回覆；前一輪回覆不被報成後一輪失敗回覆。

獨立執行時：[test_ai_runtime.py](../../../../experiments/jd-relational-app/tests/test_ai_runtime.py) **12 PASS／0.84s**。OR-R01 **4 PASS**。前置 read、無 observer 及 start/close 交錯是額外合成探針，未算入 12 個測試；探針首輪只有 Python import path 缺少 src 而未執行，補上既有 src/tests 路徑後取得上述實際反例。沒有真 PostgreSQL、SDK wire 或新宿主驗證，不據此宣稱完整 App 已通過。

## 修後窄複核

### CR-R01 與同步 start／close

`start` 的未知例外現在於公開出口轉成 `checkpoint_unavailable`，原 exception 不作可見 cause；原同 key 衝突仍保留。首次原請求查回改經 `ManualRuntime.inspect_foreground_start`，持同文件 slot 與短期 `start_token`；manual／catalog／另一個 start 看見相同 admission，close 會等待同步 read，且同 thread 的重入 close 也不會略過 token。這個接點只管理 read 生命週期，不提供 SQL 權限，不增加全域 I/O 鎖。

主代理新增前置錯誤、同步 read／close、無 observer 三個反例，保存 **3 FAIL → PASS**；本 reviewer 在最後四檔回歸再執行，通過。原記錄的關閉接合條件已在共用 owner 收斂，不再留給未來 HTTP 作者另行補鎖。

### CR-R02、自動閉合及 callback 註冊競爭

App 現在於真 foreground Future 完成後自動嘗試一次 `_settle`。public `wait(timeout)` 只觀察 attempt Event，不取得 settling lock 或做 DB；自動閉合失敗保留原 attempt 及固定 `run_recovery_required`，顯式 `recover()` 只查原 receipt／補持久閉合。正常已完成 Future 的晚到 stop／close 不再把回合改標 cancelled。

第一次修正後，獨立審查另以 Event 控制原生 Future 重現下列真競爭：Future 已 FINISHED，但 owner 先前註冊的 callback 尚未設定 `settled`；此刻新註冊的 callback 會在註冊 thread 立即執行，不能只依註冊順序推定前 callback 已結束。當時結果如下：

```text
actual_run_done=True
after_owner_settled=True
still_blocked=True
automatic_error=run_recovery_required
explicit_recover=completed
```

主代理將此反例保存在 `test_done_callback_registration_waits_for_the_owner_callback_that_is_still_running`，**1 FAIL → PASS**。最後接點在 App callback 前明確等待 owner 的 `settled` Event，且不持有 slot lock 等待；本 reviewer 已核對實碼與重跑。不是忽略錯誤或依賴使用者事後 recover 才解除正常回合。

最後另補兩個獨立可辨識反例：自動 closure 的 Saver update 故障只嘗試一次、wait 回固定錯誤且維持封鎖，修復接點後只經顯式 recover 閉合而不再叫模型；Saver closure 被 Event 阻塞時，`wait(.01)` 仍回 Timeout、recover 回 pending、owner.close=false，釋放後才 completed。`recover()` 對已持有 terminal result 的只讀 handle 直接回同結果，避免把沒有本地 attempt Event 的原結果查回誤判 pending。此小修與兩案已獨立重跑 coordinator 全檔 **25 PASS／1.01s**。

### 同 owner 的 coordinator 唯一性

另一個相同 run 的多實例入口會讓不同 `_Attempt` 共用同 foreground handle，不能只靠每個實例各自的 start lock。最後由 `ManualRuntime.claim_foreground_coordinator` 使用既有短 registry lock 原子 claim 一次；`AiRuntime` 驗完 ports 才 claim，第二個或並行 constructor 固定拒絕。沒有跨 owner 的全域 registry、共享錯誤 codec 的 singleton 或 unregister 流程。重開只讀測試使用新 owner／同 Saver，沒有沿用已關閉 owner 冒充重開。

### 初始 input 未完整保存的範圍

已唯讀核對 [AiRunCheckpoints](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) 與[初始原生探針](initial-checkpoint-probe.md)：START 分支只讀固定 root 對應的實際 Saver tuple，核 thread／namespace／checkpoint ID、原始四欄 payload、單一 Human、空 bindings／read、同 scope／digest，及前一輪已終結。使用原生 `add_messages` 保留先前完整對話；這是已保存 input 的觀察，並不授予 writer 或停止證據。

全部 put 均失敗的分支仍由持原 permit 的 coordinator 執行，先要求真 run Future／owner callback 結束、沒有 SQL identity／tool entry，再核呼叫前後完整 idle snapshot 的位置及 values 相同，且本次 Human ID 不存在。只有符合才回 `input_saved=false`；不以 `run_not_found` 單獨放行。

額外有限原生探針：對新文件與已有舊對話的 START input 故障，各建立新的 `DocumentCheckpoints` gate 讀同 Saver，兩者均回 `document_busy`；沒有新模型節點執行。這說明 pending 不會因本地 Future 不存在被視為 idle，**不構成新 OS 宿主的 AI 恢復驗收**。目前 foreign-host pending 仍保守阻擋，沒有 graph resume 或重建執行 permit。

## 最後執行與 PG 證據核對

本 reviewer 最後自行執行：

```text
tests/test_ai_runtime.py tests/test_ai_checkpoints.py
tests/test_foreground_runtime.py tests/test_manual_runtime.py
126 passed in 1.54s
```

最後追加上述兩個 closure 情境及 terminal-result early return 後，僅重跑受影響 `tests/test_ai_runtime.py`，**25 PASS／1.01s**。工作目錄為 `experiments/jd-relational-app`；使用既有 frozen lock、offline／no-sync、`PYTHONUTF8=1` 及 `-p no:cacheprovider`。這是原生 graph／Future、InMemorySaver 與合成 storage 的窄回歸，不含 PostgreSQL／provider。與先前 12／73／4／126 PASS 有重疊，不加總。

另唯讀核對 [test_ai_runtime_postgres.py](../../../../experiments/jd-relational-app/tests/test_ai_runtime_postgres.py) 四案、主代理最後 stdout（`253 passed in 4.04s` 與 `14 passed in 6.43s`）及[切片結果](../../2026-09-13-jd-ai-runtime-and-tools-slice.md#6-分層驗收紀錄)。本 reviewer 沒有重跑 DB，證據判讀如下：

| 案例 | 原始碼及紀錄可支持的範圍 |
|---|---|
| AI → 人工 → AI | 6 次 SDK 固定請求，真正 owner／JD SQL／PG Saver；在 SQL 前核已保存 binding。兩筆成果、一筆要求及人工描述保留；head 1→4／3 operations，下一輪 notice 核原 manual operation。只實跑 read／create_task／set_text，不能寫成十工具都過真 PG。 |
| COMMIT ACK 遺失 | 2 次 SDK 固定請求；先真 commit 再拋錯，原 command 只 execute 一次。查回 committed receipt 並补原 call 真結果；run 如實 failed，不續叫模型，不能稱整輪自動成功。 |
| 純訪談與重開 | 1 次 SDK 固定請求，head1／0 operation；同程序關原 connection／owner，再建新 owner／Saver／graph 只讀原保存內容，未再次叫模型。不是新程序、Windows host death 或復原演練。 |
| 取消串流 | 1 次 SDK 固定請求，真 SDK streaming iterator 被 Event 阻塞；stop／timeout 後仍 running／blocked、metadata 拒寫、close=false。釋放真 Future 後才保存 cancelled；沒有虛構完整 AIMessage／model view。 |

四案共 **10 次 SDK 請求，全部 MockTransport，0 provider**；專用 PG opt-in 守衛檢查 DB／user／18.6 及既有 Saver schema，不做 setup／drop。最後 **14 PG PASS** 包含本輪四案與既有 manual 八案、context 兩案，不能全稱本輪新增 AI 案例。全組 1766 PASS／197 PG SKIP 是最後幾個小修前的紀錄；最後 253 窄組涵蓋這些變更，沒有假報全組重跑。

本次可判 PASS 的是程序內 admission、實際執行結果與閉合契約。新宿主 AI pending 恢復、AI HTTP／Web 接線、來源／Memory／selection 真接點、每個工具與全部故障的 PG 覆蓋、自然顧問品質及真人操作，仍按切片的未完成界線推進。
