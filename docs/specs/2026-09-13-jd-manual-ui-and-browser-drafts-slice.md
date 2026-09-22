# JD 六章手動管理、自動保存與瀏覽器恢復：RS-3 第一段

日期：2026-09-13；Topic：JD-R002；隔離實作 `experiments/jd-relational-app`。本稿只保存這次結果與後續工作，格式、資料庫及產品語意仍由[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)路由至責任文件。ADR0075 仍 Proposed，production ADR0060 不變；0 次產品模型呼叫，未使用真實訪談資料。

## 1. 已完成的效果

已有實際 React／Next／MUI 畫面，從空白文件管理六章 JD。職責、任務、多筆成果、多筆要求、知識技能定義及多對多引用，由原共用 Python 業務服務寫入 PostgreSQL；畫面不把整份文章 JSON 當成關聯資料的替代品。欄位文字可換行，不要求員工排版。

一般文字修改自動保存；新增／完整修訂任務、移動、排序及刪除以既有具名命令保存。成果與要求保持獨立子清單；刪職責保留任務，可在同次操作補入必要適用範圍。文件建立／更名／封存恢復使用同一目錄 API。歷史及實際前後差異在同畫面查看，沒有逐筆接受 AI 建議流程。

瀏覽器用 IndexedDB 保存未完成文字、整份管理表單及原保存請求；恢復先比较，不自動送出失去基準的候選。原結果未知時保留同一 operation，只明示查回或繼續原操作。同來源第二分頁開同份 JD 時唯讀。前端只協調輸入與顯示；正式資料、業務約束、版本與操作結果仍由後端負責。

**範圍限制：**畫面上的顧問區目前明示 AI 尚在接合。沒有自然訪談模型證據、來源原文查閱、選區請 AI 更正、歷史還原／整輪撤回及日常圖形啟停。尚未通過完整 RS-3 或成品門檻，不能把本稿解讀為 AI 顧問已交付。

## 2. 官方依據與本案接合

依據於本日核對；具體套件版本、正式／預覽狀態、免費開源授權及限制沿 [React／Next／MUI 前置](evidence/2026-09-13-jd-react-ui-preflight.md)、[瀏覽器候選前置](evidence/2026-09-13-jd-browser-draft-preflight.md)、[API 映射](evidence/2026-09-13-jd-ui-api-mapping.md)。框架保持可替換，不重新以品牌數量判定方案。

| 官方公開原則 | 本案的具體接合與界線 |
|---|---|
| [AWS Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)：多種 client 透過接點使用 domain，技術可替換，也有增加 adapter 的成本。 | ManualService／模型 transport 最終進同一候選與保存規則。Web 只讀 schema、組合具名命令和協調瀏覽器輸入，不重算資料關係約束。此處不引入 AWS 雲端服务，也不宣稱 AWS 指定本案十三表或八個工具。 |
| [AWS 安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)：呼叫者提供意圖身分、同身分重試保持原效果、辨識同 key 異意圖與晚到請求。 | 在網路前保存原 request；未知結果不換 key，舊回覆只清除其涵蓋的輸入世代。原 key／結果交易由既有 Python service 保證；瀏覽器格式是本案映射，不是跨供應商統一協定。 |
| [React 穩定 key](https://react.dev/learn/rendering-lists)、[保留元件狀態](https://react.dev/learn/preserving-and-resetting-state)：同一項目的穩定身分及祖先位置影響輸入狀態。 | Read v2 提供 DB item UUID 與六章 section key；元件及祖先容器用穩定身分。Opaque ref 仍檢查文件、版本與用途，不能用 UUID 取代可寫定位。 |
| idb／IndexedDB 短交易、Web Locks、HTTP ETag／CAS、JSON Schema 2020-12。 | 原生短交易等待 tx.done，網路不跨 IDB transaction；同文件 Web Lock 不使用 steal。Ajv 驗既有七份 schema，不修剪／補值／轉型。新建結果查回與目錄版本檢查接原服務。細節與官方來源在上述前置。 |

本次沒有變更 OpenAI／Anthropic 的模型工具契約；其既有官方核對與離線 SDK 驗證仍有效。不能以 UI 通過推論 provider 接受請求或模型會正確自主使用。

## 3. 文件與實作變更

- `jd-read.schema.json` 的 ReadPage／ChangeReadPage format 升至 2，新增既有 `section_key`／`item_id`，Python／TS 由標準 generator 重生；簽章 envelope、cursor format 1 及 snapshot v3 不變，沒有 DB migration。
- `web/src/lib/api.ts` 嚴格驗回應、同版完整分頁、狀態與媒體格式；逾時不自動重試。`view.ts` 為只讀六章投影，`item-form.ts` 對應既有有限業務命令。
- `drafts.ts` 的候選格式 1 綁 API origin／dataset／document，短交易核對擁有者與原 submission；本地输入 B 不被 A 的晚到 ACK 清掉。未保存的 RAM 輸入也留在比較區。
- `session.ts` 在原結果確認後，透過歷史讀取將 observation ref 正規化成歷史 ref，再判斷目前稿是否是自己的已保存結果；前端不解碼 token。部分表單內新增共用定義的 ACK 與原 submission 清理在同次 IDB 交易完成，不留下可重複新增的候選。
- `Workspace`、`DocumentWorkspace`、`JdEditor`、`ItemDialog` 與 `HistoryPanel` 提供管理、候選處理及歷史。未保存時保護切換；封存不重新掛載編輯 Session；另一份建立成功不強制切走正在編輯的文件。

## 4. 實際驗證

測試資料全部合成；PG 18.6 位於 `127.0.0.1:55436`，專用資料庫 `caliburn_jd_setup_test_d5261157fbcc42897a9f26ef28dba317`。API `8767` 使用真 DPAPI 配置與獨立 Windows native host，Web `3002`；沒有假 writer、正式資料庫或模型 provider。暫存配置留在該 fixture，不提交配置檔。

| 層級 | 已實際觀察的結果 |
|---|---|
| Python 全組 | **1540 PASS／180 PG SKIP**，24.19 秒；1 項第三方 Starlette AnyIO alias deprecation。這不是全組真 PG 通過。 |
| Read v2 受影響組 | 105 PASS；真 PG 身分／重開 2 PASS，另有原 receipt 經 history 正規化的 committed／no-change 2 PASS。各組可能重疊，不累加當唯一總數。 |
| Web 純測 | **99 PASS**：API 38、draft 18、form 16、view 14、session 13。不是 TSX、實體 IME 或真人驗收。 |
| 生成、型別與 build | generator `--check`、完整 Web 型別檢查與最終 production build **PASS**。Next 16.3.5 編譯 5.2 秒、TypeScript 568 毫秒；動態根頁正確。 |
| 真瀏覽器建立／文字 | 新建文件，職稱及多行職務目的保存後重開讀回；任務改名後保留同一 UUID，保存後輸入焦點仍在原欄位。 |
| 真瀏覽器關係 | 建立 1 職責、1 任務、2 成果、1 要求與共用知識；任務表單內先新增知識仍保留未提交內容。再建立名稱未知的任務並引用同一知識，顯示使用於 2 任務。 |
| 真瀏覽器候選 | 未完成任務的多欄／勾選引用，關頁重開後明示找回；繼續後內容與引用完整，不自動提交。另一分頁開同 JD 唯讀。 |
| 真瀏覽器移動／刪除 | 未命名任務移入職責，同 UUID／內容／引用保留。刪職責時同次補兩任務範圍；2 任務移為未分組，成果、要求、2 筆共用引用保留。 |
| 真瀏覽器封存／恢復 | 封存後全文唯讀；恢復後續改職稱為「系統維護工程專員」並自動保存，任務與關係保持。 |
| 真瀏覽器歷史／尺寸 | 歷史列實際版本及任務改名前後。一般窄畫面堆疊；1440 桌面左右同頁，DOM client／scroll width 均 1425，無水平溢出；測後恢復原 viewport。 |
| 獨立 DB 快照 | 原 head 7 與[最終 head 11](evidence/jd-relational-ui/browser-db-final-review.json)唯讀核對 **PASS**：11 版本／10 committed 操作，current rows／snapshot／digest／原回執一致；0 職責、2 任務、2 成果、1 要求、1 知識及 2 引用。metadata version 3／archived=false，封存恢復未增加正文版本。中途封存狀態仍以瀏覽器觀察為證。 |

固定 Web 純測涵蓋 A 送出後續打 B、晚到舊 refresh、確定失敗／未知、RAM 保存失敗的候選保留、部分恢復及 blocked 出口。尚未用真瀏覽器注入配額／斷線／回覆遺失；不能將純測敘述成原生故障全部通過。

## 5. 首敗與獨立審查

本次保留已發現缺口及最終結論，不只列綠燈：

1. Read v1 沒有穩定顯示身分，新增反例失敗後升 v2；不用可變 ref 當 React key。
2. API 初期 schema root／錯誤投影／分頁測試失敗，修到 37 項；真瀏覽器再發現 native fetch 接點問題。新增 receiver 回歸，以記憶體複本還原舊呼叫確實失敗，現版 API 38 項通過。
3. 首次自動保存把 observation ref 與 history ref 字串直接相比，误報外部更改；改由原結果的歷史讀取核對，有真 PG 反例及瀏覽器續改證據。
4. 表單定位／欄位假設、祖先 key、舊讀取晚回覆、RAM 比較遺漏、建立／封存切走候選、来源差異及 blocked 出口，經獨立審查與有限修正。Session 晚讀反例由 1 FAIL／12 PASS 轉 13 PASS。
5. Node worker 與 Next TypeScript 子程序在 sandbox 遇到 EPERM。純測用官方 `--test-isolation=none`；build 在允許的原生程序環境執行，保留型別檢查，不改成假通過。
6. 結果文件獨立審查另發現 README 下半部仍列畫面／autosave 未完成且指向舊結果；已同步四處並窄核通過，避免下一施工重做已完成接點。

獨立審查由不同代理分別核對 draft 交易、UI／Session 交接、API／read v2 與 AWS 原則映射；前次 4 項 P2 及後續兩個接合點已閉合，最後有界只讀審查未發現新增可重現 P1／P2。這是限定檔案與已觀察案例的結論，不是證明沒有任何錯誤。

## 6. 重現、保存與下一步

操作員重現入口見 [Web README](../../experiments/jd-relational-app/web/README.md)及[本機設定](2026-09-13-jd-managed-configuration-slice.md)。原 CLI 使用同一受管理設定初始化／開啟；沒有為瀏覽器加入任意 DSN 路由。合成驗收先建立上述唯一空 DB，prepare／initialize／serve 是分開程序；瀏覽器按第 4 節順序操作，最後獨立唯讀核對。

本次本機原始紀錄位於 `S:/caliburn/.research-tmp/jd-ui-d5261157fbcc42897a9f26ef28dba317/`；[保存的證據](evidence/jd-relational-ui/)只包含合成核對 JSON 與必要測試紀錄，沒有 DPAPI、帳密或環境內容。瀏覽器步驟為研究者使用 CUA 操作的觀察紀錄，未提供自動重播測試，不冒稱真人操作。

驗收結束已停止經身分核對的自有 Next 程序，API 依測試控制正常關閉，`closed=true`／`saver_connection_closed=true` 且原父子 PID 已退出。合成資料庫與候選／歷史證據保留；不是關閉或清空其他服務。

**唯一下一施工：**完成 RS-3 其餘必要接點與故障驗證，優先原保存結果遺失／重新開頁、人工更改通知與 AI 回合交接。歷史來源原文、選區、還原／整輪 JD 撤回沿既定契約補齊；正式訪談與 Memory 需接獲採用的正式責任，再做零付費固定輸出驗證。實體 IME、未調整職位自然模型與真人操作仍分開驗收；有費用的模型測試另依授權範圍，不先執行。Excel 繼續延後。
