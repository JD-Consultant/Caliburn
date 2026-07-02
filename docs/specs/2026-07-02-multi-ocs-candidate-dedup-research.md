# 研究紀錄 — 多職類參考下的候選近重複:去重不是唯一解

- 日期:2026-07-02。狀態:研究完成,待與維護者討論(尚無 ADR/plan)。
- 問題(維護者原話):「我們可以選多職位來當參考,所以可能有類似的工作項目、工作內容、OPKSA 等等,
  使用者會看到重複的選項、不知道怎麼選。不一定要用去重。」LLM(訪談引擎,ADR 0020)也要用到。

## 0. 問題定義:近重複出現在四個表面

MOL 職能基準是**每職業一份文件、各自編碼**(T/P/O/K/S/A 皆為基準內局部碼),不同基準之間
**沒有跨職業的正典實體**——選多職類必然引入語意相同、字面相異的項目(尤其共通職能類:溝通、
專案管理、品質意識)。近重複暴露處:

| # | 表面 | 現狀行為 | 痛感 |
|---|---|---|---|
| S1 | **任務勾選**(TaskCuratePanel / `task-candidates`) | 依職類分組,**跨組零去重** | 高:兩組各有「撰寫測試計畫」級的近重複,使用者不知選哪個/都選 → 文件出現兩條幾乎一樣的工作項目 |
| S2 | **表頭候選池**(`header-meta`:所屬職類/職業/行業/**態度**) | `header_meta.aggregate` 已做 **exact-key 聯集去重 + `sources` 溯源 + first-seen 排序** | 中:exact 擋得住完全同字,近重複(「溝通協調」vs「良好溝通能力」)全存活;態度池最明顯 |
| S3 | **LLM grounding**(`ai.py::_task_candidates` → `extract_tasks`) | 多職類任務 flatten 成 `[{id: task_code, title}]`,**無去重** | 高:近重複 title 讓模型重複建議;**另有正確性缺陷,見 §1.3** |
| S4 | **文件彙整品質**(北極星藍圖⑤彙整,ADR 0020) | 無任何機制 | 中期:近重複任務各自填 K/S 後,最終 JD 重複冗長——訪談引擎的彙整節點需要語意合併能力 |

K/S/O/P 逐格候選(`task-catalogs` / CellFillerPanel)**不混池**——每任務的池來自它自己的
來源基準(`indexer_ref`),近重複風險低,不在本題範圍。

## 1. 現狀盤點(程式碼事實,2026-07-02 @ main `0eb1d25`)

1. `apps/api/app/core/domain/header_meta.py`:`_merge_pairs`/`_merge_texts` 以
   code(fallback name)/exact text 為 key 聯集;**每候選已記 `sources: [ocs_code]`**
   (docstring:前端可在「最後一個貢獻來源被移除」時才撤候選)。→ **溯源基建已存在**,
   任何分群/合併方案都能沿用這個型別。
2. `documents.py::task_candidates`:逐 code 呼叫 `occupation_tasks`,原樣分組回傳;
   `buildTasks` 的 picked 帶 `{ocs_code, task_code}` 雙鍵,文件端 `indexer_ref` 可溯源。
3. **撞碼缺陷(S3)**:`ai.py::_task_candidates` 用裸 `task_code` 當 grounding id,而任務碼
   是基準內局部碼(每份基準都有 T1、T1.1…)。多職類 flatten 後 id 不唯一;
   `TaskCuratePanel.runExtract` 把建議 id 對**每一組**都試著打勾(`for g of groups`)——
   模型建議 A 基準的 T1,B 基準的 T1(完全不同任務)也被自動勾選。
   **這是 correctness bug,獨立於近重複策略,應優先修**(id 改 `ocs_code::task_code` 命名空間)。
4. 嵌入基建:BGE-M3(dense+sparse)已服務化(`apps/embedder`,ADR 0012),api/indexer 走 HTTP;
   Qdrant 已運行(ADR 0003/0009)。→ 語意相似度計算**不需新增依賴**。

## 2. 權威資料

### 2.1 分類學層:重複的根因與正解(ESCO / O*NET 模式;MOL 共通職能)

- **ESCO(歐盟官方)**:技能支柱維護 ~13,500 個**正典技能/知識概念**,每概念一個 preferred term
  + 多語 non-preferred terms(同義詞表);職業透過關聯**引用同一概念**——跨職業零重複是
  **資料模型層**的成果,不是演算法補救。
  另兩個關鍵概念:
  - **Skill reusability level**(四級:transversal → occupation-specific):跨域通用技能
    (≈ MOL 的共通職能)正是最容易近重複的類別;職業特定技能極少碰撞。→ 可用相似度分布
    預期:態度/軟技能池碰撞率高,專業任務池碰撞率低但傷害大(直接進文件)。
  - **Skill contextualisation**:ESCO 刻意把 transversal 技能「情境化」成職業特定版本——
    **近重複可能是有意義的情境變體**(同是「品質管理」,半導體版與工具機版的脈絡不同)。
    → **反對 silent merge**:合併要嘛保留變體可展開,要嘛讓使用者/LLM 明選。
- MOL《職能基準發展指引》(先前深讀,見
  [`2026-07-02-llm-interview-authoring-research.md`](2026-07-02-llm-interview-authoring-research.md) §7)
  將職能分**共通/專業**兩類,與 ESCO reusability 同構——本土權威同樣預期共通類跨基準高度相似。

### 2.2 演算法層:語意去重與多樣性排序(均為業界主流、可直接落地)

- **SemDeDup**(Abbas et al., Meta AI 2023, arXiv:2303.09540;**NVIDIA NeMo Curator 已產品化**):
  embedding → 分群 → 群內 cosine 超過門檻視為語意重複、留代表。網路級資料可去 50% 而效能不損。
  我們的池只有數十~數百項:**免 k-means,池內兩兩 cosine + 連通分量即可**,O(n²) 完全可行。
- **MMR**(Carbonell & Goldstein 1998 經典;LangChain/Google Cloud 官方文件均內建):
  以 λ 平衡「與查詢相關」vs「與已選項目不相似」的貪婪重排——**不刪資料的多樣性呈現**,
  適合「排序讓近重複不相鄰」的輕量選項。
- **BGE 官方門檻實務**(bge-model.com / HF model card):短句相似過濾「依資料的相似度分布選
  0.8 / 0.85 / 0.9」——門檻要**用我們自己的池校準**(拿幾組真實多選職類的池跑分布),不硬編猜測。
  需要更準的兩兩判定時,**bge-reranker-v2-m3**(cross-encoder,輸出 [0,1])可部署進既有
  embedder 容器——但先驗證 dense+sparse 夠不夠,YAGNI。
- **上下文冗餘傷害 LLM**:redundancy-aware context selection 是 2025-26 RAG 研究熱點
  (如 AdaGReS, arXiv:2512.25052:token 預算下冗餘感知的貪婪選擇);LangChain MMR retriever
  存在的動機即「重複檢索結果浪費上下文、降低回答多樣性」。→ S3 給 LLM 的 grounding 清單
  **收斂近重複=省 token + 減少重複建議**,與 S1 的 UX 收斂是同一份工作。

### 2.3 基礎設施層:Qdrant 官方 grouping

- Qdrant **`query_points_groups` API**(官方文件):以 payload 欄位 `group_by` 分組回傳,
  官方明示用途「避免同一 item 在結果中冗餘」;`group_size` 控制每組取幾點、`with_lookup`
  可掛共享資料。→ 若未來在**索引時**算 cluster_id 存 payload,檢索端去重是現成能力,
  不用自己寫。(F4 職類搜尋的 api 端 dedupe-by-ocs_code 未來也可下沉至此。)

### 2.4 UX 層:NN/g 兩條直接適用的證據

- **Choice Overload Impedes User Decision-Making**(NN/g):選項越多、蒐集資訊與決策成本越高,
  分析癱瘓。→ 近重複是「無資訊量的選項膨脹」,收斂本身就是 UX 改善。
- **Explicitly State the Difference Between Options**(NN/g):**選項難以區分時,使用者要嘛
  假設全都一樣、要嘛為微小差異糾結;正解是把「差異」顯性標出**。→ 對近重複不是只有「刪」:
  **標差異(來源職類、用詞差異)讓使用者能選**,與 ESCO contextualisation 的警示互相印證。

### 2.5 大廠生產系統:技能圖譜的共識資料模型(第二輪研究)

- **LinkedIn Skills Graph**(官方工程部落格):**~39K 正典技能 + 374K 別名**(26 語系)、
  20 萬+ 技能間關聯;由**人類分類學家 + ML(KGBert 關係推斷)混合維護**;抽取後的技能一律
  **正規化到正典表示**(「data analytics」=「data analysis」)。
- **Workday Skills Cloud**(官方):**~50K 正典技能 + 200K 已認同義詞**;ML+圖技術維護關聯;
  排程背景工作把與正典完全相同的眾包技能「吃掉」只留正典版;曾把 **100 萬條使用者輸入技能
  收斂到 5.5 萬**。
- 與 ESCO(§2.1)三方互證:**業界對技能/任務類短文本重複的正解收斂於「正典實體 + 別名集 +
  非破壞性連結」**——沒有人放任重複,也沒有人無家可歸地硬刪。但三者都養著分類學家團隊——
  正典化是長期工程,不是一個 endpoint;我們的量級適合**查詢時分群起步、人工確認逐步固化**。

### 2.6 判定管線:Entity Resolution / MDM 的企業定式(第二輪研究)

- **AWS Entity Resolution**(官方服務):rule-based(瀑布規則)與 ML matching 兩式;產出
  **match group + confidence 0.0–1.0**。ER 管線的標準形:blocking → 兩兩比對 → 分群。
- **Informatica MDM**(官方):golden record = **match(exact/fuzzy)→ merge → survivorship**;
  survivorship 規則 = 來源階層(trust/precedence)/最新/最完整。→「**群裡誰當代表**」有企業
  標準答案:規則驅動——對我們即「主基準優先,次以文字完整度」的正式化。
- **LLM 當比對器**(Peeters & Bizer, EDBT 2025;arXiv:2310.11244、2405.16884):LLM zero-shot
  entity matching 比最佳 PLM 高 8–68% F1、對未見實體泛化強;「Match/Compare/**Select**」框架中
  從候選集**選擇**的形式表現佳。→ 邊界案例(cosine 落在灰區)可用 LLM 判定,學術已驗證;
  也直接背書未來訪談引擎彙整節點的 LLM 合併判斷。

### 2.7 關係語意標準:W3C SKOS 的一個關鍵設計警告(第二輪研究)

- **SKOS**(W3C Recommendation)mapping 屬性:`skos:exactMatch`(廣泛場景可互換,**遞移**)
  vs `skos:closeMatch`(僅部分場景可互換,**刻意不遞移**——避免跨體系鏈接時的「複合誤差」)。
- → 演算法直接推論:**鬆門檻下不可用連通分量分群**(A≈B、B≈C 鏈成 A≈C 正是 SKOS 禁止的
  複合誤差);近似級(closeMatch)分群應以**代表為中心的星型**、或只在 exactMatch 級門檻
  (≥0.9 級)允許傳遞。若日後固化人工確認的等價對,SKOS 兩級語意就是現成的儲存詞彙。

### 2.8 呈現與 LLM 上下文:大廠 UX 定式與模型商官方指引(第二輪研究)

- **Amazon parent-child variations**(Vendor Central 官方指南):近似商品收在**不可購買的
  parent** 下,顧客在單一頁面內選 child 變體——世界最大目錄對「近重複呈現」的答案就是
  **分組+變體內選**。且 **2026 新政策**:「功能差異顯著」的 child 不再共享評論——連 Amazon
  都在管制**過度合併**,與 ESCO contextualisation 警示(§2.1)互證:分組門檻寧嚴勿鬆。
- **Anthropic 官方**(Effective context engineering for AI agents):context 是**有限資源、
  邊際效益遞減**;token 增加導致 **context rot**(n² 注意力被稀釋);「每一步推理都是策展
  決策」。→ grounding 清單的近重複是純粹的上下文污染;S3 的收斂由模型商官方指引直接背書。

## 3. 解法選項空間 × 表面適用

| 選項 | 機制 | 優 | 劣 | 適用 |
|---|---|---|---|---|
| A. 硬去重 | 相似度>門檻直接刪、留一 | 最乾淨 | 丟情境變體(§2.1 反對);門檻誤判=使用者根本看不到某選項 | 僅 exact-dup(已有)|
| B. **分群+代表+溯源** | 近重複收成一群:顯示代表項+「n 個來源」徽章,可展開看變體與出處 | 不破壞資料;差異顯性(NN/g);LLM 拿代表項省 token | 需要分群計算+UI 支援 | S1、S2、S3 |
| C. LLM 正典合併 | 模型把變體改寫成一條正典文字 | 文件最終品質最好 | 改寫非目錄原文,違反目錄類零幻覺紀律——只能在**敘述/彙整層**用+staged 審閱 | S4(訪談⑤彙整) |
| D. MMR 排序 | 不刪不併,重排讓近重複不相鄰、沉底 | 零風險、實作最小 | 沒解決「還是會看到兩條像的」 | 搜尋結果類(occupations `q=`)|
| E. 僅溯源標示 | 原樣列出+標來源職類 | 已half存在(sources) | 未收斂,choice overload 仍在 | 作為 B 的展開層 |

## 4. 兩輪研究後的共識綜合(待與維護者詳細討論)

跨標準組織(W3C、歐盟)、大廠生產系統(LinkedIn、Workday、Amazon、AWS、Informatica)、
學術(Meta SemDeDup、Peeters & Bizer EDBT、MMR 原典)、模型商(Anthropic、NVIDIA)、
UX 權威(NN/g)、本土權威(MOL)的**共識五點**:

1. **根治靠正典化**(canonical + aliases;ESCO/LinkedIn/Workday 三方一致),但那是養分類學的
   長期工程 → 我們適合「查詢時分群」起步,把人工確認過的等價對逐步固化(儲存語意用 SKOS
   exactMatch/closeMatch 兩級)。
2. **判定管線有定式**(ER/MDM):相似度打分(BGE-M3 已有)→ 灰區用更強判定器(reranker 或
   LLM——LLM zero-shot 已被學術驗證)→ match group → **survivorship 規則選代表**
   (主基準優先、次以完整度——MDM 標準做法)。
3. **分群演算法有紅線**(SKOS):近似級關係不遞移 → **不可鬆門檻連通分量**;星型(以代表
   為中心)或僅高門檻允許傳遞。
4. **呈現有大廠範本**(Amazon parent-child + NN/g):**分組+代表+變體內選+差異顯性**;
   同時 Amazon 2026 政策與 ESCO contextualisation 都警告**過度合併**——寧嚴勿鬆、非破壞、可展開。
5. **LLM 端同一份工作雙倍回報**(Anthropic context rot):grounding 清單收斂 = UX 改善 + agent
   品質改善;未來訪談引擎的彙整節點(北極星⑤)可用 LLM 當合併判定,staged 審閱把關。

**時序注意**(維護者 2026-07-02:主要架構之後會重寫):§1.3 撞碼 bug 維護者裁示**不先修、
併入重寫**;據此,dedup 能力應定位為 **api 知識/策展層的獨立服務**(重寫前後都能接),
現行 UI 是否先接一版輕量分群屬時序決策,待討論。

**明確不做**(YAGNI):索引時全域正典化(ESCO 式重建分類學——量級不符)、reranker 先不掛
(先驗 dense 夠不夠)、Qdrant payload cluster_id(等分群邏輯穩定再考慮下沉)。

## 5. 來源

- ESCO(歐盟官方):[Skills pillar](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/skills-pillar) ·
  [Skill reusability level](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/skill-reusability-level) ·
  [Skill contextualisation](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/skill-contextualisation) ·
  [Two-pillar structure](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/two-pillar-structure-esco)
- SemDeDup:[arXiv:2303.09540(Meta AI)](https://www.alphaxiv.org/overview/2303.09540v3) ·
  [NVIDIA NeMo Curator — Semantic Deduplication(產品化)](https://docs.nvidia.com/nemo/curator/curate-text/process-data/deduplication/semdedup)
- MMR:Carbonell & Goldstein 1998(原典)· [Google Cloud 官方 MMR 文件](https://docs.cloud.google.com/bigtable/docs/mmr-vector-search) ·
  [LangChain MMR 參考](https://reference.langchain.com/python/langchain-mongodb/utils/maximal_marginal_relevance)
- BGE 官方:[BGE-M3(bge-model.com)](https://bge-model.com/bge/bge_m3.html) ·
  [BAAI/bge-m3(HF)](https://huggingface.co/BAAI/bge-m3) ·
  [BAAI/bge-reranker-v2-m3(HF)](https://huggingface.co/BAAI/bge-reranker-v2-m3) ·
  [FlagEmbedding(GitHub)](https://github.com/FlagOpen/FlagEmbedding)
- Qdrant 官方:[Query point groups API](https://api.qdrant.tech/api-reference/search/query-points-groups)
- NN/g:[Choice Overload Impedes User Decision-Making](https://www.nngroup.com/videos/choice-overload/) ·
  [Explicitly State the Difference Between Options](https://www.nngroup.com/articles/explicit-differences/)
- 上下文冗餘:[AdaGReS(arXiv:2512.25052)](https://arxiv.org/pdf/2512.25052) ·
  [Anthropic — Effective context engineering for AI agents(官方)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- 大廠技能圖譜:[LinkedIn — Building and maintaining the skills taxonomy(官方工程部落格)](https://www.linkedin.com/blog/engineering/data/building-maintaining-the-skills-taxonomy-that-powers-linkedins-skills-graph) ·
  [LinkedIn — Extracting skills from content](https://engineering.linkedin.com/blog/2023/extracting-skills-from-content-to-fuel-the-linkedin-skills-graph) ·
  [Workday — The Foundation of the Workday Skills Cloud(官方)](https://blog.workday.com/en-us/foundation-workday-skills-cloud.html) ·
  [Workday Skills Cloud Datasheet(官方)](https://www.workday.com/content/dam/web/en-us/documents/datasheets/workday-skills-cloud-datasheet-enus.pdf)
- Entity Resolution / MDM:[AWS Entity Resolution(官方文件)](https://docs.aws.amazon.com/entityresolution/latest/userguide/what-is-service.html) ·
  [Informatica — What is a Golden Record(官方)](https://www.informatica.com/blogs/golden-record.html) ·
  [Peeters & Bizer — Entity Matching using LLMs(EDBT 2025)](https://openproceedings.org/2025/conf/edbt/paper-81.pdf) ·
  [Match, Compare, or Select?(arXiv:2405.16884)](https://arxiv.org/pdf/2405.16884)
- 標準:[W3C SKOS Reference(Recommendation;exactMatch/closeMatch 遞移性)](https://www.w3.org/TR/skos-reference/)
- 呈現範本:[Amazon — Product Variations Relationship User Guide(Vendor Central 官方)](https://vendorcentral.s3.amazonaws.com/Resource+Center/vendor-central/GLOBAL_Selling/Product_Variations_Relationship_User_Guide.pdf)
- 本 repo:[北極星研究 §7 MOL 指引(共通/專業職能)](2026-07-02-llm-interview-authoring-research.md) ·
  ADR 0012(embedder 服務)· ADR 0016(task-catalogs 批次)· ADR 0020(訪談互動模式)
