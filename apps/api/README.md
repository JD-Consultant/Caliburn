# api — Caliburn 後端(FastAPI + LangGraph)

「著作」bounded context 的後端。提供 REST `/api/v1/*`(users / job-profiles / documents / **occupations**(根層職類目錄搜尋)/ ai)與 AG-UI agent 端點 `/copilotkit`。自訂方法用 AIP `:verb`(`document:finalize`、`document:buildTasks`,ADR 0019)。擁有 **Postgres**(使用者文件、LangGraph checkpoints)。透過 HTTP 消費 `ocs-indexer` 取知識。

- **import 套件名**:`app`(Phase 3 才改 `caliburn_api`;現由 `pytest.ini` 的 `pythonpath=.` 提供)。
- **uv application 模式**(無 build-system,見 [ADR 0005](../../docs/adr/0005-per-app-uv-defer-workspace.md))。

## 跑

```bash
uv sync
docker compose up -d db            # 需 Postgres(:5432)
uv run python run_live.py          # :8001(Windows 用 SelectorEventLoop,已內建)
# 或從 monorepo 根:npx turbo dev
```
健康檢查:`GET /healthz`(main 與 live app 統一,含 DB readiness;ADR 0017)。知識查詢需另起 indexer(見 [`../../docs/runbook.md`](../../docs/runbook.md))。

**兩個 app 入口,一個組裝點**:`app.main`(REST-only,給 tests/docker)與 `app.copilotkit_live_app`(生產,額外掛 PG checkpointer + `/copilotkit`)都經 `app_factory.configure()` 這個**單一 composition root** 掛 router/CORS/health,故 wiring 不會漂移(ADR 0017)。

## 測試

```bash
uv run pytest -q     # 無 DB 時 DB 相關測試會 skip
```

## 結構(六邊形,ADR 0008 已實作)

`app/{core(ports + domain)、adapters(DB/LLM/knowledge 等邊緣)、services(use-case)、authoring(LangGraph 編排,原 graph_v3)、api/routes(+ `api/router.py` 聚合)、app_factory.py(composition root:`configure()`)、schemas}`。Phase 3a 已抽 `core/`、移除 graph↔services 反向邊;ADR 0017 收斂 app 入口為單一組裝點。

新增依賴:改 `pyproject.toml` + `uv lock`(舊 `requirements.txt` 已過期、待退役)。
