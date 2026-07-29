# api — Caliburn 後端(FastAPI + 訪談引擎)

「著作」bounded context 的後端。提供 REST `/api/v1/*`(含訪談引擎 `interview:*`)。
擁有 **Postgres**(users/job_profiles/document_versions + interview_*);知識一律
透過 HTTP 消費 `ocs-indexer`,**不碰 Qdrant**(資料主權,見根 [`ARCHITECTURE.md`](../../ARCHITECTURE.md))。
既有 production AI 共編端到端（v3）見 [`docs/design/interview-engine.md`](../../docs/design/interview-engine.md)。
新的專業顧問 Task Analysis 引擎位於 `app/job_analysis/`，是與既有 `interview`／`interview_vnext`
隔離的 greenfield 工作面；目前已完成 in-memory scripted vertical，**尚未接 DB、route 或 Web**，
端到端邊界見 [`docs/design/task-analysis-engine.md`](../../docs/design/task-analysis-engine.md)。
`interview_vnext` 仍是歷史隔離開發線，不是新引擎的依賴。

- **import 套件名**:`app`(Phase 3 才改 `caliburn_api`;現由 `pytest.ini` 的 `pythonpath=.` 提供)。
- **uv application 模式**(無 build-system,[ADR 0005](../../docs/adr/0005-per-app-uv-defer-workspace.md))。

## 跑 / 測試

```bash
uv sync
docker compose up -d db            # 需 Postgres(:5432)
uv run python run_live.py          # :8001(Windows 用 SelectorEventLoop,已內建;reload 已關)
# 或從 monorepo 根:npx turbo dev
uv run pytest -q                   # 無 DB 時 DB 相關測試自動 skip
```

健康檢查:`GET /healthz`(含 DB readiness;ADR 0017)。知識查詢需另起 indexer + embedder
(見 [`docs/runbook.md`](../../docs/runbook.md))。新增依賴:改 `pyproject.toml` + `uv lock`。

**單一入口,單一組裝點**(T12 後):tests 與 production 都是 `app.main`
(`run_live.py` 直起 `app.main:app`),經 `app_factory.configure()` 這個
**composition root** 掛 tracing/router/CORS/health,wiring 不會漂移(ADR 0017/0030)。

## Codemap(六邊形,ADR 0008)

| 路徑 | 是什麼 | 依賴方向 |
|---|---|---|
| `app/core/` | **純內圈**:`ports.py`(KnowledgePort/PersistPort/LlmPort Protocol)、`domain/ocs_doc.py`(OCS 文件純函式:skeleton/assemble_final/validate/completion)、`domain/knowledge_pack.py`(知識包組裝,ADR 0021)、`knowledge_dto.py`(re-export [`packages/indexer-contract`](../../packages/indexer-contract/)) | 不 import 任何外圈 |
| `app/adapters/` | 邊緣實作:`knowledge_http.py`(indexer typed client)、`persistence.py`(ProfileRepo/DocRepo/LiveDbPersist)、`llm_openrouter.py`(per-role LLM + JSON 重試)、`stubs.py`(測試/demo 假件) | 實作 ports |
| `app/services/` | use-case 純函式:`ai/`(recommend_ks/draft_op/extract_tasks/structure_task/clarify + prompts)、`knowledge/task_detail.py`(池→單任務切片) | 只吃 ports/DTO |
| `app/interview/` | **既有 production 訪談引擎**(ADR 0030):`consultant.py`(對話+READ 工具)、`scribe.py`(op 化+落 `_pending`)、`verify.py`(六查,blocking)、`ledger.py`(覆蓋帳本)、`backstop.py`(確定性 sweep)、`skills/`(判準教材 8 檔+`skill_loader.py`)、`service.py`(回合編排) | 吃 ports;既有寫入路徑 op→verify→`_pending` |
| `app/job_analysis/` | **現行 greenfield Task Analysis 工作面**(ADR 0040／0042):Task／Proposal／Context／one-stage operation／deterministic verifier／in-memory transition | 不 import `interview`、`interview_vnext`、`job_authoring`、DB 或 Web；尚未進 production composition root |
| `app/interview_vnext/` | **隔離開發中的 greenfield vNext**（ADR 0034）：V1 domain lifecycle + V2-A provider-neutral LLM/Capture contracts/in-memory fakes/共 33 schemas 已完成；無 route、DB、live LLM | 不 import v3 internals；SDK只准在未來 provider adapter；production composition root 不 import此 package |
| `app/observability.py` | OTel tracing 橫切(gen_ai.* 手埋;verify 拒收/審閱事件 span) | — |
| `app/api/` | HTTP 面:`routes/{users,job_profiles,documents,occupations,ai}.py`、`router.py`(唯一聚合點)、`deps.py`(get_knowledge) | 薄轉接,邏輯下沉 |
| `app/app_factory.py` | composition root:`configure()` 掛 router/CORS/healthz | — |
| `app/{config,database,models,schemas}.py` | Settings(.env)/engine/ORM 三表/pydantic in-out | — |

## 資料模型(Postgres,Alembic 管 schema)

```
users ─1:N─ job_profiles ─1:N─ document_versions
```

- `job_profiles.selected_ocs_codes`(ARRAY):已選職類,順序=優先度。
- `document_versions`:**version = 文件世系**(finalize/重建才 +1,INSERT 新列)、
  **revision = 同一列的編輯回合**(SQLAlchemy `version_id_col`,每次 UPDATE 自動 CAS +1)。
  雙 token 構成 PATCH 樂觀鎖(ADR 0015)。`content` = 整份 OCS JSON(JSONB,draft 含 `_` UI 欄位)。

## REST 端點 reference(`/api/v1`)

依賴降級政策(ADR 0018):**critical** = indexer 掛 → 502 快錯;**enrichment** = 略過壞的部分
→ 200 + `meta.partial=true`。

| Method Path | 用途 | indexer |
|---|---|---|
| `POST/GET /users…`、CRUD `/job-profiles…` | 匿名使用者 + 職務檔案(list 附 doc_status/completion) | — |
| `GET /job-profiles/{id}/document` | of-record 信封;無文件回 `status:"none"` 空殼 | — |
| `PATCH …/document?expect_version=&expect_revision=` | 存草稿(整份文件);token 不符 → **409** + current token;不帶=不守衛(legacy) | — |
| `POST …/document:finalize` | 組裝+驗 schema(失敗 422)→ INSERT 新 final 列 | — |
| `GET …/document/export` | 唯讀匯出乾淨契約 JSON(剝 `_` 欄位,不寫 DB) | — |
| `PUT …/occupations` | 整批取代**參考集合**(`selected_ocs_codes`;0029 脫鉤:只寫 profile、不動文件表頭——主基準由前端職類視窗 PATCH) | — |
| `GET …/knowledge` | **知識包**(ADR 0021):occupation_details + 12 池 + source_tasks,每官方值帶 srcs——web 所有選單的唯一資料源。**含 `similarity`**(ADR 0022:態度/任務兩池丟 indexer `items:match`,回應**原樣掛上**,api 不拆包不選代表;輸入由 `knowledge_pack.similarity_items` 純函式組) | 單掛 partial/**全掛 502**;match 掛→缺該 kind + `meta.similarity: ok\|partial\|unavailable`(enrichment) |
| `GET /occupations?q=` | 根層職類目錄搜尋(全域知識,不掛 profile 下;ADR 0019) | **critical** |
| `POST /ai/{recommend-ks,draft-op,extract-tasks,structure-task,clarify}` | **只提議、不寫 DB**;無金鑰→降級回 catalog/空 | enrichment |
| `POST …/interview:start` | 訪談 session 建/續(**冪等**;空白文件也可起跑,顧問開場引導選職類) | — |
| `POST …/interview:turn` `{text}` | 一回合(v3):顧問先說話→喚醒閘→書記 op→verify→`_pending`→backstop sweep;回 `suggest_finish`。無 LLM→503;受限解碼失效→**502**(0024 保險絲) | — |
| `POST …/interview:finish` | 收尾對帳(T10):態度綠標落地+結構化總結回讀→phase=review | — |
| `GET …/interview` | session 全貌:逐字稿+議程三態 `agenda[]`+`pending_count`——續談與稽核視圖 | — |
| `POST …/interview:review-events` `{events}` | ✓/✗/批量的**無聲記帳**(不觸發 AI;文件變換由前端執行) | — |
| `GET /healthz` | 就緒(含 DB) | — |

## 關鍵流程

### 1. 文件 of-record 生命週期

```
GET(無文件)→ status:"none" 空殼(version 0, revision 0)
PATCH / PUT occupations → upsert_draft:
   最新列是 draft → 原地更新 content(version 不變,revision 自動 +1)
   否則           → INSERT 新 draft(version+1,revision 從 1 起)
finalize → assemble_final(補全+剝 `_`)→ validate → INSERT 新 final 列(version+1)
```

樂觀鎖:應用層先比 (expect_version, expect_revision),不符 raise → 409;同毫秒競態由
`version_id_col` 的 CAS 兜底(StaleDataError → rollback → 409)。

### 2. 選職能基準參考(PUT occupations;0029/0031)

只寫 profile 的 `selected_ocs_codes`(無序參考集合)——**不動文件**。文件表頭主基準由
前端職類視窗 PATCH 寫入。**訪談引擎的有效參考碼=profile∪文件碼**(0031 不變量:
只看文件會對已選參考視而不見)。任務待前端任務盤/選單選入(編輯文件 + PATCH)。

### 3. 知識包組裝(ADR 0021)

選職類後 web 抓一次 `GET …/knowledge`:per-code **並行**抓 indexer 三資源(detail/tasks/
competencies)→ `core/domain/knowledge_pack.build_pack` 純函式**照優先序組裝**——池(append 序
+ key 去重 + srcs 累積;key 表見 spec §5.1)+ `source_tasks`(任務 URN byId,掛 o/p/k/s_refs)。
此後 web 對 knowledge 零請求(特殊功能除外:`/occupations?q=`、`/ai/*`)。舊三投影端點
(header-meta/task-candidates/task-catalogs)與 `document:buildTasks` **已隨 web 切換完成退役**
(P3):web 讀包、寫入一律走 PATCH。

### 4. AI 提議降級鏈(D28)

`有 note + 有金鑰 → LLM 篩選/草擬(錯誤/空回 → fallback)→ 官方 catalog → 空`。
路由層薄:載文件→定位任務(provenance)→委派 `services/ai/` 純函式,同邏輯供未來訪談 agent 重用。

## 不變量

- **core 不 import 外圈**(adapters/interview/fastapi);違反=架構回歸(ADR 0008)。
- **`/ai/*` 永不寫 DB**:提議由前端套用後走 PATCH(read-only 純函數;**不是**共編路徑)。
- **文件寫入只有三條路**:PATCH(使用者編輯,含 ✓/✗ 去標還原)、finalize(產正式版)、
  **書記 op→verify→`_pending`**(AI 唯一寫入;ADR 0030)。PUT occupations 只寫 profile
  參考集合、**不動文件**(0029/0031)。knowledge 池端點**唯讀**,重選參考不會洗掉使用者編輯。
- **表頭官方名絕不退回使用者 job_title**(indexer 掛就留空)。
- **draft 寬鬆、final 嚴格**:PATCH 不驗 schema,finalize 才 assemble+validate(422)。
- LLM 無金鑰 → `llm=None` 全鏈優雅降級,不發注定失敗的呼叫。

## 指路

**內部深文檔(改對應子系統前先讀)→ [`docs/`](docs/)**:`build_pack` 組包、`ocs_doc`(finalize gate)、
AI 提議鏈;**訪談引擎端到端 → [`docs/design/interview-engine.md`](../../docs/design/interview-engine.md)**。

ADR [0008](../../docs/adr/0008-api-hexagonal-layering.md)(六邊形)·
[0015](../../docs/adr/0015-document-save-optimistic-concurrency.md)(樂觀鎖)·
[0016](../../docs/adr/0016-batch-task-catalog-endpoint.md)·
[0017](../../docs/adr/0017-app-entry-single-composition-root.md)(組裝點)·
[0018](../../docs/adr/0018-indexer-dependency-degradation-policy.md)(降級)·
[0019](../../docs/adr/0019-api-naming-alignment.md)(命名)·
契約:[`packages/indexer-contract`](../../packages/indexer-contract/)(indexer DTO 權威)、
[`docs/ocs-schema.md`](../../docs/ocs-schema.md)(OCS 文件結構)。前端消費視角見
[`apps/web/README.md`](../web/README.md)。
