# JD 關聯資料層：版本、交易接點與真 DB 驗證前置

**同日後續實作：**已依本文在新隔離 lock 安裝、固定 migration 並完成十三表真 PG 初始化／22 項驗證，詳[結果與保存基礎](../2026-09-13-jd-result-and-storage-foundation.md)。本文下列「尚未」描述本研究交付當時；完整 command 保存／恢復仍未通過。

- 查閱日：2026-09-13；Topic：JD-R002／RS-F 資料接點、RS-2。
- 狀態：有界官方研究已收束；可供隔離施工選定依賴，尚未安裝此組合、產生 migration 或驗證真 DB 保存。production authority／G6 不變。
- 已讀依據：[目前決策](../../current-decisions.md)、[決策流程](../../decision-process.md)、[契約策略](../../contract-strategy.md)、[十三表與保存契約](../2026-09-12-jd-relational-schema-and-write-contract.md) §3–10、[框架選型](../2026-09-13-jd-app-stack-selection.md)、[原生接點前置](../2026-09-13-jd-native-framework-and-integration-preflight.md)、[RS-1–7 計畫](../../plans/2026-09-13-jd-relational-app-implementation.md)。本輪問題僅為既定保存效果有無原生資料層接點；不重選 JD 欄位、刪除政策、回執語意或 Agent loop。

## 1. 推薦的精確組合與證據等級

**選 SQLAlchemy Core＋同步 Psycopg 3＋Alembic。**用 Core 的 Table／SQL expression／Connection 承接固定十三表，domain 仍是獨立的純 Python；資料層 mapper 不把 SQLAlchemy Row 或 ORM entity 直接送到 HTTP／模型。這是本案接點取捨，不因舊碼使用 Python 加分，也不是大廠統一資料框架的宣稱。

| 層 | 本輪推薦／現行狀態 | 官方版本、相容性、授權與限制 |
|---|---|---|
| Python | 3.12.13，沿本次隔離切片已驗 runtime | 本地 probe 要求 `>=3.12,<3.13`；這不是宣稱 Python 3.12 為最新主版本。以下三套新依賴均涵蓋 Python 3.12；完整 lock 解算與匯入仍待施工 |
| SQLAlchemy | `SQLAlchemy==2.0.52`，Core；2026-08-11 Current Release | [官方下載／授權與狀態](https://www.sqlalchemy.org/download.html)：MIT；2.1.0rc2（2026-09-08）仍屬 Beta，沒有採 RC 的本案必要性。[PG dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)列 PG 9.6+ supported，原生提供 Psycopg 3 dialect；這不延長已 EOL PostgreSQL 的官方支援 |
| Driver | `psycopg[binary]==3.3.5`；2026-08-31 穩定發布 | [官方 release notes](https://www.psycopg.org/psycopg3/docs/news.html) current 為 3.3.5；頁首 3.3.6.dev1 是開發文件版本，不能拿來鎖套件。[官方 PyPI 發布](https://pypi.org/project/psycopg/3.3.5/)為 LGPL-3.0-only、Python >=3.10。[安裝支援表](https://www.psycopg.org/psycopg3/docs/basic/install.html)列 Python 3.10–3.14、PG 10–18、Windows；受支援 PG 才持續跑 CI，EOL server 只是 best effort |
| Binary implementation | `psycopg-binary==3.3.5`，由 extra 鎖入 | [官方發布檔](https://pypi.org/project/psycopg-binary/3.3.5/)已有 `cp312-cp312-win_amd64` wheel。[安裝文件](https://www.psycopg.org/psycopg3/docs/basic/install.html)說明 binary 自帶 client libraries，適合本機免編譯；其 libpq 版本依建置產物而定，安裝後須記實際 `psycopg.pq.version()`，不能從 server 版本推算。發佈包須保存實際套件及隨附函式庫的授權資訊；不把 LGPL 套件誤寫成 MIT |
| Migration | `alembic==1.20.0`；2026-09-11 穩定發布 | [官方 changelog](https://alembic.sqlalchemy.org/en/latest/changelog.html)下一個 1.20.1 尚無發布日；[官方 PyPI](https://pypi.org/project/alembic/1.20.0/)列 MIT、Python >=3.10。1.18.3 起最低 SQLAlchemy 1.4.23，所選 2.0.52 在範圍內。剛發布不等於整合已驗 |
| 新 fresh-data DB 目標 | PostgreSQL 18.6；官方 image `postgres:18.6-bookworm` | [官方版本表](https://www.postgresql.org/support/versioning/)列 18.6 為最新穩定 major 的 patch，支援至 2030-11-14；19 Beta 不選。[映像維護者 README](https://github.com/docker-library/docs/blob/master/postgres/README.md)列此 tag。[PostgreSQL License](https://www.postgresql.org/about/licence/)為寬鬆開源授權；image 還包含各自授權的作業系統套件。本輪未 pull、核 image digest 或啟動新 server |

此表是可施工的**精確直接依賴與 DB 目標**，不是已完成的完整 lock／artifact digest。安裝後由隔離 lock 固定 transitive dependencies 與平台產物，再跑本案反例。SQLAlchemy 管理連線即可，本輪不另引入 `psycopg_pool`、asyncpg、SQLModel 或第二個 pool owner。

唯一替代比較是 Django ORM：整合 migration 與管理能力仍有價值，但 [Django 6.1 composite primary key 文件](https://docs.djangoproject.com/en/6.1/topics/composite-primary-key/)明示 `ForeignKey` 尚不能指向複合 PK，`ForeignObject` 不建立 DB FK／index 且忽略 `on_delete`。本案密集使用 `(document_id,item_id)` 複合鍵及同文件關係，採 Core 的具名複合 FK 更直接；不為配合 ORM 改十三表，也不表示 Django 無法搭配自訂 SQL 完成。Django 版本／BSD 3-Clause／支援週期沿[既有選型研究](../2026-09-13-jd-app-stack-selection.md)；本輪只增核這個會影響資料接點的限制。

## 2. 八個原生接點與本案責任

下表的官方文件均於 2026-09-13 讀取；SQLAlchemy 使用 2.0.52 文件，Alembic 使用 1.20.0 文件，Psycopg 使用目前 3.3 文件並核新增功能不晚於 3.3.5，PostgreSQL 使用 18 文件。沒有把文件範例算成實測。

| # | 官方能力／限制 | 本案施工映射 |
|---|---|---|
| DB-E01 短交易 | [SQLAlchemy Connection](https://docs.sqlalchemy.org/en/20/core/connections.html)提供 `Connection.begin()`／`Engine.begin()`，正常離開才提交，例外往外傳；第一個 SQL 也可能觸發 autobegin | 每個 command 一條 connection、一個明確外層交易。解析、LLM／source I/O 在交易外；寫入和對帳按既定 READ COMMITTED。不能在 begin block 內先回 confirmed，還沒執行的 context exit 才是真 COMMIT 邊界 |
| DB-E02 Savepoint | [Connection.begin_nested](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Connection.begin_nested)回傳 nested transaction；其 commit 是 RELEASE SAVEPOINT，rollback 是 ROLLBACK TO SAVEPOINT；Connection.commit 作用於外層 | document→head 鎖在 savepoint 前取得。已知語意／具名約束錯誤回滾候選後，在外層保存 failure receipt；no_change 同樣先撤回候選。savepoint 成功不是 receipt 持久證明 |
| DB-E03 避免提前 flush | [ORM transaction 文件](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)明示 `Session.begin_nested()` 無論 autoflush 設定都先 flush pending state | 採 Core 可明確控制每句 DML，避免 ORM pending state 在候選 savepoint 前送出。這不是 ORM 不支援交易；若未來改 ORM，須證明鎖前及 savepoint 前無不該發布的 DML |
| DB-E04 不暗中 pipeline | [Psycopg pipeline 文件](https://www.psycopg.org/psycopg3/docs/advanced/pipeline.html)明示 `executemany()` 自 3.1 起內部使用 pipeline | 契約 §6.2 已限定同步逐句；首版採單組參數 execute，不把 `Connection.execute(stmt, list_of_dicts)` 當成已證無 pipeline。DBAPI 探針須核實實際路徑；不能只搜尋沒有 `.pipeline()` 就判 PASS |
| DB-E05 鎖與對帳 | [PG row locks](https://www.postgresql.org/docs/18/explicit-locking.html)指出 savepoint 後取得的鎖可隨該 savepoint rollback 釋放；FOR UPDATE 等到另一 writer 結束 | 所有 mutation、archive 與恢復同 document→head 鎖序；rollback 候選不能放掉外層 barrier。對帳須先有原 writer 停止證明，再取得 barrier，下一 statement 查原 operation；框架不提供這項業務證明 |
| DB-E06 同版唯讀 | [PG SET TRANSACTION](https://www.postgresql.org/docs/18/sql-set-transaction.html)要求在第一個 query 前確立 isolation；REPEATABLE READ 用同一交易讀取視野。[SQLAlchemy READ ONLY 接點](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#setting-read-only-deferrable)提供 `execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)` | 取 connection 後、第一個業務 query 前設選項，再 begin，完整 materialize 單份 JD／metadata／來源 links。關閉交易後才產 projection／refs 或讀外部原文。讀取不 FOR UPDATE、不跨請求保持 snapshot；對帳仍 READ COMMITTED，不能共用 reader 設定 |
| DB-E07 連線失敗與 COMMIT | [SQLAlchemy pool 文件](https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-pessimistic)明示 pre_ping 無法挽救交易中斷線，例外交 App 處理。[Psycopg 狀態](https://www.psycopg.org/psycopg3/docs/api/objects.html)區分 connection UNKNOWN 與 transaction FAILED／COMMITTED，FAILED 包含連線故障 | 這些是客戶端狀態，不是 JD operation 查回結果。App 記錄階段及已確認 rollback／COMMIT；COMMIT 可能送達而未收到確認時維持 effect unknown、原 binding 與 reconcile_operation。已證 rollback 則 effect unchanged，但未確認 receipt 仍不解綁。框架一般 retry 建議不能覆蓋本案「不自動重播 mutation」 |
| DB-E08 初始化／版本簿 | [Alembic runtime](https://alembic.sqlalchemy.org/en/latest/api/runtime.html)提供 transaction context、target_metadata、版本表與 schema；對真 PG 的 transactional DDL 可包實際交易，離線 `--sql` 只是輸出文字 | 採一套 JD MetaData＋明示 migration 初始化，日常啟動只檢查版本，不 create_all／清表／自動降版。Alembic 的 `alembic_version` 是遷移簿，不是第十四張 JD 業務表或另一份 JD revision；報物理表數時要分列 |

Psycopg 自己也提供 [transaction context](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)，但已由 SQLAlchemy 管理的 connection 不再混入第二層 driver transaction owner。否則先前 SELECT 的 autobegin 可能使 driver context 只建立 savepoint，離開後仍未提交最外層；App 不能從「某個 with 正常結束」猜出保存成功。

## 3. 十三表約束沒有框架能力缺口；以下必須落成 DDL 與 mapper

SQLAlchemy 的 [ForeignKeyConstraint](https://docs.sqlalchemy.org/en/20/core/constraints.html)可表達多欄 FK；兩個獨立 ForeignKey 不能代替成對的同文件 FK。PostgreSQL 的 [constraints](https://www.postgresql.org/docs/18/ddl-constraints.html)提供本案 PK／FK／CHECK／UNIQUE 及刪除行為；nullable FK、NULL 的 UNIQUE 語意及 CHECK 非跨列驗證仍需正確使用。

| 已定表／不變量 | 必要落點與不能冒稱的部分 |
|---|---|
| document、profile、head、revision 初始化 | 依契約在同交易建立 catalog→profile→initial snapshot/revision→head；create key 唯一且 digest 核對。父表存在不能單靠 FK 保證必有 profile/head，完整初始化與啟動驗證由 App 負責 |
| collaborator／duty／task／capability／condition | 複合 PK、document scope FK、kind／非 NULL 有意義欄位／非負 position CHECK；全空白判斷及 LF 正規化仍由共同 mapper。不要將 Python 空白規則偷偷換成 SQL trim 規則 |
| task→duty、task_detail、task_capability | 同文件 FK；task→duty RESTRICT，task 刪除的 details／links CASCADE，capability 被引用時 RESTRICT。D01 先保留／解除 tasks 再刪 duty；ORM cascade 設定不能代替 DB 約束或業務順序 |
| source_link typed targets | 八種邏輯 target exactly-one；relation 兩欄同空／同有值，並有指向 junction 的三欄 FK。其餘 nullable typed FK 用正常 nullable 規則，不能一律 MATCH FULL，因 document_id 固定非 NULL 會使合法未使用 target 失敗。來源 port scope、讀取權責、basis 最終內容及 upsert 順序仍由 App 驗 |
| revision 線性與歷史 | 同文件 self FK；initial iff parent NULL；每文件至多一 initial 的部分唯一規則；UNIQUE(document_id,parent_revision_id) 阻止同 parent 兩 successors；revision_number 唯一。snapshot 是歷史 material，current rows 才是可編輯權威；初版只提供 insert/read port，不誤稱 FK 會自動使歷史 immutable |
| operation 終局 | 同文件 base/result FK、origin/run 同時性 CHECK、status 白名單、committed result 的部分唯一索引；相同 key 不 UPSERT 覆寫。result／effect／durability／next_action 的合法組合沿 root 正在閉合的 SSOT；欄位 FK 非空不能單獨證明 receipt 與 snapshot/head 同時保存 |

**需要在首版 migration 審查時閉合的技術缺口**是具名約束清單／DDL、constraint→domain code 白名單、ordered DML／restore 次序及版本識別；不是尚待 Owner 決定要幾張表。source-ref 同 target 的穩定去重已是 service 契約；這份研究不自行增加來源生命週期或改為覆寫全部來源。

[Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)是候選 migration：1.19 起已有 CHECK plugin，1.19.2 起預設關閉，只按名稱辨識增刪，同名 expression 改變不會被發現。初版應逐條核對已定 CHECK；後續 `alembic check` PASS 也不能替代約束反例。範圍過濾須固定 JD metadata，避免把其他 owner 的表當成多餘表產生 drop；RS-2 仍只在專用新 DB 初始化，本輪研究未執行初始化。

COMMIT／SQL 例外也可能含 SQL parameters、server DETAIL 或原文。資料 adapter 只對已核 SQLSTATE／具名 constraint 做分類，不輸出完整 exception／SQL／連線字串；沿[安全診斷前置](2026-09-13-jd-app-boundaries-errors-logging-evidence.md)，logger 故障不能覆蓋實際結果。連線 invalidated、錯誤名稱或 log 出現「commit」都不構成持久 receipt 證據。

## 4. 本機唯讀觀察與未驗限制

2026-09-13 已執行 Docker version／ps、已知容器中的 `postgres --version` 與 q019 的 `pg_isready`；未讀 `.env`、container environment、密碼或業務資料。一般 sandbox 第一次查 Docker pipe 回 permission denied；經唯讀權限執行後得到以下結果，這不是 Docker 不可用的結論。

| 表面 | 實際觀察 |
|---|---|
| Docker Engine | 29.7.2 |
| `caliburn-db-1` | image tag `postgres:16`；Up／healthy；binary 16.14（Debian 16.14-1.pgdg13+1）；5432 對外綁定 |
| `caliburn-q019-postgres` | image tag `postgres:16`；Up；binary 16.14（同上）；host 127.0.0.1:55433；pg_isready 接受連線 |

這只證明執行環境與 readiness，沒有驗證使用新 App 設定登入、專用 DB 已存在、其內容為空、schema 相容或 migration 權限。不可因 q019 名稱而把舊資料表／volume 作新 relational 權威；本輪未初始化、修改／升級／停止任何容器或資料。

官方目前 16 系列 patch 已是 **16.15**，支援至 2028-11-09；本機 16.14 不能標成最新 patch。若首個反例先使用已授權的專用新 DB、server 16.14，只能報 PG16.14 相容性結果，不能宣稱 PG18.6 目標已驗。新 fresh-data 目標按 §1 使用 PG18.6，版本／映像 digest 在實際初始化證據中固定。

PG18 官方 image 的預設 PGDATA 改為 `/var/lib/postgresql/18/docker`，volume mount 改為 `/var/lib/postgresql`，見[映像 README](https://github.com/docker-library/docs/blob/master/postgres/README.md)。新目標使用專用 fresh volume，不把 16 的舊 volume 掛上嘗試自動升級；這是本案 fresh-data 限制的接法，不是本輪執行結果。

## 5. 下一個真 DB 單位的最小反例

全部先用合成資料、無模型、專用新 DB。保存首敗與最後結果，並記真正 server／driver／libpq／SQLAlchemy／Alembic 版本；資料層 mock、DDL 編譯與真 PG 證據分列。

| 反例 | 可驗 PASS 條件 |
|---|---|
| DB-T01 初始化／版本 | 同 create key 同 digest 回同一完整文件；不同 digest 拒絕。中途注入例外不留下只有 catalog 的半份文件；新程序重讀初版一致。錯誤 snapshot／receipt／schema version 停止，沒有清資料 |
| DB-T02 直接約束 | 跨 document FK、半組 relation source target、零／兩個 target、非法 kind、第二 initial、同 r1 的第二 successor、重複 junction、兩個 committed producer 都在真 PG 被拒絕；錯誤沒有被一律改成 invalid_input |
| DB-T03 候選回滾仍保留 barrier | 先移 task 再觸發已知 constraint；rollback savepoint 後所有 current 值仍原樣，外層 document/head 鎖仍在，failure receipt 只有外層 COMMIT 後 confirmed。no_change 不增 revision、不換 head |
| DB-T04 成功原子性／相同 operation | current rows／canonical snapshot／head／receipt 全相符；同 key 同 digest 查回原結果，不因最新 head 再驗而拒絕；不同 digest 不覆寫。首個原子提交之後模擬回覆遺失，只對帳同一 operation |
| DB-T05 COMMIT／rollback 故障 | 分開「COMMIT 前且 rollback 已證」、「COMMIT 確實到 server 但確認遺失」、「failure receipt COMMIT 失敗」、「rollback 本身失敗」。未確認時保留 binding；只有停止證明＋同鎖 barrier＋下一 statement 原回執／known-none，才按既定恢復 port 閉合；不重播命令 |
| DB-T06 同 base／不同文件 | 同文件兩 writer 依鎖序只容許一 successor，另一依原 identity 得到已定結果；archive 交錯不漏原 operation 閉合；文件 A 的鎖不使用全域 mutex 阻擋文件 B |
| DB-T07 同版 read | reader 讀 r5 duties 後 writer 新增 C／移 T→C／提交 r6；reader 後續 task／source／refs 全仍 r5，下一 read 全 r6。對帳 READ COMMITTED 等鎖後的下一 statement 能看見原 writer 剛提交的 receipt，不能誤走 known-none |
| DB-T08 完整保存與還原 | D01 保 tasks、子項與共用 K/S；跨 duty move 只更改允許範圍；source basis 以最終值刷新、空 refs 保留。完整樣稿 rows→snapshot→projection 無損；restore 子項先刪／父項先建，途中錯誤無半份發布，成功保留歷史 IDs／來源、形成新 revision，不回退 Memory／問答 |

DB-T03／05 同時檢查 SQL 執行路徑沒有 executemany／pipeline；DB-T07 的 connection 歸還後再次寫入，驗證 READ ONLY／isolation 沒有污染 writer。這些是已定契約的有限接合驗證，沒有另造通用 transaction engine。

## 6. 收束

本輪沒有發現需要替換 SQLAlchemy／Psycopg／Alembic 或增加 JD 業務表才能滿足的能力缺口。真正阻擋 RS-2 驗收的是隔離 lock 與 DB 目標實際落地、十三表具名 DDL、保存／恢復接線及上述真 DB 反例；共同 result SSOT／HTTP 投影可並行。

研究到此停止。若實際 driver 路徑、migration 約束或失敗注入推翻上述接法，再針對反證重開；不追加框架排名、雲端／微服務、第二 Agent loop 或舊資料搬移。本稿只寫入這份 evidence；其他文件及實作由 root 整合，整體 G4／G6 不因本稿完成而改判。
