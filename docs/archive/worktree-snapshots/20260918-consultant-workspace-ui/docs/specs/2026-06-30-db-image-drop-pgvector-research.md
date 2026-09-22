# DB image 去 pgvector 研究紀錄 — `pgvector/pgvector:pg16` → `postgres:16`

> **類型**:研究紀錄(findings,非決策)。決策見 [ADR 0014](../adr/0014-db-image-stock-postgres.md)。
> **日期**:2026-06-30
> **動機**:`docker-compose.yml` 的 `db` 服務用 `pgvector/pgvector:pg16`,但 v3(D5)已把檢索外包給
> ocs-indexer 的 Qdrant、API 不再有 in-DB 向量。盤點 pgvector 是否還有用,決定是否降回 stock Postgres。

## 1. 診斷:pgvector 在現行程式碼是否還被使用?

全 repo 掃描(排除 `.venv`)結論——**現行程式碼零依賴 pgvector**:

| 證據 | 位置 | 說明 |
|---|---|---|
| API 明說已移除 | `apps/api/requirements.txt:10` | `v3: dropped psycopg2-binary + pgvector + llama-index — retrieval 外包 jd-ocs-indexer (Qdrant), 無 in-DB 向量 (D5)` |
| Alembic baseline 只建 `uuid-ossp` | `apps/api/alembic/versions/0001_document_centric_baseline.py:25` | `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`;**無** `CREATE EXTENSION vector`,**無** `Vector`/`::vector` 欄位型別 |
| 無 init.sql | (不存在) | schema 全由 Alembic 管(D25);沒有會 `CREATE EXTENSION vector` 的啟動腳本 |
| 所有 `pgvector` 字眼皆為歷史/註解 | `docs/archive/jobintel-v3/**`、上述註解 | 重構前架構;`docs/archive` 依規不改 |
| `SparseVector`/`EmbeddedVector` 與 pgvector 無關 | `apps/ocs-indexer/**` | 是 Qdrant `models.SparseVector` 與 indexer 自有 DTO,走 Qdrant,不碰 Postgres |

對齊既有決策:**D5**(`docs/archive/jobintel-v3/specs/2026-06-16-refactor-decision-log.md`)
「Postgres 留;砍 pgvector + `icap_embeddings`,檢索外包 indexer/Qdrant」。

## 2. 權威發現:image 關係

pgvector 官方 README(Docker Installation)明載:該 image **「adds pgvector to the
[Postgres image](https://hub.docker.com/_/postgres)」**——即從官方 `postgres` image 衍生,
僅多裝 `vector` 擴充;tag 命名 `pg13`…`pg18`(對應 Postgres 大版本)。

→ `pgvector/pgvector:pg16` ≡ 官方 `postgres:16` **+ 一個我們沒啟用的擴充**。
因此 `postgres:16` 是其**嚴格子集**:換過去只是移除「未使用」能力,不增不改任何現用行為。

## 3. 選項比對

| 選項 | 取捨 |
|---|---|
| **A. 換 `postgres:16`(建議)** | image 與實際用途一致(無 in-DB 向量);更小、官方主映像、更新更勤;表意清楚。代價:萬一未來要 in-DB 向量需改回(但架構決策是走 Qdrant,可能性低)。 |
| B. 維持 `pgvector/pgvector:pg16` | 不動;但映像帶著沒人用的擴充,易誤導(README/註解都還寫「pgvector」),且 image 來源較非主流。 |
| C. 全面遷向 in-DB pgvector | 與 ADR 0003/0012(indexer + embedder 服務化)相悖,推翻 D5;不在本次範圍。 |

## 4. 安全性(move-only 論證)

- 換 image **不動 `pgdata` named volume**:既有資料保留。現有庫從未 `CREATE EXTENSION vector`
  (baseline 只建 uuid-ossp),故 stock `postgres:16` 對現有 volume 完全相容,**不需重建 volume**。
- 無程式碼/migration/SQL 參照 `vector` 型別 → green-before == green-after。

## 來源
- [pgvector — Installation (Docker) · GitHub README](https://github.com/pgvector/pgvector#docker)(「adds pgvector to the Postgres image」)
- [Official `postgres` image — Docker Hub](https://hub.docker.com/_/postgres)
- 既有決策 D5(`docs/archive/jobintel-v3/specs/2026-06-16-refactor-decision-log.md`)、ADR 0003 / 0012。
