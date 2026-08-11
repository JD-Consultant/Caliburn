"""Shared kernel:跨功能模組共用的 Current State 與穩定 domain language(ADR 0058）。

不得 import FastAPI、SQLAlchemy、HTTPX、OpenPyXL 或任何 feature／adapter 模組。
"""
