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

## 5. 實驗(第三輪:用真實 OCS 資料驗證,2026-07-02)

- **方法**:三個會被一起選的軟體職類(SET3115-001v5 工具機軟體人機介面 / ISD2152-001v4
  半導體軟體設計 / ISD2519-002v2 軟體測試),任務層用 indexer 既有 `tasks:findSimilar`
  (Qdrant 已存 BGE-M3 dense 向量,兩兩 cosine);態度/知識/技能層抓官方 metadata 過
  embedder `/embed` 算跨職類兩兩相似度。
- **任務層(524 對 ≥0.5)**:**沒有任何 ≥0.9 的真重複**。最高帶 0.80–0.82 全是「同領域、
  不同任務」(「製作雛形開發程序與測試分析評估」vs「制定測試方法與程序」0.823);直方圖
  0.8 帶 105 對、0.7 帶 342 對——dense 把「同領域」壓在 0.7–0.85 窄帶,**單一門檻切不開
  「同任務異措辭」與「同領域異任務」**。連測試專職 vs 軟體設計的最高對也只有 0.787
  (「測試分析與設計」vs「制定測試方法與程序」——相關、不重複)。
- **態度層(119 對)**:**真重複實錘**——「主動積極」跨基準**逐字相同**(1.000;官方態度
  多出自共通職能字典)、「團隊合作 vs 團隊意識」定義全同僅標籤異(0.930),然後**斷崖**
  到 0.742(不同態度)。→ **0.9 門檻乾淨可切,dense-only 足夠**。
- **技能層(605 對)**:真近重複存在(「技術文件蒐集與閱讀分析能力 vs 技術文件閱讀與撰寫
  技能」0.790)但被**【T1.1】類註記污染**——「問題解決能力【T1.1】【T1.2】 vs 問題解決
  能力」只得 0.788,清洗註記後真重複會浮上 0.85+ 帶。→ 需前處理(strip 【】註記)再嵌入。
- **知識層(601 對)**:最高 0.702(物件導向分析知識 vs 物件導向程式設計)——多為相關而
  非重複,問題較輕。
- **附帶發現**:`header_meta` 現行 exact 去重以 code 為主鍵,但態度碼是**基準內局部碼**——
  跨基準同文異碼會漏合(實驗中 1.000 那對正是如此才雙雙出現在池裡)、同碼異文會誤併。
  現行 exact 去重本身有瑕疵。

### 5.1 補充實驗:同職位兩版本(模擬多公司/同職位重選情境,2026-07-02)

維護者指出未來會有多公司/同職位重選 → 用索引裡現成的**同職業雙版本**測(904 個職業中
~170 個家族有多代碼,其中 MQM2141-001 v2+v4、MPD2151-002 v2+v4、LPS5404-001 v1+v3 為
同職業異版本):

- MQM2141-001(品管)v2×v4:95 對 ≥0.5,**0.9+ 零對**;最高 0.806 =「負責檢驗與測試
  原物料、半製品、成品」vs「依規格檢驗原物料、半成品與成品」——**這是真重複(同任務改寫)**。
- MPD2151-002(機構設計)v2×v4:最高 0.820 =「規劃目標與建立專案」vs「確認設計需求」
  ——**這是不同任務**。
- LPS5404-001(保全)v1×v3:最高 0.872(CCTV 維護 vs CCTV 監控記錄,相關而非同一);
  任務名同樣有【註1】【註2】註記與 PDF 換行噪音 → 前處理(去註記、併空白)是全層通用需求。
- **關鍵結論:任務層的「真重複改寫」(0.806)與「同領域不同任務」(0.820)分數帶完全重疊**
  ——任何全域門檻要嘛漏掉真重複、要嘛誤殺不同任務。**任務層不可自動合併**;真重複落在
  Fellegi-Sunter 的灰區,正確處置是「標出待確認」(UI 顯差異 / 未來 LLM 判定或澄清提問),
  不是機器擅自決定。態度層(斷崖分布)不受此限,0.9 自動分組安全。
- 升級槽位:cross-encoder(bge-reranker-v2-m3,部署進既有 embedder 容器,仍是確定性元件)
  對「同一 vs 相關」的鑑別力遠高於 bi-encoder cosine,是灰區收窄的第一選項(先不做,留槽)。

## 6. 問題重構:三層資料、三種病、三種主流解法(第三輪)

實驗證實維護者最初的直覺(「不一定要用去重」):

| 層 | 病 | 主流正解 | 依據 |
|---|---|---|---|
| **任務** | 不是重複,是**相關任務對外行人難分辨**(選擇混淆) | **引導式選擇**:澄清式提問縮小範圍 + 差異顯性化;去重無藥可醫 | Baymard:product finder/guide 是「給非領域專家」的主流工具;SIGIR '19 Aliannejadi 起的 clarifying-questions 系譜(ClariQ、SIGIR '22 生成、2024 RAG 式);NN/g explicit differences;**正好就是北極星訪談②③的職責**(ADR 0020) |
| **態度**(今天就混池) | **真重複**(共通字典逐字/近字) | 高門檻(≈0.9)嵌入分群 + 代表 + 溯源;dense-only 足夠、斷崖分布安全 | 本實驗 §5;SemDeDup;survivorship(§2.6) |
| **技能/知識**(未來彙整時混) | 真近重複 + 註記噪音 | 前處理(去【】註記)後同態度機制;灰區小 | 本實驗 §5 |
| **文件層**(彙整品質) | 多來源任務各帶 K/S 進文件 → 成品重複冗長 | LLM 彙整/合併 + staged 審閱(可做成編輯器動作**與** agent 工具同源)| Peeters & Bizer(LLM 比對已驗證);Word Copilot staging(北極星研究);Anthropic context 策展 |

**設計含義**:任務層的解法**不是新功能,是訪談引擎(ADR 0020)本來就要做的事**——
候選任務落在相似窄帶時,agent 問一個鑑別性問題(「你做的是規劃測試方法,還是實際執行測試?」),
以兩任務的**差異**為 grounding;UI 同步把差異顯性化。態度/技能層的分群是**獨立的小型策展
服務**(池進、群出),重寫前後都能接。文件層 QA 是**同一能力的第三個消費者**(編輯器動作
+ agent 工具)。

## 7. 架構設計提案:統一「分帶策展」工具(第四輪,2026-07-02,待維護者拍板)

維護者方向(2026-07-02):**所有層統一一個機制**、分數分帶路由;**先不接 LLM,做成未來
訪談 LLM 的工具**。此方向與 record linkage 奠基模型 **Fellegi-Sunter(1969)三區決策**
完全同構(≥上門檻自動連結 / 兩門檻間送人工複核 / <下門檻視為不同;Splink=英國司法部
開源實作、GOV.UK 演算法透明登記在案),與 Anthropic 官方工具設計指引(「工具是**確定性
系統與非確定性 agent 之間的契約**」;consolidated、meaningful context、token-efficient)
互相印證。

### 7.1 設計

**一個確定性(LLM-free)相似度策展能力,四層(T/O·P/K·S/A)共用管線、per-kind 只差 config:**

```
items: [{id, text, kind, source}]            # kind: task|output|indicator|knowledge|skill|attitude
  → ① 前處理(全層同款):去【註*】/【T*.*】註記、併換行空白、trim
  → ② 打分:BGE-M3 dense cosine(embedder 既有;升級槽:cross-encoder reranker,仍確定性)
  → ③ 分帶(Fellegi-Sunter;per-kind {θ_high, θ_low} 為 config):
       ≥θ_high        → duplicate groups(星型聚代表,SKOS 非遞移紅線 §2.7;
                         survivorship 選代表:主基準優先→文字最完整,§2.6)
       [θ_low,θ_high) → similar_pairs(灰區:回「對+分數」,交上層處置)
       <θ_low         → distinct
  → 輸出 {groups, similar_pairs}(緊湊、可直接餵 UI 或 agent;不回原始矩陣)
```

- **實驗校準起點**(§5/§5.1;上線前按分布再校):attitudes {0.90, 0.70} · skills/knowledge
  {0.85(清洗後), 0.65} · **tasks {0.95, 0.70}**——任務層 θ_high 刻意高到幾乎只攔逐字級,
  因為實驗證明其真重複與相關任務同帶(§5.1),**灰區才是任務層的主場**。
- **落點**:泛用 `items:findSimilar`(texts 進、帶出)放 **ocs-indexer**(相似度的 bounded
  context;已有 embedder client 與 `tasks:findSimilar` 先例);契約走 `packages/indexer-contract`
  (ADR 0010)。api 端薄服務做 survivorship、文件形狀對應、供 REST 與(未來)agent tool。
  既有 `tasks:findSimilar`(Qdrant 存量向量版)保留,texts 版共用分帶邏輯。

### 7.2 消費者(現在 → 未來)

| 消費者 | 用法 | 時機 |
|---|---|---|
| 表頭態度池(header-meta) | groups 取代 exact-by-code 去重(順帶修 §5 附帶發現的 bug) | 現在即可 |
| 任務勾選(TaskCuratePanel) | similar_pairs → 相似徽章 + 差異並排(NN/g explicit differences) | 現在即可(純顯示) |
| 編輯器動作「檢查相似項目」 | 對文件現有 items 跑同 endpoint → 面板列 groups/pairs,人工處置 | 可排 |
| **訪談 agent(ADR 0020)** | 同 endpoint 做 agent tool:灰區對 → LLM 產生**鑑別提問**(clarifying questions 系譜)或彙整期合併提案(staged 審閱) | 重寫時 |
| 記憶(可選,後期) | 人工確認的等價/不等價對持久化(SKOS exactMatch/closeMatch 語意)→ 下次直接命中,越用越準 | 後期 |

### 7.2.1 維護者拍板與新增需求(2026-07-02)

- **架構方向同意**(「架構應該是你說的這樣」)。
- **語料分區**:未來公司版職說書會切進同一索引,但要**分群**——API 須支援「只搜公版 /
  只搜私版 / 都搜」(Qdrant payload 分區 + 過濾;多租戶隔離對齊 ADR 0006 精神,實作時
  另研究 Qdrant 官方 multitenancy 模式)。curation 工具的 `source` 欄位已容納公/私標記。
- **本專案核心 = 人與 LLM 共同編輯**:「主要以 LLM 為主,使用者也可自行編輯——先做工具
  就是共同編輯的意思」。共編協定(LLM 怎麼寫入、staged 提案 vs 直改、回合語意與 2a token
  的關係)是訪談引擎立項的核心設計題,**另開研究**;本工具是該體系中 LLM 的 tool 之一。
- **時序**:先把 curation 工具做成功能(LLM 一定用得到);訪談/共編設計隨後專題研究。

### 7.3 LLM 與工具的關係(回維護者問)

- **工具本體不放 LLM**:分帶是確定性契約(可測、便宜、毫秒級、離線可跑)——符合 Anthropic
  「tools = deterministic contracts」定義;LLM 是**上層消費者**(agent 拿 similar_pairs 去
  提問/提案)。
- 「工具帶 LLM 功能」不是禁忌(業界有 LLM-as-judge 工具),但對本能力:灰區的 LLM 判定
  應做成**可選批次增強**(離線/彙整時,預設關),線上路徑保持確定性。升級順位:
  前處理 → reranker(確定性)→ LLM 判定(批次)——每級先驗證是否已夠。

**「灰區用 LLM」的證據狀態(2026-07-02 查證,回維護者「是業內共識嗎?」)**:
**不是既定共識,是「新興且有據的實踐」**。分帶三區是共識(FS 1969 至今);灰區送「人」
複核是經典共識;灰區給 LLM 的現狀——(a) **官方統計界研究中**:ISI 提出 LLM-assisted
record linkage 框架(LLM 判模糊對 + Bayesian 與先驗融合 + **人工抽驗兜底不可省**);
(b) **ER 龍頭 Senzing 的定位**:LLM 不宜當主比對器(一致性/可解釋性/成本 100–1000× 六維
限制),適位角色之一是「**取代 edge-case 複核中的人**」;(c) 學術驗證強(Peeters & Bizer)。
→ 一句話:LLM 判灰區「有據可循、方向正確、尚未共識、必須帶評估與人工兜底」。
**本設計不賭它**:v1 灰區→人(UI 顯差異=產品化 clerical review);訪談情境→LLM 只是
「幫忙問問題」的角色,最終判斷者是員工本人(比 clerical review 更好——問到唯一知道
真相的人);LLM 批次判定=後期可選、評估把關。

### 7.4 v1 設計細節(2026-07-02 定,維護者授權命名重設計)

- **D1 命名**:`POST /items:match`(取代草案 findSimilar)——對齊 ER/FS 標準詞彙
  (AWS「matching workflow」、Splink、FS 三區即 match / possible match / non-match),
  回應欄位與理論端到端同名。既有 `tasks:findSimilar`(Qdrant 存量向量特化版,零消費者)
  暫保留,分帶邏輯穩定後再評估統一。
- **D2 Request**:`{kind, items: [{id, text, source?}], config?: {theta_high?, theta_low?}}`
  ——池同質故 kind 放 request 層;config 覆寫僅供校準實驗,線上走 server 端 per-kind 預設。
- **D3 Response**:`{groups: [{medoid, members: [{id, score}]}], possible_matches: [{a, b,
  score}], config: {kind, theta_high, theta_low, model}}`——distinct 隱含不回傳(token
  效率,Anthropic 工具指引);回 config 供重現(對齊 ADR 0009 版本紀律)。
- **D4 前處理**:去【…】註記、併換行/連續空白、trim;完全同字先收斂(免嵌入)。NFKC 不做。
- **D5 分群**:θ_high 邊按分數降序**貪婪星型**——雙方皆未入群→開新群;一方在群→僅當
  「與該群中心分數 ≥θ_high」才併入(**成員與中心直連是硬條件**,SKOS 非遞移紅線 §2.7)。
- **D6 兩種「代表」分離**:indexer 回 **medoid**(幾何中心,與群內平均相似度最高);
  **survivorship(顯示代表:主基準優先→文字最完整)在 api 層**(領域知識歸 api)。
- **D7 門檻**:indexer settings per-kind 預設(att 0.90/0.70 · k/s 0.85/0.65 · task
  0.95/0.70);**校準腳本進 repo**,用真實共選組合輸出分布與建議值;改門檻=config change
  +校準紀錄。
- **D8 上限**:items ≤500/call(超回 413);O(n²) 毫秒級;embedder 單次批呼。
- **D9** dense-only;sparse 混合與 reranker 留槽(§5.1)。
- **D10 api 接法(additive、零破壞)**:header-meta 增 `attitude_groups`(平面 `attitudes`
  保留);match 呼叫失敗→池原樣+`meta.partial`(enrichment 語意,ADR 0018)。
- **D11** task-candidates 增 `similar_pairs`(跨組灰區對),同 enrichment 語意。
- **D12 版本一致性**:inline 嵌入 fresh-vs-fresh 自洽,無 manifest 相容問題;存量向量路徑
  (tasks:findSimilar)既有 manifest 檢查不動。

### 7.5 前置發現:來源資料的代碼污染是系統性問題(2026-07-02 全量掃描)

維護者指示「先處理 api/web 顯示:候選文字不帶代碼、代碼顯示在引用、文件內部 OPKSA 代碼照舊」。
全量掃描 908 份來源 JSON 的量化結果:

| 污染類型 | 規模 | 性質 |
|---|---|---|
| K/S/O name 內嵌【T*】適用性標記 | **113 檔 / 335 項** | **不是垃圾,是資料**——多任務共用 block(§6.3 的 0.6% 案例)裡「這條 K 適用哪個任務」的標記;應**剝離成結構化欄位**(如 `applies_to`)而非丟棄 |
| 任務名吞入 PDF 表格殘片(如「確認顧客或市場需求T1.1.1確認客戶需求T1.1.2…」) | **88 筆** | **pdf-to-json 解析缺陷**(子任務版面未處理);ingest 層無法真正修,需回 parser(另一 bounded context,golden 紀律,獨立排程) |
| CJK 詞中斷行空白(「能 力」「特性需求 」) | **6,493 項** | PDF 換行 artifact,ingest 層可修 |
| 任務名【註N】腳註標記 | **69 筆** | 對應 `notes` 欄位;ingest 層可剝離 |

**污染同時傷顯示與 embedding**(§5 實驗:同名技能因【T*】只得 0.788)。

**2026-07-03 澄清(維護者)**:「代碼與名稱分離」(K01/T1.1 等目錄代碼不混進候選文字、
另作引用顯示)**已經做好、已上線,不用動**——`task_detail.py::task_competencies` 回
`{code, name}` 分離欄位、`CellFillerPanel.withSrc` 把 `code` 包進 `srcs` 引用物件、
`FieldCombobox` 用 `name` 顯示候選文字。**著作文件內部的 OPKSA 代碼(ocs-schema,可自訂
順序)也本來就完整保留、不受影響**——那是另一套代碼空間(著作文件自己的),與來源代碼
無關。以上兩點是既有正確設計,以下只針對**內嵌在 `name` 文字裡的【T1.1】標記**(與代碼
欄位分離無關的另一個問題)。

**追加查證(2026-07-03,逐層追到 Qdrant 攝入):是否冗餘?——實測結果是「不冗餘、且現有
`sources` 結構丟失了它」**。追蹤 `apps/ocs-indexer/src/jd_ocs_indexer/ingestion/builder.py`
(docstring:「`task` record **per task_code**,攜帶該任務群組**整組** competency_blocks」)
+ `api/service.py::get_competencies`:同一 block 若 `task_codes=[T1.1..T1.5]`(§6.3 的
0.6% 多任務共用案例),indexer **展開成 5 個獨立 Qdrant task point**、**每個各自攜帶整組
K/S/O 清單的完整複本**;`get_competencies` 逐 point 收集、依 `(ocs_code, type, code)` 去重
合併 `sources`。**實測**(工具機軟體人機介面工程師,T1.1–T1.5 共用一 block):K01 的
name 標【T1.1】,但因所在 block 的 task_codes 涵蓋 T1.1–T1.5,K01 最終合併出的
`sources` 會是 **[T1.1,T1.2,T1.3,T1.4,T1.5] 全五個**——**跟 K15(標【T1.1~T1.6全部】,
真的適用全部)混不出差別**。→ **`sources` 現況只到「block 群組」精度,【T1.1】文字
標記帶的是「群組內哪一項該精確歸哪個/哪些任務」——這一層目前無處存放,唯一存在的地方
就是這段文字**。故非冗餘;應解析進結構化欄位(暫名 `applies_to: [task_code]`,精度細於
現有 `sources`),而不是丟棄。→ 修層決策:

1. **indexer ingest 清洗 + 結構化(Task 0)**:normalize/攝入時,把【T*】解析進新結構化
   欄位(細粒度,獨立於現有 block 級 `sources`),同時把【T*】/【註N】文字與詞中空白/
   換行從 `name` 剝除;**re-index 一次**(既有指令)。顯示與向量同時變乾淨,細粒度任務
   歸屬資料被保留而非丟失。
2. **api/web 顯示**:不需改動(既有分離設計已正確);清洗後 `name` 本身變乾淨,顯示層
   零改動即受益。
3. **pdf-to-json 修 88 筆吞名 bug**:獨立 plan(re-parse + re-index),不擋 Task 0。
4. match 工具的 D4 前處理降級為**防禦性**(同規則、冪等)——源頭乾淨後它只是保險。

### 7.5.1 維護者定調(2026-07-03):dedup 只需 name,不處理 T 標記,兩件事解耦

維護者釐清:**dedup(items:match)只需要乾淨的 `name`**。【T*】是「來源/引用」(provenance),
對「兩個 K/S 名稱算不算近重複」毫無作用——「問題解決能力」vs「問題解決能力」重不重複,
跟它們各自被哪個任務引用無關。故 dedup 工具 = **拿 name → 剝【T*】/【註N】→ 比對**,
**不解析、不結構化** T 標記。

由此把上面 §7.5 的兩件事**明確解耦**(先前把它們混在一起是過度耦合):

- **Concern D(dedup,本工具)**:唯一需求 = 乾淨 `name`。**在讀取當下**(D4 前處理)剝標記
  取 name 即可,來源【T*】原樣保留當引用。→ **dedup 功能零 ingest / 零 re-index 改動**;
  items:match 輸入乾脆為 `{id, text=name, kind, source=ocs_code}`。
- **Concern A(逐任務 K/S 歸屬,如工具機五分特例)**:上面「【T*】非冗餘、應結構化成
  `applies_to`」的分析**只對這件事成立**——它是顯示 / 資料品質的**獨立議題**,**不在 dedup
  關鍵路徑上**。dedup 不必等它、不擁有它;要不要做、何時做,與 dedup 無依賴。
- 故 §7.5 的「修層決策 1」(ingest 清洗 + 結構化 Task 0)**不再是 dedup 的前置**:dedup 直接
  用讀取時 D4;Concern A 的 ingest 清洗/結構化(以及 88 筆吞名 parser bug)各自獨立排程。

## 8. 來源

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
- Fellegi-Sunter / 三區決策:[Splink — The Fellegi-Sunter Model(英國司法部官方文件)](https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html) ·
  [GOV.UK — MoJ Data First (Splink) 演算法透明紀錄](https://www.gov.uk/algorithmic-transparency-records/moj-data-first-splink) ·
  [Winkler — Machine Learning and Record Linkage(美國普查局)](https://isi-web.org/sites/default/files/import/files-2011/450070.pdf)
- Agent 工具設計:[Anthropic — Writing effective tools for agents(官方)](https://www.anthropic.com/engineering/writing-tools-for-agents)
- 灰區 LLM 證據狀態:[ISI — LLM-Assisted Record Linkage: Framework for Official Statistics(官方統計界)](https://www.isi-next.org/abstracts/submission/3897/view/) ·
  [Senzing — Future of Entity Resolution in the Age of Generative AI(ER 龍頭)](https://senzing.com/entity-resolution-generative-ai/)
- 引導式選擇(任務層):[Baymard — Product Lists & Thematic Browsing/Finders(電商 UX 權威)](https://baymard.com/research/ecommerce-product-lists) ·
  Aliannejadi et al. — Asking Clarifying Questions in Open-Domain Information-Seeking Conversations(SIGIR '19,奠基作)·
  [ClariQ(EMNLP 2020 SCAI 挑戰)](https://github.com/aliannejadi/ClariQ) ·
  [Generating Clarifying Questions with Web Search Results(SIGIR '22)](https://dl.acm.org/doi/10.1145/3477495.3531981) ·
  [Corpus-informed RAG of Clarifying Questions(arXiv:2409.18575)](https://arxiv.org/pdf/2409.18575) ·
  [Users Meet Clarifying Questions(ACM TOIS)](https://dl.acm.org/doi/10.1145/3524110)
- 本 repo:[北極星研究 §7 MOL 指引(共通/專業職能)](2026-07-02-llm-interview-authoring-research.md) ·
  ADR 0012(embedder 服務)· ADR 0016(task-catalogs 批次)· ADR 0020(訪談互動模式)

## 9. 第五輪(2026-07-04):v1 立項研究——查證、兩個實驗、與知識包整合設計

> 脈絡:維護者定調「工具先行、LLM 後接、SaaS 暫緩」;中文正式名稱定案**「相似比對」**
> (similarity matching;「去重」為棄用暫名——本工具不刪任何項目)。本輪關閉 §7.4 之後
> 所有殘餘開放問題;產出正式設計 spec
> [`2026-07-04-similarity-matching-v1-spec.md`](2026-07-04-similarity-matching-v1-spec.md) 與 ADR 0022。

### 9.1 查證 B——SemDeDup/NeMo 的代表選法是**反面教材**(反而驗證 D6)

[NeMo Curator 官方文件](https://docs.nvidia.com/nemo-framework/user-guide/24.09/datacuration/semdedup.html):
SemDeDup 在重複群裡保留「與群中心 cosine **最低**」(=離中心最遠)的點——因為其目標是
**訓練資料多樣性最大化**(刪重複時留最邊緣的點保資訊量)。我們的目標相反(給人看的可讀代表),
故 D6 的 medoid(幾何,indexer)+ survivorship(顯示,web;見 9.5)不抄它,且有了明確理由。
NeMo 示例 eps 0.01–0.001(≈cosine 0.99+)極端嚴格,與「寧嚴勿鬆」(§2.1/§2.8)三方互證。
工程補充:貪婪星型須**決定論**——pair 按(分數降序、id 升序)排序處理,tie-break 固定。

### 9.2 查證 C——reranker 可行性 + **實測鑑別力**(升級槽從假設變已驗證)

- 資源:bge-reranker-v2-m3 約 4GB VRAM、單批 ~240ms([HF 討論](https://huggingface.co/BAAI/bge-reranker-v2-m3/discussions/39)、
  [TEI 部署實測](https://www.spheron.network/blog/self-host-embedding-reranker-tei-gpu-cloud/));
  RTX 4060(8GB)與 BGE-M3 同容器共存**實跑成功**,權重已入 hf_cache volume。
- **鑑別力實測**(20 對人工標註的灰區對,embedder 容器內跑,批次 6.5s 含暖機):
  - **底部大掃除**(真正強項):dense 因各向異性膨脹的假相似被壓到近零——
    「檢驗分析能力↔統計分析能力」0.834→**0.276**、「風險分析↔統計分析」0.808→**0.156**、
    「協助推廣品質觀念↔協助供應商完成品質管理」0.792→**0.193**。
  - **頂部確認**:四對真重複全 ≥0.996。
  - **中段誠實失敗**:「製程品質巡檢↔製程品質控管」(一字差、實為兩事)得 **0.988**——
    表面重疊高、語意有別的任務名,cross-encoder 一樣被騙。
- **結論**:reranker 的正確角色 = **灰區的過濾器與排序器**,永遠不是合併裁決者
  (§5.1「任務層不可自動合併」對它同樣成立)。**v1 不部署**(D9 維持);觸發條件白紙黑字:
  **K/S 混池表面上線前必開**(見 9.4 skill 層爆炸),或校準顯示徽章噪音過高。

### 9.3 查證 D——窄帶是各向異性的教科書症狀;校準方法論修正

§5 觀察到的 0.7–0.85 窄帶 = 嵌入**各向異性**(向量擠在窄錐、絕對 cosine 系統性偏高)的已知
現象(原典 [Li et al., EMNLP 2020](https://arxiv.org/pdf/2011.05864);2026 綜述
[arXiv:2504.16318](https://arxiv.org/html/2504.16318v2))。推論:(1) **絕對門檻跨模型/資料
不可移植**——文獻門檻數字零參考價值,D7「用自己的池校準」是唯一正解且獲理論背書;
(2) 排序不變、絕對值失真 → **校準腳本主產出 = 分布 + 斷崖位置**(門檻定在崖中間),
不是套慣例數字。mean-centering/whitening 對數十~數百項的池過重,不做(未來縫,一行註記)。
來源衛生:搜尋另撈到單作者未審 preprint(arXiv:2601.16907,被標記文字重疊)——**棄用**,
結論全部改錨同儕審原典。

### 9.4 實驗 A——灰區體積(三組真實組合 × 四 kind,完整管線)

方法:真實共選組合(§5 軟體三職類 / 品管三職類 MQM2141-001v4+008v1+005v2 / 同職雙版本
001v2×v4),完整管線(前處理→NFKC exact-collapse→嵌入→跨來源兩兩 cosine→分帶)。
結果(自動群對/灰區對,D7 起點門檻):

| 組合 | attitude | knowledge | skill | task(θ_low=0.70) |
|---|---|---|---|---|
| 軟體三職類 | 1 / 5 | 0 / 7 | 1 / **116** | 0 / **24** |
| 品管三職類 | 1 / 2 | 0 / 6 | 2 / **186** | 1 / **39** |
| 同職雙版本 | 0 / 0 | 0 / 1 | 3 / 67 | 0 / 3 |

1. **態度層定案 {0.90, 0.70}**:斷崖第三次驗證(0.986 dup → 下一名 0.72),灰區 0–5 對。
2. **任務層 θ_low 翻案 0.70→0.80**:0.7 帶塞 112 對(全是同領域不同任務),0.70 起算灰區
   24–39 對 = 徽章噪音(choice overload 換位爆);真重複全在 0.83+(0.966/0.868/0.846),
   提到 0.80 後灰區 5–10 對、真重複零漏。**任務層定案 {0.95, 0.80}**。
3. **前處理是精度工程**:§5.1 真重複對(依規格檢驗原物料…)未清洗 0.806 → 清洗後 **0.868**。
4. **exact-collapse 升為必要步驟**:knowledge 175→46、skill 209→48(同基準 K/S 跨 block
   重複),嵌入呼叫省 ~70%。
5. **skill 層灰區爆炸**(116–186 對;「○○能力」句式擠在 0.7 帶):v1 無感(K/S 池不混),
   但成為 reranker 的明確觸發條件(9.2)。

### 9.5 與知識包整合的設計定案(讀碼修正兩處)

讀 [`knowledge_pack.py`](../../apps/api/app/core/domain/knowledge_pack.py) /
[`documents.py::get_knowledge_pack`](../../apps/api/app/api/routes/documents.py) /
[`pack.ts`](../../apps/web/src/lib/pack.ts) 後定案:

1. **輸入 = pack 池 rows**(ADR 0021 已按 kind 分 12 池、key 去重、srcs 累積)——工具零抽取;
   indexer 端 exact-collapse 降級為防禦性(只補 NFKC 級漏網)。
2. **修正一(過時結論)**:§5 附帶發現的「態度 exact-by-code 漏合」是舊 header_meta 的 bug,
   pack 態度池已改 **name key**(同文跨基準已合併);本工具對態度池的增量 = **近重複**層。
3. **「同基準不比」泛化**:pack row 的 srcs 跨來源合併過 → **來源集合不相交才比對**
   (共同基準的編輯意圖 = 刻意分開)。
4. **修正二(D6 半翻案)**:survivorship **從 api 移到 web**——「主基準是誰」是文件層、
   render 時才知道的狀態(`clearPrimaryBasis` 可隨時清),api 組 pack 時不知道;
   pack.ts 本就是「唯一的 pack 讀取邏輯集中點、全純函式」(vitest 模式現成)。
   indexer 回 medoid(幾何)不變。
5. **api = 純搬運**(enrichment):build_pack 後對態度/任務池各打一通 items:match(並行),
   原樣掛 `pack.similarity`(optional);失敗不掛,web 行為與現狀逐位元相同(ADR 0018 語意)。
6. **自動勾選交互——一條規則消滅整族 bug**:選擇邏輯(primaryDefaults/首開自動套/勾選
   狀態/寫入身分)**全跑在平的成員選項上,一行不改;分群只是 render 最後一步的顯示變換**。
   兩個湧現不變量:(A) 來源不相交規則 ⇒ 一群內每基準最多一條 ⇒ 自動勾選不可能勾雙;
   (B) survivorship 主基準優先 ⇒ 主基準成員在群內必為代表 ⇒ 勾代表=勾對身分。
   收合列**就是代表成員本人**(群無可選身分;文件永遠只出現成員真身)。
7. **v1 範圍**:indexer `POST /items:match` + 校準腳本(units 一起跑但不接線)+ api 搬運 +
   web 態度池收合與任務相似徽章。契約沿用 `packages/indexer-contract`
   (contract-strategy rubric row 3:internal、all-Python、單一 in-repo 消費者)。

### 9.6 本輪新增來源

[NeMo Curator SemDeDup(NVIDIA 官方)](https://docs.nvidia.com/nemo-framework/user-guide/24.09/datacuration/semdedup.html) ·
[Li et al. — On the Sentence Embeddings from Pre-trained Language Models(EMNLP 2020,原典)](https://arxiv.org/pdf/2011.05864) ·
[Semantics at an Angle(2026 綜述)](https://arxiv.org/html/2504.16318v2) ·
[bge-reranker-v2-m3 GPU 需求(HF 官方討論)](https://huggingface.co/BAAI/bge-reranker-v2-m3/discussions/39) ·
[TEI self-host 實測(2026)](https://www.spheron.network/blog/self-host-embedding-reranker-tei-gpu-cloud/)。
實驗腳本:scratchpad `grayzone_experiment.py` / `rerank_test.py`(校準腳本雛形,實作時進 repo)。
