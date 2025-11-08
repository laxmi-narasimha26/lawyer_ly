from dataclasses import dataclass, field
from typing import List
from datetime import datetime

@dataclass
class PerformanceMetrics:
    retrieval_time_ms: float
    context_build_time_ms: float
    llm_time_ms: float
    verified: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PerformanceMonitor:
    def __init__(self):
        self.records: List[PerformanceMetrics] = []

    def record(self, metrics: PerformanceMetrics) -> None:
        self.records.append(metrics)

    def summary(self) -> dict:
        if not self.records:
            return {"count": 0}
        count = len(self.records)
        avg_retrieval = sum(m.retrieval_time_ms for m in self.records) / count
        avg_context = sum(m.context_build_time_ms for m in self.records) / count
        avg_llm = sum(m.llm_time_ms for m in self.records) / count
        verified_ratio = sum(1 for m in self.records if m.verified) / count
        return {
            "count": count,
            "avg_retrieval_ms": avg_retrieval,
            "avg_context_ms": avg_context,
            "avg_llm_ms": avg_llm,
            "verified_ratio": verified_ratio,
        }
