"""Render the observed replay without changing scores or judgments."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parents[1] / "2026-10-05-memory-public-unit-retrieval/run-01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name, text):
    with (HERE / name).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text + "\n")


def main():
    rows = read(HERE / "results.json")
    new = {(r["case_id"], r["method"]): r for r in rows}
    old = {(r["case_id"], r["method"]): r for r in read(PRIOR / "graded-results.json")}
    cases = read(PRIOR / "cases.json")
    summaries = []
    table = ["| 案例 | 原話M-R | 原話U-R | B2 M-R | B2 U-R |", "|---|---|---|---|---|"]
    def strong(row):
        found = [f'{p["name"]}第{p["rank"]}' for p in row["selected"] if p["judgment"] and p["judgment"]["grade"] == 3]
        return "、".join(found) if found else "無"
    for case in cases:
        ident = case["case_id"]
        values = [strong(old[(ident, "O-M-R")]), strong(new[(ident, "O-U-R")]),
                  strong(old[(ident, "B2-M-R")]), strong(new[(ident, "B2-U-R")])]
        table.append("| " + " | ".join([ident] + values) + " |")
        summaries.append({"case_id": ident, "old_O_M_R": values[0], "new_O_U_R": values[1],
                          "old_B2_M_R": values[2], "new_B2_U_R": values[3]})
    write("representatives.json", json.dumps(summaries, ensure_ascii=False, indent=2))
    introduction = """# 聯集保留至rerank：候選截斷重播

2026-10-05，隔離研究。**移除rerank前的聯集截斷，找回全端共同參考，但沒有通用改善。** 本輪是相同已觀察案例／固定模型品質分數的cached replay，沒有新GPU／DB／LLM推論、外送或费用，不是新holdout、正式接線或JD完成判定。

## rerank如何用

同一員工query分別搜D整份／T任務chunk各20個父公版；U保留完整去重聯集，每query26–35份。將query與每份候選的**完整公版正文**配對，用本機固定BGE-reranker-v2-m3得到logit，再排序。單query保留此排序；B2多query各自rerank後，以完整池RRF k2融合，最後最多五份公版。公版職稱與OPKS代碼／表頭仍不額外當搜尋正文。

官方契約是query／passage共同輸入、輸出相關性分數；分數越高越相關，也可sigmoid映射0–1。[BAAI官方模型卡](https://huggingface.co/BAAI/bge-reranker-v2-m3)。本輪沿原logit排序，没有把分數當經校準的職位機率或套門檻。0–3代表性分數是另一個盲評模型的判讀，不是reranker logit。

本輪將已封存的同query×同完整公版logit重用，逐一核query／正文SHA與來源revision／FP16設定。rerank配對對其他同批候選不互相競賽，故同一已觀察分數可用於不同候選池的排序重播；不因此宣稱新推論穩定性。

## 結果

- **全端原話：**舊M-R前五無3，新U-R將「網站系統設計人員」排第1／3分，支持前後端。原D名次40／T15，D20/T20聯集34份，舊M融合第25被截；U保留到rerank找回。新U的前五與既有O-T-R相同，不能說比任務單路更好。
- **B2全端：**前五仍以前端第1／3分，網站系統公版不在兩路N20，保留聯集無法補未進候選的來源。
- **前端／帳務／倉庫／採購：**原話主要強代表仍在，前端第1退到2；採購助理仍第2，但第3新增0分來源。B2帳務仍有會計助理2／會計5，第一名改成2分業務助理；倉庫理貨3退到4，採購仍無3。不能以全端一案稱所有案例更準。
- **視覺：**原話U-R新增多媒體第5／3分，但平面強代表仍未找回；多媒體判讀沿前輪疑義，不能把它當已人工確認改善。冷氣原話冷凍空調仍第4，B2無3；課程行政兩輸入仍無3。

只列既有模型3分與名次；無=這組前五無3，不是全庫無資料。不加總／平均。完整0–3／理由／字面證據見[逐案前五](report.md)、[結構化結果](results.json)。
"""
    ending = """
## 工作量與驗證

16組80位置、71唯一員工×公版，全部已有相同輸入的盲評可重用，0未評、0新增provider calls／外部費用。20query聯集共628個source-bound品質pair，舊M-R為400個，**配對數1.57倍**；不是實測時間增加57%，也沒有證明時間降低。原話／B2並未互相合併，兩路是D與T。

48個舊D／T／M-R控制的完整候選池／合併排名不變，551前輪seal檔hash不變；新26–35父聯集、628pair文字SHA／logit、16選擇／融合、71評分與來源引用經[獨立重算](verification.json)。六個截斷／去重／缺cache／改SHA／非有限分數測試Red→Green；不將排序完整性當語意真值。

重用仍帶前輪模型判讀、6引句明示抄錄修正與30舊A request JSON欄位順序不同的限制；原件不改。沒有新真人、全庫qrels／Recall、新holdout、Memory忠實度全量人工驗收、JD完整度、ANN或fresh延遲。實際工程時間需後續真GPU暖機與DB路徑測量，不能拿cached replay或歷史pair秒數加總當結果。

目前推薦保持原話／B2對照，先將完整聯集R當候選以避免早截；它的候選量增加且其他案例仍有錯排，不選正式通用方法／相似度線。候選深度、聯集後額度、R模型適配與fresh品質／時間取捨仍待有界比較。

原件：[事前協定](protocol.md)、[事前計畫](../../../plans/2026-10-05-rerank-union-candidate-replay.md)、[輸入hash](input-manifest.json)、[逐query聯集及分數](query-unions.json)、[M-R對照](comparison.json)、[配對工作量](workload.json)、[重用評分](reused-judgments.json)、[空的待評清單](new-judge-jobs.json)、[進度](progress.md)、[最後審查](review.md)、[封存SHA／bytes](artifact-hashes.json)。前輪[十二法原件](../../2026-10-05-memory-public-unit-retrieval/run-01/README.md)全部保留。
"""
    write("README.md", introduction.replace("费用", "費用").replace("没有", "沒有") + "\n" + "\n".join(table) + "\n" + ending)
    lines = ["# 聯集rerank逐案前五", "", "2026-10-05。相同已觀察品質logit与既有盲評重用，沒有新推論；每份0–3不加總。",
             "", "完整員工原文與公版正文沿[前輪seal](../../2026-10-05-memory-public-unit-retrieval/run-01/artifact-hashes.json)。"]
    for row in rows:
        lines += ["", f'## {row["case_id"]}／{row["method"]}', "", "query：" + "、".join(row["query_ids"])]
        for item in row["selected"]:
            judgment = item["judgment"]
            lines += ["", f'### 第{item["rank"]}：{item["name"]}（{item["id"]}）', "",
                      f'代表性分數：{judgment["grade"]}；既有評分重用。', "", judgment["reason"], "",
                      "主要工作面向：" + json.dumps(judgment["main_work"], ensure_ascii=False), "",
                      "限制：" + json.dumps(judgment["limitations"], ensure_ascii=False)]
            for evidence in judgment["evidence"]:
                lines += ["", "員工字面證據：" + evidence["employee_quote"], "公版字面證據：" + evidence["reference_quote"]]
    write("report.md", "\n".join(lines).replace("logit与", "logit與"))
    print("README, 80-position report and representatives saved")


if __name__ == "__main__":
    main()
