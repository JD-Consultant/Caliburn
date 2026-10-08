# T1：規劃筆記共用編輯核心、工具與契約

本紀錄對應[實作計畫 T1](../../2026-10-07-interview-plan-implementation-and-comparison.md#t1純編輯工具與生成契約plan_tools)及[唯一設計 §5–6](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md#5-最小工具內容與-ui)。此處只保存工程證據；不是 provider 接受、真 PostgreSQL 保存或訪談／JD 品質驗收。

## 實際效果

- V4A parser／matcher／editor 沿既有演算法，共用純核心移至 `adapters/body_edits.py`／`body_matching.py`。`allow_blank_body=False` 只控制原有兩處非空前後置檢查。Memory 原入口保持非空政策；同一 actual-diff helper 移至 adapter，原 Memory preparation 保留相容 re-export。
- 規劃工具僅收 read `{}` 或 edit `{diff}`。prepare 綁當轮候選位置、套用全文、保留 nullable no-op，再固定完整 `PlanEdit` 與已核容量的原成功 JSON 文字。execute 不重新匹配或重算 diff／結果，而由 owner `apply()` 回原 `result_text`。
- 規劃正文／diff／hunks 初值為 16,000／16,000／32；原 ambiguity scan 政策不變。序列化完整結果上限 64,000 字元，超量在 prepare 拒絕；讀取不截斷；恢復不拿較小新版上限改寫原成功结果。
- 新 ConsultantTurn `plan_preview` 為 required nullable；物件內 `plan` 仍為 required nullable。HTTP `interview-plan-view` 與工具共用 canonical 正文；Python／TypeScript／packaged tool schemas 由鎖定生成器產生。
- `ConsultantTools` 可綁規劃 handler；原無此能力的 handler 不接受新命令。新 template 預設含規劃 read／edit；P1 與舊能力模板可明確設 `interview_plans_enabled=False`，捕捉／恢復及 runner 接線由 T3 驗證。

## Red 與 Green

所有命令在 `S:\caliburn` 執行，使用既有 `apps/api/.venv/Scripts/python.exe`。初次依 README 使用 `uv run --project apps/api --locked ...` 時因 sandbox 無法寫 uv cache 而失敗；此環境問題不算 Red。TemporaryDirectory／pytest tmp_path 的新目錄 ACL 也受 sandbox 阻擋；後續有界生成／全套暫存測試以工具自動核准的 escalation 執行，未更改來源資料或解除 schema 的遠端引用限制。

1. **空正文用途 Red：** 新 `test_interview_plan_body_edits.py` 先執行，五例因既有函式沒有 App-only `allow_blank_body` 介面而失敗。直接呼叫既有 `apply_body_diff('', '@@\n+筆記\n*** End of File')` 亦實際得到 `BodyEditError: Update requires a nonblank source body`；不是缺 module／拼錯 import。
2. **工具能力 Red：** `test_consultant_tools.py::test_new_consultant_template_advertises_minimal_plan_read_and_edit_tools` 在既有 template 上得到 `AssertionError: read_interview_plan not in definitions`。
3. **核心 Green：** `python -m pytest apps/api/tests/unit/test_interview_plan_body_edits.py apps/api/tests/unit/test_memory_body_edits.py apps/api/tests/unit/test_memory_edit_preparation.py -q -p no:cacheprovider` → **74 passed**。涵蓋從空建立、全刪為空、無文字效果、空白／CRLF 保留、容量以及原 Memory 非空與原定位回歸。
4. **工具初版 Green：** 規劃工具／顧問分派／strict schema 三檔 → **70 passed**。測 nullable no-op、保留 untouched context 的模糊定位 actual diff、確定拒絕、準備階段輸出容量、較小新版容量下原成功結果重播、缺 nullable command 欄位、foreign execution。
5. **恢復型別 Red：** 真實鎖定 Pydantic 的 `Literal[1]` 在 strict JSON 中仍把 `true`／`1.0` 轉成 `1`，而 Python dict equality 認為這些值相等。新增 `test_saved_command_does_not_repair_a_non_integer_version` 兩例先得到 **DID NOT RAISE ValueError**。execute 改以 JSON 型別保真的 roundtrip 比較，未改原 `result_text`；規劃工具加既有兩份 Turn contract → **29 passed**。
6. **較廣受影響 Green：** 規劃 contract／tools／顧問分派／import boundary／原 Memory body 與 preparation → **140 passed**（在新增型別保真兩例前）。

## 生成器的具體接縫

鎖定 datamodel-code-generator 0.83.0 搭配 `--no-allow-remote-refs` 會將來源 `http/` 當安全基底，拒絕本次正式 `../tools/interview-plan.schema.json`；CLI 沒有受支援的基底旗標，公開 GenerateConfig 也拒絕 `base_path`。另對外部 root-object `$ref` 要求 modular output directory，所以共用正文採既有 `$defs` 風格，HTTP／preview 引用其正式 definition。

`generate_contracts.py` 在生成前只暫存目前 canonical 集合：檔名跨 family 碰撞拒絕；外部 URI、越出 `contracts/` 或不在 canonical 集合的引用拒絕；合法 local path 改為 flat staging 檔名且原 fragment 不變。Python generator 仍用 `--no-allow-remote-refs`，TypeScript generator 讀原 canonical schema；packaged tool resource 仍逐字複製原來源，不新增 DTO authority。

- `python apps/api/scripts/generate_contracts.py --check` → **exit 0、無差異**（全 http／tools）。
- `test_contract_generation.py` → **4 passed**：跨 family 本文、canonical 原件不變、remote／越界拒絕、同 basename 碰撞拒絕。
- HTTP Python 的 scalar property ref 生成 `Plan` RootModel；JSON wire 仍是原 nullable 字串。contract test 核 `model_dump(mode='json')` 完整等於原 wire，HTTP consumer 不手改 generated DTO。

## 目前驗證邊界

- T1 owned 13 檔 Ruff check／format check 通過。
- 共用核心／規劃工具／顧問分派四個 source 的 mypy strict 通過。
- `git diff --check` 通過；Git 的 LF／CRLF 提示不等於內容錯誤。
- 首次 API 全 unit／contracts：**1435 passed、8 failed**，失敗全為既有 Turn contract 測試尚未註冊共用工具正文 schema，未把該輪說成通過。T4 後續修正對應 registry，兩份 contract 與 legacy preview unit **13 passed**。整體重新執行的結果由 T5／主代理記錄，不覆寫此失敗。
- 第二次 API 全 unit／contracts：**1442 passed、3 failed**。同時施工的 T3 runner 新增完成結果恢復 I/O，既有 `test_reference_tool_registration.py::test_saved_reference_request_with_missing_client_fails_before_history_model_work` 與 `test_role_prompt_contracts.py` 的兩個 consultant effort fixture 仍使用無 async context manager 的 `Mock` session，失敗於 `_recover_completed`。已交主代理更新相應 I/O fixture並再驗；本輪不宣稱全套通過。
- 未在本切片使用資料庫、provider、金鑰、commit／push；真保存、取消競爭、captured context、HTTP/UI、provider 與品質 gate 分別由 T2–T5 負責。

## 交接

工具公開型別為 `InterviewPlanTools(workflow, writer, *, policy=..., max_result_characters=64_000)`，具 `names`／`read_names`／`write_names`；`prepare(name, arguments, operation_id)` 回拒絕文字或 `{"kind":"interview_plan_edit","version":1,"change":完整 PlanEdit}`，`execute(prepared)` 回 owner 原成功結果。正式 DTO 為 `generated/interview_plan_view.py:InterviewPlanView`。本切片可供獨立 spec／程式審查；必要整體門檻仍由主代理完成。
