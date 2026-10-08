# 全系統工程設計與維護：官方做法及 Caliburn 審查判準

- 查閱日期：2026-10-08。
- 狀態：**研究建議**。本頁記錄審查前的來源與判準；下列反例不是已發現的缺陷。後續實際 code review、重構及驗證見[全系統工程證據](../../plans/evidence/full-system-review-2026-10-08.md)，不由研究建議推定程式已符合。
- 問題：如何讓整個產品乾淨、可靠、可維護，方便替換 Prompt／Tool／元件做對照，並能在真人訪談時查回實際 Context、Memory、工具及正式結果？
- 範圍：目前單一操作者、本機 Web、單 App 程序及 PostgreSQL 的 JD 產品。研究覆蓋設計、執行、資料、安全、介面、驗證、效能與交付；各面向的施工仍由其責任文件及有效授權決定。

## 1. 結論與比較方式

**高內聚、低耦合與乾淨程式是開發基線，讓專案持續增長時仍能理解、測試及維護。** 這些工程要求不以先證明 JD 品質提升或已發生故障為條件；產品目標仍是產出完整、高品質、忠於員工實際工作的 JD，兩類品質分別驗收。建議採責任清楚的模組化單體，沿正式流程提供必要的可替換邊界、執行證據及分層驗證。分模組依資料責任、業務不變量及共同變更原因；Prompt、Tool 與外部 client 在實際需要的接縫組裝。品質對照與真人使用共用正式保存、scope、取消及恢復路徑，才能將觀察結果用於改善產品。

「各方面研究」表示下面各面向都要有依據、適用判斷及可核對問題；不是功能清單或逐項建平台的施工單。工程方案比較責任與依賴、資料可靠、可理解性、變更影響及實際維護成本；涉及分析或訪談行為時，再驗相應的 JD 品質。基本規範由程式結構、工具檢查、行為測試及審查落實，不逐項要求收益實驗。具體工程取捨沿[開發規範 §3.1](../../implementation/development-standard.md#31-依風險配置驗證與交付粒度)。不要求每次局部修正都巡查所有廠商，也沒有適用所有產品的唯一最佳架構。

以下區分三種證據：**版本文件的行為契約**（例如 PG 隔離與 Python 取消）、**公開工程原則或經驗**（例如 AWS 重試與 Google 審查）、**Caliburn 建議取捨**（如何在本案採用）。官方線上文件不自動證明專案鎖定版的接線符合；真正採用時仍依[技術決策](../../implementation/technology-decisions.md)核版本與測試。本次未升級套件或導入外部平台。

2026-10-08 再核 [Google code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)與 [Microsoft Well-Architected 標準化開發](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/tools-processes)，未見需要改變上述結論的新證據：前者要求審查設計、複雜度、測試有效性及文件；後者建議成熟工具、統一開發慣例與早期自動測試。本案以公開大廠規範及官方框架建議作為審查依據，記查閱日期並核適用版本，分清正式穩定建議、預覽／趨勢與本案取捨；該頁的「AI opportunity」屬可評估方向，不等於必採架構。採用規則回到既有責任文件：格式、型別及生成一致性交自動檢查，契約、保存及恢復用行為驗證，設計、可讀性與測試有效性仍需審查者判斷。這不是全業界唯一標準，也不表示目前程式已符合。

## 2. 架構、程式與介面

| 面向 | 官方依據 | Caliburn 建議、代價與適用條件 | 後續審查／驗收例 |
|---|---|---|---|
| **1. 模組責任與依賴** | [AWS Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)以業務核心及外部 adapter 分離依賴；[Microsoft 架構指引](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures)區分邏輯分層與實際部署。 | 優先模組化單體，以有限公開介面協作；核心規則不依 HTTP、模型 SDK 或 UI。跨責任協調有明確位置。拆服務增加網路、部署與一致性成本，須有獨立部署等具體需求；切更多目錄本身不改善內聚。 | 改一條 JD 資料規則，是否由其責任模組裁決？HTTP、Tool、UI 若各存一份規則，要追查權威散落；transport 的投影與使用者提示則可不同。 |
| **2. 乾淨程式、依賴與組裝** | [Google 審查指引](https://google.github.io/eng-practices/review/reviewer/looking-for.html)重視設計、功能、複雜度及可維護測試；[Microsoft DI 指引](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines)反對 service locator，要求明確依賴及生命週期。 | 用普通函式、明確值型別與必要的有狀態實例；組裝根提供 client、設定、Prompt 與工具。領域與模組抽象依責任及不變量建立，可替換介面依實際替換或 I/O 邊界設計；不因形狀相似就建立萬用 Agent／Service／registry。代價是維護少數明確介面，收益是局部理解與替換。 | 同程序組裝兩個不同候選，配置及 mutable state 互不污染；結束其中一組不誤關共享 client。新增工具不必修改一串無關 flags。 |
| **3. API／Tool 契約與相容性** | [Google AIP-180](https://google.aip.dev/180)區分 source、wire、semantic 相容；[OpenAPI](https://spec.openapis.org/oas/v3.2.1.html#data-types)指出 `format` 支援可不同，描述不等於每個 validator 都強制檢查。 | 延用唯一 Schema、Python／TS 生成與 runtime 邊界驗證。介面要交代 scope、預設值、輸出、副作用、錯誤與生命週期。同步升級的 Web 與已保存／可恢復工作有不同相容要求；不照搬永久對外 API 負擔。本文引用 OAS 3.2.1 不是升級建議。 | 同批合法／非法 payload 在兩端的接受範圍一致；驗 `null`、缺省、未知 enum、額外欄位。嚴格 consumer 下新增選填欄位也可能破壞相容；舊 captured request 要依既定政策恢復或明確處置。 |

責任去向：[程式組織](../../implementation/code-organization.md)、[程式撰寫](../../implementation/coding-standard.md)、[契約策略](../../contract-strategy.md)。研究不另訂目錄樹或第二套 interface 規範。

### 2.1 前後端框架慣用法的補充核對

2026-10-08 後續研究聚焦「規範怎樣落到實際寫法與工具」，沒有重做已涵蓋的 Query key、草稿、交易與 Promise 規則。以下框架細節已補入[程式撰寫規範](../../implementation/coding-standard.md)對應章節；現有程式與檢查設定尚未據此審核。

| 官方依據 | 核實的行為與本案意義 | 規範責任 |
|---|---|---|
| [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[yield dependency](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/) | lifespan 與舊事件的執行方式不同；dependency 清理時點依 scope 而異。共享資源、請求資源、回應與正式保存不能混為同一生命週期；串流資源也不能過早關閉。 | §5 資源與副作用；具體行為須核鎖定版 |
| [FastAPI overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/)、[pytest fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html) | override 會略過原依賴及子依賴；fixture 在 yield 前失敗不跑其 yield 後清理。測例須保留受測責任，清理假依賴及已取得資源，避免下一例被污染。 | §7 測試隔離與外部替身 |
| [Pydantic validators](https://pydantic.dev/docs/validation/latest/concepts/validators/) | plain／wrap 與 default 的驗證路徑不同；型別宣告不等於所有輸入都經相同檢查。使用既有 Schema 時仍須測真正接受範圍；不以自訂 validator 任意改原話。 | §2 型別與邊界驗證 |
| [React Effect 與互動](https://react.dev/learn/you-might-not-need-an-effect#sending-a-post-request)、[清理與重入](https://react.dev/learn/synchronizing-with-effects#how-to-handle-the-effect-firing-twice-in-development) | 使用者互動與外部同步分開；Effect 能承受建立、清理、再建立。重掛載不應多送業務命令，舊 scope 的事件不污染目前職務。 | §6 UI 寫法；既有恢復契約仍有效 |
| [Ruff formatter](https://docs.astral.sh/ruff/formatter/)、[mypy imports](https://mypy.readthedocs.io/en/stable/running_mypy.html) | formatter 不處理全部 lint 問題；import 缺型別可能形成 Any 傳播。要查實際設定、檔案範圍及例外，不能只看工具已安裝或 strict 字樣。 | §8 工具檢查與人工審查分責 |

成熟框架提供依賴、資源、狀態與測試機制，Caliburn 應先正確使用；額外工具按能否減少重複與除錯成本選用。網路情境重現的 MSW、工具測試的 MCP／Inspector、追蹤及評測平台的候選比較沿[持續對照研究](2026-10-08-agent-experimentability-and-observability.md)，不因出現在研究就視為已安裝或已完成驗收。

## 3. 資料、長任務、並行及網路

| 面向 | 官方依據 | Caliburn 建議、代價與適用條件 | 後續審查／驗收例 |
|---|---|---|---|
| **4. 資料權威、交易與隔離** | [PG 18 隔離](https://www.postgresql.org/docs/18/transaction-iso.html)：Read Committed 每個 statement 取快照；Serializable 有額外成本，仍要處理整交易重試。 | 沿 JD、Memory、Plan 各自正式來源及不可變版本；原子性與一致讀取由明確交易／鎖策略保證。每次執行依 App 綁定讀取版本，長訪談不持有跨輪 DB 交易。隔離級別不代替職務 scope，也不一律升到最高級。 | 並行准入、完成與 Memory 發布時，不能混用讀取版本；別檔案 ID 必須拒絕。正式結果與必要關聯在同一失敗情境一致回滾。 |
| **5. 長任務資格、版本及恢復** | [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers#durability-modes)：`sync` 在下一步前保存；`async` 有未寫入的 crash 窗口；`exit` 不保證執行中間狀態。replay 可能重做模型及外部呼叫。 | 分清執行資格、checkpoint 與領域正式結果。恢復沿已捕捉 request、scope、版本與原操作核對；checkpoint 不能單獨保證外部效果只執行一次。較密保存增加 I/O，須按故障風險選擇並核鎖定版行為。 | 在模型結果保存、工具提交、tool output 保存、正式完成處中斷；重啟後不重做已知效果、不採用失效 writer。換 Prompt／Tool 後恢復舊工作，不靜默套最新配置。 |
| **6. async、取消與資源所有權** | [SQLAlchemy 2.1](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)要求並行 task 各有 AsyncSession；[Python 3.14](https://docs.python.org/3.14/library/asyncio-task.html#task-groups)的 TaskGroup 管作用域內子 task，取消需清理且通常重拋 CancelledError。 | engine／client／pool 由其建立者管理；借用者不關閉。只並行語意獨立的工作；TaskGroup 適用同生共死分支，持久長任務沿 supervisor。I/O timeout、Python 取消、Turn 取消與正式採用資格分開處理。 | 分支失敗或關閉 App 後無遺留工作／連線；並行檔案不共用 mutable scope。取消與完成競爭只成立契約允許的結果；`wait_for` 可能等待取消清理超過期限，不能假定時間到就已停。 |
| **7. 網路失敗、重試與未知提交** | [AWS timeout／backoff 經驗](https://d1.awsstatic.com/builderslibrary/pdfs/timeouts-retries-and-backoff-with-jitter.pdf)提醒 timeout 不證明遠端未執行，重試應有界且避免各層相乘；[AWS 冪等 API](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)以原意圖身分及原子保存辨識重入。 | 檢查連線、讀取、串流及總工作期限的實際涵蓋。區分 provider 暫時失敗、DB 保存重試及未知業務效果對帳；沿既有 command／operation 身分核結果。保留冪等結果有資料成本；無 provider 保證時，重新請求是新 attempt，可能再次計費。 | COMMIT 後回覆丟失，重入查到原效果；同 ID 換參數拒絕，相同參數的新意圖仍能執行。SDK＋Graph＋service 不形成重試倍增，確定權限／格式錯誤不盲重送。 |

責任去向：[持久化架構](../../architecture/persistence.md)、[資料與契約](../../implementation/data-and-contracts.md)、[Agent 執行](../../implementation/agent-execution.md)、[撰寫規範](../../implementation/coding-standard.md)。以上不要求新增 receipt、validator 或持久化引擎。

## 4. 安全、前端及使用者體驗

| 面向 | 官方依據 | Caliburn 建議、代價與適用條件 | 後續審查／驗收例 |
|---|---|---|---|
| **8. 權限、信任邊界與本機網路** | [Microsoft SDL](https://www.microsoft.com/en-us/securityengineering/sdl/practices)把安全納入設計至營運；[OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)要求可靠邊界逐次驗權；[REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)限制 CORS 來源。 | 以本機實際威脅研究：外部網站、錯誤檔案 scope、模型輸入、不可信內容及本機敏感資料。Host／Origin、同源及變更操作保護沿既有契約；CORS 不是身份驗證或完整 CSRF 防護。scope／版本／能力由 App 綁定並在服務驗證，模型不決定權限。不因大廠有 SSO 就新增雲端帳號。 | 惡意 Origin、另一檔案物件 ID、模型偽造 scope 都不能越界；A 工具不能寫 Memory。dev proxy 不能改寫來源資訊而讓測試繞過正式邊界。 |
| **9. 金鑰、敏感內容與模型注入** | [OWASP Secrets](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)涵蓋最小權限、輪替、撤銷及安全紀錄；[Prompt Injection 防護](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)要求工具權限及參數驗證，不能只靠另一個模型判斷。 | 金鑰限 backend；原話、JD、Memory、引用、tool output 均視為資料，不能提升能力。必要 Context 正文受控查閱，普通 log 去敏；按用途限制外送及保留，沿既有資料刪除權責。防注入沒有保證全阻擋的單一技巧，不任意改員工原話或增加 guardrail agent。 | 來源內的「忽略指示」無法取得額外工具；密鑰不出現在瀏覽器、例外或診斷匯出。刪檔與保留策略涵蓋衍生診斷資料，不能以觀測為由留下無期限第二份私人內容。 |
| **10. 前端狀態、競爭與可信回饋** | [React 狀態設計](https://react.dev/learn/choosing-the-state-structure)避免矛盾及冗餘；[TanStack Query 官方原件](https://raw.githubusercontent.com/TanStack/query/main/docs/framework/react/guides/invalidations-from-mutations.md)說明 mutation 後 invalidation，以及等待 Promise 的 pending 行為。 | server cache、局部草稿、未確認命令分責。編輯基底快照有用途，不能為去重讓背景 GET 蓋掉草稿。串流內容、後端保存、重新讀取是不同效果；cache 框架不替 App 保證交易或命令冪等。需維護少量明確狀態，避免成功／失敗互相矛盾。 | 切檔後舊回應不污染新檔；背景刷新保留未送草稿。保存已確認但刷新失敗時，呈現保存成功及畫面待更新；候選／串流片段尚未正式採用不能冒充完成。 |
| **11. 安全呈現、可用性與匯出** | [W3C APG modal](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)定義鍵盤、焦點進出與 Escape 模式；APG 不是整體 WCAG 符合證明。安全來源另見上兩列。 | 沿既有安全 Markdown、MUI、受控 PDF／字型／網路設定；測實際整合。正文可閱讀、狀態可辨認、窄畫面可操作，需兼顧長訪談及長 JD；不以元件庫已支援就免驗，也不自行重造焦點管理。 | 全程鍵盤開關 dialog、刪除後回合理位置；長正文及引用能讀。惡意 HTML／遠端圖片不執行或外連。PDF 中文、分頁及引用保持可讀，匯出失敗不改正式 JD。 |

責任去向：[交付與營運邊界](../../architecture/delivery-and-operations.md)、[介面與交付](../../implementation/interface-and-delivery.md)、[持久化及刪除](../../architecture/persistence.md)。安全研究以目前部署和資料權責為準，不套用不存在的公網多租戶產品。

## 5. 驗證、觀測、效能及交付維護

| 面向 | 官方依據 | Caliburn 建議、代價與適用條件 | 後續審查／驗收例 |
|---|---|---|---|
| **12. 分層測試與故障診斷** | [Google 測試工程](https://abseil.io/resources/swe-book/html/ch12.html)重視測試可維護性；[Playwright](https://playwright.dev/docs/best-practices)建議測可見行為、隔離資料、穩定 locator 與等待式 assertion，失敗時以 trace 診斷。 | 純規則／契約、真 PG／程序競爭、mock provider 旅程、真模型品質分層，各驗其保證。只 mock 不證明保存與恢復；每次全量 E2E／付費訪談也不划算。重試不能掩蓋 flaky，測試亦須清楚且好維護。 | 網路回覆丟失後 reload，正式效果只成立一次；browser trace 能連到對應後端 execution。錯誤訊息與 evidence 能定位失敗層，不需重跑付費模型才知道當時發生什麼。 |
| **13. Prompt／Tool／元件對照** | [Anthropic Agent eval](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)區分軌跡與最終環境結果；[LangSmith 分層評估](https://docs.langchain.com/langsmith/evaluate-complex-agent)涵蓋單步、路徑與成品。 | 沿正式 workflow，在實際責任接縫替換；宣告變因、版本、資料、評分及停止條件。局部固定 Context 回答局部問題，自主旅程驗完整 JD；不指定唯一工具順序，也不拿工具成功當品質成功。模型波動需相稱的重複，不能由各一場推定穩定優勢。 | 只換工具說明時能核實其他設定；多項連動就只評整組。兩組 JD／Memory／Plan 不互相污染；標明真人、模擬員工與 AI 評閱，保留失敗案例及正式成品。 |
| **14. 執行觀測與真人查閱** | [OTel GenAI](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md#execute-tool-span)提供模型／工具關聯語彙，仍為 Development；[Google SRE monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)結合內部診斷與外部效果，觀察 latency、traffic、errors、saturation。[OTel Logs](https://opentelemetry.io/docs/specs/otel/logs/data-model/) 為 Stable，定義事件、時間、等級與 Trace／Span 關聯；[OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html#event-collection)提供安全收集與失敗驗證原則。 | 沿既有原件及可重建投影查證，不另造執行權威。由職務檔案／Turn 找實際 model request、組裝後 Prompt／工具定義、Context、綁定 Memory 版本、參數、回傳、耗時及採用結果；失敗／取消也能由 execution 查。全文受控取得，普通 log 保留定位。查詢與保留有成本，不能任意全量複製。 | 真人測試能依 runbook 查回當輪資料；區分「綁定可用」「預載」「實際讀取」，不從最新 Memory 還原過去。紀錄存在不等於成功或採用，缺少紀錄不等於未執行；不要求受訪者 UI，也不展示隱藏推理。 |
| **15. 效能、容量與成本** | [Google SRE overload](https://sre.google/sre-book/handling-overload/)指出 QPS 不一定反映資源成本，重試可能放大負载；低流量產品不必套用大型系統的自適應限流。 | 量測模型首回應／完整回應、token/context 成長、工具／保存耗時、pool／lock 等待、checkpoint 大小及診斷成本；成功與失敗分開看。沿有界並行及容量准入，依瓶頸改善。cache、壓縮或刪除可能影響事實、引用、恢復與品質，須一併驗證。 | 長訪談增長及多檔工作時資源仍有界；外送限流不引發重試風暴，容量不足仍能看已保存資料。改善延遲或費用不能以 JD 完整性及可信度下降換取。 |
| **16. 依賴、建置與供應鏈** | [Docker 建置指引](https://docs.docker.com/build/building/best-practices/)建議可信精簡基底、多階段及固定版本；[GitHub Actions 安全](https://docs.github.com/en/actions/reference/security/secure-use)要求最小權限、固定 action SHA、隔離不可信程式；[SLSA 1.2](https://slsa.dev/spec/v1.2/build-track-basics)以 provenance 描述產物來源，分級保證抗竄改能力。 | lock、生成器、基底 digest、browser revision 與字型來源可追溯；固定版本仍須有意識地更新及驗相容。CI 若存在，按來源配置金鑰及發布權；本機 App 不需立即導入 attestations 平台。manifest 不等於達成 SLSA 等級。 | 從指定來源可建出對應 App／Web／契約，產物不夾金鑰或私人測試資料；不可信 PR 取不到正式模型金鑰／發布權，標題不成為 shell。結果可追實際 commit 或 WIP 雜湊及 lock／設定。 |
| **17. 啟停、migration、備份及恢復** | [PG ALTER TABLE](https://www.postgresql.org/docs/18/sql-altertable.html)說明鎖、掃描及重寫成本；[PG SQL dump](https://www.postgresql.org/docs/18/backup-dump.html)提供一致快照與還原方法，但還原錯誤／權限仍需處理，`psql` 預設可能遇錯繼續。 | 沿本機 runbook 停 App、備份、明確 migration、驗證再啟動；評估空間與中斷，不為大廠模式增加零停機雙寫。備份檔存在不等於可恢復；程式回退也不會自動回退 schema／業務資料。跨機自動備份仍非目前產品範圍。 | 以前版代表資料升級，含歷史引用、Memory、Plan 及在途 execution；不用清庫通過。於隔離 DB 還原，核正文、引用與恢復資格；不只看 row count 或 healthcheck。 |
| **18. 文件、審查與長期維護** | [Google Code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)審設計、行為、複雜度、測試與文件；[小型變更](https://google.github.io/eng-practices/review/developer/small-cls.html)降低理解及回退成本。 | 改動按可理解的產品行為或工程責任切片；規則回責任文件維護，入口只管狀態與路由。研究、現行保證、已實作、實測及歷史分開；移除過時敘述，不只附加補充。簡單變更按風險驗證，不用文件量／測例數代表品質。 | 任一差異可追產品契約或工程規範、責任及相應驗證；Prompt／schema／生成物／README 一致。結案後能知道實際效果與未驗範圍，不必讀整段對話猜現況。 |

LOG 建議：Logs 記事件、Traces 串步驟，Context／Memory 正文走受控診斷，不混作正式保存。事件名、等級與欄位保持穩定，沿 execution／request／attempt／operation 關聯；可得才加 trace／span ID，區分發生與觀測時間。Exception 沿既有安全分類，不任意輸出 SDK 訊息、headers 或 locals；不可信值限長並按格式編碼 CR／LF 等字元。訂定查閱權限、容量／輪替與保留期，驗證磁碟滿、無寫入權及輸出端故障不改正式結果或觸發業務重送；權威故障保存仍按原契約，不因日誌可降級而放行。

責任去向：[開發規範](../../implementation/development-standard.md)、[撰寫與觀測規範](../../implementation/coding-standard.md)、[驗證計畫](../../implementation/verification-plan.md)、[交付與營運](../../architecture/delivery-and-operations.md)、[runbook](../../runbook.md)。Agent 對照及觀測的完整推論沿[前一份研究](2026-10-08-agent-experimentability-and-observability.md)，不在本文重建第二套規範。

## 6. 插件化與現成 Agent harness：要採用到哪一層

本節回應使用者提出的 **DeepSeek Harness（dsh）**，不是 LangChain 的 Deep Agents。已由 [DeepSeek 官網](https://www.deepseek.com/en/harness/)核對官方 repository，再讀其架構、插件原理、工具管線與 Cordis 論文；並比較 OpenAI、Anthropic 及 LangChain 的公開設計。這是前述模組與生命週期面向的具體選型研究，尚未採用新平台。

### 6.1 先分清四種問題

| 層次 | 解決什麼 | 不自動得到什麼 |
|---|---|---|
| 模組化／可組裝能力 | 用明確介面替換 Prompt、工具、Context 策略、client 或觀測實作 | 動態安裝、獨立發布及卸載機制 |
| 插件系統 | 封裝能力、宣告依賴、發現與載入、版本／生命週期管理；部分系統支援熱替換 | 安全隔離、資料交易、模型品質或各插件一定能相容 |
| Agent harness | 驅動模型與工具迴圈，管理 Context、狀態及長任務執行 | Caliburn 的 JD、Memory、Plan 權責及正式採用契約 |
| 評測 harness | 啟動案例、控制變因、收集證據與評分 | 正式產品的執行權威；測試驅動仍應走受測正式流程 |

這是本次比較用的責任分類，各廠商對 plugin 的封裝範圍不同。插件可與模組化單體共存；採可插拔介面，也不必同時採動態安裝或重寫模型迴圈。

### 6.2 官方方案能借鑑什麼

| 方案及第一手依據 | 官方公開做法 | 本案收益與限制 |
|---|---|---|
| **DeepSeek Harness**：[架構](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md) | 以 profile／bundle 組裝插件樹；model、tools、session、loop 均可替換。能力分成介面定義、provider、consumer；模型可見歷史由持久 session log 投影。 | 很適合研究「換一項能力而不用改整個 loop」及可重建輸入；可借鑑其清楚的擴充位置。整套採用還會接入 Node runtime、session 與程序生命週期，須比較與既有 Python／PG 權責的適配成本。Python SDK 仍啟動 dsh，不能當成純 Python library 無成本嵌入。 |
| **Cordis**：[primer](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cordis-primer.md)、[論文](https://arxiv.org/abs/2608.25512) | 依賴透過 `inject` 宣告；註冊與清理相伴，依依賴變動啟停元件。事件區分觀察、串行、並行及可攔截管線；順序與返回語意是契約。 | 可借鑑資源所有權、可撤銷註冊及替換後清理。本文實讀論文概念及 §6.1／6.3／6.6：系統外已發出的效果不在撤銷保證內；不可信程式仍需外部 sandbox；版本相容也不是依賴 key 存在就成立。這些不構成生產力或 JD 品質優勢已實測的證據。 |
| **OpenAI**：[Plugin architecture](https://developers.openai.com/plugins/concepts/plugins)、[Agent 組裝](https://developers.openai.com/api/docs/guides/agents/define-agents)、[Agents API 架構](https://developers.openai.com/api/docs/guides/agents-api/architecture) | plugin 封裝 Skills、MCP、hooks 等能力；Agent 可組裝 instructions、tools、模型等。程式 local context 與模型 conversation 分開；Codex harness／session 與 App 自有工具、環境各有責任。 | 借鑑具名配置、有限工具集合與可信程式依賴分離。Skill 是方法，MCP 是工具服務邊界，不能代替資料權限。採託管 harness 涉及保存與外送責任，須另作架構比較；不是加一個插件就完成。 |
| **Anthropic Claude Code**：[plugins](https://code.claude.com/docs/en/plugins)、[hooks](https://code.claude.com/docs/en/hooks)、[Agent eval](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | plugins 打包 skills、agents、hooks、MCP 供分發；hooks 有的觀察，有的可改參數、Context 或阻擋操作。不同事件／handler 的錯誤與 timeout 語意不同；eval 區分軌跡與實際結果。 | 內部替換不必先建 marketplace。觀測 hook 與 policy hook 分責，不能把任何 hook 都視為可靠權限閘門。若 hook 改參數或回傳，必須查得到原值、實際執行值與模型收到的結果，否則比較會混入隱藏變因。 |
| **LangChain Deep Agents**：[overview](https://docs.langchain.com/oss/python/deepagents/overview)、[customization](https://docs.langchain.com/oss/python/deepagents/customization)、[backends](https://docs.langchain.com/oss/python/deepagents/backends) | 在 LangChain／LangGraph 上組裝模型迴圈、middleware、檔案 backend、摘要與子代理等；可替換 Prompt、工具與 backend，內建組件也可能改模型可見內容。 | 多項現成能力確實需要時值得比較；只換 Prompt／Tool 不足以證明整套划算。其指引檔 memory、檔案工具與 todos 不等於 Caliburn 的員工工作 Memory、JD 或 Markdown Plan。不能把業務資料直接暴露為任意檔案寫入；原生 Responses item、call ID、壓縮、usage 及恢復相容尚待鎖版驗證。 |

DeepSeek 的[官方狀態](https://github.com/deepseek-ai/deepseek-harness#developer-preview)仍為 developer preview，且明示會有不相容變更；[安全聲明](https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md)不將目前軟體視為 production-ready。這是直接替換正式執行層的重要選型條件，不妨礙借鑑其設計。各方案的公開文件只證明可用的擴充方式，沒有證明它們已滿足本案全部契約。

### 6.3 本案建議：以測試與診斷效果選擇組裝方式

**目前的具體問題是對照測試難組裝、真人操作 UI 後難查內部執行。** 模組化單體可以採普通依賴組裝，也可以採 MCP、插件或現成 harness；沒有技術禁用清單。優先比較當前成熟方案能否降低修改、測試、觀測及維護的總成本，並保留必要產品契約。先前偏向靜態組裝的建議是初步取捨，不是限制；現成工具若更有效便可採用，不要求先自行重造。觀測與工具測試的具體候選見[持續對照研究](2026-10-08-agent-experimentability-and-observability.md)。

| 項目 | 建議替換粒度與界線 |
|---|---|
| Prompt／指南版本 | 角色組裝選擇所需提示；能核對實際送出的內容。換版不必一律改成 Skill。 |
| 工具能力 | 描述、輸入／輸出契約及實作有一致歸屬；可只換其中一項做受控比較，但型別、權限與保存仍相容。MCP 可提供標準工具介面與現成測試客戶端，適配層沿共同業務模組執行，不複製規則。 |
| Context／Memory／Plan／Changes | 可比較載入及投影策略，保持各自資料權責；策略不得悄悄改事實或繞過綁定版本。是否載入、載入多少及最後可見內容都可查。 |
| 模型／外部 adapter | 在真有不同實作時提供必要接縫；保留原生協定及錯誤語意，不為統一介面丟掉必要欄位。 |
| 執行觀測 | 只觀測的 consumer 不改工具參數或控制流程；必要原件保存與可失敗的額外匯出分開，沿既有權威。 |
| 評分／測試驅動 | 方便替換案例、grader、候選配置；受測行為共用正式流程。候選名稱不能替代有效配置及實際軌跡。 |

元件來源、版本與組裝順序應可追；何時允許切換依既有 binding 契約，不能用最新插件覆寫已捕捉請求。程式組裝、宣告式配置、插件管理或開發者 UI 按使用效果與整體成本選擇。固定的是產品契約，不是永遠固定某個實作。

**插件平台**可因內部測試組裝、能力重用、版本管理或獨立分發的實際收益而採用，不以第三方生態為必要前提。比較收益時一併計入發現、相容性、依賴衝突、信任、安裝／卸載、資源清理與舊工作恢復。**直接換 harness**則比較省下的 loop、Context、工具及觀測維護工作，與協定、狀態、程序和資料權責的適配成本；不能只比較範例程式行數，也不能只因現有程式已寫好就排除。

### 6.4 值得列入審查的反例

- 兩組實驗只宣稱換 Prompt，預設 plugin 卻多注入 Context、摘要或子代理；應按實際改動重新界定變因。
- 模型原參數經 hook 修改後才執行，紀錄只保留原值；無法解釋真正的寫入。DeepSeek 的[工具管線](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/tool-execution-pipeline.md)也分開變換管線、guard 與最終觀察，不能只記工具入口。
- 更換 provider 後舊 listener／task 未清理，造成工具重複註冊或執行；或卸載誤關其他工作借用的 client。
- 權限 hook timeout 後被跳過，或擴充拿到未受限 DB 連線直接寫正式資料；可插拔不應讓原本必要的業務檢查變成可選功能。
- 更新插件後舊工作恢復拿到不同工具／Context 行為；版本紀錄、狀態相容與恢復政策必須一起核實。

本節尚未安裝 dsh／Deep Agents、執行模型或啟動替換實驗。先以現行規範與上述反例審查擴充成本，再決定是否需要少量介面整理、有界 prototype 或更大架構變更；不因插件名稱就跳過比較。

## 7. 從研究進入審查的用法

下一輪全面 code review 應以以上 18 面向及 §6 的插件／harness 比較為覆蓋入口，對每一面向留下**符合證據、具體缺口、尚未驗證或有理由的不適用**。每個發現要指向負責模組，依性質提供程式結構、依賴關係或可重現情境，說明後果或維護風險及修正／驗證方式；沒有證據不能把建議寫成現有 bug。高內聚、低耦合等名詞須落到責任、依賴、修改影響與生命週期來判斷，不要求架構缺口必須先造成執行失敗。

先處理可能丟資料、越權、重複效果、不可恢復或讓實驗失真的問題，再按證據改善組裝、診斷與維護負擔。若責任文件已定義相同保證，檢查落實即可；若建議改變產品語意、資料權責或跨層契約，回該文件及決策流程比較，不能由研究表直接施工。

## 8. 證據限制

- 本文連結為本次實讀的第一手文件或官方原件；Microsoft／AWS／Google 的設計文章是公開建議或經驗，不是共同強制標準。AWS timeout PDF 為既有工程文章，不冒充 2026 新功能。
- TanStack 文件頁本次擷取失敗，改讀官方 repository 原件；其 [人用入口](https://tanstack.com/query/latest/docs/framework/react/guides/invalidations-from-mutations)仍可查。LangGraph、OpenAPI、SLSA 與線上 Python 文件可能超前專案鎖定版；研究不表示已採用其新功能。
- 未驗現有程式、效能、安全性或真人查閱便利程度。例子是後續檢查設計，並非測試已通過；本文也不證明任何 Prompt／Plan 方案已改善 JD 品質。
- 這次覆蓋目前產品的完整工程面向；未來若改公網服務、多使用者或跨機部署，需重新研究威脅、身份、可用性、資料及營運契約，不能直接沿用本機結論。
