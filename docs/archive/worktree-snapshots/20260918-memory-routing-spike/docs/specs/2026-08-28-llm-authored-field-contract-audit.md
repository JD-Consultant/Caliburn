# LLM 應填欄位與 Tool Contract 審查

- 日期：2026-08-28
- 狀態：Owner 於 2026-08-28 接受方案 C；已成為 provider／Tool field contract 的目前基線，ADR 0071 仍維持 Proposed
- 範圍：主顧問輸出、Work Understanding、需要員工確認、JD 工作區、Skill receipt、來源引用與失敗修復
- 不在本輪：RAG、能力級別 A、完整 eval、production 實作
- 閱讀優先序：本研究針對「LLM 到底應填什麼」補正既有研究；若與 ADR 0071、2026-08-27 研究 §15.18 或 2026-08-28 舊實作計畫的 provider-wire 段落衝突，以本研究與後續同步段落為準，不能兩套一起施工。

## 0. 決策治理：可翻案，但不得擅自翻案

本研究中標示「Owner 已確認／已收斂」的內容是後續研究、設計與實作的**現行基準**，不是永遠不可改的真理。若新案例、官方資料、框架限制或實作證據顯示有更好方案，可以提出翻案；但任何研究者、agent、reviewer 或實作者都不得自行以「更主流」「框架原本這樣做」「舊程式較容易」為由改掉已確認方向。

翻案必須依序：

1. 指出要取代的具體既有裁決；
2. 提供新證據、真實失敗或產品需求衝突；
3. 說明維持原案與替代方案的效果、成本、複雜度及資料遷移影響；
4. 先和 Owner 討論並取得明確同意；
5. 再更新本研究／successor ADR／實作計畫，清楚標示被取代段落，之後才可施工。

未完成上述流程時，即使研究者個人認為另一方案較好，也只能提出問題與建議，不能把候選寫成已決定，更不能在 code 中先行翻案。反過來說，已確認方向也不得阻止發現問題；有較好證據時應主動提出討論。

## 1. 結論先行

現行問題不只是「欄位太多」，而是把四種不同責任塞進同一份模型表單：

1. LLM 才能判斷的職務語意；
2. application 已經知道的執行環境；
3. framework 執行後才知道的 receipt；
4. 員工才有權決定的審核狀態。

這會讓模型反覆抄 ID、猜 Skill、算字元位置、填無意義空字串，最後再由 mapper 用大量跨欄位條件拒絕。`strict` 只能保證 JSON 形狀與型別，不能讓模型知道它本來不知道的事，也不能保證職務語意正確。

本研究建議：

- 淘汰每輪固定輸出的 `ConsultantModelOutput` 巨型表單。
- 員工可見回覆使用普通 assistant message，不包進 structured output。
- Work Understanding 只在確有新增／修訂／退役時，以一個小型、原子、role／operation-specific 的 strict Tool 提交 semantic effects；Tool 成功後是否 continuation 依本輪是否立刻需要 canonical result 決定，不固定多一次模型呼叫。
- JD 繼續採可讀、可編輯的 VFS／editor Tool；但從每個 JD resource 移除 Evidence、`skill_ids`、重複 handle／kind 與預設排序等 application 可推導資料。
- Skill 是否載入、版本、run ID、revision、狀態、時間、token、diff、stale 判斷與 quote 位置全部由 framework／application 產生。
- 普通追問留在聊天文字；真的無法繼續時才呼叫小型「需要你的確認」Tool 並由 LangGraph interrupt 暫停。
- Pattern coverage 的「待補充／目前足夠」仍包含專業判斷；模型只在相關狀態需要改變時提交小型 recommendation，application 保存 basis-bound、可刪除重建的 projection cache，不再每輪填全域 sufficiency 表。
- 不用「零 union」當目標。應讓非法狀態在 Tool schema 中不可表示；只要控制 union site、branch 數與每個 branch 的欄位，會比一張所有欄位必填、靠空值模擬 optional 的表更可靠。

> **用語更正（2026-08-29）**：不能把驗收條件寫成「驗證模型沒有自行捏造 ID、版本或時間」，因為這會暗示這些欄位仍出現在模型 schema，只是期待模型不要亂填。正確規則是：**model-facing schema 根本不暴露 canonical ID、revision、timestamp、lifecycle、run／tool-call ID 等 application-known metadata**；framework／application 直接產生或透過 `ToolRuntime` 注入，Pydantic／strict schema 拒絕任何額外欄位。模型若要修訂既有內容，只能從 Context／read Tool 已提供的 model-safe handle 中選擇目標；application 以 read-set 解析該 handle 對應的 canonical ID 與 exact revision。這是「選取既有參照」，不是「由模型生成 ID」。

這不是照抄 Codex／Claude 的產品 UI，而是採用兩者共同的 harness 原則：模型只提出它能判斷的 semantic action；harness 執行、驗證、產生 receipt／diff／錯誤，再把高訊號結果交回模型。

## 2. 現況量測與已發生錯誤

### 2.1 現行 final structured output

`apps/api/app/consultant/model_output.py` 的根物件固定要求：

- `visible_reply`
- `analysis_bases`
- `reply_basis_ordinal`
- `understanding_changes`
- `attention_changes`
- `gaps`
- `question`
- `sufficiency`

本輪對 current code 量測：

| 指標 | Pydantic schema | LangChain provider-normalized schema |
|---|---:|---:|
| Schema 大小 | 8,211 bytes | 6,189 bytes |
| `$defs` | 15 | — |
| properties | 54 | 54 |
| required entries | 54 | 54 |
| `anyOf` sites | 0 | 0 |

`anyOf=0` 不是成功指標。現在用 `""`、`0`、`[]`、`"none"` 表示「不適用」，因此模型仍須填每個欄位，mapper 再拒絕互相矛盾的組合。例如：

- `question.kind=none`，卻仍要填七個其他 question 欄位；
- 新增 understanding 必須把 application-owned ID 填成空字串；
- 不同 question 類型共享彼此不適用的欄位；
- 每輪都要產生 sufficiency，即使該輪只是補一句工作事實；
- 每個 conclusion 經 ordinal 間接引用另一份 analysis basis，增加錯號、漏用與重複。

### 2.2 現行 JD VFS

每個 Duty／Task／OPKS JSON 還要求模型重填：

- path 已經表達的 `handle`；
- OPKS 目錄已經表達的 `kind`；
- 可由 append 預設得到的 `display_order`；
- `source_handle`、`quote`、`occurrence`、`skill_ids` Evidence；
- 部分同時出現在檔名、內容與 registry 的 identity。

這違反「application 已知資料不要再叫模型填」的基本原則。

### 2.3 已觀察的真實失敗

- `enabler_list` 被放到錯誤的 schema 分支；
- 模型計算中文字元 quote start／end 或 occurrence 錯誤；
- 模型自報了實際沒有載入的 Skill；
- 為了滿足 giant schema 而反覆 repair，增加延遲、token 與失敗機率；
- 嚴格 shape 驗證通過後，仍被 application 的跨欄位語意規則拒絕。

這些不是「模型不夠聰明」的單一問題；其中大半是 contract 把不該由模型承擔的責任交給模型。

## 3. 權威資料真正支持的原則

### 3.1 OpenAI／Codex

[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 明確建議：

- 用 enum／object structure 讓 invalid states 無法表示；
- 不要讓模型填 application 已知的參數；
- 總是連續發生的操作可由 application 合併；
- 起始可見 Tool 應保持小型，少用的 Tool 延後載入；Tool schema 會占 context 並計費。

[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 同時提醒：

- Structured Outputs 仍可能有內容錯誤；輸入不符合 schema 時，模型甚至可能為了填滿 schema 而幻覺；
- 遇到錯誤應簡化或拆分任務；
- 使用 Pydantic／Zod 作單一 schema source，避免程式型別與 JSON Schema 漂移；
- root 必須是 object，但 nested `anyOf` 是正式支援的 schema 形狀。

[OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch) 與 [Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/) 顯示的責任邊界是：

- 模型提出 create／update／delete 語意操作或 diff；
- harness 取得 call ID、執行、驗證路徑與套用結果；
- harness 回傳 completed／failed 與短錯誤；
- 模型根據 Tool result 繼續修正或產生普通文字回覆。

所以 `call_id`、執行狀態、套用成功與否、實際 diff、錯誤分類，都不是模型需要填的業務欄位。

### 3.2 Claude

[Claude Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) 說明 strict 透過 grammar constrained sampling 保證 schema 形狀；同頁也列出複雜度限制：每次最多 20 個 strict tools、24 個 optional parameters、16 個使用 `anyOf`／type array 的參數，且 nested／union／Tool 數會交互增加 grammar 成本。

這代表應控制 union，而不是把所有 union 消滅。把不適用欄位改成 required，再要求模型填假值，只適合「該值確實有合理預設」；不適合拿來混合 Case／Pattern／Unresolved、普通問題／阻塞問題等不同語意。

[Claude Define Tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools) 建議把密切相關操作合成較少的 Tool，避免 Tool selection ambiguity；Tool result 只回傳下一步需要的高訊號資料。

[Claude Text Editor](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool) 的 `str_replace` 讓模型提供 exact old text 與 new text，application 必須驗證 old text 恰好唯一匹配。這支持 Caliburn 保留「模型挑選逐字 quote」的語意責任，但 application 負責定位；模型不應計算 Unicode offset 或 occurrence ordinal。

### 3.3 LangChain／LangGraph

[LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools) 的 `ToolRuntime` 會自動注入 state、context、store、tool call ID 與 execution info，而且這些參數不會出現在送給模型的 Tool schema。這正適合承接：

- document／workspace／thread identity；
- expected revision／current source；
- loaded Skill receipt；
- run／attempt／tool call ID；
- 目前 pending workspace 與 approved baseline。

[LangChain Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) 原生支援 approve／edit／reject／respond 與 checkpoint resume；審核決定應由員工輸入與 framework state 保存，不是由模型產生狀態字串。

### 3.4 不能過度延伸的地方

官方資料佐證的是責任原則，不是 Caliburn 必須照搬某個 Tool 名稱或資料模型。Case／Pattern／Unresolved、Duty／Task／OPKS 與員工審核語意仍是 Caliburn 的職務分析 domain；框架只應承接通用 orchestration、durability、tool runtime、strict shape、editor、interrupt 與 receipt。

## 4. 欄位所有權規則

判斷一個欄位是否應由 LLM 填，只問四題：

1. 這個值是否需要職務語意判斷？若否，優先由程式處理。
2. application 在呼叫模型前是否已知道？若是，透過 `ToolRuntime` 注入。
3. 這個值是否只有執行後才知道？若是，由 framework 產生 receipt。
4. 這個值是否改變員工權威或審核狀態？若是，只能由員工 command 產生。

### 4.1 四方責任矩陣

| 所有者 | 應負責的欄位／行為 | 不應負責 |
|---|---|---|
| LLM | 工作語意、需要新增／修訂／退役的 semantic effect、精確原句片段、語意關聯、JD 實際文字、短理由、真正阻塞時的問題與選項 | Skill receipt、UUID／revision、狀態、時間、token、offset、diff、stale 判斷 |
| Framework | Tool call ID、實際 loaded Skills、run／model／provider／usage receipt、checkpoint／interrupt／resume | 職務內容真假、員工是否同意 |
| Application | stable IDs、revision、digest、source binding、quote 定位、default order、diff／dependency／stale／invariant、原子提交與 typed error | 猜員工工作、替員工核准 |
| 員工 | 接受／修改後接受／拒絕、直接編輯 JD、回答必要確認 | 填技術錯誤、驗證 Skill 是否真的載入 |

## 5. 現行主輸出逐欄審查

| 現行欄位 | 結論 | 新責任 |
|---|---|---|
| `visible_reply` | 移出 structured output | 普通 assistant message |
| `analysis_bases` | 淘汰 ordinal table |來源直接附於 Work Understanding semantic effect；JD 待審只引用 Work Understanding |
| `reply_basis_ordinal` | 移除 | 普通聊天不建立權威 provenance |
| `understanding_changes` | 保留目的、替換機制 | 小型 atomic Tool 的 `changes[]` |
| `attention_changes` | 淘汰舊 entity | Focus 是 runtime bookmark；真的變更才呼叫小型 focus command／Tool |
| `gaps` | 淘汰第二份 writer | 持久問題是 Work Understanding 的 Unresolved variant |
| `question` | 拆開 | 普通問題是聊天文字；阻塞問題才用「需要你的確認」Tool＋interrupt |
| `sufficiency` | 淘汰每輪全域表 | 按需 pattern-level coverage recommendation；application 驗 basis 並保存可重建 projection |

### 5.1 一律不得由模型填

- `skill_ids`、Skill version、Skill load success；
- model／provider／run／attempt／cost／token／timestamp；
- stable source UUID、understanding UUID、version UUID、document UUID；
- expected revision、digest、workspace／thread identity；
- tool call ID、status、pending／accepted／rejected／stale；
- quote start／end、Unicode offset、occurrence ordinal；
- before-state、semantic diff、dependency closure、read set、stale fingerprint；
- path 或 Tool action 已經表示的重複 `handle`／`kind`；
- 單純 append 可得到的 `display_order`；
- 為了滿足 schema 而出現的 `""`、`0`、空陣列、`"none"` dummy field。

### 5.2 可以由模型填，但只在需要時出現

- Work Understanding 的 Case／Pattern／Unresolved 語意內容；
- create／revise／retire 的 semantic intent 與既有 model-safe target handle；
- Case／Pattern 的逐字 employee quote；
- Pattern 支持的既有 Case handles；
- Unresolved 關聯的既有 understanding handles；
- Duty／Task／OPKS 的文字與真正的 domain relation；
- 待審 JD 變更的短理由與 1～N 筆 Work Understanding handles；
- 必要確認的問題、少量可選選項與相關理解 handles；
- Focus 真正需要改變時的簡短 label 與相關理解 handles。

### 5.3 現行 nested fields 的逐組去留

| 現行欄位群 | 欄位 | 處理 |
|---|---|---|
| Evidence | `source_handle` | current turn 由 runtime 注入；只有低頻舊來源 recall 路徑才讓模型選 model-safe handle |
| Evidence | `quote` | 保留給模型，因為選哪段原話支持哪個理解是語意判斷 |
| Evidence | `occurrence` | 移除；application exact match，重複就要求擴大 quote |
| Evidence | `skill_ids` | 移除；framework loaded-Skill receipt 是唯一事實 |
| Understanding | `operation` | 以 tagged action type 保留，例如 `create_case_from_current_source` |
| Understanding | `understanding_id` | create 不填；revise／retire 只選 model-safe target handle，application 解析 stable ID／revision |
| Understanding | `kind` | 移除自由文字；由 Case／Pattern／Unresolved variant 表達 |
| Understanding | `text` | 改名 `content`，保留完整職務語意，不拆回 JD-like facets |
| Understanding | `impact` | 從 provider wire 移除；若 UI／projection 真需要，應由 semantic change 與 dependency 推導，不讓模型自評技術影響 |
| Understanding | `work_ids` | 移除舊 Work entity 綁定；使用 role-specific `supported_by／about` understanding handles |
| Understanding | `basis_ordinal` | 移除；source quote 直接在該 effect 的 support variant 中 |
| Attention | `attention_id／kind／title／subject_id／reason／missing_before_enough／recommended_next_step／priority／disposition／make_current／basis_ordinal` | 整組退役；Focus 只在改變時提交 label＋相關理解 handles，其餘是 runtime／projection |
| Gap | `gap_id／reason／description／subject_kind／subject_id／blocks_dependent_analysis／basis_ordinal` | 整組退役；真正持久未知改成 Unresolved，validator／coverage signal 留在 application |
| Question | `text` | 普通問題移到 assistant text；阻塞問題才出現在 required-input Tool |
| Question | `choices` | 只在阻塞問題且選項真的有助澄清時出現；仍保留自訂回答 |
| Question | `answer_target／reason／current_understanding／affected_work_ids／affected_branch／basis_ordinal` | 從巨型輸出移除；必要的關聯只用 related understanding handles，runtime 保存 interrupt identity |
| Sufficiency | `currently_enough／reason／remaining_gap_reasons／continuing_benefit／basis_ordinal` | 淘汰這份全域物件；模型按需提交單一 Pattern 的 `label＋短理由＋basis handles`，application 驗 revision／矛盾並保存 projection cache |

這張表是「不重建舊名稱」的具體 gate。不能只把 `skill_ids` 刪掉，卻把相同責任改名成 `methods_used`、`evidence_method` 或 `analysis_receipt` 再交給模型。

## 6. Skill：模型可選擇，但不能自我作證

必須區分兩件事：

1. 模型依 catalog／description 判斷「現在需要載入 Task／Duty／O／P／K／S 哪個 Skill」；
2. framework 記錄「該 Skill 是否真的讀取成功、版本為何、何時載入」。

第一件是模型行為，第二件是 execution fact。現行 `PackageSkillBackend.loaded_skill_ids` 已經具備 receipt 雛形，因此所有 provider output、Workspace Evidence 與 JD resource 內的 model-authored `skill_ids` 都應移除。

若某種 document operation 有方法前提，application 只驗證「本 run 的真實 receipt 是否包含所需 Skill」，不能要求模型再填一次，也不能把自報欄位當證據。這不表示每筆 JD 欄位都能證明由哪個 Skill 推導；第一版只證明 run 中確實載入過必要方法，避免製造虛假精確度。

## 7. Source quote：保留語意選擇，移除位置計算

### 7.1 正常 current-turn 路徑

目前員工訊息的 source identity 已由 application 知道，因此透過 `ToolRuntime` 注入；模型只提供真正支持該 Work Understanding 的 exact quote。

Application：

1. 在 immutable employee source 內做 exact match；
2. 0 筆回 `quote_not_found`；
3. 1 筆建立 anchor；
4. 多筆回 `quote_not_unique`，要求模型擴大 quote 到唯一片段。

不做 trim、Unicode normalize、fuzzy match，也不要求模型算 index／occurrence。這能保留可追溯性，同時消除已實際發生的中文字元位置錯誤。

### 7.2 舊來源 recall 路徑

常見路徑不應每次要求模型重抄 current `source_handle`。若模型按需讀取舊來源並確實要建立漏掉的 Work Understanding，才動態提供可指定 `source_handle＋quote` 的 recall 版本；或先由 read Tool 回傳一個 application-safe source handle。這是低頻能力，不應增加每輪常駐欄位。

純粹的 Unresolved（「目前完全沒資料」）可以沒有 quote；不存在的資訊本來就無法引用原話。

## 8. 建議的 Work Understanding Tool contract

### 8.1 不採用的兩種方案

#### A. 保留 giant final output

淘汰。每輪被迫填 Reply、Understanding、Attention、Gap、Question、Sufficiency，與「先理解工作，必要時才編 JD」的大方向衝突。

#### B. 一個 flat effect，所有 relation 都 required，沒有資料填空陣列

淘汰。這是既有研究 §15.18 與舊實作計畫採用的方案，表面減少 `anyOf`，實際允許 Case 帶 Unresolved-only 欄位、retire 帶 content、create 帶假的 revision，再靠 mapper 拒絕。它把 schema complexity 轉成語意 repair，正好重現目前問題。

### 8.2 推薦方案 C：一個原子 Tool＋小型 tagged variants

> **後續閱讀警告（2026-08-29）**：下方 11 個 Case／Pattern／Unresolved branch 是 §15.21 重新審核三種語意責任前的歷史候選，**不可直接當 implementation schema**。仍有效的是「一個相關能力、原子 changeset、小型 discriminated variants、provider 不相容才用 role-specific Tool fallback」這四項機制；角色名稱、branch 數與 model-authored fields 必須以 [`2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md` §15.21.15～§15.21.16](2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md#152115-精確責任分工第一步id版本與時間不進模型-schema) 的最新討論為準。

概念形狀：

```json
{
  "changes": [
    {
      "type": "create_case_from_current_source",
      "content": "負責受理客戶回報並確認問題情境。",
      "quotes": ["客戶反映問題時，我會先確認是哪個功能出錯"]
    },
    {
      "type": "revise_pattern_from_cases",
      "target": "wu-pattern-004",
      "content": "持續診斷並協調處理產品使用問題。",
      "supported_by": ["wu-case-012"]
    }
  ]
}
```

root 保持 object；`changes.items` 使用 provider 支援的 nested union。每個 branch 只出現該 action 真正需要的欄位。依 ADR 0071 已收斂的 source invariant，第一個 provider candidate 應至少區分：

- `create_case_from_current_source(content, quotes)`
- `revise_case_from_current_source(target, content, quotes)`
- `create_pattern_from_current_source(content, quotes)`
- `revise_pattern_from_current_source(target, content, quotes)`
- `create_pattern_from_cases(content, supported_by)`
- `revise_pattern_from_cases(target, content, supported_by)`
- `create_unresolved_gap(content, about)`：純缺口，沒有假 quote；`about` 的 0～N 是真實 domain cardinality
- `revise_unresolved_gap(target, content, about)`
- `create_unresolved_conflict(content, quotes, about)`：已有互斥線索，必須保留 source quote 與受影響理解
- `revise_unresolved_conflict(target, content, quotes, about)`
- `retire(target)`

如果固定 transcript 證明 Pattern 必須同時保存 direct source 與 supporting Cases，應增加明確的 mixed-support variant，而不是讓所有 Pattern 永久填兩組可能為空的欄位。空 collection 只有在該 variant 的 domain cardinality 本來允許 0～N 時才合理；不能拿來假裝另一種 variant。

工具密切相關且需要同一 transaction，因此合為一個 atomic Tool；role／operation 又以 variant 排除非法組合，兼顧 Claude「減少 Tool selection ambiguity」與 OpenAI「invalid states unrepresentable」兩項原則。

上述 11 個 branches 仍只位於一個 nested union site，但 branch 數也會影響 grammar。實作時若實際 Claude／OpenAI provider preflight 顯示編譯過慢或不相容，fallback 是依當輪可用 role 動態曝光 2～4 個小型 role-specific Tools；不可退回 flat all-required dummy schema。這是 provider compatibility fallback，不是新增第二套 domain model。

Pydantic application model 是單一真相；provider adapter 只把同一型別轉成實際供應商支援的 nested `anyOf`／等價 shape。不可手工維護第二份 schema。由於 OpenAI、Claude 與 OpenRouter 的支援子集合不完全相同，施工前要用實際選定 provider 做小型 schema compile／parse preflight，不能只看本地 JSON Schema。

### 8.3 第一版避免 local refs

不要先讓模型替同輪新物件編 `u1／u2` 再互相引用。通常可以：

- 直接角色陳述建立 Pattern；或
- 先建立 Case，Tool 回傳 canonical handle；真的需要時，同一 agent run 再用該 handle 建立／修訂 Pattern。

只有真實 transcript 證明這造成大量額外 step 或品質下降，才考慮加入 local refs。先多一次「有依賴時才發生」的 Tool continuation，通常比每筆 change 永久多一組 local-ref 欄位可靠。

### 8.4 同一 product run 不固定增加 model step

本研究不推翻既有成本感知分流：

1. 模型可以在同一 provider response 中產生普通 assistant text block 與 understanding Tool call；
2. application 先暫存文字，不在 authority Tool 尚未成功時提前顯示成完成結果；
3. Tool 成功、且本輪不需要用新 canonical understanding 繼續改 JD：直接提交暫存文字並結束 product run，不固定再問模型一次；
4. Tool result 會影響同輪 JD edit／Pattern relation／required input：把 canonical handles 與高訊號 receipt 回給同一顧問，才 continuation；
5. Tool 可修復失敗：不顯示舊暫存文字，回 typed error 給同一顧問做一次 repair。

Anthropic 的 Tool response 原生可同時含 text 與 `tool_use` blocks；OpenAI Responses 也把 message／function call 視為 response items。LangChain Tool 可用 `return_direct`／graph routing 在不需後續推理時短路。具體 adapter 必須以實際 provider smoke 驗證「成功時不 continuation」的事件處理，不能假定所有供應商 SDK 的 stop semantics 完全相同。

### 8.5 目標 Tool surface 與載入時機

| 能力 | 是否常駐 | LLM semantic input |
|---|---|---|
| 普通員工回覆／追問 | 不用 Tool | assistant text |
| Work Understanding reconcile | 工作訪談時可用 | role／operation-specific changes |
| JD read／edit | 只有需要看或改 JD 時使用既有 VFS tools | path＋真正文件內容／exact replacement |
| Focus 更新 | 焦點確實改變時才可用 | label＋理解 handles |
| Pattern coverage | 正在評估該 Pattern 時才可用 | label＋理由＋basis handles |
| 需要你的確認 | blocking ambiguity 才可用 | question＋選項變體＋理解 handles |
| Skill | framework catalog／read 機制按需載入 | 模型選擇讀取；receipt 不在 semantic payload |

Tool description 先寫清楚「何時用／何時不用／參數語意」。只有真實 smoke 顯示某個 nested branch 反覆填錯，才放 1～3 個精簡正反例；不要替每個 action 堆一長串 few-shot，因為 Tool schema／description／examples 都會占每輪 context。若工具僅在某階段需要，以 LangChain dynamic tool filtering 或既有 Skill／VFS progressive disclosure 延後曝光。

## 9. JD VFS 欄位審查

VFS／editor 機制符合 Codex／Claude 的主流 harness 形狀，不需要改回巨大 JD 表單；需要縮減的是 resource content。

| Resource | LLM 應填 | Application 應推導／移除 |
|---|---|---|
| Header | 已知後才填的職稱、職業別等 domain 內容 | document ID、revision、狀態 |
| Duty | `statement` | path 已有的 `handle`、default `display_order`、Evidence |
| Task | `duty_handle`、Task domain fields、必要 enablers | path handle、default order、Evidence、stable IDs |
| OPKS | `text`、`task_handles`、K／S 必要時的 indicator relations | directory 已有的 `kind`、path handle、default order、Evidence |

排序不是永遠禁止模型處理；只有員工或語意確實要求 reorder 時，才曝光專用 reorder action。新增資料一律由 application append，避免每次寫檔都讓模型重算整份順序。

`statement` 與 `action／object／purpose_result` 是否屬重複 domain 表達，不能在本輪憑 schema 美化直接刪除；須另對照 Task 分析研究與匯出契約。這是剩餘 domain-field 審查，不是 execution metadata 問題。

### 9.1 待審 JD 的理由與 Work Understanding 引用

核准 JD 本體不保存 employee quote、Skill ID 或「為什麼這樣改」。待審變更仍需要：

- 短理由：LLM 用員工看得懂的話說明為什麼改；
- 1～N 個 Work Understanding handles：表示本次 JD 變更依據。

它們應位於 change-group／review metadata，不重複塞進每個 Duty／Task／OPKS JSON。application 從本輪實際 VFS mutations 產生 before／after diff、resource list、dependency component 與 stale fingerprint。

第一版可以一個 coherent edit wave 對應一個 review group；若同一 run 有明確可獨立接受的多組變更，才讓模型對每組提供一次 `reason＋understanding_handles`。模型不填 diff，也不把完整對話複製進理由。

## 10. Focus、coverage 與問題欄位

### 10.1 Focus

Focus 不是 Duty／Task ID，也不是一份可寫 Agenda。若本輪焦點沒有改，不輸出任何欄位；真的改變時才使用：

```text
set_focus(label, related_understanding_handles[])
```

Focus ID、時間、thread、resume state 由 runtime 產生。

### 10.2 Coverage／進度

不再要求模型每輪填整份 `sufficiency`。Coverage 含有「目前資訊是否足以解釋這個工作模式」的專業語意，不能只靠 record 數量或「沒有 Unresolved」由程式猜；同一主顧問只在評估相關 Pattern、選 Focus 或準備 JD 時，按需呼叫小型 `set_pattern_coverage(pattern_handle, label, reason, basis_handles)`。Application 驗證 exact basis revision、blocking contradiction 與 required input，再保存可刪除重建的 cache；相關理解 revision 改變就 stale。百分比、confidence、全域完成狀態與每輪固定說明都不進 model wire。

### 10.3 問題

- 普通訪談追問：普通 assistant text，員工可回答別的內容或下次再繼續。
- 「需要你的確認」：只有多種合理理解且不回答就會錯誤更新工作理解／JD 時，才呼叫小型 strict Tool。為避免 optional／空陣列，再分成 `request_confirmation_with_choices(question, choices, related_understanding_handles)` 與 `request_confirmation_open(question, related_understanding_handles)` 兩個變體；前者提供 2～4 個誠實選項且仍允許自訂回答，後者只要求必填自由文字。依 ADR 0071，本輪先保存 1～N 筆相關 Work Understanding，再由 LangGraph interrupt 暫停。
- schema／quote／Skill／provider 錯誤：絕不轉成員工必答問題，由 application 對模型回 typed error 或終止本輪並解鎖。

## 11. 失敗與 retry 政策

### 11.1 三層驗證

1. Provider strict：JSON shape、required、enum、type、`additionalProperties`。
2. Application deterministic：handle 存在、exact quote 唯一、revision、role relation、JD invariant、atomicity。
3. 員工 authority：接受、修改後接受、拒絕。

三層不能互相假裝。Strict 通過不代表語意正確；員工也不負責修 schema error。

### 11.2 Tool error 只回高訊號

每次最多回少量 typed diagnostics，例如：

```json
{
  "status": "repairable_error",
  "errors": [
    {
      "code": "quote_not_unique",
      "target": "changes[1].quotes[0]",
      "message": "這段文字在 source 中出現 2 次；請擴大逐字引用範圍。"
    }
  ]
}
```

不把完整 JSON Schema、traceback、所有 context 或內部 DB 資料回灌模型。

### 11.3 有界修復

- provider transient failure 與 model semantic repair 分開計數；
- 同一 authority stage 最多一次 validation-driven repair；
- 第二次仍失敗就 rollback、解鎖聊天與 JD，顯示可理解的重試訊息；
- 不為了讓失敗「看起來成功」而 fuzzy match quote、忽略 stale 或自行補 Skill。

Schema 縮減應先於增加 retry；否則只是花更多 token 重做同一張錯誤表單。

### 11.4 OpenRouter 不得靜默降級 strict

OpenRouter 官方指出 Structured Outputs 是 endpoint-level 能力，同一模型的不同 provider endpoint 支援可能不同，而且某些 endpoint 只把 schema 當強提示。Production adapter 必須：

- 設 `provider.require_parameters=true`，只路由到支援本次參數的 endpoint；
- 啟動／設定時確認目標 model endpoint 宣告 `structured_outputs`／strict 能力；
- 對實際 Tool schema 做 parse preflight；
- 不支援時明確 fail configuration 或改走已驗證 endpoint，不能悄悄降成 prompt-only JSON 再增加 repair。

Response healing 只能處理非 strict endpoint 的 JSON 格式瑕疵，不能修復錯誤 Skill、quote、relation 或職務語意，因此不作本設計的正確性基礎。

## 12. 與現行文件衝突、同步清單

Owner 已接受本研究；文件同步至少包含以下內容：

1. ADR 0071 已把舊的扁平 wire／空陣列 sentinel 改為 atomic tagged variants；
2. ADR 0071 與研究稿中的 model-authored `occurrence` 改為 application exact-match／要求擴大 quote；
3. 2026-08-27 研究 §15.18 的 flat wire 結論標成被 successor section 取代；
4. 2026-08-28 實作計畫中 `ConsultantModelOutput` 固定 root fields、`source_basis_ordinal`、local refs、all-required dummy fields 全部重寫；
5. `docs/design/consultant-runtime.md` 與 production workspace schema 中 JD Evidence／model-authored Skill 說明移除；
6. 保留 framework execution receipt，但不要把 receipt 又映回模型要填的 business payload。

不能只刪 `skill_ids` 一個欄位就施工；否則 giant output、occurrence、ordinal basis、Attention／Gap／Sufficiency 的同類錯誤仍然存在。

## 13. 實作前最小驗收條件

這不是完整 eval；只做防止 contract 細節再次做錯的便宜 gate：

- provider schema 中不存在 `skill_ids`、stable UUID、revision、digest、quote offset／occurrence；
- 普通文字回覆不需要填 structured root；
- Work Understanding 每個 variant 只含合法欄位，不使用 dummy sentinel；
- 實際 OpenRouter 目標 provider 都能 compile／parse 同一小型 fixture；
- current-turn source 由 runtime 注入；quote duplicate 以擴大 quote 修復；
- Tool receipt 能證明實際 loaded Skills，模型不能偽造；
- JD resource 不重複 path 已知 handle／kind，不帶 Evidence／Skill；
- application 能從 VFS mutation 產生 diff，模型不填 before／after／stale metadata；
- 一次 repair 後仍失敗會 rollback 並解鎖，不讓 UI 永久卡住；
- 使用一份 Pydantic authoritative type 產生 schema 與本地 validation，CI 防止 provider schema 漂移。

## 14. Owner 裁決與下一輪待審

Owner 於 2026-08-28 接受方案 C：

> 普通 assistant text ＋一個原子 Work Understanding Tool（小型 tagged variants）＋既有 JD VFS editor ＋少量按需 Focus／required-input Tool；framework／application 負責所有 execution metadata 與 receipt。

因此正式推翻舊的 flat all-required wire、固定 `ConsultantModelOutput` 根表單、model-authored occurrence／Skill receipt 與 dummy sentinel。這是目前可推翻的施工基線；只有實際 provider preflight、固定 transcript 或產品證據顯示不可行，才重開方案比較。

下一輪仍須審清楚，但不需要重新討論本節已決事項：

1. **JD 領域語意欄位**：Header／Duty／Task／OPKS 中哪些內容真的要由模型判斷，哪些可由 application／export 推導；特別是 Task `statement` 與 `action／object／purpose_result` 是否重複、哪些欄位可選，以及一個 Task 多筆 O／P／K／S 的最小寫入形狀。
2. **審核群組 metadata**：短理由與 1～N 筆 Work Understanding basis 應只存在 semantic change group 一次，不得在每個 VFS resource 重複；group boundary 仍須用既有 atomic-review 需求逐例驗證。
3. **實際 provider preflight**：用 authoritative Pydantic types 產生 tagged Tool schema，對正式 OpenRouter endpoint 驗證 compile／parse／strict routing；這是技術驗證，不是要求 Owner 再選一次產品流程。
4. **實作計畫重寫**：舊計畫仍含被推翻的欄位範例，必須先依本研究完整重寫並複審，才可開始 production。

## 15. 主要官方來源

- [OpenAI — Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI — Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)
- [OpenAI — Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
- [OpenAI Codex — Skill Creator source](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md)
- [OpenAI Codex — App Server](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [Anthropic — Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic — Strict Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
- [Anthropic — Define Tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Anthropic — Text Editor Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)
- [Anthropic — Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [LangChain — Tools／ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — Structured Output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [OpenRouter — Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
- [OpenRouter — Provider Selection](https://openrouter.ai/docs/guides/routing/provider-selection)

## 16. JD 領域欄位、原子編輯與審核分組後續研究

本節處理 §14 尚未收斂的前三項問題。結論仍是**可推翻的研究建議**，不是已核准 ADR，也不是 production 實作指令。若後續 provider preflight、固定訪談案例或 UI 實測顯示效果較差，應回到本節重選方案，而不是為了保住既有類別名稱繼續補欄位。

### 16.1 官方資料實際支持什麼

#### Task 是一個可讀的工作陳述，不是五份彼此獨立的真相

[O*NET Task Statement Components](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf) 把 Action、Object、Purpose／Result、Enabler、Context 定義為一段 Task statement 的**組成部分**；其中 Purpose／Result 可以隱含，Context 在 Task statement 中通常很少出現，Enabler 又可能包含工具、方法、Knowledge 與 Skill。[O*NET 2025 Emerging Tasks 技術報告](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf) 也描述分析員如何利用這些部分起草、修訂一段簡潔、可理解、避免 double-barreled 的 Task statement，而不是把五個部分都發布成五個必要欄位。現行 [O*NET 31.0 Task Statements data dictionary](https://www.onetcenter.org/dictionary/31.0/json/task_statements.html) 對外仍以單一 `task` 文字欄位保存正式 Task statement。

[U.S. OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 要求研究 Task、competency／KSA 以及兩者的關聯，但沒有要求把 Action／Object／Purpose 各自保存成公開 JD 權威欄位。這支持 Caliburn 保留 Task ↔ OPKS 關聯，同時把 Task components 當成分析與品質檢查方法。

本 repo 的 production code 又提供第二組證據：`ApprovedTask` 與 VFS Task resource 同時保存 `statement`、`action`、`object`、`purpose_result`、`context`、`enablers`，但 deterministic export 目前只讀 `task.statement`；`enablers` 還與獨立 OPKS 內容部分重疊。這表示現況很容易出現兩段文字不同步，卻沒有 downstream consumer 能判斷哪一段才是真實 JD。

因此目前較強的推論是：

- Action／Object／Purpose／Context 是 Task Skill 用來理解、起草、拆分與驗證 Task 的 rubric；
- 詳細工作事實留在 Work Understanding；
- 正式 JD 保存一段 canonical Task statement；
- OPKS 保存為獨立、可多筆、可關聯的正式內容；
- 只有確實具有產品用途、且不與 statement 重複的工作屬性，才另列 JD 欄位。

這是從官方標準與本地 consumer 共同推出的設計判斷，不是 O*NET 或 OPM 直接規定 Caliburn 的資料模型。

#### 模型只填語意；harness 負責執行資訊

[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 明確建議讓 invalid states 無法表示、不要讓模型填 application 已知的參數，並把永遠連續執行的操作合併；同頁也只把「起始時少於 20 個 Tool」當軟性目標，罕用工具應延後載入。[OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch) 的角色分工是模型提出小型結構化 diff，harness 套用、驗證並回報 typed result。

[Anthropic Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works) 同樣把 Tool 定義成模型與 application 的契約：模型提出 structured request，application 執行並回傳結果；官方 [Text Editor Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool) 以 view／create／exact `str_replace`／insert 讓模型編輯文字，找不到或多重匹配由 executor 回錯，而不是讓模型填 revision、offset、receipt 或 rollback metadata。

[LangChain ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools) 可把 state、context、store、thread／run 等 runtime 資料注入 Tool，而且不出現在給模型的 schema；[Deep Agents backends](https://docs.langchain.com/oss/python/deepagents/backends) 已提供 `ls`、`read_file`、`write_file`、`edit_file`、`grep` 等 VFS surface，並允許以 Postgres 等 custom backend 投影。這支持沿用成熟框架 VFS，而不是重新發明整套檔案工具；Caliburn 只需補上框架不理解的 domain transaction 與 authority 規則。

### 16.2 Task 欄位三個可推翻方案

#### 方案 A：保留所有既有拆解欄位

權威 Task 同時保存 statement、action、object、purpose、context、frequency、responsibility、enablers。

優點是查詢細；缺點是同一語意有多份可漂移的真相、模型必須填更多 optional 欄位、Enabler 與 OPKS 重複，而且現行匯出沒有消費大部分欄位。這正是本次 schema error 與修復成本的來源之一，**目前不推薦**。

#### 方案 B：正式 Task 只保存 statement

優點是最接近 O*NET 對外 Task statement、schema 最小且不會漂移；缺點是 Caliburn 已討論過希望在內部 JD 顯示頻率與責任角色，全部刪除會犧牲明確的產品用途。

#### 方案 C：canonical statement＋少量非重複屬性（目前推薦）

此處的「正式 Task」是指 **Caliburn 內部 JD authority 中，員工可查看、可編輯，且 AI 變更經員工接受後成立的 Task 資料**。它不是指公版匯出一定要新增三個獨立欄位。AI working copy／待審變更與已核准 JD 使用同一份 Task 語意形狀；兩者差別是 authority／review 狀態，不是兩套 Task schema。

第一版內部 JD Task 只由模型判斷：

- `statement`：員工看得懂的一段 canonical Task；
- `frequency_text`：可選，只有訪談確實得到頻率時填；
- `responsibility_role`：可選，只有產品確實需要區分主責／協作等角色時填；
- `duty_handle`：可為空；Task 尚未能合理分組時進未歸類區。

Action／Object／Purpose／Context 不再是獨立 JD authority fields，由 Task Skill 在 Work Understanding 上分析並用來形成／檢查 statement。`enablers` 不再與 OPKS 雙寫；工具、方法、知識與技能若只是訪談細節留在 Work Understanding，確定要成為 JD 內容時寫成 O／P／K／S。

`frequency_text` 與 `responsibility_role` 是 Caliburn 的產品選擇，不是 O*NET 強制；若後續 UI／匯出證明沒有用途，也可再刪。此方案在「效果、可讀性、模型可靠度、維護成本」間最平衡。

三個層次必須分清楚：

1. **內部 JD authority**：Task 保存 `statement`，以及有資料時才保存 `frequency_text`／`responsibility_role`；員工可直接編輯。
2. **AI 待審 working copy**：使用相同欄位；AI 新增或修改的值顯示 semantic diff，員工接受後才進 authority。員工修改綠色內容不會自動接受，仍需整組裁決。
3. **匯出 projection**：維持既有 deterministic export 規則；本裁決不等於立刻增加「頻率」或「責任角色」公版欄位。日後若要呈現在特定匯出模板，再由 export adapter 決定獨立欄、合成文字或不輸出，不回頭污染 JD／Work Understanding 的權威邊界。

### 16.3 Duty／Task／OPKS 的最小模型輸入

在方案 C 下，模型真正需要提供的 JD 內容可縮成：

| Resource | 模型提供 | Application／framework 提供 |
|---|---|---|
| Duty | statement | stable ID、path handle、order、revision |
| Task | statement、可選 frequency／responsibility、可空 Duty relation | stable ID、預設 order、revision |
| O／P | text、恰好一個 Task relation | stable ID、kind（由 path／Tool variant 知道）、order |
| K／S | text、至少一個 Task relation | stable ID、去重、order、各 Task 下的 UI projection |
| A／能力級別 | 第一版不讓 LLM 產生 | 待研究 Skill 完成後再開 |

一個 Task 可有多筆 O、P、K、S。K／S 是 canonical shared resource，可連多個 Task；UI 可在每個 Task 下投影，但不能複製成多份權威文字。第一版不要求模型同時填「直接 Task relation」與「經 P 推導的第二套 relation」；若 export 需要 P 關係，應由 application 根據已核准的 Task／P 關聯推導，或等真實案例證明不能推導時再增加語意欄位。

### 16.4 編輯 Tool 三個方案

#### 方案 A：只保留原始 VFS write／edit／delete

框架程度最高、程式最少，但 current resource JSON 仍會迫使模型填 handle、kind、Evidence、Skill、order 等重複資訊，而且一次跨多檔的拆分／搬移缺少清楚的 transaction boundary。

#### 方案 B：每個 domain 動作一個 Tool

例如 `add_task`、`rename_task`、`move_task`、`split_task`、`merge_task`、`add_knowledge`。它能把規則寫得很死，但 Tool 數量與 selection ambiguity 會快速增加；也把「拆分」誤當獨立資料模型，而非新增／修改／刪除的組合，與已確認的編輯器概念衝突。

#### 方案 C：成熟 VFS＋一個小型原子 edit group（目前推薦）

保留 Deep Agents 的 read／list／grep 與 custom database backend；另用一個薄的 domain Tool 包住三種低階 operation：

```text
edit_jd_group(
  reason,
  understanding_handles[1..N],
  operations[
    create(path, content)
    exact_replace(path, old_text, new_text)
    delete(path)
  ]
)
```

這不是讓模型填整份 JSON Patch，也不是新增 `split_task`／`merge_duty` 等業務 Tool。它只提供成熟編輯器共同的 create／replace／delete primitives，並加上 Caliburn 必要的一次原子提交邊界：

- 改名：一個 exact replace；
- 搬移 Task：修改 relation；UI 由 diff 顯示從舊 Duty 移出、向新 Duty 移入；
- 拆分 Task：同組 create 兩個 Task、重連 OPKS、delete 原 Task；
- 合併 Task：同組 create／replace 合併結果、重連 OPKS、delete 舊 Task；
- 新增一整組 Task＋OPKS：同一 group 內建立多個 resource；
- 刪除 Duty／Task但保留子項：同組先解除／重連子項再 delete；
- 明確連子項一起刪除：同組列出所有 delete。Application 可從 operation composition 判斷是 preserve 還是 cascade，不要求模型再填一個重複的「刪除模式」。

Tool schema 只有一個 nested tagged union、三個 branch；path 已經表示 resource kind／local handle，content 不再重複 handle、kind、ID、order、Evidence、Skill。Application 依 ToolRuntime 注入 document／thread／revision，分配 stable ID 與 append order，按順序在暫存 working copy 套用全部 operation，任一失敗就整組 rollback，再產生 compact receipt。

這比直接綁 OpenAI `apply_patch` 更適合本產品：OpenAI 的 Tool 是很好的 harness 參考，但 Caliburn 要能替換 OpenAI／Claude／其他 OpenRouter provider；Deep Agents VFS 與自訂 Pydantic Tool 能保留 provider neutrality。

### 16.5 審核群組不應由欄位數決定

[VS Code 最新 Agent Host review](https://code.visualstudio.com/docs/agents/run/review-code-edits) 顯示 Agent 可直接更新隔離工作區，再由使用者在 diff、checkpoint、commit／merge／discard 邊界審查；同頁也保留較舊 extension-host 的 per-change Keep／Undo。這證明成熟工具並沒有唯一固定的 approval 粒度，粒度取決於 harness 與整合邊界。[GitHub suggested changes](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/incorporating-feedback-in-your-pull-request) 也同時允許單筆套用與把多筆建議組成 batch。

Caliburn 不是程式碼 IDE，核准會改正式 JD authority，因此建議：

1. 一個 `edit_jd_group` Tool call 表示一個員工可獨立裁決的語意決定；
2. application 先依 operation 實際結果算 semantic diff，再把同一 entity 的關聯欄位與必要 dependency closure 擴成最小安全群組；
3. `reason＋1..N Work Understanding handles` 只存在群組一次；模型不填 before／after、digest、stale、action IDs；
4. UI 讓員工編輯綠色 working content，但編輯不等於接受；整組仍明確接受或拒絕；
5. 接受後正式 JD 不保存 AI 理由與 Work Understanding 引用；拒絕整組回退，拒絕理由不必填；
6. 員工自己直接編輯正式 JD 是 deterministic authority command，不需要偽造 AI 理由或來源。

[LangChain Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) 提供 approve／edit／reject／respond 與 durable interrupt，可承擔暫停與恢復的通用機制；但它預設是在 Tool 執行前審核每個 call。Caliburn 的產品需求是 AI 先更新可持久化 working copy、員工稍後在 semantic diff 審核，因此不應直接把 generic HITL middleware 當完整 review domain。框架負責 durability／resume，application 保留最薄的 semantic group 與 authority commit 規則。

### 16.6 Partial update、刪除與 stale 防護

[Google AIP-134](https://google.aip.dev/134) 建議以 partial update／field mask 更新資源，並指出 full replacement 可能在新增欄位後意外清掉客戶端不知道的資料；需要避免競態時可使用 server-computed etag。[Google AIP-135](https://google.aip.dev/135) 則要求父資源仍有子項時預設拒絕刪除，只有明確 opt in 才 cascade。這支持：

- 模型以 exact replace／小型 create／delete 修改目前 working copy，不每輪覆寫整份 JD；
- revision／stale token 由 application 注入及驗證；
- 保留子項是預設安全路徑；cascade 必須由實際 operation 清楚列出，UI 對高影響群組再確認；
- application 回傳 fully validated current projection，Web 不自行拼出 authority state。

### 16.7 本輪建議與仍待 Owner 裁決

目前最佳候選是：

> **Task 採方案 C（canonical statement＋可選 frequency／responsibility）；編輯採方案 C（Deep Agents VFS＋一個原子 edit group）；審核群組以 Tool call 的語意邊界起始，再由 application 擴成最小 dependency closure。**

它保留已研究過的 Task／Duty／OPKS 分析方法與員工 authority，替換掉的是重複欄位、巨型 DTO 與自製 file-operation plumbing。它也明確推翻 2026-08-27 研究中「工作細節至少要把 action／object／purpose／context／enablers 都做成 JD 欄位」的暫定寫法；那些內容改由 Work Understanding＋Task Skill 保存與使用。

**歷史裁決，已被 §17 新方向暫停，不得作為 implementation baseline：**Owner 曾於 2026-08-28 同意第一版內部 JD Task 採 `statement＋可選 frequency_text＋可選 responsibility_role`。其中 `statement` 是 canonical Task 內容；後兩者是有訪談依據時才存在的獨立工作屬性，不得為了填滿 schema 推測或產生空字串。Action／Object／Purpose／Context／Enabler 留在 Work Understanding 與 Task Skill 分析，不再建立第二份 JD 權威文字。

當時預定依此建立 authoritative Pydantic candidate 並做 provider preflight；§17 已明確停止這個施工順序。現在必須先完成「職務說明書本體有哪些成品欄位」的研究與 Owner 裁決，才能重開 schema／preflight。

## 17. 新方向：畫面與匯出共用「成品 JD」語意模型

### 17.1 狀態與取代範圍

Owner 於 2026-08-28 提出更高層的新方向：

> Work Understanding 保存對員工工作的完整、細節化、可反覆修訂理解；JD 不必重複保存所有分析細節。先研究一份高品質、適合 Caliburn 產品目的的「成品職務說明書」應包含哪些內容，再讓 Web 編輯畫面與實際匯出共用這份成品模型。

這個方向**暫停 §16.7 的立即施工結論**。`statement＋frequency_text＋responsibility_role` 不再視為已可直接寫入 production 的固定 Task schema；`frequency_text`／`responsibility_role` 只有在後續成品 JD 研究證明它們應出現在最終文件時才保留。這不是否定上一輪研究，而是依 Owner 明確允許「已討論結論可被更好方案推翻」後，提升設計問題的層級。

### 17.2 三個權威物件，不建立影子 JD

新方向的邊界是：

1. **Work Understanding**：給主顧問長期使用的完整工作知識。保存 Case／Pattern、成立內容、待釐清、修訂 lineage 與逐字來源；可比最終 JD 詳細很多，不因 JD 為了可讀性而濃縮就遺失細節。
2. **成品 JD semantic document**：員工真正要查看、編輯、核准與匯出的職務說明書內容。只放成品需要的欄位，不把分析中間件、quote、Skill receipt 或未用於成品的拆解欄位塞進來。
3. **System／review metadata**：stable ID、relation、order、revision、pending group、diff、stale、digest、來源 handle 等應用程式資料。它們支援編輯與審核，但不是成品 JD 欄位，也不要求出現在匯出文件。

Web 與匯出不必 pixel-identical：Web 可以用 Duty → Task → OPKS 階層、摺疊、工作地圖、紅綠 diff 與接受／拒絕控制；XLSX／DOCX／PDF 可以改用適合列印的表格或章節。但是兩者必須**語意同源**：

- 成品有的內容，Web 能看到與編輯；
- Web 中屬於 JD 的內容，匯出不能悄悄忽略；
- 同一欄位不能在 UI schema 與 export schema 各保存一份；
- UI-only 的操作狀態與 system metadata 不算 JD 內容，可不匯出。

AI pending working copy 也使用同一份成品 JD schema，只在上面疊加 review metadata。AI 與員工仍編輯同一份目前文件；接受／拒絕決定的是 pending diff 是否進入核准 authority，不建立「內部 JD」與「匯出 JD」兩份互相同步的文件。

### 17.3 官方資料帶來的修正

[U.S. OPM USA Class — Editing an AI generated duty statement](https://support-class-usadata.opm.gov/hc/en-us/articles/51122999688595-Editing-an-AI-generated-duty-statement) 允許使用者直接編輯 AI 生成的 duty statement；其 [Preview & Submit](https://support-class-usadata.opm.gov/hc/en-us/articles/51137958252307-Major-Duties-Preview-Submit-Overview) 再預覽同一批內容並匯出 Word。這是「編輯畫面與匯出共用同一語意成品」的近期官方實例，雖然 Caliburn 不照抄其欄位或審核流程。

[SHRM 2026 job-description guide](https://www.shrm.org/in/topics-tools/news/blogs/beginners-guide-clear-effective-job-description) 把職稱、部門／報告關係、職務摘要、主要責任、skills／qualifications、工作地點／型態等列為常見結構，但它主要服務招聘；薪資、福利、成長機會等 job-ad 欄位不能直接搬進 Caliburn 的員工職務分析成品。[CIPD Job Design 2025](https://www.cipd.org/en/knowledge/factsheets/job-design-factsheet/) 則強調角色、責任、工作流程、價值與工作品質，提醒 JD 不只是招聘廣告。

[OPM 2026 Competency-Based Classification Policy](https://www.opm.gov/policy-data-oversight/classification-qualifications/competency-based-policy/) 代表近期 skills-based 趨勢：實際工作與可觀察 competency 要有關聯，並能隨技術與任務演變更新。[OPM Major Duties](https://support-class-usadata.opm.gov/hc/en-us/articles/51115834989843-Major-Duties-Statements-Overview) 又把 recurring、significant work 寫成 major duties，並把 time allocation 放在 Duty 層，而非強迫每個 Task 填固定頻率。這使上一輪的 per-Task `frequency_text` 必須重新比較，不能因現行 schema 已有就保留。

[EEOC essential-functions guidance](https://www.eeoc.gov/publications/ada-your-responsibilities-employer) 把實際員工經驗、花費時間與不執行的後果視為判斷 essential function 的證據。這支持 Work Understanding 保存頻率、時間與影響等細節，但不等於每一項都必須成為 JD 顯示欄位；是否呈現要依 Caliburn 成品目的與適用法域另行決定。

[UK National Archives job-description guidance](https://www.nationalarchives.gov.uk/archives-sector/advice-and-guidance/running-your-organisation/writing-a-job-description/putting-a-job-description-together/) 也指出 JD 應清楚、簡潔、描述主要工作範圍，而不是列出任職者可能做過的每一項細節。這與「完整工作理解 → 萃取成品 JD」的產品方向一致。

### 17.4 「完美滿分」不是欄位最多

不存在脫離用途、產業與法域的唯一滿分 JD。Caliburn 應先定義成品的 primary purpose，再以幾個品質標準評分：

- 是否讓員工與閱讀者清楚理解此職位為何存在、負責哪些 recurring／significant work；
- Duty／Task 是否完整涵蓋工作，又沒有把單一案例、工具步驟或重複事項當成職務本體；
- 預期產出／成果與必要 Knowledge／Skill 是否能連回實際工作；
- 欄位是否都能由訪談與 Work Understanding 支持，而不是為了模板完整而猜測；
- 語言是否簡潔、可讀、可維護，工作改變後能局部更新；
- 是否把招聘廣告、薪酬福利、個人履歷或內部推理錯放進職務說明書。

因此下一輪不是先問「要不要 frequency 欄」，而是先比較 2～3 種成品架構，再從成品用途反推每個欄位。

### 17.5 下一輪研究範圍

後續要以本產品「員工訪談後產生專業職務說明書」為核心，逐項研究並討論：

1. 文件表頭／職位識別：職稱、職務目的、組織位置／報告關係哪些是核心、可選或超出員工 authority；
2. 主體：Duty、Task、主要責任、預期成果要如何分層，避免 Duty／Task 只是兩層重複句子；
3. OPKS：哪些應直接出現在成品、如何與 Task 關聯、是否需要集中區與 Task 內 projection；
4. 工作屬性：頻率、責任角色、重要性、工作情境、協作關係、essentiality 哪些只留 Work Understanding，哪些能提升成品；
5. 招聘／person specification 欄位：學歷、年資、證照、薪資、工作地點等是否屬本產品第一版，不能因一般 job ad 常見就自動加入；
6. 版面：先建立 semantic document，再分別設計互動 Web 與 deterministic export renderer；
7. 以不同型態職務做少量代表案例檢查，不做完整 eval，但要防止只適合辦公室知識工作。

完成這個成品模型裁決前，不建立新的 Pydantic JD candidate、不做 provider schema preflight，也不依 §16.7 移除或新增 production 欄位。

### 17.6 多用途不等於一份超大型文件

Owner 進一步確認，Caliburn 的產出未來要能支援多種用途：招募與甄選、績效考核／KPI、內部訓練，以及其他人力資源用途。產品權威順序是 **Work Understanding → 職務說明書 → 招募／KPI／訓練**。官方與大型 HCM 產品的共同方向支持「一份可重用的核心職務說明書，多個 purpose-specific projection」，而不是每個用途各自維護一份職務真相，也不是把所有用途的欄位都塞進同一張超大型 JD。

- [OPM — What is a job analysis?](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/what-is-a-job-analysis/) 明確表示同一份 Task＋competency job-analysis data 可支援 recruitment、selection、performance management、career development、promotion 與 employee development。
- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 也把 Task、competency 與兩者關聯視為共同基礎，再用於 training needs、classification、promotion 與 performance appraisal。
- [SAP SuccessFactors Job Profile Builder](https://help.sap.com/docs/SAP_SUCCESSFACTORS_PLATFORM/6653514fe7d84eca8e9bc2d38e46666d/what-is-job-profile-builder) 以可組合 content types 建立完整 Job Profile，再用 established role 建 performance profile、職位匹配與發展用途；不是把每個 downstream form 當另一份 job truth。
- [Oracle HCM Profile Management](https://docs.oracle.com/en/cloud/saas/human-resources/faucf/overview-of-profile-management.html) 讓 job／position profile 的 skills、competencies、qualifications 被 recruitment、performance、training-needs 與 career planning 重用。
- [Oracle Job Skills Enrichment](https://docs.oracle.com/en/cloud/saas/readiness/hcm/25a/lear-25a/25A-learning-wn-f35717.htm) 的 AI skill suggestions 以 pending／Needs Review 進入 Job Profile，核准後才供 skill gap 與 learning recommendation 使用，也佐證 AI 建議與跨用途權威 profile 應分開。

依此研究，Caliburn 的候選整體形狀改為：

```text
員工訪談／來源
        ↓
Work Understanding（完整、細節、可修訂的工作知識）
        ↓
職務說明書（經員工核准的唯一核心成品）
        ├─ 招募／甄選 projection
        ├─ 績效／KPI setup projection
        └─ 訓練／發展 projection
```

`Job Profile` 只可作為 SAP／Oracle 等外部框架或產品資料結構的參考名詞；Caliburn 不在職務說明書上方或旁邊另建一份名為 Job Profile 的第二權威。Web 主要編輯與預設匯出的就是職務說明書本身。

各 projection 只能重用 core 已核准的職務事實；用途特有資料則由該用途自己的 authority 補入，不得倒灌成 AI 猜測的職務事實：

| 用途 | 可從職務說明書重用 | 仍需額外 authority／資料 |
|---|---|---|
| 核心 JD | 職務目的、Duty／Task、產出／績效指標、K／S、必要工作情境 | 組織核定欄位、簽核／版本資訊 |
| 招募／甄選 | 主要工作、必要 K／S、工作條件 | 必要／加分條件裁決、學歷／證照政策、薪資、地點、僱用型態、甄選門檻 |
| 績效／KPI | Task、Output、Performance Indicator | KPI 公式、目標值、期間、權重、資料來源與主管核定；`P` 不是完整 KPI |
| 訓練／發展 | 職務要求的 K／S 與其 Task 關聯 | 個人目前能力、缺口評量、課程對應、學習優先級與發展計畫 |

這個邊界避免三個錯誤：

1. 不能因為未來要做 KPI，就讓訪談模型現在猜目標值與權重；
2. 不能因為未來要招募，就把薪資、福利與應徵條件塞進員工工作理解；
3. 不能因為未來要訓練，就把「職務需要的 K／S」誤當「目前員工已具備或缺少的 K／S」。

Web 第一個主要編輯面顯示職務說明書；日後選擇招募、KPI 或訓練用途時，才切換到該 projection 的預覽與補充流程。各畫面可不同，但共同欄位只讀同一份職務說明書，不能 copy 後各自漂移。

Owner 於 2026-08-28 同意：第一版先完成職務說明書本體、Web 顯示／編輯／審核與同語意匯出；招募、KPI、訓練先保留為由職務說明書延伸的 projection 邊界，不在本輪一次實作全部 downstream workflow。

### 17.7 已對齊的端到端白話例子

以下例子只用來固定產品語意，不是最終欄位裁決。假設受訪者是「勞動法令管理專員」：

1. **員工訪談**：員工先說自己追蹤法令、評估重大修法、回答內部問題並偶爾協助教育訓練。顧問不立刻把這些句子照抄成 JD，而會追問最近一次具體案例、處理步驟、交付結果與核准邊界。員工若之後在一般聊天中說「我剛才說錯了，不是每週彙整；平時持續追蹤、每月彙整，重大修法即時通報」，就和正常顧問訪談一樣由下一輪理解更新處理，不另設「更正原話」按鈕。
2. **Work Understanding**：保存比 JD 更完整的工作知識，例如資訊來源、從法令辨識到影響分析與送核的流程、誰有最終核准權、實際產出、頻率、曾處理的育嬰留停修法案例，以及「是否負責勞資爭議」「是親自授課或只製作教材」「何時轉外部法律顧問」等仍待釐清項目。單一案例保留在理解層，不會永久偽裝成一條通用 Task。
3. **職務說明書**：從已建立的工作理解萃取穩定且重要的工作。例如職務目的可寫成「持續追蹤並解讀勞動法令，評估對公司制度與流程的影響，提供內部諮詢與調整建議，以降低法令遵循風險」；主要職責可分為「法令追蹤與影響評估」及「內部法令諮詢與溝通」，其下再列 recurring／significant Tasks、必要成果或完成標準，以及執行所需 K／S。育嬰留停個案本身不成為永久 Task。
4. **員工審核**：若 AI 寫成「負責核定制度修改」，員工可直接把綠色待審內容改為「草擬制度修改建議，提交主管核准」。編輯後仍維持待審，直到員工接受整個可獨立裁決的變更組；拒絕則整組回退。
5. **招募／甄選**：由核准 JD 的主要工作與必要 K／S 派生職缺基礎；HR 再補學歷／證照政策、必要與加分條件、薪資、地點、聘僱型態及甄選門檻。這些不是從訪談憑空猜入 JD。
6. **績效／KPI**：由核准 JD 的 Tasks、成果與完成標準建立考核候選；主管再決定公式、目標值、期間、權重、資料來源與核准責任。JD 中描述的成功完成條件不是一套已完成的 KPI。
7. **訓練／發展**：由 JD 的職務所需 K／S 建立要求側基礎，再和員工目前能力的獨立評量比較，才形成缺口與訓練計畫；「職務需要什麼」不能被誤寫成「這位員工目前缺什麼」。

這個例子的固定主線是：

```text
員工訪談
  → Work Understanding（完整、細節、可修訂）
  → 職務說明書（正式、精簡、員工核准）
  → 招募／甄選、績效／KPI、訓練／發展
```

下游用途發現 JD 事實不正確時，必須回到訪談／Work Understanding 與待審變更修正核心 JD；不得由下游表單靜默改寫職務真相。

## 18. `P` 的語意與成品 JD 欄位研究（進行中）

### 18.1 問題不是只在翻譯

Owner 明確要求 Caliburn 不照抄 iCAP，而要研究適合「由員工真實工作形成核心職務說明書，再供招募、KPI 與訓練使用」的成品。因而要分別回答：

1. iCAP 的 `P` 原本是什麼；
2. Caliburn 是否仍需要同一概念；
3. 若需要，產品名稱與資料形狀是否仍應叫「行為指標／績效指標」；
4. 獨立 `O`、`P` 是否都必須成為核心 JD 欄位，不能因現行程式已存在就保留。

### 18.2 現行官方與跨國資料的共同邊界

1. [iCAP 官方知識頁](https://icap.wda.gov.tw/ap/knowledge_introduction.php) 把「行為指標」定義為**用以評估是否成功完成工作任務之標準**，並要求描述任務情境下應有的行為或產出；它不是單純列出員工的動作。2026《[職能基準品質認證作業手冊](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E5%93%81%E8%B3%AA%E8%AA%8D%E8%AD%89%E4%BD%9C%E6%A5%AD%E6%89%8B%E5%86%8A.pdf&e=20260311201400.pdf&t=download)》又要求其具體反映能力展現程度、清楚描述行為表現，並可作成果評量依據。
2. UK NOS 2024《[Quality Criteria](https://next.ukstandards.org.uk/media/kqppvuwl/sds-nos-quality-criteria-update-13-05-2024.pdf)》使用 `performance criteria`，回答「為了把功能做到合格，個人需要做什麼或確保什麼發生」，並要求整組 criteria 能區分 satisfactory／unsatisfactory performance。這比「行為」更接近**合格完成條件**。
3. 澳洲官方 training package 結構把 `performance criteria` 定義為完成工作所需的表現；真正用來證明達標的次數、材料與情境另放 `Performance Evidence／Assessment Conditions`。例如 2024 [TAEASS412](https://training.gov.au/assets/TAE/TAEASS412_R1.pdf) 的 criteria 多採「依組織程序」「不損害評量完整性」等可查核條件，數量門檻則留在 assessment requirements。
4. 本 repo 的[跨國 P 原料](2026-08-01-opks-raw-performance-indicators.md) 已全量或抽樣比對澳洲、香港、新加坡與 OPM：職務／職能描述層不自行發明數值目標；數字若存在，多位於獨立評量元件或評分量表。新加坡 Skills Framework 也把 `Critical Work Functions／Key Tasks／Performance Expectations` 與 skills 分開，而非把 Expectations 當 KPI 表。
5. [OPM Developing Performance Standards](https://www.opm.gov/policy-data-oversight/performance-management/reference-materials/articles/developing-performance-standards/) 把真正的 performance standard 定義為**管理者核准**、放在員工績效計畫中的門檻／要求／期待，會進一步決定品質、數量、時效、成本及具體衡量方式。因此 JD 的成功完成條件不能冒充已核准 KPI。

暫時結論：iCAP 的 `P` **官方名稱是「行為指標」**，但其語意比名稱寬；對 Caliburn 而言，它既不是單純行為清單，也不是完整績效指標／KPI，而是「這項工作怎樣才算合理完成」的可觀察、可查核條件。

### 18.3 三個產品名稱選項

| 名稱 | 優點 | 主要風險 |
|---|---|---|
| `行為指標` | 與 iCAP 名詞一致 | 容易被員工與 LLM 誤解成重述動作或通用軟性行為，忽略成果、品質、合規與時效；Caliburn 已不以 iCAP 匯出為目標 |
| `績效指標` | HR 使用者熟悉 | 最容易被誤認為 KPI，期待公式、目標值、期間與權重；也暗示員工具有訂定管理門檻的 authority |
| `完成標準`（候選首選） | 直接回答「怎樣算完成得合理」，可容納成果、品質、程序／法規、時效與必要例外 | 若不加定義，仍可能被寫成空泛句子 |

較正式的替代名稱是 `工作表現標準`，但仍帶 performance-management 聯想。Owner 於 2026-08-28 接受此語意方向：產品顯示採「完成標準」，內部契約候選採語意清楚的 `completion_criteria`。`P`／「行為指標」只作研究既有資料時的對照名詞，不再是產品欄位或匯出 compatibility target。這項裁決確立的是產品語意與名稱；整體成品 JD schema 仍須待本節其餘欄位收斂後才能成為 implementation authority。

`completion_criteria` 可描述：

- 必須產生或維持的成果／狀態；
- 品質、正確性、完整性或可用性條件；
- 必須遵循的法規、SOP、核准與責任邊界；
- 有來源時的時效／服務條件；
- 真正常見且影響成敗的例外處理。

它不包含：模型猜出的百分比、主管尚未核准的目標值、績效權重、評分公式，或可以原封不動套到任何職位的「主動積極／良好溝通」。

### 18.4 「完美 JD」的三種結構候選

「完美」在本研究中不是欄位最多，而是：能準確描述目前職位、讓人讀得懂、能從 Work Understanding 追溯、適合維護，並能安全派生下游用途。現有權威可形成三種候選：

#### 方案 A：iCAP 相容優先

`職務名稱／工作描述 → Duty → Task → O → P → K／S`。

- 優點：台灣使用者熟悉，與既有公版直接對應。
- 重要修正：iCAP 雖有獨立 O 欄，但**不是每個 Task 都必填**；官方明定只有行動或操作性工作成果時可省略 O，並把成果寫進行為指標。因此「可選的關鍵產出」不是 Caliburn 自行放寬 iCAP。
- 缺點：跨國資料顯示「獨立 O 欄」仍是 iCAP 較特殊的版型；若沒有資訊增益仍硬列，O、Task result 與完成標準容易重複，`P` 舊名稱也容易誤導。

#### 方案 B：一般國際 JD 精簡型

`職務名稱／職務目的／組織與回報關係 → Major Duties／Responsibilities → 必要 K／S → 重要工作情境`。

- 優點：接近 OPM 的 major duties／responsibilities／organizational relationships，以及英國 National Archives 建議的 title／key purpose／duties／reporting line；清楚、短、容易維護。
- 缺點：若只做到這裡，Caliburn 已研究過的 Task 粒度、成果、完成品質與 K／S 關聯會大量消失，對後續 KPI／訓練的重用價值較弱。

#### 方案 C：Caliburn 混合型（目前推薦繼續討論）

```text
職務表頭
  - 職務名稱
  - 職務目的
  - 組織位置／回報關係（有可靠 authority 時才填）

Duty（主要且持續的責任範圍）
  - 名稱
  - 簡短責任／目的說明
  - Task（最小且有意義成果的 recurring／significant 工作）
      - canonical statement
      - 關鍵產出（可選、可多筆；只有獨立列出能增加資訊時才存在）
      - 完成標準（0～N；成熟 Task 原則上應具備，訪談未取得時保留待補資訊）
      - 所需 K／S 關聯

職務層補充（只在重要時顯示）
  - 關鍵協作／責任與核准邊界
  - 重要工作條件或法定要求
```

方案 C 吸收 O\*NET「Task 是帶有意義成果的最小活動單位」、OPM 2026 USA Class「major duties 應描述 regular and significant work」、UK NOS「performance criteria 應區分合格與不合格」與 OPM task↔competency linkage；但不照抄任何單一政府表格。

以下暫不放入核心 JD：

- 完整訪談案例、quote、待釐清與推理細節（留在 Work Understanding）；
- 每個 Task 的固定頻率／責任角色（是否提升成品仍待代表案例檢查）；
- 招募廣告的薪資、福利、學歷、加分條件；
- KPI 目標值、公式、期間與權重；
- 員工個人能力缺口與課程；
- `A` 與職能級別（Owner 已決定第一版先不做分析 Skill）。

### 18.5 尚待 Owner 逐項討論

1. **已收斂：**產品上的 `P` 改稱「完成標準」；`P`／「行為指標」只作研究對照，不保留 iCAP 匯出映射；
2. **已收斂：**`O` 是 Task 下 0～N 筆可選的「關鍵產出」；只有獨立列出能增加資訊時才存在。無獨立產出時不硬填，但有意義成果仍須存在於 Task 或完成標準。這也符合 iCAP 原本允許省略 O 的規則；
3. **已收斂：**Duty 名稱必填；簡短目的／範圍說明可選，只有能補充責任邊界而不重複 Tasks 時才存在；
4. **已部分收斂：**職務名稱與職務目的為核心必填；所屬單位／團隊、直接回報職位與管理責任有可靠資料才填，不要求員工猜正式編制或主管核定資訊；
5. **已收斂：**「工作關係與重要條件」為整區可選；只保留會實質影響工作、交接、責任邊界或安全的資訊，無內容時整區不顯示；AI 不自行宣告法律上的 essential function；
6. **已收斂：**已用知識工作、現場操作與服務工作做小型壓力測試；方案 C 能跨職類表達，但確認 `O` 必須可選、成熟 Task 應有可判斷合理完成的完成標準、K／S 必須能與 Task 建立關聯且避免重複複製。訪談中的 partial state 仍依 §18.12 允許完成標準為 0 筆；這是品質待補，不是 schema error。詳見 §18.9。

上述欄位與關聯已完成產品收斂，但在 ADR、設計稿與實作計畫同步且再審通過前，不修改 production schema、Tool contract 或匯出格式。

### 18.6 匯出政策：只做 Caliburn 自有職務說明書

Owner 於 2026-08-28 明確決定：**Caliburn 不再提供或保留 iCAP 格式匯出；最終只匯出本研究收斂出的 Caliburn 自有職務說明書格式。**iCAP 仍可作為職務分析方法、欄位語意、品質判準與台灣官方案例的研究來源，但不是產品 schema、欄位名稱、位置碼或版面 authority。

因此：

1. Web 編輯、員工審核與 deterministic export 共用同一份 Caliburn semantic JD；
2. 匯出器只負責把同一語意內容排成適合閱讀／列印的 Caliburn 版面，不再做 iCAP 欄位映射；
3. 不因 iCAP 表格存在 `O／P／K／S`、位置碼或基準級別，就要求產品保存同名欄位；
4. 既有文件中「公版匯出」「iCAP compatibility／projection」只屬歷史研究背景，後續設計與實作不得再以它們為需求；
5. 若未來另有外部交換需求，必須作為新的 opt-in adapter／產品決策重新研究，不能預埋進核心 schema。

這個方向符合近期官方與大型 HCM 產品的可組合做法：

- [OPM USA Class 2026](https://support-class-usadata.opm.gov/hc/en-us/articles/51115834989843-Major-Duties-Statements-Overview) 以 Major Duty title／description／statements 組裝其自身 position description，並由使用者編輯 regular and significant work；它不是套用 iCAP 類型的跨國公版。
- [SAP SuccessFactors Job Profile Builder 1H 2026](https://help.sap.com/docs/SAP_SUCCESSFACTORS_PLATFORM/6653514fe7d84eca8e9bc2d38e46666d/99856fa2c4944001ab5991e92c9454eb.html) 將 Job Responsibility、Skill、Employment Condition 等做成可組合 content types；[template sections](https://help.sap.com/docs/SAP_SUCCESSFACTORS_PLATFORM/6653514fe7d84eca8e9bc2d38e46666d/0896db039fb6406eaa9e0144e95ea9ab.html) 可分別設定 required、visibility 與標題。
- [Oracle HCM Profile Types](https://docs.oracle.com/en/cloud/saas/human-resources/faucf/profile-types.html) 同樣以 configurable content sections 定義 job／position profile，並分離 job requirements、work requirements、權限與 downstream 使用方式。

這些產品的 schema 遠比 Caliburn 大，但共同教訓是「欄位依產品目的組合」而非「尋找一張全球唯一模板」。Caliburn 第一版仍採 YAGNI：只保留經訪談可建立、員工能理解、對核心 JD 或已確認下游用途有資訊價值的欄位。

### 18.7 關鍵協作、工作條件與 essentiality 的候選邊界

官方資料支持這些資訊可能有價值，但不支持全部必填：

- 英國 National Archives 的[職務說明書指南](https://www.nationalarchives.gov.uk/archives-sector/advice-and-guidance/running-your-organisation/writing-a-job-description/putting-a-job-description-together/) 把 reporting line、key relationships、working hours 與 location 列為可考慮的 sections；同時強調 JD 應清楚簡潔、不是列出每件可能工作。
- [Oracle HCM Profile Types](https://docs.oracle.com/en/cloud/saas/human-resources/faucf/profile-types.html) 把 work schedule、travel frequency 等視為可配置 work requirements，而不是所有職位固定必填的核心文字。
- [SAP Job Profile Builder](https://help.sap.com/docs/SAP_SUCCESSFACTORS_PLATFORM/6653514fe7d84eca8e9bc2d38e46666d/99856fa2c4944001ab5991e92c9454eb.html) 也把 Employment Condition、Physical Requirement、Job Responsibility 與 Skill 分成不同可組合 content types。
- [EEOC essential-functions guidance](https://www.eeoc.gov/publications/ada-your-responsibilities-employer) 指出 essential function 需綜合職位存在原因、可分工人數、專業程度、目前／過去任職者實際經驗、投入時間與不執行後果；書面 JD 只是證據之一。因此 LLM 不能只依一次訪談自行把 Task 宣告成法律上的「必要職能」。

目前推薦的最小邊界是：

| 資訊 | 核心 JD 處理 | 不應做的事 |
|---|---|---|
| 關鍵協作 | **可選**；只列理解工作與交接所必需的角色類型，如「人資主管、各部門窗口、外部法律顧問」 | 不列人名、不把每個對話對象都列入 |
| 責任／核准邊界 | **可選但優先級高**；確實影響責任範圍時放 Duty 說明或職務層補充 | 不把草擬、建議、執行誤寫成最終核准權 |
| 工作時間／輪班／待命／出差 | **可選**；只有它是職務固有要求時顯示 | 不把一般聘僱條件、臨時安排或招募政策硬寫進 JD |
| 地點／環境／身體條件／風險 | **可選**；只有會實質改變工作執行方式或安全要求時顯示 | 不從職稱推測體力、現場或危險條件 |
| essentiality | 第一版不讓 AI 自行產生法律標籤；相關頻率、後果與專業性證據留在 Work Understanding | 不因 Task 被列入 JD 就自動宣告為 essential function |

Owner 於 2026-08-28 接受：把前四類合併成一個可選的「工作關係與重要條件」區塊；沒有內容時整區不顯示。這能避免為每一類再造必填欄，也比把資訊藏在任意補充文字中容易理解與維護。

### 18.8 三層文件邊界與本輪討論範圍

Owner 再次提醒：**目前正在收斂的是「核心職務說明書 JD」；不得把 Work Understanding 或後續延伸文件的欄位誤塞進 JD。**三層關係固定如下：

```text
員工訪談／歷史來源
        ↓
Work Understanding
（AI 長期理解員工實際工作；完整、細節、可修訂、含來源與待釐清）
        ↓ 萃取穩定且重要的職務事實
核心職務說明書 JD
（員工查看、編輯、審核與 Caliburn 自有格式匯出的正式成品）
        ↓ 依用途派生，不反向靜默改寫 JD
後續延伸文件
（招募／甄選、績效／KPI、訓練／發展等）
```

欄位歸屬判準：

| 問題 | 應歸屬 |
|---|---|
| AI 為了長訪談不遺忘、判斷衝突、保留案例、來源與細節，需要知道什麼？ | Work Understanding |
| 這是不是該職位目前穩定、重要且值得正式告知員工／組織的工作事實？ | 核心 JD |
| 這是不是只有在招聘、考核或訓練時才需要的政策、目標、門檻或個人資料？ | 對應的後續延伸文件 |

例子：

- 員工曾處理哪一件育嬰留停修法、當時查過哪些來源、還有哪些衝突未釐清：Work Understanding；
- 職務目的、Duty／Task、可選關鍵產出、完成標準、必要 K／S、重要責任邊界：核心 JD；
- 薪資、招募學歷門檻、KPI 權重／目標值、員工個人技能缺口與課程：後續延伸文件。

因此 §18.3～18.7 的所有欄位裁決都只適用於**核心 JD**。Work Understanding 的 Case／Pattern／Gap／來源模型與 downstream projections 不在這一段重新設計；它們只能用來供應或消費 JD，不得藉本輪新增第二份職務真相。

### 18.9 三類職務壓力測試（Owner 已確認）

為避免只用單一辦公職務倒推 schema，本輪以三種差異明顯的工作檢查方案 C。這不是要複製 O\*NET 的欄位，而是用其官方職業資料確認同一組 Caliburn 語意能否涵蓋知識、現場與服務工作。

| 類型與例子 | Duty／Task | 關鍵產出 `O` | 完成標準 | K／S | 可選補充 |
|---|---|---|---|---|---|
| 知識工作：勞動法令／合規專員 | 追蹤法規並評估制度影響 | 影響分析、修訂建議；有獨立成品時才列 | 涵蓋受影響制度、結論可追溯、未越過核准權限 | 勞動法令與公司制度；法規解讀、影響分析 | 關鍵協作與核准邊界 |
| 現場工作：設備維修技術員 | 診斷並修復設備故障 | 維修或零件紀錄；確實需要交付時才列 | 修復後通過檢測、遵守安全程序、紀錄正確 | 機械／電控／安全知識；診斷、量測與修復技能 | PPE、危害與作業環境 |
| 服務工作：客服人員 | 釐清並處理顧客問題 | 互動紀錄；沒有獨立產出時可省略 | 回覆正確、適當升級、確認問題處理狀態 | 產品與政策知識；傾聽、問題釐清與溝通技能 | 協作、交接或固有輪班條件 |

壓力測試得到六項邊界：

1. `O` 不得為所有 Task 強制生成；服務或即時處理工作常由 Task 本身與完成標準充分表達；
2. 「完成標準」不可被 `O` 取代，因為三類工作都需要表達品質、合規、正確性或處理結果；
3. K／S 需要能回到它支援的 Task，否則無法判斷某項知識或技能為何是職務所需；
4. 同一 K／S 可能支援多個 Task，不應在每個 Task 下複製成彼此會漂移的多份文字；資料形狀仍待下一輪收斂；
5. 工作關係與重要條件適合整區可選：現場工作常重要，純知識或服務工作則只在確實影響責任與執行時顯示；
6. 頻率不是每個 Task 的必要成品欄位；它可保留在 Work Understanding，只有會實質界定工作或完成條件時才提升到核心 JD。

佐證來源：

- [O\*NET Compliance Officers](https://www.onetonline.org/link/summary/13-1041.00) 同時列出法規評估、溝通、政策與法律知識，顯示知識工作仍可用 Task、K、S 與工作情境區分；
- [O\*NET Industrial Machinery Mechanics](https://www.onetonline.org/link/summary/49-9041.00) 將診斷、維修、測試、安全與設備知識並列，支持現場工作需要完成條件與重要工作環境；
- [O\*NET Customer Service Representatives](https://www.onetonline.org/link/summary/43-4051.00) 顯示服務工作可有多項互動／問題處理 Task，但不必為每項工作強造獨立實體產出；
- [O\*NET Task 定義](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf) 將 Task 定義為帶有可辨識開始與結束、並產生有意義成果的工作活動；「有意義成果」不等於每個 Task 都必須另有一筆 `O`；
- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 要求工作分析辨識 Tasks 與 competencies，並檢查兩者關聯；這支持下一輪保留 K／S↔Task linkage，而不是只列一份無關聯清單。

Owner 於 2026-08-28 確認此壓力測試符合產品方向。這代表方案 C 已通過跨職類概念檢查，但**不等於 K／S 的資料模型與 UI 已裁決**；下一輪需比較「每 Task 複製」「只做職務層清單」與「共用 K／S＋Task 關聯」三種做法。

### 18.10 K／S：共用內容與 Task 關聯（Owner 已確認）

Owner 於 2026-08-28 選擇「共用 K／S＋Task 多對多關聯」，而不是在每個 Task 內複製文字，也不是只留一份看不出用途的職務層清單。

第一版語意邊界如下：

1. 同一份 JD 內，每項 Knowledge／Skill 只保存一份 canonical 內容與穩定 ID；ID 由系統建立，不要求 LLM 生成；
2. Task 與 Knowledge、Task 與 Skill 分別建立多對多關聯；一項 K／S 可支援多個 Task，一個 Task 也可需要多項 K／S；
3. Task 階層中可投影顯示相關 K／S，讓員工在工作脈絡內閱讀；職務層另提供去重後的「所需知識與技能」總覽，並標出其相關 Tasks；兩處是同一資料的不同 projection，不是兩份內容；
4. 第一版的共用範圍限於**同一份 JD**。不先建立跨文件、跨職務或全公司的技能 taxonomy／content library；未來若有明確重用需求再另行研究；
5. 第一版仍不加入能力級別、權重或 entry／target proficiency；
6. Knowledge 應描述知識領域或概念，例如「勞動法令及相關子法」；Skill 應描述可運用的能力，例如「法規解讀與制度影響分析」，不得只是把 Task 改寫成「具備執行某任務的能力」。

這項設計是兩類權威做法的組合，而不是宣稱任何單一產品已提供 Caliburn 完整模型：

- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 要求分析 Tasks、competencies 與兩者連結；其[官方簡報](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/job_analysis_presentation.pdf)進一步要求無法連到 competency 的 Task、以及無法連到 Task 的 competency 應重新檢查；
- [SAP SuccessFactors 1H 2026](https://help.sap.com/docs/successfactors-platform/implementing-and-managing-job-profile-builder/mapping-skills-and-other-attributes-to-job-roles) 以 Talent Intelligence Hub 維護共用 skill／competency，再用 mapping 關聯到 role；[Job Profile object dependencies](https://help.sap.com/docs/successfactors-platform/implementing-and-managing-job-profile-builder/job-profile-objects-dependencies) 也把內容物件與 mapping 視為分離的關聯物件；
- Caliburn 擷取兩者共同原則：「能力內容只存一份、用途用關聯表示」，但保留更細的 Task linkage，以符合本產品的工作分析目的。

Owner 同日進一步裁決：**尚未連到任何 Task 的 K／S 只留在 Work Understanding／一般待釐清，不進核心 JD，也不為此建立「未歸屬 K／S」正式區。**找到相關 Task 後，AI 才提出「新增或重用 K／S＋建立 Task 關聯」的待審變更；一直找不到 Task 的內容仍是訪談線索，不會被誤寫成正式職務要求。

這項邊界不否定訪談可以先發現 K／S：發現順序仍可為 K／S→Task，差別只在尚未形成可說明的工作關聯前，它屬於較完整的工作理解，而不是較精簡的成品 JD。這也避免為了安放 K／S 而虛構暫時 Task，或讓員工看到一份含有未證明職務相關性的正式能力清單。

### 18.11 Task：單一成品敘述，分析拆解不成為正式欄位（Owner 已確認）

Owner 於 2026-08-29 裁決：核心 JD 的 Task 只保存一段 canonical `statement`。Action、Object、Purpose／Result、Context 與 Enabler 仍是 Task 分析 Skill 的寫作與品質檢查方法，也可在確有長期價值時保留於 Work Understanding；但不各自成為員工需要閱讀、編輯與核准的正式 JD 欄位。

例：

> 分析重大勞動法令變動對公司制度與流程的影響，提出修訂建議。

Skill 可在產生或審查此句時辨識「分析／重大法令變動／制度與流程／提出修訂建議」，但 Tool 只提交最終 statement，application 也不維護一套可能與 statement 漂移的拆分文字。

正式邊界如下：

1. Task 的唯一必要成品文字是 `statement`；
2. 關鍵產出、完成標準與 K／S 是各自可重複的相關內容，不塞回 Task statement 的結構欄位；
3. 頻率通常留在 Work Understanding；只有會實質界定該工作或完成條件時，才自然寫入 Duty／Task 語意或「工作關係與重要條件」，不建立固定 per-Task frequency 欄；
4. 主責、協作與核准邊界同理：有資訊價值時寫入 Task 語意、Duty 說明或職務層補充，不建立固定 per-Task responsibility-role 欄；
5. 一句若包含彼此可獨立成立、沒有共同成果的工作，應拆成多個 Tasks，而不是增加更多欄位包住雙重任務；
6. stable ID、Duty relation、order、revision 與 review metadata 仍由 application／framework 管理，不是 statement 的一部分。

佐證：

- [O\*NET 31.0 Task Statements](https://www.onetcenter.org/dictionary/31.0/json/task_statements.html) 的正式資料以單一 `task` 文字保存每項 Task；
- O\*NET 的[官方寫作附錄](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf)則以 Action、Object、Purpose／Result、Enabler 與 Context 協助形成高品質 statement，並指出 Purpose／Result 可隱含或明示、Context 通常較少見；這支持「分析結構完整、成品欄位精簡」；
- [O\*NET 近期 emerging-task 方法](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf)要求 statement 清楚、精簡、避免 double-barreled wording；
- [OPM USA Class 2026](https://support-class-usadata.opm.gov/hc/en-us/articles/51115834989843-Major-Duties-Statements-Overview) 讓使用者直接新增、編輯、排序與刪除完整 duty statements，也要求它們兼具 recurring-work 廣度與足以審查的細節。

本節正式取代 §16.3、§16.7 的 `statement＋frequency_text＋responsibility_role` 舊候選；那些段落只保留為研究歷程，不得再作 implementation baseline。

### 18.12 結構有效不等於分析已完整（Owner 已確認）

Owner 於 2026-08-29 裁決：核心 JD 必須能在多輪訪談中逐步建立，不能把「尚未分析完整」做成 schema error，也不能為了通過驗證逼模型同輪猜滿所有欄位。

因此第一版分成兩層：

1. **結構 invariant**：只有會造成資料無法解讀或關聯失效的情況才拒絕，例如 Task 沒有 statement、K／S 指向不存在的 Task、同一 child 同時掛到互斥父項；
2. **分析待補資訊**：已確認 Task 尚缺完成標準、尚未辨識必要 K／S，或工作邊界仍不清楚時，仍可保存與核准 Task，但把缺口保留在 Work Understanding／一般待釐清，供後續訪談選焦點。

各項第一版 cardinality／品質語意：

| 項目 | 結構上允許 | 品質目標 |
|---|---|---|
| Task statement | 恰好 1 段非空文字 | 清楚、單一工作、包含足夠的 action／object／result 語意 |
| 關鍵產出 | 0～N | 只有獨立列出有資訊增益時才存在；缺少本身不是 Gap |
| 完成標準 | 0～N | 成熟 Task 原則上應能說明怎樣算合理完成；尚未取得時形成待補資訊，不阻擋保存／核准 |
| K／S relations | 0～N | 成熟 Task 應連到必要 K／S；尚未辨識時形成待補資訊，不阻擋保存／核准 |
| Duty 說明、工作關係與重要條件 | 可空 | 只有真實且增加責任邊界／執行條件時才填；不因空白形成 Gap |

AI 後續取得資訊時，以新的待審變更補上完成標準或 K／S 關聯；不重寫整份 Task，也不把「這項 Task 還缺什麼」塞成正式 JD 文字。本節只決定訪談期間的資料與品質邊界，不改動現行匯出政策。

佐證邊界：

- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 把 Task、competency 與兩者關聯視為完整分析的品質基礎，但其流程本身先蒐集、列出、評定再識別 critical items，並非要求第一筆資料就已完成全部關聯；
- [UK NOS Quality Criteria 2024](https://next.ukstandards.org.uk/media/kqppvuwl/sds-nos-quality-criteria-update-13-05-2024.pdf) 要求成熟的 occupational function 具有可區分合格／不合格的 performance criteria 與必要 knowledge；這是成品品質目標，不代表訪談中的 partial state 必須被資料庫拒絕；
- [SAP AI-extracted skill validation](https://help.sap.com/docs/successfactors-recruiting/setting-up-and-maintaining-sap-successfactors-recruiting/validating-skills-in-job-description) 也區分 AI 建議、使用者驗證與正式保存。Caliburn 不照抄其 recruiting workflow，只採「建議可逐步完善、權威核准另有邊界」的共同原則。

### 18.13 不對稱的彈性階層（Owner 已確認）

Owner 於 2026-08-29 裁決：核心 JD 不要求任何時間點都形成完整樹，也不允許所有子項無條件脫離語意父項。第一版採下列不對稱階層：

| 內容 | 核心 JD 關聯規則 | 尚未形成關聯時 |
|---|---|---|
| Duty | 可暫時有 0～N Tasks | 空 Duty 可保存，但形成「尚待辨識具體工作」的待補資訊 |
| Task | 可連 0～1 Duty | 無 Duty 時仍可保存，顯示在「尚未歸屬」；其既有子項跟隨 Task |
| 關鍵產出 | 必須且只連 1 個 Task | 先留 Work Understanding，不進核心 JD |
| 完成標準 | 必須且只連 1 個 Task | 先留 Work Understanding，不進核心 JD |
| Knowledge／Skill | 進入核心 JD 時必須連 1～N Tasks | 依 §18.10 留在 Work Understanding／一般待釐清 |

這代表發現順序仍然自由：訪談可以先出現 Duty、Task、成果、標準或 K／S 線索；限制的是它們**何時成為可解讀的核心 JD 內容**，不是限制 AI 必須照 Duty→Task→OPKS 的順序分析。

UI 的「尚未歸屬」只需要承接真正能獨立成立的 Tasks，以及跟著該 Task 的關鍵產出／完成標準；不另建孤立 O、完成標準或 K／S 的正式區。也不得為安放子項而建立假的 Duty／Task。

佐證與產品推論：

- [iCAP 官方知識頁](https://icap.wda.gov.tw/ap/knowledge_introduction.php) 把工作產出定義為執行某任務的關鍵產出，把行為指標定義為是否成功完成工作任務的標準；因此 Caliburn 的關鍵產出與完成標準若沒有 Task，就失去被評估的對象；
- [UK NOS Quality Criteria 2024](https://next.ukstandards.org.uk/media/kqppvuwl/sds-nos-quality-criteria-update-13-05-2024.pdf) 也把 performance criteria 與 knowledge 寫成針對特定 occupational function 的要求；
- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)要求 Tasks、competencies 與兩者關聯，支持 K／S 不能以無法說明工作用途的孤立正式要求存在；
- 「Duty／Task 可暫時不完整，但 child content 需有可解讀 parent」是 Caliburn 對多輪訪談與動態重組需求的產品推論，不宣稱由上述任一官方格式直接規定。

依 §0，本節是目前 implementation baseline，但仍可在新證據下經 Owner 討論後翻案；任何實作者不得自行放寬成「所有 OPKS 都可孤立」或收緊成「沒有完整 Duty 樹就不能保存」。

### 18.14 K／S 失去最後 Task 關聯的生命週期（Owner 已確認）

Owner 於 2026-08-29 裁決：**已進入核心 JD 的 canonical Knowledge／Skill 若因解除關聯、刪除 Task 或 cascade 操作而失去最後一個 Task link，必須在同一個 deterministic authority command 中從核心 JD 移除。**產品不建立「待重新連結 K／S」、孤立 K／S 倉庫或隱藏正式區。

操作邊界如下：

1. server 在套用結構操作前計算 dependency closure 與 blast radius，將「會失去最後 link 並移出核心 JD 的 K／S」列入實際結果；UI 不自行推算；
2. 可完整逆轉的單項操作可立即執行並提供 Undo；刪除含多個 Tasks 的 Duty 等高影響 cascade，仍須先顯示受影響 Task、關鍵產出、完成標準、K／S links 與將移出的 K／S，再由員工確認；
3. 同一 K／S 仍被其他 Task 引用時，只解除本次 link，不刪 canonical item；
4. 此結構結果**不自動新增、修訂或刪除 Work Understanding**。工作理解仍由顧問依員工對話與最新 JD delta 在後續分析中更新；若既有理解顯示該 K／S 仍屬此職務，AI 可提出重新建立／重用 K／S 並連到適當 Task，或在真正不清楚時詢問員工；
5. 待審 AI atomic group 內若刪除／改寫 Task 會讓 K／S 失去最後 link，該移除結果必須留在同一 dependency closure；員工看到並接受的是完整 after-state，不允許接受出無 link 的核心 JD K／S。

這項裁決正式取代 ADR 0070 與 2026-08-27 UI 設計稿中「K／S 最後 link 消失後保留在待重新連結區」的舊候選。它延續 §18.10「核心 JD 的 K／S 必須連 1～N Tasks」與 §18.13「不建立孤立 K／S 正式區」，同時保留 Work Understanding 與核心 JD 的 authority 邊界；application 只維護文件結構完整性，不把文件刪除副作用冒充成新的員工工作事實。

## 19. 模型可修復 Tool 錯誤與有界回饋協定（Owner 可翻案同意）

### 19.1 狀態、目的與不處理範圍

Owner 於 2026-08-29 暫定同意本節方向，並再次確認：所有同意都可被後續真實案例、成本／品質數據、框架限制或更強官方證據推翻，但不得由實作者自行翻案。本節補完 §11.2～§11.3 尚未寫清楚的問題：模型填錯 Tool 參數、找不到項目、exact replace 失敗、關聯不合法或工作區版本失效時，application 到底要回什麼，誰應修正，以及何時停止重試。

本節不是新建一套自製 agent protocol，也不要求模型再填一張「錯誤表單」。Provider-native 的 `call_id`／`tool_use_id` pairing、Tool result message、tool loop、retry 與 durable route 由 LangChain／LangGraph 承擔；Caliburn 只定義框架不知道的 JD domain diagnostics。本節也不處理員工可見 UI 文案、RAG、A／能力級別或完整 eval。

### 19.2 官方資料直接支持的共同模式

#### OpenAI／Codex

[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 把 Tool output 定義為 application 執行模型 Tool call 後產生、並以同一 `call_id` 回給模型的結果；內容可以是 structured JSON 或文字。官方同頁建議開啟 strict mode、用 object／enum 讓 invalid state 難以表示、不要讓模型填 application 已知的參數，並在程式可完成時把負擔移出模型。這些規則只保證輸入 shape；`task-999` 是否存在、K／S 是否連到合法 Task、某段舊文字是否唯一等 domain truth，仍須 application 驗證。

[OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch) 的正式流程是：模型提出 structured diff，host harness 真正解讀與套用、記錄成功／logs／errors，再為每個 `call_id` 回一個含 `status` 與可選 `output` 的結果，讓模型繼續編輯或說明。OpenAI 並沒有把「patch 能被 JSON 解析」等同於「目標檔案存在且修改有效」。

[OpenAI GPT-5.6 Model guidance](https://developers.openai.com/api/docs/guides/latest-model) 要求 Tool description 寫清楚預期 return fields、types 與 error behavior；若每個中間結果可能改變模型下一個判斷，應維持 direct Tool feedback，而不是把結果藏進不透明的批次程式。它也建議 prompt／Tool 保持精簡，只在成功品質不變時才把 calls、turns 或 token 較少視為改進。

Codex 開源 harness 提供更直接的實作證據：[apply-patch handler](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/apply_patch.rs) 在 patch parse／verification 失敗時使用 `FunctionCallError::RespondToModel`，把可修正的失敗回給模型；[Codex app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#errors) 則把 upstream／quota／sandbox／internal 等 turn-terminal failures 分成獨立 error lifecycle。兩者共同支持「模型可修復的工具失敗」與「系統終止錯誤」不能混成同一個 `分析錯誤，請重試`。

#### Anthropic／Claude Code

[Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls) 規定 client Tool 的結果以對應 `tool_use_id` 回傳，執行失敗時設定 `is_error: true`；Tool result 必須緊接對應 Tool use，收到結果後 Claude 才繼續原任務。官方同頁也建議在不需要完全自控時使用 SDK Tool Runner 管理 loop、結果格式與 retries。

[Anthropic Tool-use troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use) 建議以 strict mode、較小 enum、清楚 description／input examples 避免錯誤參數；同頁要求 Tool result 保留為資料，不要把應用程式指令混進可能不可信的 Tool result。故 Caliburn 的「看到某個 error code 後應怎麼做」屬固定 runtime／Tool description 規則，每一筆 error payload 只傳事實，不重複塞一段命令式 prompt。

[Anthropic Fine-grained tool streaming](https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming#handling-invalid-json-in-tool-responses) 在 Tool input 無法解析時，以對應 `tool_use_id`、`is_error: true` 與小型 JSON wrapper 把原始失敗回給 Claude；這證明「精簡 structured error 作為 Tool result」是官方支援的正常 agent loop，不是 Caliburn 自創 retry prompt。[Claude Code agentic loop](https://code.claude.com/docs/en/how-claude-code-works) 也以 gather context → take action → verify results 的循環處理工具結果；[Claude Code Tools reference](https://code.claude.com/docs/en/tools-reference#lsp-tool-behavior) 說明檔案編輯後 LSP 會把 type errors／warnings 回給 Claude，讓它依真實執行結果修正。

#### LangChain／LangGraph

[LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools) 的 `ToolNode` 已負責 Tool 執行、parallel calls、state injection 與 error handling；`ToolRuntime` 可注入 state、context、store 與 tool-call ID，而且這些欄位不會出現在 model schema。`ToolMessage`／`Command` 可同時把結果交回模型並更新 graph state。[LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents#tool-error-handling) 的 `wrap_tool_call` middleware 可只捕捉已知 exception，回一個帶原 tool-call ID 的 ToolMessage；這正是 Caliburn 應重用的轉譯面。

[Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately) 明確把錯誤依真正能修復的人分成 transient、LLM-recoverable、user-fixable 與 unexpected；[LangGraph Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) 則以 `RetryPolicy`／timeout／error handler 處理節點與外部服務失敗，而且預設不盲目 retry 多種 deterministic programming errors。這支持 provider retry、模型語意 repair、員工 interrupt 與程式 bug 四條分離路徑。

### 19.3 Caliburn 的產品推論：共同小型 envelope，不做巨型 error union

官方資料沒有規定 JD application 必須使用哪一組 error codes；以下是把上述共同模式套到 Caliburn 的產品推論。比較三種方案後，第一版採 C：

1. **A．只回自由文字**：程式最少，Claude／OpenAI 也能讀，但模型必須從 prose 猜 operation、target、是否已套用與下一個 read 範圍，難以跨 provider 測試；現況已有這種不一致，淘汰。
2. **B．為每種錯誤建立大型 tagged union**：型別最完整，但會重現本研究要消除的 giant schema、optional fields 與 provider grammar 成本；錯誤 payload 又是 application 產生，不需要模型通過複雜 input schema，淘汰。
3. **C．共同小型 envelope＋少量穩定 code**：framework 保留原 call pairing，application 只產生 `status／workspace_effect／errors[]`；每筆 diagnostic 只帶定位與事實。這是目前推薦。

模型可見的修復結果候選形狀：

```json
{
  "status": "repair_required",
  "workspace_effect": "not_applied",
  "errors": [
    {
      "code": "TARGET_NOT_FOUND",
      "operation": "edit_file",
      "target": "/workspace/tasks/task-014.json",
      "at": "edit_file.target",
      "message": "找不到指定的 Task；這次編輯沒有套用。",
      "read_paths": ["/workspace/tasks"]
    }
  ]
}
```

欄位語意：

- `status`：模型只需辨識 `applied` 或 `repair_required`；transient／user-required／terminal bug 由 graph 走別條路，不塞進此 envelope。
- `workspace_effect`：至少區分 `not_applied` 與 `candidate_updated`。前者表示這個操作完全沒進工作區；後者表示低階編輯已進 AI working copy，但 after-state 尚未通過 deterministic validation，模型應修正目前 copy，不重做已成功部分。
- `candidate_updated` **只表示本次有界 repair 內的非權威 working copy 已改動**：在整個 changeset 通過驗證前，員工看不到可接受的半成品，也不會部分寫入核准 JD；repair 最終失敗就回到該 wave 前最後有效 snapshot。因此它不推翻「整組變更原子審核／原子接受」規則。
- `errors[].code`：language-neutral、穩定、可測試的分類；UI 不直接顯示它。
- `operation`：指出哪一類 Tool／operation 失敗，不要求模型回填 call ID。
- `target`：model-safe path／handle；不得放內部 UUID。
- `at`：精確到參數、JSON pointer 或 relation 欄位，避免只說「資料錯誤」。
- `message`：application template 產生的短事實；不放 traceback、SQL、內部 prompt 或猜測的正確答案。
- `read_paths`：只有修正前確實需要刷新資料時才存在，且只列最小可讀範圍；不回灌整份 JD、完整 Schema 或全對話。

成功 receipt 同樣保持小型：

```json
{
  "status": "applied",
  "workspace_effect": "candidate_updated",
  "changed": ["/workspace/tasks/task-003.json"],
  "validation": "valid"
}
```

這些欄位全部由 framework／application 產生，**不增加任何 LLM-authored field**。Provider-native 的 `call_id`、`tool_use_id`、message ordering 與 `is_error`／status 由 LangChain adapter 映射；Caliburn 不為 OpenAI、Anthropic、OpenRouter 各寫一套 domain error contract。

### 19.4 錯誤分流與模型可見範圍

| 類型 | 例子 | 真正修復者 | Caliburn 路由 | 是否交回模型 |
|---|---|---|---|---|
| Provider／input shape | 漏 required、type／enum 錯、無法 parse Tool input | strict provider／LangChain invocation validator，其後才是模型 | Tool 未執行，回最小欄位 diagnostic；最多一次 model repair | 是 |
| 低階編輯前置條件 | target 不存在、create 已存在、old text 找不到或不唯一 | 模型重讀小範圍後修正 Tool call | 該 operation 不套用，回 target／match facts | 是 |
| JD domain after-state | Task 指不存在 Duty、O／P 無 Task、K／S relation 無效、group 不符合 invariant | 同一主顧問修 working copy | working copy 暫不可進 review；回最多五筆根因 diagnostic | 是 |
| Workspace stale／rebase | 員工上一輪 direct edit、approved baseline 或來源 basis 已改 | application 先刷新／rebase；真正語意衝突才需顧問或員工 | 先 deterministic refresh；必要時只重讀受影響 slice | 視情況，不把所有 stale 都浪費成 model call |
| 真正職務語意歧義 | 員工原話互斥、兩種合理工作理解會導致不同 JD | 員工 | LangGraph durable interrupt「需要你的確認」 | 否；它不是 Tool error |
| 暫時基礎設施失敗 | timeout、rate limit、provider 5xx、短暫連線中斷 | system | `RetryPolicy`／backoff／timeout，與 model repair 分開計數 | 否 |
| Unexpected／bug | invariant 程式缺陷、DB exception、未知 exception | 開發者 | rollback、terminal failure、記錄 correlation／trace、UI 一定解鎖 | 否 |

Strict mode 只能阻止 JSON shape 錯誤，不能證明一個語法合法的 handle 存在，也不能判斷工作語意；deterministic validator 只能證明結構／來源／relation invariant，不能代替員工回答真實工作歧義。三者不得互相假裝。

### 19.5 第一版候選 error families

精確 enum 應在實作計畫中由現行 validator 與代表失敗案例反推，不能現在為完整而無限列舉。第一版只需要下列小族群；名稱可在 code review 前微調，但語意不得偷偷合併：

- `INVALID_ARGUMENT`：strict provider 未攔到的 invocation／content shape 錯誤；只回錯欄與 expected type／enum，不回整份 Schema。
- `TARGET_NOT_FOUND`／`TARGET_ALREADY_EXISTS`：目標資源的存在性前置條件失敗。
- `MATCH_NOT_FOUND`／`MATCH_NOT_UNIQUE`：exact replace 的舊文字零次或多次匹配；回 match count 與 resource path，不要求模型算 Unicode offset。
- `INVALID_RELATION`：存在的資源之間不符合 Duty／Task／OPKS 關聯 invariant；回壞掉的兩端與 relation path，不替模型猜應連到誰。
- `STALE_WORKSPACE`：模型所依據的 slice 已變；revision／digest 由 ToolRuntime／application 比對，不由模型填。
- `DOCUMENT_INVALID`：同一 mutation wave 後有少量跨資源根因；只回最多五筆去重後 diagnostic，不把單一缺失造成的所有 cascade 都列出。

若日後出現新的真實 failure，可新增 code；不得為了避免改 code，把任何 exception 文字直接塞入 `message` 當成萬用分類。

### 19.6 有界 repair 的完整流程

1. 模型只看到本輪相關的少量 Tool 與精簡 input schema；document／thread／source／revision／call ID 由 `ToolRuntime` 注入。
2. Provider strict／Pydantic 先驗 input shape；失敗時 Tool 不執行。
3. `ToolNode`／middleware 以原 tool-call ID 執行或拒絕低階操作；每個 Tool call 必須恰好有一個對應 ToolMessage。
4. 一個 coherent mutation wave 完成後，Caliburn deterministic validator 檢查整份 candidate after-state，將連鎖診斷壓成最多五筆根因。
5. application 以共同小型 envelope 回同一主顧問；error result 只含資料，固定修復規則留在 Tool description／runtime policy。
6. 每個 authority／edit wave 在一個 product run 中最多一次 validation-driven model repair；success path 不新增 repair call。
7. 若修復後仍失敗，或相同 `(code, target, at)` 指紋再次出現，立即停止，不再讓模型花 token 重做同一錯誤。
8. repair exhaustion 回到該 wave 前最後有效 snapshot；先前已安全提交的 Work Understanding 保留，未通過的 JD wave 不進 review／approved。
9. 無論 provider、validator 或 unexpected error，run finalizer 都必須解除聊天與 JD 的 active-run lock；員工不能再遇到只能按「重試」卻無法繼續輸入的死鎖畫面。

「最多一次」是目前為效果、成本與產品可靠度設定的第一版上限，不是 OpenAI／Anthropic 的通用數字；若日後代表 transcript 證明一次明顯不足，可帶著成功率、重複錯誤率、token、latency 與 UI 失敗率再向 Owner 提案調整。

### 19.7 現行 production gap：保留成熟元件，只統一 model-facing seam

現行程式已具備大部分 primitive，不需要為本節重寫 runtime：

- [`WorkspaceDiagnostic`](../../apps/api/app/consultant/workspace_state.py) 已保存 `code／path／message／severity`；
- [`WorkspaceValidationService／Middleware`](../../apps/api/app/consultant/workspace_validation.py) 已限制 diagnostic 數量、驗證完整 after-state，並可要求一次 model continuation；
- [`WorkspaceToolWaveMiddleware`](../../apps/api/app/consultant/workspace_tools.py) 已用 `ToolMessage` 與原 tool-call ID 拒絕衝突 mutation wave；
- [`WorkspacePolicyBackend`](../../apps/api/app/consultant/workspace_backend.py) 已有 VFS path／create-only／exact-edit／delete policy。

真正落差是 model-facing result 尚未一致：部分 domain validation 是 typed diagnostic，部分 VFS／wave failure 仍是自由文字，例如 file exists、invalid path、replace-all 禁止與 overlap 說明。後續實作計畫只需：

1. 在 LangChain Tool middleware 建一個薄的 deterministic translator，把**已知** invocation／VFS／domain failures 正規化成共同 envelope；未知 exception 必須 bubble／terminal，不能捕捉成可修復文字。
2. 保持 ToolNode／ToolRuntime／LangGraph pairing 與 route，不手刻 Anthropic `is_error` 或 OpenAI `function_call_output`。
3. 加入 repair fingerprint、最後有效 snapshot rollback 與 unconditional unlock finalizer。
4. 以 model-safe path／handle 定位，不把 UUID、digest、完整來源或 traceback 暴露給模型。
5. 讓 Web 只顯示安全的產品狀態；raw Tool diagnostics 屬 agent trace，不直接當員工錯誤文案。

### 19.8 實作前驗收與最小 live smoke

實作計畫至少要覆蓋：

1. Tool call 與 ToolMessage 一對一且 call ID 正確；parallel call 也不得漏結果、重複結果或插入錯誤順序。
2. wrong type／enum、target missing、create conflict、zero／multiple match、invalid relation、stale、provider transient、unexpected exception 各有一個 deterministic test。
3. `workspace_effect` 與真實 Store after-state 一致，模型不會把未套用操作誤認為已成功，也不會重做仍存在的成功編輯。
4. 同一錯誤指紋第二次出現會停止；success path 不多一次 LLM call，repair path最多多一次。
5. repair 成功才產生可審 semantic diff；repair 失敗 rollback 且 UI 解鎖。
6. 實際 OpenRouter profile 至少用目前選定的 Luna 與一個 Claude endpoint 做小型 Tool-error smoke，確認 LangChain provider adapter 都把 ToolMessage 送回同一 agent loop；只驗 protocol／修復，不提前做完整產品 eval。
7. 記錄 calls、input／output／cached tokens、latency、error code 與是否修復；不得記錄完整員工原話或 Tool payload 到一般 telemetry。

### 19.9 來源索引與各自用途

| 官方來源 | 本節採用的資訊 | 不可過度延伸 |
|---|---|---|
| [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) | `call_id` pairing、strict、structured Tool output、application-known args 不交模型 | 不定義 JD error code 或一次 repair 上限 |
| [OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch) | model diff → harness apply／verify → status／error 回模型 | 不要求 Caliburn 綁 OpenAI patch syntax |
| [OpenAI GPT-5.6 Model guidance](https://developers.openai.com/api/docs/guides/latest-model) | Tool return／error behavior 要清楚、每個結果影響下一判斷時保留 direct feedback、效果優先於少 calls | 不證明最高 reasoning 或更多 steps 一定較好 |
| [OpenAI Codex apply-patch source](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/apply_patch.rs) | verification failure 可直接回模型修正 | Codex 的 Rust exception／file protocol 不是 JD domain schema |
| [OpenAI Codex app-server](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#errors) | terminal system errors 與 tool item lifecycle 分離 | 不照抄其 UI 或全部 error enum |
| [Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls) | `tool_use_id`、`tool_result`、`is_error` 與訊息順序 | 不要求 application 手寫 provider wire；LangChain 應映射 |
| [Anthropic Troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use) | strict／description／examples降低參數錯；Tool result 保持資料 | input examples 是否有益仍須依模型／失敗實測，不固定大量加入 |
| [Anthropic Fine-grained Tool Streaming](https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming#handling-invalid-json-in-tool-responses) | invalid input 可用小型 structured error 回同一 Tool call | Caliburn 第一版不因此必須啟用 fine-grained streaming |
| [Claude Code How it works](https://code.claude.com/docs/en/how-claude-code-works)／[Tools reference](https://code.claude.com/docs/en/tools-reference#lsp-tool-behavior) | 真實 tool／diagnostic 結果回到同一 gather-act-verify loop | 程式碼 LSP 規則不能取代 JD deterministic validator |
| [LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools)／[Agents](https://docs.langchain.com/oss/python/langchain/agents#tool-error-handling) | ToolNode、ToolRuntime、ToolMessage、middleware error seam | framework 不知道 Caliburn Duty／Task／OPKS invariant |
| [Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately)／[Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) | transient／LLM／human／unexpected 分流與 retry policy | 不替產品決定哪些職務問題一定要問員工 |

依 §0，本節是下一版實作計畫的目前研究基線，但仍可在新證據下經 Owner 討論後翻案。實作者不得自行退回自由文字萬用錯誤、無限 retry、所有錯誤都問員工，或為了「更 typed」再建立一個由模型填寫的巨型 error schema。
