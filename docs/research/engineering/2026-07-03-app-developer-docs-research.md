# 研究紀錄:per-app 開發者文檔怎麼寫(README 補齊前的寫法研究)

- **日期**:2026-07-03
- **狀態**:研究完成,依此撰寫三個 app 的 README
- **動機**:維護者要求「讓別人不用把代碼全看完,就清楚知道這代碼在做什麼、怎麼流動」的
  開發者導向文檔(含流程與細節),範圍 `apps/api`、`apps/web`、`apps/ocs-indexer`。
  現況:web README 仍是 create-next-app 樣板(零資訊);indexer README 結構好但**大量過時**
  (v3 payload、in-process BGE-M3、`jobintel-ai` 舊名);api README 簡潔但缺端點面與流程。

## 1. 來源(全部權威;類別標註)

| 來源 | 類別 | 要點 |
|---|---|---|
| matklad(Aleksey Kladov,rust-analyzer 作者)〈ARCHITECTURE.md〉2021 | 概念原始出處 | bird's-eye + **codemap**(「一張國家地圖,不是各州地圖集」)+ **不變量**(invariants,「常是『沒有什麼』,從代碼裡讀不出來」)+ 層邊界;避免連到具體檔案行號(會爛)、避免實作細節(留給行內註解)、要短(「每個常貢獻者都得讀」);10k–200k LOC 專案效益最大;名句:不熟專案寫 patch 慢 2x,但**找到該改哪裡慢 10x** |
| Diátaxis(Daniele Procida)diataxis.fr | 官方框架(Gatsby/Cloudflare/Vonage 採用) | 四型分開:tutorial(學)/how-to(做)/reference(查)/explanation(懂);混在一起是文檔失敗主因 |
| arc42(Starke & Hruschka)arc42.org | 範本官方 | **Building Block View**(靜態分解)+ **Runtime View**(用場景寫關鍵流程:重要 use case、關鍵外部介面互動、錯誤/例外行為)+ Crosscutting Concepts(跨模組原則);務實裁剪、不照單全收 |
| Google styleguide docguide | 大廠實務 | **每目錄一個 README** 導引;minimum viable docs(「盆栽:活著但常修剪」);**docs 跟 code 同一個變更一起改**;壞文檔比沒文檔糟,定期刪死文檔;**連結既有文檔,不要複製**(避免雙份漂移) |

## 2. 共識(四層互證)

1. **README = 該目錄的地圖**(Google)= codemap + 鳥瞰(matklad)。回答「功能住在哪、每塊是幹嘛的」,
   不逐檔案講實作。
2. **流程用「runtime 場景」寫**(arc42 Runtime View):挑**少數關鍵 use case**,一步步走資料怎麼流
   (含錯誤/降級行為),而不是列 API 清單就完事。維護者要的「流程」正是這個。
3. **把「不變量/邊界」白紙黑字寫出來**(matklad):像「document cache 就是編輯器狀態」「embed 字串
   不回存 payload」這種*不存在於任何單一檔案*的規則,是新人最難從代碼推出的東西。
4. **Reference(端點表/schema 指針)與 explanation(為什麼)分開**(Diátaxis):端點表列面,
   「為什麼」連去 ADR/spec,**不複製內容**(Google:link, don't duplicate)。
5. **短、活、跟碼走**(matklad + Google):過時段落直接刪;避免行號連結;結構性改動時同 commit 更新。

## 3. 套用到本 repo 的模板(三個 README 共用骨架)

```
# <app> — 一句話定位(bounded context + 對誰服務)
跑 / 測試(how-to,最少可用)
Codemap(表格:路徑 → 是什麼,一層深即可)
資料層 / 資料模型(該 app 的核心狀態:誰擁有、形狀、生命週期)
關鍵流程(arc42 runtime view:3–6 條,含降級/衝突等錯誤路徑)
不變量(matklad invariants:跨檔案規則,條列)
介面 reference(端點/консumer 表;權威 schema 連到 contract 套件/ADR)
指路(ADR / specs 連結,不複製內容)
```

- 語言:繁中(對齊 repo 慣例);表格優先;每 README 目標 100–200 行。
- 與 `ARCHITECTURE.md` 分工:root 檔管跨 app 鳥瞰(不常變),per-app README 管該 app 內部
  地圖與流程;`docs/adr` 管為什麼。互連不互抄。

## 4. 本次直接修正的過時點(Google:刪死文檔)

- `apps/web/README.md`:整檔是 create-next-app 樣板 → 全重寫。
- `apps/ocs-indexer/README.md`:`ocs_v3` → `ocs_v4`;in-process BGE-M3 / `BGE_M3_*` env →
  embedder 服務(`EMBEDDER_URL`,ADR 0012);`jobintel-ai` → `apps/api`(Caliburn);
  v3 payload 欄位(`unit_id/task_id/k_pairs…`)→ v4(`ocu_code/task_code/competency_blocks`);
  模組表 `embeddings/bge_m3.py` → `http_embedder.py`/`factory.py`(+ 補 `api/urn.py`);
  移除 `docs/superpowers/`(不存在)與 `../jd-pdf-to-json` 舊路徑。
- `apps/api/README.md`:補端點 reference 面(critical/enrichment 標註,ADR 0018)、
  文件 of-record 生命週期與 AI 提議降級鏈等 runtime 流程、資料模型三表。
