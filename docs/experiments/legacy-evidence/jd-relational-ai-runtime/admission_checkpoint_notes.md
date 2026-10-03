# JD 工具寫入前原生 checkpoint 接點核實

查閱／實測：2026-09-13。限定 LangChain 1.4.0、LangGraph 1.2.11、checkpoint 4.2.0；皆沿本 App 已鎖定的正式 MIT 套件，不升級或另裝。這是隔離接法研究，不是實際 AI writer、PostgreSQL 或 provider 驗收。

## 推薦

使用原生 `after_model` 節點保存一筆完整操作綁定；宿主明示 `durability="sync"`，待原生下一步進入 `wrap_tool_call` 後，才能以已綁定的原 `BoundEdit` 呼叫共用 `JdStorage`。不在 active child 另外 `update_state` root，也不新增 run／binding 資料表或模型工具迴圈。

這是本案映射：模型提供工具名稱、業務參數及原生 tool-call ID；App 持有文件／dataset／run、原 AIMessage ID、原 tool-call ID 與 `BoundEdit.identity` 的七欄。既有 identity 包含 document／operation／base／origin／ai_run／digest／command kind，不能用單一 call ID 代替。AI 原始回覆已由原生 messages 保存，不另存一份對話。可序列化的 identity 與消息識別進 native state；含 callable 的 `BoundEdit.context` 保留於同一實際 owner 的本次執行記憶體，不能假造可恢復 candidate。

## 官方事實與精確 code path

| 接點 | 已核事實與本案限制 |
|---|---|
| [LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom) | Node-style hook 回 dict 更新 state；`after_model` 是獨立節點。沒有列出 `before_tools` hook。wrap-style 的 `wrap_tool_call` 可零次／一次／多次呼叫 handler，因此「只呼叫一次」由本案負責。 |
| 已裝 `langchain/agents/factory.py:1599–1621,1663–1729,1787–1801` | `model → after_model → tools`；多個 after hook 依 middleware 反向順序執行。綁定 hook 應位於其他允許改寫工具呼叫的 hook 之後，且之後不得修改已綁定意圖。最小組合只增加本案一個 after hook。 |
| [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | `sync` 在下一步前保存；預設 `async` 可讓下一步先開始。`pregel/main.py:2862–2865` 傳遞 durability 給 child，`:2960–2988` 在步驟切換等待 Saver future。`Command` 回傳 state update 本身不是 SQL 前的保存屏障。 |
| 已裝 `factory.py:1923–1967`／`prebuilt/tool_node.py:1014–1069` | 每筆未完成 call 使用 native `Send("tools", [call])` 分派；wrapper 取得 tool-call、state、runtime，更新需回 `Command`。單靠 wrapper 先建立 binding 再呼叫 SQL、最後回 Command，無法使前兩者之間產生 checkpoint。 |
| 已裝 `prebuilt/tool_node.py:383–391,1054–1068` | 預設只將 invocation 錯誤轉成 ToolMessage，execution 例外重拋。unknown 若被包成普通 ToolMessage，原生工具迴圈會再進模型；本案應保留原 binding 並以固定執行例外停止，不能吞成一般可重試錯誤。 |
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#how-it-works)／[Anthropic handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls) | 兩家均要求實際工具結果對應原呼叫：OpenAI `call_id`，Anthropic `tool_use_id`。它们是對話配對，不是本案 DB 冪等或 writer 權限。Anthropic 還要求結果緊接原工具呼叫；保留 native ToolMessage mapper，不捏造 HumanMessage。 |

AWS 冪等依據沿已核的 [Builders Library](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)：原 key／原意圖／原結果及 mutation＋receipt 同交易由既有保存層承擔。本次沒有新缺口需要擴大 AWS 搜尋；checkpoint 先記 admission 並不使 Saver 與 JD SQL 變成單一交易。

## 必須由實際 owner 接好的流程

1. graph invoke 前完成文件／run 准入，同文件人工与 AI 共用原 gate。root/child 都宣告 binding 欄位，但 active child 的未完成內容先在 child namespace，不能依賴 root 提前收到。
2. 完整模型回覆保存後，`after_model` 核原 AIMessage／tool-call scope、數量、既存 pending；用正式讀取／source 接點一次取得材料、`bind_edit` 固定意圖，產生 App operation UUID。此步不呼叫 SQL mutation。LLM 不補填這些欄位。
3. sync checkpoint 成功後 wrapper 核 call／run 與原綁定一致，取同 owner 中已凍結的 `BoundEdit` 執行一次。沒有原 live candidate 時不能重新解析來源或生成新 digest 後宣稱原操作重試；恢復走 candidate-free identity 查回。
4. 已確認結果使用既有 observation projection，回原 call 的 ToolMessage；可由同一 tools-step `Command` 更新 binding 關閉狀態。未確認結果保持原 identity 並停止當前圖，不再讓模型發新 operation。確認 SQL 與 ToolMessage checkpoint 仍可能分開失敗。
5. 停止後恢復先查固定 root 的 task.state，再定位固定 child checkpoint；仍沿先前 pinned 規則避免 pending-writes overlay。只查原 receipt／必要時在實際退出證據下 `reconcile_stopped(identity)`。本探針不執行 graph resume、promotion、模型重播或 SQL 重播。

實作限制：native 工具分派可以並行，第一個寫入版本宜在 after_model 明確拒絕未支援的多工具寫入組，而非只相信 provider 的平行設定。`before_tools` 不是現有公開 hook；`before_model` 已晚於工具，不適合作為這次 admission 屏障。不要用 `Command(goto=END)` 猜測會取消既有 tools→model 路由，若要其他收尾方式須另做有限原生證明。

節點內 `get_config().configurable.checkpoint_ns` 可能包含目前 node/task namespace；它不等於 Saver 的 child checkpoint namespace。不得以此直接猜地址或自製拆字串規則。宿主恢復使用原生 task.state 的 config；探針為檢查次序，直接記錄 native `put` 收到的 namespace，不是新增 production namespace 產生器。

## 五個可重現結果

[探針](admission_checkpoint_probe.py)／[原始輸出](admission_checkpoint_probe.stdout.txt)使用真 `create_agent`、compiled root/child、InMemorySaver 與本 App `bind_edit`；synthetic 工具只計數 SQL 邊界，從未連 DB。

| 情境 | 結果 |
|---|---|
| sync 正常 | binding 保存 → 工具，工具入口核持久原 identity；一個工具、兩次固定模型回覆。 |
| binding put 前失敗 | 0 工具，固定 child 尚無 binding；不自動重播 after_model 或模型。 |
| binding put 後 ACK 遺失 | 0 工具；固定 child 保留完整原 identity，root 仍有 pending task。 |
| 工具執行邊界後 unknown | 1 工具、1 次固定模型回覆；原 binding 保留，沒有續叫模型。 |
| async 反例 | 工具先於 binding 保存；證偽沿用預設模式足以滿足本案要求。 |

首輪探針有兩個測試用法錯誤：command 錯用 `input` 而非既有 `arguments`，以及把 after_model node config 的 namespace 當作 child Saver namespace。修正探針後五例均 PASS；這兩敗不冒稱產品故障。版本確認與所有輸出均是本機合成，0 provider、0 DB、0 resume。

未證明的必要下一驗收：真 PostgresSaver 保存／ACK 故障與新程序重開；實際同文件 owner／Win32 停止證據；shared JdStorage 真 transaction/result unknown；provider 原始 call／message完整性與零或一工具 enforcement；invalid/source不可用的 binding前拒絕；完整恢復後如何結束或續談。這些沒有因原生 ordering PASS 就自動完成。
