# R1 Task Discovery 實驗資產

- 日期：2026-07-27
- 狀態：**Segment 1–3 完成；scripted 骨架已跑通，零真模型 trial、零真實請求**
- experiment revision：**1**（案例內容）／verifier revision：**2**（契約與門檻）
- suite canonical hash：`6c8863863a233830a9216a3ebae46389c91082f097b337c25404400bc93694f7`
  —— 由 `FROZEN_SUITE_HASH` 常數與測試斷言鎖住，改案例會直接紅燈
- 不使用：`OPENROUTER_API_KEY`、任何 provider、production route、Web、資料庫

> **設計 authority 不在本目錄**，在
> [R1 Task Discovery 實驗設計](../../specs/2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md)。
> 本目錄只是那份設計的可執行資產；兩者衝突以設計為準。
> 實作分段見 [實作計畫](../../plans/2026-07-27-r1-task-discovery-implementation-plan.md)。
> Python harness 與 tests 位於
> [`apps/api/evals/professional_consultant_r1/`](../../../apps/api/evals/professional_consultant_r1/)；
> 本目錄只保存凍結案例、rubric 與之後的 trial 結果。

## 本段交付了什麼

| 檔案 | 責任 |
|---|---|
| [`cases/`](cases/) | 八個凍結案例 `TI-R1-01`–`08`、建立與凍結規則、[人工裁決理由](cases/adjudication.md) |
| [`rubric.md`](rubric.md) | 裁決標準：共同／full-only 維度分層、三值聚合、anchors、效力上限 |
| `apps/api/evals/professional_consultant_r1/contracts.py` | case 與兩種輸出視圖的最小契約、維度白名單、canonical hash、`project_canonical_view()` |
| `apps/api/evals/professional_consultant_r1/validate_r1_cases.py` | 案例凍結完整性 ＋ suite hash |
| `apps/api/evals/professional_consultant_r1/verify_output.py` | 模型輸出的 deterministic checks（不需網路的部分） |
| `apps/api/evals/professional_consultant_r1/provider_request.py` | Segment 2：provider 綁定與精確請求體（禁 fallback／單一 upstream／strict schema／停用 plugin） |
| `apps/api/evals/professional_consultant_r1/routing_facts.py` | Segment 2：從**回應**正規化 resolved route 與 cache 狀態，拿不到就 fail closed |
| `apps/api/evals/professional_consultant_r1/transport.py` | Segment 2：一次 attempt 一次 HTTP，永不 retry；環境失敗與品質結果分開 |
| `apps/api/evals/professional_consultant_r1/capture.py` | Segment 2：trial 目錄、redaction、Trial Manifest 與其完整性檢查 |
| `apps/api/evals/professional_consultant_r1/matrix.py` | Segment 3：固定六 arm、48 observations 與最多 80 次 generator calls |
| `apps/api/evals/professional_consultant_r1/assembler.py` | Segment 3：minimal／full Context、one／two-stage prompt、light／heavy portable schema 與 local schema verifier |
| `apps/api/evals/professional_consultant_r1/runner.py` | Segment 3：注入式 model port；Stage 1 無效即終止，不 repair／retry |
| `apps/api/evals/professional_consultant_r1/blind_grader.py` | Segment 3：公開 packet builder 先以 `gradable_views()` 擋掉 deterministic fail，再建立匿名正反序評審 packet 與 disagreement→unknown |
| `apps/api/evals/professional_consultant_r1/batch.py`、`report.py` | Segment 3：scripted 批次骨架與不得宣稱品質的報表 |
| `apps/api/evals/professional_consultant_r1/test_*.py` | 217 個離線測試；Segment 3 只新增 11 項結論保護測試 |

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
舊實作可能有多餘或錯誤的決定。測試 `test_r1_eval_and_production_dependencies_are_one_way`
掃描原始碼，雙向擋住 eval→`app.*`（含 `interview_vnext`）與 `app.*`→eval。

## 本段**沒有**做什麼

- 沒有送出任何真實 API 請求（Segment 4 才有，且需 owner 核准）；
- 沒有 `trials/`、`results.csv`、`report.md` —— **沒有結果就不會有這些檔案**；
- 沒有把任何實驗欄位、schema、runner 或 grader 當成 production 契約；
- Segment 2 的 route／binding／單次 HTTP／cache 檢查目前只有 mocked 證據，真實 wire 形狀仍待
  Segment 4 preflight。

## 執行

```bash
# 測試（用 apps/api 的 uv 環境）
cd apps/api && uv run pytest evals/professional_consultant_r1 -q

# 驗證案例並印出 suite hash
cd apps/api && uv run python -m evals.professional_consultant_r1.validate_r1_cases
```

CJK 內容在 Windows 上需 `PYTHONUTF8=1`。

## 定位限制

- 八案是 `constructed_edge`，**全部已在必讀 spec 中曝光**，只能淘汰明顯錯誤設計，
  不得宣稱架構勝出，也不是 unseen generalization 證據（ADR 0041 決定 13）。
- `TI-R1-02`／`TI-R1-07` 是 locked regression anchors，不是 holdout。
- 「2 個 case 改善」＝ `screening_signal_n2`，是兩個單次 observation，
  **沒有統計或聚類效力**；真正的重複驗證在 shortlist 的 pass³。
- 期望值已凍結：不得為配合模型輸出改寫（ADR 0041 決定 15）。
