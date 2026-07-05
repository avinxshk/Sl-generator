# Step 7 — Launch Readiness

**Status:** Approved (2026-07-05)

## 1. Rollout plan

1. **Internal dogfood (weeks 1–2):** 2–3 marketers, real campaigns, demo→live
   mode with a shared API key. Exit criteria: acceptance rate ≥50%, zero
   guardrail escapes, offline eval grid green.
2. **Team beta (weeks 3–6):** full marketing team; every campaign logs an
   outcome. Exit criteria: ≥20 A/B outcomes captured; measured lift reported
   with caveats from evaluation doc §4.
3. **Decision gate:** lift positive → invest in ESP integration (auto outcome
   capture) and revisit T-003 (per-segment → per-recipient) and T-004
   (heuristic → learned ranking). Lift flat/negative → iterate on prompt and
   retrieval before scaling.

## 2. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Off-brand or dishonest candidate reaches a send | High | Guardrail linter + human-in-the-loop (T-001) + banned-terms list owned by brand lead |
| Marketer over-trusts scores ("84 means 84% open") | Medium | Score shown with breakdown and labeled as heuristic; no percentage framing in UI |
| Feedback loop poisons itself (bad self-reported data) | Medium | `source='app'` rows auditable and separable; outlier open rates flaggable in v2 |
| LLM outage blocks campaign work | Medium | Demo mode fallback; marketer can always write manually — tool is assistive |
| Prompt injection via email body ("ignore instructions…") | Low–Med | Body is data inside a delimited section; guardrails run on output regardless; human review is the final gate |
| Homogenization: every brand email starts sounding the same | Medium | Tone diversity requirement; exemplar rotation encouraged; monitor edit distance |
| API key/cost creep | Low | Single call per segment (T-012); usage visible in provider console |

## 3. Privacy & security posture (prototype)

- Synthetic customer data only; no real PII in the repo or the demo DB.
- Segment **aggregates** (not individual customer rows) are sent to the LLM —
  this stays true when real data is connected and must be preserved (only
  profile-level stats leave the building).
- No auth in v1: run locally or behind a trusted network. Auth is a
  precondition for any shared deployment.
- API key via environment variable only; never stored in the DB or repo.

## 4. Preconditions for production (post-prototype backlog)

Auth + roles (marketer vs. brand lead), ESP integration for send + outcome
capture, migration off SQLite for concurrency, prompt/eval versioning, rate
limiting, and audit log UI for blocked candidates.
