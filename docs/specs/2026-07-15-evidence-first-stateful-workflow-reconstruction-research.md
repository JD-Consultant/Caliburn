# Evidence-first Stateful Interview Architecture——專業顧問 LLM 層研究與候選架構

- 日期：2026-07-15
- 狀態：**研究持續中／架構尚未定案**。本檔不是現行 runtime 的描述；現行 v3 仍以 [`../design/interview-engine.md`](../design/interview-engine.md) 為準。文中的 C0/C1/C1A/C2 都是待比較候選，不是已核准設計。
- 範圍：Caliburn「訪談式工作分析 → OCS/JD 草稿」的 LLM 層、狀態、工具、驗證與評估。
- 非範圍：Web 文件編輯／`_pending` 審閱 UX、OCS 公版契約、租戶與權限架構重做。
- 來源政策：優先採用 OpenAI、Anthropic、Google、O*NET、ESCO、ILO 等一手資料；研究論文僅使用 ACL 等可追溯學術來源。來源截至 2026-07-15 可取得版本。

---

## 1. 結論先行

Caliburn 不應再把問題表述為「把員工每回合回答抽進 JD 欄位」。正確問題是：

> 透過多輪訪談，累積可回查的工作證據，理解該員工實際的工作事件；只在確有價值時重建流程關係，再把**有足夠證據的職務候選**投影為可人工審閱的 JD。

目前證據最強的不是一張完整 Workflow Graph，而是 **Evidence-first Stateful Interview** 的最小骨架：

```text
不可修改的逐字稿
        │
        ▼
Evidence Ledger（有 quote 的事實與明示限定條件）
        │
        ├──────────────► Interview Agenda（覆蓋、缺口、矛盾、停止訊號）
        │                         │
        └──────────────► Inference Ledger（可撤銷推論）
                                  │
                                  ▼
Candidate Job Model（任務／產出／K-S-A／行為指標候選）
        │
        ▼
OCS/JD `_pending`（既有 Web 逐筆審閱）
```

其中 LLM 仍是語意理解、追問、分類與候選生成的核心；但它**不是**事實的唯一記憶體、語意真相的最終裁決者，亦不能直接無聲改寫 JD。`WorkflowGraph`、多 agent planner、模擬 rollout 與正式流程語言目前都只是可被實驗引入或淘汰的擴充，不屬於第一版不可變核心。

---

## 2. 研究問題與答案

### 2.1 大廠是否有公開的「員工訪談 → JD」端到端產品流程？

截至本文日期，仍未找到 OpenAI、Anthropic 或 Google 公開一套可直接照搬的「完整員工工作訪談 → JD」成品架構。但已找到非常接近上游問題的實際大廠案例：Anthropic Interviewer 採 **planning → adaptive interviewing → analysis** 三階段，以固定研究問題維持跨訪談一致性、依回答調整追問，再由人與 Claude 協作分析逐字稿並保留代表性引文；2026 年公開研究已擴至 80,508 份合格訪談、159 國、70 種語言。[A8][A9]

因此，現在能採用的是「被實際大規模使用的訪談與分析模式」，不能宣稱 Anthropic 已證明如何產生 JD。公開一手資料與同行評審研究共同支持：

1. LLM 在 loop 中根據目前 workflow/state 做判斷與工具選擇。
2. 外部工具負責資料讀取、寫入與可驗證動作。
3. 長任務的關鍵是 context/harness/state 管理，不是把完整歷史永久塞入 prompt。
4. 結構化輸出保證格式，不保證業務語意；應用程式必須驗證。
5. 半結構式訪談應同時保留固定核心議題與回答驅動的追問，並明確衡量覆蓋、深度、新資訊與受訪負擔。
6. agent 品質必須評估 trajectory（對話、工具、狀態改變）以及最後 outcome，不只看最後的文字。

因此 Caliburn 的差異化不應是模仿某家供應商的 Agent UI，而是把上述通用工程原則和 BEI 職能訪談、OCS/iCAP、公版職能標準結合，並用自己的工作分析資料證明哪個候選真的有效。

### 2.2 目前的主流趨勢是 single-agent 還是 multi-agent？

答案不是「multi-agent 已淘汰」。正確結論是：

- **single agent + tools + external state 是預設起點**；它較容易調試、評估、維護。
- 當任務可平行、子任務的 context 幾乎互不相干、或長時間研究的廣度確有收益時，才使用 subagents。
- 對 Caliburn 這種一對一長訪談，subagent 會複製／切碎同一份人員敘事，增加 context 漂移、成本與除錯難度，沒有先驗收益。

Anthropic 建議先採最簡解，只有必要時再加複雜度；OpenAI 也指出單一 agent 可透過逐步增加工具處理許多任務，並建議先建立 eval baseline 再優化架構。[A1][O1]

### 2.3 「LLM 不要當分析器」是否正確？

此句過度化。應修正為：

> LLM 可以做語意分析與推論；但不能讓未驗證的推論直接取代證據、持久 state 或文件事實。

LLM 最適合的責任是：辨識可追問之處、從敘事抽取候選事實、提出流程假設、挑選工具、決定下一個高價值問題、在事件結束後將證據編碼成候選 JD 元素。確定性程式則負責來源、權限、狀態轉移、去重、約束與落地。

---

## 3. 一手來源的共同結論與 Caliburn 映射

| 一手來源結論 | 對 Caliburn 的設計決策 |
|---|---|
| Context 是有限資源；每回合應從不斷成長的資料宇宙中挑選高訊號內容，而非只優化一句 prompt。[A2] | 把逐字稿留在 DB；prompt 只帶目前 episode、相關 evidence、未解缺口、JD 四態與最近對話。 |
| 長任務需要可恢復的 session 與明確 artifacts；session 不等於模型 context window。[A3][A4] | `turns` 為 append-only transcript；Evidence/Workflow/Inference 是可讀取的外部 state；摘要與 compaction 不是唯一資料來源。 |
| Agent 的核心是 model、tools、instructions；模型用工具取 context／採取動作，並在 guardrails 中執行 workflow。[O1] | 顧問保有 `read_state`、`search_reference`、`open_episode`、`close_episode` 等受限工具；不得直接寫 OCS。 |
| Single agent 應先於 multi-agent；以 eval baseline 決定何處需要較小或較強模型。[O1][A1] | 一個 Consultant loop；Extractor/Coder 是同一服務內的受限 pass，不是自主協商的 agent 群。 |
| Structured output 適合受限抽取；function calling 適合連接系統資料與動作。[O2] | Evidence/Inference/Coder 使用小 schema；工具動作走 function/tool calling；不以自由文本解析為寫入契約。 |
| JSON/schema 合格不代表語意正確；應在應用程式驗證值並處理 schema-compliant 的錯誤輸出。[G1] | 保留並延伸 `verify.py`；增加 quote、span、evidence-link、狀態轉移、人工內容保護與語意不變量。 |
| Agent eval 要看 trial、transcript、工具與最終 environment state，並混用程式、模型、人工 grader。[A5][O3] | JD outcome、來源、訪談行為、流程圖、工具選擇分開打分；建立 capability suite 與 regression suite。 |
| Anthropic Interviewer 將方法拆成 planning、adaptive interviewing、analysis；固定核心問題，追問依回答改變，分析輸出回扣研究計畫並附引文。[A8][A9] | 把「訪談計畫／agenda」、「即時提問」、「訪談後編碼」分成不同契約；不可要求同一次模型輸出同時自然聊天、完整抽取與完成 JD。 |
| Anthropic 2026 的 80,508 份訪談使用分工明確、人工驗證的 classifiers；不同問題使用 single-label 或 multi-label，未回答者排除，不把缺資料硬分到某類。[A9] | 每個 JD 元素有自己的 cardinality、unknown/insufficient 與 applicability 規則；工作類別、任務、技能、疑慮不可共用一個萬用分類 prompt。 |
| O*NET 以 incumbents、occupational experts、analysts 等多來源維護資料；task 的 relevance、frequency、importance 分開評定，且保留來源、樣本數與低精度訊號。[S4][S5][S6] | 「有做這件事」、「多常做」、「是否核心／重要」必須是可分離 evidence；不得從提及次數或語氣自動推論重要性。 |
| O*NET 將 tasks、work activities/context、skills、knowledge、abilities、work styles 分開；ESCO 將 occupation 與 skills/competences、knowledge 分開。[S1][S2] | OCS 的 T/P/O/K/S/A 保留；新增 workflow/evidence 作為上游模型；不要把 ability、skill、attitude 混成一個「能力」欄位。 |
| 最新多語 HR skill extraction 實驗仍顯示抽取難、資料敏感、規則可解釋、監督式模型在其資料上可達較高 F1；不能把一次 LLM 輸出當最終真相。[R1] | quote-first、可撤銷 inference、人工審閱與 eval-first 是產品要求，而非防衛性附加功能。 |

---

## 4. 現行 v3 的資產、缺口與本提案關係

### 4.1 必須保留的現行資產

現行 [`../design/interview-engine.md`](../design/interview-engine.md) 的下列決策正確，v4 不應倒退：

- 顧問無文件寫入權。
- `scribe/harvest → op → verify → _pending → 人審` 是唯一 AI 寫入路徑。
- `_pending.src.quote` 與 `ref_urn` 是可稽核的 provenance。
- episode/BEI 是比逐欄位訪談更自然的訪談單位。
- coverage、session state、review event 與 LLM call 都應可觀測。
- iCAP/O*NET/ESCO/SFIA/Bloom 等判準應當是 reference knowledge，不是模型憑空知識。

### 4.2 需修正的結構性缺口

現行設計曾明確退役 `interview_evidence`，將來源只放在 `_pending.src`。此做法能解決「JD 草稿的來源」，卻無法處理下列問題：

1. 同一段敘事支持多個任務、流程步驟、產出與指標時，JD 欄位不是合適的工作記憶體。
2. 尚未足以寫入 JD、但值得在後續驗證的資訊沒有穩定位置。
3. workflow、假設、矛盾、未解問題無法被 consultant 以結構化方式讀取。
4. 一次回答中的多意圖與跨 episode 關聯，容易被逐回合 scribe 壓扁成單一欄位操作。
5. 行為指標、K/S/A 與 attitude 是對多段證據的編碼結果，不必也不應全在第一次提及時落成 JD。

本提案不是恢復舊的「suggestion review table」，也不改變 Web 的 `_pending` 審閱模式；它新增的是**內部、append-only、以 evidence 為中心的工作模型**。JD 仍是唯一供使用者接受／拒絕的建議層。

### 4.3 目前程式與目標角色對照

| 現有元件 | 保留／改造後責任 |
|---|---|
| `consultant.py` | 保留為唯一對話主腦；改為讀 `state_view`，不只讀 document view。 |
| `scribe.py` | 改為 Evidence Extractor：先產出 quote-backed facts，而不是直接承擔完整 JD 編碼。 |
| `harvest.py` | 保留事件結束後的能力編碼定位；改讀 episode evidence 與 agenda。只有 C2 實驗才額外讀／寫 workflow graph。 |
| `agenda.py` / `coverage.py` | 保留確定性事實與 guardrail；coverage 改以 evidence sufficiency 衡量，不以線性欄位梯子衡量。 |
| `verify.py` | 保留六查概念；擴充 evidence link、span、state transition、不可把推論偽裝成事實等檢查。 |
| `_pending` / Web review | 不改；它是 Verified Job Model 對 OCS/JD 的待審投影。 |

---

## 5. 候選資料模型

### 5.1 候選物件超集；不是第一版全做

下表是用來比較 C1／C1A／C2 的**語意超集**，不是一張必須同時實作的資料表清單：

- C1 必要：`TranscriptTurn`、`Evidence`、`Inference`、candidate job items、`JDProjection`。
- C1A 另加：`InterviewAgenda`；它是目前主要對話候選。
- C2 才另加：`WorkflowGraph`；若第 22.7 節 gate 不通過，不得因本節有 schema 就實作。
- `VerifiedJobModel` 可先是 inference/job-item 的受控 view，不要求第一版另建服務或資料庫。

| 物件 | 變更語意 | 真正用途 | 適用候選／不可拿來當什麼 |
|---|---|---|---|
| `TranscriptTurn` | append-only | 保存員工原話與對話順序。 | 全候選；不可當作每次 prompt 的唯一記憶體。 |
| `Evidence` | append-only；可標無效／更正 | 有 quote/span 的最小工作事實與限定條件。 | C1+；不可放 LLM 自由推論或潤飾後 JD。 |
| `Inference`／candidate job item | 可撤銷 | 把 evidence 解釋為任務、產出、指標、K/S/A 或職類候選。 | C1+；不可偽裝成已確認事實。 |
| `InterviewAgenda` | reducer 可重算／版本化 | 追蹤主題、episode、sufficiency、矛盾、拒答、疲勞與停止訊號。 | C1A+；不可成為另一份自由文字摘要。 |
| `WorkflowGraph` | versioned | 在必要案例重建順序、分支、回工與交接。 | 僅 C2+；不可當固定職業模板或唯一真實流程。 |
| `VerifiedJobModel` | 僅受控更新 | 有足夠證據／確認的 job-item view，可投影 JD。 | C1+ 的邏輯 view；不可當未確認候選暫存區。 |
| `JDProjection` | 可再生 | OCS/JD `_pending` operations 與人工審閱狀態。 | 全候選沿用；不可當對話記憶體或 evidence database。 |

### 5.2 證據（Evidence）核心契約

Evidence 必須是「可在員工原話中定位」的原子主張；一筆 evidence 可連到多個後續 inference。下例只展示跨候選都不變的核心欄位；否定、更正、時間、典型性、歸屬、限定條件與 elicitation metadata 的完整候選契約以第 23.2 節 `Evidence v0.2` 為準。

```json
{
  "evidence_id": "ev_01J...",
  "session_id": "...",
  "episode_id": "ep_...",
  "kind": "action | decision | input | tool | stakeholder | output | standard | exception | frequency | scope | explicit_self_assessment",
  "claim": "從 ERP 匯出月結資料",
  "source": {
    "turn_id": 17,
    "speaker": "employee",
    "quote": "我會先從 ERP 把月結資料拉出來",
    "char_start": 3,
    "char_end": 18
  },
  "status": "accepted | duplicate | disputed | superseded",
  "entities": ["erp", "monthly_close_data"],
  "created_by": "extractor",
  "created_at": "2026-07-15T00:00:00Z"
}
```

不變量：

1. `quote` 必須是該 employee turn 的精確子字串；正規化規則需和既有 verifier 一致。
2. 沒有 quote 的內容不可成為 `Evidence`；只能成為 `Inference` 或 `question_gap`。
3. 一筆 evidence 不得同時聲稱多個無法獨立驗證的事實；應拆分。
4. evidence 不可被「改寫得更專業」後失去原意；JD 文案改寫發生在 Projection，不發生在 Evidence。
5. `explicit_self_assessment`（例如「我很有抗壓性」）是員工自述，不能直接升格為 ability/work style。

### 5.3 推論（Inference）最小契約

Inference 是 LLM 或規則根據 evidence 提出的可撤銷解釋。必須清楚與 evidence 分層。

```json
{
  "inference_id": "inf_01J...",
  "kind": "task_candidate | workflow_node | workflow_edge | output_candidate | indicator_candidate | knowledge_candidate | skill_candidate | ability_hypothesis | attitude_hypothesis | occupation_match",
  "value": "檢核月結資料一致性",
  "supported_by": ["ev_...", "ev_..."],
  "confidence": 0.78,
  "status": "candidate | needs_confirmation | corroborated | confirmed | rejected",
  "reason_code": "explicit_action_and_standard",
  "reference_links": [{"source": "iCAP", "urn": "...", "relation": "candidate_match"}],
  "created_by": "episode_coder"
}
```

不變量：

- `supported_by` 至少一筆 accepted evidence；否則不可產出成 JD。
- `confidence` 是 routing 訊號，不是事實機率，也不是人工核准的替代。
- 官方 reference 僅能標示 `candidate_match`／`terminology_normalization`；不可覆蓋員工 evidence。
- `ability_hypothesis`、`attitude_hypothesis` 預設 `needs_confirmation`；除非跨事件有足夠可觀察行為。

### 5.4 Workflow Graph 契約（僅 C2 條件式候選）

本節只定義「若 C2 通過入場 gate」時的最小契約，不構成實作授權。Workflow 不是只有 action sequence；它是由 evidence 驅動、允許分支、迴圈與交接的 session-local 有向圖。

```json
{
  "workflow_id": "wf_...",
  "name": "月結資料分析與報表交付",
  "status": "candidate | corroborated | confirmed",
  "nodes": [
    {"id": "n1", "type": "input", "label": "ERP 月結資料", "supported_by": ["ev_1"]},
    {"id": "n2", "type": "action", "label": "匯出資料", "supported_by": ["ev_2"]},
    {"id": "n3", "type": "validation", "label": "比對異常", "supported_by": ["ev_3"]},
    {"id": "n4", "type": "output", "label": "月度管理報表", "supported_by": ["ev_4"]}
  ],
  "edges": [
    {"from": "n1", "to": "n2", "type": "sequence", "supported_by": ["ev_1", "ev_2"]},
    {"from": "n3", "to": "n2", "type": "rework_if_failed", "supported_by": ["ev_5"]}
  ],
  "open_gaps": ["異常資料由誰最終核准？"]
}
```

允許的 node type：`trigger`、`input`、`action`、`decision`、`validation`、`handoff`、`output`、`exception`、`improvement`。

允許的 edge type：`sequence`、`condition`、`rework_if_failed`、`parallel`、`handoff_to`、`escalates_to`、`recurs`。

規則：

- 節點、邊都必須連到 evidence；沒有證據的圖元素只能是 `candidate`。
- 一個高階 task 可包含多個 workflow；一個 workflow 也可支持多個 task。
- 不要求每件工作都是線性流程；例外處理、回圈、審核與跨部門交接是高價值 evidence。
- 不建立數百個固定 workflow library。初期只維護上述小型 grammar；未來 reference workflow 僅作檢索候選，不作真相。

### 5.5 已確認職務模型（Verified Job Model）

這是唯一可投影 OCS/JD 的業務模型。其項目需要 evidence 與確認狀態，不直接等同於資料庫中的 OCS 文件。

```json
{
  "tasks": [{"id": "task_1", "text": "檢核月結資料並產出管理報表", "evidence_ids": ["ev_..."], "status": "confirmed"}],
  "outputs": [{"text": "月度管理報表", "task_ids": ["task_1"], "evidence_ids": ["ev_..."], "status": "confirmed"}],
  "indicators": [{"text": "發現數據不一致時回查原始來源並完成修正後再交付", "task_ids": ["task_1"], "evidence_ids": ["ev_..."], "status": "pending_review"}],
  "knowledge": [],
  "skills": [],
  "abilities": [],
  "attitudes": []
}
```

`confirmed` 的來源可為：員工明確確認、人工審閱接受、或產品日後定義的多事件 corroboration 規則。初期應以「員工明確確認／人工審閱接受」為主，避免過度自動化。

---

## 6. 職務元素的操作定義

O*NET 將工作資訊與工作者資訊分開：tasks/work activities/work context 屬於工作，skills/knowledge 屬於 worker requirements，abilities/work styles 屬於 worker characteristics。[S1] ESCO 亦把 occupation、skill/competence、knowledge 分開，且職業檔案將職能作為相關 reference，而不是個人實際工作的替代。[S2]

| 元素 | 在 Caliburn 的定義 | 合格證據 | 不可混淆為 |
|---|---|---|---|
| Task（任務） | 動詞＋工作對象＋目的的責任。 | 實際執行行動、頻率／範圍、成果。 | 單一軟體名稱或抽象能力。 |
| Workflow step（流程步驟） | 為完成任務而發生的輸入、行動、判斷、驗證、交接或例外。 | 事件中的順序、條件或回圈描述。 | 固定職業模板。 |
| Output（產出） | 可交付、可檢視或可驗收的名詞型結果。 | 員工說明交給誰、用於何處、如何驗收。 | 「處理」「協調」等活動。 |
| Indicator（行為指標） | 情境＋可觀察行為＋品質/驗收條件。 | 做法、檢查、判斷、錯誤處置、標準。 | 單純形容詞或 KPI 數字。 |
| Knowledge（知識） | 完成工作所需的原理、規則、制度、領域事實。 | 說明為何這樣做、依何規範判斷。 | 使用某工具的動作。 |
| Skill（技能） | 將知識／工具運用於完成工作的可訓練做法。 | 具體方法、工具、程序與成果。 | 長期穩定天賦。 |
| Ability（能力） | 跨情境、相對穩定的基礎能力。 | 多事件一致行為或員工確認。 | 一次事件完成得好。 |
| Work style / attitude（工作風格／態度） | 可從跨事件行為模式觀察的傾向。 | 反覆的選擇、回應壓力、責任承擔。 | 自我標籤「細心、抗壓」。 |

### 6.1 行為指標的生成規則

行為指標的最小句式為：

```text
在［情境／觸發］下，能［可觀察行為］，以［品質標準／驗收結果］。
```

範例：

```text
在月結資料不一致時，能回查 ERP 與原始單據、與財務確認差異，
完成修正後再交付管理報表。
```

此句是 JD 文案，非原始 evidence；它必須回鏈到至少一段「異常如何發現／如何處理／何時算完成」的 employee quote。若只有「我很細心」，只能保留為自我評估，不能生成此指標。

---

## 7. 訪談與狀態更新 runtime

### 7.1 每個 employee turn 的順序

現行 service 的「consultant 先回覆、後做 scribe」可讓顧問讀到原文，但顧問無法先讀取最新結構化 state。目標流程應調整為：

```text
① append TranscriptTurn（不可修改）
② Evidence Extractor：本回合抽取事實＋精確 quote/span
③ Evidence verifier：quote、來源、去重、注入防護、schema 檢查
④ State reducer：更新 episode、inference、agenda/sufficiency；C2 實驗才更新 workflow candidate
⑤ Consultant loop：讀取 state_view，必要時呼叫 reference/read 工具
⑥ Consultant 回覆：自然承接，最多一個前進問題，必要時 open/close episode
⑦ close/auto-close 時：Episode Coder 編碼 task/output/P/K/S/A candidates；C2 才另產生 workflow patch
⑧ Projection：符合規則者轉成既有 op → verify → `_pending`
⑨ 記錄 trace：context 摘要、tool call、state delta、驗證結果、成本/延遲
```

若 ②–④ 失敗，對話應 fail-open：顧問仍可依原文回覆，但不可把未驗證內容寫入 JD；失敗應可在 trace 中被觀測並於後續 backfill。

### 7.2 Episode 的生命週期

```text
candidate
  └─員工提及一段具體工作／顧問選定方向→ active
active
  ├─收集 context、action、decision、output、standard、exception
  ├─資訊足夠／員工換題／持續無收益→ closing
  └─episode coder 產生 evidence-backed candidates→ harvested
harvested
  ├─有未解關鍵問題→ held_for_followup
  └─可投影 JD→ projected
```

不以「某欄位填完」作為 episode 結束判斷；以 evidence sufficiency 作為判準。最小充分事件不必每次都包含所有元素，但至少應盡可能取得：做什麼、為何/在何情境、怎麼做、產出／結果。`standard` 與 `exception` 是高價值但可延後補問的欄位。

### 7.3 提問策略

顧問的下一題由 `state_view` 產生，而不是由固定欄位梯子產生。優先序：

1. 修正矛盾或不可信的 evidence。
2. 補足正在進行 episode 的最小結構。
3. 補足高頻／高影響任務的 output、standard、exception。
4. 用具體事件驗證高價值 inference（例如職類匹配、能力、工作風格）。
5. 擴張到尚未覆蓋的主要工作流程。
6. 收尾時讓員工檢視摘要並修正。

每次一個前進問題；可先自然回應或簡短轉述，但不能一次丟出多個 slot 問題。員工一句回答可更新多筆 evidence；系統不可因為只問了一題就只收一格。

### 7.4 Task decomposition policy

不使用大量預建 workflow library。對任何高階 task，模型僅在下列任一訊號出現時才把它標為 `decomposable_candidate`：

- 明示多個動作或先後順序。
- 明示輸入 → 處理 → 輸出。
- 包含決策、驗證、核准、例外或回工。
- 涉及多工具、多人或跨部門交接。
- 任務範圍很大但沒有可驗收產出。

若訊號不足，不強制拆解；保留員工原話的高階 task，詢問「這件事通常從哪一步開始？」。拆解目標是理解實際工作與找出高價值追問，不是把每件事情切成越多步越好。

---

## 8. Context engineering 與工具設計

### 8.1 Session、context 與摘要的關係

```text
Session store（完整、可回查）
├─ 全部 TranscriptTurn
├─ Evidence / Inference / Agenda 版本與事件；C2 才有 Workflow
├─ tool calls / verify outcomes / review events
└─ 原始 OCS/JD 文件版本

每次模型 context（有限、可丟棄）
├─ 穩定 system instructions
├─ 當前組織／職務背景與權限
├─ active episode 摘要＋相關原文
├─ 高相關 Evidence / Inference／Agenda slice；C2 可另帶極小 Workflow slice
├─ 未解 gaps、疲勞與 coverage signals
├─ JD 四態摘要（confirmed/pending/rejected/unknown）
└─ 最近少量 turns
```

OpenAI 的 conversation state 與 compaction 可協助減少長對話 context；但 compaction 產物是模型延續用的 opaque context，不應取代 Caliburn 自己可審計的 transcript 與 evidence store。[O4][O5] Anthropic 亦明確區分可恢復的 session log 與餵給模型的 context window。[A3]

### 8.2 工具最小集合

一人團隊不要先做 MCP 平台或數十個工具。初期只保留高價值、語意清楚、可評估的工具：

| 工具 | 類型 | 回傳／動作 | 重要限制 |
|---|---|---|---|
| `read_state` | data | episode、evidence、inference、agenda/sufficiency 的切片；C2 可選 workflow。 | 不回傳整場逐字稿。 |
| `read_transcript_slice` | data | 指定 turn/episode 的原文。 | 僅在需要核對時使用。 |
| `read_document` | data | OCS/JD 四態視圖。 | 不回傳不相關完整文件。 |
| `search_reference` | data | iCAP/O*NET/ESCO 候選與來源。 | 回傳 candidate，不寫入事實。 |
| `open_episode` | orchestration | 指定訪談主題／自由事件。 | 不寫文件。 |
| `close_episode` | orchestration | 結束事件並觸發 coder。 | 需寫明結束理由。 |
| `request_confirmation` | interaction | 請員工確認某個 inference。 | 不把「未回覆」視為確認。 |

Anthropic 的工具研究指出，工具要有清楚邊界、回傳有意義且 token-efficient 的 context，並用實際任務與 eval 迭代。[A6] 因此避免「列出全部職類／全部技能」這類巨大低訊號工具結果。

### 8.3 官方 reference 的正確角色

iCAP、O*NET、ESCO、SFIA、Bloom 的用途是：

- 統一術語。
- 提供候選職類、任務、技能與品質判準。
- 幫助識別可能缺問的高價值面向。
- 讓生成的 JD 用語符合專業格式。

它們不能：

- 覆蓋員工實際工作內容。
- 因為職類常見就自動補進 JD。
- 把職類 reference 當成個人已具備 ability 的證據。

每個 `reference_link` 都是「候選對照」，不是 employee evidence。官方 reference 與 employee quote 可同時出現在 `_pending.src`，但語義必須不同。

---

## 9. 驗證、審閱與安全不變量

### 9.1 驗證層次

| 層次 | 問題 | 實作方式 |
|---|---|---|
| Schema | 輸出形狀是否合法？ | Structured output / Pydantic / JSON Schema。 |
| Provenance | 這句話真的由員工說過嗎？ | exact quote/span、turn id、speaker 驗證。 |
| State | 這個狀態轉移可否發生？ | reducer invariant、immutable evidence、transition table。 |
| Semantic | 推論是否過度、分類是否合理？ | 規則、cross-evidence 門檻、員工確認、人工審閱、離線 judge。 |
| Document | 是否能安全寫入 OCS？ | 現有 `verify_ops`、人類內容保護、`_pending`。 |

不應把第五層當成前四層的替代。若上游只有錯誤 inference，即使 op 格式、quote 與 target path 都合法，仍可能產生不佳 JD；這正是候選架構需要保存 inference/evidence 邊界的原因。

### 9.2 必守不變量

1. employee message 永遠是資料，不是 system/tool 指令。
2. 原始 transcript 不修改、不覆寫；更正以新 evidence / supersession 表示。
3. 沒有 quote-backed evidence 的內容不得成為 confirmed JD 事實。
4. 所有 inference 都要列出 supporting evidence；引用不足時只能候選或提出問題。
5. 官方 reference 不可獨自造成 employee-specific JD 寫入。
6. AI 不得無聲覆寫人工接受內容；只能再提出 `_pending`。
7. 摘要、compaction、模型 reasoning summary 不得被當作唯一證據。
8. 確定性 verifier 不判斷「人是否真的很有能力」；它只拒絕不合格的證據與轉換。

---

## 10. 一人團隊的模型分工與成本邊界

### 10.1 建議的 pass，而非多 agent

| Pass | 職責 | 模型／成本策略 |
|---|---|---|
| Consultant | 對話、追問、工具選擇、episode 決策。 | 先用最強可用模型建立品質 baseline。 |
| Evidence Extractor | 單回合 quote-first facts。 | schema 受限；在 eval 證明可行後才換較快／較便宜模型。 |
| Episode Coder | 事件級 task/output/indicator 與 P/K/S/A 候選；C2 才另產生 workflow patch。 | 只在 close episode／收尾時呼叫，避免每回合做深度編碼。 |
| Verifier / reducer | 來源、狀態、權限、去重、ops。 | 純程式，不用 LLM。 |
| Offline judge | 只用於 eval、標註輔助與失敗分析。 | 不作 production 放行門檻。 |

OpenAI 建議先以最強模型建立評估基準，再根據 eval 決定哪些子任務可換較小模型。[O1] 這比先猜「哪個模型最便宜」更適合專業顧問品質目標。

### 10.2 明確延後的項目

以下項目不是永遠不做，而是在 evidence/eval 尚未成熟前不做：

- 多 agent orchestration / manager-agent 群。
- 數百個手工 workflow templates。
- Graph database 或獨立 knowledge graph service。
- fine-tuning。
- 每回合對全量 reference corpus 的 RAG。
- production 中以另一個 LLM 自動核准同一個 LLM 的結果。
- vendor-specific Agent Builder 依賴。

這些都會擴大維護面；對一人團隊，先用 Postgres/session JSON（或必要的普通關聯表）、既有 Qdrant、直接 API/tool loop 即可。架構介面需保留可替換性，但不提早為未知規模抽象。

---

## 11. Evaluation-first 開發

### 11.1 最小 golden set

先建立一組由領域專家／產品維護者人工標註的匿名訪談，不追求大量，先追求清楚的判準。建議最小集合覆蓋：

1. 員工一開始給出大量完整自述。
2. 一句話同時含多任務與多產出。
3. 高階複合任務，值得拆流程。
4. 原子任務，不應過度追問。
5. 有例外處理與回工。
6. 有跨部門交接與核准。
7. 僅有模糊形容詞，應要求事件。
8. 使用者否定模型假設。
9. 官方職類與實際工作不完全吻合。
10. 長對話後的 context 壓縮／回查。
11. 需要產生指標的高品質故事。
12. 疲勞、拒答或轉題時的 graceful close。

每案例至少標註：原始 quote、evidence、可接受／不可接受 inference、預期追問、最終 JD 重要項。只有 process-sensitive case 另標 workflow 關係（順序、條件、回工、交接），不得要求所有案例硬湊流程圖。

### 11.2 指標

| 維度 | 例子 | grader |
|---|---|---|
| Evidence precision/recall | 該抓的事實有抓到嗎？是否把推論當事實？ | 程式 + 人工抽樣。 |
| Quote validity | quote/span 是否真的存在於指定 employee turn？ | 程式。 |
| Inference grounding | 每個候選是否至少有正確 evidence 支持？ | 程式 + rubric judge + 人工校準。 |
| Workflow quality | 節點／邊是否支持真實工作理解，而非編造模板？ | 專家 rubric。 |
| JD coverage | 高影響任務、產出、標準、例外是否齊全？ | 專家 rubric。 |
| Indicator quality | 是否可觀察、與情境/行為/標準相連？ | rubric judge + 人工。 |
| K/S/A separation | 是否把工具、知識、技能、能力、態度混淆？ | rubric + taxonomy check。 |
| Conversation behavior | 是否一次一題、避免重問、適時結束 episode？ | trace grader。 |
| Safety/review | 是否只產生可追溯 `_pending`，不覆寫人工內容？ | 程式。 |
| Efficiency | 每成功案例的 turns、tokens、latency、工具數。 | trace metrics。 |

Capability eval 用於衡量「系統還不擅長、但希望做到」的案例；regression eval 用於確保已處理好的案例不退步。這正是 Anthropic 對 agent eval 的區分。[A5]

### 11.3 模型 judge 的限制

LLM judge 可幫助評分開放式項目，但不得成為唯一真相。使用方式：

- 優先程式檢查 quote、狀態、schema、ops、重複與來源。
- 對 workflow/JD/indicator 用明確 rubric 的 judge。
- 定期以人工標註案例校準 judge。
- judge 可跨供應商以減少同模型自評偏差，但只用於離線 eval。
- 讀 trace；不能只讀總分。

---

## 12. 分階段落地計畫

### Phase 0：可觀測性與基準

- 固定匿名 replay transcript 與目前 JD outcome。
- 為每回合記錄 input、context slice、tool call、scribe/harvest output、verify rejection、latency、cost。
- 建立上節最小 golden set 與人工標註格式。
- 不先改前端或 OCS schema。

完成條件：能重播目前問題案例，並指出是對話、抽取、驗證、coverage 或投影哪一層失敗。

### Phase 1：Evidence Layer

- 加入 `Evidence`／`Inference` 的 versioned state；初期可置於既有 session state 或小型關聯表。
- 將現有 quote verifier 抽成可重用 evidence validator。
- 把 scribe 的第一職責改成 evidence extraction；保留既有 direct-to-pending fallback 作短期相容路徑。
- 新增 `read_state` view，供 consultant 讀取。

完成條件：第一回合的豐富自述不會因「尚無任務殼」而丟失；每項候選可回查 employee quote。

### Phase 2：Evidence Sufficiency Agenda（不預設需要 Workflow Graph）

- episode 開／關仍由 consultant tool call 與 guardrail 共同控制。
- 建立 `InterviewAgenda`：追蹤核心主題、目前事件、evidence sufficiency、矛盾、拒答、已問問題、待追問與停止訊號。
- close episode 時先產生 candidate task/output/indicator/K/S/A；只有 process-sensitive eval 顯示必要時，才另產生 Workflow Graph。
- 把 `coverage` 改為 evidence sufficiency；一個回答可以產生多筆 evidence，一筆 evidence 也可以支持多個 inference，但每個主張仍需可獨立追溯。
- 將 unresolved gaps 與其優先級注入下一輪 state view；不要把整張 agenda 或完整逐字稿無差別塞回 prompt。

完成條件：行為指標有固定的事件級生成位置；同一故事能同時支持多個任務與技能而不重問；episode 能根據 sufficiency／邊際收益停止，而非填完固定欄位或耗盡硬編碼題庫。

### Phase 2b：Workflow Graph 實驗（條件式）

只有第 22.7 節的入場條件成立，才建立 session-local Workflow Graph prototype，並以 C1A 對 C2 的 process-sensitive golden cases 判斷是否保留。不得因文件已有 graph schema 就視為核准實作。

### Phase 3：Projection 與確認

- 僅從 corroborated/confirmed model items 投影 `_pending`。
- 對高風險 inference 觸發 `request_confirmation`。
- 將人工 accept/reject 回饋寫回 Verified Job Model，而不是只改 OCS 文件。

完成條件：人工拒絕可撤銷對應 inference，後續對話不再反覆建議同一錯誤內容。

### Phase 4：Eval gate 與模型路由

- 在 prompt、schema、模型、工具描述與 coverage 改動前後跑 capability/regression suite。
- 先以最強模型出 baseline，再以 eval 決定 Extractor 是否可降模型。
- 建立 trace dashboard／至少可檢索的失敗報表。

完成條件：每次改善能用明確指標說明收益與回歸，而非依單場主觀感受判斷。

### Phase 5：再決定是否擴張

只有以下條件成立才重新評估 workflow library、fine-tuning、多 agent 或 graph DB：

- golden set 顯示同一類 workflow 缺失反覆出現且無法靠 grammar/reference 解決。
- retrieval eval 證實 reference 搜尋是主因。
- 有足夠已審核標註資料，且 prompt/model/state 優化已飽和。
- 一人維護成本與產品收益有明確證據。

---

## 13. ADR 前需裁決的問題

1. Evidence/Inference 是否放在 `interview_sessions.ledger_state` 初期 JSON，或立即建小型 append-only table？提案：先以可 version 的 session state 落地，若需跨 session 查詢／分析再正規化。
2. `confirmed` 是否只接受人工審閱，還是允許員工確認？提案：兩者皆可，但要保留 confirmer 與時間。
3. 是否保留逐回合 direct-to-pending scribe？提案：Phase 1 暫留低風險內容，Phase 2 後僅讓 evidence-backed projection 寫入。
4. Workflow Graph 是否是可見 UX？提案：初期只作內部 artifact／debug view，不新增終端使用者 UI。
5. OCS schema 是否新增 workflow 欄位？提案：不新增；workflow 是訪談引擎內部資料，JD 只保留最終必要投影。
6. 哪些 item 需要員工確認？提案：職類匹配、ability/attitude、高影響任務與任何低 confidence inference 優先確認。

裁決後應新增 ADR；實作時同步更新 `docs/design/interview-engine.md`，避免現行 v3 與目標 v4 混淆。

---

## 14. 來源與註解

### Agent、state、context、工具與評估（一手）

- [A1] Anthropic, [Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents), 2024-12-19。workflow vs agent、先採最簡解、框架抽象成本。
- [A2] Anthropic, [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 2025-09-29。context 是有限資源；compaction、structured note-taking、按需取得 context。
- [A3] Anthropic, [Scaling Managed Agents: Decoupling the Brain from the Hands](https://www.anthropic.com/engineering/managed-agents), 2026-04-08。append-only session、harness、外部 context object 與可替換介面。
- [A4] Anthropic, [Effective Harnesses for Long-running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), 2025-11-26。長任務中的明確 artifacts、incremental progress 與 compaction 限制。
- [A5] Anthropic, [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), 2026-01-09。trial、trajectory、outcome、harness、code/model/human grader、capability/regression eval。
- [A6] Anthropic, [Writing Effective Tools for AI Agents](https://www.anthropic.com/engineering/writing-tools-for-agents), 2025-09-11。工具邊界、回傳 context、token efficiency、以 eval 改良工具。
- [A7] Anthropic, [Harness Design for Long-running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps), 2026-03-24。harness 元件必須逐一驗證是否仍為 load-bearing；模型進步後應移除失去收益的 scaffold。
- [A8] Anthropic, [Introducing Anthropic Interviewer: What 1,250 professionals told us about working with AI](https://www.anthropic.com/research/anthropic-interviewer), 2025-12-04。公開的 planning → adaptive interviewing → analysis 三階段案例；研究者審閱 interview plan、逐字稿分析回扣研究問題並附引文，也明列 self-report、selection、ordering 與 researcher interpretation 限制。
- [A9] Anthropic, [What 81,000 people want from AI](https://www.anthropic.com/features/81k-interviews) 與 [Methods Appendix](https://cdn.sanity.io/files/4zrzovbb/website/99156863ed4a812569fe00a2adfb1c93f7e5a911.pdf), 2026-03。80,508 份通過品質門檻的訪談、159 國、70 種語言；固定四個核心問題配合 adaptive follow-up；分工 classifiers、bottom-up category formation、人工 agreement 檢查、unknown/exclusion 與 ordering/dropout 限制。
- [O1] OpenAI, [A Practical Guide to Building Agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/)。model/tools/instructions、single-agent first、baseline 再做模型成本路由、分層 guardrails。
- [O2] OpenAI, [Structured Model Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。function calling 與 structured response 的不同用途；schema adherence。
- [O3] OpenAI, [Working with Evals](https://developers.openai.com/api/docs/guides/evals)。以明確 task、test input 與結果迭代 LLM 應用。
- [O4] OpenAI, [Conversation State](https://developers.openai.com/api/docs/guides/conversation-state)。持久 conversation 與 response chaining。
- [O5] OpenAI, [Compaction](https://developers.openai.com/api/docs/guides/compaction)。長對話 context 壓縮；compaction item 為模型延續而設。
- [O6] OpenAI, [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)，存取於 2026-07-15。task-specific eval、production/historical/human-curated datasets、持續評估、pairwise/pass-fail 與人工校準；同頁亦公告舊 Evals platform 將於 2026-10-31 唯讀、2026-11-30 關閉，因此本架構只依賴可攜的 dataset/grader/trace 契約，不綁定該平台。
- [G1] Google, [Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output?lang=rest), last updated 2026-07-07。JSON schema 與 function calling 的區別；應用程式仍須驗證 schema-compliant 但語意錯誤的輸出。

### 職務／技能標準（一手）

- [S1] O*NET Resource Center, [O*NET Content Model](https://www.onetcenter.org/content.html)。職務、工作活動、work context、tasks、skills、knowledge、abilities、work styles 的分層。
- [S2] European Commission, [ESCO Classification](https://esco.ec.europa.eu/en/classification) 與 [Occupations](https://esco.ec.europa.eu/en/classification/occupation_main)。目前 ESCO v1.2.1，最後更新 2025-12-10；occupation 與 knowledge/skills/competences 的關係。
- [S3] International Labour Organization, [ISCO concepts and definitions](https://ilostat.ilo.org/methods/concepts-and-definitions/classification-occupation/)。job 為一組 tasks and duties；occupation 為主要 tasks and duties 類似的 jobs。
- [S4] O*NET Resource Center, [Data Collection Overview](https://www.onetcenter.org/dataCollection.html)，頁面更新 2026-07-14。O*NET 以 incumbents、occupational experts、analyst ratings、職缺、NLP/ML 與其他多來源維護職業資料，不以單一 LLM 或單一自述作真相。
- [S5] O*NET 2024 OMB Package, [Occupation Expert Tasks Questionnaire](https://www.onetcenter.org/dl_files/omb2024/AppendixF-OE-Tasks.pdf)。task 定義為為達成 objective 而共同執行的 action(s)；逐項分問 relevance、frequency、importance，並允許受訪者補充最多五項未列任務。
- [S6] O*NET 30.3, [Task Statements](https://www.onetcenter.org/dictionary/30.3/text/task_statements.html) 與 [Task Ratings](https://www.onetcenter.org/dictionary/30.3/text/task_ratings.html)，2026。保留 task source、incumbent response count、sample size、standard error、confidence interval 與 low-precision suppression signal；Core task 依 relevance 與 importance 門檻區分。

### 領域方法與可追溯研究

- [R1] Vásquez-Rodríguez et al., [Skill Extraction from Resumes and Job Offers across Six Languages](https://aclanthology.org/2026.swisstext-1.10.pdf), ACL Anthology / SwissText 2026。多語、多領域、規則／semantic／supervised 方法及可解釋性的實務限制。
- [R2] McClelland, [Identifying Competencies with Behavioral-Event Interviews](https://journals.sagepub.com/doi/10.1111/1467-9280.00065), *Psychological Science*, 1998。BEI 的經典方法基礎；屬領域基準而非最新 LLM 技術。
- [R3] Senger et al., [Deep Learning-based Computational Job Market Analysis](https://aclanthology.org/2024.nlp4hr-1.1.pdf), NLP4HR 2024。skill extraction、identification、standardization、classification 的不同問題定義，以及 ESCO/O*NET 作為知識基礎的角色。
- [R4] Li et al., [LLM-based Business Process Models Generation from Textual Descriptions](https://aclanthology.org/2025.findings-ijcnlp.31/), Findings of IJCNLP-AACL 2025。文字到流程模型在複雜控制流與不完整輸入下仍需系統評估；few-shot、CoT、fine-tuning 的收益隨情況不同。
- [R5] Kourani et al., [Evaluating Large Language Models on Business Process Modeling: Framework, Benchmark, and Self-improvement Analysis](https://link.springer.com/article/10.1007/s10270-025-01318-w), *Software and Systems Modeling*, 2025。不同前沿模型的流程建模表現差異大；以 ground truth/event log conformance 做可重複比較，而非以單一模型結果定論。
- [R6] Wuttke et al., [AI Conversational Interviewing: Transforming Surveys with LLMs as Adaptive Interviewers](https://aclanthology.org/2025.latechclfl-1.17/), LaTeCH-CLfL / ACL 2025。公開 prompt、資料與評估；一次一題、避免 leading、適度 active listening 與 context-dependent probe；也實證小改 prompt 可造成追問退化，必須以逐 turn 人工編碼與受訪體驗共同評估。
- [R7] Huang et al., [Teaching Language Models To Gather Information Proactively](https://aclanthology.org/2025.findings-emnlp.843/), Findings of EMNLP 2025。把「辨認缺口並以 targeted questions 引出隱性知識」定義成獨立能力；支持 gap-driven clarification，但其 fine-tuning 結果不可直接外推為 Caliburn 架構收益。
- [R8] Seo et al., [FQ-Eval: Building Evaluation Dataset for User-centered Follow-up Question Generation](https://aclanthology.org/2025.emnlp-industry.188/), EMNLP Industry 2025。以使用者研究建立 follow-up 評估準則並使用 pairwise/score 評測；證明只看 topical relevance 不足，但其一般聊天五準則需改寫為工作分析專用 rubric。
- [R9] Anugraha et al., [SparkMe: Adaptive Semi-Structured Interviewing for Qualitative Insight Discovery](https://arxiv.org/abs/2602.21136), Stanford arXiv preprint, 2026-02。提出 coverage + emergence − interview cost 的 utility、agenda、coverage-aware stopping 與 rollout planner；有 70 人／7 職業 user study，但尚未同行評審、未直接對比專家訪談，模擬與 LLM-judge 亦有外推限制，因此只作候選與 eval 設計來源，不作採用 multi-agent 的依據。
- [R10] Liu et al., [Bridging Information Gaps with Comprehensive Answers](https://aclanthology.org/2025.starsem-1.2/), *SEM* / ACL 2025。以「目前回答 vs 目標充分回答」辨識 information gap，再產生補缺追問；支持先形成 gap 再問，而非自由生成下一題。

---

## 15. 文件維護規則

- 本檔是「為什麼與要採什麼」的研究／提案；不是 code of record。
- 一旦 ADR 裁決，將裁決寫入 `docs/adr/`，並把真正 runtime 搬入／更新 `docs/design/interview-engine.md`。
- 每次 provider API、模型或工具架構調整，只有在它改變上述設計決策時才更新本檔；不要把模型型號、價格或瞬時 benchmark 寫成長期架構事實。
- 實作任何 Phase 時，該 PR 必須同時更新設計文件、eval cases 與本檔的「現況／提案」界線。

---

## 16. 實驗用 state envelope 與 reducer 規格（候選）

本節刻意比概念設計更精確，但仍是待 eval 的候選契約。它不是要求第一版立刻建立 graph database；C1/C1A 可使用普通 Postgres JSON／關聯表，且 `workflows` 在 C2 以前不存在。實驗可以改 storage，但同一候選內**不能自行改變語意與不變量**，否則比較失去效度。

### 16.1 Session state envelope

```json
{
  "schema_version": 1,
  "session_id": "sess_...",
  "document_id": "doc_...",
  "last_reduced_turn_id": 17,
  "active_episode_id": "ep_03",
  "episodes": [],
  "evidence": [],
  "inferences": [],
  "agenda": {},
  "job_model": {},
  "rejected_fingerprints": [],
  "projection_links": [],
  "audit": []
}
```

C2 prototype 只在上述 envelope 額外加入 `"workflows": []`。C1 不要求 `agenda`；為了讓 C1 與 C1A 可比較，C1 可把該欄留空，但不可暗中使用 agenda policy。

欄位規則：

| 欄位 | 擁有者 | 寫入時機 | 不能做的事 |
|---|---|---|---|
| `last_reduced_turn_id` | reducer | 成功處理 employee turn 後。 | 因 LLM timeout 跳過未處理 turn。 |
| `active_episode_id` | agenda tool reducer | `open_episode`／`close_episode` 成功後。 | 由 scribe 猜測並改寫。 |
| `evidence` | evidence reducer | evidence verifier 通過後 append。 | 直接覆寫／潤飾舊 quote。 |
| `inferences` | inference reducer | extractor/coder 的候選通過 grounding 檢查後。 | 未附 evidence 就設為 confirmed。 |
| `agenda` | agenda reducer | evidence／episode 更新後依 reason codes 重算；C1A 才啟用。 | 讓 LLM 用一段摘要直接覆寫；把未問當已答。 |
| `workflows`（可選） | workflow reducer | 僅 C2：episode coder 或明確 workflow patch 後。 | C1/C1A 先行實作；把 reference template 當成已發生流程。 |
| `job_model` | confirmation/projector reducer | corroboration、員工確認或 review event 後。 | 直接承接 model 的自由文字。 |
| `rejected_fingerprints` | review reducer | 人工拒絕後。 | 跨 tenant 或跨 document 共用。 |
| `projection_links` | projector | 每個 job-model item 對應 `_pending` op 後。 | 因重跑而重複新增同一項。 |
| `audit` | service | 每次 reducer/tool/projector 變更。 | 只記最終成功、不記 rejection。 |

### 16.2 版本與 id 規則

1. `TranscriptTurn.seq` 是本 session 的單調遞增序號；不得重用。
2. `Evidence`、`Inference`、`Episode`、`Workflow`、`JobModelItem` 使用穩定 UUID/ULID；不得以 array index 當永久 id。
3. state 每次成功 reduce 都產生 `state_revision`；所有 tool call、projection 與 review event 都記錄其讀取 revision。
4. 若兩個請求競爭更新 session，使用既有 optimistic locking；衝突時重讀最新 state，**重跑純 reducer**，不得盲目重送舊 op。
5. schema 升級只能以 migration/reducer 轉換；禁止在 runtime 以大量 `dict.get()` 默默兼容未知版本。

### 16.3 Evidence reducer 的確定性演算法

Evidence Extractor 只提出候選；reducer 才決定是否進 state。

```text
reduce_employee_turn(state, employee_turn, extractor_output):
  1. assert employee_turn.seq == state.last_reduced_turn_id + 1
     或把缺漏 turn 依序補處理；不可越過。
  2. 對每筆 candidate 驗證：schema、speaker=employee、turn_id、quote/span。
  3. 對通過者生成 canonical fingerprint：
       tenant + session + turn + kind + normalized quote span
  4. 若 fingerprint 已存在：記 duplicate audit，不新增 evidence。
  5. 若只是同義但 quote 不同：保留兩筆 evidence，建立 optional corroborates link；
     不可因 embedding 相似就刪掉其中一筆。
  6. 若與既有 evidence 明確矛盾：兩者都保留，標記 disputed，
     建立 contradiction gap；不可採 last-writer-wins。
  7. 將 accepted evidence append；更新 episode 的 touched evidence ids。
  8. 從 accepted/disputed evidence 純函式重算 coverage 和 open gaps。
  9. 寫 audit event，最後才更新 last_reduced_turn_id/state_revision。
```

`normalized quote span` 可使用既有 quote verifier 的 whitespace／全半形正規化，但 audit 必須同時保存原始 quote。永遠以 employee 原字串作最後比對，不以 embedding 相似度當來源驗證。

### 16.4 衝突與更正規則

員工可能在後續回合更正自己；這不是資料錯誤，而是訪談應追蹤的業務狀態。

| 情況 | state 行為 | 顧問後續行為 |
|---|---|---|
| 「其實不是每天，是每月一次」 | 舊頻率 evidence 保留並標 `superseded_by`；新 evidence append。 | 在有影響時簡短確認，更新 task frequency candidate。 |
| 「不是我核准，是主管核准」 | 舊 `decision/authority` evidence 標 disputed；新增 handoff/authority evidence。 | 補問實際責任界線，避免把核准權寫進 JD。 |
| 使用者否認模型的 workflow 推論 | 相關 inference → `rejected`，加入 document-local fingerprint。 | 不重問同一假設；改問開放式下一步。 |
| 人工拒絕 `_pending` | linked job-model item/inference → `rejected_by_reviewer` 或 `needs_clarification`。 | 不因 backstop 再自動補回；只有新 evidence 才可解除。 |

### 16.5 Inference 狀態機

```text
candidate
  ├─沒有合格 evidence / verifier fail → rejected
  ├─有一筆 evidence，但推論影響大或可替代解釋多 → needs_confirmation
  ├─有多筆獨立 evidence / 規則門檻足夠 → corroborated
  └─員工明確確認或人工接受投影 → confirmed

needs_confirmation / corroborated
  ├─員工或人工否定 → rejected
  ├─新證據矛盾 → disputed
  └─新證據支持／確認 → confirmed

confirmed
  ├─新 evidence 表示內容已變更 → superseded
  └─不可被 model 自行降回 candidate；需明確 reducer event。
```

建議初期門檻：

- `task_candidate`：一筆直接 action evidence 即可候選；要投影至少需有 action + object，或員工確認。
- `output_candidate`：必須有明確交付物／使用者／驗收任一證據；僅「我處理」不可產生 output。
- `indicator_candidate`：必須有 observable action，且有 standard、exception handling、verification 或明確 result 之一。
- `knowledge_candidate`：必須有規則／原理／制度／領域概念 evidence，或員工確認；僅看到工具名稱不可推知 knowledge。
- `skill_candidate`：必須有「如何做」的實際操作 evidence；僅 task title 不足。
- `ability_hypothesis`／`attitude_hypothesis`：至少兩個不同事件的可觀察行為，或員工明確確認後才可投影；單事件預設不投影。

門檻是可調參數，但每個調整都需有 golden eval 佐證。

---

## 17. JD Projection 規格：從 job model 到既有 `_pending`

### 17.1 可投影條件

`_pending` 是待人審的建議，所以不必等 item 已被人工接受；但 item 至少必須 `corroborated` 或有明確 employee confirmation。下列矩陣是唯一允許路徑：

| Job model status | 可產生 `_pending`？ | 理由 |
|---|---|---|
| `candidate` | 否。 | 還只是單次模型猜測。 |
| `needs_confirmation` | 原則否；可由 `request_confirmation` 追問。 | 防止高影響猜測直接污染 JD。 |
| `corroborated` | 是，標 `_pending`。 | 有足夠 evidence，仍交給人審。 |
| `confirmed` | 是；若已存在 accepted OCS 值則不重複新增。 | 內容已具較高語意信心。 |
| `disputed/rejected/superseded` | 否；若先前已投影，產生受控 `mod/del` 建議。 | 不保留已失效內容。 |

### 17.2 Projection 規則

```text
project_item(item, current_document):
  1. assert item.status in {corroborated, confirmed}
  2. assert all required evidence are accepted and source-valid
  3. 取得 task/document target；若目標不存在，不可猜 array index
  4. 以 semantic fingerprint 對 accepted、pending、rejected 找重複或近似項
  5. 若已有相同 accepted 項：不寫 op
  6. 若已有相同 pending 項：更新 projection link，不重複寫 op
  7. 若已有 rejected fingerprint 且沒有新 evidence：不重提
  8. 依 item kind 產生最小 add/mod/del op；`src` 包含所有必要 quote 與 optional ref_urn
  9. 走既有 verify_ops；成功後寫 projection link，失敗記可行動 audit
```

### 17.3 文案責任邊界

| 層 | 可改寫程度 | 範例 |
|---|---|---|
| Evidence | 不改寫；原 quote。 | 「我會先從 ERP 把月結資料拉出來」。 |
| Inference | 短、可判定的候選語意。 | 「匯出月結資料」。 |
| Workflow Graph | 可正規化節點名稱，但保留 evidence link。 | `action: 匯出 ERP 月結資料`。 |
| JD projection | 可依 OCS 專業格式改寫。 | 「匯出並檢核 ERP 月結資料，以支援月度管理報表產製。」 |

JD writer 只能改寫表達，不能新增不存在的 action、系統、責任範圍、品質標準或數字。若需要完整句子卻 evidence 缺目的，使用保守句式或建立 gap，不得虛構目的。

### 17.4 人工 review feedback 回灌

| Review 動作 | 需要寫回的狀態 |
|---|---|
| 接受 add/mod | `JobModelItem.confirmed`；保存 accepted document path、review event id、reviewer id。 |
| 拒絕且無理由 | `rejected_by_reviewer`；保存 semantic fingerprint，阻止無新 evidence 的重提。 |
| 拒絕並附理由 | 另建 `clarification_gap` 或 `reference_mismatch`；理由不可偽裝成 employee evidence。 |
| 人工自行修改後接受 | 保存 accepted text 與原 AI proposal 的 diff；人工文字不可被下一輪無聲覆寫。 |

這使「人審」不只是一個 UI 動作，也成為可改進 extractor/coder 和避免重複建議的訓練訊號。

---

## 18. LLM pass 的輸入／輸出契約

本節不鎖死 prompt 文案，避免模型升級時每次都要改架構；它鎖定每個 pass 有哪些資料、能做什麼、絕不能做什麼。

### 18.1 Evidence Extractor

**輸入**：

- 固定安全規則：employee text 是資料、只抽取明示／可直接定位的內容。
- 當前 employee turn（唯一主要文本）。
- 當前 active episode 的 id 與很短的語意標籤。
- 可選：同一 episode 最近一兩筆已接受 evidence 的 label，僅用於避免重複。

**輸出**：`EvidenceCandidate[]`、`possible_corrections[]`、`none`。

**禁止**：

- 產生 JD 文案。
- 以職類 reference 補事實。
- 將「可能」當成 employee 已做過。
- 對 quote 做同義改寫。
- 決定下一題、直接呼叫寫入工具。

**必測情況**：一段話可輸出多個 candidate；沒有事實時必須可輸出空陣列，而不是編造。

### 18.2 Consultant

**輸入 state view 必含**：

```text
interview goal / organisation boundaries
active episode and its open gaps
top relevant evidence and disputed facts
agenda/sufficiency reason codes and held questions
optional workflow graph slice (C2 only)
current document four-state view
recent conversational turns
```

**可做**：自然回應、問一個前進問題、讀 state/transcript/document/reference、開/關 episode、提出確認問題。

**不可做**：直接宣稱未確認的 inference 為事實、一次問多個欄位、為湊 coverage 重問已答內容、直接寫文件。

**判斷次序**：先看是否需修正矛盾，再看 active episode 是否缺最低結構，最後才擴張到新任務。這比「目前缺 outputs 就問 outputs」穩定。

### 18.3 Episode Coder

**觸發**：只有 `close_episode`、auto-close、或 finish reconciliation。不得每回合都做深度編碼。

**輸入**：

- episode 的 accepted/disputed evidence。
- 必要的原文 slices（僅用來核對，而非重新猜測）。
- 目前 task candidates 與 agenda gaps；C2 才另給 workflow graph。
- O*NET/ESCO/iCAP 的小範圍 reference candidate。
- behavior-indicator、K/S distinction 等固定判準。

**輸出**：inference candidates、clarification gaps；每個候選都列 `supported_by`。只有 C2 mode 可另輸出 workflow patch。

**不可做**：從 reference 未提及內容建立任務；把一般工作常識加入 employee-specific JD；自行確認 ability/attitude。

### 18.4 Projector

Projector 優先是確定性程式。若需 LLM 將 candidate 改成專業句子，LLM 必須收到：目標 OCS 欄位規則、item、linked evidence、不可增加事實指令；其輸出再走 deterministic source/permission verifier。

---

## 19. 端到端 worked example（規格範例）

以下範例不是事實資料，也不是 golden answer；它先展示 C1/C1A 必須保存的 Evidence／JD 邊界，再以可選 C2 圖示說明何時 workflow 關係可能有額外價值。

### Turn 12：員工原話

> 每個月結帳前，我會先從 ERP 拉出銷售和庫存資料，在 Excel 對帳；如果差異很大，就找財務確認。確認沒問題後，我用 Power BI 做月報給營運主管看。

### Step A：Evidence Extractor 的合法輸出

```text
ev1 input       「從 ERP 拉出銷售和庫存資料」
ev2 action      「在 Excel 對帳」
ev3 exception   「如果差異很大，就找財務確認」
ev4 validation  「確認沒問題後」
ev5 action      「用 Power BI 做月報」
ev6 output      「月報給營運主管看」
ev7 frequency   「每個月結帳前」
```

Extractor 不可輸出「具備資料建模能力」「負責跨部門溝通」「確保資料正確」；這些是 inference 或後續需要補問的內容。

### Step B：Reducer、Agenda 與可選 C2 Workflow Graph patch

C1/C1A 必須先保存 ev1–ev7；C1A 會把「差異門檻、月報用途、發布權限」列為有 reason code 的 gaps。以下流程圖只在 C2 prototype 產生：

```text
input: ERP 銷售／庫存資料
  → action: 匯出資料
  → validation: Excel 對帳
  → condition: 差異很大？
       ├─是 → handoff: 與財務確認
       └─否／已確認 → action: Power BI 製作月報
  → output: 提供營運主管的月報
```

open gaps：

- 「差異很大」如何判定？
- 月報包含什麼決策用途？
- 財務確認後由誰決定資料可發布？

### Step C：Consultant 的下一題

可問：

> 你判斷「差異很大」時，通常看哪些數字或規則？

不可一次問：

> 你的 KPI 是什麼、會用什麼 DAX、你要跟哪些部門溝通、你的技能有哪些？

### Turn 13：員工原話

> 通常是跟上個月差超過 10%，或庫存金額跟財務帳不一致；我會先回查明細，真的對不起來才請財務調整。主管主要拿月報看哪些產品要補貨。

### Step D：新增 evidence 與 inference

合法 evidence：10% 門檻、庫存與財務帳不一致、先回查明細、請財務調整、月報用於補貨決策。

可產生的 inference：

```text
task_candidate:
  「整合並檢核銷售與庫存資料，產出月度營運報表」
  supported_by: ev1, ev2, ev5, ev6, ev7

indicator_candidate:
  「發現月度差異超過 10% 或帳務不一致時，先回查明細，
   必要時與財務協作完成調整後再產出報表。」
  supported_by: ev2, ev3, ev4, turn13 evidence

knowledge_candidate:
  「月度銷售、庫存與財務帳務一致性規則」
  supported_by: turn13 evidence

skill_candidate:
  「運用 Excel 進行資料對帳，並使用 Power BI 製作營運月報」
  supported_by: ev2, ev5
```

不應產生：

```text
ability: 「具備卓越分析能力」
attitude: 「高度責任感」
```

因為現有 evidence 尚不足以證明跨情境穩定特質。

### Step E：Projection

若 task／indicator 已達 `corroborated`，可以產生 `_pending`，並在 `src.quote[]` 放入上述原話。若員工或人工拒絕「10%」是一般規則而非其責任，相關 indicator 必須退回 `needs_clarification`，不是只把數字從句子刪掉後繼續自動寫入。

---

## 20. 實作驗收與測試案例

### 20.1 Reducer 單元測試

| 測試名稱 | 輸入 | 必須結果 |
|---|---|---|
| `test_first_rich_turn_is_retained_without_task_shell` | 空白 OCS + 首回合包含多項工作。 | Evidence 全被保留；不得因無任務 index 而只輸出 `none`。 |
| `test_quote_must_be_exact_employee_span` | model 捏造或截錯 quote。 | verifier reject；不寫 evidence、不寫 pending。 |
| `test_same_quote_is_idempotent` | 同 turn extract 重試兩次。 | 一筆 evidence、一筆 duplicate audit。 |
| `test_distinct_quotes_can_corroborate` | 兩回合說同一工作。 | 兩筆 evidence 保留並可支援同一 inference。 |
| `test_correction_does_not_delete_history` | 每日更正為每月。 | 舊 evidence superseded、新 evidence accepted、frequency gap 解除。 |
| `test_inference_without_evidence_cannot_project` | candidate 無 `supported_by`。 | 不產生 `_pending` op。 |
| `test_rejected_item_needs_new_evidence_to_reappear` | reviewer reject 後 backstop 重跑。 | 不重提；除非有新 evidence id。 |
| `test_human_accepted_content_is_not_silently_overwritten` | accepted path + 新 AI 文案。 | 只能生成待審 mod，不能直寫。 |

### 20.2 Episode／對話整合測試

| 場景 | 斷言 |
|---|---|
| 多意圖回答 | 一句話至少可更新 task、output、tool、stakeholder 等多筆 evidence。 |
| 事件深挖 | 顧問優先補 action/output/standard/exception，不在每一槽各問一次。 |
| 回答已足夠 | episode close，觸發 coder，而非無限追問。 |
| 使用者轉題 | active episode 進 held/closed，新的 evidence 不遺失。 |
| 模糊形容詞 | 顧問要求具體事件；不能直接產生 ability/attitude。 |
| reference 不匹配 | iCAP/O*NET/ESCO 僅保留 candidate link，不能自動新增未提及職責。 |
| 長對話 | context view 不含完整 transcript；工具可精準回讀前一事件原文。 |

### 20.3 Release gate

任何修改 consultant prompt、extractor schema、agenda／可選 workflow reducer、reference retrieval、模型路由、verify 規則時，至少要：

1. 跑 reducer 單元測試。
2. 跑 regression golden set，quote validity 與 safety 需 100% 通過。
3. 跑 capability set，報告 evidence、indicator、對話行為分數的變化；C2 實驗另報 workflow 關係分數。
4. 人工閱讀至少數個成功與失敗 trace；確認 grader 沒有把合理行為誤判。
5. 記錄成本、turn 數與 latency，避免品質改善是靠不可接受的訪談膨脹換來。

---

## 21. 下一份文件與實作順序

本檔已定義研究結論與實作級語意，仍不應直接當作現行 code 說明。方向正式裁決後，文件鏈應為：

```text
本研究 spec
  └─ ADR：C0/C1/C1A/C2 採用結果、Evidence storage、projection 門檻
       └─ design/interview-engine.md：實際 endpoint、DB、runtime、工具與失敗語義
            └─ plan：可執行、可驗證的 Phase 0 → Phase 4 工作拆分
                 └─ tests/evals：golden data 與 release gate
```

在 ADR 尚未裁決前，任何實作不得宣稱 `Evidence`、`InterviewAgenda`、`WorkflowGraph`、`VerifiedJobModel` 已被核准或已經存在；它們目前是不同候選中的實驗契約。

---

## 22. 反證式架構驗證：不把「看起來完整」誤當「最優解」

### 22.1 為何本節必要

Caliburn 已有「研究後看似合理、實作後效果卻很差」的經驗。因此本檔不能把 Evidence-first／Agenda／Workflow 任一組合當成已證明的最佳架構，更不能因為術語完整就全量重構。

最新研究也支持這個警覺：流程模型可從文字中生成，但不同 LLM 的表現差異明顯，流程邏輯越複雜、輸入越不完整，可靠性越不能由漂亮輸出推定。[R4][R5] Anthropic 2026 進一步指出，harness 的每一個元件都隱含「模型做不到什麼」的假設，必須逐一壓力測試；模型能力改變後，原本有用的 scaffold 也可能變成成本與延遲。[A7]

所以此提案的正確地位是：

```text
研究支持的原則  ≠  已證實最優的 Caliburn 組合
架構假設          →  預先定義的 replay eval  →  保留、簡化或淘汰
```

### 22.2 可信度分層：哪些應先做，哪些必須先證明

| 元件／主張 | 外部證據強度 | 對 Caliburn 的目前結論 | 實作決策 |
|---|---|---|---|
| quote-backed provenance、受控寫入、人工審閱 | 高；專業文件與 agent reliability 都需要可稽核來源。[A5][G1][R1] | 現有 `_pending` 已證明此層健康。 | **保留並擴充**。 |
| transcript 與模型 context 分離；外部 durable state | 高；Anthropic/OpenAI 都將 session/context management 視為長任務基本能力。[A2][A3][O4][O5] | 目前只靠 JD 與近期 turns 不足以承擔長訪談。 | **Phase 1 必做**。 |
| Evidence 與 Inference 分層 | 高；由 schema 不等於語意正確、HR 抽取可解釋性不足，以及 provenance 需求共同支持。[G1][R1] | 是防止「推論=事實」的最小必要結構。 | **Phase 1 必做**。 |
| episode 級編碼，而非線性欄位填寫 | 中高；BEI 與現有事故都支持。[R2] | 已有 episode 元件；需改變其資料輸入。 | **Phase 2 必做**。 |
| 內部 Workflow Graph | 中；流程建模研究證明其可行與有價值，但也顯示模型／輸入／邏輯複雜度會強烈影響品質。[R4][R5] | 對排序、分支、回工、交接可能很有用；尚未證明每場訪談都需要完整圖。 | **作為可驗證選項，不是 Phase 1 硬需求**。 |
| BPMN/POWL 等正式流程語言 | 中於流程工程、低於此產品初期需求。 | 對 JD 生成功能過重；使用者也未要求流程執行。 | **不做**；最多離線 eval/研究使用。 |
| 多 agent manager/planner 群 | 條件式；對平行研究／多小時自主任務可有收益，不是預設。[A1][A7] | 一對一訪談的核心 evidence 會被拆散，且一人難以維護。 | **不做**。 |
| 專屬 Workflow Library | 缺乏 Caliburn 專屬資料證明，維護成本高。 | 可能把標準工作流程投射成員工事實。 | **不做**；先用 grammar + reference candidate。 |
| fine-tuning | 在流程建模研究可提高某些 benchmark 準確率，但需要足夠同分佈標註資料。[R4] | 尚無足量、審核一致的 Caliburn gold data。 | **延後**。 |

這個表的關鍵修正是：**最小可行實驗是 Evidence-first，不是 WorkflowGraph-first。**

### 22.3 必須比較的候選架構

不可只測新架構與人工直覺。要以相同資料、相同產品限制，比較下列候選：

| 候選 | 組成 | 回答的問題 | 是否建議實作 |
|---|---|---|---|
| C0：現行 v3 修補版 | 既有 consultant/scribe/harvest/verify；修正已知 incident bug。 | 單純修 bug 是否已足夠？ | 作為 baseline/replay 對照。 |
| C1：Thin Evidence-first | C0 + append-only Evidence + Inference + `read_state` + evidence-backed projection；**不持久化 Workflow Graph**。 | 分離事實與推論是否就是主要品質槓桿？ | **優先實作**。 |
| C1A：Evidence + Sufficiency Agenda | C1 + topic/episode coverage、缺口、矛盾、已問問題、拒答與停止訊號；仍是 single consultant loop。 | 明確 agenda 是否改善追問、轉題與停止，而不需要 graph／planner？ | **最新研究後的主要對話候選**。 |
| C2：Evidence + Workflow Graph | C1 + 只在 episode close 後生成的 graph node/edge。 | 流程圖是否真的改善順序、例外、交接與行為指標？ | 只在 C1 的失敗 trace 支持時實作。 |
| C2P：Deliberative planner prototype | C1A + 每數 turn 比較候選追問方向；可先離線，不要求 multi-agent。 | 對 emergent work 是否有可重複的額外資訊收益？ | 只在 C1A 過度線性或漏 emergent themes 時測。 |
| C3：正式流程模型／模板庫／多 agent | C2/C2P + BPMN/POWL、流程模板、planner/evaluator agents 等。 | 進一步複雜度是否帶來大於成本的收益？ | 初期禁止；除非較簡候選已達瓶頸且 eval 支持。 |

目前的推薦不是「直接做 C2/C2P」，而是：

> **先把 C1 做成可重播、可評估的最小垂直切片，再把 C1A agenda 當獨立變因比較；讓 C2/C2P 必須靠失敗證據取得入場資格。**

這保留了 WorkflowGraph 的研究價值，也避免又一次「大架構先行、問題反而更難定位」。

### 22.4 統一實驗協定

每個候選必須遵守以下條件，否則比較沒有意義：

1. 使用同一批匿名化 transcript、相同 organisation/reference pack、相同初始 OCS 文件。
2. 固定當輪可用工具、最大 turn budget、context budget、模型版本／推理設定；測試變因必須是候選架構本身。
3. 對 stochastic model 進行多 trial；不得挑選單一最好對話當成果。
4. golden case 需有人工標註的 evidence spans、可接受／不可接受 inference、重要 task/output/indicator 與預期追問方向。
5. 讀完整 trace：員工回答、context slice、tool call、state delta、候選、verify 結果、JD ops、人工 review outcome。
6. 程式 grader 負責 quote、重複、狀態、權限與寫入；模型 judge 只評開放式品質，且需以人工案例校準。
7. 每一個架構元件都要有明確假設、metric、預期收益與 kill condition。

流程建模研究採用 ground truth 與 conformance/evaluation 比較，而不是宣告某個模型天然最好；Caliburn 雖非可執行 BPMN 系統，也應採相同精神，以已標註 evidence 與 JD outcome 作為自身 ground truth。[R5]

### 22.5 不可妥協的 gate

以下不是「分數較高即可接受」，而是任何候選都必須全部通過：

| Gate | 要求 | 原因 |
|---|---|---|
| Provenance safety | quote/span/turn/speaker 驗證為 100%；無來源項不可投影。 | JD 是專業工作文件，不能容忍捏造來源。 |
| Human authority | 不得無聲改人工內容；review reject 未有新 evidence 時不得重提。 | 現有 Web 審閱的核心信任模型。 |
| Replayability | 同一輸入與 state revision 可重播並解釋 state delta。 | 否則無法診斷「效果差」的原因。 |
| Failure visibility | extractor/coder/projector 失敗要有 audit，不可靜默漏寫。 | 現有事故正是靜默斷鏈。 |
| Context separation | 完整 transcript 在 session store 可回查；prompt 摘要不是唯一真相。 | 防止 compaction／摘要遺失造成無法稽核。 |

### 22.6 價值 gate：用 baseline 決定，而不是先猜百分比

沒有足夠 Caliburn 標註資料前，任意宣告「提升 20% 才算成功」是假精確。因此採兩階段門檻：

1. **先跑 C0 baseline**：記錄 evidence recall/precision、quote validity、indicator quality、主要任務覆蓋、重複提問、turn 數、人工接受/拒絕與 latency/cost 的分佈。
2. **再預註冊 C1/C2 的成功條件**：在不違反不可妥協 gate 下，需在其欲解決的 failure class 上有可重複、經人工 trace 審查確認的改善，且不以不可接受的 turn/cost/疲勞增加換取。

建議的 failure class 與對應候選：

| Failure class | C1 應解決？ | C2 才可能額外解決？ |
|---|---|---|
| 首回合豐富自述遺失 | 是。Evidence 不依賴 task shell。 | 否。 |
| quote 缺失、推論偽裝成事實 | 是。Evidence/Inference 分層。 | 否。 |
| 同一回答只填一欄、漏掉多意圖 | 是。全寬 evidence reduce。 | 否。 |
| 指標無證據、被塞進錯欄位 | 是。事件級 coder + evidence links。 | 少量幫助。 |
| 流程先後、條件、回工、交接被抹平 | 部分；可用 linked evidence 表示。 | **是；graph 的核心假設**。 |
| 顧問反覆問已知步驟，或無法知道哪一步缺失 | 部分。 | **是；需證明 graph 提供額外訊號**。 |
| 職類／技能 reference 過度投射 | 是；reference 與 evidence 分離。 | 否。 |

若 C1A 已解決主要 failure class，而 C2 沒有在「流程順序／分支／交接」案例中穩定提升，就**不做 Workflow Graph**。這是本提案最重要的淘汰規則。

### 22.7 Workflow Graph 的入場與淘汰條件

只有同時成立以下條件，C2 才可進入實作：

1. C1A 的 replay／branching／真人 trace 反覆出現、且已人工標註為流程結構缺失的失敗：順序錯置、例外漏失、handoff 歸屬錯誤、回工循環消失。
2. 這些失敗不能只靠補 evidence schema、改善 coder prompt 或調整 episode closing 修正。
3. 有一組專門的 process-sensitive golden cases，能定義「正確關係」而非只評漂亮文字。
4. 小型 C2 prototype 在這組案例上改善，且不降低 C1A 在其他案例的 evidence/source/review／對話指標。
5. graph 不需要成為 Web UX、BPMN、圖資料庫或跨租戶知識庫；它仍是 session-local artifact。

任一條不成立，就保留較簡的 C1A（或 C1），Workflow Graph 退回研究備選。

### 22.8 目前領先候選，不是「最優解」定案

截至目前研究，能負責任地下的結論是：

> 對一人團隊，**目前風險最低、資訊價值最高的第一個實驗是 C1：Thin Evidence-first；真正的對話候選是緊接著比較的 C1A：Evidence + Sufficiency Agenda。**

這不表示 C1/C1A 已是最優架構。C1 有最多 provenance 與 state 證據、最少新增維護面，並提供測量 C1A/C2/C2P 是否值得存在的必要資料；C1A 則直接吸收 Anthropic Interviewer 的固定 guide + adaptive follow-up 模式，以及 2026 SparkMe 對 coverage/emergence/cost 的可測量化，但不先承擔其 multi-agent 與 rollout 成本。[A8][A9][R9]

完整 Workflow Graph 與 deliberative planner 都是有前景但尚未被 Caliburn eval 證明的擴張選項。若 C0 修補版已在真實資料上達標，C1 也可能被判定不值得；若 C1A 無法改善真人訪談，agenda 同樣必須被簡化或淘汰。

這不是降低目標，而是讓「最強」變成可被證據證明、可隨模型與資料演進調整的系統，而不是一次性架構信仰。

---

## 23. 2026 第二輪深查：工作分析採集、Sufficiency Agenda、停止規則與有效評測

本節是 2026-07-15 追加研究。它不宣告前 22 節無效，而是修正三個容易導致「設計看起來完整、實作卻很差」的假設：

1. 有 Evidence Ledger 不代表顧問知道下一題該問什麼。
2. 有固定 coverage 不代表真的理解工作；「提過」與「足以產生 JD」不是同一件事。
3. 固定 transcript replay 無法單獨證明 adaptive interview policy，因為不同問題會改變後續回答。

### 23.1 目前最接近本產品的外部實證

#### Anthropic Interviewer：大規模可行，但不是 JD generator

Anthropic 已公開一個真正運作中的 AI 訪談系統，而不是只有 agent 概念文章：

```text
Planning
  研究目標 → Claude 草擬 interview guide → 人類研究者修訂

Interviewing
  固定核心研究問題 → 根據受訪者回答產生 adaptive follow-up

Analysis
  完整逐字稿 + 原研究計畫 → 分類／主題／回答 → illustrative quotations
  → 人類研究者驗證與解釋
```

2025 初始研究包含 1,250 位專業人士；2026 的公開研究收到 112,846 份訪談，其中 80,508 份通過品質門檻，橫跨 159 國、70 種語言。[A8][A9]

可直接採納的模式：

- interview guide 與 adaptive follow-up 並存，不是全腳本，也不是完全自由聊天。
- planning、interviewing、analysis 是不同階段；人類在計畫與分析均有角色。
- 分析回扣原始研究問題，並以逐字稿 quote 支持結果。
- 不同分析目標使用不同 classifier：某些維度 single-label、某些 multi-label。
- 資訊不足時採 broad/unclear，未到達該題時排除，不強制分類。
- classifier 先從資料 bottom-up 找類別，再由人驗證；不是先寫一張完美 taxonomy 後硬套所有人。

不可直接外推的部分：

- Anthropic 的目的是質性研究與主題分析，不是個人 JD 或職能認證。
- 其 2026 classifiers 至少以 25 筆人工標籤達 90% agreement；這是該研究的操作門檻，不足以成為 Caliburn 的通用準確率保證。[A9]
- 自述仍受 recall、social desirability、selection、ordering、dropout 與 researcher interpretation 影響；Anthropic 也明列這些限制。[A8][A9]
- 代表性 quote 支持「受訪者說過」，不自動證明該工作客觀發生、成效數字正確或能力已達某等級。

#### O*NET：工作事實與任務評定分開

O*NET 的最新公開資料採多方法、多來源，不以一段自述一次產生完整職業模型。其 task questionnaire 先確認一項 task 是否 relevant，再分開問 frequency 與 importance，最後允許補充未列出的工作；資料庫另外保留來源、樣本數、standard error、confidence interval 與 low-precision signal。[S4][S5][S6]

對 Caliburn 最重要的不是照搬 O*NET 的量表，而是下列分離原則：

```text
「我做這件事」            = task/action evidence
「通常每週做」            = frequency qualifier evidence
「不常做但錯了影響很大」  = importance/criticality qualifier evidence
「只是幫同事，不是我負責」= ownership/scope qualifier evidence
「以前做，現在沒有」      = temporality + polarity evidence
```

因此，不得採用以下捷徑：

- 提及次數高 ⇒ 核心任務。
- 每日做 ⇒ 一定重要。
- 描述很長 ⇒ 代表高能力。
- 標準職類常見 ⇒ 該員工一定有做。
- 使用某工具 ⇒ 已具備對應 skill level。

#### 2025–2026 訪談研究：追問本身是一個待評估能力

Wuttke 等人的 AI conversational interview 研究公開完整 prompt 與逐 turn 人工編碼。它支持一次一題、不 leading、不評價受訪者答案、適度以原話確認理解、在不清楚或意外回答時追問；同時也發現 AI 可能嚴重漏追問，且小幅 prompt 修改可產生未預期副作用。[R6]

2025 的 proactive information gathering 與 information-gap 研究把「先辨認缺少什麼，再問 targeted question」當成獨立能力，而不是期待一般聊天模型自然做到。[R7][R10] FQ-Eval 則顯示 follow-up 不能只評 topical relevance；應以使用者目標與實際價值建立專用 rubric。[R8]

2026 SparkMe 把半結構式訪談形式化為：

```text
Interview Utility = α × 預定主題覆蓋
                  + γ × 受訪者帶出的相關新主題
                  - β × 訪談負擔／長度
```

其 agenda 追蹤 subtopic、notes、coverage 與 emergent topics；當沒有待探索主題時停止。研究的 multi-agent rollout planner 在其測試中有收益，但研究仍是 preprint、沒有直接對比專家真人訪談，主要自動 benchmark 也依賴 simulated users 與 LLM judge。[R9] 因此 Caliburn 應先採其**可測量目標**，不要先採其**最重實作**。

### 23.2 Evidence v0.2：先修語意漏洞，不增加萬用大物件

原 5.2 節的 `kind + claim + quote` 能保證來源，但還不足以阻止下列錯誤：

- 把團隊、主管或其他部門的行為算到受訪員工名下。
- 把「以前做」「可能會做」「不是我做」當成現職責任。
- 把一次例外當成通常流程。
- 把 frequency、importance、scope 塞進改寫後 claim，後續無法更正其中一部分。

建議的候選契約如下；它仍需由 C1 eval 決定欄位是否 load-bearing：

```json
{
  "evidence_id": "ev_01J...",
  "session_id": "...",
  "episode_id": "ep_...",
  "kind": "action | decision | input | tool | stakeholder | output | standard | exception | frequency | importance | impact | scope | ownership | authority | explicit_self_assessment",
  "claim": "從 ERP 匯出月結資料",
  "subject": "employee | employee_team | other_person | other_team | organization | unclear",
  "polarity": "affirmed | denied | uncertain | corrected",
  "time_scope": "current | past | future_planned | hypothetical | unclear",
  "typicality": "usual | recurring | one_off | exception | example_only | unclear",
  "qualifies_evidence_id": null,
  "source": {
    "turn_id": 17,
    "speaker": "employee",
    "quote": "我會先從 ERP 把月結資料拉出來",
    "char_start": 3,
    "char_end": 18,
    "question_id": "q_...",
    "elicitation": "spontaneous | open_probe | targeted_probe | confirmation"
  },
  "status": "accepted | duplicate | disputed | superseded",
  "created_by": "extractor",
  "schema_version": 2
}
```

欄位的實作語意：

| 欄位 | 必須解決的錯誤 | 禁止用法 |
|---|---|---|
| `subject` | 誰實際執行／承擔。 | `employee_team` 不可無條件投影成個人 task。 |
| `polarity` | 否定、更正、不確定。 | `denied` 不可因 claim 文字像任務而進 JD。 |
| `time_scope` | 現職、過去、未來、假設。 | `past` 不可自動列入 current JD；可保留作背景。 |
| `typicality` | 通常工作、一次事件、例外。 | `example_only` 不等於 frequency；`exception` 不等於核心流程。 |
| `qualifies_evidence_id` | 把頻率、重要性、權限等限定連回被限定 task。 | 不可用語意相似度偷偷綁定；連結必須由同 turn 明示或經確認。 |
| `elicitation` | 區分自發陳述、開放追問、針對性追問與 yes/no 確認。 | 不可把 confirmation 的「對」視為比具體事件更豐富的證據。 |

#### 原子化規則

同一句可以產生多筆 Evidence，但每筆只保存一個可否定主張：

> 「我每週一從 ERP 拉資料，對不上才找財務調整。」

應拆為：

1. action：員工從 ERP 匯出資料。
2. frequency：每週一，`qualifies_evidence_id → action`。
3. exception/condition：資料對不上。
4. action：員工聯絡財務。
5. stakeholder：財務。
6. action/authority：由財務調整；不可改寫成員工親自調整。

不應拆成沒有上下文價值的 token 級碎片；例如「ERP」仍可作 action 的 entity/tool link，不必為每個名詞建立一筆 Evidence。

#### Evidence 與「可信度」

Evidence 不建議存一個看似精準的 `confidence: 0.83` 當真實機率。至少要分開：

- `source_validity`：quote/span/speaker 是否經程式驗證。
- `extraction_review`：候選是否被 reducer 接受、拒絕或送人工抽樣。
- `claim_status`：affirmed/denied/disputed/superseded。
- `inference_confidence`：只存在 Inference，且只用於 routing。

模型對自己的把握不能替代來源、使用者確認或人工審閱。

### 23.3 Qualifier 不等於 Task：工作分析採集順序

對每一個可能成為 JD 核心任務的 candidate，採集順序建議是：

```text
存在性／所有權
  這是不是你目前實際負責或參與的工作？
        ↓
事件骨架
  什麼情況開始 → 你做什麼 → 產出給誰／用來做什麼？
        ↓
品質與例外
  怎樣算完成／正確？哪裡最容易出錯？錯了怎麼處理？
        ↓
任務評定
  多常發生？影響／重要性？你有多少決定權？
        ↓
跨事件推論
  skill / knowledge / ability / attitude candidate
```

這不是固定逐題問卷。若受訪者第一段已自然提供其中多項，Extractor 應全寬吸收，Agenda 只標出真正缺口。O*NET 的 relevance/frequency/importance 提供分離思路；Caliburn 的對話仍以具體工作事件為主，不需要把每項任務都問成三個 Likert scale。[S5][S6]

### 23.4 JD 元素的「足夠證據」定義

`covered` 不得只代表某關鍵字出現。Agenda 應使用 `sufficiency_profile`；每種下游元素有不同最低證據。

| 目標元素 | 最低 evidence sufficiency | 不足時處理 |
|---|---|---|
| `task` | current + employee/employee_team ownership；具體 action；可辨識 object/input/output/purpose 至少一項。 | 保留 candidate；優先問產出或目的，不從職類 reference 補寫。 |
| `output` | 明示 deliverable/result；可辨識 recipient/use 或完成狀態。 | 若只是「做分析」不能自行生成「分析報告」。 |
| `performance_indicator` | condition/context + observable behavior + standard/result；數值門檻只能來自明示 quote/reference policy。 | 缺標準時只保留 behavior candidate，不產生漂亮但空泛 KPI。 |
| `knowledge` | 明示規則／原理／制度／domain knowledge 被用於一項 action/decision。 | 只提領域名時列 `needs_clarification`。 |
| `skill` | 明示 action + method/tool；若要寫熟練度，另需 complexity、autonomy、consistency 或多事件證據。 | 使用工具一次不等於熟練；不可由職稱推定。 |
| `ability` | 至少跨兩個不同事件的可觀察行為模式，或受訪者確認且人工審閱；不能只靠自評形容詞。 | 保留 hypothesis；通常不主動追逐低價值人格標籤。 |
| `attitude/work style` | 跨情境、一致且可觀察的選擇／行為；避免將服從流程誤當責任感。 | 預設不投影；需要人審。 |
| `frequency` | 明示週期、次數、比例或可辨識的情境頻率。 | 不由逐字稿提及次數推定。 |
| `importance/impact` | 明示錯誤後果、決策用途、影響對象、風險或受訪者評定。 | 不由頻率推定。 |
| `authority/scope` | 明示誰決定、誰核准、誰執行，以及受訪者的參與邊界。 | 未明時不得把團隊流程全部歸給個人。 |

`sufficiency_profile` 應回傳 reason codes，而不是只有 0–100 分：

```json
{
  "target": "indicator_candidate:inf_123",
  "status": "insufficient",
  "satisfied": ["context", "observable_behavior"],
  "missing": ["standard_or_result"],
  "blocking": true,
  "next_probe_family": "standard_or_exception"
}
```

數值分數可以用於排序，但 release/debug 必須看得到 missing reason；否則實作又會回到無法診斷的「coverage 76%」。

### 23.5 Interview Agenda v0.1 候選契約

Agenda 不是第二份逐字稿，也不是把所有 JD 欄位排成待填清單。它只保存決策下一題與停止所需的壓縮 state：

```json
{
  "agenda_revision": 12,
  "required_topics": [
    {
      "topic_id": "role_scope",
      "status": "sufficient",
      "supported_by": ["ev_1", "ev_2"],
      "missing": []
    }
  ],
  "episodes": [
    {
      "episode_id": "ep_monthly_report",
      "label": "月報產製與異常處理",
      "priority": "high",
      "status": "active",
      "sufficiency": {
        "task": "sufficient",
        "output": "sufficient",
        "indicator": "insufficient",
        "skill": "candidate"
      },
      "gaps": [
        {
          "gap_id": "gap_standard",
          "kind": "standard_or_result",
          "why_it_matters": "indicator_projection",
          "ask_count": 0,
          "last_asked_turn": null,
          "status": "open"
        }
      ],
      "emergent_topics": [],
      "contradictions": [],
      "declined": []
    }
  ],
  "fatigue": {
    "consecutive_minimal_answers": 0,
    "explicit_stop_request": false,
    "turns_in_episode": 3
  },
  "recommended_actions": [
    "probe:gap_standard",
    "transition:next_high_priority_episode",
    "close_episode"
  ]
}
```

Agenda reducer 的責任：

1. 用 accepted Evidence 更新 sufficiency；不得用模型自由摘要直接標 sufficient。
2. 同一回答可關閉多個 gap。
3. 記錄每個 gap 被問過幾次、得到哪些新 evidence、使用者是否拒答／不知道。
4. 受訪者主動提及且與工作分析相關的內容可建立 `emergent_topic`；不能因「有趣」就無限旁支。
5. `recommended_actions` 由確定性條件產生候選集合；Consultant 只能在合法集合中選擇或回傳理由要求例外。
6. Agenda summary 可重建；Evidence/Transcript 才是 source of truth。

### 23.6 下一題政策：先選缺口，再寫自然語句

避免直接 prompt：「根據上下文問最佳下一題」。推薦拆成兩步，但可在同一個模型 call 以 structured output 完成：

```text
Step 1：Question Policy
  從合法 action 中選：
  - probe current gap
  - clarify contradiction
  - explore employee-introduced topic
  - transition
  - confirm candidate
  - close episode
  - finish interview

Step 2：Question Realizer
  把選定 action 寫成一個簡短、中立、承接上一答的問題
```

候選 action 排序的初始原則：

1. 先處理會阻擋 task/output/indicator 投影的 high-impact gap。
2. 當上一答出現與目前核心工作相關、且可能改變職責理解的新內容，可探索 emergent topic。
3. 若目前 episode 已 sufficient，轉到下一個 high-priority episode，不為填滿所有 K/S/A 欄位繼續問。
4. 若矛盾會改變所有權、現況、頻率、門檻或產出，優先澄清。
5. 若同一 gap 已問且沒有新 evidence，降低優先級或關閉為 unresolved。
6. 問題一次只能有一個主要 answer target；禁止把 KPI、工具、利害關係人與技能綁成一題。

工作分析專用 question rubric：

| 維度 | 通過條件 |
|---|---|
| Grounded | 問題承接已知 evidence/gap，不錯認員工說過的內容。 |
| Non-leading | 不提供預設答案、職類標準或正向評價暗示。 |
| Single-focus | 一次一個主要資訊目標。 |
| Expected value | 回答可能關閉明確 gap 或驗證高影響 inference。 |
| Novelty | 不重問已有 accepted evidence。 |
| Cognitive load | 短、具體、受訪者知道要回想哪個事件。 |
| Conversational continuity | 必要時用受訪者原詞簡短承接，不長篇摘要。 |
| Respect | 接受不知道、拒答、轉題與停止。 |

#### 建議 probe families

這些是 question families，不是固定問卷：

| Gap | 中立問題型 |
|---|---|
| ownership | 「在這段流程裡，通常哪一部分是你親自負責的？」 |
| trigger | 「這件事通常在什麼情況下開始？」 |
| action | 「最近一次發生時，你第一個實際動作是什麼？」 |
| output/use | 「你完成後會留下什麼結果，接著誰會用它？」 |
| standard | 「你怎麼判斷這次已經完成、可以交出去？」 |
| exception | 「什麼情況會讓你不能照平常方式處理？」 |
| correction/rework | 「發現不符合時，你接下來怎麼處理？」 |
| frequency | 「這通常多久發生一次，還是只有特定情況才會做？」 |
| impact | 「如果這一步沒做好，最直接會影響什麼？」 |
| authority | 「這一步你可以自己決定，還是需要誰確認？」 |
| skill evidence | 「這一步最需要你做判斷或運用方法的地方是什麼？」 |

不得把這些範例硬編碼為每個 episode 全部必問；是否問由 sufficiency 與價值決定。

### 23.7 Episode 與整場訪談的停止規則

只用「題庫問完」會漏 emergent work；只用「模型覺得聊完」則不可重播。建議混合規則。

#### Episode 可以關閉

滿足任一條：

1. `task + output` sufficient，且目前產品所需的 high-priority downstream gaps 已關閉。
2. 下一個 open gap 不會改變 JD 內容，只會增加低價值細節。
3. 同一 gap 已進行兩次中立 probe，仍無新增 accepted evidence。
4. 使用者明示不知道、不負責、不願回答或要轉題；保留 unresolved reason。
5. 連續兩個回答幾乎沒有新 evidence，且沒有高影響矛盾。
6. episode turn budget 到達；以 `budget_exhausted` 關閉，不得偽裝為 sufficient。

上述「兩次／兩回合」是第一輪可測預設，不是永遠不變常數；eval 應追蹤被過早關閉與過度追問，之後再調整。

#### 整場訪談可以結束

必須同時符合：

- required topics 都是 `sufficient | not_applicable | declined | unresolved_with_reason`，不可仍是無原因 `open`。
- high-priority tasks 至少達 task/output 最低 sufficiency。
- 沒有會改變個人職責歸屬或重大 JD 內容的未處理 contradiction。
- 最近兩個可選 probe 的預期價值都低於 transition/finish，或使用者主動停止。
- 產生結束前摘要時只說已理解與仍待人工確認的項目，不新增 inference。

#### 必須立即停止或降載

- 使用者要求停止。
- 反覆拒答或顯著疲勞；改為詢問是否先結束，而不是繼續追問。
- 涉及不必要的敏感個資、第三人隱私或與 JD 無關的健康／家庭細節。
- 模型／工具連續失敗導致 state 無法可靠更新；顯示可恢復狀態，不假裝完成。

### 23.8 三層 eval：不要讓 fixed replay 承擔做不到的事

#### Layer A：固定 transcript replay

可回答：

- Evidence 是否抽對、抽全。
- ownership/polarity/time/typicality 是否正確。
- contradiction/supersession 是否正確 reduce。
- Inference 與 JD projection 是否有來源、欄位是否正確。
- 同一 state revision 是否可重播。

不可回答：

- 如果問另一題，真人會提供什麼。
- 哪條 adaptive 路徑的資訊收益較高。
- 使用者是否覺得追問自然、疲累或被引導。

#### Layer B：branching simulation

建立少量具 hidden facts 的 synthetic interviewee profile；候選 C0/C1/C1A/C2P 可問不同問題，simulator 僅依 profile 與已問問題回答。用途是：

- 快速比較 gap coverage、重問、停止與 turn cost。
- 產生壓力案例：簡短回答、跨題回答、更正、拒答、模糊所有權、例外工作。
- 對 agenda/reducer 做可重複 ablation。

限制：

- simulator 不是真人；不可用它單獨核准上線。
- hidden profile 不能把所有答案寫得過度完整，否則只測模型是否會讀標準答案。
- interviewer 與 simulator 最好不要永遠使用同一模型／prompt，並需抽樣人工看 trace。
- 任何 LLM judge 需對人工標註校準；SparkMe 的作者也明確警告 simulated users 與 judge 的外推限制。[R9]

#### Layer C：真人／專家 pilot

在不碰正式 production 前，至少進行小型、同意參與的真人 pilot：

- 以 randomized、blinded pairwise review 比較候選，不讓 reviewer 知道架構名稱。
- 受訪者評 clarity、是否被理解、問題重複、疲勞、是否願意繼續、結果是否代表其工作。
- 工作分析 reviewer 評 task/output/indicator/K/S/A 的完整性、正確性與可追溯性。
- 閱讀完整 trace，不只看最後 JD。
- 把真人出現但 golden set 沒有的 failure 加入 regression set。

上線前不能只引用 Anthropic 的高滿意度或 SparkMe 的 user study；Caliburn 的受訪目的、文化、語言、風險與輸出不同，必須有自己的 pilot。

### 23.9 指標與 grader 的實作分工

#### Deterministic graders

| 指標 | 計算方式 |
|---|---|
| quote validity | quote 必須是指定 employee turn 的精確 span。 |
| source attribution | subject/speaker/turn/episode link 合法。 |
| polarity safety | denied/past/hypothetical evidence 不可進 current JD。 |
| projection grounding | 每個 `_pending` item 的所有 material claim 有 accepted evidence。 |
| repetition | normalized question target/gap id 是否重複且無新 evidence。 |
| state legality | reducer revision、supersession、human authority、idempotency。 |
| single-focus proxy | question action 只有一個 primary gap id；文字仍抽樣人工檢查。 |
| cost | turns、tokens、latency、tool/model calls、failures。 |

#### Human-calibrated rubric graders

| 指標 | 核心問題 |
|---|---|
| evidence semantic correctness | claim 是否忠於 quote，而非只通過 substring。 |
| question groundedness | 問題是否正確承接前文。 |
| non-leading | 是否暗示理想答案、職類標準或正面能力。 |
| information value | 回答是否新增會改變工作模型的 evidence。 |
| sufficiency accuracy | sufficient 是否過早；insufficient 是否造成無謂追問。 |
| emergent relevance | 新主題是否由員工帶出且與 JD 目標相關。 |
| final JD fidelity | 是否代表此人實際工作，不是標準職類模板。 |
| indicator observability | 是否可看見情境、行為、標準／結果。 |

OpenAI 2026 官方 eval 指引建議 task-specific dataset、持續從 production/logs 擴充、優先 pairwise/pass-fail、並以人工標籤校準 model grader；同時舊 Evals platform 已公告退場。[O6] 因此：

- eval case、expected labels、grader inputs/outputs 必須存在 repo／自有資料層，可由任何 runner 執行。
- 不把測試資產只存在供應商 dashboard。
- LLM judge 輸出需保留模型版本、rubric 版本、輸入與理由；分數不可覆蓋人工標註。
- prompt optimizer 或自動改 prompt 的結果必須跑 held-out regression，不可直接部署。

### 23.10 C0/C1/C1A/C2/C2P 的正確比較順序

```text
C0  修補 v3，取得真實 baseline
 │
 ├─ 若已達產品門檻：停止重構，僅保留研究 backlog
 │
 ▼
C1  Evidence/Inference + evidence-backed projection
 │   驗證：來源、抽取、修正、多意圖、JD fidelity
 │
 ▼
C1A Sufficiency Agenda
 │   驗證：追問、轉題、停止、emergent relevance、turn cost
 │
 ├─ 流程關係仍反覆失敗 ─────► C2 Workflow Graph prototype
 │
 └─ emergent theme/長期規劃失敗 ► C2P Planner prototype
                                  （先離線／單 pass，再決定是否多 agent）
```

每個元件的 kill condition：

| 元件 | 保留條件 | 淘汰／簡化條件 |
|---|---|---|
| Evidence v0.2 欄位 | 明顯降低錯誤歸屬、否定／過去誤投影。 | 欄位低一致、未被任何 guardrail/policy 使用。 |
| Sufficiency Agenda | 真人與 simulation 均減少重問／漏問，且 JD 不退步。 | 只是另一份不可靠摘要，或增加 turn/latency 無品質收益。 |
| Emergent topic | 能找到 guide 外但影響 JD 的實際工作。 | 主要帶來旁支、隱私風險或訪談膨脹。 |
| Workflow Graph | 改善順序、分支、handoff、rework 的專門案例。 | C1A 已能以 linked evidence/notes 解決。 |
| Planner/rollout | 在相同成本邊界提升有價值的新資訊與停止決策。 | simulation 漂移、latency/cost 高、真人無收益。 |
| Multi-agent | 單 loop 無法維持明確責任，且拆分後 eval 穩定改善。 | 只把 pass 改名為 agents，增加 handoff 與 context 漂移。 |

### 23.11 自述、隱私與「專業顧問」的誠實邊界

專業顧問 AI 必須區分：

```text
employee_reported       員工自述
employee_confirmed      員工確認模型的理解
document_supported      組織文件／制度支持
reviewer_accepted       人工 reviewer 接受作為 JD
objectively_verified    有外部可驗證紀錄；多數訪談內容不會到這層
```

UI 或 export 不應把 `employee_reported` 寫成「已驗證事實」。同樣地：

- 不要求員工透露客戶姓名、病患資料、帳號、商業機密等才能說明工作。
- Extractor 可在 quote 保留前做明確的敏感資訊處理政策，但原始 transcript 的保存、去識別與權限需另有資料治理 ADR。
- 用 reference 對齊術語時，保存原話與 normalized candidate；不要讓標準術語抹掉在地工作差異。
- 工作能力與態度可能影響人事決策，必須保留人工 authority、可爭議／更正與來源。

### 23.12 實作前不得自行猜的決策表

| 問題 | 本研究目前答案 | 必須由何種證據改變 |
|---|---|---|
| 是否直接做完整 Workflow Graph？ | 否；先 C1/C1A。 | C1A process-sensitive failure + C2 prototype 改善。 |
| 是否使用多 agent？ | 否；passes 可分責任，但保持單一對話 owner。 | 單 loop 明確瓶頸 + multi-agent ablation。 |
| 是否 fine-tune？ | 否。 | 穩定 taxonomy、足量一致標註、prompt/state 已飽和。 |
| 是否把 O*NET/ESCO task 自動加進 JD？ | 否，只作候選／術語。 | 員工 evidence 或授權文件支持。 |
| 是否每回合直接寫 `_pending`？ | C1 實驗期只保留相容 fallback；目標由 evidence-backed projection 寫入。 | replay 與人工 review 證明 direct path 更可靠。 |
| 是否全問 frequency/importance？ | 否；只對 JD 核心候選或排序需要時問。 | 產品明確要求量化，且疲勞 eval 可接受。 |
| 是否把 confidence 當事實機率？ | 否，只作 routing。 | 有校準研究與明確使用情境。 |
| 是否只跑 transcript replay？ | 否；A/B/C 三層。 | 不可改；adaptive policy 的因果限制。 |
| 是否綁 OpenAI 舊 Evals platform？ | 否。 | 平台退場公告已確定；僅可換 runner。 |

### 23.13 本輪研究後的結論

截至 2026-07-15，能負責任地說：

1. **訪談架構已有大廠實例**：Anthropic 的 planning → adaptive interview → analysis 已在 8 萬級、多語訪談使用；固定 guide 與 adaptive follow-up 並存是目前最有力的實務模式。[A8][A9]
2. **工作分析不能一次分類完成**：O*NET 的多來源與 task/relevance/frequency/importance 分離，支持 Evidence qualifier 與明確 unknown，而不是讓 LLM 從敘事猜核心程度。[S4][S5][S6]
3. **下一題政策要獨立設計與評估**：gap-driven question selection、non-leading、一次一題、sufficiency 與停止規則，不可藏在一段 persona prompt。[R6][R7][R10]
4. **最新研究提供 planner 候選，但未證明 Caliburn 要先做 multi-agent**：先採 coverage + emergence − burden 的 objective 與 agenda；rollout planner 只有在 C1A 失敗後才有入場資格。[R9]
5. **目前沒有已證明的最優架構**：C1 是資料可靠性實驗，C1A 是對話政策實驗；C2/C2P/C3 都要靠 Caliburn 自身 eval 晉級。

所以接下來若進入實作規劃，第一個垂直切片應是：

```text
一個真實匿名 incident transcript
→ Evidence v0.2 extractor + deterministic reducer
→ sufficiency reason codes
→ evidence-backed task/output/indicator projection
→ 與 C0 盲評
```

通過後才加入 C1A 的 agenda/question policy，並用 branching simulation + 真人 pilot 評估。這個順序讓每次新增複雜度都能被單獨歸因、保留或刪除。

---

## 24. 第一批 database session 稽核：架構假設與可重播性的實證更新

本節不是新的外部文獻結論，而是 2026-07-15 對 Caliburn 現有資料庫所做的第一批內部實證稽核。完整、不含逐字稿與個資的稽核報告見 [`real-candidate-audit-2026-07-15.md`](../../apps/api/evals/interview_v4/reports/real-candidate-audit-2026-07-15.md)。外部方法仍依 Anthropic 的 trajectory/outcome eval 與 OpenAI 的 production/historical dataset、task-specific eval、人工校準原則。[A5][O6]

### 24.1 執行邊界與資料治理

本次先依可能是真實資料的最保守假設盤點 database session；之後資料擁有者確認目前資料全部為
測試資料。以下 private export 與去識別流程保留為未來 production data 的操作證據，不再構成此
synthetic case 的 privacy blocker：

- 僅啟動專案既有 PostgreSQL `db` 容器，不啟動 API/Web、不執行 migration。
- inventory 使用 read-only query，只輸出 session UUID 與彙總數量，不輸出 profile/user id、職稱、文件或逐字稿。
- candidate export 使用 PostgreSQL `SET TRANSACTION READ ONLY`。
- 去識別候選只寫入 OS 暫存目錄，不在 Git worktree。
- source UUID 只轉為 salted fingerprint；salt 不寫入 artifact。
- 已知姓名、Email、公司、部門、職稱由本機 profile/user rows 建 exact replacement，不印出原值。
- Regex 直接識別掃描為 0，第二層 heuristic prescreen 找到一個 `ORGANIZATION_CUE`。對一般資料
  應維持 `redaction_pending_review`；本 case 因 owner-confirmed test data 改標 `synthetic`。

此結果仍證明「regex 沒找到」不能等同「已去識別」。下列規則適用於未來非 synthetic 候選：

- 不得 commit；
- 不得送到外部模型 provider；
- 不得標成 `deidentified`；
- 不得成為 validation／held-out case。

### 24.2 可用資料量與候選定位

資料庫只有一個 synthetic interview session，無法形成第 22／23 節要求的
incidents/successes × role families 分層樣本。此 session 同時有成功與失敗訊號，故只可定位為
development 的 mixed incident candidate：

| 項目 | 觀察值 | 可以說什麼 | 不能說什麼 |
|---|---:|---|---|
| Employee turns | 10 | 有足夠內容開始 claim annotation。 | 不代表主題或 JD 欄位已覆蓋。 |
| Consultant turns | 10 | 儲存資料呈交替對話。 | 不代表問題自然、non-leading 或高資訊價值。 |
| Employee chars | 3,586 | 回答不是全為極短句。 | 字數不等於證據品質。 |
| Accepted review events | 105 | UI／人工曾接受 105 筆建議。 | 不等於 105 筆語意都正確。 |
| LLM calls | 30 | 每 10 次員工回答有 3 倍 call amplification。 | 未記 tokens，不能算完整成本。 |
| Guard | 105 pending-add、12 verify-reject、3 drop | 同時存在產出與 contract friction。 | verify pass 不能替代 semantic gold。 |
| Session | 10 次員工回答後仍 active/survey | 可標 `long_active_session` 供停止規則研究。 | 單例不能證明 agenda 整體失敗。 |

因此本 case 的 `risk_tags` 是：

```text
guard-alert
long-active-session
mixed-acceptance
missing-initial-fixtures
negative-evidence
temporal-contradiction
unanswered-final-question
```

### 24.3 延遲與責任層定位

儲存的 30 calls 全部標示同一 model `openai/gpt-5.4-mini`；這只描述歷史 session，不是 model recommendation，也沒有做 provider/model ablation。

| Audit call role | Calls | Total latency | p50 | p95 | Guard 結果 |
|---|---:|---:|---:|---:|---|
| `interview` | 10 | 22,316 ms | 1,438 ms | 5,221 ms | 無記錄 guard failure |
| `select` | 20 | 178,900 ms | 4,005 ms | 38,548 ms | 105 pending-add、12 verify-reject、3 drop |
| 合計 | 30 | 201,216 ms | 2,941 ms | 38,548 ms | 同上 |

`select` 佔已記錄模型延遲約 88.9%。現有 role 名稱過粗，不能由此確定每次 `select` 是 pool selection、scribe extraction、retry 還是 fallback；但可以排除「目前最明顯的瓶頸在 consultant 生成文字」這種未經驗證的直覺。現有單例顯示第一個應拆解量測的是 selection/extraction/write-contract path。

兩個 regression seed：

- **Turn 13**：1 次 `interview` + 3 次 `select`，總 61,337 ms，單 call 38,548 ms。多出的一次 `select` 可能是 retry/fallback，但 audit 缺 outcome，故只能列假設。
- **Turn 19**：1 次 `interview` + 2 次 `select`，總 50,942 ms，單 call 47,314 ms；同回合有 7 個 verify reject（6 invariant、1 hygiene）。

所有 call 的 prompt/completion token 都是 NULL。`candidate_metrics.py` 已修正為：

```json
{
  "prompt_tokens": {"recorded_calls": 0, "total": null},
  "completion_tokens": {"recorded_calls": 0, "total": null}
}
```

不能把 missing telemetry 加總成 0；否則「低成本」只是 observability 缺口。

### 24.4 Verify reject 告訴我們什麼

12 個 reject 的 deterministic check 分布：

| Check | 數量 | 目前可安全分類的 reason |
|---|---:|---|
| hygiene | 6 | `non_plain_single_line` × 6 |
| invariant | 6 | `other` × 6；現行 guard message 截斷不足以穩定細分 |

可成立的結論：

1. guardrail 有效攔住部分不符合文件契約的提案，不應因 reject 數量高就放寬。
2. selection/extraction pass 付出 LLM latency 後，仍提出 deterministic contract 不接受的值／操作。
3. Turn 19 的長延遲與 invariant cluster 應成為 failure localization case。
4. C1 應比較「LLM 先產 evidence、程式再投影」是否比「LLM 直接提出 doc mutation」少產生非法操作。

不能成立的結論：

- 其餘 105 筆 pending-add 都正確。
- invariant 是模型能力不足；也可能是 prompt/schema/候選池/路徑責任設計不良。
- 換更強模型就會解決；本次沒有同 case、同 prompt 的 model comparison。
- verify pass rate 可代表 JD fidelity。

### 24.5 對候選架構優先順序的更新

本次實證**沒有**授權直接實作完整 v4，但提高了下列優先度：

```text
P0  補齊可重播 capture + trace
P1  C0 真實 baseline
P2  C1 Evidence Extractor → deterministic Reducer → evidence-backed Projector
P3  C1A Sufficiency Agenda / question policy
P4  只有 process-sensitive failure 通過 gate 才做 C2 graph
```

#### 為何 C1 仍是正確的下一個架構實驗

現行 `select` 的 guard friction 與 latency 都發生在文件建議路徑。C1 的受控變因不是「新增更多 agent」，而是改變中間表示與責任：

| 現行候選責任 | C1 實驗責任 |
|---|---|
| LLM 由敘事靠近 doc path/value。 | LLM 只產 quote/span-backed Evidence。 |
| 同一 pass 混合抽取、分類與寫入意圖。 | Extractor、Reducer、Projector 契約分離，但仍在單一 service/loop。 |
| verifier 最後才看到非法 mutation。 | Evidence schema 先縮小自由度；Projector 以 deterministic mapping 產 mutation。 |
| acceptance event 被當成主要正向訊號。 | acceptance 只是 feedback；claim-level semantic gold 才決定品質。 |

但 C1 只有在同 fixture、同 reference、同 model config 下改善 hard gates 與 blind review 才能晉級；本節不是 C1 成功證明。

### 24.6 歷史 C0 為何不能執行

候選缺少三個真正的 turn-zero fixture：

```text
initial_document       unavailable
initial_session_state  unavailable
reference_snapshot     unavailable
```

現行 production draft 在同一 row 原地更新，只有最新 observed document；session state 也只保留匯出當下值。LLM audit 未保存完整 prompt、raw/parsed response、state delta 與 outcome。因此：

- 把 observed final draft 當 initial document 會讓 replay 從答案附近開始；
- 用目前 knowledge 重建 reference 會產生 temporal leakage；
- 只重播 transcript、但讓初始 state 來自 session 結尾會污染 agenda/coverage；
- 缺 prompt/schema hash 時，無法證明 C0 是哪一版本；
- 缺 model outcome/raw parsed output 時，無法重建 retry/fallback path。

exporter 已修正，不再把當前 state 冒充 initial fixture：

```text
initial_document.json        unavailable_fixture.v0.1
initial_state.json           unavailable_fixture.v0.1
reference_snapshot.json      unavailable_fixture.v0.1
observed_document.json       latest_at_export_not_replay_initial
observed_session_state.json  latest_at_export_not_replay_initial
replay.ready                 false
```

所以目前可做 claim annotation、quote/subject/negative-evidence/temporal-consistency 靜態評測與
failure localization；不能產生可信 C0 score。

### 24.7 新 eval pilot 的 immutable capture 契約與實作狀態

下一個可評測 session 開始前就要保存，不可在 session 結束後猜回來。以下是完整目標欄位；
2026-07-15 已完成第一個可執行 slice，尚未完成的 provider-level 欄位在本節末明列。

#### A. `EvalSessionStart.v0.1`

```json
{
  "eval_session_id": "opaque id",
  "consent_policy_version": "non-empty",
  "locale": "zh-TW",
  "started_at": "RFC3339",
  "initial_document_artifact": "restricted artifact ref + sha256",
  "initial_state_artifact": "restricted artifact ref + sha256",
  "reference_snapshot_id": "immutable id",
  "reference_snapshot_hash": "sha256",
  "interview_guide_version": "non-empty",
  "agenda_policy_version": "non-empty or C0-none",
  "prompt_bundle_hash": "sha256",
  "tool_schema_hash": "sha256",
  "code_git_sha": "git sha",
  "dirty_worktree": false
}
```

#### B. `ModelCallTrace.v0.2`

```json
{
  "call_id": "opaque id",
  "eval_session_id": "opaque id",
  "turn_seq": 19,
  "stage": "consultant|evidence_extract|reference_select|project|backstop",
  "attempt": 1,
  "provider": "provider id",
  "requested_model": "model id",
  "resolved_model": "model id",
  "temperature": null,
  "seed": null,
  "prompt_hash": "sha256",
  "tool_schema_hash": "sha256 or null",
  "input_tokens": 0,
  "output_tokens": 0,
  "latency_ms": 0,
  "outcome": "success|timeout|parse_failure|provider_failure|fallback",
  "raw_response_artifact": "restricted ref + sha256",
  "parsed_output_artifact": "restricted ref + sha256 or null"
}
```

`input_tokens/output_tokens=0` 只有 provider 明確回 0 時才可寫 0；未提供必須是 NULL。`stage` 不可再全部合併為 `select`。

#### C. `TurnTrajectory.v0.1`

```json
{
  "turn_seq": 19,
  "employee_turn_seq": 20,
  "state_before_artifact": "ref + sha256",
  "relevant_context_artifact": "ref + sha256",
  "model_call_ids": ["..."],
  "candidate_evidence_artifact": "ref + sha256",
  "verify_result_artifact": "ref + sha256",
  "reducer_delta_artifact": "ref + sha256",
  "projection_delta_artifact": "ref + sha256",
  "state_after_artifact": "ref + sha256",
  "document_after_artifact": "ref + sha256",
  "stop_or_transition_reason": "stable reason code"
}
```

#### D. `VerifyFinding.v0.2`

目前只存截斷文字，不足以分群。下一版至少保存：

```json
{
  "op_index": 3,
  "check": "invariant",
  "reason_code": "duplicate_entry",
  "target_kind": "task|output|indicator|knowledge|skill|attitude|header",
  "retryable": true,
  "message_artifact": "restricted ref or null"
}
```

reason code 必須穩定、可聚合；message 可在 restricted storage，不能靠截斷 free text 當唯一診斷欄位。

#### E. 儲存與隱私規則

- Raw transcript/prompt/response 不進 Git；repo 只放去識別 fixture 或 restricted artifact fingerprint。
- Consent、retention、刪除、存取角色與 provider data policy 需另有資料治理 ADR。
- 去識別後仍保留原始 semantic relation；不能為隱私直接刪掉所有情境、導致 indicator eval 失真。
- 測試 runner 只讀 immutable artifact；每 trial deep copy state/document，不回寫 production profile。
- 每次 export 都需 direct-id scan、heuristic prescreen、人工 privacy review 三關。

#### F. 2026-07-15 executable slice

已完成：

- `EvalSessionStart`、`ModelCallTrace`、`TurnTrajectory`、`VerifyFinding` Pydantic contract 與 committed
  JSON Schema；
- migration `0009_interview_eval_capture`；
- `interview_eval_captures` 一 session 一筆 turn-zero contract；
- `interview_eval_artifacts` 以 `(capture_id, kind, sequence)` 唯一，並由 PostgreSQL trigger 拒絕
  `UPDATE`；`DELETE` 只為 retention/privacy cascade 保留；
- start 保存 initial document/state/reference snapshot 與 canonical SHA-256；
- 每回合保存 before/after state/document、完整動態 tool results、各 stage parsed output、trajectory；
- trajectory 按真實執行語意記錄 `curation → consultant → scribe → harvest`，不以 DB insert order 猜測；
- finish 保存 final state/document、blockers、guard、stop reason；
- finish 後 status 由 `capturing` 單向轉成 `completed`；重送 finish 讀既有 artifact，不重跑模型；
- LLM audit 新增 stage/provider/requested/resolved model/attempt/outcome/prompt/tool-schema hash；歷史 rows
  只回填 `legacy_unknown`，不冒充 success；
- server 與 request 兩層 opt-in，預設關閉；必須 turn zero、consent policy 與固定 git SHA，否則
  fail closed。

尚未完成，因此 API 仍固定回 `replay_ready=false`：

- provider resolved model、tokens、raw response；
- provider-internal 每 attempt prompt/outcome；
- request exception 的獨立 failure trace。目前 turn 與 capture 共用 transaction，provider 例外會一起
  rollback，下一版需 separate transaction 或 outbox；
- `VerifyFinding.v0.2` stable reason code 尚未全面接進現行 free-text guard；
- capture artifact 到 portable case bundle 的 promotion/exporter 尚未完成。

### 24.8 第一個 case 的標註結果與剩餘 backlog

Owner 已確認資料為 synthetic，故已提交
`apps/api/evals/interview_v4/cases/development/TEST-SYNTHETIC-SESSION-001`。完成內容：

1. 22 個 required evidence，全部指向 employee turn 的 exact quote；
2. 每個 evidence 標 `subject/polarity/time_scope/typicality`；
3. 3 個 acceptable、3 個 needs-confirmation、3 個 forbidden inference；
4. 3 個 episode boundary 與 4 個 state expectation；
5. 明確保存 turn 13「沒有正式 QA 文件」的否定證據，不能被手動 Slow 3G 測試改寫掉；
6. 明確分離 observed 連點、hypothetical PostgreSQL outage 與 proposed OCR change；
7. turn 20 只有 consultant 問題、沒有 employee 回答，因此 LINE error branch tests 保持 unresolved；
8. 依 LINE 官方公告，LINE Notify 已於 2025-03-31 終止；2026 session 中「今年年初串 LINE
   Notify」標為 temporal contradiction，只允許追問年份／產品名稱，不允許偷偷改寫來源。

剩餘 backlog：

1. 105 review events 尚未全部連到 claim/projection；
2. Turn 13 retry cluster 仍只有 `legacy_unknown`，不能事後猜 outcome；
3. Turn 19 被拒操作的 intended semantics 尚需逐項 adjudication；
4. session stopping point 屬 C1A 標註，不能混入 C1 extractor score；
5. `annotation.status=maintainer_checked`，尚需獨立 domain review 才能成為 promotion gold；
6. 缺 initial fixtures，無論標註多完整仍不得改成 replay-ready。

### 24.9 本輪 gate 結果

| Gate | 結果 | 理由 |
|---|---|---|
| Synthetic development case 存在 | PASS（最低限度） | 有 1 個 owner-confirmed synthetic mixed candidate。 |
| 分層資料量 | FAIL | 未達 3–5 incidents + 3–5 successes，且無 role-family diversity。 |
| 自動 direct-id scan | PASS | 0 個 direct pattern residual。 |
| 此 case privacy 分類 | PASS | owner-confirmed test data；`privacy.status=synthetic`。 |
| Claim-level gold | PARTIAL PASS | 22 evidence 與 inference/state labels 已 maintainer-check；domain review 未完成。 |
| Immutable initial fixture | FAIL | document/state/reference 均缺。 |
| Historical C0 replay | BLOCKED | `replay.ready=false`；不得假造起點。 |
| C1 production implementation | NOT AUTHORIZED | 尚無可信 baseline 與 promotion set。 |
| Eval/trace foundation | PASS | exporter、schemas、loader、graders、isolated runner、capture migration 與 runtime instrumentation 已建立。 |
| Provider-level trace | PARTIAL | resolved model/tokens/raw response/per-attempt/failure outbox 尚缺。 |

本輪的實際下一步不是繼續擴大架構圖，而是：

```text
完成 synthetic claim annotation
→ 完成 immutable eval-session capture foundation
→ 補 provider-level trace 與 failure outbox
→ 從 turn zero 跑新的 captured synthetic pilot
→ 驗證 hash chain 後產生 replay-ready session
→ 擴充 incidents/successes 與 role-family 樣本
→ C0 baseline
→ C1 isolated vertical slice
→ blind paired decision
```

這個 gate 對「一人團隊」尤其重要：先讓每次新增的 schema/pass/call 都有可歸因證據；否則架構越完整，越可能只是把未知問題變成更多維護面。
