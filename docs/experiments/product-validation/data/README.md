# 實驗資料（保存供專題報告與重新核對）

本目錄保存各次有界真模型實驗的**原始輸出與整理後的指標**；結論、取捨與限制只在對應的任務證據頁維護，這裡不重寫。全部是合成資料，不含金鑰、真實員工資料或 provider 的不透明 reasoning。位元組不變的資料檔以 `.gitattributes` 排除換行轉換，雜湊記在各目錄的 `SHA256SUMS.txt`。

| 目錄 | 內容 | 對應證據 |
|---|---|---|
| [`instruction-experiments-2026-10-01/`](instruction-experiments-2026-10-01/README.md) | 顧問 A 指引的對照實驗：基準 Q1（c0）、候選 Q2（c1）、補跑 Q2b（c1b），以及長訪談旅程；含每份的原始 JSON、可讀逐字稿＋最終 JD、指標 CSV、算數字的工具副本 | [T14 證據](../../../history.md#source-d3293e9b28c75bbb6616)、[T17 證據](../../../history.md#source-98d840caa9eed7fb2840) |
| [`earlier-experiments-2026-10-01/`](earlier-experiments-2026-10-01/INDEX.md) | 2026-10-01 以前的有界實驗原始輸出（50 個檔）：舊預設基準 b0、Sol 對照、核心旅程、來源選擇診斷、effort／B1 精度診斷、壓縮與額度探針（含 160K 真窗口） | [T14](../../../history.md#source-d3293e9b28c75bbb6616)、[T16](../../../history.md#source-6d2d7ab4abfedbf8416e)、[T17](../../../history.md#source-98d840caa9eed7fb2840) |

使用須知：樣本小、員工是模型、自動檢查是粗略標記，只適合比較版本間的大效果；不能當普遍品質保證，也不能替代真人試點（V25）。
