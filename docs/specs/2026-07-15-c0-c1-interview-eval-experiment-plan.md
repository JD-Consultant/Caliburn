# C0 → C1 訪談 LLM 實驗計畫——先證明 Evidence-first，再決定架構

- 日期：2026-07-15
- 狀態：**eval foundation 已實作／真實 C0 baseline 與 C1 尚未開始／不構成架構 ADR**
- 上游研究：[`2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md`](2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md)
- 比較對象：C0（現行 v3 可重播基線）與 C1（Thin Evidence-first）
- 本文件不評定：C1A Sufficiency Agenda、C2 Workflow Graph、C2P planner、多 agent、fine-tuning
- 適用團隊：一人開發團隊；需要少量外部職務分析／HR domain review 時會明確標示，不假裝開發者就是 SME

2026-07-15 實作進度：已建立 `apps/api/evals/interview_v4/` 的 case/gold/run 契約與 JSON Schema、完整 case loader、只讀去識別 exporter、deterministic graders、isolated C0 runner、現行 scribe/harvest adapter、provisional legacy case 與測試。尚無真實 promotion-ready dataset，因此不得把 foundation 完成解讀為 C1 已通過。

---

## 1. 決策先行

下一步不是直接重構 production runtime，而是完成一個能回答下列問題的配對實驗：

> 在相同逐字稿、相同初始 JD、相同 reference snapshot 與相同人工評分規則下，C1 將 `Evidence` 與 `Inference` 分離後，是否比 C0 更忠實、更完整、更容易更正，而且沒有以不可接受的成本、延遲或漏寫換取表面安全？

實驗只允許三種結論：

| 結論 | 意義 | 後續 |
|---|---|---|
| `C1_PROMOTE` | C1 通過硬性安全 gate，並在主要 failure class 有穩定的 paired-case 淨改善。 | 才能設計 C1A adaptive interview 實驗。 |
| `C1_REVISE` | C1 安全，但抽取、qualifier、projection 或成本仍有明確可修問題。 | 保留 C0 production；修 C1 後重跑同一 protocol。 |
| `C1_REJECT` | C1 破壞來源、人工內容、狀態正確性，或沒有可歸因收益。 | 不進 C1A；回到較小的 C0 修補假設。 |

不得使用「看起來比較專業」「模型比較新」「平均總分稍高」直接作 `C1_PROMOTE`。

---

## 2. 這個實驗能證明與不能證明什麼

### 2.1 能回答

- 同一段員工原話能否被完整拆成原子 evidence。
- 否定、更正、時間、典型性、ownership、frequency、importance 是否被正確保存。
- inference 是否有合格 evidence 支持。
- JD projection 是否增加逐字稿或 reference 沒有的事實。
- 首回合豐富敘事、多意圖回答與跨回合更正是否會遺失。
- 人工拒絕後，沒有新 evidence 時是否會重提。
- 相同輸入重跑是否 idempotent。
- C1 對 C0 的品質、成本、延遲與錯誤型態差異。

### 2.2 不能回答

固定 transcript replay 無法證明：

- C1A 問出的下一題是否比 C0 好。
- 不同問題是否能引出更多真實工作內容。
- 受訪者是否感覺被理解、疲勞、受冒犯或願意繼續。
- 何時轉題、停止、探索 emergent topic 最好。
- Workflow Graph 或 planner 是否值得。

原因不是工具不足，而是因果結構不同：顧問換一個問題，後續員工回答就不再是同一條 transcript。這些能力必須在 C1 通過後，以 branching scenario、受控 simulated user 與真人 pilot 另測；不可把 fixed replay 分數包裝成 adaptive interview 成效。

---

## 3. 2026 方法依據

本計畫延續上游研究第 14、22、23 節，採用下列方法，不重新發明一套任意分數：

1. OpenAI 2026 eval 指引：task-specific dataset、從歷史／production failures 持續擴充、先用可判別的 pass/fail 或 pairwise、以人工標註校準 model grader；測試資產不可只存在即將退場的舊 Evals platform。[上游 O6](2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md#agentstatecontext工具與評估一手)
2. Anthropic 2026 agent eval：區分 trial、trajectory、outcome、grader 與 harness；capability eval 和 regression eval 目的不同；隨機系統要重複 trial。[上游 A5](2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md#agentstatecontext工具與評估一手)
3. Anthropic Interviewer：固定研究問題和 adaptive follow-up 並存，分析回到完整 transcript 並保留代表性 quote；分類器需人工驗證，資訊不足不強制分類。[上游 A8/A9](2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md#agentstatecontext工具與評估一手)
4. O*NET：task 是否存在、relevance、frequency、importance 分開；來源和不確定性需保留。[上游 S4/S5/S6](2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md#職務技能標準一手)
5. 最新訪談研究：追問要評 gap、non-leading、單一焦點與實際資訊價值，不只評 topical relevance；但這屬 C1A，不混入本輪 C1 replay 結論。[上游 R6/R7/R8/R10](2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md#領域方法與可追溯研究)

---

## 4. 現有 repo 資產稽核

### 4.1 可直接保留的資產

| 現有資產 | 位置 | 本實驗用途 | 限制 |
|---|---|---|---|
| append-only transcript | `interview_turns`、`InterviewRepo.list_turns` | 匯出 replay input 與 quote source。 | 需去識別；目前沒有 case manifest。 |
| review events | `interview_review_events` | 找人工 accept/reject 與重提事故。 | 無拒絕理由時不能猜 rejection 原因。 |
| LLM call audit | `interview_llm_calls` | model、role、duration、tool/guard metadata。 | 現行 production 呼叫常沒有 token；也未保存完整 prompt、raw response、state before/after。 |
| quote verifier | `app/interview/verify.py` | exact/normalized quote validity 硬 gate。 | 驗證「說過」而非「推論正確」。 |
| `_pending.src` | 現行文件 | C0 projection provenance。 | 只能看已投影內容，不能保存尚未投影的 evidence。 |
| Source Score walker | `evals/source_score.py` | 找出有／無來源的現有 projection。 | 不可再用單一比例取代 unsupported-claim 檢查。 |
| HTTP provider | `evals/provider_turn.py` | 可作 C0 smoke runner 參考。 | module-level `_STARTED`、外部 profile 與 DB 狀態使案例隔離不夠明確。 |
| 既有 unit tests | `apps/api/tests/test_interview_*.py` | regression safety net。 | 多數驗程式契約，不等於產品品質 eval。 |
| OpenTelemetry spans | `app/observability.py` | latency/token/verify/review 觀測基礎。 | 尚不足以重建完整 trial trajectory。 |

### 4.2 可遷移但不得直接當 gold 的資產

#### `JD-golden-001`

目前只有一個 golden case，且檔案明示 reference 是「agent 依來源自審」、維護者不是 JD 領域專家。它可以作 schema migration 樣本與 provisional capability case，不能單獨擔任語意 release gate。

另有一個必須人工裁決的語意衝突：逐字稿同時說「回歸要百分之百跑完」以及「趕的時候手動的可以抽樣」，但 reference 直接寫成 100% 完成。可能解釋包括：

- 100% 指測試範圍，手動抽樣仍被正式計入完成；
- 員工前後矛盾；
- 100% 是一般原則，趕工是例外；
- reference 過度選擇了較漂亮的版本。

沒有補問或 SME adjudication 前，不得把任一解釋標成唯一真相。正確 gold 應保存 contradiction／exception gap，而非用 reference 成品掩蓋不確定性。

#### `interview_sim.py` 與 promptfoo simulated users

可保留為 smoke／resilience test，不能作 JD faithfulness gate，因為目前 persona 被要求「自訂一致的事實」：

- 每次 trial 的 latent facts 不固定。
- runner 不知道完整真相，因此無法計算漏抽或新增事實。
- simulated user 和 judge 都可能共享模型偏誤。
- 目前主要分數是 slot keyword、coverage、verify pass 等 proxy，不代表職務理解正確。

後續 C1A 若要使用 simulated user，必須先提供固定 `fact_world` 與回答政策；模型只能決定如何表達，不能臨場發明 ground truth。

### 4.3 必須先修正的現有 eval 漏洞

| 問題 | 現況 | 為何危險 | 本計畫處理 |
|---|---|---|---|
| 問號 assertion 實作錯誤 | `say.count("?") + say.count("?")` 重複計 ASCII 問號，且不計全形 `？`。 | 一個 ASCII 問號會被算成 2；全形會算 0。 | 不沿用；改判定 conversational action 與 `forward_question_count`。 |
| 每回合硬性必問 | prompt 和 assertion 都要求恰好一題。 | 合理確認、拒答處理與收尾可能不該再問。 | C1 不評 policy；C1A 依狀態判 `ask/confirm/transition/close` 是否合理。 |
| Source Score ≥ 0.8 | 容許最多 20% 寫入沒有合格來源。 | 對專業 JD，少量重大 hallucination 不能被平均數掩蓋。 | `unsupported_projection_count == 0` 為硬 gate；比例只作診斷。 |
| 空輸出 Source Score = 1.0 | `total == 0` 回傳 1.0。 | 什麼都不寫可假裝完全忠實。 | 同時評 precision 與 required-evidence recall；空輸出不得自動通過 capability case。 |
| 單一 reference answer | rubric 偏向逐字命中特定成品。 | 合理同義輸出可能被錯殺；reference 自身也可能過度推論。 | 改為 claim-level required／acceptable／forbidden labels。 |
| agent 自審取代 SME | 現有 README 把 agent 自審稱為 SME gate。 | 模型可能驗證自己的假設，且無 domain authority。 | 明確改稱 provisional label；只有 domain-reviewed item 才能作 semantic release gate。 |
| 固定 profile state | provider 以 module `_STARTED` 保持狀態。 | 重跑／中斷後可能讀到舊 session 或舊文件。 | 每個 trial 建獨立 fixture/profile/session，完成後保存 immutable artifact。 |
| 缺 raw trajectory | DB 有 metadata，但未完整保存 prompt、raw response、state delta。 | 無法定位是 context、模型、parser、verifier 還是 reducer 失敗。 | run artifact 必須補齊第 9 節欄位。 |

這些問題不代表現有測試無價值；它們表示「程式 regression」與「架構品質證明」必須分開。

---

## 5. 實驗單位與資料分層

### 5.1 最小單位是完整 case，不是單一 turn

一個 `case` 包含：

```text
初始文件／profile/reference snapshot
+ 完整員工與顧問 turns
+ review events（若有）
+ claim-level gold labels
+ failure tags
+ 適用的 graders
```

不可把同一場 session 的 turns 隨機拆到 dev 與 held-out。相鄰 turns、同一工作事件與同一員工用語高度相關，這會造成 leakage。

### 5.2 三種 case 來源

| 類型 | 用途 | 能否作 promotion gate | 要求 |
|---|---|---|---|
| `real_incident` | 重現已發生失敗，價值最高。 | 是，完成去識別與標註後。 | 保存原始失敗類型，不只選容易修的案例。 |
| `real_success` | 防止新架構破壞現有成功行為。 | 是。 | 需人工確認成功不是只看文件外觀。 |
| `constructed_edge` | 精準測否定、時間、注入、重試、idempotency。 | 只作 deterministic gate／能力診斷。 | 不可用大量合成案例掩蓋真人退步。 |

自由生成 simulated user 不屬於上述 fixed replay promotion set；它留到 C1A branching evaluation。

### 5.3 第一批資料量

建議第一個可執行批次為 **24 個完整 case**，這是初始操作值，不是假裝具有統計代表性的樣本量：

- 12 `development`：可看標籤、修 schema／prompt／grader。
- 6 `validation`：選門檻與檢查 overfitting，不用來反覆改 prompt。
- 6 `held_out`：最後一次盲跑；結果揭露後即視為已使用，下一輪需補新 held-out。

若暫時拿不到 24 個真實案例：

- 最少先做 12 個真實／高可信案例加必要 edge cases。
- 標示 `pilot_only=true`，只允許 `C1_REVISE` 或繼續研究，不宣稱產品級勝出。
- 不用複製、切 turn 或大量模型生成來湊數。

### 5.4 failure class 配額

第一批至少涵蓋下列類型；一個 case 可有多標籤：

| 代碼 | Failure class | 必須觀察 |
|---|---|---|
| `E-MISS` | 明示 evidence 遺漏 | 首回合豐富敘事、多意圖。 |
| `E-FAB` | 捏造 evidence／quote | 逐字來源、turn 歸屬。 |
| `E-QUAL` | qualifier 錯誤 | frequency、importance、ownership、authority、scope。 |
| `E-TIME` | 時間錯誤 | 過去／現在／未來／假設。 |
| `E-POLARITY` | 否定／不確定被當肯定 | 「不是我」「偶爾幫忙」「可能」。 |
| `E-CORRECT` | 更正未取代舊理解 | 每週改為每月、主管核准。 |
| `I-OVER` | inference 超過 evidence | 工具名推成能力、任務推成態度。 |
| `I-CONFLATE` | K/S/A／task/output 混淆 | taxonomy 與 observable behavior。 |
| `P-UNSUPPORTED` | JD 投影新增事實 | KPI、數字、責任、標準、系統。 |
| `P-OMIT` | 高價值 JD 項漏掉 | 核心 task/output/standard/exception。 |
| `P-REPEAT` | 拒絕後無新證據重提 | review feedback semantics。 |
| `S-NONDET` | reducer 非冪等／狀態被覆蓋 | retry、duplicate、out-of-order。 |
| `R-PROJECT` | reference 污染個人事實 | O*NET/iCAP 常見任務被自動加入。 |

問題政策 `Q-*` 類另留 C1A，不在 C0/C1 fixed replay promotion score 混算。

---

## 6. 去識別、同意與資料邊界

### 6.1 真實資料不得直接提交原文到 Git

repo 可保存：

- 已取得用途授權、完成去識別的 case。
- constructed edge cases。
- schema、標籤、hash、runner、grader 與 aggregate report。

repo 不應保存未處理的：

- 員工姓名、Email、電話、帳號。
- 客戶／病患／候選人可識別資料。
- 商業機密、憑證、內部 URL、真實財務數字。
- 可由部門＋罕見事件重新識別個人的組合資訊。

原始資料若必須留存，應進權限受控的外部資料層；manifest 只記 opaque source id 與 de-identification version。

### 6.2 去識別不能破壞待測語意

替換值必須型別一致且穩定，例如：

```text
「王經理」       → 「[主管_A]」
「客戶甲公司」   → 「[客戶_A]」
「SAP S/4HANA」  → 若工具身分影響 skill 判定則保留；否則改「[ERP_A]」
「每月 3,200 萬」→ 若數字影響 responsibility/standard，改成同量級虛構值並標 transformed
```

每個 transformation 記錄是否影響 gold；無法安全轉換就不納入資料集。

---

## 7. Case manifest v0.1

建議未來存放於 `apps/api/evals/interview_v4/cases/<split>/<case_id>/case.json`。本輪先定契約，不建立 runner。

```json
{
  "schema_version": "interview_eval_case.v0.1",
  "case_id": "INT-E-QUAL-001",
  "split": "development",
  "source_type": "real_incident",
  "locale": "zh-TW",
  "role_family": "finance_operations",
  "risk_tags": ["E-QUAL", "P-UNSUPPORTED"],
  "privacy": {
    "status": "deidentified",
    "version": "deid.v1",
    "approved_use": "architecture_eval",
    "raw_source_in_repo": false
  },
  "initial": {
    "document_fixture": "initial_document.json",
    "session_state_fixture": "initial_state.json",
    "reference_snapshot": "reference_snapshot.json",
    "review_events_fixture": "review_events.json"
  },
  "transcript": "transcript.jsonl",
  "gold": "gold.json",
  "annotation": {
    "status": "domain_reviewed",
    "annotator_roles": ["product_maintainer", "job_analysis_reviewer"],
    "guideline_version": "claim-label.v0.1",
    "adjudication_notes": "adjudication.md"
  },
  "applicable_graders": [
    "quote_validity",
    "evidence_claims",
    "inference_grounding",
    "projection_faithfulness",
    "state_invariants"
  ]
}
```

### 7.1 Transcript 格式

```json
{"seq":1,"role":"consultant","text":"……"}
{"seq":2,"role":"employee","text":"……"}
```

規則：

- `seq` 使用原 session 順序，不能把 employee turns 重新編成連續 1、2、3 後失去原始關係。
- quote 的 source 只能指 employee turn。
- 原始時間戳如非測試必要，匯出時移除。
- case 不把 prompt injection 字串清洗掉；若它就是待測內容，保留並標 `security_case`。

### 7.2 Initial fixtures

必須固定四種初始狀態，否則 C0/C1 不是同一題：

1. `initial_document.json`：accepted、pending、rejected 可見狀態。
2. `initial_state.json`：session/episode/ledger 的起點；C1 新欄位須空白初始化。
3. `reference_snapshot.json`：當時可查到的 iCAP/O*NET/ESCO 候選；不連 live corpus。
4. `review_events.json`：案例開始前已發生的接受／拒絕。

reference 必須 snapshot，避免外部資料版本改變造成同一 case 前後結果不同。

---

## 8. Gold annotation v0.1

### 8.1 不使用「唯一標準 JD」作主要 gold

每個 case 改標 claim-level truth set：

```json
{
  "required_evidence": [],
  "optional_evidence": [],
  "forbidden_evidence": [],
  "acceptable_inferences": [],
  "inferences_requiring_confirmation": [],
  "forbidden_inferences": [],
  "required_projection_claims": [],
  "acceptable_projection_variants": [],
  "forbidden_projection_claims": [],
  "unresolved_gaps": [],
  "state_expectations": []
}
```

這允許多種專業文案，同時對事實邊界保持嚴格。

### 8.2 Evidence label

```json
{
  "label_id": "gold_ev_07",
  "kind": "frequency",
  "claim": "通常每月執行一次盤點",
  "subject": "employee",
  "polarity": "affirmed",
  "time_scope": "current",
  "typicality": "usual",
  "qualifies_label_id": "gold_ev_02",
  "source": {
    "turn_seq": 8,
    "quote": "其實是一個月才一次"
  },
  "requirement": "required",
  "notes": "更正 turn 2 的每週一次；舊 evidence 應 superseded，不刪歷史"
}
```

標註規則：

- 只標員工明示或可直接定位的主張。
- 一筆只標一個可獨立判定事實；action 與 frequency 分開。
- quote 必須是精確子字串；正規化只供 verifier，不改 gold 原文。
- 「我很細心」標 `explicit_self_assessment`，不標 attitude confirmed。
- 「我用 Excel」可標 tool/action，不自動標資料分析 skill level。
- 否定內容也要標；不能因為不投影 JD 就丟棄。
- 例子、一次性事件、一般職責要由 `typicality` 分開。

### 8.3 Inference label

Inference 不要求逐字命中，需定義語意範圍：

```json
{
  "label_id": "gold_inf_03",
  "kind": "indicator_candidate",
  "semantic_claim": "發現帳務不一致時先回查明細，再依權限交由財務調整",
  "supported_by": ["gold_ev_03", "gold_ev_04", "gold_ev_05"],
  "allowed_status": ["candidate", "needs_confirmation"],
  "must_not_add": ["員工擁有最終核准權", "保證零錯誤"],
  "alternatives": [
    "先查核明細，無法排除時轉交財務處理"
  ]
}
```

### 8.4 Projection label

Projection 分三類：

- `required`：若系統目標是生成該 JD 元素，缺少即影響 recall。
- `acceptable`：可有可無或有多種保守寫法。
- `forbidden`：任何出現都算 unsupported，即使句子很專業。

不得要求 C1 把每筆 evidence 都寫進 JD。過去工作、否定、低典型性、敏感內容可能只應留 evidence 或 gap。

### 8.5 Unknown 與 disputed

標註者不能確定時必須使用：

```text
unknown       原文不足，沒有唯一答案
disputed      原文內有未解矛盾
not_applicable 該 grader 不適用
needs_sme     需要領域判定，開發者不可自判
```

`unknown` 不計模型錯，但模型若把 unknown 寫成確定事實則算錯。

---

## 9. Run artifact v0.1

每次 C0/C1 trial 都輸出 immutable artifact；不能只留 aggregate score。

```json
{
  "schema_version": "interview_eval_run.v0.1",
  "run_id": "run_...",
  "case_id": "INT-E-QUAL-001",
  "case_content_hash": "sha256:...",
  "candidate": "C0",
  "trial_index": 1,
  "git_sha": "...",
  "dirty_worktree": false,
  "started_at": "...",
  "runner_version": "...",
  "model_calls": [
    {
      "role": "select",
      "provider": "...",
      "requested_model": "...",
      "resolved_model": "...",
      "temperature": 0,
      "prompt_hash": "sha256:...",
      "tool_schema_hash": "sha256:...",
      "input_tokens": 0,
      "output_tokens": 0,
      "latency_ms": 0,
      "raw_response_artifact": "...",
      "parsed_output_artifact": "..."
    }
  ],
  "trajectory": [
    {
      "turn_seq": 2,
      "state_before": "...",
      "candidate_output": "...",
      "verifier_result": "...",
      "state_delta": "...",
      "projection_delta": "..."
    }
  ],
  "final": {
    "state": "final_state.json",
    "document": "final_document.json",
    "grader_results": "grader_results.json"
  }
}
```

### 9.1 必須固定或記錄的變因

- transcript、initial fixtures、reference snapshot。
- prompt/template 版本與 hash。
- tool/schema 版本與 hash。
- model requested name 與 provider 實際 resolved name。
- temperature、seed（供應商若支援）、max tokens、reasoning 設定。
- retries、timeouts、fallback model。
- code commit 與 dirty state。

若 C0/C1 使用不同模型，結果只能回答「整套組合誰好」，不能歸因 Evidence architecture。第一輪應使用相同模型與相同可比 generation settings；只有 schema 所需輸入不同。

### 9.2 Trial 次數

- deterministic reducer/verifier：每 case 一次並另跑 property/unit tests。
- LLM extraction/projection：development 可先 1 次快速迭代；正式 validation/held-out 每 case 至少 3 trials。
- promotion 判定以 case-level 多 trial 結果報告穩定性；不得只挑最佳一次。
- timeout/fallback 必須算該 candidate 的結果，不能靜默刪除失敗 trial。

`3` 是一人團隊的初始成本折衷，不是統計學充分性保證；若 trial variance 高，增加 trial 或先修不穩定來源。

---

## 10. C0 與 C1 runner 邊界

### 10.1 C0

C0 是現行行為的可重播 adapter：

```text
employee turn
→ current scribe/harvest/verify/apply
→ current document `_pending`
```

允許在不改語意的前提修正 runner 隔離、輸出 artifact 與明顯 eval bug；不得為了提高 C0 分數臨時改 prompt 或 production logic。若要測「C0 修補版」，另命名 `C0R`，不能覆蓋原 baseline。

### 10.2 C1

C1 最小垂直切片：

```text
employee turn
→ Evidence v0.2 extractor
→ deterministic evidence verifier/reducer
→ episode-close 或 finish 時產生 inference/job-item candidates
→ evidence-backed projection
→ 既有 verify
→ isolated final document
```

C1 不得：

- 使用 Interview Agenda 改變訪談問題。
- 建 Workflow Graph。
- 從 reference snapshot 補 employee facts。
- 因為 gold label 可見而注入 case-specific prompt。
- 直接改 production DB；第一輪使用 offline/isolated fixture state。

### 10.3 同一 transcript 的處理方式

為避免 C0 consultant 問句影響 C1：

- extraction/projection replay 直接使用 case 已固定的 employee turns。
- 顧問 turns 只作語境，不由 C0/C1 重新生成。
- C0 和 C1 都按原始順序處理 employee turn。
- episode boundary 若原始 session 有 tool trace就沿用；沒有則由 case fixture 明示，不讓 C1 模型自行選 boundary。

因此本輪比較的是分析層，不是問題政策。

---

## 11. Grader 分工

### 11.1 確定性 grader

| Grader | 判定 | Gate |
|---|---|---|
| `schema_validity` | 輸出與 state 是否符合版本 schema。 | 100%；硬 gate。 |
| `quote_validity` | quote 是否為指定 employee turn 精確／允許正規化子字串。 | 100%；硬 gate。 |
| `source_subject` | 不可引用 consultant/system/tool text 當 employee evidence。 | 100%；硬 gate。 |
| `projection_grounding` | 每個投影 claim 是否可回到 accepted evidence 或允許 reference relation。 | unsupported count = 0；硬 gate。 |
| `human_content_protection` | accepted/human-touched 內容是否被無聲覆寫。 | 0 次；硬 gate。 |
| `state_idempotency` | 同 turn 重跑是否產生重複 evidence/projection。 | 0 duplicate semantic item；硬 gate。 |
| `correction_history` | 更正是否 append + supersede，而非刪歷史／last-write-without-link。 | 100%；硬 gate。 |
| `rejected_reproposal` | 無新 evidence 時是否重提 rejected fingerprint。 | 0 次；硬 gate。 |
| `reference_leakage` | reference-only claim 是否被標 employee fact。 | 0 次；硬 gate。 |

這些是安全／資料完整性不變量，不用平均分抵銷。

### 11.2 Claim-level semantic grader

先用人工 gold 做集合比對，再由人工處理語意同義與邊界：

- evidence precision／recall 分開報。
- qualifier accuracy 分 subject、polarity、time、typicality、frequency、importance。
- inference supported／overreach／needs-confirmation routing。
- projection required-claim recall。
- projection forbidden-claim count。
- K/S/A confusion matrix。

不把所有項目壓成一個「Answer Score」。總分會掩蓋少量重大錯誤，也讓團隊不知道該修哪一層。

### 11.3 人工 rubric

每個 final JD 由 reviewer 在不知道 candidate 名稱的情況下判：

| 維度 | 問題 | 回答格式 |
|---|---|---|
| faithfulness | 是否代表受訪者說的工作，而非標準職類或模型常識？ | pass/fail + offending claim ids。 |
| material coverage | 是否漏掉會實質改變 JD 的核心 task/output/standard/exception？ | pass/fail/unknown + missing ids。 |
| responsibility boundary | ownership、authority、handoff 是否正確？ | pass/fail/unknown。 |
| indicator observability | 指標是否包含可觀察行為及有證據的標準／結果？ | pass/fail/not_applicable。 |
| K/S/A separation | 工具、知識、技能、能力、態度是否混淆？ | pass/fail + item ids。 |
| usability | 作為 `_pending` 給人審，是否清楚、非重複、可採用？ | pairwise preference + reason。 |

候選名稱、模型名、prompt 版本不得出現在 reviewer 畫面。

### 11.4 LLM judge

只可用於：

- 對大量 trial 預標可能的 semantic mismatch。
- pairwise 比較文案清晰度。
- 找人工需要審的可疑案例。

不得單獨決定：

- employee 是否真的有某項能力／態度。
- contested label 的正解。
- `C1_PROMOTE`。

judge artifact 必須保留 provider/model、prompt/rubric hash、輸入、理由與分數；以人工 calibration set 報 false positive／false negative，不只報相關係數。

### 11.5 Claim matching 與分母規則

Evidence／projection 不可用 substring 或 embedding top-1 直接算對。每個 trial 採下列順序：

1. 先以 deterministic 條件建立可能配對：source turn、quote/span、subject、polarity、time_scope 不得衝突。
2. `kind` 相同者優先；允許的跨 kind 對照必須寫在 case 的 `acceptable_variants`，不可由 runner 臨場放寬。
3. 對語意 claim 作人工或已校準 grader 判定：`equivalent | narrower_but_valid | broader_unsupported | different | unknown`。
4. 使用一對一 matching；一筆 system output 不可同時滿足兩筆不同 required gold，一筆 gold 也不可被重複計 recall。
5. `narrower_but_valid` 可計 precision matched，但若漏掉 gold 的 material qualifier，不計 required recall。
6. `broader_unsupported` 即使包含正確片段，仍計 unsupported claim；不得因部分命中而通過。

指標定義：

```text
evidence_precision = matched_valid_output_evidence / all_output_evidence
evidence_recall    = matched_required_gold_evidence / all_required_gold_evidence
projection_precision = supported_projection_claims / all_projection_claims
projection_recall    = matched_required_projection_claims / all_required_projection_claims
```

空分母規則：

- case 沒有 required evidence 時，`evidence_recall = not_applicable`，不填 1.0。
- system 沒輸出 evidence 時，若 case 有 required evidence，precision 記 `not_applicable`、recall 記 0；不得以 precision 滿分通過。
- system 沒有 projection 時，若 case 有 required projection，recall 記 0；若 case 本來就不該投影，另以 `expected_no_projection=true` 的 pass/fail grader 判。
- aggregate 時排除 `not_applicable` 的分母，但必須同時報適用 case 數，不可只報百分比。

### 11.6 Trial 聚合規則

每個 validation／held-out case 的三次 trial 先各自評分，再聚合：

- hard gate：三次都要通過；任一 trial 出現 critical／unsupported projection，case hard-gate fail。
- major failure：報 `0/3`、`1/3`、`2/3`、`3/3` 發生率，不用平均文字分數沖淡。
- semantic metric：同時報三個原值、中位數與最差值；promotion 不只看最佳或平均。
- case winner：至少兩次 trial 在 blind rubric 勝出且沒有 hard-gate regression，才標 C1 win；一勝一負一平或 reviewer 無法判斷皆標 tie/unclear。
- candidate aggregate：以 case 為單位計 win/tie/loss，不能把 evidence 數量很多的長案例權重放大。

模型供應商若沒有完全 deterministic seed，這些規則用來顯示不穩定性，不宣稱三次就估計了完整機率分布。

---

## 12. 標註流程與一人團隊現實

### 12.1 角色分工

| 標註內容 | 開發者可定案？ | 需要 domain review？ |
|---|---|---|
| quote span、turn、speaker、否定詞、時間詞 | 是。 | 抽樣即可。 |
| schema、state transition、idempotency | 是。 | 否。 |
| 原文是否明示 action/tool/output | 多數可；模糊時 unknown。 | 邊界案例需要。 |
| task 是否為核心、importance、責任界線 | 不應只憑開發者。 | 是，或保留 unknown。 |
| skill/knowledge/ability/attitude 判定 | 不應單獨定案。 | 是。 |
| 最終 JD 專業品質 | 可作產品觀點，不是 SME gold。 | promotion set 至少需 domain review。 |

### 12.2 Annotation status

每個 label 必須有狀態：

```text
draft              初標，不進 gate
maintainer_checked 客觀來源／schema 已核對，可進 deterministic gate
domain_reviewed    領域 reviewer 已核對，可進 semantic gate
adjudicated        歧義已記錄並裁決
disputed           尚無共識，不以單一答案扣分
```

不要再把 agent 自審稱為 SME review。

### 12.3 無法取得 SME 時

可以繼續做：

- quote、安全、狀態、correction、reference leakage 等 deterministic C1 實驗。
- 建立 provisional semantic labels。
- 找出 C0/C1 差異與待審 claim。

但只能下 `C1_REVISE`／「工程層通過」結論，不能宣稱顧問品質已被專業驗證。可把 domain reviewer 的工作壓縮成審閱最具決策價值的 6–10 個案例，不要求長期加入團隊。

---

## 13. Failure severity

| 等級 | 定義 | 例子 | Promotion 影響 |
|---|---|---|---|
| `critical` | 可能誤導人事責任或破壞不可逆資料／權限。 | 虛構核准權、覆寫人工內容、跨員工資料混入。 | 任一未解 critical 即不得 promote。 |
| `major` | 實質扭曲職務或漏掉核心責任。 | 過去工作寫成現職、否定當肯定、核心 output 遺漏。 | C1 不得比 C0 增加；需 paired-case 審查。 |
| `minor` | 不改變主要事實但降低可用性。 | 同義重複、文案不順、次要分類邊界。 | 可權衡，但需列入 backlog。 |
| `diagnostic` | 非產品錯誤，只顯示成本／穩定性。 | token 上升、某模型 retry 多。 | 由成本邊界判定。 |

severity 由「影響」決定，不由 grader 類型或模型信心決定。

---

## 14. Promotion gate

### 14.1 硬 gate

C1 要進入產品化／C1A 研究，validation 與 held-out 必須：

1. 所有可檢查的 quote/source/schema/human-content/state 不變量 100% 通過。
2. `unsupported_projection_count == 0`。
3. `critical_failure_count == 0`。
4. 無新 evidence 時 `rejected_reproposal_count == 0`。
5. 不把 reference-only claim 標為 employee fact。
6. runner 完整保存 trial，沒有把 timeout、parse failure 或 fallback 靜默排除。

硬 gate 失敗時，不看平均總分，直接 `C1_REVISE` 或 `C1_REJECT`。

### 14.2 價值 gate

硬 gate 通過後，才比較 paired cases：

- C1 對目標 failure classes 的 major errors 淨減少。
- evidence required-claim recall 不低於 C0；若 C0 無 evidence layer，使用可從 C0 projection／records 還原的可比集合並標 limitation。
- final JD material coverage 不退步。
- reviewer 在盲測 pairwise 中不偏好 C0，且能指出 C1 的實質收益，不只是格式偏好。
- correction、ownership、temporality 至少有一個先前主要事故類別被穩定修正。

本輪樣本小，不用虛假的 p-value 宣稱普遍勝出。報告每個 case 的 paired delta、勝／平／負、failure severity 與 3-trial variance；若結果只由一兩個案例拉動，結論應是 `C1_REVISE`。

### 14.3 成本 gate

先量 baseline，再定可接受比例；第一版不得預先捏造「最多增加 20%」之類門檻。至少報：

- 每 employee turn 的 model calls。
- input/output/cached tokens。
- p50/p95 latency。
- retry／parse failure／fallback rate。
- 每完成一個可審 JD item 的 token 與 latency。
- storage growth／case。

若 C1 品質改善只來自多倍模型呼叫，要列出「同模型同預算」與「最佳品質」兩個比較，不混為單一架構收益。

### 14.4 最終決策演算法

```text
if dataset_status != promotion_ready:
    decision = C1_REVISE
elif any hard gate fails:
    decision = C1_REVISE or C1_REJECT
elif C1 introduces any new unresolved critical failure:
    decision = C1_REJECT
elif held_out has no paired-case net improvement on target failure classes:
    decision = C1_REJECT
elif improvement is concentrated in <= 1 case or trial variance changes the winner:
    decision = C1_REVISE
elif material coverage regresses or reviewer reasons show factual loss:
    decision = C1_REVISE
elif cost/latency exceeds the measured product boundary:
    decision = C1_REVISE
else:
    decision = C1_PROMOTE
```

`C1_REJECT` 與 `C1_REVISE` 的界線：若失敗可定位到 schema、prompt、reducer 或 runner 的有限問題，選 REVISE；若 Evidence layer 在相同資料／成本下沒有穩定價值，或結構本身造成新的主要錯誤，選 REJECT。decision memo 必須列出判斷依據，不由 runner 自動猜「是否可修」。

---

## 15. 實驗執行順序

### E0：修正 eval 定義，不改 runtime

產出：

- 本文件核准版。
- failure taxonomy 與 annotation guideline。
- 移除「agent 自審 = SME」的 release 語意。
- 現有 eval 資產清單與 deprecated gate 清單。

完成條件：每個分數能說清楚「評什麼、不評什麼、誰能定案」。

### E1：建立 case exporter 與 schema

產出：

```text
apps/api/evals/interview_v4/
├─ README.md
├─ schemas/
│  ├─ case.schema.json
│  ├─ gold.schema.json
│  └─ run.schema.json
├─ cases/
│  ├─ development/
│  ├─ validation/
│  └─ held_out/
├─ graders/
├─ runners/
└─ reports/
```

完成條件：一個去識別 session 可匯出、schema validate、再還原為 isolated fixture；不接 production write path。

### E2：建立第一批 cases 與標註

順序：

1. 先選 3–5 個真實重大事故。
2. 加 3–5 個現有成功案例。
3. 補 qualifier/correction/reference/idempotency edge cases。
4. 先標客觀 evidence，再標 inference，最後才標 projection。
5. 對 disputed／needs_sme 不強制答案。
6. 由 reviewer 盲審高價值案例。

完成條件：development 至少能覆蓋主要 failure classes；validation/held-out 在 runner 完成前封存。

### E3：C0 baseline

產出：

- 每 case × trial 的 immutable run artifacts。
- C0 failure matrix。
- 既有 `JD-golden-001` 的重新標註結果。
- latency/token 缺失欄位清單。

完成條件：能從報告點回 transcript → model call → verifier → document delta，而不是只看到總分。

### E4：C1 offline vertical slice

最小實作順序：

1. Evidence v0.2 schema。
2. Extractor adapter。
3. exact quote／subject／qualifier verifier。
4. deterministic append/supersede/dispute reducer。
5. 最小 task/output/indicator inference。
6. evidence-backed projection adapter。
7. 同一 C0 fixture runner。

不在此階段建立 Agenda、Graph、planner 或新 Web UX。

### E5：Blind paired evaluation

- 鎖 prompt/schema/model config。
- 跑 validation 三 trials。
- 修正只能回 development；修改後 validation 視需要重跑並記錄使用次數。
- 最後解封 held-out，一次完成 C0/C1。
- 人工 reviewer 只看匿名 A/B artifact。

### E6：Decision record

產出不是最終架構 ADR，而是 experiment decision memo：

```text
candidate: C1
decision: PROMOTE | REVISE | REJECT
hard_gate_results
paired_case_results
critical/major failures
cost/latency delta
known limitations
next experiment authorization
```

只有 `C1_PROMOTE` 才授權撰寫 C1A experiment spec；仍不能自動授權 C2/C2P。

---

## 16. 報告格式

### 16.1 Case-level paired table

| Case | C0 critical/major/minor | C1 critical/major/minor | Required recall delta | Forbidden claims | Cost delta | Winner | Reviewer reason |
|---|---:|---:|---:|---:|---:|---|---|

### 16.2 Failure matrix

| Failure class | C0 affected cases | C1 affected cases | Fixed | Regressed | Unclear | 下一動作 |
|---|---:|---:|---:|---:|---:|---|

### 16.3 不允許的報告方式

- 只報一個總分。
- 只展示最漂亮的成功案例。
- 排除 timeout／空輸出後再算平均。
- 以 verify pass rate 代表 semantic correctness。
- 以長輸出、欄位填滿率或 promptfoo pass 代表專業顧問效果。
- 不揭露 model、prompt、schema 或 reference 版本。

---

## 17. 實作時不得自行猜的決策表

| 問題 | 本文件答案 |
|---|---|
| 現在是否修改 production runtime？ | 否；先 exporter/schema/C0 baseline，C1 走 isolated fixture。 |
| 是否直接沿用 `JD-golden-001`？ | 否；遷移成 provisional case，重新 claim-level 標註與 adjudicate。 |
| 是否沿用 Source Score 0.8 gate？ | 否；保留診斷，projection unsupported count 必須為 0。 |
| 空輸出是否算安全通過？ | 只能通過「無 hallucination」，不能通過 capability／coverage。 |
| 是否要求每回合恰好一題？ | C1 replay 不評；C1A 依 action/state 評，不用全域硬規則。 |
| 是否用 simulated user 補足 24 例？ | 否；可補 edge/smoke，不可取代真人 promotion cases。 |
| 是否 random split turns？ | 否；以完整 session/case 分組。 |
| 是否每個 label 都要兩位專家？ | 否；客觀與程式標註由維護者，語意 promotion subset 需 domain review。 |
| 沒有 SME 可否繼續？ | 可完成工程／安全實驗，但不得宣稱專業 JD 品質已證明。 |
| 是否現在選 Claude/OpenAI 某個最終模型？ | 否；第一輪同模型公平比較，模型 routing 在架構收益證明後。 |
| 是否建立 Workflow Graph？ | 否；C1/C1A failure evidence 通過上游 22.7 gate 才能進場。 |
| 是否先 fine-tune？ | 否；尚無穩定 taxonomy 與足量 adjudicated data。 |

---

## 18. 第一個可執行工作包

此工作包已於 2026-07-15 完成「eval foundation」，未做 C1 runtime：

1. 建立 `interview_v4/schemas` 的 case/gold/run JSON Schema。
2. 寫一個只讀 exporter，把指定 session 匯出到暫存目錄並去除直接識別欄位。
3. 將 `JD-golden-001` 複製／遷移為 provisional v0.1 case，不刪舊 eval。
4. 寫 deterministic schema、quote、source-subject grader。
5. 建立 isolated C0 runner；每 trial 使用新 fixture，不碰既有 profile。
6. 產生第一份 C0 report，列出資料與 trace 缺口。

驗收：

- 不需 OpenAI/Anthropic dashboard 才能讀取 case 與結果。
- 不需 production DB write。
- 同一 fixture 可重跑且不累積舊狀態。
- report 可逐 claim 回到 employee quote。
- 現有 v3 測試保持不變；新 eval 不把舊 promptfoo 分數假裝成新 gate。

完成此工作包後，才開始 C1 Evidence extractor/reducer PR。

目前 gate 狀態：程式與 capture foundation 已通過；promotion data gate 未通過。現有 owner-confirmed
synthetic case 已可做靜態 claim eval，但缺 historical initial fixtures。下一步不是立刻寫 C1，而是先
補 provider-level trace，從 turn zero 產生新的 replay-ready synthetic pilots，再依第 15 節 E2 擴充
3–5 個 incidents 與 3–5 個 successes、補 role-family diversity 與 domain-reviewed gold，最後執行
E3 C0 baseline。若未來納入 production data，仍須另走 consent/deidentification gate。

---

## 19. 本計畫的停止條件

以下任一情況發生，先停止 C1 實作而不是繼續堆架構：

- 找不到足夠真實 failure cases，問題定義仍主要靠想像。
- 無法把現有 session 隔離重播，C0 baseline 不可信。
- gold 中大量 claim 連人工都無法一致理解；先修訪談問題／資料定義。
- production trace 不足以定位失敗層；先補 observability。
- C1 只能靠讀取 gold/reference answer 才改善。
- C1 的主要收益來自更強模型或更多 calls，無法歸因 architecture。

停止不是失敗；它避免再次把「研究後看似完整」直接變成昂貴且不可驗證的 production 重構。

---

## 20. 本文件結論

Caliburn 已經有 transcript、review event、verify、`_pending`、LLM-call metadata、promptfoo 與模擬器等基礎，但目前的 eval 還不能證明哪個 LLM 架構最好：單一 agent 自審 golden、自由生成 simulated facts、Source Score 0.8、空輸出滿分與「每回合必問」都可能導致錯誤結論。

因此下一步的正確產出不是完整 v4，而是：

```text
可信的完整-case dataset
→ claim-level gold
→ isolated C0 replay
→ immutable trajectory artifacts
→ C1 offline vertical slice
→ blind paired decision
```

這套基礎建好後，C1 若失敗，可以知道是 Evidence schema、extractor、reducer、inference 還是 projection；C1 若成功，也能證明收益不是模型、prompt、資料洩漏或平均分造成的錯覺。

---

## 21. 直接來源

本文件的 eval 方法與限制以以下一手／可追溯來源為依據；詳細解讀與來源分級見上游研究：

- OpenAI, [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)，存取於 2026-07-15：task-specific eval、production/historical data、人工校準、pairwise/pass-fail、持續評估與舊 Evals platform 退場資訊。
- Anthropic, [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)，2026-01-09：trial、trajectory、outcome、grader、harness、capability/regression 與多次 trial。
- Anthropic, [Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)，2025-12-04：planning、adaptive interviewing、analysis、quote 與 human collaboration。
- Anthropic, [What 81,000 people want from AI](https://www.anthropic.com/features/81k-interviews) 及 [Methods Appendix](https://cdn.sanity.io/files/4zrzovbb/website/99156863ed4a812569fe00a2adfb1c93f7e5a911.pdf)，2026-03：80,508 份合格訪談、品質篩選、分類器人工 agreement、unknown/exclusion 與研究限制。
- O*NET Resource Center, [Data Collection Overview](https://www.onetcenter.org/dataCollection.html)，更新於 2026-07-14；以及 [Occupation Expert Tasks Questionnaire](https://www.onetcenter.org/dl_files/omb2024/AppendixF-OE-Tasks.pdf)：多來源工作分析及 relevance/frequency/importance 分離。
- Wuttke et al., [AI Conversational Interviewing](https://aclanthology.org/2025.latechclfl-1.17/)，ACL 2025：adaptive interview prompt、逐 turn violations、追問與人類／UX 評估。
- Huang et al., [Teaching Language Models To Gather Information Proactively](https://aclanthology.org/2025.findings-emnlp.843/)，EMNLP 2025：gap identification 與 targeted elicitation。
- Anugraha et al., [SparkMe](https://arxiv.org/abs/2602.21136)，Stanford arXiv preprint，2026-02：coverage、emergence、interview cost、agenda 與 stopping；因 preprint／simulation 限制，只作 C1A 候選方法，不作 C1 promotion 證據。

---

## 22. 2026-07-15 database session gate 更新

已完成第一輪 database inventory、保守 private export，以及 owner-confirmed test-data export。詳細
稽核見
[`real-candidate-audit-2026-07-15.md`](../../apps/api/evals/interview_v4/reports/real-candidate-audit-2026-07-15.md)，架構解讀見上游研究第 24 節。

### 22.1 實際資料狀態

- 資料庫只有 1 個 synthetic mixed candidate，未達 E2 的 incidents/successes 分層數量。
- 候選有 10 employee turns、105 accepted reviews、30 LLM calls、12 verify rejects、3 drops。
- 20 個 `select` calls 佔 178,900/201,216 ms 已記錄模型延遲；p95 38,548 ms。
- tokens 全為未記錄（NULL），不得當 0。
- privacy prescreen 有 1 個 organization cue；owner 已確認全部為測試資料，因此本 case 標
  `privacy.status=synthetic`，不再是 privacy blocker。
- initial document、turn-zero state、historical immutable reference snapshot 全部不存在。
- `TEST-SYNTHETIC-SESSION-001` 已完成 22 個 required evidence、9 個 inference labels、3 個 episode
  boundary 與 4 個 state expectation；annotation 是 `maintainer_checked`，尚非 domain-reviewed。

### 22.2 Gate 決定

```text
decision: CAPTURE_FOUNDATION_IMPLEMENTED_NEW_PILOT_REQUIRED
C0 historical replay: BLOCKED
C1 production implementation: NOT AUTHORIZED
synthetic static claim evaluation: READY
claim annotation: MAINTAINER_CHECKED_DOMAIN_REVIEW_PENDING
immutable eval-session capture foundation: IMPLEMENTED_DEFAULT_OFF
provider-level trace/failure outbox: NEXT IMPLEMENTATION PACKAGE
```

observed export-time document/state 只可作 failure audit，不可冒充 initial fixture；以目前 reference
重建歷史 snapshot 會造成 temporal leakage。下一個 consented pilot 必須在 turn 0 保存 initial
document/state、reference hash、prompt/tool schema hash，並逐 call 保存 stage、resolved model、tokens、
outcome、latency 與 parsed artifact。Migration `0009` 與 runtime 已保存 turn-zero snapshot、每回合
before/after state/document、tool results、stage outputs、trajectory hash chain 與 session-final snapshot；
歷史 audit rows 以 `legacy_unknown` 保留未知。

目前仍缺 provider resolved model、tokens、raw response、逐 attempt trace，以及 request exception 的
獨立 failure outbox，所以所有新 capture 仍回 `replay_ready=false`。只有新 case 通過 fixture hash
chain + provider trace + gold gate（production data 再加 privacy/consent gate），才執行 E3 C0。

### 22.3 下一個 synthetic pilot 的逐項驗收

不得只看「資料表有 rows」。一個新 pilot 要晉升 replay-ready，必須逐項通過：

1. start 前沒有 employee turn，且 initial document/state/reference 三份 artifact 都存在；
2. 三份 initial artifact 的 canonical hash 與 `EvalSessionStart` 完全相等；
3. 每個 employee turn 恰有 before/after state/document 與 trajectory；
4. trajectory 的四個 hashes 能對回 artifact，call ids 依真實 stage 執行順序；
5. 每個動態 knowledge/tool result 都由當回合 artifact 凍結，不在 replay 時重新查 current data；
6. 每個 model attempt 能識別 provider、requested/resolved model、prompt/tool schema、tokens、latency、
   outcome、raw/parsed output；
7. provider exception 即使回合 transaction rollback，failure trace 仍存在；
8. finish 有 final state/document、unresolved gaps 與 stable stop reason；
9. exporter 只能讀 capture artifacts 建 case，不能用 export-time current document 補缺；
10. loader、quote validation、hash-chain validation 與至少一次 isolated replay 全部通過。

任一項失敗，只能留在 development/failure-localization；不得人工把 `replay.ready` 改成 `true`。
