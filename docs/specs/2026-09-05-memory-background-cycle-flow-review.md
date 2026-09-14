# Q017：B 背景 Memory 一次整理的流程審閱

> 2026-09-05 · `LLM-Q017` G4 · **B 流程經 Owner 暫時同意；資料與接線細節未全部核准，不授權施工**。
>
> 上一輪 A 的一輪流程已由 Owner「同意」；本輪只接續 B。父層為[框架接力 §3.3–3.5](2026-09-05-openai-shaped-memory-framework-composition-research.md#33-owner-最新方向先確認分工與完整接力再補協調機制)，有效狀態見 [current decisions](../current-decisions.md)。B/C 寫入協調仍由 [Q018](2026-09-05-memory-background-live-repair-coordination-research.md) 後續處理。

> **後續路由更新：**保存用途／直接交接與引用機制已接續討論，最新為[流程細節覆蓋索引](2026-09-05-work-understanding-memory-flow-working-design.md#7-openai-流程細節覆蓋索引)及[框架接力 §8](2026-09-05-memory-extraction-artifact-framework-handoff-review.md#8-引用接力的框架覆蓋核對)。§3.4–3.5 保留當時查證與取捨，不把其歷史「下一 gate」當成需重新詢問 Owner 的現況。表示／reader、觸發與恢復仍未選。

> **2026-09-06 最新見 §6.8：**Owner 指出原生推理延續正是目前需要的能力，詢問框架支援。官方連接器已有承接機制，不能與本案 OpenRouter 路徑已驗證混為一談。§6.7 的原生推理／顯式知識區分維持；§6.6 即時寫 Memory 仍是候選，不再把它當下輪必須先核准的方案。不新增筆記層、不取消 B／擴大 C 或施工。
>
> **同日 Owner 後續已同意分工：**原生 reasoning／thinking 承接多輪分析，長期 Memory 提供可修訂知識與長訪談 Context；整體接線集中於[組合提案 §7](2026-09-05-memory-framework-end-to-end-composition-proposal.md#7-原生推理延續長期-memory目前整體接線)。本稿保留 §6.5–6.8 的需求、候選與查證沿革，不再重問是否另存每輪筆記；B 不讀取／解密主顧問 opaque reasoning，不取消原兩階段。

## 1. 本輪問題與結論

**問題：B 如何接收一批對話，產生可補查的中間內容，整併現有 Memory，並交付真實完成結果？**

沿用已暫准的兩階段目的：先整理對話，再對照現有 Memory 整併。不是每則訊息各生一筆 Memory，也不是每輪同步呼叫 manager。B 是一條背景工作流程；其中 extraction 可是模型步驟，consolidation 是可按需用工具的 Agent，不表示每個方塊再開一個 Agent。

本稿區分：**官方事實**、**已准方向**、**組合建議／待定接線**。沿用既有研究，只補觸發差異、交付與失敗邊界；不宣稱這是每家一致的唯一最佳實作。

## 2. 何時啟動：目的相近，觸發方式並不一致

| 官方公開產品／框架 | 實際說明 | 不能據此推論 |
|---|---|---|
| Codex local memories | 等合格聊天足夠閒置才背景處理；跳過 active／短暫 session，可能受 quota 門檻影響 | 使用者每發一則訊息就整理，或所有產品固定等相同時數 |
| OpenAI Sandbox Agents SDK | run 結果追加至 conversation file；sandbox session 關閉時處理累積內容 | 關閉 sandbox 等於永久結束使用者的 conversation |
| Deep Agents 官方 recipe | 另部署 consolidation Agent，配 recent-conversation tool 與排程；提醒 cadence／lookback 不合會漏處理或重複 | 開啟 Memory 就已有完整排程；官方範例的六小時是必要規格 |

直接來源：[Codex local memories](https://learn.chatgpt.com/docs/customization/memories)、[SDK generation／multi-turn](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/#generate-memory)、[Deep Agents background recipe](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)。

**[已准方向＋本輪說明]** B 處理已選定、已保存的對話範圍；不要求整個長期 conversation 永久結束。尚在累積的新訊息不自動滲入一個已開始抽取的輸入範圍。這是原 Q014 的「封存互動片段」接線方向，不冒充 OpenAI SDK 原生只讀新 delta 的規則。

**[仍待定]** 閒置觸發、定時掃描或組合，以及切段邊界、重疊消歧範圍、頻率、executor。本輪只確認不要每次訊息無條件付完整整理成本；不因某次「沒有可處理輸入」而把尚未處理的資料當作完成。

## 3. B 的一次正常整理

```text
選定本次要處理的已保存對話範圍
    ↓
Extraction：對話摘要＋候選記憶資訊
    ↓
Runtime 保留可供後續補查／重用的中間產物（接法待審）
    ↓
Consolidation Agent：對照目前 Memory
    ↔ 搜尋／讀取 Memory
    ↔ 必要時補查相關對話摘要
    ↔ 編輯 Memory → 讀工具實際結果 → 必要時修正
    ↓
維護小型 Memory 導覽
    ↓
記錄本次實際結果；供後續 A 讀取
```

**圖示邊界：**保存有後續讀者與重用目的，不是 consolidation 語意判斷的必要前置；也不代表須結束本次工作、等待下次排程或再叫模型讀回。Owner 追問後的保存理由與直接交接比較見 §3.5，先確認用途，再選保存接法。

### 3.1 Extraction：先分清本段互動與可重用知識

**[官方事實]** SDK Phase 1 由對話形成 summary 與 raw memory extract；Phase 2 才整併。`raw_memory` 不是原始逐字對話。Codex 的 `rollout_summary`／`rollout_slug`／`raw_memory` 詳義與固定原始碼，已在[OpenAI 系統圖 §5.6](2026-09-05-openai-conversation-context-and-memory-system-map.md)核對，不另創資料分層。[SDK Phase 1](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/#generate-memory)

**[組合建議]** 沿用 LangChain structured output 形成兩種語意產物，由 LangGraph step 接續保存：

- **對話摘要**：保留本段發生什麼、討論脈絡、更正、結果與未明事項，供之後補查；不是逐字來源。
- **候選記憶資訊**：值得與既有 Memory 比對的內容；尚未直接成為目前 Memory。沒有值得保留的資訊可以不新增 Memory，不強迫湊候選。

中間產物可供 B 恢復與 Phase 2 深讀，不是 A 的短 Context compaction；兩者不可互換。選定範圍、可信來源定位與執行時間由 Runtime 處理，不要求模型自己捏造。精確 schema／locator 沿用待決路由，本稿不新增必填欄位。[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)、[LangGraph task 持久結果](https://docs.langchain.com/oss/python/langgraph/functional-api)

**後續小元件核對：**[抽取產物接力子稿](2026-09-05-memory-extraction-artifact-framework-handoff-review.md)已分清 model wrapper／agent／LangMem extractor、task result／Tool artifact，以及 BaseStore record／StoreBackend file。Runtime 可直接保存產物，無須模型再叫存檔 Tool；保存表示與來源 locator 尚未選定，不從本節圖示推論自動發布或整批交易。

### 3.2 Consolidation：對照現有內容，不是候選逐筆照存

**[官方事實]** Codex 固定 pipeline 先同步選定的 extraction 產物並比對處理範圍；沒有有效輸入差異時可略過 consolidation model。整併 instructions 要求按需讀取相關 summary、保守修改既有內容。這與「模型讀完判斷沒有新知而不修改」是兩種不同的 no-op。[Codex lifecycle README](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/README.md)、[Consolidation prompt](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md)

**[組合建議]** B 的 `create_agent` 接收本批候選與可讀取位置，再用獨立 filesystem 工具搜尋、深讀及修訂：重複就不新增；新細節補入適合的內容；確有獨立用途才另立內容；明確更正才修訂過時敘述。情境差異與未解矛盾不能只因較新就抹掉。這些是整併 instructions 的語意政策，不是要另造同名 CRUD／MERGE／RETIRE 工具或硬性狀態欄位。

沿用已准可見範圍：**B Phase 2 可以補查相關 summary，但不直接接 A 的原始對話回查權限。** 所核對 Codex 背景 prompt 明確禁止讀 raw sessions；不能把前台按需回查和背景整併混為一談。[Codex 補查與 raw 限制](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L159-L167)

工具回傳實際結果後，B 才判斷是否修正、繼續或結束；由官方 Agent loop 承接，不自造 while-loop。LangMem manager 不等於這個中途補查流程，也不為湊元件而再固定呼叫一次。[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)、[框架事實圖 §5–6](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md)

### 3.3 Guide 與交付：正文先成立，導覽才有依據

**[已准方向]** B 處理正文後維護小型導覽，供 A 找路；不用另叫摘要 Agent，也不把導覽變成另一份獨立知識權威。OpenAI 的正文／guide 分工與 prompt 要求見上述 consolidation source 及[系統圖 §5.7](2026-09-05-openai-conversation-context-and-memory-system-map.md)。

**[待審的完成邊界]** 交付依實際執行結果，不只採信 B 最後說「完成了」。沒有改動、確實處理完成、或有未完成步驟，要能被 Runtime 分辨；這不是要模型填一整份稽核表。導覽只因正文受影響才需相應維護，不要求每次重寫所有檔案。

A 之後透過既有 hook／Tool 讀取才看到更新；已送出的模型 request 不會因背景存好 Memory 自動換掉。**何時重新載入與 B/C 交錯的精確保證屬下一輪接力／Q018**，本稿不把兩者的共享 Store 當成自動一致性。

### 3.4 呼叫計數釐清：兩個階段，不是固定兩次 API request

> 2026-09-05 Owner 追問後核對。這是已准 B 分工的計數說明，不是核准中間產物格式、模型選擇或呼叫上限。

**[本輪重新取得的官方證據]** Sandbox Agents 文件明說：先抽取 conversation summaries 與 raw memories，再整併為 `MEMORY.md` 與 `memory_summary.md`。Codex 官方也分開提供 `memories.extract_model`／`memories.consolidation_model`。所以 Owner 所述「先抽取，再依抽取內容整理 Memory 並更新導覽」符合這兩個公開產品的責任形狀；不是以同一次模型回應直接完成全部工作，也不代表所有 OpenAI Memory 產品都有同一個實作。[Sandbox Memory generation](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)、[Codex Memory 設定](https://learn.chatgpt.com/docs/customization/memories#configure-local-memories)

| 責任／動作 | 模型看到什麼／完成什麼 | 正確的計數方式 |
|---|---|---|
| Phase 1 extraction | 選定對話 → 同份抽取結果內的摘要＋候選記憶資訊；Codex 快照另有 slug | 是抽取模型工作，不因兩種產物就一定拆兩次。處理多份輸入、失敗重試會改變實際 requests |
| 中間產物保存／呈現 | Runtime 保存解析結果與來源位置，按需呈現可讀內容 | 普通程式 I/O 本身不呼叫 LLM；不增加第三個「存檔模型」 |
| Phase 2 consolidation | 本批候選＋既有 Memory；按需查摘要、去重／補充／修訂 | 是另一個 Agent 工作流程，內部可有多次 model↔Tool 往返；不是固定只有第二次 request |
| 更新 Memory 導覽 | 讓小型導覽反映整併後的 Memory 正文 | 屬同一 consolidation 工作流程；不必另開第三個專職導覽 Agent，但產生／寫入／確認導覽可能占用該流程的後續 model steps |

Phase 2 的搜尋、讀取、修改及導覽最後更新，沿用既有[OpenAI 系統圖 §5.7](2026-09-05-openai-conversation-context-and-memory-system-map.md#57-第三個細部邊界phase-2-如何形成-durable-memory)及其固定 source，不從檔名推測呼叫數。OpenAI 官方 function calling 也明示：模型提出 Tool call → 程式執行 → **再發 model request 帶回結果** → 模型回答或再呼叫工具。[官方 Tool calling flow](https://developers.openai.com/api/docs/guides/function-calling#the-tool-calling-flow)

**因此不寫「B 固定兩次 LLM 呼叫」。** 正確是「一次背景整理有 extraction、consolidation 兩個階段，導覽在後者維護」；實際計費要加總兩階段所有 model requests。若某份抽取以單次 structured request 成功，便是該次抽取的 1 次，加上 consolidation 的若干次；這只是計數例子，**不是官方固定次數或本案新 budget**。相同模型可擔任兩階段，不必選兩款不同模型；模型選型仍待相應 gate。

**不是每則訪談訊息都跑兩階段：**Codex 官方會略過 active／short-lived sessions、等待足夠閒置並考量 quota；Sandbox SDK 的公開觸發是 session 關閉後整理累積內容，兩者不能混成同一排程。既有 Codex 快照還有「輸入無差異就不啟動 consolidation model」；與模型已被呼叫、讀完判斷無需改動是兩回事。選取多份 extraction 產物也可以交給一輪 consolidation，不是每份候選各跑一次完整整併。來源見 §2、§3.2 及上述官方 Memory 頁面。

**Finding／next gate：**兩階段與導覽所屬位置有直接官方依據，但這只回答官方如何分工，不證明保存方式或兩階段是所有產品的唯一最優解。Owner 接續要求審核「為何先保存、能否直接交接」，由 §3.5 承接；不得以已同意計數說明為由阻止此審核。本次未新增精確 schema、模型、第三個 Agent、排程或 API 實驗。

### 3.5 保存中間結果：為了後續補查／重用，不是才能整併

> 2026-09-05 Owner 要求重新核對。**官方事實已釐清；保存與接續建議待審，未核准物理接法。** 本節取代「保存失敗就表示抽取內容無效」或「分兩階段所以必須分兩次排程」的讀法。

**先分清三件事：**

1. **兩階段分析**：先從一段對話抽出素材，再拿素材對照現有 Memory 去重／補充／修訂。Owner 提出的「抽取完直接交給整併」仍是這兩個語意階段，不等於同一次模型回應做完一切。
2. **中間結果保存**：讓這次產物在目前程式／run 結束後仍可取得。這是資料生命週期，不是另一輪推理。
3. **交接／排程**：當次能立即接續，也能由之後的背景批次選取；是否保存，不能單獨決定是否要等下一次排程。

**[此次重新取得的官方產品證據]** Sandbox Memory 文件同時公開生成順序、`raw_memories/`／`rollout_summaries/` 等保存位置，以及未來 run「導覽→搜尋 Memory→需要細節才開 rollout summary」的讀取流程。因此中間 summary **不是整併完就再也沒人讀的臨時回答**；它也服務後續按需補查。Codex 產品頁同樣說保存 summaries、durable entries、recent inputs 與 supporting evidence，並分開設定 extraction／consolidation model。[Sandbox Memory 的生成、layout 與讀取](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)、[Codex Memory storage／configuration](https://learn.chatgpt.com/docs/customization/memories)

**[沿用已研究的固定實作證據，不宣稱本輪重抓 source]** Codex 的 Stage 1 結果存 DB，Phase 2 再選一批結果、同步候選與 summary，對照上次成功 baseline 決定是否啟動整併；細節及固定來源見 [artifact 詳表 §4.3–4.5](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md#43-phase-1rollout_summaryrollout_slugraw_memory)。這說明保存還能供**後續批次重用已有抽取結果**，而不只是當次函式之間傳參數。該 Codex 快照不等於所有 OpenAI 產品的固定 DB／排程契約。

| 產物 | 保存後的實際用途／證據邊界 |
|---|---|
| 對話摘要 | B 按需取得本段脈絡；未來 A 也可深讀。它仍是模型整理內容，不是逐字原文或 current truth。後續讀取有上述直接官方契約 |
| 候選記憶資訊 | 供本次或之後 Phase 2 選取／比對，不必重新從原始對話抽取。批次選取重用有既有 Codex source 證據；不代表每份候選永久保存、每輪都注入或全部變成 Memory |
| 已完成抽取的執行結果 | 框架可供失敗恢復時重用；**不必為了重試另造同一份結果庫**。LangGraph 已有 checkpointed task result，但其恢復介面不自動等於 A／B 的摘要 reader；保存位置與讀者介面仍須分開核對。[Functional API checkpointing](https://docs.langchain.com/oss/python/langgraph/functional-api#functional-api-vs-graph-api) |

**[推論，不冒充官方保證]** 保存並重用已成功抽取的結果，可以避免某些重試／重新整併時再付 extraction 成本，亦能保留較完整的本段脈絡；實際是否節省、品質是否更好，仍取決於讀取及恢復流程。單純多存一份資料，不會自動提升模型判斷，也不保證所有細節無損。

**對 Owner 替代方式的判斷：直接交給整併是可行的。** 其輸入需要的是有效抽取內容，不是「這段內容曾被寫進資料庫」這個事實。框架 parsed output 已是程式可傳遞的結果，接點見 [抽取產物子稿 §2.1](2026-09-05-memory-extraction-artifact-framework-handoff-review.md#21-三個官方接點責任並不相同)。但若只傳遞、完全不保留，未來 A／B 就不能直接回讀這份摘要／候選，除非另有保存可查，或重新處理原始對話。那不是同樣效果下免費刪掉一步，而是不同生命週期取捨。

**[本輪建議／待 Owner 審核]** 保留中間產物的補查／重用能力，當次不為保存而人為延後整併。成功保存後，可將手上同份抽取結果與可讀位置直接交給 B；**不用僅為交接再重讀一次 DB、重跑 extraction、另開一個「存檔 Agent」或排到下次。** B 需要時的摘要 Tool read 仍有用途，與不必要的整包重讀不同。這是框架組合建議，不聲稱 OpenAI 所有表面都用同一個即刻交接實作。

**本輪更正／未決：**先前把保存畫成必經方塊，沒有把以上用途、執行時機及失敗含義分開，表達不完整。§4 改為分清「抽取失敗」與「有效結果未持久保存」；不能假造成功 reference，但也不能因此說結果語意必然無效。是否保存後才啟動 B、失敗時如何續做／重排，仍須在所選接法及 Q018 定義。記錄、檔案、checkpoint 或多層介面的選型不由此題自動核准；也不改 `MEM-Q005` 的 JD／Memory sibling-effect 決策。

**下一個 gate：**Owner 先審核上述保存目的與直接接續的取捨，再審產物接法；不重做整套 OpenAI／跨家 Memory 研究。若 Owner 改選不保留中間產物，須明列 A／B 如何維持已准的後續摘要補查能力，不能靜默刪掉讀取層。

## 4. 遇到失敗：這輪只確認責任，不偷設計交易系統

| 情況 | 本輪需維持的語意 | 尚未決定 |
|---|---|---|
| 抽取／解析失敗 | 不將不存在／不可用的抽取結果當作有效輸入 | 重試數、批次其他輸入能否繼續、如何重排 |
| 抽取有效但中間產物保存失敗 | 不宣稱持久保存成功，不提供假成功的可讀位置；不把 I/O failure 當成抽取語意無效 | 是否先補存再啟動 B，或允許當次交接並明確處理後續可讀性／恢復，須隨接法及 Q018 決定；不預設其中之一 |
| Memory edit 回傳可修正錯誤 | 實際錯誤回 B 模型，允許有界修正；不保證一定成功 | 各錯誤的 retry／用量政策 |
| 部分正文成功，但另一筆／guide 失敗 | 不宣稱整批完整成功，也不假設已寫內容自動回滾 | 部分成功恢復、發布與 B/C 協調 |
| 本批已處理，沒有值得改的內容 | 可正常完成且不修改 Memory；與執行失敗分開 | 精確結果契約由後續設計承接 |

這是根據公開錯誤／恢復能力提出的交付要求，**不是宣稱 OpenAI／框架已提供同一套整批交易**。Codex 有 job failure／processed selection 記錄；SDK generation 也有捕捉錯誤記 warning 的路徑，不能由「flush 返回」推論所有 Memory 都成功保存。[Codex Phase 2 source](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/phase2.rs)、[SDK generation source](https://github.com/openai/openai-agents-js/blob/e6c3663017e3e36af67370a4bc09db674ef0fd9f/packages/agents-core/src/sandbox/memory/generation.ts)

LangGraph 可保存完成的 task 結果供恢復，但 replay／未完成 task 仍需正確處理，不能保證任意 Store 副作用 exactly-once；Checkpointer 也不是背景 scheduler。精確接線留 Q018，現在不新增 lock、CAS 或自訂協調器。[Functional API：idempotency](https://docs.langchain.com/oss/python/langgraph/functional-api#idempotency)、[父層 §4.4–4.5](2026-09-05-openai-shaped-memory-framework-composition-research.md#44-背景與-c-都會更新同份-memory框架是否已解決)

## 5. 審核、成本與下一步

- **方向一致**：A/B 分工；C 仍是 A Tool；B 有 extraction／consolidation 及中途補查，不改成每輪同步 manager。
- **框架邊界明確**：可重用 structured output、checkpointed workflow、Agent loop、filesystem／StoreBackend；輸入選取、instructions、artifact 接力與調度仍需組裝，不宣稱零自訂。
- **成本不是零**：B 多出抽取與整併呼叫，補查可能再增加 steps；批次、無新輸入略過、增量整理可減少不必要工作，不能無測試聲稱一定更便宜或品質最好。
- **不照抄所有預設**：SDK 公開的長對話截斷、最近 N 份保留，以及 Codex retention 參數是各自產品政策；本稿未核准任何原始資料刪除或細節遺失策略。相關差異已有[系統圖 §5.6–5.7](2026-09-05-openai-conversation-context-and-memory-system-map.md)記錄。
- **本輪無 implementation／spike／付費模型測試**。只作文件核對，不宣稱新組合已跑通。

**下一個 gate：** Owner 已同意 B 及[父層 §3.6](2026-09-05-openai-shaped-memory-framework-composition-research.md#36-資料細節應何時討論已同意順序與完整範圍)的資料對照順序；最新先審 §3.5 保存目的／直接接續，再審中間產物接法。其後對照 current Memory／導覽，再串框架流程與 Q018。既有原文對照見 [Conversation gap review §8](2026-09-05-conversation-compaction-framework-gap-review.md#8-q017-對話資料的框架存取對照)。不是各名詞另存一份，不是已核准最終契約；LangMem 局部能力及 manager 邊界見父層 §3.2。只補本次被指出的用途／失敗表達缺口，不重做其餘已完成的概念研究。

**重開條件：** Owner 改變目的／分工、官方契約或版本改變，或後續最小相容性驗證推翻接線。核准一樣是可翻案的 Working Decision，但須記錄理由並討論，不得靜默改回舊方案。

## 6. 前台分析如何留下來：是否需要取消背景整理？

**2026-09-06／LLM-Q017，Owner 新問題；建議待審，不施工。** 產品仍是一個主顧問接收員工訊息、分析、按需使用 JD 工具並回答；另一個角色負責 Memory 整理。不是理解 Agent、判斷 Agent、JD Agent 的固定接龍。「兩個角色」不保證只發兩個 API requests；本節不改 §3.4 的計數。

### 6.1 不可假設模型想過的事都會出現在聊天裡

**Official fact：**Anthropic 公開區分 thinking blocks 與一般回覆，thinking 可只回摘要或省略可讀文字；其 provider-specific continuation 能力不等於一份可供任意 Memory 整理模型讀取的完整分析記錄。[Thinking output／display](https://platform.claude.com/docs/en/about-claude/models/extended-thinking-models)

**效果推論：**主顧問有原始輸入可重新分析，但未輸出、未經工具保存的結論不能被我們當成「必定已保留」。近期歷史確實包含某項結論，也只提供重用機會，不保證模型絕不重做；新資料使舊判斷改變時，本來就應重新檢視。需要保留的是可陳述的工作結論、限制、未解問題，不是模型完整 chain-of-thought。

### 6.2 查證後的實質缺口：保留 AI 提出的問題，不等於相信 AI 的答案

既有 [G4 §15.2](2026-09-04-llm-machine-effects-and-sibling-results-working-design.md#152-extraction-的責任邊界) 將 extraction 聚焦員工新陳述，禁止背景自行製造 coverage gap、把模型內容當員工事實；這些限制有用途。但若實作者進一步把 assistant 只用來消歧，丟掉前台**已明確提出的待確認工作判斷／未解問題**，就不符合 Owner 此輪的分析延續需求。

**建議澄清，待 Owner：**背景可保留「顧問暫認為 A/B 屬同類工作，已詢問責任是否相同，尚未獲答」這個互動結果；不能寫成「員工已確認 A/B 相同」。員工陳述、AI 暫定解讀、工具確實執行的結果須在內容上分清，無須本輪新增強制狀態欄位。背景不替未回答問題自行補答案，也不負責另做一次 JD 分析。[既有 summary／candidate 用途](2026-09-05-openai-conversation-context-and-memory-system-map.md#兩份-derived-artifact-的責任不同) 已包括結論、脈絡及未明事項；本輪只是檢查其輸入能否實際留下這些內容，不新增第六種 artifact。

### 6.3 前輪三種接法與推薦（不足之處由 §6.5 接續）

| 接法 | 效果與代價 | 本輪判斷 |
|---|---|---|
| 主顧問按需維護 Memory，不設背景整理角色 | 少一個背景角色及跨角色同寫問題；可累積幾輪才整理，並非必須每輪更新。但整理發生時增加前台延遲／多工，仍要維持詳記、引用及導覽效果 | 可選替代，不因「分析型」就認定必要或最佳；不得把它誤寫成只有「每輪完整重整」這種選項 |
| 主顧問留下可接續成果，背景按批整理；C 保留窄修補 | 日常先靠近期問答／實際工具結果接續，背景對累積內容去重、補充、修訂；有更新延遲及既存 B/C 協調問題 | **前輪推薦；§6.5 已指出不適合作預設** |
| 只靠聊天與 compaction，取消可修訂 Memory | 流程更少，但不再提供既定工作理解／詳記導覽、持久修訂與深查功能 | 不符合目前已准效果，不建議 |

**Official fact：**LangChain 官方同時列 hot-path 與 background 的取捨：前者即時、但增加延遲與主 Agent 多工；後者移出主要互動路徑，可選時機避免重複整理。Deep Agents 官方預設 hot path，另提供獨立 Agent 背景 consolidation recipe；沒有「所有分析型應用必須背景」或「同一輪必須整理」的通用規定。[Memory overview：Writing memories](https://docs.langchain.com/oss/python/concepts/memory#writing-memories)、[Deep Agents background consolidation](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)

**討論軸線：**誰整理（主顧問／背景角色）與何時整理（每輪／累積一段／按需）是兩個選擇。將 Memory 交回主顧問不代表必須每輪完整整理；維持背景也不代表重要更正一律得等待。此處只比較角色取捨，不偷偷固定觸發頻率。

**本案推薦，不冒充官方唯一最優解：**前台負責理解／追問／按需編輯 JD；背景接收已保存的完整問答及相關已輸出結果，整理成既定詳記、候選、工作理解與導覽。背景仍需抽取及整併判斷，不宣稱「完全不再分析」，但不應再獨立訪談或重新做整份 JD。先不新增專職筆記 Agent、每輪強制 Memory 寫入或大型 structured output。

重要且適合給員工核對的結論，自然寫入一般回覆，例如「這兩個網站暫時看作同一類接案工作，但第二案是否還含維運，需要再確認」。已由 JD 工具留下的結果可供後續參考，不必全文重貼聊天。**若有重要且不適合展示的結論，仍需另選明確保存出口；不能以本案推薦假裝所有分析都已覆蓋。** 可評估框架 state／既有 Memory Tool，但會涉及額外輸出或 C 範圍，未核准前不私加。

### 6.4 前輪停止線（最新待審見 §6.6）

- 已核對 register／流程、B 全文、既有 OpenAI artifact 分工與 G4 extraction 限制；新查官方 thinking、Memory hot-path／background，沒有重做整套 OpenAI 研究。
- **唯一待審：**是否維持兩個角色，並讓背景保留前台已輸出的、明確標為暫定的分析成果／未解問題？取消背景、擴大 C 與新增內部筆記均未獲授權。
- 這題通過後只收斂最小交接契約：前台實際留下哪些內容、背景從哪裡拿、何時觸發、錯誤如何回報與續做；沿用既有能力與引用，不再逐名詞開新研究。
- 進實作前尚須交代原有 B/C 同寫協調、摘要配對與預算的真實阻塞，不能宣稱此輪已全部解決。先整理一份有代表情境的接線設計與必要驗證清單，再依 gate 取得實作授權；不新增大型 eval 或付費測試。

### 6.5 Owner 再澄清：工作理解要能內部保存，不以展示給員工為前提

**需求已澄清，機制建議待審。** 在背景尚未整理出 Memory 的前幾輪，主顧問已從員工回答形成工作案例、細節、暫定理解及未知事項；對外往往只問下一題。Owner 要把**本次已整理出的工作知識**留在內部，供下輪 Context 接續，不要求全部寫進聊天，也不希望再叫另一個模型才重建相同理解。這是分析成果，不是要求擷取模型隱藏 chain-of-thought。

**修正前輪推薦：**這不是日後才可能出現的「不適合展示」例外，而是主要使用情境。只保存使用者可見問答／JD 工具結果，再等 B 形成 Memory，不能保證保存主顧問當時的理解；前輪推薦不再作預設。可保留短小的對外追問，同時有較完整的內部知識，不把兩者綁成同一份輸出。

**官方可用模式：**Anthropic Memory Tool 允許執行中的模型 create／read／update／delete 持久知識，程式執行操作並回傳結果；不需要另叫一個抽取模型才能首次存入。Deep Agents 官方也以對話中的 Memory 寫入為預設，背景整併是另一個選項。因此「主顧問把學到的知識留下」有直接公開機制，不是自行發明新種記憶。[Anthropic Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)、[Deep Agents Memory](https://docs.langchain.com/oss/python/deepagents/memory)

**推薦接續研究的最小方向：**主顧問按本輪實際新增／修訂的理解，直接寫入同一 JD scope 的工作 Memory，之後組 Context 時取得相關最新內容；尚無 Memory 就能建立，不限「修理已存在的過時紀錄」。只記本輪有用的新內容／修正，不要求每輪重寫全部 Memory，也不把未知補成事實。這是 public Memory Tool／讀寫元件可承接的方向；精確資料表示、輸出方式、讀取保證與接線尚未選定。

背景若保留，可承接較大範圍的去重、整併、詳記與導覽維護、對照原始問答找漏；不再是唯一能首次形成工作理解的角色，也不應忽略前台已保存的成果而一律從零推導。這會改變目前 B/C 的分工，**不是已核准的窄 live repair 原封不動就覆蓋**。是否保留全部 B 兩階段及如何利用原有詳記／候選引用，須明列功能收益／成本再決定；不能為加速就偷偷刪掉已有深查能力。若直接維護同份 Memory 足夠，優先避免再加第二份內容近似的筆記庫；若需短期工作筆記，應先說明額外用途。

**成本界線：**同一主顧問 run 可產生內部知識及對外回覆，不代表同一次 API request 必定完成。Memory Tool 內容仍花輸出 tokens，回傳結果後可能有後續模型呼叫；節省的是重新抽取／重建理解的機會，不保證總費用必降或零重複分析。新證據出現時仍需重看舊理解。局部記錄與全域整併是不同工作量，無須因每輪資訊少就連已得到的局部成果也延後保存。

**Closure／下一步：**本輪只確認需求並更正推薦，無實作／模型測試；官方 primitive 已有足夠依據，停止擴大名詞研究。下一題聚焦「主顧問直接維護同份 Memory」的最小輸入、保存結果與下輪載入，並列出對 B/C 既有決策需修改之處交 Owner 審閱。尚未選 schema／新增 Tool 名稱／排程或核准施工。

### 6.6 最小接法與角色取捨：增量寫入，不每輪完整重整

**LLM-Q017／G4 建議待 Owner 審核；2026-09-06。** Owner 要求加快且有效率。本節只收斂 §6.5 的內部成果保存，不重新開 Memory 表徵／OpenAI 全流程研究；也不把「繼續」記為新架構已核准。

**定向補證的官方接點：**

- Anthropic Memory Tool 是模型提出操作、程式執行並回傳的正常 Tool loop；支持直接 create／edit，不必另設抽取 Agent 才能保存本輪理解。[官方 handler 與命令](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#implement-the-memory-handler)
- LangChain `create_agent(store=...)` 的官方範例以 `ToolRuntime.store` 讀寫同一 Store，可信 scope 由 runtime context 取得；可用 PostgreSQL。這證明既有根 Agent 能直接操作持久 Memory，不代表官方例子的 profile schema 就是本案應採的知識格式。[Read／write long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- Deep Agents 公開對話中直接修改 Memory 與背景 consolidation 兩種模式，也列出延遲／多工／更新延後的取捨。它們都是官方模式，**不證明本節混合分工是所有廠商共同標準或品質已實測最好**。[Memory／background consolidation](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)

**建議資料接力（Caliburn mapping，不是廠商逐字流程）：**

1. 主顧問讀近期問答及相關目前 Memory，分析員工這次回答；沒有 Memory 也可開始。
2. 有值得接續的新細節、理解或待釐清內容時，以 Memory Tool 建立／局部修改同份工作 Memory。未知仍寫成未知，不當成已核實事實；沒新內容可不寫。既有搜尋／深讀與引用效果保留，不強制每輪重寫所有檔案或所有 artifact。
3. 程式保存並回傳實際成功／錯誤；模型處理結果後對員工回答或追問。內部知識與對外回覆分開呈現，不需展示完整理解。不額外叫一個模型重新抽取主顧問剛產生的同一份內容。
4. 下輪透過近期延續內容與 Memory 讀取取得已保存結果。**Store 保存不等於自動加入 Context。** 接線驗收須包含「空 Memory 新建、導覽尚未更新、下一句回答上一題」；不能只依舊導覽，漏掉新建的工作理解。公開 model middleware／Tool 讀取是可用接點，近期結果如何納入預算仍需收斂，不新增第二份知識庫。[Model middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
5. 背景保留作候選：累積資料後對照目前 Memory 做較大範圍去重、補漏及詳記／導覽維護；重用主顧問已保存的成果，但不能將 AI 暫定解讀當員工已確認。原兩階段資料、引用與深查能力不能因此默默刪除。背景也可能需重新閱讀／判斷，不承諾零重複分析。

| 選擇 | 效果／取捨 | 建議 |
|---|---|---|
| 主顧問局部寫＋背景較大範圍整理 | 當輪理解可保存，保留既有詳記／導覽整理能力；有前台寫入成本及同寫協調需求 | **推薦**；擴大 C 的用途，B 分工須跟著修訂 |
| 主顧問包辦所有 Memory 整理 | 少背景執行與同寫協調；較大範圍整理也占前台時間，原 B 各項效果須另交代如何覆蓋 | 可選；不得因開發急就視為已核准取消 B |
| 另存短期分析筆記，再由背景轉 Memory | 能留下未說出口的成果，但多一種內容交接及生命週期 | 暫不優先；先證明同份 Memory 寫入不能滿足需要，再考慮 |

**成本／失敗界線：**當輪局部寫入仍花 tokens，Tool 結果通常需後續 model request；同一 run 不等於一個 request。背景不再是首次建立知識的必要條件，但整併仍有成本。寫失敗不可宣稱已保存，可按既定 Tool error 路徑有界修正；不因此推翻 `MEM-Q005`、阻擋獨立有效 JD 變更。背景同寫風險保留 Q018，不假設 Store 已自動防覆寫。

**Closure／下一個 gate：**官方能力已足以支持本輪角色選擇，停止找同類佐證。Owner 只需審核上述推薦分工；通過後一次產出最小接線設計，集中處理工具輸入／成功錯誤、近期寫入如何進 Context、既有詳記引用如何接續及 Q018，避免每個欄位另開一輪討論。沒有實作、付費測試、schema 決定或 production 授權。

### 6.7 原生推理延續不等於可修訂的工作知識

**2026-09-06／定向官方查證，非新機制決定。** Owner 問內部內容可否修訂、由誰分析，以及兩家是否只靠可見上下文。既有系統圖已記 opaque compaction 可延續 prior state／reasoning；本輪只補 reasoning 跨回合契約，不重做 Memory pipeline。

- **OpenAI API 官方事實：**Responses 在支援模型上可帶回先前 reasoning items；目前文件明示 GPT-5.6 支持 `reasoning.context=all_turns`，但必須真的保有先前 response items。內容 opaque，兼容性以模型家族為界，不能解讀成任意模型都可讀寫同一份推理文字。[Preserve reasoning across calls](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)
- **Anthropic 官方事實：**可回傳 thinking blocks 供後續推理接續，不等於只保留使用者可見聊天；block 須原樣回傳。保留／模型兼容性有版本差異；新版 preserved-thinking 還有 prefix 綁定，不能先假設任意重組 Context 後都可沿用。[Thinking](https://platform.claude.com/docs/en/build-with-claude/thinking)、[Preserved thinking](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking)
- **可修訂 Memory 是另一個公開機制：**Anthropic Memory Tool 由主模型提出 create／read／replace／insert／delete，應用程式執行；Memory 儲存本身不會分析。模型可將已學到的知識直接寫入，不必另叫模型重新抽取。Codex local Memory 則公開從合格歷史聊天背景抽取／整併，可各自指定模型；這是另一種知識產生分工，不是 OpenAI reasoning API 自動轉成可讀 Memory。[Anthropic Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)、[Codex local memories](https://learn.chatgpt.com/docs/customization/memories)

**需校正的推論：**「沒寫在對外回覆就一定無法續接」不成立；原生 reasoning continuity 可支持接續分析，但不能由此保證永不重算、永久完整保留所有工作細節、按主題搜尋或供任意背景模型重用。相反，也不能因本案要延續理解就直接認定每輪須額外輸出整份工作知識。§6.6 僅是可選且有官方原型的 hot-path 寫法，未證明優於兼容的原生延續＋背景整理。

**可修改的意思：**對顯式 Memory，模型讀相關內容、根據新回答更新同一紀錄／文件，例如把「上線後維護責任未明」改為「只處理另行委託修改」；不改寫原始員工對話，也不是編輯歷史加密推理。新內容仍需模型判斷，不是 Memory 資料庫自行理解；背景整理若會分析，是因另有 LLM 工作流程。

**Closure／下一步：**本輪只分清三件事：conversation／reasoning continuity、模型明確留下的可修訂知識、背景模型整理。功能均有公開依據，具體混合頻率不是跨家一致共識。後續接線須核對 provider／framework 是否完整傳遞原生延續內容，再決定哪些工作知識需即時明確寫入；不為本輪問答另造筆記層、強制每輪寫入或推翻既定長期細節／回查要求。未做 API 相容性測試、改模型或施工；官方契約或效果需求改變才重開相同查證。

### 6.8 框架能承接原生推理；不等於目前路徑已接好

**2026-09-06／LLM-Q017 G4，定向能力查證。** Owner 明示需要 §6.7 的原生推理延續。本輪只查「框架有沒有」，不重開 Memory pipeline 或要求另存每輪分析。

| 責任 | 官方接點與查證 | 邊界 |
|---|---|---|
| OpenAI reasoning 延續 | LangChain `ChatOpenAI` 的 Responses API 支持完整訊息接續或 `previous_response_id`。當日 upstream 的 `_construct_lc_result_from_responses_api` 保留 reasoning output item；`_construct_responses_api_input` 會送回 reasoning block，stateless 時要求可用的 `encrypted_content`；streaming 完成事件也有保存加密內容的分支。 | 不是只取可見 reasoning summary；`all_turns` 的有效性仍由模型／OpenAI API 決定。框架 `reasoning` 是 dict 接點，不代表本案 gateway 已支援該參數或已實測。 |
| Claude thinking 延續 | `ChatAnthropic` 回傳包含 thinking／signature 的 `AIMessage`；當日 upstream `_format_messages` 保留兩者及 redacted thinking，包含只有 signature 的處理。 | 框架傳遞不解除模型兼容／簽章／prefix 限制；不能任意改寫 thinking 或先前 Context。 |
| 跨回合保存 | LangGraph Checkpointer 保存 thread graph state；把完整 `AIMessage` 寫進 messages，可保存內容 blocks 及 metadata，供後續連接器使用。 | 只寫 `response.text`、自訂只剩字串的投影或摘要替換，會失去原生承接資料；Saver 不會自動補回。關閉應用後恢復需持久 Saver。 |

**來源／可重查位置：**[ChatOpenAI conversation state](https://docs.langchain.com/oss/python/integrations/chat/openai#managing-conversation-state)、[OpenAI adapter source](https://github.com/langchain-ai/langchain/blob/master/libs/partners/openai/langchain_openai/chat_models/base.py)、[ChatAnthropic extended thinking](https://docs.langchain.com/oss/python/integrations/chat/anthropic#extended-thinking)、[Anthropic adapter source](https://github.com/langchain-ai/langchain/blob/master/libs/partners/anthropic/langchain_anthropic/chat_models.py)、[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。此處 source 是查證日移動分支，不宣稱為本案已安裝版本；施工時須鎖版本再核對。原生語意依 [OpenAI reasoning continuity](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls) 與 [Anthropic preserved thinking](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking)，不是從 framework 名稱推論。

**本案現況／Unknown：**只讀確認 `apps/api/app/adapters/openrouter/langchain.py` 使用 `ReceiptChatOpenRouter(ChatOpenRouter)`，不是以上官方直連接法。本輪沒有核對整條 gateway／context middleware／持久化 round trip，不能稱已啟用，也不能稱 OpenRouter 不支持。`ChatOpenAI` 官方明確不保證第三方非標準 `reasoning_details` 等欄位，須使用相應 provider adapter；本案已用專屬 adapter，但這仍不證明與 OpenAI `all_turns` 等價。[ChatOpenAI API scope](https://docs.langchain.com/oss/python/integrations/chat/openai)

**Closure：**框架原生承接能力有直接依據，不必為此自創 Memory Tool 或筆記庫；下一步聚焦 provider 能力與完整訊息進出／Compaction 相容性，不先擴大 C／改掉 B。原生推理沒有永久完整記憶、跨模型可搜尋或免費 token 的保證，故不據此刪除長期 Memory。未安裝、付費呼叫、測試、切 provider 或改 production。只有接線／版本證據不足時補查，不重搜相同能力。
