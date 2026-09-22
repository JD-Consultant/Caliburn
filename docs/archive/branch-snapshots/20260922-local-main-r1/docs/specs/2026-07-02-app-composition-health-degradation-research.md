# App 組裝點 / health / 降級政策 — 架構研究(F1 + F2 落實前置)

> **類型**:研究紀錄(來源 + 診斷 + 選項 + 比對)。落實各自另開 ADR / plan。
> **日期**:2026-07-02
> **動機**:API review findings(`2026-06-30-api-review-findings.md`)的 **F1(降級契約不一致)** 與
> **F2(health/app 入口重複漂移)** 要落實。維護者要求「改得多、要仔細研究大廠/資深人士/主流/規範/最新的架構」,
> 且**特別強調注意架構**(api 是 hexagonal,ADR 0008)。本輪**只研究、未改碼**。
> **原則**:對齊公認專家(Seemann、Fowler)、大廠實作(Netflix Dispatch)、社群主流(zhanymkanov)、
> 官方文件(FastAPI、Kubernetes)、規範(AWS Well-Architected、Google SRE、IETF)。

---

## 1. 診斷:現況到底哪裡不對

### 1.1 F2 — 三個 app 入口 + wiring 重複 + 測試≠生產

| 模組 | health | 誰在跑 | 誰在測 | 掛了哪些 router |
|---|---|---|---|---|
| `app.main:app` | `/health`(查 DB) | Dockerfile `CMD`(api 其實不在 compose,近乎閒置) | **全部 REST 測試**(`from app.main import app`) | users/job_profiles/documents/ai |
| `app.copilotkit_live_app:app` | `/healthz` | **`run_live.py`**(本地 dev 8001,實際生產入口) | 只 `test_copilotkit_live_app`(打 `/healthz`) | 同上 **+ `/copilotkit`** |
| `app.copilotkit_app:app` | `/healthz` | 沒人跑(demo) | `test_copilotkit_endpoint` | 只 `/copilotkit`(stub agent) |

**根因**:四個 REST router 在 `main.py` 與 `copilotkit_live_app.py` **各掛一份**(兩個組裝點)。
- **測試驗的 `main:app` 生產不跑;生產跑的 `copilotkit_live_app` 只有一條 health 測試** → route wiring 可漂移(某端點只掛其一而沒被測到)。
- CORS 兩份也不一致(`main` 有 `allow_credentials=True` 且只 `localhost:3000`;`live` 多 `127.0.0.1` 但無 credentials)。
- health 路徑分裂(`/health` vs `/healthz`),回應格式也不同。

### 1.2 F1 — indexer 掛掉的失敗契約兩套

- **502(fail-fast)**:`task-candidates`、`ocs-search`。
- **降級回空**:`header-meta`、`task-catalogs`、`ai/*`。
政策是隱性的、散在各端點的 try/except,無統一分類、無「部分資料」訊號。

---

## 2. 研究:權威來源與發現

### 2.1 Composition Root(Mark Seemann)— 單一組裝點,越靠入口越好

Seemann《Dependency Injection Principles, Practices & Patterns》定義:
> *"A Composition Root is a (preferably) **unique** location in an application where modules are composed together."*
> *"Each application/process requires only a **single** Composition Root."*
> *"composition should take place **as close as possible to the application's entry point**."*

→ **診斷對照**:Caliburn 現在有**兩個組裝點**(main + live 各自 wire router),違反「single composition root」。這正是 F2 的架構病根——不是「該不該用工廠」,而是**組裝邏輯應該只有一份**。

### 2.2 FastAPI 結構:工廠 vs global app —— 主流其實是「單一 wiring 點 + global app」

**反轉發現(修正我先前的建議)**:

| 來源 | 做法 | 備註 |
|---|---|---|
| **zhanymkanov `fastapi-best-practices`**(社群最常引用,源自其 startup、**inspired by Netflix Dispatch**) | **global `app`**(`src/main.py` inits app),測試 `from src.main import app` + **`dependency_overrides`** 做隔離 | **不用 `create_app()`** |
| **Netflix Dispatch**(大廠實際 FastAPI 專案) | global `app` + 單一 `api_router` 聚合器(`api.py` 把各 domain router `include_router` 進一個 router) | 單一 wiring 點,非工廠 |
| 泛用「production patterns」部落格 | 推 `create_app()` 工廠(**Flask 傳統**:每測試 fresh instance) | FastAPI 官方 tutorial 用 global app;工廠非 FastAPI 慣例 |
| FastAPI 官方《Bigger Applications》 | `APIRouter` 分模組,`app.include_router()` 於單一 `main.py` 聚合 | 官方示範即 global app + 單一聚合 |

→ **結論**:FastAPI 圈的主流不是工廠,而是 **①一個 global `app` + ②一個單一 wiring 聚合點(`api_router` 或 `configure()`)**;
測試隔離靠 **`dependency_overrides` + httpx ASGITransport**(本專案測試已用 ASGITransport ✓)。
工廠(`create_app`)的價值(每測試 fresh app)在 FastAPI 用 `dependency_overrides` 就達成,**不必引入 Flask 式工廠**。

### 2.3 Lifespan 組合(官方)——lifespans 本來就該不同,用 AsyncExitStack 疊

FastAPI 官方《Lifespan Events》+ Discussion #9397/#10083:多個 lifespan 用
`contextlib.AsyncExitStack` 逐一 `enter_async_context` 疊起來。
→ **對照**:live app 需要 PG checkpointer + `/copilotkit`(要 DB),tests/docker 不需要。
**lifespan 不同是合理的**;要單一化的是 **wiring(router/CORS/health)**,不是 lifespan。
`copilotkit_live_app` 現有的 `AsyncExitStack` lifespan 保留即可。

### 2.4 Health 端點:K8s 官方已 `healthz` deprecated → `livez` + `readyz`

Kubernetes 官方《API health endpoints》(WebFetch 查證):
- **`/healthz`:v1.16 起 deprecated**。
- **`/livez`**:活著嗎?失敗→重啟(liveness,**不查依賴**)。
- **`/readyz`**:可服務嗎?失敗→把流量導開(readiness,**查 DB/依賴**)。
- `z` 後綴避免與業務路由衝突;`?verbose`、`?exclude=` 為官方細節。

其他規範:IETF `draft-inadarei`(結構化 `{status, checks[]}`,非正式 RFC、已過期,de-facto 參考);
Spring Boot Actuator `/actuator/health`(`UP/DOWN` + components)。

→ **對照**:本專案 `main`(`/health` 查 DB)其實是 **readiness** 語意;indexer 的 `/healthz`
(degraded 時回 503,查 model+Qdrant)也是 **readiness** 語意,且 `HttpIndexerClient.healthz()` 已依賴此路徑。
**現代標準是 livez/readyz 分離**;但本專案**尚無 K8s / 容器編排在跑**(compose 只有 db/qdrant/embedder,api/web/indexer 跑在 host)。

### 2.5 降級 / 韌性:critical vs non-critical 是共識

- **AWS Well-Architected REL05-BP01**:把硬依賴轉軟依賴;**逐依賴分類 critical(fail)/ non-critical(degrade)**,non-critical 回快取/部分/空資料。
- **Google SRE**(《Cascading Failures》/《Handling Overload》):fail-fast 勝過 fail-slow(「5ms 的 503 勝過 30s 的 200」);load shedding。
- **Michael Nygard《Release It!》/ Martin Fowler**:circuit breaker——依賴持續掛時停止連續猛打、防級聯失敗。
- **dev.to graceful-degradation(2026)**:「每個整合應獨立失敗;別讓一個 client 的例外炸掉整個 handler」。

→ **對照**:現況分類**大致已對**(task-candidates/ocs-search 是 critical;header-meta/task-catalogs 是 enrichment)。
缺的是 **①顯性分類 + ②「部分資料」訊號 + ③(可選)circuit breaker**。CB 目前 YAGNI(單一 indexer、已有 timeout)。

---

## 3. 架構定位(hexagonal,ADR 0008)——這是維護者強調的重點

| 關注 | 屬於哪層 | 現況 | 該怎麼擺 |
|---|---|---|---|
| **wiring(掛 router/CORS/health)** | **composition root**(最外層入口) | 散在 main + live 兩份 | 收斂成**單一 wiring 點**;入口模組(main/live)只是薄殼 |
| **agent + deps 組裝** | composition root | 已在 `authoring/serving.py`(`build_live_deps`/`build_live_agent`)✓ | 維持;它是 agent 的組裝根 |
| **降級分類 critical/enrichment** | **application / use-case**(政策) | 隱性散在 route | 分類是 use-case 政策;HTTP 狀態碼映射(→502)是 delivery |
| **「回部分資料」** | **service / domain**(已優雅降級) | `header_meta.aggregate` 已能吃空 metas ✓ | 維持:service 產部分結果,route 決定 critical→raise |
| **HTTP 狀態映射** | **delivery adapter**(routes) | 各端點自理 | 收斂成薄 helper(delivery 關注 502 vs partial) |

**關鍵洞察**:F2 的 wiring 收斂 = **落實「single composition root」**(Seemann),完全對齊 hexagonal「入口是唯一組裝點」。
F1 的降級 = **service 優雅降級(回部分)+ delivery 映射狀態碼**,分層清楚,不把政策寫死在 route。

---

## 4. 選項比對

### F2-A wiring 收斂(擇一)

| 選項 | 做法 | 對齊 | 取捨 |
|---|---|---|---|
| **(a) 單一 `api_router` 聚合 + `configure(app)`**(推薦) | 新 `app/api/router.py` 聚合四 router;`configure(app)` 疊 CORS+health;main/live 各自 `configure(app)` | **Netflix Dispatch / zhanymkanov 主流**;Seemann single wiring | 改動最小、最 FastAPI-idiomatic;保留 global app;測試 import 不變 |
| (b) `create_app()` 工廠 | 抽工廠回傳 app;main/live/tests 都呼叫 | 泛用 production 部落格(**Flask 傳統**) | 每測試 fresh app;但 FastAPI 用 `dependency_overrides` 已達成,徒增 churn、非慣例 |
| (c) 只統一 health 路徑 | 不收斂 wiring,只把 `/health`→`/healthz` | — | 不解漂移根因,不推薦 |

### F2-B health 慣例(擇一)

| 選項 | 做法 | 對齊 | 取捨 |
|---|---|---|---|
| **(a) 統一 `/healthz` + DB 檢查**(短期推薦) | main/live 都 `/healthz`(查 DB) | 系統內部一致(indexer 也 `/healthz`);現有 README/client | 最少改動;但 `healthz` K8s 已 deprecated、語意籠統 |
| (b) `/livez` + `/readyz` | livez 不查依賴、readyz 查 DB | **K8s 現行標準 / 最新** | 語意最準、未來容器化即用;但目前無 K8s(YAGNI)、對外路徑變更 |
| (c) 先 (a)、留 (b) 為容器化時的 ADR | — | 兩全 | 記錄未來方向,不現在做 |

### F1 降級落實(擇一)

| 選項 | 做法 | 取捨 |
|---|---|---|
| **(a) 輕量:加 `meta.partial` + docstring 政策**(傾向) | header-meta/task-catalogs 降級時回 `meta.partial=true`;分類寫進 docstring;保留現有 per-code try/except | 行為幾乎不變(additive 欄位);不為重構而重構 |
| (b) 共用 `_indexer(critical=…)` helper | 收斂 try/except 樣板 | 一致性↑,但 per-code 迴圈本已清楚,收益有限 |
| (c) 加 circuit breaker | 依賴持續掛時短路 | YAGNI(單一 indexer + 已有 timeout);未來多依賴再說 |

---

## 5. 建議(待維護者拍板)

- **F2 wiring**:走 **(a) 單一 `api_router` 聚合 + `configure(app)`**——落實 Seemann single composition root,對齊 Netflix Dispatch/zhanymkanov,**不引入 Flask 式工廠**。main/live 變薄殼;live 保留自己的 checkpointer/copilotkit lifespan。
- **F2 health**:短期 **(a) 統一 `/healthz`**(系統內一致、改動最小);**(c) 開一則 ADR 記錄「容器化時遷 livez/readyz」** 為未來方向。
- **F2 demo app**:`copilotkit_app.py` 待決(刪→收斂成「1 wiring 點 + 1 live 殼」;需先查 `build_demo_agent` 無他用)。
- **F1**:走 **(a) 輕量 + `meta.partial`**;**circuit breaker 明確延後**(記在此)。
- 落實照紀律:F2、F1 各一份 `docs/plans/` bite-size;**move-only**、green-before==green-after;一 task 一 commit。
- 破壞面:health `/health`→`/healthz` 已查證**零外部消費者**(web 打 REST + `/copilotkit`;compose 無 api healthcheck;README 已載 `/healthz`)。

---

## 6. 來源(全權威:公認專家 / 大廠 / 官方 / 規範)

**Composition Root / DI / 架構**
- Mark Seemann,《Composition Root》 https://blog.ploeh.dk/2011/07/28/CompositionRoot/ · Seemann & van Deursen《Dependency Injection Principles, Practices, and Patterns》(Manning)
- Hexagonal Architecture(Alistair Cockburn)—— 本專案 ADR 0008

**FastAPI 結構(大廠 / 主流 / 官方)**
- zhanymkanov《FastAPI Best Practices》 https://github.com/zhanymkanov/fastapi-best-practices (inspired by Netflix Dispatch)
- Netflix Dispatch(FastAPI 實際大廠專案) · FastAPI 官方《Bigger Applications》 https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI 官方《Lifespan Events》 https://fastapi.tiangolo.com/advanced/events/ · Discussion #9397 / #10083(多 lifespan / AsyncExitStack)

**Health 端點(規範 / 官方)**
- Kubernetes《API health endpoints》 https://kubernetes.io/docs/reference/using-api/health-checks/ (healthz deprecated → livez/readyz)
- IETF `draft-inadarei-api-health-check`(de-facto,已過期) · Spring Boot Actuator Health

**降級 / 韌性(規範 / 大廠 / 專家)**
- AWS Well-Architected REL05-BP01 https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_graceful_degradation.html
- Google SRE《Addressing Cascading Failures》/《Handling Overload》 https://sre.google/sre-book/addressing-cascading-failures/
- Michael Nygard《Release It!》(circuit breaker 原始出處) · Martin Fowler《CircuitBreaker》 https://martinfowler.com/bliki/CircuitBreaker.html
