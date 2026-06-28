"""jd-ocs-indexer: OCS JSON -> Qdrant index builder."""

# Windows OpenMP workaround — set BEFORE torch/numpy load their native runtimes.
# On Windows, torch's multi-threaded CPU kernels segfault here when a duplicate
# OpenMP runtime (libiomp/MKL) is present: BGE-M3 weight access / forward crash
# (SIGSEGV) regardless of torch/transformers/numpy version. Serializing OpenMP
# (OMP_NUM_THREADS=1) + tolerating the duplicate lib avoids it. GPU compute is
# unaffected (work runs on CUDA). setdefault → users can still override; guarded
# to win32 so Linux/CI keep full CPU threading.
import os as _os
import sys as _sys

if _sys.platform == "win32":
    _os.environ.setdefault("OMP_NUM_THREADS", "1")
    _os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

__version__ = "0.1.0"
