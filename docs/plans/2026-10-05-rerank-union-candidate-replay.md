# 聯集保留至 rerank 的排序重播計畫

> 使用者已同意「兩路各前20，聯集去重後全部rerank，最後前5」的隔離研究。沿 writing-plans／executing-plans inline；不改 production、不提交、不啟服務、不新增付費外送。

**Goal:** 檢查移除 rerank 前的聯集截斷，是否找回代表主要工作的公版；保留固定八案、原話及B2對照。

**Architecture:** 唯讀使用上一輪已封存的D/T候選與逐query×完整公版reranker logit；來源與模型設定相同的配對才重用。每query保留D20/T20完整去重聯集，按logit排序；多query沿RRF k2融合完整池，最後全域去重K5。

**Tech Stack:** Python標準庫、既有凍結JSON／JSONL、同一固定cross-encoder品質分數。沒有新embedding／DB／GPU／LLM呼叫。

**Spec:** [本輪協定](../experiments/2026-10-05-rerank-union-candidate-replay/run-01/protocol.md)、[職位整體搜尋候選設計](../specs/2026-10-04-occupation-overview-reference-retrieval-design.md)。

## Global Constraints

- 只改候選保留位置；每路N20與最終K5固定。兩組新方法O-U-R、B2-U-R；U指D/T聯集，不是前輪工作單元表示。
- 使用相同員工、query、完整公版正文、模型revision與FP16分數；不重寫原話、Memory、公版或原分數。
- D/T任務命中仍回到父公版；重複父只rerank一次，同query重複來源不能加票。
- B2多query沿zero-based RRF k2，單query保留logit排序；不是原話與B2互相合併。
- 原M-R／D-R／T-R結果完整重播控制；舊封存551檔逐檔hash核對。
- 同員工×公版、正文與員工hash相同的既有盲評重用；不新增外送。若出現未評pair，保存完整待評工作，不能補造分數或把45組授權擴張。
- 分數0–3逐份列出、不相加；這是已觀察合成案例的cached replay，不是新holdout／全庫Recall／JD完整度。
- 比較實際候選配對數；沒有fresh GPU或DB計時，不宣稱重播秒數等於產品延遲。
- 原件保留；只有mutable狀態與路由文件可更新，sealed前輪不改。

## Review Focus

1. 某公版只在任務路進候選且合併名次超過20：必須能rerank，不得偷偷再切20。
2. 同query兩路重複父：去重計一次；B2不同query可各貢獻一次。
3. 缺失或query／公版hash不符的cache：必須失敗，不能借別query分數。
4. B2多query融合：使用完整union重排池，固定k2；最終五份唯一。
5. 未評的新pair：明列缺評，不採用其他員工或自行插入評分；cached結果不冒充fresh時間。

## Task 1：重播、核驗及保存

**Files:** 新增本輪protocol、test_replay.py、replay.py、verify.py、manifest與結果；最後新增README／progress／review／seal，按題更新檢索路由。

- [ ] 先寫負向／截斷反例測試，觀察缺少實作的Red，再加入重播實作並觀察Green。
- [ ] 執行前凍結計畫／協定／程式／輸入hash；核前輪551檔封存；執行八案兩法，完整保存每路名次、聯集、rerank及跨query融合。
- [ ] 重播原48個D/T/M-R控制；核20query完整union的來源hash／logit及配對成本；既有評分重用、缺評另存。
- [ ] 獨立verify重算聯集、排序、融合、選擇、評分來源及舊封存；保存負向probe。
- [ ] 一次fresh review；主代理裁定限制，核文件／路由並封存、hash readback；沒有待評時交付全部結果，有待評時先交付可審查payload再問必要外送授權。

狀態以本輪progress為準，本事前計畫執行後不回改成事後協定。
