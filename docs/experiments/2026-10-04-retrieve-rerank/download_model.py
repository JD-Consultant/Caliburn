"""Bounded mechanism probe: download public weights, no employee data leaves host."""
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path

import requests
from huggingface_hub import snapshot_download

out = Path('/experiment')
model = 'BAAI/bge-reranker-v2-m3'
started = time.perf_counter()
revision = '953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e'
path = Path(snapshot_download(model, revision=revision, allow_patterns=[
    'config.json', 'model.safetensors', 'tokenizer*', 'sentencepiece.bpe.model', 'special_tokens_map.json']))
files = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
         for p in path.iterdir() if p.is_file()}
assert files['model.safetensors']['sha256'] == 'd9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286'
result = {'model': model, 'revision': revision, 'path': str(path), 'files': files,
          'download_seconds': time.perf_counter() - started,
          'packages': {k: importlib.metadata.version(k) for k in ['torch', 'transformers', 'huggingface-hub']}}
(out/'model.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({k: result[k] for k in ['model', 'revision', 'download_seconds', 'packages']}), flush=True)
import runpy
runpy.run_path(str(out/'gpu_worker.py'),run_name='__main__')
