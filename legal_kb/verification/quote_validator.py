import re
from typing import Dict

class QuoteValidator:
    quote_pattern = re.compile(r'"([^"\n]{10,400})"')

    def validate(self, answer: str, context_map: Dict[str, str]) -> Dict[str, list[str]]:
        quotes = self.quote_pattern.findall(answer)
        missing = []
        for quote in quotes:
            normalized = " ".join(quote.split())
            if not any(normalized in " ".join(text.split()) for text in context_map.values()):
                missing.append(quote)
        return {"quotes": quotes, "missing": missing}
