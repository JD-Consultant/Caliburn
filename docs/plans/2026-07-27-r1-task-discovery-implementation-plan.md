# R1 Task Discovery 實作計畫

- 日期：2026-07-27
- 狀態：**Segment 1–3 完成**；Segment 4–5 待 owner 逐段核准
- 上位決策：[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)、
  [ADR 0041](../adr/0041-r1-p0-closure-first-version-context-and-holdout.md)
- 實驗設計（唯一 authority）：
  [R1 Task Discovery 實驗設計](../specs/2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md)
  （含 §17 第一輪審查處理；第二輪已回覆共識成立）

> 本計畫只負責「怎麼做」。任何與實驗設計衝突之處，**以實驗設計為準**；要改設計得回去改那份文件，
> 不在計畫裡偷偷偏離。

## 分段與停線

照實驗設計 §16 切五段。**每段一個 commit，綠了才 commit；跨段之間是 owner 停線，不自動往下做。**

| # | 段 | 網路 | 停線 |
|---|---|---|---|
| 1 | Contracts + 8 cases + rubric + verifier | 無 | 本段完成後交第二位審查者 |
| 2 | Thin OpenRouter transport + capture | mocked HTTP | 設計 §9.2／§12.1 綠 |
| 3 | 六 arm assembler + runner + blind grader | scripted output | 48 observation 骨架可跑 |
| 4 | Disposable live preflight | **實網路、丟棄式 fixture** | 需 owner 明確允許付費 |
| 5 | 正式 48 observations | 實網路 | 需 §12.3 八項全數具備 |

Segment 4 之前不得送出任何真實 API 請求。Segment 5 之前不得動用八案。

## 實驗資產與執行碼邊界

凍結案例、rubric、人工裁決與執行結果留在
`docs/experiments/2026-07-27-r1-task-discovery/`；可執行 Python harness 與 tests 放在
`apps/api/evals/professional_consultant_r1/`。這是為了使用 `apps/api` 的 pytest／uv 環境、
避免不同實驗的頂層模組撞名，並落實設計 §9.2 的單向 dependency guard。

這個 package 是**可丟棄的實驗儀器，不是 production 雛形**：

- `app/` 不得 import 它；
- 它不得 import `app.*` 或既有 `interview_vnext`；
- R1 的欄位、schema、prompt、runner 與 grader 名稱不構成成品契約；
- R1 只裁決 harness、呼叫階段、schema 重量與模型能力，不裁決正式資料庫、API、Graph 或
  Current Work Model 的最終形狀。

## Segment 1（本次）

### 交付物

```text
docs/experiments/2026-07-27-r1-task-discovery/
├─ README.md              # 導覽 + 本段邊界；設計 authority 仍在 docs/specs/
├─ rubric.md              # 裁決標準（common / full-only 分層、anchors、聚合）
├─ cases/
│  ├─ README.md           # 案例建立與凍結規則
│  └─ TI-R1-0{1..8}.json  # 八個凍結案例
├─ contracts.py           # case / CanonicalTaskReviewView / StateChangeDiagnosticView 形狀
├─ validate_r1_cases.py   # 案例凍結完整性檢查 + suite canonical hash
├─ verify_output.py       # 對單一模型輸出跑 deterministic checks
├─ test_validate_r1_cases.py
└─ test_verify_output.py
```

### 邊界

- **無網路、無 provider、無 DB、無 Web、無 production import**。
- 不建 runner、不建 context assembler、不建 grader prompt —— 那些是 Segment 2／3。
- 不做通用 eval framework、不做 hash chain、不做 event sourcing。
- `contracts.py` 只寫 R1 實際會用到的欄位；設計 §4.2 的 JSON 是形狀示意，不是要照抄成完整 JSON Schema。

### 逐項任務

1. **case 契約**：`schema_id`／`case_id`／`case_revision`／`source_type`／`case_family_id`／
   `sources`／`initial_work_model`（可選）／`expected`。
   `expected` 內含 `required_behaviors`／`forbidden_behaviors`／
   `common_applicable_rubric_dimensions`／`full_harness_only_dimensions`。
2. **八案**：素材取自
   [R1 深入研究 §11](../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md) 的
   `TI-R1-01`–`08`。全部 `source_type: constructed_edge`、`case_family_id == case_id`
   （ADR 0040 決定 13；八案無衍生案例）。
3. **rubric**：common 與 full-only 維度分層、三值聚合、locked anchors、
   `flagged_n1`／`screening_signal_n2` 的效力上限、正反序雙評。
4. **驗證器**：
   - `validate_r1_cases.py` —— 凍結完整性（ID 唯一、來源引用合法、維度在白名單內、
     `initial_work_model` 的 `source_ids` 存在、無模板殘留），並算 suite canonical hash。
   - `verify_output.py` —— 設計 §11.1 中**不需要網路**的那幾條：JSON 形狀、source ID 存在、
     quote 逐字子字串、跨欄位引用合法、`clarify`／`no_change` 允許 0 Task、機械重複、
     arm metadata 未洩漏進共同視圖。
   - provider route／binding／retry 三條屬 Segment 2，本段不做，於程式內標明。
5. **測試**：pytest，涵蓋八案實際載入、每條 deterministic check 的正反例、suite hash 穩定性。

### 完成定義

- `uv run pytest` 綠；
- 八案通過 `validate_r1_cases.py`（含 `FROZEN_SUITE_HASH` 比對）；
- suite canonical hash 記錄於實驗 README；
- 期望值凍結（ADR 0041 決定 15：`預期`／`Critical failure` 不得為配合模型輸出而改寫）。

## Segment 2（已完成）

`provider_request.py`／`routing_facts.py`／`transport.py`／`capture.py` ＋ mocked-HTTP 測試。
涵蓋設計 §12.1 第 7–11 項：精確路由、每 attempt 一次 HTTP、resolved route 只能來自回應、
secret／reasoning 不進 capture、manifest 可驗 refs 與 hash。

**既有 `app/interview_vnext` 不是權威。** R1 是重新設計；舊實作可能有多餘或錯誤的決定。
本段只承接兩類東西：設計 §8.3 明文要求的條件，以及 OpenRouter 的 wire 形狀 ——
後者標為 **PROVISIONAL**，要在 Segment 4 用真實回應核對。讀不懂的形狀一律 fail closed。
dependency guard 測試禁止本 eval import `app.*`。

## Segment 3（已完成）

只做正式付費實驗前需要的 no-network 骨架，不建通用 eval framework：

1. `matrix.py`：固定 A1–A6，展開 8 cases × 6 arms＝48 observations，最大 generator calls＝80。
2. `assembler.py`：組裝 minimal／full、one-stage／two-stage、light／heavy 的 prompt、Context 與
   portable schema；不得包含 case-specific expected answer。
3. `runner.py`：依 observation plan 呼叫注入的 scripted port；one-stage 恰一次，two-stage 最多兩次；
   Stage 1 verifier 失敗即 terminal，不呼叫 Stage 2，也不 repair／retry。
4. `blind_grader.py`：只接收 canonical review views；建立 seeded 正序與完全反序 packet；
   同一維度兩次判決不一致時聚合為 `unknown`。
5. `report.py`：輸出 48-observation 骨架、deterministic outcome 與待 grader／owner 欄位；
   scripted 結果不得冒充模型品質結果。

最小測試只保護能影響結論的行為：

- 六 arm 與 48／80 計數；
- A1 不含 Current Work Model，full arm 會包含；two-stage final 仍含完整原始 sources；
- one-stage／two-stage 呼叫次數與 Stage 1 terminal fail；
- common projection 不洩漏 arm／schema／model／rationale；
- 正反序與 `unknown` 聚合；
- production/eval 雙向 dependency guard；
- 全程無真實 network。

Segment 3 完成後停線。Segment 4 的 disposable live preflight 仍需 owner 明確允許付費。

### 完成證據

- scripted 48 observations 全數走完，generator call 上限實際為 80；
- Stage 1／final raw output 均由本地 portable-subset verifier 驗收，不依賴 provider 自述；
- `decision_basis` 可為 null，且投影後不進 blind grader，避免強迫 rationale 成為隱藏 treatment；
- focused package：**217 passed／0 skipped**；其中 Segment 3 僅 11 項結論保護測試；
- 未讀 API key、未送網路請求、未建立正式 trial 結果。

段末複查抓到兩處與設計不符，已於本段修掉：

1. Stage 1 的 context 原本也帶 Task 六項判準，違反設計 §5.3（判準屬 Stage 2），
   會讓 two-stage 退化成「同一份 context 打兩次」，A2 vs A6 的對比失效。
2. `final_invalid` 的 observation 仍留有 `canonical_view`，原本沒有任何東西阻止它被送進盲評，
   違反設計 §5.3.1 第 6 條。新增 `gradable_views()` 作為唯一入口，只放行 `completed`。

## 已知會踩的環境雷

- 跑測試用 `apps/api` 的 uv 環境（`uv run pytest <path>`）；本機 global python 沒有 pytest。
- **async 測試一律加 `@pytest.mark.asyncio`**：`asyncio_mode=auto` 只在 `apps/api/pytest.ini`
  被當 rootdir 時生效；用絕對路徑跑本目錄時吃不到，async 測試會被**靜默跳過**而不是失敗。
  （Segment 2 一度有 9 個測試這樣消失。）
- CJK 內容需 `PYTHONUTF8=1`。
- 檔案是 LF，git autocrlf 會轉；比對用 `git diff`。
