# Job Analysis attributed live smoke：執行結果

日期：2026-07-31
狀態：**三回合場景已跑完（run 5 Opus 5、run 6 Luna-Pro、run 7 Sonnet 5，皆 `committed`×3）。**
八次 run 累計 US$0.613，找出**七個**契約層缺陷（grammar 過大／ordinal 基準不一致／
6 條規則模型無從得知／一般 open issue 無關閉路徑／新 issue 拿不到 `last_asked_turn_id`／
schema 名稱帶點／`$ref` 帶兄弟 keyword），全部已修；後兩個是換 provider 才浮現的**可攜性**
缺陷，契約原本鎖死 Anthropic。**merge／split／withdraw、supersession 與 Proposal 決策
仍未被任何 run 觀測到。**
計畫：[2026-07-31 attributed live smoke plan](../../plans/2026-07-31-job-analysis-attributed-live-smoke-plan.md)
研究：[OpenRouter 歸因與最小 live smoke](../../specs/2026-07-31-job-analysis-openrouter-attribution-and-live-smoke-research.md)

## 0. Run 2（2026-07-31 12:09 UTC）：wire 契約修正後，turn 1 通過

`compiled grammar is too large` 已解除。以下三節（§1–§5）保留 run 1 的原始紀錄，**不修改**。

| 項目 | 值 |
|---|---|
| commit | `97bca87`（`dirty: false`） |
| 指令 | `uv run python scripts/job_analysis_live_smoke.py --max-generation-calls 1 --budget-usd 0.20` |
| run id | `20260731T120931Z` |
| generation calls | **1**（本次授權上限 1） |
| retry | **0** |
| 實際支出 | **US$0.058195**（prompt 5,399 tok = US$0.026995；completion 1,248 tok 含 155 reasoning = US$0.0312） |
| HTTP | 200 |
| response id | `gen-1785499775-Vn5OY2FTlvgOKuKPDxwn` |
| schema | `task_analysis_result.v2`，`strict: true`，`sha256:0cbc27a5fc430357…`，**4,084 bytes** |
| prompt hash | `sha256:a7866627139d8107…`（5,090 bytes） |
| turn outcome | **committed**（verifier 通過、transition 套用、authority_generation 1） |
| 建立的文件 | `33a963c1-5d4a-4507-ba65-9b3c38f71ea2`（留在本機 dev DB） |
| raw capture | `output/job-analysis-live-smoke/20260731T120931Z/`（gitignored） |

`stopped_reason` 是 `turn 2 was not sent: already used 1 of 1 generation calls` —— 這是**預期的**，
本次授權只買一次呼叫來驗證 grammar，不是失敗。

### Route 歸因

`strategy: direct`、`attempt: 1`、`provider: Anthropic`、pipeline 空、`region: TPE`、
`endpoints.total: 7` 且 `available` 恰好一個 `selected: true`。

`quality_eligible = false`，**唯一一項 limitation**：

> `selected model did not match the preflight catalog endpoint`

catalog 報 `anthropic/claude-opus-5`，router 實際選 `anthropic/claude-opus-5-20260723`
（alias 背後的日期快照）。這是**已知的 fail-open 降級，不是路由問題**——路由本身完全乾淨。
判準刻意用精確比對，**本檔不放寬它**；要不要讓判準接受「alias → 其日期快照」是獨立決策。

### 這一輪模型實際產出了什麼

**這不是品質 gate**（單次、合成場景、無 rubric），只記錄觀測到的事實：

- 2 個 Task：`每週彙整服務錯誤與效能資料並產出營運週報…`（enablers: Python、Excel）、
  `維護門市資料匯入程式，確保每日門市資料準時進入系統`（enabler: Java）。
- 1 個 open issue（`責任邊界不明`）：員工說「版本上線時，我會協助正式環境部署」，
  模型判定無法分辨是本人責任的獨立工作或他人工作的支援步驟，逐字引用該句並追問。
- 0 個 exclude。next_question 指向該 open issue，問題具體到可以接短答。
- Enabler 硬規則有作用：Python／Excel／Java 都進了 `enablers`，沒有任何一個被升格成 Task。

### 仍未被本次觀測到的

三回合場景只跑了第一回合，因此**跨回合記憶、更正／撤回、merge／split、Proposal 決策**
都還沒有真模型的觀測。要驗證這些需要另外的授權。

---

## 0b. Run 3（2026-07-31 12:16 UTC）：turn 1 被 verifier 擋下，找出契約缺陷

| 項目 | 值 |
|---|---|
| commit | `7069679`（`dirty: false`） |
| 指令 | `--max-generation-calls 3 --budget-usd 0.50` |
| run id | `20260731T121651Z` |
| generation calls | **1**（上限 3；turn 2／3 未送出） |
| retry | **0** |
| 實際支出 | **US$0.064145** |
| HTTP | 200（provider 正常） |
| turn outcome | **failed** —— `UncommittableOperationResult: cannot commit operation outcome 'rejected'` |

**根因是我們的契約缺陷，不是模型。** 模型輸出語意正確（2 個 Task ＋ 1 個
`責任邊界不明` open issue，工具全部落在 enablers），被擋下的是 `next_question`。

v1 有兩個分開的欄位：`ordinal`（packet 的 **1-based** ordinal）與 `index`
（本次輸出的 **0-based** 位置）。v2 把它們併成單一的 `target_ordinal`，
而這份契約裡其他每一個叫 ordinal 的東西都是 1-based。名字指向 1-based、
description 卻要求 0-based。

真模型在**兩次相同場景**下對**同一個**（第三個）訊號送出不同的值：

| run | `target_ordinal` | 基準 | 結果 |
|---|---:|---|---|
| `20260731T120931Z` | 2 | 0-based | 落在範圍內 → 通過（**僥倖**） |
| `20260731T121651Z` | 3 | 1-based | 超出 0..2 → `NEXT_QUESTION_TARGET_INVALID` |

也就是說 §0 的通過是運氣，這個缺陷在真實使用中約每兩回合就會發作一次。

**修法**（commit 見下方執行紀錄）：wire 一律 1-based，0-based 的
`NextQuestionTarget.index` 由 mapper 換算，不外洩給模型；`target_ordinal < 1`
直接拒絕。規則放進介面的一致性，而不是靠 description 講例外。
被擋下的那份輸出以修好後的 mapper 重放，`index = 2`，落在 0..2 內。

**turn 2／3 仍未以真模型跑過。**

---

## 0c. Run 4（2026-07-31 12:33 UTC）：turn 1 通過，turn 2 停線

| 項目 | 值 |
|---|---|
| commit | `3e46836` |
| run id | `20260731T123344Z` |
| generation calls | **2**（上限 3；turn 3 未送出） |
| 實際支出 | **US$0.128910** |
| turn outcomes | `committed`, `failed` |

turn 1 的 1-based 修正有效，穩定通過。turn 2（員工更正「正式環境部署不是我負責」）被
`RESOLUTION_OPEN_ISSUE_NOT_RECONCILABLE` 擋下。

**模型的判斷是對的，契約不允許。** 它把 turn 1 自己提的 `責任邊界不明` open issue 標成
已解決（`resolves_open_issue_ordinal: 1`）＋ `exclude / 他人工作`。但依 ADR 0044，
`resolves_open_issue_ordinal` **只服務 JD-only reconciliation issue**；packet 用
「`Current JD Task:`」那一行區分兩者，先前**沒有任何地方說明那條線的意義**。

已補：該欄位的 description 明說只能指帶那一行的 issue，其餘 issue 不會因為回答而關閉。

### 未決的設計缺口（需 ADR）

**模型自己提的 open issue 沒有任何關閉路徑。** `transition.py` 只在 reconciliation 路徑
`remove(issue)`；`next_question` 指向它只更新 `last_asked_turn_id`。多輪訪談下 open issue
單調累積，而 Static Instructions 要求優先處理「仍可取得答案的 open issue」——有重問迴圈的風險。
本次觀測到的情境正是如此：員工已經回答了那個 issue，它仍會留在 Current State。

---

## 0d. 離線重放（2026-07-31，US$0，0 generation call）

ADR 0047 修好之後，**不再付費去問同一個問題**：run 4 的 turn-2 原始輸出還在
`output/…/20260731T123344Z/turn-02.json`，文件 `4f783a47-fc8d-4bc0-bba4-c2c3a529ef02`
也還在本機 dev DB（turn 1 已 commit、turn 2 rollback）。用 `prepare_turn()` 讀回真 packet，
再把那份輸出送過**現在的** mapper／verifier／transition。純函式，沒有寫入。

| 檢查點 | 結果 |
|---|---|
| verifier | `is_valid = True`（原本 `RESOLUTION_OPEN_ISSUE_NOT_RECONCILABLE`） |
| transition | `applied` |
| turn 1 的 `責任邊界不明` issue | 已關閉，從 `open_issues` 消失 |
| 該訊號自身的 exclude | 仍落地（`excluded_signals = 1 / 他人工作`）——ADR 0047「關閉後不 return」在真資料上驗證 |
| open issue 總數 | 1 → 1（新的 `證據不足` 頂上，未單調累積） |
| `next_question` | `target_ordinal 2` → `index 1`，落在 0..1 內 |
| anchors | 全為 `turn_ordinal 4`，等於 `current_turn_ordinal`，新護欄不誤擋 |

**重放不是新抽樣。** 它只證明契約接得住那一份既有輸出；模型下次會產生什麼、
merge／split／Proposal 決策長什麼樣，都不在本節的證據範圍內。

### 重放找出的第五個缺陷：新 open issue 永遠是「尚未問過」

把 turn-2 結果往前推一步、算出 turn 3 的 packet 之後，open issue 那段渲染成：

```text
[1] 證據不足: 員工提到上線前的測試與檢查由本人執行，但未說明…
    依據: [4] 「我只做上線前的測試與檢查」 回應提問 [3]
    最近提問: (尚未問過)
```

但 `active_question`（同一份 packet 的上一節）問的就是它。

`record_next_question()` 只認 `existing_open_issue`；當顧問**同一輪提出 issue 又追問它**
（`next_question.target = new_signal`），新建的 issue 拿不到 `last_asked_turn_id`。
`context.py` 的註解正好寫著這條路不能斷：「缺了 last_asked，它會把剛問過的缺口當成沒問過再問一次」。

真模型到目前為止產生的**每一則** open issue 都命中這個缺口——turn 1 的
`live-smoke-turn-01-i2` 在 `state_before` 裡也是 `last_asked_turn_id: null`，而 [3] 問的就是它。
命中率 100%，且正是 ADR 0047 想避免的重問迴圈。

已修：`new_signal` target 也記，issue id 用 `{operation_id}-i{index}` 對上；該訊號沒產生
issue（例如追問剛新增的 Task）就沒得記，不是錯誤。修好後同一份重放渲染出 `最近提問: [5]`。

---

## 0e. Run 5（2026-07-31 17:04 UTC）：三回合首次跑完

| 項目 | 值 |
|---|---|
| commit | `a70e5c0`（`dirty: false`） |
| 指令 | `--max-generation-calls 3 --budget-usd 0.50` |
| run id | `20260731T170405Z` |
| generation calls | **3** |
| retry | **0** |
| 實際支出 | **US$0.210285**（turn 1 $0.0683／turn 2 $0.07984／turn 3 $0.062145） |
| turn outcomes | `committed`, `committed`, `committed`；`stopped_reason: null` |
| 建立的文件 | `1b9c390b-0fe8-4b74-b116-6efbadc2a98b`（留在本機 dev DB） |
| 最終狀態 | 4 Task、0 open issue、1 excluded signal、4 筆 pending `add` Proposal、7 conversation turns、`authority_generation: 3` |

Route 三回合都是 `direct`／`attempt: 1`／pipeline 空／provider Anthropic。
`quality_eligible = 0/3`，limitation 每回合都只有同一條：`selected model did not match the
preflight catalog endpoint`（catalog 報 `anthropic/claude-opus-5`，router 選
`anthropic/claude-opus-5-20260723`）。這是刻意保留的嚴格判準，見 §0。

### 首次觀測到的行為

- **跨回合記憶。** turn 3 員工岔題（改講權限稽核、沒回答上一題），模型仍新增該工作，
  並把 next question 明寫成「**回到上線前的測試與檢查**」，接回 turn 2 未答的線。
- **更正處理。** turn 2 把「正式環境部署」判為 `exclude / 他人工作`（它從未成為 Task，
  只是 open issue），**同一個訊號**關掉 turn 1 的 `責任邊界不明` issue，另外新增員工真正
  在做的「上線前的測試與檢查」。
- **ADR 0047 在真流量上成立。** 關閉與該訊號自身的 exclude 兩個效果都落地；
  最終 `open_issues = 0`、`excluded_signals = 1`。
- **`last_asked_turn_id` 修正在真流量上成立。** turn 1 的 next question 指向
  `new_signal #3`（即那個 open_issue 訊號），issue 拿到
  `last_asked_turn_id = live-smoke-turn-01-consultant`。同一位置在 run 4 是 `null`。
- **Enabler 硬規則三回合都守住。** Python／Excel／Java 全在 `enablers`，沒有一個被升格成 Task；
  「交給資訊安全窗口」寫在 Task statement 裡當交接，沒有變成另一筆 Task；
  沒有工具的兩筆 Task 也沒有被硬塞 enabler。

### Context 成長（給 context 預算用的實測）

| turn | request bytes | prompt tokens | completion tokens |
|---:|---:|---:|---:|
| 1 | 11,850 | 6,360 | 1,460（reasoning 129） |
| 2 | 13,989 | 7,193 | 1,755 |
| 3 | 14,698 | 7,474 | 991 |

每回合約 +550 prompt tokens。固定成本（instructions 5,090 ＋ schema 4,818 bytes）不隨對話成長，
成長的是 packet；四筆 Task ＋ 四筆 Proposal 之後 packet 已是請求的主要變動項。

### 本次**沒有**觀測到的（不得由本節推得）

- **過早關閉 open issue 的風險沒有被測到。** turn 2 結束時 open issue 已歸零，
  turn 3 根本沒有東西可以誤關（`resolves = 0` 是因為沒得關，不是因為模型克制）。
- merge／split／revise／withdraw 一筆真正的 Task、supersession：一次都沒發生。
- Proposal 決策：建立了 4 筆 pending，driver 不做決策，員工端路徑仍未經真模型驗證。
- JD-only reconciliation issue：本文件從空白開始，沒有 Current JD。
- 單次 trial 不能宣稱穩定性或品質；本節只記錄觀測到的事實，沒有 rubric。

### 一個小的表達力缺口（記錄，不修）

turn 3 的 `next_question.target_kind = none`：問題要回指的是**前一輪新增的 Task**，
而 target 詞彙只有 `existing_open_issue` 與 `new_signal`，表達不了。模型選了中性值，
是誠實的做法。真的造成追問失焦時再處理，現在不加欄位。

---

## 0f. Run 6–7（2026-07-31 20:19／20:26 UTC）：Luna-Pro 與 Sonnet 5 的 A/B

同一個凍結場景、同一份 prompt、同一份 schema，只換 `job_analysis_model` 與
`job_analysis_provider`（env var，不改 repo）。Opus 5 的 run 5 當 baseline。

### 換 provider 先撞出兩個契約缺陷（都 US$0，生成前被拒）

| # | 錯誤 | 根因 | 修正 |
|---|---|---|---|
| 1 | `Invalid 'text.format.name': …pattern '^[a-zA-Z0-9_-]+$'` | schema 名字裡的**點**（`task_analysis_result.v2`）；Anthropic 收，OpenAI 不收 | 改名 `task_analysis_result_v2`＋測試守住（`5f3a2a5`）|
| 2 | `$ref cannot have keywords {'description'}` | Pydantic 把 enum 欄位輸出成 `{"$ref":…,"description":…}`；**那些 description 就是給模型的規則本體**，不能拿掉 | 可攜投影裡把 `$ref` 全部內聯（`12ddee1`）|

第二項量過才做：14 個 `$def` **每個只被引用一次**，間接層零重用效益，展開後 schema
從 4,970 縮到 4,218 bytes，離當初炸掉的 6,818 更遠。**兩家都賺，不是拿 Anthropic 換 OpenAI。**
這兩個修正與最後選哪個模型無關——契約本來在兩處鎖死單一 vendor，現在不鎖了。

### 成本：兩個「便宜」都被侵蝕，倍率與目錄單價差很多

| 模型 | 目錄單價 vs Opus | **實測三回合** | **實際比例** |
|---|---:|---:|---:|
| `anthropic/claude-opus-5` | 100% | US$0.210285 | 100% |
| `anthropic/claude-sonnet-5` | 40%（導入價） | US$0.111156 | **53%** |
| `openai/gpt-5.6-luna-pro` | 2% | US$0.020856 | **10%** |

侵蝕原因不同：

- **Luna-Pro**：GPT tokenizer 吃繁中效率差，同一份 packet **20,039 vs 6,360 tokens（3.1x）**；
  `mode=pro` 的 reasoning **7,722 vs 129（60x）**、completion 9,437 vs 1,460。
- **Sonnet 5**：prompt token 與 Opus 相當（略少），但輸出較長（completion 2,788／3,328／1,133
  vs Opus 1,460／1,755／991）。
- Sonnet 5 現在是導入價 $2/$10、**2026-08-31 到期**；以牌價 $3/$15 重算同一次 run 是
  US$0.1667 = **79% of Opus**——屆時只省兩成。

### 判斷品質：一個測試點乾淨地分開了它們

turn 1 員工說「版本上線時，我會**協助**正式環境部署」：

| 模型 | 判斷 |
|---|---|
| Opus 5（run 4 **與** run 5，2/2） | 不成立 Task，開 `責任邊界不明` open issue，追問哪一段真的是他做的 |
| Sonnet 5 | **同上**（`責任邊界不明`，relation 用 `uncertain`）|
| Luna-Pro | **直接建 Task**：「協助執行正式環境部署，支援版本上線」，`purpose_result` 只是把句子重講一遍 |

turn 2 的員工更正救了 Luna-Pro——但**那是場景剛好有更正**。真實訪談裡員工若沒更正，
JD 會寫著他負責正式環境部署，而那是假的。open issue 機制存在的理由就是擋這個。
Luna-Pro 的補救也不乾淨：`revise` 後的 Task 仍帶著錯誤原版的 `purpose_result`
「支援版本上線」（Opus 寫的是「以確認版本具備上線條件」）；它的 `exclude` 還帶了
`relation=overlap, targets=[3]`，而 exclude 不需要指向任何 Task。
**Luna-Pro 三回合一則 open issue 都沒開過。**

Sonnet 5 比 run 5 的 Opus 更保守：turn 2 把「上線前測試與檢查」留成 `證據不足` open issue
而非成立 Task（＝run 4 的 Opus 判法），turn 3 並以 `existing_open_issue` 精確指回它。
最終 3 Task ＋ 1 open issue（Opus run 5 是 4 Task ＋ 0）。兩種判法都在 Opus 自己身上出現過，
沒有 rubric 就不能說誰對——但「該不該從『協助』二字生出一條 Task」不是這種擺盪，
那條線 Luna-Pro 是踩過去了。

### 每份 JD 的推估（用實測的每回合 +550 prompt tokens 外推 30 回合）

| 模型 | 每份 JD |
|---|---:|
| Opus 5 | ~US$3.2 |
| Sonnet 5（導入價／牌價） | ~US$1.6／~US$2.4 |
| Luna-Pro | ~US$0.3 |

這才是產品該看的數字；三回合 smoke 的成本是研發開銷，不是單位經濟。

### 不得由本節推得

單一 trial ×3，沒有 rubric，沒有重複抽樣。本節能支持的只有兩件事：兩個契約可攜性缺陷
是真的且已修；以及「從『協助』生出一條 Task」這個具體失誤，Luna-Pro 犯了、兩個 Claude 模型
沒犯。其餘差異都在單次抽樣的雜訊範圍內。

---

## 0g. Run 8（2026-07-31 20:59 UTC）：把判準搬到 `disposition` 之後，再測 Luna-Pro

commit `4b75190`（`disposition` 補 195 bytes 判準；prompt 五段判準一字未改）。
同場景、同模型、US$0.019079，`committed`×3。與 run 6 逐回合比：

| | run 6（搬之前） | run 8（搬之後） |
|---|---|---|
| turn 1「協助正式環境部署」 | 建成 Task | **仍建成 Task** ✗ |
| turn 2 收拾方式 | `revise` ＋ `exclude`（revise 後仍帶錯誤原版的 purpose） | **`withdraw` ＋ `employee_denied`**——語意正確的那個操作，Proposal 轉 `stale` |
| turn 2「上線前測試與檢查」 | 直接建 Task | **留成 `證據不足` open issue** ✓（＝Sonnet 5 與 Opus run 4 的判法）|
| turn 3 追問 | `target_kind: none` | **`existing_open_issue #1`**——精確指回未答的缺口 |
| 最終 | 4 Task／0 issue | 3 活 Task ＋ 1 retired／1 issue |

**結論：位置修正在次要判斷上有效，在最要緊的那一個上無效。**
把規則放到模型正在填的那個參數上之後，Luna-Pro 仍然從「我會**協助**部署」生出一條 Task。
規則在 prompt 三處明文、在 `open_issue` 的類別名稱上、現在還在決策點的 description 上——
它還是走過去了。這支持「**能力問題，不是指令問題**」的判讀。

再往下只剩對單一模型的失誤寫專門文字（例如列舉「協助／幫忙／支援」這類詞），
那是 over-fit 到一個不打算上生產的模型，而且會讓強模型多付推理成本。**到此為止。**

單一 trial：run 6 與 run 8 的其他差異也可能是抽樣雜訊，本節不宣稱它們由該修正造成；
能說的是全部差異都朝期望方向，沒有一項反向。

**未驗證的風險（本次造成）**：`4b75190` 改的是所有模型看到的東西，
但只在 Luna-Pro 上觀測過。Sonnet 5／Opus 5 是否因此變差**沒有量過**。

---

## 1. 結論（run 1，2026-07-31 08:35 UTC）

三回合場景**沒有跑完**。第一回合的請求被 Anthropic 以 HTTP 400 拒絕，原因不是模型輸出不好，
而是**本產品的 strict output schema 編譯出的 grammar 過大**：

```text
{"type":"error","error":{"type":"invalid_request_error",
 "message":"The compiled grammar is too large, which would cause performance issues.
            Simplify your tool schemas or reduce the number of strict tools."},
 "request_id":"req_011CdZq1Xf7ubQGu1zGfADnz"}
```

請求在生成任何 token 之前就被拒絕，因此 **US$0**、沒有 transcript。

**產品層含意（強推論，非直接觀測）**：production 的 `get_job_analysis_adapter()` 與這次 smoke 走
同一個 `OpenRouterAdapter.build_body()`、同一份 `task_analysis_result_provider_schema()`
（schema `sha256:a233699…`）、同一組 provider 設定；兩者的 `response_format` 區塊逐位元組相同，
差別只有 smoke 多加的兩個診斷 header。因此**在這個 route 上，員工的每一個 AI 回合現在都會撞到同一個 400**。
本檔沒有另外對 production route 送請求來直接證明這一點。

**不得由本檔推得的結論**：模型品質、prompt 好壞、Task 邊界、工具處理、更正處理、跨回合記憶
——這些一項都沒有被觀測到。

## 2. 執行紀錄

| 項目 | 值 |
|---|---|
| commit | `9966255`（`dirty: false`） |
| 指令 | `uv run python scripts/job_analysis_live_smoke.py --budget-usd 0.75 --max-generation-calls 3` |
| run id | `20260731T083501Z` |
| generation calls | 1（上限 3） |
| 實際支出 | **US$0**（回應沒有 usage／cost；請求被拒，未生成 token） |
| 該次 reserve | US$0.174855（14,491 request bytes × 0.000005 + 4,096 × 0.000025） |
| retry | 0（停線後未重送，未改 prompt） |
| PostgreSQL migration | `0013 (head)` |
| 建立的文件 | `a6c7e248-efb1-42ab-be65-ff3aa68dc235`（title 含 `[synthetic live smoke]`，留在本機 dev DB） |
| 最終 state | 0 個 Task、1 個 conversation turn（只有開場白）；**沒有任何半套資料落地** |
| raw capture | `output/job-analysis-live-smoke/20260731T083501Z/`（gitignored；manifest / catalog / turn-01 / summary） |

先前 2026-07-31 稍早的一次 dry preflight 曾因 `anthropic` endpoint `status = -2` 停線
（0 call、US$0）；本次執行前重查已回到 `status = 0`，價格與能力不變，才進入付費步驟。

## 3. 請求事實

| 項目 | 值 |
|---|---|
| model | `anthropic/claude-opus-5`（provider `anthropic`、`allow_fallbacks: false`、`require_parameters: true`） |
| max output tokens | 4096；`reasoning.effort = high` |
| prompt hash | `sha256:43a03d3b18eaad99…` |
| schema hash | `sha256:a2336995ac69a737…`，`strict: true`，name `task_analysis_result.v1` |
| **schema 大小** | **6,818 bytes** |
| 整包 request | 14,491 bytes |
| 動態 packet | 551 字元 |
| 固定 instructions | 3,093 字元 |

Context 一點都不大（551 字元）。過大的是**輸出契約本身**，與對話長度無關——這代表它不會隨著
訪談變短而自行好轉。

## 4. Route 歸因

| 欄位 | 值 |
|---|---|
| strategy | `direct` |
| attempt | 1 |
| requested | `anthropic/claude-opus-5` |
| endpoints | `total: 7`，`available: [{provider: "Anthropic", model: "anthropic/claude-opus-5-20260723", selected: false}]` |
| region | `TPE` |
| pipeline | 空 |
| usage／cost | 無 |

`quality_eligible = false`，limitations 三項：cost 無法核算、response model 不符、沒有恰好一個
selected endpoint。這是**正確的 fail-closed**：請求被拒時本來就不該有可用的品質歸因。
路由本身沒有問題——它直達 Anthropic、第一次嘗試、沒有 fallback、沒有 pipeline 介入。
`available[0].model` 顯示 alias 背後的實際快照是 `anthropic/claude-opus-5-20260723`。

## 5. 失敗分類

依計畫 §Step 4 的順序，第一個適用類別是 **1 `provider_or_attribution`**：provider 回錯、
沒有 cost、沒有 selected endpoint，因此該 trial 無歸因資格。

但**可行動的根因在 schema 層**：Anthropic 拒絕的是 `response_format.json_schema` 的
`strict: true` 編譯結果，不是輸出內容。它不屬於類別 3 所指的「輸出 invalid／verifier rejected」
（那需要先有輸出），也完全不是類別 4 的 prompt／rubric 問題。

依計畫與 owner 指示，**本輪不修、不調 prompt、不重跑**。

## 6. 最小後續工作（run 1 當時的規劃；1 與 2 已於 run 2 完成，見 §0）

1. **確認限制的形狀。** 是 Anthropic 近期收緊 grammar 編譯上限，還是本 schema 一直就超過？
   查官方 structured output 限制，並量出目前 schema 觸發上限的是哪幾段（巢狀 union、
   `TaskChangePayload` 的多形載荷、多個 enum）。
2. **決定契約要往哪邊讓。** 兩條互斥方向：縮小 strict schema 的 grammar 體積，或改送
   非 strict 的 portable schema、把責任完全交給既有的 deterministic local verifier。
   後者會動到 ADR 0040 決定 26（portable structured output ＋ `strict: true`），
   **必須另開研究與 ADR，不能當成 bug fix 直接改**。
3. **修好後重跑同一支 CLI。** 本次的 budget、recording transport、三回合 driver 與 capture
   格式都沒有被否定，可原樣重用；場景不改，仍是 3 calls／US$0.75／零 retry。

## 7. 已知限制

- 本次沒有任何模型輸出，因此計畫 §Step 3 的八項語意判準（tools、work boundaries、correction、
  cross-turn memory、grounding、consultant question、durability、route）**只有 route 一項有結果**。
- 單次 trial 不能宣稱穩定性；本檔也不比較模型或 effort 設定。
- route 證據只說明 OpenRouter 回報了什麼，不是 Anthropic 的獨立簽章。
- 這不是瀏覽器 E2E：UI 點擊、CORS 與前端錯誤顯示都未驗證。
