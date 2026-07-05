"""Fixed taxonomies shared across the pipeline (PRD section 4, FR-2)."""

INTENTS = [
    "promotional",
    "newsletter",
    "product_announcement",
    "winback",
    "transactional_upsell",
    "event_invite",
]

TONES = [
    "urgency",
    "curiosity",
    "benefit_led",
    "personal",
    "social_proof",
    "plain_informative",
]

# Audience size bands used by retrieval and ranking (architecture section 3.2)
def size_band(size: int) -> str:
    if size < 5000:
        return "<5k"
    if size <= 25000:
        return "5-25k"
    return ">25k"
