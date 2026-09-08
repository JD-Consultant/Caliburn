# CT41：持續訪談、修補新鮮度與背景一致性

2026-09-09 · LLM-Q019 / CT40-Q01 · 隔離 analysis-agent；G8 尚未作整體穩定認定。

## 這份文件回答什麼

Owner授權局部持續優化、只有重大改變才詢問。延續[本輪計畫](../plans/2026-09-09-ct41-memory-edit-freshness.md)，不重開Memory架構，不加入JD，不改production。模型一直是Luna；研究／試驗／採用分開。

## 已核實的診斷與決定

| 現象 | 直接證據 | 本輪處理／不能推論的事 |
|---|---|---|
| A拿舊工具內容修補；medium格式及原文匹配失敗 | 合成舊讀取對照；baseline及新提示medium都未發布更正 | 新提示說明本輪讀取、就地修改及回讀；high兩次主要內容改善，但仍先失敗才讀正文。**不能說freshness已保證** |
| high不是全部階段的通用解 | 真API第3批B2 high用完8次，格式及原文不符；最後用18次才完成 | 只該失敗批保留計數續跑，test-only上限8→12→16→20；途中B2改medium，不能把恢復全歸因於effort。產品上限未改 |
| 主顧問升級不應自動把B2一起升級 | 原先A/B2共用model binding；高推理第三批慢且仍錯 | 在既有注入點增加獨立B2 model副本，沿同一SDK client、context預算、輸出上限與關閉生命週期。預設仍A medium/B1 high/B2 medium；真訪談測A high/B1 high/B2 medium |
| 第4輪修補失敗不再假裝持久保存成功 | A明說背景尚未完成，再通知B；B成功發布更正 | 沿原tool結果與背景流程，不加入CT35已停放的專用final攔截 |
| 第11輪聊天收尾正確，保存的Memory仍有舊未知 | 原始B2請求107的read_file含完整舊段落（4802字元）；新共通段落確認雲岸本人部署，個案兩處仍未知；空近期Context reader指出衝突 | **不是原文未存、不是讀取被截斷，也不是框架沒套patch**；模型漏改同一事實的其他位置。整場原始結果仍判不完全通過 |
| 原最後一批B2對照改善 | 同一已存B1＋第11輪前基準，僅替換兩條一致性提示，仍medium；5次／4tools完成 | 修訂共通／案例／未知提醒的同一事項，移除過時雲岸未知，保留其他真正未知和案例細節。診斷上限14但實際5，未靠額外步數才成功；源PG資料未改。一次對照不等於全場重測通過 |

## 官方依據：哪些是官方，哪些是本案映射

1. [OpenAI GPT-5.6 prompting guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)：本日透過官方文件工具全文核讀。用明確成功標準、工具先決條件與具體情境調整；逐一保留原失敗，依正確性、延遲與成本選effort。**沒有官方保證high一定比較好**。本案「已解答事項不能仍在另一段待確認」是對Memory一致性的具體成功標準，不是新資料schema。
2. [Anthropic Memory tool／prompting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)：維持Memory最新且一致，按需要強化指引；其原生Memory tool的自動提示不是本案SDK自動附送。該頁[編輯回饋](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#str_replace)另說明成功／不匹配回覆；不把它與本案SDK patch格式說成一模一樣。
3. [LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)：middleware可組裝每次模型可見context，並與持久state區分。本輪不改原對話、不改opaque reasoning內容。
4. [LangChain Model call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)：thread_limit跨同thread累積；resume不應獲得免費重置。限制是成本／防失控護欄，不是語意驗證。本輪保留8/12/16各次失敗與實際累積18次結果。
5. [既有OpenAI流程研究](2026-09-07-ct15-openai-consolidation-input-trace.md)：原話、詳記、候選、正文與導覽原分層未變。沒有新建case表、語意裁判或另一套寫入器。

## 實際修改

- `live_memory.py`：替換一小段行動指引，不增加欄位或強制guard；舊工具讀取不代表本輪最新正文。
- `consolidation.py`：替換兩條既有一致性要求；同一事實可能出現在共通做法、個案與待确认提醒，須同步修訂受影響處。不得把不同事項／不同案例真正未知一併刪掉。
- `api.py`／`service.py`／`scheduling.py`：沿既有model注入，A／B2 effort分開；沿用所有原SDK資源與保護，沒有另加重試loop。
- 離線測試保留CT25歷史golden，以明確delta查本輪接線。它只證明prompt有正確送到SDK，不證明模型必然遵守。

## 測試邊界與審查

- 合成probe含舊工具讀取與新Memory、已確認／未確認／沒有新資訊三種情境。high未確認案例更新了「可能」的說法，仍保留未核對，不是升格為事實；原no-write斷言太嚴，保留原結果並註明人工更正解讀。
- 真API／PG共11輪，沒有預先種Memory；自然通知與背景整理，完整訪談涵蓋需求估算、範圍變更、畫面與串接、驗收部署、維護、每週彙整、交付說明、低頻安全升級。每輪重新開服務也檢查了保存後續接。
- 空近期Context獨立回查有完整實際輸出，第一次抓到真實Memory矛盾，**沒有把「能回答」算成品質通過**。
- 最後一批B2重播使用官方InMemoryStore/Saver及既有PublicationStore；原PostgreSQL訪談只讀。這是診斷重播，不是多了一輪員工訪談，也不是手工修Memory。
- 舊測試結果不改寫；測試helper曾有初始化位置錯誤（0請求），另一次audit與reader共用帳本有競態風險，已在reader结束後順序重做0費用audit。這些均與產品錯誤分開。
- 獨立程式審查：CT41-R01仍要求不得宣稱freshness已保證；R02預設／非法設定測試已補；角色model注入及兩條新B2指引未見新增架構或保護回歸。

## 後續對照與目前採用版本

原失敗逐筆留在[機器證據](evidence/2026-09-09-ct41-interview-and-memory.json)；[實際訪談與回查](evidence/2026-09-09-ct41-transcript.md)提供閱讀版，不以重寫的理想對話冒充實測。

| 階段／請求（full帳本） | 實際結果 | 解讀 |
|---|---|---|
| 原11輪，1–112 | 主訪談完成；第三批B2曾耗盡8／12／16次，第18次完成；最終仍有舊未知 | 原長訪談**不是完整通過**；模型HTTP成功不代表內容品質成功 |
| 空近期回查113–115 | 發現部署責任已確認／仍未知並存 | 不是只靠近期聊天回答，確實讀到保存矛盾 |
| 同B1局部重播116–120 | B2 medium，5次完成一致修訂 | 只讀原PG、複製到官方隔離Store／Saver；不是重跑長訪談 |
| 維護121–135 | 重抽取1次＋B2共14次；原8次失敗保留，再沿checkpoint續跑；發布rev12 | 長引用誤抄與patch匹配造成額外步數，不歸咎資料庫；未放寬產品上限 |
| 維護後回查136–138 | 正確區分已確認責任、不同案例及其他真正未知 | 只支持這份修訂後Memory，不代表新提示長訪談全過 |
| 導覽候選重播139–152／153–166 | medium與high各14次仍未完成 | **沒有證據說全面high可解決編輯問題** |
| 最後工具路由重播167–171 | medium，讀正文→完整寫正文→完整寫導覽→預檢→結束，5次完成 | 短檔完整可見、多處改動時，使用現成write_file降低補丁抄寫錯誤。舊導覽仍留引用清單，不能稱已清理所有歷史導覽 |

採用版本仍使用原框架讀寫工具、SDK patch與既有錯誤回饋，不自創模糊匹配、不增加驗證Agent。`consolidation.py`額外校準既有兩組規則：小型導覽只負責路由；最小**語意**修改不等於一定使用patch。`consolidation_tools.py`的既有write_file說明與此一致。長檔或未完整讀取不得據一頁內容覆寫全文。

追加直接來源（本日核讀）：

- [Codex官方consolidation模板](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md)的density objective及What's in Memory：導覽是高訊號路由，細節／provenance在正文與詳記，搜尋詞須實際能找正文。它允許重要直接連結；本案「不逐批追加全部詳記地址」不等於官方禁止導覽引用。
- [DeepAgents StateBackend.write](https://reference.langchain.com/python/deepagents/backends/state/StateBackend/write)及[官方write_file提示](https://reference.langchain.com/python/deepagents/middleware/filesystem/WRITE_FILE_TOOL_DESCRIPTION)：既有工具可建立或完整替換檔案。本案「短、全文可見、輸出可容納且多處修改時優先完整寫回」是有本輪對照證據的局部路由取捨，**不是各家共同強制規則**。未修改底層覆寫、patch、引用檢查或發布權威。

## 最後版的新職位反例

全新文件／無Memory種子；3輪資訊完整的總務採購訪談（不是第二場長訪談），同一真API／PG入口，A high／B1 high／B2 medium。每輪重開服務；工具及背景產品上限未提高。

- 第1輪：採購／交期／驗收界線；「印象中總務課長」保持未核實。松澗排風機是延遲分批交貨，南堤濾網是尺寸錯誤換貨，沒有互借原因。B2 6次發布。
- 第2輪：確認採購經理核准、課長彙整；補請款、季度供應商評估與低頻替代來源。C成功修訂兩次，保留不自行核准／不做工程驗收／不付款界線。
- 第3輪：補结案標準與兩案結果，AI正常收尾；B2 6次發布。新導覽以主題、案例別名與正文查找詞路由，不逐批堆UUID。
- 空近期Context只讀回查：完整找回兩案例差異、每日／週五／每批到貨／每季／偶發頻率、真正核准者與本人權責；沒有沿用已撤銷的核准者未知。讀者僅用既有讀取工具，未改Memory。
- 27次請求（含回查），估US$0.04103226；所有訪談及背景phase完成、最後idle、rev4。這些是人工核對的有限案例結果，不是統計可靠性保證。

## 保存、Context與回歸驗證

- 前端職位完整來源：11員工訊息＋12則SDK可見AI輸出＝23則。原audit以一問一答算出false；第95請求實際有可見commentary＋final，並非資料遺失。新canonical audit逐則比對所有可見輸出，23則相同，保留原false與判讀，不讀取opaque內容。11個詳記來源區段、2個已發布修補來源收據均精確相同。
- 採購職位：6則完整問答、2個詳記來源區段、2個修補來源收據精確相同。兩文件ID不同；回查與重開後保存內容不變。
- 原生推理／壓縮回傳與下輪傳入均有帳本證據；主訪談full請求46／65／87及role請求15觸發compaction。只記錄opaque雜湊，不解讀其中的推理，也不宣稱永遠不遺忘。
- 最後程式全套離線：**556 passed、41 skipped**；41個skip另接真PostgreSQL：**41 passed**。各有同一個既有Starlette deprecation warning。沒有Web UI／JD驗收。
- 獨立審查：新增role binding、預設／非法effort、完整寫入路由及官方backend接點未見新增Critical／Important問題。CT41-R01仍OPEN：提示不能保證每次修補都先讀最新正文；不復活強制C／額外final裁判。

## 帳本與結論

| 封存帳本 | 請求 | usage估費 |
|---|---:|---:|
| 合成probe | 28 | US$0.01842980 |
| 前端長訪談、恢復與局部對照 | 171 | US$0.24898140 |
| 新採購職位與只讀回查 | 27 | US$0.04103226 |
| 合計 | **226** | **US$0.30844346** |

三帳本均closed；護欄由最初160逐步調到250次，總US$0.75未變，事件見計畫／帳本。費用是API usage估算，不是帳單；這包含診斷與失敗，不能當正常每份職位成本。未測xhigh／max，未把所有階段升high，未改.env、production或JD。

**本切片局部採用；整體G8仍OPEN。** 下一gate是固定最後版，從空白Memory重走一場長訪談＋保存後獨立回查（CT42），不重跑整套舊對照、不增加新架構。新鮮度R01、歷史導覽冗長及不同職位泛化限制繼續保留；只有新實測失敗才重開相應問題。
