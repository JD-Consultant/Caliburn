"""items:match 端點測試 — 假 embedder 餵可控向量。spec §1/§2/§5(ADR 0022)。"""
import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jd_ocs_indexer.api.routes import router


class FakeEmbedder:
    provider = "bge-m3"

    def __init__(self, table):
        self._table = table          # text -> dense vector

    def embed_texts(self, texts):
        return [SimpleNamespace(dense=self._table[t]) for t in texts]


def _app(table):
    app = FastAPI()
    app.include_router(router)
    app.state.embedder = FakeEmbedder(table)
    app.state.embed_lock = threading.Lock()
    app.state.client = None          # match 不碰 Qdrant
    app.state.settings = SimpleNamespace(qdrant_collection="unused")
    return TestClient(app)


def _items(*rows):
    return [{"id": r[0], "text": r[0], "sources": list(r[1])} for r in rows]


def test_groups_and_gray_and_config():
    # 向量設計:「主動 積極」清洗後與「主動積極」同字 → exact-collapse 成群(不經分帶);
    # 主動積極–持續學習 cos≈0.72 → 灰區。皆跨來源。
    table = {"主動積極": [1.0, 0.0], "持續學習": [0.72, 0.6939]}
    c = _app(table)
    body = {"kind": "attitude", "items": _items(
        ("主動積極", ["OC1"]), ("主動 積極", ["OC2"]), ("持續學習", ["OC3"]))}
    r = c.post("/items:match", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["config"] == {"kind": "attitude", "theta_high": 0.9, "theta_low": 0.7, "model": "bge-m3"}
    [g] = data["groups"]
    ids = {m["id"] for m in g["members"]}
    assert ids == {"主動積極", "主動 積極"}
    assert all(m["score"] == 1.0 for m in g["members"])
    [p] = data["possible_matches"]
    assert p["left_id"] < p["right_id"] and 0.7 <= p["score"] < 0.9


def test_same_source_pairs_skipped():
    table = {"甲": [1.0, 0.0], "乙": [1.0, 0.0]}
    c = _app(table)
    r = c.post("/items:match", json={"kind": "task", "items": _items(("甲", ["OC1"]), ("乙", ["OC1"]))})
    assert r.status_code == 200
    assert r.json()["groups"] == [] and r.json()["possible_matches"] == []  # 同基準刻意分開,不比


def test_embedding_dup_group_has_center_and_score():
    # 跨來源近同字(嵌入層 ≥0.95):甲乙向量幾乎同向 → 進星型群
    table = {"協助供應商品質管理": [1.0, 0.0], "協助供應商完成品質管理": [0.999, 0.0447]}
    c = _app(table)
    r = c.post("/items:match", json={"kind": "task", "items": _items(
        ("協助供應商品質管理", ["OC1"]), ("協助供應商完成品質管理", ["OC2"]))})
    [g] = r.json()["groups"]
    scores = {m["id"]: m["score"] for m in g["members"]}
    assert scores["協助供應商品質管理"] == 1.0 or scores["協助供應商完成品質管理"] == 1.0  # 中心
    assert g["medoid"] in scores


def test_limits_and_unknown_kind_and_short_circuit():
    c = _app({})
    too_many = {"kind": "task", "items": [{"id": str(i), "text": str(i), "sources": []} for i in range(501)]}
    assert c.post("/items:match", json=too_many).status_code == 413
    assert c.post("/items:match", json={"kind": "nope", "items": []}).status_code == 422
    # id 唯一是管線前置條件(collapse/score 以 id 為鍵;撞號會靜默吃掉配對)
    dup_ids = {"kind": "task", "items": _items(("同id", ["OC1"]), ("同id", ["OC2"]))}
    r = c.post("/items:match", json=dup_ids)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "duplicate_item_ids"
    # <2 條:短路回空,不打 embedder(FakeEmbedder 空表也不會炸)
    ok = c.post("/items:match", json={"kind": "task", "items": _items(("唯一", ["OC1"]))})
    assert ok.status_code == 200 and ok.json()["groups"] == []
