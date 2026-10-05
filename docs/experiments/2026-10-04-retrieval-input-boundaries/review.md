# 唯讀審查紀錄

2026-10-04，既有reviewer `review_occupation_experiment` 完成方法、程式、原始資料及報告審查。最終沒有未解除Critical／Important，也沒有必須修正的Minor，可封存本輪研究；不是正式採納或JD品質驗收。reviewer未改檔、未執行GPU或DB。

預審指出初始cases.json仍有前輪歷史new_holdout標籤，容易與本輪全部已觀察的範圍混淆。已在新embedding／排名前另存cases-observed.json／input-amendment-01：split全改observed_regression，source_split保留歷史，原話／topics／grades不動。三種表示的全文、標點、連續offset與origins都可獨立重建。

最終核查：

- 7個離線測試與verify.check()通過；變體identity wrapper能拒絕相同request_id卻誤標variant，既有DB次數／config／response guard也保留。
- 使用不依analyze、per_passage或metric的腳本獨立重建132筆完整選取與段落mapping、支持主題／次要涵蓋、字符與pair數、6組摘要，以及22個原話rerank前輪控制，全部一致。
- 逐內容鍵重建缺件，2,660個需要pair與jobs／實際補算集合一致，沒有缺分數當0。
- 自行由805正文向量重算256組full排名，與保存一致；品質原生score最大誤差1.2863207066e-7。116次benchmark native查詢也全對應正確variant及深度。
- 本輪24次實跑計時及階段數字與結果一致；前四輪132／69／86／96份sealed原件逐hash未變。

README結論合理：固定N20/K5，原話／合併／逐句支持主題86／78／86；合併8個缺口全是次要工作。逐句已標註涵蓋沒增加，正文增加89.1%、邏輯pair增加116.2%。這是不同總工作量的已觀察合成輸入敏感度，不是同預算方法優勝、新holdout或Memory品質驗收。

報告正確把公版留作客製化JD完整度參考，允許多來源及任務拆併；命中文件不等於公版所有子句適用、本人責任確定或JD已完整。已知職位界線也不拿來算文件precision。真正工作事項切分、JD語意拆合與後續決策模型／主LLM仍另驗，沒有正式接線或以公版任務數定停止。
