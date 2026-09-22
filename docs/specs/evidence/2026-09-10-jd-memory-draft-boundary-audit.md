# JD 的未知、未分組草稿與 Memory 邊界核對

2026-09-10；JD-R001/C06、JD-R002/C01。Owner 問「尚未釐清或尚未歸屬內容是否需要 JD 區，留記憶即可？」本附件是格式討論的有限研究推薦，供主線整合；不是已核准的新區塊或 implementation gate。依 [current register](../../current-decisions.md)，完整格式仍在 G3 討論，Task 1 暫緩。只新增本附件；不修改 runtime、schema、Memory、DB、樣稿或 UI，不執行模型／資料庫呼叫。

## 1. 推薦：不預設獨立區塊，保留不同內容的原有責任

**一般訪談待釐清事項沿現有訪談／Memory 保存，不需要另設 JD「待釐清區」。已經成為文件內容、只是尚未分組的草稿則留在 JD，不因拿掉該區塊而刪除或移出。**

這不是「任何未知都不能出現在 JD」。如果省略限制會讓讀者把未確認權責誤認為已確認，顧問應先釐清，或在相關工作敘述就近表達已知範圍與必要限制。若組織本身確實尚未決定一項重要權責，這個已知的未定狀態也可能是目前工作的重要事實。兩者均不需要把所有訪談問題複製成文件旁的清單。

保存不等於完整、正確或核准；資訊未齊的 JD 可以保存。員工已輸入／保存的草稿走既有保存與更正流程，不由 App 自動搬到 Memory、覆寫或刪除。尚未保存的 buffer 仍是 buffer，不能冒稱已持久保存或已更新 Memory。

## 2. 可審核分類：先問這段內容的用途與來源

這是顧問判斷及設計審查表，不是新 enum、Gap 表、分類 Agent、收件匣或每段必填 metadata。只有分組未定，與責任事實未定，是兩個不同問題。

| 情況 | 例子（方法示例，非真實員工資料） | Memory／訪談責任 | JD 處理 |
|---|---|---|---|
| 尚未形成可支持的職位敘述 | 「我們有時處理採購」，尚不知本人做什麼 | 保留原話、相關未知及後續追問線索；不把「我們」改成本人責任 | 暫不新增肯定任務；不為此建立一格「採購待釐清」或假 Duty |
| 有足夠根據的工作已成稿，分組未定 | 已知本人初審申請、核對附件，但尚未決定放在哪個職責 | 工作理解仍保留已知責任；章節位置不是新分析缺口 | 保留完整敘述，可先直接列任務或普通段落；後續整理位置而不丟內容，不必有「未歸屬區」 |
| 員工直接輸入未完整草稿 | 員工先寫「月報：整理營收與異常……」 | 不把手改自動視為已核實的工作事實更正，也不自動寫回 Memory | 保留已輸入內容及保存狀態；AI 從目前稿續編，不能因不完整而移走。會改變責任且有歧義時先釐清該處 |
| 部分責任已知，重要邊界尚未問清 | 已確認「本人初審」；最終核准者未確認 | 保留已知初審，只留下核准者這個真正未知；答覆後更新相關理解 | 可先寫已支持的初審責任；若文字會使讀者誤認本人有最終核准權，須就近限定或明示尚待確認，不把初審一起刪掉 |
| 未定狀態本身是經確認的工作現況 | 員工明說組織尚未決定新流程的最終核准角色 | 保留此說法、適用期間／流程及來源，不混同「訪談沒問到」 | 若會改變工作責任，按真實範圍就近保留未定狀態；不能寫成固定本人核准，也不能藏起來冒稱權責已清楚 |
| 純分析或非必要細節未明 | 尚不知某個案例的偶然工具版本，而不影響責任理解 | 必要時留詳記／原文；不逐欄製造未知 | 無須空白欄、待辦提示或占位段落；不得因不明而猜填 |

**成稿判準不是「有一句文字」。** 員工先提到成果、工具或案例，並不表示那段訪談已被選為 JD 內容。顧問應依既有寫作時機，對某項工作有足夠理解才寫；不必等待整份工作完全分析完，也不必每輪改稿。另一方面，員工明確在文件內寫入的文字具有草稿身分，不能再用同一篩選理由靜默移除。保留草稿不表示永遠不能編修；有依據的對話更正或員工手改仍沿正常流程更新，不新增逐次確認或凍結規則。

「正式 JD」在本案仍是持續工作稿，沒有因保存而自動核准。成熟程度的判斷與可否保存分開：重要未知若會改變結論，不能宣稱該部分已充分理解；但不因此禁止保存其他已知內容，或復活目前 PARKED 的真人簽核／交付流程。

## 3. 現有 owner 已承接什麼

### 3.1 訪談與 Memory：未知已有去處

[分析指南 §4／§6](../2026-09-09-complete-work-analysis-guide.md#4-案例工作理解與-jd如何取捨而不丟失)已區分原始訪談、詳記、工作理解與 JD；Memory 保留會影響理解的未知，JD 不收所有案例與分析過程。完整度採工作→JD、JD→依據雙向檢查，不要求每筆 Memory 都變成一項 JD，也不建立 coverage ID 或 verifier。[深度校準 §3／§6](../2026-09-09-customized-jd-depth-and-interview-calibration.md#何時換方向何時保留未知)進一步要求問不清就保留未知、不循環逼答、不把重要未知包裝成充分理解。

[Memory 設計 §1](../2026-09-06-analysis-only-agent-memory-design.md#1-保存責任與五個概念)已有以下責任，不能因 JD 格式討論再複製一套：

| 現有 owner／產物 | 本題相關責任 | 不能推得的事 |
|---|---|---|
| LangGraph Checkpointer 的 canonical messages | 保存實際問答及可回查語境；context 壓縮不以摘要覆寫原始訪談 | 顧問問題不等於員工答案；完整保存也不保證模型每次都會找到 |
| PostgreSQL Store 的訪談詳記／候選 | B1 保留本段已知、案例差異、相關待答與原文引用；候選供 B2 整理 | 不是 JD 草稿收件匣，也不是已核實整體現況 |
| 版本化工作理解正文與導覽 | B2 整理目前理解、適用條件、真正未知與詳記路由；C 可修已核實的過時理解 | 不是另一份 JD，也不因正文有未知就要求文件顯示同一份問題清單 |
| publication metadata／既有 runtime state | 管版本、來源進度、回執及執行恢復 | 不另保存語意 Gap／工作理解正文 |

實際隔離 source 查閱基準為 `.worktrees/analysis-only-agent` HEAD `622e548d9d37ce4f8adb2ac0f0e61ce0d7aad3d9`；本輪檢查的 extraction／consolidation／live_memory 三檔無未提交差異。下列是隔離成果的 owner，不能宣稱 production authority 已切換：

- [extraction.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/extraction.py) 36–53 行：B1 區分員工陳述與顧問問題，不把本段沒提寫成整體未知；部分回答只保留真正未答部分，不能撤銷已知做法；不輸出 JD／Task 表單。
- [consolidation.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/consolidation.py) 24–50 行：B2 明定不編輯 JD；部分已回答時保留已知、移除同一事項過時疑問，只記影響理解的未知、不逐欄製造缺口；仍未解的其他問題不得一併刪除。
- [live_memory.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py) 20–43、115–143 行：主顧問沿已核實更正修目前 Memory，含已解決的未知；歧義先問或回查。每輪固定初始 guide／讀取版本，模型請求實際帶入導覽，按需讀正文。這支持沿既有入口使用未知，不需要加 JD 區才能讓模型有機會找回。
- [memory.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/memory.py) 127–144、157–178 行：runtime 保存詳記／候選並加入 source window，summary address 可沿 owner 解回原文。詳記與 Memory 是整理資料，不是逐字來源的替代品。

[CT49 固定完整訪談結果](../../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct49-fixed-long-interview-results.md)保留具體實證：前段核准者「印象中」仍是未確認，後段查證後修正；排序權限未說明先追問，回答後更新而不殘留同一舊問題。另有只留詳記的內容，後續回查能找到。**這是固定代表情境的既有結果，包含修補延遲與措辭限制，不是本輪重測或所有未知永遠正確更新的保證。** 最新隔離配置／驗收效力沿 [worktree register](../../../.worktrees/analysis-only-agent/docs/current-decisions.md)，不把較早 Memory 設計中的初始額度當現況。

### 3.2 JD：內容與組織狀態沿文件 owner

[欄位指南 §2](../2026-09-09-jd-field-and-writing-guide.md#2-內容總覽)明定成熟文件應能回答的核心問題，不是第一輪必填，也不禁止不完整保存。[關係研究](../2026-09-09-jd-document-relationships-working-research.md#未歸屬不是新分析系統)已說「未歸屬」是文件組織狀態而非訪談待釐清，不增加第二工作理解、Gap 表或強制候選層。

[Plate profile §2–3](../2026-09-10-jd-plate-document-profile.md#3-空白未完整與允許欄位)允許直接任務、普通段落、合法空稿及尚未完整敘述；這提供保留草稿的形狀能力，**不要求新建一個「未歸屬」UI 區、獨立儲存欄位或自動搬移流程**。本題推薦不必新增 schema 欄位；若日後要變動語法，仍須另核契約，不能拿本文直接施工。

[主設計 §3.1](../2026-09-09-jd-editor-app-integration-design.md#31-不每輪改稿的顧問接點)已確立：目前 JD 是續編基底，不能因與舊 Memory 不同就蓋回；人工修改不自動等於工作事實更正，不自動更新 Memory。責任差異有歧義時先不改該處、正常訪談釐清；背景 Memory 不寫 JD。相同原始問答同時支持工作理解與 JD，是不同用途，並不等於允許建立兩份待辦 owner。

## 4. 現有文檔容易誤導之處與替代文字

以下只提替代文義，由主線決定整合；不更改原檔。行號以本次讀取為準。

| 位置 | 具體風險 | 建議替代／釐清 |
|---|---|---|
| [完整格式稿](../2026-09-10-jd-format-review.md)第 86 行「尚未釐清／尚未歸屬的內容」列於「文件旁資訊」 | 把訪談疑問、文件分組與草稿保存混為一列，容易讓人以為必須有常駐 JD 待辦區 | 移除該預設區塊列，改用本文下方的一段分工說明。這是呈現推薦，不代表刪除既有草稿內容 |
| [關係研究](../2026-09-09-jd-document-relationships-working-research.md)第 70–72 行先從「員工可能先提成果、方法或問題」接到「建構中的內容」 | 原文已反對第二 Gap 系統，但仍可能被讀為每個訪談碎片都先進文件等待歸屬 | 明指「已選擇寫入 JD，或員工直接輸入的文件內容，可能尚未分組；保留其原內容。仍在釐清的訪談資訊沿 Memory／原文，不因此先建文件條目」 |
| [關係研究](../2026-09-09-jd-document-relationships-working-research.md)第 96 行待後續欄寫「未歸屬區的畫面與操作」 | 前文說尚不指定區塊，這裡卻預設有一個專區 | 改為「建構中既有內容的保存與後續整理；不預設獨立區塊」 |
| [分析指南 §4](../2026-09-09-complete-work-analysis-guide.md#4-案例工作理解與-jd如何取捨而不丟失)「將完整理解萃取為…JD」 | 單獨閱讀可能被誤解成整份工作分析完成前一字都不能寫；與既有某項足夠即可寫不同 | 若主線認為需補，改為「根據已獲得的工作理解，逐步形成有依據的職位敘述；各項資訊足夠才寫，整份持續補充」；這是消歧，不改深度要求 |

可用於格式稿的完整替代段落：

> 訪談中尚未釐清的事項，由既有訪談與工作記憶保留，供顧問後續追問；JD 不另設一份待辦區。已寫入 JD、只是尚未分組或未完整的內容仍可保存和整理，員工手改也不因不完整而被移出。若未確定的責任或條件會影響讀者理解，在相關內容就近誠實說明，不補成肯定；保存不代表已完成或核准。

需一併避免兩種相反誤解：「不設專區」不是刪除未知或未分組草稿；「允許不完整保存」也不是要求把所有訪談碎片提前變成 JD。

## 5. 官方支持到哪裡

查閱日 2026-09-10；本輪只定點讀官方 Memory／context 文件，沿用既有職務分析來源，不重做模型／框架研究或升級依賴。

| 精確官方來源／版本 | Official fact | Caliburn mapping／限制 |
|---|---|---|
| [Anthropic Memory tool：How it works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#how-it-works)及[Prompting guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)，現行 `memory_20250818`；工具無需 beta header，部分 SDK helpers 仍在 beta namespace | 記憶可保存於 context 外並按需讀回，實際操作由 App 執行；提示可限定記憶主題、維持內容一致及組織 | 支持既有 Memory 留相關未知與工作理解，沒有規定 JD 顯示區、分類欄位、追問清單或把所有未知移出文件。本案不是改用 Anthropic memory tool |
| [Anthropic Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)，2025-09-29 發表的官方工程文 | 持久筆記可在後續帶回 context；重要細節不可因過度壓縮丟失；輕量引用及按需讀取有成本／召回取捨 | 支持保存與模型可見性分開；不證明有記憶就一定找到、不支持為省 context 刪掉 JD 必要責任。文中工具當時 beta 是歷史，成熟度以本列上方現行頁為準 |
| [OpenAI Sandbox agents：Persist memory across runs](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)，現行 Agents SDK 指引，頁面無固定 release | conversation Session 保存消息；sandbox memory 提煉可重用工作資訊。讀取採導覽→正文→必要詳記；生成有抽取與整併階段 | 支持原文、理解與 context 的既有責任分界。它是 SDK 公開機制，不是本案所有資料都已自動進記憶，也不替 JD 決定章節或未知顯示政策 |
| [既有 Anthropic context 證據](2026-09-10-jd-context-anthropic.md)、[OpenAI context 證據](2026-09-10-jd-context-openai.md)，同日有界官方文件／公開碼核對 | 模型可見通知與使用者介面事件不同；存在主動提供人工變更 context 的公開接點，但無「所有產品每輪完整外部 diff」共同保證 | 已保存手改應沿既定 JD context 接線讓顧問知情；這不等於自動更新 Memory，更不能用舊 Memory 抹去尚未分析的新草稿 |

「哪些未知屬於職務重要內容」仍由本案[分析指南](../2026-09-09-complete-work-analysis-guide.md)、[欄位指南](../2026-09-09-jd-field-and-writing-guide.md)及[深度校準](../2026-09-09-customized-jd-depth-and-interview-calibration.md)判斷。模型廠商沒有公布共同 JD 格式；本文分類是可審核的產品映射，不以品牌代替職務分析理由。

## 6. 風險與後續有限核對

| 錯誤方向 | 會造成什麼問題 | 檢視時要看到的結果 |
|---|---|---|
| 所有未知都留 Memory，JD 一律刪掉限制 | 「初審／核准未定」被寫成「負責審核」，讀者誤判權限 | JD 保留已知責任與必要限定；尚未支持的肯定句不新增 |
| 所有碎片都先入 JD 待歸屬 | 工作稿混成訪談筆記，顧問可能為整理而造假任務 | 未形成成稿依據的資訊仍在既有訪談／Memory，沒有被提前確定為本人職責 |
| 移除區塊時一併移除手改或未分組內容 | 員工輸入遺失，既有草稿被舊記憶覆寫 | 同一稿保留內容；後續移動／改寫可看實際差異，未保存候選不冒稱保存成功 |
| 同一疑問分存 Memory 與獨立 JD Gap 清單 | 一邊已回答、另一邊繼續待確認，責任不明 | 沿既有 Memory 修正相關未知；JD 只有必要的內容表達，沒有平行待辦狀態 |
| 聊天說「記下了」就等同持久或可回查 | 斷線／稍後回訪時丟失分析脈絡 | 沿實際 Memory／原文結果判斷；不要求為本題每輪強制呼叫工具或另建同步 |

本題的退出條件是格式稿清楚區分這些用途、移除預設專區暗示並保留可保存不完整草稿與重要限制；不需要再擴搜。後續實作仍沿原切片驗草稿保存、手改接續、Memory／原文回查及內容更正。本次沒有重測模型或保存可靠性，不能把文義收斂稱為完整產品驗收。
