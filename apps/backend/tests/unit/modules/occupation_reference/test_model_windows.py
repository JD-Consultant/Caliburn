"""Exercise full-document scoring through real tokenization, without weights."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceProviderError,
    ReferenceQueryError,
)
from caliburn.modules.occupation_reference.infrastructure.models.local import (
    LocalModels,
)


class RecordingRanker:
    def __init__(self, torch: Any) -> None:
        self.torch = torch
        self.inputs: list[list[int]] = []
        self.logit: float | None = None

    def to(self, device: str) -> RecordingRanker:
        return self

    def eval(self) -> RecordingRanker:
        return self

    def __call__(self, **inputs: Any) -> SimpleNamespace:
        assert inputs.keys() == {"input_ids", "attention_mask", "return_dict"}
        assert inputs["input_ids"].shape[0] == 1
        assert inputs["input_ids"].shape[1] <= 8192
        assert not self.torch.is_grad_enabled()
        ids = inputs["input_ids"][0].tolist()
        assert inputs["attention_mask"][0].tolist() == [1] * len(ids)
        self.inputs.append(ids)
        logit = self.logit
        if logit is None:
            logit = max(
                ({5: -1.0, 6: 3.0, 7: 9.0}.get(i, 0.0) for i in ids[4:-1]),
                default=0.0,
            )
        return SimpleNamespace(logits=self.torch.tensor([[logit]]))


@pytest.fixture
def reranker(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[LocalModels, RecordingRanker]]:
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    tokenizers = pytest.importorskip("tokenizers")
    backend = tokenizers.Tokenizer(
        tokenizers.models.WordLevel(
            {
                "<s>": 0,
                "<pad>": 1,
                "</s>": 2,
                "<unk>": 3,
                "query": 4,
                "body": 5,
                "overlap": 6,
                "tail": 7,
            },
            unk_token="<unk>",
        )
    )
    backend.pre_tokenizer = tokenizers.pre_tokenizers.Whitespace()
    backend.post_processor = tokenizers.processors.TemplateProcessing(
        single="<s> $A </s>",
        pair="<s> $A </s> </s> $B </s>",
        special_tokens=[("<s>", 0), ("</s>", 2)],
    )
    tokenizer = transformers.PreTrainedTokenizerFast(
        tokenizer_object=backend,
        bos_token="<s>",
        eos_token="</s>",
        unk_token="<unk>",
        pad_token="<pad>",
    )
    ranker = RecordingRanker(torch)

    def tokenizer_factory(*args: object, **options: object) -> Any:
        assert options["revision"] == "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
        assert options["local_files_only"] is True
        assert options["trust_remote_code"] is False
        return tokenizer

    def ranker_factory(*args: object, **options: object) -> RecordingRanker:
        assert options["revision"] == "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
        assert options["local_files_only"] is True
        assert options["trust_remote_code"] is False
        return ranker

    monkeypatch.setattr(
        transformers.AutoTokenizer, "from_pretrained", tokenizer_factory
    )
    monkeypatch.setattr(
        transformers.AutoModelForSequenceClassification,
        "from_pretrained",
        ranker_factory,
    )
    models = LocalModels()
    try:
        yield models, ranker
    finally:
        models.close()


def test_full_document_preserves_overlap_tail_input_order_and_raw_logits(
    reranker: tuple[LocalModels, RecordingRanker],
) -> None:
    models, ranker = reranker
    document = "body " * 8123 + "overlap " + "body " * 8122 + "tail " + "body " * 754
    assert models.score("query", [document, "body"]) == [9.0, -1.0]
    assert ranker.inputs == [
        [0, 4, 2, 2, *([5] * 8123), 6, *([5] * 63), 2],
        [0, 4, 2, 2, 6, *([5] * 8122), 7, *([5] * 63), 2],
        [0, 4, 2, 2, 7, *([5] * 754), 2],
        [0, 4, 2, 2, 5, 2],
    ]


@pytest.mark.parametrize(
    "query,document,expected",
    [
        ("query", "body tail", [0, 4, 2, 2, 5, 7, 2]),
        ("query", "", [0, 4, 2, 2, 2]),
        ("query", " \t\n", [0, 4, 2, 2, 2]),
        ("", "body", [0, 2, 2, 5, 2]),
        ("", "", [0, 2, 2, 2]),
        ("query <s>", "</s> body", [0, 4, 0, 2, 2, 2, 5, 2]),
    ],
)
def test_pair_template_preserves_empty_and_special_token_inputs(
    reranker: tuple[LocalModels, RecordingRanker],
    query: str,
    document: str,
    expected: list[int],
) -> None:
    models, ranker = reranker
    models.score(query, [document])
    assert ranker.inputs == [expected]


@pytest.mark.parametrize("documents", [[], ["body"]])
def test_query_without_overlap_capacity_is_rejected_before_inference(
    reranker: tuple[LocalModels, RecordingRanker],
    documents: list[str],
) -> None:
    models, ranker = reranker
    with pytest.raises(ReferenceQueryError, match="capacity"):
        models.score("query " * 8124, documents)
    assert ranker.inputs == []


def test_smallest_allowed_capacity_does_not_truncate_the_query(
    reranker: tuple[LocalModels, RecordingRanker],
) -> None:
    models, ranker = reranker
    models.score("query " * 8123, ["body " * 70])
    assert ranker.inputs == [[0, *([4] * 8123), 2, 2, *([5] * 65), 2]] * 6


@pytest.mark.parametrize("logit", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_window_score_is_a_provider_failure(
    reranker: tuple[LocalModels, RecordingRanker],
    logit: float,
) -> None:
    models, ranker = reranker
    ranker.logit = logit
    with pytest.raises(ReferenceProviderError):
        models.score("query", ["body"])
