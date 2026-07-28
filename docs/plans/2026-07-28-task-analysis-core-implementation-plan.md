# Task Analysis Core 實作計畫（第一條可運作 vertical）

- 日期：2026-07-28
- 狀態：Proposed
- 目標：證明 `員工回覆 → 組 Context → 模型分析 → verifier → 更新 in-memory Work Model →
  建立可供員工決定的 Proposal → 選出下一題` 這條路走得通
- 決策依據：[ADR 0042](../adr/0042-r1-screening-stop-and-a6-first-version-default.md)、
  [Task 邊界研究 §9–§12](../specs/2026-07-28-task-boundary-merge-split-and-identity-research.md)
- **本計畫不含**：資料庫、persistence、Web／route、OPKS、公版檢索、長對話壓縮、
  provider registry、通用 agent／graph framework、付費架構實驗

## 0. 位置與隔離

新程式碼一律住 `apps/api/app/job_analysis/`（涵蓋後續 Task、OPKS 與工作分析，不叫 `task_analysis/`
以免過窄）。

依 ADR 0040 決定 3，新引擎 greenfield：**不得 import** `app/interview_vnext`、`app/interview`、
`app/job_authoring`、`evals/*`。以 AST dependency guard 測試強制，讓「不作為前提」在程式結構上可檢查，
而不只是文件宣示。

```text
app/job_analysis/
├─ domain/          Task、Proposal、Work Model、SourceRef（純 Pydantic）
├─ llm/             TaskAnalysisResult.v1 契約、portable schema、prompt
├─ application/     verifier、context assembler、transition service
└─ providers/       薄 OpenRouter adapter
```

## 1. Task 切分

一個 task 一個 commit，綠了才 commit。

### T1 — Domain contracts

`domain/`：§9.1 的 Task／SourceRef／SourceAnchor／`open_issues`／`excluded_signals`，
§10 的 Proposal（狀態、action/target、`jd_before`/`jd_after`、`staged_work_model_delta`、
`edited_jd_after`、`RevisionRequestResolution`）。純 Pydantic，immutable，無 DB、無 route。

**完成條件**：unit test 覆蓋 enum 值域、必填/可空、§10.5 的 `edited_jd_after` 四條硬規則、
lineage 不成環。
**不做**：為內部 DTO 產生 JSON Schema 與 golden。

### T2 — `TaskAnalysisResult.v1` 契約與 provider schema

`llm/`：§12.1 的輸出形狀 ＋ portable subset 的 provider-facing JSON Schema（ADR 0040 決定 24）。

**完成條件**：schema lint 通過 portable subset（object／array／基本型別、required、nullable union、
enum、`additionalProperties: false`）；schema golden test。
**不做**：operation registry、definition hash、多版本並存。

### T3 — Deterministic verifier

`application/verifier.py`：§9.5 ＋ §10.5 ＋ §12.3 的全部確定性規則。純函式，不呼叫模型。

**完成條件**：每條規則各有正向與反向 test，特別是——`quote` 必須是該員工回合的逐字子字串、
`no_match` 時 `target_task_ordinals` 必須為空、`merge` 需 ≥2 target、`withdraw` 不得帶 `task_fields`、
同一 target 被兩筆 `task_change` 指涉時**兩筆都拒**、輸出不得含 UUID 形狀字串。
**不做**：任何語意判斷（是否同一 purpose、該不該 merge）——那些歸 rubric。

排在 assembler 之前，因為它只依賴 T1／T2，而且是唯一能在沒有模型的情況下端到端測的東西。

### T4 — Context assembler

`application/context.py`：§11.1 的三個區段投影，pure、deterministic——相同輸入得到相同 packet。
ordinal 每輪重編並在 packet 中明示；保存當輪投影作為 read-set（§11.3）。

**完成條件**：相同輸入產生逐字相同 packet；ordinal↔ID mapping 正確且不進 domain；
待決 Proposal 明標「尚未成立」。
**不做**：embedding、retrieval、compaction、recent-window（長對話退化才啟用）。

### T5 — One-stage operation ＋ 薄 OpenRouter adapter

`providers/openrouter.py`：**新寫的最小 adapter**，不 import 也不整份複製舊路徑。
沿用已驗證的 wire invariants：一次 HTTP、portable structured output、固定 exact model slug 與
provider endpoint、`require_parameters: true`、**禁 fallback、禁隱藏 retry**、明確的 typed 失敗結果。

`application/operation.py`：組 packet → 呼叫 → parse → 交給 verifier 的單一顯式流程，
不是通用 agent runner。

**完成條件**：以 mock transport 覆蓋成功、schema 不符、refusal、timeout、非 200；
斷言 transport 只被呼叫一次（無隱藏 retry）；斷言送出的 body 帶固定 model／provider／
`require_parameters`。
**不做**：registry、通用 provider framework、artifact graph、fallback、bake-off。

### T6 — Pure transition／application service

`application/transition.py`：把通過 verifier 的結果轉成 Work Model 變更與 Proposal——
§12.2 的 mapping、§9.6 的 identity gate（`topology_affected_existing_ids ∩ current_jd_task_ids`）、
§9.5 的原子性三出口、§10 的 Proposal 建立與 stale／disposition。

state 保存在記憶體（一個 in-memory Work Model ＋ Current JD），**不碰 DB**。

**完成條件**：unit test 覆蓋——JD 外 withdraw 立即 retire、JD 內 withdraw 走 Proposal、
merge 成員全不在 JD 時立即套用、任一成員在 JD 時建立 Proposal、`active` Task 零有效支持時
三個出口的行為、同一輪混合立即套用與 Proposal。
**不做**：交易、CAS、reload、authority snapshot 的持久化保護（留給第二份 plan）。

### T7 — Scripted vertical smoke

少量案例走完整條路徑（scripted fake provider，不打真 API）。至少涵蓋：

1. 工具不成 Task（`TI-R1-01` 語意）；
2. 含工具的工作成立（`TI-R1-02` 語意）；
3. 一段話多個工作訊號；
4. 員工更正導致既有 Task 撤回（`TI-R1-08` 語意）；
5. 短答必須連回 `question_turn_id` 才可解讀。

**完成條件**：五個案例端到端綠，且輸出可讀（人可以看懂它產生了什麼 Task 與下一題）。
**不做**：eval、grader、pass³、付費 live、品質裁決。

> smoke 通過**不代表**模型品質通過。依 ADR 0042 決定 3，R1 exit gate 已暫停阻擋效力但判準未被否決；
> 任何文件不得把 smoke 綠燈寫成 Task Discovery 已通過。

## 2. 驗收

- `cd apps/api && uv run pytest tests/test_job_analysis_*.py -q` 全綠；
- dependency guard 測試證明 `app/job_analysis` 未 import 上述四個舊路徑；
- 完整 API suite 維持 green-before == green-after；
- 全程 no-network（T5 用 mock transport，T7 用 scripted provider）。

## 3. 停線條件

出現下列任一項就停下來、不要硬做：

- §9–§12 的凍結形狀在實作時被發現不可實作 → 回研究稿改，不在程式裡自行變形；
- 需要新增欄位才寫得下去 → 先指出它避免的具體使用者失敗（ADR 0042 決定 7）；
- 需要 import 舊路徑才做得到 → 停線，那代表 greenfield 邊界或設計有問題。

## 4. 之後

第二份很短的 persistence plan：目前狀態資料表 → 原子寫入 → authority snapshot stale 保護 →
關閉後 reload。再之後才是最小 local Web。
