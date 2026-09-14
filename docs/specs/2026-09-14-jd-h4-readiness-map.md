# 新 JD App：施工順序五項的現況與唯一阻擋

日期：2026-09-14；Topic：JD-R002。這份只做一件事：把施工順序的五項，逐項對到**可以自己去看的證據**（tag、結果稿、測試），並說明剩下什麼、為什麼剩下。不重述設計，不代替[收尾清單](2026-09-13-jd-app-open-issues.md)。

基準 `f160be97`；本階段最後一個 tag `jd-review-fixes-20260914` 指在目前 HEAD。下列 tag 都是本地 tag，沒有 merge、push 或切換 production authority。

## 1. H4-R1：固定 target 與有界批次，真 PostgreSQL

**完成。**tag `jd-b1-fixed-target-batch-20260914`、`jd-h4-r1-postgres-batch-20260914`。

source owner 自己發 `purpose=window` 的固定 target，依 publication cursor 切連續有界 batch；caller 不解 token、不拼 first/last、不回 latest。一批 B1 在真 `PostgresSaver`／`PostgresStore` 上保存，故障後關閉重建資源續作，重抽與重複 request 查回都驗過。結果：[批次接點](evidence/jd-b1-adoption/fixed-target-batch-results.md)、[R1 真 PG](evidence/jd-b1-adoption/r1-postgres-batch-results.md)。

## 2. H4-R2：B1→B2→publication 有序交接

**完成。**tag `jd-h4-r2-consolidation-20260914`。

B2 逐字採用，兩批有序交接、B2 pending 重建資源續作、發布回覆遺失以原 request 查回、C 較晚更正都在真 PG 上驗過；未發布不推 cursor、不開始下一批。結果：[R2 交接](evidence/jd-b1-adoption/r2-consolidation-handover-results.md)。

## 3. H4-R3：通知、准入、宿主生命週期、顧問方法

**除了一件事以外完成**（那一件見 §6）。

| R3 子項 | 狀態 | 證據 |
|---|---|---|
| 1. 明示初始化最小准入狀態 | 完成 | `jd_memory_admission` 依 [ADR0076](../adr/0076-jd-background-admission-record.md)；真 PG 驗保存、對帳、重複喚醒、受阻、封存 |
| 2. 純通知 call/result 辨識、停止、未知、恢復 | 完成 | [R3 結果](evidence/jd-b1-adoption/r3-notification-and-background-results.md) |
| 3. A 指引／三項分析 Skills／Memory 行動指引；人工與 LLM 同一 writer | 完成 | tag `jd-consultant-guidance-skills-20260914`、[結果稿](2026-09-14-jd-consultant-guidance-and-skills-slice.md) |
| 4. 安全回合與啟動恢復時喚醒同一背景入口 | 完成 | 同 R3 結果稿；重複喚醒不重跑、不換 target、不重設額度 |
| 5. 普通關閉與排空 | 完成 | 同上；宿主有限 worker、drain、Saver 關閉 |
| 6. 本機角色配置與狀態出口 | 完成 | tag `jd-provider-keys-20260914`；金鑰在 Windows 認證管理員，缺金鑰時人工 JD 照常、AI 顯示未啟用 |
| 7. 真新 Windows 程序＋真 PG 的四個停點續作 | 完成 | tag `jd-h4-r3-new-process-recovery-20260914`；已保存的模型結果與已提交的發布，在新程序都是 **0 次模型請求** |

## 4. JD editor：六章與其上的所有操作

**完成，並且每一項都有測試。**下表的數字是覆蓋該關鍵字的測試檔數（Python／Web），不是斷言數。

| 能力 | 測試檔（py／web） |
|---|---|
| 新增項目（六章 CRUD） | 10／1 |
| 排序與移動 | 10／1 |
| 成果／要求 | 15／4 |
| 知識技能多對多 | 7／0 |
| 來源 | 12／2 |
| 當輪差異 | 7／3 |
| 歷史 | 59／10 |
| 整輪 JD 撤回 | 7／0 |
| 整份還原 | 5／0 |
| 自動保存與瀏覽器暫存 | 0／6 |
| 封存／恢復 | 30／7 |
| 回覆遺失與查回 | 21／4 |

人工與 LLM 走同一 writer：`manual_command` 與 `model_command` 轉入同一 command，由同一 `JdStorage` 交易保存（`test_command_flow.py` 兩種模式都驗）。schema 由 SSOT 生成，`generate_contract.py --check` 相符。

本輪另外補上的：[整份還原與整輪撤回的真瀏覽器驗收](evidence/2026-09-14-jd-restore-and-undo-browser-results.md)、[還原確認期間暫停手改與新回合](2026-09-13-jd-app-open-issues.md)（OI-06 進度三）、[撤回來源記錄](evidence/2026-09-14-jd-restore-and-undo-browser-results.md)、[來源標記與點回原話](2026-09-14-jd-source-readback-slice.md)。

## 5. 產品驗收：已完成與未完成，分開說

| 驗收面 | 狀態 |
|---|---|
| Web／API／契約 | 完成；`tsc`、`npm run build`、`generate_contract --check` 通過 |
| 配置與啟停訊息 | 完成（tag `jd-operations-acceptance-20260914`）；**未做**：本機建立正式安裝後的 CLI 真程序啟停 |
| 備份還原 | 完成（tag `jd-backup-restore-drill-20260914`）；**未做**：世代輪替、異地保存、同名覆蓋還原 |
| 代表性真瀏覽器 | 完成三條旅程（還原、整輪撤回、來源點回原話）；**未做**：實體 IME、觸控、並行分頁、修改／刪除／移動的辨認（[OI-04](2026-09-13-jd-app-open-issues.md)） |
| 真 PG | 完成；全組 **3258 passed，0 failed**。先前那一項 [OI-05](2026-09-13-jd-app-open-issues.md) 分頁失敗已定案：錯的是那條斷言，不是實作或契約 |
| Windows 新程序 | 完成（背景四停點、宿主恢復） |
| 自然模型 3 職位各 2 次 | **未做**，需費用授權（[OI-09](2026-09-13-jd-app-open-issues.md)） |
| 3 名員工自行試用 | **未做**，需 Owner 安排真人（[OI-10](2026-09-13-jd-app-open-issues.md)） |

## 5.1 獨立審查

本階段 19 個提交已由非實作者[獨立審查](evidence/2026-09-14-jd-phase-independent-review.md)：八項發現全部修正（兩項 HIGH 都是「把不知道說成知道」），兩條沒有鑑別力的測試一併重寫，一句在當時不成立的文件宣稱已更正。採用保真度、撤回來源推導與不可偏離的產品效果由審查者獨立核對通過。窄複核進行中。

## 6. 唯一擋住「持續訪談」的東西

**A 顧問要用哪個 Anthropic 模型，還沒有人選。**

其餘都在位：金鑰讀取（Windows 認證管理員）、顧問指引與三項分析 Skills、十六個已註冊工具、純通知辨識、背景整理與發布、同一 writer、當輪差異、撤回與還原。`create_consultant_model(model_name=..., api_key=..., ...)` 只缺 `model_name` 這一個值。

這是費用決定，不是施工選擇：本 App 把 A 釘在 Anthropic 是既有決定，但已驗來源那邊的 A 走的是 OpenAI，所以沒有可沿用的既驗 model id。依指引「遇到會改變費用的問題，先停止回報，不要自行補做法」，這裡停住等 Owner 指名。

指名之後要做的事很小：`serve` 以該 id 與已保存的金鑰組出顧問、把 `build_consultant()` 接上日常入口，然後才是 OI-09 的付費自然驗收與 OI-10 的員工試用。**在那之前，日常 AI 維持未啟用，不能宣稱持續訪談可用。**
