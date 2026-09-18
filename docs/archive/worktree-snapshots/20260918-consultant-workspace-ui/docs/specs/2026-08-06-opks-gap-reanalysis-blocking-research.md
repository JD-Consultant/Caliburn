---
title: OPKS 缺口把再分析鎖死——pre-gate 的「無 active gap」該不該留
date: 2026-08-06
status: 待裁決，尚未開 ADR
purpose: 裁決「一個 Task 有未解 OPKS 缺口時，新證據到達可不可以重新分析」
---

# OPKS 缺口與再分析的封鎖關係

## 0. 這份回答什麼、不回答什麼

**回答**：ADR 0054 決定 3 的 pre-gate 條件「無 active 的 OPKS gap」在生產模型下造成什麼後果、
它實際擋住了什麼、有哪些選項、代價各是什麼。

**不回答**：缺口摘要要怎麼寫、specialist 該開幾個缺口才算好（判斷品質問題，要 rubric 與真人
資料，不是這裡）；也不翻案 0054 的 durable 語意、digest 範圍或四種 receipt。

**本輪不動任何程式碼。**

## 1. 觸發這份研究的實測

2026-08-06 的 [OPKS 漸進式蒐集 live smoke](../experiments/2026-08-06-opks-progressive-elicitation-live-smoke/README.md)
兩次 run（Luna-Pro、Opus 5），同一個凍結場景：Current JD 有一個 Task，只有一句依據。

| | 第一次分析開的缺口 | turn 3 員工回答後關掉 | 仍 active | 第二次分析 |
|---|---|---|---|---|
| Luna-Pro | 2 | 1 | 1 | **沒有** |
| **Opus 5** | **4** | 1 | **3** | **沒有** |

Opus 那一輪的具體狀態：員工在 turn 3 講出了做法（「先把各店 POS 的日結資料抓下來對過，
數字對不起來就打電話問店長確認」），這句話**已經**成為 task-1 的 SupportLink、
`analysis_input_digest` **已經**改變，主顧問也正確地用 `issue_resolutions.answered` 關掉了它
命中的那個缺口。

**但 specialist 永遠看不到這句話**，因為另外三個缺口還 active。

模型越誠實（缺口開得越細），再分析被鎖得越久。

**但不能把這次觀察外推成「第二次分析永遠不會發生」**（本文初版這樣寫，2026-08-06 修正）。
同一次 run 也顯示：第 2 回合主顧問**主動問了**缺口、第 3 回合員工回答後主顧問**正確關掉**其中
一個。缺口確實會被問、也確實會一個一個關掉，觀察到的速度約**一回合一個**；四個缺口再花
3–4 回合就清完，一場正常長度的訪談跑得完，清完後 pre-gate 自然放行、第二次分析會正常發生。

該 run 只有 3 回合、單一 Task。**真正的殘餘風險是尾端衰減**——訪談結束時仍開著缺口的 Task
（多半是後期才發現的），其已回答內容產出為零——不是全面失效。本文以下的診斷與選項比對
在技術上仍然成立，但**嚴重程度應以此段為準**。

## 2. 原始理由：文檔怎麼說這條規則要幹嘛

先把 0054 自己寫下的理由找齊，再談要不要動它。

**(i) pre-gate 的自述目的**——ADR 0054 決定 3 的標題就是判準：

> **Pre-gate 只擋明顯過早，不得宣稱資料完整**

**「明顯過早」是這條規則的全部授權範圍。** 缺口未解 ＋ 員工剛給了新依據，
**不是**「明顯過早」——那是分析最該發生的時刻。

**(ii) 成本上限不是這條規則給的**——ADR 決定 5 與研究稿 §4.1 都把浪費上限歸給 digest receipt：

> 證據太薄時由 specialist 回全 `uncertain`，**該 digest 的終端 receipt 使浪費上限為
> 「每個輸入狀態一次呼叫」**。（決定 5）

> **因此接受一次浪費**：⋯⋯該 digest 的 receipt 會擋住重跑，**浪費上限是「每個輸入狀態
> 一次呼叫」**，不累積。（研究稿 §4.1）

兩處都沒有把成本上限歸給「無 active gap」。**拿掉它不會鬆動任何已載明的成本保證。**

**(iii) 唯一與封鎖有關的理由，是為另一條寫的**——研究稿 §4.7 末句：

> **agenda 位置**：「Task 邊界矛盾／責任問題 → 一般 open issue → **OPKS gap** → 遺漏掃描」。
> 這與 pre-gate 的「無指向此 Task 的**未解 issue**」是同一條規則的兩端，不需要新機制。

這句話的內容是對的，但它講的是**決定 3 的另一條**——「無指向該 Task 的未解**邊界／矛盾／
證據不足** issue」。那條的意思是「這件工作是什麼、是不是他的，都還沒確定，先別花錢分析細節」。
`_agenda_rank()` 的註解也照這個理由寫：

> OPKS gap 最後，因為它只在 Task 已經站穩之後才有意義（這與 pre-gate 的「無指向此 Task 的
> active issue」是同一條規則的兩端）。

**問題就在這裡：OPKS 缺口不是「Task 站不站得穩」的問題。** 邊界／責任 issue 表示這件工作本身
還沒確定；OPKS 缺口表示**這件工作已經確定了，分析也已經跑過了，只是某幾軸還缺依據**。
兩者被寫成「同一條規則」，但它們的前提相反：前者要等 Task 站穩，後者的 Task 早就站穩了。

決定 3 的清單把兩者並列成兩個獨立 bullet，卻沒有為第二個寫下自己的理由。
**這份研究的結論就是：第二個 bullet 繼承了不屬於它的理由。**

## 3. 診斷：兩個 damper，其中一個是多餘或有害的

ADR 0054 決定 3 的 pre-gate 對「同一個 Task 要不要再分析」有**兩條**獨立條件：

- **(a) 無相同 `analysis_input_digest` 的終端 receipt**（決定 29；付費邊界）
- **(b) 無 active 的 OPKS gap**（決定 20 定義 active）

實作上 (a) 住 `select_scheduled_opks()`（`journal.get()`），(b) 住
`eligible_opks_candidates()` 的 `_issue_blocks()`。

**逐情況拆開看 (b) 做了什麼：**

| 情況 | (a) 的行為 | (b) 的行為 | (b) 有沒有用 |
|---|---|---|---|
| digest 未變（員工還沒回答） | 找得到當初產生這些缺口的那筆 receipt → **擋** | 擋 | **多餘**。(a) 已經擋住了 |
| digest 已變，且新證據正是缺口的答案 | 新 digest 沒有 receipt → 放行 | **擋** | **有害**。這正是要重新分析的時刻 |
| digest 已變，但變動與缺口無關（改敘述、無關回合追加依據） | 放行 | 擋 | **有用**：省下一次多半會重開同樣缺口的呼叫 |

所以 (b) 的真實功能只有第三列：**抑制「與缺口無關的 digest 變動」造成的重跑**。
代價是它同時擋掉第二列——而第二列才是產品要的東西。

**(b) 還有一個沒被寫下來的副作用：它是目前唯一防止缺口累積的東西。**
`opks_generation.py` 落地缺口時是 append：

```python
"open_issues": (*state.work_model.open_issues, *gap_issues)
```

今天不會累積，只因為「有 active 缺口的 Task 永遠不會被再分析」。**(b) 一旦放寬，累積就會發生**
——新分析對同一軸再開一個缺口，舊的那個不會消失。這一點必須跟 (b) 一起處理，不能只拿掉 (b)。

## 4. 權威來源核對

### 4.1 Microsoft Agent Framework — HITL 的 pending request 沒有「全部答完才前進」的閘

[Human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
（`ms.date` 2026-07-16、`updated_at` 2026-07-17）。框架把待答請求做成 `request_id` 鍵控，
回應以 dict 交回：

> Handle any pending human feedback requests. … `responses[request_id] = guess`
> … Run the workflow until there is no more human feedback to provide

> **Runs are not isolated; state is preserved across multiple calls to run.**

> The framework automatically routes the responses back to the appropriate executor based on the
> original request.

**API 形狀上不存在「所有 pending request 都被回答才能繼續」這個閘**：`responses` 是「你手上有的
那些」，`run()` 拿到就繼續。這是**形狀先例**，沿用 0054 研究稿定下的使用邊界：
「此處只借 durability 形狀，不引入其框架，也不用它證明任何 OPKS 領域語意」。

**誠實限度**：該頁沒有一句話直接寫「部分回答也應推進」，是我從 API 形狀與範例迴圈讀出來的。
它證明的是「不設全域閘是一個大廠會做的設計」，不證明我們該怎麼做。

### 4.2 Anthropic — 只在能證明改善時才加複雜度

[Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) 逐字：

> you should consider adding complexity **only** when it demonstrably improves outcomes.

> **Agentic systems often trade latency and cost for better task performance**, and you should
> consider when this tradeoff makes sense.

evaluator-optimizer（反覆修正）值得用的條件：

> when we have clear evaluation criteria, and when iterative refinement provides measurable value

**對本案的意義是雙向的**：它同時反對「為了省錢多加一層節流機制」，也反對「為了多分析幾次
而放寬成本邊界」。判準是**能不能證明改善**。§1 的實測就是那個證明：目前這條線在生產模型下
**第二次分析根本不會發生**，所以現況不是「省錢」，是「功能沒發生」。

### 4.3 Ask or Assume?（arXiv 2603.26233v2）——追問本身有大幅價值，但不回答批次問題

三種策略在 underspecified SWE-bench 上（Claude Sonnet 4.5）：

| 策略 | resolve rate |
|---|---|
| Never-Ask | **54.80%** |
| Calibrated-Ask（UA-Multi） | 69.40% |
| Always-Ask | **70.40%** |

UA-Multi 平均 3.06 次詢問／題，且「queries distributed across the early and middle stages of
execution」，處理方式是「agents pause execution when clarification is needed, receive answers,
**then continue within the same trajectory**」。

**誠實限度**：該論文**沒有**比較「一次問完再一起處理」與「答一題就往前一步」，也沒有
re-run 任務的實驗。它能支持的只有一件事：**追問的價值很大（+15.6 個百分點），不該為了省一次
呼叫而讓追問結果進不了分析**。

### 4.4 被拒絕的來源

網搜「agent workflow re-run analysis when partial new information arrives」回到的全部是
Medium／DEV／廠商 blog（`medium.com`、`dev.to`、`augmentcode.com`、`mindstudio.ai`、`arize.com`）。
**一律不採用**——來路不明、無可核實的實驗，且其中「no subsequent step executes until current
tests pass」這類句子與本案不同構（那是 CI gate，不是 HITL）。照既有規矩，讀不到權威來源就說沒有。

## 5. repo 內部先例：同構的問題以前怎麼判的

放寬 (b) 之後必須回答「新分析跑完了，舊缺口怎麼辦」。這個問題的形狀
——**新資訊到達時，既有紀錄由誰決定生死**——repo 判過三次，判準一致。

### 5.1 「不猜」：要動既有紀錄，模型必須明確指認哪一筆

`SupportLink` 的 supersession（[Task 邊界研究稿](2026-07-28-task-boundary-merge-split-and-identity-research.md) §12.3）
處理的正是同一件事：新回合的話推翻了舊引述，舊的那條依據該怎麼辦。判法是給模型一個
`supersedes_support_ordinals[]` 欄位**明確指認**，並寫下理由：

> 若模型無法指認是哪一條，**application 只能自行猜測，而那是語意判斷**，依 §9.5 末段
> 不得放進 verifier。⋯⋯**這是本欄位存在的唯一理由，不作其他用途。**

**規則：application 永遠不猜哪一筆舊紀錄被取代了。**

### 5.2 「不用文字相似度配對」——已被否決兩次

ADR [0044](../adr/0044-partial-jd-task-reconciliation-and-human-confirmation.md)：

> **文字相似度不能可靠決定兩筆工作是否相同**；AI 也不得在員工未確認時靜默合併或刪除 Current JD。

ADR [0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md) 決定 8 與其脈絡段：

> **衝突與 stale 一律以 `entity_id` 判定，不用文字相似度。**

> 被拒候選只能靠文字相似度辨認——**正好走回 0044 已否決的那條路**。

**規則：配對只能靠穩定 identity；沒有穩定 identity 就不要配對。**

### 5.3 「不得累積」有實測代價

ADR [0047](../adr/0047-model-owned-open-issue-closure.md) 脈絡段量過：

> open issue 單調累積，而**每一輪 Context Packet 都要重新渲染全部 open issue**。實測一則
> 約 200 bytes⋯⋯已被回答卻仍在清單上的 issue 會排擠真正的缺口——這對職務說明書品質是
> **確定**的損害，而不是假設性的。

**規則：重複或過時的 issue 留在清單上，是已量測過的損害，不是理論風險。**

### 5.4 head-of-line blocking 已經是 0054 認得的問題

決定 29 讓終端失敗寫 `failed` receipt，理由寫在 `_is_terminal_failure()` 的 docstring：

> 作用是解除 head-of-line blocking——否則同一個 Task 每輪都會被重新排定、每輪都再燒一次錢。

0054 已經替**失敗路徑**解掉了 head-of-line blocking。§3 顯示的是：
**(b) 在成功路徑上把它重新製造了一次**，而且更糟——失敗那條至少會停在一次呼叫，
缺口這條是直接把後續分析全部鎖死。

### 5.5 這三條先例對「舊缺口怎麼辦」的直接推論

我在前一版建議的「**新分析的缺口取代舊的**」**同時違反 5.1 與 5.2**：

- 缺口的 ID 是 `{operation_id}-gap{index}`，**每次分析都不一樣**——跨分析沒有穩定 identity。
- 因此「哪個新缺口對應哪個舊缺口」只能靠**文字**配對，那是 0044／0051 兩度否決的路。
- 而且它讓**模型的記憶力**凌駕已持久化的紀錄：新分析漏講一項，那項就靜默消失，
  沒有人回答過它、也沒有人問過它。這正是 0043「不得覆寫員工文件」與 0044「不得靜默刪除」
  要擋的形狀。

**取代方案因此出局，不是因為它不好用，是因為它踩了三條既有裁決。**

## 6. 選項比對

前提：**任何選項都不動 (a)**。相同 `analysis_input_digest` 只付一次錢是 0054 決定 31 的付費邊界，
不翻案。

| | A：拿掉 (b)，由 digest receipt 單獨守門 | C：`answered` 才解鎖一次 | D：限制 specialist 一次開幾個缺口 | E：不改 |
|---|---|---|---|---|
| 何時再分析 | digest 一變就分析 | 只有主顧問送出 `answered` 且 digest 變了才分析 | 同現況 | 同現況 |
| Opus 場景（4 缺口） | turn 3 就重新分析 | turn 3 就重新分析 | 缺口變少，但仍要全關 | 約再 3–4 回合全關後才分析 |
| 每個 Task 的呼叫上限 | 每個輸入狀態 1 次（0054 既有上限） | 每次 `answered` 1 次 | 同現況 | 同現況 |
| 無關編輯造成的重跑 | **會**（每次 1 呼叫） | 不會 | 不會 | 不會 |
| 缺口累積問題 | **必須一起解**（§3 末、§6.1） | **必須一起解** | 不出現 | 不出現 |
| 與 owner 既有裁決的相容性 | 相容 | 相容 | **牴觸**：owner 已裁定同一軸可以有數個不同缺口（`0b261fc`），Opus 實測也確實開了兩個獨立知識缺口 | 相容 |
| 新機制 | 無（少一條規則） | 有（新的解鎖條件） | 有（新的產出限制） | 無 |

**D 應被否決**，理由不只成本：owner 在 2026-08-05 用「不知道交出什麼文件」與「不知道要達到
什麼狀態」是兩件事，否決了 `DUPLICATE_GAP_AXIS` verifier 規則；Opus 這次開的兩個知識缺口
（涵蓋範圍與定義／資料來源）正是那個反例的實例。限制缺口數＝獎勵模型少講實話，與北極星相反。

**E（不改）的真實代價**（2026-08-06 依 §1 末段修正，初版寫成「功能缺席」是過度推論）：
缺口會被問、會一個一個關掉，全部關完後第二次分析正常發生，所以功能**沒有**缺席。
代價是**尾端衰減**——訪談結束時仍開著缺口的 Task，其已回答內容產出為零；缺口開得越多、
該 Task 發現得越晚，衰減越明顯。另有 K/S 碎片化的反向好處：等答完再一次分析，
文件層 K/S（0048 決定 6，多對多）切得比零碎產出完整。

### 6.1 放寬之後，舊缺口怎麼辦——三個子選項

| | 取代（**已出局**） | **G：重新分析只收候選，不建新缺口** | F：讓 specialist 明確指認哪個舊缺口不再成立 |
|---|---|---|---|
| 怎麼配對新舊 | 只能靠文字 | **不配對** | 靠 ordinal，模型明確指認 |
| 違反 5.1（不猜） | **違反** | 不違反（沒有猜的餘地） | 不違反（就是 5.1 的作法） |
| 違反 5.2（不用文字相似度） | **違反** | 不違反 | 不違反 |
| 舊缺口會不會靜默消失 | **會** | 不會 | 不會 |
| 會不會累積重複（5.3） | 不會 | **不會**（根本不建新的） | 不會 |
| 契約成本 | 無 | **無** | `opks_result_v1` 要加欄位與 ordinal，**推翻 0054 決定 15 的「零 schema 變更」與決定 20 的「specialist 不解決 issue」** |
| 代價 | — | 新證據掀出的**全新**缺口要等現有缺口清光才浮現 | 契約變大；specialist 取得它原本沒有的權力 |

**G 的完整規則**：一個 Task 已經有 active 缺口時，這次分析的 `uncertain` **不落地**；
proposals 照常提交。缺口的生死維持 0054 既有的三條出路——員工回答（`answered`，移除）、
員工說不知道／不適用（寫 `terminal_resolution`，轉記憶）、Task 離開 Current JD（移除，決定 26）。
**specialist 從頭到尾不能刪缺口**，與 0054 決定 20 一致。

**F 值得記著但現在不做。** 它其實是 5.1 那條先例的正解，而且 ADR 0047 的理由
（「只有處理該回合答案的模型知道自己上一輪的問題有沒有被回答」）套到 specialist 身上也成立
——缺口是它提的，它最有資格說還算不算數。但它要動 wire schema、要給 specialist 解 issue 的
權力，而**目前沒有任何測量顯示 G 的代價真的發生了**。依 Anthropic 那句
「only when it demonstrably improves outcomes」，先做 G，等實測看到浪費再考慮 F。

### 6.2 G 讓前一版的兩個未解問題直接消失

前一版列的兩個待解問題，在 G 之下不存在：

1. ~~缺口累積~~——不建新缺口就不會累積。
2. ~~`last_asked_turn_id` 跟著舊缺口消失~~——缺口物件從頭到尾**沒有被換掉**，
   `last_asked_turn_id` 自然留著，主顧問不會重問。

這是 G 相對取代方案最實際的好處：**它不是「解決了那兩個問題」，是讓它們沒有機會發生。**

### 6.3 G 剩下的一個待裁決細節

被抑制的 `uncertain` 不落地時，receipt 的 `outcome` 該記什麼？決定 28 的 validator 把
`needs_clarification` 綁在 `gap_issue_ids` 非空上。若這次只提了候選，outcome 會記成 `proposed`
——**receipt 因此不會顯示「specialist 其實還說了三項看不出來」**。

兩種寫法，留給 ADR：

- 就記 `proposed`／`no_change`。理由：receipt 記錄的是**狀態變更**，而這次確實沒有新增缺口。
- 在 payload 加一個 `suppressed_gap_count`。理由：診斷時看得出「模型還在說缺」。
  代價是多一個只為診斷存在的欄位。

傾向前者（少一個欄位），但這確實是資訊量的取捨，不是明顯對錯。

## 7. 仍缺的資料

- 真實訪談中一個 Task 平均會開幾個缺口（目前 n=2 次 synthetic run，Opus 開 4 個）。
- 員工回答一個缺口時，順帶答到其他缺口的比例（Opus 這次是 1/4 精準命中，沒有溢出）。
- 放寬後每份職務說明書實際多花多少錢（Opus 一次 specialist 呼叫本次量到 US$0.024）。
### 7.1 決定 8 的兩個門檻怎麼量

**application 不能自己判斷兩個缺口是不是語意重複**——那需要文字相似度，0044 與 0051 決定 8
已經封死。因此兩個比率**一律離線量**：從 raw capture 與當時的 packet 取樣，由人工或獨立
eval adjudicator 判定，**結果不寫回 domain state，eval 的相似度邏輯不得搬進 application**。

**門檻 (a)——重複負擔。** 量兩個數字，後者才是真正的傷害：

```text
duplicate_gap_rate =
  本次新建 gap 中，經離線審查判定「已被當時 packet 內 active／terminal gap 涵蓋」的數量
  ÷ 本次新建 gap 總數

duplicate_question_rate =
  員工實際收到的問題中，語意上已問過、或已有 terminal resolution 的比例
```

有重複 gap 不代表它真的被排進 agenda（一次只問一題，訪談可能先結束）。
**`duplicate_question_rate` 才是員工感受到的打擾**，`duplicate_gap_rate` 只是它的上界。

**門檻 (b)——分類方案的召回損失。** 必須用 shadow evaluation 量，**不得直接上線試**：
拿同一批 capture 重跑一次帶 `known_gap_ordinal` 的 specialist，比對它標成 `existing` 的項目
是否真的被既有缺口涵蓋。

```text
false_existing_rate =
  被模型標成 existing、但離線審查判定「不被任何既有 gap 涵蓋」的數量
  ÷ 被標成 existing 的總數
```

這個比率直接對應「職務說明書永久少一項」的機率。**沒有這個數字就不該採用該方案**，
因為門檻 (a) 再高也回答不了「換過去會不會更糟」。

### 7.2 其他仍缺的資料

- 真實訪談中一個 Task 平均會開幾個缺口（目前 n=2 次 synthetic run，Opus 開 4 個）。
- 員工回答一個缺口時，順帶答到其他缺口的比例（Opus 這次是 1/4 精準命中，沒有溢出）。
- 放寬後每份職務說明書實際多花多少錢（Opus 一次 specialist 呼叫本次量到 US$0.024）。

## 8. 外部意見核對（2026-08-06，只看過 ADR 0055、沒看過本 repo）

owner 取得一份外部意見。逐條核對後：**三處採納，兩處因該意見看不到本 repo 的實作而不成立，
一處是它主推的方案有它沒察覺的漏洞。**

### 8.1 採納：「能指認 ≠ 有權修改」——我的 ADR 決定 8 推理錯了

> 目前 ADR 決定 8 把「給 specialist ordinal」＝「給 specialist 解 issue 的權力」，這個推論不成立。

**對，我推錯了。** 0054 決定 20 的「不配發 ordinal」是針對**主顧問 packet**——那裡 ordinal 正是
`issue_resolutions[]` 的指認手段，所以不配發＝結構上不可解決。但 `opks_result_v1`
**根本沒有任何解決 issue 的欄位**，給 specialist ordinal 只是讓它能指認，拿不到寫入權。

拒絕該方案的理由必須改寫，不能再說「它推翻決定 20」。

### 8.2 採納：LangGraph 是第三個「明確 identity」的先例

[LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)（已核實）：

> **map each interrupt ID to its resume value.** This ensures each response is paired with the
> correct interrupt at runtime.

> the node restarts from the beginning of the node where the interrupt was called when resumed
> … **Side effects called before interrupt should (ideally) be idempotent**

多個同時待答的 interrupt **以 ID 配對，不靠順序也不靠文字**——與 §5.1、§5.2 同向，
補強「配對只能靠明確 identity」這條。（LangGraph 本身已由 ADR 0030 退場，此處只引其設計判準。）

### 8.3 採納：決定 3「丟掉 uncertain」要改

與我在 §6.1 之後自行得到的結論一致，不重複論證。

### 8.4 不成立：「active gap 進 packet 會造成自我觸發」

該意見擔心 gap 進 packet 後會 `分析 → 建 gap → digest 變 → 又符合條件 → 再建 gap`。

**本 repo 不會。** `compute_analysis_input_digest(task)` 的**簽章只收一個 `Task`**，
缺口住 `work_model.open_issues`，呼叫端沒有東西可以多傳——這是 `opks_digest.py` 開頭寫明的
「簽章層事實」。缺口進 packet 不會改變 digest，**自我觸發在型別上不可能發生**。

### 8.5 不成立：「應拆成 `trigger_digest` 與 `packet_digest`」

該意見認為 packet 內容（含 known gaps）必須全部凍結，否則 replay 會送出不同的 packet。

**這會反轉 0054 一個刻意的決定。** 缺口記憶不進 `read_set`，理由寫在 `opks_context.py`：

> `settled_gaps` 刻意不在裡面。OPKS child 的 freshness 契約是 `analysis_input_digest`；
> 終結記憶是 context，不是 authority input。放進來會製造一個**與分析輸入無關的 abandon 觸發器**
> ——別的 Task 上有人回答「不知道」，就會讓這個 child 白跑一趟。

實際後果也不嚴重：replay 時若某個缺口已轉 terminal（不需要新證據，所以 digest 不變），
specialist 拿到的記憶區會多一則。它分析的**證據完全相同**，只是記憶更完整——
**分析結果更好，不是更錯**，而付費邊界（同一 digest 一次）完全沒鬆動。
反過來把它放進 read_set，那一輪會 abandon、下一輪再排一次，**反而多付一次錢**。

不採納。

### 8.6 它主推的方案有一個沒被察覺的失敗模式

該意見主推：specialist 把 uncertainty 明確分成 `existing`（指向既有缺口 ordinal）與 `new`，
application 只為 `new` 建 issue。它並宣稱「模型若判斷錯誤，錯誤會以重複缺口呈現，
而不是靜默遺失」。

**只有一半成立。** 兩個方向的誤判後果不對稱：

| 模型誤判 | 該意見的方案 | 本文 §6.1 的 H（既有缺口只進記憶區、所有 uncertain 照常落地） |
|---|---|---|
| 把**既有**當成新的 | 產生重複缺口（**看得見**） | 產生重複缺口（**看得見**） |
| 把**新的**當成既有（指向某個 ordinal） | **不建 issue → 靜默遺失** | 不可能發生——application 不看分類，一律落地 |

該意見只考慮了第一列。第二列才是本文 §5.5 與 ADR 0044／0052 一路要擋的形狀：
**一個新缺口在沒有人回答、也沒有人問過的情況下消失，而且沒有任何跡象。**

兩個方案都在賭模型：H 賭它讀了記憶區就不重複，該方案賭它分類正確。
**差別在賭輸時的樣子**——H 賭輸只會多一筆重複（員工被多問一次，顧問可以用同一個答案一次收掉
兩筆，決定 22 明文支持），該方案賭輸會讓職務說明書永久少一項。

依 0044「不得靜默刪除」、0052「缺漏必須在成品上看得見」，**選 H**。

而且 H 的賭注 0054 已經下過一次：決定 20 讓已終結的缺口進 specialist packet，用意就是
「不要再開同一個缺口」，靠的正是同一種 prompt 遵從。H 只是把同一個機制多蓋一區，
不是新賭注。**該方案要新增 wire 欄位才能換到的東西，是把「重複」的風險換成「遺失」的風險。**

### 8.7 該方案仍是有價值的升級路徑

契約成本其實不高：`opks_result_v1` 目前 495 compact bytes、4 個 item property、
**0 個 anyOf／oneOf／$defs**。加一個純量 `known_gap_ordinal`（0 ＝ 新缺口）就夠，
不需要 discriminated union，離 2026-07-31 撞過的 grammar size 問題很遠。

**所以它不是不可行，是現在沒有做的理由**：沒有任何測量顯示 H 的重複率高到值得用「遺失風險」
去換。要做它的判準是**實測重複率**，寫進 ADR 決定 8。

### 8.8 該意見的測試清單

大致可用，兩點要調整：

- 「建立 gap 不會自我觸發」——§8.4，型別上已不可能，測試仍值得留一筆當回歸網。
- 「replay packet 不漂移」——§8.5，與 0054 刻意決定相反，**不要加這條測試**；
  該加的是反向的：**缺口記憶改變不得造成 abandon**。

它另外建議的「測 `subject_task_id` 是否只屬於 OPKS gap」值得採納：`_issue_blocks()` 與
verifier 的 `RESOLUTION_OPKS_GAP_NEEDS_ISSUE_RESOLUTION` 都拿 `subject_task_id` 當缺口的判別式
（domain 只保證 `opks_axis` 非空必有它，反向沒有保證，目前靠「全 repo 只有 `_gap_issues()` 會寫它」）。
釘一筆 AST 或單元測試，日後有人給別種 issue 寫 `subject_task_id` 時會紅。

## 9. 裁決結果（2026-08-06）

owner 裁決**暫不採用**，ADR 0055 標為 Rejected。理由見 §1 末段與 §6.1 的修正：
缺口會被問、會被關，功能沒有缺席，殘餘風險是尾端衰減而非全面失效，目前不足以支付
「每次新依據多一次呼叫 ＋ 重複缺口風險 ＋ K/S 碎片化」的成本。

**重啟的唯一條件是缺口關閉率的實測**：一次 10–15 回合、2–3 件工作的 live smoke，量
「每回合關掉幾個缺口」與「每次分析開幾個缺口」。消得比開得慢就重議，反之此案永久關閉。
本文其餘分析（診斷、內部先例、選項比對、量法定義）保留，供該實測後直接引用。

以下原「建議的下一步」保留為當初主張的紀錄。

## 10. 原建議的下一步（未採用）

1. 開一份 **Proposed ADR**：拿掉 pre-gate 的「無 active OPKS gap」（§3、§6），
   採 G 處理舊缺口（§6.1），並在 ADR 裡裁決 §6.3 的 receipt outcome 寫法。
2. ADR 必須明寫**不做**的事：不做取代、不做文字配對、不給 specialist 刪缺口的權力、
   不加 backoff／節流／新狀態。
3. 實作後補一次 live smoke（同一個凍結場景），**觀察第二次 specialist 呼叫是否真的發生、
   以及員工的回答有沒有變成候選**——那正是這次 run 沒能觀測到的那一段。
