# F02：正式官方 Plate plugins 的四組有限驗證

JD-R002/C03；2026-09-10；執行前固定範圍。Owner 已選 Plate 免費核心與持續工作稿；本輪只補官方插件组合的 headless 實證，不改 production／Memory／既有 probe，不新增模型、DB、瀏覽器或 UI。

## 假設、版本與接點

固定 Node 22.12.0；platejs／core53.3.11、basic-nodes53.0.0、list-classic53.0.0、table53.0.9、diff53.0.0、React／React DOM19.2.4。沿既有 slate53.3.10／utils53.3.11／slate0.126.2，resizable53.0.0。新目錄有獨立 package/lock；只用 npm install --ignore-scripts，不改 root lock。新增套件 package metadata／LICENSE 及完整 lock 封存。核心／基本節點／list／table 為免費 MIT，diff 實際 LICENSE 另列；0 付費、0 DB、0 production。

只用 createSlateEditor、官方 BaseHeading／Blockquote／HorizontalRule／Bold／Italic／Underline／Strikethrough／List／Table plugins。jd_section／jd_duty／jd_task 是三個普通 block plugins（isElement:true），無 domain normalizer。NodeId 啟用 reuseId:true、initialValueIds:'always'；使用原生預設隨機 ID generator，不使用固定回零序列。原生 normalization 保留；批次可用 withoutNormalizing，結尾正常 normalize。

完整 r2 從既有 F01 fixture 明確映射，保留合成 source_refs 標記、全文與原 ID；唯一輸入形狀變更是 li 直接 p 改為官方 lic，blockquote 仍包 block，hr 保持空 Text child 並由官方 void plugin 定義。這是固定 fixture mapping，不是通用 importer、格式轉換器或資料遺失修補。

## 固定四組與判準

1. **F02-A canonical 全稿：**官方組合 normalize；全文、必要格式／全部原 Element ID／來源與完整工作條件保留。允許先觀測原生 canonical 與輸入差異，但不預先刪內容湊全等。canonical 寫普通 JSON 檔，由另一 Node process 建全新 editor，normalize 後與保存值精確全等。保存原始、mapped、canonical／reload、operations 與首次結果。
2. **F02-B 官方修改：**同完整 canonical baseline，原生修改職務目的段落、Task4 的一個子清單文字；官方 TablePlugin 原生插入一行，核对原行全文不變及新行存在，再由官方原生刪該行。最終完整正文須只多兩段固定合成附註，表格原全文／ID 不丟失；不得用整表替換冒充原生增刪。
3. **F02-C 移動／unwrap：**將完整 Task8 移到 Duty1，再取消 Duty4 分組；Task8 全 subtree／ID／source_refs、Task4／7 及原 Duty4 標題保留，原 Duty4 容器消失；操作後寫檔→另一 Node process 新 editor，精確全等。更改只是固定結構移動，不改任務條件或繼承新父範圍。
4. **F02-D 格式 operations 保存：**完整 baseline 上對固定文字範圍原生 addMark／removeMark，觀察真實前後 clean value／同步 capture 的 operations；肯定普通 JSON 檔案往返是否保留 operation own keys／undefined、原始值，再由新 Node process 的同基底 fresh editor 原生 apply，完整 value 與實際後版精確相等。若失敗即 FAIL，保留 memory inspect 與 raw JSON 控制；不寫 codec／replacer／vendor patch，不把僅 clean document 可存算 operations 也可存。依執行前主線 source 核對，Slate 原生 set_node 以 newProperties 缺 key 表示移除，與 computeDiff 的 own undefined 不同；實驗肯定實際結果，不鏡射預測。

每組都保存實際 before／after、operations（raw JSON 與無損人讀 inspect）及明確 assertions。原生 operations 只在 onChange 同步 clone，不在 flush 之後猜測。任何 FAIL 保留首輪結果與 code hash；官方接法錯誤最多一輪定向修正，不能改判準、normalizer、diff、歷史、身分或回退引擎來過測。若要改 document profile，先報精確反例，不在本輪改共用設計。

Pass 只適用該組具體斷言；四組完成即停止。停止條件：需要自訂通用引擎、付費／非 OSS 依賴、DB／production 改動，或一輪接法修正後仍無法執行。未驗 DOM／IME／人工鍵盤／clipboard／API／模型／完整 profile grammar validator，不能宣稱 S5 或產品整合通過。

## 重現與材料

完成後補實際命令、結果路徑及完整 LICENSE／hash 清單。封存時保留 package/lock、scripts、獨立完整 fixture、source、results；不封 node_modules。請在新臨時目录重現，不覆寫首次實證。
