# OpenRouter／Luna 對話延續 Compaction 設計

- 日期：2026-09-16
- Topic：`JD-R002／CTX-C001`
- Stage：**G4 WORKING DESIGN；Owner 已裁決方向，可進 G7 小型施工**
- 取代：2026-09-15「等待 OpenRouter、改 direct OpenAI、另選長上下文策略」三選一的未決狀態
- 不取代：Q019 顧問 Prompt、Skills、Memory A／B1／B2／C、JD relational writer、publication CAS、背景通知與准入規則

## 1. 決定與產品效果

採用 **LangChain／LangGraph → OpenRouter → OpenAI-only route → Luna** 的既定單一模型路徑，在 App 內加入一個薄的、非破壞式 `ContinuationCompactionMiddleware`：

```text
canonical conversation（Saver，完整且唯一）
    ↓ 只讀
選出已完成、可安全切割的舊對話前綴
    ↓ 同一 OpenRouter／Luna，獨立摘要 request
continuation_compaction = 摘要文字＋涵蓋邊界＋來源指紋
    ↓
本次模型 request view = continuity summary＋未涵蓋尾段＋當次 JD／Memory context
```

這個摘要只回答「對話／工作目前進行到哪裡、已完成什麼、下一步是什麼」。它不是員工原話、訪談詳記、工作資訊候選、工作理解、JD 或 publication basis。canonical conversation 不被刪除、改寫或用摘要取代；既有原話、詳記與 Memory 回查一律讀原 owner。

本輪不切 direct OpenAI，不把 OpenRouter key 傳給 OpenAI endpoint，不新增 fallback，也不再把 OpenRouter 原生 inline compaction 當成 App 可用的前置條件。OpenAI Responses 的 native compaction 可保留為未來 provider optimization；若日後採用，仍須轉成相同 request-only 效果並通過本稿驗收，不能改變資料 authority。

## 2. 為什麼不是重做一套 Memory 或摘要框架

| 元件 | 本輪處理 |
|---|---|
| LangChain／LangGraph | 繼續負責 agent loop、Tool 配對、middleware、state reducer、Saver／Store 與恢復 |
| OpenRouter／Luna | 產生顧問回答及需要時的 continuity summary；沿同一 route／receipt／成本邊界 |
| Caliburn 薄 middleware | 只負責安全切點、摘要狀態、request-only view 與失敗語意 |
| 工作理解 Memory | 沿既有 B1 詳記／候選、B2 knowledge／guide、C 即時修補及 publication 版本規則，完全不由 continuity summary 取代 |

不直接採 LangChain `SummarizationMiddleware`，因鎖定版本會以摘要與尾段更新 graph `messages`，不符合 canonical 原文不可被有損投影覆寫的要求。第一個切片也不直接採 Deep Agents summarizer：其額外 history offload、overflow 分支及 `ExtendedModelResponse` 與目前 `JdNoticeMiddleware` 的組合都需要比薄接合更多的權責修正。LangMem 目前未安裝，且既有研究已找到多工具切點與保存時點仍需產品接合；第一版不為了包住相同缺口新增依賴。

這不是另寫 agent loop、tokenizer、Checkpointer 或工作理解引擎。只使用公開 middleware／`ModelRequest.override`／`ExtendedModelResponse`／`Command`／模型 Runnable 接點；不複製框架 private helper。

## 3. 唯一新增的衍生狀態

在各 agent 的 typed state 增加一個可為空的整體欄位；欄位名稱與最小內容固定如下：

```json
{
  "continuation_compaction": {
    "format_version": 1,
    "summary_text": "...",
    "covered_through_message_id": "...",
    "covered_prefix_digest": "sha256:..."
  }
}
```

- `summary_text` 與涵蓋邊界必須作為同一個 state value 更新，不能只前移位置或只保存文字。
- `covered_through_message_id` 指向 canonical conversation 中實際存在的安全終點。
- `covered_prefix_digest` 由該次已涵蓋 canonical prefix 的穩定序列化產生，用來攔截邊界指錯、內容暗變或跨文件重用；模型不填這兩個欄位。
- 不建立新的 SQL table、原文副本、詳記副本或第二個 publication head。此 state 由既有 Checkpointer 按原 thread／attempt 保存。
- request view 是臨時值，不另存完整副本。只保存能重建它的 summary 與邊界。

若狀態格式、message id、digest 或 scope 不一致，視為 `invalid_continuation_compaction`。仍在安全輸入預算內時可忽略壞的衍生摘要、以 canonical view 繼續並留下診斷；已超出安全預算時必須明確失敗，不能猜切點、刪原文或無界重送。

## 4. 安全切割與增量摘要

### 4.1 切割單位

middleware 只摘要**已完成的舊互動 wave**：

- 不納入本次尚未得到顧問最終回答的最新員工訊息；
- 不切開 `AIMessage.tool_calls` 與所有對應 `ToolMessage`；
- 不切開同一次模型回覆的平行工具結果；
- 終點必須位於沒有 pending tool call 的完成邊界；
- 至少保留最近八則訊息，但若八則會拆開一個完整 wave，尾段向前擴大到安全邊界；
- 找不到安全切點時不生成新摘要。若因此無法形成安全 request，回報明確錯誤，不以任意最後 N 則替代。

已存在有效 summary 時，只把「舊邊界之後到新安全邊界」的增量連同前一版 summary 交給摘要模型，產生一份新的累積 summary；不每次重讀從第一則開始的全部原文。舊 summary 是可替換的衍生狀態，不形成版本歷史產品功能。

### 4.2 摘要內容

摘要 prompt 與主顧問 Prompt 分開；本輪不修改已校準的顧問訪談 Prompt。摘要指令沿既有顧問 runtime 已使用的「non-authoritative conversational continuity」原則，至少要求：

- 保留目前訪談／整併目標、已確認的更正、尚待回答事項；
- 保留已完成 Tool 的真實結果及後續仍需配對的名稱／識別，不把 request 當成成功；
- 保留不確定性、衝突與失敗，不補造員工未說的事；
- 不把摘要宣稱成 employee evidence、Memory、JD 或 source of truth。

摘要模型不取得 JD 編輯、Memory 修改、背景通知或其他業務 Tool。它只收到上一份 summary 與選定的 canonical prefix。

## 5. 預算、呼叫與保存時點

- 第一版沿既有 OpenRouter 顧問政策，以完整 request 約 **16,000 input tokens** 作摘要觸發起點，保留至少八則近期訊息；這兩項放入 role profile，不散落硬編碼。
- 預算判斷必須包含 system／developer instruction、JD／Memory context、Tool schemas、對話及輸出預留，不能只數 `messages`。
- continuity summary 輸出第一版上限 **2,048 tokens**。每個 model step 最多觸發一次摘要，不因摘要內容不滿意自動再問。
- summary request 使用同一個 OpenRouter model factory、OpenAI-only provider restriction、no fallback、`store=false` 與 route／usage receipt。SDK hidden retry 為 0；摘要 request 納入該 run 的 provider attempt、token、cost 與 elapsed 上限，不能繞過既有帳本。
- v1 不為摘要另加一個持久工作節點。摘要成功且主模型成功時，由同一 model step 的 `ExtendedModelResponse` 保存「模型結果＋summary／boundary」；主模型失敗時新摘要不推進，canonical 與上一個已保存摘要保持不變，恢復時允許在既有總預算內重算一次。這是明示的有限重算，不宣稱 exactly-once。

## 6. A 與 B2 的生命週期

### A：文件唯一對話

- `continuation_compaction` 位於 `ConsultantState`，跟隨該文件既有 `thread_id=document_id` checkpoint 跨回合恢復。
- 每個 model step 先由既有 `JdNoticeMiddleware` 組入當次 JD／source／Memory context，再由 compaction middleware 以完整 projected request 判斷預算；它只替換送模型的 `messages` view。
- summary 不進 `source_notice`、B1 source window、Memory reader 或 JD `basis_refs`。
- 不同文件的 runtime context、thread、summary、boundary 與 digest 不得互用。

### B2：單次有界整併 attempt

- 使用相同 middleware 行為，但 state 只存在於該 B2 attempt 的 graph／checkpoint。
- 同一 attempt 中斷後可沿原 state 恢復。
- publication stale 後既有流程建立新版重整 attempt；新 attempt 從空的 `continuation_compaction` 開始，只讀新版 Memory 及 runtime 受控提供的更正來源。不得沿用舊 attempt 的 summary、opaque context 或工具尾段。
- B1 仍讀固定 canonical source windows，不使用 continuity summary，也不因本決定增加 compaction。

## 7. Middleware 組合的必要修正

目前 A 的 middleware 順序讓 `JdNoticeMiddleware` 位於外層，compaction 位於內層；這可確保摘要預算看見已組入的 JD／Memory／Tool context，但內層觸發摘要時會回 `ExtendedModelResponse`。現有 `_bound_response()` 只接受 `ModelResponse`，會把合法結果判成 `invalid_consultant_response`。

施工必須讓 `_bound_response()`：

1. 同時接受普通 `ModelResponse` 與內層 `ExtendedModelResponse`；
2. 對底層 `model_response` 執行既有 terminal／refusal／message-id 驗證；
3. 保存內層 `continuation_compaction` command，再加入自己的 `jd_model_view` command；
4. 不讓外層更新覆蓋內層不同欄位，也不接受 compaction middleware 更新 `messages`、JD 或 Memory 欄位。

B2 沒有 A 的 JD notice，但仍用相同 compaction state 與 request-only 不變量。既有 `native_context_view` 保留作 Responses adapter 的已驗歷史接縫與 characterization test，不接進新 OpenRouter 正式路徑，也不刪除其證據。

## 8. 失敗與禁止降級

| 情況 | 唯一允許行為 |
|---|---|
| 未達門檻 | 不呼叫摘要模型，沿既有 request |
| 找不到安全切點 | 不移動邊界；仍可安全送出則繼續，否則明確失敗 |
| 摘要呼叫失敗／截斷／拒絕 | 不保存新狀態、不刪原文；依本次既有有限預算失敗 |
| 主模型在新摘要後失敗 | 不推進新摘要；恢復時可有限重算，所有費用照實記錄 |
| summary／boundary 損壞 | 不猜、不跨 scope 使用；安全預算外明確失敗 |
| OpenRouter 未來產生 native item | 不自動混用；另經相同契約驗證後才可作 adapter optimization |

禁止的替代方案：長期每輪重送全部原始訪談、刪除 canonical messages、把 summary 餵給 B1 冒充原話、把 summary 變成第二套 knowledge、切換 credential／provider、無界摘要重試，或為了通過測試把工具結果／目前員工訊息藏在 system prompt 重複提供。

## 9. G7 最小施工與驗收

施工只分成一個可審切片：

1. 新增 typed compaction state、公開 middleware 與 profile 設定；不加 dependency／table／migration。
2. 修正 `JdNoticeMiddleware` 的 response／Command 組合，正式 A 注入新 middleware。
3. B2 改用同一 OpenRouter model boundary＋attempt-scoped middleware，移除其 production direct Responses／native `context_management` 依賴；保留舊 adapter 契約測試作歷史證據。
4. 只跑受影響回歸；離線通過後再依既有費用授權規則提出一條有界自然 smoke，不在文件施工中讀 key 或呼叫 provider。

最少固定反例：

- Saver 重載後 canonical messages 逐項未變，summary＋boundary 可重建相同 request view；
- 最新員工訊息與多工具 call/result wave 不被切開；
- 已有 summary 的下一次只摘要增量，不重送全歷史給摘要模型；
- summary 成功／主模型失敗不前移狀態，恢復費用有界；
- A 同時保存 `jd_model_view` 與 `continuation_compaction`；
- A 跨回合恢復且兩文件隔離；
- B2 同 attempt 恢復，stale 新 attempt 不帶舊 summary；
- summary 不是 source／Memory／JD basis，B1 固定窗口不受影響；
- 完整 request 預算、輸出上限、OpenAI-only／no-fallback 與 usage receipt 均可觀察。

完成本切片只代表 A／B2 的 App-side compaction 接線與離線契約通過；不等於完整 App dispatcher、自然長訪談品質或 production authority 已驗收。

## 10. Memory 分層參考的界線

OpenAI 官方目前只直接說明：Codex 會在背景從合格的既有聊天產生本機 memory files，跳過 active／short-lived sessions；生成資料包含 summaries、durable entries、recent inputs 與 supporting evidence，且 extraction／consolidation model 可分別設定。這支持「原始對話、抽取產物、整併結果與導覽用途分開」，但沒有規定 Caliburn 必須採相同 schema、同一版號或 publication CAS。[OpenAI Docs：Memories](https://learn.chatgpt.com/docs/customization/memories#how-local-codex-memories-work)

Caliburn 的詳記重抽另存、穩定引用、publication head 與本回合讀取基準，繼續以本案既有 Q019 設計／程式／測試為 authority。討論者提供的 Codex source trace 可作研究佐證，但未進官方文件的內部欄位與 upsert 行為不得寫成 OpenAI 對本產品的契約。
