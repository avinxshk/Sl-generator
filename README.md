# SL Generator — AI Subject Line Generator

A working prototype that generates **ranked, on-brand candidate subject lines**
for email campaigns, grounded in audience segment data and the historical
performance of past subject lines — with a human-in-the-loop feedback flywheel.

Built 0→1 through a documented product lifecycle: problem framing → PRD →
architecture → UX → prototype → evaluation → launch readiness, with every
tradeoff logged.

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000
# open http://localhost:8000
```

That's it — the app seeds a synthetic SQLite database (segments, customers,
60 historical campaigns, brand voice) on first start and runs in **demo mode**
with realistic canned candidates.

**Live generation with Claude:**

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # see .env.example
uvicorn app.main:app --port 8000
```

**Tests:**

```bash
pytest
```

## The flow

1. **New Campaign** — pick an intent, paste the email body, select audience segments.
2. **Review** — 6 ranked candidates per segment, each with a tone label, a
   rationale grounded in similar past campaigns (viewable, with open rates and
   match reasons), a transparent score breakdown, and guardrail warning badges.
3. **Select** — accept up to 2 per segment (A/B), edit freely (edits are
   re-linted; originals retained).
4. **Log outcome** — after sending, enter the open rate. The sent line joins
   the historical corpus and informs the very next generation (the flywheel).

## How generation is grounded

```
segment profile ─┐
brand voice ─────┼─► retrieval (similar past campaigns + tone stats)
campaign intent ─┘        │
                          ▼
                  Claude generation (6 candidates, ≥4 tones)
                          │
                  guardrail linter (block/badge)
                          │
                  heuristic ranker (tone evidence + length + brand fit)
```

Retrieval, guardrails, and ranking are all deterministic and explainable —
every score shows its components, every comparable shows why it matched.

## Repository map

| Path | What it is |
|---|---|
| `docs/01-problem-framing.md` | Problem, users, JTBD, success metrics |
| `docs/02-prd.md` | Requirements, user stories, MVP scope |
| `docs/03-architecture.md` | System design, data model, pipeline, prompts |
| `docs/04-ux-spec.md` | Screen-by-screen UX spec |
| `docs/05-evaluation.md` | Pre-send, post-send, and flywheel evaluation |
| `docs/06-launch-readiness.md` | Rollout plan, risk register, security posture |
| `docs/TRADEOFFS.md` | **Every flagged tradeoff decision (T-001…T-012)** |
| `app/` | FastAPI backend: pipeline stages as one module each |
| `static/` | No-build vanilla JS single-page app |
| `tests/` | Guardrails, ranking, retrieval, and end-to-end API tests |

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset (demo mode) | Enables live Claude generation |
| `SL_MODEL` | `claude-sonnet-5` | Model for generation |
| `SL_DB_PATH` | `./sl.db` | SQLite location |
