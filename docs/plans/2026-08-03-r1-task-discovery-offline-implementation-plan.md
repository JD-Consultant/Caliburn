# R1 Task Discovery 離線實作計畫

- 日期：2026-08-03
- 狀態：T1/T2/T3 COMPLETE；R1 IN PROGRESS（尚未 OFFLINE-READY／GATE-PASSED）
- 決策：[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)、
  [ADR 0042](../adr/0042-hybrid-job-discovery-and-ttop-formation.md)
- 研究：[R1 深入研究](../specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)、
  [R1 紅隊修訂](../specs/2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md)、
  [離線契約／verifier 實作研究](../specs/2026-08-03-r1-offline-contract-verifier-implementation-research.md)、
  [T2 prompt/schema/runner 研究](../specs/2026-08-03-r1-t2-prompt-schema-scripted-runner-research.md)、
  [T3 六臂／manifest／capture 研究](../specs/2026-08-03-r1-t3-ablation-manifest-capture-research.md)

## 1. 目標與現況

R0 已通過；R1 沒有 runtime、測試、commit 或 tag 證據，是第一個未通過 gate 的階段。本計畫只建立 fixture／CLI
品質路徑，不接 DB、正式 router、Web、Current JD、O/P/K/S/A、公版 retrieval、Graph runtime 或多 Agent。

本輪前 API no-network baseline：`1163 passed / 218 skipped / 5 failed`。五個 failure 均為既有 vNext historical
frozen-byte hash mismatch，與 R0 執行紀錄一致；本計畫不得順便改它們。

## 2. 已確認的 public seam

TDD 只測下列公開邊界：

1. `app.professional_consultant.contracts`：greenfield 的 domain／operation typed values；
2. `app.professional_consultant.verifier.verify_task_discovery`：來源＋結果進、排序穩定的 report 出；
3. `evals.professional_consultant.r1.loader`：runtime input 與 expectations／adjudication 分離載入；
4. runner 的一次呼叫與兩階段介面，以及後續 CLI／Trial Manifest。

domain 不 import FastAPI、ORM、provider SDK、`app.interview`、`app.interview_vnext`、`app.job_authoring` 或 eval package。
測試不 mock 自有模組，只在 external provider port 使用 scripted fake。

## 3. Task 切片

### T1 — 離線 authority bundle（完成）

先依 red→green 小步完成：

- `apps/api/app/professional_consultant/{__init__,contracts,verifier}.py`：strict／frozen／tuple contracts、
  `turn.understand`、`work.reconcile + decide` 與一次呼叫 output、固定 verifier issue vocabulary；
- `apps/api/evals/professional_consultant/r1/{contracts,loader}.py`：fixture metadata、runtime／evaluation 分離；
- `apps/api/evals/professional_consultant/r1/rubric/job-analysis-quality-rubric.v1.json`：單一 Job Analysis
  Quality Rubric；
- `apps/api/evals/professional_consultant/r1/cases/TI-R1-01-*`～`TI-R1-08-*`：每案
  `case.json`、`transcript.jsonl`、`expectations.json`、`adjudication.md`，全部依新 Task 定義重新裁決；
- `apps/api/tests/test_professional_consultant_{contracts,fixtures,verifier,dependencies}.py`：只經 public seam 驗證；
- 同 commit 更新 `ARCHITECTURE.md`、`docs/README.md` 與 living design 的實際狀態。

完成條件：8 案都可載入；runtime loader 無法讀到 expectations／adjudication；valid examples 通過；span、reference、
correction、disqualified-only support、duplicate relation 與 exact-repeat question 的 invalid examples 都被擋；cold import／AST
guard 通過；targeted tests、受影響 tests、baseline comparison、`git diff --check` 通過。提交一個 task commit，不打 R1 tag。

### T2 — operation prompt、portable schema 與 scripted runner（完成）

- 版本化 minimal／full prompt 與 light／heavy provider schema projection；
- 一次呼叫 runner，以及 `turn.understand → work.reconcile + decide` 兩階段 runner；
- deterministic verifier 在每個 provider result 後必跑；scripted fake 覆蓋成功、invalid、parse／provider failure；
- 禁止 provider payload 穿越 operation seam。

逐檔案施工順序：

1. `app/professional_consultant/prompts.py` 與 `prompt_assets/*.txt`：建立
   `task.discover` minimal/full、`turn.understand` full、`work.reconcile_decide` full 的版本化 artifact；prompt 只描述
   operation 責任、Task rubric、來源限制與一個下一問，不要求 chain-of-thought。
2. `app/professional_consultant/schema_projection.py`：從同一 output model 產生相同 value shape 的 light/heavy portable schema；
   light 只含 structural vocabulary，heavy 只多 property descriptions。兩者 inline `$ref`、移除 local constraints，
   `const` 轉 singleton enum，輸出 canonical JSON。
3. `app/professional_consultant/runner.py`：建立 neutral `StructuredOutputProvider` Protocol、frozen request/response、
   `run_task_discovery_once` 與 `run_task_discovery_two_stage`；operation request 不含 OpenRouter/SDK wire fields。
4. `contracts.py` 只補兩階段組合所需的 `WorkReconcileDecideInput.prior_claims`；`verifier.py` 補 stage-1 understanding verifier，
   不改 Task 定義或放寬 full verifier。
5. `evals/professional_consultant/r1/scripted_provider.py`：唯一 external-boundary fake，依序回 typed response 或 typed provider
   failure，保存 neutral requests 供 offline harness 使用；production `app/` 不 import 它。
6. 新增 `tests/test_professional_consultant_prompt_schema.py` 與 `tests/test_professional_consultant_runner.py`，逐個 red→green
   鎖定 artifact version、portable vocabulary、同 shape、一次／兩階段成功、stage-1 fail-fast，以及
   `provider_failed`／`output_json_invalid`／`output_schema_invalid`／`verification_failed` 四類錯誤。

完成條件：所有新 public seam 測試綠；stage 1 invalid 時 scripted provider 只收到一次請求；每個成功 provider result 後都跑
deterministic verifier；cancellation 不被改寫；dependency/cold-import guard 通過；完整 API 相較 T1 baseline 只增加 pass，既有五個
historical frozen-byte mismatch 不變。同 commit 更新 `apps/api/README.md`、`ARCHITECTURE.md`、`docs/README.md` 與 living design；
提交一個 T2 commit，不打 tag、不進 T3。

### T3 — 六臂 ablation、Trial Manifest 與 capture

精確建立 A1～A6，不增減 arm：A1 最強／輕／一次／minimal；A2 最強／輕／兩階段／full；A3 最強／重／
兩階段／full；A4 便宜／輕／兩階段／full；A5 便宜／重／兩階段／full；A6 最強／輕／一次／full。
快篩固定 48 observations、80 generator calls，grader 另計。runtime 外保存 source/state、context＋operation input、
trial evidence，由單一 immutable Trial Manifest 關聯。

逐檔案施工順序：

1. `evals/professional_consultant/r1/ablation.py`：建立 literal A1～A6 registry、獨立的 `HarnessProfile`、
   strongest／cheap logical tier、once／two-stage runner kind、8-case fast-screen plan 與 planned
   `48 observations / 80 generator calls / grader calls excluded`。不得由笛卡兒積多生 arm，也不得以 `PromptProfile`
   代替整體 harness bundle。
2. `evals/professional_consultant/r1/minimal_harness.py`：建立 A1 專用的 minimal typed output、turn-only context projection
   與 minimal verifier／once runner；只給 Task rubric，輸出 Task statements＋一個下一問。A6 仍走 T2 full once runner；兩者
   共用 provider port、strongest logical tier 與 light schema，但不得共用 full Work Model/context/verifier 後再假稱 harness ablation。
3. `evals/professional_consultant/r1/capture.py`：建立 strict／frozen source-state、context-operation-input、trial-evidence、
   response-resolved facts、artifact reference 與 `TrialManifest` contracts；canonical UTF-8 JSON 的 digest 對實際 bytes 計算，
   writer 先寫三層 artifact、最後 create-only 發布 manifest，reader 重算 SHA-256 並核對所有 trial/case/arm reference。
4. `evals/professional_consultant/r1/observed_provider.py`：建立 eval-only external-boundary scripted provider；requested model
   與 response facts 分欄保存，resolved model/provider/endpoint 只能由 scripted response receipt 提供。typed provider failure
   仍保存 terminal attempt evidence，不把外圈 payload 回灌 T2 neutral operation seam。
5. `evals/professional_consultant/r1/harness.py`：逐一執行 fast-screen 48 個 trial slot，A1 呼叫 minimal baseline、A6 呼叫
   既有 full once runner、A2～A5 呼叫既有 two-stage runner；
   每 trial 成功或 `OperationRunError` 都形成 terminal capture；summary 從 artifacts 計算 actual attempts、terminal trials、
   evaluable observations 與 failure count。stage-1 fail-fast 不補造 stage 2，planned 80 不得冒充 actual 80。
6. `tests/test_professional_consultant_ablation.py`：literal 比對六臂每欄，鎖定 8 cases、48 slots、80 expected calls、grader
   另計與 case/arm 唯一性。
7. `tests/test_professional_consultant_minimal_harness.py`：鎖定 A1 只有 turn-only context、minimal output schema／verifier，
   並證明 A1 與 A6 的 request 不是只換 prompt 名稱。
8. `tests/test_professional_consultant_capture.py`：鎖定 frozen contract、三層分離、create-only publication、digest／reference
   tamper fail-closed、requested/resolved 不同仍保存 response facts，以及 typed failure terminal evidence。
9. `tests/test_professional_consultant_harness.py`：用 external provider seam 的 scripted responses 完整跑 48/80，驗證 A1/A6
   各一次、A2～A5 各兩次、48 份 manifest 可讀；另以 stage-1 failure 證明 actual count 下降且 run 不得標完整。

完成條件：T1～T3 targeted 與 dependency/cold-import guard 全綠；production `app/` 不 import eval；capture 不含
expectations／adjudication；writer 無覆寫路徑；reader 對缺 manifest、缺 artifact、digest 或 relation 不符 fail closed；完整 API
相較 T2 baseline 只增加 pass，既有五個 historical vNext frozen-byte mismatch 不變。同 commit 更新 `apps/api/README.md`、
`ARCHITECTURE.md`、`docs/README.md` 與 living design；提交一個 T3 commit，不打 tag、不進 T4。

### T4 — blind grader、CLI dry-run 與 OpenRouter preflight seam

- blind grader 不讀 generator rationale，可逐維度回 `Unknown`；
- CLI 能 validate fixtures、dry-run 六臂、輸出 manifest/report，預設不連網；
- exact model slug／endpoint preflight、`require_parameters: true`、fallback off、portable schema 實送；
- mock/offline tests 完整；任何 live call 都需另有明確授權。

### T5 — live eval、shortlist 與 R1 gate

沒有付費授權時停在 `IMPLEMENTED／OFFLINE-READY／LIVE-EVAL-PENDING`，可建立
`r1-task-discovery-offline-ready`。取得授權後才執行：

1. 8 案快篩只淘汰明顯錯誤，不宣稱勝出；
2. shortlist 擴至 20–30 cases；
3. 實質改善預先定義為：相對 A1，paired case-family 的 Task-boundary normalized mean 至少提高
   `0.10`，且 family win rate 減 loss rate至少 `0.20`；任一 critical regression 直接不通過；
4. shortlisted critical subset 必須 pass³；下一問的自然、單一、不重複、不引導全部通過；
5. 持平或未達門檻選一次呼叫；可診斷性不能單獨放行兩階段。

只有完整報告、人工校準、tests 與上述 gate 全部有證據，才可標 `GATE-PASSED` 並建立
`r1-task-discovery-gate`。未過前不得開始 R2。

## 4. 停線條件

- 新 package 必須 import／wrap v3 或 vNext 舊 operation、state、Evidence、schema、gold、loader、grader；
- schema 為了必填迫使產生 Task，或 verifier 不能允許合法 no-op；
- fixture runtime path 可看到 expectations／adjudication；
- Task 只有過去、他人、否定或一次性內容支持仍能通過；
- 為完成離線 R1 而新增 DB、route、Web、SaaS、Graph 或 multi-agent framework；
- 兩階段未達實質改善門檻，卻因可診斷性或已投入工時被放行。

## 5. T1 執行證據（2026-08-03）

- RED：public package、eval loader、verifier issue vocabulary 與 bounded historical anchor 行為先分別失敗；GREEN 後
  `test_professional_consultant_{contracts,fixtures,verifier,dependencies}.py` 為 `18 passed`。
- 相鄰 architecture guards：R1 targeted 加 `test_app_wiring.py`、`test_job_authoring_dependencies.py`、
  `test_interview_vnext_dependencies.py` 為 `34 passed`（bounded-anchor 追加前；追加案例另由 targeted 18 覆蓋）。
- 完整 API no-network：`1181 passed / 218 skipped / 5 failed`；相較施工前 `1163 passed / 218 skipped / 5 failed`
  新增 18 passed，失敗仍是完全相同的 5 個 historical vNext frozen-byte hash mismatch，沒有新 regression。
- `git diff --check` 通過；AST 與 cold-process guards 證明新 core 未 import v3、vNext、Authoring、eval、FastAPI、
  persistence、provider SDK、torch 或 agent/Graph framework。
- 未執行 provider/live call、paid API、DB migration、route、Web 或 deployment；未建立 tag。下一個可獨立 task 是 T2。

## 6. T2 執行證據（2026-08-03）

- RED→GREEN slices：prompt module 缺失、兩階段 prompt 缺失、schema projector 缺失、once runner 缺失、strict duplicate-JSON
  分類、typed provider failure、two-stage runner 與 package export 均先有可重現 RED，再以 public seam 轉綠。
- professional consultant T1+T2 targeted：`29 passed`；相鄰 app wiring、job-authoring/vNext dependency guards 合跑
  `46 passed`。
- 完整 API no-network：`1192 passed / 218 skipped / 5 failed`；相較 T1 baseline
  `1181 passed / 218 skipped / 5 failed` 新增 11 passed。五個 failure 仍是完全相同的 historical vNext frozen-byte hash
  mismatch，沒有新 regression。
- light/heavy schema 三個 operation 都通過同 value-shape、portable keyword、closed/required object 與 canonical JSON guard；
  neutral request 明確沒有 provider/HTTP/SDK wire fields。
- scripted once/two-stage success、stage-1 fail-fast、provider/JSON/schema/verifier 四類 failure、attached verification report 與
  cancellation propagation 均通過 offline tests。
- 未呼叫 live／paid provider，未選 model/endpoint，未建立 Trial Manifest/Capture、CLI、DB、route、Web 或 deployment；未打 tag。
  下一個可獨立 task 是 T3。

## 7. T3 執行證據（2026-08-03）

- RED→GREEN slices：A1–A6 module、capture module、A1 minimal bundle 與整批 harness 都先因 public module 缺失形成可重現 RED；
  capture 第一版另由 strict Python-mode enum round-trip 測試抓到 reader 錯誤，改成 duplicate-check 後的 strict JSON-mode validation。
- professional consultant T1–T3 targeted／dependency guards：`40 passed`；加 app wiring、job-authoring/vNext architecture guards
  合跑 `57 passed`。
- 完整 API no-network：`1203 passed / 218 skipped / 5 failed`；相較 T2 baseline
  `1192 passed / 218 skipped / 5 failed` 新增 11 passed。五個 failure 仍是完全相同的 historical vNext frozen-byte hash
  mismatch，沒有新 regression。
- literal registry 精確鎖定 A1～A6；8 案 plan 是 48 trial slots／80 expected generator calls，grader 明確另計。A1 使用
  minimal typed output、turn-only context 與 minimal verifier；A6 使用 full once runner，不是只換 prompt 名稱。
- 成功離線路徑實際發布並讀回 48 份 manifest／80 次 attempts；A2 stage-1 provider failure 路徑留下 48 terminal trials、
  79 actual attempts、47 evaluable observations 與 1 failure，且不補造 stage 2、不標 execution complete。
- 三層 canonical JSON 由 create-only manifest 最後發布；reader 對檔案集合、SHA-256 digest 與 trial/case/arm relation fail closed。
  requested model 與 response-supplied generation/resolved model/provider/endpoint 分欄，provider failure 不推測 resolved facts。
- 未呼叫 live／paid provider，未選 exact model/endpoint，未建立 blind grader、CLI、OpenRouter adapter/preflight、DB、route、Web
  或 deployment；未打 tag。下一個可獨立 task 是 T4。
