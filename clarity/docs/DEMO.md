# Demo run sheet — four minutes

One journey, told end to end, then two clients to show it generalises. Reset
decisions before you start: `POST /api/reset`, or `python -c "from clarity.review import get_store; get_store().reset()"`.

---

## 0:00 — The problem, on one screen

Open the book. Do not explain the product yet; let the screen do it.

> "Priscilla covers twenty clients, 596 million dollars, five snapshots, a
> thousand positions. On a Monday morning her question is not *what does my
> client's portfolio look like*. It is *who do I call first, and what do I say*."

Point at the ranking column.

> "Eighty-three open findings, ranked by a formula we publish: severity, size,
> time pressure. Not a black box score — every row shows why it is where it is."

---

## 0:40 — CL-0014, Lau Chi Ming. Why now.

Click row 1.

> "Number one is a Hong Kong property developer. His Lombard facility sits at
> 69.41% loan-to-value against a 70% margin call trigger. **Zero point five nine
> points of headroom.** A 0.8% fall in his collateral and the bank calls him."

Then the second finding.

> "And he has a *confirmed* HKD 60 million equity contribution due by mid-2027.
> He has 19.4 million dollars of daily-liquidity assets. He can withdraw ninety
> thousand — because the rest is pledged, and selling it and taking the cash out
> removes lending value while the loan stays the same size. That is the whole
> problem in one sentence, and no single report in the bank shows it."

---

## 1:30 — Exposure. The look-through.

Open **Exposure and mandate**.

> "Here is why his collateral is fragile. Golden Harbour Properties is 29.5% of
> everything he owns — but it never appears as one line. It is shares, a
> *subordinated* perpetual, and an accumulator that obliges him to keep buying
> below strike. Three wrappers, three different payoffs, one issuer."

Point at the `underlying_reference` column.

> "We found the accumulator by reading `instruments.underlying_reference`, and we
> show you which field we read it from. Hong Kong property in total is 49% — and
> his source of wealth is Hong Kong property development. The portfolio and the
> business are the same bet. His own RM note says he knows: *'that is why I am
> confident.'*"

---

## 2:10 — Evidence. Where the trust comes from.

Back to **Why now**, click **Evidence** on the top finding.

> "Every number has a source row: file, id, field, snapshot date. The assumptions
> are named — we count a worst-of basket at full notional against each underlying,
> and we say so, and we say what changes if you disagree. Suitability checks run
> before anything is proposed. And when we cannot verify something, we say that
> too: one of his notes references 'three Asian banking majors' the dataset never
> names, so we report it as unknown rather than inventing three banks."

---

## 2:45 — The decision. The human in the loop.

**Review options (3)** on the collateral finding.

> "Three options. Sell HKD 11.2 million of the Asia High Yield Bond Fund and repay
> — and that number is solved, not illustrated: it is the amount that takes
> loan-to-value from 69.41 back to 60, given that fund's 50% advance rate. The
> engine picks that line because it settles daily and costs the least borrowing
> capacity per dollar raised, not because it is the easiest to sell. Second option
> caps withdrawals at what can actually leave. Third is do nothing, with a defined
> trigger — because *do nothing* is a legitimate decision if it is a decision."

Edit the next step, add a note, approve.

> "She picks one, edits the wording, signs it. It goes to the audit trail with her
> name, the timestamp, and the engine's original wording next to hers. Clarity
> never acts."

---

## 3:20 — The brief. What she walks in with.

**Meeting brief**.

> "What to say, what to ask, and what *not* to say — do not quote a tax outcome,
> do not present an RM note as verified fact, do not quote loan-to-value until
> operations confirm the drawn balance. That last one is there because we found
> HKD 2 million of drawdown that the transaction ledger does not explain, and we
> reported it instead of quietly working around it."

Scroll to the draft.

> "And a draft follow-up she edits and sends. Note the flag: his reporting
> language is Traditional Chinese, so it routes through translation."

---

## 3:50 — It generalises

Back to the book. Two fast ones.

**CL-0002:** > "His facility breached its trigger at the half-year and is fine
today — but it was cured by the *market*, not by an action. Nobody repaid
anything. And 68% of his wealth is an unlisted holding carried at a September
2025 mark."

**CL-0005:** > "A *discretionary* sustainable mandate with binding exclusions,
holding 21% in excluded instruments. The bank picked them. Her note says she
believes the policy is being applied."

Close.

> "Signal, understanding, decision, engagement — with the relationship manager in
> charge of all four."

---

## If something breaks

* API down → `python -m clarity.cli client CL-0014` gives the same content in the
  terminal.
* Frontend down → `npm run build` output is served by the API on port 8000.
* Everything down → `clarity/fixtures/client_CL-0014.json` is the frozen payload.

## Questions you will get

**"How do you know the numbers are right?"** 30 tests, run them live. They check
that holdings reconcile to stated AUM at all five snapshots on all 24 portfolios,
that attribution sums exactly to the change in value, and that the loan-to-value
repayment arithmetic lands on its target.

**"Where is the AI?"** At the edge, deliberately. Ranking, breaches, exposures and
option arithmetic are deterministic Python. Language is only ever used to phrase
already-computed facts, with citations attached. That is what makes the evidence
drawer honest — and it is why this could pass a compliance review.

**"Would this work in a real bank?"** The engine is stateless and reads a
normalised view; the API is a thin layer over plain dictionaries; the decision
record already carries actor, timestamp, prior state and the model's original
wording. The parts that would change are storage and entitlements, not the
analytics.
