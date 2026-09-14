# Q019：記憶整理時機與對話延續的成本／效果審查

> 2026-09-06 · Topic：`Q019-MEM-CADENCE-01` · **Owner 已暫准「主顧問段落整理訊號＋新文字量後備」，策略為 G3 WORKING。**
> 最新裁示：不用訪談閒置 90 秒觸發；回合數不作主要判準；不能依賴員工手動整理，是否額外開放入口待討論。具體訊號契約與數值未定；接法移至獨立 G4 子稿。本輪只更新研究與相關設計／計畫，未改程式或使用付費模型。舊 OR 規則保留為沿革，不再是待施工預設。

## 1. 唯一決策題與文件分工

**何時值得啟動背景抽取／整併，才能兼顧長訪談的完整性、當下理解與總成本？**

Owner 最新補充：專案非常依賴記憶，但每輪資訊可能很少，不應頻繁重做整理；已選擇原生 reasoning／thinking 延續。概念分層為「訪談原始對話 → 案例／詳記 → 理解 Memory → LLM 分析製作 JD」。本版仍只做訪談分析，不接 JD 編輯。

本稿不重開五產物、存放位置或框架選型，也不新增案例資料表、每輪內部筆記或整理判斷 Agent。沿用文件如下：

- [Memory 設計](2026-09-06-analysis-only-agent-memory-design.md)：五產物、來源視窗、B1／B2／C、回查與發布；仍為內容及流程設計入口。
- [Runtime 設計](2026-09-06-analysis-only-agent-runtime-design.md)：原生推理、每次請求的 Context 與 Compaction。
- [背景生命週期研究](2026-09-05-memory-background-cycle-flow-review.md)：抽取／保存／整併分工，不重新研究同一生命週期。
- [OpenAI 詳記更正證據](2026-09-06-openai-rollout-summary-correction-source-review.md)：已固定版本的程式證據與詳記更新邊界，不把摘要批次當成單一案例主檔。
- [應用接線計畫](../plans/2026-09-06-analysis-only-agent-application-wiring.md)：Task3 最小 API、Task4 排程；本題不阻塞 Task3，但 Task4 不能把候選門檻當作已驗證最佳值。
- [通知接線子稿](2026-09-06-memory-consolidation-request-wiring-design.md)：具體工具／metadata、dispatcher、取消及恢復檢查；本稿只保留策略與成本依據。

## 2. 官方實際做法：共同目的，不是相同時鐘

下列皆於 2026-09-06 核對官方頁面。只描述公開行為，不推測未公開的內部排程或宣稱某個頻率效果最好。

| 來源 | 官方直接公開的做法 | 能學習什麼／不能推成什麼 |
|---|---|---|
| [OpenAI Codex local memories](https://learn.chatgpt.com/docs/customization/memories) | 從合格聊天產生記憶；跳過仍活躍或太短暫的 session，等足夠閒置後背景更新；剩餘配額低時可跳過一輪背景產生。不是每次聊天一結束就更新。 | 支持累積後整理、避免整理仍變動中的內容與考慮預算；不支持 Caliburn 固定每 4 輪或 90 秒就是最優。Codex 跨聊天的資格政策也不能原封套到本案持續單訪談。 |
| [OpenAI Sandbox Agents：Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs) | Conversation Session 與可重用 Memory 分開；執行期間累積 run segments，sandbox session 關閉後先抽取摘要／候選，再整併正文與導覽；另支援執行時修補記憶。 | 支持 B 批次整理與 C 執行時修補的不同用途。sandbox session 關閉不是員工每一則訊息送出，也不等於必須等整份 JD 訪談永遠結束。 |
| [Anthropic Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)、[Claude Code auto memory](https://code.claude.com/docs/en/memory#auto-memory) | Memory 與有限 Context 配合使用；模型可在工作中讀寫記憶。Claude Code 依後續是否有用決定保存，不是每個 session 都留下新記憶。Memory Tool 指引強調內容連貫、更新，以及避免不必要的新檔案。 | 支持選擇性保存／按需維護，不證明 Anthropic 使用 Codex 相同的背景節奏；也不能把「不寫入新的長期記憶」理解為刪除原始訪談。 |
| [LangChain：Writing memories](https://docs.langchain.com/oss/python/concepts/memory#writing-memories) | 區分即時與背景更新的延遲／新鮮度取捨；背景可採事件後延遲、新事件重排、週期排程或手動觸發，沒有單一通用解。 | 框架支持依工作量選時機，不替應用判斷什麼訪談內容重要。移到背景主要改善前台等待，不代表沒有模型費用。 |
| [Deep Agents：Background consolidation](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation) | 公開獨立整併 Agent 的排程範例，要求頻率符合實際使用量，並警告太頻繁會花 token 做沒有實質更新的工作。 | 支持避免過密整理。本次以實際頁面為準，不以搜尋摘要中的舊片段拼湊 API；範例時數／lookback 不是本案待處理來源的保留政策。 |

**可以支持的共同原則：**當下對話延續與持久記憶是不同責任；記憶更新要兼顧新鮮度及成本；不應把每次訊息都等同一次完整重整。

**不是各家共同規格：**背景／即時更新比例、session 定義、等待時間、批次大小、是否有額外分類模型。共同目的不能證明某組實作細節必然最佳。

## 3. Reasoning、Compaction 與背景 Memory 怎麼配合

### 原生 reasoning 先支撐正在進行的訪談

OpenAI 支援在相容模型及正確請求鏈下延續可用的先前 reasoning；`all_turns` 不會製造未帶回的內容。這些 items 是不透明狀態，不是可自行編輯、可交 B1 解碼的工作理解正文。[Preserve reasoning across calls](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)

因此，新資料還沒進長期 Memory 時，主顧問仍可依近期問答與可用 reasoning 繼續訪談；但不能承諾完全不重新分析、永久保存全部分析細節，或免費延續。背景仍按既有設計從可讀的實際問答抽取，而不是複製主顧問的隱藏思考。這不是再增一份可寫的「內部思考筆記」。

### Compaction 看 Context 壓力，不看訪談是否已經值得整理

OpenAI 的 server-side compaction 可依請求設定的 context token 門檻觸發，回傳後續使用的 compaction item；這是在管理模型的延續 Context，不是完成訪談詳記／工作理解整併。[Compaction](https://developers.openai.com/api/docs/guides/compaction)

本案已實作原生 compaction 的參數與 request view，但 `compact_threshold` 目前預設 `None`；32,000 只曾用於參數傳遞測試，不是正式啟用值。背景排程也尚未接好，不能說現在已自動每 4 輪整理。

**本案既有保存界線：**Context 壓縮不刪 canonical 原始訪談，B1 仍能抽取未處理範圍。但「原文還在」不等於模型當下必然想到、或已知道如何找回所有尚未抽取的細節。背景延後過久仍有 Context／回查成本及遺漏風險，不能只用 reasoning 存在作為無限延後的理由。

## 4. 三種節奏的取捨

| 方案 | 主要好處 | 主要代價／風險 |
|---|---|---|
| 只依主題告一段落 | 比單純數回合更接近訪談脈絡 | 主題會交錯、被打斷、重新打開；模型也可能漏發訊號。不能把「永遠分析完」當成唯一啟動條件。 |
| 只依累積新文字量 | 便宜、可觀察；不需另一個語意判斷模型 | 長度不等於知識量；短更正可能重要，長敘述也可能尚未講清楚。 |
| **主顧問的段落整理訊號＋累積新文字量後備** | 有適當段落可以早點整理，持續長聊也有另一個整理機會；沿用 A／B／C | 訊號的定義與可靠性需小額驗證，主模型的輸出或工具動作也非零成本。具體接線／數值尚未核准。 |

第三項已經 Owner 回覆「同意，繼續開始」暫准，為 **Caliburn mapping／WORKING 策略**；具體接線與數值仍待審閱。各家支持按需記憶與應用事件觸發，但公開證據不足以稱「主題結束＋文字量」為 OpenAI／Anthropic 共同排程。前輪「累積量＋閒置機會」因 Owner 新限制修訂，不保留另一個換了秒數的閒置觸發。

### 舊候選 OR 觸發需要留意

**歷史，不再是執行預設：**原候選為「4 回合，或 6,000 字，或有新內容且閒置 90 秒」。最後一條會讓很短的一輪也可能觸發整套整理。Owner 已排除 90 秒觸發；回合數不再是主要判準。6,000 字也不因此成為已核准值。

不能用「短句沒有價值」解決：員工回答「對」，可能確認上一輪重要責任；「不是我負責」可能更正核心工作。**不因字數少丟掉來源，也不另用關鍵字規則推斷語意重要性。** 字數／回合數只是便宜的工作量訊號，不能證明是否已有可用新知識；模型抽取仍須看到必要的前置問答。

## 5. 建議原則與尚未決定的細節

1. **原始訪談每次可靠保存。** 是否啟動整理不影響保存；小批次尚未處理就保持待處理，不能假裝已抽取或永久略過。
2. **一般訪談先用近期上下文、可用 reasoning 與既有 Memory。** 不要求主顧問每輪付出完整整理成本，也不要求多叫一個模型判斷要不要整理。
3. **建議由主顧問提出段落整理訊號，文字量作另一個觸發機會。** 不用 90 秒閒置或固定回合數判定已值得整理。主顧問只提出何時值得排程，B 仍負責抽取與整併；不是讓主顧問再寫一次詳記／理解。具體訊號形式及門檻須在 Task4 前收斂。
4. **立即需要修正既有記憶時沿用 C 局部修補。** 是否需要由主顧問依當輪脈絡判斷，不用每次更正都重跑整個 B。背景之後仍按來源游標吸收訪談；B／C 的版本協調沿用已測機制。
5. **不重複處理已成功整理範圍，已有產物可恢復沿用。** 沒有新來源時的模型前 no-op 可省呼叫；模型看完後判定沒有值得更新的內容，仍已花費 token，兩者必須分清。
6. **最新資訊以最新問答及正確可用內容為準，不能假定舊 Memory 已更新。** 正在訪談可使用尚未入 Memory 的對話；必要時回查。最終 JD 全面核對的完整性仍屬後續產品能力，不在本輪加「每次 JD 都必須先全量整併」的新 gate。

**分層沒有變成四次模型呼叫：**案例／詳記是整理後內容，不強制一個案例一筆資料；一段詳記可含多個案例，同一案例也可在後續段落補充。候選協助整併、導覽協助回查，不新增另一份 Memory。Memory 是提供判斷的知識，將來仍由 LLM 分析／編輯 JD，不由 Memory 自動操控文件。

**尚未定案：**主模型如何發出排程訊號、文字量單位／數值、小批次未出現訊號就關頁時是否另需補齊條件、是否提供員工選用入口，以及 compaction threshold。組合策略已暫准，不重問是否採用。不同問題不強行綁成一次大翻案；本輪不新增強制 memory-before-compaction 流程。

### 5.1 「主題告一段落」的語意與官方依據

**不是主題已經完全正確、已可生成 JD 或不能再更改。** 建議含義是：本段已累積值得保留的新進展，適合先整理；可以仍有未知或待問問題。從 A 主題切到 B 不必然代表 A 已完成；同一主題很長也可分段整理。需要由主顧問判斷，Runtime 不會只靠文字量自動知道語意。

- [Anthropic context engineering：Structured note-taking](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents#context-engineering-for-long-horizon-tasks) 支持 Agent 定期維護 Context 外的記憶，並指出這類方法適合有明確里程碑的反覆工作。**它沒有宣稱里程碑是每次背景整併的唯一觸發條件。** 這是概念依據，不照搬該文發表時的模型版本／API。
- [Claude Code auto memory](https://code.claude.com/docs/en/memory#auto-memory) 支持由模型依後續用途判斷保存；[LangChain Writing memories](https://docs.langchain.com/oss/python/concepts/memory#writing-memories) 支持應用邏輯觸發背景作業。兩者能支持「主 Agent 提出需要整理，由背景執行」這類接法，**不表示兩家官方都有相同的主題完成工具**。
- [Codex local memories](https://learn.chatgpt.com/docs/customization/memories) 公開的是閒置／資格策略，不是主題結束。採 Owner 提出的段落方式，是針對本案訪談的可逆選擇，不能改寫官方事實來說它完全一樣。

**接線方向，非已核准契約：**不另呼叫一個分類 LLM；讓正在訪談的主模型按需提出整理要求，Runtime 在來源可安全封閉後排進既有 B dispatcher。[G4 子稿](2026-09-06-memory-consolidation-request-wiring-design.md)比較按需工具＋artifact、Command state 及小型結構化輸出，建議先採空參數工具。不從顧問可見文字猜「換個話題」就觸發，也不新增 topic table／Task ID／完成率欄位。工具若增加主模型 step，必須計入成本，不能稱完全免費；契約未實作。

**段落訊號只決定何時跑，不決定只保存哪個主題。** 沿既有未處理來源範圍抽取，避免在多主題交錯時漏掉旁支內容；B1 的有界視窗與前置問答規則不變。未說清楚的部分保留未知，而非等到完美才可留下詳記。

**文字量後備的意義：**計算上次已成功處理後的新、可抽取訪談，不是累計全歷史、重複 Context、模型隱藏 reasoning 或技術 log。可用字數作直觀配置，token 量更接近模型負載但依 tokenizer 而異；兩者都只是負載代理，不是語意完整度。達門檻也要等目前問答的安全邊界；不因某個短句未達門檻丟掉它，不替 Owner 定案數值。

若突然關頁、沒有段落訊號也未達文字量，原文與未處理範圍仍保留，不能宣稱 Memory 已更新。下次恢復如何補齊需納入接線／小額驗收；本輪不偷偷改成另一個 idle timer。

### 5.2 手動入口：指令、管理與全量整理是三件不同的事

[Claude Code `/memory`](https://code.claude.com/docs/en/memory#view-and-edit-with-memory) 用於查看／管理；也可在聊天要求記住指定資訊。它不等於一個「現在對所有對話完整重跑 B1／B2」按鈕。[Codex `/memories`](https://learn.chatgpt.com/docs/customization/memories#control-local-memories-per-chat) 控制聊天是否使用／貢獻記憶，也不能當成強制整併 API 的證據。

本輪建議：自動流程不依賴員工要求整理；第一版不把專用整理按鈕列為必備。是否容許聊天提出「記住這個」或額外操作入口仍待 Owner 決定，沒有禁止的定案。開發測試可呼叫 dispatcher，不代表必須曝光員工按鈕；即使日後開放，也應走相同來源／並行限制，不能無條件全量重算。

## 6. 成本與後續小額測試：沿已核准第四步，不另造 eval

比較的是整段訪談的總花費與結果，不是單次主顧問回答速度。至少觀察主顧問所有 steps、B1 抽取、B2 工具循環、C 修補／重試的 usage 與次數；原生 compaction 若有可用 usage 也記錄，不假裝它必然免費。背景 B1／B2 不保證總共只有兩次模型請求。快取以 provider 實際回報區分，不能先假定所有重讀都免費。

既有小額驗收與第四步 Prompt 優化加入以下代表情境即可，**本輪不執行**：

- 多輪少量補充：不反覆對近乎相同的理解做完整整理。
- A／B 類似案例：一般模式可合併，差異與細節仍可沿引用找回。
- 重要短更正／回答先前問句：不因少字而漏掉，也不把每個短句都當昂貴整併必需。
- 持續長聊、Context 壓縮或重開：未整理來源仍能接續處理；舊案例細節可回查，不能只驗「資料庫有存」。
- 主題交錯／中途轉題、同一主題很長及漏發整理訊號：不把轉題當成全部分析完成；檢查文字量後備是否保住處理機會，訊號成本是否值得。

同一批訪談比較整理次數、總 input／cached input／output／可得 reasoning usage、等待時間、未處理積壓，以及細節／修訂／回查結果。選較少不必要整理、又沒有重要效果退步的節奏；不先承諾精確節省比例。真 API 沿 Owner 指示用 Luna／medium，執行前限額。

## 7. 研究停止點與接續

官方時機差異、原生推理界線及段落訊號的證據邊界已清楚，不重新研究整套 Memory 架構。**組合方向已暫准；下一步只審通知接線子稿，再做 Task4 所需離線接線驗證**，不重問策略。已同步 Memory／接線稿／計畫及 current register；數值不因文件更新而變成最佳值。最小 API 仍可依既有授權接續；本輪不是已實作或新付費測試授權。
