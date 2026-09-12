# JD：同版讀取、受控定位與確切改動

- 日期：2026-09-13；Topic：JD-R002；RS-1／2 隔離施工，承接[保存切片](2026-09-13-jd-transaction-service-slice.md)與[讀取前置](evidence/2026-09-13-jd-read-reference-preflight.md)。
- 狀態：本單位已實作並通過下列有限驗收；不是完整 App 驗收。框架可替換；沒有新增產品選擇、正式採用、模型費用或私有資料外傳。

## 1. 要接出的效果

人工與 AI 由同一份已驗讀取材料取得六章內容與 refs；每次材料屬單一修訂。歷史讀取不變成另一份可編稿；即使歷史版恰好等於 head，其 refs 仍不可寫。名稱可重複，模型只帶回 App 發配的目標，不猜 UUID／行號。

只讀投影使用固定類型的 section、container、item、field、task-capability relation、source records。這是給 App 重建畫面及模型按需讀取的輸出，不是任意 JSON CRUD 或另一份保存權威。欄位值完整保留；頁面可以在 records 間分段，不能截掉一個欄位的後半句。任務讀取包含父職責、成果、要求及相關 K/S，K/S 讀取可追到受影響任務。

一般頁依序列化後 UTF-8 bytes 限量，過大的單一允許欄位另以明示單項頁交付，不降低既定 64 KiB 欄位容量。`has_more`、cursor、總數與頁起點明列；讀完頁面不等於專業完整性已通過。current 續頁遇 head 變動即拒絕；history/change 綁原 immutable revision/pair，不能改跟新 head。

## 2. 責任與原生接點

| 元件 | 本單位責任 | 不承擔 |
|---|---|---|
| 既有 JdStorage | 同版 relational current＋已驗 snapshot | 不重新簽 refs 或呼叫來源服務 |
| HistoryReader | 短唯讀 REPEATABLE READ；指定歷史、原 operation 的 base/result、固定上界歷史頁 | 不改 head、不取 writer、不偽造失敗／no_change 差異 |
| 固定 JD changes | 依穩定 IDs 比較兩份完整 snapshot；完整 row 前後與欄位、父容器、引用變動 | 不重播事件、不造逆操作或通用 diff 引擎；淨差異不等於真實操作序列 |
| ReferenceCodec | ItsDangerous 標準簽章；固定型別、document/dataset/revision/purpose，ref/cursor salt 分離 | 不提供登入授權、不配 operation/run、不另存 key／dataset 權威 |
| 讀取投影／resolver | 生成式 DTO、固定六章與完整續頁、由已驗 refs 建 CommandContext | 不讓外部 caller 提交可信 context；新來源仍由既有 owner 查核 |

`URLSafeSerializer` 不加時間到期；適用性由版本、用途與資料集約束，不讓已保存對話僅因時間經過而失去定位。payload 可解碼，不含秘密、JD 全文或原始問答。SHA-256 由套件既有 signer 接點配置；不自建 HMAC。key 至少 32 bytes，document/dataset locator 各最多 256 UTF-8 bytes，token 收發最多 4 KiB；這些是本案工程邊界，非廠商統一規定。服務建立的文件 ID 是 UUID，不縮減員工文字容量。

宿主日常重啟需保留同 key／dataset，真正的重建或備份還原世代依 DA-03 發配；本單位只驗注入契約，不新增資料表或秘密檔案。選區由瀏覽器捕捉並驗證的接線另列，不把一般 field ref 當 selection ref。

## 3. 精確差異的界線

profile 五欄、所有正文列、共享關係與來源皆有落點。新增／刪除回完整 row；更新回完整 before/after 及改動欄。任務改父容器記 move；同項也改文字可同時記 update。來源新增／移除／basis 變動完整保留；來源可回讀與 basis 是否仍匹配分開。

reorder 只比較同容器／種類兩版存活 sibling 的相對順序。使用 Python `difflib.SequenceMatcher(..., autojunk=False)` 對唯一 IDs 找未改順序，沒有自製 LCS；不宣稱得到唯一最小動作或當時使用者拖曳的是哪一項。插入／刪除造成 position 正規化不冒稱內容更新；完整前後稿仍能查看實際數值。共享 K/S 更新附兩版受影響任務並集。

## 4. 官方依據與停止研究條件

查閱日 2026-09-13；精確套件版本／授權與有限原碼核實接[讀取前置](evidence/2026-09-13-jd-read-reference-preflight.md)。

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)：清楚工具目的、已知欄位交程式及真實回傳；未指定本案 refs 或表格。
- [Anthropic writing tools](https://www.anthropic.com/engineering/writing-tools-for-agents)：相關且可行動的內容、明示分頁／截斷與下一步；不能以精簡為由默默漏讀。
- [AWS CLI pagination](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-pagination.html)：續讀及排序變化的限制；本案額外固定 revision，不冒稱 AWS 保證 JD 快照。
- [ItsDangerous 2.2 stable](https://itsdangerous.palletsprojects.com/en/stable/serializer/)／[concepts](https://itsdangerous.palletsprojects.com/en/stable/concepts/)：免費 BSD-3-Clause，標準簽章／salt／可讀 payload；宿主管理 key 不由套件代勞。
- [Python 3.12 difflib](https://docs.python.org/3.12/library/difflib.html)：SequenceMatcher、自動 junk heuristic 與非最小編輯限制；本案不把它當歷史事件權威。
- [PostgreSQL 18 isolation](https://www.postgresql.org/docs/18/transaction-iso.html)：短交易一致材料；外部來源與跨請求不是同一 DB snapshot。

以上機制已足以進有限反例；只有實測缺口才重開，不再比較同層品牌。不得推定 OpenAI／Anthropic 私有產品內部也用本案的 signer、snapshot 或 SQL 設計。

## 5. 驗收與未完成範圍

本單位最低驗收：完整六章／空白 containers、重名／無名稱、長繁中多頁無損、過時 current cursor、歷史 head 同版也不可寫、跨文件／dataset／錯用途／偽造 refs、同 key 新程序解析、原結果不升最新、no_change／failure 無變動、K/S 及全部來源、插入不偽 reorder、移動兼文字更新。SQL 讀取由專用真 PG 證據支持，純投影／簽章另測，不混稱瀏覽器或自然模型。

仍須後續完成：實際 run writer／停止 proof、來源 owner、瀏覽器選區、人工 notice 的 response-backed 基準、HTTP／Web CRUD／autosave、歷史還原／整輪撤回、正式採用、備份還原、自然模型與員工驗收。Excel 延後不變。

## 6. 實作落點與精確邊界

以下皆位於新隔離 [jd-relational-app](../../experiments/jd-relational-app/README.md)，未接正式產品，未新增資料表或 migration。

| 實作 | 已完成與接合限制 |
|---|---|
| `contracts/jd-read.schema.json`／生成 Python、TS | `jd_read` 的 current/item/section/history 三參數輸入、固定 record union、完整頁面與安全錯誤。格式版本明示為嚴格整數 1，不接受 bool。 |
| `reads.py`／`read_transport.py` | 同份材料完整投影、章節／項目與依賴內容、byte 分頁、空 containers；兩家真 SDK 離線外殼。來源回讀沒有偷偷同步進 DB snapshot：僅 basis 計算，readability 明示 `not_checked`。 |
| `references.py` | 實際標準 signer、ref/cursor payload 精確驗證、同文件／dataset／用途／版本。新程序測同一個**注入** key／dataset；未建立宿主秘密保存或還原世代 owner。 |
| `command_context` | 讀回的 current item/field/container ref 重核存在性及欄位 digest，與人工／模型既有共同 command 接合；history 同 head 仍不能寫。selection issuer 未接，此路徑回 `selection_not_available`。新來源由注入 resolver 查同文件／可讀性；實際來源 owner 尚未接。 |
| `storage/history.py` | 短唯讀 REPEATABLE READ，核 snapshot/digest/metadata/父版／原 producer；歷史索引第一頁固定 anchor，後頁不升新 head。變更材料讀原 operation base/result；failure 無結果版，no_change 無虛构差異。 |
| `changes.py` | 固定 JD row／relation 的淨差異，完整前後值、欄位、移動／排序與共享 K/S 的受影響任務。不是任意 patch、replay 或反向撤回引擎。 |
| `observation_projection.py` | 原 `WriteObservation`／`SavedOperation` 投影到既有合法 result；只 committed 發 change ref，no_change 發原 result revision，unconfirmed 保留原 effect 並 reconcile 原操作。不查 head、不改 receipt；發配或輸出驗證失敗僅 `projection_failed`，不能改判原保存是否成功。 |

已知區別：`HistoryReader.read_change` 與純淨差異是**材料層**，`jd_change_read` 的公開 DTO、分頁、工具外殼及 HTTP 還未接，不能說員工已有可用差異畫面。上表 `jd_read` 工具外殼已接，HTTP／Agent 自動調用尚未接。模型要求的 `document_id`、revision、digest、run／operation 身分不因此新增到三參數輸入。

目前 signer 為 ItsDangerous **2.2.0**，穩定、BSD-3-Clause；此為現行官方穩定版的有界採用，非看到年份較早便判淘汰。其他鎖定依賴沒有升級；原 8 份生成檔保持不變，只新增 read 的 Python／TS。`domain.source_basis_digest` 抽出既有同一算法供讀／寫共用，不另定來源支持算法。

## 7. 執行、首敗與獨立審查

執行日 2026-09-13；Python 3.12.13／此目錄固定 lock。PG18.6 專用測試容器於 loopback 55436，僅合成資料；沒有產品資料、DDL 改動、模型付費呼叫或瀏覽器測試。

| 實際檢查 | 最後結果 | 證據範圍 |
|---|---|---|
| 全套 `pytest -q -p no:cacheprovider`，PG 關閉 | **732 PASS／74 SKIP**，26.93 秒 | 離線 domain／格式／refs／diff／SDK wire 等；74 項為預設跳過的真 PG，不當 PASS |
| `test_storage_history.py`＋`test_read_storage_integration.py`，PG 明示開啟 | **36 PASS**，38.38 秒 | 13 離線＋**23 真 PG**；SQL 歷史 12、read→command→save 11，不與上一行加總 |
| `test_reads.py`＋`test_read_transport.py` | **32 PASS** | 同版完整讀取、實際內層工具內容 byte 限制及正確錯誤歸因；已包含於全套 |
| `test_observation_projection.py` | **29 PASS**，獨立審查也重跑 | 合成 observation＋真 signer；不是 writer／DB commit 的額外證據 |
| 五份 schema 的 Python／TS `generate_contract.py --check` | PASS | 無手改生成物；既有 4 份 schema 的 8 份輸出無差異 |
| TypeScript `tsc -p tsconfig.json` | PASS | 生成型別可編譯；未宣稱 Web 已接 |

真 PG 接合涵蓋：空白容器新增職責／任務，已發配 field ref 改稿與 item ref 移動；同版材料進共同 domain、固定意圖、admission fixture 與實際保存；完整六章重讀、歷史同 head 也不可寫、current cursor 過時拒絕、immutable item/section/index 續頁、原 producer refs、跨文件拒絕，以及 source basis current→needs_recheck→明示刷新。WriterAuthority 與來源 resolver 仍為合成替身。

首敗與修正保留如下，避免把測試演進寫成一次全過：

1. changes、history、read、observation 的新增測試曾因模組尚未建立而 collection fail；完成實作後各專項通過。refs 首次 2 FAIL／91 PASS：Pydantic literal 1 接受 bool、子程序缺 src path；加精確型別檢查並修 fixture 後 93 PASS。
2. PG 整合 fixture 首次 1 PASS／10 setup ERROR：把 condition item kind 誤寫成 qualification；修測試材料後 11 PASS，沒有因此放寬 domain 規則。
3. 獨立審查找到 **RD-R01／P2**：讀取層用緊湊 JSON 算頁量，provider adapter 另加空格，32 KiB 頁可能實際輸出 32805 bytes。加兩家×兩頁量四個反例，先 **4 FAIL**，再由分頁與出口共用 `read_json`；四項複核 PASS，**CLOSED**。限制針對完整內層工具結果字串，含已簽 refs／cursor／envelope；不宣稱等於整個 provider HTTP request 大小。
4. root 自審找到 **RD-R02**：內部 issuer／輸出 DTO 壞掉被誤回 `invalid_ref`／`invalid_input`，會誘導模型改錯參數。測試先有一次 readonly fixture 錯誤，改為 class injection 後兩項明確 **2 FAIL**；拆 caller `_request` 與內部讀取／投影邊界，後者只回 `read_failed`。兩反例及既有 caller 錯誤獨立複核 PASS，**CLOSED**。
5. 新增公開套件的沙箱連線失敗、離線 cache 無檔；一次有界升權安裝 ItsDangerous 2.2.0 成功。沒有以失敗為由升級其他依賴或讀取本地秘密。

獨立審查：history、純 changes、signer、讀取投影、工具外殼、原 observation 投影皆完成。讀取另以 205 版索引跨 100 筆 SQL 上限、4 KiB 分頁與新 head 驗 205→1 無漏頁；source／K/S／歷史項目多頁作合成反例。RD-R01、RD-R02 已窄複核閉合；文件審查另修正保存稿將 `q019_document`／舊 Plate JSONB 寫成目前狀態的過時文字，對照實際十三表閉合。未發現剩餘阻擋 finding。此結論只涵蓋本切片，不替未做的整體接線背書。

## 8. 下一個工作單位

沿[新版施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)把已驗差異材料接 `jd_change_read` 公開契約，接實際 run/writer owner 與 HTTP，再供六章管理畫面使用。來源 owner、選區發配、資料集身分與人工 notice 按依賴閉合；不再對同層框架廣搜。整輪 JD 撤回仍只回退 JD，不回退 Memory／原始訪談；目前沒有新增這些資料的 writer。
