---
title: OPKS（工作產出／行為指標／知識／技能／態度）設計裁決研究
date: 2026-08-01
status: Proposed —— 供 owner 討論；尚未寫 ADR、未動碼
purpose: 把 2026-08-01 三份原料收斂成可裁決的選項比對，並誠實標出兩處未完成的原料缺口
---

# OPKS 設計裁決研究

## 0. 這份回答什麼、不回答什麼

OPKS 就是[實現路線圖](2026-07-25-professional-consultant-architecture-realization-roadmap.md) §11 的
**R4 切片**。R5（Proposal／Current JD durable vertical）已先落地並在真瀏覽器閉環，所以本切片是
**補回被跳過的一格**，不是新方向。

**本文只做裁決比對。**「每個欄位怎麼寫才合格」的判準教材已經備齊，不重寫：

- [iCAP 逐欄位官方標準](2026-07-13-ai-redesign-raw-icap-field-standards.md)
- [國際體系欄位定義與撰寫標準](2026-07-13-ai-redesign-raw-intl-competency-standards.md)

本輪新增三份原料：

| 代號 | 檔案 | 涵蓋 |
|---|---|---|
| A | [`opks-raw-validity-and-ai-regulation`](2026-08-01-opks-raw-validity-and-ai-regulation.md) | SIOP *Principles* 5th ed.、29 CFR §1607.14C、Morgeson 兩篇原著、EU AI Act（含 2026/1744 Omnibus）、NYC LL144、台灣 AI 基本法、證據分級先例 |
| B | [`opks-raw-skills-taxonomies`](2026-08-01-opks-raw-skills-taxonomies.md) | O\*NET 30.3／ESCO／Lightcast／SFIA 9／iCAP 的版本、授權、繁中支援；Workday／SAP／LinkedIn／Microsoft 官方做法；proficiency 現況 |
| E | [`opks-raw-llm-generation-grounding`](2026-08-01-opks-raw-llm-generation-grounding.md) | 結構化生成的輸出量上限、abstention、grounding／citation 實證、schema 誘導填表 |

**未完成：C（工作產出的權威處理）與 D（行為指標與數字門檻）**——見 §5。

---

## 1. 已被鎖死的，不再開放討論

| 來源 | 內容 |
|---|---|
| [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 決定 29–32 | K/S/A 與 Indicator 數值門檻一律帶支持度四級；`unsupported` 不得進正式 JD；`reference_candidate` 只能作候選；**員工按接受不得被記錄成已有行為證據**；Attitude 一併適用 |
| ADR 0040 決定 33–34 | 匯出須標示為採 iCAP 版型的客製 JD；**不得自產職能基準代碼** |
| [`product-notes`](../product-notes.md) | 第一版**不預建尚無 production contract 的 O/P/K/S/A tables** → 本切片的責任正是先給出 contract |
| iCAP 官方（指引 p37／p49／p76） | **A 合併呈現於文件層**，不逐任務；**K/S 須對應行為指標**以避免重複；**操作型任務可合法省略 O**，成果併入行為指標 |

這四條之中，第四條最容易被忽略：**iCAP 的關係圖不是「Task → O/P/K/S/A 五格平列」**，
而是 `Task → O`、`Task → P`、`P → K/S`、`文件 → A`。

---

## 2. 新原料修正了什麼（三條，都會改設計）

### 2.1 `employee_confirmed` 是被實證點名的**弱**證據，不是「次高證據」

Morgeson et al. (2004) *JAP* 89(4) 674–686 是**田野實驗**，不是意見：

- 員工對 ability 陳述比對 task 陳述**平均多認領 0.80 條**（12 個 job component 全部顯著），**d = .52**
- 對**假造（bogus）**的 ability 陳述認領 *M*=2.04 vs bogus task *M*=1.00，**d = .55**
- 操縱極弱——ability 與 task 陳述的唯一差別只是**加上 "ability to" 這個詞**
- 就算在低動機情境（結果不影響受測者）仍觀測到膨脹

> "the motivation to present oneself favorably may be stronger than the ability to differentiate the
> actual abilities associated with a particular position."（p. 682）

**含意**：「員工說這是工作要求」正是被證實會膨脹的那個動作。現行「`employee_confirmed` 可進正式 JD
但保留標記」是**可辯護的下限**，不得再放寬，且 UI 上必須與 `behavior_grounded` 視覺可區分。

原著給的唯一具體對策，我們已經在做：
> "give incumbents explicit task–ability linkages so that they can have the appropriate frame of
> reference and can anchor their ability judgments in the tasks performed."

→ 「K/S 必須有 Task linkage」**有原著背書，不是自創**。

### 2.2 四級支持度是自創；兩端有法源，中間兩級把兩個正交軸壓成一維

- **`behavior_grounded` 是法規意義下唯一成立的那一級**：29 CFR §1607.14C(4) 要求 K 必須是
  「used in and is a necessary prerequisite for **observable aspects of work behavior**」，
  S/A 必須「defined in terms of **observable aspects of work behavior**」。
- **`unsupported` 對映 O\*NET 的 `Recommend Suppress`**、NOS 的非 essential。
- **中間兩級的排序是本 repo 的設計選擇**：Morgeson et al. (2004) p. 683 明說非在職者判斷
  「less likely to be systematically inflated」——所以 `reference_candidate` 在**膨脹**這一軸上其實比
  `employee_confirmed` **更乾淨**，只是在**本職特異性**這一軸上更差。
- O\*NET 的做法是**兩個正交維度**（`Domain Source` = Analyst／Incumbent × `Recommend Suppress` 精度旗標），
  不是一條線性等級。

### 2.3 官方 citations 這條路不存在

Anthropic 官方明文（2026-08-01 核實）：

> **Citations and structured outputs are incompatible** — …the API returns a 400 error. This is because
> citations require interleaving citation blocks with text output, which is incompatible with the strict
> JSON schema constraints of structured outputs.

而 ALCE（EMNLP 2023）實證 citation recall 在 ELI5 上只有 **51.1%**——**要求模型引用不會讓引用變正確**。
引文的價值是把虛構搬到程式抓得到的位置。我們的 verifier 已有 `QUOTE_NOT_VERBATIM` 逐字子字串檢查，
這一類 100% 攔得下。

---

## 3. 需要裁決的五題

### Q1. 支持度：維持四級，還是拆成兩個正交欄位？

| | 甲：維持四級（現行 ADR 0040） | 乙：拆兩軸 `source` × `behavior_link` |
|---|---|---|
| 形狀 | 一條線性等級 | `source`: incumbent／reference／model；`behavior_link`: linked／claimed／none |
| 權威 | 兩端有 §1607.14C 法源；中間排序無先例 | 對映 O\*NET `Domain Source` × `Recommend Suppress` |
| 表達力 | 無法表示「公版來源但已連上 Task」 | 可以；也能表示「員工說的但連不上任何 Task」 |
| 成本 | 零（已 Accepted） | 需**翻案開新 ADR**（Nygard：Accepted 不改內容）；schema 多一欄；UI 多一維 |
| 風險 | 把兩個正交軸壓成一維，日後重構要動資料 | 兩欄的組合有 9 格，其中數格無意義，需要規則收斂 |

**建議：先落甲，但把「四級是自創、且是兩軸的一維投影」寫進實作文檔。**
理由：R4 還沒有任何真實資料，此刻拆軸是在沒有摩擦證據的情況下加複雜度（違反最小方案原則）。
拆軸的**觸發條件**應該寫死：一旦出現「公版候選已連上 Task」或「員工陳述連不上任何 Task」
這兩種現行四級表達不出來的實例，就翻案。

### Q2. 掛載形狀：照 iCAP 的關係，還是五格平掛 Task？

| | 甲：照 iCAP（`Task→O`、`Task→P`、`P→K/S`、`文件→A`） | 乙：五格全部平掛 Task |
|---|---|---|
| 匯出 | 與公版版型天然對齊 | 匯出時要重建 `P→K/S` 關係，資訊不足時只能猜 |
| 去重 | iCAP 明文：K/S 對應行為指標即為了「避免相同職能重複出現」 | 同一條 K 會在多個 Task 下重複出現，需另做去重 |
| 生成難度 | 模型要先產 P 才能產 K/S，鏈較長 | 一次可平行產五格 |
| 與現況相容 | `Task.success_criterion_hint` 正好是 P 的種子 | 同 |
| A 的位置 | 文件層單一清單，符合官方 | 逐任務 A 會嚴重膨脹（A 是最缺行為證據的一格） |

**建議：甲。** 而且 A 一定要文件層——ADR 0040 決定 32 已點名 Attitude「最缺行為證據、最易膨脹」，
逐任務問只會放大它。

### Q3. 生成粒度：一次要模型吐多少？

E 的決定性證據是 ExtractBench（arXiv 2602.12247v2, 2026）：綁定變數是**總輸出量**，不是輸入長度、
不是欄位巢狀深度。369 欄位的 schema 下「no model produced valid output for any of the seven documents」，
整體通過率 **4.6%**；只需 0.9k output token 的任務通過率 **56.3%**。同篇還測到 constrained decoding
讓 validity 從 **51% → 37%**。

| | 甲：整份文件一次生成全部 OPKS | 乙：**以單一 Task 為粒度，一次生成該 Task 的 O/P/K/S** | 丙：每格各一次呼叫 |
|---|---|---|---|
| 輸出量 | 隨 Task 數線性膨脹，直接踩 ExtractBench 的失敗區 | 有界 | 有界 |
| 證據一致性 | 好 | 好——K 與 S 對同一 Task 共享同一組證據 | **差**：拆開等於把填表壓力乘四 |
| 呼叫數 | 1 | N（Task 數） | 4N |
| 成本 | 低但不可用 | 中 | 高 |

**建議：乙。** A（態度）另走文件層一次，不進 per-Task 呼叫。

### Q4. K/S 綁不綁外部 skills taxonomy？

**建議：不綁，維持本地代碼 + 繁中自由文字。** B 已完整論證，摘要：

1. **受控詞彙的官方理由只有互通**（ESCO 明文：offering a "common language"、
   "can be understood by electronic systems"）——而本產品**本機、一次一份、不跨組織、不跨語言**，
   互通收益趨近 0，成本全額發生。
2. **四個候選全部沒有繁體中文**（O\*NET／ESCO／Lightcast 無中文；SFIA 9 只有簡體）。
   自譯 SFIA 並散布**明文需付費授權**。
3. **O\*NET 自己就是雙層**：事實層（18,796 條 task statements）自由文字、靠**撰寫規則**管品質；
   受控層（2,000+ DWA）另建、用途是跨職業比對。我們缺的是撰寫規則的執行，不是缺詞彙表。
4. **綁詞彙表會破壞 evidence linkage**：K/S 被壓成清單裡最接近的通用詞後，
   就不再是訪談原話的可追溯結論。

同時採用（低成本、留縫）：**文件內**同義收斂（identity gate，不跨文件）；`code` 欄保留但不填外部 ID；
**taxonomy 當判準教材、不當下拉值域**（ESCO 的 knowledge 名詞化規則、O\*NET 的 task 撰寫禁令）——
這條在授權上完全乾淨。

### Q5. 訪談怎麼問 K/S？

**建議：禁止直接問「你需要具備什麼能力」，一律從 Task 反推。**

Morgeson et al. (2004) 的操縱**只是加上 "ability to" 這個詞**就produced d≈.5 的膨脹。
一旦我們的顧問問「這份工作需要什麼知識技能」，就是在複製那個實驗條件。

改為：問「你做什麼、怎麼做成的、做壞會怎樣」，由 `job.analyze` 從 Task 與故事反推 K/S 候選，
再讓員工**否決**（否決不會膨脹，認領才會）。

---

## 4. 可以直接採用的（無爭議，有依據）

- **bogus 參照項當品質閘**：候選清單裡混入與本職無關的參照 K/S，員工照單全收 →
  該次訪談的 K/S 整體降級。這正是 Morgeson et al. (2004) 用來**測量**膨脹的方法（H4），可直接當降級條件。
- **不加 per-skill proficiency**：ESCO／O\*NET／SFIA／iCAP **沒有任何一個**在單一技能上掛個人熟練度；
  級別一律掛在更大的單位。現行 `competency_level`／`ocs_level` 的位置與國際慣例一致。
- **若未來加重要性評分，不得只呈現平均值**：Morgeson et al. (2004) p. 682 明示平均會**遮蔽**膨脹，
  要保留 endorsement 計數。
- **不靠提高 thinking／effort 讓模型更誠實**：AbstentionBench 量到 reasoning fine-tuning
  讓 abstention 平均**降低 24%**。
- **unknown 用可為空的 array 表示**：O/P/K/S/A 天然是清單，空 array 就是最誠實的「沒有」，
  不需要 sentinel、不動用 union 預算，沿用現行零 `anyOf` 紀律。

---

## 5. 缺口（誠實標記，未完成）

**C（工作產出的權威處理）與 D（行為指標與數字門檻）兩份原料未產出**——研究 agent 在寫檔前
撞到 session limit；隨後改由主線補查時，`opm.gov`、`training.gov.au`、`hkqf.gov.hk`、
`skillsfuture.gov.sg` 分別以 ECONNRESET／timeout／JS-only 渲染失敗，未取得一手內容。

**尚未回答、且會影響 schema 的問題：**

| 缺口 | 為什麼重要 | 還要查什麼 |
|---|---|---|
| C：無形產出 | iCAP 有 O 欄位、國際體系**都沒有**；服務／監控／預防／決策型工作寫不出交付物時該怎麼辦 | Gilbert *Human Competence* 的 accomplishment vs behavior 原文；Fine 的 FJA "result" 成分；新加坡 Skills Framework 的 Performance Expectations；香港 SCS 的 Range／Assessment Criteria；澳洲 Performance Evidence |
| C：產出缺失是否該回頭質疑 Task | O\*NET 定義 task = "smallest unit of activity with a **meaningful outcome**"——若寫不出產出，可能是 Task 邊界錯 | 有無權威體系明文把「產出缺失」當任務品質訊號 |
| D：數字門檻全禁或條件允許 | 直接決定 verifier 是硬擋還是標記 | 澳洲 Performance Criteria／香港 Assessment Criteria／新加坡 Performance Expectations 是否允許數字；有無官方要求標準須有組織資料佐證 |
| D：指標與級別對齊 | iCAP 審核指標 3.4.3 要求指標能力程度對應職能級別 | SFIA／EQF／AQF 有無等價的「措辭隨級別升階」判準語言 |

**在補上之前不得宣稱 O 與 P 的設計已有權威依據。** §3 的 Q1–Q5 不依賴 C／D，可以先討論。

---

## 6. 下一步

1. 與 owner 討論 §3 的五題（尤其 Q1 是否現在就翻案 ADR 0040 決定 29–30）；
2. 補完 C／D 原料（換時段重試官方站，或改抓 PDF 直鏈）；
3. 才寫 ADR；ADR 之後才寫 `docs/plans/`；plan 之後才動碼。

**本輪不動任何程式碼。**
