# Step 4 — UX Specification

**Status:** Approved (2026-07-05)
**Realized in:** `static/` (single-page app, five views)

Design principles: (1) the marketer's flow is *compose → generate → choose*,
everything else is supporting evidence; (2) every AI output shows its working —
rationale, retrieved comparables, score breakdown; (3) risk is visible before
choice (badges), never after.

Navigation: persistent left sidebar — **New Campaign · Campaigns · History ·
Segments · Brand Voice**. Demo-mode banner shown at top when no API key.

---

## V1 — New Campaign (wizard, single screen)

```
┌─────────────────────────────────────────────────────────────┐
│ New Campaign                                                │
│ Name        [ Summer flash sale                    ]        │
│ Intent      [ promotional ▾ ]                               │
│ Segments    [x] Loyal high-spenders  [ ] New signups        │
│             [x] Lapsed 90-day        [ ] Bargain hunters    │
│ Email body  [ multiline textarea ................. ]        │
│                                                             │
│                              [ Generate subject lines ▸ ]   │
└─────────────────────────────────────────────────────────────┘
```

- Intent: fixed taxonomy dropdown (PRD §4). Validation: name, intent, ≥1
  segment, body required. Button shows spinner during generation (<15 s).

## V2 — Candidate Review (the core screen)

One tab per selected segment. Per segment:

```
┌ Segment: Lapsed 90-day (2,340 recipients) ── [tab] [tab] ───────────────┐
│ ▸ Audience: no open in 90+ days · owns: Basic plan (72%) · low clicks   │
│ ▸ Grounded on 5 similar campaigns (winback, 1–5k) — view comparables ▾  │
│                                                                         │
│ ┌───────────────────────────────────────────────────────────────────┐   │
│ │ #1  score 84 ▾   "We saved your favorites, Maya-style"            │   │
│ │     tone: curiosity   ⚠ 56 chars — may truncate on mobile         │   │
│ │     Why: curiosity lines averaged 31% opens for winback at this   │   │
│ │     audience size; references saved items from the email body.    │   │
│ │     [ Accept ] [ Edit ] [ Reject ]                                │   │
│ └───────────────────────────────────────────────────────────────────┘   │
│ ... candidates #2–#6 ...                                                │
│                                                                         │
│ Accepted (max 2 = A/B):  A: "…"   B: "…"     [ Finalize selection ]     │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Score breakdown** (`score 84 ▾` expands): tone evidence 38/45, length fit
  22/25, brand similarity 14/20, base 10, −0 penalties.
- **Comparables drawer**: retrieved historical lines with open rates and
  match reasons ("same intent · same size band").
- **Badges**: amber = warn (truncation, spam word, caps, punctuation);
  blocked candidates are not rendered (they exist only in the audit log).
- **Edit**: inline text input pre-filled with candidate; live char counter and
  guardrail re-check on save; accepted-as-edited keeps original visible on hover.
- Accepting a 3rd candidate is disabled with tooltip "A/B limit — reject one first".

## V3 — Campaigns (list + detail)

List: name, intent, segments, status (`draft` / `selected` / `outcome logged`),
created date. Detail: chosen lines per segment and the **Log outcome** form:

```
Segment: Lapsed 90-day     Variant A: "…"  open rate [ 28.4 ] %
                           Variant B: "…"  open rate [ 31.1 ] %
Sent date [2026-07-08]                     [ Save outcome ]
```

On save: confirmation toast — "Added to history. Future generations for
winback will see this." (makes the flywheel visible, U6/FR-12).

## V4 — History

Table of `historical_campaigns`: subject line, intent, tone, audience size,
open rate, source badge (`seed`/`app`). Filters: intent, tone. Sort: open rate,
date. Purpose: trust — this is exactly the corpus the AI cites.

## V5 — Segments

Card per segment: name, size, description, traits, product-ownership mix,
engagement profile (avg opens/clicks 90d, recency). Read-only in v1.

## V6 — Brand Voice (Ben's screen)

```
Voice guidelines   [ multiline textarea ]
Banned words/claims [ tag input: "guarantee", "risk-free", … ]
Exemplar subject lines (with optional note)
  1. "Your March picks are in"        [x]
  2. "A little something for loyal…"  [x]
  [ + add exemplar ]                    [ Save ]
```

Save applies to next generation. Banner: "Changes affect all future
generations."

---

## States & edge cases

- **Demo mode**: persistent banner "Running in demo mode — candidates are
  canned examples. Set ANTHROPIC_API_KEY for live generation."
- **Generation error**: inline error card with Retry (keeps form state).
- **No comparable history**: note above candidates — "No similar past
  campaigns; ranking uses length + brand fit only."
- **Fewer than 6 survivors** after guardrails + one regen: show survivors with
  notice "N candidates removed by brand guardrails".
- Empty states for every list view with a pointer to the action that fills it.
