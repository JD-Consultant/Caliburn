# JD 工作計畫：只有指引與指引＋Plan 的有限比較

**施測協議，2026-10-08。** 使用者在確認元件分工後授權開始實作與測試；沿本次對話既有真 API 使用授權及取消整批時間截止的指示，執行以下有限比較。工程代理採 US$4.00 估算費用及本協議的用量上限約束本批，不沿用舊批剩餘額度。正式外送前核查 runner、材料及 guard，凍結 manifest；執行狀態與結果以本批原件及[施工證據](../../../plans/evidence/jd-work-plan-2026-10-08.md)判定，不以本協議宣稱已執行或通過。

元件責任由[架構文件 §2.1](../../../architecture/system-boundaries.md#21-長任務的元件分工)維護，Plan 內容與用法沿[詳細設計 §10](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md#10-jd-工作計畫內容與用法)。有效狀態沿[目前決策](../../../current-decisions.md)及 ADR0082；舊「只記未知」八場比較仍依其[協議](../interview-plan-comparison-2026-10-07/protocol.md)與[結果](../interview-plan-comparison-2026-10-07/results.md)查閱，不能當成新 Plan 的效果樣本。

## 1 要回答的問題及唯一主要差異

核心問題：在相同顧問方法、資料與訪談資源下，持久的 JD 工作計畫是否改善最終正式 JD 的重要涵蓋、責任與條件忠實度，並減少換題／換窗後遺失的未完工作，而沒有增加無據內容或不必要重問？

| 組別 | 相同部分 | 差異 |
|---|---|---|
| P1：只有指引 | 相同分析／JD／顧問指南、共同焦點與使用時機指引、Memory／原話、JD 工具及相同既有獨立 Diff 能力。 | 不提供持久 Plan 正文、Plan read／edit 或 Plan 壓後投影。仍可使用既有上下文自主規劃。 |
| P2：指引＋JD 工作計畫 | 同 P1。 | 增加同一份可持久 Markdown Plan、既有 read／edit、合法接續全文與必要的工具使用說明；內容為短大綱、目前焦點及未完工作。 |

共同指引應包含：先輪廓後深入、以交付成果為目標、已知未入稿仍是工作、部分完成／未知／拒答／更正的界線，以及每輪定位、實質變動才修訂安排、離開焦點前回看整體、交付前核對實際 JD。不能把這些更好的方法只交 P2，再宣稱收益來自 Plan。

P2 專屬說明只負責這些安排如何寫入、讀取、精簡及更新正文，不另加一份品質方法。兩組均不新增獨立 planner／evaluator 或固定每輪規劃呼叫。實際 outgoing instructions 與 ordered tools 需保存並核出預先列明的唯一差異；指引 hash 相同不足以代替有效 request 核查。

Plan 與 Memory 共用的 V4A patch 是正文局部修改機制；變更檢視（Changes，下文 Diff 均指此獨立能力）的文件稱呼已統一，工具名稱及行為未變。兩組固定相同既有 Diff 能力及其使用方式，不先修改 Diff、不增加輪前提示，也不把新提示的驗收列為 Plan 比較前提。

這是「共同方法＋持久 Plan 能力」整體增益比較，不能再細分宣稱效果全由儲存、格式或某一句提示造成。若需比較剩餘清單與短大綱，應另案控制變因，本批不混做。

## 2 案例、配對及資源對齊

正式安排兩種合成職務、兩種接續條件，每條件 P1／P2 各一場，共 **4 對、8 場 fresh journey**。每場空白 JD、空白 Memory、無先置 Plan，獨立 job file 與隔離 PostgreSQL schema；不得沿用舊 P1、預先代寫 Plan 或把另一組答案補入本組。

| 配對 | 職務 | 接續條件 | 主要可觀察反例 |
|---|---|---|---|
| W1 | 物流中心倉庫管理員 | production 原生門檻 | 收貨／盤點／退貨／帶教的全局涵蓋、盤點換題後返回、責任更正、已知未入稿。 |
| C1 | 成人教育課務行政專員 | production 原生門檻 | 代課換題後返回、退費權限、拒答與一般流程區分、重要低頻工作。 |
| W2 | 同一倉儲輪廓的新檔案 | 一次受控 A within-Work compaction | 未完工作在實際換窗前後的接續；人工改稿後不按舊安排覆寫。 |
| C2 | 同一課務輪廓的新檔案 | 同上 | 跨窗後保持未知的原意；人工改稿與未完成成品工作。 |

這是兩種接續條件的有限重複，不能把 r1／r2 當成完全同條件的統計重複。建議凍結順序為 W1-P1、W1-P2、C1-P2、C1-P1、W2-P2、W2-P1、C2-P1、C2-P2，以平衡先後位置；執行中不依品質換順序或挑重跑。

沿既有 driver，每場最多 **20 個 Turn，含相同共同收束輸入**。前段依實際問題回答，不強制兩組取得同序事實；第 20 Turn 僅要求整理及保存已確認內容、指出未知，不提供新事實。較早由 driver 收束、資源停止及模型自行宣稱完成分開記錄。共同收束不是自然完成證據，也不要求當輪最後一問一定另有答案。

相同 Turn 上限不代表相同 token 或相同已取得資料。因此同時報告相同 Turn 前綴的成品差異、實際有效回答數、工具／生成／壓縮成本與等待時間；不靠增加 P2 訪談輪數補出勝負。若兩組事實披露不同，分開判斷「有無取得」及「取得後有無正確成稿」。

施測前先做最多兩場各 6 Turn 的機制 pilot，兩組各一場，另立原件且不進正式品質樣本。Pilot 用公開合成內容核對 Plan 建立、局部 patch、正式保存及接續使用；是否真的 compaction 另查，不以 pilot 名稱當證據。正式必須用新空白檔案。

## 3 回答者、可見返回機會及共同人工改稿

### 3.1 凍結事實與逐題裁決

以舊 [private_facts.json](../interview-plan-comparison-2026-10-07/private_facts.json) 的倉儲／課務工作為基底，保留原事實內容、否認範圍及重要性。本批 [private_facts.json](private_facts.json) 另存新 availability cue 與人工改稿情境，隨新 manifest 凍結；舊 oracle 及其 hash 保持原樣。

逐題沿[舊披露政策](../interview-plan-comparison-2026-10-07/disclosure-policy.md)的匿名語意裁決，關鍵原則如下：

- 裁決者只見實際問題、所需近期公開脈絡、該案例已正式提交的披露狀態與凍結事實，不見 arm、Plan、成本或另一組成果。不得兼任持有 arm metadata 的營運監測；無法隔離則明列匿名限制。
- Keyword candidate 只作候選，不能自行放行。Compound 最多四個明確相關且當下可取得的 frozen fact；一般流程不能冒充未提供的特殊情境答案。
- 已知確認、真正未知、指涉不明、拒答及沒有提問分開。真正未知只保留未知；不得因問句含「退費」便重播一般退費答案。沿舊課務 r1 的公平性失敗設回歸反例。
- 新更正按既定相關提問及已披露前提觸發，不按固定第幾輪偷偷補正。拒答只有凍結情境中明示重新願意談時才重開；一般流程不跟著被封鎖。
- `pending → decision → selected → HTTP accepted → formal source_id` 全鏈保留。按當次 accepted 身分核 source，不用文字相同就把歷史重播誤算成當次披露。未送答案、遲到裁決及最後 Turn 後的未用選答不列已取得。

裁決最多等 300 秒，超時停止而不自動用 keyword 或未知答案代替；讀到檔案後仍再核是否逾時。這是單次操作失敗界線，不恢復舊批已取消的絕對截止。

### 3.2 返回機會必須是模型能辨認的機會

舊 oracle 在換到帶教／退費後隱藏解鎖後續答案，但不一定給顧問可見的新線索。新批不能把「oracle 私下已可回答」直接當模型應回問的機會。

新版本保留盤點／代課的未知與轉題，再於**首次符合前提且實際送出的新主題回答**附加一次固定短句：

| 情境 | 前提 | 給顧問可見的固定短句 |
|---|---|---|
| 倉儲 | 盤點未知已正式披露，其後首次披露帶教內容 | 「剛才說盤點後面怎麼處理想不清楚，現在我想起一些了，可以再說明。」 |
| 課務 | 代課後續未知已正式披露，其後首次披露退費內容 | 「剛才說代課後面怎麼接想不清楚，現在我想起一些了，可以再說明。」 |

兩組採同一條件及原字串，不按輪次、arm、Plan 內容或是否漏問而改觸發。短句只表明可再說明，不提供責任答案、不指定問法、不催模型維護 Plan；實際後續資訊仍要由相關回訪取得。它是明示提示下的返回機會，不能稱完全無提示的自主找回。

有效返回機會至少需：重要未完範圍曾公開、後續出現可見的新線索或可回答切入點、沒有有效拒答、當下仍有後續訪談機會。逐個記錄開啟位置、可見線索、有效窗口、後續處理與結果。未觸發前提、線索只在未送選答中、線索後立即到共同收束，均列未形成機會；不算失敗或成功。已知可推進但被較重要方向暫留，依實際安排及終局結果判讀，不強制下一句必須回問。

同時保留沒有新線索的未知與拒答作對照：正確保存且不徒然重問是有效界線，不把所有未返回均算失敗。要查的原命題，例如「是否普遍適用」，不能以問到頻率冒充已返回解決。

### 3.3 共同人工 JD 改動情境

兩組使用施測版本相同的既有 `read_jd_changes` 與目前稿讀取能力，凍結其工具、指引與可見資料規則；不要求先增加或修改 Diff 提示。相同是能力及規則，個案 revision／diff 自然可能不同，不能要求業務資料 bytes 相等。人工改稿只作 Agent 運用獨立能力的整合情境，觀察它是否實際讀取、正確判斷及更新工作安排；不是 Diff 新功能驗證。

每場在第 10 Turn completed 後、第 11 次員工輸入前，且顧問非 active 時，安排一次由既有正式 HTTP 寫入的人工編修，僅使用兩組相同公開初始原話：

- 倉儲：把最初收貨差異工作表達為「核對採購單、送貨單與實收數量，拍照通知採購；拒收或退換貨由其他權責者決定」。
- 課務：把最初臨時缺課工作表達為「接獲講師不能到的消息，通知主任與學員；代課人選不由本人決定」。

人工編修者只看匿名目前 JD、該公開初始原話及上列文字，不看 Plan、arm 或私有事實；定位已有相應 task 以局部修訂，保留其他有效細節。沒有相應 task 時，可沿同一公開語意建立所需 area／task。選定 target、原 revision、正式 command、實際 diff 及保存結果全部留存，不直接寫 DB、不直接改 Plan／Memory、不注入「你忘了」提示。

這是固定時點的人工 UI 操作模擬，不是固定輪次披露新員工事實。目的是核人工先處理之後 Agent 能否運用目前稿及既有 Diff 判斷，而不是讓人工幫任一組補 oracle。若目標欄位已完整等價，記為 `no_op`；若第 10 Turn 前已停止或缺少可合法編修的狀態，記為未發生。不得為湊事件故意先破壞 JD。

只在兩邊都有相關人工改動及後續 A 時，把它列為配對機制對照；單邊命中仍保留，但不宣稱配對效果。Plan 先前是否真的有相應待辦、後續是否重複寫入、是否覆寫人工新稿，另逐項核查；不能因一次人工改稿就宣稱已覆蓋所有過時 Plan 情境。

## 4 真正的換窗及工程可用性

W1／C1 沿施測版本的 production 原生門檻，不為取得事件改門檻。W2／C2 延續已修正的[受控機制](../interview-plan-comparison-2026-10-07/diagnostics/repaired_comparison.py)：只在隔離程序把 A 的 within-Work exact-count 門檻設為 45,000；第一次**官方 saver 已提交且重新讀驗的 A adopted within-Work C**後恢復該版本原門檻。兩組同條件；B 的門檻及模型不變。不能在收到 provider compact 回應或 pre-work C 時提早解除。

每個「確實跨窗」主張須有完整證據鏈：provider C 原 item hashes、對應 official saved adopted checkpoint／stage、後續 A request 採用完整 C prefix。P2 再核同位置的保存 Plan projection 與下一 A 的 exact plan item；P1 則核沒有 Plan 正文／工具／projection 洩漏。公開 raw body 可重算者直接重算；opaque item 只報完整 hash witness 一致，不能說公開資料已能獨立重算未披露 bytes。

C 發生時重要未完工作是否已出現、後續是否還有處理機會另行標註。若只在缺口出現之前 compact，最多證接線；不能聲稱「缺口跨窗不遺失」。沒有實際 A within-Work C、只見 B 壓縮、只有 count／嘗試、或共同收束後才有 C，均不算指定情境通過。不得為獲得漂亮證據臨時調低單組門檻、補 filler 或人工注入 Plan。

Pilot 先查 Plan 建立／局部編輯／正式讀回與新輪使用。形式拒絕、沒有建立 Plan、兩組既有能力與凍結基線不符、observer 損壞原 stream，均先停下診斷；相關失敗和用量保留。修復後須新 manifest／新樣本，不能用一整批空 Plan 判新內容方案無效，也不能刪去失敗說工具全成功。

## 5 成品盲評及行為判讀

沿本批[匿名 JD 判準](blind-jd-rubric.md)與既有六個語意維度及三份指南，不新造總分，不用字數、任務數、Plan 長度、打勾數或模型自評作品質。新版判準的案例內容按本次 oracle 凍結，不能沿舊 hash 宣稱新資料相同。

分兩層判讀，先鎖內容結論，再看 arm：

1. **正式成品品質。** 評閱者只見同一匿名目錄中的正式 JD、正式員工原話、固定 revision 的可回查來源，以及必要的公開人工改稿文字／差異。人工改稿不是新的事實來源。不得看 Plan、工具、成本、模型過程或營運目錄名。先逐案判「有據可用／仍有重要缺口或錯誤／尚無可用成品」，再做四個匿名配對；所有結論與來源 hash 固定後才解盲。
2. **機制、行為及披露稽核。** 品質鎖定後，依原 request、員工原話、Plan、工具結果及正式 JD 核有效返回、已知未入稿、語意變形、完成短句過度概括、人工改稿後行為及跨欄更正。先依公開事件凍結機會清冊，再讀 Plan 判斷處理方式，不以有筆記的項目才選為分母。逐題另核 oracle 放行是否正確。

未揭露的重要 oracle 工作與「已揭露但沒有正確成稿」分開；真未知／拒答有其成品限制，但如實保留不能當成捏造的對照劣勢。公開有據但未取得後續更正，亦與憑空寫出無據內容分開。更多細節若加入錯誤責任，不能抵銷重要缺口。

每個關鍵工作方向保留以下觀察鏈，而不是一個「有沒有問」分數：

```text
已形成工作方向 → 出現可處理機會 → 選擇返回／編修
→ 取得正確理解或達到工作結果 → 正式 JD 有適當且一致的表達
```

各環節可以未發生。例：Plan 保住「適用範圍未知」但只問頻率，是返回語意不正確；問到但員工仍不知道，是未取得答案；寫入候選但 Turn 失敗，不能列正式成稿；成品局部改對而其他欄仍相反，是尚未完成一致性修正。

報告同時列每場的有效返回機會與結果、不必要重問／拒答重開、問句負擔、已披露未入稿、無據或錯誤主張、過早完成聲稱、Plan 維護及讀取成本。Plan 不建、工具失敗及恢復失敗列機制故障，不與內容策略效果混為一因。

四對均保留，允許結論為較好、較差、無可辨差異或各有得失。重要穩定性反例不得被平均遮掉。若關鍵情境未形成，只能說該情境未驗到；不因要宣稱完成而補事實、重播最佳結果或事後新增測項。四對合成訪談不足以宣稱統計顯著、真人負擔下降或所有職務皆改善。

## 6 停止、費用估算與批次界線

既有 driver 的共同 `CLOSURE` 與 `CONTINUE` 原字串可沿用。沒有問題而只是摘要時，最多兩次不連續的中性提醒，仍無主動推進就共同收束並記錄；不能指定下一題或補 oracle。它仍是受控訪談，不得把 driver 收束寫成自然完成。

每個 Turn 沿既有 700 秒觀察上界、Memory 收尾沿既有 180 秒有界觀察；超時是未完成／需診斷，不是模型已停止或准許重放。費用、用量不明、來源漂移、原件損壞、policy 違反、工具機制失效或 guard 超限都停止新外送。使用者先前已取消時間截止，本候選不延用舊批任何絕對日期／四小時截止；整批仍由有限案例、Turn 與用量界線限制。若 runner 仍強制要求整批秒數，須在實驗 guard 明確處理此相容性，不偷偷複用舊 deadline。

費用規劃先用舊八個有效案例的觀察值，不把其當本批承諾：合計 US$1.366484375，每場 US$0.129192650–0.245032485；A generation 728 次、Memory generation 467 次、A compact 9 次。舊結果也顯示 40M counted input 不足，不能照抄第一次正式 cap。這些是舊 frozen 費率的 usage 換算，非最新價格承諾或 provider 發票。

估算基準：8 場 × 舊最高每場 US$0.245032485，約 US$1.9603；再保留 50% 給新 Plan 維護、人工差異及行為變動，約 US$2.9404。機制 pilot 暫留 US$0.20，已知消耗規劃約 US$3.14。舊 compact 最壞單次 reserve 最高約 US$0.8375。本批採 **US$4.00 累計估算費用上限**，pilot 與正式共用；未知 reserve 不釋放，上限不足時停止，不保證一定完成八場，也不將估算上限當 provider 帳單保證。

整批凍結上限為 pilot＋正式合計最多 2,600 generations、6,000 outbound、150M 累計 counted input、32 compact；pilot 最多 160 generations、2 compact、兩場各 6 Turn。2026-10-08 依 [GPT-6 Luna 官方價格](https://developers.openai.com/api/docs/models/gpt-6-luna)核對 Standard 每百萬 input／cached input／cache write／output 為 US$0.10／0.01／0.125／0.50；超過 272K input 的整個 request，input 及 cache 費率乘 2，output 乘 1.5。本批使用 `service_tier=default`，實際 rates、模型、runtime、上限及授權來源寫入 manifest；運行中不得自行放寬。

沿 [BatchGuard／GuardedTransport](../interview-plan-comparison-2026-10-07/guard.py)及[已修正 stream ownership](../interview-plan-comparison-2026-10-07/append_stream.py)核帳：A generation、A compact、B1／B2、計數路由、失敗／重試／未知預留分項，全部出站 attempt 入帳，未知不釋放。Pilot、正式及任何機械恢復納入同一新研究累計帳務，不重設以繞 cap；舊研究帳務另保留，沒有宣稱其 reserve 已釋放或舊授權剩餘即屬本批。

本批一案只安排一次 fresh journey。可恢復中斷只沿產品原 request／operation 語義與已凍結處置接續，不能重新發新員工輸入充當重播；無法恢復則保留未完成。任何需 fresh 補案的決定先記明機械理由、來源與額度，另凍結 revision，不按品質結果選案，不覆寫舊 raw。已完成但表現差的案例不可重跑替換。

## 7 沿用設備與 runner 驗證接縫

沿既有本機 loopback 產品 HTTP、真 PostgreSQL 隔離 schema、正式 migration、同一顧問／Memory pipeline、SDK 與 checkpoint saver。RAG 兩組關閉；模型與 effort 沿當時有效產品設定一致凍結，不使用不同模型補償任一組。舊實驗 runtime 的修正結論可以沿用，但實際 Python／鎖檔版本須記錄，不因有舊證據便宣稱新環境已驗。

金鑰只經既有 reader 在執行時讀入記憶體；不輸出金鑰、環境或 headers。公開 provider 原件排除 encrypted content，保留完整原 item 的 hash witness。啟停先核自有程序及 listener，沿 runbook；不停止未確認的服務，不清舊 schema／volume。這些是沿用已有執行邊界，不新增產品保存機制。

下表列出新批 runner 的責任與驗收接縫。新入口組合既有機制，修改保存在本實驗目錄並凍結；舊 runner、協議、結果與 manifest 保持可重現。

| 既有來源／接縫 | 新批需完成的差異與核查 |
|---|---|
| [run_batch.py](../interview-plan-comparison-2026-10-07/run_batch.py)：`journey`／`run_case` | 新批 paths／schema 前綴／排程；兩組皆為新共同指引；正式 HTTP 人工編修事件；精確 accepted→source 核對；裁決等待 300 秒及遲到拒用；不得照搬 120 秒原入口。 |
| [manifest.py](../interview-plan-comparison-2026-10-07/manifest.py) | 凍結新 protocol、oracle、披露政策、人工編修規則、共同／P2 指引、完整 ordered tools、兩組相同既有 Diff 能力與可見資料規則、模型／runtime／價格及可用額度；新 source snapshot，出站前驗 bytes。舊 `source_hashes` 只掃舊目錄，不能直接當新檔已被 freeze。 |
| [conditional_answers.py](../interview-plan-comparison-2026-10-07/conditional_answers.py)及 oracle | 以新檔保存兩種 availability cue 的一次性、先後及正式送出資格；保留純未知／compound／更正／拒答反例；anonymous semantic review 才能披露，不將 keyword fallback 用於 paid。 |
| [evidence.py](../interview-plan-comparison-2026-10-07/evidence.py) | 沿固定 revision/source_ref 收集來源；匿名 bundle 加必要公開人工編修脈絡，維持無 arm／Plan／成本；全部配對放同一匿名目錄，mapping 隔離。 |
| [measurements.py](../interview-plan-comparison-2026-10-07/measurements.py)、[repaired_comparison.py](../interview-plan-comparison-2026-10-07/diagnostics/repaired_comparison.py)：`bind_case_observers` | 沿實際 adopted stage 才解除 45K；新增未完工作位於 C 前／後的證據索引、P1 無 Plan 洩漏，以及人工改稿整合情境的既有 Diff／目前稿實際讀取原件。新入口不可沿舊 hard-coded manifest、既存 P1 reuse proof 或截止啟動。 |
| [guard.py](../interview-plan-comparison-2026-10-07/guard.py)、[append_stream.py](../interview-plan-comparison-2026-10-07/append_stream.py) | 沿有界 reservation／count／原 stream 清理；新累計帳務與用量欄位；確認取消整批時間截止的相容做法，保持單次操作有界。未知帳務停止，任何中斷不重設 reserve。 |
| 新 runner 的離線測試 | 兩組允許差異核對、空 Plan 與編輯拒絕、availability cue 不提前／不重播／未送不生效、課務真未知不重播一般答案、人工編修 no-op／未觸發／成功及兩組既有 Diff 能力一致、原 C 全項和位置、預算與機械恢復、匿名資料不洩漏。測試需在零 key／零 provider 路徑可執行。 |

共同方法與 Plan 說明已按設計實作，工程結果沿[施工證據](../../../plans/evidence/jd-work-plan-2026-10-08.md)。Changes 維持兩組相同的既有能力；實驗 runner 不另造 production 差異提示或防過時機制。新入口為 [runner.py](runner.py)，提供零 key dry-run、freeze-only、pilot 與 formal；只有凍結核對及 pilot 機制審查通過才准入正式比較。實際命令、manifest 與結果保存在本批目錄，不用協議文字代替執行證據。

本批交付應有：凍結 manifest 與精確來源；8 場及所有未完成原件；逐題披露與人工改稿 audit；正式 JD／固定引用；匿名品質鎖定及解盲 mapping；有效返回機會清冊；實際 C／Plan 接續證據；累計用量與 reserve；清楚區分品質結果、機制通過及未觀察情境的結果報告。研究依據沿[既有公開比較](../../../research/work-analysis/2026-10-06-long-interview-planning-and-focus-research.md#20-2026-10-07-memory-與-plan實際公開設計比較)，本批不以更多廣搜或漂亮筆記取代這些證據。
