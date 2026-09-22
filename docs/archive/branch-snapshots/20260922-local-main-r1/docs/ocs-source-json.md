# OCS 來源 JSON 契約 — 取用注意事項

> 這份講的是 OCS(職能基準)**來源**標準:PDF →(`apps/pdf-to-json`)→ 結構化 JSON,被 `apps/ocs-indexer` 索引、被 `apps/api` 查詢取用。
> 跟 [`ocs-schema.md`](ocs-schema.md) 不同 —— 那份是**著作產出文件**(`build_doc` 的輸出 / `packages/ocs-contract`);這份是**上游來源**。
> 相關:[`service-split-framework.md`](service-split-framework.md)。

## 權威契約 = `apps/pdf-to-json/README.md`

動 indexer 欄位投影 / Qdrant payload / 任何 OCS 契約解讀**之前,先讀 `apps/pdf-to-json/README.md`(尤其 §6.3 `ocs_content`)**。比臆測欄名、或只看單一 json 檔可靠。

## 鐵則:先看真實 JSON 確認「基數」,別憑欄名臆測

碰 OCS 來源欄位前,**先開一兩個真實檔**(`apps/ocs-indexer/data/jd-json/*.json`)看結構,確認每個欄位是**多值清單**還是**單值**。

- `category` 三組 —— `job_categories` / `occupations` / `industries` —— **都是多值** `[{code, name}]`(分類用)。
- `ocs_name.{job_category_name, occupation_name}` —— **單值**(職能基準名稱,擇一,幾乎都是 occupation;`job_category_name` 常為 null,標題用)。兩者**無關、別混**。

> **踩過的坑**:曾把多值的 `category.job_categories`(如 AIoT = MPM/INM/ISD/SET)誤當單值,又跟單值的 `ocs_name.job_category_name` 混為一談,連帶 normalizer 只抓了 code、丟了 name。修法:normalizer 用「**鎖步收集 code+name、依 `code|name` 去重**」確保平行陣列對齊。

## §6.3 關鍵條款(摘要;權威以 README 為準)

- **一個 `tasks[]` 條目 = 「PDF 同表格中共用同一組 `competency_blocks` 的工作任務群」**,是原子單位。`task_codes[]` **通常長度 1**;「同格多 T code」時 >1,**且這些任務共用同一組 O/P/K/S**(不可過度歸因到單一 task)。實測 908 檔:約 99.4% 單值、0.6%(半導體全系列 / 工業設計師 / 工具機… 等真實職業)多值。
- **`competency_block` 由「K/S 是否出現新值」分界**(新 O-code 或 `competency_level` 改變,且同列有 K/S 才算新 block)。多 level 任務才有多 block;實測約 96.5% 單 block。
- **術語**:K 知識 / S 技能 / A 態度(全域)/ O 工作產出(可空、可跨 block 共用)/ P 行為指標(每 block 必 ≥1)/ T 任務或職責代碼。

## indexer 取用現況(歷史觀察,請對照現行 `apps/ocs-indexer` normalizer 確認)

> 以下為 2026-06 的觀察,**會隨程式碼演進**,引用前請對照現行碼:

- 索引時 indicators(P)被丟掉(payload 無);`activity_examples` 其實是 P text 的截斷衍生。
- K/S 的 code 是**OCS 本地**編號(會跨不同 OCS 撞名),不是全域唯一鍵。
