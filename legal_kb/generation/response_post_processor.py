import re
from typing import Dict, List

class ResponsePostProcessor:
    citation_pattern = re.compile(r"\[cite:([^\]]+)\]")

    def extract_citations(self, answer: str) -> List[str]:
        return list(dict.fromkeys(self.citation_pattern.findall(answer)))

    def validate_citations(self, answer: str, allowed_ids: List[str]) -> Dict[str, List[str]]:
        citations = self.extract_citations(answer)
        invalid = [cid for cid in citations if cid not in allowed_ids]
        valid = [cid for cid in citations if cid in allowed_ids]
        cleaned_answer = answer
        for cid in invalid:
            cleaned_answer = cleaned_answer.replace(f"[cite:{cid}]", "")
        return {"answer": cleaned_answer.strip(), "citations": valid, "invalid": invalid}

    def format_response(self, answer: str, citations: List[str]) -> str:
        if not citations:
            return answer
        citation_block = "\n\nCitations:\n" + "\n".join([f"- [cite:{cid}]" for cid in citations])
        return answer + citation_block
