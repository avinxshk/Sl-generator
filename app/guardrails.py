"""Stage 4: deterministic guardrail linter (T-006, FR-6..FR-9).

Each check returns None (pass) or a badge dict {level, code, message}.
level: 'warn' shows a badge; 'block' removes the candidate from display.
"""
import re

WARN_LENGTH = 55
BLOCK_LENGTH = 90
CAPS_RATIO = 0.30
MAX_EXCLAIM = 2

SPAM_WORDS = [
    "free!!!", "act now", "buy now", "click here", "winner", "cash bonus",
    "no obligation", "urgent", "once in a lifetime", "$$$", "100% free",
    "risk-free", "guaranteed", "limited time only",
]


def check_length(text: str) -> dict | None:
    n = len(text)
    if n > BLOCK_LENGTH:
        return {"level": "block", "code": "too_long",
                "message": f"{n} chars — exceeds {BLOCK_LENGTH} char limit"}
    if n > WARN_LENGTH:
        return {"level": "warn", "code": "truncation",
                "message": f"{n} chars — may truncate on mobile (>{WARN_LENGTH})"}
    return None


def check_spam_words(text: str) -> dict | None:
    lower = text.lower()
    hits = [w for w in SPAM_WORDS if w in lower]
    if len(hits) >= 2:
        return {"level": "block", "code": "spam_words",
                "message": f"spam triggers: {', '.join(hits)}"}
    if hits:
        return {"level": "warn", "code": "spam_word",
                "message": f"possible spam trigger: '{hits[0]}'"}
    return None


def check_caps(text: str) -> dict | None:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if ratio > CAPS_RATIO:
        return {"level": "warn", "code": "all_caps",
                "message": f"{int(ratio * 100)}% uppercase letters"}
    return None


def check_punctuation(text: str) -> dict | None:
    count = len(re.findall(r"[!?]", text))
    if count > MAX_EXCLAIM:
        return {"level": "warn", "code": "punctuation",
                "message": f"{count} exclamation/question marks"}
    return None


def check_banned_terms(text: str, banned_terms: list[str]) -> dict | None:
    lower = text.lower()
    hits = [t for t in banned_terms if t.lower() in lower]
    if hits:
        return {"level": "block", "code": "banned_term",
                "message": f"brand banned term: '{hits[0]}'"}
    return None


def run_guardrails(text: str, banned_terms: list[str]) -> list[dict]:
    """Run all checks; returns the list of badges (possibly empty)."""
    checks = [
        check_length(text),
        check_spam_words(text),
        check_caps(text),
        check_punctuation(text),
        check_banned_terms(text, banned_terms),
    ]
    return [b for b in checks if b]


def is_blocked(badges: list[dict]) -> bool:
    return any(b["level"] == "block" for b in badges)
