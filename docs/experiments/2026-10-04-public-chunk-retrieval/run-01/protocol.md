# 公版切塊比較的事前協定

2026-10-04。隔離研究，使用者同意前述chunk比較，未授權改正式App。固定同805来源、BGE-M3 revision 5617a9f61b028005a4858fdac845db406aefb181、FP16／1024維／8192 tokens、Qdrant1.18.2 exact cosine。沿用既有合成資料外送授權；新評審最多US$1／100 Responses／每次4096 output tokens／SDK retries0／批次30分鐘。沒有新增訪談或真人資料。

## 固定資料與表示

八案為前輪F01–F05原始需求（前後端、前端、帳務、冷氣、視覺），及H01–H03完整A訪談（課程行政、倉庫、採購）。只取原有whole查詢及既有向量，hash核相同文字；評分看同員工完整事實。不同来源分開呈現，不算前後改善率。

D：原整份概述及T/O/P正文，805 points不改。T：每個JSON task node一個chunk，包含所屬工作單元名稱、task_codes中的名稱、outputs名稱、indicators正文；同節點多個任務碼保留定位而不複製成多份chunk。U：每個JSON工作單元一個chunk，單元名稱及底下全部任務T/O/P。空正文節點保存排除原因，不偽造文字。

T/U各另外保存每公版的非空job_description作獨立overview chunk，避免切任務同時捨棄概述；不把整段職能概述複製到每任務。不新增LLM摘要或自由分群。所有文字沿原clean_text規則，精確項目字串去重，公版職位名不額外加入、OPKS代碼與表頭不進向量，K/S不加。若原正文自然含職位名稱，不作全文關鍵詞刪除。每份公版的D正文非空行須在T及U的chunk聯集中找到。

父公版代碼、職稱、來源path/hash、unit/task節點序號、所有任務码為定位metadata，非embedding輸入。相同文字可重用同一向量，但不同父／節點的point仍保留不同身份。超8192tokens停止該表示，不能靜默截斷或事後改切法。

## 候選與合併

每案一個固定whole查詢。原生group_by parent_id、group_size3、limit20，按最高chunk分數取得20個不同父公版；每個父最多3個最高chunk。這沿Qdrant官方分組契約，另與全chunk離線exact分數核對。

D-max：原805整份正文，同候選20／最終5。
T-max／U-max：父分數取最高chunk cosine。
T-mean3／U-mean3：**只重排相同max初搜20份父公版**，取其最高min(3,該父chunk數)個cosine算術平均，不補零、不按命中數加分。這不是全805父公版的mean3排名，也未保證3個chunk覆蓋不同工作。每個方法父公版去重K5，同分依父ID；不設相似度門檻。前三均值仍可能受到chunk數及長度影響，作候選合併控制而非已驗收契約。

不加rerank、不變員工分段、不改模型／語料版本。保存所有chunk分數、各父前三、20候選與前五，能回查命中正文。前三均值不是評審分數平均；0–3代表性評分依舊逐份列出。

## 評分與成本

唯一員工×完整公版的評分，公版正文仍用D，不能只給命中chunk後改變評判对象。已有82 pair依employee與D hash核對重用分析版分級，原引用修正沿原reconciliation，不重評來選贏家。新pair依F/H对应原Prompt、schema與input格式盲評；隱藏方法、名次、sourceID／職稱／cosine，grade來源及Prompt hash逐筆保存。未知／否定／他人工作不升格；原模型語意疑義保留，新增literal引用失敗保存為缺測，不偷偷改分。

直接Responses、gpt-6-luna/high、standard/default、storefalse/backgroundfalse、重試0、concurrency3，先count再預留、保存actualusage。新pair超100或費用上限則停止模型批次，報未評，不增加授權界線。

向量生成、首次載入／服務ready、建索引及查詢成本分開。各方法三次暖機真DB分組與App合併，使用cached query embedding；不是rerank測試或產品總延遲。T/U表示不同point數，805父數保持固定，不能把切細後points數稱為新增職位。

## 依據與邊界

[Qdrant官方grouping](https://qdrant.tech/documentation/search/search/)規定群組按最高point分數排序、group_size為best effort、group key支援keyword/integer並建議payload索引；本輪建parent keyword index，實測完整前三再核對，不能聲稱官方原生按mean3排序。[BGE官方](https://huggingface.co/BAAI/bge-m3)為1024維、8192tokens；版本及runtime須與已保存向量一致。

八既有小樣本／单模型評審、前五pool無全庫qrels。不宣稱切塊必然更好、召回全庫、後端不存在、正式門檻、真人或Memory可用、JD/PDF完成。結果可支持下一個有限實驗；正式採用需更可靠評分與留出資料。
