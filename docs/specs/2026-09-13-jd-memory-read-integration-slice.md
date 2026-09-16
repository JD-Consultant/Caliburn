# JD 顧問：固定 Memory 讀取與原話回查

日期：2026-09-13；JD-R002／OI-02 局部。基準 `81a1ca76`。沿[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)接已保存的工作理解；不新增產品功能或第二份 Memory。只顯示當輪 JD 改動，不增加舊對話選輪入口；Excel 延後，ADR0074／0075 Proposed、production ADR0060 不變。

**2026-09-17 successor：**本切片的固定回合讀取語意已延伸到 [`MEM-L001` 分層 bundle](2026-09-16-layered-case-and-work-understanding-memory-alignment.md)：A 現在先取得案例與工作理解兩份 guide，再以 typed tools 按需讀取目前案例／理解及其已驗證來源／案例綁定；舊兩檔版本保持相容。這不代表 dispatcher、分層 C、B1 compaction 或完整 App 已完成。

## 效果與責任

顧問每輪先取得已發布工作理解的簡短導覽，需要時使用原生 `ls`／`grep`／`read_file` 讀正文或詳記，再以 `read_conversation` 核對已取得詳記的原話。模型不填文件 ID、Memory 版本、執行身分或保存欄位。沒有發布過 Memory 是明確的空狀態；已發布版本讀不到，則停止本輪，不能假裝沒有工作理解。

| 負責者 | 本次實際接合 |
|---|---|
| App／前景 owner | 入圖前選一次已發布 head、讀固定 guide；將選版 metadata 放入原生 input checkpoint，沿既有前景排空。每次模型及工具檢查相同文件／回合、原生 Store、state 與停止狀態。 |
| 顧問 | 使用導覽定位需要的工作資訊，按需讀詳記及公開原話；辨別歷史理解、員工原话及 AI 上下文。不要求每輪寫 JD，也不把 AI 轉述當員工確認。 |
| 原生框架 | Deep Agents 提供三個文件工具的 schema、格式、錯誤及分頁；LangChain／LangGraph 提供 ToolRuntime 注入、工具替換與 native state 保存。沒有安裝 FilesystemMiddleware 的 offload／scrubbing hooks。 |
| 原 Memory／來源 owner | 同一 StoreBackend／PublicationStore 提供固定版本，原 Source owner 回固定 signed reference。詳記來源由既有 header 解析，不讓模型轉抄內部編碼。 |

本輪選定版本稱 `jd_memory_view`，只含 scope、revision、version ID 及 guide digest；它不是「模型已讀完整 Memory」的證明。導覽只進本次模型 request 的 JSON 資料區塊，不改原 HumanMessage，不保存另一份 Memory 正文。已有的 `jd_model_view` 真回覆配對證據及 JD 讀稿／保存條件維持各自責任。

同輪稍後有新發布時，本輪仍讀原先版本；下一輪重新取目前版。本切片沒有 C 修補，不能以此規則冒稱已完成「修補成功後同輪刷新」；該接點沿下一工作完成。訪談詳記是既有不可變 artifact，新增詳記可被發現，但不因此把它當成已納入目前工作理解。

## 已查明的版本差異與官方依據

查閱日均為 2026-09-13。以下是公開工具／框架契約，不聲稱廠商採用本案資料表、頁長或 checkpoint 欄位。

| 來源／適用狀態 | 官方事實與本案取捨 |
|---|---|
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)，現行 API 指南，服務文件非採用套件 | 說明工具用途、參數與回傳，已知引數交程式提供，初始工具数量宜小。本次共有 14 個工具，沒有讓模型填可推導 scope；數量建議不是品質保證，仍須自然模型驗收。 |
| [Anthropic Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)，現行指南；原工具不需 beta header、SDK helpers 仍在 beta namespace | 支援按需讀記憶，App 負責實際儲存及執行。沿已驗證框架與保存責任提供只讀工具，不額外導入另一套 SDK Memory handler。 |
| [Anthropic 工具設計](https://www.anthropic.com/engineering/writing-tools-for-agents)及[define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)，現行指引 | 工具回傳應適合任務且有明確限制／錯誤。來源工具只回公開訊息及可續頁片段，輸入錯誤與儲存故障分開；3,000 字元沿本案既有界線，不稱跨廠標準。 |
| [Deep Agents 0.7.13 原碼](https://github.com/langchain-ai/deepagents/blob/deepagents%3D%3D0.7.13/libs/deepagents/deepagents/middleware/filesystem.py)，MIT、穩定版 | 0.7 已移除 backend factory，callable 會被拒絕。已用安裝原碼及反例核實，改用初始化好的固定 reader 工具，沒有重新包回舊 factory。 |
| [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools#access-context)／[LangGraph tool node](https://github.com/langchain-ai/langgraph/blob/1.2.11/libs/prebuilt/langgraph/prebuilt/tool_node.py)，實測 LangChain 1.4.0／core 1.6.3、LangGraph 1.2.11，MIT、穩定版 | ToolRuntime 不進模型參數；public `ToolCallRequest.override(tool=...)` 可替換為同一原生工具、固定 backend 的實例。採既有 Memory 讀路徑的這個接點，不增加 Agent hook、工具執行迴圈或通用 backend adapter。 |

套件／lock 未升級；沒有新資料表、migration、背景程序或 provider 設定。採用的原生三工具來源與局部範圍見[套件證據](../../packages/consultant-memory/read-tools-results.md)。

## 失敗與恢復

- 缺 head 可以繼續訪談；查 head／已發布 guide 失敗在模型前停止，不用空內容或最新 fallback。此時尚未進 native input，沿既有 App 回報輸入是否已保存。
- 文件、回合、Store、固定 view 不一致，或取消已生效：不執行讀取。錯引用／無效引數回可修正錯誤；來源／Store 故障停輪，沒有自動模型重試。
- 三原生文件工具維持原參數與正常格式；只從固定 reader 的已初始化實例執行。未绑定的展示用工具不能讀任何內容。原生 validation error 曾帶回完整引數（MR-R01）；以公開 `BaseTool.handle_validation_error` 設定固定提示，保留 error status／原 call ID，沒有自製 validator 或新 hook。
- 原話工具的 offset 只對已解析的固定公開文字分頁，保留 message ID、role、原始文字位移及換行；長訊息可跨頁，串回不丟字，不產生新來源 locator。沒有另外保存 context 不等於没有較早訪談。
- native START／root／child／close 都保留同一選版；舊四欄 START 相容但不繼承上輪 view。保存回覆遺失只重讀確認；Memory read 沒有 JD operation，未完成讀取回明確未完成並停止，不假造修改結果、不重播工具。

## 實際驗證

| 證據層級 | 本次結果與範圍 |
|---|---|
| 套件原生工具 | 原核心＋工具 55 PASS；原生 override 補三案後工具14 PASS；MR-R01 的三反例首3 FAIL／4.24s，修正後工具全17 PASS／4.38s。首次缺新模組及 0.7 factory 拒絕皆保留，見[套件紀錄](../../packages/consultant-memory/read-tools-results.md)。 |
| 來源工具 | 新工具最終 26 PASS；先前新25＋既有54共79 PASS。[首敗與修正](evidence/jd-memory-read-integration/source-tool-results.md)記錄 ToolRuntime 注入／嚴格模型、pytest note 斷言及 malformed summary 分類。 |
| 固定選版與既有接點 | context／managed 23 PASS；六個受影響檔 114 PASS；補 Memory pending/saved 分類八案後，runtime／inspection／checkpoints／Memory context 140 PASS。測試範圍重疊，不相加成總數。 |
| native 中斷／原 view | 新23 PASS；先前新21＋既有85共106 PASS。[作者證據](evidence/jd-memory-read-integration/checkpoint-results.md)記原 root/child、START、錯 scope、不同 view 及 ACK 保存錯 view；未讀 Store 恢復。 |
| 真 SDK＋PostgreSQL | `test_consultant_memory_postgres.py` **1 PASS／9.46s**：九個 MockTransport request、三輪、14工具；原話→合成 fixture 發布→固定 Memory／詳記／原话→共用 JD 新增→下輪取新版本→新連線 inspection 查原結果。真 PG18.6、原 JD 十三表、Saver＋Store＋publication；沒有 setup／清資料。初次 **1 FAIL／10.19s** 是測試把 domain dict 當物件，修正該斷言與查回 API 後通過。 |
| 真 Windows／PG 宿主回歸 | 原 `test_memory_host_native.py` **1 PASS／41.61s**，一般 managed App＋新程序重開仍可用；既有測試只使用合成 native node／fixture 發布，不冒稱新工具在真模型或瀏覽器通過。 |
| 獨立審查 | [App／checkpoint 審查](evidence/jd-memory-read-integration/review.md)：218 不重疊案例 PASS，該範圍未發現 P1／P2；套件作者不自算套件獨審。[工具／來源窄審](evidence/jd-memory-read-integration/source-review.md)首54 PASS後另抓 MR-R01；修正後三反例3 PASS／6.18s、原 marker probe PASS，finding CLOSED，無其他 P1／P2。 |

受影響檢查使用 App 既有 frozen/offline 環境；部分前期命令有 pytest cache 權限警告，後续停用測試 cache。既有 Starlette／AnyIO DeprecationWarning 不影響斷言，沒有把警告稱作新產品缺陷。完整首敗記錄見各責任頁，未執行的 full suite／Web／自然模型未填通過。

主代理最後窄核工具修正時，跨 package／App 的命令首遇兩個 collection ERROR／7.32s（pytest 改用共同上層 root，未載 App pythonpath）；明確使用 `-c pyproject.toml` 後同三檔 **57 PASS／8.48s**。這是測試啟動設定問題，不改產品或框架 import。Windows 宿主回歸現場保留在 `.research-tmp/jd-configured-host-035e033cb3e4452382b3bb7f7456e22f`，沒有清掉合成 DB 或設定。

## 下一步

本次完成「模型可以按需讀到已保存工作理解及原話」的固定接線。仍要接既有 C 即時修補、B1/B2 完整來源窗口與背景整理／排空、專業顧問指引和日常模型設定；之後才是核准預算內的自然訪談驗收。這些集中在[收尾清單](2026-09-13-jd-app-open-issues.md)，不另開競爭中的下一題。

日常 `enable_chat=False` 維持，產品 provider 呼叫為零；沒有宣稱可用成品、滿分 JD 或完整 Memory 顧問已完成。
