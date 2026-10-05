# 2026-10-04：續跑前檢查

本次只更動研究接線，正式產品 Python、員工來源、判準與原 protocol 雜湊均與 main-02 相同。新增的 `continuation.py` 以既有主執行腳本為底，差異限於 64 步、前綴副本、續跑起點及累計護欄；原 main.py／main-02 不追改。

## 付費前的證據

- 15 項續跑及原研究護欄測試通過，Ruff 通過。測試先出現缺少模組的收集失敗，再實作；本次不宣稱六項都有行為性 Red。
- 兩次本機測試被 Windows 沙箱暫存權限阻擋，改用已安裝的專案 Python 及隔離暫存目錄，沒有為環境問題外送模型。
- 副本已建立後，首個檢查在連線字串格式處停止，尚未更動副本業務資料；改用 SQLAlchemy URL 正規編碼，明示沿用該副本，不重新建立或覆寫資料庫。
- 真 PostgreSQL：51 段／103 則正式訊息；透過既有產品交易將失敗 e052 終止並丟棄候選。停止前後正式產品匯出逐位元組相同，亦與 main-02 的 product-051 相同；已採用 ContextPosition 不變，當前執行已解除。模型外送零次。
- 原資料庫、trace、manifest、失敗候選與原 checkpoint 完整保留。新研究 DB `caliburn_compaction_main03`，仍位於隔離容器 55441；不接正式 DB。
- 前綴有 51 exchange、51 product、三批 Memory，逐項事件與雜湊核對；第 52 段不存在正式成功原件。
- 累計已占用 US$0.583808190（含 main-01 預留），剩 US$1.416191810；generation／compact／outbound／input 沿用 main-02 計數，新四小時由本次執行起算。

## 驗證命令

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/test_continuation_support.py docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/test_main_support.py -q -p no:cacheprovider --basetemp .research-tmp/pytest-continuation-20261004-03
apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/continuation_database.py --clone-already-created
```

前置資料與保存的安全 Context 原件見 `continuation-preflight.json`。以上是續跑準備證據，不是四組品質比較已完成。
