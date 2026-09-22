# P3-B01：Responses 原生 compaction 的最大計費上界

查閱日：2026-09-10。有限唯讀研究；**結論 Unknown，P3-B01 尚未閉合**。Luna 的長context門檻／公開費率可確認，但所讀官方契約不足以證明「一次出站 Responses request 含 inline compaction 的全部最大計費tokens」。因此不能把 context window × 最貴費率變成已證實的US$1預留策略。

只研究此一缺口；未改code／DB／設定／guard／模型／effort／8192／native compaction 12000，未讀key／env、載入Settings、執行count或任何付費請求。未重新審測法／CT全套，不影響Task5施工。自然批次仍NOT AUTHORIZED，P3-B02–04不在本輪閉合範圍。

## 1. 接點與來源範圍

先讀 `docs/specs/2026-09-10-jd-natural-trial-budget-preflight.md` P3-B01，再以 `git show 8eec072d` 讀受版控的 `experiments/analysis-agent/src/analysis_agent/provider.py`、`budget.py`、`experiments/analysis-agent/uv.lock`，沒有讀施工中的runtime檔。lock列OpenAI Python SDK3.8.0、langchain-openai1.6.0。

另唯讀已安裝官方SDK的METADATA及 `openai/types/responses/response_create_params.py`、`response_usage.py`、`compacted_response.py`、`response_compaction_item.py`、`service_tier.py`，均位於 `experiments/analysis-agent/.venv/Lib/site-packages/`；METADATA確認3.8.0，未import／執行。SDK是client參數／結果schema證據，不是伺服器內部計費實作。

官方網路只定點查OpenAI既有compaction／Luna model／pricing頁及針對compaction billing的有限搜尋；沒有採用不同模型或Anthropic計費推論。`.md`網址讀取工具回unsupported content-type，改讀同一HTML頁正文；搜尋未提供可補齊上界的直接契約，不以搜尋摘要充當證明。

## 2. 已確定官方事實

|ID|來源與事實|能支持／不能支持|
|---|---|---|
|F01|[Compaction guide，Server-side compaction／User journey](https://developers.openai.com/api/docs/guides/compaction)：threshold觸發server-side pass；同一回應可emit opaque compaction item，prune後繼續inference，不需另一個compact HTTP。|12000是觸發點，不是最大input、最大總usage或最多pass次數。文件沒有給每筆請求的內部pass數／計費token總量數值上限。|
|F02|[Luna model，規格／Pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna)：context1,050,000、最大輸出128,000；input>272K時整筆請求input費率×2、output×1.5；cache-write為uncached input費率×1.25。|原preflight的短／長門檻unknown在本輪得到具體來源。模型容量不是server-side多階段總billable量的同義詞；128K不是本App的8192，也不拿來換設定。|
|F03|[Pricing，Luna各processing表](https://developers.openai.com/api/docs/pricing)：Standard短context為input/cached/write/output $0.20/$0.02/$0.25/$1.20每M；長為$0.40/$0.04/$0.50/$1.80。Fast長為$0.80/$0.08/$1.00/$3.60；合資格regional processing另有10%uplift。|可以建立已確認endpoint／tier集合內的最高單價；無法單憑單價補足未知token量。不把未限定帳戶／endpoint／tier稱全部已覆蓋。|
|F04|官方SDK3.8.0 `response_create_params.py` max_output_tokens註解：response生成tokens上限含visible及reasoning。truncation disabled註解：超model context input會400。|對生成／輸入接受規則有直接證據；沒有明說inline compaction的額外internal生成／重讀是否全部受同一8192及一次context總量約束。不能把400保護直接換算成所有失敗attempt最大帳單。|
|F05|同SDK `response_usage.py`提供input/output/total，input details含cached/cache_write、output details含reasoning；`compacted_response.py`另列standalone pass的usage。|可事後分項對帳；schema無最大數值／總量不等式。standalone compact有usage不能證明inline免費、等同standalone，或一定只計一次。|
|F06|同SDK service_tier：未指定為auto，依project設定；default為standard。回應tier代表實際處理，可能異於request。enum包含auto/default/flex/scale/priority/fast/ultrafast；註解ultrafast當時限Sol。|接受版build_model未顯式指定tier，因此不能從原碼推斷實際必為Standard。此輪不讀project設定、不改tier；不能用任意unknown tier默認為公開Luna最高價涵蓋。|

上述是契約範圍判讀，不是聲稱OpenAI一定會超額／重複收費。沒有找到上界證據與證明實際無界是兩件事。

## 3. 本案推論：為何現有常數不足

已接受binding使用Responses、store=False、truncation disabled、high/all_turns與原生context_management；`budget.py`自己明示pending response的新inline compaction無法先由count預測。不得用現有byte×2估式、12000 threshold或一次exact input count替代全費用契約。

要在HTTP出站前推出有限最壞費用，至少需要：

- `Imax`：該request全部可能計費input（含opaque內容的伺服器表示、inline compaction相關讀取／可能重讀）之總上界。
- `Omax`：該request全部可能計費output（包含任何另計的compaction生成）之總上界，以及與8192的明確關係。
- `Rin/Rout`：實際允許endpoint／model／processing／region集合內適用的最高費率，cache-write與長context完整納入；若存在其他計費項，亦有上界。

只有這些前提成立，才能用 `Imax×Rin + Omax×Rout + 其他已知最高費用` 作每attempt reserve；所有A/B在途合併後再與US$1比較。**這是待證條件式，不是新guard設計或可採用的數字。** 這裡的I/O是整筆計費總量，不能未經證明就各代入1,050,000與8192。

即使對已知processing集合一律取Fast長context費率、甚至加已知regional uplift，也只處理單價不確定性，不能封住未知總tokens。反之，如果適用tier尚不清楚，也不能光靠事後response tier解決事前reserve。已列公開最貴費率不構成任意商業合約／provider路由的普遍最高價保證。

原生compaction使當前有效context減小，與整筆request已被服務端處理、可能計費的歷史總量不同。12000觸發亦不保證每筆入參≤12000：本輪新增內容、工具結果、schema及opaque context均不由這個threshold單獨設上限。

## 4. 最小缺失契約（可重開此題的具體輸入）

|缺口|需要官方明確回答的內容|目前缺什麼|
|---|---|---|
|B01-C1 inline output|對POST /responses帶native compaction，max_output_tokens是否同時限制所有計費的compaction生成與最終生成；如否，其獨立上限為何？|SDK的response生成上限文義，未明列internal compaction的帳務歸屬／最大值。|
|B01-C2 input總量與pass|單request最多觸發幾次compaction；input／cache-write usage是否含每pass重讀；是否有明確「全筆billable input≤某值」及opaque項目如何計入的上限保證？|context容量及400規則不提供跨pass總計費不等式；opaque bytes與billable tokens關係未給上界。|
|B01-C3完整計費與失敗|inline是否額外收費、如何納入Responses usage；若回應中斷／timeout／服務失敗，全部可能已計費處理是否仍受上述同一上界？|成功回應usage schema只給實際量；未知結果時不能據此釋放reserve或倒證事前安全。|
|B01-C4適用價格集合|凍結執行包的實際endpoint／Luna tier／region與適用單價；auto未解析或非預期tier應如何有據界定？|現行原碼未pin tier；公開表可查，但本trial實際設定本輪未取用，不能假填。|

C1–C3可由足夠明確的官方契約合併回答，不要求逐條新文件。若無此種證據，本輪僅能保留Unknown；不以一兩次paid觀測或以往CT樣本最大值代替普遍上界。既有8K、native12000及Luna/high不因本缺口而調整。

## 5. 採用選項與停止條件

本輪唯一建議：**採納已確認的費率／>272K門檻事實，P3-B01維持Unknown／OPEN，停止擴大搜尋。** 不採用「context×最高價即硬上限」或byte估式，不施工guard、不增加count或試驗預算，不重做Memory。

後續只在取得C1–C3的明確官方上界契約，並由原執行包確認C4、完成原offline guard檢查後，才可重開判斷每attempt reserve是否足以守住US$1。不能確立上界／適用價即依原P3規則不送下一筆；未知usage依原規則停止並保留在途額。沒有新增Owner產品裁決需求，也不把這項P3付費前置升成Task5／6工程阻擋。

本報告未改durable preflight/register，僅交root作有限材料；0產品provider requests，0count requests，0付費，無實作verdict。
