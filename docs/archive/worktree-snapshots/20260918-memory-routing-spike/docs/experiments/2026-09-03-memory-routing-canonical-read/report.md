Verdict: FAIL_UNPROVEN

# Memory Routing 與 Canonical Read 隔離實驗報告

## 1. 結論

Trial revision 3 仍沒有產生可評分的模型結果。它已通過資料庫、Store 與 embedding 路徑，並以
三個 embedding request 處理 274 tokens；但第一個 Luna chat request 在 OpenRouter 路由層收到
HTTP 404，沒有上游 provider／model response，也沒有 Memory tool call 或 model-visible turn。
六個品質判準因此仍全部是 `NOT_EVALUATED`。本結果不能解讀為 Memory routing 成功，也不能
解讀為 Luna 或兩個 Memory tools 的語意品質失敗。

唯讀官方 capability metadata 與凍結 request 的交叉核對已定位一個充分原因：request 同時送出
`parallel_tool_calls: false` 與 `provider.require_parameters: true`，但 OpenRouter 列出的七個
Luna endpoint 都沒有宣告支援 `parallel_tool_calls`。依 OpenRouter 官方路由規則，這會把全部
endpoint 排除。詳細證據見 §10。

Revision 2 的 Windows event-loop failure 與後續 bounded repair 紀錄保留在 §3～§9。依 revision 3
授權，這次 attempt 已保存並停止；現在不授權 revision 4、修改條件後重跑、production 整合、
ADR 狀態改變、merge 或 push。

## 2. Revision 2 凍結條件

| 項目 | 實際值 |
|---|---|
| Case SHA-256 | `a39f668dbcb23f4b7c8b8396cb8593f115dda8da41d092efb4b24be63bf9b835` |
| Rubric SHA-256 | `7555260a65dd5882be1ab680c6ac1ecf3ebb45fb385048f0515d5d72682a0158` |
| Prompt SHA-256 | `91558055927742669fe1be8df33100a63a216490d95c2dac44e24c808d62c701` |
| Chat model | `openai/gpt-5.6-luna` |
| Reasoning | `medium` |
| Embedding model | `openai/text-embedding-3-small` |
| 最大 model／tool calls | `3／2` |
| Provider／framework retry | `0／0` |

Case、rubric、prompt、模型與所有 caps 在 attempt 前後均未修改。

## 3. Revision 2 實際發生的事

1. runner 成功讀取不落盤的 API key，並完成 model、embedding 與 endpoint metadata preflight。
2. runner 以 Windows 上的 `asyncio.run()` 啟動；Python 3.13 預設建立
   `ProactorEventLoop`。
3. `open_spike_runtime()` 在 `_read_current_database()` 建立第一個 Psycopg async connection
   時被官方相容性檢查拒絕。
4. 程序以 exit code 1 結束，launcher wall time 為 2,749 ms；尚未進入 Store、embedding、
   LangGraph agent runtime、Memory tools 或 Luna。
5. 例外不在 runner 的 receipt error boundary 內，因此正常 `LiveSmokeReceipt` 沒有寫出。
   `trials/revision-2-luna-medium.json` 是依保存下來的 command result 重建的 attempt record，
   不是 provider receipt。

精確錯誤分類是 `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in
async mode`。

## 4. 為何 revision 2 的 deterministic tests 沒有提早發現

`tests/conftest.py` 在 Windows 明確安裝 `WindowsSelectorEventLoopPolicy`，所以 PostgreSQL
tests 使用 Psycopg 相容的 Selector loop。CLI runner 的 `main()` 直接使用預設
`asyncio.run()`，沒有繼承 pytest-only 設定；因此 deterministic suite 綠燈，而實際 CLI
入口仍失敗。

這是 experiment-runner entrypoint coverage 缺口，不是 Store、Checkpointer 或 Memory read
contract 的反例。

## 5. Revision 2 官方診斷與當時的最小候選修法

Psycopg 官方明示 Windows 預設 `ProactorEventLoop` 不相容，應使用
`SelectorEventLoop`。Python 官方說明 Windows 自 Python 3.8 起預設使用 Proactor；Python
3.13 的 runner API 則建議以 `asyncio.run(..., loop_factory=...)` 設定 loop，而非依賴全域
policy。

不發 provider request 的 DB-only 診斷已用
`asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)` 成功讀回專用資料庫名稱
`caliburn_memory_routing_spike`。因此最小候選修法是只在 Windows CLI entrypoint 選用
Selector loop，並補 entrypoint regression test；不需要改 Memory 架構、升級 SDK、增加
retry 或更換資料庫。

本報告初稿只記錄候選修法；其後 Product Owner 另行核准 bounded repair，結果見 §9。原 trial
verdict 不因此改寫；修復後是否另核准新的 live attempt 仍是獨立 gate。

直接來源：

- [Psycopg — Concurrent operations／Windows event-loop warning](https://www.psycopg.org/psycopg3/docs/advanced/async.html)
- [Python 3.13 — asyncio platform support on Windows](https://docs.python.org/3.13/library/asyncio-platforms.html#windows)
- [Python 3.13 — asyncio runners and `loop_factory`](https://docs.python.org/3.13/library/asyncio-runner.html#running-an-asyncio-program)

## 6. Revision 2 Rubric 結果

| 判準 | 結果 | 原因 |
|---|---|---|
| A 案細節與精確原句 | `NOT_EVALUATED` | 沒有 Luna request |
| A／B 分案與更正後 current Memory | `NOT_EVALUATED` | 沒有 Luna request |
| 未知資訊不捏造 | `NOT_EVALUATED` | 沒有 Luna request |
| 自主 search＋canonical deep-read | `NOT_EVALUATED` | 沒有 model／tool call |
| Context 有界 | `NOT_EVALUATED` | 沒有 model-visible turn |
| Scope／secret 不洩漏 | `NOT_EVALUATED` | 沒有 model-visible turn |

## 7. Revision 2 支持、不支持與未證明

### 支持

- metadata preflight 可在凍結模型與成本條件下完成。
- 既有 deterministic suite 支持隔離元件的 PostgreSQL persistence、scope guard、strict tool
  contract 與 storage-growth 量測；這些不是 revision 2 的模型品質結論。
- 官方建議的 Windows Selector loop 能在同一環境完成專用資料庫 identity read。

### 不支持

- 現行 CLI live runner 可在 Windows 預設設定下跑通；revision 2 直接反證此點。

### 未證明

- Rubric 六項與 M2、M4 read-side、M7、M8 model-routing、M10 model deep-read、M11
  model-visible scope 全部未證明。
- 原計畫列出的 M3 admission breadth、完整 M4 manager 更新、M5 未知／衝突
  consolidation、M6 整體關係品質、M9 final exact full audit、真實員工資料品質、production
  scale 與 UI 仍未證明。
- 因未發 inference request，實際 resolved model／provider、token、cache、reasoning、embedding
  usage 與 inference request IDs 均未產生；metadata request 的 response identifier／latency 未由
  runner 保存，也不得推測。

## 8. 當時的下一個 gate（已由 §9 完成）

當時先由 Product Owner review 本報告，決定是否只核准 Windows CLI event-loop bounded repair；
該 gate 後來依 §9 完成。repair 不自動授權下一個 Luna attempt，且沒有在同一決策中默認重跑。

## 9. Post-report bounded repair（不改寫 trial verdict）

Product Owner 於 review 本報告後，只核准 Windows CLI event-loop repair 與 regression test，沒有
核准再次執行 Luna。修復採 Python 3.13 官方 `asyncio.run(..., loop_factory=...)` 入口：Windows
使用 `asyncio.SelectorEventLoop`，其他平台維持預設 loop。

regression test 刻意把 pytest policy 還原成 Windows 預設 Proactor，再從真 CLI `main()` 進入
實際 Psycopg database identity read。RED 精確重現 revision 2 的 `psycopg.InterfaceError`；單行
runner 修復後 GREEN，整份 live-smoke deterministic 測試為 28 passed。這只證明原 CLI plumbing
缺口已被覆蓋；完整 isolated deterministic suite 為 60 passed、1 個 optional skip。這不證明任何
Luna／Memory rubric 項目，§1 的 `FAIL_UNPROVEN` 維持不變。

## 10. Trial revision 3 實際結果

### 10.1 凍結條件與 receipt

Revision 3 沿用 §2 的同一 case、rubric、prompt、Luna medium、embedding model、call／tool／
token／cost caps 與零 retry；執行前完整 isolated deterministic suite 為 60 passed、1 個 optional
skip。實際 receipt 為
[`trials/revision-3-luna-medium.json`](trials/revision-3-luna-medium.json)，摘要如下：

| 項目 | 實際值 |
|---|---|
| Status | `failed` |
| Error | `live_NotFoundResponseError` |
| Chat request budget counter | `1` |
| 上游 resolved model／provider | 未產生 |
| Memory tool calls | `0` |
| Model-visible turns | `0` |
| Chat input／output／reasoning tokens | `0／0／0` |
| Embedding | 3 requests；274 tokens；resolved model `text-embedding-3-small` |
| 已知實際費用 | USD `0.00000548`，全數來自 embedding |
| Wall latency | 7,488 ms |

`model_calls: 1` 表示實驗執行器已進入第一次 chat invocation 並先扣除 call budget；它不代表模型
已開始生成。SDK 在回傳 `ChatResult` 前拋出 404，因此 receipt 沒有 chat usage、request ID、
resolved model、provider 或模型輸出。三個保存的 `gen-emb-*` ID 全都是 embedding request ID。

### 10.2 失敗位置

1. model／embedding／endpoint metadata preflight 成功；
2. Windows Selector loop、Psycopg、LangGraph PostgreSQL Store setup 與 semantic-memory embedding
   成功；
3. 第一次 Luna request 經 pinned `langchain-openrouter==0.2.7` 呼叫
   `openrouter==0.10.8` 的 `/chat/completions`；
4. OpenRouter SDK 解析 HTTP 404 為 `NotFoundResponseError`；
5. graph 未收到任何 `AIMessage`，所以沒有 tool routing、canonical deep-read 或 rubric 可評分輸出。

因此這是 **provider capability-routing contract failure**，不是 Memory Store／retrieval failure、
模型拒答、工具 schema 解析錯誤或答案品質失敗。

### 10.3 官方證據與根因邊界

凍結 request 的 deterministic HTTP-boundary test 已證明實際 payload 含：

- `model: "openai/gpt-5.6-luna"`；
- `reasoning: {"effort": "medium"}`；
- `max_completion_tokens: 1200`；
- 兩個 strict tools；
- `parallel_tool_calls: false`；
- `provider: {"allow_fallbacks": false, "require_parameters": true}`。

2026-09-04 對 OpenRouter 公開 catalog 做不帶 API key、無付費推論的唯讀核對：

- Luna 存在且列出 7 個 provider endpoint；
- Luna 出現在 `tools`、`reasoning`、`max_completion_tokens` capability filters；
- Luna **不在** `parallel_tool_calls` capability filter；
- 7 個 endpoint 的 `supported_parameters` 均包含 tools 與 reasoning，但沒有任何一個包含
  `parallel_tool_calls`。

OpenRouter 官方說明 `require_parameters: true` 只會把 request 路由給支援**所有已提供參數**的
provider，不符合者在 routing 前就會被排除；官方 tool-calling 說明也指出，當沒有符合 tool
需求的 endpoint 時會回 404。兩者和本次 404、零 provider/model response 完全一致。由於
`parallel_tool_calls` 是凍結 payload 中唯一未被 Luna capability metadata 支援的關鍵
inference parameter，這個組合已足以解釋零 eligible endpoint。

本次 receipt 只保存 exception type，沒有保存 SDK exception 已持有的安全 error message／body，
所以報告不能逐字引用 OpenRouter 當次 404 訊息；這是 observability 缺口，不影響上述由官方
路由規則、公開 capability matrix 與實際 payload 建立的診斷。Account-level routing policy
是否另有額外限制則未驗證，也不需要用它才能解釋本次失敗。

直接來源：

- [OpenRouter — GPT-5.6 Luna model／providers／tool support](https://openrouter.ai/openai/gpt-5.6-luna-20260709)
- [OpenRouter — requiring providers to support all parameters](https://openrouter.ai/docs/guides/routing/provider-selection#requiring-providers-to-support-all-parameters)
- [OpenRouter — provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter — tool-calling 404 與 capability 檢查](https://openrouter.ai/blog/tutorials/tool-calling/#models-that-dont-support-tools)
- [OpenRouter — endpoint metadata API](https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints)
- [OpenAI — GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)

### 10.4 Revision 3 rubric

| 判準 | 結果 | 原因 |
|---|---|---|
| A 案細節與精確原句 | `NOT_EVALUATED` | 沒有 model response |
| A／B 分案與更正後 current Memory | `NOT_EVALUATED` | 沒有 model response |
| 未知資訊不捏造 | `NOT_EVALUATED` | 沒有 model response |
| 自主 search＋canonical deep-read | `NOT_EVALUATED` | 沒有 tool call |
| Context 有界 | `NOT_EVALUATED` | 沒有 model-visible turn |
| Scope／secret 不洩漏 | `NOT_EVALUATED` | 沒有 model-visible turn |

### 10.5 支持、反證與下一個 gate

Revision 3 新支持：

- 修復後的 Windows CLI 能通過 Psycopg、Store 與 embedding 路徑；
- semantic-memory embedding 的三個 provider request 成功，且已知費用遠低於 cap；
- receipt 能在 chat route failure 後保存 bounded、無 secret、無 private reasoning 的結果。

Revision 3 直接反證：

- frozen `parallel_tool_calls: false`＋`require_parameters: true` 可以在目前 OpenRouter Luna
  capability matrix 上形成可路由的 request。

仍未證明：所有 Luna／Memory 語意 rubric，以及 production Memory writer、JD 操作、真實資料、
scale、UI 與完整 final audit。

下一步不是重試。唯一合法 gate 是先由 Product Owner 決定是否另開一個 bounded contract-design
問題，研究如何同時維持工具執行上限與 OpenRouter 可路由性。可能候選包括：不傳
`parallel_tool_calls` 並由 Runtime 驗證 tool-call 數量；或不使用 hard
`require_parameters` filter、讓 Runtime 對 provider 行為 fail closed。這些都會修改 frozen
contract，尚未獲准，也不得在本報告內替 Owner 決定。更換模型／provider 或改走 direct OpenAI
同樣是不同實驗，不是 revision 3 的自動修復。
