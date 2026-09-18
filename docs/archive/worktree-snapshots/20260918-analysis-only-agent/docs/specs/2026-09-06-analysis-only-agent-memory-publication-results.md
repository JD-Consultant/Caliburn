# Q019 第四切片：Memory 原子發布與回執結果

> 2026-09-06 · 隔離實作；全套 **49 passed／0 skipped**；獨立 review R1 已重現、修復並複核關閉，沒有新阻塞。本地 commit/tag 見 main 決策入口；未 merge／push。
> [計畫](../plans/2026-09-06-analysis-only-agent-memory-publication-slice.md) · [有效 Memory 設計 §6](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md) · [決策入口](S:/caliburn/docs/current-decisions.md)

## 1. 本段效果

| 情境 | 現在的結果 |
|---|---|
| 一份整理完成的新 Memory | 先核對 Store 中完整正文、導覽與引用；短 SQL 交易切換目前版本，並寫成功回執 |
| B 與 C 都從同一舊版开始準備 | 不同 operation 只有一個能發布；落後者回 stale，不把新內容蓋回去 |
| 同 operation 同內容再次送達 | 回原本成功結果；就算後來有新版，也不把 head 切回舊版 |
| 同 operation 卻换內容 | 明確拒絕，不能利用重試換掉同一決策 |
| 正文沒變，只更新來源處理進度 | 仍走 ORM 版本檢查；C 不推進 B 的來源游標 |
| 提交前失敗 | head 與 receipt 一起 rollback；未發布 artifact 不成為目前內容 |
| 提交成功、回覆遺失 | 可用同一 request／operation 查 receipt 或重送；不自動重新呼叫模型 |
| 讀取目前知識 | 一次 current 取得固定 MemoryVersion，再交原 reader／guide；不分別查不同 head 拼正文與導覽 |

本段是**發布協調底座**，不是 B/C 模型流程完成。沒有自動背景抽取／整併、C edit Tool、Command 刷新、排程、UI 或 JD。

## 2. Framework 與應用責任

- **Official fact：**SQLAlchemy **2.0.52** 為查證日官方 stable，使用 mapped class、sessionmaker.begin、ORM version_id_col；不採2.1 beta、不用 bulk UPDATE 規避版本檢查。PG短交易完成metadata同時提交。[版本計數](https://docs.sqlalchemy.org/en/20/orm/versioning.html)、[交易](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
- **Mapping：**q019_document_memory_head／q019_memory_publication_receipt 是本案小型 metadata：文件 scope、版本、artifact地址、來源範圍引用、operation、指紋。**没有 Memory 正文或第二份對話內容**。不是宣稱 OpenAI 內部用同一 schema。
- StoreBackend 保持正文、導覽、詳記的保存者；verify_version 以公開 download/read 驗存在、既有大小格式、引用並產生 SHA256 指紋。head 中只選 version ID。
- published bytes 不提供原地 writer；可信 Runtime 的 save_memory 只建立新 UUID 空間，A 仍只有唯讀工具。DB 管理員／旁路直接改 Store 不在此 API 能阻止的範圍；發布前可驗 prepared bytes 未變，不宣稱儲存系統天然不可變。
- no-op 也改 last operation 屬性，以確保 flush 發 UPDATE／CAS；所有成功 operation 留獨立 receipt，不是只留最後ID。[SQLAlchemy no-dirty 行為](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#committing)

## 3. 接口與錯誤

程式在 experiments/analysis-agent/src/analysis_agent/publication.py；metadata 都是 Runtime 資料，不要求 LLM 填寫：

- prepare：驗 prepared artifacts、生成 operation／指紋；原 expected revision 保留到提交，不能最後一刻偷換最新值。
- publish：查既有回執、驗封版、短交易再次核對；成功只回 PublishedHead。StalePublication 要重新考慮內容，不能只替換版本號。
- receipt：新 Session 讀特定 operation。暫時查無結果不是原交易確定失敗。
- current：沒有已發布內容回 None；第一個發布 expected revision=0，用資料庫 primary key 協調 INSERT。
- repair_receipts：固定revision上界，按序有界分頁；後續 B2 可取得 C 保存的更正來源，不在本段自動呼叫原文／模型。
- PublicationUncertain：發布流程中的提交／首次receipt查詢／rollback後對帳遇 DBAPIError，保留相同request再對帳；不加無限retry、不假報成功。獨立 current/receipt讀取仍拋DB例外，不當成「沒有記憶」；已知不相關IntegrityError不偽裝成不確定提交。

receipt／head 同一 DB transaction；Store artifact writes 在外面，所以不是跨儲存系統的分散式交易。模型或大型讀寫不放進此 SQL 交易。PG READ COMMITTED 與 ORM WHERE revision 檢查決定競爭結果。[PG16 isolation](https://www.postgresql.org/docs/16/transaction-iso.html#XACT-READ-COMMITTED)

## 4. 本輪測試與發現

- 基線30 passed／2 PG skipped；未把 skip當 durable pass。前段真PG32passed。
- 新契約測試初始確認缺 publication module 而失敗，實作／審核修復後 tests/test_publication.py **12 passed**：歷史receipt、stale、C cursor不變、no-op CAS、同ID不同payload、缺失／變動artifact、隔離、來源refs、rollback、lostreply及三條對帳讀取斷線路徑。
- tests/test_postgres_publication.py **5 passed in 3.50s**：實際兩連線競爭，涵蓋第一個INSERT及後續UPDATE、相同／不同operation；使用Barrier讓兩邊先讀同基準再競爭。另驗真实COMMIT後人工中斷回覆、重建metadata connection與重新發布後仍可找舊receipt。不是實際拔線／kill主機／DB failover測試。
- 修復後全套 **49 passed in 12.19s，0 skipped**；複核後提交前再跑 **49 passed in 12.67s，0 skipped**。包含先前原生reasoning／compaction／Memory回查／雙程序恢復。compileall及uv lock check通過；73packages，新增SQLAlchemy2.0.52／greenlet3.5.5，原有pins不變。
- 模型 HTTP 保持 synthetic；**付費 API 呼叫0**、不讀產品.env。
- 獨立審核 Q019-S4-R1／P2：首次receipt查詢及rollback後receipt／current查詢的斷線，原本漏出OperationalError，無法走已定PublicationUncertain恢復分支；不是發現資料毀損。新增3案例先重現3 failed／9 deselected，再把不確定結果處理包住完整發布／對帳流程，12項契約測試通過。保留相同request、未加自動重試。
- R1 限定複核已關閉：審核者獨立重跑 **12 passed in 3.63s**；另注入真實 SQLite NOT NULL 違反，確認不相關 IntegrityError 原樣傳出、只寫一次、head＋receipt 一起回退，解除故障後相同 request 可成功。未發現新阻塞；完整 PG 結果由主代理執行，不冒稱審核者另跑全套。
- 過程發現的環境／接點問題：SQLite測試原用系統tmp路徑遇權限，改用原生in-memory SQLite（並行／耐久另用PG，不冒充）；PG fixture把conninfo既作位置參數又作keyword導致TypeError，核對實際dialect及psycopg簽章後，改官方connect_args傳解析後的DB參數。[官方connect_args](https://docs.sqlalchemy.org/en/20/core/engines.html#use-the-connect-args-dictionary-parameter)。沒有改架構或新增重試來遮掩。

測試只使用既有專用 q019_agent_test／localhost55433。新建上述兩metadata表，finally以精確隨機document刪測試receipt／head／artifacts；不drop表／庫、不刪其他訪談。手寫測試資料可重建；專用schema保留。

## 5. 未完成與 next gate

1. B1/B2 的模型抽取、整併、來源視窗切分與工作排程尚未接上；來源游標的完整／向前涵蓋由未來B workflow驗證，publication只保存成功範圍且防stale覆蓋。
2. C 的實際局部edit／Command及A同run受控切版尚未接；本段 current()只提供一致版本handle，不宣稱工具已會自動刷新。
3. repair_sources 驗format／document scope，是Runtime已有來源引用；不是語意依據逐字核實，沒有每次變動必須新原話的規定。B2如何在stale後重讀更正片段仍在後段。
4. 沒有GC／TTL，也沒有舊資料搬移。未發布artifact可以保留，不影響目前版本；不宣稱任意外部副作用exactly-once。
5. SHA驗完整正文/guide會讀完整內容，無額外模型tokens；大型資料I/O成本尚未量測。沒有因測試通過就宣稱分析效果好、永久不忘記或最佳架構。

下一段：依Q019 Memory§2先接B1有界來源抽取／產物交接，再接可補讀B2與publication，最後C局部修補與受控刷新。遇產品語意或官方契約反證再回Owner，不重開已定Memory分層。
