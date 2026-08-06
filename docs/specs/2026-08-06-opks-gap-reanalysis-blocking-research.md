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

模型越誠實（缺口開得越細），再分析被鎖得越久。真實訪談中員工隨時可能結束，
**這條線很可能一次都跑不到第二次分析**。

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

## 5. 選項比對

前提：**任何選項都不動 (a)**。相同 `analysis_input_digest` 只付一次錢是 0054 決定 31 的付費邊界，
不翻案。

| | A：拿掉 (b)，由 digest receipt 單獨守門 | C：`answered` 才解鎖一次 | D：限制 specialist 一次開幾個缺口 | E：不改 |
|---|---|---|---|---|
| 何時再分析 | digest 一變就分析 | 只有主顧問送出 `answered` 且 digest 變了才分析 | 同現況 | 同現況 |
| Opus 場景（4 缺口） | turn 3 就重新分析 | turn 3 就重新分析 | 缺口變少，但仍要全關 | **永遠不會** |
| 每個 Task 的呼叫上限 | 每個輸入狀態 1 次（0054 既有上限） | 每次 `answered` 1 次 | 同現況 | 同現況 |
| 無關編輯造成的重跑 | **會**（每次 1 呼叫） | 不會 | 不會 | 不會 |
| 缺口累積問題 | **必須一起解**（§3 末） | **必須一起解** | 不出現 | 不出現 |
| 與 owner 既有裁決的相容性 | 相容 | 相容 | **牴觸**：owner 已裁定同一軸可以有數個不同缺口（`0b261fc`），Opus 實測也確實開了兩個獨立知識缺口 | 相容 |
| 新機制 | 無（少一條規則） | 有（新的解鎖條件） | 有（新的產出限制） | 無 |

**D 應被否決**，理由不只成本：owner 在 2026-08-05 用「不知道交出什麼文件」與「不知道要達到
什麼狀態」是兩件事，否決了 `DUPLICATE_GAP_AXIS` verifier 規則；Opus 這次開的兩個知識缺口
（涵蓋範圍與定義／資料來源）正是那個反例的實例。限制缺口數＝獎勵模型少講實話，與北極星相反。

**E（不改）的真實代價**：漸進式蒐集的「漸進」在生產模型下不會發生。0054 的價值主張是
「員工回答 → 自動重新分析」，實測顯示第二段不會執行。這不是保守，是功能缺席。

## 6. 傾向與尚未解決的細節

**傾向 A**，理由是它**少一條規則**而不是多一條：付費邊界本來就由 digest receipt 定義
（每個輸入狀態一次呼叫），(b) 是疊在上面的第二層節流。沒有缺口的 Task 早就照 (a) 的規矩走；
**有缺口的 Task 反而被更嚴格地節流，方向是反的——那正是最需要再分析的 Task。**

A 相對 C 的代價是「無關編輯也會重跑一次」。但那個代價已經是全系統的既定成本模型（0054 決定 31），
不是這裡新引入的；為它特別加一條例外，就是 Anthropic 那句「只在能證明改善時才加複雜度」要擋的東西。

**採 A 必須同時解決的兩件事，本文不裁決，留給 ADR：**

1. **缺口累積**（§3 末）。傾向：一個 Task 的 active 缺口集合＝**最近一次分析的 uncertain 集合**，
   新分析提交時取代舊的。理由是 specialist 的最新判斷才是「現在還缺什麼」的權威；舊缺口是對
   舊輸入說的話。terminal 缺口不動（它們是「已問過、勿重問」的記憶，決定 20）。
2. **`last_asked_turn_id` 會跟著舊缺口一起消失**。取代後新缺口是新 ID，packet 會顯示「尚未問過」，
   主顧問可能把已經問過的缺口再問一次——這正是 ADR 0047 脈絡段記載的那種傷害。
   需要決定：按 (subject_task_id, axis) 承接？兩個同軸缺口時怎麼配對？或接受重問一次？

第 2 點沒有明顯正確答案，是開 ADR 前要先想清楚的地方。

## 7. 仍缺的資料

- 真實訪談中一個 Task 平均會開幾個缺口（目前 n=2 次 synthetic run，Opus 開 4 個）。
- 員工回答一個缺口時，順帶答到其他缺口的比例（Opus 這次是 1/4 精準命中，沒有溢出）。
- 放寬後每份職務說明書實際多花多少錢（Opus 一次 specialist 呼叫本次量到 US$0.024）。
