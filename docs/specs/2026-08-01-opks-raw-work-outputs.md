---
title: 工作產出（O）的權威處理 —— 無形產出、outcome 陳述與「產出缺失」的訊號價值（研究原料）
date: 2026-08-01
purpose: 補 OPKS 研究缺口 C；iCAP 有獨立「工作產出」欄位而國際體系都沒有，本檔找出可替代的權威做法
source_discipline: 只收官方一手；取得失敗的站與未逐字核實的項目一律列入 §6
---

# 工作產出（O）的權威處理（研究原料）

## 0. 取得狀態（先講清楚哪些拿到、哪些沒有）

| 來源 | 狀態 |
|---|---|
| 香港 SCS《Specification of Competency Standards for the Logistics Industry》 | ✅ **PDF 全文取得並逐頁抽字**（1.7 MB，13,202 行）。以下引文皆自抽出文字 |
| 美國 OPM *Delegated Examining Operations Handbook*（Appendix D／G） | ✅ **PDF 全文取得**（2.3 MB，12,794 行） |
| 新加坡 Skills Framework | ❌ 官方 PDF 直鏈回傳 Next.js SPA 殼，非 PDF；未取得 |
| 澳洲 *Standards for Training Packages* / training.gov.au | ❌ `dewr.gov.au`、`asqa.gov.au` 連線 timeout；未取得 |
| Gilbert《Human Competence》accomplishment 原文 | ❌ **未取得一手**。專書無公開全文；同儕審查回顧（*JOBM* 2019, 40(1)）為 403。詳見 §6 |

**因此本檔的權威強度不均**：§1–§3 有逐字一手；§4 只有二手轉述，明確標為未核實。

---

## 1. 香港 SCS：`integrated outcome requirements` —— 找到的最佳「無形產出」處理法

### 1a. Unit of Competency 的官方欄位順序（自 PDF 抽出）

```
1. Title      2. Code      3. Range      4. Level
5. Credit     6. Competency（內含 Performance Requirements，分節編號 6.1／6.2…）
7. Assessment Criteria      8. Remarks
```

**沒有獨立的 output／deliverable 欄位**——與 O\*NET／NOS／ESCO／SFIA 一致，再次確認
**iCAP 的獨立 O 欄位在國際上是例外**。

### 1b. 但每個 UoC 結尾有一段獨立的成果陳述（逐字）

> "**The integrated outcome requirements of this unit of competency are:**
> Capable of inspecting and sorting cargoes for delivery
> Capable of using appropriate equipment to sort and shift cargoes
> Capable of completing required records or notices"

另一個 UoC（`LOWHOM101A`，純知識型、**完全沒有實體交付物**）：

> "**The integrated outcome requirements of this unit of competency is:**
> Capable of using warehousing terms, codes and abbreviations correctly in general communication and
> document handling **so as to avoid delays, mistakes or losses caused by wrong use of terms**"

### 1c. 這兩個例子給出的句式規則

**這是本檔最有用的發現。** 香港的做法不是列交付物清單，而是把成果寫成
**「能力 + 對象 + 結果條件」**，而**無形工作靠「所避免的損害」補上結果**：

| 成分 | 有形工作 | 無形工作 |
|---|---|---|
| 能力 | Capable of completing | Capable of using … correctly |
| 對象 | required records or notices | warehousing terms, codes and abbreviations |
| 結果 | （交付物本身即結果） | **so as to avoid delays, mistakes or losses caused by wrong use of terms** |

→ **判準 C-1：服務／監控／預防／協調型任務的「產出」，寫成「維持住的狀態」或「避免掉的後果」，
不是行為本身。** 若連「避免了什麼」都寫不出來，該任務的成果主張就不成立（見 §3）。

### 1d. 誠實記錄一個權威衝突

同一份 SCS 的 Performance Requirements 大量使用 **"Understand …"** 開頭
（`LOWHOM101A` 的 6.1 底下連續 12 條以 Understand 起首）。這**直接違反** Bloom 修訂版的
可觀察動詞規則——Airasian & Miranda 明言 "Ambiguous verbs such as 'state,' 'list,' 'demonstrate,'…
should be used with great care"，Krathwohl 更點名 "understand" 可涵蓋從記憶到綜合的任何層次
（見 [2026-07-13 國際體系原料](2026-07-13-ai-redesign-raw-intl-competency-standards.md) §3a）。

**不要假裝各權威一致。** 現況是：香港 SCS 在**知識型**單元上使用不可觀察動詞；
Bloom／O\*NET／OPM 這一系要求可觀察動詞。本 repo 應採後者（理由見 §2 的 OPM 規則），
並把香港的**成果句式**（§1c）與其**動詞用法**分開採用。

### 1e. 數字門檻

抽出的 UoC 內容中，Performance Requirements 與 outcome requirements
**未出現任何數值門檻**（無百分比、無時限、無次數），一律為質性描述。
——單一產業 SCS 的觀察，不足以推論全體系，但與「本 repo 禁止無來源數字」同向。

---

## 2. 美國 OPM：能力必須連回任務，否則刪除（雙向）

**權威文件：** U.S. Office of Personnel Management, *Delegated Examining Operations Handbook*,
Appendix D "OPM's Job Analysis Methodology" 與 Appendix G（PDF 全文取得）。

### 2a. Uniform Guidelines 要求 task↔competency linkage（逐字，Appendix D, p. D-1）

> "The Uniform Guidelines also require that **the tasks and competencies be linked to demonstrate the
> respective job-relatedness of competencies**. The linkage also ensures that there is a clear
> relationship between the tasks performed on the job and the competencies required to perform those tasks."

### 2b. 未連結者一律刪除——**而且是雙向的**（Job Analysis Template, Step 6d 逐字）

> "You and SMEs should then **eliminate any tasks not linked to one or more competencies** and only
> competencies that are not linked to at least one task."

以及 Step 6c 的註（逐字）：

> "(Note: **If any tasks/competencies are not linked, you should reconsider whether all critical tasks
> and competencies have been considered**)"

→ **判準 C-2：連結缺失是「回頭重審兩邊」的訊號，不是「把缺的那邊補上」的訊號。**
這正是本 repo 路線圖 §11.2「O/P/K/S 應能觸發 Task reopen，而不是把錯誤 Task 補完整」的官方對應物。

---

## 3. 「產出寫不出來」是否該回頭質疑 Task？

**沒有任何體系明文寫「產出缺失 ⇒ Task 邊界有問題」**（誠實結論）。但有三條可組合的官方依據：

1. **O\*NET 的 task 定義本身**（已於 2026-07-13 原料逐字引用）：
   task = "the smallest unit of activity with a **meaningful outcome**"。
   → outcome 是 task **成立的定義要件**，不是可選欄位。寫不出 outcome，
   等於這條東西不符合 task 的定義——**它可能是步驟、工具或動作，不是 Task。**
2. **OPM 的雙向刪除規則**（§2b）：官方在 linkage 缺失時要求**重審兩邊**，不是單向補齊。
3. **iCAP 的合法例外有明確邊界**（指引 p37 逐字，2026-07-13 原料 §4）：
   > 「若該項任務**僅有行動或操作性質之工作成果**，則不必列出工作產出，
   > 建議將相關成果列於行為指標之描述中」

   → iCAP 允許省略的是**欄位**，不是**成果**。成果必須改寫進行為指標，仍然要存在。

**判準 C-3（三條合成，可直接寫進 prompt 與 verifier）：**

| 情況 | 處置 |
|---|---|
| 有有形交付物 | 寫進 O（名詞化、可查核） |
| 無交付物但講得出「維持的狀態／避免的後果」 | O 留空，成果寫進 P（iCAP 合法路徑 + 香港句式） |
| 連狀態或後果都講不出來 | **不是補 O，是把該 Task 標為邊界可疑**，回到 `work.reconcile` |

第三列是 O\*NET task 定義 + OPM 雙向規則的直接推論；**本 repo 自行合成，無單一官方條文可引**，
應在 ADR 中如實標註。

---

## 4. Gilbert 的 accomplishment（**未取得一手，僅供背景**）

Thomas F. Gilbert《Human Competence: Engineering Worthy Performance》（McGraw-Hill, 1978；
HRD Press／ISPI Tribute edition, 1996）提出 behavior 與 accomplishment 的區分，
與 First Leisurely Theorem（worthy performance = valuable accomplishments ÷ costly behavior）。

**本輪未能取得專書原文或同儕審查全文**（*JOBM* 2019, 40(1) "Human Competence Revisited: 40 Years of
Impact" 回傳 HTTP 403；其餘搜尋結果為課程 wiki、廠商部落格等不符來源紀律者，已全部剔除）。

→ **不得在 ADR 中引用 Gilbert 的逐字定義。** 若要用「產出是行為的產物」這個論點，
現階段應改引 §1c（香港逐字）與 §3.1（O\*NET task 定義逐字），兩者都已一手核實。

---

## 5. 對 Caliburn 的判準彙整

| 編號 | 判準 | 依據 |
|---|---|---|
| C-1 | 無形產出寫成「維持的狀態」或「避免的後果」，不寫行為本身 | 香港 SCS `integrated outcome requirements` 逐字（§1b） |
| C-2 | linkage 缺失 ⇒ 重審兩邊，不單向補齊 | OPM Job Analysis Template Step 6c／6d 逐字（§2b） |
| C-3 | 連狀態或後果都寫不出 ⇒ 標記 Task 邊界可疑，不補 O | O\*NET task 定義 + OPM 規則 + iCAP p37；**合成判準** |
| C-4 | O 欄位可空；iCAP 的獨立 O 欄位是國際例外，匯出才需要它 | 香港／O\*NET／NOS／ESCO／SFIA 皆無獨立欄位（§1a） |
| C-5 | 採香港的**成果句式**，不採其**動詞用法** | §1d 的權威衝突 |

---

## 6. 查不到／需二次確認（誠實清單）

1. **Gilbert 一手文本**——未取得（§4）。ISPI 官方對 accomplishment 的定義亦未取得。
2. **新加坡 Skills Framework 的 Performance Expectations 欄位定義**——官方站回傳 SPA 殼，未取得。
   這是唯一已知**明確有「期望表現」欄位**的政府體系，值得日後補。
3. **澳洲 Performance Evidence 是否使用次數門檻**（如 "on at least 3 occasions"）——
   `dewr.gov.au`／`asqa.gov.au` 連線 timeout，未取得。這一條直接影響 D 的數字門檻裁決。
4. **香港 SCS 的跨產業一致性**——本輪只讀了物流業一份。`Assessment Criteria` 欄在該份中僅出現 1 次
   （其內容實際由 `Performance Requirements` 承載），是否為該產業排版特例未確認。
5. **香港 SCS 官方版本日期**——抽出文字中未見明確版次；HKU SPACE 為轉載host，
   原始出處應為 hkqf.gov.hk，**引用前須回官方站確認版本**。
