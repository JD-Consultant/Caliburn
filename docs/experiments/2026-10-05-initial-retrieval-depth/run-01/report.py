"""Report depth retention and clearly separate old N20 rerank diagnostics."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parents[1] / "2026-10-05-memory-public-unit-retrieval/run-01"
UNION = HERE.parents[1] / "2026-10-05-rerank-union-candidate-replay/run-01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name, text):
    with (HERE / name).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text + "\n")


def dump(name, value):
    write(name, json.dumps(value, ensure_ascii=False, indent=2))


def main():
    results = read(HERE / "results.json")
    indexed = {(r["case_id"], r["variant"], r["depth_each_route"]): r for r in results}
    targets = read(HERE / "targets.json")
    cases = read(PRIOR / "cases.json")
    summaries = read(HERE / "summary.json")
    previous_r = {(r["case_id"], r["method"]): r for r in read(UNION / "results.json")}
    stage = []
    for case in cases:
        own = [t for t in targets if t["case_id"] == case["case_id"]]
        for variant in ("O", "B2"):
            initial = indexed[(case["case_id"], variant, 20)]
            prior_r = previous_r[(case["case_id"], variant + "-U-R")]
            rank_lookup = {p["id"]: rank for rank, p in enumerate(prior_r["merged_ranking"], 1)}
            candidate_ids = set(initial["employee_candidate_ids"])
            assert candidate_ids == set(rank_lookup)
            rows = [{"id": t["id"], "title": t["title"], "main_work": t["main_work"],
                     "initial_N20_recalled": t["id"] in candidate_ids,
                     "prior_U_R_rank": rank_lookup.get(t["id"]),
                     "prior_U_R_final_K5_retained": rank_lookup.get(t["id"], 9999) <= 5,
                     "sensitivity_excluded": t["sensitivity_excluded"]} for t in own]
            supported = {f for t in rows if t["prior_U_R_final_K5_retained"] for f in t["main_work"]}
            clear_supported = {f for t in rows if t["prior_U_R_final_K5_retained"] and not t["sensitivity_excluded"] for f in t["main_work"]}
            stage.append({"case_id": case["case_id"], "variant": variant, "depth": 20,
                          "targets": rows, "prior_U_R_known_facets_retained": sorted(supported),
                          "prior_U_R_clear_facets_retained": sorted(clear_supported),
                          "scope": "existing N20 rerank diagnostics only; no N40/N80 rerank result"})
    dump("stage-diagnosis.json", stage)
    table = ["| 輸入 | 每路Top N | 已知3分代表保留 | 已知工作面向支持 | 排除疑義後代表 | rerank配對量 |", "|---|---:|---:|---:|---:|---:|"]
    for s in summaries:
        refs, facets, clear = s["known_grade3"], s["known_work_facets"], s["clear_grade3_sensitivity"]
        table.append(f'| {"原話" if s["variant"] == "O" else "B2"} | {s["depth_each_route"]} | {refs["retained"]}/{refs["known"]} | {facets["retained"]}/{facets["known"]} | {clear["retained"]}/{clear["known"]} | {s["rerank_pair_workload"]} |')
    intro = """# 初搜Top20／40／80比較

2026-10-05，隔離研究，固定八案及已封存完整exact排名。**原話雙路N20已保留全部12個已知主要代表、8個已知工作面向；B2的N20漏全端後端參考，N40找回。** 增至N80沒有增加這份固定清單的命中，不代表沒有其他未評相關公版。

## 固定清單與方法

前輪158個已評員工×公版中，12個grade3作固定主要代表清單；其中多媒體／資材兩個沿語意疑義，排除敏感度另外呈現，原分不改。代表支持的main_work沿原判讀，對上固定員工major_work_facets，重複面向只記一次。7案有已判3支持、共8個面向；**H01課程行政第8案的1個面向尚無grade3支持，涵蓋無法判定，不納入8個已知面向的分母。** 12/12是已知來源回歸，不是所有工作或全庫Recall。

輸入O原話整段8query、B2逐理解12query；D整份／T任務各805父排名沿同BGE-M3 1024 dense、真Qdrant exact已核結果。每query各取N父而非N個chunk，D/T完整union去重，不先RRF截。員工候選可跨多公版，最後五份仍是後續rerank額度。本輪只驗初搜prefix，沒有新DB／GPU／embedding／Memory／LLM推論。

## 結果
"""
    ending = """
12來源與8面向是不同分母，不加總／平均0–3分。排除兩個疑義來源後結果一致：原話N20起10/10，B2N20 9/10、N40起10/10。

- **原話：**N20→40→80沒有增加已知代表／面向，配對量247→480→926；每位各一query，所以員工候選父數與配對數相同。
- **B2：**N20唯一漏F01網站系統設計人員（D24、T41），也漏其已判支持的後端面向；N40由D路找回。配對量381→748→1438；多query的員工去重候選總數324→628→1166，不能把兩種數量混用。
- **最小N診斷：**這批已知清單的最小每路深度原話15／B2 24；固定比較仍是20／40／80，沒有事後新增N15／24方法或把它選成通用參數。
- **課程行政：**沒有已判3參考，三個深度都無法判定；不能因unknown說已完整或全庫無資料。

## 初搜與重排損失

額外讀取既有N20完整聯集U-R，沿同模型分數與既有判讀作階段診斷，沒有N40／80新rerank。原話初搜12個已知3進池，U-R前五留9個；其原模型支持8個面向，排除多媒體疑義後只7個。B2初搜11個已知3，U-R前五留5個、支持4個面向；排除多媒體後3個。來源可重疊支持同面向，不能以來源少了就直接推工作缺漏，也不能信任疑義來源宣稱已完整。

冷氣B2的冷凍空調技術人員在D28／T7，**初搜N20已由T召回**，既有U-R排17而未留前五。前端、採購等也有已進池後掉出的情況；這些應定位為排序／最終額度問題，不能一律歸因初搜深度不足。全端B2網站系統則是N20未召回、N40補進，兩種問題分開。每份階段去留見[診斷](stage-diagnosis.json)。

## 結論與未驗範圍

這批資料可先以**原話D20/T20完整聯集**保留初搜控制；B2若繼續作候選，至少比較D40/T40後的品質與時間。原話N40／80無已知回歸增益且候選更多，沒有證據要求一律用N80。這是有限初值，不是正式DB參數或所有真人訪談通用最佳；原話／B2長度與query數不同，不是等成本純改寫比較。

下一瓶頸是rerank是否能按主要職位代表性保留候選；本輪沒有證明新N40／80 rerank品質或省時。工作量是未來逐query×公版配對數，不是fresh時間；新N40缺600個既有rerank score、N80缺1736個，清單另存，並未計算或外送。

40個805父rank由177460個已存chunk cosine重聚，48組prefix／union／facet／敏感度／診斷與20個N20控制經[獨立驗證](verification.json)，581個兩輪seal不變；7負向／邊界測試Red→Green。沒有新外部費用或服務，完整排名／文字沿來源hash固定。既有模型判讀、引句修正／JSON欄位順序、少量Memory忠實度疑義仍在，沒有新人工語意验收、全805qrels、真人、新holdout、ANN、fresh延遲或JD完整度。

原件：[協定](protocol.md)、[事前計畫](../../../plans/2026-10-05-initial-retrieval-depth.md)、[固定標註](targets.json)、[所有候選](results.json)、[每代表每query名次](target-ranks.json)、[最小N診斷](minimum-depth.json)、[六组摘要](summary.json)、[缺rerank cache](missing-rerank-cache-pairs.json)、[來源hash](input-manifest.json)、[進度](progress.md)、[最後審查](review.md)、[封存](artifact-hashes.json)。
"""
    write("README.md", intro + "\n" + "\n".join(table) + "\n" + ending.replace("验收", "驗收").replace("六组", "六組"))
    lines = ["# 初搜48組逐案候選與保留", "", "只查固定已評清單，未知不是負例；原0–3不加總。完整候選ID／cosine與query邊見results.json。"]
    names = {t["id"]: t["title"] for t in targets}
    for r in results:
        state, facets = r["known_grade3"], r["known_work_facets"]
        lines += ["", f'## {r["case_id"]}／{r["variant"]}／每路N{r["depth_each_route"]}', "",
                  f'query數{len(r["query_ids"])}；員工去重候選{r["employee_unique_parents"]}；逐query配對{r["rerank_pair_workload"]}。', "",
                  "已知代表保留：" + ("、".join(names[ident] + "（" + ident + "）" for ident in state["retained_ids"]) or "無"),
                  "已知代表缺漏：" + ("、".join(names[ident] + "（" + ident + "）" for ident in state["missing_ids"]) or "無"),
                  "已有評分支持的面向：" + json.dumps(facets["retained"], ensure_ascii=False),
                  "已有評分但未召回的面向：" + json.dumps(facets["missing"], ensure_ascii=False),
                  "尚無已判3支持的面向：" + json.dumps(facets["unassessed"], ensure_ascii=False),
                  "敏感度排除兩疑義來源：" + json.dumps(r["clear_grade3_sensitivity"], ensure_ascii=False)]
    write("report.md", "\n".join(lines))
    print("README, 48-group report and existing-N20 stage diagnostic saved")


if __name__ == "__main__":
    main()
