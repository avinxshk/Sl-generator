"""Stage 1: assemble the grounding context for one campaign x segment."""
import json
from collections import Counter

from . import db
from .taxonomy import size_band

BODY_WORD_LIMIT = 150  # T-011: truncate instead of summarizing


def segment_profile(conn, segment_id: int) -> dict:
    seg = conn.execute("SELECT * FROM segments WHERE id=?", (segment_id,)).fetchone()
    if seg is None:
        raise KeyError(f"segment {segment_id} not found")
    rows = conn.execute("SELECT * FROM customers WHERE segment_id=?", (segment_id,)).fetchall()
    product_counts: Counter = Counter()
    opens = clicks = recency = 0
    for r in rows:
        product_counts.update(json.loads(r["products_json"]))
        opens += r["opens_90d"]
        clicks += r["clicks_90d"]
        recency += r["last_open_days"] or 0
    n = max(1, len(rows))
    top_products = [
        {"product": p, "share": round(c / n, 2)} for p, c in product_counts.most_common(3)
    ]
    return {
        "id": seg["id"],
        "name": seg["name"],
        "description": seg["description"],
        "size": seg["size"],
        "size_band": size_band(seg["size"]),
        "traits": json.loads(seg["traits_json"]),
        "top_products": top_products,
        "avg_opens_90d": round(opens / n, 1),
        "avg_clicks_90d": round(clicks / n, 1),
        "avg_days_since_open": round(recency / n, 1),
    }


def brand_voice(conn) -> dict:
    row = conn.execute("SELECT * FROM brand_voice WHERE id=1").fetchone()
    return db.row_to_dict(row)


def body_summary(body: str) -> str:
    words = body.split()
    if len(words) <= BODY_WORD_LIMIT:
        return body.strip()
    return " ".join(words[:BODY_WORD_LIMIT]) + " …"


def build_context(conn, campaign: dict, segment_id: int) -> dict:
    return {
        "intent": campaign["intent"],
        "body_summary": body_summary(campaign["body"]),
        "segment": segment_profile(conn, segment_id),
        "brand": brand_voice(conn),
    }
