# H2–H3 提交後獨立複核

2026-09-13；Owner要求審查實作者交付，避免接續偏離。審核提交 `7181db63f345b2ec91618cc169a29c624414afc2`，相對 `8403d7e2`；tag `jd-memory-repair-app-integration-20260913` 確實指向受審提交。主代理審工具／session／產品方向，另兩個唯讀代理分別審恢復與封裝／FH05。**本次範圍未發現需阻擋H4採用映射的程式問題。**不是所有故障、自然模型或整體App驗收。

## 結論與方向

- CA-01無binding時，只能用原call與原生binding node的已提交狀態收尾，不補operation／source。CA-02必須比對固定START原input；不能只看缺receipt就當沒執行。
- 無C checkpoint的分支要求root仍pending consultant；`consultant_next`的來源限定在該分支。未找到C已執行卻仍能被此分支判為未執行的可達反例。未知／publish缺receipt仍保持門閘。
- close確切查回包含Memory view與repair bindings；終局get／lookup／startup另核C的原request／receipt。JD結果與Memory回執沒有合併成另一資料權威。
- FH05使用實際新Windows程序，原程序真提交後遺失回覆、在native閉合前退出；新程序不重跑模型、工具、JD execute、setup、publish或patch。Store save與C六節點也有禁止執行的guard。
- 34檔提交未涉及正式`apps/api`／`apps/web`、migration、JD格式或UI切換；`open_managed_app(enable_chat=False)`保留。沒有重做原顧問、改回文章編輯器、加歷史選輪或開付費模型。

依據為本次程式及實測。再次核對[LangGraph子圖](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)、[持久狀態](https://docs.langchain.com/oss/python/langgraph/persistence)與[AWS安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，查閱2026-09-13。沿App鎖定LangChain1.4.0／LangGraph1.2.11，已發布MIT套件；網站不是此版本每個shape的保證。本案binding判定須靠鎖定原碼與反例，不能稱AWS或兩家模型廠商規定的唯一實作。LLM輸入未再修改，沿[C核心已有OpenAI／Anthropic依據](../../2026-09-13-jd-memory-repair-core-slice.md)，不重开同題廣搜。

## 本次真正執行的驗證

工作目錄 `S:/caliburn/experiments/jd-relational-app`；`PYTHONUTF8=1`；沿既有venv／lock，零provider。各組範圍重疊不相加，也不代替實作者全組數字。

| 執行者／範圍 | 本次結果 |
|---|---|
| 主代理：session／records／repair checkpoints／inspection | **155 passed／7.21s** |
| 恢復審查代理：session／records／repair checkpoints／原ai_checkpoints／Memory read recovery | **233 passed／8.29s** |
| 主代理：CA三種停止位置＋FH05真PG／真新Windows程序 | **4 passed／24.71s** |
| 恢復審查代理：多call原生close診斷 | **1 passed／4.48s**；不是owner／HTTP端到端 |
| 封裝審查代理：乾淨venv smoke與依賴檢查 | `WHEEL ISOLATION CHECK OK`；**79 packages compatible**；受constraints約束版本差異0 |

主代理可重現命令：

```powershell
Set-Location S:/caliburn/experiments/jd-relational-app
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider tests/test_memory_repair_session.py tests/test_memory_repair_records.py tests/test_memory_repair_checkpoints.py tests/test_consultant_inspection.py --tb=short
$env:JD_RELATIONAL_TEST_DB='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider tests/test_consultant_memory_postgres.py::test_repair_stopped_before_c_closes_the_original_call_as_not_executed tests/test_ai_host_restart_postgres.py::test_fh05_repair_commit_reply_loss_reconciles_the_original_receipt_after_restart --tb=short
Remove-Item Env:JD_RELATIONAL_TEST_DB
```

只使用既有`127.0.0.1:55436/caliburn_jd_relational_test`合成fixture，測試內核DB/user/schema。沒有setup／清資料／讀正式訪談。新程序由既有Hidden helper啟動，測試只停止自身已確認身分的程序。

[多call診斷](../../../../.research-tmp/h23-review-agent/test_parallel_native_close.py)實際create_agent產生repair＋read_file，停binding node後補同call結果，通過`_repair_evidence`／`_verify_saved_results`、真native close及重讀。它按`_settle`規則補另一個讀取結果，未跑owner或HTTP；不冒稱完整端到端。最初兩次為診斷腳本自身import／工具名假設錯誤，修正後通過，非產品首敗。

## 封裝與跨程序產物路由

- [既存FH05目錄](../../../../.research-tmp/jd-ai-host-recovery-2dd2d938f66845bba465661622564c21/original.json)：舊實際PID41184，原repair真commit且回合未閉合；`repair_reply_loss-e84da2bffa3d46f3b9651466955a84aa.process.json`退出碼73。
- 同目錄`recover-6f6e0199518c4ca39d079cf800813ae9.json`：新實際PID132772、recovered_count=1、ready=true、六項counter全0；對應process紀錄退出碼0。這些既存產物由封裝代理實讀，主代理又獨立重跑FH05。
- `packages/consultant-memory/adoption.json`七筆adopted hash全符合來源。
- [重建wheel](../../../../.research-tmp/jd-memory-c-app-dist-20260913b/caliburn_consultant_memory-0.1.0-py3-none-any.whl) SHA256：`8177326ee4ac9efc900978778ce031a3afcbdf2e2b4832199394745406e99ac1`，符合實作者宣稱。
- 乾淨venv `include-system-site-packages=false`；79個installed distributions除受驗本案wheel外全部match同目錄`wheel-install-constraints.txt`。無analysis_agent／jd_relational或舊checkout路徑，不是借用App site-packages。

```powershell
& S:/caliburn/.research-tmp/jd-memory-c-clean-venv/Scripts/python.exe -I -B S:/caliburn/.research-tmp/jd-memory-c-app-dist-20260913b/wheel_isolation_check.py
uv pip check --cache-dir S:/caliburn/.research-tmp/uv-cache --python S:/caliburn/.research-tmp/jd-memory-c-clean-venv/Scripts/python.exe
```

封裝代理首次漏傳cache參數，被預設cache存取拒絕；補正既有參數後通過，未安裝／升級套件。

## 文件問題及處理

1. **接續狀態矛盾，已修。**計畫頁首/表格仍稱未提交、CA未修與H2獨審未完成，OI頁首也仍列OPEN。改成7181db63及H4；舊表與反例明標交接歷史，已驗步驟保留為規範，不能再當新待辦。
2. **全組與舊獨審可追溯性不足，如實列界線。**本次未找到2740／22／130三組完整原始輸出與原獨審逐字產物路由；不能單憑作者整理重新背書每個數字。結果稿保留作者歷史記錄並連本次獨立證據，沒有為補數字重跑全suite。既有聊天歷史分頁問題仍在OI-05，本次未另重跑基準worktree或改該程式。
3. **多call未驗的理由不準，已修。**outgoing禁parallel斷言與MockTransport故意回錯誤多call不衝突；應寫尚未驗，不是技術上不能驗。已有單元＋本次native close證據，完整owner／HTTP仍列非阻擋界線，不擴產品需求。

本次不修改產品程式、不開始H4、無merge／push或正式切換。接受H2–H3在上述範圍的完成結論，下一只做既有B1／B2／顧問方法的採用映射，再按原計畫接合。既有非JD顧問成果不可被解讀成需從零開發。
