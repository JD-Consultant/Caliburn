# T05：Memory 工具與唯一 V4A

- 日期：2026-09-30；狀態：**施工中**。本頁記實測與後續接縫，任務完成狀態在 [tasks](../tasks.md#t05-memory-讀寫工具與唯一-v4a)。
- 上位：共同工具、Memory read/update 契約由任務表路由；編輯機制的唯一說明在 [正文編輯接線](../../../implementation/memory-body-editing.md)。無 production 切換、無舊資料搬遷。

## 1. 研究與取捨

主代理讀完三份工具責任契約、CRUD 範例與工程規範；官方 OpenAI Docs 技能用於核對 V4A 的執行方責任。研究子代理唯讀核對最新／本地 helper source、license 與合成反例；主代理直接讀完整本地 source 及固定版 MIT 全文。

- 官方 helper 的 `_read_section` 可重用；first-match、EOF 內文 fallback、忽略終止符後資料不符合本案契約。只抽取語法演算法，不引入 Agents SDK orchestration。
- 子代理核對固定 source 與新 main，另執行 22 項原 helper 純字串 assertions；此為研究證據，**不是新 adapter 驗收數字**。具體來源、commit、hash、license 見 [第三方註記](../../../../apps/api/THIRD_PARTY_NOTICES.md)。
- 主代理核對 RapidFuzz 官方 API／PyPI 3.14.6、安裝包 MIT；只新增成熟字串距離套件，不自製距離演算法。版本與 hashes 在 backend lock；新隔離 Python 3.14.7 可安裝。
- 不採早期探針的「精確先於模糊」政策；合格位置全部計數，避免有精確位置就忽略另一個近似位置。這是可測的保守取捨，不宣稱最優或完全避免模型語意誤改。

## 2. Red → Green 與審核發現

1. 新介面先無編輯效果；中文模糊 context／混合換行測例實際 **1 failed**，正文仍是每月而非每週。不是 import／安裝失敗冒充 Red。
2. 接上完整 parser／定位／原文切片後，該例通過；後續加入歧義、非法尾段、零匹配、多 hunk 與長文反例。
3. 獨立來源審核指出合法 EOF 純新增會被過嚴語法拒絕；主代理另補重用父 anchor 測例，得到 **5 failed、47 passed**。依唯一 EOF 與順序游標修正後 **52 passed**。不因既有測例綠色就縮減 V4A 能力。
4. 一個雙近似 fixture 的第二行實際只有 0.895、未達 0.90，已修正合成案例，使其真正有兩個合格位置；沒有降低政策讓錯誤 fixture 通過。
5. 獨立程式審核找到三個可重現缺口：結果可超 body 上限、相同多行替換改掉混合換行符、EOF 插入接受空白來源。主代理加入六個測例，實跑 **6 failed、53 passed**；修正後正文編輯器 **59 passed**。只補安全邊界，不新增保存或工具能力。

命令均在 `apps/api`：

```powershell
$env:PYTHONUTF8 = '1'
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_memory_body_edits.py -q -p no:cacheprovider --tb=short
./.venv-target/Scripts/python.exe -m ruff check src tests --no-cache
./.venv-target/Scripts/python.exe -m mypy --cache-dir ../../.research-tmp/mypy-t05 src
```

最終切片檢查（2026-09-30）：

- `pytest tests/unit tests/contracts -q -p no:cacheprovider --tb=short`：**246 passed**，含上述 59 項正文編輯測例；不是整個 T05 或產品驗收。
- `ruff check src tests --no-cache`、`ruff format src tests --check --no-cache` 通過（134 files）；`mypy --cache-dir ../../.research-tmp/mypy-t05 src` 通過（108 source files）。修正期間曾有一行超長，已調整，不弱化檢查。
- uv 0.12.20 在新目標隔離環境建 wheel，檢查包內確有 adapter 的 MIT 授權文件與 RapidFuzz 3.14.6 dependency；未發布套件。系統 uv 0.10.8 不符專案版本要求，改用既有研究 runtime，不修改舊產品環境。
- 本地文件檢查涵蓋 14 個本切片／責任檔案、232 個連結，0 errors；`git diff --check` 通過。
- 獨立程式審核另做 20 項記憶體內控制測試；三個 findings 已用主測試重現並修正，不將控制測試混入 pytest 數字。
- 132,035 字元中文 Markdown 合成 probe 單次約 3.91 ms；只證明本例可執行，不是完整負載基準或時限保證。

本切片未碰 DB schema／交易，故依風險執行純運算、unit／contract 及靜態驗證，沒有重跑 PostgreSQL 整合；多欄原子採用仍是下一切片的真 DB gate。

## 3. 下一個可執行切片

保持 T05 未完成。承接 T04 候選／快照公開介面，建立唯一 schema、角色工具與按需投影；先用原操作重入／title 重用、跨層拒絕及多欄後段 hunk 失敗作真 PG 反例。薄工具不複製資料 owner、版本或原操作結果。工具成功必須返回真實採用位置與差異，不能把請求 echo 成效果。

本輪不呼叫付費模型、不讀密鑰／原始員工資料；無 provider strict／真模型品質證據。後續接線須依 T06／T16 有界 preflight 與 T17 品質 gate，不能用離線通過替代。
