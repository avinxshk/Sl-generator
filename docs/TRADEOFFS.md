# Tradeoff Decision Log

Running log of every flagged tradeoff. Newest at the bottom. Each entry records
the decision, the alternatives we rejected, and what we knowingly gave up.

---

## T-001 — Assistive vs. autonomous selection

**Decision:** The tool generates **ranked candidates**; the marketer chooses or
edits. It never auto-selects a subject line.

**Alternatives rejected:** Fully autonomous selection; auto-select with veto window.

**Rationale:** Brand risk of one bad automated subject line is high and
asymmetric. Marketer trust is the adoption bottleneck for a 0→1 tool. The
accept/edit/reject decisions we capture become the training signal for future
ranking improvements.

**Cost accepted:** We forgo full automation value in v1; a marketer remains in
every loop.

---

## T-002 — Prototype form: standalone web app

**Decision:** Self-contained web app with realistic synthetic customer/campaign
data and a real LLM behind it.

**Alternatives rejected:** ESP plugin (mostly integration plumbing, needs
accounts/credentials); API-first with thin console (wrong primary user — ours
is a marketer, not an engineering team).

**Cost accepted:** Re-integration work later; synthetic data may hide messy
real-data problems (dedup, tagging quality, missing open rates).

---

## T-003 — Personalization depth: per-segment

**Decision:** One candidate set per campaign × audience segment, grounded in
that segment's aggregate traits and engagement history.

**Alternatives rejected:** Per-campaign only (ignores the customer data we
have); per-recipient (batch generation at send scale, per-line QA impossible,
cost scales with list size).

**Cost accepted:** Leaves per-recipient lift on the table. Architecture should
not preclude it later (keep generation request shaped as *context → candidates*
so a "context" can later be one recipient).

---

## T-004 — Historical data usage: retrieval + heuristic ranking

**Decision:** Retrieve similar past campaigns (by intent, tone, audience-size
band), feed top/bottom performers into the prompt as grounding, and rank
candidates with a transparent heuristic score.

**Alternatives rejected:** Trained open-rate prediction model (needs volumes of
history most brands lack; opaque to marketers); prompt-only with no retrieval
(wastes the performance dataset; cannot improve).

**Cost accepted:** Heuristic ranking is weaker than a trained model at scale.
Revisit when the tool has logged enough of its own campaign outcomes.

---

## T-005 — LLM provider: Claude API

**Decision:** Claude API for generation, behind a thin internal interface.
App runs in **demo mode** (canned, realistic outputs) when no API key is set.

**Alternatives rejected:** Full provider-agnostic abstraction layer (build cost
before we need it — the thin interface keeps the door open); local/open-source
model (weaker constrained copywriting, hosting burden in a prototype).

**Cost accepted:** Per-call cost; external dependency. Demo mode mitigates for
demos/CI.

---

## T-006 — Guardrail layer in v1

**Decision:** Rule-based linter runs on every candidate before display:
length/truncation, spam-trigger lexicon, all-caps ratio, punctuation abuse,
brand banned words/claims. Hard violations are filtered; soft ones get warning
badges.

**Alternatives rejected:** Length check only; defer entirely to v2 and trust
prompt constraints.

**Rationale:** Deterministic checks catch what the LLM occasionally misses; one
embarrassing candidate in a demo destroys trust; directly serves the brand-lead
persona.

**Cost accepted:** Lexicon-based spam detection is crude (false positives
possible); rules need curation over time.

---

## T-007 — Full feedback loop in v1

**Decision:** Record accept/edit/reject per candidate AND let marketers log
post-send open rates. Sent campaigns join the historical retrieval corpus.

**Alternatives rejected:** Selection capture only; generation-only v1.

**Rationale:** "The tool gets smarter with use" is the product's key strategic
claim — the demo must show the flywheel, and v2 ranking needs this data.

**Cost accepted:** Manual open-rate entry is friction (acceptable until ESP
integration automates it); self-reported data can be sloppy.

---

## T-008 — Candidate count & A/B selection

**Decision:** Generate 6 candidates per segment, deliberately diversified
across tones, ranked; marketer selects up to 2 as A/B variants.

**Alternatives rejected:** 6-pick-1 (ignores standard A/B practice);
3-pick-1 (weak diversity → whole-set rejections and retries).

**Cost accepted:** Slightly larger LLM output per call; A/B attribution adds a
field to the outcome model.

---

## T-009 — Brand voice editable in-app

**Decision:** Settings page where the brand lead edits voice guidelines, banned
words/claims, and exemplar subject lines; changes apply to the next generation.

**Alternatives rejected:** Static config file (locks out the persona who owns
the voice); read-only display with file-based editing.

**Cost accepted:** More UI surface; no approval workflow on voice edits in v1
(single-workspace prototype, low risk).

---

## T-010 — Tag-based retrieval, no vector DB

**Decision:** Retrieve similar historical campaigns via transparent tag
matching — intent (strongest weight), audience-size band, engagement profile —
rather than embedding similarity.

**Alternatives rejected:** Vector/embedding retrieval (adds infra and an opaque
similarity notion for marginal gain at a corpus of tens-to-hundreds of
campaigns); no retrieval at all.

**Rationale:** At this corpus size, structured tags ARE the signal (intent and
tone are already labeled), and the match reason can be shown to the marketer
verbatim. Revisit when the corpus is large enough that lexical/semantic
similarity of the *body content* adds retrieval value.

**Cost accepted:** Misses semantically similar campaigns with different intent
labels; depends on tagging quality. Fixed intent taxonomy (PRD §4) mitigates.
