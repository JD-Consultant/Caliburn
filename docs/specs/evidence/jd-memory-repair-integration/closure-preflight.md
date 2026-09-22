# C 接線：停止、原結果查回與回合閉合前置

2026-09-13；程式基準 `8403d7e2`。本次獨立唯讀核對 `AiRuntime`、`AiRunCheckpoints`、`ManualRuntime` 與已採用的 `RepairWorkflow`；只寫本文，沒有改產品、執行測試、呼叫 provider 或讀寫 DB。動態 ToolNode 內 C 子圖的實際可見性由本輪另一個原生探針驗證，本文不假定其 snapshot 形狀。

## 1. 推薦的最小接合

**C 沿同一個 foreground owner、原生 Agent／Saver 及既有 PublicationStore。只補 C 的原 call 證據與收尾分支，不把它當成 JD operation，也不能列入只讀工具豁免。**

結束條件需要三件分開證明的事：原工作確實停止、原 C 發布結果已確認、保存的對話及回合狀態已閉合。Future 結束只滿足第一件；查到 receipt 只滿足第二件；補 ToolMessage 或 `update_state` 不可替代前兩件。

這沿用[已採用核心](../../2026-09-13-jd-memory-repair-core-slice.md)與[接合前窄審](../jd-memory-repair-core/runtime-preflight.md)，沒有重開 patch、Memory 分層或資料表設計。C 的 artifact／publication、JD 的 SQL operation、原始對話各維持原本權責。

## 2. 最小分類矩陣

下表中的「可閉合」都另要求同文件／dataset／run／原 AIMessage／tool call／App operation／原輸入匹配，實際 Future 與 callback 已停止，或已取得既有 foreign-host proof；其他 JD／C 操作也都已確認。只根據 stop event、HTTP 取消、timeout 或 `task.error is None` 不成立。

| 原 C 所在情況 | 足夠的證據及可回報內容 | 查回／保留 gate |
|---|---|---|
| 本輪沒有 C call，也没有 C binding | 固定完整原消息與已保存狀態均無 C；沿既有一般回合收尾。新輸入未保存仍只走既有本機 `_confirm_input_not_saved` 的完整前後比對，不由 `run_not_found` 推定。 | 無須補 C 結果；仍等原回合閉合。 |
| 已有原 C call，但尚無 C binding | 必須由**已驗的原生步驟邊界＋實作不變量**證明沒有機會進入 C handler，例如 C 的副作用入口必須先讀到已持久化的原 binding。只有這種正面證據才可說 `not_executed`。 | binding 缺失、缺 child 或 task 沒有 error 單獨都不足；無法證明則保留 gate，不沿未知工具的 JD `_not_executed()`。 |
| 原 C binding 已保存，但原工具任務未執行 | 需要將 binding 對上**那一個原生 task**，並有明確的未開始邊界。`next=tools` 或只見待處理 call，不能直接當未開始證明。 | 若實際探針無法區分「未開始」與「曾執行但未存回結果」，就 unknown；不為了放行重播 handler。 |
| 原 C 已進 seed／edit／validate／save，但可證尚未進 publish | 原生同步 checkpoint 的有效進度若能證明仍在發布之前，可回報「已停止、尚未發布」，**不能說整個工具未執行**。可能已有 StateBackend 暫存或未發布 MemoryVersion；保留現場，不自動刪檔或回退。已保存的 `invalid_edit`／`no_memory`／`stale` 結果要按原核心分支核對。 | 能證未發布且原輸入、結果完整，才補原 call 的失敗／停止結果並閉合。若只能看到可能過時的父層指標，不能據此放行；需本輪動態子圖探針確定可讀的進度界線。 |
| 原 `PublishRequest` 已保存，尚未看到 publish 結果 | `next=publish` **不能證明 publish 沒跑**：已 COMMIT、但節點結果／checkpoint 回覆遺失也可能留在這個位置。以原生保存的原 `PublishRequest` 呼叫現成 `RepairWorkflow.reconcile`，不重跑 prepare。 | 匹配的原 receipt 可確認 applied；無 receipt、讀取失敗或不匹配一律保留 gate，除非另有正面原任務未開始證據。不得新建 operation、重送 publish 或借 JD reconcile 寫一筆假的未執行回執。 |
| 已 COMMIT，但 feedback／結果未知 | 原 receipt 的 request digest、kind、source、doc、base、memory 及 applied revision 都與原 request 匹配；確認可用的 current 不落後 applied。 | 使用核心 `reconcile(original_request)`；成功只讀查回，不重跑 patch／Store save／publish。原 request 丟失或 current 不可確認，仍保持 unknown。 |
| 發布結果已確認，但原 ToolMessage 未保存 | 原 call／binding、原 request、receipt 加上已保存的 C outcome 能配對；只補該 call 的確切結果。若 outcome 本身沒有保存，不可聲稱 receipt 證明原 patch 文字；edits 只能來自原固定 binding。 | caller 需決定原 outcome 與查回 feedback 的有限結果形狀，再一次性閉合；沒有模型／工具重播。不可為產生 ToolMessage 再跑整個 C 子圖。 |
| 原 ToolMessage 已保存，或 root close ACK 遺失 | 已保存結果驗證成功後，固定重讀 root，核 terminal／無 pending tasks、原話保留、所有結果及 C 證據／讀版完全一致。 | exact readback 已成立才 `finish_foreground`；不成立保留 gate。既有 `close` 的一次 update＋只讀查回可沿用，但新 C 欄位必須納入同一完整比較。 |

「未發布」和「未執行」刻意分開。發布前已做的暫存、patch、來源回讀及 immutable artifact 保存，不會因取消而變成沒有發生；它們也不等於 publication head 已變。

## 3. 現有程式的精確接點

| 接點 | 現況證據 | 本輪有限修改建議 |
|---|---|---|
| [AiRuntime._verify_saved_results](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py) `165–204` | 有 binding 的結果僅依 JD receipt 投影；未綁工具只豁免 JD／Memory reads，其餘須像 JD 的 unchanged error。 | 增加明確 C 分支，核原 call／C 結果／publication 證據。不要加進 `MEMORY_READ_NAMES`，也不要用 JD `MutationResult` 解讀 Memory applied。 |
| 同檔 `_settle` `611–676` | 真 `handle.wait(0)` 後查 JD bindings；未綁的其餘工具會落入 `_not_executed()`，再追加 ToolMessage、close、finish。 | C 在這個預設分支之前完成分類；unknown 直接保留 gate。所有 C／JD 結果确认後才呼叫 close。C 查回不呼叫 `owner.recover_foreground` 的 JD `AdmittedIdentity` 接口。 |
| 同檔 `_inspect_run` `424–478`、`_lookup`、`recover_previous` terminal 分支 | `effects_settled` 目前以 JD 原操作集合、closed 與工具結果驗證成立；歷史查回亦有自己的 terminal 驗證。 | 同一 C 驗證須涵蓋正常返回、唯讀原 run 查回、外來宿主恢复與 terminal 分支，不能只修 `_settle`。`operations` 仍是 JD receipt 集合；C 不放入 `read_run_operations`。唯讀 inspect 不發布或補寫 checkpoint。 |
| [AiRunCheckpoints._material／_observe_current](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) `113–144`、`296–395` | 目前只讀一層 consultant child；`372` 明拒 child task 中再有 `state`。目前 material 只有 JD bindings／read、model view、初始 Memory view。 | 依**實測的唯一 C 路徑**做窄解碼與 scope 校驗。不可直接移除巢狀拒絕，或將不相容圖投影成 empty。新 C 材料須進 observation，否則閉合會遺失證據。 |
| 同檔 `close` `397–473` | 必須 caller 先證停止與 SQL 結果；原 messages 只可追加匹配 ToolMessage，bindings／view 不變；一次 `update_state(as_node='consultant')`，ACK 遺失後只核 exact readback。 | 保留這些界線，將原 C binding／核定 outcome 與同輪 current Memory read binding 納入 desired 與 exact 比較；不能在 C unknown 時清掉 pending 圖。 |
| [ManualRuntime foreground](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py) `_require_foreground_stopped:443`、`finish_foreground:712`、`close:1006` | 真 Future 與 settled callback、foreign proof、原 permit、per-document gate 已存在；Future done 不等於 graph closed。關閉要等登記讀取、foreground 及閉合，才釋放資源。 | 同步執行的 C I/O 留在這個生命週期即可；不加 Memory 專用 pool、lock 或 run 表。caller 的 closed callback 需要核新 C 欄位；C 未解決時 `close` 應維持 False，不能提早關 Store／Saver／pool。 |

所有行號指上述基準，之後實作可能移動。上述是採用缺口與建議，不表示当前尚未公開 C 工具已在誤報成功。

## 4. 原結果查回與同輪讀取不要混淆

`RepairWorkflow.reconcile` 已正確接受**原生保存的原 PublishRequest**，不接受 caller 重填 edits；receipt 證明的是原 publication，不能由它反推模型當時輸入的 patch。App 若需要回報原修改，須核同一原 AIMessage／call 與持久 binding。

另一個需要保留的差別是：原 C applied H2／ToolMessage feedback read H2 已完整保存，之後 B 發布 H3，原 ToolMessage 仍合法。不要每次歷史驗證都拿「現在 reconcile 得到的 head／guide H3」與原 ToolMessage H2 逐字比較，否則會將真實歷史判成矛盾。應核真 applied receipt、保存當時的 feedback 及固定讀版；缺 ToolMessage 時另用明確查回結果收尾，而不是改寫既有消息。

初始 `jd_memory_view` 仍是本輪模型最先看見的固定版本；同輪 C 成功後的 current reader 是另外已核的 feedback 接點。不能把初始 view 改成 latest，也不能從前輪 C 回覆更新新 run。未來 B 的 publication 不因此被撤回或凍結。

## 5. 必要驗收與未證範圍

本輪接線只需保留以下能改變判斷的反例，不另做通用恢復框架：

1. 原 C call／binding 已存但 handler 未進：精確 native task 證据成立才 `not_executed`；缺材料安全阻擋。
2. seed／patch／artifact save 後停止：不宣稱整個工具沒跑；確認未 publish、原話保留，不回退 artifact／JD。
3. prepare 已存與 publish COMMIT 後 ACK 遺失：即使同見 `next=publish`，只由原 request／receipt 或額外確定的未開始證據決定；禁止重送。
4. 真結果已存但 ToolMessage 未存：只補原 call；root close ACK 遺失後 exact readback 可確認，不產生第二次 publication。
5. 原 feedback read H2 已存，較晚 B H3：舊結果仍合法，同輪不因查回偷偷追 latest；新輪另取 initial。
6. C 尚在 source／Store／publication I/O 時取消或宿主關閉：Future 未完不釋放資源；Future 已完而 C unknown 仍不釋放 gate。

**仍待本輪實證：**動態 ToolNode 內的 C task 是否由同 compiled graph 的公開 API 完整觀察、哪個 fixed checkpoint 能證未開始、成功後 C outcome 在哪個原生材料中仍可讀。前輪核心驗證是具名 compiled child，不等於本輪 dynamic ToolNode 已證；本文沒有把這項差別省略。若探針否定目前觀察路徑，須先選能保留原材料的最小原生接法，不能猜 namespace 或自行掃 raw blobs 作新引擎。

## 6. 官方證據與版本

2026-09-13 新讀 [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 與 [Python 3.12 Future 文件](https://docs.python.org/3.12/library/concurrent.futures.html)，並核本地已鎖 LangGraph **1.2.11** 原碼：`types.py:637–706` 的 `PregelTask`／`StateSnapshot`、`pregel/main.py:1392–1438` 的固定 `get_state` 及 `2986–2988` 的 sync checkpoint 等待。這些是現用穩定 OSS API；LangGraph 為 MIT、Python 為 PSF 授權。本輪沒有升級，也沒有宣稱另查 PyPI 最新發行。

- **官方事實：**checkpoint 保存 thread state，Store 保存另外的應用資料；兩者並非一次跨系統交易。原生 snapshot 是 step 起點，tasks 是待執行步驟、曾嘗試可能帶 error；不能反推 `error=None` 就從未執行。已安裝原碼的 `get_state` 在未給 checkpoint id 時會套 pending writes，給固定 id 時不套；本案採固定配置避免把 overlay 當閉合。
- **官方事實：**`durability='sync'` 在下一步前等待 checkpoint 寫入。它不等於外部 PublicationStore COMMIT 與 Saver 原子提交。Future 的 timeout 不取消工作，running Future 也不能用 `cancel()` 證明停止。
- **本案選擇：**同一 owner 等實際停止、查原 receipt，再追加原 ToolMessage 與 exact native closure；這是根據以上契約的業務接合，並非大廠規定一種通用 C schema。
- **沿用已核依據，未重搜：**[OpenAI 原 call result](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)、[Anthropic tool error](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)、[AWS 原意圖冪等](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)。它們支持原請求／實際結果配對及不確定重試要受控，沒有公開證明兩家使用本案的 Memory／DB 內部實作。

結論限於程式與官方契約的有界核對；不能以本文取代本輪 C 動態圖、真 PG 故障與新程序恢復驗收。
