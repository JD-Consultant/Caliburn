# CT40：正常訪談接回驗收——局部通過，保留即時修補語意問題

2026-09-09 · LLM-Q019 · G8仍OPEN · 非完整職位／長訪談全面驗收

## 1. 結論與閱讀路由

CT39 的「候選提示＋B1 high，A/B2 medium」已經從真實服務入口運作。5輪合成訪談都完成，2批自然背景整理正常發布；初次「印象中」在**詳記、候選與工作理解**均未升格為肯定。案例差異、工作頻率、責任界線與未回答事項能保留。

**但不能說全部修好：**第4輪主顧問實際用了C即時修補，更新核准者成功，卻把雲岸的驗收補充寫成新增段落，沒有改掉同主題舊「尚未確認」。新舊兩段並存，獨立回查因此建議再確認員工已回答的內容。最後自然收尾沒有通知B，這個矛盾仍在。沒有偷偷調提示、人工改Memory、增加驗證模型或把失敗從結果刪掉。

- 前因：[CT39接線結果與引用](2026-09-09-ct39-extraction-adoption-results.md) → [本次計畫](../plans/2026-09-09-ct40-normal-interview-verification.md)。
- [可讀逐輪訪談／最後Memory](evidence/2026-09-09-ct40-transcript.md)。
- [完整機器證據](evidence/2026-09-09-ct40-normal-interview.json)：請求、工具、詳記、候選、Memory前後版本、原文引用、用量、版本、測試腳本均封存；opaque reasoning僅存雜湊，不存內容或金鑰。SHA256 `91fe77916b222c47234c41d45f848d7a13a9205cb48f889426226e099049e787`。

## 2. 實際環境與範圍

獨立 worktree `codex/analysis-only-agent`，基準 `8cad23ea`；新空白PostgreSQL資料庫／文件，沒有CT16等舊Memory種子。沿既有CT15 runner：FastAPI TestClient → 真正 `open_service` → 真LangChain/SDK/OpenAI API → PostgreSQL Saver/Store；不是用假模型回應證明品質。

- 模型皆 Luna。B1兩次請求5、16實際為high，其餘29次medium；`all_turns`、既有Memory工具與錯誤處理不變。
- 實驗設定：單次输出8192，原生compaction閾值12000，背景poll 2秒、recoveries 0，未設文字fallback。不是變更產品預設。這個小情境**沒有實際觸發compaction**，只能確認reasoning不透明items有返回並再次傳入，不能據此宣稱壓縮後仍完整記得。
- 5輪員工內容均為固定合成前端案例；先建立初步資料、補青禾，再補雲岸差異，核實責任，最後自然段落收尾。刻意包含清楚的「不確定／先不要下結論」措辭，比真實含糊訪談簡單，不是泛化正確率。
- 只讀Memory診斷使用既有空近期Context reader，與正常A訪談分開標示；沒有把全部員工訪談或oracle塞給它，也沒有強迫它走到原文。
- 原定30次／US$0.15；第22次後估費US$0.01917469，兩批B工具往返超過最初估計。依Owner既有可提高／agent自行決定授權，**先commentary告知、再記帳本事件**，只把agent自訂請求數改40，US$0.15不變；不是Owner另外明確回覆40次，也不是產品上限。帳本已closed，不續跑。

## 3. 實際流程與結果

| 段落 | 請求 | 實際觀察 |
| --- | --- | --- |
| 訪談1 | 1–2 | 確認接案型前端而非固定兩網站；讀既有分析Skill，接著問需求確認／交付責任。 |
| 訪談2＋B第一批 | 3–11 | 青禾產品負責人只是「印象中」核准者，待核合約；A自然通知B。B1 high→B2 medium發布rev1，三層都保留不確定，維護問題尚未回答。 |
| 訪談3＋B第二批 | 12–22 | 雲岸只課程報名／防重送，青禾才有會員及金流狀態；每週五整理所有專案，不限付款。A自然通知B，rev2保留兩案區分及未回答事項。 |
| 訪談4／C | 23–26 | 員工核實青禾由營運主管核准，並確認雲岸也採共同驗收流程。兩次repair回`applied`，rev2→3→4；核准者正確，但雲岸新增同名段落，舊未知未移除。 |
| 獨立只讀回查 | 27–30 | grep→讀工作理解→讀較早詳記，三工具success。能答對案例、頻率、核准者；明確看出雲岸兩種記載，建議再次確認。沒有讀原始對話；不是無矛盾回查通過。 |
| 訪談5自然收尾 | 31 | 不新增實質內容；A允許下次補維護，不宣稱整份職位已完整。0工具／沒有B通知；rev4未變，背景idle。 |

查新資料後核准者更新是**C medium**完成，不可寫成「本輪已驗B1 high抽取後續確認」。最後B processed-source到第3輪；第4–5輪有771個可見字元未進下一批B，其中第4輪更正已部分經C存入。B未排程不是執行失敗，也不代表B將來一定能收整這個矛盾。背景tick重疊警告來自既有單實例排程，兩批均完成；沒有因警告重啟Docker或另加worker。

## 4. CT40-Q01：新增代替更新（OPEN，不施工）

**已觀察，不猜模型內心：**請求23產生的patch只替換青禾核准者句子，並以`+`新增第二個雲岸標題與驗收內容；沒有刪除或替換原雲岸段落的「尚未確認」。請求24只讀導覽，請求25更新導覽。工具依patch正確套用，沒有`invalid_edit`／相符位置錯誤證據，故不以換patch引擎或重試傳输作解釋。

原程式責任也吻合：`repair.py` `_edit`用既有SDK patch；`_validate`→`staged_texts`驗格式／引用及正文導覽存在，不判斷語意是否重複。`applied`是寫入成功，不是語意保證。既有`MEMORY_EDIT_GUIDANCE`已要求最小修改、保留未變資訊，所以**不能說完全漏寫prompt**，也不能僅憑一例判定A medium一定不行。

**上游資料流已定位：**請求13的`read_file`（`call_IjGeoJLFBbE1mQnitqrHMdpy`）發生於B第二批前，讀的是rev1，還沒有獨立雲岸段落。B在請求16–22產生rev2、加入雲岸段。第4輪請求23仍帶著那份歷史讀取結果；system已提供`Initial guide publication revision: 2`及指向雲岸既有段落的導覽，但A未重讀rev2正文，第一個動作直接`repair_memory`。這證明缺少「背景更新後、修補前讀最新受影響內容」的實際動作；與沿用舊讀取結果相符，但不能證明模型內部究竟如何推理。下一個局部研究應先核對現有版本／讀取回饋，不把問題縮成只加一句「不要新增」。

另一個相關限制：C保存正確原文引用於publication receipt，但現有正文保留較早詳記連結，新增雲岸段沒有新的詳記（因尚未B抽取）。獨立reader本次沿舊詳記回查，沒有取到修補回執。後續是否需改善修補後的可見回查路徑，須先核對既有設計／框架接點，不能因此憑空新增另一份來源表。

**目前僅建議下一個局部研究／對照：**背景已更新Memory後如何讓修補依最新受影響段落執行、既有主題如何就地更新避免舊「未知」留在正文，以及既有工具回執能否幫模型看到修改後相關內容。先比對已用提示及官方做法再選；不增另一個審核Agent、不強制每輪B、不全面升high、不復活CT35專用final攔截。未授權／未實作新的修補機制。

## 5. 驗證數字與限制

- **31次實際模型請求，全部HTTP200/completed；估US$0.03033571**，沒有未知費用預留，帳本closed。不是帳单精確金額。
- 175,320 input（其中101,468 cached）、9,036 output（**已包含**2,175 reasoning），總184,356 tokens；這是全部請求累計，不是單次Context長度。最高單次input11,070。
- 正常A 13次、B1 2次、B2 12次、獨立reader4次；沒有為本次品質判斷另叫LLM judge。
- 新跑7個既有CT39模型接線回歸：7 passed／7.43秒；另本地帳本角色／費用／請求數／closed護欄測試通過，0網路。沒有重跑551項全suite，先前綠燈只在CT39。
- 真PG重開後Memory head／內容／cursor一致。全部5組問答（10訊息）逐字一致；兩個詳記原文窗口及兩筆C來源回執的每頁片段均與canonical訊息逐字一致。**這是程式只讀稽核，不是模型已成功回查第4輪原文。**
- 封存腳本第一次誤將新增訪談前後的canonical訊息數也要求相同；修正為只比較Memory欄位後通過。這是測試斷言問題，沒有改產品或重跑生成。
- 本輪`src/analysis_agent`與`tests`相對`8cad23ea`無diff；未改模型／prompt／schema／工具／Skill／排程設定程式，未動production或舊資料。
- Newton作唯讀覆核，**就已讀範圍**未提出阻擋PARTIAL/G8 OPEN封存的新Critical／Important；確認重複段落、舊unknown、回查重問已揭露。未獨立完成全部成本／hash／source逐筆重算，也未核完後補的舊read時間線；不能稱全部證據獲雙重驗證，更不是產品PASS或merge核准。

## 6. 官方對照的效力

2026-09-09重讀資料，不新宣稱「廠商同意就一定正確」：

- [OpenAI GPT-5.6 effort 指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#reasoning-effort)：先確認提示與任務baseline，用觀察選effort，不能由本次C語意問題直接推出所有角色都改high。
- [Anthropic Memory prompting guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)：Memory散亂時可補強維護最新、一致、有組織的內容；這支持先校準現有維護行為，不是本案新提示已證實有效。
- [Anthropic替換工具契約](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#str_replace)：成功與找不到／多重匹配是操作層回饋，並非語意驗收。不能將其字串替換工具與本案V4A patch說成完全相同。
- [既有OpenAI整併原提示研究](2026-09-07-incremental-memory-quality-calibration.md#直接來源與設計邊界)記錄增量維護／保留正確內容；B2的規則不能直接推定C有相同表現。此舊來源本輪只沿引用，不冒稱重新研究了完整Codex底層。
- [OpenAI計價](https://developers.openai.com/api/docs/pricing)：本輪短Context／standard Luna input0.20、cached0.02、cache-write0.25、output1.20美元／百萬token。由實際usage估費，非以output以外再加一次reasoning。

## 7. 下一步與防止重複討論

保留CT39採用設定；**這轮不是「全部high」的比較，也不重開Memory分層／Store／框架選擇。**下一個待審問題是CT40-Q01，先用現成失敗patch與前後Memory研究一致性修補及可回查性。若Owner仍希望先放下C，則只記問題，後续长訪談必須計入此風險，不能說背景「一定會修」。本次未開始新的C修復。
