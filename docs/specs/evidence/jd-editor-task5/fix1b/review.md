# Spec Compliance

❌ **Issues found／Task quality：Needs fixes。** 原 R01–R05 閉合；R06 的 manual recovery 分支已修，但同一全入口 drain 要求在 `stop` 的末尾結果投影仍有缺口，保留一項 Important。不可標 Task5 accepted 或以前置完成進入 Task6。

審查日期：2026-09-11。限定原六項與受影響 caller；採最新 `task-5-fix1b-review.diff`（77528 bytes），SHA256 `069a35ee9684988136ffb006224db74553ca5c0221345e7cf0ec8a3f76a2b8b5`。manifest 的十個 snapshot 檔案逐一核 SHA256 全吻合；runtime service SHA256 `549a17442c6e3661c32e5152e9876b1e60b43b634216c6f5a1ac079ce57459f4`。沒有把 root 報告的 addressed 視為 closure 證據。

下列路徑根為 `S:/caliburn/.worktrees/analysis-only-agent`；`A`＝`experiments/analysis-agent`，`W`＝`experiments/jd-editor/web`。行號指 fix1b 凍結來源；未改 caller 僅核具名接點。

| 原 finding | 本輪判定 | 來源與證據 |
| --- | --- | --- |
| R01 | CLOSED | `A/src/analysis_agent/service.py:603–631`：最終同鎖重查原 key／已保存 input、archived、pending、accepting、owner／selection generation 後才寫 Human input。`A/tests/test_jd_fix1_admission.py:12` 實際 archive interleaving 保證未建立 run／input。 |
| R02 | CLOSED | `W/src/jd/useJdSession.ts:198–211`：exact 原 key 的 receipt 與 no-key discovery 的 gate 分別保留；descriptor 清除後不再覆掉原 terminal。actual session 的 committed／no_change／save_failed 三例包含後續 refresh。 |
| R03 | CLOSED（隔離範圍） | `A/src/analysis_agent/service.py:307–313`、`W/src/jd/useJdSession.ts:174–177,198–211`、`W/src/jd/JdWorkspace.tsx:149–156`：無 run／descriptor 時輸出 restart_required，head read 失敗仍讀 owner gate，畫面顯示保留頁面及原啟動入口重開步驟。API owner、actual session、獨立 recovery component 證據支援本隔離版；日常啟停 UI 仍屬 P5，不宣稱已完成。 |
| R04 | CLOSED | `A/src/analysis_agent/service.py:338–345,571–586,792–802`：recovery／stop／abandon 的清理、PG 對帳與 close_turn 等待移出全域 admission lock，同文件仍有 closing／generation 保護。`A/tests/test_jd_fix1_admission.py:52,126` 的真 PG head lock 與 stop／abandon barrier 證明 A 等待期間 B 可 admission。短 shared-state mutex 並非本 finding 要移除的機制。 |
| R05 | CLOSED | `A/src/analysis_agent/service.py:380–404`：先核 identity／digest 及原 receipt；匹配 descriptor 的可選清理失敗保留 gate，仍回 terminal。`A/tests/test_jd_fix1_admission.py:30` 的 full HTTP POST 兩個參數涵蓋 clearfail／sibling owner。 |
| R06 | PARTIAL／OPEN | `A/src/analysis_agent/service.py:320–357` 的 recovery accepting、drain 與同鎖投影已閉合；`stop:803–808` 仍在投影前解除 entry，詳下。 |

# Strengths

- ✅ Recovery 在 `service.py:348–357` 同一次 Condition lock 內先解除 closing、完成投影、再減 drain 計數，既顯示正確 gate，也避免舊 finally 覆蓋新 owner。沒有改 SQL／checkpoint authority 或引入另一套 coordinator。
- ✅ fix1b 已恢復原 `W/src/jd/JdWorkspace.test.tsx:7,25` 的完整單一 editor 與 empty-leaf formatting 兩項測試；R03 測試獨立於 `JdRecoveryWorkspace.test.tsx`。已直接讀到兩個原案例及最新 37 PASS／8 files raw；不再保留測試被移除的疑點。未將先前 35 PASS 當成包含這兩項。

# Issues

## Important

### T5-R06／P2／OPEN：stop 在結果投影前解除 shutdown 的等待計數

- **位置：** `A/src/analysis_agent/service.py:803–808`；受影響 caller `get_run:680–686`、`close:831–835`，資源生命期 `A/src/analysis_agent/api.py:159–161,207,228–230`。
- **具體交錯：** 已 admission 的 stop 完成 `_close_turn`／`_reconcile` 後，在 finally 清 closing、將 close_entries 減為零並釋鎖；最後 `get_run` 此時尚未取得 lock。另一執行緒可完成 `close()` 的 drain 及剩餘收束並返回；resource manager 隨後釋放 Saver／Store／engine。stop 才進 `get_run` 讀 catalog 和 graph，會碰到已退出的資源。這是原 R06 全入口完整 unwind 邊界的同一缺口，並非要求擴充普通 GET 的生命期。
- **實測：** `scratch/task-5-fix1b-review-stop-drain.py` 從最新 frozen source 用 AST 執行原 `stop`、`close`，只替換 catalog／graph／native 等依賴；Event 在最後投影方法入口、尚未取得其 lock 時暫停。actual close 返回時，觀測 `close_entries_at_final_projection=0`、`close_returned_while_stop_projection_pending=true`。釋資源標記後放行投影，收到注入的 `Saver/DB already disposed`。這是控制流程反例；未宣稱真 PostgreSQL 已發生該錯誤，也未實跑 Uvicorn shutdown。actual get_run 的資料存取及 ExitStack 順序支援該交錯的影響。
- **要求：** 讓 stop 的最終結果投影仍在同一次 entry／lock 保護內，結果完成後才釋放 drain，並保證投影拋錯也正確 unwind。沿已修的 recovery 原則處理即可；補 stop 最後投影 barrier＋close 的有限回歸，不需新架構或重跑完整故障矩陣。
- **現有證據界線：** `A/tests/test_jd_fix1_admission.py:81` 驗 recovery 中途 cleanup 的 close 等待；`:126` 驗 stop／abandon 等待不阻 B。它們沒有把 stop 的最後 get_run 暫停於 entry 已減後，因此 54 API PASS 不反證此交錯。

## Minor

- ✅ 原 R07 的 Starlette／AnyIO DeprecationWarning 已在 fix1／fix1b 報告明記，raw 保留；符合本輪「記錄且不隱藏、不為消音擴改依賴」要求，無新增阻擋。

# Checks／證據效力

- ✅ 直接讀原輸出：`scratch/task5-root-fix1-api-green.log`＝54 PASS／1 warning／77.55s；`scratch/task5-root-fix1-memory2-green.log`＝63 PASS／1 warning／33.85s；`docs/specs/evidence/jd-editor-task5/fix1b/web-restored.log`＝37 PASS／8 files／9.99s。原 codegen／check-codegen／types／lint 證據已在前段複核讀取；沒有重跑完整測試或相加重疊輪次。
- ✅ 本輪新增唯一執行：cwd 為上述 worktree，`experiments/analysis-agent/.venv/Scripts/python.exe scratch/task-5-fix1b-review-stop-drain.py`，exit 0；輸出為預期缺陷觀測，非產品 PASS。fixture SHA256 `192e30109efcbc7e067fcdf01fc55a47ad41104ccde7cbe22f24e756de8a88be`。沒有 DB、付費 provider、native bridge 或現有 API 程序操作。
- ⚠️ 不由 diff／純 fixture 宣稱真服務 shutdown 時序已驗。本 finding 可由 actual stop／close 的 entry 缺口及實際資源 caller 判定；下一輪只需對該具名接點驗 closure。
- ⚠️ 原 NL08 suspended child、NL10 manual A＋selection B、NL11 nested 成功／真 access-denied 的效力限制不變；沒有補跑 exact JS-transform／AI-edit 組合／nested-incompatible。最後 source 未有新的 headed browser；OS 真人 IME、natural model、真人產品品質與日常啟停入口均未因此通過。
- ✅ 本輪只寫本 review 與窄 scratch；沒有修改 code／計畫／已存 raw，沒有 git mutation、key 讀取、產品 provider 或 DB 動作。原 Task1–4 accepted、Task6 未做、production 0060 與零付費邊界不變。

# Assessment

**Task quality：Needs fixes。** 五項原 Important 已具體閉合；R06 的 recovery 修正正確，但 stop 最後投影仍可落在 drain 完成之後。修正此唯一剩餘 Important 並做窄複核前，Task5 不可判 PASS。
