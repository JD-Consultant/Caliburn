# Memory 完整列舉、版本、來源與最小切片重驗

- 日期：2026-09-02
- 狀態：**Working Research；校正下游設計稿，不授權 production cutover**
- 研究時間點：2026-09-02；只採研究當日仍在線的官方文件與本 repo 實際版本
- 上位目的：[`2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md`](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)
- 框架無關契約：[`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md)

> **較新機制稽核（2026-09-02）**：[`Memory 實作機制與成熟框架共識稽核`](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md) 是目前判讀底層實作與框架 primitive 的入口。本文對官方 API 的查證仍有效，但 LangGraph offset inventory、serial writer、deterministic key 與 checkpoint worklist 都降為候選產品映射，不再構成已核准施工路徑。

> **後續能力校正（2026-09-02）**：把完整 Semantic Memory collection 放進 single-thread checkpoint 的候選已否決；最新方向見 [`Memory 實作機制與成熟框架共識稽核` §10](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md)。因此本文對 Store listing／CAS／lineage 的分析重新成為主要候選邊界，但仍只依實際 contract 缺口啟用，不能提前自建平台。

> **Exact-inventory 共識重驗（2026-09-02）**：OpenAI 公開 collection API、Anthropic Managed Agents Memory、Google Memory Bank 與 AWS AgentCore Memory 的共同公開形狀，是「有界 page＋伺服器 cursor／token＋明確 continuation／completion signal」；不是 offset，也不是猜一個大 `limit`。Anthropic 更明列 `view=full` 是 export／sync 的 bulk-read path。Caliburn 的完整盤點只用於 **JD 完成前的低頻全面檢查**；日常建立／修改 JD 仍只取本輪相關 Memory。因目前 LangGraph PostgreSQL Store 沒有上述 cursor contract，`cap＋1` 只能是 isolated spike 的 fail-closed fallback，不得冒充跨家共識或無界 production 解法。

## 0. 為什麼要重驗

前一輪已正確辨識幾個 production 風險：全量盤點不能用 semantic top-k 冒充、可重放副作用不能重複、模型不能填可信 metadata、並行寫入不能靜默覆蓋。然而後續文件又把數個**成熟但非跨家共同、也尚未被第一個切片證明必要**的機制一起升格成硬要求：

- 每筆 Memory 都有 immutable revision；
- 每次 update／remove 都做 CAS；
- 每次 operation 都有 receipt table；
- 每次全量盤點都建立持久 snapshot manifest；
- 每次 Memory mutation 都必須有語意來源 lineage，缺少就拒絕；
- 在任何真實模型驗證前先完成以上所有自訂 authority infrastructure。

本次重驗只回答四題：

1. 各家最新公開 Memory API 是否共同提供完整列舉？
2. 各家是否共同要求 immutable history、CAS 與 operation receipt？
3. 各家是否共同要求每筆衍生 Memory 有必填、可驗證的來源 lineage？
4. Caliburn 第一個 Memory 垂直切片最少要證明什麼，才不會把時間花在尚未出現的風險？

本文嚴格標示三種結論：

- **官方事實**：來源明文公開的介面或行為；
- **跨家共同方向**：至少多個獨立成熟系統反覆出現的效果，不宣稱內部實作相同；
- **Caliburn 推論／選擇**：針對本機、單一操作者、每份 JD 單一訪談範圍的最薄映射。

## 1. 最新官方事實

### 1.1 OpenAI／Codex

[Codex Memories](https://learn.chatgpt.com/docs/customization/memories) 在研究日公開下列行為：

- 從 eligible prior chats 擷取 useful context，並在背景更新，不保證每段聊天結束後立即完成；
- 本機 Memory 生成狀態包含 summaries、durable entries、recent inputs 與 supporting evidence；
- `generate_memories` 與 `use_memories` 分離，並可分別指定 extraction／consolidation model；
- 官方提醒這些是 generated state，不應把手動改檔當成主要控制面。

[OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) 則證明 `conversation`／`previous_response_id` 能延續對話，但舊 input tokens 仍計費；它不是 application Semantic Memory 的版本、CAS 或 inventory API。

[OpenAI List container files](https://developers.openai.com/api/reference/cli/resources/containers/subresources/files/methods/list) 不是 Codex Memory API，但能確認 OpenAI 公開 collection contract 的一般形狀：每頁有上限、以 object ID `after` cursor 繼續，並回 `has_more` 與 `last_id`。這只能用來佐證成熟 list API 的 continuation 形狀，不能反推 Codex 內部 Memory Store。

**證據邊界：**公開 Codex 文件沒有提供可供一般 application 依賴的 exact-scope list API、跨頁 snapshot、per-memory expected-version CAS，或「每筆 Memory 缺少精確來源 ID 就拒絕」契約。不能從 OpenAI 可能存在的內部實作反推 Caliburn 必須自建同名機制。

### 1.2 Anthropic Managed Agents Memory

[Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory) 與 [List memories API](https://platform.claude.com/docs/en/api/beta/memory_stores/memories/list) 在研究日使用 `agent-memory-2026-07-22` beta 行為，公開：

- workspace-scoped text-document store；官方建議 many small focused files；
- 每筆 Memory 上限 100 kB、每個 store 最多 10,000 筆；這是現行 beta service limit，不是 Caliburn 的建議粒度；
- 每次 mutation 建立 immutable memory version；
- update **可以**帶 `content_sha256` precondition，失配後重新讀取再試；
- list 以穩定、server-defined order 回傳，使用 opaque `next_page` 分頁；
- `next_page == null` 才表示沒有後續頁；`view=full` 是官方明列的 export／sync bulk-read path；
- list result 含 service-generated ID、current version ID、hash 與時間。

**證據邊界：**hash precondition 是可用的安全能力，不是所有 request 的強制欄位；API 文件也沒有承諾跨多頁列舉期間的 snapshot isolation。Memory version 提供變更 audit／recovery，不等於每筆內容都具有 semantic source citation。

### 1.3 Google Memory Bank

[Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)、[List memories API](https://cloud.google.com/vertex-ai/docs/reference/rest/v1beta1/projects.locations.reasoningEngines.memories/list) 與 [Memory revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions) 在研究日公開：

- extraction 後會與同 scope 既有 Memories consolidation；預設會考慮同 scope 的全部既有 Memories；
- `ListMemories` 以 `pageSize／pageToken` 分頁，response 的 `nextPageToken` 用來繼續；沒有 token 才表示後續頁已走完；
- current Memory 與 revision history 分開；revisions 預設開啟，但官方允許停用；
- revision label 可附 data-source ID，但 label 是應用可選 metadata；
- background generation 是 production 常見建議，但當前 run 依賴結果時可等待完成。

**證據邊界：**Google 證明 revisions 與全量 scope retrieval 是成熟能力，卻沒有建立與 Anthropic 相同的 expected-content-hash CAS，也沒有公開跨頁 snapshot token。可停用 revisions 與可選 labels 更不能被改寫成所有第一版實作的硬要求。

### 1.4 AWS AgentCore Memory

[Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)、[ListMemoryRecords](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListMemoryRecords.html) 與 [BatchCreateMemoryRecords](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_BatchCreateMemoryRecords.html) 公開：

- timestamped raw events 與 extracted／consolidated long-term records 分層；
- namespace／path 下可用 `nextToken` 分頁列舉 Memory records；
- batch create 可選 `clientToken` 以保證該 batch request 的冪等處理；
- batch response 可能同時有 successful 與 failed records；metadata 由應用選擇提供。

**證據邊界：**AWS 沒有公開 record update 的 expected-revision CAS，也沒有承諾 batch 全成全敗或跨頁 snapshot。optional metadata 不能證明 per-memory semantic lineage 是必填共識。

### 1.5 LangGraph／LangChain

[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 明確區分：checkpointer 保存 thread state snapshots；Store 保存 application-defined key-value data。官方 PostgreSQL saver／store 可承接 production persistence。

[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api) 明確要求可能重放的 side effect 放進 task，並以 idempotency key 或查核既有結果避免重複。這是**效果要求**；它沒有規定每個應用都要另建 operation-receipt table。

[LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores) 現在明文把「不帶 `query`／`filter` 的 `search／asearch`」定位為列舉 namespace 內容的方式，並示範用 `limit＋offset` 逐頁走完；`list_namespaces／alist_namespaces` 則用來發現 namespace。這是可直接使用的成熟 primitive，不應先另建 catalog。文件同時明示三個限制：prefix 不是 exact match、超過 `limit` 會靜默截斷，而且不同 backend 的預設排序不同。

[BaseStore `asearch`](https://reference.langchain.com/python/langgraph.store/base/BaseStore/asearch) 公開 `limit／offset`，而[官方 PostgreSQL Store 原始碼](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/store/postgres/base.py)顯示非語意列舉只以 `updated_at DESC` 排序後做 `LIMIT／OFFSET`，沒有 key tie-break、opaque cursor 或 snapshot token。這不推翻它作一般 browsing primitive 的用途，但依 [PostgreSQL `LIMIT／OFFSET` 官方規則](https://www.postgresql.org/docs/current/queries-limit.html)，非唯一排序無法構成穩定分頁契約；跨頁測試即使某次通過也不能證明 exact inventory。它只能用來暴露失敗，不能作 M9／Go 依據。

Store 也提供 namespace、key、put／delete／search／listing 等 primitive；公開 `put` 契約沒有 expected-version CAS。這表示 Store 不自動解決多 writer lost update，但也不表示每個單 writer 第一切片都必須先另建版本平台。

本 repo 目前鎖定 `langchain==1.3.15`、`langgraph==1.2.11`、`langgraph-checkpoint-postgres==3.1.2`，其 transitive `langgraph-checkpoint==4.1.1`；研究日 PyPI 的 `langgraph-checkpoint` latest 是 `4.2.0`。這不構成自動升級理由；施工前要先核對相容範圍，並在實際 lockfile 版本重跑 Store contract tests。現行 runtime 也已用 per-document `asyncio.Lock` 阻止同一 process 內 model run 與 employee mutation 交錯。這是 **Caliburn 現況**，不是大廠共識；它只說明第一切片可以先明確採單 writer 假設，不必假裝目前已有多 writer。

### 1.6 Pydantic AI Harness Memory

[Pydantic AI Harness Memory](https://pydantic.dev/docs/ai/harness/memory/) 在研究日仍是 `0.x`，但公開了幾個值得正式比較的成熟 primitive：

- application resolve namespace，model-facing Tool 不能選其他使用者 scope；
- bounded notebook injection，以及 `read／write／delete／search` Tools；
- store contract 內建 optimistic CAS 與由 run／tool-call 衍生的 durable idempotency；PostgreSQL store 在 DB transaction 內實作；
- read、path listing 與 search 全部刻意有界，超出時以 truncation／limit 告知模型再按需讀取；
- 官方明示 Memory records 不自帶 source citations 或 verified provenance。

**證據邊界：**Harness 很適合證明 CAS、冪等、有界 Context 與 Runtime-owned scope 可以由框架承接；但其公開 `list_paths(limit)` 沒有 M9 所需的 iterate-all cursor／offset 契約，且官方明說 verified provenance 需 application schema／custom store。因此不能因單項 Store ergonomics 較完整，就宣稱它已覆蓋 Caliburn 全量盤點或來源政策。

### 1.7 來源新鮮度與證據等級

| 來源 | 研究日可確認的新鮮度 | 本文採用方式 |
| --- | --- | --- |
| OpenAI Codex Memories／公開 collection APIs | 2026-09-02 直接讀取現行官方頁；Codex Memories 頁未提供公開版號 | Codex 只採公開 Memory 行為，不推測內部 Store；collection API 的 ID cursor＋`has_more` 只佐證 OpenAI 公開 list contract 形狀 |
| Anthropic Managed Agents Memory | 現行 beta header `agent-memory-2026-07-22`；2026-09-02 直接讀取 | 可引用 stable server-defined order、opaque `next_page`、bulk-read path、immutable versions 與可選 hash precondition；beta 能力不得冒充跨家所有細節標準 |
| Google Memory Bank | API reference 提供 `pageToken／nextPageToken`；平台頁明示 2026-09-01 更新 | 可引用 scope listing、token pagination、current＋revision 與可停用 revisions |
| AWS AgentCore Memory | 2026-09-02 直接讀取 latest API Reference | 可引用 namespace listing、`nextToken`（null 表示結束）、可選 client token 與逐筆 batch 結果 |
| LangGraph／LangChain | 現行 Stores／Persistence／Functional API；PyPI `langgraph 1.2.11` 發布於 2026-08-11、`langgraph-checkpoint 4.2.0` 發布於 2026-08-07 | API 行為先以官方文件為準；排序與 SQL 邊界另用官方原始碼確認，最後以本 repo pinned version 測試 |
| Pydantic Harness | 2026-09-02 現行官方文件仍標示 Harness 為 `0.x` | 作 CAS、冪等與有界 notebook 的成熟候選證據；不把其有限 listing 或無 verified provenance 誤寫成 M9 完整解法 |

## 2. 逐題結論矩陣

| 能力 | OpenAI 公開 | Anthropic | Google | AWS | LangGraph | 研究結論 |
| --- | --- | --- | --- | --- | --- | --- |
| scope 內完整列舉／分頁 | Codex Memory 未公開；其他 OpenAI collection API 採 ID cursor＋`has_more` | stable order＋opaque `next_page` | `pageToken／nextPageToken` | `nextToken` | 官方文件只有無 query/filter listing＋offset；無 cursor／overflow／snapshot 保證 | **成熟共同能力形狀是 bounded pages＋server continuation token＋明確結束訊號**；LangGraph 目前不直接覆蓋 |
| 跨頁一致 snapshot／manifest | 未公開 | 未承諾 | 未承諾 | 未承諾 | 未內建承諾 | **不是跨家共識**；只有真有並行 writer／長盤點風險時才加 |
| current state 可修訂 | 有 generated consolidation 概念 | 有 | 有 | 有 managed update／consolidation | 有 put／delete | **共同效果** |
| immutable revision history | 未公開相同契約 | 有 | 有、可停用 | 未公開相同契約 | Store 無；checkpoint 另有 history | **成熟選用治理能力**，不是第一切片共同硬要求 |
| expected-version／hash CAS | 未公開 | 有、可選 | 未公開相同契約 | 未公開相同契約 | Store 無 | **供應商差異能力**；多 writer 或 lost-update 風險出現才升級 |
| retry 不重複副作用 | 未公開 Memory operation token | mutation API 可安全重試但機制不同 | managed operation | optional client token | 明確要求 task idempotent | **共同效果**；實作可用 deterministic key、task result、token 或 receipt，不固定 table |
| 每筆必填 semantic lineage | supporting evidence 存在，但未要求每筆 | version audit，未要求逐筆來源 | source／revision label 可選 | metadata 可選 | application schema 自訂 | **不是共識**；不能以缺少 lineage 一律拒絕 mutation |

## 3. 修正後的框架無關基線

第一版真正必須保留的是效果，不是特定資料表：

1. 原始 conversation／events 耐久保存，與整理後 Semantic Memory 分層。
2. 每份 JD 使用受信任、隔離的 scope；模型不能填 scope、canonical ID、版本或時間。
3. Semantic Memory 可 add／revise／remove／no-op，正常讀取只看目前有效內容。
4. 日常建立／修改 JD 只取少量相關 Memory；只有員工準備完成 JD、執行最後全面檢查時，Runtime 才使用非語意 inventory seam 走完 exact-scope 全部 Memory。該 seam 不能與 relevance search 混用，且必須通過所選 backend／版本的完整性測試。
5. 可重放 side effect 不得重複建立邏輯 Memory；第一版可用 checkpointed task＋Runtime deterministic key／upsert 達成，不預設 operation-receipt table。
6. tool／store 結果要能區分成功、no-op、invalid、not-found 與 retryable failure；模型不能猜成功。
7. 全量盤點只能證明「所有當時已發布的目前 Memory 都被送入處理」，不能證明所有來源事實都已正確 admission 進 Memory，也不能保證 LLM 的語意判斷百分之百正確。

以下能力保留為成熟強化選項，不再作第一切片硬門檻：

- immutable revision history／rollback；
- expected-version／content-hash CAS；
- dedicated operation receipt table；
- persisted inventory snapshot manifest；
- 每筆 Memory 強制 semantic lineage，缺少就拒絕；
- Qdrant、embedding、outbox 或 reranker。

## 4. Exact inventory 的精確語意

### 4.1 它不是日常 JD hot path

Caliburn 需要兩種不同讀取模式，不能混成「每次做 JD 都把全部 Memory 塞入 Context」：

1. **日常分析／編輯**：依本輪員工訊息、目前主題與 JD 變更，只召回少量相關 Memory；模型仍可按需再搜尋／讀取。
2. **完成前全面檢查**：員工準備完成 JD 時，才低頻列舉同一 JD 的全部 current Memory，分批檢查工作是否完整涵蓋、是否重複或互相衝突。

因此 exact inventory 是 final-audit capability，不是每回合成本。它保證的是「需要全面盤點時不會因 top-k 或靜默截斷漏掉 Memory」，不是要求單次 prompt 同時容納所有 Memory；Runtime 可以分批處理並累積檢查結果。

### 4.2 大廠公開共識與證據邊界

| 系統 | 非語意全量 list 的公開契約 | 可確認的結束條件 |
| --- | --- | --- |
| OpenAI 公開 collections（非 Codex Memory API） | bounded `limit`＋object-ID `after` cursor | `has_more == false` |
| Anthropic Managed Agents Memory | stable server-defined order＋opaque `page／next_page`；`view=full` 用於 export／sync | `next_page == null` |
| Google Memory Bank | `pageSize／pageToken` | response 無 `nextPageToken` |
| AWS AgentCore Memory | `maxResults／nextToken`；官方建議 pagination | `nextToken == null` |

共同點是 **page 有界、continuation 由 server 發出、client 走到明確 completion signal**。公開文件都沒有承諾跨頁期間的 snapshot isolation；因此「盤點期間同 scope 不發布 mutation」仍是本切片的 Caliburn 邊界，不冒充供應商保證。

下列不是跨家共識：

- `LIMIT/OFFSET` 搭配非唯一排序；
- 只因某次結果少於一個猜測 limit，就在無已知上限時宣稱完整；
- 每次日常 JD 編輯都列舉全部 Memory；
- 為完整盤點必須先自建 manifest、第二 authority 或 revision platform。

### 4.3 LangGraph 缺口與 isolated-spike 暫定映射

M9 的必要效果是：

```text
受信任 JD scope
  → 走完全部頁面
  → 每個當時列出的 current Memory 都恰好進入處理
  → 完成後才可聲稱「已處理全部已發布 Memory」
```

目前 LangGraph 官方 Store 的無 query/filter listing 會在 `limit` 後靜默截斷，PostgreSQL backend 又只按非唯一 `updated_at DESC` 做 `LIMIT/OFFSET`。這不具上述成熟 server-cursor contract；依 PostgreSQL 官方規則，它不能作跨頁 exact inventory 的 Go 證據。

Owner 在看完本節共識研究後，已於 2026-09-02 **正式同意只供 isolated spike 使用**的映射是：

1. 設定一個只屬於 spike claim boundary 的 `configured_spike_cap`，單次要求 `cap＋1`；
2. 回傳 `0..cap` 筆時，逐筆驗證 exact leaf、key 唯一性與 expected key set；
3. 回傳 `cap＋1` 筆時，回 typed overflow 並停止 final audit，絕不把部分集合交給模型或標成完成；
4. 不預設 production 永遠不會超過 cap，也不把此 fallback 稱為大廠共識；
5. production 若需支援 cap 以上，必須改採具 stable server cursor／token 的成熟 substrate，或停止重新選擇，而不是恢復目前 offset pager。

這個 fallback 的價值只是讓第一切片在明示上限內驗證 Store／writer／replay foundation，同時避免靜默漏資料；它不是 scalable exact-inventory 的最終設計。第一切片也不新增 `alist_namespaces＋aget` catalog、manifest、custom SQL repository 或第二 authority。

只有在下列任一事實成立後，才重開 snapshot 設計：

- 同一 JD 允許 model、employee 或 background writer 在全量盤點期間並行發布；
- 一次盤點長到不能用現有 admission lock／checkpoint 保持單一狀態；
- production 出現跨頁重複／漏讀或 stale publish；
- 產品需要對外證明某次 JD 由哪一組精確 Memory revisions 產生。

屆時再比較 database snapshot、scope generation、版本 worklist／manifest 或遇變更重啟；不能現在就宣稱某一個是大廠共識。

## 5. Provenance／lineage 的精確語意

跨家共同方向是「原始來源與衍生 Memory 分層，必要時可回查」，不是「每筆 Memory 都有模型填的 quote／source ID」。Caliburn 第一切片應採：

- conversation source 繼續由現行 durable owner 保存；
- Runtime 若已知本次 run／turn／event window，可低成本附上診斷 reference；
- 模型永遠不填可信 UUID、時間、版本或 quote offsets；
- 缺少細粒度 lineage 不應使本來合法的 add／update 失敗；
- 若未來稽核、幻覺診斷或員工 UX 證明需要，再提高到 per-memory supporting evidence。

因此「lineage 可用」是 observability 能力；「lineage 缺少就拒絕」是額外產品政策，尚未獲得跨家共同證據，也不應進入第一切片。

## 6. 修正後的最小垂直切片

### Stage 1：官方 Store primitive，無模型

只驗證：

1. per-JD namespace 隔離；
2. Runtime-owned deterministic key；模型形狀不能指定 canonical metadata；
3. add／revise／remove／no-op 的目前內容語意；
4. 同一 logical task replay 不重複建立 Memory；
5. 依 Owner 最終裁決的 inventory substrate 驗證 exact leaf；若採 isolated-spike `cap＋1` fallback，測零筆、一筆、cap 邊界、overflow、同時間戳、nested／相鄰 scope、刪除與 restart，overflow 必須 fail closed；
6. process／connection 重啟後資料仍存在；
7. typed success／no-op／invalid／not-found／retryable result。

第一階段直接使用 LangGraph 官方 PostgreSQL Store seam；不得使用其 offset pagination 冒充完整盤點。若 `cap＋1` fallback 無法在官方 public seam 證明明示邊界內的完整與 overflow fail-closed，就停止回來討論；不在同一 task 自行發明 pager。通過前不建立 custom revision repository、receipt table、manifest table、Qdrant 或 embedding。

### Stage 2：極小 Luna smoke，提早驗證真正風險

在 deterministic seam 綠燈後立即用短小、匿名繁中 fixture 驗證：

- 新工作資訊能新增；
- 員工明確補充／更正能修改既有目前內容；
- 無新工作資訊能 no-op；
- 模型只輸出小型語意 effect，不填系統 metadata；
- 無效 reference／schema 最多一次 bounded repair，仍錯就停止。

這只測 wiring、Prompt 與 effect contract，不建立完整 eval。它應早於版本平台與向量索引，因為目前最大未知是模型是否能可靠形成、修訂 rich Memory，而不是 PostgreSQL 能否保存 revision rows。

### Stage 3：只依實際缺口升級

- 召回真的不足，再比較 LangGraph Store semantic search、PostgreSQL lexical 或 derived hybrid index；目前產品明確不接 Reference RAG。
- 真有多 writer／lost update，再加 CAS。
- 真有 audit／rollback 需求，再加 immutable history。
- 真有長盤點並行修改，再加 snapshot／generation／manifest。
- 真有來源診斷需求，再提高 lineage 粒度。

## 7. 對現有文件的校正

本次重驗要求下游文件依下列優先序解讀：

1. [`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md) 保留 M1～M11 產品效果，但應移除把 immutable revision、CAS 與 persisted manifest 當成 framework-independent 必要機制的文字。
2. [`2026-09-02-memory-versioning-concurrency-and-replay-research.md`](./2026-09-02-memory-versioning-concurrency-and-replay-research.md) 的跨家事實仍有價值；其 custom versioned adapter、receipt 與 manifest 組合降為**條件式強化候選**，不再是第一版基線。
3. [`2026-09-02-memory-framework-selection-revalidation.md`](./2026-09-02-memory-framework-selection-revalidation.md) 仍可選 LangChain／LangGraph＋PostgreSQL；Qdrant／Voyage 研究保留為未來召回候選，不是 Memory foundation 的必要部分。
4. [`2026-09-02-memory-foundation-vertical-slice-design.md`](./2026-09-02-memory-foundation-vertical-slice-design.md) 應改成 §6 的最小順序。
5. Proposed ADR 0071／0072 與 Accepted ADR 0060 的正式取代關係沒有因本文自動改變。任何 production authority cutover 仍需新 ADR 明確核准；研究稿不能暗中翻案。

## 8. 最終判斷

本輪不是否定版本、CAS、manifest 或 lineage，而是把它們放回正確層級：

- **完整列舉／分頁**只在 JD 完成前全面檢查時是硬效果；多家成熟 API 的共同形狀是 server cursor／token＋明確結束訊號。LangGraph pinned PostgreSQL Store 不直接具備該契約，isolated spike 只能在明示 cap 內以 `cap＋1` fail closed 驗證，不能外推為無界 production 保證；
- **不重複副作用**是 durable runtime 的硬效果，但不固定為 receipt table；
- **immutable revisions、CAS、snapshot manifest、強制 lineage**是成熟但條件式的治理機制；
- 第一個切片應先用成熟框架 primitive 取得真實產品證據，再由觀察到的風險觸發強化。

這比先自建完整 authority platform 更符合目前產品核心、單一操作者與加速產品完成的限制，也更忠實於各家公開證據。
