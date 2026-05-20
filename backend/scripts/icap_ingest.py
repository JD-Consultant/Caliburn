"""
Batch-embed all iCAP JSON files and upsert into the pgvector icap_embeddings table.

Usage (from repo root, with .env loaded):
    cd backend
    python -m scripts.icap_ingest --json-dir /path/to/json [--batch-size 50] [--dry-run]

Requirements: DATABASE_URL_SYNC and OPENAI_API_KEY must be set in .env.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Allow running as a module from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import psycopg2
from openai import OpenAI

from scripts.icap_parser import parse_icap_file

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL_SYNC = os.environ.get("DATABASE_URL_SYNC", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL   = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBED_DIM         = 1536  # text-embedding-3-small output dimension

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ── Helpers ───────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API with retry on rate-limit."""
    if client is None:
        raise RuntimeError("OPENAI_API_KEY not set")
    for attempt in range(5):
        try:
            resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            return [item.embedding for item in resp.data]
        except Exception as e:
            if "rate" in str(e).lower() and attempt < 4:
                wait = 2 ** attempt
                print(f"  [rate-limit] waiting {wait}s …")
                time.sleep(wait)
            else:
                raise


def upsert_nodes(conn, nodes_with_embeddings: list[tuple]) -> int:
    """
    Insert rows into icap_embeddings.
    Returns number of rows inserted.
    Schema:
        id UUID, ocs_code TEXT, chunk_type TEXT, chunk_text TEXT,
        metadata JSONB, embedding vector(1536)
    """
    sql = """
        INSERT INTO icap_embeddings
            (id, ocs_code, chunk_type, chunk_text, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::vector)
        ON CONFLICT (id) DO UPDATE SET
            chunk_text = EXCLUDED.chunk_text,
            metadata   = EXCLUDED.metadata,
            embedding  = EXCLUDED.embedding
    """
    import json as _json
    cur = conn.cursor()
    rows = [
        (
            node.id_,
            node.metadata.get("ocs_code", ""),
            node.metadata.get("chunk_type", ""),
            node.text,
            _json.dumps(node.metadata, ensure_ascii=False),
            f"[{','.join(str(v) for v in emb)}]",
        )
        for node, emb in nodes_with_embeddings
    ]
    cur.executemany(sql, rows)
    conn.commit()
    cur.close()
    return len(rows)


def clear_ocs_code(conn, ocs_code: str):
    """Remove all rows for a given ocs_code before re-inserting (idempotent re-run)."""
    cur = conn.cursor()
    cur.execute("DELETE FROM icap_embeddings WHERE ocs_code = %s", (ocs_code,))
    conn.commit()
    cur.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def _dedup_files(all_files: list[Path]) -> list[Path]:
    """Return one representative file per OCS code (first encountered wins)."""
    import json as _json
    seen: set[str] = set()
    unique: list[Path] = []
    for fp in all_files:
        try:
            data = _json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        vi = data.get("version_info", {})
        code = next(
            (v["ocs_code"] for v in vi.get("versions", []) if v.get("status") == "最新版本"),
            None,
        )
        if code and data.get("ocs_profile", {}).get("ocs_code") == code:
            if code not in seen:
                seen.add(code)
                unique.append(fp)
    return unique


def _already_ingested(conn, ocs_code: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM icap_embeddings WHERE ocs_code = %s LIMIT 1", (ocs_code,))
    exists = cur.fetchone() is not None
    cur.close()
    return exists


def ingest(json_dir: str, batch_size: int = 50, dry_run: bool = False, resume: bool = False):
    json_root = Path(json_dir)
    all_files = sorted(json_root.rglob("*.json"))
    print(f"Found {len(all_files)} JSON files under {json_root}")

    unique_files = _dedup_files(all_files)
    print(f"Unique OCS codes: {len(unique_files)}  (skipping {len(all_files) - len(unique_files)} duplicates)")

    if dry_run:
        print("[dry-run] parsing first 3 unique files only, no DB writes")
        unique_files = unique_files[:3]

    conn = None if dry_run else psycopg2.connect(DATABASE_URL_SYNC)

    total_nodes   = 0
    total_files   = 0
    skipped_files = 0
    resumed_files = 0

    for file_path in unique_files:
        nodes = parse_icap_file(file_path)
        if not nodes:
            skipped_files += 1
            continue

        ocs_code = nodes[0].metadata.get("ocs_code", "unknown")

        if not dry_run and resume and _already_ingested(conn, ocs_code):
            resumed_files += 1
            print(f"  [skip] {ocs_code} already in DB")
            continue

        print(f"  [{total_files + 1}/{len(unique_files)}] {ocs_code} → {len(nodes)} nodes  ({file_path.name})")

        if dry_run:
            for n in nodes[:2]:
                print(f"    [{n.metadata['chunk_type']}] {n.text[:70]!r}")
            total_files += 1
            total_nodes += len(nodes)
            continue

        # Delete existing rows for this OCS code so reruns are idempotent
        clear_ocs_code(conn, ocs_code)

        # Embed in batches to respect token limits
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i : i + batch_size]
            texts = [n.text for n in batch]
            embeddings = embed_texts(texts)
            upsert_nodes(conn, list(zip(batch, embeddings)))
            print(f"    embedded batch {i // batch_size + 1} ({len(batch)} nodes)")

        total_files += 1
        total_nodes += len(nodes)

    if conn:
        conn.close()

    print(
        f"\nDone. Processed: {total_files}  |  "
        f"Resumed (already in DB): {resumed_files}  |  "
        f"Skipped (parse error): {skipped_files}  |  "
        f"Total nodes: {total_nodes}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest iCAP JSONs into pgvector")
    parser.add_argument("--json-dir", required=True, help="Root directory of iCAP JSON files")
    parser.add_argument("--batch-size", type=int, default=50, help="Embedding batch size (default 50)")
    parser.add_argument("--dry-run", action="store_true", help="Parse + print only, no DB writes")
    parser.add_argument("--resume", action="store_true", help="Skip OCS codes already present in DB")
    args = parser.parse_args()

    ingest(args.json_dir, args.batch_size, args.dry_run, args.resume)
