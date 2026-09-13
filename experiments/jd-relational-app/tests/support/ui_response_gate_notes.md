# 單次回覆遺失合成驗收 helper

此目錄僅供測試，不由 production import。查閱日期：2026-09-13。

- [ASGI HTTP 2.5](https://asgi.readthedocs.io/en/latest/specs/www.html) 的 Response Start／Body 說明：`http.response.start` 是應用送出回覆的邊界；server 可以到 body 才 flush。此 helper 在第一個 start **呼叫原 send 之前**等待，200／202 都涵蓋，原 body 不讀取、不改寫。
- 同份規範的 send exception／disconnect 不是 worker 停止證明；send 不一定拋錯。已核實安裝 Uvicorn 0.52.4 的 `protocols/http/h11_impl.py`：disconnected 時 send 可直接 return，因此 `released` 只代表交還原 send，不等於瀏覽器收到。
- Starlette 1.6.0 已安裝 `middleware/errors.py` 使用純 ASGI send wrapper。官方 middleware 網頁兩次回 502，未憑失敗頁推定其他能力；採直接核實的官方原始碼與 ASGI 契約。這些是現行穩定套件／規範；沒有新增依賴或複製通用中介層框架。

## 啟動（由主代理操作）

Python 使用本 App 的 frozen venv；設 `PYTHONUTF8=1`、`JD_RELATIONAL_TEST_DB=1`。路徑為 `tests/support/ui_response_gate_server.py`。

```text
prepare S:/caliburn/.research-tmp/jd-ui-gate-<32個小寫UUIDhex> --api-port 8767
initialize <同目錄>
serve <同目錄> --gate-timeout 90
arm <同目錄> --document-id <瀏覽器建立的合成文件UUID>
release <同目錄>
```

`prepare` 僅確認 127.0.0.1:55436 的固定合成 fixture DB／jd_test／PG180006 後建立全新 `caliburn_jd_setup_test_<同hex>`；不 DROP、不清資料。`initialize` 是獨立程序，原生 DPAPI 與 Windows host；待程序真退出才 `serve`。serve 在開 host 前核對解密設定的完整 fixture 範圍，普通開啟不 setup。使用相同 UI Origin `http://127.0.0.1:3002`；API 埠由 manifest 固定，8767／8768 都允許，不可和 Next 設定混指。背景啟動須 Hidden，保留 PID/stdout/stderr。

## 操作與證據

1. 等 `serve.ready.json`；瀏覽器先建立合成文件，再 `arm`。只攔該文件下一個 POST `/jd/edits`，後續 POST、GET、其他文件與 lifespan 通過。arm 和 claimed 保留，不得刪掉重新利用同 fixture 偽裝首個操作。
2. 由 UI 新增一項任務。`gate.held.json` 表示原 response.start 尚未轉送；`gate.committed.json` 由原 storage.execute 的 confirmed committed receipt 旁錄原 operation/revision。無正文、DSN、簽章 key 或 raw exception。
3. 用另一條只讀 DB 連線核實該 operation／revision。等待 UI 原生 15 秒 fetch timeout，確認待查回；關頁重開後不應自動新送編輯。透過 UI 查回原 operation；同時 GET 仍能完成。
4. 閘門有 90 秒上限；在 `gate.finished.json` 出現前，以 `release` 釋放。release CLI 同時要求 held＋committed 文件；wrapper 也要求自己的真 receipt 觀察。逾時會留下 `outcome=timeout`，不能列成功。可以先完成瀏覽器 timeout 再 release，之後關頁重開，避免人工步驟超時。
5. `gate.routes.json` 只計指定文件 `/jd/edits` 的 POST 與原 operation UUID 的 GET：重開／查回後應維持 `edit_post_count=1`、`original_operation_get_count` 增加，可區別被 server 去重而未進 execute 的重送。`writer.observations.json` 另計真 execute 入口／原結果；查回後與 DB 對照只新增一次任務／一份 revision／一筆 receipt。最後在目錄建立 `stop.request`，等待 `serve.finished.json` 並另核 native PID 真退出；不以檔案或 Future 狀態冒稱程序死亡。

`released`／`send_disconnected` 都不是接收端 ACK；完整通過需要瀏覽器重開、原操作查回及獨立 DB 證據。此情境不是斷電、瀏覽器程序 crash、磁碟損壞、自然模型或真人驗收。純 ASGI 單測用合成 observation，只能證明閘門控制流；真 DB 證據須由上述原生旅程補齊。
