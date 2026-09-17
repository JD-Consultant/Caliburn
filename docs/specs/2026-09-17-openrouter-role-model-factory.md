# OpenRouter／Luna 角色模型工廠

- 日期：2026-09-17
- Topic：`JD-R002`
- Stage：**G7 離線窄切片完成**
- 狀態：A／B1／B2 的正式角色模型由單一 App factory 建立，B1／B2 正式執行限制已由 App profile 統一；successor 已完成 managed background callback 的離線窄接線，仍未完成 layered C、付費自然模型、完整瀏覽器 App 旅程或 production authority

## 1. 目的與既有決策

Caliburn 只有一個 App 與一個 OpenRouter credential。正式模型路徑維持：

```text
LangChain／LangGraph
    ↓
ChatOpenRouter／OpenRouter SDK
    ↓ 單一 OpenRouter key
OpenRouter
    ↓ provider only = OpenAI、allow_fallbacks = false
openai/gpt-5.6-luna
```

本切片只補齊角色模型組裝，不重做顧問 Prompt、Skills、JD tools、B1／B2 Memory 語意、compaction、dispatcher、publication 或錯誤恢復。A、B1、B2 是同一 App 的三個內部角色，不是三個產品或三套 credential。

## 2. 官方事實、產品取捨與未知

### 官方事實

- OpenRouter 提供單一 API key 與 OpenAI-compatible endpoint；client SDK 是薄的 API client，conversation loop、工具與應用狀態仍由 App／framework 管理。
- OpenRouter provider routing 的 `only` 可限制 provider；`allow_fallbacks` 預設允許 fallback，因此本產品要禁止 fallback 必須明確送出 `false`。
- LangChain `ChatOpenRouter` 公開支援 `model`、`max_tokens`、`max_retries`、reasoning、tool calling、usage metadata 與 `openrouter_provider`。鎖定版 `langchain-openrouter==0.2.7` 仍以本 repo 的離線 wire tests 驗證實際序列化，不能把最新版文件直接外推成鎖定版已驗能力。

### Caliburn 取捨

- 沿用既有共用 `openrouter_model.py`，不新增第二套 HTTP／SDK adapter。
- 沿用已驗 Luna route：`openai/gpt-5.6-luna`、reasoning `high`、parallel tool calls 關閉。A 保留既有輸出上限 8,192 與 90 秒 timeout；背景 B1／B2 採下節正式 profile，不把 A 的數值誤當所有角色共同上限。
- A／B1／B2 各有獨立 model object 與 tracing component，但共用 caller-owned sync／async HTTP clients、同一 credential、同一 provider restriction。
- 三個角色的 SDK hidden retry 均為 0；語意返工、stale 重整與 durable resume 繼續由既有 Runtime／workflow 管理，不在 model factory 疊加重試。
- B1／B2 主呼叫與 continuity compaction 仍由 `build_background_memory_workflow()` 使用同一個注入角色模型物件；factory 不另建 summary model。

### 正式背景執行 profile

`background_memory_limits.py` 是 App assembly 的單一設定來源；package defaults 仍只是通用／測試預設。正式值為：

| 限制 | B1 案例維護 | B2 工作理解 |
|---|---:|---:|
| reasoning | high | high |
| 主輸出上限 | 32,768 tokens | 32,768 tokens |
| compaction summary 上限 | 8,192 tokens | 8,192 tokens |
| request timeout | 300 秒 | 300 秒 |
| model steps | 256 | 128 |
| tool calls | 240 | 120 |
| 完成修正 | 3 | 3 |
| B1 來源窗口／消歧前文／最多窗口 | 24,000／6,000 chars／16 | 不適用 |

共同 compaction trigger 保留 16,000 input tokens，保留最近 8 個安全訊息／完整工具 wave；同一背景 job 的 CAS stale 最多重做 5 次。B2 發現案例問題後退回 B1 的語意返工仍最多一次，與 stale 競爭重做不是同一額度。

這些值是根據既有長訪談／背景實驗、工作複雜度與「優先產出可用結果」要求選定的 App guardrail，不是 OpenAI／OpenRouter 規定。32,768 是容量保險，不代表 8,192 已被自然模型實測證明必然截斷；暫不加入 32K→65K 自動重送，因目前框架計數與 checkpoint 邊界不能讓該重送保持明確可核算。若正式 route 日後出現可重現的 length truncation，再設計一個計入既有 durable counters 的恢復路徑。

### 仍待真實驗證

- 真 key 可用性、自然模型品質、費用與 provider 實際 route 尚未由本切片驗證。

## 3. 組裝與生命週期

`create_role_models()` 接受 caller 已取得的 key 及 caller-owned sync／async clients，回傳：

```text
RoleModels
├─ consultant       → A 主顧問
├─ case             → B1 案例維護者
└─ understanding    → B2 工作理解維護者
```

建構只建立本機 client/model objects，不送出模型請求，不讀 credential store，也不建立 DB、Saver、Store、scheduler 或 document registry。`open_consultant_runtime()` 是目前 process owner：它建立一次 shared clients 與三個角色模型，以 `consultant` 建立既有顧問 graph，並保留 `case／understanding` 供下一片 managed background callback 注入。關閉仍只由 process runtime 在 App 排空後關閉 shared clients。

缺 key 的普通產品入口維持既有行為：不呼叫 factory、人工 JD 可用、AI 關閉。若 factory 被錯誤地以空白 key 呼叫，則在任何外送前以既有 `invalid_model_configuration` 明確拒絕；不嘗試 OpenAI key、環境 fallback 或另一 provider。

## 4. 驗收與證據

離線契約固定驗證：

- 建立三個角色時沒有 HTTP request；
- 三個 wire request 都是 Luna、OpenAI-only、`allow_fallbacks=false`、reasoning high、parallel tools 關閉；A 實送 8,192／90 秒，B1／B2 實送 32,768／300 秒；
- 三個角色的 hidden retry 都是 0；
- 空白 key 在外送前拒絕；
- process runtime 保留三個角色並仍用原 A graph／tools，shared clients 可確認關閉且 close 冪等；
- B1／B2 assembly identity 測試繼續保證主呼叫與 compaction 使用同一注入角色模型，並固定兩個 summary 8,192、B1 24,000／6,000／16、步數／工具／完成修正與 stale 額度；dispatcher 的 source planning 使用相同 B1 設定。

原角色 factory 切片指定相鄰離線回歸為 **63 passed／0 failed**。正式背景 profile 接線後，fresh 完整 App 離線回歸為 **2,996 passed／320 environment-skipped／0 failed**，`src／tests` compileall 成功；無 credential read、provider call、付費、DB、schema、migration、Prompt、Skills、Memory 或 JD 行為變更。

## 5. 來源與下一 gate

- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart)，查閱 2026-09-17；單一 API key、OpenAI-compatible endpoint 與 client 組裝。
- [OpenRouter Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)，查閱 2026-09-17；`only`、`order`、`allow_fallbacks` 與 `require_parameters`。
- [OpenRouter Python SDK](https://openrouter.ai/docs/client-sdks/python/overview)，查閱 2026-09-17；薄 client 與 application-owned orchestration。
- [LangChain ChatOpenRouter](https://docs.langchain.com/oss/python/integrations/chat/openrouter)，查閱 2026-09-17；model、reasoning、tool calling、usage 與 provider routing 公開接點。
- [CTX-C001 compaction](2026-09-16-openrouter-continuation-compaction-design.md)；同角色 main／summary model boundary。
- [MEM-L001 workflow](2026-09-17-layered-memory-background-workflow-design.md)；B1／B2 注入點、attempt 與 publication 權責。

[managed App 背景 callback](2026-09-17-managed-app-background-callback-design.md) successor 已完成窄 G7：process-owned `RoleModels.case／understanding` 已經 App-owned coordinator 注入既有 document-scoped `BackgroundMemoryWorkflow`，共用 A graph 也改由 per-invocation Runtime context 取得背景 availability；Task 5 lifecycle closure 後的最終完整 App 離線回歸為 **3,016 passed／320 skipped／5 warnings／0 failed**。**唯一下一 gate 是獨立 layered C bundle repair**；其後的自然模型／付費、完整瀏覽器 App 旅程與 production authority 仍分開驗證，多 process 拓撲則必須先補 DB 原子 admission claim。本稿的模型 factory 契約與既有 Memory／compaction 邊界不因 successor 重開。

Task 3 re-review 已關閉 synthetic `ui_chat_server` 漏傳 B1／B2 models 的 UI helper composition seam；該 focused 證據固定零 model request／零 provider network，但停在 `open_managed_app` 邊界，未啟動 DB、lifespan、listener 或瀏覽器，完整瀏覽器 App 旅程仍未驗。
