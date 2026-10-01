# LLM 應用「可靠、可信、可驗證」工程實務研究(2025–2026)

> 純學習研究,站在巨人肩膀上、不犯前人的錯。來源以模型廠官方文件/工程文章、原廠框架、官方規範、頂會論文為主。
> 撰寫日期:2026-07-12。每條發現標來源 URL + 發布日期(見末節總表)。
> 名詞保留英文。

---

## 1. 結構化輸出(Structured Outputs)2026 現況

**結論.** 三大廠都已把「schema 即契約」從 prompt 祈禱升級成 **constrained decoding(把 JSON schema 編成 grammar,解碼時 mask 掉不合法 token)**,結構合規已是**數學保證**而非機率。但三方都明確警告:**保證的是「形狀」不是「內容」**——結構對了,值仍可能自信地錯。真正的坑在 schema 子集限制、enum 大小寫、schema 太大/太深退化、以及 refusal / max_tokens 造成的「合法回應但殘缺」。

**關鍵證據.**
- Anthropic Structured Outputs 已 GA(前身 beta header `structured-outputs-2025-11-13`),兩種模式可獨立或併用:**JSON outputs**(`output_config.format`)與 **strict tool use**(`strict: true`,保證 tool 名稱與參數完全符合 schema)。官方原話:透過 "constrained sampling with compiled grammar artifacts" 保證合規,好處是「**Always valid**: No more `JSON.parse()` errors … **Reliable**: No retries needed for schema violations」。(platform.claude.com/docs, GA 版)
- Anthropic 明列的 **schema 子集限制**很實際:支援 `enum`/`const`/`anyOf`/`$ref`/`$def` 與常見 string format;**不支援** recursive schema、`minimum`/`maximum`/`minLength`/`maxLength` 等數值/字串約束;`additionalProperties` 必須為 `false`。硬上限:**每請求最多 20 個 strict tools、24 個 optional 參數、16 個 union-type 參數**。
- Anthropic 明列的「**無效輸出**」情境:`stop_reason: "refusal"`(安全拒絕,回 200 且照樣計費,可能不符 schema)、`max_tokens`(截斷不完整)、以及 **enum 大小寫**——「Claude may return enum values differing only in capitalization from your schema」。
- OpenAI Structured Outputs(`strict: true`)同樣用 constrained decoding,官方限制一致:`additionalProperties` 必為 `false`、所有欄位須 required(optional 用與 `null` 的 union 表達)、不支援 `minimum`/`maximum`/`minLength`、root 必須是 object 而非 `anyOf`、property/nesting 有上限(約 5000 props、5 層)。**新 schema 首次請求有額外延遲**(API 需編譯 grammar),之後同 schema 免。安全拒絕改為以顯式 **refusal 欄位** programmatically 可偵測。
- 業界資深實務者的一句話總結廣被引用:「constrained decoding makes invalid output impossible, so **stop engineering for malformed JSON and start engineering for the harder problem it exposes: a perfectly shaped answer can be confidently wrong** … constrain the wire format, never the thinking, and **measure meaning, not just shape**.」(Collin Wilkins, 2026)

**對「別犯前人錯」的啟示.**
- **schema 是 wire format 的契約,不是思考的契約**:用 constrained decoding 保證可 parse,但**仍要對「值」做語意驗證**(business rule、交叉一致性)。不要因為 JSON 合法就當內容可信。
- **enum 一律做 case-insensitive 正規化 / 白名單映射**,別假設模型回傳大小寫跟 schema 一致。
- **schema 別無限膨脹**:太大/太深會退化且撞上廠商硬上限;拆成小而聚焦的 schema、必要時分多次抽取。數值/長度約束多半**不被 constrained decoding 支援**,要在**應用層另做 validation**(不能指望 schema 幫你擋範圍)。
- **一定要處理 `refusal` 與 `max_tokens`**:合法回應不等於完整回應;把這兩個 stop_reason 當一級錯誤路徑。

---

## 2. 對話式引導 / 訪談型應用(elicitation / 需求引導 / 表單填寫)

**結論.** 官方層級最權威的參考是 **MCP 的 `elicitation` capability(2025-06-18 spec)**:它把「聊天中途向使用者要缺漏資訊」正規化為**帶 JSON schema 的結構化請求**,並刻意把 schema **限制為「扁平物件 + primitive 型別」**以利 client 生表單、驗證、給引導。三動作回應模型(accept / decline / cancel)是覆蓋率與放行設計的核心。設計哲學是**「自然對話負責理解與蒐集,結構化 schema 負責把欄位收齊、驗證、保存狀態」兩層分工**。

**關鍵證據.**
- MCP spec 定義:elicitation 讓 server「request additional information from users through the client」,且「Servers request **structured data from users with JSON schemas to validate responses**」,並可「**nested inside other MCP server features**」(即在別的流程中途插入問答,保住 workflow 狀態)。
- **schema 刻意受限**:「elicitation schemas are limited to **flat objects with primitive properties only**」,支援 string / number / boolean / enum(含 `enumNames` 顯示名);「complex nested structures, arrays of objects … are **intentionally not supported to simplify client implementation**」。client 可用此 schema「Generate appropriate input forms / **Validate user input before sending** / Provide better guidance to users」。
- **三動作回應模型**(覆蓋率/放行的關鍵):**accept**(帶 `content` 符合 schema)、**decline**(明確拒答)、**cancel**(未做選擇即關閉)。spec 要求 server「handle each state appropriately」:decline → offer alternatives;cancel → prompt again later。
- **安全紅線**:「Servers **MUST NOT** use elicitation to request sensitive information」(PII/credentials 走 out-of-band),client **SHOULD** 顯示哪個 server 在要資料、允許使用者隨時 decline、實作 rate limiting、並「present … in a way that makes it clear **what information is being requested and why**」。

**對「別犯前人錯」的啟示.**
- **把「訪談」拆成兩層**:LLM 負責自然地聊 + 判斷還缺什麼;**一份顯式 schema/欄位清單當 single source of truth**,決定「收齊了沒」。覆蓋率(coverage)= 針對這份 schema 的 required 欄位逐一勾稽,而不是靠模型「感覺聊夠了」。
- **放行條件要確定性**:所有 required 欄位皆 accept 且通過 validation 才放行;decline/cancel 要有明確 fallback(換問法、之後再問、或標記缺漏)。別讓模型自己決定「差不多可以了」。
- **提交前先 client 端 validate**(spec 明講),把「格式/範圍」錯誤在收集階段擋掉,而不是寫入後才發現。
- **問答要可解釋**:每次追問講清楚「要什麼、為什麼」——降低使用者流失,也讓覆蓋率追蹤有據。
- **敏感資訊不要用對話式蒐集**;走安全的 out-of-band 管道。

---

## 3. 忠實性與溯源(grounding / citation / quote)

**結論.** 主流工程做法是**「先引原文、再據原文作答」**:Anthropic Citations API 把來源文件切成句子級 chunk,讓模型**回傳指向確切句子/段落的引用**,內部評測 recall 準確度提升「up to 15%」。但官方與資深來源一致強調關鍵限制:**citation 只保證「引用位置真的存在於來源」,不保證「對引用的詮釋正確」**——citation ≠ hallucination-proof。官方 prompting 指南另給一套不靠 API 也能用的溯源紀律。

**關鍵證據.**
- Citations API:讓 Claude「**ground its answers in source documents**」並「provide detailed references to the **exact sentences and passages** it uses」;機制是「chunking [documents] into sentences」後連同 query 給模型,模型「generates a response that includes **precise citations** based on the provided chunks」;內部評測「increasing **recall accuracy by up to 15%**」。(Anthropic,2025 年初上線)
- 限制(資深轉述,緊貼原意):**Citations only guarantee that "the cited position actually exists in the source" — not that "the interpretation of the citation is correct."** 模型仍可能誤讀文件語意。
- Anthropic 官方「Reduce hallucinations」指南三招 grounding:
  1. **允許「不知道」**:「Explicitly give Claude permission to admit uncertainty … can **drastically reduce false information**」(例:指示回「I don't have enough information to confidently assess this」)。
  2. **先抽 word-for-word 原文再作答**(長文 >20k tokens):「ask Claude to **extract word-for-word quotes first** before performing its task … grounds its responses in the actual text」。
  3. **用 citation 驗證每一項主張**:「have it cite quotes and sources for each of its claims … have Claude **verify each claim by finding a supporting quote** after it generates a response. **If it can't find a quote, it must retract the claim**」。並限制「only use information from provided documents and not its general knowledge」。
  官方 Note:「while these techniques significantly reduce hallucinations, they **don't eliminate them entirely. Always validate critical information**」。

**對「別犯前人錯」的啟示.**
- **寫入型內容要 quote-first**:先讓模型抽逐字原文、標明來源位置,再據原文生成;**找不到支撐 quote 的主張就刪掉/標記空缺**(官方的 `[]` 留白法),而不是讓它自由發揮。
- **明確給「不知道」的出口**,並在 prompt 中限定「只用提供的文件」——這是降幻覺最高 ROI 的一招。
- **不要把 citation 當終點**:citation 保證位置存在、不保證詮釋對。**引用位置可以程式化驗證(deterministic:字串真的在來源裡嗎),詮釋則需另做評測/人審**。高風險內容一律人工複核。

---

## 4. 評測(evals)

**結論.** 2026 主流方法論(以 Anthropic「Demystifying evals for AI agents」為代表)是:**兩套 suite 分工——capability evals(找短板,起始 pass rate 低)vs regression evals(防退步,pass rate 近 100%);capability 打磨到高分後「graduate」成 regression 持續跑防 drift**。LLM-as-judge 是主力但有公認限制,修正法是**每個維度用獨立 judge + 清楚 rubric + 定期對人類專家 calibration**。agent 類要同時評 **trajectory(過程)與 outcome(結果)**。

**關鍵證據.**
- Anthropic(2026-01-09):**capability evals**「ask, 'What can this agent do well?' They should **start at a low pass rate**」;**regression evals**「'Does the agent still handle all the tasks it used to?' and should have a **nearly 100% pass rate**」;「capability evals with high pass rates can **'graduate' to become a regression suite** that is run continuously to catch any drift」。
- Judge 設計:「Create clear, structured rubrics … and then grade each dimension with an **isolated LLM-as-judge rather than using one to grade all dimensions**」;「LLM-as-judge graders should be **closely calibrated with human experts**」;給 judge「a way out … return 'Unknown' when it doesn't have enough information」。
- agent 評測:「Each task can have multiple graders, each containing multiple assertions … evaluating some portion of **either the transcript or the outcome**」(過程與結果都評)。
- LLM-as-judge 公認限制(頂會/實驗室):對**較長輸出、排版良好的回應、無 epistemic marker 的答案有偏好**;**self- / model-family preference**(偏好自家或同族模型輸出);**position bias**(同一變體放第二個位置得分 +8.2、第一個僅 +1.7);**scoring granularity**——「reliable … determining binary factual correctness or rating on a simple 1–5 scale; however, as the scoring scale becomes more detailed … more likely to produce **arbitrary scores**」。修正:**Panels of LLM evaluators(PoLL)用多個小而不同族模型**降 intra-model bias、且更便宜、與人類相關性更高。

**對「別犯前人錯」的啟示.**
- **建立 golden set + 兩套 suite**:capability(推進能力)與 regression(綠前==綠後,防退步)。**每個維度一個獨立 judge**、每個 judge 一份明確 rubric,別用一個 judge 打所有分。
- **judge 要對齊人類**:定期用人審抽樣 calibrate,確認 divergence 小才信任;**用 binary / 粗粒度(1–5)量表**,別追求 1–100 的假精度。
- **警惕 judge bias**:控 position(交換順序)、避免 self-preference(judge 用不同 model family,或用 PoLL 多評審)、別讓長度/排版騙分。
- **agent 要評 trajectory**:不是只看最終答案對不對,還要看過程(用了對的工具、沒走危險步驟)。

---

## 5. 守門與回退(guardrails)

**結論.** 主流是**分層、且把「安全/合規的最後一道」做成 deterministic 且獨立於 LLM**:輸入端(moderation、jailbreak、PII)、輸出端(schema、format、citation validity、PII、hallucination check)、與 runtime。OpenAI Guardrails 用 **pipeline 分 input/output/pre-flight 三階段**、drop-in 取代 client。核心紀律:**安全控制必須 deterministic 且獨立於 LLM——讓模型執行自己的邊界會製造遞迴風險與假信心**。寫入前驗證(擋)與寫入後審核(補)並用,高風險走 human-in-the-loop。

**關鍵證據.**
- OpenAI Guardrails:「a safety framework … **automatically validates inputs and outputs** using configurable checks」,採「**Pipeline-based validation across input, output, and pre-flight stages**」;check 分三類:Content Safety(moderation、jailbreak)、Data Protection(PII、URL filtering)、Content Quality(**hallucination detection**、off-topic)。可 drop-in 換成 `GuardrailsAsyncOpenAI`,每次呼叫自動跑。
- deterministic backstop 原則(業界資深/survey 一致):「**Deterministic checks belong at the base (schema, format, scanners, citation validity)**」;「security controls **must be deterministic and independent of the LLM**, as asking a model to enforce its own boundaries creates **recursive risk and false confidence**」。
- agent 守門趨勢:LLM 管 NLU/工具選擇,**deterministic constraint enforcement 交給 hooks**;「The guardrail agent functions as a **deterministic policy executor**」。2025 的 guardrails「are **not static filters; they are adaptive frameworks**」(AgentSpec DSL、Pro2Guard 機率可達性等 runtime 規則),但底層仍以確定性規則兜底。
- 幾乎所有平台在回應返還前有 content moderation 當 **backstop**;Anthropic 靠 constitution、OpenAI 靠 RLHF 做 model-level 對齊,但那是「內建傾向」不是「保證」。

**對「別犯前人錯」的啟示.**
- **最後一道門要 deterministic**:schema 驗證、格式、citation 位置存在性、PII scanner、business rule——這些**別交給 LLM 判**;「模型守自己的門」=遞迴風險+假安全感。
- **寫入前 vs 寫入後取捨**:能 deterministic 檢查的就**寫入前擋**(schema、必填、範圍、引用存在);需語意判斷的高風險內容**寫入後審核 / human-in-the-loop**。兩者互補,不是二選一。
- **風險分級**:低風險自動放行、高風險強制人審或加確定性 backstop;guardrail 要獨立成層,不要散在 prompt 裡。

---

## 6. 多輪一致性(不重問、不忘記、不自相矛盾)

**結論.** 官方(Anthropic「Effective context engineering」2025-09-29)的核心診斷是 **context rot**:「context window 變大,模型從中準確回憶的能力反而下降」——所以長對話一致性**不是靠塞更多 context,而是靠工程管理最小高信號 context**。三大手段:**compaction(接近上限就摘要後重啟)、structured note-taking(把狀態寫到 context 外的 memory 再取回)、sub-agent(乾淨 context 分工)**。訪談型應用「不重問/不忘記」最穩的做法是**把已收欄位存成 context 外的結構化狀態**,而非依賴模型記住整段對話。

**關鍵證據.**
- context rot:「as the number of tokens in the context window increases, the model's ability to **accurately recall information from that context decreases**」;把 context 當「a **finite resource with diminishing marginal returns**」;目標是找「the **smallest possible set of high-signal tokens** that maximize the likelihood of some desired outcome」。
- **Compaction**:「taking a conversation nearing the context window limit, **summarizing its contents, and reinitiating a new context window with the summary**」,要保留「architectural decisions, unresolved bugs, and implementation details」丟掉冗餘。
- **Structured note-taking**:agent「regularly **writ[e] notes persisted to memory outside of the context window**」再按需取回,「allows the agent to **track progress across complex tasks, maintaining critical context and dependencies**」。
- Anthropic memory/context 工具線(2025):context editing(規則式修剪)、context awareness(回報剩餘容量)、memory tools(跨對話持久存取)。
- 相關工程原則(業界)提醒 reasoning model 會被 **contextual distractors** 干擾(「Lost in the Noise」),更凸顯「少而準」勝過「多而雜」。

**對「別犯前人錯」的啟示.**
- **狀態存在 context 之外**:已收欄位/已確認事實寫成結構化 state(不重問靠「查 state 有沒有這欄」,不是靠模型記憶);每輪把「已知 state 摘要」注回,而非整段歷史。
- **長對話用 compaction**:接近上限就摘要重啟,明確保留決策/未解事項/關鍵細節,丟冗餘——避免 context rot 造成的忘記與自相矛盾。
- **一致性檢查可 deterministic**:新回答和既存 state 衝突時,用程式偵測矛盾並回頭確認,而不是期待模型自己不打架。
- **別靠加大 window 解決記憶問題**:context rot 讓「塞更多」反而更糟;工程重點是策展(curate)最小高信號集合。

---

## 7. 前人踩坑(官方/資深明講的 anti-pattern)

**結論.** 反覆被官方與資深來源點名的錯:**(a) 把 LLM-as-judge 當唯一守門(inverted testing pyramid);(b) 讓模型驗證自己/守自己的門;(c) prompt 補丁螺旋;(d) 忽略確定性檢查;(e) 誤把「結構合法」當「內容正確」。** 共同教訓:**deterministic 檢查放在金字塔底座,LLM 判斷放上層且要 calibrate。**

**關鍵證據.**
- **Inverted testing pyramid**:把 LLM-as-judge 放金字塔底是反模式——實例:一套測試對 200 例跑了 247 次 judge、九個 rubric,judge 對 groundedness 打 **0.91**,十二小時後客戶卻回報 bot **吐出應用無法 parse 的 malformed JSON**。教訓:「**Deterministic checks belong at the base (schema, format, scanners, citation validity)**」。(2025–2026 實務文)
- **別讓模型 grade/守自己**:「**Stop Letting Models Grade Their Own Homework**」——judge 對 prompt-injection 防禦不可靠;「security controls must be **deterministic and independent of the LLM**」,自我守門「creates recursive risk and false confidence」。(Lakera 2025)
- **judge 不穩定本身是坑**:「same input can **score differently across runs**」;position/verbosity/self-preference bias;量表越細越易「produce arbitrary scores」——**過度依賴單一 judge**會累積這些偏誤。
- **結構 ≠ 正確**:「Structured outputs **don't remove uncertainty. They make uncertainty visible.**」;「a perfectly shaped answer can be **confidently wrong**」——把 constrained decoding 當正確性保證是常見誤解。
- **官方對「補丁螺旋」的解方**是往結構化走:Anthropic 靠 rubric + 每維度獨立 judge + 人類 calibration 取代「一直加 prompt 條件」;prompt injection 的權威解方(Simon Willison / 論文「Design Patterns for Securing LLM Agents」2025-06)也是**架構性 design pattern(如把不可信輸入隔離、動作走確定性授權)而非再補一句 prompt**。

**對「別犯前人錯」的啟示(綜合)。**
- **測試金字塔正過來**:底座是 deterministic(schema/format/citation 存在性/scanner/business rule),中層是校準過的 LLM-as-judge,頂層是人審 golden set。judge 高分**不能**取代確定性檢查。
- **凡是安全/正確性的「最後保證」都別交給 LLM**:模型可以生成、可以初判,但**不能是自己的裁判與守門人**。
- **拒絕 prompt 補丁螺旋**:反覆 fail 時優先問「這該用 deterministic 規則/schema/架構解嗎」,而不是再疊一句 prompt。
- **把不確定性顯性化並管理**:constrained decoding 讓不確定性可見(refusal 欄位、殘缺 stop_reason、值的語意錯)——工程重點是**接住這些訊號並驗證語意**,而非假設它們不存在。

---

## 來源總表

| # | 來源(作者/機構) | 標題 | URL | 日期 | 性質 |
|---|---|---|---|---|---|
| 1 | Anthropic | Structured outputs(平台文件,GA) | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | 2025(beta header `structured-outputs-2025-11-13`→GA) | 官方文件 |
| 2 | OpenAI | Structured Outputs 指南 | https://developers.openai.com/api/docs/guides/structured-outputs | 2024-08 起(持續更新) | 官方文件 |
| 3 | OpenAI | Introducing Structured Outputs in the API | https://openai.com/index/introducing-structured-outputs-in-the-api/ | 2024-08-06 | 官方工程文 |
| 4 | Collin Wilkins | LLM Structured Outputs: Schema Validation for Real Pipelines | https://collinwilkins.com/articles/structured-output | 2026 | 署名實務者 |
| 5 | Model Context Protocol | Elicitation(spec 2025-06-18) | https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation | 2025-06-18 | 官方規範 |
| 6 | Anthropic | Introducing Citations on the Anthropic API | https://claude.com/blog/introducing-citations-api(原 anthropic.com/news/…) | 2025 年初(Simon Willison 報導 2025-01-24) | 官方公告 |
| 7 | Anthropic | Reduce hallucinations(平台文件) | https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations | 2025(持續維護) | 官方文件 |
| 8 | Anthropic | Demystifying evals for AI agents | https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents | 2026-01-09 | 官方工程文 |
| 9 | Anthropic | Effective context engineering for AI agents | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | 2025-09-29 | 官方工程文 |
| 10 | OpenAI | Guardrails Python(框架文件) | https://openai.github.io/openai-guardrails-python/ | 2025 | 官方框架 |
| 11 | ACM IUI 2025 | Limitations of the LLM-as-a-Judge Approach for Expert Knowledge Tasks | https://dl.acm.org/doi/10.1145/3708359.3712091 | 2025 | 頂會論文 |
| 12 | Lakera | Stop Letting Models Grade Their Own Homework | https://www.lakera.ai/blog/stop-letting-models-grade-their-own-homework-why-llm-as-a-judge-fails-at-prompt-injection-defense | 2025 | 安全實驗室 |
| 13 | Simon Willison | Anthropic's new Citations API | https://simonwillison.net/2025/Jan/24/anthropics-new-citations-api/ | 2025-01-24 | 署名資深 |
| 14 | Beurer-Kellner et al.(引 Simon Willison) | Design Patterns for Securing LLM Agents against Prompt Injections | https://arxiv.org/abs/2506.08837 / https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/ | 2025-06 | 論文+署名資深 |
| 15 | (arXiv) | Let Me Speak Freely? Format Restrictions vs LLM Performance | https://arxiv.org/pdf/2408.02442 | 2024–2025 | 論文(格式限制影響) |
| 16 | (arXiv) | Lost in the Noise: Reasoning Models Fail with Contextual Distractors | https://arxiv.org/pdf/2601.07226 | 2026 | 論文(context 干擾) |

> 備註:項 6 的發布月份,WebFetch 摘要曾回「2025-06」,但 Anthropic 官方公告與 Simon Willison 報導皆為 **2025 年 1 月**,以後者為準。項 3、15 為 2024 下半年資料,因屬該主題奠基性官方/論文材料而保留;其餘均為 2025 下半年–2026 材料。
