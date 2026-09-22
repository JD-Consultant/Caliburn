# F01：正式 JD 容器與必要內容的有限驗證

2026-09-09；JD-R002/C03；執行前固定範圍。只有隔離研究，未採用 schema／review policy，不改 production、Memory、DB、模型或原始 probe。R01 另驗待審取消，不能以此 F01 取代。

## 假設與固定 profile

依 C01 與接線設計 §2，以三種普通 block element `jd_section`、`jd_duty`、`jd_task` 包住完整 r2 的原生段落、標題、表格及清單；標題、適用條件仍是內文，不把它們另存隱藏 props。Task 可不經 Duty。來源只用有明確標示的固定虛構 references，不建立 Memory／lineage。

使用既有兄弟目錄 `jd-editor-native-probe` 的 Plate 53.3.11／diff 53.0.0／React 19.2.4 lock，Node 22.12.0；沒有新安裝。寫入 editor 啟用 NodeId `reuseId:true, initialValueIds:'always'`。只用普通 element plugins 與原生 transforms，沒有 domain normalize override。

固定 r2 mapping 是手寫 fixture 包裝，不是通用 importer。前次 Task2 上 score／approved／provenance／obsolete 是刻意合成的 diff 測試欄，本次正式內容候選不帶它們；原始 fixture／失敗結果原樣保留。本次仍逐字保留整份 r2 及 Task4／8 全部要求，另加明示的虛構 source references。新增的未完整／未歸屬內容只屬獨立測試資料。

## 最多六組操作

1. F01-A：完整 r2 包裝後強制原生 normalization、JSON 存檔及新 editor 重開；去掉新增容器與測試 references 後，與原固定內容精確全等。
2. F01-B：把 Task8 移到另一個 Duty；整個 Task 的 ID／內文／適用條件／引用全等，Task4 等無關內容不變。移動不繼承新父項的工作條件。
3. F01-C：取消 Duty 分組，用原生 unwrap；保留標題及所有 Task 子內容。這與刪除全部工作不是同一操作。
4. F01-D：新增沒有 Duty 的未完整 Task 與未歸屬成果，保存重開；另觀測空 children 的 Task 被原生怎麼修整，與合法空 paragraph 表示分開，不自行造 normalizer 補過測試。
5. F01-E：在 Task 正文中原生 insertBreak；觀察段落／Task 身分及內容，不把換行冒充語意拆任務。這不是 DOM Enter／Backspace／IME 驗收。
6. F01-F：原生插入一段含完整 Task 的固定 fragment，觀察內容／層級與重複 ID 處理；這不是瀏覽器剪貼簿／外部 HTML parser 或跨文件來源驗證。

保存每組真實 before／after、原生 operations、ID／內容判準。失敗保留，不在同輪靜默增加 profile 正規化、專用 matcher、身份／回退引擎；接法錯誤修正須分清與原生能力缺口。

## 呈現與停止界線

必要可讀內容（特別是 Task4 異常處理與 Task8 月檢條件）在正文；測試 source references 以可讀標籤呈現。有限 React SSR 可補欄位呈現觀測，不能代替瀏覽器、編輯、選取或螢幕可用性驗收。完整 dirty/current/proposed/accepted 視圖依尚未完成的審閱選型決定，不默認三種容器解決 pending。

Slate 官方規定 element 要有 Text descendant、block 子內容不可混合 block 與 inline/text；normalization 可能插入空文字或轉換／移除不合形狀的內容。本輪檢查現有固定版本的實際結果，不將 normalization 當成拒絕無效輸入的保證。[Slate](https://docs.slatejs.org/concepts/11-normalizing)、[Plate Element](https://platejs.org/docs/api/slate/element)
