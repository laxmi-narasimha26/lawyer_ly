"""
Standalone token manager helper.
"""
import tiktoken


class TokenManager:
    def __init__(self, model: str = "gpt-4o"):
        if model in {"gpt-4o", "gpt-4.1", "gpt-4o-mini"}:
            encoding_name = "o200k_base"
        else:
            encoding_name = "cl100k_base"
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text))
