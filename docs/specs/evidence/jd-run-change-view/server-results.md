# 整輪改動公開讀取：主代理接合驗證

2026-09-13；0 產品 provider。新只讀服務、共用差異投影、ChatService／HTTP 及 source schema 出站核對由主代理實作；真 PG／SDK 驗收由另一位協作者先撰寫並執行，主代理於出站補驗落實後再窄跑。

| 執行 | 實際結果 |
|---|---|
| 新純讀取反例先行 | 收集時 `RunChangeCursor` 尚未落檔，1 import error；保留為施工首敗，不是產品 SQL 故障。 |
| 首次投影及原差異組 | `test_run_change_reads.py`＋`test_change_reads.py`，38 PASS／20.17s。 |
| 原 owner／HTTP 接合 | 新讀取／HTTP＋原 chat API，33 PASS／9.61s；其後再加 source conditions 與 OpenAPI 反例。 |
| 出站條件補齊後，含真 PG | `test_run_change_reads.py test_run_change_api.py test_change_reads.py test_chat_api.py test_run_change_api_postgres.py`，**67 PASS／35.39s**。 |
| 獨審 RC-S01 反例先行 | 初頁／續頁 × capture／歷史引用 issuer 四案 **4 FAIL**，caller 壞 cursor **1 PASS**／2.14s；App 發配錯誤被誤回 `invalid_ref`。 |
| RC-S01 修正後最後受影響組 | 上述四個非 PG 檔案，新增 HTTP 503 與 issuer 分界，**70 PASS／23.71s**。未重跑無關 PG；真 PG 證據仍為上一列。 |

在原 Python 3.12 frozen 環境，以 `uv run --offline --frozen --no-sync`、`PYTHONUTF8=1`、`-p no:cacheprovider` 執行；真 PG 批次另明示 `JD_RELATIONAL_TEST_DB=1`。3 個真 PG 案使用原 55436 專用測試庫及 Saver，詳見[獨立真 PG 報告](postgres.md)；非 PG 部分不冒稱 SQL 或瀏覽器已驗。Starlette TestClient 的上游 BlockingPortal alias 有 1 個棄用警告；App 沒有引入該 alias，不另擴 fork 上游工作。

## 核實的接點

- 原生 owner 的 confirmed 集合發配固定 capture；續頁不呼叫 native inspect 追較晚內容。真 SDK 暫停／續行案例核對第一頁後又新增操作，原頁仍維持原 E／1操作／unconfirmed；新初頁才看到2操作／settled。
- `ChangeReadService` 與 `RunChangeReadService` 共用同一完整欄位／結構投影。真 PG 首次新增的4筆淨差異與舊 operation endpoint逐筆相等；較晚人工保存不改原輪 S/E／原話／模型次數。
- base/result ref 使用 canonical history-purpose，與目前 read 回的 revision ref直接相等；Web不用解token。純訪談沒有偽造 JD revision。
- 公開 GET 沿原 App boundary，固定422錯誤、安全cache/request標頭、同owner排空；未知run或壞cursor不假報沒有修改。
- RC-S01：只將外部 continuation 的驗證錯誤歸為 `invalid_ref`；App 在合法讀取期間發配引用或投影失敗回 `read_failed`，沿原 HTTP 映射 `503/service_unavailable/lookup_run`。不將內部錯誤要求員工修正，也不自動重送。
- 生成器不保存 if/then：既有 `jsonschema 4.26.0`＋`referencing.Registry`載入兩份固定 source schema（chat與read）補出站驗證；沒有遠端retriever。反例證generated model接受但正式source拒絕的錯誤組合，出口確實拒絕。
- OpenAPI 使用原source條件，唯一 `ChatOpaqueRef` 引用直接帶入原定義，不手改generated或重寫規則；實際 OpenAPI schema亦拒絕none卻count1。

## 分界

這是後端公開讀取及實際 ASGI／SDK／PG 證據，不是socket瀏覽器、Memory、自然模型或整輪撤回完成。Web／生成／游標及獨立審查各自列結果，不把重疊測試相加。Source schema是本App既有必帶資源；正式封裝要保留該資源，依[收尾 OI-08](../../2026-09-13-jd-app-open-issues.md)追蹤。
