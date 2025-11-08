from dataclasses import dataclass
from typing import Dict

@dataclass
class PromptMessages:
    system: str
    user: str
    temperature: float
    metadata: Dict[str, str]


class PromptBuilder:
    """Constructs prompts for answer generation."""

    def __init__(self):
        self.base_system_prompt = (
            "You are a senior Indian legal analyst. Always ground answers strictly in the provided context. "
            "For every material assertion, cite the supporting source using the format [cite:SOURCE_ID]. "
            "Do not invent facts outside the context. If the context is insufficient, say so explicitly."
        )

    def build(self, query: str, analysis: Dict, context_payload: Dict) -> PromptMessages:
        query_type = analysis.get("query_type", "factual")
        temperature = 0.2 if query_type == "factual" else 0.5 if query_type == "comparative" else 0.3

        source_ids = context_payload.get("source_ids", [])
        source_note = "Source IDs available: " + ", ".join(source_ids) if source_ids else ""

        statute_block = context_payload.get("statute_block", "")
        case_block = context_payload.get("case_block", "")
        context_text = "\n\n".join([block for block in [statute_block, case_block] if block])

        instructions = (
            "Answer with clear structure. Use headings where appropriate. Include a short conclusion and list citations as [cite:SOURCE_ID]."
        )

        user_prompt = (
            f"Question: {query}\n"
            f"{source_note}\n"
            "---\n"
            f"{context_text}\n"
            "---\n"
            f"{instructions}"
        )

        metadata = {
            "query_type": query_type,
            "section_guesses": ",".join(analysis.get("section_guesses", [])),
        }

        return PromptMessages(
            system=self.base_system_prompt,
            user=user_prompt,
            temperature=temperature,
            metadata=metadata,
        )
