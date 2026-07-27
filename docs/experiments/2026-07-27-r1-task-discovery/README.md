# R1 Task Discovery 實驗資產

- 日期：2026-07-27
- 狀態：**Segment 1–2 完成；沒有執行任何 trial，沒有送出任何真實請求**
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
| [`provider_request.py`](provider_request.py) | Segment 2：provider 綁定與精確請求體（禁 fallback／單一 upstream／strict schema／停用 plugin） |
| [`routing_facts.py`](routing_facts.py) | Segment 2：從**回應**正規化 resolved route 與 cache 狀態，拿不到就 fail closed |
| [`transport.py`](transport.py) | Segment 2：一次 attempt 一次 HTTP，永不 retry；環境失敗與品質結果分開 |
| [`capture.py`](capture.py) | Segment 2：trial 目錄、redaction、Trial Manifest 與其完整性檢查 |
| `test_*.py` | 206 個離線測試（malformed-output 型別矩陣 ＋ mocked HTTP） |

### 兩個由程式保證、不靠約定的不變量

1. **raw ≠ 盲評視圖**：`decision_basis`、arm、model、schema、latency、cost 由
   `project_canonical_view()` 在投影時強制移除；`verify_grader_packet()` 是它的守門測試。
2. **anchor 必須指名來源**：每個 Task 的 `source_anchors[]` 帶 `source_id` ＋ 逐字 `quote`，
   且 quote 必須是**該筆** source 的子字串 —— 只驗「出現在某個來源」擋不住張冠李戴。

### Provider 形狀是 PROVISIONAL

`provider_request.py` 的 plugin id 清單與 `routing_facts.py` 的 router metadata 形狀，
依 OpenRouter 的 wire 結構寫成，但**尚未用真實回應核對** —— 那要等 Segment 4 的
disposable live preflight。在那之前一律 fail closed：讀不懂的形狀記 limitation、
`resolved_model` 留 null，寧可作廢一個 trial 也不猜。

既有的 `app/interview_vnext` 實作**不是本實驗的權威**：R1 是重新設計，
舊實作可能有多餘或錯誤的決定。測試 `test_r1_eval_never_imports_interview_vnext` 守住這條界線。

## 本段**沒有**做什麼

- 沒有送出任何真實 API 請求（Segment 4 才有，且需 owner 核准）；
- 沒有 context assembler、runner、grader prompt（Segment 3）；
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
