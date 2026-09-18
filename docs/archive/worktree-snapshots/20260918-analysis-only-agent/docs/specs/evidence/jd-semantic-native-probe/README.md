# F03：JD v2 語意分組與引用的有限原生驗證

2026-09-10；JD-R002/C01。這是 root 確认的有界研究，0 付費、0 DB、0 production；只在本目錄新增材料，不改 v1／F02 封存，不安装套件或執行模型。先寫本 README 再生成 fixture／執行原生驗證。

## 固定候選與責任

- `jd_task.children = (body | jd_outcomes | jd_requirements)+`，至少一個 body、恰一成果組、恰一要求組；群組僅 Task 直屬且各含 `body+`。未知群組以空 `p` 承載，不造內容；兩組不合併、不配對。
- `jd_knowledge`／`jd_skill` 是普通 block 完整項目，各含 `body+`；只准在對應 knowledge／skills section 直屬。不新增 O／P item、scope、關係繼承或通用圖引擎。
- Task 的 `knowledge_ids`／`skill_ids` 可省略或為有序無重複陣列；同候選內須指向唯一、正確種類的 item。來源 `source_refs` 不混用。
- 新建內容不含原生 IDs／links；原生配 ID 後再讀取、設定 links。本 probe 只證原生層，沒有實作 HTTP、模型 issued handles、首建工具或 DB 兩次保存流程。
- 拆掉 Task 會使兩組直接出現在其父層：單獨 unwrap 必須被 App grammar 拒絕。只有明示同批先 unwrap 兩組、再 unwrap Task，最終合法才可發布。刪單一群組亦須同批補完整群組或刪 Task；清空群組內容則保留空 paragraph。

使用既有 `.research-tmp/jd-editor-official-profile-probe` 固定安裝：Node 22.12.0、platejs／core53.3.11、basic-nodes53.0.0、list-classic53.0.0、table53.0.9、diff53.0.0、React／React DOM19.2.4、@platejs/slate53.3.10、slate0.126.2。NodeId=`reuseId:true,initialValueIds:'always'`，預設 nanoid，不重置計數。四種新節點只 `isElement:true`，無自訂 normalizer、history、diff、codec 或 ID 引擎；官方 basic/list/table 原生 normalization 保留。

## 固定 fixture 與四組判準

來源為 F02 第二輪已保存 canonical 全 r2：`../jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/F02-A-canonical-input.json`。明列 Task／list item ID 分類，不用標籤 prefix 猜內容；保留全部文字、Text marks 與可沿用正文 ID／source refs。Task 2／4／7 沒有獨立成果清單，新增空成果組。K／S 表格依固定 row 對應轉成完整 block items，保留名稱及用途原段落；表頭原文字保留，退役的 table／row／cell 包裹 ID 列於 mapping，不假稱排版不變或通用 v1 migration。

對 Task 4／7／8 的幾條 links 是本次明列合成測試關係，並非聲稱原 r2 訪談已逐條核准連線。原 r2 文本與既有合成 `source_refs` 不改寫。

1. **F03-A：**映射後全文、所有 Text leaf 與原來源保留；恰兩組、完整 K／S 與無 links／空白 Task 均成立。官方 editor normalize 後保存普通 JSON；另一 Node process 新 editor／normalize 與保存值全等。
2. **F03-B：**原生插入無 IDs／links 的 K、S、Task，讀出实际新 ID 再 `setNodes` 建 links；原生續改一項要求及共用 K 正文。比較真實全文與未指定內容；新程序重開 refs／正文相等。沒有模擬模型或宣布工具首建已通過。
3. **F03-C：**只複製 Task 時全部新 Element ID、保留共享 links；另明列複製 Task＋一 K＋一 S，先保存原生未重映射結果，再用本 fixture 明列映射更新複本 links，原引用者不轉向。移動 Task 8 後完整 subtree／條件／links 保留；普通 JSON 新程序重開全等。映射只服務固定 fixture，不提供通用複製／relation engine。
4. **F03-D：**觀察單 unwrap Task、單刪群組、刪被引用 K 的原生結果，明確指出原生未替 App 阻擋；固定 grammar／端點斷言辨識非法候選。另驗同批 unwrap 兩組再 Task 全文保留、清空群組留空 p、明示解除所有相關 links 後刪 K 的最終合法候選。負例不是宣稱正式 App validator 已實作。

每組保留 before／after、原生 operations、失敗與斷言。`onChange` 同步 clone operations；候選使用 `withoutNormalizing` 批次，觀察邊界 force normalize。不得先修 fixture／normalizer 以掩蓋首次失敗。接法錯誤最多一輪診斷修正且保留首輪 source／結果；內容或原生反例如實 FAIL，不擴寫引擎。

## 執行與未覆蓋

執行入口將為 `node prepare-fixture.mjs`、`node probe.mjs`；兩者僅寫本目錄，probe 每輪另建時間目錄。舊 probe 不重跑。依賴由本目錄 `engine.mjs` 的明確 createRequire anchor 解析，不把 current 網站 API 當固定版本。

未覆蓋：DOM／IME／鍵盤跨群組、可編／diff renderer、新 wire schema／全 profile validator、真模型語意或 issued refs、Python／PG／交易／保存回執、跨文件來源搬移、自動 migration、任意複製範圍。原生 NodeId 不驗 K／S 存在性／種類，也不替自訂 ID 陣列重映射。完成四組即停止；結果僅支持所列原生結構與普通 JSON／新程序證據，不代表 Task 1 或新 v2 整合已完成。

固定原始碼與授權沿 [F02 lock](../jd-official-profile-probe/package-lock.json)、[F02 inventory](../jd-official-profile-probe/license-inventory.json)及既有實裝 LICENSE；不重新採用付費插件。實際 resolved 版本、hash、命令與結果於執行後補錄。

## 實際結果（已停止原生驗證）

| 輪次 | 固定位置 | 結果與判讀 |
|---|---|---|
| 首輪 | [2026-09-09T22-37-40-563Z](results/2026-09-09T22-37-40-563Z/summary.json) | 0／4 組完成通過、12 項已執行檢查；四組均在 fresh process 的 `spawnSync` 記錄 `EPERM` 而中止，因此各組後半不是原生 FAIL，而是未執行。A／D 另各有 `map(structuredClone)` 把 index 誤傳成 options 的 harness 錯誤。 |
| 第二輪 | [2026-09-09T22-38-20-172Z](results/2026-09-09T22-38-20-172Z/summary.json) | 4／4 組、21 項檢查通過（A4、B5、C4、D8）。只把 clone 包成 unary function，再由工具核准本機子程序權限執行同一 `probe.mjs`；沒有變更 fixture、probe assertions、原生套件或 normalization。 |

兩輪各有 `executed-*` 原碼與 `run-metadata.json` 輸入雜湊；首輪 process diagnostics、缺少 fresh output 的事實及 exception 均不覆蓋。第二輪有六份成功的 `*-fresh.json`，分別記載另一 PID、新 editor 與全值核對；同一 probe 內的空草稿另外只驗 headless normalization，不冒稱空草稿也另開新程序。時戳為 UTC，以上均是本地 2026-09-10。

| 實測範圍 | 可以支持的结論 | 仍由 App 承擔／未驗 |
|---|---|---|
| A | 四種新普通 Element、八任務恰兩組、K／S 各五個完整 item、空草稿皆能由官方插件組合承載；全 r2 文字／含格式 leaves 與原八個來源節點保存後新程序全等。 | `finiteIssues` 只是本 fixture 新型別／端點斷言，沒有驗完整 v2 schema、所有允許属性、來源合法性或正式 renderer。 |
| B | 可先原生建立無 ID／links 的完整 K、S、Task；讀到原生產生的 ID 後 `setNodes` 寫兩組陣列，續改 K 與要求文字不換 item 身分；真實 `set_node` 陣列可普通 JSON 保存。 | API 發配 ref／先建→讀→設定的模型流程與兩次 PG 保存尚未實作或實測。 |
| C | Task-only 複本全新 Element IDs，原共享 links 保留；複製完整 K／S 後原生不自動重寫 Task 自訂 links。明列固定映射可透過 `setNodes` 只改複本；Task8 原生移動完整 subtree（含條件、IDs、source_refs、links）相等且重開全等。 | 拷貝輸入去 ID 與明列映射是 App fixture 準備，不是新模型 command／通用複製引擎；跨文件、任意選取範圍及來源搬移未驗。 |
| D | 單拆 Task、單刪群組、刪被引用 K 的原生操作都會執行；固定斷言能指出非法候選。明示三次 unwrap、留空 p 清內容、解除全部相關 links 後刪 K 的最終候選可成立。 | 負例 PASS 是觀察原生沒有替 App 擋錯，不能稱正式 validator 已完成。unwrap 只證全文／marks 保留與有限 grammar 成立，**被刪 Task4 wrapper 上的 source_refs 與 K／S links 隨 wrapper 消失，原生不下傳**；正式來源附著／關係處置仍須沿已定 App 契約驗證。 |

### 完整樣稿與 Task8 固定材料

- [fixture.json](fixture.json) SHA-256 `f994045df13fd0095593a3333755df9e411dbc52ddeaeeba9aa276298d19a264`；[fixture-mapping.json](fixture-mapping.json) 明列所有 Task／row 對應及 38 個退役 table／row／cell 包裹。映射前 192、後 190 Elements，完整原文 2,133 UTF-16 code units 未改寫。
- 實際計數見 [fixture-statistics.json](fixture-statistics.json)：6 sections、4 duties、8 tasks、8 outcomes／8 requirements、5 knowledge／5 skill；**1 table**（5 tr、2 th、8 td），17 ul、22 li／22 lic。不能沿用 v1「三張表」作 v2 驗收；K／S 兩張表的名稱、用途與表頭原文字仍在完整 items／body 中，不宣稱同一表格排版。
- [task8-subtree-expected.json](task8-subtree-expected.json) 是原 Task8 完整值；[task8-move-full-expected.json](task8-move-full-expected.json) 是明列「duty-4 → duty-1 最後」的完整 fixture 期望值，供後續 Task1 單獨移動驗收。**這份 full expected 本身未作另一個 standalone 原生 case**；本次實測 C 還先做複製及明列映射，其真實完整結果為 [F03-C.json](results/2026-09-09T22-38-20-172Z/F03-C.json) 的 `after`。不可把兩份不同情境的整份文件直接宣稱相等。

### 重現與封存

實際依序執行（repo 根目錄）：`node docs/specs/evidence/jd-semantic-native-probe/prepare-fixture.mjs`、`node docs/specs/evidence/jd-semantic-native-probe/probe.mjs`；第二條首輪受限後，只作上述 harness 修正與權限重試。`capture-materials.mjs` 僅用 fs／JSON／hash 整理靜態材料，不 import editor 或新增原生 case。該靜態整理器首次把 Task8 的父節點假設成 section-work，防衛條件在寫檔前停止；查固定原 fixture 確認父節點為 duty-4 後修正，原碼另留 `capture-materials-first-attempt.mjs`，不改判原生結果。

[dependency-provenance.json](dependency-provenance.json) 記錄實際 10 個版本、lock、31 份已安裝原始碼與 40 份授權檔的 hash；與 F02 封存均吻合。完整相依 48 項的另外 8 份固定 gitHead 官方授權 fallback 沿 [F02 fallback 來源](../jd-official-profile-probe/licenses/official-fallback-sources.json)，不冒稱 npm 安裝包本來就附檔。核心／basic／list／table、Slate、React 為 MIT；diff 53.0.0 的實際 LICENSE 有 Apache-2.0／MIT 雙授權說明，不能一概寫全包 MIT。本 probe 沒有呼叫 diff。

跨機器重現須保留本 evidence 與 F02 evidence 的相對位置，並在 `.research-tmp/jd-editor-official-profile-probe/` 依已封存 exact package/lock 準備原安裝；本輪沒有安裝。`engine.mjs` 固定 resolve 該目錄，不依賴 root package 或下載最新版本。新生成的 nanoid 不預期跨執行相同；**每次保存值再重開時的完整 IDs／links 相同**已被逐值核對。

`artifact-hashes.json` 覆蓋本目錄材料（自身除外）。收尾只作材料 hash／文档核對，沒有再執行 editor、模型、DB、DOM／IME、production 或先前 probe。
