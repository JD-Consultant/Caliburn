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
