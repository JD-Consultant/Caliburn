# T09 Responses 公開 commentary 串流

狀態：provider 側有界實作、離線 SDK wire 與 shared ResponseStep 原生記憶體 saver 承接已驗；App 暫存／HTTP／UI、PG 與真 provider 驗收由各 owner 補證，**本節不宣稱 T09 完成**。

## Provider 切片（2026-09-30）

本輪限 adapters `openai_responses`／新 `response_streaming`、workflow `model_requests` 注入與相關測試。不改 A prompt／runner／bootstrap、shared loop／tool steps／compaction；不啟停、不讀 key／`.env`、不接 DB、不外送或 commit。工作直接在共享 worktree，並行變更不納入本切片完成宣稱。

### 官方契約與本機依據

- [Responses streaming](https://developers.openai.com/api/docs/guides/streaming-responses)：使用官方 `responses.create(stream=True)` typed events；沒有另建 SSE parser 或模型迴圈。
- [Reasoning phase](https://developers.openai.com/api/docs/guides/reasoning#phase-parameter)：僅明示 `assistant`／`commentary` message 的公開文字可投影。`final_answer`、缺 phase、reasoning、function arguments 不納入；模型不保證每輪產生 commentary，空更新是正常結果。
- [Streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events#response.completed)：直接保留 completed／failed／incomplete terminal event 的原生 `response`；公開 deltas 不是原件，也不據其推導正式完成。
- 本機鎖版 `openai==3.20.0`、`httpx2==2.13.1`。檢查 SDK `lib/streaming/responses/_responses.py` 與 `lib/_parsing/_responses.py`：parsed helper 可能對 strict tool arguments 先做 JSON parsing，且其 final accessor 只接受 completed。本切片不用該 helper，不補造或重組原件；synthetic terminal 含無效 arguments 字串仍須完整帶回。
- 檢查 `_streaming.py`／HTTP `aiter_raw` 的 finally cleanup：取消可能被 close error 蓋過，HTTP transport error 又會包成 `APIConnectionError`。已用反例重現；只辨識此已知單層 SDK wrapper 與直接取消 context，不掃任意例外鏈、不把普通傳輸失敗一概改成取消。

### 公開介面與責任

`ResponseRequest(..., stream: bool = False)` 保留原預設；snapshot false／true 原樣還原，不接受字串布林；token count payload 不帶 stream。只有主線新 A composition 決定何時設 true，舊 snapshot 不升級。

新公開 frozen dataclass `PublicCommentaryUpdate(response_id: str, message_id: str, text: str)` 位於 `adapters/response_streaming.py`。`create_response(..., on_commentary=...)` 與 `ModelRequestExecutor(..., on_commentary=...)` 接同步 `Callable[[PublicCommentaryUpdate], None] | None`。callback 只收到同 message 累積文字，按原 response/message identity 更新；完整 item／done 事件不重複相同更新。文字不進 dataclass repr。

callback 是短小、非阻塞投影，不負責保存；普通 observer exception 只停用本次 observer，固定安全 warning 不記正文／exception payload；`CancelledError` 不當成 UI 失敗吞掉。同步 callback 本身若阻塞仍會阻塞 event loop，組裝者不得在其中做網路／DB I/O。

terminal R 在任何 cleanup await 前保留；收到後不等 EOF。close 失敗時 adapter 拋 `ResponseStreamCleanupError.response`，取消拋 `ResponseStreamCancelledError.response`（繼承 `CancelledError`）。executor 包入既有 `ReceivedModelResponse(R, attempt_id)`：

- `ReceivedModelResponseError.received`：完整 R 與原 admitted attempt，不得進 provider retry／新 reserve。
- `ReceivedModelResponseCancelledError.received`：同上，而且仍是取消；shared owner 必須先沿既有 recovery 保存／保留原件，再向上傳取消，不自動續跑。

**跨 owner 接線 gate**：Pascal／主線已將以上兩個 handoff 類型收斂到 `agent_execution/tool_steps.py`，workflow 只 import，不存在反向依賴或重複類型。shared request_model 捕獲 carrier→正常 sync 保存→原 recovery／取消承接；本切片追加 SDK wire→executor→shared native saver 證據（下文），不是只驗 adapter。沒有第二保存 owner／receipt／event table，正式歷史仍從既有完整 response checkpoint 投影。真 PG／產品取消接線不能由記憶體 saver 通過推定。

terminal 前乾淨 EOF 明確拒絕，不拿已顯示文字補 R；terminal 前取消仍取消。其他 provider error 的原 executor 分類與預算／重試 owner 不變。

### Red–Green 與驗證

1. 先新增官方 SDK＋`httpx2.MockTransport` 的合成 SSE 行為測試；排除 fixture 編碼修正後，11 項因缺少 stream／callback 接縫而 Red，再實作轉 Green。測試沒有真 provider／網路。
2. 取消＋cleanup error 反例先重現原取消被遮蔽；HTTP `ReadError` 又先 Red 為 SDK `APIConnectionError`，再修窄交界轉 Green。另以實際 `task.cancel()` 驗 terminal cleanup 的取消 carrier，task 仍 cancelled、僅一次 HTTP、原 R 完整。
3. 覆蓋 completed／failed／incomplete 原件、strict malformed arguments 不被 helper 提前解析、public allowlist／錯 item index／無 phase、不保證 commentary、done 去重／frozen update、observer 失敗、無 terminal、terminal 後破損尾端、executor 原 attempt／無 provider retry。

實際最終驗證命令與結果見下一節；不把離線成功等同真模型串流品質、PG 保存、HTTP SSE／瀏覽器斷線取消或完整 Demo 驗收。

## 本切片驗證記錄

在 `apps/api` 執行：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_response_streaming.py tests/unit/test_terminal_response_handoff.py tests/unit/test_result_save_cancellation.py tests/contracts/test_openai_responses.py tests/contracts/test_response_serialization.py tests/unit/test_import_boundaries.py tests/unit/test_response_steps.py tests/unit/test_response_recovery.py tests/unit/test_response_retries.py tests/unit/test_public_commentary.py -q -p no:cacheprovider --tb=short
```

接線後 fresh 結果 **128 passed in 2.57s**，其中本切片 provider streaming 檔 **20** 項；另兩個 shared handoff／cancel 測試檔屬 Pascal，未由本切片修改。新增跨接縫兩例沿實際 SDK SSE transport→executor→`run_response_step`：cleanup error／cancel 在上傳前已有 native checkpoint 的**完整 raw terminal R＋原 attempt**，且 tools／accounting 未執行，reserve／HTTP 各一次。另包含 Pascal 的保存失敗保留原件、真正 task.cancel 與明確重入不重問測試。先前 provider 較窄集合為 110 passed；此處使用接線後 fresh 結果，不混同真 PG。

既有 contract 將過去「true 一概拒絕」更新為「非布林 `"true"` 拒絕」；store true 仍拒絕，不放寬其他 snapshot 欄位。

```powershell
./.venv-target/Scripts/python.exe -B -m ruff check src/caliburn/adapters/openai_responses.py src/caliburn/adapters/response_streaming.py src/caliburn/workflows/model_requests.py tests/unit/test_response_streaming.py tests/contracts/test_openai_responses.py
./.venv-target/Scripts/python.exe -B -m mypy src/caliburn/adapters/openai_responses.py src/caliburn/adapters/response_streaming.py src/caliburn/workflows/model_requests.py src/caliburn/agent_execution/tool_steps.py --follow-imports=silent --no-incremental
```

Ruff 全通過；接線後 mypy 含 shared `tool_steps.py`，**4 source files 無錯誤**。scoped `git diff --check` 通過（只見既有 Windows 換行提示）。初次 mypy 用 Windows `NUL` 作 cache directory 造成工具 internal error，改以 `--no-incremental` 重跑成功，未把工具失敗當成程式通過。

本切片六個檔案：兩個 adapter、新／改 `model_requests`、新 `test_response_streaming`、既有 `test_openai_responses` contract、本 evidence。shared owner 與產品接線另由各自實作人追加證據，不覆寫上述驗證界線。
