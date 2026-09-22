# Memory Foundation 最小垂直切片設計（Store-first 重寫）

- 日期：2026-09-02
- 狀態：**Draft for Owner Review；尚未授權施工**
- 範圍：只設計第一個可驗證的 Memory foundation 切片；不是完整 Memory、JD、UI、ADR 或施工計畫
- 取代：本文件先前的「Checkpointer current collection」候選；該候選已正式否決，不再保留為可施工方案
- 上位產品契約：[`Framework-independent Memory Contract`](./2026-09-01-framework-independent-memory-contract.md)
- 能力來源：[`滿分 JD 的 LLM 能力研究`](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)
- 框架稽核：[`Memory 實作機制與成熟框架共識稽核`](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md)

> **閱讀規則**：本文只回答「下一個最小實驗要證明什麼，以及什麼證據不足時必須停止」。它不因寫得具體就自動授權 production 改造。若本文與較早 Memory 草稿衝突，以本文及上列較新研究為準；若實作發現新證據，先回來討論，不得自行補出第二套 authority、資料表、manifest、CAS、RAG 或 retry loop。

> **現行 production 邊界不變**：Accepted ADR 0060 與 `AGENTS.md` 目前仍由 Checkpoint 擁有可修訂 semantic state，Store 擁有來源。本文研究的新方向會改變該 authority 分工；在 successor ADR 明確 Accepted 前，不得把本切片直接接入 production authority。

## 0. 白話結論

第一個切片不是先做完整顧問，也不是先做 JD。它只驗證兩個真正未知：

1. **LangGraph 官方 PostgreSQL Store 能否可靠保存一份 JD 私有的多筆目前 Memory**：可新增、讀取、修訂、移除、重啟恢復、隔離，並在完整檢查時不靠相似度搜尋而走完全部目前 Memory。
2. **LangMem 哪個正式介面能較可靠地把新訪談與既有 Memory 整理成新增／補充／更正／不同案例／未解衝突**，同時不遺失員工沒有在本輪重述的既有細節；第一切片只驗證 deterministic `no_change` outcome 的 apply wiring，不驗證模型能否從自然語言辨識 no-op。

首選責任分工是：

```text
LangGraph PostgreSQL Checkpointer
  = active conversation／run state、有限近期訊息或來源 references、interrupt／resume、故障恢復與短暫工作結果

LangGraph PostgreSQL Store（每份 JD 由 Runtime 固定隔離範圍）
  = 完整可回查的員工來源
  + 多筆聚焦、詳細、自足、可修訂的目前 Semantic Memory

LangMem core 或 Store manager（以極小對照實驗二選一）
  = conversation＋目前相關 Memory
    → 新增／修訂／移除／no-op 的 extraction／consolidation 候選

可信 Runtime
  = scope、identity、framework metadata、驗證、持久化結果與 typed failure

LLM＋職務分析 Skill（後續切片）
  = 讀取 Memory、理解工作、判斷是否及如何編輯 JD
```

Store 官方文件常用「cross-thread long-term memory」描述用途；這是 Store **可以**跨 thread 使用，不是「只有跨 thread 才能使用」。本產品雖是一份 JD 對應一個長期 thread，仍需要可逐筆搜尋、修訂、列舉且不隨每個 graph checkpoint 重複快照的長期 application data，因此 Store 比 Checkpointer 更符合生命週期與存取模式。

## 1. 不可偏離的產品目的

Caliburn 的目的只有一個：透過長期員工訪談，產出準確、完整、不重複、抽象層級合理、可持續修訂且由員工核准的高品質職務說明書。

Memory 只是手段。它必須讓後續顧問在需要時能取得員工完整工作範圍與重要細節，但 Memory 本身不能：

- 決定一段資訊是 Duty、Task、工作細節、完成標準或 K／S；
- 決定現在是否要編輯 JD；
- 操作或核准 JD；
- 把一筆 Memory 一對一映射成一個 JD 欄位；
- 取代員工核准。

第一切片必須保住以下效果：

1. 一名員工、一份 JD、一個長期訪談 thread、一組私有 Memory；不跨 JD 共用。
2. 完整訪談來源與整理後 Memory 分層；Memory 不能取代原始來源。
3. Memory 是多筆聚焦、詳細、自足、可修訂的目前內容，不是巨大摘要，也不是一則訊息一筆 fact。
4. 補充不能刪掉本輪未重述的既有細節；明確更正才取代舊理解；條件或案例不同不能誤當覆寫。
5. 不知道與未解衝突可以留在自然語言內容中，不為填欄位猜答案。
6. 日常可有界召回；只有 JD 完成前的全面檢查必須能處理全部目前有效 Memory。
7. 模型只產生語意內容與受限 mutation intent；scope、canonical identity、版本、時間、retry 與權限由 Runtime／framework 管理。

完整能力定義仍以 M1～M11 為準；本文只誠實說明第一切片能證明其中哪一部分。

## 2. 研究事實、產品映射與未決問題必須分開

### 2.1 已有多家官方支持的責任分層

| 共同方向 | 官方公開形狀 | 對本切片的約束 |
| --- | --- | --- |
| Conversation／events 與整理後長期 Memory 分層 | OpenAI Codex generated memories、Anthropic Memory stores／tool、AWS short／long-term、LangGraph Checkpointer／Store | 原始訊息與 Semantic Memory 不互相取代 |
| Memory 以多筆聚焦內容累積與修訂 | Anthropic 建議 many small focused files；LangMem collection；LangGraph Store records | 不把完整工作理解塞成單一 checkpoint channel 或巨大 profile |
| Extraction 與 consolidation 分責思考 | OpenAI 分開 extraction／consolidation model；Google、AWS、LangMem 有同類流程 | 新來源先判斷形成什麼，再和目前 Memory 比較；不代表固定兩次模型呼叫 |
| Runtime／應用掌握可信 scope 與 identity | Anthropic 掛載 store/path；LangGraph Runtime namespace；Pydantic Harness resolver | 模型不能選 JD scope，也不能自行捏造 canonical ID |
| 自動 Context 有界，必要時按需搜尋／讀取 | Anthropic JIT memory read、LangGraph Store search、LangMem／Harness bounded retrieval | 不以每輪注入全部 Memory 換取表面記憶能力 |
| 失敗可辨識、重放不能重複副作用 | OpenAI／Anthropic call-correlated tool result、AWS client token、LangGraph idempotent task guidance、Harness idempotency | 必須測 end-to-end replay；不能只看到 `put` 成功就宣稱已安全 |

這些是責任分工或共同效果，不表示各家使用同一 database、key、lock、cursor、CAS 或 retry loop。

### 2.2 本切片明示採用的 Caliburn 產品映射

下列不是「OpenAI／Anthropic 內部也一定如此」，而是為本機、單操作者、每份 JD 獨立範圍作出的最薄候選：

1. 使用同一套 LangGraph／LangChain runtime，Checkpointer 與 PostgreSQL Store 各負責其官方定位的資料。
2. 一份 JD 由 Runtime 解析成固定、不可由模型指定的 Store scope。
3. 來源與 Semantic Memory 使用同一 PostgreSQL Store 的不同**邏輯 leaf namespace**；不代表新建兩套資料庫或兩套 authority。
4. 日常建立／修改 JD 只召回本輪相關 Memory；只有 JD 完成前的低頻全面檢查才啟動完整盤點。該盤點只接受能證明「沒有漏、沒有重」的 exact-inventory primitive；同一 JD 沒有並行 mutation 仍是第一切片邊界，但這個條件本身不能修補不唯一排序的 offset pagination。
5. 使用 `gpt-5.6-luna`、`medium` 做極小相容性 smoke；不是正式模型品質 eval。

### 2.3 尚未決定，不能由實作者偷選

1. `create_memory_manager` 或 `create_memory_store_manager` 哪個成為正式 semantic writer leaf。
2. exact inventory 的 **production** substrate 尚未決定。Owner 已在完成大廠共識查證後正式同意 isolated spike 可用「可信單批上限＋overflow fail closed」驗證明示邊界；不得把它冒充 server-cursor 共識、無界解法，或沿用 PostgreSQL Store 的 `updated_at DESC＋LIMIT/OFFSET` 當作完整盤點。
3. 新增 Memory 的 end-to-end stable identity／replay owner；Store 的同 key upsert 不等於整條模型流程已冪等。
4. 多筆 mutation 是否需要 bundle atomicity，以及所選 framework 是否真的提供該 transaction contract。
5. 未來若有重疊 writer，採 CAS、hash precondition、operation token 或其他成熟 primitive。
6. immutable revision history、rollback、tombstone 或 archive 的正式物理形狀。
7. 日常 lexical／semantic／hybrid ranking、候選筆數與 token budget。
8. 小型導覽是否持久化；第一版可以完全不做。

## 3. 第一切片的 authority 與資料邊界

### 3.1 Checkpointer 只保存執行狀態

Checkpointer 可保存：

- thread 的 active conversation／run progress，以及本輪需要的有限近期訊息或來源 references；
- interrupt／resume；
- 目前節點的短暫結果；
- 本輪使用過的 Memory references；
- framework task result 與故障恢復需要的狀態。

Checkpointer 不再保存完整 Semantic Memory collection。否則每個 graph step 都可能把長期累積的完整集合重複進 checkpoint history，並把「可逐筆搜尋／修訂的長期資料」生命週期綁到 workflow snapshot。

### 3.2 Store 保存兩類不同但同 scope 的長期資料

概念上：

```text
trusted document scope
├─ source leaf
│  └─ 完整員工訊息／來源事件，可回查
└─ semantic-memory leaf
   └─ 目前有效的多筆 Semantic Memory
```

規則：

1. `document_id → namespace` 由 Runtime 以可信 catalog／context 解析，模型與自由文字輸入不能指定。
2. source leaf 與 semantic-memory leaf 必須可明確區分；第一切片不要求新 table。
3. semantic-memory leaf 下不再掛 child Memory namespace，避免 prefix listing 把其他集合混入。
4. 所有 list 結果仍逐項驗證 `item.namespace == expected_leaf`；發現相鄰或 child namespace 內容就 fail closed。
5. 不提供跨 JD fallback search；查不到就是查不到。
6. source leaf 只由可信 conversation intake 新增並供回查；員工後續更正形成新的來源事件，不能讓 semantic writer 覆寫或刪除舊原話。overwrite／delete 只作用於 semantic-memory leaf 的目前內容。
7. source 的 append-only 是應用契約，不是 Store `put` 自動提供：同一 source key＋完全相同 immutable payload 重送是 no-op；同 key＋不同 payload 必須 typed failure 且舊值不變；更正使用新 source key，兩筆都可回查。

### 3.3 單筆 Semantic Memory 的最薄邏輯形狀

Store 原生擁有：

- namespace；
- key；
- created／updated time；
- PostgreSQL persistence metadata。

模型可撰寫的 semantic document 只保留：

```text
topic
content
```

- `topic`：短、穩定、中性的工作主題標籤，只幫助辨識與召回，不是 identity。
- `content`：一項可獨立搜尋、理解與修訂的連貫工作主題；保留已知的行動、對象、目的／成果、情境、頻率、例外、協作、責任邊界與重要案例細節。

第一切片不要求模型填：

- canonical Memory ID／Store key；
- JD scope／namespace；
- source UUID、quote offset 或時間；
- status、confidence、conflict type；
- schema version、revision、hash；
- Skill ID、retry policy 或 operation token。

模型可以**選擇 Runtime 本輪已提供的既有 Memory handle**來表達「修訂這一筆」，但不能自行發明一個未提供的 handle。新增項目的持久 identity 必須由 framework／Runtime 產生；哪個元件正式擁有這一步，要由 replay contract test 後裁決。

### 3.4 粒度與目前內容規則

1. 一筆 Memory 是一個可獨立搜尋、理解與修訂的工作主題，不是一則訊息、一個 JD 欄位或整名員工的巨大 profile。
2. 拆開會破壞條件、例外、責任邊界或因果關係時，保留在同一筆 rich content。
3. 兩部分會獨立改變或日後需分別搜尋／修訂時，才拆成兩筆。
4. 工作案例若會影響理解，保留在相應 content；第一切片不另建 case store 或 case schema。
5. 同一主題的新細節是補充；明確否定／更正才取代舊細節；不同條件或不同案例可以並存。
6. 未知與未解衝突直接寫清楚「尚未確認什麼」及互斥說法；不新增模型欄位，也不依 recency／confidence 自動選邊。
7. 正常讀取只看目前有效內容；舊說法至少仍可由完整 source 回查。immutable history 是後續治理候選，不是第一切片前提。

## 4. 第一切片要驗證的三條路徑

### 4.1 路徑 A：官方 PostgreSQL Store contract（無模型）

使用真 PostgreSQL Store，先把模型不穩定性完全排除，驗證：

1. **Persistence**：source 的 append／get，以及 Semantic Memory 的 put／get／overwrite／delete，皆符合官方契約；process／connection restart 後仍一致。
2. **Isolation**：相同 key 在兩份 JD scope 中互不影響；具共同前綴的 canonical document ID、相鄰 leaf 或 child namespace 都不會混入另一個 exact scope。
3. **Current content**：同 key overwrite 只產生一份目前值；delete 後不再進 current listing，source leaf 不受影響。
4. **Typed result**：成功、合法 no-op、invalid、not-found 與 retryable infrastructure failure 可被區分，錯誤不能偽裝成成功。
5. **Restart**：API process／connection pool 重建後，來源與 Semantic Memory 都能按原 scope／key 讀回。
6. **Same-key replay**：相同 Runtime key 的同一 Semantic Memory `put` 重送不新增第二筆。這只證明 Store identity 層，不冒充完整模型流程冪等。
7. **Source immutability**：同 source key＋同 payload 重送不改變內容；同 source key＋不同 payload 被拒且舊值不變；更正以新 key 並存；semantic delete 無法碰到 source leaf。

不在此路徑建立 custom repository、revision table、receipt table、manifest table、outbox、Qdrant 或 embedding。

### 4.2 路徑 B：非語意 exact-scope 全量列舉（無模型）

這條路徑只服務 **JD 完成前的全面檢查**。日常訪談與 JD 編輯維持 bounded recall／按需 read，不會每回合列舉全部 Memory，也不要求把全部 Memory 塞進單一 prompt。final audit 可以分批處理，但不能依 relevance top-k，也不能把「測試某次剛好沒漏」當成完整盤點契約。

2026-09-02 重開官方資料後，可確認的成熟公開形狀是：

| 系統 | 公開 list contract | 明確完成訊號 |
| --- | --- | --- |
| OpenAI 公開 collections（Codex Memory 本身未公開 list API） | bounded `limit`＋object-ID `after` cursor | `has_more == false` |
| Anthropic Managed Agents Memory | stable server-defined order＋opaque `page／next_page`；`view=full` 是 export／sync bulk-read path | `next_page == null` |
| Google Memory Bank | `pageSize／pageToken` | response 無 `nextPageToken` |
| AWS AgentCore Memory | `maxResults／nextToken`；官方建議使用 pagination | `nextToken == null` |

跨家共同方向是 **有界 page＋server-issued continuation token＋明確 completion signal**。各家公開文件都沒有承諾跨頁 snapshot isolation；因此 final audit 期間同 scope 不發布 mutation 是本切片邊界，不是供應商保證。

官方 PostgreSQL Store 在無 `query／filter` 時使用 `ORDER BY updated_at DESC LIMIT/OFFSET`；`updated_at` 不是唯一排序鍵，也沒有 cursor 或 overflow signal。PostgreSQL 官方明示，`LIMIT/OFFSET` 只有在唯一、可預測排序下才能穩定切頁。因此原先「逐頁走到空頁」候選**不能作為 M9／Go 證據**，即使同 scope 暫停 mutation 仍不夠。

Stage 0 只比較下列成熟／最薄方向，不自行造 manifest 或 repository：

1. **可信單批上限＋overflow fail closed（isolated-spike fallback，不是大廠共識）**：以一次 exact-leaf listing 要求 `configured_spike_cap＋1` 筆；若結果不超過 cap，逐項驗證 namespace、duplicate 與 expected key set；若取得 cap＋1，回 typed overflow 並停止，不回傳「看似完整」的部分結果。它只證明明示 cap 內的 foundation，不代表 production 永遠不會超限。
2. **server cursor／token 的成熟 pager（production 共識方向）**：只有 official／pinned substrate 確實提供，而且不需改 vendor SQL 或另建 authority，才可採用。若 production 要支援 cap 以上，必須採這類 substrate 或重新選擇，不能恢復目前 offset pager。
3. **停止／重選 substrate**：前兩者都不能滿足時，本切片不得宣稱 M9 已覆蓋。

Owner 已在看完上述共識結論後正式裁決第一切片採第 1 條。必測：零筆、一筆、cap 邊界、overflow、接近相同時間寫入、更新、刪除、相鄰 JD／leaf／child namespace、restart，以及 actual key set 對 expected key set。第一切片仍不聲稱 cap 以上、snapshot isolation 或並行 writer 下的 exactly-once inventory。

### 4.3 路徑 C：Semantic writer 介面對照（極小真模型）

只比較兩個 LangMem 官方介面，不先假設哪個比較好：

#### 候選 C1：`create_memory_manager`

- 明確接收 conversation＋existing memories，回傳更新後 collection。
- 優點：無意中寫入 canonical Store 前可先驗證完整結果；候選 Memory 集合與 Context 由 Runtime 明確控制。
- 風險：Runtime 仍需一個很薄的 diff／apply seam；必須驗證 framework-generated identity、未變項目保留與 replay 邊界，不能自己重寫一個 Memory manager。啟用 delete 時，官方 core 對既有 external ID 的刪除會在 final response 保留 `RemoveDoc` tombstone；Runtime 必須把它解讀成受限 delete intent，不能把 tombstone 當成 canonical semantic content。

#### 候選 C2：`create_memory_store_manager`

- 直接搜尋 LangGraph Store、形成 mutation 並 upsert／delete。
- 優點：CRUD、search 與 persistence plumbing 較多由 framework 承接，程式較少。
- 風險：官方預設 `query_limit` 是有界相關候選，不代表看過整個 collection；官方範例也使用具 semantic index 的 Store，因此不能先假設它在本切片「不接 embedding」的邊界內仍可正確取得候選。它的實際 Store value 是 `{"kind": ..., "content": ...}` envelope，且 invoke 回傳只有 `final_puts`、不含已執行的 delete；因此空回傳不能直接推導成 `no_change`，真實結果必須以 Store before／after 與 framework side effect 一起判斷。直接 side effect 的 validation、bundle atomicity 與 crash／replay 邊界也必須實測，不能因 API 名稱是 manager 就假設全部安全。

C1／C2 先過一個**不呼叫 provider 的 contract matrix**，逐一記錄：candidate public input、framework API return、真 Store before／after、delete 表徵、no-op 表徵、physical envelope 與 identity owner。C2 另外用 retrieval spy 驗證它實際向 Store要什麼。若正確運作需要尚未核准的 semantic index、embedding、額外 retrieval model，無法讓 Runtime 約束候選範圍，或無法在不新增另一套 receipt 基礎設施的情況下可靠判讀 typed outcome，候選就在 Stage 0 淘汰；不得為了保留比較對象而擴張第一切片。候選淘汰是有效實驗結果，不會阻止另一候選繼續。

通過 Stage 0 的候選都只能在**隔離 scratch namespace**上測試，不能寫 production authority。若兩者都合格，使用同一組 fixture、相同模型、相同 instruction 與相同上限；若只有 C1 合格，就只測 C1，不湊出假的二選一。評估：

- 新增一項真正不同的工作；
- 補充同一主題而不遺失未重述細節；
- 明確更正舊內容而不是新增矛盾副本；
- 不同條件／案例並存；
- 未知與未解衝突不被擅自選邊；
- deterministic `no_change` outcome 不產生 Store mutation；自然語言 no-op 辨識不在本切片證據範圍；
- 助理未被員工支持的推測不能升格成工作事實；
- 模型沒有填 Runtime metadata。

選擇標準依序是：語意正確與細節保真、可靠發布與失敗邊界、功能覆蓋、成本／延遲，最後才是程式碼量。

## 5. Replay 與發布：先測真正邊界，不預先發明答案

### 5.1 必須區分兩種「冪等」

1. **Store identity 冪等**：相同 namespace＋key 的 `put` 是 overwrite，不會多一筆。路徑 A 可直接證明。
2. **End-to-end semantic operation 冪等**：同一員工來源／同一 durable run 因 crash 或 resume 重放時，不會因重新產生新 key 而多一筆邏輯 Memory。這不是 Store `put` 自動保證，必須另測。

### 5.2 End-to-end replay fault injection

deterministic fake 只能取代 provider 的語意輸出；它不能固定 canonical ID、不能繞過候選 public API，也不能另寫一條測試專用 apply path。Stage 1 必須以 candidate 的公開入口驅動真 PostgreSQL Store mutation，再由真 PostgreSQL Checkpointer 保存 durable task result。若候選沒有可用的公開 seam 讓 provider 輸出被固定，該候選的 contract 無法隔離驗證，不能 monkeypatch 私有內部後照樣宣稱通過。

每個 semantic writer 候選都要在下列明確邊界注入失敗：

1. candidate public call 之前；
2. 真 Store mutation 已 commit、但 `@task` 尚未保存完成結果；
3. `@task` 結果已持久化、但 entrypoint 尚未完成，接著 resume／retry。

只允許使用**同一 thread／相同 runtime config**做有界 resume；不得換 thread 重新呼叫後冒充 replay。每個 fault case 只注入一次故障，接著只做一次明確 resume；若 pinned framework 內部另有 retry，測試必須在開始前固定並記錄其上限與實際 attempt count，不能迴圈到變綠。重啟後比較 semantic-memory leaf 的 key set 與目前內容，並確認 durable task result 已保存、entrypoint 到達 terminal completion：不得多一筆、不得少一筆、不得把舊內容復活，也不得出現 Store 已收斂但 run 永遠未完成。超過預定 retry／resume budget、需要人工修復或無界重送才能收斂，立即停止。

若候選無法通過，本文**不指定自製補丁**。停止後只帶實證比較：

- LangGraph 官方 task＋應用 idempotency guidance 能否以最薄映射補足；
- Pydantic Harness PostgreSQL Memory Store 的原生 operation idempotency／CAS 是否值得作 leaf；
- 或其他同時滿足本機 PostgreSQL、exact inventory 與單一 runtime 邊界的成熟 substrate。

未經 Owner 再次裁決，不得自行加入 deterministic-key 演算法、receipt table 或第二套 agent loop。

### 5.3 多筆 mutation 原子性

Store Manager 或 core apply 一次可能產生多筆變更。第一切片必須用兩筆 mutation 的故障注入確認所選 primitive 的實際行為；在官方／pinned backend 沒有證明全成全敗前，不得宣稱 bundle atomic。

測試固定一份 initial state 與一份 intended final state，分別注入「先寫 A、B 失敗」及「先寫 B、A 失敗」兩種 partial order；每次都只走候選 public seam、預定 retry budget 與一次明確 framework resume，最後必須同時收斂到 intended final state、保存 durable task result 並完成 entrypoint，不能只因 Store 看似正確就讓未完成 run 過 Gate。

若只保證逐筆持久化，必須先證明上述 replay 最終可收斂且不遺失／重複，才能作 foundation 候選；否則停止並回來討論成熟 transaction primitive。第一切片不為此先建立自訂 transaction platform。

## 6. 驗證階段

### Stage 0：版本與 API contract canary（無模型）

目的：先證明文件所引用的 API 確實存在於要測的版本，不依 demo 或記憶猜測。

1. 確認本 repo 鎖定 `langchain==1.3.15`、`langgraph==1.2.11`、`langgraph-checkpoint-postgres==3.1.2` 與 transitive checkpoint 版本。
2. LangMem 尚未是 production dependency；隔離 spike 必須記錄實際解析到的精確版本、wheel／sdist SHA-256 與對應 source tag／commit，再核對該 artifact 的 core／Store manager signature、預設 delete、query limit、namespace template、return value 與 side effects；不能以 GitHub `main` 代替實際測試版本。
3. 建立 C1／C2 contract matrix：固定同一 input，逐項記錄 public API return 與 Store before／after，特別驗證 C1 `RemoveDoc`、C2 `kind＋content` envelope、delete 未出現在 `final_puts`，以及空回傳不能自行等同 no-op。
4. 以 pinned source／官方 contract 加 spy／fake canary 核對 Store manager 的候選讀取：是否呼叫 semantic query、是否需要 index／embedding／額外 query model，以及 Runtime 能否約束它看到的候選。需要任何未核准 retrieval dependency 就淘汰 C2，不新增該 dependency。
5. 確認 PostgreSQL Store 的 `aput／aget／adelete／asearch／alist_namespaces` 行為與官方文件相符；明確記錄一般 listing 的 `updated_at DESC＋LIMIT/OFFSET` 不具 unique total order，不能拿來通過 M9。
6. 對 Owner 選定的 final-audit exact-inventory substrate 做 contract canary；若正式核准 isolated-spike 單批 fallback，必須證明 `cap` 內完整、`cap＋1` fail closed，不能回部分結果，也不能把它描述成 cursor pagination 或 production 無界保證。
7. 確認 Store value 是 JSON-safe document，namespace／key／timestamps 由 framework／Runtime 提供。
8. 確認 structured semantic schema 只有 `topic／content`；若 LangMem 內部要求選擇既有 handle，必須只能從本輪候選中選，不能自由填 canonical identity。
9. 任一 API、預設或 failure semantics 與文件不符就停止，先更新研究，不加 wrapper 假裝一致。

Stage 0 不改 production dependency lockfile，不接 graph，不呼叫真模型。

### Stage 1：Deterministic fake effects＋真 PostgreSQL Checkpointer／Store（無 provider）

對每個通過 Stage 0 的候選，只在 provider semantic-output seam 使用 framework 可接受的 fake／stub，並經候選 public API 放進**真的最小 LangGraph durable task**；用官方 PostgreSQL Checkpointer 記錄 task／run 完成狀態、用官方 PostgreSQL Store 執行長期資料 mutation。canonical ID 與 apply path 仍走候選真實行為。只有這樣才能驗證 §5 的「Store 已寫、task 尚未完成」重播窗口，而不是測一個與 durable runtime 無關的 repository。接著驗證路徑 A、Owner 選定的路徑 B 與 §5：

- source／semantic leaf 隔離；
- source append／read／same-key collision，以及 Semantic Memory add／read／overwrite／delete／no-op；
- 同 key replay；
- candidate public call 前、Store commit 後但 task 未完成、task 完成後但 entrypoint 未完成的 end-to-end crash window；
- 兩筆 mutation 的兩種 partial order 與實際 failure boundary；
- 每個 fault case 的固定 attempt／resume budget，以及 Store final state、durable task result、entrypoint terminal completion 三者一致；
- restart；
- 可信 catalog 的 document→thread／source leaf／semantic leaf 綁定，以及 unknown document、mismatched thread、相鄰／child／foreign leaf 在 Store mutation 前 fail closed；
- Owner 選定 final-audit inventory substrate 的 exact leaf、overflow 與 expected-key-set equality；日常 bounded recall 不走此全量路徑；
- forged fake effect 嘗試未知 handle、foreign／child scope、source leaf 與 Runtime metadata 時，在 mutation 前 deterministic fail；
- typed result／failure。

Stage 1 只測 framework foundation 與 durable replay wiring，不把 fake effects 誤稱為 Memory 品質證據。若某候選無法在不呼叫 provider 的情況下經**公開 seam** deterministic 驅動，記為該候選 contract 未能隔離驗證，不可 monkeypatch 私有內部、跳過 replay 測試後仍宣稱可靠。

### Stage 2：極小 `gpt-5.6-luna` 對照 smoke

只在 Stage 0／1 的 Store 基礎綠燈後執行：

- 模型：Owner 指定的 `gpt-5.6-luna`；reasoning `medium`；provider 與實際回傳 model ID 均記錄。
- 資料：短小、匿名、繁中職務訪談 fixture；不使用真員工資料。
- 候選：只測通過 Stage 0／1 的候選；每個候選最多兩次 **Luna provider invocation 總數**，包含任何 framework repair／retry。兩個都合格時總計最多四次，只有一個時總計最多兩次；只要任一候選需要第三次 provider invocation，該候選立即記失敗並停止。
- 呼叫前先經候選的 public seam，以 deterministic provider output 建立一筆代表較早訪談回合的詳細目前 Memory；不得直接寫底層 table。該內容包含後續回合故意不再重述的頻率、低頻例外、協作對象與最終責任邊界。
- 第一個 call 代表後續訪談回合：只提供同主題補充、一個不同案例、一項與其他主題無關且仍缺答案的 independent unknown，以及與既有頻率互斥但尚未釐清的新說法；故意不重述上述既有細節。通過時必須保留未受影響細節與 independent unknown，且不依 recency 自動選掉衝突。
- 接著關閉 candidate、Runtime client 與其 Store connection，從同一 PostgreSQL、JD scope 與 thread 建立全新 client；不得把先前 Python 物件、Memory list 或快取重新注入。第二個 call 中員工只釐清衝突的正確說法，仍不重述其他舊細節。通過時目前 Memory 必須採用已釐清答案、保留其餘細節、不同案例與仍未知項，而且不得新增重複邏輯 Memory。
- 必須經 public seam 保存四份 canonical snapshot：`seed 後`、`call 1 後`、`fresh client 冷讀後／call 2 前`、`call 2 後`。call 1 後就必須無重複、保留全部 sentinel 細節、同時呈現互斥說法與 independent unknown；冷讀 snapshot 必須與 call 1 後完全相等；不能等 call 2 才修掉中間錯誤後只驗最終結果。
- Stage 1 只用預定的 `no_change` effect 驗證 typed outcome／apply wiring 不產生 mutation；它不能證明模型會把寒暄、改寫或無新工作資訊辨識成 no-op。自然語言 no-op 辨識列為本切片未證明，不占用真模型 call。
- 不另給 framework repair／retry 額外 call budget。若第一次 invocation 觸發文件化 repair／retry，它會耗掉第二次也是最後一次 quota；跨輪案例因而無法完成，候選即記失敗並停止，不自建無界 retry。
- 分開記錄 input／output／reasoning tokens、cache hit、tool calls、延遲、成本、實際 mutation 與失敗原因。

這只是三個邏輯回合（deterministic seed＋兩次真模型 call）的短跨輪 continuity／wiring smoke，不是完整 eval，也不能證明所有職務、數月長訪談或 JD 品質。

### Stage 3：形成選擇證據，不接 production

輸出一份小型實驗報告：

1. pinned framework contracts 實際通過／失敗項；
2. exact inventory 可宣稱到什麼邊界；
3. replay／多筆發布真正的 failure window；
4. 每個通過 Stage 0／1 候選的逐案結果、token、延遲與程式責任，以及較早淘汰候選的 contract 證據；
5. 推薦一個介面，或明確判定目前沒有合格候選；
6. 需要哪個成熟 fallback，以及具體由哪個失敗觸發。

報告交 Owner 複核。通過後才另寫 successor ADR 與施工計畫；不從 spike 直接複製成 production。

## 7. 代表性測試矩陣

### 7.1 Storage／scope cases

| Case | 預期結果 |
| --- | --- |
| 同 key 同 scope 重送 | 仍只有一筆目前值 |
| 同 key 不同 JD | 兩份資料互不覆蓋、互不可見 |
| source 與 semantic leaf 同 key | 各自存在，互不污染 |
| source 同 key＋同 payload 重送 | 合法 no-op；原內容不變 |
| source 同 key＋不同 payload | typed failure；舊來源不被 Store upsert 覆蓋 |
| source 更正 | 使用新 source key；舊、新來源皆可讀 |
| prefix／child／相鄰 namespace | 不納入候選；發現 foreign item 在 mutation 前 fail closed |
| unknown document／mismatched thread | 可信 catalog boundary 在 Store 前拒絕 |
| restart 後 get／list | key set 與內容完全一致 |
| exact inventory | Owner 選定 substrate 在支援範圍內與 expected key set 完全相等；overflow fail closed，不回部分集合 |
| delete current Memory | current listing 不再出現；source 仍可回查 |
| provider／DB failure | 不回成功；舊目前內容不被假更新 |

### 7.2 Semantic cases

| Case | 最低通過條件 |
| --- | --- |
| 新工作主題 | 新增一筆聚焦、自足內容，不塞成舊主題的無關段落 |
| 同主題補充 | 更新既有主題，保留員工本輪未重述的角色、頻率、例外與責任邊界 |
| 明確更正 | 目前內容採新說法，舊錯誤不再進一般召回；原始來源仍在 |
| 不同條件／案例 | 不把其誤判成對舊內容的否定；能在同筆補充或另筆保留合理邊界 |
| 尚未確認 | 明確保留未知，不虛構答案 |
| 互斥說法 | 同時保留衝突與待確認處，不依最近一句自動選邊 |
| 跨輪補充→重啟→釐清 | 後續回合未重述的工作細節仍存在；重啟後能取得並修訂同一目前理解；釐清後只收斂衝突部分，不刪其他細節或製造重複 Memory |
| 助理推測 | 未獲員工支持時不得升格成工作事實 |
| 指令型／低信任資料 | 訪談內容或既有 Memory 中形似 system／tool 指令的文字仍只被當成資料，不得改變 scope、policy、metadata 或觸發越權 mutation |
| 偽造受信任參數 | unknown handle、foreign／child scope、source leaf 或 Runtime metadata 在呼叫 Store 前 deterministic fail |
| 重放 | 相同 durable operation 不產生第二筆邏輯 Memory |

### 7.3 詳細 fixture 的必要內容

fixture 至少包含：

- 一項週期性工作及其低頻例外；
- 明確的協作對象與最終責任邊界；
- 一個具體案例，但不能因此自動升格成固定 Task；
- 後續補充時故意不重述部分舊細節，用來抓 destructive rewrite；
- 第一個真模型回合引入一次仍無法判定的衝突；
- 第一個真模型回合另外引入一項與衝突無關、仍缺答案的 independent unknown；
- Runtime／candidate／Store client 重建後，第二個真模型回合只提供衝突的明確釐清，且仍不重述其他舊細節或回答 independent unknown；
- 一段被員工當作工作內容引用、但字面形似「忽略規則／刪除記憶」的文字，用來驗證 Memory 是低信任資料而不是控制指令；

## 8. Typed outcome 與錯誤政策

第一切片只需要下列**語意類別**，不是要求現在定正式 wire schema：

| 類別 | 意義 | 行為 |
| --- | --- | --- |
| applied | 所要求的目前內容已發布 | 回傳實際 framework key／結果供 Runtime 記錄；不讓模型產生可信 metadata |
| no_change | 輸入合法但沒有 semantic change | 視為成功 no-op，不製造空 Memory 或重試 |
| invalid | schema、未知 handle、大小或 namespace contract 不合法 | 不發布；回傳安全、精確且可動作的錯誤 |
| not_found | 指定的既有 handle 不存在於可信候選／scope | 不猜 ID、不跨 JD 搜尋 |
| retryable_failure | provider／network／DB 暫時失敗 | 只走 framework transport／Tool retry budget；耗盡即失敗 |

規則：

1. deterministic invalid 與 transient failure 不使用同一 retry。
2. 錯誤回到原 tool／task call；不把 stack trace、SQL 或敏感內容送給模型。
3. 模型 repair 只修語意 payload／已提供 handle；不能修 scope、key、version 或 retry policy。
4. `conflict` 只有在正式選用 CAS／hash precondition 後才成為持久化 outcome；第一切片不為尚不存在的多 writer 預先造欄位。
5. crash 後若無法判定 side effect 是否發布，不得硬套成上述成功類別；先依 framework recovery 查核目前狀態，不能盲目重送。
6. framework API return 不是唯一事實來源：尤其 C2 空 `final_puts` 可能同時代表 no-op 或只發生 delete；typed outcome 必須由 contract matrix 證明的 return＋Store before／after 組合判讀。

## 9. M1～M11 的誠實覆蓋

| 能力 | 第一切片能證明 | 第一切片仍不能證明 |
| --- | --- | --- |
| M1 長期連續性 | PostgreSQL source／Memory 重啟後仍存在；deterministic seed＋兩次真模型 call 的短跨輪修訂；Checkpointer／Store 責任分開 | 真實長時間、多月訪談 |
| M2 細節保真 | rich content fixture；跨輪補充／衝突／釐清時未重述細節保留 smoke | 所有職務與所有模型的品質 |
| M3 廣度完整性 | 本切片只證明 source append 與 semantic operation 的 typed outcome wiring；不建立 per-source extraction receipt，也不宣稱每則來源已被語意吸收 | admission prompt 對所有真實來源永不漏抽，以及每則來源的 durable extraction outcome |
| M4 可修訂目前理解 | current add／overwrite／delete primitive；semantic supplement／correction | 正式 retire／merge／split policy與 history UX |
| M5 未知／衝突 | 指定短跨輪 fixture 中，independent unknown 與 conflict→clarification 未被壓平，且釐清一項不會順帶虛構另一項答案 | 其他未知／衝突形狀，以及長訪談下的穩定召回與澄清品質 |
| M6 語意關係 | 單筆 rich content 內保留條件、例外、協作與責任 | 跨 record 關係是否需要額外 projection |
| M7 案例與穩定工作 | 同一 collection 可保留工作主題與重要案例，不建第二 authority | 大量案例下的抽象品質 |
| M8 日常有界召回 | Store／LangMem 有 search/read seam；只有 C2 通過 Stage 0 時才觀察 Store manager 的 bounded query 行為 | 正式 lexical／semantic ranking、budget 與主顧問 Tool；C2 若在 canary 淘汰，不能宣稱已驗證其召回行為 |
| M9 可驗證完整盤點 | 只在 JD 完成前 final audit 啟用；只有 Owner 選定且 Stage 0／1 通過的 exact-inventory substrate 可在其明示邊界內成立；日常 JD 編輯維持 bounded recall；`updated_at＋offset` 不算 | 超出可信單批 cap（若採該方案）、snapshot-grade 並行盤點與完整 JD batch workflow |
| M10 原始來源回查 | source leaf 與 semantic leaf 分層，同一 scope 的來源可列舉並按 ID 讀回 | 是否需要更細 per-memory supporting evidence |
| M11 單一 JD 隔離 | Runtime namespace＋真 PostgreSQL isolation tests | production 所有入口是否都強制同一隔離規則；本切片不接 production |

Stage 0～2 全綠只表示「Memory foundation 候選值得進下一階段」，不等於完整 Memory 已完成，更不等於已能產出滿分 JD。

## 10. Go／stop 判準

### 10.1 Go 必須全部成立

1. Checkpointer／Store 責任沒有再被混回同一份完整 Semantic Memory。
2. 真 PostgreSQL Store 的 persistence、restart 與 per-JD isolation 通過。
3. Owner 已選定 exact-inventory substrate，且在零／一／邊界／overflow、更新、刪除、相鄰 scope 與 restart cases 無缺、無重、無 foreign item；overflow 不回部分結果。
4. 同 key replay 通過，且 end-to-end crash window 有明確證據；不得只驗 happy path。
5. 所選 LangMem 介面在指定 deterministic／短跨輪 fixture 中沒有在補充時刪掉未重述細節，也沒有把不同案例、independent unknown 或衝突錯誤壓平；不得外推成所有輸入的全稱保證。
6. 模型沒有被要求產生 scope、canonical identity、version、timestamp、source UUID、Skill ID 或 retry metadata。
7. 只使用一套 agent runtime 與一個 canonical Memory Store；沒有雙寫、第二 authority 或相容舊層。
8. 所有未覆蓋能力都在 §9 誠實標示，不以 demo 綠燈冒充 production 保證。
9. Store manager 沒有暗中引入未核准的 embedding／semantic index／額外 retrieval model；若有，已在 Stage 0 淘汰而不是擴張範圍。
10. source append-only collision、可信 catalog scope binding、public-seam fake boundary，以及三個 replay injection points 都有 deterministic 證據。
11. 指令型低信任 fixture 沒有造成未受員工語意支持的新增／覆寫／刪除，也沒有把資料文字升格成 scope、policy 或 Runtime 指令。
12. 短跨輪 smoke 的四份 canonical snapshot 全部通過：client 重建後冷讀等於 call 1 後狀態；補充、未解衝突與後續釐清只改應改部分，舊細節、不同案例與 independent unknown 仍完整存在。

### 10.2 任一成立就停止

- Store 跨 scope、restart 後遺失，或 exact inventory 出現漏／重／partial-as-complete；
- source 同 key＋不同 payload 覆蓋舊原話；
- semantic writer 在 crash／resume 後產生重複邏輯 Memory；
- 多筆發布出現無法恢復的半完成狀態；
- 補充／更正會刪掉本輪未重述的重要細節；
- generic consolidation 自動選掉未解衝突；
- client／Runtime 重建後取不到先前目前 Memory，或釐清衝突時連帶刪除未受影響細節、留下互斥 current truth、產生重複邏輯 Memory；
- 任何候選需要第三次 Luna provider invocation，或四個 snapshot 任一出現暫時重複、細節遺失、cold-read 不一致、unknown 被擅自補答案；
- 指令型低信任內容造成沒有員工語意依據的 mutation，或改變 scope、policy、metadata；
- 需要為了讓測試變綠而自建 revision／receipt／manifest／RAG／第二 runtime；
- LangMem pinned API 與官方文件不符，且只能依賴未文件化內部行為。
- 候選只能靠 monkeypatch 私有內部才能注入 deterministic provider output 或觀察必要 side effect。

停止後要帶具體 failing case、framework contract 與替代候選回來討論，不在同一 task 擴張範圍。

## 11. 明確不做

- 不改 production graph、authority、JD、訪談 UI、審核或匯出；
- 不接 Reference／公版 RAG、Qdrant、embedding、reranker 或外部 corpus；
- 不做跨 JD／跨員工 Memory；
- 不做 knowledge graph、episodic engine、case store 或第二份工作理解；
- 不做每輪固定第二個模型、multi-agent 或背景 worker；
- 不做完整 eval 平台；只做 deterministic contracts 與極小 live smoke；
- 不預建 immutable revision、CAS、receipt、inventory manifest、outbox 或自訂 repository；
- 不先做小型導覽、正式日常召回、Memory Tool UI 或完整 Memory→JD audit；
- 不讓 Memory manager 自行決定或修改 JD；
- 不把 `topic＋content` 宣稱為 OpenAI／Anthropic 共同 schema。

## 12. 完成物與下一個決策點

本切片完成後只應存在：

1. 一組隔離的 contract／spike tests；
2. 一份極小真模型 smoke 記錄；
3. 一份 framework 行為與失敗報告；
4. 一個經證據選出的 Semantic writer 介面，或「目前兩者皆不合格」的明確結論；
5. 一份需要 Owner 裁決的 fallback 清單。

Owner 核准報告後，才依序：

```text
successor ADR（正式改變 Checkpoint／Store authority）
  → implementation plan
  → isolated worktree production implementation
  → 每一小段回看產品目的與 M1～M11
  → 日常 bounded recall／按需 read 設計
  → complete Memory→JD audit 設計
```

如果 Store／LangMem foundation 不通過，就回到 framework selection；不能因已寫 spike 而保留較差方向。

## 13. 官方來源與證據邊界

### 13.1 OpenAI

- [Codex 本機 Memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)：支持 eligible conversation 與 generated Memory 分層、背景更新、summaries／durable entries／recent inputs／supporting evidence，以及 extraction／consolidation model 分離；**未公開**可供本產品直接照搬的 Store schema、CAS 或 exact inventory API。
- [OpenAI List container files](https://developers.openai.com/api/reference/cli/resources/containers/subresources/files/methods/list)：不是 Codex Memory API；只用來佐證 OpenAI 公開 collection API 採 object-ID cursor、bounded limit 與 `has_more`，不反推內部 Memory 實作。
- [Agents SDK Sessions](https://openai.github.io/openai-agents-python/sessions/)：支持 durable conversation 與有界 history input；不是 Semantic Memory CRUD substrate。
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)：支持 strict schema、由 code 提供已知參數及縮小 model-facing Tool payload。

### 13.2 Anthropic

- [Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)：支持 many small focused text documents、直接 read／edit、immutable versions 與可選 optimistic hash；它是 beta managed service，不是本機 PostgreSQL 實作。
- [Anthropic List memories](https://platform.claude.com/docs/en/api/beta/memory_stores/memories/list)：stable server-defined order、opaque `next_page`、明確 null completion，以及 export／sync 用 `view=full` bulk-read path。
- [Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)：支持 client-side storage、JIT read、CRUD、call-correlated error，以及 compaction 與 Memory 分工；實際 storage／validation 仍由應用負責。

### 13.3 Google／AWS Memory listing

- [Google Memory Bank `ListMemories`](https://cloud.google.com/vertex-ai/docs/reference/rest/v1beta1/projects.locations.reasoningEngines.memories/list)：bounded `pageSize`、`pageToken` 與 `nextPageToken`。
- [AWS AgentCore `ListMemoryRecords`](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListMemoryRecords.html)：bounded `maxResults`、`nextToken`，且官方建議 pagination；null token 表示結束。

### 13.4 LangChain／LangGraph／LangMem

- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：Checkpointer 保存 thread graph state；Store 保存 application-defined long-term data；也明示長 conversation checkpoints 會持續成長。
- [LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores)：PostgreSQL Store、namespace、CRUD、semantic search、無 query/filter listing、limit／offset、prefix 與 backend ordering 邊界。
- [LangGraph Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)：durable task replay 與 side effect idempotency guidance；不等於 Store 自帶 operation token。
- [LangMem Core Concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)：collection／profile、conversation＋current Memory 的 extraction／consolidation、hot path／background 與 application-specific instructions。
- [LangMem Memory API](https://langchain-ai.github.io/langmem/reference/memory/)：`create_memory_manager` 與 `create_memory_store_manager` 的正式介面、Store manager 預設 `query_limit=5`、相關候選取回與 Store side effects；官方範例使用具 embedding index 的 Store，因此第一切片必須先驗證 C2 的 retrieval dependency，不能自行推定。
- [LangMem `extraction.py` source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)：補足 API reference 未寫清楚的 candidate contract 風險；core final response 可保留 external-ID `RemoveDoc`，Store manager 實際寫 `kind＋content` envelope、執行 put／delete 後只回 `final_puts`。Stage 0 必須以實際 pinned artifact 再驗證，不能直接把 `main` 當測試版本。
- [PyPI `langmem`](https://pypi.org/project/langmem/)：記錄實際發行 artifact 與 SHA-256；spike 必須鎖定所測 wheel／sdist，避免文件與 source 漂移。

### 13.5 PostgreSQL

- [PostgreSQL — LIMIT and OFFSET](https://www.postgresql.org/docs/current/queries-limit.html)：`LIMIT/OFFSET` 必須有唯一、可預測的排序才能穩定分頁；PostgreSQL Store 只按非唯一 `updated_at DESC` 排序，因此該 offset 路徑不能作 exact-inventory Go 證據。

### 13.6 正式備選

- [Pydantic AI Harness Memory](https://pydantic.dev/docs/ai/harness/memory/)：支持 Runtime-owned namespace、bounded notebook、PostgreSQL CAS 與 durable idempotency；但仍是 0.x，且公開 list API 未直接提供 M9 所需 iterate-all contract，因此只在 LangGraph Store contract 實際失敗後重開比較。

### 13.7 本 repo 研究回讀

- [`Framework-independent Memory Contract`](./2026-09-01-framework-independent-memory-contract.md)：最終效果與 M1～M11。
- [`Memory 實作機制與成熟框架共識稽核`](./2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md)：F1／R1／I1／V1／P1／D1 分級與 Checkpointer 候選否決。
- [`完整列舉、版本、來源與最小切片重驗`](./2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)：Store listing、CAS、replay、lineage 與條件式強化邊界。
- [`Memory／顧問 Runtime 框架選擇複核`](./2026-09-02-memory-framework-selection-revalidation.md)：LangGraph／LangChain 首選、Harness 備選與 deferred retrieval。
- [`Memory mapping §9.47～§9.48`](./2026-08-30-caliburn-memory-requirements-mapping-working-research.md)：Checkpoint／Store 分工與 A+ 單筆 Memory 邏輯表徵。

## 14. Design review 結論

本重寫版不再把「一份 JD 只有一個 thread」當成把完整長期 Memory 塞進 Checkpointer 的理由。它採目前官方責任分層最一致的 Store-first 方向，又保留三條誠實停止線：

1. 大廠公開共識是 bounded pages＋server cursor／token＋明確完成訊號；LangGraph PostgreSQL Store 的 `updated_at DESC＋offset` 已被證明缺少 unique total order，不能再作全量盤點候選。Owner 已正式同意 isolated spike 採 cap＋overflow fail closed，但它只是明示邊界內的 fallback，不是 production 決策；
2. Store same-key overwrite 不等於整條 LLM／workflow 已冪等，必須做 crash-window replay test；
3. LangMem 是成熟方向但仍為 pre-1.0 leaf；core／Store manager 必須先以精確 artifact 通過 input／return／Store-before-after contract matrix，合格者才用同一 fixture 實測，而不是依 API 名稱選擇、把 tombstone 當內容、把空 return 當 no-op，或為 C2 偷接 retrieval infrastructure。

這個切片的成功標準不是「寫出一套新的 Memory 平台」，而是以最少 production 承諾取得足夠證據，知道哪些成熟 framework primitive 真的能承接 Caliburn 為製作完整 JD 所需要的 Memory 能力，以及哪一個缺口仍需要下一次 Owner 決策。
