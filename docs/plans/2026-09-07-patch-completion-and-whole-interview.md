# CT12：patch 發布補驗與整份工作訪談

LLM-Q019 · isolated G5/G8 · 基準 `9a196c94` · 2026-09-07。

## Preflight

- Owner 本輪核准「都補完……測試長訪談到訪談結束」。承接 [CT11](../specs/2026-09-07-official-memory-patch-trial-results.md) 及 [CT09 整份工作驗收](2026-09-07-long-interview-acceptance.md)，不是新架構設計。
- 唯一待驗：修正版是否能完成 B2 發布，並在整份工作訪談中持續正確更新、保存與回查。
- 隔離 analysis-only，不接 JD／UI／production，不用舊 pending tool 載荷；保留舊測試失敗證據及所有非本輪修改。
- 新測試帳本最多 120 次 Luna／medium、US$0.50；是本輪安全護欄，不是產品限制。不滿足完成條件就不得報通過；需改產品語意／authority 或成本級別時回 Owner，不自行重設額度。

## 順序與 pass/fail

1. 針對性 B2：合成來源與既有 Memory → 真 B1／B2 → patch 回饋 → final → 發布。檢查修正、月報時間、未改案例與引用；這一步的明示 patch 測試提示不得當自然選工具證據。
2. 全新 PG 文件，沿真 API 自然訪談。沿用 CT09 已封存 8 範圍／4 案例 oracle，回答依顧問提問逐步揭露，不將 oracle 直接塞進模型或 Memory。主訪談、背景整理、模型原生推理延續、重開持久化均觀察真實結果。
3. 對整份工作做收尾盤點；不以模型說「夠了」單獨判定。對照已揭露資料：工作範圍、頻率、責任界線、例外、案例差異、明確更正、未知項目。訪談須能結束而非反覆重問；案例不能各變成一個永久工作。
4. 最終 Memory／詳記／來源逐項核對，另用不帶近期聊天的 reader 回查早期案例與更正。沒有發生原生 compaction 則如實標未觸發，不假裝測過。
5. 有錯先封存，對照官方契約與本地框架原碼；必要局部修正先失敗回歸再修復。驗證成功、獨立審查後保存本地 commit/tag，不 merge/push。

## 來源與邊界

- [OpenAI patch harness](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness)，本輪重讀：應回傳每個 patch 的成功／失敗，驗證 path，區分暫存套用與發布。這不是宣稱本案 function tool schema 就是原生 apply_patch schema。
- [OpenAI Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、[價格](https://developers.openai.com/api/docs/pricing)：保留 Luna／medium，不以高階模型掩蓋問題；Ledger 計每次 HTTPS 嘗試與 usage，不保存 key／opaque reasoning。
- 底層 patch 選擇、SDK first-match 限制與官方固定原碼沿用 [CT10](../specs/2026-09-07-memory-editor-framework-comparison.md)，不重開已完成研究。

短結果另寫 spec；逐輪原文／模型與工具結果／版本／費用放 evidence。這是代表性合成職位驗收，不是任何職位皆百分之百完美的證明。

## Owner 中途決定

針對性 B2 已發布，但 B1 候選曾把「案件月報」擅加限定為「退換貨案件月報」，與同一輸出的詳記範圍不一致。Owner 明確選擇：**先保留紀錄，訪談測完再討論**。本輪不因此修改抽取提示、schema 或 verifier；先在同一基準完成自然訪談，結果分開報技術發布與內容品質。

## 驗證收尾

已完成 14 輪自然訪談、兩批自然背景整理、完整來源核對與四次獨立回查；65 次／US$0.07783077，帳本關閉。技術路徑已完成，但抽取／回答的範圍偏差與顧問收尾品質仍待 Owner 討論，不是整體品質 PASS。原生 compaction 未觸發。562 項含 PG 回歸通過。詳見 [CT12 短結果與問題清單](../specs/2026-09-07-patch-and-whole-interview-results.md)，後續不擅自修提示或重開本次額度。
