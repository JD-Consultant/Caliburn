# Plate 待審保存：現成 SuperJSON 的有限實證

JD-R002/C03；查閱、固定版本與執行日 **2026-09-09**。Owner 已同意 Plate 免費核心方向；本單位只回答原 R4 保存缺口是否可以使用現成開源元件解決。**四組固定情境全部通過，沒有執行錯誤；原 raw JSON 的 R4 失敗仍保留。**這是保存元件候選的證據，不是完整 JD 保存／審閱驗收或 production 採用。

**後續效力：**Owner 已採[持續工作稿、差異及更正](../2026-09-09-jd-editing-and-review-working-design.md#77-owner-裁決持續工作稿保留差異與更正)，不設個別 pending 審閱。本 codec 保留為原生待審保存的限定證據，**不是 clean working value 的必裝套件或正式格式**；不再為本版追加此類驗證。

## 1. 問題與官方依據

[原 R01-4](2026-09-09-jd-native-pending-review-comparison.md)由 Plate 原生 removeMark 產生 `properties:{bold:undefined}`。普通 JSON 保存會刪掉這個自有 key，重開後原生 reject 不能恢復粗體。因此不能先做 JSON stringify，再由丟失資料的 JSON 推回原值。

SuperJSON 官方提供 `serialize`／`deserialize`，保存完整 `{json,meta}` envelope；undefined 以 JSON 可表示的值及型別註記保存，反向還原。此能力核對於固定發布來源 [README](https://github.com/blitz-js/superjson/blob/931dccad2ccbb923d8cde95eed59ca41fbd860e1/README.md)、[transformer.ts](https://github.com/blitz-js/superjson/blob/931dccad2ccbb923d8cde95eed59ca41fbd860e1/src/transformer.ts)與 [index.ts](https://github.com/blitz-js/superjson/blob/931dccad2ccbb923d8cde95eed59ca41fbd860e1/src/index.ts)。這是 serializer 官方契約與本案組合驗證，**不是 Plate 官方指定保存格式，更不是 OpenAI／Anthropic 的共同內部架構**。

| 固定材料 | 版本、授權與適用範圍 |
|---|---|
| SuperJSON | npm 當次 latest 正式版 **2.2.6**；發布 2025-11-27T13:27:45.738Z；gitHead `931dccad2ccbb923d8cde95eed59ca41fbd860e1`。實裝與固定官方 LICENSE 相同，MIT。Node 要求 >=16 |
| 直接且唯一 runtime dependency | **copy-anything 4.1.0**，MIT，無 runtime 子依賴；Node 要求 >=18。新增實裝共兩套件，lock／integrity／實際 LICENSE 保留 |
| 編輯器 | 唯讀借用原 R01 lock：Plate／core **53.3.11**、suggestion **53.2.3**、@platejs/slate **53.3.10**、Slate **0.126.2**、React／DOM **19.2.4**；授權沿[原實證](2026-09-09-jd-native-pending-review-comparison.md#1-版本來源與授權) |
| 執行 profile | Node **22.12.0**；createSlateEditor＋BaseSuggestionPlugin；NodeId `reuseId:true`／`initialValueIds:'always'`，原生 normalization；沒有 registerCustom、自訂 transformer、vendor patch 或手造 suggestion metadata |

完整[依賴清單](jd-codec-probe/source/dependency-inventory.json)、[官方來源 URL／雜湊](jd-codec-probe/source/official-source-manifest.json)及[發布 metadata](jd-codec-probe/registry-metadata.json)。舊 blitz-js 倉庫網址可能導向 ravionhq；固定 commit 與下載來源皆保留，不用猜測 release tag。第一次 registry 網路讀取失敗、一次授權重試成功；正式功能只跑一次。

## 2. 固定操作與實際结果

[執行前判準與重現入口](jd-codec-probe/README.md)、[實際程式](jd-codec-probe/codec-probe.mjs)、[四組原始結果](jd-codec-probe/results/2026-09-09T15-28-48-170Z/codec-results.json)。結果為 **4 PASS／0 FAIL／0 execution error，24 個斷言通過**。

| 情境 | 實際證據與限定結論 |
|---|---|
| C01：重開後拒絕移除粗體 | fresh editor 重新執行原生 removeMark，確認 own-key `bold:undefined`；完整 envelope 普通 JSON 寫檔→讀檔→deserialize→另一 fresh editor，完整 pending value 相等；reject 恢復原粗體及完整乾淨節點，無 raw suggestion keys。記憶體控制成功，普通 JSON 控制仍失敗 |
| C02：同一 pending 接受 | 從 C01 的磁碟 envelope 再建另一 fresh editor；accept 後正文保留、粗體正確移除，原生 pending ID 與 raw suggestion keys 都清空。只證同一固定格式修改的另一結算方向 |
| C03：兩項獨立待審修改 | 原生建立月檢替換與另處故障新增兩個 ID。完整 value 經 codec 檔案重開相等；reject 月檢恢復原節點，故障整個節點的正文與待審 metadata 全等，交付段不變，僅剩故障 ID |
| C04：undefined／null／缺 key | envelope 本身可普通 JSON roundtrip；deserialize 後以 Object.hasOwn 與值同時區分 undefined、null、缺 key，巢狀亦同。普通 JSON 控制確實丟 undefined，自有 null 仍在 |

普通 traces JSON 無法表示 undefined，故完整[inspect traces](jd-codec-probe/results/2026-09-09T15-28-48-170Z/codec-traces.inspect.txt)與[實際 envelope](jd-codec-probe/results/2026-09-09T15-28-48-170Z/format-pending-superjson-envelope.json)一併保存；不能只讀被普通 JSON 簡化的 trace 就聲稱值不存在。原生查詢結果為空之外，另核對 raw metadata，避免重犯 R01-F 的假結清判斷。

## 3. 決策影響與仍未證明

**可推薦 SuperJSON 2.2.6 作待審格式保存的有限整合候選，無須針對本反例自造 codec。**保存完整 json＋meta，重開時先由同配置 JavaScript codec 還原，再建立 Plate editor；不能只存 json 部分。若後續使用 Python／PostgreSQL 傳遞 envelope，應將其作同一完整 payload，不在 Python 另實作 decoder，也不將 envelope 內的 null 當成 JD 的內容語意。

本次沒有 Python／DB 往返、實際 Agent、DOM／IME、跨版本、全部資料型別、完整 JD profile 或長期相依待審測試。新的 serializer metadata 是傳輸保存表示，不是產品審閱群組、內容來源或接受狀態。C03 的獨立文字案例不能推成任意續改／結構移動的成員發現與安全結算。P01 的 clean-value DB 正證也不替本次補上 pending DB 驗收。

原 R01 **2 PASS／2 FAIL**、R01-F **3 PASS／1 FAIL** 與原 source／lock／結果全部未變；新增 codec 路徑的成功不改判原普通 JSON 路徑。完整審閱分組仍依[接線候選](../2026-09-09-jd-editor-app-integration-design.md)收斂，production authority 不變。

## 4. 獨立審查與封存

另一位 reviewer 唯讀核對程式及實際輸出，確認原生重建、structuredClone 隔離、磁碟讀回、新 editor、raw key 與組外全值核對，未發現影響上述限定結論的問題。未另跑實驗。

[封存清單與 source／archive SHA-256](jd-codec-probe/results/artifact-hashes.json)涵蓋程式、README、package／lock、官方來源、實裝授權與全部輸出；不封存 node_modules／cache。重現還需依原 R01 lock 安裝唯讀借用的編輯器環境，見[重現補充](jd-codec-probe/REPRODUCE.md)。本次只新增隔離研究依賴及文檔，沒有改 Memory／production、寫 DB、使用真員工資料或呼叫付費模型。
