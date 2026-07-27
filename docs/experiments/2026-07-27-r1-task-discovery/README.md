# R1 Task Discovery 實驗資產

- 日期：2026-07-27
- 狀態：**Segment 1 完成（含第二位審查者 corrective 修訂）；沒有執行任何 trial**
- experiment revision：**1**（案例內容）／verifier revision：**2**（契約與門檻）
- suite canonical hash：`6c8863863a233830a9216a3ebae46389c91082f097b337c25404400bc93694f7`
  —— 由 `FROZEN_SUITE_HASH` 常數與測試斷言鎖住，改案例會直接紅燈
- 不使用：`OPENROUTER_API_KEY`、任何 provider、production route、Web、資料庫

> **設計 authority 不在本目錄**，在
> [R1 Task Discovery 實驗設計](../../specs/2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md)。
> 本目錄只是那份設計的可執行資產；兩者衝突以設計為準。
> 實作分段見 [實作計畫](../../plans/2026-07-27-r1-task-discovery-implementation-plan.md)。

## 本段交付了什麼

| 檔案 | 責任 |
|---|---|
| [`cases/`](cases/) | 八個凍結案例 `TI-R1-01`–`08`、建立與凍結規則、[人工裁決理由](cases/adjudication.md) |
| [`rubric.md`](rubric.md) | 裁決標準：共同／full-only 維度分層、三值聚合、anchors、效力上限 |
| [`contracts.py`](contracts.py) | case 與兩種輸出視圖的最小契約、維度白名單、canonical hash、`project_canonical_view()` |
| [`validate_r1_cases.py`](validate_r1_cases.py) | 案例凍結完整性 ＋ suite hash |
| [`verify_output.py`](verify_output.py) | 模型輸出的 deterministic checks（不需網路的部分） |
| `test_*.py` | 144 個離線測試（含 malformed-output 型別矩陣） |

### 兩個由程式保證、不靠約定的不變量

1. **raw ≠ 盲評視圖**：`decision_basis`、arm、model、schema、latency、cost 由
   `project_canonical_view()` 在投影時強制移除；`verify_grader_packet()` 是它的守門測試。
2. **anchor 必須指名來源**：每個 Task 的 `source_anchors[]` 帶 `source_id` ＋ 逐字 `quote`，
   且 quote 必須是**該筆** source 的子字串 —— 只驗「出現在某個來源」擋不住張冠李戴。

## 本段**沒有**做什麼

- 沒有 provider transport、沒有送出任何 API 請求（Segment 2／4）；
- 沒有 context assembler、runner、grader prompt（Segment 2／3）；
- 沒有 `trials/`、`results.csv`、`report.md` —— **沒有結果就不會有這些檔案**；
- deterministic checks 中需要網路的三條（provider route／binding、無隱藏 retry、無 cache replay）
  刻意未實作，程式內已標明歸屬 Segment 2。

## 執行

```bash
# 測試（用 apps/api 的 uv 環境）
cd apps/api && uv run pytest ../../docs/experiments/2026-07-27-r1-task-discovery -q

# 驗證案例並印出 suite hash
cd docs/experiments/2026-07-27-r1-task-discovery && python validate_r1_cases.py
```

CJK 內容在 Windows 上需 `PYTHONUTF8=1`。

## 定位限制

- 八案是 `constructed_edge`，**全部已在必讀 spec 中曝光**，只能淘汰明顯錯誤設計，
  不得宣稱架構勝出，也不是 unseen generalization 證據（ADR 0041 決定 13）。
- `TI-R1-02`／`TI-R1-07` 是 locked regression anchors，不是 holdout。
- 「2 個 case 改善」＝ `screening_signal_n2`，是兩個單次 observation，
  **沒有統計或聚類效力**；真正的重複驗證在 shortlist 的 pass³。
- 期望值已凍結：不得為配合模型輸出改寫（ADR 0041 決定 15）。
