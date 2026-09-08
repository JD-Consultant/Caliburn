# CT22：Memory提示契約接線與局部驗證

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **隔離接線與局部技術review完成；251項離線測試通過，自然模型語意驗證未執行。G8 OPEN。**

## 1. 本輪決策與範圍

Owner「OK」核准[CT21 A1](2026-09-08-ct21-memory-prompt-contract-review.md)。依[局部計畫](../plans/2026-09-08-ct22-memory-prompt-contract-implementation.md)將其完整candidate接入；不重研ABC，不新增Agent、強制工具、分類器、排程、欄位或驗證器，不改模型／JD／production。

保存時機集中在Memory system；C工具交代修補用途與實際結果／重試分支；B工具交代空參數通知契約、不等待背景、不把回執當完成。其餘顧問分析、Skills、讀取層級、patch／案例細節／來源與讀取版本權威保留。**這是待證偽的提示候選，不是Runtime強制保存保證。**

上次[CT19](2026-09-08-ct19-routing-regression.md)回答5日、0工具、Memory仍10日的反例保持不變；不付費重製已有baseline。新付費12次／US$0.05範圍已詢問，本稿此刻未取得答覆，沒有真實模型請求。

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
| 自然工具選擇／Memory真寫入效果 | **未測** | 不能從MockTransport預選read_file推得Luna會自主repair／通知 |

最終251項命令：於`experiments/analysis-agent`執行`.venv/Scripts/python.exe -m pytest tests/test_memory_prompt_contract.py tests/test_live_memory.py tests/test_memory_patch.py tests/test_consolidation_request.py tests/test_analysis_skills.py tests/test_current_input_source.py tests/test_memory_read_path.py tests/test_memory_references.py tests/test_context_budget.py tests/test_native_context_budget.py -q --tb=short --basetemp <fresh-path>`。使用真Agent／Saver／Store／ORM與合成HTTP；此組不含PostgreSQL重開或整套scheduler驗證。新增兩項wire對照單跑亦為2 passed／4.63s。

保留施工中診斷，不改寫成全程綠燈：

1. 新測試初稿讀取root result的`memory_initial_revision`造成KeyError。框架將MemorySession狀態留在子流程；改為用測試前的固定head／guide、只將SDK wire中的本輪地址正規化，不改產品state或複製第二份狀態。第二跑才是上述預期RED。
2. 初版C/B docstring縮排造成完整tool description對照FAIL；改用官方description參數後通過，不將此格式差異說成CT19漏用工具根因。
3. 局部安全網首跑209 passed／41 setup errors，為Windows既有pytest暫存ACL；以正常權限和已驗證在worktree內、原先不存在的新路徑重跑得到250 passed。補服務wire的沙箱首跑同樣遇到暫存PermissionError，正常權限新路徑2 passed；最後全組251 passed。沒刪除舊暫存或改產品防護。

## 4. 獨立review與範圍限制

CT22-R01／P2 nonblocking／`AnalysisService._context`的no-Store低階組裝：B工具描述會參照未注入的Memory actions，C工具亦不存在。Reviewer初列重要finding；核對後確認`api.open_service`一律建立PostgresStore，而`BackgroundDispatcher.__init__`會拒絕`store=None`，no-Store只有接線／Skills等測試用途，不是可運作的Memory保存入口。移除的全域B句原本也只在有Store的factory使用。不能把no-Store工具receipt當成會保存Memory。

主agent補查後由同一reviewer再次核定為上述nonblocking限制：未找到會破壞本次full-Store候選的產品路徑。新增服務組裝wire測試確認首次無已發布Memory不等於無Store。**不擅加no-Store保存能力、不撤工具或改核准candidate。**若未來要支援no-Store對外模式，必須另核對工具可用性與說明；不可直接沿用本候選宣稱完整。

其餘方向／schema／patch／來源／Skills／框架錯誤路徑未發現阻礙本切片的finding；不代表自然模型會選對工具。這是依本repo實際可達路徑的scope判斷，不冠名大廠共識。

## 5. 下一個驗證與停止條件

只有新額度核准後才做Luna／medium局部真測；使用原合成訪談隔離副本，保留自然員工輸入，不提示工具名、不force tool choice。先測先前漏存的更正，再測新更正與已保存重述；同時核對正文、導覽、其他案例／未知、原文與引用。

若首個同類漏選／漏存反例再次出現，立即封存停止，不在同一候選上繼續加提示重跑。只有局部品質通過才回到長訪談。原文字增加673字元的代價不變，未量token／費用前不宣稱成本下降。

Decision：落實已核准A1，不追加產品政策。Status：G7隔離技術檢查與review完成；G8 OPEN。Sources：CT20/21及§2官方連結、§4實際程式邊界。Affected：四個提示檔、wire test、README／計畫／本稿與register。Reopen：語意反例或review證明未保留核准邊界。Next gate：新額度核准後局部真測，沒有核准不使用已關閉舊帳本。
