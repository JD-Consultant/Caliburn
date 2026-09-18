# Q019 第四切片：Memory 原子發布與提交回執

> For agentic workers: 依 executing-plans 逐步執行；同一發布 seam 不拆平行修改，最後獨立 review。2026-09-06，Owner「ok」延續已核准 Q019 §6。只准隔離開發。
>
> 狀態：第四切片測試與獨立複核完成，49 passed／0 skipped；R1 已關閉。本地保存點由 main decision register 記錄，不是完整 Memory 產品完成。

**Goal:** 背景整理／即時修補可各自準備新版，但只完整、未過期的版本能成為目前 Memory；不確定提交可用原 operation 恢復。
**Architecture:** StoreBackend 保持正文／導覽保存者。新增兩個小型 SQLAlchemy ORM tables，只放 head 與永久 receipt metadata；短 transaction＋version_id_col，沒有 LLM 期間鎖定，沒有第二份 Memory 文字。A 由一次 head 查詢建立同版本 read view。
**Tech Stack:** 上切片 pins＋SQLAlchemy 2.0.52（官方目前 stable；2.1 beta 不採）；PostgreSQL16，測試可用 SQLite 做序列契約，但真正並寫必須 PG。
**Spec:** [Memory §6](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md)、[整體](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design.md)、[審核 F04–F06](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-design-review.md)、[上切片結果](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-read-path-results.md)。

## Preflight

- Topic: LLM-Q019；目前隔離存取底座完成，進發布 seam。
- 已讀：main register／decision-process／Q019 整體、Memory、review、第三結果；不讀歷史 production 方法來約束本段。
- 唯一問題：prepared version → CAS head＋receipt → 重開 read view，是否不丟更新／不重播？
- 不做：B1/B2 生成／排程、C edit Tool／Command 刷新、UI、JD、provider 或 Skill 變更、付費 API、GC、merge/push。
- 重用 .worktrees/analysis-only-agent，branch codex/analysis-only-agent；基線30 passed／2 PG skipped，前段實際 PG32 passed／0skip。
- 官方核對：version_id_col 只在 ORM flush 生效；BEGIN scope 正常 commit／例外 rollback；沒有 dirty attributes 不會送 UPDATE；PG READ COMMITTED 更新會重新核對 WHERE。這些支持版本檢查，不代表框架原生有本案 receipt schema。

## Task 1：一個可恢復發布的垂直切片

### 檔案與邊界

- 新 src/analysis_agent/publication.py：PublicationStore(engine, artifacts) 固定文件；ORM head／receipt、runtime request／snapshot dataclasses；不 import App，不包模型。
- 改 src/analysis_agent/memory.py：verify_version(version) 用公開 download/read 驗完整正文＋導覽、引用、既有格式；回 runtime SHA256 指紋。新版本只由 save_memory 建立；無公開 in-place writer。
- 新 tests/test_publication.py：序列發布、過期、回執、部分失敗與校驗；使用真 ORM SQLite＋官方 InMemoryStore。
- 新 tests/test_postgres_publication.py：真 PG Store/Saver/ORM、兩 connection 同基準競爭、同 op 重送、commit 後結果遺失、reopen。
- pyproject.toml／uv.lock：增加官方 SQLAlchemy stable。
- README／本計畫／結果稿／main register 同步狀態。只 explicit stage 本段檔案。

### Runtime 接口（均非模型填欄位）

- prepare(version, expected_revision, kind, processed_source=None, repair_sources=()) → PublishRequest：kind consolidation／repair；operation UUID、artifact digest 由程式產生。B processed_source 是已完成來源視窗 reference，C 不推 B 游標；C 可保存0～多筆受控更正來源供後續 B2 重讀，不要求每次整理都新原話。
- publish(request) → PublishedHead：先查同 op receipt，再驗封存指紋；短交易內再查 receipt、比較生成時 expected_revision、修改 mapped head instance、flush、插 receipt、commit。沒有 head 時 base=0，第一位 INSERT 以 PK 判勝。
- current() → PublishedHead | None：只取得一份 head metadata；由 artifacts.reader/guide(head.memory) 固定版本，避免分別查 head。
- receipt(operation_id) → Receipt | None：獨立新 Session；找不到只代表目前沒看到，不斷言先前交易已失敗。
- repair_receipts(after_revision, through_revision, limit=20) → list[Receipt]：固定上界／按 revision 升序分頁；後段 B2 可重用，不在本段跑 B2。
- stale → 明確 StalePublication（含當時 current）；不同 payload 用同 op → ValueError；DB 提交結果不明 → PublicationUncertain，保留相同 request 重查／重送，不改 op、不自動重跑模型。

Metadata：head 只含 document、revision、artifact version、B cursor、last operation；receipt 含 document＋operation unique、request fingerprint、base／result revision、artifact version、結果 cursor、kind、repair refs。正文／完整問答不寫入這兩表。來源游標有無向前涵蓋／完整視窗由未來 B workflow 控制；此 seam 只防舊基準覆寫、C 擅動 B cursor。

### 交易核心

```python
with sessions.begin() as session:
    # 同 op 必須完整相同，否則拒絕；成功 receipt 永久可查。
    row = session.get(HeadRow, document_id)
    if (row.revision if row else 0) != request.expected_revision:
        raise StalePublication(...)
    # 已有 row 用 ORM mapped assignment，禁止 bulk UPDATE。
    row.last_operation_id = request.operation_id  # 即使正文/cursor no-op 也觸發 CAS
    session.flush()
    session.add(ReceiptRow(...))  # 与 head 同一 transaction
```

- Store 保存／讀回在 SQL 短交易外；失敗不動 head。不跨 Store＋SQL 做 distributed transaction：未發布 artifact 可以殘留，尚無 GC。
- IntegrityError／StaleDataError 必須先讓 transaction rollback，再用新 Session 查同 op receipt；有則恢復原結果，沒有則回 stale 或原 DB 錯誤，不掩蓋其他 constraint 失敗。
- 保留模型不可寫已封版 namespace 的前切片約束；不能宣稱 Store 自帶不可變。可信 process 外部直接改 DB 不在本 API 保證內。

### Tests／步驟

- [x] 寫缺功能紅燈：publish 第一版、讀 current 正文/guide；同 op 重送回相同 revision，沒有額外 receipt。
```python
request = publications.prepare(v1, expected_revision=0, kind="consolidation", processed_source=source)
first = publications.publish(request)
assert first.revision == 1
assert publications.publish(request) == first
assert artifacts.guide(publications.current().memory) == "案例A導覽"
```
- [x] 執行 pytest tests/test_publication.py -q，確認缺 publication 而 fail；加入 SQLAlchemy，最小實作。
- [x] 補失敗：缺失版本（正文／guide不可讀）／改 prepared bytes、不同 document、不合法 request、舊基準；都不改 head 或 cursor。
- [x] 補 C 勝 B 舊結果被拒；來源 cursor 不被 C 推進；same-version no-op B 仍增 revision 防舊 B 覆寫；receipt 能在後續多次發布後回原結果，另一 document 看不到。
- [x] 用 SQLAlchemy 公開 test events 注入 flush 後失敗，驗 head＋receipt 一起 rollback；after_commit 斷回覆，重建 Session 並依同 op 恢復；不在 production 放測試 hooks。
- [x] 真 PG：Barrier 讓兩個 mapped UPDATE 同時讀到相同 base再flush，確認一成功一 stale；同 op 競爭回同receipt；第一版 INSERT競爭同理。設 timeout，無 paid model；只清本次隨機文件的測試 rows/artifacts，不 drop tables/DB。
- [x] 審核R1：首次receipt／rollback後receipt與head讀取斷線均先重現，再納入PublicationUncertain；不把查不到或查詢失敗解讀成原交易失敗。
- [x] 全套 PG＋離線測試、compileall、lock check、diff check；獨立 review，finding先重現再修。R1 限定複核 12 passed，沒有新阻塞。
- [x] 結果分層記錄、main register 關閉本驗證 gate／列 next。local commit/tag 的實際保存點以 main register 為準；B2 重算語意與 C 受控刷新仍未交付。

## 自我覆蓋審核

覆蓋 Memory §6 的封版檢查／短交易／expected base／receipt／不確定提交。§6 的模型重讀與 state Command、§2 的排程與完整來源處理仍不在本切片；不能稱 B/C 產品流程已全部完成。不開新產品決策；若官方實測反證 mapper交易能力，停止並帶證據回 Owner。

## 來源

- [SQLAlchemy versioning](https://docs.sqlalchemy.org/en/20/orm/versioning.html)：non-null counter、ORM flush、StaleDataError；禁止 bulk繞過。
- [Transactions](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)：sessionmaker.begin 生命週期；例外 rollback。
- [Session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#committing)：no-dirty 不會有 UPDATE，故需要 last operation 觸發。
- [PG16 READ COMMITTED](https://www.postgresql.org/docs/16/transaction-iso.html#XACT-READ-COMMITTED)：並寫等待與 WHERE 再判斷。
- 本機 SQL schema／runtime request 是上述 API 的應用 mapping，不宣稱 OpenAI 使用相同表／ID。OpenAI 記憶原理本段未重研／未改。
