# 專業顧問 Context 表示：外部權威證據審查

> 日期：2026-07-26
> 狀態：**研究完成；作為 R1 Context 實驗與第一版實作的設計依據，不自行取代 ADR 0040**
> 問題：長期職務訪談應把完整原始對話、檢索片段、結構化 Evidence／Work Model，還是它們的組合交給模型？
> 上游：
> [顧問流程最終反方審查](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)、
> [LLM 程式架構紅隊審查](2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md)、
> [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)

## 1. 結論

權威資料**不支持**以下任何一個絕對說法：

- 「模型 context 很長，所以每次把全部對話塞進去就是最佳解」；
- 「先把對話整理成 Evidence，就可以不再給模型原話」；
- 「向量相似度會自動找回所有重要內容」；
- 「先上知識圖譜／多 Agent 才是 2026 年主流架構」。

目前證據最支持的是一個**三層 Hybrid**：

```text
Source Layer（保真）
完整逐字對話／員工直接編輯／員工對提案的決策
        │  永遠保留，不被摘要取代
        ▼
Current Work Model（可操作現況）
已確認 Task、候選 Task、否定／更正、未決問題、O/P/K/S/A linkage
        │  是工作中的現況索引，不冒充逐字來源
        ▼
Operation-specific Context Packet（本次模型的工作記憶）
共同規則 + 目前目標 + 最近回合 + 相關原句 + 必要現況 + 不確定性
```

這不是把同一份資料存三次：

- Source 回答「員工實際說了／做了什麼」；
- Current Work Model 回答「目前對這份工作的理解是什麼」；
- Context Packet 回答「這一次模型要看什麼，才最可能做好當前任務」。

對第一版本的直接建議是：

1. **短訪談先採簡單 Hybrid**：完整 transcript + 小型 Current Work Model，不先建向量記憶或 Graph。
2. 對話變長或 eval 證明 full context 開始退化後，再加**按 operation 選取的原句**；不以任意固定 token
   數當永久架構常數。
3. Evidence／Work Model 的每個重要判斷都要能回到原始 `turn_id`；它是索引與工作現況，
   **不是新的真相來源**。
4. 更正、否定、他人責任與時間範圍不能只靠 embedding；至少要保留最近回合、明確的 correction
   關係與字面／metadata 查找。
5. Context 不足時，模型必須能輸出「尚不足以判斷」與下一個追問，不能被 schema 迫使產生 Task。
6. 公版檢索是另一個 knowledge source，只能提供候選；不得與員工自述 Evidence 混成同一種權威。
7. Graph Engineering 暫不進第一版 runtime。等到真實 eval 證明跨大量 Task／O/P/K/S 關係的全域查詢
   是瓶頸，再做最小 graph projection。

## 2. 證據等級與閱讀方式

| 等級 | 本文採用方式 | 來源 |
|---|---|---|
| A | 可支撐第一版設計原則 | 大廠正式工程文章、官方產品實作、已發表同行審查論文 |
| B | 可形成待測假說，不鎖架構 | 大廠研究預印本、特定領域或合成 benchmark |
| C | 只列 watchlist，不作決策 authority | 未審查的新 memory framework、廠商自報 benchmark |

不同論文的任務並不等於職務訪談。本文只把可合理轉移的失敗模式帶回本產品，並明確標示推論，
不把 QA、程式開發或百萬 token 文件的結果直接當成本產品成效。

## 3. 完整 Raw Context：必要，但不是永久唯一方案

### 3.1 支持 Raw 的證據

Anthropic 的 Contextual Retrieval 指南明確指出，資料在可管理範圍內時，直接放入完整 context
可能是最簡單的解；EMNLP 2024 對 RAG 與 long-context 的比較也發現，在資源充分的測試中，
long context 平均表現優於 RAG，但成本較高
（[Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)；
[Li et al., EMNLP 2024](https://aclanthology.org/2024.emnlp-industry.66/)）。

這支持 Caliburn 在短訪談階段保留一個真正的 `raw_only`／full-transcript baseline。若現有對話不長，
引入 extraction、retrieval、reranking 反而可能增加新的錯誤面。

### 3.2 反對永遠全塞的證據

長 context 的「可放入」不等於「可可靠使用」：

- TACL 2024 的 *Lost in the Middle* 發現，相關資訊放在長 context 中間時，模型表現可顯著下降，
  即使模型宣稱支援長 context 也是如此
  （[Liu et al., TACL 2024](https://aclanthology.org/2024.tacl-1.9/)）。
- Anthropic 2025 把 context 視為有限 attention budget，主張選擇能完整支援行為的最小高訊號 token
  集合，而不是無限累積
  （[Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)）。
- Microsoft／ICLR 2026 的多輪研究在六種生成任務看到平均 39% 的多輪表現下降；主要問題不是模型完全
  沒能力，而是早期做錯假設後變得不可靠且難以恢復
  （[LLMs Get Lost in Multi-Turn Conversation](https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/)）。

**對本產品的推論**：完整 transcript 必須保留，但每次 inference 不必機械式塞入全部歷史。越長的訪談，
越需要把「現況」「最近變化」「本次問題需要的原句」提高顯著性。

## 4. Structured Evidence／摘要：有用，但不能取代原話

### 4.1 它解決的真問題

持續訪談需要處理 knowledge updates、時間、更正、跨 session 推理與資訊不足。ICLR 2025 的
LongMemEval 把這些列為長期互動記憶的核心能力；長 context 與商用助理在持續互動記憶上仍出現約 30%
的 accuracy drop。其結果顯示 indexing、retrieval 與 reading 的設計會實質影響表現
（[LongMemEval, ICLR 2025](https://openreview.net/pdf/1b18c306d21b8ccc8ea3ab0ab975a62da3e73544.pdf)）。

OpenAI 2026 公開的內部 data agent 也不是只掃 raw logs。它把 schema／lineage、人工註解、程式碼衍生
語意、組織知識、可編輯 memory 與 runtime live context 分層；離線聚合成 normalized representation，
查詢時只拉最相關內容，必要時再即時查原系統
（[Inside OpenAI’s in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/)）。

這些資料支持 Current Work Model 的存在：模型不應每回合都從零重新推導「哪些 Task 已確認、哪些已被
否定、哪些仍未決」。

### 4.2 它不能成為唯一真相

Dialogue summarization 的實證對「把摘要當真相」提出直接警告：

- NAACL 2024 報告受測 LLM 產生的對話摘要平均 26.8% 含 factual inconsistency；當時最強受測模型仍有
  16%，且主客體理解是明顯難點
  （[She et al., NAACL 2024](https://aclanthology.org/2024.naacl-long.338/)）。
- ACL 2024 的人工 span-level 分析發現，LLM 會根據對話線索產生「合理但沒有被完整支持」的推論
  （[Analyzing LLM Behavior in Dialogue Summarization](https://aclanthology.org/2024.acl-long.677/)）。

職務分析正好高度依賴主體、責任、時間與否定，因此這不是邊緣風險。若 Evidence 寫成「使用 Java
開發系統」，原話可能只是「我偶爾幫同事看 Java 錯誤」；摘要看似合理，Task 邊界卻已經錯了。

**設計結論**：

- Evidence 必須保留 `source_turn_ids`，重要 claim 能取回逐字原句；
- Evidence 要有 `confirmed / candidate / contradicted / unknown` 等現況語意；
- 後來更正不能刪除舊原話，而是改變舊 claim 的現行效力；
- Current Work Model 可以被員工確認、修改或否定；
- 任何摘要或結構化欄位都不能單獨作正式 JD 的充分證據。

## 5. Retrieved Spans：不能只做 embedding top-k

### 5.1 為什麼需要選片段

選取片段可讓關鍵原話回到模型的高顯著位置，降低 full history 的注意力負擔。Anthropic 的 Contextual
Retrieval 實驗顯示：為 chunk 補上其在原文件中的簡短脈絡，再混合 embeddings 與 BM25，可降低 retrieval
failure；再加 reranking 會進一步改善。但該結果來自多種文件知識庫，不是職務訪談直接成效
（[Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)）。

### 5.2 為什麼相似度不足

- EMNLP 2025 的 conversational retrieval benchmark 涵蓋 9.1k 對話；16 個常用 embedding 模型中，
  最佳者 NDCG@10 仍約 0.51。作者指出 implicit state、turn dynamics 與 contextual references 是對話
  檢索的特有難題
  （[Finding Diamonds in Conversation Haystacks](https://aclanthology.org/2025.emnlp-industry.162/)）。
- Google Research／ICLR 2025 強調 retrieval 不只要「相關」，還要判斷 context 是否**足以**回答；
  不完整、矛盾或無結論的 context 都應視為 insufficient，並允許選擇性不回答
  （[Sufficient Context](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)）。
- Anthropic 也指出傳統 chunking 會破壞脈絡；單句若缺少人物、時間與文件位置，即使被找回也可能無法
  正確使用。

**對本產品的推論**：更正句「不是，那是以前的工作」與原 Task 的語意相似度可能不高，卻是最高優先級。
因此第一版 span selection 至少要混合：

1. 最近 N 個完整回合（N 由 eval 調整，不寫死成架構常數）；
2. 與目前 Task／未決問題直接連結的 `source_turn_ids`；
3. correction／denial／time／ownership metadata；
4. 關鍵字或 ID 的字面查找；
5. 對話真的長到需要時，才加 embedding／BM25／reranking。

檢索片段必須帶鄰近問句或最小 episode context，不能只交一個失去指涉的短句。

## 6. Hybrid 是主流方向，但必須保持權威分層

大廠公開實務的共同點不是某個框架名稱，而是**多種 context 各司其職**：

- Anthropic：預先放入必要背景 + 需要時自主探索；長任務使用 compaction 與 structured notes，但警告
  過度壓縮會遺失後來才看得出重要性的細節。
- OpenAI data agent：normalized representation + retrieval + runtime live queries + 可由人編輯的 memory。
- Microsoft GraphRAG：local search 仍把 AI 抽出的 graph 與 raw text chunks 一起使用，不是只信 graph
  （[GraphRAG Query Engine](https://github.com/microsoft/graphrag/blob/main/docs/query/overview.md)）。

所以 Caliburn 的 Hybrid 不應是「把 raw、summary、Evidence 全部重複貼一次」，而應是：

| Context 區塊 | 內容 | 權威 |
|---|---|---|
| `goal_and_policy` | 本次 operation 與 Task 判準 | 系統規則 |
| `current_work_state` | 已確認／候選／否定／未決 | 可修改現況 |
| `recent_dialogue` | 最近完整問答 | 原始來源 |
| `retrieved_source_spans` | 與本次判斷相關的完整原句及鄰近脈絡 | 原始來源 |
| `reference_candidates` | 公版相似 Task／K／S | 候選，不是員工事實 |
| `sufficiency` | 已知缺口、矛盾、下一問目標 | 系統計算 + 模型建議 |

同一資訊若同時出現在 state 與 source，必須可由 ID 連回，不能形成兩份互不相干的文字副本。

## 7. 對顧問流程的具體對映

### 7.1 每個員工回合

```text
員工輸入
  ↓
保存完整 turn（Source）
  ↓
辨識字面主張、否定、更正、時間、責任與新工作線索
  ↓
以「候選變更」更新 Current Work Model
  ↓
檢查：是否與既有 Task 衝突／合併／拆分／需要追問
  ↓
組裝下一問所需 Context
  ↓
顧問回答 + 必要時提出 JD 修改 proposal
```

「辨識字面主張」不等於每句建立一筆正式 Evidence，也不等於 Java／HTML／Python 各自變成 Task。
它只保留可追溯線索；Task 必須通過穩定責任、目的／結果、現在性、本人責任、可辨識工作邊界等判準。

### 7.2 發現新工作的情況

無論目前正在問 Task、Output、Indicator 或 K/S，只要員工提到新工作：

1. 先保存原話；
2. 建立 `task_candidate`，不直接插入正式 JD；
3. Context Engine 在後續排序時考量其重要性與證據缺口；
4. 必要時暫停目前支線，用一個短追問判斷新線索是新 Task、原 Task 的步驟、工具，或同一 Task 的另一故事；
5. 再回到原本未完成的分析目標。

這就是「固定分析責任、彈性訪談路徑」，不是死板的 Task → Output → Indicator → K/S 流水線。

### 7.3 Reload

重新開啟文件時：

- UI 讀 Current JD 與 Current Work Model；
- 對話區讀 Consultation Journal／transcript；
- 下一次 inference 重新由 Context Builder 組 packet；
- 不靠 LLM 記憶、不靠重播 journal 重建 current state，也不把上次臨時 prompt 當真相。

## 8. Graph Engineering 的裁決

Microsoft GraphRAG 的主要證據是百萬 token 私有語料上的 global sensemaking；standard indexing 還需要
LLM 抽 entity／relationship／claim 並產生 community summaries，官方 repo 也警告 indexing 可能昂貴
（[GraphRAG 論文](https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/)；
[官方 repo](https://github.com/microsoft/graphrag)）。

這不能證明一份 JD 的早期訪談需要 GraphRAG。第一版只需要普通 relational／in-memory references：

```text
Task ── Output
  ├── Indicator
  ├── Knowledge
  ├── Skill
  └── supporting source_turn_ids
```

只有出現以下實測問題才升級：

- Task／O/P/K/S 多到 operation-specific retrieval 無法維持一致性；
- 需要回答跨整份 JD 的 global 問題，而普通查詢與一次模型 synthesis 穩定失敗；
- 公版 corpus 的跨職類、跨職能關係成為產品核心；
- eval 證明 graph 比 raw + state + selected spans 有實質品質改善。

因此 `Work Graph` 在架構文件中可作**概念模型**，第一版不等於要引入圖資料庫、GraphRAG 或多 Agent
runtime。

## 9. Make the strongest case that Hybrid 仍可能是錯的

| 攻擊 | 若成立會發生什麼 | 第一版如何避免 |
|---|---|---|
| Current Work Model 錨定早期錯誤 | 後續每次都看見同一錯 Task，錯誤自我強化 | candidate/confirmed/contradicted 分離；更正優先；定期 reconcile；員工可改 |
| Extraction 遺失句間脈絡 | 「不是我做的」被拆掉主詞 | 原句與鄰近問句可回取；重要判斷不能只有 summary |
| Retrieval 漏掉低相似更正 | 舊說法復活 | recent window + correction link + lexical/metadata，不只 embedding |
| Hybrid 重複內容反而分散注意力 | state 與 raw 各說一次，context 變胖 | 只放本 operation 需要的 state；selected source 不機械重貼所有 claim |
| 強模型 raw-only 已經最好 | 多做一層只增加成本與錯誤 | 保留 raw baseline；持平選簡單者 |
| Graph 提前固化錯誤關係 | 錯 entity／edge 變成檢索權威 | 第一版不做 GraphRAG；references 只是可修改 current state |

這些攻擊表示 Hybrid 是**目前最安全的待驗證預設**，不是已被證明的最終最優解。

## 10. 對 R1-P0 與後續實驗的裁決

原 P0 想把 Codex subagent 當作外部 API 受測模型。owner 已確認平台不允許這種使用方式，因此：

- **沒有任何 P0 trial 被執行或可當證據**；
- 六個 frozen cases、rubric、context assembler 仍是可重用實驗資產；
- 不得建立虛構 `results.csv`／`report.md`；
- 外部研究不能取代本產品 A/B，只能提供安全預設與待測風險；
- 若未來重啟，須用實際 provider endpoint，另升 experiment revision，並固定 resolved model／endpoint、
  prompt、context、schema 與輸出；不使用 Codex subagent 代替 API；
- 正式 R1 仍依 ADR 0040 的六 arm、最強模型天花板與持平選簡單者執行。

### 最小而不過度設計的下一個實證

在 actual provider 可用時，只先跑 Task Discovery：

1. `raw_full`：完整短 transcript；
2. `raw_plus_current_state`：完整 transcript + 最小 current Task state；
3. 對話長度足以造成壓力時才加入 `state_plus_recent_plus_selected_sources`。

先驗證 Task precision／merge／split／更正／零證據；沒有實質改善就不建更複雜 Context Engine。

## 11. 採用、延後、拒絕

| 決定 | 項目 |
|---|---|
| **現在採用** | lossless transcript、可修改 Current Work Model、operation-specific Context Packet、source linkage、recent window、insufficient/unknown 出口 |
| **有失敗證據再加** | BM25／embedding、reranker、compaction、週期性 challenger、較完整 retrieval planner |
| **延後** | GraphRAG、圖資料庫、多 Agent memory、全域 community summaries |
| **拒絕** | summary-only、Evidence-only、embedding-only、每回合永遠 full-history-only、用 Codex subagent 冒充 provider trial |

## 12. 來源

### A 級：官方工程／同行審查

- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents),
  2025-09-29。
- Anthropic, [Introducing Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval),
  2024-09-19。
- Anthropic, [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps),
  2026-03-24。
- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents),
  2026-01-09。
- OpenAI, [Inside OpenAI’s in-house data agent](https://openai.com/index/inside-our-in-house-data-agent/),
  2026-01-29。
- OpenAI, [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/),
  2026。
- Microsoft Research, [LLMs Get Lost in Multi-Turn Conversation](https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/),
  ICLR 2026。
- Liu et al., [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/), TACL 2024。
- Li et al.,
  [Retrieval Augmented Generation or Long-Context LLMs?](https://aclanthology.org/2024.emnlp-industry.66/),
  EMNLP Industry 2024。
- Wu et al.,
  [LongMemEval](https://openreview.net/pdf/1b18c306d21b8ccc8ea3ab0ab975a62da3e73544.pdf),
  ICLR 2025。
- She et al.,
  [Exploring the Factual Consistency in Dialogue Comprehension of LLMs](https://aclanthology.org/2024.naacl-long.338/),
  NAACL 2024。
- Lee et al.,
  [Finding Diamonds in Conversation Haystacks](https://aclanthology.org/2025.emnlp-industry.162/),
  EMNLP Industry 2025。
- Google Research,
  [Sufficient Context: A New Lens on RAG Systems](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/),
  ICLR 2025。
- U.S. OPM, [Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)。
- 勞動部勞動力發展署，
  [職能發展及應用推動要點](https://icap.wda.gov.tw/Quality/quality_specification.aspx)。

### B／C 級：只作 watchlist

- Microsoft Research,
  [From Local to Global: A Graph RAG Approach](https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/),
  2024 preprint：只用於界定 Graph 的 corpus/global-query 適用範圍。
- Microsoft Research,
  [Human-Inspired Memory Architecture for LLM Agents](https://www.microsoft.com/en-us/research/publication/human-inspired-memory-architecture-for-llm-agents/),
  2026-05 arXiv：混合多線索檢索與 consolidation 有成本／容量價值，但仍是預印本與其他任務。
- Microsoft Research,
  [Beyond Semantic Organization: Memory as Execution State Management](https://www.microsoft.com/en-us/research/publication/beyond-semantic-organization-memory-as-execution-state-management-for-long-horizon-agents/),
  2026-06 arXiv：指出純語意相似度會打散執行依賴；可作 correction／active-state 設計假說，不能直接搬其
  hierarchical state tree。
- Microsoft Research,
  [Thinking Ahead: Prospection-Guided Retrieval](https://www.microsoft.com/en-us/research/publication/thinking-ahead-prospection-guided-retrieval-of-memory-with-language-models/),
  2026-05 arXiv：低 query-reference 相似度的記憶會被一般 RAG 漏掉；支持未來測 query expansion，
  不足以要求第一版 Tree-of-Thought retrieval。
- Microsoft Research,
  [RHELM](https://www.microsoft.com/en-us/research/publication/beyond-static-dialogues-benchmarking-realistic-heterogeneous-and-evolving-long-term-memory/),
  2026-05 arXiv：提醒現有 benchmark 與 memory framework 對多來源聚合、演化脈絡仍弱。

這些 2026 資料顯示研究趨勢正從「存更多記憶」轉向**管理有效現況、衝突、時間與多線索檢索**，
方向與本文三層 Hybrid 相容；但它們多使用合成 benchmark、程式／個人化記憶任務，且尚未證明可改善
單一員工的職務分析。不得據此提前加入 graph database、sleep consolidation、multi-agent memory、
Tree-of-Thought retrieval 或複雜 threshold pipeline。
