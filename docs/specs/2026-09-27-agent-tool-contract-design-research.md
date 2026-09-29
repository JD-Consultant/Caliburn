# Agent 工具契約：跨廠研究與共同規範候選

- 查閱日期：2026-09-27；2026-09-28 補核模型參考資料按需重讀、引用更新與回傳風格；2026-09-29 重新核對本輪表列官方契約並依已定語意收斂工具文件，未做 wire 驗收。
- 狀態：**已定產品效果＋依授權選定的工程設計／未實作驗證**。§6.1 的參考資料按需重讀效果已由 Owner 確認；具體分支、最小結果及錯誤沿各責任文件，不代表 provider／保存接線已通過或授權 production 施工。明標歷史的研究比較不作施工依據。
- 決策者：Product Owner；研究與維護：工程協作者。入口：[全產品目標導覽](../target-architecture-map.md)。
- 範圍：A／B1／B2 及後續 Agent 的 model-facing 工具契約；不是統一全部業務操作、儲存、錯誤 JSON 或建造通用工具框架。
- 本輪問題：如何讓模型選對能力、填對意圖、讀懂實際效果，出錯後由正確責任者處理，而不重複 Domain／Runtime 的責任？
- 已定邊界：Memory 分責、候選與完整發布、title 唯一範圍及 V4A 正文編輯依[產品概念](../product-concept.md)；執行／恢復機制仍由[共用執行設計](2026-09-27-shared-agent-execution-and-state-design.md)承接。
- 不決定：全部工具名稱及數量、來源代號、最終 wire schema、retry 常數、保存位置、tool search 採用或新增框架。§2 的命名方向與五個參數用語已獲 Owner 同意，不代表完整更新工具已採納。

**2026-09-29 文件收斂界線：**Memory 名稱重用、候選按身分維持關係、A 的 Turn 固定發布版及 JD 明確來源核對均是已定效果；下文與各工具責任文件據此補齊可執行的語意。模型定位欄位一致使用 `target_title`，不另設 `title_target` 同義參數。工程表示供後續生成與驗證，不宣稱 provider 已接受、保存已接通或產品已驗收；明標歷史的比較不作新工具契約。

### 本輪工程選擇與官方依據（2026-09-29）

Owner 授權未影響產品效果的工程部分自行研究收斂。本輪重新取得下列官方正文，將尚未選定的表示收斂為**工程設計／未實作驗證**；不是新增產品行為或聲稱各家採同一契約。

| 當前第一手契約 | 本案採用的工程選擇 | 適用界線 |
|---|---|---|
| [OpenAI function results](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)允許文字、JSON、錯誤碼及簡短成功表示 | Memory Create／Delete／unchanged 回最小 status；Update 保留實際 title／description 與實際 changes，不附 stage；JD 沿自己的定位及短結果契約。 | 原 call 配對及可靠原結果仍須保存；短回傳不替代已成立效果。 |
| [OpenAI strict](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)及[支援子集](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)允許 nested anyOf，要求 object 屬性 required 且禁止額外屬性 | 採固定 object 根、有限分支及明確省略／空集合語意；從正式型別生成 schema，不手抄生成檔。 | 不以 required 把「不修改」改成 null；真正 SDK／provider 序列化仍需驗證。 |
| [Anthropic 工具工程](https://www.anthropic.com/engineering/writing-tools-for-agents)要求有用且節制的結果、可行動的錯誤及任務評測 | 回傳新觀察及必要定位，已知輸入不全量重抄；錯誤說原因及合法下一步。 | 格式不是跨模型最優保證；不新增 response_format 或已讀 proof。 |
| [Google AIP-193](https://google.aip.dev/193#permission-denied)區分權限與不存在，要求先查權限；錯誤應簡短且可處理 | scope／權限先於目標與來源細節；無效查詢回錯誤，不偽裝空集合、零差異或來源刪除。 | 借鑑分類，不導入 google.rpc／HTTP wire；沿原業務 owner 驗證。 |
| [JSON:API 關係更新](https://jsonapi.org/format/#crud-updating-relationships)分開成員增刪、集合替換及原物件刪除 | Memory 未列引用則保留，add／remove 只改關係；同身分重複 add 為無變更。 | 本案以 title 選取，remove 必須命中目標已有關係；不照搬穩定 ID API 對不存在關係的成功回應，以免掩蓋名稱重用後選錯成員。 |

各工具文件負責具體分支、結果及反例；以下歷史研究不再讓已收斂的工程選擇退回「等 Owner 逐欄討論」。尚待實作的是生成 schema、保存接線、容量數值及有效性證據。

## 1. 結論與證據強度

**2026-09-29 已確認的跨工具設計目的：**工具的名稱、description、模型參數及回傳都屬於[App 自主管理的上下文工程](../product-concept.md#技術核心app-自主管理的上下文工程目標已確認未實作)。角色只取得所需能力，模型不重填 App 已知資料，結果以支持下一步判斷的最小充分內容呈現；精簡不能省掉真實效果、必要定位、資料完整性或合法錯誤處置。這是設計目標，不將下方所有候選 schema 一併升格。

優化發生在**工具契約與新結果形成時**，不是事後把已交給模型的原生 call／output 改寫成較短摘要。框架不得另做未知裁切、重包角色或自動摘要；既有歷史的 compact／回退依共用執行契約，不在工具層再造生命週期。效果評估同看理解與操作正確性、往返／錯誤、token／耗時，不只比較字元數。

**建議採「按業務任務設計、權限受限、型別明確的工具＋App 注入執行資訊＋真實且可行動的結果」。**共用的是設計審查方式與必要契約，不是讓 Memory、JD 共用一個任意 CRUD 工具。

可以稱為公開共同原則的是：清楚的名稱與說明、模型只承擔需要推論的選擇、程式檢查與執行、回傳有用結果、依任務效果評估。**沒有證據顯示所有廠商共用一套命名順序、固定工具數、錯誤 envelope 或最佳 `changes[]` 格式。**本稿的具體規範是 Caliburn mapping，須與官方事實分開。

| 官方來源 | 直接支持的重點 | 不可外推 |
|---|---|---|
| [OpenAI function 設計](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions) | 名稱、參數及輸出含意清楚；程式已知值不交模型重填；固定相連流程可合併；初始工具集宜精簡並實測。 | 不是每欄一工具，也不是所有相關功能一律合併；少於 20 是軟性建議。 |
| [Anthropic 工具定義](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools) | 說明何時用、限制及參數；有意義的 namespace；可將相關操作整合。 | `action` 合併不是所有任務的唯一最佳形狀，也不取代執行授權。 |
| [Anthropic 工具工程研究](https://www.anthropic.com/engineering/writing-tools-for-agents) | 工具須配合 Agent 任務而非機械包 API；回傳重要資訊；以任務結果、錯誤、呼叫及耗用評估。 | 名稱前綴／後綴、JSON／Markdown 等格式的效果仍因模型與任務而異。 |
| [Google Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling#best-practices) | 具體名稱／description、明確型別、執行前驗證、錯誤處理與限制 active tools。 | 文件的 10–20 工具建議不是 API 通用硬上限，也不替本產品選定數目。 |
| [Microsoft function tools](https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools) | runtime-only context 可不出現在模型 schema；例外診斷與對模型的結果可分開；共享可變狀態的工具要控制並行。 | 此處借鑑邊界，不採用 Microsoft framework，也不把其預設重試／並行等同 LangGraph 行為。 |
| [MCP 2026-07-28 tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#error-handling) | 協定錯誤與具可行動回饋的工具執行錯誤分開；工具 metadata 不是可信授權本身。 | 本產品使用 direct Responses，不因此導入 MCP 或照抄 `isError` wire。 |
| [AWS 安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | 以原操作身分與冪等契約避免重複效果，重試可承接語意相同的原結果。 | 不能由 timeout 或相同參數就判定未提交／同一次意圖；不新增第二套 receipt。 |

### 官方建議有差異的地方

- **拆分粒度：**OpenAI 強調固定順序可合併，Anthropic 更明確建議整合相關 action。共同目的為減少選錯及不必要往返，並非共同規定所有 create／update／delete 合成一個工具。
- **範例：**Anthropic 建議複雜輸入可附範例；OpenAI 同頁提醒範例可能不利於 reasoning models。候選政策是先寫清語意，只有格式敏感或反覆誤用時加少量例子並驗效果，不強制每個工具塞大量範例。
- **錯誤 wire：**[OpenAI 結果格式](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)允許字串中的 JSON／文字等；[Claude](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)及 MCP 各有自己的 error 標記。共同語意可一致，但 wire 不必相同；不虛構 OpenAI 通用 `is_error` 頂層欄位。

## 2. 命名與 description 候選規範

**2026-09-27 命名續議／歷史方向，工具詞序已由下段取代：**當時採「業務對象＋動作」；`target_title`、`changes`、`field`、`value`、`diff` 的含意仍保留，分別表示目前目標標題、本次修改集合、被改欄位、短欄位完整新值、正文 V4A diff。這不一併採納全部工具名、結果代碼、完整 schema 或保存接線。內容欄位 `title`／`description`／`body` 沿 [009](../product-concept.md#工作情境與工作理解的三個內容欄位目標未實作)，不被這五個操作參數取代；更新表示的對應見[單物件契約 §3](2026-09-27-memory-object-update-tool-contract.md#3-模型輸入一個目標與有限-changes)。

**名稱表示動作與業務對象，參數表示它實際承載的值。**2026-09-28 Owner 後續要求模型工具採動賓短語；目標命名方向改為 `動作_資源` snake_case，例如 `read_work_situation`／`update_work_situation`。本稿較早的 `work_situation_read`／`work_situation_update` 是當時的候選示例，不能再作為最新命名規範；Memory／JD 本輪工程名稱已沿各 owner 文件選定，工具註冊尚未驗證。不要把模糊的 `manage`、`process`、`data` 當作足夠說明，也不只用 A／B1／B2 內部代號命名業務能力。

- `title` 是內容標題，`target_title` 是定位既有物件的修改前標題；不是 `title_id`，不冒稱固定 ID。改名仍是同一物件，App 先綁定目標再處理修改。
- 若參數實際傳的是 App 提供的 ref／ID，就明確叫 ref／ID；**不禁止模型選取已提供的識別值，禁止它猜造 App 已知的執行身分**。來源短代碼方案不在本題採納。
- `body` 是 Markdown 正文，`description` 是導覽描述；不拿 `context` 同時表示正文與 Agent 的完整上下文。
- 同一概念跨工具保持名稱與語意一致；不為表面一致而把不同資料硬改成同一格式。

**2026-09-28 前綴續議補正：**較早的資源前綴工具名（如 `work_situation_create`）已被上方「動賓短語」方向取代；資源名稱仍出現在動詞後，例如 `create_work_situation`。已確定單一資源的內容參數仍用 `title`／`description`／`body`，不重複成 `work_situation_title`。定位既有物件仍用 `target_title`，建立新物件用 `title`。跨資源的引用欄位則保留 `interview_references`／`work_situation_references`，因其前綴確實區分引用對象。這是命名方向，不宣稱已採納全部工具名稱。

### 2.1 本輪風格審核與收斂候選

**2026-09-29：已確認命名與效果沿唯一責任文件；下表工程風格已收斂，不代表整套 schema 已生成或驗收。**統一詞彙與語意，不造所有工具都必填的大型 envelope。

| 範圍 | 建議統一方式 | 保留的差異 |
|---|---|---|
| 工具名稱 | 動作＋業務對象，snake_case；例如 `read_work_situation`／`update_work_situation`。導覽／差異仍須有清楚的讀取動詞與對象。 | 只是命名方向，不據此新增工具；Memory 內容、JD 關聯式項目與執行控制分開。 |
| 目標與內容 | 可按需讀取的 map 項目與其下一層可讀引用項目用 `target_title`／`description`；read 工具輸入沿用 `target_title`；被讀物件內容及結果用 `title`／`description`／`body`。 | 不在同一項目重複 `title`／`target_title` 或另加 `can_read`；訪談用正式訪談序號，不叫 title 或籠統 id；title 到 ID 的映射仍由 App 處理。 |
| 引用 | 用 `interview_references`／`work_situation_references` 表明引用對象；不混用 sources／refs 等同義名稱。 | 更新的名稱／按需表示已確認，見更新契約 §10；讀取工程表示沿用同名欄位，值依 read 契約包含正式訪談序號或可讀目標／描述，不強迫與增刪輸入同形。 |
| 修改意圖與成立效果 | 輸入 `changes`；輸出 `applied_changes`。引用輸入 `add`／`remove`，實際效果 `added`／`removed`。 | V4A 是 body 更新輸入；結果需回實際差異，不能回送請求冒充效果。讀取沒有修改，不套 applied_changes。 |
| 狀態與資格 | `status` 只說本次 call 的結果；candidate／published 是資料資格，不是每份模型結果必填的 `stage`。 | Create 正常成功只回 created，Read 不回 stage；候選範圍由工具說明及 App 綁定表達。Update／Delete 沿各自文件的工程表示，結果描述已成立的候選效果，不把資格或 call 結果當整個 Agent 工作進度。 |
| 錯誤 | 穩定的 `code`、可理解的 `message`、必要定位及合法 `next_action`，按需要提供。 | 結果不明先由 App 核對，不能僅回 retryable=true 叫模型重送；不洩露禁止層、stack trace 或連線資訊。Memory JSON／JD 短文字沿 §7，序列化待驗。 |
| 省略與空值 | 沒有修改意圖就不填；工具輸出不為對齊外觀填一堆 null／空陣列。 | 完整讀取結果的空集合可能真的是「沒有任何項目」，不可一律省略而混成未提供；省略、空集合、未讀與節錄由各工具說清楚。 |

參數說明依同一檢查順序撰寫：**用途 → 允許範圍 → 如何取得／填寫 → 成功代表什麼 → 失敗及下一步**。只寫本工具需要的資訊；共用分析指南、權限與恢復機制不複製進每個 description。已知 scope／job／版本／操作身分不交模型填；來源選擇仍是模型意圖，不能全交 App 猜。

**審核依據與限制：**2026-09-28 再核 [OpenAI 定義函式](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)與[結果格式](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)，及 [Anthropic 工具工程](https://www.anthropic.com/engineering/writing-tools-for-agents)：明確命名、回傳後續任務需要的資訊、以 eval 判斷工具品質。具體 prefix、欄位名及上述風格是 Caliburn 選擇，不是大廠指定的唯一 JSON；不因輸入 strict 規則要求 App 輸出也強填同一組欄位。

**審核範圍：**共同工具設計、Memory map／read／update、訪談來源回讀與生命週期接縫；不是現行 production 全工具合規審計。**最新規則不設來源數量門檻**：建立可帶合法引用，更新可移除全部引用；刪除情境時 App 同次解除當前候選的理解綁定、不刪理解，B2 再分析語意影響。較早「建立必附／最後引用不可清空」已撤回。唯一規則見[建立／候選刪除](2026-09-27-memory-object-update-tool-contract.md#11-建立與候選刪除目標已確認)，例子見 [CRUD 範例](2026-09-28-memory-tools-crud-examples.md)。完整 wire 與模型效果仍待驗，不為每個參數重開一輪架構。

每個工具說明應足以讓只看到該契約的人回答：

1. 用來完成什麼、何時用、容易混淆的相鄰能力是什麼？
2. 作用在哪一層、候選或正式資料、誰有權使用？
3. 每個參數的含意、合法值、格式、單位／範圍、值從哪裡取得？
4. 成功到底代表讀到、更新候選、接受意圖，還是正式發布？
5. 失敗是否有改動、下一步可做什麼；是否可能結果仍不明？

這是檢查清單，不要求所有答案重複塞進每個模型 description。共用工作規則放 Agent 指引，欄位含意放參數 description，該工具效果與限制放 tool description；保存／恢復細節留責任文件。實際 schema 中仍要具備使用該工具不可缺少的語意，不只藏在未載入文件。

## 3. 模型參數與 App 參數

| 資料 | 建議提供者 | Caliburn 例子 |
|---|---|---|
| 需要理解工作後才能選擇的意圖 | 模型 | 選哪個情境、改成什麼標題／描述、V4A 修改、從已提供來源選哪些依據。 |
| 已由本輪／本批固定的執行範圍 | App | 職務檔案、Agent 權限、Turn／job、Memory 基準、候選、合法訪談範圍。 |
| 保存及恢復的機制資訊 | App／業務 owner | 內部物件與版本身分、原操作辨識、交易、完成／發布結果。 |
| 模型可選，但合法範圍由 App 約束的資訊 | 模型選、App 驗 | 從導覽選 target_title、按訪談序號或範圍回讀；不能藉參數跨職務檔案或讀寫禁止層。 |

**同一資料不要求模型與 App 各填一次再核對。**已 pin 本批輸入的讀取工具可以沒有模型參數；模型需要選目標或內容時才保留該選擇。不能為了消滅參數而讓 App 猜模型要編輯哪個物件。

執行前仍由原資料責任者核對授權、基準與業務約束。隱藏 schema 欄位、strict mode 或不列出某工具，都不是完整安全邊界；不能靠模型不呼叫來保護 B1／B2 的分責。

## 4. 工具應如何拆分

| 方案 | 優點／風險 | 建議 |
|---|---|---|
| 逐欄／逐 DB 操作拆工具 | 每個 schema 小，但容易多次往返、暴露內部表結構及產生半套修改。 | 不作預設。 |
| 按業務物件與任務設計，有限型別化操作 | 同一邏輯修訂可一起完成；參數和效果可清楚驗證。 | **首選候選。** |
| 全部收進 `execute(action, payload)` | 表面工具少，實際仍需理解大量操作；權限、錯誤及 schema 常變模糊。 | 不作預設，不造通用 CRUD／patch engine。 |

合併的判準：**同一目標、同一權限與候選基準、同一邏輯修訂，且應共同成功或拒絕**。拆分的判準：不同讀寫風險、不同完成／確認邊界、很少一起使用，或合併會讓模型面對不相關參數。不是按程式檔案數或資料表數拆分。

因此 Memory 同物件的 `title`／`description`／V4A `body` 放同一更新工具的 `changes[]`：沒列的欄位不變；短欄位交新值，body 交 diff；本層引用可同次增刪。**同物件多欄一次修改的效果已確認**，見更新契約 §3；完整序列化及模型效果仍待驗，不宣稱已驗證最佳解。建立及刪除保留各自清楚的入口，不在此暗中合併不同生命週期。

讀取、更新、發布也不能僅為省 call 而綁成不可分操作。模型已有正確且有效的正文時，不要求重複 read；缺少內容或基準過時才取得所需觀察。Memory 與 JD 共用規範，不共用一個編輯表示。

## 5. Schema 與驗證邊界

- 模型輸入首選明確型別、enum、固定欄位與有限 variants，不使用任意 `dict`／自由 SQL／任意 JSON path。
- [OpenAI strict](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)要求 object 的 declared properties 全列 required、`additionalProperties:false`。這是 provider wire 契約；不能因此把 Domain 的「不修改」改成 nullable 值。
- 本案 partial update 仍以「沒有該欄位的 mutation entry → 保留」表達；合法 clear 與 set 分清，必備 title／description 不因通用化而增加 clear。
- `changes[]` 各種類型的確切 strict schema 仍要核對序列化結果與 OpenAI 支援子集，不能只看 Python 型別就宣布可用。
- 格式解析處理 shape；原 Domain 處理既定範圍的標題唯一性、可改欄位、引用與完整性；Runtime／業務層處理 scope、候選基準及操作生命週期。薄轉譯不得再寫第二套相同業務 validator。
- 模型 schema 合法不代表改對物件、忠於原話或保存成功；這些分層驗收。

## 6. 成功回傳：提供下一步需要的真實觀察

**Memory 更新的結果語意已由 Owner 於 2026-09-28 確認，唯一詳細格式見[更新契約 §6](2026-09-27-memory-object-update-tool-contract.md#6-成功回傳已成立的候選效果)。**這不一併批准所有工具的完整 envelope；以下共同要求保留逐工具套用邊界。

候選共同要求：讓模型知道**哪個目標、發生何種效果、哪些必要內容或可用定位值、是否有未完成限制**；不是每個工具都套一份巨大 envelope。

- 讀取：回正文或導覽所需欄位、合法後續定位資訊；若只有部分內容，說明範圍及取得餘下內容的方法，不能靜默截斷後冒充完整。
- 更新：回本次實際更新的對象與欄位、必要的修訂片段／差異及生效階段。長文不必每次全量回傳；但 diff 定位與後續推理不可缺的資訊不能為省 token 刪掉。
- 候選寫入的工具說明明確限定「本批工作稿，不代表正式發布」，執行由 App 綁定；不要求每次模型結果都重複 `stage: candidate`。候選完整保存與正式可見仍是兩個不同保證，UI／內部回執不以模型可見 JSON 作唯一狀態來源。
- 背景要求的接受／意圖保存與背景發布不同；依已定政策，A 成功完成後才啟動涵蓋本輪的整理。工具不能提前回「Memory 已更新」。具體回傳詞與接線由原生命週期設計承接。
- 不在每次結果重印整套操作手冊，不預設所有業務都新增 diff 工具、永遠置頂的成功摘要或永久工具訊息副本。2026-09-28 Owner 已要求 B2 能按需讀 B1 的情境變更，依下節及其責任文件處理；JD 的人工／Memory 來源差異入口另由 JD 工具契約選定，不從 Memory 照搬。

JSON 適合狀態與結構資料，Markdown 適合長正文；可組合。**沒有跨模型一律最佳的格式**，不為一致而把 Markdown body 拆成大量 JSON 欄位。

**2026-09-29 JD 讀取表示補正（Owner 已確認目標／未實作）：**JD map 按需回精簡 JSON；模型輸入只填本次需要它選的參數，其餘由 App 綁定。其他讀取回傳依用途選擇：後續須用定位／關係操作時保留必要結構，偏長文閱讀且不太需要操作時可用 Markdown。這是 JD 讀取的已確認界線，不把所有 Memory map 或局部工具結果一併定成相同格式；不為切換格式新增模型參數或第二份資料 owner。詳見[顧問 JD 導覽與讀取 §3.2–3.3](2026-09-26-consultant-context-and-state-design.md#32-jd-導覽的按需定位目標已確認未實作)。

**2026-09-29 差異讀取表示補正（Owner 已確認目標／未實作）：**B2 按需閱讀 B1 情境差異，以及 A 按需閱讀 JD 來源或人工改稿差異時，模型可見的詳細比較內容採 Markdown；簡短變更概覽仍可依其定位用途保持精簡結構。Markdown 不是工具輸入 schema，也不是 Memory `body` 寫入用的 V4A 指令；須標出比較對象、改動範圍與必要定位，不把兩份完整長文無條件重貼。Memory 差異入口沿[背景工具細設](2026-09-25-b1-b2-information-gap-lifecycle.md#差異讀取的最小工程契約2026-09-29-推薦待實作驗證)，JD 入口沿其工具契約；分支及異常語意已有設計，段落排版、容量與接線待實作驗證。

**2026-09-28 模型可見輸出精簡（Owner 補正；目標／未實作）：**本題只設計供模型接續的結果，不把內部保存、診斷或業務回執的欄位全部搬進 context。App 按既定接續契約保留原 function call／arguments 及配對 output，結果優先提供**新增的觀察、已確認結果及必要修正資訊**，不一律重抄輸入。Create 依提交內容完整建立且可可靠承接時，只回 `{"status":"created"}`，不再 echo title、description、interview_references，也不回 stage；B2 建立沿相同原則。Read 不回 stage，但仍提供所請求的正文與來源資料。工具結果精簡不等於只保存這個 status，也不改變正式引用、候選保存或恢復保證。

呼叫意圖不是已成立效果：若實際結果與輸入不同，或模型須核對模糊 patch 的實際位置、未生效項目或錯誤，仍回傳所需資訊，不能以短 success 掩蓋差異。Update 的實際效果與工程表示依更新契約 §6；任何後續精簡須維持同等資訊。原生配對仍由外層 call_id 承接，不必在 JSON 內容另抄一遍。歷史能被模型看到，前提是 App 確實送入；Compaction 後不能保證原呼叫逐字仍在，需要細節時依既定按需讀取能力取得，不因此建立永久重複訊息。

**官方契約與本案取捨分開：**[OpenAI 工具接續範例](https://developers.openai.com/api/docs/guides/function-calling#handling-function-calls)將原 output items 與配對 function result 加入後續 input；[結果格式說明](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)允許沒有資料返回的操作只給成功／失敗資訊，不要求 echo arguments。具體採 `status: created`、Read 不回 stage 是本案選擇，不是官方指定的 schema。

### 6.1 起始參考資料亦可按需重讀（目標已確認／未實作）

**2026-09-29 局部補正（目標已確認／未實作）：**App 起始提供的工作情境、工作理解導覽須可按需重讀；JD 導覽**不再起始提供**，由[同一 JD 讀取入口](2026-09-26-consultant-context-and-state-design.md#32-jd-導覽的按需定位目標已確認未實作)按需取得導覽、全文或指定位置。模型不必只能依賴起始訊息或壓縮後的概略內容；需要定位、核對或補回細節時，可重新取得被允許的資料。B2 另需取得 B1 的變更資料及按需可讀的差異；其比較範圍與交接生命週期由 [B1／B2 設計](2026-09-25-b1-b2-information-gap-lifecycle.md#b1-變更資料與-b2-按需回讀目標未實作)維護。

| 使用方 | 本題要求的按需讀取能力 | 不改變的邊界 |
|---|---|---|
| A | 起始提供的工作情境、工作理解導覽可重讀；JD 導覽按需首次取得，並可讀全文／指定位置；訪談依既定共用 read 契約 | Memory 仍為本 Turn 固定的已發布基準；JD 按該輪正式／候選讀取契約反映自己的已成立修改。 |
| B1 | 工作情境導覽、自己情境層的修改；本批及歷史訪談依既定 read 契約 | 不讀理解導覽／正文／修改；不擴大本批訪談上界。 |
| B2 | 工作情境導覽、工作理解導覽、B1 的情境變更及自己理解層的修改；正文及歷史訪談按共用 read 契約深入 | 讀本批有效候選；訪談受本批固定上界及來源資格限制；不能修改情境，diff 不取代語意分析。 |

共同規則：

1. **同一資料責任，取得時機依資料而定。**起始 Memory 導覽與工具重讀使用同一業務資料及投影規則；JD 導覽只在按需讀取時從目前可見 JD／候選投影，不預載或另行維護 map，也不建立第二份可獨立修改的資料真相。這是契約要求，不預定新增 service、registry 或每種導覽各一個工具。
2. **重讀不是一律取全域最新。**Runtime 承接 Agent 權限、職務檔案、固定 Memory／本批候選及相應讀取語意；模型不重填這些版本與執行身分。B1／B2 的導覽、正文及候選來源列沿物件身分反映目前候選；A 讀本 Turn 固定發布版。JD 舊依據由 App 保留固定修訂並提供舊→本 Turn 可見新基準的差異，Agent 不透過一般 read 取舊版 Memory 正文。人與 App 的精確歷史回查仍讀原快照；新觀察不改寫既存引用，也不等於 JD 已確認對齊。
3. **新觀察追加，不改寫歷史。**工具結果保留原生回傳；不能把 context 中較早的導覽或結果原地換成新值。已具備足夠有效資訊時，不要求每 Step 重讀或每次模型請求重投影全部資料。
   2026-09-28 Owner 補正：B1／B2 對自己的工作也是如此，需要時才核對改動；不另設每次交接切換 diff 基準或模型已讀進度。具體查詢範圍由工具契約說清楚，不由模型猜，也不把讀取當成已理解／已完成。
4. **完整性與權限一致。**重讀須保留原資料所需欄位、來源及範圍；若分段回傳，須標示未完範圍及取得餘下內容的方法，不把節錄冒充完整。Memory 導覽的全體集合要求仍依原讀取契約。
5. **不是任意 context 匯出。**此能力針對 App 提供的業務參考資料，不授權讀取其他 Agent 的私人 reasoning、隱藏指令或禁止層；不將 compaction opaque items 當作一般業務查詢資料。

**依據與取捨（2026-09-28 核對）：**[Anthropic 工具工程指引](https://www.anthropic.com/engineering/writing-tools-for-agents)支持回傳對後續任務有用的資料、依需求提供精簡／詳細內容並實測工具粒度；[LangGraph State 指引](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#step-3-design-your-state)支持保存必要原始工作資料、可推得的內容按需形成。兩者不強制「每份起始導覽必有工具」或本案 diff 基準；那是本產品的明確取捨，也不表示已選定具體保存方式。

**待驗 gate：**同一讀取範圍、同一資料狀態下，起始 Memory 投影與工具重讀的業務內容一致；JD 起始訊息不含 JD 導覽，按需導覽與指定位置／全文讀取則來自同一目前可見 JD／候選；同輪 A 重讀不取得新發布 Memory；B1 重讀仍拿不到理解；候選修改後相應導覽可查回新內容；重讀不改寫舊觀察或建立新的業務效果。工具名稱、schema、分段表示與實作測試尚未完成。

## 7. 錯誤回傳與恢復責任

Anthropic 的[錯誤處理](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)要求提供具體改進方向；Microsoft 的[錯誤診斷界線](https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools#control-tool-error-details)則提醒例外文字可能洩漏敏感資料。兩者可同時滿足：**對模型提供經整理的可行動資訊，完整 stack trace／DB／連線資訊留給可信診斷通道。**

| 情況 | 模型應得知 | 恢復責任／不可做 |
|---|---|---|
| 參數錯誤、違反標題唯一性、重複 field | 哪個欄位不合法、合法方式、本次是否確定未修改 | 模型可修正意圖；不原封不動重送。 |
| patch 無匹配或多處匹配 | 哪個 hunk、原因、允許範圍內的有限候選上下文、如何補足辨識 | 重讀／補上下文；不可默選第一處或越權返回其他層資料。 |
| 操作綁定後候選基準過時、綁定目標消失 | 原操作目前不能採用，須取得哪些有效資料再判斷 | 原操作不偷偷換 ID／升級同輪 Memory 基準。新的 title 操作按當前作用域解析，名稱重用本身不是拒絕理由；不猜模型未表達的舊身分。 |
| 暫時網路／限流故障 | 有界恢復後仍需它處理的必要狀態 | 程式依安全性、成本及 retry 契約處理；已修好不逐次叫模型修參數。 |
| 保存結果不明 | 尚不能確認效果，不能宣稱未修改 | 原業務 owner 核對原操作；不以最新正文冒充原結果、不盲目建立新操作。 |
| 無權限、額度不足、容量／設定阻塞 | 不可繼續的原因與合法下一步 | 模型不能改 scope、繞權限、無限重試；交 App 的有界停止／恢復策略。 |

以下只是**錯誤回傳內容示例，不是已定統一 schema**：

```json
{
  "status": "rejected",
  "code": "ambiguous_patch_context",
  "target_title": "網站維護",
  "effect": "unchanged",
  "message": "第 2 個修改區塊有兩處合格匹配；本次標題、描述與正文均未修改。",
  "next_action": "重讀候選正文，加入可區分兩處的真實前後文後重新提交。"
}
```

`unchanged` 僅在已確定本次未寫入時成立；保存結果不明不得套用此例。候選列表若過長須有界呈現並提供繼續閱讀方式。JSON 欄位無需讓模型自己填，也不能從這個例子推導新增 status 表。

**工程設計：錯誤語意與 scope 次序。**模型可修正的拒絕回 `rejected`、穩定 `code`、簡短原因與合法下一步；Memory 採 JSON 的 `status`／`code`／`message`／`next_action`，JD 沿[其結果契約 §5](2026-09-29-jd-model-tool-contract-review.md#5-模型可見結果與失敗)的短文字表示。只有定位失敗項目需要時才加 `field`、`target_title` 或有界片段，不回內部 scope、版本或堆疊。先驗執行工作仍有效與權限，再解析允許範圍內目標；不因不存在／其他檔案而洩露對方內容。

| 工程 code | 適用情況／下一步 |
|---|---|
| `invalid_arguments` | 形狀、型別、空操作或互斥分支不合法；修正指出的參數。 |
| `scope_not_allowed` | 職務檔案、層級、引用所屬目標或執行權限不符，或訪談序號超出可讀上界；只從本工作有權使用的入口取得定位，不讓模型更改 scope。 |
| `target_not_found` | 在有權作用域內找不到目前目標或既存引用；重讀相應導覽／項目，不猜同名歷史物件。 |
| `target_stale` | 原操作綁定後基準失效；重新判斷新意圖，同一操作的重入先核對原結果。 |
| `source_kind_not_supported` | 來源型別不適用所選能力，例如將訪談引用交給 Memory source diff；回正確讀取路徑。 |
| `source_not_available` | 合法作用域內的來源／比較端點無法讀取或來源不具正式共享資格；明說無法完成，不回假差異或原文。超界另依 scope_not_allowed，不混為來源已刪除。 |

標題重名、patch 歧義等既有業務錯誤仍由其 owner 返回可辨認原因；不在此複製所有 Domain 錯誤碼。read 的空集合只代表合法且完整查得沒有成員；diff 的零差異只代表合法兩端完整比較後沒有差異。保存結果不明不是上述確定拒絕，仍先對帳，不能回 `effect: unchanged`。

**三種動作分清：**執行方重試同一操作、模型改參數形成新的意圖、使用者取消後發起新 Turn，不是同一個 retry。依 [AWS 冪等契約](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，相同參數不充分證明相同操作；App 應承接原操作辨識與結果。重試次數仍待成本／失敗類型設計，沒有統一「所有錯誤最多一次」共識。

工具回傳先供 Agent 接續，不等同全部原樣顯示於 UI。最終未恢復且影響使用者的失敗需誠實呈現；已自行修好的短暫錯誤不必污染正式訪談。

## 8. 權限、原子性與接續

- 工具只暴露該 Agent 可用能力，執行時再驗 scope／權限。B1 不提供理解讀寫；B2 可讀情境但不可修改情境。共用實作不代表共用全部權限。
- 原始訪談、Memory 正文與工具回傳中的引用內容是資料，不得因被工具讀出就升格 system／developer 指令。App 產生的效果欄位也須與引用正文分清；role 及結構只是防線，不能替代授權。原生工具結果仍按所選 API 的 call/result 配對，不改成無關聊天訊息。
- 同一物件的邏輯更新若宣告全有或全無，必須在真正保存邊界做到；模型一次送多個 calls 不自帶整批交易。
- 獨立讀取可評估並行；同一候選互相依賴的編輯不能直接平行。模型可生成多個 calls 與 App 是否允許同時執行分開。
- Step 恢復、取消候選及正式提交依既有共同責任，不在工具層新建第二套 receipt、重試計數器或發布 validator。

## 9. 套用到 Memory 更新的下一份契約

**責任入口：**模型輸入、description、流程、結果／錯誤與驗收集中於 [Memory 單物件更新契約](2026-09-27-memory-object-update-tool-contract.md)。本節不維護第二份 schema。title 改名／刪除後可重用及來源按需增刪已確認；strict wire 與實測不是因此完成。

先前「metadata 工具與 body 工具分開」只是候選，見[編輯研究 §10.7](2026-09-09-llm-app-tool-use-and-document-editing-common-practices.md#107-標題唯一性與建立基本資料更新刪除的候選契約2026-09-27)。這次建議改比較**同一更新工具內的有限 changes**，不是增加另一套重疊入口：

- 外層 `target_title` 依 Owner 暫時同意作修改前定位值；模型不提供本批、scope 或內部版本。
- `title`／`description` 提交新值；`body` 提交已選 V4A diff。每欄至多一筆，body 可含多個 hunk；未列欄位不變。
- App 先綁定單一物件及候選基準；改名不影響同次 body 的目標。檢查或任一 hunk 失敗，整個更新不保存；提交不明另依原操作對帳。
- 建立、候選刪除及來源增刪依更新契約 §10／§11。固定歷史來源依身分／修訂，不因名稱重用改指別物件；新 title 操作則解析到當前作用域內的同名物件，不追蹤模型心中未表達的舊身分。精確字串比較已由讀取契約 §4 選定；wire 及重名／Unicode 邊界仍待驗，不要求模型填版號。

這是可檢驗的設計候選，不宣稱已是 production 或模型最優 schema。

## 10. 規範如何驗收與維護

每個工具在所屬責任文件留下簡短契約：**目的／權限、模型輸入、App 綁定、成功與失敗結果、生效與恢復邊界、代表性反例**。共同原則集中本稿候選，採納後再升格；各工具不各抄一份共用規範，不一次填滿所有尚未討論的工具。

| Gate | 證明什麼 | 本輪狀態 |
|---|---|---|
| 契約靜態審查 | 不讀實作也能判斷選哪個工具、填什麼、何時正式生效；無同義衝突及越權參數。 | 官方研究已完成；具體工具契約仍待設計。 |
| 離線 schema／Domain | 最終序列化 strict 合法；未指定欄位保留；重名／歧義／重複 field 拒絕；多修改全有或全無。 | 未執行新 gate。 |
| 保存／恢復 | 同一操作重入不重複效果；候選與正式、已知失敗與 unknown、取消及發布符合原契約。 | 未執行；不由 schema PASS 推定。 |
| 有界真模型 | 同一任務下選對工具與目標、內容正確、能利用錯誤修正；比較修復次數、模型／工具呼叫、tokens、時間及費用。 | 未執行；不宣稱特定命名／合併形狀最佳。 |

代表任務先用「只改標題」「標題＋描述＋兩處正文同改」「第二處歧義拒絕」「改名後再讀」「過時目標」「同層重名拒絕／跨層與跨版本同名允許」「斷線後查原結果」。正常成功率與不該改卻被改的比率分開；不能為了減少 call 放寬歧義、權限或保存語意。多種合法工具順序可達同一結果，不用唯一 transcript 當答案。

**停止廣搜：**公開資料已足以建立審查框架；剩餘差異須由具體契約與有界測試回答。工具 search、全域命名翻新、通用 provider abstraction、新 Agent／儲存／registry、額外的固定審核 loop 均不在本輪提議施工。

**最新後續順序：**Memory 引用增刪、命名、更新回傳及建立／刪除的效果已定；[010 讀取與來源回查](2026-09-27-memory-read-and-source-navigation-contract.md)負責讀取／定位語意，[Memory 更新契約](2026-09-27-memory-object-update-tool-contract.md)負責寫入及結果，[CRUD 範例](2026-09-28-memory-tools-crud-examples.md)核對接續，[JD 工具契約](2026-09-29-jd-model-tool-contract-review.md)已承接 JD 來源與差異入口。完成這些文件的語意對齊後才規劃實作，依各自 gate 驗 wire、保存及模型效果，不重開 V4A 或關聯式 JD。先前研究僅抽查 `consultant_tools.py` 的 scope 注入與錯誤回傳，不能宣稱現有實作已符合新目標。

**交付限制：**僅官方研究、唯讀核對與文件維護；未改 production、未安裝套件、未呼叫付費模型、未執行產品測試、未 commit／push。文件差異、閱讀路由與狀態另作檢查；不將文件檢查當功能驗收。
