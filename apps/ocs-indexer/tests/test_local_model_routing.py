"""Actual local HTTP routing must not inherit a shell's ambient proxy."""

import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
import pytest
from jd_ocs_indexer.embeddings.http_embedder import HttpEmbedder
from jd_ocs_indexer.reranking.http_reranker import MODEL, REVISION, HttpReranker
from jd_ocs_indexer.store.qdrant_client import make_client
from qdrant_client import qdrant_remote


@contextmanager
def local_model_server():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, None))
            result = (
                {"title": "qdrant", "version": "1.18.2"}
                if self.path.rstrip("/") == ""
                else {"result": {"collections": []}, "status": "ok", "time": 0.0}
            )
            encoded = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, body))
            if self.path.endswith("/embed"):
                result = {
                    "embeddings": [
                        {
                            "dense": [0.1] * 1024,
                            "sparse": {"indices": [1], "values": [0.5]},
                        }
                        for _ in body["texts"]
                    ],
                    "model": "BAAI/bge-m3",
                    "dim": 1024,
                    "revision": 1,
                    "model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
                }
            else:
                result = {"model": MODEL, "revision": REVISION, "scores": [0.5]}
            encoded = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        assert not worker.is_alive()


@pytest.mark.parametrize("adapter_type", [HttpEmbedder, HttpReranker])
def test_model_text_goes_to_explicit_origin_not_environment_proxy(
    monkeypatch, adapter_type
):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    with (
        local_model_server() as (origin, direct),
        local_model_server() as (proxy, redirected),
    ):
        monkeypatch.setenv("HTTP_PROXY", proxy)
        adapter = adapter_type(origin)
        try:
            if isinstance(adapter, HttpEmbedder):
                assert len(adapter.embed_query("SYNTHETIC-EMPLOYEE-TEXT").dense) == 1024
            else:
                assert adapter.score(
                    "SYNTHETIC-EMPLOYEE-TEXT", ["public reference"]
                ) == [0.5]
        finally:
            adapter.close()
        assert len(direct) == 1
        assert redirected == []


def test_qdrant_uses_explicit_origin_without_environment_proxy(monkeypatch):
    probes = []

    def track_probe_thread(*args, **kwargs):
        thread = Thread(*args, **kwargs)
        probes.append(thread)
        return thread

    monkeypatch.setattr(qdrant_remote, "Thread", track_probe_thread)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    with (
        local_model_server() as (origin, direct),
        local_model_server() as (proxy, redirected),
    ):
        monkeypatch.setenv("HTTP_PROXY", proxy)
        client = make_client(url=origin, api_key=None)
        try:
            assert client.get_collections().collections == []
        finally:
            client.close()
            for probe in probes:
                probe.join(timeout=10)
                assert not probe.is_alive()
        assert any(path == "/collections" for path, _ in direct)
        assert redirected == []


@pytest.mark.parametrize("adapter_type", [HttpEmbedder, HttpReranker])
def test_adapter_leaves_injected_client_ownership_with_caller(adapter_type):
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200))
    ) as client:
        adapter = adapter_type("http://synthetic-model", client=client)
        adapter.close()
        assert not client.is_closed
    assert client.is_closed
