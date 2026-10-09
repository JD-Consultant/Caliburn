# 業務、資料及契約接線

- 狀態：**現行業務、資料及契約的接線原則** 。具體保存分別由[訪談](interview-storage.md)、[JD](jd-storage.md)及[Memory](memory-storage.md)文件說明；正式 DDL 與生成契約由程式維護。
- 語意權威：[資料保存與交易](../architecture/persistence.md)、[Memory 單向調度](agent-supervision.md)、[JD 工具與保存](jd-storage.md)。本頁只說接線方式。

本頁從人工與模型工具共用的業務入口開始，說明短交易、原操作結果、Memory 發布及 JD 完成如何接在一起。具體資料表與保存演算法由各保存文件維護，這裡說明它們必須共同遵守的接線規則。

閱讀路徑：[共用用例](#1-一個-service一個正式結果兩種入口) → [交易與原操作](#2-sql交易責任) → [Memory](#3-memory可變工作稿與固定快照不是兩個相反模型)／[JD](#4-jd關聯式候選來源與正式完成) → [契約生成](#5-唯一契約來源及生成)／[遷移與恢復](#6-資料演進與恢復)。

## 1. 一個 service、一個正式結果，兩種入口

人工 HTTP 與 Agent tool 各自轉譯輸入，呼叫同一領域用例，因此同一種修改遵循相同的業務規則。用例輸入包含 App 綁定的檔案／執行資格、解析後的內部目標、型別化修改與原操作辨識；模型不填這些執行值。

用例回傳有型別的實際結果，HTTP 將它投影為 DTO，模型工具則投影為精簡文字。模型可見的 `updated` 是成功確認；恢復時仍查原業務結果，不能把這段文字當成資料庫保存的唯一憑據。

三種識別各有用途：client command ID 辨認瀏覽器重送同一命令，模型 `call_id` 配對 function output，業務 operation ID 則用來查回原操作效果。這些用途須分清，但不強制三張表或三套 registry。operation identity 在派送前須可恢復；重新進入時沿用原目標，不重新解析已改名的 target_title。

## 2. SQL／交易責任

單庫短交易預設從 PostgreSQL Read Committed＋顯式條件／短行鎖開始驗證，不以 Serializable 包住整輪。跨列不變量以唯一鍵、FK、檔案／候選控制列鎖或條件更新保障；Serializable 只有具體反例需要時局部採用，serialization failure 由原操作重試而非重跑 LLM。所有可見資料均檢查 job_file scope。

業務服務定義「一次必須成立什麼」，SQL adapter 實現原子性。工作流開短交易，相關服務參與同一 session，內層不提交；模型、串流、PDF、等待使用者及重試 backoff 期間不得持有該交易。

DB pool connection 與 Graph checkpointer connection 各自管理，不能假設 saver 與業務共享 transaction。[PostgreSQL](https://www.postgresql.org/docs/current/transaction-iso.html)、[SQLAlchemy async session](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)

**每筆具副作用操作的共同接法：**

1. 先以 scope＋原操作身分查已成立結果；有結果就校驗原 payload 一致並回它，不拿 latest 代替。
2. 未能確認時不能當未執行。取得本操作所需的資格／短鎖，重新查原結果，排除仍在途或舊 writer。
3. 校驗執行仍有效、候選位置／權限及該領域不變量；在記憶體暫算修改。
4. 同一交易保存候選位置、效果及原結果；COMMIT 確認不明再查原操作。相同 ID 不同內容拒絕。
5. Graph 接回該結果；Graph 落後不重新產生業務效果。

不把這五步造為任意任務都可回滾的框架。共用 transaction／operation plumbing 可抽小函式，領域命令與 validator 仍各自維護。一次修改多欄全成／全拒；一 Step 多筆工具是多筆操作，不能誤稱整 Step 一個 DB transaction。

## 3. Memory：可變工作稿與固定快照不是兩個相反模型

Memory 領域模組擁有候選、固定修訂、快照及原操作。工具先把模型的標題定位轉成受限範圍內的穩定身分；workflow 協調執行資格，原操作重入沿用已固定命令。候選的動態綁定與發布後的固定引用由同一領域模組處理。

| 要修改的責任 | 維護位置 |
|---|---|
| 標題解析、A／B1／B2 可見基準、prepare／execute | [Memory 工具接線 §2–4](memory-tools.md#2-固定基準與候選最新位置) |
| 候選位置、修訂重用、固定來源與 map 投影 | [Memory 保存 §2](memory-storage.md#2-保存表示固定修訂而非資料庫舊列) |
| 來源、名稱、角色權限與全成全拒 | [Memory 保存 §3](memory-storage.md#3-交易與讀取邊界) |
| B1 → B2 交接、引用固定化與原子發布 | [Memory 保存 §5](memory-storage.md#5-候選交接與發布接線) |
| 正式歷史及候選的保留用途 | [保存架構 §6](../architecture/persistence.md#6-保留失效與清理) |

發布前的大額純計算可在交易外對固定位置完成，提交時再核位置及資格。交易內由 workflow 協調快照、涵蓋邊界、原發布結果與正式 head 一起成立，不能以多次讀取 latest 拼成發布結果。具體選用及引用演算法由上述保存文件維護。

## 4. JD：關聯式候選、來源與正式完成

JD 以 profile、職責、任務、成果、要求、知識、技能及關係建立型別模型，欄位意義沿[產品內容判準](../product/concepts.md#內容判準)，schema 不從 Memory Markdown 或 UI widget 反推。舊 SQL／測例只供參考，沒有相容表名義務。人工及模型入口共用 JD 領域模組；模型工具寫入候選，A 完成交易才正式採用，不能借人工正式 API 提前寫入正式稿。

候選位置、分支回退與採用由 [JD 保存 §3.1](jd-storage.md#31-本輪候選與可恢復位置)維護；模型定位及來源解析見[工具接線 §3.2–3.3](jd-storage.md#32-模型導覽與既有物件定位)，差異與明確核對見[來源接線 §3.5](jd-storage.md#35-來源及人工改稿差異)。`read_ref`、`target_title`、`citation_ref` 各自解析不同責任所擁有的資料，不能靠同名猜測身分。跨層呼叫傳入固定基準，資料解析及合法性仍由各領域判斷。

完成 A 由 [ConsultantCompletionWorkflow](../../apps/api/src/caliburn/workflows/consultant_completion.py)開啟同一短交易，協調[架構交易表](../architecture/persistence.md#3-交易邊界)所列參與者；Plan 以 `validate_final` 核對原位置，其後輪資格依共同完成結果成立，不另提交一份 Plan 正式 head。序號使用檔案內受交易保護的分配，不直接依會跳號的全域 sequence 保證取消不佔號。完整已公開中間訊息另按回看政策保留，無正式序號、不作依據。

取消、人工寫入准入及完成後撤回是不同用例，依 [JD 保存](jd-storage.md)及[正式採用與交易](../architecture/persistence.md)的資格與交易執行；本頁不再展開其產品規則。

## 5. 唯一契約來源及生成

`apps/api/contracts/http/` 保存跨語言 DTO，`contracts/tools/` 保存模型可見 schema。Schema 與描述按業務拆，不每參數一檔。鎖定 datamodel-code-generator 產 Python DTO，json-schema-to-typescript 產 TypeScript；OpenAPI 從 API 的生成型別形成，不再手寫 OpenAPI／TS／Pydantic 三份 shape。HTTP／tool 邊界仍做執行時驗證，TS 型別不代替它。[現行策略](../standards/contract-strategy.md)的原則保持，路徑不同不接回退役 package。

[`generate_contracts.py`](../../apps/api/scripts/generate_contracts.py)維護下列生成物；執行及檢查命令見 [API README](../../apps/api/README.md)。

| 生成物 | 位置與用途 |
|---|---|
| Python DTO | `apps/api/src/caliburn/contracts/generated/`；工具型別位於其 `tools/` 子目錄 |
| TypeScript 型別 | `apps/web/src/shared/api/generated/`；工具型別位於其 `tools/` 子目錄 |
| Canonical schema 資源 | `apps/api/src/caliburn/contracts/generated/{http,tools}/*.schema.json`；保留原相對參照，供安裝後的 runtime guard 與工具定義讀取 |
| DTO／資源索引 | `apps/api/src/caliburn/contracts/generated/schema-manifest.json`；生成的 root DTO 全名對應 canonical 資源路徑 |

Web 使用同一份 HTTP schema 驗證回傳，再放入查詢快取，不手寫第二份資料 shape。

依 [canonical 契約政策](../standards/contract-strategy.md)，HTTP request body 經 FastAPI 的 `Annotated[DTO, canonical_body(DTO)]` 接縫；Tool JSON 經 `contracts.validation.parse_contract(DTO, arguments)`。兩者由 `Draft202012Validator` 與 `FormatChecker` 對 canonical 原始值先驗證，通過後才呼叫 `model_validate(..., strict=False)`。因此 `StrictInt` 生成欄位可轉換 schema 合法的 `1.0`，布林、字串與額外欄位仍由 schema 拒絕；不手改 DTO 或逐欄新增 validator。HTTP 的型別／OpenAPI 仍沿原 DTO，領域規則與角色 scope 仍留在原責任模組。

runtime guard 由 `importlib.resources` 讀取包資源，官方 `referencing.Registry` 只登錄包內 schema，未配置任何外部 retriever。`jsonschema[format-nongpl]` 是鎖版正式相依；所有 canonical format 都必須有已安裝 checker，缺少時失敗，不靜默略過。驗證錯誤只保留安全種類與 schema 路徑，不轉送 validator 的輸入正文、message 或 cause；Tool 繼續回原本的可行修正指引。schema 已接受、DTO 卻無法表示時屬內部契約錯誤，以安全 `RuntimeError` 中止，不能冒充使用者參數錯誤。Python 用 `FormatChecker.checks`、Web 在唯一 `shared/api/schema-policy.ts` factory 用 Ajv `addFormat` 接上標準 UUID 表示檢查，排除套件額外容許的 URN 或多餘連字號。各 feature 仍擁有其 schema 與編譯後 guard，不各自重建接受政策，也不讓 shared 反向依賴 feature。

模型 schema 與 HTTP 不強求相同：HTTP 需要保存／預覽狀態，tool 只回推理下一步所需資訊。模型 strict wire 是薄編譯邊界：有限 variants、required／additionalProperties 按 provider 子集，語意上未列 change 仍是保留，不把 null 當清空。生成後以真 SDK payload 驗，而非只測 Python class 建得出來。

生成器亦將 HTTP／tools 原 schema 與索引寫為安裝包內唯讀資源，`--check` 驗 byte 一致；provider definitions 使用 tools 的同一份生成副本，不從 DTO 再生另一個 shape。離線 SDK payload 不等於遠端 strict 接受；實測範圍依 [Memory 工具接線](memory-tools.md)。

原始 Responses items 不塞進自製 message schema；按官方 SDK output→input 轉換後保留必要 metadata、opaque bytes 與順序，兩種方向各有 round-trip 測例。生成檔不手改；CI 再生成比 diff。實際 wire 以 schema、生成物與對應驗證為準。

## 6. 資料演進與恢復

新產品使用新的 PostgreSQL database／schema namespace 與 fresh migrations，沒有舊資料 ETL。Alembic autogenerate 是候選 migration，需人工／Agent 審閱及真 PG 空庫升級測試；它不自動理解所有 rename 或 data change。[Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)

首版不自動清理候選／checkpoint，也不新增備份產品；保留邊界仍需可測。新 migration 前 fail fast 檢查 DB 版本與配置；schema 不相容不得帶著半套表啟動。框架 saver schema 用官方 setup／upgrade 路徑，不在業務 Alembic 中手抄其結構。

取消與最後提交使用相同持久資格裁決；重啟時舊 runner 的資格不得沿用到新 attempt。writer fencing 由 executions 執行資格模組 的行鎖與條件更新實現，程序接管依[執行接線 §6](agent-execution.md#6-本機-a-supervisor)，不把 Python mutex 當跨程序保存保證。未知 COMMIT 要對帳，不能因查詢超時便把目前表頭回退。
