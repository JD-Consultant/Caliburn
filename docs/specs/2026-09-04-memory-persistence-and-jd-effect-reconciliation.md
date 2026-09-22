# Memory 持久化與 JD 待審變更相依性 reconciliation

- Decision ID：`MEM-Q005`
- 狀態：**G3 Product Owner 已核准的 Working Decision（2026-09-04）**
- Production 效力：**無**；仍須由後續 LLM orchestration design、successor ADR 與 implementation gate 承接
- 目前狀態入口：[`../current-decisions.md`](../current-decisions.md)

> 本文只回答一題：同一輪分析產生的 Semantic Memory 更新若因技術問題尚未成功持久化，是否必須丟棄或阻擋同輪的 JD 待審變更。本文不決定 retry 次數、模型 call 數、資料表、queue、UI 告警樣式或 production migration。

## 1. Preflight

```text
Topic ID: MEM-Q005
Current stage: G3 Owner decision complete；等待後續 orchestration G4
Binding decisions: MEM-D001～MEM-D003、MEM-Q001～MEM-Q004
This turn's only blocking question:
  Memory 持久化失敗是否必然使同輪 JD 待審變更失效？
Already reviewed evidence:
  OpenAI Codex Memories、OpenAI Tools、Anthropic Tool-use contract／parallel tool use、
  Google Memory Bank、AWS AgentCore Memory、LangGraph／LangMem error／retry guidance。
Out of scope / parking lot:
  retry 精確次數、timeout、queue、背景 worker、schema、模型步數、完整 UI、production 施工。
```

## 2. 先分清楚兩種「依賴」

### 2.1 語意輸入依賴

JD 判斷依賴模型**實際讀到的內容**：目前有效 Semantic Memory、相關 canonical conversation、本輪員工訊息、目前 JD，以及同一 run 已形成並通過內容驗證的理解。

### 2.2 持久化完成依賴

另一個動作若必須重新讀取「已發布的新 Memory head」才能計算，才依賴 Memory 寫入成功。例如下一個獨立 run 只從 Store 讀取新 head，或最終全面檢查要宣稱全部有效工作資訊均已處理。

同一 run 從同一組輸入與同一份已驗證理解形成的 Memory mutation 與 JD 待審變更，是兩個**並列 effects**；JD 使用了該份理解，不表示它依賴這份理解先寫入 Store。

```text
canonical conversation + current Semantic Memory + current JD
                            ↓
                 本輪已驗證的語意理解
                     ↙                 ↘
        Semantic Memory mutation     JD 待審變更
```

## 3. 官方事實與能下的結論

### 3.1 OpenAI

Codex 本機 Memory 會在對話閒置後背景 extraction／consolidation，不保證對話結束後立即更新，接近 rate limit 時也可能略過一次背景處理；官方並將 Memory 定位為有助回想的輔助層，而不是必須永遠適用之規則的唯一依據。這直接證明目前工作不必普遍等待持久 Memory 發布。

OpenAI Tools／Function Calling 讓 application 執行自訂 Tool，並可用 `parallel_tool_calls=false` 限制平行呼叫。官方提供的是 Tool contract 與排程控制，不替應用定義兩個業務 effects 是否相依。

### 3.2 Anthropic

Anthropic 的 client Tool contract 是模型提出結構化呼叫、application 執行並回傳 `tool_result`。Parallel Tool Use 官方明說執行順序由 application 決定：獨立操作可並行；有 side effect、共享狀態或排序要求的呼叫宜依序執行。若前一個呼叫失敗而後一個確實依賴它，後者可以不執行並回傳 `is_error: true`。

這支持「只阻擋真正相依的動作」，不支持「只要都是同輪 side effect，就必須一律串行或一起報廢」。

### 3.3 Google、AWS 與 LangGraph／LangMem

Google Memory Bank 同時公開 blocking 與 background generation；AWS AgentCore 先保存 raw event，再非同步 extraction／consolidation並讓持續失敗的 ingestion 可查、可 redrive。LangGraph／LangMem 則分開處理 transient retry、模型可修正錯誤、使用者可修正問題與不可恢復錯誤，並區分 hot-path 與 background formation。

共同結論是：來源不得因 Memory pipeline 失敗而遺失；失敗不能冒充成功；真正讀取新結果的步驟才等待。公開資料沒有任何一家規定「Semantic Memory 寫入失敗時，必須丟棄由相同對話與相同理解形成的業務候選」。

## 4. Owner 核准的 Caliburn 映射

1. 員工訊息／canonical conversation 先耐久保存；此步失敗不能假裝已收到訊息。
2. LLM 可在同一個 product run 中，根據同一份 Context 形成 Semantic Memory mutation 與零至多筆 JD 待審變更；不要求固定一或兩次模型呼叫。
3. Runtime 分別驗證 Memory mutation 與 JD 待審變更；兩者各自有成功、合法 no-op 或失敗結果。
4. Memory 因格式、暫時性基礎設施或 Store 寫入問題失敗時，進行依錯誤類型、有上限且冪等的修正／重試。
5. **Memory 技術性持久化失敗本身，不會刪除、阻擋或自動標 stale 同輪已通過自身驗證的 JD 待審變更。**員工仍可查看、修改、接受或拒絕該 JD 變更。
6. Memory 重試耗盡時，舊 current head 繼續有效；失敗必須可觀察且可從 canonical conversation 重新抽取。後續 Context 不得假裝新 Memory 已發布。
7. 只有重新分析後的工作理解實質改變，或 JD 自身 base state 已改變，相關 JD 待審變更才需要重新驗證或標示 stale。單純「Store 尚未寫入成功」不是語意 stale。
8. 語意不明或員工說法可能有多種合理解讀，是寫入前的顧問判斷／詢問問題，不是 Memory Tool 的寫入錯誤，也不是無限技術重試的理由。
9. 最終全面製作、重大重整或宣稱 JD 完整涵蓋時仍是例外：依 `MEM-D003`，相關來源若仍未成功形成 Memory 或合法 no-op，就不能宣稱已完成全量盤點。
10. Memory 本身不操控 JD；員工核准仍是正式 JD 的 authority seam。

## 5. 失敗行為

| 情況 | Memory | JD 待審變更 |
| --- | --- | --- |
| Tool 參數／格式錯誤 | 回傳精確錯誤，有限次模型修正 | 自身驗證通過且語意未變則保留 |
| timeout、429、暫時性 5xx | Runtime bounded backoff／retry | 保留，不因基礎設施錯誤刪除 |
| Store 寫入最終失敗 | 舊 head 有效；保留可恢復失敗並由 conversation 重建 | 保留且可審核；不得聲稱 Memory 已同步 |
| concurrent stale／precondition 失敗 | 重讀 current head 後重新整理 | 只有最新語意或 JD base 改變才重新驗證 |
| 新分析改變原本工作理解 | 發布修正後 current Memory | 受影響候選重新驗證／stale |
| 重複或沒有值得保存的新內容 | 合法 no-op | 照自身判斷與驗證處理 |
| canonical conversation 保存失敗 | 本輪不能繼續形成可靠持久結果 | 不建立該輪 JD 待審變更 |

若底層資料庫整體不可用，JD 自己的持久化也可能失敗；那是 JD Tool 的獨立錯誤，不應誤報成「因 Memory 相依而跳過」。

## 6. 本次取代與不取代的內容

本決策取代以下過度寬泛敘述：

- 「所有會形成 durable／對外可觀察效果的 JD 變更，都必須等待 Semantic Memory 先發布」；
- 「Memory 技術性寫入失敗時，同輪 JD 候選一律停止或丟棄」；
- 「JD 待審變更只因 Memory receipt／revision 尚未成功便自動 stale」。

本決策**沒有**取消以下規則：

- 真正需要重新讀取新 Memory head 的後續步驟必須等成功結果；
- 最終完整性檢查必須可驗證地處理全部有效 Memory／來源；
- Memory 未完成不得冒充已完成；
- JD 變更自身仍需 deterministic validation 與員工核准。

## 7. 不能過度宣稱的地方

- 沒有廠商公開「Memory → JD」的專用交易規則；「並列 effects」是把官方 Tool／Memory 時序映射到 Caliburn 的產品決策。
- 本文不要求 Memory 與 JD 跨 Store ACID transaction，也不選 queue／outbox／background worker。
- 本文不決定精確 retry 次數；只要求依錯誤類型、有上限、可觀察、冪等。
- 本文不要求模型填 scope、ID、版本、重試狀態或基礎設施欄位；這些仍由 Runtime／framework 管理。

## 8. Reopen triggers 與下一個 gate

只有以下情況重開 `MEM-Q005`：

1. representative long-interview test 證明保留 JD 候選會把已改變的錯誤理解帶入文件；
2. Memory 最終失敗後，canonical conversation 無法可靠重建遺漏理解；
3. 所選 provider／framework 的新官方契約要求不同的 side-effect sequencing；
4. Product Owner 改變「Memory 輔助 JD、但不操控 JD」的產品邊界。

下一個 gate 是將本規則納入 LLM orchestration G4：定義同一 run 的 Context snapshot、兩類 effect 的 framework wiring、typed failure 與產品可觀察結果。這不授權 production 施工。

## 9. 直接來源

- [OpenAI — Codex Memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)
- [OpenAI — Using tools](https://developers.openai.com/api/docs/guides/tools)
- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Anthropic — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic — Parallel tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)
- [Anthropic — Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Google Cloud — Memory Bank generation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google Cloud — Memory Bank troubleshooting](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/troubleshooting)
- [AWS — AgentCore Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)
- [AWS — Redrive failed ingestions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-redrive.html)
- [LangGraph — Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)
- [LangMem — Core concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)

