# Plan:Task Analysis compact model-facing wire contract

**日期**:2026-07-31
**依據**:[`specs/2026-07-31-context-engineering-model-facing-contract-research.md`](../specs/2026-07-31-context-engineering-model-facing-contract-research.md)
(原則與量測)、[`specs/2026-07-31-anthropic-strict-schema-grammar-limit-research.md`](../specs/2026-07-31-anthropic-strict-schema-grammar-limit-research.md)(400 的量測)
**不開 ADR**:維持 `strict: true` 與一次呼叫,ADR 0040 決定 24／26 不變。只有改 non-strict 或拆成兩次呼叫才需要 ADR。

## 目標

解除 `compiled grammar is too large`,同時把每回合的固定成本降下來。

| 維度 | 現況 | 目標 | 官方限制 |
|---|---:|---:|---:|
| union parameters | 17(展開後) | **0** | 16 |
| nesting levels | 9 | ≤ 6 | — |
| properties | 54 | ≤ 35 | — |
| schema wire bytes | 6,818 | ≤ 4,500 | — |
| instructions bytes | 6,203 | ≤ 5,200 | — |
| request bytes | 14,491 | ≤ 11,000 | — |

**位元組目標在 T1／T3 被上修過,原值訂錯了。** schema 原訂 3,000:實測 4,084,再壓下去
只能縮短 property 名稱,與「descriptive, unambiguous」相衝。instructions 原訂 2,800:
五段顧問判準加開場白就是 3,867,不變量 1 說那些一字不改,2,800 從一開始就不可能。
真正的綁定條件是結構維度,不是位元組。

union 目標是 **0 而非「≤16」**:官方明載個別限制全部滿足仍可能被拒
(「even if each individual limit in the preceding table is satisfied」),另有未公開的
compiled grammar size 上限。瞄準剛好合規沒有餘裕。

## 不變量(違反就是做錯了)

1. **`TASK_ANALYSIS_INSTRUCTIONS` 的顧問判準一字不改** —— 「顧問訪談方式」「Task 成立條件」
   「Enabler 硬規則」「Split 與 Merge」「不成立的訊號怎麼放」五段共 3,658 bytes 是產品本身。
   只刪 verifier 已強制與 strict 已保證的段落。
2. **`verifier.py`、`transition.py`、`durable_turn.py`、DB migration、`apps/web` 一律不動。**
   既有測試就是 characterization net,green-before == green-after。
3. **mapper 只做中性值還原,不做語意判斷。** 任何「哪個欄位該非空」的判斷留在 verifier。
4. **夾帶要拒絕,不能靜默丟棄。** disposition 未使用的欄位若帶非中性值,mapper 必須讓該回合
   落到 `INVALID_OUTPUT`;靜默丟棄會讓 verifier 失去攔截能力。

---

## T1 — wire 契約與離線計數 gate

**新增** `app/job_analysis/llm/wire.py`:`TaskAnalysisWire` 及其 `$defs`。
**新增** `app/job_analysis/llm/schemas/task_analysis_wire.v1.json` committed golden。

形狀(扁平化 `WorkSignal`,把三個 payload 插槽的欄位提升到同一層):

```
TaskAnalysisWire        work_signals[], next_question
WireSignal(12)          anchors[], relation, target_task_ordinals[], supersedes[],
                        resolves_open_issue_ordinal, disposition, change,
                        withdraw_reason, task, split_children[],
                        rejection_code, rejection_summary
WireTaskFields(5)       statement, action, object, purpose_result, enablers[]
WireSplitChild(4)       statement, action, object, inherited_support_ordinals[]
WireAnchor(2)           turn_ordinal, quote
WireSupersession(2)     task_ordinal, support_ordinal
WireEnabler(2)          kind, name
WireNextQuestion(3)     text, target_kind, target_ordinal
```

中性值約定(取代所有 nullable union):

| 原本 | wire | 中性值 |
|---|---|---|
| `purpose_result: str \| None` 等 | `string` | `""` |
| `task_change: TaskChangePayload \| None` | `change` enum 加 `none` | `"none"` |
| `withdraw_reason: RetirementReason \| None` | enum 加 `none` | `"none"` |
| `task_fields: TaskFields \| None` | `task` required | 三個字串全 `""` |
| `exclude` + `open_issue` 兩個插槽 | 合併成 `rejection_code` + `rejection_summary` | `"none"` / `""` |
| `resolves_open_issue_ordinal: int \| None` | `integer` | `0` |
| `next_question.target: … \| None` | `target_kind` enum 加 `none` | `"none"` |

`exclude` 與 `open_issue` 的 payload 同構(reason/kind + summary),故合併;
`rejection_code` 的值域是 `none` ＋ 5 個 `ExclusionReason` ＋ 4 個 `OpenIssueKind` = 10 值,
**由 `disposition` 決定 mapper 放進哪一個 payload**,不由 mapper 自行推斷。

`next_question` 的 `ordinal`／`index` 合併成單一 `target_ordinal`,由 `target_kind` 決定語意。
**sentinel 由 `target_kind` 承載,不由數值承載** —— `new_signal` 的 index 可以是 0,
用 `0 = 無` 會把合法值吃掉。

`split_children` 只帶 `statement`／`action`／`object` ＋ `inherited_support_ordinals`,
**不複製整份 `TaskFields`**。這一項單獨移除 17 個 union 中的 8 個並砍掉 2 層巢狀;
domain 的 `SplitChildPayload.task_fields` 不變,其餘欄位由 mapper 留 `None`,
後續回合以 `revise` 補齊(progressive disclosure)。

`description` 政策:只允許承載「欄位名無法表達的中性值約定」(例:`change` 的 `"none"` 表示
這個訊號不是 Task 變更),**總量上限 600 bytes**,禁止內部規格章節號與範例 ID。
這是刻意把規則從 prompt 散文搬進介面。

### T1 的驗證

新增 `tests/test_job_analysis_wire_schema.py`,離線、零網路:

- `union_parameters == 0`、`nesting_levels <= 6`、`properties <= 35`、wire bytes `<= 3000`
- 每個 object 仍 `additionalProperties: false` 且 `required == list(properties)`
- 通過既有 `assert_portable_strict_output_schema()`
- committed golden 與生成結果一致(沿用既有 golden 比對慣例)
- description 總量 `<= 600` bytes、不含 `§` 與 `TI-` 前綴

**T1 需先確認的事實**(寫碼前查,結果記在 commit message):
`resolves_open_issue_ordinal` 對應的 open issue ordinal 是否 1-based。若為 0-based,
`0 = 無` 的 sentinel 不成立,改用 `target_kind` 式的旗標欄位。

**commit**:`feat(job-analysis): add the compact wire contract`

---

## T2 — 純 mapper 與 operation seam

**新增** `wire_to_task_analysis_result(wire) -> TaskAnalysisResult`(放 `llm/wire.py`)。
**改** `application/operation.py` 兩行:line 70 的 schema 來源、line 86 的 parse。

mapper 規則,依**各自的中性標記**驅動,**不依 `disposition`**:

| 判斷 | 產生 |
|---|---|
| `change != "none"` | `TaskChangePayload` |
| `rejection_code` 落在 `ExclusionReason` 值域 | `ExcludePayload` |
| `rejection_code` 落在 `OpenIssueKind` 值域 | `OpenIssuePayload` |
| 以上皆否 | 三個 payload 皆 `None`(即 `support_only`) |

**這一條是本 plan 起草時的修正。** 原本寫「依 `disposition` 驅動」,實作時發現那會讓
mapper 做語意判斷並靜默「修正」矛盾——模型說 `disposition=exclude` 卻給 open-issue 的
code 時,依 disposition 會產出 `ExcludePayload`,`PAYLOAD_DOES_NOT_MATCH_DISPOSITION`
就永遠不會觸發。兩個值域互斥,依值決定落點是純的,而且保住每一條既有 violation。

拒絕的條件收斂成一句:**內容沒有 domain 落點就拒絕**。
`change` 是 `"none"` 時沒有 `TaskChangePayload`,所以 `task`／`split_children`／
`withdraw_reason` 帶內容即拒;`rejection_code` 是 `"none"` 時沒有 payload,
所以 `rejection_summary` 非空即拒。其餘一律放行給 verifier
(例如 `change=add` 卻帶 `withdraw_reason` → `WITHDRAW_REASON_FORBIDDEN`)。

`identity.target_task_ordinals` 與 `task_change.target_task_ordinals` 由 wire 的**單一**
`target_task_ordinals` 同時填入 —— verifier 的 `TARGET_ORDINALS_DISAGREE` 因此恆不觸發,
這是預期的:該規則本來就在驗兩份重複資料一致。

**domain 的兩處移除**(零消費者,全 repo 已 grep 確認):
`NextQuestion.purpose`、`TaskAnalysisResult.limitations`。留著會逼 mapper 填假資料
(`purpose` 是 `NonEmptyText` 必填)。移除前確認 DB 與 web 皆未持有。

### T2 的驗證

新增 `tests/test_job_analysis_wire_mapper.py`:

- 四種 disposition × 五種 change 各一條 round-trip
- `""` → `None`、`"none"` → `None`、`0` → `None` 各一條
- **夾帶拒絕**:每種 disposition 各一條「未使用欄位帶非中性值 → raise」
- `rejection_code` 與 `disposition` 值域不符 → raise
- `split` 的 child 只有三個語意欄位時仍能建出合法 `SplitChildPayload`
- mapper 不修改輸入
- 既有 `tests/test_job_analysis_operation*.py`、verifier、transition 測試全綠

**commit**:`feat(job-analysis): map the wire contract onto the domain result`

---

## T3 — instructions 瘦身

只刪兩段中確定由別處保證的句子,目標 ≤ 5,200 bytes(實測 5,090):

| 刪除 | 依據 |
|---|---|
| 「只輸出符合輸出 schema 的 JSON,不要加說明文字、不要包在程式碼區塊裡」 | strict 保證;且官方文件載明 structured outputs 會自動注入輸出格式說明,這是第三份拷貝 |
| 「一輪只問一個問題」 | `next_question` 是單一物件 |
| 「`disposition` 決定哪一個 payload 欄位非空,其餘三個必須是 null」 | wire 已無 payload 插槽;改由 `description` 承載中性值約定 |
| 「`identity.relation` 與 `task_change.change` 必須一致…」對照表 | `RELATION_DOES_NOT_MATCH_MAPPING` |
| 「你永遠不產生 ID」 | 壓成半句(schema 無 ID 欄位,但防幻覺仍有值) |
| 「每一筆訊號都要有 `anchors`」 | `ANCHOR_MISSING` |
| `retired_tasks` 不得出現在 target | `TARGET_ORDINAL_RETIRED` |
| `supersedes` 的回合必須在 anchors 裡 | `SUPERSESSION_MISSING_CURRENT_TURN_ANCHOR` |
| `resolves_open_issue_ordinal` 的兩種可填情況 | `RESOLUTION_MAPPING_INVALID`／`_NOT_RECONCILABLE` |
| `limitations` 那一句 | 欄位已移除 |

**保留**:`quote` 必須逐字(違反成本高,值得先講)、矛盾未解引兩句、pending/deferred 是待決假說、
`split` 的 inherited support 只選真正支持該 child 的、duplicate/overlap/uncertain 要追問不得自動 merge。
這些是語意判斷,verifier 只能驗形式。

### T3 的驗證

`tests/test_job_analysis_prompt.py`:instructions bytes `<= 5200`;五段顧問判準**逐段
位元組數**不變(比 hash 可讀,而且一樣抓得到誤傷);已搬走的規則不得回流(逐條對上
`ViolationCode`);只有模型能做的判斷仍在。

**commit**:`refactor(job-analysis): drop instructions the verifier already enforces`

---

## T4 — 單次 live turn 1

沿用 `scripts/job_analysis_live_smoke.py`,`--max-generation-calls 1`。

- 上限 **US$0.10**、零 retry、失敗即停線並寫進
  `docs/experiments/2026-07-31-job-analysis-attributed-live-smoke/`
- 必須留存:HTTP status、upstream error／request ID、route attribution、usage／cost、
  `generation calls`、`retries`、schema hash
- 通過後才續跑原本的三回合 smoke(仍在原 US$0.75 授權的剩餘額度內)

**T1–T3 全部離線、零成本。T4 需要 owner 放行金額。**

---

## 執行紀錄

| Task | 狀態 | commit | 備註 |
|---|---|---|---|
| T1 | ✅ | `aef0d2f` | union 17→0、properties 54→32、nesting 9→6、wire 6,818→4,084 bytes。byte 預算由 3,000 改成 4,500 並改記為粗略迴歸護欄:實測 4,084,再壓下去只能縮短 property 名稱,與 S5「descriptive, unambiguous」相衝。同時移除已取消的 Probe U |
| T2 | ✅ | (本 commit) | v2 成為唯一送出去的形狀;v1 provider schema 與 golden 一併移除(已無人送)。mapper 改為值驅動(見上)。`NextQuestion.purpose`、`TaskAnalysisResult.limitations` 移除 |
| T3 | ✅ | (本 commit) | 6,203 → 5,090 bytes(−18%);兩段機械規則 2,336 → 1,223(−48%),「輸出規則」整段消失。五段判準逐段位元組數不變,由 `test_job_analysis_prompt.py` 逐段守住 |
| T4 | 未開始 | | 待 owner 放行 US$0.10 |
