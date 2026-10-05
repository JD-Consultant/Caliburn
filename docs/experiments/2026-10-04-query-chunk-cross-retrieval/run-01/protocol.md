# 員工分段與公版chunk的交叉比較協定

2026-10-04，隔離研究，使用者已同意本探查。不改正式App、不重新生成訪談／Memory、不重寫分段。沿前輪805公版、BGE-M3 revision5617a9f61b028005a4858fdac845db406aefb181、FP16／1024維／8192tokens及Qdrant1.18.2 exact cosine。只重啟已確認自有Qdrant，embedding／reranker容器不需啟動。

## 固定輸入

五合成需求F01–F05與三歷史真A／合成員工H01–H03，同完整員工事實評分。重用原whole及既有人工工作主題segments：F各2段、H各3／4／5段，共8whole＋22segments＝30查詢。query text／原定位及vector hash沿旧檔精確核對；H第一段有共通第一句與第一回答重複沿原amendment保留，不在本輪修字。F與H不同来源分開解讀，不算訪談改善率。必要顧問問題只供脈絡，員工證據只用employee_statement。

公版D805、T8068、U3661point沿前輪storage、metadata與向量原件讀取；T/U各含803獨立overview，任務多碼不dup、全部D非空行保留。職稱／代碼表頭不額外添加、K/S不加；不新切chunk或算新embedding。

## 方法與父合併

每query各查D/T/U，group_by parent_id、group_size3、limit20、exactTrue；公版父max採最高chunkcosine，mean3只重排相同20父，最高min(3,該父chunk数)平均，依原規則不足三個不補零。同分父ID，先去重父，每查詢20份不同公版。

whole只有一query，保持local父排名取5，不加融合。segments每段都保留完整20父序，zero-based RRF k2＝sum1/(2+rank)，同父 across queries合併，全域最高5；同分父ID。RRF只用每段父排名，不直接平均跨query cosine，不讀grade。chunk數不直接加分；同父每段最多貢獻一次。mean3是cosine聚合，RRF是名次融合，0–3為另一個代表性評審。

W-Dmax、W-Tmax、W-Tmean3、W-Umax、W-Umean3為whole控制；S對應五組為segments新增，共8×10＝80組400前五位置。各case仍固定最高五份，不將每段20的聯集全部交付。保存全部query×chunk分數／805父max全序、每段20父、union大小及最後RRF排名／貢獻，可定位強代表是單段候選不足或融合排除。

whole前五須和前輪五法40組一致，S-Dmax須和F/H原R03前五一致；不一致先診斷，不調参湊結果。真90grouping與離線分數核，三次暖機每方法重查所有需要query，整段／分段query次數分開。原query embedding直接重用，沒有新embedding時間，不冒充互動總延遲或大庫ANN／p95。沒有rerank、門檻或D＋U雙路融合。

## 評判與保存

同employee×完整D的前五聯集盲評。旧F49＋H33＋新chunk35＝117pair，按employee／D hash及literal引用重用；不按新結果重評旧pair。只評新pair，沿F／H對應原Prompt及schema；H新增欄位順序沿上一輪，和最初H順序差異仍是限制。過去主要領域粒度、額外責任與孤立動作分級疑義保留，不據此選正式贏家。

本輪Luna/high直接Responses，default／standard、storefalse、backgroundfalse、4096output、concurrency3、SDK retries0，先count預留，最大US$1／100 Responses／付費批次30分鐘；只送既有合成員工與公开公版。provider失敗不自動重跑；引用失敗保留，能唯一定位的字面修正另記before/after、原grade不改。

協定／程式／输入／旧seal hash在新排名前保存。結果逐份列0–3，不加總或平均，不把單一主要領域多3當不同領域齊全；沒有全庫qrels，不算Recall或真人正確率。檢索步驟及量測可以驗收，語意真值、Memory、自動分段、JD/PDF收尾仍未驗。
