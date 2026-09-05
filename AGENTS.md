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
| Teammate 1 — **Project lead** | **Task 1 — Client Context / intelligent portfolio explanations** | Own the client-context module: profile, objectives, tax domicile, mandate, RM notes, multi-portfolio roll-up, snapshot comparisons, and the grounded `what changed / why` explanation. Deliver a reusable `ClientContext` payload and evidence-linked explanation cards. As project lead, set scope, resolve product trade-offs, keep the demo storyline coherent, and accept each completed vertical slice. |
| Teammate 2 | **Task 2A — AI Wealth Intelligence / risk and opportunity engine** | Own deterministic signal checks and evidence payloads for concentration, liquidity, currency, mandate, collateral, and scenarios, plus explainable priority-score inputs. Deliver stable `Insight` fixtures/API responses for the UI; do not own the RM action workflow. |
| Teammate 3 | **Task 2B — Overall UI/UX and intelligence views** | Own the shared visual language and the screens that present Task 2: intelligence cards, risk/opportunity detail, evidence drawer, charts, and loading/error states. Integrate Task 1 context and Task 2 signals into clear, reusable components; do not own the recommendation/approval logic. |
| You | **Task 3 — RM Intelligence Workbench and client advisory action** | Own the RM decision workflow: the prioritised-book workbench (using Task 2's priority inputs), insight selection/review state, meeting brief, action options, suitability checklist, RM edit/approve/dismiss controls, and client-ready follow-up. Consume the shared inputs rather than rebuilding the analytics or client-context logic. |

### Extra task — solution foundation and integration

This is a shared enablement task, not a fourth feature track. **Teammate 2 is the technical owner** because its data contracts and signal engine depend on it; Teammate 3 owns the UI shell contribution; Teammate 1 approves scope; you integrate the workbench once the contract is stable. Keep it focused on the reusable capabilities needed to unblock parallel work, but do not trade away correctness, evidence provenance, accessibility, or testability:

1. Runnable repository/app bootstrap, environment template, and one command to start the demo.
2. CSV/JSON loaders, normalised client/portfolio/instrument data model, and three selected demo-client fixtures.
3. Versioned `ClientContext` and `Insight` contracts, source-evidence format, and stubbed responses where a task is not ready.
4. Shared routing, design tokens, and a single end-to-end vertical slice: priority card → client dossier → evidence → RM action.

### Implementation hand-offs

1. The **extra foundation task starts first** and gives every teammate a runnable path and sample payloads.
2. **Task 1** plugs its client-context and explanation output into that path. Its explanation must retain date, portfolio/holding, and event evidence—not only prose.
3. **Task 2A** publishes the insight/priority contract; **Task 2B** makes it comprehensible and usable in the shared experience.
4. **Task 3** consumes these inputs in the RM workflow, then adds review and advisory-action state. It should never recalculate signals already supplied by Task 2A.
5. The **project lead** validates the full flow against the product story and rubric. The technical owner keeps the shared branch/build working, but does not make product-scope decisions alone.

Every feature should be usable through the same path: `priority card → client dossier → evidence → RM action`. Avoid isolated dashboards that cannot feed a decision.

## Suggested solution structure

Start with a well-structured modular application rather than premature distributed services. Preserve clean boundaries so calculation, evidence, workflow, and language generation can be separated into governed services in a future bank deployment.

```text
data/ or repository CSVs          Source-of-truth synthetic data
clarity/backend/clarity/
  loaders/                        CSV/JSON parsing and normalised client view
  analytics/                      Deterministic calculations and rule checks
  signals/                        Evidence-backed risk, governance and planning checks
  contracts.py                    Stable Python contracts for the UI
  api.py                          Standard-library HTTP API and static-file server
  review.py                       JSON-backed RM decisions and append-only audit trail
clarity/frontend/
  src/                            Vite React TypeScript workbench
  components/                     Book, dossier, evidence, action and meeting components
  charts.tsx                      Purpose-built accessible SVG charts
  styles.css                      Hand-written private-bank design system
  types.ts                        TypeScript mirror of backend contracts
clarity/fixtures/                 Frozen payloads for demo and offline frontend work
clarity/state/                    Local persisted review/audit state (runtime only)
run_backend.py                    Root-level local API launcher
api/index.py                      Vercel Python Function entrypoint
```

### Selected current product stack

- **Frontend:** Vite 5, React 18 and TypeScript 5. The interface is built from purpose-specific components and hand-written CSS; do not migrate to Next.js, Tailwind, shadcn/ui, or another design system while this product already has a coherent one.
- **Visualisation:** lightweight, accessible inline SVG charts in `frontend/src/components/charts.tsx`. Do not add a charting dependency unless a required chart cannot be represented and tested clearly with the current primitives.
- **Frontend-to-backend integration:** browser `fetch`, a Vite development proxy from port 5173 to port 8000, and TypeScript types in `frontend/src/types.ts` that mirror `backend/clarity/contracts.py`. Contract changes must update both sides together.
- **Backend and analytics:** dependency-free Python standard library, including CSV/JSON loaders, deterministic analytics and `ThreadingHTTPServer`. Do not replace it with FastAPI or pandas unless a concrete capability—not framework preference—requires it.
- **Workflow persistence:** local mode uses JSON adapters under `clarity/state`; setting `DATABASE_URL` selects the shared versioned PostgreSQL adapter for review decisions, scenarios, meeting packages, follow-through, calibration, knowledge, integrations and AI audit metadata. Hosted PostgreSQL failures fail closed for writes and never silently fall back to JSON.
- **AI and external services:** deterministic wording remains the default. Optional server-side Gemini and OpenAI-compatible adapters can draft only a selected Meeting Studio surface; they cannot calculate, rank, approve, send, retrieve uncontrolled facts or execute actions. Provider keys stay in environment variables.
- **Runtime and delivery:** from the repository root use `python run_backend.py`; after `npm run build`, the API serves `frontend/dist` on port 8000. For hot reload, run the backend on port 8000 and Vite on port 5173. `api/index.py` is the Vercel function boundary, and `vercel.json` rewrites `/api/*` to it.
- **Hosted write control:** when `CLARITY_API_TOKEN` is configured, every POST requires `Authorization: Bearer <token>`. The UI stores the token only in browser `sessionStorage`; the role switcher remains a simulated demo permission model, not authentication. Hosted reset is disabled unless explicitly enabled.
- **Testing:** the current baseline is 104 backend tests and 24 frontend tests/build. PostgreSQL and deployed smoke tests are opt-in through `CLARITY_TEST_DATABASE_URL` and `CLARITY_DEPLOY_URL`; use isolated databases because the persistence tests reset workflow namespaces.

### Current implementation status and teammate handoff

The repository now contains the full Task 3 workflow, not only the original RM
decision screen:

- **Decision gates:** `new → opened → under_review → rm_edited/rm_reviewed → client_ready`, with controlled escalation, return, defer and dismiss paths. Client-ready requires evidence, suitability, tax/planning, data/model and human-decision gates plus RM rationale.
- **Scenario Studio:** bounded, deterministic Lau, Margarethe and Fong comparisons. Results retain inputs, assumptions, evidence and calculation version; they are arithmetic, not forecasts or recommendations.
- **Meeting Studio:** immutable package versions, four communication channels, preflight, evidence/caveat checks, simulated hand-off and optional guarded AI previews.
- **Follow-through and Audit:** tasks, referrals, meeting outcomes, evidence updates, re-evaluation requests, role-scoped views and unified source/system/user audit chronology.
- **Calibration Lab:** transparent priority-policy candidates and RM feedback; Compliance/Audit activation requires final feedback coverage for Lau, Margarethe and Fong.
- **Knowledge Library:** five approved synthetic internal guides with deterministic lexical search and citations. It never indexes raw client files and never injects references into decisions or client copy.
- **Integration Sandbox:** local inbound event validation/acceptance, evidence-update/re-evaluation creation, idempotent CRM/specialist work orders and model-readiness metadata with `training_eligible: false`.
- **Durable deployment layer:** local JSON remains the offline fallback; PostgreSQL is selected by `DATABASE_URL`, with advisory-locked schema bootstrap, optimistic revisions, append-only audit mirroring and fresh hosted seed state.

The canonical local demo is:

```text
Book → Client dossier → Evidence/context → Scenario or options
→ Decision gates → RM rationale → Client-ready
→ Meeting Studio → Follow-through/Audit
```

The three acceptance journeys are Lau (`CL-0014`), Margarethe (`CL-0003`)
and Fong (`CL-0017`). A feature is not demo-ready until it preserves evidence,
gate state, audit lineage and RM control for all three.

For local work, keep `DATABASE_URL` blank and use `python run_backend.py`.
For hosted validation, configure `DATABASE_URL`, `CLARITY_API_TOKEN` and
`CLARITY_ALLOW_DEMO_RESET=false` in Vercel; follow the hosted validation
runbook in `clarity/README.md`. Never commit database URLs, API tokens or AI
provider keys. Do not use a local JSON reset or a test database as the demo
database.

## Shared contracts

Define these shapes early so four people can work in parallel.

```text
Insight
  id, client_id, category, severity, priority_score, headline
  observed_facts[], client_relevance, suggested_next_step
  evidence[] {source_file, row_or_id, snapshot_date, field, value}
  assumptions[], suitability_checks[]
  status (new | opened | under_review | rm_edited | escalated
          | returned_for_review | rm_reviewed | client_ready | deferred | dismissed)

Client briefing
  client profile, objectives, portfolio roll-up, RM notes
  selected insights, explanation, scenario, meeting questions
  action options[], RM decision, audit trail

Action option
  id, insight_id, action_type, client_outcome, summary
  expected_impacts[], trade_offs[], assumptions[], blocked_by[]
  required_specialists[], suitability_checks[], rm_decision

Evidence
  source_file, source_row_or_id, as_of_date, scope
  field, raw_value, calculation_id, confidence, explanation

Audit event
  event_id, actor, action, timestamp, object_id
  prior_state, new_state, reason, evidence_version
```

Use stable `client_id`, `portfolio_id`, `instrument_id`, snapshot dates, and source IDs rather than display names as join keys. Keep computation outputs separate from AI wording so a judge can inspect the basis of each statement.

## Task 3 product roadmap — RM Intelligence Workbench

### Product objective

Task 3 turns the outputs of Tasks 1 and 2 into a controlled RM operating workflow. At any point, Priscilla should be able to answer:

1. **Who needs my attention first, and why now?**
2. **What can I substantiate from the client, portfolio, mandate, cash-flow and event evidence?**
3. **Which useful actions or conversations should I consider, and what are their trade-offs?**
4. **What is still unknown, unsuitable, or awaiting specialist review?**
5. **What did I decide, and what is the next accountable step?**

The unit of value is a **better client conversation**, not a trade. A trade may eventually follow the bank's normal advisory and execution controls, but Task 3 never executes one.

### Research synthesis and product decisions

The ChatGPT, Google and Gemini research is aligned on an AI-augmented, human-controlled RM cockpit. Use the following combined decisions:

| Research idea | Decision for Task 3 |
| --- | --- |
| Unified 360-degree client view | **Adopt.** Combine client objectives, life stage, risk, tax domicile, notes, household portfolios, liabilities, commitments and planned cash needs while preserving source and scope. |
| Prioritised book / air-traffic controller | **Adopt.** Present an actionable queue with transparent drivers and hard overrides. Task 2A calculates factors; Task 3 explains and operationalises them. |
| Human-in-the-loop next-best action | **Adopt and strengthen.** Offer contact, investigate, compare, escalate, defer or dismiss workflows. Require an RM decision and reason before client-ready status. |
| Explainable rebalancing and option comparison | **Adopt carefully.** Show two or three constrained options, before/after impacts and trade-offs. Never manufacture a security recommendation or optimal timing. |
| Life-event planning and what-if modelling | **Adopt in layers.** Begin with dated cash-flow and liquidity scenarios; add stochastic projections only when assumptions and validation are sufficient. |
| Draft client email/WhatsApp/proposal | **Adopt as editable draft.** Generate only from structured evidence. Provide copy/export or a simulated hand-off; never auto-send. |
| One-click trade execution or digital consent | **Reject for this product.** It weakens the RM-control and governance story and is unsupported by the challenge data. |
| Automated tax-loss harvesting, wash-sale logic and tax-alpha claims | **Do not implement as advice.** The book spans jurisdictions and lacks complete tax data. Surface tax-sensitive facts/data gaps and route to a qualified specialist. |
| Reinforcement learning, churn prediction, collaborative filtering, SHAP/LIME | **Future research only.** Twenty synthetic clients cannot train or validate these models. Transparent rules and evidence are more credible now. |
| Client value/AUM/revenue as priority drivers | **Exclude by default.** Priority should reflect urgency and client outcomes, not who is most profitable. Any commercial factor must be separately labelled and governed. |
| Live market/news retrieval and vector search | **Exclude from causal explanations.** `event_log.csv` remains authoritative. Retrieval may later support approved policy/knowledge documents, never override source controls. |
| Streaming AI and command-centre visuals | **Use selectively.** Responsive generation and polished interactions are valuable, but the UI should feel calm, private-bank appropriate, and evidence-led. |

### End-to-end information architecture

```text
Morning Book
  -> client priority card
  -> Client Action Canvas
       -> evidence and context
       -> scenarios and action options
       -> suitability / uncertainty gates
  -> Meeting Studio
       -> agenda, questions, talking points, editable communication
  -> RM Decision
       -> select, edit, escalate, defer or dismiss
  -> Follow-through
       -> owner, due date, review state and audit trail
```

Use persistent navigation for **Book**, **Client**, **Actions**, **Meetings**, and **Audit**. The main interaction should be a responsive master-detail layout: a compact priority queue on the left and the selected client's workspace on the right. Full-page routes remain addressable and shareable inside the application.

### Action taxonomy and workflow state

Every proposed next step must be one of five controlled action types:

| Action type | Purpose | Required output |
| --- | --- | --- |
| **Contact / prepare** | A time-sensitive exposure, cash need, life event or unanswered client question | Contact reason, urgency, meeting objective, questions and evidence pack |
| **Investigate / verify** | Data is missing, stale, conflicting or too uncertain for advice | Data gap, requested evidence, accountable owner and no-action guardrail |
| **Compare options** | A mandate, concentration, funding or goal tension has more than one reasonable response | Two or three options with impacts, trade-offs, assumptions and blocked checks |
| **Escalate** | Tax, credit, compliance, product or wealth-planning expertise is required | Specialist, referral reason, assembled evidence and open questions |
| **Defer / dismiss** | The issue is immaterial, accepted, already handled or not actionable | RM rationale, next review date and retained audit history |

The canonical state machine is:

```text
new -> opened -> under_review
under_review -> rm_edited -> rm_reviewed -> client_ready
under_review -> rm_reviewed -> client_ready
under_review -> escalated -> returned_for_review -> under_review
under_review -> deferred
under_review -> dismissed
```

`client_ready` means the brief has passed the workbench gates; it does not mean that advice was delivered or a transaction was authorised.

### Roadmap stage 0 — Domain, contracts and workflow backbone

Build the durable foundations Task 3 needs from the extra foundation task.

- Finalise typed `ClientContext`, `Insight`, `ActionOption`, `Evidence`, `SuitabilityGate`, `MeetingBrief` and `AuditEvent` schemas.
- Define household versus portfolio scope, `as_of_date`, base/reporting currency and source-version semantics.
- Implement the workflow state machine and append-only audit-event model independently of the UI.
- Create stable fixtures for Lau, Margarethe and Fong, including conflict, missing-data and specialist-escalation cases.
- Establish feature flags/fallbacks so the workbench remains fully demonstrable when LLM generation or an upstream module is unavailable.

**Exit criteria:** every Task 3 screen can render from versioned fixtures; invalid transitions fail; evidence and calculation versions survive every transition.

### Roadmap stage 1 — Morning Book and transparent triage

Create the RM's daily starting point, optimised for comprehension and action rather than alert volume.

- Show no more than five highest-priority items above the fold, followed by the full filterable book.
- Use priority bands such as **Immediate review**, **Prepare this week**, **Monitor**, and **Needs verification**.
- Each card shows `why now`, the client outcome at risk, two or three contributing factors, confidence/freshness and one primary next step.
- Support filters for category, urgency, booking centre, meeting/cash-need horizon, unresolved gate and workflow status.
- Provide visible hard-override reasons for near/breached collateral thresholds, unfunded confirmed cash needs and critical suitability failures.
- Never present a decimal score as truth. If a numeric score is exposed, show its factor breakdown and what would change the rank.

**Exit criteria:** an RM can identify and defend the first call without opening another system; no ranking relies on an unsupported attribute or hidden LLM judgement.

### Roadmap stage 2 — Client Action Canvas and evidence-first explanation

Turn a selected priority item into a complete, progressive decision workspace.

- Lead with the client's intended outcome and why action/review matters now.
- Present observed facts separately from interpretations, RM-note context and generated wording.
- Show household roll-up alongside portfolio/mandate scope; expose structured-product look-through and liquidity tiers where relevant.
- Provide a consistent evidence drawer with source file, row/ID, date, raw value, calculation and confidence.
- Surface stale valuations, note-data contradictions, missing tax lots and other imperfections as product states, not console errors.
- Add a contextual timeline combining portfolio snapshots, controlled events, transactions, cash needs, commitments and RM notes.

**Exit criteria:** every material number and causal statement is inspectable; the UI clearly distinguishes fact, calculation, assumption, client statement and AI draft.

### Roadmap stage 3 — Scenario and Action Option Studio

Help the RM explore choices without pretending there is one model-approved answer.

- Offer a baseline plus two or three action options relevant to the insight: reserve liquidity, adjust exposure, change funding order, obtain documents, involve a specialist, or accept/monitor a deviation.
- Compare before/after allocation, concentration, cash buffer, mandate position, lending value/LTV and goal coverage when the data supports them.
- Show assumptions as editable inputs with clear units and dates; recalculate via deterministic Task 2 services.
- Display trade-offs across client objective, risk, liquidity, tax uncertainty, cost and reversibility.
- Allow scenario save/compare and retain the evidence/calculation version used.
- For life events, build a dated cash-flow and funding timeline first. Add Monte Carlo or probability-of-goal outputs only with documented return/inflation models, reproducibility, sensitivity analysis and validation.

**Exit criteria:** the RM can explain why options differ, inspect every assumption and choose no action; unavailable tax or product data blocks false precision.

### Roadmap stage 4 — Suitability, uncertainty and specialist gates

Make governance an active part of the experience rather than a disclaimer.

Before an option can become client-ready, evaluate five gates:

1. **Evidence:** every financial statement has a source/date/calculation; 2026 event claims use only `event_log.csv`.
2. **Suitability:** mandate, risk profile, objectives, liquidity, service model, concentration and product knowledge/experience are passed or visibly unresolved.
3. **Tax and planning:** tax domicile is used; missing tax lots/jurisdictional facts block tax conclusions; specialist referral is available.
4. **Data and model:** stale, missing or conflicting data, calculation version, confidence and AI-draft status are visible.
5. **Human decision:** RM selection/edit/defer/dismiss includes reason, timestamp, actor and evidence version.

Design unresolved gates as useful next steps—request a document, confirm a preference, contact credit, or refer to tax/wealth planning—not as dead-end error messages.

**Exit criteria:** the application cannot transition to `client_ready` while a mandatory gate is unresolved, and overrides require an authorised role plus a recorded rationale.

### Roadmap stage 5 — Meeting Studio and client-ready communication

Convert approved intelligence into a high-quality conversation package.

- Generate an editable meeting objective, agenda, discovery questions, talking points, option summary, risk/caveat section and follow-up tasks.
- Support tone/channel variants such as concise email, formal briefing, call notes or client-app copy, while keeping the same approved facts.
- Give the RM fine-grained control: edit, regenerate only a selected section, compare draft versions, restore the original and record final changes.
- Cite internal evidence in the RM view; translate it into plain language in the client view without exposing internal IDs unnecessarily.
- Add a preflight preview showing audience, channel, approved facts, unresolved caveats and prohibited claims.
- End with copy/export or simulated hand-off. Do not auto-send, collect digital consent or execute a trade from the prototype.

**Exit criteria:** the final communication contains no uncited numerical claim, no unsupported causal language and no action beyond the RM's approved option.

### Roadmap stage 6 — Collaboration, follow-through and audit

Make the workbench useful after the meeting, not only during preparation.

- Assign specialist referrals and follow-up tasks with owners, due dates, evidence and status.
- Record meeting outcomes, client preference changes and requested documents without rewriting the historical insight.
- Re-evaluate affected insights when new data arrives and show what changed between evidence versions.
- Provide an audit timeline for source ingestion, calculation, AI draft, RM edits, gate decisions, referrals and final disposition.
- Add role-based views for RM, specialist, compliance/audit and product operations, with least-privilege access.
- Separate source-data logs, model-generation logs and user-decision logs so accountability remains clear.

**Exit criteria:** another authorised person can reconstruct what the system knew, what it suggested, what the RM changed and why the final state was reached.

### Roadmap stage 7 — Advanced intelligence after validation

Only add advanced modelling when data volume, labels, governance and evaluation justify it.

- Calibrate priority weights from RM feedback and observed false-positive/false-negative reviews while preserving visible rules and hard overrides.
- Add approved-document retrieval for policy and product knowledge with citations, permission filters and document-version controls.
- Explore predictive drift, engagement/churn or next-best-action models only with representative training data, bias review, out-of-sample evaluation and explainability testing.
- Add stochastic goal planning, tax optimisation or portfolio optimisation only as specialist-governed modules with complete inputs and jurisdiction-specific rules.
- Integrate bank systems through APIs and events while retaining the workbench contracts, idempotent actions and complete audit trail.

**Exit criteria:** an advanced feature must outperform the deterministic baseline on defined measures, remain explainable to an RM, and pass model-risk, privacy, security and suitability review.

### Three anchor journeys for product acceptance

- **Lau (CL-0014):** proves transparent urgency, correlated exposure, collateral/liquidity scenario comparison, credit escalation and RM-controlled action selection.
- **Margarethe (CL-0003):** proves human context, mandate/risk conflict, missing-tax-data blocking, sensitive meeting preparation and specialist referral.
- **Fong Family Office (CL-0017):** proves household-versus-sleeve reasoning, commitments timeline, gated-liquidity treatment, multi-stakeholder planning and follow-through.

Build every roadmap stage against all three journeys. A feature is not complete if it works only for the easiest client.

### Task 3 quality measures

Track product quality without inventing financial-performance claims:

- **Decision readiness:** percentage of priority items with a clear next step, owner and due date.
- **Traceability:** percentage of material facts with valid evidence and `as_of_date`; target 100%.
- **RM control:** percentage of client-ready briefs explicitly reviewed or edited by an RM; target 100%.
- **Gate integrity:** zero client-ready transitions with unresolved mandatory gates.
- **Priority usefulness:** RM agreement with top-ranked items and false-alert/dismissal reasons.
- **Preparation efficiency:** median time from opening a card to a reviewed meeting brief.
- **Client relevance:** percentage of briefs that explicitly connect the issue to a stated objective, constraint or life event.
- **Accessibility and resilience:** keyboard-complete core flow, readable charts/tables, deterministic fixture fallback and graceful AI/API failure states.

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

## Cross-team delivery sequence

1. Read `clients.csv`, `rm_notes.json`, and `event_log.csv`; validate the three anchor journeys against the source records and calculations.
2. Establish the shared foundation, contracts, evidence rules, design primitives and fixture fallback.
3. Complete Lau as the first vertical slice: source data → deterministic signal → evidence → client context → options/gates → RM decision → meeting brief.
4. Generalise every layer for Margarethe and Fong; remove assumptions that only work for Lau.
5. Expand breadth across the full book only after the three anchor journeys pass their acceptance criteria.
6. Add governance, accessibility, failure recovery, audit reconstruction and role-based access as product capabilities, not presentation-only claims.
7. Validate calculations and content independently, test the complete workflow, and rehearse a concise judge journey that exposes evidence and RM control.

## Definition of done

The demo is ready when Priscilla can identify who to call first, open a defensible explanation of what changed, see the client-specific risk/opportunity and trade-offs, edit or reject a proposed next step, and leave with a client-ready meeting brief. A judge should be able to see both the human benefit and how the design could operate inside a regulated bank.
