# JD：共同編輯到真實保存的交易切片

- 日期：2026-09-13；Topic：JD-R002；RS-1／RS-2 隔離實作。
- 承接[結果與十三表基礎](2026-09-13-jd-result-and-storage-foundation.md)、[保存契約](2026-09-12-jd-relational-schema-and-write-contract.md)、[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。
- **已接通八個編輯操作、目前內容讀取、版本／操作保存及 failure-only 資料庫收尾。**入口仍是 Python 內部 service；未提供 App 畫面／HTTP endpoint／正式 refs，也未接顧問或真程序停止證明。沒有修改正式 authority 或舊資料，0 產品模型呼叫。

## 1. 使用效果與實作責任

同一份 JD 可以新增完整任務、分列成果與要求、關聯共享 K/S，再持續修改、移動與刪除。人與模型的八個具名 command 使用同一 `prepare_edit`／domain；它產生候選，保存 service 才能產生確認結果。框架保留替換空間，沒有因此改六章或管理方式。

| 元件 | 本次已完成的責任 | 沒有承擔的責任 |
|---|---|---|
| [snapshot SSOT](../../experiments/jd-relational-app/contracts/jd-snapshot.schema.json)／[codec](../../experiments/jd-relational-app/src/jd_relational/snapshots.py) | 固定 v3／jd-relational-v1、完整欄位及穩定 IDs；嚴驗後在 arrays 與 domain keyed rows 間轉換；拒絕未知欄／版本／重複 ID／錯關係 | 不推論工作、不正規化舊稿成新事實、不發 refs 或保存 |
| [固定意圖](../../experiments/jd-relational-app/src/jd_relational/intents.py) | App 配發 operation ID；固定 command 與可信 context 副本；對穩定目標、base、origin/run 及內容計算 request digest | 不驗外部 token 真偽、不取得 writer gate、不自行呼叫來源 owner |
| [九組 current mapper](../../experiments/jd-relational-app/src/jd_relational/storage/rows.py) | 同文件增量 INSERT／UPDATE／DELETE；完整 final row 一次更新，未改列不寫；共用 snapshot/domain 驗證 | 不開連線／commit；不做通用 repository 或歷史 restore |
| [永久回執型別](../../experiments/jd-relational-app/src/jd_relational/storage/receipts.py) | SQL row 擁有 identity/base/result；Python 內部 versioned body 保存 command kind、固定 error／next action；讀回核外部結果 SSOT 的合法組合 | 不保存短效 token；內部 ID 不直接充當 API refs |
| [transaction service](../../experiments/jd-relational-app/src/jd_relational/storage/service.py) | 新建／查回文件、同版 current read、原 operation 查回、一次保存與 failure-only 收尾；安全診斷 | 不建立第二套 runtime／Memory、不重播 mutation、不替 caller 證明程序停止 |

body 是只有 Python producer/consumer 的內部持久型別，使用既有 Pydantic 明確 model；符合[契約策略](../contract-strategy.md)的 shared typed module 分界。跨語言 snapshot／外部 result 仍是 JSON Schema 生成，沒有改成手寫 Web 型別。snapshot 根保存 document scope，row 不重複 scope；當前 revision 不放 content digest，避免同內容因版號不同被誤認為有變。

## 2. 保存與恢復契約如何落實

### 原意圖與原結果

`bind_edit` 先以既有 generated schema 驗八工具；command 是可獨立取用的副本，Ref／Source／Selection mapping 也複製並唯讀。摘要把已驗 JD token 映為穩定 typed identity；selection 使用 field identity、原生 UTF-16 範圍及原全文／選取摘要。來源 token 沿 source owner 身分，不自行翻譯。重新發出不同 JD token 指同一目標時，意圖不變；修改 base/run/目標/內容時則不同。未使用的 context refs 與 ID 產生器狀態不影響摘要。

執行先讀同 operation；已存在則驗 digest、回原回執，不重新驗候選／新 head／writer 資格。同 key 不同意圖回 operation_conflict，原回執不動。過去成功後查回連線故障仍可能已成功，不能因本次未連上 DB 就回 unchanged。

### 一次寫入

短 READ COMMITTED，document→head 行鎖在 savepoint 前；等鎖後以**下一 SQL statement**重查原 operation。鎖後再核 writer 與封存狀態；違反已 binding 資格只保存 save_failed，不重回無 binding 的 busy。鎖等待本切片固定 5 秒為有界起始值，不宣稱供應商推薦此秒數。

同 savepoint 內組完整候選、驗規則、增量改 current、由實際 rows 重建 snapshot，核與候選相同。相同 digest 時 rollback 候選、只保存 no_change；有變時依序新增 revision(parent=base)、committed receipt、更新 head。只有外層 COMMIT 確認才回 confirmed。

Domain 具名拒絕先 rollback savepoint，再保存 failure receipt。DB 只將已明列的 K/S RESTRICT 約束映為 dependent_items；未知 SQL／程式問題不得變成使用者輸入錯誤。一般 row mapper 的 UPDATE／DELETE 檢 matched rowcount=1；單列 INSERT 不把 -1 rowcount 誤判為失敗。

### 不明結果與 failure-only 收尾

尚未跨原 operation barrier 查明不存在前，讀取／連線失敗維持 unknown。候選整筆 rollback 已確認，才回 unchanged；外層 COMMIT 成功但未收到確認時，有正文變更者維持 unknown。若只在提交 no_change／failure receipt，JD 效果已證 unchanged，但回執仍 unconfirmed，須 reconcile。

`reconcile_stopped` 要求 caller 的 `WriterAuthority.require_stopped`，在 document→head 鎖與後續 statement 查回後再次核實；真回執優先。確認無回執才以原 identity/digest 寫 save_failed，沒有重新執行 command 或 LLM。缺 proof／缺 head／DB 故障不能宣稱終局。**本輪 authority 為明示合成替身，尚未驗證 OS 程序停止、取消或正式 run owner。**這個 port 不能直接由 HTTP boolean 代填。

### 同版讀取與可維護性

current read 在第一個 query 前設 READ ONLY REPEATABLE READ；讀 document/head/revision 與九組 current，核 snapshot／digest／版本一致後才回。沒有跨 UI 或模型持有交易。新程序可重讀已保存內容與原回執，無須獲得 writer 權限。

診斷只記 App 配發 document／operation、固定 phase／outcome、是否確認及耗時，不記 JD／工具參數／來源／原始 driver exception。logging sink 故障不取代已保存或未確認結果。讀取及停止 proof 失敗使用固定 code，阻斷原 exception chain；log 不是回執權威。

## 3. 官方依據與本案選擇

本輪 2026-09-13 重核以下一手文件；穩定版本／授權沿[資料層前置](evidence/2026-09-13-jd-relational-db-preflight.md)，未新增依賴或升級。SQLAlchemy 2.0.52、Alembic 1.20.0、Psycopg 3.3.5、PostgreSQL 18.6 維持前次精確 lock／image。

| 來源 | 有限支持與採用分界 |
|---|---|
| [AWS idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | 原 request identity 與原語意結果、同 token 不同意圖的處理原則。JD 用自己的 document/operation/digest 契約；不等於 AWS 指定這十三表或允許不查明即重播。 |
| [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/core/connections.html#using-transactions)／[rowcount](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.CursorResult.rowcount) | 明示外層 transaction／savepoint 及 matched-row 語意；rowcount 主要可靠用於單組 UPDATE/DELETE，INSERT 可為 -1。直接使用原生 Core，不自行造 transaction framework。 |
| [PostgreSQL 18 locks](https://www.postgresql.org/docs/18/explicit-locking.html)／[isolation](https://www.postgresql.org/docs/18/transaction-iso.html) | 行鎖、savepoint rollback 對鎖的影响、READ COMMITTED statement 與 REPEATABLE READ snapshot。固定鎖序與停止後 failure-only 是本案既定組合，不是 DB 自動理解 JD operation。 |
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)／[Claude tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls) | 工具由 App 執行並回原 call 的真實結果；App 承擔已知資訊與錯誤接點。沒有公開資料證明兩家採相同 SQL 表、摘要格式或 ref signer。本輪未改供應商 API、未呼叫 provider。 |

## 4. 首敗、實測與獨立審查

所有 DB 操作只在 `127.0.0.1:55436/caliburn_jd_relational_test` 合成資料；未動正式 DB。正文保存與COMMIT是真 PG；故障由 SQLAlchemy event／driver commit wrapper 注入。成功 COMMIT 後故意丟回覆是在真 DB 提交後注入客戶端例外，不是假 fixture 回成功，也不是實際網路斷線演練。

| 範圍 | 最後實際結果 |
|---|---|
| 完整離線 suite | **525 PASS／51 PG cases SKIP**，未把 skip 算 PASS；含 snapshot 45、intent 49、receipt 14、mapper 13 等，舊結果不累加 |
| mapper＋service 真 DB 接合 suite | **42 PASS＝13 離線 mapper＋11 真 PG mapper＋18 真 PG service**；18 中含新程序用 service 續讀 |
| 末次固定錯誤 code／proof failure 包裝窄驗 | 5 PASS／13 deselected，為前述 service 內的受影響案例，非另增五個成果 |
| codegen／TypeScript | check PASS，既有非 snapshot 六個生成檔雜湊未變 |
| 獨立審查 | mapper PASS；service／receipt PASS，另做 12 組程序內假連線／交易控制流反例 PASS，與真 DB 數分開 |

已驗效果：八工具連續保存、尚未知的內容可 null、來源 basis 保留、D01／跨職責移動、共享 K/S 解除與保留、整個意圖重送不重複新增、同 base 競爭一成功一過時、不同文件獨立寫入。一般修改未整份刪光重建。

故障例：task/revision/operation/head SQL 後各注入失敗，確定指定點實際命中一次；正文／head／回執全部回滾。savepoint 拒絕後，在 failure receipt 尚未提交時用另一連線 NOWAIT 證明 document/head 鎖仍保留。已提交的內容／失敗回執丟確認、接著原 operation 查回連線失敗、缺停止 proof、壞 log sink及新建初始資料後失敗均有反例。

首敗保留：snapshot／intent／rows 入口未就緒時各 collection error；mapper 真 PG 首次 7 FAIL／13 PASS，原因 INSERT rowcount=-1，依官方接點修正。service 首次受此共同 mapper 問題為 5 FAIL／8 PASS；旅程另有舊 move/delete fixture key，已按 SSOT 修正。intents 擴案例時換 token helper 誤改 literal kind 的 1 FAIL／48 PASS 只修測試，最終49 PASS。snapshot 基線114／加45共159 PASS不另累加。

獨立 service 審查指出「原 COMMIT 不明後，查回連線失敗被誤判 unchanged」P1；改以跨 barrier 後的原結果觀察判斷，並補真 commit／查回故障案例通過。所有已知 findings 已修正，沒有因此把 lookup 問題變成重寫命令。

文件窄審另發現工具／保存契約舊文將 unknown 限於 COMMIT 遺失，或漏掉只提交無內容變更回執的分支；兩處已同步上述三分法，避免後續投影接線回歸同問題。snapshot 排序亦按實際 codec 精確記錄；獨立文件窄複核 PASS，不因文件修正重跑無變更的程式測試。

## 5. 下一工作與尚未完成的成品要求

下一工作接**正式讀取投影／refs／history/change read**，讓員工及 AI 可取得新版正確定位、確切前後差異及人工變更；並將停止／admission port 接實際 run owner。需要有界驗證 signer／游標與資料集還原身分，按[讀取前置](evidence/2026-09-13-jd-read-reference-preflight.md)處理，不重開同層品牌比較。

尚未完成：catalog 更名／封存 API、整份還原／整輪 AI 撤回、HTTP／Web CRUD、自動保存 dirty buffer、顧問接線、OS 取消／重啟恢復、備份還原、自然模型與真人驗收。上述保持原範圍；不得把本切片當完整 App 或正式權責切換。Excel 延後有效。
