# Task 4 凍結實作獨立 review

2026-09-10；reviewer：jd_task4_review；Topic JD-R002/C03，隔離 G7。

**Spec FAIL；quality CHANGES REQUIRED。**同頁編輯、原生選取／history、canonical API、create 原子保存及效能修正已有實際成果；以下四項是原 Task 4 契約中的具體缺口。修正後只需按 finding 做受影響窄驗收與 diff 複核，不重開框架／產品決策，不重跑全部已通過基底。

## 審查範圍及證據

- BASE `80e29b4a98363f10cffeaf332802adb6f6e29329`；69 檔 source/test/generated 凍結，以 `task-4-review.diff`、`task-4-review-manifest.json`、`task-4-snapshot/` 為準。另讀 root support 兩檔 diff；原 README 11 行研究 hunk 已從 baseline 排除。未改 source、git、DB 或 production。
- 本次同一輪先審 source diff，再讀已確認 final 的 `task-4-report.md`、109 檔 `task-4-files.json`／manifest 及 durable `docs/specs/evidence/jd-editor-task4/web-app/` 的必要 raw/log。schema candidate 2 沿既有獨立 PASS，不重做候選 review。
- 只新增一組純記憶體反例，從凍結 snapshot 的 `useJdSession.ts`／依賴經現有 TypeScript transpile 載入，Node 22.23.2；無網路／DB。結果 `task-4-review-focused-results.json` 包含 HTTP 409／422 明確拒絕、及重開 stale 候選後不相關新保存三個觀察。這是對具名 code doubt 的窄驗證，沒有重跑既有 suite。

## T4-R01 — 明確未 admission 的人工保存會永久困在 unknown

- **Severity：P2；狀態 OPEN。**
- 位置：`experiments/jd-editor/web/src/jd/useJdSession.ts:193`、`:227`、`:236`；對應 `experiments/analysis-agent/src/analysis_agent/jd_routes.py:156`／`:162`／`:171`。
- 違反：Task 4.3a／4.4，員工旅程 §4–5、J04：非法或無法保存的候選要保留並有可操作出口；不能把明確拒絕和結果未知混成無法閉合的狀態。
- 實際路徑：送出前設 `manualUnknown=true`；API 可因 invalid manual envelope／source 在寫 receipt 前直接 422，或因 archived／foreground 新寫入拒絕 409。這些回覆走 `catch`，沒有解除 unknown 或提供已拒絕狀態；`locked` 封住 editor／新保存，`discardCandidate()` 也立即返回。重開仍同 key 重送同非法 payload，因根本沒有 receipt，永遠不會讀到 confirmed failure。
- 窄反例：port 明確回 `ApiError(422, 'Invalid scoped manual submission')`，save→discardCandidate→save(true) 後 `manualUnknown=true`、`locked=true`、cache 未清、兩次皆同拒絕；409 archived 案例相同。非法貼上／過期 source 可讓員工無法修正或明示捨棄，只能離開並再次遇到同鎖。
- 有限要求：由既有 API／生成契約明確區分「此次請求確定未 admission」與真正 receipt unavailable／網路未知，將確定拒絕保留成可處理候選；原問句與 value 保留，允許已授權的修正／明示捨棄出口。**不要只因任何 409／422 就一律推定零寫入**，unknown 與可能已存在的同鍵結果仍須原對帳。加一個真 API admission rejection→Web recover 的窄案例及 unknown 不解鎖反例即可。

## T4-R02 — 不相關新保存會刪掉尚未處理的失敗候選

- **Severity：P1；狀態 OPEN。**
- 位置：`experiments/jd-editor/web/src/jd/useJdSession.ts:180`–`:193`、`:212`–`:213`；`submissionCache.ts:15` 的同 document 單一 key 寫入。
- 違反：Task 4.3a、員工旅程 §4／J04：confirmed failure 的 exact 候選要一直保留，直到員工將該候選轉成持久新提交或明示捨棄。head 已變時，候選只讀展示不能被 current 的新保存靜默消耗。
- 實際路徑：重開後 stale 候選保留在 `candidate`、current editor 載新版；此時 `manualUnknown=false` 可繼續編 current。員工尚未複製／處理舊候選，僅修改 current 的另一段並保存，`cache.write(payload)` 直接用不含舊候選的新 value 覆寫唯一恢復記錄，成功後清 cache 與 `candidate`。沒有 discard 動作或候選轉用確認。
- 窄反例：cache 初值含唯一文字 `ONLY RECOVERABLE OLD TEXT`，load 對帳得到 confirmed stale；current 是另一份 server value。對 current 做 unrelated edit 後保存，新 payload 不含舊文字，cache 及 session candidate 均不存在。這是尚未保存到 server 的候選內容失去最後持久副本，不只是提醒文字錯誤。
- 有限要求：未處理 failure candidate 不得被一般 current save 當作已轉用而覆寫／清除。沿已採用的「轉為新持久提交」或「明示捨棄」出口守住原候選；不要求另建 authority 或通用合併。加 reopen stale→修改不相關 current→save→再次重開仍有原 exact 候選的反例，以及員工明示處理後才清的正例。

## T4-R03 — Clipboard 綠燈實際貼入了不同內容，未證明複製保真

- **Severity：P2；狀態 OPEN（驗收缺口，尚不能推定是哪個產品／OS接點造成）。**
- 位置：`experiments/jd-editor/web/browser/task4-input.mjs:147`–`:161`；`task4-input-browser.json.saved.fragment`／`task4-input-screen.png`，以及 final report 的 clipboard 通過表述。
- 違反：Task 4.4／4.6 與 profile §4 的真 browser copy/paste 完整內容、新 ID 與保存重開驗收。
- 實際材料：script 對原 editor 按 Ctrl+A/C，再換段 Ctrl+V；當時正文為 `工作第二處修正手職務`。但 raw saved 與實際截圖的新增段落為 `資料表保存什麼…jd_head…jd_revision…jd_operation…` 等不同內容，並非複製的 fragment。斷言僅檢查 top-level ID 唯一與段落數大於一，因此任何舊 clipboard 文字都能綠燈。
- 可保留的證據：真 browser 貼上確實發生，保存後有新 paragraph ID；不能從此稱原文／marks／結構／refs 經 copy/paste 全等。原因可能是 clipboard／焦點／harness 時序，現有 raw 未隔離，review 不猜測。
- 有限要求：保留本次原 raw／綠燈誤判沿革，補一個受控真 browser clipboard 案例，先固定／核對實際複製範圍與 clipboard（不靠預存環境資料），再斷言 paste 內容與必要 marks／結構及 fresh IDs、保存重開結果；若實測是產品接法缺陷才修對應接點。這是 browser clipboard gate，與 **OS IME NOT RUN** 完全分開，不要求真人 OS IME 或廣泛跨應用測試。

## T4-R04 — 舊 create recovery 尚未讀入時仍能發新 key

- **Severity：P2；狀態 OPEN（凍結 source 直接成立，未另跑 browser）。**
- 位置：`experiments/jd-editor/web/src/documents/DocumentList.tsx:15`–`:22`、`:31`、`:51`。
- 違反：員工旅程 §6.1／J02：存在 unresolved create，重開應先提示原身分再次確認，不因讀取失敗／等待而配新 key。
- 實際路徑：`pending` 初始空陣列，只有 `await api.documents()` 成功後才讀 localStorage。列表 GET 等待期間建立按钮已啟用；GET 失敗時甚至一直不讀原 create cache。已有 commit-lost-reply 記錄的員工會看到可用的「建立文件」，create() 直接產新 UUID，DB 的 same-key 去重自然無法防止這次第二份建立；`setPending([payload])` 又在本頁隱藏先前恢復記錄。
- 有限要求：將本機 create recovery 的讀取／失敗狀態從列表 GET 分開，原記錄尚未檢查或無法讀取前禁止新 create 意圖；已有 unresolved 時保持原 key 提示。同時在 create handler 守住此條件，不單靠按鈕狀態。只補 existing cache＋slow/failed list GET 的窄案例，不需重跑 PG 原子性。

## 已核成立的部分與效力限制

| 項目 | 本輪核對結果 |
|---|---|
| North Star／authority | 一頁一份 current editor；exact before/after/history/source 唯讀，同 renderer，沒有 accept/reject／第二可編稿。canonical service/PG/native/source owner 沿原實例；schema／API DTO 機械生成，未接 production。 |
| 保存／API | create key＋digest＋catalog＋revision＋head 在一 transaction，key advisory lock／唯一性及 rollback 有固定 PG tests；metadata conditional version 不造 JD revision、UI archived filter 不改內部 catalog；run-by-request 在 ID route 前、查 canonical Human、fingerprint 含 text/selection/abandon_pending。兩 origin CORS／same_origin、scope／原 receipt 優先有實測。上述不消除 R01/R02/R04 的 Web 恢復缺口。 |
| 正文與差異 | 完整 v2、原生 table/list、新增 marks/metadata 可讀；same-ID before/after、空 marks、共享 K/S 兩版各自名稱／解除者及來源 callback 有 component 正證。J10/J11 不誇稱每個排列皆真 browser；source read 不把 Memory path 或模型摘要當逐字原文。 |
| 真 selection／history | 讀過 actual POST：原問句「請改選取」、同 base、anchor4/focus2；fixed transport 真 jd_read→replace_selection，saved 只第二次「工作」改成「第二處修正」。AI batch＋人工兩次 undo/redo、cross-block/missing/stale 反例已見 raw。 |
| 真 browser／恢復 | first-browser 1 editable／8 tasks／1 table、0 page errors；manual commit response-loss、POST 即關頁、stale 兩次重開、run GET-only 恢復／one Human／one run、普通 dirty beforeunload 已有真 browser raw。未把這些固定情境擴成所有 failure recovery 通過。 |
| 新 runtime | root 先前已保存官方 Node ZIP 簽章/hash/license 材料；本次 API worker 580 的 self.node 與對應 binary execPath/version/versions 為 isolated 22.23.2，bridge 回歸實跑。套件 React19.2.4 與 compiled/browser `19.3.0-canary-cbb046ab-20260731` 分列，RSC 無獨立 version 的限制據實記 peer/build identity；436 依賴 inventory 無缺 license declaration，audit 0。未稱全部 MIT 或整機安全認證。 |
| Final 工程驗證 | 已讀 raw final logs：contract27、native68、Web18、API/受影響 owner41；8組命令 exit0，typecheck/lint/Next16.3.3 build 通過。uv VIRTUAL_ENV 被忽略而選 contract project、Starlette deprecation 保留。review 沒有為安心重跑此 suite。 |
| 效能 | 沿先前候選review與438＋92有限對照；採用後完整r2 realbrowser約1.80s ready／2.07s保存confirmed UI／1.50s重開有 raw，0 page errors。這是固定觀測，不是SLO/p95；不拿有/無 profiler 數字互相比較。 |

首敗 selection attempts1–4、source serialization、harness回覆／路由等待問題、完整稿超時與候選1生成union反證均保留，不因本次多數綠燈改判；R03 是本輪發現的綠燈斷言不足，應追加而非覆寫原 evidence。

**OS IME NOT RUN** 保持明示；CDP events 已見 compositionstart/update/beforeinput/input/end，不冒稱真人候選輸入。J06完整取消／Windows native owner、Task5 admission/MV18、Task6 Skill/E2E／自然模型、P5完整管理UI、production0073/0074正式化均仍後續，不從這些未完成项新增本輪 blocker。

下一 gate：root 集中交原實作者修 T4-R01–04；回覆精確 fix diff／窄 RED/GREEN／更新 evidence與限制，再做各 finding closure。當前 Task 4 不宜接受或 commit；review 報告與純記憶體觀察是本 reviewer 唯一新增產物。

## Fix1 窄複核 — 2026-09-10

**最新 Spec verdict：PASS（Task4 已授權範圍）。最新 quality verdict：APPROVED。T4-R01–04 全部 CLOSED；沒有新增 remaining finding。** 上方原始 FAIL／OPEN 與首敗資料保留為歷史，本節取代其目前狀態，並不追認初輪 clipboard 保真綠燈。

本次由原 reviewer 只核 `task-4-fix1-review.diff` 的15檔與四項受影響接點，以及 final `task-4-fix1-report.md`／raw。root 已核其餘57原檔未變；reviewer 額外按 `task-4-fix1-files-manifest.json` 實讀核51項 SHA256，零不符。沒有重審 schema 候選、爬 repo、重跑原154或完整 browser，也沒有修改產品程式、git、DB 或呼叫付費模型。

### T4-R01 — CLOSED（P2）

API 從既有 manual identity 算式抽出共用 helper；Pydantic validation、envelope/source 與 archived/foreground 拒絕，均只在同 service lock 下確認相同 canonical UUID identity 沒有 receipt 後回傳 actual Pydantic `ManualSaveRejection`。已有 receipt 的 malformed replay、receipt 無法讀取不宣告 not_admitted；合法重試仍先回原 receipt。生成 API union 引用這個實際 HTTP DTO，沒有另建 JD schema 或以所有409/422推論無寫入。

Web 僅接受 matched request_key 的明確 not_admitted，解除 unknown 同時保留候選／問句；其他409/422/503、不同key與網路失敗保持鎖。已讀 API2通過 raw及對應測試；headed Chrome 真 archived409 raw 的 marker/key 與 cache 相同，head 未改、明示捨棄才清cache。獨立文件 network abort 則候選保留、捨棄 disabled、contenteditable=false。這項有限修正解除原不存在 receipt 的永久鎖，沒有把真正未知變成可丟棄。

### T4-R02 — CLOSED（P1）

一般 save 在建立新 payload/key 或寫cache前先拒絕已有 candidate；原唯一候選不會被另一份 current draft覆寫。聚焦測試沿首個反例，保留 `ONLY RECOVERABLE OLD TEXT`、一般保存不POST、再建session仍讀回同候選；明示discard後才允許新提交成功。19項聚焦Web raw通過。確認為單一候選保護，未新增多稿authority／自動merge；本項沒有誇稱重跑全部真browser recovery。

### T4-R03 — CLOSED（P2，證據缺口）

補充報告明確撤回初輪保真含義並保留原raw。新腳本先寫入sentinel、實際鍵盤選取、核DOM range及既有產品selection ready，再Ctrl-C並核 clipboard原文。首敗 raw保留 copy types=[]／sentinel未變，沒有再靠段數通過；等待產品選取訊號是harness同步，未改產品copy或注入editor selection。

已核最終 headed Chrome153.0.8010.37 raw：copy/paste事件均有 text/plain、text/html、application/x-slate-fragment；clipboard文字等於「複製保真內容」。兩leaf（含bold）貼上後全等、paragraph type相同、source ID保留且new ID不同；保存重開斷言與截圖兩份相同正文吻合，ok=true、page errors=[]。此為有限 paragraph/marks clipboard證據，不擴張成所有table/refs／跨應用組合。原 input腳本已加內容／marks／type／fresh ID斷言，但本輪只有單檔lint，未把它標成重新跑過。

### T4-R04 — CLOSED（P2）

本機 create recovery 讀取先於列表 GET，cacheReady初值false／讀失敗維持禁止新建；cache錯誤與list錯誤分開。create handler再次檢查cache，已有原記錄時一般submit不能產新key，recovery亦須匹配key/title。新增 slow/failed GET 與 unreadable storage測試包含繞過disabled的直接submit，均不create；原記錄可立即顯示並以原key確認。對應Web19通過raw已核，無須重跑未改的PG原子性。

### 驗證與效力

已讀實際 final logs與命令結果：API2、Web19、check-codegen、typecheck、lint、Next16.3.3 build通過。第一輪type exit2、API UUID處理失敗、clipboard sentinel首敗、browser唯讀role定位首敗均保留，未抹成全程綠燈。新worker29272的保存manifest仍指向isolated Node22.23.2；本次沒有重新認證未變的官方runtime材料。

本節 closure 與原已核成立部分共同支持 Task4 接受。**OS IME NOT RUN** 仍明示，CDP不能代替真人OS輸入；Task5完整生命周期／admission／MV18、Task6 Skill/E2E／自然模型、P5完整管理UI及production gate仍後續。此 verdict 不宣告整個產品／計畫完成。
