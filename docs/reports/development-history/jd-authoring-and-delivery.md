# JD 編輯、引用與交付的演進材料

回到[演進總覽](README.md)。這條線追查參考資料如何成為可編輯的 JD、人與 AI 如何共用成果、引用能否支持改後文字，以及成品能否交付。

日期採原文事件；設計文件可能持續修訂，不把首次檔名日期當全部實驗的執行日。以下「通過」均限原件記載，本次沒有重跑模型、DB 或瀏覽器。

## 1. 2026-07-11：參考選單不應暗中改掉文件身分

**問題／發現：**選參考職能基準會連帶重寫文件表頭，部分選單初次開啟便預先套用；改名又會清掉來源身分。這把「拿來參考」「真正寫進 JD」「項目原來從哪裡來」混在一起。

**研究／改法：**重分控制、參考與素材選單；選參考集合不再改文件表頭，文字改名不再直接抹除出處。前後程式可以看到 `set_occupations` 移除 `_refresh_header` 與文件寫入；`renameUnit`／`renameTask` 保留 refs／provenance，選單改用來源碼辨認既有項目。

**證據／限制：**原研究記 API 330、Web 58 項通過；本次僅讀原件及 diff，沒有重跑。無來源碼的值物件仍按名稱比對，不能說當時已解決所有身分歧義。「保留出處」也不等於保證改後敘述仍被原來源支持。

**引用：**[選單研究 §1–5、§9、§13](../../history.md#source-17605e43789d1be5d104)；前後程式 `f1a76b6f:apps/api/app/api/routes/documents.py`、`5150d2f0:apps/web/src/lib/ocsDoc.ts` 及同提交 `apps/web/src/lib/pack.ts`。早期 autosave 競態另見[程式演進第3例](code-evolution.md)，不在這裡重複。

## 2. 2026-08-15 至 08-23：換成檔案工具，仍不等於模型知道如何建立第一筆資料

**問題／發現：**早期大型 mutation 格式要求模型處理許多無關欄位、身分與引用定位；後來改 VFS，仍遇到來源路徑、strict schema 與第一個資源建立契約不足。8/22 一輪診斷已有 48 次工具上限，模型完成 18 次讀取卻沒有編輯，接著被既定 lookup-wave 限制阻止。

**研究／改法：**trace 與零成本契約核對發現：空 OPKS 沒有現成檔案範例，分析 Skill 教的是「怎麼分析工作」，`write_file` 卻沒有交代建立路徑、必填欄位及 evidence 格式。因此只補既有工具的 Duty／Task／Output 三個精確範例，不繼續增加工具、模型或預算。

**證據／限制：**相同模型設定再試，成功修改既有任務、建立兩個任務和第一筆 Output，跨過 first-resource blocker；但第九次模型呼叫超過當時八次上限，仍無員工可見的完成結果，連 candidate check 成功也不能由該次 trace 確認。後續又有 finalization、輸出容量與持久草稿修訂，8/23 的兩輪 smoke 記在同原件後段；不能把其中一次局部成功寫成整套 VFS 或新模型品質全面通過。

**引用：**[ADR0063](../../adr/0063-hybrid-candidate-edit-tool-and-structured-final-response.md)、[VFS與證據定位研究](../../history.md#source-577ba3070035e1f4163c)、[原 smoke §1–5](../../history.md#source-59f3bfe039c7e9ac5e72)。quote 的 slice mismatch 是當時的定位反例，不足以單獨證明中文為根因。這一例適合呈現「不是只改 Prompt；工具契約本身也是模型可用性的一部分」。

## 3. 2026-08-26 至 09-13：共用一份目前稿，仍要釐清編輯是否等於核准

**問題／發現：**正式 editor 與 AI 工作稿並存、再做三方 rebase，讓員工像在面對兩份競爭文件。ADR0069 改成一份共用目前稿，卻把修改 AI 待審內容視為接受最小合法群組；下一輪 UI 討論又指出，員工可能只是想先改幾個欄位，還沒打算核准。

**設計如何再變：**8/27 的 ADR0070 候選把「編輯」與「明確接受」分開；9/12 新關聯式 App 又重新選定 AI 可直接保存、以可見差異與歷史承接，不逐次要求接受。這是產品互動與權責多次取捨，不是同一套審核流程從頭用到尾。

**證據／限制：**ADR0070 仍標 Proposed，不能把候選當已切換。9/13 真瀏覽器＋真 SQL／Saver、固定 provider 的兩輪旅程，觀察到單一可編輯 JD、實際差異、人工修改及關頁重開。第一輪 fetch 曾失敗，查回原輪後才完成；根因沒有足夠資料確認，不能補寫已修好。這不是自然模型品質或所有故障驗收。

**引用：**[ADR0069 §Context與決定6–7](../../adr/0069-shared-current-jd-working-copy-and-semantic-approval.md)、[ADR0070](../../adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md)、[9/12設計 §5.5–6](../../history.md#source-8edfebf03222f20deda7)、[首個瀏覽器旅程](../../experiments/legacy-evidence/jd-relational-chat-web/browser-first.md)。後來新目標的 Turn 候選預覽與成功採用是另一次生命週期設計，接[T09 UI證據](../../history.md#source-072687957bc7ca22325b)，勿沿用上述歷史核准規則。

## 4. 2026-09-09 至 09-12：原生文件 diff 能畫紅綠，不一定讓人看懂業務變更

**問題／發現：**Plate 固定 JD probe 能呈現表格、清單及兩版文字，但 scope 改動只在展開 JSON 中可讀；另有數字 `1→0` 顯成 undefined、空文字格式改動不產生 diffOperation 的反例。

**研究／取捨：**保留原生結果與反例，不另外造一套 diff 假裝通過。之後重問產品究竟需要自由富文字，還是可管理的任務／欄位／關係；9/12 確認統一排版、文字與換行已足夠，轉向一般欄位與結構化管理，不因已研究 Plate 就硬保留。

**證據／限制：**29 項 Node／SSR 通過**包含「兩個反例仍成立」**，不是 29 次原生 diff 正確。瀏覽器看見三欄九張表格、重開仍在；未驗任意 JD、IME、即時編輯或 PG 交易。後來不用 Plate 的理由包括產品需求收斂，不能僅憑這兩個 bug 宣稱整個框架不適合。

**引用：**[呈現與重開原報告](../../experiments/legacy-evidence/2026-09-09-jd-native-editor-ui-probe.md)、[機器結果](../../experiments/legacy-evidence/jd-ui-probe/results/ui-node-results.json)、[瀏覽器觀測](../../experiments/legacy-evidence/jd-ui-probe/results/browser-observations.json)、[需求重審 §1–2](../../experiments/legacy-evidence/2026-09-12-jd-relational-editor-needs-and-design-review.md)。

## 5. 2026-09-12 至 09-30：工具要完成業務效果，不只是把 CRUD 拆小

**問題／發現：**設計寫 AI 修改是原子 batch，工具稿卻只有人工能 batch；AI 更正同一核准規則的兩處內容時，可能第一處成功、第二處失敗。另一反例是已知完整任務仍被迫先建名稱，再補敘述。還發現任務移出職責後，資料列雖全在，原先只寫在職責上的適用條件卻可能不再可見。

**研究／改法：**先定共同業務效果與保存界線，再比較具名完整操作、有界組合及萬用 payload。9/29 新工具設計選少量具名入口，模型填目標、內容和直接來源，App 承擔已知 scope／版本／操作身分；建立任務可一次附目前已知內容，按需讀取與 Markdown 差異另有責任。不是工具越少越好，也不是 FK 正確就表示工作意思沒變。

**證據／限制：**9/12 finding 先是設計矛盾與反例，文件閉合不等於程式完成。9/30 T07 才逐項串驗工具 codec、候選隔離、修改／移動／刪除／來源及重入；語意上是否保留責任範圍、模型是否適當選工具，仍須產品旅程量測。不能把八個 JD 入口當全部 Agent 工具數，也不能由單項原子性推論任意多工具共同原子。

**引用：**[初審 JR-R01／JR-R05與後續複核路由](../../experiments/legacy-evidence/2026-09-12-jd-relational-editor-needs-and-design-review.md)、[9/29工具契約 §1–4、§6–7](../../specs/2026-09-29-jd-model-tool-contract-review.md)、[T07工具串接與完成對照](../../history.md#source-57a6c655d8755a610427)。

## 6. 2026-09-10 至 09-30：員工改了 JD，不代表引用也已重新支持它

**問題／發現：**保存成功、通知模型、模型真的理解是不同事情；員工手改的 JD 也不能直接冒充訪談事實。舊來源依然存在，不表示它仍支持改後文字。

**研究／改法：**區分內容修改與來源核對，讓顧問看人工差異，再按需回讀來源。9/13 真 PG＋固定 SDK 兩輪測試：改一個任務敘述後，該任務來源變待核對，另三個未變子項保持原狀；第二輪 AI 讀到人工新內容，再改名稱並追加來源。新目標後來將 diff 閱讀與明確確認分開，確認後再改文字也須重新判斷。

**證據／限制：**該次 PG 測試首敗是 harness 只讀第一頁便當全文，較大來源回傳有 32 KiB 分頁；修測試跟隨 cursor 後才過。這不是產品語意 bug 已被修復，也不是自然模型自行判斷來源可信。當時的分頁設計屬歷史，不應倒灌為新工具規範。

**引用：**[Context／人工修改／來源研究](../../research/agent-systems/2026-09-10-jd-context-change-and-source-research.md)、[原PG首敗與結果](../../experiments/legacy-evidence/jd-consultant-source-integration/postgres-results.md)、[T07 §5的只讀diff／明確確認／再改文字反例](../../history.md#source-57a6c655d8755a610427)。仍有「模型有資料卻漏選早期依據」的品質限制，接[案例三](../research-casebook.md#案例三-來源已提供但模型仍漏選引用)，不把保存與引用格式通過當語意品質通過。

## 7. 2026-09-12 至 10-01：交付不是 API 回 PDF 就結束

**問題／演進：**9/12 曾提出 Excel 匯出，9/13 又延後，不能把設計當下載功能完成。新目標實作 PDF 時，要先固定正式版本、排除未完成候選，處理中文長頁，還要確認 UI 真能下載。

**研究／改法：**採現成 Chromium／Playwright 排版；固定正式修訂取料，DB session 關閉後才渲染。依相應官方執行緒與取消契約接線，不另造 PDF 引擎。後續由直接 API 檢查加上真瀏覽器點下載，避免 API 成功掩蓋 UI 未接通。

**證據／限制：**原 T13 有一頁／三頁真 PDF、四頁逐頁視檢、80 個步驟與末尾成果回查；候選不進正式 PDF。後續文字抽取卻把「長」變成「⻑」，以不同字型對照追到 cmap／glyph 映射：視覺正確不等於複製或搜尋相同。原文選擇保留限制，沒有為此新增字型加工管線。乾淨交付另屬 T18，不能拿本機已有 browser／font 當跨平台通過。

**引用：**[9/12設計 §8及後續延後](../../history.md#source-8edfebf03222f20deda7)、[T13切片、接線、下載與文字層診斷](../../history.md#source-409f20a1c297740aed7d)。打包後 migration 找不到的問題與非 editable 安裝驗證，接[工程沿革第7例](engineering-and-verification.md#7-開發環境能跑不代表套件裝好能跑)。

## 8. 2026-10-04 至 10-05：縮短選讀，仍要保留 JD 的責任與條件

後續研究用相同 Memory 比較選讀邊界，再比較工作情境單位與 A 的寫作指示。讀取較少、輸入較短，並不必然保住其他單位的分工、適用範圍與不確定程度：候選仍曾漏掉分工，或把已有表述改寫成較強的責任。各案逐項核對 JD 與來源，不只計算工具次數。

分層維護接著發現，情境中的新期限雖已保存，理解的另一處副本仍可能沿用舊值。五對局部保存比較保留三層；正式 B2 僅增加兩條跨案數字／期限副本維護規則，A 的候選指示未採用。後續對話的延遲檢索及更正能保住部分 JD 內容，但兩批成本方向相反，不能由局部結果推出全面效率提升。

**引用：**[相同 Memory 選讀比較](../../experiments/product-validation/data/memory-reading-boundaries-2026-10-04/README.md)、[JD 範圍保留](../../experiments/product-validation/data/jd-scope-preservation-2026-10-05/README.md)、[分層內容比較](../../experiments/product-validation/data/memory-layered-value-2026-10-05/README.md)、[內容與選讀研究的現況](../../research/agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md)。數字與採用界線集中見[Memory 沿革](memory-and-context.md#2026-10-04-至-10-05從保存得到進一步比較選讀與使用)。

## 9. 2026-10-05 至 10-06：整份職務檔案的生命週期也屬交付

清單已提供整份職務檔案刪除：須確認，包含訪談、JD、Memory、引用及執行歷史，有未結束工作時拒絕。介面成功回應前保留清單資料，回應遺失時可針對同一檔案重試；Docker 實機驗了確認／取消，真正刪除由 API 與 PostgreSQL 核對，前端提交及 cache 清理由行為測試驗證。

10/06 進一步修正取消後 Saver 遲到寫入的競態，詳[工程接續](engineering-and-verification.md#9-取消已提交仍須等真正保存結束)。這補上保存與管理契約，未新增真模型產稿品質證據，也尚未重建至前一天的示範映像。

**引用：**[整份檔案刪除與接續驗證](../../experiments/product-validation/2026-10-05-job-file-deletion.md)。

## 可以連著讀的問題鏈

- **身分與來源：**參考選單改名不斷來源 → JD 改文不等於來源核對 → 固定 Memory 來源及按需 diff；相同詞彙在不同階段有不同保證。
- **編輯與可用性：**巨型 mutation → VFS 第一筆建立缺契約 → 關聯式業務操作 → 小型模型的自然旅程驗收，不能只比較工具數。
- **人機共同工作：**競爭的兩份稿 → 一份目前稿 → 編輯／核准語意再修訂 → 新目標候選預覽與正式完成邊界。
- **驗證層次：**固定資料與程式測試 → 真 PG／固定 provider → 真瀏覽器 → 自然模型 → PDF 成品 → 打包交付；每層補不同的盲點，不互相冒充。

各節保留原始條件；正式報告採用時再核對團隊分工與可公開材料。
