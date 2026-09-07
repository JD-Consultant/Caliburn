# CT13：CT12 訪談品質與回查問題的局部修法研究

2026-09-07 · LLM-Q019 · **Owner 已同意局部方案 A；改做法前必須查清官方實際底層，再分段施工。**

**接續結果：**已完成方案 A 的隔離提示校準、原文回查及完成判定測試接線；[CT13 結果](2026-09-07-ct13-local-repair-results.md)為目前狀態。580 項含 PG 回歸通過、0付費；語意／長訪談仍待真測。下文原建議與未施工描述保留為沿革。

接續狀態：Owner 回覆「同意」，並要求不能只模仿概念就自行發明底層。以下初次研究的「待審／未核准」是當時狀態，由本段更新；無新付費測試授權。A3 來源回查已完成[官方 producer→consumer 與框架底層核對](2026-09-07-source-read-runtime-resolution-trace.md)，補明「純回查不依賴候選檔」及「前置問答脈絡不能漏」；尚未改工具或其他產品程式。

## 1. 本輪問題、邊界與閱讀路由

唯一決策題：CT12 已能跑完訪談與背景整理，但出現範圍失真、過早收尾與回查問題，下一步應採哪一組最小修正？

Owner 最新要求「那要怎麼辦？請你研究」；先前「先保留紀錄，訪談測完再討論」仍有效。因此本輪只讀證據、查官方資料、提出方案，不改 prompt／Skill／工具／配置，不追加付費測試。CT12 的 65 次／US$0.07783077 帳本保持關閉。

閱讀順序：[決策入口](../../../../docs/current-decisions.md) → 本篇 → [CT12 結果](2026-09-07-patch-and-whole-interview-results.md) → [逐字稿](evidence/2026-09-07-patch-and-whole-interview.transcript.md)／[原始 trace](evidence/2026-09-07-patch-and-whole-interview.json)。職務資訊取捨沿用已核准的[工作案例與工作理解研究](../../../../docs/specs/2026-09-07-work-case-and-understanding-information-selection.md)，不重開整套 Memory，不重新閱讀已排除的產品流程長稿。

本輪完整讀了上述兩份短研究／結果、現行 B1/B2 提示、三份分析 Skill、主顧問指令、Memory 讀取／引用程式；另逐筆查看 request 1、18、47、59、60、65 及第 7、11–14 輪相關內容。下列「現象」有直接 trace；「哪段提示會改善」仍是假設，不能混稱已修復。

## 2. 先分清原因，不把全部問題歸咎於工具或上限

| 問題 | 可證實的資料流 | 判斷與尚不能證明的事 |
|---|---|---|
| Q01 範圍縮窄 | request 1：原話／詳記是「上月案件」，同一 B1 輸出的候選卻加了「退換貨案件」；B2 據候選寫入 | 首個失真在 B1 候選，不是 patch 匹配或資料庫遺失。附近有退換貨敘述，但不能斷言模型內部為何這樣推論 |
| Q03 條件遺失 | 第 6 輪原話與當輪回述均有「日期未確認」；request 18 詳記保留，候選省略；request 21／37 正文局部沿用無條件說法 | 條件不是原文沒給，也不是所有正文都錯；局部無條件句與其他正確句並存，會誤導後續使用 |
| Q03 回答跨範圍套用 | request 47 將安全事件的禁止通電放進一般排查；65 將月報試算表套到受理、把未確認頻率的物流事項列為低頻 | 找到資料不等於語意用對；只修 B1 不能證明 reader 的組合推論也已修好 |
| Q04 用詞變義 | **第 7 輪顧問已把「依訂單去重建案」回述成「案件重建」**；request 18 詳記再寫「依訂單重建案件」，47 沿用 | 是主顧問也發生的問題，不只背景抽取。顧問的改寫不應被後續當作員工的新事實；中文連寫有歧義的程度不能由機械測試判定 |
| Q02 過早收尾 | 第 11 輪自行稱完整；員工第 12 輪提醒專業判斷／做好標準後，顧問才讀 outcomes Skill、續問 | 現有三份 Skill 已涵蓋相關方法，但主指令沒有清楚的整體收尾條件；屬提示／選用時機缺口，不證明需要另一位 agent |
| 回查繞路／地址抄錯 | 第一次精確回查在診斷 7 步用盡；補測第 59 次抄錯長來源碼，60 修正後讀到原文，63 完成 | 現有工具能回錯及恢復；沒有「原文永遠找不到」。但搬運長編碼是可移除的負擔；單次失敗不能算一般錯誤率 |
| 長答截斷 | request 47 為 `incomplete/max_output_tokens`，4096 中含 317 reasoning tokens | 是輸出額度耗盡，不是這次觸發了 compaction。診斷 reader 未使用產品的 TurnValidation，不能據此聲稱服務會把半截答案當成功 |

## 3. 官方直接說了什麼

以下頁面於 **2026-09-07 實際重新取得並閱讀相關段落**；日期是查閱日，不把舊文章改稱當天發布。OpenAI／Anthropic 的產品原理可交叉參考，但不存在「每家都使用本案相同提示、工具參數及上限」的證據。

| 來源與精確章節 | 直接支持 | 不支持的過度推論 |
|---|---|---|
| [OpenAI GPT-5.6 family prompting guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)：Simplify prompts／Outcome-first／Grounding／Prompt migration | 清楚寫成果、證據、保留內容及停止條件；刪重複規則；按真實退化局部修改、一次控制一種變因；縮短先去重複，不刪必要事實與限制 | 其內部測試成效不能套成本案 Luna 的預測改善百分比；不是把提示愈堆愈長 |
| [OpenAI Structured Outputs：Handling mistakes](https://developers.openai.com/api/docs/guides/structured-outputs#handling-mistakes) | 合規輸出仍可有內容錯誤；可調指令、示例或任務拆分 | JSON／Pydantic 通過不代表員工事實正確；沒有要求自製逐句語意 validator |
| [OpenAI Reasoning best practices](https://developers.openai.com/api/docs/guides/reasoning-best-practices#how-to-prompt-reasoning-models-effectively) | 簡潔目標／限制，先零樣本、必要時少量一致示例；不必要求公開逐步思考 | 不能把所有反例灌進每輪 prompt，也不要求輸出或保存隱藏推理 |
| [Anthropic：Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations#basic-hallucination-minimization-strategies) | 允許未知、按來源作答及核對支持；相關短原句可協助 grounding | 不能保證零幻覺。其頁面的長文逐句引用／多次驗證是選用手段，不是本案必須加的新 schema 或每輪模型 |
| [Anthropic Memory tool：Prompting guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance) | 可以指定保存哪些主題，維持一致與有組織；工具已有說明不用重複 | 工具不會自行判斷職務資訊是否被過度概括，也不代表要更換已選的 B/C 架構 |
| [OpenAI Function calling：Best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)；[Anthropic Writing tools](https://www.anthropic.com/engineering/writing-tools-for-agents)，Returning meaningful context／Token efficiency | 已知參數交程式處理；減少難抄識別碼，提供清楚輸入／有用錯誤／分頁 | 不代表完全不能用 ID，也不必另造一份來源資料庫；具體用既有詳記地址是本案映射 |
| [LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools#access-context)；[DeepAgents BackendProtocol](https://docs.langchain.com/oss/python/deepagents/backends#implement-the-backend-protocol) | ToolRuntime 可隱藏 state/config；工具透過公開 backend 讀取與回傳結果 | 框架不自動知道 Caliburn 的來源 header，該解析仍是應用接線，不能冒稱原生完整方案 |
| [OpenAI reasoning output 預算](https://developers.openai.com/api/docs/guides/reasoning#allocating-space-for-reasoning)；[LangChain call limits](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit) | output 含推理；要辨識 incomplete，按任務配置空間；框架提供可配置模型／工具次數限制 | 4096、7、9 都不是大廠共同最佳值；也不能機械套用文件的初始 25000 建議，或直接取消所有限制 |
| [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)；[O*NET Content Model](https://www.onetcenter.org/content.html) | 理解工作活動、情境、所需知識技能及其關聯 | 不提供「14 輪即完整」或本產品精確收尾算法；不要求填滿 KPI、學位、A／L 或不知道的外部主管資料 |

本次亦重讀 [Codex local memories](https://learn.chatgpt.com/docs/customization/memories)：其持久記憶含摘要、耐久項目與聊天佐證，不是唯一規則來源；這支持保留回查分層，**不能證明 Codex 的摘要不會失真**。更細的抽取／整併既有研究沿§1路由，不用重開一遍。

## 4. 建議方案 A：沿原流程局部校準，按失真位置修

### A1. 保留事實的適用範圍，而不是要求更多文字／更多欄位

現有 [B1](../../experiments/analysis-agent/src/analysis_agent/extraction.py)、[B2](../../experiments/analysis-agent/src/analysis_agent/consolidation.py)、[讀取指引](../../experiments/analysis-agent/src/analysis_agent/memory_tools.py)已經有許多「保留條件／不把個案當通則」規則。下一步應**取代含糊或重複語句**，先局部校準一條可核對的輸出要求，不再無限制追加警告。

擬測的要求是：整理可以改措辭，但同一項事實的「對象／本人做法／適用條件／頻率／權限」不能因縮寫或分組而變成另一個意思。這些是閱讀檢查面向，**不是五個新必填欄位**。

- B1 的候選可比詳記短，但不能增加詳記／員工未支持的範圍；缺少條件會改義時，保留完整短句。對可能誤切的工作用語，以員工用詞及問答脈絡為準，不能因顧問先前改寫過就升格為員工事實。
- B2 仍可用自成一體的候選；如果候選與已讀內容不一致、語句不足以確定限制，或準備擴大／縮小既有工作邊界，沿現有 `read_file` 補讀相關詳記。**不是強制每批讀完所有詳記，更不是每輪重讀全部原文。**
- 主顧問與 reader 同樣維持事實邊界；歸納共同模式時，不能把某案例的工具、頻率、禁令套給全部工作。沒有依據就保留未確認；有實際影響的歧義才問員工。
- B1／B2／回答各自只輸出其原有產物；核對不要求暴露內部推理，也不新增「我已驗證」欄位。舊 trace／Memory 不手工洗成成功；之後要修已存實驗資料，另走既有重抽／修補流程並保留歷史。

用 CT12 說明效果目標，**不是把測試答案硬寫進正式提示**：

| 原資訊 | 可接受整理 | 不可悄悄變成 |
|---|---|---|
| 日期未確認，不能承諾 | 未確認補貨日期前不對客戶承諾 | 所有補貨日期都不可承諾 |
| 月報彙整上月案件 | 上月案件月報；範圍依原資料 | 僅退換貨月報，或反過來自行補成所有公司業務 |
| 月報需用試算表去重 | 月報：試算表去重；受理：已知按訂單辨识同案 | 受理也必用試算表 |
| 某安全案例禁止通電重現 | 安全事件按該限制處理 | 所有一般排查都套同一禁令 |

依§3 OpenAI prompting guidance／reasoning best practices，先測簡短直接要求；若仍失敗，才用少量**不同合成情境**的對比示例，不能直接擴成全套表單。本案效果仍須小測，不能承諾改一句就好。

### A2. 收尾前核對工作全貌與專業深度，不增加另一位 agent

在現有主顧問指令與三份 Skill 的選用描述中，補清楚「何時能稱訪談整體已充分了解」：不只知道工作名稱，還要對已發現的重要範圍理解本人做法、責任／交接、重要條件、結果及實際專業判斷。可以由不同案例合併支持，不要求每個案例重新問一遍。

準備收尾時，顧問先對照目前對話與必要 Memory；若有專業／做好標準的重要未知，使用現有 outcomes Skill；內容已在有效上下文就不用重載。仍有關鍵問題就自然問下一題；員工不知道的事項維持已知／未知界線，不無限重問。不必每輪跑全面盤點，不加 gap 表、進度分數、固定問卷或新的完成工具。

完成表述應準確：能說明目前涵蓋範圍及尚未確認的限制，不以反覆「最後一題」或一句「完整」充當驗證。員工仍可隨時停止或下次續談；外部資料未知不自動阻止休息，也不為收尾編造 KPI。這是§3 OpenAI 的成功條件原則＋已核准職務方法的本案映射，不宣稱 OPM 給了 LLM 停止算法。

### A3. 讓程式代取已知原文地址，保留現有工具／儲存／隔離

**實作前必讀補證：**[CT13-A3 底層核對 §2–5](2026-09-07-source-read-runtime-resolution-trace.md)。下文直接呼叫 `extraction_window` 是初案；補查發現它兼做重抽檢查，應共用 metadata 解析而非讓純回查也依賴 candidates，並保留前置問答與 C 直接來源。這是已核對框架的應用接線，不可稱為 Codex 有相同專用工具。

現況：模型讀詳記後，需把包含 document、checkpoint、first、last 的長 `conversation:` 編碼抄進 `read_conversation`。request 59 只差一個字元就指錯 checkpoint。

建議在**同一既有工具**增加更易用的讀法：模型提供已看到的詳記地址；程式用既有 [MemoryArtifacts.extraction_window](../../experiments/analysis-agent/src/analysis_agent/memory.py) 取出系統保存的真正 source reference，再交現有 [ConversationReader](../../experiments/analysis-agent/src/analysis_agent/sources.py) 分頁讀取。模型選哪份資料，程式處理其已知內部定位。

這不增一個模型工具或新資料表，不重存原話，不讓模型填 checkpoint；不是向量搜尋重設計。**現有 C 即時修補仍可能引用沒有詳記的原始來源，不能因只支援詳記地址而切斷它**；既有合法來源讀法要保留，不能將所有來源強制變成新詳記。詳細參數名稱在獲准後按現有工具契約收斂，不先定新複雜 union。

既有 header 解析與文件 scope 檢查仍保留。無效地址應明說未讀取，提示從已找到的詳記取得地址，絕不猜測、模糊匹配或退回最新原文。這是 OpenAI 的已知參數代填／Anthropic 的識別碼簡化原則，透過 LangChain ToolRuntime 與現有程式承接；**不是框架自動原生解析我們的 header**。

解析邊界：`extraction_window` 目前不只讀 header，還確認配對的 candidates 檔存在。只適用系統已保存、格式可驗的詳記；不能承諾任意 Markdown 都能反查。局部試接要覆蓋配對檔缺失、歷史無 header、C 直接來源與分頁，不能用猜測修復引用。

### A4. 對齊測試與產品的完成判定，按任務調整額度

下一次 reader 驗證應重用真正服務或相同公開 factory／完成驗證，不能再以裸 loop 的 `recorded` 充當成功。沿現有 LangChain 計數與 incomplete 檢查，不另寫一套 retry 管理。

一般問答優先簡潔，刪除重複不是刪除限制。需要完整總覽時，可以配置較大 output 預算；是否增加以實際長度與費用比較決定，不擅自拆成不完整的短答案。模型步數也要容納找到資料後的最終回答；先減少無用重搜／抄錯，再判斷既有 9／8 是否足夠，不把加兩步當万能修復。

CT12 只證實診斷 reader 的失敗及補測恢復；本輪不冒充已發現產品同樣失敗。額度調整不解決 Q01／Q03 的語意失真，不能用「終於 completed」作內容通過。

## 5. 三個實質方案與取捨

| 方案 | 效果、成本與風險 | 建議 |
|---|---|---|
| **A：分段校準提示／收尾與回查介面** | 保留 ABC、官方 patch、原生推理與框架；不固定增加 LLM 呼叫。疑點才多讀。能直接針對首個失真位置，但不能機械保證語意正確 | **優先**；A1先做，A2／A3／A4各自驗證，不一次混改後宣稱因果 |
| B：額外模型檢查每份候選／每次回答 | 可做独立語意核對，但多一輪以上成本與延遲，judge本身也可能錯；本案尚無證據其收益值得 | 後備；只有 A 的代表性失敗仍反覆出現時，針對背景抽取等高影響步驟比較，不全回合強制加 |
| C：只提高步數／output／推理或換更強模型 | 可能降低截斷或某些推理錯誤，但不修難抄地址與缺少收尾目標；成本增加不能保證範圍保真 | 不作單一解法；維持 Luna／medium 基線，必要時局部對照，非全產品直接升 max |

## 6. 核准後怎麼驗，不重跑大實驗

1. **內容校準：**同一模型／effort／輸入，先對照已封存的 Q01、日期條件、案例限制、去重用詞；另用不同職務的同型變體查是否只記住舊答案。逐筆核對原話→詳記→候選→正文→回查回答，允許等義文字；格式 PASS 不是品質 PASS。
2. **收尾：**從第 11 輪之前的同一已知訪談狀態續測，不給顧問 oracle 或第 12 輪的提醒答案；看是否主動查出重要深度缺口，同時不追問已回答／不知道的外部規則。不硬規定必讀某 Skill 才算正確。
3. **讀取：**先離線證明詳記地址及直接來源仍讀到相同 canonical 範圍，跨文件／缺檔／格式不明明確失敗；再針對性真讀取，檢查錯誤、分頁、最終 completed 與回答內容，不要求一律讀到 EOF。
4. **整體回歸：**各小修正過關後才做一輪正常訪談，記錄請求、usage、延遲、來源正確性與收尾。真正 compaction／第二職位長訪談仍另列，不混成 CT12 已驗過。

本輪不執行以上測試、不建立大型 eval；真測費用在下一 gate 明確界定。若同一失真經局部校準仍重現，不持續疊提示：回報哪個邊界仍失真，再討論 B 或背景模型局部對照，不能擅自翻案。

## 7. Closure

- **Finding：**技術流程可跑與引用可讀已有證據；語意失真與收尾門檻仍 OPEN。新增確認 Q04 在主顧問回述已出現，不能只修改背景。
- **Status：**方案 A 為研究建議，待 Owner 審閱；不是已核准、已修復或滿分驗收。
- **變更：**只新增本研究與主決策入口路由；產品、prompt、Skill、schema、Memory 資料與配置均未動。0 次付費模型請求／US$0；不 merge／push。
- **來源／可重看位置：**§1 本地證據、§3 官方連結、§4 對應現有程式；CT12 原 trace 不覆寫。
- **下一 gate：**Owner 審阅是否採 A，優先校準「不改變事實範圍與條件」，再按切片修讀取與收尾；本題已有可驗證方案，不再無限廣泛搜尋或重開框架選型。

限定唯讀交叉審查確認 Q04 的主顧問先發偏差、既有提示／Skill 已有內容，以及裸 reader 不等於服務失敗；另指出來源解析需配對 candidates，已補入 A3。主審核對了對應程式及 trace。這是研究事實與方案邊界核對，不是語意修正已通過測試。
