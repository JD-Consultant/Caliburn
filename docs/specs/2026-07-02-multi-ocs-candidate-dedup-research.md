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

## 3. 解法選項空間 × 表面適用

| 選項 | 機制 | 優 | 劣 | 適用 |
|---|---|---|---|---|
| A. 硬去重 | 相似度>門檻直接刪、留一 | 最乾淨 | 丟情境變體(§2.1 反對);門檻誤判=使用者根本看不到某選項 | 僅 exact-dup(已有)|
| B. **分群+代表+溯源** | 近重複收成一群:顯示代表項+「n 個來源」徽章,可展開看變體與出處 | 不破壞資料;差異顯性(NN/g);LLM 拿代表項省 token | 需要分群計算+UI 支援 | S1、S2、S3 |
| C. LLM 正典合併 | 模型把變體改寫成一條正典文字 | 文件最終品質最好 | 改寫非目錄原文,違反目錄類零幻覺紀律——只能在**敘述/彙整層**用+staged 審閱 | S4(訪談⑤彙整) |
| D. MMR 排序 | 不刪不併,重排讓近重複不相鄰、沉底 | 零風險、實作最小 | 沒解決「還是會看到兩條像的」 | 搜尋結果類(occupations `q=`)|
| E. 僅溯源標示 | 原樣列出+標來源職類 | 已half存在(sources) | 未收斂,choice overload 仍在 | 作為 B 的展開層 |

## 4. 建議(待討論)

**分層混和,B 為主幹、非破壞性**:

1. **先修撞碼**(§1.3,獨立 bug):grounding id 與勾選鍵改 `ocs_code::task_code` 命名空間。
2. **S1/S2/S3 共用一個「池內語意分群」服務**(api 服務層,查詢時計算):
   池項目 → embedder(BGE-M3 dense,批次一次呼叫)→ 兩兩 cosine → 門檻連通分量 →
   `[{representative, members: [{text, sources}]}]`。門檻先跑真實池的分布再定(BGE 官方做法);
   分群結果**只改呈現與 grounding,不改底層資料**(隨時可關,回滾=關開關)。
   - S1 UI:近重複任務跨組收斂成一列「代表 + 來源徽章 ×n,可展開」;勾代表=挑其中一個
     來源(預設主基準優先,可展開改選)——差異顯性化,對齊 NN/g。
   - S2:態度/職類池同機制(sources 型別已備)。
   - S3:LLM 拿分群後代表清單(帶 namespaced id),重複建議自然消失。
3. **S4 留給訪談引擎立項**(ADR 0020 的⑤彙整節點):LLM 語意合併敘述文字,staged 審閱把關
   ——與目錄類分群是兩件事,不混做。
4. **不做**(YAGNI):索引時全域正典化(ESCO 式重建分類學——量級不符)、reranker 加掛
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
- 上下文冗餘:[AdaGReS(arXiv:2512.25052)](https://arxiv.org/pdf/2512.25052)
- 本 repo:[北極星研究 §7 MOL 指引(共通/專業職能)](2026-07-02-llm-interview-authoring-research.md) ·
  ADR 0012(embedder 服務)· ADR 0016(task-catalogs 批次)· ADR 0020(訪談互動模式)
