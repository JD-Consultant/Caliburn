# 動態 JD 任務與避免重複提問研究

查閱日期：2026-10-05。狀態：**研究與候選設計**；未修改 production、啟停服務或執行付費模型。這份研究接續[JD 收尾研究](../work-analysis/2026-10-05-jd-long-task-convergence.md)與[長任務進度研究](../retrieval/2026-10-05-long-running-agent-progress.md)，針對已接入工具後的使用方式補充比較，不另制定正式工具契約。

**建議讓模型動態決定工作內容與下一步，App 保存少量不可遺失的結論，並在決策前提供必要狀態。** JD 任務可以新增、拆分、合併與修訂；某一輪已釐清的是特定工作範圍，不是永久完成整項工作。公版提供可能的缺口，不構成逐項必問或完整度分母。

## 1. 使用者確認的問題

JD 是總目標。底下各項工作類似子任務，數量與粒度沒有預先固定，會隨訪談與模型分析修正。需要解決的是：長對話換輪、重啟或壓縮後，顧問仍能沿用已確認的責任界線，避免員工說沒做後又被問相同內容；同時保留發現新工作及更正舊答案的能力。

使用者已將正式公版 state 簡化為 `selected_reference_ids + excluded_work`，不保存回答來源欄位或一般確認紀錄。這個研究不重新加入每份公版／每項 JD 任務的完整進度表。正向工作事實由訪談、Memory 及 JD 的既有權責保存；尚未回答、拒答與不知道不能寫為否認。

## 2. 官方公開做法

以下分開公開機制與本案映射。大廠工程文章是公開案例，不能視為其所有產品的內部架構，也不能單獨證明 Caliburn 的訪談效果。

| 來源 | 公開做法 | 對 Caliburn 的推論 |
|---|---|---|
| [Microsoft Research Magentic-One](https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/)，2024-11-04 | Task Ledger 保留事實、推測及計畫；Progress Ledger 評估進展與下一步。停滯時更新計畫。 | 可借用動態重規劃及接續資訊；不必因此增加多 Agent，也不把該系統的猜測當員工事實。 |
| [Anthropic 長任務 harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)，2025-11-26 | 以進度檔、功能清單及可檢查的產物交接跨 context 的軟體工作。 | 借用外部保存及重新載入；軟體功能清單的完整性不能當成員工所有工作已知。 |
| [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)，2025-09-29 | 結合 compaction、持久筆記與按需讀取；過度壓縮可能失去後續所需細節。 | 保存與進入本輪 context 是兩個步驟；必要否認界線適合主動提供，公版正文按需讀。 |
| [Anthropic 後續 harness 實驗](https://www.anthropic.com/engineering/harness-design-long-running-apps)，2026-03-24 | 在較強模型的版本移除 sprint 分解，重新檢查各元件是否仍有作用。 | 分解方式可隨模型與任務調整；不能把固定分解當成長任務的必要條件。 |
| [OpenAI ExecPlans](https://developers.openai.com/cookbook/articles/codex_exec_plans) | 使用可更新、自足的計畫，保留進度、決策、發現與驗證結果，使後續執行可接續。 | 借用可修訂的接續點；本案不必搬入完整工程計畫格式。 |
| [OpenAI Memory 與 Compaction 範例](https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction) | 當次 compaction 延續工作；產物保留有依據的發現與未決問題。該例跨次 memory 保存方法經驗。 | 最終 JD 與正式事實不能只存在壓縮上下文；範例的 memory 用途不等同本案 B1／B2。 |
| [Google ADK State](https://adk.dev/sessions/state/) | 可更新、可序列化的 state 與事件歷史分開；持久性依 SessionService。state 可明示投影至模型輸入。 | DB 有資料仍需安排模型何時看見；否認應限於職務檔案，不能跨操作者所管的其他員工共用。 |
| [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) | 區分 thread state 的短期記憶與可跨 thread 取用的長期記憶，並依用途安排更新。 | checkpoint 解決執行接續；業務事實及否認已有保存，不需再建通用 memory store。 |
| [Deep Agents v0.7](https://www.langchain.com/blog/deep-agents-v0-7)，2026-07-29 | 待辦工具改成 opt-in；官方消融沒有發現該待辦 prompt／工具的顯著效益。 | 保留重要狀態與增加待辦系統不同。對 JD 應實驗最小接續資訊，不能預先宣稱待辦越多越可靠。 |

上述來源支持的共同工程原則，是把需要跨階段沿用的資訊顯式保存、在適當時機讀回，並重新檢查組件效果。它們沒有共同指定待辦 schema、子任務數量或 JD 完成政策。

## 3. 論文提供的邊界

| 論文 | 可核對觀察 | 對本題的用途 |
|---|---|---|
| [Lost in the Middle](https://arxiv.org/abs/2307.03172)，TACL，2023 年版本 | 當時受測模型對長 context 的資訊位置敏感，相關資訊位於中間時表現可能下降。 | 完整歷史已傳入，不等於可靠使用；此歷史結果不能直接量化今日模型的重問率。 |
| [LongMemEval](https://arxiv.org/html/2410.10813v2)，ICLR 2025 | 評測資訊抽取、跨 session 推理、時間推理、知識更新及不確定時 abstention；分析 indexing、retrieval、reading 三階段。 | 分開測資料有沒有存、是否讀到、是否正確使用；尤其需測否認後更正與條件範圍。它是問答記憶評測，不是 JD 收尾實驗。 |
| [LongMemEval-V2](https://arxiv.org/html/2605.12493v1)，2026 預印本 | Web agent 記憶評測包含動態狀態、工作流程、環境陷阱與前提辨識。 | 可借用「過時狀態」與「問題前提不成立」反例；網站經驗不能直接替代員工訪談真值。 |
| [ADaPT](https://aclanthology.org/2024.findings-naacl.264/)，NAACL 2024 | 依執行困難按需分解及規劃，而非一次固定所有步驟。 | 支持讓模型依具體問題調整子工作；其執行成功判準不能轉成 JD 永久完成旗標。 |

本題較接近「持續更新的工作模型＋有限的當前行動」。子任務已回覆不表示工作理解完整；所有已列問題都處理，也不證明尚未發現的責任不存在。

## 4. 長任務與短任務如何對應

| 層次 | 本案例子 | 何時可收束及再開 |
|---|---|---|
| 總目標 | 交付反映本人主要工作、可供使用的當前 JD／PDF | 依當前證據判斷版本可交付；新資訊仍可修訂。模型回覆 final 只是本輪執行結束。 |
| 可修訂工作範圍 | 網站功能開發、客服退貨處理 | 內容可新增、拆合與修正；目前已足夠描述可以先沿用，不設永久 done。 |
| 當前釐清事項 | 正式環境由本人部署，還是交給維運？ | 明確答案可解除這個疑問；不同環境或新責任是另一範圍，不能一併封鎖。 |
| 短操作 | 讀 Memory、讀公版、保存排除、修訂 JD 文字 | 以實際工具結果判斷操作是否完成；保存成功不能替模型宣告分析品質完成。 |

細分長短主要依接續需求與可驗證行為，不依固定 token 或分鐘門檻。JD 任務與 Agent 當前動作保持不同概念，避免「讀完一份公版」被計為「完成一項本人工作」。

## 5. 現行接線與具體缺口

現行 [state 契約](../../specs/2026-10-04-public-reference-completion-design.md)已有 selected references、可更正的 `excluded_work`、跨輪正式資格與 Memory 固定 F。[接線驗證](../../experiments/engineering/2026-10-05-occupation-reference-tools/agent-integration-verification.md)證明保存、工具分派及原生恢復。

顧問[公版指引](../../../apps/api/src/caliburn/agents/job_consultant/reference_instructions.py)要求按需讀 state；[initial context](../../../apps/api/src/caliburn/agents/job_consultant/context_binding.py)目前組 Memory maps、近期訪談及當輪員工輸入，沒有自動加入排除清單。也沒有結構化的員工提問出口來阻擋重問。

因此目前具備「可存、可讀」，仍依賴模型主動讀取及正確理解。尚不能由接線測試推論：原話被壓縮、Memory 排除否認或模型換個說法後，就一定不再問。

## 6. 三個方案與建議

| 方案 | 效果與代價 | 目前建議 |
|---|---|---|
| A：既有 state＋模型按需讀 | 變更最少；讀取時機及使用仍靠模型，可能忘記查。 | 保留作控制組。 |
| B：必要 state 主動提供＋可選的短接續點 | 新 Turn 及壓縮後的合法接續邊界提供有效否認；模型決定當前重點與重要未決問題。正文及已知工作仍沿原工具按需讀。 | **優先比較**。先只改善排除資料可見性；接續點是否有用再做單獨消融。 |
| C：受控提問入口 | 模型先提交要確認的工作範圍；App 可檢查已處理範圍後才顯示問題。新增跨層契約及語意判斷責任。 | 若 B 仍有明顯重問，再評估；任意自然語言的語意等價仍無確定性保證。 |

B 不要求建立每項工作狀態或公版 checklist。正向工作由原 Memory／JD 承載；否認只用既有 `excluded_work`。若反例證明原 context 無法接續「正在問哪件事」，才保留一小段當前焦點及未決事項，先檢查既有保存可否承接。

這是本案取捨，不是官方保證。不能保證模型永不犯錯；可以先保證應提供的否認資料不因歷史壓縮或換輪而消失，並測模型實際重問率。

## 7. 員工說沒有後如何接續

例：顧問問正式環境部署；員工答「沒有，那是維運做。我只開發及交測。」

1. 顧問依相鄰問題保存明確範圍：`正式環境部署由維運負責，本人不執行`。不把員工省略語境的「沒有」單獨存成通用排除。
2. 後續新 Turn 在合法綁定時提供這段有效 state；即使近期原話已不在 context，仍可看見此範圍。公版又提到部署，不重置答案。
3. 模型核對公版線索時沿用該結論；同一正式環境部署換成「發布上線」仍應辨識為同範圍。測試環境部署是否本人負責則尚未由這個答案排除，只有對 JD 重要才追問。
4. 員工改說「上個月起正式部署改由我負責」，顧問依新回答精確解除舊排除，維護實際工作及相關 JD；不清空其他排除或重新分析整份公版。

新搜尋名次、換公版、Memory 無關更新或 JD 任務拆合不構成重問理由。新的責任、條件或矛盾才可能需要局部重核。同義判斷仍由語意處理，不能拿 cosine 門檻當已回答／否認的確定判準。

### 與原生恢復一致

候選主動提供必須沿原 execution／職務檔案及固定可見範圍，不能將後輪資料帶回舊批次。恢復已保存 request 時不刷新該 request 或重加 state；壓縮後若需要追加資料，須在合法新 request 邊界捕捉並持久保存。業務文字仍是低權限分析材料，不升為 system 指令。

本次不凍結新的 App data schema 或保存格式。重要狀態的提供時機須由後續 context／tool 契約定義，沿既有 checkpoint 與 feature，避免第二份 authority。

## 8. 如何判斷當前版本可以交付

建議由顧問核對主要工作是否有合理廣度、已確認內容是否寫入 JD、重大權責矛盾是否處理，以及是否還有答案會實質改變 JD 的重要問題。這沿既有工作分析與[收尾研究](../work-analysis/2026-10-05-jd-long-task-convergence.md)，不新設固定完成分數。

沒有新重要問題時，可交付當前版本；新證據可局部重開。只剩可選潤飾不必再次訪談。遇到無法回答則保留未知，不同於已否認；到達執行上限也不能冒充內容完整。公版任務確認完只表示該批線索已處理，不能證明所有未知工作已發現。

## 9. 最小驗證設計

先以相同員工原話、同一工作輪廓與公版命中做 A／B 配對，第一組只改 state 可見性；第二組才加短接續點。保持模型、工具、正文、溫度與預算條件一致，記錄原請求、工具結果及對員工公開的問題。之後再決定是否需要 C，不把多項改動的效果歸給單一機制。

至少涵蓋：明確否認；依前句答「沒有」；帶條件的否認；同義重問；新公版重複相同範圍；未知／拒答；部分負責；員工更正；無關 Memory 更新；任務拆合；長 context 壓縮；取消／恢復。短情境與跨輪／換窗情境分開報告。

評估重複詢問已否認相同範圍的次數及機會分母、誤封鎖合理新問題、更正後採用新範圍、遺失重要工作、否認工具漏存／誤存與查讀成功但未遵守的比例。另量測新增 token／時間及 JD 事實保留；原樣問句及換句話的相同範圍都納入標註。容許多條有效提問路徑，不能拿固定公版數或逐字問句當唯一答案。

本輪只完成研究及候選比較，沒有新模型結果。研究已足以形成有限對照，接著應驗最小方案，避免再靠更多框架名稱決定設計。
