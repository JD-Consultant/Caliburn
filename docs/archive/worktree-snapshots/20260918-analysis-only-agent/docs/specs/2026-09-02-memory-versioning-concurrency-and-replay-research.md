# Semantic Memory 版本、一致性與重放研究

- 日期：2026-09-02
- 狀態：**跨家事實已複核；2026-09-02 已校正第一切片的過強映射**
- 上位契約：[`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md)
- 框架選型：[`2026-09-02-memory-framework-selection-revalidation.md`](./2026-09-02-memory-framework-selection-revalidation.md)
- 範圍：只研究 current head、不可變歷史、stale-write protection、冪等、重放與原子發布；不決定正式 schema、migration、graph node 或 API。

> **研究紀律**：先分清楚「多家共同追求的效果」與「各家不同的具體機制」。`content hash`、單筆 revision、整個 scope generation、event-stream expected version 都能防止舊寫入，但不是同一個實作。本文不得把 Caliburn 的映射寫成所有大廠都使用的內部方法；官方未公開的部分維持未知。

> **重驗入口**：[`2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](./2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md) 以研究日最新官方 API 重新檢查 listing、snapshot、revision、CAS、idempotency 與 provenance。若本文較早文字把 custom revision repository、operation receipt 或 inventory manifest 寫成第一切片必做，以該重驗與本文校正後的 §3～§4 為準。

> **較新機制稽核（2026-09-02）**：[`Memory 實作機制與成熟框架共識稽核`](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md) 再把功能效果、責任分工、相同 primitive、單家 framework 能力與 Caliburn 映射分層。下文的 serial writer、deterministic key 與 LangGraph Store 組合只能視為候選映射，不是已核准基線；mutation safety／replay 尚待 Owner 從成熟候選中裁決。

> **後續能力校正（2026-09-02）**：把完整 Semantic Memory collection 放進 Checkpointer 的候選已否決；最新方向見 [`Memory 實作機制與成熟框架共識稽核` §10](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md)。下文 Store replay／CAS 分析重新適用於主要候選，但第一切片仍只依實際 contract 缺口採用，不能把所有強化機制一次升格為硬要求。

## 1. 結論摘要

跨 OpenAI、Anthropic、Google、AWS、LangGraph、Pydantic Harness 與成熟 PostgreSQL／SQLAlchemy primitive 複核後，可以支持下列結論：

1. **模型只能提出語意變更，不能自己填 scope、record ID、revision、hash、時間或 operation ID。**這些是 Runtime／Store 的可信 metadata。
2. **可重試工作一定要防止重複副作用。**LangGraph 明確要求可重放 task 的寫入自行具備 idempotency；Pydantic Harness 與 AWS Memory API 公開 token 型機制，但共同的是效果，不是 operation-receipt table。
3. **stale-write protection 是成熟能力，但只有實際存在重疊 writer 時才是必要機制。**Anthropic 提供可選 `content_sha256` precondition；Pydantic Harness 用 revision CAS；SQLAlchemy 可用 row version。這些不能推導出本機單 writer 的第一切片必須先自建 CAS 平台。
4. **current state 與可回查歷史分離是成熟做法，但 immutable history 不是每個公開 Memory API 的共同硬要求。**Anthropic 與 Google 公開 versions／revisions，Google 也允許停用；LangGraph Store、AWS 與 OpenAI 公開契約沒有相同保證。
5. **原子性只保證到公開介面承諾的 mutation unit。**PostgreSQL transaction 能讓一組本地寫入 all-or-nothing；Pydantic 要求 CAS 與冪等在同一 store operation 原子完成。AWS 的 batch Memory API 則會回傳逐筆成功與失敗，不能據此推論跨 record 原子性。

因此，本輪不把 `per-JD scope generation`、immutable revision、CAS、operation receipt 或 snapshot manifest 宣稱為跨家第一版共識。本文當時曾暫定以下第一切片候選，但較新機制稽核已撤銷其「基線」地位：

```text
單一 JD scope 的 serial writer
  + LangGraph task／checkpoint 可安全 resume
  + Runtime deterministic key 或查核既有結果，避免 replay 重複 add
  + 官方 Store 的目前內容 CRUD／非語意 listing／persistence
  + typed success／no-op／invalid／not-found／retryable result
```

在 Owner 裁決前，這段不能直接轉成實作計畫。

當產品真的允許並行 writer、觀察到 lost update、需要 rollback／audit，或全量盤點期間仍要接受 mutation 時，再依觸發的問題選 CAS、immutable history、receipt、snapshot 或 `scope generation`；不把它們綁成一整套預設平台。

## 2. 各家公開做法

| 來源 | 公開保證 | 沒有證明的部分 |
| --- | --- | --- |
| OpenAI Responses | `conversation`／`previous_response_id` 可延續多輪 conversation state | 公開 API 未提供可據以宣稱 application Semantic Memory 具有 current-head CAS、immutable revision 或跨 record 原子更新的契約 |
| Anthropic Managed Agents Memory | live retrieve 取最新版本；每次 mutation 產生 immutable version；更新可帶 `content_sha256` precondition，失配後重讀再試；復原是把舊內容寫成新的 update | Managed service 為 beta、綁供應商；沒有證明其內部採 per-scope generation |
| Google Memory Bank | `Memory` 表示目前 consolidated state；create／update／delete 形成 child immutable `MemoryRevision`；可 list／get／rollback；scope 可全量分頁取回 | 公開 revision 文件未建立與 Anthropic 相同的 expected-hash CAS 契約，也沒有承諾跨頁 concurrent mutation snapshot |
| AWS AgentCore Memory | `CreateEvent`、Memory resource mutation 與 batch create 等 API 使用 `clientToken`／request identifier 提供冪等；Memory record 有 service-generated ID 與時間 | batch response 可同時含 successful／failed records，不能當成跨 record all-or-nothing；公開 record update input 未顯示 expected revision CAS |
| LangGraph | checkpoint 保存 thread state history並支援 resume／replay；Functional API 要求副作用放進 task 並自行使用 idempotency key 或查核既有結果 | `BaseStore.put` 只是 store-or-update；官方 `PostgresStore` 實作是無 expected revision 的 `ON CONFLICT ... DO UPDATE`，不能單獨承擔 stale-write protection |
| Pydantic Harness Memory | Store contract 直接包含 optimistic CAS 與 idempotency；stale revision 失敗；同 operation ID＋同參數 replay 不重複寫入；同 ID＋不同參數報 operation conflict；PostgreSQL store 在 DB transaction 內保證 | Harness 仍是 0.x；file／notebook contract 沒有公開等同 Anthropic／Google 的 immutable history，也沒有建立 Caliburn exact-inventory snapshot 契約 |
| SQLAlchemy／PostgreSQL | `version_id_col` 產生 `WHERE id=? AND version=?` 型 stale-row detection；PostgreSQL transaction 讓多步寫入 all-or-nothing，conditional update 可原子確認舊版本 | ORM row version 只處理映射 row 的 flush，不自動解決跨多筆 Memory、operation receipt、歷史 revision 或長時間 LLM 分析後的 stale result |

### 2.1 OpenAI 公開資料的正確解讀

OpenAI Responses 的 `conversation`／`previous_response_id` 解決的是多輪 state continuation。它可以作為 conversation durability 的證據，但不能拿來證明 OpenAI 公開了 application Semantic Memory 的 CAS 或 revision backend。本輪官方搜尋沒有找到這項公開契約，因此本文不推測 OpenAI 內部實作。

### 2.2 LangGraph checkpoint 與 Store 不是同一種一致性

LangGraph replay 會重用已完成 task 的 checkpointed result；但一個已開始、未成功完成的 task 仍可能再次執行，所以官方要求副作用本身冪等。這表示：

- checkpoint 能保護 workflow progress；
- 它不會自動把外部／Store 寫入變成 exactly-once；
- Semantic Memory publisher 仍須 operation idempotency；
- checkpoint history 也不能自動變成 Store item 的 immutable revision history。

### 2.3 「共同效果」不等於「共同欄位」

各家用不同 token 表達「我是在舊狀態 X 上修改」：

| 形式 | 代表來源 | 意義 |
| --- | --- | --- |
| content hash precondition | Anthropic | 只有目前內容仍符合讀取時 hash 才更新 |
| record／file revision | Pydantic Harness、SQLAlchemy version row | 只有目前 revision 仍等於 expected revision 才更新 |
| client／operation token | AWS、Pydantic Harness、LangGraph 官方 guidance | 同一 logical operation 重試不能重複產生副作用 |
| immutable version resource | Anthropic、Google | current state 可變，但舊版本保留供 audit／recovery |

Caliburn 應承接的是這些效果，不要求模型輸出任何一種 token，也不必複製某家雲端 API 的欄位名稱。

## 3. Caliburn 第一版 Working Recommendation（重驗後）

### 3.1 發布單位

Memory Manager 只產生有界語意 intent：

```text
add(content)
update(target_reference, new_content)
remove(target_reference)
no-op
```

Runtime 根據本輪已提供的短期 reference 解析真正 target identity；Store 才執行發布。模型不得填 canonical ID、時間、scope、operation ID、版本或 current flag。第一切片不暴露並行 writer，因此 update／remove 不先要求模型或 Runtime 攜帶 expected revision；若日後開放並行，才在同一 seam 增加可信 precondition。

### 3.2 安全發布與 replay

第一切片在既有 per-document admission／lock 內只有一個 writer。每個可重放 side effect 放進 LangGraph task，Runtime 以 run／task 已知資料形成 deterministic Memory key，或先查核該 logical effect 是否已存在；相同 task replay 只得到相同目前結果，不重複建立第二筆 Memory。

第一切片直接使用官方 PostgreSQL Store 的原子單項 put／delete；只有彼此依賴的多項變更真的需要 all-or-nothing 時，才另研究一個最小 transaction seam。不能因 PostgreSQL 支援 transaction 就先建立所有尚未被產品觸發的 revision／receipt tables。

### 3.3 重放與錯誤語意

| 情境 | Store 結果 |
| --- | --- |
| task 在 Store write 前失敗 | 沒有 mutation；可重跑 |
| Store write 成功、task completion 尚未 checkpoint 就 crash | deterministic key／既有結果查核讓 replay 成為同一 put／remove，不重複 add |
| target reference 找不到 | `NOT_FOUND`；重新 search／read，不猜 ID |
| payload／operation 不合法 | `INVALID`；依欄位錯誤最多有界修正 |
| 暫時性基礎設施失敗 | `RETRYABLE_FAILURE`；由 Runtime bounded retry |
| 未來發現 stale／並行衝突 | 停止 silent overwrite，新增 CAS 後重讀再做語意判斷；此情境不假裝第一切片已支援 |

重試邊界應有上限；任何語意或 reference 錯誤都不能由 tool 無限自行循環。

### 3.4 Exact inventory 的一致性另行處理

完整列舉與跨頁一致 snapshot 是兩種能力。Anthropic、Google、AWS 與 LangGraph 都有 listing／pagination primitive，但研究日官方文件都未共同承諾跨頁 snapshot isolation。[LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores) 明示不帶 `query／filter` 的 `search／asearch` 可用來列舉，並示範 `limit／offset`；同頁也明示 namespace 參數是 prefix、PostgreSQL backend 按 `updated_at` 排序且不同 backend 順序不同。[官方 PostgreSQL Store 原始碼](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/store/postgres/base.py) 進一步顯示目前 SQL 沒有 key tie-break。因此第一切片採單 writer與 Runtime-owned leaf namespace，逐項驗 exact namespace equality，盤點 worklist／進度保存在既有 LangGraph checkpoint，並把多頁、相同 `updated_at`、nested／相鄰 scope、delete 與 restart 列為 pinned-version contract tests：

```text
同一 JD scope 暫停 mutation
  → 走完全部 pages
  → 每個列出的 current Memory 恰好處理一次
  → 完成後才解除 admission
```

只有這些測試通過後，才能在目前 PostgreSQL backend 上聲稱 exact inventory；失敗就停下比較最薄 fallback，不由實作者自行加 catalog。若未來允許 background／employee／model writer 與盤點並行，再比較 database snapshot、version worklist／manifest、`scope_generation` 或遇變更重啟。第一切片不新增持久 manifest entity。

## 4. 框架責任調整

LangGraph 仍是首選 runtime。第一切片使用：

```text
LangGraph task／checkpoint
  + 官方 AsyncPostgresStore namespace／put／delete／非語意 listing
  + Runtime-owned scope、短期 reference、deterministic key 與薄 inventory wrapper
```

內建 `AsyncPostgresStore` 足以作為目前內容、隔離、persistence 與 inventory 的**驗證起點**；它是否足以承擔本案「跨頁無漏／重」宣稱，要由 pinned-version contract tests 裁決，不能只靠 API 名稱推定。它確實沒有 expected-version CAS／immutable history；這是已知能力邊界，不是要求尚未出現多 writer 風險時先自建平台。任何後續 inventory fallback、CAS／history 強化都放在 Store seam 外，且不能修改 framework-owned table 或依賴未文件化內部 schema。

## 5. 本輪排除方案

### 5.1 只靠「同一 JD 同時一個 run」

單 writer 能排除同時 lost update，但不能單獨處理 process crash replay；因此第一切片另以 LangGraph task＋deterministic key／查核既有結果補足 replay。只要不啟用 background writer，兩者合用已是可驗證的第一階段 boundary。

### 5.2 只把 revision 寫進 Store JSON 再 `put`

兩個 writer 可以同時讀到 revision 7，然後都無條件覆寫成 8；這只是標記版本，不是 CAS。第一切片不使用這種假 CAS，也不假裝存在兩個 writer。

### 5.3 直接混入 Pydantic Harness

Harness 是很好的 CAS／idempotency 參考，但目前不是 primary runtime，且沒有完整覆蓋 immutable revision history 與 exact inventory。第一版不為單一元件混入第二套完整 agent runtime。

### 5.4 導入完整 event-sourcing platform

Expected stream revision、append-only events 與 projections 可以滿足這類一致性，但也會引入 aggregate、event model、projection runner 與另一套 operational abstraction。第一切片的 serial writer、LangGraph task／checkpoint、deterministic key 與官方 PostgreSQL Store 已足以驗證目前被觸發的效果；尚未出現 audit、rollback 或多 writer 問題前，不先增加 event-sourcing 或自訂 versioned adapter。

## 6. 條件式強化與尚未決定

1. 正式 semantic payload／tool wire contract；
2. 真有並行 writer 時，expected precondition 使用整數 revision、content hash 或其他 framework primitive；
3. 真有 audit／rollback 需求時，immutable revision 的保留期限與 privacy redaction；
4. 真有盤點中並行 mutation 時，snapshot／manifest／generation／restart 的最薄方案；
5. 代表性訪談證明官方 Store search 不足後，才比較 lexical／vector／hybrid recall；
6. typed error 的正式契約名稱與重試上限。

以上項目必須繼續先比較成熟做法，再選最薄方案；不得由實作者自行補欄位。

## 7. 官方來源

### OpenAI

- [Responses API：`conversation`／`previous_response_id` 用於多輪 conversation state](https://platform.openai.com/docs/api-reference/responses)

### Anthropic

- [Managed Agents Memory：immutable versions、latest retrieve、`content_sha256` optimistic concurrency 與 recovery](https://platform.claude.com/docs/en/managed-agents/memory)

### Google

- [Memory revisions：current Memory、immutable revisions、delete history 與 rollback](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)
- [Fetch memories：exact-scope retrieval、similarity retrieval 與分頁](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)

### AWS

- [CreateEvent：`clientToken` 讓 operation no-more-than-once](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_CreateEvent.html)
- [BatchCreateMemoryRecords：batch idempotency token 與逐筆成功／失敗](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_BatchCreateMemoryRecords.html)
- [MemoryRecordUpdateInput：record update 的公開輸入](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_MemoryRecordUpdateInput.html)

### LangGraph／LangChain

- [Functional API：replay、side-effect task 與 idempotency guidance](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [Persistence：checkpoint history、replay 與 Store 分工](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Stores：非語意 listing、offset pagination、靜默截斷與 backend 排序差異](https://docs.langchain.com/oss/python/langgraph/stores)
- [BaseStore `asearch`：`limit／offset` 公開契約](https://reference.langchain.com/python/langgraph.store/base/BaseStore/asearch)
- [BaseStore `put`：store or update](https://reference.langchain.com/python/langgraph.store/base/BaseStore/put)
- [官方 PostgreSQL Store source：無 expected revision 的 `ON CONFLICT ... DO UPDATE`，非語意 listing 只按 `updated_at DESC`](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/store/postgres/base.py)

### Pydantic AI／資料庫

- [Pydantic Harness Memory：CAS、operation idempotency 與 atomic custom-store requirement](https://pydantic.dev/docs/ai/harness/memory/)
- [SQLAlchemy version counter：row-level stale update detection](https://docs.sqlalchemy.org/en/20/orm/versioning.html)
- [PostgreSQL transaction：多步 all-or-nothing](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [PostgreSQL transaction isolation：conditional update、serialization failure 與 retry](https://www.postgresql.org/docs/current/transaction-iso.html)
