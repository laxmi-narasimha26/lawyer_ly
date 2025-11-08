#!/usr/bin/env python3
"""
Embed chunked legal documents (judgments + statutes) into PostgreSQL/pgvector.
Source data: out/chunks/2020/*.jsonl and out/chunks/BNS/BNS_2023.jsonl
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Dict, Any

import openai
from openai import OpenAI
import psycopg2

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "legal_kb"))
from config import Config  # noqa: E402


MODEL = "text-embedding-3-small"
BATCH_SIZE = 64  # keep comfortably below 128
MAX_RETRIES = 5
RETRY_BACKOFF = 2.0


def to_pgvector(values: List[float]) -> str:
    return "[" + ",".join(f"{v:.10f}" for v in values) + "]"


def parse_date(value: Any):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def chunk_iter(paths: Iterable[Path]) -> Iterable[Dict[str, Any]]:
    for path in sorted(paths):
        for record in load_jsonl(path):
            record["_source_file"] = str(path)
            yield record


def embed_batch(client: OpenAI, texts: List[str]) -> List[List[float]]:
    attempt = 0
    while True:
        try:
            response = client.embeddings.create(model=MODEL, input=texts)
            return [item.embedding for item in response.data]
        except (openai.RateLimitError, openai.APIError, openai.InternalServerError) as err:
            attempt += 1
            if isinstance(err, openai.APIError) and err.status not in {429, 500, 503}:
                raise
            if attempt > MAX_RETRIES:
                raise
            sleep_for = RETRY_BACKOFF ** attempt
            time.sleep(sleep_for)


def upsert_judgment_batch(cur, batch: List[Dict[str, Any]], embeddings: List[List[float]]):
    sql = """
        INSERT INTO judgment_chunks (
            id, doc_id, type, "order", text, tokens, overlap_tokens,
            case_title, decision_date, bench, citation_strings, para_range,
            source_path, sha256, embedding
        )
        VALUES (
            %(id)s, %(doc_id)s, %(type)s, %(order)s, %(text)s, %(tokens)s, %(overlap_tokens)s,
            %(case_title)s, %(decision_date)s, %(bench)s, %(citation_strings)s, %(para_range)s,
            %(source_path)s, %(sha256)s, %(embedding)s
        )
        ON CONFLICT (id) DO UPDATE SET
            text = EXCLUDED.text,
            tokens = EXCLUDED.tokens,
            overlap_tokens = EXCLUDED.overlap_tokens,
            case_title = EXCLUDED.case_title,
            decision_date = EXCLUDED.decision_date,
            bench = EXCLUDED.bench,
            citation_strings = EXCLUDED.citation_strings,
            para_range = EXCLUDED.para_range,
            source_path = EXCLUDED.source_path,
            sha256 = EXCLUDED.sha256,
            embedding = EXCLUDED.embedding,
            updated_at = NOW()
    """
    for record, embedding in zip(batch, embeddings):
        cur.execute(sql, {
            "id": record["id"],
            "doc_id": record["doc_id"],
            "type": record["type"],
            "order": float(record["order"]),
            "text": record["text"],
            "tokens": int(record["tokens"]),
            "overlap_tokens": int(record.get("overlap_tokens", 0)),
            "case_title": record.get("case_title"),
            "decision_date": parse_date(record.get("decision_date")),
            "bench": json.dumps(record.get("bench") or []),
            "citation_strings": json.dumps(record.get("citation_strings") or []),
            "para_range": record.get("para_range"),
            "source_path": record.get("source_path") or record.get("_source_file"),
            "sha256": record["sha256"],
            "embedding": to_pgvector(embedding),
        })


def upsert_statute_batch(cur, batch: List[Dict[str, Any]], embeddings: List[List[float]]):
    sql = """
        INSERT INTO statute_chunks (
            id, doc_id, type, "order", act, year, section_no, unit_type,
            title, text, tokens, effective_from, effective_to,
            source_path, sha256, embedding
        )
        VALUES (
            %(id)s, %(doc_id)s, %(type)s, %(order)s, %(act)s, %(year)s, %(section_no)s, %(unit_type)s,
            %(title)s, %(text)s, %(tokens)s, %(effective_from)s, %(effective_to)s,
            %(source_path)s, %(sha256)s, %(embedding)s
        )
        ON CONFLICT (id) DO UPDATE SET
            text = EXCLUDED.text,
            tokens = EXCLUDED.tokens,
            effective_from = EXCLUDED.effective_from,
            effective_to = EXCLUDED.effective_to,
            title = EXCLUDED.title,
            source_path = EXCLUDED.source_path,
            sha256 = EXCLUDED.sha256,
            embedding = EXCLUDED.embedding,
            updated_at = NOW()
    """
    for record, embedding in zip(batch, embeddings):
        params = {
            "id": record["id"],
            "doc_id": record["doc_id"],
            "type": record["type"],
            "order": float(record["order"]),
            "act": record["act"],
            "year": int(record["year"]),
            "section_no": record["section_no"],
            "unit_type": record["unit_type"],
            "title": record.get("title"),
            "text": record["text"],
            "tokens": int(record["tokens"]),
            "effective_from": parse_date(record.get("effective_from")),
            "effective_to": parse_date(record.get("effective_to")),
            "source_path": record.get("source_path") or record.get("_source_file"),
            "sha256": record["sha256"],
            "embedding": to_pgvector(embedding),
        }
        try:
            cur.execute(sql, params)
        except Exception:
            debug_payload = dict(params)
            debug_payload.pop("embedding", None)
            print("Failed statute record:", json.dumps(debug_payload, ensure_ascii=False))
            raise


def process_chunks(
    conn,
    client: OpenAI,
    records: Iterable[Dict[str, Any]],
    upsert_fn,
    label: str,
):
    cur = conn.cursor()
    batch: List[Dict[str, Any]] = []
    processed = 0

    for record in records:
        batch.append(record)
        if len(batch) >= BATCH_SIZE:
            embeddings = embed_batch(client, [item["text"] for item in batch])
            upsert_fn(cur, batch, embeddings)
            conn.commit()
            processed += len(batch)
            print(f"{label}: {processed} chunks embedded", flush=True)
            batch = []

    if batch:
        embeddings = embed_batch(client, [item["text"] for item in batch])
        upsert_fn(cur, batch, embeddings)
        conn.commit()
        processed += len(batch)
        print(f"{label}: {processed} chunks embedded", flush=True)

    cur.close()


def main():
    parser = argparse.ArgumentParser(description="Embed chunk JSONL files into pgvector")
    parser.add_argument("--judgment-dir", default="out/chunks/2020", help="Directory containing judgment JSONL files")
    parser.add_argument("--statute-file", default="out/chunks/BNS/BNS_2023.jsonl", help="Statute JSONL file path")
    args = parser.parse_args()

    config = Config()
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    conn = psycopg2.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        database=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )

    try:
        statute_path = Path(args.statute_file)
        if statute_path.exists():
            print(f"Embedding statute chunks from {statute_path}")
            statute_records = list(chunk_iter([statute_path]))
            process_chunks(conn, client, statute_records, upsert_statute_batch, "Statutes")
        else:
            print(f"Statute file not found: {statute_path}")

        judgment_dir = Path(args.judgment_dir)
        if judgment_dir.exists():
            judgment_files = sorted(judgment_dir.glob("*.jsonl"))
            print(f"Embedding judgments from {len(judgment_files)} files under {judgment_dir}")
            judgment_records = list(chunk_iter(judgment_files))
            process_chunks(conn, client, judgment_records, upsert_judgment_batch, "Judgments")
        else:
            print(f"Judgment directory not found: {judgment_dir}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
