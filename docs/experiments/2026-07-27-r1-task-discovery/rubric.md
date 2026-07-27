# R1 Task Discovery Rubric

- experiment revision：**1**
- 凍結時間：2026-07-27
- authority：
  [R1 實驗設計](../../specs/2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md)
  §11。本檔是那一節的可執行版本，衝突以設計為準。

> **凍結**（ADR 0041 決定 15）：`預期`／`Critical failure`／本檔的維度定義與門檻，
> 在迭代期間**不得為了配合模型輸出而改寫**。要改須升 `case_revision` 與 experiment revision 並記錄理由。

## 1. Task 定義

員工**目前**、**穩定**、**屬於本人責任**、且具有**可辨識目的或結果**的工作。
工具、技術、知識、技能、單一步驟、一次性事件、過去工作、假設工作與他人責任
**不得因為被提及就升格成 Task**。資訊不足時可以不建立 Task。

## 2. 兩層裁決

| 層 | 誰執行 | 產出 |
|---|---|---|
| Deterministic checks | `verify_output.py` | 形狀／引用／逐字對應的硬失敗 |
| Semantic dimensions | blind model grader ＋ owner | 每維度 `pass`／`fail`／`unknown` |

**deterministic 失敗優先**：任一 deterministic error 成立，該 trial 先記 invalid，
不進語意比較（避免拿壞掉的輸出去談 Task 品質）。

規則程式**不裁決「這是不是 Task」**。關鍵字規則不得用來判定 Task 成立與否。

## 3. 維度分層（B1 的防線）

### 3.1 共同維度 —— 所有 arm 一律適用

| 維度 | 問的是 |
|---|---|
| `meaningful_outcome` | Task 有可辨識的目的或結果，不是純手段 |
| `employee_responsibility` | 是本人責任，不是他人或共同工作被誤收 |
| `assignability_checkability` | 邊界清楚到可以指派、可以檢查完成 |
| `stability_formal_low_frequency` | 穩定或正式低頻責任，與一次性事件正確區分 |
| `merge_split_boundary` | 同一工作不因多故事重複建立；不同結果的工作不被錯誤合併 |
| `past_other_one_off_exclusion` | 過去工作、他人責任、一次性支援未進現況 |
| `correction_authority` | 後說的更正壓過舊說法，被撤回的內容不復活 |
| `source_grounding` | 每個判斷都能回到來源，且沒有輸入外的推測 |
| `uncertainty_honesty` | 證據不足時誠實說不足，不硬湊 |
| `next_question_value` | 下一問單一、自然、能降低當前最關鍵的不確定性 |

### 3.2 full-harness-only 維度 —— 只評 A2–A6

| 維度 | 問的是 |
|---|---|
| `state_change_targets_existing_task` | 是否正確把 state change 指向既有 Task ID |

**A1 看不到 Current Work Model，結構上不可能滿足這層。** 因此：

1. full-only 維度**只在 full arm 上評分**，minimal arm 記 `not_applicable`，**不是 `fail`**；
2. full-only 結果**與共同維度分開報告**；
3. **full-only 維度不得用來宣稱 A6 的 Task 邊界優於 A1**
   （設計 §4.2、§11.2；ADR 0040 決定 9 的「持平選較簡單者」靠這條保護）。

`proposed_tasks` 代表「依本 case 所有來源，目前應成立的完整 Task 語意集合」，不是本輪 delta。
A1 因此能在 TI-R1-08 上以「保留上線前測試、不保留本人正式部署」通過 `correction_authority`，
不需要知道 `task-existing-001` 這個 ID。

## 4. 三值判定與聚合

- 每個 `(case × arm class)` 的 applicable 維度回 `pass`／`fail`／`unknown`。
- 聚合固定為：任一 `fail` → `false`；無 `fail` 但有 `unknown` → `null`；全部 `pass` → `true`。
- **`fail` 優先於 `unknown`；`null` 不等於通過**，需 owner 裁決後才定案。
- `unknown` 不得靜默丟掉，必須進報告。

## 5. Locked regression anchors

| Case | 必須成立的行為 |
|---|---|
| `TI-R1-02` | 能形成一個有 outcome 的升級 Task（正向案例） |
| `TI-R1-07` | 能拒絕一次性代班成為穩定 Task |

外加全案通用的 critical 條件：correction 不得復活；不得有 tool-as-task、step-as-task、
past／other／one-off leakage；不得因 schema 必填而硬造 Task；不得產生沒有 source 的 Task。

任一 anchor 失敗，該 arm **不進 shortlist**。這是 development screening 結論，
不是統計證明。兩個 anchor 的全部輸出必須由 owner 人工覆核，不能只靠 model grader。

## 6. 盲評程序

- grader 一次讀同一 case 的六份匿名輸出，**只看 `CanonicalTaskReviewView`**；
- 不看 arm、模型、schema、latency、cost，也不讀 `decision_basis`；
- **正序與反序各評一次**；兩次判決不一致的維度一律記 `unknown`
  （n=1 之下隨機排序無法抵銷位置效應，設計 §8.2）；
- 上線前先做校準：owner 先人工裁決一個 disposable packet，與 grader 比對，
  給 grader prompt 一輪修正後才凍結；
- 不得改用 generator 同款模型當 grader 來省成本（grader 呼叫本來就只有個位數）。

## 7. 「實質改善」的效力上限

八案只能形成方向性訊號：

| 標記 | 條件 | 效力 |
|---|---|---|
| `flagged_n1` | 只有 1 個 case 改善 | 不能拔擢也不能淘汰，送 20–30 案 |
| `screening_signal_n2` | ≥2 個 case 的共同維度改善、無新 critical regression、grader 與 owner 不衝突、deterministic validity 不退步 | 只能決定「值得進 20–30 案」 |

第一批八案沒有衍生案例，`case_family_id == case_id`，所以這裡的「2」**只是兩個單次 observation，
不是聚類控制、重複驗證或統計獨立性證據**。真正的重複驗證在 shortlist 的 pass³。

**兩者都不能宣稱某架構勝出。** 持平時一律照 ADR 0040 決定 9 選較簡單、呼叫較少的版本。

## 8. 不作為通行證的項目

中間結果較好看、錯誤較容易定位、schema 欄位較完整、rationale 較長、grader 較喜歡文風、
可觀測性較多 —— 都可以記錄，但**不得單獨替較複雜的架構取得通行證**。
