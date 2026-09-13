# JD 顧問 context 與人工變更通知：RS-4 前置

查閱日期：2026-09-13。範圍：JD-R002 已核准的隔離 App；只收斂人工通知、模型回覆保存與既有 Memory／來源的接點。本文不是 production 採用或真模型驗收。

## 1. 結論與現況

**採當次 request 的 App context 投影，保留原始對話；把通知邊界與實際模型回覆一同持久化後，才前進基準。**模型收到「哪些保存事件可查」不等於讀完所有 JD、理解全部差異或接受改動；`last_model_view` 沿既定命名，但語意是有回覆依據的通知邊界，不能當內容 read receipt。

責任沿[工具契約 §8–9](../2026-09-12-jd-relational-agent-tool-contract.md#8-人工修改如何進下一輪-context)、[施工 RS-4](../../plans/2026-09-13-jd-relational-app-implementation.md)。程式現況：[DocumentState](../../../experiments/jd-relational-app/src/jd_relational/runtime_checkpoints.py)只有原生 `messages` 與 `jd_manual_pending`；[manual runtime](../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py)已有文件所有權與人工保存恢復，**未接模型通知基準、自然顧問或正式 Memory**。共用 Saver 不代表子圖任意欄位自動成為根圖權威。

| 核對對象 | 本機版本／狀態／授權 | 本輪可證明的範圍 |
|---|---|---|
| LangGraph／checkpoint／PostgresSaver | 1.2.11／4.2.0／3.1.2，穩定套件，MIT | new app lock 與已安裝原碼；原生 checkpoint 接點 |
| langchain-core | 1.6.3，穩定套件，MIT | `MessagesState` 等共同格式；不等於已安裝 `create_agent` |
| `langchain`／`langchain-anthropic` | **new app 尚未選定或安裝** | 現行官方 middleware 是候選，未驗其精確相容版本 |
| Anthropic SDK／OpenAI SDK | 1.5.0 MIT／3.13.0 Apache-2.0，鎖在 dev | 離線 SDK 格式與本次合成串流探針；不是 provider／模型通過 |
| Claude Messages／OpenAI Responses | 現行官方服務文件，商業服務契約 | 公開 request／tool／stream 能力；不推測產品內部實作 |

版本來源為隔離 App [pyproject](../../../experiments/jd-relational-app/pyproject.toml)／[lock](../../../experiments/jd-relational-app/uv.lock)及安裝套件 METADATA。框架選用仍依需求與證據，沒有「已安裝所以優先採用」結論。

## 2. 官方事實

### Anthropic：分清 request 角色、工具結果與內容信任

- Messages 支援由 App 提供多輪輸入；top-level `system` 是正式介面。不能假設 Claude 存在 OpenAI 的 `developer` role。一般 API 說明仍有「messages 無 system」文字，但同頁型別已列 system，必須連同下列專頁解讀。[Messages API](https://platform.claude.com/docs/en/api/http/messages/create)
- **現行專頁明示 Opus 5 等指定模型支援 mid-conversation system，無須 beta header**；Sonnet 5 不支援，仍用 top-level。`clear_at`、動態 tool changes 及 per-message effort 各有額外 beta 條件，不得合稱全部穩定或全部 beta。專頁直接舉 App 發現檔案改動等狀態通知；亦警告不可把外部工具／文件內容提升成 system 指令。[Mid-conversation system messages](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages)
- 真實工具結果以 `tool_use_id` 配對，在對應 assistant 呼叫後接 user 的 `tool_result`；有錯誤可用 `is_error` 並提供可採取動作。工具結果不應被當成 system 文字，通知也不能靠捏造 tool call／result 注入。[Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- 串流有完整事件順序，以 `message_stop` 結束；HTTP 成功後仍可能出現 error。部分 tool／thinking blocks 不能當完整回覆使用。`tool_use` 是正常 stop reason，不必等整輪顧問沒有後續工具才承認一個模型回覆。[Streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)

### OpenAI：輸入與工具結果的正式契約

App 可整理當輪輸入；自行維護 conversation state 時須保留適用的完整 response output 與原生 reasoning／phase，不能只重送 `output_text`。[Conversation state](https://developers.openai.com/api/docs/guides/conversation-state#manually-manage-conversation-state)

模型提出工具呼叫、App 執行並按 `call_id` 回傳結果；已知參數交程式提供，結果可帶 JSON／錯誤。`parallel_tool_calls:false` 將單一回覆限制為零或一個工具呼叫。[Function calling](https://developers.openai.com/api/docs/guides/function-calling)

**兩家共同支持的是 App 管理輸入、真實工具結果與角色分工。**本文的 `last_model_view`、通知格式及 checkpoint 前進條件是本案映射，並非兩家指定的 schema 或產品內部共同實作。

### LangChain／LangGraph：原生接點與限制

- `wrap_model_call` 可用 `request.override(messages=...)` 改單次模型輸入，不修改持久 state。官方明分 transient model context 與 persistent state；Runtime Context／State／Store 也有不同責任。[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- 現行 middleware 支援 `ExtendedModelResponse(model_response=..., command=Command(update=...))`，將狀態更新隨模型回覆返回；多層 middleware 的覆寫與重試會影響哪次更新生效。這是將回覆與通知邊界綁在同一模型步驟的候選接點，**尚須鎖定實際套件並驗證**。[Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- `update_state` 產生新 checkpoint，走 reducer，`as_node` 會影響後續執行；replay 可能再次呼叫模型／API。`durability="sync"` 在下一步前等待 checkpoint，預設 async 沒有相同等待保證。[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- 已安裝 LangGraph 1.2.11 `pregel/main.py` 的同步執行在 2987–2988 行等 `_put_checkpoint_fut.result()`，非只憑文件名稱推定。此能力仍不使 JD SQL 與 Saver 自動成為同一交易，也不能代替文件 writer owner。

## 3. 本案最小接合方式

1. **先取得同一文件的前景執行權。**完成瀏覽器候選保存／handoff，再取得 H 與 `(last_model_view,H]` 已提交事件的同版讀取材料。純訪談回合也沿已同意的手改暫停；不同文件維持獨立。
2. **凍結這一次真正送入的材料。**App 綁定 dataset／document、原通知基準、H 與通知內容；這些由 App 產生，不讓 LLM 填身分、計數或基準。A→B→A 仍有兩個人工事件；`no_change` 不假造內容變更。
3. **通知只作 request 投影。**不 append 到 canonical `messages`、不改員工 `HumanMessage`、不寫成原始訪談，也不自動更新 Memory。先用可信的事件種類、數量、界線與 opaque refs；任務文字／前後全文經真正 `jd_change_read` 或 `jd_read` 結果提供。這是對 §8 概念預覽欄位的實作建議：不把任意文件文字放進 system；省略內容必須明示。
4. **provider 映射保持明確。**Claude 的可信通知可放支援模型的普通 mid-conversation system；不支援或 adapter 尚未證明能原樣傳遞時，使用 top-level system，並記錄快取代價。兩者均不需 `clear_at`。若採 LangChain，必須捕捉真正 wire request，確認沒有把中途 system 靜默搬到不合法位置；不在 tool_use 與其結果之間插入通知。OpenAI 沿其原生 request 角色映射。不要建立泛用自製訊息／佇列引擎。
5. **完整回覆與邊界共同保存。**推薦同一模型節點輸出原生 response 與該次通知基準，再用原生同步 checkpoint 完成保存，才供後續步驟沿用。一次正常 tool-call 回覆也可閉合本次通知；這不代表整輪顧問已完成或工具已執行成功。不能先以 `update_state` 宣稱已送達，再呼叫模型。
6. **不確定就保留原基準。**未送出、傳輸錯誤、缺終端事件、只有 delta、provider error、回覆不能合法還原，均不能前進。checkpoint ACK 遺失只讀回原生回覆及相同 notice 綁定；讀不到完整證據不猜成功，也不為補證自動重叫付費模型。瀏覽器斷線與 provider／Saver 成功是不同事件，不能互相代推。
7. **基準不倒退。**JD 還原／本輪撤回是新的人工事件；不回退聊天、Memory 或通知基準。通知後仍可由 AI 按需要讀取差異、追問或更新理解，沒有每輪強制改 JD。

選擇只剩「經驗證的原生 middleware」與「同一原生模型節點直接投影」兩個有限接點；優先驗前者，不因未裝套件而先造自己的 agent loop。這不是重新研究所有 agent 品牌。

## 4. Memory 與來源不另建權威

依[現行顧問責任](../../design/consultant-runtime.md)及[既有 context／Memory 核對](../2026-09-06-analysis-only-context-memory-readiness-audit.md)，保留已有工作理解、案例差異、原始問答與精確回查的需求；不包裝舊實驗程式或復活舊待審體驗。

| 資料／效果 | 本次接點責任 |
|---|---|
| 原始問答 | 由既有採用方案的來源權威保存與回查；App notice 不是一則員工回答。新原話未進 Memory 時，顧問仍須能經直接上下文或真實來源 handle 取得。 |
| 可反覆修正的 Memory／案例理解 | 顧問透過它們自己的具名能力讀寫；JD 手改、還原或撤回不隱式改寫／回退。只有模型有依據而明確調整理解時才更新。 |
| JD 來源關係 | 只接受同文件且可實際回查的 source handle。Memory 檔案路徑不是永久引用；人工改欄位後，既有 basis 不再吻合不能冒稱仍有依據。 |
| 通知及歷史 | JD 操作／修訂是事實權威，通知只是有界投影；被省略事件仍可用同一範圍查回，不新增另一份來源或歷史表。 |

「原始資料還在」不等於「模型能找得到」：既有研究已指出沒有可達來源 handle 時的回查缺口。RS-4 必須驗證晚期更正、未進 Memory 的新資料與被壓縮對話的可達路由，不能以保存存在取代此驗收。

## 5. 有限實證與真正未決

**本次已做：**讀取上述現行文件、lock／已安裝原碼；未改 runtime、套件或資料庫，零 provider 呼叫。另用 `httpx2.MockTransport` 與真 Anthropic SDK 1.5.0 執行兩個完全合成 SSE（`message_start`、帶 `stop_reason=end_turn` 的 `message_delta`；只差有無最後 `message_stop`）。兩者 `get_final_message()` 都返回 snapshot：

```text
sent_message_stop=false, sdk_returned_snapshot=true, stop_reason=end_turn
sent_message_stop=true,  sdk_returned_snapshot=true, stop_reason=end_turn
```

可重現附件：[探針](jd-relational-context/anthropic_stream_closure_probe.py)／[本次實際 stdout](jd-relational-context/anthropic_stream_closure_probe.stdout.txt)。探針固定 SDK／transport 版本、純合成資料及本機 MockTransport，對兩種輸出均有斷言；2026-09-13 重新執行 exit 0，兩案吻合。

原因可在安裝原碼 `anthropic/lib/streaming/_messages.py:94` 與 `_streaming.py:63` 核對：消耗至 iterator EOF 即可回 snapshot，沒有強制看到 `message_stop`。**施工需有限補核終端事件；不能只驗 final-message 方法回傳或 stop_reason 非空。**這是離線 SDK 反例，不是真 provider 故障測試；不宣稱所有未選定 LangChain adapter 都有同一行為。

| 尚待施工前閉合 | 有限通過條件 |
|---|---|
| 精確 `create_agent`／provider adapter 版本與 wire | 鎖定免費 OSS 相容版，原生輸入捕捉驗通知角色、tool 配對、完整 response round-trip；原始 HumanMessage 與來源逐字不變。 |
| 回覆與通知邊界的持久步驟 | 用真 compiled graph／Saver 驗完整回覆、模型失敗、缺 message_stop、checkpoint ACK 遺失、子圖／根圖重開；原回覆與原 H 成對才前進，重啟不重播模型。 |
| 有界通知和可達的完整差異 | 驗 A→B→A、no_change、H 以後新事件、被省略大量事件、模型後續查回舊範圍；不能前進後令省略事件失去路由。完整 request 預算含工具／指引／來源，不只裁通知。 |
| 顧問／Memory／source port 採用 | 關閉第二權威風險，驗最新問答未進 Memory、人工更正後 basis 失效、JD-only 撤回與重開；自然內容品質另按核准真模型案例驗收。 |

公開證據已足以進入上述有限接合，不再擴大品牌廣搜；真正未知是版本相容、wire 與保存故障實證，沒有需要額外要求員工確認的產品選項。
