# JD 本機持久配置：DA-03 有界前置研究

- 查閱日期：2026-09-13；Topic：JD-R002／RS-3／DA-03。
- 狀態：主代理已採為下一有限驗證方向；尚未實作或完成行為實證。本文件沒有改變 production authority，沒有實作設定、初始化資料庫或執行 DPAPI 加解密。
- 依據：[目前決策](../../current-decisions.md)、[新版施工計畫](../../plans/2026-09-13-jd-relational-app-implementation.md)、[DA-03 缺口](../2026-09-12-jd-design-readiness-audit.md)、[自動保存 §5](../2026-09-12-jd-autosave-and-handoff-design.md#5-瀏覽器暫存與重開)、[歷史與恢復 §7](../2026-09-12-jd-history-and-recovery-design.md#7-驗收與剩餘工程前置)、[refs 前置](2026-09-13-jd-read-reference-preflight.md)、[Windows 宿主結果](../2026-09-13-jd-host-restart-recovery-slice.md)。
- 已讀實作：[references.py](../../../experiments/jd-relational-app/src/jd_relational/references.py)、[windows_host.py](../../../experiments/jd-relational-app/src/jd_relational/windows_host.py)、[host_runtime.py](../../../experiments/jd-relational-app/src/jd_relational/host_runtime.py)。本文只處理持久身分與本機配置；瀏覽器恢復記錄的 IndexedDB schema、容量及更新順序仍由 DA-03 後續單位閉合。

## 1. 推薦與有效範圍

**本機固定設定位置＋一份 Windows DPAPI 保護的設定內容；安裝身分固定、資料集世代明示更新、簽章金鑰正常重開不變。**沿已鎖的 pywin32 呼叫正式 Windows API，Python 標準庫負責小型序列化、隨機值及檔案 I/O；不新增 secret manager、背景設定服務或通用配置框架。

本輪推薦**不為配置新增 DB 表**。設定只負責連到哪個受管理的本機資料集、使用哪個宿主身分與 signer；JD current、revision、operation、訪談及 Memory 仍由原保存責任方負責。配置不存文件清單、head、receipt、run 狀態或來源副本。

此結論的必要界線是：**更換資料庫、重建及備份還原必須經 App 明示維護流程。**不能允許普通啟動以環境變數覆寫資料庫後，仍沿用舊 dataset incarnation。繞過 App 直接把 PostgreSQL 還原成舊內容，而保留全部本機配置不變，並不是本方案能自動識別的行為；本文不聲稱這項能力。若後續要求辨識外部任意還原，必須另定可驗證的需求，不能把新增一欄 epoch 或 PG 系統識別碼當成已解決。

## 2. 官方來源、版本與限制

以下均於 2026-09-13 核對。正式 API、框架能力與本案配置布局分開記錄；沒有把 Windows 或單一框架選擇稱為各大廠統一內部實作。

| ID | 官方來源及適用版本 | 穩定性、授權與本輪使用界線 |
|---|---|---|
| LC-S01 | [Microsoft CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)、[CryptUnprotectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata) | Win32 正式桌面 API；本機已驗 Windows 10.0.26200。Windows 系統元件不是 OSS 套件，沿既有 OS 使用，不複製官方範例或採雲端服務。DPAPI 一般綁目前登入使用者及電腦，漫遊設定有例外；不是可攜備份格式。PromptStruct 互動流程已棄用，官方記載 2027-02 移除，不能採舊教學的 prompt 路徑。 |
| LC-S02 | [KNOWNFOLDERID](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)、[SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath) | 現行 Known Folder 正式契約；`FOLDERID_LocalAppData` 是 per-user 位置。文件不要求 Caliburn 的子目錄名稱，也不保證任何使用者自行更改的檔案 ACL。 |
| LC-S03 | [pywin32 b312 DPAPI 原碼](https://raw.githubusercontent.com/mhammond/pywin32/b312/win32/src/win32crypt/win32cryptmodule.cpp)、[Shell 原碼](https://raw.githubusercontent.com/mhammond/pywin32/b312/com/win32comext/shell/src/shell.cpp) | 已安裝並鎖定 **312**，本地 METADATA 列 Production/Stable；Python 3.12 可用。整包依各檔授權，不能一概稱 MIT；沿[既有 pywin32 授權核對](../2026-09-13-jd-host-restart-recovery-slice.md)。本轮只檢查模組與原碼，沒有以真金鑰試跑。 |
| LC-S04 | Python 3.12 [secrets](https://docs.python.org/3.12/library/secrets.html)、[uuid](https://docs.python.org/3.12/library/uuid.html)、[os](https://docs.python.org/3.12/library/os.html) | 實際 runtime **3.12.13**；現行 3.12 文件顯示 3.12.14，不據此升級。穩定標準 API、PSF License；`secrets.token_bytes` 用 OS 安全隨機源，`uuid.uuid4` 是隨機 UUID。檔案 rename／flush 不可擴稱為設定與 PG 的共同交易。 |
| LC-S05 | [ItsDangerous General Concepts 2.2.x](https://itsdangerous.palletsprojects.com/en/stable/concepts/) | 已鎖 **2.2.0**、BSD-3-Clause、穩定。官方要求長隨機 secret，不進原碼／版本控制；salt 分用途，換 key 使舊 token 失效。金鑰的產生、保存與輪替系統不由套件提供。 |
| LC-S06 | [Windows Creating and Opening Files](https://learn.microsoft.com/en-us/windows/win32/fileio/creating-and-opening-files)、[MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)、[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers) | 正式 Win32 API，沿 pywin32／標準庫薄接合。檔案分享模式與排他建立有正式語意；不採 TxF、不加新的通用檔案交易引擎。flush 須檢查實際返回；沒有整台電腦斷電實證，不能承諾所有硬體故障下最新設定必然保留。 |
| LC-S07 | [ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)、[CPython v3.12.13 posixmodule.c](https://raw.githubusercontent.com/python/cpython/v3.12.13/Modules/posixmodule.c) | ReplaceFile 保留部分原檔屬性，但 `REPLACEFILE_WRITE_THROUGH` 明示不支援，部分失敗會留下不同檔名狀態。CPython 本版 Windows rename／replace 走 `MoveFileExW`；不可只引用 POSIX atomic rename 就宣稱 Windows 斷電持久性。 |
| LC-S08 | PostgreSQL 18 [pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html)、[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html)、[SQL Dump](https://www.postgresql.org/docs/18/backup-dump.html) | 本 App **18.6**；官方現行穩定 18 線，PostgreSQL License。單 DB dump 可得到一致資料庫視圖；不包含 Windows 設定／DPAPI 使用者環境。`--single-transaction` 使相容的 restore 命令全部成功或全部不套用，含 exit-on-error；不涵蓋檔案或外部資料，也不能和 parallel jobs 同用。 |
| LC-S09 | PostgreSQL 18 [System Information Functions](https://www.postgresql.org/docs/18/functions-info.html)、[Database File Layout](https://www.postgresql.org/docs/18/storage-file-layout.html) | `pg_control_system` 描述 cluster control file；DB OID 與名稱不是應用程式 restore 世代契約。沒有官方「自動偵測一份 JD 資料集被還原」API。本文不為讀取 cluster control 增權限。 |
| LC-S10 | [keyring 官方發行 25.7.0](https://pypi.org/project/keyring/)、[v25.7.0 Windows backend](https://raw.githubusercontent.com/jaraco/keyring/v25.7.0/keyring/backends/Windows.py) | 查閱時 PyPI 最新穩定 **25.7.0**（2025-11-16）、Production/Stable、MIT；`latest` 文件是 25.7.1.dev，不當穩定版本。Windows backend 使用 Credential Manager，預設 enterprise persistence；未安裝、未採用，僅比較必要接點。 |
| LC-S11 | PostgreSQL 18 [libpq Environment Variables](https://www.postgresql.org/docs/18/libpq-envars.html) | 官方不建議以 `PGPASSWORD` 暴露密碼，並提供 passfile 接點。這不表示環境變數全部過時；本案選受保護設定是為固定同一份本機接線與避免秘密出現在啟動命令／診斷。 |

## 3. 三種身分不能混用

| 值 | 唯一責任與建議來源 | 普通重開 | 明示還原／重建 |
|---|---|---|---|
| `installation_id` | App 初始化產生一次 canonical UUID；只供目前 Windows 宿主 mutex／Job 名稱及本機設定識別 | 保留；不是 PID、目錄 hash、DSN hash 或每次隨機值 | 同一本機安裝維護保持不變，沿同一所有權排除仍活著的舊宿主 |
| `dataset_incarnation` | App 對此受管理資料集發配的 canonical UUID，注入 `ReferenceCodec.dataset_id` 並提供非秘密的 client scope | 保留；不能依啟動時間改變 | 每次真正替換資料內容前明示換新，避免備份内相同 doc／revision／operation UUID 使舊引用或暫存重新有效 |
| `signing_key` | `secrets.token_bytes(32)` 產生的秘密；本案選固定 32 bytes，符合目前 codec 至少 32 bytes 契約 | 完整讀回相同 bytes；不得每次產生、硬編碼或從 UUID／密碼猜出 | 健康原 key 可保留，dataset 更換已可隔離；遺失、無法解密或明示輪替另走維護，不能普通啟動悄悄替換 |

UUID 的格式與安全隨機來源有官方契約；以上三種壽命與分工是**本案映射**。dataset incarnation 不是 JD head，不因正常編輯、撤回 JD 或新增文件改變。Memory／原始對話也不因 JD 撤回退回；真正完整備份還原是另一個明示維護行為。

外部 refs 仍為可解碼的簽章定位資料；把 key 放進 DPAPI 不會把 token 變成加密正文或 writer permission。原用途、document、revision、目標存在性、業務規則及 owner gate 都保留。

## 4. 最小保存位置與設定內容

使用 `SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, None)` 取得真實 per-user 路徑，再置於固定產品子目錄，例如 `Caliburn/JDRelational/host.v1.dpapi`。路徑名稱是候選，不是平台規範；不依 cwd、repo、Desktop、OneDrive 附件或開發者個人 home 猜位置。普通讀取不帶會建立目錄的 flags；建立只發生在明示初始化。

**推薦一份受保護的完整小型配置內容**，內部用嚴格 JSON／既有 Pydantic 驗證，包含：格式版號、維護階段、上述三個值、固定 loopback DB 連線欄位、checkpoint schema，以及明示 UI origins。DB 密碼與 signer key 都在受保護內容中；HTTP 只能取得所需的公開 scope／狀態，不能回整份配置。設定載入物件不輸出含秘密的 repr、原始錯誤、payload、DSN 或完整路徑。

建議配置讀取上限 64 KiB、解密後同樣受限，UUID／32-byte key／loopback 位址／合法 port／固定 schema／canonical origins／格式與階段各自 strict 驗證。64 KiB 是可調整的本案工程界線，不是 DPAPI 官方上限。拒絕 duplicate JSON keys、未知欄位、未知版本與非法組合，不用 defaults 修補損毀。金鑰若以 base64 放入內部 JSON，必須嚴格解碼及核長度；base64 本身不是保護機制。

實際 pywin32 b312 介面為：

```python
import win32crypt
import win32cryptcon

win32crypt.CryptProtectData(
    plaintext_bytes, DataDescr=None, OptionalEntropy=None,
    Reserved=None, PromptStruct=None,
    Flags=win32cryptcon.CRYPTPROTECT_UI_FORBIDDEN,
)
# returns protected bytes

win32crypt.CryptUnprotectData(
    protected_bytes, OptionalEntropy=None, Reserved=None,
    PromptStruct=None, Flags=win32cryptcon.CRYPTPROTECT_UI_FORBIDDEN,
)
# returns (description, plaintext_bytes)
```

本地唯讀 introspection 確认 b312 的 flag 位於 `win32cryptcon`，`win32crypt` 本身沒有該常數；不能直接照 C API 所在模組猜 Python 常數位置。此核對沒有加解密或讀取任何秘密。

只採 current-user 保護，不設 `CRYPTPROTECT_LOCAL_MACHINE`；不以固定字串或第二個密碼發明額外 key derivation。由 OS 既有檔案保護承接使用者資料目錄，不重演先前猜一組 user-only DACL 的做法。DPAPI 保護靜態 bytes，**不是隔離同一使用者已執行的惡意程式、消除記憶體中的明文，或保證備份在其他電腦可解密**。這些不是本機單人 App 新增登入／ACL 的理由。

**有限替代：**keyring 25.7.0 的 Windows backend 是成熟 OSS 能力，但需新增套件及「credential entry＋設定檔」的對應／缺損恢復，並明確處理其預設 enterprise persistence；目前 Windows-only、小型完整配置已有 DPAPI，沒有會改善本需求的必要缺口。若未來跨平台安裝或共用 OS credential 管理成為實際需求，再評估採用；不為追新先裝。亦不把 `PGPASSWORD`／明文 `.env` 當日常設定或備份秘密格式。

## 5. 初始化、一般開啟與缺損停止

| 操作 | 必须具備的行為 |
|---|---|
| 第一次明示初始化 | 一次產生 installation／dataset／key，先以排他建立語意保存 `initializing` 配置並讀回核對；已有配置不得覆蓋。取得同一 installation 的原生 host 所有權後，才執行明示 migration／Saver setup；完整核對後發布 `ready`。 |
| 初始化被中斷 | 配置或 schema 不完整就停止普通開啟。明示續作沿原身分與原已記錄階段，不重新配 key／UUID；現有未知資料庫不當空白庫清除或重新初始化。設定完全遺失時不得換一個新 installation UUID 嘗試繞開可能仍存活的旧宿主。 |
| 普通開啟 | 只讀既有配置→DPAPI／版本／內容驗證→使用原 UUID 取得 OS host lease→讀檢查實際 schema／PG／checkpoint prerequisites→完成既有 startup reconciliation→才提供寫入。沒有 setup、建立隨機 key 或環境變數備援。 |
| 配置缺少、截斷、拒絕存取、無法解密、版本不符 | 固定錯誤與維護入口，停止進 DB／模型／新 writer；保留現場。不顯示「空白文件」代替出錯的資料集，不自動刪檔、降級明文或新建資料庫。 |
| 更換 DB 接線或 secrets | 沿同一 installation 的排他維護流程，不能在正在服務的 host 內熱換。DB 替換時一定更新 dataset；純 UI 顯示設定不因此更換 dataset。 |

普通開啟若因缺損無法取得原 installation 身分，安全修復需先找回已知有效配置／身分並完成原宿主排除；此時沒有「產生新 UUID 就算重新安裝」的捷徑。跨電腦重新安裝與遺失整個 Windows 使用者環境不在本輪一般開啟能力內。

檔案发布使用同目錄暫存、完整寫入、flush／讀回驗證與原生 rename／replace；首次建立不可覆蓋另一個初始化者。細部採 Python 或 pywin32 接點由有限 Windows 反例決定，不另建通用 transaction manager。**不能假定檔案替換＋PG 變更是同一交易**；維護階段要先持久標記，未完成時普通開啟保持停止。尤其不能使用不受支援的 `REPLACEFILE_WRITE_THROUGH`，也不能因 `os.replace` 成功就宣稱斷電演練已通過。[LC-S06](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)、[LC-S07](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)

## 6. 備份／還原與 DB schema 是否新增

**本輪只定必要接點，不宣稱完整備份交付。**PG 的一致 dump 與 Windows 配置快照是不同範圍；完整產品備份仍須按實際 owner 包含 JD、訪談、Memory、checkpoint／歷史及相容版本，不能只備份十三張 JD 表就稱完整。DPAPI 配置可以隨本機災難修復材料保存，但它不是可攜明文金鑰包；也不能將舊設定整份覆蓋成正常運作設定而復活舊世代。

推薦的明示還原順序：

1. 以原 installation 排除既有 host／writer，核對備份來源與支援版本；記錄維護中，停止一般開啟。
2. 配發**新的** dataset incarnation，保存於維護中配置；舊值只可保留在診斷／備份描述，不能供正常 signer 驗證。原 installation 保持不變。
3. 沿官方工具執行已選定範圍的 restore；可相容時用 `pg_restore --single-transaction`，檢查退出結果及原生 DB／checkpoint 一致性。檔案與各保存 owner 若不同庫／不同媒介，須另驗一致範圍，不能沿單 DB dump 推定已涵蓋。
4. 確認恢复成功後才發布 `ready`。任何中斷、回覆不確定或配置發布失敗保持維護中；不能靠 retry 啟動重新 restore 或當作空白系統。
5. 新 host 將新 dataset 注入 codec／公開 scope，瀏覽器保留舊暫存供閱讀或人工比較，禁止自動套用；原 operation 結果也只能按新資料集實際保存內容查回，不因舊頁請求不見而重播。

**為何目前不新增一張 dataset 表：**在受管理、同一安裝只有一個配置入口的邊界內，host 配置可以是唯一資料集世代發配者；普通開啟不另增或雙寫 DB epoch。PG cluster `system_identifier`、DB 名稱與 OID 不能取代此應用語意。把 epoch 放进 DB 單列固然能提供明確資料库身份校驗，但 dump/restore 也會带回舊列，仍需維護流程換世代；同時在本機檔與 DB 存「目前 epoch」又須定兩者衝突權責。**新增 DB metadata 不是錯誤方案，但沒有解決本案尚未要求的外部任意還原偵測，也不是目前必需。**[LC-S08](https://www.postgresql.org/docs/18/app-pgdump.html)、[LC-S09](https://www.postgresql.org/docs/18/functions-info.html)

本配置不往 `jd_document` 的任意一份文件、Memory、checkpoint message、資料庫 COMMENT 或 Alembic 版本表塞系統世代，也不建立平行 document catalog。如果將來允許多安裝共同指向同一 DB、任意更改 DSN 或未受管理的資料庫替換，應重新選定唯一的 dataset authority；不能沿本方案擴稱支援。

## 7. 不能漏接的業務邊界

`ReferenceCodec` 已核 dataset，但其存在不代表全部 App mutation 都已隔離。新建文件、只帶 UUID 的目錄操作與恢復操作可能沒有 field／base token。因此產品需提供**非秘密的目前 dataset incarnation**，並在所有這類 mutation 的 App admission 核對呼叫者預期世代；具體 DTO／header 由共同契約正式生成，不在本文發明第二個工具格式。

Web 恢復記錄仍需依資料集、文件、頁面 session generation 及原 operation 區分；只是前端比較不夠，server 不能接受舊世代的無 ref 修改。已簽 refs 的讀／改保留原驗證，不能把公開 dataset UUID 當 token 簽章或授權替代品。資料集世代變更後來源 owner 仍按其原契約回查，不能為恢復新增另一份 Memory／來源別名。

## 8. 有限驗證矩陣與停止條件

| ID | 反例／驗證 | 通過要求 |
|---|---|---|
| LC-01 | 普通開啟時配置／目錄不存在 | 不建立檔案、UUID、key 或 DB；固定缺設定提示。 |
| LC-02 | 兩個明示初始化同時開始；初始化寫入中止 | 只有一份原配置及同一 installation；另一方不能覆蓋、另開 host／DB，殘缺狀態停止而非重設。 |
| LC-03 | 配置空檔、截斷、bit flip、未知版號、extra／duplicate key、超限、invalid UUID／key | 讀取／解密／strict 驗證拒絕；沒有 plaintext fallback，沒有帶秘密的例外鏈或 log。 |
| LC-04 | 相同使用者、相同配置、全新 Python 程序 | 原 installation／dataset／32-byte signer 相同，先前合法 ref 可核；測試只用合成秘密，結果不印 key／DSN。 |
| LC-05 | 明示資料集換世代，doc／revision UUID 恰好相同 | 舊 ref／cursor 拒絕；無 ref mutation 也因世代不符零套用；新讀取得新 scope。 |
| LC-06 | 只換環境變數 DSN／cwd；另一份配置被錯指定 | 普通入口不改實際資料集；未知 scope 不自動採用。 |
| LC-07 | 正在運作的原 installation＋嘗試重建設定 | 不以新 installation key 逃離原 host 互斥；維護只在可證明舊組已停止後開始。 |
| LC-08 | 配置發布前後故障、還原失敗、ACK 遺失 | 已驗的維護階段可檢查；沒有未完成卻開服務，沒有自動再次 restore；記首敗與恢復結果。 |
| LC-09 | 還原後重開持有 A 未知請求／B 草稿的舊頁 | 保留可讀輸入，禁止跨資料集提交；不依相同文件名稱配對或改 base／operation 後重發。 |
| LC-10 | DPAPI 另使用者／不相容系統環境 | 實際環境允許時驗拒絕或明示平台例外；不能用 fake adapter 宣稱跨帳號隔離實測。 |
| LC-11 | DB schema／Saver prereq 缺失與版本錯誤 | 普通開啟只有 read checks，不 setup、不刪資料；配置不變成第二個 head／receipt authority。 |
| LC-12 | UI origins／checkpoint schema／secret 讀取錯誤 | 原本機 HTTP／host 驗證仍生效，公開 metadata 只有需要的非秘密值，診斷固定且不包含配置正文。 |

本輪已完成官方 API／已裝原碼與版本核對，沒有完成上述行為測試。重要選擇已有證據，可停止同層廣搜；下一步沿已採的有限驗證邊界，實作有界設定載入／明示初始化並安排合成 Windows、新程序與真 PG 反例。DA-03 的瀏覽器恢復格式、完整備份還原及日常啟停仍須後續各自驗收，不能因設定檔可讀而標為整體完成。
