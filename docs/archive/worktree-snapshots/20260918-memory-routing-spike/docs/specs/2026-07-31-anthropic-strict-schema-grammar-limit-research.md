# Anthropic strict schema「compiled grammar is too large」：限制查證與修法分析

日期：2026-07-31
狀態：研究完成，待 owner 裁決；**尚未改任何程式**
前置事實：[live smoke 實驗紀錄](../experiments/2026-07-31-job-analysis-attributed-live-smoke/README.md)

## 1. 問題

2026-07-31 的 live smoke turn 1 被 Anthropic 以 HTTP 400 拒絕：

```text
invalid_request_error: "The compiled grammar is too large, which would cause
performance issues. Simplify your tool schemas or reduce the number of strict tools."
```

拒的是 `response_format.json_schema`（`strict: true`）編譯出的 grammar，不是模型輸出。
產品走同一份 schema，**同 route 下員工的每一個 AI 回合現在都會撞到同一個 400**。

一個容易誤導的細節：錯誤訊息說「tool schemas」「strict tools」，但我們沒有送任何 tool。
官方 strict tool use 頁說明了原因——**兩者共用同一條編譯管線**：

> "Strict tool use compiles tool `input_schema` definitions into grammars using the same
> pipeline as [structured outputs]. Tool schemas are temporarily cached for up to 24 hours
> since last use."

所以這是共用編譯器吐出的共用錯誤字串，不是我們送錯欄位。

## 2. 官方資料（2026-07-31 查核）

| 來源 | 相關內容 |
|---|---|
| [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | **明列複雜度上限：optional 24、union parameters 16。** 支援子集：`anyOf`、`allOf`（但 `allOf` 搭 `$ref` 不支援）、`$ref`/`$def`/`definitions`（外部 `$ref` 不支援）、`enum`、`const`、`default`、`required`、`additionalProperties: false`、字串 format、陣列 `minItems`（只支援 0／1）。不支援遞迴 schema、數值／字串約束。grammar 編譯有首次延遲，編譯結果快取 24 小時 |
| [Anthropic Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use) | 與 structured outputs 共用 grammar 編譯管線與 24 小時 schema 快取；PHI 不得放進 schema |
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 「up to 5000 object properties total, with up to 10 levels of nesting」、「Total string length of all property names, definition names, enum values, and const values cannot exceed 120,000 characters」、「up to 1000 enum values」。strict 要求**所有欄位 required**，optional 以 `["string","null"]` union 模擬 |
| [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) | 「Support is determined per endpoint, not just per model」；「Enforcement varies by provider: some guarantee schema-conforming output, while others translate your schema into their own structured-output format or treat it as a strong hint」 |

兩家的取捨方向正好相反：OpenAI 要求 strict 全欄位 required、**鼓勵**用 null union 模擬 optional，
上限寬鬆（5000 property／10 層）；Anthropic 則對 **union 本身**設了很緊的上限（16）。
把 OpenAI 慣例照抄到 Anthropic，等於把成本堆到對方最敏感的那個維度上——這就是本次 400 的由來。
「JSON Schema 語法可攜」確實不等於「grammar 複雜度可攜」。

## 3. 本產品 schema 實測

`task_analysis_result.v1`（`llm/portable_schema.py` 產生，schema hash `sha256:a233699…`）：

| 指標 | 送出形式（含 `$ref`） | **`$ref` 展開後** | 官方上限 |
|---|---|---|---|
| **nullable union（`anyOf: [X, null]`）** | 13 | **17** | **16** ← 超出 |
| optional 欄位 | 13 | 17 | 24 |
| properties | 44 | 54 | — |
| definitions | 20 | —（全數內聯） | — |
| bytes | 6,818 | 6,988 | — |
| object / array 節點 | 13 / 9 | 15 / 10 | — |
| enum 站點／enum 值總數 | 8 / — | 9 / 39 | — |
| schema 巢狀層數（property／array hop） | — | 9 | — |

最深路徑穿過**三層巢狀陣列**：

```text
root.work_signals[].task_change.split_children[].task_fields.enablers[].kind
```

17 個 nullable union 的分佈（展開後）：

- **8 個（47%）在 `TaskFields` 的四個選填欄位**（`purpose_result`／`context`／
  `deliverable_hint`／`success_criterion_hint`），因為 `TaskFields` 被
  `task_change.task_fields` 與 `split_children[].task_fields` 各內聯一次而**乘二**；
- 4 個是 disposition 的載荷插槽（`task_change`／`exclude`／`open_issue`）與 `resolves_open_issue_ordinal`；
- 3 個在 `next_question.target`；
- 2 個是 `withdraw_reason` 與 `target` 本身。

## 4. 診斷

**union 超限是目前最強、而且可直接否證的根因假說。** 它還不是已證實的根因。

- 送出形式只有 **13** 個 union——**在 16 上限之內**；
- **本地把 `$ref` 展開後是 17 個——超出 16**；
- optional 是 17，在 24 上限之內。

為什麼還不能收尾成定論：本次 400 只說 `compiled grammar is too large`，**沒有回報 union count、
也沒有指出是哪一段超限**。17 > 16 是非常強的證據，但因果要靠 Probe U 補上——
**用「本地展開後超限」推得「Anthropic 編譯器也這樣計數」是推論，不是觀測**。

同理，optional 17 雖未超過自己的 24 上限，**不能在 Probe U 前完全排除交互影響**：
官方同時列出 union、optional 與其他結構限制，這些成本可能互相作用而非各自獨立。
巢狀深度 9 與三層巢狀陣列同樣未被觀察到超限（官方未對深度設限，OpenAI 的 10 層我們也在其內），
但它們也留在「未排除」而非「已排除」。

如果 Probe U 通過，就同時驗證了兩件事：union 是綁定維度，且編譯器確實按展開後形狀計數。
如果 Probe U 失敗，則上述推論至少有一環不成立，需要重新設計下一個探針。

一個與修法直接相關的觀察（同樣待 Probe U 驗證）：`TaskFields` 被
`task_change.task_fields` 與 `split_children[].task_fields` **各內聯一次**，四個選填欄位因此
在展開後變成八個 union——若編譯器按展開後計數，這一次重複就佔掉半數額度，也正是把 13 推過 16 的主因。
`$ref` 未被去重這一點與社群回報一致（[anthropics/anthropic-sdk-python#1185](https://github.com/anthropics/anthropic-sdk-python/issues/1185)，
2026-02-18，無官方回覆）。這只是旁證，官方數字才是判準。

### 撤回先前結論

本稿前一版有三處錯誤，在此撤回：

1. 「Anthropic 官方沒有公布任何數量上限」——**錯**，官方頁明列 optional 24、union parameters 16；
2. 「我們的 union 遠低於已知失敗門檻」——**錯**，展開後 17 已超出官方上限 16；
3. 「以 20 次二分探針（≈US$0.04）量出完整門檻表」——**撤回**。門檻已由官方公布，不需要自己量；
   目前唯一的已知超限項只有一個，做完整門檻表是沒有必要的工。

保留的部分：`$ref` 展開量測（§3）與共用編譯器診斷（§1）。前者現在是主要證據，後者解釋了錯誤訊息。

## 5. 方案比對

### A. 精簡的固定 strict wire schema ＋ mapper（討論稿方案 1）——採用

以 `""`／`0`／`"none"`／`[]` 取代 null union，目標 provider schema **零 `anyOf`**；新增很薄的
`ProviderTaskAnalysisResult` ＋ 純 mapper 轉回既有 `TaskAnalysisResult`；domain、verifier、
資料庫、prompt 判準全不動。

- **為什麼先試它**：它把目前唯一已知的超限項（展開後 17 union）打到 0，額度從超出 1 變成剩餘 16。
  這是對準最強假說，不是繞路——但假說成立與否要由 Probe U 回答，不是由本節宣告。
- **保留 strict 保證**，因此不動 ADR 0040 決定 26 的 portable strict 契約，也不放棄
  deterministic local verifier 這層安全網。
- **成本**：中性值把「沒有值」與「值是空字串／0／none」在 wire 上混同，mapper 必須嚴格拒絕
  不一致內容才不會把語意漏洞帶進 domain——討論稿已正確要求這一點，保留。
- **殘餘風險**：若官方的 16 是在**展開後**計數（我們的證據支持這個讀法），零 union 必然通過；
  若編譯器另有未公布的深度／分支成本，仍可能失敗。這正是 Probe F 存在的理由。

### B. discriminated `anyOf`（討論稿方案 2）——不採

每個結果一個分支語意較漂亮，但 union 正是官方設限最緊的維度（16），這個方向會把成本堆回
綁定條件上。不採。

### C. 放棄 strict 或拆成兩次呼叫（討論稿方案 3）——不採，但不永久排除

放棄 strict 會失去格式保證（我們**本來就有** deterministic local verifier ＋ 一次 HTTP 無 retry，
實際風險比表面小）；兩次呼叫會改變 A6 一階段設計、增加成本、延遲與錯誤傳播。
兩者都動到 ADR 0040 決定 26。只有在 Probe U **且** Probe F 都失敗時才回到這條路，屆時**必須開 ADR**。

## 6. 驗證協定：Probe U

### 成本前提（保守措辭）

本次 400 的 capture 顯示總支出 US$0、無 `usage`。**那是一次觀測，不是官方的免費保證**——
不得推論「所有 grammar rejection 都不計費」。因此 Probe U 自帶**單次硬上限 US$0.05**：
送出前先算保守 reserve，超過上限、或事後 route／usage attribution 不完整，即停線並記錄。

### Probe U（唯一變因：消除 union）

以**目前這一次失敗的請求為基礎**，只做機械轉換：

```text
anyOf: [X, null]  →  X
```

Probe U 階段**不得**：新增 `"none"`／空物件或任何中性 sentinel、修改 enum、修改 property 數量或
名稱、改變巢狀／陣列／`split_children`／`enablers` 結構、改 prompt／model／provider／route／
fallback 設定、retry。

這個 probe 只回答一個問題：**移除 union 之後 grammar 能否編譯**。
它**不要求輸出具備產品語意**，結果**不得送進 application transition**（不碰 PostgreSQL、
不呼叫 `submit_employee_turn()`）。

必須保存的證據：原 schema hash 與 probe schema hash、轉換前後的 union／optional／property／
depth 計數、HTTP status、upstream error 與 request ID、route attribution、usage／cost evidence，
以及明確的 `generation_calls = 1`、`retries = 0`。

### 裁決規則

- **Probe U 失敗** → 證明單純去除 union 不足以編譯。**屆時才設計下一個探針（Probe F）；現在不預先設計。**
- **Probe U 通過** → 證明「去除 nullable union」這個方向有效，
  **但不等於方案 A 已完成**。接著才設計真正的 sentinel wire schema 與 mapper；
  該最終 production schema **必須單獨重跑一次 turn 1**——加入 sentinel enum／payload 之後，
  它已經不是 Probe U 的同一份 grammar。
- **production schema 通過 turn 1 之後**，才繼續原本的三回合 smoke。

## 7. 執行順序

1. **Probe U**（丟棄式 experiment 腳本 ＋ 離線計數測試；不改 production schema、prompt 或
   application code）——先回報 diff 與計數，再送**唯一一次** live request；
2. 通過 → 設計 sentinel wire schema ＋ mapper，實作後**單獨重跑一次 turn 1**；
3. turn 1 通過 → 才繼續三回合 smoke；
4. Probe U 不通過 → 屆時才設計下一個探針；
5. **不先改 prompt**——避免同時改兩個變因。討論稿這一點正確，保留。

ADR 門檻：**最終 strict schema 若能維持原產品語意，不需要新 ADR**；只有在 strict 經合理精簡後
仍不可行、準備改成 non-strict 或拆成兩次呼叫時，才需要開 ADR。

## 8. 可下與不可下的結論

可以說：

> 產品的 strict output schema 在**本地** `$ref` 展開後有 17 個 union parameters，超出 Anthropic
> 官方公布的 16 上限。這是目前最強、可直接否證的根因假說；optional 為 17，在 24 上限之內。

不可以說：

- 「Anthropic 沒有公布上限」——**有**，optional 24、union parameters 16；
- 「union 超限已確認為本次 400 的根因」——本次錯誤只回報 `compiled grammar is too large`，
  沒有回報 union count；因果待 Probe U；
- 「編譯器確定按 `$ref` 展開後計數」——那是由本地展開超限推得的**推論**，Probe U 才能驗證；
- 「optional 與巢狀已被排除」——官方限制可能互相作用，Probe U 前只能說「未觀察到超限」；
- 「消除 union 之後一定會通過」——Probe U 尚未執行；
- 「grammar rejection 一定不計費」——只有一次 US$0 的觀測，不是官方保證；
- 「schema 必須小於 N bytes」——沒有任何來源支持這種常數，不得寫進程式。

## 9. 本輪不做

- 不改 prompt、model、max output、verifier、domain 或 production schema；
- 不做完整門檻表、不做多輪二分——官方已公布門檻；
- **不預先設計 Probe F**——只有 Probe U 失敗才設計；
- 不設「schema 必須少於幾 bytes」這類脆弱常數；
- 不引入 non-strict 或兩次呼叫，除非 strict 經合理精簡後仍不可行，且另開 ADR。
