"""Stage 3: candidate generation — Claude API call, or demo mode without a key.

Contract: generate(context, retrieval) -> list of 6 dicts {text, tone, rationale}
spanning >= MIN_DISTINCT_TONES tones (FR-1, FR-2). Tone diversity is enforced by
instruction plus one corrective retry (T-012). Demo mode returns curated canned
sets keyed by intent so the rest of the pipeline behaves identically (FR-5).
"""
import json
import os
import re

from .taxonomy import TONES

MODEL = os.environ.get("SL_MODEL", "claude-sonnet-5")
N_CANDIDATES = 6
MIN_DISTINCT_TONES = 4
TIMEOUT_S = 15.0

SYSTEM_PROMPT = """You are a senior email copywriter for this brand.

Brand voice guidelines:
{guidelines}

Exemplar subject lines that define the brand's register:
{exemplars}

Never use these banned words or claims: {banned}

You write email subject lines that are specific, honest, and grounded in the
audience and evidence provided. Never promise anything the email body cannot
back up."""

USER_PROMPT = """Write exactly {n} candidate subject lines for this campaign.

CAMPAIGN INTENT: {intent}
EMAIL BODY (summary): {body}

AUDIENCE SEGMENT: {segment_name} — {segment_desc}
Size: {size} recipients. Traits: {traits}.
Top products owned: {products}. Avg opens last 90d: {opens}; avg days since last open: {recency}.

HISTORICAL EVIDENCE (similar past campaigns and their open rates):
Top performers:
{positives}
Poor performers (avoid these patterns):
{negatives}
Mean open rate by tone in comparable campaigns: {tone_stats}

REQUIREMENTS:
- Exactly {n} candidates, covering at least {min_tones} distinct tones from: {tones}.
- Target <= 55 characters per line.
- Each rationale is at most 2 sentences and must reference the audience or the historical evidence.
- Respond with ONLY a JSON array, no prose: [{{"text": "...", "tone": "...", "rationale": "..."}}, ...]"""


def demo_mode() -> bool:
    return not os.environ.get("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------- demo mode
# Curated per-intent sets; {seg} is replaced with the segment name.
DEMO_SETS = {
    "promotional": [
        ("Your 25% off ends at midnight", "urgency", "Urgency lines average the top open rates for promotional sends to comparable audiences; the deadline is concrete."),
        ("The sale our {seg} see first", "personal", "Early-access framing rewards this segment's relationship with the brand."),
        ("25% off the plan you already use", "benefit_led", "Ties the discount to a product this audience owns, echoing top benefit-led performers."),
        ("What 25% off actually gets you", "curiosity", "A curiosity angle with a concrete payoff, avoiding hype the body can't back."),
        ("3,000 people upgraded this week", "social_proof", "Social proof performed well for similar audience sizes in past sends."),
        ("Sale details inside: dates and terms", "plain_informative", "A plain control line for readers who ignore persuasion; historically the floor, not the ceiling."),
    ],
    "winback": [
        ("We kept your favorites safe", "curiosity", "Curiosity leads winback open rates in comparable campaigns; implies stored value waiting."),
        ("Did we do something wrong?", "personal", "Direct personal appeal is the second-best winback tone in the history for this size band."),
        ("A lot changed since you left", "curiosity", "Change-since-you-left framing performed above the winback average."),
        ("Your account, exactly as you left it", "plain_informative", "Reassurance angle for dormant users wary of starting over."),
        ("Come back before your credits sleep too", "urgency", "Gentle urgency variant; note urgency underperforms curiosity for winback historically."),
        ("Members who returned saved an average of $40", "social_proof", "Concrete peer outcome for the price-sensitive lapsed segment."),
    ],
    "newsletter": [
        ("5 things worth your inbox this week", "plain_informative", "Numbered digest lines are the newsletter workhorse in the archive."),
        ("The feature everyone asked about, explained", "curiosity", "Curiosity slightly outperforms plain tone for newsletters in the history."),
        ("What {seg} read most last month", "personal", "Audience-mirroring subject tailored to this segment's reading habits."),
        ("Inside: our roadmap, unfiltered", "curiosity", "Transparency framing suits an engaged readership."),
        ("This month in product, in 3 minutes", "benefit_led", "Time-bounded benefit respects the reader's attention."),
        ("Team picks: tools we actually use", "social_proof", "Practitioner credibility angle for a professional audience."),
    ],
    "product_announcement": [
        ("Meet the upgrade you asked for", "benefit_led", "Benefit-led lines top announcement open rates in comparable sends."),
        ("You asked. We built it.", "personal", "Echoes a top-performing historical announcement pattern."),
        ("What's new: faster, roomier, quieter", "plain_informative", "Concrete triad of improvements without hype."),
        ("The one feature we couldn't keep secret", "curiosity", "Curiosity is the second-strongest announcement tone in the archive."),
        ("Early users call it a game changer", "social_proof", "Peer validation for a feature-focused audience."),
        ("New today: more room in every plan", "urgency", "Freshness framing; urgency is historically weaker here, ranked accordingly."),
    ],
    "transactional_upsell": [
        ("Your plan is working hard. Give it help.", "personal", "Speaks to observed usage; personal tone performs well for upsell in history."),
        ("One upgrade, twice the room", "benefit_led", "Benefit-led is the top upsell tone in comparable campaigns."),
        ("You're at 80% - here's the fix", "urgency", "Usage-threshold urgency grounded in a fact the body substantiates."),
        ("What Pro users get that you don't (yet)", "curiosity", "Gap-framing curiosity with a concrete payoff inside."),
        ("Teams like yours upgraded last quarter", "social_proof", "Peer-cohort proof for a B2B-leaning audience."),
        ("Storage options for your account", "plain_informative", "Plain control line; historically the floor for upsell sends."),
    ],
    "event_invite": [
        ("Save your seat - 200 already in", "social_proof", "Social proof is the top invite tone in the archive; scarcity is factual."),
        ("You're invited: live session Thursday", "personal", "Direct invitation with a concrete date, matching strong past invites."),
        ("Doors close Friday for the summer event", "urgency", "Deadline urgency is a close second for invite opens historically."),
        ("What we're unveiling on stage", "curiosity", "Reveal framing for an announcement-style event."),
        ("90 minutes that will change your workflow", "benefit_led", "Time-boxed benefit promise for a busy audience."),
        ("Summer launch event: agenda inside", "plain_informative", "Plain agenda line as the informational control."),
    ],
}


def _demo_candidates(context: dict) -> list[dict]:
    seg_name = context["segment"]["name"]
    out = []
    for text, tone, rationale in DEMO_SETS[context["intent"]]:
        out.append({"text": text.replace("{seg}", seg_name.lower()),
                    "tone": tone, "rationale": rationale})
    return out


# ---------------------------------------------------------------- live mode
def _format_history(items: list[dict]) -> str:
    if not items:
        return "  (no comparable history)"
    return "\n".join(
        f'  - "{i["subject_line"]}" (tone: {i["tone"]}, open rate: {i["open_rate"]}%, {i["match_reason"]})'
        for i in items
    )


def _build_messages(context: dict, retrieval: dict) -> tuple[str, str]:
    brand = context["brand"]
    seg = context["segment"]
    system = SYSTEM_PROMPT.format(
        guidelines=brand["guidelines"],
        exemplars="\n".join(f'- "{e}"' for e in brand["exemplars"]),
        banned=", ".join(brand["banned_terms"]) or "(none)",
    )
    user = USER_PROMPT.format(
        n=N_CANDIDATES,
        min_tones=MIN_DISTINCT_TONES,
        tones=", ".join(TONES),
        intent=context["intent"],
        body=context["body_summary"],
        segment_name=seg["name"],
        segment_desc=seg["description"],
        size=seg["size"],
        traits=", ".join(seg["traits"]),
        products=", ".join(f'{p["product"]} ({int(p["share"] * 100)}%)' for p in seg["top_products"]) or "n/a",
        opens=seg["avg_opens_90d"],
        recency=seg["avg_days_since_open"],
        positives=_format_history(retrieval["positives"]),
        negatives=_format_history(retrieval["negatives"]),
        tone_stats=json.dumps(retrieval["tone_stats"]) or "{}",
    )
    return system, user


def _parse_candidates(raw: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON array in model output")
    items = json.loads(match.group(0))
    out = []
    for item in items:
        text = str(item["text"]).strip()
        tone = str(item["tone"]).strip()
        if tone not in TONES:
            tone = "plain_informative"
        out.append({"text": text, "tone": tone,
                    "rationale": str(item.get("rationale", "")).strip()})
    if not out:
        raise ValueError("empty candidate list")
    return out


def _call_claude(system: str, user_msgs: list[dict]) -> str:
    import anthropic  # imported lazily so demo mode needs no key or network

    client = anthropic.Anthropic(timeout=TIMEOUT_S)
    resp = client.messages.create(
        model=MODEL, max_tokens=2000, system=system, messages=user_msgs,
    )
    # Skip thinking blocks; grab the first text block.
    for block in resp.content:
        if hasattr(block, "text"):
            return block.text
    raise ValueError("no text block in model response")


def _distinct_tones(cands: list[dict]) -> int:
    return len({c["tone"] for c in cands})


def generate(context: dict, retrieval: dict) -> list[dict]:
    if demo_mode():
        return _demo_candidates(context)

    system, user = _build_messages(context, retrieval)
    messages = [{"role": "user", "content": user}]
    raw = _call_claude(system, messages)
    try:
        cands = _parse_candidates(raw)
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        # One corrective re-ask with the error appended (architecture section 5).
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": f"Invalid output ({e}). Respond with ONLY the JSON array."}]
        cands = _parse_candidates(_call_claude(system, messages))

    if _distinct_tones(cands) < MIN_DISTINCT_TONES:
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user",
                      "content": f"Only {_distinct_tones(cands)} distinct tones — regenerate with at least {MIN_DISTINCT_TONES} distinct tones from: {', '.join(TONES)}. JSON array only."}]
        try:
            cands = _parse_candidates(_call_claude(system, messages))
        except (ValueError, json.JSONDecodeError, KeyError):
            pass  # keep the under-diversified set rather than fail the request
    return cands[:N_CANDIDATES]
