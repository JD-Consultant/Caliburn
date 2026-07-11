# AI 層重設計 — 研究紀錄(2026 主流共識與趨勢)

日期:2026-07-12。範圍裁決:**丙(整包)**——寫入載體、對話層、舊件處置、引擎骨幹全部進圈
(承 ADR 0029 §11 延後的 AI 共編載體;討論按層鎖定,決策將另立 ADR)。

## 0. 研究方法與原始報告

三個研究線平行調查,**只收權威來源**(模型廠官方工程文/文件、原作者、公認 HCI 準則、頂會論文),
每條發現標 URL+發布日期,優先 2025 下半–2026 材料;二手來源一律標註且僅作趨勢佐證,
無法核實的數字明確標記不採用。原始報告(含全部引文與來源總表,共 42 條一手來源):

1. [Agent 架構線](2026-07-12-ai-redesign-raw-agent-architecture.md) —— 單/多 agent、編排、
   context engineering、工具設計、狀態、anti-pattern、2026 新方向。
2. [人機共編 UX 線](2026-07-12-ai-redesign-raw-coediting-ux.md) —— 直寫 vs 建議層、修訂呈現、
   審批與自主度、對話擺位、溯源、失敗模式、結構化欄位範式。
3. [可靠性工程線](2026-07-12-ai-redesign-raw-llm-reliability.md) —— structured outputs、
   elicitation、溯源、evals、guardrails、多輪一致性、anti-pattern。

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

## 4. 後續

按層討論鎖定(架構→載體→對話→舊件),決策另立 ADR;本檔為共識與來源的單一參照點。
