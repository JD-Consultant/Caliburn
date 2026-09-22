# ADR 0011 — 契約 #3(api⇄web 著作文件 Part A):web 改吃 ocs-contract 生成的 TS 型別

- **狀態**:Accepted（2026-06-28;契約 #3 Part A)。

## 脈絡

著作文件(顧問產出的 OCS 文件)沿 api⇄web 流動;web 在 `apps/web/src/types/index.ts` **手寫整份 OCS 文件型別**(`OcsDocument`/`OcsProfile`/`OcuUnit`/`OcsTask`/`CompetencyBlock`/`CodeName`/`Indicator`…)= 手抄 `ocs-contract` 的 schema,外加前端專屬欄位(`_id/_uid/_tid/_notes`…)。`@caliburn/ocs-contract` 有 schema SSOT(`ocs-document.schema.json`)+ Python codegen,但**沒有 TS 生成、web 什麼都沒 import** → 文件形狀手抄兩份,schema 一改(新區塊/改名欄)web 靜默飄移。

依 `docs/contract-strategy.md` 判準:文件是**領域文件 + 有非 Python(TS)消費者** ⇒ 第 2 列 = **JSON-Schema SSOT + codegen**。研究紀錄:`docs/specs/2026-06-28-contract-3-api-web-document-research.md`。

## 決定

**Part A(本 ADR)**:給 `@caliburn/ocs-contract` 加 **`json-schema-to-typescript`** 目標 → `types/ocs-document.ts`(`OCSDocument` + 巢狀);web 以 **workspace 依賴 + type-only import** 消費,刪掉手抄鏡像,改用**從生成基底衍生**的型別:`Omit<Gen, …> & { …re-tighten… } & { UI 欄位 }`。契約型別保持純淨(無 `_` 欄);UI 增補只在 web。

- **封閉 TS**:schema 的 `additionalProperties:true` 會讓 json2ts 產 `[k:string]:unknown` 索引簽章 —— 那會使 `Omit/keyof` 把明確欄位塌成 `unknown`(破壞 typed 消費者)。故 codegen 後以 `scripts/strip-index-sig.mjs` 去除索引簽章,產**封閉**契約型別;**schema 本身仍寬鬆**(供 Python/wire 容忍演進)。
- **守門**:`check-codegen.sh` 現同時守 Python 與 TS(regen + `git diff`)。
- **安全網**:web 無自動測試 → `tsc --noEmit` + `eslint` 為閘門 + **人工瀏覽器煙測**(文件工作台載入/編輯 O/P/K/S/表頭/finalize/export,主控台無紅字)已通過後才發 tag。

**為何只做 Part A**:api⇄web 的 **REST 信封**(`DocumentEnvelope`/`HeaderMeta`/AI 結果…)目前多由回 raw dict 的端點供給,OpenAPI 不完整 → 要先補 api 的 `response_model` 才能 `openapi-typescript` 生成。信封薄、api 自有、飄移風險低 → **延後為 Part B**(另開,走 OpenAPI-first)。

## 後果

- ✅ 文件形狀跨語言單一來源:web 型別衍生自生成契約,schema 一改即由 `tsc` 逼出 web 不符處。
- ✅ `check-codegen` 同守 Python + TS;UI 欄位與契約清楚分離。
- ✅ 行為不變(型別在編譯期抹除):瀏覽器煙測通過。
- ⚠️ 生成 TS 為封閉型別(去索引簽章);若未來要在 TS 端容忍未知欄位,於消費點自行放寬。
- 📌 tag `contract3-doc-types`。

## 已知後續(範圍外)
**Part B**:補 api 各路由 `response_model` → 匯出 `openapi.json` → web 以 `openapi-typescript` 生成信封/AI 型別、退役手寫信封(另開 ADR)。
