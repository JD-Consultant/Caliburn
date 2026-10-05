# 唯讀審查

日期：2026-10-04。審查者：既有研究 reviewer 子代理 `/root/review_occupation_experiment`，依 superpowers:requesting-code-review；唯讀文件與資料，不呼叫模型／GPU／DB，不修改舊封存或產品程式。這是工程／證據審查，不是受測顧問或獨立人工職務專家評分。

範圍：候選設計、計畫、協定、prepare／verify、生成前 manifest、來源、目錄及兩種導覽；README 完成後另核 README 與 current-decisions、specs、experiments 入口措辭。

獨立腳本核來源 bytes／hash、全體來源／任務群組／能力區塊及多 T 共用關係、全部查詢文字／來源／排名證據／命中邊、職位條目及可回讀目錄；核對結果與 verification-01 一致。另執行 verify.py 不帶輸出通過，未寫入舊資料包。五輪 132／69／86／96／78 份 sealed 原件逐 hash 未變。

審查結論：無 Critical／Important。原始來源只存一次；群組不按 T 名稱數複製能力區塊；文件命中明示 document／not_evaluated。工作假設沒有被寫成已證實的模型失敗；沒有宣稱新召回、任務適用、未知發現或 JD 完整度通過。零結果／缺代碼未驗及已知來源文字品質限制均有交代。

一項 Minor 已修：README 的 276 條目原寫「跨情境去重」，易誤認為所有 case 合起來全域去重；改為「各情境內去重職位導覽條目（跨情境累計）」。數據、程式及已有封存結果不變。
