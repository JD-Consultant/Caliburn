已完成窄 closure 審查。以下為報告。

---

# 隔離 JD 核心 F1／F2／F3 窄 closure 獨立複核

**對象**：BASE `3d0445ae` 之上的 closure packet（唯讀）。我**未執行**任何測試、指令、provider、網路或 Git 操作；未驗 sha256（需執行）。所有判斷標明「讀碼推理」或「讀證據觀察」。

## 一、結論

- **Spec：PASS（限 F1／F2／F3 三項 closure 範圍）**
- **品質：APPROVED**（附下述 Minor 殘留，非阻斷）
- **F1 CLOSED／F2 CLOSED／F3 CLOSED**

## 二、逐項 closure 判定

### F1 CLOSED — 過時手改在同頁有真實出口，且未破壞既有守衛

讀碼核對（`useJdSession.ts`、`JdWorkspace.tsx`、`JdEditor.tsx`）：

1. **普通 dirty 不自動替換**：`useJdSession.ts:186-204` 未改，dirty 時 `refresh()` 只設 notice、不推進 head；`JdSavedProjection.test.tsx:95-117` 的反例仍成立（R04 guard 未回退）。
2. **先讀後換**：`loadSavedHead()` 於 `useJdSession.ts:91` 先 `await port.read` 成功，才在 `:93-101` 換 head／value／dirty。無 HTTP 寫入、無 rebase／merge、無新 store（`JdStaleCandidate.test.tsx:93` 另斷言 `port.save` 未被呼叫）。
3. **保留聊天與已送出候選**：`:99-101` 僅改 notice，未動 `this.text`、`this.candidate` 或 `submissionCache`；`JdStaleCandidate.test.tsx:50-52`、真瀏覽器 `core-stale-browser.json:236` 與第 53 行斷言 localStorage 候選字串前後完全相同。
4. **讀取失敗保留全部**：`:103-106` catch 只設 error，buffer／base／chat 不動（`JdStaleCandidate.test.tsx:82-94`）。
5. **未確認結果擋掉捨棄**：`:85` `if (this.locked)`，而 `locked` 含 `manualUnknown`（`:139`）；`JdStaleCandidate.test.tsx:66-80` 以丟失回覆的未知結果驗到 `loadSavedHead()` 回 false。符合 transport 設計 §4「不另發新 writer／新 key」與 journey §5「未確認」列。
6. **同 revision 也真的重建 Plate**：`JdWorkspace.tsx:32` 的 `|| session.dirty` 使回呼在同 revision 時仍進入；`applySavedHead()`（`JdEditor.tsx:26-27`）因 editor 內容 ≠ baseline 而回 false，回呼 `:35-37` 清 `editor.current` 並 `setEpoch`，以既有 `key={epoch}`（`:294`）重建唯一 editor，而非只改 React state。`JdStaleWorkspace.test.tsx:24` 以 `it.each(['r1','r2'])` 在真 Plate DOM 同時覆蓋同版與新版，並斷言 `[contenteditable=true]` 僅 1 個、取消 confirmation 時 `port.read` 零呼叫。此 `|| session.dirty` 只會在 `loadSavedHead` 路徑為真（`refresh` 只在 `!dirty` 時呼叫回呼；`save()` 在 `:322-326` 先把 dirty 設 false），不影響既有兩條路徑。
7. **舊候選重送＋更新的 dirty**：`:322-327` 在 `reconcile && this.dirty` 時不推進 head／value，`:335-337` 明示「先前候選已保存；畫面上的修改尚未保存，仍以舊版為基準」，不謊稱已保存；`JdStaleCandidate.test.tsx:96-116` 驗到之後仍能以明示載入收斂。
8. **晚到回應**：`loadSavedHead` 以 `++this.generation`（`:87`）與 `:92`、`:104` 的世代檢查丟棄晚到結果；`++this.recoverySequence`（`:88`）使在飛的 `refreshRecovery` 失效並維持 `serverWriteBlocked=true`（保守方向）。

**不採用舊 `discardBuffer()` 的判斷我同意**：`:79-82` 會清 `this.text`（聊天）並在讀取前先清 dirty，違反 journey §4「未送出聊天單獨處理」與 stop line (3)。原 RED（`core-stale-red2.log:10-19`）期望 `revalidate()` 直接變 r2，只證明 current 不可達；把它當產品需求會回頭違反 §5「普通 dirty 不能自動替換成 server 新 head」。最終測試改用明示方法正確。

**已採用要求對照**：journey §4「若 head 已變，保留 current 唯一 editor，將失敗候選以同頁唯讀材料提供；員工可複製需要的內容到 current 再保存，或明示捨棄該候選」——`core-stale-browser.json:237` 的 AX 快照顯示載入後唯一可編稿為 `伺服器已保存的新工作`、候選以唯讀 `員工尚未保存的更正` 留在下方、聊天 `這段補充先不要送出` 仍在，之後新保存以 r2 為 base（`:151`）、committed（`:238-243`），與 `after`（`:256-271`）一致。

### F2 CLOSED — 只擋 `PublicationUncertain`，逐文件續行

`service.py:845-849` 僅捕捉 `PublicationUncertain` 並 `continue`，與同迴圈既有 `:854-856`、`start()` 的 `:209-213` 同語意；其他例外仍穿出，無假 receipt、無刪除、未改停止證明或 DB 權責。該文件未解狀態由 `start()` 的 `:198-203`／`:204-213` 收斂。`test_jd_shutdown_isolation.py:24-26` 斷言兩份文件都被檢查且 `sent == []`；RED（`core-close-red2.log:27-28`）確為 `service.py:845` 未保護。注入 `_reconcile_manual` 不等於真 DB 故障，報告已自陳，我同意此標示。

### F3 CLOSED — 純文案

`JdNode.tsx:28-32` 依 `jd_knowledge`／`jd_skill` 回「未命名知識／未命名技能」，其餘維持「未命名項目」，對應 journey §8「無名稱顯示『未命名知識／技能』」。無 schema／關係／render 結構變更。

## 三、殘留問題（Minor，均不阻斷 F1／F2／F3）

**R1 — 已確認終局失敗的候選仍提供必定失敗的重送**
`JdWorkspace.tsx:340`（`disabled={!session.canRetryCandidate}`）＋ `useJdSession.ts:219-222`。情境：confirmed `stale_base`（候選 base=r1）且已明示載入 r2 後，`manualUnknown` 已為 false，故按鈕啟用——`core-stale-browser.json:237` 的 AX 快照即顯示「再次送出同一份」未禁用；以原 key／原 base 重送在伺服器只會再得 `stale_base`（`next_action: reread_current`）。要求依據：transport 設計 §4「available terminal failure：…有 candidate 繼續保留供檢視／明示捨棄」（重送出口只列給 `no_pending`），journey §5「新意圖先核最新 base」。最小修正：`canRetryCandidate` 增加 `this.candidate.base_revision_ref === this.head?.revision_ref`，或排除 `candidateRecovery.status === 'available'` 且 result 為終局失敗者。

**R2 — 候選面板文案與已確認結果矛盾**
`JdWorkspace.tsx:338`「這份材料尚未確認保存」在同畫面與 `:326`「這次修改未保存：stale_base」並存（AX 快照可見兩段同時顯示）。結果其實已 confirmed 為「未保存」，非「尚未確認」。要求依據：transport §4「不一律將終局結果說成仍在保存」。最小修正：依 `recovery.status==='available'` 的終局結果改為「已確認未保存；保留供複製或明示捨棄」，未確認時才用現文案。

**R3 — 明示動作被併發 revalidate 取消時無任何可見結果**
`useJdSession.ts:92`。情境：`loadSavedHead` 讀取在飛時 `pageshow`／`visibilitychange` 觸發 `revalidate()`→`refresh()`（`:168` 遞增 generation），loadSavedHead 靜默回 false；若伺服器 revision 未變，`refresh` 的 `:203-204` 也不會設 notice，員工按下並確認後看不到任何回饋（狀態保守、無資料損失）。要求依據：journey §5「恢復不成功時停止轉圈，顯示可再次確認…不假造已完成」。最小修正：世代不符時設 notice「已改讀最新狀態，請再按一次載入」。

**R4 — `busy` 於 finally 無條件歸零（既有型態，非本次引入）**
`useJdSession.ts:107-109`（同 `:356`、`:274` 既有寫法）配合未檢查 `busy` 的 `stop()`／`resume()`（`JdWorkspace.tsx:250`、`:255`）：若在 `loadSavedHead` 飛行中按「停止顧問」，loadSavedHead 的 finally 會提早解鎖 UI，直到 `stop()` 自身結束。無資料誤用（各方法皆有世代檢查），屬既有型態被新方法延伸。最小修正：finally 僅在 `generation === this.generation` 時歸零 busy，或為 `stop/resume` 加 busy 守衛。此項在 F1／F2／F3 範圍外，優先度最低。

**觀察（非問題）**：被捨棄的 dirty buffer 不保留為唯讀材料（瀏覽器證據因此以重新輸入完成）；journey §4 的唯讀材料要求針對失敗候選，且捨棄有 `window.confirm`（`JdWorkspace.tsx:282`）明列會捨棄什麼，屬已採取捨。另外 `serverWriteBlocked`／`restartRequired` 期間此出口一併停用（`locked`），與該狀態各自既有出口一致。

## 四、我實際讀過的有限面

- `manifest.json`、`original-review.md`、`report.md`
- 四份 diff：`service.py.diff`、`useJdSession.ts.diff`、`JdWorkspace.tsx.diff`、`JdNode.tsx.diff`（全文）
- Source 全文：`useJdSession.ts`（512 行）、`JdWorkspace.tsx`（363 行）、`JdStaleCandidate.test.tsx`、`JdStaleWorkspace.test.tsx`、`test_jd_shutdown_isolation.py`、`browser/core-stale-recovery.mjs`
- Source 部分：`service.py` 僅 180-239 與 800-860 行（全檔 47KB 未全讀）、`JdNode.tsx` 僅 1-45 行
- Context 全文：`JdEditor.tsx`、`submissionCache.ts`、`JdSavedProjection.test.tsx`、journey 設計、manual-recovery transport 設計
- Evidence 全文：`core-stale-browser.json`（含 requests／AX／三份 receipt）、`core-stale-browser.log`、`core-stale-red2.log`、`core-close-red2.log`、`core-fix-python.log`（86 passed）、`core-fix-pg.log`（19 passed）、`core-fix-test.log`（11 檔／47 passed）、`core-fix-web-results.json`（test／build／typecheck／lint exit 0）

## 五、限制（不得被引用為更大的通過）

1. 我未執行任何測試或瀏覽器；上述 PASS 數字是**讀 raw log／JSON 的觀察**，非我重跑。
2. 原 RED 的測試檔本身不在 packet，我只讀到其失敗輸出；報告稱兩份分別保留，我未核對檔案。
3. 瀏覽器證據為**單段合成文件短流程**（新建空文件 `1a5e196e-…`、`keyboard.insertText`），helper 自陳 `OS_IME: NOT RUN`；不構成完整六章旅程重跑、真人 IME 或 OS 剪貼簿。`product_provider_calls: 0` 是 helper 內常數，可支撐的實際觀察是 requests 中 0 筆 `POST /runs`、且來源僅 127.0.0.1:3001／8091。
4. F2 為注入 `_reconcile_manual` 的例外，非真 DB 邊界故障。
5. 本審查只覆蓋 F1／F2／F3 與其直接接點；Task1–6 各自既有結論、未讀檔案（其餘 Python／contract／native／Memory）不因本報告重新背書。
6. P3 自然品質、P5 日常維運／完整管理 UI、P6 真人與長訪談、production G6 **仍各自未通過**，不得與本 closure 合併宣稱。