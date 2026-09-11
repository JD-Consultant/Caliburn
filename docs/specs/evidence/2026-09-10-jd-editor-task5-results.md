# Task5：取消、停止與恢復實作驗收

2026-09-11；狀態：**獨立 Spec PASS／quality Approved，T5-R01–R06 全部 CLOSED；root 已接受隔離 Task5，準備精確本地保存點。**

[初審](jd-editor-task5/review.md)、[fix1b closure](jd-editor-task5/fix1b/review.md)及[最後 R06 closure](jd-editor-task5/fix2/review.md)保留完整演進；修正封存競速、遺失回覆查回、明確恢復出口、慢速等待的鎖範圍、原保存結果優先，以及停止／恢復直到最後讀取都完成才釋放關閉等待。

- [fix1](jd-editor-task5/fix1/report.md)：54 項編輯／服務、63 項 Memory 回歸及契約生成／型別／lint 通過。
- [fix1b](jd-editor-task5/fix1b/report.md)：保留原兩項編輯器測試，新增恢復測試獨立存放，最終 Web 37 PASS；較早 35 PASS 不作最終案例數。
- [fix2](jd-editor-task5/fix2/report.md)：成功及拋錯兩個停止反例 2 RED，修正後 9 項相關測試 PASS；沒有重跑前述集合，不累加重疊案例。
- [鎖範圍官方核對](jd-editor-task5/fix1/lock-evidence.md)：保留短暫共用狀態同步，慢速操作退出全域鎖；不宣稱所有全域 mutex 都錯誤或未量測的效能倍數。

34 個最終來源由原始／fix1b／fix2 凍結 hash 合併核對；首敗、原始紀錄與依賴警告完整保留。

31 個來源檔逐一核對 SHA256，完整原始結果與首敗已保留。實作報告列規定 JD 集合 36 項、Web 23 項，Memory 首輪 62 通過／1 失敗、修正後受影響 43 項通過，最後接點 8 項通過；多組有重疊，不加總成不實案例數。

- [凍結實作報告](jd-editor-task5/implementation/report.md)
- [原始證據索引](jd-editor-task5/implementation/raw-files.json)
- [來源 hash](jd-editor-task5/implementation/source-files.json)
- [人工恢復介面設計及 closure](jd-editor-task5/manual-recovery-transport/review.md)
- [前次未受管測試 API 的受控交接](jd-editor-task5/bootstrap-handoff/README.md)

報告原件的相對連結以原 `scratch/task-5-report.md` 位置為準；此入口提供可用的責任路由，原件 bytes 不改写。NL08 未直接觀測 JS transform 執行中停止；NL10 跨程序場景為人工 A 提交加 B 選取，AI binding 另測；NL11 本機 nested 不相容未觸發。這些限制已由獨立 review 接受為有限證據，不用命名相近的案例代稱已驗。

Task6、自然模型、實際 OS 真人輸入及成品尚未完成。0 付費，production ADR0060 與 Proposed0073／0074、G6 界線不變。

[完整審查](jd-editor-task5/review.md)列 T5-R01–R06 六個既定契約缺口，原作者集中修正後做同一 reviewer 窄複核。測試中既有 Starlette／AnyIO DeprecationWarning 保留，記為 upstream 非阻擋，不假稱輸出無警告。原始測試綠燈不抵銷 review findings。
