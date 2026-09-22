# R1/R2 收斂審查結果

**PASS — APPROVED**

## 實際讀取檔案（Read，僅此 4+1 份）
- `change.diff`
- `manifest.json`
- `useJdSession.ts`
- `JdStaleCandidate.test.tsx`
- `JdWorkspace.tsx`（第 300–365 行）
- `core-stale-recovery.mjs`

## 核對結論（限 F1/F2/F3 核心收斂）
1. **`canRetryCandidate` 拒絕 `status === 'available'`**：新子句以 AND 前置，位於 `no_pending || !manualUnknown` 之前，不改動既有兩條通過路徑。`applyRecovery` 在 `available` 且 `result.status` 為 `committed/no_change` 時已清空 `candidate`，故新子句只作用於「已確認終局失敗且候選仍在」一種狀態；此時同 `request_key`、同 `base_revision_ref` 重送必然重演同一終局結果，封鎖正確。
2. **文案區分未知/已知**：`manualUnknown` 為真走「尚未確認保存」，為假走「未保存、保留供查看」。與按鈕 disabled 狀態方向一致，未出現「按鈕可按但文案說不能」的矛盾。
3. **既有復原路徑未退化**：
   - `no_pending`（測試 4 的 `not_admitted` 路徑）：`applyRecovery` 於非 `available` 時提前返回，`candidateRecovery.status === 'no_pending'`，`save(true)` 仍放行，`toBe(true)` 成立。
   - 刻意不加 base-revision 相等限制：`no_pending` 表示寫入從未發生，整份重送仍是正確語意；即使 head 已前進，伺服器只會回 `stale_base` 並被新子句收斂，不會覆蓋他人版本，屬安全收斂。
4. **新增單元斷言可成立**：`save()` 失敗後 finally 的 `refreshRecovery` 使 `candidateRecovery` 成為 `available`、`manualUnknown=false`、`serverWriteBlocked=false`；`canRetryCandidate` 為 false，`save(true)` 在 `reconcile && !canRetryCandidate` 早退，`port.save` 僅一次。後續 `loadSavedHead`、捨棄後以 r2 為基準新存的斷言鏈亦不受影響。
5. **Native/DB/AI 未觸及**；diff 僅四檔、僅前述兩處產品 delta。

**無阻斷性退化。**

## 非阻斷註記（歸 P5，不重開已接受的廣審）
- 已知失敗文案以 `manualUnknown` 切分，`not_admitted`（重送仍開放）與確認失敗共用同一段「建議捨棄」文字；敘述不假，但對可重送情形略欠精準。
- `discardCandidate` 後 `candidateRecovery` 仍留舊 `available`，在下次 `refreshRecovery` 前偏保守（fail-closed），由 `save` 的 finally 自癒。
- `core-stale-recovery.mjs:47` 的 disabled 斷言，成立前提是真實 recovery 端點對確認 `stale_base` 的 exact key 回 `available`；此為本次唯一尚未閉合的經驗證據，依你所述瀏覽器重跑進行中，本審查不代為宣稱其結果。web.log 不在本封包，未讀取、未代為確認。