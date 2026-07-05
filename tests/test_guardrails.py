from app import guardrails as g


def codes(badges):
    return {b["code"] for b in badges}


def test_clean_line_passes():
    assert g.run_guardrails("Your March picks are in", []) == []


def test_length_warn_and_block():
    warn = g.check_length("x" * 60)
    assert warn["level"] == "warn" and warn["code"] == "truncation"
    block = g.check_length("x" * 95)
    assert block["level"] == "block"
    assert g.check_length("x" * 40) is None


def test_spam_words_escalate():
    one = g.run_guardrails("Act now for spring savings", [])
    assert codes(one) == {"spam_word"} and one[0]["level"] == "warn"
    two = g.run_guardrails("Act now, click here for savings", [])
    assert any(b["code"] == "spam_words" and b["level"] == "block" for b in two)


def test_caps_ratio():
    assert g.check_caps("HUGE SALE today for you") is not None
    assert g.check_caps("Huge sale today for you") is None
    assert g.check_caps("123 456!") is None  # no letters: no division by zero


def test_punctuation():
    assert g.check_punctuation("Really?! Are you sure?!")["level"] == "warn"
    assert g.check_punctuation("One question? Fine.") is None


def test_banned_terms_block_case_insensitive():
    badges = g.run_guardrails("A Risk-Free month on us", ["risk-free"])
    assert any(b["code"] == "banned_term" and b["level"] == "block" for b in badges)
    assert g.is_blocked(badges)


def test_is_blocked_false_for_warnings_only():
    assert not g.is_blocked([{"level": "warn", "code": "x", "message": ""}])
