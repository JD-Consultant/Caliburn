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

**綁定條件是 union parameters，而且只超出 1。**

- 送出形式只有 **13** 個 union——**在 16 上限之內**；
- `$ref` 展開後是 **17** 個——**超出 16**；
- optional 是 17，在 24 上限之內，**不是**綁定條件。

這同時證實了一件對修法很重要的事：**編譯器計數的是 `$ref` 展開後的形狀，不是我們送出的形狀**。
`$defs` 不會替我們省下 union 額度。具體到本產品，`TaskFields` 被內聯兩次，四個選填欄位因此
變成八個 union——**光是這一次重複內聯就佔掉半數額度，也正是把我們從 13 推過 16 的主因**。

`$ref` 展開這一點與社群回報一致（[anthropics/anthropic-sdk-python#1185](https://github.com/anthropics/anthropic-sdk-python/issues/1185)，
2026-02-18，無官方回覆，報告者亦觀察到 `$ref`／`$defs` 未被去重而是展開內聯）。這只是旁證，
官方數字才是判準。

巢狀深度 9 與三層巢狀陣列**不是已知的超限項**（官方未對深度設限，OpenAI 的 10 層我們也在其內）。
它降級為**次要假設**：只有在消除 union 之後仍被拒，才需要考慮深度×分支的乘性成本。

### 撤回先前結論

本稿前一版有三處錯誤，在此撤回：

1. 「Anthropic 官方沒有公布任何數量上限」——**錯**，官方頁明列 optional 24、union parameters 16；
2. 「我們的 union 遠低於已知失敗門檻」——**錯**，展開後 17 已超出官方上限 16；
3. 「以 20 次二分探針（≈US$0.04）量出完整門檻表」——**撤回**。門檻已由官方公布，不需要自己量；
   已知超限項只有一個，做完整門檻表是沒有必要的工。

保留的部分：`$ref` 展開量測（§3）與共用編譯器診斷（§1）。前者現在是主要證據，後者解釋了錯誤訊息。

## 5. 方案比對

### A. 精簡的固定 strict wire schema ＋ mapper（討論稿方案 1）——採用

以 `""`／`0`／`"none"`／`[]` 取代 null union，目標 provider schema **零 `anyOf`**；新增很薄的
`ProviderTaskAnalysisResult` ＋ 純 mapper 轉回既有 `TaskAnalysisResult`；domain、verifier、
資料庫、prompt 判準全不動。

- **為什麼現在站得住**：它直接把唯一的超限項（17 union）打到 0，額度從超出 1 變成剩餘 16。
  不是繞路，是對準綁定條件。
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

## 6. 驗證協定：最多兩次探針，每次一個變因，零 retry

被拒的請求在 grammar 編譯階段就終止、不生成 token，因此**不計費**（本次 400 的 capture 已證實：
無 `usage`、總支出 US$0）。通過的探針以 `max_tokens: 1` ＋一句話 user message 收尾，成本可忽略。
探針用丟棄式腳本，**不進 `app/`**。

### Probe U（先做，唯一變因：消除 union）

把 17 個 nullable union 全部改成必填＋中性值（`""`／`0`／`"none"`／`[]`），
**巢狀結構、陣列層數、property 數、enum 一律不動**。送一次。

- **通過** → 綁定條件確認為 union，方案 A 即為修法。**不開新 ADR**——這是 provider 邊界修正，
  strict 與 portable 契約都沒有改變，ADR 0040 決定 26 原樣成立。直接寫 bite-size plan 實作。
- **失敗** → 才做 Probe F。

### Probe F（只有 U 失敗才做，唯一額外變因：扁平化最深 split 路徑）

在 Probe U 的基礎上，額外扁平化最深的 split 路徑
（`work_signals[].task_change.split_children[].task_fields.enablers[]`）。送一次。

- **通過** → 除 union 外還需降低巢狀成本；修法範圍擴大到結構調整，仍在 strict 之內。
- **失敗** → strict 這條路在目前 schema 形狀下走不通，改走方案 C，**開 ADR** 再動工。

**上限就是兩次，不重試、不邊看邊改。** 兩次都不改 prompt、model、max output 或 verifier。

## 7. 執行順序

1. **Probe U**（丟棄式腳本，不進 `app/`）；
2. 通過 → 直接寫 bite-size plan 實作 wire schema ＋ mapper，**不開 ADR**；
3. 不通過 → **Probe F**；再不通過 → 開 ADR 討論放棄 strict 或兩次呼叫；
4. 修好後**先只重跑 turn 1**，能生成才繼續三回合語意 smoke；
5. **不先改 prompt**——避免同時改兩個變因。討論稿這一點正確，保留。

## 8. 可下與不可下的結論

可以說：

> 產品的 strict output schema 在 `$ref` 展開後有 17 個 union parameters，超出 Anthropic 官方
> 公布的 16 上限，因此被 grammar 編譯器拒絕。optional 為 17，在 24 上限之內，不是原因。
> 編譯器計數的是展開後的形狀，`$defs` 不會節省額度；`TaskFields` 被內聯兩次是主要來源。

不可以說：

- 「Anthropic 沒有公布上限」——**有**，optional 24、union parameters 16；
- 「巢狀深度是本次失敗的原因」——未觀察到，官方也未對深度設限；它只是 Probe U 失敗時的次要假設；
- 「消除 union 之後一定會通過」——Probe U 尚未執行；
- 「schema 必須小於 N bytes」——沒有任何來源支持這種常數，不得寫進程式。

## 9. 本輪不做

- 不改 prompt、model、max output、verifier 或 domain；
- 不做完整門檻表、不做多輪二分——官方已公布門檻，已知超限項只有一個；
- 不設「schema 必須少於幾 bytes」這類脆弱常數；
- 不引入 non-strict 或兩次呼叫，除非 Probe U 與 Probe F 都失敗，且另開 ADR。
