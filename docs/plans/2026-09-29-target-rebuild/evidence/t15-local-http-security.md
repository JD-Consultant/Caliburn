# T15 loopback HTTP 信任邊界窄切片

- 日期：2026-09-30；本片只交付 HTTP Host／來源防護，不宣告全部 T15、安全 gate 或 production 切換完成。
- 責任：[介面與交付 §5](../../../implementation/interface-and-delivery.md#5-安全與新舊切換)、[交付運作](../../../architecture/delivery-and-operations.md)、[安全驗收 V24](../../../architecture/verification.md)、[共同工具規範](../../../specs/2026-09-27-agent-tool-contract-design-research.md)。HTTP 邊界不代替 workflow 的檔案隔離、execution writer 或工具資格裁決。
- 首切片只新增 `transport/http/security.py`、`tests/unit/test_local_http_security.py` 與本證據；主線負責 bootstrap 整合。後續已授權的 TestClient 機械調整與產品接線回歸見末節，Settings、registry、runner 與前端仍未由本片修改。

## 接線與明確 policy

在 `create_app` 建立 FastAPI 後、啟動前加入：

```python
from caliburn.transport.http.security import LocalHttpSecurityMiddleware

app.add_middleware(LocalHttpSecurityMiddleware)
```

公開 constructor 為 `LocalHttpSecurityMiddleware(app: ASGIApp) -> None`。不用 DB、key、額外 store 或 auth config；維持現行 single-local 模式。server 仍須只 bind loopback，middleware 不能替代網路 bind。

- Host：沿鎖定 Starlette `TrustedHostMiddleware` 解析，只接受 `127.0.0.1`、`localhost`、`[::1]`，關閉 www redirect；缺少／多值 Host 先拒絕。Host port 依 framework 語意不參與 hostname 比對，Origin port 則精確比對。不允許 `testserver`、萬用字元、任意 DNS 或其他本機 hostname。
- Origin：六個精確值為 `http://{127.0.0.1,localhost,[::1]}:{8100,5173}` 的組合；若有 Origin，所有 HTTP method 都核對。`null`、空值、重複值、錯誤 port、路徑／userinfo／相似網域均拒絕，不以字串 prefix 放行。
- unsafe method：除 GET／HEAD／OPTIONS 外一律檢查。`Sec-Fetch-Site: cross-site`、未知／多值 `Sec-Fetch-Site` 拒絕；否則需合法 Origin 或 `Sec-Fetch-Site: same-origin`。`same-site`／`none` 單獨不構成許可。GET／HEAD／OPTIONS 必須由 route owner 保持無副作用。
- CLI fallback：沒有 Origin、Referer 或任何 Fetch Metadata 才能用唯一 `Content-Type: application/json`（可帶 charset）。沒有 body 的控制請求可顯式帶合法 Origin 或 JSON Content-Type。未知來源的 form／text/plain／無 Content-Type 不因「看似 CLI」而放行；不使用 User-Agent 或 client IP 分辨瀏覽器。
- 不信任 `Forwarded`／`X-Forwarded-Host`，不增加 CORS header、不開 wildcard CORS。錯誤為 Host 400／provenance 403，無回顯使用者輸入；403 `Cache-Control: no-store`。拒絕前不讀 body，不進入 route；純 ASGI 保留原 body／stream 分塊。

## Vite、CLI 與主線最小測試調整

現有 Vite `/api` proxy 指向 `http://127.0.0.1:8100`；瀏覽器對 5173 發同源 request，proxy 保留其 Origin／Fetch Metadata，不需要 CORS。測試涵蓋保留 frontend Host 與重寫 backend Host 兩種 shape，以及 IPv6。這是 ASGI header-shape 驗證，沒有宣稱啟動 Vite 或真瀏覽器驗收。

Vite 必須實際使用 5173；若 busy 自動選 5174，明確 Origin 不在 allowlist，會 fail closed，不能為 demo 臨時放寬為任意 local port。8100 是現行 backend 入口。直接由 frontend 跨 origin 呼叫 8100 不是本次支援路徑，應沿現有 `/api` proxy。

CLI JSON 請求維持現有 `Content-Type: application/json` 即可。bodyless POST／DELETE 的最小明示 header 為 `Origin: http://127.0.0.1:8100`；唯讀 CLI 只需合法 Host。

主線安裝 middleware 時，既有 **7 檔、10 個 TestClient constructor** 需效果等價機械調整，不能加入 production `testserver` 例外：

```python
TestClient(
    app,
    base_url="http://127.0.0.1:8100",
    headers={"Origin": "http://127.0.0.1:8100"},
    # 原 backend_options 與其他參數照舊。
)
```

檔案：`tests/integration/conftest.py`（1）、`test_consultant_http_execution.py`（3）、`test_consultant_memory_http_journey.py`（1）、`test_database_migrations.py`（2）、`test_input_acceptance.py`（1）、`tests/unit/test_bootstrap.py`（1）、`test_settings.py`（1）。一般 journey fixture 模擬合法同源瀏覽器；本片安全反例 fixture 不預設 Origin。OpenAI MockTransport 的 `base_url=https://openai.invalid` 不屬 HTTP TestClient，不改。

## 官方核對與 Caliburn 取捨

2026-09-30 查 [FastAPI middleware 官方文件](https://fastapi.tiangolo.com/advanced/middleware/#trustedhostmiddleware)，並完整核對本機鎖定 FastAPI 0.141.1／Starlette 1.7.0 的 `starlette/middleware/trustedhost.py` 及 `_utils.py` Host parser。沿框架 Host／IPv6 解析，不再建另一個 parser。

[OWASP CSRF 指引](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) 建議拒絕 cross-site unsafe 請求；Fetch Metadata 缺席須有額外判斷，simple request 不受 CORS preflight 保護。本片採精確 Origin、同源 metadata，及無瀏覽器訊號時非 simple JSON fallback。這是 Caliburn 的 loopback 相容取捨，不是辨認 CLI 身分或全面防護保證；未新增 cookie/token session 或 auth 平台。

## Red–Green 與限制

先對未保護的真 FastAPI ASGI route 設副作用紀錄，得到 **30 failed、11 passed**：惡意 Host／Origin、cross-site 與 ambiguous header 均曾回 200 且 route 被執行，不是 import error 或假 mock。加入 middleware 後，同一批反例均拒絕且 route 紀錄為空。

補驗缺失 Host／惡意 provenance 在讀 body 前拒絕、response 分塊不緩衝、唯讀與 CLI 相容、無 CORS preflight 授權，以及真 `create_app(Settings())` 手動安裝 middleware 後健康路徑。命令（`apps/api`）：

```powershell
.venv-target/Scripts/python.exe -m pytest tests/unit/test_local_http_security.py tests/unit/test_bootstrap.py tests/unit/test_settings.py -q --tb=short -p no:cacheprovider
.venv-target/Scripts/python.exe -m ruff check src/caliburn/transport/http/security.py tests/unit/test_local_http_security.py
.venv-target/Scripts/python.exe -m ruff format --check src/caliburn/transport/http/security.py tests/unit/test_local_http_security.py
.venv-target/Scripts/python.exe -m mypy src/caliburn/transport/http/security.py --follow-imports=silent
```

首切片加既有 bootstrap／Settings 窄回歸 **57 passed**；Ruff check／format、scoped mypy 通過。當時尚未安裝至正式 bootstrap；整合後的 HTTP／控制旅程見末節。沒有 PG owner 變更，未重跑完整 DB suite；沒有真模型／付費 API、.env、commit。

限制：不能抵擋能偽造 HTTP header 的本機惡意程序、受信任 origin 上的 XSS 或已受控 loopback 服務；不新增 WebSocket provenance 契約。CORS／remote exposure、port 或登入模式日後若改，須重新驗這個邊界。本片不覆蓋秘密日誌、prompt injection、容量、query 效能或其餘 T15 gate。

## 主線安裝後：TestClient 與產品 composition 回歸

2026-09-30 主線已在 `bootstrap.create_app` 安裝 `LocalHttpSecurityMiddleware`。先以未調整的既有測試確認 **2 failed、8 passed**：`test_health_and_openapi_without_credentials` 與 `test_legacy_database_setting_is_not_used` 都因預設 `Host: testserver` 得到 400，並非 production allowlist 缺陷。

依本次明示授權，完成上述 **7 檔、10 個 TestClient constructor** 的 loopback `base_url` 與合法預設 Origin；保留原 `backend_options`、assertions、dependency override 與其他代理變更。修改 `test_input_acceptance.py` 前已通知 Volta，只動 reconnected constructor 的兩個 args，不碰其 F2 修補。

`test_local_http_security.py` 最後的 `test_real_bootstrap_keeps_offline_health_and_blocks_bad_host` 已移除手動 `add_middleware`，直接呼叫 `create_app(Settings())` 驗 health、惡意 Host 400 與 `Origin: null` 403。此測例不預設 Origin，不再以第二層 guard 遮蔽產品接線缺口；獨立 middleware 反例 fixture 仍保留自己安裝的單層 guard。

已使用既有獨立 loopback PostgreSQL 測試環境，每例沿 fixture 建立／清理自己的 namespace。合成 provider 使用既有 MockTransport，沒有付費模型請求。`apps/api` 執行：

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
$env:PYTHONDONTWRITEBYTECODE='1'
.venv-target/Scripts/python.exe -m pytest tests/unit/test_local_http_security.py tests/unit/test_bootstrap.py tests/unit/test_settings.py tests/integration/test_job_files.py tests/integration/test_job_file_rename.py tests/integration/test_input_acceptance.py tests/integration/test_input_replay_readiness.py tests/integration/test_consultant_http_execution.py tests/integration/test_consultant_http_controls.py tests/integration/test_consultant_memory_http_journey.py tests/integration/test_interview_history_turns.py tests/integration/test_database_migrations.py tests/integration/test_jd_profile.py tests/integration/test_jd_work.py tests/integration/test_jd_export.py -q --tb=short -p no:cacheprovider
```

結果 **163 passed，60.40s**，涵蓋共用 HTTP fixture 的建檔／改名、輸入准入與 F2 重送、無正文 pause／resume／cancel、範圍拒絕、正式歷史、JD 編輯／讀取／匯出、migration 啟動 gate，以及 A→Memory 發布→下一輪固定快照的合成 provider 旅程。8 個本次變更測試檔的 Ruff check／format check 通過，相關 tracked diff 無 whitespace error。

production allowlist 未增加 `testserver` 或任何例外；本次沒有改 middleware policy、bootstrap、F2 owner、schema、generated、registry 或 runner。仍未重跑完整 PG suite／真瀏覽器；未 commit。
