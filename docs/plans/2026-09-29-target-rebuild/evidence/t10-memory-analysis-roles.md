# T10：B1／B2 角色工具 schema 預檢

## 外送 manifest（執行前記錄）

- 記錄時間：2026-09-30 10:56 Asia/Taipei；Owner 本次明確授權適用。
- 範圍：新目標 B1 `work_situation_analyst`、B2 `work_understanding_analyst` 的實際 canonical function definitions；沿 `function_definition` 讀取權威 schema 的生成副本，不由 Pydantic 重建、不造 dummy binding。
- 外送內容僅為工具定義及全合成短訊息：instructions = `Synthetic schema validation only.`；user = `Validate the tool schema.`。不含員工／JD／正式訪談／資料庫內容。
- 模型：`gpt-6-luna`，reasoning effort `medium`；正式 OpenAI Responses input-token count endpoint。
- 上限：每角色一次 count，合計最多 **2 次 HTTP 嘗試**；每次 timeout **30 秒**；**0 generation、0 retry**，禁止 redirect。
- key 僅由 `read_openai_api_key` 讀取 `apps/api/.env`，不顯示、不寫證據；不讀取其他環境或金鑰來源。
- 不宣稱 count 免費；本記錄不是費用帳單，若回傳 input_tokens 也不將其冒充生成 usage／結算金額。
- 屬 [T08 同批 demo manifest](t08-consultant-turn.md#51-真模型背景旅程-manifest執行前) 的兩次預檢，不重設／另加生成預算；沿該批總成本上限。count 費用尚未核實，不把其未知費用記為零。
- 400 或其他失敗先停下記錄，離線研究原因，不盲重試、不擴大本次外送額度。
- 接受條件：兩角色的 count 請求各一次被 API 接受。這僅證明所送 strict tool schema 在 count 路徑可接受，不證明真訪談品質、生成／工具選擇品質，也不是 T10 或全 gates 完成。

## 結果

離線 Red：新增 helper／role 參數前，8 個窄測試依預期失敗。Green：相同窄測加既有路由、權限及 import boundary 共 **31 passed**（1.43s）。Mock HTTP 已驗兩角色 canonical definitions、一次 count、30 秒、400／503 即停止且不按 retry header 重送、輸出不洩露 key。

### 真 API count（2026-09-30 10:59 Asia/Taipei）

| 角色 | 工具數 | API count 接受 | input_tokens | HTTP 嘗試 | generation／retry |
| --- | ---: | --- | ---: | ---: | --- |
| B1 `work_situation_analyst` | 6 | 是，程序 exit 0 | 1,780 | 1 | 0／0 |
| B2 `work_understanding_analyst` | 8 | 是，程序 exit 0 | 2,030 | 1 | 0／0 |

總計 **2 HTTP、0 generation、0 retry**；各 30 秒 timeout 並另有同長度的總等待界線，未逾時、未有 400，沒有 rerun。兩次授權額度已用完。input_tokens 是供應商 count 回值，不是已結算費用；未宣稱 count 免費。

完整 definitions 的 SHA-256（UTF-8 JSON，`ensure_ascii=False, sort_keys=True, separators=(",", ":")`）：

- B1：`a249b15d9323df25bfaf5dc471e5e6a4d0fd81beecf124cf1ea104e5df3cb7d8`
- B2：`96b7aaca8aa3199d0ef45c25bacc7af25d274170cf8924639c2667e3a42bb8bc`

B1 為 `read_work_situation_map`、`read_work_situation`、`read_interview`、`create_work_situation`、`update_work_situation`、`delete_work_situation`。B2 另可讀 `read_work_understanding_map`／`read_work_understanding`，三項 write 則只限 `work_understanding`。沒有新增同義工具、B1 理解讀取權限或 B2 情境寫入權限。

實測命令（cwd `apps/api`；**本次已執行，非待辦，不要自動重跑**）：

```powershell
./.venv-target/Scripts/python.exe -B scripts/probe_consultant_tool_schema.py --role work_situation_analyst --key-file .env
./.venv-target/Scripts/python.exe -B scripts/probe_consultant_tool_schema.py --role work_understanding_analyst --key-file .env
```

### Canonical definitions 接縫

- `workflows/memory_analysis/tools.py`：`memory_analysis_tool_definitions(layer: MemoryLayer)`，無 binding、DB、dummy service 或新 registry。
- `transport/model_tools/memory_reads.py`：`memory_read_names(layer=None)` 與既有 `memory_read_definitions(names=...)`；bound `MemoryReadTools.names` 委派同一權限選擇。
- `transport/model_tools/memory_writes.py`：`memory_write_names(layer)`／`memory_write_definitions(layer)`；bound `MemoryWriteTools` 委派同一名稱及定義。原 descriptions、parameters、strict、路由、錯誤及效果不變。
- 兩角色 runtime 仍組合這兩個實際工具 class；探針只組合其相同 helper。測試逐項比較完整 definitions 與 names，無複製 schema。所有 parameters 沿 `function_definition`；權威／生成 JSON schema 都沒有修改，也未執行 codegen。
- `scripts/probe_consultant_tool_schema.py --role` 預設仍為 `consultant`；本次未執行 A 預檢。

離線驗證命令（cwd `apps/api`）：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_memory_schema_probe.py tests/unit/test_memory_analysis_tools.py tests/unit/test_import_boundaries.py tests/contracts/test_memory_read_tool_dispatch.py -q -p no:cacheprovider --tb=short
```

交付前再驗同組 **31 passed（1.58s）**；五個改動 Python 檔案 Ruff 通過，三個 runtime module 與探針共四個檔案 mypy 通過；未放寬 import boundary 測試。

未判定／未宣稱：真訪談分析品質、真生成工具選擇、全 T10／T16／全部 gates。這些不是 count endpoint 可驗的效果；本次不啟動訪談、不接觸 DB、不發布候選。

## 任務完成對照（2026-09-30 恢復後）

沿[任務表 T10 的 Red 與完成條件](../tasks.md#t10-b1b2-私有角色與-context)逐條對照既有測試；只補了一個缺口（V14 的情境差異專項測試）。路徑相對 `apps/api/tests`。

| T10 Red | 代表測例（真 PG，除註明外） |
|---|---|
| B1 透過錯誤／gap 看理解 | `unit/test_memory_analysis_outcomes.py::test_b1_rework_final_is_not_allowed_outcome`、`unit/test_role_prompt_contracts.py::test_analysis_prompt_roles_only_offer_their_permitted_write_layer`（B1 沒有任何理解讀取入口）、`integration/test_memory_read_workflow.py::test_candidate_reads_enforce_role_stage_and_fixed_interview_frontier` |
| B2 修改情境 | `integration/test_memory_candidates.py::test_role_and_stage_permissions_are_enforced_beyond_tool_registration`、`integration/test_memory_write_tools.py::test_model_create_update_delete_reports_real_effects_and_isolates_permission` |
| 回交重置分析／compact | `integration/test_memory_analysis_runners.py::test_b1_b2_rework_retains_candidate_private_history_and_original_frontier`、`integration/test_memory_batch_orchestration.py::test_b2_gap_roundtrip_keeps_its_existing_understanding`、`integration/test_memory_candidates.py::test_b1_return_keeps_b2_work_and_restore_retains_second_safe_point` |
| B2 只看已有引用而漏新增情境 | **本次新增** `integration/test_memory_stage_changes.py`：B2 收到的差異涵蓋新增（含尚無理解引用者）、刪除、改名（附 `previous_title`）、改正文、改回（淨文字與來源相同時明說，不給空 diff），已受影響的理解標題隨附，未動的情境不列；只有 B2 階段能取得（B1 階段被拒）。另 `integration/test_memory_read_workflow.py::test_candidate_map_includes_changes_after_its_stage_started` |
| 原話上界偷偷用 A 最新輪 | `integration/test_memory_source_windows.py::test_required_window_ends_at_requested_employee_not_final_reply_or_latest_history` |

| T10 完成條件 | 對照 |
|---|---|
| V10／V11／V14 的角色層 | V10：見 [T11 對照](t11-memory-batch.md#任務完成對照2026-09-30-恢復後)；V11：上表；V14：新增的差異專項測試＋既有 `test_memory_revisions.py::test_same_edit_is_noop_but_changing_back_creates_a_new_revision` |
| fixed F、共同訪談 read | `integration/test_memory_source_windows.py`（6 案）、`integration/test_memory_read_workflow.py`（7 案） |
| B2 讀現在情境＋必要 diff、只改理解；gap 具體、不要求固定互審 | 上表；`unit/test_role_prompt_contracts.py::test_model_copying_prompt_json_examples_will_satisfy_actual_outcome_parser` |
| 真模型證據 | 三批 A→B1→B2 正式發布（[T08 §5.2](t08-consultant-turn.md#52-真-a--b1--b2--正式快照1109-台北核對)）、課程行政旅程 4 批背景 Memory（[T17](t17-course-administrator-journey.md)；其中 1 批因已移除的金額預留攔截失敗）、之後的模擬員工評測中背景批次照常發布 |

**結論：**T10 的角色權限、固定資料與 context 在其範圍內成立，勾選。**不含**：背景整理品質是否讓長訪談更好（T14／T17）、按需差異在超長批次的容量（T15／T16）、跨程序故障矩陣（T12）。
