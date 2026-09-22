# 固定 Memory 讀取接合：獨立審查

日期：2026-09-13。基準 `81a1ca76`，檢查本輪未提交的 `ai_checkpoints.py`、`memory_context.py`、`consultant_context.py`、`consultant_tools.py`、`ai_runtime.py`、`inspection_model.py` 與相關測試；附帶核對 `DocumentState` 通道及 managed composition 接點。

**結論：本次限定範圍未發現可重現的 P1／P2 阻擋問題。** 本審查者是 package `read_tools.py` 作者，因此該 package 實作及其測試不算本人的獨立審查證據；這裡核對的是其他作者的 App／checkpoint 接合。

## 核對結果

| 接點 | 實際核對及界線 |
|---|---|
| 舊 START／歷史相容 | `AiRunCheckpoints._initial_material` 只接受原四鍵或加一個 `jd_memory_view` 的形狀。舊 START 缺此欄位時明確置 `None`，不從上一輪 root 繼承。舊已閉合／停在 child 的回合仍可讀；沒有 run 卻有 Memory view 不能偽裝空歷史。 |
| 固定 root／child | `_material` 透過純 `checked_memory_view` 核格式、UUID、三 scope、revision／version 配對及 guide digest；不開 Memory 連線。讀 child 時同時核 run record 與 Memory view 和原 root 相等。觀測結果以 JSON 私有副本保存，呼叫者改回傳 dict 不會改原觀測。 |
| 保存回覆遺失 | `close` 保存原觀測的 Memory view；`exact` 包含 view 等值。原生 update 成功但回覆遺失仍只重讀，不重送 update。保存了不同 view 時回 `closure_unconfirmed`，不以相同訊息或狀態誤報成功。 |
| 每輪固定選版 | `MemoryReadSession.open` 在 owner 的前景工作內，以既有 publication／Store 取 head 與 guide，再將版號／版本ID／digest 寫入原生 input checkpoint。後續 model/tool 驗同一 session、state、Store instance、dataset/doc/run、thread 及 stop；不在每次讀取時重新取 publication head。未發布、缺已發布 guide 分別處理，後者不假裝空 Memory。 |
| 模型 context | Memory guide 只作本次 request system projection，明示它是導覽資料，沒有覆寫原 `HumanMessage`；固定 view 不是「模型已讀完整 Memory」收據。模型呼叫之前先核相同 session 與 state。 |
| 工具執行 | `AiToolSession.prepare` 將四個 Memory 名稱分類為 readonly，不建立 JD `BoundEdit`；`AiToolMiddleware` 先核原 call identity／prepared，才透過 public `ToolCallRequest.override(tool=...)` 選固定 reader 的原生工具。參數仍交原生 ToolNode；未知 session 的 advertised backend 不能執行。來源工具沿自身來源 owner，未增加原話保存權威。 |
| 取消／重開收尾 | `_verify_saved_results` 不把 readonly 結果當 SQL receipt。停止後未閉合的 Memory read call 補 `memory_read_not_completed`／`stop`，不重播模型、文件讀取或來源讀取；`_settle` 保留原 checkpoint Memory view 後閉合。取消必須等既有 owner 真正工作結束，未修改排空規則。 |
| 未啟用／inspection | `execution_enabled` 沒有因 Memory 工具變成 true；普通 managed composition 仍沿原 enable_chat。inspection 使用相同原生工具布局，model/tool 外層 guard 與 after_model inspection guard 保留，讀 checkpoint 不需要 Memory session 或 provider。 |

## 獨立執行

使用新 App 的 lock／editable 環境，Python 3.12、Deep Agents 0.7.13、LangChain 1.4.0／core 1.6.3、LangGraph 1.2.11；沒有舊 worktree 的執行環境。

| 命令所含測試 | 實際結果 |
|---|---|
| `test_memory_read_recovery.py test_consultant_memory_context.py test_consultant_inspection.py` | **56 PASS／9.26s** |
| `test_memory_read_tools.py test_consultant_tools.py test_ai_runtime.py test_ai_checkpoints.py` | **162 PASS／11.59s** |

這兩組測試檔不重疊，共 218 案。本次首跑即通過，沒有新失敗需要改測試；未修改產品或測試。原始輸出為 `.research-tmp/jd-memory-read-independent.txt` 及 `.research-tmp/jd-memory-read-independent-runtime.txt`。

在 `experiments/jd-relational-app` 可使用下列共同前綴重跑表列檔案：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_memory_read_recovery.py tests/test_consultant_memory_context.py tests/test_consultant_inspection.py -q -p no:cacheprovider
```

本次證據是原生圖／InMemorySaver／InMemoryStore、合成模型及 SQLite；**沒有執行 PostgreSQL、宿主新程序、服務、瀏覽器或 provider**。只讀過新 `test_consultant_memory_postgres.py` 的驗收路徑，沒有把它計為本人的通過結果。固定回覆下的 Memory 讀取不等於 C／B1／B2 已接合，也不等於自然訪談品質已通過。

早先接合時核實的版本差異已收斂：Deep Agents 0.7.13 明確拒絕已移除的 backend factory；現行 App 採已安裝 LangGraph 的 `override(tool=...)`，沒有把 callable 重新包成另一套 backend engine。這是前置核對後已落地的選擇，不是本報告留下的 OPEN 問題。
