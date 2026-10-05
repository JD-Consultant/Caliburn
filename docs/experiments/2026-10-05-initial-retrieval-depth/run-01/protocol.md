# 初搜候選深度比較事前協定

2026-10-05。已同意的隔離研究，先檢查初搜涵蓋再比較rerank。固定八案、O原話整段8query／B2逐理解12query、805公版D與T表示及既有BGE-M3 1024 dense exact cosine。

三個每路深度N20／N40／N80，D/T各前N不同父，完整聯集保留；B2多query每段各搜，再保留員工所有候選及query邊。聯集沒有預先RRF截斷。本輪不rerank、不產生新最終前五；K5是後續階段額度。

### 固定評判清單

沿前輪graded-results的158個同員工原話×公版判讀，僅12個grade3作主要代表回歸清單。每個target沿原grade、main_work、reason／evidence與source hash。未評來源不當負例，不從新增候選自行挑3；這不是完整805qrels或真人職位真值。

主要工作面向沿原cases的major_work_facets；一個被召回的既有grade3只能支持它原main_work中已有的面向。多份公版支持相同面向只記一次；沒有任何已判3支持的面向標unassessed，不把未找到標成全庫不存在。H01目前無grade3，涵蓋不能判定，不使用0/0=100%。

預先保留F05多媒體AVA2172-001v4與H03資材MMP1324-001v4的語意疑義，另列排除兩者的敏感度；原分數不改。正式評分仍逐份0–3，不加總／平均；本輪的保留數是employee×已知代表的布林命中計數。

### 輸出與診斷

每個員工／輸入／N列：query D/T完整prefix與去重union、員工去重候選父數、逐query配對數、已知3代表保留／漏掉、已知主要面向支持／漏掉／未評，以及敏感度。

每個已知代表完整保存各query的D／T名次；最小入池N是所有其query／路徑名次的minimum。回收全部已知代表所需N是其maximum；支持全部已知面向所需N按每facet最先支持它的target計min，再取max。這是診斷值，不在看結果後新增第四種比較。

40個完整父rank從既有chunk scores獨立重建max cosine／父ID順序；20個N20聯集須重現前輪，551＋30seal不變。比較初搜池工作量，沒有fresh DB／GPU／Memory／embedding／LLM時間，沒有新外送或費用。

結果只能說固定pool中的已知代表／面向是否保留；不能宣稱所有員工工作、所有相關公版、全庫Recall或JD已完成。這批資料已看過，不是holdout。
