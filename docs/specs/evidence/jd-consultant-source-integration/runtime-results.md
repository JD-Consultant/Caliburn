# 當輪來源：App 接線與故障驗證

2026-09-13；本檔只記 root 實際執行；[作者來源測試](source-results.md)、[真資料庫](postgres-results.md)、[獨立審查](review.md)分開保存。

## 接線

`ConsultantContext.source_notice` 是可信 App callback，在真正 model request 上驗證原話及供 metadata，不新增 state／ToolMessage／原話副本。`AiRuntime.conversation_sources` 每輪建立自己的 lazy notice，並將同 owner resolver 給既有工具 session；既有明示 resolver 與此 owner 不能並存。`managed_app` 使用原宿主 graph、同持久 key／dataset，人工與 AI 注入同一來源服務，一般 `enable_chat=False` 不變。

來源讀取故障在工具準備階段停止回合，不要求模型修不存在的參數錯誤，也不執行下一模型步。人工保存的 history／source／bind 準備用既有 `inspect_document` 等待讀取結束，然後才由既有 `submit` 獨立檢查寫入准入；沒有新鎖或另一個 owner。

## 首敗及修正

- 新 context 反例先跑：1 FAIL，`ConsultantContext` 尚無 `source_notice`，模型未呼叫。接合後一項測試的整段錯誤正規式被原生 graph 加上的 task notes 影響；改核 `str(error)`／`code` 原值，未放寬錯誤或回傳正文。
- 初步 context／原 context：20 PASS，2.57s。
- 獨審 CSI-R01／02 指出故障歸因與人工讀取排空。root 的兩個反例修前 **2 FAIL，3.62s**：来源故障後模型仍繼續；來源 resolver 還在執行時 `owner.close(0)` 竟回 True。
- 修正後受影響組 **103 PASS，10.95s**。來源故障停止在第二個模型步、writer 0；讀取期間 close 回 False，讀取退出後能關閉。既有純訪談、取消、原請求查回與資源生命週期仍通過。

```text
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider tests/test_conversation_source_failures.py tests/test_consultant_source_context.py tests/test_consultant_context.py tests/test_consultant_tools.py tests/test_manual_service.py tests/test_managed_app.py tests/test_ai_runtime.py
103 passed, 1 warning in 10.95s
```

唯一 warning 為既有 Starlette TestClient 使用 AnyIO alias 的 deprecation；本次不為它升級框架。沒有改生成契約、依賴、schema 或 Web，因此沒有重跑無關的生成／前端整組。

## 效力

這組使用真 native Agent／Saver／Futures 與合成 material ports；不是 PostgreSQL、真瀏覽器、自然模型或真人證據。費用、來源 UI、較早 Memory 回查與完整專業顧問仍按[收尾清單](../../2026-09-13-jd-app-open-issues.md)推進。本輪沒有 provider 請求，也沒有正式產品採用切換。
