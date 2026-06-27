# Deep Interview 重設計 — 研究與架構選項（討論中，**未定案**）

> 本地、untracked、不 commit。起始 2026-06-23。
> **狀態：研究 + 討論進行中。** 本文件記錄「別人怎麼做、效果好、權威來源」與各架構選項的優劣，供討論。定案後再寫進 decision log（暫編 D30）並開 TDD。
>
> **討論進展（2026-06-23）：使用者同意「核心架構方向」** = 以 **expand-and-prune DAG（[R6]）為骨幹** + **catalog/OCS grounding（[R7]）** + **LLM-as-judge 做 prune/expand 與最終完整度校驗（[R10][R11]）**，單 agent、單層 LangGraph loop。三條獨立研究線（rubric-aware 訪談 [R1] / 醫療問診 [R5][R6][R7] / 貝氏選題 [R2]）收斂同形狀為信心依據。
>
> **已定（2026-06-23）：**
> - **心智模型 = DAG（骨架穩定 + 深度自適應），非線性。** 使用者要「像顧問、天花板高、題數動態、高分」。線性問卷天花板太低，排除。
> - **疲勞預算 = ~30 分鐘 / 場，以「完整滿分」為優先**（願意換長度換完整度）。題數動態，由 termination + 上限兜底；不為省題犧牲完整度，但要靠 catalog 預填 + 不對稱深度 + 任務分級把題花在刀口。
> - **下一步順序：先端到端流程圖（視覺對齊）→ 再挖 slot 地基（§4.1）→ 最後 expand 防爆炸（§4.x）。**
>
> **仍未定**：slot 粒度/權重、termination 閾值具體數字、反思範圍、K/S 是否納入 DAG、每節點 expand 上限（見 §6）。
> 方法論（使用者定）：權威來源 → 列優劣 → 適配分析 → 使用者選 → 記錄 → TDD。

## 0. 目標（使用者定）

- **砍掉現有 deep loop（`star→five_w2h→indicator` 固定腳本），greenfield 重設計**。舊碼可丟。
- 目標不是 80 分，是 **100 分、像模擬一個資深顧問**：問得深、做得完整。
- 取向：**目前主流、權威、效果好**的架構。
- **（2026-06-23 更新）使用者表示「先不管之前的選擇」→ 以下三項全部「重新開放」，僅列為候選傾向、非定案：**
  1. ~~混合提問~~（候選）：主軸任務導向；「績效/指標」格切**事件導向（BEI/關鍵事件法）**逼具體。
  2. ~~硬規則先行~~（候選）：覆蓋骨架從 OCS 職能基準契約硬導出；catalog 當候選填充。
  3. ~~受訪者=員工本人~~（候選）：問句口吻為「你怎麼做」。
  → 一切以「效果最好的主流權威架構」為準，不被上述預選綁住。

---

## 1. 三個必須遵守的實證警訊（決定設計形狀，非臆測）

這三點把設計空間夾得很窄，是後面所有選擇的依據：

1. **純放任 LLM 自由追問 → 多輪準確率會「掉」。**
   醫療問診研究：一旦讓 LLM 自己決定問什麼並迭代，準確率比單輪明顯下降，且「該回頭時不回頭」。
   → **不能做自由 agent，必須有結構骨幹拉著。** 來源 [R6][R7]。

2. **「叫 LLM 問個好問題」本身效果差；要顯式的資訊增益機制。**
   以 EIG（期望資訊增益）衡量，LLM（尤其開源）生成的問題普遍不夠 informative [R3]。
   BED-LLM 用 EIG 選題，20-questions 成功率 45%→93%、平均 +37 個百分點 [R2]。
   → **選題要有「資訊增益」的顯式機制**，不能只靠 prompt「請問下一個好問題」。

3. **多 agent 成本 4–220x，不可分解就別用。**
   訪談是強順序、強 HITL、不可平行 → **單 agent**。來源（前序討論 D-multi-agent）。

> **三條獨立研究線（rubric-aware 訪談、醫療問診、貝氏選題）全部收斂到同一形狀：**
> **結構化骨幹 + 顯式資訊增益選題 + 反思校驗，單 agent。** 這就是主流權威解。

---

## 2. 收斂後的六元件架構

```
A. PLAN（開場前，像顧問備訪綱）
   依 OCS 職能基準 + indexer catalog，為每個任務生成「覆蓋骨架」
   = 一組 slot（知識/技能/產出/績效標準/協作/工具…），每 slot 帶權重/優先度
   來源：Plan-and-Execute [R4]、醫療 DAG 協定骨幹 [R6]、competency formalization [R9]

B. STATE 追蹤（每答必更新）  ← 「judge / 那把尺」
   對話狀態 = {每 slot: 值, 飽和度(空/糊/紮實), grounding}
   judge 每收一答就重評，標哪些 slot 還缺、哪些已夠
   來源：Dialogue State Tracking [R8]、MedClarify 不確定追蹤 [R5]、rubric-aware judge [R1]

C. 選題（資訊增益驅動，取代固定腳本）  ← 核心引擎
   挑「不確定性最高 × 一問就能解 × 權重高」的 slot → 生成針對性問題
   混合：一般 slot 任務導向；績效/指標 slot 切事件導向
   來源：BED-LLM EIG [R2]、MedClarify entropy 選題 [R5]、醫療 DAG priority-DFS [R6]

D. 停止（三條件任一觸發）
   全 slot 飽和 / 到問題上限 / 邊際資訊增益趨近 0（連問沒進展）
   來源：MedClarify 停止準則 [R5]、醫療 DAG termination score [R6]

E. 反思校驗（80→100 的閘）
   問完後 reflection pass 批判完整度 + grounding，可「重開」不合格 slot 再問
   來源：Reflection pattern [R4]、LLM-as-judge / G-Eval / Autorubric [R10][R11]

F. HITL：上限到頂仍空的 slot → 標「待人工」交顧問（不硬湊）
```

全部**單 agent、一條 LangGraph loop**。控制流（plan/loop/stop/route）由 orchestrator 確定性程式掌握；LLM 只在三處出手：① judge 更新狀態 ② 生成問題 ③ 最後合成。

### 2.1 兩層訪談：廣度（任務發現）+ 深度（逐任務）—— 使用者 2026-06-23 提出的缺口

**問題**：原流程從「任務清單已存在」開始，**深問沒問員工『你做哪些工作』**。現況任務來源 = T10 intake（3 欄淺敘述）→ T11 `extract_tasks`（**單發** AI：intake+catalog 一次產出 suggested ids + custom 候選）→ T12 一鍵帶 + UI 勾選。是 catalog-grounded 混合，但**非對話式、非覆蓋驅動、不像顧問**。

**權威解法 = DACUM [R17]**：職務分析黃金標準（40 年/120 職業/58 國），結構 **職責(Duty)→任務(Task)**，**由在職員工腦力激盪先講出來**（避免清單錨定、抓公司特有任務），再精煉排序。關鍵：**OCS 契約 `ocs_content→ocu_units→tasks` 本就是此結構，ocu_units≈Duty，可當任務發現的覆蓋骨架。** 且 LLMREI [R18] 實測純 LLM 開放訪談只完整問出 ~61% + 部分 ~13%（漏 ~25%）→ **必須開放問 + catalog 對賬雙軌**。

**結論：補一個 Level 0「任務發現（廣度訪談）」，與 Level 1 深問共用 expand-prune 引擎**：

```
Level 0 任務發現（覆蓋骨架 = OCS ocu_units 職責）
   開放問「描述你的工作/一週/主要負責」
   → 對賬 catalog（extract_tasks 升級成對話式）：確認/移除/新增
   → 覆蓋探查：員工沒提到但 ocu_unit 有的職責 → expand 追問「是否也處理 X」
   → 產出：確認過的真實任務清單
Level 1 逐任務深問（覆蓋骨架 = 每任務 slot DAG）← §3
```

**已定（2026-06-23）：任務發現取向 = 開放後對賬**（先開放抓心智模型+特有任務 → catalog 補漏 → ocu_unit 覆蓋探查）。理由：DACUM 精神（先講避免錨定）+ 補上 LLMREI 證明會漏的 ~25% + `extract_tasks` 已是半成品。

### 2.2 與現有系統的關係：**升級既有流程的「引導核心」，非另立功能**（使用者 2026-06-23 提的策略問題）

**問題重述**：現有系統（D24–D29：選 OCS → curate 任務池 → star/5w2h/indicator 深問〔僅需幾句〕→ curate KS/A → 出文件）較適合「**已懂寫職務說明書、或對自身工作有清楚認知**」的人。目標客群其實是「**不懂寫的員工（多數）**」→ 想用「深度訪談模擬顧問」解決。

**關鍵洞察：不需要做兩套。adaptive expand-prune 引擎天然自適應使用者能力，一條流程服務兩種人。**
- 不懂的員工 → 答得糊 → judge **EXPAND** → 一步步引導、追到具體（顧問手把手）。
- 懂的人 → 答得完整 → judge **PRUNE** → 幾題就過（不被煩）。
研究佐證 [R19]：沒有個人化時「新手因看不懂問題而放棄，專家因被問太多非必要問題而厭煩」；專家平均提 10.1 個屬性 vs 新手 5.9；解法是「**即時依使用者能力調整提問深度**」——這正是 prune/expand 在做的事。**故此重設計不是另一個功能，是「引導核心」的升級，順帶一條流程同時服務懂與不懂的人。** 補充：除深度外，**提問風格也要自適應**（新手→簡單、步驟化、給例子；專家→精簡），由輕量能力訊號驅動 [R19][R20]。

**對既有六階段的影響地圖：**
| 階段 | 影響 |
|---|---|
| ① pick_profile（選 OCS） | **保留**；未來可由對話替不懂的員工**推斷 OCS**（不必自己選）— 後話 |
| ② 任務池 curate + T10/T11 intake | **升級 → Level 0 任務發現**（開放後對賬，建在 `extract_tasks` 上） |
| ③ 深問 star/5w2h/indicator（僅幾句） | **替換 → Level 1 DAG 深問**（這就是使用者問的「會升級深問嗎」＝會，且是 greenfield 重寫；「幾句」變「對懂的人幾句、對不懂的人引導式深挖」） |
| ④⑤ curate KS / A | **大致保留**；更豐富的訪談輸入讓候選更準 |
| ⑥ build_doc | **保留** |

**結論：漸進整合、就地升級，非另立功能。** 你已在這條路上（T10/T11/T12）。建議排序：Phase 1 = Level 0 任務發現升級；Phase 2 = Level 1 DAG 深問替換；④⑤⑥ 不動但受惠。每階段可獨立 TDD、無大爆炸重寫。

### 2.3 連續 vs 分段（使用者傾向「一步到位的模擬訪談」，續議）

- **連續**（任務發現直接接逐任務深挖，像一場顧問對話）：最自然、最像顧問、有動能；但 [R13] SparkMe 指純 sequential 有「主題轉換不穩定」風險，且使用者**深挖前看不到完整任務清單**，若 Level 0 漏/多抓任務 → 深挖錯集合、難顯示進度。
- **分段**（先確認任務清單 → 再深問）：可在便宜處（清單階段）修正、進度清楚、合 HITL checkpoint；但有 UI 斷點、較不像連續對話。
- **傾向（待使用者確認）：連續「體感」+ 一個輕量 review checkpoint**。任務發現後插一句對話式確認「我聽到你主要做 A/B/C，有漏的或不做的嗎？」再進深挖。**理由**：DACUM 本就有「review & refine task statements + sequence」這一步 [R17]；Plan-Review-Execute 也是 review 在 execute 前 [R16]。既保留「一步到位」的連續感，又留便宜修正點 + 進度感。checkpoint 是對話式、非生硬表單。

### 2.4 對話 vs 直接操作：**hybrid + progressive disclosure（不捨，整合分層）**（使用者 2026-06-23 提，基本同意）

**問題**：現有系統有很多直接操作能力（D27 工作台：拖拉、手填 O/P/K/S）。chat 訪談是另一範式，怎麼捨取？

**2026 權威裁決**（[R21][R22]）：
- **「chatbot-first」是陷阱**——強迫對話製造摩擦；對話只有與 GUI 深思結合才強大 [R21]。→ 純聊天排除。
- **直接操作有不可取代價值**：操作螢幕物件降低「組織語言提問」的認知負荷、更精準表意、減少流程中斷 [R21]。→ 拖拉/手填要留。
- **混合分工**：對話處理探索/模糊；GUI 處理結構化/可重複；inline AI 不強迫切換 [R21]。設計重點＝兩者**轉場**。
- **progressive disclosure**：進階功能放次級 UI、先給必要的；同服務新手與專家、防決策癱瘓 [R22]。

**頓悟**：**現有工作台＝「專家視圖」，對不懂的員工會決策癱瘓（正是「只適合懂的人」的病根）；顧問 chat＝「新手視圖」；progressive disclosure 把兩者疊在同一份 live 文件上 → 什麼都不丟。** 技術底已具備（D11 CopilotKit 共享狀態 + D25 document JSONB of-record，chat 與工作台寫同一份文件）。

**已定（基本同意，2026-06-23）：**
- **走 hybrid，不刪直接操作**：拖拉排序、手動增刪 K/S/態度、直接改字 → 收進「**編輯模式（揭露層）**」（＝現有 D27 工作台），一鍵打開；看文件/確認 chips/基本修正 → 預設層。
- ~~**入口分流**~~（**2026-06-25 取消**，被 §2.9 取代）：**不在進場問「訪談 vs 編輯」**。**所有人都從「描述你的工作」開始**——老手講得精準、系統照樣推斷；新手得到引導。**編輯模式（工作台）仍在，但改為 progressive disclosure「隨時可開」的揭露層，不是進場分流。** 理由：自適應引擎已同時服務懂與不懂的人（§2.2），再加進場分流是多餘的決策摩擦。

### 2.5 大量任務的確認：選單還是打字？（使用者 2026-06-23 提，討論中）

**原則（沿用 §2.4 mixed-initiative [R21]）：確認＝結構化/可重複動作 → 用 GUI 選單，不要逼打字。** 打字只留給「開放敘述」與「新增 catalog 沒有的自訂任務」。
- **開放敘述** → 打字（探索性，chat 強項）
- **AI 對賬後的清單確認** → **多選選單 + AI 預勾**（員工只取消不做的/補勾建議的，批次一次過，不是逐項打字）
- **ocu_unit 覆蓋探查（漏的職責）** → 也用**批次「你是不是也做這些?」勾選清單**，非逐句問
- **任務很多時的減負**：①AI 預勾 + 一鍵「確認全部」 ②**依職責(ocu_unit)分組**讓清單可掃描 ③primary/secondary 分流（只 core 任務進深問，次要批次輕確認）④次要任務預設收合
- 接既有：T11 task-inventory AI 預勾 + CIT 補漏、T12 一鍵帶 catalog 正是雛形。

### 2.5b 核心 vs 次要：AI 依據什麼判定（使用者 2026-06-23 問）

**權威基準 = O*NET 職務分析法 [R23]**：任務以 **Importance(1–5)** × **Relevance(% 在職者會做)** × **Frequency** 評分。**核心任務 = Relevance ≥ 67% 且 mean Importance ≥ 3.0**；其餘為 supplemental（次要）。這是判「核心」的黃金標準三維度：**重要性 × 普遍性 × 頻率**。

**但誠實面對：O*NET 靠大量在職者問卷 + 訓練有素分析師；我們只有「1 名員工 + catalog」**，AI 無法真的「知道」重要性。AI 實際能用的訊號：
1. **catalog/OCS 標準訊號**（≈分析師代理）：該任務在 OCS 是否核心職能單元、ocs_level、catalog 排序/優先度。
2. **員工敘述顯著度**（≈單一在職者問卷）：開放敘述中**先提到/強調/著墨多**的（「**主要**做招募」）＝重要性+頻率的代理訊號。
3. **一個便宜的明確訊號**（選配）：用選單 chip 收「頻率：每天/每週/偶爾」或「主要/偶爾」，**不打字**。
→ **原則：AI 用上述訊號『預排 + 說明理由』，員工用 toggle 確認/調整。** 不假裝 AI 單獨權威；AI 排序+解釋、人定奪（呼應 [R19] 人格自適應、HITL）。預設刀：AI 預標核心、員工微調（§2.5 選項 a）。

### 2.6 任務非固定：catalog 是「鷹架」不是「牢籠」——支援彈性 + 訪談中冒出的新任務（使用者 2026-06-23 提）

**使用者主張**：任務不能完全照公版；要彈性；**訪談中可能問出新工作任務**。**學界完全支持：**
- **標準本質落後**：SOC/O*NET 以**5 年**問卷週期更新，**無法即時捕捉新形成的職業/任務** [R24]。→ catalog 必然不全。
- **Job crafting（工作塑造）**：員工**不總是照正式職務說明書做**，會主動塑造自己的工作；idiosyncratic（因人而異）任務會累積/協商而生 [R24]。
- **emergent 活動**：人會做自發、突現、超出指派的活動 [R24]。
- 早前 LLMREI [R18]：catalog/開放單軌都會漏 → 本就要雙軌 + 開放。

**結論：catalog 的角色 = ①幫員工回想（減漏，LLMREI）②提供 grounding/K-S 候選 ③ocu_unit 覆蓋檢查。但員工的真實任務（含 catalog 沒有的）是一等公民。** 非 catalog 任務的三個入口：
1. **發現階段自訂**（已有：`extract_tasks` custom_candidates）。
2. **★ 訪談中突現（emergent）**：深挖任務 A 時，員工提到其實是另一項任務 B → **judge（本就每輪在跑）順手偵測「此回答描述了清單外的任務」→ 在自然斷點用選單確認「你剛提到也做 X，要列為一項工作嗎？」**。這就是醫療 DAG [R6] 的「expand→長新分支」**用在任務層**（Level 0 DAG 本身可動態加節點）。→ **兩層 DAG 皆可動態擴張**（Level 0 加任務、Level 1 加 slot），對稱。
3. **標 N/A**：catalog 有但員工不做 → 移除/標不適用，不硬塞。

**預算處理**：後期才冒出的新任務可能撞 30 分鐘 → 加入清單後由 triage 決定「現在深挖／延後／僅列出」，尊重預算（§2.3 budget）。

### 2.7 相似/重複任務的處理（語意去重 / entity resolution）（使用者 2026-06-23 提）

**問題**：選多個職位（多 OCS）合併任務池、或同職位不同公司時，會出現**語意相似/重複的任務**（如「撰寫測試報告」vs「編寫測試報告書」）。怎麼辦？

**這是經典 entity resolution / 語意去重問題，有兩個互補的槓桿：**

**A. 預防（在「選任務/檢索」時就別讓變體擠進來）= MMR 多樣性重排 [R27]**
- top-k 檢索天生會「塌縮成同一主題的近似重複」，浪費名額。MMR 在檢索後逐個挑：分數 = λ·相關度 +(1-λ)·與已選的相異度。**λ 0.5–0.7**（生產常用）。便宜、不動索引、直接破解「前幾名全是同義變體」。
- → LLM/檢索產候選任務清單時套 MMR，先天減少重複冒出。

**B. 解決（合併多池時把重複收斂）= 語意去重管線 [R25]（NeMo/SemHash 標準法）**
1. **embed**：用既有 BGE-M3（indexer/Qdrant 已有）算任務向量。
2. **blocking + 分群**：ANN 找候選相似對 → Union-Find 併成群。
3. **三層門檻**（cosine）：**≥0.85 自動合併**（near-dup）；**0.7–0.85 灰帶 → LLM-judge 判是否同義 [R25 HAC]**（embedding 找候選、LLM 定奪，精度高）；**<0.7 視為不同任務、保留**（避免把「測試計畫」vs「測試報告」誤併）。
4. **代表名**：取群心最近者（NeMo），或 LLM 生乾淨 canonical 名，或**優先採高優先序 OCS 的措辭**（既有 selected_ocs_codes 已排序）。
5. **★ 保留 provenance**：合併後**記住來自哪些 OCS code**（與 D29 header_meta 的 `sources` 同模式）——因為之後 K/S grounding 要從各 OCS 的 pairs 池抓，**併任務 ≠ 斷掉與各職類能力池的連結**。
6. **HITL**：ESCO/O*NET crosswalk 的教訓 [R26]——entity resolution 用 human-in-the-loop，不靜默自動併；灰帶合併在選單上「這兩個像同一件事，合併？」讓人確認（去重達 80–90% 基數縮減，但需人把關）。

**兩個情境的範疇差異：**
- **多 OCS（單文件內）= 現在就要**：合併 selected_ocs_codes 的任務池 → A+B 全套，provenance 記 OCS code。
- **同職位不同公司（跨文件）= 較大的產品題**：本質是「canonical 任務庫 + 各公司變體（job crafting，§2.6）」。同一去重引擎，但範疇是跨租戶任務庫/模板，**建議後話**，先把單文件多 OCS 做好。

**接既有**：emergent 任務（§2.6）加入前也跑一次去重檢查，別加到已存在任務的重複。infra：BGE-M3/Qdrant 已有向量；v3 後端在合併池後去重（indexer 回任務 + 向量/相似度，或 v3 對候選對跑 LLM-judge）。

**待定**：三層門檻數字、灰帶用 LLM-judge 還是一律 HITL、canonical 名策略（群心/LLM/高優先 OCS）、情境 2（跨公司任務庫）要不要納入路線圖。

#### 2.7a 具體演算法（block-and-match，[R25][R28][R29]）

業界標準是 **block-and-match** [R29]：先用 embedding「blocking」縮小比較範圍（不做 O(n²)），再對候選對「match」。SemHash [R28] 把這封裝成 `self_deduplicate(threshold)` → 回 `selected`(留) + `duplicates`(去除+配對+分數)，門檻可 `rethreshold` 免重算。

```
輸入：合併後任務池 tasks[]（每個含 text + 來源 ocs_code）
1. EMBED      每個 task.text → 向量（BGE-M3；Qdrant 已有或現算）
2. BLOCK      ANN/kNN：每個 task 找 cosine≥0.70 的鄰居 → 候選對（只比相似的）
3. MATCH      每個候選對 (a,b) 三層：
                cos≥0.85          → SAME（自動）
                0.70≤cos<0.85     → LLM-judge：「a 和 b 是同一件工作嗎？SAME/DIFF+理由」（zero-shot 即可 [R29]）
                cos<0.70          → 不成對
4. CLUSTER    Union-Find 把所有 SAME 對併群（遞移：A=B,B=C ⇒ {A,B,C}）
5. CANONICAL  每群選代表名：高優先序 OCS 措辭 / 最完整 / LLM 生乾淨名
6. PROVENANCE 代表任務 sources = 群內所有 ocs_code（K/S grounding 仍連回各池）
7. HITL       灰帶（步驟 3 經 LLM 判 SAME）的合併在選單請人確認
```

**Worked example**（OCS-A 軟體測試工程師 ∪ OCS-B 品保工程師）：
```
A: 撰寫測試計畫 / 執行測試案例 / 撰寫測試報告 / 缺陷追蹤管理
B: 編寫測試報告書 / 執行品質稽核 / 測試案例執行與記錄 / 缺陷管理
配對：
  撰寫測試報告 ↔ 編寫測試報告書      cos .91 → 自動 SAME
  缺陷追蹤管理 ↔ 缺陷管理            cos .88 → 自動 SAME
  執行測試案例 ↔ 測試案例執行與記錄  cos .82 → LLM SAME
  撰寫測試計畫 ↔ 撰寫測試報告        cos .74 → LLM DIFF（計畫≠報告，保留）
  執行品質稽核                       無鄰居 → 獨有
結果 8→5：撰寫測試報告[A,B] / 執行測試案例[A,B] / 缺陷追蹤管理[A,B] / 撰寫測試計畫[A] / 執行品質稽核[B]
```

**MMR 預防（選任務時，[R27]）**：候選清單逐個挑 `argmax λ·rel(t) + (1-λ)·(1 - max_{s∈已選} sim(t,s))`，λ≈0.6 → 先天不讓同義變體佔滿名額。

**順序 = 先去重、後 MMR（業界 RAG pipeline 共識 [R30]）**：檢索→合併→**去重**→(rerank)→**MMR 多樣性**(最後)。兩個理由：①去重前先做才不浪費後續算力、且 MMR 最後做才不打亂最終序；②**對我們更關鍵**——去重會「合併並記 provenance(sources=[A,B])」，MMR 只會「丟掉重複」不記來源；若 MMR 先跑丟掉 OCS-B 的變體，就**斷了該任務與 OCS-B 能力池的連結**（K/S grounding 會漏）。故**去重必須先**。註：OCS 池是有限 curated 清單，MMR 多在「大池自由文字檢索」（如 emergent 任務查找）才需要；多 OCS 合併本身**主要靠去重**。

**落點**：v3 後端，合併 selected_ocs_codes 的池後、出任務發現選單前。LLM-judge 用既有 LlmPort（cheap）。可單測（純函式：給定向量+門檻→群）。

### 2.8 完整流程總覽（端到端，串起 §2.1–§2.7）

```
（無進場分流 §2.4-rev：所有人都從「描述你的工作」開始；老手講得精準、系統照樣推斷）
1  開放問「描述你平常的工作」(§2.9)   打字(chat) — 同一段敘述同時餵 ②OCS 推斷 + ③任務種子
2  推斷+確認 OCS (§2.9)             從①敘述推薦 OCS(LLM4Jobs:summarize→embed→比對 OCS 池)
                                  →員工複選確認(HITL,可多選/混合職)。[知道職類者可直接挑，非強制]
3  任務發現 Level 0 (§2.1/2.5/2.6/2.7)
   3a 用①敘述對賬 catalog（命中既有任務 + 抓 custom）
   3b 合併多 OCS 池 → 去重(block-and-match,記 sources) → (大池才 MMR)
   3c AI 預勾 → 多選選單確認(非打字)，依職責(ocu_unit)分組
   3d ocu_unit 覆蓋探查：漏的職責批次勾選
   3e triage：AI 預標核心/次要(O*NET 重要性×普遍性×頻率代理)，員工微調
   ⇒ 確認過的真實任務清單（emergent 入口全程開著）
4  review 關卡 (§2.3)              對話式「我聽到你做 A/B/C，有漏/不做的嗎？」(連續體感)
5  逐任務深問 Level 1 (§3 DAG)
   核心任務 for-each：
     PLAN  從 OCS 契約+catalog 生 slot DAG（catalog 已知→預設 Closed）
     LOOP  挑最缺 slot→生問(grounding catalog;指標切事件導向;風格隨能力)
           →interrupt 問→judge prune/expand→控制閥(回合上限/無進展/circuit breaker)
     emergent 偵測新任務→去重檢查→選單確認加入
     STOP  飽和 / 預算 / 無進展
   次要任務：輕量帶 catalog K/S，不深問
   全程：右側 live 文件+覆蓋進度；能力自適應(懂→快 prune；不懂→引導 expand)
6  反思校驗 (§2 元件E)             LLM-judge 全 rubric(MET/UNMET/CANNOT_ASSESS)
                                高價值 UNMET→重開回 5；預算盡仍缺→標「待人工」
7  出文件 (既有④⑤⑥)              curate K/S(從各任務 sources 的 OCS 池) + 態度A → build OCS doc
                                「待人工」標記交顧問精修
跨層：hybrid UI(chat 主軸 / 編輯模式=工作台拖拉手填，progressive disclosure 隨時可開，非進場分流)、
      同一份 live doc、30 分鐘預算、全程 HITL。
```

### 2.9 待議：開放敘述要不要移到「選職類」之前（使用者 2026-06-25 提）

**使用者直覺**：「你平常都在忙什麼？」這個開放問，要不要放在**選 OCS 職類之前**？

**分析 — 我同意前移，理由強：**
- **不懂的員工根本不會選 OCS**（不知道自己是「OCS-coded 某職類」）→ 要他先選職類，正是我們要消滅的「需要專業」門檻。
- **顧問本來就先問「你做什麼」再對應標準**，不是先問「你的職類代碼是什麼」。
- **技術可行且成熟**：從自由敘述反推職類 = 既有任務（LLM4Jobs [R31]：summarize→embed→比對 taxonomy；IReRa/多階段 [R31b]：LLM+檢索+rerank）。**且你基礎設施已有**（BGE-M3+Qdrant+OCS 池），既有 `ocs-search` 端點就是「自由文字→OCS 搜尋」（backend log 可見）。
- **一段敘述雙重用途**：同一段「描述你的工作」**同時餵 ①OCS 推斷 + ②任務種子**，省一步、更連續。

**提議的新順序：**
```
0 進場分流
1 開放問「描述你平常的工作」     ← 前移；打字
2 推斷+確認 OCS                從①敘述推薦 OCS（LLM4Jobs：summarize→embed→比對）→員工複選確認(HITL,可多選/混合職)
                              [專家捷徑：直接挑 OCS，跳過①]
3 任務發現 Level 0（沿用①敘述對賬 + 去重 + 選單確認 + 覆蓋探查 + triage）
4 review → 5 逐任務深問 → 6 反思 → 7 出文件（同 §2.8）
```
**注意事項**：①推斷會錯/模糊（一段敘述可能對到多個或混合職）→ 必須 HITL：推薦 top-N 讓員工複選確認，非靜默決定。②敘述太薄無法推斷 → 追一句澄清（同 adaptive 提問）或退回手選。③**保留專家捷徑**（知道職類者直接挑，呼應 §2.4 mixed-initiative）。

**已定（2026-06-25）**：① 開放敘述**前移到選職類之前**，採上述新順序。② **無進場分流——所有人都從「描述你的工作」開始**（老手講得精準、系統照樣推斷；§2.4 入口分流取消）。③ 「直接挑職類」降為非強制的次要入口（知道的人可用），不再是 gating 選擇。

### 2.10 建置策略：**編輯端能力優先，LLM 是同層能力的消費者**（使用者 2026-06-25 定）

**決策（建置順序反轉）**：**先做「編輯端」的功能 + 資料 + API（人手動操作、確定性、可單測），再做 LLM 顧問層。** 因為 **LLM 會用到的每個能力（去重、任務發現/對賬、ocu_unit 覆蓋、core/secondary triage、OCS 推斷、slot 管理、K/S grounding…），編輯端本來也都該有**——它們是**共用底層能力**，LLM 只是另一個消費者（呼叫同一批 API/純函式來驅動）。
- **依據**：Anthropic「先把工具做好、agent 再用」[R32]；呼應 D28 §I「薄 adapter + 純函式可重用」（純函式被 REST 端點與未來 LLM 同時用）。
- **好處**：能力層先有 UI 可手動驗證、可單測、不賭 LLM；LLM 接上時是「驅動已驗證的工具」，非同時賭工具與 agent。
- **路線**：Phase A = 編輯端能力層（本節後續的功能/資料/API 清單）→ Phase B = LLM 顧問層（§2.8 流程）疊上。

**流程收尾點（2026-06-25 定，spec 暫不逐字改、記於此）：**
- **頭**：職稱/部門/公司 = **新增職位時的欄位**（既有，細節之後談）。
- **尾**：LLM 流程**不自帶匯出**；用完**交回現有編輯端**，於該處匯出 docx/pdf（沿用既有 D27 工作台系統）。
- **語音**：取消（全程文字）。**顧問精修步驟**：取消（產出即完成；「待人工」僅為未完成標記）。
- **Resume**：需要（30 分鐘未完可存檔續做；對映既有 resume 待辦）。

#### 2.10a 能力 / 資料 / API 清單（討論中，逐步補）
> 目標：把 §2.8 流程每一步拆成「編輯端要有的能力」→ 標 已有/待建、需要的資料、要設計的 API。Phase A 先做。

**既有編輯端 API（documents.py / ai.py / job_profiles.py）**：GET·PATCH `/document`、`/document/finalize`、`/document/export`、POST `/occupations`、GET `/task-candidates`、POST `/build-tasks`、GET `/ocs-search`、`/header-meta`、`/ksa-pool`；AI（D28）`/recommend-ks`·`/draft-op`·`/extract-tasks`·`/structure-task`·`/clarify`；job_profiles CRUD（含職稱等欄位）。前端：OccupationPicker / DocHeader / JobDocTable / CellFillerPanel / DocNotes / TaskCuratePanel / HeaderMetaPanel / AiTaskPanel / InterruptHandlers。

| 流程能力 (§2.8) | 編輯端現況 | 待建 | 需要資料 | API |
|---|---|---|---|---|
| 描述→推 OCS (§2.9) | `ocs-search` ✓、OccupationPicker ✓ | 包成「推薦 top-N + 確認」+ summarize | OCS embeddings(✓Qdrant) | 既有 `ocs-search`（或加 recommend wrapper） |
| 設定 OCS | POST `/occupations` ✓ | — | — | ✓ |
| 任務對賬 catalog | `task-candidates` ✓、`extract-tasks`(AI) ✓ | — | catalog 任務池 ✓ | ✓ |
| **任務去重 (§2.7)** | ❌ | dedup 純函式 + API + 合併確認 UI | 任務向量(BGE-M3)、每任務 `ocs_code` provenance | **新**（內建 build-tasks 或 `/dedupe-tasks`） |
| **ocu_unit 覆蓋探查 (§2.1)** | ❌ | 覆蓋檢查 + 批次補問 UI | **indexer 是否回 ocu_units？待確認** | **新**（`/coverage` 或 task-candidates 帶 unit） |
| **核心/次要 triage (§2.5b)** | T12 一鍵帶（部分） | 形式化 core/secondary + 訊號 | importance/frequency 代理訊號 | 擴 `build-tasks`/`document` |
| 任務清單編輯 | JobDocTable / TaskCuratePanel ✓ | 依職責(ocu_unit)分組 | ocu_unit | — |
| slot 填寫 | CellFillerPanel ✓ | **slot/覆蓋模型（slot 地基，§4.1 未定）** | OCS 契約欄位 | — |
| **完整度指標 (§2 元件E)** | ❌ | rubric 覆蓋顯示（每 slot 狀態）| slot 模型 | 新/輕量 |
| K/S grounding | `ksa-pool` ✓、`recommend-ks`(AI) ✓ | — | pairs 池 ✓ | ✓ |
| header-meta | ✓ (D29) | — | ✓ | ✓ |
| 匯出 / finalize | `export` ✓、`finalize` ✓ | — | — | ✓ |

**Phase A 真正的新編輯端工作（缺口集中在 4 處）**：① 任務去重（含 provenance）② ocu_unit 覆蓋（先確認 indexer 資料）③ core/secondary triage 形式化 ④ slot/覆蓋模型 + 完整度指標（= slot 地基）。其餘多為「已有、微調」。

#### 2.10b 資料盤點 + provenance 設計（2026-06-25，讀真實 OCS JSON + indexer schemas）

**真實 OCS JSON 結構（人力資源勞動法令人員 BHR2422-006v4 為例）——每一層都有原生代碼，即 citation 錨點：**
```
ocs_profile.ocs_code            BHR2422-006v4      ← 版本釘選的 OCS 代碼（頂層錨）
 ocs_content.ocu_units[]
   ocu_code / ocu_name          T1 / 訂定勞動法規遵循政策   ← 職責(Duty)錨
     tasks[].task_codes[]       {code:T1.1, name:蒐集勞動相關法規} ← 任務錨（注意 task_codes 是 LIST）
       competency_blocks[]
         competency_level       3
         indicators[]           {code:P1.1.1, text:...}   ← P 行為指標/績效（有 code！）
         outputs[]              {code, name}              ← O 工作產出
         knowledge[]            {code:K01, name:勞動相關法規} ← K（有 code！）
         skills[]               {code:S01, name:...}      ← S（有 code！）
 ocs_attitude                   （A，全域）
 notes                          prerequisites / supplements
```
**「O P K S」釐清**：competency_block 內四種葉節點 = **O**utputs / **P**erformance 指標(indicators) / **K**nowledge / **S**kills；**A**ttitude 是全域。**四者各自帶原生 code**。

**Provenance 脊椎（任何葉項的完整引用路徑）**：
`OCS_code(版本) → ocu_code → task_code → competency_block(level) → {葉類型, 葉code, name}`
例：K01 的來源 = `BHR2422-006v4 / T1 / T1.1 / level3 / K01`。完全符合 W3C PROV（Entity+derivation chain）[R33] 與 RAG attribution（每個 claim 有 id 鏈）[R34]。

**indexer 現有投影的 provenance 缺口（schemas.py）：**
- `Pair{code,name}` ✓ K/S/O 葉項本身有帶 code（K01/S01）。
- ❌ **`PairsResponse` 把 K/S/A/O 攤平成 occupation 層 union（all_k_pairs…）→ 丟失 unit/task 路徑**：知道 OCS 卻不知這個 K 來自哪個任務。
- ❌ **indicators（P/行為指標）完全沒投影**（Hit/TaskDetail 只有 k/s/output_pairs，無 indicators）。
- ⚠️ `task_codes` 原生是 **LIST**，indexer 投成單一 task_id/title（疑取首；依 [[verify-ocs-json-cardinality]] 待確認多值）。
- `TaskDetail`(tasks/by-id) 有保 unit_id/title + 每任務 k/s/output_pairs → **task 層 provenance 在這裡還在**，但仍缺 indicators、且缺 competency_block 細分。

**indexer API 重設計原則（grounded [R33][R34]）：每個回傳的葉項（K/S/O/P/task/attitude）都附「完整 provenance 路徑物件」，不再 aggregate 掉 lineage。** 設計一個 canonical `SourceRef`：
```
SourceRef = { ocs_code, ocs_name, ocu_code, ocu_name, task_code, task_name, competency_level }
每個 KSOP 項 = { type:K|S|O|P|A, code, name/text, source: SourceRef }
```
**待議**：①引用粒度到 competency_block（K/S 就住這層）夠嗎？②要不要補 indicators(P) 投影？③pairs 端點改成「保留 provenance 的巢狀回傳」還是新增 provenance 欄位？④task_codes 多值如何處理。

#### 2.10c indexer 重設計（詳案）— 讀 service.py + 多份真實 JSON 後

**新增關鍵發現：**
1. **K/S 的 code 是「OCS 本地」**（K01/S01 每個 OCS 重頭編）→ AIoT 的 K01 ≠ HR 的 K01。**全域唯一引用必須帶 ocs_code 前綴。**
2. **K/S 是「多來源」**：同一 S01「資料蒐集與分析能力」在 AIoT 的 T1.1、T1.2… 重複出現 → 一個 K/S 的 provenance 是**一組路徑**（像 RTX-KG2「每個 fact 平均 3 個來源」[R36]）。而 **O/P 的 code 是任務命名空間**（O1.1.1、P1.2.1）→ 與單一任務 1:1，單一來源。A 全域。
3. **indicators(P) 在「索引時」就被丟掉**（service.py 的 task 點 payload 只有 k/s/output_pairs，無 indicators）→ **要吐 P 必須改 ingestion（builder/normalizer）+ re-ingest**（同 D29 等級的工程，非只改 API）。
4. task 點已把 competency_blocks 攤平成單一 competency_level（多 blocks 會合併；目前觀察多為 1 block/task）。

**設計（grounded：W3C PROV [R33] + FHIR 穩定識別碼 [R35] + KG 多來源 [R36]）：**

*穩定可引用識別碼（URN，由來源 id 衍生、全域唯一、人類可讀）：*
```
K/S（OCS 本地碼、多來源）：  ocs:{ocs_code}:K:{code}     e.g. ocs:LMP9999-001v1:K:K01
O/P（任務命名空間、單來源）： ocs:{ocs_code}:O:{code}     e.g. ocs:...:O:O1.1.1
A（全域）：                  ocs:{ocs_code}:A:{code}
```
*CitableItem（每個 K/S/O/P/A 葉項的統一回傳形狀）：*
```
PathRef     = { ocu_code, ocu_name, task_code, task_name, competency_level }
CitableItem = { id(URN), type:K|S|O|P|A, code, name/text,
                ocs_code, ocs_name, sources: [PathRef,…] }   # K/S 多 path；O/P 單 path；A 空
```
≈ FHIR「business identifier = system(ocs:{code}) + value(K01)」+ PROV「sources = derivation 路徑」。

**端點改動：**
- `/pairs`：每個 pair 由 `{code,name}` → **CitableItem（帶 sources[]）**。additive 保留 code/name，D29 header-meta 不破。
- `/tasks/by-id` & task 投影：**新增 indicators(P)**（需 ingestion 改）。
- （選配）新端點 `/profile/{ocs}/blocks` 或擴 task：回完整 `task→competency_blocks[]→{P,O,K,S as CitableItem}` 的巢狀結構，供「文件按來源引用」。

**真正的工程範疇**：因 P 與 block 結構在 Qdrant payload 不存 → **builder/normalizer 改 + 全量 re-ingest**（D29 級）。API 層才是其次。

**詳案待議**：①URN 格式 `ocs:{ocs_code}:{type}:{code}` 同意？②K/S 用「多來源 sources[]」（列出用在哪些任務）確認要？③補 indicators(P) 進 ingestion + re-ingest，做？④`/pairs` 走「攤平+每項帶 sources」(傾向，讀友善/去重友善) 還是「按任務巢狀」？⑤competency_block 維持 1 level/task 攤平 vs 存 blocks（觀察多為 1 block，傾向維持但補存 P）。

#### 2.10d 目標 Qdrant payload（完整）

**原則**：payload 只存原始事實；URN 與 sources[] **查詢時由 API 組出**（task 點的路徑欄位即來源依據）。**唯一新增 stored 欄位 = `indicators`(P)** → 此即 re-ingest 的唯一驅動。其餘為「重命名對齊原 JSON」（選配，做了要同步改 v3 http_client / header-meta 等少數消費者）。

**profile 點（1/OCS）**（2026-06-25 修正：刪 version＝ocs_code 冗餘；釐清 ocs_name vs category；三組分類改 [{code,name}] 像 attitudes，消滅 D29 lockstep bug，見 [[verify-ocs-json-cardinality]]）
```
chunk_level: "profile"
ocs_code: "BHR2422-006v4"          # 即版本（version 欄刪除）
ocs_base_code: "BHR2422-006"       # NEW(選配) 跨版本去重用
is_current
# 職能基準名稱（ocs_name，原始巢狀；擇一；幾乎都 occupation，job_category 幾乎 null）
# 保留來源原名（不改名）：契合 provenance/可追溯，靠巢狀與頂層 job_categories 區隔
ocs_name: { job_category_name: null, occupation_name: "人力資源勞動法令人員" }
job_description, ocs_level
# 所屬分類（三組皆多值 [{code,name}]，與 attitudes 同形狀）★ 取代平行 _codes[]/_names[]
job_categories: [{code,name}]      # e.g. [{code:"BHR", name:"企業經營管理/人力資源管理"}]
occupations:    [{code,name}]      # e.g. [{code:"2422", name:"人力資源勞動法令人員"}]
industries:     [{code,name}]
attitudes:      [{code,name}]      # A 全域（= 現 all_a_pairs）
prerequisites[], supplements[]
source_file
```
注意：`category.occupations`（分類，code 2422）與 `ocs_name`（名稱）文字常同但為**不同欄位**，皆保留。`ocs_name` 表示法待定：`ocs_name`+`ocs_name_kind` vs 保留原始巢狀 `{job_category_name,occupation_name}`。

**task 點（= 1 個 task_code 一個 chunk）**（2026-06-25 定案）
> 契約 [R37]§6.3.1：`tasks[]` 條目=「共用同一組 competency_blocks 的任務群」＝**語意**單位。但**儲存/索引單位**選「每個 task_code 一 chunk」（與語意單位脫鉤）——理由：新流程重度依賴**任務搜尋**（描述比對/emergent/去重），per-task 一向量才搜得精準；條目層一向量代表多任務會鈍。風格 B 的共用 blocks **複製**到群內每 chunk。**不存 shared_group**：共用語意查詢時由 K/S 的 `sources[]` 還原（K01 出現在全群 chunk → union 後 sources 自列全群）。block 由「K/S 出現新值」分界（§6.3.2），多 level 才多塊。
```
chunk_level: "task"
ocs_code: "BHR2422-006v4"
ocs_name: "人力資源勞動法令人員"    # 解析後顯示名（denormalized，免 by-id join）
ocu_code: "T1"                     # = 現 unit_id（重命名對齊 JSON）
ocu_name: "訂定勞動法規遵循政策"     # = 現 unit_title
task_code: "T1.1"                  # 單一（一個 task_code 一個 chunk；風格 B 拆成多 chunk）
task_name: "蒐集勞動相關法規"
competency_blocks: [               # ★ 巢狀；多 level 才多元素；風格 B 群內各 chunk 複製同一組
  { competency_level: 3,           # 可為 null
    indicators: [{code:"P1.1.1", text:"..."}],   # ★ NEW；必填 ≥1（每 block 都有 P）
    outputs:    [{code:"O1.1.1", name:"..."}],   # 可空 []（~21% 無 O）；可跨 block 共用
    knowledge:  [{code:"K01", name:"勞動相關法規"}],
    skills:     [{code:"S01", name:"..."}] }
]
source_file
```
**point id** = `uuid5(ocs_code : task_code)`。**風格 B**：條目 N 個 task_code → N 個 chunk，competency_blocks 複製（量小，21 職業）。provenance：K01 ← sources[] 自然列出共用它的全群任務（不需 shared_group 欄）。
**`activity_examples` 刪除**：經查它＝indicators 的衍生（normalizer evidence＝indicator text；builder 取 text 截斷、丟 P code）。正式存 `indicators:[{code,text}]` 後它即重複劣化品 → 刪。v3 用到的 6 檔（ai.py/nodes.py/knowledge models·http_client·base/stubs/前端 InterruptHandlers）改抓 `indicators[].text`（還賺到 code+完整清單）。

**掃描定案（908 檔）+ 契約 [R37] 校正**：
- **決策 4（point 切法）**：task_codes 99.4% 單值；0.6% 多值是**真實 21 職業**（半導體全系列、工業設計師、工具機…**風格 B**）。現 indexer 取首→掉任務=真 bug。→ **每個 task_code 一個 chunk**（風格 A 不變、風格 B 拆 N chunk 救回任務 + 各自可精準搜尋；共用 blocks 複製、靠 K/S sources[] 還原共用語意）。語意單位是「條目」(契約 [R37]§6.3.1) 但**儲存單位脫鉤為 task_code** 以利搜尋。
- **決策 5**：competency_blocks 96.5% 單一、3.5% 多、**1.45%(121 任務)多 level**（如 AIoT T4.1 = level[3,4,5]）→ **巢狀 competency_blocks[]** 忠實保留，點數 1/task_code。
- 附帶：**每個 block 都有 indicators（0 例外，契約必填）**→ P 普遍、必 surface（23804 條）；~21% block 無 outputs→O 稀疏選填。

**改動總結**：①★`indicators` 新增 ②`competency_blocks[]` 巢狀（K/S/O/P/level 進去）③每 task_code 一 chunk（風格 B 拆多 chunk、複製共用 blocks、不存 shared_group）④重命名對齊源 ⑤`ocs_name` denormalize ⑥刪 `activity_examples`。

**API 查詢時組出（不入庫）：**
```
PathRef     = { ocu_code, ocu_name, task_code, task_name, competency_level }   # 來自 task 點欄位
CitableItem = { id:"ocs:{ocs_code}:{type}:{code}", type, code, name|text,
                ocs_code, ocs_name, sources:[PathRef,…] }
# K/S：掃該 OCS 全 task 點、依 code union、累積 sources[]（多來源）
# O/P：單一 task 點 → 單一 source
# A  ：profile 點 → sources 空
```

#### 2.10e indexer 重構計畫（Phase A，動代碼前定稿，2026-06-25）

**決策（已拍板）**：① 重命名對齊源（趁 re-ingest 一次改乾淨，不走 additive）② **砍 version_seq**（版本只用最新 = `is_current`；連帶 `version`、`update_date` 等版本 metadata 可砍）③ `indexed_at` **保留但不索引** ④ **加 `schema_version`**（資料契約 [R39]，消費端可斷言 schema、CI 擋破壞）⑤ **payload 改 pydantic typed 契約**（不再手刻 dict；解耦、可驗證、與 API schemas/CitableItem 共用型別）。

**重構發現的更正**：builder [builder.py:159] 的 `for task in group.tasks` **早就「一個 task_code 一個 record」**→ 風格 B 任務**沒被丟**（我先前「取首掉任務」是未讀碼的誤判）。故決策 4「拆 task_code」**已是現況**，免做。

**normalizer.py（小改）**：
- 已有：每 block 的 `k_pairs/s_pairs/output_pairs`、`evidence`(=indicators code+text)、`competency_level`→ **indicators 早就抓了**。
- 加：`job_category_pairs / occupation_pairs / industry_pairs`（lockstep pair）。**順修潛在 bug**：occupations/industries 現以 `if code:append`/`if name:append` 分開收（[normalizer.py:177-186]）→ 缺一邊會錯位（只 job_categories 修過）。改 pair 一次修掉。

**builder.py（主改）**：
- 砍 `_aggregate_group` 攤平 → 新 `_block_payload(b)` 每 block 出 `{competency_level, indicators:[{code,text}], outputs, knowledge, skills}`；`build()` 傳 `competency_blocks=[_block_payload(b) for b in group.blocks]`。
- `_task_record`：改名 unit_id→ocu_code / unit_title→ocu_name / task_id→task_code / task_title→task_name；以 `competency_blocks` 取代 k_pairs/s_pairs/output_pairs/competency_level/**activity_examples(砍)**；加 `ocs_name`(=norm.job_title)。embed text 仍用 task.name+指標文字（不入 payload）。
- `_profile_record`：`ocs_name` 巢狀 `{job_category_name, occupation_name}`；category 三組改 `[{code,name}]`(用新 pair)；`all_a_pairs`→`attitudes`；砍 `version`/`version_seq`/`job_category`(flat)/`*_codes`/`*_names`；留 `ocs_code_base`、`indexed_at`、`is_current`；加 `schema_version`。
- **typed 契約**：定 `payloads.py`（pydantic：ProfilePayload/TaskPayload/CompetencyBlock）→ builder 建模型 `.model_dump()`。

**索引紀律 [R38]**：payload 全存、但 Qdrant payload index 只建會 filter 的 `ocs_code`/`chunk_level`/`is_current`；高基數（indexed_at）與巢狀（competency_blocks）不索引。

**順序依賴（必守）**：① builder/normalizer + payload 契約 → ② indexer API service.py（get_pairs/build_task_pool/_project_task_detail/get_profile 讀新欄名 + 組 CitableItem）→ ③ v3 消費端（http_client/models/header_meta）→ **④ 最後 re-ingest**（`uv run jd-ocs-indexer index data/jd-json`，~908檔/9500點/~10min；破壞性動共享 Qdrant，**跑前明確授權**）。`schema_version` 讓任何漏改的消費端會「fail loud」而非默默讀錯。

**參考**：[R38] 向量庫 metadata 慣例（原子化、只索引 filter 欄、高基數別索引）；[R39] data contract（schema 版本化、CI 驗證、producer/consumer 解耦）。

### 2.11 indexer API 層設計（步驟②，2026-06-25；部分討論中）

**需求（使用者確認）**：選職類→分數+排序+來源；選任務→來源；O/P/K/S→來源；要能抓每任務的 OPKS。
**評估**：v4 + CitableItem **全覆蓋**；現況舊 API 做不到（缺 P、缺 provenance、攤平）。

**★ 統一 provenance 詞彙（已定）**——linked-data `@id` 風格，每層實體一個穩定 URN（呼應 W3C PROV/FHIR [R33][R35]；REST 建議 provenance 當「資料」非深 URL 巢狀 [R40]）：
```
職類  ocs:{ocs_code}
職責  ocs:{ocs_code}:U:{ocu_code}
任務  ocs:{ocs_code}:T:{task_code}
KSOPA ocs:{ocs_code}:{K|S|O|P|A}:{code}
```
- **在哪組**：indexer API 層（service.py）**查詢時用 payload 欄位純函式組**（不入庫；§2.10d 原則）。`urn(ocs_code,type,code)`。
- **在哪用**：v3 存進 document JSONB 當每項 source；web 顯示來源/去重鍵/引用；LLM grounding/引用；dedup 的鍵。共享 `SourceRef`/`Citable` 模型，所有端點共用（資料契約 [R39]）。

**★ 命名/結構重設計（2026-06-25 定，資源導向、自我說明）**——使用者痛點「光看 API 看不懂做什麼、拿到什麼」。依 Google AIP-121 [R44] + Microsoft/Stripe [R40]：資源名詞複數、巢狀 ≤1 層、標準方法、自我說明、別洩漏 DB 內部詞（`profile`/`pairs` 即洩漏）。

| 需求 | 新端點（資源導向） | 拿到什麼 |
|---|---|---|
| 搜職類 | `POST /occupations/search` | 排序職類（ocs_code/名稱/描述/**raw score**）。score only、不做 relevance |
| 取一職類（**自動填表頭**） | `GET /occupations/{ocs_code}` | profile：ocs_name + **category 三組全（職類別/職業別/行業別，code+name）** + 描述/級別/態度/備註（＝D29 header-meta 來源） |
| 職類能力池 | `GET /occupations/{ocs_code}/competencies` | K/S/A/O/P **CitableItem(URN+sources[])**；多來源；**含 P** |
| 職類任務 | `GET /occupations/{ocs_code}/tasks` | 任務（依 unit 分組，task URN）。**取代多參數 task-pool**：v3 對多選職類各取一次再合併（同 header-meta 模式） |
| 搜任務（emergent） | `POST /tasks/search` | 任務命中**只回身分**（ocs/ocu/task_code/name+score） |
| 取指定任務細節（**OPKS**） | `POST /tasks/batchGet` | 任務 + competency_blocks（含 P）；單來源 |
| 找相似任務（去重） | `POST /tasks/findSimilar` | 候選對（§去重，討論中） |
| 維運 | `GET /stats` `/healthz` | — |

**已定**：① `profile`→`occupations`（不只 level=profile，是「職類資源」）② 砍多參數 task-pool → 單職類 `/occupations/{code}/tasks` + v3 合併 ③ search 用 `POST .../search` 子路徑（body 帶 query+filter；非 Google 冒號風）④ `batchGet`/`findSimilar` 用動作子路徑。

**競爭力池 vs 任務細節**：`/competencies`=整職類「大池」（廣度，多來源 CitableItem，給挑）；`/tasks/batchGet`=選定任務「細節」（深度，單來源原始 blocks，按需）。互補非重複。

**架構結論**：端點**結構**用資源導向重命名（自我說明）；但**不搞深 URL 巢狀**（provenance 當資料 [R40]）；統一 URN 詞彙不變。

**選配（之後做，使用者定先不做）**：搜職類相關性弱（spec 已知問題）→ **cross-encoder reranker** 重排 top-k（對短職稱匹配有效 [R41]）。另開增量、不擋 provenance 工作。

**`POST /tasks/findSimilar`（去重，⚠️ 討論中、未定案）**：dense-only（非 hybrid，避免關鍵字過匹配）、回候選對+分數、門檻 0.70；三層 tier + LLM-judge + Union-Find + canonical + provenance 全在 v3（§2.7a）。Qdrant 做法 [R42]：scroll 全 task 點 + 逐向量 search(score_threshold) + 排除自己 → 候選對。**範疇/時機/門檻校準/canonical 策略/HITL 程度未定，續議。**

---

## 3. 具體實作骨幹：expand-and-prune DAG（醫療問診 [R6] 近乎可直接借）

[R6]（arxiv 2510.12490，LLM 醫療問診用醫療演算法當 DAG）給了一個**最具體、可實作**的機制，正好同時實現 A~D 並回答「混合（骨幹 vs 臨場偏離）」：

- **DAG = G(V,E)**。每個節點 = 一個該問的問題；每節點三屬性：
  - **Priority** P(v)：Low / Intermediate / High / Urgent（依回答動態調整）
  - **State** S(v)：**Open（未答）/ Explore（問了但要追）/ Closed（解決）**
  - **Label** L(v)：類別（對映我們的 slot 種類：知識/技能/產出/績效…）
- **冷啟**：從知識庫（他們是 1,020 個診斷演算法）用 embedding 分群生出初始節點。
  → 我們對映：**從 OCS 職能基準契約 + catalog 生初始 slot 節點**（呼應「硬規則」）。
- **遍歷 = DFS，依 priority 排序**：把同一主題問完再換 → 主題連貫、降低受訪者認知負荷（不要跳來跳去）。
- **expand-and-prune（核心，就是「混合」）**：每收一答，`LLM.evaluate()`（function-calling 出結構化 JSON）判定：
  - **prune**：回答已充分 → 關節點（Closed）→ 前進下一個 Open 節點。
  - **expand**：回答不完整/含糊/帶出新點 → **動態生成 follow-up 子節點**掛進 DAG。
  - 提示詞強制：「問很有資訊量的 follow-up，但**別問已答過的**」（去冗，呼應 Note2Chat [R7]）。
- **停止 = termination score**：`(已答的 unique Label 數) / (總 unique Label 數)`，閾值 **0.99=徹底 / 0.80=核心**，外加最大交換次數當安全閥。
- 量測（人因）：NASA-TLX 15.6（極低負荷）、SUS 86、QUIS 8.1/9。

> **為何這個比抽象 EIG 更適合我們**：完整 EIG（BED-LLM [R2]）的數學是為「猜一個隱藏變數」（20 問遊戲、多選題格式、要 logits）設計；我們的場景是「**填滿一張豐富 rubric、答案是開放式長文**」。expand-and-prune DAG 抓到 EIG 的精神（不問已知、優先補缺、會偏離也會剪枝），又天然吃 free-text、可 function-calling、好測。**這是 EIG 原則在我們場景的工程化落地。**

### Grounding：問題要錨定在 catalog/OCS（Note2Chat [R7] 的結論）

Note2Chat 證明：把問題**錨定在外部結構化知識源**（病歷 → 我們的 catalog/OCS）能同時降低兩種失敗：
- **幻覺問題**（問到不相關的東西）→ 因為問題從已知條目延伸。
- **冗餘問題**（重問已答）→ 因為對照知識源知道哪些已覆蓋。
→ **C 元件生成問題時，必須餵 catalog/OCS 候選當 grounding，而非讓 LLM 憑空生。**

### Judge / 反思的做法（LLM-as-judge，G-Eval / Autorubric [R10][R11]）

- LLM-as-judge 與人類評審一致度約 **85%**（比兩個人之間還高），是 2026 評估預設法 [R10]。
- 做法：**每個準則原子化**評，輸出結構化 verdict **MET / UNMET / CANNOT_ASSESS + 引述證據**（G-Eval 風格、CoT、機率加權分數）；用 rubric 錨定分級控制 verbosity bias。
- → B（judge 每 slot 飽和度）與 E（最後完整度校驗）都用這套：每 slot 一個原子準則，judge 回 MET/UNMET/CANNOT_ASSESS + 證據。**rubric 像程式碼一樣版本化管理。**

### 3.1 防爆炸 / 反疲勞控制（[R13] SparkMe、[R14] 對話問卷追問、survey agent 共識）

「題數動態」必須有界，否則 expand 會無限長。權威做法（多篇一致）：
- **每主題回合上限**：對單一 slot/Label 設 turns 上限（醫療 DAG 的 priority-DFS + termination 也是這意思）。
- **限制連續主題跳轉**：避免「該深挖卻一直換主題」或「卡同一主題」——兩種都是失敗模式 [R13]。
- **necessity score（必要性分數）**：evaluation agent 對「是否值得再問」打分，低於閾值就前進；資訊不足才生 follow-up。
- **無 pending 子主題即結束**：agenda 清空就收，省掉無謂問題。
- **circuit breaker**：連續 N 次（如 3）沒進展/失敗 → 跳出迴圈進校驗，防 runaway（LangGraph 生產模式 [R16]）。
- **over-/under-questioning 指標**：當 eval 量測（對齊 D12 eval-gate），避免問太多或太少。

### 3.2 LangGraph 落地形狀（**關鍵澄清：DAG 在「狀態」裡，不在 graph 拓樸**）

容易誤會的點：這張 DAG 是**應用層的資料結構（存在 state 內）**，**不是** LangGraph 的節點拓樸。LangGraph graph 本身維持**小而靜態的單層 loop**（呼應現有架構、不做 subgraph）：

```
plan_node ─▶ interview_step (loop) ─▶ reflect_node ─▶ build_doc
                │  ▲
        interrupt() 問人；judge 更新 state 內 DAG；
        conditional edge 判 termination → 續迴圈 or 出迴圈
```

對映 Plan-and-Execute + HITL（[R16]）：`plan_node`＝冷啟 DAG/slot；`interview_step`＝挑最高 priority 的 Open 節點、`interrupt()` 問、judge 做 prune/expand、寫回 state；conditional edge＝termination + circuit breaker；`reflect_node`＝完整度校驗（可重開 slot 回迴圈）。狀態快照由 AsyncPostgresSaver 持久化，天然支援「存檔續做」（呼應 30 分鐘可分段）。

---

## 4. 各元件的設計選項與取捨（**含未定的選擇點**）

### 4.1 PLAN — slot 骨架來源（已傾向「硬規則」，細節待定）
- **硬導出**：直接從 OCS 職能基準契約欄位 + catalog 條目生 slot（與 D29 的 profile/pairs 對齊）。Frontiers 2026 [R9] 證明可從職業標準自動形式化能力（582 能力 / 2072 outcomes / 14000 KSA 元素）。
- 待定：slot 的**粒度**（每任務幾個 slot？太細→疲勞、太粗→不深）、**權重**怎麼定（哪些 slot 必填、哪些選填）。

### 4.2 選題引擎強度（**主要未定選擇點**）
| | 完整 EIG（BED-LLM [R2]） | expand-and-prune DAG [R6]（傾向） | 飽和度貪婪（最簡） |
|---|---|---|---|
| 機制 | 抽 N 假設、算候選問題 logits 熵、選 EIG 最大 | DAG + priority-DFS + LLM 判 prune/expand | 挑最不飽和×最高權重 slot |
| 嚴謹 | 最高（+37pp 出處） | 高（EIG 精神工程化） | 中 |
| 代價 | 需 logits/多選題格式、token 重、不合 free-text | 中（function-calling JSON） | 低 |
| 適配 | **不合身**（我們非猜隱變數） | **最合身** | 堪用、最省 |

### 4.3 停止條件閾值與預算（未定數字）
- termination score 閾值（0.99 徹底 / 0.80 核心，可分「必填 slot 必須 100%、選填 80%」）。
- 每任務追問上限、無進展中止（連 2 題沒提升飽和度）。
- 待定：具體數字（保守預設可由我先給）。

### 4.4 反思校驗範圍（未定）
- 只對「績效/指標/grounding」這類高風險 slot 跑 reflection？還是全 slot？
- 重開上限 N 次，到頂標待人工。

### 4.5 K/S 的處理（待釐清）
- 現況：K/S 來自 catalog 池於 curate 階段（`curate_ks`）。
- 選項：訪談階段的 rubric 只管「任務證據 slot」；K/S 覆蓋當**另一張 rubric**在 curate 階段查；或把 K/S 缺口也納入訪談 DAG。

---

## 5. 對映現有 stack / 程式碼

- **stack 不變**：單一 LangGraph + `interrupt()` HITL + AsyncPostgresSaver（D3/D4/D8）。深問仍是**單層 node loop**（不做 subgraph）。
- **丟**：`deep_nodes.py` 的固定 `star→five_w2h→indicator` 順序與 `route_after_indicator`。
- **留作零件可重用**：現有 zh-TW 問句模板、`_DIM_TO_FIELDS`（7 格，可當初始 slot 骨架雛形）、`_score_quality`（judge 雛形可升級）、indicator prompt（最後合成用）。
- **新增**：DAG/slot 狀態進 `DeepState`；judge / 選題 / 反思各一個 LLM 呼叫點（薄 adapter + 純函式，沿用 D28 §I 風格便於單測）。
- orchestrator vs LLM 分工：plan/DFS/prune-route/stop = 確定性程式；judge.evaluate / 生成問題 / 合成 = LLM。

---

## 6. 待使用者拍板的選擇點（清單）

1. **六元件架構方向**是否認同？哪塊加強/拿掉？
2. **選題引擎**：採 expand-and-prune DAG [R6]（傾向）／完整 EIG [R2]／飽和度貪婪？
3. **slot 骨架粒度與權重**：每任務 slot 數、必填 vs 選填怎麼分？
4. **停止閾值與預算數字**：用保守預設還是自訂？
5. **反思範圍**：高風險 slot only vs 全 slot？
6. **K/S**：訪談 rubric 只管任務證據，K/S 留 curate？還是納入 DAG？

---

## 7. 參考資料（權威優先，含一句話用途）

- **[R1] Beyond the Resumé: A Rubric-Aware Automatic Interview System** — judge 追蹤 rubric belief + interviewer 補缺 saturate；本架構 B/C 的直接藍本。
  https://arxiv.org/pdf/2603.01775
- **[R2] BED-LLM: Intelligent Information Gathering with LLMs and Bayesian Experimental Design** — EIG 選題；20Q 45%→93%（+37pp）；選題嚴謹版上限參考。
  https://arxiv.org/html/2508.21184
- **[R3] Learning to Ask Informative Questions (EMNLP 2024 Findings)** — 證明 LLM 天生不擅長問 informative 問題（需顯式 EIG）。
  https://aclanthology.org/2024.findings-emnlp.291/
- **[R4] Agentic Design Patterns 2026（ReAct / Plan-and-Execute / Reflection / ToT）** — Plan-and-Execute 92%完成率/3.6x；Reflection 校驗模式。
  https://dev.to/gabrielanhaia/react-plan-and-execute-or-reflection-the-three-agent-patterns-every-engineer-needs-in-2026-355p
- **[R5] MedClarify: information-seeking AI agent for medical diagnosis** — entropy-based 不確定追蹤 + 缺口偵測 + 三停止準則 + 去冗。
  https://arxiv.org/pdf/2602.17308
- **[R6] Using Medical Algorithms for Task-Oriented Dialogue in LLM-Based Medical Interviews** — ★ expand-and-prune DAG（priority-DFS、Open/Explore/Closed、termination score）；本架構 §3 主骨幹。
  https://arxiv.org/html/2510.12490v1
- **[R7] Note2Chat: Multi-Turn Clinical History Taking Using Medical Notes** — 問題錨定外部結構化知識源 → 降幻覺+去冗；grounding 在 catalog 的依據。
  https://arxiv.org/pdf/2601.21551
- **[R8] Dialogue State Tracking（survey / topics）** — slot-value 狀態追蹤的形式骨幹。
  https://www.emergentmind.com/topics/dialogue-state-tracking
- **[R9] AI-driven framework for automated competency formalization (Frontiers 2026)** — 從職業標準自動生能力/KSA（582 能力 / 14000 KSA）；PLAN 硬導出之依據。
  https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2025.1710358/full
- **[R10] LLM-as-a-Judge 2026 guide** — 與人類一致 ~85%；rubric 評估預設法。
  https://www.confident-ai.com/blog/why-llm-as-a-judge-is-the-best-llm-evaluation-method
- **[R11] Autorubric: Unifying Rubric-based LLM Evaluation（arxiv 2603.00077）** — 原子準則 MET/UNMET/CANNOT_ASSESS + 證據；judge/反思做法。
  https://arxiv.org/html/2603.00077v2
- **[R12] BEI / 關鍵事件法（Workitect / Flanagan CIT）** — 事件導向提問法（混合的「事件導向」那半）。
  https://workitect.com/conduct-behavioral-event-interview/
- **[R13] SparkMe: Adaptive Semi-Structured Interviewing for Qualitative Insight Discovery（arxiv 2602.21136）** — 自適應半結構訪談的深度/覆蓋控制、主題跳轉穩定性；§3.1 反疲勞依據。
  https://arxiv.org/pdf/2602.21136
- **[R14] What should I Ask: Knowledge-driven Follow-up Questions Generation in Conversational Surveys（arxiv 2205.10977）** — 知識驅動的 follow-up 生成；grounding 追問。
  https://arxiv.org/pdf/2205.10977
- **[R15] Modular Conversational Agents for Surveys and Interviews（arxiv 2412.17049）** — 訪談 agent 模組化設計（探深/探新/轉主題的動作選擇）。
  https://arxiv.org/pdf/2412.17049
- **[R16] LangGraph Plan-Review-Execute + Interrupts（2026 生產模式）** — DAG-in-state + 單 loop + interrupt() + circuit breaker；§3.2 落地形狀依據。
  https://medium.com/@niteen.badgujar/plan-it-review-it-execute-it-building-a-human-in-the-loop-ai-agent-with-langgraph-c77aa41bcc74
- **[R17] DACUM Occupational Analysis（EKU / OSU ICC，40 年職務分析黃金標準）** — 職責(Duty)→任務(Task)，由在職員工先講出來再精煉；§2.1 任務發現依據。對映 OCS `ocu_units→tasks`。
  https://www.eku.edu/in/guides/dacum-occupational-analysis/
- **[R18] LLMREI: Automating Requirements Elicitation Interviews with LLMs（arxiv 2507.02564）** — 純 LLM 開放訪談完整問出 ~61% + 部分 ~13%（漏 ~25%）→ 需開放+對賬雙軌。
  https://arxiv.org/pdf/2507.02564
- **[R19] Estimating User Domain Knowledge in Conversational Recommenders（arxiv 2512.13173）/ 專家 vs 新手提問適配** — 無個人化時新手放棄、專家厭煩；需即時依能力調深度（專家 10.1 vs 新手 5.9 屬性）；§2.2 人格自適應依據。
  https://arxiv.org/pdf/2512.13173
- **[R20] Speaking the Right Language: Expertise Alignment in User-AI Interactions（arxiv 2502.18685）** — 提問/解釋的用語複雜度要對齊使用者專業度（新手簡單步驟化、專家精簡）。
  https://arxiv.org/pdf/2502.18685
- **[R21] Beyond the Conversation Trap: Designing for Hybrid Human-Agent Interaction Modes（designative.info 2026）/ Conversational UI hybrid trap** — chatbot-first 是陷阱；對話+GUI+inline 依目標分工；直接操作降認知負荷；§2.4 依據。
  https://www.designative.info/2026/03/23/beyond-the-conversation-trap-designing-for-hybrid-human-agent-interaction-modes/
- **[R22] Progressive Disclosure in AI（IxDF / AI Design Patterns，2026）** — 進階功能放次級 UI、先給必要的；同服務新手/專家、防決策癱瘓；§2.4/§2.5 依據。
  https://www.aiuxdesign.guide/patterns/progressive-disclosure
- **[R23] O*NET OnLine — Scales, Ratings（Importance/Relevance/Frequency；core 任務判準）** — 核心任務 = Relevance≥67% 且 Importance≥3.0；§2.5b 核心/次要判定依據。
  https://www.onetonline.org/help/online/scales
- **[R24] Job crafting / 職業突現（Wikipedia job crafting；arxiv 2603.15998 NLP occupational emergence）** — 標準 5 年週期落後、員工塑造工作、idiosyncratic/emergent 任務；§2.6 任務非固定依據。
  https://en.wikipedia.org/wiki/Job_crafting
- **[R25] Semantic Deduplication（NVIDIA NeMo SemDeDup / SemHash / LLM-HAC）** — embed→分群→pairwise cosine→留代表；門檻 0.88 strict / 0.75 balanced / 0.60 high-recall；灰帶用 embedding+LLM 推理判同義；§2.7 解決槓桿 B。
  https://docs.nvidia.com/nemo-framework/user-guide/24.09/datacuration/semdedup.html
- **[R26] ESCO×O*NET Crosswalk / 技能本體 entity resolution（EU Commission；arxiv 2512.03195）** — HITL + BERT bi-encoder 排序候選 + 專家回饋；去重 80–90% 基數縮減；canonicalization 用語意版本化；§2.7 HITL+provenance 依據。
  https://esco.ec.europa.eu/en/about-esco/data-science-and-esco/crosswalk-between-esco-and-onet
- **[R27] Maximum Marginal Relevance（MMR）多樣性重排 / RAG 去冗（SIGIR'98；Azure AI Search 2026）** — λ·相關 +(1-λ)·相異，λ 0.5–0.7；破解 top-k 塌縮成近似重複；§2.7 預防槓桿 A。
  https://espc.tech/learning-hub/blog/enhancing-rag-with-maximum-marginal-relevance-mmr-in-azure-ai-search/
- **[R28] SemHash（語意去重函式庫，實作）** — embed→ANN(Vicinity)→cosine 門檻；`self_deduplicate(threshold)`→selected+duplicates、`rethreshold` 免重算；門檻試 0.75/0.85/0.92/0.95 看 dup 比例；§2.7a API 依據。
  https://medium.com/@sreeprad99/how-semhash-simplifies-semantic-deduplication-for-llm-data-a0b1a53e84fe
- **[R29] Match, Compare, or Select? LLM for Entity Matching（ComEM，arxiv 2405.16884）** — block-and-match 框架；pairwise/side-by-side/select 提示法；zero-shot 即佳、接近人類一致度；§2.7a MATCH 步驟依據。
  https://arxiv.org/html/2405.16884v2
- **[R30] RAG pipeline 順序（fan-out dedup→rerank→MMR；mindit.io / Databricks / Qdrant MMR）** — 最佳順序：檢索→合併→去重→rerank→MMR(最後)；去重在 merge 後 rerank 前；MMR 是 post-scoring 重排；§2.7a 順序依據。
  https://qdrant.tech/blog/mmr-diversity-aware-reranking/
- **[R31] LLM4Jobs：從自由文字職務敘述反推標準職類（arxiv 2309.09708）** — 兩階段 summarize→embed→比對 ISCO/ESCO 職類池；§2.9 自由敘述推斷 OCS 依據。對映既有 ocs-search。
  https://arxiv.org/html/2309.09708
- **[R31b] Multi-Stage Taxonomy-Guided Occupation Classification（IReRa，arxiv 2503.12989）** — LLM 推理 + 檢索 + rerank + taxonomy-guided in-context；自由敘述→職類分類的多階段框架；§2.9 依據。
  https://arxiv.org/html/2503.12989v3
- **[R32] Writing effective tools for AI agents — Anthropic** — 先把工具/能力做扎實，agent 再來用；工具設計原則；§2.10 編輯端能力優先依據。
  https://www.anthropic.com/engineering/writing-tools-for-agents
- **[R33] W3C PROV（PROV-DM/PROV-O/PROV-N）** — provenance 標準：Entity（被追溯物）+Activity+Agent 的 lineage/audit trail；§2.10b provenance 脊椎與 SourceRef 依據。
  https://www.w3.org/TR/prov-dm/
- **[R34] RAG Attribution / Source Attribution（2026）** — 每個生成 claim 連回檢索來源 id 以供驗證；citation registry 先於檢索結構化來源；§2.10b 「每葉項帶來源」依據。
  https://www.aicerts.ai/news/rag-attribution-provenance-tools-transforming-llama-workflows/
- **[R35] FHIR Resource References / Identifiers（HL7 FHIR R5）** — canonical URL 當穩定邏輯識別碼；business identifier = system(命名空間)+value；可用 identifier 做邏輯引用；§2.10c URN/CitableItem 依據。
  https://www.hl7.org/fhir/references.html
- **[R36] RTX-KG2 知識圖譜（含 provenance 的事實，多來源）** — 每個 fact 帶來源/citation、平均約 3 origin；pre-canonical vs canonical 雙版本；persistent URI；§2.10c「K/S 多來源」依據。
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9520835/
- **[R37] jd-pdf-to-json README（OCS→JSON 契約權威）** — `S:\jd-pdf-to-json\README.md`。§6.3.1 tasks[] 條目=共用 blocks 的任務群；§6.3.2 block 由 K/S 新值分界；§6.3.3 版型對應；§4 K/S/A/O/P/T 術語。**欄位投影/payload 設計以此為準。**
- **[R38] 向量庫 metadata 慣例（2026）** — metadata 原子化、只索引會 filter 的欄位（每多索引拖慢 ingestion）、高基數（timestamp）別索引、缺值用 default 非 null；§2.10e 索引紀律依據。
  https://medium.com/@kandaanusha/metadata-filtering-in-vector-databases-e3ebe61c8f76
- **[R39] Data Contract / 解耦 ingestion（2026）** — schema 當「文件化+可測+版本化」契約，producer/consumer 獨立演進、CI 擋破壞；transform 分 parsing/normalization/enrichment/embedding 各自可測、保留 provenance；§2.10e schema_version + typed 契約 + 分層依據。
  https://awadrahman.medium.com/the-decoupling-principle-for-future-proof-data-architectures-9c8ace859905
- **[R40] REST 巢狀資源設計（Moesif / Azure / digitalapplied 2026）** — URI 別深層巢狀(>3 層脆且耦合儲存)、「model the domain not the database」、provenance 當資料回非 URL 路徑；HATEOAS/穩定 id 讓 client 不寫死結構；§2.11 架構結論依據。
  https://www.moesif.com/blog/technical/api-design/REST-API-Design-Best-Practices-for-Sub-and-Nested-Resources/
- **[R41] Cross-encoder reranking 提升短文字檢索（Qdrant reranking；arxiv 2605.27656 job semantic retrieval）** — cross-encoder 把 query+候選一起編碼、抓 bi-encoder 漏掉的語意、重排 top-k；對短職稱/職類匹配有效；§2.11 選配 reranker 依據。
  https://qdrant.tech/documentation/search-precision/reranking-semantic-search/
- **[R42] Qdrant 近似重複偵測（官方 discussion #3268）** — 無內建去重；做法＝scroll 全集 + 對每向量 search(limit,score_threshold) + 排除自己 → 候選，再進一步去重；門檻需依資料校準；§2.11 /tasks/similar 依據。
  https://github.com/orgs/qdrant/discussions/3268
- **[R43] 搜尋分數顯示 / 正規化（Azure AI Search ranking；normalize cosine）** — vector 分數常被轉成單調遞減 ranking score(非真 cosine)；hybrid 多來源範圍不一、直接當機率會誤導；排序可靠、絕對值非機率；§2.11 /search raw score 依據。
  https://learn.microsoft.com/en-us/azure/search/vector-search-ranking
- **[R44] Google API 設計指南 / AIP（resource-oriented design）** — AIP-121 資源導向：名詞資源+少數標準方法(Get/List/Search)、複數集合、自我說明、巢狀淺；Microsoft/Stripe 一致（複數名詞、≤1 層巢狀、別鏡射 DB）；§2.11 API 重命名依據。
  https://google.aip.dev/121

## 8. 可再深挖（討論中按需）
- [R6] DAG 的 priority 動態調整細節、expand 子節點如何避免爆炸（深度/廣度上限）。
- [R1] rubric-aware 的 belief 更新與 saturation 閾值如何設定。
- 反思 pass 與 judge 是否共用同一 rubric（版本化）、如何避免 judge 與 interviewer 互相強化偏誤。
- zh-TW 提問品質的小 eval（對齊 D12 eval-gate）。
