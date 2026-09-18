---
title: OPKS 原始生成與 grounding：棄權、引證、分段與 schema 設計的證據基礎
date: 2026-08-01
purpose: >
  為 O(工作產出)／P(行為指標)／K(知識)／S(技能)／A(態度)這一階段的 model-facing schema
  與 prompt 設計提供裁決依據。核心風險是這一格最容易被模型憑職稱先驗填滿;
  設計目標是「寧可留 unknown,不可虛構」。本研究不作決策,決策另開 ADR 或 plan。
source_discipline: >
  只收模型供應商官方文件(Anthropic／OpenAI／Google／OpenRouter)、arXiv 原始論文(標 ID 與版本)、
  頂會 official proceedings、大廠官方 engineering blog。全部條目於 2026-08-01 實際 WebFetch 原始頁面;
  無法取得原文者一律列入 §10「查不到／需二次確認」,不憑記憶補寫。
---

> **【現行裁決】** 本檔是**研究原料**。OPKS 的現行裁決是
> **[ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)
> ＋ [0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)
> ＋ [0050](../adr/0050-opks-proposal-minimal-shape.md)
> ＋ [0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)**（四份一起讀）。
> 本檔建議凡與四份 ADR 不符者，**一律以 ADR 為準**。
>
> **本檔特別注意**：文中多處寫「每個 Task 一次呼叫、**五格**同批」（§表 3、§277–278）。
> **ADR 0048 決定 8 已改為每個 Task 四格（O/P/K/S），態度（A）走文件層另處理**，
> 不進 per-Task 呼叫。照本檔原文施工會把態度掛回每個 Task——而那正是證據上最會膨脹的一格。

前置:`2026-07-31-context-engineering-model-facing-contract-research.md`(context 預算、規則放介面)
與 `2026-07-31-anthropic-strict-schema-grammar-limit-research.md`(strict grammar 的 union 16／optional 24
上限)。本研究不重寫那兩份的結論,只在它們之上回答 OPKS 特有的問題。

---

## 0. 裁決摘要(每條都對應下面一節的證據)

| # | 問題 | 建議 | 主要依據 |
|---|---|---|---|
| 1 | unknown 怎麼表示 | **不用 nullable、不用空字串**。優先用「可為空的 array」讓「沒有」不需要任何 sentinel;固定欄位則用 `evidence_status` enum,把誠實出口做成 enum 的一個合法值 | S10、S12、S13、S4 |
| 2 | 要不要強制 evidence span | **要,而且必須是逐字子字串 + deterministic 檢查**。但它不是防虛構的保證,只是把虛構移到抓得到的位置 | S1、S2、S7 |
| 3 | 一次 vs 分段 | **Task 一次呼叫;OPKS 以「每個 Task 一次呼叫、五格同批」分段**。不要五格各一次 | S11、S3、S6 |
| 4 | schema 誘導 | 拿掉 `minItems: 1`;enum 一定要含誠實出口;required 欄位數 = 填表壓力;`description` 寫判準不寫規格代號 | S5、S8、S9、S12、S14 |
| 5 | 驗證分工 | 逐字／指涉／跨欄位一致性 → deterministic;「這段引文是否真的支持這個 K/S」→ 只能靠模型(本輪先不做) | S1、S2、S7、S15 |
| 6 | 新能力 | Citations 與 structured outputs **官方明文互斥**;Anthropic Messages API **無 logprobs**;effort/thinking 不等於更誠實 | S2、S16、S17、S10 |

---

## 1. Q1 — Abstention:讓模型說「不知道」

### 1.1 官方立場(唯一一條直接的官方指引,且是定性的)

Anthropic 官方 hallucination 指南把「允許說不知道」列為第一條基本策略:

> "**Allow Claude to say "I don't know":** Explicitly give Claude permission to admit uncertainty.
> This simple technique can drastically reduce false information." — S2

其示例把出口寫成**一個具體字串**,而不是抽象許可:

> "If you're unsure about any aspect or if the report lacks necessary information, say
> "I don't have enough information to confidently assess this."" — S2

同頁的但書必須一起讀:

> "while these techniques significantly reduce hallucinations, they don't eliminate them entirely." — S2

**含意**:官方沒有給任何數字。「drastically reduce」是 Anthropic 自己的定性措辭,不能當成量化依據。
可以據此設計,不能據此宣稱效果。

### 1.2 為什麼「有空格就會填」有理論解釋

OpenAI + Georgia Tech 的論文把幻覺歸因於**評分機制**而非模型缺陷:

> "Under binary grading, abstaining is strictly sub-optimal. IDK-type responses are maximally
> penalized while an overconfident "best guess" is optimal." — S10(arXiv 2509.04664v1, 2025-09-04;
> Kalai/Nachum/Zhang @ OpenAI,Vempala @ Georgia Tech)

他們給出的修法是把**信心門檻寫進題目本身**:

> "Answer only if you are >t confident, since mistakes are penalized t/(1−t) points, while correct
> answers receive 1 point, and an answer of "I don't know" receives 0 points." — S10

**對本產品的含意(重要)**:我們的 schema + prompt **就是模型面對的評分規則**。
一個 required 的 `knowledge` 字串欄位,對模型而言等同於「不填必扣分」的題目——留空是格式違規,
編一個「熟悉 Java」則完全合規。**所以「寧可留 unknown」不能只寫在 prompt 散文裡,
必須讓「留白」在 schema 層面是一個合法且明確的動作**,否則我們是在用 prose 對抗自己設的評分函數
(這正是前一份 context engineering 研究 P4「規則放進介面」的同一條原則)。

### 1.3 反直覺證據:更會推理 ≠ 更會棄權

Meta FAIR 的 AbstentionBench(20 個資料集、20 個 frontier model):

> "Evaluating 20 frontier LLMs reveals abstention is an unsolved problem, and one where scaling
> models is of little use. While recent reasoning LLMs have shown impressive results in complex
> problem solving, surprisingly, we find that **reasoning fine-tuning degrades abstention
> (by 24% on average)**, even for math and science domains on which reasoning models are explicitly
> trained. We find that while a carefully crafted system prompt can boost abstention in practice,
> it does not resolve models' fundamental inability to reason about uncertainty."
> — S3(arXiv 2506.09038v1, 2025-06-10)

**含意**:兩件事同時成立——(a) 換更強／更會思考的模型**不會**自動降低這一格的虛構風險,
把 Opus 5 的 effort 拉高也不是解方(§6.3);(b) system prompt 有幫助但有上限,
所以**deterministic 安全網不是可選項**。

### 1.4 unknown 在 JSON schema 裡怎麼表示最有效(有實證的部分)

三份 2025–2026 的實證材料直接對到這個問題。

**(a) 三態語意是有價值的,而且要在評測層被分開。** ExtractBench(Contextual AI)的評測框架:

> 明確區分三種值狀態:present(有抽出)、null(明確為空)、MISSING(輸出中不存在),
> 並據此把錯誤分成 **hallucination(捏造不存在的資訊)vs omission(漏抽存在的資訊)**。
> — S11(arXiv 2602.12247v2, 2026)

**(b) 但三態本身也是分歧的來源。** 臨床出院摘要的 schema 敏感度研究,
用 `yes/no/not_documented` 三態:

> "collapsed the schema to binary" 之後 "dissolves most of the cross-prompt disagreement,
> locating it on the **absence-versus-silence** distinction rather than on whether the finding
> is present." — S12(arXiv 2606.05970, 2026-06-04)

也就是說:模型對「這件事沒有發生」與「這件事沒被提到」的區分**極不穩定**,
跨 prompt 的不一致幾乎全部集中在這條軸上。

**(c) 加一個 "Unknown" 選項本身會改變行為,而且可能只是表面模仿。**

> 加入 "Unknown" 選項、或把它換成**隨機不相干的詞**,在 True/False 題上造成**相同**的準確度下降;
> 作者稱之為 *Abstention Inflation*,結論是模型可能 "imitate the surface pattern of abstention,
> rather than … express genuine uncertainty." — S13(arXiv 2507.16199,v1 2025-07-22,v6 2026-06-03)

**綜合裁決(對 OPKS)**:

1. **首選:讓「沒有」不需要任何 sentinel。** O/P/K/S/A 天然是**清單**,不是固定欄位。
   把它們設計成 array,則「這個 Task 沒有可舉證的 K」= 空 array,不需要 null、不需要空字串、
   不需要 `"none"`。這同時避開 S12 的 absence-vs-silence 軸(沒有「填了一格說沒有」這件事可做),
   也避開 Anthropic 的 union 預算(前置研究:union 上限 16,是我們撞到 400 的維度)。
2. **必須是固定欄位時,用 enum 不用 nullable。** 我們的 wire 已經在做這件事
   (`llm/wire.py`:`""`／`"none"`／`0` 的中性值,零 `anyOf`)。OPKS 若需要「這一項的證據強度」,
   應該是 `evidence_status: quoted | inferred | insufficient` 這種 **enum**,
   而不是 `knowledge: str | None`。理由:enum 在 grammar 上便宜(不是 union)、
   語意明確(不會像 `""` 一樣把「沒有」與「空字串」混同)、且 verifier 可以直接 key 在上面做交叉檢查。
3. **不要對每一格都開 unknown 值。** S13 是這條的直接依據:多開一個選項本身就會改變分佈。
   只在**確定需要三態**的地方開,其餘用「不輸出這一項」表達。
4. **不要相信 status 欄位。** 它是給 verifier 用的一個可檢查的宣告,不是模型內部信心的真實讀數(S13)。
   `insufficient` 必須連動 deterministic 檢查(內容欄位必須為空、evidence 必須為空),
   否則模型可以同時宣告 `insufficient` 又填滿內容。

---

## 2. Q2 — Grounding／引用:evidence span 到底有沒有用

### 2.1 硬事實:Anthropic 的 Citations 功能不能用在我們的路徑上

官方文件的 Warning 原文:

> **"Citations and structured outputs are incompatible"**
>
> "Citations cannot be used together with structured outputs. If you enable citations on any
> user-provided document (`document` blocks or `search_result` blocks) and also include the
> `output_config.format` parameter … the API returns a 400 error."
>
> "This is because citations require interleaving citation blocks with text output, which is
> incompatible with the strict JSON schema constraints of structured outputs." — S1

同樣的限制也套用在 `search_result` content block(S16,2025-08-08 GA)——它是 citations 的 RAG 版本,
被同一句 Warning 涵蓋。

**含意**:「用官方 citations 功能來保證引文有效」這條路**在 structured output 下不存在**。
再加上 ADR 0040 決定 26 選的是 portable strict schema 走 OpenRouter,citations 是 Anthropic 專屬 API,
本來也不可攜。**我們只能自己做 prompt-level 的 evidence span + 自己的 deterministic 檢查。**
這不是次佳選擇,而是唯一選擇——而我們已經有這個機制(§2.4)。

### 2.2 官方對 prompt-level 引用的說法與代價

Anthropic 對 citations 功能相對於 prompt-based 引用的三點宣稱:

> * "**Cost savings:** If your prompt-based approach asks Claude to output direct quotes, you may see
>   cost savings because `cited_text` does not count toward your output tokens."
> * "**Better citation reliability:** … citations are guaranteed to contain valid pointers to the
>   provided documents."
> * "**Improved citation quality:** In Anthropic's evaluations, the citations feature is significantly
>   more likely to cite the most relevant quotes from documents than purely prompt-based approaches." — S1

> "Enabling citations incurs a slight increase in input tokens because of system prompt additions
> and document chunking." — S1

**含意(這是 evidence span 的真實成本表)**:我們走 prompt-level,所以
(a) **引文字元要付 output token**(官方明說 citations 功能才免);
(b) **指標有效性沒有 API 保證**,要自己驗;
(c) 引文品質預期**低於**官方功能(官方自評語)。三項都是我們要自己吃下的成本。

同一份 hallucination 指南把 prompt-level 的做法寫得很具體,值得直接照抄形狀:

> "**Use direct quotes for factual grounding:** For tasks involving long documents (>20k tokens),
> ask Claude to extract word-for-word quotes first before performing its task." — S2

> "After drafting, review each claim … For each claim, find a direct quote from the documents that
> supports it. If you can't find a supporting quote for a claim, **remove that claim**." — S2

> "**External knowledge restriction**: Explicitly instruct Claude to only use information from
> provided documents and not its general knowledge." — S2

最後一條對 OPKS 特別重要:K/S/A 的虛構來源正是「軟體工程師 → Java」這種 parametric prior,
而 external knowledge restriction 是官方唯一針對這個機制的指引。

### 2.3 實證:要求引用**不會**讓引用變正確

ALCE(EMNLP 2023,Princeton NLP)是這條線的標準評測。定義與數字:

- **Citation recall**:該敘述是否**完全**被所引段落支持(逐句 0/1 再平均)。
- **Citation precision**:偵測不相干引用(移除它不影響其餘引用的支持力,且它自己也不能單獨支持)。

vanilla prompting 的引用品質:

| 資料集 | Citation Recall | Citation Precision |
|---|---:|---:|
| ASQA | 73.6% | 72.5% |
| QAMPARI | 20.5% | 20.9% |
| ELI5 | 51.1% | 50.0% |

> 在 ELI5 上,"around 50% generations of our ChatGPT and GPT-4 baselines are not fully supported by
> the cited passages." — S7(EMNLP 2023 main, pp. 6465–6488;arXiv 2305.14627)

代價面:ALCE 的分析顯示要求引用**沒有明顯傷害流暢度**(MAUVE 維持高分),
但相對 closed-book 基線在正確性上有輕微代價。

**含意(直接影響裁決)**:**「要求輸出 evidence span」與「內容真的有據」是兩件事。**
在最難的任務上,一半的生成即使附了引文也不被引文支持。
所以 evidence span 的價值**不在於它本身降低虛構**,而在於它**把虛構搬到一個可以被程式抓到的位置**:
一段宣稱逐字的引文,是否真的逐字出現在員工說過的話裡,是 O(1) 的字串檢查。
沒有引文欄位,虛構就完全不可檢;有了引文欄位,至少「引文本身是編的」這一類會被 100% 攔下。

### 2.4 我們已經有這個機制,OPKS 應該沿用而不是另發明

`app/job_analysis/llm/result.py` 的 `SignalAnchor(turn_ordinal, quote)` 加上
`app/job_analysis/application/verifier.py` 的四個 code,已經是上面推論的完整實作:

| ViolationCode | 檢查 |
|---|---|
| `ANCHOR_MISSING` | 每個 signal 至少一個 anchor |
| `ANCHOR_TURN_UNKNOWN` | 指到的回合必須存在於 packet |
| `ANCHOR_TURN_NOT_EMPLOYEE` | 只能引員工說的話,不能引顧問自己上一輪的話 |
| `QUOTE_NOT_VERBATIM` | `anchor.quote not in turn.text` → 拒 |

`ANCHOR_TURN_NOT_EMPLOYEE` 是這裡最值得保留到 OPKS 的一條:它在結構上禁止**自我循環引用**
(模型引自己上一輪生成的內容當證據)。OPKS 的證據面比 Task 更廣(可能來自上傳文件而非只有對話),
但同一條原則要保留:**證據來源必須是員工或文件,不能是模型自己的前一輪輸出。**

---

## 3. Q3 — 一次生成 vs 分段生成

### 3.1 官方判準

> "This workflow is ideal for situations where the task can be easily and cleanly decomposed into
> fixed subtasks." … "The main goal is to **trade off latency for higher accuracy, by making each
> LLM call an easier task**." … "You can add **programmatic checks** (see 'gate' …) on any
> intermediate steps to ensure that the process is still on track." — S6(Anthropic, Building effective agents)

> "For complex tasks with multiple considerations, **LLMs generally perform better when each
> consideration is handled by a separate LLM call**, allowing focused attention on each specific aspect." — S6

> "we recommend finding the simplest solution possible, and only increasing complexity when needed"
> … "consider adding complexity *only* when it demonstrably improves outcomes." — S6

OpenAI 在 structured outputs 指南裡給了同方向的一句:

> "Structured Outputs can still contain mistakes. If you see mistakes, try adjusting your
> instructions, providing examples in the system instructions, or **splitting tasks into simpler
> subtasks**." — S5

### 3.2 實證:綁定變數是**輸出量**,不是輸入長度或巢狀深度

ExtractBench 是目前最直接的量化證據(35 份文件、2,076 頁、12,867 個可評欄位):

- 369 欄位的 SEC 10-K/Q schema:**"no model produced valid output for any of the seven documents"**;
  全體 aggregate pass rate **4.6%**。
- **決定成敗的是總輸出量,不是輸入文件長度、也不是巢狀深度**:
  credit agreement 平均 137 頁(最長)、壓縮比 682×,但只需 **0.9k output tokens** → pass rate **56.3%**;
  research paper 的 schema 寬度相同,卻因為 100+ 引用陣列需要 **25k output tokens** 而大量失敗。
- **結構有效 ≠ 內容正確**:sports results **90%** valid JSON,但 field-level pass rate 只有 **12.5%**。
- **constrained decoding 反而更糟**:開啟後整體 validity 從 **51% → 37%**、pass rate 從 **6.9% → 5.5%**,
  原因是 schema 拒絕門檻與剛性結構強制,讓輸出**無法優雅降級**。 — S11(arXiv 2602.12247v2, 2026)

格式限制對推理能力的代價(EMNLP 2024 Industry Track,pp. 1218–1236):

> "Surprisingly, we observe a **significant decline in LLMs reasoning abilities under format
> restrictions**. Furthermore, we find that **stricter format constraints generally lead to greater
> performance degradation in reasoning tasks**." — S8(arXiv 2408.02442v3;EMNLP 2024 Industry)

### 3.3 對 OPKS 的裁決

我們的候選是三種:(甲) O/P/K/S/A 五格與 Task 同一次呼叫;(乙) 每格一次呼叫(5×);
(丙) 先 Task,再以 Task 為單位一次生成五格。

**建議(丙)**,理由逐條對到證據:

- **反對(甲)**:S11 指認的綁定變數是總輸出量。把 Task 判斷 + N 個 Task × 5 格塞進一次呼叫,
  輸出量隨 Task 數線性膨脹,正好踩在 369-field schema 全滅的那個模式上。
  而且 schema 的 union／property 數也會再度逼近前置研究記錄的 grammar 上限。
- **反對(乙)**:S6 的 sectioning 條件是「**cleanly decomposed**」。K 與 S 對同一個 Task 而言
  共享同一組證據與同一段脈絡(「他要判讀 X 報表」同時支撐一條知識與一條技能),
  拆開會讓五次呼叫各自重讀同一段脈絡、各自獨立產生一份猜測——**填表壓力被乘以 5,而不是被消除**。
  另外 5× 呼叫在本機單人產品上是實打實的延遲與費用。
- **支持(丙)**:每次呼叫只處理**一個 Task 的五格**,輸出量被 Task 粒度天然封頂
  (S11 的 credit-agreement 情境:短輸出 → 高通過率);符合 S6 的「each LLM call an easier task」;
  而且 Task 之間本來就相互獨立,是真正 cleanly decomposed 的切法(S6 的條件成立)。
  兩階段之間可以放 programmatic gate(S6 明文建議),而我們已經有 verifier 這個 gate。

**關於「填表效應」的誠實結論**:我沒有找到一篇直接測量「schema 空格數 → 虛構率」的論文
(§10)。但三條間接證據指向同一結論並且互相獨立:
S10 的評分理論(留白必扣分則猜測最優)、S11 的 369-field 全滅 + 90% valid/12.5% correct、
S13 的 Abstention Inflation(多一個選項就改變分佈)。
**可以據此設計,不可以宣稱「已有實證證明填表效應」。**

---

## 4. Q4 — Schema 設計對虛構的影響

### 4.1 required vs optional:兩家官方的取捨相反

> "All fields or function parameters must be specified as `required`." — S5(OpenAI)
> "It is possible to emulate an optional parameter by using a union type with `null`" — S5

Anthropic 則對 union 本身設下 16 的上限(前置研究已記錄),Google 的說法是:

> "To allow a property to be null, include `"null"` in the type array (e.g., `{"type": ["string", "null"]}`)"
> ,並警告 "**Very large or deeply nested schemas may be rejected**" — S14(Google, Gemini structured output)

**含意**:「用 nullable 表達 optional」是 OpenAI／Google 的慣例,但在 Anthropic 是最貴的維度。
我們的 wire 已經走中性值路線(零 `anyOf`),**OPKS 必須沿用同一條路線,不能因為新欄位就退回 nullable**。
更重要的是:即使照 OpenAI 慣例,**required + nullable 仍然是「一定要輸出這個 key」**,
差別只在允不允許填 null——所以 required/optional 這一維**根本不是**避免填表效應的槓桿。
真正的槓桿是 §1.4 的「用可為空的 array 讓這一項根本不必存在」。

### 4.2 array 的 `minItems`

Anthropic strict 只支援 `minItems` 的 0 與 1(前置研究已記錄)。
**建議:OPKS 的 O/P/K/S/A array 一律不設 `minItems: 1`。**
`minItems: 1` 在 grammar 層面等於「這個清單不准是空的」——對一個「寧可留 unknown」的產品,
這是把虛構寫進契約。任何「至少要有一項」的期待應該由 verifier 產生**警告**或由員工決策處理,
不是由 grammar 強制。

### 4.3 enum

Anthropic 支援 enum(strings/numbers/bools/nulls);OpenAI 上限 1,000 個值(S5)。
enum 的行為含意是:**它把模型逼進一個封閉值域**。這對 `EnablerKind` 這種分類是正確的,
但意味著 **enum 必須自帶一個誠實出口**,否則 enum 本身就是虛構誘餌
(模型無法表達「都不是」時,只能挑一個最像的)。我們的 wire 已經用 `"none"` sentinel 做了這件事,
OPKS 的任何新 enum 要延續這個慣例。

### 4.4 `description` 與命名:官方說有用,但要寫對東西

> "Create clear titles and descriptions for important keys in your structure" 以 "maximize the quality
> of model generations";"Name keys clearly and intuitively." — S5(OpenAI)

這與前置 context 研究「拿掉 `title`／`description`」**不矛盾**:那份研究量到我們的 description
承載的是 `§12.3`、`TI-R1-08` 這類**模型看不懂的內部規格代號**(佔 schema 27.4%),那是雜訊也是幻覺誘餌。
**裁決:OPKS 的 `description` 只寫模型判斷需要的判準**(例如「knowledge 指可被說出的事實性內容;
skill 指經練習才能做到的操作」),不寫規格章節號、不寫 verifier 已經在檢查的規則。

### 4.5 schema 品質本身可以是槓桿(實證)

> PARSE 指出既有做法 "treat JSON schemas as **static contracts designed for human developers**,
> leading to suboptimal extraction performance, **frequent hallucinations**, and unreliable agent
> behavior when schemas contain ambiguous or incomplete specifications";
> 以 schema 最佳化在 SWDE 上取得 **64.7%** 抽取準確度提升,並在第一次 retry 內減少 **92%** 的抽取錯誤。
> — S9(arXiv 2510.08623, 2025-10-08)

**含意**:這是「schema 是給模型的介面而不是給開發者的資料類別」這條原則的**外部量化支持**,
與我們前一份研究把 wire contract 與 domain model 分離的決定同向。OPKS 的 wire 形狀應該由
「模型怎麼判斷」決定,不是由 `domain/task.py` 的 `Enabler` 直出。

### 4.6 schema 合規完全不能當作真實性的證據

> "Every model exceeds 84% JSON Pass, yet **no model surpasses 80.4% Value Accuracy**."
> 最佳 Value Accuracy(exact leaf-value match):text **83.0%**、image **67.2%**、audio **23.7%**,
> 而 schema compliance 最佳可達 **99.97%**(text)。
> "Structured hallucinations are harder to catch. When a model hallucinates inside a JSON field,
> the output looks authoritative: correct format, correct types, plausible value."
> — S15(The Structured Output Benchmark,arXiv 2604.25359v1, 2026-04-28)

(註:80.4% 與 83.0% 兩個數字來自同一篇的不同切面——前者是跨來源的總體上限敘述,
後者是 text 子集最佳值;引用時要標清楚是哪一個。)

**含意**:99.97% 合規 / ≤83% 正確 的落差,量化了「strict schema 保證的是形狀,不是真相」。
這正是 OPKS 最危險的地方:一條格式完美、型別正確、看起來合理的 `"熟悉 Java"`,
不會被任何 schema 機制擋下來。

---

## 5. Q5 — 驗證分工:哪些歸程式,哪些只能靠模型

### 5.1 官方對 eval 的取向

> "**Automate when possible**: Structure questions to allow for automated grading (for example,
> multiple-choice, string match, code-graded, LLM-graded)." — S17(Anthropic, Create strong empirical evaluations)

> "**Prioritize volume over quality**: More questions with slightly lower signal automated grading is
> better than fewer questions with high-quality human hand-graded evals." — S17

> "Generally best practice to use a **different model** to evaluate than the model used to generate
> the evaluated output" — S17(官方範例碼註解,出現在每一個 LLM-grading 範例)

ALCE 的做法是同一件事的學術版:citation 是否**支持**該敘述,他們用 **NLI model** 判定(S7)——
也就是說,連學術界的標準做法都承認「支持關係」這一層無法用字串比對解決。

### 5.2 分工建議(對 OPKS)

**A. 必須是 deterministic(程式,零模型參與)**

1. **引文逐字**:`quote in source_text`。我們已有 `QUOTE_NOT_VERBATIM`,OPKS 直接沿用。
2. **來源合法性**:引到的回合／文件必須存在,且**不得是模型自己上一輪的輸出**
   (現行 `ANCHOR_TURN_NOT_EMPLOYEE` 的推廣)。
3. **指涉存在**:每一條 O/P/K/S/A 必須掛在一個存在且未退休的 Task ordinal 上。
4. **狀態一致性**:`evidence_status == insufficient` ⇒ 內容欄位與 evidence 皆為空;
   反之非空內容 ⇒ 至少一條 anchor。這是把 §1.4 的第 4 點變成可執行的檢查。
5. **重複與空值**:同一 Task 下重複的 K/S 條目、空字串、只有標點的內容。
6. **跨欄位組合**:延續現行 `_PAYLOAD_FIELD_BY_DISPOSITION` 那一類的表驅動檢查。

**B. 只能靠模型／rubric(本輪建議不做,列為未來縫)**

1. **entailment**:這段引文是否**真的支持**這條知識/技能判斷(ALCE 用 NLI 的那一層)。
2. **分類正確性**:這一項到底是 knowledge 還是 skill、是 output 還是 indicator。
3. **可觀察性**:這條行為指標是否真的可被觀察/衡量。

**C. 只能靠員工**

「這是不是我真正在做的事」——這已經是現行 Proposal → 員工決策的設計,OPKS 沿用即可。
S3 的結論(棄權是未解問題、system prompt 有上限)是保留這道人工關卡的直接理由。

**取捨陳述**:B 類全部要另一次 LLM 呼叫(S17 還要求換一個模型),成本與延遲都是真的,
而且判斷層依 memory 的既有規則不得用便宜模型驗。**本輪建議只做 A**,把 B 記成一行未來縫,
不要在 OPKS 首版就引入 judge 迴圈。

---

## 6. Q6 — 2025–2026 有哪些「官方確實有」的新能力

### 6.1 可用

| 能力 | 狀態 | 對本產品 |
|---|---|---|
| **Structured outputs** | Claude API **GA 2026-01-29**(Sonnet 4.5／Opus 4.5／Haiku 4.5);2025-11-14 beta(`structured-outputs-2025-11-13`)。GA 含 "expanded schema support, improved grammar compilation latency";`output_format` → `output_config.format` — S16 | 已在用。grammar 上限見前置研究 |
| **OpenRouter `structured_outputs`／`response_format`** | 有,但 "some guarantee schema-conforming output, while others translate your schema into their own structured-output format or **treat it as a strong hint**, so exact compliance is not guaranteed on every endpoint" — S4 | **我們走 OpenRouter,所以 strict 不是端到端保證**,本地 verifier 是必需品而非備援 |

### 6.2 明確**不可用**

| 能力 | 事實 | 依據 |
|---|---|---|
| **Citations 功能** | 與 structured outputs **互斥,同時送出回 400** | S1 |
| **`search_result` content blocks** | 同上;它是 citations 的 RAG 形式(2025-08-08 GA) | S1、S16 |
| **Anthropic logprobs** | **Messages API 沒有 `logprobs`／`top_logprobs` 參數**,也沒有任何回傳 token 機率的機制;2026-08-01 逐條看過全部 release notes,**查無** logprobs 字樣 | S16、S18 |
| **OpenRouter logprobs(對 Anthropic 端點)** | OpenRouter **有**記錄 `logprobs`(bool)與 `top_logprobs`(0–20)參數,但明說支援與否看 provider。Anthropic 端點沒有這個能力,所以走 Anthropic 拿不到 | S4、S18 |

**含意**:**「用 logprobs 做 per-field confidence」這條路在我們的 provider 組合下不通。**
替代方案是**verbalized confidence**(把信心寫成輸出欄位),而這在學術上其實比 logits 更好:

> "verbalized confidences emitted as output tokens are typically **better-calibrated than the model's
> conditional probabilities** on the TriviaQA, SciQ, and TruthfulQA benchmarks, often **reducing the
> expected calibration error by a relative 50%**." — S19(Just Ask for Calibration,EMNLP 2023;arXiv 2305.14975v2)

但必須與 S13 的 Abstention Inflation 一起讀:**verbalized 的東西可能是表面模仿**。
所以 confidence 欄位只能當「可被 verifier 交叉檢查的宣告」,不能當門檻閥值直接放行/擋下。

黑箱情境下的替代路線存在但未驗證:CONSTRUCT 宣稱在無 logprobs 的黑箱 API 上做
output-level 與 field-level 的可信度評分,"detects errors in outputs from various LLMs
(including Gemini 3 and GPT-5) with significantly higher precision/recall than existing techniques"
— S20(arXiv 2603.18014v2, 2026-03-31)。**未經我們驗證,列為未來縫,不建議首版採用。**

### 6.3 effort／thinking:不要誤當成誠實度旋鈕

Opus 5 的 `effort` 是主要操控手段,thinking 預設開啟(S16、S21)。但:

- S3 的量化結論是 **reasoning fine-tuning 讓 abstention 平均降低 24%**;
- Opus 5 官方行為說明還指出 "It also **verifies its own work without being told to**, so remove
  verification instructions carried over from earlier models … they cause over-verification" — S21。

**含意**:提高 effort 會提高分析深度,但**沒有任何官方或學術證據說它會提高棄權傾向**,
S3 的證據方向甚至相反。不要把「OPKS 太會編」的問題交給 effort 解決;
也不要在 OPKS prompt 裡加「請再檢查一次」這類自我驗證指示(S21 明說要移除)。

---

## 7. 彙整:對 OPKS schema 與 prompt 的具體建議

**Schema(model-facing wire,延續 `llm/wire.py` 的形狀慣例)**

1. O/P/K/S/A 一律是**可為空的 array**,不設 `minItems: 1`,不用 nullable。「沒有」= 空 array。
2. 每個項目**強制帶 anchors**(`turn_ordinal` 或 `source_ordinal` + 逐字 `quote`),
   與現行 `SignalAnchor` 同形。
3. 需要三態的地方用 **enum**(含誠實出口值),不用 `X | None`、不用 `""`。
   零 `anyOf` 這條紀律要維持到 OPKS。
4. `description` 只寫模型判斷判準;不放 `§`／`TI-Rx-xx` 這類內部代號。
5. schema 形狀由「模型怎麼判斷」決定,不由 `domain/task.py` 的 `Enabler` 直出(S9)。

**Prompt**

6. 明確給出誠實出口的**具體措辭**(S2 的形狀),而不是抽象許可。
7. 明確的 **external knowledge restriction**:只能用員工說過的話與提供的文件,
   不得用對職稱的一般認識(S2)——這是針對 K/S/A 這一格最主要的虛構機制。
8. **不要**加「請再驗證一次」(S21)。驗證是 verifier 的工作,不是 prompt 的。

**流程**

9. Task 與 OPKS **分兩階段呼叫**;OPKS 以單一 Task 為粒度批次生成五格(§3.3)。
10. 兩階段之間放 deterministic gate(S6);A 類檢查全部進 verifier(§5.2)。
11. entailment judge 與 confidence scoring **記成未來縫,首版不做**。

---

## 8. 可下與不可下的結論

**可以說**

- Anthropic 官方明文:citations 與 structured outputs 互斥,同時送出回 400(S1)。
- Anthropic Messages API 沒有 logprobs;走 Anthropic 端點無法用 token 機率做 confidence(S16、S18)。
- 在最佳條件下,schema 合規可達 99.97% 而 value accuracy ≤83.0%(S15);
  複雜 schema 的 aggregate pass rate 可低到 4.6%,且綁定變數是輸出量(S11)。
- reasoning fine-tuning 平均降低 abstention 24%(S3)。
- 要求引用不保證引用成立:ELI5 上約 50% 的生成不被所引段落完全支持(S7)。

**不可以說**

- 「加了 evidence span 就不會虛構」——S7 直接反證。
- 「已有實證證明 schema 空格會誘導模型填滿」——本輪**沒有找到**直接測量此事的論文(§10);
  現有依據是三條間接且互相獨立的證據(S10／S11／S13)。
- 「Anthropic 的『允許說不知道』能降低 X%」——官方只給定性措辭 "drastically reduce",無數字(S2)。
- 「提高 effort/thinking 會讓模型更誠實」——無證據,S3 方向相反。
- 「本產品在 OpenRouter 上有 strict 保證」——S4 明說並非每個 endpoint 都保證合規。

---

## 9. 來源總表(全部於 2026-08-01 實際取用原始頁面)

| # | 來源 | 類型 | 日期／版本 |
|---|---|---|---|
| S1 | Anthropic Docs, [Citations](https://platform.claude.com/docs/en/build-with-claude/citations) | 供應商官方文件 | 2026-08-01 取用(功能 2025-01-23 上線) |
| S2 | Anthropic Docs, [Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations) | 供應商官方文件 | 2026-08-01 取用 |
| S3 | Kirichenko, Ibrahim, Chaudhuri, Bell (Meta FAIR), [AbstentionBench: Reasoning LLMs Fail on Unanswerable Questions](https://arxiv.org/abs/2506.09038) | arXiv | **2506.09038v1**, 2025-06-10 |
| S4 | OpenRouter Docs, [Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)、[API Parameters](https://openrouter.ai/docs/api_reference/parameters) | 供應商官方文件 | 2026-08-01 取用 |
| S5 | OpenAI, [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 供應商官方文件 | 2026-08-01 取用 |
| S6 | Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | 大廠官方 engineering blog | 2026-08-01 取用 |
| S7 | Gao, Yen, Yu, Chen (Princeton), [Enabling Large Language Models to Generate Text with Citations](https://aclanthology.org/2023.emnlp-main.398/) | **EMNLP 2023 main**, pp. 6465–6488 | arXiv 2305.14627 |
| S8 | Tam, Wu, Tsai, Lin, Lee, Chen, [Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of LLMs](https://aclanthology.org/2024.emnlp-industry.91/) | **EMNLP 2024 Industry Track**, pp. 1218–1236 | arXiv **2408.02442**,v1 2024-08-05／v3 2024-10-14 |
| S9 | Shrimal, Jain, Chowdhury, Yenigalla, [PARSE: LLM Driven Schema Optimization for Reliable Entity Extraction](https://arxiv.org/abs/2510.08623) | arXiv | **2510.08623**, 2025-10-08 |
| S10 | Kalai, Nachum (OpenAI), Vempala (Georgia Tech), Zhang (OpenAI), [Why Language Models Hallucinate](https://arxiv.org/abs/2509.04664) | arXiv | **2509.04664v1**, 2025-09-04 |
| S11 | Ferguson et al. (Contextual AI), [ExtractBench: A Benchmark and Evaluation Methodology for Complex Structured Extraction](https://arxiv.org/abs/2602.12247) | arXiv | **2602.12247v2**, 2026 |
| S12 | Murin, [Measuring the sensitivity of LLM-based structured extraction to prompt, model, and schema choices in clinical discharge summaries](https://arxiv.org/abs/2606.05970) | arXiv | **2606.05970**, 2026-06-04 |
| S13 | Ling et al., [LLM Abstention Can Be a Prompt Artifact, in Addition to Genuine Uncertainty](https://arxiv.org/abs/2507.16199) | arXiv | **2507.16199**,v1 2025-07-22／v6 2026-06-03 |
| S14 | Google AI, [Structured output (Gemini API)](https://ai.google.dev/gemini-api/docs/structured-output) | 供應商官方文件 | 2026-08-01 取用 |
| S15 | Singh, Khurdula, Khemlani, Agarwal, [The Structured Output Benchmark](https://arxiv.org/abs/2604.25359) | arXiv | **2604.25359v1**, 2026-04-28 |
| S16 | Anthropic Docs, [Claude Platform release notes](https://platform.claude.com/docs/en/release-notes/api) | 供應商官方文件 | 2026-08-01 取用 |
| S17 | Anthropic Docs, [Create strong empirical evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests) | 供應商官方文件 | 2026-08-01 取用 |
| S18 | Anthropic Docs, [Messages API reference](https://platform.claude.com/docs/en/api/messages) | 供應商官方文件 | 2026-08-01 取用 |
| S19 | Tian, Mitchell, Zhou, Sharma, Rafailov, Yao, Finn, Manning, [Just Ask for Calibration](https://arxiv.org/abs/2305.14975) | **EMNLP 2023** | arXiv 2305.14975v2, 2023-10-24 |
| S20 | Goh, Mueller, [Real-Time Trustworthiness Scoring for LLM Structured Outputs and Data Extraction](https://arxiv.org/abs/2603.18014) | arXiv | **2603.18014v2**, 2026-03-31 |
| S21 | Anthropic Docs, [What's new in Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5) | 供應商官方文件 | 2026-08-01 取用(Opus 5 於 2026-07-24 發布) |
| S22 | Kadavath et al. (Anthropic), [Language Models (Mostly) Know What They Know](https://arxiv.org/abs/2207.05221) | arXiv | 2207.05221,v1 2022-07-11／v4 2022-11-21 |

**S22 的用法說明**:它是 P(True)／P(IK) 這條線的原始出處(Anthropic 自家研究,顯示模型的自評有一定校準,
但跨任務泛化時校準變差)。**它是 2022 年的材料,不是 2025–2026 的最新證據**,
本文只用來標示「模型自評有理論基礎但泛化有限」,不作為裁決依據。

**被排除的來源**(依來源紀律主動剔除):多篇 Medium 文章(含一篇宣稱「Anthropic 2026 已支援 logprobs」
的文章——與 S16／S18 的官方查核直接矛盾,已剔除)、letsdatascience.com、aimodels.fyi、emergentmind.com、
liner.com、researchgate 轉載、MDPI *Applied Sciences* 的 citation-enforced prompting 論文
(期刊非指定頂會,未採用)。

---

## 10. 查不到／需二次確認

1. **「schema 空格數 → 虛構率」的直接量測**:沒找到。所有相關論文(S11／S15)測的是
   value accuracy 與 hallucination-vs-omission,**沒有一篇把「schema 欄位數」當自變數**去測填表傾向。
   §3.3 與 §4 的裁決建立在三條間接證據上,這一點在 ADR 裡必須誠實標註。
2. **S8(Let Me Speak Freely)的逐任務數字**:PDF 抽取只取到定性摘要,
   GSM8K／Last Letter／Shuffled Objects／DDXPlus／NL2BASH 的**確切百分比未取得**。
   本文只引用了摘要中的 verbatim 敘述。要引用具體數字必須另行取得原文表格。
   另注:此論文的方法(尤其 JSON-mode 與 prompt-based 格式限制的混用)在社群有爭議,
   S11 的 constrained decoding 反效果數字(51%→37%)是較新且獨立的佐證。
3. **S15 的 80.4% vs 83.0%**:兩個數字來自同一篇不同切面,本文已標註,
   但**未從全文確認兩者的精確定義差異**,引用時需再核。
4. **S11 的正式發表狀態**:arXiv 2026,**未確認是否已被頂會接收**。
5. **S12／S13／S20 均為單篇 arXiv preprint**,未確認同儕審查狀態;
   S13 的 v6(2026-06-03)相對 v1 有多次修訂,本文引用的是 abstract 層級敘述,
   十次實驗的具體數字未取得。
6. **Anthropic 是否有未公開的 logprobs beta**:只能證明「官方文件與 release notes 查無」,
   不能證明「不存在」。若之後要靠 logprobs 做 confidence,需要重新查核。
7. **「兩階段呼叫比一次呼叫在本產品上更好」沒有我們自己的實證**。S6／S11 是他人證據。
   本產品沒有 eval——這是前一份研究就記下的同一個缺口,OPKS 會把它放大,
   因為 K/S/A 的正確性比 Task 更難用 verifier 判定。**是否要建最小 eval 是獨立決策,不在本研究範圍。**
