# 框架原始對話、摘要與持久化：小元件資料流核對

> 2026-09-05 · `LLM-Q017 / G4` · **Source review；未選定 Compaction、未授權施工**。
>
> 父層：[框架接力 §3.6](2026-09-05-openai-shaped-memory-framework-composition-research.md#36-資料細節應何時討論已同意順序與完整範圍)；候選狀態：[Conversation gap review](2026-09-05-conversation-compaction-framework-gap-review.md)；有效決策：[register](../current-decisions.md)。
> **最新接續：§7 收斂來源定位、模型讀取與錯誤契約；§1–6 保留底層研究及接法沿革。** 不再將 Owner 必須選唯一保存格式當作 blocker。

## 0. 本輪問題與查證範圍

Owner 要求先找到框架原文在哪裡、摘要如何取得／回傳資料、誰真正寫入儲存，再找可重用小元件與公開擴充點。**不把「替換 messages」直接翻譯成「資料庫原始對話被刪除」，也不把高階元件不完全承接當成必須另建原文資料庫。**

OpenAI 用途與流程沿用既有研究，本輪沒有重新搜尋 OpenAI。只查框架官方開發文件、固定原始碼及相關測試；沒有安裝、呼叫付費模型或執行測試。以下是所讀程式的事實，不是已實測 release 組合。

固定來源：Deep Agents `4e5f9350e4d77b8bf19e472e8414662d3fa59dc0`（同既有研究，pyproject 為 `0.7.13`）；LangChain `8215039dea978372bd3fd95b88663a11b0159043`；LangGraph `81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1`；LangMem `f8c7ebd6110c124a36995dab645a8cb0eb0b8210`。新取得的 LangChain／LangGraph commit 是 source snapshot，不等同已安裝／驗證的套件組合。

## 1. 必須分清三種「替換」

| 層 | 實際發生什麼 | 不能因此推論 |
|---|---|---|
| Model request | 改本次送模型的 `messages` | 原 state 或歷史 checkpoint 已刪除 |
| Current graph state | reducer 將目前 `messages` 更新；Saver 保存新 checkpoint | 資料庫所有過去 checkpoint 同時被改寫／刪除 |
| Checkpoint history／其他原始紀錄 | 另外執行刪除、清理或採有不同保留政策的 saver | 一般摘要元件會自動永久保留或永久刪光歷史 |

**官方原始碼：**`add_messages` 收到 `RemoveMessage(REMOVE_ALL_MESSAGES)` 時回傳其後的新列表；這是 reducer，沒有 SQL。[reducer](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/langgraph/langgraph/graph/message.py#L187-L234)

普通 `PostgresSaver.put` 依新的 checkpoint ID／channel version 寫資料；SQL 的衝突更新只針對同一 checkpoint ID。`get_tuple` 不指定 ID 才取最新，指定 ID 可取歷史；`list` 可列舉歷史。`delete_thread` 是另一個實際刪除入口。因此**摘要後最新 state 不含舊訊息，不等於普通 PostgresSaver 的舊歷史也消失**。仍以未刪除／未裁切的保存配置為前提，不推廣到所有 saver。[put/get/list](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/checkpoint-postgres/langgraph/checkpoint/postgres/__init__.py#L112-L402)、[SQL](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/checkpoint-postgres/langgraph/checkpoint/postgres/base.py#L131-L144)

## 2. 摘要元件不是各自去資料庫抓原文

```text
Graph 恢復／更新 thread state
  → create_agent model node 將 state.messages 放入 ModelRequest
  → middleware 取得 messages（不是自行查一份 transcript 資料庫）
      ├─ 計算／選取／摘要 → 改 model request → 模型看到有界內容
      └─ 如另回傳 dict／Command → reducer 更新 state → Saver 保存
```

`create_agent` 的 model node 明確傳入 `messages=state["messages"]` 與 `state=state`；middleware 的額外 Command 與模型回覆交回 graph。因此要問「原文改沒改」，必須繼續看回傳內容、reducer 與 saver，不能停在 summarizer 的一句說明。[factory](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/langchain_v1/langchain/agents/factory.py#L1468-L1489)、[Command 組合](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/langchain_v1/langchain/agents/factory.py#L213-L261)

## 3. 同名摘要元件的實際差異

### 3.1 一般 LangChain SummarizationMiddleware

`before_model` 直接讀 state.messages，選出舊段與近期段，生成摘要，再回傳 `messages=[RemoveMessage(REMOVE_ALL_MESSAGES), summary, ...recent]`。**它會改目前 graph state，不只是本次 prompt；但沒有自行刪除資料庫歷史。** 最新 `get_state` 不是完整原文，歷史回查另走 checkpoint API。[完整方法](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/langchain_v1/langchain/agents/middleware/summarization.py#L398-L436)

內部 `_partition_messages` 是切列表；`_create_summary` 把選中訊息經 token 限制及文字 rendering 後送摘要模型。它們不是原文 repository／reader，且是 private 方法。`trim_tokens_to_summarize` 也代表摘要模型未必看到被移出區段的每個細節，不能把 continuation summary 當無損資料。[內部實作](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/langchain_v1/langchain/agents/middleware/summarization.py#L771-L910)

### 3.2 Deep Agents SummarizationMiddleware：修正前輪誤讀

在**原研究已鎖定的同一 commit**，同步正常摘要路徑已經是：

1. 由 request.messages 與已存摘要事件重建「summary＋未摘要尾段」的有效視圖。
2. 視設定截短工具參數，再選段、處理內嵌媒體，把該段文字 rendering 交給 backend；先前的 summary 不重複存入歷史檔。
3. 重用 LangChain helper 生成摘要。
4. `request.override(messages=summary＋recent)` 只改本次模型輸入。
5. `ExtendedModelResponse(Command(...))` 保存 `_summarization_event` 與 `_summarization_session_id`；**正常摘要不以 RemoveMessage 清掉 state.messages。**

來源：[helper 組合](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/summarization.py#L588-L664)、[有效視圖](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/summarization.py#L767-L848)、[完整同步路徑](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/summarization.py#L1345-L1484)。**async 是處理媒體後，同時進行 archive 與摘要生成，再組模型輸入／event**；不是同步方法那樣先完成 archive 才生成摘要。[async 實作](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/summarization.py#L1569-L1625)

**不能再寫「Deep Agents 一定只剩 summary／recent state，選它必須把原文 authority 搬到 backend」。** 但也不能反向保證所有工具原始 payload 一律留在最新 state：context overflow 支線會把大型尾端 ToolMessage 換成縮短內容／檔案指標，並以同 message ID 回寫；一般工具先前也可能已 offload。人類訊息的正常摘要與工具輸出的 eviction 必須分開核對。[_overflow_clip](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/_overflow_clip.py#L76-L173)

backend history 也**不是完整原始 message object 的無損序列化**：它是 XML 風格文字包在 Markdown 區段，可能包含已截短的工具參數及媒體路徑。預設路徑使用內部 `session_<uuid>`，不是直接 thread_id；同 state 保存的 session ID 會重用。archive 寫入失敗時會警告，但仍摘要，event 的 file_path 為 None；不能稱作「原文存成功才允許壓縮」的強保證。[offload](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/summarization.py#L1190-L1264)、[失敗與 session 測試斷言](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/tests/unit_tests/middleware/test_summarization_middleware.py#L1483-L1614)

測試名稱 `test_summarization_aborts_on_write_failure` 與實際斷言不一致：斷言是仍摘要。**以方法內容及斷言為證，不只看註解／名稱。** 本輪閱讀測試，未執行。

### 3.3 LangMem 的小型公開元件：原事實圖漏列

`langmem.short_term.summarize_messages`／`asummarize_messages` 接收 messages、可選 RunningSummary、model 與 budgets，回傳 `SummarizationResult(messages, running_summary)`；函式本身沒有查 Store、刪 checkpoint 或提交 state 的步驟。RunningSummary 帶摘要與已處理 message IDs，供後續增量摘要使用。[公開 API](https://langchain-ai.github.io/langmem/reference/short_term/)、[函式實作](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/short_term/summarization.py#L337-L496)

`SummarizationNode` 才把函式包成 graph node：預設從 `messages` 讀、往另一個 `summarized_messages` 欄位回傳，並保存 running_summary 的 context。**只有刻意把 input/output key 設成相同，才回傳 RemoveMessage 清掉舊列表。** 這是官方可配置行為，不需要自己發明第二份對話資料庫。[node 實作](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/short_term/summarization.py#L660-L860)

這補足的是元件清單，**不是改選 LangMem**：其 release 較舊、與最新 agent middleware 的組合／tool pairing 尚未實測；不照抄範例舊 model 或舊 agent factory。也不能把 node 預設不同輸出欄位說成所有 graph schema 都自動接好。

## 4. 找到的小元件：可用與不可直接依賴

| 責任 | 已有公開元件／接點 | 邊界 |
|---|---|---|
| 恢復／讀取已存訊息 | graph `get_state/aget_state`、history；Saver `get_tuple/list` | 讀的是該 snapshot 的資料；不是自動全文搜尋 API |
| 訊息更新規則 | `add_messages`、`RemoveMessage`、`Command` | 同 ID 可替換；不是資料庫 delete 指令 |
| 本次模型視圖 | `AgentMiddleware.wrap_model_call`、`ModelRequest.override` | 若另外回傳 Command，仍可同時改 state；兩條路徑分開審 |
| 摘要生成／延續 | LangMem 公開 summary 函式、RunningSummary；整顆公開 summarization middleware | Deep Agents 使用的 `_lc_helper`、`_create_summary` 等 private 接點不當成我們穩定擴充 API |
| 檔案內容讀寫 | `BackendProtocol`、`StoreBackend`、`CompositeBackend` | 統一 I/O，不代表已自動提供 checkpoint→conversation 檔案投影 |
| 取得可分頁文件內容 | backend `read(path, offset, limit)` | 回傳 ReadResult；面向 LLM 的行號等格式由 filesystem middleware 處理 |
| 取得既存文件原始 bytes | `download_files/adownload_files` | 不等於原始 conversation；取出的完整性取決於當時寫入內容 |
| 檔案搜尋 | backend `grep`／`glob`／`ls` | StoreBackend 的 grep 列舉檔案後做文字匹配，非向量檢索，也不查 Checkpointer |

公開擴充依據：[LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom#state-updates)、[Deep Agents backend protocol／wrapper](https://docs.langchain.com/oss/python/deepagents/backends#custom-backends)。底層來源：[BackendProtocol](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/protocol.py#L404-L434)、[StoreBackend read](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L366-L399)、[grep](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L593-L611)、[download](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L689-L719)。

**來源內部也有舊註解：**summary offload 說不用 `read` 因其含行號；但所讀版本 StoreBackend.read 契約已是原始 window＋metadata，行號由 middleware 添加。兩者都能讀檔，但不能據該舊註解定義最新 backend result。研究應追實際 producer／consumer，不照抄一句話。

## 5. 對既有判斷的更正與未決

| Finding | 等級／影響 | 處理狀態 |
|---|---|---|
| `CC-F04`：混淆 Deep Agents request-view 與 state replacement | P1，會錯誤迫使改原文保存者；違反上列固定 source | 更正 gap review §3–5／§8；不把錯誤事實當 Owner 核准的設計 |
| `CC-F05`：把永久 state update 說成資料庫歷史被刪除 | P1，會漏看 Saver history 能力或另造原文副本 | 依 §1 分三層；歷史可查不等於已有方便、低成本、完整 transcript reader |
| `CC-F06`：LangMem 長 Context 能力列為缺少 | P2，漏掉公開 summary 函式／node，過早認定必須自寫 | 補列能力；未核准換引擎 |
| `CC-F07`：把 archive 稱為無損 canonical 保證 | P1，工具截斷／媒體／寫失敗下不成立 | 改稱可深讀的歷史 rendering；完整性逐路徑核對 |

**本輪接續結果：**上述 reader 的官方接點已於 §6 核對；可共用同源 message objects，不需要先新增原文副本。尚未裁決 reader 暴露方式、片段邊界、Compaction 引擎或保留政策，見 §6.5。

### 原輪 Closure（後續進度見 §6）

- Finding：摘要的模型輸入、current state 與 DB history 是三層；已找到實際可重用 primitive，修正先前過早的缺口判斷。
- Status：官方事實與開發接點已定向核對；候選組合仍待審，不是 G5 pass。
- Why：Owner 要求追到底層；同一固定 source 已推翻原研究依據，不是只找到另一個名稱。
- Sources：各節固定官方 source、相關測試與公開開發文件；OpenAI 不重查。
- Affected：本子稿、父層 gap review、官方事實圖、Q017 路由與 register；不改 production。
- Reopen：來源版本／公開 API 或原文保留需求改變、最小驗證提供反證。
- Next：上述原文 reader 接力；之後才完成中間 artifact mapping，再回 Q018。無新付費實驗、無選型或施工授權。

## 6. 接續核對：同源原文如何供 B 抽取與 A 深查

> 2026-09-05；Owner「同意」後的定向研究。沿用 §0 固定 SHA，另讀官方公開 API 與實際 producer／consumer；不重做 OpenAI 研究。以下 **Official fact** 與 **組合建議** 分開，不聲稱整套接線已內建或通過測試。

### 6.1 已保存的訊息：從 graph API 讀，不必另建 transcript repository

**[Official fact]** `graph.get_state/aget_state(config)` 先呼叫 Saver 的 `get_tuple/aget_tuple`，再按該 graph 的 channels 重建 `StateSnapshot.values`。因此一般應取 `values["messages"]`，不是把 checkpoint SQL row／整個 snapshot 當對話。普通 PostgresSaver 透過自己的 serializer 還原 channel values；**不需要應用程式先把 messages 轉成 Markdown 才能保存。** [graph 呼叫鏈](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/langgraph/langgraph/pregel/main.py#L1145-L1266)、[公開 get_state](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/langgraph/langgraph/pregel/main.py#L1392-L1478)、[Saver 解碼](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/checkpoint-postgres/langgraph/checkpoint/postgres/base.py#L377-L389)、[官方 serializer 說明](https://docs.langchain.com/oss/python/langgraph/checkpointers#serializer)。

讀取位置分三種，不能混稱：

| 使用者 | 現成入口 | 拿到的內容／限制 |
|---|---|---|
| A 當輪的 Tool | 注入的 `ToolRuntime.state["messages"]` | 此 Tool 執行時的 graph state；不等於 middleware 縮小後的模型 request，也不承諾任意剛產生的內容都已完成持久化 |
| B 輸入載入步驟／run 外的 reader | 主對話 graph 的 `get_state/aget_state`，使用 Runtime 選定的 conversation config | 已保存的 state；背景自己的 `runtime.state` 不會自動變成主對話，也不能只因共用 Saver 就拿任意 graph schema 讀 |
| 需要先前版本 | 指定 `checkpoint_id` 的 get_state，或 `get_state_history/aget_state_history` | 回傳 snapshots；`before/limit/filter` 是 checkpoint 選取，不是 message 全文／語意搜尋或訊息分頁 |

來源：[ToolRuntime 注入／state](https://docs.langchain.com/oss/python/langchain/tools#access-state)、[history source](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/langgraph/langgraph/pregel/main.py#L1480-L1588)、[Postgres list](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/checkpoint-postgres/langgraph/checkpoint/postgres/__init__.py#L112-L190)。框架提供讀取機制；上述 A／B 的讀取者分配是**組合建議**，不是新存儲 owner。

**讀取 API 不會逆轉前段裁切：**若某 middleware 已將 current messages 換成 summary，ToolRuntime 與最新 get_state 就只會讀到該目前內容；要取原文須讀仍保有原訊息的歷史版本。若採只縮模型 request 的路徑，正常 messages 仍可直接讀。大型 Tool output 若已 offload，也須依其實際保存位置回讀。這沿用 §3，不把所有候選說成無條件可從最新 state 取得完整原始 payload。

**封口與成本細節：**不指定 checkpoint ID 的最新 state 讀取會套用可用的 pending task writes；指定 ID 不走同一個一般 pending-writes 分支，但 snapshot 組裝仍處理 `NULL_TASK_ID` writes。故不能把「取最新 state」直接等同「本批已封口、內容絕不再變」。B 的已完成輸入邊界仍待契約收斂，不自行添加鎖或資料副本。History 實作會先消費所選 checkpoint list；必須區分有界回傳模型與 DB 實際讀取量，不因回傳十行就宣稱只查十行資料。多 snapshot 直接串接還會重複／混入不同版本。[實際 snapshot／pending 邏輯](https://github.com/langchain-ai/langgraph/blob/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/langgraph/langgraph/pregel/main.py#L1228-L1266)

### 6.2 選取、序列化、文字 rendering 是不同小元件

| 公開小元件 | 真正用途 | 不能當成什麼 |
|---|---|---|
| `filter_messages` | 依 name／type／ID 過濾已取得的訊息；保留順序 | 不查 DB、不按語意找段落、不自動補前後問答；多個 include 條件是 OR，不是 AND |
| `messages_to_dict`／`messages_from_dict` | 以 message type＋`model_dump()` 資料輸出／還原框架支援的訊息類別，適用需跨程序傳輸等場合 | 不是新的資料庫，也不代表必須另存 JSON；未知自訂 type 不會自動獲得解碼支援 |
| `get_buffer_string` | 將已選取訊息轉成模型可讀的 prefix／XML 文字 | 不是完整原始 message 的無損 archive；一般 message ID／metadata 不在輸出中 |
| `merge_message_runs` | 合併連續同類訊息；ToolMessage 不合併 | 不是來源分段／逐訊息 identity 保留機制 |

來源：[filter 實作](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/core/langchain_core/messages/utils.py#L857-L998)、[dict 序列化](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/core/langchain_core/messages/base.py#L474-L498)、[dict 還原](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/core/langchain_core/messages/utils.py#L515-L557)、[文字 rendering](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/core/langchain_core/messages/utils.py#L287-L511)、[merge](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/core/langchain_core/messages/utils.py#L1002-L1127)。

**與「保留細節」直接相關：**XML rendering 對一般純文字／text blocks 不在此步摘要，但會跳過 base64／未知 block，並截短 `text-plain` document、server tool args/results 至 500 字元。這是特定資料型態限制，**不是所有員工文字都只保留 500 字**。因此應保留原始 message objects；面向模型時再依用途選取及呈現。檔案 URL／file ID 仍只是引用，序列化不保證外部附件永久可讀。[content block formatter](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/core/langchain_core/messages/utils.py#L142-L244)

### 6.3 抽取元件確實共用輸入，不另查一套原文

**[Official fact]** LangMem 公開匯出的 `create_thread_extractor` 接收 `input["messages"]`；內部 `utils.get_conversation` 先用 `merge_message_runs`，再串接 `pretty_repr()`，包在 conversation prompt 內交給 Trustcall extractor。沒有以 thread ID 自動查 Checkpointer／Store 的程式。[公開匯出](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/__init__.py)、[完整 pipeline](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/knowledge/extraction.py#L113-L182)、[內部 formatter](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/utils.py#L98-L101)

故它能接同源訊息做抽取，但不能稱「原始訊息與所有引用逐欄原封不動送模型」。`get_conversation` 在此只是內部 formatting helper，不把它提升成我們依賴的持久 reader；也不為補 ID 就要求 LLM 重填完整對話。來源定位與片段範圍由 Runtime 接合的具體方式尚待核准。這補充 [artifact 詳表 §5.4](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md#54-langmem-create_thread_extractor)，不改選抽取模型或 schema。

### 6.4 `StateBackend` 不等於對話 reader；公開擴充能接同源資料

**[Official fact]** 固定版本 `StateBackend.read`／grep／download 都取 graph 的 **`files` channel**，不讀 `messages`。它必須在 graph 執行 context 內使用，內部透過 Pregel 私有 config read/send 接 state；這是套件自己實作其公開 BackendProtocol，不代表應用也應複製私有實作來讀訊息。[StateBackend 完整 source](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/state.py)

`CompositeBackend` 依最長 path prefix 路由，再將 path／offset／limit 交給選定 backend；它不自動把 messages 轉成 files。官方 `BackendProtocol` 可接 database 等既有資料來源，`read` 回傳結構化 ReadResult，開發者可自行映射資料，而非必須複製存儲。[路由 source](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/composite.py#L195-L291)、[read 委派](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/composite.py#L391-L418)、[官方 backend 擴充契約](https://docs.langchain.com/oss/python/deepagents/backends#custom-backends)

因此有兩個可討論的公開接法，**均不是現成的完整 checkpoint transcript plugin**：

- **直接 reader Tool**：用 ToolRuntime／graph 公開讀取拿訊息，選取相關原始問答，作為這次 Tool 的資料結果回給 A。B 的輸入載入步驟共用同一讀取邏輯，不需要向模型再發一次 Tool call。優點是保留 message 結構直接處理；需要接合定位、窗口與結果呈現。
- **唯讀檔案投影**：沿 BackendProtocol 將同源訊息呈現為可 read／list／grep 的虛擬文件，復用 FilesystemMiddleware 工具；不是另存原文。優點是模型沿用檔案操作，代價是要實作 path 映射、穩定分頁、唯讀政策及 sync／async 接點。這是官方擴充方式支持的**組合推論**，不是已找到內建 conversation backend，也不宣稱零自訂。

兩者可共用來源但不必共用相同模型輸入：A 得到有界引用片段；B Phase 1 得到已選定抽取範圍；Compaction 得到其自身 token 視圖。**B Phase 2 仍只可補查 summary，不因共用 reader 就擴權讀原始對話**，沿用 [B §3.2](2026-09-05-memory-background-cycle-flow-review.md#32-consolidation對照現有內容不是候選逐筆照存)。

### 6.5 前輪結論、未決與 closure（接續見 §6.6）

- **Finding／Status：**現有框架已提供保存、state/history 讀取、訊息轉換、ToolRuntime 與 backend 擴充；共用同源原文在公開接點層可行。尚未作相容性／大對話成本測試，不宣稱端到端已完成。
- **Why：**高階摘要／抽取元件的「原文輸入」實際由呼叫者提供，不存在因每個 consumer 就必須各存原文的理由；`files` 與 `messages` 更不能只因都在 state 就視作同物。
- **Sources：**§6.1–6.4 固定 source 與官方公開開發資料；沿用既有 OpenAI 用途，不重新搜尋。
- **選擇仍未決：**直接 reader Tool 或唯讀檔案投影、抽取片段／來源 locator、Compaction 具體接線。未新增第二份原文、未改保留政策、未決定原始對話 semantic index。
- **接續建議：**先把此二選項保留到下一項 extraction artifacts 一起審閱，確認 summary／候選的保存與引用接力，再選最少失真的共用讀取方式；不再重問原文在哪、原生摘要是否自己查 DB。Q018 仍待完整 A/B/C 接力。
- **Affected／Reopen：**本子稿 §6、父層路由、artifact §5.4 與 register；官方 API／原文保留效果改變，或最小驗證提供反證才重開。僅研究文件，無程式、測試、付費模型、spike、commit 或 push。

### 6.6 接續討論：原文共用讀取，模型入口建議先採直接 Tool

> 2026-09-05 · **流程／回查效果已獲 Owner 暫時同意；直接 Tool 是可調整的接法建議，非指定實作**。最新邊界見[流程稿 §0.1](2026-09-05-work-understanding-memory-flow-working-design.md#01-owner-澄清流程效果必須達成實現方式不鎖死)。本節補原始問答 reader，不重開完整對話保存者，不把詳記當原始問答，也不改 A/B/C；以下保留提出建議時的查證。

**Preflight：**`LLM-Q017 / G4`；本輪比較 §6.4 已有的兩種原文入口。已回讀本稿全文、current register／decision-process、單一訪談流程與抽取產物引用研究。重新讀官方 Checkpointers、Tools、Backends 開發頁；固定原始碼細節沿用 §6.1–6.4，沒有重新下載最新 HEAD。未決 Compaction 引擎、Q018、原始對話索引、production 均不在本輪選型範圍。

**[官方能力]** `get_state(config)` 可讀最新或指定 checkpoint 的 snapshot，`get_state_history` 回傳的是歷史 snapshots，而不是訊息分頁；`ToolRuntime` 可注入 state／可信 context，不進模型參數 schema。BackendProtocol 可擴充其他來源，但已查的 StateBackend／StoreBackend 不會自動讀 messages。[官方 checkpoint 定位](https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state)、[history](https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state-history)、[ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools#access-state)、[backend 擴充](https://docs.langchain.com/oss/python/deepagents/backends#custom-backends)

| 原文入口 | 能達到的效果 | 代價／何時更適合 |
|---|---|---|
| **直接 Tool（本輪建議）** | A 依已提供來源位置讀原始問答；B1 載入步驟直接重用底下的 graph reader | 需接合來源解析、問答窗口、長結果續讀與錯誤；沒有原生通用 transcript Tool 可直接宣稱完成。適合目前「沿詳記引用回查」用途 |
| 唯讀檔案投影 | A 使用既有 read_file；原文仍來自同一 graph，非副本 | 需實作 checkpoint→path／文字／穩定行分頁及唯讀 backend；原生 formatter 可重用。若日後確有原文目錄／grep 或統一檔案入口的需求，可更合適 |

**推薦理由是效果與接點相符，不是只比少寫程式：**原文不是已存在的 FileData；保留其 message objects 與問答順序，直接讀取較少經過另一次合併／文字重排。兩案都需要正確窗口與定位，不能以 Tool 名稱宣稱避免全部遺漏；也不能宣稱這是 OpenAI 唯一共識。中間摘要②原生檔案的推薦不因此撤回，因為那類內容本來就是可讀的整理文字。

**[接力設計：目的已同意，精確契約待收斂]**

1. Runtime 選取同一份主訪談已保存的訊息範圍，B1 透過主對話 graph 的公開 reader 取得 message objects；不使用背景 Agent 自己的 state 冒充主對話，不依賴 model request 的壓縮視圖。
2. 抽取詳記／候選成功後，Runtime 將本次真正讀取的來源位置附在產物上。主對話身份、需要時的 checkpoint 與訊息範圍，來自實際 reader 結果，不讓模型捏造。**這是本批輸入位置，不保證精準指出詳記每一句對應哪句原話。** 精確 locator 表示與已完成輸入邊界仍待收斂，不新增引用資料庫。
3. A 開詳記後若需要原話，將已提供的來源位置帶回原文 Tool；Runtime 在目前文件 scope 下解析，取得相關問答並有界呈現。不是叫模型猜歷史 ID，也不是另叫一個模型把原文摘要後當逐字來源。
4. B1 共用的是底下讀取邏輯；程式直接取得資料，**不為此額外讓 LLM 呼叫讀取 Tool**。A 因按需查證而呼叫 Tool，之後模型接收結果的 request 仍有 token 成本。B2 仍只補查摘要，不因此獲得 raw reader。

**需一併守住的邊界：**

- `source` 指向保存的問答，不只抽員工回答。例如「AI：例外也由你核准嗎？／員工：不是，主管核准」必須保留問句才能正確解讀；需擴展時由模型依返回內容再要求上下文，不假裝框架自動解決所有指涉。窗口／續讀格式未在此寫死。
- 摘要後最新 state 是否仍有原文，取決於採用的 middleware；無原文時須讀仍保留它的 snapshot，而不是把 summary 冒稱原句。多個 snapshots 不可全部串接當 transcript；`get_state` 查閱不等於 invoke/replay，不應重跑訪談來讀原文。
- 來源找不到、已被清理或不屬於目前文件時，明確回報無法讀取；不要退回「最新但不同的片段」冒充成功。實作前須驗證原文保留／定位與 Compaction 組合。官方也提醒 checkpoint 保留策略影響可讀歷史；這輪不新增清理或永久保存所有中間快照的政策。[官方持久化與保留注意事項](https://docs.langchain.com/oss/python/langgraph/persistence#checkpoints-growing-unboundedly)
- 傳少量內容給模型，不代表 DB 只查少量訊息；目前 graph reader 可能還原整個 snapshot。是否需 DeltaChannel 等官方儲存優化留到規模／相容性核對，不能為了這輪原文入口偷偷換 channel 或另外建立 transcript store。

**Closure（Owner 補充後）：**依已同意目的繼續細化「共用 graph reader＋A 的直接 Tool」研究接法；不再要求 Owner 選定唯一入口形式，效果等價替代依流程稿 §0.1 記錄取捨。來源位置、窗口與角色分配仍是依公開 API 的接合設計，不是內建完成的通用原文服務；須連同原文／Compaction 保留問題收斂契約，不宣稱已驗證可用。不重問是否保留原文、是否使用兩份 Memory。沒有程式、模型測試或施工。

## 7. 原文回查契約：來源定位與有界讀取

> 2026-09-05 · Q017／G4 接續設計；依 [Owner 等價實現原則](2026-09-05-work-understanding-memory-flow-working-design.md#01-owner-澄清流程效果必須達成實現方式不鎖死)細化，**不是 OpenAI 的原封 schema，也不是已實測完成**。

**Preflight：**問題限於「已存詳記如何可靠讀回其原始問答」。已完整回讀 register、decision-process、單一訪談流程、本稿、產物接力及原生 backend 審閱；官方用途沿用既有 OpenAI 研究，不重搜。Compaction 選型、B 觸發／重跑、C 寫入與 Q018 協調不在本節裁決。

### 7.1 來源位置採框架身份＋實際訊息範圍

**[Official fact]** LangGraph 的 `StateSnapshot.config` 帶 thread／checkpoint namespace／checkpoint ID，`values` 才是資料；指定 checkpoint 的 `get_state/aget_state` 是讀取，不是 replay。官方另有 `next/tasks` 描述執行狀態，不能將模型文字輸出完成直接當成背景輸入已封口。[官方 snapshot／讀取／replay](https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state)

**[本案接法]** 延續共用 graph reader，保存來源定位時採「**Runtime 選定、確實可讀的主訪談 checkpoint＋實際輸入的訊息範圍**」。引用跟著詳記／候選保存；不另存原文副本或新建來源資料庫。訊息使用其既有 identity，範圍由程式根據真正取得的 message objects 記錄，不由 LLM 猜 ID、時間或中文字元位置。

| 方案 | 對本用途的判斷 |
|---|---|
| 只有 thread，回查一律讀 latest | 不足以定位哪次抽取的哪段問答；只適合作取得目前狀態的入口 |
| **選定 checkpoint＋訊息範圍（設計基線）** | 可按當時位置重讀；使用框架既有身份，不自建版本系統。代價是來源所依賴的 checkpoint 必須可讀 |
| 持久原文檔案／另一份 archive | 未有新需求足以推翻 MEM-Q001，不採；既有唯讀檔案投影只是 reader 替代，不是此種原文副本 |

精確字串編碼不是本輪產品裁決：可將定位封裝為可原樣帶回的 reference，不讓模型分別組裝 RunnableConfig。持久引用不能只存在某次 run 的暫存對照表；解析仍受當前文件 scope 限制。首尾範圍／必要舊脈絡須反映真正輸入，**不宣稱每個候選句子都有精準 quote 對應**。這是官方身份 API 的應用接合，不是宣稱 LangGraph 自動產生抽取 provenance。

**封口接點尚須與 B 生命週期一起收斂：**背景不能任意讀 ongoing latest 並標成完成輸入。所查 source 對未指定 ID 的讀取會合併一般 pending writes；指定 ID 也不代表新的不可變 archive 保證。這裡只確立用可讀來源定位，不提前決定在哪個 callback／stream event 交接或新增鎖。[既有 §6.1](#61-已保存的訊息從-graph-api-讀不必另建-transcript-repository)

### 7.2 模型要填什麼、拿到什麼

**[Official fact]** `ToolRuntime` 可由框架注入，不暴露在模型 schema；一般 Tool 結果可回成模型可見內容。`ToolMessage.artifact` 不送模型，因此不能把下一步需要的引用只放在 artifact。[Tools](https://docs.langchain.com/oss/python/langchain/tools#access-state)、[Messages](https://docs.langchain.com/oss/python/langchain/messages#tool-message)

**[接法契約；不是新增一套錯誤協定或鎖定欄位名]**

- **模型輸入：**讀取先前已提供的來源 reference；內容未完時，使用結果提供的續讀位置。文件 scope、主訪談身份、DB 配置與預設預算由 Runtime 管理，不要求模型重填。
- **Tool 回傳給模型的內容：**相關原始問答、角色、實際讀取範圍，以及是否還有內容／如何續讀。這些由 reader 產生，不由 LLM 重填。若引用只是某批輸入，明示其粒度，不將整份摘要的 source 說成逐句來源。
- **問答脈絡：**讀到員工「不是，主管核准」時需呈現相關 AI 問句；按原始順序呈現，不能只 filter human messages。模型若仍遇到「剛才那個」等不明指涉，可要求鄰近脈絡；沒有 framework 自動解決語意指涉的保證。
- **歷史是資料：**A 收到的是本次 Tool 的歷史內容，不把舊 AI 問句／Tool calls 當成當前指令再執行。B1 則在程式載入步驟直接使用同源資料，不多安排一個 reader LLM。
- **短內容直接完整回傳；長內容分段。** 不另叫模型把待核實原文摘要一遍。若單則訊息太長，也必須提供剩餘部分的讀取方式，不能靜默略過或卡在永遠空的一頁；offset 等位置由程式算，不讓模型算 quote start/end。

詳記仍重用官方 filesystem reader；其窗口及續讀已在[backend 審閱 §1](2026-09-05-memory-artifact-native-backend-design-review.md#1-框架底層真正如何接力)查清。**直接 message reader 不會自動繼承檔案分頁**，需接合上述窗口；不依賴 private formatter。`trim_messages` 可限模型輸入，但不是會回傳原文續讀位置的 reader，不能單獨當成完整回查實作。框架 API 有 `allow_partial` 與文字切割選項，不代表已完成本案續讀契約。[官方 trim_messages](https://reference.langchain.com/python/langchain-core/messages/utils/trim_messages)

### 7.3 「未讀到」不能被誤判為「不存在」

**新增底層核對：**固定 LangGraph source 的 `_prepare_state_snapshot/_aprepare_state_snapshot` 在沒有 saved checkpoint 時回傳 `values={}`、`metadata=None` 等空 snapshot。故「呼叫沒拋例外」不足以表示來源存在；讀取端須確認保存狀態與要求的訊息實際存在。這不是新增語意 verifier，而是正確使用官方讀取回傳。[固定 source：get_state 與 snapshot preparation](https://raw.githubusercontent.com/langchain-ai/langgraph/81bf17b23123e4ef8b9d5f49fa09a0122fc2edd1/libs/langgraph/langgraph/pregel/main.py)

| 情況 | 回傳／恢復責任 |
|---|---|
| 成功但只讀一部分 | 顯示實際片段與續讀方式；不得標成已讀完整來源 |
| reference／訊息範圍無法解析，或不屬於目前文件 | 以既有 Tool error 路徑說明不能讀取；模型可從已讀詳記重新取得 reference，不得猜另一份文件 |
| checkpoint 或目標訊息已不可得 | 明確是「此來源目前不可讀」，不退回最新末尾或摘要冒充原文，也不斷言員工沒說過 |
| DB 暫時失敗 | 沿既有 bounded infrastructure retry／failure 規則；不要求模型捏造另一個來源 ID，也不新增無限重試 |

錯誤使用 LangChain 官方工具執行／middleware 接點，沿用 Q014 已有分流；上表是訊息含義，不另訂平行狀態機。[官方 Tool error handling](https://docs.langchain.com/oss/python/langchain/tools#error-handling)

### 7.4 驗收與剩餘 gate

以下是**待實作時的機制檢查，不是已執行測試**：

1. 前半段詳記建立後再增加多輪對話，同一 reference 仍回到前半段；不誤讀 latest 尾段。
2. 經選定 Compaction 組合後，B1 與 A 仍能讀回引用範圍；整理摘要與 middleware 標記不得冒充員工原句。
3. 回查包含必要問句與回答；長中文訊息多次續讀能覆蓋原內容，不靜默遺漏／重複跳頁。
4. 換文件、無效／已清除 checkpoint、訊息不存在時均不偽裝成功；關閉重開後引用仍可解析。
5. 原文回查不呼叫新的摘要模型、不 replay 訪談、不另寫原文庫；B2 沒有因此取得 raw Tool。

**成本限制：**回傳有界不代表 DB 讀取有界；graph reader 可能還原整個 snapshot。來源定位避免為已知引用遍歷全部 history，但不能保證大型 thread 的固定成本。原文保留與 checkpoint 儲存成長須在下一項 Context／Compaction 接線一併處理；`DeltaChannel` 是另有版本／beta 條件的官方優化，不由此自動採用。[官方儲存成長與 DeltaChannel 注意事項](https://docs.langchain.com/oss/python/langgraph/checkpointers#optimize-checkpoint-storage)

**Closure：**本節形成可繼續設計的來源讀取基線；不用 Owner 再選唯一 reference 格式。用途不變，沒有新增原文 store／embedding／Agent。下一個 gate 是把來源保留接到非破壞性的 Context／Compaction，再收斂 B 生命週期及 Q018；不宣稱整體 Memory 已完成。

**查證紀錄：**本輪重新讀官方 Checkpointers、Tools、Messages、Backends、custom middleware 頁及上述固定 `pregel/main.py`。終端下載被網路拒絕，改用 web 取得該固定 source；未抓最新 HEAD。部分 API reference 頁直開失敗，`trim_messages` 參數由官方搜尋結果全文及既有來源交叉核對，未當成執行證據。只更新研究／指路；未安裝套件、執行框架／付費模型測試或 production 施工。
