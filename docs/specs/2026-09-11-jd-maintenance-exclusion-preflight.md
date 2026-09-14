# P5-O02：維護期間與日常啟動的互斥接點

查閱日：2026-09-11。**有限官方核對及候選，未採用／未施工／未實測。** 主線仍是已接受 Task5 後的 Task6；不重開 Task5，不改 production ADR0060、Proposed0073／0074 或 G6。沒有模型、帳戶、DB、程序或設定操作。

## 現有問題與固定來源

原 [P5 前置](2026-09-10-jd-operations-preflight.md) O02 要求：停止 API 後，備份／還原／更新期間不能被日常入口重新接單。只看到舊程序停止，無法保證之後沒有新程序。

唯讀接受版 `444416722190fd48c14f4423d101f36b25831de1` 的 `experiments/analysis-agent/src/analysis_agent/windows_lifecycle.py`：API 主執行緒取得安裝範圍的 `.ApiMutex` 並保留至程序退出；bootstrap 取得 mutex 後才核對／停止同名舊 Job、建立新 Job、接觸 App 資源。現有 mutex 不只是 Python 文件鎖，也不是 PostgreSQL 資料權威。

## 官方事實與適用範圍

| 來源 | 官方事實 | 本案界線 |
|---|---|---|
| [Microsoft Using Mutex Objects](https://learn.microsoft.com/en-us/windows/win32/sync/using-mutex-objects)（頁面更新 2026-07-17） | Mutex 可同步跨程序的資源使用；取得、使用、釋放有明確順序。官方建議有界等待及錯誤診斷；abandoned 需檢查被保護狀態。 | 支持使用 OS 原生同步，不表示產品應用一把 mutex 包住每份文件的慢速操作。 |
| [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)（現行 Win32 契約，頁面更新 2024-08-22） | WAIT_ABANDONED 同時授予 mutex ownership；它不表示先前持有者完成工作。WAIT_TIMEOUT 與 WAIT_FAILED 不授予成功。等待中關閉 handle 的行為未定義。 | 不能把非正常退出等同「備份成功」或「資料操作已終局」；錯誤／清理仍須持有正確 handle。 |
| [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)（頁面更新 2025-07-14） | Job 管理程序群組；預設子程序會加入，依旗標有例外。最後 handle 關閉與 KILL_ON_JOB_CLOSE 有特定終止語意。 | 不證明 SQL、checkpoint、receipt 已完成；維護程式不能直接呼叫目前會把自身加入 API Job 的 bootstrap 來假造同一角色。 |
| [PostgreSQL 16 pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)（現行受支援 16 文件） | 單 DB dump 可取得一致備份，同時不阻擋其他讀寫；應檢查診斷與結果。 | Dump 一致性不代替 App 排除重新接單，也不表示未完成 operation 已成功。 |

以上使用既有 Windows OS API 及 PostgreSQL 16 官方工具，未新增套件／商業擴充。Win32 API 文件不是可重散布程式碼的授權聲明；本輪沒有複製官方範例。既有 pywin32312 各部分授權沿 Task5 inventory，PG 沿 PostgreSQL License；正式交付仍核實實際 binary 版本。

## 本案候選：沿同一安裝 mutex 取得完整維護區間

這是本案映射，不稱 Microsoft／OpenAI／Anthropic 的完整產品方案；後两家並非 Windows 本地維護同步契約來源。

1. 維護入口先要求**已確認身分的本 App**受控停止；尚未取得安裝 mutex 前，不開始 dump、restore 或更新。
2. 舊 API 退出後，維護程式在同一主執行緒、有界等待取得**同一**安裝 `.ApiMutex`。若另一日常啟動先取得 mutex，維護返回忙碌且不執行維護內容；不搶殺新程序或無限重試。因此停止到取得鎖之間即使有競爭，也不能造成兩方同時工作。
3. 取得後，沿既有規則核對舊 Job／必要停止證據，再進入只為維護提供的有限資源接點。維護程式不加入 API Job，不啟動顧問／背景模型，也不使用會自動 setup 或排程的完整日常 factory。
4. **整段維護持有 mutex**，包含啟動官方工具、等待工具退出、結果與內容核對；確認 cleanup 結束後由原持有執行緒釋放。新 API 的現有 bootstrap 在取得同一 mutex 前即被擋住。
5. 原 DB 的未知結果仍依 receipt／checkpoint 表示；備份可以保存未閉合狀態，但不得把它改稱完成。恢復來源及格式核對依 P5-O05–07；不因取得 mutex 就擅自重播 AI、清空 pending 或改 operation authority。

此候選不需先增設第二把全域文件鎖、常駐 supervisor 或維護資料庫。**維護互斥只適用同安裝入口，不排除有權限的外部 SQL 客戶端**；目前單機單操作者範圍內，PG 自身的 transaction/snapshot 仍是資料一致性依據。

## 有限驗證與停止條件

| 情境 | 必須觀察的結果 |
|---|---|
| 維護取得 mutex 後啟動新 API | API 尚未接觸 DB／native／client 即回忙碌；維護完成清理後才可正常啟動。 |
| API 在停止後的競爭空檔先取得 mutex | 維護有界退出、工具呼叫數為 0；不得誤報維護開始或成功。 |
| 維護等待時失敗／超时 | 不釋放別人持有的 mutex，不開始任何維護寫入；診斷清楚。 |
| 維護程序突然退出 | 不宣稱成功。必須分別驗 dump、restore、update 子程序及部分產物；不能僅靠 abandoned 狀態解鎖便稱安全。 |
| Dump 完成、但結果／內容核對失敗 | 舊有效備份及原 DB 保留，新產物不列為已驗備份；不自動開始更新。 |

**尚未閉合：**真正受控 stop 接點、維護子程序停止歸屬、restore 明確目標、update 部分資產與啟動版本核對。它們已屬原 O01／O05–07 與正式採用工作，不以本文候選宣稱解決。尤其 maintenance crash 後，子程序仍可能存活；未有產品實證前，不能把 mutex 可取得当完整恢復證據。

下一步在正式接手設計中核對此候選及上述失敗路徑；若需要新的持久 owner 或改既有停止契約，再做有限設計審查。停止廣搜相同 mutex 原理；不現在修改已接受 Task5 或正在施工的 Task6。
