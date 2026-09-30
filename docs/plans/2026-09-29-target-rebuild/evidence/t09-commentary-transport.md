# T09：公開 commentary 暫態 SSE backend

2026-09-30，有界 backend 切片；不代表整體 T09／T16／T17 或真模型 UI 旅程通過。

## 責任與實作

依 [interface-and-delivery §2](../../../implementation/interface-and-delivery.md#2-串流不是保存權威)、[開發規範](../../../implementation/development-standard.md)及[程式撰寫規範](../../../implementation/coding-standard.md)。公開串流僅呈現，不是正式成功、訪談來源或恢復權威。無 DB／event store、無新的 SDK event protocol。

- `apps/api/contracts/http/commentary-update.schema.json` 是唯一 wire 來源；正式生成 Python `CommentaryUpdate` 與前端 `generated/commentary-update.ts`。只允許五個必要欄位：`job_file_id`、`execution_id`（UUID）、`response_id`、`message_id`、`text`（string）；`additionalProperties: false`。
- 既有 `caliburn.transport.http.consultant_turns.router` 增加 `GET /api/job-files/{job_file_id}/consultant-turns/{execution_id}/commentary-stream`。event 固定 `commentary`，data 為上列 JSON；text 是累積全文，不是 delta。沒有 phase／reasoning／tools、SDK event 轉送、假進度或 completion event。
- request dependency 在 SSE headers 前 `await ConsultantStatusWorkflow.read(job_file_id, execution_id)`，沿 execution 與 interview 原 owner 核同檔案、CONSULTANT_TURN、原輸入。不存在／錯檔案／錯操作族為 404；正式結果缺失仍為原 owner 的 503。檢查時已 terminal 為 204 空 body，不訂閱。
- 活躍 stream 不自行查詢／改變後續 execution 狀態；前端依既有 status GET 關閉 stream。斷線只解除訂閱，沒有暫停、取消、重送員工輸入、模型呼叫或費用效果。

## 主線接線

```python
from caliburn.workflows.consultant_commentary import ConsultantCommentaryHub

app.state.consultant_commentary_hub = ConsultantCommentaryHub()

# 在同一 asyncio event loop 的 App 公開 commentary callback 呼叫：
hub.publish(job_file_id, execution_id, response_id, message_id, text)
```

公開介面：

```python
ConsultantCommentaryHub(
    *, queue_capacity: int = 8,
    max_subscribers: int = 64,
    max_update_chars: int = 32768,
)
publish(
    job_file_id: UUID, execution_id: UUID,
    response_id: str, message_id: str, text: str,
) -> None
```

同一 hub 由 composition 持有；不新增 router 註冊需求。constructor 不啟動 task／程序／I/O。callback 必須已選定**公開** commentary；本模組不能從任意字串判斷機密與否，亦不接收整包 SDK event。

每 subscriber 8 格、總共最多 64 subscribers；滿 queue 丟最舊暫態。`response_id + message_id + text` 合計超過 32768 Unicode 字元時整則丟棄，不截斷、不改正式 body。訂閱額滿為 503；未注入 hub 為 503。publish 是同步 `put_nowait`，不等待 subscriber／網路、不建立背景 task；無訂閱時不保留消息，detach 清空 queue 並移除 scope key。所有使用者須在同一 event loop；跨 thread／worker fanout 不屬本機單程序切片。

慢讀／超大／斷線／晚訂閱均可漏暫態；恢復靠原有 status GET 中已保存公開 commentary／正式回覆。沒有 SSE id、Last-Event-ID replay 或第二份保存。原 producer 的完整公開消息保存仍由既有 checkpoint owner 負責。

## 官方機制確認

查閱 [FastAPI SSE 教學](https://fastapi.tiangolo.com/tutorial/server-sent-events/)與[官方 API reference](https://fastapi.tiangolo.com/reference/sse/)，並核本機鎖定 **FastAPI 0.141.1** 的 `fastapi/sse.py`、`fastapi/routing.py`。

採 generator route `response_class=EventSourceResponse`、yield `ServerSentEvent(event="commentary", data=generated_model)`；JSON／SSE framing、閒置 heartbeat 與結構化取消由框架處理。不直接回傳 marker response 繞過 FastAPI routing，也不自造 SSE parser。scope 與 subscription 在 request-scope dependency 持有／釋放，不把 DB 交易留到 stream 結束。正式 ASGI 測試核 `text/event-stream`、`X-Accel-Buffering: no`、event/data bytes 與 disconnect 清理。

## Red／Green 與限制

- Hub 最小空實作先出現代表 Red：應有 2 則 bounded updates 卻為 0；超訂閱未拒絕。route 加入前真 PG 測例為 404 而非預期 stream，且不具有 scope owner 的錯誤回應。隨後實作到 Green，非以缺 import 當行為 Red。
- 2026-09-30 窄測試 **62 passed in 3.84s**，命令如下（測試 DB 為明確 loopback `_test`；fixture 每次用自己的 schema）：

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
$env:PYTHONDONTWRITEBYTECODE='1'
.venv-target/Scripts/python.exe -m pytest tests/unit/test_consultant_commentary.py tests/contracts/test_commentary_update_contract.py tests/integration/test_commentary_stream.py tests/integration/test_consultant_status.py tests/contracts/test_consultant_turn_contract.py tests/unit/test_local_http_security.py -q --tb=short -p no:cacheprovider
```

覆蓋 queue/drop-oldest、scope 隔離、detach／無 replay、容量／超大丟棄、零上限拒絕、wire 額外私有欄位拒絕、真 PG scope／操作族、ASGI framing／disconnect、不改執行 active、HTTP 503／204，以及原公開 status／本機安全 guard 回歸。沒有付費模型、key、`.env`、服務啟停或 commit；未改 bootstrap／runner／model_requests。

- 正式 `scripts/generate_contracts.py` 與 `--check` 均 exit 0；一般 sandbox 執行先遇 Windows temp ACL PermissionError，經工具核准執行同一命令後成功，未改生成器或手改生成物。
- 本切片五個手寫 Python 檔 Ruff check／format check 通過；hub／route 的 targeted mypy strict 通過（`--follow-imports=silent`）。`git diff --check` 通過。

本切片未驗真 provider → callback → 瀏覽器的完整串流或跨程序負載；主線整合及 T16／T17 gate 保留。測試不以暫態收到當成正式完成，也不改原取消／資格要求。

## 主線 composition 接入後複驗

2026-09-30，主線已注入 hub 與 A native-stream callback 後再驗。`test_commentary_stream.py` 改用 bootstrap 真正建立的 hub，不再替換成測試 instance；直接驗 `text/event-stream`、`X-Accel-Buffering: no`、`Cache-Control` 包含 `no-store`、固定公開 event/data bytes。斷線後可重新占滿全部 64 個預設訂閱名額且 queue 為空，下一訂閱為 503，原 execution 仍 active。錯檔案／操作族仍先回 404，cancelled terminal 為 204 空 body 且 no-store。

上述窄命令加上 `tests/integration/test_consultant_http_execution.py` 後，**65 passed in 5.62s**；包含真 PG 的 synthetic SDK formal-answer/native-stream 接線回歸，無對外 API。修改後 test 的 Ruff check／format check 也通過。本輪只調整此 test 與本 evidence，未改任何 production 接線、schema 或生成物。真 provider／真瀏覽器仍留主線後續驗證。
