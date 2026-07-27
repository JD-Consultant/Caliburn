# R1 Task Discovery 實驗資產

- 日期：2026-07-27
- 狀態：**Segment 1–5 完成；R1a 三 arm 快篩批次完整，語意裁決待 owner 確認**
- experiment revision：**1**（案例內容）／verifier revision：**2**（契約與門檻）
- suite canonical hash：`6c8863863a233830a9216a3ebae46389c91082f097b337c25404400bc93694f7`
  —— 由 `FROZEN_SUITE_HASH` 常數與測試斷言鎖住，改案例會直接紅燈
- 正式八案仍不接 production route、Web 或資料庫。Segment 4 disposable preflight 與
  Segment 5 R1a 使用 owner 開發環境的 `OPENROUTER_API_KEY`，key 未寫入 artifact 或 Git。

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
| `apps/api/evals/professional_consultant_r1/live_preflight.py` | Segment 4：一次性 catalog／route／structured output／grader live plumbing |
| `apps/api/evals/professional_consultant_r1/live_batch.py` | Segment 5：A1／A6／A2 正式批次、grader calibration、預算停線與 owner review queue |
| `apps/api/evals/professional_consultant_r1/test_*.py` | 離線測試；只保護會污染實驗結論的契約 |

### 兩個由程式保證、不靠約定的不變量

1. **raw ≠ 盲評視圖**：`decision_basis`、arm、model、schema、latency、cost 由
   `project_canonical_view()` 在投影時強制移除；`verify_grader_packet()` 是它的守門測試。
2. **anchor 必須指名來源**：每個 Task 的 `source_anchors[]` 帶 `source_id` ＋ 逐字 `quote`，
   且 quote 必須是**該筆** source 的子字串 —— 只驗「出現在某個來源」擋不住張冠李戴。

### Provider 形狀已由 disposable live preflight 核對

`provider_request.py` 的 plugin id、metadata／cache headers 與 `routing_facts.py` 的 router
metadata 形狀已由 Segment 4 真實回應核對。真實 wire 顯示 `endpoints.total` 可大於 1，
即使 exact routing 後 `available[]` 只有一個 selected endpoint；歸因因此以
`available[]`、`selected`、resolved provider／model、strategy 與 attempt 聯合證明，
不使用 `total == 1` 這個錯誤假設。讀不懂的形狀仍一律 fail closed。

既有的 `app/interview_vnext` 實作**不是本實驗的權威**：R1 是重新設計，
舊實作可能有多餘或錯誤的決定。測試 `test_r1_eval_and_production_dependencies_are_one_way`
掃描原始碼，雙向擋住 eval→`app.*`（含 `interview_vnext`）與 `app.*`→eval。

## 本實驗**沒有**做什麼

- 沒有把任何實驗欄位、schema、runner 或 grader 當成 production 契約；
- 沒有執行 A3／A4／A5，所以不回答 heavy schema 或 economical model；
- 沒有接 Web／DB，也沒有把 R1a 當成 shipping architecture 已證明；
- Segment 4 只驗證 plumbing；Segment 5 才形成 development screening 證據。

## Segment 4 live preflight 證據

- run：`preflight-20260727T113646Z`；A1／A3／A4 三條代表路徑完成。
- 5 次 generator calls ＋ 2 次 grader calls；該 run cost **US$0.1868955**。
- 加上前一次由過嚴 route gate 中止、但已成功送出的 US$0.02765，Segment 4 累計
  **US$0.2145455**（owner 上限 US$1）。
- requested／canonical／endpoint 與三份 catalog snapshot hash 詳見
  [實作計畫 Segment 4](../../plans/2026-07-27-r1-task-discovery-implementation-plan.md#完成證據)。
- artifacts 在 gitignored
  `apps/api/output/professional-consultant-r1/preflight-20260727T113646Z/`；
  manifest 完整性與 secret scan 通過。
- grader 正反序一致只代表管線能解析、合併；`quality_conclusion_eligible=false`，
  **不能據此裁決任何 arm、模型或架構**。

## Segment 5 R1a 完成證據

- run：`r1a-20260727T120447Z`；
- 24 / 24 observations、32 generator calls、16 formal grader calls、2 calibration calls；
- 24 個 observation 全為 `completed`，無 deterministic／harness invalid；
- formal run cost **US$1.6658400**；連兩次中止嘗試共 **US$1.7712050**，
  低於 owner US$2.50 上限；
- exact model／endpoint、direct route、attempt 1、無 fallback、無 retry；
- call 43 命中 OpenRouter moderation inspection，但 `flagged=false`、內容未改寫。
  owner 核准只允許這個精確形狀並留下 limitation；其餘 pipeline 仍 fail closed；
- 由既有 capture 接續剩餘 7 次 grader，**沒有重送 32 次 generator**；
- 完整結果、人工稽核草案與暫定建議見
  [R1a 架構快篩結果](r1a-results.md)。

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
