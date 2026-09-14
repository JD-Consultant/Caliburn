# JD 保存契約補正：單向版本關係與終局回執

- 日期：2026-09-10；Topic：JD-R002/C03；範圍：DB02–04，並承接已決待驗的 DB01。
- 效力：Owner 已同意補正這批契約；本附件固定可施工的工程方案，由主線同步共用文義。不修改既有稽核證據、schema、程式或 DB；沒有 SQL probe、安裝、模型呼叫或 production 切換。
- 本案選擇：**只由 operation 引用 result revision；revision 不重複保存 producing-operation 外鍵。**非初版的產生操作由唯一 committed receipt 反查。所有 FK 即時檢查，沒有雙向 FK、暫存假回執或新來源庫。
- 標記：**F** 為既有原始碼／官方事實，**D** 為本次固定設計，**V** 為施工尚須驗證。本文是約束方案，不聲稱已有 migration 或 PostgreSQL 驗收。

## 1. 依據與選擇理由

**2026-09-10共識效力補註：**本附件三表與完整revision是本案工程設計，不是OpenAI／Anthropic或共編產品統一資料表規範。JSON／關聯／協作狀態的分層、近期公開實例、版本粒度與token保留的差異見[保存研究§7](2026-09-10-jd-semantic-relations-storage-audit.md#7-json關聯與三表現行公開證據能支持到哪裡)。此次補證不修改以下已固定SQL契約或保留政策，也不把每個工具attempt都列為須永久保存的回執。

依 [current register](../../current-decisions.md)、[流程](../../decision-process.md)、[DB01–04 稽核](../2026-09-10-jd-responsibility-and-evidence-audit.md)、[完整關係與來源](2026-09-10-jd-storage-relations-audit.md)、[主設計 §5.4](../2026-09-09-jd-editor-app-integration-design.md#54-保存資料的具體約束)、[ADR 0073](../../adr/0073-plate-jd-app-working-document-and-revision-authority.md)、[施工 Task 2](../../plans/2026-09-10-jd-editor-core-implementation.md#task-2同-pg-唯一工作稿revision-與回執)。持續 clean 工作稿、同文件接續、保存後可查完整差異、失敗零發布及相同 operation 對帳的產品語意不變；Memory／來源沿既有 owner，真人交付 PARKED。

**D：採單向關係。**`jd_operation.result_revision_id` 指向 `jd_revision`；只對 committed rows 加部分唯一索引，提供「一新版本最多一個產生操作」。反查便能取得 producer，不需要 revision 再存同一個 operation ID。對本案僅新增版本的寫入流程，這比兩邊 FK 加 deferred 檢查少一組重複關係，也讓 revision→receipt→head 的寫入顺序明確。

**未採方案：**雙向 FK 並將一側設 `DEFERRABLE INITIALLY DEFERRED` 是 PostgreSQL 16 支援的機制，不是不安全或不可用；本案沒有必須反向實體欄位的查詢需求，因此不採。若日後出現新需求，須另評估，不能在本版同時保留兩路。**F：**部分唯一索引與可延後 FK 均有官方機制；可延後 constraint 不能作 `ON CONFLICT` arbiter。[Constraints §5.4](https://www.postgresql.org/docs/16/ddl-constraints.html)、[CREATE TABLE](https://www.postgresql.org/docs/16/sql-createtable.html)（PostgreSQL 16；查閱 2026-09-10）。

## 2. 固定欄位與約束

2026-09-10 Owner同意保存方向後，新格式沿[語意契約v2](2026-09-10-jd-semantic-contract-closure.md)：Task群組、K／S item與單向IDs同完整revision保存；反向集合由同版推導，沒有新增關係表／FK或第二可寫正文。本附件僅更新profile核值，其他三表關係與回執語意不變，尚未建表。

**D：**以下是隔離 `JdStore` 的物理欄位契約，不是第二份對外 wire schema。`receipt` 使用既有 SSOT 的 `JdWriteResult`；生成 DTO 仍只在 adapter／mapper，domain service 不直接 import transport。單一 SQL owner 沿同一 catalog engine，三表不存另一份 Memory、來源正文或目前稿 mirror。

共同規則：`document_id` 型別與既有 `q019_document.id` 相同，採無長度限制的 `varchar`；revision／operation 的內部 ID 採 App 配發 UUID，opaque `*_ref` 經 mapper 解析，不當成未驗 UUID 直寫。FK 全為 `NOT DEFERRABLE`、`MATCH SIMPLE`、`ON UPDATE NO ACTION`／`ON DELETE NO ACTION`。本版無完整文件刪除 API，不藉此加入 cascade 清來源／Memory。表為一般 logged table，不是 temporary／unlogged。

### 2.1 `jd_head`

| 欄位 | 型別／可空 | 約束／責任 |
|---|---|---|
| `document_id` | varchar，非空 | PK；FK→`q019_document.id` |
| `current_revision_id` | uuid，非空 | 與 document 組成 FK→`jd_revision(document_id, revision_id)` |

每份 JD 文件至多一列；成功建立文件時的「至少一列」由 §4 同交易建立保證。head 不保存第二份 value，也沒有 active／deleted／pending 狀態。current read 以同文件 head→revision 的一次查詢取得完整保存版，不能拼接不同版本的 value／profile。

### 2.2 `jd_revision`

| 欄位 | 型別／可空 | 約束／責任 |
|---|---|---|
| `document_id` | varchar，非空 | FK→catalog；與 revision ID 組成 PK |
| `revision_id` | uuid，非空 | 複合 PK `(document_id, revision_id)` |
| `parent_revision_id` | uuid，可空 | `(document_id, parent_revision_id)` FK→同表複合 PK；有值時不得等於自身 ID |
| `origin` | text，非空 | 只准 `initial`／`ai`／`manual` |
| `format_version` | integer，非空 | active設計CHECK為`2`；v1封存不作新格式讀寫，尚未部署所以不安排舊資料migration |
| `engine_profile` | text，非空 | active設計CHECK為`jd-plate-clean-v2`；語意契約升版，套件lock不變 |
| `value` | jsonb，非空 | DB 核 root 為非空 array；完整 schema／grammar／ID／來源另由 App＋固定 Node profile 驗證 |
| `created_at` | timestamptz，非空 | App／DB 記一次建立時間，不以時間排序推算 parent 或 current |

固定額外約束：

- `origin='initial'` **若且唯若** `parent_revision_id IS NULL`；其他 origin 必須有同文件 parent。
- 唯一部分索引 `(document_id) WHERE origin='initial'`，每文件至多一初版。
- 唯一部分索引 `(document_id, parent_revision_id) WHERE parent_revision_id IS NOT NULL`，本版線性工作稿不能對同一父版保存兩個後繼版本。歷史更正仍接 current 產後續版本，不建立分支或讓舊版回當 head。
- **沒有 `producing_operation_id` 欄位或反向 FK。**以 operation 中相同 document／result 且 `status='committed'` 查 producer；初版查不到 producer 是預期。

**D／V 邊界：**以上唯一性只保證「至多」；每個非初版恰有一筆 committed producer，由 §4 唯一寫入交易保證。`JdStore` 不提供 revision UPDATE 或獨立新增孤立非初版的 public port。PK／FK 本身不禁止任意 privileged SQL 竄改，本文不為此新增 trigger 或通用 lineage engine。父版已存在、鎖內核 base／head、只新增版本的協定與測試共同承擔可用版本鏈；不能宣稱自我 FK 單獨證明全鏈無循環。

### 2.3 `jd_operation`

| 欄位 | 型別／可空 | 約束／責任 |
|---|---|---|
| `document_id` | varchar，非空 | FK→catalog；與 operation ID 組成 PK |
| `operation_id` | uuid，非空 | 複合 PK `(document_id, operation_id)`，立即唯一；不以 tool-call 文字或內容相似度去重 |
| `request_digest` | text，非空 | server 計算的 64 字元小寫 SHA-256 十六進位；固定語意表示，不由 Node／模型提供 |
| `origin` | text，非空 | `ai`／`manual`；沒有 initial operation |
| `base_revision_id` | uuid，可空 | 同文件複合 FK→revision；成功／no_change 必須有值，失敗只在已核對合法 base 時有值 |
| `result_revision_id` | uuid，可空 | 同文件複合 FK→revision；成功／no_change 必須有值，持久失敗為 NULL |
| `status` | text，非空 | 只准 §3 的八種可持久終局狀態 |
| `receipt` | jsonb，非空 | 一份既有 `JdWriteResult` 完整終局結果；DB 核 object，App 用 SSOT 驗全形狀及 status×next_action |
| `created_at` | timestamptz，非空 | 本終局回執實際保存時間；同鍵重播不改時間／內容 |

唯一部分索引 `(document_id, result_revision_id) WHERE status='committed'` 限定一新版本最多一個 producer。**不對全部 result 加 UNIQUE**：兩筆 no_change 可以都指同一 base，也可指早先另一 committed operation 產生的版本。

`receipt` 是完整輸出材料，`status`／base／result 是供約束、索引及同文件 FK 使用的有限欄位；沒有第二套結果 schema，native operations／affected IDs／錯誤與 next_action 不再另複製一組獨立可寫欄位。終局 row 不 UPDATE／UPSERT 覆寫；同鍵衝突先讀原 row，PK 唯一違反不能當成覆寫許可。

## 3. 保存狀態、資料條件與對外結果

**D：**table 只保存 confirmed terminal receipt。`receipt_durability` 不另設欄位，receipt 內必為 `confirmed`，且只有 SQL commit 已確認或後續已從 DB 對帳查到時才交給呼叫者。交易內建好 JSON 不等於可以提早回傳成功。

| 可保存 `status` | base／result 欄位 | 正文作用與 receipt 條件 |
|---|---|---|
| `committed` | base、result 非空；result≠base | 同交易新增 result；其 parent=base，origin 相同。effect=`committed`；actual_changes 非空；error 為 JSON null |
| `no_change` | base、result 非空；result=base | 不新增 revision、不更新 head。effect=`unchanged`；actual_changes before=after=base、affected IDs 為 `[]`；error 為 JSON null |
| `invalid_input`／`unsupported_content`／`target_missing`／`stale_base`／`engine_failed`／`save_failed` | result 為 NULL；base 只保留可核實的同文件 base，否則 NULL | 已綁定 operation 的確定失敗；不新增 revision、不更新 head；effect=`unchanged`、actual_changes 為 JSON null、error 非空 |

no_change receipt 的 `native_operations` 固定為 JSON null：候選 editor 可能曾執行淨零 transforms，但沒有已發布的文件變更，不把 transient operations 當成已保存變更。這不抹除既有實驗原始 operations；本版 authoritative changes 仍以完整前後保存版為真相。AI committed 才附確實捕獲且驗證過的 operations；manual committed 為 null，不偽造按鍵紀錄。

下列**不建立 terminal row**：

- 入場前沒有綁定 operation 的格式錯誤／不存在文件／busy；busy 一律 operation_ref=null。
- `outcome_unknown`：文件作用未知、receipt 未确认，保留既有 operation 身分走對帳。
- 已知文件未變但失敗回執還未持久確認：保留原失敗 status、effect=`unchanged`、unconfirmed 及 `reconcile_operation`；不能改稱 unknown，也不能假裝已有終局 row。
- `operation_conflict`：原 operation 已綁不同 payload，**只回當次拒絕 projection**。若原 receipt 已查得，引用其身分；不得以 conflict 覆寫原成功／失敗回執或另插相同 PK。沒有查得持久 receipt 時也不能冒稱 confirmed。

confirmed terminal 的 next_action 沿主線 ER01 的唯一矩陣：committed／no_change→continue；invalid／unsupported→correct_arguments 或 stop；target_missing／stale_base→reread_current 或 stop；engine_failed／save_failed→stop。這些是 mapper 許可值；receipt 一旦保存，其實際 next_action 不隨重播當下剩餘預算改寫，runtime 另執行取消／預算／停止限制。未確認且 operation 已綁定時，只有先對帳，不由模型再猜寫入。

### 3.1 哪些由 DB 強制

**D：**CHECK 只讀同列欄位／receipt，不呼叫來源 owner、不 SELECT 其他列。以下條件都必須得到 true；不得讓遺漏 key 造成 SQL NULL 而通過 CHECK。

1. status 白名單、digest 格式、origin、root JSON 類型及必要非空欄位。
2. receipt 的 status 與欄位 status 相等；operation_ref 是非空 string；receipt_durability=`confirmed`。
3. §3 各狀態對 base／result 的 null／相等／不等条件，以及 effect／actual_changes／error 的型態／JSON null 條件。
4. committed／no_change 的 receipt base／result／change refs 必須存在且為非空 string；actual_changes.origin=欄位 origin，actual_changes.before_revision_ref=receipt.base_revision_ref，after_revision_ref=result_revision_ref。no_change 的 receipt base/result 也必相等，affected IDs 必為空 array、native_operations 必為 JSON null。
5. 持久失敗的 receipt result_revision_ref、change_ref、actual_changes 必為 JSON null；base_ref 的 null／非空與 base ID 可空性對應。其 operation_ref 仍非空，不能套入 pre-binding error。

一般 JSONB 欄位的 SQL NULL、receipt 中的 JSON null 與缺 key 是三種不同狀態；實作以 key 存在／`jsonb_typeof`／明確比較及 true 判定處理，不能只用 `->>` 的 nullable 結果期待 CHECK 自動拒絕。**F：**CHECK 的 NULL 行為及不可跨列限制見 [PostgreSQL 16 Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)（查閱 2026-09-10）。

### 3.2 哪些由唯一 mapper／交易強制

- schema 通過後，mapper 將 receipt 的 operation／base／result refs 解回已綁定 document／internal IDs，逐一等於同列欄位；opaque ref 不能直接拿來跟 UUID 字串比較。change_ref 解析到本次 operation 的確切 before／after pair。
- committed result 的 parent=base、origin/profile 正確、canonical value 通過固定引擎，且有且僅有本次成功 receipt；同一短交易寫入，不以跨列 CHECK 假裝完成。
- 回執建立前核對原生操作與 candidate 來自同一已驗 Node result；manual 不提供假的 operations。`affected_element_ids` 只能來自實際結果／已支持判定，不由 LLM 宣稱。
- digest 對 App 驗證後、包含 document／base／profile／請求語意的既定表示計算；同鍵重送重算比對。時間／候選隨機新 ID 不進語意 digest。人工同鍵保存沿 client 保留的 exact payload，不讀 cache 當 current。
- source_refs 經既有 owner 核對，不複製 source 原文或建立 source junction store；JSONB 值合法不等於來源真實或文件 grammar 正確。

## 4. 固定建立與提交順序

### 4.1 DB01：新文件原子建立

1. 在 Node／App 中先取得已驗 canonical 空 `p`（有 Element ID、空 Text），配初版 ID；不是 `[]`、null 或模型空字串。
2. 同一短 SQL transaction：新增 catalog→新增 `origin=initial`／parent=NULL 的 revision→新增 head 指初版→commit。
3. 只有 commit 確認後才回文件已建立；中途任一失敗全部 rollback。初版無 operation，不造初始 AI receipt。

讀取既有 catalog 若沒有 JD head，回既有有限錯誤流程，不在 read 或普通 write 偷補初版；此方案不遷移舊文件、不建背景補資料任務。完整刪除另走 production authority gate。

### 4.2 已綁定操作：只發布一個終局

1. 先查同文件／operation receipt；同 digest 回原結果，不同 digest 回 conflict projection。沒有 row 才做候選運算；SQL transaction 外完成 Node／來源／profile 驗證。
2. 開啟單次 Read Committed 短 transaction，取得既有同文件 head row lock；**再次查 receipt，先處理同鍵結果，再核 base=head**。查不到必要 head 不視為已鎖定，不能發布。
3. 候選與 base 的 **JSONB 結構相等**，走 no_change：只新增 receipt；不產版、不改 head。
4. 確有改動：新增 revision（parent=base）→新增 committed receipt（result 指新 revision）→更新 head→commit。FK 在每步立即可成立；任一步失敗整個 transaction rollback，沒有中途可見的無回執新版本。
5. 已綁定的確定 validation／engine／stale 失敗，走同一 head／receipt 檢查後只新增失敗 receipt。若先前保存交易已失敗，只在已證原 writer 結束且完整 rollback 後，才容許一筆獨立短交易記錄終局 save_failed；它不能蓋過另一執行者已提交的同鍵 row。
6. 回應遺失或 commit 結果未知，不新增 terminal failure；沿同 operation 查實際結果。已終局 failure 永遠回原 failure，不能在「resume」名義下同鍵變成功。

**D：**不同 operation 使用同 base 同時競爭，head lock 使第一個成功後，另一個在鎖內得到 stale_base。唯一 parent／producer 索引是補強約束，不取代這段協定，也不以唯一違反代替清楚 stale 結果。**F：**交易可原子提交多步；Read Committed 的每句快照及等待後重檢、row lock/deadlock 行為，見 [Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)、[Isolation](https://www.postgresql.org/docs/16/transaction-iso.html)、[Explicit Locking](https://www.postgresql.org/docs/16/explicit-locking.html)（PostgreSQL 16；查閱 2026-09-10）。

## 5. JSONB 相等、重試與持久性的有限界線

**D：**保存判定使用 PostgreSQL 原生 JSONB `=`，將已驗 canonical candidate 以 JSONB 參數與鎖內核對過的 `base.value` 比較；不用 `@>` containment、文字摘要或自製 diff 引擎。objects 的 key 排列不是本 profile 的內容差異；arrays 的元素次序、重複、marks、props、IDs、source refs 都在完整值中。合法 JSON number 的相等以 canonical 結構語意判定，不因 `1`／`1.0` 的文字表示差異產版。Node 的 `changed` 只作診斷，不是保存權威，也不能讓它跳過這個最後判據。digest 仍用既定 Python 請求表示，不能改拿 DB 顯示字串雜湊。**F：**JSONB 的表示與 containment 特性見 [JSON Types §8.14](https://www.postgresql.org/docs/16/datatype-json.html)（PostgreSQL 16；查閱 2026-09-10）。

**D：**v1 每次保存 transaction 一次原始 attempt、零自動重跑 SQL／Node／模型；這是本案保守配置，不冒称官方規定次數。SQL attempt 總控制預算 30 秒，沿既有隔離 DSN 的 connect 5 秒、statement 10 秒、lock 5 秒；statement timeout 不等於整個 transaction 限時。這些本案可配置起始值及取消／停止確認由 ER03 統一執行與錯誤映射。記錄已知失敗的 receipt 是另一個明確記錄動作，不是再次執行失敗的保存命令；該記錄失敗就回 unconfirmed，不迴圈重試。receipt 對帳亦單次查詢、零自動查詢迴圈；查無 row 不代表原寫入已失敗或可解鎖。

`40001`／`40P01` 可識別已中止交易，但本版不因此自行重跑；timeout／斷線不一律等於可證 rollback。未知 commit 只對帳，明確恢復也不得改鍵／換 payload／重跑模型；已有 terminal row 直接返回。若未有 row且需重新嘗試原保存，必須由既有 explicit resume 路徑先證原 writer 已停止及未提交，再遵守同一單次交易協定，不能由模型 `retry` 字樣授權。**F：**官方列出 serialization／deadlock 等錯誤的處理，要求若重試就重試完整交易與決策，不保證所有 unique violation 可重試；見 [PostgreSQL 16 §13.5](https://www.postgresql.org/docs/16/mvcc-serialization-failure-handling.html)（查閱 2026-09-10）。

**D／V：**Task 2 初始化核實實際 PostgreSQL 16 patch、一般 logged tables、`fsync=on` 與本 transaction 的 `synchronous_commit=on`。未滿足時不宣稱 crash-durable receipt；不在正常請求偷偷修改全域設定。官方預設不等於本機已查得。[WAL settings](https://www.postgresql.org/docs/16/runtime-config-wal.html)（PostgreSQL 16；查閱 2026-09-10）。JSONB 無法存入的非法字元／數值不得自動改文，沿 input／save failure 邊界保留原輸入，不能引入自製 codec 補洞。

## 6. Task 2 有限驗收與主線同步

下列是後續實作驗收，**本輪沒有執行**；沿原 `test_jd_postgres.py`／mapper tests，不新增獨立微型 probe：

| 驗收 | 精確結果 |
|---|---|
| 原子初版／中途失敗 | commit 後有 catalog＋唯一初版＋head，沒有 initial operation；每個注入失敗點均全無新增資料 |
| DB02 正反 | committed 一筆產新版；兩個不同 no_change operation 都可指同一 base；第二個 committed producer 指同版被拒，原資料不變 |
| DB03 即時順序 | revision→receipt→head 可按立即 FK 保存；transaction 中途 failure 後沒有孤立非初版、receipt 或變動 head；producer 反查唯一 |
| 同文件／狀態錯配 | 外文件 parent/base/result 拒絕；committed result=base、no_change result≠base、failure 有 result、receipt 與欄位／actual_changes refs 不符均在約定層拒絕 |
| 完整相等 | 相同 canonical JSONB 為 no_change；清單順序、重複項數、文字、marks、props、ID、source refs 有差異便不因包含關係被誤判相等 |
| 終局／重開／失敗 | 同鍵同 payload 原樣回 receipt；不同 payload 只 conflict projection；terminal failure 重開不變成功；failed receipt 未存成功為 unchanged＋unconfirmed，不存假 row |
| 同時競爭／commit 遺失 | 真兩連線同 base 僅一 committed，另一 stale；commit 回覆遺失從新程序查同 receipt，不重跑 Node、不新增 operation／revision |

**主線需同步的 shared 文義：**

1. 主設計／ADR／Task 2 的「revision 保存產生操作引用」改為「非初版由唯一 committed receipt 反查產生操作；不在 revision 重複保存反向 FK」。保留正文的 origin／profile／parent。
2. no_change 只引用 base，不產版；部分唯一限制僅套 committed。DB 約束＋mapper／交易核值與 SSOT 型別驗證分開。
3. confirmed terminal 只收 §3 八種狀態；busy 無 op、unknown 非終局、conflict 不覆写原 receipt，已知未變但 receipt 未確認仍是 unchanged。
4. ER03 是唯一 timeout／恢復策略來源；本附件固定單次保存及零自動 rerun，不另建立競爭的 retry engine。

其餘 profile、來源 owner、單畫面、人編與 AI admission、Memory authority gate 不變。DB02–04 可据此進入既有切片施工；設計閉合不代表尚未執行的 DDL、交易與跨程序恢復測試已通過。
