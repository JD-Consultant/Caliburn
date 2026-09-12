已完成審查。以下為報告。

---

# 隔離 JD 核心整體跨切片獨立審查報告

**審查對象**：HEAD `3d0445ae`（對照 BASE `622e548d`）；唯讀 packet，未執行任何測試、指令、provider 呼叫或 Git 操作。
**審查者定位**：獨立審查，不擁有分析／設計／修正／驗收。所有結論標明「讀碼推理」或「文件觀察」，**沒有任何一項是我實機執行的結果**。

## 一、實際讀取的有限面（finite scope）

先讀 `manifest.json`（全 2064 行）取得精確檔名，未猜測任何檔案。

**完整讀取**
- 需求：`requirements/core-review-brief.md`、`requirements/2026-09-10-jd-editor-core-integration.md`、`requirements/2026-09-10-jd-employee-journey-design.md`
- Python source：`api.py`、`jd_routes.py`、`jd_service.py`、`jd_store.py`、`jd_engine.py`、`jd_tools.py`、`jd_context.py`、`jd_references.py`、`jd_reconcile.py`、`windows_lifecycle.py`、`service.py`（全 856 行，分三段）
- Web source：`useJdSession.ts`、`JdEditor.tsx`、`JdWorkspace.tsx`、`jd/api.ts`、`navigationGuard.ts`、`JdNode.tsx`、`JdChanges.tsx`、`DocumentList.tsx`、`DocumentActions.tsx`
- Native source：`native/src/read-selection.ts`
- 測試：`web/src/jd/useJdSession.test.tsx`、`web/src/jd/JdSavedProjection.test.tsx`

**部分讀取**：`conversation.py`（前 120 行＋完整 diff）、`sources.py`（僅 diff）

**未讀（明示）**：`jd_contract.py`、`jd_types.py`、`catalog.py`、`scheduling.py`、`publication.py`、`memory*.py`／`live_memory.py`／`extraction.py`／`consolidation*.py`／`repair.py`／`skills.py`／`budget.py`／`provider.py`／`runtime.py`；全部 `SKILL.md` 與 references；contract schema／`models.py`／`jd-editor-v2.ts`／lock 檔／license inventory；全部 `tests/test_jd_*.py`、`test_postgres_*`、native tests、`web/browser/*.mjs`；全部 `evidence/*.log`／`*.json` raw 快照；其餘五份 root 技術設計（tool contract、plate profile、model-view notice、native process lifecycle、manual recovery transport）與兩份 `review.md`。

因此本報告**不對 Task1–5 既有結論改判**，也不重跑既有審查；只針對整合後的跨切片行為。

## 二、結論

- **Spec：FAIL（單一項）** — 僅 F1 一項不符已採用的員工旅程設計出口要求；本次核對的其他跨切片項目（伺服器 admission、手動／AI 閘門、程序生命週期與對帳、單一 JSONB 文件與同一 scoped ID、來源取得與下輪模型通知、JdSession／editor 轉移、原生選取出口）在我讀過的面上 **PASS**。
- **品質：CHANGES REQUIRED** — 因 F1。
- **有阻斷性發現**：是（F1 一項）。其餘為 Minor。

## 三、發現

### F1（Critical）dirty 且已保存版本前進後，同頁沒有任何可成功保存或送出的出口

**確切位置**
- `web/src/jd/useJdSession.ts:169-175`（dirty 時不套用新 head，只設 notice）
- `web/src/jd/useJdSession.ts:293-298`（`reconcile && dirty` 時**不**推進 `this.head`）
- `web/src/jd/useJdSession.ts:272`（保存一律以 `this.head.revision_ref` 為 base）
- `web/src/jd/useJdSession.ts:306`（該路徑仍設 notice「已保存」）
- `web/src/jd/useJdSession.ts:368`（`send()` 先保存，失敗即 return false）
- `web/src/jd/useJdSession.ts:79-82` 的 `discardBuffer()` 僅被 `web/src/jd/JdWorkspace.tsx:65` 的離頁流程呼叫
- `web/src/jd/JdWorkspace.tsx:273-281`（文件面板只有「保存／這次改動／讀取上一筆歷史」）
- 伺服器端終局判定：`analysis_agent/jd_store.py:256-257`（`current_id != base.id` → `stale_base`，confirmed）

**觸發（兩條皆在單一員工旅程內可達）**
1. 候選重送：畫面已有尚待處理候選、員工同時繼續打字（dirty），按「再次送出同一份」→ `save(true)` 成功 committed。因 `reconcile && dirty`，`this.head` 仍停在候選的舊 base。
2. F5 guard 情境（Task6 R04 本身的終態）：`JdSavedProjection.test.tsx:95-117` 明確斷言 `session.locked === false`（第 107 行，即等待 change 期間可打字）、事後 `session.head === baseline`、`dirty === true`、notice 含「未保存修改仍留在畫面」。

**失敗與影響（讀碼推理，非實機觀察）**
進入該狀態後：`refresh()` 因 dirty 永不推進 `head`；`save()` 永遠以已過期的 `base_revision_ref` 送出，伺服器每次回 confirmed `stale_base`；`send()` 因 `dirty && !(await save())` 而永遠 return false，**連純聊天也送不出**。同頁唯一的離開方式是「捨棄未保存修改與未送出聊天後離開」（`JdWorkspace.tsx:193`），亦即必須丟掉員工的未保存修改才能繼續。UI 同時出現矛盾訊號：狀態列顯示「未保存」，notice 卻顯示「已保存」（`useJdSession.ts:306`，指的是候選）。沒有靜默資料覆蓋，也沒有把未保存內容謊稱已保存，但**員工在同頁沒有真實可操作的出口**。

**違反的已採用要求**
- `2026-09-10-jd-employee-journey-design.md` §4：「若 head 已變，保留 current 唯一 editor，將失敗候選以同頁唯讀材料提供；員工可複製需要的內容到 current 再保存，或明示捨棄該候選。」實作在 dirty 時反向：editor 停在過期 buffer，current 不可達，無法「複製到 current 再保存」。
- 同文件 §5 狀態矩陣（confirmed stale／保存失敗一列須「可依 §4 處理」）與 §1 唯一問題（「是否都有真實且可操作的出口」）。
- 註：§5 另一列「普通 dirty 不能自動替換成 server 新 head」同樣是已採用要求，故 **R04 guard 本身正確，不應回退**；缺的是 guard 之後的明示出口。

**最小修正**
在 `JdWorkspace.tsx` 的 notice／候選區增加一個明示動作，呼叫既有的 `session.discardBuffer()` 後 `revalidate()`（載入最新 current），文案明確說明會捨棄畫面上的未保存修改；並在 `useJdSession.ts:293-298` 走到 `reconcile && dirty` 時，把 notice 改成「候選已保存並產生新版本；畫面上的未保存修改以舊版為基準，需先處理才能保存」。不新增保存、重試、rebase、自動 merge 或全域鎖（符合 R04 修正界線與旅程設計停止線 (1)）。

**公平性聲明**：我未讀 `2026-09-10-jd-manual-recovery-transport-design.md` 等其餘五份 root 設計。若其中已明示接受「dirty＋head 已變時僅能離頁捨棄」，root 應據該文件把本項降級為已知取捨；依我讀到的旅程設計，它是缺口。

### F2（Minor）`close()` 的 manual 對帳未比照 `start()` 作 per-document 容錯

**位置**：`analysis_agent/service.py:843-845`（對照 `service.py:209-213` 的 `try/except PublicationUncertain: pass`，以及同一迴圈內 `service.py:848-852` 對 `_close_turn` 的 `continue`）。
**觸發**：關閉服務時，某一文件的 `_reconcile_manual` 丟出 `PublicationUncertain`（例如關機期間 DB 邊界不可用）。
**影響（讀碼推理）**：例外穿出 `close()`，同一迴圈中**其後所有文件**的關閉對帳被略過；該些文件的 run 只能靠下次 `start()` 以 `interrupted` 收斂。無資料遺失或假結果，ExitStack 其餘資源仍會釋放。
**依據**：與同檔既有「保留未知工作、不偽造結果、逐文件繼續」的既定處理一致（`service.py:851` 註解）。
**最小修正**：把 `service.py:845` 包成 `try/except PublicationUncertain: pass`（與 `start()` 同樣語意），不改其他行為。

### F3（Minor）K／S 無名稱時的文案與已採用設計不符

**位置**：`web/src/jd/JdNode.tsx:29-30` 回傳「未命名項目」。
**依據**：`2026-09-10-jd-employee-journey-design.md` §8：「無名稱顯示『未命名知識／技能』」。
**影響**：純文案，不影響資料或關係解析。
**最小修正**：`nameOf` 依 `node.type` 回「未命名知識」／「未命名技能」，其餘節點維持現值。

## 四、跨切片核對通過的項目（我讀過的範圍內）

- **單一文件與責任**：`jd_store.py` 是唯一 SQL owner，revision／head／operation 皆以 `document_id` scoped，`jd_one_initial`／`jd_one_successor`／`jd_one_producer` 與 receipt CHECK 約束把 committed／no_change／失敗三類收據的欄位一致性推到 DB 層；`publish()` 對 commit 不確定性一律降級為 unconfirmed，不轉成 failure。模型工具仍是 `jd_read`／`jd_edit`／`jd_change_read` 三個（`jd_tools.py:17`），且 `conversation.py` diff 與 `JdExecutionIdentity` 雙重擋住同名假工具。
- **伺服器 admission 與手動／AI 閘門**：`service.save_manual()` 在同一 `self.lock` 邊界內查既有 receipt → 檢查 `_write_blocked` → 寫 root-only descriptor；`_write_blocked` 同時涵蓋 archived、foreground run、`native_calls` 非 quiescent 與未閉合 binding。`rejected_manual()` 明確不以 HTTP 狀態推斷零寫入。
- **程序生命週期**：`create_app()` 在任何資源前 `bootstrap()`，`open_service()` 首行 `require_bootstrap()`；`JdNativeCalls.finish()` 無法確認清理時保留 `cleanup_pending`，經 `manual_recovery()` 的 `restart_required` 投影到 `JdWorkspace.tsx:149-156` 的明示重啟指引——這是 native 卡住時的誠實有限出口。
- **來源取得（T6-R01）**：`jd_tools.py:193-204` 僅在實際 owner 讀取結果比對成功後附加 `tool_call`，且以 `{**prior.get(reference,{}), ...}` 保留 App 已發配的 `current_input`；`validate_sources` 的兩個否定守衛（未發配、非本輪身分）仍在。
- **下輪模型通知**：`jd_context.prepare_notice` 的 16KB 上限、preview／exact 二分、`visible_jd_result_ids` 只計仍可見且有 factory 綁定的 ToolMessage，並由 `JdExecutionIdentity.wrap_model_call` 逐項核對準備後未被更動。
- **原生選取在 run 建立前的有限出口**：`service.submit()` 在 admission 內以 `store.current(scope).id != base` 擋過期 selection（→ `ServiceConflict` → 409），`read-selection.ts` 的非法選取一律成為分類錯誤；Web 端 `send()` 對 409/422 清掉 pendingRun 並要求重新選取，`requireSelection` 失敗保留原問句，`selectionIntent` 另有「改為純聊天」。此路徑**不需要新 route**。
- **瀏覽器讀取不重播寫入**：`mount → load → lookup` 與 `pageshow／visibilitychange → revalidate → refresh` 全為唯讀；`submit`／`recover` 僅由明示按鈕觸發。

## 五、剩餘未驗 gate（不在本核心範圍，勿併稱完成）

1. P3 付費自然模型品質（方法是否被自然使用）與案例授權。
2. OS 真人 IME、真人員工使用、長訪談與三名員工（P6）。
3. 日常啟停／備份／還原／更新（P5），含完整更名／封存／恢復管理 UI —— 依旅程設計 §9 明示屬 P5，故本次**不列為缺口**。
4. Production successor ADR／G6 正式授權（ADR 0060 權責不變）。
5. F5 最終 guard 的實機競態：僅有精確反例測試與最終 built Web 重開通過；我**不宣稱**該 guard 曾以真人瀏覽器手動觸發競態。
6. 本報告全部結論來自唯讀讀碼與 root 提供的文件；F1／F2 為讀碼推理，未實機重現。