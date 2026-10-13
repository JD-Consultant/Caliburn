# 業務、資料及契約接線

- 狀態：**現行業務、資料及契約的接線原則**。具體保存分別由[訪談](interview-storage.md)、[JD](jd-storage.md)及[Memory](memory-storage.md)文件說明；正式 DDL 與生成契約由程式維護。
- 語意權威：[資料保存與交易](../architecture/persistence.md)、[Memory 單向調度](agent-supervision.md)、[JD 工具與保存](jd-storage.md)。本頁只說接線方式。

本頁說明人工與模型工具如何共用業務入口，以及短交易、原操作結果、Memory 發布與 JD 完成之間的接線規則。具體資料表與保存演算法見上述保存文件。

閱讀路徑：[共用用例](#1-一個-service一個正式結果兩種入口) → [交易與原操作](#2-sql交易責任) → [Memory](#3-memory可變工作稿與固定快照不是兩個相反模型)／[JD](#4-jd關聯式候選來源與正式完成) → [契約生成](#5-唯一契約來源及生成)／[遷移與恢復](#6-資料演進與恢復)。

## 1. 一個 service、一個正式結果，兩種入口

人工 HTTP 與 Agent tool 各自轉譯輸入，呼叫同一領域用例，因此同一種修改遵循相同的業務規則。用例輸入包含 App 綁定的檔案／執行資格、解析後的內部目標、型別化修改與原操作辨識；模型不填這些執行值。

「共用」指領域規則與保存責任相同，不要求兩種入口呼叫完全相同的 workflow。人工 JD 修改正式稿，A 修改本輪候選；各自核對准入，之後重用 JD 的內容規則及固定修訂。

用例回傳有型別的實際結果，HTTP 將它投影為 DTO，模型工具則投影為精簡文字。模型可見的 `updated` 是成功確認；恢復時仍查原業務結果，不能把這段文字當成資料庫保存的唯一憑據。

HTTP 的同形內部 dataclass 直接用 Pydantic `model_validate(..., from_attributes=True)` 讀取 DTO 宣告的屬性，避免先以 `asdict()` 遞迴複製；需加欄位或組合資料的投影仍明示轉換。這只用於已實體化的內部結果，不讀 ORM lazy attributes，也不代替外部 JSON 的入站驗證。內部額外屬性不外送，DTO 欄位與巢狀型別仍須通過驗證。依據：[Pydantic attribute validation](https://pydantic.dev/docs/validation/latest/concepts/models/#arbitrary-class-instances)。

三種識別各有用途：

- client command ID 辨認瀏覽器重送的同一命令。
- 模型 `call_id` 配對 function output。
- 業務 operation ID 用來查回原操作效果。

用途須分清，但不強制建立三張表或三套 registry。operation identity 在派送前須可恢復；重新進入時沿用原目標，不重新解析已改名的 target_title。

## 2. SQL／交易責任

### 隔離與交易範圍

單庫短交易預設從 PostgreSQL Read Committed＋顯式條件／短行鎖開始驗證，不以 Serializable 包住整輪。跨列不變量以唯一鍵、FK、檔案／候選控制列鎖或條件更新保障；所有可見資料均檢查 job_file scope。

Serializable 只有具體反例需要時局部採用，serialization failure 由原操作重試而非重跑 LLM。

業務服務定義「一次必須成立什麼」，SQL adapter 實現原子性。工作流開短交易，相關服務參與同一 session，內層不提交；模型、串流、PDF、等待使用者及重試 backoff 期間不得持有該交易。

一般業務提交與 Graph checkpoint 分別保存，不能假設兩者共享 transaction。整檔刪除是明示的例外：Saver 借用當前業務連線，一起刪除該檔案的 checkpoint，詳見[刪除接線](interview-storage.md#11-整份職務檔案刪除)。連線及 session 的並行界線依 [PostgreSQL](https://www.postgresql.org/docs/current/transaction-iso.html)與 [SQLAlchemy async session](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)。

### 原操作與提交保證

各領域維持相同的提交保證，鎖與原結果查詢的具體先後由用例決定：

| 邊界 | 必須維持的保證 |
|---|---|
| 原結果 | 以 scope＋原操作身分定位，再校驗完整原意圖；相同 ID 不同內容拒絕。已成立時回原結果，不拿 latest 代替。 |
| 新寫入 | 在所需短鎖內核對准入、writer、候選位置及領域不變量；鎖外讀取不能取代提交前檢查。 |
| 共同提交 | 效果、新位置及原操作結果全成或全退。查詢或 COMMIT 結果不明時先查原操作，不能推定尚未執行。 |
| 接續 | Graph 接回正式操作結果；checkpoint 落後不授權重複產生效果。 |

例如人工 JD 先鎖檔案、查原結果，再核新寫入准入；Memory 修改先核活躍 writer，才進入候選用例核對原操作。原結果重播不等於取得新的寫入資格。各用例的實際順序見對應保存文件。

共用交易協調可抽成小函式，領域命令與 validator 仍各自維護；不擴成任意任務回滾框架。一次修改多欄須全成／全拒；一 Step 多筆工具是多筆操作，不能把整 Step 稱為一個 DB transaction。

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

JD 以 profile、職責、任務、成果、要求、知識、技能及關係建立型別模型，欄位意義沿[產品內容判準](../product/concepts.md#內容判準)，schema 不從 Memory Markdown 或 UI widget 反推。人工及模型入口共用 JD 領域模組；模型工具寫入候選，A 完成交易才正式採用，不能借人工正式 API 提前寫入正式稿。

候選位置、分支回退與採用由 [JD 保存 §3.1](jd-storage.md#31-本輪候選與可恢復位置)維護；模型定位及來源解析見[工具接線 §3.2–3.3](jd-storage.md#32-模型導覽與既有物件定位)，差異與明確核對見[來源接線 §3.5](jd-storage.md#35-來源及人工改稿差異)。

`read_ref`、`target_title`、`citation_ref` 各自解析不同責任所擁有的資料，不能靠同名猜測身分。跨層呼叫傳入固定基準，資料解析及合法性仍由各領域判斷。

A 的完成交易由 [ConsultantCompletionWorkflow](../../apps/api/src/caliburn/workflows/consultant_turns/completion.py)開啟，在同一短交易內協調[架構交易表](../architecture/persistence.md#3-交易邊界)所列參與者。Plan 以 `validate_final` 核對原位置，其後輪資格依共同完成結果成立，不另提交一份 Plan 正式 head。

序號在檔案內分配並受交易保護，不直接依賴會跳號的全域 sequence 保證取消不佔號。完整已公開中間訊息另按回看政策保留，無正式序號、不作依據。

取消、人工寫入准入及完成後撤回是不同用例，依 [JD 保存](jd-storage.md)及[正式採用與交易](../architecture/persistence.md)的資格與交易執行；本頁不再展開其產品規則。

## 5. 唯一契約來源及生成

### 來源及生成物

HTTP 以 [Pydantic models](../../apps/api/src/caliburn/transport/http/models/) 為唯一可修改來源。路由宣告 request／response 型別及固定 operation_id，FastAPI 導出 OpenAPI；工具以 [JSON Schema](../../apps/api/contracts/tools/) 為唯一來源。領域／workflow 不依賴 HTTP 型別，HTTP 共用 JD 查閱值及工具的 InterviewPlan 值，避免候選預覽另複製 shape。

[`generate_contracts.py`](../../apps/api/scripts/generate_contracts.py) 是唯一生成與 readonly check 入口；命令見 [API README](../../apps/api/README.md)。

| 生成物 | 位置與用途 |
|---|---|
| HTTP SDK／TypeScript | `apps/web/src/shared/api/generated/http/`；Hey API 按 OpenAPI 生成具名 SDK、型別及 fetch client |
| HTTP Web 驗證函式 | 同目錄的 `validators.js`／`validators.d.ts`；Ajv standalone 從同一 OpenAPI 生成 |
| 工具 Python／TypeScript | `apps/api/src/caliburn/contracts/generated/tools/` 與 `apps/web/src/shared/api/generated/tools/`；沿既有 datamodel-code-generator／json-schema-to-typescript |
| 工具 Schema 資源／索引 | Python generated 的 `tools/*.schema.json` 與 `schema-manifest.json`；安裝後准入及 provider 工具定義共用 |

HTTP 匯出不啟動 lifespan、資料庫或模型；Node [生成器](../../apps/web/scripts/generate-http-contracts.mjs)只接本機解析後的 OpenAPI object，不向 Registry 傳送規格。Hey API 接手 endpoint／method／body 組裝；Ajv 官方 standalone 產碼經 Vite 打包為自包含 ESM，瀏覽器不編譯 Schema。生成碼不手修、不另存手寫 HTTP Schema。

`--check` 在暫存目錄生成並比對全部產物，不修改正式檔案；`--schema` 只限定工具 DTO，HTTP 每次全量生成。工具原 Schema、索引與生成物保持一致，過時產物須移除。依據：[FastAPI body／OpenAPI](https://fastapi.tiangolo.com/tutorial/body/)、[Hey API SDK](https://heyapi.dev/docs/openapi/typescript/plugins/sdk)、[Ajv standalone](https://ajv.js.org/standalone.html)。

### 執行時驗證與安全錯誤

HTTP body 直接由 Pydantic 驗證，共用 wire 值型別明定數學整數、標準連字號 UUID 及 Unicode 文字政策，再導出 OpenAPI。新增限制須核 Python 與 Web 的接受集合；詳見[契約策略](../standards/contract-strategy.md)。輸入失敗由共用 RequestValidationError handler 回固定安全422，禁止回顯 input、未知欄位 loc、message 或 cause；回應型別失配屬內部錯誤，不冒充使用者錯誤。

Web [HTTP policy](../../apps/web/src/shared/api/http.ts)接官方 client hooks，管理 timeout、caller abort、安全錯誤及 request correlation。SDK 返回前先跑 OpenAPI 驗證，再核具名 scope predicate；成功但檔案／execution／command 不符的回應不得進入 query cache。TanStack Query 仍負責既有 cache keys、失效與 polling，SDK 不接管業務命令恢復。PDF、204與原生 EventSource 沿各自媒體／生命週期處理。

工具 JSON 經 `contracts.validation.parse_contract(DTO, arguments)`：官方 Draft202012Validator 先核 canonical 原始值，再呼叫 `model_validate(..., strict=False)` 做已驗值的表示轉換。工具 Schema 目前無 format 關鍵字，不保留 HTTP 專用的 runtime format 接線；新增此類限制時須同時引入對應驗證及反例。

工具 guard 由 importlib.resources 讀包內資源，官方 referencing.Registry 只登錄這些資源，不配置外部 retriever。拒絕時只保留安全種類與 Schema 路徑，保留既有可行修正指引。Schema 接受而 DTO 無法表示時屬內部契約錯誤，以安全 RuntimeError 中止。原件、writer、版本及角色資格仍由業務 owner 判定。

### 模型 wire 與原生 items

模型 schema 與 HTTP 不強求相同：HTTP 需要保存／預覽狀態，tool 只回推理下一步所需資訊。模型 strict wire 是薄編譯邊界：有限 variants、required／additionalProperties 按 provider 子集，語意上未列 change 仍是保留，不把 null 當清空。生成後以真 SDK payload 驗，而非只測 Python class 建得出來。

provider definitions 使用 tools 的同一份生成副本，不從 DTO 再生另一個 shape。離線 SDK payload 不等於遠端 strict 接受；實測範圍依 [Memory 工具接線](memory-tools.md)。

原始 Responses items 不塞進自製 message schema；按官方 SDK output→input 轉換後保留必要 metadata、opaque bytes 與順序，兩種方向各有 round-trip 測例。生成檔不手改；CI 再生成比 diff。實際 wire 以 schema、生成物與對應驗證為準。

## 6. 資料演進與恢復

### 遷移與啟動檢查

現行 `0034_jd_task_sources` 以空 PostgreSQL database／schema namespace 初始化，拒絕含子項來源 owner／`target_task_id` 的舊 layout，沒有舊資料 ETL 或雙讀。Alembic autogenerate 是候選 migration，需人工／Agent 審閱及真 PG 空庫升級測試；它不自動理解所有 rename 或 data change。[Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)

目前不自動清理候選／checkpoint，也不提供備份產品；保留邊界仍需可測。migration 與 App 啟動檢查 DB 版本及配置；schema 不相容不得帶著半套表啟動。框架 saver schema 用官方 setup／upgrade 路徑，不在業務 Alembic 中手抄其結構。

### 取消、接管與未知提交

取消與最後提交使用相同持久資格裁決；重啟時舊 runner 的資格不得沿用到新 attempt。writer fencing 由 executions 執行資格模組的行鎖與條件更新實現，程序接管依[本機 A supervisor](agent-supervision.md#1-本機-a-supervisor)，不把 Python mutex 當跨程序保存保證。

未知 COMMIT 要對帳，不能因查詢超時便把目前表頭回退。
