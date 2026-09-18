# ADR 0014 — DB image 降回 stock `postgres:16`(移除未使用的 pgvector)

- **狀態**:Accepted（2026-06-30）。
- 研究依據:[`../specs/2026-06-30-db-image-drop-pgvector-research.md`](../specs/2026-06-30-db-image-drop-pgvector-research.md)。

## 脈絡

`docker-compose.yml` 的 `db` 服務沿用 `pgvector/pgvector:pg16`,是 v3 重構前(API 在 Postgres
內以 pgvector 做 iCAP RAG)的遺留。**D5** 已決定砍 pgvector、檢索外包 ocs-indexer 的 Qdrant
(對齊 ADR 0003 indexer 獨立、ADR 0012 嵌入服務化)。

盤點現行碼:Alembic baseline 只建 `uuid-ossp`,無 `CREATE EXTENSION vector`、無 `Vector` 欄位、
無 init.sql、無任何 `::vector` 參照;所有 `pgvector` 字眼皆在 `docs/archive/` 或「已移除」註解。
pgvector 官方 README 載明該 image「adds pgvector to the Postgres image」,即官方 `postgres` 衍生映像
→ `pgvector/pgvector:pg16` 等於 `postgres:16` 多帶一個我們沒啟用的擴充。

## 決定

`db` 服務 image:`pgvector/pgvector:pg16` → **`postgres:16`**。

- 同步更新 `docker-compose.yml` 檔頭註解與 `README.md` 服務表中「Postgres(pgvector)」字樣 → 去掉 pgvector。
- **不動** `pgdata` volume:現有庫從未建 `vector` 擴充,stock `postgres:16` 完全相容,毋須重建。
- service 名(`db`)、ports、env、healthcheck、Alembic 流程一律不變。

## 後果

- ✅ image 與實際用途一致(無 in-DB 向量);改用官方主映像(更小、更新更勤、來源主流)。
- ✅ 去除誤導:不再讓人以為 DB 仍跑向量檢索;與 ADR 0003/0012 + D5 一致。
- ⚠️ 若未來要改走 in-DB pgvector,需改回此 image 並新開 ADR 翻案——惟現架構走 Qdrant,可能性低。
- 📌 move-only:green-before == green-after;一個 task 一個 commit。
