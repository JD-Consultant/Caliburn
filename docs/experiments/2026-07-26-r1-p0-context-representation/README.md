# R1-P0 Context Representation Subagent Screening

- 日期：2026-07-26
- 狀態：**Designed — 待 owner 審閱後執行**
- 性質：R1 前置、免外部 API key 的架構快篩
- 不使用：`OPENROUTER_API_KEY`、`OPENAI_API_KEY`、production route、Web、資料庫
- 上游 authority：
  - [ADR 0040](../../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)
  - [R1 Task Discovery 深入研究](../../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)
  - [2026-07-26 紅隊修訂](../../specs/2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md)

## 1. 要回答的問題

目前架構把原始對話轉成 Evidence／Work Model，再由 Context 組裝器提供給後續模型。但這仍是假說：

1. 強模型直接閱讀原始對話，是否已足以正確辨識 Task？
2. 結構化表示是否會遺失否定、更正、時間、責任邊界與故事脈絡？
3. 結構化表示加上相關原文的 Hybrid，是否真的比 Raw-only 有實質改善？
4. 若沒有改善，Evidence／Work Model 是否應從第一版 Task Discovery 移除或延後？

本實驗只回答**Context 表示對 Task 分析的相對影響**，不選 OpenRouter shipping model，也不驗證
provider structured output、routing、成本或 latency。

## 2. 為什麼先做 P0

ADR 0040 的正式 R1 六 arm 會同時比較 model、schema、單／雙階段與整體 harness。它可以判斷 full harness
是否承重，卻不能單獨歸因 Evidence 表示的價值。

若連理想化的 Structured／Hybrid Context 都無法優於 Raw-only，就不應先建 Evidence Engine 或完整
Context Engine。反之，即使理想 Hybrid 有效，也只能證明「這個表示值得繼續研究」，尚未證明模型能可靠
產生它。

## 3. 受測 arms

三個 arm 使用相同案例、受測模型、共同指令、輸出格式與 rubric，只更換 `context_payload`。

| Arm | 模型看到的 Context | 目的 |
|---|---|---|
| `raw_only` | 完整案例 transcript，逐字保留 | 最簡單 baseline；測強模型能否自行理解 |
| `structured_only` | 人工依同一 transcript 製作的理想結構化表示；不附 transcript | 診斷結構化壓縮的資訊損失，不預設為產品候選 |
| `hybrid` | 同一結構化表示 + 每項相關逐字 source spans + 最新員工回合 | 測雙表示是否改善邊界又保留脈絡 |

### 3.1 為什麼 Structured Context 先人工製作

P0 要隔離「表示方式是否有用」。若先讓另一個模型抽取 Evidence，失敗可能來自抽取器，也可能來自表示本身，
無法歸因。因此 P0 使用依 rubric 製作、人工檢查的理想結構化表示，測其**效用上限**。

只有 Hybrid 在 P0 顯示實質改善，才另做後續 extraction fidelity 實驗，驗證模型能否從 raw transcript
可靠產生相同表示。兩個問題不得混在一次實驗中。

## 4. Subagent 模型策略

### 4.1 快速篩選

- requested model：`gpt-5.6-luna`
- reasoning effort：`medium`
- 每個 case × arm 一個新的 subagent
- `fork_context=false`
- 共 6 cases × 3 arms = **18 trials**

### 4.2 強模型確認

快速篩選後只保留 Raw-only 與表現最好的結構化候選，以 `gpt-5.6-sol` 對 3–6 個 critical cases
各跑一次。若快篩沒有任何結構化候選達到 §10 的保留條件，仍抽 3 個 critical cases 比較 Raw-only
與 Hybrid，避免把便宜模型能力不足誤判成架構失敗。

這一階段最多 12 trials；預期通常為 6 trials。

### 4.3 Subagent 邊界

Subagent 在這裡就是**原本要由 API 呼叫的受測 LLM**，不是文獻研究員。每個 subagent：

- 只收到 §6 的共同指令、單一 case 的指定 Context，以及輸出要求；
- 不繼承本 thread、repo 文檔、其他 arm 結果或人工裁決；
- 被明確要求不讀 repo、不呼叫工具、不使用外部知識；
- 不被要求產生或揭露 chain-of-thought。

平台目前能固定 requested subagent model 與 reasoning effort，但不是 OpenRouter 的原始 completion API。
平台隱藏 system instructions 與工具實際可用性不是完整可觀測量，因此結果只可作**相對架構快篩**。

## 5. 案例

P0 固定六個 constructed capability cases；每案只測一個主要風險，避免案例數膨脹：

| Case | 主要風險 |
|---|---|
| `CR-01-tools-not-tasks` | Java／Python／HTML 等工具或技能被升格成 Task |
| `CR-02-one-story-many-work` | 一個故事包含多個具有不同產出的工作 |
| `CR-03-many-stories-one-task` | 多個故事只是同一穩定工作的不同實例 |
| `CR-04-responsibility-boundary` | 他人責任、偶爾協助與本人穩定責任混淆 |
| `CR-05-correction-and-negation` | 後續更正、否定與時間範圍被舊說法覆蓋 |
| `CR-06-insufficient-evidence` | 資訊不足時模型被迫製造 Task |

案例格式與建立規則見 [`cases/README.md`](cases/README.md)。正式 transcript 與三種 context payload
必須在第一個 trial 前一次完成並固定。

## 6. 共同受測指令

以下文字是所有 arm 的共同 instruction；實際送出的單一完整 request 仍逐 trial 原樣保存在 `trials/`：

```text
你是受測的職務分析模型。你只能根據 INPUT_CONTEXT 判斷，不得使用外部知識、repo、工具或其他對話。

目標是辨識員工目前、穩定、屬於本人責任，且具有可辨識目的或結果的工作任務。工具、技術、知識、
技能、單一步驟、一次性事件、過去工作、假設工作與他人責任不得直接升格成 Task。資訊不足時可以不建立 Task。

只輸出一個 JSON object：
{
  "tasks": [
    {
      "statement": "動詞開頭的工作敘述",
      "source_ids": ["可直接支持此 Task 的輸入來源 ID"]
    }
  ],
  "excluded_mentions": [
    {
      "source_id": "來源 ID",
      "reason": "tool_or_skill|step|past_work|hypothetical|other_person|one_off|insufficient"
    }
  ],
  "uncertainties": ["目前無法安全判斷的事項"],
  "next_question": "最能降低目前關鍵不確定性的單一問題；若不需要則為 null"
}

不要輸出 JSON 以外的文字。不得為填滿欄位而推測。
```

這是輕量輸出格式，不使用 API Structured Outputs。格式錯誤會被記錄，但 P0 的主要裁決仍是 Task
邊界品質，不把 Codex subagent 的 JSON adherence 外推為 provider 能力。

## 7. 執行順序

1. 依 [`rubric.md`](rubric.md) 完成六個案例與人工 adjudication。
2. 為每案建立 paired `raw_context`、`structured_context`、`hybrid_context`。
3. 凍結共同 instruction、案例與 rubric；記錄 experiment revision `1`。
4. 以匿名 arm 順序跑 18 個 Luna trials；同一 subagent 不得看到兩個 arm。
5. 驗證輸出能否解析；保留原始輸出，不自動修 JSON。
6. 以 rubric 逐案裁決，先記 deterministic blockers，再記 0–2 品質分。
7. 依 §10 選出強模型確認組，跑 Sol trials。
8. 產生 `results.csv` 與 `report.md`，將平手、失敗與限制一併回報。
9. 結果若要改變 ADR 0040 或最終架構，另開研究修訂／ADR；不得直接以實驗 README 當新 authority。

## 8. Trial 保存格式

每次 trial 的檔名：

```text
<case-id>__<arm-id>__<model-short-name>__t01.json
```

欄位與完整範例見 [`trials/README.md`](trials/README.md)。最低要求：

- experiment／case／arm／phase；
- requested model、reasoning effort、`fork_context`、agent ID 與執行時間；
- 實際傳給 subagent 的完整 prompt；
- subagent 最終原始輸出；
- parse 結果、rubric 裁決與 reviewer notes；
- 平台不可觀測限制。

不建立 hash chain、event sourcing、資料庫或通用 trial framework。

## 9. 評分

評分 authority 是 [`rubric.md`](rubric.md)。概要：

- Critical：工具升格、責任邊界、merge／split、更正否定、零證據、來源忠實度。
- Secondary：Task statement 品質、下一問價值、未支持推測、輸入負擔。
- arm 必須先通過所有適用的 critical checks，secondary 分數才可比較。
- P0 只有 6 個案例，不做顯著性、排行榜或「最佳架構」宣稱。

## 10. 預先固定的決策規則

1. **Raw-only 持平時選 Raw-only**：若 Hybrid 沒有多通過任何 critical case，或只提升可讀性／
   可診斷性，不建 Evidence／Work Model。
2. **Structured-only 只作診斷**：只要出現否定、更正、actor、time 或 qualifier 遺失，就不得作為
   唯一產品 Context。
3. **Hybrid 保留條件**：相對 Raw-only 至少多通過一個預先定義的 critical case，且沒有新增
   critical regression；之後仍只取得「值得進一步驗證」資格。
4. **便宜模型失敗不直接刪架構**：Hybrid 未達標時仍在三個 critical cases 以強 subagent 複驗。
5. **強模型仍持平或更差**：第一版 Task Discovery 採 Raw-only，Evidence／Work Model 延後；
   不以架構完整性為理由保留。
6. **強模型確認 Hybrid 改善**：下一個實驗才測 structured representation 的自動抽取忠實度；
   未通過前不得把人工理想 Evidence 當成產品能力。

## 11. 已知限制

- Codex subagent 不是 OpenRouter shipping model，結果不能取代正式 provider 複驗。
- 平台隱藏 system instructions、私有 reasoning 與完整工具軌跡不可擷取。
- 6 個 constructed cases 只適合發現明顯錯誤，不代表真實員工分布。
- Structured／Hybrid 使用人工理想表示，只量測表示效用上限，不量測 extraction reliability。
- 每配置一次 trial 無法證明穩定性；P0 不跑 pass³。
- Raw、Structured 與 Hybrid 的字元量不同，結果要同時報告可見輸入字元數，不把較長 Context
  自動解讀為架構較好。

## 12. 本階段交付邊界

本文件核准後才建立正式 case JSON 並派 subagent。P0 完成時應新增：

- `cases/CR-01...CR-06.json`
- `trials/*.json`
- `results.csv`
- `report.md`

在此之前不接 Web、production code、provider adapter、資料庫、完整 Context Engine 或 Evidence Engine。
