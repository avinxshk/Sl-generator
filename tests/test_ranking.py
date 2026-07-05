from app import ranking

TONE_STATS = {
    "curiosity": {"mean_open_rate": 31.0, "n": 6},
    "urgency": {"mean_open_rate": 17.0, "n": 4},
}
EXEMPLARS = ["Your March picks are in", "We saved you a seat (and a discount)"]


def test_tone_evidence_prefers_winning_tone():
    assert ranking.tone_evidence("curiosity", TONE_STATS) > ranking.tone_evidence("urgency", TONE_STATS)


def test_tone_evidence_neutral_without_history():
    assert ranking.tone_evidence("curiosity", {}) == 0.5


def test_unseen_tone_gets_mild_penalty():
    assert ranking.tone_evidence("social_proof", TONE_STATS) == 0.35


def test_length_fit_peaks_in_ideal_zone():
    assert ranking.length_fit("x" * 35) == 1.0
    assert ranking.length_fit("x" * 35) > ranking.length_fit("x" * 60) > ranking.length_fit("x" * 85)


def test_score_bounds_and_breakdown():
    score, bd = ranking.score_candidate(
        "We kept your favorites safe", "curiosity", TONE_STATS, EXEMPLARS, [])
    assert 0 <= score <= 100
    total = sum(v["points"] for v in bd.values())
    assert abs(total - score) < 0.11  # breakdown adds up (rounding tolerance)


def test_warning_penalty_lowers_score():
    hi, _ = ranking.score_candidate("Steady line here", "curiosity", TONE_STATS, EXEMPLARS, [])
    lo, bd = ranking.score_candidate("Steady line here", "curiosity", TONE_STATS, EXEMPLARS,
                                     [{"level": "warn", "code": "x", "message": ""}])
    assert hi - lo == ranking.WARN_PENALTY
    assert bd["guardrail_penalty"]["points"] == -ranking.WARN_PENALTY


def test_ranking_orders_evidence_backed_tone_first():
    a, _ = ranking.score_candidate("A lot changed since you left", "curiosity", TONE_STATS, EXEMPLARS, [])
    b, _ = ranking.score_candidate("A lot changed since you left", "urgency", TONE_STATS, EXEMPLARS, [])
    assert a > b
