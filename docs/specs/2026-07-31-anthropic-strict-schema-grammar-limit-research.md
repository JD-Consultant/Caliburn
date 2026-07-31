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

## 2. 官方資料查核（2026-07-31 查核）

| 來源 | 有記載什麼 | **沒有**記載什麼 |
|---|---|---|
| [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | 支援子集：`anyOf`、`allOf`（但 `allOf` 搭 `$ref` 不支援）、`$ref`/`$def`/`definitions`（外部 `$ref` 不支援）、`enum`、`const`、`default`、`required`、`additionalProperties: false`、字串 format、陣列 `minItems`（只支援 0／1）。不支援遞迴 schema、數值／字串約束。grammar 編譯有首次延遲，編譯結果快取 24 小時 | **完全沒有任何數量上限**：沒有 union 數上限、沒有 optional 欄位上限、沒有巢狀深度上限、沒有 property 數上限、沒有 grammar 體積上限。也**沒有**這個錯誤訊息本身 |
| [Anthropic Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use) | 與 structured outputs 共用 grammar 編譯管線與 24 小時 schema 快取；PHI 不得放進 schema | 同上，無任何複雜度上限 |
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 明確數字：「up to 5000 object properties total, with up to 10 levels of nesting」、「Total string length of all property names, definition names, enum values, and const values cannot exceed 120,000 characters」、「up to 1000 enum values」。strict 要求**所有欄位 required**，optional 以 `["string","null"]` union 模擬 | — |
| [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) | 「Support is determined per endpoint, not just per model」；「Enforcement varies by provider: some guarantee schema-conforming output, while others translate your schema into their own structured-output format or treat it as a strong hint」 | 沒有任何 schema 複雜度建議 |

**必須更正討論稿的一項事實**：討論稿說「沒有超過 Anthropic 明示的 16 個 union 上限」。
查核結果是 **Anthropic 官方文件沒有公布任何 union 上限**（16 或其他數字）。我查了 structured
outputs（兩次不同提問）、strict tool use、tool use overview 四處，都只有「支援／不支援哪些
JSON Schema 語法」，沒有任何數量門檻。這個數字不能當判準用。

### 2.1 非官方但方向一致的證據（明確標記為社群回報）

[anthropics/anthropic-sdk-python#1185](https://github.com/anthropics/anthropic-sdk-python/issues/1185)
（2026-02-18 開啟，**截至查核時無 Anthropic 維護者回覆**）回報的失敗 schema：約 50 個 property、
約 48 個 nullable union、5 層巢狀。回報者的診斷是 nullable union 造成 FSA 分支膨脹，且
**`$ref`／`$defs` 沒有被去重、而是展開內聯**。同一批社群回報另提到 `output_config.format`
在**約 24 個以上 optional 參數**時開始出現此錯誤。相關回報另見
[anthropics/claude-code#55539](https://github.com/anthropics/claude-code/issues/55539)。

這些是使用者觀測，不是規格。可以拿來**排序假設**，不能拿來當設計常數。

## 3. 本產品 schema 實測

`task_analysis_result.v1`（`llm/portable_schema.py` 產生，schema hash `sha256:a233699…`）：

| 指標 | 送出形式（含 `$ref`） | **`$ref` 展開後**（社群回報中編譯器實際看到的形狀） |
|---|---|---|
| bytes | 6,818 | 6,988 |
| definitions | 20 | —（全數內聯） |
| properties | 44 | **54** |
| nullable union（`anyOf: [X, null]`） | 13 | **17** |
| 其他 union | 0 | 0 |
| object / array 節點 | 13 / 9 | 15 / 10 |
| enum 站點／enum 值總數 | 8 / — | 9 / **39** |
| `description` 欄位 | — | 5 |
| **schema 巢狀層數**（property／array hop） | — | **9** |

討論稿的「13 nullable union、20 definitions、44 欄位」與送出形式相符，量測無誤。

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

## 4. 診斷：哪一個變數是綁定條件？

**還不知道，而且現有資料不足以判定。** 這是本研究最重要的結論。

把我們的數字和唯一可比的失敗回報並排：

| 指標 | 社群回報的失敗案例 | 本產品（展開後） | 相對 |
|---|---|---|---|
| properties | ~50 | 54 | 相當 |
| nullable union | ~48 | **17** | **少 65%** |
| 巢狀層數 | 5 | **9** | **深 80%** |
| 巢狀陣列 | 未提 | **3 層**（`work_signals[]` → `split_children[]` → `enablers[]`） | — |

我們的 nullable union 遠低於回報的失敗門檻（~48），也低於社群提到的 ~24 optional 門檻，
**卻仍然被拒**。同時我們的巢狀比對方深近一倍，而且深度來自巢狀陣列。

在 FSA／grammar 編譯裡，扁平的 optional 欄位是**相加**成本，巢狀陣列裡每個 item 的分支是
**相乘**成本。因此更可能的主因是「`work_signals[]` 的每個 item 帶一組四選一 disposition ＋
三個選填載荷物件，其中一個再包一層 `split_children[]` 陣列、裡面又包 `enablers[]` 陣列」
這個結構，而不是 optional 欄位的絕對數量。

**這直接影響修法選擇**：討論稿的方案 1（把所有 optional 改成中性值、目標零 `anyOf`）
只削減 17 個 nullable union，**沒有動到巢狀陣列結構**。若綁定條件真的是深度×分支，
做完整套 wire schema ＋ mapper ＋ 測試之後仍可能被拒——那是白做一輪。

反過來說也成立：如果綁定條件真的是 union 數，方案 1 就會直接成功。**兩種可能都存在，
而且分辨它們的成本極低。**

## 5. 關鍵發現：分辨成本是 US$0

本次 400 的 capture 顯示：`usage` 缺席、`usage.cost` 缺席、OpenRouter 記錄總支出 **US$0**。
請求在 grammar 編譯階段就被拒，**沒有生成任何 token，因此不計費**。

含意：既然限制未公開，**直接量測就是最權威、也最便宜的來源**。

- **被拒的探針：US$0。**
- **通過的探針**：可用 `max_tokens: 1` ＋ 一句話 user message，成本約 300 input token
  ＋ 1 output token ≈ **US$0.002**。
- 20 次二分探針 ≈ **US$0.04**，遠低於一次 smoke 回合。

這讓我們可以在寫任何 mapper 之前，先用零成本二分法回答三個問題：

1. 現行 schema 的哪一段跨過門檻？（逐段砍：拿掉 `split_children` / 拿掉 `enablers` /
   把 4 個 `TaskFields` 選填欄位改必填 / 拿掉 `exclude`＋`open_issue` 載荷，各測一次）
2. 純粹消除 nullable union（方案 1 的形狀）是否**足夠**？
3. 若不足夠，還要砍掉哪一層巢狀才通過？

沒有這組數字，任何 schema 重設計都是在猜。

## 6. 方案比對

### A. 精簡的固定 strict wire schema ＋ mapper（討論稿方案 1）

以 `""`／`0`／`"none"`／`[]` 取代 null union，目標 provider schema 零 `anyOf`；新增很薄的
`ProviderTaskAnalysisResult` ＋ 純 mapper 轉回既有 `TaskAnalysisResult`；domain、verifier、
資料庫、prompt 判準全不動。

- **優點**：保留 strict 保證與既有安全網；不動 ADR 0040 決定 26 的 portable strict 契約；
  mapper 是純函式、可完整測試；與 OpenAI 的 strict 慣例（全欄位 required）一致。
- **風險（新增，討論稿未涵蓋）**：**它只削 union，不削巢狀陣列深度**。若綁定條件是深度×分支，
  做完仍會被拒。§5 的探針可在動工前排除這個風險。
- **次要成本**：中性值把「沒有值」與「值是空字串／0／none」在 wire 上混同，mapper 必須嚴格
  拒絕不一致內容才不會把語意漏洞帶進 domain——討論稿已正確要求這一點。

### B. discriminated `anyOf`（討論稿方案 2）

語意乾淨，但 union 正是最可疑的成本來源之一，方向與診斷相反。**不採**。

### C. 放棄 strict 或拆成兩次呼叫（討論稿方案 3）

放棄 strict 會失去格式保證（但我們**本來就有** deterministic local verifier ＋ 一次 HTTP 無 retry
的設計，這條路的實際風險比表面小）；兩次呼叫會改變 A6 一階段設計、增加成本與錯誤傳播。
兩者都動到 ADR 0040 決定 26，**必須另開 ADR**。目前不採，但**不應在取得 §5 數字前就永久排除
非 strict**——如果連方案 A 都過不了門檻，非 strict ＋ local verifier 會變成唯一不改產品語意的出路。

### D.（本研究新增）先做零成本 grammar 探針，再選 A 或 C

不寫 mapper、不改 domain，只用一支丟棄式腳本送 N 個候選 schema，記錄 400／200 邊界。
產出是一張「哪些構造跨過門檻」的表，然後才決定做 A 還是 C。

- **成本**：≈US$0.04、半天以內。
- **風險**：低。不動產品程式，不改契約，探針腳本用完即棄。
- **它買到什麼**：把「猜哪個變數綁定」變成「量到哪個變數綁定」，並讓後續 ADR 有實測依據
  而不是社群 GitHub issue。

## 7. 建議

**採 D → 再依結果做 A（或在 A 被證明不足時，才討論 C）。**

理由：修法本身（A）是合理的 provider 邊界修正，我不反對它的形狀；但它建立在
「nullable union 是主因」這個**未經驗證且與我們自己的數字有衝突**的假設上
（我們只有 17 個 union，遠低於已知失敗門檻，卻仍被拒）。既然驗證這個假設只要 US$0.04，
先量再做是嚴格佔優的順序。

執行順序：

1. **零成本探針**（丟棄式腳本，不進 `app/`）→ 產出門檻表，寫進本研究紀錄的續章；
2. 依門檻表**開 ADR**（動到 ADR 0040 決定 26 的 strict／portable 契約就必須開）；
3. 再寫 bite-size plan 實作 wire schema ＋ mapper；
4. 修好後**先只重跑 turn 1**，能生成才繼續三回合語意 smoke；
5. **不先改 prompt**——避免同時改兩個變因。討論稿這一點正確，保留。

## 8. 可下與不可下的結論

可以說：

> 產品的 strict output schema 被 Anthropic 的 grammar 編譯器拒絕。Anthropic 未公開任何
> grammar 體積或 union 數上限；我們的 schema 展開後為 54 property、17 nullable union、
> 9 層巢狀（含三層巢狀陣列），遠低於 OpenAI 公布的上限，但仍被 Anthropic 拒絕。

不可以說：

- 「超過 Anthropic 的 16 個 union 上限」——**沒有這個公開上限**；
- 「nullable union 是本次失敗的原因」——尚未驗證，且我們的 union 數低於已知失敗案例；
- 「改成中性值就會通過」——未驗證；
- 「schema 必須小於 N bytes」——沒有任何來源支持這種常數，也不該寫進程式。

## 9. 本輪不做

- 不改 prompt、model、max output、verifier 或 domain；
- 不在取得門檻表前寫 mapper 或改 provider schema；
- 不設「schema 必須少於幾 bytes」這類脆弱常數（討論稿已正確排除，保留）；
- 不引入 non-strict 或兩次呼叫，除非方案 A 被實測證明不可行，且另開 ADR。
