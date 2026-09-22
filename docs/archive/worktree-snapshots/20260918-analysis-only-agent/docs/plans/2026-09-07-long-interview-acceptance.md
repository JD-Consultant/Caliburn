# CT09：整份工作長訪談驗收

LLM-Q019 · 2026-09-07 · Owner要求實際扮演員工訪談；基準 a9d87e0a。只測隔離 analysis-only API，不改產品prompt／架構，不製作JD。承接[CT08](../specs/2026-09-07-interview-partial-knowledge-repair.md)，方法見[資訊取捨](../../../../docs/specs/2026-09-07-work-case-and-understanding-information-selection.md)。

## 驗收目的（Owner本輪澄清）

不是足以開始寫某項Task，而是對**整份工作**的理解足以支持完整、高品質、全覆蓋JD：已知工作範圍、本人責任／界線、頻率／觸發、重要條件與例外、產出／判準、相關專業均正確；不把個案當永久工作，不把不知道當沒有。這是具體合成職位的驗收，不能聲稱證明任何JD百分之百完美。

## 測法與停止線

1. 先封存不傳給顧問的合成職位oracle：電商售後營運專員、8個工作範圍、重要案例和更正。事實在自然回答中逐步揭露，主代理依顧問問題扮演員工，不使用另一個付費模型生成員工答案。
2. 全新獨立DB與文件，沿實際create_app／runs／官方provider入口訪談，保持模型Luna／medium、既有Skill／Memory工具／背景排程／上下文。最多120次生成、US$0.50 usage預算；每次SDK嘗試也計數，包含背景與reader。此為本次測試護欄，不是產品規格。來源[OpenAI當日價格](https://developers.openai.com/api/docs/pricing)。
3. 通常20–30輪；依提問和實際涵蓋調整，不硬湊輪數。觀察正常背景發布，不手動代跑B2，不偷偷植入Memory。不為了過測修改提示。
4. 最後由員工請顧問盤點完整工作範圍與剩餘未知（不写JD）；逐項對照已揭露事實、正式發布理解、詳記、來源。另用無近期對話reader檢查重要案例與更正能否找回。
5. 發現錯誤保留失敗；能繼續就觀察是否自然恢復，卡住則停止該路徑，不擅自加產品機制。不把資料未提供算記憶遺失，也不把來源可查當成理解已正確。

## 測試器界線

沿用既有Ledger／snapshot，針對長測擴大**測試器**舊80KB封包限制，保持保守預留與120次／US$0.50上限；不改產品context budget。正常訪談用自然排程；診斷inspect／fresh reader在app startup前停用其排程，避免CT08的重複整理污染。每輪重開服務同時驗證持久延續，原始對話不覆寫。實際壓縮是否發生依wire判定，不虛稱已測。

## 紀錄

短結論與缺口寫同日CT09 spec；oracle、逐輪原文、usage、Memory版本與引用放獨立JSON evidence，不把長逐字稿塞進current register。入口只更新本輪gate和結果。所有既有未提交修改保留；不merge／push。
