# CT15：案例保真、整理積壓與回查額度的局部審閱

2026-09-07 · LLM-Q019 · **最新（2026-09-08）：Owner 已同意 A 修復、B 局部對照與依證據選擇；22次小測後採用有界本批詳記入料，完整訪談另56次已封存，品質 gate 仍 OPEN。** 最新結論與下一題只看[CT15結果](2026-09-08-ct15-grounding-and-whole-interview-results.md)，底層來源看[OpenAI 整併入料 trace](2026-09-07-ct15-openai-consolidation-input-trace.md)。下文待審措辭只保留首輪沿革，不再當成 A／B 未授權。排程提示／5,000字備援數值仍待確認，未改。

## 1. 本輪問題與閱讀邊界

Owner 要求追查 CT14「石橋吸塵器被寫成除濕機」、只整理到 T8、層層查找耗盡工具額度，並補查 **OpenAI 與 Anthropic 的官方 prompt 指引**。目標仍為穩定完成整份工作的訪談分析；本版不接 JD／UI／production。

- **唯一 blocking question：**是否先沿既有 B1／B2 與讀取工具，局部校準「案例辨識資訊、缺依據時回查」並小額複測？其他問題先列清楚，不綁成一次架構翻案。
- **本輪 Owner 回覆：**「先看完整研究結論再改」。本稿先交付完整診斷與取捨；不把先前的一般優化授權當成本次具體方案已核准，不開始改 prompt 或付費複測。
- **已決界線：**Luna／medium；原生 reasoning／compaction；原始訪談、詳記／候選、正文／導覽及 C 修補分工不變。不新增案例表、必填模型欄位、語意驗證 Agent，不重選框架。
- **已讀證據：**[CT14 結果](2026-09-07-ct14-whole-interview-retest-results.md)、其[完整 trace](evidence/2026-09-07-ct14-whole-interview-retest.json)與逐字稿；本輪再核對 request19 的 B1 output、request20 的 B2 實際 input，以及目前程式。
- **既有研究不重做：**[資訊取捨](../../../../docs/specs/2026-09-07-work-case-and-understanding-information-selection.md)、[整理時機](../../../../docs/specs/2026-09-06-memory-generation-cadence-and-continuity-review.md)、[Memory 設計](../../../../docs/specs/2026-09-06-analysis-only-agent-memory-design.md)。本稿只持有新反證、官方提示依據及修復候選，不重貼整套設計。

## 2. 已定位的問題，不混成「prompt 不夠長」

### Q01：正確資料存在，但整併補出未讀資料

| 階段 | 本輪核對的實際內容 |
|---|---|
| T6 員工訪談 | 石橋是吸塵器運損案 |
| request19／B1 詳記 | 吸塵器外箱凹陷、機殼裂開；產品正確 |
| 同次 B1 候選 | 「石橋運損案」，未寫產品名稱；不是寫成除濕機 |
| request20／B2 input | 候選全文＋真實詳記地址＋既有導覽，**不包含新詳記全文** |
| B2 工具讀取 | 讀舊正文與舊導覽，沒有讀新詳記 |
| request22／23 寫入 | 正文首次補出「石橋除濕機」，導覽沿用錯誤，rev2 發布 |

程式對照：[B1](../../experiments/analysis-agent/src/analysis_agent/extraction.py) 的三文字產物；[B2 `_load`](../../experiments/analysis-agent/src/analysis_agent/consolidation.py) 會確認詳記可讀，但只將候選文字與地址送進 payload。**Runtime 讀過檔案，不等於模型收到全文。**

已證實錯誤出現在 B2 輸出，且新增產品名稱沒有其已讀資料支持；不能證明模型內部如何聯想，亦不能斷言單一提示句必能修好。不是 JSON 格式錯、patch 匹配錯、資料庫改錯名稱或回查 resolver 選錯來源。格式／引用存在驗證不等於事實正確驗證。

現有 B1 已寫「自成一體、保留對象與條件」，B2 也已有保真與按需回查規則。因此不再只追加同義的「不要混淆／不要遺漏」警告；需要測清楚 **何時必須取得缺少的依據，以及有依據後仍會不會混淆**。

### Q02：T8 後不是遺失，而是未排程整理

T9–20 原始問答完整保存；累積 **9,877 個可見字元**未整理。兩個啟動條件都未成立：模型沒再呼叫通知工具，字數備援未設定。背景是 idle，不是 failed／blocked。[排程判斷](../../experiments/analysis-agent/src/analysis_agent/scheduling.py)與 [API 配置](../../experiments/analysis-agent/src/analysis_agent/api.py)一致。

主顧問還有近期對話，不能因 fresh reader 失敗就聲稱它當時已忘記；但也不能說「原文在，所以不會忘」。本次 fresh reader 不知道晚期月報／FAQ／帶教，且未測 compaction。**完整來源、當輪可用 Context、已發布 Memory 是三個不同驗收結果。**

既有「段落訊號＋新文字量後備」已獲策略同意，不重問是否採用；**數值未定**。本次測試沿前次配置關閉備援，證據只顯示純模型通知不夠可靠，不能冒稱已測組合策略也失敗。

### Q03／Q04／Q06：顧問分析與摘要條件仍需校準

T15 員工提醒後才深入判斷，並不表示之前完全沒問判斷。T18 把有焦味危險時的「不再次通電」泛化成一般排查禁令；rev2 Memory 這條條件原本正確，失真在主顧問回述。T17 短暫過度收束未知，T18 又列回求償核准者。

已回看三個現有分析 Skill，深挖產出／專業判斷的方法已存在。這些是後續主顧問行為驗證，不以加固定欄位、每輪全量盤點、強制回報 Skill ID 或另一個 Judge 解決。

### Q05：有限額度會中止合法深入路徑，也有重複查找

reader1 用完 8 個工具，第9個被攔，沒有正常最終回答；不是 HTTP 失敗。主顧問預設 9 model／8 tool；背景 B2 是另一組預設 8 model／12 tool，不能用「全域8次」混稱所有路徑。[conversation](../../experiments/analysis-agent/src/analysis_agent/conversation.py)、[service](../../experiments/analysis-agent/src/analysis_agent/service.py)、[consolidation](../../experiments/analysis-agent/src/analysis_agent/consolidation.py)。

reader1 同時有可縮減的目錄探索／重複搜尋。這是診斷 reader，不含完整主顧問指令／Skills；不能把它當成正常 API 必然卡死。提高工具上限值得比較，但不會修好案例內容混淆或沒有通知背景整理。

## 3. 本次官方資料與適用邊界

以下均於 **2026-09-07**直接打開官方內容；不是引用搜尋標題推測。共同的是原則，不是 Caliburn 的特定 prompt 或數值由大廠認證。

| 官方來源 | 直接支持的做法 | 本案採用／不直接套用 |
|---|---|---|
| [OpenAI：GPT-5.6 family prompting guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6) | 明確目標、成功條件與依據；移除重複／矛盾指令；保留顯式值；必要依據缺少時取得資料，否則縮限回答而非猜；每次局部改動後重測。 | 作為 Luna／medium 的 family 層參考；不搬用其 coding 實驗提升百分比，不換模型／effort，不整包改寫 prompt。 |
| [OpenAI：Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering) | 分清規則、例子、Context；示例須多樣、能代表需求；提示與測試一起版本化；推理模型仍需要清楚目標與限制。 | 保留固定提示／動態資料分隔及同版對照，不新增託管 prompt 平台；不要求輸出隱藏推理。 |
| [OpenAI Cookbook：Memory consolidation §4.2](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization#42-memory-consolidation) | 整併是容易引入長期幻覺、遺失與矛盾的階段；需要控制去重、修正、淘汰的積極程度。 | 支持先追 B2 事實來源。這是官方範例，不是證明 Codex 內部完全使用本案流程；不直接採用跨用戶／跨文件 Memory。 |
| [Anthropic：Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | 明確直接、解釋原因、區隔資料／指令／例子；示例應相關且多樣；讀相關檔案再作有依據的主張。 | 學習原則，用不同職位的少量短例測試；不是把 Claude 專用模板、模型設定、固定示例數全部塞給 Luna。 |
| [Anthropic：Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations) | 允許未知、依據相關來源與引句核對主張；這些方法不會完全消除幻覺。 | 沿已存詳記核對缺少的案例事實。**不因此恢復必填逐字 quote／Skill／來源位置欄位**；也不採該頁的外顯 CoT 或每次多模型驗證選項。 |
| [LangChain：Model／Tool call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit) | 框架可配置 model 與 tool 限額、run／thread 範圍及停止行為。 | 沿現有官方 middleware 校準，不另造限流器；官方範例數字不是所有 Agent 的最佳值。提高上限不等於每輪必用滿，實際成本仍需記 usage。 |
| [LangChain：Writing memories](https://docs.langchain.com/oss/python/concepts/memory#writing-memories) | 背景整理有新鮮度／重複成本取捨，何時觸發由應用選擇，沒有單一通用頻率。 | 沿已核准段落通知＋字數備援，不假稱固定字數是 OpenAI／Anthropic 共識。 |

**不盲合併建議：**Anthropic 提供 few-shot 的具體數量／長文引句策略；OpenAI 5.6 指引要求刪掉無效重複與多餘示例。兩者不能合成「每輪多放五個例子必然最佳」。先以一個真正改變決策邊界的短例做原情境與不同職位對照，無改善就撤回；所有語意提升結論都須真測。

## 4. 三個可比較選項

| 選項 | 好處 | 成本／限制 |
|---|---|---|
| **A：保留現有分層，校準缺依據時的檢索規則（建議先做）** | 不改資料與工具契約；一般共同工作沿候選整理，精確案例屬性缺依據時讀相關詳記。B1 候選保留足以區分案例的資訊；B2 不憑鄰近案例補產品／角色／條件。 | 需要時會多讀取與生成；模型仍可能不遵循，不能只靠 prompt 承諾正確。 |
| B：本批詳記也直接進 B2 Context | 讓本批正確依據一開始可見，可測是否主要是漏讀，也可能減少往返查找；不是把全部歷史放入 Context。 | 本批 input 變大，仍可能混淆；改 B2 入料策略須另確認，不先上線。 |
| C：另加事實核對模型／必填逐項來源 schema | 可能增加交叉檢查能力。 | 多一次或多次生成、更複雜欄位與錯誤迴圈，也不能保證語意正確；本輪不建議。 |

A 不保證總成本比 B 低：按需查找需要額外 model step，而 B 可能增加每步輸入。要比較正確率、實際 input／output／快取、工具次數與延遲，不只比較首個 prompt 長度。候選未寫所有詳記屬性本身不一定是錯；真正的錯是 B2 將沒有依據的精確屬性寫成已知。

### A 的短設計（待 Owner 確認）

- 保留三個抽取文字欄位，不加 case_id／產品欄位表單。候選中的案例名稱、已知對象與關鍵差異應足以辨識；不為填滿而發明未知屬性。
- 整併要寫一個候選／已讀正文沒有支持的精確細節時，沿同批 `summary_path` 用既有 `read_file` 讀相關詳記；有必要且有依據才寫。不需要該屬性就保留原本較窄說法，不補猜。
- 已有來源支持時不要求重新讀所有詳記，不改成每批必讀到底。共同模式可歸納，不能把個案身分或適用條件互相移植。
- 精簡這組規則附近的重複句，補一個不含 CT14 客戶／產品答案的短例；先只改 B1／B2，不同時變更整套主顧問／Skills／模型／排程。
- 若仍然混淆，先比「正確資料已有沒有實際進 B2」再決定選項 B；**不繼續無限追加警告句**。

## 5. 相鄰項目的下一步，不自行定案

1. **Q02：**在 A 小測後，校準現有通知工具何時值得呼叫（已有一段進展、轉入下一工作範圍、整理收尾有新內容，不要求主題完全無未知）。同時考慮啟用已存在的文字量備援；初值要按實際新文字量與成本比較，不能抄回已退役的 6,000 字預設當成共識。短收尾也可能未達門檻，所以備援不能單獨保證最後一段已整理。
2. **Q05：**可先給同一回查情境較充裕的有界 model／tool 額度，觀察它是否完成、為何繼續查；若成立再調可配置產品預設。保留正常最終回答的 model 空間，所有實際請求計成本；不因上限較高就要求用滿。不把一次成功當作上限最佳。
3. **Q03／Q04／Q06：**案例保真修復獨立成立後，再測顧問是否自主深問、回述保留條件、未知沒有被漏列；先用已有 Skills，不增加新流程。

## 6. 最便宜的可信複測與停止條件

先本機回歸（框架接線與資料不丟），再用 Luna／medium 小額真測；不新建大型 eval 系統。**本輪研究用量 0 次／US$0。**

1. 重播同一批 B1 來源，確認候選能區分案例、不新增未講的產品／權限，既有有用細節仍在。
2. 單獨重播 CT14 的「缺產品候選＋正確詳記＋舊正文」，避免 B1 改好後掩蓋 B2 仍會補猜。檢查真工具路徑與發佈結果，不只 schema 通過。
3. 換一個職位的相似案例／條件例外作獨立驗收情境，不能把原測客戶或答案寫進提示。校準例子與驗收資料分離。
4. 原案例小測成立後，再跑真服務入口的完整長訪談；記自然背景觸發、處理游標、最新 Memory、晚期工作回查、成本及自主訪談深度。**不得靠手動補整理或測試者提醒才算通過。**
5. 必須另覆蓋實際 compaction 後的延續與回查；CT14 的20輪沒有觸發壓縮，不能拿它代替。

接受標準：相似案例不串案；已知更正及條件正確；所需晚期工作可回查；普通訪談不強迫每輪整理；在有界成本內完成回答。詳細原文保留但模型找不到仍算能力缺口。任何模型／框架／資料契約變更先回到討論。

## 7. Closure

- **Finding：**案例問題已追到 B2 無依據新增屬性；原文／詳記正確。積壓是通知與備援皆未啟動；上限是另一個獨立問題。
- **Status：**CT14 品質 G8 仍 OPEN；本稿是 CT15 G2 結果，Owner 先審完整結論，A 短設計待 G3，不表示已修復。
- **Next gate：**Owner 確認 A 後先做局部小測；Q02／Q05 不因研究完成就自動改預設。重測前另記實驗護欄，沿用已准模型與費用紀錄方式。
- **寫回範圍：**本稿＋root current-decisions 路由；歷史 CT14 證據不改，產品 source／DB／配置未改。
