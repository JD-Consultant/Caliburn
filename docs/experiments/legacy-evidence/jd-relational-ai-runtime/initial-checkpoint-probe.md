# RS-4：初始輸入 checkpoint 失敗的有限驗證

查閱／實測：2026-09-13。使用現有穩定鎖定 LangGraph **1.2.11**、langgraph-checkpoint **4.2.0**、langchain-core **1.6.3**，MIT。没有安裝依賴。此證據是該版本 native InMemorySaver／StateGraph 行為，不推定其他供應商內部實作相同。

## 官方接點與實際限制

[官方 Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) 說明 checkpoint／pending task writes 的區別、`get_state`／`get_tuple` 及同步保存模式。[官方 time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel) 說明 `update_state` 新增 checkpoint，經原生 reducers 套用指定節點的寫入；`as_node` 影響下一節點，之後呼叫 `invoke` 才會重跑節點。本案只做明示停止後的 state update，沒有 resume/invoke 重播。

已核安裝原碼：`langgraph/pregel/main.py` 的 `_prepare_state_snapshot`（約 1145–1265 行）、`bulk_update_state`／`perform_superstep`（約 1590–2050 行），以及 `pregel/_loop.py` 的 `_first`／`_put_checkpoint`。固定 `checkpoint_id` 的 graph 讀取不套用一般 task pending-writes overlay；原始 input 存放在原生 `channel_values[START]`。這個 START 形狀是本版本的實測接點，不能宣稱為跨版本不變的資料格式。

## 探針結果

[可重現探針](initial-checkpoint-probe.py)／[完整輸出](initial-checkpoint-probe.stdout.txt)，**8 個初始情境＋1 個 clear-task 反例通過**。每種主要情境均驗新文件與已有完整舊對話，模型節點／provider／SQL／graph 重播均為零。

| 故障 | 原生後續動作及固定 root | 判斷 |
|---|---|---|
| 第一個 input put 在保存前單次失敗 | 仍會嘗試下一 root loop put；後者若成功，原話／新 run 已在固定 values，next=`consultant`、child 尚未開始 | 不能只因第一個 put 例外就宣稱 input 沒有保存；既有 observer／close 可處理 |
| 第一個 input put 保存後 ACK 遺失 | 同樣可能有後續成功的 root loop checkpoint | 依固定最新 checkpoint 判斷，不能因 ACK 遺失重送模型 |
| input put 成功，下一 root loop put 前失敗 | latest overlay 有新原話／run、next 空；固定 root 仍 source=`input`、next=`__start__`、唯一 task 為 START，新原話／run 尚不在 values；原 payload 留在 `get_tuple(fixed_config).checkpoint.channel_values[START]` | 需有限 START input 讀取分支，不能把 latest overlay 當完整閉合 |
| 全部 put 均保存前失敗 | 新文件仍無 checkpoint；已有歷史則最新固定位置／內容維持呼叫前完整版本；沒有本次原話／run | 只能在真本次 Future 已結束、沒有工具／SQL，並核對前後完整固定狀態未變後回報 input 未保存；`run_not_found` 單獨不構成證據 |

另測 `update_state(fixed_input_config, None, as_node=END)`：它套用已存在的 START pending output 後，反而產生 next=`consultant`，**不是這個狀態的一步閉合保證**。因此本案不走先清 tasks 再另寫失敗記錄的兩次保存流程。

## 本案採用與已完成的有限修正

主代理同意後，`AiRunCheckpoints.observe` 補以下唯一分支：

1. 固定 root 的 source 必須是 `input`；next 與唯一 task 只能是原生 START，無 child／interrupt。
2. 經 graph 實際 Saver 的公開 `get_tuple(fixed_root.config)` 讀原 payload，核對其 checkpoint ID／thread／namespace 仍為同一固定位置。
3. payload 必須恰為原 `jd_ai_run`、單一 `HumanMessage`、空 bindings、`read=None` 四欄；run 必須 running，文件／dataset／run／原話 digest 全部一致。不得把目前 request 重新拼成「已保存的原輸入」。
4. 原生 `add_messages` 合併之前完整對話與原 Human；先前 model view 仍須與原 AIMessage 配對。舊 run 若存在，必須已終結、同文件／dataset，且不能與新 run 重用 ID。bindings／read 歸零來自已保存的新 run input，不是恢復時清掉既有工具記錄。
5. `close` 沿原先一次 `update_state(as_node="consultant")`，保存原完整消息、原 view 與 failed／cancelled status，再固定讀回驗證。ACK 遺失不重試 update。actual Future 已停止及沒有未確認 SQL 的責任仍在呼叫者，不由 observer 授權。

新增四個真 native 初始故障反例（新／舊對話 × 正常 closure／closure ACK 遺失）首跑 **4 FAIL／48 deselected**，原本都因 START 狀態被拒而無法收尾。修正後 `test_ai_checkpoints.py` **52 PASS／0.98s**，含十二個錯誤 payload／scope／原始內容反例。沒有修改工具業務、AiRuntime 或資料库。

## 全部 put 失敗時的精確界線

交給 AiRuntime 的有限未開始確認：必須持原本同文件 permit，確認本次实际 Future 與 callback 完成、session 未進工具、owner 沒有 SQL entry；呼叫前 snapshot 本來已 idle。再讀目前 latest locator 及其固定 snapshot，驗前後 checkpoint ID／namespace／thread 相同、完整 values 與原消息／run/model-view 相同、tasks／next／interrupts 皆空，而且本次 Human ID／run 不存在。新文件則前後皆真正空 state 且沒有 checkpoint ID。

符合時可明示本次 `input_saved=False`；資料未保存不能改說已保存。若位置或內容有任何變化、固定讀取失敗，或本次內容出現在原生 input checkpoint／pending 狀態，就繼續封鎖並走對應原結果恢復。本探針沒有實作或驗證該 AiRuntime 分支，也不提供跨程序死亡證據。
