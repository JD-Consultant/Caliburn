# 下一問、轉題與收尾：顧問指引對照

狀態：已結案。24 次有效回覆完成，約 17.45 分鐘，估算占用 US$0.073042255；未超過本次 US$0.10／20 分鐘。新版尚未改善指定條件的探索，本輪 Prompt 重排未採用，已恢復修改前工作稿。8105／8106 Docker 未更新。

本批檢查：把「可編寫部分 JD」「可轉換焦點」「可結束整份訪談」集中定義，能否改善正常流程已清楚後的重要條件探索，同時避免重問及勉強延長訪談。

- 方法、假設及判準：[protocol.md](protocol.md)。
- 結果、用量及採用決定：[results.md](results.md)。
- 每案實際問題與接續判讀：[first-turn-review.md](first-turn-review.md)。
- 可見內容的局部調整：[case-overrides.json](case-overrides.json)。
- 員工回答規則及私人答案：[reply-policy.json](reply-policy.json)，只供評測者，不預載給顧問。
- 舊案例與前次失敗：[前批結果](../jd-condition-exploration-2026-10-07/results.md)。
- 接線：[run_comparison.py](run_comparison.py)。沿既有真顧問 Runner、隔離 PostgreSQL 及費用護欄，不另建 Agent loop。
- 環境、測試及還原紀錄：[execution-notes.md](execution-notes.md)。

模型固定 `gpt-6-luna`／high，輸出上限 16,384。舊版是本次修改前、已含條件探索規則的 Prompt，不是最早沒有探索規則的版本；兩版工具、Context、起始 JD 及原話相同。

本批外送已結束，不再次執行 `prepare`／`execute`，也不使用剩餘預算補跑。實際執行版本保存在 `live-02`、`live-03`、`live-04` 的凍結包；`live-01` 只有未啟動的準備包，不列入結果。可用 [verify_evidence.py](verify_evidence.py) 離線核對原件，不需資料庫或模型。

語意判讀、成品、工具路徑與用量均已保存；實測結果與一般品質結論分開。公版 HTTP 為固定合成 fixture，沒有背景 Memory 外送，不作真 RAG、超容量或整份職務訪談驗收。

接續備忘（2026-10-07）：本次先保存紀錄，不啟動下一批測試或修改產品。未解問題與後續討論方向沿 [results.md §4](results.md#4-採用決定與下一步) 查閱，不另建重複清單。
