# Caliburn Current Decision Register
**JD-R002／同頁聊天與原話保護（2026-09-13，RS-3／4局部）：**[結果](specs/2026-09-13-jd-chat-web-slice.md)已接手改先保存、原聊天request重開、最新原話／回覆及逐次實際差異；Web233、後端及helper219、生成／TS／build與窄獨審通過。真瀏覽器兩輪後PG核head3／operation2與訪談一致，純訪談不改JD。首次fetch中斷明示查回恢復，限定重現仍有未定位連線問題，維持OPEN；不宣稱無故障完成。下一沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)有限定位，再補CV-01整輪呈現；Memory／source／撤回／深歷史／自然品質與完整App未完。需求不清或無據擴複雜度先討論，Excel延後、0產品模型、ADR0075 Proposed／production0060不變。
**JD-R002／聊天HTTP與原修改結果（2026-09-13，RS-4局部）：**[結果](specs/2026-09-13-jd-chat-http-slice.md)完成生成契約、原run狀態／取消／恢復、固定root/source对話頁與真SQL效果全集。最後離線2211 PASS／209 SKIP，三個真PG HTTP情境分批通過，生成／TS及兩組獨審通過；CH-R01收尾誤顯執行中已修。日常新AI仍明示未啟用，原對話可查。下一沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接同頁聊天Web及原請求重開保護；深歷史locator／Memory／source／自然品質與完整App未完成。需求不明或無據擴複雜度先討論；Excel延後、0產品模型、ADR0075 Proposed／production0060不變。
**JD-R002／聊天版次准入與原回合查回（2026-09-13，RS-4 局部）：**[結果](specs/2026-09-13-jd-chat-admission-and-original-run-slice.md)完成同文件原子准入、V2起始版次／V1原樣恢復、有效原生歷史查回及唯讀排空；使用者分享已核兩家官方並記取捨。完整離線1961 PASS／201 SKIP，真PG4與新程序PG4 PASS，AC-R01假成功已修且四組獨審無阻擋。下一沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接生成聊天契約／HTTP／Web；256祖先查找上限與缺鏈明示未解，Memory／source／自然模型及完整App未完成。Excel延後、0產品模型；ADR0075 Proposed／production0060不變。
**JD-R002／新宿主 AI 原回合恢復（2026-09-13，RS-4 局部）：**[結果](specs/2026-09-13-jd-ai-restart-recovery-slice.md)完成同宿主 startup、真舊程序退出證據、原SQL回執與native收尾；相同Agent檢視圖不開provider／不重播。新真程序PG4 PASS、原PG回歸8 PASS、最後離線293 PASS；先前全組1830 PASS／197 SKIP，互斥pending P2已修且獨審關閉。LLM依據以OpenAI／Anthropic為主，AWS對應業務重試。下一沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)補舊run定位與expectedJD准入後接聊天HTTP／Web；Memory／source與自然AI未完成、Excel延後、0產品模型，ADR0075 Proposed／production0060不變。
**JD-R002／AI 共用編輯與回合收尾（2026-09-13，RS-4 局部）：**[本次結果](specs/2026-09-13-jd-ai-runtime-and-tools-slice.md)已接原生 Agent／具名工具、同文件 owner／共同 SQL 與原回執恢復；真 PG 固定 SDK 驗 AI→手改→AI、純訪談及 COMMIT 確認遺失，App 自動收尾不依賴等待者。最後核心253 PASS、真PG14 PASS；先前全組1766 PASS／197 PG SKIP，生成／TS與獨立窄複核通過，停止憑證／callback競爭P2已修。AWS及兩家工具契約有明確映射。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接新宿主 AI 恢復與聊天 HTTP；Memory／source／選區、完整App／自然AI未完成，Excel延後、0產品模型，ADR0075 Proposed／production0060不變。
**JD-R002／人工通知與模型回覆共同保存（2026-09-13，RS-4 第一段）：**[本次結果](specs/2026-09-13-jd-consultant-context-slice.md)已固定相容 Agent／provider adapter，接同版人工事件、真 SDK 請求及完整 AIMessage／notice 原生 PG 保存；重開只讀不重播，缺 terminal 不前進基準。受影響74 PASS（13真PG），全組與ACL補跑聯集1624非PG PASS，193PG未全跑；codegen及獨立審查通過，交錯串流P2已修。AWS共用業務、兩家模型與原生框架依據及private接點限制已記。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接前景AI准入／取消／恢復、具名工具writer，再接Memory／source與聊天；完整App／自然AI未完成，Excel延後、0產品模型，ADR0075 Proposed／production0060不變。
**JD-R002／回覆遺失真瀏覽器驗收與顧問接點（2026-09-13，RS-3 局部）：**[本次結果](specs/2026-09-13-jd-browser-reply-loss-slice.md)確認真DB先提交、HTTP回覆未到、關頁重開後查回原結果；1保存POST／1原操作GET／1實際execute，任務與head2不重複。修正對話框關閉誤落封存分支，新build／TS、Web99、helper23及獨立審查通過。AWS安全重試有實際映射；[OpenAI／Anthropic context前置](specs/evidence/2026-09-13-jd-consultant-context-preflight.md)收斂，SDK不完整串流反例已留。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)閉合實際Agent adapter、人工通知／模型回覆共同保存及固定回應接線。來源／還原撤回／其餘故障／IME、完整App與自然AI未完成；Excel延後、0產品模型，ADR0075 Proposed／production0060不變。
**JD-R002／六章手動管理與瀏覽器恢復（2026-09-13，RS-3 第一段）：**[本次結果](specs/2026-09-13-jd-manual-ui-and-browser-drafts-slice.md)已接實際 React／Next／MUI 畫面與共同 API／十三表；自動保存、未完成表單重開、移動／刪職責保留任務、共享引用及封存恢復有真瀏覽器證據。Python1540 PASS／180 PG SKIP，Web99 PASS，生成／TS／build及獨立審查通過；真PG最終head11一致。AWS共同業務與安全重試原則有明確映射，不宣稱十三表為廠商指定。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)補結果遺失／重開、人工通知與AI回合接合。其餘故障／實體IME、來源原文、還原／撤回及完整App未完成；Excel延後、0產品模型，ADR0075 Proposed／production0060不變。
**JD-R002／持久配置與明示初始化（2026-09-13，RS-1／2→3 局部接合）：**[本次切片](specs/2026-09-13-jd-managed-configuration-slice.md)完成同一本機設定、原身分初始化／續作、普通重開及unsafe HTTP資料集門閘。全組1528 PASS／178 PG SKIP；schema helper18真PG、新配置原生整合6案、修正後跨接點3案通過；生成／TS與獨立審查通過，同名CHECK／predicate的P2已修並窄複核。沿AWS共同業務及安全重試、Microsoft／PG／框架官方契約，不新增通用配置或migration引擎。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接六章手動管理畫面、自動保存與瀏覽器恢復格式。框架可替換、Excel延後、0產品模型；完整App／AI未完成，ADR0075 Proposed／production0060不變。
**JD-R002／文件目錄 HTTP 與建立查回（2026-09-13，RS-1／2→3 局部接合）：**[本次切片](specs/2026-09-13-jd-catalog-http-slice.md)完成空白建立、列表、更名及封存恢復；原 key／意圖查回、資料集門閘與 ETag／CAS 保護，目錄不改 JD 正文歷史。全組 1372 PASS／154 PG SKIP；分別執行真 PG 86、native Saver 接合 10、Windows／PG／HTTP 新程序 2 案例均通過，生成／TS 與兩組獨立審查通過。AWS 共同業務／安全重試及 HTTP 官方依據已記。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)實作[持久本機配置](specs/evidence/2026-09-13-jd-local-configuration-preflight.md)與明示初始化，再接六章管理畫面；未宣稱完整 App／AI 完成。框架可替換、Excel 延後、0 產品模型；ADR0075 Proposed／production0060不變。
**JD-R002／人工保存 HTTP 接合（2026-09-13，RS-1／2→3 局部接合）：**[本次切片](specs/2026-09-13-jd-manual-http-slice.md)接同一業務保存、原操作查回、狀態與明示恢復；真 Windows／PG／Uvicorn 驗斷線、後續改稿及新程序重開不重播原操作。全組 1217 PASS／130 PG SKIP；受影響真 PG 42 案例全部通過，生成／TS 通過。獨立審查發現的兩項狀態契約 P2 已修並窄複核；上游 literal bool 限制由狹窄 App 出口補核，不手改生成檔。AWS／ASGI／本機 Origin 的官方依據與範圍已記。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)補文件入口與持久本機配置，再接六章管理畫面；AI 回合及完整 App 未完成。框架可替換、Excel 延後、0 產品模型；ADR0075 Proposed／production0060不變。
**JD-R002／人工宿主與重啟恢復（2026-09-13，RS-1／2→3 局部接合）：**[本次切片](specs/2026-09-13-jd-host-restart-recovery-slice.md)完成 Windows 原生程序所有權、舊組退出證據及含封存文件的 startup 恢復；真程序＋PG 驗保存前中斷、提交回覆遺失、競爭宿主與多文件，原始對話保持一致。全組 1026 PASS／117 PG SKIP；受影響組 211 PASS（155 非 PG 含 4 真 Windows、56 真 PG 含 4 跨程序），生成／TS 與獨立審查通過。Win32 官方依據與實測修正已記；AWS 共用業務／安全重試原則延續。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接共同寫入 HTTP、查回與狀態，再供管理畫面；AI 回合、日常啟停與完整 App 未完成。框架可替換、Excel 延後、0 產品模型；ADR0075 Proposed／production0060不變。
**JD-R002／人工持久執行流程（2026-09-13，RS-1／2→3 局部接合）：**[本次切片](specs/2026-09-13-jd-manual-runtime-slice.md)完成原生 PG checkpoint、單程序實際人工 writer、原回執查回及 failure-only 恢復；真 PG 驗先記操作再 SQL、ACK 遺失、訊息保留及跨文件進度。955 離線 PASS／108 PG SKIP；受影響接合 131 PASS（84 離線、47 真 PG），生成／TS 與獨立審查通過。AWS 共用業務／重試依據及三個 Agent 方向的持久責任已記，不重開同層廣搜。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接跨程序 host／退出證據，再開共同寫入 HTTP 與管理畫面；AI 回合與完整 App 未完成。框架可替換、Excel 延後、0 產品模型；ADR0075 Proposed／production0060不變。
**JD-R002／查詢 API 與恢復身分（2026-09-13，RS-1／2→3 局部接合）：**[接合切片](specs/2026-09-13-jd-query-api-and-recovery-identity-slice.md)完成公開原次差異、兩個 HTTP 查詢、無 writer 的唯讀服務及只憑原操作身分恢復；真 PG／Uvicorn 新程序驗讀取不改資料。871 離線 PASS／89 PG SKIP；受影響接合 69 PASS（13 離線、56 真 PG），生成／TS 與獨立審查通過。下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接真持久 runtime／writer owner、共同編輯 HTTP 與六章管理畫面；fake authority、測試 server 不算正式宿主。框架可替換、Excel 延後、0 產品模型呼叫；完整 App 未完成，ADR0075 Proposed／production0060不變。
**JD-R002／同版讀取與確切差異（2026-09-13，RS-1／2 局部實作驗證）：**[讀取切片](specs/2026-09-13-jd-read-change-implementation.md)已接六章／項目／歷史讀取、typed refs／cursor、原操作的變更材料、固定淨差異及原結果投影；真 PG 驗讀→定位→保存與歷史隔離。732 離線 PASS／74 PG SKIP；history＋接合 36 PASS（13 離線、23 真 PG），codegen／TS 與獨立審查通過。公開 change-read／HTTP／App、實際 writer／來源／選區／notice 仍未完成；下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)接差異公開契約、run owner 與 HTTP，再供六章管理畫面。框架可替換、Excel 延後、0 產品模型呼叫；ADR0075 Proposed／production0060不變。
**JD-R002／共同保存交易（2026-09-13，RS-1／2 局部實作驗證）：**[交易切片](specs/2026-09-13-jd-transaction-service-slice.md)已接八操作、v3 snapshot、固定意圖、關聯 current 與永久回執；真 PG 驗部分失敗全回滾、原操作不重播、COMMIT 確認遺失、同版讀取及新程序續讀。525 離線 PASS／51 PG SKIP；mapper＋service 42 PASS（13 離線、29 真 PG），獨立審查通過。正式 refs／HTTP／App／顧問與實際程序停止證明仍未完成；下一單位沿[計畫](plans/2026-09-13-jd-relational-app-implementation.md)完成讀取投影、refs、history/change read 及 writer owner 接點。框架可替換、Excel 延後、0 產品模型呼叫；ADR0075 Proposed／production0060不變。
**JD-R002／結果契約與十三表真 DB 基礎（2026-09-13，RS-1／2 局部實作驗證）：**[結果與保存基礎](specs/2026-09-13-jd-result-and-storage-foundation.md)完成合法結果／HTTP 投影、十三表固定 migration 及獨立 PostgreSQL 18.6 初始化；404 離線 tests、22 真 PG tests 通過，包含來源關係反例與新程序讀回。審查發現的 HTTP 分支缺口及真 PG 測試覆蓋缺口已修正。依[資料層前置](specs/evidence/2026-09-13-jd-relational-db-preflight.md)使用穩定 OSS 接點，[讀取前置](specs/evidence/2026-09-13-jd-read-reference-preflight.md)分清永久結果與外部 refs。下一單位集中一致讀取、永久 snapshot／receipt 與 command 完整保存／對帳；尚無完整保存 service／HTTP endpoint／App／自然模型，不擴稱成品完成。框架仍可替換、Excel 延後、0 產品模型呼叫；ADR0075 Proposed／production0060不變。
**JD-R002／八個共同編輯操作與錯誤診斷（2026-09-13，RS-1 局部實作驗證）：**[八個編輯操作](specs/2026-09-13-jd-management-operations-slice.md)已接同一 App 準備／domain，含刪職責保留任務、受限移動、精確選區及 K/S 保護；289 tests、codegen、TS 通過。[AWS／兩家模型／HTTP／紀錄證據](specs/evidence/2026-09-13-jd-app-boundaries-errors-logging-evidence.md)落實錯誤旗標、輸入不經標準 traceback 外露、診斷故障不蓋掉原結果；獨立窄審通過。框架維持可替換、無同層廣搜；下一單位沿[RS-1–2](plans/2026-09-13-jd-relational-app-implementation.md)完成讀取／ref、完整結果與 HTTP，並閉合資料層及十三表初始化交易。仍為保存前候選，無真DB／畫面／自然模型完成宣稱；Excel延後、ADR0075 Proposed／production0060不變。
**JD-R002／框架可替換與首個共同業務切片（2026-09-13，Owner 續行授權／RS-1 局部驗證完成）：**框架屬工程選擇，不寫成產品需求；停止同層品牌廣搜，依相依部分閉合 RS-F。[完整任務／一次更正切片](specs/2026-09-13-jd-relational-command-slice.md)已在新隔離目錄實作：兩具名操作、同一業務候選、generated Python／TS、兩家 SDK 離線捕捉；128 tests、codegen及TS檢查通過。補齊來源合併／最終 basis 與排序反例；新資料仍為保存前候選，沒有DB／App／真模型完成宣稱。下一單位沿[RS-1](plans/2026-09-13-jd-relational-app-implementation.md)補齊其餘具名CRUD及讀取／HTTP／錯誤回執契約，RS-2資料層前置可並行；Excel延後、十三表設計、ADR0075 Proposed／production0060不變。
**JD-R002／技術選型前提修正與 App 框架比較（2026-09-13，Owner 授權／G3 WORKING）：**不優先沿用現有框架或原生元件，不要求整合舊碼；Owner 舉例的框架名稱不是技術偏好。[選型前置](specs/2026-09-13-jd-native-framework-and-integration-preflight.md)撤回原整組沿用結論；依[現行框架比較](specs/2026-09-13-jd-app-stack-selection.md)，研究者選 TypeScript／React／Next.js App Router、Python／FastAPI 為方向，MUI 免費核心為 UI 驗證候選，無跨大廠統一框架的宣稱。下一單位閉合[RS-F](plans/2026-09-13-jd-relational-app-implementation.md)精確組合、有限反例、資料及 Agent 接點，再進 RS-1；不因框架選定而沿舊碼或冒稱實測。JD／Memory 能力、欄位審核與 Excel 延後有效；整體 G4 未閉合、ADR0075 Proposed／production0060 不變；未改 runtime、建表或呼叫產品模型。
**JD-R002／完整 JD 欄位最後審核與 App 優先（2026-09-13，Owner 授權／G3 WORKING，局部設計審核）：**依完整工作分析、客製化深度與十五筆情境完成[欄位充分性審核](specs/2026-09-13-jd-field-sufficiency-audit.md)，無需增減正文欄位／十三表；修正線性revision圖表不一致FA-R01並窄複核DESIGN CLOSED。Owner延後Excel，先App／共用業務／LLM／測試，下載不作本輪門檻。[完整六章管理旅程](specs/2026-09-13-jd-complete-app-journey-design.md)與[原生框架前置](specs/2026-09-13-jd-native-framework-and-integration-preflight.md)承接，[新版RS-0–7計畫](plans/2026-09-13-jd-relational-app-implementation.md)取代舊Plate／v2施工路由。下一單位RS-1精確successor契約＋兩家離線fixture，DA-03恢復格式／資料集識別並行；原生文字欄位優先，不另啟用leaf Plate。整體G4仍未闭合、ADR0075 Proposed／production0060不變；本輪未建表、改runtime或呼叫產品模型。
**JD-R002／CV-01 已選與剩餘設計盤點（2026-09-12，Owner 同意／G3 WORKING）：**Owner 接受[目前稿標記＋同頁按需查看差異](specs/2026-09-12-jd-change-visibility-design.md)，AI 直接保存、無逐次接受；不再列預設 UI 待選。[完成度與剩餘工作 DA-01–07](specs/2026-09-12-jd-design-readiness-audit.md)分清未定版型／工程細節、已設計待驗及舊計畫同步差異；JR-R01–05 不重開。下一單位是完整六章管理旅程與 Excel／原始訪談可審樣本，暫存相容性／資料集識別及 successor 契約前置可並行，再完成新版施工映射／整體獨立審查。整體 G4 Needs revision、ADR0075 Proposed／production0060 不變；未改 runtime／建表／呼叫產品模型。
**JD-R002／整輪 JD 撤回與可見改動（2026-09-12，HR-02 Owner 已選／G3；CV-01 呈現候選／G2）：**Owner 已選[撤回這輪 AI 的全部 JD 改動](specs/2026-09-12-jd-relational-editing-requirements.md#12-hr-02撤回這輪-ai-的-jd-改動2026-09-12)，只改 JD，Memory／案例／原始對話保留；取代下方 HR-01 的不加快捷。[有界設計](specs/2026-09-12-jd-ai-turn-undo-design.md)共用還原及 operation、補可信 run 歸屬。Owner 重申 AI 直接改、不逐次接受，具體[差異呈現候選](specs/2026-09-12-jd-change-visibility-design.md)待看合成示意後討論；推薦目前稿標記＋同頁按需展開。[局部文件審查](specs/evidence/2026-09-12-jd-ai-turn-undo-review.md)與可驗情境已記；下一步討論呈現預設並接續暫存相容性／successor 契約前置。整體 G4 Needs revision、ADR0075 Proposed／production0060 不變；未改 runtime／建表／呼叫產品模型。
**JD-R002／草稿與歷史恢復範圍已定（2026-09-12，Owner 裁決／G3 WORKING，局部文件複核 PASS）：**Owner 已選[DR-01／HR-01](specs/2026-09-12-jd-relational-editing-requirements.md#11-本輪裁決草稿歷史與還原2026-09-12)：聊天或未完整任務、不另設待整理區；歷史對照／局部更正／明確整份還原，不加最近一步撤回。Owner 澄清 workspace 為反覆試改穩定再提供，研究者受權採[WS-01 第一版不設持久 AI 試稿區](specs/2026-09-12-jd-agent-workspace-necessity-research.md#7-owner-澄清後的裁決第一版不設持久-ai-試稿區)。[歷史／來源／重開設計](specs/2026-09-12-jd-history-and-recovery-design.md)已接共同保存與模型通知，兩份[獨立文件審查](specs/evidence/2026-09-12-jd-history-and-recovery-review.md)PASS；下一工程單位是暫存格式／容量／資料集識別與 successor 契約驗證前置。整體 G4 Needs revision、ADR0075 Proposed／production0060 不變；未改 runtime／建表／呼叫產品模型。
**JD-R002／LLM 工作區必要性研究（2026-09-12，Owner 要求／G2 推薦）：**已核 OpenAI／Codex／ChatGPT、Anthropic／Claude 現行官方資料及本地 Memory／JD 接點，完成[能力分界、三方向與採用門檻](specs/2026-09-12-jd-agent-workspace-necessity-research.md)。推薦第一版沿既有受控能力；短期任務筆記或跨多工具 JD 試稿須有具體需求／反例再評估，不新增通用檔案／執行 workspace。B2 已有私有 Memory staging，不誤稱主顧問已有任意工作區。未完整資料的兩種意思與 LLM 暫存分開，見[需求 §10](specs/2026-09-12-jd-relational-editing-requirements.md#10-未完整資料與-llm-工作區的區分2026-09-12)。本輪只有研究／文件，沒有新工具／建表／模型呼叫；G4 Needs revision、ADR0075 Proposed／production0060 不變。主線仍為員工未歸任務草稿、撤回／歷史與重開恢復。
**JD-R002／完整操作與持續修訂（2026-09-12，受權裁決／G3，局部設計複核完成）：**Owner 授權研究者決定必要範圍呈現，並提醒 LLM 可反覆改 JD 與 Memory。已依完整工作分析／寫作／樣稿研究形成[完整業務操作、範圍與責任](specs/2026-09-12-jd-business-operations-and-scope-design.md)，同步格式、工具及資料庫責任稿。JR-R01／04／05 與首敗 CS-R01／02 已[DESIGN CLOSED](specs/evidence/2026-09-12-jd-business-operations-review.md)，R02／03 保持前次文件閉合；均非產品實測。下一單位：未歸任務草稿、自動保存後撤回／歷史與重開恢復。整體 G4 Needs revision、ADR0075 Proposed／production0060 不變；未改 runtime／建表／呼叫產品模型。
**JD-R002／隔離核心已交接（2026-09-12）：**六切片與整體review通過，保存於隔離checkout 54cdfb3420d074d1f4566cb04f12d1fb9a868022／tag jd-editor-core-isolated-20260910；[完整修正與證據](../.worktrees/analysis-only-agent/docs/specs/evidence/jd-editor-core-review/review.md)。最後47 Web／86受影響Python／19真PG、build/types/lint與真Chrome恢復PASS；原Task6完整旅程保留，不累加。**下一工作：P3離線費用防護／執行包及A1受測版本採用清單。**P3-B01仍OPEN、0產品provider；G6正式接合、P5日常維護、P6自然品質／真人與P7成品未通過。R3/R4呈現Minor列P5；未merge／push。

- 最後核對：**2026-09-03**
- 狀態：**目前決策與閱讀路由的唯一入口**
- 流程：[`decision-process.md`](decision-process.md)

> 本表不取代現行 code、`AGENTS.md` 或 Accepted ADR。它負責指出「現在什麼有效、什麼只是候選、下一步只處理哪一題」。Working Decision 若與 production authority 衝突，必須經 successor ADR 與實作 gate，不能直接施工。

## 1. 閱讀順序

後續討論者、reviewer 與實作者依序閱讀：

1. [`../AGENTS.md`](../AGENTS.md)；
2. 本表；
3. 本表指定的 current ADR／contract／design；
4. 只有需要查理由或重新驗證時，才讀完整 research；
5. 只有進入 implementation gate，才讀對應 plan。

文件標題出現「latest／final／approved」不會自動高於本表與 Accepted ADR。聊天內已同意但未寫回本表的內容，必須先補登記，才能被下一個工作階段當成 durable decision。

## 2. 全域治理決策

| ID | 狀態 | 目前結論 | Authority／依據 | 重開條件 | 下一個 gate |
|---|---|---|---|---|---|
| `GOV-D001` | `WORKING` | 重大研究、設計、review 與施工一律使用 [`decision-process.md`](decision-process.md)；本表是第一閱讀入口。 | Product Owner 2026-09-03 核准；AWS／Microsoft ADR 與 Google review 官方來源見流程文件。 | 實際使用證明流程造成重大阻塞、漏掉關鍵決策，或 Owner 改變治理方式。 | 將現有主題逐一登記；不回頭重寫全部歷史。 |
| `GOV-D002` | `WORKING` | 每輪只能有一個 blocking decision ID；鄰近但不阻塞的問題進 parking lot。每輪結束必須寫回 status、理由、來源、重開條件與 next gate。 | `GOV-D001` 流程。 | 同上。 | 所有新研究立即適用。 |
| `GOV-D003` | `WORKING` | `WORKING` 在被明確 supersede 前約束後續研究／設計；它不能越過 Accepted ADR 或現行 code 授權 production。 | `GOV-D001` authority 分層。 | Owner 調整 Working／Accepted 邊界。 | 架構翻案一律另開 successor ADR。 |

## 3. Memory 主題目前狀態

### 3.1 現在仍有效的邊界

| ID | 狀態 | 目前結論 | Authority／依據 | 重開條件 | 下一個 gate |
|---|---|---|---|---|---|
| `MEM-D000` | `ACCEPTED` | Production 仍依現行 code、`AGENTS.md` 與 Accepted ADR 0060；2026-08-30～09-02 的 Memory 研究沒有自行改變 production authority。 | [`adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`](adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)、現行 code。 | Accepted successor ADR 通過且對應 implementation／verification 完成。 | 在此之前只允許 research／design／明確隔離 spike。 |
| `MEM-D001` | `WORKING` | Memory 的唯一產品目的，是讓長訪談後的 LLM 仍能完整理解員工工作與必要細節，支援產出、修訂及最終檢查高品質 JD；Memory 本身不是產品目的，也不操控 JD。 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) 的產品效果；Owner 多輪確認。 | 完美 JD 的產品目的或 Memory 必要效果被明確翻案。 | 作為候選機制與測試的效果門檻。 |
| `MEM-D002` | `WORKING` | 一名員工對應一份隔離文件、一個持續訪談 thread 與一份 JD；目前不需要跨 JD 共用員工 Memory。 | Owner 明確裁決；[`specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md`](specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md)。 | 產品範圍加入跨員工／跨 JD 知識共享。 | 約束 scope／namespace 候選。 |
| `MEM-D003` | `WORKING` | 日常回合不必把全部長期 Memory 放進 prompt；但最後全面製作／檢查 JD 時，必須具備可驗證地處理該 JD 全部有效 Memory 的能力。所有員工工作都不得因摘要或召回策略而永久遺失。 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) §3.4–3.5、M3／M9。 | 官方能力或代表性實驗證明需採不同效果契約。 | 納入 `MEM-Q001`～`MEM-Q003` 與後續 isolated smoke 的驗收情境。 |

### 3.2 Memory reconciliation 決策

| ID | 狀態 | 目前決策／待決問題 | Authority／階段 | 重開條件／已有資料 | 下一個 gate |
|---|---|---|---|---|---|
| `MEM-Q001` | `WORKING` | 採用三層責任：LangGraph Checkpointer 保存每份 JD 的完整員工↔顧問 conversation 與 graph/run/interrupt state；PostgreSQL Store 保存可修訂 semantic Memory collection；Memory manager 只產生 extraction／consolidation 候選；每輪 model context 非破壞性地由兩層資料有界組裝。第一版不建立重複 employee-source 文字 leaf；如日後需要 provenance，只引用 canonical message ID。 | Product Owner 2026-09-03 核准；完整證據與三方案比較見 [`specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md)。 | 真 PostgreSQL contract 顯示長 thread 儲存／延遲不可接受；產品加入獨立 event query/export/retention；官方 primitive 改變；或 Owner 改變一 JD／一 thread 邊界。 | 持續約束 `MEM-Q002`／`MEM-Q003` 與 successor ADR；production 現在仍禁止依此施工。 |
| `MEM-Q002` | `WORKING` | 採 canonical conversation＋選擇性 consolidation：全部案例原始對話耐久保留；重複資訊 no-op；同主題通用新細節 update；需要獨立搜尋／修訂且會影響 JD 的重要差異才 add focused Memory；更正 revise、未解衝突保留兩邊；不採每案例固定一筆。長距離案例指涉必須可按需回查 canonical conversation。 | Product Owner 2026-09-03 核准方案 C；完整官方證據、三方案、A／B／更正情境與八項驗收門檻見 [`specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md`](specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md)。 | 代表性驗證顯示重要案例差異會靜默遺失、同義案例造成近線性膨脹、長距離原始片段無法找回；官方 primitive 改變；或 Owner 改變產品效果。 | 約束 `MEM-Q003`；production 仍須 successor ADR，現在不授權 schema、索引或施工。 |
| `MEM-Q003` | `WORKING` | 採修正後方案 B：Checkpointer 保存 canonical conversation；Semantic Memory／小型導覽先 routing，按需依 canonical message reference 回讀原始問答；未命中才做有界 exact scan／澄清。第一版不替每則 raw message 建 semantic index；只有代表性 smoke 證明重要久遠細節無法找回，才重開 derived raw-conversation／hybrid index。 | Product Owner 2026-09-03 核准；五家官方共同邊界、OpenAI Codex／Agents SDK 與 Anthropic 實際 read path、三方案與限制見 [`specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md`](specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md)。 | 官方新增原生 Checkpointer conversation search；isolated spike 證明 recall、成本／延遲不可接受；或 Owner 改變完整細節找回要求。 | **G4／G5：**收斂 Semantic Memory routing、canonical reference／read contract 與 isolated spike；production 仍須 successor ADR。 |
| `MEM-Q004` | `WORKING` | G4 read contract 採 progressive disclosure：先由小型、可重建的 Semantic Memory 導覽定向；需要更多內容時，模型使用 `search_semantic_memory(query)`，Runtime 在目前 JD／文件 scope 內回傳少量但逐筆完整、自成一體的 current Semantic Memory，以及輕量 `message_refs[]`；只有需要核對原句或問答脈絡時才以 `read_conversation_context(message_ref)` 深讀 canonical conversation。兩個 Tool 都只有一個 required string；scope／limit／filter／窗口／retry 由 Runtime 管理。第一版不另建 conversation summary。Isolated spike 只替 focused Semantic Memory 啟用 LangGraph Store semantic index／embedding；raw conversation semantic index 維持 deferred。名稱與最小結果視圖是 Caliburn mapping，不冒充 vendor 標準。 | Product Owner 2026-09-03 核准 read shape、isolated semantic-index mechanism、兩個 Tool 名稱及 Revision 2 G5 隔離實驗；官方、框架及 pinned contract 稽核見 [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) §3、§6。 | Isolated spike 證明自然語言 routing、canonical deep-read、scope isolation、成本或延遲不可接受；或官方 primitive 改變。 | 執行 G5 隔離實驗並回到 report review；不授權 production。 |

### 3.3 現有 Memory 文件如何使用

| 類別 | 文件 | 目前效力 |
|---|---|---|
| 產品能力基線 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) | `WORKING` requirement input；可用來判斷候選是否覆蓋效果，不授權 mechanism。 |
| 跨家官方研究 | [`specs/2026-08-30-agent-memory-landscape-and-decision-working-research.md`](specs/2026-08-30-agent-memory-landscape-and-decision-working-research.md) | Evidence library；需回到原始官方連結，不能把彙整文字直接當廠商內部事實。 |
| Caliburn 能力 mapping | [`specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md`](specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md) | Working analysis；產品需求輸入，不是 framework 決策。 |
| 最新機制重驗 | [`specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)、[`specs/2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md`](specs/2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md) | Evidence／diagnosis；供 `MEM-Q001` 定向核對。 |
| `MEM-Q001` 定向 reconciliation | [`specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，但仍不授權 production 施工，須由 successor ADR 承接。 |
| `MEM-Q002` 定向 reconciliation | [`specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md`](specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，只裁決相似案例細節、共同理解、consolidation 與長距離回查責任，不授權 schema／搜尋索引或施工。 |
| `MEM-Q003` 定向 reconciliation | [`specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md`](specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，採 progressive disclosure＋canonical evidence deep-read，不授權 production schema、索引或 tool 施工。 |
| `MEM-Q004` read contract／isolated spike design | [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) | **G4 complete／G5 authorized**；read shape、focused Semantic Memory semantic index、兩個 Tool 名稱與最小 contract 已核准，raw conversation index 維持 deferred；只授權隔離 spike，不授權 production。 |
| `MEM-Q004` isolated spike plan | [`plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md`](plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md)、[`specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md`](specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md) | **Revision 2／G5 authorized**；已從產品流程、責任層、Context、Tool contract、framework wiring 到實驗參數逐層分類，並修正持久 conversation 與暫態 tool state 混層、強迫 tool call、重疊 error handling及價格上界四項 finding；Product Owner 於 2026-09-03 核准執行，附帶「由廣到細均以可追溯共識為先、未討論自訂不得冒充共識」條件。 |
| 候選切片與 framework 選擇 | [`specs/2026-09-02-memory-foundation-vertical-slice-design.md`](specs/2026-09-02-memory-foundation-vertical-slice-design.md)、[`specs/2026-09-02-memory-framework-selection-revalidation.md`](specs/2026-09-02-memory-framework-selection-revalidation.md) | **PAUSED**；其中 substrate／authority 結論與後續討論衝突，reconciliation 前不可施工。 |
| Design review packet | [`specs/2026-09-02-memory-foundation-design-review-packet.md`](specs/2026-09-02-memory-foundation-design-review-packet.md) | **PAUSED**；原核准只適用當時候選，不能越過後續重開的 `MEM-Q001`。 |
| Isolated spike plan | [`plans/2026-09-02-memory-foundation-isolated-spike.md`](plans/2026-09-02-memory-foundation-isolated-spike.md) | **PAUSED**；保留內容，不執行。待 `MEM-Q003` 與後續 Manager／Store design 收斂後重寫或 supersede。 |
| Proposed Memory ADR | [`adr/0071-revisable-work-understanding-context-and-review-provenance.md`](adr/0071-revisable-work-understanding-context-and-review-provenance.md)、[`adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md`](adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md) | 仍為 Proposed／deferred；不可當 production authority。 |

## 4. Memory 下一輪 preflight

```text
Topic ID: MEM-Q004
Current stage: G5 authorized；isolated spike plan revision 2 開始在隔離 worktree 執行
Binding decisions: MEM-D000～MEM-D003、MEM-Q001～MEM-Q004
This turn's only blocking question:
  無；下一個 blocking gate 是實驗 report 是否支持後續設計，須待 G5 完成後由 Product Owner review。
Already reviewed evidence:
  2026-09-03 MEM-Q001 已核准 Checkpointer 是 canonical conversation owner；
  2026-09-03 MEM-Q002 已核准 canonical conversation＋選擇性 consolidation，
  並把長距離案例 search／read 列為必要效果。
  2026-09-03 G2 已確認 OpenAI／Anthropic／Google／AWS／LangGraph
  均把 canonical event list/read 與 semantic retrieval 分離；
  補驗 OpenAI Codex／Agents SDK 與 Anthropic 公開 read path 後，
  Product Owner 已核准 Semantic Memory routing＋canonical evidence deep-read；
  不再預設建立 raw-message search_text 副本；
  LangMem 官方有 create_search_memory_tool，LangGraph Store 也有 namespace-scoped search，
  但自然語言 similarity search 必須配置 embedding index；
  Product Owner 已核准 isolated spike 只替 focused Semantic Memory 啟用該 index，
  raw conversation semantic index 仍 deferred；
  LangGraph Checkpointer 可取 latest state／state history，沒有公開的 message-id 內容搜尋 primitive；
  Product Owner 已核准 search_semantic_memory(query) 與
  read_conversation_context(message_ref)；兩者只暴露一個 required string，
  其餘已知 scope／policy 由 ToolRuntime 注入；
  框架已覆蓋 typed validation、tool loop、Store search、retry 與 transient context projection，
  只有 exact-scope guard、canonical message window 與安全結果整形保留為薄 adapter。
  最終稽核已確認 read-tool graph 應為不掛 checkpointer 的單次暫態 execution，
  不把 tool chatter 寫回 80 則 synthetic canonical conversation；
  live prompt 不再直接命令工具順序，而由需要精確原話的任務驗證 search／deep-read 選擇；
  expected tool errors 統一走一個 typed ToolNode handler；
  provider 價格無法建立保守上界時不發第一個 paid call。
Out of scope / parking lot:
  production Semantic Memory schema、Manager prompt／mutation schema、Reference RAG、production migration、
  UI、JD 編輯器、跨 JD Memory、raw-message semantic index；
  production embedding model／top-k／threshold／pgvector／Qdrant 仍不在本輪裁決。
```

`MEM-Q003` 已完成；`MEM-Q004` 的 read shape、isolated semantic-index mechanism、Tool 名稱與最小 contract 均已完成 G4 收斂。Product Owner 已於 2026-09-03 核准 [`isolated spike plan`](plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md) Revision 2 進入 G5；本次只可在隔離 worktree 產生實驗證據，完成後回到 report review，不授權 production、merge 或 push。
