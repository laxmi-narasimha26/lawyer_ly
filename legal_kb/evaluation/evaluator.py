import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import mean, median
from typing import Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from legal_kb.config import Config
from legal_kb.database import connection as db_connection
from legal_kb.database.connection import get_db_manager
from legal_kb.services.embedding_service import EmbeddingService
from legal_kb.services.retrieval_service import RetrievalService

DEFAULT_OUTPUT = PROJECT_ROOT / "out" / "reports" / "evaluation_summary.json"


@dataclass
class QueryEvaluation:
    question: str
    expected_statutes: List[str]
    expected_cases: List[str]
    retrieved_statutes: List[str]
    retrieved_cases: List[str]
    statute_hit_at_3: bool
    statute_hit_at_5: bool
    case_hit_at_5: Optional[bool]
    case_hit_at_8: Optional[bool]
    retrieval_time_ms: float
    notes: List[str]
    statute_hit_ranks: List[int]
    case_hit_ranks: List[int]
    missing_statutes: List[str]
    missing_cases: List[str]


class EvaluationRunner:
    def __init__(self, golden_path: Optional[Path] = None):
        self.golden_path = golden_path or Path(__file__).resolve().parent / "golden_set.json"
        self.config = Config()
        self.embedding_service = EmbeddingService(self.config.OPENAI_API_KEY)
        self.retrieval_service = RetrievalService()

    async def evaluate(
        self,
        statute_k: int = 8,
        case_k: int = 8,
        limit: Optional[int] = None,
        start_index: int = 0,
        print_per_query: bool = False,
    ) -> Dict[str, any]:
        await get_db_manager()
        with open(self.golden_path, "r", encoding="utf-8") as handle:
            dataset = json.load(handle)
        # Apply slicing controls
        if start_index < 0:
            start_index = 0
        if limit is not None and limit > 0:
            dataset = dataset[start_index:start_index + limit]
        elif start_index:
            dataset = dataset[start_index:]

        evaluations: List[QueryEvaluation] = []
        for idx, entry in enumerate(dataset, start=start_index + 1):
            question = entry["question"]
            expected_statutes = entry.get("expected_statutes", [])
            expected_cases = entry.get("expected_cases", [])

            start = time.perf_counter()
            query_embedding = await self.embedding_service.get_embedding(question)
            payload = await self.retrieval_service.search(
                question,
                query_embedding,
                statute_k=statute_k,
                case_k=case_k,
            )
            retrieval_time_ms = (time.perf_counter() - start) * 1000

            statute_ids = [item["id"] for item in payload.get("statutes", [])]
            case_ids = [item["id"] for item in payload.get("cases", [])]

            statute_lookup = {cid: idx for idx, cid in enumerate(statute_ids)}
            case_lookup = {cid: idx for idx, cid in enumerate(case_ids)}

            statute_hit_ranks, missing_statutes = compute_hit_ranks(statute_lookup, expected_statutes)
            case_hit_ranks, missing_cases = compute_hit_ranks(case_lookup, expected_cases)

            hit_at_3 = any(rank <= 3 for rank in statute_hit_ranks) if expected_statutes else True
            hit_at_5 = any(rank <= 5 for rank in statute_hit_ranks) if expected_statutes else True

            case_hit_at_5 = None
            case_hit_at_8 = None
            if expected_cases:
                case_hit_at_5 = any(rank <= 5 for rank in case_hit_ranks)
                case_hit_at_8 = any(rank <= 8 for rank in case_hit_ranks)

            notes: List[str] = []
            if missing_statutes:
                notes.append(f"Missing statute hits: {missing_statutes}")
            if missing_cases:
                notes.append(f"Missing case hits: {missing_cases}")

            evaluations.append(
                QueryEvaluation(
                    question=question,
                    expected_statutes=expected_statutes,
                    expected_cases=expected_cases,
                    retrieved_statutes=statute_ids,
                    retrieved_cases=case_ids,
                    statute_hit_at_3=hit_at_3,
                    statute_hit_at_5=hit_at_5,
                    case_hit_at_5=case_hit_at_5,
                    case_hit_at_8=case_hit_at_8,
                    retrieval_time_ms=retrieval_time_ms,
                    notes=notes,
                    statute_hit_ranks=statute_hit_ranks,
                    case_hit_ranks=case_hit_ranks,
                    missing_statutes=missing_statutes,
                    missing_cases=missing_cases,
                )
            )
            if print_per_query:
                stat_hit5 = "Y" if hit_at_5 else "N"
                case_hit5 = "-" if case_hit_at_5 is None else ("Y" if case_hit_at_5 else "N")
                print(
                    f"[QUERY {idx}] ms={retrieval_time_ms:.1f} | statutes={len(statute_ids)} cases={len(case_ids)} | "
                    f"Stat@5={stat_hit5} | Case@5={case_hit5} | q={question[:120].replace('\n',' ')}"
                )

        summary = aggregate_results(evaluations)
        summary["embed_cache_hits"] = self.embedding_service.cache_hits
        summary["embed_cache_misses"] = self.embedding_service.cache_misses
        summary["embed_cache_bypass"] = getattr(self.embedding_service, "cache_bypass", 0)
        return {"summary": summary, "details": [asdict(ev) for ev in evaluations]}


def compute_hit_ranks(lookup: Dict[str, int], expected_ids: Iterable[str]) -> Tuple[List[int], List[str]]:
    ranks: List[int] = []
    missing: List[str] = []
    for expected in expected_ids:
        if expected in lookup:
            ranks.append(lookup[expected] + 1)  # convert to 1-based index
        else:
            missing.append(expected)
    return ranks, missing


def aggregate_results(evaluations: List[QueryEvaluation]) -> Dict[str, any]:
    count = len(evaluations)
    statute_evals = [ev for ev in evaluations if ev.expected_statutes]
    case_bool_evals = [ev.case_hit_at_5 for ev in evaluations if ev.case_hit_at_5 is not None]
    case_bool_evals_8 = [ev.case_hit_at_8 for ev in evaluations if ev.case_hit_at_8 is not None]

    statute_hit3_rate = (
        sum(ev.statute_hit_at_3 for ev in statute_evals) / len(statute_evals)
        if statute_evals
        else None
    )
    statute_hit5_rate = (
        sum(ev.statute_hit_at_5 for ev in statute_evals) / len(statute_evals)
        if statute_evals
        else None
    )
    case_hit5_rate = sum(case_bool_evals) / len(case_bool_evals) if case_bool_evals else None
    case_hit8_rate = sum(case_bool_evals_8) / len(case_bool_evals_8) if case_bool_evals_8 else None

    retrieval_times = [ev.retrieval_time_ms for ev in evaluations]
    avg_retrieval = mean(retrieval_times) if retrieval_times else 0.0
    med_retrieval = median(retrieval_times) if retrieval_times else 0.0
    p95_retrieval = percentile(retrieval_times, 95) if retrieval_times else 0.0
    max_retrieval = max(retrieval_times) if retrieval_times else 0.0
    min_retrieval = min(retrieval_times) if retrieval_times else 0.0

    statute_expectations = sum(len(ev.expected_statutes) for ev in evaluations)
    case_expectations = sum(len(ev.expected_cases) for ev in evaluations)
    statute_hits = sum(len(ev.statute_hit_ranks) for ev in evaluations)
    case_hits = sum(len(ev.case_hit_ranks) for ev in evaluations)

    statute_recall = (statute_hits / statute_expectations) if statute_expectations else None
    case_recall = (case_hits / case_expectations) if case_expectations else None

    statute_failures = [
        {"question": ev.question, "missing_statutes": ev.missing_statutes}
        for ev in evaluations
        if ev.missing_statutes
    ]
    case_failures = [
        {"question": ev.question, "missing_cases": ev.missing_cases}
        for ev in evaluations
        if ev.missing_cases
    ]

    return {
        "queries": count,
        "statute_hit_at_3": statute_hit3_rate,
        "statute_hit_at_5": statute_hit5_rate,
        "case_hit_at_5": case_hit5_rate,
        "case_hit_at_8": case_hit8_rate,
        "statute_recall": statute_recall,
        "case_recall": case_recall,
        "avg_retrieval_ms": avg_retrieval,
        "median_retrieval_ms": med_retrieval,
        "p95_retrieval_ms": p95_retrieval,
        "max_retrieval_ms": max_retrieval,
        "min_retrieval_ms": min_retrieval,
        "statute_failures": statute_failures,
        "case_failures": case_failures,
    }


def percentile(samples: List[float], pct: float) -> float:
    if not samples:
        return 0.0
    if len(samples) == 1:
        return samples[0]
    samples_sorted = sorted(samples)
    rank = (len(samples_sorted) - 1) * (pct / 100)
    low = int(rank)
    high = min(low + 1, len(samples_sorted) - 1)
    if low == high:
        return samples_sorted[low]
    return samples_sorted[low] + (samples_sorted[high] - samples_sorted[low]) * (rank - low)


async def run_evaluation(
    golden_path: Optional[Path] = None,
    statute_k: int = 8,
    case_k: int = 8,
    limit: Optional[int] = None,
    start_index: int = 0,
    print_per_query: bool = False,
) -> Dict[str, any]:
    runner = EvaluationRunner(golden_path)
    try:
        return await runner.evaluate(
            statute_k=statute_k,
            case_k=case_k,
            limit=limit,
            start_index=start_index,
            print_per_query=print_per_query,
        )
    finally:
        if db_connection.db_manager is not None:
            try:
                await db_connection.db_manager.close()
            finally:
                db_connection.db_manager = None
        client = getattr(runner.embedding_service, "client", None)
        if client and hasattr(client, "close"):
            await client.close()
        if hasattr(runner.embedding_service, "close"):
            runner.embedding_service.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the golden set evaluation suite.")
    parser.add_argument("--golden-path", type=Path, default=None, help="Override path to golden_set.json")
    parser.add_argument("--statute-k", type=int, default=8, help="Top-k statutes to retrieve for evaluation.")
    parser.add_argument("--case-k", type=int, default=8, help="Top-k cases to retrieve for evaluation.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Where to write the evaluation summary.")
    parser.add_argument("--no-details", action="store_true", help="Skip writing per-query details to disk.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of queries to run from the golden set.")
    parser.add_argument("--start-index", type=int, default=0, help="Start index within the golden set (0-based).")
    parser.add_argument(
        "--print-per-query",
        action="store_true",
        help="Print a one-line summary per query with timings and hit flags.",
    )
    return parser.parse_args()


def write_results(results: Dict[str, any], output_path: Path, include_details: bool = True) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": results["summary"]}
    if include_details:
        payload["details"] = results["details"]
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def print_summary(summary: Dict[str, any]) -> None:
    def _fmt_rate(value: Optional[float]) -> str:
        return f"{value:.3f}" if value is not None else "n/a"

    case_rate = summary["case_hit_at_5"]
    case_rate_8 = summary.get("case_hit_at_8")
    print(
        f"Queries={summary['queries']} | Statute@3={_fmt_rate(summary['statute_hit_at_3'])} | "
        f"Statute@5={_fmt_rate(summary['statute_hit_at_5'])} | Case@5={_fmt_rate(case_rate)} | "
        f"Case@8={_fmt_rate(case_rate_8)}"
    )
    print(
        "Retrieval ms -> "
        f"avg={summary['avg_retrieval_ms']:.1f} | median={summary['median_retrieval_ms']:.1f} | "
        f"p95={summary['p95_retrieval_ms']:.1f} | max={summary['max_retrieval_ms']:.1f}"
    )
    print(
        "embed_cache: hits={h} | misses={m} | bypass={b}".format(
            h=summary.get("embed_cache_hits", 0),
            m=summary.get("embed_cache_misses", 0),
            b=summary.get("embed_cache_bypass", 0),
        )
    )


if __name__ == "__main__":
    args = parse_args()
    results = asyncio.run(
        run_evaluation(
            golden_path=args.golden_path,
            statute_k=args.statute_k,
            case_k=args.case_k,
            limit=args.limit,
            start_index=args.start_index,
            print_per_query=args.print_per_query,
        )
    )
    write_results(results, args.output, include_details=not args.no_details)
    print(f"Evaluation complete. Summary written to {args.output}")
    print_summary(results["summary"])
