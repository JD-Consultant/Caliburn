# Q019 第二切片結果：Agent 循環與 PostgreSQL 重開恢復已驗證

- 日期：2026-09-06；最新狀態：**PASS（本切片範圍），12 passed／0 skipped**。Docker 恢復與真 PostgreSQL 補驗證見 §6–7；不等於完整 Memory／UI／真實模型效果完成。
- 範圍：[第二切片計畫](../plans/2026-09-06-analysis-only-agent-durable-conversation-slice.md)。
- 實作：S:/caliburn/.worktrees/analysis-only-agent，codex/analysis-only-agent。
- 最新設計與決策仍在主 checkout：[Runtime](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-runtime-design.md)、[register](S:/caliburn/docs/current-decisions.md)。

## 1. 本段真正完成什麼

使用官方 create_agent；模型要求工具 → 官方工具執行 → 同一循環帶結果再呼叫模型。新增一個公開 wrap_model_call middleware，只縮小單次 request 的對話視圖。固定 instructions 不放進 canonical messages，也沒額外設計隱藏思考筆記或第二份對話儲存。

沿用第一切片的 inline compaction helper，沒有換成會永久移除 canonical messages 的 generic summarizer。這是 Q019 已核准的效果選擇，不宣稱所有廠商實作相同。
[LC transient/persistent context](https://docs.langchain.com/oss/python/langchain/context-engineering)、[OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)。

## 2. 檢查與誠實界線

- 原有 8 項測試仍通過。
- 新增 compiled Agent 離線測試：工具接力的 encrypted reasoning／phase／tool pair；下輪 request 從 compaction 延續，原對話及工具結果仍保留；模型失敗後 None 續跑不重複員工輸入／已保存的測試 reader；文件 thread 隔離。
- 第一輪環境受阻時 **11 passed、1 skipped**；compileall 通過。只替換 HTTP 邊界，LC／SDK／compiled graph／serializer 是真的。InMemorySaver 只能證明這些接線，不是磁碟保存證據。
- PostgreSQL opt-in test：官方 PostgresSaver + setup、真實兩個 Python process、另一連線在模型回覆前看見 employee input、失敗後重新開啟續跑、native items／compaction／thread 隔離。第一輪跳過；Owner 准許恢復 Docker 後已於 §7 補驗證通過。
- 無 paid API、無 .env／金鑰讀取、無外部 tracing；API 費用 0。Synthetic opaque strings 不是服務端有效加密內容，不證明模型實際分析品質或 effective all_turns。

依據：[PostgresSaver setup](https://docs.langchain.com/oss/python/langchain/short-term-memory)、[sync durability](https://reference.langchain.com/python/langgraph/types/Durability)、[persistence/recovery](https://docs.langchain.com/oss/python/langgraph/persistence)。測試停在已保存工具結果後的 provider exception；不是 arbitrary power-loss／外部副作用 exactly-once 證明。

## 3. 實作中遇到什麼

### 測試假設修正，非 framework patch

初版測試期待 outgoing assistant text 仍有伺服器 msg ID。實際 source 顯示 store=False 時 adapter 刻意不輸出這個 lookup ID，但保留文字與 phase；reasoning encrypted content、call_id 也維持。測試改驗真正的延續內容，不修改框架 private converter、不捏造 ID。
版本依據：langchain-openai 1.6.0 的 chat_models/base.py，assistant content 重組區塊（store is not False 判斷）；[官方 adapter source](https://github.com/langchain-ai/langchain/blob/master/libs/partners/openai/langchain_openai/chat_models/base.py)為動態連結，重現以本切片 uv.lock 為準。

### 初始 Docker 環境 blocker（已由 §6 排除）

已安裝 Docker Desktop，但啟動時 backend log 明確顯示：
「initializing Inference manager… dockerInference… The file cannot be accessed by the system」。

這發生在 Docker engine／PostgreSQL 啟動前，不是 Saver 或 Agent 的錯誤。容器查詢無正常回覆；只啟動既有 Desktop 並讀取診斷，沒有 reset、移動 socket、終止其他服務、刪 DB 或資料。沒有另裝一套 PostgreSQL 迴避此 gate。需要先恢復 Docker，或明確提供可用的專用測試 PostgreSQL。

## 4. 尚未做與下一個 gate

沒有 UI、B extraction/consolidation、C live repair、Memory 搜尋、Skills、完整 token/run budget、非同步／串流或 JD；不接舊 App。這只是同步 Agent 的接線段落。

原 gate 是先恢復 Docker 再跑專用 DB 雙 process 測試，現已完成。下一步依 Q019 設計撰寫 Memory artifact／read-path 的有界計畫，再接 B/C；不重新討論已定選型，也不把本切片當作 Memory 已經完成。

## 5. 保存與 review

獨立 review：Critical 0、Important 程式阻塞 0；reviewer 當時獨立重跑 11 passed／1 skipped。兩項 Minor 已補強：直接斷言 canonical 的完整原生 AI 區塊；測試 DB 的 connection／statement／lock 等待有界。當時仍須 PostgreSQL 實測，現已在 §7 補驗證；不把設定完成與 DB 測通混為一談。

Review 修正後再跑：11 passed／1 skipped、compileall、uv lock --check --offline 與 git diff --check 通過。工程初值是測試 connection 1–10 秒、SQL 10 秒、lock 5 秒、子程序 45 秒；不是模型費用上限或業界統一值。[PostgreSQL timeout 設定](https://www.postgresql.org/docs/current/runtime-config-client.html)。

被測程式為本地 commit 3176e1e5、tag q019-agent-loop-offline-v1；該既有標籤只代表離線切片，不回寫或移動舊標籤。補驗證只更新紀錄／README，不修改程式。精確最新文件保存點見主 register；未 merge／push／修改 production。

## 6. Owner 准許的 Docker 恢復

本輪仍是 Q019／G5，只排除同一個 PG gate；Owner 回覆「可以」授權修復啟動，不重設、不刪既有資料、不重啟整台電腦／所有 WSL、不上傳 diagnostics。先停止 Docker，再針對已驗明只有執行期 socket 的目錄做可回復改名備份；驗證 engine 後才建專用 q019_agent_test DB。

本機證據：Docker 4.77.0 backend 在 dockerInference 啟動失敗；該項目是 0 bytes ReparsePoint，fsutil query 返回 Error 1920。Docker/run 只有三個 socket；另一路 docker-secrets-engine 只有 engine.sock。不是容器 VHDX 或 volume 資料。

來源：[Docker 官方診斷／restart 與 destructive reset 區別](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/)；[Docker 公開 issue #460](https://github.com/docker/desktop-feedback/issues/460) 有相同錯誤及父目錄改名的 workaround；[近期同類 #625](https://github.com/docker/desktop-feedback/issues/625)。Issue 是使用者實際報告，不冒稱官方核准／根本修復，也不由此斷言本機 NTFS 已損壞。若恢復後再次出現，另行討論版本修復或重啟，不反覆 reset。

實際操作：官方 stop 一般停止失敗，官方 stop --force 成功；確認 Desktop/backend 全停後，驗明父目錄不是 reparse point、內容全是指定的 0-byte socket，再改名並啟動。保留兩份備份：

- C:/Users/chenb/AppData/Local/Docker/run.q019-backup-20260906
- C:/Users/chenb/AppData/Local/docker-secrets-engine.q019-backup-20260906

引擎恢復，原有容器仍保留且未啟動舊產品；沒有 reset、刪除檔案、修改 settings、重啟電腦或全部 WSL。這是已驗證的啟動 workaround，不保證 Windows／Docker 根因永久消失。備份保留作回復與診斷，不自動刪除。

## 7. 真 PostgreSQL 補驗證與退出條件

新建完全隔離的 caliburn-q019-postgres 容器、caliburn-q019-postgres-data named volume、q019_agent_test DB，使用本機已有官方 postgres:16 映像（16.14，image ID fe03a7605299a34ddf5e4f285dff78c3d7190a576b3c6b46f2fcff69f4bffd54），只綁 127.0.0.1:55433。隨機測試密碼僅在該容器設定／測試程序環境，不輸出、不寫入 repo；沒有讀產品 .env。
[官方 PostgreSQL image 初始化](https://hub.docker.com/_/postgres)、[Docker 本機 port／環境變數](https://docs.docker.com/reference/cli/docker/container/run)。這是測試配置，不是 production 部署決策。

- 單獨 PG 測試：1 passed，7.19 秒。
- 完整測試（PG 已啟用）：12 passed，8.37 秒，0 skipped。模型 HTTP 仍為 synthetic，API 費用 0。
- 真實兩個程序接續、跨連線 input 保存可見、reasoning／phase／call/result 保存、compaction 不刪 canonical、thread 隔離均通過；不聲稱測過突然斷電、資料庫 failover 或 LLM 語意品質。
- 本次測試隨機 thread 經官方 delete_thread 清除後，checkpoints／checkpoint_writes／checkpoint_blobs 對 q019-test-% 的筆數均為 0；專用 schema 與 volume 保留可重跑。未刪員工資料或舊 DB。
- 引擎正常，只有專用測試 PostgreSQL 正在運行，restart policy=no。本輪不再反覆重啟 Docker 測故障；再次發生才重開環境題。

本 gate 已解除，不需改框架接法。接續的產品工作是 Memory，不是繼續擴大環境修復。
