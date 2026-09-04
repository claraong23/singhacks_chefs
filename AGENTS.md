# SingHacks 2026 — Julius Baer Wealth Intelligence

## Mission

Build an RM-first wealth-intelligence prototype that turns a fragmented client book into a defensible next action:

```text
client and portfolio context → evidence-backed signal → RM review → client-ready action
```

The product is not a trading bot and does not replace the Relationship Manager (RM). It helps **Priscilla Ong** decide who to contact, understand the client's situation, prepare a suitable conversation, and review a proposed action before anything reaches the client.

## The hackathon idea

### Product: `Clarity` — the RM's morning intelligence brief

The demo starts with a ranked workbench for Priscilla's 20-client book. She selects a client whose situation needs attention and moves through one calm, evidence-first flow:

1. **Why now** — a concise priority card states the signal, urgency, and impact.
2. **What changed and why** — the client context page explains the portfolio movement using dated snapshots, relevant holdings, and cited entries from `event_log.csv`.
3. **What could happen next** — risk/opportunity checks highlight concentration, liquidity, currency, mandate, collateral, or scenario exposure that is relevant to this client.
4. **What to discuss** — the RM workbench produces a client-meeting brief: objectives and RM notes, options to consider, suitability checks, questions to ask, and a draft follow-up. The RM can edit, reject, or approve it.

This tells the complete challenge story—**signal → understanding → decision → engagement**—without pretending that an LLM can autonomously give investment advice.

### Demo scope

Go deep on three client journeys and use the book-level workbench to demonstrate scale. Strong candidate journeys to validate from the data are:

- **CL-0003, Margarethe Voss-Brenner:** inherited a portfolio that appears misaligned with her conservative preference, while a confirmed EUR 3.4m tax instalment is due in 2026.
- **CL-0014, Lau Chi Ming:** possible correlated Hong Kong property exposure across holdings/structured products, facility use, limited sellable assets, and a confirmed HKD 60m redevelopment contribution.
- **CL-0017, Fong Enterprises Family Office:** USD 15.8m of confirmed private-markets commitments alongside a gated private-credit position and an explicit request for a liquidity map.

These are **investigation storylines, not investment recommendations**. The analytics and evidence panel must confirm every claim before it is shown in the demo. CL-0002 (volatile technology collateral) and CL-0012 (retirement-income/duration risk) are useful backup priority cards.

## Team ownership

| Owner | Primary responsibility | Deliverable and interface |
| --- | --- | --- |
| Teammate 1 | **Task 1 — Client Context / intelligent portfolio explanations** | A reusable client dossier: objectives, tax domicile, mandate, notes, multi-portfolio roll-up, snapshot changes, and a plain-language `what changed / why` explanation with source evidence. |
| Teammates 2 and 3 | **Task 2 — AI Wealth Intelligence Layer and UI/UX** | Deterministic signal checks and prioritisation, plus a polished shared visual system and screens. Suggested split: one owns data/risk rules and evidence payloads; the other owns the end-to-end UI, loading/error states, and demo polish. |
| Project lead (you) | **Task 3 — RM Intelligence Workbench**, solution foundation, and client advisory action | Create the application skeleton and shared contracts; own book prioritisation, insight-review state, meeting brief, recommendation options, suitability guardrails, approval/rejection, and the final client-action screen. Integrate the other workstreams and maintain the demo narrative. |

Every feature should be usable through the same path: `priority card → client dossier → evidence → RM action`. Avoid isolated dashboards that cannot feed a decision.

## Suggested solution structure

Keep the build small enough to finish. A single application with a data/analytics layer is preferable to distributed services.

```text
data/ or repository CSVs          Source-of-truth synthetic data
backend/
  loaders/                        CSV/JSON parsing and normalised client view
  analytics/                      Deterministic calculations and rule checks
  evidence/                       Source rows, dates, assumptions, confidence
  api/                            Stable payloads for the UI
frontend/
  pages/                          Book workbench, client dossier, action review
  components/                     Shared cards, charts, evidence drawer, controls
  styles/                         Accessible Julius Baer-inspired visual system
fixtures/                         Three demo-client payloads and test expectations
```

Recommended approach for a weekend:

- Use **deterministic Python calculations** for money, allocations, LTV, liquidity, mandate and priority scoring; make them inspectable and testable.
- Use an LLM only to turn already-computed facts into concise explanations or meeting-brief prose. Pass structured facts and citation IDs, never raw unrestricted portfolio data plus an open-ended prompt.
- A lightweight React/Next frontend with a FastAPI or similar Python API is a good full-stack choice if the team is comfortable with it. A Streamlit prototype is acceptable if it enables a substantially better end-to-end demo. Do not introduce LangGraph, vector search, or multiple agents unless they solve a real demo need.
- The organiser's optional accelerators are Groq (fast inference), LangChain/LangGraph, Chroma/Weaviate/Pinecone, Streamlit/Chainlit, Vercel/Railway, Tavily, and LlamaIndex. They are optional, not requirements.

## Shared contracts

Define these shapes early so four people can work in parallel.

```text
Insight
  id, client_id, category, severity, priority_score, headline
  observed_facts[], client_relevance, suggested_next_step
  evidence[] {source_file, row_or_id, snapshot_date, field, value}
  assumptions[], suitability_checks[], status (new | reviewed | dismissed | actioned)

Client briefing
  client profile, objectives, portfolio roll-up, RM notes
  selected insights, explanation, scenario, meeting questions
  action options[], RM decision, audit trail
```

Use stable `client_id`, `portfolio_id`, `instrument_id`, snapshot dates, and source IDs rather than display names as join keys. Keep computation outputs separate from AI wording so a judge can inspect the basis of each statement.

## Data and governance rules — non-negotiable

- This repository contains **synthetic** client data only; still handle it as if it were confidential. Do not expose it to public services or commit keys/secrets.
- The dataset's current date is **2026-08-26**. Treat the five provided dates as a time series; a static snapshot cannot support a convincing explanation.
- `event_log.csv` is the authoritative source for 2026 events. Do not use model memory or live web facts to explain a portfolio event.
- Aggregate a client's portfolios before judging household-level concentration, liquidity or exposure. Custody portfolios form part of the wealth view but are not governed by a bank mandate.
- Look through structured products via `instruments.underlying_reference`; their labelled asset class is not the full economic exposure.
- Use `tax_domicile`, not residence, in tax-aware reasoning. Do not calculate tax outcomes unless the required information and assumptions are explicit.
- Treat private-markets marks as potentially lagged. Use lending value and advance rates—not market value—for LTV; liquidity tiers must constrain suggested funding actions.
- RM notes are useful but subjective. Show them as relationship context and flag contradictions with structured data; never present them as independently verified facts.
- Recommendations are **options for RM review**, not instructions. Every action needs an explanation, suitability/mandate checks, uncertainty or missing-data disclosure, and RM approval/edit/dismiss controls.

## Implementation sequence

1. Read `clients.csv`, `rm_notes.json`, and `event_log.csv`; choose the three demo journeys after checking them against the calculations.
2. Agree the `Insight` contract, date convention, formatting helpers, and a small shared design system before building separate views.
3. Implement one vertical slice for a chosen client: source data → deterministic signal → evidence → dossier → RM action. Demo this internally before expanding.
4. Add the book-priority view and the remaining two journeys. Favour clear ranking reasons over opaque AI scores.
5. Add review/dismiss/edit states, a compact evidence drawer, empty/missing-data states, and a short architecture/governance slide.
6. Rehearse a 3–5 minute journey. Confirm every number, event, and recommendation shown has a traceable source and an RM-control moment.

## Definition of done

The demo is ready when Priscilla can identify who to call first, open a defensible explanation of what changed, see the client-specific risk/opportunity and trade-offs, edit or reject a proposed next step, and leave with a client-ready meeting brief. A judge should be able to see both the human benefit and how the design could operate inside a regulated bank.
