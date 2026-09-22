# JD Memory Scope 與 Conversation Thread Cardinality（Working Design）

- 日期：2026-09-04
- Topic ID：`MEM-Q005`
- 階段：G3；Product Owner 已核准方案 A
- 觸發原因：Product Owner 指出成熟設計常允許多個長期 thread 共用一份 Memory；Caliburn 每份 JD 有自己的 Memory，但第一版不一定需要多個 thread
- 效力：只釐清 JD、Memory 與 conversation thread 的 scope／cardinality；不授權 schema、UI、多 agent、跨 JD Memory 或 production 施工

## 1. 本輪唯一問題

Caliburn 是否應將長期 Memory 的 scope 與 conversation thread 解耦：第一版每份 JD 只開一個主要 thread，但同一份 JD 的 Memory 不綁死該 thread，未來可由同一 JD 的多個 thread 共用？

## 2. 官方事實

### F1．LangGraph 明確區分 thread checkpoint 與跨 thread Store

LangGraph Checkpointer 依 `thread_id` 保存 graph／conversation state；Store 則保存 graph state 外的長期資料，官方用途包含跨 threads 存取。Store namespace 可由應用自行定義，不必以 user 或 thread 為唯一 scope。

### F2．Anthropic Memory Store 是獨立資源，可掛載到多個 sessions

Anthropic Managed Agents 的 session 保存該 session 的 conversation history；Memory Store 則獨立於 session，刪除 session 不會刪除 Memory Store。同一 store 可掛載到多個 sessions並同步讀寫，官方也直接列出「每位使用者、每個團隊或每個 project 一個 store」作為產品 scope 範例。

### F3．OpenAI 也區分 conversation Session 與跨 runs 的 agent Memory

OpenAI Agents SDK Session 保存特定 conversation 的訊息歷史；Sandbox Agent Memory 是另一層、由先前 runs 萃取的持久資料。其 Memory isolation 由 memory layout／conversation identity 決定，並不等同單次 run state。

### F4．公開共識是「責任分離」，不是「每個產品必須有多個 threads」

各家提供多 conversation／session 共用長期 Memory 的能力，是為了支援多工作階段、多 agent 或多入口；是否真的建立多個 threads 是產品 cardinality 決策。沒有官方資料支持為單一連續聊天室預先建立多 thread 會自動提升品質。

## 3. 三個方案

| 方案 | 形狀 | 優點 | 主要代價 |
|---|---|---|---|
| **A．第一版一個主要 thread；Memory 以 JD 為 scope（建議）** | `JD/document → one current conversation thread`；`JD/document → one semantic Memory namespace`。兩者 identity 分離，日後可讓同一 JD 的其他 thread 使用相同 Memory | 符合目前一個聊天室的產品體驗；避免對話碎片與合併問題；又保留成熟 Store 的跨 thread 能力 | 需在責任上區分 document identity 與 thread identity，但不必現在建立多 thread UI／API |
| **B．第一版允許一份 JD 多個 threads，共用 JD Memory** | 員工可另開訪談、審核、專題等 threads | 長任務可分題、隔離短期 context | 員工要選 thread；原始對話與待辦可能分散；需處理並行更新、routing、合併與顯示，現在沒有產品需求 |
| **C．Memory 直接綁定唯一 thread** | thread ID 同時作 conversation 與 Memory scope | 表面欄位最少 | 把兩種 lifecycle 混在一起；日後分 thread、重建 conversation 或遷移時會牽動 Memory authority，違背框架的責任分離 |

## 4. 建議 A 的白話語意

```text
一份員工 JD 文件
  ├─ 一個目前對員工可見的長期聊天室（thread）
  └─ 一份只屬於這份 JD 的長期 Memory

未來若真的新增第二個 thread：
  ├─ thread A 有自己的短期對話與 checkpoint
  ├─ thread B 有自己的短期對話與 checkpoint
  └─ 兩者都讀寫同一份 JD Memory
```

第一版只建立 A 的第一個 thread，不建立 thread list、切換 UI、merge policy 或多 agent。設計上只避免把 Memory ownership 定義成「屬於 thread」；它應屬於 JD／document scope。這不要求現在預做複雜 1:N 功能。

## 5. 對既有 Working Decision 的精確修正

- `MEM-D002` 原本的「一名員工對應一份隔離文件、一個持續訪談 thread 與一份 JD」仍可作第一版產品 cardinality。
- 需要補清楚的是：**一個 thread 是第一版 UI／conversation 選擇，不是 Memory 的 ownership 邊界。**
- `LLM-Q004` 的「一份 JD 一個持久 thread」應理解為第一版只有一個主要 conversation thread；不代表未來第二個 thread 必須建立第二份 Memory。
- 不加入跨 JD 共用 Memory；不同員工／JD 的 Memory 仍完全隔離。

## 6. 重開條件

只有出現以下需求之一才考慮方案 B：

1. 同一員工／JD 必須同時有兩個獨立聊天室或工作入口；
2. 需要平行 specialist／subagent threads，且共用同一 JD Memory；
3. 真實長訪談證明單一 conversation thread 的 context／操作體驗不可接受；
4. 需要把訪談、主管審核或全面檢查分成可獨立保存的 conversations。

若沒有這些證據，建立多 thread 只會增加產品與一致性成本。

## 7. 官方來源

- [LangGraph Persistence：Checkpointer 與跨 thread Store](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangChain Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [OpenAI Agents SDK Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK Sandbox agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [Anthropic Managed Agents Sessions](https://platform.claude.com/docs/en/managed-agents/sessions)
- [Anthropic Managed Agents Memory Stores](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic Session Operations：Memory Store 與 session lifecycle 分離](https://platform.claude.com/docs/en/managed-agents/session-operations)

## 8. G3 裁決與下一個 gate

Product Owner 於 2026-09-04 核准方案 A：第一版每份 JD 只有一個主要 thread，長期 Memory 以 JD／document 為 scope；保留日後同一 JD 多個 threads 共用 Memory 的能力，但目前不展開多 thread UI、API、routing、merge 或並行寫入功能。

下一步回到已完成 G2 研究的 `LLM-Q005`，不重做相同研究。
