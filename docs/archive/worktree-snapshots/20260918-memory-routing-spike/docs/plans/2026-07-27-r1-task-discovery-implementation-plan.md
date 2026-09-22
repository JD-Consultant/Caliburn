# R1 Task Discovery 實作計畫

- 日期：2026-07-27
- 狀態：**Segment 1–5 完成**；Segment 5 以預算受限的 R1a 三 arm
  架構快篩完成（owner 於 2026-07-27 核准，US$2.5 上限），語意裁決待 owner 確認
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
| 5 | R1a 正式 24 observations（A1／A6／A2） | 實網路 | 批次完成；owner 語意裁決待確認 |

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
   違反設計 §5.3.1 第 6 條。公開 `build_blind_packets()` 會先強制套用
   `gradable_views()`，只放行 `completed`，呼叫端不能直接繞過。

## Segment 4（已完成）

owner 於 2026-07-27 回覆「OK 繼續」，核准小額付費 disposable live preflight。這不是正式
R1 結果，不得使用八個凍結案例，也不得據此裁決架構。

### Catalog 預查（零推理成本）

2026-07-27 已從 OpenRouter 官方 model／endpoint API 核對：

| 角色 | request slug | canonical slug | exact endpoint tag |
|---|---|---|---|
| strongest | `openai/gpt-5.6-sol-pro` | `openai/gpt-5.6-sol-pro-20260709` | `openai/flex` |
| economical | `openai/gpt-5.6-luna-pro` | `openai/gpt-5.6-luna-pro-20260709` | `openai/flex` |
| blind grader | `anthropic/claude-opus-5` | `anthropic/claude-opus-5-20260723` | `anthropic` |

三個 exact endpoint 均宣告支援 `response_format`、`structured_outputs`、`reasoning` 與所需
token 參數。alias 與 canonical slug 必須分開保存：request 用前者，resolved route 只接受
catalog 當次回傳的 canonical slug。

### 最小實作與請求

1. 修正 request headers：明確送 `X-OpenRouter-Metadata: enabled` 與
   `X-OpenRouter-Cache: false`，transport 必須真的帶上它們。
2. 新增 experiment-only live preflight：抓 model／endpoint snapshot、驗 exact tag 與 required
   parameters、保存 canonical hash；不抽 production provider abstraction。
3. 補齊兩個 Segment 5 前必需 seam：
   - transport／route 失敗 → `harness_invalid`，不得混進模型品質；
   - grader structured output 解析與 label／dimension cardinality 驗證。
4. 只使用一個 inline disposable case，跑三條代表路徑：
   - A1：strongest／minimal／light／one-stage；
   - A3：strongest／full／heavy／two-stage；
   - A4：economical／full／light／two-stage；
   - 將有效輸出匿名後交 grader 正序／反序各一次。
5. 所有 request／response／catalog snapshot 經 redaction 寫入 gitignored `apps/api/output/`；
   只把 run ID、hash、route、token、cost、limitation 與結論回寫本文件／實驗 README。

### Stop gate

- 任何 catalog／exact endpoint／required parameter 不符，零推理停止；
- 任何 route metadata 無法證明單一 selected endpoint、attempt 不是 1、cache replay、model／provider
  不符，preflight 失敗；
- owner 後續將 Segment 4 上限提高為 **US$1.00**；實際所有 live 嘗試累計
  **US$0.2145455**，未觸發上限；
- API key／Authorization／reasoning 進 artifact，整次作廢；
- preflight 只證明 plumbing 可用，**不形成模型品質或架構結論**。

### 完成證據

- 成功 run：`preflight-20260727T113646Z`；inline disposable case，未使用八個凍結案例。
- generator：A1 一次、A3 兩次、A4 兩次；grader 正序／反序各一次，共 **7 calls**。
- 該 run cost：**US$0.1868955**；先前 route gate 誤判後停止的單次成功 HTTP
  cost：**US$0.02765**；Segment 4 累計 **US$0.2145455**。
- 三個 role 的 request／canonical／exact endpoint：
  `openai/gpt-5.6-sol-pro` → `openai/gpt-5.6-sol-pro-20260709` → `openai/flex`；
  `openai/gpt-5.6-luna-pro` → `openai/gpt-5.6-luna-pro-20260709` → `openai/flex`；
  `anthropic/claude-opus-5` → `anthropic/claude-opus-5-20260723` → `anthropic`。
- catalog snapshot hashes：strongest
  `0b99f2ed48027903340e8756e39c04d7ba9b9be9906573e93b8229f3a64ed222`；
  economical `fc8197855dd4b4b5c9e61dace167045a3cefea325b66907b9584ac8d94e7c649`；
  grader `d9f9565277f9bd3db81bf4d7702f956a8ff2a2846abef3cd00e0c97c27289986`。
- 真實 metadata 證實 `endpoints.total` 可能大於 1，即使 exact routing 後
  `available[]` 恰一個且 `selected=true`；gate 已改為以可路由集合與 selected endpoint
  證明歸因，不再把 catalog 總數誤當實際候選數。
- 三個 observation 都完成；grader 正反序一致。但案例只是 plumbing smoke，
  `quality_conclusion_eligible=false`，**不得據此說 A1／A3／A4 誰比較好**。
- gitignored artifacts 位於
  `apps/api/output/professional-consultant-r1/preflight-20260727T113646Z/`；
  7 份 manifest 均通過完整性驗證，secret pattern scan 為 0。

## Segment 5（R1a 三 arm 架構快篩，已核准）

完整六 arm 依 Segment 4 真實 token／cost 外推約需 US$3.5–5，超過 owner
提供的 US$2.5。owner 核准先執行不改 prompt／schema／rubric 的預算受限子集：

| Arm | 保留原因 |
|---|---|
| A1 | strongest／minimal／light／one-stage baseline |
| A6 | strongest／full／light／one-stage；與 A1 比 full harness bundle |
| A2 | strongest／full／light／two-stage；與 A6 比兩階段 treatment |

八案 × 三 arm＝**24 observations**，最多 **32 generator calls**；每案仍由
Claude Opus 5 正序／反序各評一次，共 **16 grader calls**。正式八案前先用
不屬於 suite 的三候選 packet 跑 grader calibration 正反序各一次。

### 效力邊界

- 本批只回答「full harness 是否值得進下一階段」與「兩階段是否值得進下一階段」。
- A3／A4／A5 未執行，因此**不能**回答 heavy schema 或 economical model。
- 本批名稱固定為 **R1a architecture screening**；不得寫成完整 R1 六 arm 已完成。
- 八案仍只有 development screening 效力；結果最多淘汰明顯錯誤設計或送
  20–30 案，不得宣稱 shipping architecture 已被證明。

### 成本與停線

- 付費上限為 **US$2.50**，只計本次 R1a fresh batch；每次 request 前保留
  role-specific 安全額度，預估下一次可能超限就停止。
- 不 repair、不在同一 request retry、不重送已成功 call；任一 `harness_invalid`、
  grader calibration 不符、secret／reasoning 外洩或 manifest 驗證失敗，整批停止。
  owner 裁決環境規則後，可從已驗證 immutable capture 接續**尚未執行**項目，但不得
  把舊 response 改寫成新 response。
- 若預算耗盡而 24 observations／16 grader calls 未完整，結果標
  `incomplete_budget`，不得用已完成的 arm/case 片段裁決。
- `TI-R1-02`、`TI-R1-07` 全部輸出，以及任何 grader fail／unknown，進 owner
  review queue；未完成 owner review 前只能提供 provisional screening analysis。

### Grader calibration 修訂紀錄

第一次 calibration 正反序一致，唯一差異是「未提出 Task、只要求澄清」的候選：
grader 對 `source_grounding` 回 `unknown`，原 gold 寫 `pass`。依 rubric，
`source_grounding` 問的是 Task 是否有合法來源；沒有 Task 就沒有可評 claim，不能硬算
pass，因此修正 gold 為 `unknown`，grader prompt 不變。這是設計允許的唯一一輪
calibration 修正；第一次兩次 grader calls 共 US$0.047885，後續 fresh run 上限降為
US$2.45，使所有 R1a 嘗試累計不超過 owner 的 US$2.50。

第二次 calibration 在第一個 forward call 以 `finish_reason=length` 停止；usage 顯示
2048 completion tokens 中 reasoning 只有 295，主因是可見 `reason` 過長。依 §8.2.1
允許的唯一一輪 grader prompt 修正，prompt 升為
`r1-task-discovery-grader.2`，只增加「每個 reason 限一個短句（最多 30 個中文字）」；
模型、rubric、dimensions、schema 與 generator prompt 均不變。該失敗 call 花
US$0.05748；前兩次嘗試累計 US$0.105365，因此下一個 fresh run 上限降為 US$2.39，
所有 R1a 嘗試累計仍不超過 US$2.50。

### Live 執行與 resume 紀錄

正式 run `r1a-20260727T120447Z` 完成 32 次 generator 與前 9 次 formal grader
後，call 43 的 OpenRouter metadata 出現：

```json
{
  "type": "guardrail",
  "name": "moderation",
  "data": {"engine": "openai-moderations", "flagged": false}
}
```

舊 gate 把所有非空 pipeline 一律停線。依 OpenRouter 官方 router metadata／guardrail
定義與 owner 裁決，規則收斂為：

- 只接受 `type=guardrail`、`name=moderation`、`data.flagged=false`；
- 保存 `inspected_nonmutating: moderation` limitation；
- `flagged=true`、未知 guardrail、plugin、compression／healing 或其他 pipeline
  一律 fail closed。

call 43 的 manifest 與 raw response 保持不可變；resume 重新驗 file hashes、route
identity、raw response 與 local parser，沒有改寫舊 artifact。其後只補送尚未執行的
7 次 grader，沒有重送 calibration 或 32 次 generator。綁死本 run／call 43 的
一次性 recovery code 在完成後移除，不把事故腳本偽裝成長期通用框架。

完成證據：

- 24 / 24 observations、24 `completed`；
- 32 generator calls、16 formal grader calls、2 calibration calls；
- run 共 50 個 call directories；
- formal run cost `US$1.6658400`；
- 加上前兩次中止嘗試共 `US$1.7712050 < US$2.50`；
- batch 完整，`quality_conclusion_eligible=false` 直到 owner 確認語意稽核；
- 結果與限制見
  [R1a 架構快篩結果](../experiments/2026-07-27-r1-task-discovery/r1a-results.md)。

## 已知會踩的環境雷

- 跑測試用 `apps/api` 的 uv 環境（`uv run pytest <path>`）；本機 global python 沒有 pytest。
- **async 測試一律加 `@pytest.mark.asyncio`**：`asyncio_mode=auto` 只在 `apps/api/pytest.ini`
  被當 rootdir 時生效；用絕對路徑跑本目錄時吃不到，async 測試會被**靜默跳過**而不是失敗。
  （Segment 2 一度有 9 個測試這樣消失。）
- CJK 內容需 `PYTHONUTF8=1`。
- 檔案是 LF，git autocrlf 會轉；比對用 `git diff`。
