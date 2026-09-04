# SingHacks 2026 Project Context

This context was collected from the current Codex chat and the files in this workspace. No separate chat transcript named "Implement Singhacks 2026 project" was available in the repo; paste that transcript or add it as a file if it should be folded into this brief.

## Challenge

Build an AI-powered wealth intelligence experience for Julius Baer Relationship Manager Priscilla Ong. The product should help her move from static portfolio monitoring to client-ready advisory intelligence:

1. What is happening in a client's portfolio?
2. What could happen next?
3. What actions should the RM consider?

The target user is the RM, not the end client. Recommendations should support human decision-making, remain explainable, and be suitable for a regulated private-bank context.

## North Star

Build the intelligence layer between portfolio data and the Relationship Manager.

The best demo should surface a small number of defensible, personalized insights rather than show every chart possible. The README explicitly recommends going deep on two or three clients instead of shallow across all twenty.

## Dataset Facts

- All data is synthetic.
- The in-dataset "today" is 2026-08-26.
- Event and market context must be grounded in `event_log.csv`, not model memory.
- The repo currently stores CSV/JSON files at the workspace root, although the README and quickstart text refer to `data/` and `docs/`.
- Current dataset size:
  - `clients.csv`: 20 clients
  - `portfolios.csv`: 24 portfolios
  - `holdings.csv`: 1,015 position rows across dated snapshots
  - `instruments.csv`: 62 instruments
  - `mandates.csv`: 48 mandate allocation rows
  - `transactions.csv`: 393 transactions
  - `credit_facilities.csv`: 5 facilities
  - `commitments.csv`: 5 private-market commitments
  - `planned_cash_needs.csv`: 20 planned needs
  - `market_context.csv`: 115 market observations
  - `event_log.csv`: 16 controlled events
  - `rm_notes.json`: 28 RM notes

## Time Dimension

Holdings are provided at five snapshots:

- 2025-12-31: baseline
- 2026-02-27: before Middle East conflict
- 2026-03-31: after Strait of Hormuz closure
- 2026-06-30: after June technology drawdown
- 2026-08-26: current date in dataset

Implementation should compare snapshots. Treating holdings as static loses most of the advisory value.

## Important Joins

- `clients.client_id -> portfolios.client_id -> holdings.portfolio_id`
- `holdings.instrument_id -> instruments.instrument_id`
- `portfolios.mandate_code -> mandates.mandate_code`
- `holdings.snapshot_date -> market_context.snapshot_date`
- `credit_facilities.collateral_portfolio_id -> portfolios.portfolio_id`
- `rm_notes[].client_id -> clients.client_id`

## Governance Constraints

- `event_log.csv` is the authoritative source for 2026 events.
- Insights must show supporting evidence: holdings, mandate, notes, market context, event log, cash needs, or credit data.
- Recommendations should be framed as RM-reviewed actions, not automatic investment advice.
- Suitability matters: mandate, risk profile, objectives, tax domicile, liquidity needs, and RM notes can override generic portfolio logic.
- RM notes may disagree with structured data; those tensions are demo opportunities.

## Product Direction

A strong build path is an RM Intelligence Workbench with:

- Prioritized client alerts across Priscilla's book.
- Client drilldown showing portfolio change across snapshots.
- Evidence-backed explanation cards that link market events to affected holdings.
- Risk checks for concentration, mandate drift, liquidity, collateral, and sustainability exclusions.
- Suggested next actions with rationale and "review / edit / dismiss" RM controls.
- Client conversation prep that turns analysis into a concise talking track.

Avoid making a generic portfolio dashboard. Existing tools already show valuations and allocation; this project should explain what matters and why.

## High-Potential Demo Storylines

### CL-0002 Ravi Chandrasekaran

- UHNW founder with USD 46.7m AUM, high liquidity needs, Growth risk profile.
- Secondary share sale expected around Q4 2026; planned tax and trust funding needs start in late 2026 / early 2027.
- RM note says he does not want to sell listed positions and is comfortable increasing Lombard borrowing.
- Lombard facility CF-0001 is under pressure: LTV peaked at 75.64% on 2026-06-30 against a 75% trigger and is still high at 73.71% on 2026-08-26.
- Event link: 2026-06-05 technology drawdown and collateralized lending channel.
- Demo angle: "founder concentration plus collateral stress plus near-term liquidity need."

### CL-0003 Margarethe Voss-Brenner

- HNW inherited portfolio, Conservative risk profile, recently widowed, low risk comfort according to RM notes.
- Client says she wants something safe and boring.
- German inheritance tax instalment of EUR 3.4m is due from 2026-10-01 to 2026-12-31.
- RM note says the transferred portfolio is not conservative.
- Event link: Middle East conflict, energy shock, rate moves, fixed income pressure.
- Demo angle: "suitability mismatch after inheritance with a confirmed tax cash need."

### CL-0001 Hartono Wijaya Kusuma

- UHNW second-generation wealth, USD 46.6m AUM, objective is to diversify away from family coal/energy business.
- RM note says he resisted reducing legacy shareholding and later asked for more energy exposure.
- Planned SGD 9m property deposit in early 2027.
- Lombard facility CF-0005 previously breached margin trigger: 78.5% LTV on 2025-12-31 vs 70% trigger, now 59.15%.
- Event link: energy rally and Strait of Hormuz events.
- Demo angle: "client objective says diversify away from family energy risk, but behavior increases the same exposure."

### CL-0005 Aishah binti Rahman

- Sustainable Balanced mandate.
- RM note says client believes the portfolio is fully aligned with family sustainability policy and was unaware of an energy fund holding.
- Mandate notes include binding exclusions: thermal coal, oil and gas E&P, controversial weapons, tobacco, unresolved deforestation controversies.
- Demo angle: "explainable sustainability breach / exception workflow."

### CL-0017 Fong Enterprises Family Office

- Largest client by AUM at about USD 87.9m across three portfolios.
- Has USD 15.8m planned outstanding private markets commitments and USD 14m uncalled in Meridian Private Equity Fund VII.
- Multi-generational family office with education funding and private-market liquidity planning needs.
- Demo angle: "household-level view across multiple portfolios where risks are invisible if each account is viewed alone."

## Other Notable Risk Hooks

- CL-0014 Lau Chi Ming: HKD 60m redevelopment equity contribution due from 2026-11-01; Lombard LTV is 69.41% vs 70% trigger.
- CL-0006 Nguyen Thi Bao Tran: USD 5m university fees and USD 3m private equity capital calls, both beginning in 2026; has USD 3m uncalled PE commitment.
- CL-0007 Alistair Pemberton-Hale: USD 12m charitable foundation endowment expected in 2027.
- CL-0011 Tan Boon Huat: SGD 2.8m succession-related cash need; property-backed term loan is fully utilized.

## Suggested MVP

1. Data ingestion layer
   - Load CSV/JSON files from repo root.
   - Normalize dates and current snapshot.
   - Build joined client, portfolio, holding, instrument, mandate, notes, events, facilities, commitments, and cash-needs views.

2. Insight engine
   - Snapshot delta: portfolio AUM and holdings changes from 2025-12-31 to 2026-08-26.
   - Event attribution: map holdings to `event_log.primary_transmission` channels by asset class, sector, region, and instrument metadata.
   - Rule checks: mandate allocation bands, single-position concentration, sustainability exclusions, facility LTV, upcoming cash needs, liquidity tiers, uncalled commitments.
   - Evidence bundle: each insight stores the rows and assumptions that justify it.

3. RM workbench UI
   - Book-level priority queue: clients sorted by urgency and explainability.
   - Client detail page: timeline, current exposures, triggered insights, supporting evidence, and recommended RM actions.
   - Conversation prep: concise script, data-backed talking points, open questions, and compliance-safe caveats.

4. Demo narrative
   - Open on Priscilla's book and ranked alerts.
   - Drill into Ravi for collateral stress and founder/liquidity risk.
   - Drill into Margarethe for suitability and inheritance-tax cash need.
   - Optional third story: Aishah for sustainable mandate governance or Hartono for contradictory diversification behavior.

## Implementation Notes

- `requirements.txt` only lists `pandas`, which is not installed in the current environment.
- `quickstart.py` appears copied from a layout with `starter/quickstart.py` and `data/`; in this repo root it will not load files without path changes or a `data/` folder.
- README and DATA_DICTIONARY links refer to `data/` and `docs/`, but actual files are at root.
- Some README characters display as mojibake in this shell, but the core content is readable.

## Open Questions

- What stack should the team use for the MVP: Streamlit, Next.js, Flask/FastAPI, or another stack?
- Is the expected output a demo app, slide deck, written concept, or all three?
- Should the project optimize for hackathon speed or production-style architecture?
- If there is a prior chat transcript for "Implement Singhacks 2026 project", it should be added so this context can be updated with implementation decisions already made.
