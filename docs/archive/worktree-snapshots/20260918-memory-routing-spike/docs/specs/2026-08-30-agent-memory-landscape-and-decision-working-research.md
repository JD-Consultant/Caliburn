# Agent Memory 市場流程、共同基線與方案決策工作研究

- 日期：2026-08-30；最近深潛更新：2026-08-31
- 狀態：**通用 Memory 研究已完成第二輪表徵收斂；尚未映射任何產品，不構成 ADR、施工規格或實作授權**
- 主題：研究最新 Agent／Assistant Memory 的產品流程、公開資料表徵、Memory Prompt、Memory Tool 與管理責任
- 本輪不處理：Caliburn 資料結構、LangGraph checkpoint／Store 分工、資料庫、Schema、API、JD 流程、RAG 接線與 migration

> **閱讀規則**：本文採「先理解市場真實做法，再決定產品方案」的順序。不得先把既有 `Domain Semantic Memory`、工作理解、Checkpoint、Store、LangMem 或任何舊元件當成答案，再回頭挑資料佐證。舊研究只能提供待複核線索；若與本文後續收斂衝突，必須列出差異並與 Owner 討論，不能自動沿用或靜默翻案。

> **範圍鎖定**：D1～D7 的研究與 Owner 暫時裁決，全部指向「通用 LLM Memory 的最佳行為方案」。資料來自多家官方做法的比較與綜合，不先考慮 Caliburn、職務訪談、JD、第一版 UI 或現行程式限制。只有通用方案整體收斂後，才另開產品 mapping；不得把通用結論直接寫成 Caliburn 需求。

> **暫時同意規則**：本文所有「Owner 已確認／已對齊／採用」都只代表**目前證據下，通用 LLM Memory 研究階段的暫時最佳判斷**。它不是不可推翻的永久決策，也不代表 Caliburn 必須照搬。後續做 Caliburn 產品 mapping 時，若產品目標、成本、風險、框架能力或新證據顯示其他方式更適合，可以重新比較並翻案；但必須先列出差異、證據與取捨，和 Owner 討論，不能靜默改寫。

## 0. 白話目的

這份文檔先回答四件事：

1. OpenAI、Anthropic 與其他主要大廠，現在實際公開了哪些 Memory 流程？
2. 成熟 Agent 框架與專用 Memory 產品，又提供哪些不同流程？
3. 各家共同擁有什麼？這些共同點可作為哪些高可信基線？
4. 各家真正不同的地方是什麼？哪些是後續必須逐項討論的選項？

研究完成後，才依產品目標比較效果、正確性、長期連續性、成本、延遲、可修正性、透明度與成熟度，形成最佳方案。本文會研究大廠**已公開的技術 contract**，例如資料表徵、Prompt 責任、Tool 操作與 runtime 管理邊界；但現在**不替 Caliburn 設計 schema／API／資料庫，也不先選框架或授權施工**。

## 1. 研究方法與證據門檻

### 1.1 納入條件

只有符合以下條件的資料，才可進入主要比較：

1. 來自官方產品、官方文件、官方工程文章或官方原始碼倉庫；
2. 截至 2026-08-31 仍是目前版本、已出貨能力或明確標示的 Preview／Beta；
3. 能看出至少部分 `寫入／更新／召回／注入／刪除` 流程，而不只是泛稱「支援 Memory」；
4. 能區分已公開事實與我們的推論；
5. 舊版機制若已被新版本取代，只能作歷史對照，不能當現在基線。

### 1.2 研究集合

本輪不是窮舉全世界每個小套件，而是涵蓋目前**有獨立 Memory 政策、具有決策代表性**的主要家族：

- 第一優先大廠：OpenAI ChatGPT／Codex／API、Anthropic Claude／Claude Code／API；
- 大廠託管平台：Google Gemini Enterprise Agent Platform Memory Bank、AWS Bedrock AgentCore Memory、Microsoft Foundry Memory；
- 通用 Agent 框架：LangGraph／LangMem、PydanticAI Harness、AutoGen、CrewAI、LlamaIndex；
- 專用 Memory 系統：Letta、Mem0、Zep／Graphiti。

若後續發現另一個仍在維護、流程獨特且能影響決策的主流方案，再補入本文；不因套件數量多就提高證據權重。

### 1.3 不混為一談的四種東西

| 名稱 | 本文暫定意義 | 不等於 |
| --- | --- | --- |
| Active conversation context | 當次模型真正看得到的近期訊息、工具結果與必要上下文 | 跨會話長期 Memory |
| Conversation history／event log | 可回查的原始對話或事件紀錄 | 已整理、已修正的語意理解 |
| Compaction | 為了 token 預算壓縮或清除 active context | 長期 Memory 的完整替代品 |
| Long-term Memory | 可跨回合／跨會話保留、更新並在需要時召回的資訊 | Prompt cache、完整 prompt 重播或單純向量資料庫 |

### 1.3.1 Long-term Memory 內仍有不同用途

LangGraph、AWS、LlamaIndex、Mem0 等官方資料使用的分類並不完全一致；本文只正規化用途，不宣稱心理學分類與軟體實作一一對應：

| 用途 | 典型內容 | 現行代表 | 重要邊界 |
| --- | --- | --- | --- |
| Semantic／profile memory | 使用者偏好、穩定事實、領域理解、目前狀態 | Claude topics、Google facts、AWS semantic/user preference、LangGraph profile/collection | 可修訂；不是原始 transcript，也不是 semantic search 的同義詞 |
| Episodic memory | 曾發生的事件、過去 agent 行動、成功／失敗案例 | AWS episodic、Zep episodes、LangGraph few-shot examples | 常用於回顧或示例；不應無條件全量注入 |
| Procedural memory | agent 如何做事的規則、prompt／workflow 改進 | LangGraph procedural、Mem0 procedural、Letta skills | 若會改 system policy，風險與 authority 高於一般使用者事實；不能讓低信任 Memory 靜默覆蓋受控規則 |
| Conversation source | 原始訊息、工具結果、事件序列 | OpenAI Conversations、Google Sessions、AWS events、Claude chat search | 是 provenance／回查來源，不自動等於整理後 Memory |

因此「支援 Memory」不足以代表支援全部用途。框架只提供向量搜尋、message history 或 JSON Store 時，不得宣稱已完成 semantic extraction、episodic learning、procedural policy 與治理全套。

### 1.4 文檔中的四個決策層級

為避免後面把「大廠怎麼做」、「跨家共同點」、「目前暫時同意」與「Caliburn 最終怎麼做」混成一件事，本文固定保留四層：

1. **各家官方公開事實**：逐家記錄 OpenAI、Anthropic、Google、AWS 與框架實際公開的行為、限制和未公開部分。即使本文最後選了別的通用方案，也不刪掉各家差異。
2. **跨家共同基線候選**：多家都出現、通常代表成熟系統不可缺少的行為。共同出現提高可信度，但仍不是數學證明，也尚未自動成為 Caliburn 需求。
3. **通用方案的暫時裁決**：Owner 在目前證據下接受的最佳通用行為，用來讓研究能繼續往下一題收斂；後續新證據或整體一致性檢查仍可經討論翻案。
4. **Caliburn 產品 mapping／ADR**：通用方案完成後，才把產品目標、單機使用方式、成本、框架與既有資料納入，逐項決定採用、簡化、替換或不採用。只有後續正式 ADR 才能成為施工 authority。

因此本文不能只保留「最後選了 C」而刪掉 A／B 或各家做法；那些資料正是日後判斷 Caliburn 是否需要改選的依據。

## 2. 正規化比較流程

不同廠商使用不同名詞。為了能公平比較，本文只把它們映射到同一組問題，不代表各家內部實作相同：

```text
來源事件／對話
    ↓
當前對話連續性
    ↓
是否選取為長期資訊
    ↓
抽取／整理／合併／更正
    ↓
持久 Memory
    ↓
自動召回或模型按需搜尋
    ↓
有界地加入當次 Context
    ↓
使用者或系統查看、修正、刪除
```

每個方案都用以下八個比較軸評估：

1. 來源保留；
2. 寫入時機；
3. Memory 單位與組織方式；
4. 更新、更正與淘汰；
5. 召回方式；
6. Context 注入方式；
7. 範圍隔離與控制；
8. 成熟度、延遲與成本。

## 3. 第一優先：OpenAI 與 Anthropic

### 3.1 OpenAI ChatGPT 與本機 Codex 的產品邊界

OpenAI 現行官方文件明確說明：ChatGPT web 使用 ChatGPT Memory；本機 Codex client 使用另一份 local Memory store 與控制面。兩者不能因為都叫 Memory，就被推論為共用同一套抽取器、資料表或 retrieval 演算法。

官方目前可直接驗證的共同產品行為只有：

1. Memory 用來把先前工作的有用 Context 帶到後續工作；
2. 必須永遠成立的規則仍要放在 `AGENTS.md` 或受控文件，Memory 只是 recall layer；
3. 使用既有 Memory 與讓目前聊天貢獻未來 Memory 是可分離控制；
4. ChatGPT Memory 與本機 Codex Memory 有各自的設定與儲存邊界。

官方來源：

- [OpenAI — Memories：ChatGPT 與 Codex 使用不同 store／controls](https://learn.chatgpt.com/docs/customization/memories)

OpenAI 於 2026 年公開的 Dreaming V3 文章已能證明：ChatGPT 會在背景參考多段聊天、綜合出會持續更新的 Memory state，並以可供使用者檢視與調整的 Memory summary 呈現重點。因此「ChatGPT 有背景綜合」不再是推測。仍未公開的是內部 record schema、Memory Prompt、ranking、embedding、衝突合併細節、觸發門檻，以及它是否與本機 Codex 共用實作；本文只採用已公開的高階流程，不替私有細節補答案。

- [OpenAI — Dreaming: Better memory for a more helpful ChatGPT（2026）](https://openai.com/index/chatgpt-memory-dreaming/)

### 3.2 OpenAI Codex

Codex 開源倉庫目前已公開實際運行的兩階段 Memory pipeline、Prompt templates、檔案布局與 read path；不再只能從產品說明推測。流程可正規化為：

```text
合資格、已閒置且非 ephemeral／sub-agent 的 rollout
    ↓
Phase 1：逐 rollout 過濾 response items，模型輸出 structured raw_memory、rollout_summary、可選 rollout_slug
    ↓
Phase 2：依 usage／recency 選取，建立 raw_memories.md、rollout_summaries 與 git-style diff
    ↓
單一受限 consolidation agent 更新 MEMORY.md、memory_summary.md 與可選 skills/
    ↓
新工作預載小型 memory_summary；需要時關鍵字查 MEMORY.md，再讀 1～2 份詳細摘要／Skill／原始 rollout
```

公開原始碼還能直接驗證以下管理方式：

1. Phase 1 是模型的 structured output，主要內容欄是 `raw_memory`、`rollout_summary` 與可選的 `rollout_slug`；runtime 負責 rollout 身分、claim／lease、重試退避、時間與成功／無輸出／失敗狀態。
2. Phase 2 不靠模型填一個巨大 Memory JSON；它把候選與摘要整理成檔案工作區，使用 git-style diff 找新增、修改與刪除，再由受限 agent 更新文件。
3. `memory_summary.md` 是 prompt-loaded 的高密度導覽；`MEMORY.md` 是可搜尋 handbook；`rollout_summaries/` 與原始 rollout 提供逐步深入的細節與依據。
4. read prompt 明定 quick pass：先讀 summary、再搜尋 `MEMORY.md`、只在被指向時開 1～2 份詳細檔；找不到就停止，不掃完整歷史。
5. Memory 是可能過時的 guidance；對會漂移且容易驗證的事要即時重查，使用未驗證 Memory 時需揭露其可能過時。
6. 背景抽取允許合法的 `succeeded_no_output`；並以 bounded selection、global lock、watermark、retry backoff 與 usage telemetry 控制成本和並行。

官方明確提醒：需要保證執行的規則仍應放在 `AGENTS.md` 或受控文件；Memory 是 recall layer，不是唯一規則來源。

官方來源：

- [OpenAI Codex 開源倉庫 — Memories pipeline README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)
- [OpenAI Codex — Phase 1 Memory Prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/stage_one_system.md)
- [OpenAI Codex — Phase 2 Consolidation Prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)
- [OpenAI Codex — Memory Read Prompt](https://github.com/openai/codex/blob/main/codex-rs/ext/memories/templates/memories/read_path.md)
- [OpenAI Agents SDK — Sandbox Agent Memory](https://openai.github.io/openai-agents-python/sandbox/memory/)

公開資料**能證明**：開源 Codex 採兩階段背景抽取／整併、分層檔案表徵、漸進式讀取、usage-based selection、受限 consolidation agent 與明確 Prompt contract。公開資料**不能證明**：Codex 與 ChatGPT Dreaming 共用相同內部引擎，也不能證明 coding-agent 專用的 task／cwd／rollout schema 適合其他領域。

### 3.3 OpenAI API 的 conversation state 與 compaction

OpenAI API 公開提供兩個相關但不同的 primitive：

- Conversations／Responses 可持久保存長期 conversation object，包括訊息、工具呼叫與工具結果；`previous_response_id` 也可串接回應狀態；
- Server-side compaction 在 Context 接近門檻時壓縮舊內容，讓長任務繼續，但壓縮內容不是公開可編輯的語意 Memory。

官方來源：

- [OpenAI API — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI API — Compaction](https://developers.openai.com/api/docs/guides/compaction)

這證明 conversation continuity 與 context compaction 都是正式 primitive；它們本身不等於 ChatGPT／Codex 的跨對話語意 Memory。

#### 3.3.1 OpenAI Agents SDK Sandbox Memory（Beta）

OpenAI Agents SDK 另公開一套可供開發者直接使用的 Sandbox Agent Memory。它與 SDK `Session` 的 conversation history 明確分離：Session 保存訊息 items；Sandbox Memory 把過往 run 的可重用教訓整理成 workspace files。

其公開布局與 Codex 類似：

```text
sessions/<rollout-id>.jsonl
memories/memory_summary.md
memories/MEMORY.md
memories/raw_memories.md
memories/raw_memories/<rollout-id>.md
memories/rollout_summaries/<rollout-id>_<slug>.md
memories/skills/
```

讀取採 progressive disclosure：先把小型 `memory_summary.md` 注入 developer prompt，相關時再搜尋 `MEMORY.md` 並開 rollout summary。寫入採兩階段：Phase 1 從 conversation 產生摘要與 raw extract；Phase 2 consolidation 再形成 `MEMORY.md` 與 summary。應用可用 `MemoryGenerateConfig.extra_prompt` 告訴 generator 哪些 domain signals 值得重視，也能分別關閉 read、generate 或 live update。

這是目前 OpenAI 最具體的開發者可用 Memory 表徵，但仍標示 Beta；它證明「框架可提供 pipeline／layout／progressive disclosure」，也同時證明產品仍要提供 domain-specific `extra_prompt`，框架不會自動知道某領域應記住什麼。

### 3.4 Anthropic Claude

Claude 目前公開流程可正規化為：

```text
目前聊天
    ↓
在對話期間讀取／更新個別、分類的 Memory topics
    ↓
後續聊天套用相關 topics

過往原始聊天
    ↓
獨立的 chat search
    ↓
需要時回傳結果並連回原始聊天
```

2026-07-10 的新版以個別分類條目取代舊的每日綜合摘要。Memory 和 chat search 是兩個互補功能：Memory 保持跨對話理解；chat search 在需要精確歷史時搜尋並提供來源。

官方來源：

- [Anthropic Support — Claude chat search and memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Anthropic — Claude release notes](https://support.claude.com/en/articles/12138966-release-notes)

公開資料**能證明**：現行 Claude 不再只靠一份總摘要，且持久理解與原始聊天回查分離。公開資料**不能證明**：分類 topics 的私有 schema、排序模型或底層是否採向量資料庫。

### 3.5 Claude Code 與 Anthropic Memory Tool

Claude Code／Memory Tool 公開流程可正規化為：

```text
小型主索引／主要記事預先提供
    ↓
詳細主題檔依需要 read／search
    ↓
模型依 Memory Prompt 判斷值得保存時，用 file-style tool create／str_replace／insert／delete／rename
    ↓
跨 session 重用
```

Claude Code 將開發者維護的 `CLAUDE.md` 與模型自行維護的 auto memory 分開；`MEMORY.md` 只預載有界前段，其他主題檔按需讀取。Anthropic Memory Tool 則提供 client-side 的檔案操作 contract，實際儲存由應用程式掌控。它的資料表徵不是固定 JSON schema，而是 `/memories` 下由模型與應用共同治理的文字檔／目錄。

Memory Tool 被啟用時，Anthropic 會自動加入 Memory protocol system instruction：工作前先 `view` Memory 目錄、進行中持續記錄需要跨 Context 保留的進度，並假設 Context 可能中斷。Tool 自身的描述又要求保持目錄 coherent／organized；應用可另用簡短 Prompt 限定「只保存與某主題有關的資料」。官方 SDK 範例更明確示範：不要把 transcript 整份複製成 Memory、保存使用者 facts／preferences、遇到更正就更新或刪除過時內容。不過最後這組是官方範例 Prompt，不是平台保證自動注入的固定政策。

各層責任如下：

- 模型填：command、memory path、要新增／替換／插入的文字；
- Tool／應用填與管：實際 store、path sandbox、錯誤回傳、檔案大小／分頁、ACL；
- Managed Agents 服務填：store／memory ID、版本、content hash、created time、workspace scope；每次 mutation 建立 immutable version；
- 產品 Prompt 決定：哪些資料值得保存、如何分類、何時更新；Memory Tool 本身不替產品決定 domain schema。

官方 Context Engineering 資料另外把 compaction、tool-result clearing 與 Memory 視為三種互補策略。

官方來源：

- [Claude Code — How Claude remembers your project](https://code.claude.com/docs/en/memory)
- [Anthropic API — Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic 官方 Python SDK — Memory Tool 範例 Prompt](https://github.com/anthropics/anthropic-sdk-python/blob/main/examples/memory/basic.py)
- [Anthropic Managed Agents — Agent Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic Cookbook — Context engineering tools（2026-03-20）](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools)
- [Anthropic API — Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)

公開資料**能證明**：「小型有界入口＋按需讀取詳細內容＋模型可維護 Memory」是已出貨做法。公開資料**不能證明**：此檔案型態是所有非 coding 產品的最佳表徵。

## 4. 其他大廠託管 Memory

### 4.1 Google Gemini Enterprise Agent Platform Memory Bank

```text
來源 conversation／events 或預先抽取的 facts
    ↓
依 managed／custom topics 選取值得保存的資訊
    ↓
在相同 scope 內 extraction＋consolidation
    ↓
建立、更新或刪除 memories
    ↓
建立可檢視、可 rollback 的 revisions
    ↓
依 scope 列出全部、filter 或 similarity search
    ↓
由 ADK Tool 或應用程式加入 agent 流程
```

Google 最新公開流程已不只是「抽取 facts 後做向量搜尋」。Memory Bank 會判斷資訊是否值得長期保存，依 topic 抽取，再與同一 scope 的既有 memories consolidation；每次結果明列 `CREATED／UPDATED／DELETED`。Current `Memory` 只反映最新整併狀態，歷史 mutation 另存在 `MemoryRevision`，可檢查 extraction／consolidation 中間結果並 rollback。官方建議 production agents 通常把 memory generation 放在背景；retrieval 則可取全部、依 filter 或相似度搜尋。

- [Google Cloud — Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google Cloud — Fetch memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [Google Cloud — Memory revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)

公開資料**能證明**：自動 extraction、scope 內 consolidation、版本歷史、rollback 與多種 retrieval 都是 Google 目前已公開的 managed Memory 流程。公開 REST 仍位於 `v1beta1` 且平台快速演進，因此它能強力佐證機制方向，但 production 成熟度仍須和功能完整度分開評估。

### 4.2 AWS Bedrock AgentCore Memory

```text
session 中的原始 turn events
    ↓
短期記憶保存事件
    ↓
背景依 strategy 抽取／整併 insights
    ↓
長期 memory records
    ↓
語意召回並加入後續推理
```

AWS 明確區分保存原始事件的 short-term memory 與從多次互動抽取的 long-term memory；long-term strategies 包含 semantic、summarization、user preference、episodic 與 custom。抽取是非同步流程，可能不是立即可讀。

- [AWS — AgentCore Memory overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)
- [AWS — Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [AWS — Saving and retrieving long-term insights](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-saving-and-retrieving-insights.html)

### 4.3 Microsoft Foundry Memory

```text
持久 conversation／transcript
    ↓
每次模型呼叫前召回相關 memories
    ↓
模型處理本輪
    ↓
每輪後背景抽取／更新 user-profile memories
```

Microsoft 的 hosted memory provider 會在 model call 前召回、在每輪後更新。官方目前標示 Public Preview、無 SLA 且不建議 production，因此只作方向與 API 形狀證據。

- [Microsoft Learn — Foundry hosted agent with memory](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-memory-hosted-agent)
- [Microsoft Learn — Agent Framework concepts](https://learn.microsoft.com/en-us/agent-framework/concepts/agents/)

## 5. 通用框架與專用 Memory 方案

### 5.1 LangGraph／LangMem

LangGraph 官方區分 thread-scoped short-term memory 與自訂 namespace 下、可跨 thread 的 long-term memory；長期 semantic memory 可採單一 profile 或多筆 collection。Profile 變大時整份更新容易出錯；collection 較容易新增且通常 recall 較高，但更新、搜尋與組成完整 Context 更困難。寫入可在 hot path 完成，也可交給背景工作。

LangMem 在此基礎上提供兩條不同寫入路徑：

1. hot path `manage_memory` tool：模型填 `content`、既有 `id`（update／delete 時）與 `action=create|update|delete`；runtime 由 config 展開 namespace，不讓模型填 principal／scope；
2. background `create_memory_manager`／`create_memory_store_manager`：輸入 messages 與相關 existing memories，由模型依 Prompt＋schema 產生 insert／update／delete effects，並可先搜尋相關 Memory 再 consolidation。

預設 unstructured Memory 只是一個 standalone `content: str`；也可由應用傳入 Pydantic schema。預設 manager Prompt 要求保留 surprising／persistent、dense／complete 而非重疊的 Memory；預設 tool Prompt 則要求在出現新偏好、明確 remember、重要工作 Context 或發現 Memory 過時時呼叫。這些都是可覆寫的通用起點，不是任何特定產品領域的完成 schema。

這再次證明 LangMem 是 Memory policy／CRUD／reconcile helper，不是 LangGraph Store 本身自動擁有的語意；應用仍需定義 domain instructions 與 schema。

重要限制：LangGraph 提供 persistence／Store／search primitive，不替產品決定記憶語意；LangMem 目前仍是 0.0.x，GitHub Releases 頁也尚無正式 release，不能只因功能最接近就視為成熟度已證明。

- [LangChain／LangGraph — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [LangGraph — Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [LangMem — GitHub](https://github.com/langchain-ai/langmem)
- [LangMem — GitHub Releases](https://github.com/langchain-ai/langmem/releases)
- [LangMem — Conceptual guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [LangMem — Memory manager source（預設 Prompt 與 Memory schema）](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)
- [LangMem — Memory tools API（tool signature 與預設 instructions）](https://langchain-ai.github.io/langmem/reference/tools/)

### 5.2 PydanticAI Harness

PydanticAI Harness 提供兩個互補能力：

1. `Memory`：Markdown notebook、bounded `MEMORY.md` 預載、其他檔案按需 read／search，並提供寫入、替換與刪除；
2. `ConversationSearch`：從持久 conversation snapshots 搜尋 compaction 已移出 active context 的原始訊息。

自動 injection 有明確 token／line 上限，namespace 由 application runtime 解出而不進 model-facing schema，也支援 optimistic concurrency。它明確警告：model-written Memory 是 untrusted content；user-role delimiter 只能降低權限，不是硬安全邊界；內建 Memory 不帶經驗證 provenance，literal search 也不等於 semantic retrieval。

這是目前找到最接近「Claude Code 式主索引＋按需詳細 Memory＋原始對話搜尋」的框架實作之一；但 Harness 官方仍是 0.x，API 可在 minor release 改變，成熟度必須和功能分開評估。

- [PydanticAI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/)
- [PydanticAI Harness — Conversation Search](https://pydantic.dev/docs/ai/harness/conversation-search/)
- [PydanticAI — Message history](https://pydantic.dev/docs/ai/core-concepts/message-history/)

### 5.3 CrewAI

CrewAI 1.15.18 以單一 `Memory` API 取代早期分散的 short-term／long-term／entity／external memory。它可在保存時由 LLM 推斷 scope、category、importance 與 metadata；`extract_memories` 把 raw task output 拆成離散 statements；召回可採 semantic similarity、recency、importance 複合分數，並提供 shallow／deep recall。Scope 是樹狀範圍，slice 可組合多個 scope 並設為 read-only。

批次 `remember_many` 可非阻塞寫入，但 `recall` 先 drain pending writes，形成 read barrier；相似內容的 consolidation 會決定 keep／update／delete／insert。這是功能完整的自動化方案，也意味著保存與深度 recall 可能增加模型、embedding、延遲與成本。

這是一個高度自動化、功能完整的對照方案，但其預設以 task output 為主要抽取來源，是否符合長期自然訪談仍需另行判斷，不能只因功能多就選用。

- [CrewAI — Unified Memory](https://docs.crewai.com/concepts/memory)

### 5.4 AutoGen

AutoGen 提供可替換的 `Memory` protocol：`add`、`query`、`update_context`、`clear`、`close`，並有 List／ChromaDB／Redis／Mem0 integrations。官方明確把「何時加入內容、如何抽取」留給應用程式。

因此 AutoGen 能證明「Memory 作為可替換 Context provider」是成熟框架介面，但它不是一套完整的記憶政策。

- [Microsoft AutoGen — Memory and RAG](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/memory.html)

### 5.5 LlamaIndex

現行 `Memory` 取代已 deprecated 的 `ChatMemoryBuffer`。它把近期訊息放在 FIFO short-term block，超出 token 門檻時將較舊訊息移入可配置的 long-term blocks，再於讀取時合併短期與長期內容。官方提供 static、fact extraction 與 vector blocks。

此方案特別擅長 context-window 管理；FactExtraction block 在容量壓力下可能透過模型做 reduction／summarization，因此「能保存長期資訊」不等於「保證保留全部細節」。舊 `ChatMemoryBuffer`、`ChatSummaryMemoryBuffer`、`VectorMemory` 與 `SimpleComposableMemory` 已在官方頁面列入 deprecated 區段，不能再當現行方案。

- [LlamaIndex — Memory](https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/memory/)

### 5.6 Letta

Letta 現行所有 agent 使用 Git-backed `MemFS`，不再以舊 core／archival blocks 當主要基線。每個 agent 擁有一個 Memory repository；`system/` 下的 Markdown 每輪放入 system prompt，其他檔案只在需要時由普通 file tools 讀取，而檔案樹會持續當作導覽 signposts。Conversation-history search 與 MemFS 分離。

每次 Memory edit 都成為 Git commit，因此具備版本歷史與衝突邊界；dreaming／memory doctor 以 worktree 背景整理。語意／向量索引不是預設能力：一般 file search 是基線，semantic／hybrid search 需另裝 mod。Shared memory 目前使用 Git repository；舊 shared memory block API 被官方標為 legacy，應遷移。

- [Letta — MemFS](https://docs.letta.com/concepts/memfs)
- [Letta — Memory & dreaming](https://docs.letta.com/configuration/memory)
- [Letta — Shared memory：舊 shared block 為 legacy](https://docs.letta.com/concepts/shared-memory)

### 5.7 Mem0

Mem0 V3 官方 migration 與 Add Memory 文件把新流程描述為單次 LLM、ADD-only extraction；既有 facts 不在 extraction 中被覆寫或刪除，時間變化主要由 multi-signal retrieval（semantic＋keyword＋entity＋temporal）排序。Platform add 是非同步工作，先回 `PENDING` event，再查成功或失敗；expiration／delete 仍是獨立生命週期操作。

但同一套現行官方文件存在不能忽略的矛盾：`Memory Types` 頁又寫 `infer=True` 會先搜尋既有 candidates，再由單次 LLM 決定 `ADD／UPDATE／DELETE`，而 Add／V3 migration 頁明確寫 Platform 與 OSS 均為 ADD-only。這表示不能只靠「Mem0」品牌名推論 exact semantics；採用前必須鎖定實際 SDK／backend／endpoint 版本，並以該版本原始碼或 runtime 行為驗證。另一項現行限制是：Python OSS 的 `memory_type` 只有 procedural 已實作，semantic／episodic enum 尚未實作。

- [Mem0 — Platform V2 → V3 migration](https://docs.mem0.ai/migration/platform-v2-to-v3)
- [Mem0 — Add Memory](https://docs.mem0.ai/core-concepts/memory-operations/add)
- [Mem0 — Memory Types 與目前實作狀態](https://docs.mem0.ai/core-concepts/memory-types)
- [Mem0 — V3 Add Memories API](https://docs.mem0.ai/api-reference/memory/add-memories)

### 5.8 Zep／Graphiti

Graphiti 將每次 ingestion 保存為 episode，再抽取具有時間資訊的 entities、relationships 與 facts；episode 保留來源，edge 可具 valid／invalid time，因此能保留歷史並使舊關係失效。召回可混合 BM25、semantic、time 與 graph traversal，並可用 RRF、MMR、cross-encoder、node distance 或 episode mentions rerank。Zep managed 版則另外提供治理與大規模服務能力。

它適合關係與時效性很強的情境，但引入 temporal knowledge graph、ontology、graph backend 與多階段 LLM extraction 的語意、運維及成本最高。官方公開 benchmark 是供應商自己的結果，不能直接證明它在所有產品都優於較簡單表示法。

- [Zep Graphiti — Overview](https://help.getzep.com/graphiti/getting-started/overview)
- [Zep Graphiti — Adding episodes](https://help.getzep.com/graphiti/core-concepts/adding-episodes)
- [Zep Graphiti — Searching](https://help.getzep.com/graphiti/working-with-data/searching)
- [Zep — Episodes 與原始來源回查](https://help.getzep.com/episodes)

## 6. 跨家共同點

### 6.1 第一層：跨大廠近乎一致的通用必要基線

| 編號 | 必要基線 | 交叉證據與精確邊界 |
| --- | --- | --- |
| B1 | Active context、conversation source 與 durable Semantic Memory 分層 | OpenAI Conversation／Codex、Claude chat search／Memory、Google Sessions／Memory Bank、AWS short／long-term 都分層；三者可互補但不能互相冒充 |
| B2 | 不把全部歷史永久塞入每次模型請求 | OpenAI compaction、Claude Code bounded index、Google／AWS retrieval、各框架 token budget 都採有界 Context；即使放得下，長歷史也會增加成本與干擾 |
| B3 | 保存資格、寫入／整理、召回與注入是不同步驟 | 「存在資料」不代表應成為 Memory，也不代表每輪要注入；每一層有不同失敗、成本與控制語意 |
| B4 | Durable Memory 是選取層，空結果合法 | Codex eligible/useful、Claude topic policy、Google valuable topics、AWS strategies 都不要求每輪一定產生 Memory |
| B5 | Scope／namespace 與 principal／AuthZ 必須由受信任 runtime 控制 | Google exact scope＋IAM、AWS actor／namespace＋IAM、Anthropic store access、Pydantic runtime namespace 都不讓模型自行決定安全身分 |
| B6 | Recall 與 Context injection 必須有界 | top-k、token／line limits、read/search、按需檔案與相似度搜尋都是現行做法；全量注入不是可擴展基線 |
| B7 | Memory 必須具有可修訂生命週期 | 成熟系統提供 update／delete／consolidation、revision、expiration 或 current-state ranking；只追加永不處理變化不是通用要求，Mem0 V3 是特定設計選項 |

這七項是本輪證據最強的共同核心。它們的「共同出現」代表多個獨立成熟系統在相同問題上收斂，因此可當成預設必要基線；但這仍是工程歸納，不是「所有場景效果最佳」的數學證明。日後若要排除其中一項，應提出清楚的產品原因與相反證據，而不能只因框架缺功能就降低需求。

### 6.2 第二層：成熟 production 系統反覆出現的治理基線

這些能力不是每個輕量框架都內建，但 OpenAI／Anthropic／Google／AWS 或多個成熟方案已反覆證明其 production 價值。缺少它們不一定代表最小 demo 不能運作，卻會把正確性、安全或維運責任留給產品自行補足。

| 編號 | 成熟治理基線 | 代表證據 |
| --- | --- | --- |
| B8 | 原始 source／events 與衍生 Memory 分開保留 | Codex supporting evidence、Claude chat search、Google SessionEvents／revisions、AWS raw events、Zep episodes |
| B9 | Hot path 與 background 依正確性期限混合 | Claude topics／Memory Tool 支援即時修正；Codex、Google、AWS、Anthropic Dreams 支援背景抽取或 consolidation |
| B10 | 發布狀態、版本與並行衝突可觀察 | Anthropic immutable versions＋content hash、Google revisions／rollback、Letta Git、CrewAI read barrier、AWS ingestion status／redrive |
| B11 | 使用既有 Memory 與由本次來源學習分離 | Codex chat-level use／contribute、Claude pause／incognito；它們是不同隱私與行為控制 |
| B12 | Persistence eligibility 先於 durable write | Claude 敏感 topic、Codex eligible chats／redaction、Google topics＋空結果警告、AWS strategies 都表明「有用」與「允許保存」不是同一判斷 |
| B13 | Memory 是可錯、可污染的低權限資料 | Anthropic、Google、AWS 與 Pydantic 都直接警告 prompt injection／memory poisoning；Memory 不得升格為 system policy 或權限來源 |
| B14 | 成本、延遲、失敗與 recall 行為需要 observability | AWS ingestion jobs／CloudWatch、Anthropic event stream／dream usage、Google operations／revisions、CrewAI match reasons／barrier 都讓非同步與召回不再是黑盒 |

### 6.3 仍屬可選、不能因「大廠有人做」就升格為通用要求

| 可選能力 | 現行代表 | 為什麼不能直接列為必要 |
| --- | --- | --- |
| 文字 topics／notebook／原子 facts／Git files／temporal graph | Claude、Google／AWS、Letta、Zep 各自不同 | 表徵取決於資料關係、修訂粒度、檢索與操作成本，沒有跨家唯一答案 |
| 向量、lexical、hybrid、entity、graph 或 reranker | Google、Mem0、CrewAI、Pydantic、Letta、Graphiti | Retrieval engine 是可替換策略；exact ID／filter 查詢甚至不需要向量 |
| 每輪更新、背景批次或獨立 Dreaming | Claude、Codex、Google／AWS、Anthropic Dreams、Letta | 何時更新取決於下一個依賴點、延遲與成本，不能固定成單一時機 |
| 使用者直接編輯 Memory | Claude、Anthropic store API、Pydantic／Letta files | 可查看／更正／刪除很有價值，但直接暴露底層 schema 不是所有產品都適合 |
| 每筆精確 quote citation | Codex supporting evidence、Claude past-chat citation、Zep episode | 來源可追查是成熟能力；逐筆 quote 是否必填仍取決於稽核需求與成本 |
| Temporal graph／bi-temporal facts | Zep／Graphiti | 能力最強但 ingestion、ontology、storage 與維運成本也最高，非一般 Memory 預設 |
| 多 agent／第二模型審核／Dreaming | Anthropic Dreams、Letta、LangMem manager | 可提升大型整理品質，但不是每輪必需，應以資料量與錯誤成本觸發 |

## 7. 主要分歧與目前研究結論

### D1. Memory 何時更新

| 選項 | 已出現在哪些做法 | 優點 | 風險 |
| --- | --- | --- | --- |
| 對話中立即更新 | Claude topics、Memory Tool、顯式 saved memory | 新資料與更正很快生效 | 增加 hot-path 延遲；模型同輪多工 |
| 每輪結束後更新 | Microsoft provider、CrewAI task lifecycle | 主回覆與記憶更新責任較清楚 | 下一輪前才可用；可能產生短暫不一致 |
| 背景批次／consolidation | Codex、Google／AWS、Anthropic Dreams（Research Preview）、Letta dreaming | 不阻塞使用者；可跨多輪綜合 | eventual consistency；背景失敗、延遲或跳過 |
| 混合 | OpenAI、Anthropic 的產品組合；LangGraph／LangMem 可配置 | 明確更正快速生效，廣泛模式背景整理 | 規則最需要設計清楚，否則會重複寫入 |

**目前決定（Owner 於 2026-08-30 確認，仍可經後續證據與討論翻案）：採依「正確性期限」分流的混合模式。**

1. 使用者訊息送出後，原始 conversation 先持久保存；這不是 Semantic Memory 更新。
2. 目前 run 直接使用本輪訊息與 active context，因此不必先等待 Semantic Memory 更新才回答。
3. 新資訊依其目前的確認程度進入本輪：新事實保留其可信／待核實狀態，明確更正替換 active understanding，未解問題只以「尚未確認」的語意生效，用來避免錯誤結論或觸發澄清，**不得被當成已確認事實**。Semantic Memory 最遲必須在下一個依賴該理解的分析步驟或 run 開始前可用；若沒有後續依賴，不因 Memory 更新阻塞本輪回覆。正式狀態欄位與名稱留待實作研究。
4. 沒有持久價值的重複內容、閒聊或暫時訊息不寫入 Memory。
5. 去重、重新分類、跨多輪綜合、過時內容整理等不影響下一輪正確性的工作，可在背景完成，不阻塞使用者。

這項決定**不代表**每回合都要額外呼叫一次模型，也不代表每句話都要寫入 Memory。同一個主要 run 可以同時產生使用者回覆與少量 Memory effects；也可先保存 conversation，再於下一個依賴點前完成背景整理。是否拆成額外模型步驟屬後續實作研究。「本輪結束前」可以是低成本時的最佳努力，但不是硬性產品期限。

裁決理由：

- Claude 2026 Memory 會在交談過程中讀寫個別 topics，支援「下一次交談立即知道」的更新時效；
- OpenAI Codex 公開說明 background extraction／consolidation 是 best-effort recall layer，而不是立即一致、永遠執行的 authority；
- Google Memory Bank 建議：目前 run 不需要結果時，正式環境通常背景執行生成／consolidation，以避免不必要延遲。

直接來源：

- [Anthropic Support — Use Claude’s chat search and memory to build on previous context（2026-08 更新）](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [OpenAI Docs — Codex Memories（背景更新，不保證對話結束時立即完成）](https://learn.chatgpt.com/docs/customization/memories)
- [Google Cloud — Generate memories / Generating memories in the background](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Anthropic — Dreams（Research Preview；輸出為獨立新 store）](https://platform.claude.com/docs/en/managed-agents/dreams)

### D2. Memory 的主要表徵

| 選項 | 代表 | 核心取捨 |
| --- | --- | --- |
| 單一 profile／總體文件 | LangGraph profile 類型 | 易完整注入；變大後重寫容易遺漏或互相覆蓋 |
| 分類 topics | Claude 2026 | 組織直觀；分類與跨主題關係需處理 |
| 原子 facts／collection | Google、AWS、Mem0、CrewAI、LangMem | 易單筆更新與檢索；可能碎片化、重複或失去整體脈絡 |
| Notebook／主索引＋詳細檔 | OpenAI Codex／Agents SDK Sandbox Memory、Claude Code／Anthropic Memory Tool、PydanticAI | 適合小型索引預載、詳細內容按需閱讀與修訂；檔案組織本身成為新決策 |
| Git-backed 主索引＋按需檔案 | Letta MemFS | `system/` 每輪載入、其他檔案按需讀；可版本化，但檔案樹與內容治理仍需設計 |
| Temporal graph | Zep／Graphiti | 能表達關係與時間失效；複雜度最高 |

**目前決定（Owner 於 2026-08-30 確認，仍可經後續證據與討論翻案）：採「依主題組織的多筆、可獨立修訂、語意完整的 Memory 集合」。**

規則：

1. Memory 不是一份會反覆整體重寫的總摘要；摘要若存在，只能是可重建的顯示或導覽投影。
2. Memory 也不拆成脫離脈絡的極小詞彙或欄位碎片；每筆內容必須能在沒有相鄰項目時仍被正確理解。
3. 每筆 Memory 可以獨立新增、修正、淘汰；相關項目可依 topic／category 組織。
4. 現階段不升級成 temporal graph，也不先決定 notebook、資料庫 schema、欄位或框架。

例如，不把「使用系統 A」「每週使用」「追蹤案件」拆成三個缺乏脈絡的 facts，而保留成一筆完整內容：「使用者每週使用系統 A 追蹤案件處理狀態；重大案件會另外通知主管。」這只是展示 self-contained Memory 的通用例子，不代表本文已套入特定領域。

裁決理由：Claude 已從每日總摘要改成個別分類 topics；Google Memory Bank 也以 scope 下的獨立 self-contained facts 為單位進行新增、更新、刪除與 consolidation。OpenAI 開源 Codex／Agents SDK Sandbox Memory 進一步證明「小型 `memory_summary.md` 導覽＋可搜尋 `MEMORY.md`＋逐 rollout 詳細檔」是實際使用的分層表徵，但 ChatGPT 私有 Memory 的 record schema 仍未公開，因此不得把其 UI summary 推論成單一資料 blob。Letta 則證明 Git-backed Markdown tree 也是現行可行表徵，但不是跨家共同答案。

直接來源：

- [Anthropic Support — Use Claude’s chat search and memory to build on previous context](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Google Cloud — Agent Platform Memory Bank](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank)
- [OpenAI Codex — Memories pipeline README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)
- [OpenAI Agents SDK — Sandbox Agent Memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [Letta — MemFS](https://docs.letta.com/concepts/memfs)

### D3. Recall 由誰發動

- middleware 每輪自動召回；
- 模型覺得需要時呼叫 search／read；
- 小型核心預載，其餘按需搜尋；
- 自動先召回少量結果，信心不足再讓模型擴大搜尋。

**目前決定（Owner 於 2026-08-30 確認，仍可經後續證據與討論翻案）：採「有界自動召回＋模型按需 search／read」。**

1. 每次需要模型分析時，系統自動提供少量、與目前內容相關且有明確上限的 Memory。
2. 模型需要更早、更細或未被自動召回的內容時，可以主動 search／read 更多 Memory 或原始 conversation。
3. 不把全部長期 Memory 注入每次 prompt；這會隨時間增加 token、干擾與 stale-context 風險。
4. 不只依賴模型自行搜尋；模型可能不知道自己漏了什麼，因此完全 tool-only 會有 unknown-unknown 風險。
5. 此處尚未決定自動召回的筆數、token budget、排序公式、向量／關鍵字／混合檢索或 confidence 門檻。

裁決理由：OpenAI Docs 公開說明 Codex 可將既有 memories 注入未來 sessions，並把 summaries、durable entries、recent inputs 與 supporting evidence 分層保存；Anthropic 將已整理 Memory 與需要時透過 RAG tool call 搜尋 past chats 分開；Google 同時提供全取與 similarity retrieval。這些公開行為共同支持「有界預先 context＋按需細查」，而不是全量注入或完全依賴模型想起來才搜尋。

直接來源：

- [OpenAI Docs — Codex Memories](https://learn.chatgpt.com/docs/customization/memories)
- [Anthropic Support — Use Claude’s chat search and memory to build on previous context](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Google Cloud — Retrieve memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)

### D4. 更正與衝突如何表示

不同方案公開的行為並不完全相同：

| 來源 | 官方公開行為 | 能下的結論與限制 |
| --- | --- | --- |
| OpenAI Codex | 從 chats extraction，再以獨立 consolidation model 整理 global Memory；生成狀態含 durable entries、recent inputs 與 supporting evidence | 證明 active Memory 會整理，不證明其內部如何裁決衝突或是否逐筆保留 revision；不得替 OpenAI 推測 |
| Anthropic Claude | Memory 是可獨立更新的 topics；使用者可在對話中要求 change／forget，也可直接編輯或刪除 topic，修改後套用至後續對話 | 支持「更正 active head」，但消費型 Claude 未公開 topic 的內部 revision policy |
| Anthropic Managed Agents | 每次 Memory mutation 產生 immutable version；一般 retrieve 永遠回最新 head；版本可稽核、回復或 redact，且可在 live Memory 刪除後暫時保留 | 直接支持「active head 與隱藏版本歷史分離」；版本留存期與 API 仍是 Anthropic 產品細節，不能原樣照搬 |
| Google Memory Bank | consolidation 會依新資料新增、更新或移除 Memory，先檢查重複與矛盾；正常比較預設只使用最新 revision，舊 revision 可另外檢視 | 直接支持正常召回只用目前版本、歷史另查 |
| AWS AgentCore | semantic consolidation 使用 Add／Update／Skip；矛盾時依 confidence 更新或略過，並要求保留時間與具體細節 | 支持保守更新與時間脈絡；但以「seems／definitely」等語氣推 confidence 不適合直接當成任何使用者／領域事實的 authority 規則 |
| LangMem | agent／manager 可 create、update、delete；delete 可配置，functional API 允許產品把 removal 實作成 hard delete、soft delete 或降權 | 可直接承載 active Memory 更新，但框架本身不保證 immutable revision history，仍需由選定 backend 提供 |

**目前已確認部分（Owner 於 2026-08-30 確認，仍可經後續證據與討論翻案）：**

1. 使用者明確更正時，新理解取代 active Memory 的目前版本；舊理解不得繼續參與一般召回。
2. 舊版本不與新版本一起注入 prompt，而是留在獨立、預設不召回的 revision history，供診斷、復原或稽核；真正的隱私刪除／redaction 留到 D7 裁決。
3. 前後說法互相衝突但使用者尚未明確更正時，不把兩者硬合併成一個看似確定的事實，也不只靠模型判斷語氣強弱決定誰正確；應保留「尚待確認」的語意並向使用者釐清。
4. 現實狀態真的隨時間改變時採「選擇性 temporal grounding」：active Memory 以目前狀態為主；只有歷史、轉換或排程仍影響目前理解時，才保留使用者實際說出的時間脈絡。

這不是要求通用基線建立 temporal graph。最低必要行為只是：正常召回只有一個 current head；歷史版本不污染 active context；未解衝突不能被偽裝成已確認事實。

#### D4-b. 現實狀態真的隨時間改變（Owner 已確認）

先區分兩種時間，否則容易設計錯誤：

- **mutation time**：系統何時建立或修改 Memory；Anthropic immutable version 的 `created_at`、一般資料庫的 `updated_at` 屬此類；
- **valid time**：該事實在現實中何時開始／停止成立；例如「2026 年 7 月以前每週彙整，之後改成每月」。

revision history 只能可靠回答前者，不能自動回答後者。若使用者沒有說現實狀態何時改變，不能從 Memory 的寫入時間推測事實有效期間。

跨家資料顯示：

1. OpenAI Codex 公開 extraction、consolidation 與 supporting evidence，但沒有公開 temporal-fact policy；此處不能借 OpenAI 名義下結論。
2. Anthropic Managed Agents 提供 current head 與 immutable versions，適合稽核／復原；公開 schema 的版本時間是 mutation time，不等於工作事實的 valid time。
3. Google Memory Bank 預設以最新 revision consolidation，也可納入多個歷史 revisions 協助識別長期趨勢；官方沒有要求所有 Memory 都建立 valid-from／valid-to。
4. AWS AgentCore 的官方 semantic Memory prompt 明確要求 temporal grounding：可計算的相對時間轉成日期；「最近」等模糊時間不得捏造日期；帶不同 timestamps 的新事件應分開保存，避免合併成 temporal contradiction。
5. Graphiti 是完整 temporal／bi-temporal graph 路線，以 `valid_at`、`invalid_at`、`reference_time` 表達事實有效期並讓新事實失效舊關係；能力完整，但也引入 graph、關係解析、時間抽取與矛盾解析成本。

候選行為：

| 方案 | 行為 | 優點 | 風險 |
| --- | --- | --- | --- |
| A. Current-only | active Memory 只留現在狀態；舊狀態只在 conversation／revision | 最簡單 | 無法直接回答狀態如何演變；進行中的轉換可能遺失 |
| B. 選擇性 temporal grounding | 預設只留現在狀態；只有使用者明確描述歷史、轉換期或時間會影響目前分析時，才在語意完整 Memory 中保留時間脈絡 | 保住必要細節，不要求全域 temporal graph | Memory manager 需判斷哪些時間脈絡仍有用；需避免捏造日期 |
| C. 全面 temporal graph | 每個事實／關係都有有效期間與失效關係 | 歷史查詢與演變推理最完整 | 對多數通用互動可能過度設計，增加抽取錯誤、成本與維護面 |

**目前決定（Owner 於 2026-08-30 確認，仍可因後續證據或產品需求經討論翻案）：採 B「選擇性 temporal grounding」。**

具體規則如下：

1. **active Memory 預設描述目前有效的事實與狀態。** 已失效、且不再影響目前理解的舊狀態，不進正常 recall；原始對話與 revision history 仍保留，供稽核或必要時回看。
2. **只有歷史、轉換或排程本身仍影響目前理解時，才把時間脈絡留在 active Memory。** 例如：「以前每週彙整，2026-07 起改成每月彙整」應保留目前做法、先前做法與明確生效時間，而不是只留下其中一個版本。
3. **可確定的相對日期才可正規化。** 若訊息時間已知，且「下週一」「昨天」等能 deterministic 計算，可轉成具體日期；「最近」「之前」「目前」等模糊表達必須保留其模糊程度與 reference time，不得自行捏造起訖日期。
4. **Memory mutation time 不等於事實 valid time。** 系統何時寫入或修改記憶，只能表示記憶版本時間，不能冒充現實狀態何時開始或結束。
5. **通用基線不採完整 temporal graph。** 先要求具時間語意的完整 Memory entry 加 revision history；只有特定應用真的需要跨期比較、事件序列推理或任意時間點查詢時，才重新評估 `valid_at`／`invalid_at` 等完整模型。

例子：

- 使用者說「以前每週彙整，2026 年 7 月起改成每月彙整」：active Memory 可記錄「目前每月彙整；2026-07 前為每週彙整」。
- 使用者只說「最近改成每月彙整」：保留「最近改為每月彙整（以該則訊息時間為參考）」；不得自行填入某個月份。

直接來源：

- [OpenAI Docs — Codex Memories](https://learn.chatgpt.com/docs/customization/memories)
- [Anthropic Support — Claude topics 的更新、編輯、刪除與 past-chat citations](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Anthropic Platform — Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic Platform — Managed Agents Memory versions](https://platform.claude.com/docs/en/managed-agents/memory)
- [Google Cloud — Memory Bank extraction、consolidation 與 revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [AWS — AgentCore semantic Memory consolidation system prompt](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [LangMem — Extract semantic memories](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
- [LangMem — Memory tools API](https://langchain-ai.github.io/langmem/reference/tools/)
- [Graphiti — temporal fact fields 與 invalidation 實作](https://github.com/getzep/graphiti/blob/main/graphiti_core/edges.py)

### D5. 原始 conversation 與 provenance（Owner 已確認）

先把四個常被混在一起的概念分開：

1. **conversation continuity**：保存使用者、AI 與工具依時間發生的原始事件，讓同一段長期互動可以延續；
2. **derivation provenance**：知道某筆衍生 Memory 是由哪次 extraction／consolidation、哪個來源範圍產生；
3. **supporting evidence／citation**：能進一步指回支持該結論的特定原始訊息或內容；
4. **Memory revision history**：知道整理後 Memory 自己何時被新增、修改或淘汰。

它們不是同一件事。Memory revision 能證明「系統何時改過理解」，不能單獨證明「這項理解來自使用者哪句話」；conversation continuity 也不代表每筆 Memory 已建立細粒度來源關係。

#### D5-a. 最新官方做法

| 來源 | 公開可確認的行為 | 不能過度宣稱的部分 |
| --- | --- | --- |
| OpenAI Responses／Codex | Responses 的 Conversation 保存並自動追加 input／output items；Codex 本機 Memory 明列 summaries、durable entries、recent inputs 與 prior-chat supporting evidence。OpenAI 也提醒必須永遠生效的規則不應只依賴 Memory | 公開文件沒有說每一筆 durable entry 都必須一對一綁定精確 quote 或 message ID |
| Anthropic Claude | Memory tool／Managed Agents Memory 與 session context 分離；Claude 引用 past chat 時會提供回到原聊天的 citation；Enterprise export 中 chat summaries 仍綁定 source conversation；Memory versions 則提供變更 audit／restore | Memory file 本身沒有官方強制的逐項來源 schema；memory version 是變更歷史，不等於來源證據 |
| Google Memory Bank | 可由直接 events、Agent Platform Session 或 pre-extracted facts 產生 Memory；revisions 可檢查 extraction 與 consolidation 中間結果 | 公開 Memory schema 沒有承諾每個 fact 一定附精確 source-event citation；來源 Session／event set 與逐筆 evidence 是兩個層次 |
| AWS AgentCore Memory | immutable、timestamped event 是 short-term source；semantic strategy 從 events 抽取 long-term records。兩層可分別讀取，原始 events 不必被 Memory 取代 | 官方 long-term record 說明沒有承諾自動帶回 supporting event ID；event metadata 也不會無條件原樣流入 record |
| LangGraph／LangMem | thread messages／checkpoints 與 long-term Store 分層；Store 支援自訂 JSON、metadata、namespace 與 semantic search | provenance 欄位不是 LangMem 強制內建契約；若產品需要，必須由使用者 schema／寫入流程承載 |

直接來源：

- [OpenAI API — Responses Conversation](https://developers.openai.com/api/reference/python/resources/conversations/methods/create)
- [OpenAI Docs — Codex Memories](https://learn.chatgpt.com/docs/customization/memories)
- [Anthropic — Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Search past chats、memory 與 source-chat citations](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Anthropic — Managed Agents Memory 與 immutable versions](https://platform.claude.com/docs/en/managed-agents/memory)
- [Google Cloud — Memory Bank generation、source events 與 revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [AWS — AgentCore Memory：raw events 到 long-term records](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-get-started.html)
- [AWS — immutable event 與 event branching](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/short-term-create-event.html)
- [LangChain — short-term thread state 與 long-term Store](https://docs.langchain.com/oss/python/concepts/memory)
- [LangMem — semantic memory extraction](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)

#### D5-b. 跨家共同點與研究結論

1. **原始 conversation／event stream 與整理後 Semantic Memory 是兩層。** Memory 是可修訂、可召回的衍生理解，不應取代原始歷史。
2. **正常推理不必重送全部原始歷史。** active context 先使用有界的 Memory；需要驗證、更正、處理衝突或回想細節時，才搜尋／讀取原始 conversation。
3. **可回查來源是成熟方向，但逐筆精確 quote 不是跨家共同硬規則。** OpenAI Codex 與 Claude 產品提供 supporting evidence／source-chat citations；AWS、Google 與 LangMem 公開 primitive 則允許保留來源層，但不強制每筆衍生 Memory 綁特定訊息。
4. **revision history 與 factual provenance 必須分開。** 前者說明 Memory 自身怎麼變；後者說明它根據什麼來源形成。
5. **來源 ID、時間與版本應由系統產生或驗證。** 這是基於各家 immutable event／session／revision primitive 得出的產品設計推論，不是聲稱某家公開了完全相同的內部 schema；模型不應自行捏造 UUID、event ID 或 timestamp。

#### D5-c. 三個候選

| 方案 | 行為 | 優點 | 缺點 |
| --- | --- | --- | --- |
| A. Memory-only | 整理完成後只留 Memory，原始 conversation 可丟棄 | 最省儲存 | 無法查錯、處理更正或證明來源；不符合大廠共同分層，排除 |
| B. 每筆強制精確 citation | 每筆 Memory 必須綁一個以上 message ID／quote | 最容易逐項稽核 | 增加抽取 schema、模型填錯與重試；跨多段話形成的理解難以精確一對一；不是跨家共同要求 |
| C. 分層 provenance | 原始 conversation 作為獨立 source ledger；每次 Memory revision 至少由系統記錄來源 session／event window／generation run，必要時再附細粒度 supporting event；正常 recall 不載入來源全文 | 可追溯、成本可控、避免模型捏造 ID，也保留日後升級精確引用的空間 | 回查單一結論時，可能需要再搜尋來源 window |

**目前決定（Owner 於 2026-08-30 確認，仍可因後續證據或產品需求經討論翻案）：採 C「分層 provenance」。**

通用基線行為界線：

1. 原始 conversation／events 依發生順序保存；使用者更正以新訊息追加，不改寫舊話。
2. Semantic Memory 是原始 conversation 的衍生 current understanding；刪除或改寫 Memory 不等於刪除來源歷史。
3. 每個 Memory revision 至少保留由系統建立的 generation lineage，可回到此次處理的 source session／event window；LLM 不填 ID、版本或時間。
4. 精確 message／quote citation 是可選的 supporting evidence，不作為每筆 Memory 的通用必填欄位；當系統能可靠識別，或衝突／更正需要查證時才使用。
5. 主模型平常收到有界 Memory；需要核實時透過 search／read 取回原始對話，不把完整歷史塞進每一輪 Context。

這是對多家公開做法的綜合設計推論，不宣稱 OpenAI、Anthropic、Google 或 AWS 內部使用完全相同的資料結構。

**狀態：Owner 已確認 C。** 這項裁決要求保留 raw conversation 與可回查 lineage，但不把「每筆 Memory 必須附精確 quote／message ID」升級為通用硬規則。若後續驗證證明 source window 不足以定位錯誤，再以證據評估是否提高 supporting evidence 粒度。

### D6. 更新一致性與失敗行為（Owner 已確認）

先拆開四個容易被誤寫成同一件事的時間點：

1. **來源已保存**：使用者訊息／事件已耐久保存，不會因後續 Memory 失敗而遺失；
2. **Memory 工作已受理**：extraction／consolidation 已排入處理，但結果可能仍在執行；
3. **新 Memory 已發布**：新 revision 已驗證完成並成為可召回的 current head；
4. **下一個依賴分析已讀到**：後續模型實際使用到這個已發布版本。

只有第 3 點成立，才能說「Memory 已更新」；只有第 4 點成立，才能說後續判斷確實依賴了新理解。HTTP 接受、背景工作排程成功或模型已產生文字，都不能替代這兩個保證。

#### D6-a. 最新官方做法

| 來源 | 官方公開行為 | 對本題能下的結論與限制 |
| --- | --- | --- |
| OpenAI Responses | Conversation 的 input／output items 在 Response **完成後**才自動加入；Response 明確區分 `queued`、`in_progress`、`completed`、`failed`、`cancelled`、`incomplete`，並分別提供 `error`／`incomplete_details` | 支持「完成狀態與提交時間要分開」，但 OpenAI 沒公開跨對話 Semantic Memory 的交易一致性，不能替它推測 |
| Anthropic Managed Agents Memory | Memory update 可帶 `content_sha256` precondition；內容已被別人改過時不覆蓋，必須重讀最新內容再重試。每次 mutation 建立 immutable version，live retrieve 只回最新 head | 直接支持 optimistic concurrency、不可靜默 last-write-wins、current head 與歷史版本分離 |
| Google Memory Bank | `GenerateMemories` 是 long-running operation；需要當下結果時可 blocking，當前 run 不依賴結果時官方建議 production 背景執行。Operation 完成後才回報每筆 `CREATED`／`UPDATED`／`DELETED`；故障排查要求先確認 LRO 完成，再檢查 operation error | 支持「依賴結果才等待、非依賴可背景」，也證明排程成功不等於 Memory 已可用；未公開跨多筆 Memory 的 ACID 原子性 |
| AWS AgentCore Memory | 先以 `CreateEvent` 保存 raw interaction，再非同步 extraction／consolidation；官方提醒 long-term result 可能一分鐘以上才可召回。`clientToken` 保證同一事件至多建立一次；retryable 409 建議 exponential backoff；持續失敗會成為可查 failure reason、可 redrive 的 extraction job | 支持「raw source 先耐久保存」「冪等重試」「失敗不能消失」；AWS 的 long-term Memory 明確是 eventual，不適合直接承擔下一個必須使用新更正的判斷 |
| LangGraph／LangMem | LangGraph checkpoint 保存執行狀態與 failure provenance；task 結果可恢復，未完成 task 可能重跑，因此官方要求 side effect 冪等。RetryPolicy 依錯誤類型有限重試，重試耗盡才進 error handler。LangMem 明確區分立即 hot-path update 與延遲 background formation | 可直接提供 durable execution、bounded retry、resume 與 hot/background primitive；框架不替產品定義哪個 Memory 更新是 correctness-critical |

直接來源：

- [OpenAI API — Create a model response：Conversation commit timing 與 Response status](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [Anthropic — Managed Agents Memory：optimistic concurrency、latest head 與 immutable versions](https://platform.claude.com/docs/en/managed-agents/memory)
- [Google Cloud — Memory Bank generation：LRO、blocking／background 與 action results](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google Cloud — Memory Bank troubleshooting：確認 LRO completion 與 operation errors](https://docs.cloud.google.com/gemini-enterprise-agent-platform/troubleshooting/memory-bank)
- [AWS — AgentCore Memory types：raw events 先存、long-term extraction 背景執行](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)
- [AWS — Save and retrieve insights：long-term Memory 的可見性延遲](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-saving-and-retrieving-insights.html)
- [AWS — CreateEvent：clientToken 冪等與 retryable 409](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_CreateEvent.html)
- [AWS — Redrive failed ingestions：failure reason、監控與重送](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-redrive.html)
- [LangGraph — Functional API：checkpoint、replay 與 idempotent side effects](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [LangGraph — Fault tolerance：typed retry、backoff 與 resume-safe failure](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [LangMem — Core concepts：hot-path 與 background Memory formation](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)

#### D6-b. 跨家共同點與不能過度宣稱的地方

1. **來源耐久化與衍生 Memory 生成是兩階段。** Memory pipeline 失敗時，原始 conversation／event 仍須存在，才能重試或重建。
2. **受理、執行、完成與失敗必須可區分。** 不得把「已排程」回報成「已記住」。
3. **同步或非同步不是全域二選一，而是依賴關係。** 當下或下一個分析需要新理解時要等到發布；不影響正確性的 consolidation 才可 eventual。
4. **未完成的新版本不得污染 current head。** 生成、驗證或儲存失敗時，舊 head 繼續有效；不能讀到半成品，也不能假裝更新成功。
5. **並行更新不能靜默覆蓋。** 成熟做法使用 version／hash precondition；衝突時重讀最新狀態並重新整理，而非 last-write-wins。
6. **重試必須有限、依錯誤類型且冪等。** timeout、429、暫時性 409／5xx 可 backoff 重試；無效輸入、權限、找不到資源或語意驗證失敗不能無限重送同一內容。
7. **失敗要留下可恢復狀態。** 至少能知道哪個 generation 失敗、失敗原因與來源範圍，並可安全重跑；不能只在 log 留一句錯誤後遺失工作。
8. **不能從目前官方資料推論跨多筆 Memory 一定有 ACID transaction。** Google 回報逐筆 action，AWS／LangMem 也未公開全批次原子承諾；若產品需要整組一致，只能明確定義「依賴 barrier／發布單位」，不能假借廠商能力。

這些是多家目前官方行為的共同結論。它們不要求通用基線先自建分散式交易、全域鎖或訊息佇列；本題只是先決定使用者與下一個模型能觀察到什麼，以及失敗時不可發生什麼。

#### D6-c. 三個候選

| 方案 | 行為 | 優點 | 缺點 |
| --- | --- | --- | --- |
| A. 全同步強一致 | 每則訊息都等所有 extraction、consolidation 與 Memory 寫入完全成功後才回覆 | 行為最直觀，下一輪一定讀到 | 每輪延遲與成本最高；任何非關鍵背景整理失敗都會阻塞訪談；不符合 Google／AWS／LangMem 對非依賴工作的現行建議 |
| B. 全背景 eventual | 先回覆，所有 Memory 都在背景更新；下輪讀到舊版也接受 | 最低互動延遲 | 更正或衝突可能在後續分析仍使用舊理解；不適合需要連續正確理解的長期互動 |
| C. 依賴 barrier＋版本化發布 | 原始事件先保存；Memory generation 有明確執行狀態。下一個步驟若依賴新理解，就等相關更新完成發布；無依賴的重整可背景。更新以 expected revision／hash 防止覆蓋，成功才切換 current head；失敗保留舊 head、原因與可重跑工作 | 同時保住正確性與互動速度；直接組合大廠與 LangGraph／LangMem 已提供的成熟 primitive；不要求全庫每輪鎖住 | 必須明確標示依賴更新；背景與必要更新有兩種完成時效，觀測與測試比 A 多一些 |

#### D6-d. 建議採 C，但先把邊界說死

這是目前研究後的最佳候選，也與 D1 已確認的 correctness-deadline hybrid 一致；D6 只是把失敗與並行細節補完整：

1. 收到使用者訊息後，先耐久保存 raw conversation／event；這一步失敗就不能假裝已收到。
2. Memory generation 進入可辨識的執行狀態；名稱與 schema 留到實作研究，不先發明欄位。
3. 同一 run 的一般回答或澄清，可直接使用已保存的本輪訊息、舊 current head 與本輪已驗證的暫時結果，不必為了先寫入 durable Memory 而停住。下一個 run，或任何會形成 durable／對外可觀察效果、且正確性確實依賴本輪新理解的步驟，才必須等相關 Memory revision 驗證並發布；若發布失敗，依賴它的效果停止，但系統仍可說明失敗或提出不會把未定內容冒充事實的澄清問題。
4. 發布採 expected revision／content hash；若 current head 已改變，重讀最新 head 後做**有限次**重新整理，不覆蓋別人的更新。
5. 同一個來源事件或 generation 重試時沿用系統產生的 idempotency key，避免建立重複 Memory／revision。
6. 暫時性基礎設施錯誤使用 bounded exponential backoff；不可重試錯誤直接標示失敗。模型輸出不合法可進有上限的修正回路，但不歸類成網路重試。
7. generation 失敗時，raw conversation 與舊 current head 都保留；依賴新理解的後續步驟停止，非依賴流程不必一起報廢。
8. 每筆 topic Memory 的 head 切換必須原子；若一次 generation 產生多筆互相依賴的變更，下一個依賴者須等該組全部完成。通用基線不因此要求「所有 Memory 全庫原子提交」。

第 8 點是基於 D2「Memory 可獨立修訂」與各家公開行為做出的最小產品推論，不宣稱任何廠商公開保證相同的 grouped transaction。若實作 mapping 發現既有框架能以單一 checkpoint 原生提供整組發布，再於後續 ADR 比較；現在不先做自訂 transaction engine。

**狀態：Owner 於 2026-08-30 確認採 C「依賴 barrier＋版本化發布」。** 尚未決定正式狀態名稱、資料結構、retry 次數、timeout、queue、transaction 或使用 Checkpoint／Store；這些屬後續框架 mapping 與實作研究。此裁決仍可因後續新證據或產品需求經討論翻案，但不得未經 Owner 討論自行改成全同步或全背景。

### D7. 使用者控制程度（Owner 已確認）

「讓使用者控制 Memory」不是單一開關。至少要分清楚六種不同能力，否則很容易把隱私刪除、語意更正與暫停使用混成同一件事：

1. **查看**：知道系統目前記得／理解什麼；
2. **自然語言更正**：在正常對話中要求記住、修正或忘記；
3. **直接編輯**：像編輯設定或文件一樣改寫某筆 Memory；
4. **刪除／重設**：刪除單筆、某個範圍或全部衍生 Memory；
5. **使用／學習控制**：分別決定本次對話能否讀既有 Memory、以及本次對話能否成為新 Memory 的來源；
6. **來源歷史控制**：刪除原始 conversation／event，而不是只改掉由它衍生的 Semantic Memory。

#### D7-a. 最新官方做法

| 來源 | 官方公開行為 | 對本題能下的結論與限制 |
| --- | --- | --- |
| OpenAI Codex Memories | 每個 chat 可分開控制「使用既有 memories」與「讓本 chat 產生未來 memories」；全域設定也分成 `generate_memories` 與 `use_memories`。本機 memory files 可檢查，但官方明確說不要把手動編輯生成檔當成主要控制面 | 直接支持「讀取」與「學習」要分開；也支持生成 Memory 可檢查，但不支持把裸檔案編輯照搬成一般使用者 UX |
| OpenAI Conversations API | 可刪除 conversation item；也可刪 conversation container，但官方特別註明刪 container 不會連帶刪 items | 支持來源歷史本身有獨立生命週期；不能把「刪 Memory」假設成「刪對話」，反之亦然 |
| Claude 消費型產品 | Memory 以個別 Topics 保存；使用者可查看、直接編輯或刪除 topic，也可在聊天中要求 Claude remember／change／forget。Pause 會保留既有 Memory、停止讀取且停止新增；Reset 才永久清空。Past-chat search 有獨立開關與 incognito chat；來源聊天 citation 可回到原對話 | 同時證明自然語言更正與直接編輯都能成為成熟產品能力；也證明 Pause、Reset、chat search 與 source deletion 不是同一操作 |
| Anthropic Managed Agents Memory | 應用可用 API／Console 建立 review workflow，直接 list／read／create／update／delete Memory；可把 store 掛成 `read_only` 或 `read_write`。每次 mutation 有 immutable version，敏感歷史可 redact | 提供完整治理 primitive；這是開發平台能力，不等於每個產品都應把內部 Memory schema 直接暴露給終端使用者 |
| Google Memory Bank | API 支持 retrieve、create、依 resource name 刪除、依條件 purge；新資訊與明確 forget instruction 也可在 generation／consolidation 時造成既有 Memory 更新或刪除 | 支持自動 reconcile、明確忘記與管理端精準刪除並存；Google 沒替產品決定終端 UI 是否要做直接編輯器 |
| AWS AgentCore Memory | raw event 與 long-term memory record 分別有刪除 API；官方明說刪除 event 不會自動移除由它抽出的 long-term record，後者要另外刪 | 直接證明來源與衍生理解必須分開治理；若提供隱私刪除，UI 必須說清楚刪的是哪一層 |
| LangMem | `manage_memory` tool 可配置允許 create／update／delete；Memory manager 可自動更新被新資訊推翻的既有 Memory，delete 預設可關閉；search tool 另行提供 recall | 現行框架已覆蓋模型自然更正、CRUD 與召回 primitive；仍不包含使用者 UI、隱私文案、刪除範圍或權限政策 |

直接來源：

- [OpenAI — Codex Memories：per-chat use／contribute 與全域 generate／use 控制](https://learn.chatgpt.com/docs/customization/memories)
- [OpenAI API — Delete a conversation：container 與 items 的刪除邊界](https://developers.openai.com/api/reference/typescript/resources/conversations/methods/delete)
- [OpenAI API — Delete a conversation item](https://developers.openai.com/api/reference/ruby/resources/conversations/subresources/items/methods/delete)
- [Anthropic — Claude chat search and memory：Topics、聊天更正、Pause／Reset、來源 citation 與個別刪除](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Anthropic — Managed Agents Memory：review workflow、CRUD、read-only／read-write、versions 與 redaction](https://platform.claude.com/docs/en/managed-agents/memory)
- [Google Cloud — Memory Bank API quickstart：retrieve、create、delete、purge 與 semantic forget](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/api-quickstart)
- [AWS — Delete an event：刪 raw event 不等於刪衍生 long-term record](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/short-term-delete-event.html)
- [AWS — Delete memory records：精準移除衍生 Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-delete-memory-records.html)
- [LangMem — Memory tools：可配置 create／update／delete 與獨立 search tool](https://langchain-ai.github.io/langmem/reference/tools/)
- [LangMem — Memory manager：自動 update／delete 與開關](https://langchain-ai.github.io/langmem/reference/memory/)

#### D7-b. 跨家共同點與不能誤讀的地方

1. **Semantic Memory 與來源 conversation 是兩層資料。** 刪除、停用或修正其中一層，不應默默假裝另一層也完成相同行為。
2. **自然語言更正是成熟的一級操作。** Claude、Google 與 LangMem 都直接支持「記住／改成／忘記」進入 reconcile；不需要為一般更正另造「更正這段原話」流程。
3. **可查看與可刪除是高可信共同能力。** 完全黑盒、無法知道或移除系統理解的方案不適合作為長期產品基線。
4. **直接編輯是成熟選項，但不是跨家共同必要條件。** Claude 產品與 Anthropic 平台支持；Codex 反而明確說生成檔案不應是主要控制面。是否提供直接編輯，要看 Memory 是給使用者管理的偏好檔，還是給模型維持一致理解的內部語意狀態。
5. **「暫停」至少包含兩個維度。** OpenAI 分開 use 與 contribute；Claude 的 Pause 同時停止讀與寫但保留資料，Reset 才刪除。產品不能用一個模糊的「關閉 Memory」同時代表停止使用、停止學習與永久清除。
6. **版本歷史不是隱私刪除。** 版本可用來復原與稽核，但遇到真正刪除要求仍要有 delete／redact；不能因為系統保留 revision 就宣稱內容已忘記。
7. **平台 CRUD 不等於終端 UI 決策。** Google、AWS、Anthropic API 與 LangMem 都提供 primitive，但特定應用是否露出單筆編輯器、批次 purge、暫停或 incognito，仍要依後續產品 mapping 決定，不能為了「框架有功能」全放進 UI。

#### D7-c. 三個候選

| 方案 | 行為 | 優點 | 缺點 |
| --- | --- | --- | --- |
| A. 全自動黑盒 | 系統自動維護；使用者只能繼續聊天，不能查看、刪除或控制使用 | UI 最少 | 無法核對錯誤理解，也缺少成熟產品普遍提供的透明、刪除與隱私控制；排除 |
| B. 完整 Memory 編輯器 | 使用者可直接查看、逐筆改寫、刪除、還原、暫停與管理來源 | 控制最完整；適合本身就是知識庫管理工具的產品 | 會把模型內部語意狀態變成第二份使用者文件；容易繞過正常對話、更正與來源關係，UI／權限／復原成本最高 |
| C. 分層控制 | 正常聊天是主要更正方式；可選擇查看目前理解，提供明確 forget／delete／reset；來源 conversation 另有獨立刪除邊界。底層保留 use 與 learn/write 分離能力，但只向使用者露出應用真正需要的控制，不把內部 schema 當成一般編輯器 | 符合 OpenAI／Anthropic 的成熟分層，又不迫使採用者把應用變成 Memory 管理器；框架已覆蓋 reconcile、CRUD 與 search，多數自訂工作集中在清楚的產品政策與 UI | 使用者不能像改文件一樣任意重寫內部 Memory；查看畫面若太技術化仍可能造成困惑，需要呈現可理解的語意而非資料表欄位 |

#### D7-d. 通用 LLM Memory 的研究後建議

目前只就通用 LLM Memory 行為採 C「分層控制」；尚不套入 Caliburn 或任何特定產品。通用邊界如下：

1. 使用者可在一般對話中自然表達「我剛才說錯了」「不是 A，是 B」，由 Memory layer 依 D4 reconcile；通用機制不要求使用者先找到來源訊息或操作專用更正表單。
2. Memory 應可檢查，但「直接編輯內部 topic schema」不是通用必要條件；應用可選擇唯讀語意檢視、產品化編輯器或只提供對話更正。
3. 必須能要求忘記個別理解或重設整份 Semantic Memory；具體是聊天指令、設定介面或兩者並存，屬後續產品 mapping，而不是通用 Memory 先決定的 UI。
4. 刪除 Semantic Memory 與刪除原始訪談要分開且明白說明影響；需要真正刪除時，不能只讓 active head 不再召回，還要依 retention 政策處理 revision／source。
5. 底層應保留「可讀既有 Memory」與「可由本次對話更新 Memory」兩個獨立能力；特定應用是否需要 incognito／pause，留待產品需求階段判斷。
6. 管理端／診斷端可使用成熟框架的 CRUD、revision 與 redaction；不代表全部能力都必須向終端使用者暴露。

這裡只裁決通用 Memory 的控制原則，沒有先決定特定產品名稱、UI、刪除 retention、權限、資料結構、框架 mapping 或第一版範圍，也不授權施工。等通用 Memory 方案整體收斂後，才另外研究哪些原則適合套入 Caliburn。

**狀態：Owner 於 2026-08-30 確認採 C「分層控制」。** 此裁決仍只屬通用 LLM Memory 行為方案；後續套入特定產品時，可依新的產品證據經討論調整，但不得未經 Owner 討論自行翻案。

### 7A. D1～D7 整體一致性審核（2026-08-30，通用研究已收斂）

本節不把通用方案套入任何產品。它檢查 D1～D7 放在一起後，是否形成互相相容、可失敗、可刪除且不會跨範圍污染的完整行為；並依本輪授權補齊 F6～F9。這仍是研究結論，不是不可推翻的產品規格。

#### 7A-a. 證據紀律

本次審核把證據分成四層，避免把大廠產品行為與我們的設計推論混在一起：

1. **官方明說**：官方產品或 API 文件直接承諾的行為；
2. **跨家共同點**：兩家以上官方資料呈現相同的外部行為，但不代表內部實作相同；
3. **整合推論**：為了讓已選行為能同時成立而必須補上的產品級約束；
4. **未知**：廠商未公開，不以推測冒充事實。

Anthropic 的同一篇 Help Center 頁面同時保留 2026 新版 Memory 與後段 legacy 說明；兩者的刪除、更新時效與儲存模型不完全相同。本文只以新版段落作現行產品證據，legacy 段落只能作歷史對照，不能混合拼成一套流程。

#### 7A-b. 整體結論

**D1～D7 沒有需要整套推翻的致命矛盾。** 主要骨架是相容的：原始 conversation 先保存；Memory 依主題形成可獨立修訂的 current head；召回有界且可按需搜尋；更正、版本、來源、失敗與使用者控制分層。

§6.1 的 B1～B7 也都能與 D1～D7 共存。F1～F9 補齊了正確性期限、未解狀態、使用／學習控制、刪除、隔離、寫入資格、信任、召回與成本／維運邊界。

**通用 Memory 的行為方案已完成第一輪收斂。** 這表示必要功能、選項與未知邊界已能完整說明；不表示某個框架、資料結構或產品 mapping 已被選定。廠商未公開的內部機制仍保留為未知，不以整合推論冒充官方做法。

#### 7A-c. 交界矩陣

| 交界 | 審核結果 | 診斷 | 待處理方式 |
| --- | --- | --- | --- |
| D1＋D2＋D3 | 相容 | 可在正確性期限內更新多筆語意完整 Memory，再有界召回；不要求每輪全量重寫或全量注入 | 不改決策 |
| D2＋D4＋D6 | 相容 | current head、revision history、optimistic concurrency 與成功後發布可以共同成立 | 不改決策 |
| D3＋D5 | 相容 | 正常先用有界 Memory；核實、更正或需要細節時再讀原始 conversation，沒有要求每輪重送全部來源 | 不改決策 |
| D4＋D7 | 相容 | 自然語言更正、active head 替換、歷史版本與真正刪除可分層處理 | 不改決策 |
| D1＋D6 | **已解決** | D1 允許目前 run 直接使用本輪訊息；D6 barrier 現已縮小為下一個 run 或真正依賴已發布 Memory 的 durable／對外可觀察效果 | Owner 已確認 F1，D6-d 第 3 點已同步修正 |
| D1＋D4 | **已解決** | 新資訊依確認程度參與本輪；未解問題只以「尚未確認」語意生效，不得冒充已確認事實 | Owner 已確認 F2，D1 第 3 點已同步修正 |
| D1／D3＋D7 | **已解決** | use 與 learn/write 是可分離控制；關閉任一能力時，對應 pipeline 不得仍偷偷執行，但目前訊息仍可供本輪對話使用 | Owner 已確認 F3；產品是否提供開關、預設值與 UI 留待 mapping |
| D5＋D7 | **已解決** | 來源、衍生 Memory、revision 可以分別刪除，不默認 cascade；forget／reset／privacy erase 是不同承諾 | Owner 已確認 F4；retained lineage 的產品呈現仍留待 mapping |
| D6＋D7 | **已解決** | 背景 generation／retry 可能晚於 forget／reset；完成後舊工作不得把已移除內容重新發布 | Owner 已確認 F4 的 anti-resurrection 外部行為；內部機制仍未知 |
| §6 B5＋全部 D 項 | **已解決** | topic、recall、source、revision、delete 都必須先知道正確 scope；否則完整機制仍可能把 A 的 Memory 給 B | Owner 已暫時確認 F5 方案 C；產品 mapping 仍可重新比較 |
| 寫入選取＋D7 | **已解決** | 值得記得不等於允許保存 | 採分層 persistence eligibility，見 F6 |
| 召回／寫入＋安全 | **已解決** | Memory 可能由 prompt injection 或錯誤抽取污染，未來 session 又把它當可信內容 | 採低信任資料與 least-privilege 基線，見 F7 |
| D3＋檢索策略 | **已解決** | 自動召回、exact lookup、search／read 與 rerank 的優先順序未完整 | 採有界混合召回，見 F8 |
| D1／D6＋成本維運 | **已解決** | 每輪模型更新、背景任務與失敗若不可觀察，會造成高成本與假成功 | 採 correctness-driven hot path 與可觀察 background，見 F9 |

#### 7A-d. 三個既有交界的修正候選

##### F1. D6 barrier 只應阻擋真正依賴「已發布 Memory」的後續效果（Owner 已確認）

Google 官方把 blocking 與 background generation 依「目前工作是否需要結果」分流；LangGraph／LangMem 也區分 hot-path state 與背景 long-term formation。這支持 D1 的核心判斷，但 D6-d 第 3 點目前把「後續提問」整類納入 barrier，範圍過大。

建議只修文字、不翻案：

- 同一 run 的一般回答或澄清，可以直接使用已保存的本輪訊息、舊 current head 與本輪已驗證的暫時結果，不必為了先寫入 durable Memory 而停住；
- 下一個 run，或任何會形成 durable／對外可觀察效果、且正確性確實依賴新理解的步驟，才必須等新 revision 成功發布；
- 如果 Memory 發布失敗，依賴它的效果停止，但仍可向使用者說明失敗或提出不需要把未定內容冒充事實的澄清問題。

這是 D1 與 D6 的邊界修正，不等於取消依賴 barrier。

**狀態：Owner 於 2026-08-30 確認。** D6-d 第 3 點已依上述行為修正；當時沒有連帶改動後續邊界，F2～F9 已在各自章節另行研究，也沒有預選 checkpoint、queue 或其他實作機制。

##### F2. 「未解問題生效」只代表它以未解狀態生效（Owner 已確認）

D4 已要求衝突不能硬合併成事實。為避免 D1 被誤實作，建議明說：

- 新事實以目前可信度／狀態進入本輪；
- 明確更正替換 active understanding；
- 未解問題只以 `unresolved` 語意參與推理，用來避免錯誤結論或觸發澄清，**不得被當成已確認事實**。

正式欄位名稱仍留到實作研究，這裡只裁決可觀察語意。

**狀態：Owner 於 2026-08-30 確認。** D1 第 3 點已依上述行為修正；沒有預選 status enum、資料結構或額外模型步驟；F3～F9 已在各自章節另行研究。

##### F3. use 與 learn/write 控制優先於一般 Recall／Memory 更新（Owner 已確認）

OpenAI Codex 明確分開「本 chat 可使用既有 memories」與「本 chat 可貢獻未來 memories」；Claude 的 Pause 則同時停止使用與新增，但保留資料。因此 D7 的控制必須具有清楚優先順序：

- `use off`：D3 不得自動召回或按需讀取既有 Semantic Memory；
- `learn/write off`：D1 不得由本輪來源新增或修改持久 Semantic Memory；
- 兩者都不妨礙模型使用本輪使用者明確提供的訊息完成當前對話；
- delete／reset 是資料生命週期操作，不應被模糊成單純 pause。

這只是通用行為：完整通用方案必須保留 read/use 與 learn/write 的獨立控制能力。是否向特定產品露出開關、兩者是否在某個產品中固定開啟、預設值與 UI，全部留到產品 mapping；本節不先替 Caliburn 下結論。

**狀態：Owner 於 2026-08-30 確認。** 這項裁決只補足通用方案的控制語意與優先順序，不授權新增任何產品 UI；F4～F9 已在各自章節另行研究。

#### 7A-e. 六個必要邊界（F4～F9 已完成通用研究）

##### F4. 刪除語意與 anti-resurrection

**狀態：Owner 於 2026-08-30 確認方案 C。** 本節只討論通用 Memory 的可觀察刪除語意，不選 API 名稱、資料表、tombstone、epoch、queue 或 UI。

###### F4-a. 各家官方實際承諾

| 來源 | 官方明說的刪除／保留行為 | 能支持的結論 | 不能從中推論的事 |
| --- | --- | --- | --- |
| OpenAI Conversations API | 刪除 conversation container **不會**刪除其中 items；item 另有獨立 delete API | 不同資料資源可有不同生命週期，不能假設刪父層就自動 cascade | 這不是 OpenAI 消費型 Memory 的內部刪除規格；OpenAI 尚未公開 Memory topic、source、revision 如何連鎖刪除 |
| Claude 現行 Memory | `Pause` 保留既有 Memory，但停止使用及產生新 Memory；`Reset` 永久刪除全部 Memory；刪除／到期 conversation 不會移除已衍生 topic，topic 可個別刪除 | pause、來源刪除、個別 Memory 刪除與整體 reset 是不同操作 | 不知道 Claude 如何攔截已在背景執行的舊 extraction |
| Anthropic Managed Agents | 刪 live Memory 不會抹除 immutable versions；歷史敏感內容需逐版 redact；刪整個 store 才一併永久移除 store、Memories 與 versions | current head、audit history、redaction 與整庫刪除可分層治理 | Managed Agents 的 API 形狀不等於 Claude 消費型 UI 的內部實作 |
| Google Memory Bank | 支援精確 delete、條件 purge、由新內容觸發的語意 forget；delete／purge 預設可非同步；刪除會形成空白最新 revision，舊 revisions 最多仍可取回 48 小時並 rollback | 「受理」與「完成」不同；刪目前 Memory 與保留短期復原歷史可以同時成立 | 未公開 forget 與既有 in-flight generate job 的競態裁決演算法 |
| AWS AgentCore Memory | 刪 short-term event 不會刪除由它衍生的 long-term record；long-term record 另有 delete API；ingestion 是非同步，失敗工作可稍後 redrive | source 與 derived Memory 明確分層；舊工作可在更晚時間重新執行 | 未公開 delete 與 redrive 同時發生時，平台是否代替應用阻止舊資料重建 |
| LangMem | Memory manager／tool 可 create、update、delete；自動 manager 可選擇是否允許模型刪除 outdated／contradicted Memory | 成熟框架能提供 CRUD／reconcile primitive | 不定義 source、revision、privacy erase 或 in-flight job 的產品承諾 |
| LangGraph | checkpoint 可 replay／resume，失敗 task 可 retry；官方要求有副作用的寫入使用 idempotency key 或先驗證既有結果 | 背景更新與 retry 必須被當成可能重跑的 durable work | LangGraph 不替應用定義「忘記後不可復活」或刪除 retention |

這些資料呈現三個穩定共同點：

1. **來源與衍生 Memory 通常是不同生命週期。** 刪 conversation／event 不應被默認宣稱會刪掉 derived Memory；反向也相同。
2. **刪除目前可用內容，不必等於抹除所有歷史。** current head、revision／audit、redaction 與整體 erase 可以是不同層級。
3. **非同步系統必須區分 accepted 與 completed。** Google、AWS 明確如此；LangGraph 的 retry／replay 進一步說明已啟動工作可能晚於原請求完成。

沒有任何官方證據支持「所有刪除都自動連鎖」，也沒有公開的跨家共同 anti-resurrection 演算法。

###### F4-b. 三個通用方案候選

**A. 單一 `delete`，由系統自行猜要刪哪些層**

- 優點：表面 API 最少。
- 缺點：使用者無法知道來源、目前 Memory、版本是否仍保留；與多家官方明確分層的生命週期不符。
- 研究判斷：**排除。** 少一個名詞不值得交換含糊且可能不實的刪除承諾。

**B. 任一 forget 都連鎖刪除來源、Memory、版本與索引**

- 優點：最容易解釋為「全部不見」。
- 缺點：一般更正／忘記也會摧毀 conversation 與 audit／復原能力；不是跨家共同做法，亦混淆語意更正與隱私清除。
- 研究判斷：**排除作為通用預設。** 若特定產品需要，應以明確的 privacy erase 操作提供。

**C. 分層操作，並對完成後的結果提供穩定保證（建議）**

1. **forget one／delete current Memory**：指定 active Memory 不再被一般 recall 使用；來源與 revision 是否保留，依各自 retention 顯示清楚。
2. **reset Semantic Memory**：清除該 scope 的全部 active Semantic Memory，之後從空白理解開始；不暗示已刪原始 conversation。
3. **delete source**：刪除指定 conversation／event；不暗示 derived Memory 已一併刪除，若產品要 cascade 必須明說。
4. **privacy erase**：依明確政策處理 active Memory、revisions、來源、搜尋索引、cache 與備援；這是比 forget／reset 更強的資料生命週期操作。
5. 同步操作可直接回報結果；非同步操作則必須讓呼叫端分辨「已受理、仍處理、已完成、失敗」等可觀察結果，不能在 accepted 時就聲稱已忘記。

上述是**行為分層**，不是要求產品一定露出四顆按鈕，也不是預選四個 API 名稱。產品 mapping 可把低階操作包成較少的使用者行為，但不能對結果說錯話。

###### F4-c. anti-resurrection 的精確邊界

若 forget／reset 已對外宣告 completed，但較早啟動的 extraction、consolidation、retry、redrive 或 replay 隨後又把同一舊來源發布回 active Memory，使用者實際上並沒有被忘記。D6 的背景工作與 D7 的刪除承諾便無法同時成立。

因此方案 C 還需要一條外部行為：

> forget／reset／erase 完成後，**操作之前的來源或工作**不得再把被移除內容重新發布為 active Memory；若使用者在操作之後重新提供同一資訊，是否允許重新學習，則依 learn/write 與 persistence eligibility 政策處理。

這條是由官方已公開的「非同步處理＋可重試／重播」和「完成後應不再使用／已永久刪除」兩類承諾推出的**必要整合約束**，不是任何一家公開的內部演算法。實作可能採 cancellation、generation fence、conditional write、tombstone 或其他方式；目前沒有證據可決定哪一種最佳，必須留到框架 mapping 後再研究。

同理，若 retained revision／source 已被刪除或 redact，系統不得仍把它呈現成可開啟、可核實的來源；具體 lineage 顯示方式留到 provenance／產品 mapping。

###### F4-d. 已確認裁決

Owner 確認方案 C 的通用可觀察語意：

- 不把 forget、source deletion、Semantic Memory reset 與 privacy erase 混成同一件事；
- 不默認 cascade，也不禁止特定產品明確提供 cascade；
- 非同步刪除不能在受理時冒充完成；
- completed 之後，舊工作不得使被移除內容復活；
- 目前不選任何防復活的資料結構或框架機制。

這項裁決只封閉 D5／D6／D7 的生命週期交界；不會決定任何特定產品的刪除 UI、保留期、法遵政策或第一版功能；F5～F9 已在各自章節另行研究。

##### F5. Scope／namespace／principal 隔離

**狀態：Owner 於 2026-08-30 暫時確認方案 C。** 本節只裁決通用隔離行為，不決定 Caliburn 的欄位、單機身分模型、Store 數量、資料表或 UI；產品 mapping 時仍可依產品證據重新比較。

###### F5-a. 四個常被混用、但不能互相替代的概念

| 概念 | 回答的問題 | 不能拿來代替什麼 |
| --- | --- | --- |
| `principal` | 是誰或哪個服務正在提出這次操作，並擁有哪些權限 | 不是「這筆 Memory 屬於誰」；後端服務 principal 可能依法替某位使用者操作 |
| semantic `scope` | 哪一組 Memory 可一起召回、consolidate、revision、reset；例如某個人、專案或用途的集合 | 不是登入驗證；知道 scope ID 不代表有權讀寫 |
| session／thread | 哪一段連續互動與短期 state 應接續 | 不是跨 session 的 durable Memory owner，也不是授權憑證 |
| namespace／store address | Memory 在儲存層如何分組、掛載或尋址 | 可承載 scope，但單靠路徑或 tuple 不會自動驗證呼叫者權限 |

另有第五個獨立維度是 `access mode／permission`：同一個 principal 對同一個 scope 可能只有 read、可 write，或擁有特殊管理權。Anthropic 的 `read_only／read_write`、Google 的 viewer／editor／user IAM roles 與 AWS 的 IAM action 都把它和資料地址分開。

因此「每個 project 有不同 namespace」只處理**放在哪裡**；還需要可信 runtime 先決定**誰在呼叫、可碰哪些 scope、這次可做什麼**。反過來，只做登入而不限制資源 scope 也不夠。LangSmith 官方甚至明說：只加入 authentication、尚未加入 resource authorization 時，使用者仍可存取彼此資源。

###### F5-b. 各家官方實際行為

| 來源 | 公開隔離方式 | 能支持的結論 | 不能從中推論的事 |
| --- | --- | --- | --- |
| OpenAI Responses／Codex | Responses 的 `conversation` 是多輪 items 的連續性容器；ChatGPT project 讓同 project chats 共用 files／instructions／sources，而各 chat 保留自己的 transcript；本機 Codex Memory 又是按 host／Codex home 分開，並可逐 chat 控制 use／contribute | conversation、project context 與 durable Memory 是不同邊界；OpenAI 產品也沒有把所有狀態放進單一 global context | OpenAI 沒公開一個可供第三方直接複製的「per-user／per-project Semantic Memory ACL schema」；`safety_identifier` 是濫用偵測識別，不是 Memory 授權或 scope key |
| Claude 消費型 Memory | 每個 project 有獨立 memory space 與 project summary，與 project 外聊天分開 | project-scoped Memory 是已出貨產品行為，不是 Caliburn 自創概念 | Claude 未公開其內部 principal、索引與 ACL schema |
| Anthropic Managed Agents | Memory store 是 workspace-scoped；session 建立時明確 attach 最多 8 個 stores；store 可依 end user、team、project 或生命週期拆分；每個 mount 有 `read_only／read_write`，store ID 必須屬於 caller 的 organization／workspace | 一個 session 可以明確讀多個不同 owner／用途的 store；資料所有權、生命週期與 access mode 可分開 | Managed Agents 的 store 形狀不等於 Claude 消費型 Memory 的內部實作，也不證明所有產品都要一 scope 一實體 store |
| Google Memory Bank | 每個 scope 是隔離 collection；普通 retrieval 只考慮**完全相同 scope**；scope 建立後 immutable；consolidation 只在同 scope 內；IAM Conditions 可把已驗證 principal 的 viewer／editor 權限綁到 exact scope 或特定 scope 條件 | scope 是 retrieval、consolidation 與 revision 的資料邊界，principal／IAM 是另外的權限邊界；兩者都需要 | scope dictionary 本身不是身分驗證；`ListMemories／PurgeMemories` 等跨 scope API 不支援 scope IAM Conditions，必須視為另外的高權限管理面，不能當一般 recall |
| AWS AgentCore Memory | short-term events 由 `actorId + sessionId` 組織；long-term records 由 namespace 組織，可使用 actor／session／strategy 與自訂 organization／team／environment 維度；IAM 可限制 exact namespace 或 namespace path | actor、session 與 long-term namespace 可採不同粒度；跨 session Memory 不應被綁死在單一 session | `actorId` 只是資料歸屬／組織值，不等同 API caller 的 IAM principal；AWS 甚至允許明確的 `/` global namespace，故安全性取決於應用選擇與 IAM，而非字串名稱本身 |
| LangGraph／LangMem | checkpointer 以 `thread_id` 保存 thread state；Store 以任意 tuple namespace 保存跨 thread Memory；LangMem 可由 runtime config 展開 user／org／project namespace，agent 本身不必知道實際位置；read 與 write tool 可使用不同 namespace | 成熟框架已提供 thread、Store namespace、動態 scope 與分離 read／write target 的 primitive，不需自造儲存抽象 | namespace 是 routing／addressing primitive，不是自動 AuthZ。LangSmith 官方明說：沒有 custom authentication 時只看得到 API-key owner；只做 AuthN、未做 resource AuthZ 時，使用者仍能看到彼此資源 |

跨家最穩定的共同點不是某一組固定欄位，而是：

1. **thread/session 與 durable semantic scope 分開。** session 保存一段互動；同一個長期 scope 可以跨多個 sessions，單一 session 也可能明確讀多個 scopes。
2. **資料 scope 與 caller principal 分開。** scope 說明 Memory 屬於哪個集合；AuthN／AuthZ 說明目前 caller 是否能對該集合執行某項操作。
3. **一般召回與 consolidation 不做隱含全域混合。** Google 採 exact scope，Anthropic 採顯式 attach stores，AWS／LangMem 則要求應用選定 namespace；跨 scope 是明確能力，不是查不到就偷偷 fallback global。
4. **讀取範圍與寫入目標可以不同，但必須明確。** Anthropic 支援多 store 與 access mode，LangMem 也示範 agent-specific write 加 shared-team read；不能因讀到 shared Memory 就默認可改它。
5. **bulk／admin 是另一條權限較高的路徑。** Google 的跨 scope list／purge 限制直接證明，普通 user-scoped recall 與管理全庫不能共用模糊權限。

###### F5-c. 三個通用方案候選

**A. 讓模型在 tool payload 自己填 principal／user ID／scope 路徑**

- 優點：表面 schema 直接、似乎很彈性。
- 缺點：把不受信任的模型輸出當成安全邊界；填錯或 prompt injection 都可能讀寫另一個 scope。也浪費 token 讓模型重複填 runtime 已知資料。
- 研究判斷：**排除。** LangMem 的成熟做法恰好相反：agent 只知道有 Memory tool，namespace template 由 runtime config 展開。

**B. 只用 `thread_id／session_id` 隔離全部 Memory**

- 優點：最少概念；每個 conversation 天然分開。
- 缺點：無法形成跨 session 的 durable Memory；若重用 thread 又會把所有用途永久綁成同一 scope。與 OpenAI／Anthropic 的 project context、Google user scope、AWS actor-level namespace 及 LangGraph Store 的跨 thread 目的都不符。
- 研究判斷：**排除作為通用 long-term Memory 邊界。** thread 仍保留作 short-term continuity。

**C. trusted runtime 解出 principal＋授權 scopes；thread 與 semantic scope 分離（建議）**

1. 呼叫進入時由可信 runtime／應用 context 驗證 principal，解析允許讀取、允許寫入與管理的 scopes；模型不能提供或改寫這些安全識別值。
2. `thread/session` 只選擇短期 conversation state；durable Semantic Memory 另以明確 scope 尋址，兩者不可互相冒充。
3. 一般 create／update／delete／revision／consolidation 每次都只有一個明確 target scope；該 scope 在工作排程、retry 與發布途中不得被模型換掉。
4. read 可以是零到多個**明確 attach 且已授權**的 scopes；每筆結果仍保留 origin scope 與 access mode，避免讀取 shared knowledge 後誤寫回 shared scope。
5. 普通 retrieval 預設只查要求的 exact scope；跨 project／team／全域 recall 必須是明確授權與明確啟用的路徑，不做隱含 fallback。
6. bulk list／purge／跨 scope migration 另列為管理能力，不與一般 Memory tool 共用權限語意。

這是可觀察的隔離行為，不是要求固定採 `org/user/project/thread` 四層，也沒有決定 scope 是一個 tuple、dictionary、store、資料庫 schema 或實體分庫。特定產品日後可以只有一個 semantic scope，也可以有 user＋project＋shared reference；前提是映射明確，而不是刪掉隔離概念。

###### F5-d. 尚不能下結論的部分

- OpenAI 與 Claude 消費型產品的內部 Memory ACL／namespace schema 未公開；不能聲稱它們使用 Google scope、AWS path 或 LangGraph tuple。
- 一個 scope 是否一個實體 store，或同一 store 內用 immutable scope partition，跨家沒有共同答案。
- shared scope 是否預設 read-only、何種資料可持久化、prompt injection 如何防護，屬 F6／F7，不在 F5 偷渡裁決。
- 單機單一操作者產品如何把 principal 與 semantic scope 簡化，屬產品 mapping；不能反過來刪除通用方案的邊界。
- 權限撤銷後，已在背景執行的工作是否必須重新 AuthZ、如何中止或發布，需和 F4 anti-resurrection／後續框架機制一起研究；F5 只要求它不得換到別的 scope。

###### F5-e. 暫時裁決

Owner 暫時確認方案 C 的通用行為：

- principal、semantic scope、session/thread、namespace 與 access mode 分工清楚；即使 scope 編碼在 namespace 中或值剛好相同，也不能因此推定已通過 AuthZ；
- trusted runtime 解析 principal 與授權 scopes，模型不填安全識別；
- 普通操作採明確 scope，預設不跨 scope，也不做 global fallback；
- read scopes 可多個，但必須明確 attach／授權並保留來源 scope；mutation 只有一個明確 target scope；
- bulk／admin operation 與一般 Memory tool 分開；
- 暫不選 scope 欄位、層級、資料表、實體 Store 數量或 Caliburn mapping。

B5 因此由候選升級為**暫時確認的通用基線**；它仍不是任何特定產品需求或實作選擇。F6～F9 在下文分別處理寫入資格、信任邊界、召回與成本／維運。

##### F6. Persistence eligibility：值得記得不等於允許保存

**狀態：官方資料已補查；Owner 於 2026-08-30 暫時接受方案 C。** 本節只回答「某段內容是否有資格進 durable Memory」，不決定特定產品的欄位、敏感分類清單、保留期、加密、UI 或模型呼叫次數。

###### F6-a. 各家官方實際公開的資格邊界

| 來源 | 官方明說的持久化資格／排除 | 官方沒有公開或不能據此推論的部分 |
| --- | --- | --- |
| OpenAI Codex Memories | Codex 只會把「eligible prior chats」中的 useful context 轉成 Memory；會跳過 active／short-lived sessions；每個 chat 可分別控制是否使用既有 Memory、是否貢獻未來 Memory；可設定凡使用 MCP、web search 或 tool search 的 chat 不參與 Memory generation；生成欄位會做 secrets redaction，但官方仍要求不要把 secrets 存進 Memory。 | 沒有公開「useful／eligible」的完整分類、評分門檻或 secrets classifier；不能聲稱 OpenAI 只用規則、只用 LLM，或所有外部 context 都預設排除。 |
| Claude 消費型 Memory | Claude 以個別 topic 保存日常且有助協作的脈絡，例如角色、專案、工作方式、技術偏好與進行中工作；可自動保存，也接受明確的「remember this」。Pause 後既不使用也不新增 Memory；incognito chat 不進 Memory。敏感 topic 預設不保存，必須由使用者 opt in；政府證件號、刑事紀錄、金融帳號與移民身分即使要求也不保存。 | 沒有公開 topic 抽取器、敏感分類器與 relevance ranking 的內部實作；這是 Claude 產品政策，不能直接冒充 Anthropic API Memory Tool 的通用預設。 |
| Anthropic API Memory Tool | Memory Tool 是 client-side CRUD／JIT-read primitive；應用可用 prompt 限定「只記某主題」。官方說 Claude 通常會拒絕把敏感資料寫進 Memory，但同時建議應用實作更嚴格的 validation／stripping。 | Tool 本身沒有宣稱提供一套完整、不可繞過的產品級 persistence policy；資料是否允許保存及保存在哪裡仍由應用負責。 |
| Google Memory Bank | 不是每段互動都產生 Memory；內容必須被判定對未來有價值，而且至少符合一個 configured memory topic。Topic 可用 managed／custom instructions 定義，並可用正例與「應產生空結果」的反例 few-shot 教導邊界；explicit remember／forget 是官方 managed topic 之一。Google 同時警告敏感／個資排除不是絕對可靠，不能只靠該功能過濾。 | 沒有公開 usefulness 與敏感偵測的內部模型／規則比例及精確門檻。 |
| AWS AgentCore Memory | 若沒有設定 long-term memory strategy，就不會抽取 long-term records；strategy 決定抽取 user preference、semantic facts、summary、episode 或自訂內容。Built-in override 可限定只抽某領域並控制粒度；語意策略在沒有 relevant／noteworthy information 時回空列表。 | 本輪查到的官方 Memory strategy 文件沒有宣稱會對所有策略套同一份敏感資料禁止清單；加密文件說明如何保護已保存資料，不等於內容因此具有保存資格。 |
| LangGraph／LangMem | LangGraph Store 提供 durable JSON／namespace primitive；LangMem 以可自訂 instructions、schema 與 permitted actions 的 manager／tool 做抽取、更新與刪除。預設 manage tool 鼓勵記 preference、明確 remember 指令、重要工作脈絡及過時 Memory 修正。 | Framework 沒有替應用決定完整隱私、同意或法遵政策；「schema 驗證通過」也不代表內容被允許永久保存。 |

以上表格刻意把**產品政策**與**開發框架 primitive**分開。Claude 消費型產品已提供明確敏感 topic 政策，不代表直接啟用 Anthropic Memory Tool 就自動得到同一政策；LangMem、AgentCore 與 Memory Bank 能協助抽取／整併，也不會替產品 owner 決定全部資料治理規則。

###### F6-b. 跨家共同點與只屬整合推論的部分

可由多家官方資料直接支持的共同點：

1. **Durable Memory 是選取層，不是 transcript 副本。** 空結果是正常成功結果；短暫、尚在進行或沒有未來價值的內容可以不保存。
2. **「記什麼」要受目的／topic／strategy 約束。** Google 用 memory topics＋few-shots，AWS 用 strategies／override，Anthropic Memory Tool 與 LangMem 用 instructions／schema；不能只寫模糊的「記住所有重要資訊」。
3. **來源會話是否可供學習，是外層資格。** OpenAI 提供每 chat 是否 contribute 的控制與外部 context 排除選項；Claude 提供 Pause／incognito。這與「已經存了什麼」是兩件事。
4. **明確 remember 是強烈意圖，但不是無條件越權。** Google 與 Claude 都支援 explicit remember；Claude 同時證明有些內容即使使用者要求也不能保存。
5. **敏感資料偵測不是唯一保證。** OpenAI redaction 後仍警告不要存 secrets；Google 明說過濾不可靠；Anthropic API 文件建議應用做更嚴格 validation。
6. **抽取、consolidation、加密與 retention 不能冒充 admission policy。** 它們分別處理內容形成、更新衝突、儲存保護與保存時間，並不回答內容一開始是否應進 durable Memory。

下列是根據上述共同點形成的**整合推論**，不是任何一家公開宣稱的內部固定管線：durable write 前需要同時通過「來源／會話允許」、「語意上值得且符合目的」與「產品政策允許」三種邏輯資格。三者可由同一次模型 run、模型加規則、背景 manager 或其他機制實現；本節不預選實作。

###### F6-c. 不要混在一起的四種判斷

1. **Persistence eligibility**：這段內容可不可以永久保存；本題處理。
2. **Epistemic status**：內容是已知、推測、矛盾或未解；沿用 D1／F2。未解問題若對未來有用，可以以「未解」狀態持久化，但不能偽裝成已確認事實。
3. **Consolidation**：已具資格的新內容要新增、更新、取代、跳過或刪除哪筆舊 Memory；沿用 D4／D6。
4. **Scope／access／trust**：內容寫到哪個範圍、誰可讀寫，以及日後能不能當指令；分別屬 F5 與 F7。

因此，重複或矛盾不必一律判成「禁止保存」；它可能是 consolidation 的輸入。相反地，一段內容即使完全正確且有用，只要來源會話禁止學習、含 credentials／secrets，或不符合產品允許目的，仍不應進 durable Memory。

###### F6-d. 三個通用方案候選

**方案 A：模型自行判斷，輸出通過就直接保存**

- 優點：流程最短、程式最少。
- 缺點：和 Google「敏感過濾不可單獨依賴」、OpenAI「redaction 後仍不得存 secrets」、Anthropic「應用需更嚴格 validation」直接衝突；prompt 只寫「記重要的」也沒有明確目的邊界。
- 研究判斷：**排除。**

**方案 B：固定 allowlist／denylist 完全決定，不讓模型判斷價值**

- 優點：規則清楚、容易稽核，適合 credentials 等硬禁止項。
- 缺點：難以判斷自然語言內容是否具有未來價值，也難涵蓋新的領域 topic；會失去 Google topics／few-shots、AWS strategy 與 Claude topic Memory 所提供的語意選取能力。
- 研究判斷：可作 policy gate，但不適合作為完整通用方案。

**方案 C：分層資格（推薦）**

邏輯上依序確認：

1. **來源／會話資格**：learn／contribute 已允許，且不是 incognito、no-memory 或被排除的來源類型；
2. **語意資格**：內容對未來互動有持續價值，符合明確 topic／strategy／purpose，不只是寒暄、短暫中間狀態或無資訊內容；
3. **政策資格**：由受信任的應用政策執行硬限制；credentials／secrets 不得進 durable semantic Memory，敏感個資的自動保存預設需要明確產品目的與使用者控制，必要時可有永不保存類別；
4. 通過後才交給既有 validation／consolidation／publish 邊界。

補充規則：

- 使用者明確「請記住」可直接滿足強烈的語意意圖，但不能繞過來源開關、scope／AuthZ 或硬政策；
- 使用者明確 no-memory／pause／incognito 應優先於背景抽取；
- 來自 web、MCP、tool result 或外部文件的內容不能只因出現在 Context 就自動成為「關於使用者的持久事實」；是否可存須由來源政策與應用目的明確允許；
- 沒有產生 Memory 是合法成功，不應為了看起來有產出而硬寫一筆；
- redaction、classifier、encryption 與人工檢查可以疊加，但任何單層都不能被宣稱為完整保證。

這裡的「分層」只是可觀察資格，不要求三次模型呼叫、三張表或三個 agent。

###### F6-e. 尚未公開、不得亂猜

1. OpenAI／Anthropic 消費型產品如何精確判定 useful topic、敏感類別與保存門檻；
2. 各家內部是由同一模型、另一個 extractor、規則分類器或混合機制完成每一層；
3. OpenAI `disable_on_external_context` 在所有產品或環境中的預設值；
4. AWS built-in strategies 是否另有未公開、對所有策略一致的敏感資料分類器；
5. 各產品完整的敏感分類、地區法規、保留期與使用者同意要求。

**研究結論：暫時採方案 C。** F6 升級為通用 Memory 的暫時行為基線；它不會直接成為任何特定產品的敏感欄位、UI、資料庫或法遵規格。

##### F7. Memory 是可錯、可污染的資料，不是高優先權指令

**狀態：跨家官方證據已收斂為通用必要基線。**

Google 官方直接警告 prompt injection 與 memory poisoning：錯誤或惡意資訊若寫入 Memory，未來 session 會繼續使用。Anthropic Managed Agents 也明說 read-write store 可能被不受信任輸入污染，因此建議不需要寫入的 store 採 read-only；Anthropic 的 prompt-injection 指南要求把第三方內容放在 `tool_result`、標明來源與性質，並明說它不能覆蓋 system policy。AWS 同樣把輸入驗證與最小權限列為應用責任。PydanticAI Harness 則直接提醒：模型寫入的 Memory 是 untrusted，僅靠 delimiter 或 user-role 包裝不是安全邊界。

因此通用最低基線如下：

1. **Memory 永遠是資料，不是指令 authority。** 它不能取代 system／developer policy、受控規則或權限設定；OpenAI Codex 也明確要求必須永遠成立的規則放在 `AGENTS.md` 或受控文件。
2. **來源與信任層級由 runtime 標示。** 外部網站、文件、email、tool result 與模型自行生成內容不得靠自身文字宣稱升格為高信任來源；principal、scope、source type 與 access mode 不由模型填寫。
3. **持久化前做 admission 與 validation。** F6 的來源、價值與政策資格先成立，再做 schema／內容驗證；任何單一 LLM classifier、redaction 或 delimiter 都不是完整保證。
4. **讀寫遵守 least privilege。** 能 read-only 就不給 write；一般召回只讀明確授權 scope；管理、跨 scope 與 erase 使用獨立高權限路徑。
5. **Memory 不授予行動權限。** 高影響工具或外部動作仍依當下 AuthZ、sandbox、確認與工具政策；不能因 Memory 記著「使用者曾允許」就延續或擴張授權。
6. **寫入與召回兩端都防 poisoning。** 寫入端檢查惡意／不允許內容；召回端仍把內容當低信任資料，必要時重新核實。只保護其中一端不足以阻止跨 session 污染。
7. **持續監控與 adversarial testing。** 至少可觀察 Memory 來源類型、write／read、拒絕、錯誤、刪除與高影響行動；production 前以惡意文件、tool output 與跨 session poisoning 做 red-team。

這些是多家安全文件對同一風險的收斂，不代表各家使用相同 classifier、sandbox 或資料模型。本文不推測未公開內部實作。

直接來源：

- [Anthropic — Mitigate jailbreaks and prompt injections](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks)
- [Anthropic — Managed Agents Memory：read-only／read-write 與持久污染風險](https://platform.claude.com/docs/en/managed-agents/memory)
- [Google Cloud — Memory Bank governance 與 memory poisoning](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank)
- [AWS — AgentCore Memory best practices](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/best-practices.html)
- [PydanticAI Harness — Memory security](https://pydantic.dev/docs/ai/harness/memory/)

##### F8. Recall／retrieval：先精確、再有界自動召回、最後按需擴展

各家沒有統一使用同一種搜尋技術，但公開行為高度收斂在「不要全量注入」以及「先縮小 scope，再取少量相關內容」。現行差異如下：

| 做法 | 現行代表 | 適用與限制 |
| --- | --- | --- |
| Exact ID／path／metadata filter | Google exact scope、AWS namespace、Letta files、Pydantic literal search、LangGraph Store filter | 已知目標時最精確、低成本；不能處理未知措辭或語意近似 |
| Semantic similarity | Google、AWS、LangGraph Store、Microsoft Foundry | 能找語意近似；對專有名詞、否定、時間與精確字串可能不足 |
| Keyword／full-text | Claude past-chat search、Letta local transcripts、Graphiti BM25 | 適合專有名詞與原句；改寫或同義詞 recall 較弱 |
| Hybrid multi-signal | Mem0 V3、Graphiti、Letta optional mod、CrewAI | 同時利用 lexical／semantic／entity／recency；效果通常更穩，但成本與調參增加 |
| Graph／temporal traversal | Graphiti、Mem0 V3 built-in graph boost | 關係、多跳與時間問題有價值；不是一般 Memory 的免費預設 |
| Reranking | Graphiti、Mem0 optional rerank | 複雜 query 可改善排序；增加延遲與費用，需代表性 query 驗證 |

**通用研究結論：**

1. 已知 ID、scope、topic 或 path 時先做 deterministic exact lookup／filter，不用 embedding 猜。
2. 一般模型步驟前可自動取少量有界結果，避免模型不知道自己遺漏了什麼；結果數與 token 必須有上限。
3. 模型仍可按需 `search／read` 更舊、更細或原始 conversation；自動召回與 tool search 是互補，不是二選一。
4. Retrieval engine 是可替換策略。Hybrid 是目前明顯趨勢，但 Letta 等現行系統仍可只靠 file tree＋keyword，因此不能升格為所有產品強制要求。
5. Reranker、graph、時間訊號只在資料形狀或代表性 query 證明必要時啟用；不能用供應商自己的 benchmark 直接推論所有場景最佳。
6. 不把相似度分數當事實可信度。Retrieval score 只表示排序相關性，不表示內容正確、目前有效或已授權。

直接來源：

- [Google Cloud — Retrieve memories：exact scope、all／similarity retrieval](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/fetch-memories)
- [LangGraph — Memory overview：Store semantic search 與 content filter](https://docs.langchain.com/oss/python/concepts/memory)
- [Letta — MemFS：file search、conversation search 與 optional hybrid mod](https://docs.letta.com/concepts/memfs)
- [Mem0 V3 — hybrid multi-signal retrieval 與 optional rerank](https://docs.mem0.ai/migration/platform-v2-to-v3)
- [Graphiti — Search and reranking](https://help.getzep.com/graphiti/working-with-data/searching)

##### F9. 成本、延遲與可營運性：正確性決定 hot path，其餘背景化

現行官方方案共同證明，Memory 不只是「多一個資料庫」；抽取、consolidation、embedding、rerank 與背景任務都可能產生模型費用、延遲與失敗。Google／AWS 將生成做成可非同步 operation；Codex 會在閒置後 best-effort 生成且可能跳過；CrewAI 明確處理 non-blocking write 與 recall 前的 drain/read barrier；Mem0 V3 add 回傳 `PENDING event_id`，rerank 預設關閉並明列約 200–400ms 額外延遲。

**通用研究結論：**

1. 只有下一個依賴步驟的正確性需要新 Memory 時，才把相關 update 放在 hot path；去重、重分類、壓縮與廣泛 consolidation 優先背景化。
2. 不要求每輪一定產生 Memory，也不要求每輪額外模型呼叫；空結果、跳過與 deterministic update 都是合法路徑。
3. 每次自動 recall 設定 top-k／token／line budget；按需搜尋另設工具與總成本上限，避免查不到就無限擴張。
4. 非同步 API 的「accepted／PENDING」不等於「已可召回」。必須能觀察 queued／running／succeeded／failed 或等價狀態，並在依賴點設 read barrier。
5. Retry 必須 bounded、typed、idempotent；失敗保留 raw source 與舊 current head，不以空白或半成品覆蓋。
6. 至少觀察 extraction/consolidation 次數、模型／embedding token、延遲、空結果率、拒絕／失敗、recall 命中與注入量。若框架不提供，產品仍需補 instrumentation；不能把背景 pipeline 當黑盒。
7. Prompt caching／compaction 可降低 context 成本或維持長對話，但不替代 durable Memory 的選取、修訂、刪除與召回。

直接來源：

- [OpenAI — Codex Memories：background best-effort 與跳過條件](https://learn.chatgpt.com/docs/customization/memories)
- [Google Cloud — Memory Bank：asynchronous generation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank)
- [AWS — Ingest content：非同步 job、status 與 redrive](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-ingest-data.html)
- [CrewAI — Unified Memory：non-blocking writes 與 read barrier](https://docs.crewai.com/en/concepts/memory)
- [Mem0 V3 — async add、rerank 延遲與代表性 query 重調](https://docs.mem0.ai/migration/platform-v2-to-v3)

#### 7A-f. 官方尚未公開，現在不得下結論的項目

1. OpenAI／Anthropic 消費型產品如何在內部做 retrieval ranking、衝突裁決與 store schema；
2. 各家是否以 transaction、epoch、tombstone 或 cancellation 防止刪除後復活；
3. 各家是否對跨多筆 Memory 提供同一個原子發布單位；
4. supporting evidence 如何精確映射到每個 Memory fragment。
5. OpenAI／Anthropic 消費型 Memory 的 usefulness／sensitive classifier、內部門檻與模型／規則分工；
6. AWS 是否對所有 Memory strategies 套用未公開的統一敏感資料排除器。

因此本文只能要求可觀察結果，不能聲稱「大廠都使用某個特定資料表／演算法」。後續框架 mapping 必須重新檢查候選框架能否提供這些結果，不能用名詞相似就視為能力相同。

#### 7A-g. 本輪新增官方來源

- [OpenAI — Codex Memories：Memory 不是規則 authority、use／contribute 分離、背景更新與 secrets redaction](https://learn.chatgpt.com/docs/customization/memories)
- [OpenAI — Delete a conversation：刪 conversation container 不會連帶刪 items](https://developers.openai.com/api/reference/typescript/resources/conversations/methods/delete)
- [OpenAI — Delete a conversation item：conversation item 有獨立刪除操作](https://developers.openai.com/api/reference/ruby/resources/conversations/subresources/items/methods/delete)
- [Claude — 現行 chat search 與 Memory：topic Memory、explicit remember、Pause／Reset／incognito、敏感 topic 政策，以及刪 chat 不連帶刪 Memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Anthropic — Managed Agents Memory：scope、read-only／read-write、memory poisoning、optimistic concurrency、versions 與 redaction](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Delete a Memory：刪 current Memory 後 retained versions 仍存在](https://platform.claude.com/docs/en/api/beta/memory_stores/memories/delete)
- [Anthropic — Redact a Memory version：抹除 retained version 內容但保留 audit row](https://platform.claude.com/docs/en/api/beta/memory_stores/memory_versions/redact)
- [Anthropic — Mitigate jailbreaks and prompt injections：不受信任內容與指令分層、least privilege](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks)
- [Google Cloud — Memory Bank：scope isolation、IAM、prompt injection 與 memory poisoning](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank)
- [Google Cloud — Generate memories：價值選取與敏感資料過濾限制](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google Cloud — API quickstart：非同步 delete／purge 與 semantic forget](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/api-quickstart)
- [Google Cloud — Memory revisions：current consolidated state 與 immutable history](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)
- [AWS — Delete an event：來源刪除不會連帶刪除衍生 long-term Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/short-term-delete-event.html)
- [AWS — Delete memory records：衍生 long-term Memory 的獨立刪除](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-delete-memory-records.html)
- [AWS — IngestData：受理與完成分離的非同步 long-term Memory extraction](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-ingest-data.html)
- [AWS — Redrive failed ingestions：失敗 extraction 可於稍後重新執行](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-redrive.html)
- [LangChain — Memory overview：hot path 與 background 的時效取捨](https://docs.langchain.com/oss/python/concepts/memory)
- [LangGraph — Persistence／fault tolerance：checkpoint、pending writes、replay 與冪等 side effects](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Functional API：retry／resume 下副作用需冪等，未完成 task 可能重跑](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [LangMem — Memory manager：對既有 Memory 的 update／delete 能力](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem — Memory tools：模型可用可自訂 instructions／schema／actions 的 create／update／delete 工具管理持久 Memory](https://langchain-ai.github.io/langmem/reference/tools/)
- [OpenAI — Responses create：`conversation` 是多輪 items 容器；`safety_identifier` 用於濫用偵測而非 Memory 授權](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [OpenAI — Projects and chats：project 共享 files／instructions／sources，各 chat 保留自己的 transcript](https://learn.chatgpt.com/docs/projects)
- [Claude — 現行 project Memory：每個 project 有獨立 memory space 與 project summary](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Anthropic — Managed Agents Sessions API：memory store 必須屬 caller organization／workspace，attachment 有 read-only／read-write](https://platform.claude.com/docs/en/api/beta/sessions)
- [Google Cloud — Fetch memories：普通 retrieval 只考慮 exact same scope，scope 建立後 immutable](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/fetch-memories)
- [Google Cloud — Memory Bank IAM Conditions：principal、viewer／editor roles 與 memory scope 條件分離](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/iam-conditions)
- [AWS — Long-term Memory namespaces：actor／session／custom dimensions 與 namespace IAM](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/specify-long-term-memory-organization.html)
- [AWS — AgentCore Memory harness：short-term 依 actor＋session、long-term 依 namespace／strategy 召回](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-memory.html)
- [LangGraph — Persistence：thread checkpoint 與跨 thread Store namespace 分層](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangSmith — Authentication & access control：AuthN 與 resource AuthZ 分離](https://docs.langchain.com/langsmith/auth)
- [LangSmith — Custom auth 教學：只驗證登入、未做 resource authorization 時仍會互見資源](https://docs.langchain.com/langsmith/set-up-custom-auth)
- [LangMem — Dynamic namespaces：namespace 由 runtime config 展開，agent 不必知道實際 user／org／project 路徑](https://langchain-ai.github.io/langmem/guides/dynamically_configure_namespaces/)
- [Anthropic — Memory Tool：主題限制、敏感資料 validation 與應用自主管理的 client-side primitive](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Google Cloud — Memory Bank setup：managed／custom topics、正反 few-shot 與 TTL](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup)
- [Google Cloud — Memory Bank troubleshooting：沒有符合 topic／價值門檻時，空結果是正常成功](https://docs.cloud.google.com/gemini-enterprise-agent-platform/troubleshooting/memory-bank)
- [AWS — Memory strategies：沒有 strategy 就不抽 long-term Memory；strategy 決定抽取類型](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [AWS — Built-in strategy customization：以 instructions 限定領域與粒度，保留 managed schema](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-custom-strategy.html)
- [AWS — Semantic Memory system prompt：relevant／noteworthy 選取、explicit／implicit facts 與空列表](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [AWS — AgentCore Memory encryption：敏感資料的儲存保護，不等同 persistence admission](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/storage-encryption.html)
- [LangMem — Semantic extraction：由 instructions／schema 定義抽取範圍，並允許空／更新／刪除](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)

## 8. 已確認不應再當成最新基線的做法

1. **完整歷史每輪全部重送**：成本與 Context 品質都不可長期擴展；主流已採有界 Context 與召回。
2. **單一總摘要就是全部 Memory**：Anthropic 已以分類 topics 取代舊每日總摘要；其他現行方案也普遍保留可獨立修訂的 facts／files／records。摘要可作導航或 compaction，不應自動冒充完整長期 Memory。
3. **向量資料庫等於 Memory**：向量搜尋只覆蓋 retrieval；不負責什麼值得保存、如何更正、淘汰、隔離或注入。
4. **Compaction 等於 Memory**：它主要解決當前 Context 大小，不保證形成可靠、可管理的長期理解。
5. **Prompt cache 等於 Memory**：cache 只降低重複前綴的計算成本／延遲，不替產品保存或選取語意。
6. **舊 LangChain `ConversationBufferMemory`**：不能代表 LangGraph／LangChain 1.x 的現行 short-term／long-term Memory 分層。
7. **舊 LlamaIndex Memory 類別**：`ChatMemoryBuffer`、`ChatSummaryMemoryBuffer`、`VectorMemory`、`SimpleComposableMemory` 均在現行頁面列為 deprecated，由新的 `Memory` 與 blocks 取代。
8. **舊 Letta core／archival blocks 作為現行主架構**：Letta 現行所有 agent 改用 Git-backed MemFS；舊 shared memory blocks 也被標為 legacy。
9. **舊 CrewAI short／long／entity／external 四套 API**：CrewAI 1.15.18 已改成 Unified Memory；不得用舊分類推論目前寫入與召回語意。
10. **AutoGen 0.2 文件或 API**：現行 stable 文件已提供 migration guide 至 0.4 系列；舊範例不能代表目前 `Memory` protocol。
11. **把 Mem0 品牌當成單一固定語意**：現行 V3 migration／Add 頁與 Memory Types 頁對 ADD-only 和 ADD／UPDATE／DELETE 有矛盾；採用前必須鎖定 SDK、backend、endpoint 與版本，以實際 runtime 驗證。
12. **只追加、永不更正是通用共識**：Mem0 V3 Platform 是特定 ADD-only＋retrieval-time ranking 路線；Google、Claude、AWS、LangMem 等仍採 update／delete／consolidation。它不能推翻 B7 的可修訂生命週期要求。
13. **把已公開的 ChatGPT Dreaming 高階流程擴寫成私有實作細節**：OpenAI 已公開 Dreaming 會在背景參考多段聊天並綜合 freshness／relevance，不能再說背景綜合完全未核實；但 record schema、Prompt、ranking、embedding、衝突演算法與內部門檻仍未公開，本文不得自行補完。

## 9. 通用 LLM Memory 的完整研究結論

### 9.1 正規化完整流程

```text
0. trusted runtime 解出 principal、session/thread、允許讀寫 scopes
    ↓
1. 原始 conversation／event 先耐久保存
    ↓
2. active context 只帶近期、有界內容；超長時 compaction／清理
    ↓
3. 依 source-use／learn 控制判斷本來源能否參與持久學習
    ↓
4. 依 topic／purpose／strategy 選取具有未來價值的候選；空結果合法
    ↓
5. 受信任 policy gate 排除 secrets／禁止類別並驗證內容；Memory 仍是低信任資料
    ↓
6. 在 exact target scope 中 extraction／consolidation，形成 current head＋revision
    ↓
7. 發布成功後才對依賴者可見；非關鍵整理可背景，失敗可觀察、可有界重試
    ↓
8. 下一個模型步驟先做少量有界自動 recall
    ↓
9. 模型需要細節時再 exact lookup／search／read Memory 或原始 conversation
    ↓
10. 召回結果以資料身分加入 Context，不得覆蓋 policy 或授予權限
    ↓
11. 使用者可自然語言更正、查看、forget／delete／reset；舊 head 不再一般召回
    ↓
12. 背景去重、重分類、Dreaming／reflection、graph enrichment 依需求選用
```

其中 0～11 是由 B1～B14 與 F1～F9 組成的完整通用行為；第 12 步不是每個系統都需要。流程順序是語意依賴關係，不要求每格是一個 agent、一個模型 call、一張表或一個 framework node。

### 9.2 必要基線與可選設計的最終分界

| 類別 | 通用必要 | 仍屬可選 |
| --- | --- | --- |
| 資料分層 | Active context、raw conversation/events、durable Memory 分開 | 是否另有 knowledge graph、episode store 或 Git repository |
| 寫入 | 選取而非全抄；空結果合法；scope 與 policy gate | 每輪、背景批次、顯式 tool、第二模型／Dreaming |
| 表徵 | 可獨立修訂、語意完整、有 current head | Topics、JSON profile、collection、Markdown files、atomic facts、graph |
| 修訂 | Update／delete／失效、revision／audit 或等價能力 | 完整 bi-temporal model、Git worktree、使用者直接編輯底層檔 |
| 召回 | Scope first、有界、可按需擴展 | Vector、keyword、hybrid、entity、graph、cross-encoder rerank |
| 安全 | Trusted runtime identity／scope、低信任資料、least privilege、權限不由 Memory 延續 | 特定 classifier、Model Armor、第二模型 screening、特定敏感分類 |
| 使用者控制 | 更正、forget/delete/reset 邊界清楚；use 與 learn 可分離 | 是否露出 pause/incognito、直接編輯、完整 revision UI |
| 營運 | Accepted 不等於 published；狀態、成本、失敗與 bounded retry 可觀察 | Queue、transaction、epoch、tombstone、特定 observability backend |

### 9.3 各家定位矩陣

| 來源 | 主要表徵／流程 | 寫入時機 | 召回 | 修訂／治理 | 最重要限制 |
| --- | --- | --- | --- | --- | --- |
| OpenAI Codex | Phase 1 DB records（raw memory／rollout summary）＋`raw_memories.md`／`rollout_summaries`＋`MEMORY.md`＋小型 `memory_summary.md`＋可選 skills | root session 啟動時背景兩階段、bounded／best-effort | summary 預載；keyword search → handbook → 1～2 份詳細檔 → 必要時原始 rollout | claim／lease、global lock、git diff、usage selection、redaction、retry backoff、citation telemetry | coding-agent task／cwd schema 不可直接照搬；ChatGPT 私有 ranking/schema 仍未知 |
| OpenAI API | Conversations items＋compaction | 應用控制 | 直接串 conversation state | item／conversation 有各自 API | Conversation continuity／compaction 不等於 semantic Memory |
| OpenAI Agents SDK Sandbox Memory | `sessions/*.jsonl`＋`memory_summary.md`＋`MEMORY.md`＋raw／rollout details＋skills | session close 後兩階段生成；讀取時可 live update | developer prompt 注入 summary，詳細檔 progressive disclosure | read／generate／live update 可分開；layout 可隔離；`extra_prompt` 限定 domain signal | Beta；框架不替產品定義要記住的領域內容 |
| Claude 消費型 | 分類 topics＋獨立 chat search | 對話中自動更新／顯式 remember | topic 自動使用，舊聊天按需 RAG | edit/delete/reset/pause/incognito、敏感 topic policy | 私有 schema/ranking 未公開；source chat 刪除不會自動刪 topic |
| Claude Code／API | bounded index＋topic files／client-side Memory Tool | 模型按需 CRUD | 主索引預載＋詳細檔按需讀 | 應用掌握 storage/scope；Managed Agents 有 versions/OCC | coding/file 形狀非所有產品唯一答案；write store 有 poisoning 風險 |
| Google Memory Bank | scope 下 self-contained facts＋revisions | 觸發式／background extraction＋consolidation | exact scope 內 all/filter/similarity | create/update/delete、TTL、rollback、IAM | REST `v1beta1`；敏感過濾非絕對可靠 |
| AWS AgentCore | raw short-term events＋strategy-derived long-term records | 非同步 extraction／ingestion | namespace 內 semantic recall | strategy、IAM、job status/redrive | 自訂 schema 需 self-managed；模型 extraction/consolidation 計費 |
| Microsoft Foundry | `MemoryItem(memory_id, content, kind, scope)` | tool inactivity debounce、顯式 update API 或 direct remember／forget | `memory_search_preview` tool 或 store search | item CRUD、scope、TTL、update operation status | Preview；內部 extraction Prompt／ranking 未公開 |
| LangGraph／LangMem | thread state＋namespace JSON Store；profile/collection | hot path 或 background | filter／semantic＋應用注入 | CRUD／manager／extractor | LangGraph 不定義產品語意；LangMem 0.0.x |
| PydanticAI Harness | bounded Markdown notebook＋conversation snapshots | 模型 file operations | bounded injection＋literal search | OCC、runtime namespace | 0.x；沒有內建 semantic retrieval 或 verified provenance |
| CrewAI | Unified Memory、LLM-inferred scope/category/importance | task lifecycle、可非同步 | semantic＋recency＋importance、shallow/deep | consolidation、scope slices、read barrier | 高自動化代表更多模型／embedding 成本；task-oriented |
| AutoGen | 可替換 Memory protocol | 應用決定 | query＋update_context | add/clear/close | 只有 primitive，不含完整 admission/consolidation policy |
| LlamaIndex | FIFO short-term＋long-term blocks | overflow／block policy | 合併 short/long-term | blocks 可配置 | reduction／summary 可能遺失細節；舊 APIs deprecated |
| Letta | Git-backed MemFS；`system/` 預載、其他按需 | agent file edit＋commit；可 background dreaming | file tree/search＋獨立 conversation search | Git history/conflict/worktrees | 預設無 semantic/vector；舊 core/archival/shared block 基線已過時 |
| Mem0 V3 | ADD-only facts＋built-in entity graph（依 V3 migration） | single-pass async add | hybrid multi-signal，可選 rerank | expiration/delete API | 現行官方頁面語意互相矛盾，必須鎖版本驗證 |
| Zep／Graphiti | episodes＋temporal entities/edges/facts | episode ingestion＋LLM extraction | BM25/vector/graph/time＋多種 rerank | provenance、valid/invalid time | 功能與運維成本最高；供應商 benchmark 非中立證明 |

### 9.4 研究結論的使用方式

之後選任何框架或資料結構時，先檢查它能否覆蓋必要基線，再比較效果、正確性、可修訂性、召回品質、安全、成本、延遲、失敗恢復、成熟度與維護風險；「少寫多少程式」是次要效益，不是主要選擇標準。成熟框架若能達成相同目的，優先採用；只有缺少必要 primitive 或效果不夠時才補產品自訂機制。

本輪不選框架、不映射產品、不制定資料表／API，也不授權施工。

## 10. 目前討論紀錄

### 2026-08-30：研究順序與範圍對齊

Owner 已確認：

1. 目前只研究 Memory；
2. 先完整攤開最新大廠與框架流程；
3. 先找跨家共同點，共同點作為高可信、通常必要的基線；
4. 各家不同之處才是主要分析與討論的選項，也可暫時不選；
5. 現階段不研究實作細節；
6. 不先把 Caliburn 舊名稱、舊元件或既有實作套進來；
7. 研究與討論都可依新證據翻案，但不得未經討論擅自改變方向。

### 2026-08-30：D1 Memory 更新時機已對齊

Owner 接受依「下一個分析是否必須依賴」決定更新時效：新事實、更正與未解問題立即成為目前 run 的有效資訊；Semantic Memory 最遲須在下一個依賴點前可用，而非一律阻塞至本輪結束。若沒有後續依賴，不必等待 Memory；不影響正確性的去重、重整與跨輪綜合也可背景處理。原始 conversation 先保存，不能把背景 Memory pipeline 當成唯一資料保全機制。

此結論只裁決產品行為與正確性期限，尚未裁決：

- Memory 的正式表徵；
- 使用哪個框架或儲存 primitive；
- 是否需要額外模型 call；
- 背景工作排程與失敗重試細節。

### 2026-08-30：D2 Memory 表徵已對齊

Owner 接受以 topic／category 組織多筆可獨立修訂、語意完整的 Memory。這是在單一總摘要與過度碎片化原子 facts 之間的平衡；總摘要若需要，只能由正式 Memory 重建，不能反過來成為唯一資料。現階段不採 temporal graph，也尚未裁決正式分類、欄位、儲存方式或框架。

### 2026-08-30：D3 Recall 發動方式已對齊

Owner 接受每次模型分析前自動提供少量、相關且有界的 Memory，並讓模型在需要更舊或更細內容時主動 search／read。這項決定排除每輪全量 Memory 注入，也排除完全依賴模型先意識到遺忘才搜尋。檢索演算法、budget 與索引技術留待行為方案收斂後研究。

### 2026-08-30：D4 更正、衝突與時間變化已對齊

Owner 接受明確更正只留下新的 active head，舊理解退出一般召回但保留在預設不注入的 revision history；未明確裁決的衝突不得由模型依語氣強弱自行選邊，也不得硬合併成已確認事實。此結論已交叉檢查 OpenAI、Anthropic、Google、AWS 與 LangMem 官方資料；其中 immutable revision 是 Anthropic Managed Agents 與 Google 明確提供的成熟能力，不宣稱所有消費型產品都公開採相同內部實作。現實狀態真的隨時間改變時採「選擇性 temporal grounding」：active Memory 以目前狀態為主，只有仍影響目前理解的歷史、轉換或排程才保留時間脈絡；不把記憶寫入時間當成事實生效時間，通用基線也不建立完整 temporal graph。

### 2026-08-30：D5 原始 conversation 與 provenance 已對齊

Owner 接受 C「分層 provenance」：raw conversation／events 是獨立 source ledger；Semantic Memory 是可修訂的衍生理解；每個 Memory revision 至少由系統記錄 source session／event window／generation run，模型不得自行填 UUID、event ID、版本或時間。精確 message／quote citation 是可選 supporting evidence，不是每筆 Memory 的通用必填欄位；正常 Context 使用有界 Memory，只有核實、更正、衝突或回想細節時才 search／read 原始 conversation。

採用理由不是單純節省欄位，而是多家官方公開做法共同顯示原始 conversation 與 long-term Memory 應分層保留；OpenAI Codex 與 Claude 提供 supporting evidence／source-chat citation 能力，但 AWS、Google 與 LangMem 並未把逐筆精確 quote 公開定義為所有 Memory 的必要 schema。若未來測試顯示 source window 無法可靠查錯，才重新討論更細粒度的 supporting evidence。

### 2026-08-30：D6 更新一致性與失敗行為已對齊

OpenAI、Anthropic、Google、AWS、LangGraph 與 LangMem 的官方資料共同支持：來源事件耐久化、Memory 工作受理、current head 發布與下一個依賴分析讀到新版本是不同承諾；排程成功不能冒充已記住。Owner 接受 C「依賴 barrier＋版本化發布」：需要新理解的下一步等待相關 revision 成功發布，非關鍵 consolidation 可背景；以 optimistic concurrency 防止靜默覆蓋，以 idempotency＋typed bounded retry 避免重複與無限重試；失敗保留 raw source、舊 head、失敗原因與可安全重跑的工作。

此處仍只裁決可觀察行為，未選擇 Checkpoint／Store、資料表、狀態 enum、queue 或 transaction。跨多筆 Memory 的 ACID 原子性不是目前大廠公開共同保證，因此不先自建全庫 transaction；只要求單筆 head 原子切換，以及後續依賴者不得讀取未完整發布的相依更新組。

### 2026-08-30：D7 使用者控制已對齊

本輪把使用者控制拆成查看、自然語言更正、直接編輯、刪除／重設、使用／學習控制與來源歷史控制六個維度，並交叉核對 OpenAI Codex、Claude 消費型產品、Anthropic Managed Agents、Google Memory Bank、AWS AgentCore 與 LangMem。跨家證據支持：自然語言更正、可查看／刪除、來源與衍生 Memory 分層，以及「使用既有 Memory」與「由本次對話學習」不能混成單一模糊開關。直接編輯是成熟選項，但不是跨家共同必要條件；平台 CRUD 也不能直接等同終端使用者 UI。

Owner 接受通用方案 C「分層控制」：一般對話是主要更正方式，Memory 可檢查但不強制直接編輯內部 schema；保留明確 forget／delete／reset、來源刪除邊界，以及 use 與 learn/write 的分離能力。至於特定產品要露出哪些 UI、是否需要 incognito／pause、能否直接編輯，全部留到通用方案收斂後的產品 mapping。此裁決沒有授權實作。

### 2026-08-30：整體審核 F1 已對齊

Owner 接受縮小 D6 barrier：同一 run 的一般回答與澄清可直接使用本輪訊息及已驗證的暫時結果，不必先等 durable Memory 發布；只有下一個 run，或會形成 durable／對外可觀察效果且正確性確實依賴新理解的步驟，才等待相關 revision 成功發布。此修正只消除 D1／D6 的文字衝突，不取消 correctness barrier；F2～F9 後續均已分題研究。

### 2026-08-30：整體審核 F2 已對齊

Owner 接受「未解問題只以未解狀態生效」：它可阻止 AI 把不確定內容當成事實，並可觸發後續澄清；使用者確認後才由確定答案取代。此修正同步寫入 D1 第 3 點，但不預先決定狀態欄位、資料結構或模型呼叫方式；F3～F9 後續均已分題研究。

### 2026-08-30：整體審核 F3 已對齊

Owner 接受通用 Memory 應把 read/use 與 learn/write 視為可分離控制，任一能力關閉時，對應的召回或持久寫入不得仍在背景偷偷執行；目前對話訊息仍可供本輪使用。這項裁決刻意不考慮 Caliburn：特定產品是否提供開關、是否固定開啟、預設值與 UI，都留到通用方案收斂後的產品 mapping。

### 2026-08-30：整體審核 F4 已對齊

本輪補查 OpenAI、Claude 現行 Memory、Anthropic Managed Agents、Google Memory Bank、AWS AgentCore、LangGraph 與 LangMem 的刪除、版本、非同步處理及重試語意。官方共同證據不支持單一 delete 或預設全層 cascade，而是把 source、active Memory、revision／audit 與整體 reset／erase 分開；Google、AWS、LangGraph 亦證明 accepted、completed 與 retry／replay 不能混為一談。

Owner 接受分層方案 C，並只裁決外部行為：完成 forget／reset／erase 後，操作前的舊來源或舊工作不得把被移除內容重新發布；內部是 cancellation、generation fence、conditional write 或 tombstone 仍屬未知，不得假借大廠名義預選。這項確認未套入任何特定產品；F5～F9 後續均已分題研究。

### 2026-08-30：整體審核 F5 已暫時對齊

本輪補查 OpenAI Responses／Projects／Codex Memory、Claude project Memory、Anthropic Managed Agents、Google Memory Bank、AWS AgentCore、LangGraph／LangSmith 與 LangMem。共同證據顯示 principal、semantic scope、session／thread、namespace 與 access mode 是不同維度：scope／namespace 負責資料分區與尋址，AuthN／AuthZ 才負責誰能做什麼；只做其中一層都不能保證隔離。

Owner 暫時接受方案 C：由 trusted runtime 解出 principal 與已授權 scopes，模型不填安全識別；thread 只負責短期連續性；普通 Memory 操作使用明確 exact scope，不做隱含 global fallback；多 scope 讀取必須顯式 attach 並保留 origin，mutation 只有一個 target scope；bulk／admin 另列高權限路徑。這仍只是目前通用研究的最佳判斷，尚未選 scope 欄位、層級、Store 數量或 Caliburn mapping；產品 mapping 時可依產品證據重新比較其他方式。

### 2026-08-30：整體審核 F6 已暫時對齊

本輪補查 OpenAI Codex Memories、Claude 現行 Memory、Anthropic API Memory Tool、Google Memory Bank、AWS AgentCore Memory 與 LangGraph／LangMem。可由官方資料共同支持的是：durable Memory 屬選取層而非 transcript 副本；來源會話是否允許學習與內容是否值得保存是不同資格；抽取目的需由 topic／strategy／instructions 約束；明確 remember 是強烈意圖，但不能被推論為可以繞過所有產品政策；敏感資料偵測、redaction、加密或 schema validation 任一單層都不是完整保存許可。

Owner 暫時接受方案 C「分層資格」：邏輯上分別檢查來源／會話允許、語意價值與目的符合、受信任政策允許，通過後才進 validation／consolidation／publish。這是跨家證據形成的整合方案，不宣稱任何一家公開採取完全相同的內部管線，也不要求多次模型呼叫、多個 agent 或特定資料表。OpenAI／Anthropic 的 usefulness／sensitive classifier、模型與規則分工仍未公開，文件已明確列為未知。

### 2026-08-30：整體審核 F7～F9 已完成研究

F7 以 Anthropic、Google、AWS、OpenAI Codex 與 PydanticAI 官方資料收斂 Memory trust boundary：Memory 是可錯、可污染的低信任資料，不是 policy 或授權來源；source/scope/access 由 trusted runtime 控制；寫入與召回兩端都需防 poisoning，並以 least privilege、sandbox／確認、監控與 red-team 分層保護。

F8 比較 exact/filter、semantic、keyword、hybrid、graph 與 rerank。共同基線不是某一個檢索引擎，而是 scope-first、有界自動 recall、已知目標先 exact lookup、模型可按需 search/read，且 retrieval score 不冒充真實性。Hybrid 是明顯趨勢但仍屬選項；graph／rerank 只在資料與 query 證明有價值時使用。

F9 比較 Codex、Google、AWS、CrewAI 與 Mem0 的 hot-path／background、PENDING／published、barrier、retry 與成本行為。研究結論是以正確性期限決定 hot path，其餘背景化；空結果與 deterministic update 合法；每次 recall、模型、embedding、rerank 與 retry 都有界並可觀察。

### 2026-08-31：公開資料表徵、Memory Prompt 與 Memory Tool 深潛

Owner 要求暫時不做 Caliburn mapping，先查清楚 OpenAI、Anthropic 與其他大廠實際公開的資料形狀、Prompt、Tool 和管理責任。本輪因此新增 §13，並修正先前把部分 OpenAI 行為籠統列為未知的寫法：

1. OpenAI 已公開開源 Codex 的兩階段 Memory pipeline、Phase 1／consolidation／read prompts，以及 `memory_summary.md`、`MEMORY.md`、raw／rollout detail 的分層表徵；OpenAI Agents SDK 也已提供 Beta Sandbox Memory。這些是可直接閱讀原始碼與官方文件的公開事實，不再以推測描述。
2. ChatGPT Dreaming 的背景跨聊天綜合與可檢視 summary 已公開，但私有 record schema、Prompt、ranking、embedding、衝突演算法與觸發門檻仍未知；不得用 Codex 的公開實作補完 ChatGPT 私有細節。
3. Anthropic API Memory Tool 公開 file-style CRUD contract；Managed Agents Memory 公開 path-addressed text documents、immutable versions、OCC 與 access mode。Claude 消費型 Memory 的 topic schema／Prompt／ranking 仍未公開，三者不得混為同一底層。
4. Google 以 exact scope 下的 self-contained facts、topics、few-shots 與 revisions 管理；AWS 以 strategy-specific extraction／consolidation Prompt 與 Add／Update／Skip schema 管理；Microsoft 公開 `MemoryItem` 與 `memory_search_preview`，但未公開 extraction Prompt。
5. LangGraph Store 只是 namespace／key／JSON primitive；LangMem 才加上 `manage_memory`／`search_memory` tools、manager Prompt 與可自訂 schema。接上 Store 不等於已得到成熟 Memory 語意。
6. 跨家最重要的責任邊界是：資料表徵、Memory Prompt、Memory Tool、召回策略與 trusted runtime metadata 是不同層。模型負責受控的語意內容與有限 mutation intent；scope、principal、ID、version、timestamp、ACL、TTL、lease 等由 runtime／storage 產生與驗證。

本輪只更新市場事實與共同責任，不選 `MEMORY.md`、atomic fact、profile、topic、LangMem 或任何 Caliburn 正式資料結構。

### 本輪通用研究狀態

- 暫時確認：D1～D7，以及 §7A 的 F1～F6；
- 研究收斂：§6.1 B1～B7 為跨家必要核心，§6.2 B8～B14 為 production 治理基線；共同出現是強工程證據，不是數學證明；
- 研究收斂：F7 trust boundary、F8 retrieval、F9 cost／operations 已補齊完整通用方案；
- 尚未做：任何特定產品 mapping、框架選擇、schema、API、資料庫、UI 或施工計畫。

## 11. 通用研究完成邊界與後續順序

本輪通用研究已完成第一輪封口。後續若要進入特定產品，順序應為：

1. 先由 Owner 一次閱讀 §6、§7 與 §9，確認或翻案通用基線；
2. 再另外建立產品目標與需求 mapping，逐項標示「直接採用／簡化／不採用／需新增證據」；
3. 才比較框架對必要基線的覆蓋率、實際效果、成熟度、成本與替換風險；
4. 最後才寫 ADR、資料結構、API 與施工計畫。

不得倒過來因某個框架方便，就刪掉已確認的必要行為；也不得因本研究列出某項成熟能力，就在沒有產品需求時全部照搬。

## 12. 來源成熟度速查

| 來源 | 截至 2026-08-31 的用途 | 使用限制 |
| --- | --- | --- |
| ChatGPT Memory／Dreaming V3 | 已出貨跨聊天 Memory；官方公開背景綜合、可檢視 summary 與 freshness／relevance 目標 | 與本機 Codex 是不同 store／controls；私有 Prompt／record schema／ranking 未公開 |
| Codex Memories | 已出貨且開源兩階段抽取／consolidation、Prompt templates、分層檔案表徵與 progressive disclosure | coding-agent 專用形狀；背景 recall，不是強一致 authority |
| OpenAI Agents SDK Sandbox Memory | 開發者可用的兩階段檔案型 Memory、progressive disclosure 與 `extra_prompt` | Beta；domain schema／selection policy 仍由應用提供 |
| Claude Memory／chat search | 已出貨分類 Memory＋來源聊天搜尋 | 私有內部排序／儲存未公開 |
| Claude Code／Memory Tool | 已出貨 bounded index／JIT read／CRUD primitive | coding-agent 形狀不可直接視為所有產品最佳 UX |
| Anthropic Managed Agents Memory／Dreams | Memory store、immutable versions、OCC；Dreams 可做獨立背景 consolidation | Managed Agents 為 Beta／Dreams 為 Research Preview；不得當穩定通用依賴 |
| Google Memory Bank | extraction＋consolidation＋revision／rollback 的完整 managed 流程 | 公開 REST 為 `v1beta1`，平台仍快速演進 |
| AWS AgentCore Memory | 大廠 raw events＋長期抽取策略＋非同步 ingestion | Managed service 的 built-in schema／費用與自訂需求需分開評估 |
| Microsoft Foundry Memory | `MemoryItem`、`memory_search_preview`、direct remember／forget、debounced update 與 item CRUD | Preview、無 SLA；內部 extraction Prompt／ranking 未公開 |
| LangGraph | 穩定的 state／Store／memory 概念與 primitive | 不定義產品 Memory 語意 |
| LangMem | 直接提供 semantic memory reconcile | 0.0.x、GitHub 無正式 release，成熟度需另驗證 |
| PydanticAI Harness | 完整 notebook＋conversation search 參考 | 0.x，minor API 可變 |
| CrewAI 1.15.18 | Unified Memory、scope、recall、consolidation、read barrier | 高自動化增加模型／embedding 成本；預設 task-oriented |
| AutoGen | 成熟可替換 Memory protocol | 不是完整寫入與治理政策 |
| LlamaIndex | 現行短期＋長期 blocks | 部分 block 會摘要，細節保真另判斷 |
| Letta MemFS | 現行 Git-backed files、bounded system context、按需 read、版本歷史 | 預設無 semantic/vector；舊 core/archival/shared block 基線已過時 |
| Mem0 V3 | single-pass async add、hybrid retrieval、built-in graph boost | 官方頁面對 mutation semantics 有矛盾；必須鎖版本與 runtime 驗證 |
| Zep／Graphiti | temporal graph 與歷史失效 | 能力強但複雜度最高 |

## 13. 2026-08-31 深潛：公開資料表徵、Memory Prompt 與 Memory Tool

### 13.1 本節研究目的與邊界

本節依 Owner 指示調整順序：**先看各家實際公開的 Memory 資料、Prompt、Tool 與管理流程，再討論任何產品需求或 schema。** 它回答：

1. 原始資料與衍生 Memory 各長什麼樣？
2. 模型實際被要求填哪些內容？
3. Memory Prompt 決定什麼？
4. Memory Tool 提供哪些操作？
5. ID、scope、版本、時間與權限由誰產生？
6. 哪些內容是官方已公開，哪些仍是私有未知？

本節不做 Caliburn mapping、不選框架、不設計工作理解 schema，也不因現行程式已有某元件就替它找對應答案。

### 13.2 先把容易混淆的五層拆開

| 層 | 作用 | 典型例子 | 不負責什麼 |
| --- | --- | --- | --- |
| Source stream | 保存實際發生的訊息、事件、tool calls／results | OpenAI Conversation items、Codex rollout JSONL、Google events、AWS short-term events | 不自動等於已整理的長期 Memory |
| Memory representation | 保存可跨工作重用的衍生內容 | Markdown files、standalone fact、Pydantic／JSON record、topic | 不自動決定何時寫、何時召回 |
| Memory Prompt／policy | 告訴模型什麼值得保存、如何去重／更新／淘汰 | Codex Phase 1／2 Prompt、Anthropic system guidance、Google topics＋few-shots、AWS strategy prompts | 不負責真正持久化或授權 |
| Memory Tool／API | 提供 read／search／create／update／delete 等操作 | Anthropic Memory Tool、Microsoft `memory_search_preview`、LangMem manage/search tools | 不替產品定義 domain truth |
| Trusted runtime metadata | 控制身分、scope、ID、時間、版本、權限、重試與發布狀態 | namespace、memory ID、revision、lease、TTL、OCC | 不應交給模型自行捏造 |

研究結論是：各家資料形狀不一致，但成熟方案幾乎都把這五層分開；不能把「有 Memory Tool」誤解為「框架已替產品設計好 Memory 內容」。

### 13.3 OpenAI

#### 13.3.1 ChatGPT Dreaming：公開高階流程，不公開 record contract

OpenAI 2026 官方文章公開了以下產品行為：

- saved memories 之外，Dreaming 會在背景參考多段 chat history；
- 背景流程綜合出持續更新的 Memory state，目標是 freshness、continuity 與 relevance；
- 使用者看到的是可檢視與調整的 Memory summary；
- 官方評估重點是跨聊天帶回有用 Context、遵守偏好／限制，以及隨時間保持最新。

仍未公開：底層 memory record 欄位、Dreaming Prompt、tool schema、embedding／ranking、合併衝突演算法、觸發門檻。Memory summary 是 UI／context 入口，不足以證明底層只有一份 summary。

- [OpenAI — Dreaming: Better memory for a more helpful ChatGPT](https://openai.com/index/chatgpt-memory-dreaming/)
- [OpenAI — Memory and new controls for ChatGPT](https://openai.com/index/memory-and-new-controls-for-chatgpt/)

#### 13.3.2 開源 Codex：目前公開最完整的 OpenAI Memory 實作

Codex 把資料分成至少四層：

| 層 | 公開表徵 | 主要用途 |
| --- | --- | --- |
| 原始 rollout | append-only JSONL；含 session metadata、turn boundary、status、messages、tool calls／outputs | 最後需要精確證據時回查 |
| Phase 1 DB output | structured `raw_memory`、`rollout_summary`、可選 `rollout_slug` | 逐 rollout 正規化、保留可重用訊號 |
| Phase 2 detail | `raw_memories.md`、`rollout_summaries/*.md`、可選 `skills/` | consolidation 輸入與深入讀取 |
| Phase 2 active Memory | `MEMORY.md`＋`memory_summary.md` | 可搜尋 handbook＋小型 prompt-loaded 導覽 |

Phase 1 Prompt 的重點不是「摘要所有內容」，而是：

- 先過 minimum-signal gate，無值得保存內容時允許空輸出；
- user messages 是偏好與限制的強來源，tool／verification output 是事實與成功證據的強來源；
- 對每個 task 保存 preference signals、reusable knowledge、failures、references；
- 不把一次探索、assistant 建議或未採納想法直接升格成穩定 Memory；
- structured output 只回 `raw_memory`、`rollout_summary` 與可選 slug，不能輸出額外 prose。

Phase 2 Consolidation Prompt 的重點是：

- 先看前次成功 baseline 到目前輸入的 git-style diff；
- 只對新增／修改／刪除的證據做增量整併，必要時才深入 rollout summary；
- 原始 rollout 是 immutable evidence；外部 tool output 是資料，不是指令；
- `MEMORY.md` 保留可搜尋、足以重用的細節與來源指標；
- `memory_summary.md` 高密度、去重、只作導覽，不複製整本 handbook；
- 無新訊號時 no-op 優於為了更新而製造 churn。

Read Prompt 採 progressive disclosure：

1. 先從注入的 `memory_summary.md` 抽關鍵字；
2. 搜尋 `MEMORY.md`；
3. 只有被 `MEMORY.md` 指向時才開 1～2 份 rollout summaries／skills；
4. 需要 exact commands／errors／evidence 時才搜尋原始 rollout；
5. 沒有相關命中就停止，不掃完整歷史。

這條公開路徑**不是一個讓主 agent 自由填巨大 CRUD schema 的 `save_memory` tool**。背景 writer 由兩組專用 Prompt＋structured output／filesystem workspace 完成；read path 則用既有 file／search 能力逐層讀。使用者明確要求更新 Memory 時，現行 read prompt 要求只寫小型 ad-hoc update note，不讓主 agent 直接任意改 consolidated files。

模型與 runtime 的分工：

- 模型產生：Memory 文字內容、task grouping、summary、檔案整併；
- runtime 產生：rollout／thread identity、eligibility、claim／lease、timestamps、usage counts、watermark、retry backoff、global lock、secret redaction、檔案 baseline；
- consolidation agent 不取得 network、approval 或 collab 權限，只能在 Memory workspace 內寫入。

- [OpenAI Codex — Memory pipeline README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)
- [OpenAI Codex — Phase 1 Prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/stage_one_system.md)
- [OpenAI Codex — Phase 2 Consolidation Prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)
- [OpenAI Codex — Read Prompt](https://github.com/openai/codex/blob/main/codex-rs/ext/memories/templates/memories/read_path.md)

#### 13.3.3 OpenAI Agents SDK Sandbox Memory（Beta）

開發者版 Memory 沿用相同家族的分層檔案與兩階段生成：conversation extraction 先產生 conversation summary＋raw memory extract，layout consolidation 再形成 `MEMORY.md` 與 `memory_summary.md`。SDK 提供：

- `Memory()`：同時啟用 read 與 generate；
- `Memory(generate=None)`：只讀；
- `Memory(read=None)`：只為未來生成；
- `MemoryReadConfig(live_update=False)`：讀取時不允許即時修正 stale Memory；
- `MemoryGenerateConfig(extra_prompt=...)`：追加少量 domain-specific 記憶指引；
- `MemoryLayoutConfig`：隔離不同 agent／用途的 Memory layout。

這裡的 `extra_prompt` 是「產品告訴 Memory generator 哪些訊號重要」的正式擴充點。官方範例明確建議保持短小、聚焦，不要用它重寫整份內建 Memory Prompt。

- [OpenAI Agents SDK — Agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [OpenAI Agents SDK — Memory example](https://github.com/openai/openai-agents-python/blob/main/examples/sandbox/memory.py)

#### 13.3.4 OpenAI API primitive 的邊界

Responses／Conversations 保存 ordered items（messages、tool calls、tool outputs）；compaction 產生 opaque continuation item；Vector Store Search 回傳相關 chunks、score 與 file metadata。三者分別解決 conversation continuity、Context 壓縮與資料檢索，**沒有一個等於通用 semantic Memory manager**。如果不使用 Sandbox Memory，應用仍需自己定義 Memory Prompt、record schema、CRUD／reconcile 與 retrieval policy。

- [OpenAI API — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI API — Compaction](https://developers.openai.com/api/reference/java/resources/responses/methods/compact)
- [OpenAI API — Vector Store Search](https://developers.openai.com/api/reference/typescript/resources/vector_stores/methods/search)

### 13.4 Anthropic

#### 13.4.1 Claude 消費型 Memory

Claude 消費型產品公開「分類 topics＋獨立 past-chat search＋使用者可 change／forget」的行為，但沒有公開 topic record schema、Memory Prompt、ranking 或儲存引擎。不能用 API Memory Tool 的檔案 contract 反推消費型 Claude 一定使用相同底層。

#### 13.4.2 API Memory Tool：file/document 表徵＋模型主動 CRUD

Memory Tool 的資料是 `/memories` 下的檔案與目錄；應用把虛擬 path 映射到自己的 filesystem／object store／database。Anthropic 公開的 command contract 為：

| command | 模型主要填入 | 應用主要處理 |
| --- | --- | --- |
| `view` | path、可選 line range | 列目錄／讀檔、分頁、大小、找不到錯誤 |
| `create` | path、file text | 建檔、已存在策略、path sandbox |
| `str_replace` | path、唯一 old text、new text | 精確替換；找不到／多重命中回 typed error |
| `insert` | path、line、text | 範圍檢查、插入結果 |
| `delete` | path | 刪檔／目錄；禁止刪 Memory root |
| `rename` | old path、new path | rename／move；目的已存在時拒絕 |

啟用 Tool 時，平台會自動加 Memory protocol：工作前先看 Memory 目錄；工作中記錄需跨 Context 保存的進度；假設 Context 可能隨時中斷。這是**通用行為 Prompt**，不是 domain schema。官方另建議應用用簡短 Prompt 指定只保存某主題，並在產品層做更嚴格 validation／敏感資料過濾。

官方 SDK 範例的額外 system Prompt 示範：不要只是存 transcript、保存 user facts／preferences、回答前先查 Memory、遇到新資訊時更新並移除過時內容。這是可參考的官方範例，不是每個 Memory Tool request 都自動附帶的固定文字。

- [Anthropic — Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic Python SDK — Memory example](https://github.com/anthropics/anthropic-sdk-python/blob/main/examples/memory/basic.py)

#### 13.4.3 Managed Agents Memory：文字文件＋平台版本治理

Managed Agents 把 workspace-scoped Memory Store 掛載成 session sandbox 中的目錄：

- 每筆 Memory 由 path 尋址，是可直接 API read／edit 的 text document；
- store 的 name／description／instructions 會進 agent system context，告訴模型在哪裡找、用途是什麼；
- session attachment 指定 read-only／read-write；
- 每次 mutation 產生 immutable version，可稽核與 point-in-time recovery；
- 平台管理 ID、version、content hash、created time、workspace scope 與 optimistic concurrency。

文件建議採多個小型、聚焦文件，不要少數巨大文件；這是針對 file-based agent retrieval 的設計建議，不是所有 semantic Memory 必須照抄的唯一 schema。Managed Agents Memory 目前仍是 Beta。

- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Platform release notes](https://platform.claude.com/docs/en/release-notes/overview)

### 13.5 Google Memory Bank

Google 的主要長期表徵是 scope 下的 self-contained `fact`。公開 response 顯示：

- active `Memory` 有 resource name 與 `fact`；
- scope 建立後 immutable，只有 exact same scope 的 Memory 會互相 consolidation／retrieval；
- `MemoryRevision` 保存每次更新前後的 `fact`，可加 source labels、rollback，亦可設定 TTL；
- generation response 明列 `CREATED`／`UPDATED` 等 action；刪除會留下空 fact 的 deletion revision；
- intermediate extracted memories 也以 `fact` 表示，但不等於每個候選都會發布為 active Memory。

Google 沒要求應用直接撰寫完整底層 extraction system Prompt，而是提供兩個正式控制面：

1. **Memory topics**：用 managed topic 或自訂 label＋instructions 說明什麼資訊才值得持久化；不符合任何 topic 的內容不保存。
2. **Few-shot examples**：用 conversation→expected memories 示範抽取粒度、措辭與負例；負例以空 `generated_memories` 表示。官方建議自訂 topics 一律搭配 few-shots。

管理 API 分成：Generate／IngestEvents、直接提供 pre-extracted facts、Create／Get／List／Update／Delete、Retrieve exact-scope all memories 或 similarity top-k，以及 Revision inspect／rollback。`GenerateMemories` 是 long-running operation；目前 run 不需要結果時，官方建議 production 背景執行。

- [Google — Set up Memory Bank（topics、few-shots、perspective、consolidation）](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup)
- [Google — Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google — Fetch memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [Google — Memory revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)

### 13.6 AWS Bedrock AgentCore Memory

AWS 把 source 與 long-term record 明確分開：short-term Memory 保存 session events；Memory strategies 再把事件抽取／整併成 namespace 下的 long-term memory records。不同 strategy 有不同 schema，沒有單一通用 Memory JSON。

官方公開 Prompt 的層次非常清楚：

| 階段 | Prompt 責任 | 公開 structured output 例子 |
| --- | --- | --- |
| Extraction | 從 past／current conversation 與 event payload 選出值得長期保留的內容 | semantic strategy：`language`＋standalone `fact` |
| Consolidation | 將候選與 existing memories 比對，避免重複並處理更新 | `AddMemory`、`UpdateMemory(update_id, updated_memory)`、`SkipMemory` |
| Reflection（部分 strategy） | 從 episodes 產生跨事件洞察 | strategy-specific reflection schema |

Semantic Prompt 要求 standalone、保留數字／位置／日期、減少代詞歧義；Consolidation Prompt 要求保留既有細節、只在 closely relevant 時更新、壓縮重複以提高 signal-to-noise。User Preference strategy 則使用 context／preference／categories 等不同欄位，證明 schema 應隨 Memory purpose 改變。

應用可選 built-in、built-in overrides 或 self-managed strategy：override 可調 Prompt／model；self-managed 可自訂 extraction／consolidation、schema、namespace 與批次 CRUD。AWS 服務負責 record ID、namespace、job／ingestion status 與 API；模型不應填安全 scope。

- [AWS — Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [AWS — Built-in strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-strategies.html)
- [AWS — Semantic Memory system Prompt](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [AWS — User Preference Memory system Prompt](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-user-prompt.html)
- [AWS — Memory terminology](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-terminology.html)

### 13.7 Microsoft Foundry Memory（Preview）

Microsoft 最新 Preview 的公開 item 形狀為 `MemoryItem(memory_id, content, kind, scope)`；示例 `kind` 是 `user_profile`。應用可以逐 item create／get／list／update／delete，也能提交 conversation items 給 update operation，取得 operation kind、memory ID 與新 content。

模型側提供 `memory_search_preview` tool：

- agent 可在 conversation 中讀取與寫入 store；
- runtime 配置 store name、scope 與 inactivity `update_delay`；
- 使用者明確要求 remember／forget 時，tool 可立即產生 memory command items；
- 一般更新可 debounce 後背景處理；
- search response 回 `memories` collection；scope 必須一致。

Microsoft 公開了 Tool 與 item contract，但沒有公開底層 extraction／consolidation Prompt 或 ranking；不能把 managed service 自動更新反推成已知演算法。

- [Microsoft Foundry — Create and use memory](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/memory-usage)

### 13.8 LangGraph／LangMem

LangGraph Store 的持久化 primitive 是：

```text
namespace: tuple[str, ...]
key: string
value: JSON document
可選：embedding index／filter／semantic search
```

它不規定 value 應該是 profile、fact、topic 或文件。LangMem 在這個 primitive 上提供：

#### Hot-path tools

```text
manage_memory(content?, id?, action=create|update|delete)
search_memory(query)
```

預設 tool instructions 建議在新 user preference、明確 remember／行為更正、重要工作 Context、發現舊 Memory 錯誤／過時時呼叫。Namespace template 由 runtime config 展開；模型不必也不應填真正 user／project scope。

#### Background manager

`create_memory_manager` 接收 messages、可選 existing memories、max steps；預設 unstructured schema 是 standalone `Memory(content: str)`，也可由應用傳 Pydantic models。預設 Prompt 要求保存 surprising／persistent 訊號、避免 false Memory、偏好 dense complete over overlapping。Manager 可開關 insert／update／delete。

`create_memory_store_manager` 可先搜尋相關 memories、再 extraction／consolidation／enrichment，並把結果寫入 Store。應用仍要提供 domain instructions／schema；LangMem 不會僅因接上 store 就知道某領域的完整性、關聯或 truth policy。

- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [LangMem — Memory Tool API](https://langchain-ai.github.io/langmem/reference/tools/)
- [LangMem — Memory manager source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)

### 13.9 正規化對照：各家實際怎麼分

| 來源 | 主要 Memory 表徵 | Memory Prompt／policy | Model-facing Memory Tool | 系統管理內容 |
| --- | --- | --- | --- | --- |
| ChatGPT Dreaming | 私有；UI 有 Memory summary | 私有，只公開高階目標 | 私有／未公開 | 背景綜合與使用者控制 |
| OpenAI Codex | DB stage-1 records＋Markdown summary／handbook／details／skills | 公開 Phase 1、Phase 2、read prompts | 非單一 semantic CRUD tool；structured output＋受限 filesystem／search | eligibility、lease、usage、lock、watermark、redaction、retry |
| OpenAI Agents SDK | JSONL sources＋分層 Markdown files | 內建兩階段 Prompt＋可選 `extra_prompt` | Memory capability 組合 file／shell abilities | layout、read／generate／live-update 開關 |
| Claude consumer | 私有分類 topics | 私有 | 使用者自然語言 change／forget | topic UI、chat search／citations |
| Anthropic Memory Tool | 任意文字檔／目錄 | 自動 Memory protocol＋應用 system prompt | `view/create/str_replace/insert/delete/rename` | 應用 storage／scope／validation |
| Anthropic Managed Agents | path-addressed text documents | store instructions＋agent prompt | 一般 file tools | store、versions、OCC、hash、access mode |
| Google Memory Bank | exact-scope standalone `fact`＋revisions | topics＋instructions＋few-shots | 主要是 managed API／SDK，不要求 agent 自由 CRUD | ID、scope、LRO、action、revision、TTL、IAM |
| AWS AgentCore | namespace records；schema 隨 strategy | 公開 extraction／consolidation／reflection prompts | managed pipeline API；self-managed 可自訂 | record ID、namespace、ingestion jobs、IAM |
| Microsoft Foundry | `MemoryItem(id, content, kind, scope)` | 內部 Prompt 未公開 | `memory_search_preview`＋direct remember／forget | store、scope、TTL、debounce、operation status |
| LangMem | JSON／Pydantic profile 或 collection | 可覆寫 manager／tool instructions | `manage_memory`＋`search_memory` | runtime namespace、Store key、search index |

### 13.10 跨家共同責任分配

| 資訊 | 應由誰產生 | 理由 |
| --- | --- | --- |
| 要保存的語意內容 | 模型依受控 Prompt／topic／schema 產生 | 需要語意判斷與整併 |
| create／update／delete／skip 意圖 | 模型或 managed Memory pipeline | 需要判斷新舊內容關係；但必須 schema-bounded |
| 要搜尋什麼 | runtime 預檢＋模型按需 query，可混合 | 自動召回處理 unknown-unknown，tool search 補細節 |
| principal、scope、namespace | trusted runtime | 屬安全與資料隔離邊界，不是模型語意 |
| record ID、revision、timestamp、version | trusted runtime／storage | 避免模型捏造或衝突 |
| source identity／event ID | source runtime | 必須對應真實輸入，模型只能引用不能創造 |
| 權限、TTL、retention、redaction policy | application／platform | 屬治理，不得由 Memory 內容自我授權 |
| tool execution error | tool／storage 回 typed error | 讓模型有界修正，不能靠模型猜成功 |

### 13.11 本輪能成立的共同結論

1. **沒有跨家的單一最佳 record schema。** OpenAI／Anthropic coding Memory 偏分層文件；Google／AWS／Microsoft 偏自包含 records；LangMem 兩者都能承載。
2. **Memory Prompt 與 Tool 必須分開。** Prompt 定義 selection／consolidation 語意；Tool 只給有限操作。只接 CRUD tool 不會自動得到好 Memory。
3. **通用 Prompt 必須留 domain extension seam。** OpenAI `extra_prompt`、Anthropic app prompt、Google custom topics＋few-shots、AWS override、自訂 LangMem instructions 都明確保留產品定義空間。
4. **原始 conversation／events 與衍生 Memory 分層。** OpenAI Codex、Google、AWS 都直接公開此結構；Anthropic 也把 Memory files 與 session／past-chat search 分開。
5. **小型入口＋按需深入是強共識。** OpenAI Codex／Agents SDK、Claude Code／Memory Tool 都採 summary／directory 先行，再 read／search 詳細檔；Google／AWS 則以 scope＋bounded retrieval 達成同目的。
6. **模型不填安全與系統欄位。** Scope、principal、ID、version、timestamp、ACL、TTL、lease 等由 runtime 管理；模型主要填語意內容與有限 mutation intent。
7. **空結果／no-op 是正常結果。** Codex 有 `succeeded_no_output`，Google few-shot 可示範空 memories，AWS 有 `SkipMemory`，LangMem manager 可回空或不變。
8. **更新不是單純 append。** Google／AWS／Microsoft／LangMem 支援 update／delete／skip；Codex／Anthropic file pipelines 透過 diff／replace／delete 維持 active Memory。
9. **表徵、召回與 governance 是不同選擇。** 選 Markdown、fact 或 Pydantic schema，並不自動決定 vector／keyword recall、revision、權限或一致性。

### 13.12 不能從公開資料推論的內容

1. ChatGPT Dreaming 與 Claude consumer Memory 的私有 record schema、Prompt、ranking、embedding、衝突規則；
2. OpenAI Codex 的 coding-specific task／cwd／failure schema 是否適合其他 domain；
3. Anthropic Memory Tool 的 file representation 是否優於所有 structured records；
4. Google／Microsoft managed extraction 的完整 system Prompt 與內部模型；
5. 各家相似概念是否共用底層實作；
6. 只因某家出貨某能力，就推論它是所有產品必需或效果一定最佳。

### 13.13 下一步研究順序

這次深潛完成後，下一步才是：

1. **已完成第一輪：**[`2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md` §5](2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md) 已從高品質 JD 倒推出 M1～M11，並切開 Memory 與 LLM／Skill／Tool／authority 的責任；
2. **已完成第二輪：**[`2026-08-30-caliburn-memory-requirements-mapping-working-research.md` §9](2026-08-30-caliburn-memory-requirements-mapping-working-research.md) 已逐項 mapping M1～M11 到共同 primitive 與成熟差異能力；
3. **已完成第三輪：**[`2026-08-30-caliburn-memory-requirements-mapping-working-research.md` §9.9～§9.14](2026-08-30-caliburn-memory-requirements-mapping-working-research.md) 已比較 retention／admission 差異方案，將來源資格、語意 admission、持久化政策與其後 consolidation 切開；目前只暫定責任分界，未選框架或 Prompt；
4. **已完成第四輪：**[`2026-08-30-caliburn-memory-requirements-mapping-working-research.md` §9.15～§9.21](2026-08-30-caliburn-memory-requirements-mapping-working-research.md) 已重新核對 D4 並完成 M5 mapping：成熟 lifecycle／revision 可承接基礎能力，但 managed default 不能自動冒充產品 truth policy；目前推薦用成熟 extension seam 承載 unknown／unresolved conflict 語意，尚待 Owner 確認；
5. **已完成第五輪：**關係表徵、完整盤點與案例／穩定工作界線的產品 mapping 已集中記錄於 [`2026-08-30-caliburn-memory-requirements-mapping-working-research.md` §9.22～§9.25](2026-08-30-caliburn-memory-requirements-mapping-working-research.md)，本文新增 §13.14～§13.15 保存本輪通用事實；
6. **已完成第一輪完整候選比較：**框架、Prompt／Tool、Context、成本與最低驗證的暫定產品建議記錄於 mapping 文檔 §9.26～§9.31；仍須 Owner 核准後才可進 ADR／plan。

本節沒有替 Caliburn 選擇 `MEMORY.md`、atomic fact、profile、topic、LangMem 或任何 schema。

### 13.14 關係表徵、完整列舉與 episodic 的新增通用事實

#### 13.14.1 關係表徵沒有跨家唯一標準

目前公開做法至少分成三類：

1. OpenAI Sandbox Memory／Anthropic Managed Agents 使用分層文字文件，依 summary／directory 先行、需要時 read 詳細文件；Anthropic 建議多個小而聚焦的文件，不建議少數巨大文件。
2. Google／AWS 使用自包含 records／facts；LangGraph Store 的 value 是任意 JSON；LangMem 允許 Pydantic schema，官方亦用 `subject/predicate/object/context` triple 示範關係記憶。
3. Graphiti 使用 temporal context graph，以 episode、entity、relationship 與 valid-time 表達會變動的關係，並提供 hybrid／graph retrieval。

上述事實只證明成熟生態可承載 rich document、structured record 與 graph；不能推論任何有關係的 domain 都必須採 graph，也不能推論 atomic fact 能自動保留跨項脈絡。

#### 13.14.2 List-all 與 semantic search 是不同 API 行為

- Anthropic `List memories`：recursive path listing、stable server-defined order、opaque cursor；一般 view 每頁最多 100，full-content view 最多 20。
- Google Memory Bank：不帶 similarity 的 exact-scope retrieve 可取得 scope 內全部 Memory，每頁最多 100；SDK pager 可走完所有頁。帶 similarity 時才是 top-k。
- AWS `ListMemoryRecords`：namespace／namespacePath、每頁 1～100、`nextToken`；與 semantic retrieval 分開。
- LangGraph Store：`search(namespace, query=None, filter=None)` 是 listing mode，使用 `limit/offset`；超出 limit 會截斷，backend order 也不可跨 implementation 假設一致。

公開文件沒有共同承諾 list pagination 在 concurrent mutation 下具有 snapshot isolation。Stable order、cursor、next token 與 offset 能支持遍歷，但若產品要求「某一 revision 的完整 inventory」，仍需 substrate transaction／snapshot 或 application 在遍歷期間固定 revision。

#### 13.14.3 AWS episodic 不等於所有 domain 的案例記憶

AWS episodic strategy 會偵測 agent interaction episode 完成，整理 situation、intent、actions／turns、assessment、justification、outcome 與 reflection，再從多個 episode 形成跨事件洞察。它適合 agent task trajectory、工具使用與成功／失敗模式；不能只因產品有「員工案例」就推論應直接使用 episodic strategy。各 domain 仍需定義 case 的語意與何時一般化。

### 13.15 方案成熟度的新增通用事實（截至 2026-08-31）

| 方案 | 目前公開成熟度事實 | 不應過度宣稱 |
| --- | --- | --- |
| LangGraph | 1.0 為 LTS，2.0 前維持 ACTIVE，之後至少一年 MAINTENANCE；Postgres／Mongo／Redis 等 persistent stores 已公開 | LTS 不代表 domain Memory Prompt 已自動正確 |
| LangMem | 公開 hot-path tools、background manager、custom schema 與 LangGraph Store integration；PyPI 最新穩定版仍為 0.0.30（2025-10-27） | 文件存在不等於與最新 LangGraph 1.x 全組合已有 LTS 保證 |
| AWS AgentCore | 2025 起 GA，2026 持續增加 metadata filtering、Harness 與 observability；Memory 按 raw events、records、retrieval 與模型使用計費 | GA managed service 不等於 built-in semantic policy 適合所有 domain |
| Google Memory Bank | Agent Platform 在支援地區以 `v1` 承載 GA features、以 `v1beta1` 承載 Preview features；截至本次研究，Memory profiles 與 `IngestEvents` 已明確公告 GA，topics、few-shots、scope retrieval、revision 等能力有現行官方文件；Memory Bank 自 2026-09-01 起依 storage／operations／model tokens 計費 | 不應把「部分能力已 GA」擴張成每個 Memory Bank feature 都有相同成熟度；standalone facts 也不自動等於 rich relational Memory |
| Anthropic Managed Agents Memory | path documents、list cursor、versions、OCC、recovery 已公開；服務仍為 beta，另有 token＋session runtime 費用 | 不能當成 provider-neutral、穩定 GA contract |
| Graphiti | 0.x 仍活躍發版，temporal graph／hybrid retrieval／custom entity edges 已公開 | 活躍 0.x 不等於應預設承擔每個產品的 Memory |

主要新增來源：

- [OpenAI Agents SDK — Agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic API — List memories](https://platform.claude.com/docs/en/api/http/beta/memory_stores/memories/list)
- [Google — Fetch memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [Google — Agent Platform release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
- [Google — Agent Platform supported locations／API versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/agent-locations)
- [AWS API — ListMemoryRecords](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListMemoryRecords.html)
- [AWS — Episodic memory strategy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/episodic-memory-strategy.html)
- [LangChain — LangGraph Store／Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangChain — Release policy](https://docs.langchain.com/oss/python/release-policy)
- [LangMem — Extract semantic memories](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
- [PyPI — LangMem](https://pypi.org/project/langmem/)
- [Graphiti — Overview](https://help.getzep.com/graphiti/getting-started/overview)
- [Graphiti — Releases](https://github.com/getzep/graphiti/releases)

### 13.16 來源事件、整理知識與下游文件不是跨家固定三層

#### 13.16.1 本輪問題

產品討論常把「具體案例 → 目前理解 → 正式文件」畫成三個盒子，但公開成熟方案真正出貨的是一組可組合 primitive，並沒有共同要求三者各自成為 store、schema 或 model stage。本節只記錄供應商／框架事實，不替 Caliburn 選表徵。

#### 13.16.2 各家公開表徵與管理方式

| 來源 | 原始互動／來源 | 整理後知識 | 是否另有 current profile／summary | 對下游正式文件的公開契約 |
| --- | --- | --- | --- | --- |
| OpenAI Responses／最新 model guidance | Conversation 保存有序 input／output items；長流程可做 opaque compaction | 官方 API 提供 conversation state、compaction、file search／custom tools，但沒有公開通用 Semantic Memory record schema | Compaction 保存任務延續資訊，但定位是 continuation，不是可檢查的 domain knowledge profile | **沒有**公開「來源／案例 → current understanding → 業務文件」的 schema 或 derivation contract；應由應用程式定義 |
| Anthropic Memory Tool／Managed Agents | Message history／session 與 Memory 分開；Memory Tool 由 application 執行 file CRUD | Claude 可按需建立、讀取、修改、刪除 path-addressed files；application 可指示只保存特定主題 | Managed Agents Memory 是多個小型聚焦文件，live retrieve 讀 latest head，每次 mutation 建 immutable version | **沒有**固定 case／understanding 類型，也不替應用決定如何生成正式文件 |
| Google Memory Bank | Conversation events／Sessions／`IngestEvents` 是 generation source | Natural-language memories 經 extraction＋consolidation，會 create／update／delete；同 scope 預設比較既有 Memories | Structured Memory Profiles 可與自然語言 memories 同時生成；schema 由開發者定義，retrieve 回最終 consolidated profile | **沒有**JD 類業務文件映射；topics、few-shot、schema 只控制什麼值得記與如何表示 |
| AWS AgentCore Memory | `CreateEvent` 保存 raw interaction／short-term memory | Semantic strategy 抽取 factual/contextual knowledge；strategy 決定 extraction／consolidation | 可同時掛 semantic、summary、preference、episodic 或 custom strategies；episodic 要在 episode 完成後才生成 | **沒有**把 domain case 自動映射成正式文件；built-in episodic 主要描述 agent interaction trajectory |
| LangGraph／LangMem | Thread messages／checkpoint 承接 conversation state | Store 保存 namespaced JSON；LangMem manager 以 conversation＋existing memories做 insert／update／delete | Semantic Memory 可採單一 profile 或 collection；官方明示 profile 變大後更新較易出錯，collection 通常 recall 較高 | schema、instructions 與任何 downstream document 都由 application 定義 |
| Zep／Graphiti | Episode 是 message／text／JSON 原始 ingestion event；Zep 可保存 verbatim episode | LLM 從 episode 抽取 entity／fact／relationship，並把 derived facts 連回 episode | Entity summary、thread summary、observations 等是額外 derived context；facts 可隨新資料失效 | 提供最明確的 source→derived provenance，但仍不包含 domain-specific 正式文件生成規則 |

#### 13.16.3 跨家能成立的共同點

1. **原始互動與整理後可用資訊通常不是同一責任。** OpenAI conversation／compaction、Anthropic session／Memory files、Google events／memories、AWS events／records、Zep episodes／facts 都至少在行為上切開 source continuity 與 curated context。
2. **整理後知識不是只能有一種粒度。** Anthropic 讓 agent 自行組織聚焦文件；Google 可同時產生 natural-language memories 與 structured profile；AWS 可組合多種 strategies；LangMem 明確提供 profile／collection；Graphiti 則保留 episode＋fact＋summary。
3. **「什麼值得保存」仍需要產品指令或 schema。** Anthropic 可由 Prompt 限定 topic；Google 使用 memory topics／few-shot；AWS 使用 strategy／override；LangMem 使用 instructions／schema。成熟 manager 不是把所有對話自動變成正確 domain knowledge 的黑盒。
4. **更新通常是 consolidation，不只 append。** Google、AWS、LangMem 會在既有內容上 add／update／delete／skip；Anthropic files 可 replace／delete 並保留版本；Graphiti 會讓舊 fact 失效。
5. **來源、整理知識與業務成品之間沒有共同的一對一關聯。** 目前沒有一家官方文件定義「每個 source event 必須成為一筆 Semantic Memory」「每筆 Semantic Memory 必須對應一個業務文件欄位」或「接受成品後必須把推導理由寫回成品」。

#### 13.16.4 各家差異與不能混用的概念

- AWS `episodic` 的 episode 是完整 agent interaction／trajectory，不能只因 domain 有「工作案例」就直接視為同一概念。
- Google structured profile 是 application-defined current view；它能與 natural-language memories 並存，但不是所有大量、持續成長知識都適合塞入單一 profile。
- LangMem profile／collection 是表徵選擇，不是「理解／案例」的固定對照表；同一 domain 可依查詢與更新特性選一種或混合。
- Zep／Graphiti 最接近「原始案例＋整理理解」的顯式兩層來源鏈，但代價是 graph、entity resolution、temporal extraction 與額外 LLM ingestion；不能因 provenance 完整就推論所有產品都需要它。
- OpenAI 與 Anthropic 的公開通用工具刻意讓 application／agent 組織 Memory；未公開的私有內部 schema 不能拿來補足本節空白。

#### 13.16.5 通用研究結論

跨家共同基線應表述為：

```text
durable source／conversation
        +
可持續整理、修訂與按需取回的知識面
        +
application-defined downstream reasoning／actions
```

它**不是**：

```text
每個案例一張表
        →
每個理解一張表
        →
每個正式文件欄位一條永久 link
```

是否需要把具體 domain case 獨立成 records，只能由下游效果證明：若 conversation＋current semantic representation 已能保留細節、修訂、相關召回與完整盤點，就沒有通用證據要求增加第三層；若這些效果失敗，才比較 collection、profile＋collection 或 episode／graph。

本節主要新增來源：

- [OpenAI Responses — conversation state 與 tools](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [OpenAI — Compaction](https://developers.openai.com/api/reference/java/resources/responses/methods/compact)
- [OpenAI — 最新 model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)
- [Anthropic — Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Google — Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google — Memory Profiles](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/profiles)
- [Google — Memory revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)
- [AWS — Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [AWS — Episodic memory strategy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/episodic-memory-strategy.html)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [LangMem — Extract semantic memories](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
- [Zep／Graphiti — How graph creation works](https://help.getzep.com/how-graph-creation-works)
- [Zep — Episodes](https://help.getzep.com/episodes)
