# LLM 應用工程與營運優化技術調查(2025–2026)

> 研究員紀錄。調查方背景:FastAPI + Next.js B2B SaaS,自建 agent loop 走 OpenRouter,PDF 傳統 parser 管線,規劃中 tracing 橫切層 + golden-set evals。**品質優先**。
> 判定欄採三級:**建議用 / 可試 / 不用**。日期以來源標示為準(環境時鐘 2026-07)。
> 來源紀律:只收模型廠官方文件、OpenTelemetry 官方、框架原廠、原論文、公認資深實務者(Simon Willison)。內容農場僅在無官方替代時作背景,並標註。

---

## 1. LLM 可觀測性標準:OpenTelemetry GenAI Semantic Conventions

### 白話
一套「LLM 呼叫該怎麼記 trace」的命名標準——span 叫什麼、要帶哪些欄位(模型名、token 數、finish reason)。你自建 tracing 若照它命名,將來換後端(Langfuse / Grafana / Jaeger)不用改埋點。

### 官方證據
- **標準本身**:`gen_ai.request.model`、`gen_ai.usage.input_tokens` / `output_tokens`、`gen_ai.response.finish_reasons`、`gen_ai.input.messages` / `gen_ai.output.messages`、`gen_ai.system_instructions`,以及 metric `gen_ai.client.operation.duration`(延遲直方圖)與 `gen_ai.client.token.usage`。來源:OpenTelemetry 官方部落格〈Inside the LLM Call: GenAI Observability with OpenTelemetry〉,https://opentelemetry.io/blog/2026/genai-observability/(2026)。官方原文:**"The GenAI semantic conventions are already in use today and under active development."**
- **成熟度(關鍵)**:2026 年 GenAI conventions 已從主 semconv repo **搬到獨立 repo** `open-telemetry/semantic-conventions-genai`(原 `/docs/specs/semconv/gen-ai/` 頁面現為 redirect notice:*"This page has moved and is no longer maintained in this repository."*,https://opentelemetry.io/docs/specs/semconv/gen-ai/)。搬家本身表示仍在快速演進、尚未完全定版。獨立 repo 於查證時 **"No releases published"**(https://github.com/open-telemetry/semantic-conventions-genai)。
- **分層穩定度**:工程文章(oneuptime,2026-02-06,https://oneuptime.com/blog/post/2026-02-06-monitor-llm-opentelemetry-genai-semantic-conventions/view)整理:截至 2026 上半,`gen_ai.client` 層(單次 LLM round-trip)已趨穩定並廣泛採用;`gen_ai.agent.*`(agent 呼叫層)仍屬 experimental。整體頁面在 semconv 1.40.x 時期仍標 *Development*。(此為工程文章,非官方定版聲明,僅作成熟度佐證。)
- **廠商定位**:Langfuse 官方提供 OTLP 端點 `/api/public/otel`,可當 OpenTelemetry backend 直接收 spans(https://langfuse.com/integrations/native/opentelemetry;changelog 2025-02-14)。即 Langfuse/Phoenix 這類工具的官方姿態是「**做 OTel 的後端/相容層**」,而非要你綁專屬 SDK。

### 適用時機
建 tracing 橫切層的**當下**就對齊——命名成本近乎零,回報是後端可換。

### 成本
低。埋點時採用 `gen_ai.*` 命名慣例即可;若用 OpenTelemetry SDK,social cost 是多一層依賴,但你本就要做 tracing。

### 不該用的情況
若你完全不打算做結構化 trace、只想 print log,套標準是過度設計。`agent.*` 層還在動,不要為它寫死大量 schema。

### 對「品質優先 B2B SaaS」的判定:**建議用(對齊命名,不綁 SDK)**
自建 tracing 就照 `gen_ai.*` 慣例命名 span/attribute(至少 client 層:model、token、finish_reason、latency)。**不要**綁死任一廠商 SDK;把 Langfuse/Phoenix 當「可插拔的 OTLP 後端」。`agent.*` 層自行定義即可,等它定版再對齊。這正好契合你「tracing 橫切層」規劃且避免 vendor lock-in。

---

## 2. Prompt 管理與版本化

### 白話
把 prompt 當成程式碼一樣管:有版本號、能標 label(staging/prod/A/B)、能 rollback,且**改 prompt 必觸發回歸 eval**,擋在合併前。

### 官方證據
- **版本 + label 模型**:Langfuse 官方——每次更新產生 immutable 版本(1,2,3…),label 是指向某版的可移動指標,可綁環境(staging/production)、租戶(tenant-1/tenant-2)或實驗(prod-a/prod-b);非工程人員能在 UI 改 prompt,App 自動抓最新版、**不需重新部署**。https://langfuse.com/docs/prompt-management/overview 與 /features/prompt-version-control、/features/a-b-testing。
- **A/B**:App 隨機在 prod-a / prod-b 間切,Langfuse 追每版的 latency/cost/token/eval 指標。(同上 a-b-testing 頁)
- **prompt↔eval 掛鉤(關鍵)**:promptfoo(**MIT，2025 起併入 OpenAI,維持開源;README 稱 "Used by OpenAI and Anthropic"**,https://github.com/promptfoo/promptfoo)。官方 GitHub Action `promptfoo/promptfoo-action@v1` 在**每個改動 prompt 的 PR 自動跑 before-vs-after eval**,標出 pass→fail(regression)與 fail→pass(win),assertion 失敗回傳非零 exit code 使 CI 紅燈。https://www.promptfoo.dev/docs/integrations/github-action/ 與 /integrations/ci-cd/。

### 適用時機
prompt 已是產品核心資產、會被反覆調、且改壞會直接傷輸出品質時(顧問級 JD 生成正是)。

### 成本
中低。promptfoo 用宣告式 YAML,接 CI「兩行」。真正成本在**建立與維護 golden-set / assertion**——但這你已規劃。Langfuse prompt management 若自架需一套服務。

### 不該用的情況
prompt 幾乎不動、或只有一兩條 hard-coded prompt 時,全套版本化+A/B 是過度設計。A/B 需要「足夠流量 + 明確成功指標」才有意義;B2B 低流量下 A/B 統計力弱,優先做**回歸 eval**而非線上 A/B。

### 對「品質優先 B2B SaaS」的判定:**建議用(prompt↔eval 掛鉤);A/B 可試**
最高價值是把 **promptfoo 接進 CI**,和你規劃的 golden-set evals 天然合體:改 prompt = 跑回歸,擋在合併前(正對齊 CLAUDE.md「green-before==green-after」紀律)。prompt 版本化用輕量方案即可(prompt 存 repo 檔案 + git 版本,已足夠 rollback);Langfuse 全套 prompt management / 線上 A/B 列為**可試**,低流量下優先級低於回歸 eval。

---

## 3. Prompt Injection 防禦的架構模式

### 白話
當「使用者輸入會變成後續要處理/會落進文件的內容」(如訪談逐字稿、上傳 PDF 文字),裡頭可能藏惡意指令。防禦不是靠「叫模型別聽壞話」,而是**架構上讓不可信資料碰不到有權限的動作**。

### 官方證據
- **權威綜述**:Simon Willison〈Design Patterns for Securing LLM Agents against Prompt Injections〉,2025-06-13,https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/(評介 2025-06 論文 arXiv:2506.08837)。六個 pattern:
  1. **Action-Selector**:agent 只能觸發工具、**不接收工具回傳**,像「LLM 調變的 switch statement」,因無回饋迴路而 *"immune to prompt injections"*。
  2. **Plan-Then-Execute**:在接觸不可信內容**之前**先定好動作序列,惡意輸入無法改「要呼叫哪些工具」。
  3. **LLM Map-Reduce**:sub-agent 各自處理不可信內容,只回**結構化結果**(如 boolean),再安全彙整。
  4. **Dual LLM**:privileged LLM(有工具)協調 quarantined LLM(碰不可信資料、**無工具**),後者只回符號變數,避免污染前者。
  5. **Code-Then-Execute**:privileged LLM 產生 sandbox DSL 程式碼,可做**完整 data-flow 分析**追蹤污染資料(源自 CaMeL)。
  6. **Context-Minimization**:把使用者原始輸入從 context 剝掉,轉成 DB query/結構化格式,避免原注入被重新引入。
- **CaMeL(DeepMind + ETH Zurich)**:〈Defeating Prompt Injections by Design〉arXiv:2503.18813(v2, 2025-06-24),https://arxiv.org/pdf/2503.18813。把使用者指令編譯成類 Python 步驟,custom interpreter 追 data provenance、每次 tool call 前套 security policy;privileged LLM 產計畫、quarantined LLM 處理不可信資料無工具權。**在 AgentDojo benchmark 中和 67% 攻擊**(Simon Willison 評述 https://simonwillison.net/2025/Apr/11/camel/;InfoQ 2025-04)。開源 https://github.com/google-research/camel-prompt-injection。
- **lethal trifecta**:Willison 的判準——同時具備「存取私密資料 + 接觸不可信內容 + 能對外通訊」三者才是高危組合(https://simonw.substack.com/p/the-lethal-trifecta-for-ai-agents)。

### 適用時機
你的訪談逐字稿 / 上傳文件正是「不可信內容」。**關鍵區分**:你的場景多半是「輸入 → 變成文件內容輸出」,而非「輸入 → 觸發有副作用的工具/對外通訊」。若 agent 不會因文件內容自動去呼叫危險工具或外送資料,則你**缺的是 lethal trifecta 的第三邊**,風險等級較低。

### 成本
Dual LLM / CaMeL 這類完整方案成本高(多一個 LLM 層 + interpreter + policy),延遲與 token 翻倍。Context-Minimization、Plan-Then-Execute、Map-Reduce 相對便宜。

### 不該用的情況
若 agent 沒有「被文件內容誘導去執行危險副作用」的路徑,套 full CaMeL/Dual-LLM 是過度設計。純文字生成場景,重點應放在:輸出邊界(別讓注入的內容偽裝成系統指令影響後續步驟)、以及**不要**把不可信文字直接拼進「有工具權限」那顆 LLM 的 system prompt。

### 對「品質優先 B2B SaaS」的判定:**可試(選用輕量 pattern),full CaMeL 不用**
- **建議採用的輕量版**:(a) **Context-Minimization / Map-Reduce**——把逐字稿丟給「無工具、無權限」的抽取步驟,只回結構化欄位,再交給主流程;(b) 明確標記資料信任邊界,不可信文字永不進「能呼叫工具」那層的指令區。
- **full Dual-LLM / CaMeL 不用**:對「輸入變文件內容」的場景屬過度設計(成本高、你缺 trifecta 第三邊)。
- **前提檢查**:先確認你的 agent loop 是否存在「文件內容 → 自動觸發外送/危險工具」路徑;若有,才升級到 Plan-Then-Execute 隔離。

---

## 4. VLM 文件解析(取代傳統 OCR/parser)

### 白話
用視覺語言模型(Gemini/Claude/GPT/Mistral OCR)直接「看」PDF 抽表格與文字,取代傳統 parser。優點是懂版面、抗掃描件;風險是**會幻覺**(傳統 parser 只會漏、不會編)。

### 官方證據
- **Gemini 原生 PDF**:單檔至 1000 頁、50MB;Gemini 3 用 `media_resolution`(low/med/high)控成本,且 **PDF 內原生文字直接抽出、該部分 token 不計費**。https://ai.google.dev/gemini-api/docs/document-processing。
- **Claude PDF**:全 active model 支援;機制是**每頁轉成圖 + 抽該頁文字一起餵**,吃 vision 額度;每頁約 1,500–3,000 token;Files API(beta)原生上傳至 100 頁。https://platform.claude.com/docs/en/build-with-claude/pdf-support(注:Claude 官方明說 PDF 支援「subject to the same limitations as other vision tasks」)。
- **Mistral OCR(專用模型)**:2025-03-06 發布,https://mistral.ai/news/mistral-ocr/。官方 benchmark **表格 96.12% 準確**,勝 GPT-4o(91.70%)、Gemini 2.0 Flash(91.46%);整體 94.89%;掃描件 98.96%;約 **1000 頁 / $**,可選 on-prem。(後續有 OCR 3/OCR 4 迭代版,價格 $2–4/1000 頁,支援 bounding box、block classification、inline confidence score——見 mistral.ai/news/;部分數據來自二手報導,以官方頁為準。)
- **反方(重要,務必平衡)**:PyMuPDF〈Why PDF-Native Extraction Beats Vision Models〉https://pymupdf.io/blog/pdf-native-vs-vision-models-gemini-3。論點:**born-digital PDF 已含結構化資料,轉圖丟給 VLM 是 lossy**;VLM 對複雜版面、刪節線等格式、bounding-box 引用會出錯;且「模型出錯不能直接 patch,只能調 prompt 或 fine-tune」。宣稱 PyMuPDF 靠 gridline 分析達 **97% 表格結構偵測**、CPU 上 sub-second。(廠商 blog,有立場,但技術論點成立。)

### 適用時機
掃描件 / 影像式 PDF / 版面雜亂 / 傳統 parser 反覆脆裂時,VLM 或 Mistral OCR 價值高。**政府公文式 PDF**若是 born-digital(有文字層、規整表格),傳統 parser 反而更穩更省。

### 成本
Gemini native text 免費 token 是亮點;Claude 每頁 1.5–3k token 會累積。Mistral OCR ~$2/1000 頁,批次半價,且可 on-prem(資料不出境,B2B 合規友善)。傳統 parser 近乎零邊際成本。

### 不該用的情況
**高風險欄位**(金額、日期、人名、法規條號)絕不能只靠 VLM 裸抽——幻覺會給出「看似合理但錯」的值且無 200-error 提示。政府公文若格式固定,VLM 是殺雞用牛刀且引入幻覺風險。

### 對「品質優先 B2B SaaS」的判定:**可試(混合式,VLM 當 fallback / 交叉驗證);不要全面替換傳統 parser**
你已有傳統 parser。建議**保留 parser 為主**,VLM 作:(a)parser 失敗時的 fallback;(b)對關鍵欄位做**交叉驗證**(兩者不一致 → flag 人工)。若出現大量掃描件或版面爆炸,評估 **Mistral OCR**(表格 SOTA、可 on-prem、成本可控)作為專用管線。品質優先場景下,**幻覺不可靜默通過**是紅線,故不建議「拆掉 parser 全上 VLM」。

---

## 5. 語意快取 / 請求去重(Semantic Caching)

### 白話
把「語意相近」的請求命中舊答案以省錢省延遲。陷阱:**相似 ≠ 相同**,可能對「長得像但其實不同」的問題回錯答,且 **200 OK、無錯誤、無聲**。

### 官方證據
- **失敗是隱形的**:Catchpoint〈Semantic Caching for AI Agents〉——bad cache hit *"returns an incorrect answer with full confidence and a 200 OK status"*;在 agentic 多步流程中,一次靜默誤命中會**帶偏整條 workflow**。https://www.catchpoint.com/blog/semantic-caching-what-we-measured-why-it-matters。
- **embedding 換版即失效**:底層 embedding model 一改,舊向量與新 query 不再同構,造成靜默錯配。(同上)
- **threshold 難調**:Portkey〈Semantic Caching Thresholds〉——閾值太鬆→false hit 傷正確性;太緊→false miss 失去節省。https://portkey.ai/blog/semantic-caching-thresholds/。
- **cache poisoning**:存進「本不該被重用」的回應會長期污染。(Catchpoint 同上)

### 適用時機
高流量、重複性高、且**容錯**的查詢(FAQ、檢索式問答的近似查詢)。省錢效果隨重複率上升。

### 成本
基礎設施中等(向量庫 + 相似度比對);真正成本是**正確性風險**與**監控負擔**(必須量測 false-hit 率)。

### 不該用的情況
你的核心是**顧問級文件著作**:每份 JD 依公司語境/職務不同,輸出需精準且客製——這正是 semantic cache 最會「相似但不同 → 回錯」的地雷區。B2B 多租戶下,跨租戶誤命中更是資料隔離事故。

### 對「品質優先 B2B SaaS」的判定:**不用(於核心生成路徑);去重可試(於昂貴的確定性子步驟)**
核心著作路徑**不用** semantic cache——false hit 直接傷品質、且與多租戶隔離衝突。可考慮的是**精確去重**(exact-match / 內容 hash cache)於「同輸入必同輸出」的昂貴子步驟(如同一份 PDF 的解析結果、同一段逐字稿的抽取),那不是語意近似、無誤命中風險。

---

## 6. 降延遲手法

### 白話
讓使用者更快看到結果:邊生成邊吐(streaming)、同時打多個工具(parallel tool calls)、預測輸出加速(speculative decoding / predicted outputs)。

### 官方證據
- **Parallel tool calls**:OpenAI 原生 `parallel_tool_calls`,一次抓多個獨立資訊而非序列化,官方/實務量到約 **3x** 加速。https://platform.openai.com/docs/guides/function-calling。(Anthropic 亦支援平行工具呼叫。)
- **Predicted Outputs(API 端 speculative decoding)**:OpenAI 2024-11 推出 `prediction` 參數(GPT-4o / 4o-mini),傳入「你預測的輸出」當 reference,API 以 speculative decoding **平行驗證** token,rewrite / code-edit 類工作快 **3–5x**,且**無損**(輸出與不帶 prediction 相同)。https://platform.openai.com/docs/guides/predicted-outputs;Simon Willison 2024-11-04 https://simonwillison.net/2024/Nov/4/predicted-outputs/。
- **Streaming**:各家(OpenAI/Anthropic/OpenRouter)標準 SSE 串流,不改內容、只改**感知延遲**,是最低風險的第一手段。
- **注意**:speculative decoding **本身**(draft model)是自架推理(vLLM 等)才直接控制的層;走 API 你能用的是 **Predicted Outputs 這種「外顯 prediction」介面**,前提是你能猜到大部分輸出(如「把這份 JD 微調某欄」)。

### 適用時機
Streaming:任何面向使用者的長生成,**一律該開**。Parallel tool calls:agent 有多個獨立工具呼叫時。Predicted Outputs:輸出與某已知文本高度重疊(編輯/重寫既有 JD)。

### 成本
Streaming、parallel tool calls 近乎免費(SDK 內建)。Predicted Outputs:猜錯的 token 仍計費,重疊低時不划算;僅 OpenAI 系模型,走 OpenRouter 需確認該 provider 是否透傳此參數。

### 不該用的情況
Predicted Outputs 用在「從零生成、無可預測基底」的內容純浪費(猜不中反而多花錢)。speculative decoding 別期待在 OpenRouter 純轉發下由你控制。

### 對「品質優先 B2B SaaS」的判定:**Streaming + Parallel tool calls 建議用;Predicted Outputs 可試(限「編輯既有文件」場景)**
Streaming 是 UX 標配、零風險先上。你自建 agent loop 若有多個獨立工具呼叫,開 parallel。Predicted Outputs 只在「使用者微調已生成 JD 的某段」這種**高重疊**場景試用,並先確認 OpenRouter 對目標 model 透傳 `prediction`。

---

## 7. 失敗處理工程(retry / fallback / 多供應商容錯)

### 白話
LLM 呼叫會失敗(5xx、429 限流、逾時、內容審核拒答)。要有自動 retry、跨 provider / 跨 model 的 fallback、逾時與部分結果策略。你走 OpenRouter,這些多半 gateway 已內建。

### 官方證據(OpenRouter,對你直接相關)
- **Provider 級 failover(預設開)**:同一 model 下若選中的 provider 回 5xx 或限流,OpenRouter **自動切下一個 provider**;`provider.allow_fallbacks` 預設 `true`。注意欄位是巢狀 `provider.allow_fallbacks`(複數),寫成頂層 `allow_fallback` 會**被靜默忽略**。https://openrouter.ai/docs/guides/routing/provider-routing。
- **Model 級 fallback**:`models` 參數列多個模型,主 model 全 provider 掛掉/限流/審核拒答時,**依序試下一個 model**。https://openrouter.ai/docs/guides/routing/model-fallbacks。
- **Retry 訊號**:429 / 503 回應可能帶 `Retry-After` header 指示等待秒數。
- **計費**:失敗請求不計費;"zero-completion insurance"——只付完成的那次。
(以上均 OpenRouter 官方 docs / blog:https://openrouter.ai/blog/insights/reliability-failover/)

### 適用時機
任何生產 LLM 呼叫都需要。你既已走 OpenRouter,應**顯式配置** `models` fallback 清單與 provider routing,而非只靠預設。

### 成本
低——多為設定與少量 client 端程式(逾時、指數退避、冪等鍵)。fallback 到不同 model 可能造成**輸出品質/格式漂移**,需 eval 覆蓋各 fallback model。

### 不該用的情況
別在**非冪等**副作用操作上盲目 retry(可能重複執行)。別 fallback 到未經 eval 驗證的 model——品質優先下,錯誤的答案比慢的答案更糟。

### 對「品質優先 B2B SaaS」的判定:**建議用(顯式配置 OpenRouter fallback + 自建逾時/退避)**
- 顯式設 `models` fallback 清單(主 + 備),並對**每個 fallback model 跑 golden-set eval**,確保降級後品質仍可接受(否則「有回應但變差」會靜默傷品質)。
- client 端補:合理逾時、指數退避(尊重 `Retry-After`)、冪等鍵防重複、**部分結果策略**(長流程中途失敗保留已完成步驟)。這一切應被你的 tracing 橫切層記錄(哪次走了 fallback、走去哪個 provider/model)——與主題 1 相扣。

---

## 8. 記憶 / 個人化(跨 session 記住偏好)

### 白話
讓系統跨 session 記住「這家公司的用語慣例 / 格式偏好」,不用每次重講。

### 官方證據
- **Anthropic Memory Tool(2025)**:file-based,Claude 可在專屬 memory 目錄 create/read/update/delete 檔案,**跨對話持久**、逐步累積知識庫;**完全 client-side**——storage backend 由開發者掌控(存哪、怎麼持久由你決定)。https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool。
- **Context Editing(搭配)**:接近 token 上限時自動清除 stale tool call/result,保留對話流。官方內部 100-turn web-search benchmark:memory + context editing 省 **84% token、效能 +39%**。https://www.anthropic.com/news/context-management(2025,公開 beta,Claude Developer Platform / Bedrock / Vertex 均可)。
- **OpenAI**:ChatGPT 端有 user-facing memory(2025-04-10 起參照全部歷史對話;https://openai.com/index/memory-and-new-controls-for-chatgpt/),但**開發者 API 層**主要靠 Conversations API(以 conversation id 持久)與 Agents SDK Sessions(僅單線 session 歷史,**無跨 session 語意記憶**);官方尚無「第一方跨 session 語意記憶 API」。https://developers.openai.com/cookbook/examples/agents_sdk/session_memory。

### 適用時機
B2B「記住每家公司用語慣例」高度契合——但關鍵在:這類偏好其實是**結構化的租戶級知識**(術語表、格式模板、禁用詞),不一定要用 LLM memory tool。

### 成本
Memory tool:你要自建 storage backend + 決定寫入/召回策略;跨租戶必須嚴格隔離(B2B 多租戶紅線)。LLM 自主寫記憶有「記錯/記髒」風險,需治理。

### 不該用的情況
若偏好是穩定、可枚舉的(公司術語表、JD 模板),**用你自己的 DB + 每租戶設定檔**更可控、可審計、可版本化,勝過讓 LLM 自主管理黑箱 memory。Memory tool 的價值在「非結構化、演進中、難預先枚舉」的記憶。

### 對「品質優先 B2B SaaS」的判定:**可試(先用結構化租戶偏好 DB;LLM memory tool 列為進階選項)**
- **先做**:租戶級「用語/格式偏好」結構化存於你自己的 DB(每家公司一份 profile:術語對照、格式模板、風格規則),生成時注入 context。可控、可審計、契合多租戶隔離與你的 contract 導向架構。
- **memory tool 進階**:若出現「難以預先枚舉、需從歷次著作中自動學習」的偏好,再評估 Anthropic memory tool(client-side、storage 自控,隔離可自管)。務必**每租戶獨立命名空間**,並把記憶寫入納入 eval/審計。OpenAI 側目前無對等第一方 API,不宜依賴。

---

## 額外值得補的(自行補充)

- **LLM-as-judge evals**:golden-set 之外,用另一顆 LLM 打分做無 reference 的品質評估(顧問級 JD 難有唯一正解)。與主題 2 的 promptfoo 直接整合(promptfoo 內建 LLM-rubric assertion)。**建議納入你的 golden-set eval 設計**——但 judge 本身要固定版本 + 校準,否則 judge 漂移會污染回歸訊號。
- **Structured Outputs / 強制 JSON schema**:OpenAI Structured Outputs、Anthropic tool-use 強制 schema——B2B 文件生成需穩定結構,比 prompt 求「請回 JSON」可靠。**建議用**,與你的 ocs-contract(JSON-schema→Pydantic/TS)天然契合。
- **Prompt caching(≠ semantic caching)**:Anthropic/OpenAI 官方的**確定性** prefix 快取(hash 相同前綴),省 input token 且**無誤命中風險**(與主題 5 的語意快取本質不同)。你若有長固定 system prompt / 大 context,**建議開**——純省錢省延遲、零正確性代價。

---

## 來源總表

| # | 來源 | URL | 日期 | 類型 |
|---|------|-----|------|------|
| 1 | OTel 官方 blog：GenAI Observability | https://opentelemetry.io/blog/2026/genai-observability/ | 2026 | 官方 |
| 1 | OTel semconv gen-ai(已 redirect) | https://opentelemetry.io/docs/specs/semconv/gen-ai/ | 2026 | 官方 |
| 1 | OTel GenAI semconv 獨立 repo | https://github.com/open-telemetry/semantic-conventions-genai | 2026 | 官方 |
| 1 | Langfuse OTel 整合 / OTLP backend | https://langfuse.com/integrations/native/opentelemetry | 2025-02-14 | 原廠 |
| 1 | oneuptime:client/agent span 成熟度 | https://oneuptime.com/blog/post/2026-02-06-monitor-llm-opentelemetry-genai-semantic-conventions/view | 2026-02-06 | 工程文章(佐證) |
| 2 | Langfuse Prompt Management overview | https://langfuse.com/docs/prompt-management/overview | 2025 | 原廠 |
| 2 | Langfuse Version Control / A-B | https://langfuse.com/docs/prompt-management/features/prompt-version-control | 2025 | 原廠 |
| 2 | promptfoo repo(併入 OpenAI, MIT) | https://github.com/promptfoo/promptfoo | 2025–26 | 原廠 |
| 2 | promptfoo GitHub Action / CI-CD | https://www.promptfoo.dev/docs/integrations/github-action/ | 2025–26 | 原廠 |
| 3 | Willison：Design Patterns for Securing LLM Agents | https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/ | 2025-06-13 | 資深實務者 |
| 3 | 論文:Design Patterns…(arXiv) | https://arxiv.org/html/2506.08837v2 | 2025-06 | 原論文 |
| 3 | CaMeL:Defeating Prompt Injections by Design | https://arxiv.org/pdf/2503.18813 | 2025-06-24 (v2) | 原論文 |
| 3 | Willison：CaMeL 評述 | https://simonwillison.net/2025/Apr/11/camel/ | 2025-04-11 | 資深實務者 |
| 3 | Willison：lethal trifecta | https://simonw.substack.com/p/the-lethal-trifecta-for-ai-agents | 2025 | 資深實務者 |
| 4 | Gemini Document Understanding | https://ai.google.dev/gemini-api/docs/document-processing | 2025–26 | 官方 |
| 4 | Claude PDF Support | https://platform.claude.com/docs/en/build-with-claude/pdf-support | 2025–26 | 官方 |
| 4 | Mistral OCR 發布 | https://mistral.ai/news/mistral-ocr/ | 2025-03-06 | 官方 |
| 4 | PyMuPDF:PDF-native vs Vision(反方) | https://pymupdf.io/blog/pdf-native-vs-vision-models-gemini-3 | 2025–26 | 原廠 blog(有立場) |
| 5 | Catchpoint:Semantic Caching failures | https://www.catchpoint.com/blog/semantic-caching-what-we-measured-why-it-matters | 2025–26 | 工程文章 |
| 5 | Portkey:Semantic Caching Thresholds | https://portkey.ai/blog/semantic-caching-thresholds/ | 2025–26 | 原廠 |
| 6 | OpenAI Predicted Outputs | https://platform.openai.com/docs/guides/predicted-outputs | 2024-11 | 官方 |
| 6 | Willison:Predicted Outputs | https://simonwillison.net/2024/Nov/4/predicted-outputs/ | 2024-11-04 | 資深實務者 |
| 6 | OpenAI Function Calling(parallel) | https://platform.openai.com/docs/guides/function-calling | 2025 | 官方 |
| 7 | OpenRouter Provider Routing | https://openrouter.ai/docs/guides/routing/provider-routing | 2025–26 | 官方 |
| 7 | OpenRouter Model Fallbacks | https://openrouter.ai/docs/guides/routing/model-fallbacks | 2025–26 | 官方 |
| 7 | OpenRouter Reliability/Failover | https://openrouter.ai/blog/insights/reliability-failover/ | 2025–26 | 官方 |
| 8 | Anthropic Memory Tool | https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool | 2025 | 官方 |
| 8 | Anthropic Context Management | https://www.anthropic.com/news/context-management | 2025 | 官方 |
| 8 | OpenAI ChatGPT Memory | https://openai.com/index/memory-and-new-controls-for-chatgpt/ | 2025-04-10 | 官方 |
| 8 | OpenAI Agents SDK Session Memory | https://developers.openai.com/cookbook/examples/agents_sdk/session_memory | 2025–26 | 官方 |

> 註:少數成熟度/迭代版數據(OTel client-span 穩定度、Mistral OCR 3/4 版本)來自工程文章或二手報導,已於文中標註;判定以官方 primary source 為準。內容農場一律未採用。
