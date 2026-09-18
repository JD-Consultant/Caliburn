# Task5 fix1b：保留既有測試及最新交接

2026-09-11。**未完成獨立複核；不可標記 Task5 接受、不可進正式產品切換。**

fix1 原待審來源及 54 項 API／63 項 Memory 回歸維持有效。[原 fix1](../fix1/report.md)的所有初敗與有限效力保留。後續根據 Git 差異核對，發現 root 新增 recovery 畫面測試時誤覆蓋了原有 `JdWorkspace.test.tsx` 的兩項測試；這是測試安全網回歸，不是原兩測試失敗。

已將原檔從 accepted HEAD `8eec072d51e97735b22c5f0df598b67101fe570b` **byte-exact 恢復**，新 recovery 測試獨立為 `JdRecoveryWorkspace.test.tsx`。沒有修改 runtime、契約或既有測試判準。最新 Web **8 files／37 PASS，9.99s**；[完整輸出](web-restored.log)。先前 35 PASS 僅代表當時少兩項的集合，不能宣稱涵蓋原兩項。

最新[凍結來源](source-manifest.json)為 10 檔，對最初 Task5 review snapshot 的[完整修正差異](review.diff)77528 bytes；其餘原31中的23檔hash仍相同。舊 fix1 freeze 不覆寫，複核應用本份 fix1b；原 `JdWorkspace.test.tsx` 不在修正清單，核 HEAD 相同即可。

獨立 reviewer 因執行額度限制而中斷，沒有產出 fix1／fix1b closure verdict。Task6 前置 agent 同樣中斷，未改任何 Task6 code。未贖回額度、未購買點數，未呼叫產品模型。root 的本地核對及綠燈不冒稱獨立審查。

下一個具體動作：reviewer 對此凍結包關閉 R01–06；若無 Important finding，才依計畫建立精確 Task5 commit／tag，再啟動 Task6。Task6 的[最新官方前置](../../../2026-09-11-jd-skill-current-official-preflight.md)已完成，沒有新增產品方向或額外權限。

原 NL08／NL10／NL11、headed browser 未驗最後版本、OS 真人 IME 及自然模型／真人品質效力限制不變；原 Starlette／AnyIO 警告不隱藏。當前修改仍在隔離 checkout，正式產品未切換。
