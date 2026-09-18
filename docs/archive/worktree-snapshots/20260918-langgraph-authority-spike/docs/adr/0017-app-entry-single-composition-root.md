# ADR 0017 — 後端 app 入口收斂:單一組裝點 + `/healthz` 統一

- **狀態**:Accepted（2026-07-02）。
- 研究依據:[`../specs/2026-07-02-app-composition-health-degradation-research.md`](../specs/2026-07-02-app-composition-health-degradation-research.md)(§2.1–2.4、§3、§4-F2)。
- 關聯:API review findings F2([`../specs/2026-06-30-api-review-findings.md`](../specs/2026-06-30-api-review-findings.md) §F2)。

## 脈絡

後端有**三個 app 入口**,各自 `include_router`,導致「測試打的 app ≠ 生產跑的 app」:

| 模組 | health | 誰跑 | 誰測 |
|---|---|---|---|
| `app.main:app` | `/health`(查 DB) | Dockerfile（api 不在 compose,近閒置） | **全部 REST 測試** |
| `app.copilotkit_live_app:app` | `/healthz` | `run_live.py`（dev/生產,:8001） | 只一條 health 測試 |
| `app.copilotkit_app:app` | `/healthz` | 沒人跑（demo） | `test_copilotkit_endpoint` |

四個 REST router 在 `main.py` 與 `copilotkit_live_app.py` **各掛一份 = 兩個組裝點**。加新 router 若漏掛其一,**測試(打 main)看不到、但生產(跑 live)有** → 靜默漂移。CORS/health 路徑也兩份不一致。

## 決定

落實 **single Composition Root**(Mark Seemann):wiring 只有一份,入口模組變薄殼。**不引入 `create_app()` 工廠**——工廠是 Flask 傳統;FastAPI 主流(Netflix Dispatch、`zhanymkanov/fastapi-best-practices`)是 **global `app` + 單一聚合點**,測試隔離用 `dependency_overrides`(本專案已用 ASGITransport)。

1. **新 `app/api/router.py`**:唯一的 `api_router = APIRouter(prefix="/api/v1")`,聚合 users/job_profiles/documents/ai。
2. **新 `app/app_factory.py::configure(app)`**:單一 wiring 來源——掛 `api_router` + CORS + `/healthz`(含 DB readiness 檢查)。
3. `main.py`、`copilotkit_live_app.py` 都只呼叫 `configure(app)`;**lifespan 各自保留**(live 需 PG checkpointer + `/copilotkit`,tests/docker 不需要——lifespan 不同是合理的,要單一化的是 wiring)。
4. **health 統一 `/healthz`**:`main` 的 `/health` → `/healthz`,回應含 DB 檢查。系統內部一致(indexer 亦 `/healthz`、`HttpIndexerClient.healthz()` 依賴此路徑)。
5. **刪 demo app `copilotkit_app.py`** + `test_copilotkit_endpoint.py`:其能力已被 live app + stub 依賴覆蓋;`build_demo_agent` 保留(`test_serving_smoke` 仍用)。

## 後果

- ✅ 加/改 router 只動 `api/router.py` 一處 → **wiring 漂移結構上不可能**;測試從此驗到與生產同一份 REST wiring。
- ✅ CORS/health 收斂成一份,去除既有不一致。
- ✅ app 入口從 3 → 2(`main` = REST-only 薄殼給 tests/docker;`copilotkit_live_app` = REST + copilotkit,生產入口)。
- ✅ move-only:router/CORS/health 皆搬移,行為不變;既有測試 import(`from app.main import app`)不變,靠 149 測試當 characterization net。
- ⚠️ `/health`→`/healthz` 屬對外路徑變更,但已查證**零外部消費者**(web 打 REST + `/copilotkit`;compose 無 api healthcheck;README/runbook 已載 `/healthz`,順手更新)。
- ⚠️ `configure()` 須確保不漏掛 router → 加一條「四 router 皆在」的斷言測試當網子。

## 延後(記錄,非遺漏)

- **health 遷 `/livez` + `/readyz`**:K8s 官方 `/healthz` 已 deprecated,現代標準是 livez(活著,不查依賴)/readyz(可服務,查 DB)。但本專案**尚無 K8s / 容器編排**(compose 只跑 db/qdrant/embedder,app 在 host)→ 現無讀者,YAGNI。**待 api 容器化上 K8s 時遷移**,readyz 查 DB + indexer 可達;屆時翻新 ADR。
