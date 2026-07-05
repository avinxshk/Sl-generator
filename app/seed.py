"""Synthetic seed data: segments, customers, historical campaigns, brand voice.

Deterministic (fixed random seed) so demos and tests are reproducible.
Open-rate patterns are deliberately opinionated so retrieval and ranking have
signal to find: curiosity wins for winback, urgency wins for promotional, etc.
"""
import json
import random
from datetime import date, timedelta

from . import db

SEGMENTS = [
    (1, "Loyal high-spenders", "Frequent buyers, top 10% lifetime value, open most emails.",
     4200, ["high LTV", "engaged", "brand loyal"]),
    (2, "Lapsed 90-day", "No email open or purchase in 90+ days.",
     2340, ["dormant", "churn risk", "price sensitive"]),
    (3, "New signups", "Joined in the last 30 days, little purchase history.",
     8700, ["new", "exploring", "high curiosity"]),
    (4, "Bargain hunters", "Buy mostly on discount, open promos, ignore newsletters.",
     18500, ["deal seeking", "promo responsive"]),
    (5, "Enterprise accounts", "B2B contacts on team plans.",
     31200, ["B2B", "feature focused", "multiple stakeholders"]),
]

PRODUCTS = ["Basic plan", "Pro plan", "Team plan", "Storage add-on", "Analytics add-on"]

# (intent, tone) -> mean open rate %. Unlisted pairs fall back to 18.
TONE_PRIORS = {
    ("promotional", "urgency"): 34, ("promotional", "benefit_led"): 27,
    ("promotional", "curiosity"): 22, ("promotional", "plain_informative"): 15,
    ("winback", "curiosity"): 31, ("winback", "personal"): 27,
    ("winback", "urgency"): 17, ("winback", "plain_informative"): 13,
    ("newsletter", "plain_informative"): 24, ("newsletter", "curiosity"): 26,
    ("newsletter", "urgency"): 12,
    ("product_announcement", "benefit_led"): 29, ("product_announcement", "curiosity"): 25,
    ("product_announcement", "social_proof"): 22,
    ("transactional_upsell", "benefit_led"): 26, ("transactional_upsell", "personal"): 23,
    ("event_invite", "urgency"): 25, ("event_invite", "social_proof"): 27,
    ("event_invite", "personal"): 21,
}

SUBJECT_TEMPLATES = {
    "promotional": ["Last day: {n}% off everything", "Your {n}% code expires tonight",
                    "{n}% off - because you earned it", "The sale ends when the clock does",
                    "Weekend deal: {n}% off Pro"],
    "winback": ["We kept your favorites safe", "Did we do something wrong?",
                "It's been a while - here's what changed", "Your account misses you",
                "Come back to a better {p}"],
    "newsletter": ["5 things worth reading this week", "The March roundup is here",
                   "What our team shipped in June", "Inside: the feature you asked for"],
    "product_announcement": ["Meet the new {p}", "{p} just got a major upgrade",
                             "You asked. We built it.", "Now live: {p} for everyone"],
    "transactional_upsell": ["Your {p} is working hard - give it help",
                             "Unlock more from your {p}", "One upgrade, twice the room"],
    "event_invite": ["You're invited: live session Thursday", "Save your seat - 200 already in",
                     "Join us for the summer launch event"],
}

BRAND_VOICE = {
    "guidelines": (
        "Friendly, direct, lightly witty. Write like a helpful colleague, not a "
        "salesperson. Prefer concrete specifics over hype. Sentence case, no "
        "exclamation stacking, at most one emoji and only when it adds meaning. "
        "Never manufacture urgency that the email body cannot back up."
    ),
    "banned_terms": ["guarantee", "risk-free", "act now", "limited time only", "100% free"],
    "exemplars": [
        "Your March picks are in",
        "A little something for our regulars",
        "The feature you kept asking about is live",
        "We saved you a seat (and a discount)",
        "Skip the line on Thursday",
    ],
}


def seed(db_path: str | None = None, n_customers: int = 200, n_history: int = 60) -> None:
    rng = random.Random(42)
    db.init_db(db_path)
    conn = db.get_conn(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM segments")
    if cur.fetchone()[0]:
        conn.close()
        return  # already seeded

    for sid, name, desc, size, traits in SEGMENTS:
        cur.execute(
            "INSERT INTO segments (id, name, description, size, traits_json) VALUES (?,?,?,?,?)",
            (sid, name, desc, size, json.dumps(traits)),
        )

    # Customers: engagement profile follows the segment's character.
    profiles = {1: (18, 7, 3), 2: (1, 0, 120), 3: (8, 3, 6), 4: (10, 4, 12), 5: (6, 2, 15)}
    for i in range(n_customers):
        sid = rng.choice([s[0] for s in SEGMENTS])
        opens, clicks, recency = profiles[sid]
        products = rng.sample(PRODUCTS, k=rng.randint(1, 3))
        cur.execute(
            "INSERT INTO customers (segment_id, products_json, opens_90d, clicks_90d, last_open_days)"
            " VALUES (?,?,?,?,?)",
            (sid, json.dumps(products),
             max(0, opens + rng.randint(-3, 3)),
             max(0, clicks + rng.randint(-2, 2)),
             max(0, recency + rng.randint(-5, 15))),
        )

    # Historical campaigns with intent/tone open-rate signal.
    pairs = list(TONE_PRIORS.items())
    start = date(2025, 1, 6)
    for i in range(n_history):
        (intent, tone), mean = pairs[i % len(pairs)]
        seg = rng.choice(SEGMENTS)
        template = rng.choice(SUBJECT_TEMPLATES[intent])
        subject = template.format(n=rng.choice([15, 20, 25, 30]), p=rng.choice(PRODUCTS))
        open_rate = round(max(2.0, rng.gauss(mean, 4.0)), 1)
        audience = int(seg[3] * rng.uniform(0.5, 1.0))
        sent = (start + timedelta(days=rng.randint(0, 500))).isoformat()
        cur.execute(
            "INSERT INTO historical_campaigns"
            " (subject_line, intent, tone, audience_size, open_rate, segment_id, sent_at, source)"
            " VALUES (?,?,?,?,?,?,?, 'seed')",
            (subject, intent, tone, audience, open_rate, seg[0], sent),
        )

    cur.execute(
        "INSERT INTO brand_voice (id, guidelines, banned_terms_json, exemplars_json) VALUES (1,?,?,?)",
        (BRAND_VOICE["guidelines"], json.dumps(BRAND_VOICE["banned_terms"]),
         json.dumps(BRAND_VOICE["exemplars"])),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed()
    print(f"Seeded database at {db.DB_PATH}")
