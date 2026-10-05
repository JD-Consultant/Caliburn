# 檢索輸入邊界敏感度實驗

已授權的隔離研究延伸，依[生成前協定](../experiments/2026-10-04-retrieval-input-boundaries/protocol.md)執行；不改正式產品／資料或commit。使用者確認公版為客製化JD完整度參考，任務允許多對多；向量查詢方式待實驗後設計。

- [x] 固定22個既有情境、86來源支持主題及三種不刪改原話的表示；TDD核拆分可重建及否定／權責保留，不作新ground truth。
- [x] 重用可核模型／文字hash的向量與pair cache，缺少才實際補算；真Qdrant exact與full805排名逐項核。
- [x] 固定N20／K5比較三種輸入之dense／rerank工作主題涵蓋、次要主題、已知混淆、正文與pair數；原話控制須吻合前輪結果，不調參。
- [x] E01／M04每種表示兩次實跑暖機檢索、tokenize、GPU及去重，分開冷載入與embedding。
- [x] 獨立重算與篡改反例、唯讀review、報告／入口更新，停止自有研究服務、確認前輪seal未變並封存本輪。

這輪僅測查詢輸入邊界，不驗收JD語意拆併／本人責任／真正完整度，後續分元件驗證。

完成證據：[報告](../experiments/2026-10-04-retrieval-input-boundaries/README.md)、[核對](../experiments/2026-10-04-retrieval-input-boundaries/verification-final.txt)、[唯讀審查](../experiments/2026-10-04-retrieval-input-boundaries/review.md)。原話段／合併／逐句86／78／86個來源支持主題，372次真Qdrant、24次實跑計時；全部是已觀察合成案例，不採納正式查詢方式／參數或JD完整度規則。
