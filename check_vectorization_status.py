#!/usr/bin/env python3
"""
Snapshot summary of judgment/statute chunk vectorization status.
Assumes the chunking pipeline wrote JSONL files that ultimately load into
PostgreSQL tables `judgment_chunks` and `statute_chunks`.
"""

import os
import sys
from pathlib import Path

import psycopg2

# Ensure we can import the shared config
sys.path.insert(0, str(Path(__file__).parent / "legal_kb"))
from config import Config  # noqa: E402


def format_row(label: str, value) -> str:
    return f"{label:<32}: {value}"


def main() -> int:
    config = Config()
    conn = None

    try:
        conn = psycopg2.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            database=config.POSTGRES_DB,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
        )
        cur = conn.cursor()

        # Counts -------------------------------------------------------------
        cur.execute("SELECT COUNT(*) FROM judgment_chunks")
        judgment_total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM statute_chunks")
        statute_total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM judgment_chunks WHERE embedding IS NOT NULL")
        judgment_embedded = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM statute_chunks WHERE embedding IS NOT NULL")
        statute_embedded = cur.fetchone()[0]

        # Token stats --------------------------------------------------------
        cur.execute(
            """
            SELECT
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY tokens),
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY tokens),
                MAX(tokens),
                MIN(tokens)
            FROM judgment_chunks
            """
        )
        j_p50, j_p95, j_max, j_min = cur.fetchone()

        cur.execute(
            """
            SELECT
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY tokens),
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY tokens),
                MAX(tokens),
                MIN(tokens)
            FROM statute_chunks
            """
        )
        s_p50, s_p95, s_max, s_min = cur.fetchone()

        # Oversized / undersized safeguards
        cur.execute("SELECT COUNT(*) FROM judgment_chunks WHERE tokens > 800 OR tokens < 80")
        judgment_bad = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM statute_chunks WHERE tokens > 800 OR tokens < 1")
        statute_bad = cur.fetchone()[0]

        # Print summary ------------------------------------------------------
        print("Vectorization Status")
        print("=" * 72)
        print(format_row("Judgment chunks (total)", judgment_total))
        print(format_row("Judgment chunks (embedded)", judgment_embedded))
        print(format_row("Statute chunks (total)", statute_total))
        print(format_row("Statute chunks (embedded)", statute_embedded))
        print()
        print("Judgment token distribution")
        if j_p50 is None:
            print("  (no judgment chunks stored)")
        else:
            print(format_row("p50", f"{j_p50:.0f}"))
            print(format_row("p95", f"{j_p95:.0f}"))
            print(format_row("max", f"{j_max:.0f}"))
            print(format_row("min", f"{j_min:.0f}"))
        print(format_row("out-of-range chunks", judgment_bad))
        print()
        print("Statute token distribution")
        if s_p50 is None:
            print("  (no statute chunks stored)")
        else:
            print(format_row("p50", f"{s_p50:.0f}"))
            print(format_row("p95", f"{s_p95:.0f}"))
            print(format_row("max", f"{s_max:.0f}"))
            print(format_row("min", f"{s_min:.0f}"))
        print(format_row("out-of-range chunks", statute_bad))
        print()

        # Top docs by chunk count
        cur.execute(
            """
            SELECT doc_id, COUNT(*) AS cnt
            FROM judgment_chunks
            GROUP BY doc_id
            ORDER BY cnt DESC
            LIMIT 5
            """
        )
        rows = cur.fetchall()
        print("Top judgments by chunk count")
        if not rows:
            print("  (no data yet)")
        else:
            for doc_id, cnt in rows:
                print(f"  - {doc_id}: {cnt} chunks")

        cur.close()
        conn.close()

        return 0

    except Exception as exc:
        print(f"Database check failed: {exc}")
        if conn:
            conn.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
