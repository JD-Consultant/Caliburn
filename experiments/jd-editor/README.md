# JD editor — 隔離 Task 1

本工作區只提供 v2 JSON Schema 生成契約與官方 Plate 原生編輯核心；不加入 production monorepo，不讀 DB／Memory／API key，也不呼叫模型。正式 authority 仍由 root ADR／current register 管理。實作範圍依 `docs/plans/2026-09-10-jd-editor-core-implementation.md` Task 1。

在本目錄執行：

```text
npm ci --ignore-scripts
npm run codegen -w @caliburn/jd-editor-contract
npm run check-codegen -w @caliburn/jd-editor-contract
npm run build -w @caliburn/jd-editor-native
npm run test -w @caliburn/jd-editor-native
cd contract
uv run pytest -q tests/test_schema_contract.py
```

固定 Node 22.12.0、Plate 53.3.11、basic/list 53.0.0、table 53.0.9、diff 53.0.0、React 19.2.4；完整版本見独立 package-lock.json。官方 F02 lock 的全部 48 個 runtime 套件版本一致。npm 10.9 的 optional-peer 解析遇到 `edgesOut` 失敗，`.npmrc` 固定 legacy-peer-deps；實裝 `npm ls --all` 無缺少／不符 peer。安裝一律停用 scripts；不更新 root production lock。

## 契約

`docs/specs/contracts/jd-editor-v2.schema.json` 是唯一手改 SSOT。contract/generated、types、src/jd_editor_contract/models.py 全由固定工具生成；check-codegen 在暫存目錄生成後逐 byte 比對，不重寫已保存產物。生成器 Python 預設 PEP604 對遞迴 JsonValue RootModel 產出不能 import 的 forward-ref，已使用官方 `--no-use-union-operator` 選項修復，未手改 DTO。

DTO 不完整表達 JSON Schema 的 allOf／not／if／then；JS/Python 仍須先用原 schema 驗證。TS set_properties 分支由已驗證的 schema 輸入經有限 command-mapper 收斂內部型別，不能單靠 TS/Pydantic 接受判定 wire 合法。Python 同版關係與 source scope 在後續 App seam 接線，本切片 Node 已驗完整 candidate 的 ID／K／S 關係。

## 原生核心

profile／react-profile 分別接官方 headless／React plugins；semantic containers 只有 isElement，不加內容 normalizer。createJdEditor 先驗保存值，使用 clone、官方 NodeId reuseId:true／initialValueIds:always；normalization 真 operations 由同步 onChange 捕捉。transform 僅七個固定 command；整批 disposable editor，失敗不回部分 value，不聲稱框架 rollback。

固定 `native/dist/bridge.js transform|validate-value|read-selection` 只讀 stdin JSON、回一份 stdout JSON。程式碼／路徑不接受模型參數。選取用原生 range、NodeApi、fragment；只回已解析文字 block 的原生 fragment，避免 partial ancestors 被誤當完整 Task。read-selection 遇 canonical normalization 改動直接拒絕。

人工同文件 copy 的本地 helper 使用 native insert 生成全部新 ID，再只對複本內已複製端點做有限 ID 映射；它不是第八個模型工具／bridge entry。應只在 disposable candidate editor 使用，最終整份 validation 後才能保存。跨文件 source scope 不在此 helper 處理。

`affected_element_ids` 從真實 native apply 當時的樹與 operations 收集：文字／mark／props 包含實際節點及必要父容器，結構操作包含插入／移除／移動內容，並涵蓋 normalization／NodeId 新生成 ID；不列無關 siblings。整批前後全文相等時回空列表，仍保留真 operations。它是實際操作涉及內容的有限索引，完整 before/after 仍是完整回查材料，不能用此列表取代正文或官方 computeDiff。

## fixtures 與證據

r2-canonical 直接複製 active F03 v2，190 Element、8 Task 各兩組、5 K／5 S、1基本資料表；expected-task8-move 是固定 Task8-only oracle。fixture-mapping 保留38個退役外框ID；不改 v1。source-map 由測試 fixture issuer 建立8個合成 handle，Node不替來源owner授權；Task3再接實際來源。新增關係是合成測試配置，不是已確認工作事實。

license-inventory.json 和 licenses 保存安裝 metadata／授權，diff 的原衍生碼為 Apache-2.0，修改部分 Apache-2.0／MIT 雙授權，不能全部稱 MIT。2個 tooling 套件只有 package MIT declaration（inventory明列），其餘授權文字封存。依主線核准的有限安全修補，Vitest已由4.1.9固定升至4.1.11，修復官方GHSA-82fw-gwwq-j7x9；npm-audit.json重新核對為0 vulnerabilities，48個F02 runtime版本不變。

未驗：DOM／IME／clipboard／完整 UI、SQL 保存、取消與對帳、自然模型選工具與 JD 品質、真人使用。這些仍在後續切片與預算 gate；本切片0付費請求。
