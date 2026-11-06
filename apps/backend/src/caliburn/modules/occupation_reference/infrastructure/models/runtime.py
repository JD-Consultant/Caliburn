"""Keep dynamic Transformers values inside this local SDK boundary."""

from __future__ import annotations

import gc
import importlib
import math
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceProviderError,
    ReferenceUnavailableError,
)


@dataclass
class ModelRuntime:
    # Transformers auto factories and ModelOutput intentionally have dynamic
    # signatures. No SDK value escapes this adapter into application models.
    tokenizer: Any
    encoder: Any
    torch: ModuleType
    device: str

    def close(self) -> None:
        self.encoder = None
        self.tokenizer = None
        gc.collect()
        if self.device.split(":", 1)[0] == "cuda":
            self.torch.cuda.empty_cache()

    def encode(self, text: str) -> list[int]:
        tokens: object = self.tokenizer.encode(
            text, add_special_tokens=False, truncation=False
        )
        if not isinstance(tokens, list) or not all(
            isinstance(token, int) for token in tokens
        ):
            raise ReferenceProviderError("tokenizer returned invalid token IDs")
        return [int(token) for token in tokens]

    def pair_score(self, query: list[int], document: list[int]) -> float:
        bos = self.tokenizer.bos_token_id
        eos = self.tokenizer.eos_token_id
        if not isinstance(bos, int) or not isinstance(eos, int):
            raise ReferenceProviderError("reranker tokenizer lacks pair delimiters")
        # Fixed BGE reranker uses XLM-R's four-token pair template, including
        # empty documents. Preserve window token IDs without decoding them.
        ids = [bos, *query, eos, eos, *document, eos]
        if len(ids) > 8192:
            raise ReferenceProviderError("reranker pair exceeds model token capacity")
        inputs = {
            "input_ids": self.torch.tensor([ids], device=self.device),
            "attention_mask": self.torch.ones(
                (1, len(ids)), device=self.device, dtype=self.torch.long
            ),
        }
        with self.torch.inference_mode():
            return float(
                self.encoder(**inputs, return_dict=True)
                .logits.flatten()[0]
                .float()
                .item()
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        encoded = self.tokenizer(
            texts, padding=True, truncation=True, max_length=8192, return_tensors="pt"
        )
        inputs = {key: value.to(self.device) for key, value in encoded.items()}
        with self.torch.inference_mode():
            output = self.encoder(**inputs, return_dict=True)
            # BGE-M3's dense head is normalized CLS, in the model's precision.
            dense = self.torch.nn.functional.normalize(
                output.last_hidden_state[:, 0], p=2, dim=-1
            )
            rows: object = dense.float().cpu().tolist()
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise ReferenceProviderError("embedding count does not match input")
        result = []
        for row in rows:
            if not isinstance(row, list) or len(row) != 1024:
                raise ReferenceProviderError("embedding must have 1024 dimensions")
            if not all(
                isinstance(value, (float, int)) and math.isfinite(value)
                for value in row
            ):
                raise ReferenceProviderError("embedding contains non-finite values")
            result.append([float(value) for value in row])
        return result


def load_runtime(
    *,
    model: str,
    revision: str,
    path: Path | None,
    cache_dir: Path | None,
    device: str,
    use_fp16: bool,
    classification: bool = False,
) -> ModelRuntime:
    """Load only a fixed cached snapshot; never fetch code or model files."""
    if path is not None and (not path.is_dir() or path.name != revision):
        raise ReferenceUnavailableError(
            "model path must be an existing snapshot named by its fixed revision"
        )
    try:
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
        source = str(path) if path is not None else model
        options = {
            "revision": revision,
            "local_files_only": True,
            "trust_remote_code": False,
            "cache_dir": str(cache_dir) if cache_dir is not None else None,
        }
        tokenizer = transformers.AutoTokenizer.from_pretrained(source, **options)
        factory = (
            transformers.AutoModelForSequenceClassification
            if classification
            else transformers.AutoModel
        )
        dtype = (
            torch.float16
            if use_fp16 and device.split(":", 1)[0] != "cpu"
            else torch.float32
        )
        encoder = factory.from_pretrained(
            source, **options, dtype=dtype, attn_implementation="sdpa"
        )
        encoder = encoder.to(device).eval()
        return ModelRuntime(tokenizer, encoder, torch, device)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise ReferenceUnavailableError(
            "fixed local model could not be loaded"
        ) from exc
