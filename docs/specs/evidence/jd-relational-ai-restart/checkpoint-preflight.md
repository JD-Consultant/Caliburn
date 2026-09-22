# RS-4：新宿主只讀識別原 AI 回合與相容檢視圖

查閱／驗證日期：2026-09-13。範圍：`experiments/jd-relational-app`，延續 `3980689a`；不升級、不連 provider、不操作 PostgreSQL 或宿主。這是新宿主恢復的必要接點，不是已完成整個啟動恢復流程的宣告。

## 1. 結論與本案取捨

採同一 `build_consultant_node` 原生 Agent 工廠建立檢視組合：相同 JD 工具、`ConsultantState`／`ConsultantContext`、`JdNoticeMiddleware`／`AiToolMiddleware`，模型使用只會拒絕執行的 `InspectionOnly`。不另手拼 Agent 節點，也不以 `MessagesState` 簡化圖讀取原顧問 checkpoint。

`AiRunCheckpoints.discover(document_id, dataset_id)` 只讀取目前固定 root，再讀該 root 指向的固定 child；不需要預先知道 run ID。發現原回合後交現有材料驗證。沒有可辨識的 AI 資料才回 `None`；資料損壞或有未辨識的工作一律停止。`None` 不表示 manual gate 空閒，也不證明其他宿主已退出。

這是依原生保存／檢視契約所做的有限 App 接合；沒有新增 run 表、Saver、工作流、模型回覆或資料權威。是否可恢復仍由既有 owner 的真停止證據及原 SQL receipt 決定。

## 2. 官方事實、適用版本與限制

本次核對已鎖定的穩定開源版本：LangChain **1.4.0**、LangGraph **1.2.11**、LangGraph checkpoint **4.2.0**、LangChain Core **1.6.3**；均 MIT。PostgreSQL Saver 本輪沒有執行／升級。以下是這組版本的公開 API 與已安裝官方原碼，不稱為其他供應商內部共同實作。

| 依據 | 官方契約／原碼結果 | 本案映射與限制 |
|---|---|---|
| [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)；已裝 `pregel/main.py:1392`、`:1480` | `get_state` 可指定 checkpoint；`get_state_history` 接受 `before`、`limit`；歷史檢視與執行／重播不同。 | 最新 `get_state` 只作位置索引；以其 config 再讀固定 root。不可用 `invoke(None)` 查回。 |
| 已裝 `pregel/main.py:1145–1265`、`:1433` | snapshot 使用目前編譯圖的 channels/processes 投影；未指定 checkpoint ID 的 latest 路徑會套 pending writes。 | 不把 latest overlay 的值當成已閉合 root。固定 root 與固定 child 由共同材料解碼器驗證。 |
| 已裝 `pregel/_algo.py:600`、`:978` | 不存在於目前圖的 PULL node 不形成 task；未知 pending Send node 會警告後略過。 | **只有 state 欄位相同仍不夠**，不相容節點布局可能隱藏原待執行工作。檢視圖由相同 factory 產生。 |
| 已裝 `checkpoint/memory/__init__.py:333–376`；公開 `get_state_history` | 主 config 帶 checkpoint ID 會只篩該筆；`before` 限位置；`filter` 查 metadata，不查 `jd_ai_run` channel。 | 查舊 run 時使用明示 document/root namespace、固定 `before` 和有限 `limit`。不得把 record 放 metadata filter，或誤以為帶 checkpoint ID 就取得整段歷史。 |
| [BaseChatModel 公開介面](https://reference.langchain.com/python/langchain-core/language_models/chat_models/BaseChatModel)；已裝 `chat_models.py:284–330` | 子類實作 `_generate`、`_llm_type`；async hook 可明確實作。 | `InspectionOnly` 是執行禁用守門，不是假裝可回答的模型；sync/async 一律 `execution_disabled`，不建立 SDK 或讀 key。 |
| [自訂 middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)；已裝 `agents/factory.py:263–280`、`:661`、`:720` | model/tool wraps 可以不呼叫 handler；第一個 wrap 在最外層。`after_model` 是獨立原生節點。 | 最外層 `InspectionGuard` 同時拒絕 sync/async model/tool；`AiToolMiddleware` 保持同 class/node 名，檢視模式在 after_model 入口也拒絕。無未知額外 middleware。 |

原 native START input 的固定讀法沿[前一單位實證](../jd-relational-ai-runtime/initial-checkpoint-probe.md)：只接受 root 的 `next == (__start__,)`、唯一 START task、`source=input`，用公開 Saver `get_tuple(fixed_config)` 核對原四個輸入欄位。不是一般性解析全部 checkpoint 格式或 pending writes。

## 3. 可重現反例

[探針](checkpoint-probe.py)與[原始輸出](checkpoint-probe.stdout.txt)共 **5 組通過**，只用 InMemorySaver。合成模型只在建立測試 checkpoint 時產生固定回覆；檢視不呼叫模型，沒有 provider、DB 或宿主。

原簡化圖固定為 baseline fixture 後再次執行仍 **5 組通過**，見[可重跑版本輸出](checkpoint-probe.final.stdout.txt)；前一份輸出沒有覆寫。

1. 同一 Saver 改用修改前 `3980689a` 的 `unavailable_consultant` MessagesState child，遺失 `jd_ai_run`、bindings、read、model view，原 pending tools／after_model 也消失。材料驗證會拒絕，不應把此失敗當成沒有 AI 工作。主代理接上新 inspection 工廠後，探針改為內建此舊布局的明示 baseline fixture，以免反例依賴已修正的程式；原始輸出仍保留。
2. 改成同欄位但單一不同 node 的 child，完整材料仍在，**child.next/tasks 卻變空**。這證偽「只補 state schema 就足夠」。
3. 提議的相同原生 Agent 工廠配置，能保留原 tools 與 after_model 兩種停點的 messages、view、bindings、read、channel 名稱、task 與 next。手動同名 node 的探針雖也能保留此樣本，但維護另一份布局無必要，未採用。
4. 新回合 START input 已存、下一個 root loop 保存失败時，root.values 仍可能是上一個 terminal run。必須從固定原 START payload 找新 run，不能讀舊值宣告已完成。root 已 idle 但 record 仍 running，也不能推論回合已結案。
5. **只把模型 `_generate` 禁用仍不足**：直接重啟 pending tools 會先到工具體。加最外層 wraps 才能在 handler 前停止。獨立 sync/async 拒絕試驗確認這個界線。

探針最後兩組刻意對隔離 fixture 嘗試 invoke，驗證拒絕；不是「本輪從未 invoke」。純檢視流程沒有 resume。被拒的 invoke 仍可能寫原生 input/error checkpoint，因此正式檢視只使用讀 API，不能把 guard 宣稱為「invoke 完全無副作用」。

## 4. 本輪有限實作與驗證

新增 `inspection_model.py` 的 `build_inspection_consultant_node()`；兩種模型使用同一個 `consultant_context.build_consultant_node`。只有 exact `InspectionOnly` 與 exact 一個 `AiToolMiddleware` 可進檢視路徑，未知 middleware／InspectionOnly 子類一律拒絕；原 ConfirmedChatAnthropic 的 streaming／no-retry／cache 設定檢查保留。檢視路徑用同名 `AiToolMiddleware(inspection_only=True)`，不多造 graph node。

新增 `AiRunCheckpoints.discover(document_id, dataset_id) -> AiRunObservation | None`；和已知 run 的 `observe` 共用 `_observe_current`，每次只有一次 latest locator。原 START payload 與 regular fixed root 的 scope、原話 digest、完整 view／AIMessage 配對繼續沿用原驗證。沒有 record 但還有 messages／view／read／bindings／pending 時不回 `None`。

實際結果：

- 新 discover 驗收先 **11 FAIL**（尚無方法），見[首敗](discovery-first-failure.txt)；完成後與既有觀察／閉合 **63 PASS**。
- 檢視檔初跑 **6 FAIL／13 PASS**：原生 LangGraph 加入 task exception notes，`pytest match` 的字串包含 notes，並非 guard 放行。改檢查 exact exception type、`.code` 與 `str(error)`；未放寬執行條件。
- 最終[受影響檢查](checkpoint-focused-tests.txt) **136 PASS**：19 inspection、17 context、37 tools、11 discovery、52 原 checkpoint。包含真原生同步／非同步的 fresh model、pending tools、pending after_model 六種入口；`_project`／`_session` 呼叫皆為零。
- 另外直接比較 Confirmed provider factory 與 inspection factory 的 node／channel／edge 集合一致；只建立 synthetic key 的配置，不呼叫 provider。固定 child 比較涵蓋完整值及 task 身分／path／error／interrupt。合成 bindings 僅證保存與讀回，不證 SQL receipt 語意。

## 5. 舊請求查回與後續 owner 接合

本輪 `discover` 只識別目前固定位置，**不提供任意舊 run 的查回 API**。原 HumanMessage.id 是 run ID；native add_messages 相同 ID 會更換內容，所以重複舊 ID 不可當成新訪談輸入。

建議後續已有 run ID 的查回走有上限的 native root history：從當前固定 root 作界線、namespace 明示空字串、檢查原 run record／scope／原 HumanMessage／digest；只取可證 terminal 且 root idle 的原結果。相同 run 不同 digest 應衝突；找到舊 Human 卻未取得可信原結果、或耗盡查找上限時，不能建立新 run 或重播。歷史列舉可能含 branch，不是只列 parent lineage；不在此建通用 branch 重建器或新索引表。

以上僅回應讀取與布局缺口。新宿主 OS proof、同文件 gate、原 receipt 查回、ToolMessage 補全、explicit stopped closure 及真正新程序 PostgreSQL 接合由 owner／AiRuntime 單位驗證。沒有查明資料、工具或模型已停止前，不可把 pending 工作自動重播或清空。
