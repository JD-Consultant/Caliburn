# 聊天狀態與歷史讀取：獨立窄審

日期：2026-09-13；基準 `2734b82b` 後本輪差異。審查者沒有修改受審 production source；只新增 [test_chat_execution_state.py](../../../../experiments/jd-relational-app/tests/test_chat_execution_state.py) 與本稿。以下 PASS 只適用指定接點，沒有執行 provider、PG、HTTP、瀏覽器或 OS 宿主。

## 1. CH-R01／P2：已完成的工作誤顯執行中——已關閉

原 [AiRuntime._active_status](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py) 將 `ForegroundHandle.wait(0)` 的 Timeout 當成工作仍在執行。但該 wait 等待的是 owner callback 的 settled Event；原生 Future 完成與 callback 排空是兩個不同事實。

首個唯讀離線探針使用真 `concurrent.futures.Future`，將結果設為完成、保持 owner callback Event 未完成；原碼實際輸出：

```text
{'future_done': True, 'future_running': False, 'owner_callback_done': False,
 'public_status': ('running', False)}
```

這是原碼探針失配證據，並非先跑出 pytest failure。修正由主代理完成： [ForegroundHandle.execution_running](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py) 只觀察原 Future 是否尚未 done；公開狀態用此事實區分 running／closing，沒有放寬原 wait 的安全語意。

新增九個回歸案例：完成／異常／取消 Future、尚排隊／真正 running、closure 失敗、沒有本地 handle，以及真正 ThreadPool 工作已完成但 owner callback 被 Event 暫停的情境。關鍵斷言：

- Future done 且 callback 未完成時為 closing，不能標 running。
- 同時 `handle.wait(0)` 仍 Timeout，原 writer 排他與閉合要求保留。
- Future 尚未完成仍 running；stop 只是協作旗標，不會取消 callable。
- closure 已失敗為 recovery_required；沒有本地 handle 不推定已停止或已閉合。
- 不因晚到的 stop 將已結束工作改標取消。

**判定：P2 已關閉。**沒有以禁止並行、提早解除排他或忽略 callback 的方式規避。

## 2. 其他指定狀態接點

唯讀核對 `inspect_run / _public_response / execution_enabled`，未發現其他 P1／P2：

- 先固定原 native observation，再讀該 run 的全部 SQL 回執。活動中的 SQL 可比固定 bindings 新，但投影仍 unconfirmed，不宣稱全部效果已知。
- terminal 只有在 root 已 closed、無 pending call、SQL 集合與 bindings 完全相等、全部回執 confirmed 且已保存 ToolMessage 與真結果相符時才 settled。多出的 SQL 不被 terminal 投影忽略。
- 本地 attempt 還沒完成持久收尾，即使 native terminal 已可讀仍保守 closing；原話確知未存必須有原本地結果證據，不能將不存在或未知換成 not_saved。
- 舊 run 沿既有祖先查回；公開 response ID 從該原 Human 後的公開正文挑選，不拿工具專用訊息或前一輪回覆冒充。
- `execution_enabled=False` 在新原請求准入前拒絕，仍能查回原已受理請求；沒有模型重播或增加另一套保存權威。

上述是程式窄審，不單靠 DTO shape 推定保存證據成立。

## 3. 歷史與新增固定 source 接點

獨立唯讀審查 [chat_history.py](../../../../experiments/jd-relational-app/src/jd_relational/chat_history.py) 與別人本輪新增的 [observe_at(source_config)](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) 差異。既有 observe_at 的原基底是本代理前輪實作，此處只將它當已知介面，**不將自己原實作宣稱為獨立審查**。

未發現本輪 P1／P2 阻擋：

- 初頁固定 root 與實際 source checkpoint；續頁以具名用途簽章驗 dataset／document／run／root／source／offset。改 key、scope、用途、未知欄或失效位置固定失敗，不退回 latest。
- explicit source 讀 root 時 `subgraphs=False`，只核原 task namespace；再讀已指定 child checkpoint，沒有順帶選取新的 latest child。root／child scope、原 record 相等與原訊息前綴仍驗證。
- START 只允許 root 作 source，沿原 saved input 解碼。沒有 child 的 root 不能混入另一個 source；即使簽過但缺失的 checkpoint 也不改查別份。
- 使用 Core 公開 message.text 屬性抽出 AI 正文，Human 仍是原字串；chunk 拒絕。工具、system、thinking、signature、usage 與 provider 欄位不出現在公開 message。
- 每頁最多 50 則及 1 MiB，整則訊息保留；過大單則明確失敗，不截斷原話。換 run 或同 child 前進不改舊頁 anchor。純查詢沒有 invoke、update 或恢復寫入。

限制：這條公開投影依賴既有完整 canonical messages 與已驗原生 checkpoint；不能把摘要或模型上下文當成全部歷史。Cursor 是簽章，不是加密；payload 只含位置與 scope，不包含對話內容。宿主排空與 live read 追蹤由 App／owner 接點負責，本 service 本身不發 writer permit。

## 4. 實際窄驗結果

在隔離目錄沿既有離線 lock 執行：

```text
tests/test_chat_execution_state.py tests/test_chat_history.py
48 passed in 1.32s

tests/test_ai_checkpoints.py tests/test_ai_checkpoint_discovery.py tests/test_consultant_inspection.py
104 passed in 2.42s
```

第一組為九個新增狀態回歸與 39 個既有 native InMemory 歷史案例；第二組驗新增 source 接點没有破壞原 checkpoint／START／discovery／inspection 行為。使用真 Future／ThreadPool 與 native LangGraph InMemorySaver、合成內容；不代表真資料庫或模型驗收。新增檔案的 `git diff --check` 通過。
