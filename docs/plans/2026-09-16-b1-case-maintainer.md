# B1 案例維護者：前兩個施工切片

日期：2026-09-16

狀態：B1 staged contract 與固定來源 Agent graph 兩片皆完成；尚未接 B2／背景發布／正式 App
上位決策：[分層案例／工作理解 Memory 對齊](../specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)

> **2026-09-17 接續修正：**本計畫記錄已完成切片及當時證據；其中「所有改動案例自動附整批 canonical source」只代表舊切片現況，已被 Owner 的完整訪談回合引用決策取代，不再指導下一步。下一片須讓 B1 從 Runtime 已提供／已讀的完整回合 references 選擇並在 revise／split／merge 時正確分配；本次待整理來源是 processed-source 邊界，不是 B1 訪談回查權限上限。見 [MEM-L001](../specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md) 與[完整背景 Workflow 設計](../specs/2026-09-17-layered-memory-background-workflow-design.md)。
>
> **2026-09-17 接續結果：**上述精確 evidence 分配已由[引用施工計畫](2026-09-17-interview-evidence-citations.md) Task 4 完成。本檔 §4、§5 與 §7 保留的是前兩片當時契約與證據，不再是目前工具介面；目前 create／revise／split／merge 只選 Runtime keys，finish 不收 outcome。後續以引用施工計畫 Task 5 為準，不把本檔舊介面接回。

## 1. 第一片要完成的效果

本片只固定 B1 對案例層可做的語意操作與可 checkpoint 的 staged 狀態。B1 的輸出仍不是正式 Memory；必須等後續 B2 完成影響分析並由完整背景工作一次發布，A 才能看到。

模型可做：

- 依 Runtime 提供的穩定 `case_id` 按需讀取一筆目前案例。
- 建立新案例。
- 以局部 diff 修訂既有案例，未修改內容保持不變。
- 將一筆既有案例拆成多筆、將多筆合成一筆，或淘汰不再成立／重複的案例。
- 只更新指定案例的導覽文字；實體路徑及 Markdown link 由 Runtime 產生。
- 明確以 `changed` 或 `no_op` 完成本次 B1 判斷。

Runtime 負責：

- 綁定 document、base publication revision、base Memory version 與本批 canonical source。
- 產生新案例 ID，保存既有 ID，驗證來源及 scope。
- 維持 staged current set、supersession、案例 guide 與 change set。
- checkpoint 本 attempt 已成功讀取的案例；修訂、拆分、合併或淘汰前強制先讀目前正文，不能只看 guide 覆寫。
- 驗證 no-op／changed 是否與實際 staged 變更一致，以及完成時每筆目前案例都有且只有可解析的導覽入口。

## 2. 第一片明確不做

- 不改 B1 Prompt、Skills、模型、provider、credential 或費用設定。
- 不把舊三欄 `rollout_summary/raw_memory/slug` 包裝成新案例層。
- 不接固定 source window 的 Agent graph、checkpoint 恢復或 compaction；本片只提供它們之後使用的狀態／工具契約。
- 不做 B2、C、dispatcher、正式 App 接線、UI 或 publication。
- 不新增案例關聯式資料表、第二份 canonical 原話、RAG、文件封存、Memory GC 或舊資料猜測式 migration。

## 3. 可沿用與不可沿用

沿用既有：

- `MemoryArtifacts` 的 document scope、canonical source 驗證、不可變 bundle 與穩定 UUID。
- 既有 V4A `apply_diff` matcher；抽成純文字 helper 後供案例局部修訂共用，不改 matcher 語意。
- LangChain 1.4.0／LangGraph 1.2.11 的 `ToolRuntime` 隱藏注入與 `Command(update=...)` checkpoint state 更新。
- 正式模型組裝既有 `parallel_tool_calls=False`；同一 staged 狀態不接受平行競爭修改。

不沿用：

- 舊 B1 的固定三欄輸出與「每個窗口另存一份詳記／候選就是完成」語意。
- 舊 B2 的兩個固定檔案 staging／patch path 白名單。
- 讓模型填 document ID、來源引用、版本、路徑、digest、時間或 operation ID 的做法。

## 4. 工具契約

第一版固定八個窄工具：

1. `read_case(case_id)`
2. `create_case(content, route_note)`
3. `revise_case(case_id, diff, route_note?)`
4. `split_case(case_id, replacements[])`
5. `merge_cases(case_ids[], content, route_note)`
6. `retire_case(case_id)`
7. `set_case_route(case_id, route_note)`
8. `finish_case_maintenance(outcome)`

`route_note` 是一行自由文字，只表達名稱／別名／辨識詞／狀態／未確認事項等導覽語意；模型不填路徑。新案例的來源固定加入本批 canonical source；修訂、拆分與合併保留既有來源並加入本批 source。`context-only`、Working State、compaction summary 或模型自己的 change note 都不能成為案例來源。

拆分／合併只針對已發布的穩定案例 ID；同一 attempt 新建後發現內容要調整，使用 `revise_case`，避免產生從未發布過的虛假 supersession 歷史。

## 5. 驗收

本片全為零 provider 離線驗證：

- 開啟空白及既有 bundle 時不深讀全部案例，只讀 manifest／小型 guide。
- 新增、補充、更正保留穩定 ID、舊內容及舊來源，並加入本批來源。
- 重複資訊可以明確 no-op，不新增案例。
- 拆分、合併、淘汰的 current set、guide 與 supersession 一致。
- 模型工具 schema 不暴露 document、版本、來源、路徑、digest 或 runtime。
- 工具回傳的 `Command` 可經真 `ToolNode` 更新 checkpoint state，且保留完整 tool call/result 配對。
- 不能以 no-op 結束已有變更，也不能以 changed 結束完全未變更的 staged 狀態。
- 非法／不存在／已淘汰 ID、錯誤 diff、guide 漏 route、來源 scope 錯誤均安全失敗，沒有部分 state 變更。

## 6. 官方／版本依據與本案取捨

查閱 2026-09-16：

- [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)：工具應有清楚、不可互相矛盾的輸入，程式已知的參數由程式提供；本片據此把 scope、來源、ID 配置與儲存欄位留給 Runtime。
- [OpenAI 模型／工具設計指引](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)：工具描述應說明用途、輸入、副作用及失敗／重試；本片用窄語意工具與明確 staged/no-op 回應，不把儲存細節交給模型。
- [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)：工具是應用程式執行、模型選擇的 typed contract；錯誤可回給模型修正。本片不把工具呼叫本身當已發布效果。
- [LangChain tools／runtime](https://docs.langchain.com/oss/python/langchain/tools)：`ToolRuntime` 可注入 state/context/store 且不出現在模型 schema；本片已再以鎖定的 LangChain 1.4.0／LangGraph 1.2.11 原碼與本地探針核對。

上述來源共同支持「窄工具、Runtime 注入已知狀態、驗證後再生效」；案例分層、共同 publication、supersession 與 B1/B2 權責仍是 Caliburn 已確認的產品設計，不冒稱廠商規定。

## 7. 第一片施工結果

第一施工切片已完成：

- 新增可 JSON 往返、可由 LangGraph checkpoint 保存的 `CaseMaintenanceStage`。
- 新增八個 B1 語意工具；模型 schema 不含 scope、來源、版本、路徑、digest 或 runtime，經鎖定版 LangChain 的 strict OpenAI tool conversion 後根物件與 split replacement 都拒絕額外欄位。
- 新增 read-before-write 證據；修訂、拆分、合併或淘汰已發布案例前，必須先由同一 attempt 成功讀取正文。
- 新 ID、canonical source 合併、案例路徑、guide link、supersession 與完成結果均由 Runtime 產生／驗證。
- 同一模型步若送出多個 B1 工具會全部安全拒絕；不依賴 provider 永遠遵守 `parallel_tool_calls=false`。
- 把既有 V4A matcher 抽成純文字 helper，舊兩檔 staging 繼續走同一 matcher，沒有改變其 path 白名單或寫入行為。

第一片當時的實際驗證：`consultant-memory` **176 passed**；相鄰既有 B1 extraction／B2 consolidation App 固定接合 **33 passed**；0 provider、0 正式 publication、0 DB schema 變更。它指定的下一片是把既有固定 source window、Agent checkpoint／有限錯誤恢復接到這份 stage／tools 並補新 B1 Prompt；該片結果接續記於下節。

## 8. 第二片：固定 canonical batch Agent graph

第二片只完成第一片已指定的下一接點：

- `CaseMaintenanceWorkflow` 接受 Runtime 固定的整批 canonical source reference 與精確 base publication／Memory bundle。
- 沿既有 `ExtractionSourceReader` 交付 Runtime 固定的完整 canonical batch。能在實際 request 預算內完整提供時以單一窗口交付；只有來源或模型限制確實需要時，才在同一 batch 內規劃有界 `NEW_SOURCE`／`CONTEXT_ONLY` 分頁。是否分頁不是產品語意，也不由固定字數決定案例邊界。
- 一個或多個來源窗口都由同一個 LangChain Agent 與同一 B1 stage 依序處理；若使用多個窗口，非最後窗口不能提前 `finish`，最後窗口必須明確以 `changed`／`no_op` 完成。正式案例來源只加入整批 canonical reference，context-only 不成為證據。
- 新 B1 Prompt 只描述案例層責任、來源可信度、guide 導覽、read-before-write、案例身分生命週期與完成規則；不把 B2 穩定理解、JD 寫作或主顧問訪談責任混入。
- Runtime 使用同一 durable graph checkpoint 保存成功工具效果。模型 transport 在工具後失敗時，`resume()` 從原 checkpoint 接續，不重做已成功的案例操作或重新配置 ID。
- 模型／工具步數與最後完成修正都有同工作上限；重開／resume 不配置新額度。新 B1 的正式模型／工具上限不是舊 `max_windows=16`，也不直接借用 A／B2 的 16／15，因此 package 要求 App 組裝時明確提供；本片 16／15 只用於合成機制測試。provider 回報 incomplete、refusal 或 invalid tool call 時，在工具執行與完成前拒絕，stage 不發布。
- 新工作可在前一個完成 attempt 後重用同一 document graph；同 source＋同 base 直接讀回原完成結果，真正 stale 的同 source＋新 base 才建立新語意 attempt。

本片沒有把來源窗口改成多份正式來源，也沒有另建 source cursor。dispatcher 仍負責提供固定 batch；來源 owner 負責完整交付該 batch，只有必要時才決定窗口 pair、順序與分頁。這沿用「一個 B1 batch reference、一個語意 attempt；底層可用一個或多個讀取窗口」契約。package 的 `max_chars`／`max_windows` 是有界來源交付與合成測試機制，不是要求正式 App 固定切窗的產品規則。

2026-09-16 Owner 再確認：訪談資訊可能跨很多回合散落，因此背景通知固定的完整 batch 才是 B1 分析單位；窗口只是可選工程方法。B1 compaction 不得摘要、截斷或替換該批 canonical 訪談，只能處理 Agent 自己已完成的舊模型／工具往返。此項校正不禁止必要分頁，也不改已驗證的同 stage、checkpoint 與來源引用行為。

第二片新增 12 項零 provider graph 反例；連同第一片與既有套件測試，`consultant-memory` **188 passed**，相鄰舊 B1 extraction／B2 consolidation App **33 passed**。沒有 provider 呼叫、正式 publication、DB schema、dispatcher、compaction、UI 或 production authority 變更。

下一個獨立工作單位先做 B2 understanding maintainer 的 staged state／語意工具與影響分析反例，再接 B1→B2→完整 bundle publication；不在 B1 片內偷接 dispatcher、C 或完整 App。
