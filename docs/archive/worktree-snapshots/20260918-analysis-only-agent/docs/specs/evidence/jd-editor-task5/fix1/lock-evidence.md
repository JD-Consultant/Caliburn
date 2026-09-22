# Task5 lock 契約有限核對

2026-09-10；Topic `JD-R002/C03`，隔離 G7 fix1 前證據補充。只核既有 review 的鎖範圍與責任；不審未凍結 fix source，不改 code／ADR／register，不重選架構。

**結論：官方資料不支持「Python 全域 mutex 本身非主流，所以必須移除」。**它們支持共享狀態需要同步，並明確定義持鎖等待的效果。本案已有反例支持的是：**A 文件等待 PG 對帳時持有服務共用 lock，導致無關 B 文件無法取得 admission**。應修持鎖範圍／文件 owner 接線；沒有證據要求刪除所有短 shared-state lock，亦無效能倍數結論。

## 官方事實

| 來源 | 可確認的契約 |
|---|---|
| [Python 3.12 Lock／RLock](https://docs.python.org/3.12/library/threading.html#lock-objects) | 同一 lock 被占用時其他 thread 會等待；RLock 容许擁有 thread 重入，但须最外層 release 才放行別人。RLock 不會因目前正在等待 I/O 就自動解鎖。 |
| [Python Condition／wait_for](https://docs.python.org/3.12/library/threading.html#condition-objects) | 官方示範用 lock 同步 shared state；`wait()` 等待時釋放 associated lock，返回前重新取得。`notify()` 本身不釋鎖；`wait_for` 於持鎖下檢查 predicate，返回需核結果。 |
| [PostgreSQL 16 row locks](https://www.postgresql.org/docs/16/explicit-locking.html#LOCKING-ROWS) | row lock 阻擋同 row 的衝突 writer／locker；FOR UPDATE 可能等另一交易結束。row lock 通常於 transaction end 釋放，普通 SELECT 不被此 row lock 阻擋。 |
| [PostgreSQL 16 advisory locks](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS) | 意義由應用程式定義，PG 不強制其他 code 遵循。session lock 需明示釋放或等 session 結束，rollback 不會自動解除；transaction lock 於交易結束自動釋放。 |
| [PostgreSQL 16 Read Committed](https://www.postgresql.org/docs/16/transaction-iso.html#XACT-READ-COMMITTED) | 每個普通 SELECT 使用該 statement 開始時的 snapshot；同一交易內兩個 statement 可看到期間提交的不同資料。 |

查閱的是 Python 3.12 線官方線上文件（頁首目前顯示 3.12.14）；已測本機 runtime 是 3.12.13。此次沒有將線上文件 patch 版本當成本機已升級，也沒有重新測 runtime。

## 本案 mapping／推論，不是官方指定架構

- **短 shared-state mutex：**可用於同一 process 的 owner map、admission 狀態及 drain 計數的一致存取。官方同步 primitive 支持這個用途；「短」是本案避免無關文件相互等待的責任安排，沒有官方毫秒標準。Condition.wait_for 的等待會釋鎖，不能因它寫在 `with condition` 內便判成整段持鎖等待。
- **持共用 mutex 等 PG／Node：**Python 的服務 lock 仍被 A 持有，PG 只知道資料庫鎖，不會替 Python 釋鎖。B 即使鎖不同 document row，也可能在發 SQL 前就被 Python 層擋住。這是已審 source 的具體跨文件序列化；非泛稱所有 mutex 錯誤。
- **PG 鎖與 App owner 不互相替代：**既有 JD head row lock 保護保存／對帳 transaction；create 的 request-key transaction advisory lock 保護對應建立意圖。它們不會自行追蹤 Python Future、Popen／pipe、checkpoint closure 或恢復中的 entry。直接用一把 DB advisory lock 取代全部 App 同步，並未從這些官方契約得到證明。
- **receipt 查詢順序不變：**本案鎖 head 後用下一 statement 查 receipt，還必須具備原 writer 已停止、無後續 mutation 的既有 proof。Read Committed 本身不讓一般 receipt absence 變成 known-none。

## 對 R01–R06 的界線

原審查：[task-5-review.md](../.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-5-review.md)。以下只說缺陷類別，不預判 fix1 已閉合。

- **R04** 是本次需調整同步範圍的主要問題：凍結 `service.py:334–338,422–426,734–738` 在共用 lock 下等 PG；pure fixture 已證 SQL 接點等待時，B 取不到共用 lock。修正可沿既有每文件 reservation／generation，無需提出新產品架構。
- **R01、R06** 是與同步相關的接線正確性：最終 admission 要核封存，recovery 要列入停止與 drain。只移出全域 lock 不會自動修好這兩個問題。
- **R02、R03、R05** 是結果／恢復接線：原 terminal 可見性、無 run 阻塞診斷與 receipt-first。它們不構成重選 mutex／DB 策略的依據，但仍是已採契約中的待修缺陷，不能因稱為接線便略過。

**效力／下一 gate：**有限證據補充完成；未取得業界採用率資料，不能宣稱何種設計「不主流」，未做效能 benchmark，不能宣稱10–100倍。本次只新增本 scratch，0模型／0DB／0程序控制。等待 root fix1 精確凍結後，沿原 finding 做窄複核。
