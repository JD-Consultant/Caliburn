# OPKS 漸進式蒐集 live smoke（2026-08-06，Luna-Pro）

狀態：**三回合全部 committed，4 次呼叫（3 主顧問 ＋ 1 specialist），花費 US$0.021240865。**

授權：owner 當次核准「用 Luna 先測、上限 US$0.50」。模型取自 `.env` 現行覆寫
（`openai/gpt-5.6-luna-pro`），未改設定。

driver：[`apps/api/scripts/job_analysis_opks_elicitation_live_smoke.py`](../../../apps/api/scripts/job_analysis_opks_elicitation_live_smoke.py)
（commit `dc8da2e`，跑之前工作樹乾淨）。raw capture 在 gitignore 的
`output/job-analysis-opks-elicitation-live-smoke/20260806T065059Z/`。

**這一次不能用來下判斷層結論。** 依既有分界線（設計文檔 §8.2），Luna-Pro 只能驗契約與管線；
ADR 0054 計畫 T18 的四個觀察點全部是判斷層，要用生產模型另跑一次才算數。本篇只記錄
**這次實際發生了什麼**，不宣稱 prompt 或判準已通過。

## 1. 路由與歸因

| 項目 | 值 |
|---|---|
| requested model | `openai/gpt-5.6-luna-pro` |
| **selected model**（4 次皆同） | **`openai/gpt-5.6-luna-pro-20260709`** |
| provider | OpenAI |
| catalog 實價 | in US$0.10/M、out US$0.60/M |
| `max_output_tokens` | 4096 |
| `quality_eligible` | **false**（4 次皆是） |

`quality_eligible=false` 的原因與 2026-08-02 那次相同：alias 被解析成 dated snapshot，與 preflight
定價的 endpoint 字串不相等。**判準沒有放寬**——照原樣記錄。

逐次成本：主顧問 0.003143 / 0.007476 / 0.008037，specialist 0.002585。**沒有出現 luna-pro 路徑
reasoning 爆量（2026-08-02 實測 2.7 倍）的情形**，可能只是這次 packet 小；一次觀測不推翻那筆紀錄。

## 2. 場景（跑之前凍結）

單一 Task「每月彙整門市營運月報」直接種進 Current JD，**只有一句依據**：

> 我每個月初要做一份門市營運月報給區經理。

刻意設計：這句證明「有這份產出」，但完全沒說怎麼做、用什麼工具、對到什麼程度算完成。
**工作產出站得住，知識與技能站不住**——specialist 若把後兩軸也編出來，是可歸因的 grounding
失誤，不是品味問題。

三回合員工原話預先凍結（第 1 回合換話題讓 pre-gate 的 `next_question` 那條放行；第 2 回合閒聊，
看主顧問怎麼問缺口；第 3 回合講出做法）。

## 3. 這次實際發生了什麼

### 3.1 specialist 沒有硬編（觀察點 1）

一次呼叫輸出 4 項，**兩項成立、兩項留缺口**：

| 軸 | decision | 內容 |
|---|---|---|
| 工作產出 | `add_new` | 每月提供給區經理、用於掌握各店營運狀況的門市營運月報 |
| 行為指標 | `add_new` | 每月初完成一份門市營運月報並提供給區經理 |
| 知識 | **`uncertain`** | 缺乏門市營運月報所需資料內容、定義或判讀規則之必要性依據 |
| 技能 | **`uncertain`** | 缺乏除執行彙整外，完成門市營運月報所需具體操作技術之必要性依據 |

這正是決定 18 的 item-level 部分發布：有依據的照常提案，缺依據的留缺口，**不做同軸扣住、
不做整個 Task 扣住**。兩個 gap 落成帶 `subject_task_id` 與 `opks_axis` 的 `OpenIssue`，
receipt outcome 是 `needs_clarification` 且 `proposal_ids` 非空。

**待生產模型覆核的一點**：行為指標「每月初完成一份門市營運月報並提供給區經理」幾乎是把 Task
重述一次當指標。是否「可觀察且有意義」屬 rubric 層，deterministic verifier 依 ADR 0048 決定 24–25
本來就管不到。**不用 Luna 的判斷替它結案。**

### 3.2 缺口摘要是陳述句，不是問句（觀察點 2）

兩則摘要都以「缺乏⋯⋯之必要性依據」結尾，機械檢查 0 則以問號結尾。決定 16 要的形狀成立。

措辭偏公文（「之必要性依據」），但缺口摘要**員工看不到**——問句由主顧問在提問當下生成，
所以這不影響產品文案。

### 3.3 主顧問問行為，沒有問成認領題（觀察點 3）

三題原文：

1. 請回想最近一次店長詢問庫存的情況：你實際查了哪些資料、怎麼處理或回覆，最後幫店長解決了什麼問題？
2. 做每月門市營運月報時，你實際會彙整哪些資料或欄位？這些數字通常怎麼確認、判讀，才知道可以提供給區經理？
3. 你提到各店 POS 的日結資料，月報實際會填哪些欄位或指標？請舉出幾項，並說明除了核對數字是否一致外，還要依什麼情況判斷、註記或處理，才算可以提供給區經理？

**沒有任何一題是「你是否具備⋯⋯能力」。** 第 2 題針對 knowledge 缺口問的是「這些數字通常怎麼
確認、判讀」，正是 ADR 0048 決定 14 要的做法與情境問法。一次 trial，不宣稱穩定。

### 3.4 `issue_resolutions[]` 沒有被當偷懶出口（觀察點 4）

全程只出現一筆：turn 3 的 `{open_issue_ordinal: 2, resolution: answered}`。它通過了 verifier 的
機械前提——同一輪確實有一筆 `support_only` 把員工那句話掛成 task-1 的依據：

```
task-1 support_links（turn 3 之後）
  我每個月初要做一份門市營運月報給區經理。
  月報我是先把各店 POS 的日結資料抓下來對過，數字對不起來就打電話問店長確認，都對上了才填進月報。
```

**沒有出現 `employee_unknown`。** ADR 後果段承認 verifier 擋不住那條，這次沒撞上。

### 3.5 沒有走後門（觀察點 5）

三回合 0 rejection，模型一次都沒有嘗試用 `resolves_open_issue_ordinal` 關缺口
（`RESOLUTION_OPKS_GAP_NEEDS_ISSUE_RESOLUTION` 未觸發）。這條規則是 `a013d3b` 才加的，
本次未被實測撞擊——**未觸發不等於已證明模型不會走那條路**。

## 4. 這次揭露的產品節奏（照 ADR 設計，但帳沒算過）

**specialist 只被呼叫 1 次，不是 2 次。**

turn 3 關掉了 skill 缺口、也讓 task-1 的 digest 改變，但 **knowledge 缺口仍 active**。
決定 3 的 pre-gate 明文「無 active 的 OPKS gap」，所以 task-1 不 eligible，不會重新分析。

行為完全正確，但後果值得寫下來：

> **一個 Task 上有 N 個缺口時，員工答掉其中一個不會觸發再分析；要等 N 個全部關掉
> （`answered`／`employee_unknown`／`not_applicable`）才會重跑一次。**

ADR 決定 3 只寫了「無 active 的 OPKS gap」，沒有討論多缺口的節奏。這代表 specialist 一次開兩個
缺口，就要兩輪追問才會有第二次分析。

還有一件從結果看不出原因的事：turn 3 員工其實同時講到了 knowledge 缺口要的東西（「各店 POS 的
日結資料」就是資料內容），但模型只關了 skill 那一個。是保守，還是它判斷 knowledge 還沒答夠，
**這次無法區分，也不該用 Luna 的判斷推論**。

要不要改（例如「同一 Task 的最後一個缺口被關掉時才重跑」以外的節奏），需要先有生產模型的
觀測與真人資料，不在本篇裁決。

## 5. 誠實邊界

- **一次 trial。** 不宣稱穩定品質，不比較模型。
- **判斷層結論一律待補。** Luna-Pro 只驗管線與契約；四個觀察點要用生產模型再跑一次。
- **場景不完全忠實**：種下的依據不在 transcript 裡（主顧問看得到 Task 與引文，看不到員工何時說的）；
  員工回合預先凍結，接不上主顧問當下真正問的那一題。第 3 回合恰好對得上，是設計運氣不是保證。
- `quality_eligible=false`：本次 4 筆呼叫都不符合既有的歸因判準。
