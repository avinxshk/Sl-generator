"""Stage 2: transparent tag-based retrieval over historical campaigns (T-010).

similarity = 3*(intent match) + 1*(size band match) + 1*(exact segment match)
Returns positive exemplars (top open rates among most similar), negative
exemplars (worst open rates among similar), and per-tone performance stats
for the matched set. Every item carries a human-readable match_reason.
"""
from .taxonomy import size_band

TOP_K = 5
BOTTOM_K = 2


def _similarity(row, intent: str, seg_band: str, segment_id: int) -> int:
    score = 0
    if row["intent"] == intent:
        score += 3
    if size_band(row["audience_size"]) == seg_band:
        score += 1
    if row["segment_id"] == segment_id:
        score += 1
    return score


def _match_reason(row, intent: str, seg_band: str, segment_id: int) -> str:
    parts = []
    if row["intent"] == intent:
        parts.append("same intent")
    if size_band(row["audience_size"]) == seg_band:
        parts.append("same audience-size band")
    if row["segment_id"] == segment_id:
        parts.append("same segment")
    return " · ".join(parts) if parts else "weak match"


def retrieve(conn, intent: str, segment: dict) -> dict:
    seg_band = segment["size_band"]
    seg_id = segment["id"]
    rows = conn.execute("SELECT * FROM historical_campaigns").fetchall()

    scored = []
    for row in rows:
        sim = _similarity(row, intent, seg_band, seg_id)
        if sim > 0:
            scored.append((sim, row))

    def item(sim, row):
        return {
            "subject_line": row["subject_line"],
            "intent": row["intent"],
            "tone": row["tone"],
            "audience_size": row["audience_size"],
            "open_rate": row["open_rate"],
            "similarity": sim,
            "match_reason": _match_reason(row, intent, seg_band, seg_id),
        }

    positives = [item(s, r) for s, r in
                 sorted(scored, key=lambda x: (x[0], x[1]["open_rate"]), reverse=True)[:TOP_K]]
    negatives = [item(s, r) for s, r in
                 sorted(scored, key=lambda x: (-x[0], x[1]["open_rate"]))[:BOTTOM_K]]

    # Tone performance over the full matched set (not just top/bottom).
    tone_sums: dict[str, list[float]] = {}
    for _, row in scored:
        tone_sums.setdefault(row["tone"], []).append(row["open_rate"])
    tone_stats = {
        tone: {"mean_open_rate": round(sum(v) / len(v), 1), "n": len(v)}
        for tone, v in tone_sums.items()
    }

    return {"positives": positives, "negatives": negatives, "tone_stats": tone_stats}
