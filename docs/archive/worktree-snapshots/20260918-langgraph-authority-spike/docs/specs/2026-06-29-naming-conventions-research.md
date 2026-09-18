# 命名規範研究紀錄 — web 改名 / v3→v4 / docker 命名

> **類型**:研究紀錄(findings,非決策)。決策見後續 ADR。
> **日期**:2026-06-29
> **動機**:三件命名整理 —(1) web 改成專案名、(2) 把殘留的 `v3` 處理掉、(3) docker pgvector 等容器改名。原則:**符合規範 / 主流 / 大廠 / 資深人物**的命名慣例,不憑感覺。

## 1. 現況盤點

| 命名域 | 現況 | 問題 |
|---|---|---|
| web npm 套件名 | `apps/web/package.json` = `"frontend"` | 與 `@caliburn/api`、`@caliburn/ocs-contract` 不一致,**唯一沒掛 scope 的內部套件** |
| web 品牌顯示名 | `layout.tsx` title=`"JobIntel AI"`;api `config.py` `app_name="JobIntel AI"` | 還是舊產品名 |
| 版本號 `v3` | api `app/graph_v3/`(~30 檔 + `test_graph_v3_*`/`test_state_v3` + OTel span 名);web `app/v3/[id]/`(URL `/v3/`)+ `components/interview/v3/` | 純內部程式碼帶版本號 |
| 版本號 `v4`(資料) | Qdrant collection `ocs_v4`;`*-api-v4-*` 計畫 | 合理(資料/契約版本),非問題 |
| docker 容器 | service `db`/`qdrant`/`embedder`;`container_name: jobintel_db`/`jobintel_qdrant`/`jobintel_embedder`;`POSTGRES_DB=jobintel` | 容器名與 DB 名仍是舊專案名 `jobintel`(embedder image 已是 `caliburn-embedder`) |
| 歷史文件檔名 | `apps/ocs-indexer/docs/.../2026-06-14-v3-*.md`、`schema-v3-design.md` 等 | **日期化歷史紀錄,不該改名**(改=竄改歷史) |

## 2. 權威發現

### 2.1 npm 套件命名(npm 官方)
- 格式 `@scope/name`,小寫;**「套件名」與「資料夾名」可不同、且不需同步**。monorepo 慣例:內部套件一律掛同一 scope 以避免衝突、表明歸屬。
- → `frontend` 應改 `@caliburn/web`;**`apps/web` 目錄可不必改**(目錄名 ≠ 套件名)。

### 2.2 Docker Compose 容器命名(Docker 官方 + 社群)
- Compose 用 **project name** 隔離環境並**前綴所有資源**;預設容器名 = `<project>_<service>_<index>`(如 `caliburn-db-1`)。project name 限小寫/數字/`-`/`_`。
- service 名用 **role-based 小寫**(`db`/`cache`/…)。
- `container_name` 會**蓋掉自動命名,且使該 service 只能單機單實例**(名稱必須唯一)→ 主流建議:**非必要不要寫死 `container_name`**,優先用 project 前綴的自動名;若真需要固定名(對外 DNS/腳本引用),也應**加 project 前綴**。
- → 現行 `jobintel_*` 是舊 project 名殘留,與專案 `caliburn` 不一致。

### 2.3 程式碼/模組名中的版本號(Google Cloud / Apigee — Martin Nally;REST 版本化共識)
- 版本號屬於**外部契約面**:entity 版本放 URL、format 版本放 HTTP header(`Accept-Version`)。
- **只用 major 版本**(v1/v2 代表破壞性變更);minor/patch 放進對外 URL 是 anti-pattern。
- **API 自管版本,獨立於 build number**;**不要過早版本化**;**不要把支援狀態(alpha/beta)塞進版本 ID**。
- → 推論(套到內部程式碼):**內部模組名不該帶版本號**。working tree 就是「當前版本」,歷史交給 git;`graph_v3` 這種**純內部** Python 套件帶 `_v3` 不符規範。`ocs_v4`(Qdrant collection 的資料格式版本)是**真正的外部/資料契約版本**,保留合理。web 的 `/v3/` 是改寫遺留、**並非維護中的多版本 API 面**。

## 3. 對應建議(三個命名域)

- **A. web 品牌 + 套件**:`frontend` → `@caliburn/web`(目錄留 `apps/web`);品牌字串 `JobIntel AI` → 專案名(`Caliburn`,AI 後綴待定),同步 api `config.py` `app_name`。
- **B. 版本命名**:傾向「**內部去版號、外部/資料才保留版本**」——`graph_v3`→語意名(如 `graph`)、`components/interview/v3` 與 `/v3` route 去版號語意化;`ocs_v4` 保留。(替代:照使用者原話 literal `v3→v4`。)
- **C. docker/db**:service `db` 留;`container_name` 改用 project 前綴(`caliburn_*`)或移除走自動名;`POSTGRES_DB`/`database_url` 的 `jobintel`→`caliburn`(**資料面決策**:新庫 vs 沿用舊名);`qdrant`/`embedder` 容器一併處理。

## 4. 待拍板(forks，將寫入 ADR)
1. 版本命名走 **B「內部去版號」**(建議)還是 literal **v3→v4**?涵蓋範圍(僅 web route?含 `graph_v3`?)
2. 品牌顯示名 = `Caliburn` 還是 `Caliburn AI`?
3. docker:`container_name` 移除走自動名(建議)還是固定 `caliburn_*`?DB 名 `jobintel`→`caliburn`(新庫)還是沿用?

## 來源
- [About scopes — npm Docs](https://docs.npmjs.com/about-scopes/) · [Scope — npm Docs](https://docs.npmjs.com/misc/scope/)
- [Specify a project name — Docker Docs](https://docs.docker.com/compose/how-tos/project-name/) · [Default naming scheme (docker/compose#6316)](https://github.com/docker/compose/issues/6316)
- [API design: which version of versioning is right for you? — Google Cloud / Apigee (Martin Nally)](https://cloud.google.com/blog/products/api-management/api-design-which-version-of-versioning-is-right-for-you)
- [Versioning Best Practices in REST API Design — Speakeasy](https://www.speakeasy.com/api-design/versioning)
