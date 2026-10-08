# 架構圖示與文件層次研究（2026-10-08）

Caliburn 的圖面應先區分結構、流程、時序、狀態、資料關聯及部署，再用各圖種的符號表達責任。主要審查目標是讓讀者辨認「有哪些東西、誰負責、關係往哪裡、何時成立」，而不是要求每張圖換成不同形狀，或把所有細節塞進一張總圖。

本研究供本輪架構與報告文件修訂使用，記錄官方依據及本案建議，不另維護產品契約。採用後的寫作規則由[文件與圖面規範](../../implementation/documentation-standard.md)維護；產品現況仍沿[目前決策](../../current-decisions.md)及各責任文件核對。全部外部來源於 **2026-10-08** 查閱。

## 1. 來源的權威與適用範圍

| 來源 | 本次可確認的內容 | 使用界線 |
|---|---|---|
| [C4 diagrams](https://c4model.com/diagrams)、[notation](https://c4model.com/diagrams/notation)、[checklist](https://c4model.com/diagrams/checklist) | 分層靜態視角、圖名與範圍、元素責任及關係標籤的建議 | C4 是建模方法，沒有強制幾何形狀；不要求每個系統畫滿四層 |
| [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/About-UML)及其[規範 PDF](https://www.omg.org/spec/UML/2.5.1/PDF) | 本次直接取得官方 PDF，核對 dependency、activity、sequence、instance specification 及部分 state notation | UML 的規範適用於聲稱使用 UML 的記號；不能自動套到所有 Mermaid 圖 |
| [ISO 5807:1985](https://www.iso.org/standard/11955.html)及 [SIST 官方公開預覽](https://preview.sist.si/sist-preview/11955/1b7dd254a2a54fd7a89d616dc0570e18/ISO-5807-1985.pdf) | 已實讀預覽正文 pp.1–8，核對圖種、基本／專用符號、處理、子流程、決策及線條；相關條款見 §3.2 | 未取得完整標準；預覽未含 §9.4 起訖／連接符號及 §10 製圖慣例，不宣稱全標準合規 |
| Microsoft Visio 官方 [Basic Flowchart](https://support.microsoft.com/en-us/visio/create-a-basic-flowchart-in-visio)、[Crow’s Foot](https://support.microsoft.com/en-us/visio/create-a-diagram-with-crow-s-foot-database-notation)、[Data Flow Diagram](https://support.microsoft.com/en-us/visio/create-a-data-flow-diagram-in-visio) | 流程形狀用途、鳥足端點讀法，以及 DFD 的處理／儲存／外部來源與目的地區分 | 官方製圖指引，不是 ISO 或 OMG 規範；不以任意方框加箭頭冒充已採用某種正式記法 |
| Mermaid 官方 [flowchart](https://mermaid.js.org/syntax/flowchart.html)、[sequence](https://mermaid.js.org/syntax/sequenceDiagram.html)、[state](https://mermaid.js.org/syntax/stateDiagram.html)、[ER](https://mermaid.js.org/syntax/entityRelationshipDiagram.html)及 §3.2 所列 `develop` 原碼 | 各圖種的語法、形狀、線條及目前原碼的幾何差異 | 工具支援不等於 UML／ISO 合規；`develop` 原碼不代替固定版渲染驗證 |
| arc42 [building block](https://docs.arc42.org/section-5/)、[runtime](https://docs.arc42.org/section-6/)、[deployment](https://docs.arc42.org/section-7/) | 靜態分解、代表性互動及基礎設施映射三種互補視角 | 文件組織方法，沒有要求本案照抄章名、目錄或固定圖數 |

查核時分開三件事：**標準所定義的語意**、**工具提供的表示法**、**Caliburn 為一致閱讀選用的慣例**。例如「本案流程分支用菱形」可以是明確的維護規則，但不能寫成「ISO 強制每個可能失敗的動作後都接菱形」。

## 2. 先決定讀者要回答的問題

| 讀者的問題 | 適用視角 | 圖中節點與線的意義 |
|---|---|---|
| 誰使用產品，與哪些外部系統互動？ | 系統情境 | 人、產品、外部系統；有用途的互動關係 |
| 哪些應用程式與資料儲存構成產品？ | C4 容器 | 應用程式／資料儲存；呼叫或資料交換及協定 |
| 後端內部分工及依賴是什麼？ | 元件／邏輯結構 | 模組責任；明確定義的依賴或協作 |
| 在什麼條件下走哪條路？ | 流程／活動 | 動作及分支；控制先後 |
| 誰先呼叫誰，何時回覆或提交？ | 時序 | 參與者／生命線；依時間排列的訊息 |
| 某個工作目前能處於哪些狀態？ | 狀態 | 狀態及其轉移；觸發事件和必要條件 |
| 資料如何識別、選用及關聯？ | ER | 實體／資料表；識別關係及兩端基數 |
| 一個具體快照、修訂或引用例子有哪些實例連結？ | UML 實例視角 | 具名 instance specification 及實例間的 link；不由個案推定基數 |
| 哪些實例執行在哪個環境？ | 部署 | 主機、執行環境及程式實例；通訊關係 |

C4 的 container 指應用程式或資料儲存的執行邊界，不等於 Docker container；component 是容器內封裝相關責任的單位，不是獨立部署服務。[C4 container](https://c4model.com/abstractions/container)、[component](https://c4model.com/abstractions/component)

本案建議以系統／容器總覽建立全貌，再對有閱讀價值的責任放大。角色、Python 模組、Graph 節點、資料表及部署程序是不同概念；若一張圖需要同時出現，應清楚標出種類與邊界。不能因 A、B1、B2 職責不同，就將它們畫成三個實際存在的獨立服務。

## 3. 形狀與箭頭要隨圖種解讀

### 3.1 結構圖：關係用途比外觀更重要

C4 建議各關係單向、有用途標籤，容器間再標示通訊技術或協定；元素標示種類、責任及適用技術。圖需有範圍與圖例，但 C4 不指定方框、顏色或箭頭外觀。[C4 notation](https://c4model.com/diagrams/notation)

本案採用方式：

- 將無標籤雙向線拆成可解讀的關係。若只描述「API 呼叫資料庫讀寫」，單向線由 API 指向資料庫，圖例說明是呼叫方向；不因資料會回傳，就自動畫成雙向依賴。
- 若圖的問題是資料流，線應跟隨資料去向，並命名資料。若問題是靜態依賴，則線由依賴方指向提供方。兩者不可在同一組無圖例箭頭中互換。
- 同一對元素確有兩種方向不同的關係時，各自命名；不要用一條「互動」線隱藏不同責任。

UML dependency 另有正式記號：虛線箭頭由 client 指向 supplier。這與 C4 的自訂實線關係是不同表示法，不能把所有結構圖的實線一律判為錯誤。[UML 2.5.1 §7.7.4，正文 p.39／PDF p.81](https://www.omg.org/spec/UML/2.5.1/PDF)

本輪比較靜態 import 圖的兩種做法：UML Package Dependency 適合要精確建模 package 與其依賴時使用，元素和關係都須採該記法，不能只將 Mermaid 流程線換成虛線就稱符合 UML。現有圖則按共同責任聚合 Python 模組，有些群組跨目錄，重點是允許依賴方向；採 C4 notation 的一般標示建議即可保留此用途。圖名限定為「程式模組依賴視角」，各節點明示 Python 模組群組及責任，每條單向線標明匯入用途；這是借用官方可讀性原則，不宣稱為 C4 Component 層級，也不新增通用概念圖規範。[C4 notation](https://c4model.com/diagrams/notation)

### 3.2 流程圖：先分操作、資料與控制邊界

**符號依節點表示的事物選擇，不能只按「讀、寫、保存、返回」等動詞分類。** ISO 5807 §3.1–3.2 區分基本與專用符號：是否需要表明具體處理性質或資料媒介，才是選擇依據。§5 的程式流程圖描述操作順序、線表示控制流；§9.3.1 的一般線則可表示資料或控制，因此圖名與圖例須先限定線的用途。[SIST 預覽，正文 pp.1–2、6／PDF pp.5–6、10](https://preview.sist.si/sist-preview/11955/1b7dd254a2a54fd7a89d616dc0570e18/ISO-5807-1985.pdf)

已實讀的 ISO 符號條款如下；最後一欄是本案應用判準：

| 符號與條款 | 標準所述語意 | 本案判準 |
|---|---|---|
| Process，§9.2.1 | 處理功能，可是一個或一組操作，改變資訊的值、形式、位置或決定流向 | 「官方 saver 保存」可用處理框；不能因一框有多個操作就宣稱違規 |
| Predefined process，§9.2.2.1 | 已在別處定義其操作／步驟的具名程序 | 高層圖可用雙側線框引用已展開的子流程，並指向具體章節；不以雙線框泛稱所有 SDK 呼叫 |
| Decision，§9.2.2.4 | 單一入口，依框內條件選出唯一出口 | 菱形寫判斷，分支線寫可區分的結果；不將多條出口當成並行 |
| Data／Stored data，§9.1.1.1–2 | 資料／適合處理的已存資料，媒介未指定 | 資料實體與保存動作分開；不把所有資料存取都畫成資料庫圓柱 |

上述條款見 [SIST 預覽，正文 pp.2–4／PDF pp.6–8](https://preview.sist.si/sist-preview/11955/1b7dd254a2a54fd7a89d616dc0570e18/ISO-5807-1985.pdf)。Microsoft Basic Flowchart 另將 Data 用於資訊進入或離開流程、Start/End 用於局部流程起訖、Subprocess 用於別處定義的步驟群；On-page reference 小圓表示同圖他處的接續位置。這些是官方製圖指引，不冒充本輪未讀到的 ISO §9.4 條文。[Visio Basic Flowchart](https://support.microsoft.com/en-us/visio/create-a-basic-flowchart-in-visio)

Mermaid 對應語法為 `A[處理]`、`D{判斷}`、`P[[具名子流程]]`、`S([局部起訖])`、`I[/輸入／輸出/]`、`DB[(資料庫)]`。一般圓角矩形 `A(...)` 與起訖膠囊 `A([...])` 是不同形狀：官方 `develop` 的 [shapes.ts](https://github.com/mermaid-js/mermaid/blob/develop/packages/mermaid/src/rendering-util/rendering-elements/shapes.ts) 分別命名為 Event 與 Terminal Point；[roundedRect.ts](https://github.com/mermaid-js/mermaid/blob/develop/packages/mermaid/src/rendering-util/rendering-elements/shapes/roundedRect.ts) 使用一般圓角半徑，[stadium.ts](https://github.com/mermaid-js/mermaid/blob/develop/packages/mermaid/src/rendering-util/rendering-elements/shapes/stadium.ts) 使用高度一半的端部圓弧半徑。這是官方原碼核對，**不是鎖定版本的渲染驗證**；正式圖仍須用實際固定版工具驗圖。[Mermaid flowchart](https://mermaid.js.org/syntax/flowchart.html)

本案以原生接續文件為例的取捨：

- 「呼叫 SDK、保存結果、結算」可抽象為操作群；若圖要解釋恢復交界，應展開交界，或用具名子流程連到細圖。這是閱讀目的要求，不是 ISO 禁止多動作矩形。
- 「保存 R」是操作；「checkpoint 中的 R」是已存資料；「向呼叫方輸出 R」是資料交接。控制圖以處理框表達保存即可，只有要畫資料實體時才另加儲存符號。
- 「返回歷史」可強調資料輸出；「輪前準備結束、交回呼叫方」可作子流程終點。局部起訖不宣稱整個 Turn 或 Memory 批次已正式提交。
- 執行 interrupt、可靠保存停妥、確認 PAUSED 與等待 resume 分別是動作及等待。跨暫停／續作的細圖應分清這些階段；Mermaid 的 `delay` 可表示等待，但本輪未確認它是 ISO 5807 規定。只畫單次呼叫時，回傳暫停結果可以是局部終點。
- 只畫正常路徑可明示省略異常；圖要比較成功／失敗時才展開結果判斷。選擇與並行分開，不從處理框多條出邊推定並行。

UML activity 另有 control flow、object flow、decision／merge 與 fork／join 的正式語意；時序圖的 `par` 又是組合片段，不能把一般流程圖混稱 UML activity。本案需表達並行互動時，可選時序圖與 `par`，依 operand 保留各自事件順序。[UML 2.5.1 §15.2.3.3、§15.3.4.2–3、§17.6.3.10](https://www.omg.org/spec/UML/2.5.1/PDF)、[Mermaid parallel](https://mermaid.js.org/syntax/sequenceDiagram.html#parallel)

### 3.3 時序圖：回傳不等於非同步

UML 同步訊息使用實心箭頭，非同步訊息使用開放箭頭；reply 使用虛線，箭頭可開放或實心。因此「虛線＝非同步」及「回傳必須開放箭頭」都不是正確概括。[UML 2.5.1 §17.4.4，正文 p.577／PDF p.619](https://www.omg.org/spec/UML/2.5.1/PDF)

Mermaid 的 `->>` 是實線帶箭頭、`-->>` 是虛線帶箭頭；`-)` 及 `--)` 是開放非同步箭頭。Mermaid 也提供雙向箭頭語法，工具支援並不代表一條雙向線足以描述一問一答的時間順序。[Mermaid messages](https://mermaid.js.org/syntax/sequenceDiagram.html#messages)

本案採 `->>` 表請求／呼叫、`-->>` 表對應回傳；真正發送後不等待完成的訊息才依語意採開放箭頭。`async def`、`await` 是程式寫法，不足以單獨判定圖上的訊息種類。事件通知、HTTP 接受工作與背景完成應分清，不能把「已接受」畫成「已正式完成」。

條件用 `alt`／`opt`，重複用 `loop`；沒有回傳內容需要說明時，可省略純確認訊息。交易框則只框實際資料庫交易範圍；圖上框住一段互動，不會因此產生原子性。後兩項是本案以產品契約審圖的要求，不是 Mermaid 能替程式保證的效果。

### 3.4 狀態圖：轉移描述狀態機，不代替業務提交

Mermaid `stateDiagram-v2` 提供狀態、附文字的轉移、`[*]` 起訖、choice 及 fork／join。`[*]` 的意義由進出方向決定，描述的是該圖中的起止。[Mermaid state diagrams](https://mermaid.js.org/syntax/stateDiagram.html)

UML 的狀態為圓角矩形；初始 pseudostate 是實心圓，final state 是外圈包實心圓。轉移標籤的文字結構為 `trigger [guard] / effect`，條件不應全寫成事件名。初始轉移通常不加標籤；規範對 ClassifierBehavior 的物件建立事件另有特定例外，不能概括成初始線永遠禁止文字。本案將「新 Turn 已准入」放在狀態圖前置條件，恢復分支則分開核對事件與 `[成立條件]`。[UML 2.5.1 §14.2.4.4，正文 p.319／PDF p.361；§14.2.4.5–6，正文 p.327／PDF p.369；§14.2.4.8，正文 p.331／PDF p.373](https://www.omg.org/spec/UML/2.5.1/PDF)

本案建議節點表示「執行中、暫停、完成」等狀態，操作名稱放在轉移上，並補必要條件。若要比較工作執行狀態與資料正式資格，應分成兩個有關聯的視角；不能以 Graph END 或時序生命線結束推定訪談、JD 或 Memory 已提交。

UML 還區分 internal、local 與 external transition；這些差異有實際語意，不能只為版面好看任意替換。[UML 2.5.1 §14.2.4.9，正文 p.334／PDF p.376](https://www.omg.org/spec/UML/2.5.1/PDF) 本案一般生命週期總覽若不需描述這些細節，可採附圖例的簡化狀態圖，不聲稱完整呈現 UML 狀態機。

### 3.5 ER：識別、基數與必填是不同問題

Mermaid ER 以兩端標記表達零／一／多的基數，以 `--` 表識別關係、`..` 表非識別關係；線的實虛不是可空性。它的說明偏向實體能否獨立存在。[Mermaid cardinality and identification](https://mermaid.js.org/syntax/entityRelationshipDiagram.html#relationship-syntax)

實體資料表視角還應核識別鍵。MySQL Workbench 官方將 identifying 定義為子表無法脫離父表而唯一識別，並以父鍵參與子表主鍵的關係示範實線。[MySQL Workbench relationship tools](https://dev.mysql.com/doc/workbench/en/wb-relationship-tools.html)

Crow’s Foot 的端點讀法可直接核對 Microsoft 官方指引：圈是零、短線是一、鳥足是多；靠近實體的符號表示最大值，內側符號表示最小值。組合為零或一、恰好一、零到多、一到多。PK 是主鍵，FK 是外鍵，UK 是唯一鍵；一個複合主鍵的多個 PK 欄位合起來才構成識別，不表示每欄各自唯一。[Microsoft Crow’s Foot](https://support.microsoft.com/en-us/visio/create-a-diagram-with-crow-s-foot-database-notation)、[Mermaid attribute keys](https://mermaid.js.org/syntax/entityRelationshipDiagram.html#attribute-keys-and-comments)

ER 圖交代實體、關係、鍵及基數；欄位參考表交代型別、可空性、單位、預設與約束。若 ER 只用簡化型別，須明示並連到實際 schema／migration，避免讀者把 `string` 或 `datetime` 當成 PostgreSQL 的精確欄位定義。這是本案維護權責的選擇，不另建立一份需人工同步的完整資料字典。

本案實體 ER 建議明定採鍵識別慣例：父鍵參與子表主鍵時用識別實線，其餘外鍵通常用非識別虛線；概念模型若採生命週期依附定義，另標明，避免兩者混用。例如子表有獨立 UUID 主鍵、父外鍵不可空，仍可用 `FILE ||..o{ TURN : contains` 表示「每個 Turn 屬於一份檔案，一份檔案可有零到多個 Turn」。必填外鍵本身不會讓它變成識別關係。

逐條核對 FK、PK、唯一約束、nullable 及父端是否真的至少有一筆子資料。`NOT NULL` 外鍵約束子列，不保證每個父列都有子列；若最少一筆只由產品流程保證，圖旁說明適用狀態。局部 ER 應列出省略範圍；不把應用程式引用、衍生查詢或資料流直接畫成實體外鍵。

### 3.6 具體資料例子：用 UML 實例記法，不假設 ER 基數

UML 的 InstanceSpecification 用所屬 classifier 的形狀呈現，名稱寫成帶底線的 `instance : Classifier`。分類為 Association 的 InstanceSpecification 表示 link，以實線連接實例；明顯連接實例時，連結名稱不必另加底線。導航箭頭可省略，若畫出就須符合對應 association 的端點導航語意。[UML 2.5.1 §9.8.4，正文 p.128／PDF p.170；實例與 link 範例 Figure 9.30，正文 p.129／PDF p.171](https://www.omg.org/spec/UML/2.5.1/PDF)

報告圖 05 的任務／理解／情境／對話，以及圖 07 的 M1／M2 快照與固定修訂，都是具體合成例子，適合採此實例記法。改成 ER 會將個案改成類型關係，還須另證基數；改叫 C4 也不能把資料實例變成軟體元件。本輪保留各個實例與連結，採矩形、完整加底線的實例名稱與分類，以及具名實線 link，省略導航箭頭。關係標籤寫明「任務引用理解」「快照選用情境」等角色，不把無箭頭解釋成雙向業務引用。

合成實例名稱可含括號提示，例如 `S1-r1（每日整理） : 工作情境修訂`；括號是圖中辨識名稱的一部分，不是另外發明的資料欄位或屬性槽。顏色只輔助辨認類型，類型名稱本身必須可讀。若未來需要展開 UML slot，則依同一條款使用屬性名稱、等號與值的記法，不把任意文字當成既有 schema。

Mermaid 沒有在本輪使用獨立 object-diagram 語法；以 `flowchart` 作為排版工具，節點使用 `"<u>instance : Classifier</u>"`、連結使用 `---|關係名稱|`。先用兩個實例和一條 link 試畫：Mermaid 12.1.0、`securityLevel: strict` 能保留 `<u>`，SVG 序列化後載為圖片，PNG 中仍可看見底線及無箭頭實線。這項驗證只證明上述記號可正確呈現，不宣稱 Mermaid 全部語法都符合 UML。

## 4. 部署圖應回答實例落在哪裡

C4 deployment 將系統／容器實例映射至一個指定部署環境的主機、虛擬化設施或執行環境，節點可巢狀。arc42 deployment 同樣要求說明基礎設施及軟體構成的映射。[C4 deployment](https://c4model.com/diagrams/deployment)、[arc42 deployment view](https://docs.arc42.org/section-7/)

本案建議將原生本機啟動及 Docker 交付分清，標明主機、瀏覽器、API、資料庫及外部服務所在邊界。需要時再畫選用 RAG；必須清楚標示何者為選配及如何連線。host、Docker container、C4 container、API 內模組不能互為同義詞。圖的環境及接線要沿 runbook、App README 與實際設定查證，不由圖示形狀推導新部署方式。

## 5. 文件清晰度與單一責任來源

[Google Technical Writing：Documents](https://developers.google.com/tech-writing/one/documents)建議先界定讀者與範圍，開頭回答核心問題，再按讀者需要安排內容；[大型文件組織](https://developers.google.com/tech-writing/two/large-docs)則說明可用階層、導航與漸進揭露安排深度。這支持簡明入口及可逐層深入，不要求所有文件都縮成一頁。

[Diátaxis explanation](https://diataxis.fr/explanation/)著重原因、脈絡、替代方案與理解；[reference](https://diataxis.fr/reference/)則供讀者準確查閱。據此，本案總覽交代產品與主要分工，設計取捨交代理由，契約維護精確規則，runbook 說明操作；不在每個入口重複完整契約。

arc42 building block 以階層展開靜態責任，runtime 選擇具有架構意義的正常、異常及操作情境。[Building block view](https://docs.arc42.org/section-5/)、[runtime view](https://docs.arc42.org/section-6/) 其作者對重複介面的建議是：高層保留名稱及意義，詳情放在實際負責的層，其他地方引用。[arc42 FAQ C-5-10](https://leanpub.com/read/arc42inpractice/chapter-vii)

本案文件密度審查採以下問題：

1. 開頭能否讓新讀者說出本章解決什麼問題，以及要去哪裡查更深的內容？
2. 總覽是否充斥函式、欄位及歷史日期，使主要責任難以辨認？將細節移回責任章並保留連結。
3. 段落是否同時混入現況、目標及歷史？先標狀態，再留下與本題有關的理由及證據。
4. 圖旁文字是否補充關鍵限制，還是逐字重述所有節點？前者保留，後者刪去重複。
5. 一個契約是否在多處各有可編輯全文？保留責任來源，其他位置用必要摘要及引用；摘要仍須準確。

依使用者同日指定，架構與實作圖源獨立存於 `docs/diagrams/`，正文引用生成圖片並附圖源連結；每圖仍只有一份可編輯來源。這是本案降低漂移的維護選擇，不是 C4 或 UML 規定的儲存格式。也不採固定字數或節點上限作為合格門檻；若標籤擁擠、跨線遮擋或需要大量旁白才能判讀，就拆視角、縮短標籤並把細節移到正文。arc42 亦建議保留少量重要執行情境，其示例數量是經驗建議，不能升格為每個專案的硬性上限。[arc42 runtime scenarios](https://docs.arc42.org/tips/6-2/)

## 6. 本輪可執行的審查與驗證

| 檢查層 | 應有證據 | 不足以通過的證據 |
|---|---|---|
| 來源與狀態 | 圖種、範圍、現行／目標／候選／歷史，以及責任正文一致 | 檔名很新，或舊計畫曾寫完成 |
| 元素 | 每個節點的種類、責任及邊界可辨認 | 全用漂亮圖示，但模組與程序混在一起 |
| 關係 | 逐條知道方向、用途及線型意義；跨程序標協定 | Mermaid 成功解析 |
| 行為 | 分支、回傳、並行、恢復及提交與情境契約一致 | 所有動作都補一個菱形 |
| 資料 | 關係回查正式模型／migration，基數及識別線型有依據 | 只看欄位名稱相似 |
| 可讀性 | 以實際輸出尺寸檢查中文、換行、裁切、箭頭與交線 | 只檢查原始 Markdown，或只用縮圖瀏覽 |
| 衍生物 | 可從唯一來源重建，產物與正文相符 | 單獨修 SVG／PNG 後未回寫來源 |

上述是供本輪使用的審查方法，不表示尚未檢查的圖面已符合。純文件修訂以差異、連結、圖的解析／渲染及語意核對為驗證；不因圖已清楚就宣稱部署、真模型、資料競爭或完整產品品質已通過。

## 7. 本次限制與決策去向

- ISO 5807 已由 SIST 官方公開預覽實讀正文 pp.1–8，§3.2 引用其中核對過的條款。預覽未含 §9.4 起訖／連接符號及 §10 製圖慣例；這些缺口不以其他指引補稱 ISO 要求，也不宣稱全標準合規。
- UML 2.5.1 官方 PDF 已在記憶體中取得並抽取上述段落；本文只摘要與本題直接相關的條文，未作全規範符合性審查。正文頁碼與 PDF 頁碼並列，方便重查。
- Mermaid 線上文件及 `develop` 原碼包含持續變動的語法與實作；本案實際可用語法、幾何及中文排版須以鎖定渲染器驗證，不能由本次原碼閱讀推定固定版已通過。
- 本研究完成的是表示法與文件方法比較。正式採用的局部寫法回到[文件與圖面規範](../../implementation/documentation-standard.md)，具體產品規則仍回到原責任文件，不新增第二套架構 authority。
