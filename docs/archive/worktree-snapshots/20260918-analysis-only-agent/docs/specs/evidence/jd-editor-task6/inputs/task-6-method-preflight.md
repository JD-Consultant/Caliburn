# Task 6 專業方法接線前置映射

2026-09-10；JD-R002/C03。**只列既定要求與待驗效果，未撰寫新prompt／Skill、未實作或執行測試，沒有實作verdict。** Task 6 須等待root發配已接受Task 5 BASE；本輪未將C-W卡或oracle任何事實帶入方法／runtime。

已讀完整本plan `task-6-brief.md`、三份方法指南、Task 3已接受結果與named SkillAssets／SkillsMiddleware接點。首讀時三指南在isolated同名路徑尚不存在，故從主root唯讀；root其後已原樣補入三指南及10份直接缺失參照，13檔hash清單在本plan `task-6-method-input-manifest.json`。這些只是研究inputs，不加入Task4檔案清單或runtime import。主顧問能力宣告與assets接點最後以指定accepted HEAD `80e29b4a98363f10cffeaf332802adb6f6e29329` 的git show確認，不以Task4施工中api.py作判定依據；實作者到時仍核實際accepted BASE。

## 1. 原文位置與接線範圍

本文代號只是閱讀路由，不新增runtime代碼／Skill ID：

- **G**：[完整工作分析](S:/caliburn/docs/specs/2026-09-09-complete-work-analysis-guide.md)，SHA256 `ea8f240f9c443c3d0587d7943208476408eba593b6fdbc5ff6dd65858f38672f`。
- **D**：[客製深度／訪談校準](S:/caliburn/docs/specs/2026-09-09-customized-jd-depth-and-interview-calibration.md)，SHA256 `80d3ebcc6a2331ab189907d791c63955ba5454f99673f10872d74ca1cbb4c446`。
- **F**：[欄位與寫作指南](S:/caliburn/docs/specs/2026-09-09-jd-field-and-writing-guide.md)，SHA256 `daa8b5a024b421e18ce5429f3225ba8879b2e575c3272aaab713bb870919197f`。
- **Q**：已接受 `docs/specs/2026-09-10-jd-product-quality-acceptance.md` §3–4，補最新對話／手改／保存真相的既定規則，不把§5案例或完整rubric塞入方法。

既定產物只有 `/skills/write-customized-jd/SKILL.md` 及其 `references/complete-work-guide.md`、`references/writing-and-correction.md`。Skill負責適用時機、少量核心方法及按需reference路由；兩refs分別承接完整工作理解、成文與修訂。不是三份重複全文，也不要求每輪全讀。

三指南包含研究歷史及「未來再接線」等當時狀態；方法內容可精煉，舊候選狀態不得推翻後來採用的active v2、平行成果／要求及Task 3正式工具契約。

## 2. 概念→原文→可觀察固定驗收

下列驗收分兩層：**方法資產／request檢查**證實所選規則能讀到、未被能力宣告否定；**固定E2E**證實事先固定回答／工具意圖可走通真服務並產生預期保存效果。固定模型照fixture輸出，不能證明模型學會自然追問或必然遵守方法。

| 必須保留的概念 | 原文位置 | 方法產物位置 | 可觀察固定驗收／反例 |
|---|---|---|---|
| 寫作與實質修正才按需用方法；不每輪修改 | F§3「何時開始寫、何時修正」L90；G§3 L36、§7 L130；Task6.1–2 | Skill核心時機，writing ref展開 | discovery有用途／read路徑；初始不足固定回應只問、JD revision不增；已足夠固定回應能形成稿。無每輪強制read/edit規則 |
| 全工作範圍優先，不只最近一案 | G§1–2 L5／11、§6 L109；D§6 | complete-work ref | 資產保留日常／周期／事件／交付後／低頻；固定增補A後，expected全值中的有效B不消失。不是靠最後一輪重新拼稿 |
| 從重要缺口選中立追問，未知可停留 | G§3；D§3「從缺口選追問」「何時換方向」 | complete-work ref | 資產不暗示答案／不逐欄問卷；固定不足與未知回應不造數字、無要求先填完才能保存。自然是否問得好仍未驗 |
| 職業參考不是員工事實；本人／團隊／他人權限分清 | G§1–2；D§1、§4；F§2、§5資格 | 兩refs按用途 | 固定輸入／expected責任邊界一致；方法沒有模板補學歷、職級、批准權；固定輸出不能越權的fixture按真資料核，不新增雇主事實 |
| 案例支持通則，保留有意義差異，不逐案永久Task | G§4 L51–74；D§2、§5；F§3 | complete-work→writing ref | 既定兩類情境保留輸入／處置／範圍差異，適當歸納不重複Task；新增佐證不必新revision。禁止只按字詞／案件名合併拆分 |
| 客製深度看辨識力，不看字數／頁數／固定項数 | D§1–2、§5；F§3、§7 L172 | writing ref | 資產保留對象、判斷、交接、邊界與必要條件，無八項／N字等任意門檻；固定月檢修訂仍保完整故障處理細節 |
| 目的／職責／任務是不同縮放；標題不等於完整Task | F§1–3 L7–94 | writing ref | expected全值不只剩短標題；既定正文六章不是六工具／六表；文件識別不由模型猜；不為形式造Duty |
| 成果與要求平行、各可多項、條件就近 | F§4 L96、L125；最新格式裁決 | writing ref | 固定active v2完整值中兩組獨立、不配對／不互為父子；改一組不破另一組；未知可留空。不得帶回已退役「重複就合併／省一組」 |
| 既定數字保範圍；印象／個案不升確定周期或KPI | G§4；D§2–4；F§4 L115 | 兩refs按用途 | 固定「月檢僅限約定服務」更正只改適用Task，另一故障處理不改頻率；方法不禁止所有數字，也不要求每Task必填頻率 |
| K是理解規則，S是運用方法，共用須有支持 | F§5 L131–158；G§2；D§2 | writing ref | 固定首建／重讀／引用走已發配refs，定義一份、共享關係合理且无懸空；不全K/S掛全Task，不把履歷／興趣當資格 |
| 實際工作／合理要求／單次表現／願望分清 | D§4、§7；F§4、§6 L159 | 兩refs按用途 | 方法不把漏檢、趕工、單次成果或未來願望寫成正常要求；固定case的期望由已知資料支持；不增加績效／招募／訓練功能 |
| 更正有範圍，矛盾未明先釐清 | G§4；D§3–4；F§3寫作時機；Q§3.7 | writing ref | 固定更正的before／after和全值查回一致；未改區完整；canonical歷史仍可查，不用最新一句無條件覆蓋所有舊內容 |
| 最新已保存對話可先於Memory生效 | Q§3.8、Q09；G§4用途分工 | Skill提醒／writing ref | 固定最新更正未整併情境不由舊Memory蓋回；actual request／背景狀態與新稿有證據。不改背景時機／等它完成才認新話 |
| 人工稿是current，不自動成訪談事實 | Q§3.9、Q10；Task6.3步4；Task3已接受通知結果 | writing ref | 同頁人工保存→下一request有真通知／比較範圍；以人工新版續編、保留無關手改；canonical/Memory不新增假原話，無舊source假背書 |
| 雙向全稿核對、低頻保留、收尾誠實 | G§6 L109–128；D§6；F§7；Q14 | complete-work ref＋Skill路由 | 方法有工作→JD與JD→工作、重要未知及補充機會；固定全稿可查每項支持和保留項。輪數／欄位滿／沉默／「100%」不可作完成證据 |
| 保存回覆依工具真結果，不把意圖當成功 | Task6.2–3；Q12；Task3結果／Task5 lifecycle | Skill最小技術邊界 | 固定success/no_change/failure/unknown按真receipt回答；commit後回覆丟失只一版、原call結果不重複；純訪談取消不等假JD receipt |

## 3. 最小主顧問宣告需消除的矛盾

accepted HEAD的 `experiments/analysis-agent/src/analysis_agent/api.py` 在instructions末段確有：「目前只做訪談分析，不製作或編輯JD。」它與已接同一Agent三工具及Task6寫稿能力矛盾，Task6.2要求移除／窄改。这里只指出必須表達的能力，不先產新prompt：同一顧問可以在需要時按需讀專業方法、讀最新版、以既定JD工具保存／修訂並按實際結果說明。

相鄰已驗保護須保留：優先有價值問題、未知不反覆逼問、不把案例條件外推、改寫不等員工確認、收尾核重要範圍、不顯示隱藏推理。不要為刪一個否定句重寫整份主提示或Memory B/C。

accepted `skills.py` 的「此Skills接線只新增唯讀方法資產……不新增……JD操作能力」本意是**資產載入不授權寫入**，不應一律刪掉。Task6應讓這條邊界不再被讀成「整個主顧問沒有已提供的JD工具」；保留資產唯讀，實際JD操作仍只來自正式工具。兩句需按責任分清，不能讓Skill檔自行獲主機寫檔／執行／網路權限。

固定檢查應查看**最終model request**，確認新skill metadata可見、已接受三工具完整schema／description仍原樣，沒有後置middleware把能力否定或改掉真JD ToolMessage後仍推manifest；不是只看檔案有無字串。Task3 R01–04已CLOSED，僅回歸被Task6改動影響的最終request／factory等接點，歷史結果不改判。

## 4. 既有公開Skill接點：最小固定验收

accepted `SkillAssets` 以package skills目錄的FilesystemBackend虛擬根讀取，經CompositeBackend `/skills/` remap；有ls/read/grep及供discovery用download_files，無write/edit/delete/upload/execute。無Memory時fallback是_NoFiles，不能掛cwd。既有三方法為work-scope-interview、compare-work-patterns、outcomes-and-expertise，需繼續可讀。

已安裝官方 `deepagents/middleware/skills.py` 的 `before_agent` 讀metadata（已有skills_metadata便略過），`modify_request`／公開wrapper附skills list與路徑，不等於把SKILL正文與全部refs每輪注入。此點只用於正確觀測接點，不升級／patch框架。

| 固定驗收 | 可觀察要求 |
|---|---|
| discovery | 新方法名稱／用途／`/skills/write-customized-jd/SKILL.md`由同metadata路徑出現；既有方法仍在；不冒稱同名fake工具有方法權限 |
| body/reference read | 既有read_file可按需讀新Skill及兩refs；asset-local路徑不洩漏成公開路徑；正文與reference的內部連結可由同mount解析 |
| containment | traversal／Windows drive path／越界读取有限錯誤，不能讀host任意檔案；无写檔／执行工具；不因Skill增加JD以外權限 |
| progressive disclosure | 初始request是metadata与用途；fixed read後才實際供給正文；已有效內容不強制重讀；不把三篇研究／整份rubric全塞system |
| actual response integration | 同一main Agent、原ToolNode與來源／結果通道；固定已讀方法＋JD操作經真router/service/native/store；不建第二審核Agent／縮水測試API |
| metadata既有狀態 | 別以舊checkpoint已cache的skills_metadata推論新discovery失敗或成功；按實際fresh invocation測，後续沿既有session語意，不新增每輪reload機制 |

## 5. 不應抄進Skill／runtime的材料

- 整份JSON Schema、生成DTO、持久IDs、operation/digest、scope/profile注入、DB locks、Popen handles、Job/mutex細節。這些由已採契約／App owner承擔；方法可說只用工具已發配引用與真結果，不能造第二wire。
- 固定回合數、每輪先讀所有Memory／Skills、必定edit、固定频率或每Task必填全部分析面向。十四資訊面向是開放觀察清單，非新workflow／Memory欄位。
- 自評100分、stop judge、第二verifier／Agent、coverage IDs／新評分、額外token或工具預算；質性核對不能宣稱已發現所有未說工作。
- 三篇研究全文、國際職業表或研究沿革作每輪prompt；方法引用不等於新增瀏覽／公司上傳／主管簽核功能。歷史候選與後來accepted格式分清。
- C-W或其oracle的任何事實／答案、其他校準答案、CT49與r2跨情境拼接。評讀材料是測試資料，不是員工事實或方法示例來源。已定E2E合成情境需自有清楚fixture標記，不把測試答案搬進Skill讓它「通過」。
- 個人履歷／證照／願望自動作職位門檻；未知當不存在；為專業感捏數字，或反過來一律刪去已確認期限／負荷／條件。

## 6. 固定E2E的證明上限與交接

Task6.3既定六段順序保持：空文件原話先存且不足不寫→足夠後真read/插入→有界月檢修正保其他細節／來源→人工新版通知與續編／純訪談不改→commit回覆遺失對帳及純訪談取消→關Web/API後真新程序比全值／歷史／來源／receipt。這是規定好的合成工程fixture，不在此新增內容或模擬自然問法。

offline factory必經Task5接受的真Windows bootstrap，在DB/native/client前成立owner；只替換provider與專用key/DB，不讓harness代填proof。Task6.4舊bare uvicorn命令須隨Task5最終入口同步，不能成為bypass理由；本文不操作Windows／服務。

以上可證實方法可發現／按需讀、真服務接受固定意圖、資料不被誤改、真browser顯示與保存一致及跨程序恢復。**不能證明自然選工具、訪談廣度、所有職位專業品質、模型總會遵守方法、真人可用性或OS真人IME。** 前者留獨立授權P3，未見案例與真人留P6；固定模型答對不能算自然品質trial。當前沒有新付費授權。

Task6最終必要回歸依brief：focused RED/GREEN後一次全隔離A（opt-in PG真跑分列）及J codegen/test/build/type/lint、authored diff；不改第三方／封存raw換行求漂亮。重跑僅因實際改動／失敗，不為安心重複基底。root控制後续review/commit；本文不作實作PASS/FAIL判決。

**材料交接：**原缺檔已由root補齐；三指南isolated／主root hash一致，13檔輸入清單見 `task-6-method-input-manifest.json`。方法mapping已完成，無需再廣搜／重選框架。實作者須對實際accepted BASE核宣告與公開assets接點，本稿不替Task4/5中的新接線作結論。
