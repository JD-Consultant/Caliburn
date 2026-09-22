# A evidence：ToolMessage private artifact 與 OpenRouter wire 固定實證

- 日期：2026-09-20
- Topic：`JD-R002 / MEM-L001 / A-R001`
- 用途：驗證[跨顧問、Memory 與 JD 的模型安全證據契約](../2026-09-20-cross-agent-evidence-and-jd-context-contract.md)能沿鎖定框架做 model-visible content／Runtime-private evidence 分離
- 性質：本機零 provider、零 DB、零正式資料的 transport／serialization probe；不是 Agent、checkpoint DB、自然模型或完整 App 驗收

## 環境

從 `experiments/jd-relational-app/.venv` 直接讀取並執行鎖定安裝：

| 套件 | 版本 |
|---|---|
| langchain | 1.4.0 |
| langchain-core | 1.6.3 |
| langgraph | 1.2.11 |
| langchain-openrouter | 0.2.7 |

## 官方／安裝原碼事實

- LangChain `ToolMessage.artifact` 的 docstring 明示該內容不應送給模型，適用於 model content 只取完整工具結果一部分的情境。[官方 ToolMessage reference](https://reference.langchain.com/python/langchain-core/messages/tool/ToolMessage)
- 鎖定的 `langchain_openrouter.chat_models._convert_message_to_dict()` 對 `ToolMessage` 只序列化 `role`、`content` 與 `tool_call_id`；沒有序列化 `artifact`。
- 鎖定的 LangChain message dict round-trip 會把 `artifact` 納入 message data 並恢復。

## 固定探針

建立一筆：

```text
ToolMessage.content  = evidence_key=E1
ToolMessage.artifact = {source_reference: PRIVATE_SIGNED_REFERENCE, next_offset: 0}
```

再分別執行 OpenRouter message conversion 與 LangChain `messages_to_dict` → `messages_from_dict` round-trip。

實際結果：

```text
wire = {
  role: tool,
  content: evidence_key=E1,
  tool_call_id: call_1
}
wire_contains_private = false
restored_artifact = {
  source_reference: PRIVATE_SIGNED_REFERENCE,
  next_offset: 0
}
```

## 可以與不能推出的結論

可以推出：鎖定版本有一條現成的 content／artifact 分離接點；A evidence tool 不需要把 signed source token 放進 model-visible ToolMessage 才能讓 Runtime 保存它。

不能推出：

- 尚未證明正式 LangGraph PostgreSQL checkpointer、graph rebuild 與 request-only compaction 的完整往返；施工 Task 1／5 必須補這些反例。
- 尚未證明 artifact 內容可信；正式實作仍須核 factory tool identity、call/result、document/run scope、格式與 digest。
- 尚未證明 Luna 會正確選 key、JD 內容會正確引用或 C 的語意判斷自然通過。
- 此 probe 不授權新增 registry DB、切 provider、修改 Prompt 或直接採用 production。
