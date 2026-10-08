# 磁碟中斷恢復與有限補足

本次 `formal-append` 因 S: artifact 磁碟已滿而停止，原程序 exit 1；不把它歸為 native crash。原服務與無金鑰恢復服務的 loopback 8177 listener 均已關閉。唯讀正式 HTTP 確認中斷案第 12 輪為 failed、未送收束，該 schema executions 沒有 active。原 journal、state、0-byte `turn-12-result.json` 和 console 保留原樣，副本與雜湊放在指定 C: artifact 根。

恢復帳務完整承接 `spent_usd=0.341333835`、`occupied_usd=0.366492710`、351 generations、1 compact、762 outbound、17,328,720 counted input。兩筆未知預留為 `0.013296750` 與 `0.011862125`，沒有釋放或扣低。最後一筆帶 guard state 的 journal 之後仍有已寫下的 29,361 token count；因此相對最後 state 是 `+1 generation/+2 outbound/+29,361 input`，對全部 journal 重建則是 `+1 generation/+1 outbound/+0 input`。後者為未寫成 admission 記錄的未知保存狀態，保留其完整預留，不能因 source 的 record-before-dispatch 次序而當作已證實零費用。

只有實際提交共用收束、且該輪 completed 的第一案保留；原 schedule 的其餘七案 fresh 執行。Memory 失敗、筆記失敗或品質不影響選案。補足 aggregate 上限為 USD 8、3000 generations、7000 outbound、180,000,000 counted input、32 compact，絕對截止為 2026-10-07T04:30:34Z；原批上限與原件不改寫。

來源與套件、模型、guides、payload、工具、pressure policy 仍使用 S: 原凍結 bytes。新的 `completion_batch.py` 只將重用 HTTP driver 的 artifact binding 放到 C:，`manifest.HERE`、條件披露來源與 `run_batch.ROOT` 保持 S:。review queue 與匿名 blind input 同在 C:。同一 pair 的原 S: bundle 會逐 bytes 複製到 C: 同根後再同時交盲評，避免來源路徑透露 arm。

離線驗證：原入口拒絕缺 case/result 的恢復反例為 1 failed/14 passed（真正 behavior Red；此前 sandbox tmp_path errors 不列為 Red）；窄 disk audit、carry、source、runtime、output route、實際 no-key dry run、live server 拒絕、異常 finally 帳務保存與 bytes snapshot 共 56 passed。新五個 Python 檔 Ruff check 與 format check 通過。實際 dry run 確認只選七案、0 credential read、0 provider calls。獨立 metadata 審查閉合之前不出站。

可核原件：

- [完整恢復 metadata](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/recovery-disk-complete/recovery-metadata.json)
- [disk audit v2](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/recovery-disk-complete/disk-audit-v2.json)，SHA256 `114c1d694970e033d2741fd191d67ad57a4b789629a0a2ab8826cf9261f417f0`；v1 原件保留
- [真正 Red](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/disk-gate-red-actual.log)
- [56 個 Green](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/disk-gate-green-2.log)
- [實際 dry run](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/supplement-dry-run.json)

第一個只讀恢復 probe 使用錯誤 JD route 而收到 HTTP 404，0 provider；其 metadata 保留在 C: `recovery-disk`。修正 `/jd/profile`、`/jd/work`、`/jd/sources` 後另建 `recovery-disk-complete` 成功，不覆寫前次紀錄。
