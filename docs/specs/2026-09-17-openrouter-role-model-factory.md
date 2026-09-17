# OpenRouter／Luna 角色模型工廠

- 日期：2026-09-17
- Topic：`JD-R002`
- Stage：**G7 離線窄切片完成**
- 狀態：A／B1／B2 的正式角色模型由單一 App factory 建立；尚未接 managed background callback、layered C、付費自然模型或 production authority

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
- 沿用已驗 Luna request profile：`openai/gpt-5.6-luna`、reasoning `high`、輸出上限 8,192、parallel tool calls 關閉。
- A／B1／B2 各有獨立 model object 與 tracing component，但共用 caller-owned sync／async HTTP clients、同一 credential、同一 provider restriction。
- 三個角色的 SDK hidden retry 均為 0；語意返工、stale 重整與 durable resume 繼續由既有 Runtime／workflow 管理，不在 model factory 疊加重試。
- B1／B2 主呼叫與 continuity compaction 仍由 `build_background_memory_workflow()` 使用同一個注入角色模型物件；factory 不另建 summary model。

### 尚未由本切片決定

- 新 B1／B2 的正式 model-step、tool-call、來源窗口與 stale 上限仍由 managed callback 的組裝參數明示；不能把 package fixture 的 `12／12` 或舊 B2 的 `16／15` 偷升格為產品政策。
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
- 三個 wire request 都是 Luna、OpenAI-only、`allow_fallbacks=false`、reasoning high、8,192 output、parallel tools 關閉；
- 三個角色的 hidden retry 都是 0；
- 空白 key 在外送前拒絕；
- process runtime 保留三個角色並仍用原 A graph／tools，shared clients 可確認關閉且 close 冪等；
- 既有 B1／B2 assembly identity 測試繼續保證主呼叫與 compaction 使用同一注入角色模型。

本切片指定相鄰離線回歸為 **63 passed／0 failed**；無 credential read、provider call、付費、DB、schema、migration、Prompt、Skills、Memory 或 JD 行為變更。

## 5. 來源與下一 gate

- [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart)，查閱 2026-09-17；單一 API key、OpenAI-compatible endpoint 與 client 組裝。
- [OpenRouter Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)，查閱 2026-09-17；`only`、`order`、`allow_fallbacks` 與 `require_parameters`。
- [OpenRouter Python SDK](https://openrouter.ai/docs/client-sdks/python/overview)，查閱 2026-09-17；薄 client 與 application-owned orchestration。
- [LangChain ChatOpenRouter](https://docs.langchain.com/oss/python/integrations/chat/openrouter)，查閱 2026-09-17；model、reasoning、tool calling、usage 與 provider routing 公開接點。
- [CTX-C001 compaction](2026-09-16-openrouter-continuation-compaction-design.md)；同角色 main／summary model boundary。
- [MEM-L001 workflow](2026-09-17-layered-memory-background-workflow-design.md)；B1／B2 注入點、attempt 與 publication 權責。

下一 gate 是把 process-owned `RoleModels.case／understanding` 經 document-scoped managed callback 注入既有 `BackgroundMemoryWorkflow`。該片只組裝已完成的 dispatcher 與 workflow；正式 B1／B2 執行上限若文件仍無有效決策，須先提出最小候選與影響，不得沿 fixture 猜值。
