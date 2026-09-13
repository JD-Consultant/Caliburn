# Memory 宿主：資源、重開與回歸結果

2026-09-13；[設計](../../2026-09-13-jd-memory-host-integration-slice.md)。Python 3.12.13、既有 App lock；PG18.6，零 provider 呼叫。Windows／PG 使用合成資料與隱藏的自有測試程序，未讀真實訪談／日常設定、未改正式產品。

## 實際接線

[host_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/host_runtime.py)讓同 host 擁有 Saver 與另一條 Store connection；Memory schema-mapped engine view 共用原 JD pool。前置不足不 setup；中途失敗清理所有已開資源。關閉先等原 owner 排空，任一活躍工作未結束則保留所有資源；排空後即使單項 close 失敗仍嘗試剩餘清理，回未確認。

[runtime_checkpoints.py](../../../../experiments/jd-relational-app/src/jd_relational/runtime_checkpoints.py)使用官方 `compile(store=...)`；真原生 child 的 `Runtime.store` 是 host 的同一 Store，預綁不同 Store 的 child 會被拒絕。沒有新增自製 Store／工作登記引擎或模型工具。

## 反例與分層測試

- 第一組資源測試 **9 PASS／5 ERROR／3.30s**：測試先要求新的 PostgresStore 接點，舊 host 尚不存在，保留缺能力反例。
- 接線後 host／checkpoint **69 PASS／2.56s**；增加實際 child Store 注入與另一 Store 拒絕，加配置／managed App 共 **98 PASS／9.73s**。
- 最後受影響七檔合組：`test_host_runtime.py`、`test_runtime_checkpoints.py`、`test_configured_host.py`、`test_managed_app.py`、`test_storage_setup.py`、`test_memory_setup.py`、`test_init_test_runtime.py`，**154 PASS／9.63s**。只有原上游 Starlette／AnyIO deprecated alias 警告，未為此改動無關版本。
- [初始化結果](setup-results.md)的 **33 真 PG** 是不同資料庫初始化／故障案例；[fixture 前置](host-preflight.md)的兩個 host schema 明示補表，有變更前後所有既存 table 的筆數／內容摘要相同證據。它們不代替下方新程序驗收。

## 新程序完整 Memory 核心旅程

測試：[test_memory_host_native.py](../../../../experiments/jd-relational-app/tests/test_memory_host_native.py)；沿既有 [configured_host_worker.py](../../../../experiments/jd-relational-app/tests/configured_host_worker.py)，Memory 合成操作在 [memory_host_journey.py](../../../../experiments/jd-relational-app/tests/memory_host_journey.py)。

1. 真 DPAPI 設定與 Windows host 在新合成 DB 明示初始化。
2. 首個工作程序從 `open_managed_app` 取得真正 host 的 Store、publication view 與原話 owner。建立 JD、兩輪合成原話及詳記，發布 Memory 初版及修正版。
3. Memory 舊回執取回不倒退目前版；修補不前進背景游標；JD 仍是原本第一版，沒有 JD operation。
4. 真執行緒透過 `ManualRuntime.inspect_document` 保持 Memory 讀取未結束。`host.close(timeout=0.01)` 回 False，Store／Saver 都仍 open；放行後讀到正確導覽，再 close 成功。
5. 首程序退出後，以同設定啟動另一程序：不執行任何合成節點，讀到原話原字元、詳記、Memory 舊／新版及兩個原回執；再次驗登記讀取的排空。schema OID 保持相同。

普通 open 的 setup 入口以測試 hooks 禁止（主 initializer、Saver／Store／PublicationStore setup、Alembic），且核 schema OID 不變；實作本身不在普通 open 呼叫建表。測試主 thread 的 Memory 發布／原話建立屬同步合成 fixture，**不冒稱模型 Memory writer／背景排程已接入**；只有後段明確登記讀取的排空是目前實際驗證範圍。

首跑一般沙箱 **1 FAIL／14.75s**，原生配置替換回 `configuration_write_unconfirmed`，現場保留於 `.research-tmp/jd-configured-host-e621c0c2bc5c469ab78b44fe3f52e819`；未把未知結果當成功，也未清除候選檔或 DB。改以本機使用者權限執行後初始化通過，**1 FAIL／15.98s** 停於新 Memory fixture；獨審核出 `source` 是 keyword-only，修正测试呼叫，不改產品核心。

最後 **1 PASS／40.89s**。證據目錄：`.research-tmp/jd-configured-host-705b36f415204e338cbe1f2dae2ac03f`；DB `caliburn_jd_setup_test_2f17929a73714bafb43d8d61b370c6df`。Memory head **2**、receipt **2**、artifact **6**；JD revision **1**、operation **0**。首程序合成節點 **2** 次，重開程序 **0** 次，provider **0**。

## 原有旅程回歸

同一本機使用者權限，明示補好兩個合成 host schemas 後，以下 **3 PASS／85.12s**：

- `test_host_recovery_postgres.py::test_committed_ack_lost_crash_returns_exact_original_receipt_without_new_revision`：JD SQL 已保存而回覆遺失，舊程序退出後查原回執，不加版本。
- `test_ai_host_restart_postgres.py::test_fh03_original_a_and_commit_ack_lost_b_keep_exact_receipts_without_replay`：固定 SDK 的原 AI 操作與後續提交回覆遺失，真新 host 查原結果，不重播模型／命令。
- `test_configured_host_native.py::test_real_initialize_open_edit_and_restart_keep_original_dataset_and_signer`：真配置、HTTP 手改與另一程序重開保留原身分、文件、簽署來源及回執。

實作未改 Web／公開 wire／provider，因此未重跑無關 UI 或自然模型。獨審的 **71** 與 **56** 窄組分別見[review](review.md)，與作者範圍有重疊，不相加成案例總數。

## 未完部分

此單位已接一般 host 的 Memory 資源與儲存初始化。模型的固定 Memory head／導覽投影、按需工具、C 修補、B1/B2 完整窗口與背景整理尚未接；未宣稱它們已受本輪排空測試覆蓋。來源 UI、備份還原、自然品質與日常 AI 啟用仍在[唯一清單](../../2026-09-13-jd-app-open-issues.md)。只看當輪 JD 改動的需求保持，沒有追加舊對話選輪入口。
