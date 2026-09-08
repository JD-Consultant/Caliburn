# CT22：Memory提示契約接線與局部驗證

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **自然更正真測FAIL，候選封存、不promote；251項離線通過不代表語意正確。G8 OPEN。**

## 1. 本輪決策與範圍

Owner「OK」核准[CT21 A1](2026-09-08-ct21-memory-prompt-contract-review.md)。依[局部計畫](../plans/2026-09-08-ct22-memory-prompt-contract-implementation.md)將其完整candidate接入；不重研ABC，不新增Agent、強制工具、分類器、排程、欄位或驗證器，不改模型／JD／production。

保存時機集中在Memory system；C工具交代修補用途與實際結果／重試分支；B工具交代空參數通知契約、不等待背景、不把回執當完成。其餘顧問分析、Skills、讀取層級、patch／案例細節／來源與讀取版本權威保留。**這是待證偽的提示候選，不是Runtime強制保存保證。**

上次[CT19](2026-09-08-ct19-routing-regression.md)回答5日、0工具、Memory仍10日的反例保持不變；不付費重製已有baseline。接續Owner「OK」核准新付費12次／US$0.05範圍。本次只用1次／usage估US$0.00242175便重現同樣反例，依核准停止條件封存；未沿用CT19帳本，未執行其餘兩項或重跑長訪談。

## 2. 接線方式與官方依据

- `api.py`只移除末尾重複B政策，其餘顧問提示保留；`live_memory.py`以同檔可讀常數維護核准文字，仍由原middleware注入，產品不讀審查JSON。
- C/B使用框架公開的`@tool(description=...)`，參數schema推導及ToolRuntime注入不變。既有C的patch／細節保留指引仍原樣附加。
- 原因：第一版用多行docstring，實際SDK wire包含函式縮排，與核准candidate不同。核對安裝版`tool` signature與[LangChain自訂description官方說明](https://docs.langchain.com/oss/python/langchain/tools#custom-tool-description)後使用其現成參數；没有自行做空白正規化、schema轉換或新工具包裝。
- 提示設計及官方Memory/tool對照沿用[CT20](2026-09-08-ct20-official-memory-tool-prompt-audit.md)。本輪重新讀[OpenAI提示精簡](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)：移除重複，同時保留成功／停止、路由與安全條件。不是官方保證此候選對Luna一定有效。

## 3. 已執行驗證與限制

| 驗證 | 結果 | 能證明什麼 |
|---|---|---|
| 修改前三組既有回歸 | 52 passed，10.50s | C、patch、B通知基線可用 |
| 新SDK wire對照，舊版 | 預期FAIL：實際system不等於核准candidate | 能抓漏移／重複／錯接提示，不是只查常數存在 |
| 四檔實作後wire對照 | 1 passed，4.49s | 第一次呼叫與工具回傳後續呼叫，完整system＋6工具定義和candidate相等；只正規化動態guide／版本／地址 |
| 十組局部安全網 | 250 passed，18.87s；1既有Starlette棄用警告 | 接線、case/source引用、Skills、context預算、stale／失敗重試、通知保存與去重未發現回歸 |
| 補真正服務入口後的最終回歸 | **251 passed，18.51s**；同1既有警告 | 額外涵蓋AnalysisService＋Store＋背景配置：首次Memory未發布時，第一次及工具後續SDK請求仍完全符合candidate |
| 自然工具選擇／Memory真寫入效果 | **FAIL：1次模型、0工具，回答5日，正文／導覽仍10日** | 真實SDK request的完整system＋6工具定義等於CT21candidate；不是漏綁工具、工具執行失敗或額度用盡 |

最終251項命令：於`experiments/analysis-agent`執行`.venv/Scripts/python.exe -m pytest tests/test_memory_prompt_contract.py tests/test_live_memory.py tests/test_memory_patch.py tests/test_consolidation_request.py tests/test_analysis_skills.py tests/test_current_input_source.py tests/test_memory_read_path.py tests/test_memory_references.py tests/test_context_budget.py tests/test_native_context_budget.py -q --tb=short --basetemp <fresh-path>`。使用真Agent／Saver／Store／ORM與合成HTTP；此組不含PostgreSQL重開或整套scheduler驗證。新增兩項wire對照單跑亦為2 passed／4.63s。

保留施工中診斷，不改寫成全程綠燈：

1. 新測試初稿讀取root result的`memory_initial_revision`造成KeyError。框架將MemorySession狀態留在子流程；改為用測試前的固定head／guide、只將SDK wire中的本輪地址正規化，不改產品state或複製第二份狀態。第二跑才是上述預期RED。
2. 初版C/B docstring縮排造成完整tool description對照FAIL；改用官方description參數後通過，不將此格式差異說成CT19漏用工具根因。
3. 局部安全網首跑209 passed／41 setup errors，為Windows既有pytest暫存ACL；以正常權限和已驗證在worktree內、原先不存在的新路徑重跑得到250 passed。補服務wire的沙箱首跑同樣遇到暫存PermissionError，正常權限新路徑2 passed；最後全組251 passed。沒刪除舊暫存或改產品防護。

## 4. 獨立review與範圍限制

CT22-R01／P2 nonblocking／`AnalysisService._context`的no-Store低階組裝：B工具描述會參照未注入的Memory actions，C工具亦不存在。Reviewer初列重要finding；核對後確認`api.open_service`一律建立PostgresStore，而`BackgroundDispatcher.__init__`會拒絕`store=None`，no-Store只有接線／Skills等測試用途，不是可運作的Memory保存入口。移除的全域B句原本也只在有Store的factory使用。不能把no-Store工具receipt當成會保存Memory。

主agent補查後由同一reviewer再次核定為上述nonblocking限制：未找到會破壞本次full-Store候選的產品路徑。新增服務組裝wire測試確認首次無已發布Memory不等於無Store。**不擅加no-Store保存能力、不撤工具或改核准candidate。**若未來要支援no-Store對外模式，必須另核對工具可用性與說明；不可直接沿用本候選宣稱完整。

其餘方向／schema／patch／來源／Skills／框架錯誤路徑未發現阻礙本切片的finding；不代表自然模型會選對工具。這是依本repo實際可達路徑的scope判斷，不冠名大廠共識。

## 5. 已核准的真測與停止條件（已執行）

新額度核准後執行Luna／medium局部真測；使用原合成CT16訪談完整資料庫副本，初始正文／導覽與首句員工輸入逐字對照CT19相等，不提示工具名、不force tool choice。原計畫先測先前漏存的更正，再測新更正與已保存重述；第一項失敗，後兩項依停止規則未執行。

若首個同類漏選／漏存反例再次出現，立即封存停止，不在同一候選上繼續加提示重跑。只有局部品質通過才回到長訪談。原文字增加673字元的代價不變，未量token／費用前不宣稱成本下降。

## 6. 真實結果與可查證證據

- [原樣可見更正對話](evidence/2026-09-08-ct22-natural-correction.transcript.md)、[完整去敏JSON](evidence/2026-09-08-ct22-natural-correction.json)。JSON包含實際system、6工具完整description／schema、工具結果、原始可見Q/A、Memory前後、來源分頁、用量、腳本與hash；不保存密鑰或opaque reasoning內容。SHA-256：`932529be827921343ffe5b31e11faeb648c753c0ed35b5760bdc7b12e0d9e3cc`。
- 正常服務完成回答「每月5日前」，HTTP200／completed、1次／0工具，Memory revision3不變；正文、導覽、processed_source及idle背景狀態全等。沒有repair patch可失敗，也沒有通知或背景模型請求。**只能定位到模型未發出保存動作，不能由此猜測內部原因或斷言Luna一定做不到。**
- 實際wire完整對照CT21審查JSON相等；維持medium／all_turns、原生context接線與同一6工具；未強制tool_choice。延續歷史與Memory都存在，這不是純Memory recall實驗，也不是統計A/B。
- 42則原問答＋新2則問答逐字核對，4份詳記的source/context引用逐頁對照canonical原文全等；Memory本次未寫，所以其他案例／未知保持，**不能反推「將來修補一定保留細節」已通過**。
- 真測前2項wire測試4.69s通過，費用帳本離線驗證第13次／費用不足／closed拒絕。保守預留沿用短context計法：`max(64000, request_bytes×2)`以cache-write費率，加最大8192輸出；request限128000 bytes。每次含SDK重試先預留再依實際usage核算，沒有借舊額度或提高上限。此為試驗護欄、非精確計數或帳單保證；本次9342 input／72 output，費用依[2026-09-08再讀的官方Pricing](https://developers.openai.com/api/docs/pricing)估US$0.00242175，與[模型頁](https://developers.openai.com/api/docs/models/gpt-5.6-luna)的medium及價格規則核對。
- 首次外部執行被安全審查拒絕，當時0請求。隨後唯讀檢查既有合成oracle、CT15建庫腳本／逐字稿、CT16全部21則員工輸入與CT22完整Q/A等值，證明非真實員工資料；同一原動作才重新獲准。沒有換目的地、間接繞過或把密鑰放進payload。
- 候選`b7312d9a`留在隔離分支供重現，**不promote、不再改prompt、不增加驗證Agent／強制工具／費用／產品上限**。本次沒有修改產品src或tests；帳本已closed，三個唯讀phase（初始讀取、來源核驗、真測後核驗）皆不產生額外模型請求。

## 7. 收斂／下一個唯一gate

2026-09-08獨立只讀review（Lorentz）：未發現阻礙保存報告的Critical／Important finding；核對hash、1次費用帳本、0工具／Memory未變、Q/A與引用檢查、停止條件及限制，接受closed／FAIL、G8 OPEN。這不是批准promote候選或證明內部根因。

Decision／finding：CT22提示候選未解決CT15-R07；保存完全依賴模型自主tool selection的可靠性需要重新討論，不能再將「提示已明寫」當「一定保存」。Status：本次實驗closed／FAIL，G8 OPEN。Why：同一自然更正再次只有回答更新，無任何工具動作；既有錯誤處理未被觸發。Sources：§2官方提示／框架資料與§6實際trace。Affected：本稿、evidence、README、plan及register；產品候選保留供重現，不當完成版。Reopen：Owner核准有不同依據的下一個局部選項；不逐句加提示重跑。Next gate：先討論必要保存與模型自主選工具的責任界線，研究既有官方／框架方式後才改；不擅改ABC或換模型。
