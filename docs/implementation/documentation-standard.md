# 文件分工、敘述與圖面規範

本頁維護工程文件的寫法，以及各種圖採用的規範來源與檢查方式。系統本身的責任、生命週期及取捨由[架構目錄](../architecture/README.md)與對應契約維護，不能由寫作規範推導新產品行為。

閱讀順序：[維護責任](#1-一個問題一份責任文件) → [篇章與敘述](#2-先說明概念再展開機制) → [圖種與符號](#3-圖面種類與符號) → [搜尋與檢查](#4-維護搜尋與檢查)。

## 1. 一個問題，一份責任文件

架構回答「誰負責、什麼必須成立、為什麼」，實作回答「哪段程式、哪些表與介面、如何落實及測試」。具體文件對照由[架構入口](../architecture/README.md#架構與實作的維護分工)維護。其他層可用一句摘要承接，完整條件只在責任文件修改，避免版本、門檻、狀態機與驗證結果各抄一份。

- 同一責任內的連續步驟放在一起；只有維護原因或讀者任務不同才拆檔，不以行數硬切。
- 拆檔時移動正文並修正相對連結。仍有人引用的舊錨點可留短轉址，不能留第二份完整正文。
- 現行、目標／未實作、候選與歷史就近標示。工程規範不改寫 Accepted ADR 或原始實驗結果。
- 設定值由程式或正式契約管理；測試結論連到受測版本與原件，索引只維護路由。

文件的生命週期依用途處理：現行契約隨行為整合修改；設計提案及研究保留當時條件，頁首指出現行接續位置；Accepted ADR 及凍結實驗原件保留原記錄。不能只在頁尾加「最新補充」，讓已失效與有效規則並列等待讀者自行裁決。現行頁採穩定主題名，研究／提案／實驗／計畫沿日期識別；既有文件不因檔名帶日期就整批封存。

各層 README 提供用途與閱讀去向，不手抄工程進度或實驗數字。施工狀態在計畫，採用狀態在決策入口，測試結果在受測版本的原件；報告可以為不同讀者重述，但須交代日期與範圍。幾句就能說清的必要背景留在本頁，避免把「不雙寫」做成連續跳轉。完整規則、條件與參數仍只有一處維護。

## 2. 先說明概念，再展開機制

每頁先用一小段說明用途、範圍及閱讀入口。長頁提供依問題分組的短導航，先講主要情境，再展開例外；參考表、格式及完整機制留給需要深入的讀者。這採用 [Google 技術寫作](https://developers.google.com/tech-writing/two/large-docs)的漸進揭露，不要求所有文件套同一章節模板。

段落各處理一件事。表格適合並列比較；單格塞進多段流程、限制與歷史時，改成小節或連到負責文件。清單用於步驟及平行條件，不把整頁拆成零碎口號。強調只用在讀者需要留意的界線，不讓每句都加粗。

潤稿保留施事者、條件、範圍、先後、否定及確定程度。不把「已接線」改成「已驗證」，不把「未驗證」改成「不支持」，也不能因精簡而刪除獨有的例外。完成後對照原文確認資訊保留，再檢查標題與連結。

### 2.1 代理工作指引

`AGENTS.md` 的讀者是工程代理。維護時檢查每條指令是否交代適用情境、應採取的行動及判斷標準；專案狀態、封存沿革與詳細契約沿責任文件查閱。指引有變更時同時刪修失效內容，避免歷次對話提醒累積成互相衝突的限制。

截至 2026-10-08，寫法核對以下官方指引，並採用適合本案的部分：

- [OpenAI：AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)說明全域、專案與目錄指引的載入及優先順序。本案根檔維護共同方法，局部規則就近放置；只有需要不同規則時才新增局部指引。
- [OpenAI：GPT-6 提示建議](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)提醒核查 Skills／指引中的衝突，並依工作需求明定自主推進、委派、表達及驗證範圍。本案採用具體工作條件與完成標準，將測試投入對應改動風險。官方說明這些建議主要基於 GPT-6 Astra 的行為觀察，可作為 GPT-6 家族的起點，仍須以所用模型及工作負載驗證。

這些是提示與文件維護依據，不是產品模型選型或效果驗收。修訂後核對責任文件、引用與指令一致性；是否改善代理行為，須另以具體任務觀察，不能由文字整理直接推定。

## 3. 圖面種類與符號

先選圖種，再選符號。每張圖標明圖名、範圍、現行／目標／候選／歷史及必要省略；同類圖使用一致圖例。Mermaid 是繪圖工具，`flowchart` 語法也能畫關係圖，不能單憑語法名稱把其中的方框全解讀成流程步驟。

### 3.1 每種圖依哪一份規範

正式標準、官方方法指引與工具語法分開核對。UML 的訊息與狀態語意以 OMG 為準；C4 是架構描述方法，並未指定固定幾何形狀；Mermaid 決定如何輸入及渲染符號，不能取代前兩者。

| 圖種與用途 | 採用來源 | 必須檢查的符號與語意 |
|---|---|---|
| 系統、容器、元件：誰負責、如何連接 | [C4 notation](https://c4model.com/diagrams/notation)官方指引 | 標出元素種類、責任與適用技術；邊界有名稱。每條線單向、有具體關係名稱，跨程序寫協定。內部元件不能畫成後端之外的獨立服務；不同放大層次須分圖或明示範圍。 |
| 部署：應用實際在哪裡執行 | [C4 deployment](https://c4model.com/diagrams/deployment)官方指引 | 區分部署節點與其內的應用／資料儲存實例。框表示裝置或執行環境，線表示實際連線；不能把邏輯元件、OS 程序與 Docker 容器混為同一層。 |
| 基本流程：操作的先後與分支 | [Microsoft Basic Flowchart](https://support.microsoft.com/en-us/visio/create-a-basic-flowchart-in-visio)官方指引；[ISO 5807 公開預覽](https://preview.sist.si/sist-preview/11955/1b7dd254a2a54fd7a89d616dc0570e18/ISO-5807-1985.pdf)可讀條款交叉核對 | 起訖用終端形；處理用矩形；決策用菱形；資料輸入／輸出用平行四邊形；另處定義的子流程用兩側雙線矩形。箭頭表示控制順序，決策出口寫明互斥條件；分類先看圖的邊界及節點語意。 |
| 時序：誰先呼叫誰、何時返回 | [OMG UML 2.5.1 §17.4.4](https://www.omg.org/spec/UML/2.5.1/PDF)正式標準，印頁 577 | 生命線向下表時間。同步訊息用實心箭頭，非同步用開放箭頭，reply 用虛線；reply 箭頭依標準可開放或實心。回傳應接回原呼叫方，不能藉虛線表示所有通知。 |
| 狀態：一項工作目前可處於什麼狀態 | 同一 UML §14.2.4.4–8，印頁 319、327、331 | 狀態用圓角矩形，initial 用實心圓，final 用外圈包實心圓。轉移標籤區分 `trigger [guard] / effect`，即事件、條件、效果；節點名稱表示狀態。本案省略標準允許的 entry／do／exit 內部行為。 |
| 靜態依賴：哪個程式元素依賴哪個元素 | 同一 UML §7.7.4，印頁 39；本案程式模組圖借用 C4 notation，明示非 C4 層級圖 | UML Dependency 必須是虛線、開放箭頭，由依賴者指向被依賴者，元素也須用對應 UML 記法。借用 C4 notation 時仍須標示種類、責任與有標籤的單向關係；不能把實線流程圖改名就稱 UML 依賴圖。 |
| ER：資料實體、鍵及關聯基數 | [Microsoft Crow’s Foot](https://support.microsoft.com/en-us/visio/create-a-diagram-with-crow-s-foot-database-notation)、[Mermaid ER](https://mermaid.js.org/syntax/entityRelationshipDiagram.html)及 [MySQL 關係指引](https://dev.mysql.com/doc/workbench/en/wb-relationship-tools.html) | 用圈、短線、鳥足表達兩端的最小／最大基數；實線與虛線另表識別／非識別關係。實體 schema 以父鍵是否參與子表主鍵核對識別關係，不能用 `NOT NULL` 代替。 |
| 物件：某個具體例子中的實例與連結 | 同一 UML §9.8.4，印頁 128–129 | 帶底線的 `instance : Classifier` 表示實例；實線 link 連接實例並標明關係。省略導航箭頭時，不能推論業務關係可雙向操作。適合合成快照／修訂示例，與 ER 類型及基數分開。 |

基本流程圖依上述指引畫製，不稱 UML Activity Diagram。ISO 5807 已讀公開預覽中的處理、資料、子流程、初始化、決策及流程線條款；預覽未涵蓋全部符號與連線慣例，因此不標示完整 ISO 合規。具體條款及限制見[研究紀錄](../research/engineering/2026-10-08-architecture-diagram-notation-and-documentation.md#32-流程圖先分操作資料與控制邊界)。

### 3.2 在 Mermaid 中落實並核對

- **基本流程圖**：`([起訖])`、`[處理]`、`{決策}`、`[/資料輸入或輸出/]`、`[[子流程]]`、`{{初始化}}`。起訖不用一般圓角矩形 `(...)` 代替；六角形只標初始化／準備，不因節點名稱有「prepare」就套用。只畫成功路徑時須說明省略範圍；需要並行互動時使用時序圖的 `par`，不從處理框多條出邊推定並行。
- **時序圖**：`->>` 是同步訊息，`-)` 是非同步訊息，`-->>` 是回傳。`alt`、`opt`、`loop`、`par` 分別描述互斥、選擇性執行、重複與並行片段；分支寫明條件。交易註記只包實際短提交，不包完整模型工作。
- **狀態圖**：以 `stateDiagram-v2` 的起訖及狀態符號呈現。進入圖之前已成立的條件放圖說；線上分開寫事件與 `[條件]`。圖中的終態只屬於該狀態機，不能把 Graph END 當成業務正式完成。
- **ER 圖**：`erDiagram` 的線端沒有呼叫方向；須從兩端各讀一次基數，再核對主鍵、外鍵、唯一約束與可空性。局部圖就近標示省略了哪些表、關係或欄位。
- **物件圖**：以矩形與 `<u>instance : Classifier</u>` 呈現帶底線的實例名稱，`---` 畫無導航箭頭的實線 link。Mermaid 的 `flowchart` 此時只負責排版，不把實例當流程動作；須核實際輸出仍保留底線與線型。

流程圖逐節點分類時，先確定它表示**操作、資料、選擇，還是控制進出**：

- 處理可以涵蓋同一目的的一組操作，不是每個矩形只能有一個動詞。若圖要解釋恢復交界，就拆開外送、保存及後續處理，或用具名子流程指向已有定義；不能把數個責任塞在框中，再僅憑外形判定正確。
- 平行四邊形要能說出資料跨哪個邊界，例如 provider 返回、saver 讀寫、子流程輸出。交易核資格並採用位置是業務操作；`checkpoint` 這份已存資料才是儲存實體。不要按「保存」字樣一律改成圓柱，或按「讀取」字樣一律改成 I/O。
- 子流程框必須有名稱及可追讀的位置；圖的抽象分解不等於程式新增 child graph、thread 或服務。局部返回可用終端形，但圖名及圖說要說清結束的是哪一段。
- 菱形保留單一入口；必要的回圈／替代路徑先匯合，再進入判斷。出口應涵蓋圖示範圍且互斥。若判斷之前含遠端查詢或需要可靠保存的計算，先把該操作及保存邊界畫清楚。
- 暫停動作、停妥證據、當次呼叫返回與另一個明確續作入口分開。流程圖不可以一條無條件回線暗示會自動續作；小圓連接點也不表示等待。

ER 的最小圖例（以下列出線右端寫法，左端符號鏡像排列）：

- `o|`：零或一；`||`：恰好一。
- `o{`：零或多；`|{`：一或多。圈表示零，短線表示一，鳥足表示多。
- `--`：識別關係；`..`：非識別關係。例如 `PARENT ||--o{ CHILD : owns` 表示每個 child 有一個 parent，每個 parent 可有零到多個 child，且父鍵參與子表主鍵。
- `PK`：主鍵；同一實體中多欄標為 PK 時共同構成複合主鍵。`FK`：外鍵；`UK`：唯一鍵。複合外鍵或唯一約束的欄位組合須在圖說／欄位表說清，不能讓讀者誤認每欄各自唯一。

ER 圖負責關係、基數與鍵；欄位表補型別、可空性、單位及重要約束。若圖內使用 `string`、`datetime` 等簡化型別，須明示不是 PostgreSQL DDL。完整實體定義由 schema／migration 維護，不再手抄第二份完整資料字典。

### 3.3 圖面交付與維護

布局以主閱讀方向由上而下或由左至右為主；回圈有明確出口，避免交叉線、重疊標籤與只能靠顏色分辨的語意。線是否直角、方框填什麼顏色是排版選擇，不冒稱通用標準。圖大到需縮小文字時，先拆視角或刪去本題無關細節，不為湊滿 C4 四層或錯誤分支而加圖。

受維護文件的圖源獨立存於 `docs/diagrams/<責任目錄>/<文件名>/<圖名>.mmd`，正文嵌入同名 PNG，旁邊附圖源連結；SVG 供放大。每圖只有一份可編輯來源，正文保留適用範圍、圖說及責任契約，不再內嵌另一份 Mermaid。報告重用相同圖片，說明可在正文補充；另有用途的簡化示例須明示省略。輸出的獨立圖片帶圖名、狀態及必要圖例。索引與重繪方式見[圖源目錄](../diagrams/README.md)；報告映射見[報告圖稿](../reports/system-architecture/diagrams/README.md)。

產品截圖與外部素材沿 `assets/` 保存；凍結實驗圖片及歷史原件保留來源位置。它們是證據或素材，不能為統一圖稿路徑改動其原始位元組、雜湊或實驗引用。既有純圖稿搬移時同步更新所有受維護引用與產圖命令，核對節點／連線語意，再移除重複副本。

更新後依序檢查：**語意與正文一致 → Mermaid 解析／渲染 → 中文、裁切、箭線與圖例 → 引用與衍生圖同步**。能渲染不等於符合符號含義，也不代表程式符合圖上的契約。

2026-10-08 核對：[C4 notation](https://c4model.com/diagrams/notation)、Mermaid [流程形狀](https://mermaid.js.org/syntax/flowchart.html#complete-list-of-new-shapes)、[時序訊息](https://mermaid.js.org/syntax/sequenceDiagram.html#messages)、[狀態圖](https://mermaid.js.org/syntax/stateDiagram.html)、[ER 基數與關係](https://mermaid.js.org/syntax/entityRelationshipDiagram.html)。正式圖採穩定基本語法，渲染器版本沿工具鎖定；不為新版外觀使用預覽圖種。

依據：[C4](https://c4model.com/diagrams)按讀者問題逐層放大，且不必畫滿四層；[arc42 building blocks](https://docs.arc42.org/section-5/)描述責任及內部結構，[runtime view](https://docs.arc42.org/section-6/)補代表性互動。這支持多視角，不規定本案目錄名稱。[Microsoft 架構規格](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-design-specification)支持業務目標、功能／非功能選擇、操作與驗證一併說清；[Google 文件工程](https://abseil.io/resources/swe-book/html/ch10.html)支持面向讀者及持續維護。查閱：2026-09-29。

## 4. 維護、搜尋與檢查

每次修改沿受影響責任更新正文，並在同一變更核對上層入口、操作說明與必要圖稿。新增頁須從既有入口可達；改名／拆分須檢查反向引用，保留仍被歷史或固定版本使用的必要錨點。內容不因換目錄而失去限制，也不因研究或工程結案就改稱品質已驗收。

在 repository 根目錄安裝鎖定的 workspace 依賴後，執行：

```powershell
pnpm docs:check
```

[檢查工具](../../scripts/check-docs.mjs)使用 remark 解析 Markdown／GFM，github-slugger 解析標題；核對本機檔案、圖片與跨頁錨點，忽略程式碼示例及外部網址。預設檢查受維護的 docs，包括研究與報告；ADR 原決策、`archive/`、實驗原件及計畫 evidence 不作改寫對象，只檢查它們的維護入口。被引用的本機目標仍會檢查是否存在，不能靠排除來源掩蓋斷鏈。可直接選頁核對：

```powershell
node scripts/check-docs.mjs docs/specs/jd-work-plan.md
```

本地引用檢查接入根 `pnpm check`，隨既有 CI 執行；它不連外網、不呼叫模型，也不聲稱驗過產品行為。生成圖稿另沿圖源索引重繪。自動檢查之外，審查者須確認讀者能從入口找到答案、辨認現行與歷史，並知道修改應落在哪一份正文。

檢查與產圖工具共用[文件範圍及 Markdown 解析](../../scripts/documentation.mjs)，避免一邊排除凍結原件、另一邊卻要求改寫。搬檔時略過工作樹已刪除的來源頁，其他頁仍指向它的引用照常報錯。

日常查現行系統可先限制搜尋範圍：

```powershell
rg -n "關鍵字" docs/architecture docs/specs docs/implementation docs/guides docs/runbook.md
```

查研究再選 `docs/research/`；查原件沿實驗入口；追舊設計沿[歷史取回](../history.md)。不要預設搜尋 `docs/archive/` 或 `source-snapshot`，也不要把這些材料刪除來減少搜尋結果。新執行暫存使用既有 `.tmp/`，不混入正文或凍結快照。

這些安排依 [Diátaxis](https://diataxis.fr/how-to-use-diataxis/)、[Google 文件維護](https://google.github.io/styleguide/docguide/best_practices.html)、[GitLab 目錄與單一來源](https://docs.gitlab.com/development/documentation/site_architecture/folder_structure/)及 [Microsoft ADR](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)作本案取捨；來源限制及盤點見[文件資訊架構研究](../research/engineering/2026-10-08-documentation-information-architecture.md)。檢查工具採 [remark](https://github.com/remarkjs/remark)／[GFM](https://github.com/remarkjs/remark-gfm) 與 [github-slugger](https://github.com/Flet/github-slugger) 的 MIT 授權開發依賴，版本沿 lockfile；停用時可移除文件命令與根開發依賴，不影響產品執行。
