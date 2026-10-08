# 無 key 的原生 crash 診斷

正式首批原程序於第 6 Turn 中途 native crash。Windows Application 1000／1001 記錄 python314.dll access violation（0xc0000005）；主程序沒有正常 finally 結案。36 admitted attempts 中有 35 個唯一 received usage，最後一個 A attempt 用量未知，原 reserve US$0.013296750 保留；spent US$0.022429100、occupied US$0.035725850。前 5 Turn completed、第 6 Turn active，Memory 1 completed。無 key 真產品 HTTP 已保存中斷後正式 JD、員工原話、固定來源及狀態；沒有完整匿名 pair，也不宣稱比較完成。

有限重播使用相同 `replay.py`（SHA256 `5e5cee97b15768a9c69ae38f89271a68df90ca15dc7dd494fd95bae55f1f3366`），只從原 trace 取公開 request／terminal output／usage，經本地 MockTransport 和真 SDK；另只讀原 checkpoint，不寫業務資料。沒有 credential reader、provider 呼叫、locals／headers／opaque 輸出或 memory dump。faulthandler 只存堆疊。重播無法復原 opaque reasoning 與原始 wire chunk／時序，不能冒稱完整 provider replay。

| 隔離檢查 | Runtime image | 實際结果 |
| --- | --- | --- |
| serde＋saver | uv standalone CPython 3.14.7 / 原 package bytes | 2,000 roundtrip＋2,000 readonly checkpoint，15.71s，exit 0 |
| SDK stream | 同上 | 1,793 terminal envelope／60.02s，exit 0 |
| combined 第一次 | 同上 | 約 8s、81–90 迭代內 native access violation |
| combined 第二次 | 同上 | 約 7s、同區間 native access violation |
| combined image 對照 | 本機 official CPython 3.14.0 / 同 package bytes，-I/-B | 約 9s、81–90 迭代內 native access violation |
| combined 無 observer 1／2 | 原 uv CPython 3.14.7 / 同 package bytes | 各 2,000 SDK＋2,000 readonly checkpoint，76.21／75.26s，均 exit 0 |
| combined OwnedObservedStream 1／2 | 同上，僅新實驗 observer ownership | 各 2,000 SDK＋2,000 readonly checkpoint，75.57／75.05s，均 exit 0 |

3.14.7 的 GIL enabled／Py_GIL_DISABLED=0，JIT available=False／enabled=False，Py_DEBUG=0。不能以 free-threaded 或 JIT 問題解釋。official 3.14.0 對照也失敗，排除「只此 uv 3.14.7 image」的窄假設；image、patch 及啟動 isolation 仍是對照差異，尚未判特定 library 根因。

第二次 combined faulthandler 顯示 worker 的 `_load_writes → jsonplus.loads_typed → _asyncgen_finalizer_hook → call_soon_threadsafe → _write_to_self`，主 thread 為 Garbage-collecting／no Python frame。伴隨 BoundAsyncStream／Response.aiter_raw 已執行中關閉警告。兩個單獨路徑通過而組合重現，將故障邊界收斂至 off-thread checkpoint 解碼、GC 與串流生命週期的交互；不把警告直接判為原因，先導也曾有警告且結案成功。

本機 OpenAI 3.20.0 `AsyncStream.close()/aclose()` 只關閉 HTTP response；原產品在 terminal event 後停止讀取並呼叫 close。移除實驗 ObservedStream 後兩次 combined 均通過，將本次失敗觸發收斂至實驗 observer 串流生命週期，沒有證據要求修改 production 或更換 runtime。新 `append_stream.py` 用持有 iterator 的 AsyncByteStream，沒有自己的 yield async generator；早停時顯式關閉所持 iterator，再關 original stream，未知或終態觀測恰一次。原 SDK chunks 逐 byte 傳回，不排空 EOF、不改模型或 source。Python 官方說明指出 async generator 提前退出需要明確清理，亦提醒不可並行迭代／關閉；本次因果證據以單變量重播為準，不將官方一般說明當成 vendor 本案修復保證：[官方 asyncio 開發說明](https://github.com/python/cpython/blob/main/Doc/library/asyncio-dev.rst)。

原 frozen production／harness、正式 manifest／snapshot 與原 DB 均保留。新 observer 3 個早停／未知／close failure 反例與 carry 建構延遲反例實際 4 failed／4 passed Red；窄修後 Green。增加 split chunks／同 chunk 多事件 bytes、CancelError before terminal、terminal double close 及真 append wiring，12 tests 通過。Carry 第一行取 monotonic anchor，建構延遲不增加原剩餘時限；此反例由獨立 storage review 重跑閉合。所有費用／未知 reserve／36 gen／77 outbound／765,475 counted input 保留，原 deadline 不重設，原 cap 計入消耗，帳務不一致即拒絕。

正式 append 使用同 CPython3.14.7、同 packages／production／model／guides／工具／oracle／披露政策，只在新批次接 OwnedObservedStream 與 carry accounting。兩次 complete combined Green、相關真 PG 只讀＋SDK probe、12 行為檢查及独立 carry review 是付費放行條件；新 manifest 逐 byte 封存新增 observer／entry source，記明有限實驗差異與旧未完成批次。原總界線仍 US$8／4h／1500 gen／3500 outbound／16 compact／40M input，固定 deadline `2026-10-07T01:30:34Z`，未知 reserve 不釋放。盲評不把中斷首場當完整 pair，未覆寫既有材料；vendor 原生 bug 的底層原因仍未證明。

放行檢查完成後，`formal-append` 於 `2026-10-06T22:02:47Z` 封存並啟動。新 manifest SHA256 為 `b59e51e1b090955e7b2ff4b1cadec336471611761c8add73b748e0550cff17d6`；470 份 source snapshot 逐位元組核對全部吻合。入口亦核對原 production／guide／schema／dependency 子集合與中斷批次的帳務原件。新批次結果另存，不回寫先導或中斷批次；啟動本身不代表八場訪談或品質比較已完成。
