# T09 UI 缺口 1：依職務檔案找回目前顧問 Turn

日期：2026-09-30。範圍：只讀 HTTP、既有 execution owner 查詢、公開狀態投影、唯一 schema／雙端生成及測試。這是新目標的一個切片，不代表 T08／T09 或整體 Goal 完成；前端接線、Demo 驗收仍由主線處理。

## 效果與接口

`GET /api/job-files/{job_file_id}/consultant-turns/current`

- 200：`{"turn": <ConsultantTurn>}`；Turn 欄位與既有 by-execution／by-command 狀態相同：`job_file_id`、`execution_id`、`status`、`pause_requested`、`input_text`、`allowed_controls`、`commentary`、`candidate`。
- 沒有進行中 A：200 `{"turn": null}`，必須明示 `turn`，不返回最近的 terminal 歷史。
- 檔案不存在：404 `{"detail":{"code":"job_file_not_found"}}`。
- 200 回應設定 `Cache-Control: no-store`。既有非終態 A 缺少原輸入等結果不一致情況回 503 `consultant_result_unavailable`，不吞成空結果。
- 目前非終態 enum 是 `active`、`paused`；正在暫停為 `active` 且 `pause_requested=true`，沒有發明 `pause_requested` 狀態值。
- 控制可用性沿既有 `allowed_controls` 投影；沒有控制服務時仍可找回 Turn，回空控制清單。

依據：[T09 缺口 §5](t09-ui-redesign.md#5-api-缺口交回後端處理)、[介面責任 §1／§2](../../../implementation/interface-and-delivery.md)、[execution 與 supervisor 責任 §6](../../../implementation/agent-execution.md#6-本機-a-supervisort08-有界接線)、[唯一契約來源](../../../implementation/data-and-contracts.md#5-唯一契約來源及生成)。

## 接線與取捨

`features/executions/persistence.py` 在原 `executions` 表依路徑的 `job_file_id`、固定 `consultant_turn` kind、active／paused 查唯一列；原 admission partial unique index 已保證至多一筆，沒有新表、migration、store 或第二套執行狀態。SQL 留在原 owner，service 回既有 `ExecutionInfo`。supervisor 的 active-only 掃描保持原職責。

`ConsultantStatusWorkflow.read_current()` 先透過 job-files 公開 query 區分檔案不存在，再讀 execution 查詢及共用 status／candidate／commentary 投影。三個狀態入口共用 `_read_status(session, execution)`，發現時取得的 execution 狀態不另讀成 terminal 歷史。HTTP 使用原 `turn_view` 白名單，不公開 writer、scope、checkpoint、reasoning 或原生工具 payload。

這是一次查詢觀察，不取得控制／寫入資格，也不承諾回應抵達後狀態不再變動；後續 pause／cancel／resume 仍由原 owner 重新核資格。讀取不 claim writer、不 notify supervisor、不執行或恢復 Graph、不觸發模型。

schema：將原 `ConsultantTurn` 形狀放進原檔案的 `$defs/ConsultantTurn`，原 root 用 `allOf` 引用；新 envelope 引用同一定義並允許 null。既有 wire 形狀不變。實測發現鎖定 datamodel-code-generator 的跨檔 root 引用要求目錄輸出，而既有生成器採單檔輸出；直接 root `$ref` 另觸發 TS resolver 循環。使用現成 `$defs`／`allOf` 後兩端生成與既有 UI guard 均通過，沒有修改生成器或手改生成物。這是有界機制相容調整，沒有新框架選型。

## Red／Green 與驗證

使用既有 fixture，在唯一授權的 `postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test` 建立／清理每測例自己的隨機 schema，未操作 Demo DB、DROP DATABASE 或 volume。

| 驗證 | 實際結果 |
| --- | --- |
| Red：新 current 查詢＋原公開歷史測試 | **12 failed、1 passed，7.04s**。新 `/current` 缺失，落到 UUID 路由並回 422；原 by-execution 公開歷史通過。這是實作前的真 PG 行為失敗 |
| 第一輪 Green：13 PG＋新契約 11＋既有契約 1 | **25 passed，7.37s**。新 `test_current_consultant_turn_contract.py` 為 4 個有效＋7 個拒絕案例；另跑既有 `test_consultant_turn_contract.py` 的 1 個案例。原「12 contract」指兩檔合計，並非新契約有 12 項 |
| 受影響 PG 回歸 | **42 passed，25.05s**：current、公開歷史、HTTP 控制／派送、正式完成與 supervisor |
| 完整後端 unit／contracts | **973 passed，10.54s** |
| 既有 interview 前端回歸 | **8 檔／43 passed，8.50s**；驗共用 schema 調整沒有破壞現有 UI guard |
| Ajv 專項＋interview 回歸 | **9 檔／52 passed，7.42s**；直接匯入既有 `validation.ts` 的 `isConsultantTurn`，驗五種原狀態、候選巢狀引用，另以同版 Ajv 註冊原 schema 後編譯新跨檔 `$ref`；驗 nullable envelope 及拒絕私有欄位／虛構狀態 |
| TypeScript | `tsc --noEmit` 通過 |
| 前端測試靜態 | 新 contract 測試的 ESLint／Prettier check 通過；未修改 `validation.ts` |
| Python 靜態 | 本切片 Ruff、format check、mypy 四個 production 檔通過 |
| 生成漂移 | `generate_contracts.py --check` exit 0，Python／TS 無漂移 |
| 差異 | `git diff --check` 通過；其他代理修改保留 |

上述第一輪 25 項與後續 42 項是不同命令的執行結果，不能累加為互不重複的案例總數；42 項為六個 PG 檔案，不含契約測試。2026-09-30 依主線提醒核對原 Green 命令與測例組成，補明此計數歸屬，未重跑測試。

PG 反例包括：新檔案 null／不存在 404、尚無 writer／候選即可找回、active／pending pause／paused、候選形狀、不同檔案與同檔 Memory 隔離、completed／cancelled／failed 不作 current、後來的新 A 可以找回。原公開歷史測試同時跑 current 與 by-execution，真 PG saver 的 checkpoint／pending writes 僅公開合法 commentary，拒絕 reasoning、metadata、工具 arguments 及 final 文字洩入公開中間訊息。

Ajv 專項為 schema 重構後依 Owner 指示補的相容性驗證，不冒稱新增業務行為的 Red。既有前端沒有獨立 shared-api contract test，故新增專項直接消費原 guard；`validation.ts` 目前只編譯 by-execution 的 `ConsultantTurn`，尚未匯入新 envelope。未來接線需先用 `consultant-turn.schema.json` 名稱註冊共用 schema，再 compile `current-consultant-turn.schema.json`；專項已實測此完整依賴解析，沒有只靠 TS 型別通過作保證。

另以 PG `default_transaction_read_only=on` 的獨立 engine 重複讀取 paused Turn；成功後原 writer／pause 狀態相同、正式訪談仍只有開場、正式 JD 未被候選取代。GET 不依賴模型配置。

環境失敗另記：第一個 repo-root pytest 因 `tests` import root 不符而 collection error，改在 `apps/api` 跑；不算 Red。生成器在 Windows sandbox 的 TemporaryDirectory 無法寫入，改 workspace temp 仍失敗；完整 unit 首跑為 968 passed／5 個合成 credential fixture 的 temp 權限錯誤；Vitest 首跑為 spawn EPERM。獲准沙箱外重跑後上述生成、unit／contracts、Vitest 均通過；未改工具鏈或停用測試，未讀真實 `.env`。

### 重現命令

以下使用本次指定 runtime。pytest 於 `S:\caliburn\apps\api` 執行，其餘於 repo root。

```powershell
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
& .venv-target/Scripts/python.exe -m pytest tests/integration/test_current_consultant_turn.py tests/integration/test_consultant_progress.py -q --tb=short -p no:cacheprovider
& .venv-target/Scripts/python.exe -m pytest tests/integration/test_current_consultant_turn.py tests/integration/test_consultant_progress.py tests/contracts/test_consultant_turn_contract.py tests/contracts/test_current_consultant_turn_contract.py -q --tb=short -p no:cacheprovider
& .venv-target/Scripts/python.exe -m pytest tests/integration/test_current_consultant_turn.py tests/integration/test_consultant_progress.py tests/integration/test_consultant_http_controls.py tests/integration/test_consultant_http_execution.py tests/integration/test_consultant_completion.py tests/integration/test_consultant_supervisor.py -q --tb=short -p no:cacheprovider
& .venv-target/Scripts/python.exe -m pytest tests/unit tests/contracts -q --tb=short -p no:cacheprovider
```

```powershell
$env:PATH = 'C:\Users\chenb\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
& apps/api/.venv-target/Scripts/python.exe apps/api/scripts/generate_contracts.py
& apps/api/.venv-target/Scripts/python.exe apps/api/scripts/generate_contracts.py --check
& 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' .research-tmp/pnpm-12.5.1/package/bin/pnpm.mjs --dir apps/web typecheck
& 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' .research-tmp/pnpm-12.5.1/package/bin/pnpm.mjs --dir apps/web test src/features/interview
& 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' .research-tmp/pnpm-12.5.1/package/bin/pnpm.mjs --dir apps/web test src/shared/api/current-consultant-turn.contract.test.ts src/features/interview
& 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' .research-tmp/pnpm-12.5.1/package/bin/pnpm.mjs --dir apps/web exec eslint src/shared/api/current-consultant-turn.contract.test.ts
& 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' .research-tmp/pnpm-12.5.1/package/bin/pnpm.mjs --dir apps/web exec prettier --check src/shared/api/current-consultant-turn.contract.test.ts
$turnSources = @('apps/api/src/caliburn/features/executions/persistence.py', 'apps/api/src/caliburn/features/executions/service.py', 'apps/api/src/caliburn/workflows/consultant_status.py', 'apps/api/src/caliburn/transport/http/consultant_turns.py')
$turnTests = @('apps/api/tests/integration/test_current_consultant_turn.py', 'apps/api/tests/integration/test_consultant_progress.py', 'apps/api/tests/contracts/test_current_consultant_turn_contract.py')
& apps/api/.venv-target/Scripts/python.exe -m ruff check @turnSources @turnTests
& apps/api/.venv-target/Scripts/python.exe -m ruff format --check @turnSources @turnTests
& apps/api/.venv-target/Scripts/python.exe -m mypy --config-file apps/api/pyproject.toml @turnSources
git -c core.safecrlf=false diff --check
```

## 本切片檔案與限制

- `apps/api/src/caliburn/features/executions/persistence.py`、`service.py`
- `apps/api/src/caliburn/workflows/consultant_status.py`
- `apps/api/src/caliburn/transport/http/consultant_turns.py`
- `apps/api/contracts/http/consultant-turn.schema.json`、`current-consultant-turn.schema.json`
- `apps/api/src/caliburn/contracts/generated/consultant_turn.py`、`current_consultant_turn.py`（生成）
- `apps/web/src/shared/api/generated/consultant-turn.ts`、`current-consultant-turn.ts`（生成）
- `apps/api/tests/integration/test_current_consultant_turn.py`、`test_consultant_progress.py`
- `apps/api/tests/contracts/test_current_consultant_turn_contract.py`
- `apps/web/src/shared/api/current-consultant-turn.contract.test.ts`
- 本 evidence。

未改前端 UI、settings／security／bootstrap／Vite／共用 README／tasks／current-decisions；工作目錄中這些檔案的並行差異屬主代理。未啟停 Demo、未連 Demo DB、未呼叫真模型、未 commit／push／merge。未跑所有 PG integration、瀏覽器跨裝置旅程或真模型品質；此切片提供 UI 所需入口與生成契約，實際 UI 使用 `/current` 仍待主線接線。

## 主線整合與獨立審核補正

主線先獨立重跑六個 PG 檔案＋新 contract，**53 passed（42＋11）**，既有 interview **43 passed**、新 Ajv 專項 **9 passed**、tsc 通過。不將子代理與主線重複執行加總成更多案例。

獨立 reviewer 發現原候選 fixture 的 `capabilities=[]` 沒涵蓋實際 DTO 轉接問題：`turn_view(...).model_dump()` 預設 Python mode 留下生成類別的普通 `Kind` Enum；另一個生成 DTO 的同名 enum 不是同一個 Python 型別。有知識／技能時 by-execution 成功，current 會因驗證錯誤成為 500。

主線在真 PG 中先透過人工能力 API 建立 knowledge／skill，再准入與初始化 A 候選，新增兩項 HTTP 等價回歸，修正前 **2 failed**，明確指向 `turn.candidate.work.capabilities.0.kind`。依 [Pydantic Enum serialization](https://docs.pydantic.dev/latest/api/standard_library_types/#enums) 改為 `model_dump(mode="json")` 後再交給 envelope validator；不更改生成檔、不放寬 schema，也不新增另一套 DTO converter。完整候選知識／技能和原 by-execution 回應應一致。

最後主線合併命令包含前述六個 integration 檔、新 current contract，以及 `test_dev_origin_settings.py`、`test_local_http_security.py`、`test_bootstrap.py`、`test_settings.py`：**130 passed，21.87s**（本片 PG／contract **55**＋安全片 **75**）。兩片 Ruff check 通過。API 仍未在 Demo 重啟載入，前端接線仍未實作；不把合成整合驗證寫成真模型或換瀏覽器旅程已通過。

獨立 reviewer 複核兩項修正後關閉原 important／minor，未發現新增問題；主線 scoped mypy（6 source files）通過。審核未代替尚未做的 UI／完整 PG／真模型驗收。
