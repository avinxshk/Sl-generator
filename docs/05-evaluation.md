# Step 6 — Evaluation & Learning Plan

**Status:** Approved (2026-07-05)

The system is evaluated at three moments: before the marketer sees candidates
(pre-send quality), after campaigns send (performance), and over time
(flywheel health).

## 1. Pre-send quality (automated, every generation)

| Check | Mechanism | Target |
|---|---|---|
| Brand safety | Guardrail linter (`app/guardrails.py`) | 0 blocked candidates ever displayed |
| Tone diversity | ≥4 distinct tones per set (enforced in `generator.py`) | 100% of sets |
| Length discipline | ≤55 chars target | ≥80% of candidates unbadged |
| Rationale grounding | Rationale must reference audience or history (prompt contract) | Spot-checked in review below |

**Offline eval harness (pre-launch gate):** run generation across a fixed grid
of intent × segment (36 combinations), assert the automated checks above, and
human-review one batch per intent for: on-brand voice (1–5), honesty vs. the
email body (pass/fail), and rationale usefulness (1–5). Regenerate the grid
whenever the prompt, model, or brand voice changes — this is the regression
suite for prompt engineering.

## 2. Post-send performance (the real test)

- **Primary:** open-rate lift vs. marketer-written baseline, matched by intent
  and segment. Measurement path in v1: marketers A/B a generated line against
  their own line (the tool supports 2 accepted variants precisely for this).
- **Secondary:** acceptance rate (target ≥60%), edit distance on `edited`
  candidates (heavy edits = weak generation), rank quality (did the #1-ranked
  candidate win the A/B? — measures the heuristic ranker directly).
- Every outcome logged feeds `historical_campaigns` with `source='app'`, so
  these analyses are simple SQL over one table.

## 3. Flywheel health (monthly)

- Corpus growth: app-sourced rows / total rows.
- Retrieval usefulness: share of generations where comparables existed
  (`no_history` flag rate should fall over time).
- Tone-stat stability: variance of per-tone open rates within intent — when it
  tightens, ranking weights can be trusted more (and eventually learned, see
  T-004 revisit condition).

## 4. Known evaluation gaps (accepted for v1)

- Open rates are marketer-reported; no verification against the ESP.
- Apple Mail privacy protection inflates open rates — lift comparisons are
  valid (both arms inflated), absolute numbers are not.
- No holdout: marketers self-select which campaigns use the tool, so lift
  estimates carry selection bias until an ESP integration allows proper splits.
