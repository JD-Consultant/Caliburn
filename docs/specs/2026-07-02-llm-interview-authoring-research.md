# LLM 訪談式撰寫職務說明書 — 終局藍圖研究

> **類型**:研究紀錄(需求定義 + 現有地基 + 五軸權威研究 + 綜合方向)。**只研究、未改碼**;
> 落實前各自開 ADR / plan。
> **日期**:2026-07-02
> **動機**:維護者定調終局——LLM 扮演 **iCAP 職能顧問**訪談員工、自動撰寫職務說明書;
> 近期仍先優化編輯工具,但設計要為終局鋪路(直接影響 2a 並發設計的定位)。
> **原則**:全權威來源(官方/大廠/論文/域內主管機關),優先 2026 最新;經典僅取原始出處。

---

## 0. 問題定義(維護者原話整理)

- **使用者是誰**:顧客公司的**員工本人**——**不專業**,不會寫職務說明書;可能說不清楚自己的工作、
  或**有做但沒說**。
- **LLM 的角色**:模擬 iCAP 職能顧問的訪談:
  1. 請使用者粗描工作內容 → 幫他**定位職類**(彈選單/追問/直選,開放設計);
  2. 追問工作細節;
  3. **從 OCS 公版反推**「你是不是也有做這個?」逐項確認(彈選單或直問);
  4. 產出完整職務說明書。
- **混合主導權**:人隨時可**直接改文件**;但主要模式是訪談。
- **寫作依據**(全選):OCS 官方目錄(已有)+ 訪談/intake 內容 + 公司內部文件(未來)+ 外部公開資料。
- **近期**:先優化編輯工具;核心流程未定,開放討論。信任邊界與品質把關 → 本研究要回答。

## 1. 現有地基(讀碼驗證)

| 終局需求 | 現有對應物 | 檔案 |
|---|---|---|
| 粗描 → 檢索職類 → 彈選單 | `pick_profile`(search_occupations → **interrupt 候選** → 有序複選 → 落 DB) | [nodes.py](../../apps/api/app/authoring/nodes.py) |
| 深問工作細節 | `star → five_w2h → indicator` 逐任務 loop(**STAR + 5W2H**,interrupt 驅動;刻意單層) | [deep_nodes.py](../../apps/api/app/authoring/deep_nodes.py)、[graph.py](../../apps/api/app/authoring/graph.py) |
| 公版反推 + 確認 | `extract_tasks`(自述+公版候選 → LLM 挑 id,**自創 id 丟棄**;額外提及 → custom 候選) | [extract_tasks.py](../../apps/api/app/services/ai/extract_tasks.py) |
| K/S/態度勾選 | `fetch_ksa_pool → curate_ks → curate_attitudes`(池內 interrupt 勾選) | [curate_nodes.py](../../apps/api/app/authoring/curate_nodes.py) |
| 人直接改文件 | D27 文件工作台(REST PATCH)+ `ai/*` proposal-apply | [documents.py](../../apps/api/app/api/routes/documents.py) |
| 溯源 | 文件 `_ref` provenance + 契約 `CitableItem.code/sources` | ADR 0011/0016 |

**Gap**:訪談 graph(`/copilotkit`,`DocRepo.save` 寫新版本)與文件工作台(REST PATCH 就地更新 draft)
是**兩條寫入路**,終局要共編同一份文件 → 這正是 2a 並發設計服務的縫。

## 2. 五軸研究發現

### 軸 1 — 自由文字 ↔ 官方職能分類對映(「反推」的業界標準形狀)

OCS 的國際對應物:歐盟 **ESCO**(13,939 skills)、美國 **O*NET**。這題歐美已大量解過,2025–2026 共識架構:
**embedding 檢索 → 候選 shortlist → LLM 受限連結/分類(只准輸出目錄內 id)→(人/下游)確認**。

- [ESCOX](https://www.sciencedirect.com/science/article/pii/S2665963825000326)(EU Horizon SKILLAB 開源工具):LLM + 文字嵌入 從非結構文字抽 skill/occupation 對映 ESCO。
- [LLM4Jobs](https://www.sciencedirect.com/science/article/pii/S0950705125003491)(Knowledge-Based Systems 2025):無監督 LLM 職業抽取 + 標準化。
- [LLM-Supervised Multilingual Skill Extraction](https://link.springer.com/chapter/10.1007/978-3-031-97144-0_9)(Springer 2025):300 萬+ 職缺、GPT-4o-mini 監督、對映 13,896 ESCO skills 的多語模型。
- [O*NET features from NLx corpus](https://arxiv.org/pdf/2510.01470)、[Contrastive learning job vacancies](https://arxiv.org/pdf/2601.03558)(2026-01)。

→ **對照本專案**:indexer(BGE-M3 hybrid)+ `extract_tasks`(grounded-id 選擇)**已是這個共識形狀**;
終局要加的是「訪談迴圈中的逐項確認 UX」,不是換架構。

### 軸 2 — AI 訪談員(2026 現況)

- [The AI interviewer: multi-faceted evaluation of adaptive questioning](https://www.nature.com/articles/s41598-026-46517-7)(**Nature Sci. Reports 2026**):
  半結構訪談 agent 的關鍵設計——**每回合先判斷「要不要追問」,再生成追問**;對六個 SOTA 模型做系統評測(含 Claude)。
- [AI Conversational Interviewing](https://arxiv.org/pdf/2410.01824)(ACL Workshop 2025):LLM vs 人類訪談員對照實驗;
  LLM 可行,但需**腳本骨架(guideline adherence)+ 自由追問**的半結構混合。
- [LLM-generated follow-up questions(WoZ, 17 受試)](https://arxiv.org/html/2509.12709):定位 LLM 為**輔助而非取代**人類判斷。
- [SparkMe](https://arxiv.org/pdf/2602.21136)(2026-02)、[AInterviewer 平台](https://arxiv.org/html/2606.20588v1)(2026-06)、
  [SAGE 2026 GenAI 訪談](https://journals.sagepub.com/doi/10.1177/20597991261448157):平台化與方法學正快速成熟。
- [StorySage](https://arxiv.org/pdf/2506.14159):**對話訪談 → 填結構化文件**的多 agent 架構(自傳)——與本案同構,可借鑑其
  「訪談 agent / 文件填寫 agent / 一致性檢查」分工。

→ **對照**:STAR/5W2H interrupt 骨架 = 正確的「半結構」形狀;**缺的是 adaptive follow-up 判斷器**
(現在固定問四槽,不會依回答品質決定追問/跳過)。

### 軸 3 — 人機共寫文件(大廠產品 + CHI)

- [Word Copilot(微軟官方)](https://support.microsoft.com/en-us/office/welcome-to-copilot-in-word-2135e85f-a467-463b-b2f0-c51a46d625d1):
  AI 草稿一律**staged**——**Keep / Discard / Regenerate** 三鍵審閱後才進文件。
- [Collaborative Document Editing with Multiple Users and AI Agents](https://arxiv.org/pdf/2509.11826)(**CHI 2026**,30 人×14 團隊×一週實證):
  agent 產出走**留言/建議通道**而非直接改文;團隊「把 agent 納入既有的**作者權與協調規範**,而不是當成隊友」。
- [GhostWriter](https://arxiv.org/pdf/2402.08855)(CHI 2024,個人化+代理權)、[MindCopilot](https://arxiv.org/html/2605.23535v1)(2026,細粒度共寫形式化)、
  經典:[Wordcraft](https://arxiv.org/abs/2107.07430)(Google PAIR)/ CoAuthor(Stanford)。

→ **對照**:**proposal-apply + 回合制(ADR 0015)被大廠產品與 CHI 2026 實證雙重背書**。
LLM 直寫也應以「新版本 + 可 diff 審閱 + 可回溯」呈現——`DocRepo.save`(INSERT 新版本)天然支持。

### 軸 4 — Agent 架構 / HITL

- [Anthropic《Building Effective Agents》](https://www.anthropic.com/engineering/building-effective-agents):
  **workflow(預定義路徑)優先於自主 agent**;「在 checkpoint 或遇阻時暫停等人」;
  複雜度「只在可證明改善結果時才加」。evaluator-optimizer 適用於有明確評準的迭代精修。
- LangGraph 官方 interrupt/HITL(已在用)+ 12-factor agents(repo 既有原則,ADR 0007)。

→ **對照**:現有 graph = predefined workflow + interrupt checkpoints,**形狀正確,不需推倒**;
終局是「接上文件工作台 + 補 adaptive 判斷 + 補品質迴圈」,不是改成自主 agent。

### 軸 5 — 品質把關 / eval(2026)

- **分區信任(risk-proportional guardrails)**([Datadog](https://www.datadoghq.com/blog/llm-guardrails-best-practices/) 等):
  依風險配比防護——輕量全查、重型只上高風險輸出。
- **LLM-as-judge**:2026 現況約 **85% 與人類評審一致**(高於人與人互評);rubric 化把「好」拆成可操作準則
  ([RubricHub](https://arxiv.org/pdf/2601.08430) 2026-01、[動態 rubric](https://arxiv.org/html/2605.30568v1) 2026-05);
  已知偏誤:position/verbosity/self-preference/rubric drift。
- **golden dataset 迴歸**:可信子集當 gating(repo `evals/` 已有地基)。
- 結構化輸出:schema 驗證 + 受限選擇(`extract_tasks` 的 grounded-id 模式)。

→ **對照(信任邊界的答案雛形)**:
| 欄位類型 | 生成策略 | 把關 |
|---|---|---|
| **目錄類**(任務/K/S/O/P/態度代碼) | **受限選擇**(只准池內 id,自創即丟)= 零幻覺 | schema + provenance 驗證(確定性) |
| **敘述類**(job_description、活動舉例、STAR 精煉) | LLM 自由寫,**溯源到訪談原話** | LLM-judge rubric + 人審(staged) |

### 域內方法論(最重要的權威)

- **勞動部勞動力發展署《職能基準發展指引》**(工研院執行,[iCAP 官方 PDF](https://icap.wda.gov.tw/ap/get_file.php?t=download&c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf)):
  職能分析方法 = **訪談法、蝶勘法(DACUM)、名義群體技術(NGT)、一般調查法**,可混用 + **三角檢核**。
  → **LLM 顧問的提問腳本應以此指引為本**(= 把正統顧問方法論編碼進 prompt/流程)。**設計期必須精讀**。

## 3. 綜合:北極星藍圖(草案,待討論)

```
員工粗描工作
  → ①定位:indexer 檢索職類候選 → 彈選單確認(pick_profile 既有)
  → ②盤點:extract_tasks 反推公版任務 → 「你是不是有做?」逐項確認(勾選/追問)
           + 有做但公版沒有 → custom 任務(structure_task 既有)
  → ③深掘:逐任務 STAR/5W2H(既有)+ **adaptive follow-up 判斷器**(Nature 2026 模式:先判斷再追問)
  → ④彙整:目錄類受限選擇(零幻覺)+ 敘述類 LLM 草擬(溯源訪談原話)
  → ⑤審閱:staged 提議(Word Copilot Keep/Discard 模式)寫入 document-of-record 新版本
  → ⑥品質:schema 驗證(確定性)+ LLM-judge rubric(敘述類)+ golden 迴歸(evals/)
```
- 全程 = **workflow + interrupt checkpoints**(Anthropic 準則),不是自主 agent。
- 訪談 agent 與工作台**共編同一份 document-of-record**:agent 回合寫新版本(可 diff/回溯),
  人回合走 PATCH;並發以 **2a 樂觀鎖(revision token + 409)** 守住回合邊界。

## 4. 對近期工作的直接影響

1. **2a-minimal 照原設計繼續**(revision token + 409 + no-op skip + 衝突對話框)——回合制 + staged
   審閱獲軸 3/4 雙重背書,2a 正是它的並發地基。
2. 編輯工具預埋的縫(做 2a 時順手保留、不提前建):
   - envelope 的 `version/revision` 語意分離(agent 回合 = version+1,人的編輯 = revision+1)→ 未來「版本 diff 審閱」直接可做;
   - proposal-apply seam(`ai/*`)維持「只提議不寫」——未來訪談 agent 的提議走同一 seam。
3. **不要做的**(YAGNI,有依據):CRDT/OT(CHI 2026 顯示 agent 走建議通道,非即時逐字);自主 agent 重構;
   RAG on 公司內部文件(未來另開研究)。

## 5. 待決 / 待深研(下輪討論題)

- 訪談 UX 載體:聊天面板(CopilotKit 既有)vs 工作台內嵌逐步精靈 vs 混合?
- adaptive follow-up 判斷器的具體設計(Nature 2026 的 per-response 決策模式 → 我們的 STAR 槽位)。
- 《職能基準發展指引》精讀 → 提問腳本/三角檢核如何編碼。
- 敘述類 rubric 的具體條目(風格一致性、口吻、詳略)+ golden set 建置。
- 公司內部文件 RAG(多租戶隔離下)——未來獨立研究。

## 6. 來源(權威分類)

**域內主管機關**:勞動部勞動力發展署《職能基準發展指引》(iCAP 官方)。
**大廠官方**:[Anthropic Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) · [Microsoft Word Copilot 官方文件](https://support.microsoft.com/en-us/office/welcome-to-copilot-in-word-2135e85f-a467-463b-b2f0-c51a46d625d1) · Google PAIR Wordcraft · [Datadog LLM guardrails](https://www.datadoghq.com/blog/llm-guardrails-best-practices/)。
**論文(2025–2026 為主)**:Nature Sci. Reports 2026 AI interviewer · CHI 2026 Collaborative Editing with AI Agents(2509.11826) · ACL 2025 AI Conversational Interviewing(2410.01824) · SparkMe(2602.21136) · AInterviewer(2606.20588) · StorySage(2506.14159) · MindCopilot(2605.23535) · GhostWriter(2402.08855,CHI 2024) · RubricHub(2601.08430) · ESCOX(SoftwareX) · LLM4Jobs(KBS 2025) · Springer 2025 多語 skill extraction · O*NET/NLx(2510.01470)。
**經典原始出處**:Wordcraft(2107.07430)、CoAuthor(Stanford)。
