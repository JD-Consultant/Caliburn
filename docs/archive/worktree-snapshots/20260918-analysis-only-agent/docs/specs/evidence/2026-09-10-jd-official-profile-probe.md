# F02：正式官方 Plate 插件組合的有限實證

JD-R002/C03；2026-09-10（Asia/Taipei）；**第二輪四組、十五個斷言全部通過。首輪一組通過、三組子程序結果缺檔的執行失敗完整保留。**只有 headless、普通 JSON 檔案與全新 Node 程序；不代表 DOM／IME、完整 grammar、API、模型或 S5 已通過。

依 [正式文件 profile](../2026-09-10-jd-plate-document-profile.md)補上一個明確缺口：F01 的基本 list／table 註冊能否換成官方免費插件，仍保留完整 JD 與原生操作結果？本輪不是框架重選、pending 結算、codec 或通用引擎研究；不改 production、Memory、DB 或舊實證，0 付費請求。

## 1. 固定版本、授權與真實配置

隔離目錄 `.research-tmp/jd-editor-official-profile-probe`；安裝前已寫 [README 原判準](jd-official-profile-probe/sources/README-executed.md)。Node `22.12.0`；`platejs@53.3.11`、`@platejs/core@53.3.11`、`@platejs/basic-nodes@53.0.0`、`@platejs/list-classic@53.0.0`、`@platejs/table@53.0.9`、`@platejs/diff@53.0.0`、React／React DOM `19.2.4`。overrides 固定 `@platejs/slate@53.3.10`、`@platejs/utils@53.3.11`、`@platejs/resizable@53.0.0`、`slate@0.126.2`；其餘精確版本依 [獨立 lock](jd-official-profile-probe/package-lock.json)。使用 `npm install --ignore-scripts --no-audit --no-fund`，沒有改 root／production lock。

[實裝授權盤點](jd-official-profile-probe/license-inventory.json)含 48 項：46 項宣告 MIT、1 項 Apache-2.0、diff 未填 metadata license 欄。diff [實際 LICENSE](jd-official-profile-probe/licenses/node_modules__@platejs__diff/LICENSE)說明原衍生碼 Apache-2.0，修改部分 Apache-2.0／MIT 雙授權。40 個安裝包有可封存的 LICENSE／NOTICE；其餘八項宣告 MIT、未附 root LICENSE，已依各固定 npm gitHead 取得 [官方授權 fallback](jd-official-profile-probe/licenses/official-fallback-sources.json)，不混稱實裝包原本附有。只涵蓋本隔離 lock，未採付費套件。

[engine.mjs](jd-official-profile-probe/engine.mjs)直接使用官方 `BaseHeadingPlugin(levels:[1,2,3])`、`BaseBlockquotePlugin`、`BaseHorizontalRulePlugin`、四種格式插件、`BaseListPlugin`、`BaseTablePlugin`；只有 `jd_section/jd_duty/jd_task` 是本案 `isElement:true` 普通容器。沒有以 plain 元件代替 native list/table，沒有 `isContainer:true` 的 JD 容器或自訂 normalizer。list/table options 沿原生預設（包括 table 的 merge 接點）。diff 僅固定依賴，**本輪未呼叫 computeDiff 或重跑原 diff 實驗**。

NodeId 啟用 `reuseId:true, initialValueIds:'always'`，其餘原生預設，包括 `nanoid(10)`；沒有固定回零測試 ID generator。初始化、操作與觀測邊界使用同一官方 normalizers；結果不可借關掉 ID／normalization 解釋。重播只在同一 baseline 進行，不證 stale operations、rebase 或持久 history。

## 2. 固定完整 r2 與四組結果

完整 [原始 F01 值](jd-official-profile-probe/fixture-original-f01.json)與 [官方形狀 fixture](jd-official-profile-probe/fixture.json)均封存。唯一明示輸入 mapping：22 個 `li` 直接 `p` 改為 `lic`，文字、格式、Element ID／source_refs 不改；blockquote 仍包 block，hr 保留其空 Text child，官方插件令它成為 void。[mapping 與來源 hash](jd-official-profile-probe/fixture-mapping.json)。這不是 importer，來源仍是有標記的虛構 r2／`fixture-source:*`，不是真實 Memory 引用或模型輸出。

最終完整 [results](jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/results.json)與 [before／after／operations traces](jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/traces.json)可逐項核對。所有失敗斷言原樣保存；以下 PASS 僅指對應實際斷言。

| 組別 | 真正做了什麼／肯定結果 | 證據邊界 |
|---|---|---|
| **F02-A（5／5）** | 官方組合 force normalize 全 r2；全部文字、非空 leaf 格式、所有原 Element ID、來源保留；3 表、8 Task、li→lic、hr void 確實存在。clean value 無 undefined 等非 JSON 值。canonical 寫檔後，另一 Node process 建 fresh editor、normalize，與保存值完整深相等 | mapped input **不是** canonical：原生仍移除 Task4「完成要求：」後一個多餘空、無格式 leaf。沒有稱任意 raw JSON 不變、全部 schema 或 source owner 已驗 |
| **F02-B（4／4）** | 原生插字修改 `purpose` 與 Task4 子清單 `r2-52`，添加明示合成附註。官方 `tf.insert.tableRow` 在基本資料表最後插一空列，原列完整相等；選取該新列後 `tf.remove.tableRow` 刪除它。最終整份 JSON 只多兩個固定附註，原表／其餘全文／ID 精確保留；確有 tr 的 insert_node／remove_node，無 table 替換 | 只驗原生 headless 一次增刪列；未驗 UI 按鈕、鍵盤、增刪欄、merge/split cell 或此組的獨立重開 |
| **F02-C（3／3）** | Task8 完整移到 Duty1，再 unwrap Duty4；Task8／4／7、原 Duty4 標題、適用条件／ID／source_refs 全保留，8 Task 仍在，Duty4 容器消失。整份結果與明確預期結構相等；寫檔後另一 Node process fresh editor 全等 | 只驗固定父子位置及明示 unwrap；不外推拖曳、語意拆任務、任意父條件繼承、跨文件來源或語意合併 |
| **F02-D（3／3）** | 全稿目的文字 add underline、Task4 既有粗體 label remove bold；全文不變，格式實際更新。同步 capture 四個原生 operations，普通 JSON 檔讀回與 memory operations 完整深相等。另一 Node process 由相同完整 baseline 逐一原生 apply，normalize 後與實際後版深相等 | 四個操作是兩個 set_selection、兩個 set_node；未測全部 operation 變種、未知 metadata 或任意歷史。沒有 codec／replacer／diff 修補 |

主程序 PID `4264`，A／C／D 的 fresh 程序分別為 `10492`／`26368`／`5680`；[fresh-editor.mjs](jd-official-profile-probe/fresh-editor.mjs)由子程序自行讀普通 JSON、建立 editor、套用原生接點並寫出結果。它們是不同 OS process，不是只在同一 process 重新呼叫 editor constructor；仍無 DOM。

## 3. 兩個重要界線

**Canonical 不等於任意輸入原樣保存。**F02-A 捕到的單一 normalization operation 是 `remove_node`，path `[4,2,2,2,0,0,1]`，node `{text:''}`。這延續 [F01](2026-09-09-jd-native-content-profile-probe.md)已知多餘空無格式 leaf 的觀測；F01 原始 JSON 失敗不改判。F02 肯定的是全部原工作內容／必要格式／身分保留後，canonical value 檔案與新程序往返相等。未新增「可以刪空格式」政策。

**Slate 原生操作與 computeDiff 顯示資料不同。**F02-D 真實移除粗體為：

```json
{"type":"set_node","path":[4,2,2,2,0,0,0],"properties":{"bold":true},"newProperties":{}}
```

`newProperties` 省略 `bold`，沒有 own `bold:undefined`；新增底線則是 `properties:{}`、`newProperties:{underline:true}`。两個 selection 操作可含原生 `null`，這是 operation 表示，不是把 clean document 的 props 改成 null。[原始 operations JSON](jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/F02-D-operations-memory.json)與 [memory inspect](jd-official-profile-probe/results/2026-09-09T16-26-50-933Z/F02-D-operations-memory.inspect.txt)並列，原生新程序重播成功支持這組格式變動資料可直接 JSON 保存。

這沒有修好 `computeDiff` 的 leaf score 1→0 或空 Text marks 漏標反例；也沒有證明任意兩份快照可完整高亮。原生當批 operations 要在 `onChange` 同步取得，持久保存及員工看得懂的顯示由正式接線驗收；不得把前述正證延伸成現成通用 diff／history 引擎。

## 4. 首次失敗與唯一接線修正

[首輪 results](jd-official-profile-probe/results/2026-09-09T16-26-03-698Z/results.json)為 1 PASS／3 FAIL：[首輪原 probe source](jd-official-profile-probe/results/2026-09-09T16-26-03-698Z/first-run-probe.mjs)完整保留，不只留 hash。A／C／D 在讀取 fresh 子程序預期輸出檔時 ENOENT，該輪 archive 確實沒有那些檔案。先前已完成的內容／操作斷言仍可查看，但 fresh process 邊界當輪失敗，不算通過。

首輪 helper 尚未持久保存 spawnSync 的 status/error/stdout/stderr，故**無從確認原始啟動錯誤代碼，不能斷言一定是權限或某一種環境錯誤**。唯一修正是在讀檔前記錄進程診斷並直接傳遞 proc.error；第二輪以允許隔離子程序的執行權限重跑同四組。未改 assertions、fixture、normalizers 或官方插件；第二輪全過不倒推首輪根因。[完整準備紀錄](jd-official-profile-probe/setup-notes.md)

兩輪資料目錄是 UTC 時間（`2026-09-09T16:26…Z`），本地 Asia/Taipei 為 2026-09-10。無額外情境或舊 probe 重跑。準備期另有封存 fixture import 相對路徑錯誤，在四組執行前改為原研究兄弟目錄；沒有改旧 fixture。

## 5. 來源、封存與可用結論

官方來源 publisher 為 Plate／Slate／各套件維護者，查閱日 2026-09-10；以 [指定版本 npm metadata](jd-official-profile-probe/sources/registry-metadata.json)、完整 lock integrity 與 **實裝 npm dist 原碼**為準。[31 份 source manifest](jd-official-profile-probe/sources/installed-source-manifest.json)涵蓋 basic/list/table、core／NodeId、Slate transforms、相關型別與既有 diff 原碼；未改 vendor source。對外固定來源可從 [basic-nodes53.0.0](https://registry.npmjs.org/@platejs/basic-nodes/53.0.0)、[list-classic53.0.0](https://registry.npmjs.org/@platejs/list-classic/53.0.0)、[table53.0.9](https://registry.npmjs.org/@platejs/table/53.0.9)及 [Slate0.126.2](https://registry.npmjs.org/slate/0.126.2)核對，不把 monorepo release 當各 package 版本。

[封存 README](jd-official-profile-probe/README.md)提供新臨時目錄重現方式；獨立 fixture 已齊，不必 import 舊研究目錄。封存包含 package/lock、scripts、原始／mapped fixtures、两輪全部已產出 results、memory inspect、原 source／LICENSE／metadata、[SHA-256 清單](jd-official-profile-probe/artifact-hashes.json)，**不含 node_modules**。執行時 README 原文另存，與 run report 的來源 hash 對應。

可支持：正式選定的官方免費插件組合在這四組完整 headless 情境可承接原生修改及 canonical JSON 重開；本次未發現需要改 document profile、加入 codec 或自製引擎的反證。尚不能宣稱：完整 grammar／欄位 validator、非法輸入拒絕、來源 authority、DOM／IME／clipboard、人工 history 交接、DB／API／Agent／模型、所有 table/list 操作或任意歷史差異已通過。下一步應把本結果交主線必要整合驗收，不新增微型實驗。
