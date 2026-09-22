# JD 本機配置、初始化與一般開啟

- 日期：2026-09-13；Topic JD-R002，RS-1／2→3 局部接合；狀態：本切片實作、分層驗收與獨立審查通過，完整 App 未完成。
- 上游：[目前決策](../current-decisions.md)、[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)、[配置前置](evidence/2026-09-13-jd-local-configuration-preflight.md)、[初始化前置](evidence/2026-09-13-jd-managed-initialization-preflight.md)。
- 隔離 `experiments/jd-relational-app`；無 production 接合、真訪談或產品模型呼叫；ADR0075 Proposed、production ADR0060 不變。

## 1. 本單位效果

固定同一份本機設定，讓新程序讀回原資料庫、安裝身分、資料集與簽章金鑰。普通開啟只核對現有資料；首次初始化與中斷後接續是明示操作。缺設定或資料格式不符時停止，不自動另建空資料、產生新身分或替換秘密。

設定檔由 Windows DPAPI 保護，位於 OS Known Folder 的 `Caliburn/JDRelational/host.v1.dpapi`。一份空白且永久保留的 sibling `.lock` 只記「初始化曾開始」及序列化檔案發布，不保存第二份資料身分。首次建立後即使設定檔遺失，原 guard 阻止重新發配身分绕開舊宿主。普通讀取不建立目錄、guard 或設定。

新日常 HTTP 組合在 Origin 通過後，要求所有不安全 method 帶單一正確 `X-JD-Dataset`。包含沒有簽章 ref 的恢復入口；舊畫面不符時先回 409／重新讀取，不讀 body、不進 writer。GET 列表可取得目前公開 dataset；此欄位是資料範圍檢查，不是帳號授權。建立 body 的資料集、原請求 key、metadata ETag、ref／業務規則仍各負原責任。

`python -m jd_relational` 提供維運者 `status`、`init`、`resume-init`、`serve`：固定設定位置，沒有任意 config path／DSN／身分參數。首次連線資料由本機互動輸入，密碼不顯示；非互動 init 停止。普通 serve 使用真 host、startup 恢復與同一組服務，單程序 loopback、無 reload／proxy headers；目前只有人工 API，尚無管理畫面。顧問 node 明示 unavailable，沒有假訪談結果或 provider 呼叫。

## 2. 分工與保存順序

| 元件 | 責任 |
|---|---|
| `local_configuration.py` | 內部 Pydantic strict 格式，拒 duplicate keys／未知格式／非法來源，不從環境補值；產生身分只限明示初始化。不是跨語言 API，未另造 JSON Schema。 |
| `config_file.py` | DPAPI current-user、64 KiB 明文／80 KiB 加密檔上限、排他建立、同目錄 candidate／backup、原檔 CAS；失敗保留現場，無自動 fallback。 |
| `configured_host.py` | 原設定 → 原 native host lease → 再讀設定避免等待期間改過 → 明示 setup 或普通 open。初始化更新 phase 保留原 key／dataset／installation。 |
| `storage_setup.py` | 固定 PG18.6／JD migration／Saver3.1.2 的唯讀核對與明示初始化；不新增資料表、migration engine 或自動修復器。 |
| `host_runtime.py` | OS 所有權後才開 DB；與 initializer 共用 `check_installed`，普通開啟不 setup；Saver search_path 僅自身 schema。 |
| `configured_api.py`／`managed_app.py` | 共用已驗 query/manual/catalog，補資料集門閘與真正的生命週期組合；不另算業務規則或宣告操作成功。 |

配置階段為 `initialization_pending → initializing → ready`。pending 時只能驗配置指定 DB 為空；原生 lease 下驗空後，先持久發布 initializing 再執行 DDL。JD 固定 Alembic migration 使用一個 SQLAlchemy transaction；Saver 依官方 autocommit 原生 setup，兩者不強包同一 transaction。完成後重查全套必要形狀與版本，再 CAS ready。`maintenance` 會停止普通啟動；實際備份還原留後續單位。

初始化中斷只能接原身分與有據的原生版本前綴；JD 接受空或完整固定版，Saver 接受已記連續前綴及至多下一步已成功 DDL。版本洞、同名錯形狀、unknown objects、已有業務資料或 invalid concurrent index 均保留並停止。ready 發布回覆遺失不謊報完成；新的只讀 `status` 可確認現在 phase，再決定普通開啟或明示接續。

## 3. 官方依據與本案取捨

2026-09-13 重查 [AWS hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html) 與 [安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)：共同 domain 不依賴外部介面；原請求識別與意圖使重試可判斷。這支撐人／AI 共用業務、原結果查回及本單位不另開保存路徑，沒有宣稱 AWS 指定本案 phase、表名或 header。

Windows、Pydantic、Alembic／SQLAlchemy、Psycopg／PG 及 Saver 的版本／授權／限制以兩份前置為來源；未升級任何依賴。OpenAI／Anthropic 工具與模型行為沒有在本單位變更，沿[已完成的兩家契約與 App 分工](evidence/2026-09-13-jd-app-boundaries-errors-logging-evidence.md)，不重開同層廣搜。

有限實測發現 **pywin32 b312 ReplaceFile wrapper 把 target／candidate 轉成反向參數**；[官方 b312 原碼](https://raw.githubusercontent.com/mhammond/pywin32/b312/win32/src/win32file.i) 3674–3690 與新合成檔實驗相符。因此僅此 API 用 Python ctypes 薄接 [Microsoft ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)，依 target、candidate、backup 正確順序，不在 App 倒填參數依賴上游錯誤、不放寬 ACL、不用不支援的 WRITE_THROUGH。其他 Win32 能力沿 pywin32。

[Uvicorn programmatic deployment](https://uvicorn.dev/deployment/) 及已裝 0.52.4 `main.py` 支持 app instance 的單程序執行；本案需先在專用程序主執行緒 bootstrap，再啟動 event loop，故用明示 programmatic instance、workers=1／reload=False。0.52.4 為已鎖穩定 BSD-3-Clause 發行；這是 Windows 本機宿主映射，不宣稱所有服務都應單程序。

## 4. 實證與審查

程式停止寫入後執行完整回歸；分開 DPAPI／真 Windows 新程序、合成 ASGI、真 PG、固定分支故障及維運入口，不累加不同批次。

| 範圍 | 實際結果及限制 |
|---|---|
| 全組、PG opt-in 關閉 | **1528 PASS／178 PG SKIP，23.87 秒**；含真 Windows 配置／程序與合成 ASGI，非全部純記憶體測試。一筆既有 Starlette/AnyIO alias 棄用警告保留。 |
| schema helper 最終組 | **40 PASS＝22 純測＋18 真 PG，5.25 秒**；真 PG 使用合成 lease 分支，原生 host 證據另列。來源 hash 後續追加只窄驗既有一案 PASS。 |
| 新 DPAPI／Windows／PG／HTTP 完整組 | **6 PASS，21.91 秒**：初始化、修改、查回、重開、ready 發布後 ACK 遺失及四個不完整配置拒絕。一般開啟禁止四個 setup 入口；正常離開確認 native PID 退出、close=true。 |
| schema P2 修正後跨接點回歸 | **3 PASS，21.81 秒**：新配置完整旅程＋既有人工 HTTP＋catalog HTTP，皆真 Windows／PG／Uvicorn 新程序；舊署名 ref 重開仍查回原結果、不重播 SQL，schema OID 保持。 |
| root 獨立原生配置重跑 | **31 PASS，1.23 秒**；合成路徑，沿同使用者原生檔案權限執行，未改 ACL。 |
| 契約／型別 | 八組 SSOT 的 Python／TypeScript 生成一致，TypeScript check 通過；本單位沒有手改生成檔或新增依賴。 |
| 獨立審查 | 配置／DPAPI、HTTP 資料集、managed App／CLI 各 PASS。schema reviewer 提出的 P2 已修，22 純測＋4 記憶體反例及來源窄測複核 **P2 CLOSED**；reviewer 未冒稱重跑 PG。 |

- 配置最初缺新模組造成收集失敗；擴充測試曾因 pytest 過長參數ID與 PermissionError fixture 不等於 Win32 share violation 失敗，修測試後真 native 31 PASS，等待有界化再窄驗 4 新程序 PASS。
- 初始化／host orchestration、phase發布回覆遺失以合成邊界反例驗證；真 native 接合另列。managed_app 首輪 1 FAIL 是測試期待內層錯誤，但原 query lifespan 會再遮蔽成固定外層錯誤；確認既有契約後修 test，未放寬產品錯誤處理。
- 配置／DPAPI 與 HTTP 資料集兩路獨立唯讀審查沒有 P1／P2。獨立 reviewer 重跑 native 配置時在 pytest 暫存目錄受 WinError5 阻擋，31項未執行；不能混稱 reviewer 通過，另用實作者及整合的真 native 證據。
- schema P2：原 CHECK 只核名字、partial predicate 只核存在，接受同名錯義規則。真 PG `format_version=4`／`WHERE origin='manual'` 兩反例先失敗；改以固定版官方 PG canonical profile 核 **29 CHECK＋12 predicates** 後通過。profile 只作相容性證據，來源 migration／metadata hash 在測試核對，不從日常 DB 重設期望、不新增 SQL parser。[修正實證](evidence/2026-09-13-jd-managed-initialization-preflight.md#10-p2-收尾同名規則也必須有正確意義)
- pywin32 反向參數現場：`S:/caliburn/tmp/config-api-probe-79964f09c9bd418697272b8c1093f5c5`。native config 測試現場：`S:/caliburn/tmp/jd-cf4`／`jd-cf5`。全部為合成資料，非真設定。
- 新程序完整旅程證據：`S:/caliburn/.research-tmp/jd-configured-host-7739b05bc0644181907198747f773cbc`；ready ACK 遺失：`jd-configured-host-b8fa515bae6141fe967d58036d0fee2d`。root 完整回歸暫存為 `.research-tmp/jd-managed-full-20260913-01`，窄 native 另保留各自 boot／finished／process 記錄。測試以新 `caliburn_jd_setup_test_<uuid>` DB 保留現場，不 DROP／清原 fixture。
- P2 修正後 root 三案現場分別為 `.research-tmp/jd-configured-host-68dd94d346e743688b5193e6fef595a3`、`jd-manual-http-a2ca21766aee4ab18f3cee0373bc3fbd`、`jd-catalog-http-43da7420050946e8a47cb111f021e33a`；再讀核 **7 個 zero-exit 與 6 個 finished 紀錄**。27 檔精確單位核對68個相對連結、差異、生成物及依賴未變更；不帶入決策入口原有未提交歷史。

## 5. 通過界線與下一步

本單位不保證斷電、跨使用者解密、DPAPI與PG共同交易或繞App任意還原的自動識別。相同 Windows 使用者可運行的惡意程式不在 DPAPI 隔離保證。schema 核對是固定安裝相容性；本版 CHECK／partial predicate 已逐字核对，不作一般 SQL 等價證明，也不聲稱偵測任意外部篡改。受管理初始化與正常開啟不採納外部寫入；缺損先停止。

接續 RS-3 六章手動管理、瀏覽器自動保存暫存與恢復格式，使用本次真配置／共同 API；仍須後續接 AI 回合、來源、Memory、歷史還原／整輪撤回、日常圖形入口及完整備份。Excel 延後，實際模型費用與員工試用按原計畫另驗。不把 API／宿主通過稱完整 App。
