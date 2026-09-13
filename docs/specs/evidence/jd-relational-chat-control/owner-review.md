# 聊天准入：共用 owner 獨立審查

日期：2026-09-13。基準 `36cc1cb9` 加本輪未提交 diff。審查者未實作本輪 `manual_runtime.py`／`test_foreground_admission.py` 變更；僅唯讀核對這兩檔及必要既有呼叫／關閉接點，新增本報告，不修改被審程式。

**結果：本次範圍沒有未處理 P1／P2，無阻擋發現。**這是同程序 owner 接點審查，不代表聊天 HTTP、Web、真 DB／新程序或自然模型全部完成。

## 核對結果

| 重點 | 實際程式與反例 |
|---|---|
| 同文件驗版→Future 原子准入 | `admit_foreground` 在同一 slot RLock 與 start_token 期間完成原 request 查回、idle checkpoint、current head／封存檢查、最後 open／host 再核、`_launch_foreground` 的真 Future attach。沒有讀完版次釋鎖後再重新准入的空窗。測試讓 head 查讀阻塞，同文件 catalog 等待後被 busy 拒絕，另一文件仍進行。 |
| 原 request 優先 | `lookup_original` 先於 owner same-run 比較、current head 檢查；callback 拒舊格式／不完整查找先傳回。合法已知原結果不因 head 前進而被新 stale 規則改寫。same-run改digest仍拒絕。 |
| public read 不取得 writer 權限 | `inspect_document` 僅登記 thread ID／完成 Event，無 `_execution`、`_catalog_execution` 或 foreground permit。callback 執行時不保留它所取得的 slot lock；同文件／別文件的正常寫入可進行，live AI 工具亦可保存。 |
| 關閉等待實際讀取 | `close` 先關准入，再取得現有 slots；新讀取不能在此後登記。已登記讀取要等 callback finally 移除 token、set完成 Event，不能把 timeout 當作讀取已停。 |
| 同執行緒重入與失敗 | start／catalog token與read_tokens讓 callback 裡重入 close 回 False，避免 RLock 重入被誤認為已排空。head 查讀後再次檢 open／host，阻止在重入 close 或 lease失效後派新 Future。read 的 ValueError／KeyboardInterrupt 等出口也由 finally 解除自身 token。 |
| status 不晚讀已關閉 Saver | 已有 foreground／operation／start／catalog state 可直接回可證觀察；尚未 startup 或已停止接收時直接回阻擋狀態。需要讀 idle checkpoint 時經 `inspect_document` 納入 drain；不是關閉後直接碰 Saver。 |
| 失敗沒有偷偷執行 | stale／封存／未知文件／head失敗／pending／lookup未完整均沒有 foreground或工具效果。executor submit失敗保留實際 known-not-started，沿既有明確收尾，不製造已執行 Future。 |

`status` 是一個觀察，不是後續寫入許可。若讀取期間發生關閉，consumer仍要合併當下 `ready`；所有真正寫入再次驗准入。不能把一次 WriterStatus 的沒有 pending 等同 host仍可接收。現 `ManualService.status` 的責任分工維持此界線。

## 保留的 caller 契約

- `lookup_original` 必須回已驗的原 request 或在原範圍確知不存在時才回 None；不完整歷史、格式／digest不相容要拋固定錯誤。owner 不重建第二個聊天 decoder。
- `inspect_document` callback 必須在返回前完成同步 I/O，回已具體化的材料；不能回 lazy iterator／另起 background worker後立即返回。這是少數 App ports 的明確契約，沒有新增通用 worker／queue 管理器。
- `start_foreground` 保留為舊內部低階接點；新的公開聊天 start 必須走 `admit_foreground`。本報告沒有把既有低階測試入口當成新的 HTTP API。
- 原話與保存結果語意、原 run歷史定位、HTTP投影由 coordinator／chat service／history 契約另核；read token 不授予 SQL或 checkpoint寫入權。

## 實際驗證

獨立執行下列四個受影響測試檔，**116 PASS，0.85 秒**：

- `tests/test_foreground_admission.py`
- `tests/test_foreground_runtime.py`
- `tests/test_manual_runtime.py`
- `tests/test_catalog_runtime.py`

使用隔離已鎖定環境 `uv run --offline --frozen --no-sync`；真 ThreadPoolExecutor／Event，SQL、模型與宿主死亡為測試 port。0 provider、0 DB、新程序未啟動。本次沒有新增反例首敗，因唯讀審查未找到需要修改的具體問題；不以舊全組數字充作本次重新執行結果。
