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

## Judging criteria — visible proof in the product and demo

The four criteria carry equal weight. Do not leave any of them as a claim in a presentation: make each one visible in a screen, a decision, and a line in the narration.

| Criterion | What `Clarity` demonstrates | Evidence to show in the demo |
| --- | --- | --- |
| **Client-Centric Innovation (25%)** | Advice begins with the whole person—not a generic portfolio score. Each insight combines portfolio facts with objectives, life stage, tax domicile, planned cash needs, and RM relationship context. | Open a client-specific priority card, then show why the same market/risk signal matters differently for that client's goals. State the client outcome: greater confidence, earlier preparation, or a more relevant conversation. |
| **User Experience & Design (25%)** | A calm, RM-first flow reduces a 20-client book to the next best conversation. Progressive disclosure moves from `why now` to `why` to `what to discuss`; evidence is available without overwhelming the main view. | Complete the full journey in under 90 seconds: ranked book → client dossier → explanation/evidence → editable meeting brief. Show clear urgency labels, source dates, empty/missing-data handling, and one-click review/dismiss/edit controls. |
| **Technical & Operational Feasibility (25%)** | The architecture is deliberately bank-realistic: deterministic analytics for financial facts, a controlled event source, stable data contracts, traceable evidence, and AI limited to grounded narrative drafting. | Show the evidence drawer with source file/ID/date, suitability checks, assumption disclosure, and the RM approval state. Explain the single-app data/API architecture, synthetic-data handling, and how rules can be independently tested and audited. |
| **Strategic Impact (25%)** | `Clarity` is the intelligence layer that turns existing portfolio data into scalable, higher-quality RM coverage while retaining the relationship-led Julius Baer model. | Frame the outcome as helping Priscilla prioritise all 20 clients and arrive prepared for the three complex conversations—not replacing her judgement. Close with how the same workflow can expand from a prototype to monitored, governed advisory workflows. |

### Non-negotiable demo beats

1. Start with the **RM problem**: twenty clients, limited time, and too much descriptive information.
2. Demonstrate a **specific client decision**, not just analytics or charts.
3. Expose the **evidence and caveat** behind one insight; this is the trust moment.
4. Show the RM **editing, approving, or dismissing** the proposed action; this is the human-in-the-loop moment.
5. End on a client benefit and a business benefit: more timely, personalised advice and a scalable RM operating model.

## Team ownership

| Owner | Primary responsibility | Deliverable and interface |
| --- | --- | --- |
| Teammate 1 | **Task 1 — Client Context / intelligent portfolio explanations** | Own the client-context module: profile, objectives, tax domicile, mandate, RM notes, multi-portfolio roll-up, snapshot comparisons, and the grounded `what changed / why` explanation. Deliver a reusable `ClientContext` payload and evidence-linked explanation cards that Task 3 can display. |
| Teammate 2 | **Task 2 — Solution foundation and intelligence engine** | Own the working application foundation: repository/app bootstrap, CSV/JSON loaders, normalised data model, shared `Insight`/evidence contracts, API or service layer, deterministic signal checks, priority-score calculation, and fixtures/tests. Publish stable sample payloads early so the other tracks are never blocked by unfinished analytics. |
| Teammate 3 | **Task 2 — Shared UI/UX and platform integration** | Own the application shell and shared experience: routing/navigation, visual system, reusable cards/charts/evidence drawer, responsive/loading/error states, and integration of Task 1 and Task 2 payloads. Build the client-dossier and intelligence screens; keep the workbench action components reusable for Task 3. |
| Project lead (you) | **Task 3 — RM Intelligence Workbench and client advisory action** | Own the RM decision workflow on top of the Task 2 foundation: the prioritised-book view (using the supplied priority score), insight selection/review state, meeting brief, action options, suitability checklist, RM edit/approve/dismiss controls, and the client-ready follow-up screen. Own end-to-end acceptance checks and the final demo narrative—not the underlying application foundation. |

### Implementation hand-offs

1. **Task 2 establishes the foundation first**: the runnable app, sample client data, `Insight` contract, and shared design primitives. This is the integration path for every team member.
2. **Task 1 plugs client context into that contract**: its explanation output must carry the underlying date, portfolio/holding and event evidence, not only prose.
3. **Task 3 consumes, rather than recreates, Task 1 and 2 outputs**: it presents the provided priority score and evidence in the RM workflow, then adds review and advisory-action state.
4. **Task 2 remains the integration owner**: merge the work on the shared branch, resolve contract changes, and keep one working end-to-end vertical slice at all times. The project lead validates that the flow meets the story and rubric.

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
