# OpenAI Codex Memory progressive disclosure 深入查證

Status: focused evidence child；不形成 production 決策、不授權施工  
Topic: `LLM-Q014 / G4.3b`  
Checked: 2026-09-04

> 2026-09-05 接續：讀取順序的研究保留；「摘要位置由誰建立、怎麼成為 Memory 的相關引用、框架回傳什麼」見 [Q017 摘要路由 source review](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)。該稿已重新取得固定 Codex source 並核對最新 main 三檔內容相同。最新接法／待決以 [current decisions](../current-decisions.md) 為準，不從本稿歷史候選自動選型。

## 0. 本稿回答什麼

本稿只回答一個窄問題：OpenAI 公開的 Codex／Sandbox Agent Memory，實際如何完成：

```text
小型 Memory 摘要
  → 搜尋 Memory 索引
  → 開少量 rollout summary
  → 需要精確內容時才深入原始對話
```

這裡必須分開三種證據：

1. **產品／SDK 公開契約**：OpenAI Developers 與 ChatGPT Learn 文件明確承諾的行為。
2. **目前 open-source harness 實作快照**：`openai/codex` `main` 分支目前的 README、prompt 與 source layout；可解釋「怎麼做」，但不是永遠不變的 API 契約。
3. **對 Caliburn 的推論**：只能作為 G4.3b 候選依據，不得冒充 OpenAI 官方要求。

## 1. 先給精確結論

原本的四步描述大致正確，但少了「Memory 怎麼生成」與「conversation state 是另一層」。完整形狀是：

```text
canonical conversation / rollout JSONL
        │
        ├─ Phase 1：每個已閒置 rollout 個別抽取
        │      ├─ detailed raw_memory
        │      └─ detailed rollout_summary
        │
        └─ Phase 2：跨 rollout 整併
               ├─ memory_summary.md   極小、每次注入、只負責導覽
               ├─ MEMORY.md           可文字搜尋的 durable handbook
               └─ rollout_summaries/  單次 rollout 的詳細橋接層

下一個 agent run：
memory_summary.md 已在 prompt
        ↓
模型取出相關關鍵詞
        ↓
以 Shell／文字搜尋 MEMORY.md
        ↓
MEMORY.md 若直接指向細節，才開 1～2 份 rollout summary／Skill
        ↓
仍需精確命令、錯誤或佐證時，才搜尋 rollout_path 的原始 JSONL
```

關鍵校正：

- 公開路徑中的「索引」是可 `grep` 的 `MEMORY.md`，**不是已公開的向量資料庫或 embedding pipeline**。
- 這不是固定的 `search_memory` Provider API。模型使用 Shell／Filesystem 能力，在 prompt 指引下搜尋與開檔。
- `rollout_summary` 不是原始對話，也不是最上層 Memory；它是保留單次工作的細節、證據與脈絡，讓多數情況不必回開 JSONL 的中間層。
- conversation／Session 保存訊息歷史；Agent Memory 保存跨 run 可重用的提煉資訊。OpenAI 官方明確把兩者分開。

## 2. 四層資料各自做什麼

| 層 | 實際 artifact | 是否每輪直接送模型 | 用途 | 詳細度／權威邊界 |
|---|---|---:|---|---|
| 對話層 | `sessions/<rollout-id>.jsonl` 或 `rollout_path` | 否；近期 conversation 另由 Session／Responses 延續 | 原始訊息、Tool call、Tool result、turn 邊界 | 最精確的執行記錄；append-only evidence |
| 單次工作橋接層 | `rollout_summaries/<rollout-id>_<slug>.md` | 否 | 保留一次 rollout 的目的、結果、證據、失敗與細節 | 比 durable Memory 更完整；仍是模型整理後內容 |
| Durable handbook | `MEMORY.md` | 否；按需文字搜尋 | 將多個相關 rollout 整併成可重用的 task group、偏好、程序、失敗防線 | 比 summary 詳細、比 rollout summary 更去重與泛化 |
| Prompt 路由層 | `memory_summary.md` | 是 | 提供使用者輪廓、穩定偏好、主題與關鍵詞，告訴模型去哪裡找 | 極小、去重、不可放完整 runbook 或 provenance |

`raw_memories.md` 是 Phase 1 輸出機械合併後、供 Phase 2 整併的工作輸入；它不是一般 read path 的最終查詢介面。

## 3. 寫入：Memory 不是每次聊天後立刻 CRUD

### 3.1 何時觸發

OpenAI 的本機 Codex 文件說 Memory 在背景更新，不會每次 chat 結束就立即完成；系統會等 session 閒置，並可能在剩餘 rate limit 太低時跳過。現行 Codex open-source harness 更具體地要求：root session、非 ephemeral、Memory feature 開啟、不是 sub-agent，且 state DB 可用，才啟動背景 pipeline。

目前公開 config defaults 包含：

- rollout 至少閒置 6 小時才可抽取；
- 每次 startup 最多處理 16 個 rollout candidate；
- rollout 最多回看 30 天；
- Phase 2 最多保留 256 份 raw memory 供 consolidation；
- 30 天未使用的 Memory 預設不再符合 consolidation selection；
- rate-limit 剩餘低於 25% 時可不啟動生成。

這些是**目前 Codex 產品的成本／清理預設**，不是所有 Memory 系統都必須照抄的通用規則。

### 3.2 Phase 1：per-rollout extraction

每個 eligible rollout 會個別送進 extraction model。輸出是一個嚴格的小型 JSON：

```json
{
  "rollout_summary": "...",
  "rollout_slug": "...",
  "raw_memory": "..."
}
```

其 prompt 的重要規則：

- 原始 rollout 是 immutable evidence，不可改寫。
- 只根據 rollout evidence，不可補造；secret 要遮罩。
- 沒有能讓未來 agent 做得更好的 durable signal 時，三欄全空，允許 no-op。
- 使用者訊息與明確修正，優先級高於 assistant 自己的提議。
- `rollout_summary` 可相當完整，保留結論如何形成、成功／失敗／不確定狀態，以及具體 evidence。
- `raw_memory` 是日後整併所需的結構化工作素材，不是原始逐字稿。

多個 rollout 可平行抽取；state DB 會 claim／lease job 以避免重複工作，失敗則 backoff，而不是立即熱迴圈重試。

### 3.3 Phase 2：global consolidation

Phase 2 取得單一 global lock，選出一批 Phase 1 結果，先同步：

- `raw_memories.md`
- `rollout_summaries/*.md`
- 一份與上次成功結果比較的 git-style workspace diff

沒有差異就直接成功，不呼叫 consolidation model。有差異才啟動一個受限的 consolidation sub-agent；它不能連網、不能再委派，只能修改本地 Memory workspace。

Consolidation agent：

1. 先看 workspace diff，辨認新增、修改與刪除的來源。
2. 將新資訊路由到既有 `MEMORY.md` task group，必要時才建立新 group。
3. 有衝突、重複或證據不足時，才開相應 `rollout_summaries`。
4. 只移除已失去來源支持的內容，不因一部分來源消失就刪掉整個仍有支持的 block。
5. 最後才重建／更新 `memory_summary.md`，讓它反映整併後的 Memory。

Phase 2 的 prompt 明確要求不要直接打開 raw sessions。換句話說：**寫入／整併時也採 progressive disclosure**；先處理已抽取的材料，只有 read path 最後需要精確證據時才碰原始 rollout。

## 4. 讀取：每一步到底發生什麼

### 4.1 第 0 層：目前 conversation 不是 Agent Memory

OpenAI Responses 可用 Conversation 或 `previous_response_id` 延續對話；所有先前 input token 仍會計費，context 太長時可用 compaction。Compaction 產生的是 opaque continuation state，用來延續模型上下文；它不是可搜尋的 durable Memory，也不取代原始 conversation 保存。

### 4.2 第 1 層：自動注入 `memory_summary.md`

run 開始時，SDK／harness 將 `memory_summary.md` 放進 prompt。Read prompt 明確告訴模型「已經提供，不要再開一次」。

它不是所有 Memory 的摘要，而是高密度導覽，內容包含：

- 穩定的 user profile／工作偏好；
- 少量跨 task 的一般性提示；
- `MEMORY.md` 中有哪些主題，以及可搜尋的具辨識力關鍵詞。

它刻意不放詳細 provenance、完整 runbook 或 task-local 細節，以降低每輪固定 token。

### 4.3 第 2 層：模型自己從任務與 summary 取關鍵詞

沒有一個公開的固定 query classifier 或 embedding retriever。Read prompt 要模型：

1. 看目前使用者要求；
2. skim 已注入的 summary；
3. 抽出與本輪相關的 repo、module、錯誤字串、Tool／API 名稱、使用者偏好等關鍵詞；
4. 用這些詞搜尋 `MEMORY.md`。

因此這一層的 routing 是「LLM 判斷＋普通文字搜尋」，不是一個獨立 retrieval model 的公開契約。

### 4.4 第 3 層：搜尋 `MEMORY.md`

`MEMORY.md` 的格式就是為文字搜尋設計：

- 每個 block 有 `Task Group` 與短 `scope`；
- 每個 task 先列 `rollout_summary_files`；
- 再列 discriminative `keywords`；
- 後面才是 user preferences、reusable knowledge、failures／next-time guidance。

模型透過 Shell 搜尋檔案。官方 prompt 沒把它限定成某一條命令，但公開說法就是 search／grep，不是 vector search。搜尋命中後，很多問題可直接由 `MEMORY.md` 回答，因為每個 block 被要求能自成一體，且比最上層 summary 具體。

### 4.5 第 4 層：只開 1～2 份 rollout summary

只有當 `MEMORY.md` 直接指向某份 rollout summary，且本輪真的需要更多背景，才打開最相關的 1～2 份。這一層用來補：

- 當時使用者真正要什麼；
- 方案怎麼演變；
- 哪些內容已驗證、只是提議，或曾被否決；
- 具體錯誤、Tool 輸出與使用者修正；
- `MEMORY.md` 整併時被壓掉、但本輪又需要的 nuance。

它的設計目標就是讓未來 agent 通常不必重開原始 rollout。

### 4.6 第 5 層：最後才深入原始 conversation rollout

如果前四層仍無法回答，而且本輪需要**精確命令、逐字錯誤或精確 evidence**，模型才沿 `rollout_path` 搜尋 append-only JSONL。

公開 read prompt 說明 JSONL 中至少可見：

- `session_meta.payload.id`：session／rollout identity；
- `turn_context`：turn 邊界；
- `event_msg`：輕量狀態事件；
- `response_item`：真實訊息、Tool call 與 Tool result。

搜尋策略是優先使用 rollout summary filename suffix 或 `session_meta.payload.id` 定位；除非必要，不做所有 rollout 的全文廣掃。

### 4.7 停止規則與成本界線

現行 read prompt 要求：

- quick memory pass 理想上控制在 4～6 個 search step；
- 不掃描所有 rollout summary；
- 沒有相關命中就停止查 Memory，回到正常工作；
- Memory 可能過時；容易即時驗證且可能漂移的事要重新驗證。

這不是「保證只呼叫模型 4～6 次」。多數搜尋是同一 agent run 裡的 Tool step；成本主要是 tool round trip、讀入的檔案 token，以及背景 extraction／consolidation model call。

## 5. 為什麼不直接把全部對話放進 prompt

OpenAI 公開架構同時保留 conversation 與 distilled Memory，目的不同：

- conversation 保留發生過什麼；
- rollout summary 保留一次工作的完整可讀脈絡；
- `MEMORY.md` 保留跨工作可重用、去重後的知識；
- `memory_summary.md` 只付每輪固定 routing token。

因此，它不是用 Memory 取代 conversation，而是把「每輪必讀」與「必要才讀」拆開。Responses 文件也明確提醒：即使用 `previous_response_id`，鏈上先前 input tokens 仍會計費；長上下文還受 context window 與 latency 約束。

## 6. 哪些是公開事實，哪些不能誤稱

| 判斷 | 狀態 |
|---|---|
| Session／conversation 與 distilled agent memory 分層 | OpenAI 官方明確文件 |
| `memory_summary.md → MEMORY.md → rollout summary` progressive disclosure | OpenAI 官方 SDK 文件 |
| 最後可沿 rollout path 深讀 append-only JSONL | Codex 官方開源 harness 的目前 prompt／實作 |
| `MEMORY.md` 以關鍵詞／Shell 搜尋 | 官方 SDK 文件＋官方開源 prompt |
| 這條路徑使用向量資料庫／embedding | **沒有公開證據，不能聲稱** |
| 固定存在 `search_semantic_memory(query)` Provider Tool | **沒有；這是其他 framework／application 可做的介面** |
| 這套 retention 預設可保證永不遺失所有 domain detail | **不能；Codex 有 signal gate、時間／數量上限與 stale pruning** |
| 任何 Agent 都應照抄 6h／30d／256 等數字 | **不能；這些是產品預設，不是通用定理** |

## 7. 對 Caliburn G4.3b 的可用證據與限制

這份查證支持以下效果方向：

1. 每輪只放極小 routing context，按需逐層展開，是 OpenAI 實際採用的成熟 pattern。
2. Semantic Memory 與 canonical conversation 應分層；深讀原話是 fallback，不是每輪預設。
3. 中間的詳細 derived artifact 可以降低重開原始對話的頻率。
4. 來源 locator 應由 Runtime／storage 產生；模型只沿已看到的 pointer 查找，不應猜 ID。

但它**不能直接替 G4.3b 裁決**：

- OpenAI Codex 用檔案＋Shell，LangMem 原生是 search-first Tool，介面並不相同。
- Codex 面對多個 coding rollout；Caliburn 第一版是一份 JD 對應一條 canonical 長訪談。是否值得另存 rollout-summary 層，仍需用 Caliburn 的成本與找回需求判斷。
- Codex 的 durable-memory signal gate 與過期／未使用清理，不能直接套到「所有員工工作細節都必須可找回」的產品要求。
- OpenAI 的 read path 只能證明 A3「小型導覽＋全文 handbook search＋必要時深讀」是成熟形狀；不能證明 Caliburn 必須複製它的檔名、Markdown schema 或 retention policy。

因此，本稿不改變目前 blocking question：第一版應採 A1 LangMem search-first、A2 list/read，或 A3 小型導覽＋full-search hybrid。它只把 A3 的 OpenAI 實際機制與限制查清楚。

## 8. 直接來源

### OpenAI 公開產品／SDK文件

- [OpenAI Developers — Sandbox Agents：Session 與 Memory 分層、progressive disclosure、檔案 layout 與寫入流程](https://developers.openai.com/api/docs/guides/agents/sandboxes)
- [ChatGPT Learn — Codex local memories：背景生成、storage、chat-level controls 與模型設定](https://learn.chatgpt.com/docs/customization/memories)
- [ChatGPT Learn — Config reference：Memory selection／retention／rate-limit defaults](https://learn.chatgpt.com/docs/config-file/config-reference)
- [OpenAI Developers — Conversation state：Conversation／`previous_response_id`、保存與 token 邊界](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI Developers — Compaction：opaque continuation state 與 context window 管理](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI Developers — Codex as a platform：open-source harness 的責任邊界](https://developers.openai.com/blog/codex-as-a-platform)

### OpenAI 官方開源實作快照

- [`openai/codex` — Memory pipeline README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)
- [`openai/codex` — Read-path prompt](https://github.com/openai/codex/blob/main/codex-rs/ext/memories/templates/memories/read_path.md)
- [`openai/codex` — Phase 1 extraction prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/stage_one_system.md)
- [`openai/codex` — Phase 2 consolidation prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)

### 主張對應表

| 本稿主張 | 直接依據 |
|---|---|
| conversation／Session 與 agent Memory 是不同層 | Sandbox Agents「Persist memory across runs」 |
| `memory_summary.md → MEMORY.md → rollout summary` | Sandbox Agents 的 progressive-disclosure 說明 |
| 背景更新、閒置與 rate-limit gate | Codex local memories＋Config reference |
| Phase 1／Phase 2、claim／lease、global lock、workspace diff | `openai/codex` Memory pipeline README |
| 模型選關鍵詞、搜尋 handbook、只開 1～2 份 summary、最後才讀 JSONL | `openai/codex` Read-path prompt |
| 三種 artifact 的精確內容與 incremental consolidation | `openai/codex` Phase 1／Phase 2 prompts |
| `previous_response_id` 仍計入既有 input tokens | Conversation state |
| compaction 是 opaque continuation，而非可搜尋 Memory | Compaction guide |

## 9. Stop rule

本稿已回答 OpenAI 路徑「實際怎麼做」。下一步若要推進 production，應回到
[`2026-09-04-llm-machine-effects-and-sibling-results-working-design.md`](2026-09-04-llm-machine-effects-and-sibling-results-working-design.md)
的 G4.3b，逐一比較 A1／A2／A3；不得把本稿直接當成 Caliburn schema 或施工授權。
