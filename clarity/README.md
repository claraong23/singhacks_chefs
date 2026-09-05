# Clarity — the RM's morning intelligence brief

SingHacks 2026, Julius Baer challenge. An RM-first wealth intelligence layer that
turns a fragmented 20-client book into a defensible next action:

```
client and portfolio context → evidence-backed signal → RM review → client-ready action
```

Clarity does not trade, does not advise, and does not replace Priscilla Ong. It
tells her who to call first, why, what to say, and what she would have to accept
if she acted — and it makes her approve, edit or reject every one of those before
anything reaches a client.

---

## Run it

Two commands. No install step for the backend — it is standard library only.

```bash
# 1. the engine and API  (from clarity/backend)
python -m clarity.api                    # http://127.0.0.1:8000

# 2. the UI  (from clarity/frontend, first time only: npm install)
npm run dev                              # http://127.0.0.1:5173
```

`npm run build` writes `frontend/dist`, which the API serves itself — so for the
demo, one process on port 8000 is the whole product.

No API keys, no external calls, no data leaves the machine.

### Durable hosted mode

Local mode is the default: all mutable Task 3 workflow records use JSON files
under `clarity/state`. To deploy durable state on Vercel, set `DATABASE_URL` and
`CLARITY_API_TOKEN` in the deployment environment. With a database configured,
decisions, saved scenarios, meeting packages, follow-through, calibration,
knowledge lifecycle, integration records, and AI audit metadata use versioned
PostgreSQL state; the source CSVs remain read-only and AI previews still expire
in memory after 15 minutes.

Hosted reads remain public. The UI prompts an RM to enter the shared demo token
to unlock POST actions for that browser session; the token is never bundled into
the frontend, committed, or stored beyond the session. The visible role switcher
is still a demo permission model, not real sign-in. Hosted reset is disabled
unless `CLARITY_ALLOW_DEMO_RESET=true` is explicitly configured.

### Without a browser

Every screen has a terminal equivalent, which is the fallback if the demo laptop
misbehaves:

```bash
python -m clarity.cli book               # the ranked book
python -m clarity.cli client CL-0014     # one full dossier
python -m clarity.cli brief CL-0014      # the meeting brief and draft follow-up
python -m clarity.cli fixtures           # freeze JSON payloads into clarity/fixtures
```

### Tests

```bash
cd clarity/backend && python -m unittest discover -s tests -t .
```

100 backend tests. They check the things a judge would push on: that holdings reconcile to
`portfolios.aum_<date>` at all five snapshots for all 24 portfolios, that the FX
direction follows each pair's quoting convention, that the attribution
decomposition sums exactly to the change in value, that the single-position limit
is only applied to instruments flagged `concentration_limit_applies`, that the
loan-to-value repayment arithmetic actually lands on its target, and that no
signal silently fails.

---

## What it does

### 1. The book — who to call first

Twenty clients ranked by a **published formula**, not by an opaque score:

```
priority = 0.45 × severity + 0.30 × materiality + 0.25 × urgency      (0–100)
```

Materiality is the share of *household* wealth affected, capped at 30%. Urgency
is days to the driving date, banded. Every row shows the reasons behind its
position, and the weights are stated so they can be argued with.

### 2. The dossier — four questions in order

| Tab | Question |
|---|---|
| **Why now** | The ranked findings, each with figures, evidence and reviewable options |
| **What changed and why** | Attribution across the five snapshots, tied to `event_log.csv` |
| **Exposure and mandate** | Look-through concentration, themes, mandate bands and limits |
| **Liquidity and collateral** | What is actually sellable, what is pledged, and LTV through time |
| **Scenario Studio** | Evidence-backed baseline-versus-option comparison for Lau, Margarethe, and Fong; current-state arithmetic only |
| **Meeting Studio** | Versioned, evidence-backed meeting packages and client-ready drafts; copy/simulated hand-off only after preflight |

### 3. The decision — the RM stays in charge

Each finding carries two to four options. Every option states how it would work,
what it costs, which suitability checks it clears, and what it depends on. The RM
selects one and approves, marks the finding reviewed, or dismisses it — and can
rewrite the next step in her own words. Every decision is written to an audit
trail with actor, timestamp, the previous state and the engine's original wording.
Before anything can become client-ready, evidence, suitability, tax/planning,
data/model quality, and RM rationale must all pass. Saved Scenario Studio
comparisons retain their bounded inputs and calculation version; they cannot
bypass a decision gate or execute a transaction.

### 4. Meeting Studio — turn an approved finding into a conversation

A package can be created only for one `client_ready` finding. It freezes the
selected option, evidence version, optional scenario calculation and passing
gate snapshot, then creates editable internal sections plus concise email,
formal briefing, call-notes and client-app variants. Every edit appends a
version. Communication preflight rechecks the client-ready source, cited
evidence, required caveats, prohibited claims and reporting language before an
RM can copy the draft or record a **simulated** hand-off. Nothing is sent.

### 5. Follow-through and Audit — make the meeting accountable

The RM can assign evidence-linked tasks and specialist referrals with owners and
due dates, then record client statements, requested documents and meeting
outcomes. Product Operations may record newly received evidence, which creates a
tracked re-evaluation request without changing source files or historical
decisions. A simulated least-privilege role switcher demonstrates what an RM,
specialist, Compliance/Audit user and Product Operations user can see or change.
The Audit Console keeps source-data, deterministic system and user-decision
activity visibly separate.

### 6. Calibration Lab — improve the queue without an opaque model

Final RM dispositions collect a governed usefulness and urgency assessment. An
RM can compare baseline, urgency-first, materiality-first, or bounded custom
weights against the same deterministic signal set. Compliance/Audit can activate
a submitted candidate only after final feedback covers Lau, Margarethe and Fong.
The policy version, feedback, evaluation, and approval stay append-only in the
audit trail; no threshold, evidence, historical decision, recommendation, or
client-ready gate is changed.

### 7. Knowledge Library — governed reference, never a client-data search

The global **Knowledge** view provides deterministic lexical search over five
approved, fictional internal reference guides: evidence/data quality,
collateral/liquidity, mandate/suitability, tax/planning escalation and
private-markets commitments/liquidity. Every result includes its document,
version, effective date, source reference, exact matched fields and a bounded
excerpt. It is visibly labelled synthetic prototype material—not Julius Baer
policy, client evidence, advice, a tax conclusion or a recommendation.

Only approved versions are searchable. Product Operations can author drafts and
revisions; Compliance/Audit must approve or reject a submitted version with a
rationale. Approved revisions supersede rather than overwrite prior versions.
Search excludes all CSVs, RM notes, meeting packages, client statements and
external sources, and it cannot inject wording into a decision, scenario,
meeting package or client communication. Action Review and Meeting Studio open
only safe category shortcuts; retrieval activity and document lineage appear in
the unified audit timeline.

### 8. Optional AI Meeting Drafting — controlled rewrite, never autonomous advice

Meeting Studio can optionally request a rewrite of one current internal section
or client-facing channel. The primary adapter is Google Gemini; an
OpenAI-compatible endpoint is also supported. Both run server-side, are disabled
by default, and receive only the selected approved package text—not raw CSVs,
RM notes, the full dossier, knowledge results, or web data.

Every candidate is an in-memory preview that expires after 15 minutes. It is
screened for source continuity, retained evidence, new numerical/date/currency
claims, product claims, prohibited recommendation/execution/tax/guarantee/
redemption wording, and (for client copy) required caveats. Only an RM can apply
a passing preview with a rationale. Applying creates an immutable, AI-provenanced
package version and requires preflight again; nothing is sent or executed.

To opt in locally, configure one provider before starting the Python service:

```powershell
# Gemini
$env:CLARITY_AI_PROVIDER = "gemini"
$env:GEMINI_API_KEY = "your-local-key"
$env:CLARITY_GEMINI_MODEL = "your-approved-model"

# Or an OpenAI-compatible endpoint
$env:CLARITY_AI_PROVIDER = "openai_compatible"
$env:CLARITY_OPENAI_COMPATIBLE_BASE_URL = "https://provider.example/v1"
$env:CLARITY_OPENAI_COMPATIBLE_API_KEY = "your-local-key"
$env:CLARITY_OPENAI_COMPATIBLE_MODEL = "your-approved-model"
```

Keys, provider URLs, prompts, and candidate text never enter the browser or
durable audit log. The audit retains only actor, source package/version, target,
provider/model identifier, prompt-template version, candidate digest, and
guardrail outcomes.

The Meeting Studio flag does not enable the older Task 1 attribution experiment;
that separate path remains deterministic unless its own
`CLARITY_ATTRIBUTION_AI_ENABLED=true` flag is deliberately set.

### 9. Integration Sandbox — replayable operating-loop boundary

The global **Integration Sandbox** demonstrates a governed connection boundary
without connecting to a bank system. Product Operations can validate a synthetic
inbound event, then accept or reject it with a rationale. Acceptance creates the
same append-only evidence update and re-evaluation request used by Follow-through;
it never changes raw CSVs or historical insight, scenario, decision, or meeting
snapshots. Replaying the same source-system/event ID returns the original event.

An RM can prepare and simulate-dispatch a CRM or specialist-queue work order from
an existing task, referral, meeting package, or client-ready finding. A simulated
external reference is recorded locally only; no CRM call, client message, trade,
or execution occurs. Assigned specialists may acknowledge only their own queue
work. The unified audit timeline preserves source/schema lineage, replay keys,
Operations disposition, downstream links, and dispatch/acknowledgement history.

Integration audit events also carry a fixed deterministic feature-schema version
and `training_eligible: false`. That is model-readiness metadata, not a model:
the synthetic 20-client book has neither representative outcomes nor completed
bias and out-of-sample evaluation, so it does not alter signals, rankings, or
decisions.

---

## What it found

These are the outputs, not the design intentions. Each was computed and is cited
in the UI.

| Client | Finding |
|---|---|
| **CL-0014 Lau Chi Ming** | Lombard facility at 69.41% LTV against a 70% trigger — **0.59 points of headroom**, and a 0.8% fall in collateral produces a margin call. He owes a confirmed HKD 60m by mid-2027 but can withdraw **USD 90,754** without breaching it. Golden Harbour Properties is 29.5% of his household across *three* wrappers — shares, a subordinated perpetual, and an accumulator that obliges further buying below strike — and Hong Kong property in total is 49%, which is also his business. |
| **CL-0002 Ravi Chandrasekaran** | Facility breached its 75% trigger at the half-year and was **cured by the market, not by an action**. 68% of his wealth is an unlisted holding carried at a **September 2025 mark**, 330 days stale. |
| **CL-0017 Fong Family Office** | Liquid in aggregate, but the **Alternatives Sleeve** that owes USD 15.8m of uncalled commitments holds USD 900k of cash. `planned_cash_needs` CN-016 restates the same USD 15.8m already in `commitments.csv`; counted once, and the duplication is reported. |
| **CL-0003 Voss-Brenner** | Profiled Conservative after inheriting a portfolio that is 83% risk assets — 71% equity against a 30% ceiling — with EUR 3.4m of German inheritance tax confirmed due before year end. Her USD decline this year is mostly **currency translation**, not markets, and the UI says so rather than blaming a theme. |
| **CL-0005 Aishah binti Rahman** | A **discretionary** Sustainable Balanced mandate with binding exclusions holds 21% in instruments flagged `sustainability_excluded`. The bank picked them. Her RM note says she believes the policy is being applied. |
| **CL-0001 Hartono Wijaya Kusuma** | Facility breached its trigger at 78.5% in December and 75.7% in February, then fell to 58.9% with **no repayment at all** — the energy rally lifted the collateral. Resolved by the market, and it would return if the move reversed. |

Three data artefacts are surfaced rather than worked around: the stale unlisted
mark, HKD 2m of drawdown on CF-0002 that `transactions.csv` does not explain, and
the commitments double count. A fourth is flagged as unverifiable: `SYN-SP-0506`
references "three Asian banking majors" the dataset never names, so the issuers
behind that note are reported as unknown instead of guessed.

---

## How it is built

```
clarity/
  backend/clarity/
    config.py          Dates, thresholds, conventions. Nothing inferred.
    contracts.py       Insight, Evidence, ActionOption, scenario and meeting contracts
    loaders.py         CSV/JSON → normalised, indexed, coerced once
    analytics/         Deterministic calculation, no narrative
      valuation.py       household roll-up across every portfolio
      lookthrough.py     issuer and theme exposure through wrappers
      mandate.py         bands, single-position limits, exclusions
      collateral.py      LTV through time, cure attribution, reconciliation
      liquidity.py       obligations vs what can actually be sold
      attribution.py     price / FX / flow decomposition
      income.py          run-rate income and cost of the facility
      event_impact.py    event → theme → holdings → affected-client ranking
    signals/           One file per family of checks; each returns Insights
    actions.py         Reviewable options, solved from the data
    scenarios.py       Bounded current-state comparisons for the anchor journeys
    scenario_store.py  Saved-scenario JSON adapter
    meeting.py         Deterministic meeting packages and communication preflight
    meeting_store.py   Versioned Meeting Studio JSON adapter
    followthrough.py   Controlled post-meeting workflow validation
    followthrough_store.py Local tasks, referrals, outcomes and source-update adapter
    knowledge_store.py Local approved-reference lifecycle and lexical retrieval adapter
    ai_drafting.py    Optional provider adapters, ephemeral draft preview and audit metadata
    integration_store.py Local inbound-event and outbound-work-order adapter
    audit.py           Unified origin-labelled audit reconstruction
    brief.py           Legacy deterministic brief used by the terminal fallback
    review.py          RM decisions, changed-alert reopening and audit trail
    postgres_review.py Optional deployed PostgreSQL review adapter
    dossier.py         Assembly into stable JSON
    api.py             Standard-library HTTP API
    cli.py             Terminal demo and fixture export
  frontend/            Vite + React + TypeScript, hand-written CSS, no UI kit
  fixtures/            Frozen payloads for the demo clients
  docs/                Method, assumptions, demo run sheet
```

**Why no pandas, FastAPI or charting library.** The dataset is 1,015 holdings
rows. Standard library covers it, the analytics import cleanly into a notebook, a
test, the API or a Streamlit fallback, and there is no install step to fail on a
strange laptop the morning of a demo. Swapping `api.py` for FastAPI is mechanical
— the payloads do not move, because `dossier.py` returns plain dictionaries.

**Where AI sits.** Deliberately at the edge. Every number, ranking, breach and
option in this repo is deterministic Python, and every narrative sentence is
assembled from already-computed facts with a citation attached. Nothing is passed
to a model as "here is a portfolio, what do you think". That is the difference
between an explanation that survives a compliance review and one that merely
sounds plausible — and it is the only way the evidence drawer can promise that
each claim traces to a row.

---

## Contracts

The interface between the four workstreams is `backend/clarity/contracts.py`,
mirrored in `frontend/src/types.ts`. Change both together.

```
Insight        id, client_id, category, severity, priority_score, priority_reasons[]
               headline, summary, observed_facts[], client_relevance, suggested_next_step
               evidence[] {source_file, row_or_id, field, value, snapshot_date, note}
               assumptions[], suitability_checks[], confidence, open_questions[]
               related_event_ids[], portfolio_ids[], instrument_ids[], amount_usd, status

ActionOption   id, label, rationale, mechanics[], trade_offs[]
               suitability_checks[], requires[], estimated_impact, evidence[]

ScenarioResult template_id, client_id, insight_id, option_id, inputs{}
               metrics[] {baseline, scenario, unit, available}, assumptions[]
               evidence[], blocked_checks[], calculation_version

MeetingBrief   purpose, talking_points[], questions_to_ask[], relationship_context[]
               contradictions[], do_not_say[], draft_follow_up, provenance

MeetingPackage id, client_id, insight_id, source{option, scenario, evidence, gates}
               current_version, versions[] {sections[], communications[]}, handoffs[]
Communication  channel, content, evidence_refs[]; preflight {can_hand_off, checks[]}

FollowUpTask / SpecialistReferral  client_id, insight_id?, owner_role, due_date, status,
                                   evidence_refs[], history[]
EvidenceUpdate / ReevaluationRequest source_ref, affected_insight_ids[], immutable history
AuditTimelineEvent timestamp, origin {source_data|system|user_decision}, object, actor
PriorityPolicy  weights {severity, materiality, urgency}, versioned lifecycle and approval history
RMFeedback      final disposition usefulness, urgency assessment, rationale, policy and evidence version
```

Two rules hold everywhere: **no claim without a citation**, and **computed
numbers never share a field with generated prose**.

### Adding a signal

```python
from clarity.signals.base import SignalContext, priority, signal

@signal("my_check")
def my_check(ctx: SignalContext):
    if not something_is_wrong(ctx):
        return
    score, reasons = priority(Severity.HIGH, materiality_pct=12.0, days_until=45)
    yield Insight(id=f"{ctx.client_id}-my-check", ..., evidence=[...])
```

Register it by importing the module in `signals/__init__.py`. It appears in the
book automatically, with no other change. A check that raises does not take down
the book — it surfaces as a visible engine error against that client instead of
silently dropping findings.

### Where each workstream plugs in

The seams are already cut, so four people can work without colliding.

| Workstream | Owns | Touches |
|---|---|---|
| **Task 1 — Client context and explanations** | `analytics/attribution.py`, `signals/explain.py`, the *What changed and why* tab | Extend `THEMES` in `analytics/lookthrough.py` and `THEME_MARKET_SERIES` to explain a new driver |
| **Task 2a — Risk rules and evidence** | `signals/risk.py`, `signals/governance.py`, `signals/planning.py`, `analytics/` | Add a `@signal`; it appears in the book with no other change |
| **Task 2b — UI and design system** | `frontend/src/components/`, `frontend/src/styles.css` | Only `types.ts` couples you to the backend; `clarity/fixtures/*.json` lets you work with the API stopped |
| **Task 3 — Workbench and action** | `actions.py`, `meeting.py`, `review.py`, `dossier.py`, `api.py` | Owns the contracts and the demo narrative |

## API

| Route | |
|---|---|
| `GET /api/book` | The ranked book |
| `GET /api/clients/<id>` | One full dossier |
| `GET /api/events` | `event_log.csv`, normalised with stable ids |
| `GET /api/events/<id>/impact` | Ranked clients, mapped exposure and explicit sensitivity for one event |
| `GET /api/meta` | Snapshots, categories, thresholds, load warnings |
| `GET /api/audit` | Unified origin-labelled audit timeline; supports client and origin filters |
| `GET /api/priority-policies` | Active policy, candidate policies, and curated transparent templates |
| `GET /api/priority-policies/<id>/evaluation` | Deterministic candidate-versus-active shadow ranking |
| `POST /api/priority-policies` and `/<id>/(revise|submit|approve|reject)` | Governed RM proposal and Compliance/Audit lifecycle |
| `GET /api/knowledge-documents` | Role-scoped approved reference register and controlled version visibility |
| `GET /api/knowledge-documents/<id>` | One permitted document with immutable version history |
| `GET /api/knowledge/search?q=&category=&tag=` | Approved-only lexical reference search with citation provenance |
| `POST /api/knowledge-documents` and `/<id>/(revise|submit|approve|reject)` | Product Operations authoring and Compliance/Audit lifecycle |
| `GET /api/clients/<id>/scenario-templates` | Supported bounded comparisons for an anchor client |
| `GET /api/clients/<id>/scenarios` | Saved RM scenario comparisons |
| `POST /api/clients/<id>/scenarios/evaluate` | Evaluate `{template_id, insight_id, option_id, inputs}` |
| `POST /api/clients/<id>/scenarios` | Re-evaluate and save a named comparison |
| `POST /api/insights/<id>/decision` | `{status, rm_note, selected_option_id, edited_next_step}` |
| `POST /api/insights/<id>/narrative` | Optional grounded OpenAI wording for one computed insight |
| `GET /api/clients/<id>/meeting-packages` | Versioned packages for one client |
| `POST /api/insights/<id>/meeting-packages` | Create a package from one client-ready finding |
| `POST /api/meeting-packages/<id>/versions` | Save an evidence-linked section edit |
| `POST /api/meeting-packages/<id>/(regenerate|restore|preflight|handoff)` | Controlled package lifecycle operations |
| `GET /api/ai-drafting/status` | Safe local availability of the optional server-side drafting adapter |
| `POST /api/meeting-packages/<id>/ai-drafts` | Generate a guarded, ephemeral RM preview for one package surface |
| `POST /api/meeting-packages/<id>/ai-drafts/<draft_id>/apply` | RM-only, rationale-required immutable application of a passing preview |
| `GET /api/follow-through?role=<role>` | Role-scoped local tasks, referrals, outcomes and re-evaluation work |
| `POST /api/follow-through/(tasks|referrals|outcomes|evidence-updates)` | Create governed post-meeting workflow records |
| `POST /api/follow-through/<collection>/<id>/update` | Controlled work or re-evaluation status update |
| `POST /api/reset` | Clear local demo workflow state and reseed the five approved synthetic knowledge fixtures |

---

## Conventions

* The dataset's today is **2026-08-26**. Every ageing calculation is relative to
  that, never to the machine clock.
* Reporting currency is USD. FX direction is read off each series id, since
  `market_context.csv` quotes in market convention.
* Risk is measured at the **household** level across every portfolio, including
  custody. Mandate compliance is measured **per portfolio**, and custody accounts
  are excluded from it entirely.
* Loan-to-value uses **lending value**, never market value.
* `event_log.csv` is the only source for 2026 events.
* `tax_domicile`, not residence, drives tax-aware reasoning — and no tax figure is
  ever computed.

Assumptions that could reasonably be made differently are listed in
[`docs/METHOD.md`](docs/METHOD.md) and attached to the individual insights that
depend on them.

---

*Synthetic dataset. Not investment advice. Not for any use outside the hackathon.*
