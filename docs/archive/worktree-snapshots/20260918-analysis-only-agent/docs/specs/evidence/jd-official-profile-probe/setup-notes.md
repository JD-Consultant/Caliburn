# 執行準備紀錄

2026-09-10：第一次 prepare-fixture 的 import 指到 evidence/jd-profile-probe/fixture.mjs；該原封存 script 依 REPRODUCE.md 要以兄弟 jd-editor-ui-probe 名稱還原，不能直接在 evidence 路徑 import，故 ERR_MODULE_NOT_FOUND，未產生 fixture、未開始四組實驗。改為唯讀 import 既有 .research-tmp/jd-editor-profile-probe/fixture.mjs（正確兄弟目錄），來源 hash 及原始資料另存。沒有改舊文件或 fixtures；不是官方插件失敗或 probe assertion 改判。

首輪 `2026-09-09T16-26-03-698Z`：F02-B PASS；A/C/D 在讀取應由 fresh Node 子程序產出的檔案時 ENOENT，該檔案確實不存在。首次 helper 尚未保存 spawnSync status/error/stdout/stderr，故不能確認原始錯誤代碼，也不能宣稱一定是特定權限錯誤。首輪 result／trace、原 `first-run-probe.mjs` 及所有已產出的檔案完整保留。

唯一實驗執行接線修正：在讀取輸出前保存原始進程診斷並直接傳遞 proc.error；沒有更動四組情境、assertion、官方 plugin 或資料。第二輪允許隔離 Node 子程序，`2026-09-09T16-26-50-933Z` 四組十五項全部 PASS，A/C/D 各有不同 PID 的真正新 Node 程序。第二輪成功不倒推第一輪 ENOENT 的具體原因。上述 Z 時間在 Asia/Taipei 均為 2026-09-10。

授權收集：40 項安裝包有實際授權檔；8 項 package 宣告 MIT 但未附 root LICENSE，另按各正式版本 registry gitHead 取得官方授權原文。Slate 四項的原文件名為大小寫精確 `License.md`；兩個全大寫路徑未找到後改查正確文件名。完整來源及 hash 另列，不把上游 fallback 稱為該 npm 包已附的檔案。收集器同步列入該正確文件名，沒有重跑實驗。
