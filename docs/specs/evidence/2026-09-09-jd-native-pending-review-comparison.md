# JD 待審取消：Plate 與 ProseMirror 原生能力實證

JD-R002/C03；查閱與執行日 **2026-09-09**。本稿比較當時尚未確認的修改，不要求任意已接受歷史一鍵撤回。**後續 Owner 已明確採[持續工作稿](../2026-09-09-jd-editing-and-review-working-design.md#77-owner-裁決持續工作稿保留差異與更正)，本版個別 pending 接受／取消已取代；下文是原始能力與決策沿革，正反結果全部保留。**停止其成員／結算研究，不能再把未解條件當本版 gate。有效狀態依 [register](../../current-decisions.md)。

**結論：兩套都有「取消一項獨立待審文字修改、保留另一項」的原生正證，因此不能把需求說成只能自造引擎。兩套也都有未解反例，尚無完整 JD 審閱方案通過。** 下列是固定操作證據；不是模型、DOM、IME、正式資料庫或專業內容驗收。

**後續增量：**Owner 已同意 Plate 文件底座；另有[SuperJSON codec 四項實證](2026-09-09-jd-native-pending-codec-probe.md)處理已測保存缺口，固定版本／LICENSE 也已補齊。它是新增成功路徑，不改下文 R4 普通 JSON 失敗。§6 的「未安裝／尚未驗」是 codec probe 前的查閱紀錄；完整分組／結算仍未驗收。

## 1. 版本、來源與授權

| 實際執行組合 | 版本／狀態／免費開源界線 |
|---|---|
| Plate R01 | Node 22.12.0；platejs／core 53.3.11、@platejs/slate 53.3.10、Slate 0.126.2、suggestion 53.2.3、React／DOM 19.2.4。正式 npm 發布，Suggestion React source 仍有 experimental 註解，不能等同所有行為穩定。核心與 suggestion MIT；必要依賴 diff 53.0.0 的衍生部分 Apache-2.0、Plate 修改另提供 MIT／Apache-2.0。45 個實裝 package 的版本、授權宣告與選定實際 LICENSE 已封存 |
| ProseMirror T02 | Node 22.12.0；prosemirror-suggestion-mode 1.0.79。作者 README 明示 WIP，package／README 宣告 MIT，但實際發布樹及已讀 source 沒有獨立 LICENSE，採用前材料缺件仍在。六個直接 peer 依作者 source lock 固定；實裝共 13 packages，完整版本／integrity 及其 package／LICENSE 副本保留。未採 Tiptap 商業擴充 |

Plate 公開原始碼固定於 [cee7a4e](https://github.com/udecode/plate/tree/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src)，不把 monorepo release 號套給每個 package。T02 作者 source 固定於 [e61b70c](https://github.com/davefowler/prosemirror-suggestion-mode/tree/e61b70c3cd313979778677bb448b13c0a78cfa20)；實際執行的是 lock 中的 npm ESM bundle，其 SHA-256 為 `ccaaaf5d181c1fbc7bfab99f98218a2e9febdacd136f16a41c7ee864adbf9a6f`。套件層 source／license 背景見 [Plate](2026-09-09-jd-oss-plate.md)及[替代路線](2026-09-09-jd-oss-alternatives.md)。

## 2. 實際結果

### Plate：首次四組 2 PASS／2 FAIL，沒有執行錯誤

完整原始 [R01 結果](jd-review-probe/results/2026-09-09T14-36-40-805Z/review-results.json)、[逐步 traces](jd-review-probe/results/2026-09-09T14-36-40-805Z/review-traces.json)及[來源診斷](jd-review-probe/RESULTS.md)保留，未修套件、手写 suggestion metadata 或用會清空 pending 的 AI helpers。

| 組別 | 已看到的結果／界線 |
|---|---|
| R01-1：取消月檢、保留故障 | 原生文字替換與另段新增得到不同 suggestion ID。JSON 寫檔→新 editor 後，reject 月檢恢復原始乾淨節點；故障全文及 pending metadata、交付段皆全等，只剩故障 ID。PASS |
| R01-2：接受月檢、保留故障 | 同一保存值→另一新 editor，accept 月檢保留當次新版且清除該建議；故障 pending 與交付段不變。PASS。只有一次月檢替換，不能代替反覆续改最新版的驗收 |
| R01-3：AI→人→AI，結算最初 ID | 三次全句替換產生三個原生 ID，JSON 重開完整保留它們。只 accept／reject 最初 ID，無法得到乾淨最新版／組前內容；故障仍全等。FAIL 指最初 ID 不是整條鏈的結算入口，並非資料消失，也不證逐一結算所有 ID 必敗 |
| R01-4：取消移除粗體 | 原生 update metadata 含 `properties:{bold:undefined}`。保留 undefined 的記憶體控制組→新 editor→reject 恢復粗體；標準 JSON 寫檔→新 editor 後 key 消失，reject 無法恢復粗體，正文仍在。FAIL。不能泛稱所有格式取消都壞，也不能以文字重開 PASS 宣稱 raw JSON 是完整待審保存格式 |

R3 使用各次不同作者且一直處於 suggestion mode，僅是一種測試 profile；沒有替 Owner 採用「人工改後仍待審」。原生 accept／reject 接受單一 ID，一般續編 API 未提供將整次改寫綁定既有 ID 的選項；`setSuggestionNodes({suggestionId})` 是直接標記 remove，不是通用續編群組設定。R4 的 undefined 形狀在官方 removeMarkSuggestion 與其測試中明確存在，並由本輪 memory／JSON 對照實測確認。[官方 removeMarkSuggestion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/removeMarkSuggestion.ts)、[rejectSuggestion](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/transforms/rejectSuggestion.ts)

### ProseMirror：三组，A／B 固定文字通過，C 有兩個缺口

完整 [T02 結果](jd-pm-review-probe/results/run-20260909T144514Z/report.json)與[範圍說明](jd-pm-review-probe/RESULTS.md)。正式功能只跑一次，exit 2；較早自建 schema 初始化失敗及原碼／日誌保留，當時尚未執行套件功能，不能算成套件反例。

| 組別 | 已看到的結果／界線 |
|---|---|
| A：兩個獨立 pending | App 在 native transaction metadata 分別給 A／B groupId。兩段 ReplaceStep→doc JSON 檔案→新 EditorState 後，probe 由 A marks 計算連續範圍，原生 range reject A 恢復原文，B 全文及 pending marks／未改 attrs 保留。PASS。這組沒有測 B 待審時 accept A，也不是原生 groupId resolve command |
| B：同一組 AI→人→AI | 後兩次只改現有 insertion mark 中的部分文字，三次均提供同一 App groupId。JSON→新 EditorState 後，range reject 回原文、accept 得最新版且清除 pending。PASS。但 mark 作者／stage 仍沿初次 AI，沒有保存逐次人工與 AI 歸屬，不能稱完整變更紀錄 |
| C：link href／title | `tr.addMark` 更新同型 link 實際產生 RemoveMarkStep＋AddMarkStep。JSON 重開保留 pending；accept 本例正確，reject 後出現兩份「設備手冊」，其中一份無 link。真反例，僅限所測 link 屬性更新流程 |
| C：node scope attr | `setNodeAttribute` 產生有效 AttrStep；套件讀取該 step 不具備的 from／to，slice 拋 Position undefined out of range。未返回新 state，未到 JSON／審閱。這證此版本的 AttrStep 路徑有缺口，不代表 ProseMirror 無法修改 attrs 或其他原生操作必敗 |

位置取自唯一固定 fixture，不走套件的 first-match `applySuggestion`。range helper 只包一個連續、互不交疊的 fixture group，發現包到另一組就拒絕，沒有自己重建原文；但此 App 已知群組與範圍責任必須明列，不能稱安裝套件即可辨識任意相關工作。

## 3. 不能直接拿 PASS 數量排優劣

Plate R3 是不同原生 ID 的全句替換，再只結算最早 ID；PM B 是 App 共用 groupId、在既有 insertion 內局部改字，再結算已知整個範圍。修改大小、成員提供者、結算範圍與作者保留政策均不同。**PM B 不直接解掉 Plate R3，也不能由 Plate R3 推論多 ID 原生組合必然不成立。**

為補這個比較缺口，另以原 R3 保存值觀察「正確三個 ID 已知後，用 Plate 原生單 ID 命令依序結算」。[R01-F 首次結果](jd-review-probe/results/order-followup-2026-09-09T14-53-39-183Z/review-order-results.json)為 **3 PASS／1 FAIL、0 執行錯誤**，原 R01 四組及 2／2 不變：

| 固定順序 | 結果 |
|---|---|
| accept 正序、accept 反序 | 兩者均得到乾淨最新版，故障整個 pending／交付段全等，最終 JSON→新 editor 全等 |
| reject 反序：再次 AI→人工→初次 AI | 得到乾淨原文，組外內容／pending 及最終重開全等 |
| reject 正序：初次 AI→人工→再次 AI | 留下原文＋初次 AI 文＋人工文。原生 nodes 回報月檢 ID 清單為空，但 raw JSON 仍有兩個 suggestion key；公共 suggestion flag 已清掉，殘文也進入目前文字投影。完整節點／正文斷言正確判 FAIL，不能把查詢空當成 metadata 已結清 |

這證明已知成員與指定順序時，原生單 ID 命令可以組合；**反序成功只限本例，不是通用排序法**。此觀察沒有成員發現、群組追蹤、相依圖、before-image 寫回或 vendor 修補；不證 App 已能決定成員與順序。文字投影使用原生 SkipSuggestionDeletes，仍非 DOM 呈現驗收。原 R4 格式保存反例不受此正證影響。

## 4. 本案映射與停止點

1. **保留独立待審取消的效果基線。** 兩套都已有局部正證，不因先前提問難懂就改成「只能聊天更正」。員工可以告訴 AI 更正事實，也可以查看並處理修改；是否強制逐筆確認是另一個 UX 問題。
2. **文件底座排序與審閱完成度分開。** Plate 的結構／diff／保存候選仍有其證據，但不能以乾淨快照保存替代 B05／B06。PM 第三方文字修訂也有價值，尚不能因 A／B 通過就升為完整首選。
3. **必要缺口需先有原生或正式公開接法證據。** Plate 的待審格式保存、跨作者鏈結算，以及 PM 的所測 mark／AttrStep 缺口都未被修好。本輪没有自造 codec、diff、review、grouping 或 rollback engine，也不排除必要格式／metadata 來湊全綠。
4. **審阅 metadata 不等於完整可查變更紀錄。** PM B 的作者合併说明這個區別；每次實際變更與目前內容／待審狀態仍須分辨。它不授權多存一份 semantic authority，具體保存須依文件模型與已決效果定稿。

下一個技術判斷是：在保留目前效果的前提下，這些已重現缺口是否有已公開、可採用的免費原生接法；若沒有，列有限整合與體驗取捨的具體代價再議。先不擴大完整 UI／模型實驗，也不因目前兩套未全通過就自造一般引擎。完整內容容器的另一組證據見 [F01](2026-09-09-jd-native-content-profile-probe.md)，它不代替此處審閱驗收。

## 5. 重現、封存與獨立覆核

- Plate：[原 run 入口](jd-review-probe/README.md)、[來源／授權／診斷](jd-review-probe/RESULTS.md)、[67 份封存雜湊](jd-review-probe/results/artifact-hashes.json)、[重現補充](jd-review-probe/REPRODUCE.md)。inspect traces 必須與 JSON traces 同存，因為 undefined 的消失正是 R4 觀察，不把 inspect 格式当正式 codec。
- PM：[原 run 入口](jd-pm-review-probe/README.md)、[結果](jd-pm-review-probe/RESULTS.md)、[原始材料清單](jd-pm-review-probe/results/evidence-manifest.json)、[57 份封存雜湊](jd-pm-review-probe/results/artifact-hashes.json)。原清單中的 node_modules 選定材料轉存 `source/packages/`；完整 node_modules／cache 不封存，重跑依 lock 安裝。
- 兩套首次結果及 R01-F 均經另一位 reviewer 唯讀核對。R3 的 ID／range 不公平比較、PM A 未驗 accept-with-B、B 作者歸屬、C 的 step 類型及正序 reject 隱藏 raw keys 均依 review 收窄。原始反例不改判。

本輪只有隔離開源安裝、固定操作及文檔；沒有 DB 寫入、付費模型呼叫、Memory 或 production 修改。較早 P01 的專用測試 DB 是另一單位，不能把本輪新 editor 重開稱作 DB 待審恢復。

## 6. 定點補查已收束：公開修復與整合代價

仍於 **2026-09-09** 查閱；只做來源核對，没有新增安裝或實驗。兩位研究者分別對各套缺口做兩輪精準查找。結論是「所查材料未找到可採修復」，不是保證網路上不存在任何未索引的新修復。

| 已重現缺口 | 本輪公開資料結果 | 決策影響 |
|---|---|---|
| Plate undefined 待審保存 | [現行 suggestion 文件](https://platejs.org/docs/suggestion)未給此 payload 的 serializer 契約；[固定 changelog](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/CHANGELOG.md)53.2.3 是 block removal userId 修正，沒有此修復。未找到相關維護者處理結論；本輪 registry／raw 查讀失敗，版本現況仍依同日既有 metadata，不宣稱排除所有新發佈 | raw JSON 路線的 R4 仍 FAIL。可以比較现成序列化元件，不能直接改報 PASS |
| Plate 群組／順序 | 同一 text node 多 suggestion 是官方能力，activeId 是視覺高亮；現行文件與固定 accept／reject source 沒有通用成員判定或結算順序規則 | R01-F 反序成功仍只是已知三個 ID 的正證。App 成員與順序責任不能省略或以 LLM 猜測代替 |
| PM link attrs／AttrStep | 作者 main 仍為 [e61b70c](https://github.com/davefowler/prosemirror-suggestion-mode/commit/e61b70c3cd313979778677bb448b13c0a78cfa20)，2025-03-31；[releases](https://github.com/davefowler/prosemirror-suggestion-mode/releases)未列 release。讀取 38 筆 issue／PR 的標題及正文，未找到對應修復。已有測試不包含本案 link attrs 重開取消情境 | 不能因套件聲稱支持格式或較新 PM 核心就忽略已測反例 |
| PM setNodeMarkup 替代 AttrStep | [PM transform 1.10.3 原始碼](https://github.com/ProseMirror/prosemirror-transform/blob/1.10.3/src/structure.ts#L170)有產生 ReplaceAroundStep 的路徑。但[修訂套件名為 ReplaceAround 的測試](https://github.com/davefowler/prosemirror-suggestion-mode/blob/e61b70c3cd313979778677bb448b13c0a78cfa20/test/integration/suggestions.steps.test.ts#L288)實際用 replaceWith，只驗節點／marks，未證 attrs 修改後取消／重開；[#23](https://github.com/davefowler/prosemirror-suggestion-mode/issues/23)與[#30](https://github.com/davefowler/prosemirror-suggestion-mode/issues/30)清理／補測議題仍 open | 原生 API 存在不能作替代接法已通過的證據；這輪不再新增 probe |

### 現成保存元件與 App 必要整合，不能混為自造引擎

**Official fact：**SuperJSON 的官方 README 列明支持 undefined，serialize 輸出可交 JSON 保存的 json＋meta，deserialize 還原原值；[現行原始碼](https://github.com/ravionhq/superjson/blob/main/src/transformer.ts)有 undefined→null 加型別註記、反向還原的規則。[官方倉庫](https://github.com/ravionhq/superjson)顯示 MIT，舊 blitz-js 位址現重新導向 ravionhq；[npm 發布頁](https://www.npmjs.com/package/superjson)當次顯示 2.2.6／MIT。[tRPC 11.x 官方文件](https://trpc.io/docs/server/data-transformers)列出這種傳輸方案，要求兩端配置相同 transformer。這證明「保留 JSON 以外 JS 值」有現成開源機制，不是 Plate 官方指定做法，也不是 OpenAI／Anthropic 的 JD 保存共識。

**Mapping／未採用：**可將這類現成元件列為 R4 的有限保存候選，禁止先 JSON.stringify 掉資訊才補救。Node／browser 兩端解碼；Python／DB 不自行重造同套 decoder，也不把編碼中暫用的 null 當成文件語意。這需要固定版本、實裝依賴／LICENSE、契約與原 R4 端到端驗收。本轮固定 v2.2.6 source tag 與 LICENSE 直接讀取未成功，僅有現行 source／README／npm 版本資訊；没有安装、沒有證明 Plate 相容，也沒有把它放進正式依賴。

| 整合項 | 有界線的候選工作 | 仍不允許默默承諾的部分 |
|---|---|---|
| 保存 | 使用已存在的開源 codec，在原始 editor value 尚完整時編碼，重開後再交原生 editor | 自造格式復原規則、宣稱只改 stringify 就完成所有保存、讓 Python 猜特殊值 |
| 一項產品建議對應哪些原生修改 | App 在實際執行有意義改稿時記錄成員及基準；由已知命令建立關聯，不能依相同作者／時間猜同組 | 目前沒有經驗收的成員／依賴機制。移動、跨項、人工續改與組外依賴的成本尚不能保證很小；不批准通用 dependency／rollback engine |
| 原生結算與核對 | 在隔離候選上執行原生 accept／reject，核對完整內容、metadata、組外內容再發布 | 不以查詢空代替結算正確；不能把「檢查不過就停止」當作完整 B05／B06 已實現 |

**收斂結論：**文件底座仍推薦 Plate；PM 作保留備選，Lexical 的已知比較結論不變。沒有理由再廣搜或重跑原正證。可先確認文件底座方向，接著就上述有範圍的整合寫設計；若發現必須自建通用引擎，帶具體代價返回產品討論。這不等於完整審閱定案，也不變更 B05／B06 或原生實驗結果。
