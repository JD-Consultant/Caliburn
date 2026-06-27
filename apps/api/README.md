# api — Caliburn 後端(FastAPI + LangGraph)

「著作」bounded context 的後端。提供 REST `/api/v1/*`(users / job-profiles / documents / ai)與 AG-UI agent 端點 `/copilotkit`。擁有 **Postgres**(使用者文件、LangGraph checkpoints)。透過 HTTP 消費 `ocs-indexer` 取知識。

- **import 套件名**:`app`(Phase 3 才改 `caliburn_api`;現由 `pytest.ini` 的 `pythonpath=.` 提供)。
- **uv application 模式**(無 build-system,見 [ADR 0005](../../docs/adr/0005-per-app-uv-defer-workspace.md))。

## 跑

```bash
uv sync
docker compose up -d db            # 需 Postgres(:5432)
uv run python run_live.py          # :8001(Windows 用 SelectorEventLoop,已內建)
# 或從 monorepo 根:npx turbo dev
```
健康檢查:`GET /healthz`(live app 是 `/healthz`,非 `/health`)。知識查詢需另起 indexer(見 [`../../docs/runbook.md`](../../docs/runbook.md))。

## 測試

```bash
uv run pytest -q     # 無 DB 時 DB 相關測試會 skip
```

## 結構(現況 → 目標)

現為 `app/{api/routes, services, graph_v3, models, schemas}`(layer-based)。
**Phase 3 目標**:抽 `core/`(ports + domain)、解 `graph_v3↔services` 纏繞、layer→domain 垂直切片。見 spec §二.2。

新增依賴:改 `pyproject.toml` + `uv lock`(舊 `requirements.txt` 已過期、待退役)。
