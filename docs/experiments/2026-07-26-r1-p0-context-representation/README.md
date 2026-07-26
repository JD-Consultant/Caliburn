# R1-P0 Context Representation Subagent Screening

- 日期：2026-07-26
- 狀態：**Designed（2026-07-26 corrective revision）— 待建立正式案例後執行**
- 性質：R1 前置、免外部 API key 的**否證實驗**
- 不使用：`OPENROUTER_API_KEY`、`OPENAI_API_KEY`、production route、Web、資料庫
- 上游 authority：
  - [ADR 0040](../../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)
  - [R1 Task Discovery 深入研究](../../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)
  - [2026-07-26 紅隊修訂](../../specs/2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md)

## 1. 要回答的問題

目前架構把原始對話轉成 Evidence／Work Model，再由 Context 組裝器提供給後續模型。P0 只打其中最小的一問：

1. 強模型直接閱讀原始對話，是否已足以正確辨識 Task？
2. 把關鍵原句重貼一次（提高顯著性）本身是否就足以解釋任何改善？
3. 在完整原文之外再加一份**字面 claim table**，是否另外還有價值？
4. 若用字面結構取代員工原話、但仍保留顧問逐字提問，會遺失多少否定、更正、時間、責任邊界與故事脈絡？

**P0 是否證實驗。** 它可以證明「人工整理的字面 claim table 沒有加值」，因此第一版不建這層；
但它**不能**因為人工理想表示表現好就宣稱 Evidence 架構已成立——那只換得「值得進一步驗證」資格。
本實驗不選 OpenRouter shipping model，也不驗證 provider structured output、routing、成本或 latency。

### 1.1 預先登記的預期結果

§3.1 把受測結構化表示削到只剩「原子化切分 + 完整覆蓋」之後，自變數很薄。
**最可能的結果是 Hybrid 與 Raw+Spans 持平，依 YAGNI 選 Raw。** 這句話在跑第一個 trial 前寫定，
事後不得把持平重新解釋成別的結論。

## 2. 為什麼先做 P0

ADR 0040 的正式 R1 六 arm 會同時比較 model、schema、單／雙階段與整體 harness。它可以判斷 full harness
是否承重，卻不能單獨歸因 Context 表示的價值。

若連理想化的字面結構表示都無法優於 Raw-only 與 Raw+Spans，就不應先建專用的 literal-claim layer。
typed Evidence／Work Model 的價值仍超出 P0 射程，不能由這個結果一併否決。

## 3. 受測 arms

四個 arm 使用相同案例、受測模型、共同指令、輸出格式與 rubric，只更換 `context_payload`。

| Arm | 模型看到的 Context | 這個 arm 存在的理由 |
|---|---|---|
| `raw_only` | 完整案例 transcript，逐字保留 | 最簡單 baseline；測強模型能否自行理解 |
| `raw_plus_spans` | 完整 transcript ＋ 相關原句逐字重貼一次 | 隔離**顯著性／重複**效果，不含任何結構化欄位 |
| `hybrid` | 完整 transcript ＋ 相同相關原句 ＋ 字面 claim table | 測 claim table 在顯著性之外是否另有價值 |
| `structured_only` | 顧問 turns 逐字保留；員工 turns 由字面 claim table 取代 | 診斷員工原話被字面結構取代時的資訊損失；**不是產品候選** |

三個成對比較各只打開一個變因：

| 比較 | 唯一差異 | 回答 |
|---|---|---|
| `raw_only` vs `raw_plus_spans` | 關鍵原句是否被重貼 | 顯著性／重複是否有幫助 |
| `raw_plus_spans` vs `hybrid` | 是否附 claim table | 結構化是否另外有價值 |
| `raw_only` vs `structured_only` | 只把員工原話換成字面 claims；顧問 turns 不變 | 取代員工原話會損失什麼 |

**`hybrid` 必須保留完整 transcript。** 原設計的 hybrid 省略未選中的 turns，於是同時改動了「結構」與
「資訊刪減」兩個變因，任何差異都無法歸因。長對話壓縮是另一個問題，另開實驗。

### 3.1 結構化表示只能是字面 claim table

若結構化欄位帶著 `responsibility`／`time_scope`／`candidate_kind`／`corrections`／`unresolved`，
它們與 rubric 的 critical checks 幾乎一對一（C2／C4／C1／C4／C5），等於人工先完成一半職務分析，
再把答案卡交給受測模型。那不是重新表示，是洩漏。

因此 P0 的 claim 只保留**低推論、可逐字核對**的欄位：

```text
claim_id / literal_text / source_turn_ids / sequence_index / speaker
```

**刪除**：`actor`、`time_scope`、`responsibility`、`candidate_kind`、`corrections`、`unresolved`、
`qualifiers`。這些都是受測模型應該自己判斷的結果。

削減之後，claim table 剩下的唯一變換是**原子化切分**：一個回合被切成多條獨立陳述，
並保留 `sequence_index` 讓先後關係可判。這就是 P0 的自變數，構造規則（逐字子字串、完整覆蓋、
切分規則寫死）見 [`cases/README.md`](cases/README.md)。

其中**完整覆蓋**是硬條件：claim table 必須收錄員工的每一條陳述，包含工具提及、過去工作、他人責任與
後來被撤回的說法。若案例作者因為「那不是 Task」而不收，答案卡就用**省略**重建了，
而且 `structured_only` 與 `raw_only` 會塌成同一個 arm。

### 3.2 P0 測不到的東西（射程限定）

R1 的 Evidence／Work Model 之所以叫 typed，價值假說本來就在 actor／time／responsibility 這些格上。
為了消除洩漏而去型別之後，**P0 對 typed Work Model 的價值結構性不可判定**。那個問題屬於：

- 後續 extraction fidelity 實驗（模型自己產生型別欄位，錯誤可歸因到模型，等同 production 條件）；
- ADR 0040 的 A2 vs A6（兩階段 vs 一次呼叫）。

P0 的任何結論**不得**寫成「Evidence 架構已被實驗否決／成立」。

## 4. 受測模型策略

### 4.1 一律使用最強模型

- requested model：`gpt-5.6-sol`
- reasoning effort：`high`（C-01 要求先建品質天花板；四個 arm 與兩輪一律相同，不得中途更改）
- 每個 case × arm × 重複一個新的 subagent，`fork_context=false`

**不做便宜模型快篩。** 原設計先用 `gpt-5.6-luna` 跑 18 trials 再以強模型複驗，
但無論快篩結果如何，最終都由強模型裁決，因此快篩沒有架構裁決能力，也無法排除模型能力不足這個混淆因子。
這與紅隊修訂 C-01 衝突，已移除。

### 4.2 兩輪規模

| 輪 | 規模 | 用途 |
|---|---|---|
| 1. 全案例 | 6 cases × 4 arms × 1 = **24 trials** | 找出方向與明顯失敗 |
| 2. 關鍵案例重複 | 3 critical cases × 3 產品 arm × 2 = **18 trials** | 把決策從單一二元事件拉到 3 次一致 |

合計 **42 個最強 subagent trials**。第 2 輪只重複 `raw_only`、`raw_plus_spans`、`hybrid`；
`structured_only` 是診斷用，不重跑。

關鍵案例在第一個 trial 前指定為 **CR-01、CR-03、CR-05**（工具升格、多故事錯拆成多個 Task、
更正否定）。它們直接覆蓋前版產品的工作爆量風險、Task merge/split 與跨回合修正；CR-04 責任邊界
仍在第 1 輪執行，但不作三次重跑。

### 4.3 Subagent 邊界

Subagent 在這裡就是**原本要由 API 呼叫的受測 LLM**，不是文獻研究員。每個 subagent：

- 只收到 §6 的共同指令、單一 case 的指定 Context，以及輸出要求；
- 不繼承目前 thread 的對話歷史（`fork_context=false`）、其他 arm 結果或人工裁決；
- 被要求不讀 repo、不呼叫工具、不使用外部知識；
- 不被要求產生或揭露 chain-of-thought。

`fork_context=false` 只代表不繼承對話歷史，**不保證沒有平台 system／developer instructions 或
專案 instructions**。本 repo 的 `AGENTS.md` 帶著職務分析詞彙與產品目標，且注入不是 subagent「讀」進去的，
「要求不讀 repo」擋不住。這些 instructions 不可完整觀測，視為 **across-arm 常數**：相對比較仍可用，
但會抬高絕對表現，且與 OpenRouter production 條件不同。

不向 subagent 索取隱藏 instructions 自述：模型無法可靠列舉、自述無法證明完整性、可能受平台限制，
而 multi-agent 介面也不能指定 repo 外的 cwd。列為外部效度限制（§11），不做 probe。

## 5. 案例

P0 固定六個 case；每案只測一個主要風險，避免案例數膨脹：

| Case | 主要風險 |
|---|---|
| `CR-01-tools-not-tasks` | Java／Python／HTML 等工具或技能被升格成 Task |
| `CR-02-one-story-many-work` | 一個故事包含多個具有不同產出的工作 |
| `CR-03-many-stories-one-task` | 多個故事只是同一穩定工作的不同實例 |
| `CR-04-responsibility-boundary` | 他人責任、偶爾協助與本人穩定責任混淆 |
| `CR-05-correction-and-negation` | 後續更正、否定與時間範圍被舊說法覆蓋 |
| `CR-06-insufficient-evidence` | 資訊不足時模型被迫製造 Task |

**六案不是 ADR 0040／C-03 的正式八案 R1 screening。** P0 是專門隔離 Context 表示的最小案例組，
每案對應一個表示風險；正式 R1 的案例規模與階段仍照 C-03 執行，兩者不得互相替代。
同理，`raw_only` 只是 A1 minimal-harness baseline 的**概念近似**——runtime、模型與 harness 都不同，
不得拿 P0 結果代替正式 A1。

案例格式與建立規則見 [`cases/README.md`](cases/README.md)。正式 transcript 與四種 context payload
必須在第一個 trial 前一次完成並固定。

## 6. 共同受測指令

以下文字是所有 arm 的共同 instruction；實際送出的單一完整 request 仍逐 trial 原樣保存在 `trials/`：

```text
你是受測的職務分析模型。你只能根據 INPUT_CONTEXT 判斷，不得使用外部知識、repo、工具或其他對話。

目標是辨識員工目前、穩定、屬於本人責任，且具有可辨識目的或結果的工作任務。工具、技術、知識、
技能、單一步驟、一次性事件、過去工作、假設工作與他人責任不得直接升格成 Task。資訊不足時可以不建立 Task。

引用來源時只能使用 turn ID（形如 turn-001）。即使 INPUT_CONTEXT 含 claim ID，也不得引用 claim ID。

只輸出一個 JSON object：
{
  "tasks": [
    {
      "statement": "動詞開頭的工作敘述",
      "source_ids": ["可直接支持此 Task 的 turn ID"]
    }
  ],
  "excluded_mentions": [
    {
      "source_id": "turn ID",
      "reason": "tool_or_skill|step|past_work|hypothetical|other_person|one_off|insufficient"
    }
  ],
  "uncertainties": ["目前無法安全判斷的事項"],
  "next_question": "最能降低目前關鍵不確定性的單一問題；若不需要則為 null"
}

不要輸出 JSON 以外的文字。不得為填滿欄位而推測。
```

只引用 `turn-*` 是**盲評的前提**：若 `structured_only` 的輸出引用 `claim-001`，評審看 `source_ids`
就知道 arm。這是輕量輸出格式，不使用 API Structured Outputs；格式錯誤會被記錄，但 P0 的主要裁決仍是
Task 邊界品質，不把 subagent 的 JSON adherence 外推為 provider 能力。

## 7. 執行順序

1. 依 [`rubric.md`](rubric.md) 完成六個案例與人工 adjudication。
2. 為每案建立 paired `raw_context`、`raw_plus_spans_context`、`hybrid_context`、`structured_context`，
   並以字串包含檢查驗證每個 `literal_text` 與 span 都是原 turn 的逐字子字串。
3. 凍結共同 instruction、案例與 rubric；記錄 experiment revision `1`。
4. 跑第 1 輪 24 trials；同一 subagent 不得看到兩個 arm。
5. 驗證輸出能否解析；保留原始輸出，不自動修 JSON。
6. **校準盲評者**：owner 先人工裁決 1 個 case 的四份輸出，與 reviewer subagent 判決比對；
   不一致以人工為準，並給 reviewer prompt 一輪修正，之後才用它裁決其餘案例。
7. 以 rubric 逐案匿名裁決（pass／fail／unknown），先記 critical，再記 0–2 品質分。
8. 跑第 2 輪：CR-01／CR-03／CR-05 的三個產品 arm 各補至 3 次。
9. 產生 `results.csv` 與 `report.md`，將平手、失敗、`unknown` 與限制一併回報。
10. 結果若要改變 ADR 0040 或最終架構，另開研究修訂／ADR；不得直接以實驗 README 當新 authority。

## 8. Trial 保存格式

每次 trial 的檔名：

```text
<case-family-id>__<arm-id>__sol__t0N.json
```

欄位與完整範例見 [`trials/README.md`](trials/README.md)。最低要求：

- experiment／case／arm／round／重複序號；
- requested model、reasoning effort、`fork_context`、agent ID 與執行時間；
- 實際傳給 subagent 的完整 prompt；
- subagent 最終原始輸出；
- parse 結果、rubric 裁決（含 `unknown`）與 reviewer notes；
- 平台不可觀測限制。

不建立 hash chain、event sourcing、資料庫或通用 trial framework。

## 9. 評分

評分 authority 是 [`rubric.md`](rubric.md)。概要：

- Critical：工具升格、責任邊界、merge／split、更正否定、零證據、來源忠實度。
- Secondary：Task statement 品質、下一問價值、未支持推測、輸入負擔。
- arm 必須先通過所有適用的 critical checks，secondary 分數才可比較。
- 每個 critical check 允許 `unknown`。聚合固定為：任一 `fail` → `false`；無 `fail` 但有 `unknown`
  → `null`（交 owner 裁決後才定案）；全部 `pass` → `true`。**`fail` 優先於 `unknown`**，
  `null` 不等於通過。
- 盲評由獨立 reviewer subagent 執行，不讀生成器 rationale，一次比較同一 case 的四份匿名輸出，
  避免不同 reviewer 尺度漂移；上線前先經 §7.6 的人工校準。
- P0 只有 6 個案例，不做顯著性、排行榜或「最佳架構」宣稱。

## 10. 預先固定的決策規則

**0. 射程限定** —— 見 §3.2。P0 的結論只涵蓋「人工整理的字面 claim table」，不涵蓋 typed Work Model。

**1. 一致性門檻** —— 任何刪除類決策需 CR-01／CR-03／CR-05 各 **3/3 同方向**；
任一案例出現 2/1 分裂即 `inconclusive`，留到正式 R1，不得在 P0 下結論。

| # | 觀察到的模式 | 決策 |
|---|---|---|
| 2 | Hybrid 反覆輸給 `raw_only` | 字面 claim table 被否證；第一版不建 literal-claim layer；typed Evidence 仍未決 |
| 3 | `raw_plus_spans` > `raw_only`，且 Hybrid ≈ `raw_plus_spans` | 價值來自檢索／顯著性；保留 span 選取候選，不建 literal-claim layer；typed Evidence 仍未決 |
| 4 | `raw_plus_spans` < `raw_only` | 重貼原句有害；production 不做 span 重貼，且 Hybrid 的任何優勢須先扣除此效果再解讀 |
| 5 | Hybrid 穩定優於 `raw_plus_spans` | 字面結構化尚未被否證，只取得「值得進一步驗證」資格；下一步測 extraction fidelity |
| 6 | `structured_only` 出現否定／更正／時間／責任／脈絡遺失 | 永遠不得單獨取代原始對話（`diagnostic_only`） |
| 7 | critical 與實質品質持平 | P0 依 YAGNI 選 `raw_only`，不建 literal-claim layer；typed Evidence 仍未決。這是 §1.1 已登記的預期結果 |

**8. 不以架構完整性為理由保留。** 也不得因為人工理想表示表現好，就把它當成產品能力。

## 11. 已知限制

- 受測 subagent 不是 OpenRouter shipping model，結果不能取代正式 provider 複驗。
- 平台隱藏 system／developer instructions、專案 instructions（含本 repo 的 `AGENTS.md` 職務分析詞彙）、
  私有 reasoning 與完整工具軌跡不可擷取；視為 across-arm 常數，會抬高絕對表現。**不做自述 probe**，
  理由見 §4.3。
- **殘留解盲通道**：reviewer 為判 `C6_SOURCE_FIDELITY` 必須看 transcript 與 adjudication，
  而被餵 spans 的 arm 會不成比例地引用那幾個 turn ID，arm 身分因此部分洩漏。無法根治。
- 6 個 constructed cases 只適合發現明顯錯誤，不代表真實員工分布；也不是 C-03 的正式八案 screening。
- Structured／Hybrid 使用人工製作的字面表示，只量測表示效用上限，不量測 extraction reliability。
- 只有重複組（CR-01／CR-03／CR-05）跑到 3 次；CR-02／CR-04／CR-06 為 n=1，
  差異只能標 `flagged_n1` 送正式 R1，不得據以下決策（rubric §5）。
  **代價：責任邊界（CR-04／C2）在 P0 沒有可下決策的證據強度**，這是把重複配額給 merge/split 的直接後果。
- `structured_only` 在保留顧問逐字提問之後，與 `raw_only` 的差距收窄為**句間連接詞與非主張片段**；
  它只回答「句間膠是否承重」，不能宣稱「用結構取代原文會遺失脈絡」這種大結論
  （見 [`cases/README.md`](cases/README.md)）。
- 四個 arm 的字元量不同，且 `raw_plus_spans` 與 `hybrid` 的 spans 是**重複計入**的字元，
  結果要同時報告可見輸入字元數，**不得把字元較少直接解讀為效率較高**，也不把較長 Context
  自動解讀為架構較好。

## 12. 本階段交付邊界

本文件核准後才建立正式 case JSON 並派 subagent。P0 完成時應新增：

- `cases/CR-01...CR-06.json`
- `trials/*.json`
- `results.csv`
- `report.md`

在此之前不接 Web、production code、provider adapter、資料庫、完整 Context Engine 或 Evidence Engine。
