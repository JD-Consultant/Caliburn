# 選問小測：取消時間上限後的機械續跑

本批保留原件收於[私人 ZIP](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip)；各原件的包內路徑見連結標題或下文。按需取回方式見[私人歷史材料與資料庫封存](../../../artifact-storage.md#私人歷史材料與資料庫封存)。

此檔只描述研究 runner 的續跑接線，不切換正式產品指引。原[候選與評閱方法](2026-10-07-priority-candidate-protocol.md)、[原 runner](priority-probe-run.py)、[核心](priority-probe-core.py)、案例、私人披露規則與品質標準維持原凍結內容。

使用者在本次工作明確說「不用管截止」。Root 已 first-write 保存 `time-limit-revocation-user-receipt.json`，SHA-256 為 `a0f24a1b21752c3dc232f68493308dff641121ae833b0f08573ecffb59de50a4`。新 [wrapper](priority-resume-run.py) 逐次核對此授權原件及原 manifest、final ledger 的 hash，只取消絕對與經過時間限制；語意回覆檔等待仍上限 300 秒，逾時保存狀態並停止，沒有自動重做。

原 batch 因時間停止，保留依原 schedule 完成的 5 案（冷藏與錯儲位兩組完整對照、旺季 B0）。旺季 B1 的部分工作仍保存，不能當品質 sample；19 個未完成 logical trials 在新資料 schema、新職務檔案與唯一 attempt ID 重做。續跑選樣只看 complete 清冊與凍結 schedule，沒有讀品質正文。原 24 個 logical trials 最多 48 則完整回覆，已發生的 partial 1 則永久計入實際消耗，因此本次合計最多 49 則 actual 回覆。

費用及計數從已停止 ledger 延續，不能再次獲配增量：

| 累計項目 | 續跑起點 | 固定上限 |
| --- | ---: | ---: |
| 已知估計費用 USD | 2.016560225 | 佔用費用上限為 2.514531895 |
| 佔用費用 USD | 2.064305725 | 2.514531895 |
| generation attempts | 1796 | 1994 |
| outbound attempts | 3973 | 4447 |
| counted input tokens | 91,281,083 | 106,093,382 |
| compact attempts | 14 | 22 |

3 筆未知 reservation 全數原值繼承，共 USD 0.047745500。USD 8 與 3000 generation、7000 outbound、180M counted input、32 compact 的原全域上限也仍有效；上述固定 probe 上限取兩者較小值。試驗保留所有中斷、未知及費用原件，不把失敗推定為零付費。

wrapper 在本行程重綁原 runner 的 guard、metadata 驗證、first-write 輸出、lease 與有界語意等待，正式 App、HTTP、Writer、SDK、原話/JD 讀取與 trial loop 仍由原 runner 負責。新永久 `priority-resume-execution-lease.json` 防止續跑重複或並行啟動，不覆寫原 lease；沒有改 parser、tools、指引、模型或答案選擇方式。實際 prepare 凍結所有原來源及新增 wrapper/測試/本檔，並保存前次工件 hash；execute 與每次 provider admission 都重新驗證。

以下保留當時 Root 在 `apps/api` 工作目錄使用的呼叫形式。`--previous` 指向[私人 ZIP](https://github.com/JD-Consultant/Caliburn-archives/releases/download/storage-2026-10-08/caliburn-selected-c-evidence-20261008.zip "包內：caliburn-intplan-comparison/question-priority-probe/priority-probe-after-repair-v1/") 中的 `caliburn-intplan-comparison/question-priority-probe/priority-probe-after-repair-v1`；下例以 `$previous` 表示解壓後的位置。`dry-run` 與 `prepare` 不讀 key、不連 DB、不發 provider；`execute` 才使用既有授權，root 是唯一付費啟動者。付費 prepare 不加 `--offline-only`；離線測試產生的 manifest 永遠不能 execute。

```powershell
$previous = "<解壓目錄>/caliburn-intplan-comparison/question-priority-probe/priority-probe-after-repair-v1"
.venv/Scripts/python.exe -X utf8 ../../docs/experiments/product-validation/data/jd-question-selection-2026-10-07/priority-resume-run.py dry-run --previous $previous --name priority-probe-resume-after-revocation-v1
.venv/Scripts/python.exe -X utf8 ../../docs/experiments/product-validation/data/jd-question-selection-2026-10-07/priority-resume-run.py prepare --previous $previous --name priority-probe-resume-after-revocation-v1
.venv/Scripts/python.exe -X utf8 ../../docs/experiments/product-validation/data/jd-question-selection-2026-10-07/priority-resume-run.py execute --previous $previous --name priority-probe-resume-after-revocation-v1
```

離線反例在 [priority-resume-tests.py](priority-resume-tests.py)，涵蓋時間取消、非時間停止不可清除、原 cap 不重配、全域 cap、reservation 保存、只能保留 exact complete 前綴、唯一 attempt、私人內容 fence、等待 300 秒、metadata 防竄改、無 key/DB/provider 的 prepare、累計輸出與 first-write lease。它們不能當作真模型品質或正式瀏覽器驗收；付費結果另由 root 保存及匿名評閱。
