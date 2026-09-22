# JD 匯出與真人顧問交付

**2026-09-12 最新匯出需求：**Owner 已確認 **JD 第一版先提供 Excel**，並可另外匯出完整原始訪談，供系統外使用或與真人顧問續談；真人核對不是本系統的功能。Excel 版型與原始訪談格式由[需求釐清 §7](2026-09-12-jd-relational-editing-requirements.md#7-功能目的與使用方式釐清2026-09-12持續討論)接續確認；JD 內容沿既有完整 JD 研究，不按輸出版型刪減。下方整套「JD＋原始問答」合併交付包、HTML／DOCX 推薦與 Plate 接法仍為舊候選；此次沒有採用舊技術設計或啟動施工。

**PARKED（2026-09-10 Owner 裁決）：**Owner 同意核心編輯接線，但明確表示「先不用做真人交付核對」。本附件的真人交付／核對功能、HTML／DOCX＋原始問答交付包暫不施工，也不列本版核心編輯器的退出條件；只有 Owner 重新要求時才啟動。下文是保留的研究候選，不是現行施工指令。既有來源回查及一般文件編輯不受影響。

2026-09-10；JD-R002/C03；**G4 設計附件／推薦，尚未核准格式、按鈕或施工。**與 [ADR 0073](../adr/0073-plate-jd-app-working-document-and-revision-authority.md)、[App 接線 §8](2026-09-09-jd-editor-app-integration-design.md#8-可核對的員工情境與匯出)一次審閱。有效方向依 [register](../current-decisions.md)及 [decision process](../decision-process.md)：Plate 免費核心、同一持續工作稿、同畫面聊天與差異、更正形成新版；不恢復個別 pending、approved projection 或舊 iCAP／XLSX／A 級別限制。本輪僅讀文件、官方來源與既有程式；沒有安裝、匯出實驗或產品修改。

## 1. 推薦及交付效果

**推薦第一版產生一個自足的 UTF-8 HTML 交付檔**：前段是明確保存版本的完整 JD，後段是同文件的原始可見問答及可回查依據，附文件／版本／問答截止範圍。檔案內含必要樣式，可離線閱讀、搜尋、複製；不依賴 App、登入、CDN 或外部字型。這是確定的工程推薦，不把選擇 HTML 寫成 Owner 已同意。

App 內仍只有原工作畫面的聊天、唯一可編 JD、可展開差異與歷史。下載檔是某個時間範圍的可攜副本，沒有寫入 authority，不自動跟隨 current，也不成為「更正後」第二操作頁。真人在 App 內核對／修改仍走同一工作稿；若確實要在外部文書軟體續改，採 §4 的 DOCX 替代方向。外部修改回傳／匯入不在此範圍。

輸出只改呈現，不再請模型摘要、專業改寫或補齊。職責、Task 完整敘述與就近要求、成果、K／S 用途、案例差異、責任邊界及重要未知全部依保存值呈現；不可只輸出短標題。依據為 [欄位與寫作指南 §3–§7](2026-09-09-jd-field-and-writing-guide.md)、[正式 profile](2026-09-10-jd-plate-document-profile.md)與 [完整 r2](2026-09-09-frontend-engineer-jd-sample.md)。不要求有固定節數、Task 數或每欄非空，也不把交付標為專業核准。

## 2. 固定 JD 版本與訪談範圍

以下是 App 的確定性讀取責任，不增加 export workflow、另一份持久文件庫或模型工具：

| 情境 | 推薦行為 |
|---|---|
| 一般交付 | 請求綁定同文件、畫面明示的已保存 revision。App 按該不可變 revision 讀完整 clean value，不能生成途中再讀 latest head 拼出另一版。輸出標示職稱／文件識別、JD 保存版與時間、輸出時間；時間不代替 revision 身分 |
| 問答截止 | 另由既有 canonical conversation owner 固定一個已保存 snapshot／首末訊息範圍，按真實順序讀至該邊界。推薦涵蓋文件起點至匯出取樣時已保存的可見問答；**不把它宣稱為產生該 JD 版時的精確來源快照**。若問答較 JD 新，明示「此範圍可能含尚未反映於所選 JD 的補充」 |
| 未保存手編 | 不偷偷採用 browser value。一般「交付目前稿」先沿既有人編保存成功後再取得 revision；保存失敗保留輸入並回報，不能交付舊版卻稱目前畫面內容。若介面提供明示的「已保存版」交付，須清楚說不含未保存內容；本稿不新增強制按鈕 |
| AI busy／結果未知 | 匯出是唯讀，可讀已確認的確切保存版，不必等背景 Memory。AI 候選、半串流內容及未對帳的新版本不納入；標示本輪仍進行／結果確認中。若使用者要的是此次尚未確認的結果，先依既有 operation 對帳，不能猜版本 |
| 生成途中又有更正 | 已取樣 JD revision 與問答範圍不換成新值；這次輸出仍標原版本及範圍。新更正另保存、另產新交付；不覆寫舊檔的歷史意義，也不聲稱舊檔仍是 current |
| 文件刪除／跨文件引用 | 套用既有 active／document scope 檢查，返回可辨識錯誤；不以輸出 port 繞過正常讀取邊界 |

JD 與 canonical conversation 是不同事實 owner。交付綁定兩個可重讀的固定識別，不要求把它們複製進同一 JD transaction，也不聲稱跨 Saver／Store／JD owner 的全域原子快照。重試同一取樣應讀回同內容；重新選最新範圍才是另一份交付。無須建立持久 export job 才能做到這項唯讀生成。

## 3. 原始問答、依據與缺失

**原始問答**是既有持久對話中的員工原文與顧問實際可見文字，保留說話者、順序、換行、訊息識別及既有完成／未完成狀態。包括追問、員工更正及較早的原說法；不能只交員工回答、Memory 摘要、最後一輪或經模型潤飾的逐字稿。不虛構未保存的回答或時間。

系統提示、工具結果、provider reasoning／不透明內容不冒充原始問答；它們的排除範圍有簡短說明。已保存而尚無顧問回答的員工文字仍屬原文，若在所選範圍就保留並標明未完成；中斷／runtime notice 可作狀態說明，不改署名為顧問原答。實際附件／非文字內容若未包含，列出種類／缺件，不聲稱文字檔已含所有媒體。

**現有 source 事實：**隔離 [ConversationReader](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/sources.py)的 reference 限定 document／checkpoint／first／last；`read` 回傳角色、message ID、text offset、下一頁及 omitted types，每頁最多 3,000 可見字元。取得指定 checkpoint 失敗會拒絕，不能改拿最新文字。這支持沿既有 owner 讀取；**完整文件起點至截止的匯出 port 尚未接妥**，不能直接取一次 `read` 或 UI 最近訊息就說完成。正式接線透過其公開讀取／範圍發配能力，讀至 `next_offset=None`，核對分頁連續性，不從私有 checkpoint 表自行拼接或另存來源 mirror。

JD 內的 `source_refs` 轉為可讀「依據」與檔案內問答錨點；有多處引用同一訊息時可共用同一原文，不反覆複製成多份來源。原引用保留不等於所選 JD 每句已核實；手改、AI 再改也不自動更正 Memory。既有來源 owner 若提供更正關係／失效狀態，就照實附註；不由時間或文字相似度自行創建更正 lineage。

- **某筆依據無法定位，但所選問答範圍可完整取得：**保留 JD 原文及引用識別，清楚列出「此依據目前無法回查」。可交付供真人釐清，但不得標為依據完整／已核實，也不靜默移除引用或改寫正文。
- **所選原始問答範圍缺失、分頁中斷或保存版不可讀：**這次「JD＋原始問答」完整交付失敗；明示缺失並保留 App 內原稿，不產生冒稱完整的半份文件。不用 Memory 或後來版本代補。既有權威資料保留政策須能支援所承諾的讀回期間；本稿不另訂保存年限或重做 Memory。

## 4. 兩個免費開源方案與直接證據

官方來源查閱日均為 **2026-09-10**。Fact 是原生能力，Mapping 是本案取捨；本輪未驗實際 JD 匯出。

| 方案 | Fact／版本及授權 | 本案 Mapping／代價 |
|---|---|---|
| **A：HTML；推薦** | 已有 `platejs@53.3.11`／`@platejs/core@53.3.11` 的 `platejs/static` 與 `serializeHtml`；React／React DOM `19.2.4`。Plate core 及 React 為 MIT。[Plate HTML](https://platejs.org/docs/html)要求 base plugins＋static components，返回內容 HTML，樣式另提供；[React API](https://react.dev/reference/react-dom/server/renderToStaticMarkup)輸出靜態 HTML，不能 hydrate，Suspense 可能只輸出 fallback。[React 固定版 LICENSE](https://github.com/facebook/react/blob/v19.2.4/LICENSE) | 沿正式 profile 的有限靜態 renderer，另把問答／依據呈現為一般語意 HTML；不複製 live editor／Client hooks。嵌入必要 CSS，無 script／remote resource，文字正確 escape；所有資料先讀齊再 render，不能以 loading fallback 當內容。不承諾 Word 直接開啟後可無損續編，也不把瀏覽器另存 PDF 當已驗證的正式匯出 |
| **B：DOCX；外部續改需求時的替代** | `docx` 官方 **9.7.1 tag** 的 [package](https://github.com/dolanmiu/docx/blob/9.7.1/package.json)及獨立 [MIT LICENSE](https://github.com/dolanmiu/docx/blob/9.7.1/LICENSE)已核對。[Packer 固定 source](https://github.com/dolanmiu/docx/blob/9.7.1/src/export/packer/packer.ts)以 OOXML／ZIP 產生 Buffer／Blob；[官方 Table API](https://docx.js.org/api/classes/Table.html)提供列、格及段落內容。這是 OSS 產生器，非購買 Word／Copilot | 需新增固定依賴與一個針對正式 profile 的有限 OOXML mapper：段落／marks／清單層級／表格及必要屬性／來源錨點。它不直接消費 Plate value 或 React CSS，不能將 HTML 改副檔名當 DOCX。須另驗繁中、長表跨頁、清單、外部文書軟體開啟及保存；使用者選何種文書軟體不由此推定。沒有自動回匯／修改同步／tracked-change 接線 |

**固定本地 source 複核：**[core static bundle](../../.research-tmp/jd-editor-native-probe/node_modules/@platejs/core/dist/static-CTmHK15f.js)的 704–721 行，`serializeHtml` 確實呼叫 `react-dom/server.renderToStaticMarkup`，預設 `PlateStatic`；class／data stripping 是選項。檔案 SHA-256：`ff71ed69820aad0ec2bb150b131182e3a8a5e340e9ddc5d19a441bae51b74c24`。這是 source 核對，不是匯出實驗。完整 body／JD／來源顯示仍須本案 static components；不能由 API 存在推成任意 profile 已保真。正式部署沿 [profile 固定依賴](2026-09-10-jd-plate-document-profile.md#1-固定引擎與官方插件)核對各插件授權。

DOCX 的 npm registry 本輪讀取未成功，未確認安裝產物及完整 transitive lock；9.7.1 只以官方 tag／原始碼作本次替代方案版本依據。若改採 B，安裝前固定正式發布版本／完整相依及授權，再做有限驗收，不追 `latest` 或宣稱此 repo 已有 DOCX 能力。沒有增加第三個 PDF／模板引擎候選。

## 5. 有限完整性驗收與停止條件

以下是施工驗收，不是本輪已測結果；先驗推薦 A，不平行做兩套 exporter。

1. **完整 r2 與 profile：**逐一對照本文、標題層級、三張表、巢狀清單、Task4 異常處理、Task8 約定月檢、K／S 用途及責任邊界。另用正式 profile 合法的未歸屬內容、空白、未知、合併格／格式測例核對；不能靠補假資料或攤平表格通過。
2. **版本與競爭：**取 revision R 後 current 改成 R+1，輸出仍完整屬 R 並標同一問答截止；未保存／busy／unknown 不冒充新稿。重送同取樣不重選基底，下載不觸發模型、修改 JD／Memory 或批准狀態。
3. **問答逐字與範圍：**以超過 3,000 字且跨多輪的既有固定問答驗連續分頁、說話者、換行及首末邊界；保留更正前後與未完成狀態，排除工具／不透明區塊；缺來源及缺頁各有明確結果，不誤報完整。
4. **離線可讀：**完整檔案在未連 App／網路時開啟，表格、正文、來源錨點、長文字與繁中皆可讀。不得依靠 hover、JS、可編 editor、未載入 CSS 或自動摺疊而藏掉必要內容；在 App 畫面可見不等於下載檔已驗。
5. **表示法與原件：**匯出前後 JD／來源權威內容不變，不帶 diff 刪文、pending、selection、session undo。支援的格式按 profile 保留；空 leaf marks 即使沒有可見字，也不能由匯出反向清掉原值。不宣稱 HTML／DOCX 是完整 Plate round-trip 備份；比較／歷史仍由 App 已保存版本承接。

讀不到承諾的保存版／問答，或正式 renderer 會漏必要內容，就停止該交付、回報具體位置；不靠 LLM 重新撰寫、通用 converter／模板引擎或另一個來源庫補洞。若 A 的離線閱讀不足以支援真人實際工作，或 Owner 明定需外部可編文書檔，再以 B 的明確映射／驗收代價改選，不重開 Plate 或工作稿政策。

**交接結論：**將 A、明示版本與問答範圍、dirty／busy 行為及缺件規則納入 ADR／施工計畫一次評審；格式及可見控制仍屬推薦。此附件完成設計輸入，不代表匯出、完整 S4／S5 或專業 JD 品質已驗收。
