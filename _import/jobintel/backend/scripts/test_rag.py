"""
Quick RAG query test — calls icap_retriever functions and prints results.

Usage (from backend/):
    python -m scripts.test_rag --query "資料庫備份還原" --type task
    python -m scripts.test_rag --query "電腦維修" --type all
    python -m scripts.test_rag --query "SQL 查詢語法" --type knowledge --ocs-code DAT-001
"""
import argparse
import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from app.services.icap_retriever import (
    search_tasks,
    search_outputs,
    search_indicators,
    search_knowledge,
    search_skills,
    search_attitudes,
)

SEARCH_FNS = {
    "task":      search_tasks,
    "output":    search_outputs,
    "indicator": search_indicators,
    "knowledge": search_knowledge,
    "skill":     search_skills,
    "attitude":  search_attitudes,
}


def _bar(similarity: float, width: int = 20) -> str:
    filled = round(similarity * width)
    return "#" * filled + "-" * (width - filled)


async def run(query: str, chunk_types: list[str], top_k: int, ocs_code: str | None):
    for chunk_type in chunk_types:
        fn = SEARCH_FNS[chunk_type]
        print(f"\n{'─'*60}")
        print(f"  query      : {query}")
        print(f"  chunk_type : {chunk_type}   top_k={top_k}"
              + (f"   ocs_code={ocs_code}" if ocs_code else ""))
        print(f"{'─'*60}")

        kwargs = {"top_k": top_k}
        if ocs_code and chunk_type in ("task", "output", "indicator"):
            kwargs["ocs_code_filter"] = ocs_code

        hits = await fn(query, **kwargs)

        if not hits:
            print("  （無結果 — similarity 低於 0.58 閾值）")
            continue

        for i, h in enumerate(hits, 1):
            sim = h["similarity"]
            print(f"\n  #{i}  {_bar(sim)}  {sim:.4f}")
            print(f"       code      : {h['code']}")
            print(f"       name      : {h['name']}")
            print(f"       ocs_code  : {h['ocs_code']}")
            if h.get("breadcrumb"):
                print(f"       breadcrumb: {h['breadcrumb']}")


def main():
    parser = argparse.ArgumentParser(description="RAG query test")
    parser.add_argument("--query", required=True, help="查詢字串")
    parser.add_argument(
        "--type", default="all",
        choices=["all", "task", "output", "indicator", "knowledge", "skill", "attitude"],
        help="chunk_type（預設 all）",
    )
    parser.add_argument("--top-k", type=int, default=3, help="回傳筆數（預設 3）")
    parser.add_argument("--ocs-code", default=None, help="縮窄到特定職種（如 DAT-001）")
    args = parser.parse_args()

    chunk_types = list(SEARCH_FNS.keys()) if args.type == "all" else [args.type]
    asyncio.run(run(args.query, chunk_types, args.top_k, args.ocs_code))


if __name__ == "__main__":
    main()
