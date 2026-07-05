# Step 1 — Problem Framing & Requirements

**Product:** AI Subject Line Generator for email marketing
**Status:** Approved (2026-07-05)
**Owners:** Principal PM + Principal Engineer

---

## 1. Problem statement

Marketers spend significant time writing email subject lines and rely largely on
intuition. The subject line is the single highest-leverage lever on open rate,
yet the writing process is disconnected from the data that could inform it:
historical subject line performance, audience characteristics, and brand voice
guidelines all live in different places (or in people's heads).

Consequences today:

- Inconsistent brand voice across campaigns and writers.
- Copy decisions made without reference to what has actually worked.
- No systematic learning loop — a great subject line's lesson dies with the campaign.
- 15–30 minutes of brainstorming per campaign that produces 2–3 untested options.

## 2. Users

| User | Role in this product |
|---|---|
| **Email marketer** (primary) | Composes campaigns; wants strong candidates fast, with reasons to believe |
| **Brand / marketing lead** (secondary) | Owns voice guidelines; wants them enforced without reviewing every send |
| **Lifecycle / CRM analyst** (tertiary) | Wants the performance data flywheel to actually spin |

## 3. Job to be done

> "When I've drafted a campaign for a given audience and intent, help me get
> high-performing, on-brand subject line options in seconds instead of 30
> minutes of brainstorming — and tell me **why** each option should work."

## 4. Core product insight

Three signals exist that nobody combines at write-time:

1. **Customer/audience data** — segments, product ownership, past engagement.
2. **Historical subject line performance** — past lines with open rates, tagged
   by campaign intent, tone of voice, and audience size.
3. **Brand voice constraints** — guidelines plus exemplar successful lines.

The system's differentiated value is **grounded generation**: candidates
informed by retrieval over what actually worked for similar intent + audience,
constrained by brand rules — not generic LLM copywriting.

## 5. Inputs available to the system

- Marketer-provided: **email intent** (e.g., promotional, win-back,
  announcement) and **email body content**.
- Customer data: segments, product ownership, per-customer past email engagement.
- Brand assets: voice guidelines, exemplar successful subject lines.
- Performance history: past subject lines with open rates, each tagged with
  campaign intent, subject line tone, and audience size.

## 6. Success metrics (draft — finalized in PRD)

| Tier | Metric | Definition |
|---|---|---|
| North star | **Open-rate lift** | Opens on campaigns using generated lines vs. marketer-written baseline, matched by intent/segment |
| Adoption | **Acceptance rate** | % of campaigns where a generated candidate is used as-is or lightly edited |
| Efficiency | **Time-to-subject-line** | Campaign draft → chosen subject line |
| Trust | **Rationale usefulness** | Marketer-rated helpfulness of the "why this should work" explanations |

## 7. Key decisions locked in this step

| ID | Decision | Choice |
|---|---|---|
| T-001 | Assistive vs. autonomous | **Assistive**: ranked candidates, human chooses/edits |
| T-002 | Prototype form | **Standalone web app** with synthetic data + real LLM |
| T-003 | Personalization depth | **Per-segment** (one candidate set per campaign × segment) |
| T-004 | Use of historical performance data | **Retrieval + heuristic ranking** (no trained model in v1) |
| T-005 | LLM provider | **Claude API**, with demo mode when no key is present |

Full rationale and rejected alternatives: see [TRADEOFFS.md](./TRADEOFFS.md).

## 8. Non-goals for v1

- Per-recipient personalized subject lines (revisit after per-segment proves lift).
- ESP integration (Braze/Klaviyo/SFMC) — the prototype is standalone.
- Trained open-rate prediction model — needs more data than a typical brand has.
- Send-time optimization, preview-text generation, body copy generation.
