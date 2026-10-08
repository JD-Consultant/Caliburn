# INTPLAN context 與跨層接線獨立審查：2026-10-07

本輪找到的一個 P2 已修正並獨立複驗關閉：saved toolkit 的窄 shape guard 原容許數值型別改變及額外 assertion，新增反例先取得 **6 failed／13 passed** 的業務 Red，主代理修正後相同測試 **19 passed**。其餘下列 context、精確 C、writer 鎖與 completed recovery 範圍未見可重現缺陷。結論限定於原碼及本輪執行的反例，不代表 provider／訪談或最終 JD 品質已通過。

責任來源為 [設計 §6.6／§6.9](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md)、[施工計畫 T3](../../2026-10-07-interview-plan-implementation-and-comparison.md)，並依 [程式組織](../../../implementation/code-organization.md)、[程式撰寫規範](../../../implementation/coding-standard.md)、[開發規範](../../../implementation/development-standard.md) 分別核產品契約與工程責任。審查基準是 `HEAD 6ec52822ee475876ed20e57d818c8db298c42928` 之後的指定 WIP 差異及新增檔案；共享分支其他變更保留。

## Finding：保存的工具 schema 被誤認為相容能力

審查時 `agents/job_consultant/interview_plan_context.py` 的 `has_interview_plan_tools()` 使用 `diff.get("minLength") == 1`／`maxLength == 16_000`。Python 等值使 `True`／`1.0` 及 `16_000.0` 通過；這不是保存時的原 JSON 型別。另一方面，guard 只核必要欄位，`read` object 增加 `minProperties: 1`、`edit` object 增加 `maxProperties: 0`、diff 增加 `pattern: "^allowed-only$"` 也被接受。三者會分別排除原合法空參數、排除 required diff，或限制原合法 diff，不能宣稱仍是完整相容 plan toolkit。

這違反 §6.9 的 schema／bundle 不完整或能力不一致須拒絕，以及外部 runtime 值核原型別的要求。正常 canonical schema 沒有這些變更；影響在保存的 request schema 損壞或不相容時，原 v2 capability 被默認為可用。只需沿原 helper 核精確 numeric type 與窄 shape assertion keys，不需第二套通用 validator，也不能拿今天的全部文案／schema 字串替換原 captured template。`title`／`description` 是 annotation，與有效 assertion 分開。

一個先行唯讀 probe 將原 snapshot 的 diff `minLength` 改成 `True`，本機 `Draft202012Validator.check_schema()` 拒絕，但 `has_interview_plan_tools(ResponseRequest.from_snapshot(snapshot))` 回 `True`。這只證明本機 schema 與 saved capability 的矛盾，沒有呼叫 provider；`1.0` 的反例依本案保存型別契約，未宣稱 JSON Schema validator 必然拒絕它。

依主代理授權，僅於既有 `apps/api/tests/unit/test_consultant_tools.py` 新增 saved schema cases：

| 案例 | 修正前實際結果 |
| --- | --- |
| `minLength: true`、`minLength: 1.0`、`maxLength: 16000.0` | 三個預期拒絕均 `DID NOT RAISE ExecutionStateError`。 |
| read `minProperties: 1`、edit `maxProperties: 0`、diff `pattern` | 三個不相容 assertion 預期拒絕均 `DID NOT RAISE`。 |
| read／edit `additionalProperties` 為 `0`／`0.0`／字串／null | 八個皆已正確拒絕；現行 `is False` 沒有等值陷阱。 |
| read／edit `strict` 為 `1`／`1.0` | 四個皆已正確拒絕；現行 `is True` 沒有等值陷阱。 |
| 原完整 bundle；改工具 description、object title／description 與 diff description | 正例通過，保留原 captured annotation，不要求今天文案相同。 |

Red 命令：`uv run --project apps/api --locked pytest apps/api/tests/unit/test_consultant_tools.py -k saved_plan_schema -q` → **6 failed, 13 passed, 22 deselected in 1.76s**。這些失敗由預期拒絕未發生產生，非環境或 import 問題。`ruff check` 與 `ruff format --check` 該檔均通過。新增測試時未修改 production；修正與正式來源重新凍結由主代理執行。

### 修正後 closure：tests Red／Green

主代理在 pilot 完全停止後修正同一 helper：min／max constraint 先核 `type(value) is int`，object／diff 只容許原 assertion keys；額外 `title`／`description`／`$comment` 必須為字串。未知 vocabulary、default 或額外 pattern／object assertion 不再沉默通過，沒有新 generic validator 或用今天全文 schema 作字串比較。

本審查者重新讀修正原碼，並獨立執行相同 19 cases → **19 passed, 22 deselected in 1.66s**，六個原 Red 均轉 Green，型別拒絕與原 annotation 正例仍通過，finding 關閉。

主代理另執行：`uv run --project apps/api --locked pytest apps/api/tests/unit/test_consultant_tools.py apps/api/tests/unit/test_interview_plan_projection.py apps/api/tests/unit/test_interview_plan_projection_boundaries.py apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_reference_tool_registration.py -q --tb=short --basetemp S:/caliburn/tmp/intplan-final-capability-unit` → **103 passed in 2.23s**；主代理同時回報 source／test 兩檔 Ruff／format 及 guard 一檔 mypy 通過。103 門檻明記為主代理執行，不冒稱本審查者重跑。正式比較 source manifest 需依修正版重新凍結，原 pilot 不升格為正式結果。

## 指定範圍與實際判斷

| 原碼範圍 | 核對結果 |
| --- | --- |
| `interview_plan_projection.py` 私有 graph 與恢復 reader | 先委派原 C callback，保留 inactive paid C 核帳；再核 active。先讀 raw saver tuple，`__start__` 已有 binding 即恢復，沒有以 graph 展開值缺失誤判首次。pending resume 用 `None`，不重建 binding。 |
| 同檔 `_restore_binding()`／exact C 讀取 | strict adapter 加 JSON roundtrip 核原版本型別，核 file／execution／parent UUID 及非空 thread／checkpoint。parent request 身分與 C 內部 request 身分分清。已保存 projection 指定 exact C checkpoint，不因較新 C 或較新 plan head 改綁；讀原完整 C items 加原保存 item，不重序列化正文。 |
| `agent_execution/context_compaction.py` `read_compacted_window()` | 只讀 native saver；核原 request payload、input count、adopted complete window 與 preparation policy。傳入 checkpoint 時讀精確位置。共用 loop 沒有 import plan ORM，也未把較新投影當保存缺口的容錯。 |
| `context_binding.py` 原 template 與 v1／v2 | v1 原 shape 保留，v2 required plan base；version 原型別由 strict＋JSON roundtrip 核對。首個捕捉尚 pending 仍從原 saved preparation template 恢復能力，不用今日 flag 補工具。完整 capture 與 start／base 的缺失拒絕，nullable／空 body 不免除新能力位置要求。 |
| 同檔初始捕捉與 `workflows/interview_plans.py.read_active()` | 初始 plan base 沿原 file→writer 短交易，固定 frontier 與 start。預覽／壓後 plan read 的 active reader 在同一交易依相同鎖順序核 writer 並讀 head，沒有核 active 後另開讀 transaction 的競爭窗口；例外離開也釋放鎖。 |
| `runner.py`／`planning_instructions.py`／`bootstrap.py` | tools、wrapper、completion 依原 captured capability 分派。FOCUS 與 plan 專用指引分開，production 沒有新使用者模式。完成恢復早於 policy、preparation 與新 runtime，bootstrap 沿既有資源及 readonly workflow 接線，沒有新 provider 流程。 |
| `runner._recover_completed()`／`consultant_completion.py` | completed 分支讀原 binding、exact final、原 exchange；v2 核同 execution retained head，v1 不追補。原 writer 與 context position 在既有交易核對，native I/O 在鎖外；不再走 active-only JD preview／complete，不採用後輪最新 head，不重跑工具。新 saver／SDK／runner 實例的反例設拒絕 outbound transport，仍回原 exchange。 |

## 實際驗證與限制

以下在新增 schema Red 前，以當時最新正式 source 執行；真 PG 使用本次自有 loopback `_test` DB，fixtures 各建隨機 namespace。SDK MockTransport 為本機合成往返，不是付費 provider。

- `uv run --project apps/api --locked pytest apps/api/tests/unit/test_interview_plan_projection.py apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_reference_tool_registration.py -q` → **59 passed in 1.89s**。涵蓋原版本型別、整份 C、null／空、原 projection replay、inactive 委派順序及 capability／指引接線。
- 設 `CALIBURN_TEST_DATABASE_URL` 後，同命令執行 `test_interview_plan_projection_boundaries.py`、`test_interview_plan_context_binding.py`、`test_consultant_runner.py`、`test_consultant_runner_recovery.py`、`test_consultant_compaction_intent.py` → **29 passed in 39.30s**。raw `__start__` 失 ACK、pending writes 無法保存、較新 C、parent request 採用前／後中断均核原 binding／原 C／原 item；新物件 completed recovery 核原結果且無 outbound。
- 同 PG 執行 `pytest apps/api/tests/integration/test_interview_plan_storage.py -k active_plan_read -q` → **4 passed, 29 deselected in 3.90s**。真第二 connection 以 `FOR UPDATE NOWAIT` 核 file／writer 鎖持有與 rollback 釋放；cancelled／replaced writer 拒絕，合法 pending pause 保留原資格。

本輪讀取與測試沒有 provider request，未讀 paid pilot 原件、組別、plan notes、tool usage 或 cost，沒有改 production 或盲評判準。[匿名 JD rubric](blind-jd-rubric.md) SHA-256 仍為 `13c14a856ba68b2ae9d2f325e1fe1266db987d2c64ea9cefb83d49a18423cec2`；後續只等正式匿名 bundles 依原判準評閱。
