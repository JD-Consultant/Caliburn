"""Public pinned model download with bounded ranges; verify upstream LFS SHA256."""

import concurrent.futures
import hashlib
import json
import time
from pathlib import Path

import httpx

MODEL = "BAAI/bge-m3"
REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache/weights"
CACHE.mkdir(parents=True, exist_ok=True)
url = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/pytorch_model.bin"
tree = httpx.get(f"https://huggingface.co/api/models/{MODEL}/tree/{REVISION}",
                 trust_env=False, timeout=30).raise_for_status().json()
entry = next(row for row in tree if row["path"] == "pytorch_model.bin")
size = entry["size"]
expected = entry["lfs"]["oid"]
chunk = 32 * 1024 * 1024
started = time.monotonic()


def part(index):
    low = index * chunk
    high = min(size - 1, low + chunk - 1)
    path = CACHE / f"part-{index:03d}.bin"
    if path.exists() and path.stat().st_size == high - low + 1:
        return index
    with httpx.stream("GET", url, headers={"Range": f"bytes={low}-{high}"},
                       follow_redirects=True, timeout=120, trust_env=False) as response:
        response.raise_for_status()
        if response.status_code != 206 or not response.headers.get("content-range", "").startswith(f"bytes {low}-{high}/"):
            raise ValueError("Server did not respect bounded byte range")
        with path.open("wb") as out:
            for data in response.iter_bytes():
                out.write(data)
    if path.stat().st_size != high - low + 1:
        raise ValueError("Incomplete model range")
    return index


count = (size + chunk - 1) // chunk
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    futures = [pool.submit(part, index) for index in range(count)]
    for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
        print(f"weights range {future.result()} done {done}/{count}; {time.monotonic()-started:.1f}s", flush=True)
digest = hashlib.sha256()
with (CACHE / "pytorch_model.bin").open("wb") as out:
    for index in range(count):
        with (CACHE / f"part-{index:03d}.bin").open("rb") as part_file:
            while data := part_file.read(4 * 1024 * 1024):
                digest.update(data)
                out.write(data)
if digest.hexdigest() != expected:
    raise ValueError("Public model LFS checksum mismatch")
(CACHE / "verification.json").write_text(json.dumps({"revision": REVISION, "size": size,
    "expected_sha256": expected, "actual_sha256": digest.hexdigest(),
    "elapsed_seconds": time.monotonic() - started}, indent=2), encoding="utf-8")
print("Verified complete public model", digest.hexdigest(), flush=True)
