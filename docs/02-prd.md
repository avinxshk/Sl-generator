# Step 2 — Product Requirements Document (PRD)

**Product:** AI Subject Line Generator ("SL Generator")
**Version:** v1 (MVP prototype)
**Status:** Approved (2026-07-05)
**Precedes:** [03-architecture.md](./03-architecture.md)

---

## 1. Summary

A standalone web app where an email marketer inputs a campaign's **intent** and
**body content**, selects **audience segments**, and receives **6 ranked,
on-brand candidate subject lines per segment** — each with a tone label, a
rationale grounded in historical performance, and guardrail badges. The
marketer accepts up to 2 candidates (A/B), and post-send open rates feed back
into the corpus the system retrieves from.

## 2. Personas

- **Maya, email marketer (primary).** Ships 5–10 campaigns/week. Wants strong
  options fast and a reason to believe each one. Will abandon any tool that
  produces generic copy.
- **Ben, brand lead (secondary).** Owns voice guidelines. Wants every candidate
  to respect tone, banned words, and claims policy without him reviewing sends.
- **Priya, CRM analyst (tertiary).** Wants selection + outcome data captured so
  performance analysis and future ranking improvements are possible.

## 3. User stories (MVP)

| # | Story | Acceptance criteria |
|---|---|---|
| U1 | As Maya, I create a campaign with intent + body and pick segments | Intent from fixed taxonomy; ≥1 segment required; body free text |
| U2 | As Maya, I generate candidates per segment | 6 candidates/segment, each with tone label, rationale, rank score with visible breakdown |
| U3 | As Maya, I see why the system believes in a candidate | Rationale references audience traits and/or similar past campaigns; retrieved comparables viewable |
| U4 | As Maya, I see risk flags before choosing | Guardrail badges: truncation, spam words, caps/punctuation, banned claims. Hard violations never shown as pickable |
| U5 | As Maya, I accept up to 2 candidates (A/B), edit any before accepting | Edits preserved as `edited` status with original text retained |
| U6 | As Maya, I log the campaign's open rate after sending | Outcome saved; campaign + chosen line joins historical corpus |
| U7 | As Ben, I edit brand voice, exemplars, and banned terms in-app | Changes apply to next generation; no deploy needed |
| U8 | As Maya, I browse segments and their engagement profiles | Segment list with size, traits, product mix, engagement stats |
| U9 | As Maya/Priya, I browse historical subject lines and open rates | Filterable by intent/tone; this is the corpus the AI cites |

## 4. Intent taxonomy (v1)

`promotional`, `newsletter`, `product_announcement`, `winback`,
`transactional_upsell`, `event_invite`. Fixed list in v1 — free-text intents
would fragment the retrieval corpus (noted in T-010 discussion).

## 5. Functional requirements

### Generation
- FR-1: One generation request per campaign × segment; returns exactly 6 candidates after filtering (regenerate shortfall once; if still short, show what passed).
- FR-2: Candidates must span ≥4 distinct tones from: `urgency`, `curiosity`, `benefit_led`, `personal`, `social_proof`, `plain_informative`.
- FR-3: Each candidate carries: text, tone, rationale (≤2 sentences), rank score 0–100 with component breakdown, guardrail badges.
- FR-4: Prompt context includes: segment profile, brand voice + exemplars, top-5 similar historical performers + 2 worst (negative examples), campaign intent + body summary.
- FR-5: Demo mode (no `ANTHROPIC_API_KEY`): realistic canned candidates keyed by intent; pipeline (guardrails, ranking, feedback) runs identically.

### Guardrails (all deterministic, run server-side on every candidate)
- FR-6: Length: warn > 55 chars ("may truncate on mobile"); block > 90.
- FR-7: Spam-trigger lexicon (e.g., "FREE!!!", "act now", "guaranteed"): warn; ≥2 hits block.
- FR-8: All-caps ratio > 30% of letters: warn. `!`/`?` count > 2: warn.
- FR-9: Brand banned words/claims (from brand settings): block.

### Feedback loop
- FR-10: Every candidate ends in exactly one status: `proposed` → `accepted` | `edited` | `rejected`.
- FR-11: Campaign outcome: open rate (0–100%), optional send date + variant attribution for A/B.
- FR-12: On outcome logging, the sent line(s) are inserted into `historical_campaigns` with intent, tone, audience size, open rate — immediately retrievable.

### Non-functional
- NFR-1: Generation round-trip < 15 s (single LLM call).
- NFR-2: Runs locally with `pip install` + one command; SQLite; no external services other than the Claude API.
- NFR-3: Every ranking and retrieval decision must be explainable in the UI (no black-box scores).

## 6. Out of scope (v1)

Per-recipient personalization; ESP integration; trained open-rate models;
preview text/body generation; send-time optimization; multi-language;
authentication/multi-tenant (single-workspace prototype).

## 7. Success metrics (final)

| Metric | Target for prototype validation |
|---|---|
| Acceptance rate (candidate used as-is or edited) | ≥ 60% of campaigns |
| Time-to-subject-line | < 2 minutes from campaign creation |
| Guardrail precision | 0 blocked candidates that a marketer would have wanted |
| North star (post-prototype) | Open-rate lift vs. marketer baseline, matched by intent/segment |

## 8. Decisions made in this step

T-006 (guardrail layer in v1), T-007 (full feedback loop), T-008 (6 candidates,
pick up to 2 for A/B), T-009 (brand voice editable in-app), T-010 (tag-based
retrieval, no vector DB). See [TRADEOFFS.md](./TRADEOFFS.md).
