# LLM Evals 與 LLM-as-Judge 的「正確設計方法」研究紀錄(2025–2026)

> 目的:給「AI 訪談→生成繁中專業職務說明書(JD)」評測系統的**設計細節**。前提已定案(黃金範本考題、Source/Answer 雙指標、capability/regression 雙 suite+畢業制、promptfoo 進 CI、裁判只在測試時跑、SME=維護者本人)。本文只回答「怎麼設計才真的有效」。
> 日期:2026-07-12。來源紀律:僅收模型廠官方、署名資深實務者原著、頂會/大實驗室論文、產業一手。每條標 URL+日期。

---

## 適用性總結(先讀這段)

你的系統有三個特徵決定了設計取向,務必貫穿全文:

1. **有黃金標準答案(reference JD)** → 應以 **reference-based(pointwise-against-gold)** 為主,而非兩個模型輸出互比的 pairwise。這讓「裁判有特權資訊」,是把裁判拉到專家水準的關鍵槓桿。
2. **輸出是長篇結構化文件(JD),非單一答案** → 用 **rubric 拆維度 + 分項 LLM-judge**,不要一個 judge 打整體分;程式可算的(欄位齊全、來源可溯)走 Source Score,不要浪費在裁判上。
3. **繁體中文 + 多輪訪談前段** → 多語裁判一致性顯著低於英文(Fleiss' κ≈0.3 across 25 langs),且模擬受訪者(user simulator)有系統性「太配合」偏差。這兩點是你最大的隱藏風險,必須專門設計對策(見 Q6、Q4)。

---

## Q1. Rubric 怎麼寫才有效

**結論**:好 rubric = 一組**可被兩位獨立專家判出相同 pass/fail 的、二元或近二元的具體條目**,按維度隔離、含扣分項、對照黃金答案評。爛 rubric = 模糊形容詞(「清楚」「專業」)+ 1–5 整體評分。

### 關鍵證據
- **Anthropic(官方)**:「A good task is one where two domain experts would independently reach the same pass/fail verdict.」「Vague rubrics introduce noise; structured rubrics grading isolated dimensions perform better than holistic scoring.」— *Demystifying evals for AI agents*, anthropic.com/engineering/demystifying-evals-for-ai-agents(2026-01)
- **Anthropic(官方)**:grader prompt 要具體到「the answer should always mention 'Acme Inc.' in the first sentence. If it does not, the answer is automatically graded as 'incorrect'」。— platform.claude.com/docs/en/test-and-evaluate/develop-tests(2025–2026)
- **Hamel Husain(資深實務者)**:「If your evaluations consist of a bunch of metrics that LLMs score on a 1-5 scale… you're doing it wrong.」「A binary decision forces everyone to consider what truly matters.」「If someone says you need to measure 8 things on a 1-5 scale, they don't know what they are looking for.」— hamel.dev/blog/posts/llm-judge/(2024, 2026 持續更新)
- **Harvey BigLaw Bench(產業一手)**:每個 affirmative requirement 給**正分**(依對完成任務的重要性加權);hallucination 等給**負分**(因為人要花力氣去修錯,會抵銷成品價值)。公式:`(正分 − 負分) ÷ 該題總正分 = 品質分`。實例負分:wrong controlling case cited −5、hallucinated citation −4、missed circuit split −2。— harvey.ai/blog/introducing-biglaw-bench(2024-09);GitHub: harveyai/biglaw-bench
- **維度切法**:Harvey 把「完成度」與「可溯源」拆成兩個獨立分(Answer Score / Source Score),因為「a model can make correct assertions (high answer score) while failing to provide traceability (low source score)」——這正好對應你的雙指標設計。

### 具體可執行建議
1. **量表選擇:以 binary(pass/fail)為主**。每個 rubric item 是一個可獨立判定的斷言。若真需要程度,最多用「pass / partial / fail」三級或「0/0.5/1」,不要 1–5、不要百分比自由心證。理由:1–5 不可行動、跨題不可比、放大裁判變異。
2. **維度數量:3–6 個,且互相隔離評分**。對 JD 建議維度示例:①**核心職責覆蓋**(是否涵蓋黃金答案的關鍵職責點)②**任職資格/職能對齊**(硬性條件、職能等級是否正確)③**事實忠實度/無臆造**(逐字稿沒說的資歷、數字、公司資訊不得憑空生)④**結構與欄位完整**(標準 JD 段落齊全——這條偏程式可算,放 Source 側)⑤**專業語域與體例**(繁中職場用語、書面體、無口語殘留)。每維度用獨立的 LLM-judge call,不要一個 prompt 打全部。
3. **加入負分/扣分項(仿 Harvey)**:臆造(hallucinated)條件、與逐字稿矛盾、把訪談口語直接抄進 JD、法規/職稱誤用,各給負分。負分讓「看似完整但有害」的輸出被壓下去,這對 JD(給人資直接用)特別重要。
4. **以黃金答案為錨**:每個 rubric item 寫成「相對於 reference JD 的 X,回答是否也涵蓋/正確處理了 X」。把黃金答案裡的關鍵點列成 checklist(coverage items),judge 逐點勾。
5. **每題附 reference solution 驗 grader**:Anthropic 明言「create a reference solution… proves that the task is solvable and verifies graders are correctly configured」;「a 0% pass rate is most often a signal of a broken task, not an incapable agent」。你的黃金答案本身就該能拿滿分——若拿不到,是 rubric 壞了。

---

## Q2. 裁判(judge)工程細節

**結論**:先讓 judge 用 CoT 推理再出結論、但**只保留結論丟掉推理**;對「有黃金答案」的任務用 **pointwise-against-reference**(不是 pairwise);裁判模型選**當前最強**先對齊人類、之後才談降本;分項獨立評;判定盡量走 binary 以降變異;有變異就同題多跑取多數/平均。

### 關鍵證據
- **Anthropic(官方)**:「encourage the LLM to think first before deciding an evaluation score, and then discard the reasoning — this increases evaluation performance, particularly for tasks requiring complex judgement.」「Generally best practice to use a different model to evaluate than the model used to generate.」— develop-tests 文件
- **Anthropic(官方)**:「grade each dimension with an isolated LLM-as-judge rather than using one to grade all dimensions.」給裁判 escape hatch:「return 'Unknown' when it doesn't have enough information」。「Make your graders resistant to bypasses or hacks.」— Demystifying evals
- **Eugene Yan(資深實務者)**:pairwise「leads to more stable results and smaller differences between LLM judgments and human annotations relative to direct scoring」——**但**「Some evaluation tasks, such as assessing faithfulness or instruction-following, don't fit the pairwise comparison paradigm… a response is either faithful to the provided context or it is not」。CoT 提升準確度;判斷力隨參數量上升(gpt-4 correctness Spearman ρ=0.67 vs gpt-3.5 0.61;MT-Bench gpt-4 vs 人類 agreement 85% > 人‑人 81%)。— eugeneyan.com/writing/llm-evaluators/(2024-08)
- **PoLL — Panel of LLM evaluators(Cohere, Verga et al.)**:用**三個不同廠的小模型**(command-r + gpt-3.5-turbo + haiku)組陪審團、聚合分數,比單一 GPT-4 裁判**更貼近人類且便宜 7 倍**,還能降低 intra-model bias。「there is not a single 'best' judge across all settings.」— arxiv.org/abs/2404.18796(2024-04)
- **Zheng et al., Judging LLM-as-a-Judge(MT-Bench/Chatbot Arena)**:GPT-4 裁判與人類 agreement >80%,達人‑人一致水準;系統記錄 position/verbosity/self-enhancement bias 並給緩解。— arxiv.org/abs/2306.05685(2023;NeurIPS 2023)

### 具體可執行建議
1. **judge prompt 結構**:系統角色(資深 HR/JD 顧問)→ 給評測 rubric 的**單一維度**定義 → 給 reference JD 的該維度要點 → 給待評 JD → 要求「先逐點分析(reasoning)再輸出 JSON verdict」→ 解析時**只取 verdict,丟棄 reasoning**。骨架見文末。
2. **pointwise-against-reference 為主線**。你有黃金答案,直接讓 judge 對照 reference 逐點判(coverage/faithfulness),不需要 pairwise。**pairwise 只在**你想比較「新 prompt vs 舊 prompt 哪個好」的 A/B 相對回歸時才用(此時務必做順序交換,見 Q4)。
3. **裁判模型**:選當前最強、且**與生成模型不同家**(避免 self-preference)。你的生成若是 Claude,裁判可用另一家強模型,或反之。先用最強對齊人類,對齊穩了再評估能否降到便宜模型。
4. **可選:PoLL 陪審團**用於高風險的「畢業/發版」關卡——三個異廠模型投票,降單裁判偏誤與成本。日常 CI 用單一強裁判即可。
5. **溫度/採樣**:裁判用 **temperature=0**(或極低)求可重複;但注意 temp=0 仍非完全確定。對「有意義變異」的維度(如語域這種偏主觀者),**同題跑 3–5 次取多數決(binary)或平均**,並記錄裁判自身的一致率(self-consistency)當健康指標。
6. **給 escape hatch + 防作弊**:允許裁判回 `unknown`(資訊不足),避免逼它幻覺;rubric 條目不要能被「塞關鍵字」騙過。

---

## Q3. 校準(calibration)方法論:讓裁判對齊 SME

**結論**:建一個**人工標註的 held-out 校準集**,SME(你本人)親手 pass/fail 標註,迭代 judge prompt 直到與 SME 的 **TPR 與 TNR 都夠高**(不是看 raw accuracy);divergence 過大就回頭修 rubric;prompt/模型/rubric 任一變動就重跑校準。

### 關鍵證據
- **Anthropic(官方)**:「LLM-as-judge graders should be closely calibrated with human experts to gain confidence that there is little divergence.」「Once the system is robust, it's sufficient to use human review only occasionally.」— Demystifying evals
- **Hamel(資深實務者)**:三原則——binary 輸出、手標一批 ground truth、拿 judge 輸出對照手標驗證。「Focus on achieving high **True Positive Rate (TPR) and True Negative Rate (TNR)** with your judge on a held out labeled test set.」「Using raw agreement is generally not recommended and can be misleading when classes are imbalanced. Instead… measure precision and recall separately.」迭代到「>90% agreement between the LLM and Phillip」約需 3 輪。「For any data used for testing/validating… hand-validate each label.」— hamel.dev/blog/posts/llm-judge/ 與 evals-faq
- **Eugene Yan**:一致性指標要看**Cohen's κ**(較保守、扣掉偶然一致):relevance κ 僅 0.3–0.5「fair」,但 Kendall τ/Spearman ρ 可達 0.8–0.9;人‑人 κ 常達 0.9+,故裁判 κ 有天花板。—llm-evaluators
- **Shreya Shankar et al., Who Validates the Validators?(UIST 2024)**:「**criteria drift**」——人要先定義標準才能評分,但**評分的過程本身才會讓標準浮現**;有些標準是看了輸出才長出來的,不能 a priori 全定死。故校準要「grade-then-refine」循環,不是一次寫死 rubric。— arxiv.org/abs/2404.12272(2024-04)

### 具體可執行建議
1. **抽樣多少**:校準集**至少 100 筆**手標(Hamel:先看 100 起跳;~20 筆不再出現新失敗類就可停探索,但總量 100+)。類別要平衡(pass 與 fail 都要有足量),否則 accuracy 會騙人。
2. **算什麼**:主指標 **TPR / TNR 分開報**(或 precision/recall);輔以 **Cohen's κ**(目標 ≥0.6「substantial」為佳,但接受 0.4–0.6 並持續改;對照人‑人 κ 上限)。**不要**只報 raw accuracy。
3. **grade-then-refine 循環(對抗 criteria drift)**:SME 先獨立標一批 → 對照 judge 判定 → 看分歧案例 → 分歧往往揭露 rubric 沒寫清的隱含標準 → 補進 rubric → 重跑。Hamel 觀察:「seeing how the LLM breaks down its reasoning made me realize I wasn't being consistent」——迭代也在校準 SME 自己。
4. **divergence 門檻**:任一維度 TPR 或 TNR 掉到可接受線下(建議 <0.9 就檢討),或 κ 顯著下降,就**回修 rubric 或 judge prompt**;若換 prompt 都救不動,Hamel 建議「try a different model」。
5. **多久重校**:①**每次 judge prompt / rubric / 裁判模型版本變動**都重跑校準集(這是硬性 gate)②穩定後**定期抽查**(如每季或每次系統大改)③新增考題進 suite 時順手擴充校準集。
6. **模型升版怎麼辦**:把校準集當**裁判的回歸測試**。裁判模型升版=重新對齊,先在校準集上比新舊裁判與 SME 的 TPR/TNR/κ,**只有新裁判不劣於舊裁判才切換**,並記錄切換點(避免「judge 升版靜默改變基準」,見 Q8)。

---

## Q4. 已知偏誤與對策清單

**結論**:五大偏誤都有實證來源與具體工程對策。你的 reference-based pointwise 設計天生免疫掉一部分(position/verbosity 主要傷 pairwise),但 sycophancy-toward-input、self-preference、格式偏好仍要防。

| 偏誤 | 實證來源 | 對策(工程) |
|---|---|---|
| **Position bias**(pairwise 偏好某位置) | Zheng et al. 2306.05685:gpt-3.5 偏一側 50%、claude-v1 70%。JudgeBench 2025 仍見殘留 position bias。 | **只在 pairwise 出現**。做 pairwise 時**兩種順序各跑一次、取一致結果**(不一致→判 tie 或再議)。你主線用 pointwise 可直接迴避。 |
| **Verbosity bias**(偏好長答) | Zheng et al.:claude-v1 與 gpt-3.5「preferred the longer response >90% of the time」即使冗餘。 | rubric 明列「冗長、離題、重複」為**扣分項**(仿 Harvey 的 incorrect length 負分);裁判 prompt 明示「長度不是品質,對照 reference 判資訊是否到位」。 |
| **Self-preference / self-enhancement**(偏好自家/自己產出) | Eugene Yan / Zheng:gpt-4 自偏 +10% win rate、claude-v1 +25%。 | 裁判模型與生成模型**不同家**;高風險關卡用 **PoLL 異廠陪審團**稀釋。 |
| **格式偏好**(markdown、條列、標題等) | Zheng/後續偏誤研究普遍記錄格式偏好。 | 評分前**正規化格式**(去 markdown、統一段落)再送裁判;rubric 針對「內容」而非「排版」。 |
| **Sycophancy toward input**(順著輸入/受訪者說法照單全收) | 多輪與 user-sim 研究(見 Q6);裁判也會偏好「呼應提示」的答案。 | 這是你**最該防**的:JD 生成常把逐字稿口語/自誇當事實。rubric 設**faithfulness 維度**,裁判要標「回答有無把逐字稿未證實的資歷/數字當真」;負分伺候臆造。 |
| **多語/繁中低一致**(非英語系統性偏低、translationese) | Fleiss' κ≈0.3 across 25 langs;translationese bias 偏好機翻內容。 | 裁判 prompt、rubric、reference **全繁中**,不要英文 rubric 評繁中輸出;校準集也必須是繁中真實案例;跨語一致性差→更倚重程式可算的 Source Score。 |

### 來源
- Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, arxiv.org/abs/2306.05685(2023)
- Eugene Yan, *Evaluating LLM-Evaluators*, eugeneyan.com/writing/llm-evaluators/(2024-08)
- *JudgeBench*(ICLR 2025), arxiv.org/abs/2410.12784
- 多語:*Towards Reliable Multilingual LLMs-as-a-Judge*, arxiv.org/abs/2605.28710;*Challenges & Recommendations for LLMs-as-a-Judge in Multilingual Settings*, arxiv.org/html/2607.02235;translationese:arxiv.org/abs/2603.10351(2026)

---

## Q5. 考題設計

**結論**:一題可考多維度(用多個 rubric item),但**每個 item 一維、獨立判**;數量上 **20–50 題起跑、CI 常態 100+**;edge case 從真實失敗轉化;防污染靠自建/私有逐字稿+保留 held-out;繁中要用真實繁中語料。

### 關鍵證據
- **Anthropic**:「20-50 simple tasks drawn from real failures is a great start」;「Converting user-reported failures into test cases ensures your suite reflects actual usage」;「factor in edge cases」。「Prioritize volume over quality: More questions with slightly lower signal automated grading is better than fewer questions with high-quality human hand-graded evals.」— Demystifying / develop-tests
- **Hamel**:CI 資料集「small (in many cases 100+ examples)」涵蓋「core features, regression tests for past bugs, and known edge cases」;「Be wary of optimizing for high eval pass rates. If you're passing 100% of your evals, you're likely not challenging your system enough. A 70% pass rate might indicate a more meaningful evaluation.」— evals-faq
- **繁中**:多語裁判一致性低(Q4),故繁中考題+繁中 reference+繁中 rubric 是硬要求。

### 具體可執行建議
1. **一題多維**:一份逐字稿→一份 reference JD,配一組 rubric(涵蓋 3–6 維度)。這樣單題資訊密度高、又能分維度定位失敗。但**每維獨立 judge call**,不要合併。
2. **數量門檻**:capability suite 先 **20–50 題**(挑系統會失敗的難題,低通過率起步);系統成熟後畢業成 regression suite,**常態維持 100+ 題**跨核心情境。統計意義上,~100 題才能給每個維度有意義的通過率估計(單維度 30–50 有效樣本是最低可讀線)。
3. **難度分佈**:capability 題要**難到會失敗**(通過率 <100% 才有信號;全過=太簡單,見 Q8);regression 題應**近 100% 通過**、守住不倒退。混入 edge cases:資訊稀薄的逐字稿、多職務混談、受訪者自誇灌水、跨產業罕見職務、口語極重的訪談。
4. **防污染(contamination)**:①用**自建/客戶真實逐字稿**,不要用公開 JD 樣本當答案(模型可能背過)②保留一份**never-published held-out**,只在畢業/發版關卡跑,不進日常 CI 迭代,避免對考題過擬合③reference JD 由 SME 親撰,不要用被評測的同款模型生成後當標準答案。
5. **繁中特殊**:考題與答案要涵蓋台灣職場實際用語(職稱、職等、法遵用語);避免簡繁混用;裁判與 rubric 一律繁中。

---

## Q6. Agent / 多輪系統的評測(訪談環節)

**結論**:trajectory 評測從 trace 抽**可判定的斷言**(有沒有問到必要職責、有沒有追問模糊處、有沒有臆造),但**優先評最終產物而非路徑**;模擬受訪者是必要之惡,最大陷阱是「太配合」導致假高分,要刻意注入不合作/資訊稀薄/矛盾人格;非確定性用 **pass@k / pass^k** 並跑多次取統計量。

### 關鍵證據
- **Anthropic**:「it's often better to grade what the agent produced, not the path it took」以免「overly brittle tests」。但 transcript 關鍵:「the transcript tells you whether the agent made a genuine mistake or whether your graders rejected a valid solution」;「we invested in tooling for viewing eval transcripts and we regularly… read them」。對話 agent「often require a second LLM to simulate the user」(如 τ²-Bench)。非確定性:**pass@k**(k 次至少一次成功)vs **pass^k**(k 次全成功,「especially matters for customer-facing agents where users expect reliable behavior every time」);「pass@k for tools where one success matters, pass^k for agents where consistency is essential」。「Unnecessary shared state between runs… can cause correlated failures」。— Demystifying evals
- **Hamel**:多輪先「Annotate only the first failure in the trace… downstream failures often cascade from the first」;用「transition failure matrices」(last successful state × first failure)。— evals-faq
- **User-simulator 陷阱(頂會/論文一手)**:模擬者「excessively cooperative, stylistically uniform, and lack realistic frustration」造成「easy mode」灌高 agent 成功率;τ-bench 模擬者「cannot decline the goal; willingness is a fixed input」;實測 50 段對話中 **22%(11/50)** 模擬者行為偏離指令。「even strong models become substantially less reliable when information is revealed incrementally.」— *Beyond Cooperative Simulators*(arxiv.org/abs/2605.12894)、*Mind the Sim2Real Gap*(2603.11245)、*Non-Collaborative User Simulators*(2509.23124)、τ²-Bench(2506.07982),均 2025–2026

### 具體可執行建議
1. **trajectory 斷言(從 trace 抽)**:針對訪談,寫可判定斷言——是否覆蓋 reference 所需的每個職責面向(coverage)、遇模糊回答是否**追問**、是否對受訪者未證實的說法**做臆造**(faithfulness 反面)、是否問了不該問/離題。這些做成 binary checks,程式可算的走 Source 側,主觀的走 judge。
2. **先評產物、trace 當診斷**:主分看最終 JD(對照 reference);trace 用來**歸因失敗**(是訪談沒問到,還是生成階段丟了)。用 Hamel 的「只標第一個失敗」+ transition matrix 定位斷點。
3. **模擬受訪者設計(重點防坑)**:
   - 給模擬者**明確 persona + 隱藏資訊清單**,要求「**擠牙膏式**、只在被問到才吐、不主動全盤托出、不得幻覺超出 persona 的資訊」。
   - **刻意注入不合作性**:設計「話少型」「跑題型」「自誇灌水型」「前後矛盾型」persona,避免全是配合的乖受訪者(否則 easy mode 灌高分)。
   - **驗模擬者本身**:抽查模擬對話,確認它沒偷偷洩漏未問到的資訊、沒越出 persona(參照 22% 偏離率的教訓)。模擬者用與被測 agent **不同**的模型較好。
4. **端到端可重複性(非確定性)**:同一考卷**跑 k 次(建議 k=3–5)**,報 **pass@k 與 pass^k**。JD 給人資直接用→偏向 **pass^k**(要求穩定每次都達標)。維度分數報**平均+標準差**,標準差過大代表該維度信號噪、需收緊 rubric 或多跑。
5. **隔離 run 間狀態**:每次 run 用乾淨 context,避免 leftover 造成 correlated failure。

---

## Q7. Meta-evaluation(評裁判的裁判)

**結論**:業界 benchmark(JudgeBench)顯示**即使最強裁判也遠非完美**(最佳僅 ~64% acc、裁判間差距達 31%),故不能盲信單裁判;實務上「維持 judge 品質的最小流程」= 一個**手標校準集當裁判的回歸測試 + 每次變動重跑 + 定期抽查**。

### 關鍵證據
- **JudgeBench(ICLR 2025)**:350 對嚴格驗證的難題,「the strongest model achieves only 64% accuracy」;最佳(Claude-3.5-Sonnet)與最弱(Haiku)差 **31%**;進階 rubric/meta-judge 框架可到 77%+、最佳 reward model 81%+;殘留 position/length bias。啟示:裁判強度差異巨大、要挑強裁判且持續驗。— arxiv.org/abs/2410.12784
- **Shankar et al.**:LLM 生成的 evaluator「inherit all the problems of the LLMs they evaluate, requiring further human validation」——裁判必須被人驗。— 2404.12272
- **Hamel**:裁判品質靠「hand-validate each label」+ held-out TPR/TNR。

### 具體可執行建議(維持 judge 品質的最小流程)
1. **建裁判回歸集**:即 Q3 的手標校準集(SME pass/fail),當作「裁判的考卷」。
2. **每次動裁判就重考**:judge prompt / rubric / 裁判模型版本任一變動 → 重跑校準集 → 比 TPR/TNR/κ,不劣才放行。
3. **定期抽查漂移**:每季或每次系統大改,SME 抽 20–30 筆最新輸出重標,對照裁判,看有無漂移。
4. **不追求完美裁判,追求「與 SME 對齊且穩定」**:JudgeBench 提醒 64% 天花板,故裁判分數是**相對信號**(比較版本、抓回歸),不是絕對真理;高風險發版關卡加人審。

---

## Q8. 常見失敗模式(evals 做了卻沒用)

**結論**:五大失敗——考題太簡單全過、rubric 漂移、judge 升版靜默改基準、過擬合考題、跳過 error analysis 用通用指標。每個都有對策。

### 關鍵證據 + 對策
1. **考題太簡單全過**:Hamel「If you're passing 100% of your evals, you're likely not challenging your system enough. A 70% pass rate might indicate a more meaningful evaluation.」→ capability suite 刻意挑會失敗的難題;通過率逼近 100% 的題目畢業成 regression,並持續**注入新難題**維持信號。
2. **rubric 漂移 / criteria drift**:Shankar——標準會隨看到的輸出而變。→ grade-then-refine 循環把浮現的隱含標準固化進 rubric;rubric 版本化,改動留紀錄。
3. **judge 升版靜默改基準**:JudgeBench 顯示不同裁判差 31%,升版可能無聲改變所有分數。→ 裁判模型/prompt 版本化;每次升版在校準集比對新舊;歷史分數標註「用哪版裁判產生」,跨版比較前先確認裁判一致。
4. **過擬合考題(over-fitting to eval)**:對著考題調 prompt 直到全過,但真實表現沒進步。→ 保留 never-published held-out(Q5);Anthropic「a 0% pass rate is most often a broken task」——反過來 100% 也可疑;監控 CI 分數與真實使用者反饋是否背離。
5. **跳過 error analysis、用通用指標**:Hamel「Start with error analysis, not infrastructure.」「Generic metrics… may not matter for your use case.」「Do not skip error analysis.」60–80% 的開發時間該花在看真實失敗上。→ rubric 維度要從**真實失敗的 error analysis** 長出來,不要抄「clarity/coherence」這種通用維度。
6. **裁判與 SME 用 raw accuracy 對齊**:類別不平衡下會騙人。→ 一律看 TPR/TNR + κ。

---

## 附錄 A:可仿 Rubric 範例(JD 生成)

> 針對一份逐字稿→一份 reference JD。每個 item 獨立 binary 判定;正分加權、負分扣分;Answer Score = (Σ正分 − Σ負分) ÷ Σ總正分。Source 側另算(程式)。

```yaml
task_id: JD-2026-0142
reference_jd: ./gold/JD-2026-0142.md
transcript: ./inputs/JD-2026-0142.txt

# === Answer Score(裁判算,分維度) ===
dimensions:

  core_responsibilities:            # 維度1:核心職責覆蓋(對照 reference 逐點)
    weight_note: "每個關鍵職責點 +2"
    items:
      - id: R1
        assertion: "涵蓋 reference 的『跨部門專案協調』職責"
        points: +2
      - id: R2
        assertion: "涵蓋 reference 的『年度預算編列與控管』職責"
        points: +2
      - id: R3
        assertion: "涵蓋 reference 的『團隊績效管理』職責"
        points: +2

  qualifications:                   # 維度2:任職資格/職能對齊
    items:
      - id: Q1
        assertion: "正確列出硬性條件(年資、學歷)且與逐字稿一致"
        points: +2
      - id: Q2
        assertion: "職能等級/職稱層級判斷正確(未高估或低估)"
        points: +2

  faithfulness:                     # 維度3:忠實度/無臆造(含負分)
    items:
      - id: F1
        assertion: "未出現逐字稿未提及的資歷/證照/數字"
        points: +2
      - id: F2
        assertion: "臆造具體事實(公司名、KPI 數字、法規)"
        points: -4        # 負分:仿 Harvey hallucination 罰則
      - id: F3
        assertion: "把受訪者口語自誇當客觀事實寫入"
        points: -2

  register_style:                   # 維度4:專業語域與體例(繁中)
    items:
      - id: S1
        assertion: "全篇書面繁中職場用語,無口語殘留、無簡繁混用"
        points: +1
      - id: S2
        assertion: "冗長、離題或重複段落"
        points: -1        # 負分:壓 verbosity

# === Source Score(程式算,不進裁判) ===
source_checks:
  - standard_sections_present: [職稱, 部門, 職責, 任職資格, 匯報關係]   # 欄位完整
  - every_claim_traceable_to_transcript: true                        # 可溯源比率
```

判定規則(給裁判):**每個 item 相對於 reference 與逐字稿,只回 pass / fail / unknown**;資訊不足回 unknown(不猜)。partial 覆蓋算 fail(從嚴)。

---

## 附錄 B:Judge Prompt 骨架範例(單維度、pointwise-against-reference、繁中)

> 一維一個 call。先推理後結論,解析時丟棄 reasoning。temperature=0。

```
[System]
你是資深的職務說明書(JD)審查顧問,精通台灣職場人資實務。
你的任務:只評「{{dimension_name}}」這一個面向,忽略其他面向。
只依據下列 rubric 與參考答案判定,不要憑個人風格加碼。

[Rubric — 本維度]
{{dimension_definition_and_items}}   # 例:core_responsibilities 的 R1..R3,含正/負分

[參考答案(黃金 JD)— 本維度相關要點]
{{reference_key_points_for_this_dimension}}

[逐字稿(事實來源,判 faithfulness 用)]
{{transcript}}

[待評 JD]
{{candidate_jd}}

[指示]
1. 先逐一針對每個 rubric item 分析:待評 JD 相對於參考答案/逐字稿,是否滿足?
   引用待評 JD 的具體片段佐證。資訊不足時判 unknown,不要臆測。
2. 分析完再輸出 JSON,格式如下(analysis 僅供你推理,呼叫端會丟棄):

{
  "analysis": "<逐 item 推理>",
  "items": [
    {"id": "R1", "verdict": "pass|fail|unknown", "evidence": "<片段>"},
    ...
  ]
}

只輸出上述 JSON。長度不代表品質——請對照參考答案判斷資訊是否到位,
不要因為回答較長就給較高評價。
```

**多跑取穩定**:對主觀維度(register_style)同題跑 3–5 次取多數決;客觀維度(faithfulness/coverage)temp=0 通常一次即可,但仍抽樣驗 self-consistency。
**pairwise 變體**(僅 A/B 比較 prompt 版本時用):同時給兩份輸出,**順序交換各跑一次取一致結果**,不一致判 tie。

---

## 來源總表

**模型廠官方**
- Anthropic, *Demystifying evals for AI agents*, https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents(2026-01)
- Anthropic, *Define success criteria and build evaluations*(Claude Platform Docs), https://platform.claude.com/docs/en/test-and-evaluate/develop-tests(2025–2026)

**署名資深實務者**
- Hamel Husain, *Using LLM-as-a-Judge For Evaluation: A Complete Guide*, https://hamel.dev/blog/posts/llm-judge/(2024;持續更新)
- Hamel Husain & Shreya Shankar, *LLM Evals: Everything You Need to Know (FAQ)*, https://hamel.dev/blog/posts/evals-faq/(2026-01-15)
- Eugene Yan, *Evaluating the Effectiveness of LLM-Evaluators (LLM-as-Judge)*, https://eugeneyan.com/writing/llm-evaluators/(2024-08)

**頂會/大實驗室論文**
- Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, https://arxiv.org/abs/2306.05685(2023, NeurIPS 2023)
- Verga et al. (Cohere), *Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models (PoLL)*, https://arxiv.org/abs/2404.18796(2024-04)
- Tan et al., *JudgeBench: A Benchmark for Evaluating LLM-based Judges*, https://arxiv.org/abs/2410.12784(ICLR 2025)
- Shankar et al., *Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences*, https://arxiv.org/abs/2404.12272(UIST 2024)
- *Beyond Cooperative Simulators: Generating Realistic User Personas for Robust Evaluation of LLM Agents*, https://arxiv.org/abs/2605.12894(2026)
- *Mind the Sim2Real Gap in User Simulation for Agentic Tasks*, https://arxiv.org/abs/2603.11245(2026);*Non-Collaborative User Simulators for Tool Agents*, https://arxiv.org/abs/2509.23124(2025);τ²-Bench, https://arxiv.org/abs/2506.07982(2025)
- *Towards Reliable Multilingual LLMs-as-a-Judge*, https://arxiv.org/abs/2605.28710;*Challenges & Recommendations for LLMs-as-a-Judge in Multilingual Settings & Low-Resource Languages*, https://arxiv.org/html/2607.02235;*Mitigating Translationese Bias in Multilingual LLM-as-a-Judge*, https://arxiv.org/abs/2603.10351(皆 2026)

**產業一手**
- Harvey, *Introducing BigLaw Bench*, https://www.harvey.ai/blog/introducing-biglaw-bench(2024-09);程式碼 https://github.com/harveyai/biglaw-bench
- Thomson Reuters Institute, *From Testcase to Trust: Benchmarking CoCounsel with Scorecard*, https://www.thomsonreuters.com/en-us/posts/innovation/from-testcase-to-trust-benchmarking-cocounsel-with-scorecard/(2025)

> 註:少數 2026 年 arXiv 編號屬預印本,結論作為佐證趨勢用;核心設計主張皆有官方(Anthropic)+ 資深實務者(Hamel/Yan/Shankar)+ 經同儕審查頂會論文(Zheng/JudgeBench/UIST)三方交叉支持。
