# ADR 0013 — 命名整理:web 改 Caliburn、內部去版號、容器/DB 去 jobintel

- **狀態**:Accepted（2026-06-29）。
- 研究依據:[`../specs/2026-06-29-naming-conventions-research.md`](../specs/2026-06-29-naming-conventions-research.md)。

## 脈絡

專案早已從 `jobintel` 更名為 `caliburn`,但命名留下三類不一致:① web npm 套件仍叫 `frontend`、品牌字串仍是「JobIntel AI」;② 容器名 `jobintel_*`、`POSTGRES_DB=jobintel`、logger/OTel 命名空間仍是 `jobintel`;③ 純內部程式碼帶版本號(`app/graph_v3`、web `/v3` 路由、`components/interview/v3`)。

權威依據(見研究紀錄):**npm** 官方—`@scope/name`、套件名≠資料夾名;**Docker** 官方—Compose 以 project 名前綴自動命名(`<project>-<service>-<n>`),`container_name` 會綁單機單實例,非必要不寫死;**Google/Apigee(Martin Nally)+ REST 版本化共識**—版本號屬於**外部契約面**(URL major / header),不綁 build、不過早版本化 → 推論:**純內部模組名不該帶版本號**。

## 決定

**A. 品牌 + scope**:`apps/web` 套件 `frontend` → `@caliburn/web`(目錄不改);品牌顯示名「JobIntel AI」→ **「Caliburn」**(web `<title>`、dashboard header、api `app_name`、CopilotKit app titles);移除 dashboard 的 `v3` UI 徽章。

**B. 去 jobintel(內部)**:logger `getLogger("jobintel")` → `"caliburn"`;OTel `service.name "jobintel-v3"`→`"caliburn"`、tracer `"jobintel.graph_v3"`→`"caliburn.authoring"`、attr `jobintel.*`→`caliburn.*`;zustand persist key `jobintel-user`→`caliburn-user`。

**C. 容器命名**:移除 `db`/`qdrant`/`embedder` 寫死的 `container_name`,改用 Compose project 前綴自動名(`caliburn-db-1` 等);**service 名不變**(role-based)。

**D. 去版號(內部碼;保留資料契約版本)**:
- api `app/graph_v3/` → **`app/authoring/`**;`build_graph_v3()`→`build_graph()`。**不取名 `graph`**——`app.graph`(`app.graph.graph`/`app.graph.nodes.ocs_builder`)是**已退役舊鏈**的命名空間,`tests/test_old_chain_removed.py` 仍在守它消失;`authoring` 是本 context 的 domain 名(ADR 0002「著作」)。
- web `app/v3/[id]/`(含 `/intake`)→ **`app/documents/[id]/`**;`components/interview/v3/` → `components/interview/`。
- **保留** Qdrant collection `ocs_v4`——那是真正的**資料格式/外部契約**版本,符合「版本只放契約面」。
- **不改名**:`docs/archive/`、日期化歷史 spec(`*-v3-*.md`、`schema-v3-design.md`…,改=竄改歷史)、golden fixtures。

**DB**:`POSTGRES_DB` 與 `database_url` 的 `jobintel`→`caliburn`,**重建空 `caliburn` 庫**(只清 `caliburn_pgdata` volume + `alembic upgrade head`;**qdrant 的 `ocs_v4` 不動**)。現有本機 `jobintel` 資料不遷移(使用者選 fresh)。

## 後果

- ✅ 命名一致(scope/品牌/專案);內部碼不再帶版本號(對齊 Google/Apigee);容器/DB/logging 不再references舊專案名。
- ✅ 語意更清楚:`authoring` 直述職責,勝過帶版本的 `graph_v3`。
- ⚠️ URL 從 `/v3` 改 `/documents`——僅 dev、無外部消費者,可接受;舊書籤失效。
- ⚠️ OTel `service.name` 改名 → 與舊 `jobintel-v3` 的 trace 連續性中斷(早期、可接受);persist key 改名 → 本機 UI 偏好重置(dev)。
- ⚠️ DB 為**全新空庫**;qdrant `ocs_v4` 保留。
- 📌 收尾 tag `rename-caliburn`。執行計畫見 [`../plans/2026-06-29-naming-cleanup.md`](../plans/2026-06-29-naming-cleanup.md)。
