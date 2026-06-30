# API 審視 findings — indexer / 後端 api / web 三層

> **類型**:研究紀錄(findings + 建議,非決策)。各項落實前另開 ADR / plan。
> **日期**:2026-06-30
> **動機**:維護者要求在階段 2b 後做一輪跨層 API 審視(indexer 查詢 API、後端 api 端點、web 契約),
> 找不一致與可優化處,**深入研究**權威規範後產出建議清單。本輪**只研究、未改碼**。
> **原則**:對齊規範/主流/大廠(Google AIP、Microsoft / Zalando API guidelines、AWS Well-Architected、K8s)。

---

## 0. 端點面盤點

### 後端 api(`apps/api`,prefix `/api/v1`)
| 動詞 路徑 | 檔案 |
|---|---|
| POST `/users/` · GET `/users/{id}` | [users.py](../../apps/api/app/api/routes/users.py) |
| POST `/job-profiles/` · GET `/job-profiles/` · GET/PATCH/DELETE `/job-profiles/{id}` | [job_profiles.py](../../apps/api/app/api/routes/job_profiles.py) |
| GET/PATCH `/job-profiles/{id}/document` · POST `…/document/finalize` · GET `…/document/export` | [documents.py](../../apps/api/app/api/routes/documents.py) |
| POST `…/occupations` · GET `…/task-candidates` · POST `…/build-tasks` · GET `…/ocs-search` · GET `…/header-meta` · GET `…/ksa-pool` · GET `…/task-catalogs` | documents.py |
| POST `/ai/recommend-ks` · `/ai/draft-op` · `/ai/extract-tasks` · `/ai/structure-task` · `/ai/clarify` | [ai.py](../../apps/api/app/api/routes/ai.py) |

### indexer 查詢 API(`apps/ocs-indexer`)
| 動詞 路徑 | 風格 |
|---|---|
| POST `/occupations/search` · `/tasks/search` · `/tasks/batchGet` · `/tasks/findSimilar` | **slash + camelCase 自訂方法** |
| GET `/occupations/{ocs_code}` · `…/tasks` · `…/competencies` · `/stats` · `/healthz` | 資源式 REST |

### app 入口
- 正式:`copilotkit_live_app:app`([run_live.py:21](../../apps/api/run_live.py))→ `/healthz`。
- 測試:`app.main:app`([main.py:43](../../apps/api/app/main.py))→ `/health`。
- 另有 `copilotkit_app.py`(`/healthz`)。三個 app 模組各自 `include_router`。

---

## F1 —「依賴掛掉」失敗契約不一致(中高)

**現況**:同樣是 indexer 掛,行為兩套:
- **502**:`task-candidates`([documents.py:170](../../apps/api/app/api/routes/documents.py))、`ocs-search`([:237](../../apps/api/app/api/routes/documents.py))。
- **降級回空**:`header-meta`、`ksa-pool`、`task-catalogs`、`ai/*`(各自 try/except → 空)。

**權威**:AWS Well-Architected **REL05-BP01**「把硬依賴轉成軟依賴(graceful degradation)」——應**逐依賴分類 critical(fail)/ non-critical(degrade)**,non-critical 回快取/部分資料而非錯誤。

**方案比較(各權威做法,非二選一,是分層)**:
| 機制 | 來源 | 角色 / 何時用 |
|---|---|---|
| **timeout(必備)** | Google SRE;通用 | 每個網路呼叫都要;`HttpIndexerClient` 已有 `indexer_timeout_s` ✓ |
| **fail-fast(快錯 5xx)** | Google SRE「快錯勝過慢錯」 | **critical** 端點(`task-candidates`) |
| **graceful degradation / load shedding** | Google SRE《Cascading Failures》/《Handling Overload》 | **enrichment** 端點回部分/快取資料 |
| **circuit breaker** | Nygard《Release It!》(2007)、Netflix | indexer 持續掛時**停止連續猛打**、防級聯失敗(目前無) |

→ 結論:四者**分層互補**。現況缺的是 ① critical/enrichment **明確分類**、② 可選的 **circuit breaker**(避免 indexer 掛時每請求都 30s timeout)。

**建議**:明訂並文件化政策——
- **critical**(沒有它流程走不下去,如 `task-candidates`:選任務必須有候選)→ 5xx(快錯,讓前端顯示錯誤)。
- **enrichment**(缺了仍可編輯,如 `header-meta`/`ksa-pool`/`task-catalogs`)→ 降級回空 + 可選 `meta.partial` 旗標讓前端提示「部分資料暫缺」。
- 收斂成**共用 helper**(如 `call_indexer(..., critical: bool)`)統一行為。

**影響/風險**:低(行為大多維持,只把隱性政策顯性化 + 補一致性);`ocs-search` 若改降級需確認前端搜尋 UX。

---

## F2 — health 端點與 app 入口重複/漂移(中)

**現況**:正式 app `/healthz`、測試 app(`main.py`)`/health`,三個 app 模組各自掛 router → **路由集合可能漂移**(某端點只掛在其一),且測試打的是 `main.py`、正式跑的是 `copilotkit_live_app`,**測到的 app ≠ 跑的 app**(風險:正式入口某 wiring 沒被測到)。

**方案比較(路徑慣例 + 回應格式)**:
| 面向 | 選項 | 來源 | 取捨 |
|---|---|---|---|
| 路徑 | `/healthz` | K8s 舊慣例(**v1.16 已 deprecated**) | `z` 後綴避免路由衝突;但籠統 |
| 路徑 | `/livez` + `/readyz` | Kubernetes 現行 | 分「活著」vs「可服務(DB/indexer 可達)」,語意最準 |
| 路徑 | `/actuator/health` | Spring Boot Actuator | 業界主流、生態工具支援 |
| 回應 | 簡單 `200/503` | 通用 | 最簡,難表達細項 |
| 回應 | 結構化 `{status, checks[]}` | IETF **draft-inadarei**(*非正式 RFC、已過期但被廣參考*;審視過 K8s/Azure/Spring) | 可列各依賴狀態;indexer 的 `/healthz` 已接近 |
| 回應 | `UP/DOWN + components` | Spring Boot Actuator | 主流、含元件分解 |

→ 結論:現代慣例是 **livez/readyz 分離 + 結構化回應**;indexer 已回 `{status}` + 503(接近 readyz + inadarei)。後端兩 app 的 `/health`÷`/healthz` 該先**統一**,有餘力再對齊 livez/readyz。

**權威**:K8s——`/healthz` v1.16 已 deprecated,改 `/livez`+`/readyz`;`z` 後綴避路由衝突。

**建議**:
- **收斂 app 工廠**:抽一個 `create_app()` 真正單一來源 wiring,正式/測試共用(消除漂移、讓測試打到正式 app)。
- health 統一:至少統一路徑;若要對齊現代慣例可走 `/livez`+`/readyz`(readyz 檢 DB/indexer 可達)。indexer 的 `/healthz`(回 503 when degraded,[routes.py:111](../../apps/ocs-indexer/src/jd_ocs_indexer/api/routes.py))已接近 readyz 語意,可一併對齊。

**影響/風險**:低~中(app 工廠收斂要小心 router 不漏掛;health 改名屬對外路徑變更,但只 infra/compose 引用)。

---

## F3 — indexer 自訂方法命名非慣例(中,破壞性)

**現況**:`/tasks/batchGet`、`/tasks/findSimilar`、`/tasks/search`、`/occupations/search` 用 **slash + camelCase**,與資源式 GET(`/occupations/{code}/competencies`)混風格。`batchGet` 用 slash 會讓它**看起來像名為 batchGet 的子資源**。

**權威**:
- **Google AIP-136(自訂方法)/ AIP-231(BatchGet)**:自訂/批次方法 URI 用 **`:verb`**(冒號),如 `/tasks:batchGet`、`/tasks:search`;冒號標示「對集合的操作」而非子資源。優先用標準方法,custom 僅在無法乾淨對映時。
- **Microsoft REST guidelines**:URL path 用 **kebab-case**(JSON 欄位才 camelCase)→ camelCase 出現在 path segment 不符。
- **Zalando**:path 一律 kebab-case。

**方案比較(各家如何處理 search / batchGet)**:
| 做法 | 誰用 | 適用 / 取捨 |
|---|---|---|
| `GET /tasks?q=&top_k=`(query param) | Microsoft/Zalando 標準 List+filter;Stripe list;Elasticsearch `q=` | **簡單查詢**、可快取、冪等;入參少時最佳 |
| `:search` 自訂方法(POST body) | Google AIP-136;Elasticsearch `_search`(POST DSL) | **複雜查詢**(body 帶結構);不可快取 |
| `POST /tasks:batchGet`(body `{ids}`) | Google AIP-231;Stripe(POST body)| **ids 多/超 URL 長度** → POST 合理;命名用 `:batchGet` |
| `GET /tasks?ids=a,b,c` | 部分 REST | ids 少時可快取;多了爆 URL 長度 |

→ 結論:**動詞(POST/GET)其實大多合理**(batchGet 用 POST 因 ids 可能多;search 入參簡單則可 GET),**問題在命名**——`/tasks/batchGet`、`/tasks/findSimilar` 的 **slash+camelCase** 不符 Google(`:verb`)/ Microsoft(path kebab)/ Zalando。

**建議**(擇一、求一致):
- (a) **Google 風(推薦,改動最小)**:slash → 冒號 + 動詞不變:`/tasks:batchGet`、`/tasks:search`、`/tasks:findSimilar`、`/occupations:search`。
- (b) **RESTful**:`search` 簡單入參 → `GET /tasks?q=&top_k=`、`GET /occupations?q=`;`batchGet` 維持 `POST /tasks:batchGet`;`findSimilar` → `POST /tasks:findSimilar`。
- (c) 維持 slash 但**全 kebab**:`/tasks/batch-get`、`/tasks/find-similar`(仍把動作當子資源,**最不推薦**)。

**影響/風險**:**破壞性**——動到 indexer 路由 + `indexer-contract` 客戶端 + 後端 `HttpIndexerClient`。需照 `docs/contract-strategy.md` 協調改、版本對齊。建議與 F4 合併成一次「命名對齊」ADR。

---

## F4 — 後端 noun/verb 命名混用(中,部分破壞性)

**現況**:`documents` router 混**名詞資源**(`/document`、`/header-meta`、`/task-candidates`、`/task-catalogs`、`/ksa-pool`)與**動作**(`/build-tasks`、`/ocs-search`、`/document/finalize`)。`ai` router 全動詞(`/recommend-ks`…)。

**權威**:**Google AIP-121**(資源導向:名詞資源 + 少量標準方法)+ **AIP-136**(動作用 `:verb`);Microsoft/Zalando kebab-case。AI「提議」端點屬 stateless RPC,verb 命名可接受,但宜統一表達為動作。

**建議**:
- `…/document/finalize` → `…/document:finalize`(AIP 自訂方法)。
- `…/ocs-search` → `GET …/occupations?q=`(標準 List + filter)或 `…/occupations:search`。
- `…/build-tasks` → `…/document:buildTasks` 或保留(屬明確動作)。
- `ai/*` 維持(提議型 RPC),但文件標明這是刻意的 action-style。
- kebab-case 一致(現多已 kebab)。

**影響/風險**:破壞性(URL 改 → web client + 任何呼叫端)。建議與 F3 同一輪命名 ADR + codegen/型別一起改。**維護者已授權命名調整(但要研究先行,本文件即研究)。**

---

## F5 — `POST /{id}/occupations` 語意應為 PUT(低)

**現況**:[set_occupations](../../apps/api/app/api/routes/documents.py)(POST)其實是**整批取代** `selected_ocs_codes`(冪等)。

**權威**:REST 方法語意——**冪等的整體取代用 PUT**;POST 留給非冪等建立/動作。

**建議**:改 `PUT …/occupations`(body `{ocs_codes:[...]}`)。**影響**:小;web client 一行改。

---

## F6 — 批次端點無分頁(低,YAGNI)

**現況**:`task-catalogs`、`ksa-pool`、`header-meta` 全量回。

**權威**:Zalando/Microsoft——集合端點應支援分頁;但**YAGNI**:目前單文件規模小、唯讀可快取(ADR 0016 已記)。

**建議**:現階段不動;規模成長(大 OCS / 多職類)再加 cursor 分頁。**先記錄,不行動。**

---

## F7 — `ksa-pool` 與 `task-catalogs` 概念重疊、命名未表關係(低)

**現況**:`ksa-pool`=profile 全域 K/S/A 聯集;`task-catalogs`=per-task K/S/O/P+level。兩者皆源自 `competencies` 池,命名沒表達「全域 vs 逐任務」。

**建議**:命名語意化(如 `competency-pool`(全域)vs `task-catalogs`(逐任務));或文件標明關係。低優先,可併入 F4 命名輪。

---

## 建議落實順序(各自 ADR/plan、bite-size、move-only)

1. **F1 降級政策一致化** + **F2 app 工廠收斂/health 統一** — 低風險、高清晰度,**先做**(且 F2 收斂讓「測試打到正式 app」,提升後續安全網)。
2. **F3 + F4(+F7)命名對齊** — 一次「API 命名 ADR」涵蓋 indexer + 後端,破壞性、需契約協調 + codegen,**獨立規劃**。
3. **F5 PUT** — 小,可順手併入某輪。
4. **F6** — 記錄、暫不行動。

> 破壞性項(F3/F4/F5/F7)務必照 `docs/contract-strategy.md` 選機制、api client + web 同步、green-before==green-after。

---

## 來源(全權威:標準機構 / 大廠 / 公認專家)

**API 命名 / 資源設計**
- [Google AIP-121 資源導向設計](https://google.aip.dev/121) · [AIP-136 自訂方法(`:verb`)](https://google.aip.dev/136) · [AIP-231 BatchGet](https://google.aip.dev/231) · [AIP-190 命名](https://google.aip.dev/190)
- [Microsoft Azure REST API Guidelines(path kebab-case / JSON camelCase)](https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md) · [Zalando RESTful API Guidelines](https://opensource.zalando.com/restful-api-guidelines/)

**search / batch 各家做法**
- [Elasticsearch Search API(GET `q=` vs POST body DSL)](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-search.html) · [Stripe API(GET list+filter / POST body)](https://docs.stripe.com/api)

**韌性 / 降級 / 熔斷**
- [AWS Well-Architected REL05-BP01 graceful degradation](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_graceful_degradation.html)
- [Google SRE Book — Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/) · [Handling Overload](https://sre.google/sre-book/handling-overload/)
- Michael T. Nygard,《Release It!》(circuit breaker 原始出處,2007)

**health 端點**
- [Kubernetes API health endpoints(healthz 已 deprecated → livez/readyz)](https://kubernetes.io/docs/reference/using-api/health-checks/)
- [IETF draft-inadarei「Health Check Response Format for HTTP APIs」](https://datatracker.ietf.org/doc/html/draft-inadarei-api-health-check-06)(*非正式 RFC、已過期,僅作 de-facto 參考*) · [Spring Boot Actuator Health](https://docs.spring.io/spring-boot/reference/actuator/endpoints.html)
