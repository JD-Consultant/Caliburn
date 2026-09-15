# Q019 Memory：五產物、漸進回查與 B／C 協調

> 2026-09-06 · **Owner 同意進入隔離開發的 Working Design；artifacts／回查／原子發布／B1／B2／C局部修補與A受控刷新已實作並完成隔離測試；第七切片獨立review無Critical／Important阻塞，尚未正式產品整合。**
> 最新範圍與限制見[第七切片結果](2026-09-06-analysis-only-agent-live-memory-results.md)：120 passed／0 skipped，包含PG重建clients恢復，付費呼叫0。排程／產品retry-cancel-replan／真實品質測試仍未提供。前段[整併結果](2026-09-06-analysis-only-agent-consolidation-results.md)、[抽取結果](2026-09-06-analysis-only-agent-extraction-results.md)、[發布結果](2026-09-06-analysis-only-agent-memory-publication-results.md)、[回查結果](2026-09-06-analysis-only-agent-memory-read-path-results.md)保留沿革；不是自然模型分析品質或全套 Memory 完成。
> [總覽](2026-09-06-analysis-only-agent-design.md)持有範圍／選型；[Runtime](2026-09-06-analysis-only-agent-runtime-design.md)持有 A、原生推理及 Context。本稿不新增 JD 或獨立工作理解表單。

> **最新保存點：**[詳記重抽切片](../../.worktrees/analysis-only-agent/docs/specs/2026-09-06-summary-reextraction-results.md) 已完成，226 passed／0 skipped，獨立 R1/R2 複核 CLOSED；commit `4e0438bc`／tag `q019-summary-reextraction-v1`。上段第七切片數字是沿革；本次仍不接正式產品、不做真模型品質保證。

## 1. 保存責任與五個概念

> **WORKING，2026-09-06 詳記更正切片：**Owner 已准隔離實作「同段可重抽、跨段由目前正文記錄更正與詳記引用」，不承諾任意舊詳記自動取得全部後續更正。[接法 §7](2026-09-06-interview-summary-correction-routing-proposal.md#7-已授權的小切片工程接線)與[實作／驗證紀錄](../../.worktrees/analysis-only-agent/docs/specs/2026-09-06-summary-reextraction-results.md)持有最新狀態。下文 immutable 指已發布實體不原地改寫；重抽另存詳記／候選，由 B2 核對理解及引用，沿既有 repair publication 發布且不挪動普通來源游標。原文保留，無新 Case table、來源庫或模型填寫欄位。這是 framework mapping，不宣稱資料庫底層與 OpenAI 完全相同。

> **2026-09-16 分層／版本精確化：**「已發布 artifact 不原地改寫」不等於「詳記永遠不能更正」。同一來源窗口整理錯誤時，沿既有 reextraction 另存修正版詳記／候選，再由 B2 核對 knowledge 與引用；使用者後來才補充或更正時，保存新的 canonical 原話與新詳記，由 C／B2 維護目前 knowledge，不要求把所有早期詳記改寫成彷彿當時就已說對。publication revision 選出一組一致可解析的 knowledge／guide／references；未變的詳記可被新版 publication 繼續引用，不必全部重產或擁有相同版號。一個案例也可能由多份不同時點的詳記共同承接；歷史詳記不是會自動吸收所有後續資訊的「案例目前全文」。這是既有設計澄清，不新增 artifact／table／writer 或測試工作。

> **Codex 參考界線：**[OpenAI Docs 的 local memories 說明](https://learn.chatgpt.com/docs/customization/memories#how-local-codex-memories-work)直接支持背景處理合格舊聊天、生成 summaries／durable entries／recent inputs／supporting evidence，以及 extraction／consolidation model 可分開設定；它沒有規定 Caliburn 的五產物 schema、同版號、immutable Store 或 publication CAS。公開 source trace 中的 `rollout_summary`／`raw_memory`／同步與 upsert 行為可作研究參考，但本稿的重抽另存、引用穩定與版本基準仍是 Caliburn 自己的產品／保存契約，不冒稱 OpenAI 官方要求。

同一訪談範圍內，使用三種資料責任：

| 保存位置 | 內容 | 不承擔什麼 |
|---|---|---|
| 官方 LangGraph Checkpointer | canonical 訪談、完整模型／工具 items；A／B 執行進度 | 不當成向量搜尋引擎，不用摘要覆寫原文 |
| 官方 PostgreSQL Store＋StoreBackend | 詳記、候選、正文、小型導覽；已發布版本不可原地改寫 | 不假設普通 put 自帶跨檔發布交易／CAS |
| 小型 SQLAlchemy publication metadata | 目前版本／artifact 路徑、來源處理游標、提交回執 | **不放第二份工作理解或對話內容**，不是另一套 Memory engine |

最後一列是[§6 必要接點](#6-背景與即時修補可以並行但發布不能互相覆蓋)。它相對前輪單 Store head／process lock 草案是公開列出的改進提案；不能說框架已自動做完。

| 已研究 OpenAI 概念 | 本版用途、內容與產生者 | 保存／讀取 |
|---|---|---|
| raw rollout／Conversation | 員工、顧問及工具實際往返；原生 reasoning 另保留但不供 B 解碼 | Checkpointer；A 可精確回查，B1 使用已完成訪談視窗 |
| `rollout_summary` | **訪談詳記**：具體案例、條件、限制、數量、例外、當時未解／更正；B1 生成 | Store 不可變 artifact；供 A／B2 深讀；header 由系統加入原文定位 |
| `raw_memory` | **工作資訊候選**：這段值得補充、修正或保留的訊號，尚非整體現況 | Store 不可變 artifact；主要供 B2 整併，不是 A 每輪必讀 |
| `rollout_slug` | 人可辨識的短名稱，不是知識、權威 ID 或全域唯一鍵 | B1 建議；系統清理字元並配真實 artifact identity |
| `MEMORY.md` | **工作理解正文**：按主題的可修訂知識、適用條件、差異／未知、可搜尋詞與詳記引用 | 每次發布新版本；A 搜尋／讀取、B2 整併、C 局部修補 |
| `memory_summary.md` | **工作理解導覽**：短路由提示與案例別名，指向正文主題 | 與正文一起發布，A run 開始載入；**沒有第六份額外導覽** |

五產物／producer-consumer 的原始證據沿用[OpenAI 系統圖 §5](2026-09-05-openai-conversation-context-and-memory-system-map.md)、[摘要引用路由](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)、[單訪談流程](2026-09-05-work-understanding-memory-flow-working-design.md)。SDK 官方也明確區分抽取、候選及 layout 整併。[Sandbox Memory](https://openai.github.io/openai-agents-python/sandbox/memory/)

### 表徵：用文件承接細節，不先造案例／Task schema

正文與詳記用 Markdown，schema 只放必要身份與機器 metadata。正文可以分成聚焦小節；小節包含主題、適用情況、完整敘述、可搜尋詞與來源引用。未知／矛盾寫在相關敘述中，不要求額外狀態 enum／Gap 表／Skill ID。模型整理案例共同模式，但不能把 A 案例的限制錯套到 B。

「依客戶需求開發前端網站」可進正文；A 網站付款流程、B 網站權限設計留在各詳記，需要影響一般工作模式的差異也進正文。不是每案例固定新增一個工作任務，也不是所有細節都硬塞進小導覽。

**可找回細節有兩層：**詳記盡量保留有用細節，完整訪談是最後核實來源。生成的詳記／正文不是無損壓縮，不能承諾所有細節必然已被正確提煉；必要時仍能找到原文。保存完整來源不等於模型一定會想到去找，查找效果另驗收。

### 2026-09-07：Memory prompt 調整與驗收重點

> **最新內容校準：**Owner「繼續」後只調 B1 的已知工作候選與陳述歸屬；一組 Luna／medium 完成三次整併，未答追問不再撤銷既有說法，真正改口再修正。完整回查仍被原整組實驗額度擋住，尚未驗收。本輪只在[短結果／官方來源／精確實測](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-b1-attribution-calibration-results.md)記錄，不重複擴寫本稿；後續先讀該結果，下面早期試驗是沿革，不宣稱目前程式仍未調整。

**Owner 最新偏好／WORKING：**優先調整 Memory prompt，目標是「對話 → 各種完整案例細節也保留 → 工作理解」。這是既有五產物的內容取捨與效果要求，不新增案例資料表、不把案例都改寫成 JD 任務，也不改 B／C 的發布及更正規則。

- **抽取／訪談詳記：**保存員工已提供的工作案例脈絡、本人行動與責任、條件、處理方法、數量、限制、結果、例外及尚未說清楚之處。可以整理口語與重複敘述，但不能因低頻、不是共同模式或看似類似，就刪掉該案例不同的工作細節。不是固定欄位清單，也不補造員工未說的內容。
- **工作資訊候選：**「沒有新的共同工作模式」不等於「沒有新資訊」。新案例、既有案例補充／更正、會影響回查的差異也可能是整併訊號；候選提供訊號與詳記路由，不另複製整份詳記。此點是目前簡短 prompt 的待實測風險，尚未證明現有模型一定會漏。
- **整併／工作理解：**整理員工一般在做什麼、責任範圍、共同模式及成立條件；需要影響理解的差異也保留。相似案例不用機械複製成多項相同工作，但應維持足夠的案例別名、搜尋詞與詳記引用，讓不同案例仍可被找到；不把全部案例正文灌進工作理解或小型導覽。
- **小額測試重點：**同類A／B案例有不同條件或做法→再補A細節→更正A但不改B→隔數輪重新問兩案。分別檢查詳記保留、候選是否傳遞新增訊號、正文是否誤合併／混用，以及能否沿引用找回正確案例；不能只看最後回答順暢，也不能只因原始對話還在就當整理品質通過。尚未提供細節要如實說未知。

**依據與界線：**已回讀本稿的五產物與原文邊界、[OpenAI詳記內容／整併／回查的固定source研究 §3–4](2026-09-06-openai-rollout-summary-correction-source-review.md#3-不同詳記談同一案例比對與修訂在哪裡發生)，並核對隔離程式的 [B1 prompt](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/extraction.py)與 [B2 prompt](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/consolidation.py)。當日重讀的 [OpenAI local memories官方說明](https://learn.chatgpt.com/docs/customization/memories#how-local-codex-memories-work)支持抽取、整併及不同記憶產物分工，**不保證完整保留所有工作案例細節**；上述資訊保留優先順序是本產品要求，不冒稱 OpenAI 原封採用同一 prompt。

#### 職務分析研究如何作為 prompt 參考（2026-09-07 Owner 補充）

**已確認用途：**既有「怎麼分析職位」研究也作為訪談與 Memory prompt 的方法參考；不是只教模型保存文字。效力仍限 Q019 只分析版，不因此加入 JD 編輯、固定 Task／OPKS 輸出或另一套工作理解 schema。本輪完整回讀下列三份研究並核對隔離版三個分析 Skill；舊稿中的方法、已否決建議及歷史施工安排須分開看。

| 使用處 | 從研究取用的方法與目的 | 不一起搬入 |
|---|---|---|
| 主顧問／按需分析 Skill | 從具體事件了解服務對象、目的、本人做法與判斷、交接及完成條件；由深挖案例返回其他工作範圍；有歧義先問，不重問已清楚事項。參考 [R1 §4–8](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)、[最小迴圈 §2.2、§4](2026-07-30-professional-consultant-minimal-complete-loop-research.md)。 | 固定問卷、每回合必產 Task、舊模型呼叫數與舊狀態欄位。 |
| B1 詳記／候選 | 辨認本人／他人、現在／過去、例行／臨時支援、方法、結果、條件及不確定；短答須連同問句理解。尚不足以形成穩定工作、甚至不是本人職責的案例，仍保留其真實脈絡，不用 JD 入選標準篩掉記憶。參考 [R1 §4、§6](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)。 | Source Claim／Work Unit 等舊物件、逐字 offset／Skill ID；不把顧問問句的假設當員工事實。 |
| B2 整併工作理解 | 比較目的、本人責任、結果、對象與條件：多案例可補充同一工作，一案例也可包含不同責任；工具／步驟不機械升格成工作，文字相似也不能抹掉差異。形成可修訂的工作敘述並保留案例回查，而非完成 JD 分類。參考 [R1 §4.5–5、§7、§10.4–10.7](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)。 | 舊 Task 六項判準不變成 Memory 保存門檻；不要求每個小節是一個 Duty／Task，不把未談內容填成職位應有工作。 |

**OPKS 研究的取用界線：**[OPKS 設計研究](2026-08-01-opks-design-decisions-research.md)提供產出、可觀察行動、判斷依據、知識技能與數值來源的研究路由，適合幫助顧問追問與 Memory 辨認重要資訊。但該稿首頁已更正 K/S 掛載、員工只能否決、bogus 項目及 task-anchoring 背書等原建議；不得只複製正文較早段落。舊 `先 Task 後 OPKS`、iCAP 匯出、A／能力級別、Evidence 欄位／驗證器與呼叫策略都不是本輪授權。具體 O/P/K/S 判準若要進 prompt，須續讀該判準原料／來源，不以此裁決稿的單句當充分佐證。

**與已接 Skill 的關係：**`work-scope-interview`、`compare-work-patterns`、`outcomes-and-expertise` 已有上述部分問法／比較原則；本輪只核對，未修改。[Skill 內容位置](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/skills/)與[接線結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-context-budget-and-analysis-skills-results.md)分別保存內容與機制。B1／B2 需的是適用於其任務的簡短方法，不把對員工的整份訪談問法照貼給背景模型，也不為共用研究而新增一個模型呼叫。

**本輪官方交叉核對（2026-09-07）：**[OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)支持理解工作、能力及兩者關聯；[O*NET Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf)區分行動、對象、目的／結果、手段與情境，並明說工作陳述需要人的判斷。後者是較早的方法文件，不冒稱最新 LLM 技術，亦不直接規定 Memory 的保存格式。[OpenAI Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml)支持清楚區分角色、指令、例子與參考 context；不替 Caliburn 決定職務分析方法。上述 A／B1／B2 取用是本產品的內容映射，不宣稱三家有相同顧問 prompt。

**狀態／下一步（2026-09-07 Owner「同意」後核對）：**已准小範圍 B1／B2 prompt 校準，仍不改 ABC、schema、原文或既有 Memory。核對現有三個 Skill 後，方法並無必須新增一套流程才能解決的衝突；這次待補強的是背景 prompt 的資訊取捨：B1 不以是否適合成為固定職責篩除案例，候選須傳遞案例補充訊號；B2 按目的／本人責任／結果／條件比較，不按案例數、工具名或文字相似度判定共同工作，並保留可找回案例的別名與真實詳記引用。這些是內容要求，不要求模型填新的分析方法／ID 欄位。

**小額試跑的判讀材料：**先用現有 prompt 看實際結果，再僅修失敗或不清楚的指令；不預先宣稱目前模型一定會漏。使用一組逐段加入的合成訪談，不另建大型評測設施：

| 加入的訪談資訊 | 要觀察的結果，不是要求固定輸出文句 |
|---|---|
| 同一接案者說 A 網站單次付款且需無障礙；B 網站月租、有權限分級；兩案均由本人實作前端，客戶驗收。 | 詳記保留各案差異；理解可歸納共同的客製前端工作，不把付款／權限條件互相套用，不因兩個案名就寫成兩份相同工作。 |
| 後段補充 A 付款失敗時要保留表單資料，另提過去曾一次幫同事搬設備。 | 候選不因已有前端工作模式就忽略 A 的新增細節；一次支援仍保存時間／本人角色脈絡，但不能推定成目前固定責任。 |
| 員工明確更正 A 是另一位同事做無障礙檢查，自己只修正檢查指出的前端問題。 | 更新 A 的本人責任／目前說法及新詳記路由；不把 B 一併更正，不把舊詳記記載誤當現況。 |
| 後續重新詢問 A 付款失敗怎麼處理、B 有什麼權限限制，以及尚未說過的驗收時限。 | 沿導覽／正文／詳記及必要原話回查出已知細節；未提供時限如實說未知。不可只以最後答案流暢或原文仍存在當作通過。 |

**本次已完成的機制基線，不是 prompt 品質成績：**隔離 worktree `921b0c09`，`test_extraction.py`、`test_extraction_feedback.py`、`test_consolidation.py`、`test_consolidation_feedback.py`、`test_analysis_skills.py` 共 **120 passed／11.41s**。HTTP 回覆為合成資料，未執行付費呼叫。初次跑到 Windows 共用 pytest 暫存目錄權限錯誤（93 passed／27 setup errors），改用新建的獨立測試暫存路徑及適當執行權限後全過；未因此改產品程式、重啟 Docker 或改資料。

**真模型 gate／新發現 MP-01（OPEN）：**Owner 隨後明確授權直接使用 `apps/api/.env` 的 key，設定路徑問題已解決，不再要求另找金鑰。該檔使用 `OPENROUTER_API_KEY`，對應現有設定的 `https://openrouter.ai/api/v1`；不把它寄往不相符的 OpenAI 主機。兩次小型端點探針：

- `GET /models` 回傳 `openai/gpt-5.6-luna` 且列有 `medium`，也另列 `luna-pro`；未生成內容。此查詢不代表付費權限、原生 compaction 或 reasoning 延續已通過。
- 依已安裝 OpenAI SDK 3.8.0 的 `responses.input_tokens.count` 真實路徑，送 `POST /responses/input_tokens`，內容僅 `model=openai/gpt-5.6-luna` 與 `input=Compatibility check.`，**HTTP 404**。未呼叫 `/responses` 生成、未傳訪談、未輸出或保存 key。這證明本次路徑不能承接現行計數前置步驟，不擴大宣稱所有 OpenRouter 能力都不支援。

SDK 路徑來源：[OpenAI SDK 3.8.0 input_tokens.py](https://github.com/openai/openai-python/blob/v3.8.0/src/openai/resources/responses/input_tokens.py)；既有完整預算的承接與 fail-closed 邊界見[CT-01 結果 §5](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-context-budget-and-analysis-skills-results.md#5-尚未納入本段)。**MP-01 是 provider 契約缺口，不是 Memory prompt 品質失敗。**模型列表與 medium 宣告不保證 `all_turns`、opaque reasoning 或 compaction 的語意等價，這些仍未真測。

**2026-09-07 Owner 後續同意／G5：**先做有界、獨立的 Luna／medium prompt 實驗，不阻塞於 MP-01。可重用既有 B1／B2／讀取介面，但測試 client 不代表正式 API composition：不移除產品預算、不驗證原生 compaction／跨輪推理延續、不換 production provider。合成訪談、暫存 Store／Saver／SQLite metadata；最多24次模型請求、每次輸出至多4096 tokens、單請求可见 JSON 至多100KB，按本次價格預留及回報用量在 US$0.15 實驗界線停止，不冒称帳戶硬額度；無 SDK 自動重試，出錯保留結果並停下診斷。方法要求及案例判讀沿上表，不另發明評分系統。原始 prompt 先測；有具體失敗才調整，不能把框架 mock 測試當 prompt 的紅綠證據。結果另存短實驗紀錄並由 register 指路。

Owner 也授權必要時先研究再改善可讀性／解耦；不是要求一定重構。此次先核對 B1、B2、保存、回查與 client 的公開接點，若能單獨組裝驗證就不擴大重構。若後續失敗根因是來源／引用／工具可達性而非措辭，另列 finding，不用更長 prompt 掩蓋；方法矛盾或需改 ABC 責任時先回 Owner。

**MP-02 實驗結果／局部修復（2026-09-07）：**3次有限Luna／medium試跑合計27次請求、provider回報US$0.01252361，均在首個B2的既有8步上限停止，未發布Memory、未進後續補充／更正／回查。發現B2預設ls提示與精確地址接法矛盾、裸引用後中文括號被誤算地址；兩項已局部修復，184項離線回歸通過，獨立review無重要finding。不重構，不提高上限；試驗用加長B2 prompt未納入程式，B1/B2分析指令與Skills不變。完整實際輸出、來源、成本、判讀與下一gate只放[短實驗紀錄](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-memory-prompt-live-calibration.md)。**多輪prompt品質仍未驗收，MP-01仍OPEN**，不因本輪局部修復誤認產品可用。

## 2. B：一次背景整理怎麼開始與結束

> **2026-09-07 最新 B2 交付窄修：**Owner 已核准[方案 A](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-b2-delivery-official-implementation-review.md#4-三個選項與建議)；完整可見短檔可用官方 write、長檔局部 edit，最終程式驗證必做、模型預檢可選。非空正文／空導覽走既有有界修正，保留有效空 no-op／沿用導覽。機制與當輪驗證只放[窄修結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-b2-delivery-repair-results.md)，原文／詳記／引用與 ABC 不變。下列續測是修前沿革，候選內容及未答≠否定的語意品質仍未過。

> **MP-02續測（2026-09-07）：**同組材料新增2次39請求、US$0.01960073；已保存兩修可完成前兩次B2，但整組未過。提示試改出現空導覽及精確編輯超限，已還原；候選覆蓋、未答≠否定、B2完成條件仍OPEN。見[實驗 §6](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-memory-prompt-live-calibration.md#6-同組材料續測有進展但不能只靠再加提示收尾)。下一gate先討論窄修正，不用本段舊初值或新版候選直接改流程，仍不重選ABC。

這是單一訪談分段累積，不做跨員工／跨 JD consolidation。B1／B2 是有先後依賴的工作，可使用不同模型配置，不是平行兩個顧問同時問員工。

### 2.1 觸發提案（不是 OpenAI／Anthropic 共同固定數值）

> **2026-09-06 Owner 最新同意：**「主顧問段落整理訊號＋新文字量後備」及[G4 通知／結果政策](2026-09-06-memory-consolidation-request-wiring-design.md)已准隔離施工。空參數工具＋官方 artifact 先以 Task4a 實作；完整 worker／結果 Context 仍須後續接線驗收。字數門檻未定，不用 90 秒閒置觸發、不以回合數為主要判準、不依賴員工手動整理。[策略沿革](2026-09-06-memory-generation-cadence-and-continuity-review.md)不重开，不沿用舊 OR 預設。

> **應用接線Task2已驗收：**[Q019-APP-01 §5–6](2026-09-06-analysis-only-agent-application-wiring-design.md#5-失敗取消與來源不能鎖死也不能假装成功)區分安全結束與AI成功回答，現已透過runtime邊界／B1metadata實作。`e1a3cbf0`／`q019-safe-turn-closure-v1`，209項含PG全過、R01複核關閉；失敗來源仍保留必要問句及中間回答，未知結果不前推。C停止端沿真operation查既有receipt，不重新發布或回滾。細節與限制見[Task2稿](2026-09-06-analysis-only-agent-safe-turn-closure-results.md)。本段不改Memory分析方式，API／排程仍未做。

- 有新完成的訪談才 dirty；沒有新內容不跑 B。
- **觸發策略及通知接法已准，數值未定：**「主顧問判斷本段值得整理」及「新可抽取文字量後備」，不要求整個主題全分析完。不用舊 4 回合／6,000 字／idle 90 秒 OR 初值施工；安全封閉回合仍是來源可讀條件，不是數回合的排程指標。
- 每份文件只有一個 B job；新的訊息只增加下一個待處理範圍，不同時開第二個整併者。全 App 背景並行度先為 1。
- 自動整理不依賴員工操作；「整理記憶」是否作選用入口待討論，不再是必做 UI。測試可直接驅動 B，不以測試便利反推產品需要按鈕。
- 關頁不等於關伺服器。程式停止時，尚未處理範圍保留；下次啟動由最後成功游標重排，不假裝背景永遠在線。

LangGraph 負責 job 內的 durable steps；本機排程／dirty 判斷是應用接線，並非 `create_agent` 或 Store 自帶 scheduler。[Functional API／持久步驟](https://docs.langchain.com/oss/python/langgraph/use-functional-api)

**恢復定位不能只靠 dirty：**每份文件使用可由 document ID 決定的 B workflow checkpoint 路由，保存 `job_id、來源範圍、stage、B1_refs、B2_attempt、base_version、operation_id`。這是執行資料，不是第二個員工聊天室／Memory。重啟先載既有工作並對帳 receipt；B1 已保存就沿用，B2 過期就以新 attempt／staging 重新執行，不能復用舊 B2 model result。只有前 job 已發布／明確結束，才排下一個新來源範圍。這些欄位由 Runtime 寫，不交 LLM 填。

### 2.2 B1 輸入、輸出與保存

輸入包括：抽取 instructions、新完成的**員工＋顧問完整問答範圍**、必要的前文、系統提供的真實來源位置。可參考有意義的工具可見結果，但不把它冒充員工原話；不加入 API keys、system/developer instructions、opaque reasoning 或 debug 噪音。

太長則依完整問答邊界切多個有界視窗，必要的前文可以重疊。系統記錄哪段是新內容、哪段只提供脈絡，直到新範圍全部被處理；**不能照 Sandbox 預設只留頭尾，讓中段永遠沒有抽取機會。** 每個視窗仍非固定長度保證語意自足；不清楚的指涉保留未解，不猜。

B1 以原生 structured output 回傳三個簡單字串：`rollout_summary`、`raw_memory`、`rollout_slug`。內容是敘述，不要求套 Task／OPKS，沒有 UUID、版本、時間、逐字 offset、skill_ids。沒有值得新增的資訊可讓候選為空；仍明確記錄該視窗已處理，而非把模型錯誤當 no-op。[原生 structured output](https://docs.langchain.com/oss/python/langchain/structured-output)

系統保存產物後才提供真實檔案位置；header 加入本次來源範圍與可回讀引用。抽取結果可以直接從記憶體交 B2，不為了「保存」再多呼叫一次模型。若保存失敗，重試保存已取得結果；若模型結果沒有耐久保存，恢復可能需要重跑該步，不能聲稱外部 API 恰好只執行一次。

### 2.3 B2：整併是一個可補讀的 Agent run

給 B2：新候選／真實詳記地址、基準版正文與導覽的位置、已處理游標、目前有哪些新產物，以及整理 instructions。既有正文很小可直接讀全；變大後用官方搜尋／讀檔按需讀，但不能只靠導覽覆寫未讀正文。

B2 可搜尋與打開相關詳記，釐清候選是否只是另一案例、是否新增條件、是否真的推翻舊說法。採 staging backend 讀寫，最後維護正文與導覽。候選未必都進正文；有些細節在詳記即可。

沿用既有研究的 B2 邊界：主要補查**詳記**，不另開一條任意 raw 調查 Agent。若詳記不足，不把缺資料填成事實，保留不確定與詳記引用，讓 A 需要時回原文／向員工釐清。來源完整性缺口則重新抽取受影響視窗，而不是整併猜測。[B 與 A 讀取差別](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#4-背景-b-的補查不同不能把-a-原封套過去)

整併結束後先驗檔案格式、可讀性、引用存在及大小；這些**不能驗證語意真實、全部案例已涵蓋**。成功發布後才推進處理游標。若沒有語意變更，仍需耐久記錄該來源已處理；不要每次又抽同段。

B2 初值最多 8 model steps／12 次工具；整個 job 過大便分下一批，不擴成無限 run。兩階段不等於固定兩個 API requests，也不保證第二階段只用一次 LLM。

## 3. A 如何按需找回，而不是每次讀到底

1. run 開始取得小型導覽。模型判斷是否與本輪相關。
2. 相關才對正文使用 `grep` 等官方文字搜尋，關鍵詞可含工作主題、案例別名、原有名稱與條件；命中後用 `read_file` 讀完整有界小節。
3. 已足夠就回答／分析。需要案例脈絡才沿小節中**真實詳記路徑**讀該詳記。
4. 詳記不足、需核實原句或指涉時，沿 header／內容引用呼叫原文 reader，讀員工與當時顧問問答；不只取脫離問題的「是／不是」。
5. 沒命中時可改搜尋詞、看目錄及其他候選主題；仍不足才有界查來源或詢問。不得把「搜尋不到」當「沒有這件工作」。

本版沿原廠已公開的 progressive disclosure 形狀，**不是每輪固定四層全走**，也不是 A 必讀 raw_memory。詳記不另建向量副本；metadata 與源內容分工。[OpenAI 官方 read flow](https://openai.github.io/openai-agents-python/sandbox/memory/#read-memory)、[Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

### 引用怎麼做，誰填

- 系統在來源讀取結果提供可原樣帶回的 citation／location；例如顯示「此段原始問答」的受控引用，而不是讓模型算中文 start/end。
- B1 整段詳記 header 的來源範圍由 Runtime 加入。正文引用詳記時，模型只選已有的地址，貼在相關主題旁；可以另寫為什麼適用，不抄完整訪談。
- 同輪 C 還沒有詳記時，可直接引用已保存的本輪原始問答。後續 B 產生詳記後可補成更好讀的路由，但不刪掉原文可回查性。
- 來源 identity／頁面游標／scope 由 runtime 管；LLM 不可發明新 identity。`read_file` 的 offset／limit 是一般分頁參數，不是用來生成逐字證據的精確字元驗證。
- 過期詳記仍是「當時談過什麼」；最新工作理解若已更正，不能因讀到舊詳記就當作恢復舊結論。

只驗證已引用的位置是否真實存在、屬本文件；**不要求每個 Memory 變動都附一條新員工原話才准寫**。抽象、去重、整理導覽本來可以根據既有已引用知識完成。機器 lineage 與語意依據不可混為一談。

## 4. 完整來源怎麼保留與讀取

直接使用 canonical checkpoint 的 messages，不多存 `employee-source-events` 文字副本。來源引用包含 Runtime 可解析的 document／thread／checkpoint／message 範圍；模型看到受控引用，不能跨文件拼查。確切欄位封裝不是 OpenAI 標準，而是選定框架的路由接點。

優先定位已完成 checkpoint；`get_state/aget_state` 是讀 snapshot，不是 replay 模型；要讀舊 checkpoint 時使用精確 config。`get_state_history` 不等於搜尋聊天文字，更不是消息分頁 API。不存在的 checkpoint 可能回空 state，reader 必須區分「真的沒有內容」與「來源不存在」。[完整底層 trace／來源契約](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#7-原文回查契約來源定位與有界讀取)

回傳是有界且可續讀的真實問答；大段不截尾後冒充完整。Raw 的前後脈絡按實際消息序列取，不能讓 LLM 只用最近十則的猜法補出引用。v1 不清理被引用 checkpoint；模型 Context 壓縮與資料庫來源保留是兩件事。

## 5. C：即时修補，並非每輪重做 B

當 A 讀到明確過時內容，或員工明確更正，A 可以先讀目前相關小節，再用一次局部 edits 提議修改。歧義則先問員工，不用 deterministic verifier 判定人的工作語意。

Tool 的模型輸入只包括既有檔案位置／old_text／new_text；scope、基準版、operation ID 由 runtime 保管。系統在新 staging 中用官方 backend edit 規則套用；找不到 old_text／命中多次／路徑不存在就回精確錯誤，不能 fuzzy 改掉別段。

需要時同一次 edits 更新正文及導覽；純正文細節更正且導覽仍準確，可以沿用導覽。兩個產物由同一 head 發布，不以各自寫入先後讓讀者看到半套新內容。C 不負責把所有訪談重新抽取成詳記，後續 B 仍處理新增來源。

**C 成功回覆**：已生效的新版本及修改後相關內容。**C 失敗回覆**：清楚錯在哪、是否可重試、下一步讀哪裡；不讓 A 當成已記住。框架檔案工具是執行基礎，批次 staging／發布是本案擴充，不宣稱 native liveUpdate 已提供此交易。[Backend 公開接點](https://docs.langchain.com/oss/python/deepagents/backends)

## 6. 背景與即時修補可以並行，但發布不能互相覆蓋

### 推薦機制：不可變產物＋資料庫版本檢查

1. B 或 C 讀取目前 `head` 與版本，於自己的 staging 處理；不持有資料庫交易等待 LLM。
2. 完整結果保存成新版本 immutable Store artifacts，讀回確認需要的檔案與引用存在；尚未發布不對 A 的正常 Memory 路徑可見。
3. 用**短 PostgreSQL transaction**同時更新 `document_memory_head` 及寫入 unique operation ID 的 publication receipt。先檢查 `loaded.version == expected_base_version`，才修改該 ORM instance；再由 SQLAlchemy 官方 `version_id_col`／ORM flush 防範比較後的競爭。版本欄位 `NOT NULL`；禁止繞過 mapper 的 bulk／Core 更新。提交前比對的是生成內容時的基準版本，不是在最後一刻換成最新版本後硬寫。即使正文 no-op，推進來源游標也須觸發版本受控的 UPDATE，不能因 refs 沒變而跳過 CAS。
4. 只有 head 成功更新才算發布。A 讀一次 head 後綁定該 immutable 版本，所以正文、導覽及引用彼此一致；如 C 成功或 stale，依下述受控刷新一起切換，不留下舊版 reader。
5. 版本衝突時不覆蓋。B 保留 B1 產物，只重做 B2；它必須讀新正文及 C 更正的來源，再重新判斷，不只是機械替換版本號。C 回 `stale`，最多重讀重試一次；仍失敗就如實告知，B 的 dirty 訪談未消失。

SQLAlchemy 的版本計數是成熟 ORM concurrency 能力，不是框架自動理解 Memory 語意；PostgreSQL transaction 負責提交順序。整個「Store immutable artifacts＋小 head／receipt」組合是本案 mapping，不冒稱 OpenAI 內部採同一 schema。[SQLAlchemy versioning](https://docs.sqlalchemy.org/en/20/orm/versioning.html)、[PostgreSQL isolation](https://www.postgresql.org/docs/current/transaction-iso.html)

### A 的受控刷新與 B 的更正來源

- C 成功／stale 的 ToolMessage 明確提供當前版本、小型導覽與需要重讀的位置；同一框架 state update 更新 `memory_read_head`，下一次 read tool 與 C base 都使用此版本。初始導覽留在原 prefix，工具結果說明它已被哪版取代，不偷偷修改 system history。[工具透過 Command 更新 state](https://docs.langchain.com/oss/python/langchain/tools)
- A v1 不平行呼叫工具，避免同批尚未完成的舊版讀取與切版交錯；刷新後若又有 B 发布，下一次 C 仍走正常 expected-base 檢查。工具結果不能只是寫「請重讀」卻把 reader 永遠鎖在舊版。
- B2 新 attempt 讀取新 head 及中間 C publication 的受控來源 references。C 尚未有詳記時，Runtime 只將這些更正所對應的有界原始問答片段加入 B2 input；保留 role 與來源標示。這不是給 B2 任意 raw 搜尋，也不是讓它只看版本號就猜為什麼改。過長片段保留不確定，不自動覆蓋新內容。

### 斷線與重試

- 提交結果不確定時，以新的 DB Session 向 primary 查 receipt／重試；暫時查不到不代表原交易已失敗。沿用同 operation ID、expected base 及已封存內容；receipt 與 head 在同一交易，unique constraint 防止成功效果被做兩遍。遇到 unique conflict／StaleDataError，先 rollback，再查是否第一次已成功，不能吞掉錯誤後照樣提交 head。receipt 留存 document、operation ID、內容摘要指紋、前後版本、artifact references 及 B 來源處理範圍；可補回缺失的執行 checkpoint 結果，這些不是 LLM 欄位。
- 同 operation ID 不准配另一份內容；如果重新分析改了內容，產生新 operation ID，但先確認舊 operation 是否已提交，避免把同一件事重做。
- 後來版本成功後，舊 receipt 仍可查；不能只在 head 放最後一次 ID，否則舊請求重試會看不到自己曾成功。
- 保存產物後、發布前崩潰，只留下未被 head 引用的版本，不影響目前 Memory。**Store 自己不保證 immutable**：Runtime 必須封版、撤銷 staging 寫入路徑；發布前確認 durable writes，結果不明時讀回核對內容指紋，禁止模型／旁路改 published namespace。v1 不急著做 GC／TTL；不刪引用或未決提交仍可能需要的資料。
- 不用單一 `asyncio.Lock` 宣稱跨重啟安全，也不以程序內 lock 取代 DB 版本檢查。背景排程先單 process 簡化營運，但正確性在資料庫。

這不需要 Redis 鎖／CRDT／多 Agent 共識平台。新增的是一個小 publication seam；比單純 last-write-wins 多一點碼，換取不回寫舊理解、可辨識失敗與重啟後不重複套用。

## 7. 「全部 Memory 可盤點」在這版是什麼

固定一個 published head，列出它包含的所有正文內容與必要詳記引用；正文很長就有界分頁直到 EOF。不能用 semantic top-k 宣稱已看全部，亦不能在翻頁期間切換到另一版本。

此版提供並驗證完整 enumeration 的底層能力，但**不做 JD 全面檢查器、不開每回合全量掃描**。後續 JD 功能才決定何時使用。所有有效 Memory 都可列舉，不代表模型的涵蓋／重複判斷一定正確；尚未整理的 raw 範圍也不能冒充已進 Memory。

最小驗收：重複案例不讓正文機械複製；不同案例特有細節可沿詳記／原文找回；明確更正能修正現況且保留歷史；B/C 並行不互蓋；compaction 後原文仍可回查；跨文件查不到對方內容。具體 pass／fail 在[審核稿](2026-09-06-analysis-only-agent-design-review.md)。
