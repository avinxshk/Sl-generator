"""FastAPI app: REST API + static SPA serving."""
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import context as ctx
from . import db, generator, guardrails, ranking, retrieval, seed
from .taxonomy import INTENTS, TONES

MAX_ACCEPTED = 2  # A/B limit (T-008)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")

@asynccontextmanager
async def _lifespan(app: FastAPI):
    seed.seed()
    yield


app = FastAPI(title="SL Generator", lifespan=_lifespan)


# ------------------------------------------------------------- request models
class CampaignIn(BaseModel):
    name: str = Field(min_length=1)
    intent: str
    body: str = Field(min_length=1)
    segment_ids: list[int] = Field(min_length=1)


class StatusIn(BaseModel):
    status: str  # accepted | edited | rejected | proposed
    edited_text: str | None = None


class OutcomeResult(BaseModel):
    candidate_id: int
    open_rate: float = Field(ge=0, le=100)
    variant: str | None = None


class OutcomeIn(BaseModel):
    segment_id: int
    sent_at: str | None = None
    results: list[OutcomeResult] = Field(min_length=1)


class BrandIn(BaseModel):
    guidelines: str
    banned_terms: list[str]
    exemplars: list[str]


# --------------------------------------------------------------------- meta
@app.get("/api/meta")
def meta():
    return {"intents": INTENTS, "tones": TONES, "demo_mode": generator.demo_mode()}


@app.get("/api/segments")
def segments():
    conn = db.get_conn()
    try:
        ids = [r["id"] for r in conn.execute("SELECT id FROM segments ORDER BY id")]
        return [ctx.segment_profile(conn, sid) for sid in ids]
    finally:
        conn.close()


@app.get("/api/brand")
def get_brand():
    conn = db.get_conn()
    try:
        return ctx.brand_voice(conn)
    finally:
        conn.close()


@app.put("/api/brand")
def put_brand(body: BrandIn):
    conn = db.get_conn()
    try:
        conn.execute(
            "UPDATE brand_voice SET guidelines=?, banned_terms_json=?, exemplars_json=? WHERE id=1",
            (body.guidelines, json.dumps(body.banned_terms), json.dumps(body.exemplars)),
        )
        conn.commit()
        return ctx.brand_voice(conn)
    finally:
        conn.close()


@app.get("/api/history")
def history(intent: str | None = None, tone: str | None = None):
    conn = db.get_conn()
    try:
        q = "SELECT * FROM historical_campaigns WHERE 1=1"
        args: list = []
        if intent:
            q += " AND intent=?"
            args.append(intent)
        if tone:
            q += " AND tone=?"
            args.append(tone)
        q += " ORDER BY sent_at DESC"
        return [dict(r) for r in conn.execute(q, args)]
    finally:
        conn.close()


# ---------------------------------------------------------------- campaigns
@app.get("/api/campaigns")
def list_campaigns():
    conn = db.get_conn()
    try:
        rows = conn.execute(
            """SELECT c.*,
                 (SELECT COUNT(*) FROM candidates k WHERE k.campaign_id=c.id) AS n_candidates,
                 (SELECT COUNT(*) FROM candidates k WHERE k.campaign_id=c.id
                    AND k.status IN ('accepted','edited')) AS n_selected,
                 (SELECT COUNT(*) FROM outcomes o WHERE o.campaign_id=c.id) AS n_outcomes
               FROM campaigns c ORDER BY c.id DESC"""
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["segment_ids"] = [
                s["segment_id"] for s in conn.execute(
                    "SELECT segment_id FROM campaign_segments WHERE campaign_id=?", (r["id"],))
            ]
            d["status"] = ("outcome logged" if r["n_outcomes"] else
                           "selected" if r["n_selected"] else
                           "generated" if r["n_candidates"] else "draft")
            out.append(d)
        return out
    finally:
        conn.close()


@app.post("/api/campaigns", status_code=201)
def create_campaign(body: CampaignIn):
    if body.intent not in INTENTS:
        raise HTTPException(422, f"intent must be one of {INTENTS}")
    conn = db.get_conn()
    try:
        known = {r["id"] for r in conn.execute("SELECT id FROM segments")}
        missing = set(body.segment_ids) - known
        if missing:
            raise HTTPException(422, f"unknown segment ids: {sorted(missing)}")
        cur = conn.execute(
            "INSERT INTO campaigns (name, intent, body) VALUES (?,?,?)",
            (body.name, body.intent, body.body),
        )
        cid = cur.lastrowid
        for sid in set(body.segment_ids):
            conn.execute(
                "INSERT INTO campaign_segments (campaign_id, segment_id) VALUES (?,?)", (cid, sid))
        conn.commit()
        return {"id": cid}
    finally:
        conn.close()


def _campaign_or_404(conn, campaign_id: int) -> dict:
    row = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "campaign not found")
    return dict(row)


def _candidate_out(row) -> dict:
    d = db.row_to_dict(row)
    d["display_text"] = d["edited_text"] or d["text"]
    return d


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    conn = db.get_conn()
    try:
        camp = _campaign_or_404(conn, campaign_id)
        seg_ids = [r["segment_id"] for r in conn.execute(
            "SELECT segment_id FROM campaign_segments WHERE campaign_id=?", (campaign_id,))]
        segments_out = []
        for sid in seg_ids:
            cands = conn.execute(
                """SELECT * FROM candidates WHERE campaign_id=? AND segment_id=?
                   ORDER BY score DESC""", (campaign_id, sid)).fetchall()
            shown = [_candidate_out(r) for r in cands
                     if not guardrails.is_blocked(json.loads(r["badges_json"]))]
            removed = len(cands) - len(shown)
            outcomes = [dict(r) for r in conn.execute(
                "SELECT * FROM outcomes WHERE campaign_id=? AND segment_id=?",
                (campaign_id, sid))]
            segments_out.append({
                "segment": ctx.segment_profile(conn, sid),
                "candidates": shown,
                "removed_by_guardrails": removed,
                "outcomes": outcomes,
            })
        camp["segments"] = segments_out
        return camp
    finally:
        conn.close()


# --------------------------------------------------------------- generation
def _pipeline(conn, camp: dict, segment_id: int) -> dict:
    """Run stages 1-5 for one campaign x segment and persist the candidates."""
    context = ctx.build_context(conn, camp, segment_id)
    retr = retrieval.retrieve(conn, camp["intent"], context["segment"])
    banned = context["brand"]["banned_terms"]
    exemplars = context["brand"]["exemplars"]

    raw_cands = generator.generate(context, retr)

    processed, blocked = [], []
    seen_texts = set()
    for cand in raw_cands:
        if cand["text"].lower() in seen_texts:
            continue
        seen_texts.add(cand["text"].lower())
        badges = guardrails.run_guardrails(cand["text"], banned)
        (blocked if guardrails.is_blocked(badges) else processed).append((cand, badges))

    # One top-up round if guardrails thinned the set (architecture section 5).
    if len(processed) < generator.N_CANDIDATES and not generator.demo_mode():
        for cand in generator.generate(context, retr):
            if len(processed) >= generator.N_CANDIDATES:
                break
            if cand["text"].lower() in seen_texts:
                continue
            seen_texts.add(cand["text"].lower())
            badges = guardrails.run_guardrails(cand["text"], banned)
            if not guardrails.is_blocked(badges):
                processed.append((cand, badges))

    rows = []
    for cand, badges in processed + blocked:
        score, breakdown = ranking.score_candidate(
            cand["text"], cand["tone"], retr["tone_stats"], exemplars, badges)
        is_blocked = guardrails.is_blocked(badges)
        cur = conn.execute(
            """INSERT INTO candidates (campaign_id, segment_id, text, tone, rationale,
                 score, score_breakdown_json, badges_json, status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (camp["id"], segment_id, cand["text"], cand["tone"], cand["rationale"],
             score, json.dumps(breakdown), json.dumps(badges),
             "rejected" if is_blocked else "proposed"),
        )
        if not is_blocked:
            row = conn.execute("SELECT * FROM candidates WHERE id=?", (cur.lastrowid,)).fetchone()
            rows.append(_candidate_out(row))
    rows.sort(key=lambda c: c["score"], reverse=True)

    return {
        "segment": context["segment"],
        "retrieval": retr,
        "candidates": rows,
        "removed_by_guardrails": len(blocked),
        "no_history": not retr["positives"],
    }


@app.post("/api/campaigns/{campaign_id}/generate")
def generate_candidates(campaign_id: int):
    conn = db.get_conn()
    try:
        camp = _campaign_or_404(conn, campaign_id)
        seg_ids = [r["segment_id"] for r in conn.execute(
            "SELECT segment_id FROM campaign_segments WHERE campaign_id=?", (campaign_id,))]
        # Regeneration replaces previous proposals that were never acted on.
        conn.execute(
            "DELETE FROM candidates WHERE campaign_id=? AND status IN ('proposed','rejected')"
            " AND id NOT IN (SELECT candidate_id FROM outcomes)", (campaign_id,))
        try:
            result = [_pipeline(conn, camp, sid) for sid in seg_ids]
        except Exception as e:  # LLM/network failure surfaces as a retryable 502
            conn.rollback()
            raise HTTPException(502, f"generation failed: {e}")
        conn.commit()
        return {"campaign_id": campaign_id, "demo_mode": generator.demo_mode(),
                "segments": result}
    finally:
        conn.close()


# ----------------------------------------------------------------- feedback
@app.post("/api/candidates/{candidate_id}/status")
def set_status(candidate_id: int, body: StatusIn):
    if body.status not in ("accepted", "edited", "rejected", "proposed"):
        raise HTTPException(422, "invalid status")
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "candidate not found")
        if body.status in ("accepted", "edited"):
            n = conn.execute(
                """SELECT COUNT(*) FROM candidates
                   WHERE campaign_id=? AND segment_id=? AND status IN ('accepted','edited')
                     AND id != ?""",
                (row["campaign_id"], row["segment_id"], candidate_id)).fetchone()[0]
            if n >= MAX_ACCEPTED:
                raise HTTPException(409, f"A/B limit: at most {MAX_ACCEPTED} accepted per segment")
        edited = body.edited_text if body.status == "edited" else None
        if body.status == "edited" and not (edited and edited.strip()):
            raise HTTPException(422, "edited status requires edited_text")
        conn.execute("UPDATE candidates SET status=?, edited_text=? WHERE id=?",
                     (body.status, edited, candidate_id))
        conn.commit()
        out = _candidate_out(conn.execute(
            "SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone())
        if body.status == "edited":
            banned = ctx.brand_voice(conn)["banned_terms"]
            out["edited_badges"] = guardrails.run_guardrails(edited, banned)
        return out
    finally:
        conn.close()


@app.post("/api/campaigns/{campaign_id}/outcome", status_code=201)
def log_outcome(campaign_id: int, body: OutcomeIn):
    conn = db.get_conn()
    try:
        camp = _campaign_or_404(conn, campaign_id)
        seg = conn.execute("SELECT * FROM segments WHERE id=?", (body.segment_id,)).fetchone()
        if seg is None:
            raise HTTPException(404, "segment not found")
        added = []
        for res in body.results:
            cand = conn.execute(
                "SELECT * FROM candidates WHERE id=? AND campaign_id=? AND segment_id=?",
                (res.candidate_id, campaign_id, body.segment_id)).fetchone()
            if cand is None:
                raise HTTPException(404, f"candidate {res.candidate_id} not in this campaign/segment")
            if cand["status"] not in ("accepted", "edited"):
                raise HTTPException(422, f"candidate {res.candidate_id} was not accepted")
            conn.execute(
                "INSERT INTO outcomes (campaign_id, segment_id, candidate_id, open_rate, sent_at, variant)"
                " VALUES (?,?,?,?,?,?)",
                (campaign_id, body.segment_id, res.candidate_id, res.open_rate,
                 body.sent_at, res.variant))
            sent_text = cand["edited_text"] or cand["text"]
            # The flywheel (FR-12): the sent line joins the retrieval corpus.
            conn.execute(
                "INSERT INTO historical_campaigns"
                " (subject_line, intent, tone, audience_size, open_rate, segment_id, sent_at, source)"
                " VALUES (?,?,?,?,?,?,?, 'app')",
                (sent_text, camp["intent"], cand["tone"], seg["size"], res.open_rate,
                 body.segment_id, body.sent_at))
            added.append(sent_text)
        conn.commit()
        return {"logged": len(added), "added_to_history": added}
    finally:
        conn.close()


# -------------------------------------------------------------------- static
if os.path.isdir(STATIC_DIR):
    @app.get("/")
    def index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
