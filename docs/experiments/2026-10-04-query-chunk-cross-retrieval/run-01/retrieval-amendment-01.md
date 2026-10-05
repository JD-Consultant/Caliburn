# 取候選邊界同分修正

原retrieve.py於H01-segments-1／T的第20名停止，還未保存任何新前五結果。原碼與input-manifest保留。diagnosis-01.json與boundary-tie-diagnosis.json確認FIS3321-001v2／FIS3321-002v2命中完全相同的chunk正文hash，離線cosine同為0.6089898118496508；Qdrant只取20父時可能選另一份，無法完成協定指定的父ID同分排序。

修正為每次原生group query先取21父×3hit，保留native score，依同一批已凍結向量重算float64 cosine核對誤差<1e-6，再依原父ID同分規則截20。90個query×representation只有這一個邊界同分，21足夠涵蓋；這是本輪有限有界修正，不能保證未來所有資料庫都只需多取一份。每段有效候選仍20，RRF／全域K5／評分契約不改。

retrieve-02.py於新前五保存前凍結。新的benchmark包含21父過取與保存向量重新計分的成本；與前輪20父的時間不是完全相同操作，不能把差值全部歸因於分段。失敗時已寫出的database-reuse.json移入attempt-01，原服務／向量不改。兩個新反例test_native.py先因無native模組而Red，再核同分排序及拒绝实质分數差異；與四個融合測試一起驗。
