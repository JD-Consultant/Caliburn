# OpenAI 對話、Context、Compaction 與 Memory 系統地圖

Status: focused official evidence；不形成 Caliburn production 決策、不授權施工  
Topic: `LLM-Q014 / G4.3b` evidence preflight  
Checked: 2026-09-05

> 後續來源／映射複核見[通用流程審核](2026-09-05-generic-memory-flow-framework-crosswalk-audit.md)。
> OpenAI SDK／Codex CLI 的 artifact 與觸發政策分別看待，不拼成跨產品固定契約。

## 0. 本稿的問題與邊界

本稿先只還原 OpenAI 公開的完整概念，不先套入 Caliburn，也不替
`LLM-Q014 / G4.3b` 選 read topology。它回答：

1. 同一段長對話如何延續；
2. 對話太長時如何管理 context window；
3. Codex／Sandbox Memory 如何從一段或多段對話產生；
4. 新的一輪模型呼叫到底會看到哪些 context；
5. API background mode、背景 Memory 生成與跨對話 Memory 有何不同；
6. 哪些是官方直接公開，哪些只是合理推論，哪些仍未知。

本稿使用以下標記：

- **Official fact**：OpenAI 官方文件直接公開；
- **Inference**：由官方事實推得，但不是 OpenAI 的逐字產品承諾；
- **Unknown**：公開資料不足，不能自行補造。

不處理：Caliburn schema、LangMem Tool 欄位、JD Tool、production migration、
embedding／RAG 選型或任何施工。

## 1. 一句話結論

OpenAI 並沒有一個包辦一切的「Memory」。公開系統至少分成七種責任：

```text
目前這一輪的控制規則       instructions／tools／output contract
同一對話的逐輪延續         Conversation／previous_response_id／SDK Session
超長同一對話               Compaction
可跨 run／跨對話重用的理解  Codex local Memory／Sandbox Memory
長期專案真相               Project files／AGENTS.md／workspace
本輪按需取得的資料          file search／web／shell／custom tools
效能優化                   Prompt caching
```

它們可同時存在，但不能互相冒充：

- Conversation 是歷史，不是 distilled Memory；
- Compaction 是同一工作脈絡的壓縮延續，不是可搜尋知識庫；
- Memory 是從先前工作提煉、供未來 run 取用的輔助層，不取代 conversation；
- Project／workspace 是外部真相來源，不是模型記憶；
- Prompt caching 只省延遲／費用，不會讓模型多記得事情；
- API background mode 只讓**一個 Response 非同步執行**，不是 Memory pipeline。

## 2. 名詞地圖

| 名稱 | 保存什麼 | 主要範圍 | 如何進入模型 | 不等於什麼 |
|---|---|---|---|---|
| Response | 一次模型呼叫的 input／output items | 單次呼叫 | 當輪直接使用；可由 ID 接續 | 長期 Semantic Memory |
| Conversation | message、Tool call、Tool result 等 items | 一條長期對話 | 傳 `conversation` 後，由 API 把既有 items 放到新 input 前 | 跨對話知識整理 |
| `previous_response_id` | 一串 Response 的 lineage | 一條 response chain | API 依前一個 Response 接續 | 免費或無上限 context |
| SDK Session | SDK 管理的訊息歷史 | 一段 agent conversation | Runner／SDK 帶回後續 turn | Sandbox workspace 或 durable lesson |
| Compaction | 先前 state／reasoning 的 opaque 精簡 continuation | 同一長對話 | 作為後續 canonical context window 的一部分 | 可讀摘要、原始逐字稿、Memory 搜尋索引 |
| Sandbox session／workspace | 檔案、執行環境、snapshot state | 一個工作環境 | Agent 透過 filesystem／shell 按需讀 | conversation identity |
| Codex／Sandbox Memory | 從先前工作提煉的可重用內容 | 未來 run；可跨對話 | 小 summary 自動注入，再按需 search／open | 當前 conversation history |
| Project context | 共用檔案、專案指示、來源 | 同一 project 的多個 chats | 指示可套用；檔案／來源可按需讀 | 使用者個人 Memory |
| Prompt cache | 相同 prompt prefix 的運算快取 | 多次相似 requests | 服務端自動重用相同 prefix | durable state 或 semantic recall |
| Background response | 非同步執行中的一個 Response | 單次長工作 | 完成後 poll／stream 取得 | 背景 extraction／consolidation |

## 3. 同一段對話如何延續

### 3.1 Conversation object

**Official fact**：Conversations API 與 Responses API 可建立有 durable ID 的
長期 conversation；可跨 session、device 或 job 繼續使用。Conversation 保存
message、Tool call、Tool result 與其他 items。把 `conversation` ID 傳給下一個
Response 時，既有 items 會放在本輪 input items 前，本輪 input／output 完成後也會
自動加入該 Conversation。

Conversation items 不受一般 Response object 的 30 天 TTL 限制。這是「歷史保存」與
「後續模型 context」的 API primitive，不是自動抽取出的 Semantic Memory。

### 3.2 `previous_response_id`

**Official fact**：另一種延續方法是每輪傳 `previous_response_id`，形成 threaded
response chain。這讓應用不必手動重傳每個先前 item，但所有先前 input tokens 仍會
列入後續呼叫的 input 計費。

**重要細節**：前一個 Response 的 `instructions` 不會因為
`previous_response_id` 自動沿用。需要持續生效的 developer／system contract，應由
應用在新 Response 再提供，或使用穩定的 prompt configuration。

Conversation ID 與 `previous_response_id` 是兩種延續方式；API 不允許在同一 request
同時使用兩者。

### 3.3 Agents SDK Session

**Official fact**：Sandbox Agents 文件明確把 SDK-managed Session 定位為保存
message history；Sandbox Memory 則是把先前 workspace runs 提煉成未來可重用的
lesson。多輪 sandbox chat 應使用穩定 SDK Session，並持續使用同一 live sandbox
session。

**Inference**：所以「目前這一段聊天記得上一句」首先依靠 conversation／Session，
不應等待背景 Memory 生成。

## 4. 同一對話很長時：Compaction

**Official fact**：context window 同時計入 input、output 與 reasoning tokens。
Conversation／response chain 會成長，因此 OpenAI 提供兩種 compaction：

1. **Server-side compaction**：在 Response request 設 `context_management` 與
   `compact_threshold`；到門檻時由服務自動壓縮；
2. **Standalone `/responses/compact`**：應用送入完整 context window，服務回傳新的
   canonical compacted window。

回傳的 compaction item：

- 是 encrypted、opaque；
- 帶回後續工作需要的關鍵 prior state 與 reasoning；
- 不應由應用解析；
- standalone 版本的整份輸出應原樣作為下一輪 context，不能自行再裁切。

**Inference**：Compaction 適合維持「接下來怎麼繼續工作」，但公開契約沒有保證它是
逐字、可搜尋或永不遺漏每個歷史細節的 evidence store。需要精確原句時，仍應回到
保存的 conversation items，而不是解析 opaque compaction。

## 5. Codex／Sandbox Memory 的完整寫入流程

### 5.1 不是每一輪立刻產生

**Official fact**：Codex local Memory 會從符合條件的舊對話擷取實用 context；它會
略過仍進行中或過短的 session，等 conversation 閒置後在背景處理，也可能因剩餘
rate limit 太低而跳過。`generate_memories` 與 `use_memories` 是分開的控制項。

### 5.2 同一對話與多對話都會參與，但角色不同

Sandbox Agents 公開了兩段式形狀：

```text
同一 logical conversation 的多個 run segments
        ↓ 依 conversation／SDK session identity 分組
Phase 1：抽取 conversation summary＋raw memories
        ↓
多個 eligible conversations 的 Phase 1 結果
        ↓
Phase 2：consolidate
        ↓
MEMORY.md＋memory_summary.md＋rollout summaries
```

**Official fact**：run 分組 identity 的優先序是 explicit conversation ID、SDK session
ID、run group ID，最後才是 per-run generated ID。Sandbox session ID 代表 workspace，
不是 Memory conversation ID。

因此：

- **同一對話內**：多個 turns／run segments 可先被視為同一 conversation，Phase 1
  從這段對話抽取 summary 與 raw memories；
- **跨多段對話**：Phase 2 再把多個 Phase 1 結果整併成未來可共用的 durable Memory；
- **正在進行的對話**：仍由 Session／Conversation 即時延續，不依賴這個背景流程。

### 5.3 未來 run 如何讀

**Official fact**：Sandbox Memory 採 progressive disclosure：

1. run 開始先注入 `memory_summary.md`；
2. 過去工作可能相關時，agent 搜尋 `MEMORY.md`；
3. 只有需要更多細節時，才開相關 rollout summaries；
4. 公開的本機 Codex Memory 目錄同時保存 summary、durable items、recent inputs 與
   supporting evidence。

Memory read 預設需要 Shell；live Memory update 預設需要 Filesystem，讓 agent 可在
使用者要求時修復 stale Memory。這個 live update 與 session 結束後的自動背景生成是
兩條不同路徑。

更細的 Phase 1／Phase 2、文字搜尋與 rollout deep-read 已在
[`2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md`](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)
逐段查證，本稿不重複複製。

### 5.4 校正：「Session、raw session、rollout summary、durable Memory、supporting evidence」不是五個同級層

這五個詞可以幫助理解，但若直接稱為「五層」會漏掉中間產物，也會把不同性質的
東西誤畫成同級資料庫。依 OpenAI 目前公開契約，較精確的 artifact／責任地圖是：

| Artifact／責任 | 公開形狀 | 由誰產生 | 主要用途 | 關鍵邊界 |
|---|---|---|---|---|
| Conversational Session | SDK-managed Session／Conversation items | Runtime 在互動時持續加入 message、Tool call、Tool result | 讓目前長對話立即接續 | 是對話延續，不是 distilled Memory |
| Raw rollout／session record | `sessions/<rollout-id>.jsonl` | Runtime 在 sandbox session 期間 append run segments | 保存一段實際執行的底層記錄，供後續 Memory 生成與必要核實 | 不是 SDK Session 本身；sandbox session ID 也不是 Memory conversation ID |
| Per-rollout summary | `memories/rollout_summaries/*.md` | Phase 1 extraction | 保留單段 eligible conversation／rollout 的可讀脈絡與較完整細節 | 是 derived summary，不是逐字原始對話 |
| Extracted raw-memory candidates | Sandbox 已公開 `raw_memories/<rollout-id>.md` 及 `raw_memories.md`；固定 Codex 快照用 Stage 1 DB record＋`raw_memories.md` | Phase 1 extraction | 把單段 rollout 中值得跨 run 保留的訊號交給 Phase 2 | 是 consolidation 輸入，不是一般 read path 的最終 Memory |
| Consolidated durable Memory | `MEMORY.md` | Phase 2 consolidation | 跨 rollout 去重、整併後的可重用知識；未來 run 按需搜尋 | 比 rollout summary 更泛化；不取代 canonical conversation |
| Routing projection | `memory_summary.md` | Phase 2 consolidation | 每輪先注入一小份導覽，讓模型判斷是否及去哪裡搜尋 | 是小型導航，不是完整 Memory 摘要或 evidence store |
| Supporting evidence | 官方對 Memory storage 內容的**角色描述** | 來自先前 chats／rollouts 的佐證材料 | 讓 Memory 可被追查、核實或修補 | 官方產品文件未宣告一個獨立 `evidence` artifact，也未公開每筆 durable Memory 的固定 reference schema |

**同日覆蓋審核校正：**上表候選檔名依[artifact §1.1 已核對的 Sandbox layout](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md#11-兩個-openai-公開實作不能混成一套檔案契約)同步；移除殘留「未定義逐檔命名」，不重新推測 SDK／CLI 共用實作，也不改選本案格式。

因此，`supporting evidence` 應畫成跨越 Memory 與來源材料的關係，而不是第七個平行
資料層。OpenAI 公開目錄顯示 rollout summaries 與 raw session records 是可供深讀的
材料；Codex local Memory 文件則只承諾 storage 中包含 prior chats 的 supporting
evidence。**公開產品契約沒有進一步保證每一個 `MEMORY.md` block 如何精確連回哪一則
message**；那是實作快照可觀察、但不能冒充長期 API 契約的部分。

把三條交互流程攤開後如下：

```text
即時對話延續
新訊息 → Conversational Session／Conversation items → 模型本輪 context

背景 Memory 生成
Runtime append raw rollout
  → Phase 1：rollout summary ＋ raw-memory candidates
  → Phase 2：MEMORY.md ＋ memory_summary.md

未來 run 的 progressive disclosure
memory_summary.md（自動注入）
  → 搜尋 MEMORY.md
  → 必要時開 rollout summary
  → 需要精確事實時才回到更底層 conversation／raw rollout
```

這也說明為何 OpenAI 不只留一份摘要：每個 artifact 分別最佳化「即時連續性」、
「逐段保真脈絡」、「跨段去重知識」、「低成本 routing」與「必要時核實」。把它們
合成一份會迫使每輪重讀太多內容；只留 consolidated Memory 又會失去逐段 nuance 與
精確來源。

### 5.5 第一個細部邊界：三種容易混淆的 Session

OpenAI 文件在不同 API／runtime 中重複使用 `session` 一詞。下列三者必須分開；其中
`raw session` 並不是官方固定 API 名稱，本稿後續統一稱為 **raw rollout record**：

| 概念 | Identity／公開形狀 | 保存內容 | 何時使用 | 不負責什麼 |
|---|---|---|---|---|
| Conversation／SDK conversational Session | Conversation ID／SDK Session identity | message history；Conversation items 可包含 messages、Tool calls、Tool outputs 與其他 response items | 下一個互動 turn 立即延續；不等待背景 Memory | 不負責把多段工作去重、泛化成 durable lessons |
| Sandbox session state | live provider session 或 serialized state | 可恢復的執行環境狀態；可和 snapshot／workspace artifacts 搭配 | 暫停後恢復同一 sandbox execution environment | 不是 conversation identity，也不是 Memory conversation ID |
| Raw rollout record | `sessions/<rollout-id>.jsonl` | Runtime 在 sandbox session 期間 append 的 run segments；目前官方開源實作快照可見 identity、turn boundary、狀態事件、真實 message／Tool call／Tool result | 背景 extraction 的來源；必要時核實 rollout 的精確執行內容 | 不會自動成為每輪 prompt，也不是 consolidation 後的 current Memory |

官方目前能直接確定的生命週期是：

```text
互動期間
Conversation／SDK Session 立即延續 message history
                ＋
Runtime 將 run segments append 至 raw rollout record

sandbox session 關閉後
raw rollout record
  → extraction：conversation／rollout summary ＋ raw-memory candidates
  → consolidation：MEMORY.md ＋ memory_summary.md
```

所以 Conversation 與 raw rollout **確實可能保存重疊的 message／Tool activity**，但不是
兩個同義副本：

1. Conversation／SDK Session 是線上 continuity surface，下一輪模型立即使用；
2. raw rollout 是 Memory pipeline 的離線來源 artifact，讓 extraction 不必依賴一個仍
   存活的模型 conversation context；
3. sandbox session state 恢復的是工作環境，與前兩者又是不同責任。

耐久性也不能混為一談：Conversation API object 有自己的 durable ID，官方說可跨
session、device、job 使用；sandbox session 能否恢復取決於 provider state／snapshot；
raw rollout 與 Memory files 若要跨 run 保留，則必須保存相同 memory directories、從
session state／snapshot 恢復，或掛載 persistent storage。換句話說，`sessions/*.jsonl`
出現在 workspace 不等於 OpenAI 服務永遠替應用保存它。

另一項重要官方細節是：Memory 將多個 run segment 依 explicit conversation ID、SDK
Session ID、run group ID，最後才依 generated per-run ID 分組；sandbox session ID 只標識
live workspace，不是 Memory conversation ID。因此「一個 rollout 檔」與「使用者認知的
一整段 conversation」不應僅靠檔名直覺畫等號。

**公開邊界：**官方產品契約沒有完整公布 `sessions/*.jsonl` 的永久 schema、retention
保證或逐欄相容性；更細的 `session_meta`／`turn_context`／`event_msg`／`response_item`
只屬目前官方開源 harness 的實作快照。設計其他產品時可以學其責任分層，但不能把這些
欄名當成 OpenAI 長期 API 契約。

直接依據：[Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)、
[Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)、
[Codex local memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)。

### 5.6 第二個細部邊界：Phase 1 為何同時產生 rollout summary 與 raw-memory candidates

#### 官方直接公開的契約

OpenAI Sandbox Agents 明確公開：sandbox session 關閉後，Memory generation **先抽取
conversation summaries 與 raw memories，再將 raw memories consolidation 成
`MEMORY.md` 與 `memory_summary.md`**。Codex 設定也分別暴露「每個 thread 的
`extract_model`」與「全域 `consolidation_model`」。因此「逐 thread 擷取」與「跨
thread 整併」是公開分工，不是本稿自行替一個摘要流程拆名詞。

但官方產品契約沒有承諾 Phase 1 永遠採用某個 JSON schema。下面的精確欄位只屬目前
OpenAI 官方開源 harness 的實作快照：

```json
{
  "rollout_summary": "...",
  "rollout_slug": "...",
  "raw_memory": "..."
}
```

#### 兩份 derived artifact 的責任不同

| Artifact | 主要問題 | 內容傾向 | 後續讀者 | 不是什麼 |
|---|---|---|---|---|
| `rollout_summary` | 「這一段工作發生了什麼，結論如何形成？」 | 目標、演變、成功／失敗、尚未確定之處、具體錯誤、使用者修正及足以理解本段工作的脈絡 | Phase 2 在候選有衝突／不清楚時；未來 agent 需要更多細節時 | 不是逐字 transcript，也不是全域 current Memory |
| `raw_memory` candidate | 「這一段工作有哪些訊號值得跨 run 保留？」 | 可重用偏好、經驗、程序、結論、失敗防線等待整併素材 | Phase 2 consolidation | 不是原始對話，也不是未經整併即可直接注入未來 run 的最終 Memory |
| `rollout_slug` | 「這份 summary 用什麼短名稱定位？」 | 一個供檔名／導覽使用的短 routing label | Runtime／filesystem read path | 不是 truth identity 或來源證據本身 |

白話說，`rollout_summary` 是**來源導向的工作脈絡**；`raw_memory` 是**目的導向的
Memory 候選**。它們都由模型根據 raw rollout 產生，所以都可能出錯；真正需要精確
核實時仍須回到底層 conversation／raw rollout。

#### 為何不只留其中一份

只留 rollout summary：Phase 2 每次都要再從較長敘事重新判斷哪些訊號值得保存，會
增加 token、重複抽取與漂移。

只留 raw-memory candidate：Phase 2 或未來 agent 遇到衝突時缺少「當時如何得出此
結論」的完整脈絡，容易把條件差異誤當重複、或把 tentative 建議誤當已確認事實。

兩者並存：平常 Phase 2 先讀較精煉的 candidates；只有 ambiguous、conflicting 或
需要更多細節時才開 rollout summary。這使**寫入路徑本身也採 progressive
disclosure**，而不是每次 consolidation 都重讀全部 raw conversations。

#### 成本與 no-op 邊界

Codex 不在每一個互動 turn 執行 Phase 1。官方產品文件說它略過仍進行中或過短的
threads，等待閒置後背景處理，並可因 rate-limit 門檻跳過。官方設定另限制每次處理的
rollout candidates 與可供 consolidation 的近期 raw memories 數量。

目前開源 extraction prompt 也允許「沒有值得保留的 durable signal」時三欄皆空，
因此一段對話可以正常產生 no-op，而不是為了填 Memory 強行發明內容。這是降低 Memory
膨脹的重要措施；但具體 eligibility、閒置小時與數量上限是 Codex 產品預設，不是其他
產品必須照抄的定理。

#### Supporting evidence 在這一層的位置

rollout summary 可作為低成本的 supporting context／bridge，但它仍是模型生成的
derived artifact；不能冒充逐字 evidence。OpenAI 公開資料支持「Memory storage 包含
prior chats 的 supporting evidence」以及「需要更多細節才開 rollout summary」，但
沒有公開一個跨版本保證的 per-candidate evidence pointer schema。因此可確定的是
**分層核實能力**，不能聲稱官方固定要求每個 candidate 填某組 message IDs。

直接依據：[Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)、
[Codex local memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)、
[Codex config reference](https://learn.chatgpt.com/zh-Hant/docs/config-file/config-reference)。

### 5.7 第三個細部邊界：Phase 2 如何形成 durable Memory

#### 官方直接公開的契約

OpenAI 目前明確公開的是一個**兩階段背景生成**契約：逐 thread／conversation 的
extraction 先產生 conversation summary 與 raw-memory candidates，之後才由獨立的
global consolidation 將候選整併為 `MEMORY.md` 與 `memory_summary.md`。Codex 也分開暴露
`extract_model` 與 `consolidation_model`，所以 Phase 2 不是 Phase 1 的另一個名稱。

這條路徑不是每回合立即執行。產品會略過仍在進行或過短的 thread，等待閒置後在背景
處理，也可因 rate-limit 門檻暫時跳過。現行設定另限制每次 startup 的 rollout candidates、
rollout 年齡與可供 global consolidation 的近期 raw memories 數量。這些限制證明 Phase 2
是**有界批次工作**，不是每次重讀無限歷史；但 `6h`、`30d`、`256` 等值只是 Codex
目前的產品預設，不是通用 Memory 定理。

#### 官方開源 harness 的目前實作快照

更細的增量行為來自 OpenAI 官方開源 harness 的目前 README／prompt，而非已承諾長期
相容的產品 API。其可觀察流程是：

```text
一批符合資格的 Phase 1 結果
  ＋既有 Memory workspace
  → 同步 raw_memories.md、rollout_summaries 與本批 selection
  → 計算相對上次成功狀態的 workspace diff
      ├─ 無差異：直接 no-op，不呼叫 consolidation model
      └─ 有差異：在單一 global lock 下啟動受限 consolidation agent
          → 先讀 diff，辨識新增／變更／消失的來源素材
          → 優先將新資訊整併進既有 MEMORY.md group
          → 只有確有新主題時才建立新 group
          → 重複、衝突或證據不足時才深讀相關 rollout summary
          → 保守更新 MEMORY.md
          → 最後重建 memory_summary.md
```

`global lock` 在這個快照中提供 single-writer 邊界，避免兩個 consolidation 同時改同一份
generated Memory workspace；它不是「全公司共用一份 Memory」的產品語意。
目前已核實的 Codex 快照以 DB `selected_for_phase2`／`selected_for_phase2_source_updated_at`
保存選取基準，另產生 workspace diff；**不能在這個 Codex 快照中主張使用 `phase_two_selection.json`**。
2026-09-05 定向回查的 [Sandbox SDK 官方頁](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)
則明列該檔，故先前「目前來源皆不支持」的表達過廣，改為區分產品。詳見[artifact §1.1 校正](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md#11-兩個-openai-公開實作不能混成一套檔案契約)。
這些是批次／增量 bookkeeping，不是另一份語意記憶，也不替 Caliburn 核准同名檔案。

#### 候選如何處理：可以確認到哪一層

| 候選情況 | 目前開源 consolidation 行為 | 不應過度宣稱 |
|---|---|---|
| 沒有新差異 | no-op，不花 consolidation model call | 不代表永遠不需維護；只代表這一批沒有 delta |
| 同主題的新資訊 | 優先補進既有 `MEMORY.md` group | 官方沒有固定 `update_memory` API 或永久欄位 schema |
| 新且可獨立搜尋的主題 | 必要時新增 group | 不是每一個 raw candidate 固定新增一筆 Memory |
| 明顯重複 | 在既有 group 中整併，避免平行複本 | 公開產品契約未保證某個 deterministic dedupe algorithm |
| 看似衝突、條件不同或證據不足 | 先開相關 rollout summaries 取得較完整脈絡，再決定如何整理 | 沒有公開一條「一律以最新／信心分數／語氣較強者勝出」規則 |
| 一部分來源素材消失 | 只移除失去支持的內容；仍有其他來源支持的 block 不整塊刪除 | `max_unused_days` 是 consolidation eligibility，不等同語意事實自動刪除 |

因此，可把 create／enrich／merge／correct／prune 當成理解 Phase 2 行為的動詞，但不能把
它們冒充 OpenAI 對外承諾的 typed CRUD protocol。尤其「retire」不是公開固定 status；
目前可確認的是 generated file 內容會被保守改寫，而不是每筆 Memory 都有正式生命週期欄位。

#### 為何 `memory_summary.md` 必須最後更新

`memory_summary.md` 是未來每次 run 先付出的 routing context；`MEMORY.md` 才是較完整、
按需搜尋的 durable handbook。若先更新導覽、後更新正文，agent 可能被指向尚不存在、已
改名或已失效的內容。因此目前 consolidation prompt 先完成 `MEMORY.md`，最後才讓
`memory_summary.md` 反映新的 current state。這是一份**可重建投影**與正文的關係，不是
兩份各自可獨立編輯的 truth。

#### 成本、保真與公開限制

- 成本控制來自 eligibility gate、有界 candidate batch、無 diff 即 no-op，以及只有歧義時
  才深讀 rollout summaries；不是靠每次重讀所有 raw conversations。
- 保真來自保留 rollout summaries／raw rollout 作較深核實層，而不是假設 consolidated
  Memory 永遠完整無誤。
- OpenAI 公開文件沒有保證每一筆 durable Memory 都有固定 message ID／evidence pointer
  schema，也沒有保證 Codex 的 retention policy 能保存任意產品要求的全部 domain detail。
- 目前公開資料也不足以把 consolidation 的自然語言判斷描述成 deterministic verifier；
  它仍是模型驅動的 generated state maintenance。

所以這一節能確定的是**責任形狀**：有界增量整併、歧義時逐層深讀、保守移除、導覽最後
重建。精確 Markdown 欄位、prompt、lock／diff 實作與 retention 數字都只能視為目前
Codex／open-source harness 的實作選擇，不能直接當成其他產品的固定 schema。

直接依據：[Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)、
[Codex local memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)、
[Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference)。開源實作
快照的逐檔依據與 commit-sensitive 邊界，見
[`2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md`](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)
§3.3、§6、§8。

### 5.8 第四個細部邊界：三份 read artifact 各自存什麼，何時停止深入

#### 官方直接公開的讀取契約

OpenAI Sandbox Agents 明確公開三段 progressive disclosure：run 開始時由 SDK 注入
`memory_summary.md`；過去工作可能相關時，由 agent 搜尋 `MEMORY.md`；只有需要更多細節
時，才開 rollout summaries。官方同時說 Memory storage 包含 summaries、durable entries、
recent inputs 與 prior chats 的 supporting evidence。

因此，前三列責任可由官方產品／SDK 文件直接確定；最後一列的 raw rollout fallback 則只
屬目前官方開源 read prompt 的實作快照：

| Artifact | 每輪預設進 Context？ | 應回答的問題 | 不應承擔的責任 |
|---|---:|---|---|
| `memory_summary.md` | 是 | 「有哪些可能相關的記憶主題？該用哪些詞往下找？」 | 不是所有 Memory 的短版，不保存完整細節或完整 provenance |
| `MEMORY.md` | 否，相關時搜尋 | 「過去已整理出哪些可重用的目前知識？」 | 不是原始 transcript，也不應每輪全量注入 |
| rollout summary | 否，指向且需要脈絡時才開 | 「那一次工作如何演變、驗證、失敗或被修正？」 | 不是逐字來源，也不是跨 rollout 去重後的 current truth |
| raw rollout／conversation（開源快照） | 否，最後 fallback | 「當時精確說了、呼叫了或回傳了什麼？」 | 不是日常 routing layer，也不是每輪預設 prompt |

#### 官方開源 harness 的目前內容形狀

下面的內容規則屬目前 OpenAI 官方開源 prompt 快照，不是永久 Markdown schema。

`memory_summary.md` 偏向 **high-signal-per-token 的導覽**：

- 少量穩定 user profile／工作偏好；
- 少量跨 task 的通用提示；
- `MEMORY.md` 現有哪些主題，以及可辨識、可搜尋的關鍵詞；
- 不複製完整 runbook、task-local 細節或詳細來源脈絡。

`MEMORY.md` 偏向 **可文字搜尋、可獨立重用的 durable handbook**：

- 以相關 task groups／scope 組織，而不是照 conversation 時序堆疊；
- 每個 task／block 可列相關 `rollout_summary_files` 與 discriminative keywords；
- 正文保留可重用的偏好、已知邊界、觸發條件、決策點、成功方法、失敗防線及不確定結果；
- 每個命中 block 應盡量自成一體，使多數問題停在這一層即可回答。

rollout summary 偏向 **單次工作的詳細橋接內容**：保留當時目標、方案演變、已驗證與僅
提議內容、錯誤／Tool 結果、使用者修正和必要 nuance。它比 consolidated Memory 更接近
來源脈絡，但仍是模型產生的 derived summary；要求逐字精確時仍須回到 raw rollout／
canonical conversation。

上述 `Task Group`、`scope`、`rollout_summary_files` 與 `keywords` 是 Codex coding／sandbox
domain 的目前檔案設計；可證明「讓內容可搜尋、自足並能往下定位」是實際做法，不能據此
宣稱所有產品都應照抄同名欄位。

#### 一次 future run 的實際 read path

```text
run 開始
  → memory_summary.md 已注入，不再重讀一次
  → 模型從本輪任務＋導覽取出具辨識力的關鍵詞
  → 以 Shell／普通文字搜尋 MEMORY.md
      ├─ 沒有相關命中：停止 Memory lookup，回到正常工作
      ├─ 命中內容已足夠：直接使用，停止深入
      └─ 命中內容指向 summary 且仍缺脈絡：只開最相關的 1～2 份 rollout summary
          ├─ 已足夠：停止深入
          └─ 仍需精確原句、命令、錯誤或 Tool 結果：才定位 raw rollout／conversation
```

目前公開 read prompt 的 quick pass 理想上落在約 `4～6` 個 search steps；這是產品 prompt
中的 lookup budget／停止提示，不是 API 保證，也不是呼叫模型 `4～6` 次。多個搜尋與開檔
通常是同一個 agent run 裡的 Tool steps。

#### 搜尋技術與停止規則的精確邊界

- 公開的 OpenAI 路徑是「模型依本輪問題選詞＋Shell／文字搜尋」，沒有公開 embedding
  model、vector database、固定 query classifier 或 `search_memory` Provider API。
- 搜尋不到相關內容時應停止，而不是遍歷全部 summaries；否則 progressive disclosure
  失去成本意義。
- `MEMORY.md` 已能回答時不再深讀；rollout summary 只是補脈絡，raw rollout 只處理精確
  evidence。這是依**資訊需求**停止，不是固定讀滿所有層。
- Memory 可能過時；容易即時驗證且可能漂移的外部事實應重新驗證，而不是因出現在 Memory
  就當成永久正確。
- `memory_summary.md` 可以重建且只作 routing；它若含有 `MEMORY.md`／下層 artifact 找不到的
  獨有事實，就會從導覽偷偷升格成第二份 truth，偏離目前公開責任形狀。

#### 尚未由 OpenAI 公開保證的部分

OpenAI 沒有對外承諾：

1. `memory_summary.md`／`MEMORY.md` 的永久欄位與 Markdown heading；
2. 每個 durable block 固定如何連到 canonical message IDs；
3. 一定使用 lexical、vector 或 hybrid retrieval 的跨產品標準；目前 Codex 公開路徑只證實
   lexical／filesystem search；
4. rollout summary 一定保留所有原始細節；它仍可能摘要遺失；
5. `4～6` search steps 或只開 `1～2` 份 summary 適用所有產品與資料規模。

所以，這一節能學習的是**先導航、再搜自足知識、再讀少量脈絡、最後核實原始來源**的
分層與停止原則；不能把目前 Codex 的檔名、欄位或數字直接升格成通用 schema。

直接依據：[Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)、
[Codex local memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)。目前開源
read prompt／檔案格式與原始 rollout fallback 的逐檔依據，見
[`2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md`](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)
§2、§4、§6、§8。

## 6. 三種「背景」必須分開

| 名稱 | 觸發 | 處理什麼 | 結果給誰 | 是否讓目前對話記得前文 |
|---|---|---|---|---:|
| Responses API `background: true` | 應用建立一個長 Response | 同一次模型工作非同步跑完，可 poll／恢復 stream | 當次 Response caller | 否；它不是 Memory |
| Codex local Memory background generation | chat 閒置且符合資格 | 對舊 conversation extraction，再 consolidation | 未來 eligible chats／runs | 否；目前對話靠 conversation state |
| Sandbox live Memory update | agent run 中、具 filesystem 能力 | 修正／更新 Memory files | 後續同 workspace／持久 storage runs | 可讓後續 run 使用，但不是 conversation transcript |

這解決先前最容易混淆的問題：OpenAI 說「background」時，可能指的是完全不同的
生命週期；不能看到同一個字就當成同一個功能。

## 7. 一輪模型呼叫的 Context 到底由什麼組成

### 7.1 官方公開的 context 來源

| Context 來源 | 誰提供／選擇 | 是否自動 | 典型內容 | 是否每輪應全量放入 |
|---|---|---:|---|---:|
| Developer／system instructions | 應用 | 否；每個 Response 明確提供 | 目標、規則、權限、成功條件 | 是，但應短且穩定 |
| Tool definitions | 應用／Tool Search | 一般由應用提供；可 deferred load | 可用能力、參數與副作用 | 大 catalog 不宜全量 |
| Output schema | 應用以 Structured Outputs 提供 | 否 | 當輪 machine-readable output contract | 只在需要時 |
| Conversation items | Conversation API／SDK Session | 使用 Conversation／Session 時自動 | 訊息、Tool calls、Tool results | 受 context window／compaction 管理 |
| Previous response chain | Responses API | 傳 ID 後由服務接續 | 先前 Responses state | 不等於免費；仍計 input tokens |
| Compaction window | Responses context management | 達門檻時可自動 | opaque continuation state＋部分 retained items | 只用 canonical 回傳結果 |
| `memory_summary.md` | Sandbox Memory SDK | Memory 開啟時自動注入 | 過去 Memory 的小型導航 | 是，小型且固定 |
| Memory 詳情 | Agent 透過 shell／filesystem | 否，按需 | `MEMORY.md`／rollout summary | 否 |
| Project instructions／files | Project／workspace／使用者 | 指示可共享；檔案通常按需 | `AGENTS.md`、文件、原始碼、上傳來源 | 不應全部塞入 |
| 本輪 attachments／選取內容 | 使用者／UI | 當輪附加 | 圖片、檔案、選取文字 | 只限本輪需要 |
| Tool results／retrieved data | Agent＋Tool runtime | Tool call 後加入 loop | 搜尋結果、檔案片段、API 資料 | 只回相關且有界內容 |
| 最新 user message | 使用者 | 是 | 當前要求、更正、回答 | 是 |

### 7.2 OpenAI API 沒有一個通用「自動 Context Engine」

**Official fact**：Responses／Conversations／Compaction／Prompt Caching／Tools 各自提供
primitive；Sandbox Agent harness 另外負責注入 Memory summary 與提供按需檔案讀取。

**Inference**：對任意產品而言，應用仍需定義：

- 哪些規則是每輪固定 contract；
- 哪一條 conversation 要接續；
- 何時 compact；
- 哪些 project／Memory／domain data 只暴露搜尋能力；
- Tool 回傳多少資料；
- 當輪 output contract 是什麼。

框架可以執行這些責任，但不會自動知道某個產品的 domain context 哪些最重要。

### 7.3 官方支持的組裝原則，而非宣稱隱藏 prompt 順序

OpenAI Prompt Caching 與最新模型指引支持以下**應用層組裝原則**：

```text
穩定前綴
  ├─ 短而穩定的 developer／system contract
  ├─ 穩定 Tool definitions（大型 catalog 改 deferred Tool Search）
  └─ 真正共用且穩定的 reference／instructions

延續狀態
  └─ Conversation／previous response／canonical compacted window

小型導航
  └─ Memory summary／可用資料的索引提示

動態後綴
  ├─ 本輪直接附加資料
  ├─ 最新 user message
  └─ 本輪狀態、限制或輸出需求

Agent loop 中按需追加
  └─ Memory／project／file／web／custom Tool results
```

理由：

- stable content 放前面、dynamic content 放後面，才能提高 prompt-cache prefix 命中；
- 新 message／Tool result 盡量 append，不反覆重寫舊 prefix；
- 大型 Tool catalog 用 Tool Search／deferred loading，只載入相關 subset；
- 長對話用 compaction 降低 context，而不是把所有歷史無限制重送；
- Memory／檔案細節採 progressive disclosure，而不是預先全塞；
- output schema 應走 Structured Outputs，不要在自然語言 prompt 重複貼一次 schema。

**Unknown**：OpenAI 沒有公開 ChatGPT／Codex 完整 hidden prompt 的精確 serialization
順序，也沒有承諾每個產品 surface 使用完全相同的 assembler。上圖是官方 API 契約與
官方最佳實務可支持的 application-level arrangement，不冒充內部機密實作。

## 8. 同一對話、跨對話與專案共享：該用哪一層

| 情境 | OpenAI 公開對應層 | 是否需要背景 Memory |
|---|---|---:|
| 使用者下一句接續上一句 | Conversation／`previous_response_id`／SDK Session | 否 |
| 同一對話跨數小時或重開裝置 | durable Conversation／Session resume | 否 |
| 同一對話超過有效 context window | Compaction＋保存的 conversation | 否 |
| 新 chat 想利用舊 chat 的可重用教訓 | Codex／Sandbox Memory | 是，或 run 中 live update |
| 多個 chats 共用相同文件／規則 | Project files／project instructions／workspace | 否 |
| 想找某份大型資料的相關片段 | File Search／vector store／custom retrieval | 否；這是 retrieval |
| 單次推理可能跑很久、怕 HTTP timeout | Responses background mode | 否；這只是非同步 Response |

特別校正：「閒置 6 小時」一類門檻若出現在 Codex Memory，代表舊 chat 何時成為
Memory extraction candidate；它不表示同一 conversation 要等 6 小時才記得內容。

## 9. Context 成本與可靠性

### 9.1 Conversation continuation 不等於省 token

`previous_response_id` 免除應用重送資料的麻煩，但官方明確說先前 input tokens 仍會
計費。Conversation／Session 是 state-management convenience，不是 token 壓縮。

### 9.2 Compaction 是 continuity optimization

Compaction 能減少後續 context token、延遲與成本，但它是 opaque continuation。
它與可搜尋、可審核、需要完整精確細節的長期資料責任不同。

### 9.3 Prompt cache 是 execution optimization

Prompt cache 需要相同 prefix。它不改變輸出生成、不保證同輸入同輸出，也不提供
semantic recall；cached tokens 仍計入 rate limits。Compaction 會改變 prefix，可能讓
壓縮後第一輪 cache reuse 下降，但總 input 變少仍可能更便宜。

### 9.4 Progressive disclosure 是固定成本控制

每輪只付小型 Memory guide 的固定 token；更多 Memory、rollout 或 project details
只有命中時才讀。這是 OpenAI 公開採用的 context-cost pattern，但它沒有保證背景
Memory extraction 永不漏掉所有 domain detail。

## 10. 不能由公開資料推斷的事

1. ChatGPT web Memory 的內部資料結構、retrieval ranking 與 prompt layout 沒有完整公開；
2. Codex local Memory 公開 read path 是 summary＋文字搜尋＋按需開檔，沒有證據可說它
   必然使用向量搜尋；
3. OpenAI 沒公開一個適用所有產品的固定 context token 配額表；
4. OpenAI 沒保證 compaction 或 distilled Memory 可取代精確 conversation evidence；
5. OpenAI 沒保證 Memory 自動完整保留某一專業領域的每個重要細節；
6. Background Response 與 background Memory generation 沒有隱含關係；
7. Prompt cache 不是資料庫，也不是跨對話記憶。

## 11. 對下一輪討論的輸入，但不是結論

這份研究只把 OpenAI 路徑說清楚，尚未決定 Caliburn 應如何做。下一輪若回到
`LLM-Q014 / G4.3b`，至少可以用以下已證實邊界檢查候選：

- 同一長對話 continuity 與跨 run Semantic Memory 應分開思考；
- context 不應等同「把全部資料塞進 prompt」；
- 小型導航＋按需深讀是 OpenAI 實際採用的成熟形狀；
- exact conversation evidence、compaction 與 distilled Memory 是不同 artifact；
- background manager 是可選寫入策略，不是 agent loop 必備前置步驟；
- Prompt caching 只能優化穩定 prefix，不能修復錯誤的 context selection。

是否採用、如何映射及是否需要 framework Tool，仍須回到目前唯一 blocking question，
不得由本稿直接推導 production schema。

## 12. 官方來源與主張對應

| 主張 | 官方來源 |
|---|---|
| Conversation 可跨 session／device／job，保存 message／Tool items | [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) |
| Conversation items 無一般 30 天 TTL；response chain 舊 input 仍計費 | [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) |
| `instructions` 不會隨 `previous_response_id` 自動沿用；Conversation items 會 prepend | [OpenAI — Responses API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) |
| Compaction 的 threshold、opaque item、canonical next window | [OpenAI — Compaction](https://developers.openai.com/api/docs/guides/compaction) |
| Sandbox Session 與 Memory 分層、progressive disclosure、兩階段生成、conversation identity | [OpenAI — Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes) |
| Codex Memory 閒置後背景更新、使用／生成開關、extract／consolidation models | [OpenAI — Codex local memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories) |
| Project／chat／workspace／selected-file context 的分工 | [OpenAI — Projects and chats](https://learn.chatgpt.com/zh-Hant/docs/projects) |
| Background mode 是單一長 Response 的非同步執行 | [OpenAI — Background mode](https://developers.openai.com/api/docs/guides/background) |
| stable prefix、dynamic suffix、append history、cache 與 compaction 的取捨 | [OpenAI — Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) |
| 小 prompt、Structured Outputs、Tool Search、compaction 的最新模型指引 | [OpenAI — Model guidance](https://developers.openai.com/api/docs/guides/latest-model) |

## 13. Closure

```text
Decision / finding:
  OpenAI 公開系統已能明確分成 conversation continuity、compaction、
  project/workspace context、distilled Memory、retrieval、prompt caching 與
  asynchronous Response；背景 Memory 可先處理同一 logical conversation，
  再跨多 conversation consolidation，但不負責目前 chat 的即時延續。
Status:
  Focused evidence complete；沒有 Caliburn design decision。
Why:
  官方契約已回答會改變 G4.3b 選項理解的名詞與資料流；剩餘 unknown 是產品內部
  hidden prompt／ChatGPT Memory 實作，不應用猜測補齊。
Affected artifacts:
  本稿、docs/README.md、docs/current-decisions.md 的 reviewed-evidence 路由。
Reopen trigger:
  OpenAI Conversation／Compaction／Sandbox Memory 官方契約改變，或 G4.3b 出現
  必須由 OpenAI 未公開內部行為才能回答的新選項。
Next gate:
  回到 LLM-Q014 G4.3b；比較 A1／A2／A3，不直接施工。
```
