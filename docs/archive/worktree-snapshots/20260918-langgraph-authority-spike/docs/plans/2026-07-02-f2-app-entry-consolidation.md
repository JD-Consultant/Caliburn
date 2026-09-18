# Plan — F2 後端 app 入口收斂(single composition root + `/healthz` 統一 + 移除 demo)

- 依據:[ADR 0017](../adr/0017-app-entry-single-composition-root.md) · 研究 [`../specs/2026-07-02-app-composition-health-degradation-research.md`](../specs/2026-07-02-app-composition-health-degradation-research.md)。
- 原則:**move-only**;green-before==green-after(baseline:api `uv run pytest` 149 passed);一 task 一 commit。

## Task 1 — 抽單一 wiring 點,main/live 變薄殼,health 統一 `/healthz`

**新增**
- `apps/api/app/api/router.py`:`api_router = APIRouter(prefix="/api/v1")` + `include_router(users/job_profiles/documents/ai)`。
- `apps/api/app/app_factory.py`:`configure(app: FastAPI) -> FastAPI` —— 加 CORS(統一一份)、`app.include_router(api_router)`、`@app.get("/healthz")`(含 DB readiness 檢查,搬 `main.py` 現有邏輯)。

**改**
- `main.py`:刪重複的 router/CORS/`/health` 區塊 → `app = FastAPI(...); configure(app)`;保留 lifespan(dispose engine)。`app` 仍 module-level(測試 import 不變)。
- `copilotkit_live_app.py`:刪重複的 router/CORS/`/healthz` 區塊 → 保留自己的 `AsyncExitStack` lifespan(checkpointer + `/copilotkit`)+ 呼叫 `configure(app)`。

**測試**
- 新 `test_app_wiring.py`:斷言 `configure` 後四組 REST 路由都在(擋漏掛);`/healthz` 回 200。
- `test_copilotkit_live_app.py`、`test_ai_*`/`test_documents_api`/`test_task_catalogs_api`(import `from app.main import app`)不改,應維持綠。

**驗收**:`cd apps/api && uv run pytest -q` == baseline(+ 新斷言);`curl 127.0.0.1:8001/healthz` 回 ok(重啟 live app 後)。
**commit**:`refactor(api): single composition root — api_router aggregate + configure() shim; unify /healthz [F2, ADR 0017]`

## Task 2 — 刪 demo app

**刪** `apps/api/app/copilotkit_app.py` + `apps/api/tests/test_copilotkit_endpoint.py`。
- 先確認 `build_demo_agent` 仍被 `test_serving_smoke.py` 用(留函式)。已查:無其他 app 用。
**驗收**:`uv run pytest -q` 綠(少 1 test)。
**commit**:`refactor(api): remove unused demo app copilotkit_app.py [F2, ADR 0017]`

## 同步 living docs(併入本輪)
- `apps/api/README.md`:health 行改「統一 `/healthz`」(去掉「非 /health」但書);結構段補 `api/router.py`(聚合)、`app_factory.py`(configure)。
- `docs/runbook.md:22,43`:去掉「不是 /health」但書(現統一)。
- `ARCHITECTURE.md`:api 列 or 跨切原則補一句「單一組裝點(composition root)」(視精簡原則,最小補充)。
