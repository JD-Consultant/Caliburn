# 執行進度

2026-10-05，隔離研究inline，計畫：docs/plans/2026-10-05-rerank-union-candidate-replay.md。保留其他dirty變更與全部前輪原件。

Pre-flight：已保存的D-R與T-R涵蓋同query完整D20/T20聯集配對；先核實cache來源，再使用。舊M先縮20，新U沒有這步，多query融合均沿k2；產消契約是query_id＋document_id＋兩個正文hash＋logit。

- [x] 有意義的截斷／source-binding反例Red→Green，6測試通過，原Red／Green log保留。
- [x] 凍結17 input/code manifest後重播；48原控制完全相同。
- [x] 獨立核驗16組80位置、20query／628pair、71既有評分與字面引用；0缺評、0新provider／DB／GPU、外部費用0。配對量較舊M-R 400增57%，沒有fresh計時。
- [x] 一次fresh review無Critical／Important／Minor，五個mutable檢索路由更新；文件／連結及最後封存readback由主代理核對。

Ruling：本輪只驗保留聯集到rerank後再留5，不同時改N20深度 — 使用者同意的探針如此，可隔離早截問題 — 若錯會把候選深度效果誤歸因於rerank。

Ruling：同query與同公版正文的固定模型品質分數可重用 — 排序不依候選同批其他文本，需核SHA及模型來源 — 若錯會用錯分數推導虛假的品質提升；不宣稱fresh推論或新穩定性。

Ruling：重播不驗實際時間降低 — cached排序不含GPU／DB推論；只列配對數 — 若錯會低估成本或錯選方案。

文案核對：README初稿誤稱F01 U與T-R整個top5相同；讀兩組exact IDs後另存明示report-source-correction，正文改為共有網站系統#1、其餘完整序列不同。不改logit／選擇／grade／protocol，原report.py與manifest保留。

Final: Ruling: 模型grade語意、JSON順序及舊引句修正未做新人工驗收 — 沿既有判讀與原限制，不能當真人qrels — 若錯會把模型判斷當事實。

Final: Ruling: fresh穩定性與GPU／DB／端到端時間未判 — cached replay只推導本次固定分數的選擇，配對量不等於延遲 — 若錯會低估成本／高估穩定性。

Final: Ruling: 全庫Recall、holdout、JD完整度與production適用性未判 — 只作八案有限回歸，不設定正式搜尋或收尾 — 若錯會漏工作或過早收尾。

Final: Ruling: review未判路由／文件／封存完成 — 主代理另核差異、連結、manifest與逐檔hash readback，保留全部原件 — 若錯會損失追溯或把候選冒充現行。

Final: minor (deferred): 無；沒有第二次review。事前plan／protocol／程式保持凍結，文案修正獨立記錄，不提交、push、清資料或啟服務。
