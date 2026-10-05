# 初搜Top20／40／80涵蓋與候選量比較計畫

> 使用者同意接續初搜參數研究。沿writing-plans／executing-plans inline進行隔離有界比較；不改production、不提交、不新增外送或服務。

**Goal:** 固定原話／B2與D/T表示，量測每路N20、N40、N80是否召回已知主要工作代表，以及已知工作面向與候選量。

**Architecture:** 沿前輪封存的20query完整805父公版排名，不重新生成文字或向量。每query D/T各取N父，去重保留聯集；每員工多query再保留所有候選來源邊。沒有rerank或新的最終前五。

**Tech Stack:** Python標準庫、已驗真Qdrant exact完整排名及既有模型判讀。來源固定BGE-M3 1024 dense與既有805公版，不新做ANN、embedding、DB或GPU推論。

**Spec:** [本輪協定](../experiments/2026-10-05-initial-retrieval-depth/run-01/protocol.md)、[職位整體搜尋候選設計](../specs/2026-10-04-occupation-overview-reference-retrieval-design.md)。

## Global Constraints

- 八個相同已觀察合成案例、原話整段8query與B2逐理解12query；每路N僅取20／40／80。
- 使用原D/T完整805父排名與cosine；每路按父去重，完整union不再融合截額度。
- 評判池固定前輪158個員工×公版、同原話／公版的既有盲評；主要代表12個grade3，不能把未評公版當0。
- 主指標逐案列已知grade3保留／缺漏及既有main_work對固定major_work_facets的支持；沒有已判3支持的面向列unknown，不寫100%。
- F05多媒體AVA2172-001v4與H03資材MMP1324-001v4沿既有語意疑義，預先列排除兩者的敏感度；原grade不改，不能依新rank回改標註。
- 額外診斷每個已知grade3的最小D/T／query名次與回收全部已知代表／面向的最小N；診斷不增加新的固定比較方法。
- 計候選父數與逐query的rerank配對工作量，沒有fresh延遲或模型推論；不把cached slicing速度當產品時間。
- N20候選須重現聯集重播20query，兩輪551＋30seal檔hash不變；前輪完整排名已核177460cosine，本輪另從chunk score獨立重建父rank。
- 不聲稱全庫Recall、真人正確率、新holdout或JD完整度；最終K5保持後續rerank比較額度。
- 保存全部查詢／來源／排名／標註／候選去留／hash／核驗／限制，不啟服務、外送、提交、刪原件。

## Review Focus

1. 排名正好40的相關父：N20缺、N40含；不得off-by-one或把20當chunk數。
2. 同公版多chunk／兩路／不同query：候選去重與配對工作量須分開，跨query配對仍各一次。
3. 多份公版支持相同major facet：工作面向只計一次，不靠公版多加分。
4. 無已知grade3／面向支持（H01）：結果unknown，不能作全部召回成功。
5. 語意疑義及未評公版：保留原分數與敏感度，未知不是負例；不以pool retention冒充全庫Recall或fresh時間。

## Task 1：固定來源、比較與核驗

- [ ] 先寫邊界／去重／unknown反例測試，觀察Red再Green；純資料核算不冒充LLM品質TDD。
- [ ] 凍結plan／protocol／code／來源manifest及兩輪seal；執行48組初搜候選，保存全部12target名次、面向支持、候選量與最小N診斷。
- [ ] 獨立重建40個D/T父rank及48組候選／20個N20控制、grade／面向來源與工作量；核551＋30seal未變。
- [ ] 保存逐案報告與機制／品質界線；一次fresh review，主代理裁定限制，核路由與封存readback。

事前計畫執行後不改，實際完成見progress。沒有新provider job，因此無新增費用或授權需求。
