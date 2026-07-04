"""相似比對服務(ADR 0022):items:match 的管線編排。

不碰 Qdrant——唯一 I/O 是 embedder(③)。切成三段讓校準腳本共用同一套碼
(collapse / score_pairs / match_items),校準紀錄的可信度靠「校準即生產」保證。
純函式規則、門檻、星型分群在 [core.py](core.py)。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from jd_ocs_indexer.api.schemas import (
    GroupMember,
    MatchConfig,
    MatchGroup,
    MatchItem,
    MatchResponse,
    PossibleMatch,
)
from jd_ocs_indexer.matching import core


@dataclass
class CollapsedPool:
    """①② 之後的池:reps 照池序;exact_dups[rep_id] = 其餘同字 id。"""
    ids: list[str] = field(default_factory=list)        # rep id(池序)
    texts: list[str] = field(default_factory=list)      # rep 清洗後文字(嵌入輸入)
    sources: dict[str, set[str]] = field(default_factory=dict)   # rep id -> 來源聯集
    exact_dups: dict[str, list[str]] = field(default_factory=dict)


def collapse(items: list[MatchItem]) -> CollapsedPool:
    """① 清洗(空文字丟)+ ② NFKC key 同字收斂(rep = 池序第一個)。"""
    pool = CollapsedPool()
    rep_of_key: dict[str, str] = {}
    key_of_rep: dict[str, str] = {}
    for it in items:
        text = core.preprocess(it.text)
        if not text:
            continue
        k = core.collapse_key(text)
        rep = rep_of_key.get(k)
        if rep is None:
            rep_of_key[k], key_of_rep[it.id] = it.id, k
            pool.ids.append(it.id)
            pool.texts.append(text)
            pool.sources[it.id] = set(it.sources)
            pool.exact_dups[it.id] = []
        else:
            pool.exact_dups[rep].append(it.id)
            pool.sources[rep] |= set(it.sources)
    return pool


def score_pairs(pool: CollapsedPool, vectors: list[list[float]]) -> dict[frozenset, float]:
    """④ 跨來源兩兩 cosine(來源有交集 → 同基準刻意分開,不比)。"""
    scores: dict[frozenset, float] = {}
    n = len(pool.ids)
    for x in range(n):
        for y in range(x + 1, n):
            i, j = pool.ids[x], pool.ids[y]
            if pool.sources[i] & pool.sources[j]:
                continue
            scores[frozenset((i, j))] = core.cosine(vectors[x], vectors[y])
    return scores


def match_items(embedder, *, kind: str, items: list[MatchItem]) -> MatchResponse:
    """相似比對(ADR 0022):①清洗 ②NFKC 同字收斂 ③嵌入(唯一 I/O)④跨來源兩兩
    cosine ⑤FS 分帶 ⑥星型分群+medoid。"""
    th_hi, th_lo = core.THRESHOLDS[kind]
    cfg = MatchConfig(kind=kind, theta_high=th_hi, theta_low=th_lo,
                      model=getattr(embedder, "provider", "bge-m3"))

    pool = collapse(items)
    scores: dict[frozenset, float] = {}
    if len(pool.ids) >= 2:
        vectors = [v.dense for v in embedder.embed_texts(pool.texts)]   # ③ 一批嵌入
        scores = score_pairs(pool, vectors)

    def score_of(i, j):
        return scores.get(frozenset((i, j)))

    # ⑤⑥ 分帶 → 星型 → medoid
    pairs = [(s, *sorted(p)) for p, s in scores.items()]
    dup, gray = core.band(pairs, th_hi, th_lo)
    clusters = core.star_clusters(dup, score_of, th_hi)

    # 組回應:exact dup(score 1.0)併入所屬群;純 exact 群(未進嵌入群)單獨成群
    groups: list[MatchGroup] = []
    clustered_reps: set[str] = set()
    for center, mems in clusters:
        all_ids = [center, *mems.keys()]
        clustered_reps.update(all_ids)
        member_rows = [GroupMember(id=center, score=1.0)]
        member_rows += [GroupMember(id=m, score=round(s, 4)) for m, s in sorted(mems.items())]
        for rep in all_ids:
            member_rows += [GroupMember(id=d, score=1.0) for d in pool.exact_dups.get(rep, [])]
        groups.append(MatchGroup(medoid=core.medoid_of(all_ids, score_of), members=member_rows))
    for rep, dups in pool.exact_dups.items():
        if dups and rep not in clustered_reps:
            groups.append(MatchGroup(medoid=rep, members=[
                GroupMember(id=rep, score=1.0),
                *[GroupMember(id=d, score=1.0) for d in dups]]))
    groups.sort(key=lambda g: g.medoid)

    matches = [PossibleMatch(left_id=i, right_id=j, score=round(s, 4)) for s, i, j in gray]
    matches.sort(key=lambda m: (-m.score, m.left_id, m.right_id))
    return MatchResponse(groups=groups, possible_matches=matches, config=cfg)
