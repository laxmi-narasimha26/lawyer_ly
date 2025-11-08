from typing import List, Dict

class CitationValidator:
    def validate(self, citations: List[str], context_map: Dict[str, str]) -> Dict[str, List[str]]:
        missing = [cid for cid in citations if cid not in context_map]
        return {
            "missing": missing,
            "valid": [cid for cid in citations if cid in context_map],
        }
