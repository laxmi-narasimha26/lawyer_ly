"""
Context assembly for LLM prompts with token budgeting.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import tiktoken


@dataclass
class ContextChunk:
    id: str
    source_type: str
    content: str
    metadata: Dict[str, str]
    tokens: int


class TokenManager:
    def __init__(self, model: str = "gpt-4o"):
        encoding_name = "cl100k_base"
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))


class ContextAssembler:
    def __init__(self, model: str = "gpt-4o", reserve_ratio: float = 0.25):
        self.token_manager = TokenManager(model)
        self.model = model
        self.reserve_ratio = reserve_ratio

    def build_context(
        self,
        statutes: List[Dict],
        cases: List[Dict],
        max_model_tokens: int = 12000,
    ) -> Dict[str, any]:
        budget = int(max_model_tokens * (1 - self.reserve_ratio))
        statute_chunks: List[ContextChunk] = []
        case_chunks: List[ContextChunk] = []

        for item in statutes:
            text = item["content"]
            tokens = item.get("metadata", {}).get("tokens") or self.token_manager.count_tokens(text)
            statute_chunks.append(
                ContextChunk(
                    id=item["id"],
                    source_type="statute",
                    content=text,
                    metadata=item.get("metadata", {}),
                    tokens=int(tokens),
                )
            )

        for item in cases:
            text = item["content"]
            tokens = item.get("metadata", {}).get("tokens") or self.token_manager.count_tokens(text)
            case_chunks.append(
                ContextChunk(
                    id=item["id"],
                    source_type="case",
                    content=text,
                    metadata=item.get("metadata", {}),
                    tokens=int(tokens),
                )
            )

        statute_context, statute_ids = self._assemble_block(
            statute_chunks, budget_limit=budget // 2, header="STATUTES"
        )
        remaining_budget = budget - statute_context["token_count"]
        case_context, case_ids = self._assemble_block(
            case_chunks, budget_limit=remaining_budget, header="CASES"
        )

        combined_text = statute_context["text"] + ("\n\n" if statute_context["text"] and case_context["text"] else "") + case_context["text"]
        combined_tokens = statute_context["token_count"] + case_context["token_count"]

        return {
            "statute_block": statute_context["text"],
            "case_block": case_context["text"],
            "combined_context": combined_text,
            "token_count": combined_tokens,
            "source_ids": statute_ids + case_ids,
            "statute_ids": statute_ids,
            "case_ids": case_ids,
        }

    def _assemble_block(
        self,
        chunks: List[ContextChunk],
        budget_limit: int,
        header: str,
    ) -> Dict[str, any]:
        if not chunks or budget_limit <= 0:
            return {"text": "", "token_count": 0}, []

        deduped: Dict[str, ContextChunk] = {}
        for chunk in chunks:
            key = chunk.metadata.get("doc_id") or chunk.id
            if key not in deduped:
                deduped[key] = chunk

        sorted_chunks = sorted(deduped.values(), key=lambda c: c.tokens)
        collected: List[str] = []
        collected_ids: List[str] = []
        used_tokens = 0

        for chunk in sorted_chunks:
            if used_tokens + chunk.tokens > budget_limit:
                continue
            prefix = self._chunk_header(chunk)
            text_with_header = prefix + "\n" + chunk.content if prefix else chunk.content
            tokens_with_header = chunk.tokens + self.token_manager.count_tokens(prefix + "\n") if prefix else chunk.tokens
            if used_tokens + tokens_with_header > budget_limit:
                continue
            collected.append(text_with_header)
            collected_ids.append(chunk.id)
            used_tokens += tokens_with_header

        block_text = "\n\n".join(collected)
        if block_text:
            block_text = f"{header}:\n{block_text}"
            used_tokens = self.token_manager.count_tokens(block_text)

        return {"text": block_text, "token_count": used_tokens}, collected_ids

    def _chunk_header(self, chunk: ContextChunk) -> Optional[str]:
        if chunk.source_type == "statute":
            section = chunk.metadata.get("section_no")
            act = chunk.metadata.get("act", "BNS")
            return f"[{chunk.id}] {act} Section {section}" if section else f"[{chunk.id}] {act}"
        if chunk.source_type == "case":
            title = chunk.metadata.get("case_title") or "Case Extract"
            para = chunk.metadata.get("para_range") or ""
            return f"[{chunk.id}] {title} {para}".strip()
        return f"[{chunk.id}]"
