"""Stage 5: transparent heuristic ranker (T-004).

score = 45*tone_evidence + 25*length_fit + 20*brand_similarity + 10 base
        - 15 per warning badge
All components normalized to [0,1]; the breakdown is stored and shown in the UI.
"""
import re

W_TONE = 45
W_LENGTH = 25
W_BRAND = 20
BASE = 10
WARN_PENALTY = 15

IDEAL_MIN, IDEAL_MAX = 30, 45  # chars; peak of the length-fit curve
LENGTH_FALLOFF = 40            # chars from the ideal zone edge to score 0


def tone_evidence(tone: str, tone_stats: dict) -> float:
    """Candidate tone's mean open rate, normalized against the best tone in the matched set."""
    if not tone_stats:
        return 0.5  # no history: neutral prior
    best = max(s["mean_open_rate"] for s in tone_stats.values())
    if best <= 0:
        return 0.5
    stat = tone_stats.get(tone)
    if stat is None:
        return 0.35  # tone unseen for this context: mild penalty vs evidence-backed tones
    return max(0.0, min(1.0, stat["mean_open_rate"] / best))


def length_fit(text: str) -> float:
    n = len(text)
    if IDEAL_MIN <= n <= IDEAL_MAX:
        return 1.0
    dist = (IDEAL_MIN - n) if n < IDEAL_MIN else (n - IDEAL_MAX)
    return max(0.0, 1.0 - dist / LENGTH_FALLOFF)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z']+", text.lower()))


def brand_similarity(text: str, exemplars: list[str]) -> float:
    """Best Jaccard token overlap with any exemplar, scaled: 0.30 overlap => 1.0.

    Measures stylistic kinship, not copying — capped so near-duplicates gain
    nothing extra over comfortable family resemblance.
    """
    cand = _tokens(text)
    if not cand or not exemplars:
        return 0.5
    best = 0.0
    for ex in exemplars:
        ext = _tokens(ex)
        if not ext:
            continue
        j = len(cand & ext) / len(cand | ext)
        best = max(best, j)
    return min(1.0, best / 0.30)


def score_candidate(text: str, tone: str, tone_stats: dict,
                    exemplars: list[str], badges: list[dict]) -> tuple[float, dict]:
    t = tone_evidence(tone, tone_stats)
    l = length_fit(text)
    b = brand_similarity(text, exemplars)
    warns = sum(1 for badge in badges if badge["level"] == "warn")
    raw = W_TONE * t + W_LENGTH * l + W_BRAND * b + BASE - WARN_PENALTY * warns
    score = round(max(0.0, min(100.0, raw)), 1)
    breakdown = {
        "tone_evidence": {"points": round(W_TONE * t, 1), "max": W_TONE},
        "length_fit": {"points": round(W_LENGTH * l, 1), "max": W_LENGTH},
        "brand_similarity": {"points": round(W_BRAND * b, 1), "max": W_BRAND},
        "base": {"points": BASE, "max": BASE},
        "guardrail_penalty": {"points": -WARN_PENALTY * warns, "max": 0},
    }
    return score, breakdown
