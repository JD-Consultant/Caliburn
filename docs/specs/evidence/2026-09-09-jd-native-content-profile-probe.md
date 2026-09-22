# JD F01：結構容器、內容保留與 normalization 實證

JD-R002/C03；2026-09-09。承接[接線設計 §2／§10](../2026-09-09-jd-editor-app-integration-design.md)，**六組固定情境，修正一項測試接線後五組通過、一組原始 JSON 精確保留反例仍成立**。這不是正式 schema、完整 F／U、待審取消或框架採用驗收。

## 1. 固定表示與範圍

完整 r2 以手寫 mapping 包成 `jd_section`／`jd_duty`／`jd_task` 三種普通 block element，內部沿用原段落、標題、表格及清單。Task4 三種異常／責任要求、Task8 月檢條件均留在各 Task 內文；無新增工作事實或條件繼承規則。section 的用途以有限 `section_kind` 表示，標題仍是可讀內文；它尚非已核准的通用 enum。

前次 Task2 的 score／approved／provenance／obsolete 是合成 diff 測試欄，這次候選不帶它們；原始 fixture 與反例未修改。除此以外，去掉新增容器即可精確得到原固定內容。Task 加入的 source references 全為明示虛構測試引用，不是 Memory／canonical 訪談或正式來源驗證。

使用既有 `platejs@53.3.11`／`@platejs/slate@53.3.10`／`slate@0.126.2`，Node v22.12.0；無新安裝、DB、付費模型或 production 變更。寫入 editor 啟用 NodeId，`reuseId:true`／`initialValueIds:'always'`，只自訂固定 ID 產生序列；三種容器僅設 `node.isElement:true`，沒有 domain normalizer 或 `node.isContainer:true`。

官方允許可編輯 block element 包含其他 blocks；Slate 仍會修整其內建結構約束。**普通 plugin 註冊不等於已具 JD parent／child schema 檢查，normalization 也不是只回錯而不改稿的 validator。**[Plate Element](https://platejs.org/docs/api/slate/element)、[Slate normalization](https://docs.slatejs.org/concepts/11-normalizing)

## 2. 原始結果與定點診斷

[首輪 4／2](jd-profile-probe/results/profile-2026-09-09T14-36-39-396Z.json)及[首輪原碼](jd-profile-probe/results/first-run-profile-probe.mjs)保留。只有 F01-D 的測試接線改正；F01-A 原斷言保留，另補較窄觀測。[第二輪 5／1](jd-profile-probe/results/profile-2026-09-09T14-39-28-666Z.json)仍按原始 JSON 反例回 exit 1，不能把它當執行故障或整套全綠。

| 組別 | 結果與效力 |
|---|---|
| **F01-A 完整 r2／重開** | force normalize 原生移除 Task4「完成要求：」粗體 label 後的空、無格式 Text leaf。原始 JSON 精確相等斷言 FAIL；全部可讀文字、其餘 ID／格式／要求未變。次級觀測確認差異僅此空 leaf，正規化後的 clean value 經 JSON 檔案、新 editor、再次 normalization 全等；不能改稱原始 JSON 全等 |
| F01-B 移動 Task8 | Task8 移到 Duty1 後整個 subtree／ID／source_refs 全等，Task4 不變，ID 唯一。只證本固定移動；新父没有另設條件，不外推已驗任意父條件繼承或 DOM 拖動 |
| F01-C 取消 Duty 分組 | 原生 unwrap Duty4 後，原標題、Task7、Task8 各 subtree 全等，文字及八項 Task 保留；未驗 UI 能否讓員工分清 unwrap 與 delete |
| F01-D 建構中內容 | 沒有 Duty 的未完整 Task、普通未歸屬成果、含合法空 paragraph 的 Task，經 JSON 序列化／解析後新 editor 全等；本項沒有檔案 I/O。另觀測 `children:[]` 的 Task 會變成直接含空 Text 的 Task，不自動成為正式 grammar 合法的段落容器 |
| F01-E 正文換行 | 固定 selection 的原生 insertBreak 增一個段落，文字及 Task4 身分／引用保留，Task 總數仍八。不是 DOM Enter／IME 或任務語意拆分驗收 |
| F01-F 已解析 fragment | 複製 Task4 的原生 fragment 插入後，有兩份完整文字的 Task、各 element ID 唯一且 Task ID 不同；引用仍存在。未直接驗新複本的所有 parent 規則、外部剪貼簿、HTML parser 或跨文件引用清洗 |

B／C／E／F 只比較操作當下的原生 value，未測各項操作後的 JSON 重開；不能把 A 的檔案重開正證套給整張表。

### A 的 normalization 差異

原始操作為 `remove_node`，目標是 `r2-51` 的最後一個 `{text:''}`；Slate 0.126.2 core `normalizeNode` 的空文字分支支持此觀測。測試沒有先刪掉該輸入來讓原斷言過關，也沒有改原生引擎；次級觀測以獨立 oracle 核對「只少這個空 leaf」，再驗 clean value 重開。

本反例說明：需要定義保存的是已核對的原生 canonical value，並讓 App 看見 normalization 的實際影響；不能承諾任意可輸入 JSON 原樣保留。這不是允許丟失工作、有效格式或未知必要 metadata，也不是宣告原本所有空文字格式問題已解。

### D 的測試接線錯誤

Plate NodeId wrapper 會在可修改的傳入 node 上暫加 `_id`，apply 時 clone 並消費它；乾淨 editor value 沒有該暫存欄。首輪把傳入物件同時當驗證 oracle，導致錯誤地期待重開值也含 `_id`。改用 `clone(additions)` 交原生 transform 後，獨立原值 oracle 通過。這是測試 aliasing 修正，不是保存器丟 metadata 的反例，也不是自訂 codec。

## 3. 對候選的影響與剩餘工作

三種普通容器沒有在這組固定操作中顯示表示法障礙，完整工作的敘述、局部要求與身分可隨原生操作保留。**仍須有限的 App grammar／欄位驗證與錯誤回報**，不能要求普通 plugin 自動拒絕 Task 套 Task、非法 parent 或外部引用；不靠自訂 normalizer 猜測如何修好工作內容。

本輪沒有新增 renderer／React SSR／瀏覽器，source labels 只是 fixture 對照。正式容器與所有必要欄位在員工視圖可讀、空格式前後如何說明，以及選取／輸入／貼上仍未驗收。真正任務拆分須先有明確兩項內容及條件配置；正文 insertBreak 不代替它。R01／其他框架的待審取消證據另看，不能拿 F01 的結構正證縮減 B05／B06。

獨立 reviewer 已依固定 source 分清 A 的原生差異與 D 的 harness aliasing；另一位 reviewer 核對兩輪結果，指出 D 未經檔案 I/O，本文已修正，B／C／E／F 的效力也逐項限定。第一輪 raw results 沒有被覆寫。完整[第二輪 traces](jd-profile-probe/results/profile-2026-09-09T14-39-28-666Z-traces.json)保留 before／after、operations、A 次級重開及 D 空容器觀測；[重現路由](jd-profile-probe/REPRODUCE.md)沿既有鎖檔，不需要模型或 DB。[10 份原始檔雜湊清單](jd-profile-probe/results/artifact-hashes.json)逐一比對研究目錄與封存副本相等。
