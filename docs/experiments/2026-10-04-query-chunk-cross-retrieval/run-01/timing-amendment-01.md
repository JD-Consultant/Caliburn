# 暖機計時範圍澄清

retrieval-amendment-01.md的「保存向量重新計分的成本」措辭過廣。retrieve-02.py在品質核對階段預算所有query×chunk的float64 cosine，benchmark只使用已算好的canonical_scores，沒有在240個暖機trial內重新執行完整matrix乘法。

本輪每trial計時實際包括：每段一次Qdrant exact group query（取21父×3hit）、native分數與預算cosine核對／替換、截20與max或mean3父排序、多段RRF、最高五份選出。query embedding、離線全向量cosine預算、語意評分、索引建立與App讀Memory都不在計時內。前輪取20父而本輪取21父，也使跨輪時間不是完全相同操作；整段／分段比較以本輪同樣過取21的配對控制為準。

因此本輪可報cached向量的本機DB／合併暖機時間，不宣稱使用者端總延遲、預處理免費、p95或大型庫ANN速度。
