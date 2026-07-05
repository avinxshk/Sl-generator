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
