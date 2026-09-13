# C 工具子圖的原生觀察實證

日期：2026-09-13。基準：`8403d7e2`。範圍：新隔離 App 的 native C 接合前置；沒有修改產品程式、schema、Saver／Store 權責，也沒有 provider／PG／新程序呼叫。

**結論：工具內動態建立或預建閉包的 C 圖，都不能由重建 inspection root 的公開子圖觀察路徑讀到原 request。採 `Command.PARENT` 移交 root 的固定 wrapper 節點可行；C staging 保留在子圖。** 正常完成、prepare 後 interrupt、publish 已提交但 ACK 遺失三案均已實跑；未以猜測 namespace 或直接掃 Saver 補救。

## 1. 固定環境與實際探針

使用既有鎖定的 LangChain 1.4.0、LangGraph 1.2.11、DeepAgents 0.7.13 與已採用的 `caliburn_memory.repair.RepairWorkflow`。沒有升級。原框架採用／授權路由沿 [C 核心結果](../../2026-09-13-jd-memory-repair-core-slice.md)。

[探針](../../../../experiments/jd-relational-app/tests/support/memory_repair_observation_probe.py)使用真正的 `create_agent`、其原生 `ToolNode`、`InMemorySaver`、`InMemoryStore` 與 SQLite in-memory publication。模型為本地 `BaseChatModel` 固定 `AIMessage`，不建立 provider client；全段明示 `tracing_context(enabled=False)`。SQLite setup 只作用於此次一次性記憶體資料庫。輸出只有合成節點／ID定位類型、計數、布林與 request digest，不輸出來源／patch／Memory 全文。

在 `experiments/jd-relational-app` 重現：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache python tests/support/memory_repair_observation_probe.py
```

這是有斷言的 standalone 原生探針，不是 pytest 全組。初版九案同次 `exit 0`，`passed_cases: 9`，主函式量測 **1.371 秒**；後續只跑新增的 wrapper 三案，首次即 `exit 0`／**3 案、0.634 秒**。兩者皆不含 Python／依賴載入，不合稱同次十二案。現在腳本包含上述十二案例供完整重現。沒有重跑既有 PG 或整個 App 測試。

## 2. 會改變方案的反例

第一種：root → `consultant=create_agent` → 真 `ToolNode` → tool 內當次 `RepairWorkflow(...).graph.invoke(...)`。

第二種：同一結構，但把已編譯的 C 圖放入工具閉包。

兩者各跑 normal／interrupt／ACK lost，六案均有相同觀察結果：

| 情境 | 重建圖的 `get_subgraphs(recurse=True)` | 公開 task 觀察 | SQL receipt／模型呼叫 |
| --- | --- | --- | --- |
| normal | 只有 `consultant` | root 已完成；無 C request 路徑 | receipt 存在；模型 2 次 |
| prepare 後 interrupt | 只有 `consultant` | `root.tasks[consultant].state.tasks[tools].state is None` | 無 receipt；模型 1 次 |
| 真 publish 後拋 `PublicationUncertain` | 只有 `consultant` | 同上；C request 沒有可追的 child config | 原 receipt 存在；模型 1 次 |

這不代表工具內子圖沒有 checkpoint 或不能 interrupt。它證明此組合的**公開靜態發現路徑不可用**；預建 workflow 物件、單純拿同一 Saver，均沒有讓 `ToolNode` 暴露該子圖。

官方 [Subgraphs／View subgraph state](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#view-subgraph-state)（同日查閱）明確區分這個限制：`get_state(..., subgraphs=True)` 需要可靜態發現的節點；工具函式或其他間接呼叫不符合，但 interrupt 仍可傳到頂層。這與六案實測一致，並非從另一廠商行為類推。

## 3. 最小可採靜態接法與三案結果

探針仍使用真正的 `create_agent`／`ToolNode`。工具只回傳原生 `Command(graph=Command.PARENT, goto="memory_repair", update=...)`，把原 call／狀態移交同 root 的具名 C 節點；C 完成後有限結果節點寫同一 `tool_call_id` 的 `ToolMessage`，再進 consultant。六個修補步驟仍是原 `RepairWorkflow.graph`，沒有自行複製 graph loop 或 patch 流程。

官方 [Graph API／Command graph 與 Return from tools](https://docs.langchain.com/oss/python/langgraph/graph-api#graph) 支援這個父圖移交接點；共享訊息欄沿原生 reducer。官方 [Subgraph communication](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#define-subgraph-communication) 同時允許直接掛 compiled graph，或由固定 node wrapper 映射不同 state。這是框架能力；選用這條 C 接法是本案取捨。

| 靜態 C 情境 | 可讀 request 路徑 | 不重做的實際斷言 |
| --- | --- | --- |
| normal | 完成後同 call 的 `ToolMessage.artifact.request` | ToolNode 移交 1 次；C 六步各 1 次；模型 2 次；publication 1 次 |
| prepare 後 interrupt | `root.get_state(config, subgraphs=True).tasks[memory_repair].state.config` → `root.get_state(fixed).values["request"]` | 暫停時 C 的 `next=("publish",)`；原 request 已存、無 receipt；native resume 後只重入 publish，前五步／原工具／第一模型呼叫不重做，最後 publication 1 次 |
| publish ACK lost | 同一固定 C 路徑 | 原 request 的 operation／document／digest 配原 receipt；`reconcile(request)` 不重播；原生 root `update_state(..., as_node="consultant")` 後 latest `next/tasks` 皆空；模型維持 1 次、publication 維持 1 次 |

重建 inspection graph 的模型呼叫皆 **0**；讀取不改來源讀取／發布計數。原 `HumanMessage` 的 ID／角色／內容保持，正常／恢復結果都只有一筆原 tool call 及相配 `ToolMessage`。清掉 latest pending 後，保存的原 fixed root 仍可追到同一 C request；不必恢復執行該歷史圖。

最後一案的 `update_state` 只證明**原生資料收尾能力**。探針沒有提供或驗證 App owner／Future／OS 停止憑證，也沒有把「圖沒在跑」當停止權限。真正產品只有同 owner 已確認停止且原 publication 結果可證時，才能沿既有收尾規則套用。

## 4. 首敗與修正

六個工具內反例首次整組成功。靜態候選首次失敗於測試 oracle：要求 `get_state(child.config)` 的整個回傳 config 字典與輸入逐鍵相同。實際輸入與輸出 `thread_id`／`checkpoint_ns`／`checkpoint_id` 完全相同、`next` 都是 publish；框架回傳額外的執行期 `__pregel_checkpointer`。

探針改為核對三個公開定位欄與實際 pending／request，不把執行期物件當另一份持久定位 authority。之後三個靜態案例成功，再加入原 Human／call 配對斷言；最後九案同次成功。沒有為通過修改產品或框架實作。此紀錄不把 oracle 錯誤記為產品缺口。

## 5. 最終 wrapper 三案：不把 staging state 帶到 root

在同一探針增加 `wrapped=True` 的固定節點版本：真正 compiled C graph 直接捕捉在 `wrapped_repair` 函式閉包；工具經 `Command.PARENT` 保存合成原 binding 與 messages。wrapper 從 binding 投影 C input，`repair_graph.invoke(...)` 後直接回同 call 的 `ToolMessage`，其 artifact 保存 request；只有 `memory_repair → consultant`，不另設結果節點。

新增 normal／interrupt／ACK lost 三案首次即成功，公開 path、request／receipt 核對、resume 前五步不重做、ACK lost 只讀後 native close，與 §3 三案相同。額外斷言：

- 暫停和結束的 root values 只含 `messages`、`jd_memory_repair_bindings`；沒有 `files`、`material`、`version`、`request`、`outcome` 等 C 內部 channel。
- 根節點只有 `__start__`、`consultant`、`memory_repair`；没有額外 result node、head／failure counter state。
- `get_subgraphs(recurse=True)` 仍回 `consultant`／`memory_repair`；interrupt 與 ACK lost 時 `tasks[memory_repair].state` 是含 publish pending／原 request 的 `StateSnapshot`。wrapper 沒有破壞觀察性。
- 正常完成後回 consultant 得到 final；原 Human 不變、同 call 只有一筆 tool result。ACK lost 後不 invoke，`update_state(as_node="consultant")` 可清 latest pending，原 fixed root 的 request 仍可查。

因此最終接合推薦此 wrapper 版本；§3 的直接共享 `RepairState` 僅保留為先前控制組。App 的完整 binding codec、native `Runtime.context` resolver 與 actual owner 尚須各自接入驗證，不能以探針的合成 binding dict 取代正式契約。

## 6. 本案接合邊界與後續必要驗證

- C 圖維持 per-invocation，繼承同 root Saver；本次不需要另編一個獨立 Saver、不掃 namespace、不使用私有 `__pregel_*` 值作持久 authority。上面的公開 fixed config 由實際 task 回傳，不自行拼接。
- 最終 wrapper 已驗證不同 schema 的投影，不要求把 staging 內容再存 root。產品採 core 唯一六節點 factory、由 native `Runtime.context` resolve 本 run workflow；該新 factory／資源解析接線尚未由本探針驗過。
- 同一 run／call／operation 的身分仍須由 App 已保存 binding 驗證；`PublishRequest` 本身不含 AI run 身分。多 call、舊 C 結果／新 run 混配、未知 node／scope 都不能憑「找到一份 request」接受。本次每案只有一個合成 call，沒有宣稱已覆蓋完整 binding decoder。
- 正常完成用原生 `ToolMessage.artifact` 保留內部 request／已核結果；模型短回覆與同輪有效 read head 的推導由後續 App 接線核實。這份探針未驗 provider serialization，也未驗同輪 C→readhead 更新。
- ACK lost 案只執行原 receipt 對帳及 native root 收尾，沒有再次 invoke。interrupt resume 是用來驗 native checkpoint 邊界的獨立正例，不是對不明 publication 提出重送政策。
- 真 PG／PostgresSaver、新程序恢復、native owner 取消／close 排空、原 App START／inspection 分支及 daily AI 採用都留在後續接合驗收。既有 C 核心的真 PG 證據沿 [上一單位結果](../jd-memory-repair-core/postgres-results.md)，不與本次九案／新增三案累加。

本前置已足以排除隱藏工具子圖路徑、採用官方靜態節點方案；停止本題廣搜。沒有新增表、來源／Memory 權威或通用定位引擎。
