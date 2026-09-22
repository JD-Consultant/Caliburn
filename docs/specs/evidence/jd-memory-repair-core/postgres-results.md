# Memory C：真 PostgreSQL 修補與原回執查回

日期：2026-09-13；基準 `7d3f474a` 上本輪核心變更。測試檔為 `experiments/jd-relational-app/tests/test_memory_repair_postgres.py`，只有一個完整情境，不新增產品碼或測試用資料表。

**最後結果：1 PASS／8.01s，0 provider。** 使用真 PostgreSQL 18.6、PostgresSaver、PostgresStore、SQLAlchemy publication 及原生 StateBackend／SDK patch。合成對話由原生節點提供，沒有模型 SDK 呼叫；不等於自然模型或 App 完整 C 工具流程。

## 實際過程與證據

1. 以既有 ManualRuntime 在專用測試 DB 建立一份新的合成 JD（head 1），以既有 source fixture 保存兩輪原話及回覆。Memory 初始版為 revision 1，原始工作詳記及原話都可回查。
2. 兩份原生 patch 將 knowledge 與 guide 的核准者由「主管」更正為「處長」，保留其他工作與詳記連結。原生子圖在 `prepare` 之後、第一次 `publish` 之前停止；從明確 checkpoint ID 讀回同一 typed `PublishRequest`，其中 operation、base revision 1、準備版本、artifact digest、kind 與更正來源固定。
3. 此時尚無回執，`reconcile(request)` 明確回 unknown，沒有呼叫 publish。為注入下一個故障，測試才明示讓該原生節點第一次執行 publish：真 SQL 交易提交後由測試拋出「回覆遺失」，保留原 native pending 工作。累計只有 **2 次 patch、1 次 Store save、1 次原 request publish**，沒有重做前兩步。
4. 保存的回執為 repair、base 1／result 2、同 request digest 及同更正 source；C 之後的 `processed_source` 仍為原 B 游標。從 Saver 重新取得相同原 request，僅以 `reconcile(request)` 查回 applied；這時禁止 patch、Memory save、Store.put、publication.publish 及來源正文 read，仍成功回報原結果。
5. 測試明示發布一份後續 B fixture 至 revision 3，加入其他有效工作，B 游標推進至更正來源。關閉原 Store／Saver／SQL 連線後，用新連線、serializer、graph 及 source owner 再讀相同準備 request；再次禁止以上副作用，查回 **`applied_head=2`、`head=3`** 與當前 guide。沒有把晚版倒退，沒有接受呼叫者提供 edits／changes 作已保存證據。
6. 前後均核對 JD 完整 `CurrentDocument` 未變、最新原話根觀測仍等於原先已閉合觀測、兩份固定來源原文（含 CRLF 與空白）不變。新連線沒有呼叫合成對話節點，該文件共有3筆 publication 回執。

修補專用父子圖使用獨立合成 `repair_thread`，避免把本測試圖寫到原話根執行緒；這是測試組合，不是新產品 broker／run 表。故障後仍保留 pending repair checkpoint，測試透過原 request 查回並未冒稱 App 已完成該 child 的正式收尾；App 工具接線與停止後閉合另驗。

## 首敗、修正與保留資料

- 首跑 **1 FAIL／15.65s**：已走到真 SQL commit／ACK lost；測試先對尚未固定的 `child.latest.next` 斷言 `publish`，但 LangGraph pending overlay 顯示空 next。產品没有因此重寫。
- 只修測試：先依 `child.config` 讀明確保存位置，再核 fixed next 及原 request。修後 **1 PASS／12.95s**。
- 追加兩条完整性斷言，要求最新原話觀測仍與原閉合觀測一致；最後 **1 PASS／8.01s**。同一情境重跑，不相加成三個通過案例。
- 最後合成 document：`c6cb057b-c5e2-484f-af64-b902f53fd855`；repair thread：`aa575ca8-6158-4108-8f22-58c128b8151a`。結果為 Memory head 3、applied head 2、回執3、patch2、JD head1。
- 原始輸出保留 `.research-tmp/jd-memory-repair-pg-first.txt`、`jd-memory-repair-pg-final.txt`、`jd-memory-repair-pg-source-final.txt`。首敗及各次合成資料都保留，沒有清資料或 drop。

## 環境與可重跑入口

沿既有已明示初始化的 `127.0.0.1:55436/caliburn_jd_relational_test`／`jd_test`，fixture 先核 PostgreSQL `180006`、JD migration 與指定測試 schema 表集合。Memory 使用 `jd_memory_core_test`，Saver 使用 `jd_runtime_test`；只新增自己的合成 JD／Memory／訪談資料，不修改既有資料、schema 或 production 設定。

工作目錄 `experiments/jd-relational-app`：

```powershell
$env:PYTHONUTF8='1'
$env:JD_RELATIONAL_TEST_DB='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_memory_repair_postgres.py -q -s -p no:cacheprovider
```

本次「重開」是**同一 Python 程序中的全新連線與讀取物件**，沒有宣稱 Windows 新程序／foreign-host 死亡恢復、模型自然判斷修補、B1／B2 模型執行、前端或完整顧問品質已通過。
