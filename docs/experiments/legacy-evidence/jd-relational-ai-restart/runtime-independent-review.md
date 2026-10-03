# RS-4：新宿主 AI 恢復接合獨立審查

日期：2026-09-13。比較基準 `3980689a`。只讀審查 `manual_runtime.py`、`ai_runtime.py`、`managed_app.py` 本輪差異與 `test_foreground_restart.py`、`test_ai_restart.py`、`test_managed_app.py`；未改上述實作。審查者同輪實作 inspection/discover，故本報告**不把該兩個接點列為自我獨立審查通過**。

## 結果

此有界範圍未發現可重現的新增 P1／P2。執行上述三個離線測試檔，**39 PASS／1 warning，2.63 秒**。Warning 是 Starlette TestClient 使用 AnyIO 舊 BlockingPortal alias，非本輪新增錯誤。SQL／OS 在這三檔為明示合成埠；原生 LangGraph／InMemorySaver 及 Python Future 為實際執行。

核對的關鍵順序：

- `manual_runtime.py:263` 的全文件掃描先核 current host capability，每份文件進入一次具 token／文件／thread 的 startup callback。最後仍讀 native manual descriptor 並確認 foreground 已閉合；只有全掃描完成才 ready，含封存文件。
- `ai_runtime.py:188` 先讀固定、已核 scope 與原話的 record；`manual_runtime.py:346` 在 active startup callback 內才允許 adopt 原 identity，再次驗 exact original。foreign handle 沒有偽造 stopped Future，僅持既有 previous-host capability，不能進 `execute_foreground`。
- `ai_runtime.py:385`／`:405` 從原 binding 查 SQL receipt；缺結果時進現有 recovery，沒有重建 candidate、重播 model 或工具。存過的 ToolMessage 必須與原結果相符；缺少的只補可證原 tool call 的结果。terminal record 不因啟動而重標狀態。
- `manual_runtime.py:425`／`:580` 恢復要求本宿主實際 recovery Future／token，以及原 foreground 的真停止或 foreign capability；timeout 保留原 attempt，未停止前不能新建平行恢復。
- `ai_runtime.py:454` 附近閉合後再次確認 record/messages 與 native manual gate；`manual_runtime.py:602` 確認後又核 owner／停止證據才標 foreground closed。manual pending 不因 AI 結束被清除；已 terminal AI 後的 manual pending 仍由原 manual 恢復流程處理。
- `managed_app.py:48` 在啟動掃描前，將唯一 AiRuntime coordinator 掛在同一 host/runtime；配置不足時仍使用同布局、執行停用的檢視圖。ASGI lifecycle 未完成 startup 不開始供應正常請求；組合失敗仍 drain 原 host。

## 保留界線

- 這次沒有新 Windows 宿主、PostgreSQL、provider 或付費模型驗證，不能把合成 PreviousHost 當原生死亡證明。真原生跨程序接合由主代理的另一驗收單位負責。
- 最近一個已 terminal 的原請求可沿現有讀回；更早且已被後續 run 取代的 ID 仍可能回 `original_run_lookup_required`，沒有新做 bounded history lookup。本報告只確認此分支不當作新模型請求，不宣稱任意歷史請求都已可查回。
- 檢視圖 layout、discover 固定位置與 guard 的獨立複核需其他審查者；本報告僅引用其 API 契約作 root／owner 接合檢查。

## 追加：FH01–FH04 跨程序驗收檔與既有輸出獨審

只讀核對新 `tests/ai_host_recovery_worker.py`、`tests/test_ai_host_restart_postgres.py`。為驗證其 imported fixture 的實際通路，僅追讀既有 `_offline_model` 與 `engine` 的相關定義；沒有重跑 DB、服務或模型。

未發現可重現的新增 P1／P2 或把未發生故障當通過的反例。已讀主代理保存的原始結果：

- `.research-tmp/jd-ai-host-first-tests.txt`：**3 PASS／1 FAIL，48.23 秒**。FH04 的舊 oracle 讀 latest overlay，錯把 START input 看成 root.next 空；不是保存成功的證明。
- `.research-tmp/jd-ai-host-fh04-final-tests.txt`：改以 observer 的固定 root 後，**1 PASS／3 deselected，10.99 秒**。
- `.research-tmp/jd-ai-host-final-tests.txt`：最終 **4 PASS，52.89 秒**。這是主代理實際執行結果，本審查者只讀核對。

證據的成立條件：

1. 宿主確實由新 `Popen` 啟動 `open_manual_host`，取得真 HostLease、原生 PostgreSQL Saver 與 JdStorage；不是測試提供 stopped Future 或 fake PreviousHost。父端 fixture 驗固定 loopback `55436`、`caliburn_jd_relational_test`、`jd_test`、PG `180006` 及 Alembic 版；獨立 `jd_ai_host_test` schema 的四張原生 Saver 表／migration 先核對。測試 worker 把 `PostgresSaver.setup` 改為直接失敗，普通開啟不初始化。
2. 原模型流程使用既有同步 SDK `MockTransport`，`trust_env=False`；async client 建立器直接拒絕，key 是明示 synthetic 值，trace 關閉。恢復流程建同布局 InspectionOnly，另在 model/tool/execute 邊界加計數拒絕器；沒有 provider 連線或重播工具的 fallback。
3. FH02 的 SQL 未提交不只依 fault marker：同一實際 transaction 查得 2 revisions／1 operation，另一連線只看見 1 revision／0 operations；舊宿主仍存活時 contender 在 DB 建立器前被拒。`CRASH` 是該自有 worker 的實際 `os._exit(73)`；新宿主只追加原 operation 的 confirmed save_failed receipt，正文版本及內容保持原樣。
4. FH03 在原 dialect commit 成功後丟失回覆，並刻意停用本機 coordinator closure。manifest 由其他連線讀到 2 筆 committed 原 receipts／3 revisions；新宿主後完整 receipts、正文 snapshot、revision ID／number／count 都相同，ToolMessages 對應原 call／operation／digest。不是只採信 `real_commit_ack_lost` 字樣。
5. FH04 的 after_model 存在一筆持久 binding 且 execute 次數為零、JD 尚無 operation；另一文件直接用 Saver.get_tuple 取得 START 原 payload。修正後 root metadata/source、固定 checkpoint ID、保留的先前 messages 與新原話均和這筆 native payload 比對。恢復只補前者失敗 receipt，後者不新增 JD operation，兩份正文不變。
6. 成功路徑明確 STOP、等待 exit code 0 與 `closed=True`；故障路徑確認自己的 exit code 73。finally 只控制該次 Popen，以及已核對 PID／parent PID 的自有 native worker handle；沒有按 port 枚舉或终止其他服務。逾時清理不充當業務完成證明。

限制：FH02 沒有製造「舊主程序已死但另有工作子程序仍活著」的 live child-group 反例，因此不把本四案例宣稱為該 OS 邊界的新增驗證。這四案證明既有原生宿主與真 PG 的組合／恢復；不證明真模型訪談品質、正式產品切換、真人使用或任意舊 run 查回。
