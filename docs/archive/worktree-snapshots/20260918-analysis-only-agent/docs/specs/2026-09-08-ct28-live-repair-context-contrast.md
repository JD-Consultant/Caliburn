# CT28：即時修補的延續 Context 小對照

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **對照完成、帳本closed：A1修補成功／A2仍漏存；8次、估US$0.01237055。G8 OPEN，未改產品。**

## 1. 本輪邊界與依據

承接[CT27§4、§6](2026-09-08-ct27-live-repair-no-call-evidence-review.md#4-下一步選項停止重複改提示)，不重新討論Memory架構、B時機或patch介面。固定CT25提示／六工具、Luna／medium／all_turns、auto tool choice、同一CT16合成Memory及同一句更正。兩個新資料庫副本彼此隔離，舊CT22／26 FAIL及closed帳本不變。

- A1：只給本輪員工訊息及本輪後續工具鏈；原始歷史仍完整保存並能回查。固定system、導覽、Skill／tool不變。
- A2：沿現行inline compaction延續視窗，包含舊回答及opaque。不是只換reasoning參數。
- 兩組均暫不啟動背景worker，避免背景發布冒充C修補；工具仍可提出通知並留在測試資料庫，但不執行B。此為兩組相同的實驗隔離，不改產品排程。
- **共享最多16次生成請求、US$0.10保守護欄**，含SDK重試；不重開舊帳本。沿既有每次預留／usage結算；這是小測上限，不是產品限制。
- 看實際工具輸出、發布正文／導覽、來源引用與未改內容；不以模型回答正確等同寫入成功。任一API／契約／額度錯誤停止，不追加prompt或強制tool；兩組語意失敗仍完成這一個成對診斷，之後停止。

實驗使用既有LangChain `request.override(messages=...)` 接點，只替換測試程序中的view函式，不改canonical state。[LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)。新回合的工具call／result及原生reasoning保留原樣；`all_turns`只有在提供前文時才能利用前文，fresh視窗不是刪除資料或更改opaque。[OpenAI reasoning across calls](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)。API標準短context Luna費率於本輪重查：input0.20／cache-read0.02／cache-write0.25／output1.20美元每百萬token。[官方Pricing](https://developers.openai.com/api/docs/pricing#text-tokens)。

## 2. 判讀限制

這是**整體延續context**對照，不是只隔離compaction或不可見推理。兩組各一次不提供穩定成功率，不據此取消長上下文／reasoning、改模型或改產品流程。A1成功僅表示現有工具任務在此輸入可自然完成；若A2仍失敗，下一步才討論進一步隔離延續因素。兩組若皆失敗，不再用同義prompt反覆試，回到CT27候選及新證據討論。

## 3. 執行與收尾

| 組別 | 模型／工具次數 | 實際保存結果 |
|---|---|---|
| A1本輪短context | 7次模型／6次工具 | 自然選擇搜尋、讀取、修補；第一次失敗後重新讀取、再修補成功。正文及導覽都10日→5日，revision3→4 |
| A2原歷史延續 | 1次模型／0次工具 | 回答5日前，但正文及導覽仍10日前，revision3不變 |

兩組共8次HTTP200／completed，無API重試、輸出／步數／費用上限阻擋。64899 input／3192 output token；usage估US$0.01237055，不是實際帳單。A1估US$0.00992185，A2估US$0.0024487；不能把未完成保存的A2當成同效果低成本方案。測完即封存，未使用剩餘額度、未重跑長訪談。

**實際接線核對：**所有8次完整system及六工具通過CT25獨立fixture核對；除runtime本輪引用外兩組固定system相同。A1首請求只有system＋本輪訊息，沒有opaque；本輪每次返回的reasoning均原樣進入後續請求，工具往返未剪掉。A2可見input在正常化本輪來源地址後與CT26相同，opaque hash也相同。沒有強制tool choice或更改medium／all_turns，不能說是換模型解決。

**實際資料核對：**兩組重開service讀PostgreSQL後結果相同。每組原42則可見問答＋本輪2則逐字一致；四份詳記的11頁／48段來源引用逐字匹配canonical對話，並額外確認A1發布回執的runtime來源可讀到本輪更正。A1正文／導覽做精確字串比較：只把對應的10日改5日，其餘內容／案例／引用全部相等。processed_source未被C推進；B保持idle，沒有背景整理代做。

### 3.1 保留的失敗，不包裝成一次成功

A1工具順序：`grep → read_file → grep → repair_memory(失敗) → read_file → repair_memory(成功)`。第一次patch在「要被替換的舊行」末尾多寫了原文沒有的中文句號`。`，官方applier回`Invalid Context`；不是JSON解析／縮排／ID錯誤，也不是工具沒有執行。整批未發布，錯誤回傳給模型後，它重讀原段落、去掉多出的句號，第二次才成功。此例證明現有錯誤回饋／有界自修正能走通，**不證明高可靠或patch問題已消失**。未放寬匹配、未改工具契約。

測試設施另有兩個問題，與模型品質分開記：

- Windows sandbox拒絕pytest暫存目錄，兩次執行setup／cleanup失敗；改為批准的非沙箱隔離測試後，完整SDK契約2 passed／4.60秒。未更改產品權限或防線。Ledger與request-view離線自測通過。
- 新wrapper最初漏沿用舊runner的`base_url='http://localhost'`，預設`testserver`被TrustedHost拒絕。當時0次模型請求、原42則問答未變；修正測試網址後另以相同middleware重現400／`Invalid host header`，保留在instrumentation_errors。這是本輪新測試程式錯誤，不是API／LLM或產品問題；沒有重開closed帳本或掩蓋已執行的模型失敗。

## 4. 結論與下一個唯一gate

**能下的結論：**相同Memory、提示和工具，在短context可以自然修補；原延續context再次漏存。這使「延續context整體」成為有差異證據的診斷方向，不應繼續假定只是提示沒接到或patch執行器壞掉。A1仍多走一次失敗patch，與A2根本未選工具是兩個不同問題。

**不能下的結論：**無法由一組對照判定舊可見回答、opaque compaction、其他延續內容或隨機性哪個是唯一原因；不解讀隱藏reasoning，也不將短context擅自採為產品設計。G8仍OPEN，正常長訪談穩定性尚未驗收通過。

**下一唯一gate：**與Owner審閱是否進一步隔離「舊可見答覆」和「opaque延續」的影響，再選最小產品修法。CT27 B的官方custom patch介面对照仍是候選，不因A1曾出現標點匹配錯誤就自動換介面。B排程仍沿已核准段落通知＋文字量後備；不加Agent、不強制修補、不追加同義prompt。

## 5. 可重驗紀錄

[去敏完整證據](evidence/2026-09-08-ct28-context-contrast.json)包含兩組實際請求／工具回傳／回答、Memory前後、原文引用核驗、重開核驗、腳本及hash；opaque只存hash，不存內容或金鑰。SHA256：`6718b012c0d56ce7b82a7f7ce5bd8920c5b8b799ec44df588aabdff256210d6f`。

封存腳本成功核對上列數字、只有日期改動、原CT22／CT26證據hash不變；`git diff 3af6466b -- src/analysis_agent tests`為空。無production／JD／產品src或tests修改。此次為主agent自審，非獨立review；本地保存點見register，沒有merge／push。
