#!/usr/bin/env python3
"""
Apply stored tsvector + GIN migration for fast BM25 on judgment_chunks and statute_chunks.
Safe to run multiple times.
"""
import sys
from pathlib import Path

import psycopg2

# Make local package importable
sys.path.insert(0, str(Path(__file__).parent / "legal_kb"))
from config import Config  # type: ignore


SQL = r"""
-- Enable helpful extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- english_unaccent configuration (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_ts_config WHERE cfgname = 'english_unaccent'
  ) THEN
    CREATE TEXT SEARCH CONFIGURATION english_unaccent ( COPY = english );
    ALTER TEXT SEARCH CONFIGURATION english_unaccent
      ALTER MAPPING FOR hword, hword_part, word WITH unaccent, english_stem;
  END IF;
END$$;

-- Stored tsvector for judgment_chunks
ALTER TABLE judgment_chunks
  ADD COLUMN IF NOT EXISTS tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector(
      'english_unaccent',
      coalesce(case_title,'') || ' ' || coalesce(text,'')
    )
  ) STORED;

CREATE INDEX IF NOT EXISTS ix_judgment_chunks_tsv
  ON judgment_chunks
  USING GIN (tsv);

-- Stored tsvector for statute_chunks
ALTER TABLE statute_chunks
  ADD COLUMN IF NOT EXISTS tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector(
      'english_unaccent',
      coalesce(title,'') || ' ' || coalesce(text,'')
    )
  ) STORED;

CREATE INDEX IF NOT EXISTS ix_statute_chunks_tsv
  ON statute_chunks
  USING GIN (tsv);

-- Trigram indexes to accelerate small lexical boosts
CREATE INDEX IF NOT EXISTS ix_judgment_chunks_title_trgm
  ON judgment_chunks USING gin (lower(case_title) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_judgment_chunks_citations_trgm
  ON judgment_chunks USING gin (lower(citation_strings::text) gin_trgm_ops);
"""


def main() -> int:
    cfg = Config()
    conn = None
    try:
        conn = psycopg2.connect(
            host=cfg.POSTGRES_HOST,
            port=cfg.POSTGRES_PORT,
            database=cfg.POSTGRES_DB,
            user=cfg.POSTGRES_USER,
            password=cfg.POSTGRES_PASSWORD,
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SQL)
        cur.close()
        conn.close()
        print("Stored tsvector migration applied successfully.")
        return 0
    except Exception as exc:
        if conn:
            conn.close()
        print(f"Migration failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
