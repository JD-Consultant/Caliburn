# 原界線後的有限補足候選

此文件只準備離線接線，未放行補足批次。正在執行的 `formal-append` 仍沿原 manifest、US$8、1,500 generation、3,500 outbound、16 compact、40M counted input 與 `2026-10-07T01:30:34Z` 絕對截止；不更改其 top-level source、護欄或案例順序。

候選 driver 放在本 `diagnostics/` 子目錄，重用既有 `run_batch.run_case`、HTTP journey、匿名披露 queue、OwnedObservedStream、原模型與套件。只對原排程的八場工作，不開任意案例或另一套 Agent loop。新批次在先前批次真正退出並保存 final accounting 後才可啟動；root 尚未定案的新上限／截止不得猜測或沿用滾動時限。

完成判準是實際送入共同 closure，且該輪完成。此判準不讀 JD 品質、private missing facts、arm 成績或筆記成效；Memory 的失敗與不完整品質仍保留在結果，不使已完成訪談重跑。已完成案例與匿名 bundle 保留原件，資源中斷案例另建 fresh job file，未啟動案例沿原順序執行。若正常結果檔缺失或狀態互相矛盾，先停在離線核對，不猜測完成。

補足前核對正常 finally 保存的 `batch-state.json` 與全部各案 journal：已知累計 spent 必須吻合最後 received state，generation／compact 必須吻合原 carry 加所有唯一 admitted attempts，counted input 必須吻合原 carry 加所有成功 count records。未結算或未知的 reservations 全数保留；occupied 必須恰等於 spent 加 reservations。原中斷批次的未知 attempt 也須仍在，新 manifest 列明全部先前 manifest／journal／final-state hashes 與原 stop reason。每個 counter 都帶入新總界線，不重設計數或費用。

新明確總界線由 root 在首場完整用量估算後定案；總 USD 維持 8，並包含全部先前 spent 與 reservations。新總 generation／outbound／counted input／compact 上限與絕對截止寫入新 manifest，monotonic anchor 必須先於 wall-clock sampling 及任何建構。建構延遲不可增加截止；現有 carry 的獨立 Red–Green 反例沿用，再核新 driver 接線。

凍結會封存 driver 本身的 exact bytes，並獨立核其 hash；既有 base verifier 继续核完整 top-level／production／guide／schema／dependency 集合，不能為加入 diagnostics wrapper 而忽略既有來源。原 manifest 與 source-snapshot 不改寫。

離線 fixtures 預定涵蓋：八場全部未啟動；兩個完整案例加一個資源中斷；完成但 Memory failed／品質未知仍保留；closure 未提交不得列完成；重複或陌生案例拒絕；spent／reserved 算術矛盾、原未知 reserve 遺失、counter 回退拒絕；建構延遲與過期截止拒絕；新來源修改在 provider dispatch 前拒絕。測試不讀 key、不呼叫 provider。

已完成的離線小切片是 `completion_batch.py` 的純選案與帳務不變量，尚無 provider entry point。原全八場排程 baseline 對選案反例為 8 failed／3 passed，修正後 11 passed；新增帳務反例 baseline 為 10 failed／12 passed，修正後共 22 passed。實際命令為 API venv Python 的 `-X utf8 -m pytest -p no:cacheprovider .../diagnostics/test_completion_batch.py -q`，Red／Green 原件分別存 `completion-selection-*.log`、`completion-accounting-*.log`。沒有使用 import 缺模組作 Red。
