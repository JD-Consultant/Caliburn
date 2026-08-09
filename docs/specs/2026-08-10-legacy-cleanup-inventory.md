# Legacy Cleanup Inventory

日期：2026-08-10
基準：`c162bcb`、`docs/specs/2026-08-10-legacy-cleanup-and-monorepo-boundary-design.md`

## 判定

這份 inventory 只把仍受 Git 追蹤的 source、runtime composition、資料庫歷史、測試與 schema/codegen consumer 放在一起判斷。`app/job_analysis` 與 `/workspace` 是現行第一版；本輪不改它們的產品流程，也不改 migration、schema 或資料。

結論是：**沒有發現仍受 Git 追蹤且可安全直接刪除的程式元件（`DELETE NOW` 為空）**。能證明沒有 consumer 的元件已經在先前切片移除，而不是本輪再刪 runtime。`test_old_chain_removed.py` 已證明下列退役路徑不存在：舊 graph 鏈、ICAP retriever/matcher、舊 orchestrator/state service、`app.authoring`、`app.copilotkit_live_app`、`app.interview.executor`、`app.interview.commands`、`app.interview.context`。

## 分類 inventory

| 分類 | source / runtime | consumer | migration / table | test / codegen 證據 | 判定 |
| --- | --- | --- | --- | --- | --- |
| `DELETE NOW` | 無 | 無可驗證的 zero-consumer tracked component | 不適用 | 不適用；已刪路徑由 `apps/api/tests/test_old_chain_removed.py` 固定為不存在 | 本輪零刪除 |
| `KEEP LEGACY` | `apps/api/app/api/routes/interview.py`；`apps/api/app/interview/**`（含 `curation.py`、`service.py`、scribe/verify、eval capture）由 `apps/api/app/api/router.py` 掛載 | API live paths：`interview:start`、`interview:turn`、`interview:finish`、GET `interview`、`interview:review-events`；舊 OCS Web 的 `apps/web/src/app/documents/**`、`components/interview/**`、`hooks/useInterview.ts`、`lib/api.ts` 仍呼叫這些端點 | `apps/api/alembic/versions/0003_interview_tables.py` 起建立 `interview_sessions`、`interview_turns`、歷史 evidence/suggestions；0004–0009 延伸 ledger、LLM call、review event、eval capture；端點也讀寫 `document_versions` | `apps/api/tests/test_app_wiring.py`、`test_interview_routes.py`、`test_interview_service.py`、`test_interview_curation.py`、`test_interview_eval_capture.py` 等；Web runtime API 呼叫在 `apps/web/src/lib/api.ts`。`curation.py` 雖然沒有 `interview:curation` route，仍由 legacy service 使用，不能按 route 名稱誤刪 | 先保留；另以 route characterization 鎖住 live/retired path |
| `KEEP VNEXT` | `apps/api/app/interview_vnext/**`，含 domain、application、persistence、provider-neutral LLM 與 OpenRouter provider | 不掛 production router，但被 vNext 測試、persistence/replay、schema projection 與 provider conformance 使用；`app/job_authoring/postgres.py` 也讀取 vNext persistence/domain 型別 | `apps/api/alembic/versions/0010_interview_vnext_persistence.py` 建立八個 `interview_vnext_*` durable tables、FK、outbox/checkpoint/immutability guards | `test_interview_vnext_dependencies.py`、`test_interview_vnext_persistence.py`、`test_interview_vnext_fixed_replay_postgres.py`、`test_interview_vnext_execution_schemas.py`、各 provider/conformance/schema tests；`app.interview_vnext.*.write_schemas` 維護 generated schemas | 保留並維持 production route 隔離；不得當成 unused package 刪除 |
| `SEPARATE HARD CUT` | `apps/api/app/job_authoring/**`，尤其 `postgres.py`、`postgres_models.py`、contracts/transitions/schema writers | 沒有 current `job_analysis` production route consumer，但仍是 vNext Authoring Core 的 persistence/application consumer；`job_authoring/postgres.py` 依賴 `app.interview_vnext` | `apps/api/alembic/versions/0011_job_authoring_core.py` 建立 `job_authoring_documents`、`job_authoring_revisions`、`job_authoring_proposals` 三表及 FK/triggers；不能以刪檔代替資料 cutover | `test_job_authoring_dependencies.py`、`test_job_authoring_contracts.py`、`test_job_authoring_postgres.py`、`test_job_authoring_migration.py`、`test_job_authoring_vertical_postgres.py`；`uv run python -m app.job_authoring.write_schemas` 維護 generated schemas | 另開 migration/data/consumer cutover task；本輪不刪、不改 migration |

## Route 安全網

`apps/api/tests/test_app_wiring.py::test_configure_locks_legacy_interview_routes_and_retired_route_absence` 對 `configure(FastAPI())` 的實際 route set 做 characterization：

- 必須存在：`/api/v1/job-profiles/{profile_id}/interview:start`、`interview:turn`、`interview:finish`、GET `interview`、`interview:review-events`。
- 任何 path 若以 `interview:curation`、`interview:review`、`task-candidates`、`task-catalogs` 或 `document:buildTasks` 結尾，必須不存在。

這個測試只固定既有 app wiring，不新增 route、不更改 HTTP 行為；`interview:curation` 與 `interview:review` 只在 source comments/歷史說明中出現，不能把 comment 當成 runtime endpoint。

## 後續邊界

`DELETE NOW` 保持空集合。下一階段可做的是把 current `job_analysis` 的 composition dependency 與 legacy/vNext 分開、補 Web import boundary，並為 `job_authoring` 建立有 migration/data/consumer 證據的獨立 hard cut；在那之前不得刪除上述保留項目或重寫線性 migration history。
