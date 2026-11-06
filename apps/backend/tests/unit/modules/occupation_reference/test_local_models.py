"""Public local-model identity and lifetime, independent of model downloads."""

import sys
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceProviderError,
    ReferenceUnavailableError,
)
from caliburn.modules.occupation_reference.infrastructure.models.local import (
    LocalModels,
    embedding_signature,
)


def test_signature_identifies_actual_precision_without_loading_sdk() -> None:
    imported = set(sys.modules)
    cpu = embedding_signature(device="cpu", use_fp16=True)
    assert cpu == embedding_signature(device="cpu", use_fp16=False)
    assert cpu != embedding_signature(device="cuda", use_fp16=True)
    assert "torch" not in set(sys.modules) - imported
    assert "transformers" not in set(sys.modules) - imported


def test_empty_embedding_and_close_do_not_load_models() -> None:
    imported = set(sys.modules)
    models = LocalModels()
    assert models.embed_texts([]) == []
    models.close()
    models.close()
    with pytest.raises(ReferenceUnavailableError, match="closed"):
        models.embed_texts([])
    assert "torch" not in set(sys.modules) - imported
    assert "transformers" not in set(sys.modules) - imported


def test_failed_cuda_cache_cleanup_still_releases_both_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    owned: list[weakref.ReferenceType[Encoder]] = []
    cleanups: list[str] = []

    class Tokenizer:
        def __call__(self, texts: list[str], **options: object) -> dict[str, Any]:
            return {}

        def encode(self, text: str, **options: object) -> list[int]:
            return [4]

    class Encoder:
        def to(self, device: str) -> Encoder:
            return self

        def eval(self) -> Encoder:
            return self

        def __call__(self, **inputs: Any) -> SimpleNamespace:
            # Only cleanup simulates CUDA; the fake model stays on CPU.
            return SimpleNamespace(last_hidden_state=torch.ones((1, 1, 1024)))

    def encoder_factory(*args: object, **options: object) -> Encoder:
        encoder = Encoder()
        owned.append(weakref.ref(encoder))
        return encoder

    def empty_cache() -> None:
        cleanups.append("attempt")
        if len(cleanups) == 1:
            raise RuntimeError("CUDA cleanup failed")

    monkeypatch.setattr(torch.cuda, "empty_cache", empty_cache)
    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda *args, **kwargs: Tokenizer(),
    )
    monkeypatch.setattr(transformers.AutoModel, "from_pretrained", encoder_factory)
    monkeypatch.setattr(
        transformers.AutoModelForSequenceClassification,
        "from_pretrained",
        encoder_factory,
    )
    models = LocalModels(device="cuda")
    try:
        assert len(models.embed_query("query").dense) == 1024
        assert models.score("query", []) == []
        with pytest.raises(RuntimeError, match="CUDA cleanup failed"):
            models.close()
        assert len(owned) == 2
        assert all(model() is None for model in owned)
        models.close()
    finally:
        models.close()


def test_embedding_uses_normalized_cls_in_input_order_and_8192_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")

    class Tokenizer:
        def __call__(self, texts: list[str], **options: object) -> dict[str, Any]:
            assert options["max_length"] == 8192
            assert options["truncation"] is True
            assert options["padding"] is True
            assert options["return_tensors"] == "pt"
            return {"input_ids": torch.tensor([[len(text)] for text in texts])}

    class Encoder:
        def to(self, device: str) -> Encoder:
            return self

        def eval(self) -> Encoder:
            return self

        def __call__(self, **inputs: Any) -> SimpleNamespace:
            assert not torch.is_grad_enabled()
            rows = inputs["input_ids"].flatten().tolist()
            states = torch.zeros((len(rows), 2, 1024))
            for index, length in enumerate(rows):
                pair = [3.0, 4.0] if length == 3 else [4.0, 3.0]
                states[index, 0, :2] = torch.tensor(pair)
                states[index, 1, :2] = torch.tensor([100.0, 0.0])
            return SimpleNamespace(last_hidden_state=states)

    def tokenizer_factory(*args: object, **options: object) -> Tokenizer:
        assert options["local_files_only"] is True
        assert options["trust_remote_code"] is False
        assert options["revision"] == "5617a9f61b028005a4858fdac845db406aefb181"
        return Tokenizer()

    def encoder_factory(*args: object, **options: object) -> Encoder:
        assert options["local_files_only"] is True
        assert options["trust_remote_code"] is False
        assert options["revision"] == "5617a9f61b028005a4858fdac845db406aefb181"
        return Encoder()

    monkeypatch.setattr(
        transformers.AutoTokenizer, "from_pretrained", tokenizer_factory
    )
    monkeypatch.setattr(transformers.AutoModel, "from_pretrained", encoder_factory)
    models = LocalModels(batch_size=1)
    try:
        embeddings = models.embed_texts(["abc", "de"])
        assert len(embeddings) == 2
        assert len(embeddings[0].dense) == 1024
        assert embeddings[0].dense[:3] == pytest.approx([0.6, 0.8, 0.0])
        assert embeddings[1].dense[:3] == pytest.approx([0.8, 0.6, 0.0])
        assert models.embed_query("abc") == embeddings[0]
    finally:
        models.close()


def test_lazy_reranker_load_failure_preserves_embedding_until_owner_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    owned: list[weakref.ReferenceType[Encoder]] = []

    class Tokenizer:
        def __call__(self, texts: list[str], **options: object) -> dict[str, Any]:
            return {}

    class Encoder:
        def to(self, device: str) -> Encoder:
            return self

        def eval(self) -> Encoder:
            return self

        def __call__(self, **inputs: Any) -> SimpleNamespace:
            return SimpleNamespace(last_hidden_state=torch.ones((1, 1, 1024)))

    def encoder_factory(*args: object, **options: object) -> Encoder:
        encoder = Encoder()
        owned.append(weakref.ref(encoder))
        return encoder

    def missing_ranker(*args: object, **options: object) -> None:
        raise OSError("fixed reranker snapshot is missing")

    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda *args, **kwargs: Tokenizer(),
    )
    monkeypatch.setattr(transformers.AutoModel, "from_pretrained", encoder_factory)
    monkeypatch.setattr(
        transformers.AutoModelForSequenceClassification,
        "from_pretrained",
        missing_ranker,
    )
    models = LocalModels()
    try:
        first = models.embed_query("query")
        with pytest.raises(ReferenceUnavailableError, match="could not be loaded"):
            models.score("query", ["document"])
        assert models.embed_query("query") == first
    finally:
        models.close()
    assert len(owned) == 1
    assert owned[0]() is None
    with pytest.raises(ReferenceUnavailableError, match="closed"):
        models.embed_query("query")


def test_close_waits_for_physical_inference_before_rejecting_new_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    started = threading.Event()
    release = threading.Event()
    closing = threading.Event()
    closed = threading.Event()

    class Tokenizer:
        def __call__(self, texts: list[str], **options: object) -> dict[str, Any]:
            return {"input_ids": torch.tensor([[1]])}

    class Encoder:
        def to(self, device: str) -> Encoder:
            return self

        def eval(self) -> Encoder:
            return self

        def __call__(self, **inputs: Any) -> SimpleNamespace:
            started.set()
            assert release.wait(3), "test did not release model inference"
            return SimpleNamespace(last_hidden_state=torch.ones((1, 1, 1024)))

    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda *args, **kwargs: Tokenizer(),
    )
    monkeypatch.setattr(
        transformers.AutoModel, "from_pretrained", lambda *args, **kwargs: Encoder()
    )
    models = LocalModels()

    def close() -> None:
        closing.set()
        models.close()
        closed.set()

    with ThreadPoolExecutor(max_workers=2) as threads:
        inference = threads.submit(models.embed_query, "query")
        shutdown = None
        try:
            assert started.wait(3)
            shutdown = threads.submit(close)
            assert closing.wait(3)
            assert not closed.wait(0.05)
        finally:
            release.set()
            inference.result(timeout=3)
            if shutdown is not None:
                shutdown.result(timeout=3)
            models.close()
    with pytest.raises(ReferenceUnavailableError, match="closed"):
        models.score("query", ["document"])


@pytest.mark.parametrize("failure_stage", ["tokenizer", "model"])
def test_reranker_operational_value_error_is_a_provider_failure(
    monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")

    class Tokenizer:
        bos_token_id = 0
        eos_token_id = 2

        def encode(self, text: str, **options: object) -> list[int]:
            if failure_stage == "tokenizer":
                raise ValueError("tokenizer computation failed")
            return [4]

    class Ranker:
        def to(self, device: str) -> Ranker:
            return self

        def eval(self) -> Ranker:
            return self

        def __call__(self, **inputs: Any) -> SimpleNamespace:
            raise ValueError("model computation failed")

    monkeypatch.setattr(
        transformers.AutoTokenizer,
        "from_pretrained",
        lambda *args, **kwargs: Tokenizer(),
    )
    monkeypatch.setattr(
        transformers.AutoModelForSequenceClassification,
        "from_pretrained",
        lambda *args, **kwargs: Ranker(),
    )
    models = LocalModels()
    try:
        with pytest.raises(ReferenceProviderError):
            models.score("valid query", ["valid document"])
    finally:
        models.close()
