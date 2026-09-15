# C 修補後，同輪固定 Memory 讀取接點

> **2026-09-15 Owner 校正（取代本稿下方兩項舊候選）：**本稿是 2026-09-13 的施工前證據，不刪除歷史。現在的有效規則是「本回合目前的 Memory 讀取基準」，不是結果回傳時觀察到的最新 head。C 成功時，本回合固定為 C 實際產生的 `applied_head`；若 B 已在 C 保存後發布更晚版本，仍不把本輪推到該背景版。所以下方「`head` 可採較晚 B」以及「C applied 2、取結果時 B 3，則同輪 read 3」已失效，正確結果是同輪 read 2、下一輪 read 3。C 準備修改而發現 head 已變時，仍先 stale、按需讀新版並重新評估；保存用原子版本條件。最新權責見[目前決策](../../../current-decisions.md)與[接線對齊稿 §7.2.1](../2026-09-15-jd-integration-document-reconciliation.md#721-memory-版本正式-head回合起始證據與目前讀取基準)。

**接續校正：**本稿是接線前候選。下方額外持久保存讀版／failure counter與Command更新ABI，由[交接計畫 §4](../../../plans/2026-09-13-jd-app-continuation-handoff.md#4-已收斂的-c-接合設計)的原call綁定＋ToolMessage.artifact投影取代；不新增第二份head／counter。情境及官方事實仍可參考，不能照本稿舊ABI接線。

查閱：2026-09-13；基準 `8403d7e2`。範圍是既有 C 核心接入顧問的讀版與可修失敗次數；本稿未改產品、未執行模型／DB、未重跑已通過的 124 個核心案例。最終欄位 ABI 由本輪整合設計定稿。

## 結論與已核實接點

保留這輪最初的 `jd_memory_view` 作為起始證據；只有同輪 C 的明確工具回覆可以選定後續讀版。**依 2026-09-15 校正，C 成功回覆選定的是自己的 `applied_head`，不是回覆當下可能已被背景推進的 current head。**一旦選定便固定，後來 B 不自動改變這輪讀取；下一輪重新選擇當時發布版。這是產品政策，不是 LangChain 強制的 Memory 策略。

| 現有能力 | 本輪最小接合 |
|---|---|
| [memory_context.py](../../../../experiments/jd-relational-app/src/jd_relational/memory_context.py)：`MemoryReadSession.open` 只在初始選 head；`memory_session` 核 scope、Store 與初始 view | 保留原初始核對；另從本輪已確認的 C 狀態派生固定 `artifacts.reader(version)`。不更換初始 context、不重讀 `PublicationStore.current()` 選版。 |
| [consultant_context.py](../../../../experiments/jd-relational-app/src/jd_relational/consultant_context.py)：`_project` 每次提供初始 `memory.notice()` | 保留初始導覽，補清楚規則：只接受本輪、原 source 的 C 回覆所帶導覽／讀版；舊輪工具回覆是歷史。不要使「初始導覽」名稱繼續指向已刷新內容。 |
| [consultant_tools.py](../../../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py)：原生 `wrap_tool_call` 與 `request.override(tool=...)` | 同樣以選定版本替換三個原生文件讀工具；`read_conversation` 的 summary 解析也必須使用同一選定版本。直接 conversation 引用仍沿既有唯一原話來源。 |
| [repair.py](../../../../packages/consultant-memory/src/caliburn_memory/repair.py)：`_feedback`、`_publish`、`reconcile(PublishRequest)` | 沿原結果，不重算 patch 效果。C 成功時 `head` 與 `applied_head` 都指向原發布回執，作本輪後續讀版；另核 current head 未倒退／跨文件，但較晚 B 不覆蓋本輪基準。查回只接受原保存 request，不再由模型提供 edits 或新來源。 |
| [舊 live_memory.py](../../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py)：`before_agent`、`_command`、`wrap_tool_call` | 僅採用已驗政策與原生接合模式；不 import 該研究路徑或複製舊 provider/runtime。舊 reconcile ABI 已被新版原 request 查回取代。 |

## 官方事實與版本限界

- LangChain 將 `ToolRuntime` 的 state／context／Store／call ID 注入工具，不放入模型 schema；工具可回 `Command(update=...)`，一併保存自定 state 與配對原 call ID 的 `ToolMessage`。[Tools：Access state／Update state](https://docs.langchain.com/oss/python/langchain/tools#access-state)
- `wrap_tool_call` 的 handler 回傳原生 `ToolMessage | Command`，middleware 可檢查結果；模型 request 的系統內容可經 `request.override` 投影，不必改寫 HumanMessage。[Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- 精確安裝版：LangChain **1.4.0**、LangGraph **1.2.11**、langchain-core **1.6.3**、DeepAgents **0.7.13**；公開穩定套件，MIT。核 `langgraph/prebuilt/tool_node.py::_execute_tool_sync` 與 `langchain_core/tools/base.py::BaseTool.run`：原生 schema 失敗可在工具 body 前變成 error ToolMessage；`handle_validation_error` 固定字串保留 error status／call ID。ToolNode 預設錯誤可能帶原 kwargs，不能直接複用為安全提示。
- DeepAgents 0.7 的文件工具接既有初始化 backend，沿既有官方 `ToolCallRequest.override` 替换工具；本輪不新增 backend factory、讀取引擎或 middleware hooks。框架提供 state／工具接點，沒有規定本案 PG 表、C／B 版本政策或兩次限額。

## 最小狀態與驗證

1. **初始 binding 不變。** `jd_memory_view` 繼續證明本輪開始提供哪個版本，不改成「目前讀版」，也不當作模型已理解的證明。現有 root／child 初始 view 相等檢查保留。
2. **本輪讀版是執行狀態。** 在現有顧問原生 state 增加一個有界的 C 讀版欄位與失敗計數即可；沒有有效 C 時派生初始版本。每輪初始化明確清空刷新狀態及歸零，不沿用前輪值。不要在 active child 執行時外部 `update_state` 改 root。
3. **從真工具結果更新。** App 保存的 C binding 供 dataset／document／run、原 AI message／call、operation 與原 source；模型只提供 patch。只有匹配該 binding 的原 C outcome／原 receipt 查回結果可產生狀態更新，不能掃任意歷史 JSON 當成控制指令。
4. **版本和導覽一致。** `head.memory.document_id` 必須是本文件；revision、version ID 沿既有嚴格型別／canonical UUID；導覽來自該固定 version，保留原 4000 字界線與 digest 核對。`applied` 必有匹配原 request 的 applied head，本輪讀 head 必須正是該 applied head；正式 current 可以更晚，但只用來確認未倒退或跨 scope，不推進本輪。`stale`／`no_memory` 可明確提供目前發布狀態，但不得藉此清掉已知較新讀版。
5. **同次原生更新。** C 工具輸出以一個 `Command` 同時加入原 call 的 ToolMessage、所選讀版及新計數。後續工具讀 state 的固定版；初始 system 導覽保持原值，C ToolMessage 明示本輪 source 與刷新 head／guide。這是原生 checkpoint 中的讀取選擇，不是第二份 Memory authority。
6. **未知不刷新。** SQL／Store／來源故障、取消、GraphInterrupt、保存結果未明：保留原 binding／request，交既有停止與原結果查回；不能宣称未发布、不能把猜測 head 發給下一模型。查回證明原 C 已成功時，固定原 receipt 的 applied head；查回當下看到的較晚 B 只作未倒退核對，不成為本輪讀版。

## 模型參數與兩次可修失敗

- 公開工具只需要 `edits: list[MemoryEdit]`；每项只有既有 `path`、`diff`。沿核心 1–8 項、合計 12000 diff 字元、兩條既有路徑限制。operation／source／base／版本／計數由 App 與 `ToolRuntime` 注入，不交模型填写。
- `invalid_edit`、`stale`、`no_memory` 沿已驗政策累加一次。第一次 `retryable=true`，第二次 `false`；達 2 後直接回配對原 call 的 `repair_limit`，不執行 C，也不再增加。成功不重置本輪已用次數；下輪才歸零。
- **原生參數驗證也計數。** C BaseTool 設固定安全 `handle_validation_error`；wrapper 收到其 error ToolMessage 時，转成同一更新計數的 Command。若只在 C 函式 body 計數，非法 `edits` 根本進不了 body，會繞過限額。保留 call ID／error status，不輸出 kwargs、原 diff 或 `str(error)`。
- 不把未知工具、來源失敗、發布未知、取消或保存故障歸入模型可修次數；那些沿原 run 失敗出口。原 request 查回／重複結果不能再次增加同一原 call 的次數；以原生已保存 call／result 判斷，無需另建計數表或重試引擎。

## 必要反例與停止條件

| 固定情境 | 必須觀察到 |
|---|---|
| 初始 1 → C applied/read 2 → B 3 → 同輪 read | 初始 view 仍 1；read 仍 2；下一輪選 3。 |
| C 自己 applied 2，但取結果時 B 已到 3 | 正式 current 保留 3；C ToolMessage／同輪 read 固定 2，之後 B 4 也不自動追；下一輪才選當時最新。 |
| 舊輪 C、錯 source、錯 doc/run、未知發布或不匹配 receipt | 不刷新本輪，不重播 C／Store save／publish。 |
| 第一次 native schema 失敗 → 第二次 patch 失敗 → 第三次呼叫 | 原 call 的 error Message 與計數 1／2；第三次 C 未執行；private marker 不外露。 |
| stale 明示新 head → 讀取 → 第二次重作有不同 patch | 先讀新固定版；不自動重送上一 patch；成功仍保留已耗次數。 |
| Command 保存失敗／原 call 查回／下一輪重開 | 未保存更新不冒稱生效；同 call 不重算失敗次數；新輪不沿用舊刷新值。 |

以上是本輪接線的有限驗證清單，尚未執行，不能當作測試通過。框架接點已足以施工；剩餘未決只在主代理最終 ABI、原 C task／保存閉合與這些反例驗證，不再開廣泛 Memory 研究。
