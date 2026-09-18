# 有限文件審查：PASS

2026-09-11。**PASS 僅指候選文件與既有契約一致；不是採用、施工通過或 P5-O02 closure。** 沒有 Important finding，也不要求現在補完 P5 設計。

受審文件 `docs/specs/2026-09-11-jd-maintenance-exclusion-preflight.md` SHA256 已核為 `60dcbf6f4589ce682dd0a007ab3c6f12376cf7c2bc7e5115706e3d8eda06da24`。對照原 `docs/specs/2026-09-10-jd-operations-preflight.md:52` 的 O02，以及已接受 Task5 的 `experiments/analysis-agent/src/analysis_agent/windows_lifecycle.py`；後者現有 bytes 的 SHA256 `81484ec2f59a8bf7804e8910529bff6866fd820a0596c7b3eb5581f072f78d32` 與 Task5 原 source manifest 一致。

## 具體判定

- ✅ 候選 `:26–29` 的競爭處理一致：maintenance 與 API 必須取得同一 OS mutex ownership 才開始各自工作；停止後 API 若先取得，maintenance 返回忙碌、不啟動工具、不搶殺。API bootstrap `:74–81` 先取得 `.ApiMutex`，再於 `:84` 起處理舊 Job，因此持鎖期間排除新 API 的映射有實際來源。此判定只適用真正同一物件，即沿現有 `Local\\Caliburn.<key>.ApiMutex` 名称及所在命名空間；不推論為跨 Windows session 或外部 SQL 排他。
- ✅ 候選 `:28–29` 不直接重用會把自身加入 API Job 的 bootstrap，且由原持有執行緒保持 ownership 到工具退出及結果核對完成。這與現行 `windows_lifecycle.py:111` 的 API membership 責任有清楚區分，沒有偷偷新增 supervisor、第二 semantic owner 或維護資料庫。
- ✅ 候選 `:16,41,44` 明確限制 abandoned：取得 ownership 不證明前任完成，maintenance crash 後工具仍可能存活。官方契約也要求對被保護的持久狀態檢查一致性；這部分來源表述正確。[WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)
- ✅ 候選 `:17,30,32` 沒有把 Job 停止或 mutex ownership 當成 SQL／receipt terminal。Job 的群組生命期與單 DB 一致 dump 各有其責任；官方契約不賦予兩者 operation authority。[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[PostgreSQL 16 pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)
- ✅ 候選 `:15` 的有界等待、取得後才使用資源、清理釋放及 abandoned 診斷，都有直接官方依據；引用的三份 Microsoft 頁面更新日期吻合。沒有將官方程式範例當作已取得重散布授權。[Using Mutex Objects](https://learn.microsoft.com/en-us/windows/win32/sync/using-mutex-objects)

## 保留的邊界

- ⚠️ 原 O02 仍 OPEN：正常持有者存活時的 winner／busy 排他只是部分答案。維護持有者死亡後，現有 API bootstrap 不會僅因 mutex 曾被 abandoned 就知道還有 maintenance 子程序或部分更新資產；本文 `:41,44` 已如實保留此缺口。因此後续 durable routing 必須保留 O02 的完整生命週期驗收，不能因本文列出 O01／O05–07 就把 O02 關閉。
- ⚠️ `:38–42` 是未來必須觀察的結果，並非已存測試證據。尚無真正受控 stop、maintenance crash 子程序處置、restore target 或 update 部分資產／版本恢復的產品實證；本文未假稱通過，本審查不要求在本 workpackage 施工。
- ✅ 未讀 Task6 source／test，未執行測試、DB、模型、程序或 git 操作。僅核上述文件、已接受 lifecycle 原碼／既有 manifest 及四個具名官方連結；唯一寫入為本 review。

**Assessment：候選文件可作正式接手設計的有限輸入；無須補搜相同 mutex 原理。P5-O02 不因本次 PASS 而採用或閉合。**
