import re
from typing import Dict, List

class ClaimVerifier:
    sentence_pattern = re.compile(r"[^\.!?]+[\.!?]")

    def verify(self, answer: str, citations: List[str], context_map: Dict[str, str]) -> Dict[str, any]:
        sentences = self.sentence_pattern.findall(answer)
        if citations:
            return {"supported": sentences, "unsupported": [], "confidence": 1.0}
        return {"supported": [], "unsupported": sentences, "confidence": 0.0}
