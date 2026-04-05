import re
from enum import Enum


class Complexity(Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


SIMPLE_PATTERNS = [
    r"^(what|how|why|when|where|who)\b",
    r"^(explain|describe|tell me|show me|list)\b",
    r"\?$",
]

COMPLEX_SIGNALS = [
    r"\b(implement|create|build|write|add|make|develop)\b",
    r"\b(refactor|rewrite|migrate|convert|transform)\b",
    r"\b(fix|debug|solve|resolve)\b",
    r"\b(multiple|several|all|every|each)\b",
    r"\b(tests?|spec|unittest|pytest)\b",
    r"\b(and then|also|additionally|furthermore)\b",
    r"\b(feature|system|module|component|service|class)\b",
    r"\bstep\s+\d+|\d+\.",
]


def detect_complexity(prompt: str) -> Complexity:
    lower = prompt.lower().strip()
    words = lower.split()

    # Short questions → simple
    if len(words) <= 10:
        for pattern in SIMPLE_PATTERNS:
            if re.search(pattern, lower):
                return Complexity.SIMPLE

    # Two or more complex signals → complex
    signal_count = sum(1 for p in COMPLEX_SIGNALS if re.search(p, lower))
    if signal_count >= 2:
        return Complexity.COMPLEX

    # Long prompts → complex
    if len(words) > 25:
        return Complexity.COMPLEX

    return Complexity.SIMPLE
