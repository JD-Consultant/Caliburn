# ADR 0022 — 相似比對(items:match):indexer 確定性能力、三區分帶、非破壞呈現

- **狀態**:Accepted(2026-07-04)。
- 研究依據:[`../specs/2026-07-02-multi-ocs-candidate-dedup-research.md`](../specs/2026-07-02-multi-ocs-candidate-dedup-research.md)
  (五輪:權威共識、真實資料實驗 ×3、reranker 實測)。
  設計細節:[`../specs/2026-07-04-similarity-matching-v1-spec.md`](../specs/2026-07-04-similarity-matching-v1-spec.md)。

## 脈絡

多選職類必然把語意相同、字面相異的候選倒進同一池(基準間無共用字典)。實驗證實病有兩種:
**真重複**(態度層斷崖分布,0.9 可切)與**相似但不同**(任務層真重複 0.868 與相關任務 0.846
分數帶重疊——**任何門檻都切不開,機器不可自動合併**)。「去重」(刪留一)因此不是正解;
ESCO contextualisation 與 Amazon 2026 政策皆警告過度合併。LLM 訪談引擎(ADR 0020)未來需要
同一能力當 tool(灰區對 → 鑑別提問)。

## 決定

1. **能力名「相似比對」**,落 **ocs-indexer**(相似度的 bounded context):
   `POST /items:match`,kind 通用(task/K/S/attitude/…),契約沿用
   `packages/indexer-contract`(contract-strategy row 3:internal、all-Python、單一消費者)。
2. **確定性、LLM-free、非破壞**:六步純管線(清洗→NFKC 同字收斂→嵌入(唯一 I/O)→
   跨來源兩兩 cosine→**Fellegi-Sunter 三區分帶**→貪婪星型分群);不刪任何項目。
   灰區永遠交人(未來 LLM 只幫問問題)。
3. **星型紅線**:成員與中心直連 ≥θ_high 為硬條件(SKOS closeMatch 非遞移);
   對按(分數降序、id 升序)決定論處理。
4. **兩層代表**:indexer 回 medoid(幾何);**survivorship(主基準優先→文字最完整)在
   web** render 時算——主基準是文件層、可隨時清(`clearPrimaryBasis`)的狀態,api/indexer
   不知道。刻意不抄 SemDeDup 的「留離心最遠」(其目標是訓練資料多樣性,非可讀代表)。
5. **api 純搬運**:build_pack 後並行打態度/任務兩池,原樣掛 `pack.similarity`(optional);
   失敗不掛(enrichment,ADR 0018)。**web 鐵律:選擇邏輯(自動勾選/身分寫入)跑在平的
   成員選項上一行不改,分群只是 render 顯示變換**;收合列即代表成員本人,群無可選身分。
6. **門檻 = settings + 校準紀律**:attitude {0.90,0.70}、task {0.95,0.80}(實驗定案)、
   k/s {0.85,0.65}(僅校準;**K/S 混池表面上線前必開 reranker** ——實測 skill 灰區
   116–186 對、cross-encoder 只能當灰區過濾器)。絕對門檻不可移植(各向異性),
   改門檻 = config change + 校準腳本紀錄。

## 後果

- ✅ 使用者:真重複收合(態度池)、相似有徽章可比對(任務);零選項被機器消滅。
- ✅ 降級 = 沒這功能(池原樣);文件 OcsDocument 與既有自動勾選碼路零變動
  (兩個湧現不變量:來源不相交 ⇒ 群內每基準最多一條;survivorship ⇒ 代表=主基準身分)。
- ✅ LLM 訪談引擎接同一 endpoint 零改動(確定性 tool、agent 上層消費)。
- ⚠️ O(n²) 上限 items ≤500(413);門檻只對「本池 × bge-m3」有效,換模型須重校準。
- ⚠️ v1 表面僅態度+任務;units 校準先跑、K/S 待 reranker。
- 📌 不做(YAGNI):reranker 部署、快取、sparse 混合、Qdrant cluster_id 下沉、
  等價對持久化、多租戶語料分區(`sources` 已容納)。
