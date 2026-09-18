# R1 八案：建立與凍結規則

素材來源是
[R1 深入研究 §11](../../../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)
的 `TI-R1-01`–`08`。本目錄把那八段描述做成可執行 fixture，沒有新增案例、沒有改變風險意圖。

## 定位

**八案全部是 development set**，不是 holdout（ADR 0041 決定 13）：它們的輸入與期望早已公開在
上述必讀 spec 裡，寫 prompt 的人必然看過。未曝光評測集延到 20–30 案擴充階段，
規則見 ADR 0041 決定 16–17。

`TI-R1-02` 與 `TI-R1-07` 另標為 **locked regression anchors**（防退步的行為錨點），
**不得宣稱它們證明 unseen generalization**。

## 欄位

| 欄位 | 說明 |
|---|---|
| `schema_id` | 固定 `professional-consultant-r1-case.v1` |
| `case_id` | `TI-R1-01`–`08` |
| `case_revision` | 從 1 起；改動案例必須升號並記錄理由 |
| `source_type` | 一律 `constructed_edge`（ADR 0040 決定 13；owner 已裁定目前沒有真實員工訪談資料） |
| `case_family_id` | 第一批等於 `case_id`（無衍生案例）；真正生效要到 20–30 案 |
| `sources[]` | `source_id`／`source_kind`（`employee_turn`｜`consultant_turn`）／`speaker`／`text` |
| `initial_work_model` | **可選**，只有 `TI-R1-08` 有。帶了就必須宣告 full-only 維度 |
| `expected.required_behaviors` | 必須出現的行為（人工裁決用） |
| `expected.forbidden_behaviors` | critical failure（人工裁決用） |
| `expected.common_applicable_rubric_dimensions` | 所有 arm 都評的維度 |
| `expected.full_harness_only_dimensions` | 只有 A2–A6 評的維度 |

附加欄位（`primary_risk`、`locked_regression_anchor`、`full_harness_only_expectations`）
是給人讀的註記，驗證器允許但不強制。

### 維度命名

維度名以實驗設計 **§11.2** 為準（例如 `employee_responsibility`）。
設計 §4.2 的 JSON 範例用了示意性的 `responsibility_boundary`，本目錄統一正規化為 §11.2 的名稱；
白名單定義在 [`../contracts.py`](../contracts.py)。

## 為什麼只有 TI-R1-08 帶 `initial_work_model`

帶既有狀態的案例會讓 minimal arm（A1）遇到它結構上做不到的事 —— 它看不到 `task-existing-001`。
把這種案例限制在一個，可以把該效應侷限在單一 case，並用兩道防線處理：

1. `verify_output.py` 對 minimal arm 不要求 `StateChangeDiagnosticView`，
   反而**禁止**它輸出（它沒有資訊可以正確輸出）；
2. `validate_r1_cases.py` 強制「帶 `initial_work_model` 就必須宣告 `full_harness_only_dimensions`」，
   否則案例無法通過凍結驗證。

共同語意（更正是否壓過舊說法）仍照評 —— A1 光靠逐字稿就能做到。

## 凍結規則（設計 §4.3）

1. 先凍結來源、required／forbidden behaviors 與人工裁決理由；
2. 記錄 suite canonical hash；
3. **才寫 prompt**；
4. 不得因模型輸出不合預期而偷偷改 gold；
5. 真要改就升 `case_revision`、記理由，並視為新實驗；
6. 八案預期已公開，只能作 development／regression，**不得重新命名成 holdout**。

## 驗證

```bash
cd docs/experiments/2026-07-27-r1-task-discovery
python validate_r1_cases.py   # 需要 apps/api 的 uv 環境；CJK 需 PYTHONUTF8=1
```
