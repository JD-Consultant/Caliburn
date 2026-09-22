# JD：人工保存、操作查回與 HTTP 接合

- 日期：2026-09-13；Topic：JD-R002；RS-1／2→3 隔離實作。承接[宿主恢復](2026-09-13-jd-host-restart-recovery-slice.md)；不改 ADR0060，ADR0075 仍 Proposed。
- 產品效果：App 以同一業務操作保存關聯式 JD；重送、斷線與重開後查原結果，不把候選或 HTTP 成功當成已保存。不新增模型呼叫。
- 新責任檔：[manual_service.py](../../experiments/jd-relational-app/src/jd_relational/manual_service.py)、[manual_api.py](../../experiments/jd-relational-app/src/jd_relational/manual_api.py)、[HTTP SSOT](../../experiments/jd-relational-app/contracts/jd-manual-http.schema.json)。

## 1. 介面與責任

| 路徑（同一 `/api/documents/{document_id}/jd` 前綴） | 效果 |
|---|---|
| `POST /edits` | `ManualSaveInput`：operation_id、base_revision_ref、command。App 配發並保留 UUID／原 base，command 是八個具名完整業務操作之一；不接受 caller 指定 origin／ai_run_id／digest／新列主鍵。 |
| `GET /state` | ready、archived、write_blocked、running、目前 operation_id 及有限錯誤。這是畫面當下觀察，不是可以繞過 server gate 的許可。 |
| `GET /operations/{operation_id}` | 原操作的 not_found／pending／observed、原 MutationResult 及目前寫入狀態；不改 DB／checkpoint，不重讀原來源、不重建 command。 |
| `POST /operations/{operation_id}/recover` | 明示空 JSON 物件、固定原 operation；只由實際 owner 對帳／清理，不能因 HTTP 斷線而認定 worker 已停。 |

`ReadService`／`ChangeReadService` 的既有查詢路徑同時保留。HTTP 與模型使用同一原操作 Input、domain、JdStorage transaction 與 receipt；外層只補人工 operation／base，不新增第二份規則。人工身份固定 `manual`、ai_run_id 為 null。source owner 未接前，非空來源拒絕；selection 未接前明示尚未提供，不能用假的來源或一般 field token 替代。

完整建立任務、一次相依更正、移動／刪職責所需內容調整均沿具名操作的整體候選驗證。這釐清[工具契約 §4](2026-09-12-jd-relational-agent-tool-contract.md#4-app-command-與模型工具的關係)的早期通用 ordered commands 草案：實際 HTTP 沒有任意 batch，也不將已定的完整工作更正拆成逐欄提交。

## 2. 正常保存與競速

1. 原生 HTTP 層先檢查 Host／Origin、Content-Type、raw body 上限與 generated DTO；共用 parser 再拒重複 JSON keys、非法 Unicode／常數，尚未取得 writer。
2. 解確切 base revision ref，以 immutable 歷史內容核同版 `current` 內容 refs 與來源，固定原意圖。revision ref 本身只識別版本，不能把歷史 item／field refs 升格為可寫。
3. `ManualRuntime.submit` 對同 identity 返回同 handle；同 key 改意圖拒絕。若不同新操作正在執行，仍能讀到已確認舊操作原 receipt；新工作須依原 gate admission，receipt 查無不是死亡證明。
4. 原生 root 先記 admitted identity，再派實際 writer。SQL 再驗 head／關係；新操作以過時 base 到達，保存原次 stale 拒絕回執，不偷換最新版。
5. HTTP 有界等候原 handle。未等到結果只回 unknown／unconfirmed 與 reconcile_operation，不 cancel Future、不另排寫入。confirmed receipt 仍按原值投影，即使 checkpoint 收尾失敗；另查 state 會維持 write_blocked。

已保存 O 後，head 再前進，重送同 O 仍可由原 base 固定相同 digest，再查原 receipt。來源 owner 暫時不可讀或舊簽章已失效時，不保證重新 POST 可重新解析；**原操作 GET 不依賴這些材料**，仍從永久記錄取結果。簽章／dataset 的持久配置與更換程序是後續明示接點，本次真重開驗使用固定合成配置。

恢復 O 時在同一 per-document slot lock 核 `expected_operation_id`；若已換成 P，回 operation_conflict，不清 P。GET not_found 只表示這次沒看到 pending／receipt，不證明延遲 POST 不會再到達，也不授權改 key 自動重做。前端保留原請求，後續查回／明示重送仍用原 key/base/意圖。

## 3. 官方證據與本案映射

查閱 2026-09-13；沿現行已鎖版本，本單位不安裝或升級套件。

| 官方來源／適用版本與授權 | 官方事實及本案採用界線 |
|---|---|
| [AWS safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)；現行 Builders’ Library | caller key 表示意圖，同 key 異參數拒絕、晚到请求仍尊重原操作、token 與 mutation 原子保存。本案 GET／永久 receipt／pending 名稱是產品映射，AWS 沒有規定本案資料表或端點。業務分層沿[既有 AWS 證據](evidence/2026-09-13-jd-app-boundaries-errors-logging-evidence.md)。 |
| [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[strict Content-Type](https://fastapi.tiangolo.com/advanced/strict-content-type/)；0.141.1、MIT | 使用 lifespan，不混 deprecated startup/shutdown events；typed body 與 strict_content_type 阻無內容類型的 JSON CSRF。資源由 host 注入，endpoint 不讀環境／setup。 |
| [Starlette lifespan](https://starlette.dev/lifespan/)、[threadpool](https://starlette.dev/threadpool/)、[body limiter](https://starlette.dev/middleware/#requestbodylimitmiddleware)；1.6.0、BSD-3-Clause | startup yield 前不接請求；sync endpoint 用原生 AnyIO threadpool；raw bytes／chunked 超限由原生 middleware 處理。本案 1 MiB mutation 上限不是廠商共識，read parser 仍維持 16 KiB，body limiter 不冒稱慢連線逾時機制。 |
| [AnyIO threads](https://anyio.readthedocs.io/en/stable/threads.html)；4.15.1、MIT；[ASGI HTTP](https://asgi.readthedocs.io/en/latest/specs/www.html)2.5 | abandon／disconnect 不會殺掉實際同步 worker。本案 await／HTTP 回覆不擁有 SQL Future，禁止拿它作 stopped proof。 |
| [Uvicorn server](https://github.com/Kludex/uvicorn/blob/0.52.4/uvicorn/server.py)、[h11](https://github.com/Kludex/uvicorn/blob/0.52.4/uvicorn/protocols/http/h11_impl.py)；0.52.4、BSD-3-Clause | graceful timeout 取消 ASGI task 不等於 thread 死亡；斷線時 send 可能正常 return，也不證明瀏覽器收到。host 必須明確 drain 自有 runtime 再關 Saver／DB；真 HTTP 測試讀原 receipt 證明結果。 |
| [CORS middleware](https://starlette.dev/middleware/#corsmiddleware)、[原碼](https://github.com/Kludex/starlette/blob/1.6.0/starlette/middleware/cors.py)；[OWASP source Origin](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html#using-standard-headers-to-verify-origin) | CORS 對 actual request 不一定阻止執行，TrustedHost 也不檢查來源 Origin。本案在所有 unsafe POST admission 前要求一筆精確 configured local Origin（含 port），拒 missing／null／重複；不做 Referer fallback。這是本機瀏覽器邊界，沒有加入登入／ACL，也不防同機原生程序自填 header。 |

OpenAI／Anthropic 的模型提出意圖、App 執行與配對真實結果原則仍沿[工具契約](2026-09-12-jd-relational-agent-tool-contract.md)，本次沒有更換 SDK 或新模型行為，故不重開同層研究。上述公開事實與本案選擇分開，不宣稱兩家模型供應商的產品內部 HTTP／資料庫相同。

## 4. 錯誤、紀錄與狀態

保存觀察沿既有 `project_observation`／`project_result`：200 已取得成功結果，202 尚待對帳，terminal 拒絕沿對應 Problem。查詢取得原失敗回執仍是 200，body 保留原失敗。

`ManualProblem` 只報 App／輸入／來源／service 層的故障；不捏造「正文已回滾」的 MutationResult。投影故障可能發生在真正 COMMIT 後，仍要求查原操作，不改判未保存。訊息、request ID、route template、狀態碼及時間採固定安全值；不把 body、tokens、driver exception、JD 正文或 traceback cause 送診斷。logging sink 故障不蓋原結果。

只重用原生 lifespan 與 query 邊界的少量固定接點；沒有另一個寫入 executor、通用重試／CRUD／同步／回退引擎。日常 host 的 log 容量／保留政策與實際 launcher 接線仍待完成。

獨立審查找到兩個 P2：早期新 DTO 雖驗型別，卻容許「封存／未 ready 而未阻擋」，或「observed/null、pending/confirmed、not_found/committed」。已改成具名 writable／blocked 與三種 operation 分支，直接引用原結果的 confirmed／bound-unconfirmed 定義。不能用查到 status 字樣冒稱取得 receipt。

Pydantic 2.13.5 即使 strict=True，`Literal[False/True]` 仍會接受數字 0／1（含 float）；0.79.0 生成器的 literal 分支也不經普通 StrictBool 分支。沿本機官方安裝原碼及四組反例核明，沒有宣稱 generator 已解決：SSOT／DTO 公開 schema 拒數字；`ManualService._document_state` 在兩個輸出處先驗四個 flags 的真 bool 型別，再用生成 union 驗合法狀態。保留原生產生器、不手改生成檔、不為四個 flags 新造通用 validator。服務反例 `archived=0` 首先誤通過，補出口後確實拒絕。

## 5. 驗證與尚未完成

首敗：新服務／契約缺模組；生成器多 external-ref mappings 的 CLI 參數用法錯誤；原 recover 缺 expected operation 參數；同 pending key 異意圖原先只回 busy；原 O 被後續 P 的 gate 擋住而無法返回舊回執；真 HTTP helper 未明示 PYTHONPATH。均先保留首敗再修，不放寬原情境。

新增契約與原有共用契約最終 302 PASS（含新 106）；真 PG＋原生 Saver／writer 12 個新增案例通過，包含原話保留、相依更正全回滾、有效未完整任务、no_change、stale、COMMIT ACK 遺失及 cleanup。真 Windows＋PG＋Uvicorn 新程序情境：admitted POST 後斷線、同時查狀態、拒錯 Origin、保存後續新工作再重送 O，重啟後原結果一致；兩次實際寫入只有兩個 receipt／三版 JD，重啟程序零重播。父測試未提供死亡 bool，未把 pytest 加入 Job；stdin 控制仅屬測試。此 HTTP 產物保存程序／execute／最後內容，不含原始訊息快照；原操作完全相等由實際 pytest 斷言證明，原話保持由前述獨立 PG 案例證明。

最終全組 **1217 PASS／130 PG SKIP（21.75 秒）**，包含 4 真 Windows 基本宿主案例。另執行受影響真 PG **42 案例全部通過**（原操作 lookup 12、人工 runtime 8、新人工 service 12、原 query 5、原 Windows host 恢復 4、新 HTTP 斷線／重開 1）。接合首輪共 297 項，只有一筆舊 HTTP fake fixture 把 unknown 標成 observed 而失敗；改為 pending 並加一筆矛盾回應必拒的反例後，該檔 **72 PASS**、上述全組通過，無更動或重跑已通過的 DB 行為。各組重疊，不累加成獨立案例數。7 schemas 生成檢查及 TypeScript 編譯通過；保留既有第三方 Starlette／AnyIO 一筆 deprecation warning。

獨立 HTTP／真程序證據審查通過，另原始 ASGI 探針驗拒 Origin 時未讀 body、超限及安全錯誤。service／schema 審查的两項 P2 經具名分支及 bool 出口修正後 CLOSED，窄複核 **128 PASS＝106 契約＋10 service＋12 真 PG**。這些只證明本單位人工接合；沒有自然模型或真人使用證據。

仍不是完整手動 App／自然模型驗收：文件建立／更名／列表／封存／恢復尚未有正式 HTTP；持久本機配置、頁面、autosave 恢復資料、選區、實際 source owner／AI 回合／notice、歷史還原／整輪撤回及日常維護依[成品計畫](../plans/2026-09-13-jd-relational-app-implementation.md)接續。下一單位先補文件入口與持久本機配置，使六章管理畫面能從空白建立並使用本次寫入／查回介面；Excel 仍延後，0 產品模型。
