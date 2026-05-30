"""Input sanitization and security utilities."""

import re
import unicodedata
import html


class FeedSanitizer:
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous|above)\s+instructions",
        r"(?i)forget\s+(about\s+)?your\s+(instructions|prompt|system)",
        r"(?i)(new\s+)?system\s+prompt",
        r"(?i)you\s+are\s+(now|not)\s+",
        r"(?i)override\s+(mode|instructions|settings)",
        r"(?i)output\s+your\s+(prompt|instructions|system)",
    ]

    @staticmethod
    def sanitize_body(body: str) -> str:
        body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)
        body = re.sub(r'<iframe[^>]*>.*?</iframe>', '', body, flags=re.DOTALL)
        body = re.sub(r'[\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064]', '', body)
        body = unicodedata.normalize('NFKC', body)
        if len(body) > 100000:
            body = body[:100000]
        return body

    @staticmethod
    def check_injection(text: str) -> bool:
        for pattern in FeedSanitizer.INJECTION_PATTERNS:
            if re.search(pattern, text):
                return True
        return False
