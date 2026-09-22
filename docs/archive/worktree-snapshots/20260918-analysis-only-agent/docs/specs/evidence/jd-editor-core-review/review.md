# 整體核心審查：有限修正與驗收

2026-09-12；基底為已接受Task6 `3d0445ae2d4b3bb2ef3493f703ea18f0108b0eef`。第一輪Claude整體review為Spec FAIL／CHANGES REQUIRED，F1一項阻擋。Root核對原需求及程式後接受F1問題，定為Important使用阻斷；未觀測到靜默資料遺失，不沿用Critical分級。F1–3與最後R1/R2均已獨立APPROVED，root核對hash／實際結果後接受核心隔離範圍。

## F1：過時的手改缺少同頁出口

Root獨立RED：confirmed stale已保留候選，重新讀取後editable仍r1而server已r2，1FAIL／1PASS；一般未知結果的buffer守衛仍PASS。原RED期望直接refresh變current，只證明current不可達；root採用修正時改成明示動作，不把RED的自動採用期望當產品需求。原RED輸出與最後測試保留；原RED測試檔未另凍結，不主張前後逐byte相同。

採用原旅程§4/5：原稿不因普通GET覆蓋，新增使用者確認後的「捨棄畫面修改並載入最新稿」。新`loadSavedHead`先成功讀完整current，再換唯一editor；保留聊天與已送出候選。未確認結果不可用此動作，讀取失敗保留原buffer/base/chat。沒有HTTP寫入、rebase、merge、新store或AI動作。若是同revision還原手改，也經原Plate重建接點更新真editor，避免僅改React狀態。

不採review建議直接調`discardBuffer()`：它也清掉聊天，而且若先清dirty再讀、讀取失敗會喪失正確狀態。原方法繼續只供已同意的離頁捨棄流程。候選重送成功但畫面仍有後來手改時，notice明示只有先前候選已保存，畫面手改尚未保存。

最後測試核：confirmed stale→explicit current→保留候選／聊天→複製需要內容→明示捨棄舊候選→以r2新key保存；未知不換稿；讀取失敗保留；候選成功但新dirty維持。真Plate DOM另核同r1及新版r2、取消confirmation零read、唯一editable及聊天不清。

## F2：一份未知人工結果阻止其他文件close

Root真service/graph、SQLite catalog與InMemorySaver，注入`_reconcile_manual`的PublicationUncertain：原碼1FAIL，後續文件沒處理。僅對該已知例外保留該文件未解狀態並continue下一份，不吞其他例外、無fake receipt、不改停止證明或DB權責。沿同close既有逐文件未知处理；與review的pass建議相比，root選擇不繼續操作同一未解文件。PG／新程序守衛另以既有直接案例回歸；此注入測試不稱真DB故障。

## F3：未命名專業項目

`nameOf`依已採旅程§8區分「未命名知識」「未命名技能」，其他仍「未命名項目」。純文案，無關係或schema變更，沿既有render測試。

## 實際驗證

- 最後Web **47PASS／11檔**；build/typecheck/lint全部PASS。
- 受影響Python **86PASS**：shutdown反例、service、conversation lifecycle、read recovery。
- 專用真JD PG／native／managed **19PASS**：close reconcile、admission、PG recovery。與Task6原群組重疊，不累加。
- 新built Web＋新offline API、真headedChrome、真專用PG：**PASS**。新合成空文件`1a5e196e-e398-47b9-aae1-129d01352ea7`，實際打字與另次API保存造成stale；同頁明示載入、候選與聊天完整、重新輸入所需文字、捨棄候選、成功新保存。全程0 POST /runs，0產品provider；保留全部receipt/head/network/AX/PNG。此為短段落恢復，不稱完整自然JD、OS剪貼簿或真人IME；原Task6完整六章旅程证據效力不變。
- 首次Vitest sandbox EPERM、Python缺PYTHONPATH、原RED全部保留。Windows managed外層exit0不作PASS，已讀raw pytest summary。
- 根據既有2026-09-12 React effect／Plate controlled官方接點及本機Next16.3.3 use-client文件；不引進新框架API、不重查已閉合工具／DB設計。明示換稿與保留候選是本案已採產品流程，不能稱大廠統一UI。

## 界線

原整體review明列未讀raw證據及部分schema/native/Memory檔；其結果只涵蓋實際cross-slice讀碼，Task1–6各自接受證據仍負責原範圍。本次提供raw／真DOM案例供窄複核，不用新review冒稱重新審過所有原碼。

P3自然模型、OS真人IME、P5日常入口／備份還原／完整管理UI、P6真人／長訪談、production G6與P7仍未完成。0產品模型費用；Claude工程審查另依持續授權，list estimate不是帳單。無production／Memory策略／schema／依賴變更。

## 最後窄複核與主代理處置

F1/F2/F3 CLOSED後，另接受R1/R2小修：已知終局結果不再重送原key；候選文案區分未知與未保存。最後47 Web、build/types/lint及真瀏覽器再PASS，文件`522255ac-c124-4d48-ae8c-fee9821967ea`，前次原件保留於before-minor。minor reviewer未讀web.log（檔案實在其packet內）且在瀏覽器重跑完成前回覆，最後實測由root獨立核對，不補稱它已看過。

minor review把no_pending說成「寫入從未發生」不正確，root明確不採：它只表示查詢沒有pending／receipt，不能由absence證明未執行。既有原key完整候選出口、跨版本及server終局裁決未變。Reviewer供給的base相等條件亦未採，避免封死原有未知恢復。

R3保留至P5：明示載入與背景revalidate競速時可能只取消動作、缺再按一次的提示；generation仍保護內容。R4保留至P5：既有busy呈現可受重疊操作影響，server gate與active-run鎖仍守資料；原review的停止按鈕情境還依賴之後run狀態改變，並非一般idle載入即可觸發。兩項無已觀測內容遺失／假保存，不為文案與呈現另造並行引擎。

原review與closure各自讀取範圍明列；root完成來源hash與raw summary核對。初始化helper的產品provider為固定transport，瀏覽器0 POST /runs可直接核；helper常數product_provider_calls本身不是獨立證據。這不是自然品質、正式採用或日常可用成品。
