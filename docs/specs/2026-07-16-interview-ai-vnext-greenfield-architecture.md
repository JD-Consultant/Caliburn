# Interview AI vNext Greenfield Architecture——專業顧問 LLM 層定案規格

- 日期：2026-07-16
- 狀態：**greenfield 方向已核准；runtime 尚未實作；本文件是 vNext 的目標架構規格**
- 決策：不把 v3 `consultant/scribe/harvest/select` 內部流程整合、包裝或逐步演化成新版
- 適用團隊：一人開發團隊
- 產品前提：現有手動 JD Web、OCS 文件契約與人工審閱流程可用；重做範圍是 LLM 分析與訪談 runtime
- 上游研究：[`2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md`](2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md)
- 實作順序：[`../plans/2026-07-16-interview-ai-vnext-implementation-plan.md`](../plans/2026-07-16-interview-ai-vnext-implementation-plan.md)

---

## 1. 決策先行

Caliburn 的下一版不是「v3 再加一層 Evidence」；它是一個新的、可替換 provider、由應用程式掌握狀態的訪談分析 workflow：

```text
員工回答
  │
  ▼
Turn Interpreter（LLM；只輸出有 schema 的 observations/corrections）
  │
  ▼
Evidence Reducer（確定性程式；append/supersede，不讓 LLM 直接改 state）
  │
  ├────────────► Sufficiency Engine（確定性 coverage/gap/contradiction）
  │                                      │
  │                                      ▼
  │                              Question Policy（LLM 選下一個最高價值動作）
  │                                      │
  │                                      ▼
  │                              一個自然、非引導式的顧問回覆
  │
  └─ episode 可結束時 ─► Episode Coder（LLM；evidence-backed candidates）
                                  │
                                  ▼
                          Job Model Reducer + Verifier（確定性）
                                  │
  session 結束時 ────────────────┤
                                  ▼
                          Global Consolidator（受限 LLM pass）
                                  │
                                  ▼
                          OCS/JD Projector（確定性）
                                  │
                                  ▼
                          現有 `_pending`／Web 人工審閱
```

這是一個 **deterministic workflow with agentic decision points**，不是一群自主 Agent 彼此聊天，也不是單一巨大 prompt 同時負責聊天、記憶、分類、寫 JD 與自我審核。

### 1.1 立即生效的七個架構決定

1. **v3 內部相容性不是需求**：不保留舊 stage 名稱、prompt、tool protocol、`scribe/harvest/select` 責任切法或直接 doc mutation 路徑。
2. **外部產品契約仍要接上**：現有 Web、OCS/JD schema、tenant/profile/session identity 與人工 accept/reject 是產品邊界，不是要被淘汰的 LLM 架構。
3. **應用程式資料庫是 source of truth**：provider conversation/session 只能是傳輸最佳化，不能是訪談事實、進度或可恢復性的唯一來源。
4. **已知流程交給程式，語意判斷交給 LLM**：狀態轉移、idempotency、來源連結、驗證與 projection 由程式掌握；抽取、歸納、問題選擇與自然語言由 LLM 處理。
5. **預設是一個對話 owner，不先做 multi-agent**：不同 LLM pass 有各自 schema 和 prompt，但不具有獨立人格、共享自由聊天或自主 handoff。
6. **評測先於模型與框架選定**：同一套 case 可跑 OpenAI、Anthropic 或未來 provider；模型 routing 由實測品質、延遲與成本決定。
7. **Capture 是 workflow event envelope，不是 v3 stage enum**：新版觀測契約不得再次綁死某一代內部名稱。

---

## 2. 「不整合、不保留」的精確邊界

如果只寫「全部重做」，實作時仍會在錯誤的地方保留舊耦合。以下是強制邊界。

### 2.1 不保留的 v3 內部設計

| v3 內容 | vNext 決定 | 原因 |
|---|---|---|
| `consultant → scribe → harvest → select` 固定責任鏈 | 不作相容 adapter；以新 workflow operation 取代 | 舊責任同時混合聊天、抽取、文件 mutation 與收尾，難以定位錯誤。 |
| 每回合直接產生 OCS/JD operation | 移除 | 早期提及不等於已足夠支持最終職務敘述。 |
| `_pending.src` 充當唯一工作記憶 | 移除其內部記憶責任 | `_pending` 是供人審閱的 projection，不是訪談分析 state。 |
| stage 名稱作為 Capture 固定 enum | 移除 | 新增或拆分 operation 不應迫使整套 capture schema migration。 |
| 整份 document + 成長中的對話歷史永久塞入 prompt | 移除 | 長 context 會稀釋注意力，且無法明確控制每個 pass 看見什麼。 |
| provider 回傳文字後靠寬鬆 parser 猜結構 | 移除 | 新版只接受 provider structured output 或明確 failure。 |
| LLM 同時提出內容並自證內容正確 | 移除 | 產生器與 verifier 的責任必須分離，且 hard invariant 由程式檢查。 |
| 為舊 prompt 或舊 DB 中間欄位做雙寫 | 禁止 | 會把 greenfield 變成永久維護兩套語意。 |

### 2.2 保留的產品能力，不代表保留舊 LLM 架構

| 保留項目 | vNext 如何使用 | 邊界 |
|---|---|---|
| 手動 JD Web | 繼續顯示、編輯、接受或拒絕 `_pending` | vNext 不重做已可用的 Web。 |
| OCS/JD 公開契約 | vNext Projector 的輸出目標 | 上游 job model 可全新設計，不要求長得像 OCS。 |
| OCS/iCAP 等官方知識 | 作為 reference retrieval 與 taxonomy normalization | reference 不能假裝成員工實際工作事實。 |
| transcript | append-only 原始訪談紀錄 | 摘要不能覆蓋或刪除原文。 |
|人工 review authority | 高影響候選的最終權限 | LLM 不因高 confidence 跳過人工審閱。 |
| eval case、gold、runner、capture 基礎 | 作為 provider-neutral 品質量測 | 不要求 vNext 重現 v3 中間輸出。 |
| v3 runtime | 凍結成黑箱 baseline 與暫時 rollback | 不再新增架構功能；vNext 達 gate 後刪除。 |

### 2.3 baseline 與 compatibility 不同

保留 v3 作 baseline，只表示把相同起始資料送進舊版，量測最後結果和 trajectory；**不表示**新版要呼叫舊函式、寫舊中間 state、沿用舊 prompt 或逐 stage 對齊。比較單位是產品 outcome，不是內部實作。

---

## 3. 2026 一手資料結論

本輪只用供應商官方文件、官方工程文章及既有上游研究已審查的一手職務標準。框架文件用來確認主流工程方向，不等於 Caliburn 必須依賴該框架。

### 3.1 OpenAI：可組合 primitives、Responses、typed output、trace 與 eval

OpenAI 目前把 agent 基礎拆為 models、tools、state/memory 與 orchestration；需要細粒度控制時，官方把 Responses API 定位為核心基礎，Agents SDK 則是更高階的 loop、handoff、guardrail 與 tracing 抽象。官方也明說 multi-agent 不應是預設方案，只有工作清楚分離、指令或工具過度複雜時才考慮。[OpenAI Building agents](https://developers.openai.com/tracks/building-agents)

對 Caliburn 的採用方式：

- 以自有 workflow 掌握資料與狀態，provider adapter 可使用 Responses API；不把整個產品核心綁在 Agents SDK。
- 使用 strict structured output 表達 pass contract，但仍由 domain verifier 檢查 quote、語意與狀態不變量；schema 合格不等於內容真實。[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- provider conversation state 可用來減少傳輸，但 Caliburn 自有 session/event/evidence 才是可移植、可回放的來源。[OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- 每個 workflow step 都可獨立評測；持續從真實 failure 擴充 task-specific eval，優先使用可判別的 pass/fail、classification 或 pairwise，再以人工標註校準 model grader。[OpenAI Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- trace 必須能定位 model、tool、guardrail、handoff／step 的錯誤，不只留最後答案。[OpenAI Trace grading](https://developers.openai.com/api/docs/guides/trace-grading)

兩個會影響 2026 技術選型的退場資訊：

- Assistants API 預定 2026-08-26 關閉，官方替代為 Responses API 與 Conversations API。
- 舊 Evals platform 已於 2026-06-03 公告淘汰，2026-10-31 轉唯讀、2026-11-30 dashboard/API 關閉；官方遷移路徑指向 Promptfoo。

因此 vNext 不得新建 Assistants API integration，也不得把唯一 eval 資產放在 OpenAI dashboard。[OpenAI Deprecations](https://developers.openai.com/api/docs/deprecations#2026-06-03-evals-platform)

### 3.2 Anthropic：workflow 優先、context engineering、持久 session 與訪談三階段

Anthropic 將 workflow 定義為預先定義的 code path，agent 則由模型動態決定流程；其工程建議是先採最簡單、可組合的模式，只有在可量測收益存在時才增加 autonomous agent。固定可拆的任務適合 prompt chain/routing，未知步驟的開放任務才適合 autonomous loop。[Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents)

Anthropic 的 context engineering 指引把 context 視為有限資源：每次 inference 都要從不斷成長的資訊中挑出最小的高訊號集合；長任務可使用 compaction 和結構化外部 notes，但原始資料仍應可恢復。[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

Claude 官方 Messages API 可用於 stateless multi-turn conversation，而目前 Structured Outputs 以
`output_config.format` 或 strict tool schema 提供可驗證 JSON 邊界。這支持 vNext 由應用程式重建
context、由 adapter 使用 provider 的 strict schema，但同樣不能取代 domain semantic verifier。
[Claude Messages API](https://platform.claude.com/docs/en/api/messages/create)、[Claude Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

其 Managed Agents 架構更直接把 session log 放在 model context window 之外，讓 harness crash 後能從 durable event log 恢復，並明確區分「可恢復的 context storage」與「當次送入模型的 context selection」。[Scaling Managed Agents](https://www.anthropic.com/engineering/managed-agents)

最接近 Caliburn 使用情境的 Anthropic Interviewer 採三階段：

1. planning：研究目標形成可跨訪談一致、又能容納岔題的 rubric／plan，並由人類研究員定稿；
2. interviewing：依 plan 進行即時 adaptive interview；
3. analysis：以原計畫和完整 transcript 回答研究問題並附代表性引文，另做 emergent theme 分析。

它證明「固定目標 + 動態追問 + 引文支撐分析」是大規模實際模式，但沒有證明自述就等於客觀工作真相，也沒有公開一套員工訪談直接生成 JD 的成品架構。[Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)

Anthropic 2026 agent eval 指引要求區分 task、trial、grader、transcript/trajectory、outcome、eval harness 與 agent harness；對 conversational agent 同時評 end-state 與 interaction quality，並以多次 trial 看一致性。它建議 deterministic、model、human graders 混用，model judge 應有 `Unknown` 出口並接受人工校準。[Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

### 3.3 Google：predictable pipeline 與 adaptive routing 是兩種不同模式

Google 2026-07-08 的 Agent Development Kit 官方頁面明確把兩種 orchestration 分開：workflow agents 定義 predictable pipeline，agent-coordinated routing 處理 adaptive behavior；同時把 session/state、trajectory evaluation 與部署列為完整生命週期能力。[Google Cloud ADK](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/adk)

採用的是這個分工原則，不是直接導入 ADK：Caliburn 的訪談有大量已知不變量和資料處理步驟，應由 workflow 固定；只有語意抽取與下一題選擇保持 adaptive。

### 3.4 Microsoft：能寫成函式就不要變 Agent；明確步驟用 workflow

Microsoft 2026 Agent Framework 的官方 overview 把 open-ended/conversational 工作歸為 agent，把明確步驟、執行順序與多函式協調歸為 workflow，並明寫「若能用函式處理，就使用函式」。其 workflow 提供 typed routing、checkpoint、human-in-the-loop 與 telemetry；evaluation 亦採 provider-agnostic evaluator。[Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)、[Evaluation](https://learn.microsoft.com/en-us/agent-framework/agents/evaluation)

同一份官方 overview 將 Agent Framework 定位為 AutoGen 與 Semantic Kernel 的下一代直接後繼者，
因此 vNext 不會再依 2024–2025 的舊 AutoGen/Semantic Kernel orchestration 範例選型。但 Agent
Framework 目前仍是 public preview，所以只用來交叉驗證主流模式，**不作 vNext 的核心 production
dependency**。

### 3.5 O*NET：工作事實、頻率、重要性與 K/S/A 必須分開

大廠 agent 架構不能取代職務分析方法。O*NET 的官方資料採 incumbents、occupational experts 與
analysts 等多來源；task questionnaire 先判定 task relevance，再分開詢問 frequency 與 importance，
並允許補充既有清單未涵蓋的工作。O*NET Content Model 也分開 tasks、work activities/context、
knowledge、skills、abilities 與 work styles，而不是用一個「能力」欄位吞掉所有內容。
[O*NET Data Collection Overview](https://www.onetcenter.org/dataCollection.html)、[O*NET Occupation Expert Tasks Questionnaire](https://www.onetcenter.org/dl_files/omb2024/AppendixF-OE-Tasks.pdf)

因此 vNext 的 Evidence qualifier、Sufficiency gaps 與 Candidate Job Model 都把「有沒有做、誰負責、
多常做、是否重要、產出是什麼、需要哪些 K/S/A」分開；模型不能從提及次數、職稱模板或 reference
相似度自動補齊。

### 3.6 四家 agent 工程來源共同指向的設計

| 共同趨勢 | vNext 落地 |
|---|---|
| workflow 與 agent 分工 | reducer、state、verify、projection 是 workflow；語意判斷才用 LLM。 |
| state 在 context 外持久化 | event/evidence/job model 在 DB；prompt 只是當次 view。 |
| schema/typed boundary | 每個 LLM operation 有獨立 Pydantic/JSON Schema。 |
| trace + outcome eval | 記錄每個 step，但 release gate 看證據與 JD outcome，不僵硬要求唯一工具路徑。 |
| multi-agent 非預設 | 一個對話 owner；只有 eval 證明 instruction/tool/context 衝突才拆 agent。 |
| human-in-the-loop | JD projection 保持人工 accept/reject。 |
| provider 可替換 | business contract 不含 OpenAI response id 或 Anthropic message id。 |

---

## 4. 架構原則與禁止事項

### 4.1 必須成立的原則

1. **Evidence before classification**：先記錄員工說了什麼及限定條件，再查 taxonomy 或生成職務分類。
2. **Fact、inference、candidate、projection 分層**：四層不可用同一張模糊 JSON 混在一起。
3. **One writer per state transition**：LLM 提案，reducer 是唯一可改 domain state 的元件。
4. **Append or supersede, never silently rewrite**：更正與撤回建立關聯，不原地抹除歷史。
5. **No reference laundering**：OCS/O*NET 只能支持名稱、定義與候選探索，不能成為「員工有做」的證據。
6. **No silent semantic repair**：schema repair 可自動重試；業務語意錯誤不可被 parser 靜默猜測。
7. **Human authority survives model upgrades**：換模型、prompt 或 provider 不得重設已接受／拒絕的人工決定。
8. **Full transcript remains recoverable**：摘要與 context compaction 只影響模型 view，不刪原始 transcript。
9. **Every claim can answer why**：任何投影到 JD 的 task/output/K/S/A/indicator 都能回到 evidence IDs；推論還要回到 inference rule/version。
10. **Quality is measured as a distribution**：隨機系統不能以單次 demo 判定成功。

### 4.2 明確禁止

- 不以「角色名稱」直接展開一份標準 JD 再要求受訪者確認。
- 不把員工提及的工具名稱自動當成 skill。
- 不把 frequency 當 importance，也不把語氣強烈當核心責任。
- 不從一句自評形容詞直接產生 ability 或 attitude。
- 不生成來源沒有的數字 KPI、時效、品質門檻或責任歸屬。
- 不讓模型以自由文本命令 DB 寫入。
- 不儲存或要求 provider 暴露 hidden chain-of-thought；只保存輸入、可見輸出、工具、結構化理由碼和 verifier 結果。
- 不做無上限 self-reflection/evaluator loop。
- 不因 context window 變大就傳整份 session。
- 不在沒有 eval failure 證據前加入 vector DB、graph database、multi-agent manager 或 fine-tuning。

---

## 5. 執行邊界與元件

### 5.1 建議的程式邊界

vNext 先留在現有 FastAPI deployment 內，以新 package 完整隔離；一人團隊不為架構時髦拆 microservice。

```text
apps/api/app/interview_vnext/
├─ application/
│  ├─ commands.py            start/submit_turn/finish/review commands
│  ├─ workflow.py            明確 step orchestration、timeout、retry、checkpoint
│  ├─ context_builder.py     operation-specific context packet
│  └─ policies.py            turn/episode/session transition policy
├─ domain/
│  ├─ evidence.py            Evidence、qualifier、correction contract
│  ├─ episode.py             Episode、coverage、gap contract
│  ├─ job_model.py           Task/Output/K/S/A/Indicator candidates
│  ├─ events.py              domain event registry
│  ├─ reducers.py            唯一 state mutation implementation
│  └─ invariants.py          pure deterministic verification
├─ llm/
│  ├─ port.py                provider-neutral request/result envelope
│  ├─ operations.py          interpreter/question/coder/consolidator definitions
│  ├─ contracts.py           Pydantic operation input/output
│  └─ prompts/               一 operation 一版本化 prompt
├─ providers/
│  ├─ openai_responses.py    OpenAI Responses adapter
│  └─ anthropic_messages.py  Anthropic Messages adapter
├─ knowledge/
│  ├─ port.py                immutable reference snapshot interface
│  ├─ retrieval.py           metadata-first/hybrid retrieval
│  └─ normalization.py       taxonomy mapping，不創造 employee fact
├─ persistence/
│  ├─ repository.py          session/event/evidence/job-model unit of work
│  └─ models.py              vNext-only persistence mapping
├─ projection/
│  ├─ ocs_projector.py       Candidate Job Model → 現有 OCS/JD `_pending`
│  └─ verifier.py            projection hard gates
└─ observability/
   ├─ events.py              architecture-neutral execution envelope
   └─ capture.py             immutable artifact writer/outbox
```

依賴方向必須是：

```text
providers / persistence / projection adapters
                    │
                    ▼
             application workflow
                    │
                    ▼
              domain contracts
```

`domain` 不 import OpenAI、Anthropic、FastAPI、SQLAlchemy 或現有 v3 module。`interview_vnext` 不 import `app.interview.scribe`、`harvest`、`consultant` 或其 prompt。

### 5.2 不導入大型 agent framework 的理由

第一版使用普通 async Python + Pydantic + 現有 persistence/telemetry 基礎。原因不是框架不好，而是：

- workflow 只有少數明確 step，自行實作可得到最清楚的 state、transaction 和 capture 邊界；
- OpenAI Agents SDK、Google ADK、Microsoft Agent Framework 都有不同 provider/session 抽象，直接採用會讓 domain contract 受框架生命週期影響；
- Microsoft 目前仍是 preview；OpenAI 2026 的 deprecation 也證明平台層能力會退場；
- 一人團隊最需要的是可讀、可測、可刪除，不是多一層 orchestration DSL。

若未來需要跨日 durable workflow、分散式 worker 或大量 tool handoff，再以既有 event/checkpoint contract 評估框架；不得先把 framework object 寫入 domain model。

---

## 6. Domain state：六個分離但關聯的物件

### 6.1 `InterviewSession`

```json
{
  "session_id": "uuid",
  "profile_id": "uuid",
  "tenant_id": "uuid",
  "architecture_id": "interview-vnext-evidence-workflow",
  "workflow_version": "semver",
  "status": "planned|active|paused|finishing|completed|failed",
  "state_version": 12,
  "active_episode_id": "uuid|null",
  "turn_count": 6,
  "stop_reason": null,
  "reference_snapshot_id": "immutable-id",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

規則：

- 每個 command 帶 `expected_state_version`；不符合回 `409`，不做 last-write-wins。
- `completed` 後不得再接受 employee turn；需要補訪時開新 session 並明示 lineage。
- provider conversation ID 可放 execution metadata，不放 domain state。

### 6.2 `TranscriptTurn`

原始對話只追加：`turn_id`、speaker、原文、時間、前一 turn、client idempotency key。若使用者更正內容，新增 turn 並由 evidence 的 `supersedes` 表達，不編輯舊 turn。

### 6.3 `Evidence`

Evidence 是「可由 transcript 精確支持的一個原子 observation」，不是已完成的 JD 句子。

```json
{
  "evidence_id": "ev_uuid",
  "session_id": "uuid",
  "turn_id": "uuid",
  "episode_id": "uuid|null",
  "subject": "employee|employee_team|other_role|organization|unknown",
  "kind": "action|input|output|purpose|condition|standard|frequency|importance|ownership|tool|recipient|dependency|exception|negation|correction|preference",
  "claim": "在上線前整理測試結果並交給產品經理",
  "quote": "上線前我會把測試結果整理好交給 PM",
  "span": {"start": 18, "end": 38},
  "qualifiers": {
    "time_scope": "current|past|future|hypothetical|unknown",
    "typicality": "typical|occasional|exception|unknown",
    "polarity": "affirmed|denied|uncertain",
    "frequency": {"value": null, "unit": null, "verbatim": null},
    "importance": "explicit_core|explicit_supporting|not_stated",
    "ownership": "owner|shared|assists|receives|not_responsible|unknown"
  },
  "status": "active|superseded|withdrawn",
  "supersedes": [],
  "extractor_operation_id": "op_uuid",
  "schema_version": "evidence.v1"
}
```

硬規則：

- `quote` 必須是該 employee turn 的 exact 或明確規範化 span；否則 evidence 被拒絕。
- 一筆 evidence 只表達一個可獨立否定／更正的 observation。
- `past`、`hypothetical`、`denied` 不得投影成 current JD。
- ownership、frequency、importance 分開保存；缺資料就是 `unknown/not_stated`。
- extractor 不可把 reference text 放入 `quote`。

### 6.4 `Inference`

Inference 是可撤銷的解讀，例如「這可能是 release quality assurance responsibility」。欄位至少包含：

- `inference_id`、`type`、`statement`；
- `supporting_evidence_ids` 與 `contradicting_evidence_ids`；
- `reference_urns`；
- `status=candidate|confirmed_by_employee|rejected|superseded|insufficient`；
- `method=llm|rule|human`、operation/prompt/schema version；
- 結構化 `uncertainty_reason`，不使用模型自報 0–1 confidence 作真實機率。

沒有 active evidence 的 inference 不得投影。reference 只能協助命名或提供 taxonomy，不可取代 evidence。

### 6.5 `EpisodeState` 與 `Gap`

Episode 是一個具體工作事件／責任片段，不是 OCS 欄位。它至少追蹤：

- trigger/input；
- action/decision；
- output/recipient；
- purpose；
- ownership/collaboration；
- condition/tool；
- standard/result；
- frequency/importance；
- exception/rework；
- contradiction、拒答、不知道與已問問題。

`Gap` 必須是可回答的資訊需求，而非欄位名稱：

```json
{
  "gap_id": "gap_uuid",
  "episode_id": "uuid",
  "dimension": "output",
  "question_goal": "確認這項工作完成後交付給誰、以什麼形式交付",
  "supporting_evidence_ids": ["ev_1"],
  "status": "open|asked|answered|declined|not_applicable|deferred",
  "priority_features": {
    "jd_value": "high",
    "contradiction": false,
    "redundancy": false,
    "sensitivity": "low",
    "burden": "low"
  }
}
```

### 6.6 `CandidateJobItem`

Candidate Job Model 是分析結果，尚不是 Web 文件。共同欄位：

- `candidate_id`、`kind=task|output|knowledge|skill|ability|attitude|behavior_indicator`；
- `statement`、`evidence_ids`、`inference_ids`、`reference_urns`；
- `qualifiers`、`status=draft|verified|insufficient|conflicted|projected|rejected|accepted`；
- `created_by_operation`、`schema_version`；
- 若由人工 accept/reject，保存 review event 且模型不得覆寫。

---

## 7. 每類工作產出的操作定義

這一節是防止實作者「看欄位名稱猜 prompt」的最低規格。

| 類型 | 可以成立的最低證據 | 不得做的捷徑 | 不足時的追問方向 |
|---|---|---|---|
| Task | current + affirmed；action 明確；subject/ownership 不為他人；至少有 object、input、output、purpose 之一 | 從職稱模板複製標準 task | 「你實際做了哪個動作？完成後留下什麼？」 |
| Output | 可辨識交付物、決策、服務結果或系統狀態；有 recipient/use 或完成狀態更佳 | 把每個 action 名詞化就當 output | 「做完後誰拿到什麼？怎樣算完成？」 |
| Knowledge | 某知識領域確實被用來完成有 evidence 的 task | 看到產業名詞就列 Knowledge | 「做判斷時要懂哪些規則／原理？」 |
| Skill | 可學習的熟練行為，且能連到 task 的做法或品質 | 工具名稱、人格詞直接當 skill | 「熟練的人具體會怎麼做得不同？」 |
| Ability | 跨至少兩個獨立事件反覆出現的較一般能力，或由員工明示確認且仍有人審 | 單句「我很會溝通」直接成立 | 「這個能力還在哪些不同情況被用到？」 |
| Attitude | 可觀察、跨情境、與工作行為相關的傾向；高影響用途需人工確認 | 從語氣、人格印象或單一事件做標籤 | 通常不主動追問；只在 JD 契約確有需求時確認行為 |
| Behavior indicator | condition/context + observable behavior + quality/result；每部分有 evidence 或明確留白 | 生成漂亮口號或虛構數字 KPI | 「在什麼情況下會看到做得好？具體行為／結果是什麼？」 |

### 7.1 Task 與 Output 必須分開

「每週彙整客訴」是 action/task；「客訴趨勢報告」是 output。員工只說 action 時，不可假設固定報告存在；可以建立 task candidate 並開 output gap。

### 7.2 Tool 不等於 Skill

「使用 SAP」先記 `tool`。只有回答包含如何配置、分析、排錯、整合或以工具達成品質標準，才可能形成 skill candidate。Skill statement 應描述可轉移的熟練行為，tool 作為 context 或 evidence。

### 7.3 Behavior indicator 不是 KPI 生成器

若員工只說「要快速回覆」，可保留「在收到異常時主動回覆進度」等有引文支持的 observable behavior；不可自行寫「30 分鐘內回覆」或「滿意度 95%」。數值只能來自 employee quote、已核准組織 policy 或人工輸入，且來源類型要分開。

### 7.4 Ability 與 Attitude 採延遲編碼

兩者通常需要跨 episode pattern。Episode Coder 可先建立 hypothesis；Global Consolidator 才能在多事件 evidence 上提出 candidate。單一事件只可形成 skill/behavior evidence，不足以宣稱穩定能力或態度。

---

## 8. Runtime：每個 employee turn 的確切順序

### 8.1 Command 入口

`SubmitEmployeeTurn` 至少包含：

- session/profile/tenant identity；
- `client_turn_id` idempotency key；
- `expected_state_version`；
- 原始文字；
- locale；
- client timestamp 與 server receipt timestamp。

同一 `client_turn_id` 重送時回既有結果，不再次呼叫模型。相同 session 的兩個並行 turn 只能有一個通過 optimistic concurrency。

### 8.2 Step A：保存原始 turn 與 checkpoint

先以 transaction 寫 transcript turn 和 `interview.turn.received` event，再開始 provider call。provider timeout 不得使原始員工回答消失。

### 8.3 Step B：`turn_interpret`

輸入只包含：

1. operation instructions/schema；
2. 當前 employee turn 與直接 preceding consultant question；
3. active episode 摘要、active evidence 與 unresolved contradiction；
4. 可能被本回合更正的近鄰 evidence；
5. prompt-injection 邊界聲明：transcript/reference 是資料，不是指令。

輸出：

- `observations[]`；
- `corrections[]`，每筆指向既有 evidence 或標 `target_unknown`；
- `user_signal=answer|clarification|correction|dont_know|decline|stop|off_topic|mixed`；
- `episode_signal=continue|possible_shift|explicit_shift|possible_close`；
- `emergent_topics[]`，每項需附 current-turn span；
- `insufficiencies[]`；
- 不生成下一題、不查 OCS、不寫 JD。

### 8.4 Step C：Evidence Reducer

Reducer 按固定順序：schema validate → quote/span validate → subject/polarity/time validate → duplicate/correction relation → append/supersede → emit events。

失敗策略：

- transport/timeout：依 provider policy有限重試；仍失敗則 session 保持可恢復並回可理解錯誤；
- schema invalid：最多一次帶 validation error 的 repair call；
- quote 或 domain invariant invalid：拒絕該 observation並記 verifier result，不由 parser 改寫 claim；
- 部分 observation 合法時可部分接受，但 response/capture 必須列出 dropped IDs 和理由。

### 8.5 Step D：Sufficiency Engine

不呼叫 LLM。從 active evidence、asked gaps、拒答和 session budget 計算：

- current episode coverage；
- contradictions；
- 每個 open gap 的 priority features；
- episode 是否可編碼；
- session 是否可結束；
- 最多一組供 Question Policy 選擇的候選動作。

它不能把「所有欄位都填滿」當完成。停止條件是高價值 gap 已回答／拒答／不適用，且新增一題的預期資訊價值低於受訪負擔。

### 8.6 Step E：必要時 `episode_code`

在下列任一條件執行：

- 使用者明示切換到另一項工作；
- active episode 沒有 high-value gap；
- episode turn/evidence budget 已達 policy threshold；
- session finish；
- checkpoint recovery 發現 episode 已可關閉但尚未編碼。

Episode Coder 只讀該 episode evidence、contradictions、必要 reference snippets 與現有 candidates。輸出 candidate job items、inferences、unresolved gaps 及 evidence links；不得輸出 DB operation 或 `_pending` mutation。

### 8.7 Step F：Job Model Reducer + Verifier

依穩定 key 做 dedupe/supersede，檢查：

- 所有 evidence/inference/reference ID 存在；
- current-job polarity/time/ownership 合法；
- reference-only claim 被拒絕；
- ability/attitude 的跨 episode 要件；
- indicator 的 condition/behavior/result 來源；
- 人工 rejected/accepted item 不被模型重寫。

### 8.8 Step G：`question_select_and_respond`

Question Policy 從程式產生的 action candidates 中選一個：

- `ask_gap`；
- `confirm_correction`；
- `reflect_then_ask`；
- `transition_episode`；
- `offer_close`；
- `close_without_question`；
- `handle_decline`。

模型輸出固定結構：`action`、`selected_gap_id|null`、`reason_code`、`response_text`、`question_count`。一般情況 `question_count <= 1`；不是僵硬要求每回合一定問一題。程式確認 selected gap 存在、沒有重複、敏感度允許且 action 合法後，才送到使用者。

模型可提出 `emergent_gap`，但必須連到本回合 evidence/span；程式先建立 gap，再允許提問。這保留 adaptive interview，不讓模型任意離題。

### 8.9 Step H：commit 與事件

domain state、operation artifacts、回覆與 outbox event 以一致的 unit of work 提交。外部 telemetry 失敗不可回滾已完成 turn；capture writer 從 outbox 重試。

---

## 9. Session start、finish 與 recovery

### 9.1 `plan_interview`

Session start 建立初始 guide，不生成完整問題腳本。輸入：角色／組織背景、現有 JD 四態、使用者選擇的訪談目標、reference snapshot metadata。輸出：

- 固定研究目標，例如核心責任、輸出、標準、協作、K/S/A；
- 已知但待驗證的 topic；
- 禁止假設；
- 敏感題政策與 turn/time budget；
- 開場問題候選。

guide 經程式驗證後持久化；使用者已接受的 JD 內容是「待確認現況」，不是 employee evidence。

### 9.2 `finish_session`

Finish 不可只要求模型「整理成 JD」。順序：

1. 關閉／編碼 active episode；
2. `global_consolidate` 只做跨 episode dedupe、pattern、conflict 與 ability/attitude 延遲編碼；
3. deterministic Job Model Verifier；
4. deterministic OCS/JD Projector；
5. projection verifier；
6. 寫 `_pending` 供現有 Web 人審；
7. 保存 unresolved gaps、stop reason、final state hash 與 outcome artifact。

Global Consolidator 不可增加沒有 evidence 的新 task；它的每一項輸出必須引用既有 candidate/evidence IDs。

### 9.3 crash/retry recovery

每個 workflow step 都有 `operation_id` 和 status。恢復時：

- completed step 讀既有 artifact，不重跑；
- started 但無 completion 的 provider call 依 idempotency/timeout policy判斷 retry；
- reducer 由事件重建 materialized state 並驗 hash；
- 已送給使用者的 response 不重新生成；
- provider session 遺失時用自有 ContextBuilder 重新組 context，不中止整個訪談。

---

## 10. Context engineering 規格

### 10.1 三種資料不可混為「記憶」

| 層 | 內容 | 保存方式 | 進 prompt 的方式 |
|---|---|---|---|
| Record | full transcript、events、raw artifacts | append-only durable store | 只按 operation 需要取片段 |
| Working state | evidence、episode、gap、candidate、review | typed DB/materialized view | ContextBuilder 產生精簡 view |
| Model context | 當次 inference token packet | 不作 business source of truth | call 完即可丟棄；capture 留 hash/artifact |

### 10.2 ContextBuilder 是正式元件

每個 operation 有獨立 allowlist；不得使用通用 `build_everything_prompt()`。

共同組裝順序：

1. stable system policy；
2. operation-specific instructions 和 output schema；
3. current input；
4. active structured state；
5. unresolved contradictions/corrections；
6. metadata-first 找出的相關歷史 evidence；
7. 必要 reference snippets；
8. 明確標示省略內容與可用 tool/lookup。

初始可執行設定：

- `max_input_tokens=24000`，依 provider/model profile 覆寫；
- 最近兩組 user/assistant turns 永遠保留；
- active episode evidence 全保留，若超 budget 先保留 contradiction、correction、output、ownership、standard；
- cross-episode evidence 先用 subject/type/topic/lineage 過濾，再以 semantic relevance 排序，預設最多 24 筆；
- reference snippets 預設最多 8 筆，每筆含 URN/version/source type；
- 不使用 provider 的 auto-truncation 作正常策略；超 budget 要在應用層留下 deterministic selection manifest。

這些數值是 v1 的可測預設，不是永久常數。變更必須由 context ablation eval 支持。

### 10.3 摘要／compaction 的地位

- 可建立 episode summary 以改善對話流暢度；summary 是 derived artifact。
- summary 需列 source evidence IDs、版本與產生 operation。
- extraction、verification、projection 不得只讀 summary；關鍵 claim 回到原始 evidence/quote。
- compaction 失敗只影響 model context，不得破壞 durable session。

### 10.4 Retrieval 策略

對 interview state，第一版使用 structured SQL/metadata retrieval；一個 session 的 evidence 不先建獨立 vector database。對大型 OCS/O*NET/reference corpus，使用現有 knowledge service 或 hybrid retrieval：metadata filter → lexical/dense candidate → rerank → immutable snapshot。

Retrieval 分兩條 channel：

- `employee_evidence_context`：只能來自 transcript/evidence；
- `reference_context`：只能用於 taxonomy、定義、候選 gap 或 normalization。

prompt、schema 和 verifier 都保留此區分，防止來源洗白。

---

## 11. Provider 與模型層

### 11.1 provider-neutral port

```python
class LlmPort(Protocol):
    async def generate_structured(
        self,
        *,
        operation: OperationSpec,
        context: ContextPacket,
        output_schema: type[BaseModel],
        config: ModelExecutionConfig,
        idempotency_key: str,
    ) -> ModelCallResult: ...
```

`ModelCallResult` 至少包含：provider、requested/resolved model、request id、visible raw response artifact、parsed output、input/output/cached/reasoning token usage（provider 有提供時）、latency、attempts、finish/outcome、provider conversation/response ID（metadata only）、prompt/schema/context hashes。

Domain code 只看 parsed output 和 normalized failure，不看 OpenAI/Anthropic SDK object。

### 11.2 operation registry，而不是到處硬編模型名

```yaml
turn_interpret:
  quality_profile: high_precision_extraction
  output_schema: turn_interpret.v1
  timeout_ms: 45000
  max_attempts: 2
question_select_and_respond:
  quality_profile: low_latency_conversation
  output_schema: question_policy.v1
  timeout_ms: 30000
  max_attempts: 2
episode_code:
  quality_profile: deep_analysis
  output_schema: episode_code.v1
global_consolidate:
  quality_profile: deep_analysis
  output_schema: global_consolidate.v1
```

實際 provider/model 由部署設定與 eval report 綁定。第一輪應用最強可用模型取得品質上限，再用相同 case 嘗試較快／較便宜模型；不可先為省成本把架構能力判成失敗。

### 11.3 retry 與 repair

- transport、rate limit、provider 5xx：有限 exponential backoff，整體受 operation deadline 限制；
- schema invalid：最多一次 repair，輸入只附 validation errors 與原可見 output；
- domain invalid：不自動無限反思；保留 failure，必要時由 workflow 選擇一次針對性 semantic repair；
- safety refusal：不得 parser fallback，回 normalized refusal 並決定對使用者的安全回覆；
- 每次 attempt 都是 capture child event。

---

## 12. Capture vNext：類似 log，但比普通 log 更嚴格

Capture 是可重播的實驗／稽核事件資料，不只是用來找 exception 的文字 log。它必須同時回答：用了哪版流程、看了什麼、模型做了什麼、程式接受／拒絕什麼、state 如何改變、最後 outcome 是什麼。

### 12.1 通用 execution event envelope

```json
{
  "event_schema_version": "execution-event.v1",
  "event_id": "uuid",
  "occurred_at": "timestamp",
  "architecture_id": "interview-vnext-evidence-workflow",
  "workflow_version": "1.0.0",
  "run_id": "uuid",
  "session_id": "uuid",
  "turn_id": "uuid|null",
  "operation_id": "uuid|null",
  "parent_operation_id": "uuid|null",
  "event_type": "model.call.completed",
  "stage": "turn.interpret",
  "stage_taxonomy_version": "interview-vnext-stages.v1",
  "attempt": 1,
  "status": "ok|partial|failed|skipped",
  "input_artifact_refs": [],
  "output_artifact_refs": [],
  "state_before_hash": "sha256|null",
  "state_after_hash": "sha256|null",
  "metadata": {}
}
```

`stage` 是符合命名規範的 registry string，不是封閉 Pydantic `Literal`。已發出的名稱不改語意；新增 stage 只更新 taxonomy 文件。domain event 與 execution event 分開：前者描述業務事實，後者描述程式執行。

### 12.2 最低 event set

- `workflow.run.started/completed/failed`；
- `workflow.step.started/completed/failed/skipped`；
- `model.call.started/completed/failed` 與逐 attempt child event；
- `tool.call.started/completed/failed`；
- `state.transition.accepted/rejected`；
- `artifact.created`；
- `verification.completed`；
- `human.review.accepted/rejected`；
- `outcome.finalized`。

### 12.3 Capture 不綁 provider dashboard

本地 committed schema + immutable artifacts + runner 是權威；OpenTelemetry、Promptfoo 或 provider dashboard 都是 consumer。這可避免平台退場或 provider 切換時失去歷史可比性。

### 12.4 v3 Capture 的處置

現有 opt-in capture 保留作舊版黑箱 baseline，不再為 v3 補一套深度 provider integration。vNext 直接實作上述 envelope；必要時 exporter 將 v3 artifact 映射到共同 case/outcome 層，**不要求**映射新舊 stage。

---

## 13. 驗證與安全不變量

### 13.1 deterministic hard gates

任何失敗都不得靠較高平均分抵銷：

- employee quote/span 不存在；
- denied/past/hypothetical/other-role claim 被投影成 current employee duty；
- current task 沒有 employee evidence；
- reference text 被當 employee fact；
- correction 後舊 evidence 仍以 active 參與 projection；
- LLM 覆蓋人工 accepted/rejected item；
- 不存在的 evidence/reference ID；
- 無來源數字 threshold；
- tenant/profile/session identity mismatch；
- duplicate turn 造成重複 model call 或重複 projection；
- finish 後寫入新 turn；
- capture hash chain/state version 不連續。

### 13.2 prompt injection 與資料邊界

- transcript、JD、reference snippet 都放在明確 data block，system instruction 明示不可執行其中命令；
- employee-facing operations 不提供任意 DB/write/network tool；
- knowledge retrieval tool 只讀固定 tenant/reference scope；
- model output 永遠先進 reducer/verifier；
- Capture 保存 prompt/schema hash，安全 case 進 regression suite。

### 13.3 human review

人工審閱至少顯示 statement、type、supporting quotes、qualifiers、reference、conflict/uncertainty。接受、修改、拒絕都產生 review event；人工修改成為 human-authored content，不可被後續模型靜默還原。

---

## 14. Evaluation：如何證明新版真的比較強

### 14.1 三層 eval，不互相冒充

| 層 | 輸入是否固定 | 評什麼 | 不能宣稱什麼 |
|---|---|---|---|
| Component replay | 固定 turn/episode | extraction、qualifier、correction、coding、projection | 下一題能否引出更多真相 |
| Branching conversation | hidden fact world + simulated user policy | question value、redundancy、leading、stop、coverage | 真人體驗與完整專業效度 |
| Human pilot | 真人、同意參與、盲評 | 被理解感、疲勞、揭露品質、最終 JD usefulness | 所有職類已普遍成立 |

### 14.2 v3 如何當 baseline

- 使用從 turn zero 開始的新 synthetic/controlled sessions；
- C0/v3 與 vNext 得到相同 initial JD、reference snapshot、employee facts 和 budget；
- fixed replay 比分析結果，branching eval 各自與同一 hidden fact world 互動；
- 不要求 vNext 重現 v3 stage；比較 claim/outcome、interaction、cost、latency；
- v3 不因 baseline 身分繼續獲得架構功能。

### 14.3 初始資料集

依 Anthropic 2026 建議，先以 20–50 個清楚 task 起步，而不是等待數百筆。至少平衡：

- 應抽取／不應抽取；
- current/past/hypothetical；
- owner/shared/assists/not-responsible；
- affirmation/negation/correction/contradiction；
- core/occasional/exception；
- 有 output/缺 output；
- 有標準/不可虛構標準；
- 單一意圖/多意圖/切換 episode；
- 知道/不知道/拒答/要求停止；
- reference 有相似職務但員工未提及；
- prompt injection 與敏感問題。

每個 case 有 reference solution 或明確 claim-level gold，且證明 grader 可讓已知正確輸出通過。

### 14.4 graders

1. **Code graders**：schema、quote、span、ID、lineage、polarity/time/ownership、idempotency、state/outcome。
2. **Model graders**：問題是否 leading、單一焦點、自然、資訊價值；JD task/indicator 是否具體、專業。每個維度分開 rubric，允許 `Unknown`。
3. **Human graders**：gold adjudication、model-grader calibration、盲測 pairwise、重大 failure trace。

不使用同一個生成模型的「自我覺得正確」作 release gate。

### 14.5 指標

- evidence precision/recall/F1；
- qualifier exactness：time、polarity、ownership、frequency、importance、typicality；
- correction application 與 stale-evidence leakage；
- required claim recall、unsupported claim rate、forbidden claim count；
- task/output/K/S/A/indicator 的 evidence coverage；
- contradiction preservation；
- question information gain、redundancy、leading rate、平均 turns、decline respect；
- stop precision/recall；
- final JD blind pairwise win/tie/loss 與 SME severity；
- per-operation latency、tokens、cost、retry/failure；
- 多 trial pass@1 與 customer-facing consistency `pass^k`。

### 14.6 promotion gate

vNext 切 production 前必須同時成立：

- 所有 deterministic hard gates 通過；
- 不新增 unresolved critical failure；
- required claim recall 不低於 v3；
- unsupported/incorrect current-job claims 顯著少於 v3，且改善不是只由單一 case 驅動；
- blind human pairwise 對 vNext 至少不劣，並能指出內容收益而非格式偏好；
- adaptive eval 的 leading/redundancy/stop 無倒退；
- 關鍵案例多 trial 一致性達預先註冊門檻；
- latency/cost 在產品預算內，或有明確 quality-first 與 economy routing；
- failure 可從 trace 定位到 operation、context、model、reducer 或 projector。

門檻數字在建立首批 20–50 case、取得 baseline distribution 後預註冊；不可看完 vNext 結果才移動門檻。

---

## 15. Multi-agent、Workflow Graph、fine-tuning 與 RAG 的入場條件

### 15.1 Multi-agent

初版不做。只有下列全部成立才做 ablation：

1. 單一 operation 的 instructions/tools/context 已明確超載；
2. failure trace 顯示混淆來自責任衝突，不是 schema、prompt 或資料問題；
3. 子任務 context 可真正隔離，或可平行帶來可量測收益；
4. multi-agent candidate 在同資料、同 budget 或明列額外成本下勝出；
5. 一人團隊可維護其 trace、retry、handoff 與 evaluation。

「Extractor、Coder、Question Policy 是不同 pass」不等於 multi-agent。只有它們具有自主 loop/handoff/工具空間時才算。

### 15.2 Workflow Graph

第一版以 episode、evidence link、dependency/exception observations 表達流程。只有順序、分支、handoff、rework 在多個真實 case 中反覆造成重大漏失，且小型 graph prototype 改善專門案例，才持久化完整 graph。

### 15.3 Fine-tuning

先不做。需要穩定 operation schema、足量人工裁決資料、明確 base-model plateau，並證明 prompt/context/retrieval 無法解決後才評估。訓練資料不可把模型產生的 pseudo-gold 當真實標籤。

### 15.4 額外 vector/RAG infrastructure

reference corpus 可使用既有 retrieval；session evidence 先以 typed metadata/SQL。只有長 session retrieval eval 顯示 relevant evidence recall 不足，才為 evidence 增加 embedding/hybrid index。

---

## 16. 切換策略：重做內部，不拿使用者當測試工具

```text
凍結 v3 架構功能
  ↓
建立 vNext contracts + offline runner
  ↓
固定 transcript component eval
  ↓
branching simulated-user eval
  ↓
獨立 pilot／shadow outcome 比較
  ↓
feature flag 將既有 API seam 指向 vNext
  ↓
人工審閱與監控 gate
  ↓
移除 v3 internals、舊 prompts、舊中間 schema
```

「不用整合」表示不做新舊內部雙寫與 adapter 鏈；切換時仍需在一個很薄的 HTTP/application seam 接上現有 Web。若 vNext 尚未通過 gate，v3 只是暫時 production fallback，不是新版依賴。

### 16.1 切換 seam

Web request/response 的必要欄位由 contract test 固定。seam 只做：identity/auth、request validation、呼叫選定 runtime、把 domain response 映射回現有 UI contract。它不翻譯 v3 state 到 vNext state；新的 vNext session 從 turn zero 開始，不在訪談中途熱切換 runtime。

### 16.2 刪除條件

vNext production gate 通過、rollback window 結束且沒有 active v3 session 後：

- 刪 v3 prompts與內部 runtime；
- 刪只服務 v3 的中間 DB/table/flags（另做 migration）；
- 保留匿名 eval artifacts、decision report 與必要 migration history；
- 文檔把 v3 移到 archive，現行 design 改指 vNext。

---

## 17. 不確定事項與如何裁決

| 問題 | 現在的預設 | 裁決方法 |
|---|---|---|
| OpenAI 或 Anthropic 哪個最終模型？ | 不先鎖；兩個 provider adapter | 在相同 held-out cases 跑 operation-level bake-off。 |
| Question Policy 與 response composer 是否拆兩 call？ | 合併為一個 structured operation | 若自然度與 policy correctness 無法同時達標，再做拆分 ablation。 |
| Episode Coder 每次何時跑？ | shift/close/budget/finish 時 | 比較漏失、延遲與下一題品質。 |
| 是否需要 global LLM consolidation？ | 只在 finish 或跨 episode pattern 時 | 若 deterministic merge 已達標則刪除這個 call。 |
| Context budget 24k 是否最佳？ | 可執行起點 | 8k/16k/24k/更高 ablation，看 recall、錯誤、latency。 |
| 是否需要 graph？ | 否 | 專門 process-sensitive failure set。 |
| 是否需要 multi-agent？ | 否 | 只在單 operation overload 被 trace 證明後 ablation。 |
| 是否可取消人工 review？ | 否 | 本產品的人事／職務影響使其為固定 authority boundary。 |

---

## 18. Definition of Done

不能以「程式跑得動」宣稱架構完成。vNext 完成至少包含：

- 新 package 不 import v3 LLM internals；
- 六個 domain object、operation I/O、events、provider port 全部有 versioned schema；
- reducer/invariant/projector 有 deterministic unit/property tests；
- OpenAI Responses 與 Anthropic Messages 至少各有一個可替換 adapter，或先完成一個、另一個有 contract test fake；
- turn、episode、finish、retry、crash recovery、idempotency、correction、decline、stop 都有端到端測試；
- Capture vNext 不以封閉 v3 stage enum 表達；
- 20–50 個初始 tasks、balanced negatives、多 trial artifacts、human calibration subset 存在；
- v3/vNext black-box report 含 outcome、interaction、latency、cost、variance 與 trace review；
- production cutover gate 有書面 decision memo；
- 現有手動 JD Web 與人工審閱 contract tests 通過；
- 現行 design/runbook/README 在切換 commit 同步更新。

---

## 19. 最終結論

「站在巨人的肩膀上」不等於複製某一家 SDK 的範例或堆更多 Agent。2026 年 OpenAI、Anthropic、Google 與 Microsoft 的官方方向實際上收斂於：

> 用明確、typed、可 checkpoint 的 workflow 掌握已知流程；把有限且真正需要語意判斷的節點交給模型；把狀態放在 context window 外；用 trace、outcome、多次 trial 與人工校準證明品質。

因此 Caliburn vNext 的核心是 **Evidence-first durable workflow + one adaptive conversational owner + deterministic reducers/verifiers/projector + provider-neutral eval**。舊 v3 只作黑箱比較，不進入新 runtime。是否增加 graph、planner、multi-agent、fine-tuning 或更重 retrieval，全部由 Caliburn 自己的 failure trace 取得資格，而不是因為技術名稱流行就預先導入。
