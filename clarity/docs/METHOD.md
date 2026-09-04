# Method, assumptions and known limits

Everything here is a choice we made that a reviewer could reasonably make
differently. Each one is stated in the product too, attached to the insights that
depend on it — this file is the collected version.

---

## Conventions

| Choice | Why |
|---|---|
| Today is **2026-08-26**, taken from the dataset, never from the system clock | The demo has to give the same answer next week |
| Reporting currency is **USD**, using `holdings.market_value_usd` directly | It reconciles to `portfolios.aum_<date>` converted at that snapshot's FX on all 24 portfolios × 5 snapshots, so there is no reason to re-derive it |
| FX direction is read from the **series id** | `market_context.csv` quotes in market convention: `USDSGD` is SGD per USD, `EURUSD` is USD per EUR. Assuming one direction silently inverts half the book |
| Risk is measured at the **household** level; mandate compliance **per portfolio** | Concentration is invisible one portfolio at a time. Mandates are written per portfolio, and custody accounts have none |
| Loan-to-value uses **lending value**, not market value | Advance rates haircut each asset; illiquid alternatives carry a 0% advance rate and add no borrowing capacity however large they are |
| Only Daily and Weekly tiers count as **realisable inside a month** | Monthly, gated and illiquid positions cannot fund a dated obligation |
| No tax figure is ever calculated | The dataset has no residency history, allowances or acquisition dates. `tax_domicile` is surfaced and the decision is routed to wealth planning |

---

## Assumptions, and what changes if they are wrong

### Worst-of structured products are counted at 100% of notional against *each* named underlying

A worst-of pays the holder's downside on whichever basket member performs worst,
so notional exposure to each name is the conservative reading for a concentration
check. A delta-adjusted treatment would give a smaller number.

**If wrong:** the size of the finding shrinks; the direction does not change.
Affects CL-0014 (accumulator), CL-0001 and CL-0019 (Basket C), CL-0015 (Basket A).

### Positions opened during the period are measured against `cost_basis_base`

Treating a new holding as pure flow at its closing mark hides its loss. CL-0014's
HKD 25m accumulator would appear as a USD 1.9m *inflow* rather than the USD 1.3m
loss it is. Money deployed is taken from the cost basis and everything above or
below it is reported as a price effect.

**If wrong:** a small FX component of the gain is reported as a price effect,
because `cost_basis_base` is struck at the historical rate and the dataset does
not record that rate separately. The total move is unaffected.

### `Annual` means per year; `Annual instalments` means a total spread over the window

The file uses both wordings and they cannot mean the same thing. CN-012 (USD
1.28m, `Annual`) matches CL-0012's stated USD 1.1m annual drawdown as raised in
note N-016, so `Annual` is per year. CN-007 (USD 5m, `Annual instalments`, two
children, a four-year window) read the same way would exceed CL-0006's entire
household wealth, so `instalments` is read as a total.

**If wrong:** CL-0006's obligations are understated by a factor of four. Both
readings are shown per row in the liquidity table with the recurrence attached, so
the RM can check the source.

### Income is annualised by doubling two observed quarters

`transactions.csv` books income at 31 March and 30 June 2026 only.

**If wrong:** semi-annual coupons or irregular distributions make the run rate
over- or under-stated. Check against the coupon schedule before quoting it.

### Withdrawable value from a pledged portfolio is capped at `lending_value − drawn / trigger`

Selling collateral and paying the proceeds out reduces lending value while the
drawn balance is unchanged, so loan-to-value *rises*. This is why CL-0014 has USD
19.4m of daily-liquidity assets and can withdraw USD 90,754 of it.

**If wrong:** overstates what the client can raise without a margin call — the
error would be in the dangerous direction, which is why the conservative reading
was taken.

### The risk-asset ceiling implied by a tolerance score is a reference band

Derived from the mandate bands of the matching strategy, not a bank policy limit.
The mandate band check is the contractual test; this signal adds the client's own
framing to it.

### Source of wealth is linked to a theme by keyword

`clients.source_of_wealth` is matched against a small published term list per
theme, and the matched term is cited in the evidence. The dataset holds no direct
mapping.

**If wrong:** the RM dismisses the insight in one click and it leaves the audit
trail intact.

---

## Data artefacts we found, and what we did about them

| What | Where | What we did |
|---|---|---|
| An unlisted holding carried at a **2025-09-30 mark** across all five snapshots — 68% of CL-0002's household wealth, 330 days stale | `holdings.valuation_date` for `SYN-AL-0308` | Raised as a finding, sized, and added to the brief's "do not say" list so the total is never quoted without its as-at date |
| CF-0002's drawn balance moves **HKD 6m** between February and March, while `transactions.csv` records a single **HKD 4m** drawdown and note N-018 also says 4m | `credit_facilities.csv` vs `transactions.csv` | The HKD 2m gap is reported, not reconciled away. LTV depends on the drawn balance being right, so it is flagged before the number goes to credit risk |
| CN-016 "Outstanding private markets commitments USD 15.8m" restates the uncalled column of COM-001 + COM-002 exactly. CN-008 does the same for COM-003 | `planned_cash_needs.csv` vs `commitments.csv` | Detected by description and amount, counted once from `commitments.csv`, and the removal is reported in the liquidity notes |
| `SYN-SP-0506` references "three Asian banking majors" that the dataset never names | `instruments.underlying_reference` | Reported as unverifiable rather than guessed. It appears under "what we cannot verify" on the exposure tab |
| "Meridian Semiconductor Corp" and "Meridian Private Equity Fund VII" share a word but are unrelated | `instruments.csv` | Explicitly **not** aggregated, and the reason is written into the look-through table |

---

## Known limits

* **No scenario engine yet.** CL-0019 asked what happens if the Strait reopens
  (note N-026) and we surface the question without modelling the answer. The
  data supports it — `market_context.csv` has Brent at five dates — but shipping a
  scenario we could not defend was the worse trade.
* **Duration is a theme, not a number.** We group rate-sensitive positions and
  quote the yield move behind them. We do not compute modified duration, because
  the dataset has no coupon or maturity fields to compute it from.
* **Look-through is curated, not inferred.** Sixty-two instruments make a hand-
  checked map both feasible and more defensible than a string matcher, but it
  would need generating from an instrument master in production.
* **RM decisions persist to a JSON file.** In a bank this is a database with
  retention controls. The shape of the record — actor, timestamp, previous state,
  the engine's original wording alongside the RM's — is the part that matters.
* **Single-currency reporting.** Everything is shown in USD. Several clients read
  their portfolio in EUR, HKD, SGD or JPY, and for CL-0003 the USD view is
  actively misleading — the product says so in words, but does not yet offer a
  currency toggle.
