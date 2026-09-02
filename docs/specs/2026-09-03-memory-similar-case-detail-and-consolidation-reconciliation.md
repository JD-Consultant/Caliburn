# Memory 相似案例細節與共同模式 reconciliation

- 日期：2026-09-03
- Topic ID：`MEM-Q002`
- 階段：**G3 Product Owner 已核准方案 C；進入下游 G2 機制研究前置**
- 狀態：**Working Decision；不授權 production、ADR、schema、索引或 spike 施工**
- 決策入口：[`../current-decisions.md`](../current-decisions.md)
- 已核准上游：[`2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](./2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md)
- 產品效果基線：[`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md)

> 本文只回答一題：員工描述很多相似工作案例時，如何同時避免 Semantic Memory 因逐案複製而膨脹，又讓長訪談後仍可找回 A／B 各案例的具體差異。本文不選 embedding、Qdrant、資料表 schema、模型、prompt 欄位或 production migration。

## 1. 白話結論

已核准採「**原始案例不丟、共同理解不重複、特殊差異才提升、需要時回查原話**」：

1. A、B 每次訪談內容都先保存在同一份 canonical conversation，因此原始案例與細節不會因整理而消失。
2. A、B 若只是同一工作模式的重複例子，Semantic Memory 不建立兩份相同「工作理解」；既有理解已足夠時為 no-op。
3. B 若補充可泛化的新細節，就修訂同一筆目前理解；若揭露可獨立搜尋與修訂的例外、責任邊界或另一類工作，才建立另一筆聚焦 Memory。
4. 具體客戶名稱、事件經過等只屬某一次案例、又不改變 JD 判斷的細節，可以只留在 canonical conversation，不必全部複製進 Semantic Memory。
5. 員工很久以後再說「A 案例」或「那個飲料店網站」時，Runtime 應以當前指涉搜尋／讀取 canonical conversation；不能只期待模型碰巧在近期 Context 中記得。
6. 全面製作或檢查 JD 時，列舉的是全部目前有效、會影響 JD 的 Semantic Memory，不是把所有逐字對話與每個案例一起塞進 prompt；原始案例仍可在需要核實時回查。

精確地說，「記得」分成三件事：

| 層次 | 保證 | 不能誤解成 |
|---|---|---|
| 耐久保留 | A／B 原始對話與細節仍在 canonical conversation | 每輪把完整歷史送入模型 |
| 目前理解 | 共同模式與會影響 JD 的差異存在可修訂 Semantic Memory | 每個案例固定一筆 Memory |
| 可找回 | 近期 Context 不足時可按需搜尋／讀取相關 Memory 或原始對話 | 模型不使用工具也會永遠「自己想起來」 |

因此答案是：**每個案例可以被耐久記住並在需要時找回，但不應把每個相似案例都逐筆複製成工作理解。**

## 2. 本輪研究方法與停止條件

### 2.1 研究順序

1. 先固定已核准的 `MEM-Q001`：Checkpointer 是 canonical conversation／run owner，Store 是可修訂 Semantic Memory owner；
2. 回到 OpenAI、Anthropic、Google、AWS 與 LangChain／LangMem 的最新直接官方資料；
3. 分開判斷「原始互動是否保留」「長期 Memory 如何整併」「細節如何按需找回」；
4. 將每項主張標成 Official fact、Cross-vendor conclusion、Caliburn mapping 或 Unknown；
5. 用 A／B 重複、B 有新差異、C 更正三個代表情境比較最多三個方案。

### 2.2 已達停止條件

- OpenAI、Google、AWS 與 LangMem 都公開 extraction／consolidation 或等價的整理責任；
- OpenAI、Anthropic、Google、AWS 與 LangGraph 都公開 conversation／events 與 derived Memory 的分層；
- Google、AWS 明確公開 duplicate／complementary／contradictory 的 create／update／skip 或 create／update／delete 行為；
- OpenAI、Anthropic 與 managed Memory 服務都公開 progressive disclosure、JIT read 或 bounded retrieval；
- 沒有任何直接官方資料要求「每個相似案例固定一筆 Memory」，也沒有共同的 `case／pattern` schema；
- 新增同類來源不再產生第四種責任模型。

因此 G2 可以停止廣泛搜尋，進入 Owner decision；底層搜尋與 schema 留給採納後的下一題。

## 3. 產品硬需求

本輪只使用已登記的效果需求：

1. 長訪談後仍可找回員工已提供的全部工作範圍與必要細節；
2. 相似案例不得線性複製成重複工作理解；
3. 低頻但會影響 JD 的例外、責任邊界、判斷或風險不能因「不常發生」而遺失；
4. 案例不能自動冒充正式 Task，案例如何抽象由 LLM＋職務分析 Skill 判斷；
5. 日常 Context 有界；需要時可繼續搜尋／讀取；
6. 最後完整 JD 盤點可處理全部目前有效 Semantic Memory；
7. 原始來源與整理後理解不能互相冒充，也不能產生兩份逐字 authority。

來源：[`Memory contract §3～§5`](./2026-09-01-framework-independent-memory-contract.md)、[`Perfect JD capability research §5`](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)。

## 4. 直接官方事實

### 4.1 OpenAI

**Official fact O1 — conversation 與 generated Memory 分層。** Agents SDK Session 保存指定 session 的 conversation history；Sandbox Agent Memory 則明確是另一層，從 prior runs 萃取供未來使用的 Memory。
來源：[OpenAI Agents SDK — Sessions](https://openai.github.io/openai-agents-python/sessions/) · [Agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/)

**Official fact O2 — 不是只留一份摘要。** Agent Memory 先把 run 追加至 conversation file；Phase 1 產生 conversation summary 與 raw memory extract；Phase 2 再整併成 `MEMORY.md`／`memory_summary.md`，需要更多依據時會打開 rollout summaries。
來源：[OpenAI Agents SDK — Agent memory：Generate memory](https://openai.github.io/openai-agents-python/sandbox/memory/#generate-memory)

**Official fact O3 — 讀取採 progressive disclosure。** 每個 run 先收到小型 summary；相關時再搜尋 index，只有需要更多細節才打開對應 rollout summary。這證明「平常看共同模式、必要時深入案例」是成熟形狀，但 OpenAI 沒有宣稱固定使用 `case／pattern` entity。
來源：[OpenAI Agents SDK — Agent memory：Read memory](https://openai.github.io/openai-agents-python/sandbox/memory/#read-memory)

**限制 O4。** Sandbox Agent Memory 仍為 beta，而且預設 consolidation 超過 raw-memory 上限時會只保留較新的 raw memories；它適合證明分層與 progressive disclosure，不能直接作為 Caliburn「所有員工工作不得永久遺失」的唯一保證。
來源：[OpenAI Agents SDK — `max_raw_memories_for_consolidation`](https://openai.github.io/openai-agents-python/sandbox/memory/#generate-memory)

### 4.2 Anthropic

**Official fact A1 — Memory 是按需讀寫的持久檔案，不需全塞入 Context。** Claude 可 create／read／update／delete `/memories` 內容；application 擁有實際 storage。Claude 先查看 directory，再只讀取相關檔案。
來源：[Anthropic — Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)

**Official fact A2 — 官方要求 coherent、up-to-date、避免不必要的新檔案。** Anthropic 建議記憶目錄保持一致、整理與最新，並明示「除非必要，不要建立新檔案」；大型檔案應限制單次 view 並分頁讀取。這支持避免一案例一檔造成雜訊，但沒有公開自動 dedup 演算法。
來源：[Anthropic — Memory tool：Prompting guidance／File storage size](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)

**Official fact A3 — Memory 與 compaction 互補。** Anthropic 建議長任務同時使用 compaction 與 Memory：compaction 控制活動 Context，Memory 保存不能被摘要丟掉的資訊。
來源：[Anthropic — Memory tool：Using with compaction](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#using-with-compaction)

### 4.3 Google Memory Bank

**Official fact G1 — extraction 後會與同 scope 現有 Memory consolidation。** Google 會比較新資訊與同 scope 的既有 Memories，避免 duplicate／contradictory；重疊時更新或刪除，不重疊才建立新 Memory。預設會考慮該 scope 的全部目前 Memories。
來源：[Google — Generate memories：Understanding memory generation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories#understanding-memory-generation)

**Official fact G2 — 不是每次互動都形成 Memory。** 只有符合 configured memory topic、且被判斷對未來有價值的資訊才持久化；相似概念可更新同一 Memory，沒有 meaningful information 時可不產生 Memory。
來源：[Google — Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)

**Official fact G3 — 日常相似搜尋與完整列舉是不同操作。** 同 scope 可做 embedding similarity top-k，也可以不帶 similarity 參數而分頁取回全部 Memories。
來源：[Google — Fetch memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)

### 4.4 AWS AgentCore Memory

**Official fact W1 — raw events 與多種 long-term strategy 分層。** Short-term Memory 保存 messages／tool calls；Long-term Memory 可使用 semantic、summary、preference、episodic 或 custom strategy。
來源：[AWS — Harness Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-memory.html)

**Official fact W2 — Semantic consolidation 明確有 Add／Update／Skip。** AWS 預設 prompt 要求：全新資訊 Add；與既有內容密切相關且補充新細節時 Update；已存在足夠細節或無意義時 Skip；更新時要保存原有的 timestamp、specific details 與 context，同時壓縮冗餘提高資訊密度。
來源：[AWS — System prompt for semantic memory strategy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)

**Official fact W3 — episode 與跨 episode pattern 可以並存，但不是所有產品必須採用。** AWS episodic strategy 會把完成的互動整理成 episode，再跨 episodes 產生 reflections／patterns；episode 可被 semantic search 取回。它主要描述 agent experiences，不等於 Caliburn 的員工工作案例 schema，只證明「具體經驗與跨案例模式」可以是不同可取回層。
來源：[AWS — Episodic memory strategy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/episodic-memory-strategy.html)

### 4.5 LangChain／LangMem

**Official fact L1 — collection 與單一 profile 有明確取捨。** 多筆 collection 的單項範圍較小，較不容易在大 profile 重寫時漏資訊，通常 downstream recall 較高；但模型可能 over-insert／over-update，而且完整 Context 與跨 Memory 關係更難。
來源：[LangChain — Memory overview：Profile／Collection](https://docs.langchain.com/oss/python/concepts/memory#profile)

**Official fact L2 — LangMem 可承接 extraction／consolidation plumbing。** LangMem 提供 background manager 與 hot-path tools，能從 conversation 抽取、整併、更新知識，並使用 LangGraph Store；既有 Memory 可傳回 manager 讓它 upsert，而不是每次一律新增。
來源：[LangMem](https://github.com/langchain-ai/langmem) · [LangMem extraction implementation／examples](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)

**限制 L3。** LangMem 的 generic prompt 不知道職務分析中哪些案例差異會影響 JD，也不保證每則來源都正確 admission；它只能覆蓋 manager 與 Store plumbing，不能替代 Caliburn 的職務分析 Skill／policy。

## 5. 跨家共識與非共識

### 5.1 可稱為共同形狀

| 共同方向 | 直接證據 | 對 `MEM-Q002` 的意義 |
|---|---|---|
| 原始 conversation／events 與 derived Memory 分層 | OpenAI、Google、AWS；Anthropic Memory＋conversation／compaction 分工 | 原始案例不應因共同理解形成而消失 |
| 新來源先 extraction，再與既有 Memory consolidation | OpenAI、Google、AWS、LangMem | A／B 必須先與目前理解比較，不是一律 append |
| 重複資訊不新增，互補資訊更新，真正新資訊新增 | Google、AWS、LangMem | Memory 數量不應隨相似案例線性成長 |
| 日常 Context 有界，細節按需深入 | OpenAI progressive disclosure、Anthropic JIT read、Google／AWS retrieval | 長訪談後靠 search／read 找回 A／B，不靠全部塞 prompt |
| Memory formation 需要產品／domain instructions | OpenAI `extra_prompt`、Anthropic topic guidance、Google topics、AWS prompt override、LangMem instructions | 「哪些案例差異會影響 JD」仍須職務分析規則 |

### 5.2 不能冒充大廠共識

以下沒有跨家共同結論，第一版不得自行說成標準答案：

- 固定建立 `case` 與 `pattern` 兩種資料表或 model schema；
- 每個員工案例必須一筆 Semantic Memory；
- 每個工作主題只准保存固定 N 個代表案例；
- 使用 Knowledge Graph、episode engine 或向量資料庫才算正確；
- 只靠 semantic top-k 就能保證所有案例與工作都已盤點；
- 任一 managed Memory／LangMem generic default 能自動判斷完整且正確的 JD admission；
- 每筆 Memory 都必須複製 quote、source UUID 或完整原文。

## 6. A／B／更正代表情境

假設員工是接案前端工程師：

- A：替餐飲客戶製作預約網站，訪談需求、做響應式介面、串接預約 API；
- B：替健身房製作會員網站，同樣訪談需求、做響應式介面、串接會員 API；
- B 另有一項特殊情境：上線前需和客戶的個資窗口確認追蹤碼與資料蒐集範圍。

### 6.1 A 初次出現

1. A 的完整對話耐久保留；
2. Manager 萃取出會影響 JD 的工作資訊；
3. Store 建立一筆聚焦目前理解，例如「依客戶需求設計與實作響應式網站，並串接業務 API」；
4. A 的品牌名稱、討論過程等只屬案例、又不影響 JD 時，留在 conversation，需要時再回查。

### 6.2 B 出現且大部分重複

1. B 的完整對話同樣耐久保留；
2. Manager 先取回與網站開發相關的目前 Memory，再比較 B；
3. 已被 A 的理解完整涵蓋的內容為 no-op，不建立第二份相同理解；
4. 可泛化的新資訊補入同一目前理解；
5. 個資確認若會影響責任、流程、風險或必要 K／S，必須保留：可補入同一連貫 Memory；若它可獨立搜尋、理解與修訂，才另建一筆聚焦 Memory。

### 6.3 很久以後再提 A／B

- 若案例仍在近期 Context，直接理解；
- 若不在近期 Context，先由相關 Semantic Memory 判斷工作主題，再搜尋／讀取 canonical conversation 中 A／B 的具體片段；
- 若「A」沒有足夠辨識線索，顧問應請員工澄清，而不是猜；
- 取回原始片段只供本輪核實／理解，不把整段歷史永久灌回每輪 Context。

### 6.4 員工更正 B

若員工後來說「B 案沒有串接會員 API，是匯入 CSV」：

1. 更正本身作為新 user message 留在 conversation；
2. Manager 比較更正、B 相關來源與目前理解；
3. 若 API 串接仍由 A 支持，不能把整個共同模式刪掉，只修正 B 的適用範圍；
4. 若共同理解原本錯誤地把所有案例都寫成 API 串接，修訂目前內容；
5. 舊說法不再進正常 Semantic Memory Context，但仍可由 conversation 回查。

## 7. 三個方案

### 7.1 方案 A — 每個案例固定一筆 Semantic Memory

優點：A／B 容易獨立搜尋，原貌較直觀。

缺點：案例量線性成長；相似工作會重複；長期搜尋噪音與成本提高；容易把案例誤當穩定 Task；不是跨家共識。LangChain 也明示 collection 可能 over-insert，完整 Context 與跨項關係更難。

**結論：不採為固定政策。**真正獨立且會影響 JD 的差異仍可形成另一筆聚焦 Memory，但不是「每案例一筆」。

### 7.2 方案 B — 只留一份共同模式，案例全部只在 transcript

優點：Semantic Memory 最小、去重容易。

缺點：例外、責任邊界、低頻高影響細節容易在整理時被過度壓縮；往後若只查 Semantic Memory，可能不知道應回查哪個案例；不滿足 M2／M7 的細節保真。

**結論：不能單獨採用。**Conversation 是保底，不是把所有 JD 重要差異都排除於 Semantic Memory 的理由。

### 7.3 方案 C — Canonical conversation＋選擇性 consolidation（已核准）

```text
每個案例的完整對話
  → 耐久留在 canonical conversation

新案例 + 少量相關 current Memories
  → 無新語意：no-op
  → 同主題的新通用細節：update
  → 可獨立搜尋／修訂的新工作或重要例外：add focused Memory
  → 明確更正：revise current understanding
  → 未解矛盾：保留兩邊，待員工釐清

日常：相關 Memory + 近期對話；必要時 search/read 原始案例
全面 JD：exact-scope 列舉全部 current Memories；需要核實才回查來源
```

`add` 前必須先和相關的 current Memory 候選比較；若第一批候選不足以排除重複，Manager 可以繼續搜尋／讀取，不能因 top-k 沒命中就直接新增。[Google](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories#understanding-memory-generation) 以同 scope 現有 Memories 做 consolidation，[AWS](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)／[LangMem](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py) 也把 existing memories 納入 add／update／skip 判斷；至於 Caliburn 第一版用全 scope、semantic candidate search 或兩段式檢查，屬採納後才研究的底層選擇。

優點：

- 同時符合原始細節不遺失與 Semantic Memory 不線性膨脹；
- 對應 Google／AWS 的 create／update／skip 或 create／update／delete、OpenAI 的 patterns＋rollout details、Anthropic 的 organized JIT files；
- 不強迫第一版先建立 `case／pattern` schema、Knowledge Graph 或 episode store；
- 可直接由成熟 Memory manager／Store 承接 CRUD、consolidation 與搜尋 plumbing；
- 最終完整 JD 仍以全部 current Memories 盤點，不依賴 top-k。

風險與控制：

- Manager 可能 over-update，把 B 的差異壓掉：以 A／B／更正代表性 smoke 驗證，且 canonical conversation 可回查；
- Manager 可能 over-insert：同樣用重複案例 no-op 測試，不以 record 數作成功指標；
- 原始案例「有存但找不到」：採納後的下一題必須決定 canonical conversation 的按需 search／read contract；索引只能是可重建查找層，不能複製成第二份來源 authority；
- Source→Memory admission 仍可能漏判：Runtime 至少記錄每則可處理來源是成功形成／修訂、合法 no-op 或失敗；這只保證處理可觀察，不冒充模型判斷永遠正確。

最後一項是 Caliburn 為「所有員工工作不可靜默漏處理」增加的產品可觀察性，不是供應商共同 schema；狀態由 Runtime 產生，不能要求模型填 source ID、receipt、版本或時間。

**Product Owner 已核准採用方案 C。**

## 8. 不預先固定 schema 的 admission 判準

新案例只有在增加下列任一會影響 JD 的意義時，才應改變 Semantic Memory：

- 新的行動、對象、產出或目的；
- 新的工作條件、頻率、週期、例外或風險；
- 新的工具、方法、判斷或決策邊界；
- 新的協作、交接、責任或核准邊界；
- 新的完成標準或必要 K／S 線索；
- 對既有理解的明確更正或尚未釐清的矛盾。

若只是客戶名稱不同、敘事不同但沒有新增上述語意，可以合法 no-op；原始內容仍在 conversation。這是 **Caliburn 的職務目的導向 admission policy**，不是宣稱任何廠商使用相同欄位。

「同一筆更新或另建一筆」只用一個邏輯問題判斷：**這段內容是否需要被獨立搜尋、理解與修訂？**這仍是語意政策，不是要求模型填 `kind=case`、`pattern_id` 或來源 UUID。

## 9. 採納後必須通過的最小情境

本輪不施工；以下是後續 isolated spike 的效果門檻：

1. **重複案例**：A、B 意義相同，兩段 conversation 都存在，但 current Semantic Memory 不增加重複內容；
2. **互補案例**：B 新增一項重要例外，更新後共同內容與 B 的例外都可找回，A 的既有細節不被覆蓋；
3. **獨立差異**：B 揭露可獨立修訂的另一類工作，形成另一筆聚焦 Memory；
4. **長距離指涉**：大量後續對話後提到 A 或 B，系統可按需取回對應原始片段與目前理解；
5. **更正**：更正 B 不會錯刪仍由 A 支持的共同工作；正常 Context 不再使用已更正內容；
6. **不線性膨脹**：大量同義案例不讓 Memory 數量與內容按案例數等比例成長；真正不同且影響 JD 的工作不得為了控制大小而遺失；
7. **全面盤點**：完整 JD 檢查處理全部 current Semantic Memories，不以 top-k 代替；
8. **失敗可見**：來源處理失敗可重試，不會被誤記為合法 no-op。

不設定「最多 N 個案例」或「Memory 最多 N 筆」作產品正確性標準；容量、延遲與成本要量測，但不能用固定上限刪除真實工作差異。

## 10. Owner 裁決與下一步

### 10.1 Owner 裁決（2026-09-03）

Product Owner 已核准採用方案 C 作 `MEM-Q002` Working Decision：

- canonical conversation 耐久保存全部 A／B 原始案例；
- Semantic Memory 只保存目前有效、會影響 JD 的共同理解與重要差異；
- consolidation 使用 add／update／remove／no-op 家族，不採每案例固定一筆；
- 案例與共同模式是語意角色，不是第一版必填 type／schema；
- 後續必須有按需搜尋／讀取 canonical conversation 的能力，確保長距離 A／B 指涉可找回；
- 最終 JD 全量盤點處理全部 current Semantic Memories，原始來源只在核實／補漏時回查。

### 10.2 G3 closure

- **Decision／finding**：採用 canonical conversation＋選擇性 consolidation；原始案例全部耐久保留，Semantic Memory 只保存共同理解與會影響 JD 的重要差異，必要時按需回查原始對話。
- **Status**：`WORKING`。它約束後續研究與設計，但不能越過 ADR 0060 與現行 code 授權 production。
- **Why**：方案 C 同時滿足細節不永久遺失、不讓同義案例線性複製、日常 Context 有界與最終全部目前 Memory 可盤點；方案 A 會膨脹，方案 B 容易過度壓縮重要差異。
- **Sources**：本文 §4～§7 的 OpenAI、Anthropic、Google、AWS、LangChain／LangMem 官方資料與跨家比較。
- **Affected artifacts**：[`../current-decisions.md`](../current-decisions.md)、本文與後續 `MEM-Q003`；不直接改 production ADR、schema 或程式。
- **Reopen trigger**：代表性驗證顯示重要案例差異會靜默遺失、同義案例造成近線性膨脹、長距離原始片段無法找回；官方 primitive 改變；或 Owner 改變產品效果。
- **Next gate**：`MEM-Q003` G2，定向研究 canonical conversation 的成熟 search／read primitive 與 authority 邊界。

### 10.3 採納後才開的下一題

下一個 gate 依序研究：

1. canonical conversation search／read 的最小成熟 primitive，及是否需要可重建 lexical／semantic index；
2. LangMem Manager 如何用極小 prompt／schema 表達上述 admission，而不讓模型填 scope、ID、version、time、Skill ID 或 quote；
3. PostgreSQL Store 的 focused Memory physical mapping 與 exact-scope listing；
4. 以上八個情境的 isolated smoke，不接 production。

## 11. 直接來源

- [OpenAI Agents SDK — Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK — Agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [Anthropic — Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Google — Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google — Fetch memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [AWS — Harness Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-memory.html)
- [AWS — Semantic Memory system prompt](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [AWS — Episodic memory strategy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/episodic-memory-strategy.html)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [LangMem](https://github.com/langchain-ai/langmem)
