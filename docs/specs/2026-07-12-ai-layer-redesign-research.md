# AI 層重設計 — 研究紀錄(2026 主流共識與趨勢)

日期:2026-07-12。範圍裁決:**丙(整包)**——寫入載體、對話層、舊件處置、引擎骨幹全部進圈
(承 ADR 0029 §11 延後的 AI 共編載體;討論按層鎖定,決策將另立 ADR)。

## 0. 研究方法與原始報告

三個研究線平行調查,**只收權威來源**(模型廠官方工程文/文件、原作者、公認 HCI 準則、頂會論文),
每條發現標 URL+發布日期,優先 2025 下半–2026 材料;二手來源一律標註且僅作趨勢佐證,
無法核實的數字明確標記不採用。原始報告(含全部引文與來源總表,共 42 條一手來源):

**第一輪(原則與趨勢)**:

1. [Agent 架構線](2026-07-12-ai-redesign-raw-agent-architecture.md) —— 單/多 agent、編排、
   context engineering、工具設計、狀態、anti-pattern、2026 新方向。
2. [人機共編 UX 線](2026-07-12-ai-redesign-raw-coediting-ux.md) —— 直寫 vs 建議層、修訂呈現、
   審批與自主度、對話擺位、溯源、失敗模式、結構化欄位範式。
3. [可靠性工程線](2026-07-12-ai-redesign-raw-llm-reliability.md) —— structured outputs、
   elicitation、溯源、evals、guardrails、多輪一致性、anti-pattern。

**第二輪(別人實際怎麼蓋;維護者指示「看別人怎麼做 AI 應用」後加開)**:

4. [實戰案例線](2026-07-12-ai-redesign-raw-case-architectures.md) —— 7 家一手案例
   (Anthropic/Cognition/Cursor/Intercom/Sierra/GitHub/Notion):分層、寫入路徑、狀態、
   模型編排、生產品質管線、演進教訓;無一手資料者誠實標未取得。
5. [官方參考架構線](2026-07-12-ai-redesign-raw-reference-architectures.md) —— 模型廠 SDK
   (Anthropic/OpenAI/Google ADK)與雲廠架構中心(AWS GenAI Lens/Azure Foundry 基線/
   Secure Multitenant RAG)的標準分層、雙載體做法、檢索定位、守門/觀測、框架邊界、多租戶。
6. [專業文件生成線](2026-07-12-ai-redesign-raw-professional-docgen.md) —— Harvey/CoCounsel/
   Hebbia/Ironclad/Writer 等「錯了有代價」領域:品質管線、引用防幻覺、SME 在迴路、
   evals 與信任、Mata v. Avianca 等演進教訓。

**第三輪(還有什麼技術可用/可優化;維護者指示後加開)**:

7. [生成品質增強線](2026-07-12-ai-redesign-raw-quality-techniques.md) —— reasoning/test-time
   compute、Best-of-N/verifier、self-refine 定論、few-shot 黃金範本、fine-tune 時機、
   prompt caching、synthetic data、streaming;每項含判定。
8. [檢索前沿線](2026-07-12-ai-redesign-raw-retrieval-frontier.md) —— contextual retrieval、
   reranker、嵌入 SOTA(Qwen3 vs BGE-M3)、GraphRAG、query 端技術、CJK 分詞、
   metadata filtering、retrieval evals;含落地順序。
9. [工程營運線](2026-07-12-ai-redesign-raw-engineering-optimizations.md) —— OTel GenAI 標準、
   prompt 版本化+CI 回歸、prompt injection 架構防禦、VLM 文件解析、語意快取、降延遲、
   OpenRouter 容錯、記憶/個人化;每項含判定。

**第四輪(設計細節定案;逐題深挖)**:

10. [evals/裁判設計深挖](2026-07-12-ai-redesign-raw-evals-design.md) —— rubric 二元化+負分、
    judge 工程(CoT 後丟棄/pointwise-against-reference/temp=0)、校準(TPR/TNR+κ、
    grade-then-refine)、偏誤對策表、考題數量門檻、模擬受訪者防坑、meta-eval、
    五大失敗模式;附可抄 rubric YAML 與 judge prompt 骨架。
11. [審閱事件語意](2026-07-12-ai-redesign-raw-review-event-semantics.md) —— 逐產品查
    accept/reject 之後的行為:文件寫作類全為無聲 UI;Claude Agent SDK 的 deny-message
    是唯一官方 in-session 回饋先例;Grammarly 分層抑制;HAX G9/G15 主張記帳後用。
12. [agent 命名與管線健檢](2026-07-12-ai-redesign-raw-agent-naming-pipeline.md) —— 各家組件
    命名對照表、標準 turn 生命週期、UI 事件=event log+state injection(AG-UI/ADK)、
    2026 新模式(write-ahead verifier/成本感知分層驗證);B 段:本引擎與主流同構無重大
    偏差、命名保留+文檔對映、七條可抄優化。

## 1. 跨線最強共識

### 1.1 共編載體:直寫 + 修訂標記 + accept/reject(產業四家收斂)

AI 改既有文件,從「側欄建議/彈窗」與「靜默覆寫」兩個極端,收斂到**直寫入本體+track changes
語彙(綠=新增、紅=刪除)+逐筆與批量 accept/reject**:

- Word Copilot 原本靜默覆寫,合約/合規場景「幾乎不可用」,2025 補上 **word-level** track changes
  (Microsoft 365 Copilot Blog, 2025)。
- OpenAI Canvas「show changes」綠增紅刪(2024-10 起,回應使用者強烈要求)。
- Google Docs Gemini suggested edits:「核准前只有你看得到」(Workspace Updates, 2026-04-22)。
- Cursor:apply → diff → accept/reject;Cmd+Enter 批量全接受(2025)。

細則共識:粒度要**詞/句級**(整段替換=review 負擔);**必有批量 accept-all / reject-all**
(AI 一次丟很多改動);要分清 diff 是「暫態預覽」還是「持久修訂」,別混。

### 1.2 審批哲學:審計畫不審每步;風險分級;undo 承擔事後把關

Anthropic《Measuring AI agent autonomy in practice》(2026-02-18)實測:

- 逐步簽核退化成 **93% 無腦點准**(approval fatigue);
- 工具呼叫**只有 0.8% 真正不可逆**——確認力氣應集中在那少數;
- 有效監督「不是核准每一步,而是能在要緊處介入」;方案=**Plan Mode(審計畫)**+
  autonomy dial(信任漸增)+ undo。

HAX 準則對應:G8 易於忽略、G9 易於修正、G11 說明為何這樣改、G17 全域控制。

### 1.3 結構化欄位鐵律(Airtable / Notion 範式)

- AI 填欄位**綁定明確 output schema**(型別/選項),不回自由文再由人塞欄位。
- **絕不自動覆寫人手編輯過的格子**(Airtable 明文鐵律)。
- 觸發時機可設定(手動/建立時/編輯時/排程);重生成前二次確認。

### 1.4 架構:單 agent 單 loop;寫入單執行緒;context engineering 是第一職責

- 預設**單 agent + 單一泛用 loop(gather→act→verify)+ 好工具**;graph 硬編排退位為
  「證明需要 durable execution 才下沉」(Anthropic BEA 2024-12 → Agent SDK 2025-09;LangGraph 官方自我定位)。
- 多 agent 僅限 breadth-first、可平行、**read-only** 蒐集(Anthropic +90.2% 但 ~15× token);
  **寫入必須單執行緒**(Cognition 2025-06 → 2026-04 兩篇的共同判準)。
- Context engineering 取代 prompt engineering:敵人是 **context rot**(塞越多召回越差);
  手法=right-altitude prompt、JIT retrieval、compaction、note-taking、sub-agent 隔離。
- 狀態:agent = **stateless reducer**,狀態(execution+business 統一)放自家業務層,
  別綁框架 checkpoint(12-factor agents)。

### 1.5 可靠性金字塔:deterministic 底座、calibrated judge 中層、人審頂層

- **模型不能守自己的門**(遞迴風險+假信心);最後一道門必須 deterministic 且獨立於 LLM。
- structured outputs 已是 constrained decoding 數學保證,但**保證形狀不保證內容**——
  「a perfectly shaped answer can be confidently wrong」;enum 大小寫、refusal、max_tokens
  是三個要當一級錯誤路徑的坑。
- 溯源:quote-first(先抽逐字原文再作答)、允許「不知道」、找不到支撐 quote 就撤回主張;
  citation 位置存在性**可程式化驗證**,詮釋正確性要另評。
- **Evals 方法論**(Anthropic 2026-01-09):capability suite(找短板,起始低分)vs
  regression suite(防退步,近 100%);capability 高分後 graduate 成 regression;
  每維度**獨立 judge + 明確 rubric + 人類 calibration**;binary/粗量表,拒絕假精度;
  agent 要評 trajectory 不只 outcome。
- 訪談/引導型應用(MCP elicitation spec 2025-06-18):schema 當 single source of truth 追
  coverage;**放行條件 deterministic**(required 欄位齊+過驗證),不讓模型「感覺聊夠了」;
  accept/decline/cancel 三動作各有明確 fallback。

## 2. 前人坑紅線清單(設計禁忌,十條)

1. 靜默覆寫使用者文字(Word 血淚)。
2. 每步簽核 → 93% 無腦准,真危險動作也被放行。
3. 建議洪水 / AI fatigue(micro-decision 轟炸;已有正式量表研究)。
4. AI 標記永不消、無一鍵清 → 視覺噪音;修訂要有退場機制。
5. 自動覆寫人手改過的格子。
6. 過早多 agent / 過度編排 / 框架綁死狀態與控制流。
7. Context 塞爆(context rot:塞越多回憶越差;別靠加大 window 解記憶)。
8. Prompt 補丁螺旋(該用 deterministic 規則/schema/架構解的,不要疊 prompt)。
9. 模型守自己的門 / LLM-judge 當唯一守門(inverted testing pyramid)。
10. 把「結構合法」當「內容正確」。

## 3. 對照現有引擎(丙圈體檢)

0027 骨幹**大部分與 2026 共識同向**:

| 現有資產 | 2026 共識裁定 |
|---|---|
| 無狀態回合服務+狀態在 DB(0023) | ✅ 12-factor stateless reducer 正解 |
| scribe 獨佔寫入(單執行緒) | ✅ Cognition「寫入單線」判準 |
| coverage ledger(確定性覆蓋帳本) | ✅ MCP elicitation「schema 追 coverage、放行 deterministic」同構 |
| deterministic backstop | ✅ 「最後一道門獨立於 LLM」正解 |
| scribe quote 通道(溯源) | ✅ quote-first;且引用位置存在性可程式驗證(可再加強) |
| consultant 刻意單層 loop | ✅ 單泛用 loop 方向;可考慮補 verify 步 |
| CurationDialog 彈窗建議層 | ❌ 產業已收斂到直寫+標記;本輪主戰場 |
| 對話與寫入的視覺分工 | ⚠️ 側欄說話/正文改動的邊界未切乾淨 |
| evals | ❌ 整套缺席:無 golden set、無 capability/regression 雙 suite |
| 舊 LangGraph authoring 圖(0007/0023 已裁待清) | ⚠️ 處置未執行 |

## 4. 第二輪:別人實際怎麼蓋(跨案例/官方藍圖/專業 docgen 綜合)

### 4.1 真實系統的共同骨架(7 家一手案例歸納)

> **自建 harness 迴圈(gather→act→verify)+ tool/MCP 當執行層 + context 外部化 +
> 寫入單一 writer 且過守門關 + 生產 tracing/eval。**

- **寫入單線程是最強共識**:Cognition「writes stay single-threaded」;Cursor shadow workspace
  先驗證再落地;GitHub 一律 draft PR→CI→人審;Intercom 三段管線的 Validate 關;Sierra
  supervisor 疊加(90%×90%→99%)。讀取/研究可扇出,寫入不可並行。
- **可靠性來自架構不寄望模型**;**把 AI 縫進既有工作流的守門結構**(GitHub 復用 PR/CI、
  Cursor 復用 LSP),不另造信任機制。
- **沒有一家把核心編排外包給重框架**;Notion harness 重寫 5 次的領悟=「為 LLM 已懂的介面
  設計」(SQLite/Markdown),非為內部工程方便。
- 分歧(多 agent 與否/模型分工/隔離粒度)由「任務可否並行拆解+寫入是否連續」決定;
  Anthropic 量化:agent ~4×、多 agent ~15× token。

### 4.2 官方參考架構(分層藍圖)

- **洋蔥分層收斂**:UI/對話 → orchestration → 工具(含 MCP)→ 知識/檢索 → 守門 →
  狀態/記憶 → 觀測(雲廠再加網路隔離)。守門與觀測是**橫切層**;tracing 預設開。
- **chat+持久工作品=雙 state 分離**(Canvas/Artifacts/Foundry conversation object):
  工作品可定址、有版本;模型的寫=**受權限把關的工具動作**,「定點編輯 vs 整篇重寫」
  是模型核心行為;對話歷史另存。
- **檢索=工具呼叫**(agentic/JIT);要不要預建索引看語料規模;「do the simplest thing
  that works」。
- **框架 vs 自建**:全體官方一致「先 API 直寫最簡方案;用框架必須讀懂底層」。
- **多租戶鐵律**:gatekeeper API 封裝租戶資料存取+檢索時 security trimming+身分流穿+
  audit log;B2B 少租戶傾向 store-per-tenant 或共用+強過濾;模型路由(輕/重模型分工)降本。

### 4.3 專業文件生成(與本專案領域最對口)

- **品質=六件事疊加**:權威內容 grounding+檢索優化(metadata/feature/LLM-based retrieval)
  +多步 agent 分解+引用強制+SME rubric+人審。Stanford HAI 實證「RAG 非萬靈丹」
  (Westlaw 34%/Lexis 17% 幻覺率,打臉 hallucination-free 宣稱)。
- **結構程式定、內容模型生**(Ironclad);**檢索與輸出格式化拆開**近乎消除 tool-use 幻覺
  (Hebbia orchestrator+專職 subagent);單發生成整份文件已被放棄,主流=分解→逐步→合成。
- **引用防幻覺做進管線**:trace 驗證、幻覺引用**自動拒收**(Harvey Data Factory),
  非事後檢查;起點是 Mata v. Avianca(虛構判例被罰,全球 1,000+ 起裁定)。
- **evals 配方**:任務取自**真實工作成品**+SME 建 ideal-answer 金鑰+**雙指標分開計**
  (Answer Score=補完專家級成品的 %,幻覺扣負分;Source Score=主張有據的 %)+
  spot-check 驗證評估器本身+接受第三方稽核;廠商自評數字打折看。
  (Harvey BigLaw Bench、TR Scorecard——與「黃金範本當尺」同構。)
- **人審設計成可負擔的驗證**:逐句引用可點回原文、redline 可逐條裁決、trace 可展開,
  專家審「有疑處」而非重讀全文;專家最大槓桿在**建置期建 rubric/金鑰**。

## 5. 第三輪:可用/可優化技術判定總表

三線報告對每項技術給了判定(建議用/可試/不用+理由);彙整如下,細節與出處見原始報告 7–9。

### 5.1 建議用(排入設計)

| 技術 | 一句話 | 出處線 |
|---|---|---|
| Reasoning effort 分級路由 | 起草/綜合/自評走高推理,抽取/格式化走低;別全域開高(overthinking) | 品質 |
| Few-shot 黃金範本 | 3–5 份多樣、標籤化的顧問級範本當 in-context 範例;官方首選 steering,優先於 fine-tune | 品質 |
| Prompt caching | 穩定前綴(系統提示+rubric+範本)在前、易變在後;cache read ≈0.1×,黃金範本幾乎免費 | 品質+工程 |
| Rubric-grounded LLM-as-judge | 每維度獨立 judge+明確 rubric+跨模型家族(防同源偏袒);是 Best-of-N/refine/evals 共用地基 | 品質 |
| Rubric-grounded self-refine | 定論:無外部訊號的自評無效(ICLR 2024);有 rubric=有外部訊號→有效(+20%);限 2–3 輪 | 品質 |
| Streaming + partial outputs | 長文件生成 UX 關鍵+大輸出防 timeout;不改品質,是基礎設施 | 品質+工程 |
| Retrieval eval 集 | 50–200 條 query→正解+Recall@10/20+NDCG@10;**所有檢索升級的前提,無此免談** | 檢索 |
| Metadata filtering+payload index+RRF | 結構化語料最直接槓桿;先 filter 再向量;融合用 RRF 別調 alpha | 檢索 |
| 中文 sparse 分詞+繁中術語詞典+繁簡對齊 | sparse 品質=分詞品質;政府術語要自訂詞典;BGE-M3/Qwen3 訓練偏簡體要測繁中 | 檢索 |
| 自架 reranker | bge-reranker-v2-m3 / Qwen3-Reranker-4B 掛 GPU 容器;Anthropic 數字:失敗率 2.9%→1.9%;單項 CP 值最高 | 檢索 |
| OTel `gen_ai.*` 命名對齊 | tracing 埋點照標準命名(client 層已穩),後端(Langfuse 等)當可插拔 OTLP,不綁 SDK | 工程 |
| promptfoo 進 CI | 改 prompt 自動跑 before/after 回歸,對齊 green-before==green-after;prompt 存 repo 用 git 版本化 | 工程 |
| OpenRouter 顯式 fallback | `models` 清單+`provider.allow_fallbacks`;每個 fallback model 必須過 eval(降級不能靜默傷品質) | 工程 |
| Parallel tool calls | 多個獨立工具呼叫平行打;SDK 內建近乎免費 | 工程 |
| 精確 hash 去重 | 同輸入必同輸出的昂貴子步驟(PDF 解析、逐字稿抽取)用內容 hash 快取;非語意快取、零誤命中 | 工程 |

### 5.2 可試(單項、評測把關)

Best-of-N(限關鍵段落+跨家 verifier)· synthetic data 補 eval 長尾(真人優先、跨家生成、逐筆過濾)·
citations 機制強化 quote 溯源 · Qwen3-Embedding 換裝/雙跑(MTEB 70.58 超 BGE-M3,但 dense-only,
sparse 要另配;用自有評測集 A/B)· HyDE(對付白話 vs 公文語彙落差)· schema-as-context 嵌入
(用既有 schema 當情境,零 LLM 成本)· late interaction(BGE-M3 內建,reranker 之後再議)·
prompt injection 輕量 pattern(Context-Minimization/Map-Reduce:逐字稿走無工具權的抽取步)·
VLM 當 PDF fallback+關鍵欄位交叉驗證(parser 為主不拆;掃描件多再評 Mistral OCR)·
Predicted Outputs(限「編輯既有文件」高重疊場景)· 租戶偏好 DB(結構化存每公司用語/格式慣例)。

### 5.3 暫不用(記縫,含觸發條件)

| 技術 | 觸發條件 |
|---|---|
| Fine-tune / distillation | eval 到頂、數百份標註後,語氣一致性(SFT)或降本(蒸餾)才議;<100 樣本官方明說別碰;ToS 雷 |
| GraphRAG | 職能基準本身就是知識圖,別讓 LLM 重抽;除非未來要「全庫宏觀彙總」分析 |
| Agentic retrieval | 點檢索單發能解;出現真正多跳分析問句再議 |
| Semantic caching | 核心生成路徑永不用(false hit 傷品質+跨租戶誤命中) |
| Full CaMeL / Dual-LLM | 我們缺 lethal trifecta 第三邊(輸入變文件內容,不觸發危險副作用);出現該路徑再升級 |
| Anthropic memory tool | 先用結構化租戶偏好 DB;出現「難枚舉、要自動學」的偏好再議 |

## 6. 後續

按層討論鎖定(架構→載體→對話→舊件),決策另立 ADR;本檔為共識與來源的單一參照點。
