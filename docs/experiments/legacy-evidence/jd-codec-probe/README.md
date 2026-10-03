# JD-R002／C03：SuperJSON 保存待審格式的有限驗證

2026-09-09；Owner 已同意 Plate 免費開源核心作文件底座。本 probe 僅驗既有 R4 `properties:{bold:undefined}` 的保存缺口能否由現成 SuperJSON 解決，不替 Owner 定案保存格式、不改 production／Memory／舊 R01 或 R01-F。

## 固定版本與來源

- 官方 npm registry 於 2026-09-09 核對 latest 正式版 `superjson@2.2.6`，發布時間 `2025-11-27T13:27:45.738Z`，MIT，Node `>=16`。
- npm gitHead `931dccad2ccbb923d8cde95eed59ca41fbd860e1`；官方 repo `https://github.com/blitz-js/superjson`。直接 runtime dependency 為 `copy-anything:^4`，實裝解析版本、LICENSE 及必要遞迴依賴於安裝後另存清單。
- 新目錄只安裝固定 SuperJSON 及其必要依賴，使用 `--ignore-scripts --no-audit --no-fund`；不安裝到 monorepo 或舊 probe。package／lock 與 source／LICENSE／hash 全留本目錄。
- Node `22.12.0`。Plate 套件唯讀借用 `../jd-editor-review-probe/package.json` 解析：`platejs/core@53.3.11`、`@platejs/suggestion@53.2.3`、`@platejs/slate@53.3.10`、slate `0.126.2`、React／React DOM `19.2.4`。借用 lock SHA-256：`dabb5e05ed949d538605f9464839dd88034da97a007214f0c81efedda7444eff`。不修改借用環境。
- 原生 profile：`createSlateEditor`＋`BaseSuggestionPlugin`、`isSuggesting:true`、`currentUserId:'ai'`、Node ID `{reuseId:true,initialValueIds:'always'}`，normalization 維持原生預設。

## 四項固定操作及判準（執行前寫定）

1. **C01：codec 重開後拒絕移除粗體。**全新原生 editor，固定段落「保留必要的完成要求。」且 bold=true；全選後 `tf.removeMark('bold')` 產生完整 pending。以 `SuperJSON.serialize(value)` 取得原生 `{json,meta}` envelope，普通 `JSON.stringify` 寫檔、讀檔 `JSON.parse`、`SuperJSON.deserialize`，再建立全新 editor。要求 pending own-key `bold:undefined` 仍在、完整 value 相等；原生 reject 得到原 bold=true 的乾淨節點。另保留 structuredClone 記憶體控制及普通 JSON 重開控制，後者的原失敗不得改判。不是從已損失 undefined 的舊 JSON 猜回資料。
2. **C02：同一 pending 經 codec 重開後接受。**再從 C01 保存 envelope 建全新 editor；原生 accept 後正文不變、粗體正確移除、無 pending／殘存 suggestion key。
3. **C03：兩獨立 pending 組外保留。**相同 R1 fixture 原生生成月檢 old→new 替換與另處故障段落新增；兩個 ID 保持 pending。完整 value 經 codec JSON 檔重開新 editor，原生 reject 月檢，原文恢復、故障正文及 pending metadata 整個節點相等、交付段不變。
4. **C04：undefined／null／缺 key 與 JSON envelope。**固定值只含 `{unset:undefined, nullable:null, nested:{unset:undefined,nullable:null}}`，檢查序列化 envelope 本身可普通 JSON roundtrip，deserialize 後 own-key／undefined、null 與缺 key 保持區別。沒有額外 sourceRef 或未知型別。

只用現成 `serialize`／`deserialize`，不 registerCustom／自訂 transformer、手寫 metadata、vendor patch、before-image 恢復或自造 codec／group engine。accept／reject 只取原生產生的 ID，包在 `api.suggestion.withoutSuggestions`；原始 memory／raw JSON／codec 三路的完整物件、操作與 raw key 均留存，不能只憑 `nodes()` 回傳空值判 clean。

四項首次結果完整保存，若有失敗如實停，不增加第五項或擴修。普通 JSON 控制重現原 R4 失敗是控制觀察，不改原 R01 的 2 PASS／2 FAIL。未驗 DB／Python 互通、模型、DOM／IME、全部資料型別、跨版本或任意長期 pending；不可從此推成完整保存／審閱系統已驗收。

## 已知取得限制

第一次官方 registry 讀取被預設網路環境拒絕；一次授權讀取成功才固定版本，未無限重試。首次實驗與來源／實裝授權核對結果待下方記錄。

## 首次實測結果：4／4 通過

執行時間 `2026-09-09T15:28:48.357Z`，Node `22.12.0`，**4 PASS／0 FAIL／0 execution error；24 個判斷通過**。四項完成後停止，沒有重跑、擴充第五項、修 vendor 或補自訂轉換。結果保留於 `results/2026-09-09T15-28-48-170Z/`。

| 項目 | 真正執行結果 | 可支持的結論 |
|---|---|---|
| C01，8／8 | 原生重新產生 `properties` 自有 `bold:undefined`。記憶體新 editor 能 reject 恢復粗體；普通 JSON 新 editor 無法恢復，保留差異。SuperJSON envelope 經普通 JSON 檔→deserialize→新 editor，完整 pending value 相等，reject 恢復原粗體，raw suggestion key／flag 全空。 | 現成 SuperJSON 的預設轉換能補此固定 R4 保存情境，不需要自訂 codec；普通 JSON 的原失敗依然成立。 |
| C02，4／4 | 同一 envelope 再建新 editor，accept 後保留全文、正確移除粗體；完整節點等於預期，原生 IDs 與 raw suggestion keys 均空。 | 保存後接受同一待審格式變更也符合本例效果。 |
| C03，6／6 | 相同 R1 fixture 原生重新產生月檢替換與獨立故障新增，codec 重開完整 pending 相等；拒絕月檢後恢復原文、月檢 raw metadata 清空，故障整個 pending 節點及交付段完全不變。 | codec 沒有在此兩組文字 fixture 破壞原生取消與組外保留。 |
| C04，6／6 | envelope 可普通 JSON roundtrip；deserialize 後 undefined 自有 key、null、自有 key 缺席的差別及巢狀值均保留。普通 JSON 控制仍丟 undefined。 | 明列的三種 JavaScript 物件狀態可區分；不代表所有未知型別均已測。 |

`codec-traces.json` 與 `.inspect.txt` 保存原始 before／pending／各路重開／accept／reject 的完整 value、selection、native dataList、raw metadata、onChange operations；inspect 保留真實 undefined，不能作替代 codec 回灌。`format-pending-raw-json-control.json` 是普通 JSON 確實損失資料的控制，對應 inspect 則保留生成時原貌。`codec-results.json.rawJsonControl.restoredBold=false` 明記控制失敗，沒有把原 R4 改判成通過。

## 官方 source／實裝授權與保存責任

來源存取日均為 2026-09-09；Publisher 為 SuperJSON／Blitz 團隊，套件發布 `2025-11-27`，gitHead `931dccad2ccbb923d8cde95eed59ca41fbd860e1`。

- [官方 README／固定 gitHead](https://github.com/blitz-js/superjson/blob/931dccad2ccbb923d8cde95eed59ca41fbd860e1/README.md) 明列 undefined 支援，`serialize` 回傳 JSON-compatible `json` 與 `meta`，`deserialize` 使用兩者復原；這是官方 API，沒有仿造格式。
- [官方 transformer](https://github.com/blitz-js/superjson/blob/931dccad2ccbb923d8cde95eed59ca41fbd860e1/src/transformer.ts) 的預設 undefined rule 轉為 null 並標註 undefined，再反轉回 undefined；[官方 index](https://github.com/blitz-js/superjson/blob/931dccad2ccbb923d8cde95eed59ca41fbd860e1/src/index.ts) 保存／套回註記。實裝 `dist/transformer.js`／`dist/index.js` 亦已讀取及封存。
- 官方固定 gitHead 的 `package.json.version` 為 2.2.6，官方 LICENSE 與實裝 SuperJSON LICENSE hash 相同；沒有把固定 source 與編譯 JS 宣稱為位元相同。
- 此新目錄實際只安裝 **SuperJSON 2.2.6＋copy-anything 4.1.0，兩者皆 MIT**；copy-anything 無其他 runtime dependencies，要求 Node >=18，此次 Node 22.12.0 符合。完整 package-lock 固定兩者 tarball／integrity；安裝停用 scripts。

實際格式值 envelope 的 `json` 裡，`properties.bold` 為 null；`meta.values` 以該原生節點路徑記 `['undefined']`，`meta.v=1`。因此 **App 必須完整保存並還原 `{json,meta}`，不能只取 `.json` 後直接交給 Plate**。null 不是此次原生 suggestion 的替代語意；是 SuperJSON 的中間表示。讀入 editor 前須使用同一現成庫 deserialize。這是採此元件會新增的保存邊界責任，尚未定案 DB 欄位或 API 格式。

**Mapping：**此實證支持「Plate 53.3.11／Suggestion 53.2.3＋SuperJSON 2.2.6 完整 envelope」作必要保存接線的候選；原生 suggestion 輸出不需修改。它沒有把 SuperJSON 變成 Plate 官方 serializer，也沒有解掉跨作者群組／結算順序、snapshot diff、歷史或其他原生缺口。Plate 框架方向已同意，codec 的正式採用及跨 App 邊界仍由主線設計／gate 決定。

**Unknown：**Python 不會因能讀 JSON 就自動擁有 JavaScript undefined 語意；本輪未驗 Python／DB／Agent 傳遞、所有資料型別、sourceRef、未知附加欄位、DOM／IME、跨版本或舊資料 migration。沒有增刪未知型別、寫自訂 transformer／reviver，也沒有新增第二份文件 authority。

## 檔案、hash 與封存重現

- `registry-metadata.json`：官方 registry latest／發布日／gitHead／tarball／integrity 的有限摘錄。
- `source/official-superjson/`：6 份固定 gitHead 原檔；`official-source-manifest.json` 保存 URL 與 hash。
- `source/installed-superjson/`、`installed-copy-anything/`、`borrowed-*`：22 份實裝與唯讀借用材料；`materials-manifest.json` 記原檔與副本 hash，全部相等。`dependency-inventory.json` 記兩個新增套件實際版本、授權與 LICENSE hash。
- `results/2026-09-09T15-28-48-170Z/`：首次四項完整 traces、兩路控制、codec envelopes、results 及 run hashes。
- `results/original-probes-preserved.json`：原 R01／R01-F scripts、lock、results、traces 與 R3 input 的 8 個已知 hash 均不變。
- `artifact-hashes.json`：本目錄可封存材料的完整 SHA-256 清單；不包含自己、node_modules 或 npm cache。

重現時在新的臨時父目錄保留兩個同層名稱：`jd-editor-review-probe` 放既有固定 package／lock，`jd-editor-codec-probe` 放本次 package／lock 與 script。先在兩個隔離目錄各用 `npm ci --ignore-scripts --no-audit --no-fund` 重建依賴，再於 codec 目錄執行 `node codec-probe.mjs`。腳本透過明列的同層 package 路徑唯讀解析 Plate；不需要原 R4 已損失資訊的 JSON，也不需要 DB 或模型。

`capture-materials.mjs` 只做材料封存／既有 hashes 核對；重現四項行為不必執行它。若要重跑此封存輔助程式，原 R01／R01-F 結果路徑也須保留。測試腳本以時間另建結果目錄，保留首次材料；原生 ID 與時間每次可不同，不要求跨次相等。
