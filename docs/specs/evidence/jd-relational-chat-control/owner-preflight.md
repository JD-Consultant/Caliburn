# 聊天控制：同 owner 原子准入與唯讀排空

查閱日期：2026-09-13；程式基準 `36cc1cb9`，開始時隔離 app 路徑乾淨。本稿沿[聊天契約前置](../jd-relational-ai-restart/chat-contract-preflight.md)及[原生 owner 前置](../jd-relational-ai-runtime/ownership-preflight.md)，不重開品牌／資料表／模型比較。主代理採下述方案 A 後，已在 `manual_runtime.py` 與新 `test_foreground_admission.py` 完成有界實作；最後測試見 §5，尚待主代理 coordinator 接合及獨立審查。0 DB／provider，沒有執行正式模型或安裝套件。

## 1. 現況與必要效果

[ManualRuntime](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py) 的 `inspect_foreground_start` 用 `start_token` 追蹤同步查回及 close，但它沿寫入准入檢查，因此 live AI 時不能拿來公開查歷史。`AiRuntime` 目前先呼叫該查回，再另呼叫 `start_foreground`；若在 HTTP 或兩個 owner 呼叫之間讀 head，檢查與保留執行權之間存在空窗。新 API 不得沿此兩步方式核 expected revision。

必須保留四件事：

1. 新 run 的 canonical expected revision、同文件人工／metadata／AI gate 與真 ForegroundFuture 掛接，在同一 slot 保護內完成。模型執行不跨持 SQL transaction。
2. 同 run 原請求先查回；同意圖不受新 head／較晚 AI／封存影響。改原話或 canonical expected revision 是同 key 異意圖，須拒絕；換同版 ref 外殼不構成新意圖。
3. GET 只能觀察；live AI 或尚未收尾的 writer 不應阻擋已保存 run／history／read。查詢不能呼叫 start、recover、Future.cancel 或取得 writer permit。
4. 所有正在使用 Saver／engine 的同步查詢仍由同一 owner 追蹤；HTTP 等待取消／逾時不能先清掉真正執行中的讀取。close 期限包含這些讀取，沒排空便保留資源。

run locator、request format successor 及 digest 由 coordinator／checkpoint 責任處理。新版 digest 含 dataset／document／原 text／canonical expected revision；owner 直接使用已核 `ForegroundIdentity.request_digest`，不重算原話、不另存 request。對未知、scope／digest 不符或只掃到部分 history 的查回，callback 必須阻擋，不能把它轉成「不存在」以啟新 run。

## 2. 兩個有限選擇及採用方案

| 選擇 | 接口與取捨 |
|---|---|
| **A：單次准入，推薦／已採** | `admit_foreground(identity, work, *, expected_revision: UUID, lookup_original: Callable[[], object | None]) -> ForegroundAdmission`；結果明分 `handle` 或 `original`，恰有一個非空。owner 在一段 doc slot 內完成查原請求、新准入前置與真 Future 掛接。原 `start_foreground` 暫留低層既有測試；新的 AiRuntime／HTTP 路徑全部改走新接口。 |
| B：具 scope 的 reservation context manager | caller 在同一原生 context 裡查原結果、核 head、再 attach。需要額外 token／context／abandon 語意，且容易讓 caller 漏 attach 或跨 I/O 保存 capability。本次沒有需要外露這些階段的情境，因此不採。 |

兩者都需要獨立的 `inspect_document(document_id, read)` 唯讀 port，這不是第二個 owner 或新工作佇列。

### A 的具體順序

1. 驗 canonical document／run／digest、UUID 型別 expected revision、callable，取得既有 `_Slot`；檢 accepting、真 host、startup ready。
2. 以 `start_token` 標記本次同步準備，包含 reentrant close 可見的 I/O 範圍。同 run 的本地 handle 也不能跳過 coordinator 的原格式／原話核對。
3. 在同一 slot 先呼叫 `lookup_original`；舊版需查回、來源不可讀、scope／digest 不符或需續頁均由 callback 具名錯誤阻擋。callback 正常返回後，才核 slot 同 run 的完整 identity；異意圖衝突。非空回 coordinator 原結果；None 且 slot 仍有同意圖 handle 時只回原 handle，其餘 None 僅允許表示完整查明不存在。此時尚未做新 head／busy／封存判定。
4. 只有新 run 才核原 manual entry、catalog、foreground、native pending。利用現有 `storage.read_current` 取得已驗文件／head，拒不存在、封存或 expected revision 不符。現有 reader 已在短 READ ONLY REPEATABLE READ 交易驗 current；不需第二個 head authority 或跨模型 SQL 鎖。
5. I/O 後重核 open／host，建立原 `_Foreground`、submit 同一原生 executor 並掛真 Future／callback。worker 仍在取得同 slot、確認本身 token 後才開始。只有掛接完成／失敗處理完整後才清 start token、離開 slot；沒有「讀 B→放鎖→另一 writer 改 C→以 B 啟動」空窗。

owner 處理的固定前置碼為 `stale_view`、`document_archived`、`document_missing`、`document_busy`、`startup_pending`、`host_not_valid`、`runtime_closed`；head 讀取未知故障固定為 `read_failed`，native pending 檢查故障仍為 `checkpoint_unavailable`。callback 的原結果 scope／意圖／續頁錯誤沿既有安全 App 型別傳遞，owner 不解包或重新解釋原結果。新准入前置拒絕不產生假 Human 保存、假 run terminal 或 JD revision。

`expected_revision` 是 App 解既有 ref 後的 canonical identity；不可先拿當前 head 驗 ref 再決定是否查原 run。原 request 的合法舊 ref／原 UUID 仍須先配回原意圖，新 run 才比 head；dataset／簽章／locator 種類的合法性檢查不因此放寬。整個版本 precondition 是本機已定同 owner 的准入保證；不宣稱可防未經宿主的任意外部 SQL，真正每次 JD 寫入仍沿原 storage CAS。

## 3. 唯讀追蹤、status 與關閉

`inspect_document(document_id, read)` 檢 canonical doc、open、真 host、startup ready，不查 manual／catalog／foreground write gate。實際 document 存在性與查詢 scope 由既有 reader／locator 在 callback 內驗證；封存文件可以讀。callback 只返回有界、已物化的查詢結果，不能把 lazy iterator、stream 或 Future 當作已結束讀取傳出。

在既有 doc slot 的短鎖內，登記本次 token、執行 thread ID 與未完成 Event；隨即放鎖執行同步 I/O，`finally` 在原 slot 清除 token 並完成 Event。registry 仍只管理 slots／accepting，不包任何 I/O。讀取不取得 writer capability，也不妨礙其他文件查詢／寫入；同文件 live AI 的工具可以繼續使用原 gate。

`close` 先關 accepting，再取既有 slots；已登記的 read Event 納入同一 deadline，真正 callback 結束才完成。相同 thread 在自己的 callback 內 reentrant close 應直接回未關閉，不能把 RLock 可重入誤當已排空。未知／BaseException 也走 finally 清本次讀取，不把原事件借下一次工作。close 開始後拒新讀取；原已准入讀取可以完成，不能因 waiter 取消就釋放 Saver。

`status` 的 live writer／startup recovery 記憶體觀察繼續作診斷；未 ready／closed 且沒有實際 entry 時，回 blocked，不再啟 Saver I/O。正常 idle status 的 Saver 查詢須接同一 read tracking。產品 GET 聚合 run、history、JD operations／write state 時，用一次 `inspect_document` 包住整個物化讀取，不從狀態字串推定可寫，也不要求 GET 先拿寫入 gate。

## 4. 原生依據與有限驗證

沿 2026-09-13 已核[Python 3.12 futures](https://docs.python.org/3.12/library/concurrent.futures.html)與[原生 owner 證據](../jd-relational-ai-runtime/ownership-preflight.md)：實際 callable 的 Future 與完成 callback 有各自時點；timeout 不停止工作；相同 executor 的相依等待可能死鎖。原生 Lock／RLock／Event 是本案既有 stdlib 接點，Python 3.12.13、穩定、PSF 授權；LangGraph 1.2.11／checkpoint 4.2.0 的原生持久讀取沿 MIT pin。沒有新套件或升級。這些官方能力不會自動完成本案准入；slot 保留與 read token 排空是明確的 App 接合。

先建立有意義反例，再施工：

- 同 run 原結果優先於 stale／另一 live run／封存；同 ID 異 digest 拒絕，查回需續頁不可開新 Future。
- expected B 的 head 在准入前已 C：零 work／checkpoint；從 head 讀取到掛 Future 間安排同文件 manual／metadata 競爭，不能插入成功。
- 同一準備 I/O 內 reentrant close，及另一 thread close：不得提早排空或在 close 後派發新模型；失敗清本次 token。
- live AI／manual gate 下查詢正常返回；讀取 I/O 期間其他文件仍進行，同文件工具不被唯讀 callback 長持 slot 阻擋。
- 查詢逾時／例外／BaseException、close 等待、晚來 GET、startup 未 ready／host 失效／錯 doc UUID：有固定拒絕及正確 drain，無 writer permit。
- 既有 foreground／manual／catalog／startup 測試只在受影響處回歸。新測試用真 thread／Future／Event 與合成持久 ports；不等同真 DB、HTTP、OS 或 provider 驗收。

## 5. 有界實作結果

新增 immutable `ForegroundAdmission(handle, original)`，恰一欄非空；兩個公開接點及上述 close 追蹤已落地。舊 `start_foreground` 與新准入共用既有 Future 發派的 private helper，不複製 executor／owner。`status` 在 start／catalog token 存在時直接回 blocked；startup 尚未 ready／已關閉且沒有實際 entry 時不啟 Saver I/O，既有恢復中記憶體診斷仍保留。

新 [test_foreground_admission.py](../../../../experiments/jd-relational-app/tests/test_foreground_admission.py) 首輪 **29 FAIL＋1 teardown ERROR**：兩個接口尚不存在；其中 catalog 合成 token 因失敗後未清理導致 teardown error，測試已補 finally。完成接口後新 29 PASS。另加 4 個必要邊界時 **1 FAIL／3 PASS**：start preparation 的 status 仍讀 Saver；已以本地 token 直接表示 busy。主代理指出 cached handle 不可搶在 coordinator 格式核對前返回，補 **2 FAIL** 證明 callback 被略過／舊版 lookup-required 誤成 owner conflict；已調整為 callback 先行。

最後實跑：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_foreground_admission.py tests/test_foreground_runtime.py tests/test_foreground_restart.py tests/test_startup_recovery.py tests/test_manual_runtime.py tests/test_catalog_runtime.py -q -p no:cacheprovider
```

**147 PASS，0.93 秒＝新 34＋既有 owner 113。** 這是單次完整受影響 owner 組，不與先前 29／142 或主代理其他測試累加。測試使用實際 ThreadPoolExecutor／Future／Event；持久、head、host 都為合成 ports。未執行 DB／新程序／provider，未把 callback 內的合成查回當原生 history locator 或完整 HTTP 驗收。coordinator／run descriptor／真 Saver／HTTP 接合由主代理完成，不能因本段通過宣稱聊天 App 已完成。
