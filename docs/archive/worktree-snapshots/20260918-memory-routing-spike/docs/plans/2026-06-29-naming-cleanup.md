# 命名整理執行計畫 — Caliburn rename / 去版號 / 去 jobintel

> 決策見 [ADR 0013](../adr/0013-naming-cleanup-caliburn.md);研究見 [`../specs/2026-06-29-naming-conventions-research.md`](../specs/2026-06-29-naming-conventions-research.md)。
> 紀律:**每 task 一 commit**、move-only 為主、**green-before == green-after**、不動 archive/歷史 spec/golden。

**安全網(各 app 綠燈門檻)**
- api:`cd apps/api && uv run pytest -q`
- web:`cd apps/web && npx tsc --noEmit && npm run lint`
- 跑前先記基線(目前全綠),改後數量/結果一致才算過。

---

## T1 — 品牌 + npm scope
**Files**
- `apps/web/package.json`:`"name": "frontend"` → `"@caliburn/web"`
- `apps/web/src/app/layout.tsx`:title `"JobIntel AI"` → `"Caliburn"`
- `apps/web/src/app/dashboard/page.tsx`:`<span>JobIntel AI</span>` → `Caliburn`;刪 `<Badge …>v3</Badge>`
- `apps/api/app/config.py`:`app_name = "JobIntel AI"` → `"Caliburn"`
- `apps/api/app/copilotkit_app.py`:title `"jobintel v3 CopilotKit demo"` → `"Caliburn CopilotKit demo"`
- `apps/api/app/copilotkit_live_app.py`:title `"jobintel v3 (live)"` → `"Caliburn (live)"`

**Steps**:改字串 → `npm install`(根,重生 lockfile 的 `@caliburn/web` 條目)→ web tsc+lint → api `uv run pytest -q`(import 不破)→ commit `chore: rename web package + brand to Caliburn`。

## T2 — 去 jobintel 字串(logging + persist key)
**Files**
- `apps/api/app/**`:`logging.getLogger("jobintel")` → `"caliburn"`(utils、adapters/persistence、adapters/llm_openrouter、graph_v3/build_doc、graph_v3/curate_nodes、graph_v3/deep_nodes、api/routes/ai、api/routes/documents 等 ~8 處)
- `apps/web/src/store/user.ts`:persist `{ name: "jobintel-user" }` → `"caliburn-user"`

> 註:OTel 命名空間(tracing.py 的 `jobintel*`)留到 **T3** 一起改(同檔在套件搬移範圍內)。

**Steps**:全域取代 logger 名 → api pytest → web tsc → commit `chore: rename logging/storage namespace jobintel→caliburn`。

## T3 — api 去版號 `graph_v3` → `authoring`
**Files / 動作**
- `git mv apps/api/app/graph_v3 apps/api/app/authoring`
- 全 api 取代 `app.graph_v3` → `app.authoring`(serving、build_doc、graph、nodes、curate_nodes、deep_nodes、tracing、deps;外部 importer:copilotkit_app、copilotkit_live_app、adapters/llm_openrouter、run_live、scripts/live_smoke、evals/run_eval;`core/ports.py`/`adapters/stubs.py` 註解)
- `build_graph_v3` → `build_graph`(`graph.py` 定義 + serving.py + 各 test)
- `apps/api/app/authoring/tracing.py`:`service.name "jobintel-v3"`→`"caliburn"`、`get_tracer("jobintel.graph_v3")`→`"caliburn.authoring"`、`span.set_attribute("jobintel.node"/"jobintel.current_step")`→`"caliburn.*"`
- 測試改名:`git mv` `test_graph_v3_e2e.py`→`test_graph_e2e.py`、`test_graph_v3_full_e2e.py`→`test_graph_full_e2e.py`、`test_graph_v3_deep_loop.py`→`test_graph_deep_loop.py`、`test_graph_v3_spans.py`→`test_graph_spans.py`、`test_state_v3.py`→`test_state.py`;內部 import 改 `app.authoring.*`、`build_graph`
- `tests/test_old_chain_removed.py`:lines 6–7(`app.graph.*` 已移除)**保留**;line 24–26 的 `app.graph_v3.*` 改 `app.authoring.*`、函式名 `…lives_in_authoring`

**Steps**:搬移+取代 → `uv run pytest -q` 全綠(數量==基線)→ commit `refactor(api): drop version suffix, graph_v3→authoring`。

## T4 — web 去版號 `/v3` → `/documents`
**Files / 動作**
- `git mv apps/web/src/app/v3 apps/web/src/app/documents`(含 `[id]/page.tsx`、`[id]/intake/page.tsx`)
- `git mv apps/web/src/components/interview/v3/<each>` → `apps/web/src/components/interview/`(整層上移)
- 取代 import `@/components/interview/v3/` → `@/components/interview/`(documents/page.tsx、intake/page.tsx、元件間互引)
- 取代 `router.push(\`/v3/${…}\`)` → `/documents/${…}`(dashboard ×2、documents/[id]/intake ×1)
- 註解去 v3:`types/index.ts`、`lib/api.ts`、`dashboard/page.tsx` 文案(「v3 訪談」→「訪談」等)

**Steps**:搬移+取代 → web `npx tsc --noEmit && npm run lint`,`npm run build`(路由可建)→ commit `refactor(web): drop /v3 route → /documents, flatten interview components`。

## T5 — DB + docker 命名(資料面)
**Files / 動作**
- `docker-compose.yml`:移除 `db`/`qdrant`/`embedder` 的 `container_name`;`POSTGRES_DB: jobintel` → `caliburn`;更新 `embedder`/註解裡的舊容器名提及
- `apps/api/app/config.py`:`database_url`/`database_url_sync` 的 `/jobintel` → `/caliburn`
- `apps/api/.env.example`:`DATABASE_URL*` 的 `/jobintel`→`/caliburn`;首行註解 `(v3)` 拿掉、`jobintel_db` 提及更新

**重建(只清 Postgres,保留 qdrant 的 ocs_v4)**
```bash
docker compose -p caliburn -f S:\caliburn\docker-compose.yml stop db
docker compose -p caliburn -f S:\caliburn\docker-compose.yml rm -f db
docker volume rm caliburn_pgdata          # 只刪 PG 資料卷；qdrant_storage 不動
docker compose -p caliburn -f S:\caliburn\docker-compose.yml up -d db   # 以 POSTGRES_DB=caliburn 重新 init
npm run db:migrate                        # alembic upgrade head 到新 caliburn 庫
```
**Verify**:`docker ps`(容器名變 `caliburn-db-1` 等)、api 連得上新庫(`uv run pytest -q` 綠 or run_live 起得來)→ commit `chore: rename db jobintel→caliburn, drop container_name`。

## T6 — 文件 + tag
**Files**:`CONTRIBUTING.md`、`docs/runbook.md`、`docs/README.md`、`apps/api/README.md`、`apps/ocs-indexer/README.md`(若提及 `/v3`/`graph_v3`/`jobintel_*`/舊埠)、`docs/adr/README.md`(加 0013 列)、`CLAUDE.md`(本地、不版控,但更新求準)。**不動** archive、歷史 spec、golden。
**Steps**:更新引用 → 快速掃連結 → commit `docs: update references after Caliburn rename` → `git tag rename-caliburn`。

---

### 風險 / 回滾
- 各 task 獨立 commit → 出錯 `git revert` 該 commit 即可。
- T5 是唯一動資料的:僅刪 `caliburn_pgdata`(新空庫,使用者已同意);**qdrant `ocs_v4` 全程不碰**。
- OTel `service.name`/persist key 改名 → trace 連續性 / 本機 UI 偏好重置(早期、可接受,ADR 0013 已記)。
