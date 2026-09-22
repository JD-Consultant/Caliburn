# JD：文件目錄、條件更新與建立查回

- 日期：2026-09-13；Topic：JD-R002；RS-1／2→3 隔離實作。承接[人工 HTTP](2026-09-13-jd-manual-http-slice.md)，ADR0075 Proposed／正式 ADR0060 不變。
- 效果：從空白建立多份 JD、查列表、更名、封存及恢復；同一建立請求不會因回覆遺失而多出文件。只管理目錄資訊，不改 JD 正文、原話或 Memory。
- 實作：[catalog_service.py](../../experiments/jd-relational-app/src/jd_relational/catalog_service.py)、[catalog_api.py](../../experiments/jd-relational-app/src/jd_relational/catalog_api.py)、[catalog SSOT](../../experiments/jd-relational-app/contracts/jd-catalog-http.schema.json)。仍沒有可操作管理畫面或完整顧問接線。

## 1. 入口與共同規則

| 路徑 | 契約與效果 |
|---|---|
| `GET /api/documents` | 預設未封存；`archived=true/all` 可查封存或全部。ID keyset 分頁，每頁最多 100，返回非秘密 `dataset_id`。查詢沒有新建範本或寫入 checkpoint。 |
| `POST /api/documents` | `dataset_id + request_key + title`；原 key 和正規化名稱 digest 同建立交易保存。回 200 與原文件 ID，同 key 重送不宣稱新建另一份。 |
| `POST /api/document-creations/lookup` | 保留同一份原建立輸入；名稱不放 URL。found 只回原文件身分；not_found 是一次讀取觀察，不能推論原請求沒在執行或可換 key 重建。 |
| `GET /api/documents/{id}/metadata` | 文件 ID、列表名稱、封存狀態、metadata version、建立／更新時間；strong ETag 涵蓋資料集及完整回傳表示。沒有 create digest、秘密或 JD 正文副本。 |
| `PATCH /api/documents/{id}/metadata` | `application/merge-patch+json`，具名 `{title}` 或 `{archived}` 二擇一；原 `If-Match` 必填。更名、封存與解除封存沿同一目錄更新業務。 |

`title` 是列表顯示名稱；職稱仍是 JD profile 欄位。相同名稱可以有不同文件。封存不刪任何工作或歷史；可讀、可查回建立、可解除封存。更名封存文件僅改其目錄，不開放正文寫入。解除封存不是 JD 歷史還原。

JSON Merge Patch 的採用範圍只含上述可改欄位；null、未知欄位、任意巢狀修改及同次修改兩個欄位均不在本契約中。不是任意 JSON patch 引擎；業務驗證後直接呼叫既有具名 storage 方法。已保存狀態相同且原版本仍有效時不增加 metadata version；過時版本即使值恰好相同也回 412。

列表採穩定 ID 排序；分頁是多個短唯讀交易，不是假稱跨頁快照。建立／封存期間的列表可能改變，畫面可重讀。完整列表不需要載入每份 JD snapshot；文件仍由十三張關聯表與其既定 owner 保存，沒有第二套目錄或新 DB 表。

## 2. 保存、原操作與執行範圍

建立使用既有 `jd_document.create_request_key` 唯一鍵與原 title digest；initial profile／revision／head 在同一 PostgreSQL 交易。相同 key、不同原名稱拒絕；文件日後更名或封存不改原建立意圖。回覆遺失時先查回，必要時明示重送同 key／原內容；App 不自動另配 key，也不自動重試交易。

目錄更新先比對含資料集的 ETag，再在同一交易依 `jd_document → jd_head FOR UPDATE` 順序鎖定並核 metadata version。第一次 GET 與 SQL 之間若又有變更，CAS 仍拒絕，不偷偷以新版本繼續。只改 `jd_document` 目錄欄位與時間，JD current rows／revision／operation 保持不變。

目錄不是正文操作，沒有增造通用回執表。資料庫提交回覆不確定時回 `write_unconfirmed`，不能聲稱已回滾；重讀能確定目前狀態，不能把它冒稱為某一原 metadata 請求的永久回執。舊 ETag 不能因 HTTP 失敗而自動換新重試，否則可能反轉後來的封存／恢復。

原生 `ManualRuntime` 在同一文件門閘下執行 metadata SQL；有本地 writer、未清 pending 或 Saver 不可讀即拒絕。Saver 檢查、SQL 及 COMMIT 全程保留該文件鎖，不能先查 busy 再不受控地寫入。新建採原 request key 的獨立鎖；registry 鎖僅管 dictionary／accepting 狀態，沒有全域 I/O 鎖。

SQL guard 只認當次同步呼叫、原執行緒、活躍 token 與有效宿主。正常 close 會等待目錄檢查／SQL 退出；等待逾時不關閉其 DB 資源，也不把 HTTP 離線當停止證明。原生宿主／startup 尚未就緒不能新建或改目錄。既有內部 `storage.create_document` 的無 guard 形式僅保留合成 fixture／初始化相容；公共 App 入口一律經 runtime，不暴露無 owner 的 storage 呼叫。

## 3. 資料集與瀏覽器接點

建立與原建立查回都明示預期 `dataset_id`；server 不符即拒。metadata ETag 包含相同資料集身分；即使还原後文件 ID／版本剛好相同，舊 tag 也不能用來修改。公開 UUID 是範圍提示，並不是金鑰或存取權限。

同源／設定允許的本機 Origin 仍在 unsafe body／admission 前檢查。保留原 API 固定安全診斷與 no-store；CORS 增加 PATCH、If-Match 與 ETag expose，沒有加入登入或遠端存取。wrong patch media type 回 415＋Accept-Patch；缺前置條件 428、版本不符 412、忙碌／資料集不符 409。格式與 driver 故障不回原始輸入、SQL 參數或秘密。

已讀並採[本機配置研究](evidence/2026-09-13-jd-local-configuration-preflight.md)為下一有限驗證方向：Windows KnownFolder＋DPAPI current-user 保護固定安裝／資料集／簽章與本機連線設定，不新增秘密框架或 DB epoch 副本。普通重开不得自行配新身分或環境變數換庫；明示維護流程才更新資料集世代。這是設計方向，尚未實作配置或完整還原。

目前真程序測試仍注入固定合成配置；不能據此宣稱日常啟動器完成。無 signed ref 的其他既有 mutation（例如 manual recover）須在持久配置接線時一併閉合預期資料集；本次 catalog gate 不是全 App 跨資料集驗收。IndexedDB 恢復、容量與備份流程仍屬 DA-03 後續。

## 4. 官方依據與選擇界線

查閱 2026-09-13；本單位沒有新增或升級依賴。舊而仍有效的標準可以使用，不把發表年份當作淘汰證據。

| 來源、適用版本、狀態／授權 | 官方事實與本案映射 |
|---|---|
| [AWS Hexagonal Architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)，現行 Prescriptive Guidance；設計指引，非安裝套件 | 將 domain 與 UI、DB、外部 API 分離。採共同 CatalogService／runtime／storage 接點；不因 AWS 圖例出現 Lambda、DynamoDB 而為本機產品增加雲端服務或多層空殼。 |
| [AWS safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，現行 Builders’ Library；官方設計文章 | Caller key 表達意圖，原 token 與相關修改須原子保存，同 key 不同參數需辨識。映射為既有唯一建立鍵／digest；不是 AWS 指定本案表名、永久保留期限或所有 endpoint 都必須另建 ledger。 |
| [RFC 9110 §13.1.1](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match)，現行 HTTP Semantics／IETF 標準，文字依 IETF Trust | If-Match strong comparison 防止過時修改。只接受 GETmetadata 取得的單一實際 tag；本案刻意對每個不符前置條件回 412，不把狀態剛好一致當原操作回執。 |
| [RFC 5789](https://www.rfc-editor.org/rfc/rfc5789.html)、[RFC 7396](https://www.rfc-editor.org/rfc/rfc7396.html)，現行標準／IETF Trust | PATCH 支援部分修改、可配合 strong ETag；Merge Patch 定義指定屬性更新，server 決定允許的內容。採具名單欄子集，同資源 GET/PATCH 使用相同 metadata 表示與 tag，無通用定位引擎。 |
| [PostgreSQL 18 Row Locks](https://www.postgresql.org/docs/18/explicit-locking.html)，實際 18.6、穩定／PostgreSQL License | FOR UPDATE 在交易內序列化相同列。採既有 document→head 鎖序及 metadata CAS，不宣稱 DB 列鎖能取代 native writer lifecycle。 |
| FastAPI 0.141.1 MIT／Starlette 1.6.0 BSD-3／AnyIO 4.15.1 MIT／SQLAlchemy 2.0.52 MIT／Psycopg 3.3.5 LGPL-3.0 | 沿已驗[HTTP 契約](2026-09-13-jd-manual-http-slice.md)及[資料層](evidence/2026-09-13-jd-relational-db-preflight.md)的實際 lock；本次以安裝 metadata 再核版本。同步路由由原生 threadpool 執行，宿主 lifespan 仍擁有資源，不將框架 API 當業務規則。 |

AWS 是公開實務參考，不是所有公司的內部實作共識。OpenAI／Anthropic 的模型與 App 責任仍沿既有[工具契約](2026-09-12-jd-relational-agent-tool-contract.md)；本次沒有改模型工具或自然訪談行為，不重開同層品牌研究。

## 5. 驗證、審查與未完工作

最後整組 **1372 PASS／154 PG SKIP，21.31 秒**；保留一項上游 Starlette TestClient 的 AnyIO alias 棄用警告。八份 schema／Python／TS 生成一致、TypeScript 檢查通過；原十四份生成檔與依賴不變。不同批次不累加。

- 新 SQL 反例首敗：缺 `catalog_document`，1 FAIL；實作後 13 真 PG PASS。覆蓋 JD／歷史保留、CAS 競爭、原建立查回、no-change、鎖後 guard 故障、提交回覆遺失與分頁。
- 新 runtime 入口首敗 29 FAIL；原有重入 close 反例及新增 Saver I/O 反例已修。最後 70 PASS＝31 catalog runtime＋39 既有 runtime／startup／host fake/input；這批不冒稱真 PG／Win32。
- 人工 HTTP／query／新 catalog route 與 runtime 窄回歸曾 149 PASS。schema 反例記錄 JSON Schema mathematical integer 可接受 1.0，而生成 strict int 拒浮點；boolean 嚴格拒 0/1。時間字串使用原生映射保留 wire，完整日曆有效性依 DB datetime；沒有自造日期解析器。
- 真 Windows／PG／Uvicorn 新程序 2 PASS：新增建立回覆遺失、原 key 查回、更名／封存／重開及解除封存；另保留原人工斷線保存情境。新文件只有 1 筆 catalog、2 筆 revision（initial＋一次正文修改）、1 筆正文 operation。metadata 修改不增加正文修訂。
- 真 PG 受影響組 `catalog_storage＋storage_service＋operation_lookup＋manual_runtime_postgres＋manual_service_postgres`：**86 PASS，13.12 秒**。另新增 native Saver／CatalogService 組 **10 PASS，1.72 秒**，包含保存後原話／所有 JD 修訂及回執完全相同、同文件忙碌但別文件仍可改、服務檢查後版本競爭、兩種真 COMMIT 回覆遺失後只讀查回。上述 PG 不是整組跳過的案例當作通過。
- 獨立 service／storage／HTTP 與 runtime／storage 交叉審查均無 P1/P2；含限定 TestClient 錯 Origin、CORS／ETag、非法 patch、原路由保留，以及三個獨立 thread 探針。PATCH unsupported media type 收尾補 415，契約先 1 FAIL 後通過；最後整組已含此修正。

真程序 helper 只在測試內包裝回覆阻擋點，從原 HTTP 連線不讀 response 即離線；原生 SQL 已完成，查回仍返回同 ID。PID、退出與合成 snapshot 證據保留 `.research-tmp/jd-catalog-http-*`；fixture 的固定 Origin、dataset、signer 不是正式本機設定。沒有真模型、真員工或實際瀏覽器 UI 完成宣稱。

下一單位：實作已研究的持久本機配置、明示初始化與普通開啟，再接六章管理畫面和瀏覽器恢復格式。AI run／call、來源 owner、選區、手改通知、歷史整份還原／整輪撤回及完整成品驗收仍待完成；Excel 仍延後。
