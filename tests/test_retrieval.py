import pytest

from app import db, retrieval, seed
from app.context import segment_profile


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    path = str(tmp_path / "r.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    seed.seed(path)
    c = db.get_conn(path)
    yield c
    c.close()


def test_intent_match_dominates(conn):
    seg = segment_profile(conn, 2)  # Lapsed 90-day
    out = retrieval.retrieve(conn, "winback", seg)
    assert len(out["positives"]) == retrieval.TOP_K
    assert all(p["intent"] == "winback" for p in out["positives"])
    assert all("same intent" in p["match_reason"] for p in out["positives"])


def test_positives_sorted_by_open_rate_within_similarity(conn):
    seg = segment_profile(conn, 2)
    out = retrieval.retrieve(conn, "winback", seg)
    sims = [p["similarity"] for p in out["positives"]]
    assert sims == sorted(sims, reverse=True)
    top_sim = [p for p in out["positives"] if p["similarity"] == sims[0]]
    rates = [p["open_rate"] for p in top_sim]
    assert rates == sorted(rates, reverse=True)


def test_negatives_are_low_performers(conn):
    seg = segment_profile(conn, 2)
    out = retrieval.retrieve(conn, "winback", seg)
    pos_rates = [p["open_rate"] for p in out["positives"]]
    neg_rates = [n["open_rate"] for n in out["negatives"]]
    assert max(neg_rates) < max(pos_rates)


def test_tone_stats_reflect_seed_signal(conn):
    # Seed priors: curiosity (31) beats urgency (17) for winback.
    seg = segment_profile(conn, 2)
    stats = retrieval.retrieve(conn, "winback", seg)["tone_stats"]
    assert stats["curiosity"]["mean_open_rate"] > stats["urgency"]["mean_open_rate"]


def test_new_outcome_enters_corpus(conn):
    seg = segment_profile(conn, 2)
    conn.execute(
        "INSERT INTO historical_campaigns (subject_line, intent, tone, audience_size,"
        " open_rate, segment_id, source) VALUES ('Fresh app line', 'winback', 'personal',"
        " 2340, 99.0, 2, 'app')")
    conn.commit()
    out = retrieval.retrieve(conn, "winback", seg)
    assert out["positives"][0]["subject_line"] == "Fresh app line"
