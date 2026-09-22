# 2025–2026 提升 LLM 生成品質技術調查

> 調查對象:一個「AI 訪談引導 + 專業職務說明書生成」系統(品質至上、要達人類顧問等級)。
> 已有基礎:自建 agent loop、strict structured outputs、quote 溯源、確定性守門、規劃中 golden-set evals、多模型 API 路由。
> 本報告只評估「還能用什麼技術把品質再往上推」。純技術調查。
> 日期基準:2026-07。每條標來源 URL + 發布日期。

---

## 判定總覽(先看這個)

| # | 技術 | 判定 | 一句理由 |
|---|------|------|---------|
| 1 | Test-time compute / reasoning models | **建議用(已在用要調對)** | 顧問判斷=多步推理+歧義處理,正是官方點名該花推理 token 的任務;用 effort/thinking 分級 + 路由 |
| 2 | Best-of-N / verifier 重排 | **可試(針對關鍵段落)** | 品質提升確實,但成本 N 倍;verifier 要用 rubric-based、避免同源自我偏袒 |
| 3 | Self-refine / reflection 迴圈 | **有條件建議用** | 純內在自我修正在「封閉推理」無效(已成定論);但你有 golden rubric=外部訊號,refine 就有效 |
| 4 | Few-shot with golden examples | **建議用** | 黃金範本正是官方最推薦的 steering 手段;3–5 個、多樣、標籤化 |
| 5 | Fine-tuning / distillation | **暫不用(先窮盡 prompt+eval)** | 官方共識:語氣/格式先靠 prompt;知識靠 RAG;<100 樣本別 fine-tune。你尚未有 evals |
| 6 | Prompt caching | **建議用** | 同一大 context 反覆多輪=快取的最佳場景;省 latency + ~90% cached 成本,零品質風險 |
| 7 | Synthetic data / eval 生成 | **可試(僅補 eval,不取代真人)** | 用來 bootstrap golden-set 缺口;但要防 model collapse 與 judge 同源偏袒 |
| 8 | Streaming + partial structured outputs | **建議用(UX,非品質)** | 對長文件生成的體感關鍵;SDK 已原生支援;不改變輸出品質本身 |

---

## 1. Test-time compute / Reasoning models

### 白話
讓模型在回答前先「想更久」——花額外的推理 token(chain-of-thought / thinking)去規劃、驗證、探索多種解法,再輸出。代表:OpenAI o-series、Claude extended/adaptive thinking、DeepSeek R1。可用 `effort`(low/medium/high/xhigh/max)或 thinking 開關來調深度。

### 官方證據
- **OpenAI(官方 API 文件)**:reasoning models「excel at complex problem-solving requiring deep analysis... strategic planning and decision-making」,並明列適用任務:**ambiguous information navigation、complex document analysis(reason across hundreds of pages)、multi-step agentic planning、response evaluation(benchmarking other model outputs)、code review**。關鍵指引:「most AI workflows will use a combination of both models—o-series for agentic planning and decision-making, GPT series for task execution」。prompting 建議:「keep prompts simple and direct」「avoid 'think step by step'」「start with zero-shot before few-shot」。effort 分級:「medium takes ~3x longer than low, high ~3x longer than medium... for straightforward questions, medium often performs just as well」。來源:https://developers.openai.com/api/docs/guides/reasoning-best-practices(2025,持續更新)
- **Anthropic(官方)**:「Extended thinking shows dramatic improvements on mathematics... Claude scoring over 60% on AIME 2025 vs 16% without it — nearly a 4x improvement」;「Use adaptive thinking for workloads that require agentic behavior such as multi-step tool use, complex coding, and long-horizon agent loops」;「Extended thinking adds latency and should only be used when it will meaningfully improve answer quality — typically for problems that require multi-step reasoning」。來源:https://platform.claude.com/docs/en/build-with-claude/extended-thinking(2025)。Anthropic 現行 API(claude-api skill,cached 2026-06):adaptive thinking(`thinking:{type:"adaptive"}`)+ `output_config.effort`,`budget_tokens` 已在 Opus 4.7/4.8、Sonnet 5 移除。
- **DeepSeek R1(Nature 同行審查論文)**:純 RL(GRPO,rule-based rewards)即可誘發推理,無需人工標註推理軌跡;**湧現出 self-reflection、verification、dynamic strategy adaptation**;AIME 2024 pass@1 由 15.6% → 71.0%,majority voting 再到 86.7%。來源:Nature 645, 633–638 (2025-09),DOI 10.1038/s41586-025-09422-z;arXiv:2501.12948(2025-01)。
- **Snell et al.(UC Berkeley + Google DeepMind)**:compute-optimal test-time scaling 下,**小模型可勝過 14× 大的模型**,達 4× 效率;應「按題目難度自適應分配 inference 計算」。來源:arXiv:2408.03314(2024-08)。

### 適用時機
- 需要「顧問級判斷」的步驟:從零散/歧義訪談資料推斷職責、跨段落綜合、草擬需要權衡的內容、驗證自己的輸出、評分其他模型輸出(正是官方點名的 use cases)。
- 路由判準(官方精神):**規劃/判斷/評估用 reasoning;純執行/抽取/格式化用便宜快模型**。你的系統天然是混合:訪談引導與 JD 起草走高 effort,欄位抽取/格式化走低 effort 或非推理模型。

### 成本 / 代價
- token 2–10×、latency +5–30 秒(Anthropic 官方數字);o-series high effort ≈ 3× medium ≈ 9× low。
- 過高 effort 會 overthinking / 過度探索(Anthropic 4.6+ 明列此壞味道),不見得更好。
- 對 reasoning models 別再塞「think step by step」與過多 few-shot——會反效果(OpenAI 官方)。

### 不該用
- 直白抽取、簡單 Q&A、格式化、快取命中即可的查詢——多花 token 無品質回報。
- 延遲敏感的互動回合(訪談即時往返)不要一律 high effort。

### 對「品質至上文件生成系統」的判定:**建議用(且要調對分級)**
顧問判斷=多步推理+歧義綜合,是官方與論文一致點名「值得花推理 token」的任務類型。你已多模型路由,關鍵是把 effort/thinking 綁到「步驟性質」而非全域開高:起草/綜合/自評走 high,抽取/格式化走 low。

---

## 2. Best-of-N / Self-consistency / Verifier 重排

### 白話
同一 prompt 生成多個候選(N 個),再挑最好的一個。挑法有三類:(a) self-consistency——多數決(適合有單一正解的推理);(b) verifier / reward model 重排——用一個評分模型(Outcome RM 或 Process RM)排序;(c) LLM-as-judge——用模型當裁判 pairwise/rubric 評分。

### 官方證據
- **Self-consistency(原論文)**:聚合多個推理路徑取最一致的答案,顯著優於單次輸出;「reaches quality improvement without any additional models or supervision」。(Wang et al. 原始 self-consistency;見 freeCodeCamp/論文整理)
- **Test-time verification 有效**:「Sample, Scrutinize and Scale: Effective Inference-Time Search by Scaling Verification」——擴大驗證(verification)是有效的 inference-time search。arXiv:2502.01839(2025)。
- **Verifier 的代價與偏袒風險(官方/論文警示)**:「reward models tend to be task-specific and highly sensitive to the base model, and training them is computationally expensive, often requiring a similar number of parameters as the generating models」。無訓練替代:self-certainty(用模型自身 logits 機率分布估品質,免外部 RM)——「Scalable Best-of-N Selection via Self-Certainty」arXiv:2502.18581(2025-02)。
- **Judge 同源偏袒(實證)**:LLM-as-judge「documented bias toward models with similar training — GPT-5 tends to prefer GPT-5-style outputs」。來源:synthetic-data 綜述(digitalapplied,2026)。**=> verifier / judge 不要用與生成同一模型同一家。**

### 適用時機
- 針對「最關鍵、錯了代價高」的段落(如整份 JD 的核心職責摘要),而非全文每段都 N 倍。
- 你已有 strict structured outputs + 確定性守門:可先用確定性規則過濾明顯不合格候選,再讓 judge 只在剩下的少數間挑——省成本又降 judge 負擔。

### 成本 / 代價
- 生成成本 ≈ N×;若再加 verifier 推理,還要 +1 次評分成本。
- verifier 建置難、易偏袒;self-consistency 只適合「有可聚合正解」的子問題(職責條目數、必要證照有無等),不適合開放式散文。

### 不該用
- 全文長散文逐段 Best-of-N——成本爆炸、且散文無「單一正解」可多數決。
- 用同一模型同家當 judge 評自家輸出(自我偏袒)。
- 已被確定性守門 100% 涵蓋的維度(如 schema 合規),不需要再 N 選一。

### 判定:**可試(限關鍵段落 + 跨家 verifier)**
品質提升是真的,但成本 N 倍。務實作法:只對「高價值/高風險」段落開 Best-of-N;verifier 用 **rubric-based、且不同模型家族**(避免同源偏袒);能用確定性規則先篩就先篩。這與你規劃中的 golden-set evals 天然銜接(rubric 共用)。

---

## 3. Self-refine / Reflection 迴圈

### 白話
讓模型自我批評、再據批評改寫,反覆數輪(generate → self-feedback → refine)。

### 官方證據(重點:2024–2026 已有明確定論)
- **有效的一面(生成/主觀任務)**:Self-Refine(Madaan et al., NeurIPS 2023)——同一模型當生成者+回饋者+改寫者,免額外訓練,跨 7 任務(對話生成、數學等)**平均 +20%**,人類與自動指標都偏好。「for sufficiently powerful models... easier to identify and fix errors than to produce a perfect solution in one attempt」。來源:NeurIPS 2023 proceedings。
- **無效的一面(封閉推理、無外部訊號)——這是最新定論**:Huang et al.「Large Language Models Cannot Self-Correct Reasoning Yet」(ICLR 2024,arXiv:2310.01798)——**intrinsic self-correction(僅靠模型自身、無外部回饋)在推理任務上,模型難以自我修正,有時表現反而下降**。「High-quality external feedback is often unavailable in many real-world applications」。
- **後續綜述共識(2024–2025)**:「without external feedback, LLMs rarely fix their own errors」;「the current generation of LLMs can only reliably correct their responses if given access to external techniques」。來源:When Can LLMs Actually Correct Their Own Mistakes?(critical survey, 2024);Self-Correction Bench arXiv:2507.02778。

**綜合定論**:self-refine 的成敗取決於「有沒有外部訊號」。散文/主觀品質(可用明確 rubric 批評)→ 有效;封閉推理(對就對、錯就錯,無 oracle)→ 無效甚至有害。

### 適用時機
- **你有 golden rubric = 就有了外部訊號**。把 refine 迴圈綁到 rubric:第一版 → 用 rubric 逐條批評(最好由不同模型或帶 rubric 的 grader 做,而非裸自評)→ 據批評改寫。這正是「有外部訊號的 refine」,落在有效區間。
- 對職務說明書這種「有專業寫作標準」的可評判文件特別合適。

### 成本 / 代價
- 每輪 ≈ 1 次生成 + 1 次批評 + 1 次改寫 ≈ 3× token;多輪疊加。
- 裸自評(無 rubric、同模型)可能 no-op 或退步——要避免。

### 不該用
- 純內在自評、無 rubric/無外部訊號的封閉判斷(如「這個證照要求對不對」)——已證無效。
- 無限迴圈:設 max_iterations(2–3 輪通常收斂),否則燒 token 且可能 drift。

### 判定:**有條件建議用(rubric-grounded refine)**
關鍵區分:**裸 reflection 不用;rubric-grounded 的 refine 建議用**。你規劃中的 golden-set/rubric 正好把 refine 從「無效區」推進「有效區」。實作等同 Anthropic Managed Agents 的 Outcome(define rubric → iterate → grade → revise)模式。

---

## 4. Few-shot with Golden Examples

### 白話
把黃金範本(理想的訪談片段→JD 輸出)當 in-context 範例塞進 prompt,讓模型照著學格式、語氣、結構。

### 官方證據
- **Anthropic(官方)**:「A few well-crafted examples improve accuracy and consistency」;建議 **3–5 個相關、多樣、標籤化(`<example>`/`<examples>` 包裹)** 的範例;「examples should mirror your actual use case closely and cover edge cases while varying enough that Claude doesn't pick up unintended patterns」;警示「if your few-shot examples contain errors or unwanted style, the model will learn those」。來源:https://platform.claude.com/docs/en/build-with-claude/prompt-engineering(2025)。
- **OpenAI(官方)**:「start zero-shot and move to few-shot when needed」;對 reasoning models 尤其要「start with zero-shot before few-shot」(few-shot 有時反而拖累 o-series)。來源:OpenAI reasoning best-practices(2025)。
- **與 fine-tune 的取捨(官方共識)**:「Skip fine-tuning if... the failure is wrong tone (try prompting)」;「Most 'I need fine-tuning' requests turn into 'I need an eval harness and a better prompt' once measured」。來源:OpenAI fine-tuning 指引整理(2026)。

### 適用時機
- 你的黃金範本就是「北極星尺」——用 2–5 份最能代表顧問等級的 JD(對應其訪談輸入)當 few-shot,是最低成本、最直接的品質拉升。
- 選例原則:涵蓋不同職類/難度、涵蓋 edge case、每份都是真正達標的範本(有瑕疵的別放)。

### 成本 / 代價
- 吃 context 長度(範本越長越貴);但可用 prompt caching 把這段固定前綴快取掉(見 #6),邊際成本趨近零。
- 範例選錯/含壞味道會「教壞」模型;過度集中單一情境會誘發過擬合式模仿。
- reasoning models 上 few-shot 收益遞減甚至負向,需 A/B。

### 不該用
- 已有黃金範本但只放 1 份且高度同質——模型會過度模仿該份的表面特徵。
- o-series high effort 且 zero-shot 已達標時,硬加 few-shot。

### 判定:**建議用(首選、低成本)**
官方雙方一致:黃金範例是最可靠的 steering 手段,且明確優先於 fine-tune 來處理語氣/格式。配合 prompt caching,把 3–5 份黃金範本固定成快取前綴,幾乎零邊際成本地持續拉升一致性。

---

## 5. Fine-tuning / Distillation(2026 時機)

### 白話
用你的資料改模型權重:SFT(示範理想輸出)、DPO(給偏好對:好/壞各一)、RFT(可驗證正解任務上做 RL);Distillation=用強模型輸出當訓練資料餵便宜模型。

### 官方證據
- **OpenAI(官方 API 文件)**:三法分工——「**SFT** for behaviors you can demonstrate;**DPO** when you can rank pairs but not write the perfect answer;**RFT** for verifiable-correct tasks on reasoning models」。RFT 要件:「the task must be clear and have verifiable answers」+ solid grader,甜蜜點是「narrow technical domains (math, code, medical) where correctness isn't negotiable and you've already maxed out prompting and standard fine-tuning」。來源:https://developers.openai.com/api/docs/guides/reinforcement-fine-tuning、rft-use-cases(2025–2026)。
- **何時「不要」fine-tune(官方)**:「Skip fine-tuning if the task is fact retrieval (use RAG), the failure is wrong tone (try prompting), or your eval set has fewer than ~100 examples (collect more data first)」。SFT 用量:「50 to a few thousand examples」,signal 是「match this style/format/domain language」。
- **Distillation 版權/條款注意**:蒸餾要用官方支援管道(如 OpenAI model distillation / stored completions),並注意**各家服務條款對「用其輸出訓練競品模型」的限制**——用 A 家輸出訓練會與 A 競爭的模型,通常違反 A 的 ToS(這是 2025 業界反覆出現的合規雷點)。用同家的官方 distillation 產品線則被允許。
- **語氣 vs 知識(官方判準)**:語氣/格式→prompt 或 SFT;事實/知識→RAG,不要 fine-tune(會 hallucinate、且知識易過期)。

### 適用時機
- **現在還不是時候**:你尚無 golden-set evals(<100 樣本官方明說別 fine-tune),且品質問題多屬「語氣/格式/判斷」——prompt + few-shot + rubric-refine 應先窮盡。
- **未來時機**:當(a)已有穩定 eval harness + 數百份標註 JD;(b)prompt 已到極限但仍差「最後幾個百分點」的一致性/語氣;(c)想把大模型的顧問判斷蒸餾到便宜模型以降本——此時 SFT(語氣/格式一致性)或 distillation(降本)才划算。

### 成本 / 代價
- 資料標註 + 訓練 + 維運成本高;模型版本綁定(換底模要重訓)。
- 過早 fine-tune 會把「還沒想清楚的行為」固化,反而更難改。
- distillation 有版權/ToS 風險;蒸餾也會繼承強模型的偏誤。

### 不該用
- eval < 100、問題是語氣/事實、或還沒把 prompt 玩到極限——官方都說先別 fine-tune。
- 想靠 fine-tune 塞知識(該用 RAG)。

### 判定:**暫不用(記為未來縫)**
官方判準把你目前狀態直接導向「先做 eval + prompt」。fine-tune/distillation 是「prompt 到頂後」的下一步,不是現在。建議:先建 golden-set evals,量化到底哪些維度 prompt 拉不動,再決定 SFT(語氣一致性)或蒸餾(降本)。

---

## 6. Prompt Caching

### 白話
把 prompt 的固定前綴(系統提示、黃金範本、大 context)快取住,反覆請求時直接命中,省掉重算——降 latency、降成本。各家自動或半自動。

### 官方證據
- **OpenAI(官方)**:自動、無需改碼、prompts ≥1024 tokens 自動快取;「50% discount and faster prompt processing」;「reduce time-to-first-token latency by up to 80% and input token costs by up to 90%」;機制是路由到「recently processed the same prompt」的伺服器,故**必須是完全相同的 prefix**。來源:https://developers.openai.com/api/docs/guides/prompt-caching、https://openai.com/index/api-prompt-caching/(2024–2026)。
- **Anthropic(官方,claude-api skill,cached 2026-06)**:cache read ≈ **0.1× base input**,cache write = **1.25×(5m TTL)/ 2×(1h TTL)**;5m TTL 下**兩次請求即回本**(1.25+0.1 < 2)。最小可快取前綴 **1024–4096 tokens(依模型)**。核心不變量:「prompt caching is a prefix match — any change anywhere in the prefix invalidates everything after it」;render order = `tools → system → messages`,穩定內容放前、易變內容(時間戳、per-request ID、變動問題)放最後一個 breakpoint 之後。驗證:`usage.cache_read_input_tokens`,為零即有 silent invalidator。

### 適用時機
- **「同一份大 context 反覆多輪」正是快取的最佳場景**——你的訪談 session:系統提示 + rubric + 3–5 份黃金範本 + 已累積訪談歷史,是穩定前綴,每輪往返都能命中。
- 設計配合:把「凍結」內容(系統提示、黃金範本、schema)放最前並下 breakpoint;把「易變」內容(當前訪談回合、時間戳)放最後——別把 `datetime.now()`/UUID 塞進系統提示(會每次 invalidate)。

### 成本 / 代價
- 幾乎零品質風險——這是純成本/延遲優化,不改變輸出內容。
- 唯一「代價」:寫入有 1.25–2× 溢價,故**極少複用**的一次性大 prompt 不值得快取(單次 Best-of-N fan-out 若 prefix 相同,先送 1 個、待其開始 streaming 再送其餘 N-1,才讀得到快取)。
- prefix 敏感:任何 byte 變動(未排序 JSON、變動工具集、換模型)整段失效。

### 不該用
- 每次請求 prefix 都從頭不同(無可複用前綴)——加了只付寫入溢價、零讀取。
- 前綴短於模型最小門檻(silent 不快取)。

### 判定:**建議用(低風險高回報)**
零品質風險、直接改善長 session 的成本與延遲,且讓 #4 的黃金範本 few-shot「幾乎免費」。唯一要做的是把 prompt 結構按「穩定在前、易變在後」重排,並用 `cache_read_input_tokens` 驗證命中。

---

## 7. Synthetic Data / Eval 資料生成

### 白話
用 LLM 生成評測資料(golden-set 的合成補充)或訓練資料,補真人標註的缺口。

### 官方證據
- **定位(官方精神)**:「synthetic data helps you bootstrap evaluation datasets when you do not yet have enough representative examples, but it should complement — not replace — real data」;資料來源優先序「start with human-reviewed examples... especially examples that reflect important user journeys, failures, and edge cases」。來源:synthetic-data/eval 指引整理(decodingai、digitalapplied,2025–2026)。
- **Model collapse(可避免)**:「Model collapse is real — and provably avoidable. The fix is not avoiding synthetic data, it's accumulating real data alongside it rather than replacing it。」
- **Judge 同源偏袒**:「documented bias toward models with similar training — GPT-5 tends to prefer GPT-5-style outputs」——生成用 A 家、評測若也用 A 家會互相偏袒。
- **過量無益**:「after a certain point, adding more GPT-generated examples didn't improve the classifier」;建議「use a reward model (could be your current LLM) to evaluate each generated sample」過濾低值樣本。
- **業界先例**:Anthropic Constitutional AI(2022)是最早大規模用合成資料(模型自生 critique + revision)做 RLHF 的記錄;OpenAI 也曾用合成資料 fine-tune GPT-4 支援 Canvas。

### 適用時機
- 用來**擴充 golden-set 的覆蓋缺口**:少見職類、極端訪談情境、已知失敗模式的 edge cases——先有少量真人黃金範本,再用它們引導生成變體。
- 生成後**必過濾**:用 rubric grader(最好跨家)剔除低值/偏誤樣本。

### 成本 / 代價
- 純合成、無真人錨定 → distribution drift + model collapse + eval overfitting(評測分數虛高)。
- 生成 + 過濾 + 人審的流程成本;生成用同家會把該家偏誤帶進 eval。
- 「因為便宜就狂生成、生完不回看」是官方明列的濫用。

### 不該用
- 完全取代真人標註——尤其 eval set,失去真實性就失去意義。
- 生成與評測同一模型同家(偏袒 + collapse 雙重風險)。

### 判定:**可試(僅補 eval 缺口 + 嚴格過濾)**
定位為「真人 golden-set 的補充」,用來加速覆蓋長尾情境。硬規則:真人優先、合成僅補缺、跨家生成/評測、每筆過濾、控量。切勿讓合成資料稀釋你的「顧問級真人範本」這把尺。

---

## 8. Streaming + Partial Structured Outputs

### 白話
邊生成邊呈現結構化內容:模型還在寫,前端就能逐步顯示部分 JSON / 部分文件區塊(partial JSON streaming),而非等整份生成完才一次跳出。

### 官方證據
- **OpenAI(官方 SDK)**:Python/JS SDK 原生支援 streaming structured outputs——用 jiter 增量解析 JSON,`ChatCompletionStreamState` 累積 deltas 成 `ParsedChatCompletion`,可隨時透過 `current_completion_snapshot` 取當前部分狀態,`content.done` 事件給完整解析物件。來源:https://developers.openai.com/api/docs/guides/structured-outputs、openai-python streaming(2025)。
- **Anthropic(官方,claude-api skill)**:streaming 事件 `message_start / content_block_start / content_block_delta / content_block_stop / message_delta / message_stop`;SDK 提供 `.stream()` + `.get_final_message()`/`.finalMessage()` 取完整訊息;**大 `max_tokens`(>~16K)必須 streaming** 以避免 HTTP timeout;Managed Agents 另有 live preview(`event_start`/`event_delta`,accumulate-and-reconcile)。
- 注意:這是 **UX / 工程層**技術,**不改變最終輸出的品質內容**——它改善的是「等待體感」與「長輸出不 timeout」,不是把答案變得更對。

### 適用時機
- 長文件生成(整份 JD 可能上千 token):streaming 讓使用者立刻看到區塊逐步成形,大幅降低感知延遲、可提早發現方向錯誤而中止。
- 大 `max_tokens` 的請求:官方要求 streaming 才不會 timeout——這是硬性工程需求,不只 UX。

### 成本 / 代價
- 幾乎無成本;partial JSON 解析要處理「未閉合/不完整」中間態(SDK 已代勞,但自行渲染時要容錯)。
- partial 是「盡力而為」的中間態,不可當最終真值——要以 `content.done`/`finalMessage` 為準(Anthropic live preview 明示 best-effort、可能掉 delta)。

### 不該用
- 短輸出(抽取、分類、單值)——沒有可漸進呈現的價值。
- 把 partial 中間態當最終結果拿去做確定性守門或落庫(必須等 final)。

### 判定:**建議用(UX,非品質)**
對「長文件生成」的體感是關鍵改善,且大輸出本就需要 streaming 防 timeout;SDK 原生支援、成本低。但要清楚:它提升的是體驗與工程穩定性,**不是輸出品質本身**——別把它算進「品質拉升」的帳,而是「品質系統的必要基礎設施」。

---

## 額外值得加的技術(自行補充)

### A. Rubric-grounded LLM-as-Judge(裁判 = verifier 的具體建法)
把 #2 的 verifier 與 #3 的 refine 訊號統一為一個 **rubric-based grader**:給裁判明確、可獨立評分的條目(不是「看起來好不好」),逐條打分 + 給改進理由。這同時服務 Best-of-N 重排、refine 迴圈的批評訊號、與 golden-set evals。**硬規則:裁判與生成不同模型家族(避免同源偏袒,已有實證);rubric 條目要可獨立判定**。這是把你「規劃中 golden-set evals」升級成「可驅動生成品質」的樞紐。判定:**建議用**——它是 #2/#3/#7 共用的地基。

### B. Contextual grounding / Citations(強化你已有的 quote 溯源)
你已有 quote 溯源;可再用官方 citations 機制(Anthropic `citations:{enabled:true}` 回傳 `cited_text` + char/page location;各家類似)把「JD 每條主張 → 訪談原文出處」做成可機器驗證的錨點,再用確定性守門檢查「無出處的主張」。判定:**可試**——與你「確定性守門 + quote 溯源」現有設計同源,邊際強化。

---

## 來源總表

| 主題 | 來源 | 類型 | 日期 |
|------|------|------|------|
| Reasoning best practices | https://developers.openai.com/api/docs/guides/reasoning-best-practices | OpenAI 官方 | 2025(持續更新) |
| Reasoning models 指南 | https://developers.openai.com/api/docs/guides/reasoning | OpenAI 官方 | 2025 |
| Extended thinking | https://platform.claude.com/docs/en/build-with-claude/extended-thinking | Anthropic 官方 | 2025 |
| Adaptive thinking / effort / prompt caching / streaming(現行 API 細節) | claude-api skill(platform.claude.com docs 快照) | Anthropic 官方 | cached 2026-06 |
| DeepSeek R1(RL 誘發推理、湧現 self-verification) | Nature 645, 633–638;DOI 10.1038/s41586-025-09422-z;arXiv:2501.12948 | 同行審查論文 | 2025-09 / 2025-01 |
| Test-time compute optimal scaling | arXiv:2408.03314(Snell, Lee, Xu, Kumar;UC Berkeley + Google DeepMind) | 論文 | 2024-08 |
| Sample, Scrutinize and Scale(verification 有效) | arXiv:2502.01839 | 論文 | 2025 |
| Best-of-N via Self-Certainty(免 RM) | arXiv:2502.18581 | 論文 | 2025-02 |
| Self-consistency(原始) | Wang et al.(freeCodeCamp/論文整理) | 論文 | 2022–2023 |
| Self-Refine(+20%,生成任務有效) | NeurIPS 2023 proceedings(Madaan et al.) | 論文(頂會) | 2023 |
| LLMs Cannot Self-Correct Reasoning Yet(內在自評無效) | ICLR 2024;arXiv:2310.01798(Huang et al.) | 論文(頂會) | 2023-10 / 2024 |
| Self-correction 綜述 / Self-Correction Bench | When Can LLMs Actually Correct...(2024 survey);arXiv:2507.02778 | 論文/綜述 | 2024–2025 |
| Few-shot 最佳實踐(3–5 例、多樣、標籤化) | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering | Anthropic 官方 | 2025 |
| Fine-tuning SFT/DPO/RFT + 何時別 fine-tune | https://developers.openai.com/api/docs/guides/reinforcement-fine-tuning;rft-use-cases | OpenAI 官方 | 2025–2026 |
| Prompt caching(自動、50%/最高 90%、TTFT −80%) | https://developers.openai.com/api/docs/guides/prompt-caching;https://openai.com/index/api-prompt-caching/ | OpenAI 官方 | 2024–2026 |
| Synthetic data / eval(collapse、judge 偏袒、補而非替代) | digitalapplied(2026)、decodingai;Constitutional AI(Anthropic, 2022) | 整理 + 官方先例 | 2022 / 2025–2026 |
| Streaming structured outputs(jiter、snapshot) | https://developers.openai.com/api/docs/guides/structured-outputs;openai-python streaming | OpenAI 官方 SDK | 2025 |

> 註:部分「業界整理」條目(few-shot 數量、fine-tune 判準、synthetic data 陷阱)之原始出處為 OpenAI/Anthropic 官方文件;本報告已在文中回指官方頁面,整理文僅作彙整佐證,未作為唯一依據。
