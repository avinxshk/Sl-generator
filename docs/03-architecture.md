# Step 3 — System & AI Architecture

**Status:** Approved (2026-07-05)
**Implements:** [02-prd.md](./02-prd.md) · **Realized in:** `app/` and `static/`

---

## 1. System overview

Single-process FastAPI application, SQLite file database, no-build vanilla JS
single-page app served statically. One external dependency: the Claude API
(optional — demo mode without it).

```
┌──────────────────────────── Browser (SPA: static/) ────────────────────────────┐
│  Campaign wizard · Candidate review · History · Segments · Brand settings      │
└───────────────▲─────────────────────────────────────────────▲──────────────────┘
                │ JSON/REST                                    │
┌───────────────┴──────────────── FastAPI (app/main.py) ───────┴──────────────────┐
│                                                                                 │
│  POST /api/campaigns ─┐                                                         │
│  POST /api/campaigns/{id}/generate                                              │
│        │                                                                        │
│        ▼                                                                        │
│  ① context.py ──► ② retrieval.py ──► ③ generator.py ──► ④ guardrails.py ──► ⑤ ranking.py
│  segment profile   similar past      Claude API call     rule linter        heuristic
│  brand voice       campaigns         (or demo mode)      block/badge        score+breakdown
│        │               │                                                        │
│        └───────────────┴──────────── ⑥ feedback: candidate status, outcomes ────┤
│                                        POST /api/candidates/{id}/status         │
│                                        POST /api/campaigns/{id}/outcome         │
│                                              │                                  │
│                                              ▼ inserts into                     │
│                              historical_campaigns (retrieval corpus grows)      │
└───────────────────────────────── SQLite (db.py) ────────────────────────────────┘
```

## 2. Data model (SQLite, `app/db.py`)

```
segments(id, name, description, size, traits_json)
customers(id, segment_id, products_json, opens_90d, clicks_90d, last_open_days)
historical_campaigns(id, subject_line, intent, tone, audience_size,
                     open_rate, segment_id NULL, sent_at, source)   -- source: 'seed' | 'app'
brand_voice(id=1, guidelines, banned_terms_json, exemplars_json)    -- single row
campaigns(id, name, intent, body, created_at)
campaign_segments(campaign_id, segment_id)
candidates(id, campaign_id, segment_id, text, tone, rationale,
           score, score_breakdown_json, badges_json,
           status, edited_text NULL, created_at)                    -- status: proposed|accepted|edited|rejected
outcomes(id, campaign_id, segment_id, candidate_id, open_rate, sent_at, variant)
```

Design notes:
- `historical_campaigns.source` distinguishes seed data from app-logged
  outcomes so the flywheel is auditable and seed data can be swapped out.
- Generation request shape is *context → candidates*; a "context" is a segment
  today, could be one recipient later (keeps T-003's door open).

## 3. Pipeline stages

### ① Context builder (`app/context.py`)
Aggregates per-segment: size, traits, product-ownership mix, engagement stats
(avg opens/clicks 90d, recency distribution) computed from `customers`. Loads
brand voice row. Summarizes campaign body (first ~150 words verbatim — no LLM
summarization call in v1; flagged T-011).

### ② Retrieval (`app/retrieval.py`)
Transparent scored match over `historical_campaigns`:

```
similarity = 3·(intent == campaign.intent)
           + 1·(audience_size_band == segment.size_band)     # bands: <5k, 5–25k, >25k
           + 1·(segment_id == segment.id)                    # exact-audience bonus
```

Returns top-5 by `(similarity, open_rate)` as positive exemplars and bottom-2
(similarity > 0, lowest open_rate) as negative exemplars. Also computes
**tone-performance stats** for the matched set (mean open rate per tone) — used
by both the prompt and the ranker. Every retrieved item carries its
`match_reason` string for UI display.

### ③ Generator (`app/generator.py`)
Single Claude Messages API call (`claude-sonnet-5`), temperature 1.0,
structured JSON output. Prompt contract (system prompt):

- Role: senior email copywriter for this brand.
- Inputs: brand voice + exemplars, segment profile, intent, body summary,
  positive exemplars with open rates, negative exemplars, tone-performance stats.
- Instructions: 6 candidates spanning ≥4 tones from the fixed tone taxonomy;
  each with `text` (≤55 chars target), `tone`, `rationale` (≤2 sentences, must
  reference audience or historical evidence); obey banned terms; no clickbait
  that the body can't pay off.
- Output: strict JSON array; parsed defensively (retry once on parse failure).

**Demo mode:** when `ANTHROPIC_API_KEY` is unset, returns curated canned
candidate sets keyed by intent (with light template substitution from segment
name/traits), so every downstream stage behaves identically.

### ④ Guardrails (`app/guardrails.py`)
Pure functions, each returning `(level, badge)` where level ∈ {ok, warn, block}:
`check_length` (warn >55, block >90), `check_spam_words` (lexicon; warn 1 hit,
block ≥2), `check_caps` (>30% letters uppercase), `check_punctuation`
(>2 of `!?`), `check_banned_terms` (brand list → block). Blocked candidates are
persisted with status `rejected` and badge reason (auditable) but not shown as
pickable. If <6 survive, one regeneration round tops up the set.

### ⑤ Ranker (`app/ranking.py`)
Transparent 0–100 score, breakdown stored and shown:

```
score = 45·tone_evidence     # matched-set mean open rate for candidate's tone, normalized
      + 25·length_fit        # peak at 30–45 chars, linear falloff
      + 20·brand_similarity  # token overlap with exemplar lines (Jaccard, capped)
      + 10                   # base
      − guardrail_penalty    # 15 per warn badge
```

Weights are constants in one place; deliberately crude and inspectable (T-004).

### ⑥ Feedback
`PATCH`-style status endpoint enforces: ≤2 accepted/edited per campaign×segment
(A/B limit), edits retain original text. Outcome endpoint writes `outcomes` and
inserts the sent line(s) into `historical_campaigns` with `source='app'`.

## 4. API surface

```
GET  /api/segments                      GET  /api/history?intent=&tone=
GET  /api/brand   PUT /api/brand        GET  /api/campaigns  GET /api/campaigns/{id}
POST /api/campaigns                     POST /api/campaigns/{id}/generate
POST /api/candidates/{id}/status        POST /api/campaigns/{id}/outcome
GET  /api/meta                          # intents, tones, demo-mode flag
```

## 5. Failure modes & handling

| Failure | Handling |
|---|---|
| Claude API down/timeout | 15 s timeout → error surfaced with retry button; demo mode unaffected |
| Malformed LLM JSON | One re-ask with error appended; then 502 with message |
| All candidates blocked by guardrails | One regeneration with violations fed back into prompt; then show survivors + notice |
| Empty retrieval (novel intent) | Generation proceeds without exemplars; rationale/ranking fall back to length+brand components; UI notes "no comparable history" |
| Concurrent brand edits | Last-write-wins (single-workspace prototype) |

## 6. Decisions flagged in this step

- **T-011 — No LLM body summarization in v1:** body truncated to ~150 words for
  prompt context instead of a summarization call. Saves a call + latency;
  long emails lose tail context. Revisit if rationale quality suffers.
- **T-012 — Single generation call per segment** (not one call per tone):
  cheaper and faster; relies on the model honoring tone diversity instruction,
  which the diversity check + regeneration round enforces.
