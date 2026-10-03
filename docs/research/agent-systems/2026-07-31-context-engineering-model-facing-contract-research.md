# Context engineering 與 model-facing contract:主流做法與 Caliburn 對照

**日期**:2026-07-31
**觸發**:`docs/specs/2026-07-31-anthropic-strict-schema-grammar-limit-research.md` 記錄的 400
(`compiled grammar is too large`)顯示 schema 過大。owner 進一步指出:Task 分析只是第一階段,
OPKS(產出／指標／知識／技能)尚未實作,若這一階段就把每回合 14KB 燒掉,後續每個階段都會複製這個模式。
本研究先回答「**context 到底該放什麼**」,再回答「**我們的哪些欄位是必要的**」。

**本研究不做決策**,只提供依據與選項;決策另開 ADR 或 plan。

---

## 1. 來源

全部為第一方或官方 repo,2026 現行版本。

| # | 來源 | 用途 |
|---|---|---|
| S1 | Anthropic,[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | context 的基本原則、attention budget |
| S2 | Anthropic,[The new rules of context engineering for Claude 5 generation models](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)(2026-07-24) | Claude 5 世代的具體增刪準則 |
| S3 | Anthropic Docs,[Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5) | Opus 5 特有的過度指示問題 |
| S4 | Anthropic Docs,[Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | strict schema 的限制與交互作用 |
| S5 | Anthropic,[Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents) | 模型介面設計 |
| S6 | Anthropic,[Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | 何時該把一次呼叫拆成多次 |
| S7 | [anthropics/anthropic-sdk-python#1185](https://github.com/anthropics/anthropic-sdk-python/issues/1185)、[anthropics/claude-code#55539](https://github.com/anthropics/claude-code/issues/55539) | 同一個 400 的公開案例 |
| S8 | OpenAI,[Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 跨廠商對照組 |

---

## 2. 主流做法:六條可操作原則

### P1 — 目標是「最小的高訊號 token 集合」,不是「說清楚每件事」

> "Good context engineering means finding the _smallest possible_ set of high-signal tokens
> that maximize the likelihood of some desired outcome." — S1

理由不是省錢,是 attention。S1 指出 transformer 的 n² 兩兩關係使 context 成為
「a finite resource with diminishing marginal returns」,並命名了 **context rot**:
context 變長時召回準確度下降,而且**遠在視窗填滿之前就開始**。

### P2 — 過度約束會扣分,不只是浪費

S2 點名的失敗模式是**訊息重疊與衝突**:當系統同時說「leave documentation as appropriate」
與「DO NOT add comments」,模型必須「think more carefully about these overlapping and
conflicting messages」才能決定怎麼做。也就是說,重複的規則會消耗推理,不只是消耗 token。

S3 給了同一件事的具體版本:

> "If your prompt contains explicit verification instructions … remove them: instructions like
> these cause over-verification on Claude Opus 5, and removing them reduces wasted tokens
> **with no loss in quality**."

### P3 — 規模化的證據:Claude Code 砍掉 >80% system prompt,coding eval 沒有可測損失

S2 記載 Anthropic 為 Claude 5 世代模型(Opus 5／Fable 5／Sonnet 5)移除了 Claude Code
**超過 80%** 的 system prompt,「with no measurable loss on our coding evaluations」。
被移除的四類:

1. 重複的工具用法示例(改放進 tool description)
2. 關於文件與註解的規則
3. 詳細的 code review 驗證步驟(改放進 skills)
4. 過度指示性的約束

保留的兩類:**產品脈絡**(模型在什麼產品裡運作)、**必要價值觀**(團隊或產品特有的意見、知識、最佳實務)。

刪除準則(S2 原文分類):跨 system prompt 與 tool description 重複的指令;新模型已能自行處理的
過細規則;模型能從檔案結構／repo 脈絡推出的「顯而易見」指引;已不再必要的最壞情況護欄。

### P4 — 規則要放進**介面**,不要放進散文

S2 的關鍵位移是「Examples: 給詳細示例 → **設計更好的 tool 介面/參數**」、
「Repetition: 重複指令 → **只在 tool description 寫一次**」。其示例是用 status enum
(`pending`/`in_progress`/`completed`)加一句「keep one item in_progress」,
以參數設計本身傳遞行為提示,而不是用示例教。

S5 補上模型介面的兩條:只回傳高訊號資訊(「Tool implementations should take care to return
only high signal information back to agents」);把內部識別碼換成語意名稱
(「resolving arbitrary alphanumeric UUIDs to more semantically meaningful and interpretable
language … significantly improves Claude's precision」)。

### P5 — 預先塞好 vs. 用到才取:偏向 just-in-time 與 progressive disclosure

S1 建議代理持有輕量識別(路徑、查詢、連結),執行期才載入,並明說這是 hybrid:
先取一部分加速,其餘讓模型自行探索。代價誠實寫出:「Runtime exploration is slower than
retrieving pre-computed data」。

### P6 — 拆成多次呼叫的判準

S6 的立場是先簡單:「find the simplest solution possible, and only increasing complexity
when needed」、「only when it demonstrably improves outcomes」。可拆的條件與代價:

- **Prompt chaining**:「ideal for situations where the task can be easily and cleanly
  decomposed into fixed subtasks」;代價是「trade off latency for higher accuracy,
  by making each LLM call an easier task」。
- **Parallelization / sectioning**:「LLMs generally perform better when each consideration
  is handled by a separate LLM call」。

注意 S6 說的是**乾淨可分解**的子任務。彼此需要共享推理脈絡的判斷不屬於這一類。

---

## 3. strict schema 的硬事實(修正前一份研究的樂觀假設)

S4 除了 optional 24／union 16 的表格外,還有兩句直接影響我們的策略:

> These limits apply to the **combined total across all strict schemas in a single request**.

> These errors mean the combined complexity of your schemas exceeds what can be efficiently
> compiled, **even if each individual limit in the preceding table is satisfied**.
> As a final stop-gap, the API also enforces a compilation timeout of 180 seconds.

**推論:「把 union 壓到 16 以下」不是通過條件,只是必要條件。** 官方明說個別限制全部滿足仍可能被拒,
另有未公開的 compiled grammar size 上限。因此瘦身目標必須留明顯餘裕,不能瞄準「剛好合規」。

S7 的公開案例與我們高度同構:

| | issue #1185 | Caliburn |
|---|---|---|
| properties | ~50 | 54 |
| nesting | 5 層 | **9 層** |
| nullable | ~48 | 13(展開後 17) |
| 重複 sub-schema | `TypeWithSchema` inline 4 次 | `TaskFields` inline 2 次 |
| 錯誤訊息 | 同一句,且同樣誤導(講 tool schema 但用的是 output format) | 同 |

該 issue 仍 open,無官方回覆;另有 TanStack/ai、agno 等第三方函式庫回報同一錯誤。
**這是 Anthropic grammar 編譯器目前的已知邊界,不是我們用錯 API。**

跨廠商對照(S8):OpenAI 的 strict 限制是 5,000 properties／10 層巢狀／120,000 字元／1,000 enum 值。
我們的 54 props／9 層在 OpenAI 完全合規。**所以我們的 schema 不是以業界標準衡量離譜,
而是專門超出 Anthropic 編譯器的預算。** 這一點決定了選項空間(見 §6)。

---

## 4. 對照:我們違反了哪幾條,可量化

量測見 §7 附錄;request 總計 14,491 bytes。

| 原則 | 我們的狀況 | 可量化代價 |
|---|---|---|
| P2／P3 刪除跨處重複的指令 | prompt 的「行為與禁止事項」＋「輸出規則」用中文散文複述 verifier 已經在跑的判斷;`verifier.py` 有 **28 個 violation code** 逐條對得上 | **2,336 bytes,占 prompt 37.6%** |
| P3 刪除模型已能自行處理的規則 | 「只輸出 JSON、不要包在程式碼區塊裡」——strict 模式本身保證,且 S4 記載 structured outputs 會**自動注入一段說明輸出格式的 system prompt**。這是第三份拷貝 | 該句 + 「一輪只問一個問題」(schema 已強制單一物件) |
| P4 規則放進介面 | tagged union 用「disposition + 4 個永遠 3 空的 payload 插槽」表達,再用散文解釋一次 | 一個決定付兩次:union 數(grammar 上限直接來源)+ 652 bytes 散文 |
| P5 高訊號 | schema 的 `title` 全是 Pydantic 自動生的欄位名 Title Case 版;`description` 含 `§12.3`、`TI-R1-08` 等模型看不懂的內部規格代號 | **1,868 bytes,占 schema 27.4%** |
| S5 不送內部識別 | 同上;`TI-R1-08` 是幻覺誘餌 | 併入上列 |
| P1 最小集合 | `limitations`、`next_question.purpose` **全 repo 零消費者**(api + web 皆已 grep) | 每回合純輸出成本 |

### 4.1 比例是倒過來的

| 區塊 | bytes | 占比 | 每回合資訊量 |
|---|---:|---:|---|
| 固定 instructions | 6,203 | 43% | **不變** |
| JSON Schema | 6,818 | 47% | **不變** |
| 動態 Context Packet | 939 | 6% | 唯一帶新訊號 |
| 其他請求結構 | 531 | 4% | — |

P1 說要找最小的**高訊號** token 集合。我們 90% 的 request 是每回合重複、資訊量不隨訪談增長的固定成本,
真正承載本回合新訊息的只有 6%。訪談進行到第 10 回合、Task 累積到十幾條時,packet 會長大,
固定部分卻不會縮小——**現在的結構是把預算優先給了不變的部分**。

### 4.2 複利成本:寫回 packet 的欄位要付 N×T 次

`context` / `deliverable_hint` / `success_criterion_hint` 三個欄位的**唯一消費者是下一回合的 packet
自己**:存進 `Task`,再由 `application/context.py` 渲染回 packet(而且在 `current_authorities.tasks`
與 `jd_presence` 各渲染一次)。沒有 verifier、UI 或 JD 產出讀它們。

成本結構因此是 **O(N tasks × T turns × 2)** 的輸入 token,不是一次性輸出成本。
這正是 owner 指出的模式:**OPKS 還沒做,已經先為它每回合付費。**

---

## 5. 判準:一個欄位該不該由模型產生

綜合 P1／P4／S5,提出三條同時成立才保留的判準:

1. **語意獨有** —— 需要語意判斷,application 無法從別的欄位或既有狀態推導出來。
2. **有真實下游消費者** —— verifier、transition、UI 或 JD 產出至少一處讀它。
   「只餵回下一回合 packet」不算,那是自我循環。
3. **錯了抓得到** —— verifier 或員工決策能攔下錯誤值。抓不到的欄位等於無法信任的欄位。

外加一條結構判準,來自 §3 的 grammar 事實:

4. **罕見路徑不得讓常見路徑付固定成本** —— strict grammar 是每回合編譯同一份,
   罕見分支的結構複雜度由每一次呼叫平均承擔。

### 5.1 用判準過一遍 40 個葉子欄位

**A. 保留(三條全過)**

`anchors[].turn_ordinal`、`anchors[].quote`、`disposition`、`identity.relation`、
`identity.target_task_ordinals`、`task_change.change`、`task_change.withdraw_reason`、
`task_fields.statement/action/object/purpose_result`、`task_fields.enablers[].kind/name`、
`exclude.reason/summary`、`open_issue.kind/summary`、`next_question.text`

這些是顧問判斷本身,或是證據鏈與員工決策的必要輸入。

**B. 冗餘,可由 application 推導**

| 欄位 | 依據 |
|---|---|
| `task_change.target_task_ordinals` | `verifier.py` 的 `TARGET_ORDINALS_DISAGREE` **強制**它與 `identity.target_task_ordinals` 集合相等。模型填兩次,我們驗它們一樣——填一次即可 |
| `next_question.target.{kind, ordinal, index}` | 三個欄位表達單一件事(指向既有 issue 的 ordinal,或本次輸出的 index),可壓成一個帶前綴的識別 |
| `next_question.purpose` | 零消費者(判準 2) |
| `limitations` | 零消費者(判準 2) |

**C. 為未來付現在的成本**

`task_fields.context`、`deliverable_hint`、`success_criterion_hint` —— 只回流 packet(§4.2),
是 OPKS 階段的前哨欄位。判準 2 不過。爭議點:保留可讓後續階段有連續性;移除則需在 OPKS 開工時
以另一條路徑取得。**這是真取捨,不是純浪費,需在 plan 階段裁決。**

**D. 罕見路徑污染常見路徑(判準 4)**

| 結構 | 每回合固定代價 |
|---|---|
| `split_children[]` | 40 個葉子中的 9 個、17 個 union 中的 **8 個**、巢狀從 7 層推到 **9 層** |
| `supersedes_support_ordinals[]` | 一層物件陣列 |
| `resolves_open_issue_ordinal` | 一個 nullable union |

`split` 在單次訪談可能一次都不出現,但每一回合的 grammar 都背著它。

---

## 6. 選項

四個選項不互斥;A 是其他三個的前提。

### A. 純減重(零語意變更)

拿掉 schema 的 `title`／`description`;刪 B 類冗餘欄位;把 prompt 中與 verifier 重複的
散文壓成短提醒。

- 效果:schema −1,868、死欄位約 −200、prompt 約 −1,500 → **約 −3,500 bytes(−25%)**
- **不解決 union**(17 個中 8 個來自 `TaskFields`×2,減重動不到)
- 風險:低。P3 的證據支持刪重複規則不損品質,但我們沒有自己的 eval,**這是引用他人證據**

### B. Model-facing wire contract 與 domain model 分離

模型只輸出必須由它判斷的語意;ID、SupportLink、Proposal 包裝、lineage、authority 由 application 產生。
內部 domain model 維持豐富。

- 對應 S5(不送內部識別)與 P4(規則放進介面)
- 直接根治「Pydantic 直出把開發者註解漏給模型」這個機制,而非每次手動清理
- 代價:多一層 mapper 與其測試;mapper 必須是純轉換,否則會變成第二個語意來源

### C. 把罕見路徑移出常見 grammar

`split` 不在同一份 schema 表達;改為模型輸出 split 意圖 + 子項的最小語意,結構由 application 展開,
或改走第二次呼叫。

- 這是唯一能實質降低 union 與巢狀的手段(移除 `TaskFields` 的第二份 inline)
- S6 支持:split 是「cleanly decomposed fixed subtask」,且罕見,latency 代價只在罕見路徑付
- 代價:split 的產出品質不再與主判斷共享推理脈絡

### D. 放棄 strict,改 deterministic 驗證 + 重試

- S7 的 reporter 採用此法(prompt-based JSON),明說犧牲 guaranteed compliance
- 我們有 28 個 violation code 的 verifier,承受得住;但 ADR 0040 決定 26 明確選了 strict
- **此選項須開 ADR 才能採用**

---

## 7. 對 Probe U 的影響(結論改變)

前一份研究規劃了 Probe U(union-free、其他不變)以驗證 union 是否為綁定條件。§3 的兩項新事實改變了它的價值:

1. 官方明說「個別限制全部滿足仍可能被拒」,另有未公開的 grammar size 上限。
   因此 Probe U **通過**只證明「在當前 property/nesting 規模下 union 是綁定條件」,
   不證明未來的 schema 安全;Probe U **失敗**則證明還有其他綁定條件。
2. 選項 A + B + C 無論 Probe U 結果如何都會執行(減重與分離 wire contract 是被 P1–P5 獨立支持的,
   不是為了繞過 union 上限)。

**兩種結果都不改變下一步要做的事。** 依 P6 的「only when it demonstrably improves outcomes」,
建議取消 Probe U,把該次 live 驗證留給精簡後的真實 production schema——那一次的結果會直接決定成品能否上線。

此建議推翻本人前一輪「先做 Probe U」的規劃;依據是 §3 引用的 S4 兩句與 S7,均為前一輪未取得的資料。

---

## 8. 未決事項(需 plan 或 ADR)

- C 類欄位(`context`／`deliverable_hint`／`success_criterion_hint`)保留或移除,取決於 OPKS 階段的取得路徑。
- 選項 C 的具體形狀(同一次呼叫的扁平表達 vs. 第二次呼叫)。
- 瘦身後的目標餘裕(§3 說明不能瞄準剛好合規,但官方未公開真實上限,只能經驗地留大餘裕)。
- 我們沒有自己的 eval;§6 A 的「不損品質」目前引用 S2／S3 的他人證據。
  是否要建最小 eval 是獨立決策,**不在本研究範圍**。

---

## 附錄:量測方法

- instructions 逐段:以 `^## ` 切分 `TASK_ANALYSIS_INSTRUCTIONS`,UTF-8 位元組計。
- schema:`task_analysis_result_provider_schema()` 以 `json.dumps(separators=(",",":"),
  ensure_ascii=False)` 序列化(即 wire 形式,6,818 bytes;檔案含縮排為 11,890)。
- `title`／`description` 佔比:遞迴移除該鍵後重新序列化取差。
- 葉子欄位:先展開 `$ref`,再走訪 `properties`／`items`／`anyOf` 的非 null 分支。
- 消費者查核:`app/job_analysis/` 與 `apps/web/src/` 全文檢索。
