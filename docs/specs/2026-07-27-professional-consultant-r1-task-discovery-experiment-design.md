# AI 專業職務分析顧問 R1：Task Discovery 實驗設計與共識草案

- 日期：2026-07-27
- 狀態：**Accepted for implementation**（2026-07-27；owner 指示開工，第二位審查者確認共識成立）。
  **Segment 4／5 的付費 live 執行仍需 owner 另行核准**，§12.3 的停線不變。
- 範圍：R1 的案例、六個 arm、Prompt／Context／schema、模型、provider、grader、capture 與裁決方法
- 不包含：Web、資料庫、正式 Current JD、O/P/K/S/A、公版檢索、多輪保存、Graph runtime、多 Agent
- Owner 直接裁定（2026-07-27 對話，於本文件首次落成 repo 紀錄）：**「不採 GPT-5.4 mini」**
- 上位決策：
  - [ADR 0040：專業顧問引擎 greenfield 與 R1 驗證契約](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)
  - [ADR 0041：R1-P0 結案、第一版 Context 表示與案例分層](../adr/0041-r1-p0-closure-first-version-context-and-holdout.md)
- 專業方法：
  - [R1 Task Discovery 深入研究](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)
  - [顧問流程最終反方審查](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)
  - [顧問 LLM 架構紅隊審查](2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md)

> 本文件不是「把研究再寫一次」，而是把已核准原則收斂成**能實際比較的 R1 實驗設計**。
> 它刻意停在實作計畫之前：先讓第二位審查者攻擊變因、契約與裁決權，形成共識後才寫
> `docs/plans/`、runner 與 live preflight。

---

## 1. R1 真正要回答什麼

R1 只驗證職務分析最危險的第一層：

> 員工說了一段工作內容後，系統能不能把「工具、步驟、過去工作、他人工作、一次性支援」
> 與「本人目前穩定負責、具可辨識 outcome 的 Task」分開，並在資訊不足時問一個有價值的下一題？

R1 要回答四個工程問題：

1. **最小 prompt 就夠，還是完整 harness bundle 確實改善 Task 邊界？**
2. **一次模型呼叫就夠，還是先理解、再整併的兩階段值得多一次呼叫？**
3. **較重的 typed schema 是幫助模型，還是迫使模型填格、增加錯誤？**
4. **便宜模型能否在不增加 critical regression 的前提下接近品質天花板？**

R1 不能回答：

- 完整顧問流程是否已完成；
- 多輪訪談、長 context、恢復或文件共編是否可靠；
- Output、Indicator、K、S、A 是否正確；
- 三層 Hybrid Context 或 typed Work Model 是否各自具有獨立因果效果；
- 成品是否能取代真人顧問；
- 八個已曝光 development cases 是否證明 unseen generalization。

八案只用來淘汰明顯錯誤方向，不得宣布某架構「勝出」。

### 1.1 與完整顧問流程的對應

| 顧問流程 | R1 覆蓋 | R1 實際測什麼 |
|---|---|---|
| Step 0 開啟／恢復 | 否 | 不接 persistence |
| Step 1 blind-first 角色定位 | 否 | 案例不靠職稱或公版作答案 |
| Step 2 廣度工作地圖 | 很小一部分 | 只接受「資訊不足、需要繼續問」 |
| Step 3 持續顧問循環 | **是** | 理解整段回答、跨來源比較、選一個下一動作 |
| Step 4 故事深挖 | **是** | 一個故事多工作、多故事同工作、下一問 |
| Step 5 Task 邊界 | **R1 核心** | 工具／步驟／過去／他人／一次性、更正、merge／split |
| Step 6 Duty | 否 | Task 尚未累積到可合成 Duty |
| Step 7 O/P/K/S/A | 否 | 禁止在 R1 順便填欄位 |
| Step 8 公版 challenge | 否 | 保持 blind-first，避免公版錨定 |
| Step 9 文件共編 | 否 | 只輸出 recommendation，不修改正式 JD |
| Step 10 最終反方檢查 | 否 | 只有 R1 局部 critical checks |
| Step 11 完成 | 否 | R1 不得宣稱 JD 完成 |

所以 R1 不是完整顧問 prototype；它是後續所有 O/P/K/S/A、Duty 與 JD 品質都依賴的
**Task boundary 垂直切片**。若這一層做錯，後面欄位寫得再漂亮也只是把錯誤結構化。

---

## 2. 實驗外觀

```text
凍結的 case source snapshot
        │
        ├──────── A1／A6：一次 Task 分析 ──────────┐
        │                                           │
        └─ A2–A5：理解整段回答                      │
                     ↓                              │
                deterministic verifier              │
                     ↓                              │
                Task 整併／修正／下一問 ────────────┤
                                                    ↓
                                           final local verifier
                                                    ↓
                                         canonical review view
                                                    ↓
                                  盲化 model grader + owner 裁決
                                                    ↓
                                         Trial Manifest／報告
```

圖中的兩個模型步驟是**語意責任標籤**，不是永久 API、class 或 operation 名稱。實驗碼可暫稱：

- `understand_turn`：理解整段回答、來源、更正與責任語意，不建立正式 Task；
- `decide_task_changes`：跨來源與既有候選做 add／revise／merge／split／withdraw／clarify／no-change 建議。

不使用 `turn.understand`、`work.reconcile` 等舊 vNext operation 名作跨系統契約，避免把已退役架構名稱
偷渡進 greenfield。R1 結果出來後，才依保留的責任邊界決定 production 命名。

---

## 3. 六個 arm：完全沿用 ADR 0040

| Arm | Generator | schema | 呼叫方式 | harness |
|---|---|---|---|---|
| A1 | strongest | light | one-stage | minimal |
| A2 | strongest | light | two-stage | full |
| A3 | strongest | heavy | two-stage | full |
| A4 | economical | light | two-stage | full |
| A5 | economical | heavy | two-stage | full |
| A6 | strongest | light | one-stage | full |

### 3.1 三個有權回答的比較

| 比較 | 能回答 | 不能宣稱 |
|---|---|---|
| A1 vs A6 | 整個 full harness bundle 是否承重 | typed Work Model 單獨有效 |
| A2–A5 | model capacity × schema weight 的交互作用 | 任一模型普遍優於所有模型 |
| A2 vs A6 | 兩階段整體是否值得多一次呼叫 | 中間表示單獨有效 |

A2 vs A6 的「兩階段」同時包含中間 typed result、多一次推理與多一段 context，這是一個**架構 treatment**，
不是單一機制 ablation。文件與報告不得過度指定因果。

### 3.2 執行量

- 8 cases × 6 arms × 1 trial＝**48 個 case-arm observations**；
- A1／A6：16 次 generator calls；
- A2–A5：64 次 generator calls；
- 合計**最多 80 次 generator calls**：只有所有 Stage 1 都通過 interstage verifier 時才會實際打滿；
- Stage 1 terminal failure 仍是一個完整 observation，不是缺漏資料，但不再呼叫 Stage 2；
- grader calls 另計；
- provider／transport 失敗不算模型品質結果，必須保留失敗 attempt 並停止形成架構結論；
- 不自動補打；修復環境後若要補 attempt，須由 owner 核准新的 call budget，並在同一 batch report 明列；
- adapter 不得在單一 attempt 內偷偷 retry。

---

## 4. Case 契約

### 4.1 第一批固定八案

| Case | 主要能力 | 核心禁止錯誤 |
|---|---|---|
| TI-R1-01 | 工具不是 Task | Java／HTML／Python 各自變 Task |
| TI-R1-02 | 工具相關工作可形成有 outcome 的 Task | 因看到工具一律 no-op |
| TI-R1-03 | 一個故事可能有多個工作 | 每個動詞各拆一個 Task |
| TI-R1-04 | 多個故事可能支持同一 Task | 日常／月底／改版各建重疊 Task |
| TI-R1-05 | 過去工作不進現況 | 把前職責任寫入目前工作 |
| TI-R1-06 | 他人責任與交接 | 把維運部署誤收為本人 Task |
| TI-R1-07 | 一次性支援不等於穩定責任 | 一次代班直接成為 Task |
| TI-R1-08 | 更正必須壓過舊說法 | 被更正的本人部署責任復活 |

八案全部是 development screening；`TI-R1-02` 與 `TI-R1-07` 是 locked regression anchors，
不是 holdout。

### 4.2 每案的最小機器資料

每案只需要一份 `case.json` 加一份給人讀的 `adjudication.md`，不複製舊 vNext 的七檔 fixture。

`case.json` 概念欄位：

```json
{
  "schema_id": "professional-consultant-r1-case.v1",
  "case_id": "TI-R1-08",
  "case_revision": 1,
  "source_type": "constructed_edge",
  "case_family_id": "TI-R1-08",
  "sources": [
    {
      "source_id": "turn-001",
      "source_kind": "employee_turn",
      "speaker": "employee",
      "text": "我負責把版本部署到正式環境。"
    },
    {
      "source_id": "turn-002",
      "source_kind": "employee_turn",
      "speaker": "employee",
      "text": "剛才說錯，我只做上線前測試；正式部署是維運負責。"
    }
  ],
  "initial_work_model": {
    "task_candidates": [
      {
        "task_id": "task-existing-001",
        "task_statement": "將版本部署到正式環境",
        "source_ids": ["turn-001"]
      }
    ]
  },
  "expected": {
    "common_required_behaviors": [
      "final task view must not treat production deployment as the employee's responsibility"
    ],
    "common_forbidden_behaviors": [
      "the superseded deployment responsibility remains current"
    ],
    "common_applicable_rubric_dimensions": [
      "correction_authority",
      "responsibility_boundary"
    ],
    "full_harness_only_dimensions": [
      "state_change_targets_existing_task"
    ]
  }
}
```

這是設計形狀，不是最終 JSON Schema。實作時只保留 R1 真正使用的欄位。

`applicable_rubric_dimensions` 不是只看 case，而是 **case × arm class**：

- **共同語意維度**適用所有 arm：TI-R1-08 的共同要求是最終 Task 判斷不得讓「本人正式部署」復活；
  A1 從完整 transcript 就能做到，不需要知道 `task-existing-001`。
- **full-harness mechanical 維度**只適用 A2–A6 的 full arms：必須正確把 state-change 指向
  `task-existing-001`。
- full-only 維度可以阻擋一個 full arm 進 production shortlist，但**不得拿來宣稱 A6 的 Task 邊界
  優於 A1**，因為 A1 在結構上沒有該能力。

因此 TI-R1-08 不從 A1 排除，也不把整案記為 N/A；只把 A1 無法執行的 state-mutation mechanics 記為 N/A。

### 4.3 凍結規則

1. 先把八案的來源、required／forbidden behaviors、人工裁決理由凍結；
2. 記錄 suite canonical hash；
3. 才寫 prompt；
4. 不得因模型輸出不合預期而偷偷改 gold；
5. 真要改案例，升 `case_revision`、記理由並視為新實驗；
6. 八案預期已公開，因此只能作 development／regression，不能重新命名成 holdout。

### 4.4 R1 的 Source Layer 邊界

R1 只實際使用 `employee_turn`／必要的 `consultant_turn`。日後產品還需支援員工直接編輯與 proposal decision，
但不為未出現在 R1 的來源先建完整通用 provenance framework。

所有 Task 建議至少要帶：

- 一個或多個 `source_id`；
- 對應的 exact source quote；
- quote 必須是該 source text 的逐字子字串；
- 更正案必須指出新來源覆蓋了哪個舊來源或既有候選。

---

## 5. Context 設計

### 5.1 A1 minimal harness

A1 收到：

- 完整 case transcript；
- 一段精簡 Task 定義；
- 最終 light output schema。

A1 不收到：

- Current Work Model；
- actor／time／typicality／responsibility 的逐欄 checklist；
- correction policy；
- merge／split policy；
- source-link verifier 規則；
- 任何八案專屬答案或 few-shot example。

A1 不是「故意寫差的 prompt」，而是合理的最小 Task 分析 baseline。

### 5.2 A6 full one-stage

A6 收到：

- 完整 transcript；
- 最小 Current Work Model snapshot；
- Task 六項判準；
- actor、time、typicality、ownership、correction、unknown／no-op 規則；
- source grounding 要求；
- final light output schema。

它一次產出 Task change recommendations 與下一問。

### 5.3 A2–A5 full two-stage

Stage 1 收到：

- 與 A6 相同的完整 Source Layer；
- 相同的最小 Current Work Model；
- 理解責任、來源、更正與不確定性的 prompt；
- 對應 light 或 heavy intermediate schema。

Stage 2 收到：

- **相同的原始 Source Layer 與 Current Work Model**；
- 通過 local verifier 的 Stage 1 result；
- Task 六項判準與變更規則；
- 對應 light 或 heavy final schema。

Stage 2 不得只看 Stage 1 摘要。否則比較會把「兩階段推理」與「原文被壓縮遺失」綁在一起，
無法知道錯誤來自哪裡。兩階段的成本包含重送必要原文，必須據實記錄。

### 5.3.1 Interstage verifier 失敗

Stage 1 verifier 是 two-stage architecture treatment 的一部分，不是假裝所有 arm 都有的共同能力：

1. Stage 1 schema／parse／source linkage／ID 驗證任一失敗；
2. trial 立即以 `stage1_invalid` terminal outcome 結束；
3. 不呼叫 Stage 2；
4. 不自動 repair、不重跑、不把 invalid result 原樣放行；
5. 仍產生完整 Trial Manifest、Stage 1 request／response 與 verifier evidence；
6. 該 observation 在 deterministic validity 上為 fail，不能進 semantic grader；
7. transport／provider failure 另標 `harness_invalid`，不混成模型語意品質。

因此 two-stage arm 比 one-stage arm 多一個可能提早失敗的 interstage gate。這不是公平性 bug，
而是兩階段架構的真實成本；A2 vs A6 的 treatment 描述必須包含它。80 calls 是上限，不是保證實際值。

### 5.4 第一版不做檢索

八案都很短，Context Packet 固定為：

```text
完整 transcript
+ 最小 Current Work Model（full harness only）
+ 本 operation 的指令與 schema
```

不做 embedding、BM25、reranker、compaction、GraphRAG 或 summary-only。R1 不能驗證長對話 Context；
這留給 R2。

---

## 6. Output 與 schema treatment

### 6.1 所有 arm 的共同語意評審視圖

不同 schema 最後都投影成同一個 `CanonicalTaskReviewView`，盲評只看這個共同視圖：

```text
analysis_decision
  = propose_current_tasks | clarify | no_change

proposed_tasks[]
  - task_statement
  - intended_outcome
  - source_anchors[]        # 每筆 = { source_id, quote }

next_question
  - text | null
  - purpose | null

limitations[]
```

`proposed_tasks` 在 R1 代表「根據本 case 所有來源，模型目前認為應成立的完整 Task 語意集合」，
不是只列本輪新增 delta。因此 A1 在 TI-R1-08 可以用「保留上線前測試、不保留本人正式部署」通過共同語意；
它仍不需要知道舊候選的內部 ID。

Full harness 另有不進共同盲評的 `StateChangeDiagnosticView`：

```text
change_type
  = add | revise | merge | split | withdraw | no_change

affected_existing_task_ids[]
```

這讓 A1 可依 transcript 通過共同 correction 語意，又不假裝它有能力操作看不到的 Current Work Model ID。
State-change mechanics 由 full-only verifier／rubric 檢查，不混入 A1 vs A6 的 Task-boundary 分數。

`source_anchors` 必須同時帶 `source_id` 與逐字 `quote`（設計 §4.4）：只給 quote 無法確認模型指的是
哪一筆來源，也無法驗證更正關係。local verifier 驗 `source_id` 存在，且 quote 是**該筆** source 的子字串。

模型可輸出一段短 `decision_basis` 供除錯，但：

- 不要求或保存 chain-of-thought；
- **`decision_basis` 屬於 raw output，不屬於 `CanonicalTaskReviewView`**；
  投影成 grader packet 時由 projector 強制移除，不靠 prompt 約定；
- blind grader 不讀 `decision_basis`；
- `decision_basis` 不可補救缺失的來源；
- 正式比較以 Task 結果、來源與下一問為準。

### 6.2 Light schema

Light schema 只要求做出決策所需的最小欄位：

- analysis decision；
- proposed Task statement／outcome／source quotes；
- next question；
- limitations；
- short decision basis。

Full harness 的 light schema 另帶最小 `state_change`；A1 的 minimal light schema 不帶。
這是 minimal／full harness bundle 的既定差異，不冒充 schema-weight ablation。

沒有逐欄 boundary assessment，也不強迫每個 qualifier 都有格子。空 Task 陣列合法；
`clarify`／`no_change` 不得被 schema 迫使產生 Task。

### 6.3 Heavy schema

Heavy schema 的**語意任務與 prompt rubric 不變**，但要求把分析顯式放入 typed 欄位：

- Stage 1 observation：
  - actor；
  - time scope；
  - typicality／frequency；
  - responsibility；
  - activity kind；
  - intended outcome；
  - correction target；
  - unknown／unmapped reason；
  - source quotes。
- Stage 2 Task assessment：
  - meaningful outcome；
  - role responsibility；
  - assignability；
  - checkability；
  - stability；
  - boundary coherence；
  - proposed change；
  - affected IDs；
  - next-question target。

Heavy schema 不增加案例答案、不加入額外 few-shot，也不比 light schema取得更多來源。它刻意測量：

> 把相同判準強迫模型逐欄輸出，究竟提供有用 scaffolding，還是造成填格、合理化與 token 負擔？

Heavy schema 必須仍使用 ADR 0040 的 portable subset，不故意做成 provider 難以支援的壓力測試。

### 6.4 Normalization 與公平性

- light／heavy 都投影到同一 `CanonicalTaskReviewView`；
- grader 看不到 schema 名稱、arm 名稱或 heavy-only 欄位；
- heavy-only 欄位只用於診斷 Stage 1／Stage 2 錯在哪；
- schema adherence 單獨記錄，不與 Task 語意品質混成一個總分；
- 若 normalization 遺失 Task 語意，整批標 `harness_invalid`，不可繼續比較。

---

## 7. Prompt 設計規則

### 7.1 共同規則

- 使用繁體中文；
- 只分析員工本人目前工作；
- Story 是證據，不自動等於 Task；
- 工具、技術、步驟、K/S 線索不因被提及就成為 Task；
- Task 要有可辨識 outcome、本人責任、可指派／可檢查、相對穩定且邊界一致；
- 正式低頻責任可以是 Task，一次性代班通常不是；
- 最新明確更正壓過舊說法；
- 不足時可 `clarify`／`no_change`，不得為填 schema 猜答案；
- 一次只問一個主要問題；
- 不產出 O/P/K/S/A 或完整 JD。

### 7.2 不做的 prompt 技巧

- 不要求逐步展示思考；
- 不靠 schema key ordering 逼模型「先推理」；
- 不使用八案原句或答案作 few-shot；
- 不塞公版職務內容；
- 不讓模型看 grader rubric 的 case-specific expected answer；
- 不做模型自我反思迴圈或多 Reviewer 互相投票；
- 不在正式 batch 中臨時修 prompt。

Prompt、schema、context assembler 各自版本化。正式 batch 開始後任一者改動，都必須另開 batch。

---

## 8. Model 與 provider 提案

### 8.1 Generator 配對

依本文件首頁記錄的 owner 裁定，R1 不採 GPT-5.4 mini，改提議使用同一 OpenAI 5.6 家族、
同一 `pro` reasoning mode：

| 角色 | Proposed exact OpenRouter slug | 原因 |
|---|---|---|
| strongest | `openai/gpt-5.6-sol-pro` | 先建立品質天花板 |
| economical | `openai/gpt-5.6-luna-pro` | 同家族、同 pro mode，降低 provider／reasoning 設定混淆 |

OpenRouter 目前把 Sol Pro 與 Luna Pro 描述為各自底層模型以 `reasoning.mode=pro` 提供的版本：

- [GPT-5.6 Sol Pro](https://openrouter.ai/openai/gpt-5.6-sol-pro-20260709)
- [GPT-5.6 Luna Pro](https://openrouter.ai/openai/gpt-5.6-luna-pro)

這是**待 live preflight 核對的提案**，不是永久模型常數。正式凍結前必須從 catalog／endpoint API 取得：

- canonical model slug；
- 可用 endpoint；
- supported parameters；
- pricing／context snapshot；
- resolved provider／endpoint；
- model 與 endpoint snapshot hash。

若兩者無法同時固定到 `openai` upstream endpoint，必須停下討論，不得默默把一個切到 Azure 或開 fallback。

### 8.2 Blind grader

建議使用一個獨立模型家族作盲評，初始候選為：

```text
anthropic/claude-opus-5
```

Anthropic 於 2026-07-24 發布 Claude Opus 5，官方 API ID 是 `claude-opus-5`；
OpenRouter 當期 catalog 頁的 slug 是 `anthropic/claude-opus-5`。4.6 已不是本設計日期的現行候選：

- [Anthropic：Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5)
- [OpenRouter：Claude Opus 5](https://openrouter.ai/anthropic/claude-opus-5)

這仍只是 proposed slug。grader 必須與 generator 一樣通過 catalog／endpoint／supported-parameters、
structured-output live preflight，並保存 model／endpoint snapshot hash；不得只驗 generator。

理由不是「Claude 一定比較正確」，而是降低 generator 與 grader 共享同一模型偏差的風險。正式 grader：

- 每個 case 讀取六份匿名 canonical views **兩次**；
- 第一次用 seeded permutation，第二次用完全反轉順序；
- 兩次判決不一致的 dimension 一律為 `unknown`，不以多數決硬猜；
- 不看 arm、模型、schema、latency、cost 或 generator rationale；
- 按 rubric 維度回 `pass／fail／unknown`；
- `unknown` 與 grader／deterministic 衝突一律交 owner；
- 只作評審證據，不自行 promotion。

正式八案預定 16 次 grader calls。若成本估算超出 owner 限額，停下縮減整體 batch 或另行裁決；
**不得**用 strongest generator 自評作成本逃生門。

### 8.2.1 Grader 校準

正式 batch 前：

1. 建一個不屬於八案的 disposable calibration packet，含明顯 pass、明顯 fail、合理 unknown 三種匿名輸出；
2. owner 先依 Job Analysis Quality Rubric 人工裁決；
3. grader 跑正序／反序，與 owner 比對；
4. 最多允許一輪 grader prompt 修正；
5. 凍結 grader prompt／rubric／schema hash 後才跑正式 batch；
6. `TI-R1-02`／`TI-R1-07` 的全部 arm 輸出，以及任何 critical fail／unknown，仍由 owner 以匿名
   common review view 人工覆核。

校準只校準 grader，不得拿來調 generator prompt。

### 8.3 Exact routing

正式請求最低要求：

- `provider.only` 與 `provider.order` 都固定單一 upstream；
- `allow_fallbacks: false`；
- `require_parameters: true`；
- exact model slug，不用 `auto`／`latest`／`free`／`nitro`／`floor`；
- 不使用 tools、provider conversation state、preset 或自動模型路由；
- response cache／會改寫內容的 plugin 禁用；
- transport／adapter 不 retry；
- 啟用可取得 resolved route facts 的 OpenRouter metadata；
- request 使用 `response_format: json_schema` 與 `strict: true`；
- local verifier 永遠再驗一次。

依據：

- [OpenRouter Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)

---

## 9. Provider 實作邊界：三個方案

### 9.1 方案 A：直接重用 vNext adapter

優點：

- 已有 route metadata、單次 HTTP、schema hash、usage 與錯誤矩陣；
- 已測過 OpenRouter fail-closed 行為。

問題：

- adapter 綁定 `interview_vnext` 的 `LlmPort`、artifact、run／session／turn／attempt、Capture 與 conformance 契約；
- R1 是 greenfield eval，不需要 durable workflow 與舊 Evidence；
- 為了送一個實驗 request 引入大量舊 domain，會違反 ADR 0040 的隔離目的。

**不建議。**

### 9.2 方案 B：R1 experiment-only thin transport

只用既有 `httpx.AsyncClient` 建一個小型 transport：

- catalog／endpoint preflight；
- exact request body；
- 單次 HTTP；
- typed wire result；
- route／usage／cost／latency facts；
- secret／reasoning redaction；
- raw request／response capture；
- 不負責 Task 語意、grader、Current Work Model 或 production retry。

它要**沿用 vNext 已驗證的不變量與失敗案例**，但不 import 舊 Task／Evidence／Capture domain。

「沿用」必須落成明確清單，不能只寫口號：

| 既有參考檔 | 只移植／重寫的行為不變量 | 不帶入 |
|---|---|---|
| `app/interview_vnext/providers/openrouter_catalog.py` | canonical model／endpoint snapshot、supported parameter、single-endpoint preflight、snapshot hash | vNext artifact／identifier types |
| `app/interview_vnext/providers/openrouter_routing.py` | official nested與legacy flat metadata、唯一 selected endpoint、attempt count、pipeline／cache／route fail-closed | vNext execution evidence／conformance types |
| `app/interview_vnext/providers/openrouter_chat.py` | exact request body、單次 HTTP、status／parse matrix、usage／decimal cost normalization、secret／reasoning redaction | `LlmPort`、run／session／turn、Capture、durable operation |

R1 以自己的小型 contracts 與 tests 重新表達這些不變量，不 import 上列模組。dependency guards 同時要求：

- production `app/` 不 import `evals.professional_consultant_r1`；
- 新 R1 eval 不 import `app.interview_vnext`。

**建議採用。** 這是 R1 的最小需要，且不先發明 production provider framework。

### 9.3 方案 C：先抽共用 provider package

長期可能乾淨，但現在會先做 generic abstraction、遷移舊 adapter、重新跑大量 conformance 測試，
而 R1 尚未證明 production operation 形狀。

**第一版拒絕；等 R1 選出 architecture、開始 production vertical 時再決定是否抽取。**

---

## 10. 最小 Capture 與 Trial Manifest

R1 不建 event sourcing、DB 或完整 vNext Capture。每個 trial 建一個不可變目錄：

```text
trial/
  source-snapshot.json
  context-stage-1.json          # one-stage arm 可沒有
  request-stage-1.json
  response-stage-1.json
  context-final.json
  request-final.json
  response-final.json
  verifier.json
  review-view.json
  grader.json
  manifest.json
```

`manifest.json` 至少保存：

- case ID／revision／family／source type／suite hash；
- arm、round、attempt；
- prompt／schema／context assembler version 與 canonical hash；
- requested model、resolved model、resolved provider／endpoint；
- provider config 與 catalog snapshot hash；
- 各檔案 reference；
- HTTP／parse／schema／local verifier outcome；
- token usage、cost、latency；
- grader model／prompt／rubric version；
- owner adjudication；
- limitations；
- 若為 post-freeze fresh challenge，保存 freeze commit SHA + canonical hash。

禁止保存：

- API key／Authorization；
- provider 隱藏 reasoning；
- 模型 chain-of-thought；
- 未遮罩 secret；
- 由 request 猜出的 resolved endpoint。

這三層 capture 的用途分開：

1. source snapshot：未來可重跑新的 Context Builder；
2. context + operation input：可比較 prompt／schema／operation；
3. trial evidence：可審查當時到底送了什麼、回了什麼、怎麼裁決。

---

## 11. Grading 與預先登記的裁決

### 11.1 Deterministic checks

- JSON 可解析且符合 portable schema；
- source ID 存在；
- quote 是允許來源的逐字子字串；
- ID／跨欄位引用合法；
- correction target 存在；
- `clarify`／`no_change` 時可有 0 個 Task；
- forbidden source／arm metadata 未進 grader view；
- 同一 Task／source quote 沒有機械重複；
- provider route、model、endpoint 符合 binding；
- 無隱藏 retry／fallback／cache replay。

規則程式只驗能確定的事，不用關鍵字規則直接裁決「這是不是 Task」。

### 11.2 Semantic rubric

每個 `(case × arm class)` applicable dimension 回 `pass／fail／unknown`：

- meaningful outcome；
- employee responsibility；
- assignability／checkability；
- stability／formal low-frequency；
- merge／split boundary；
- past／other／one-off exclusion；
- correction authority；
- source grounding；
- uncertainty honesty；
- next-question value、單一焦點與自然度。

`unknown` 不算 pass，也不靜默丟掉；由 owner 裁決或將該比較標 `inconclusive`。
共同 Task-boundary dimensions 與 full-only state-mutation dimensions 分開報告；後者不得用來替 full harness
取得 A1 vs A6 的品質優勢。

### 11.3 Critical anchors

- `TI-R1-02` 必須能形成有 outcome 的 Task 候選；
- `TI-R1-07` 必須能拒絕一次性代班成為穩定 Task；
- correction 不得復活；
- 不得有 tool-as-task、step-as-task、past／other／one-off leakage；
- 不得因 schema 必填而硬造 Task；
- 不得產生沒有 source 的 Task。

任一 locked anchor 失敗，該 arm 不進 shortlist；這是 development screening 結論，不是假裝統計證明。
兩個 anchor 的全部輸出必須由 owner 人工覆核，不能只靠 model grader。

### 11.4 「實質改善」的第一版定義

八案只允許形成方向性的 `screening_signal`：

- 在至少 **2 個不同 cases** 的 mandatory Task-boundary dimensions 上改善；
- 沒有任何新的 critical regression；
- grader 與 owner 裁決不衝突；
- deterministic validity 不退步。

第一批八案沒有衍生案例，因此 `case_family_id == case_id`；這裡的「2」只是兩個單次 observation，
**不是聚類控制、重複驗證或統計獨立性證據**。`case_family_id` 的作用要到 20–30 案包含同 family 衍生案例
時才真正生效。

若只改善 1 個 case，標為 `flagged_n1`；兩個 case 形成 `screening_signal_n2`。
兩者都不能拔擢架構，只能決定「明顯淘汰」或「值得進 20–30 案繼續測」。

因此：

- A1 vs A6 持平 → 保留 minimal baseline；
- A2 vs A6 持平 → 保留 one-stage A6；
- light vs heavy 持平 → 保留 light；
- economical vs strongest 持平 → economical 只取得進入下一階段的候選資格，不直接成為 shipping model；
- 任一比較只在可適用 cases 中有 1 個差異 → `inconclusive／flagged_n1`。

20–30 案與 shortlisted critical pass³ 才能形成進 R2 的 gate；八案不能。

### 11.5 可診斷但不能當通行證

下列項目可記錄，但不能單獨替複雜架構取得勝利：

- 中間結果更好看；
- 錯誤比較容易定位；
- schema 欄位較完整；
- rationale 較長；
- model grader 較喜歡文風；
- 可觀測性較多。

核心仍是 Task 邊界與 critical failures。

---

## 12. 實驗前測試

### 12.1 No-network safety net

只測會保護結論的最小集合：

1. 8 cases 載入、metadata 與 frozen suite hash；
2. 6-arm matrix 正確產生 48 observations／預定 80 generator calls；
3. light／heavy schema 可生成且符合 portable subset；
4. 0 Task、clarify、no-change、correction、merge／split 可表達；
5. source quote／ID／correction local verifier；
6. common review normalization 不洩漏 arm；
7. request body exact routing、禁 fallback、無 tools／preset／cache；
8. 429／500／timeout 每 attempt 只有一次 HTTP；
9. resolved route 只能由 response metadata 取得；
10. secret／reasoning 不進 capture；
11. Trial Manifest 可驗 refs、版本與 hash；
12. blind grader 的 `unknown` 不會被算成 pass。

不追求每個 DTO 的排列組合全覆蓋，也不跑舊 vNext 全套測試作為每個小改動的日常 gate；
只跑 dependency guard，確保 production 不 import 新 eval。

### 12.2 Disposable plumbing smoke

正式八案前，用一個**不在 suite 內、跑完丟棄**的無爭議案例驗：

- catalog／endpoint；
- structured output；
- capture；
- grader；
- cost 計算；
- output 路徑。

Smoke 結果不得用來調整八案 gold，也不得作架構結論。

### 12.3 Paid run 前停線

付費前必須同時具備：

- owner 與第二位審查者核准本設計；
- implementation plan 已核准；
- no-network tests 綠；
- disposable live preflight 綠；
- exact model／endpoint／pricing snapshot；
- 根據實際 prompt tokens 算出的成本上限；
- owner 明確允許該次付費 batch；
- `.env` key 只在本機載入且不進 artifact／git。

任何一項缺失都不跑正式八案。

---

## 13. 結果怎麼解讀

| 觀察 | 允許的初步解讀 | 不允許的解讀 |
|---|---|---|
| A1≈A6 | full harness 未顯示實質改善 | Context Engineering 永遠沒用 |
| A6>A1 | full bundle 值得進 shortlist | typed Work Model 已被單獨證明 |
| A2>A6 | 兩階段整體值得進 shortlist | Stage 1 typed object 單獨有效 |
| A6≥A2 | 先保留一次呼叫 | 所有多階段工作流都錯 |
| light>heavy | **在兩階段架構下**，目前 heavy schema 可能妨礙模型 | structured output 都有害 |
| heavy>light | **在兩階段架構下**，typed scaffolding 可能承重 | 越多欄位越好 |
| Luna≈Sol | 便宜模型可進下一階段 | Luna 已可出貨 |
| Luna<Sol | 模型容量可能是限制 | harness 架構一定正確 |
| 所有 arm 同案失敗 | case／rubric／共同 prompt 或任務本身有問題 | 任選一個 arm 修 prompt 即可 |

---

## 14. Make the strongest case that this design is still wrong

### 14.1 八案全部已曝光

Prompt 作者已看過案例與期望，很容易無意識 overfit。凍結 gold 只能防止移動球門，不能證明泛化。
修正是：八案只淘汰明顯錯誤；20–30 案階段在最後 freeze 後才建立 post-freeze fresh challenge set。

### 14.2 A1 vs A6 不是乾淨單變因

它一次更換整個 harness bundle。這是刻意的產品級 treatment，但不能得出 typed Work Model 的獨立因果結論。
若日後真的需要該結論，另開一個只改 Context 表示的專門實驗，不把它偷塞進 R1。

TI-R1-08 另有一個結構差異：A1 看不到 Current Work Model ID。共同盲評只比較「更正後的 Task 語意」；
只有 full arm 才評 state-mutation target。若把 full-only mechanics 算進共同分數，實驗會預先保證 A1 失敗。

### 14.3 Heavy schema 可能變成答案提示

逐欄 `responsibility／time／correction` 會提示模型注意 critical dimensions。這正是 scaffolding 的一部分，
也是受測 treatment；但 heavy schema 不能含 case-specific label、gold 或額外來源，grader 只看共同投影。

### 14.4 兩階段同時改很多機制

多一次呼叫、中間表示、重送 context 與錯誤傳播一起變動。R1 只能判斷這整包值不值得，不可宣稱是哪一個
機制生效。兩階段還多一個 interstage verifier；Stage 1 invalid 時會提早終止且少打一個 call。
持平選一次呼叫，避免為可診斷性而多建架構。

### 14.5 Model grader 仍可能有偏誤

換 Claude 不會自動得到真相；它可能偏好特定文風或與 strong generator 有不同 Task 粒度。
因此 grader 可回 Unknown、先以人校準、不得讀 rationale，critical 結論仍可由 owner 覆核。

### 14.6 80 次 calls 仍可能比問題需要的多

成本來自 ADR 0040 要同時排除模型能力、schema 與拆分三種混淆。若 owner 決定不支付成本，
正確作法是明文取消或縮減 R1 並記錄證據缺口，不得把沒跑寫成「研究已證明」。

---

## 15. 需要第二位審查者共同裁決的六點

第二位審查者請優先攻擊下列六點，不必再重審已由 ADR 0040／0041 固定的產品範圍：

1. **Provider seam**：是否同意 R1 用 experiment-only thin transport，不 import vNext adapter，
   也不先抽 generic provider package？
2. **Generator 配對**：`gpt-5.6-sol-pro`／`gpt-5.6-luna-pro`、同 `openai` endpoint 是否是目前最少混淆的
   strongest／economical 配對？
3. **Stage 2 context**：兩階段第二步保留原始 transcript，再加 verified intermediate，是否是最公平的
   A2 vs A6 treatment？
4. **Light／heavy 邊界**：heavy 只增加 typed assessment，不增加來源、案例答案或 few-shot，是否足以測 schema burden？
5. **Blind grader**：是否接受 Claude Opus 5 每 case 正序／反序各一次、分歧為 Unknown，
   先過 disposable owner calibration，anchors 與 critical 仍由 owner 覆核？
6. **八案門檻**：至少兩個 cases 改善、無 critical regression 才算 `screening_signal_n2`；
   locked anchors 任一失敗即不進 shortlist，是否過嚴或過鬆？

在六點形成書面共識以前：

- 不寫 production code；
- 不接 Web／DB；
- 不跑正式付費 batch；
- 不建立 R1 結果 ADR；
- 不把 Proposed 模型 slug 寫成永久產品設定。

---

## 16. 共識後的最短實作路線

共識形成後才另寫 `docs/plans/`，預計只切五段：

1. **Contracts + 8 cases + rubric + verifier**：全 no-network；
2. **Thin OpenRouter transport + capture**：mocked HTTP、單次呼叫；
3. **六 arm assembler + runner + blind grader**：先用 scripted output；
4. **Disposable live preflight**：核對 model／endpoint／schema／route／成本；
5. **正式 48 observations**：生成報告，與第二位審查者共同裁決下一階段。

這條路徑先證明 Task 分析核心，不做 Web、不做 SaaS、不做完整資料模型，也不為未來 R2–R9 建框架。

---

## 17. 2026-07-27 第二位審查者第一輪意見處理

| 意見 | 查證後裁決 | 文件處理 |
|---|---|---|
| B1：TI-R1-08 讓 A1 結構性必敗 | **部分成立**。A1 無法操作既有 ID，但能依逐字稿通過共同 correction 語意 | 拆共同語意與 full-only state mutation；不把整案對 A1 記 N/A |
| B2：Stage 1 verifier failure 未定義 | **成立** | 定義 terminal `stage1_invalid`、不 repair／不放行／不打 Stage 2；80 改為上限 |
| B3：Opus 4.6 過時且 grader 未 preflight | **成立**。Anthropic／OpenRouter 均可查到 2026-07-24 Opus 5 | 改 proposed `anthropic/claude-opus-5`；grader 也做完整 preflight／snapshot |
| S1：兩個 family 其實只是兩個 n=1 cases | **成立** | 改稱 `screening_signal_n2`，明寫沒有統計／聚類效力；不增加快篩重複，維持 ADR 0040 的 8×6×1 |
| S2：heavy 結論缺兩階段限定 | **成立** | 所有結果解讀補上「在兩階段架構下」 |
| S3：單次隨機排序不能消除位置效應 | **成立** | 每 case 正序／反序各評一次；不一致為 Unknown；移除 same-generator 成本逃生門 |
| S4：缺 grader 校準 | **成立** | 增加 disposable packet、owner gold、一輪修 prompt 後 freeze |
| S5：GPT-5.4 mini owner 裁定無 repo 出處 | **成立** | 文件首頁正式記錄 owner 原話與日期，§8.1／舊研究改引用本文件 |
| Provider seam 補充：不變量來源與單向依賴需具體 | **成立** | 列出 catalog／routing／chat 三檔責任；新增雙向 dependency guards |
| Stage 2 保留原文、light／heavy 邊界、anchors | **接受審查結論** | 設計維持；補強 mechanics 與 owner anchor review |

本表是 Proposed 文件的修訂紀錄，仍待第二位審查者確認是否已消除 blocker；不代表 R1 已核准施工。
