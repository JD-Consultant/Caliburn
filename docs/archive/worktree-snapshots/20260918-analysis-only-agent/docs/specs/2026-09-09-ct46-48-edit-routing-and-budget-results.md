# CT46–48：記憶編輯方式、引用保留與呼叫額度

2026-09-09 · LLM-Q019 · 局部優化；**長訪談G8仍OPEN**。

入口：[CT45長訪談失敗](2026-09-09-ct45-fixed-long-interview-results.md)；計畫：[CT46](../plans/2026-09-09-ct46-b2-effort-replay.md)、[CT47](../plans/2026-09-09-ct47-edit-routing-candidate.md)、[CT48](../plans/2026-09-09-ct48-citation-preservation-replay.md)。只用合成員工資料，不改production/JD，不改原CT45 PostgreSQL。

## 問題與官方核對

不是「框架沒有重試」。實際工具錯誤已送回模型，模型有重新讀取、修改；但長patch包含大量原文和引用，抄錯、逆序修改及反覆檢查耗盡額度。CT46只改為xhigh仍失敗，不能以更高effort代替診斷。

- **官方SDK事實**：已完整讀取安裝版OpenAI Agents SDK 0.22.0的`agents/apply_diff.py`。每個hunk從上個匹配結束往後尋找；同diff不能先改檔尾再回檔頭。CT46 #2是原文位置10→16–17→13→21，不是UUID錯；#6／8才另有UUID錯。matcher不應把不同ID視為相同。[既有SDK研究與來源](2026-09-07-official-memory-patch-trial-results.md)、[官方patch harness](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness)。
- **提示方法**：以實際失敗trace校準工具選擇與來源保留；短且完整可見的多處變更可用既有write_file，局部patch提供必要真實context並按原文順序。不是再造編輯器或模糊matcher。[OpenAI GPT-5.6提示](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)、[Anthropic提示](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)。各廠支持明確工具指引，不代表這段中文prompt或某個精確上限是共同標準。
- **額度機制**：沿LangChain `ModelCallLimitMiddleware`／`ToolCallLimitMiddleware`，超限仍error、不發布、不用resume重置計數。官方支持可配置上限，未規定12或16。提高上限是本案測試後的可逆取捨，不是每輪固定多花。[官方模型／工具上限](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)。

## 實際對照，不混成一次成功

| 實驗 | 唯一主要改變 | 結果 | 真實請求／usage估費 |
|---|---|---|---|
| CT46 | CT45第8輪既有B1＋寫前基準，B2 high→xhigh，其餘原12／12 | 12步後未final，不發布 | 12／US$0.02371122 |
| CT47 phase0 | 回high，局部編輯候選提示，12／12 | 列表前綴不匹配一次；修好後第12步仍validate，無final，不發布 | 12／US$0.01652317 |
| CT47 phase1 | 同candidate/high及相同寫前基準，獨立複本16模型／15工具 | 7模型／6工具完成，未見工具錯誤；本批升級內容及先前子句保留 | 7／US$0.01083805 |
| CT48 | 同candidate/high/16／15，改驗第7輪原始引用流失情境 | 11模型／10工具完成，舊引用留下、新交付依據加入；仍有下列Minor | 11／US$0.01899292 |

CT46–48帳本全部closed；CT47總19次、US$0.02736122，24→32次擴充event已留、US$0.15不變。CT48使用11／24次、US$0.01899292／0.15。原失敗與staging均不冒充已發布；獨立複本revision1→2不等於原PGrevision7已更新。含CT45本段合计112次、usage估US$0.17919779，非帳單。

**重要限制：** CT47成功只用了7步，本來低於12；不能因設定16就宣稱提高上限造成成功，也不能由兩次樣本推算成功率。16／15只提供修訂及final的空間，仍可能失敗。新候選不刪原來案例區分、不確定、責任、頻率、舊細節保留等已核准規則。

## 內容與引用review

主代理與獨立reviewer均核對CT47 phase1實際B1 `NEW_DETAILS`、寫前／寫後正文及guide：已回答的升級未知移除，新升級步驟／限制／真正未回答事項有依據，未見新增Important舊子句流失。

但原CT45-Q02**仍繼承**：維護／估算段落及guide仍指到只支持交付的新詳記，真正`cc78445…`來源路由未恢復。原始資料還在，不是實體刪除，然而不能稱回查正確。CT48回到錯誤發生前的revision6，驗相同候選是否保留仍有用的舊引用；不手工修原資料後假裝產品修好。

CT48主代理與獨立reviewer已核對完整before／after、兩份相關詳記：既有維護／估算、API不明先問、責任與頻率限制未見重要刪漏，兩個來源地址均保留；相同候選在這個情境避免了舊來源被替代。不表示已修復CT45原資料、全部引用語意或所有案例：

- **CT48-R01／Minor OPEN**：舊`cc78445…`的標籤被擴稱包含交付／交接；新`4f9e69…`才是該部分依據。兩址都在，但名稱仍過寬。
- **CT48-R02／Minor OPEN**：青禾首次交付資訊放在雲岸段末，明說青禾、非事實混同，但組織不理想。
- **CT48-R03／test CLOSED**：review指出只斷言泛称limit無法區分模型／工具上限；已改為具體`ToolCallLimitExceededError`、16／15計數，單測通過。

## 局部採用與驗證

採用與CT47／48全等的B2編輯候選及共享patch操作指引；B2預設16模型／15工具，A維持12／11。模型、Memory分層、prompt其他品質規則、tools/schema、matcher、保存／發布／錯誤／resume機制不變；不增加validator、Agent或重試loop。C也收到同一patch描述，不代表C語意修補已重做真測。

這是Owner已委任的可逆局部優化。預設effort仍A/B2 medium、B1 high、預設輸出4096；本次高推理8192實驗不得冒稱預設品質通過。下一次固定版驗收須明确選定並記錄effort／輸出額度，不能換設定卻不留紀錄。

TDD：新增16步含final及超限恢復測試，原12上限時2 fail／1 pass，改後3 pass；補精確工具錯誤斷言後1 pass。第一次全回歸遇Windows沙箱tmp_path權限錯誤，未修改權限或刪目錄；改用新隔離目錄及核准執行後558 pass／2 fail／41 skip，兩個失敗是共享tool描述與已審核CT25固定wire fixture的差異。保留CT25原證據，只新增CT48 description delta，其他schema／context／tools仍逐項比對。

**最終驗證：**全套560 pass／41 skip（50.20秒），另真PG41 pass（30.67秒）；skip已由專用`q019_agent_test`驗證補足，未呼叫付費模型。真PG覆蓋保存、跨client恢復、失敗不發布及並行出版等原有測試；不是601個真模型語意案例。僅剩既有Starlette/AnyIO deprecation warning。[驗證紀錄](evidence/2026-09-09-ct48-verification.json)。

## 機器證據與回看路由

- [CT46全請求、工具回饋、before／after及腳本](evidence/2026-09-09-ct46-edit-replay.json)；[可讀正文](evidence/2026-09-09-ct46-edit-replay.md)。
- [CT47兩phase與候選全文](evidence/2026-09-09-ct47-edit-replay.json)；[可讀正文](evidence/2026-09-09-ct47-edit-replay.md)。phase1不需重新產B1、原PG唯讀，實際請求與原始內容可追溯。
- [CT48引用保留replay完整證據](evidence/2026-09-09-ct48-edit-replay.json)；[可讀正文](evidence/2026-09-09-ct48-edit-replay.md)。helper從既有第7輪artifact重建已完成B1 handoff；候選／詳記全文與Store逐一相等，不是mock模型抽取結果。
- CT47 archive的`len<=24`封存檢查是helper舊保守值；實際19符合，帳本32上限及event保留。通用authorization舊字句「no prompt changes」不代表CT47沒改提示；真候選完整在phase欄位及計畫中，產品src於這三phase未改。

下一gate：回歸與本地保存點完成後，以新固定版完整訪談、撤銷／補充及空近期context回查，關注R01／R02及來源支持範圍；不再重跑CT46–48或重開Memory分層。G8仍OPEN，不拿本次單批測試代替。
