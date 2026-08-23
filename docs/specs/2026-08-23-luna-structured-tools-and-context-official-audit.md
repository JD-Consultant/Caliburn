# Luna Structured Tools／Context：官方文件審核與修正邊界

- 日期：2026-08-23
- 性質：施工前研究與偏移審核，不是 ADR
- 目標模型：GPT-5.6 Luna；不得以 Opus smoke 代替
- 本輪邊界：不呼叫付費模型、不改 production profile、不接 RAG、不增加 Agent／Tool

## 1. 為什麼重審

目前未提交的 runtime 調整同時碰到 provider strict schema、六個虛擬編輯 Tool、Skill 續讀、最小 context 與 prompt。這些 seam 若靠臆測修正，容易把單次 provider 錯誤擴成永久產品複雜度。因此本審核把每個選擇分成三類：

1. **官方／框架既有能力**：優先直接使用，不另造同功能機制；
2. **Caliburn 必須自訂的產品規則**：只有職務分析語意、Evidence、員工 authority 等框架不可能知道的內容；
3. **尚未被證據支持的 workaround**：先撤回或保持未決，不因已寫出 code 就保留。

本文件亦取代 plan-local `task-9-runtime-root-cause-audit.md` 將「取消 VFS Tool strict」視為合理 mitigation 的暫時判斷；後者當時沒有量測實際合併 schema，也未以 OpenAI／LangChain 最新 strict 指引重審，不能再指導施工。

## 2. 不可偏離的產品大方向

本輪所有技術選擇仍必須服務同一產品流程：

```text
員工原話
  -> 一位 AI 職務分析顧問按需讀取相關 Skill／既有資料
  -> 在持久化虛擬 JD workspace 續編
  -> application 驗證並投影員工看得懂的語意差異
  -> 員工接受／修改後接受／拒絕／延後
  -> 只有核准內容進 approved JD
```

AI 可以在員工尚未裁決時繼續看見並修訂 workspace，但不能暗中改 approved JD。Task／Duty／O／P／K／S 的分析方法保留為 Caliburn Skills；框架替代的是執行、保存、context、tool calling、structured output 與恢復機制，不是專業方法。

## 3. 現行事實，不靠猜測

### 3.1 套件與 Tool surface

本 worktree 鎖定：

- `langchain==1.3.15`
- `langgraph==1.2.11`
- `langgraph-checkpoint-postgres==3.1.2`
- `langchain-openrouter==0.2.7`
- `deepagents==0.7.5`

模型只看到 Deep Agents 的六個低階 VFS Tool：`ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`。沒有 Duty／Task／OPKS business Tool，也沒有專用 split／merge Tool。

### 3.2 實際 strict schema 指標

以目前 Pydantic final schema 與 Deep Agents 六個 Tool 經 LangChain strict conversion 後的實際 JSON Schema 計數：

| Schema | bytes | optional parameters | union sites |
|---|---:|---:|---:|
| final response（具名 consultant sections） | 6,189 | 0 | 0 |
| `ls` | 194 | 0 | 0 |
| `read_file` | 479 | 0 | 0 |
| `write_file` | 333 | 0 | 0 |
| `edit_file` | 656 | 0 | 0 |
| `delete` | 201 | 0 | 0 |
| `grep` | 1,667 | 0 | 3 |
| **合計** | **9,719** | **0** | **3** |

bytes 只作相對量測，不建立「小於 N bytes」的自訂門檻。即使拿較嚴格的 Anthropic 公開上限作跨 provider 保守檢查，目前也只有 6／20 個 strict Tool、0／24 optional、3／16 union，沒有超限證據。

## 4. 官方文件得出的結論

### 4.1 Structured Output 與 Tool 應維持 strict

OpenAI 官方說 `strict: true` 會讓 function call 可靠符合 schema，並建議總是開啟；LangChain 的 `ProviderStrategy` 也把 provider-native structured output 列為可用時最可靠的方式。`ChatOpenRouter` 官方 integration 同時支援 strict Tool 與 strict JSON Schema structured output。

因此：

- final response 繼續使用 `ProviderStrategy(..., strict=True)`；
- 六個 VFS Tool 也維持 `strict=True`；
- 只有實際 provider 回傳 grammar／schema 錯誤，且量測證明簡化仍不足時，才可依 provider 官方順序縮減 strict 面；不能因假設可能超限就全關。

### 4.2 六個 Tool 不需要 Tool Search

OpenAI 的軟性建議是每回合一開始少於 20 個 function；大量或罕用 Tool 才以 Tool Search 延後載入。目前只有六個互斥的編輯動詞，新增 Tool Search 只會增加 routing 與測試面，沒有官方門檻或本地量測支持。

Skills 則不同：Deep Agents 官方把 Skill 定義為按需讀取的 progressive-disclosure 能力，正適合 Task／Duty／O／P／K／S 方法。故保持「六個 Tool 常駐、分析 Skills 按需讀取」，不混成一套機制。

### 4.3 虛擬 workspace 與跨回合續編直接使用框架

Deep Agents 官方提供 VFS backends、`StoreBackend` 與 `CompositeBackend`；LangGraph Store namespace 可隔離持久資料。這正好承接每份 JD 的工作草稿與按需讀取，不再自寫 filesystem 或另一份 workspace table。

Caliburn 仍必須自訂：JD resource schema、Duty／Task／OPKS linkage、Evidence quote resolver、stale source 規則、semantic diff、員工 review 與 approved authority。這不是框架替代失敗，而是框架沒有也不應內建的職務分析 domain semantics。

### 4.4 OpenRouter routing 維持明確、不可偷偷 fallback

OpenRouter 官方指出 structured-output 支援取決於 endpoint，不只 model；應設 `require_parameters: true`。現行 adapter 已同時設定唯一 `only／order`、`allow_fallbacks=false` 與 `require_parameters=true`，符合官方做法，應保留。

### 4.5 Context 先使用 built-in，再保留窄 domain selection

LangChain 官方建議從簡單 context 開始、逐項加入、監測 token／latency，並優先使用 built-in middleware。Deep Agents 的 Skill、Store／VFS 與 LangChain summarization 已負責大量通用機制。

Caliburn 自訂 middleware 只應選擇無法由通用框架推導的最小 domain slice：目前焦點、blocking gap、相關 approved slice、workspace validation 摘要、本輪 source handle 與 authority revision。完整 workspace、Skills 與歷史來源仍按需讀取。

Skill 檔案是普通按需 context，不是只能讀一次的消耗品。摘要若已替換舊 Tool result，允許同一 Skill 再讀是框架語意一致的恢復行為；receipt 只去重觀測，不應把合法重讀變成 deterministic failure。

### 4.6 Prompt 應描述目標與邊界，不複製 wire schema 手冊

GPT-5.6 官方指出不必規定每一步，但要提供 domain context、hard constraints、approval boundary、success criteria，重要歧義才問人；Tool 的輸入、回傳與錯誤語意應放在 Tool description。

本輪曾做過 15 欄 `effects` 對照表的未提交實驗。即使 schema 可編譯，`secondary_text／tertiary_text／flag` 依 kind 改變意思，不符合 OpenAI「名稱與參數直觀、讓無效狀態不可表示」的 Tool/schema 原則，因此已撤回。

離線 prototype 已確認具名 `understanding／attention／gap／question／sufficiency` wire 維持 strict、全欄 required、0 optional／0 union；由 Pydantic field description 說明格式，pure mapper 還原 domain type。只有量測或 exact provider error 證明這仍太複雜，才依 Anthropic 官方順序進一步減少 optional、union 或 nesting。不得直接退回 non-strict，也不得先增加第二次 model call。

### 4.7 Luna 與 Responses API

OpenAI 對 GPT-5.6 的最新指南建議 reasoning／Tool／multi-turn workload 使用 Responses API，也把 Luna 定位為高流量、成本效率模型；`medium` 是平衡起點，`high／xhigh` 應有量測品質增益才使用，`max` 留給品質優先的最難工作。

但目前實作走官方 `langchain-openrouter` 的 `ChatOpenRouter`，該 integration 文件已明列 Tool calling、structured output、reasoning 與 provider routing，且標示為 beta。從「OpenAI 原生 Responses API 是建議方向」不能直接推導「目前 OpenRouter／LangChain adapter 的 Responses 路徑已與現行 Saver、Tool、usage receipt 相容」。這是需另做 compatibility spike 的推論，不是本輪 schema 修復授權。

因此現在不 Big-bang 切 Responses API；先讓既有 framework 路徑在 Luna 上完成一次乾淨 end-to-end。之後若要遷移，另驗 `previous_response_id`、persisted reasoning、compaction、prompt cache、Tool／structured output、usage receipt 與 LangGraph restore，再決定是否替換 adapter。

## 5. 對目前未提交改動的裁決

| 未提交調整 | 裁決 | 理由 |
|---|---|---|
| final 使用具名 compact provider wire＋local mapper | **保留，generic table 已撤回** | strict wire＋mapper 有官方依據；具名欄位仍為 0 optional／0 union |
| `ReceiptChatOpenRouter.bind_tools()` 在 final strict 時取消全部 Tool strict | **撤回** | 現行 6 Tool／0 optional／3 union 無超限；與 OpenAI always-strict 建議相反 |
| 本輪 HumanMessage 不再從 `/sources` 重讀 | **保留** | 已在當前 context，重讀沒有新增資訊；舊來源仍可按需查 |
| 同一 Skill 在摘要後可 idempotent 重讀 | **保留** | 符合 Skill 按需檔案與 summarization 語意；receipt 仍去重 |
| 平行獨立 reads／互斥 mutation wave | **保留原則，縮短 prompt** | framework 支援多 Tool calls；application 仍須拒絕重疊寫入 |
| 加入 Tool Search／PTC／multi-agent | **不做** | 六個 Tool、approval-dependent semantic work，沒有必要性證據 |
| 立即遷移 Responses API | **延後 compatibility spike** | OpenAI 原生方向成立，但目前 OpenRouter adapter 相容性尚未驗證 |

## 6. 下一個最小施工波

Owner 同意後的目前施工狀態：

1. **完成**：regression 證明 final 與六個 VFS Tool 同時保持 strict；未提交的全域降級 override 已撤回。
2. **完成**：離線 prototype／實測具名 provider output schema為 0 optional／0 union；generic `effects` table 已撤回。
3. **完成**：`effects` 15 欄手冊已從 system prompt 移除，恢復 Pydantic 具名欄位。
4. **進行中**：focused output／runtime/context／run-service tests 已 56 passed；尚需完整相關 API tests。
5. 只做一次 Luna availability canary；成功才做一次完整 browser／API 訪談。禁止 Opus、provider fallback、連續付費重試。
6. 報告實際 route、input／cached／reasoning／output token、cost、latency、Tool trace、workspace diff、validation 與 approved 未被暗改的證據。

## 7. 官方來源（查閱日 2026-08-23）

- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling) — strict mode、Tool 數量、Tool Search、`allowed_tools`、schema／description 原則。
- [OpenAI — GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6-luna) — Luna 定位、Responses API、reasoning effort、prompt、PTC 與量測原則。
- [Anthropic — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — final＋strict Tool 合併計數、20 strict Tool／24 optional／16 union 與官方縮減順序。
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output) — `ProviderStrategy` 與 provider-native strict output。
- [LangChain — ChatOpenRouter](https://docs.langchain.com/oss/python/integrations/chat/openrouter) — strict Tool、JSON Schema output、reasoning、routing 與 integration maturity。
- [LangChain — Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) — built-in middleware、summarization、逐項加入與可觀測性。
- [Deep Agents — Skills](https://docs.langchain.com/oss/python/deepagents/skills) — progressive disclosure、Skill／memory／Tool 分工。
- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends) — VFS、`StoreBackend`、`CompositeBackend` 與 namespace。
- [OpenRouter — Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs) — endpoint 能力與 `require_parameters`。
- [OpenRouter — Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection) — provider pinning 與 `allow_fallbacks=false`。
